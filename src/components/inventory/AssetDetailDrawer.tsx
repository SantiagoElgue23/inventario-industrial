import { Archive, Link2, Pencil, Unlink, X } from 'lucide-react';
import { useMemo, useState } from 'react';
import type { ActivoDetalle, ActivoResumen, Producto } from '../../types/inventory';
import { normalized } from '../../utils/catalogSearch';
import { useAuth } from '../../auth/useAuth';

type Props = {
  activo: ActivoDetalle | null;
  activosDisponibles: ActivoResumen[];
  productos: Producto[];
  onClose: () => void;
  onEdit: (activo: ActivoDetalle) => void;
  onArchive: (activo: ActivoDetalle) => void;
  onAddRelationship: (targetId: number, role: string) => Promise<void>;
  onEndRelationship: (relationshipId: number) => Promise<void>;
};

const roles = [
  ['controller', 'Controlador'],
  ['smartpad', 'SmartPad'],
] as const;

const statusLabel: Record<string, string> = {
  in_stock: 'Disponible',
  sold: 'Vendido',
  disposed: 'Dado de baja',
  lost: 'Extraviado',
  unverified: 'Sin verificar',
  functional: 'Operativo',
  damaged: 'Averiado',
};

const roleLabel = (role: string) => roles.find(([value]) => value === role)?.[1] ?? role;

export default function AssetDetailDrawer({
  activo, activosDisponibles, productos, onClose, onEdit, onArchive, onAddRelationship, onEndRelationship,
}: Props) {
  const { canViewPrices, canArchive } = useAuth();
  const [targetId, setTargetId] = useState('');
  const [role, setRole] = useState('controller');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const byProduct = useMemo(() => new Map<number, Producto>(productos.map(p => [p.id, p])), [productos]);
  const isRobot = normalized(byProduct.get(activo?.product_id ?? -1)?.component_type_name) === 'robot';
  const expectedType = role === 'controller' ? 'controlador de robot' : 'smartpad';
  const available = useMemo(() => {
    const alreadyAssigned = new Set(activo?.active_relationships.map(r => r.target_asset_id) ?? []);
    return activosDisponibles.filter(item =>
      item.id !== activo?.id && item.lifecycle_status === 'in_stock' && item.active &&
      !alreadyAssigned.has(item.id) &&
      normalized(byProduct.get(item.product_id ?? -1)?.component_type_name) === expectedType,
    );
  }, [activosDisponibles, activo, byProduct, expectedType]);

  if (!activo) return null;
  const title = activo.product_name || activo.product_model || `Activo ${activo.asset_code}`;

  async function addRelationship() {
    if (!targetId || !isRobot || !available.some(item => item.id === Number(targetId))) return;
    setBusy(true);
    setError('');
    try {
      await onAddRelationship(Number(targetId), role);
      setTargetId('');
    } catch (e) {
      setError(e instanceof Error ? e.message : 'No se pudo crear la asociación.');
    } finally {
      setBusy(false);
    }
  }

  async function endRelationship(id: number) {
    setBusy(true);
    setError('');
    try {
      await onEndRelationship(id);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'No se pudo finalizar la asociación.');
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="fixed inset-0 z-[90] flex justify-end bg-slate-950/40">
      <button type="button" className="absolute inset-0" aria-label="Cerrar detalle" onClick={onClose} />
      <aside role="dialog" aria-modal="true" aria-label={`Ficha ${activo.asset_code}`} className="relative z-10 h-full w-full max-w-xl overflow-y-auto bg-white dark:bg-slate-900 p-6 shadow-xl sm:p-8">
        <div className="flex justify-end">
          <button type="button" onClick={onClose} aria-label="Cerrar" className="rounded-lg p-2 hover:bg-slate-100 dark:hover:bg-slate-800"><X size={20} /></button>
        </div>
        <h2 className="mt-5 text-2xl font-bold">{title}</h2>
        <p className="mt-1 font-mono text-sm text-blue-700 dark:text-blue-300">{activo.asset_code}</p>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">{[activo.product_brand || activo.manufacturer_brand, activo.product_model].filter(Boolean).join(' · ') || 'Sin modelo asociado'}</p>

        <div className="mt-6 flex flex-wrap gap-2">
          <button onClick={() => onEdit(activo)} className="inline-flex items-center gap-2 rounded-lg bg-blue-700 dark:bg-blue-600 px-3 py-2 text-sm font-semibold text-white"><Pencil size={15} />Editar unidad</button>
          {canArchive && <button onClick={() => onArchive(activo)} className="inline-flex items-center gap-2 rounded-lg border border-red-200 dark:border-red-900 px-3 py-2 text-sm font-medium text-red-700 dark:text-red-300"><Archive size={15} />Archivar</button>}
        </div>

        <section className="mt-7">
          <h3 className="font-bold">Identificación y estado</h3>
          <div className="mt-3 divide-y divide-slate-100 dark:divide-slate-800 text-sm">
            {[
              ['Número de serie', activo.manufacturer_serial || 'No registrado'],
              ['Fabricante', activo.manufacturer_brand || activo.product_brand || 'No registrado'],
              ['Modelo', activo.product_model || 'No asociado'],
              ['Estado funcional', statusLabel[activo.functional_status] ?? activo.functional_status],
              ['Proyecto', activo.project_names?.length ? activo.project_names.join(', ') : 'Sin proyectos asignados'],
              ['Ubicación', activo.location_name || 'Sin ubicación'],
              ...(canViewPrices ? [['Valor estimado', activo.estimated_value == null ? 'Sin valor' : `${new Intl.NumberFormat('es-PY').format(activo.estimated_value)} ${activo.value_currency}`]] : []),
              ['Observaciones', activo.observations || '—'],
            ].map(([label, value]) => <div key={label} className="flex justify-between gap-4 py-3"><span className="text-slate-500 dark:text-slate-400">{label}</span><span className="max-w-[65%] text-right font-medium">{value}</span></div>)}
          </div>
        </section>

        <section className="mt-7">
          <div className="flex items-center justify-between gap-3">
            <h3 className="font-bold">Componentes asociados</h3>
            <span className="text-xs text-slate-500 dark:text-slate-400">{activo.active_relationships.length} activos</span>
          </div>
          {activo.active_relationships.length === 0 ? (
            <p className="mt-3 rounded-lg bg-slate-50 dark:bg-slate-950 p-4 text-sm text-slate-500 dark:text-slate-400">Sin componentes asociados.</p>
          ) : (
            <div className="mt-3 space-y-2">
              {activo.active_relationships.map((rel) => (
                <div key={rel.id} className="flex items-center justify-between gap-3 rounded-lg border border-slate-200 dark:border-slate-700 p-3">
                  <div className="min-w-0">
                    <p className="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">{roleLabel(rel.relationship_type)}</p>
                    <p className="mt-1 truncate text-sm font-semibold">{rel.target_asset.product_name || rel.target_asset.product_model || 'Activo sin producto'}</p>
                    <p className="mt-1 font-mono text-xs text-blue-700 dark:text-blue-300">{rel.target_asset.asset_code}</p>
                    <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">Serie: {rel.target_asset.manufacturer_serial || 'No registrada'}</p>
                  </div>
                  <button type="button" disabled={busy} onClick={() => void endRelationship(rel.id)} title="Desvincular componente" className="rounded-lg p-2 text-slate-500 dark:text-slate-400 hover:bg-red-50 dark:hover:bg-red-950 hover:text-red-700 dark:hover:text-red-300 disabled:opacity-50"><Unlink size={16} /></button>
                </div>
              ))}
            </div>
          )}

          {isRobot ? (
            <div className="mt-4 rounded-xl border border-slate-200 dark:border-slate-700 p-4">
              <h4 className="flex items-center gap-2 text-sm font-semibold"><Link2 size={16} />Asociar un componente</h4>
              <div className="mt-3 space-y-3">
                <label className="block space-y-1 text-sm">
                  <span className="text-slate-600 dark:text-slate-300">Función del componente</span>
                  <select value={role} onChange={e => { setRole(e.target.value); setTargetId(''); }} className="w-full rounded-lg border border-slate-300 dark:border-slate-600 px-3 py-2">
                    {roles.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
                  </select>
                </label>
                <label className="block space-y-1 text-sm">
                  <span className="text-slate-600 dark:text-slate-300">Unidad compatible disponible</span>
                  <select value={targetId} onChange={e => setTargetId(e.target.value)} className="w-full rounded-lg border border-slate-300 dark:border-slate-600 px-3 py-2">
                    <option value="">Seleccionar componente</option>
                    {available.map(item => <option key={item.id} value={item.id}>{item.product_name || 'Activo sin producto'} · {item.asset_code} · {item.manufacturer_serial || 'Sin serie'}</option>)}
                  </select>
                </label>
                {available.length === 0 && <p className="text-xs text-amber-700 dark:text-amber-300">No hay unidades de este tipo disponibles. Revisá que tengan un artículo con el tipo de componente correcto.</p>}
                <button type="button" disabled={!targetId || busy} onClick={() => void addRelationship()} className="w-full rounded-lg bg-slate-900 dark:bg-slate-700 px-3 py-2.5 text-sm font-semibold text-white disabled:opacity-40">{busy ? 'Procesando...' : 'Asociar componente'}</button>
              </div>
            </div>
          ) : (
            <p className="mt-4 rounded-lg bg-slate-50 dark:bg-slate-950 p-3 text-xs text-slate-600 dark:text-slate-300">Las asociaciones de controlador y SmartPad se gestionan desde la ficha de un robot. Para habilitarlas, la unidad principal debe estar vinculada a un artículo de tipo Robot.</p>
          )}
          {error && <p className="mt-3 rounded-lg bg-red-50 dark:bg-red-950/60 p-3 text-sm text-red-700 dark:text-red-300">{error}</p>}
        </section>
        {activo.relationship_history.length > activo.active_relationships.length && (
          <p className="mt-5 text-xs text-slate-500 dark:text-slate-400">Este activo tiene {activo.relationship_history.length - activo.active_relationships.length} asociaciones anteriores en su historial.</p>
        )}
      </aside>
    </div>
  );
}
