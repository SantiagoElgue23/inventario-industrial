import { useState, type FormEvent } from 'react';
import { Boxes } from 'lucide-react';
import { useAuth } from './useAuth';

export default function LoginPage() {
  const { login } = useAuth();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  async function submit(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError('');
    try { await login(username, password); }
    catch (e) { setError(e instanceof Error ? e.message : 'No se pudo iniciar sesión'); }
    finally { setBusy(false); }
  }
  return <main className="flex min-h-screen items-center justify-center bg-slate-100 p-4 text-slate-800 dark:bg-slate-950 dark:text-slate-100">
    <form onSubmit={submit} className="w-full max-w-sm space-y-5 rounded-2xl border border-slate-200 bg-white p-8 shadow-lg dark:border-slate-700 dark:bg-slate-900">
      <div className="flex items-center gap-3"><div className="flex h-12 w-12 items-center justify-center rounded-xl bg-blue-600 text-white"><Boxes size={28} aria-hidden="true"/></div><div><h1 className="text-xl font-bold">Inventario Industrial</h1><p className="text-xs text-slate-500 dark:text-slate-400">Iniciar sesión</p></div></div>
      <label className="block space-y-1 text-sm"><span>Usuario</span><input required autoComplete="username" value={username} onChange={e=>setUsername(e.target.value)} className="w-full rounded-lg border border-slate-300 p-2.5 dark:border-slate-600 dark:bg-slate-800"/></label>
      <label className="block space-y-1 text-sm"><span>Contraseña</span><input required type="password" autoComplete="current-password" value={password} onChange={e=>setPassword(e.target.value)} className="w-full rounded-lg border border-slate-300 p-2.5 dark:border-slate-600 dark:bg-slate-800"/></label>
      {error && <p role="alert" className="text-sm text-red-700 dark:text-red-300">{error}</p>}
      <button type="submit" disabled={busy} className="w-full rounded-lg bg-blue-700 px-4 py-2.5 font-semibold text-white disabled:opacity-60">{busy?'Verificando…':'Iniciar sesión'}</button>
    </form>
  </main>;
}
