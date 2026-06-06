#!/usr/bin/env bash
set -euo pipefail

backup="${1:-}"
if [[ -z "$backup" || ! -f "$backup" ]]; then
  echo "Usage: $0 /path/to/analytics-TIMESTAMP.db.gz" >&2
  exit 1
fi
read -r -p "This replaces the current database. Type RESTORE to continue: " answer
[[ "$answer" == "RESTORE" ]] || exit 1

docker compose stop backend backup
gunzip -c "$backup" | docker compose run --rm --no-deps -T backend \
  sh -c 'cat > /data/analytics.db'
docker compose up -d backend backup

