import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react';
import { AuthContext, type Account } from './useAuth';

const INACTIVITY_MS = 30 * 60 * 1000;

export function AuthProvider({ children }: { children: ReactNode }) {
  const [account, setAccount] = useState<Account | null>(null);
  const [loading, setLoading] = useState(true);
  // Se inicializa al comenzar a vigilar la sesión (no durante el render).
  const lastActivity = useRef(0);

  useEffect(() => {
    let mounted = true;
    fetch('/api/auth/me', { credentials: 'include' })
      .then(async r => {
        if (!r.ok) return null;
        return await r.json() as Account;
      })
      .then(a => { if (mounted) setAccount(a); })
      .catch(() => { if (mounted) setAccount(null); })
      .finally(() => { if (mounted) setLoading(false); });
    return () => { mounted = false; };
  }, []);

  useEffect(() => {
    const sessionLost = () => setAccount(null);
    window.addEventListener('inv-session-expired', sessionLost);
    return () => window.removeEventListener('inv-session-expired', sessionLost);
  }, []);

  useEffect(() => {
    if (!account) return;
    lastActivity.current = Date.now();
    let lastPing = Date.now();
    const activity = () => { lastActivity.current = Date.now(); };
    const events = ['pointerdown', 'keydown', 'wheel', 'touchstart'] as const;
    events.forEach(e => window.addEventListener(e, activity, { passive: true }));
    const timer = window.setInterval(async () => {
      const now = Date.now();
      if (now - lastActivity.current >= INACTIVITY_MS) {
        await fetch('/api/auth/logout', { method: 'POST', credentials: 'include' }).catch(() => {});
        setAccount(null);
        return;
      }
      if (now - lastPing >= 60_000 && document.visibilityState === 'visible') {
        lastPing = now;
        try {
          const response = await fetch('/api/auth/ping', { method: 'POST', credentials: 'include' });
          if (response.status === 401) setAccount(null);
        } catch { /* la próxima solicitud confirmará el estado */ }
      }
    }, 15_000);
    return () => {
      window.clearInterval(timer);
      events.forEach(e => window.removeEventListener(e, activity));
    };
  }, [account]);

  const login = useCallback(async (username: string, password: string) => {
    const response = await fetch('/api/auth/login', {
      method: 'POST', credentials: 'include', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
    });
    if (!response.ok) {
      const body = await response.json().catch(() => ({ detail: 'No se pudo iniciar sesión' }));
      throw new Error(body.detail || 'No se pudo iniciar sesión');
    }
    lastActivity.current = Date.now();
    setAccount(await response.json() as Account);
  }, []);
  const logout = useCallback(async () => {
    try { await fetch('/api/auth/logout', { method: 'POST', credentials: 'include' }); }
    finally { setAccount(null); }
  }, []);
  const role = account?.role;
  return <AuthContext.Provider value={{
    account, loading, login, logout,
    canViewPrices: role === 'master' || role === 'admin',
    canEditPrices: role === 'master',
    canArchive: role === 'master' || role === 'admin',
    canAdminister: role === 'master' || role === 'admin',
  }}>{children}</AuthContext.Provider>;
}
