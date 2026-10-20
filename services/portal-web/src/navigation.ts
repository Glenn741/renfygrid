import { getFindings, getMaintenanceKpis, getVeeSummary, type ProductModule } from "./api";

// Estructura de navegacion del Portal.
//
// 2026-10-05: UNA sola definicion de las secciones internas de cada pantalla,
// usada por el menu lateral (submenu contextual) y por la barra de secciones
// de cada pantalla.
//
// 2026-10-20 (Track F, migracion 0048): QUE modulos ve cada organizacion, con
// que nombre, en que grupo y en que orden ya no esta aqui: es dato
// (`product_module`, por tipo de organizacion y por sector -- energia, gas,
// agua) y llega en la sesion (`/auth/me` -> `modules`). Aqui queda solo lo que
// es codigo de cada pantalla: sus secciones (anclas) y si su submenu sale de
// la ruta del paquete.

export interface NavSectionDef {
  id: string;
  label: string;
  /** Contador opcional para secciones que piden atencion. */
  badge?: NavBadge;
}

export interface NavBadge {
  queryKey: readonly unknown[];
  fetch: () => Promise<number>;
  /** Texto accesible, p. ej. "hallazgos abiertos". */
  meaning: string;
  tone: "alert" | "info";
}

export interface NavItemDef {
  to: string;
  label: string;
  icon: string;
  sections?: NavSectionDef[];
  /** Submenu que sale del paquete de la organizacion (la ruta del programa). */
  dynamic?: "route";
  /** Que hace el modulo (tarjeta de la Vista general). */
  description?: string;
}

export interface NavGroup {
  code: string;
  title: string | null;
  items: NavItemDef[];
}

const OPEN_FINDINGS: NavBadge = {
  queryKey: ["nav-badge", "findings-open"],
  fetch: async () => (await getFindings("open")).length,
  meaning: "hallazgos abiertos",
  tone: "alert",
};

const OVERDUE_ORDERS: NavBadge = {
  queryKey: ["nav-badge", "maintenance-overdue"],
  fetch: async () => (await getMaintenanceKpis()).overdue_count,
  meaning: "órdenes vencidas de SLA",
  tone: "alert",
};

const VEE_PENDING: NavBadge = {
  queryKey: ["nav-badge", "vee-pending"],
  fetch: async () => (await getVeeSummary()).validation.invalid_total,
  meaning: "excepciones pendientes de validar",
  tone: "info",
};

/** Pantallas que existen en el frontend y sus secciones internas. */
export const SCREENS: Record<string, { sections?: NavSectionDef[]; dynamic?: "route" }> = {
  "/": {
    sections: [
      { id: "operation", label: "Estado de la operación" },
      { id: "kpis", label: "Medición y red" },
      { id: "map", label: "Mapa de la red" },
      { id: "trends", label: "Tendencias" },
      { id: "modules", label: "Todos los módulos" },
    ],
  },
  "/inspections": { dynamic: "route" },
  "/advisory": {},
  "/advisory/guides": {},
  "/advisory/operators": {},
  "/advisory/workshops": {},
  "/organizations": {},
  "/energy": {
    sections: [
      { id: "kpis", label: "Estado de las fronteras" },
      { id: "upcoming", label: "Calibraciones por atender" },
      { id: "map", label: "Mapa de fronteras" },
      { id: "xm", label: "Novedades para XM" },
      { id: "recent", label: "Últimos registros" },
    ],
  },
  "/energy/points": {},
  "/energy/equipment": {},
  "/operations": {
    sections: [
      { id: "today", label: "Hoy" },
      { id: "measure", label: "Medir" },
      { id: "dosing", label: "Dosificación" },
      { id: "log", label: "Bitácora de operación" },
      { id: "readings", label: "Mediciones de campo" },
      { id: "meters", label: "Lecturas de medidores" },
      { id: "points", label: "Puntos de medición" },
    ],
  },
  "/system": {
    sections: [
      { id: "route", label: "Recorrido" },
      { id: "traffic-light", label: "Semáforo" },
      { id: "treatment", label: "Tratamiento" },
      { id: "findings", label: "Hallazgos", badge: OPEN_FINDINGS },
    ],
  },
  "/quality": {
    sections: [
      { id: "alerts", label: "Alertas" },
      { id: "lab", label: "Registrar análisis" },
      { id: "plan", label: "Plan de muestreo" },
      { id: "results", label: "Resultados" },
    ],
  },
  "/emergencies": {
    sections: [
      { id: "active", label: "Activas" },
      { id: "plan", label: "Plan de emergencia" },
      { id: "contacts", label: "Contactos" },
      { id: "history", label: "Historial" },
    ],
  },
  "/warehouse": {
    sections: [
      { id: "status", label: "Estado" },
      { id: "move", label: "Registrar movimiento" },
      { id: "items", label: "Artículos" },
      { id: "ppe", label: "EPP por tarea" },
      { id: "history", label: "Registro de bodega" },
    ],
  },
  "/sanitation": {
    sections: [
      { id: "components", label: "Componentes y lodos" },
      { id: "register", label: "Registro de saneamiento" },
      { id: "discharges", label: "Descargas productivas" },
    ],
  },
  "/improvement": {
    sections: [
      { id: "minimum-plan", label: "Plan mínimo de O&M" },
      { id: "inputs", label: "Insumos para el Plan de Mejora" },
      { id: "products", label: "Productos finales" },
    ],
  },
  "/compliance-reports": {},
  "/maintenance": {
    sections: [
      { id: "kpis", label: "Estado general" },
      { id: "orders", label: "Órdenes", badge: OVERDUE_ORDERS },
      { id: "pm-plans", label: "Mantenimiento preventivo" },
      { id: "events", label: "Eventos (lluvias, quejas)" },
      { id: "calendar", label: "Calendario anual" },
    ],
  },
  "/meters": {
    sections: [
      { id: "map", label: "Mapa de medidores" },
      { id: "distribution", label: "Distribución estadística" },
      { id: "fleet", label: "Flota" },
      { id: "gateways", label: "Concentradores" },
      { id: "retry-queue", label: "Cola de reintentos" },
      { id: "events", label: "Eventos y alarmas" },
      { id: "meters-list", label: "Medidores" },
    ],
  },
  "/vee": {
    sections: [
      { id: "validation", label: "V · Validación", badge: VEE_PENDING },
      { id: "estimation", label: "E · Estimación" },
      { id: "manual-edit", label: "E · Edición manual" },
    ],
  },
  "/consumption": {
    sections: [
      { id: "under-review", label: "En revisión" },
      { id: "orders", label: "Órdenes de relectura / inspección" },
    ],
  },
  "/control": {},
  "/network-balance": {
    sections: [
      { id: "map", label: "Mapa de zonas" },
      { id: "zones", label: "Zonas de red" },
      { id: "balances", label: "Balances por período" },
    ],
  },
  "/digital-twin": {
    sections: [
      { id: "map", label: "Mapa de activos" },
      { id: "assets", label: "Activos" },
    ],
  },
  "/network-model": {},
  "/team": {},
  "/group": {},
  "/program-observations": {},
  "/integrations": {},
  "/observability": {},
  "/configuration": {
    sections: [
      { id: "users", label: "Usuarios y roles" },
      { id: "session", label: "Sesión" },
      { id: "timezone", label: "Zona horaria" },
      { id: "region", label: "Región y moneda" },
      { id: "terms", label: "Terminología" },
      { id: "packs", label: "Paquetes" },
      { id: "assets", label: "Activos" },
      { id: "instrumentation", label: "Instrumentación" },
      { id: "hes-settings", label: "HES" },
      { id: "vee-rules", label: "Reglas VEE" },
      { id: "consumption-rules", label: "Reglas de consumo" },
      { id: "approval-levels", label: "Aprobación (SCR)" },
      { id: "protocol-mapping", label: "Mapeo OBIS" },
      { id: "protected-accounts", label: "Cuentas protegidas" },
      { id: "sla-policies", label: "SLA de mantenimiento" },
      { id: "failure-codes", label: "Códigos de falla" },
      { id: "crews", label: "Cuadrillas" },
    ],
  },
};

/** Los modulos de la sesion, agrupados como en el menu. */
export function navGroupsFor(modules: ProductModule[] | undefined): NavGroup[] {
  const groups: NavGroup[] = [];
  for (const m of modules ?? []) {
    let group = groups.find((g) => g.code === m.group.code);
    if (!group) {
      group = { code: m.group.code, title: m.group.label, items: [] };
      groups.push(group);
    }
    const screen = SCREENS[m.path] ?? {};
    group.items.push({ to: m.path, label: m.label, icon: m.icon, description: m.description ?? undefined, ...screen });
  }
  return groups;
}

/** Primera pantalla de la organizacion (la ONG entra a su tablero, una
 * comercializadora de energia a su tablero de fronteras). */
export function homeFor(modules: ProductModule[] | undefined): string {
  return modules?.[0]?.path ?? "/";
}

function matches(pathname: string, to: string): boolean {
  return to === "/" ? pathname === "/" : pathname === to || pathname.startsWith(`${to}/`);
}

function bestMatch(pathname: string, paths: string[]): string | null {
  let best: string | null = null;
  for (const to of paths) if (matches(pathname, to) && (!best || to.length > best.length)) best = to;
  return best;
}

/** La ruta pertenece a un modulo visible para la organizacion. Una pantalla
 * de detalle sin modulo propio (p. ej. /control/:id, /energy/points/:id) sigue
 * a su modulo; una ruta que no es de ninguna pantalla conocida no se bloquea. */
export function pathAllowed(pathname: string, modules: ProductModule[] | undefined): boolean {
  const visible = (modules ?? []).map((m) => m.path);
  if (pathname === "/operator") return visible.includes("/operations");
  const screen = bestMatch(pathname, Object.keys(SCREENS));
  if (!screen) return true;
  return bestMatch(pathname, visible) === screen;
}

/** Secciones de una pantalla, para su barra de secciones. */
export function sectionsFor(path: string): NavSectionDef[] {
  return SCREENS[path]?.sections ?? [];
}
