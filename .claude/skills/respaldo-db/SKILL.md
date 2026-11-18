---
name: respaldo-db
description: Genera un respaldo de la base PostgreSQL de con pg_dump dentro del contenedor Docker. Usar antes de migraciones, importaciones o cambios de datos.
---

# Respaldo de la base

1. Verificar que el contenedor esté corriendo y sano: `docker compose ps` (debe figurar `inventario-postgres` como `healthy`).
2. Crear la carpeta `backups/` en la raíz si no existe (está ignorada por git).
3. Generar el respaldo en formato custom con fecha y hora en el nombre, por ejemplo:
   ```powershell
   $stamp = Get-Date -Format "yyyyMMdd_HHmm"
   docker compose exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc -f /tmp/inventario.dump'
   docker compose cp db:/tmp/inventario.dump "backups/inventario_$stamp.dump"
   docker compose exec -T db rm /tmp/inventario.dump
   ```
   El contenedor ya conoce `POSTGRES_USER` y `POSTGRES_DB` desde `.env`.
4. Verificar que el archivo local existe y pesa más de cero bytes. Opcional: copiarlo de nuevo al contenedor y correr `pg_restore --list` para confirmar que es legible.
5. Informar la ruta completa del respaldo. Nunca borrar respaldos anteriores sin que el usuario lo pida.

Para restaurar (solo si el usuario lo pide explícitamente, porque sobrescribe datos): `pg_restore --clean --if-exists -U inventario -d inventory <archivo>` dentro del contenedor.
