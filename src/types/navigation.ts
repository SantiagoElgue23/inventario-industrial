export const secciones = [
  "Inicio",
  "Inventario",
  "Robots",
  "Ubicaciones",
  "Proyectos",
  "Movimientos",
  "Administración",
] as const;

export type Seccion = (typeof secciones)[number];

/** Dirección de cada sección; permite recargar, usar "atrás" y compartir links. */
export const rutas: Record<Seccion, string> = {
  Inicio: "/",
  Inventario: "/inventario",
  Robots: "/robots",
  Ubicaciones: "/ubicaciones",
  Proyectos: "/proyectos",
  Movimientos: "/movimientos",
  Administración: "/administracion",
};
