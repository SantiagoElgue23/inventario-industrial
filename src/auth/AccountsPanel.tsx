import { useCallback, useEffect, useState, type FormEvent } from 'react';
import { KeyRound, UserPlus } from 'lucide-react';
import { useAuth } from './useAuth';
import {
  actualizarCuenta,
  cambiarMiContrasena,
  crearCuenta,
  listarCuentas,
  restablecerContrasenaCuenta,
} from '../services/inventoryService';
import type { CuentaUsuario } from '../types/inventory';

const input = 'w-full rounded-lg border p-2 dark:border-slate-600 dark:bg-slate-800';
const card = 'rounded-xl border border-slate-200 bg-white p-5 dark:border-slate-700 dark:bg-slate-900';
const primary = 'rounded-lg bg-blue-700 px-4 py-2 text-sm font-semibold text-white disabled:opacity-60';
const ROLE_LABEL: Record<CuentaUsuario['role'], string> = { master: 'Master', admin: 'Administrador', user: 'Usuario' };

function errorText(e: unknown, fallback: string) {
  return e instanceof Error ? e.message : fallback;
}

/** Cambio de la propia contraseña; disponible para cualquier rol que acceda a Administración. */
function OwnPasswordForm() {
  const [current, setCurrent] = useState('');
  const [next, setNext] = useState('');
  const [repeat, setRepeat] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const { logout } = useAuth();

  async function submit(e: FormEvent) {
    e.preventDefault(); setError('');
    if (next.length < 12 || next !== repeat) {
      setError('Usá al menos 12 caracteres y confirmá la misma contraseña.'); return;
    }
    setBusy(true);
    try {
      await cambiarMiContrasena(current, next);
      // El backend cierra todas las sesiones de la cuenta, incluida esta.
      await logout();
    } catch (e) { setError(errorText(e, 'No se pudo cambiar la contraseña')); }
    finally { setBusy(false); }
  }

  return <form onSubmit={submit} className="grid gap-3 sm:grid-cols-4">
    <label className="space-y-1 text-sm"><span>Contraseña actual</span><input type="password" required value={current} onChange={e => setCurrent(e.target.value)} autoComplete="current-password" className={input} /></label>
    <label className="space-y-1 text-sm"><span>Nueva contraseña</span><input type="password" minLength={12} required value={next} onChange={e => setNext(e.target.value)} autoComplete="new-password" className={input} /></label>
    <label className="space-y-1 text-sm"><span>Confirmar</span><input type="password" minLength={12} required value={repeat} onChange={e => setRepeat(e.target.value)} autoComplete="new-password" className={input} /></label>
    <div className="flex items-end"><button disabled={busy} className={`${primary} w-full`}>{busy ? 'Guardando…' : 'Cambiar mi contraseña'}</button></div>
    {error && <p role="alert" className="text-sm text-red-700 sm:col-span-4">{error}</p>}
    <p className="text-xs text-slate-500 dark:text-slate-400 sm:col-span-4">Al cambiarla se cierran todas tus sesiones y vas a tener que volver a ingresar.</p>
  </form>;
}

/** Alta y administración de cuentas admin/user. Las cuentas master se gestionan por consola. */
function AccountsManager() {
  const [cuentas, setCuentas] = useState<CuentaUsuario[]>([]);
  const [username, setUsername] = useState('');
  const [role, setRole] = useState<'admin' | 'user'>('user');
  const [password, setPassword] = useState('');
  const [resetFor, setResetFor] = useState<CuentaUsuario | null>(null);
  const [resetPassword, setResetPassword] = useState('');
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);

  const cargar = useCallback(async () => {
    try { setCuentas(await listarCuentas()); }
    catch (e) { setError(errorText(e, 'No se pudieron cargar las cuentas')); }
  }, []);
  useEffect(() => {
    let vigente = true;
    listarCuentas()
      .then(data => { if (vigente) setCuentas(data); })
      .catch(e => { if (vigente) setError(errorText(e, 'No se pudieron cargar las cuentas')); });
    return () => { vigente = false; };
  }, []);

  async function ejecutar(accion: () => Promise<unknown>, exito: string) {
    setError(''); setMessage(''); setBusy(true);
    try { await accion(); setMessage(exito); await cargar(); return true; }
    catch (e) { setError(errorText(e, 'La operación no se pudo completar')); return false; }
    finally { setBusy(false); }
  }

  async function crear(e: FormEvent) {
    e.preventDefault();
    const nombre = username.trim().toLowerCase();
    if (await ejecutar(() => crearCuenta({ username: nombre, role, password }), `Cuenta ${nombre} creada.`)) {
      setUsername(''); setPassword(''); setRole('user');
    }
  }

  async function restablecer(e: FormEvent) {
    e.preventDefault();
    if (!resetFor) return;
    if (await ejecutar(() => restablecerContrasenaCuenta(resetFor.id, resetPassword),
      `Contraseña de ${resetFor.username} restablecida. Se cerraron sus sesiones.`)) {
      setResetFor(null); setResetPassword('');
    }
  }

  return <div className="space-y-4">
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead><tr className="border-b text-left text-slate-500 dark:border-slate-700 dark:text-slate-400">
          <th className="py-2 pr-3 font-medium">Usuario</th><th className="py-2 pr-3 font-medium">Rol</th>
          <th className="py-2 pr-3 font-medium">Estado</th><th className="py-2 font-medium">Acciones</th>
        </tr></thead>
        <tbody>
          {cuentas.map(c => <tr key={c.id} className="border-b last:border-0 dark:border-slate-800">
            <td className="py-2 pr-3 font-medium">{c.username}</td>
            <td className="py-2 pr-3">
              {c.role === 'master'
                ? <span title="El rol master solo se administra por consola">{ROLE_LABEL.master}</span>
                : <select value={c.role} disabled={busy} aria-label={`Rol de ${c.username}`}
                    onChange={e => void ejecutar(() => actualizarCuenta(c.id, { role: e.target.value as 'admin' | 'user' }), `Rol de ${c.username} actualizado.`)}
                    className="rounded-lg border p-1 dark:border-slate-600 dark:bg-slate-800">
                    <option value="admin">{ROLE_LABEL.admin}</option><option value="user">{ROLE_LABEL.user}</option>
                  </select>}
            </td>
            <td className="py-2 pr-3">{c.active ? 'Activa' : <span className="text-slate-500">Inactiva</span>}</td>
            <td className="py-2">
              {c.role === 'master' ? <span className="text-xs text-slate-500">Solo por consola</span> : <div className="flex flex-wrap gap-2">
                <button type="button" disabled={busy} onClick={() => { setResetFor(c); setResetPassword(''); }} className="inline-flex items-center gap-1 rounded-lg border px-2 py-1 text-xs dark:border-slate-600"><KeyRound size={14} />Contraseña</button>
                <button type="button" disabled={busy} onClick={() => void ejecutar(() => actualizarCuenta(c.id, { active: !c.active }), `Cuenta ${c.username} ${c.active ? 'desactivada' : 'activada'}.`)} className="rounded-lg border px-2 py-1 text-xs dark:border-slate-600">{c.active ? 'Desactivar' : 'Activar'}</button>
              </div>}
            </td>
          </tr>)}
        </tbody>
      </table>
    </div>

    {resetFor && <form onSubmit={restablecer} className="grid gap-3 rounded-lg bg-slate-50 p-3 dark:bg-slate-800/60 sm:grid-cols-3">
      <label className="space-y-1 text-sm sm:col-span-2"><span>Nueva contraseña para {resetFor.username}</span><input type="password" minLength={12} required value={resetPassword} onChange={e => setResetPassword(e.target.value)} autoComplete="new-password" className={input} /></label>
      <div className="flex items-end gap-2"><button disabled={busy} className={primary}>Restablecer</button><button type="button" onClick={() => setResetFor(null)} className="rounded-lg border px-3 py-2 text-sm dark:border-slate-600">Cancelar</button></div>
    </form>}

    <form onSubmit={crear} className="grid gap-3 sm:grid-cols-4">
      <label className="space-y-1 text-sm"><span>Usuario nuevo</span><input required pattern="[a-z0-9._\-]{3,32}" title="3 a 32 caracteres: minúsculas, números, punto, guion o guion bajo" value={username} onChange={e => setUsername(e.target.value)} autoComplete="off" className={input} /></label>
      <label className="space-y-1 text-sm"><span>Rol</span><select value={role} onChange={e => setRole(e.target.value as 'admin' | 'user')} className={input}><option value="user">{ROLE_LABEL.user}</option><option value="admin">{ROLE_LABEL.admin}</option></select></label>
      <label className="space-y-1 text-sm"><span>Contraseña inicial</span><input type="password" minLength={12} required value={password} onChange={e => setPassword(e.target.value)} autoComplete="new-password" className={input} /></label>
      <div className="flex items-end"><button disabled={busy} className={`${primary} inline-flex w-full items-center justify-center gap-2`}><UserPlus size={16} />Crear cuenta</button></div>
    </form>

    {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
    {message && <p className="text-sm text-emerald-700">{message}</p>}
  </div>;
}

export default function AccountsPanel() {
  const { account } = useAuth();
  if (!account) return null;
  return <section className={`${card} space-y-6`}>
    {account.role === 'master' && <div>
      <h2 className="mb-1 font-semibold">Cuentas de acceso</h2>
      <p className="mb-4 text-sm text-slate-600 dark:text-slate-300">Cada persona usa su propia cuenta. Las cuentas master se crean y administran solo desde la consola del servidor.</p>
      <AccountsManager />
    </div>}
    <div>
      <h2 className="mb-3 font-semibold">Mi contraseña <span className="font-normal text-slate-500">({account.username})</span></h2>
      <OwnPasswordForm />
    </div>
  </section>;
}
