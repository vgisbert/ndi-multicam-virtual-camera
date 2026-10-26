"""
NDI Virtual Camera - Dual Camera Recording Engine
Supports crash-resilient MKV recording with hardware encoder auto-detection:
1. NVIDIA NVENC (h264_nvenc)
2. Intel QuickSync (h264_qsv)
3. AMD AMF (h264_amf)
4. CPU Fallback (libx264 ultrafast)
"""

import os
import sys
import time
import re
import queue
import threading
import subprocess
from datetime import datetime
from typing import Dict, List, Optional, Tuple

_DETECTED_ENCODER = None
_DETECTED_ENCODER_INFO = None

def get_ffmpeg_binary() -> str:
    """Finds ffmpeg executable: application directory, bundle directory, or system PATH."""
    candidates = []
    if getattr(sys, "frozen", False):
        exe_dir = os.path.dirname(sys.executable)
        bundle_dir = getattr(sys, "_MEIPASS", exe_dir)
        candidates.extend([
            os.path.join(exe_dir, "ffmpeg.exe"),
            os.path.join(bundle_dir, "ffmpeg.exe"),
        ])
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    candidates.extend([
        os.path.join(base_dir, "ffmpeg.exe"),
        os.path.join(base_dir, "core", "ffmpeg.exe"),
    ])

    for c in candidates:
        if os.path.isfile(c):
            return c
    return "ffmpeg"

def detect_hardware_encoder() -> Tuple[str, str, List[str]]:
    """
    Probes ffmpeg to discover the best available video encoder.
    Returns: (codec_name, display_name, extra_args)
    """
    global _DETECTED_ENCODER, _DETECTED_ENCODER_INFO
    if _DETECTED_ENCODER_INFO is not None:
        return _DETECTED_ENCODER_INFO

    ffmpeg_bin = get_ffmpeg_binary()

    candidates = [
        (
            "h264_nvenc",
            "NVIDIA NVENC (GPU)",
            [
                "-c:v", "h264_nvenc",
                "-preset", "p4",
                "-tune", "ll",
                "-rc", "vbr",
                "-cq", "23",
                "-b:v", "8M",
                "-maxrate", "12M",
                "-bufsize", "16M",
                "-pix_fmt", "yuv420p"
            ]
        ),
        (
            "h264_qsv",
            "Intel QuickSync (GPU)",
            [
                "-c:v", "h264_qsv",
                "-preset", "veryfast",
                "-b:v", "8M",
                "-maxrate", "12M",
                "-look_ahead", "0",
                "-pix_fmt", "nv12"
            ]
        ),
        (
            "h264_amf",
            "AMD AMF (GPU/APU)",
            [
                "-c:v", "h264_amf",
                "-quality", "speed",
                "-rc", "cbr",
                "-b:v", "8M",
                "-pix_fmt", "yuv420p"
            ]
        ),
        (
            "libx264",
            "CPU Software (libx264 ultrafast)",
            [
                "-c:v", "libx264",
                "-preset", "ultrafast",
                "-tune", "zerolatency",
                "-crf", "23",
                "-pix_fmt", "yuv420p"
            ]
        )
    ]

    for codec, name, args in candidates:
        try:
            # Probe with a 256x256 test frame
            probe_cmd = [
                ffmpeg_bin, "-hide_banner", "-loglevel", "error",
                "-f", "lavfi", "-i", "color=c=black:s=256x256:d=0.04",
                "-c:v", codec,
                "-f", "null", "-"
            ]
            res = subprocess.run(
                probe_cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
                timeout=3.0
            )
            if res.returncode == 0:
                _DETECTED_ENCODER = codec
                _DETECTED_ENCODER_INFO = (codec, name, args)
                print(f"[RECORDER] Codificador detectado y validado: {name}", flush=True)
                return _DETECTED_ENCODER_INFO
        except Exception:
            continue

    # Fallback default
    fallback = candidates[-1]
    _DETECTED_ENCODER = fallback[0]
    _DETECTED_ENCODER_INFO = fallback
    print(f"[RECORDER] Fallback a codificador por software: {fallback[1]}", flush=True)
    return _DETECTED_ENCODER_INFO


def sanitize_filename(name: str) -> str:
    """Sanitizes camera name/alias for filesystem use across all OS/charsets."""
    import unicodedata
    name = unicodedata.normalize('NFKD', str(name)).encode('ASCII', 'ignore').decode('utf-8')
    name = re.sub(r'[^\w\s-]', '', name).strip()
    name = re.sub(r'[-\s]+', '_', name)
    return name or "camara"


class SingleCameraRecorder:
    """Handles an independent asynchronous FFmpeg recording pipeline for one camera."""
    def __init__(self, cam_id: str, alias: str, output_path: str, width: int = 1920, height: int = 1080, fps: float = 30.0):
        self.cam_id = cam_id
        self.alias = alias
        self.output_path = output_path
        self.width = width
        self.height = height
        self.fps = fps if fps > 0 else 30.0

        self.frames_written = 0
        self.bytes_written = 0
        self.is_active = False
        
        self._queue: queue.Queue = queue.Queue(maxsize=60)
        self._thread: Optional[threading.Thread] = None
        self._process: Optional[subprocess.Popen] = None
        self._lock = threading.Lock()

    def start(self) -> bool:
        codec, name, enc_args = detect_hardware_encoder()
        
        # Ensure destination directory exists
        os.makedirs(os.path.dirname(os.path.abspath(self.output_path)), exist_ok=True)

        ffmpeg_bin = get_ffmpeg_binary()
        cmd = [
            ffmpeg_bin, "-y", "-hide_banner", "-loglevel", "error",
            "-f", "rawvideo", "-vcodec", "rawvideo",
            "-s", f"{self.width}x{self.height}",
            "-pix_fmt", "bgr24",
            "-r", str(round(self.fps, 2)),
            "-i", "-"
        ] + enc_args + [
            self.output_path
        ]

        try:
            self._process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
                bufsize=10 * 1024 * 1024
            )
            self.is_active = True
            self._thread = threading.Thread(target=self._writer_loop, daemon=True, name=f"Recorder-{self.cam_id}")
            self._thread.start()
            print(f"[RECORDER] Grabación iniciada para '{self.alias}' -> {os.path.basename(self.output_path)} [{name}]", flush=True)
            return True
        except Exception as e:
            print(f"[ERROR] No se pudo iniciar FFmpeg para {self.output_path}: {e}", flush=True)
            self.is_active = False
            return False

    def push_frame(self, frame_bgr):
        if not self.is_active or self._process is None:
            return
        try:
            # Non-blocking put; if queue is full, drop frame for recording to protect live streaming
            self._queue.put_nowait(frame_bgr)
        except queue.Full:
            pass

    def _writer_loop(self):
        while self.is_active:
            try:
                frame = self._queue.get(timeout=0.1)
                if frame is None:
                    break
                if self._process and self._process.stdin:
                    raw = frame.tobytes()
                    self._process.stdin.write(raw)
                    self.frames_written += 1
                    self.bytes_written += len(raw)
                self._queue.task_done()
            except queue.Empty:
                continue
            except Exception:
                break

    def stop(self) -> Optional[str]:
        if not self.is_active:
            return None
        self.is_active = False
        try:
            self._queue.put_nowait(None)
        except Exception:
            pass

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)

        if self._process:
            try:
                if self._process.stdin:
                    self._process.stdin.close()
                self._process.wait(timeout=5.0)
            except Exception as e:
                try:
                    self._process.kill()
                except Exception:
                    pass
            self._process = None

        print(f"[RECORDER] Grabación finalizada: {os.path.basename(self.output_path)} ({self.frames_written} frames)", flush=True)
        return self.output_path


class MultiCameraRecordingManager:
    """Coordinates simultaneous MKV recording across all active camera streams."""
    def __init__(self, default_dir: Optional[str] = None):
        self.default_dir = default_dir or os.path.join(os.getcwd(), "grabaciones")
        self.recorders: Dict[str, SingleCameraRecorder] = {}
        self.is_recording = False
        self.start_time: Optional[float] = None
        self.session_files: List[str] = []
        self._lock = threading.Lock()

    def get_output_dir(self, custom_dir: Optional[str] = None) -> str:
        clean_dir = custom_dir.strip() if (custom_dir and isinstance(custom_dir, str) and custom_dir.strip()) else None
        out_dir = clean_dir or self.default_dir
        if not os.path.isabs(out_dir):
            out_dir = os.path.abspath(out_dir)
        return out_dir

    def start_recording(self, workers: dict, custom_dir: Optional[str] = None) -> bool:
        with self._lock:
            if self.is_recording:
                return True

            out_dir = self.get_output_dir(custom_dir)
            os.makedirs(out_dir, exist_ok=True)

            timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.recorders.clear()
            self.session_files.clear()

            started_count = 0
            used_filenames = set()
            for cam_id, worker in workers.items():
                alias_clean = sanitize_filename(worker.alias or f"cam_{cam_id}")
                filename = f"{timestamp_str}_{alias_clean}.mkv"
                # Protección anti-colisión si dos cámaras tuvieran el mismo alias
                if filename in used_filenames:
                    suffix = worker.ip.split('.')[-1] if (hasattr(worker, 'ip') and worker.ip) else cam_id[-4:]
                    filename = f"{timestamp_str}_{alias_clean}_{suffix}.mkv"
                used_filenames.add(filename)
                filepath = os.path.join(out_dir, filename)

                # Parse resolution
                w, h = 1920, 1080
                try:
                    parts = worker.resolution.split("x")
                    if len(parts) == 2:
                        w, h = int(parts[0]), int(parts[1])
                except Exception:
                    pass

                fps = worker.measured_fps if worker.measured_fps > 0 else 30.0

                rec = SingleCameraRecorder(
                    cam_id=cam_id,
                    alias=worker.alias,
                    output_path=filepath,
                    width=w,
                    height=h,
                    fps=fps
                )
                if rec.start():
                    self.recorders[cam_id] = rec
                    self.session_files.append(filepath)
                    started_count += 1

            if started_count > 0:
                self.is_recording = True
                self.start_time = time.time()
                print(f"[RECORDER] Grabación dual activa en {started_count} cámaras.", flush=True)
                return True
            else:
                self.is_recording = False
                self.start_time = None
                return False

    def push_frame(self, cam_id: str, frame_bgr):
        if not self.is_recording:
            return
        rec = self.recorders.get(cam_id)
        if rec and rec.is_active:
            rec.push_frame(frame_bgr)

    def stop_recording(self) -> List[str]:
        with self._lock:
            if not self.is_recording:
                return []
            self.is_recording = False
            self.start_time = None

            saved = []
            for rec in self.recorders.values():
                path = rec.stop()
                if path:
                    saved.append(path)
            self.recorders.clear()
            return saved

    def get_status(self) -> dict:
        with self._lock:
            codec, name, _ = detect_hardware_encoder()
            duration_s = int(time.time() - self.start_time) if (self.is_recording and self.start_time) else 0
            
            hours = duration_s // 3600
            mins = (duration_s % 3600) // 60
            secs = duration_s % 60
            dur_str = f"{hours:02d}:{mins:02d}:{secs:02d}" if hours > 0 else f"{mins:02d}:{secs:02d}"

            files_info = {}
            for cid, rec in self.recorders.items():
                files_info[cid] = {
                    "alias": rec.alias,
                    "filename": os.path.basename(rec.output_path),
                    "filepath": rec.output_path,
                    "frames": rec.frames_written,
                    "active": rec.is_active
                }

            return {
                "is_recording": self.is_recording,
                "duration_seconds": duration_s,
                "duration_formatted": dur_str,
                "encoder": codec,
                "encoder_display": name,
                "recording_dir": self.default_dir,
                "active_recorders": len(self.recorders),
                "files": files_info
            }
