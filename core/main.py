"""
NDI Virtual Camera - Main Application Entrypoint
Integrates NDI Ingest, DirectShow Virtual Camera, Multi-Camera Thumbnails, and Tactical UI.
"""

import os
import sys
import json
import time
import threading
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse

# Support both standard script execution and frozen (.exe) standalone execution
if getattr(sys, "frozen", False):
    EXE_DIR = os.path.dirname(sys.executable)
    BUNDLE_DIR = getattr(sys, "_MEIPASS", EXE_DIR)
    BASE_DIR = EXE_DIR
    CORE_DIR = os.path.join(BUNDLE_DIR, "core") if os.path.exists(os.path.join(BUNDLE_DIR, "core")) else BUNDLE_DIR
    UI_DIR = os.path.join(BUNDLE_DIR, "ui") if os.path.exists(os.path.join(BUNDLE_DIR, "ui")) else os.path.join(EXE_DIR, "ui")
    CONFIG_PATH = os.path.join(EXE_DIR, "config.json")
else:
    CORE_DIR = os.path.dirname(os.path.abspath(__file__))
    BASE_DIR = os.path.dirname(CORE_DIR)
    BUNDLE_DIR = BASE_DIR
    UI_DIR = os.path.join(BASE_DIR, "ui")
    CONFIG_PATH = os.path.join(BASE_DIR, "config.json")

ICON_PATH = os.path.join(UI_DIR, "icon.ico")

if CORE_DIR not in sys.path:
    sys.path.insert(0, CORE_DIR)

from ndi_wrapper import get_ndi
from discovery import CameraDiscoveryDaemon
from virtual_cam import VirtualCameraManager
from video_pipeline import VideoPipeline

# Global application state
app_config = {}
discovery_daemon = None
vcam_manager = None
video_pipeline = None
webview_window = None
is_window_pinned = False

def load_config():
    global app_config
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                app_config = json.load(f)
                return app_config
        except Exception as e:
            print(f"[WARN] Error al leer config.json: {e}")
    app_config = {
        "virtual_camera_name": "NDI Virtual Camera",
        "selected_source": "",
        "auto_start_virtual_cam": False,
        "resolution": {"width": 1920, "height": 1080, "fps": 30},
        "camera_aliases": {},
        "network": {"ndi_extra_ips": ["192.168.9.108", "192.168.9.171"]}
    }
    return app_config

def save_config(new_cfg):
    global app_config
    app_config.update(new_cfg)
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(app_config, f, indent=2, ensure_ascii=False)
        print("[OK] config.json actualizado correctamente.")
        return True
    except Exception as e:
        print(f"[ERROR] Error al guardar config.json: {e}")
        return False

class TacticalHttpHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=UI_DIR, **kwargs)

    def end_headers(self):
        # Enable CORS and disable caching
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/api/status":
            vcam_status = vcam_manager.get_status() if vcam_manager else {}
            data = {
                "status": "nominal",
                "vcam": vcam_status,
                "is_pinned": is_window_pinned
            }
            self._send_json(data)
            return

        elif path == "/api/cameras":
            cams = discovery_daemon.get_all_cameras() if discovery_daemon else []
            self._send_json(cams)
            return

        elif path == "/api/thumbnails":
            thumbs = video_pipeline.get_all_thumbnails() if video_pipeline else {}
            self._send_json(thumbs)
            return

        elif path == "/api/config":
            self._send_json(app_config)
            return

        # Serve static UI files
        super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode("utf-8") if length > 0 else "{}"
        try:
            payload = json.loads(body)
        except Exception:
            payload = {}

        if path == "/api/pgm":
            cam_id = payload.get("cam_id")
            if cam_id and discovery_daemon:
                ok = discovery_daemon.set_pgm(cam_id)
                self._send_json({"success": ok, "pgm_cam_id": cam_id})
                return

        elif path == "/api/vcam/toggle":
            if vcam_manager:
                if vcam_manager.is_active:
                    vcam_manager.stop_all()
                else:
                    cams = discovery_daemon.get_all_cameras() if discovery_daemon else []
                    vcam_manager.start_all(cams)
                self._send_json({"success": True, "is_active": vcam_manager.is_active})
                return

        elif path == "/api/pin":
            global is_window_pinned, webview_window
            is_window_pinned = not is_window_pinned
            if webview_window:
                try:
                    webview_window.on_top = is_window_pinned
                except Exception as e:
                    print(f"[WARN] No se pudo cambiar on_top en la ventana: {e}")
            self._send_json({"success": True, "is_pinned": is_window_pinned})
            return

        elif path == "/api/config":
            vcam_name = payload.get("virtual_camera_name")
            extra_ips = payload.get("extra_ips")
            aliases = payload.get("aliases")

            if vcam_name:
                app_config["virtual_camera_name"] = vcam_name
            if extra_ips is not None:
                if "network" not in app_config:
                    app_config["network"] = {}
                app_config["network"]["ndi_extra_ips"] = extra_ips
            if aliases:
                if "camera_aliases" not in app_config:
                    app_config["camera_aliases"] = {}
                app_config["camera_aliases"].update(aliases)
                for k, v in aliases.items():
                    for cam in discovery_daemon.cameras.values():
                        if cam.url_address == k or cam.ip == k or cam.cam_id == k:
                            cam.alias = v if v else f"Cámara {cam.ip.split('.')[-1]}"

            save_config(app_config)
            self._send_json({"success": True, "config": app_config})
            return

        self.send_error(404, "Endpoint no encontrado")

    def _send_json(self, data):
        out = json.dumps(data).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(out)))
        self.end_headers()
        self.wfile.write(out)

    def log_message(self, format, *args):
        # Mute standard HTTP request logs to keep terminal clean
        pass

def start_http_server(port: int = 8765):
    class ReusableThreadingServer(ThreadingHTTPServer):
        allow_reuse_address = True

    server = ReusableThreadingServer(("127.0.0.1", port), TacticalHttpHandler)
    t = threading.Thread(target=server.serve_forever, daemon=True, name="TacticalHttpServer")
    t.start()
    print(f"[OK] Servidor local de interfaz táctica activo en http://127.0.0.1:{port}")
    return server

def main():
    global discovery_daemon, vcam_manager, video_pipeline, webview_window, is_window_pinned

    print("=" * 65)
    print("   NDI VIRTUAL CAMERA - TACTICAL BROADCAST SUITE")
    print("   Compatible con Windows 10 / NDI 6 / DirectShow Video Capture")
    print("=" * 65)
    print()

    # 1. Load configuration
    cfg = load_config()
    res_w = cfg.get("resolution", {}).get("width", 1920)
    res_h = cfg.get("resolution", {}).get("height", 1080)
    res_fps = cfg.get("resolution", {}).get("fps", 30)

    # 2. Initialize Camera Discovery Daemon
    discovery_daemon = CameraDiscoveryDaemon(cfg)
    discovery_daemon.start()

    # 3. Initialize Virtual Camera Manager (Always-On Multicamera Bridge)
    vcam_manager = VirtualCameraManager(width=res_w, height=res_h, fps=res_fps)
    vcam_manager.start_all(discovery_daemon.get_all_cameras())

    # 4. Initialize Video Pipeline
    video_pipeline = VideoPipeline(discovery_daemon, vcam_manager)
    video_pipeline.start()

    # 5. Start embedded UI server
    port = 8765
    server = start_http_server(port=port)

    # 6. Launch Desktop Window using pywebview (WebView2 Evergreen)
    headless = "--headless" in sys.argv or "-h" in sys.argv
    if not headless:
        try:
            import webview
            print("[INFO] Abriendo ventana nativa de escritorio (Microsoft Edge WebView2)...")
            webview_window = webview.create_window(
                title="Cámara Virtual NDI",
                url=f"http://127.0.0.1:{port}",
                width=420,
                height=640,
                resizable=True,
                frameless=False,
                easy_drag=True,
                on_top=False
            )
            webview.start()
        except Exception as e:
            print(f"[WARN] No se pudo lanzar la ventana webview nativa: {e}")
            print(f"[INFO] Puedes abrir la consola en tu navegador: http://127.0.0.1:{port}")
            print("Presiona Ctrl+C para salir.")
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                pass
    else:
        print(f"[INFO] Modo Headless activo. Servidor disponible en: http://127.0.0.1:{port}")
        print("Presiona Ctrl+C para salir.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass

    # Cleanup upon exit
    print("\nCerrando servicios...")
    if server:
        try:
            server.shutdown()
        except Exception:
            pass
    if video_pipeline:
        try:
            video_pipeline.stop()
        except Exception:
            pass
    if vcam_manager:
        try:
            vcam_manager.stop_all()
        except Exception:
            pass
    if discovery_daemon:
        try:
            discovery_daemon.stop()
        except Exception:
            pass
    print("=" * 65)
    print("NDI Virtual Camera finalizado con exito.")
    print("=" * 65)

    # Salida limpia inmediata
    os._exit(0)

if __name__ == "__main__":
    main()
