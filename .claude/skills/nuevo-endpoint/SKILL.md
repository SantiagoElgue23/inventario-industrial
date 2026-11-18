---
name: nuevo-endpoint
description: Agrega un endpoint REST nuevo a la API de de punta a punta (schema, ruta, permisos, test y servicio del frontend).
---

# Nuevo endpoint

El usuario describe qué debe hacer el endpoint. Seguir estos pasos:

1. **Diseño de la URL**: sustantivo en plural, anidado si pertenece a otro recurso (`/api/projects/{id}/works`). Verbo HTTP según la acción (GET lee, POST crea, PUT/PATCH edita, DELETE archiva). Proponer la ruta al usuario antes de escribir código si hay dudas.
2. **Schemas**: agregar los modelos Pydantic de entrada y salida en `backend/app/schemas.py`.
3. **Ruta**: implementarla en `backend/app/routers/<recurso>.py` (si es un recurso nuevo, crear el router y registrarlo en `main.py` con `dependencies=[Depends(current_user)]`). Declarar `response_model`, `tags` y `status_code`, siguiendo `.claude/rules/backend.md`.
4. **Permisos**: definir qué roles pueden usarla y declararlo con `require_admin`, `require_archive` o `require_master` de `backend/app/auth.py`. Si acepta importes, llamar a `ensure_can_set_values`. Si devuelve valores económicos, agregar los campos a `SENSITIVE_KEYS`.
5. **Test**: agregar al menos un test feliz y uno de permiso o error en `backend/tests/`, reutilizando el fixture `env` de `test_auth_roles.py`. Correr `pytest backend/tests`.
6. **Frontend**: agregar la función en `src/services/inventoryService.ts` y los tipos en `src/types/inventory.ts`. Correr `npm run build`.
7. Resumir al usuario la ruta, el método, los permisos por rol y cómo probarla desde `/docs`.
