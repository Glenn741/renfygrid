import { getFindings, getMaintenanceKpis, getVeeSummary } from "./api";

// Estructura de navegacion del Portal (2026-10-05): UNA sola definicion de
// modulos y de sus secciones internas, usada por el menu lateral (submenu
// contextual) y por la barra de secciones de cada pantalla. Antes cada
// pagina tenia su propia lista de secciones; asi el menu y la pagina no
// pueden decir cosas distintas.
//
// Es la estructura del producto (vocabulario fijo del motor, igual para
// todos los tenants). Lo que cambia por organizacion -- las etapas de la
// ruta del programa -- no va aca: sale del paquete (`/process-route`).

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

export const NAV_GROUPS: { title: string | null; items: NavItemDef[] }[] = [
  {
    title: null,
    items: [{
      to: "/", label: "Vista general", icon: "⌂",
      sections: [
        { id: "kpis", label: "Estado general" },
        { id: "map", label: "Mapa de la red" },
        { id: "trends", label: "Tendencias" },
        { id: "modules", label: "Todos los módulos" },
      ],
    }],
  },
  {
    title: "Operación del sistema",
    items: [
      {
        to: "/system", label: "Mi sistema", icon: "\u{1F6B0}",
        sections: [
          { id: "route", label: "Recorrido" },
          { id: "traffic-light", label: "Semáforo" },
          { id: "treatment", label: "Tratamiento" },
          { id: "findings", label: "Hallazgos", badge: OPEN_FINDINGS },
        ],
      },
      { to: "/inspections", label: "Ruta y revisiones", icon: "\u{1F4CB}", dynamic: "route" },
      {
        to: "/maintenance", label: "Mantenimiento", icon: "\u{1F527}",
        sections: [
          { id: "kpis", label: "Estado general" },
          { id: "orders", label: "Órdenes", badge: OVERDUE_ORDERS },
          { id: "pm-plans", label: "Mantenimiento preventivo" },
        ],
      },
    ],
  },
  {
    title: "Medición (MDM)",
    items: [
      {
        to: "/meters", label: "HES / Ingesta", icon: "\u{1F4E1}",
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
      {
        to: "/vee", label: "VEE", icon: "✓",
        sections: [
          { id: "validation", label: "V · Validación", badge: VEE_PENDING },
          { id: "estimation", label: "E · Estimación" },
          { id: "manual-edit", label: "E · Edición manual" },
        ],
      },
      {
        to: "/consumption", label: "Consumo", icon: "\u{1F4C8}",
        sections: [
          { id: "under-review", label: "En revisión" },
          { id: "orders", label: "Órdenes de relectura / inspección" },
        ],
      },
      { to: "/control", label: "Control (SCR)", icon: "⚡" },
    ],
  },
  {
    title: "Red y pérdidas",
    items: [
      {
        to: "/network-balance", label: "Balance de Red", icon: "\u{1F4A7}",
        sections: [
          { id: "map", label: "Mapa de zonas" },
          { id: "zones", label: "Zonas de red" },
          { id: "balances", label: "Balances por período" },
        ],
      },
      {
        to: "/digital-twin", label: "Gemelo Digital", icon: "\u{1F5FA}",
        sections: [
          { id: "map", label: "Mapa de activos" },
          { id: "assets", label: "Activos" },
        ],
      },
      { to: "/network-model", label: "Modelado Hidráulico", icon: "\u{1F30A}" },
    ],
  },
  {
    title: "Plataforma",
    items: [
      { to: "/integrations", label: "Integraciones (CIS)", icon: "\u{1F517}" },
      { to: "/observability", label: "Observabilidad", icon: "\u{1FA7A}" },
      {
        to: "/configuration", label: "Configuración", icon: "⚙",
        sections: [
          { id: "session", label: "Sesión" },
          { id: "packs", label: "Paquetes" },
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
    ],
  },
];

/** Secciones de un modulo, para la barra de secciones de su pantalla. */
export function sectionsFor(path: string): NavSectionDef[] {
  for (const group of NAV_GROUPS) {
    for (const item of group.items) {
      if (item.to === path) return item.sections ?? [];
    }
  }
  return [];
}
