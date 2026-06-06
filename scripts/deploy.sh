#!/usr/bin/env bash
set -euo pipefail

if [[ ! -f .env ]]; then
  echo "Missing .env. Copy .env.example and configure it first." >&2
  exit 1
fi

docker compose build --pull
docker compose up -d
docker compose ps

