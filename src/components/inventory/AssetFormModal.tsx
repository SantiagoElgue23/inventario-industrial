import { useState, type FormEvent } from 'react';
import { X } from 'lucide-react';
import { useAuth } from '../../auth/useAuth';
import type { Activo, ActivoPayload, Producto, Ubicacion } from '../../types/inventory';

type Props = {
  activo: Activo | null;
  productos: Producto[];
  ubicaciones: Ubicacion[];
  initialProductId?: number | null;
  onClose: () => void;
  onSave: (payload: ActivoPayload & { asset_code_prefix?: string | null }) => Promise<void>;
};

const inputClass = 'w-full rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-900 px-3 py-2.5 text-sm outline-none focus:border-blue-500 dark:focus:border-blue-400 focus:ring-2 focus:ring-blue-100 dark:focus:ring-blue-950';

export default function AssetFormModal({
  activo, productos, ubicaciones, initialProductId = null, onClose, onSave,
}: Props) {
  const [productId, setProductId] = useState(
    activo?.product_id ? String(activo.product_id) : initialProductId ? String(initialProductId) : '',
  );
  const [prefix, setPrefix] = useState('');
  const [serial, setSerial] = useState(activo?.manufacturer_serial ?? '');
  const [brand, setBrand] = useState(activo?.manufacturer_brand ?? '');
  const [functional, setFunctional] = useState<ActivoPayload['functional_status']>(activo?.functional_status ?? 'unverified');
  const { canEditPrices, canViewPrices } = useAuth();
  const [note, setNote] = useState(activo?.observations ?? '');
  const [locationId, setLocationId] = useState(activo?.location_id ? String(activo.location_id) : '');
  const [value, setValue] = useState(activo?.estimated_value == null ? '' : String(activo.estimated_value));
  const [currency, setCurrency] = useState(() => activo?.value_currency ??
    productos.find(p => p.id === (initialProductId ?? activo?.product_id))?.value_currency ?? 'PYG');
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);

  const selectedProduct = productos.find((p) => p.id === Number(productId));

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError('');
    if (!activo && !productId && !prefix.trim()) {
      setError('Indicá un prefijo de código para generar el código de este activo.');
      return;
    }
    if (serial.trim() && !brand.trim() && !selectedProduct?.brand) {
      setError('Si registrás un número de serie, indicá el fabricante.');
      return;
    }

    const parsedValue = value.trim() === '' ? null : Number(value);
    if (parsedValue !== null && (!Number.isFinite(parsedValue) || parsedValue < 0)) {
      setError('El valor estimado debe ser un número igual o mayor que cero.');
      return;
    }

    setSaving(true);
    try {
      const payload: ActivoPayload & { asset_code_prefix?: string | null } = {
        product_id: productId ? Number(productId) : null,
        manufacturer_serial: serial.trim() || null,
        manufacturer_brand: brand.trim() || selectedProduct?.brand || null,
        functional_status: functional,
        observations: note.trim() || null,
        location_id: locationId ? Number(locationId) : null,
        ...(canEditPrices ? { estimated_value: parsedValue, value_currency: currency.trim().toUpperCase() || 'PYG' } : {}),
      };
      if (!activo && !productId) payload.asset_code_prefix = prefix.trim().toUpperCase();
      await onSave(payload);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'No se pudo guardar el activo.');
    } finally {
      setSaving(false);
    }
  }

  const locationLabel = (location: Ubicacion) =>
    location.parent_name ? `${location.parent_name} / ${location.name}` : location.name;

  return (
    <div className="fixed inset-0 z-[80] flex items-center justify-center bg-slate-950/50 p-3 sm:p-5">
      <section className="max-h-[94vh] w-full max-w-2xl overflow-y-auto rounded-2xl bg-white dark:bg-slate-900 shadow-2xl">
        <header className="sticky top-0 z-10 flex items-center justify-between border-b border-slate-100 dark:border-slate-800 bg-white dark:bg-slate-900 px-6 py-4">
          <div>
            <h2 className="text-lg font-bold">{activo ? 'Editar unidad' : 'Registrar unidad individual'}</h2>
            <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">El código interno se genera automáticamente y no puede modificarse.</p>
          </div>
          <button type="button" onClick={onClose} aria-label="Cerrar" className="rounded-lg p-2 hover:bg-slate-100 dark:hover:bg-slate-800"><X size={20} /></button>
        </header>

        <form onSubmit={submit} className="space-y-5 p-6">
          <label className="block space-y-1 text-sm">
            <span className="font-medium">Modelo o artículo asociado</span>
            <select value={productId} onChange={(e) => { setProductId(e.target.value); if (!activo && !value.trim()) setCurrency(productos.find(p => p.id === Number(e.target.value))?.value_currency ?? 'PYG'); }} className={inputClass}>
              <option value="">Sin producto asociado por ahora</option>
              {productos.filter((p) => p.tracking_mode === 'individual').map((p) => (
                <option key={p.id} value={p.id}>{p.name || `Artículo #${p.id}`} · {p.brand || 'Sin marca'} {p.model || ''}</option>
              ))}
            </select>
            <span className="text-xs text-slate-500 dark:text-slate-400">El nombre, la categoría y el modelo se toman del artículo del catálogo. Si todavía no existe, crealo primero en Inventario y luego registrá sus unidades.</span>
          </label>

          {!productId && (
            <div className="rounded-lg border border-amber-200 dark:border-amber-900 bg-amber-50 dark:bg-amber-950/60 p-3 text-sm text-amber-800 dark:text-amber-200">
              {activo
                ? 'Esta unidad no tiene un artículo de catálogo asociado. Por eso no muestra nombre, categoría ni modelo. Podés asociarla a un artículo individual existente.'
                : 'Si registrás esta unidad sin asociarla a un artículo, solo tendrá código interno y datos propios de la unidad; no tendrá nombre, categoría ni modelo en el inventario.'}
            </div>
          )}

          {!activo && !productId && (
            <label className="block space-y-1 text-sm">
              <span className="font-medium">Prefijo de código *</span>
              <input value={prefix} onChange={(e) => setPrefix(e.target.value.toUpperCase())} maxLength={10} pattern="[A-Z0-9]{2,10}" className={inputClass} placeholder="Ej.: PRB" />
            </label>
          )}

          {activo && <div className="rounded-lg bg-blue-50 dark:bg-blue-950 p-3 text-sm"><span className="text-blue-700 dark:text-blue-300">Código interno:</span> <strong className="ml-1">{activo.asset_code}</strong></div>}

          <div className="grid gap-4 sm:grid-cols-2">
            <label className="space-y-1 text-sm">
              <span className="font-medium">Número de serie del fabricante</span>
              <input value={serial} onChange={(e) => setSerial(e.target.value)} className={inputClass} placeholder="Opcional" />
            </label>
            <label className="space-y-1 text-sm">
              <span className="font-medium">Fabricante</span>
              <input value={brand} onChange={(e) => setBrand(e.target.value)} className={inputClass} placeholder={selectedProduct?.brand || 'Opcional'} />
            </label>
            <label className="space-y-1 text-sm">
              <span className="font-medium">Ubicación</span>
              <select value={locationId} onChange={(e) => setLocationId(e.target.value)} className={inputClass}>
                <option value="">Sin ubicación asignada</option>
                {ubicaciones.map((u) => <option key={u.id} value={u.id}>{locationLabel(u)}</option>)}
              </select>
            </label>
            {canViewPrices && <label className="space-y-1 text-sm">
              <span className="font-medium">Valor estimado de esta unidad</span>
              <input type="number" min="0" step="0.01" disabled={!canEditPrices} value={value} onChange={(e) => setValue(e.target.value)} className={inputClass} placeholder="Opcional" />
            </label>}
            <label className="space-y-1 text-sm">
              <span className="font-medium">Estado funcional</span>
              <select value={functional} onChange={(e) => setFunctional(e.target.value as ActivoPayload['functional_status'])} className={inputClass}>
                <option value="unverified">Sin verificar</option><option value="functional">Operativo</option><option value="damaged">Averiado</option>
              </select>
            </label>
            {canViewPrices && <label className="space-y-1 text-sm">
              <span className="font-medium">Moneda</span>
              <select value={currency} disabled={!canEditPrices} onChange={(e) => setCurrency(e.target.value)} className={inputClass}>
                {currency !== 'USD' && currency !== 'PYG' && <option value={currency}>{currency} (anterior)</option>}
                <option value="PYG">PYG · Guaraníes</option>
                <option value="USD">USD · Dólares</option>
              </select>
            </label>}
            <label className="space-y-1 text-sm sm:col-span-2">
              <span className="font-medium">Observaciones</span>
              <textarea value={note} onChange={(e) => setNote(e.target.value)} rows={2} className={inputClass} placeholder="Información adicional, condición, etc." />
            </label>
          </div>

          {error && <p className="rounded-lg border border-red-200 dark:border-red-900 bg-red-50 dark:bg-red-950/60 px-3 py-2 text-sm text-red-700 dark:text-red-300">{error}</p>}
          <footer className="flex justify-end gap-2 border-t border-slate-100 dark:border-slate-800 pt-4">
            <button type="button" onClick={onClose} className="rounded-lg border border-slate-300 dark:border-slate-600 px-4 py-2 text-sm">Cancelar</button>
            <button type="submit" disabled={saving} className="rounded-lg bg-blue-700 dark:bg-blue-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">{saving ? 'Guardando...' : 'Guardar unidad'}</button>
          </footer>
        </form>
      </section>
    </div>
  );
}
