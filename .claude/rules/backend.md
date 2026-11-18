---
paths:
  - "backend/**/*.py"
---

# Reglas del backend (FastAPI)

- Cada endpoint nuevo declara `response_model`, `tags` y, si crea un recurso, `status_code=201`.
- Escribir `HTTPException(status_code=..., detail="...")` siempre con argumentos nombrados y el `detail` en español.
- Códigos: 404 si el recurso no existe, 409 para duplicados o estados que no permiten la operación, 400 para validaciones de negocio. Los 422 los genera Pydantic.
- No borrar registros de catálogo, activos, proyectos ni ubicaciones: archivar con `active = False` y ofrecer `POST .../{id}/restore`.
- Cada cambio en `models.py` va acompañado de una migración Alembic (skill `/nueva-migracion`).
- Cada endpoint va en el router de su recurso (`backend/app/routers/`). Las utilidades que usa más de un router van a `common.py`.
- Permisos: decidir para cada endpoint nuevo si necesita `dependencies=[Depends(require_admin)]`, `require_archive` o `require_master`. Si acepta importes, llamar a `ensure_can_set_values(user, payload)`. Agregar un test de permisos en `backend/tests/test_auth_roles.py`.
- Nunca permitir asignar el rol `master` desde la API.
- Si una respuesta incluye un campo monetario nuevo, agregar su nombre a `SENSITIVE_KEYS` en `auth.py`, para que no se envíe a la cuenta `user`.
- Los listados que pueden crecer sin límite usan `page: Page = Depends(pagination)` y `fetch_page()` de `common.py`.
- El código tiene que funcionar en PostgreSQL y en SQLite (los tests usan SQLite en memoria).
