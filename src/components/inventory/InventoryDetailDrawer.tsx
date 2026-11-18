import { useState } from 'react';
import { Archive, Boxes, MapPin, Pencil, Plus, X } from 'lucide-react';
import { useAuth } from '../../auth/useAuth';
import { obtenerExistenciasProducto } from '../../services/inventoryService';
import type { Producto } from '../../types/inventory';

type UbicacionResumen = { clave: string; nombre: string; padre: string | null; cantidad: number };
type EstadoUbicaciones = { productId: number; filas: UbicacionResumen[] | null; error: string };

/** Agrupa las unidades individuales por ubicación. */
function ubicacionesDeUnidades(producto: Producto): UbicacionResumen[] {
  const conteo = new Map<string, number>();
  for (const asset of producto.assets) {
    const nombre = asset.location_name || 'Sin ubicación';
    conteo.set(nombre, (conteo.get(nombre) ?? 0) + 1);
  }
  return [...conteo].map(([nombre, cantidad]) => ({ clave: nombre, nombre, padre: null, cantidad }));
}

type Props = {
  producto: Producto | null;
  onClose: () => void;
  onEdit: (producto: Producto) => void;
  onAddAsset: (producto: Producto) => void;
  onStock: (producto: Producto) => void;
  onArchive: (producto: Producto) => void;
};

const money = (value: number | null, currency: string) =>
  value == null ? 'Sin valor registrado' : new Intl.NumberFormat('es-PY', {
    style: 'currency',
    currency,
    minimumFractionDigits: currency === 'USD' ? 2 : 0,
    maximumFractionDigits: currency === 'USD' ? 2 : 0,
  }).format(value);

export default function InventoryDetailDrawer({
  producto, onClose, onEdit, onAddAsset, onStock, onArchive,
}: Props) {
  const { canViewPrices, canArchive } = useAuth();
  const [ubicaciones, setUbicaciones] = useState<EstadoUbicaciones | null>(null);
  if (!producto) return null;
  const title = producto.name || `Artículo sin nombre #${producto.id}`;
  const individual = producto.tracking_mode === 'individual';
  // Solo se muestran si pertenecen al artículo abierto (al cambiar de artículo se ocultan).
  const ubicacionesVisibles = ubicaciones?.productId === producto.id ? ubicaciones : null;
  const tieneExistencias = individual ? producto.assets.length > 0 : producto.stock_verified && Number(producto.total_stock ?? 0) > 0;

  const toggleUbicaciones = async () => {
    if (ubicacionesVisibles) { setUbicaciones(null); return; }
    const productId = producto.id;
    if (individual) { setUbicaciones({ productId, filas: ubicacionesDeUnidades(producto), error: '' }); return; }
    setUbicaciones({ productId, filas: null, error: '' });
    // Si mientras tanto se cerró la lista o se cambió de artículo, la respuesta se descarta.
    const aplicar = (cambio: Omit<EstadoUbicaciones, 'productId'>) =>
      setUbicaciones(prev => prev?.productId === productId ? { productId, ...cambio } : prev);
    try {
      const filas = (await obtenerExistenciasProducto(productId))
        .filter(row => Number(row.quantity) > 0)
        .map(row => ({ clave: String(row.location_id ?? 'sin'), nombre: row.location_name || 'Sin ubicación', padre: row.parent_name, cantidad: Number(row.quantity) }));
      aplicar({ filas, error: '' });
    } catch (error) {
      aplicar({ filas: [], error: error instanceof Error ? error.message : 'No se pudieron cargar las ubicaciones.' });
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-slate-950/40">
      <button type="button" className="absolute inset-0 cursor-pointer" aria-label="Cerrar detalle" onClick={onClose} />
      <aside role="dialog" aria-modal="true" aria-label={`Ficha de ${title}`} className="relative z-10 h-full w-full max-w-xl overflow-y-auto bg-white dark:bg-slate-900 p-6 shadow-xl sm:p-8">
        <div className="flex justify-end">
          <button type="button" onClick={onClose} className="rounded-lg p-2 hover:bg-slate-100 dark:hover:bg-slate-800" aria-label="Cerrar"><X size={20} /></button>
        </div>
        <h2 className="mt-5 text-2xl font-bold text-slate-900 dark:text-slate-100">{title}</h2>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">{[producto.brand, producto.model].filter(Boolean).join(' · ') || 'Marca y modelo no especificados'}</p>

        <div className="mt-6 flex flex-wrap gap-2">
          <button onClick={() => onEdit(producto)} className="inline-flex items-center gap-2 rounded-lg bg-blue-700 dark:bg-blue-600 px-3 py-2 text-sm font-semibold text-white"><Pencil size={15} />Editar</button>
          {producto.tracking_mode === 'individual' ? (
            <button onClick={() => onAddAsset(producto)} className="inline-flex items-center gap-2 rounded-lg border border-slate-300 dark:border-slate-600 px-3 py-2 text-sm font-medium"><Plus size={15} />Agregar unidad</button>
          ) : (
            <button onClick={() => onStock(producto)} className="inline-flex items-center gap-2 rounded-lg border border-slate-300 dark:border-slate-600 px-3 py-2 text-sm font-medium"><Boxes size={15} />Actualizar existencias</button>
          )}
          {canArchive && <button onClick={() => onArchive(producto)} className="inline-flex items-center gap-2 rounded-lg border border-red-200 dark:border-red-900 px-3 py-2 text-sm font-medium text-red-700 dark:text-red-300"><Archive size={15} />Archivar</button>}
        </div>

        <div className="mt-7 grid grid-cols-2 gap-3">
          <div className="rounded-xl bg-slate-50 dark:bg-slate-950 p-4"><p className="text-xs text-slate-500 dark:text-slate-400">Seguimiento</p><p className="mt-2 text-sm font-bold">{producto.tracking_mode === 'individual' ? 'Por unidad' : 'Por cantidad'}</p></div>
          <div className="rounded-xl bg-slate-50 dark:bg-slate-950 p-4"><p className="text-xs text-slate-500 dark:text-slate-400">{producto.tracking_mode === 'individual' ? 'Unidades registradas' : 'Existencias verificadas'}</p><p className="mt-2 text-xl font-bold">{producto.tracking_mode === 'individual' ? producto.assets.length : producto.stock_verified ? `${Number(producto.total_stock ?? 0)} uds.` : 'Pendiente'}</p>
            {tieneExistencias && (
              <button type="button" onClick={() => void toggleUbicaciones()} aria-expanded={!!ubicacionesVisibles} className="mt-2 inline-flex items-center gap-1 text-xs font-medium text-blue-700 hover:underline dark:text-blue-400">
                <MapPin size={13} />{ubicacionesVisibles ? 'Ocultar ubicaciones' : 'Ver ubicaciones'}
              </button>
            )}
          </div>
        </div>

        {ubicacionesVisibles && (
          <div className="mt-3 rounded-xl border border-slate-200 p-4 text-sm dark:border-slate-700">
            {ubicacionesVisibles.filas === null ? <p className="text-slate-500 dark:text-slate-400">Cargando ubicaciones…</p>
              : ubicacionesVisibles.error ? <p className="text-red-700 dark:text-red-300">{ubicacionesVisibles.error}</p>
              : ubicacionesVisibles.filas.length === 0 ? <p className="text-slate-500 dark:text-slate-400">No hay existencias en ninguna ubicación.</p>
              : (
                <ul className="divide-y divide-slate-100 dark:divide-slate-800">
                  {ubicacionesVisibles.filas.map(fila => (
                    <li key={fila.clave} className="flex items-center justify-between gap-4 py-2">
                      <span className="flex items-center gap-2"><MapPin size={14} className="shrink-0 text-slate-400" /><span className="font-medium">{fila.nombre}</span>{fila.padre && <span className="text-xs text-slate-500 dark:text-slate-400">{fila.padre}</span>}</span>
                      <span className="font-semibold tabular-nums">{fila.cantidad} uds.</span>
                    </li>
                  ))}
                </ul>
              )}
          </div>
        )}

        <section className="mt-7">
          <h3 className="font-bold">Clasificación y datos técnicos</h3>
          <div className="mt-3 divide-y divide-slate-100 dark:divide-slate-800 text-sm">
            {[
              ['Descripción', producto.description || '—'],
              ['Categoría', producto.category_name || 'Sin clasificar'],
              ['Tipo de componente', producto.component_type_name || 'Sin asignar'],
              ['Marca', producto.brand || '—'],
              ['Modelo', producto.model || '—'],
              ['Prefijo de código', producto.asset_code_prefix || '—'],
              ...(canViewPrices ? [['Valor unitario', money(producto.unit_value, producto.value_currency)]] : []),
              ['Registros de origen', String(producto.source_count)],
            ].map(([label, value]) => <div key={label} className="flex justify-between gap-4 py-3"><span className="text-slate-500 dark:text-slate-400">{label}</span><span className="max-w-[65%] text-right font-medium text-slate-800 dark:text-slate-200">{value}</span></div>)}
          </div>
        </section>

        {producto.attributes.length > 0 && (
          <section className="mt-7">
            <h3 className="font-bold">Características técnicas</h3>
            <div className="mt-3 divide-y divide-slate-100 dark:divide-slate-800 text-sm">
              {producto.attributes.map((a) => <div key={a.definition_id} className="flex justify-between gap-4 py-3"><span className="text-slate-500 dark:text-slate-400">{a.name}</span><span className="font-medium">{a.value}{a.unit ? ` ${a.unit}` : ''}</span></div>)}
            </div>
          </section>
        )}

        {producto.tracking_mode === 'individual' && (
          <section className="mt-7">
            <div className="flex items-center justify-between gap-3">
              <h3 className="font-bold">Unidades físicas</h3>
              <span className="text-xs text-slate-500 dark:text-slate-400">{producto.assets.length} registradas</span>
            </div>
            {producto.assets.length === 0 ? <p className="mt-3 rounded-lg bg-slate-50 dark:bg-slate-950 p-4 text-sm text-slate-500 dark:text-slate-400">Todavía no hay unidades registradas para este modelo.</p> : (
              <div className="mt-3 space-y-2">
                {producto.assets.map((asset) => (
                  <div key={asset.id} className="rounded-lg border border-slate-200 dark:border-slate-700 p-3">
                    <div className="flex items-center justify-between gap-3"><p className="font-semibold">{asset.asset_code}</p><span className="text-xs text-slate-500 dark:text-slate-400">{asset.project_names?.length ? `Proyecto: ${asset.project_names.join(', ')}` : 'Sin proyectos asignados'}</span></div>
                    <p className="mt-1 text-xs text-slate-600 dark:text-slate-300">Serie fabricante: {asset.manufacturer_serial || 'No registrada'}</p>
                    <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">Ubicación: {asset.location_name || 'Sin ubicación'}</p>
                  </div>
                ))}
              </div>
            )}
          </section>
        )}

        <p className="mt-8 rounded-lg bg-slate-50 dark:bg-slate-950 p-3 text-xs leading-5 text-slate-500 dark:text-slate-400">Archivar no elimina físicamente el registro. Se conserva el historial y el código interno de las unidades.</p>
      </aside>
    </div>
  );
}
