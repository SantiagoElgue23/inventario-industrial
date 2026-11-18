# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Proyecto

Inventario Industrial: catálogo, existencias, activos individuales, ubicaciones, proyectos y trabajos de una empresa de servicios industriales. Frontend React + TypeScript (Vite) en `src/`, API FastAPI + SQLAlchemy en `backend/app/`, PostgreSQL 16 vía Docker Compose. La base es independiente de InvenTree: nunca escribir en InvenTree. Toda la UI, los mensajes de error de la API y la documentación están en español.

## Principios de producto

Guían todas las decisiones de diseño y funcionalidad:

1. **Intuitivo**: alguien sin capacitación debe poder completar las tareas habituales.
2. **La información necesaria, con el menor ruido posible**: cada dato o control en pantalla tiene que justificar su lugar. Ante la duda, menos.
3. **Agradable a la vista**: interfaz consistente, prolija y cuidada en modo claro y oscuro.
4. **Cada vez más autónomo (objetivo a futuro)**: el sistema debe ir detectando y avisando por su cuenta (stock bajo, conteos vencidos, trabajos demorados, inconsistencias) en lugar de depender de que alguien lo revise. Al diseñar datos y procesos, guardar la información que haga posible esa automatización más adelante (quién, cuándo, cuánto).

Las reglas concretas de interfaz están en `.claude/rules/ux.md`.

## Comandos

Entorno Windows / PowerShell. El `.env` vive en la **raíz** (`backend/app/database.py` lo carga desde ahí; plantilla: `.env.example`). El venv está en `backend/.venv`.

```powershell
docker compose up -d db                      # PostgreSQL (contenedor inventario-postgres)
alembic upgrade head                         # desde la raíz (alembic.ini apunta a backend/migrations)
alembic revision --autogenerate -m "desc"    # nueva migración tras cambiar models.py
python -m backend.app.auth_bootstrap crear-master <usuario>   # cuentas master: solo por consola (ver --help)

cd backend; uvicorn app.main:app --reload    # API en :8000, docs en /docs
npm run dev                                  # frontend en :5173, proxy /api -> 127.0.0.1:8000
npm run build                                # tsc -b + vite build (sirve como chequeo de tipos)
npm run lint

pip install -r backend/requirements-dev.txt
pytest backend/tests                                      # usan SQLite en memoria, no tocan PostgreSQL
pytest backend/tests/test_auth_roles.py::nombre_del_test  # un test puntual
```

Importación inicial del catálogo (solo una vez; se niega a correr si ya hay `source_records`): `cd backend; python -m app.import_catalog --file import_data/catalogo.xlsx`.

Producción: servidor Linux con `docker-compose.prod.yml` (PostgreSQL + API + Caddy en el puerto 80); se publica con `./deploy/deploy.sh` en el servidor (ver `deploy/LEEME.md`). Ramas: trabajo en `feature/*` → `develop` → `main`; el servidor ejecuta `main`. No mezclar los comandos de desarrollo (`docker-compose.yml`) con los de producción.

Antes de aplicar migraciones sobre la base real, hacer respaldo con `pg_dump` (skill `/respaldo-db`). Los respaldos van en `backups/` (ignorada por git).

## Arquitectura

### Backend (`backend/app/`)
- `main.py` solo crea la app, el CORS y registra los routers. Cada recurso vive en `routers/<recurso>.py` con `APIRouter(prefix="/api")`; las utilidades compartidas (`get_*_or_404`, `validate_*`, `*_payload`, paginación) están en `common.py`.
- **Autenticación**: `main.py` incluye todos los routers de negocio con `dependencies=[Depends(current_user)]`, que valida la cookie `inv_session`, renueva el vencimiento y verifica el `Origin` en métodos que modifican (CSRF). Solo `/api/health` (en `system.public_router`) y `/api/auth/login` son públicos.
- **Autorización por endpoint** con dependencias de `auth.py`: `require_admin` (estructura: catálogo, ubicaciones), `require_archive` (archivar/restaurar), `require_master`, y `ensure_can_set_values(user, payload)` dentro de los endpoints que aceptan importes. Un endpoint nuevo sin dependencia de rol queda abierto a cualquier cuenta con sesión.
- **Roles**: columna `AppUser.role` (`master` / `admin` / `user`), independiente del nombre. El rol `master` **nunca** se otorga por API: los endpoints `/api/auth/users` solo aceptan `admin` / `user` y rechazan editar cuentas master; los master se gestionan con `auth_bootstrap.py`. `master` modifica importes, `admin` los ve, y a `user` el middleware `finalize_response` le quita de toda respuesta JSON las claves de `SENSITIVE_KEYS`. Si agregás un campo monetario nuevo a una respuesta, sumalo a `SENSITIVE_KEYS`.
- Los modelos de respuesta de Trabajos (`routers/works.py`) serializan cantidades como número JSON (`JsonNumber`); el resto de la API serializa `Decimal` como texto (p. ej. `"8000.00"`).
- **Auditoría**: movimientos, traslados, trabajos (creación y cierre), líneas despachadas y devoluciones guardan la cuenta en `*_by_id` (FK a `app_users`, `ON DELETE SET NULL`). Toda operación nueva que cambie stock o estado debe registrar `created_by_id=user.id` (`user: CurrentUser = Depends(current_user)`).
- **Nunca se borra**: los "DELETE" de catálogo/activos/proyectos/ubicaciones ponen `active = False`, y existe `POST .../{id}/restore`. Solo los borradores de Trabajo se eliminan físicamente.
- **Dos modos de seguimiento de producto** (`Product.tracking_mode`): `quantity` (stock por ubicación en `StockBalance`, cambios vía `StockMovement` / `StockTransfer`) e `individual` (cada unidad es un `Asset` con `asset_code` generado desde `asset_code_prefix` + `AssetCodeSequence`). Hay restricciones CHECK que lo imponen.
- **Trabajos** (`Work`): flujo `draft` → prepare → dispatch → returns → close. El stock se descuenta al despachar, no al preparar. Las líneas guardan snapshots de valor para costear. Hay PDF vía ReportLab.
- El stock importado de InvenTree es solo referencia histórica (`SourceRecord`); el stock real empieza con un "Conteo inicial".
- El código soporta PostgreSQL y SQLite (los tests); ojo con funciones específicas de dialecto (`main.py` importa `insert` de ambos).

### Frontend (`src/`)
- Navegación con React Router (`BrowserRouter` en `main.tsx`, rutas en `App.tsx`, direcciones en `types/navigation.ts`). Lo que se quiera poder compartir o recargar va en la URL (p. ej. `/proyectos?id=12`); la URL es la fuente de verdad, no un `useState`. En producción el servidor debe devolver `index.html` para cualquier ruta que no sea `/api`.
- Cargas iniciales con `useLoadEffect(load)` (`src/hooks/`), no `useEffect(() => { void load() })`. Para reiniciar estado al cambiar una selección, hacerlo en el manejador del evento o derivar el valor al renderizar, no en un efecto.
- `useAuth` vive en `auth/useAuth.ts`; `AuthProvider.tsx` solo exporta el componente.
- Todo acceso a la API pasa por `services/inventoryService.ts` (`fetch` a `/api` con `credentials: 'include'`). La URL debe ser del mismo origen para que funcione la cookie HttpOnly; no apuntar a `http://localhost:8000` directamente.
- `auth/AuthProvider.tsx` maneja la sesión (`/api/auth/me`, ping periódico para mantenerla viva). La UI oculta acciones según rol, pero la autoridad real está en el backend.
- Estilos con Tailwind CSS 4 (plugin de Vite), íconos con `lucide-react`.

## Convenciones
- Todo cambio de esquema va con una migración Alembic en `backend/migrations/versions/`; no usar `create_all` contra la base real.
- Mensajes de `HTTPException` en español. Usar 404 para no encontrado, 409 para conflictos de estado o duplicados y 400 para validaciones de negocio.
- Los cambios nuevos se registran en `CHANGELOG.md`.
