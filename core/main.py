"""
NDI Virtual Camera - Main Application Entrypoint
Integrates NDI Ingest, DirectShow Virtual Camera, Multi-Camera Thumbnails, and Tactical UI.
"""

import os
import sys
import json
import time
import signal
import atexit
import threading
import subprocess
from typing import Optional
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
server_instance = None
is_window_pinned = False

_shutdown_lock = threading.Lock()
_is_shutting_down = False

def cleanup_all(reason="exit"):
    global _is_shutting_down, server_instance, video_pipeline, vcam_manager, discovery_daemon
    with _shutdown_lock:
        if _is_shutting_down:
            return
        _is_shutting_down = True

    print(f"\n[INFO] Ejecutando cierre ordenado y liberacion de recursos ({reason})...", flush=True)

    # 1. Detener pipeline de video y grabador MKV (asegura guardado de videos y finaliza subprocesos)
    if video_pipeline:
        try:
            video_pipeline.stop()
        except Exception as e:
            print(f"[WARN] Error al detener pipeline: {e}", flush=True)

    # 2. Cerrar TODAS las camaras virtuales DirectShow (libera memoria compartida y desbloquea UnityCaptureFilter64.dll)
    if vcam_manager:
        try:
            vcam_manager.stop_all()
        except Exception as e:
            print(f"[WARN] Error al liberar dispositivos virtuales: {e}", flush=True)

    # 3. Detener demonio de autodescubrimiento NDI
    if discovery_daemon:
        try:
            discovery_daemon.stop()
        except Exception as e:
            print(f"[WARN] Error al detener discovery: {e}", flush=True)

    # 4. Cerrar socket HTTP inmediatamente sin esperar keep-alive
    if server_instance:
        try:
            server_instance.server_close()
        except Exception:
            pass

    print("[OK] Todos los recursos, dispositivos virtuales y flujos liberados correctamente.", flush=True)

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
            rec_status = video_pipeline.get_recording_status() if video_pipeline else {"is_recording": False}
            data = {
                "status": "nominal",
                "vcam": vcam_status,
                "is_pinned": is_window_pinned,
                "monitoring_enabled": video_pipeline.is_monitoring_enabled() if video_pipeline else True,
                "preview_fps": video_pipeline.preview_fps if video_pipeline else 4,
                "recording": rec_status
            }
            self._send_json(data)
            return

        elif path == "/api/recording/status":
            rec_status = video_pipeline.get_recording_status() if video_pipeline else {"is_recording": False}
            self._send_json(rec_status)
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
        global is_window_pinned, webview_window
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
            is_window_pinned = not is_window_pinned
            if webview_window:
                try:
                    webview_window.on_top = is_window_pinned
                except Exception as e:
                    print(f"[WARN] No se pudo cambiar on_top en la ventana: {e}")
            self._send_json({"success": True, "is_pinned": is_window_pinned})
            return

        elif path == "/api/monitoring/toggle":
            if video_pipeline:
                new_state = not video_pipeline.is_monitoring_enabled()
                video_pipeline.set_monitoring(new_state)
                self._send_json({"success": True, "monitoring_enabled": new_state})
                return
            self._send_json({"success": False, "error": "Pipeline no disponible"})
            return

        elif path == "/api/monitoring/set":
            if video_pipeline:
                enabled = bool(payload.get("enabled", True))
                video_pipeline.set_monitoring(enabled)
                self._send_json({"success": True, "monitoring_enabled": enabled})
                return
            self._send_json({"success": False, "error": "Pipeline no disponible"})
            return

        elif path == "/api/window/resize":
            camera_count = int(payload.get("camera_count", 1))
            target_h = payload.get("height")
            if webview_window:
                try:
                    if not target_h:
                        if camera_count <= 0:
                            target_h = 280
                        elif camera_count == 1:
                            target_h = 395
                        elif camera_count == 2:
                            target_h = 665
                        else:
                            target_h = min(880, 140 + camera_count * 265)

                    cur_w = 420
                    if hasattr(webview_window, 'width') and webview_window.width:
                        cur_w = webview_window.width
                    webview_window.resize(cur_w, target_h)
                    self._send_json({"success": True, "height": target_h})
                    return
                except Exception as e:
                    print(f"[WARN] Error al redimensionar ventana: {e}")
            self._send_json({"success": False, "error": "Ventana no disponible"})
            return

        elif path == "/api/window/visibility":
            is_visible = bool(payload.get("visible", True))
            if video_pipeline:
                video_pipeline.set_window_visibility(is_visible)
                self._send_json({"success": True, "visible": is_visible})
                return
            self._send_json({"success": False, "error": "Pipeline no disponible"})
            return

        elif path == "/api/recording/toggle":
            if video_pipeline:
                custom_dir = payload.get("output_dir") or app_config.get("recording_dir")
                if video_pipeline.recorder_manager.is_recording:
                    saved = video_pipeline.stop_recording()
                    status = video_pipeline.get_recording_status()
                    status["saved_files"] = saved
                    self._send_json({"success": True, "action": "stopped", "status": status})
                else:
                    ok = video_pipeline.start_recording(custom_dir=custom_dir)
                    status = video_pipeline.get_recording_status()
                    self._send_json({"success": ok, "action": "started", "status": status})
                return
            self._send_json({"success": False, "error": "Pipeline no disponible"})
            return

        elif path == "/api/recording/stop":
            if video_pipeline:
                saved = video_pipeline.stop_recording()
                status = video_pipeline.get_recording_status()
                status["saved_files"] = saved
                self._send_json({"success": True, "action": "stopped", "status": status})
                return
            self._send_json({"success": False, "error": "Pipeline no disponible"})
            return

        elif path == "/api/browse-folder":
            selected_dir = ""
            if webview_window:
                try:
                    import webview
                    res = webview_window.create_file_dialog(webview.FOLDER_DIALOG)
                    if res and len(res) > 0:
                        selected_dir = res[0]
                except Exception as e:
                    print(f"[UI] Error al abrir dialogo de carpeta: {e}", flush=True)
            if not selected_dir:
                try:
                    import tkinter as tk
                    from tkinter import filedialog
                    root = tk.Tk()
                    root.withdraw()
                    root.attributes('-topmost', True)
                    selected_dir = filedialog.askdirectory(title="Seleccionar carpeta de grabaciones")
                    root.destroy()
                except Exception:
                    pass
            self._send_json({"success": bool(selected_dir), "directory": selected_dir or ""})
            return

        elif path == "/api/config":
            vcam_name = payload.get("virtual_camera_name")
            extra_ips = payload.get("extra_ips")
            aliases = payload.get("aliases")
            preview_fps = payload.get("preview_fps")
            rec_dir = payload.get("recording_dir")

            if vcam_name:
                app_config["virtual_camera_name"] = vcam_name
            if rec_dir is not None:
                app_config["recording_dir"] = rec_dir.strip()
            if preview_fps is not None:
                app_config["preview_fps"] = int(preview_fps)
                if video_pipeline:
                    video_pipeline.set_preview_fps(int(preview_fps))
            if extra_ips is not None:
                if "network" not in app_config:
                    app_config["network"] = {}
                app_config["network"]["ndi_extra_ips"] = extra_ips
                if discovery_daemon:
                    discovery_daemon.update_extra_ips(extra_ips)
            if aliases:
                # Chequeo en backend: evitar que se asigne el mismo nombre a dos cámaras distintas
                if discovery_daemon and getattr(discovery_daemon, "cameras", None):
                    cam_map = {}
                    for cam_id, cam in discovery_daemon.cameras.items():
                        alias_val = aliases.get(cam.cam_id) or aliases.get(cam.ip) or aliases.get(cam.url_address)
                        if alias_val:
                            alias_norm = alias_val.strip().lower()
                            if alias_norm in cam_map and cam_map[alias_norm] != cam_id:
                                self._send_json({
                                    "success": False,
                                    "error": f"Nombre duplicado '{alias_val}': cada cámara debe tener un nombre único."
                                })
                                return
                            cam_map[alias_norm] = cam_id

                if "camera_aliases" not in app_config:
                    app_config["camera_aliases"] = {}
                app_config["camera_aliases"].update(aliases)
                for k, v in aliases.items():
                    for cam in discovery_daemon.cameras.values():
                        if cam.url_address == k or cam.ip == k or cam.cam_id == k:
                            cam.alias = v if v else f"Cámara {cam.ip.split('.')[-1]}"

            protocols = payload.get("protocols")
            if protocols:
                if "camera_protocols" not in app_config:
                    app_config["camera_protocols"] = {}
                app_config["camera_protocols"].update(protocols)
                if discovery_daemon:
                    for k, p in protocols.items():
                        for cam in discovery_daemon.cameras.values():
                            if cam.url_address == k or cam.ip == k or cam.cam_id == k:
                                cam.protocol = p.lower()

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

def kill_process_by_pid(pid: int):
    """Fuerza la terminación de un proceso por PID usando taskkill y CIM como fallback."""
    if pid <= 0 or pid == os.getpid():
        return
    try:
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass
    try:
        ps_cmd = f"Invoke-CimMethod -Query 'select * from Win32_Process where ProcessId = {pid}' -MethodName 'Terminate' -ErrorAction SilentlyContinue"
        subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass

def find_pid_by_port(port: int) -> Optional[int]:
    """Detecta el PID del proceso de Windows que retiene el puerto TCP especificado."""
    try:
        output = subprocess.check_output(f"netstat -ano -p tcp | findstr :{port}", shell=True).decode("ascii", errors="ignore")
        for line in output.strip().splitlines():
            parts = line.split()
            if len(parts) >= 5 and "LISTENING" in parts[3].upper():
                return int(parts[4])
    except Exception:
        pass
    return None

def kill_orphan_instances():
    """Detecta y elimina instancias zombies previas de la aplicacion y libera puertos bloqueados."""
    my_pid = os.getpid()

    # 1. Liberar puerto 8765 si está retenido por un proceso previo o zombie
    port_pid = find_pid_by_port(8765)
    if port_pid and port_pid != my_pid:
        print(f"[STARTUP] Detectado puerto 8765 retenido por proceso zombie (PID: {port_pid}). Liberando...", flush=True)
        kill_process_by_pid(port_pid)
        time.sleep(0.3)

    # 2. Si se ejecuta como .exe empaquetado, cerrar cualquier otra instancia previa del mismo ejecutable
    if getattr(sys, "frozen", False):
        exe_name = os.path.basename(sys.executable)
        exe_stem = os.path.splitext(exe_name)[0]
        try:
            ps_cmd = f"Get-Process -Name '{exe_stem}' -ErrorAction SilentlyContinue | Where-Object {{ $_.Id -ne {my_pid} }} | ForEach-Object {{ $_.Id }}"
            res = subprocess.check_output(["powershell", "-NoProfile", "-Command", ps_cmd]).decode("ascii", errors="ignore")
            for p_str in res.split():
                if p_str.strip().isdigit():
                    p = int(p_str.strip())
                    if p != my_pid:
                        print(f"[STARTUP] Finalizando instancia zombie anterior de {exe_name} (PID: {p})...", flush=True)
                        kill_process_by_pid(p)
        except Exception:
            pass

def start_http_server(base_port: int = 8765) -> tuple:
    global server_instance
    class ReusableThreadingServer(ThreadingHTTPServer):
        allow_reuse_address = True
        daemon_threads = True

        def handle_error(self, request, client_address):
            # Silenciar desconexiones forzosas durante el cierre de la aplicacion
            pass

    server = None
    actual_port = base_port

    # Intentar base_port y hasta 10 puertos consecutivos si hubiera colisión insalvable
    for p in range(base_port, base_port + 10):
        try:
            server = ReusableThreadingServer(("127.0.0.1", p), TacticalHttpHandler)
            actual_port = p
            break
        except OSError:
            # Reintentar liberar el puerto si estaba tomado
            pid = find_pid_by_port(p)
            if pid and pid != os.getpid():
                kill_process_by_pid(pid)
                time.sleep(0.2)
                try:
                    server = ReusableThreadingServer(("127.0.0.1", p), TacticalHttpHandler)
                    actual_port = p
                    break
                except OSError:
                    continue

    if not server:
        # Fallback a puerto efímero asignado por el sistema
        server = ReusableThreadingServer(("127.0.0.1", 0), TacticalHttpHandler)
        actual_port = server.server_address[1]

    server_instance = server

    def _safe_serve():
        try:
            server.serve_forever()
        except Exception:
            pass

    t = threading.Thread(target=_safe_serve, daemon=True, name="TacticalHttpServer")
    t.start()
    print(f"[OK] Servidor local de interfaz táctica activo en http://127.0.0.1:{actual_port}")
    return server, actual_port

def main():
    global discovery_daemon, vcam_manager, video_pipeline, webview_window, is_window_pinned

    # 0. Limpiar cualquier instancia zombie previa y asegurar puerto libre (Anti-White-Screen)
    kill_orphan_instances()

    # Registrar handlers de salida del sistema operativo
    def _sig_handler(sig, frame):
        cleanup_all(reason=f"signal_{sig}")
        os._exit(0)

    try:
        signal.signal(signal.SIGINT, _sig_handler)
        signal.signal(signal.SIGTERM, _sig_handler)
    except Exception:
        pass
    atexit.register(cleanup_all, reason="atexit")

    print("=" * 65, flush=True)
    print("   NDI VIRTUAL CAMERA - TACTICAL BROADCAST SUITE", flush=True)
    print("   Compatible con Windows 10 / NDI 6 / DirectShow Video Capture", flush=True)
    print("=" * 65, flush=True)
    print(flush=True)

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
    preview_fps = cfg.get("preview_fps", 4)
    recording_dir = cfg.get("recording_dir")
    video_pipeline = VideoPipeline(discovery_daemon, vcam_manager, preview_fps=preview_fps, recording_dir=recording_dir)
    video_pipeline.start()

    # 5. Start embedded UI server
    server, active_port = start_http_server(base_port=8765)

    # 6. Launch Desktop Window using pywebview (WebView2 Evergreen)
    headless = "--headless" in sys.argv or "-h" in sys.argv
    if not headless:
        try:
            import webview
            print("[INFO] Abriendo ventana nativa de escritorio (Microsoft Edge WebView2)...")
            initial_cams = len([c for c in discovery_daemon.get_all_cameras() if c.get("is_online")]) if discovery_daemon else 1
            initial_h = 395 if initial_cams <= 1 else 665
            webview_window = webview.create_window(
                title="Cámara Virtual NDI",
                url=f"http://127.0.0.1:{active_port}",
                width=420,
                height=initial_h,
                resizable=True,
                frameless=False,
                easy_drag=True,
                on_top=False
            )

            # Auto-pausar monitorización al minimizar ventana
            def _on_window_minimized():
                if video_pipeline:
                    video_pipeline.set_window_visibility(False)

            def _on_window_restored():
                if video_pipeline:
                    video_pipeline.set_window_visibility(True)

            def _on_window_closing():
                cleanup_all(reason="window_closing")
                return True

            def _on_window_closed():
                cleanup_all(reason="window_closed")
                os._exit(0)

            webview_window.events.minimized += _on_window_minimized
            webview_window.events.restored += _on_window_restored
            webview_window.events.closing += _on_window_closing
            webview_window.events.closed += _on_window_closed

            webview.start()
        except Exception as e:
            print(f"[WARN] No se pudo lanzar la ventana webview nativa: {e}")
            print(f"[INFO] Puedes abrir la consola en tu navegador: http://127.0.0.1:{active_port}")
            print("Presiona Ctrl+C para salir.")
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                pass
    else:
        print(f"[INFO] Modo Headless activo. Servidor disponible en: http://127.0.0.1:{active_port}")
        print("Presiona Ctrl+C para salir.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass

    # Cleanup upon exit
    cleanup_all(reason="main_exit")
    print("=" * 65)
    print("NDI Virtual Camera finalizado con exito.")
    print("=" * 65)
    os._exit(0)

if __name__ == "__main__":
    main()
