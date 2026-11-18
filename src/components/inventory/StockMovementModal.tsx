import { useCallback, useState, type FormEvent } from 'react';
import { X } from 'lucide-react';
import type {
  ExistenciaUbicacion,
  Producto,
  TipoMovimiento,
  Ubicacion,
} from '../../types/inventory';
import { obtenerExistenciasProducto } from '../../services/inventoryService';

import { useLoadEffect } from '../../hooks/useLoadEffect';
type MovementPayload = {
  location_id: number | null;
  movement_type: TipoMovimiento;
  quantity: number;
  note: string | null;
};

type Props = {
  articulo: Producto;
  ubicaciones: Ubicacion[];
  onClose: () => void;
  onSave: (data: MovementPayload) => Promise<void>;
};

const formatQuantity = (value: number | string) => {
  const numeric = Number(value);
  return Number.isFinite(numeric)
    ? new Intl.NumberFormat('es-PY', { maximumFractionDigits: 3 }).format(numeric)
    : '—';
};

export default function StockMovementModal({
  articulo,
  ubicaciones,
  onClose,
  onSave,
}: Props) {
  const [tipo, setTipo] = useState<TipoMovimiento>('entry');
  const [cantidad, setCantidad] = useState('');
  const [ubicacionId, setUbicacionId] = useState('');
  const [nota, setNota] = useState('');
  const [balances, setBalances] = useState<ExistenciaUbicacion[]>([]);
  const [cargandoExistencias, setCargandoExistencias] = useState(true);
  const [existenciasCargadas, setExistenciasCargadas] = useState(false);
  const [error, setError] = useState('');
  const [guardando, setGuardando] = useState(false);

  const cargarExistencias = useCallback(async () => {
    setCargandoExistencias(true);
    setExistenciasCargadas(false);
    setError('');
    try {
      const rows = await obtenerExistenciasProducto(articulo.id);
      setBalances(rows);
      setExistenciasCargadas(true);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'No se pudo consultar el saldo actual.');
    } finally {
      setCargandoExistencias(false);
    }
  }, [articulo.id]);

  useLoadEffect(cargarExistencias);

  const balance = ubicacionId
    ? balances.find((item) =>
        item.location_id === (ubicacionId === 'none' ? null : Number(ubicacionId)),
      )
    : undefined;

  const saldoVerificado = balance?.verified === true;
  const conteoInicialPendiente = Boolean(ubicacionId) && !saldoVerificado;
  const tipoEfectivo: TipoMovimiento = conteoInicialPendiente ? 'count' : tipo;
  const saldoActual = saldoVerificado ? Number(balance?.quantity ?? 0) : 0;
  const cantidadNumerica = cantidad.trim() === '' ? null : Number(cantidad);
  const cantidadValida =
    cantidadNumerica !== null &&
    Number.isFinite(cantidadNumerica) &&
    cantidadNumerica >= 0 &&
    (tipoEfectivo === 'count' || cantidadNumerica > 0);

  let saldoProyectado: number | null = null;
  if (cantidadValida && cantidadNumerica !== null && ubicacionId) {
    if (tipoEfectivo === 'entry') saldoProyectado = saldoActual + cantidadNumerica;
    else if (tipoEfectivo === 'exit') saldoProyectado = saldoActual - cantidadNumerica;
    else saldoProyectado = cantidadNumerica;
  }

  const excedeSaldo =
    tipoEfectivo === 'exit' &&
    cantidadNumerica !== null &&
    Number.isFinite(cantidadNumerica) &&
    cantidadNumerica > saldoActual;

  async function enviar(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError('');

    if (!existenciasCargadas) {
      setError('No se pudo verificar el saldo actual. Volvé a consultar las existencias.');
      return;
    }
    if (!ubicacionId) {
      setError('Seleccioná dónde se encuentran las existencias.');
      return;
    }
    if (!cantidadValida || cantidadNumerica === null) {
      setError(
        tipoEfectivo === 'count'
          ? 'Ingresá una cantidad física válida. Puede ser cero.'
          : 'Ingresá una cantidad mayor que cero.',
      );
      return;
    }
    if (excedeSaldo) {
      setError(`No podés retirar ${formatQuantity(cantidadNumerica)}: el saldo disponible es ${formatQuantity(saldoActual)}.`);
      return;
    }

    setGuardando(true);
    try {
      await onSave({
        location_id: ubicacionId === 'none' ? null : Number(ubicacionId),
        movement_type: tipoEfectivo,
        quantity: cantidadNumerica,
        note: nota.trim() || null,
      });
    } catch (e) {
      setError(e instanceof Error ? e.message : 'No se pudo actualizar la existencia.');
    } finally {
      setGuardando(false);
    }
  }

  const label = articulo.name || `Artículo #${articulo.id}`;

  return (
    <div className="fixed inset-0 z-[80] flex items-center justify-center bg-slate-950/50 p-4">
      <form
        onSubmit={enviar}
        className="max-h-[94vh] w-full max-w-lg space-y-5 overflow-y-auto rounded-2xl bg-white dark:bg-slate-900 p-6 shadow-2xl"
      >
        <header className="flex items-start justify-between gap-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-blue-700 dark:text-blue-300">
              Gestión de existencias
            </p>
            <h2 className="mt-1 text-xl font-bold text-slate-900 dark:text-slate-100">Actualizar existencias</h2>
            <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">{label}</p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Cerrar"
            className="rounded-lg p-2 text-slate-500 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800"
          >
            <X size={19} />
          </button>
        </header>

        <section className="space-y-2">
          <label className="block space-y-1.5 text-sm">
            <span className="font-semibold text-slate-700 dark:text-slate-200">¿Dónde están las existencias?</span>
            <select
              required
              value={ubicacionId}
              onChange={(event) => {
                setUbicacionId(event.target.value);
                setTipo('entry');
                setCantidad('');
                setError('');
              }}
              className="w-full rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-900 px-3 py-2.5 outline-none focus:border-blue-600 focus:ring-2 focus:ring-blue-100 dark:focus:ring-blue-950"
            >
              <option value="">Seleccionar ubicación</option>
              <option value="none">Sin ubicación identificada</option>
              {ubicaciones.map((ubicacion) => (
                <option key={ubicacion.id} value={ubicacion.id}>
                  {ubicacion.parent_name
                    ? `${ubicacion.parent_name} / ${ubicacion.name}`
                    : ubicacion.name}
                </option>
              ))}
            </select>
          </label>

          {cargandoExistencias ? (
            <p className="rounded-lg bg-slate-50 dark:bg-slate-950 px-3 py-2.5 text-sm text-slate-500 dark:text-slate-400">
              Consultando saldo actual...
            </p>
          ) : !existenciasCargadas ? (
            <div className="flex items-center justify-between gap-3 rounded-lg border border-red-200 dark:border-red-900 bg-red-50 dark:bg-red-950/60 px-3 py-2.5">
              <p className="text-sm text-red-700 dark:text-red-300">No se pudo consultar el saldo actual.</p>
              <button
                type="button"
                onClick={() => void cargarExistencias()}
                className="shrink-0 text-sm font-semibold text-red-700 dark:text-red-300 underline"
              >
                Reintentar
              </button>
            </div>
          ) : !ubicacionId ? (
            <p className="rounded-lg bg-slate-50 dark:bg-slate-950 px-3 py-2.5 text-sm text-slate-500 dark:text-slate-400">
              Seleccioná una ubicación para consultar su saldo.
            </p>
          ) : saldoVerificado ? (
            <div className="rounded-lg border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-950 px-4 py-3">
              <p className="text-xs font-medium text-slate-500 dark:text-slate-400">Existencia actual en esta ubicación</p>
              <p className="mt-1 text-2xl font-bold tabular-nums text-slate-900 dark:text-slate-100">
                {formatQuantity(saldoActual)}
              </p>
            </div>
          ) : (
            <div className="rounded-lg border border-amber-200 dark:border-amber-900 bg-amber-50 dark:bg-amber-950/60 px-4 py-3">
              <p className="text-sm font-semibold text-amber-900 dark:text-amber-200">Conteo inicial pendiente</p>
              <p className="mt-1 text-xs leading-5 text-amber-800 dark:text-amber-200">
                Antes de registrar ingresos o retiros, indicá cuántas unidades hay físicamente en esta ubicación. Si todavía no hay ninguna, ingresá 0.
              </p>
            </div>
          )}
        </section>

        <label className="block space-y-1.5 text-sm">
          <span className="font-semibold text-slate-700 dark:text-slate-200">Operación</span>
          <select
            value={tipoEfectivo}
            disabled={!ubicacionId || !existenciasCargadas || conteoInicialPendiente}
            onChange={(event) => setTipo(event.target.value as TipoMovimiento)}
            className="w-full rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-900 px-3 py-2.5 disabled:bg-slate-100"
          >
            {conteoInicialPendiente ? (
              <option value="count">Conteo inicial</option>
            ) : (
              <>
                <option value="entry">Ingreso — agregar unidades</option>
                <option value="exit">Extracción — retirar unidades</option>
                <option value="count">Ajuste — corregir al conteo físico</option>
              </>
            )}
          </select>
        </label>

        <label className="block space-y-1.5 text-sm">
          <span className="font-semibold text-slate-700 dark:text-slate-200">
            {tipoEfectivo === 'count'
              ? 'Cantidad física contada'
              : tipoEfectivo === 'entry'
                ? 'Cantidad a ingresar'
                : 'Cantidad a retirar'}
          </span>
          <input
            type="number"
            min={tipoEfectivo === 'count' ? '0' : '0.001'}
            step="0.001"
            value={cantidad}
            onChange={(event) => setCantidad(event.target.value)}
            className="w-full rounded-lg border border-slate-300 dark:border-slate-600 px-3 py-2.5 outline-none focus:border-blue-600 focus:ring-2 focus:ring-blue-100 dark:focus:ring-blue-950"
            placeholder="0"
            disabled={!ubicacionId || !existenciasCargadas}
          />
        </label>

        {saldoProyectado !== null && (
          <section className="rounded-lg border border-slate-200 dark:border-slate-700 p-4">
            <div className="flex items-center justify-between gap-3 text-sm">
              <span className="text-slate-500 dark:text-slate-400">
                {tipoEfectivo === 'count' ? 'Nuevo saldo contado' : 'Saldo resultante'}
              </span>
              <strong className={`text-lg tabular-nums ${saldoProyectado < 0 ? 'text-red-700 dark:text-red-300' : 'text-slate-900 dark:text-slate-100'}`}>
                {formatQuantity(saldoProyectado)}
              </strong>
            </div>
            {tipoEfectivo === 'count' && saldoVerificado && (
              <p className="mt-2 text-xs leading-5 text-amber-800 dark:text-amber-200">
                Este valor reemplazará el saldo registrado. No se sumará a la cantidad actual.
              </p>
            )}
            {tipoEfectivo === 'count' && !saldoVerificado && (
              <p className="mt-2 text-xs text-slate-500 dark:text-slate-400">Este conteo establecerá el saldo inicial verificado.</p>
            )}
            {excedeSaldo && (
              <p className="mt-2 text-xs font-medium text-red-700 dark:text-red-300">
                La cantidad a retirar supera el saldo disponible.
              </p>
            )}
          </section>
        )}

        <label className="block space-y-1.5 text-sm">
          <span className="font-semibold text-slate-700 dark:text-slate-200">Observación <span className="font-normal text-slate-400 dark:text-slate-400">(opcional)</span></span>
          <textarea
            rows={2}
            value={nota}
            onChange={(event) => setNota(event.target.value)}
            className="w-full rounded-lg border border-slate-300 dark:border-slate-600 px-3 py-2.5 outline-none focus:border-blue-600 focus:ring-2 focus:ring-blue-100 dark:focus:ring-blue-950"
            placeholder="Motivo o referencia del movimiento"
          />
        </label>

        {error && (
          <p className="rounded-lg border border-red-200 dark:border-red-900 bg-red-50 dark:bg-red-950/60 px-3 py-2.5 text-sm text-red-700 dark:text-red-300">
            {error}
          </p>
        )}

        <footer className="flex justify-end gap-2 border-t border-slate-100 dark:border-slate-800 pt-4">
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg border border-slate-300 dark:border-slate-600 px-4 py-2 text-sm font-medium text-slate-700 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-slate-800"
          >
            Cancelar
          </button>
          <button
            type="submit"
            disabled={
              guardando ||
              cargandoExistencias ||
              !existenciasCargadas ||
              !ubicacionId ||
              !cantidadValida ||
              Boolean(excedeSaldo)
            }
            className="rounded-lg bg-blue-700 dark:bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-800 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {guardando ? 'Guardando...' : 'Confirmar actualización'}
          </button>
        </footer>
      </form>
    </div>
  );
}
