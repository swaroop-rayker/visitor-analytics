import os
import time
from datetime import datetime
from pathlib import Path

import psutil
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.dependencies import require_admin
from app.schemas import HealthResponse
from app.services.geoip import geoip_service

router = APIRouter(prefix="/system", tags=["system"], dependencies=[Depends(require_admin)])
STARTED_AT = time.monotonic()


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
        disk = psutil.disk_usage(disk_root).percent
    except OSError:
        size, disk = 0, 0.0
    degraded = database_status != "available" or not geoip_service.city_available
    return HealthResponse(
        status="degraded" if degraded else "healthy",
        database_status=database_status,
        database_size_bytes=size,
        disk_used_percent=disk,
        memory_used_percent=psutil.virtual_memory().percent,
        geoip_city_status="available" if geoip_service.city_available else "missing",
        geoip_asn_status="available" if geoip_service.asn_available else "missing",
        last_backup_time=_last_backup(),
        uptime_seconds=int(time.monotonic() - STARTED_AT),
        raw_retention_days=settings.raw_retention_days,
    )

