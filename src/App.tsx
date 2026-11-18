import { useEffect, useState } from 'react';
import { Navigate, Route, Routes } from 'react-router';
import Sidebar from './components/layout/Sidebar';
import { rutas } from './types/navigation';
import HomePage from './pages/HomePage';
import InventoryPage from './pages/InventoryPage';
import RobotsPage from './pages/RobotsPage';
import LocationsPage from './pages/LocationsPage';
import ProjectsPage from './pages/ProjectsPage';
import MovementsPage from './pages/MovementsPage';
import AdminPage from './pages/AdminPage';
import { AuthProvider } from './auth/AuthProvider';
import { useAuth } from './auth/useAuth';
import LoginPage from './auth/LoginPage';

function AuthenticatedApp() {
  const { account, loading, logout, canAdminister } = useAuth();
  const [theme, setTheme] = useState<'light' | 'dark'>(() => {
    try { return localStorage.getItem('inv-theme') === 'dark' ? 'dark' : 'light'; }
    catch { return 'light'; }
  });

  useEffect(() => {
    document.documentElement.classList.toggle('dark', theme === 'dark');
    document.documentElement.style.colorScheme = theme;
    try { localStorage.setItem('inv-theme', theme); } catch { /* modo privado */ }
  }, [theme]);

  if (loading) return <div className="min-h-screen bg-slate-50 p-12 text-slate-600 dark:bg-slate-950 dark:text-slate-300">Comprobando sesión…</div>;
  if (!account) return <LoginPage />;

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-950 text-slate-800 dark:text-slate-200 lg:flex">
      <Sidebar theme={theme} onToggleTheme={() => setTheme(t => t === 'dark' ? 'light' : 'dark')} username={account.username} onLogout={() => void logout()} canAdminister={canAdminister} />
      <main className="min-w-0 flex-1">
        <Routes>
          <Route path={rutas.Inicio} element={<HomePage />} />
          <Route path={rutas.Inventario} element={<InventoryPage />} />
          <Route path={rutas.Robots} element={<RobotsPage />} />
          <Route path={rutas.Ubicaciones} element={<LocationsPage />} />
          <Route path={rutas.Proyectos} element={<ProjectsPage />} />
          <Route path={rutas.Movimientos} element={<MovementsPage />} />
          <Route path={rutas.Administración} element={canAdminister ? <AdminPage /> : <Navigate to={rutas.Inicio} replace />} />
          <Route path="*" element={<Navigate to={rutas.Inicio} replace />} />
        </Routes>
      </main>
    </div>
  );
}

export default function App() { return <AuthProvider><AuthenticatedApp /></AuthProvider>; }
