#!/usr/bin/env bash
set -euo pipefail
docker compose run --rm --no-deps backup python -c \
  'from app.jobs.backup_daemon import create_backup; print(create_backup())'

