import { useAuth } from '../auth/useAuth';
import { useCallback, useEffect, useMemo, useRef, useState, type FormEvent } from 'react';
import { Check, ChevronDown, ChevronUp, ClipboardList, FileDown, Minus, Plus, RefreshCw, Search, X } from 'lucide-react';
import {
  cerrarTrabajo, crearTrabajo, despacharTrabajo, devolverTrabajo, eliminarBorradorTrabajo,
  obtenerActivosParaTrabajo, obtenerExistenciasProducto, obtenerTrabajo,
  obtenerTrabajos, prepararTrabajo, quitarPreparadoTrabajo, urlPdfTrabajo,
} from '../services/inventoryService';
import type { ExistenciaUbicacion, Producto, Trabajo, TrabajoDetalle } from '../types/inventory';
import { rankMatch } from '../utils/catalogSearch';

import { useLoadEffect } from '../hooks/useLoadEffect';
type WorkProductSelection = {
  product_id: number;
  origin_location_id: number | null;
  name: string;
  location: string;
  quantity: string;
};

type AvailableAsset = {id:number; asset_code:string; name:string; serial:string|null};
const formInput = 'w-full rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-900 px-3 py-2 text-sm outline-none focus:border-blue-500 dark:focus:border-blue-400';
const blue = 'rounded-lg bg-blue-700 dark:bg-blue-600 px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-40';
const secondary = 'rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-900 px-3 py-2 text-sm hover:bg-slate-50 dark:hover:bg-slate-800 disabled:opacity-40';
const num = (x: number) => new Intl.NumberFormat('es-PY', {maximumFractionDigits:3}).format(x);
const date = (v:string|null) => v ? new Date(v + 'T00:00:00').toLocaleDateString('es-PY') : 'Sin definir';

export default function ProjectWorksPanel({projectId, products}: {projectId:number; products:Producto[]}) {
  const { canViewPrices } = useAuth();
  const [works,setWorks] = useState<Trabajo[]>([]);
  const [work,setWork] = useState<TrabajoDetalle|null>(null);
  const [openingWork,setOpeningWork] = useState<number|null>(null);
  const workRequest = useRef(0);
  const [creating,setCreating] = useState(false);
  const [newName,setNewName] = useState('');
  const [newDescription,setNewDescription] = useState('');
  const [responsible,setResponsible] = useState('');
  const [outDate,setOutDate] = useState('');
  const [returnDate,setReturnDate] = useState('');
  const [busy,setBusy] = useState(false);
  const [error,setError] = useState('');
  const [search,setSearch] = useState('');
  const [choice,setChoice] = useState('');
  const [balances,setBalances] = useState<ExistenciaUbicacion[]>([]);
  const [fromLocation,setFromLocation] = useState('');
  // No reutilizar existencias de un artículo previamente seleccionado.
  const selectChoice=(value:string)=>{setChoice(value);setBalances([]);setFromLocation('');};
  const [qty,setQty] = useState('1');
  const [preparedProducts,setPreparedProducts] = useState<WorkProductSelection[]>([]);
  const [availableAssets,setAvailableAssets] = useState<AvailableAsset[]>([]);
  const [assetSearch,setAssetSearch] = useState('');
  const [preparedAssets,setPreparedAssets] = useState<number[]>([]);
  const [notReturned,setNotReturned] = useState<Record<number,string>>({});
  const [returnAssets,setReturnAssets] = useState<number[]>([]);
  const [classification,setClassification] = useState<Record<number,'consumed'|'lost'>>({});
  const [closeNote,setCloseNote] = useState('');

  const refresh = useCallback(async (id?:number|null) => {
    const rows = await obtenerTrabajos(projectId);
    setWorks(rows);
    if (id) setWork(await obtenerTrabajo(id));
  },[projectId]);
  const refreshAssets = useCallback(async ()=>setAvailableAssets(await obtenerActivosParaTrabajo(projectId)),[projectId]);
  useEffect(()=>{
    ++workRequest.current;
    let cancelled=false;
    void obtenerTrabajos(projectId).then(rows=>{if(!cancelled){setWorks(rows);setWork(null);setError('');}})
      .catch(e=>{if(!cancelled)setError(e instanceof Error?e.message:'No se cargaron los trabajos');});
    return ()=>{cancelled=true;};
  },[projectId]);
  useLoadEffect(useCallback(()=>refreshAssets().catch(()=>{}),[refreshAssets]));
  useEffect(()=>{
    if (!choice) return;
    let alive=true;
    void obtenerExistenciasProducto(Number(choice)).then(rows=>{
      if(alive){const verified=rows.filter(r=>r.verified && Number(r.quantity)>0);setBalances(verified);setFromLocation(verified.length ? String(verified[0].location_id ?? 'none') : '');}
    }).catch(e=>{if(alive)setError(e instanceof Error?e.message:'No se leyeron las existencias');});
    return ()=>{alive=false;};
  },[choice]);

  async function run(operation:()=>Promise<TrabajoDetalle>,after?:()=>void) {
    setBusy(true);setError('');
    try {const updated=await operation();setWork(updated);await refresh(updated.id);await refreshAssets();after?.();}
    catch(e){setError(e instanceof Error?e.message:'No se pudo completar la operación');}
    finally{setBusy(false);}
  }
  async function submitNew(e:FormEvent) {
    e.preventDefault();setBusy(true);setError('');
    try {
      const created=await crearTrabajo(projectId,{
        name:newName.trim(), description:newDescription.trim()||null, responsible:responsible.trim()||null,
        planned_out_date:outDate||null, planned_return_date:returnDate||null,
      });
      await refresh(created.id);
      setCreating(false);setNewName('');setNewDescription('');setResponsible('');setOutDate('');setReturnDate('');
    }catch(e){setError(e instanceof Error?e.message:'No se pudo crear el trabajo');}
    finally{setBusy(false);}
  }
  // Sin límites artificiales: todos los artículos y unidades pueden localizarse.
  // Los resultados se ordenan por relevancia al buscar y alfabéticamente en reposo.
  const quantityProducts = useMemo(() => products
    .filter(p => p.active && p.tracking_mode === 'quantity')
    .map(p => ({ product: p, score: rankMatch(search, [
      { value: p.name, weight: 80 }, { value: p.brand, weight: 50 },
      { value: p.model, weight: 90 },
      ...(p.search_aliases ?? []).map(value => ({ value, weight: 30 })),
    ]) }))
    .filter(item => item.score >= 0)
    .sort((a, b) => b.score - a.score || (a.product.name ?? '').localeCompare(b.product.name ?? '', 'es'))
    .map(item => item.product), [products, search]);
  const filteredAssets = useMemo(() => availableAssets
    .filter(a => rankMatch(assetSearch, [
      { value: a.asset_code, weight: 100 }, { value: a.name, weight: 70 },
      { value: a.serial, weight: 100 },
    ]) >= 0)
    .sort((a, b) => a.name.localeCompare(b.name, 'es') || a.asset_code.localeCompare(b.asset_code, 'es')),
  [availableAssets, assetSearch]);
  const chosenProduct = products.find(p => String(p.id) === choice);

  async function toggleWork(id: number) {
    const request = ++workRequest.current;
    setError('');
    if (work?.id === id) {
      setWork(null);
      setOpeningWork(null);
      return;
    }
    setOpeningWork(id);
    try {
      const detail = await obtenerTrabajo(id);
      if (request !== workRequest.current) return;
      setWork(detail);
      setPreparedProducts([]);
      setPreparedAssets([]);
      setNotReturned({});
      setReturnAssets([]);
    } catch (e) {
      if (request === workRequest.current) setError(e instanceof Error ? e.message : 'No se pudo abrir el trabajo');
    } finally {
      if (request === workRequest.current) setOpeningWork(null);
    }
  }

  function stageProduct() {
    const product=products.find(p=>p.id===Number(choice));
    const source=balances.find(b=>String(b.location_id??'none')===fromLocation);
    const n=Number(qty);
    if(!product||!source||!Number.isFinite(n)||n<=0||n>Number(source.quantity)||!Number.isInteger(n*1000)){
      setError('Seleccioná una ubicación con existencias verificadas y una cantidad válida.');return;
    }
    setPreparedProducts(prev=>[...prev,{product_id:product.id,origin_location_id:source.location_id,
      name:product.name||`Artículo #${product.id}`,location:[source.parent_name,source.location_name].filter(Boolean).join(' / ')||'Sin ubicación',quantity:String(n)}]);
    selectChoice('');setSearch('');setQty('1');setError('');
  }
  const outstandingProducts=work?.products.filter(p=>p.dispatched_at&&Number(p.pending)>0)??[];
  const outstandingAssets=work?.assets.filter(a=>a.dispatched_at&&!a.returned_at)??[];
  const haveToDispatch=(work?.products.some(p=>!p.dispatched_at)||work?.assets.some(a=>!a.dispatched_at))??false;
  const inWorkCount=outstandingProducts.reduce((a,p)=>a+Number(p.pending),0);
  async function registerReturns(){
    if(!work)return;
    const returns=outstandingProducts.map(p=>{
      const missing=Number(notReturned[p.id]??'0');
      return {line_id:p.id,quantity:Number(p.pending)-missing};
    });
    if(returns.some(r=>!Number.isFinite(r.quantity)||r.quantity<0||!Number.isInteger(r.quantity*1000))){
      setError('Revisá las diferencias de devolución.');return;
    }
    const selected=outstandingAssets.filter(a=>returnAssets.includes(a.id)).map(a=>a.id);
    const valid=returns.filter(r=>r.quantity>0);
    if(!valid.length&&!selected.length){setError('No hay nada para devolver. Si todo quedó pendiente, no registres la devolución todavía.');return;}
    await run(()=>devolverTrabajo(work.id,{products:valid,asset_line_ids:selected}),()=>{setNotReturned({});setReturnAssets([]);});
  }
  async function confirmClose(){
    if(!work)return;
    if(haveToDispatch){setError('Todavía hay recursos preparados sin despachar.');return;}
    if(outstandingAssets.length){setError('Primero devolvé todas las unidades físicas.');return;}
    const remaining=outstandingProducts.reduce((sum,p)=>sum+Number(p.pending),0);
    if(!window.confirm(remaining>0
      ? `¿Cerrar el trabajo? Las ${num(remaining)} unidades que no regresaron se clasificarán según lo seleccionado para cada artículo. Esta operación no se puede revertir desde la interfaz.`
      : '¿Cerrar definitivamente este trabajo? Esta operación no se puede revertir desde la interfaz.'))return;
    await run(()=>cerrarTrabajo(work.id,{confirm:true,remaining_as:'consumed',decisions:outstandingProducts.map(p=>({line_id:p.id,remaining_as:classification[p.id]??'consumed'})),note:closeNote.trim()||null}));
  }
  return (
    <section className="space-y-5 rounded-lg border border-slate-200 dark:border-slate-700 p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h4 className="flex items-center gap-2 font-semibold"><ClipboardList size={18}/>Trabajos del proyecto</h4>
        <div className="flex gap-2">
          <button type="button" className={secondary} onClick={()=>void refresh(work?.id).catch(e=>setError(e.message))} aria-label="Actualizar trabajos"><RefreshCw size={16}/></button>
          <button type="button" className={blue} onClick={()=>setCreating(v=>!v)}><Plus size={15} className="mr-1 inline"/>Nuevo trabajo</button>
        </div>
      </div>
      {error&&<p className="rounded-lg bg-red-50 dark:bg-red-950/60 p-3 text-sm text-red-700 dark:text-red-300">{error}</p>}
      {creating&&<form onSubmit={e=>void submitNew(e)} className="grid gap-3 rounded-lg bg-slate-50 dark:bg-slate-950 p-4 sm:grid-cols-2">
        <label className="text-sm sm:col-span-2">Nombre del trabajo *<input required maxLength={180} className={formInput} value={newName} onChange={e=>setNewName(e.target.value)}/></label>
        <label className="text-sm sm:col-span-2">Descripción<textarea className={formInput} value={newDescription} onChange={e=>setNewDescription(e.target.value)}/></label>
        <label className="text-sm">Responsable<input className={formInput} value={responsible} onChange={e=>setResponsible(e.target.value)}/></label>
        <div/>
        <label className="text-sm">Salida prevista<input type="date" className={formInput} value={outDate} onChange={e=>setOutDate(e.target.value)}/></label>
        <label className="text-sm">Vuelta prevista<input type="date" className={formInput} value={returnDate} onChange={e=>setReturnDate(e.target.value)}/></label>
        <div className="sm:col-span-2"><button disabled={busy} className={blue}>Crear trabajo</button></div>
      </form>}
      <div className="space-y-2">
        {works.map(w => {
          const expanded = work?.id === w.id;
          return <button key={w.id} type="button" aria-expanded={expanded}
            onClick={() => void toggleWork(w.id)}
            className={`flex w-full items-center justify-between gap-3 rounded-lg border px-4 py-3 text-left text-sm transition-colors ${expanded ? 'border-blue-400 dark:border-blue-500 bg-blue-50 dark:bg-blue-950' : 'border-slate-200 dark:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-800'}`}>
            <span className="min-w-0">
              <span className="block truncate font-semibold">{w.name}</span>
              <span className="mt-1 block text-xs text-slate-500 dark:text-slate-400">{w.status === 'draft' ? 'Preparación' : w.status === 'open' ? 'En curso' : 'Cerrado'}</span>
            </span>
            {expanded ? <ChevronUp size={18} className="shrink-0 text-blue-700 dark:text-blue-300" /> : <ChevronDown size={18} className="shrink-0 text-slate-500 dark:text-slate-400" />}
          </button>;
        })}
        {openingWork !== null && <p className="px-2 text-xs text-slate-500 dark:text-slate-400">Abriendo trabajo...</p>}
        {!works.length && <p className="text-sm text-slate-500 dark:text-slate-400">Todavía no hay trabajos creados para este proyecto.</p>}
      </div>
      {work&&<div className="space-y-5 border-t border-slate-200 dark:border-slate-700 pt-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div><p className="text-lg font-bold">{work.name}</p><p className="text-sm text-slate-500 dark:text-slate-400">{work.description||'Sin descripción'} · {work.responsible||'Sin responsable'}{work.created_by&&<> · creado por {work.created_by}</>}</p>
          <p className="text-xs text-slate-500 dark:text-slate-400">Previsto: {date(work.planned_out_date)} — {date(work.planned_return_date)}</p></div>
          {work.status!=='draft'&&<div className="flex flex-wrap gap-2">
            <a className={secondary} target="_blank" rel="noopener noreferrer" href={urlPdfTrabajo(work.id,'out')}><FileDown size={15} className="mr-1 inline"/>PDF salida</a>
            {work.status==='closed'&&<a className={secondary} target="_blank" rel="noopener noreferrer" href={urlPdfTrabajo(work.id,'return')}><FileDown size={15} className="mr-1 inline"/>PDF devolución</a>}
          </div>}
        </div>
        {work.status==='draft' && <button type="button" className="text-left text-xs text-red-700 dark:text-red-300 underline" disabled={busy} onClick={()=>{
          if(!window.confirm(`¿Eliminar el borrador "${work.name}"? No se descontaron existencias.`))return;
          setBusy(true);setError('');
          void eliminarBorradorTrabajo(work.id).then(()=>{setWork(null);setPreparedProducts([]);setPreparedAssets([]);return refresh(null);})
            .catch(e=>setError(e instanceof Error?e.message:'No se pudo eliminar el borrador')).finally(()=>setBusy(false));
        }}>Eliminar borrador de trabajo</button>}
        <div className="grid gap-2 sm:grid-cols-3">
          <div className="rounded-lg bg-slate-50 dark:bg-slate-950 p-3"><p className="text-xs text-slate-500 dark:text-slate-400">Material pendiente de regresar</p><p className="text-xl font-bold">{num(inWorkCount)}</p></div>
          <div className="rounded-lg bg-slate-50 dark:bg-slate-950 p-3"><p className="text-xs text-slate-500 dark:text-slate-400">Unidades físicas fuera</p><p className="text-xl font-bold">{outstandingAssets.length}</p></div>
          {canViewPrices && <div className="rounded-lg bg-slate-50 dark:bg-slate-950 p-3"><p className="text-xs text-slate-500 dark:text-slate-400">Costo de materiales consumidos</p>
            {Object.keys(work.material_cost).length?Object.entries(work.material_cost).map(([currency,v])=><p key={currency} className="font-semibold">{num(Number(v))} {currency}</p>):<p className="font-semibold">Sin consumo registrado</p>}
            {work.valuation_incomplete&&<p className="text-xs text-amber-700 dark:text-amber-300">Costo incompleto: faltan precios</p>}</div>}
        </div>
        <div className="overflow-x-auto rounded-lg border border-slate-200 dark:border-slate-700">
          <table className="w-full min-w-[600px] text-left text-xs"><thead className="bg-slate-50 dark:bg-slate-950 text-slate-600 dark:text-slate-300"><tr><th className="p-3">Material / equipo</th><th className="p-3">Origen</th><th className="p-3">Entregado</th><th className="p-3">Devuelto</th><th className="p-3">Pendiente</th></tr></thead>
            <tbody>{work.products.map(p=><tr key={`p${p.id}`} title={p.dispatched_by?`Despachado por ${p.dispatched_by}`:undefined} className="border-t border-slate-100 dark:border-slate-800"><td className="p-3">{p.name}</td><td className="p-3">{p.location}</td><td className="p-3">{p.dispatched_at?num(Number(p.quantity)):<button className="text-red-700 dark:text-red-300 underline" onClick={()=>void run(()=>quitarPreparadoTrabajo(work.id,'product',p.id))}>Quitar preparado</button>}</td><td className="p-3">{num(Number(p.returned))}</td><td className="p-3">{num(Number(p.pending))}</td></tr>)}
              {work.assets.map(a=><tr key={`a${a.id}`} title={a.dispatched_by?`Despachado por ${a.dispatched_by}`:undefined} className="border-t border-slate-100 dark:border-slate-800"><td className="p-3">{a.name}</td><td className="p-3">{a.asset_code}</td><td className="p-3">{a.dispatched_at?'1':<button className="text-red-700 dark:text-red-300 underline" onClick={()=>void run(()=>quitarPreparadoTrabajo(work.id,'asset',a.id))}>Quitar preparado</button>}</td><td className="p-3">{a.returned_at?'1':'0'}</td><td className="p-3">{a.dispatched_at&&!a.returned_at?'1':'0'}</td></tr>)}
              {!work.products.length&&!work.assets.length&&<tr><td colSpan={5} className="p-4 text-slate-500 dark:text-slate-400">Todavía no hay elementos preparados.</td></tr>}</tbody></table>
        </div>
        {work.status!=='closed'&&<div className="space-y-3 rounded-xl border border-slate-200 dark:border-slate-700 p-4">
          <h5 className="font-semibold">Preparar materiales para salida</h5>
          <p className="text-xs text-slate-500 dark:text-slate-400">La selección no cambia existencias hasta confirmar la salida. Podés hacer nuevas salidas durante un trabajo en curso.</p>
          <div className="grid items-start gap-4 lg:grid-cols-2">
            <div className="min-w-0 space-y-3 rounded-lg border border-slate-200 dark:border-slate-700 bg-slate-50/40 dark:bg-slate-900/40 p-3">
              <div>
                <h6 className="text-sm font-semibold">Artículos por cantidad</h6>
                <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">Buscá por nombre, marca, modelo o alias.</p>
              </div>
              {!chosenProduct ? <>
                <label className="flex items-center gap-2 rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-900 px-3 py-2">
                  <Search size={16} className="shrink-0 text-slate-400 dark:text-slate-400"/>
                  <input className="min-w-0 w-full text-sm outline-none" aria-label="Buscar artículo para salida"
                    value={search} onChange={e=>setSearch(e.target.value)} placeholder="Buscar cualquier artículo..."/>
                  {search && <button type="button" className="text-slate-500 dark:text-slate-400" aria-label="Limpiar búsqueda" onClick={()=>setSearch('')}><X size={15}/></button>}
                </label>
                <div className="flex justify-between text-xs text-slate-500 dark:text-slate-400">
                  <span>{quantityProducts.length} artículos encontrados</span>
                  <span>Lista completa, sin límite alfabético</span>
                </div>
                <div className="max-h-64 overflow-y-auto rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900" role="listbox" aria-label="Resultados de artículos">
                  {quantityProducts.map(p=><button key={p.id} type="button" role="option" aria-selected={false}
                    onClick={()=>{selectChoice(String(p.id));setError('');}}
                    className="block w-full border-b border-slate-100 dark:border-slate-800 px-3 py-2.5 text-left text-sm last:border-b-0 hover:bg-blue-50 dark:hover:bg-blue-950 focus:bg-blue-50 focus:outline-blue-500">
                    <span className="block break-words font-medium text-slate-800 dark:text-slate-200">{p.name||`Artículo #${p.id}`}</span>
                    <span className="mt-0.5 block break-words text-xs text-slate-500 dark:text-slate-400">{[p.brand,p.model].filter(Boolean).join(' · ')||'Sin marca/modelo'}</span>
                  </button>)}
                  {!quantityProducts.length && <p className="p-4 text-sm text-slate-500 dark:text-slate-400">No hay artículos que coincidan con la búsqueda.</p>}
                </div>
              </> : <div className="flex items-start justify-between gap-3 rounded-lg border border-blue-200 dark:border-blue-900 bg-blue-50 dark:bg-blue-950 p-3">
                <div className="min-w-0"><p className="flex items-center gap-1 text-xs font-semibold text-blue-700 dark:text-blue-300"><Check size={14}/>Artículo seleccionado</p>
                  <p className="mt-1 break-words text-sm font-semibold text-slate-900 dark:text-slate-100">{chosenProduct.name||`Artículo #${chosenProduct.id}`}</p>
                  <p className="text-xs text-slate-600 dark:text-slate-300">{[chosenProduct.brand,chosenProduct.model].filter(Boolean).join(' · ')}</p></div>
                <button type="button" className="shrink-0 text-xs font-semibold text-blue-700 dark:text-blue-300 underline" onClick={()=>{selectChoice('');setSearch('');}}>Cambiar</button>
              </div>}
              {chosenProduct && <>
                <label className="block text-sm font-medium">Ubicación de salida
                  <select className={`${formInput} mt-1`} disabled={!balances.length} value={fromLocation} onChange={e=>setFromLocation(e.target.value)}>
                    <option value="">Elegí una ubicación</option>
                    {balances.map((b,i)=><option key={`${b.location_id??'none'}-${i}`} value={String(b.location_id??'none')}>
                      {[b.parent_name,b.location_name].filter(Boolean).join(' / ')||'Sin ubicación'} · {num(Number(b.quantity))} uds. en stock
                    </option>)}
                  </select>
                </label>
                <p className="text-xs text-slate-500 dark:text-slate-400">Se muestran ubicaciones con existencias contabilizadas y disponibles.</p>
                {!balances.length && <p className="rounded-lg bg-amber-50 dark:bg-amber-950/60 p-2 text-xs text-amber-800 dark:text-amber-200">No hay existencias verificadas para retirar este artículo. Revisá su conteo de stock.</p>}
                <label className="block text-sm font-medium">Cantidad a retirar
                  <div className="mt-1 flex items-center gap-1">
                    <button type="button" className={secondary} aria-label="Disminuir cantidad" onClick={()=>setQty(String(Math.max(0,Number(qty||'0')-1)))}><Minus size={15}/></button>
                    <input className={formInput} type="number" min="0.001" step="0.001" value={qty} onChange={e=>setQty(e.target.value)} aria-label="Cantidad a preparar"/>
                    <button type="button" className={secondary} aria-label="Aumentar cantidad" onClick={()=>setQty(String(Number(qty||'0')+1))}><Plus size={15}/></button>
                  </div>
                </label>
                <button type="button" className={secondary} onClick={stageProduct} disabled={!balances.length||!fromLocation}>Agregar a la lista</button>
              </>}
            </div>
            <div className="min-w-0 space-y-3 rounded-lg border border-slate-200 dark:border-slate-700 bg-slate-50/40 dark:bg-slate-900/40 p-3">
              <div><h6 className="text-sm font-semibold">Unidades físicas individuales</h6>
                <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">Podés seleccionar varios equipos en la misma salida.</p></div>
              <label className="flex items-center gap-2 rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-900 px-3 py-2">
                <Search size={16} className="shrink-0 text-slate-400 dark:text-slate-400"/>
                <input className="w-full min-w-0 text-sm outline-none" aria-label="Buscar unidad física para salida"
                  placeholder="Buscar código interno, equipo o serie..." value={assetSearch} onChange={e=>setAssetSearch(e.target.value)}/>
                {assetSearch && <button type="button" className="text-slate-500 dark:text-slate-400" aria-label="Limpiar búsqueda de unidades" onClick={()=>setAssetSearch('')}><X size={15}/></button>}
              </label>
              <p className="text-xs text-slate-500 dark:text-slate-400">{filteredAssets.length} unidades encontradas</p>
              <div className="max-h-64 overflow-y-auto rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900">
                {filteredAssets.map(a=><label key={a.id} className={`flex cursor-pointer items-start gap-3 border-b border-slate-100 dark:border-slate-800 p-3 text-sm last:border-b-0 hover:bg-blue-50 dark:hover:bg-blue-950 ${preparedAssets.includes(a.id)?'bg-blue-50 dark:bg-blue-950':''}`}>
                  <input className="mt-1 shrink-0" type="checkbox" checked={preparedAssets.includes(a.id)} onChange={e=>setPreparedAssets(old=>e.target.checked?[...old,a.id]:old.filter(id=>id!==a.id))}/>
                  <span className="min-w-0 break-words"><span className="block font-medium">{a.name}</span><span className="mt-0.5 block text-xs text-slate-500 dark:text-slate-400">{a.asset_code} · {a.serial||'Sin serie'}</span></span>
                </label>)}
                {!filteredAssets.length&&<p className="p-4 text-sm text-slate-500 dark:text-slate-400">No hay unidades que coincidan con la búsqueda.</p>}
              </div>
              <p className="text-sm font-medium text-blue-700 dark:text-blue-300">{preparedAssets.length} unidades seleccionadas</p>
            </div>
          </div>
          {preparedProducts.length>0 && <div className="space-y-2 rounded-lg border border-slate-200 dark:border-slate-700 p-3">
            <h6 className="text-sm font-semibold">Artículos agregados para esta salida ({preparedProducts.length})</h6>
            {preparedProducts.map((p,i)=><div key={i} className="flex items-start justify-between gap-3 rounded-md bg-slate-50 dark:bg-slate-950 p-2.5 text-sm">
              <span className="min-w-0 break-words"><span className="block font-medium">{p.name} · {num(Number(p.quantity))} uds.</span><span className="block text-xs text-slate-500 dark:text-slate-400">{p.location}</span></span>
              <button type="button" className="shrink-0 text-xs font-semibold text-red-700 dark:text-red-300" onClick={()=>setPreparedProducts(old=>old.filter((_,j)=>j!==i))}>Quitar</button>
            </div>)}
          </div>}
          <button className={blue} disabled={busy||(!preparedAssets.length&&!preparedProducts.length)} onClick={()=>void run(()=>prepararTrabajo(work.id,{products:preparedProducts.map(p=>({product_id:p.product_id,origin_location_id:p.origin_location_id,quantity:Number(p.quantity)})),asset_ids:preparedAssets}),()=>{setPreparedProducts([]);setPreparedAssets([]);})}>Guardar lista preparada</button>
          {haveToDispatch&&<div className="border-t border-slate-100 dark:border-slate-800 pt-3"><button className={blue} disabled={busy} onClick={()=>{if(window.confirm('¿Confirmar salida física de todos los elementos preparados? descontará ahora las existencias del almacén.'))void run(()=>despacharTrabajo(work.id));}}>Confirmar salida de los recursos preparados</button></div>}
        </div>}
        {work.status==='open'&&<div className="space-y-3 rounded-xl border border-slate-200 dark:border-slate-700 p-4">
          <h5 className="font-semibold">Devolución por diferencias</h5>
          <p className="text-xs text-slate-600 dark:text-slate-300">Por defecto proponemos que regresen todos los materiales. Escribí únicamente la cantidad que NO regresó. Podés registrar devoluciones parciales y mantener el trabajo abierto.</p>
          {outstandingProducts.map(p=>{
            const missing=Number(notReturned[p.id]??'0');return <div key={p.id} className="grid items-center gap-2 border-b border-slate-100 dark:border-slate-800 pb-2 text-sm sm:grid-cols-[minmax(0,1fr)_115px_100px]"><div>{p.name}<p className="text-xs text-slate-500 dark:text-slate-400">Pendiente: {num(Number(p.pending))}</p></div><label className="text-xs">No regresó<input className={formInput} type="number" min="0" max={Number(p.pending)} step="0.001" value={notReturned[p.id]??'0'} onChange={e=>setNotReturned(old=>({...old,[p.id]:e.target.value}))}/></label><div className="text-right text-xs">Vuelve: {num(Number(p.pending)-missing)}</div></div>;
          })}
          {outstandingAssets.length>0&&<div className="space-y-2"><p className="text-sm font-medium">Unidades que regresaron (marcar)</p>{outstandingAssets.map(a=><label key={a.id} className="flex items-center gap-2 text-sm"><input type="checkbox" checked={returnAssets.includes(a.id)} onChange={e=>setReturnAssets(old=>e.target.checked?[...old,a.id]:old.filter(id=>id!==a.id))}/>{a.name} · {a.asset_code}</label>)}</div>}
          {(outstandingProducts.length>0||outstandingAssets.length>0)&&<button disabled={busy} className={blue} onClick={()=>{if(window.confirm('¿Confirmar que estas cantidades y unidades regresaron físicamente?'))void registerReturns();}}>Confirmar devolución física</button>}
          <div className="border-t border-slate-100 dark:border-slate-800 pt-4"><h5 className="font-semibold">Cerrar trabajo</h5><p className="my-2 text-xs text-slate-600 dark:text-slate-300">Cerrá solo cuando terminaste todas las salidas y devoluciones. No se puede cerrar con unidades físicas pendientes.</p>
            {outstandingProducts.map(p=><label key={p.id} className="my-2 block space-y-1 text-xs">{p.name} · pendiente {num(Number(p.pending))}
              <select className={formInput} value={classification[p.id]??'consumed'} onChange={e=>setClassification(old=>({...old,[p.id]:e.target.value as 'consumed'|'lost'}))}>
                <option value="consumed">Consumido</option><option value="lost">Perdido / extraviado</option>
              </select>
            </label>)}
            <label className="mt-2 block space-y-1 text-xs">Observación del cierre<textarea value={closeNote} onChange={e=>setCloseNote(e.target.value)} className={formInput} rows={2}/></label>
            <button disabled={busy||outstandingAssets.length>0||haveToDispatch} className={`${blue} mt-3`} onClick={()=>void confirmClose()}>Conciliar y cerrar trabajo</button>
          </div>
        </div>}
        {work.status==='closed'&&<div className="rounded-lg border border-emerald-200 dark:border-emerald-900 bg-emerald-50 dark:bg-emerald-950/60 p-4 text-sm text-emerald-800 dark:text-emerald-200"><p className="font-semibold">Trabajo cerrado</p><p>Fecha real: {work.closed_at?new Date(work.closed_at).toLocaleString('es-PY'):'—'}{work.closed_by&&<>, por {work.closed_by}</>}.</p><p>Las existencias fueron conciliadas y se puede emitir el PDF final de devolución.</p></div>}
      </div>}
    </section>
  );
}
