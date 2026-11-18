import { useEffect } from 'react';

/**
 * Ejecuta una carga asíncrona al montar el componente y cada vez que cambia `load`.
 *
 * La carga se agenda fuera del cuerpo síncrono del efecto para no encadenar
 * renders (regla react-hooks/set-state-in-effect) y se omite si el componente
 * se desmonta antes de que arranque. `load` debe estar memorizada con useCallback.
 */
export function useLoadEffect(load: () => Promise<unknown>) {
  useEffect(() => {
    let active = true;
    queueMicrotask(() => {
      if (active) void load();
    });
    return () => {
      active = false;
    };
  }, [load]);
}
