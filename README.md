# Inventario Industrial

Aplicación web para administrar el catálogo, las existencias, los activos individuales, las ubicaciones, los proyectos y los trabajos de una empresa de servicios industriales.

- **Frontend:** React 19 + TypeScript + Vite + Tailwind CSS
- **Backend:** FastAPI + SQLAlchemy 2 + Alembic
- **Base de datos:** PostgreSQL 16 (Docker Compose)

El historial de cambios está en [CHANGELOG.md](CHANGELOG.md).

## Estructura

```
backend/
  app/
    main.py            # crea la app y registra los routers
    auth.py            # sesiones, roles y endpoints /api/auth
    auth_bootstrap.py  # administración de cuentas master por consola
    common.py          # validaciones, serialización y paginación compartidas
    models.py          # modelos SQLAlchemy
    schemas.py         # schemas Pydantic
    routers/           # un archivo por recurso (products, assets, stock, works…)
    import_catalog.py  # importación inicial desde Excel
  migrations/          # migraciones Alembic
  tests/
src/                   # frontend React
deploy/                # Dockerfiles, Caddy y scripts del servidor
```

## Requisitos

- Node.js y npm
- Python 3.11 o superior
- Docker Desktop con Docker Compose (o PostgreSQL 16 local)

## Instalación (Windows, PowerShell)

Todos los comandos se ejecutan desde la carpeta raíz `inventario-industrial`, salvo que se indique otra.

### 1. Configuración y base de datos

```powershell
Copy-Item .env.example .env      # completar POSTGRES_PASSWORD y DATABASE_URL
docker compose up -d db
docker compose ps                # inventario-postgres debe figurar como healthy
```

### 2. Backend

```powershell
cd backend
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements-dev.txt   # incluye pytest; en producción: requirements.txt
cd ..
```

Si PowerShell bloquea la activación del entorno virtual: `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`.

### 3. Esquema y cuenta inicial

```powershell
alembic upgrade head
python -m backend.app.auth_bootstrap crear-master <usuario>
```

### 4. Importar el catálogo (solo la primera vez)

```powershell
cd backend
python -m app.import_catalog --file import_data/catalogo.xlsx
cd ..
```

El importador se detiene si ya hay registros importados, para no duplicar el catálogo.

### 5. Ejecutar

```powershell
# Terminal 1 — API en http://127.0.0.1:8000 (documentación en /docs)
cd backend; uvicorn app.main:app --reload

# Terminal 2 — interfaz en http://localhost:5173
npm install
npm run dev
```

Vite reenvía `/api` a la API. El frontend siempre debe llamar a `/api` en el mismo origen, porque la sesión usa una cookie HttpOnly.

## Cuentas y roles

Cada persona tiene su propia cuenta con uno de estos roles:

| Rol | Puede |
|---|---|
| `master` | Todo, incluidos los valores económicos y la administración de cuentas `admin` / `user` |
| `admin` | Ver valores, administrar categorías, tipos y ubicaciones, archivar y restaurar |
| `user` | Operar inventario, proyectos y trabajos; no recibe importes desde la API |

**El rol master nunca se otorga desde la web.** Solo quien tiene acceso al servidor puede administrarlo:

```powershell
python -m backend.app.auth_bootstrap listar
python -m backend.app.auth_bootstrap crear-master <usuario>
python -m backend.app.auth_bootstrap promover <usuario>
python -m backend.app.auth_bootstrap degradar <usuario> --rol admin   # no permite dejar el sistema sin master
python -m backend.app.auth_bootstrap restablecer <usuario>
```

Desde **Administración**, un master crea cuentas `admin` / `user`, cambia su rol, las desactiva o restablece su contraseña. Cualquier cuenta puede cambiar su propia contraseña. La sesión vence tras 30 minutos sin actividad.

## Desarrollo

```powershell
pytest backend/tests                         # pruebas (SQLite en memoria; no tocan PostgreSQL)
npm run build                                # chequeo de tipos + build
npm run lint
alembic revision --autogenerate -m "desc"    # tras cambiar backend/app/models.py
```

### Paginación

`GET /api/products`, `GET /api/assets` y `GET /api/products/{id}/movements` aceptan `limit` (1–500) y `offset`. Sin `limit` devuelven todos los registros. Con `limit`, el total sin paginar llega en la cabecera `X-Total-Count`.

## Respaldos

Antes de migrar o importar, generá un respaldo con `pg_dump`. Los respaldos van en `backups/`, que está excluida de git:

```powershell
docker compose exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc -f /tmp/inventario.dump'
docker compose cp db:/tmp/inventario.dump backups/inventario_$(Get-Date -Format yyyyMMdd_HHmm).dump
```

## Producción

Se despliega con Docker en un servidor Linux (`docker-compose.prod.yml`: PostgreSQL, API y Caddy en el puerto 80). Ramas: el trabajo se integra en `develop` y el servidor ejecuta `main`. Instalación y publicación de versiones: [deploy/LEEME.md](deploy/LEEME.md).

## Seguridad

Pensado para una red interna. Antes de exponerlo fuera de ella: servir con HTTPS y `COOKIE_SECURE=true`, agregar límite de solicitudes en el proxy inverso y programar respaldos automáticos.
