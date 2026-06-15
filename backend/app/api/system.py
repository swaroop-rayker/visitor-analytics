import os
import time
from datetime import datetime, timezone
from pathlib import Path

import psutil
from fastapi import APIRouter, Depends, BackgroundTasks, Request
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.dependencies import require_admin
from app.schemas import HealthResponse, UpdateRedirectRequest, ToggleGeoIPRequest, ToggleLatencyRequest
from app.services.geoip import geoip_service
from app.models import AuditLog

router = APIRouter(prefix="/system", tags=["system"], dependencies=[Depends(require_admin)])
STARTED_AT = time.monotonic()


def audit(db: Session, action: str, actor: str, outcome: str, details: dict | None = None) -> None:
    try:
        db.add(
            AuditLog(
                timestamp=datetime.now(timezone.utc).replace(tzinfo=None),
                action=action,
                actor=actor[:80],
                outcome=outcome,
                details=details,
            )
        )
        db.commit()
    except Exception:
        db.rollback()


def _database_path() -> Path | None:
    if settings.database_url.startswith("sqlite:///"):
        return Path(settings.database_url.removeprefix("sqlite:///"))
    return None


def _last_backup() -> datetime | None:
    backup_dir = Path(os.getenv("BACKUP_DIR", "/backups"))
    try:
        files = list(backup_dir.glob("analytics-*.db.gz"))
        if not files:
            return None
        return datetime.fromtimestamp(max(file.stat().st_mtime for file in files))
    except OSError:
        return None


@router.get("/health", response_model=HealthResponse)
def health(db: Session = Depends(get_db)) -> HealthResponse:
    database_status = "available"
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        database_status = "unavailable"
    path = _database_path()
    try:
        size = path.stat().st_size if path and path.exists() else 0
        disk_root = str(path.parent if path else Path.cwd())
        du = psutil.disk_usage(disk_root)
        disk_percent = du.percent
        disk_used_bytes = du.used
        disk_total_bytes = du.total
    except OSError:
        size, disk_percent = 0, 0.0
        disk_used_bytes, disk_total_bytes = 0, 0
        
    mem = psutil.virtual_memory()
    memory_percent = mem.percent
    memory_used_bytes = mem.used
    memory_total_bytes = mem.total
        
    from app.services import geoip_updater
    
    city_db_path = Path(settings.geoip_city_db)
    asn_db_path = Path(settings.geoip_asn_db)
    
    def _db_status(db_path: Path, service_available: bool) -> str:
        if getattr(settings, "disable_maxmind_db", False):
            return "disabled"
        if geoip_updater.GEOIP_UPDATE_IN_PROGRESS:
            return "updating"
        if not service_available or not db_path.is_file():
            return "missing"
        try:
            mtime = db_path.stat().st_mtime
            age_days = (datetime.now() - datetime.fromtimestamp(mtime)).days
            if age_days < 7:
                return "up_to_date"
            return "update_available"
        except OSError:
            return "missing"

    city_status = _db_status(city_db_path, geoip_service.city_available)
    asn_status = _db_status(asn_db_path, geoip_service.asn_available)
    
    degraded = database_status != "available" or city_status == "missing"
    
    return HealthResponse(
        status="degraded" if degraded else "healthy",
        database_status=database_status,
        database_size_bytes=size,
        disk_used_percent=disk_percent,
        memory_used_percent=memory_percent,
        memory_used_bytes=memory_used_bytes,
        memory_total_bytes=memory_total_bytes,
        disk_used_bytes=disk_used_bytes,
        disk_total_bytes=disk_total_bytes,
        geoip_city_status=city_status,
        geoip_asn_status=asn_status,
        disable_maxmind_db=getattr(settings, "disable_maxmind_db", False),
        last_backup_time=_last_backup(),
        uptime_seconds=int(time.monotonic() - STARTED_AT),
        raw_retention_days=settings.raw_retention_days,
        redirect_target_url=settings.redirect_target_url,
        geoip_update_in_progress=geoip_updater.GEOIP_UPDATE_IN_PROGRESS,
        geoip_last_error=geoip_updater.LAST_GEOIP_UPDATE_ERROR,
        disable_latency_triangulation=settings.disable_latency_triangulation,
    )


@router.post("/config/redirect")
def update_redirect(
    payload: UpdateRedirectRequest,
    admin: str = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    new_url = payload.redirect_target_url
    
    # 1. Update the .env file
    from app.services.config_updater import update_env_file
    env_updated = update_env_file("REDIRECT_TARGET_URL", new_url)
    
    # 2. Update in-memory settings
    settings.redirect_target_url = new_url
    
    # 3. Clear settings cache
    from app.config import get_settings
    get_settings.cache_clear()
    
    # 4. Audit this configuration change
    audit(db, "update_redirect_url", admin, "success", {"redirect_url": new_url, "env_updated": env_updated})
        
    return {
        "success": True,
        "redirect_target_url": new_url,
        "env_updated": env_updated,
    }


@router.post("/geoip/update")
def trigger_geoip_update(
    background_tasks: BackgroundTasks,
    admin: str = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    has_key = bool(getattr(settings, "maxmind_license_key", None))
    
    # Check if already up-to-date
    city_db_path = Path(settings.geoip_city_db)
    asn_db_path = Path(settings.geoip_asn_db)
    
    def _is_up_to_date(path: Path) -> bool:
        if not path.is_file():
            return False
        try:
            mtime = path.stat().st_mtime
            return (datetime.now() - datetime.fromtimestamp(mtime)).days < 7
        except OSError:
            return False

    if _is_up_to_date(city_db_path) and _is_up_to_date(asn_db_path):
        return {
            "success": True,
            "detail": "Databases are already up to date.",
            "has_license_key": has_key,
            "initiated": False
        }
        
    def run_update_sync():
        from app.services.geoip_updater import download_and_update_geoip
        success = download_and_update_geoip()
        from app.db import SessionLocal
        with SessionLocal() as async_db:
            audit(async_db, "geoip_update", admin, "success" if success else "failed")

    background_tasks.add_task(run_update_sync)
    
    return {
        "success": True,
        "detail": "GeoIP update initiated in background" if has_key else "Update initiated, but MAXMIND_LICENSE_KEY is not configured",
        "has_license_key": has_key,
        "initiated": True
    }


@router.post("/geoip/toggle")
def toggle_geoip(
    payload: ToggleGeoIPRequest,
    admin: str = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    disabled = payload.disabled
    
    # 1. Update the .env file (write true/false string)
    from app.services.config_updater import update_env_file
    val_str = "true" if disabled else "false"
    env_updated = update_env_file("DISABLE_MAXMIND_DB", val_str)
    
    # 2. Update in-memory settings
    settings.disable_maxmind_db = disabled
    
    # 3. Clear settings cache
    from app.config import get_settings
    get_settings.cache_clear()
    
    # 4. Audit this configuration change
    audit(db, "toggle_geoip_databases", admin, "success", {"disabled": disabled, "env_updated": env_updated})
        
    return {
        "success": True,
        "disabled": disabled,
        "env_updated": env_updated,
    }


@router.post("/latency/toggle")
def toggle_latency(
    payload: ToggleLatencyRequest,
    admin: str = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    disabled = payload.disabled
    
    # 1. Update the .env file
    from app.services.config_updater import update_env_file
    val_str = "true" if disabled else "false"
    env_updated = update_env_file("DISABLE_LATENCY_TRIANGULATION", val_str)
    
    # 2. Update in-memory settings
    settings.disable_latency_triangulation = disabled
    
    # 3. Clear settings cache
    from app.config import get_settings
    get_settings.cache_clear()
    
    # 4. Audit this configuration change
    audit(db, "toggle_latency_triangulation", admin, "success", {"disabled": disabled, "env_updated": env_updated})
        
    return {
        "success": True,
        "disabled": disabled,
        "env_updated": env_updated,
    }


@router.get("/debug_visits")
def debug_visits(db: Session = Depends(get_db)):
    from app.models import VisitLog
    from sqlalchemy import select
    visits = db.scalars(select(VisitLog).order_by(VisitLog.timestamp.desc()).limit(5)).all()
    results = []
    for v in visits:
        results.append({
            "id": v.id,
            "timestamp": v.timestamp.isoformat() if v.timestamp else None,
            "city": v.city,
            "state": v.state,
            "country": v.country,
            "location_source": v.location_source,
            "location_source_detail": v.location_source_detail,
            "confidence_score": v.confidence_score,
            "city_confidence_score": v.city_confidence_score,
            "state_confidence_score": v.state_confidence_score,
            "country_confidence_score": v.country_confidence_score,
            "timezone": v.timezone,
            "asn": v.asn,
            "isp": v.isp,
            "network_type": v.network_type,
        })
    return results


@router.get("/test_geoip")
def test_geoip(request: Request, ip: str | None = None):
    import httpx
    from app.services.security import client_ip
    target_ip = (ip or client_ip(request)).strip()

    results = {"target_ip": target_ip}

    # 1. Test ipwho.is
    try:
        url = f"http://ipwho.is/{target_ip}"
        resp = httpx.get(url, timeout=3.0)
        results["ipwhois"] = {
            "status_code": resp.status_code,
            "data": resp.json() if resp.status_code == 200 else resp.text
        }
    except Exception as e:
        results["ipwhois"] = {"error": str(e)}

    # 2. Test ip-api.com
    try:
        url = f"http://ip-api.com/json/{target_ip}"
        resp = httpx.get(url, timeout=3.0)
        results["ip-api"] = {
            "status_code": resp.status_code,
            "data": resp.json() if resp.status_code == 200 else resp.text
        }
    except Exception as e:
        results["ip-api"] = {"error": str(e)}

    return results


