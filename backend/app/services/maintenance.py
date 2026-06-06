import asyncio
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete

from app.config import settings
from app.db import SessionLocal
from app.models import VisitLog


def cleanup_expired_visits() -> int:
    cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=settings.raw_retention_days)
    with SessionLocal() as db:
        result = db.execute(delete(VisitLog).where(VisitLog.timestamp < cutoff))
        db.commit()
        return result.rowcount or 0


async def retention_loop() -> None:
    while True:
        try:
            await asyncio.to_thread(cleanup_expired_visits)
        except Exception:
            pass
        await asyncio.sleep(24 * 60 * 60)
