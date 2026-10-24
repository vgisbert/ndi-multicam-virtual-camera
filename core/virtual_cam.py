"""
Virtual Camera Streamer - Multi-Camera & Dual Device DirectShow Engine
Supports streaming multiple independent virtual cameras simultaneously to Windows (OBS, ManyCam, Zoom, Teams).
Automatically detects UnityCapture (Multi-Cam) or OBS-VirtualCam (Single-Cam fallback).
"""

import time
import threading
import numpy as np
import cv2
from typing import Dict, Optional, List

try:
    import pyvirtualcam
    from pyvirtualcam import PixelFormat
    HAS_PYVIRTUALCAM = True
except ImportError:
    HAS_PYVIRTUALCAM = False
    PixelFormat = None

class VirtualCameraDevice:
    """Represents a single virtual webcam output stream in Windows."""
    def __init__(self, channel_id: str, label: str, device_name: Optional[str] = None, backend: Optional[str] = None, width: int = 1920, height: int = 1080, fps: int = 30):
        self.channel_id = channel_id
        self.label = label
        self.device_name = device_name
        self.backend = backend
        self.width = width
        self.height = height
        self.fps = fps
        
        self.is_active = False
        self._cam = None
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._lock = threading.Lock()
        
        self._current_frame: Optional[np.ndarray] = None
        self._last_frame_time = 0.0
        self.frames_sent = 0
        self.current_fps = 0.0
        
        # Pre-render standby pattern
        self._standby_pattern = self._create_standby_pattern()

    def _create_standby_pattern(self) -> np.ndarray:
        img = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        img[:] = (25, 19, 17) # Background #111319 in BGR
        grid_color = (35, 28, 25)
        for y in range(0, self.height, 60):
            cv2.line(img, (0, y), (self.width, y), grid_color, 1)
        for x in range(0, self.width, 60):
            cv2.line(img, (x, 0), (x, self.height), grid_color, 1)
        cv2.rectangle(img, (40, 40), (self.width - 40, self.height - 40), (75, 57, 0), 2)
        return img

    def _render_standby_frame(self) -> np.ndarray:
        img = self._standby_pattern.copy()
        now = time.time()
        cx = self.width // 2
        cy = self.height // 2

        title = f"NDI VIRTUAL CAM  //  {self.label.upper()}"
        subtext = "ESPERANDO FLUXO DE RED LOCAL NDI..."
        cv2.putText(img, title, (cx - 360, cy - 40), cv2.FONT_HERSHEY_DUPLEX, 1.2, (255, 240, 0), 2, cv2.LINE_AA)
        cv2.putText(img, subtext, (cx - 280, cy + 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (200, 200, 200), 2, cv2.LINE_AA)

        mins = int(now // 60) % 60
        secs = int(now % 60)
        msecs = int((now * 1000) % 1000)
        tc_str = f"TC: {mins:02d}:{secs:02d}.{msecs:03d}"
        cv2.putText(img, tc_str, (self.width - 280, self.height - 60), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 240, 255), 1, cv2.LINE_AA)
        return img

    def push_frame(self, frame_bgr: np.ndarray, source_label: str = ""):
        with self._lock:
            if frame_bgr.shape[0] != self.height or frame_bgr.shape[1] != self.width:
                frame_bgr = cv2.resize(frame_bgr, (self.width, self.height), interpolation=cv2.INTER_LINEAR)
            self._current_frame = frame_bgr
            self._last_frame_time = time.time()
            if source_label:
                self.label = source_label

    def start(self) -> bool:
        if self.is_active:
            return True
        if not HAS_PYVIRTUALCAM:
            return False

        try:
            kwargs = {
                "width": self.width,
                "height": self.height,
                "fps": self.fps,
                "fmt": PixelFormat.BGR,
                "print_fps": False
            }
            if self.device_name:
                kwargs["device"] = self.device_name
            if self.backend:
                kwargs["backend"] = self.backend

            self._cam = pyvirtualcam.Camera(**kwargs)
            self.is_active = True
            self._running = True
            self._thread = threading.Thread(target=self._stream_loop, daemon=True, name=f"VCamStreamer-{self.channel_id}")
            self._thread.start()
            print(f"[OK] Camara Virtual {self.channel_id} iniciada en '{self._cam.device}' ({self.width}x{self.height} @ {self.fps}fps).")
            return True
        except Exception as e:
            print(f"[ERROR] No se pudo inicializar camara virtual {self.channel_id} ({self.device_name}): {e}")
            self.is_active = False
            self._cam = None
            return False

    def _stream_loop(self):
        target_interval = 1.0 / self.fps
        fps_counter = 0
        fps_timer = time.time()

        while self._running and self._cam:
            with self._lock:
                now = time.time()
                if self._current_frame is not None and (now - self._last_frame_time < 0.8):
                    frame_to_send = self._current_frame
                else:
                    frame_to_send = self._render_standby_frame()

            try:
                self._cam.send(frame_to_send)
                self.frames_sent += 1
                fps_counter += 1

                if time.time() - fps_timer >= 1.0:
                    self.current_fps = fps_counter / (time.time() - fps_timer)
                    fps_counter = 0
                    fps_timer = time.time()

                self._cam.sleep_until_next_frame()
            except Exception as e:
                time.sleep(target_interval)

    def stop(self):
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
        if self._cam:
            try:
                self._cam.close()
            except Exception:
                pass
            self._cam = None
        self.is_active = False
        self.current_fps = 0.0

    def get_status(self) -> dict:
        return {
            "channel_id": self.channel_id,
            "label": self.label,
            "device": self._cam.device if self._cam else (self.device_name or "Desconectada"),
            "is_active": self.is_active,
            "fps": round(self.current_fps, 1),
            "frames_sent": self.frames_sent
        }


class VirtualCameraManager:
    """Coordinates one or multiple simultaneous virtual camera devices."""
    def __init__(self, width: int = 1920, height: int = 1080, fps: int = 30):
        self.width = width
        self.height = height
        self.fps = fps
        self.devices: Dict[str, VirtualCameraDevice] = {}
        self.is_active = False
        self._lock = threading.Lock()

    def get_or_create_device(self, channel_id: str, label: str, preferred_name: Optional[str] = None) -> VirtualCameraDevice:
        with self._lock:
            if channel_id not in self.devices:
                # Try unitycapture backend first for multicam support
                backend = "unitycapture"
                dev = VirtualCameraDevice(
                    channel_id=channel_id,
                    label=label,
                    device_name=preferred_name,
                    backend=backend,
                    width=self.width,
                    height=self.height,
                    fps=self.fps
                )
                self.devices[channel_id] = dev
            return self.devices[channel_id]

    def push_frame(self, channel_id: str, frame_bgr: np.ndarray, source_label: str = ""):
        dev = self.devices.get(channel_id)
        if not dev and self.devices:
            for d in self.devices.values():
                if d.channel_id == channel_id or (source_label and (d.label in source_label or source_label in d.label)):
                    dev = d
                    break
        if dev:
            dev.push_frame(frame_bgr, source_label)

    def start_all(self, camera_list: List[dict]) -> bool:
        """Starts simultaneous virtual camera devices for each camera in the list."""
        all_ok = True
        # Device names for UnityCapture multi-camera backend
        device_names = [
            "Unity Video Capture",
            "Unity Video Capture #2",
            "Unity Video Capture #3",
            "Unity Video Capture #4"
        ]

        # First check if unitycapture is installed
        unitycapture_ready = False
        try:
            test_cam = pyvirtualcam.Camera(640, 360, 30, fmt=PixelFormat.BGR, backend="unitycapture")
            test_cam.close()
            unitycapture_ready = True
        except Exception:
            unitycapture_ready = False

        for idx, cam_dict in enumerate(camera_list):
            c_id = cam_dict["cam_id"]
            alias = cam_dict.get("alias") or f"Camara {idx+1}"
            
            if unitycapture_ready:
                pref_name = device_names[idx] if idx < len(device_names) else None
                dev = self.get_or_create_device(c_id, alias, preferred_name=pref_name)
                dev.device_name = pref_name
                dev.backend = "unitycapture"
            else:
                # Fallback to single-camera OBS backend for primary camera
                if idx == 0:
                    dev = self.get_or_create_device(c_id, alias, preferred_name="OBS Virtual Camera")
                    dev.backend = "obs"
                else:
                    continue

            ok = dev.start()
            if not ok:
                all_ok = False

        self.is_active = any(d.is_active for d in self.devices.values())
        return self.is_active

    def stop_all(self):
        with self._lock:
            for dev in self.devices.values():
                dev.stop()
        self.is_active = False

    def stop(self):
        self.stop_all()

    def get_status(self) -> dict:
        with self._lock:
            statuses = [d.get_status() for d in self.devices.values()]
            active_count = sum(1 for s in statuses if s["is_active"])
            fps_avg = sum(s["fps"] for s in statuses) / max(1, len(statuses))
            primary_label = statuses[0]["label"] if statuses else "NDI Multicam"
            return {
                "is_active": self.is_active,
                "active_devices_count": active_count,
                "device": f"Multicam ({active_count} dispositivos activos)",
                "resolution": f"{self.width}x{self.height}",
                "fps": round(fps_avg, 1),
                "source_label": primary_label,
                "devices": statuses
            }
