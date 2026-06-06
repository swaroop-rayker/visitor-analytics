import secrets
import threading

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.schemas import BrowserSignals, TrackResponse
from app.services.fingerprint import generate_visitor_hash, parse_user_agent
from app.services.geoip import geoip_service
from app.services.security import client_ip, enforce_rate_limit
from app.services.tracking import record_visit

router = APIRouter(tags=["tracking"])
TRACK_WRITE_LOCK = threading.Lock()


def _record(request: Request, signals: BrowserSignals, db: Session) -> None:
    enforce_rate_limit(request, "track", settings.track_rate_limit_per_minute)
    user_agent = request.headers.get("user-agent", "")
    visitor_hash = generate_visitor_hash(
        secret=settings.fingerprint_secret,
        user_agent=user_agent,
        accept=request.headers.get("accept"),
        accept_language=request.headers.get("accept-language"),
        sec_ch_platform=request.headers.get("sec-ch-ua-platform"),
        signals=signals,
    )
    geo = geoip_service.lookup(client_ip(request))
    with TRACK_WRITE_LOCK:
        record_visit(
            db,
            visitor_hash=visitor_hash,
            agent=parse_user_agent(user_agent),
            signals=signals,
            geo=geo,
        )


@router.get("/go", response_class=HTMLResponse, include_in_schema=False)
def tracking_page() -> HTMLResponse:
    nonce = secrets.token_urlsafe(18)
    fallback_url = "/api/v1/track/fallback"
    document = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <meta name="robots" content="noindex,nofollow">
  <meta http-equiv="refresh" content="2;url={fallback_url}">
  <title>Redirecting...</title>
  <style nonce="{nonce}">
    html{{color-scheme:dark}}body{{margin:0;display:grid;min-height:100vh;place-items:center;
    background:#09090b;color:#a1a1aa;font:14px system-ui}}.dot{{color:#fafafa}}
  </style>
</head>
<body><p><span class="dot">Redirecting</span> securely...</p>
<script nonce="{nonce}">
const data={{
  timezone:Intl.DateTimeFormat().resolvedOptions().timeZone||null,
  language:navigator.language||null,
  platform:navigator.userAgentData?.platform||navigator.platform||null,
  screen_resolution:`${{screen.width}}x${{screen.height}}`
}};
fetch("/api/v1/track",{{method:"POST",headers:{{"Content-Type":"application/json"}},
  credentials:"same-origin",body:JSON.stringify(data)}})
  .then(r=>r.ok?r.json():Promise.reject()).then(d=>location.replace(d.redirect_url))
  .catch(()=>location.replace("{fallback_url}"));
</script></body></html>"""
    return HTMLResponse(
        document,
        headers={
            "Cache-Control": "no-store",
            "Content-Security-Policy": (
                f"default-src 'none'; script-src 'nonce-{nonce}'; style-src 'nonce-{nonce}'; "
                "connect-src 'self'; base-uri 'none'; frame-ancestors 'none'"
            ),
            "Referrer-Policy": "no-referrer",
        },
    )


@router.post("/api/v1/track", response_model=TrackResponse)
def track(
    payload: BrowserSignals,
    request: Request,
    db: Session = Depends(get_db),
) -> TrackResponse:
    _record(request, payload, db)
    return TrackResponse(redirect_url=settings.redirect_target_url)


@router.get("/api/v1/track/fallback", include_in_schema=False)
def fallback_track(request: Request, db: Session = Depends(get_db)) -> RedirectResponse:
    try:
        _record(request, BrowserSignals(), db)
    except Exception:
        db.rollback()
    return RedirectResponse(
        url=settings.redirect_target_url,
        status_code=303,
        headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"},
    )
