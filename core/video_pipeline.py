"""
Video Pipeline - Multi-Camera Simultaneous Streamer
Ingests NDI streams for all detected cameras simultaneously at full frame rate (30 fps),
delivering each stream to its corresponding Virtual Camera device and generating live UI thumbnails.
"""

import os
import time
import base64
import ctypes
import threading
import numpy as np
import cv2
import collections
from typing import Dict, Optional, List, Callable
from ndi_wrapper import get_ndi, NDILIB_FRAME_TYPE_VIDEO
from discovery import CameraDiscoveryDaemon
from virtual_cam import VirtualCameraManager
from recorder import MultiCameraRecordingManager

def normalize_broadcast_fps(raw_fps: float) -> float:
    """Normalizes physical frame rates to standard broadcast standards (PAL / NTSC / high rate)."""
    if 23.0 <= raw_fps <= 27.0:
        return 25.0
    elif 28.0 <= raw_fps <= 32.0:
        return 30.0
    elif 48.0 <= raw_fps <= 52.0:
        return 50.0
    elif 58.0 <= raw_fps <= 62.0:
        return 60.0
    return round(raw_fps, 1)

def is_standard_broadcast_fps(fps: float) -> bool:
    """Returns True if the raw rate is near a known broadcast standard, ignoring socket burst drains."""
    return (23.0 <= fps <= 27.0) or (28.0 <= fps <= 32.0) or (48.0 <= fps <= 52.0) or (58.0 <= fps <= 62.0)

class CameraStreamWorker:
    """Manages an active NDI or RTSP receiver and pushes frames to Virtual Camera and Thumbnails."""
    def __init__(self, cam_id: str, ip: str, port: int, ndi_name: str, url_address: str, alias: str, vcam: VirtualCameraManager, monitoring_enabled: bool = True, thumb_fps: float = 4.0, protocol: str = "ndi", on_fps_update: Optional[Callable[[str, float, str], None]] = None):
        self.cam_id = cam_id
        self.ip = ip
        self.port = port
        self.ndi_name = ndi_name
        self.url_address = url_address
        self.alias = alias
        self.vcam = vcam
        self.monitoring_enabled = monitoring_enabled
        self.thumb_fps = thumb_fps
        self.protocol = protocol.lower() if protocol else "ndi"
        self.recorder_manager: Optional[MultiCameraRecordingManager] = None
        self.on_fps_update = on_fps_update
        
        self.latest_thumbnail_b64: Optional[str] = None
        self.measured_fps = 0.0
        self.resolution = "1280x720" if self.protocol == "rtsp" else "1920x1080"
        
        self._receiver = None
        self._cap = None
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

    def start(self):
        if self._running:
            return
        self._running = True
        target_fn = self._worker_rtsp_loop if self.protocol == "rtsp" else self._worker_ndi_loop
        thread_name = f"RTSPWorker-{self.ip}" if self.protocol == "rtsp" else f"NDIWorker-{self.ip}"
        self._thread = threading.Thread(target=target_fn, daemon=True, name=thread_name)
        self._thread.start()

    def _worker_rtsp_loop(self):
        rtsp_url = f"rtsp://{self.ip}:554/live/mainStream"
        os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp|buffer_size;102400|max_delay;500000|fflags;nobuffer|stimeout;2000000"
        self._cap = cv2.VideoCapture(rtsp_url, cv2.CAP_FFMPEG)
        if not self._cap.isOpened():
            print(f"[ERROR] No se pudo conectar a flujo RTSP en {rtsp_url}", flush=True)
            self._running = False
            return

        print(f"[OK] Canal RTSP (720p) activo para: {self.alias} ({rtsp_url})", flush=True)
        last_thumb_time = 0.0
        fps_frame_count = 0
        fps_timer = 0.0
        warmup_frames = 5

        while self._running and self._cap and self._cap.isOpened():
            ret, bgr_img = self._cap.read()
            if not ret or bgr_img is None:
                time.sleep(0.015)
                continue

            now = time.time()
            if warmup_frames > 0:
                warmup_frames -= 1
                fps_timer = now
                fps_frame_count = 0

            h, w = bgr_img.shape[:2]
            self.resolution = f"{w}x{h}"
            fps_frame_count += 1

            # 1. Salida DirectShow hacia cámara virtual
            if self.vcam:
                self.vcam.push_frame(self.cam_id, bgr_img, source_label=f"{self.alias} ({self.ip}) [RTSP]")

            # 2. Grabador MKV
            if self.recorder_manager and self.recorder_manager.is_recording:
                self.recorder_manager.push_frame(self.cam_id, bgr_img)

            # 3. Miniatura UI
            if self.monitoring_enabled:
                target_delay = 1.0 / max(1.0, float(self.thumb_fps))
                if now - last_thumb_time >= target_delay:
                    last_thumb_time = now
                    thumb = cv2.resize(bgr_img, (280, 158), interpolation=cv2.INTER_LINEAR)
                    _, enc = cv2.imencode('.jpg', thumb, [cv2.IMWRITE_JPEG_QUALITY, 65])
                    b64 = base64.b64encode(enc.tobytes()).decode('ascii')
                    with self._lock:
                        self.latest_thumbnail_b64 = f"data:image/jpeg;base64,{b64}"
            else:
                if self.latest_thumbnail_b64 is not None:
                    with self._lock:
                        self.latest_thumbnail_b64 = None

            # Medidor de FPS continuo con ventana de 1.0s y normalización broadcast
            elapsed = now - fps_timer
            if elapsed >= 1.0:
                raw_fps = fps_frame_count / elapsed
                if raw_fps > 0:
                    calc_fps = normalize_broadcast_fps(raw_fps)
                    if calc_fps != self.measured_fps or self.measured_fps == 0.0:
                        self.measured_fps = calc_fps
                        if self.on_fps_update:
                            self.on_fps_update(self.cam_id, self.measured_fps, self.resolution)
                fps_frame_count = 0
                fps_timer = now

        if self._cap:
            try:
                self._cap.release()
            except Exception:
                pass
            self._cap = None
        print(f"[RTSP] Conexión RTSP cerrada para {self.alias}", flush=True)

    def _worker_ndi_loop(self):
        ndi = get_ndi()
        try:
            self._receiver = ndi.create_receiver(
                ndi_name=self.ndi_name,
                url_address=self.url_address,
                recv_name=f"NDI Ingest {self.ip}"
            )
            print(f"[OK] Canal NDI activo para: {self.alias} ({self.url_address})")
        except Exception as e:
            print(f"[ERROR] No se pudo crear receptor NDI para {self.url_address}: {e}")
            self._running = False
            return

        last_thumb_time = 0.0
        fps_frame_count = 0
        fps_timer = 0.0
        warmup_frames = 5

        while self._running and self._receiver:
            frame_type, video_frame = ndi.capture_frame(self._receiver, timeout_ms=35)
            if frame_type == NDILIB_FRAME_TYPE_VIDEO and video_frame:
                try:
                    now = time.time()
                    if warmup_frames > 0:
                        warmup_frames -= 1
                        fps_timer = now
                        fps_frame_count = 0

                    w = video_frame.xres
                    h = video_frame.yres
                    stride = video_frame.line_stride_in_bytes
                    buf_size = stride * h
                    raw_bytes = ctypes.string_at(video_frame.p_data, buf_size)
                    arr = np.frombuffer(raw_bytes, dtype=np.uint8).reshape((h, stride // 4, 4))
                    bgr_img = arr[:h, :w, :3].copy()
                    
                    self.resolution = f"{w}x{h}"
                    fps_frame_count += 1

                    # 1. Push directly to its dedicated Virtual Camera device (always operational)
                    if self.vcam:
                        self.vcam.push_frame(self.cam_id, bgr_img, source_label=f"{self.alias} ({self.ip})")

                    # 2. Push to dual MKV recorder if active
                    if self.recorder_manager and self.recorder_manager.is_recording:
                        self.recorder_manager.push_frame(self.cam_id, bgr_img)

                    # 3. Update UI thumbnail only if monitoring is enabled
                    if self.monitoring_enabled:
                        target_delay = 1.0 / max(1.0, float(self.thumb_fps))
                        if now - last_thumb_time >= target_delay:
                            last_thumb_time = now
                            thumb = cv2.resize(bgr_img, (280, 158), interpolation=cv2.INTER_LINEAR)
                            _, enc = cv2.imencode('.jpg', thumb, [cv2.IMWRITE_JPEG_QUALITY, 65])
                            b64 = base64.b64encode(enc.tobytes()).decode('ascii')
                            with self._lock:
                                self.latest_thumbnail_b64 = f"data:image/jpeg;base64,{b64}"
                    else:
                        if self.latest_thumbnail_b64 is not None:
                            with self._lock:
                                self.latest_thumbnail_b64 = None

                except Exception as e:
                    pass
                finally:
                    ndi.free_frame(self._receiver, video_frame)
            else:
                time.sleep(0.010)

            # Medidor de FPS continuo con ventana de 1.0s y normalización broadcast
            now = time.time()
            if fps_timer > 0.0:
                elapsed = now - fps_timer
                if elapsed >= 1.0:
                    raw_fps = fps_frame_count / elapsed
                    if raw_fps > 0:
                        calc_fps = normalize_broadcast_fps(raw_fps)
                        if calc_fps != self.measured_fps or self.measured_fps == 0.0:
                            self.measured_fps = calc_fps
                            if self.on_fps_update:
                                self.on_fps_update(self.cam_id, self.measured_fps, self.resolution)
                    fps_frame_count = 0
                    fps_timer = now

        if self._receiver:
            ndi.destroy_receiver(self._receiver)
            self._receiver = None

    def get_thumbnail(self) -> Optional[str]:
        with self._lock:
            return self.latest_thumbnail_b64

    def stop(self):
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.5)
        if self._cap:
            try:
                self._cap.release()
            except Exception:
                pass
            self._cap = None


class VideoPipeline:
    def __init__(self, discovery_daemon: CameraDiscoveryDaemon, vcam_manager: VirtualCameraManager, preview_fps: float = 4.0, recording_dir: Optional[str] = None):
        self.discovery = discovery_daemon
        self.vcam = vcam_manager
        self.recorder_manager = MultiCameraRecordingManager(default_dir=recording_dir)
        self.workers: Dict[str, CameraStreamWorker] = {}
        self._running = False
        self._coordinator_thread: Optional[threading.Thread] = None
        self.monitoring_enabled: bool = True
        self.window_visible: bool = True
        self.preview_fps: float = max(1.0, min(30.0, float(preview_fps)))

    def start(self):
        if self._running:
            return
        self._running = True
        self._coordinator_thread = threading.Thread(target=self._coordinator_loop, daemon=True, name="PipelineCoordinator")
        self._coordinator_thread.start()
        print("[OK] Pipeline multicamara simultaneo iniciado.")

    def _on_worker_fps_update(self, cam_id: str, fps: float, resolution: str):
        """Callback invoked immediately when a worker measures physical incoming FPS."""
        cam_model = self.discovery.get_camera(cam_id)
        if cam_model:
            cam_model.fps = fps
            if resolution:
                cam_model.resolution = resolution
        if self.vcam:
            self.vcam.update_device_fps(cam_id, fps)

    def _coordinator_loop(self):
        """Monitors cameras and ensures active stream workers for all online cameras."""
        while self._running:
            try:
                all_cams = self.discovery.get_all_cameras()
                active_ids = set()
                protocols_cfg = self.discovery.config.get("camera_protocols", {})

                # Ensure virtual camera bridge is operational whenever cameras are online
                online_cams = [c for c in all_cams if c.get("is_online")]
                if online_cams and self.vcam and not self.vcam.is_active:
                    self.vcam.start_all(online_cams)

                for cam in all_cams:
                    c_id = cam["cam_id"]
                    is_online = cam["is_online"]
                    url = cam["url_address"]
                    alias = cam.get("alias", f"Camara {cam['ip']}")
                    cam_ip = cam["ip"]
                    desired_proto = (protocols_cfg.get(c_id) or protocols_cfg.get(cam_ip) or cam.get("protocol") or "ndi").lower()

                    if is_online and url:
                        active_ids.add(c_id)
                        # Create or keep worker alive
                        worker = self.workers.get(c_id)
                        if not worker or worker.url_address != url or getattr(worker, "protocol", "ndi") != desired_proto:
                            if worker:
                                worker.stop()
                            new_worker = CameraStreamWorker(
                                cam_id=c_id,
                                ip=cam_ip,
                                port=cam["port"],
                                ndi_name=cam["ndi_name"],
                                url_address=url,
                                alias=alias,
                                vcam=self.vcam,
                                monitoring_enabled=(self.monitoring_enabled and self.window_visible),
                                thumb_fps=self.preview_fps,
                                protocol=desired_proto,
                                on_fps_update=self._on_worker_fps_update
                            )
                            new_worker.recorder_manager = self.recorder_manager
                            new_worker.start()
                            worker = new_worker
                            self.workers[c_id] = new_worker
                        else:
                            worker.alias = alias
                            worker.monitoring_enabled = (self.monitoring_enabled and self.window_visible)
                            worker.thumb_fps = self.preview_fps
                            worker.recorder_manager = self.recorder_manager
                            worker.on_fps_update = self._on_worker_fps_update

                        # Always sync alias, live FPS, resolution, and protocol
                        cam_model = self.discovery.get_camera(c_id)
                        if cam_model and worker:
                            if worker.measured_fps > 0:
                                cam_model.fps = worker.measured_fps
                                if self.vcam:
                                    self.vcam.update_device_fps(c_id, worker.measured_fps)
                            cam_model.resolution = worker.resolution
                            cam_model.protocol = worker.protocol

                # Cleanup workers for cameras that went offline
                for dead_id in list(self.workers.keys()):
                    if dead_id not in active_ids:
                        self.workers[dead_id].stop()
                        del self.workers[dead_id]

            except Exception as e:
                print(f"[WARN] Error en ciclo coordinador de video: {e}", flush=True)

            time.sleep(0.8)

    def _sync_workers_monitoring(self):
        active = self.monitoring_enabled and self.window_visible
        for worker in self.workers.values():
            worker.monitoring_enabled = active
            if not active:
                with worker._lock:
                    worker.latest_thumbnail_b64 = None

    def set_monitoring(self, enabled: bool):
        self.monitoring_enabled = enabled
        self._sync_workers_monitoring()
        state_str = "ACTIVADA" if enabled else "PAUSADA (Modo Rendimiento / Ahorro CPU)"
        print(f"[PERF] Monitorización de vídeo {state_str}", flush=True)

    def set_window_visibility(self, visible: bool):
        if self.window_visible == visible:
            return
        self.window_visible = visible
        self._sync_workers_monitoring()
        if not visible:
            print("[PERF] Ventana minimizada/oculta -> Monitorización en pausa automática (Ahorro CPU)", flush=True)
        else:
            if self.monitoring_enabled:
                print("[PERF] Ventana restaurada/visible -> Monitorización de vídeo reanudada", flush=True)

    def set_preview_fps(self, fps: float):
        self.preview_fps = max(1.0, min(30.0, float(fps)))
        for worker in self.workers.values():
            worker.thumb_fps = self.preview_fps
        print(f"[PERF] Frecuencia de miniatura actualizada a {self.preview_fps:.1f} FPS", flush=True)

    def is_monitoring_enabled(self) -> bool:
        return self.monitoring_enabled and self.window_visible

    def start_recording(self, custom_dir: Optional[str] = None) -> bool:
        return self.recorder_manager.start_recording(self.workers, custom_dir=custom_dir)

    def stop_recording(self) -> List[str]:
        return self.recorder_manager.stop_recording()

    def get_recording_status(self) -> dict:
        return self.recorder_manager.get_status()

    def get_all_thumbnails(self) -> Dict[str, str]:
        if not (self.monitoring_enabled and self.window_visible):
            return {}
        thumbs = {}
        for c_id, w in list(self.workers.items()):
            t = w.get_thumbnail()
            if t:
                thumbs[c_id] = t
        return thumbs

    def stop(self):
        self._running = False
        try:
            self.recorder_manager.stop_recording()
        except Exception:
            pass
        if self._coordinator_thread and self._coordinator_thread.is_alive():
            self._coordinator_thread.join(timeout=1.5)
        for w in self.workers.values():
            w.stop()
        self.workers.clear()
        print("[OK] Pipeline multicamara detenido.")
