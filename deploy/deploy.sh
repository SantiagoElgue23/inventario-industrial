#!/usr/bin/env bash
# Publica en el servidor la última versión de main: respaldo, código nuevo, reconstrucción.
set -euo pipefail
cd "$(dirname "$0")/.."

compose="docker compose -f docker-compose.prod.yml"

if [ "$(git branch --show-current)" != "main" ]; then
  echo "ERROR: el servidor debe estar en la rama main" >&2
  exit 1
fi

git fetch origin main
if [ "$(git rev-parse HEAD)" = "$(git rev-parse origin/main)" ] && [ "${1:-}" != "--forzar" ]; then
  echo "Ya está en la última versión ($(git log --oneline -1)). Usá --forzar para reconstruir igual."
  exit 0
fi

# Respaldo antes de tocar nada (si la base ya está corriendo).
if [ -n "$($compose ps --status running -q db)" ]; then
  ./deploy/backup.sh
fi

git merge --ff-only origin/main
echo "Versión: $(git log --oneline -1)"

# La API aplica las migraciones pendientes al arrancar.
$compose up -d --build
docker image prune -f > /dev/null
$compose ps
