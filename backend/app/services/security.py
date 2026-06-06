import hashlib
import hmac
import ipaddress
import threading
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import HTTPException, Request, status
from pwdlib import PasswordHash

from app.config import settings

password_hash = PasswordHash.recommended()


class SlidingWindowLimiter:
    def __init__(self) -> None:
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str, limit: int, window_seconds: int = 60) -> bool:
        now = time.monotonic()
        with self._lock:
            events = self._events[key]
            while events and events[0] <= now - window_seconds:
                events.popleft()
            if len(events) >= limit:
                return False
            events.append(now)
            if len(self._events) > 10_000:
                self._events = defaultdict(
                    deque,
                    {k: v for k, v in self._events.items() if v and v[-1] > now - window_seconds},
                )
            return True


rate_limiter = SlidingWindowLimiter()


def _trusted_proxy(value: str) -> bool:
    try:
        address = ipaddress.ip_address(value)
        return any(address in ipaddress.ip_network(item, strict=False) for item in settings.forwarded_allow_ip_list)
    except ValueError:
        return False


def client_ip(request: Request) -> str:
    peer = request.client.host if request.client else "127.0.0.1"
    if _trusted_proxy(peer):
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            candidate = forwarded.split(",", 1)[0].strip()
            try:
                ipaddress.ip_address(candidate)
                return candidate
            except ValueError:
                pass
    return peer


def transient_rate_key(ip: str, scope: str) -> str:
    digest = hmac.new(settings.fingerprint_secret.encode(), ip.encode(), hashlib.sha256).hexdigest()
    return f"{scope}:{digest}"


def enforce_rate_limit(request: Request, scope: str, limit: int) -> None:
    key = transient_rate_key(client_ip(request), scope)
    if not rate_limiter.allow(key, limit):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Rate limit exceeded")


def verify_admin_password(password: str) -> bool:
    if settings.admin_password_hash:
        try:
            return password_hash.verify(password, settings.admin_password_hash)
        except Exception:
            return False
    return hmac.compare_digest(password, settings.admin_password)


def create_access_token(subject: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_minutes),
        "aud": "visitor-analytics-admin",
        "iss": "visitor-analytics",
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def decode_access_token(token: str) -> str:
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=["HS256"],
            audience="visitor-analytics-admin",
            issuer="visitor-analytics",
        )
        return str(payload["sub"])
    except (jwt.PyJWTError, KeyError) as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired session") from exc
