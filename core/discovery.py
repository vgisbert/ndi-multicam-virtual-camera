"""
Camera Discovery Daemon & Registry
Resolves NDI sources, hardware MAC addresses (ARP), and handles duplicate NDI names.
Periodic scanning is performed strictly while the Configuration screen is open.
"""

import time
import socket
import struct
import ctypes
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Optional, Callable
from ndi_wrapper import get_ndi
from logger import log_camera, log_state_change

_MAC_CACHE: Dict[str, str] = {}


def clear_mac_cache():
    """Limpia la caché de direcciones MAC aprendidas."""
    _MAC_CACHE.clear()


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


def get_local_ipv4_addresses() -> List[str]:
    """Obtiene las direcciones IPv4 locales de las interfaces activas del equipo."""
    local_ips = []
    # 1. Intentar detectar la interfaz de salida principal mediante socket UDP
    for target in [("8.8.8.8", 80), ("192.168.1.1", 80), ("192.168.0.1", 80), ("10.0.0.1", 80)]:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(target)
            ip = s.getsockname()[0]
            s.close()
            if ip and not ip.startswith("127.") and not ip.startswith("169.254.") and ip not in local_ips:
                local_ips.append(ip)
        except Exception:
            pass

    # 2. Añadir el resto de interfaces locales del host
    try:
        _, _, host_ips = socket.gethostbyname_ex(socket.gethostname())
        for ip in host_ips:
            if ip and not ip.startswith("127.") and not ip.startswith("169.254.") and ip not in local_ips:
                local_ips.append(ip)
    except Exception:
        pass

    return local_ips


def sweep_local_subnet_ndi(port: int = 5961, timeout_s: float = 0.20) -> List[str]:
    """
    Escanea de forma ultra-rápida en paralelo la subred local (/24) buscando cámaras con el puerto NDI (5961) activo.
    Resuelve el problema de colisión mDNS cuando dos cámaras tienen el mismo nombre NDI de fábrica en una red nueva.
    """
    local_ips = get_local_ipv4_addresses()
    if not local_ips:
        return []

    prefixes = []
    for lip in local_ips:
        parts = lip.split(".")
        if len(parts) == 4:
            pref = f"{parts[0]}.{parts[1]}.{parts[2]}."
            if pref not in prefixes:
                prefixes.append(pref)

    # Limitar a las 2 primeras subredes físicas para máxima velocidad
    prefixes = prefixes[:2]
    candidates = []
    for pref in prefixes:
        for host in range(1, 255):
            ip_cand = f"{pref}{host}"
            if ip_cand not in local_ips:
                candidates.append(ip_cand)

    found_ips = []

    def _check_ip(ip_addr: str) -> Optional[str]:
        if probe_tcp_port(ip_addr, port, timeout_s=timeout_s) is not None:
            return ip_addr
        return None

    try:
        with ThreadPoolExecutor(max_workers=64) as executor:
            for res in executor.map(_check_ip, candidates):
                if res:
                    found_ips.append(res)
    except Exception:
        pass

    # Ordenar por octeto final numérico
    found_ips.sort(key=lambda x: [int(p) if p.isdigit() else 0 for p in x.split(".")])
    return found_ips


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
        self._was_scanning = False
        self._force_subnet_sweep = False

    def set_scanning_active(self, active: bool):
        """Activa o detiene el sondeo periódico de cámaras (exclusivo de la ventana de configuración)."""
        with self._lock:
            self._scanning_active = active
            if active:
                self._scan_event.set()
                print("[DISCOVERY] Sondeo periódico en red ACTIVADO (Ventana de configuración abierta).", flush=True)
            else:
                self._scan_event.clear()
                print("[DISCOVERY] Sondeo periódico en red DETENIDO (Ventana de configuración cerrada).", flush=True)

    def is_scanning(self) -> bool:
        return self._scanning_active

    def _next_default_alias(self, ip: str) -> str:
        """Genera un alias único ('Cám 1', 'Cám 2', ...) que no esté ya en uso por otra cámara."""
        used = {c.alias.strip().lower() for c in self.cameras.values() if c.alias}
        idx = 1
        while True:
            cand = f"Cám {idx}"
            if cand.lower() not in used and f"cam {idx}" not in used:
                return cand
            idx += 1

    def _register_or_update_camera(self, ip_part: str, port_part: int = 5961, raw_name: str = "Nuroum V403", url_addr: str = "") -> CameraModel:
        """
        Crea o actualiza una cámara evitando duplicidad entre MAC sintética (cam-0200...) y MAC física real.
        """
        if not url_addr:
            url_addr = f"{ip_part}:{port_part}"

        mac = resolve_mac_address(ip_part)
        clean_mac = "".join(c for c in mac if c.isalnum()).lower()
        new_cam_id = f"cam-{clean_mac}"

        # Buscar si ya existe por IP o por cam_id
        existing_cam = None
        existing_key = None
        for k, c in self.cameras.items():
            if c.ip == ip_part or k == new_cam_id:
                existing_cam = c
                existing_key = k
                break

        aliases = self.config.get("camera_aliases", {})
        protocols = self.config.get("camera_protocols", {})

        if existing_cam is None:
            cfg_alias = aliases.get(new_cam_id) or aliases.get(ip_part) or aliases.get(url_addr)
            # Evitar asignar el mismo alias configurado que ya tenga otra cámara activa
            used_aliases = {c.alias.strip().lower() for c in self.cameras.values() if c.alias}
            if not cfg_alias or cfg_alias.strip().lower() in used_aliases:
                alias = self._next_default_alias(ip_part)
            else:
                alias = cfg_alias

            proto = protocols.get(new_cam_id) or protocols.get(ip_part) or protocols.get(url_addr) or "ndi"
            cam = CameraModel(
                cam_id=new_cam_id,
                ip=ip_part,
                port=port_part,
                mac=mac,
                ndi_name=raw_name,
                url_address=url_addr,
                alias=alias,
                protocol=proto
            )
            self.cameras[new_cam_id] = cam
            return cam
        else:
            # Si tenía un cam_id sintético (cam-0200...) y ahora conocemos la MAC física real, migrar clave sin duplicar
            if existing_key != new_cam_id and not mac.startswith("02:00:"):
                if existing_key in self.cameras:
                    del self.cameras[existing_key]
                existing_cam.cam_id = new_cam_id
                existing_cam.mac = mac
                self.cameras[new_cam_id] = existing_cam
            elif not mac.startswith("02:00:"):
                existing_cam.mac = mac

            existing_cam.ip = ip_part
            existing_cam.port = port_part
            if raw_name:
                existing_cam.ndi_name = raw_name
            if url_addr:
                existing_cam.url_address = url_addr

            cfg_alias = aliases.get(existing_cam.cam_id) or aliases.get(ip_part) or aliases.get(url_addr)
            if cfg_alias:
                used_other = {c.alias.strip().lower() for c in self.cameras.values() if c is not existing_cam and c.alias}
                if cfg_alias.strip().lower() not in used_other:
                    existing_cam.alias = cfg_alias

            cfg_proto = protocols.get(existing_cam.cam_id) or protocols.get(ip_part) or protocols.get(url_addr)
            if cfg_proto:
                existing_cam.protocol = cfg_proto.lower()
                existing_cam.resolution = "1280x720" if existing_cam.protocol == "rtsp" else "1920x1080"

            return existing_cam

    def start(self):
        if self._running:
            return
        self._running = True

        # Extraer IPs guardadas en config_camera.json (sin inventar IPs por defecto si fue inicializado desde cero)
        extra_ips = list(self.config.get("network", {}).get("ndi_extra_ips", []))
        if not extra_ips:
            extracted = set()
            for key in list(self.config.get("camera_aliases", {}).keys()) + list(self.config.get("camera_protocols", {}).keys()):
                ip = key.split(":")[0] if ":" in key else key
                if ip.replace(".", "").isdigit() and ip.count(".") == 3:
                    extracted.add(ip)
            if extracted:
                extra_ips = sorted(list(extracted))

        aliases = self.config.get("camera_aliases", {})
        protocols = self.config.get("camera_protocols", {})

        for idx, ip in enumerate(extra_ips):
            try:
                octs = [int(x) for x in ip.split(".")]
                mac = f"02:00:{octs[0]:02X}:{octs[1]:02X}:{octs[2]:02X}:{octs[3]:02X}"
            except Exception:
                mac = "02:00:00:00:00:01"
            clean_mac = "".join(c for c in mac if c.isalnum()).lower()
            cam_id = f"cam-{clean_mac}"

            cfg_alias = aliases.get(cam_id) or aliases.get(ip) or aliases.get(f"{ip}:5961")
            used_aliases = {c.alias.strip().lower() for c in self.cameras.values() if c.alias}
            if not cfg_alias or cfg_alias.strip().lower() in used_aliases:
                alias = f"Cám {idx + 1}"
            else:
                alias = cfg_alias

            proto = protocols.get(cam_id) or protocols.get(ip) or protocols.get(f"{ip}:5961") or "ndi"
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

        with self._lock:
            for c in self.cameras.values():
                c.is_pgm = False

        # Initialize NDI Finder with extra_ips
        ndi = get_ndi()
        self._finder = ndi.create_finder(extra_ips)

        # El sondeo periódico está desactivado en la pantalla principal (solo se activa en Configuración)
        self._scanning_active = False
        self._was_scanning = False
        self._scan_event.clear()

        # Comprobación única de conectividad al arranque para las cámaras ya configuradas (sin sondeo periódico)
        threading.Thread(target=self._initial_configured_check, daemon=True, name="InitialConfiguredCheck").start()

        self._thread = threading.Thread(target=self._scan_loop, daemon=True, name="NDIDiscoveryThread")
        self._thread.start()
        print(f"[OK] Demonio NDI listo (sondeo periódico exclusivo en pantalla de Configuración, extra_ips={extra_ips}).", flush=True)

    def _initial_configured_check(self):
        """Verifica una sola vez al arrancar si las cámaras guardadas en config_camera.json están accesibles."""
        with self._lock:
            cams = list(self.cameras.values())
        if not cams:
            log_state_change("network_has_cameras", False, "no encuentro cámaras en la red")
            return

        now = time.time()
        any_online = False
        for cam in cams:
            lat = probe_tcp_port(cam.ip, cam.port, timeout_s=0.35)
            if lat is None:
                lat = probe_tcp_port(cam.ip, 554, timeout_s=0.25)
            with self._lock:
                if lat is not None:
                    cam.is_online = True
                    cam.latency_ms = lat
                    cam.last_seen = now
                    any_online = True
                    # Resolver MAC real una sola vez si está online
                    real_mac = resolve_mac_address(cam.ip)
                    if real_mac and not real_mac.startswith("02:00:"):
                        self._register_or_update_camera(cam.ip, cam.port, cam.ndi_name, cam.url_address)
                    log_camera(f"cámara activa: {cam.ip} ({cam.alias}) [{cam.protocol.upper()}]")
                else:
                    cam.is_online = False
                    cam.latency_ms = 0.0

        if any_online:
            log_state_change("network_has_cameras", True)
        else:
            log_state_change("network_has_cameras", False, "no encuentro cámaras en la red")

    def reset_discovery_from_zero(self):
        """
        Olvida todas las MACs e IPs descubiertas anteriormente e inicia la búsqueda en la red desde 0.
        Se ejecuta únicamente dentro de la pantalla de configuración.
        """
        with self._lock:
            clear_mac_cache()
            self.cameras.clear()
            if "network" not in self.config:
                self.config["network"] = {}
            self.config["network"]["ndi_extra_ips"] = []
            self.config["camera_aliases"] = {}
            self.config["camera_protocols"] = {}
            self.config["camera_drivers"] = {}
            self.config["selected_source"] = ""

            ndi = get_ndi()
            old_finder = self._finder
            try:
                self._finder = ndi.create_finder([])
                if old_finder:
                    ndi.destroy_finder(old_finder)
            except Exception as e:
                log_camera(f"error al reiniciar buscador NDI: {e}")

            self._force_subnet_sweep = True
            self._scanning_active = True
            self._scan_event.set()
            print("[DISCOVERY] Configuración inicializada desde 0: MACs e IPs previas olvidadas. Escaneando subred...", flush=True)

    def _scan_loop(self):
        ndi = get_ndi()
        while self._running:
            if not self._scanning_active:
                if self._was_scanning:
                    self._was_scanning = False
                    print("[DISCOVERY] Sondeo periódico pausado (fuera de ventana de configuración).", flush=True)
                self._scan_event.wait(timeout=1.0)
                continue

            self._was_scanning = True
            try:
                # 1. Si se solicitó reinicio desde 0 o hay menos de 2 cámaras online, barrer subred local en puerto NDI 5961
                online_count = sum(1 for c in self.cameras.values() if c.is_online)
                if self._force_subnet_sweep or online_count < 2:
                    self._force_subnet_sweep = False
                    subnet_ips = sweep_local_subnet_ndi(port=5961, timeout_s=0.20)
                    if subnet_ips:
                        with self._lock:
                            cur_extra = list(self.config.get("network", {}).get("ndi_extra_ips", []))
                            added_new_ip = False
                            for sip in subnet_ips:
                                self._register_or_update_camera(sip, 5961, "Nuroum V403", f"{sip}:5961")
                                if sip not in cur_extra:
                                    cur_extra.append(sip)
                                    added_new_ip = True
                            if added_new_ip:
                                if "network" not in self.config:
                                    self.config["network"] = {}
                                self.config["network"]["ndi_extra_ips"] = cur_extra
                                old_finder = self._finder
                                try:
                                    self._finder = ndi.create_finder(cur_extra)
                                    if old_finder:
                                        ndi.destroy_finder(old_finder)
                                except Exception:
                                    pass

                # 2. Consultar fuentes NDI a través de NDI Finder
                discovered = ndi.get_sources(self._finder, wait_ms=350)
                if discovered:
                    print(f"[DISCOVERY] NDI fuentes descubiertas ({len(discovered)}): {[s.get('url_address') for s in discovered]}", flush=True)

                with self._lock:
                    for src in discovered:
                        raw_name = src["ndi_name"]
                        url_addr = src["url_address"]
                        ip_part = url_addr.split(":")[0] if ":" in url_addr else url_addr
                        port_part = int(url_addr.split(":")[1]) if ":" in url_addr else 5961
                        self._register_or_update_camera(ip_part, port_part, raw_name, url_addr)

                    # 3. Sondeo de estado y latencia de las cámaras registradas
                    now = time.time()
                    any_online = False
                    for cam in list(self.cameras.values()):
                        was_online = cam.is_online
                        latency = probe_tcp_port(cam.ip, cam.port, timeout_s=0.3)
                        if latency is not None:
                            cam.is_online = True
                            cam.latency_ms = latency
                            cam.last_seen = now
                        else:
                            rtsp_lat = probe_tcp_port(cam.ip, 554, timeout_s=0.2)
                            if rtsp_lat is not None:
                                cam.is_online = True
                                cam.latency_ms = rtsp_lat
                                cam.last_seen = now
                            else:
                                if now - cam.last_seen > 2.5:
                                    cam.is_online = False
                                    cam.latency_ms = 0.0

                        if cam.is_online:
                            any_online = True
                            if not was_online:
                                log_camera(f"cámara activa: {cam.ip} ({cam.alias}) [{cam.protocol.upper()}]")
                        else:
                            if was_online:
                                log_camera(f"cámara desconectada / sin respuesta en la red: {cam.ip} ({cam.alias})")

                    if any_online:
                        log_state_change("network_has_cameras", True)
                    else:
                        log_state_change("network_has_cameras", False, "no encuentro cámaras en la red")

                if self.on_cameras_updated:
                    try:
                        self.on_cameras_updated(self.get_all_cameras())
                    except Exception as e:
                        print(f"[WARN] Error en callback on_cameras_updated: {e}")
                        log_camera(f"error en actualización de cámaras: {e}", key="disc_cb_err", min_interval_s=30.0)

            except Exception as e:
                print(f"[WARN] Error en ciclo de escaneo NDI: {e}")
                log_camera(f"error en ciclo de escaneo NDI: {e}", key="disc_loop_err", min_interval_s=30.0)

            time.sleep(1.2)

    def get_all_cameras(self) -> List[dict]:
        with self._lock:
            # Ordenar por IP para mantener orden consistente (Cám 1, Cám 2)
            cams_sorted = sorted(
                self.cameras.values(),
                key=lambda c: [int(p) if p.isdigit() else 0 for p in c.ip.split(".")]
            )
            return [cam.to_dict() for cam in cams_sorted]

    def get_camera(self, cam_id: str) -> Optional[CameraModel]:
        with self._lock:
            if cam_id in self.cameras:
                return self.cameras[cam_id]
            for c in self.cameras.values():
                if c.ip == cam_id or c.url_address == cam_id:
                    return c
            return None

    def get_pgm_camera(self) -> Optional[CameraModel]:
        with self._lock:
            for cam in self.cameras.values():
                if cam.is_pgm:
                    return cam
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

            for ip in clean_ips:
                self._register_or_update_camera(ip, 5961, "Nuroum V403", f"{ip}:5961")

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
                log_camera(f"error al actualizar buscador NDI con nuevas IPs: {e}")

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
