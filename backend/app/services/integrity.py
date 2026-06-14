import logging
import threading
import socket
import re
import hashlib
from datetime import datetime, timezone, timedelta
from app.schemas import BrowserSignals
from app.services.fingerprint import ParsedAgent

logger = logging.getLogger("visitor_analytics.tracker")

# Thread-safe in-memory stores for honeypot tracking
_lock = threading.Lock()
# maps nonce -> datetime
_triggered_nonces: dict[str, datetime] = {}
# maps nonce -> (visit_id, datetime)
_nonce_to_visit_id: dict[str, tuple[int, datetime]] = {}

# Thread-safe in-memory stores for device tracking
# maps device_hash -> set(ip_addresses)
_device_ips: dict[str, set[str]] = {}
# maps device_hash -> (last_seen_datetime, set(asns))
_device_last_seen: dict[str, tuple[datetime, set[int]]] = {}

RDNS_LOCATION_MAP = {
    "bengaluru": ("Bengaluru", "Karnataka", "India"),
    "bangalore": ("Bengaluru", "Karnataka", "India"),
    "mumbai": ("Mumbai", "Maharashtra", "India"),
    "delhi": ("Delhi", "Delhi", "India"),
    "pune": ("Pune", "Maharashtra", "India"),
    "chennai": ("Chennai", "Tamil Nadu", "India"),
    "hyderabad": ("Hyderabad", "Telangana", "India"),
    "kolkata": ("Kolkata", "West Bengal", "India"),
    "kochi": ("Kochi", "Kerala", "India"),
    "mangalore": ("Mangalore", "Karnataka", "India"),
}


def _lookup_worker(ip: str, result: list):
    try:
        hostname, _, _ = socket.gethostbyaddr(ip)
        result.append(hostname)
    except Exception:
        pass


def get_rdns_hostname(ip: str, timeout: float = 1.0) -> str | None:
    result = []
    t = threading.Thread(target=_lookup_worker, args=(ip, result), daemon=True)
    t.start()
    t.join(timeout)
    if result:
        return result[0]
    return None


def resolve_rdns_location(ip: str) -> tuple[str | None, str | None, str | None]:
    """
    Performs a reverse DNS lookup on the client IP with a strict timeout.
    If keywords are found in the hostname, returns (city, state, country).
    """
    if not ip or ip in {"127.0.0.1", "localhost", "::1"}:
        return None, None, None
    hostname = get_rdns_hostname(ip, timeout=1.0)
    if hostname:
        hostname_lower = hostname.lower()
        for kw, loc in RDNS_LOCATION_MAP.items():
            if kw in hostname_lower:
                return loc
    return None, None, None


def calculate_device_hash(signals: BrowserSignals) -> str | None:
    if not signals.canvas_hash and not signals.webgl_hash:
        return None
    raw = f"{signals.canvas_hash or ''}|{signals.webgl_hash or ''}|{signals.screen_resolution or ''}|{signals.cores or ''}|{signals.memory or ''}|{signals.language or ''}"
    return hashlib.sha256(raw.encode()).hexdigest()


def track_device_ip_and_asn(device_hash: str, ip: str, asn: int | None) -> bool:
    """
    Registers an IP and ASN for a device hash.
    Returns True if a device collision is detected (>= 3 unique IPs or multiple unique ASNs in 15 mins).
    """
    if not device_hash or not ip:
        return False
    with _lock:
        now = datetime.now(timezone.utc)
        
        # Initialize
        if device_hash not in _device_ips:
            _device_ips[device_hash] = set()
            _device_last_seen[device_hash] = (now, set())
            
        _device_ips[device_hash].add(ip)
        _, asns = _device_last_seen[device_hash]
        if asn:
            asns.add(asn)
        _device_last_seen[device_hash] = (now, asns)
        
        # Prune old device hashes (>15 minutes inactive)
        cutoff = now - timedelta(minutes=15)
        for h in list(_device_last_seen.keys()):
            if _device_last_seen[h][0] < cutoff:
                _device_ips.pop(h, None)
                _device_last_seen.pop(h, None)
                
        unique_ips = _device_ips.get(device_hash, set())
        unique_asns = _device_last_seen.get(device_hash, (now, set()))[1]
        
        if len(unique_ips) >= 3 or len(unique_asns) >= 2:
            return True
        return False


def register_honeypot_trigger(nonce: str) -> int | None:
    """
    Registers that a honeypot link was triggered for a given nonce.
    Returns the associated visit_id if the sync request has already occurred.
    """
    if not nonce:
        return None
    with _lock:
        now = datetime.now(timezone.utc)
        _triggered_nonces[nonce] = now
        
        # Prune old entries (>15 mins)
        cutoff = now - timedelta(minutes=15)
        for k in list(_triggered_nonces.keys()):
            if _triggered_nonces[k] < cutoff:
                _triggered_nonces.pop(k, None)
                
        for k in list(_nonce_to_visit_id.keys()):
            if _nonce_to_visit_id[k][1] < cutoff:
                _nonce_to_visit_id.pop(k, None)
                
        val = _nonce_to_visit_id.get(nonce)
        return val[0] if val else None


def register_visit_nonce(nonce: str, visit_id: int):
    """Associates a nonce with a visit_id once the sync request finishes."""
    if not nonce:
        return
    with _lock:
        now = datetime.now(timezone.utc)
        _nonce_to_visit_id[nonce] = (visit_id, now)


def is_honeypot_triggered(nonce: str) -> bool:
    """Checks if a honeypot has been triggered for the given nonce."""
    if not nonce:
        return False
    with _lock:
        if nonce not in _triggered_nonces:
            return False
        now = datetime.now(timezone.utc)
        if now - _triggered_nonces[nonce] < timedelta(minutes=15):
            return True
        return False


def detect_client_spoofing(
    agent: ParsedAgent, 
    signals: BrowserSignals,
    ip: str | None = None,
    ip_country: str | None = None,
    asn: int | None = None
) -> list[str]:
    """
    Analyzes hardware capabilities, WebGL GPU details, and canvas/webgl fingerprint hashes
    against the reported User-Agent, IP, and location context to identify potential bot emulation,
    headless browsers, spoofed devices, or rotating proxies.
    """
    reasons = []
    
    os_name = (agent.os or "").lower()
    browser_name = (agent.browser or "").lower()
    device_type = (agent.device_type or "").lower()
    gpu = (signals.gpu or "").lower()
    
    # 1. Headless Browser / Automation Detection
    # WebGL software renderers are standard indicators of automated runners in headless mode
    if gpu:
        software_gpu_markers = ["google swiftshader", "llvmpipe", "softpipe", "mesa"]
        if any(m in gpu for m in software_gpu_markers):
            reasons.append("headless_software_gpu")
            
    # 2. Operating System vs GPU Mismatch Heuristics
    if gpu and os_name:
        # iOS or macOS must use Apple / Metal / Apple GPU
        if any(m in os_name for m in ["ios", "mac os", "iphone", "ipad"]):
            non_apple_markers = ["nvidia", "geforce", "rtx", "gtx", "amd", "radeon", "intel", "iris", "adreno", "mali", "powervr"]
            # Check if a non-Apple GPU is reported on Apple platforms
            if any(m in gpu for m in non_apple_markers):
                reasons.append("gpu_os_mismatch")
                
        # Android devices should have mobile GPUs (Adreno, Mali, PowerVR)
        elif "android" in os_name:
            desktop_gpu_markers = ["nvidia", "geforce", "rtx", "gtx", "amd", "radeon", "intel", "iris", "arc"]
            if any(m in gpu for m in desktop_gpu_markers) and "apple" not in gpu:
                reasons.append("gpu_os_mismatch")
                
        # Windows/Linux devices shouldn't report Apple GPU
        elif any(m in os_name for m in ["windows", "linux"]):
            if "apple" in gpu:
                reasons.append("gpu_os_mismatch")
                
    # 3. Hardware Capacity vs OS Restrictions (e.g. iOS Privacy Leak)
    # navigator.deviceMemory is blocked on iOS Safari to prevent fingerprinting.
    # If a client claiming to run iOS reports device memory, it is a desktop browser emulating mobile Safari.
    if any(m in os_name for m in ["ios", "iphone", "ipad"]):
        if signals.memory is not None and signals.memory > 0:
            reasons.append("ios_memory_leak")
            
    # 4. Hardware capacity plausibility checks
    if signals.cores is not None and signals.cores > 0:
        # Mobiles with 16+ cores are virtually non-existent or desktop emulation
        if device_type == "mobile" and signals.cores >= 16:
            reasons.append("suspicious_hardware_capacity")
            
        # Desktop browsers reporting 1 core in 2026 is highly suspicious of bot/sandboxed emulation limits
        if device_type == "desktop" and signals.cores == 1:
            reasons.append("suspicious_hardware_capacity")
            
    if signals.memory is not None and signals.memory > 0:
        if device_type == "mobile" and signals.memory > 16:
            reasons.append("suspicious_hardware_capacity")
            
        if device_type == "desktop" and signals.memory <= 1:
            reasons.append("suspicious_hardware_capacity")

    # 5. Canvas & WebGL Hash Fingerprint checks
    canvas_hash = signals.canvas_hash
    webgl_hash = signals.webgl_hash
    
    if device_type == "desktop":
        if not canvas_hash or canvas_hash in {"blank", "blocked", "failed"}:
            reasons.append("missing_canvas_fingerprint")
        if not webgl_hash or webgl_hash in {"blocked", "failed"}:
            reasons.append("missing_webgl_fingerprint")

    # 6. Honeypot check
    if signals.nonce and is_honeypot_triggered(signals.nonce):
        reasons.append("honeypot_triggered")

    # 7. Timezone & Locale Cross-Checking
    if ip_country and signals.timezone:
        country_lower = ip_country.lower()
        tz_lower = signals.timezone.lower()
        if country_lower in {"india", "in"}:
            if "kolkata" not in tz_lower and "calcutta" not in tz_lower:
                reasons.append("timezone_mismatch")
        elif "kolkata" in tz_lower or "calcutta" in tz_lower:
            if country_lower not in {"india", "in"}:
                reasons.append("timezone_mismatch")
                
    if ip_country and (signals.language or signals.accept_language):
        country_lower = ip_country.lower()
        langs = f"{signals.language or ''},{signals.accept_language or ''}".lower()
        if country_lower in {"india", "in"}:
            indian_lang_markers = {"hi", "en", "bn", "ta", "te", "kn", "mr", "gu", "pa", "ur", "or", "ml"}
            client_langs = set(re.findall(r'[a-z]{2}', langs))
            if client_langs and not (client_langs & indian_lang_markers):
                reasons.append("locale_mismatch")

    # 8. Device fingerprint collision check (Proxy detection)
    if ip:
        dev_hash = calculate_device_hash(signals)
        if dev_hash and track_device_ip_and_asn(dev_hash, ip, asn):
            reasons.append("device_collision_detected")

    if reasons:
        logger.warning(
            "[INTEGRITY_CHECK] Spoofing or anomalies detected! UA OS: %s | GPU: %s | Cores: %s | RAM: %s | Flags: %s",
            agent.os, signals.gpu, signals.cores, signals.memory, reasons
        )
        
    return reasons
