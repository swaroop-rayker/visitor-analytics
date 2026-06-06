import hashlib
import hmac
import json
import re
from dataclasses import dataclass

from user_agents import parse

from app.schemas import BrowserSignals


@dataclass(frozen=True)
class ParsedAgent:
    browser: str
    os: str
    device_type: str


def parse_user_agent(user_agent: str) -> ParsedAgent:
    parsed = parse(user_agent or "")
    if parsed.is_mobile:
        device = "Mobile"
    elif parsed.is_tablet:
        device = "Tablet"
    elif parsed.is_pc:
        device = "Desktop"
    elif parsed.is_bot:
        device = "Bot"
    else:
        device = "Other"
    browser = parsed.browser.family or "Unknown"
    if parsed.browser.version:
        browser = f"{browser} {parsed.browser.version[0]}"
    operating_system = parsed.os.family or "Unknown"
    return ParsedAgent(browser=browser[:80], os=operating_system[:80], device_type=device)


def _normalize(value: str | None, max_length: int = 256) -> str:
    if not value:
        return ""
    return re.sub(r"\s+", " ", value.strip().lower())[:max_length]


def generate_visitor_hash(
    *,
    secret: str,
    user_agent: str,
    accept: str | None,
    accept_language: str | None,
    sec_ch_platform: str | None,
    signals: BrowserSignals,
) -> str:
    """Create a stable anonymous HMAC without IP addresses or account data."""
    values = {
        "user_agent": _normalize(user_agent, 512),
        "accept": _normalize(accept),
        "accept_language": _normalize(accept_language),
        "platform": _normalize(signals.platform or sec_ch_platform),
        "timezone": _normalize(signals.timezone),
        "language": _normalize(signals.language),
        "screen_resolution": _normalize(signals.screen_resolution),
    }
    canonical = json.dumps(values, sort_keys=True, separators=(",", ":")).encode()
    return hmac.new(secret.encode(), canonical, hashlib.sha256).hexdigest()
