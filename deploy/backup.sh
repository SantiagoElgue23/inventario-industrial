#!/usr/bin/env bash
# Respaldo de la base de producción en backups/. Conserva los últimos 30 días.
set -euo pipefail
cd "$(dirname "$0")/.."

compose="docker compose -f docker-compose.prod.yml"
mkdir -p backups
file="backups/inventario_$(date +%Y%m%d_%H%M).dump"

if ! $compose exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > "$file" || [ ! -s "$file" ]; then
  rm -f "$file"
  echo "ERROR: no se pudo generar el respaldo" >&2
  exit 1
fi

find backups -name 'inventario_*.dump' -mtime +30 -delete
echo "Respaldo: $file ($(du -h "$file" | cut -f1))"
