import { useCallback, useMemo, useState, type FormEvent } from 'react';
import { ArrowLeftRight, X } from 'lucide-react';
import type {
  ExistenciaUbicacion,
  Producto,
  TrasladoExistenciasPayload,
  Ubicacion,
} from '../../types/inventory';
import { obtenerExistenciasProducto } from '../../services/inventoryService';

import { useLoadEffect } from '../../hooks/useLoadEffect';
type Props = {
  articulo: Producto;
  ubicaciones: Ubicacion[];
  onClose: () => void;
  onSave: (data: TrasladoExistenciasPayload) => Promise<void>;
};

const formatQuantity = (value: number | string) => {
  const numeric = Number(value);
  return Number.isFinite(numeric)
    ? new Intl.NumberFormat('es-PY', { maximumFractionDigits: 3 }).format(numeric)
    : '—';
};

const locationKey = (value: string) => value === 'none' ? null : Number(value);

export default function StockTransferModal({ articulo, ubicaciones, onClose, onSave }: Props) {
  const [balances, setBalances] = useState<ExistenciaUbicacion[]>([]);
  const [sourceId, setSourceId] = useState('');
  const [destinationId, setDestinationId] = useState('');
  const [quantity, setQuantity] = useState('');
  const [note, setNote] = useState('');
  const [loadingBalances, setLoadingBalances] = useState(true);
  const [balancesLoaded, setBalancesLoaded] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const loadBalances = useCallback(async () => {
    setLoadingBalances(true);
    setBalancesLoaded(false);
    setError('');
    try {
      const rows = await obtenerExistenciasProducto(articulo.id);
      setBalances(rows);
      setBalancesLoaded(true);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'No se pudieron consultar las existencias.');
    } finally {
      setLoadingBalances(false);
    }
  }, [articulo.id]);

  useLoadEffect(loadBalances);

  const sourceBalance = useMemo(() => {
    if (!sourceId) return undefined;
    const key = locationKey(sourceId);
    return balances.find((balance) => balance.location_id === key);
  }, [balances, sourceId]);

  const destinationBalance = useMemo(() => {
    if (!destinationId) return undefined;
    const key = locationKey(destinationId);
    return balances.find((balance) => balance.location_id === key);
  }, [balances, destinationId]);

  const sameLocation = Boolean(sourceId && destinationId && sourceId === destinationId);
  const sourceVerified = sourceBalance?.verified === true;
  const destinationVerified = destinationBalance?.verified === true;
  const sourceQuantity = sourceVerified ? Number(sourceBalance?.quantity ?? 0) : 0;
  const destinationQuantity = destinationVerified ? Number(destinationBalance?.quantity ?? 0) : 0;
  const numericQuantity = quantity.trim() === '' ? null : Number(quantity);
  const quantityValid = numericQuantity !== null && Number.isFinite(numericQuantity) && numericQuantity > 0;
  const exceedsSource = quantityValid && numericQuantity !== null && numericQuantity > sourceQuantity;
  const canSubmit =
    balancesLoaded &&
    !loadingBalances &&
    Boolean(sourceId && destinationId) &&
    !sameLocation &&
    sourceVerified &&
    destinationVerified &&
    quantityValid &&
    !exceedsSource &&
    !saving;

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError('');

    if (!balancesLoaded) {
      setError('No se pudieron verificar los saldos. Volvé a consultar las existencias.');
      return;
    }
    if (!sourceId || !destinationId) {
      setError('Seleccioná una ubicación de origen y otra de destino.');
      return;
    }
    if (sameLocation) {
      setError('El origen y el destino deben ser diferentes.');
      return;
    }
    if (!sourceVerified) {
      setError('El origen todavía no tiene un conteo físico inicial verificado.');
      return;
    }
    if (!destinationVerified) {
      setError('El destino todavía no tiene un conteo físico inicial verificado. Registrá primero su conteo, aunque sea 0.');
      return;
    }
    if (!quantityValid || numericQuantity === null) {
      setError('Ingresá una cantidad mayor que cero.');
      return;
    }
    if (exceedsSource) {
      setError(`No podés trasladar ${formatQuantity(numericQuantity)}: el origen dispone de ${formatQuantity(sourceQuantity)}.`);
      return;
    }

    setSaving(true);
    try {
      await onSave({
        source_location_id: locationKey(sourceId),
        destination_location_id: locationKey(destinationId),
        quantity: numericQuantity,
        note: note.trim() || null,
      });
    } catch (e) {
      setError(e instanceof Error ? e.message : 'No se pudo registrar el traslado.');
    } finally {
      setSaving(false);
    }
  }

  const locationLabel = (locationId: string) => {
    if (locationId === 'none') return 'Sin ubicación identificada';
    const location = ubicaciones.find((item) => item.id === Number(locationId));
    if (!location) return 'Ubicación';
    return location.parent_name ? `${location.parent_name} / ${location.name}` : location.name;
  };

  const title = articulo.name || `Artículo #${articulo.id}`;

  return (
    <div className="fixed inset-0 z-[90] flex items-center justify-center bg-slate-950/50 p-4">
      <form
        onSubmit={submit}
        className="max-h-[94vh] w-full max-w-xl space-y-5 overflow-y-auto rounded-2xl bg-white dark:bg-slate-900 p-6 shadow-2xl"
      >
        <header className="flex items-start justify-between gap-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-blue-700 dark:text-blue-300">Gestión de existencias</p>
            <h2 className="mt-1 text-xl font-bold text-slate-900 dark:text-slate-100">Trasladar existencias</h2>
            <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">{title}</p>
          </div>
          <button type="button" onClick={onClose} aria-label="Cerrar" className="rounded-lg p-2 text-slate-500 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800">
            <X size={19} />
          </button>
        </header>

        {loadingBalances ? (
          <p className="rounded-lg bg-slate-50 dark:bg-slate-950 px-3 py-3 text-sm text-slate-500 dark:text-slate-400">Consultando saldos...</p>
        ) : !balancesLoaded ? (
          <div className="flex items-center justify-between gap-3 rounded-lg border border-red-200 dark:border-red-900 bg-red-50 dark:bg-red-950/60 px-3 py-3">
            <p className="text-sm text-red-700 dark:text-red-300">No se pudieron consultar las existencias.</p>
            <button type="button" onClick={() => void loadBalances()} className="shrink-0 text-sm font-semibold text-red-700 dark:text-red-300 underline">Reintentar</button>
          </div>
        ) : null}

        <div className="grid gap-4 sm:grid-cols-2">
          <label className="block space-y-1.5 text-sm">
            <span className="font-semibold text-slate-700 dark:text-slate-200">Origen</span>
            <select
              required
              value={sourceId}
              onChange={(event) => { setSourceId(event.target.value); setError(''); }}
              disabled={!balancesLoaded}
              className="w-full rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-900 px-3 py-2.5 outline-none focus:border-blue-600 focus:ring-2 focus:ring-blue-100 dark:focus:ring-blue-950 disabled:bg-slate-100"
            >
              <option value="">Seleccionar origen</option>
              <option value="none">Sin ubicación identificada</option>
              {ubicaciones.map((location) => (
                <option key={location.id} value={location.id}>
                  {location.parent_name ? `${location.parent_name} / ${location.name}` : location.name}
                </option>
              ))}
            </select>
            {sourceId && (
              <span className="block text-xs text-slate-500 dark:text-slate-400">
                {sourceVerified ? `Disponible: ${formatQuantity(sourceQuantity)}` : 'Conteo inicial pendiente'}
              </span>
            )}
          </label>

          <label className="block space-y-1.5 text-sm">
            <span className="font-semibold text-slate-700 dark:text-slate-200">Destino</span>
            <select
              required
              value={destinationId}
              onChange={(event) => { setDestinationId(event.target.value); setError(''); }}
              disabled={!balancesLoaded}
              className="w-full rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-900 px-3 py-2.5 outline-none focus:border-blue-600 focus:ring-2 focus:ring-blue-100 dark:focus:ring-blue-950 disabled:bg-slate-100"
            >
              <option value="">Seleccionar destino</option>
              <option value="none">Sin ubicación identificada</option>
              {ubicaciones.map((location) => (
                <option key={location.id} value={location.id}>
                  {location.parent_name ? `${location.parent_name} / ${location.name}` : location.name}
                </option>
              ))}
            </select>
            {destinationId && (
              <span className="block text-xs text-slate-500 dark:text-slate-400">
                {destinationVerified ? `Existencia actual: ${formatQuantity(destinationQuantity)}` : 'Conteo inicial pendiente'}
              </span>
            )}
          </label>
        </div>

        {sameLocation && (
          <p className="rounded-lg border border-amber-200 dark:border-amber-900 bg-amber-50 dark:bg-amber-950/60 px-3 py-2.5 text-sm text-amber-800 dark:text-amber-200">
            El origen y el destino deben ser diferentes.
          </p>
        )}

        {(sourceId && destinationId && sourceVerified && destinationVerified && !sameLocation) && (
          <section className="rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-950 p-4">
            <div className="flex items-center justify-between gap-3 text-sm">
              <span className="font-medium text-slate-600 dark:text-slate-300">Vista previa del traslado</span>
              <ArrowLeftRight size={17} className="text-slate-400 dark:text-slate-400" />
            </div>
            <div className="mt-3 grid grid-cols-2 gap-3">
              <div>
                <p className="text-xs text-slate-500 dark:text-slate-400">{locationLabel(sourceId)}</p>
                <p className="mt-1 text-lg font-bold tabular-nums">{formatQuantity(sourceQuantity - (quantityValid ? numericQuantity ?? 0 : 0))}</p>
                <p className="text-xs text-slate-500 dark:text-slate-400">Saldo resultante</p>
              </div>
              <div>
                <p className="text-xs text-slate-500 dark:text-slate-400">{locationLabel(destinationId)}</p>
                <p className="mt-1 text-lg font-bold tabular-nums">{formatQuantity(destinationQuantity + (quantityValid ? numericQuantity ?? 0 : 0))}</p>
                <p className="text-xs text-slate-500 dark:text-slate-400">Saldo resultante</p>
              </div>
            </div>
            {exceedsSource && (
              <p className="mt-3 text-xs font-medium text-red-700 dark:text-red-300">La cantidad supera el saldo disponible en el origen.</p>
            )}
          </section>
        )}

        <label className="block space-y-1.5 text-sm">
          <span className="font-semibold text-slate-700 dark:text-slate-200">Cantidad a trasladar</span>
          <input
            type="number"
            min="0.001"
            step="0.001"
            value={quantity}
            onChange={(event) => setQuantity(event.target.value)}
            disabled={!balancesLoaded}
            placeholder="0"
            className="w-full rounded-lg border border-slate-300 dark:border-slate-600 px-3 py-2.5 outline-none focus:border-blue-600 focus:ring-2 focus:ring-blue-100 dark:focus:ring-blue-950 disabled:bg-slate-100"
          />
        </label>

        <label className="block space-y-1.5 text-sm">
          <span className="font-semibold text-slate-700 dark:text-slate-200">Observación <span className="font-normal text-slate-400 dark:text-slate-400">(opcional)</span></span>
          <textarea
            rows={2}
            value={note}
            onChange={(event) => setNote(event.target.value)}
            className="w-full rounded-lg border border-slate-300 dark:border-slate-600 px-3 py-2.5 outline-none focus:border-blue-600 focus:ring-2 focus:ring-blue-100 dark:focus:ring-blue-950"
            placeholder="Motivo o referencia del traslado"
          />
        </label>

        {error && <p className="rounded-lg border border-red-200 dark:border-red-900 bg-red-50 dark:bg-red-950/60 px-3 py-2.5 text-sm text-red-700 dark:text-red-300">{error}</p>}

        <footer className="flex justify-end gap-2 border-t border-slate-100 dark:border-slate-800 pt-4">
          <button type="button" onClick={onClose} className="rounded-lg border border-slate-300 dark:border-slate-600 px-4 py-2 text-sm font-medium text-slate-700 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-slate-800">Cancelar</button>
          <button type="submit" disabled={!canSubmit} className="rounded-lg bg-blue-700 dark:bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-800 disabled:cursor-not-allowed disabled:opacity-50">
            {saving ? 'Registrando...' : 'Confirmar traslado'}
          </button>
        </footer>
      </form>
    </div>
  );
}
