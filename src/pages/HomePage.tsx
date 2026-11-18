import { useEffect, useState } from 'react';
import { Activity, Bot, Boxes, FolderKanban, Package, Tags } from 'lucide-react';
import { obtenerResumen } from '../services/inventoryService';
import type { ResumenSistema } from '../types/inventory';

export default function HomePage() {
  const [summary, setSummary] = useState<ResumenSistema | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    let current = true;
    obtenerResumen()
      .then((data) => current && setSummary(data))
      .catch((e: Error) => current && setError(e.message));
    return () => { current = false; };
  }, []);

  const cards = summary ? [
    { label: 'Artículos en catálogo', value: summary.products, icon: Package },
    { label: 'Unidades individuales', value: summary.assets, icon: Boxes },
    { label: 'Modelos de robot', value: summary.robot_models, icon: Bot },
    { label: 'Proyectos activos', value: summary.active_projects, icon: FolderKanban },
    { label: 'Categorías', value: summary.categories, icon: Tags },
    { label: 'Conteos pendientes', value: summary.pending_stock_count, icon: Activity },
  ] : [];

  return (
    <div className="mx-auto max-w-7xl space-y-6 p-4 md:p-7">
      <h1 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-slate-100">Inicio</h1>
      {error && <p className="rounded-lg border border-red-200 dark:border-red-900 bg-red-50 dark:bg-red-950/60 px-4 py-3 text-sm text-red-700 dark:text-red-300">{error}</p>}
      {!summary ? <p className="rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 p-6 text-sm text-slate-500 dark:text-slate-400">Consultando la base de datos...</p> : (
        <>
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            {cards.map(({ label, value, icon: Icon }) => <div key={label} className="rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 p-5"><div className="flex items-center justify-between"><p className="text-sm font-medium text-slate-500 dark:text-slate-400">{label}</p><span className="rounded-lg bg-blue-50 dark:bg-blue-950 p-2 text-blue-700 dark:text-blue-300"><Icon size={18} /></span></div><p className="mt-4 text-3xl font-bold text-slate-900 dark:text-slate-100">{value}</p></div>)}
          </div>
        </>
      )}
    </div>
  );
}
