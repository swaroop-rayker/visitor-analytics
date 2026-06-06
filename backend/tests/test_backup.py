import gzip
import sqlite3

from app.jobs import backup_daemon


def test_backup_is_compressed_and_restorable(tmp_path, monkeypatch):
    database = tmp_path / "analytics.db"
    with sqlite3.connect(database) as db:
        db.execute("CREATE TABLE sample (value TEXT)")
        db.execute("INSERT INTO sample VALUES ('ok')")
    monkeypatch.setattr(backup_daemon, "database_path", lambda: database)
    destination = backup_daemon.create_backup(tmp_path / "backups")
    restored = tmp_path / "restored.db"
    with gzip.open(destination, "rb") as source, restored.open("wb") as target:
        target.write(source.read())
    with sqlite3.connect(restored) as db:
        assert db.execute("SELECT value FROM sample").fetchone()[0] == "ok"

