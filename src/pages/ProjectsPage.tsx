import ProjectWorksPanel from '../components/ProjectWorksPanel';
import { useSearchParams } from 'react-router';
import { useAuth } from '../auth/useAuth';
import { useCallback, useMemo, useState, type FormEvent } from 'react';
import { Archive, CalendarDays, FolderKanban, Minus, Plus, RefreshCw, Search } from 'lucide-react';
import { rankMatch } from '../utils/catalogSearch';
import {
  archivarProyecto,
  asignarActivosEnLote,
  asignarProductosEnLote,
  actualizarProyecto,
  crearProyecto,
  liberarActivoDeProyecto,
  liberarProductoDeProyecto,
  obtenerActivos,
  obtenerProductos,
  obtenerProyecto,
  obtenerProyectos,
} from '../services/inventoryService';
import type {
  Activo,
  EstadoProyecto,
  Producto,
  Proyecto,
  ProyectoDetalle,
  ProyectoPayload,
} from '../types/inventory';

import { useLoadEffect } from '../hooks/useLoadEffect';
const statusLabels: Record<EstadoProyecto, string> = {
  planning: 'Planificación',
  active: 'Activo',
  on_hold: 'En pausa',
  completed: 'Finalizado',
  cancelled: 'Cancelado',
};

const statusStyles: Record<EstadoProyecto, string> = {
  planning: 'bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-200',
  active: 'bg-emerald-50 dark:bg-emerald-950/60 text-emerald-700 dark:text-emerald-300',
  on_hold: 'bg-amber-50 dark:bg-amber-950/60 text-amber-700 dark:text-amber-300',
  completed: 'bg-blue-50 dark:bg-blue-950 text-blue-700 dark:text-blue-300',
  cancelled: 'bg-red-50 dark:bg-red-950/60 text-red-700 dark:text-red-300',
};

function ProjectForm({
  project, onClose, onSave,
}: {
  project: Proyecto | null;
  onClose: () => void;
  onSave: (payload: ProyectoPayload) => Promise<void>;
}) {
  const [name, setName] = useState(project?.name ?? '');
  const [description, setDescription] = useState(project?.description ?? '');
  const [status, setStatus] = useState<EstadoProyecto>(project?.status ?? 'planning');
  const [startDate, setStartDate] = useState(project?.start_date ?? '');
  const [endDate, setEndDate] = useState(project?.end_date ?? '');
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!name.trim()) {
      setError('El nombre del proyecto es obligatorio.');
      return;
    }
    if (startDate && endDate && endDate < startDate) {
      setError('La fecha final no puede ser anterior a la fecha inicial.');
      return;
    }
    setSaving(true);
    setError('');
    try {
      await onSave({
        name: name.trim(),
        description: description.trim() || null,
        status,
        start_date: startDate || null,
        end_date: endDate || null,
      });
    } catch (e) {
      setError(e instanceof Error ? e.message : 'No se pudo guardar el proyecto.');
    } finally {
      setSaving(false);
    }
  }

  const field = 'w-full rounded-lg border border-slate-300 dark:border-slate-600 px-3 py-2.5 text-sm outline-none focus:border-blue-500 dark:focus:border-blue-400';

  return (
    <div className="fixed inset-0 z-[80] flex items-center justify-center bg-slate-950/50 p-4">
      <form onSubmit={submit} className="w-full max-w-xl space-y-4 rounded-2xl bg-white dark:bg-slate-900 p-6 shadow-2xl">
        <header className="flex items-center justify-between"><div><h3 className="text-lg font-bold">{project ? 'Editar proyecto' : 'Nuevo proyecto'}</h3><p className="mt-1 text-xs text-slate-500 dark:text-slate-400">Los recursos se asociarán después de crear el proyecto.</p></div><button type="button" onClick={onClose} className="rounded-lg px-3 py-2 text-slate-500 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800">Cerrar</button></header>
        <label className="block space-y-1 text-sm"><span className="font-medium">Nombre *</span><input value={name} onChange={(e) => setName(e.target.value)} className={field} /></label>
        <label className="block space-y-1 text-sm"><span className="font-medium">Descripción</span><textarea value={description} onChange={(e) => setDescription(e.target.value)} rows={3} className={field} /></label>
        <label className="block space-y-1 text-sm"><span className="font-medium">Estado</span><select value={status} onChange={(e) => setStatus(e.target.value as EstadoProyecto)} className={field}>{Object.entries(statusLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
        <div className="grid gap-3 sm:grid-cols-2">
          <label className="block space-y-1 text-sm"><span className="font-medium">Fecha de inicio</span><input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} className={field} /></label>
          <label className="block space-y-1 text-sm"><span className="font-medium">Fecha estimada de finalización</span><input type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} className={field} /></label>
        </div>
        {error && <p className="rounded-lg bg-red-50 dark:bg-red-950/60 p-3 text-sm text-red-700 dark:text-red-300">{error}</p>}
        <footer className="flex justify-end gap-2 border-t border-slate-100 dark:border-slate-800 pt-4"><button type="button" onClick={onClose} className="rounded-lg border border-slate-300 dark:border-slate-600 px-4 py-2 text-sm">Cancelar</button><button disabled={saving} className="rounded-lg bg-blue-700 dark:bg-blue-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">{saving ? 'Guardando...' : 'Guardar proyecto'}</button></footer>
      </form>
    </div>
  );
}

export default function ProjectsPage() {
  const { canViewPrices, canArchive } = useAuth();
  const [projects, setProjects] = useState<Proyecto[]>([]);
  const [products, setProducts] = useState<Producto[]>([]);
  const [availableAssets, setAvailableAssets] = useState<Activo[]>([]);
  const [selected, setSelected] = useState<ProyectoDetalle | null>(null);
  const [form, setForm] = useState<Proyecto | null | undefined>(undefined);
  const [selectedAssetIds, setSelectedAssetIds] = useState<number[]>([]);
  const [selectedProductQuantities, setSelectedProductQuantities] = useState<Record<number, string>>({});
  const [assetSearch, setAssetSearch] = useState('');
  const [productSearch, setProductSearch] = useState('');
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [projectTab,setProjectTab] = useState<'resources'|'works'>('resources');

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const [projectRows, productRows, assetRows] = await Promise.all([
        obtenerProyectos(),
        obtenerProductos(),
        obtenerActivos({ available_for_projects: true }),
      ]);
      setProjects(projectRows);
      setProducts(productRows);
      setAvailableAssets(assetRows);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'No se pudieron cargar los proyectos.');
    } finally {
      setLoading(false);
    }
  }, []);

  useLoadEffect(load);

  const quantityProducts = useMemo(() => products.filter((p) => p.tracking_mode === 'quantity'), [products]);
  const canAssign = !!selected && selected.active && !['completed', 'cancelled'].includes(selected.status);
  const activeAssetAssignments = useMemo(() => selected?.asset_assignments.filter(a => !a.released_at) ?? [], [selected]);
  const activeProductAssignments = useMemo(() => selected?.product_assignments.filter(a => !a.released_at) ?? [], [selected]);
  const filteredAssets = useMemo(() => availableAssets.filter(a => rankMatch(assetSearch, [
    { value: a.asset_code, weight: 100 },
    { value: a.manufacturer_serial, weight: 90 },
    { value: a.product_name, weight: 80 },
    { value: a.product_model, weight: 70 },
    { value: a.product_brand ?? a.manufacturer_brand, weight: 50 },
  ]) >= 0).sort((a,b) => a.asset_code.localeCompare(b.asset_code)), [availableAssets, assetSearch]);
  const filteredProducts = useMemo(() => quantityProducts
    .filter(p => !activeProductAssignments.some(a => a.product_id === p.id))
    .filter(p => rankMatch(productSearch, [
      { value: p.model, weight: 90 },
      { value: p.name, weight: 80 },
      { value: p.brand, weight: 60 },
      { value: p.component_type_name, weight: 20 },
      ...((p.search_aliases ?? []).map(value => ({ value, weight: 35 }))),
    ]) >= 0), [quantityProducts, activeProductAssignments, productSearch]);

  function toggleAsset(assetId: number, checked: boolean) {
    setSelectedAssetIds(current => checked ? [...current, assetId] : current.filter(id => id !== assetId));
  }

  function changeQuantity(productId: number, value: string) {
    setSelectedProductQuantities(old => ({ ...old, [productId]: value }));
  }

  function incrementQuantity(productId: number, delta: number) {
    const current = Number(selectedProductQuantities[productId] ?? '0');
    changeQuantity(productId, String(Math.max(0, Math.round((current + delta)*1000)/1000)));
  }

  function toggleProduct(productId: number, checked: boolean) {
    setSelectedProductQuantities(old => {
      const next = { ...old };
      if (checked) next[productId] = '1'; else delete next[productId];
      return next;
    });
  }


  async function saveProject(payload: ProyectoPayload) {
    const editedId = form?.id ?? null;
    if (editedId) await actualizarProyecto(editedId, payload);
    else await crearProyecto(payload);
    setForm(undefined);
    await load();
    if (editedId && selected?.id === editedId) {
      setSelected(await obtenerProyecto(editedId));
    }
  }

  // El proyecto abierto se toma de la URL (?id=…): así funcionan recargar, "atrás" y los links compartidos.
  const [searchParams, setSearchParams] = useSearchParams();
  const requestedProjectId = Number(searchParams.get('id')) || null;
  const openProject = (project: Proyecto) => setSearchParams({ id: String(project.id) });
  const closeProject = () => setSearchParams({});

  const loadRequestedProject = useCallback(async () => {
    if (requestedProjectId === null) { setSelected(null); return; }
    try {
      setError('');
      setSelected(await obtenerProyecto(requestedProjectId));
      setProjectTab('resources');
      setSelectedAssetIds([]);
      setSelectedProductQuantities({});
      setAssetSearch('');
      setProductSearch('');
    } catch (e) {
      setError(e instanceof Error ? e.message : 'No se pudo abrir el proyecto.');
    }
  }, [requestedProjectId]);
  useLoadEffect(loadRequestedProject);

  async function refreshSelected() {
    if (!selected) return;
    const [detail, rows] = await Promise.all([obtenerProyecto(selected.id), obtenerProyectos()]);
    setSelected(detail);
    setProjects(rows);
  }

  async function addAssets(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selected || !selectedAssetIds.length) return;
    setBusy(true);
    setError('');
    try {
      await asignarActivosEnLote(selected.id, selectedAssetIds);
      setSelectedAssetIds([]);
      await refreshSelected();
      setAvailableAssets(await obtenerActivos({ available_for_projects: true }));
    } catch (e) {
      setError(e instanceof Error ? e.message : 'No se pudieron asignar los activos. No se guardó el lote.');
    } finally {
      setBusy(false);
    }
  }

  async function addProducts(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const items = Object.entries(selectedProductQuantities).map(([id, value]) => ({
      product_id: Number(id), quantity: Number(value),
    }));
    if (!selected || !items.length) return;
    if (items.some(item => !Number.isFinite(item.quantity) || item.quantity <= 0)) {
      setError('Todas las cantidades deben ser mayores que cero.');
      return;
    }
    setBusy(true);
    setError('');
    try {
      await asignarProductosEnLote(selected.id, items);
      setSelectedProductQuantities({});
      await refreshSelected();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'No se pudieron asignar los artículos. No se guardó el lote.');
    } finally {
      setBusy(false);
    }
  }

  async function releaseAsset(assignmentId: number) {
    if (!selected || !window.confirm('¿Retirar este activo del proyecto?')) return;
    try {
      await liberarActivoDeProyecto(selected.id, assignmentId);
      await refreshSelected();
      setAvailableAssets(await obtenerActivos({ available_for_projects: true }));
    } catch (e) {
      setError(e instanceof Error ? e.message : 'No se pudo retirar el activo.');
    }
  }

  async function releaseProduct(assignmentId: number) {
    if (!selected || !window.confirm('¿Retirar este producto del proyecto?')) return;
    try {
      await liberarProductoDeProyecto(selected.id, assignmentId);
      await refreshSelected();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'No se pudo retirar el producto.');
    }
  }

  async function archive(project: Proyecto) {
    if (!window.confirm(`¿Archivar el proyecto "${project.name}"? Sus asignaciones vigentes serán cerradas.`)) return;
    try {
      await archivarProyecto(project.id);
      if (selected?.id === project.id) closeProject();
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'No se pudo archivar el proyecto.');
    }
  }

  const formatDate = (date: string | null) =>
    date ? new Date(`${date}T00:00:00`).toLocaleDateString('es-PY') : 'Sin definir';

  const formatCurrency = (value: number, currency: string) => {
    try {
      return new Intl.NumberFormat('es-PY', { style: 'currency', currency, minimumFractionDigits: currency === 'USD' ? 2 : 0, maximumFractionDigits: currency === 'USD' ? 2 : 0 }).format(value);
    } catch {
      return `${new Intl.NumberFormat('es-PY').format(value)} ${currency}`;
    }
  };

  return (
    <div className="mx-auto max-w-7xl space-y-6 p-4 md:p-7">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <h1 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-slate-100">Proyectos</h1>
        <button onClick={() => setForm(null)} className="inline-flex items-center gap-2 rounded-lg bg-blue-700 dark:bg-blue-600 px-4 py-2.5 text-sm font-semibold text-white"><Plus size={17} />Nuevo proyecto</button>
      </div>

      {error && <p className="rounded-lg border border-red-200 dark:border-red-900 bg-red-50 dark:bg-red-950/60 px-4 py-3 text-sm text-red-700 dark:text-red-300">{error}</p>}

      <div className="grid gap-5 lg:grid-cols-[340px_minmax(0,1fr)]">
        <section className="overflow-hidden rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900">
          <div className="flex items-center justify-between border-b border-slate-100 dark:border-slate-800 p-4"><p className="text-sm font-medium text-slate-600 dark:text-slate-300">{projects.length} proyectos</p><button onClick={() => void load()} title="Actualizar" className="rounded-lg p-2 text-slate-500 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800"><RefreshCw size={16} /></button></div>
          {loading ? <p className="p-5 text-sm text-slate-500 dark:text-slate-400">Cargando proyectos...</p> : projects.length === 0 ? <div className="p-8 text-center"><FolderKanban size={30} className="mx-auto text-slate-300 dark:text-slate-500" /><p className="mt-3 text-sm text-slate-500 dark:text-slate-400">Todavía no hay proyectos registrados.</p></div> : (
            <div className="divide-y divide-slate-100 dark:divide-slate-800">
              {projects.map((project) => (
                <button key={project.id} type="button" onClick={() => openProject(project)} className={`w-full p-4 text-left hover:bg-slate-50 dark:hover:bg-slate-800 ${selected?.id === project.id ? 'bg-blue-50 dark:bg-blue-950' : ''}`}>
                  <div className="flex items-start justify-between gap-2"><span className="font-semibold">{project.name}</span><span className={`shrink-0 rounded-full px-2 py-1 text-[11px] font-semibold ${statusStyles[project.status]}`}>{statusLabels[project.status]}</span></div>
                  <p className="mt-2 text-xs text-slate-500 dark:text-slate-400">{project.asset_count} activos · {project.product_count} productos</p>
                  <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">Inicio: {formatDate(project.start_date)}</p>
                </button>
              ))}
            </div>
          )}
        </section>

        <section className="min-w-0 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900">
          {!selected ? (
            <div className="flex min-h-80 flex-col items-center justify-center p-8 text-center"><FolderKanban size={36} className="text-slate-300 dark:text-slate-500" /><h3 className="mt-3 font-semibold">Seleccioná un proyecto</h3><p className="mt-1 max-w-sm text-sm text-slate-500 dark:text-slate-400">Podrás consultar y administrar los recursos asociados y su valor acumulado.</p></div>
          ) : (
            <>
              <div className="flex flex-wrap items-start justify-between gap-3 border-b border-slate-100 dark:border-slate-800 p-5">
                <div className="min-w-0"><span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${statusStyles[selected.status]}`}>{statusLabels[selected.status]}</span><h3 className="mt-3 text-xl font-bold">{selected.name}</h3><p className="mt-1 text-sm text-slate-500 dark:text-slate-400">{selected.description || 'Sin descripción.'}</p><p className="mt-2 flex items-center gap-2 text-xs text-slate-500 dark:text-slate-400"><CalendarDays size={14} />{formatDate(selected.start_date)} — {formatDate(selected.end_date)}</p></div>
                <div className="flex gap-2"><button onClick={() => setForm(selected)} className="rounded-lg border border-slate-300 dark:border-slate-600 px-3 py-2 text-sm font-medium">Editar</button>{canArchive && <button onClick={() => void archive(selected)} className="rounded-lg border border-red-200 dark:border-red-900 px-3 py-2 text-sm font-medium text-red-700 dark:text-red-300"><Archive size={15} /></button>}</div>
              </div>

              <div className="flex gap-4 border-b border-slate-100 dark:border-slate-800 px-5 pt-4 text-sm font-semibold">
                <button type="button" onClick={()=>setProjectTab('resources')} className={`border-b-2 pb-3 ${projectTab==='resources'?'border-blue-600 dark:border-blue-500 text-blue-700 dark:text-blue-300':'border-transparent text-slate-600 dark:text-slate-300'}`}>Recursos permanentes</button>
                <button type="button" onClick={()=>setProjectTab('works')} className={`border-b-2 pb-3 ${projectTab==='works'?'border-blue-600 dark:border-blue-500 text-blue-700 dark:text-blue-300':'border-transparent text-slate-600 dark:text-slate-300'}`}>Trabajos</button>
              </div>
              {projectTab==='works' ? <div className="p-5"><ProjectWorksPanel projectId={selected.id} products={products}/></div> : <>
              <div className="grid gap-3 p-5 sm:grid-cols-3">
                <div className="rounded-lg bg-slate-50 dark:bg-slate-950 p-3"><p className="text-xs text-slate-500 dark:text-slate-400">Activos individuales</p><p className="mt-1 text-xl font-bold">{selected.asset_count}</p></div>
                <div className="rounded-lg bg-slate-50 dark:bg-slate-950 p-3"><p className="text-xs text-slate-500 dark:text-slate-400">Productos por cantidad</p><p className="mt-1 text-xl font-bold">{selected.product_count}</p></div>
                {canViewPrices && <div className="rounded-lg bg-slate-50 dark:bg-slate-950 p-3"><p className="text-xs text-slate-500 dark:text-slate-400">Valor acumulado</p>{Object.keys(selected.valuation_by_currency).length === 0 ? <p className="mt-1 text-sm font-bold">Sin valor registrado</p> : Object.entries(selected.valuation_by_currency).map(([currency, value]) => <p key={currency} className="mt-1 text-lg font-bold">{formatCurrency(value, currency)}</p>)}<p className="mt-1 text-[11px] text-slate-500 dark:text-slate-400">{selected.valuation_complete ? 'Valoración completa' : 'Hay recursos sin valor asignado'} · Importes separados por moneda; sin conversión automática</p></div>}
              </div>

              <div className="space-y-6 px-5 pb-5">
                <section>
                  <div className="mb-3 flex items-center justify-between"><h4 className="font-semibold">Robots y equipos asignados</h4><span className="text-xs text-slate-500 dark:text-slate-400">{activeAssetAssignments.length} vigentes</span></div>
                  <div className="overflow-x-auto rounded-lg border border-slate-200 dark:border-slate-700">
                    <table className="w-full min-w-[620px] text-left text-sm"><thead className="bg-slate-50 dark:bg-slate-950 text-xs text-slate-500 dark:text-slate-400"><tr><th className="px-3 py-3">Activo</th><th className="px-3 py-3">Código interno</th><th className="px-3 py-3">Serie fabricante</th><th className="px-3 py-3">Asignación</th><th className="px-3 py-3" /></tr></thead><tbody>
                      {activeAssetAssignments.map((assignment) => <tr key={assignment.id} className="border-t border-slate-100 dark:border-slate-800"><td className="px-3 py-3">{assignment.asset.product_name || 'Activo sin producto'}</td><td className="px-3 py-3 font-mono text-xs text-blue-700 dark:text-blue-300">{assignment.asset.asset_code}</td><td className="px-3 py-3">{assignment.asset.manufacturer_serial || '—'}</td><td className="px-3 py-3 text-xs">Vigente</td><td className="px-3 py-3"><button onClick={() => void releaseAsset(assignment.id)} className="text-xs font-semibold text-red-700 dark:text-red-300">Retirar</button></td></tr>)}
                    </tbody></table>
                    {activeAssetAssignments.length === 0 && <p className="p-4 text-sm text-slate-500 dark:text-slate-400">No hay activos asignados.</p>}
                  </div>
                </section>

                <section>
                  <div className="mb-3 flex items-center justify-between"><h4 className="font-semibold">Materiales y productos asignados</h4><span className="text-xs text-slate-500 dark:text-slate-400">{activeProductAssignments.length} vigentes</span></div>
                  <div className="overflow-x-auto rounded-lg border border-slate-200 dark:border-slate-700">
                    <table className="w-full min-w-[560px] text-left text-sm"><thead className="bg-slate-50 dark:bg-slate-950 text-xs text-slate-500 dark:text-slate-400"><tr><th className="px-3 py-3">Producto</th><th className="px-3 py-3">Cantidad</th>{canViewPrices && <th className="px-3 py-3">Valor unitario</th>}<th className="px-3 py-3">Asignación</th><th className="px-3 py-3" /></tr></thead><tbody>
                      {activeProductAssignments.map((assignment) => <tr key={assignment.id} className="border-t border-slate-100 dark:border-slate-800"><td className="px-3 py-3">{assignment.product_name || `Producto #${assignment.product_id}`}</td><td className="px-3 py-3">{assignment.quantity}</td>{canViewPrices && <td className="px-3 py-3">{assignment.unit_value == null ? '—' : formatCurrency(assignment.unit_value, assignment.value_currency)}</td>}<td className="px-3 py-3 text-xs">Vigente</td><td className="px-3 py-3"><button onClick={() => void releaseProduct(assignment.id)} className="text-xs font-semibold text-red-700 dark:text-red-300">Retirar</button></td></tr>)}
                    </tbody></table>
                    {activeProductAssignments.length === 0 && <p className="p-4 text-sm text-slate-500 dark:text-slate-400">No hay productos asignados.</p>}
                  </div>
                </section>

                {canAssign && (
                  <section className="grid gap-4 md:grid-cols-2">
                    <form onSubmit={addAssets} className="min-w-0 space-y-3 rounded-xl border border-slate-200 dark:border-slate-700 p-4">
                      <h4 className="font-semibold">Asignar activos individuales</h4>
                      <div className="flex items-center gap-2 rounded-lg border border-slate-300 dark:border-slate-600 px-3 py-2">
                        <Search size={16} className="text-slate-400 dark:text-slate-400" />
                        <input aria-label="Buscar activos" value={assetSearch} onChange={e => setAssetSearch(e.target.value)} placeholder="Buscar robot, equipo, o serie" className="w-full min-w-0 text-sm outline-none" />
                      </div>
                      <div className="max-h-60 space-y-1 overflow-y-auto rounded-lg border border-slate-200 dark:border-slate-700 p-2">
                        {filteredAssets.slice(0, 70).map(a => (
                          <label key={a.id} className="flex cursor-pointer items-start gap-2 rounded-md p-2 hover:bg-slate-50 dark:hover:bg-slate-800">
                            <input type="checkbox" checked={selectedAssetIds.includes(a.id)} onChange={e => toggleAsset(a.id, e.target.checked)} className="mt-1 accent-blue-700" />
                            <span className="min-w-0 text-sm"><span className="block font-medium">{a.product_name || 'Activo sin producto'}</span><span className="block text-xs text-slate-500 dark:text-slate-400">{a.asset_code} · {a.manufacturer_serial || 'Sin serie'}</span></span>
                          </label>
                        ))}
                        {filteredAssets.length === 0 && <p className="p-3 text-sm text-slate-500 dark:text-slate-400">No hay activos disponibles.</p>}
                        {filteredAssets.length > 70 && <p className="p-2 text-xs text-slate-500 dark:text-slate-400">Mostrando 70 resultados; afiná la búsqueda para ver otros.</p>}
                      </div>
                      <p className="text-xs text-slate-500 dark:text-slate-400">{selectedAssetIds.length} activos seleccionados</p>
                      <button disabled={!selectedAssetIds.length || busy} className="w-full rounded-lg bg-blue-700 dark:bg-blue-600 px-3 py-2.5 text-sm font-semibold text-white disabled:opacity-40">{busy ? 'Asignando...' : `Asignar ${selectedAssetIds.length} activos`}</button>
                    </form>
                    <form onSubmit={addProducts} className="min-w-0 space-y-3 rounded-xl border border-slate-200 dark:border-slate-700 p-4">
                      <h4 className="font-semibold">Asignar artículos por cantidad</h4>
                      <div className="flex items-center gap-2 rounded-lg border border-slate-300 dark:border-slate-600 px-3 py-2">
                        <Search size={16} className="text-slate-400 dark:text-slate-400" />
                        <input aria-label="Buscar artículos" value={productSearch} onChange={e => setProductSearch(e.target.value)} placeholder="Buscar nombre, marca o modelo" className="w-full min-w-0 text-sm outline-none" />
                      </div>
                      <div className="max-h-60 space-y-2 overflow-y-auto rounded-lg border border-slate-200 dark:border-slate-700 p-2">
                        {filteredProducts.slice(0, 70).map(p => {
                          const selectedProduct = Object.hasOwn(selectedProductQuantities, p.id);
                          return (
                            <div key={p.id} className="rounded-md p-2 hover:bg-slate-50 dark:hover:bg-slate-800">
                              <label className="flex cursor-pointer items-center gap-2 text-sm">
                                <input type="checkbox" checked={selectedProduct} onChange={e => toggleProduct(p.id, e.target.checked)} className="accent-blue-700" />
                                <span className="min-w-0 truncate font-medium" title={[p.name,p.brand,p.model].filter(Boolean).join(' · ')}>{p.name || `Artículo #${p.id}`}</span>
                              </label>
                              {selectedProduct && (
                                <div className="mt-2 flex items-center gap-1 pl-6">
                                  <button type="button" title="Disminuir" aria-label={`Disminuir cantidad de ${p.name}`} onClick={() => incrementQuantity(p.id, -1)} className="rounded-lg border border-slate-300 dark:border-slate-600 p-2 hover:bg-slate-100 dark:hover:bg-slate-800"><Minus size={14} /></button>
                                  <input aria-label={`Cantidad de ${p.name}`} type="number" min="0.001" step="0.001" value={selectedProductQuantities[p.id]} onChange={e => changeQuantity(p.id, e.target.value)} className="w-full min-w-0 rounded-lg border border-slate-300 dark:border-slate-600 px-2 py-1.5 text-center text-sm" />
                                  <button type="button" title="Aumentar" aria-label={`Aumentar cantidad de ${p.name}`} onClick={() => incrementQuantity(p.id, 1)} className="rounded-lg border border-slate-300 dark:border-slate-600 p-2 hover:bg-slate-100 dark:hover:bg-slate-800"><Plus size={14} /></button>
                                </div>
                              )}
                            </div>
                          );
                        })}
                        {filteredProducts.length === 0 && <p className="p-3 text-sm text-slate-500 dark:text-slate-400">No hay artículos disponibles para asignar.</p>}
                        {filteredProducts.length > 70 && <p className="p-2 text-xs text-slate-500 dark:text-slate-400">Mostrando 70 resultados; afiná la búsqueda para ver otros.</p>}
                      </div>
                      <p className="text-xs text-slate-500 dark:text-slate-400">{Object.keys(selectedProductQuantities).length} artículos seleccionados</p>
                      <button disabled={!Object.keys(selectedProductQuantities).length || busy} className="w-full rounded-lg bg-slate-900 dark:bg-slate-700 px-3 py-2.5 text-sm font-semibold text-white disabled:opacity-40">{busy ? 'Asignando...' : `Asignar ${Object.keys(selectedProductQuantities).length} artículos`}</button>
                      <p className="text-xs text-slate-500 dark:text-slate-400">Esta asignación administrativa no modifica las existencias físicas. Las salidas del almacén se registrarán en el módulo de Trabajos.</p>
                    </form>
                  </section>
                )}
              </div>
              </>}
            </>
          )}
        </section>
      </div>

      {form !== undefined && <ProjectForm project={form} onClose={() => setForm(undefined)} onSave={saveProject} />}
    </div>
  );
}
