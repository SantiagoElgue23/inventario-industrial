import { useCallback, useEffect, useState } from 'react';
import { Archive, Plus, Pencil, Settings2, Tags, X } from 'lucide-react';
import {
  actualizarCaracteristica,
  crearCaracteristica,
  crearCategoria,
  crearTipo,
  desactivarCaracteristica,
  desactivarCategoria,
  desactivarTipo,
  obtenerCaracteristicas,
  obtenerCategorias,
  obtenerTipos,
  renombrarCategoria,
  renombrarTipo,
} from '../services/inventoryService';
import AccountsPanel from '../auth/AccountsPanel';
import type { Categoria, DefinicionCaracteristica, TipoComponente } from '../types/inventory';

import { useLoadEffect } from '../hooks/useLoadEffect';
type Tab = 'categories' | 'types';

export default function AdminPage() {
  const [tab, setTab] = useState<Tab>('categories');
  const [categorias, setCategorias] = useState<Categoria[]>([]);
  const [tipos, setTipos] = useState<TipoComponente[]>([]);
  const [tipoSeleccionado, setTipoSeleccionado] = useState<number | null>(null);
  const [caracteristicas, setCaracteristicas] = useState<DefinicionCaracteristica[]>([]);
  const [nuevoNombre, setNuevoNombre] = useState('');
  const [nuevoAtributo, setNuevoAtributo] = useState('');
  const [unidad, setUnidad] = useState('');
  const [dataType, setDataType] = useState<'text' | 'number' | 'boolean' | 'date'>('text');
  const [error, setError] = useState('');
  const [mensaje, setMensaje] = useState('');
  const [cargando, setCargando] = useState(true);

  const cargar = useCallback(async () => {
    setCargando(true);
    setError('');
    try {
      const [cats, componentTypes] = await Promise.all([obtenerCategorias(), obtenerTipos()]);
      setCategorias(cats);
      setTipos(componentTypes);
      if (tipoSeleccionado && !componentTypes.some((t) => t.id === tipoSeleccionado)) {
        setTipoSeleccionado(null);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'No se pudo cargar la administración.');
    } finally {
      setCargando(false);
    }
  }, [tipoSeleccionado]);

  useLoadEffect(cargar);

  useEffect(() => {
    if (!tipoSeleccionado) return;
    let current = true;
    obtenerCaracteristicas(tipoSeleccionado)
      .then((items) => current && setCaracteristicas(items))
      .catch((e: Error) => current && setError(e.message));
    return () => { current = false; };
  }, [tipoSeleccionado]);

  async function ejecutar(action: () => Promise<unknown>, success: string) {
    setError('');
    setMensaje('');
    try {
      await action();
      setMensaje(success);
      await cargar();
      if (tipoSeleccionado) setCaracteristicas(await obtenerCaracteristicas(tipoSeleccionado));
    } catch (e) {
      setError(e instanceof Error ? e.message : 'No se pudo completar la operación.');
    }
  }

  async function agregarPrincipal() {
    if (!nuevoNombre.trim()) return;
    if (tab === 'categories') {
      await ejecutar(() => crearCategoria(nuevoNombre.trim()), 'Categoría creada.');
    } else {
      await ejecutar(() => crearTipo(nuevoNombre.trim()), 'Tipo de componente creado.');
    }
    setNuevoNombre('');
  }

  async function renombrar(id: number, actual: string) {
    const name = window.prompt('Nuevo nombre:', actual);
    if (!name?.trim() || name.trim() === actual) return;
    if (tab === 'categories') await ejecutar(() => renombrarCategoria(id, name.trim()), 'Categoría actualizada.');
    else await ejecutar(() => renombrarTipo(id, name.trim()), 'Tipo actualizado.');
  }

  async function desactivar(id: number, actual: string) {
    if (!window.confirm(`¿Desactivar "${actual}"? Los artículos existentes conservarán su clasificación.`)) return;
    if (tab === 'categories') await ejecutar(() => desactivarCategoria(id), 'Categoría desactivada.');
    else await ejecutar(() => desactivarTipo(id), 'Tipo desactivado.');
  }

  async function agregarCaracteristica() {
    if (!tipoSeleccionado || !nuevoAtributo.trim()) return;
    await ejecutar(() => crearCaracteristica(tipoSeleccionado, {
      name: nuevoAtributo.trim(),
      data_type: dataType,
      unit: unidad.trim() || null,
      required: false,
    }), 'Característica agregada.');
    setNuevoAtributo('');
    setUnidad('');
    setDataType('text');
  }

  async function editarCaracteristica(item: DefinicionCaracteristica) {
    const name = window.prompt('Nombre de la característica:', item.name);
    if (!name?.trim()) return;
    const unit = window.prompt('Unidad (dejar vacío si no aplica):', item.unit ?? '');
    if (unit === null) return;
    await ejecutar(() => actualizarCaracteristica(item.id, {
      name: name.trim(),
      data_type: item.data_type,
      unit: unit.trim() || null,
      required: item.required,
    }), 'Característica actualizada.');
  }

  async function quitarCaracteristica(item: DefinicionCaracteristica) {
    if (!window.confirm(`¿Desactivar "${item.name}"? Los valores existentes se conservarán.`)) return;
    await ejecutar(() => desactivarCaracteristica(item.id), 'Característica desactivada.');
  }

  const lista = tab === 'categories' ? categorias : tipos;

  return (
    <div className="mx-auto max-w-6xl space-y-6 p-4 md:p-7">
      <h1 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-slate-100">Administración</h1>
      <AccountsPanel />

      <div className="flex gap-2 border-b border-slate-200 dark:border-slate-700">
        <button onClick={() => setTab('categories')} className={`inline-flex items-center gap-2 border-b-2 px-4 py-3 text-sm font-medium ${tab === 'categories' ? 'border-blue-700 dark:border-blue-600 text-blue-700 dark:text-blue-300' : 'border-transparent text-slate-500 dark:text-slate-400'}`}><Tags size={17} />Categorías</button>
        <button onClick={() => setTab('types')} className={`inline-flex items-center gap-2 border-b-2 px-4 py-3 text-sm font-medium ${tab === 'types' ? 'border-blue-700 dark:border-blue-600 text-blue-700 dark:text-blue-300' : 'border-transparent text-slate-500 dark:text-slate-400'}`}><Settings2 size={17} />Tipos de componente</button>
      </div>

      {error && <p className="rounded-lg border border-red-200 dark:border-red-900 bg-red-50 dark:bg-red-950/60 px-4 py-3 text-sm text-red-700 dark:text-red-300">{error}</p>}
      {mensaje && <p className="rounded-lg border border-emerald-200 dark:border-emerald-900 bg-emerald-50 dark:bg-emerald-950/60 px-4 py-3 text-sm text-emerald-700 dark:text-emerald-300">{mensaje}</p>}

      <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_minmax(320px,0.85fr)]">
        <section className="overflow-hidden rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900">
          <div className="border-b border-slate-100 dark:border-slate-800 p-4">
            <h3 className="font-semibold">{tab === 'categories' ? 'Categorías' : 'Tipos de componente'}</h3>
            <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">{lista.length} registros activos</p>
          </div>
          <form onSubmit={(e) => { e.preventDefault(); void agregarPrincipal(); }} className="flex gap-2 border-b border-slate-100 dark:border-slate-800 p-4">
            <input value={nuevoNombre} onChange={(e) => setNuevoNombre(e.target.value)} placeholder={tab === 'categories' ? 'Nueva categoría' : 'Nuevo tipo de componente'} className="min-w-0 flex-1 rounded-lg border border-slate-300 dark:border-slate-600 px-3 py-2.5 text-sm" />
            <button className="inline-flex items-center gap-1 rounded-lg bg-blue-700 dark:bg-blue-600 px-3 py-2 text-sm font-semibold text-white"><Plus size={16} />Agregar</button>
          </form>
          {cargando ? <p className="p-6 text-sm text-slate-500 dark:text-slate-400">Cargando...</p> : (
            <div className="divide-y divide-slate-100 dark:divide-slate-800">
              {lista.map((item) => (
                <div key={item.id} className={`flex items-center justify-between gap-3 p-4 ${tab === 'types' && tipoSeleccionado === item.id ? 'bg-blue-50 dark:bg-blue-950' : ''}`}>
                  <button type="button" onClick={() => tab === 'types' && setTipoSeleccionado(item.id)} className="min-w-0 flex-1 text-left">
                    <p className="truncate text-sm font-semibold">{item.name}</p>
                    <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">{item.product_count} artículos asociados</p>
                  </button>
                  <div className="flex shrink-0 gap-1">
                    <button type="button" onClick={() => void renombrar(item.id, item.name)} title="Renombrar" className="rounded-lg p-2 text-slate-500 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800"><Pencil size={16} /></button>
                    <button type="button" onClick={() => void desactivar(item.id, item.name)} title="Desactivar" className="rounded-lg p-2 text-slate-500 dark:text-slate-400 hover:bg-red-50 dark:hover:bg-red-950 hover:text-red-700 dark:hover:text-red-300"><Archive size={16} /></button>
                  </div>
                </div>
              ))}
              {lista.length === 0 && <p className="p-6 text-sm text-slate-500 dark:text-slate-400">Todavía no hay registros.</p>}
            </div>
          )}
        </section>

        {tab === 'types' ? (
          <section className="rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 p-4">
            <h3 className="font-semibold">Características técnicas</h3>
            {!tipoSeleccionado ? <p className="mt-3 text-sm text-slate-500 dark:text-slate-400">Seleccioná un tipo de componente para administrar sus características.</p> : <>
              <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">{tipos.find((t) => t.id === tipoSeleccionado)?.name}</p>
              <form onSubmit={(e) => { e.preventDefault(); void agregarCaracteristica(); }} className="mt-4 space-y-2 rounded-lg bg-slate-50 dark:bg-slate-950 p-3">
                <input value={nuevoAtributo} onChange={(e) => setNuevoAtributo(e.target.value)} placeholder="Nombre: tensión nominal" className="w-full rounded-lg border border-slate-300 dark:border-slate-600 px-3 py-2 text-sm" />
                <div className="grid grid-cols-2 gap-2">
                  <select value={dataType} onChange={(e) => setDataType(e.target.value as typeof dataType)} className="rounded-lg border border-slate-300 dark:border-slate-600 px-2 py-2 text-sm"><option value="text">Texto</option><option value="number">Número</option><option value="boolean">Sí / No</option><option value="date">Fecha</option></select>
                  <input value={unidad} onChange={(e) => setUnidad(e.target.value)} placeholder="Unidad (V, A, mm...)" className="min-w-0 rounded-lg border border-slate-300 dark:border-slate-600 px-2 py-2 text-sm" />
                </div>
                <button className="w-full rounded-lg bg-blue-700 dark:bg-blue-600 px-3 py-2 text-sm font-semibold text-white">Agregar característica</button>
              </form>
              <div className="mt-4 space-y-2">
                {caracteristicas.length === 0 ? <p className="text-sm text-slate-500 dark:text-slate-400">Todavía no hay características definidas.</p> : caracteristicas.map((item) => (
                  <div key={item.id} className="flex items-center justify-between gap-2 rounded-lg border border-slate-200 dark:border-slate-700 p-3">
                    <div className="min-w-0"><p className="text-sm font-medium">{item.name}</p><p className="text-xs text-slate-500 dark:text-slate-400">{item.data_type}{item.unit ? ` · ${item.unit}` : ''}</p></div>
                    <div className="flex gap-1">
                      <button type="button" onClick={() => void editarCaracteristica(item)} title="Editar" className="rounded-lg p-2 text-slate-500 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800"><Pencil size={15} /></button>
                      <button type="button" onClick={() => void quitarCaracteristica(item)} title="Desactivar" className="rounded-lg p-2 text-slate-500 dark:text-slate-400 hover:bg-red-50 dark:hover:bg-red-950 hover:text-red-700 dark:hover:text-red-300"><X size={15} /></button>
                    </div>
                  </div>
                ))}
              </div>
            </>}
          </section>
        ) : (
          <section className="rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-950 p-5">
            <h3 className="font-semibold">Criterio de clasificación</h3>
            <p className="mt-2 text-sm leading-6 text-slate-600 dark:text-slate-300">Las categorías organizan el inventario. Los tipos de componente se reutilizan en distintas categorías y definen las características técnicas disponibles en los formularios.</p>
            <p className="mt-3 text-xs text-slate-500 dark:text-slate-400">Desactivar una categoría no elimina ni modifica los artículos que ya la utilizan.</p>
          </section>
        )}
      </div>
    </div>
  );
}
