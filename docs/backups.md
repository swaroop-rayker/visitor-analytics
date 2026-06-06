# Backup and retention

The backup container wakes at `BACKUP_HOUR_UTC`, uses SQLite's online backup
API to obtain a transactionally consistent snapshot, compresses it with gzip,
and retains the newest `BACKUP_RETENTION_COUNT` files (30 by default).

Run an immediate backup:

```bash
bash scripts/backup-now.sh
```

List backups:

```bash
docker compose exec backup ls -lh /backups
```

Restore during a maintenance window:

```bash
bash scripts/restore-backup.sh /secure/path/analytics-20260101T020000Z.db.gz
```

The Docker volume is not an off-machine backup. Copy encrypted backup files to
a separate trusted location if the data must survive VM loss. Raw visit rows
older than `RAW_RETENTION_DAYS` are removed daily; aggregates are retained
indefinitely.
