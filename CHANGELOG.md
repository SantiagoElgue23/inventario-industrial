# Changelog

Cambios relevantes de Inventario Industrial.

## [Sin publicar]
### Corregido
- Los traslados entre ubicaciones fallaban con error 500 desde la versión 0.5.0 (no se recibía la cuenta para la auditoría). Se agregó un test que cubre el traslado.

## [0.5.1] — 2026-11-18
### Agregado
- Ficha de artículo: botón "Ver ubicaciones" con las existencias (o unidades) en cada ubicación.

## [0.5.0] — 2026-11-17
### Agregado
- Auditoría: cada movimiento, traslado, despacho, devolución y cierre de trabajo registra la cuenta que lo hizo (migración `a3c7e1d9b5f2`) y se muestra en el historial.
- Direcciones por pantalla con React Router (`/inventario`, `/proyectos?id=…`, etc.): se puede recargar, usar "atrás" y compartir links.
- Principios de producto y reglas de interfaz para el desarrollo (`CLAUDE.md`, `.claude/rules/ux.md`).
- Despliegue en servidor Linux con Docker (`docker-compose.prod.yml`, Caddy, `deploy/deploy.sh`) y respaldo diario automático.
- Integración continua en GitHub Actions: tests, lint y build en cada push.

### Corregido
- Los 16 errores de lint existentes (estado actualizado dentro de efectos, `Date.now()` durante el render, exportaciones mixtas).
- El formulario de artículo ya no valida ni envía características de un tipo anterior cuando se quita el tipo.

## [0.4.0] — 2026-11-17
### Cambiado
- Cuentas personales con columna `role` (`master`, `admin`, `user`). El rol `master` solo se otorga por consola; desde la web un master crea y administra cuentas `admin` y `user`.
- El backend se divide en routers por recurso (`backend/app/routers/`). Las URLs no cambian.
- Los permisos se declaran en cada endpoint con dependencias en lugar de expresiones regulares sobre la URL.
- Paginación opcional (`limit` / `offset`) en los listados de productos, activos y movimientos.
- Documentación unificada en `README.md`.
### Eliminado
- Archivos de la plantilla de Vite sin uso (`App.css`, `hero.png`, `react.svg`, `vite.svg`, `favicon.svg`, `icons.svg`).

## V5 — Autenticación y normalización (2026-11-13)
- Login obligatorio con las cuentas `master`, `admin` y `user`; sesión en cookie HttpOnly con 30 minutos de inactividad.
- Los valores económicos solo los modifica `master`; `user` no los recibe de la API.
- Estados heredados `under_repair` y `out_of_service` normalizados a `unverified`.

## V4 — Trabajos dentro de proyectos (2026-11-10 a 2026-11-13)
- Trabajos con preparación, salida, devoluciones parciales y cierre con conciliación (consumido o perdido).
- PDF de salida y de devolución final; valoración de materiales consumidos.
- V4.1: una sola columna de existencias, buscador completo en la preparación. V4.2: monedas PYG/USD, modo oscuro, favicon.

## V3 — Búsqueda, proyectos y asociaciones (2026-11-10)
- Búsqueda por varios términos sin distinguir mayúsculas ni tildes; filtro por tipo de componente.
- Asignación de activos y artículos a proyectos por lotes, de forma transaccional.

## V2 — Traslados y limpieza visual (2026-11-06 a 2026-11-10)
- Traslado de cantidades entre ubicaciones.
- Interfaz simplificada y estanterías desplegables en Ubicaciones.

## V1 — API propia y PostgreSQL (2026-11-05 a 2026-11-06)
- Backend FastAPI + PostgreSQL independiente de InvenTree; importación del catálogo auditado desde Excel.
- Conteo inicial, ingresos, extracciones y ajustes de existencias por ubicación.
