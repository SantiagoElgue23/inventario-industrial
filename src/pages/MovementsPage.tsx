import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  ArrowDownLeft,
  ArrowLeftRight,
  ArrowUpRight,
  ClipboardList,
  Plus,
  Search,
} from 'lucide-react';
import StockMovementModal from '../components/inventory/StockMovementModal';
import StockTransferModal from '../components/inventory/StockTransferModal';
import {
  obtenerMovimientos,
  obtenerProductos,
  obtenerTraslados,
  obtenerUbicaciones,
  registrarMovimiento,
  registrarTraslado,
} from '../services/inventoryService';
import type {
  Movimiento,
  Producto,
  TrasladoExistencias,
  TrasladoExistenciasPayload,
  Ubicacion,
} from '../types/inventory';

import { useLoadEffect } from '../hooks/useLoadEffect';
const normalize = (value: string) =>
  value.toLocaleLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '');

const formatQuantity = (value: number | string) => {
  const numeric = Number(value);
  return Number.isFinite(numeric)
    ? new Intl.NumberFormat('es-PY', { maximumFractionDigits: 3 }).format(numeric)
    : '—';
};

type HistoryItem =
  | { kind: 'movement'; item: Movimiento }
  | { kind: 'transfer'; item: TrasladoExistencias };

export default function MovementsPage() {
  const [products, setProducts] = useState<Producto[]>([]);
  const [locations, setLocations] = useState<Ubicacion[]>([]);
  const [selectedProduct, setSelectedProduct] = useState<Producto | null>(null);
  const [movements, setMovements] = useState<Movimiento[]>([]);
  const [transfers, setTransfers] = useState<TrasladoExistencias[]>([]);
  const [search, setSearch] = useState('');
  const [showForm, setShowForm] = useState(false);
  const [showTransferForm, setShowTransferForm] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const [items, locs] = await Promise.all([
        obtenerProductos({ tracking_mode: 'quantity' }),
        obtenerUbicaciones(),
      ]);
      setProducts(items);
      setLocations(locs);
      setSelectedProduct((current) =>
        current ? items.find((product) => product.id === current.id) ?? null : null,
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : 'No se pudieron cargar las existencias.');
    } finally {
      setLoading(false);
    }
  }, []);

  const loadHistory = useCallback(async (productId: number) => {
    const [movementRows, transferRows] = await Promise.all([
      obtenerMovimientos(productId),
      obtenerTraslados(productId),
    ]);
    setMovements(movementRows);
    setTransfers(transferRows);
  }, []);

  useLoadEffect(load);

  const selectedProductId = selectedProduct?.id ?? null;

  useEffect(() => {
    if (selectedProductId === null) return;

    let current = true;
    Promise.all([
      obtenerMovimientos(selectedProductId),
      obtenerTraslados(selectedProductId),
    ])
      .then(([movementRows, transferRows]) => {
        if (!current) return;
        setMovements(movementRows);
        setTransfers(transferRows);
      })
      .catch((e: Error) => current && setError(e.message));

    return () => {
      current = false;
    };
  }, [selectedProductId]);

  const filteredProducts = useMemo(() => {
    const terms = normalize(search.trim()).split(/\s+/).filter(Boolean);
    return products.filter((product) => {
      const content = normalize([
        product.name,
        product.brand,
        product.model,
        product.category_name,
        product.component_type_name,
      ].filter(Boolean).join(' '));
      return terms.every((term) => content.includes(term));
    });
  }, [products, search]);

  // Solo se muestra el historial del artículo seleccionado, aunque haya datos de uno anterior en memoria.
  const history = useMemo<HistoryItem[]>(() => [
    ...movements.filter((item) => item.product_id === selectedProductId).map((item): HistoryItem => ({ kind: 'movement', item })),
    ...transfers.filter((item) => item.product_id === selectedProductId).map((item): HistoryItem => ({ kind: 'transfer', item })),
  ].sort((a, b) =>
    new Date(b.item.created_at).getTime() - new Date(a.item.created_at).getTime(),
  ), [movements, transfers, selectedProductId]);

  const locationNames = useMemo(
    () => new Map(
      locations.map((location) => [
        location.id,
        location.parent_name
          ? `${location.parent_name} / ${location.name}`
          : location.name,
      ]),
    ),
    [locations],
  );

  async function refreshAfterOperation(productId: number, operationLabel: string) {
    try {
      const [items] = await Promise.all([
        obtenerProductos({ tracking_mode: 'quantity' }),
        loadHistory(productId),
      ]);
      setProducts(items);
      setSelectedProduct(items.find((product) => product.id === productId) ?? null);
      setError('');
    } catch (e) {
      setError(
        e instanceof Error
          ? `${operationLabel}, pero no se pudo actualizar la vista: ${e.message}`
          : `${operationLabel}, pero no se pudo actualizar la vista.`,
      );
    }
  }

  async function saveMovement(data: {
    location_id: number | null;
    movement_type: 'entry' | 'exit' | 'count';
    quantity: number;
    note: string | null;
  }) {
    if (!selectedProduct) return;
    const productId = selectedProduct.id;
    await registrarMovimiento(productId, data);
    setShowForm(false);
    await refreshAfterOperation(productId, 'El movimiento se registró');
  }

  async function saveTransfer(data: TrasladoExistenciasPayload) {
    if (!selectedProduct) return;
    const productId = selectedProduct.id;
    await registrarTraslado(productId, data);
    setShowTransferForm(false);
    await refreshAfterOperation(productId, 'El traslado se registró');
  }

  const movementLabel = (movement: Movimiento) =>
    movement.movement_type === 'entry'
      ? 'Ingreso'
      : movement.movement_type === 'exit'
        ? 'Extracción'
        : 'Conteo / ajuste';

  const locationLabel = (locationId: number | null) =>
    locationId === null
      ? 'Sin ubicación identificada'
      : locationNames.get(locationId) || 'Ubicación';

  const transferLocationLabel = (
    locationId: number | null,
    name: string | null,
    parentName: string | null,
  ) => {
    if (locationId === null) return 'Sin ubicación identificada';
    if (parentName && name) return `${parentName} / ${name}`;
    return name || locationNames.get(locationId) || 'Ubicación';
  };

  return (
    <div className="mx-auto max-w-7xl space-y-6 p-4 md:p-7">
      <h1 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-slate-100">Movimientos</h1>

      {error && (
        <p className="rounded-lg border border-red-200 dark:border-red-900 bg-red-50 dark:bg-red-950/60 px-4 py-3 text-sm text-red-700 dark:text-red-300">
          {error}
        </p>
      )}

      <div className="grid gap-5 lg:grid-cols-[340px_minmax(0,1fr)]">
        <section className="overflow-hidden rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900">
          <div className="space-y-3 border-b border-slate-100 dark:border-slate-800 p-4">
            <div>
              <h3 className="font-semibold">Artículos por cantidad</h3>
              <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                {filteredProducts.length} de {products.length} artículos
              </p>
            </div>
            <label className="flex items-center gap-2 rounded-lg border border-slate-200 dark:border-slate-700 px-3 py-2.5">
              <Search size={16} className="shrink-0 text-slate-400 dark:text-slate-400" />
              <input
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder="Buscar artículo..."
                className="min-w-0 flex-1 text-sm outline-none"
              />
            </label>
          </div>

          {loading ? (
            <p className="p-5 text-sm text-slate-500 dark:text-slate-400">Cargando artículos...</p>
          ) : filteredProducts.length === 0 ? (
            <p className="p-5 text-sm text-slate-500 dark:text-slate-400">No se encontraron artículos con esa búsqueda.</p>
          ) : (
            <div className="max-h-[650px] divide-y divide-slate-100 dark:divide-slate-800 overflow-y-auto">
              {filteredProducts.map((product) => (
                <button
                  key={product.id}
                  type="button"
                  onClick={() => setSelectedProduct(product)}
                  className={`w-full p-4 text-left transition hover:bg-slate-50 dark:hover:bg-slate-800 ${
                    selectedProduct?.id === product.id ? 'bg-blue-50 dark:bg-blue-950' : ''
                  }`}
                >
                  <p className="text-sm font-semibold text-slate-900 dark:text-slate-100">
                    {product.name || `Artículo #${product.id}`}
                  </p>
                  <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                    {[product.brand, product.model].filter(Boolean).join(' · ') ||
                      product.category_name || 'Sin clasificación'}
                  </p>
                  <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                    {product.stock_verified
                      ? `Saldo conocido: ${formatQuantity(product.total_stock ?? 0)}`
                      : 'Conteo inicial pendiente'}
                  </p>
                </button>
              ))}
            </div>
          )}
        </section>

        <section className="min-w-0 overflow-hidden rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900">
          {!selectedProduct ? (
            <div className="flex min-h-72 flex-col items-center justify-center p-8 text-center">
              <ClipboardList size={34} className="text-slate-300 dark:text-slate-500" />
              <h3 className="mt-3 font-semibold">Seleccioná un artículo</h3>
              <p className="mt-1 max-w-sm text-sm text-slate-500 dark:text-slate-400">
                Consultá su historial o registrá una actualización de existencias.
              </p>
            </div>
          ) : (
            <>
              <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 dark:border-slate-800 p-5">
                <div>
                  <h3 className="font-semibold">{selectedProduct.name || `Artículo #${selectedProduct.id}`}</h3>
                  <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                    Historial de ingresos, extracciones, conteos y traslados
                  </p>
                </div>
                <div className="flex flex-wrap gap-2">
                  <button
                    type="button"
                    onClick={() => setShowForm(true)}
                    className="inline-flex items-center gap-2 rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-900 px-3 py-2.5 text-sm font-semibold text-slate-700 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-slate-800"
                  >
                    <Plus size={16} />
                    Actualizar existencias
                  </button>
                  <button
                    type="button"
                    onClick={() => setShowTransferForm(true)}
                    className="inline-flex items-center gap-2 rounded-lg bg-blue-700 dark:bg-blue-600 px-3 py-2.5 text-sm font-semibold text-white hover:bg-blue-800"
                  >
                    <ArrowLeftRight size={16} />
                    Trasladar
                  </button>
                </div>
              </div>

              <div className="overflow-x-auto">
                <table className="w-full min-w-[820px] text-left text-sm">
                  <thead className="bg-slate-50 dark:bg-slate-950 text-xs text-slate-500 dark:text-slate-400">
                    <tr>
                      <th className="px-4 py-3 font-medium">Fecha</th>
                      <th className="px-4 py-3 font-medium">Operación</th>
                      <th className="px-4 py-3 font-medium">Ubicación / recorrido</th>
                      <th className="px-4 py-3 font-medium">Cantidad</th>
                      <th className="px-4 py-3 font-medium">Antes</th>
                      <th className="px-4 py-3 font-medium">Después</th>
                      <th className="px-4 py-3 font-medium">Observación</th>
                    </tr>
                  </thead>
                  <tbody>
                    {history.map((record) => {
                      if (record.kind === 'transfer') {
                        const transfer = record.item;
                        return (
                          <tr key={`transfer-${transfer.id}`} className="border-t border-slate-100 dark:border-slate-800">
                            <td className="whitespace-nowrap px-4 py-3 text-xs text-slate-500 dark:text-slate-400">
                              {new Date(transfer.created_at).toLocaleString('es-PY')}
                              {transfer.created_by && <span className="block text-slate-400">por {transfer.created_by}</span>}
                            </td>
                            <td className="px-4 py-3">
                              <span className="inline-flex items-center gap-1.5 font-medium">
                                <ArrowLeftRight size={15} className="text-blue-700 dark:text-blue-300" />
                                Traslado
                              </span>
                            </td>
                            <td className="px-4 py-3 text-xs text-slate-600 dark:text-slate-300">
                              <span className="block">Desde: {transferLocationLabel(transfer.source_location_id, transfer.source_location_name, transfer.source_parent_name)}</span>
                              <span className="mt-1 block">Hacia: {transferLocationLabel(transfer.destination_location_id, transfer.destination_location_name, transfer.destination_parent_name)}</span>
                            </td>
                            <td className="px-4 py-3 font-semibold tabular-nums">{formatQuantity(transfer.quantity)}</td>
                            <td className="px-4 py-3 text-xs tabular-nums">
                              <span className="block">Origen: {formatQuantity(transfer.source_quantity_before)}</span>
                              <span className="mt-1 block">Destino: {formatQuantity(transfer.destination_quantity_before)}</span>
                            </td>
                            <td className="px-4 py-3 text-xs tabular-nums">
                              <span className="block">Origen: {formatQuantity(transfer.source_quantity_after)}</span>
                              <span className="mt-1 block">Destino: {formatQuantity(transfer.destination_quantity_after)}</span>
                            </td>
                            <td className="px-4 py-3 text-xs text-slate-500 dark:text-slate-400">{transfer.note || '—'}</td>
                          </tr>
                        );
                      }

                      const movement = record.item;
                      return (
                        <tr key={`movement-${movement.id}`} className="border-t border-slate-100 dark:border-slate-800">
                          <td className="whitespace-nowrap px-4 py-3 text-xs text-slate-500 dark:text-slate-400">
                            {new Date(movement.created_at).toLocaleString('es-PY')}
                            {movement.created_by && <span className="block text-slate-400">por {movement.created_by}</span>}
                          </td>
                          <td className="px-4 py-3">
                            <span className="inline-flex items-center gap-1.5">
                              {movement.movement_type === 'entry' ? (
                                <ArrowDownLeft size={15} className="text-emerald-600 dark:text-emerald-400" />
                              ) : movement.movement_type === 'exit' ? (
                                <ArrowUpRight size={15} className="text-red-600 dark:text-red-400" />
                              ) : (
                                <ClipboardList size={15} className="text-blue-600 dark:text-blue-400" />
                              )}
                              {movementLabel(movement)}
                            </span>
                          </td>
                          <td className="px-4 py-3 text-slate-600 dark:text-slate-300">{locationLabel(movement.location_id)}</td>
                          <td className="px-4 py-3 font-semibold tabular-nums">
                            {formatQuantity(movement.quantity)}
                            {movement.movement_type === 'count' && (
                              <span className="ml-1 text-xs font-normal text-slate-500 dark:text-slate-400">físico</span>
                            )}
                          </td>
                          <td className="px-4 py-3 tabular-nums">{formatQuantity(movement.quantity_before)}</td>
                          <td className="px-4 py-3 tabular-nums">{formatQuantity(movement.quantity_after)}</td>
                          <td className="px-4 py-3 text-xs text-slate-500 dark:text-slate-400">{movement.note || '—'}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>

                {history.length === 0 && (
                  <p className="p-8 text-center text-sm text-slate-500 dark:text-slate-400">
                    Este artículo todavía no tiene movimientos ni traslados registrados.
                  </p>
                )}
              </div>
            </>
          )}
        </section>
      </div>

      {showForm && selectedProduct && (
        <StockMovementModal
          articulo={selectedProduct}
          ubicaciones={locations}
          onClose={() => setShowForm(false)}
          onSave={saveMovement}
        />
      )}

      {showTransferForm && selectedProduct && (
        <StockTransferModal
          articulo={selectedProduct}
          ubicaciones={locations}
          onClose={() => setShowTransferForm(false)}
          onSave={saveTransfer}
        />
      )}
    </div>
  );
}
