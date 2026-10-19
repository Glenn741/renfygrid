import { getFindings, getMaintenanceKpis, getVeeSummary, type TenantKind } from "./api";

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
  /** Que hace el modulo (tarjeta de la Vista general). */
  description?: string;
  /** Tipos de organizacion que ven el modulo (0047). Sin indicar: prestador y agrupacion. */
  kinds?: TenantKind[];
}

const OPERATING: TenantKind[] = ["provider", "group"];

/** El modulo es visible para ese tipo de organizacion. */
export function visibleFor(item: NavItemDef, kind: TenantKind | null | undefined): boolean {
  return (item.kinds ?? OPERATING).includes(kind ?? "provider");
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
      to: "/", label: "Vista general", icon: "overview", description: "Estado de la operación, la medición y la red, y acceso a todos los módulos",
      sections: [
        { id: "operation", label: "Estado de la operación" },
        { id: "kpis", label: "Medición y red" },
        { id: "map", label: "Mapa de la red" },
        { id: "trends", label: "Tendencias" },
        { id: "modules", label: "Todos los módulos" },
      ],
    }],
  },
  // Track E (2026-10-19): las guias son el punto de partida de un acueducto
  // sin guia de operacion; sus formularios dan el marco para operar.
  {
    title: "Punto de partida",
    items: [
      { to: "/inspections", label: "Guías", icon: "guides", description: "Las guías del programa: fichas, tablas y listas que dan el marco para operar", dynamic: "route" },
    ],
  },
  // La ONG que asesora (tipo 'advisor') solo ve esto.
  {
    title: "Asesoría",
    items: [
      { to: "/advisory", label: "Tablero de asesoría", icon: "overview", kinds: ["advisor"], description: "Operadores capacitados, guías cubiertas con cada uno y mapa temático" },
      { to: "/advisory/operators", label: "Operadores", icon: "organization", kinds: ["advisor"], description: "Operadores asesorados, sus guías y la carga por archivo" },
      { to: "/advisory/workshops", label: "Talleres", icon: "workshop", kinds: ["advisor"], description: "Talleres, guías que cubren, operadores y asistencia" },
    ],
  },
  {
    title: "Plataforma",
    items: [
      { to: "/organizations", label: "Organizaciones", icon: "organization", kinds: ["platform"], description: "Crear organizaciones (juntas, agrupaciones, ONG) y su primer usuario" },
    ],
  },
  {
    title: "Operación del sistema",
    items: [
      {
        to: "/operations", label: "Operación diaria", icon: "operations", description: "Rutina del operador: mediciones de campo, bitácora, dosificación y lectura de medidores",
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
        to: "/system", label: "Mi sistema", icon: "system", description: "Componentes por etapa, semáforo técnico, tren de tratamiento y hallazgos",
        sections: [
          { id: "route", label: "Recorrido" },
          { id: "traffic-light", label: "Semáforo" },
          { id: "treatment", label: "Tratamiento" },
          { id: "findings", label: "Hallazgos", badge: OPEN_FINDINGS },
        ],
      },
      {
        to: "/quality", label: "Calidad del agua", icon: "quality", description: "Alertas de calidad, análisis de laboratorio y plan de muestreo",
        sections: [
          { id: "alerts", label: "Alertas" },
          { id: "lab", label: "Registrar análisis" },
          { id: "plan", label: "Plan de muestreo" },
          { id: "results", label: "Resultados" },
        ],
      },
      {
        to: "/emergencies", label: "Emergencias", icon: "emergencies", description: "Plan por tipo de emergencia, contactos y activaciones",
        sections: [
          { id: "active", label: "Activas" },
          { id: "plan", label: "Plan de emergencia" },
          { id: "contacts", label: "Contactos" },
          { id: "history", label: "Historial" },
        ],
      },
      {
        to: "/warehouse", label: "Bodega y EPP", icon: "warehouse", description: "Insumos y EPP: existencias, vencimientos y cruce del cloro aplicado",
        sections: [
          { id: "status", label: "Estado" },
          { id: "move", label: "Registrar movimiento" },
          { id: "items", label: "Artículos" },
          { id: "ppe", label: "EPP por tarea" },
          { id: "history", label: "Registro de bodega" },
        ],
      },
      {
        to: "/sanitation", label: "Saneamiento", icon: "sanitation", description: "Componentes y lodos, registro de intervenciones y descargas productivas",
        sections: [
          { id: "components", label: "Componentes y lodos" },
          { id: "register", label: "Registro de saneamiento" },
          { id: "discharges", label: "Descargas productivas" },
        ],
      },
      {
        to: "/improvement", label: "Plan mínimo y mejora", icon: "improvement", description: "Plan mínimo de operación y mantenimiento, insumos para el Plan de Mejora y productos",
        sections: [
          { id: "minimum-plan", label: "Plan mínimo de O&M" },
          { id: "inputs", label: "Insumos para el Plan de Mejora" },
          { id: "products", label: "Productos finales" },
        ],
      },
      { to: "/compliance-reports", label: "Informe de cumplimiento", icon: "report", description: "Informe del período para la autoridad, que la organización decide enviar" },
      {
        to: "/maintenance", label: "Mantenimiento", icon: "maintenance", description: "Órdenes, preventivo programado, eventos y calendario anual",
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
        to: "/meters", label: "HES / Ingesta", icon: "metering", description: "Medidores, concentradores, flota y eventos/alarmas",
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
        to: "/vee", label: "VEE", icon: "validation", description: "Validación, estimación y edición manual de lecturas",
        sections: [
          { id: "validation", label: "V · Validación", badge: VEE_PENDING },
          { id: "estimation", label: "E · Estimación" },
          { id: "manual-edit", label: "E · Edición manual" },
        ],
      },
      {
        to: "/consumption", label: "Consumo", icon: "consumption", description: "Consumo facturable y anomalías bajo revisión",
        sections: [
          { id: "under-review", label: "En revisión" },
          { id: "orders", label: "Órdenes de relectura / inspección" },
        ],
      },
      { to: "/control", label: "Control (SCR)", icon: "control", description: "Suspensión, corte y reconexión remota" },
    ],
  },
  {
    title: "Red y pérdidas",
    items: [
      {
        to: "/network-balance", label: "Balance de Red", icon: "balance", description: "Agua no contabilizada, ILI y balance hídrico IWA por zona",
        sections: [
          { id: "map", label: "Mapa de zonas" },
          { id: "zones", label: "Zonas de red" },
          { id: "balances", label: "Balances por período" },
        ],
      },
      {
        to: "/digital-twin", label: "Gemelo Digital", icon: "twin", description: "Inventario georreferenciado de activos de red",
        sections: [
          { id: "map", label: "Mapa de activos" },
          { id: "assets", label: "Activos" },
        ],
      },
      { to: "/network-model", label: "Modelado Hidráulico", icon: "model", description: "Simulación hidráulica (EPANET/WNTR) de presión y caudal" },
    ],
  },
  {
    title: "Organización",
    items: [
      { to: "/team", label: "Usuarios", icon: "group", kinds: ["advisor", "platform"], description: "Usuarios de la organización y sus roles" },
      { to: "/group", label: "Agrupación", icon: "group", description: "Indicadores que cada organización miembro decide compartir" },
      { to: "/program-observations", label: "Observaciones del programa", icon: "observations", description: "Observaciones para mejorar los materiales del programa" },
      { to: "/integrations", label: "Integraciones (CIS)", icon: "integrations", description: "Feed unificado de órdenes y lecturas bajo demanda" },
      { to: "/observability", label: "Observabilidad", icon: "observability", description: "Alertas activas de ingesta en tiempo real" },
      {
        to: "/configuration", label: "Configuración", icon: "settings", description: "Usuarios, región, terminología, paquetes, reglas y parámetros",
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

/** Primera pantalla de un tipo de organizacion (la ONG entra a su tablero). */
export function homeFor(kind: TenantKind | null | undefined): string {
  for (const group of NAV_GROUPS) {
    for (const item of group.items) {
      if (visibleFor(item, kind)) return item.to;
    }
  }
  return "/";
}

/** La ruta pertenece a un modulo visible para ese tipo de organizacion. */
export function pathAllowed(pathname: string, kind: TenantKind | null | undefined): boolean {
  if (pathname === "/operator") return visibleFor({ to: "/operations", label: "", icon: "" }, kind);
  let best: NavItemDef | null = null;
  for (const group of NAV_GROUPS) {
    for (const item of group.items) {
      const match = item.to === "/" ? pathname === "/" : pathname === item.to || pathname.startsWith(`${item.to}/`);
      if (match && (!best || item.to.length > best.to.length)) best = item;
    }
  }
  // Pantallas de detalle sin item propio (p. ej. /control/:id) siguen a su modulo.
  if (!best) {
    const first = `/${pathname.split("/")[1] ?? ""}`;
    for (const group of NAV_GROUPS) for (const item of group.items) if (item.to === first) best = item;
  }
  return best ? visibleFor(best, kind) : true;
}

/** Secciones de un modulo, para la barra de secciones de su pantalla. */
export function sectionsFor(path: string): NavSectionDef[] {
  for (const group of NAV_GROUPS) {
    for (const item of group.items) {
      if (item.to === path) return item.sections ?? [];
    }
  }
  return [];
}
