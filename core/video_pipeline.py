"""
Video Pipeline - Multi-Camera Simultaneous Streamer
Ingests NDI streams for all detected cameras simultaneously at full frame rate (30 fps),
delivering each stream to its corresponding Virtual Camera device and generating live UI thumbnails.
"""

import time
import base64
import ctypes
import threading
import numpy as np
import cv2
from typing import Dict, Optional
from ndi_wrapper import get_ndi, NDILIB_FRAME_TYPE_VIDEO
from discovery import CameraDiscoveryDaemon
from virtual_cam import VirtualCameraManager

class CameraStreamWorker:
    """Manages an active NDI receiver and pushes frames to Virtual Camera and Thumbnails."""
    def __init__(self, cam_id: str, ip: str, port: int, ndi_name: str, url_address: str, alias: str, vcam: VirtualCameraManager):
        self.cam_id = cam_id
        self.ip = ip
        self.port = port
        self.ndi_name = ndi_name
        self.url_address = url_address
        self.alias = alias
        self.vcam = vcam
        
        self.latest_thumbnail_b64: Optional[str] = None
        self.measured_fps = 30.0
        self.resolution = "1920x1080"
        
        self._receiver = None
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._worker_loop, daemon=True, name=f"NDIWorker-{self.ip}")
        self._thread.start()

    def _worker_loop(self):
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
        fps_timer = time.time()

        while self._running and self._receiver:
            frame_type, video_frame = ndi.capture_frame(self._receiver, timeout_ms=35)
            if frame_type == NDILIB_FRAME_TYPE_VIDEO and video_frame:
                try:
                    w = video_frame.xres
                    h = video_frame.yres
                    stride = video_frame.line_stride_in_bytes
                    buf_size = stride * h
                    raw_bytes = ctypes.string_at(video_frame.p_data, buf_size)
                    arr = np.frombuffer(raw_bytes, dtype=np.uint8).reshape((h, stride // 4, 4))
                    bgr_img = arr[:h, :w, :3].copy()
                    
                    self.resolution = f"{w}x{h}"
                    fps_frame_count += 1
                    if video_frame.frame_rate_D > 0 and self.measured_fps == 30.0:
                        stream_fps = round(video_frame.frame_rate_N / video_frame.frame_rate_D, 1)
                        if stream_fps > 0:
                            self.measured_fps = stream_fps

                    # 1. Push directly to its dedicated Virtual Camera device
                    self.vcam.push_frame(self.cam_id, bgr_img, source_label=f"{self.alias} ({self.ip})")

                    # 2. Update UI thumbnail at ~10 fps
                    now = time.time()
                    if now - last_thumb_time >= 0.10:
                        last_thumb_time = now
                        thumb = cv2.resize(bgr_img, (280, 158), interpolation=cv2.INTER_AREA)
                        _, enc = cv2.imencode('.jpg', thumb, [cv2.IMWRITE_JPEG_QUALITY, 70])
                        b64 = base64.b64encode(enc.tobytes()).decode('ascii')
                        with self._lock:
                            self.latest_thumbnail_b64 = f"data:image/jpeg;base64,{b64}"

                except Exception as e:
                    pass
                finally:
                    ndi.free_frame(self._receiver, video_frame)
            else:
                time.sleep(0.010)

            # FPS calculation
            elapsed = time.time() - fps_timer
            if elapsed >= 1.0:
                calc_fps = fps_frame_count / elapsed
                if calc_fps > 0:
                    self.measured_fps = round(calc_fps, 1)
                fps_frame_count = 0
                fps_timer = time.time()

        if self._receiver:
            ndi.destroy_receiver(self._receiver)
            self._receiver = None

    def get_thumbnail(self) -> Optional[str]:
        with self._lock:
            return self.latest_thumbnail_b64

    def stop(self):
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)


class VideoPipeline:
    def __init__(self, discovery_daemon: CameraDiscoveryDaemon, vcam_manager: VirtualCameraManager):
        self.discovery = discovery_daemon
        self.vcam = vcam_manager
        self.workers: Dict[str, CameraStreamWorker] = {}
        self._running = False
        self._coordinator_thread: Optional[threading.Thread] = None

    def start(self):
        if self._running:
            return
        self._running = True
        self._coordinator_thread = threading.Thread(target=self._coordinator_loop, daemon=True, name="PipelineCoordinator")
        self._coordinator_thread.start()
        print("[OK] Pipeline multicamara simultaneo iniciado.")

    def _coordinator_loop(self):
        """Monitors cameras and ensures active stream workers for all online cameras."""
        while self._running:
            all_cams = self.discovery.get_all_cameras()
            active_ids = set()

            for cam in all_cams:
                c_id = cam["cam_id"]
                is_online = cam["is_online"]
                url = cam["url_address"]
                alias = cam.get("alias", f"Camara {cam['ip']}")

                if is_online and url:
                    active_ids.add(c_id)
                    # Create or keep worker alive
                    worker = self.workers.get(c_id)
                    if not worker or worker.url_address != url:
                        if worker:
                            worker.stop()
                        new_worker = CameraStreamWorker(
                            cam_id=c_id,
                            ip=cam["ip"],
                            port=cam["port"],
                            ndi_name=cam["ndi_name"],
                            url_address=url,
                            alias=alias,
                            vcam=self.vcam
                        )
                        new_worker.start()
                        worker = new_worker
                        self.workers[c_id] = new_worker
                    else:
                        worker.alias = alias

                    # Always sync alias, live FPS, and resolution
                    cam_model = self.discovery.get_camera(c_id)
                    if cam_model and worker:
                        if worker.measured_fps > 0:
                            cam_model.fps = worker.measured_fps
                        cam_model.resolution = worker.resolution

            # Cleanup workers for cameras that went offline
            for dead_id in list(self.workers.keys()):
                if dead_id not in active_ids:
                    self.workers[dead_id].stop()
                    del self.workers[dead_id]

            time.sleep(0.8)

    def get_all_thumbnails(self) -> Dict[str, str]:
        thumbs = {}
        for c_id, w in list(self.workers.items()):
            t = w.get_thumbnail()
            if t:
                thumbs[c_id] = t
        return thumbs

    def stop(self):
        self._running = False
        if self._coordinator_thread and self._coordinator_thread.is_alive():
            self._coordinator_thread.join(timeout=1.5)
        for w in self.workers.values():
            w.stop()
        self.workers.clear()
        print("[OK] Pipeline multicamara detenido.")
