---
paths:
  - "src/**/*.{ts,tsx}"
---

# Reglas del frontend (React + TypeScript)

- Toda llamada a la API pasa por `src/services/inventoryService.ts`; no usar `fetch` directo en componentes ni apuntar a `http://localhost:8000` (rompe la cookie de sesión).
- Los tipos del dominio viven en `src/types/inventory.ts` y reflejan los schemas de `backend/app/schemas.py`; si cambia uno, actualizar el otro.
- Estilos con clases de Tailwind; íconos de `lucide-react`. No agregar librerías de UI nuevas sin consultarlo.
- Ocultar en la interfaz las acciones que el rol no puede hacer (ver `AuthProvider`), sin depender de eso para la seguridad: la autoridad es el backend.
- Textos visibles en español.
- Antes de dar un cambio por terminado, correr `npm run build` (chequea tipos) y `npm run lint`.
