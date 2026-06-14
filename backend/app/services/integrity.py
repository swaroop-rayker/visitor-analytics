import logging
from app.schemas import BrowserSignals
from app.services.fingerprint import ParsedAgent

logger = logging.getLogger("visitor_analytics.tracker")

def detect_client_spoofing(agent: ParsedAgent, signals: BrowserSignals) -> list[str]:
    """
    Analyzes hardware capabilities and WebGL GPU details against the parsed User-Agent
    to identify potential bot emulation, headless browsers, or spoofed devices.
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

    if reasons:
        logger.warning(
            "[INTEGRITY_CHECK] Spoofing detected! UA OS: %s | GPU: %s | Cores: %s | RAM: %s | Flags: %s",
            agent.os, signals.gpu, signals.cores, signals.memory, reasons
        )
        
    return reasons
