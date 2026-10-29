"""
Camera Discovery Daemon & Registry
Resolves NDI sources, hardware MAC addresses (ARP), and handles duplicate NDI names.
"""

import time
import socket
import struct
import ctypes
import threading
from typing import Dict, List, Optional, Callable
from ndi_wrapper import get_ndi

_MAC_CACHE: Dict[str, str] = {}

def resolve_mac_address(ip_str: str) -> str:
    """Resolves physical MAC address using Windows SendARP API, cached per IP to avoid flooding."""
    if not ip_str:
        return "02:00:00:00:00:01"
    
    cached = _MAC_CACHE.get(ip_str)
    if cached and not cached.startswith("02:00:"):
        return cached

    try:
        ip_packed = socket.inet_aton(ip_str)
        dest_ip = struct.unpack("!I", ip_packed)[0]
        mac_bytes = (ctypes.c_byte * 6)()
        mac_len = ctypes.c_ulong(6)
        
        # Call iphlpapi.SendARP(dest_ip, 0, mac, &mac_len)
        res = ctypes.windll.iphlpapi.SendARP(socket.htonl(dest_ip), 0, ctypes.byref(mac_bytes), ctypes.byref(mac_len))
        if res == 0:
            mac_str = ":".join(f"{b & 0xFF:02X}" for b in mac_bytes)
            if mac_str != "00:00:00:00:00:00":
                _MAC_CACHE[ip_str] = mac_str
                return mac_str
    except Exception:
        pass
    
    # Fallback synthetic MAC based on IP
    try:
        octets = [int(x) for x in ip_str.split(".")]
        synthetic = f"02:00:{octets[0]:02X}:{octets[1]:02X}:{octets[2]:02X}:{octets[3]:02X}"
        if ip_str not in _MAC_CACHE:
            _MAC_CACHE[ip_str] = synthetic
        return synthetic
    except Exception:
        return "02:00:00:00:00:01"

def probe_tcp_port(ip_str: str, port: int = 5961, timeout_s: float = 0.4) -> Optional[float]:
    """Tests TCP connection and returns RTT latency in milliseconds."""
    t0 = time.perf_counter()
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout_s)
    try:
        res = s.connect_ex((ip_str, port))
        if res == 0:
            latency = (time.perf_counter() - t0) * 1000.0
            return max(1.0, latency)
    except Exception:
        pass
    finally:
        s.close()
    return None

class CameraModel:
    def __init__(self, cam_id: str, ip: str, port: int, mac: str, ndi_name: str, url_address: str, alias: str, protocol: str = "ndi", fps: float = 25.0):
        self.cam_id = cam_id
        self.ip = ip
        self.port = port
        self.mac = mac
        self.ndi_name = ndi_name
        self.url_address = url_address
        self.alias = alias
        self.protocol = protocol.lower() if protocol else "ndi"
        self.is_online = False
        self.latency_ms = 0.0
        self.fps = fps
        self.resolution = "1280x720" if self.protocol == "rtsp" else "1920x1080"
        self.last_seen = 0.0
        self.is_pgm = False

    def to_dict(self) -> dict:
        return {
            "cam_id": self.cam_id,
            "ip": self.ip,
            "port": self.port,
            "mac": self.mac,
            "ndi_name": self.ndi_name,
            "url_address": self.url_address,
            "alias": self.alias,
            "protocol": self.protocol,
            "is_online": self.is_online,
            "latency_ms": round(self.latency_ms, 1),
            "fps": round(self.fps, 1) if (self.is_online and self.fps > 0) else 0.0,
            "resolution": self.resolution,
            "is_pgm": self.is_pgm
        }

class CameraDiscoveryDaemon:
    def __init__(self, config: dict, on_cameras_updated: Optional[Callable] = None):
        self.config = config
        self.on_cameras_updated = on_cameras_updated
        self.cameras: Dict[str, CameraModel] = {}
        self._lock = threading.RLock()
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._finder = None
        self._scanning_active = False
        self._scan_event = threading.Event()
        self._startup_scan_until = 0.0
        self._was_scanning = False

    def set_scanning_active(self, active: bool):
        """Activa o detiene la búsqueda activa en la red (NDI get_sources, ARP SendARP, sondeo TCP)."""
        with self._lock:
            self._scanning_active = active
            if active:
                self._scan_event.set()
                print("[DISCOVERY] Búsqueda activa en red ACTIVADA (Ventana de configuración abierta).", flush=True)
            else:
                self._scan_event.clear()
                print("[DISCOVERY] Búsqueda activa en red DETENIDA (Ventana principal en reposo).", flush=True)

    def is_scanning(self) -> bool:
        return self._scanning_active or (time.time() < self._startup_scan_until)

    def start(self):
        if self._running:
            return
        self._running = True

        # Extraer IPs candidatas configuradas o inferidas de alias/protocolos
        extra_ips = list(self.config.get("network", {}).get("ndi_extra_ips", []))
        if not extra_ips:
            extracted = set()
            for key in list(self.config.get("camera_aliases", {}).keys()) + list(self.config.get("camera_protocols", {}).keys()):
                ip = key.split(":")[0] if ":" in key else key
                if ip.replace(".", "").isdigit() and ip.count(".") == 3:
                    extracted.add(ip)
            if extracted:
                extra_ips = sorted(list(extracted))
            else:
                extra_ips = ["192.168.9.108", "192.168.9.171"]
        
        # Pre-seed configured cameras so they appear in UI even before NDI responds
        aliases = self.config.get("camera_aliases", {})
        protocols = self.config.get("camera_protocols", {})
        default_pgm = self.config.get("selected_source", "")

        for ip in extra_ips:
            # Use fast synthetic MAC for pre-seeding to avoid 4s blocking SendARP timeout if camera is offline
            try:
                octs = [int(x) for x in ip.split(".")]
                mac = f"02:00:{octs[0]:02X}:{octs[1]:02X}:{octs[2]:02X}:{octs[3]:02X}"
            except Exception:
                mac = "02:00:00:00:00:01"
            clean_mac = "".join(c for c in mac if c.isalnum()).lower()
            cam_id = f"cam-{clean_mac}"
            
            # Find configured alias or auto-generate
            alias = aliases.get(f"{ip}:5961") or aliases.get(ip) or aliases.get(cam_id) or (f"Cámara {ip.split('.')[-1]}")
            proto = protocols.get(f"{ip}:5961") or protocols.get(ip) or protocols.get(cam_id) or "ndi"
            url_address = f"{ip}:5961"
            
            cam = CameraModel(
                cam_id=cam_id,
                ip=ip,
                port=5961,
                mac=mac,
                ndi_name="Nuroum V403",
                url_address=url_address,
                alias=alias,
                protocol=proto
            )
            self.cameras[cam_id] = cam

        # Multicamera mode: All cameras start ready/standby
        with self._lock:
            for c in self.cameras.values():
                c.is_pgm = False

        # Initialize NDI Finder with extra_ips
        ndi = get_ndi()
        self._finder = ndi.create_finder(extra_ips)

        # Activar búsqueda en red durante los primeros 8 segundos de arranque
        self._startup_scan_until = time.time() + 8.0
        self._scanning_active = False
        self._was_scanning = True
        self._scan_event.set()

        self._thread = threading.Thread(target=self._scan_loop, daemon=True, name="NDIDiscoveryThread")
        self._thread.start()
        print(f"[OK] Demonio de autodescubrimiento NDI iniciado (fase arranque activa, extra_ips={extra_ips}).", flush=True)

    def _scan_loop(self):
        ndi = get_ndi()
        while self._running:
            now = time.time()
            in_startup = (now < self._startup_scan_until)
            should_scan = self._scanning_active or in_startup

            if not should_scan:
                if self._was_scanning:
                    self._was_scanning = False
                    print("[DISCOVERY] Fase de búsqueda finalizada. Red en reposo (cero ARP / cero sondeo en ventana principal).", flush=True)
                self._scan_event.wait(timeout=1.0)
                continue

            self._was_scanning = True
            try:
                # 1. Query NDI Finder sources
                discovered = ndi.get_sources(self._finder, wait_ms=400)
                if discovered:
                    print(f"[DISCOVERY] NDI fuentes descubiertas ({len(discovered)}): {[s.get('url_address') for s in discovered]}", flush=True)
                
                # 2. Probe each discovered source and preconfigured extra_ips
                with self._lock:
                    for src in discovered:
                        raw_name = src["ndi_name"]
                        url_addr = src["url_address"]
                        
                        # Extract IP and port from url_address (e.g. "192.168.9.108:5961")
                        ip_part = url_addr.split(":")[0] if ":" in url_addr else url_addr
                        port_part = int(url_addr.split(":")[1]) if ":" in url_addr else 5961
                        
                        mac = resolve_mac_address(ip_part)
                        clean_mac = "".join(c for c in mac if c.isalnum()).lower()
                        cam_id = f"cam-{clean_mac}"
                        
                        # Match by existing camera with same IP to prevent cam_id desync
                        existing_cam = None
                        for c in self.cameras.values():
                            if c.ip == ip_part:
                                existing_cam = c
                                break

                        aliases = self.config.get("camera_aliases", {})
                        protocols = self.config.get("camera_protocols", {})
                        if existing_cam is None and cam_id not in self.cameras:
                            alias = aliases.get(url_addr) or aliases.get(ip_part) or aliases.get(cam_id) or aliases.get(raw_name) or f"Cámara {ip_part}"
                            proto = protocols.get(url_addr) or protocols.get(ip_part) or protocols.get(cam_id) or "ndi"
                            self.cameras[cam_id] = CameraModel(
                                cam_id=cam_id,
                                ip=ip_part,
                                port=port_part,
                                mac=mac,
                                ndi_name=raw_name,
                                url_address=url_addr,
                                alias=alias,
                                protocol=proto
                            )
                        else:
                            target_cam = existing_cam if existing_cam else self.cameras[cam_id]
                            target_cam.ndi_name = raw_name
                            target_cam.url_address = url_addr
                            if mac and not mac.startswith("02:00:"):
                                target_cam.mac = mac
                            cfg_alias = aliases.get(url_addr) or aliases.get(ip_part) or aliases.get(target_cam.cam_id)
                            if cfg_alias and target_cam.alias != cfg_alias:
                                target_cam.alias = cfg_alias
                            cfg_proto = protocols.get(url_addr) or protocols.get(ip_part) or protocols.get(target_cam.cam_id)
                            if cfg_proto:
                                target_cam.protocol = cfg_proto.lower()
                                target_cam.resolution = "1280x720" if target_cam.protocol == "rtsp" else "1920x1080"

                    # 3. Health check all cameras (latency probe)
                    now = time.time()
                    for cam in self.cameras.values():
                        latency = probe_tcp_port(cam.ip, cam.port, timeout_s=0.3)
                        if latency is not None:
                            cam.is_online = True
                            cam.latency_ms = latency
                            cam.last_seen = now
                        else:
                            # Also probe RTSP port 554 as secondary check
                            rtsp_lat = probe_tcp_port(cam.ip, 554, timeout_s=0.2)
                            if rtsp_lat is not None:
                                cam.is_online = True
                                cam.latency_ms = rtsp_lat
                                cam.last_seen = now
                            else:
                                if now - cam.last_seen > 3.0:
                                    cam.is_online = False
                                    cam.latency_ms = 0.0

                if self.on_cameras_updated:
                    try:
                        self.on_cameras_updated(self.get_all_cameras())
                    except Exception as e:
                        print(f"[WARN] Error en callback on_cameras_updated: {e}")

            except Exception as e:
                print(f"[WARN] Error en ciclo de escaneo NDI: {e}")

            time.sleep(1.5)

    def get_all_cameras(self) -> List[dict]:
        with self._lock:
            return [cam.to_dict() for cam in self.cameras.values()]

    def get_camera(self, cam_id: str) -> Optional[CameraModel]:
        with self._lock:
            return self.cameras.get(cam_id)

    def get_pgm_camera(self) -> Optional[CameraModel]:
        with self._lock:
            for cam in self.cameras.values():
                if cam.is_pgm:
                    return cam
            # If no PGM designated, pick first online
            for cam in self.cameras.values():
                if cam.is_online:
                    cam.is_pgm = True
                    return cam
            if self.cameras:
                first = list(self.cameras.values())[0]
                first.is_pgm = True
                return first
            return None

    def set_pgm(self, cam_id: str) -> bool:
        with self._lock:
            if cam_id in self.cameras:
                for c in self.cameras.values():
                    c.is_pgm = (c.cam_id == cam_id)
                return True
        return False

    def update_alias(self, cam_id: str, new_alias: str):
        with self._lock:
            if cam_id in self.cameras:
                self.cameras[cam_id].alias = new_alias
                return True
        return False

    def update_extra_ips(self, new_ips: List[str]):
        """Dynamically updates the directed NDI probing list without restarting."""
        clean_ips = [ip.strip() for ip in new_ips if ip.strip()]
        with self._lock:
            if "network" not in self.config:
                self.config["network"] = {}
            self.config["network"]["ndi_extra_ips"] = clean_ips

            existing_ips = {c.ip for c in self.cameras.values()}
            aliases = self.config.get("camera_aliases", {})
            protocols = self.config.get("camera_protocols", {})
            for ip in clean_ips:
                if ip not in existing_ips:
                    try:
                        octs = [int(x) for x in ip.split(".")]
                        mac = f"02:00:{octs[0]:02X}:{octs[1]:02X}:{octs[2]:02X}:{octs[3]:02X}"
                    except Exception:
                        mac = "02:00:00:00:00:01"
                    clean_mac = "".join(c for c in mac if c.isalnum()).lower()
                    cam_id = f"cam-{clean_mac}"
                    alias = aliases.get(f"{ip}:5961") or aliases.get(ip) or aliases.get(cam_id) or f"Cámara {ip.split('.')[-1]}"
                    proto = protocols.get(f"{ip}:5961") or protocols.get(ip) or protocols.get(cam_id) or "ndi"
                    self.cameras[cam_id] = CameraModel(
                        cam_id=cam_id,
                        ip=ip,
                        port=5961,
                        mac=mac,
                        ndi_name="Nuroum V403",
                        url_address=f"{ip}:5961",
                        alias=alias,
                        protocol=proto
                    )

            # Clean up offline pre-seeded cameras that were removed from clean_ips
            for cam_id in list(self.cameras.keys()):
                cam = self.cameras[cam_id]
                if not cam.is_online and cam.ip not in clean_ips:
                    del self.cameras[cam_id]

            # Recreate finder with updated IP list
            ndi = get_ndi()
            old_finder = self._finder
            try:
                self._finder = ndi.create_finder(clean_ips)
                if old_finder:
                    ndi.destroy_finder(old_finder)
                print(f"[DISCOVERY] Sondeo de IPs actualizado dinámicamente en caliente: {clean_ips}", flush=True)
            except Exception as e:
                print(f"[WARN] Error al actualizar NDI finder con nuevas IPs: {e}", flush=True)

    def stop(self):
        self._running = False
        self._scan_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        if self._finder:
            ndi = get_ndi()
            ndi.destroy_finder(self._finder)
            self._finder = None
        print("[OK] Demonio de autodescubrimiento detenido.")
