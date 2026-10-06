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
        to: "/operations", label: "Operación diaria", icon: "\u{1F4A7}",
        sections: [
          { id: "today", label: "Hoy" },
          { id: "measure", label: "Medir" },
          { id: "dosing", label: "Dosificación" },
          { id: "log", label: "Bitácora 7C" },
          { id: "readings", label: "Mediciones 7B" },
          { id: "meters", label: "Lecturas de medidores" },
          { id: "points", label: "Puntos de medición" },
        ],
      },
      {
        to: "/system", label: "Mi sistema", icon: "\u{1F6B0}",
        sections: [
          { id: "route", label: "Recorrido" },
          { id: "traffic-light", label: "Semáforo" },
          { id: "treatment", label: "Tratamiento" },
          { id: "findings", label: "Hallazgos", badge: OPEN_FINDINGS },
        ],
      },
      {
        to: "/quality", label: "Calidad del agua", icon: "\u{1F9EA}",
        sections: [
          { id: "alerts", label: "Alertas" },
          { id: "lab", label: "Registrar análisis" },
          { id: "plan", label: "Plan de muestreo" },
          { id: "results", label: "Resultados" },
        ],
      },
      {
        to: "/emergencies", label: "Emergencias", icon: "\u{1F6A8}",
        sections: [
          { id: "active", label: "Activas" },
          { id: "plan", label: "Plan de emergencia" },
          { id: "contacts", label: "Contactos" },
          { id: "history", label: "Historial" },
        ],
      },
      {
        to: "/warehouse", label: "Bodega y EPP", icon: "\u{1F4E6}",
        sections: [
          { id: "status", label: "Estado" },
          { id: "move", label: "Registrar movimiento" },
          { id: "items", label: "Artículos" },
          { id: "ppe", label: "EPP por tarea" },
          { id: "history", label: "Registro de bodega" },
        ],
      },
      {
        to: "/sanitation", label: "Saneamiento", icon: "\u{1F6BD}",
        sections: [
          { id: "components", label: "Componentes y lodos" },
          { id: "register", label: "Registro 7F" },
          { id: "discharges", label: "Descargas productivas" },
        ],
      },
      {
        to: "/improvement", label: "Plan mínimo y mejora", icon: "\u{1F5D2}",
        sections: [
          { id: "minimum-plan", label: "Plan mínimo de O&M" },
          { id: "inputs", label: "Insumos 7G.2" },
          { id: "products", label: "Productos 7H" },
        ],
      },
      { to: "/inspections", label: "Ruta y revisiones", icon: "\u{1F4CB}", dynamic: "route" },
      {
        to: "/maintenance", label: "Mantenimiento", icon: "\u{1F527}",
        sections: [
          { id: "kpis", label: "Estado general" },
          { id: "orders", label: "Órdenes", badge: OVERDUE_ORDERS },
          { id: "pm-plans", label: "Mantenimiento preventivo" },
          { id: "events", label: "Eventos (lluvias, quejas)" },
          { id: "calendar", label: "Calendario anual 7G" },
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
      { to: "/group", label: "Agrupación", icon: "\u{1F91D}" },
      { to: "/program-observations", label: "Mejora de las guías (T-10)", icon: "\u{1F4DD}" },
      { to: "/integrations", label: "Integraciones (CIS)", icon: "\u{1F517}" },
      { to: "/observability", label: "Observabilidad", icon: "\u{1FA7A}" },
      {
        to: "/configuration", label: "Configuración", icon: "⚙",
        sections: [
          { id: "users", label: "Usuarios y roles" },
          { id: "session", label: "Sesión" },
          { id: "timezone", label: "Zona horaria" },
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
