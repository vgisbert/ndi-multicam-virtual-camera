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
    def __init__(self, channel_id: str, label: str, device_name: Optional[str] = None, backend: Optional[str] = None, width: int = 1920, height: int = 1080, fps: int = 25):
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
        self._lock = threading.RLock()
        
        self._current_frame: Optional[np.ndarray] = None
        self._last_frame_time = 0.0
        self.frames_sent = 0
        self.current_fps = 0.0
        
        # Pre-render standby pattern
        self._standby_pattern = self._create_standby_pattern()

    def update_fps(self, new_fps: float):
        if new_fps and new_fps > 0:
            with self._lock:
                self.fps = new_fps
                if self._cam and hasattr(self._cam, '_fps'):
                    self._cam._fps = new_fps

    def update_resolution(self, width: int, height: int):
        with self._lock:
            if self.width == width and self.height == height:
                return
            self.width = width
            self.height = height
            self._standby_pattern = self._create_standby_pattern()
            self._current_frame = None

    def is_receiving_frames(self) -> bool:
        """Returns True if this virtual camera device is currently receiving live video frames."""
        return (self._current_frame is not None) and (time.time() - self._last_frame_time < 1.2)

    def _create_standby_pattern(self) -> np.ndarray:
        img = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        img[:] = (25, 19, 17) # Background #111319 in BGR
        grid_color = (35, 28, 25)
        step = max(30, int(60 * (self.width / 1920.0)))
        for y in range(0, self.height, step):
            cv2.line(img, (0, y), (self.width, y), grid_color, 1)
        for x in range(0, self.width, step):
            cv2.line(img, (x, 0), (x, self.height), grid_color, 1)
        margin = max(20, int(40 * (self.width / 1920.0)))
        cv2.rectangle(img, (margin, margin), (self.width - margin, self.height - margin), (75, 57, 0), 2)
        return img

    def _render_standby_frame(self) -> np.ndarray:
        img = self._standby_pattern.copy()
        now = time.time()
        cx = self.width // 2
        cy = self.height // 2
        scale = max(0.5, self.width / 1920.0)

        title = f"NDI VIRTUAL CAM  //  {self.label.upper()}"
        subtext = "ESPERANDO FLUJO DE RED LOCAL..."
        cv2.putText(img, title, (int(cx - 360 * scale), int(cy - 40 * scale)), cv2.FONT_HERSHEY_DUPLEX, 1.2 * scale, (255, 240, 0), max(1, int(2 * scale)), cv2.LINE_AA)
        cv2.putText(img, subtext, (int(cx - 280 * scale), int(cy + 30 * scale)), cv2.FONT_HERSHEY_SIMPLEX, 0.8 * scale, (200, 200, 200), max(1, int(2 * scale)), cv2.LINE_AA)

        mins = int(now // 60) % 60
        secs = int(now % 60)
        msecs = int((now * 1000) % 1000)
        tc_str = f"TC: {mins:02d}:{secs:02d}.{msecs:03d}"
        cv2.putText(img, tc_str, (int(self.width - 280 * scale), int(self.height - 40 * scale)), cv2.FONT_HERSHEY_SIMPLEX, 0.65 * scale, (0, 240, 255), 1, cv2.LINE_AA)
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
                "fps": int(self.fps),
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
        fps_counter = 0
        fps_timer = time.time()

        while self._running:
            target_interval = 1.0 / max(1.0, float(self.fps))
            with self._lock:
                cam = self._cam
                if not cam or not self._running:
                    break
                now = time.time()
                if self._current_frame is not None and (now - self._last_frame_time < 0.8):
                    frame_to_send = self._current_frame
                else:
                    frame_to_send = self._render_standby_frame()

            try:
                cam.send(frame_to_send)
                self.frames_sent += 1
                fps_counter += 1

                if time.time() - fps_timer >= 1.0:
                    self.current_fps = fps_counter / (time.time() - fps_timer)
                    fps_counter = 0
                    fps_timer = time.time()

                if not self._running:
                    break
                cam.sleep_until_next_frame()
            except Exception as e:
                time.sleep(target_interval)

    def stop(self):
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.5)
        if self._cam:
            try:
                self._cam.close()
            except Exception as e:
                print(f"[WARN] Error al cerrar dispositivo virtual {self.channel_id}: {e}", flush=True)
            self._cam = None
        self.is_active = False
        self.current_fps = 0.0

    def get_status(self) -> dict:
        return {
            "channel_id": self.channel_id,
            "label": self.label,
            "device": self._cam.device if self._cam else (self.device_name or "Desconectada"),
            "is_active": self.is_active,
            "resolution": f"{self.width}x{self.height}",
            "fps": round(self.current_fps, 1),
            "frames_sent": self.frames_sent
        }


def get_installed_virtual_camera_drivers() -> List[str]:
    """Detects available DirectShow virtual camera output drivers on the system."""
    found = set()
    try:
        import winreg
        guid = '{860BB310-5D01-11d0-BD3B-00A0C911CE86}'
        for root in [winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER]:
            for sub in [f'SOFTWARE\\Classes\\CLSID\\{guid}\\Instance', f'SOFTWARE\\WOW6432Node\\Classes\\CLSID\\{guid}\\Instance']:
                try:
                    k = winreg.OpenKey(root, sub)
                    i = 0
                    while True:
                        try:
                            inst = winreg.EnumKey(k, i)
                            i += 1
                            sk = winreg.OpenKey(k, inst)
                            try:
                                val, _ = winreg.QueryValueEx(sk, 'FriendlyName')
                                if val:
                                    lval = val.lower()
                                    if any(x in lval for x in ['ndi camara', 'unity video capture', 'obs virtual camera']):
                                        found.add(val)
                            except Exception:
                                pass
                            winreg.CloseKey(sk)
                        except WindowsError:
                            break
                    winreg.CloseKey(k)
                except Exception:
                    pass
    except Exception as e:
        print(f"[WARN] Error al enumerar drivers DirectShow del registro: {e}", flush=True)

    known_order = ["NDI Camara 1", "NDI Camara 2", "NDI Camara 3", "NDI Camara 4", "OBS Virtual Camera"]
    result = []
    for name in known_order:
        if name in found or any(name.lower() == f.lower() for f in found):
            result.append(name)

    # Filter duplicate internal Unity names if NDI Camara is registered
    has_ndi = any(r.startswith("NDI Camara") for r in result)
    for f in sorted(found):
        if f not in result and not f.startswith("Cámara Virtual NDI") and not f.startswith("Camara Virtual NDI"):
            if has_ndi and f.startswith("Unity Video Capture"):
                continue
            result.append(f)

    if not result:
        result = ["NDI Camara 1", "NDI Camara 2"]
    return result


class VirtualCameraManager:
    """Coordinates one or multiple simultaneous virtual camera devices."""
    def __init__(self, width: int = 1920, height: int = 1080, fps: int = 25):
        self.width = width
        self.height = height
        self.fps = fps
        self.devices: Dict[str, VirtualCameraDevice] = {}
        self.camera_drivers: Dict[str, str] = {}
        self.is_active = False
        self._lock = threading.RLock()

    def get_or_create_device(self, channel_id: str, label: str, preferred_name: Optional[str] = None, width: Optional[int] = None, height: Optional[int] = None, fps: Optional[float] = None) -> VirtualCameraDevice:
        with self._lock:
            if channel_id not in self.devices:
                backend = "obs" if "OBS" in (preferred_name or "") else "unitycapture"
                w = width or self.width
                h = height or self.height
                f = int(fps or self.fps)
                dev = VirtualCameraDevice(
                    channel_id=channel_id,
                    label=label,
                    device_name=preferred_name or channel_id,
                    backend=backend,
                    width=w,
                    height=h,
                    fps=f
                )
                self.devices[channel_id] = dev
            return self.devices[channel_id]

    def get_driver_for_camera(self, channel_id: str = "", source_label: str = "", ip: str = "") -> str:
        """Resolves the assigned DirectShow driver name for a given camera."""
        with self._lock:
            # 1. Match by channel_id (e.g. cam-0200c0a8096c)
            if channel_id and channel_id in self.camera_drivers:
                return self.camera_drivers[channel_id]
            # 2. Match by IP
            if ip and ip in self.camera_drivers:
                return self.camera_drivers[ip]
            # 3. Match keys in source_label
            for k, v in self.camera_drivers.items():
                if (k and k in channel_id) or (k and k in source_label):
                    return v
            # 4. Default fallback: Cam 2 (192.168.9.171) -> NDI Camara 2, Cam 1 -> NDI Camara 1
            is_c2 = ("2" in source_label) or ("171" in source_label) or ("171" in ip) or ("cam_2" in channel_id) or ("vcam_2" in channel_id)
            return "NDI Camara 2" if is_c2 else "NDI Camara 1"

    def update_driver_mapping(self, new_mapping: dict, protocols_cfg: dict = None):
        """Updates driver associations dynamically and instantaneously."""
        with self._lock:
            self.camera_drivers.update(new_mapping)
            print(f"[VCAM] Asignación de drivers DirectShow actualizada: {self.camera_drivers}", flush=True)

    def get_output_driver_label(self, channel_id: str = "", alias: str = "", ip: str = "", total_online: int = 1) -> str:
        """Returns the DirectShow virtual camera device name assigned to this camera."""
        drv = self.get_driver_for_camera(channel_id=channel_id, source_label=f"{alias} {ip}", ip=ip)
        if not drv or drv in ["(Ninguno)", "Desactivado", "none"]:
            return "Desactivado"
        return drv

    def update_device_resolution(self, channel_id: str, width: int, height: int):
        with self._lock:
            dev = self.devices.get(channel_id)
            if not dev:
                for d in self.devices.values():
                    if d.device_name == channel_id:
                        dev = d
                        break
            if dev:
                dev.update_resolution(width, height)

    def push_frame(self, channel_id: str, frame_bgr: np.ndarray, source_label: str = ""):
        if not self.is_active or not self.devices:
            return

        drv_name = self.get_driver_for_camera(channel_id=channel_id, source_label=source_label)
        if not drv_name or drv_name in ["(Ninguno)", "Desactivado", "none"]:
            return

        dev = self.devices.get(drv_name)
        if not dev:
            for d in self.devices.values():
                if d.device_name == drv_name:
                    dev = d
                    break
        if dev:
            dev.push_frame(frame_bgr, source_label)

    def update_device_fps(self, channel_id: str, fps: float):
        if not fps or fps <= 0:
            return
        drv_name = self.get_driver_for_camera(channel_id=channel_id)
        with self._lock:
            dev = self.devices.get(drv_name)
            if not dev:
                for d in self.devices.values():
                    if d.device_name == drv_name:
                        dev = d
                        break
            if dev:
                dev.update_fps(fps)

    def start_all(self, camera_list: Optional[List[dict]] = None, config: Optional[dict] = None) -> bool:
        """Starts simultaneous virtual camera devices matching camera resolutions."""
        all_ok = True
        cams = list(camera_list or [])
        protocols_cfg = (config or {}).get("camera_protocols", {})
        if config and "camera_drivers" in config:
            self.camera_drivers.update(config["camera_drivers"])

        # First check if unitycapture is installed
        unitycapture_ready = False
        try:
            test_cam = pyvirtualcam.Camera(640, 360, 25, fmt=PixelFormat.BGR, backend="unitycapture")
            test_cam.close()
            unitycapture_ready = True
        except Exception:
            unitycapture_ready = False

        installed = get_installed_virtual_camera_drivers()
        needed_drivers = []
        for name in ["NDI Camara 1", "NDI Camara 2"]:
            if name in installed or unitycapture_ready:
                if name not in needed_drivers:
                    needed_drivers.append(name)

        for drv in self.camera_drivers.values():
            if drv and drv not in ["(Ninguno)", "Desactivado", "none"] and drv not in needed_drivers:
                needed_drivers.append(drv)

        for drv_name in needed_drivers:
            proto = "ndi"
            cam_alias = drv_name
            for c in cams:
                c_drv = self.get_driver_for_camera(channel_id=c.get("cam_id", ""), ip=c.get("ip", ""), source_label=c.get("alias", ""))
                if c_drv == drv_name:
                    proto = c.get("protocol") or protocols_cfg.get(c.get("cam_id", "")) or protocols_cfg.get(c.get("ip", "")) or "ndi"
                    cam_alias = c.get("alias", drv_name)
                    break

            dev_w, dev_h = (1280, 720) if str(proto).lower() == "rtsp" else (self.width, self.height)
            backend = "obs" if "OBS" in drv_name else "unitycapture"

            dev = self.get_or_create_device(
                channel_id=drv_name,
                label=cam_alias,
                preferred_name=drv_name,
                width=dev_w,
                height=dev_h,
                fps=self.fps
            )
            dev.device_name = drv_name
            dev.backend = backend
            ok = dev.start()
            if not ok:
                all_ok = False

        self.is_active = any(d.is_active for d in self.devices.values())
        return self.is_active

    def stop_all(self):
        with self._lock:
            for dev in list(self.devices.values()):
                try:
                    dev.stop()
                except Exception as e:
                    print(f"[WARN] Error al detener dispositivo virtual: {e}", flush=True)
            self.devices.clear()
        self.is_active = False

    def stop(self):
        self.stop_all()

    def get_status(self) -> dict:
        with self._lock:
            statuses = [d.get_status() for d in self.devices.values()]
            active_count = sum(1 for s in statuses if s["is_active"])
            fps_avg = sum(s["fps"] for s in statuses) / max(1, len(statuses))
            primary_label = statuses[0]["label"] if statuses else "NDI Multicam"
            res = statuses[0].get("resolution", f"{self.width}x{self.height}") if statuses else f"{self.width}x{self.height}"
            return {
                "is_active": self.is_active,
                "active_devices_count": active_count,
                "device": f"Multicam ({active_count} dispositivos activos)",
                "resolution": res,
                "fps": round(fps_avg, 1),
                "source_label": primary_label,
                "devices": statuses
            }
