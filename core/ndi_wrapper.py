"""
NDI Wrapper - CTypes binding for NewTek / Vizrt Processing.NDI.Lib.x64.dll
Supports NDI 5 and NDI 6
"""

import os
import sys
import ctypes
from typing import List, Dict, Optional, Tuple

class NDIlib_source_t(ctypes.Structure):
    _fields_ = [
        ('p_ndi_name', ctypes.c_char_p),
        ('p_url_address', ctypes.c_char_p)
    ]

class NDIlib_find_create_t(ctypes.Structure):
    _fields_ = [
        ('show_local_sources', ctypes.c_bool),
        ('p_groups', ctypes.c_char_p),
        ('p_extra_ips', ctypes.c_char_p)
    ]

class NDIlib_recv_create_v3_t(ctypes.Structure):
    _fields_ = [
        ('source_to_connect_to', NDIlib_source_t),
        ('color_format', ctypes.c_int), # 0 = BGRX_BGRA, 1 = UYVY_BGRA, 2 = RGBX_RGBA, etc.
        ('bandwidth', ctypes.c_int),    # -100 = metadata only, 0 = lowest/audio, 100 = highest
        ('allow_video_fields', ctypes.c_bool),
        ('p_ndi_recv_name', ctypes.c_char_p)
    ]

class NDIlib_video_frame_v2_t(ctypes.Structure):
    _fields_ = [
        ('xres', ctypes.c_int),
        ('yres', ctypes.c_int),
        ('FourCC', ctypes.c_int),
        ('frame_rate_N', ctypes.c_int),
        ('frame_rate_D', ctypes.c_int),
        ('picture_aspect_ratio', ctypes.c_float),
        ('frame_format_type', ctypes.c_int),
        ('timecode', ctypes.c_int64),
        ('p_data', ctypes.POINTER(ctypes.c_uint8)),
        ('line_stride_in_bytes', ctypes.c_int),
        ('p_metadata', ctypes.c_char_p),
        ('timestamp', ctypes.c_int64)
    ]

# NDI Constants
NDILIB_RECV_COLOR_FORMAT_BGRX_BGRA = 0
NDILIB_RECV_COLOR_FORMAT_UYVY_BGRA = 1
NDILIB_RECV_COLOR_FORMAT_RGBX_RGBA = 2
NDILIB_RECV_BANDWIDTH_HIGHEST = 100

NDILIB_FRAME_TYPE_NONE = 0
NDILIB_FRAME_TYPE_VIDEO = 1
NDILIB_FRAME_TYPE_AUDIO = 2
NDILIB_FRAME_TYPE_METADATA = 3
NDILIB_FRAME_TYPE_ERROR = 4
NDILIB_FRAME_TYPE_STATUS_CHANGE = 100


class NDIWrapper:
    _instance = None

    def __init__(self):
        self.dll = None
        self._initialized = False
        self._load_dll()

    def _load_dll(self):
        bundle_dir = getattr(sys, "_MEIPASS", None)
        exe_dir = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else None
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        candidate_paths = []
        if bundle_dir:
            candidate_paths.extend([
                os.path.join(bundle_dir, "core", "lib", "Processing.NDI.Lib.x64.dll"),
                os.path.join(bundle_dir, "Processing.NDI.Lib.x64.dll"),
            ])
        if exe_dir:
            candidate_paths.extend([
                os.path.join(exe_dir, "core", "lib", "Processing.NDI.Lib.x64.dll"),
                os.path.join(exe_dir, "Processing.NDI.Lib.x64.dll"),
            ])
        candidate_paths.extend([
            os.path.join(base_dir, "core", "lib", "Processing.NDI.Lib.x64.dll"),
            r"C:\Program Files\NDI\NDI 6 Runtime\v6\Processing.NDI.Lib.x64.dll",
            r"C:\Program Files\NDI\NDI 5 Runtime\v5\Processing.NDI.Lib.x64.dll",
        ])

        loaded = False
        for path in candidate_paths:
            if os.path.exists(path):
                try:
                    dll_dir = os.path.dirname(path)
                    if hasattr(os, "add_dll_directory"):
                        os.add_dll_directory(dll_dir)
                    self.dll = ctypes.CDLL(path)
                    loaded = True
                    print(f'[OK] Cargada NDI DLL desde: {path}', flush=True)
                    break
                except Exception as e:
                    print(f"[WARN] Error cargando NDI DLL en {path}: {e}")

        if not loaded:
            raise RuntimeError(
                "No se encontro Processing.NDI.Lib.x64.dll en el sistema ni en core/lib. "
                "Por favor, instala NDI 6 Runtime o verifica los archivos del proyecto."
            )

        # Setup function signatures
        self.dll.NDIlib_initialize.restype = ctypes.c_bool
        self.dll.NDIlib_initialize.argtypes = []

        self.dll.NDIlib_destroy.restype = None
        self.dll.NDIlib_destroy.argtypes = []

        self.dll.NDIlib_version.restype = ctypes.c_char_p
        self.dll.NDIlib_version.argtypes = []

        self.dll.NDIlib_find_create_v2.restype = ctypes.c_void_p
        self.dll.NDIlib_find_create_v2.argtypes = [ctypes.POINTER(NDIlib_find_create_t)]

        self.dll.NDIlib_find_destroy.restype = None
        self.dll.NDIlib_find_destroy.argtypes = [ctypes.c_void_p]

        self.dll.NDIlib_find_wait_for_sources.restype = ctypes.c_bool
        self.dll.NDIlib_find_wait_for_sources.argtypes = [ctypes.c_void_p, ctypes.c_uint32]

        self.dll.NDIlib_find_get_current_sources.restype = ctypes.c_void_p
        self.dll.NDIlib_find_get_current_sources.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint32)]

        self.dll.NDIlib_recv_create_v3.restype = ctypes.c_void_p
        self.dll.NDIlib_recv_create_v3.argtypes = [ctypes.POINTER(NDIlib_recv_create_v3_t)]

        self.dll.NDIlib_recv_destroy.restype = None
        self.dll.NDIlib_recv_destroy.argtypes = [ctypes.c_void_p]

        self.dll.NDIlib_recv_capture_v2.restype = ctypes.c_int
        self.dll.NDIlib_recv_capture_v2.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(NDIlib_video_frame_v2_t),
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.c_uint32
        ]

        self.dll.NDIlib_recv_free_video_v2.restype = None
        self.dll.NDIlib_recv_free_video_v2.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(NDIlib_video_frame_v2_t)
        ]

        # Initialize NDIlib
        if self.dll.NDIlib_initialize():
            self._initialized = True
            v_str = self.dll.NDIlib_version()
            ver = v_str.decode('utf-8', errors='ignore') if v_str else 'Desconocida'
            print(f"[OK] NDI SDK inicializado exitosamente: {ver}")
        else:
            raise RuntimeError("Fallo al inicializar NDIlib (NDIlib_initialize retorno False).")

    def create_finder(self, extra_ips: Optional[List[str]] = None):
        cfg = NDIlib_find_create_t()
        cfg.show_local_sources = True
        cfg.p_groups = None
        if extra_ips:
            ips_str = ",".join(extra_ips).encode('utf-8')
            cfg.p_extra_ips = ips_str
        else:
            cfg.p_extra_ips = None
        p_find = self.dll.NDIlib_find_create_v2(ctypes.byref(cfg))
        return p_find

    def get_sources(self, p_find, wait_ms: int = 250) -> List[Dict[str, str]]:
        if not p_find:
            return []
        self.dll.NDIlib_find_wait_for_sources(p_find, wait_ms)
        num_sources = ctypes.c_uint32(0)
        p_sources = self.dll.NDIlib_find_get_current_sources(p_find, ctypes.byref(num_sources))
        results = []
        if num_sources.value > 0 and p_sources:
            sources_arr = ctypes.cast(p_sources, ctypes.POINTER(NDIlib_source_t))
            for i in range(num_sources.value):
                ndi_name = sources_arr[i].p_ndi_name.decode('utf-8', errors='ignore') if sources_arr[i].p_ndi_name else ""
                url_addr = sources_arr[i].p_url_address.decode('utf-8', errors='ignore') if sources_arr[i].p_url_address else ""
                results.append({
                    "ndi_name": ndi_name,
                    "url_address": url_addr
                })
        return results

    def destroy_finder(self, p_find):
        if p_find and self.dll:
            self.dll.NDIlib_find_destroy(p_find)

    def create_receiver(self, ndi_name: str, url_address: str, recv_name: str = "NDI Virtual Cam"):
        cfg = NDIlib_recv_create_v3_t()
        cfg.source_to_connect_to.p_ndi_name = ndi_name.encode('utf-8') if ndi_name else None
        cfg.source_to_connect_to.p_url_address = url_address.encode('utf-8') if url_address else None
        cfg.color_format = NDILIB_RECV_COLOR_FORMAT_BGRX_BGRA
        cfg.bandwidth = NDILIB_RECV_BANDWIDTH_HIGHEST
        cfg.allow_video_fields = False
        cfg.p_ndi_recv_name = recv_name.encode('utf-8')
        p_recv = self.dll.NDIlib_recv_create_v3(ctypes.byref(cfg))
        return p_recv

    def capture_frame(self, p_recv, timeout_ms: int = 40) -> Tuple[int, Optional[NDIlib_video_frame_v2_t]]:
        if not p_recv:
            return (NDILIB_FRAME_TYPE_NONE, None)
        frame = NDIlib_video_frame_v2_t()
        frame_type = self.dll.NDIlib_recv_capture_v2(p_recv, ctypes.byref(frame), None, None, timeout_ms)
        if frame_type == NDILIB_FRAME_TYPE_VIDEO:
            return (frame_type, frame)
        return (frame_type, None)

    def free_frame(self, p_recv, frame: NDIlib_video_frame_v2_t):
        if p_recv and frame:
            self.dll.NDIlib_recv_free_video_v2(p_recv, ctypes.byref(frame))

    def destroy_receiver(self, p_recv):
        if p_recv and self.dll:
            self.dll.NDIlib_recv_destroy(p_recv)

    def close(self):
        if self._initialized and self.dll:
            self.dll.NDIlib_destroy()
            self._initialized = False

# Singleton instance accessor
_ndi_instance = None

def get_ndi() -> NDIWrapper:
    global _ndi_instance
    if _ndi_instance is None:
        _ndi_instance = NDIWrapper()
    return _ndi_instance
