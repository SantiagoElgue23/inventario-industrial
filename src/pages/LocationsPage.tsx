import { useCallback, useMemo, useState, type FormEvent } from 'react';
import { Archive, ChevronDown, MapPin, Pencil, Plus, Warehouse } from 'lucide-react';
import { archivarUbicacion, actualizarUbicacion, crearUbicacion, obtenerUbicaciones } from '../services/inventoryService';
import type { Ubicacion, UbicacionPayload } from '../types/inventory';
import { useAuth } from '../auth/useAuth';

import { useLoadEffect } from '../hooks/useLoadEffect';
export default function LocationsPage() {
  const { canAdminister } = useAuth();
  const [locations, setLocations] = useState<Ubicacion[]>([]);
  const [name, setName] = useState('');
  const [type, setType] = useState<UbicacionPayload['location_type']>('warehouse');
  const [parentId, setParentId] = useState('');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [expandedWarehouses, setExpandedWarehouses] = useState<Set<number>>(() => new Set());

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      setLocations(await obtenerUbicaciones());
    } catch (e) {
      setError(e instanceof Error ? e.message : 'No se pudieron cargar las ubicaciones.');
    } finally {
      setLoading(false);
    }
  }, []);

  useLoadEffect(load);

  const warehouses = useMemo(() => locations.filter((l) => l.location_type === 'warehouse'), [locations]);
  const roots = useMemo(() => locations.filter((l) => l.parent_id === null), [locations]);

  async function create(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!name.trim()) return;
    if (type === 'shelf' && !parentId) {
      setError('Seleccioná el almacén al que pertenece la estantería.');
      return;
    }
    setSaving(true);
    setError('');
    setMessage('');
    try {
      await crearUbicacion({
        name: name.trim(),
        location_type: type,
        parent_id: type === 'shelf' ? Number(parentId) : null,
      });
      setName('');
      setParentId('');
      setMessage(type === 'shelf' ? 'Estantería creada.' : 'Ubicación principal creada.');
      if (type === 'shelf') {
        const createdParentId = Number(parentId);
        setExpandedWarehouses((previous) => new Set(previous).add(createdParentId));
      }
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'No se pudo crear la ubicación.');
    } finally {
      setSaving(false);
    }
  }

  async function rename(location: Ubicacion) {
    const newName = window.prompt('Nuevo nombre:', location.name);
    if (!newName?.trim() || newName.trim() === location.name) return;
    try {
      await actualizarUbicacion(location.id, { name: newName.trim() });
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'No se pudo renombrar la ubicación.');
    }
  }

  async function archive(location: Ubicacion) {
    if (!window.confirm(`¿Archivar "${location.name}"? La ubicación no se elimina del historial.`)) return;
    try {
      await archivarUbicacion(location.id);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'No se pudo archivar la ubicación.');
    }
  }

  const children = (id: number) => locations.filter((l) => l.parent_id === id);
  const toggleWarehouse = (id: number) => {
    setExpandedWarehouses((previous) => {
      const next = new Set(previous);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };
  const label = (location: Ubicacion) =>
    location.location_type === 'warehouse' ? 'Almacén' :
      location.location_type === 'shelf' ? 'Estantería' : 'Área / sector';

  return (
    <div className="mx-auto max-w-6xl space-y-6 p-4 md:p-7">
      <h1 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-slate-100">Ubicaciones</h1>

      {error && <p className="rounded-lg border border-red-200 dark:border-red-900 bg-red-50 dark:bg-red-950/60 px-4 py-3 text-sm text-red-700 dark:text-red-300">{error}</p>}
      {message && <p className="rounded-lg border border-emerald-200 dark:border-emerald-900 bg-emerald-50 dark:bg-emerald-950/60 px-4 py-3 text-sm text-emerald-700 dark:text-emerald-300">{message}</p>}

      <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_340px]">
        <section className="overflow-hidden rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900">
          <div className="flex items-center justify-between border-b border-slate-100 dark:border-slate-800 p-4">
            <p className="text-sm font-medium text-slate-600 dark:text-slate-300">{locations.length} ubicaciones activas</p>
            <button onClick={() => void load()} className="text-xs font-semibold text-blue-700 dark:text-blue-300">Actualizar</button>
          </div>
          {loading ? <p className="p-6 text-sm text-slate-500 dark:text-slate-400">Cargando ubicaciones...</p> : roots.length === 0 ? (
            <div className="p-10 text-center"><Warehouse className="mx-auto text-slate-300 dark:text-slate-500" size={30} /><p className="mt-3 text-sm font-medium">Todavía no hay ubicaciones.</p></div>
          ) : (
            <div className="divide-y divide-slate-100 dark:divide-slate-800">
              {roots.map((root) => {
                const shelves = children(root.id);
                const canExpand = root.location_type === 'warehouse' && shelves.length > 0;
                const isExpanded = expandedWarehouses.has(root.id);

                return (
                  <div key={root.id} className="p-4">
                    <div className="flex items-center justify-between gap-3">
                      <div className="flex min-w-0 flex-1 items-center gap-3">
                        <div className="rounded-lg bg-blue-50 dark:bg-blue-950 p-2 text-blue-700 dark:text-blue-300"><MapPin size={18} /></div>
                        {canExpand ? (
                          <button
                            type="button"
                            aria-expanded={isExpanded}
                            aria-controls={`estanterias-${root.id}`}
                            title={isExpanded ? 'Ocultar estanterías' : 'Mostrar estanterías'}
                            onClick={() => toggleWarehouse(root.id)}
                            className="flex min-w-0 flex-1 items-center justify-between gap-3 rounded-lg py-1 text-left hover:text-blue-700 dark:hover:text-blue-300 focus-visible:outline focus-visible:outline-2 focus-visible:outline-blue-600 dark:focus-visible:outline-blue-400"
                          >
                            <span className="min-w-0">
                              <span className="block truncate font-semibold">{root.name}</span>
                              <span className="block text-xs text-slate-500 dark:text-slate-400">{label(root)} · {shelves.length} estanterías</span>
                            </span>
                            <ChevronDown size={18} className={`shrink-0 text-slate-500 dark:text-slate-400 transition-transform ${isExpanded ? 'rotate-180' : ''}`} />
                          </button>
                        ) : (
                          <div className="min-w-0">
                            <p className="truncate font-semibold">{root.name}</p>
                            <p className="text-xs text-slate-500 dark:text-slate-400">{label(root)}{root.location_type === 'warehouse' ? ' · 0 estanterías' : ''}</p>
                          </div>
                        )}
                      </div>
                      {canAdminister && <div className="flex shrink-0 gap-1">
                        <button type="button" onClick={() => void rename(root)} title="Renombrar" aria-label={`Renombrar ${root.name}`} className="rounded-lg p-2 text-slate-500 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800"><Pencil size={16} /></button>
                        <button type="button" onClick={() => void archive(root)} title="Archivar" aria-label={`Archivar ${root.name}`} className="rounded-lg p-2 text-slate-500 dark:text-slate-400 hover:bg-red-50 dark:hover:bg-red-950 hover:text-red-700 dark:hover:text-red-300"><Archive size={16} /></button>
                      </div>}
                    </div>
                    {canExpand && (
                      <div id={`estanterias-${root.id}`} hidden={!isExpanded} className="ml-9 mt-3 space-y-2 border-l border-slate-200 dark:border-slate-700 pl-4">
                        {shelves.map((child) => (
                          <div key={child.id} className="flex items-center justify-between gap-3 rounded-lg bg-slate-50 dark:bg-slate-950 px-3 py-2">
                            <div><p className="text-sm font-medium">{child.name}</p><p className="text-xs text-slate-500 dark:text-slate-400">Estantería</p></div>
                            {canAdminister && <div className="flex gap-1">
                              <button type="button" onClick={() => void rename(child)} title="Renombrar" aria-label={`Renombrar ${child.name}`} className="rounded-lg p-2 text-slate-500 dark:text-slate-400 hover:bg-white"><Pencil size={15} /></button>
                              <button type="button" onClick={() => void archive(child)} title="Archivar" aria-label={`Archivar ${child.name}`} className="rounded-lg p-2 text-slate-500 dark:text-slate-400 hover:bg-red-50 dark:hover:bg-red-950 hover:text-red-700 dark:hover:text-red-300"><Archive size={15} /></button>
                            </div>}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </section>

        {canAdminister && <section className="h-fit rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 p-5">
          <h3 className="flex items-center gap-2 font-semibold"><Plus size={18} />Nueva ubicación</h3>
          <form onSubmit={create} className="mt-4 space-y-4">
            <label className="block space-y-1 text-sm"><span className="font-medium">Nombre</span><input value={name} onChange={(e) => setName(e.target.value)} className="w-full rounded-lg border border-slate-300 dark:border-slate-600 px-3 py-2.5" placeholder={type === 'shelf' ? 'Ej.: Estantería A1' : type === 'area' ? 'Ej.: Galpón' : 'Ej.: Almacén 1'} /></label>
            <label className="block space-y-1 text-sm"><span className="font-medium">Tipo de ubicación</span><select value={type} onChange={(e) => { setType(e.target.value as UbicacionPayload['location_type']); setParentId(''); }} className="w-full rounded-lg border border-slate-300 dark:border-slate-600 px-3 py-2.5"><option value="warehouse">Almacén</option><option value="area">Área general (Galpón)</option><option value="shelf">Estantería</option></select></label>
            {type === 'shelf' && <label className="block space-y-1 text-sm"><span className="font-medium">Almacén superior</span><select value={parentId} onChange={(e) => setParentId(e.target.value)} className="w-full rounded-lg border border-slate-300 dark:border-slate-600 px-3 py-2.5"><option value="">Seleccionar almacén</option>{warehouses.map((w) => <option key={w.id} value={w.id}>{w.name}</option>)}</select></label>}
            <button disabled={saving || !name.trim() || (type === 'shelf' && !parentId)} className="w-full rounded-lg bg-blue-700 dark:bg-blue-600 px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-40">{saving ? 'Guardando...' : 'Crear ubicación'}</button>
          </form>
        </section>}
      </div>
    </div>
  );
}
