import {
  LogOut,
  ArrowLeftRight,
  Bot,
  FolderKanban,
  LayoutDashboard,
  MapPin,
  Package,
  Settings,
  Moon,
  Sun,
  Boxes,
} from 'lucide-react';
import { NavLink } from 'react-router';
import { rutas } from '../../types/navigation';

const menu = [
  { nombre: 'Inicio', icono: LayoutDashboard },
  { nombre: 'Inventario', icono: Package },
  { nombre: 'Robots', icono: Bot },
  { nombre: 'Ubicaciones', icono: MapPin },
  { nombre: 'Proyectos', icono: FolderKanban },
  { nombre: 'Movimientos', icono: ArrowLeftRight },
  { nombre: 'Administración', icono: Settings },
] as const;

type Props = {
  theme: 'light' | 'dark';
  onToggleTheme: () => void;
  username: string;
  onLogout: () => void;
  canAdminister: boolean;
};

export default function Sidebar({ theme, onToggleTheme, username, onLogout, canAdminister }: Props) {
  return (
    <aside className="w-full border-b border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 lg:sticky lg:top-0 lg:h-screen lg:w-64 lg:shrink-0 lg:flex lg:flex-col lg:border-b-0 lg:border-r">
      <div className="border-b border-slate-100 dark:border-slate-800 px-5 py-5">
        <div className="flex items-center gap-3">
          <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-blue-600 text-white">
            <Boxes size={26} aria-hidden="true" />
          </div>
          <h1 className="text-lg font-bold tracking-tight text-slate-900 dark:text-slate-100">Inventario</h1>
        </div>
      </div>

      <nav aria-label="Navegación principal" className="flex gap-1 overflow-x-auto p-3 lg:mt-3 lg:flex-col">
        {menu.filter(item => canAdminister || item.nombre !== 'Administración').map(({ nombre, icono: Icono }) => (
          <NavLink
            key={nombre}
            to={rutas[nombre]}
            end={rutas[nombre] === '/'}
            className={({ isActive }) => `flex shrink-0 cursor-pointer items-center gap-3 rounded-lg px-3.5 py-2.5 text-left text-sm transition ${
              isActive
                ? 'bg-blue-50 dark:bg-blue-950 font-semibold text-blue-700 dark:text-blue-300'
                : 'text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800'
            }`}
          >
            <Icono size={18} />
            {nombre}
          </NavLink>
        ))}
      </nav>
      <div className="mt-auto p-3 lg:pb-5">
        <div className="flex items-center justify-between gap-2 pb-2 text-xs text-slate-600 dark:text-slate-300"><span>Sesión: <strong>{username}</strong></span><button type="button" onClick={onLogout} title="Cerrar sesión" aria-label="Cerrar sesión" className="rounded-lg p-2 hover:bg-slate-100 dark:hover:bg-slate-800"><LogOut size={17}/></button></div>
        <button type="button" onClick={onToggleTheme}
          aria-label={theme === 'dark' ? 'Activar modo claro' : 'Activar modo oscuro'}
          aria-pressed={theme === 'dark'}
          className="flex h-10 w-10 items-center justify-center rounded-lg border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-950 px-3.5 py-2.5 text-left text-sm font-medium text-slate-700 dark:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600 dark:focus-visible:outline-blue-400">
          {theme === 'dark' ? <Sun size={18} /> : <Moon size={18} />}

        </button>
      </div>
    </aside>
  );
}
