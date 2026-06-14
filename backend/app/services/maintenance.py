import asyncio
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import delete, text

from app.config import settings
from app.db import SessionLocal
from app.models import CrawlerVisitLog, VisitLog

logger = logging.getLogger("visitor_analytics.tracker")


def cleanup_expired_visits() -> int:
    cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=settings.raw_retention_days)
    with SessionLocal() as db:
        result = db.execute(delete(VisitLog).where(VisitLog.timestamp < cutoff))
        crawler_result = db.execute(delete(CrawlerVisitLog).where(CrawlerVisitLog.timestamp < cutoff))
        db.commit()
        
        # SQLite optimization and vacuuming
        try:
            db.execute(text("PRAGMA incremental_vacuum(100)"))
            db.execute(text("PRAGMA optimize"))
            db.commit()
            logger.info("[MAINTENANCE] SQLite incremental vacuum and optimization complete.")
        except Exception as e:
            logger.warning("[MAINTENANCE] SQLite optimization failed: %s", e)
            
        return (result.rowcount or 0) + (crawler_result.rowcount or 0)


async def retention_loop() -> None:
    geoip_update_interval_days = 7
    
    # Initialize last_geoip_update to the oldest of the two database files' mtimes
    # so we don't auto-trigger a download on startup if the files on disk are already fresh.
    city_path = Path(settings.geoip_city_db)
    asn_path = Path(settings.geoip_asn_db)
    if city_path.is_file() and asn_path.is_file():
        try:
            mtime = min(city_path.stat().st_mtime, asn_path.stat().st_mtime)
            last_geoip_update = datetime.fromtimestamp(mtime)
            logger.info("[MAINTENANCE] GeoIP databases found on disk. Initialized last update timestamp to: %s", last_geoip_update)
        except Exception:
            last_geoip_update = datetime.min
    else:
        last_geoip_update = datetime.min
    
    while True:
        try:
            # 1. Daily raw event retention and SQLite optimization
            await asyncio.to_thread(cleanup_expired_visits)
            
            # 2. Weekly GeoIP database auto-update if license key is configured
            now = datetime.now()
            if (now - last_geoip_update).days >= geoip_update_interval_days:
                if getattr(settings, "maxmind_license_key", None):
                    from app.services.geoip_updater import download_and_update_geoip
                    updated = await asyncio.to_thread(download_and_update_geoip)
                    if updated:
                        last_geoip_update = now
                        logger.info("[MAINTENANCE] Automated weekly GeoIP update succeeded.")
                    else:
                        logger.warning("[MAINTENANCE] Automated weekly GeoIP update failed.")
        except Exception as e:
            logger.exception("[MAINTENANCE] Error in retention loop: %s", e)
            
        await asyncio.sleep(24 * 60 * 60)
