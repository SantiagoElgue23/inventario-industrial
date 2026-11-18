---
paths:
  - "src/**/*.{ts,tsx,css}"
---

# Reglas de interfaz

Toda pantalla nueva o modificada tiene que cumplir los principios de producto de `CLAUDE.md`. En la práctica:

## Información necesaria, sin ruido
- Antes de agregar un dato, texto o botón, preguntarse qué decisión ayuda a tomar. Si no ayuda a ninguna, no va.
- Un solo título por pantalla. Sin subtítulos que repitan el título ni textos que expliquen lo obvio.
- Lo secundario va a la ficha o detalle (drawer), no a la tabla principal.
- Los números importantes (stock, pendientes, faltantes) se ven de un vistazo: alineados, con unidad y con color solo si indican un estado (sin stock, pendiente de conteo, vencido).
- Los estados vacíos dicen qué hacer a continuación ("Registrá el conteo inicial"), no solo "Sin datos".

## Intuitiva
- Cada acción usa el verbo del negocio ("Despachar", "Registrar devolución"), no términos técnicos.
- Las acciones destructivas o irreversibles piden confirmación y explican qué consecuencia tienen.
- Los formularios muestran el resultado antes de confirmar (por ejemplo, el saldo resultante).
- Los errores de la API se muestran cerca de donde ocurrieron y en lenguaje claro.
- Los valores por defecto deben ser los del caso más común.

## Agradable a la vista
- Mantener la paleta, los radios (`rounded-lg` / `rounded-xl`), los espaciados y la tipografía existentes; no introducir estilos nuevos por pantalla.
- Todo componente funciona en modo claro y oscuro (`dark:`).
- Usar los íconos de `lucide-react` para acompañar acciones, no para decorar.
- Las tablas son legibles en anchos de laptop (1366 px) y no desbordan en tablet.
