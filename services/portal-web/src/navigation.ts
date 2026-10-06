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
      to: "/", label: "Vista general", icon: "overview",
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
        to: "/operations", label: "Operación diaria", icon: "operations",
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
      {
        to: "/system", label: "Mi sistema", icon: "system",
        sections: [
          { id: "route", label: "Recorrido" },
          { id: "traffic-light", label: "Semáforo" },
          { id: "treatment", label: "Tratamiento" },
          { id: "findings", label: "Hallazgos", badge: OPEN_FINDINGS },
        ],
      },
      {
        to: "/quality", label: "Calidad del agua", icon: "quality",
        sections: [
          { id: "alerts", label: "Alertas" },
          { id: "lab", label: "Registrar análisis" },
          { id: "plan", label: "Plan de muestreo" },
          { id: "results", label: "Resultados" },
        ],
      },
      {
        to: "/emergencies", label: "Emergencias", icon: "emergencies",
        sections: [
          { id: "active", label: "Activas" },
          { id: "plan", label: "Plan de emergencia" },
          { id: "contacts", label: "Contactos" },
          { id: "history", label: "Historial" },
        ],
      },
      {
        to: "/warehouse", label: "Bodega y EPP", icon: "warehouse",
        sections: [
          { id: "status", label: "Estado" },
          { id: "move", label: "Registrar movimiento" },
          { id: "items", label: "Artículos" },
          { id: "ppe", label: "EPP por tarea" },
          { id: "history", label: "Registro de bodega" },
        ],
      },
      {
        to: "/sanitation", label: "Saneamiento", icon: "sanitation",
        sections: [
          { id: "components", label: "Componentes y lodos" },
          { id: "register", label: "Registro de saneamiento" },
          { id: "discharges", label: "Descargas productivas" },
        ],
      },
      {
        to: "/improvement", label: "Plan mínimo y mejora", icon: "improvement",
        sections: [
          { id: "minimum-plan", label: "Plan mínimo de O&M" },
          { id: "inputs", label: "Insumos para el Plan de Mejora" },
          { id: "products", label: "Productos finales" },
        ],
      },
      { to: "/compliance-reports", label: "Informe de cumplimiento", icon: "report" },
      { to: "/inspections", label: "Ruta y revisiones", icon: "inspections", dynamic: "route" },
      {
        to: "/maintenance", label: "Mantenimiento", icon: "maintenance",
        sections: [
          { id: "kpis", label: "Estado general" },
          { id: "orders", label: "Órdenes", badge: OVERDUE_ORDERS },
          { id: "pm-plans", label: "Mantenimiento preventivo" },
          { id: "events", label: "Eventos (lluvias, quejas)" },
          { id: "calendar", label: "Calendario anual" },
        ],
      },
    ],
  },
  {
    title: "Medición (MDM)",
    items: [
      {
        to: "/meters", label: "HES / Ingesta", icon: "metering",
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
        to: "/vee", label: "VEE", icon: "validation",
        sections: [
          { id: "validation", label: "V · Validación", badge: VEE_PENDING },
          { id: "estimation", label: "E · Estimación" },
          { id: "manual-edit", label: "E · Edición manual" },
        ],
      },
      {
        to: "/consumption", label: "Consumo", icon: "consumption",
        sections: [
          { id: "under-review", label: "En revisión" },
          { id: "orders", label: "Órdenes de relectura / inspección" },
        ],
      },
      { to: "/control", label: "Control (SCR)", icon: "control" },
    ],
  },
  {
    title: "Red y pérdidas",
    items: [
      {
        to: "/network-balance", label: "Balance de Red", icon: "balance",
        sections: [
          { id: "map", label: "Mapa de zonas" },
          { id: "zones", label: "Zonas de red" },
          { id: "balances", label: "Balances por período" },
        ],
      },
      {
        to: "/digital-twin", label: "Gemelo Digital", icon: "twin",
        sections: [
          { id: "map", label: "Mapa de activos" },
          { id: "assets", label: "Activos" },
        ],
      },
      { to: "/network-model", label: "Modelado Hidráulico", icon: "model" },
    ],
  },
  {
    title: "Plataforma",
    items: [
      { to: "/group", label: "Agrupación", icon: "group" },
      { to: "/program-observations", label: "Observaciones del programa", icon: "observations" },
      { to: "/integrations", label: "Integraciones (CIS)", icon: "integrations" },
      { to: "/observability", label: "Observabilidad", icon: "observability" },
      {
        to: "/configuration", label: "Configuración", icon: "settings",
        sections: [
          { id: "users", label: "Usuarios y roles" },
          { id: "session", label: "Sesión" },
          { id: "timezone", label: "Zona horaria" },
          { id: "region", label: "Región y moneda" },
          { id: "terms", label: "Terminología" },
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
