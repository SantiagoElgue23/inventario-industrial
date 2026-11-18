export type TrackingMode = 'quantity' | 'individual';
export type FunctionalStatus =
  | 'unverified'
  | 'functional'
  | 'damaged';
export type LifecycleStatus = 'in_stock' | 'sold' | 'disposed' | 'lost';
export type TipoMovimiento = 'entry' | 'exit' | 'count';
export type Cantidad = number | string;
export type EstadoProyecto = 'planning' | 'active' | 'on_hold' | 'completed' | 'cancelled';

export type Categoria = {
  id: number;
  name: string;
  active: boolean;
  product_count: number;
};

export type TipoComponente = {
  id: number;
  name: string;
  active: boolean;
  product_count: number;
};

export type DefinicionCaracteristica = {
  id: number;
  component_type_id: number;
  name: string;
  data_type: 'text' | 'number' | 'boolean' | 'date';
  unit: string | null;
  required: boolean;
  active: boolean;
  sort_order: number;
};

export type ValorCaracteristica = {
  definition_id: number;
  name: string;
  value: string;
  unit: string | null;
};

export type ActivoResumen = {
  id: number;
  product_id: number | null;
  product_name: string | null;
  product_brand: string | null;
  product_model: string | null;
  asset_code: string;
  manufacturer_serial: string | null;
  manufacturer_brand: string | null;
  functional_status: FunctionalStatus;
  lifecycle_status: LifecycleStatus;
  observations: string | null;
  project_names: string[];
  location_id: number | null;
  location_name: string | null;
  estimated_value: number | null;
  value_currency: string;
  active: boolean;
};

export type Activo = ActivoResumen & {
  created_at: string;
  updated_at: string;
  archived_at: string | null;
};

export type AsociacionActivo = {
  id: number;
  source_asset_id: number;
  target_asset_id: number;
  relationship_type: string;
  started_at: string;
  ended_at: string | null;
  note: string | null;
  target_asset: ActivoResumen;
};

export type ActivoDetalle = Activo & {
  active_relationships: AsociacionActivo[];
  relationship_history: AsociacionActivo[];
};

export type Producto = {
  id: number;
  name: string | null;
  description: string | null;
  brand: string | null;
  model: string | null;
  category_id: number | null;
  category_name: string | null;
  component_type_id: number | null;
  component_type_name: string | null;
  tracking_mode: TrackingMode;
  asset_code_prefix: string | null;
  unit_value: number | null;
  value_currency: string;
  active: boolean;
  total_stock: number | null;
  stock_verified: boolean;
  source_count: number;
  search_aliases: string[];
  asset_count: number;
  assets: ActivoResumen[];
  attributes: ValorCaracteristica[];
};

export type ProductoPayload = {
  name: string | null;
  description: string | null;
  brand: string | null;
  model: string | null;
  category_id: number | null;
  component_type_id: number | null;
  tracking_mode: TrackingMode;
  asset_code_prefix: string | null;
  unit_value?: number | null;
  value_currency?: string;
  attributes: { attribute_definition_id: number; value: string }[];
};

export type ActivoPayload = {
  product_id: number | null;
  asset_code_prefix?: string | null;
  manufacturer_serial: string | null;
  manufacturer_brand: string | null;
  functional_status: FunctionalStatus;
  observations: string | null;
  location_id: number | null;
  estimated_value?: number | null;
  value_currency?: string;
};

export type Ubicacion = {
  id: number;
  name: string;
  location_type: 'warehouse' | 'shelf' | 'area';
  parent_id: number | null;
  parent_name: string | null;
  active: boolean;
  children_count: number;
};

export type UbicacionPayload = {
  name: string;
  location_type: 'warehouse' | 'shelf' | 'area';
  parent_id: number | null;
};

export type Movimiento = {
  id: number;
  product_id: number;
  location_id: number | null;
  movement_type: TipoMovimiento;
  quantity: Cantidad;
  quantity_before: Cantidad;
  quantity_after: Cantidad;
  note: string | null;
  status: string;
  created_by: string | null;
  created_at: string;
};

export type TrasladoExistencias = {
  id: number;
  product_id: number;
  source_location_id: number | null;
  source_location_name: string | null;
  source_parent_name: string | null;
  destination_location_id: number | null;
  destination_location_name: string | null;
  destination_parent_name: string | null;
  quantity: Cantidad;
  source_quantity_before: Cantidad;
  source_quantity_after: Cantidad;
  destination_quantity_before: Cantidad;
  destination_quantity_after: Cantidad;
  note: string | null;
  created_by: string | null;
  created_at: string;
};

export type TrasladoExistenciasPayload = {
  source_location_id: number | null;
  destination_location_id: number | null;
  quantity: number;
  note: string | null;
};

export type ExistenciaUbicacion = {
  product_id: number;
  location_id: number | null;
  location_name: string | null;
  parent_name: string | null;
  location_type: 'warehouse' | 'shelf' | 'area' | null;
  quantity: Cantidad;
  verified: boolean;
  updated_at: string;
};

export type Proyecto = {
  id: number;
  name: string;
  description: string | null;
  status: EstadoProyecto;
  start_date: string | null;
  end_date: string | null;
  active: boolean;
  created_at: string;
  updated_at: string;
  asset_count: number;
  product_count: number;
  valuation_by_currency: Record<string, number>;
  valuation_complete: boolean;
};

export type AsignacionActivo = {
  id: number;
  project_id: number;
  asset_id: number;
  assigned_at: string;
  released_at: string | null;
  note: string | null;
  asset: ActivoResumen;
};

export type AsignacionProducto = {
  id: number;
  project_id: number;
  product_id: number;
  quantity: number;
  assigned_at: string;
  released_at: string | null;
  note: string | null;
  product_name: string | null;
  unit_value: number | null;
  value_currency: string;
};

export type ProyectoDetalle = Proyecto & {
  asset_assignments: AsignacionActivo[];
  product_assignments: AsignacionProducto[];
};

export type ProyectoPayload = {
  name: string;
  description: string | null;
  status: EstadoProyecto;
  start_date: string | null;
  end_date: string | null;
};

export type ResumenSistema = {
  products: number;
  categories: number;
  component_types: number;
  pending_stock_count: number;
  assets: number;
  robot_models: number;
  active_projects: number;
};

// Trabajos temporales de un proyecto (V4)
export type EstadoTrabajo = 'draft' | 'open' | 'closed';
export type TrabajoProducto = {
  id: number;
  product_id: number;
  origin_location_id: number | null;
  name: string;
  location: string;
  quantity: number;
  returned: number;
  consumed: number;
  lost: number;
  pending: number;
  dispatched_at: string | null;
  dispatched_by: string | null;
  unit_value: number | null;
  currency: string;
};
export type TrabajoActivo = {
  id: number;
  asset_id: number;
  name: string;
  asset_code: string;
  serial: string | null;
  dispatched_at: string | null;
  dispatched_by: string | null;
  returned_at: string | null;
};
export type Trabajo = {
  id: number;
  project_id: number;
  name: string;
  description: string | null;
  responsible: string | null;
  planned_out_date: string | null;
  planned_return_date: string | null;
  status: EstadoTrabajo;
  created_at: string;
  departed_at: string | null;
  closed_at: string | null;
  close_note: string | null;
  created_by: string | null;
  closed_by: string | null;
};
export type TrabajoDetalle = Trabajo & {
  products: TrabajoProducto[];
  assets: TrabajoActivo[];
  material_cost: Record<string, number>;
  loss_cost: Record<string, number>;
  valuation_incomplete: boolean;
};
export type ResumenEnTrabajos = {
  products: Record<string, number>;
  assets: Record<string, number>;
};

// Cuentas de acceso. El rol master solo se asigna por consola, nunca desde la web.
export type RolCuenta = 'master' | 'admin' | 'user';
export type CuentaUsuario = {
  id: number;
  username: string;
  role: RolCuenta;
  active: boolean;
};
