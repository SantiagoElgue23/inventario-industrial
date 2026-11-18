import { useCallback, useMemo, useState } from 'react';
import { Bot, ChevronRight, Plus, Search } from 'lucide-react';
import AssetFormModal from '../components/inventory/AssetFormModal';
import AssetDetailDrawer from '../components/inventory/AssetDetailDrawer';
import {
  archivarActivo,
  actualizarActivo,
  crearActivo,
  crearAsociacion,
  finalizarAsociacion,
  obtenerActivo,
  obtenerActivos,
  obtenerProductos,
  obtenerRobots,
  obtenerUbicaciones,
} from '../services/inventoryService';
import type { Activo, ActivoDetalle, ActivoPayload, Producto, Ubicacion } from '../types/inventory';

import { useLoadEffect } from '../hooks/useLoadEffect';
const normalize = (value: string) =>
  value.toLocaleLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '');

export default function RobotsPage() {
  const [models, setModels] = useState<Producto[]>([]);
  const [individualProducts, setIndividualProducts] = useState<Producto[]>([]);
  const [assets, setAssets] = useState<Activo[]>([]);
  const [locations, setLocations] = useState<Ubicacion[]>([]);
  const [selectedModel, setSelectedModel] = useState<Producto | null>(null);
  const [selectedAsset, setSelectedAsset] = useState<ActivoDetalle | null>(null);
  const [assetForm, setAssetForm] = useState<ActivoDetalle | null | undefined>(undefined);
  const [initialProductId, setInitialProductId] = useState<number | null>(null);
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const [robotModels, individual, allAssets, locs] = await Promise.all([
        obtenerRobots(),
        obtenerProductos({ tracking_mode: 'individual' }),
        obtenerActivos({ include_non_stock: true }),
        obtenerUbicaciones(),
      ]);
      setModels(robotModels);
      setIndividualProducts(individual);
      setAssets(allAssets);
      setLocations(locs);
      setSelectedModel((current) => current ? robotModels.find((m) => m.id === current.id) ?? null : null);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'No se pudieron cargar los robots.');
    } finally {
      setLoading(false);
    }
  }, []);

  useLoadEffect(load);

  const filtered = useMemo(() => {
    const terms = normalize(search.trim()).split(/\s+/).filter(Boolean);
    return models.filter((model) => {
      const content = normalize([model.name, model.brand, model.model, model.category_name, model.component_type_name].filter(Boolean).join(' '));
      return terms.every((term) => content.includes(term));
    });
  }, [models, search]);

  async function openAsset(id: number) {
    try {
      setError('');
      setSelectedAsset(await obtenerActivo(id));
    } catch (e) {
      setError(e instanceof Error ? e.message : 'No se pudo abrir el activo.');
    }
  }

  async function saveAsset(payload: ActivoPayload & { asset_code_prefix?: string | null }) {
    if (assetForm) await actualizarActivo(assetForm.id, payload);
    else await crearActivo(payload);
    setAssetForm(undefined);
    setInitialProductId(null);
    await load();
    if (selectedModel) {
      const refreshed = await obtenerRobots();
      setSelectedModel(refreshed.find((m) => m.id === selectedModel.id) ?? null);
    }
  }

  async function archiveAsset(asset: ActivoDetalle) {
    if (!window.confirm(`¿Archivar ${asset.asset_code}? Se conservarán sus datos e historial.`)) return;
    try {
      await archivarActivo(asset.id);
      setSelectedAsset(null);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'No se pudo archivar el activo.');
    }
  }

  async function addRelationship(targetId: number, role: string) {
    if (!selectedAsset) return;
    await crearAsociacion(selectedAsset.id, { target_asset_id: targetId, relationship_type: role, note: null });
    setSelectedAsset(await obtenerActivo(selectedAsset.id));
    await load();
  }

  async function endRelationship(relationshipId: number) {
    if (!selectedAsset) return;
    await finalizarAsociacion(selectedAsset.id, relationshipId);
    setSelectedAsset(await obtenerActivo(selectedAsset.id));
    await load();
  }

  return (
    <div className="mx-auto max-w-7xl space-y-6 p-4 md:p-7">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <h1 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-slate-100">Robots</h1>
        <div className="rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 px-4 py-3 text-right">
          <p className="text-xs text-slate-500 dark:text-slate-400">Modelos registrados</p><p className="text-xl font-bold">{models.length}</p>
        </div>
      </div>

      {error && <p className="rounded-lg border border-red-200 dark:border-red-900 bg-red-50 dark:bg-red-950/60 px-4 py-3 text-sm text-red-700 dark:text-red-300">{error}</p>}

      <div className="grid gap-5 lg:grid-cols-[320px_minmax(0,1fr)]">
        <section className="overflow-hidden rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900">
          <div className="border-b border-slate-100 dark:border-slate-800 p-4">
            <h3 className="font-semibold">Modelos de robot</h3>
            <div className="mt-3 flex items-center gap-2 rounded-lg border border-slate-200 dark:border-slate-700 px-3 py-2"><Search size={16} className="text-slate-400 dark:text-slate-400" /><input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Buscar modelo..." className="w-full min-w-0 text-sm outline-none" /></div>
          </div>
          {loading ? <p className="p-5 text-sm text-slate-500 dark:text-slate-400">Cargando modelos...</p> : filtered.length === 0 ? <p className="p-5 text-sm text-slate-500 dark:text-slate-400">No hay modelos clasificados como robots. Revisá la categoría o el tipo de componente del catálogo.</p> : (
            <div className="divide-y divide-slate-100 dark:divide-slate-800">
              {filtered.map((model) => (
                <button key={model.id} type="button" onClick={() => setSelectedModel(model)} className={`flex w-full items-center gap-3 p-4 text-left hover:bg-slate-50 dark:hover:bg-slate-800 ${selectedModel?.id === model.id ? 'bg-blue-50 dark:bg-blue-950' : ''}`}>
                  <span className="rounded-lg bg-blue-50 dark:bg-blue-950 p-2 text-blue-700 dark:text-blue-300"><Bot size={19} /></span>
                  <span className="min-w-0 flex-1"><span className="block truncate text-sm font-semibold">{model.name || `Modelo #${model.id}`}</span><span className="mt-1 block truncate text-xs text-slate-500 dark:text-slate-400">{[model.brand, model.model].filter(Boolean).join(' · ') || 'Sin marca / modelo'}</span><span className="mt-1 block text-xs text-slate-500 dark:text-slate-400">{model.assets.length} unidades físicas</span></span>
                  <ChevronRight size={17} className="text-slate-400 dark:text-slate-400" />
                </button>
              ))}
            </div>
          )}
        </section>

        <section className="min-w-0 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900">
          {!selectedModel ? (
            <div className="flex min-h-80 flex-col items-center justify-center p-8 text-center">
              <Bot size={36} className="text-slate-300 dark:text-slate-500" />
              <h3 className="mt-3 font-semibold">Seleccioná un modelo</h3>
              <p className="mt-1 max-w-sm text-sm text-slate-500 dark:text-slate-400">Elegí un modelo a la izquierda para consultar sus unidades, series y componentes.</p>
            </div>
          ) : (
            <>
              <div className="flex flex-wrap items-start justify-between gap-3 border-b border-slate-100 dark:border-slate-800 p-5">
                <div><h3 className="text-xl font-bold">{selectedModel.name || `Modelo #${selectedModel.id}`}</h3><p className="mt-1 text-sm text-slate-500 dark:text-slate-400">{[selectedModel.brand, selectedModel.model].filter(Boolean).join(' · ') || 'Marca / modelo sin especificar'}</p>{selectedModel.description && <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">{selectedModel.description}</p>}</div>
                <button onClick={() => { setInitialProductId(selectedModel.id); setAssetForm(null); }} className="inline-flex items-center gap-2 rounded-lg bg-blue-700 dark:bg-blue-600 px-3 py-2.5 text-sm font-semibold text-white"><Plus size={16} />Agregar unidad</button>
              </div>
              <div className="grid gap-3 p-5 sm:grid-cols-3">
                <div className="rounded-lg bg-slate-50 dark:bg-slate-950 p-3"><p className="text-xs text-slate-500 dark:text-slate-400">Unidades activas</p><p className="mt-1 text-xl font-bold">{selectedModel.assets.length}</p></div>
                <div className="rounded-lg bg-slate-50 dark:bg-slate-950 p-3"><p className="text-xs text-slate-500 dark:text-slate-400">Prefijo de código</p><p className="mt-1 text-xl font-bold">{selectedModel.asset_code_prefix || '—'}</p></div>
                <div className="rounded-lg bg-slate-50 dark:bg-slate-950 p-3"><p className="text-xs text-slate-500 dark:text-slate-400">Tipo</p><p className="mt-1 text-sm font-bold">{selectedModel.component_type_name || 'Sin tipo'}</p></div>
              </div>
              <div className="px-5 pb-5">
                <h4 className="mb-3 font-semibold">Unidades físicas de este modelo</h4>
                {selectedModel.assets.length === 0 ? <p className="rounded-lg bg-slate-50 dark:bg-slate-950 p-5 text-sm text-slate-500 dark:text-slate-400">Todavía no hay unidades. Usá «Agregar unidad» para registrar un robot físico y generar su código interno.</p> : (
                  <div className="overflow-x-auto rounded-lg border border-slate-200 dark:border-slate-700">
                    <table className="w-full min-w-[700px] text-left text-sm">
                      <thead className="bg-slate-50 dark:bg-slate-950 text-xs text-slate-500 dark:text-slate-400"><tr><th className="px-4 py-3">Código interno</th><th className="px-4 py-3">Número de serie del fabricante</th><th className="px-4 py-3">Ubicación</th><th className="px-4 py-3">Estado</th><th className="px-4 py-3" /></tr></thead>
                      <tbody>
                        {selectedModel.assets.map((asset) => (
                          <tr key={asset.id} className="border-t border-slate-100 dark:border-slate-800">
                            <td className="px-4 py-3 font-mono text-xs font-semibold text-blue-700 dark:text-blue-300">{asset.asset_code}</td>
                            <td className="px-4 py-3">{asset.manufacturer_serial || 'No registrado'}</td>
                            <td className="px-4 py-3 text-slate-600 dark:text-slate-300">{asset.location_name || 'Sin ubicación'}</td>
                            <td className="px-4 py-3 text-slate-600 dark:text-slate-300">{asset.functional_status === 'functional' ? 'Operativo' : asset.functional_status === 'unverified' ? 'Sin verificar' : asset.functional_status}</td>
                            <td className="px-4 py-3"><button onClick={() => void openAsset(asset.id)} className="rounded-lg px-3 py-2 text-xs font-semibold text-blue-700 dark:text-blue-300 hover:bg-blue-50 dark:hover:bg-blue-950">Ver unidad</button></td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            </>
          )}
        </section>
      </div>

      <AssetDetailDrawer
        activo={selectedAsset}
        activosDisponibles={assets}
        productos={individualProducts}
        onClose={() => setSelectedAsset(null)}
        onEdit={(a) => { setSelectedAsset(null); setAssetForm(a); }}
        onArchive={(a) => void archiveAsset(a)}
        onAddRelationship={addRelationship}
        onEndRelationship={endRelationship}
      />

      {assetForm !== undefined && (
        <AssetFormModal
          activo={assetForm}
          productos={individualProducts}
          ubicaciones={locations}
          initialProductId={initialProductId}
          onClose={() => { setAssetForm(undefined); setInitialProductId(null); }}
          onSave={saveAsset}
        />
      )}
    </div>
  );
}
