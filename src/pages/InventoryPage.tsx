import { useCallback, useMemo, useState } from 'react';
import { Archive, Plus, Search, SlidersHorizontal, X } from 'lucide-react';
import InventoryTable from '../components/inventory/InventoryTable';
import InventoryDetailDrawer from '../components/inventory/InventoryDetailDrawer';
import ProductFormModal from '../components/inventory/ProductFormModal';
import AssetFormModal from '../components/inventory/AssetFormModal';
import AssetDetailDrawer from '../components/inventory/AssetDetailDrawer';
import StockMovementModal from '../components/inventory/StockMovementModal';
import {
  archivarActivo,
  archivarProducto,
  actualizarActivo,
  actualizarProducto,
  crearActivo,
  crearAsociacion,
  crearProducto,
  finalizarAsociacion,
  obtenerActivo,
  obtenerActivos,
  obtenerCategorias,
  obtenerProductos,
  obtenerTipos,
  obtenerUbicaciones,
  registrarMovimiento,
  obtenerResumenEnTrabajos,
} from '../services/inventoryService';
import { normalized, rankMatch } from '../utils/catalogSearch';
import { useAuth } from '../auth/useAuth';
import type {
  Activo,
  ActivoDetalle,
  ActivoPayload,
  Categoria,
  Producto,
  ProductoPayload,
  TipoComponente,
  Ubicacion,
  ResumenEnTrabajos,
} from '../types/inventory';

import { useLoadEffect } from '../hooks/useLoadEffect';
type Tab = 'products' | 'assets';

export default function InventoryPage() {
  const { canViewPrices, canArchive } = useAuth();
  const [tab, setTab] = useState<Tab>('products');
  const [productos, setProductos] = useState<Producto[]>([]);
  const [activos, setActivos] = useState<Activo[]>([]);
  const [enTrabajos, setEnTrabajos] = useState<ResumenEnTrabajos>({products:{},assets:{}});
  const [categorias, setCategorias] = useState<Categoria[]>([]);
  const [tipos, setTipos] = useState<TipoComponente[]>([]);
  const [ubicaciones, setUbicaciones] = useState<Ubicacion[]>([]);
  const [busqueda, setBusqueda] = useState('');
  const [categoria, setCategoria] = useState('all');
  const [tipo, setTipo] = useState('all');
  const [seleccionado, setSeleccionado] = useState<Producto | null>(null);
  const [activoSeleccionado, setActivoSeleccionado] = useState<ActivoDetalle | null>(null);
  const [formularioProducto, setFormularioProducto] = useState<Producto | null | undefined>(undefined);
  const [formularioActivo, setFormularioActivo] = useState<ActivoDetalle | null | undefined>(undefined);
  const [productoInicialActivo, setProductoInicialActivo] = useState<number | null>(null);
  const [movimiento, setMovimiento] = useState<Producto | null>(null);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState('');

  const cargar = useCallback(async () => {
    setCargando(true);
    setError('');
    try {
      const [products, assets, cats, types, locs, workRows] = await Promise.all([
        obtenerProductos(),
        obtenerActivos({ include_non_stock: true }),
        obtenerCategorias(),
        obtenerTipos(),
        obtenerUbicaciones(),
        // La consulta auxiliar no debe bloquear todo el inventario si falla.
        obtenerResumenEnTrabajos().catch((): ResumenEnTrabajos => ({ products: {}, assets: {} })),
      ]);
      setEnTrabajos(workRows);
      setProductos(products);
      setActivos(assets);
      setCategorias(cats);
      setTipos(types);
      setUbicaciones(locs);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'No se pudo cargar el inventario.');
    } finally {
      setCargando(false);
    }
  }, []);

  useLoadEffect(cargar);

  const tiposFiltrables = useMemo(() => {
    const ids = new Set(productos
      .filter(p => categoria === 'all' || String(p.category_id ?? '') === categoria)
      .map(p => p.component_type_id));
    return tipos.filter(t => ids.has(t.id));
  }, [productos, tipos, categoria]);

  const matchCategoryAndType = (product: Producto | undefined) =>
    (categoria === 'all' || String(product?.category_id ?? '') === categoria) &&
    (tipo === 'all' || String(product?.component_type_id ?? '') === tipo);

  const productScore = (p: Producto) => rankMatch(busqueda, [
    { value: p.model, weight: 90 },
    { value: p.name, weight: 80 },
    { value: p.brand, weight: 60 },
    { value: p.asset_code_prefix, weight: 55 },
    { value: p.component_type_name, weight: 30 },
    { value: p.category_name, weight: 15 },
    ...((p.search_aliases ?? []).map(value => ({ value, weight: 35 }))),
    { value: p.description, weight: 10 },
  ]);

  const productosFiltrados = useMemo(() => productos
    .filter(p => matchCategoryAndType(p) && productScore(p) >= 0)
    .sort((a,b) => productScore(b) - productScore(a) || (a.name ?? '').localeCompare(b.name ?? '', 'es')),
  // eslint-disable-next-line react-hooks/exhaustive-deps
  [productos, categoria, tipo, busqueda]);

  const activosFiltrados = useMemo(() => {
    const porProducto = new Map<number, Producto>(productos.map(p => [p.id, p]));
    return activos
      .filter(a => matchCategoryAndType(porProducto.get(a.product_id ?? -1)))
      .map(a => {
        const p = porProducto.get(a.product_id ?? -1);
        const score = rankMatch(busqueda, [
          { value: a.asset_code, weight: 100 },
          { value: a.manufacturer_serial, weight: 100 },
          { value: a.product_model, weight: 85 },
          { value: a.product_name, weight: 80 },
          { value: a.product_brand ?? a.manufacturer_brand, weight: 60 },
          { value: a.location_name, weight: 15 },
          ...((p?.search_aliases ?? []).map(value => ({ value, weight: 35 }))),
        ]);
        return { asset: a, score };
      })
      .filter(x => x.score >= 0)
      .sort((a,b) => b.score - a.score || normalized(a.asset.asset_code).localeCompare(normalized(b.asset.asset_code)))
      .map(x => x.asset);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activos, productos, categoria, tipo, busqueda]);

  async function guardarProducto(payload: ProductoPayload) {
    if (formularioProducto) await actualizarProducto(formularioProducto.id, payload);
    else await crearProducto(payload);
    setFormularioProducto(undefined);
    await cargar();
  }

  async function guardarActivo(payload: ActivoPayload & { asset_code_prefix?: string | null }) {
    if (formularioActivo) await actualizarActivo(formularioActivo.id, payload);
    else await crearActivo(payload);
    setFormularioActivo(undefined);
    setProductoInicialActivo(null);
    await cargar();
  }

  async function abrirDetalleActivo(id: number) {
    try {
      setError('');
      const detail = await obtenerActivo(id);
      setActivoSeleccionado(detail);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'No se pudo cargar el activo.');
    }
  }

  async function archivarProductoSeleccionado(producto: Producto) {
    if (!window.confirm(`¿Archivar "${producto.name || `artículo #${producto.id}`} "? Se conservarán sus datos e historial.`)) return;
    try {
      await archivarProducto(producto.id);
      setSeleccionado(null);
      await cargar();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'No se pudo archivar el artículo.');
    }
  }

  async function archivarActivoSeleccionado(activo: ActivoDetalle) {
    if (!window.confirm(`¿Archivar el activo ${activo.asset_code}? El registro y su historial se conservarán.`)) return;
    try {
      await archivarActivo(activo.id);
      setActivoSeleccionado(null);
      await cargar();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'No se pudo archivar el activo.');
    }
  }

  async function guardarMovimiento(data: {
    location_id: number | null;
    movement_type: 'entry' | 'exit' | 'count';
    quantity: number;
    note: string | null;
  }) {
    if (!movimiento) return;
    await registrarMovimiento(movimiento.id, data);
    setMovimiento(null);
    await cargar();
  }

  async function agregarAsociacion(targetId: number, role: string) {
    if (!activoSeleccionado) return;
    await crearAsociacion(activoSeleccionado.id, {
      target_asset_id: targetId,
      relationship_type: role,
      note: null,
    });
    await abrirDetalleActivo(activoSeleccionado.id);
    await cargar();
  }

  async function terminarAsociacion(relationshipId: number) {
    if (!activoSeleccionado) return;
    await finalizarAsociacion(activoSeleccionado.id, relationshipId);
    await abrirDetalleActivo(activoSeleccionado.id);
    await cargar();
  }

  const ubicacionLabel = (a: Activo) => a.location_name || 'Sin ubicación';
  const fmtMoney = (value: number | null, currency: string) =>
    value == null ? '—' : `${new Intl.NumberFormat('es-PY').format(value)} ${currency}`;

  return (
    <div className="mx-auto max-w-7xl space-y-6 p-4 md:p-7">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <h1 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-slate-100">Inventario general</h1>
        <div className="flex flex-wrap gap-2">
          <button onClick={() => { setProductoInicialActivo(null); setFormularioActivo(null); }} className="inline-flex items-center gap-2 rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-900 px-4 py-2.5 text-sm font-semibold text-slate-700 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-slate-800"><Plus size={17} />Nueva unidad</button>
          <button onClick={() => setFormularioProducto(null)} className="inline-flex items-center gap-2 rounded-lg bg-blue-700 dark:bg-blue-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-blue-800"><Plus size={17} />Nuevo artículo</button>
        </div>
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        <div className="rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 p-4"><p className="text-xs font-medium text-slate-500 dark:text-slate-400">Artículos en catálogo</p><p className="mt-2 text-2xl font-bold">{productos.length}</p></div>
        <div className="rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 p-4"><p className="text-xs font-medium text-slate-500 dark:text-slate-400">Unidades físicas activas</p><p className="mt-2 text-2xl font-bold">{activos.length}</p></div>
      </div>

      {error && <div className="flex items-start justify-between gap-3 rounded-lg border border-red-200 dark:border-red-900 bg-red-50 dark:bg-red-950/60 px-4 py-3 text-sm text-red-700 dark:text-red-300"><span>{error}</span><button onClick={() => void cargar()} className="shrink-0 font-semibold underline">Reintentar</button></div>}

      <section className="overflow-hidden rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900">
        <div className="flex flex-wrap items-center gap-3 border-b border-slate-100 dark:border-slate-800 p-4">
          <div className="flex min-w-56 flex-1 items-center gap-3 rounded-lg border border-slate-200 dark:border-slate-700 px-3 py-2.5 focus-within:border-blue-500">
            <Search size={18} className="shrink-0 text-slate-400 dark:text-slate-400" />
            <input value={busqueda} onChange={(e) => setBusqueda(e.target.value)} placeholder="Buscar por nombre, marca, modelo, código o serie..." className="w-full min-w-0 bg-transparent text-sm outline-none" />
            {busqueda && <button type="button" aria-label="Limpiar búsqueda" onClick={() => setBusqueda('')} className="text-slate-400 dark:text-slate-400"><X size={16} /></button>}
          </div>
          <div className="flex items-center gap-2 rounded-lg border border-slate-200 dark:border-slate-700 px-3 py-2.5">
            <SlidersHorizontal size={16} className="text-slate-400 dark:text-slate-400" />
            <select aria-label="Filtrar por categoría" value={categoria} onChange={(e) => { setCategoria(e.target.value); setTipo('all'); }} className="bg-transparent text-sm outline-none">
              <option value="all">Todas las categorías</option>
              {categorias.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
          </div>
          <div className="rounded-lg border border-slate-200 dark:border-slate-700 px-3 py-2.5">
            <select aria-label="Filtrar por tipo de componente" value={tipo} onChange={(e) => setTipo(e.target.value)} className="max-w-[250px] bg-transparent text-sm outline-none">
              <option value="all">Todos los tipos</option>
              {tiposFiltrables.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
            </select>
          </div>
        </div>

        <div className="flex items-center gap-1 border-b border-slate-100 dark:border-slate-800 px-4">
          <button onClick={() => setTab('products')} className={`border-b-2 px-4 py-3 text-sm font-semibold ${tab === 'products' ? 'border-blue-700 dark:border-blue-600 text-blue-700 dark:text-blue-300' : 'border-transparent text-slate-500 dark:text-slate-400'}`}>Catálogo ({productos.length})</button>
          <button onClick={() => setTab('assets')} className={`border-b-2 px-4 py-3 text-sm font-semibold ${tab === 'assets' ? 'border-blue-700 dark:border-blue-600 text-blue-700 dark:text-blue-300' : 'border-transparent text-slate-500 dark:text-slate-400'}`}>Unidades físicas ({activos.length})</button>
        </div>

        <div className="flex justify-end px-5 py-3">
          <span className="text-xs text-slate-500 dark:text-slate-400">{cargando ? 'Cargando...' : `${tab === 'products' ? productosFiltrados.length : activosFiltrados.length} resultados`}</span>
        </div>

        {cargando ? <div className="p-12 text-center text-sm text-slate-500 dark:text-slate-400">Conectando con la base de datos...</div> : tab === 'products' ? (
          <InventoryTable articulos={productosFiltrados} enTrabajos={enTrabajos} onSelect={setSeleccionado} />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[900px] text-left text-sm">
              <thead className="bg-slate-50 dark:bg-slate-950 text-xs text-slate-500 dark:text-slate-400">
                <tr><th className="px-5 py-3 font-medium">Código interno</th><th className="px-5 py-3 font-medium">Artículo / Modelo</th><th className="px-5 py-3 font-medium">Serie fabricante</th><th className="px-5 py-3 font-medium">Ubicación</th><th className="px-5 py-3 font-medium">Estado</th>{canViewPrices && <th className="px-5 py-3 font-medium">Valor</th>}<th className="px-5 py-3" /></tr>
              </thead>
              <tbody>
                {activosFiltrados.map((a) => (
                  <tr key={a.id} className="border-t border-slate-100 dark:border-slate-800 hover:bg-blue-50/40">
                    <td className="px-5 py-4 font-mono text-xs font-semibold text-blue-700 dark:text-blue-300">{a.asset_code}</td>
                    <td className="px-5 py-4"><p className="font-semibold">{a.product_name || 'Activo sin producto asociado'}</p><p className="mt-1 text-xs text-slate-500 dark:text-slate-400">{[a.product_brand || a.manufacturer_brand, a.product_model].filter(Boolean).join(' · ') || 'Sin marca / modelo'}</p></td>
                    <td className="px-5 py-4 text-slate-600 dark:text-slate-300">{a.manufacturer_serial || '—'}</td>
                    <td className="px-5 py-4 text-slate-600 dark:text-slate-300">{ubicacionLabel(a)}</td>
                    <td className="px-5 py-4"><span className={`rounded-md px-2 py-1 text-xs font-medium ${a.functional_status === 'functional' ? 'bg-emerald-50 dark:bg-emerald-950/60 text-emerald-700 dark:text-emerald-300' : 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300'}`}>{a.functional_status === 'functional' ? 'Operativo' : a.functional_status === 'unverified' ? 'Sin verificar' : a.functional_status === 'damaged' ? 'Dañado' : a.functional_status === 'under_repair' ? 'En reparación' : 'Fuera de servicio'}</span></td>
                    {canViewPrices && <td className="px-5 py-4 text-slate-600 dark:text-slate-300">{fmtMoney(a.estimated_value, a.value_currency)}</td>}
                    <td className="px-5 py-4"><button type="button" onClick={() => void abrirDetalleActivo(a.id)} className="rounded-lg px-3 py-2 text-xs font-semibold text-blue-700 dark:text-blue-300 hover:bg-blue-50 dark:hover:bg-blue-950">Ver ficha</button></td>
                  </tr>
                ))}
              </tbody>
            </table>
            {activosFiltrados.length === 0 && <div className="p-12 text-center text-sm text-slate-500 dark:text-slate-400"><Archive className="mx-auto mb-2 text-slate-300 dark:text-slate-500" size={24} />No hay unidades registradas con esos criterios.</div>}
          </div>
        )}
      </section>

      <InventoryDetailDrawer
        producto={seleccionado}
        onClose={() => setSeleccionado(null)}
        onEdit={(p) => { setSeleccionado(null); setFormularioProducto(p); }}
        onAddAsset={(p) => { setSeleccionado(null); setProductoInicialActivo(p.id); setFormularioActivo(null); }}
        onStock={(p) => { setSeleccionado(null); setMovimiento(p); }}
        onArchive={(p) => { if (canArchive) void archivarProductoSeleccionado(p); }}
      />

      <AssetDetailDrawer
        activo={activoSeleccionado}
        activosDisponibles={activos}
        productos={productos}
        onClose={() => setActivoSeleccionado(null)}
        onEdit={(a) => { setActivoSeleccionado(null); setFormularioActivo(a); }}
        onArchive={(a) => { if (canArchive) void archivarActivoSeleccionado(a); }}
        onAddRelationship={agregarAsociacion}
        onEndRelationship={terminarAsociacion}
      />

      {formularioProducto !== undefined && (
        <ProductFormModal
          producto={formularioProducto}
          categorias={categorias}
          tipos={tipos}
          onClose={() => setFormularioProducto(undefined)}
          onSave={guardarProducto}
        />
      )}

      {formularioActivo !== undefined && (
        <AssetFormModal
          activo={formularioActivo}
          productos={productos}
          ubicaciones={ubicaciones}
          initialProductId={productoInicialActivo}
          onClose={() => { setFormularioActivo(undefined); setProductoInicialActivo(null); }}
          onSave={guardarActivo}
        />
      )}

      {movimiento && (
        <StockMovementModal
          articulo={movimiento}
          ubicaciones={ubicaciones}
          onClose={() => setMovimiento(null)}
          onSave={guardarMovimiento}
        />
      )}
    </div>
  );
}
