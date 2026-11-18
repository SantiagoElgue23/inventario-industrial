---
name: nueva-migracion
description: Crea y aplica una migración Alembic después de cambiar backend/app/models.py. Usar cuando se agregan, quitan o modifican tablas, columnas o restricciones.
---

# Nueva migración Alembic

1. Revisar el diff de `backend/app/models.py` (`git diff backend/app/models.py`) y resumir qué cambia en el esquema.
2. Si hay datos reales en juego (renombrar columnas, cambiar tipos, nuevas columnas NOT NULL, cambios en CHECK), ejecutar primero el skill `/respaldo-db`.
3. Desde la raíz del proyecto, con el venv activo:
   ```powershell
   alembic revision --autogenerate -m "descripcion_corta_en_espanol"
   ```
4. Abrir el archivo generado en `backend/migrations/versions/` y revisarlo a mano:
   - Autogenerate no detecta renombres (los ve como borrar + crear): reescribirlos con `op.alter_column(..., new_column_name=...)`.
   - Columnas NOT NULL sobre tablas con datos necesitan `server_default` o un paso de relleno de datos.
   - Revisar que `downgrade()` revierta correctamente.
5. Aplicar: `alembic upgrade head`. Confirmar con `alembic current`.
6. Correr `pytest backend/tests` para comprobar que los modelos siguen siendo coherentes.
7. Si cambió algún schema de la API, actualizar `src/types/inventory.ts`.
