import { ChevronRight } from 'lucide-react';
import { useAuth } from '../../auth/useAuth';
import type { Producto, ResumenEnTrabajos } from '../../types/inventory';

type Props = { articulos: Producto[]; enTrabajos: ResumenEnTrabajos; onSelect: (articulo: Producto) => void };

export default function InventoryTable({ articulos, enTrabajos, onSelect }: Props) {
  const { canViewPrices } = useAuth();
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[760px] text-left text-sm">
        <thead className="bg-slate-50 dark:bg-slate-950 text-xs text-slate-500 dark:text-slate-400">
          <tr>
            <th className="px-5 py-3 font-medium">Artículo / Modelo</th>
            <th className="px-5 py-3 font-medium">Categoría</th>
            <th className="px-5 py-3 font-medium">Tipo</th>
            <th className="px-5 py-3 font-medium">Existencias / Unidades</th>
            {canViewPrices && <th className="px-5 py-3 font-medium">Valor unitario</th>}
            <th className="px-5 py-3"><span className="sr-only">Abrir detalle</span></th>
          </tr>
        </thead>
        <tbody>
          {articulos.map((articulo) => (
            <tr key={articulo.id} className="border-t border-slate-100 dark:border-slate-800 hover:bg-blue-50/50">
              <td className="px-5 py-4">
                <p className="font-semibold text-slate-800 dark:text-slate-200">{articulo.name || `Artículo sin nombre #${articulo.id}`}</p>
                <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">{[articulo.brand, articulo.model].filter(Boolean).join(' · ') || 'Sin marca/modelo registrado'}</p>
              </td>
              <td className="px-5 py-4 text-slate-600 dark:text-slate-300">{articulo.category_name || 'Sin clasificar'}</td>
              <td className="px-5 py-4 text-slate-600 dark:text-slate-300">{articulo.component_type_name || '—'}</td>
              <td className="px-5 py-4">
                {articulo.tracking_mode === 'individual'
                  ? <span className="rounded-md bg-blue-50 dark:bg-blue-950 px-2 py-1 text-xs font-semibold text-blue-700 dark:text-blue-300">{Math.max(0, articulo.assets.filter(a => a.lifecycle_status === 'in_stock').length - Number(enTrabajos.assets[String(articulo.id)] ?? 0))} unidades</span>
                  : articulo.stock_verified
                    ? <span className="rounded-md bg-emerald-50 dark:bg-emerald-950/60 px-2 py-1 text-xs font-semibold text-emerald-700 dark:text-emerald-300">{Number(articulo.total_stock ?? 0)} uds.</span>
                    : <span className="rounded-md bg-amber-50 dark:bg-amber-950/60 px-2 py-1 text-xs font-semibold text-amber-700 dark:text-amber-300">Pendiente de conteo</span>}
              </td>
              {canViewPrices && <td className="px-5 py-4 text-slate-600 dark:text-slate-300">{articulo.unit_value == null ? '—' : `${new Intl.NumberFormat('es-PY').format(articulo.unit_value)} ${articulo.value_currency}`}</td>}
              <td className="px-5 py-4"><button type="button" onClick={() => onSelect(articulo)} aria-label={`Ver detalle de ${articulo.name || articulo.id}`} className="rounded-lg p-2 hover:bg-blue-100"><ChevronRight size={18} className="text-slate-500 dark:text-slate-400" /></button></td>
            </tr>
          ))}
        </tbody>
      </table>
      {articulos.length === 0 && <div className="p-12 text-center text-sm text-slate-500 dark:text-slate-400">No encontramos artículos con esos criterios.</div>}
    </div>
  );
}
