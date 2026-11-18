import { useEffect, useMemo, useState, type FormEvent } from 'react';
import { X } from 'lucide-react';
import { useAuth } from '../../auth/useAuth';
import type {
  Categoria,
  DefinicionCaracteristica,
  Producto,
  ProductoPayload,
  TipoComponente,
  TrackingMode,
} from '../../types/inventory';
import { obtenerCaracteristicas } from '../../services/inventoryService';

type Props = {
  producto: Producto | null;
  categorias: Categoria[];
  tipos: TipoComponente[];
  onClose: () => void;
  onSave: (payload: ProductoPayload) => Promise<void>;
};

const inputClass = 'w-full rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-900 px-3 py-2.5 text-sm outline-none transition focus:border-blue-500 dark:focus:border-blue-400 focus:ring-2 focus:ring-blue-100 dark:focus:ring-blue-950';

export default function ProductFormModal({ producto, categorias, tipos, onClose, onSave }: Props) {
  const [nombre, setNombre] = useState(producto?.name ?? '');
  const [descripcion, setDescripcion] = useState(producto?.description ?? '');
  const [marca, setMarca] = useState(producto?.brand ?? '');
  const [modelo, setModelo] = useState(producto?.model ?? '');
  const [categoriaId, setCategoriaId] = useState(producto?.category_id ? String(producto.category_id) : '');
  const [tipoId, setTipoId] = useState(producto?.component_type_id ? String(producto.component_type_id) : '');
  const [trackingMode, setTrackingMode] = useState<TrackingMode>(producto?.tracking_mode ?? 'quantity');
  const [prefix, setPrefix] = useState(producto?.asset_code_prefix ?? '');
  const { canViewPrices, canEditPrices } = useAuth();
  const [unitValue, setUnitValue] = useState(producto?.unit_value == null ? '' : String(producto.unit_value));
  const [currency, setCurrency] = useState(producto?.value_currency ?? 'PYG');
  const [definiciones, setDefiniciones] = useState<DefinicionCaracteristica[]>([]);
  const [valores, setValores] = useState<Record<number, string>>({});
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState('');

  const definicionesActivas = tipoId ? definiciones : [];
  const tipoActual = useMemo(() => tipos.find((t) => t.id === Number(tipoId)), [tipos, tipoId]);

  useEffect(() => {
    if (!tipoId) return;
    let vigente = true;
    obtenerCaracteristicas(Number(tipoId))
      .then((items) => {
        if (!vigente) return;
        setDefiniciones(items);
        setValores((actuales) => {
          const iniciales: Record<number, string> = {};
          for (const item of items) {
            const existente = producto?.attributes.find((a) => a.definition_id === item.id)?.value;
            iniciales[item.id] = actuales[item.id] ?? existente ?? '';
          }
          return iniciales;
        });
      })
      .catch((e: Error) => vigente && setError(e.message));
    return () => { vigente = false; };
  }, [tipoId, producto]);

  async function enviar(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError('');

    if (trackingMode === 'individual' && !prefix.trim()) {
      setError('Para registrar unidades individuales, indicá el prefijo de código del modelo.');
      return;
    }
    if (trackingMode === 'quantity' && prefix.trim()) {
      setError('Los artículos administrados por cantidad no utilizan prefijo de código.');
      return;
    }

    const faltantes = definicionesActivas.filter((d) => d.required && !(valores[d.id] ?? '').trim());
    if (faltantes.length > 0) {
      setError(`Completá las características obligatorias: ${faltantes.map((d) => d.name).join(', ')}.`);
      return;
    }

    setGuardando(true);
    try {
      const parsedValue = unitValue.trim() === '' ? null : Number(unitValue);
      if (parsedValue !== null && (!Number.isFinite(parsedValue) || parsedValue < 0)) {
        throw new Error('El valor unitario debe ser un número igual o mayor que cero.');
      }

      const payload: ProductoPayload = {
        name: nombre.trim() || null,
        description: descripcion.trim() || null,
        brand: marca.trim() || null,
        model: modelo.trim() || null,
        category_id: categoriaId ? Number(categoriaId) : null,
        component_type_id: tipoId ? Number(tipoId) : null,
        tracking_mode: trackingMode,
        asset_code_prefix: trackingMode === 'individual' ? prefix.trim().toUpperCase() : null,
        ...(canEditPrices ? { unit_value: parsedValue, value_currency: currency.trim().toUpperCase() || 'PYG' } : {}),
        attributes: definicionesActivas
          .filter((d) => (valores[d.id] ?? '').trim() !== '')
          .map((d) => ({ attribute_definition_id: d.id, value: valores[d.id].trim() })),
      };
      await onSave(payload);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'No se pudo guardar el artículo.');
    } finally {
      setGuardando(false);
    }
  }

  return (
    <div className="fixed inset-0 z-[70] flex items-center justify-center bg-slate-950/50 p-3 sm:p-5">
      <section className="max-h-[94vh] w-full max-w-3xl overflow-y-auto rounded-2xl bg-white dark:bg-slate-900 shadow-2xl">
        <header className="sticky top-0 z-10 flex items-center justify-between border-b border-slate-100 dark:border-slate-800 bg-white dark:bg-slate-900 px-6 py-4">
          <div>
            <h2 className="text-lg font-bold text-slate-900 dark:text-slate-100">{producto ? 'Editar artículo' : 'Nuevo artículo'}</h2>
            <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">Los datos descriptivos y la clasificación pueden completarse más adelante.</p>
          </div>
          <button type="button" onClick={onClose} className="rounded-lg p-2 text-slate-500 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800" aria-label="Cerrar"><X size={20} /></button>
        </header>

        <form onSubmit={enviar} className="space-y-5 p-6">
          <section>
            <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">Identificación</h3>
            <div className="grid gap-4 sm:grid-cols-2">
              <label className="space-y-1 text-sm sm:col-span-2">
                <span className="font-medium">Nombre</span>
                <input value={nombre} onChange={(e) => setNombre(e.target.value)} className={inputClass} placeholder="Ej.: Robot industrial, bornera, variador..." />
              </label>
              <label className="space-y-1 text-sm">
                <span className="font-medium">Categoría</span>
                <select value={categoriaId} onChange={(e) => setCategoriaId(e.target.value)} className={inputClass}>
                  <option value="">Sin clasificar</option>
                  {categorias.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
                </select>
              </label>
              <label className="space-y-1 text-sm">
                <span className="font-medium">Tipo de componente</span>
                <select value={tipoId} onChange={(e) => setTipoId(e.target.value)} className={inputClass}>
                  <option value="">Sin tipo asignado</option>
                  {tipos.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
                </select>
              </label>
              <label className="space-y-1 text-sm">
                <span className="font-medium">Marca del fabricante</span>
                <input value={marca} onChange={(e) => setMarca(e.target.value)} className={inputClass} placeholder="Opcional" />
              </label>
              <label className="space-y-1 text-sm">
                <span className="font-medium">Modelo</span>
                <input value={modelo} onChange={(e) => setModelo(e.target.value)} className={inputClass} placeholder="Opcional" />
              </label>
              <label className="space-y-1 text-sm sm:col-span-2">
                <span className="font-medium">Descripción técnica breve</span>
                <textarea value={descripcion} onChange={(e) => setDescripcion(e.target.value)} rows={2} className={inputClass} placeholder="Descripción técnica (opcional)" />
              </label>
            </div>
          </section>

          <section className="rounded-xl border border-slate-200 dark:border-slate-700 p-4">
            <h3 className="text-sm font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">Control de inventario</h3>
            <div className="mt-3 grid gap-4 sm:grid-cols-2">
              <label className="space-y-1 text-sm">
                <span className="font-medium">Seguimiento</span>
                <select value={trackingMode} onChange={(e) => setTrackingMode(e.target.value as TrackingMode)} className={inputClass}>
                  <option value="quantity">Por cantidad (borneras, repuestos, etc.)</option>
                  <option value="individual">Por unidad (robots, equipos, etc.)</option>
                </select>
              </label>
              {trackingMode === 'individual' && (
                <label className="space-y-1 text-sm">
                  <span className="font-medium">Prefijo de código del modelo *</span>
                  <input value={prefix} onChange={(e) => setPrefix(e.target.value.toUpperCase())} maxLength={10} pattern="[A-Z0-9]{2,10}" className={inputClass} placeholder="Ej.: KR, SCARA, PRB" />
                  <span className="text-xs text-slate-500 dark:text-slate-400">Se utilizará para generar códigos únicos de sus unidades.</span>
                </label>
              )}
              {canViewPrices && <label className="space-y-1 text-sm">
                <span className="font-medium">Valor unitario estimado</span>
                <input type="number" min="0" step="0.01" disabled={!canEditPrices} value={unitValue} onChange={(e) => setUnitValue(e.target.value)} className={inputClass} placeholder="Dejar vacío si aún no se conoce" />
              </label>}
              {canViewPrices && <label className="space-y-1 text-sm">
                <span className="font-medium">Moneda</span>
                <select value={currency} disabled={!canEditPrices} onChange={(e) => setCurrency(e.target.value)} className={inputClass}>
                  {currency !== 'USD' && currency !== 'PYG' && <option value={currency}>{currency} (anterior)</option>}
                  <option value="PYG">PYG · Guaraníes</option>
                  <option value="USD">USD · Dólares</option>
                </select>
              </label>}
            </div>
          </section>

          {tipoActual && (
            <section className="rounded-xl border border-slate-200 dark:border-slate-700 p-4">
              <div className="mb-3">
                <h3 className="font-semibold">Características de {tipoActual.name}</h3>
                <p className="text-xs text-slate-500 dark:text-slate-400">Las características son configurables desde Administración. Podés dejarlas vacías si todavía no tenés los datos.</p>
              </div>
              {definicionesActivas.length === 0 ? (
                <p className="text-sm text-slate-500 dark:text-slate-400">Este tipo todavía no tiene características configuradas.</p>
              ) : (
                <div className="grid gap-3 sm:grid-cols-2">
                  {definicionesActivas.map((d) => (
                    <label key={d.id} className="space-y-1 text-sm">
                      <span className="font-medium">{d.name}{d.unit ? ` (${d.unit})` : ''}{d.required ? ' *' : ''}</span>
                      <input type={d.data_type === 'number' ? 'number' : d.data_type === 'date' ? 'date' : 'text'} value={valores[d.id] ?? ''} onChange={(e) => setValores((v) => ({ ...v, [d.id]: e.target.value }))} className={inputClass} />
                    </label>
                  ))}
                </div>
              )}
            </section>
          )}

          {error && <p className="rounded-lg border border-red-200 dark:border-red-900 bg-red-50 dark:bg-red-950/60 px-3 py-2 text-sm text-red-700 dark:text-red-300">{error}</p>}
          <footer className="flex justify-end gap-2 border-t border-slate-100 dark:border-slate-800 pt-4">
            <button type="button" onClick={onClose} className="rounded-lg border border-slate-300 dark:border-slate-600 px-4 py-2 text-sm">Cancelar</button>
            <button type="submit" disabled={guardando} className="rounded-lg bg-blue-700 dark:bg-blue-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">{guardando ? 'Guardando...' : 'Guardar artículo'}</button>
          </footer>
        </form>
      </section>
    </div>
  );
}
