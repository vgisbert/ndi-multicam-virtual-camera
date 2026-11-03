"""
Sistema de registro de incidencias y eventos en producción (camera.log).
Formato de línea: <aammdd-hhmmss> <mensaje>
"""

import os
import sys
import time
import traceback
import threading
from datetime import datetime
from typing import Optional, Dict, Any

if getattr(sys, "frozen", False):
    WORK_DIR = os.path.dirname(sys.executable)
else:
    WORK_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

LOG_FILE_PATH = os.path.join(WORK_DIR, "camera.log")

_log_lock = threading.RLock()
_last_key_time: Dict[str, float] = {}
_last_state: Dict[str, Any] = {}


def log_camera(message: str, key: Optional[str] = None, min_interval_s: float = 0.0):
    """
    Escribe una entrada en camera.log con formato: <aammdd-hhmmss> <mensaje>.
    Si se especifica `key` y `min_interval_s`, evita repetir la misma incidencia dentro del intervalo.
    """
    now = time.time()
    with _log_lock:
        if key is not None and min_interval_s > 0.0:
            last_t = _last_key_time.get(key, 0.0)
            if now - last_t < min_interval_s:
                return
            _last_key_time[key] = now

        ts = datetime.now().strftime("%y%m%d-%H%M%S")
        line = f"{ts} {message}\n"
        try:
            with open(LOG_FILE_PATH, "a", encoding="utf-8") as f:
                f.write(line)
        except Exception:
            pass


def log_state_change(key: str, new_state: Any, message: Optional[str] = None):
    """
    Registra el mensaje en camera.log únicamente cuando el estado asociado a `key` cambia.
    Devuelve True si hubo cambio de estado.
    """
    with _log_lock:
        old_state = _last_state.get(key, object())
        if old_state == new_state:
            return False
        _last_state[key] = new_state
        if message:
            log_camera(message)
        return True


def install_exception_hooks():
    """Instala manejadores globales para registrar cualquier excepción no controlada en camera.log."""
    orig_excepthook = sys.excepthook

    def _custom_excepthook(exc_type, exc_value, exc_tb):
        if issubclass(exc_type, KeyboardInterrupt):
            orig_excepthook(exc_type, exc_value, exc_tb)
            return
        tb_short = "".join(traceback.format_exception_only(exc_type, exc_value)).strip()
        log_camera(f"error crítico en la aplicación: {tb_short}")
        orig_excepthook(exc_type, exc_value, exc_tb)

    sys.excepthook = _custom_excepthook

    if hasattr(threading, "excepthook"):
        orig_thread_hook = threading.excepthook

        def _custom_thread_hook(args):
            if issubclass(args.exc_type, SystemExit):
                return
            tb_short = "".join(traceback.format_exception_only(args.exc_type, args.exc_value)).strip()
            t_name = args.thread.name if args.thread else "Thread"
            log_camera(f"error en hilo ({t_name}) de la aplicación: {tb_short}")
            orig_thread_hook(args)

        threading.excepthook = _custom_thread_hook
