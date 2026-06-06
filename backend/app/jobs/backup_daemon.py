import gzip
import shutil
import sqlite3
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.config import settings


def database_path() -> Path:
    if not settings.database_url.startswith("sqlite:///"):
        raise RuntimeError("Automated backup supports SQLite only")
    return Path(settings.database_url.removeprefix("sqlite:///"))


def create_backup(backup_dir: Path = Path("/backups")) -> Path:
    source = database_path()
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    temporary = backup_dir / f".analytics-{timestamp}.db"
    destination = backup_dir / f"analytics-{timestamp}.db.gz"
    with sqlite3.connect(source) as source_db, sqlite3.connect(temporary) as target_db:
        source_db.backup(target_db)
    with temporary.open("rb") as raw, gzip.open(destination, "wb", compresslevel=6) as compressed:
        shutil.copyfileobj(raw, compressed)
    temporary.unlink(missing_ok=True)
    backups = sorted(backup_dir.glob("analytics-*.db.gz"), key=lambda item: item.stat().st_mtime, reverse=True)
    for old in backups[settings.backup_retention_count:]:
        old.unlink()
    return destination


def seconds_until_backup() -> float:
    now = datetime.now(timezone.utc)
    target = now.replace(hour=settings.backup_hour_utc, minute=0, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return (target - now).total_seconds()


def main() -> None:
    while True:
        time.sleep(seconds_until_backup())
        try:
            create_backup()
        except Exception as exc:
            print(f"backup failed: {exc}", flush=True)
            time.sleep(300)


if __name__ == "__main__":
    main()

