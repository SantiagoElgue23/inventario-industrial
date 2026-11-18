import type {
  Activo,
  ActivoDetalle,
  ActivoPayload,
  AsociacionActivo,
  Categoria,
  DefinicionCaracteristica,
  EstadoProyecto,
  ExistenciaUbicacion,
  Movimiento,
  TrasladoExistencias,
  TrasladoExistenciasPayload,
  Producto,
  ProductoPayload,
  Proyecto,
  ProyectoDetalle,
  ProyectoPayload,
  ResumenSistema,
  TipoComponente,
  TipoMovimiento,
  Ubicacion,
  UbicacionPayload,
} from '../types/inventory';

const API_URL = '/api'; // Siempre usar proxy del mismo origen para cookies HttpOnly.

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers);
  if (options.body && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }

  let response: Response;
  try {
    response = await fetch(`${API_URL}${path}`, { ...options, headers, credentials: 'include' });
  } catch {
    throw new Error('No se pudo conectar con la API. Verificá que FastAPI esté ejecutándose.');
  }

  if (response.status === 401) window.dispatchEvent(new Event('inv-session-expired'));
  if (!response.ok) {
    let message = `Error ${response.status}`;
    try {
      const body = await response.json() as { detail?: unknown };
      if (typeof body.detail === 'string') message = body.detail;
      else if (Array.isArray(body.detail)) {
        message = body.detail.map((item) => {
          if (item && typeof item === 'object' && 'msg' in item) {
            return String((item as { msg: unknown }).msg);
          }
          return JSON.stringify(item);
        }).join(' · ');
      }
    } catch {
      // La respuesta no contenía JSON.
    }
    throw new Error(message);
  }

  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

function queryString(values: Record<string, string | number | boolean | null | undefined>) {
  const params = new URLSearchParams();
  Object.entries(values).forEach(([key, value]) => {
    if (value !== null && value !== undefined && value !== '') {
      params.set(key, String(value));
    }
  });
  const result = params.toString();
  return result ? `?${result}` : '';
}

const json = (method: string, payload: unknown): RequestInit => ({
  method,
  body: JSON.stringify(payload),
});

export const obtenerResumen = () => request<ResumenSistema>('/summary');

export const obtenerProductos = (filters: {
  q?: string;
  category_id?: number;
  component_type_id?: number;
  tracking_mode?: 'quantity' | 'individual';
  include_inactive?: boolean;
} = {}) => request<Producto[]>(`/products${queryString(filters)}`);

export const obtenerProducto = (id: number) => request<Producto>(`/products/${id}`);
export const crearProducto = (payload: ProductoPayload) =>
  request<Producto>('/products', json('POST', payload));
export const actualizarProducto = (id: number, payload: ProductoPayload) =>
  request<Producto>(`/products/${id}`, json('PUT', payload));
export const archivarProducto = (id: number) =>
  request<{ message: string }>(`/products/${id}`, { method: 'DELETE' });
export const restaurarProducto = (id: number) =>
  request<{ message: string }>(`/products/${id}/restore`, { method: 'POST' });

export const obtenerRobots = (q?: string) =>
  request<Producto[]>(`/robots${queryString({ q })}`);
export const obtenerModeloRobot = (id: number) => request<Producto>(`/robots/${id}`);

export const obtenerActivos = (filters: {
  q?: string;
  product_id?: number;
  include_non_stock?: boolean;
  include_archived?: boolean;
  unassigned_only?: boolean;
  available_for_projects?: boolean;
} = {}) => request<Activo[]>(`/assets${queryString(filters)}`);

export const obtenerActivo = (id: number) => request<ActivoDetalle>(`/assets/${id}`);
export const crearActivo = (payload: ActivoPayload & { asset_code_prefix?: string | null }) =>
  request<Activo>('/assets', json('POST', payload));
export const actualizarActivo = (id: number, payload: Partial<ActivoPayload>) =>
  request<Activo>(`/assets/${id}`, json('PUT', payload));
export const archivarActivo = (id: number) =>
  request<{ message: string; asset_code: string }>(`/assets/${id}`, { method: 'DELETE' });
export const restaurarActivo = (id: number) =>
  request<{ message: string; asset_code: string }>(`/assets/${id}/restore`, { method: 'POST' });

export const obtenerAsociaciones = (assetId: number, includeHistory = false) =>
  request<AsociacionActivo[]>(`/assets/${assetId}/relationships${queryString({ include_history: includeHistory })}`);
export const crearAsociacion = (assetId: number, payload: {
  target_asset_id: number;
  relationship_type: string;
  note: string | null;
}) => request<AsociacionActivo>(`/assets/${assetId}/relationships`, json('POST', payload));
export const finalizarAsociacion = (assetId: number, relationshipId: number) =>
  request<AsociacionActivo>(`/assets/${assetId}/relationships/${relationshipId}`, { method: 'DELETE' });

export const obtenerCategorias = () => request<Categoria[]>('/categories');
export const crearCategoria = (name: string) =>
  request<Categoria>('/categories', json('POST', { name }));
export const renombrarCategoria = (id: number, name: string) =>
  request<Categoria>(`/categories/${id}`, json('PUT', { name }));
export const desactivarCategoria = (id: number) =>
  request<{ message: string }>(`/categories/${id}`, { method: 'DELETE' });

export const obtenerTipos = () => request<TipoComponente[]>('/component-types');
export const crearTipo = (name: string) =>
  request<TipoComponente>('/component-types', json('POST', { name }));
export const renombrarTipo = (id: number, name: string) =>
  request<TipoComponente>(`/component-types/${id}`, json('PUT', { name }));
export const desactivarTipo = (id: number) =>
  request<{ message: string }>(`/component-types/${id}`, { method: 'DELETE' });

export const obtenerCaracteristicas = (tipoId: number) =>
  request<DefinicionCaracteristica[]>(`/component-types/${tipoId}/attributes`);
export const crearCaracteristica = (
  tipoId: number,
  payload: { name: string; data_type: string; unit: string | null; required: boolean },
) => request<DefinicionCaracteristica>(`/component-types/${tipoId}/attributes`, json('POST', payload));
export const actualizarCaracteristica = (
  id: number,
  payload: { name: string; data_type: string; unit: string | null; required: boolean },
) => request<DefinicionCaracteristica>(`/attributes/${id}`, json('PUT', payload));
export const desactivarCaracteristica = (id: number) =>
  request<{ message: string }>(`/attributes/${id}`, { method: 'DELETE' });

export const obtenerUbicaciones = () => request<Ubicacion[]>('/locations');
export const crearUbicacion = (payload: UbicacionPayload) =>
  request<Ubicacion>('/locations', json('POST', payload));
export const actualizarUbicacion = (id: number, payload: Partial<UbicacionPayload>) =>
  request<Ubicacion>(`/locations/${id}`, json('PUT', payload));
export const archivarUbicacion = (id: number) =>
  request<{ message: string }>(`/locations/${id}`, { method: 'DELETE' });

export const obtenerExistenciasProducto = (productId: number) =>
  request<ExistenciaUbicacion[]>(`/products/${productId}/balances`);

export const registrarMovimiento = (
  productId: number,
  payload: { location_id: number | null; movement_type: TipoMovimiento; quantity: number; note: string | null },
) => request<Movimiento>(`/products/${productId}/movements`, json('POST', payload));
export const obtenerMovimientos = (productId: number, locationId?: number) =>
  request<Movimiento[]>(`/products/${productId}/movements${queryString({ location_id: locationId })}`);
export const registrarTraslado = (
  productId: number,
  payload: TrasladoExistenciasPayload,
) => request<TrasladoExistencias>(`/products/${productId}/transfers`, json('POST', payload));
export const obtenerTraslados = (productId: number) =>
  request<TrasladoExistencias[]>(`/products/${productId}/transfers`);

export const obtenerProyectos = (filters: { q?: string; status?: EstadoProyecto } = {}) =>
  request<Proyecto[]>(`/projects${queryString(filters)}`);
export const obtenerProyecto = (id: number) => request<ProyectoDetalle>(`/projects/${id}`);
export const crearProyecto = (payload: ProyectoPayload) =>
  request<Proyecto>('/projects', json('POST', payload));
export const actualizarProyecto = (id: number, payload: ProyectoPayload) =>
  request<Proyecto>(`/projects/${id}`, json('PUT', payload));
export const archivarProyecto = (id: number) =>
  request<{ message: string }>(`/projects/${id}`, { method: 'DELETE' });

export const asignarActivoAProyecto = (projectId: number, assetId: number, note: string | null) =>
  request<unknown>(`/projects/${projectId}/assets`, json('POST', { asset_id: assetId, note }));
export const asignarActivosEnLote = (projectId: number, assetIds: number[]) =>
  request<{ assigned_count: number }>(`/projects/${projectId}/assets/batch`, json('POST', { asset_ids: assetIds }));
export const liberarActivoDeProyecto = (projectId: number, assignmentId: number) =>
  request<{ message: string }>(`/projects/${projectId}/assets/${assignmentId}`, { method: 'DELETE' });
export const asignarProductoAProyecto = (
  projectId: number,
  productId: number,
  quantity: number,
  note: string | null,
) => request<unknown>(`/projects/${projectId}/products`, json('POST', {
  product_id: productId,
  quantity,
  note,
}));
export const asignarProductosEnLote = (projectId: number, items: { product_id: number; quantity: number }[]) =>
  request<{ assigned_count: number }>(`/projects/${projectId}/products/batch`, json('POST', { items }));
export const liberarProductoDeProyecto = (projectId: number, assignmentId: number) =>
  request<{ message: string }>(`/projects/${projectId}/products/${assignmentId}`, { method: 'DELETE' });

// Trabajos temporales (no equivalen a asignaciones permanentes del proyecto)
export const obtenerTrabajos = (projectId: number) =>
  request<import('../types/inventory').Trabajo[]>(`/projects/${projectId}/works`);
export const crearTrabajo = (projectId: number, payload: {
  name: string; description: string | null; responsible: string | null;
  planned_out_date: string | null; planned_return_date: string | null;
}) => request<import('../types/inventory').TrabajoDetalle>(`/projects/${projectId}/works`, json('POST', payload));
export const obtenerTrabajo = (id: number) =>
  request<import('../types/inventory').TrabajoDetalle>(`/works/${id}`);
export const prepararTrabajo = (id: number, payload: {
  products: { product_id: number; origin_location_id: number | null; quantity: number }[];
  asset_ids: number[];
}) => request<import('../types/inventory').TrabajoDetalle>(`/works/${id}/prepare`, json('POST', payload));
export const despacharTrabajo = (id: number) =>
  request<import('../types/inventory').TrabajoDetalle>(`/works/${id}/dispatch`, { method: 'POST' });
export const devolverTrabajo = (id: number, payload: {
  products: { line_id: number; quantity: number }[];
  asset_line_ids: number[];
}) => request<import('../types/inventory').TrabajoDetalle>(`/works/${id}/returns`, json('POST', payload));
export const cerrarTrabajo = (id: number, payload: {
  confirm: boolean; remaining_as: 'consumed' | 'lost'; note: string | null;
  decisions: {line_id: number; remaining_as: 'consumed' | 'lost'}[];
}) => request<import('../types/inventory').TrabajoDetalle>(`/works/${id}/close`, json('POST', payload));
export const obtenerResumenEnTrabajos = () => request<import('../types/inventory').ResumenEnTrabajos>('/work-stock-summary');
export const urlPdfTrabajo = (id: number, mode: 'out' | 'return') =>
  `${API_URL}/works/${id}/pdf/${mode}`;
export const obtenerActivosParaTrabajo = (projectId: number) =>
  request<{id: number; asset_code: string; name: string; serial: string | null}[]>(`/projects/${projectId}/work-assets`);

export const quitarPreparadoTrabajo = (id: number, kind: 'product' | 'asset', lineId: number) =>
  request<import('../types/inventory').TrabajoDetalle>(`/works/${id}/prepared/${kind}/${lineId}`, {method: 'DELETE'});

export const eliminarBorradorTrabajo = (id: number) =>
  request<{message: string}>(`/works/${id}`, {method: 'DELETE'});

// ============================================================
// Cuentas de acceso (administración exclusiva de master)
// ============================================================
export const listarCuentas = () =>
  request<import('../types/inventory').CuentaUsuario[]>('/auth/users');
export const crearCuenta = (payload: { username: string; role: 'admin' | 'user'; password: string }) =>
  request<import('../types/inventory').CuentaUsuario>('/auth/users', json('POST', payload));
export const actualizarCuenta = (id: number, payload: { role?: 'admin' | 'user'; active?: boolean }) =>
  request<import('../types/inventory').CuentaUsuario>(`/auth/users/${id}`, json('PATCH', payload));
export const restablecerContrasenaCuenta = (id: number, password: string) =>
  request<void>(`/auth/users/${id}/password`, json('PUT', { password }));
export const cambiarMiContrasena = (currentPassword: string, newPassword: string) =>
  request<void>('/auth/password', json('POST', { current_password: currentPassword, new_password: newPassword }));
