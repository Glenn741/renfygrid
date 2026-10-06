import { useState, type ReactNode } from "react";
import { Link, useLocation } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { getProcessRoute } from "../api";
import { SessionMenu, useSessionInfo } from "./SessionMenu";
import { ROUTE_QUERY_KEY, STAGE_STATE_STYLE, stageState } from "./routeStatus";

const ROUTE_PATH = "/inspections";
const ROUTE_OPEN_KEY = "renfygrid.nav.route.open";

function readRouteOpen(): boolean {
  try {
    return window.localStorage.getItem(ROUTE_OPEN_KEY) === "1";
  } catch {
    return false;
  }
}

function writeRouteOpen(open: boolean): void {
  try {
    window.localStorage.setItem(ROUTE_OPEN_KEY, open ? "1" : "0");
  } catch {
    // preferencia de vista; si el navegador no deja guardar, no pasa nada
  }
}

/** Submenu contextual de "Ruta y revisiones" (2026-10-05): las etapas de la
 * ruta del paquete de la organizacion, con su estado. Solo aparece dentro del
 * modulo o si el usuario lo despliega; sin ruta (p. ej. un tenant solo MDM)
 * no muestra nada. */
function RouteSubmenu({ pathname, onNavigate }: { pathname: string; onNavigate?: () => void }) {
  const { data } = useQuery({ queryKey: ROUTE_QUERY_KEY, queryFn: getProcessRoute, staleTime: 60_000 });
  if (!data || data.stages.length === 0) return null;
  return (
    <ol className="mt-0.5 mb-1 ml-5 space-y-0.5 border-l border-white/10 pl-2" aria-label="Etapas de la ruta">
      {data.stages.map((s) => {
        const to = `${ROUTE_PATH}/${s.code}`;
        const active = pathname === to;
        const style = STAGE_STATE_STYLE[stageState(s)];
        return (
          <li key={s.code}>
            <Link
              to={to}
              onClick={onNavigate}
              aria-current={active ? "page" : undefined}
              title={`${s.title} · ${style.label}`}
              className={`flex items-center gap-2 rounded-md px-2 py-1.5 text-[13px] transition-colors ${
                active ? "bg-white/10 font-semibold text-white" : "text-slate-400 hover:bg-white/5 hover:text-white"
              }`}
            >
              <span className="w-3 shrink-0 text-right text-[11px] tabular-nums text-slate-500">{s.order}</span>
              <span className="min-w-0 flex-1 truncate">{s.title}</span>
              <span className={`h-2 w-2 shrink-0 rounded-full ${style.dot}`} aria-label={style.label} />
            </Link>
          </li>
        );
      })}
    </ol>
  );
}

// Shell visual compartido (Sprint C9, docs/04-plan-sprints.md E18): rebranding
// + navegacion lateral real para las 9 pantallas existentes -- capa puramente
// visual, ninguna pantalla cambia su logica (queries, mutaciones, tablas)
// para adoptar esto; solo cambia el wrapper que las envuelve (StagePage) o,
// en el caso de Overview, su JSX de layout.

interface NavItem {
  to: string;
  label: string;
  icon: string;
}

// Menu agrupado por proceso (2026-10-05, a pedido del usuario: "la vision
// de proceso no es claramente visible en el menu"). Los grupos siguen el
// recorrido del agua y de la gestion: operar el sistema, medir, entender las
// perdidas de la red, mantener, y la plataforma. Son la estructura del
// producto (vocabulario fijo del motor), no datos de un tenant.
const NAV_GROUPS: { title: string | null; items: NavItem[] }[] = [
  { title: null, items: [{ to: "/", label: "Vista general", icon: "⌂" }] },
  {
    title: "Operación del sistema",
    items: [
      { to: "/system", label: "Mi sistema", icon: "\u{1F6B0}" },
      { to: "/inspections", label: "Ruta y revisiones", icon: "\u{1F4CB}" },
      { to: "/maintenance", label: "Mantenimiento", icon: "\u{1F527}" },
    ],
  },
  {
    title: "Medición (MDM)",
    items: [
      { to: "/meters", label: "HES / Ingesta", icon: "\u{1F4E1}" },
      { to: "/vee", label: "VEE", icon: "✓" },
      { to: "/consumption", label: "Consumo", icon: "\u{1F4C8}" },
      { to: "/control", label: "Control (SCR)", icon: "⚡" },
    ],
  },
  {
    title: "Red y pérdidas",
    items: [
      { to: "/network-balance", label: "Balance de Red", icon: "\u{1F4A7}" },
      { to: "/digital-twin", label: "Gemelo Digital", icon: "\u{1F5FA}" },
      { to: "/network-model", label: "Modelado Hidráulico", icon: "\u{1F30A}" },
    ],
  },
  {
    title: "Plataforma",
    items: [
      { to: "/integrations", label: "Integraciones (CIS)", icon: "\u{1F517}" },
      { to: "/observability", label: "Observabilidad", icon: "\u{1FA7A}" },
      { to: "/configuration", label: "Configuración", icon: "⚙" },
    ],
  },
];

function isActive(pathname: string, to: string): boolean {
  if (to === "/") return pathname === "/";
  return pathname === to || pathname.startsWith(`${to}/`);
}

function SidebarContent({ onNavigate }: { onNavigate?: () => void }) {
  const location = useLocation();
  const { data: session } = useSessionInfo();
  const [routeOpen, setRouteOpen] = useState(readRouteOpen);
  const inRoute = isActive(location.pathname, ROUTE_PATH);
  const toggleRoute = () => {
    setRouteOpen((open) => {
      writeRouteOpen(!open);
      return !open;
    });
  };

  return (
    <div className="flex h-full flex-col">
      <div className="px-5 py-5 flex items-center gap-2">
        <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-indigo-600 text-white font-bold text-sm">
          R
        </span>
        <div className="min-w-0">
          <div className="text-sm font-bold text-white leading-tight">RenfyGrid</div>
          <div className="text-[11px] text-slate-400 leading-tight truncate" title={session?.tenant_name ?? undefined}>
            {session?.tenant_name ?? "Portal operativo"}
          </div>
        </div>
      </div>

      <nav className="flex-1 px-3 pb-4 overflow-y-auto" aria-label="Menú principal">
        {NAV_GROUPS.map((group) => (
          <div key={group.title ?? "inicio"} className="mb-3">
            {group.title && (
              <div className="px-3 pb-1 pt-2 text-[10px] font-semibold uppercase tracking-wider text-slate-500">{group.title}</div>
            )}
            <div className="space-y-0.5">
              {group.items.map((item) => {
                const active = isActive(location.pathname, item.to);
                const isRoute = item.to === ROUTE_PATH;
                const expanded = isRoute && (inRoute || routeOpen);
                return (
                  <div key={item.to}>
                    <div className="flex items-center">
                      <Link
                        to={item.to}
                        onClick={onNavigate}
                        aria-current={active && location.pathname === item.to ? "page" : undefined}
                        className={`flex flex-1 items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
                          active
                            ? "bg-indigo-600 text-white"
                            : "text-slate-300 hover:bg-white/5 hover:text-white"
                        }`}
                      >
                        <span className="text-base leading-none">{item.icon}</span>
                        {item.label}
                      </Link>
                      {isRoute && !inRoute && (
                        <button
                          onClick={toggleRoute}
                          aria-expanded={expanded}
                          aria-label={expanded ? "Ocultar las etapas de la ruta" : "Mostrar las etapas de la ruta"}
                          title={expanded ? "Ocultar etapas" : "Mostrar etapas"}
                          className="ml-1 flex h-8 w-8 items-center justify-center rounded-lg text-slate-400 hover:bg-white/5 hover:text-white focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-400"
                        >
                          <span aria-hidden className={`text-xs transition-transform ${expanded ? "rotate-90" : ""}`}>▸</span>
                        </button>
                      )}
                    </div>
                    {expanded && <RouteSubmenu pathname={location.pathname} onNavigate={onNavigate} />}
                  </div>
                );
              })}
            </div>
          </div>
        ))}
      </nav>
    </div>
  );
}

interface AppShellProps {
  title: string;
  children: ReactNode;
}

export function AppShell({ title, children }: AppShellProps) {
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <div className="min-h-screen bg-slate-50 lg:flex">
      {/* Sidebar -- fija en desktop, cajon deslizante en movil */}
      <aside className="hidden lg:block lg:w-60 lg:shrink-0 bg-ink">
        <div className="fixed inset-y-0 left-0 w-60 bg-ink">
          <SidebarContent />
        </div>
      </aside>

      {mobileOpen && (
        <div className="lg:hidden fixed inset-0 z-40 flex">
          <div className="w-64 bg-ink">
            <SidebarContent onNavigate={() => setMobileOpen(false)} />
          </div>
          <button
            aria-label="Cerrar menú"
            className="flex-1 bg-slate-900/50"
            onClick={() => setMobileOpen(false)}
          />
        </div>
      )}

      <div className="flex-1 min-w-0">
        <header className="sticky top-0 z-30 border-b border-slate-200 bg-white px-4 lg:px-6 py-3.5 flex items-center gap-3">
          <button
            aria-label="Abrir menú"
            className="lg:hidden flex h-8 w-8 items-center justify-center rounded-lg border border-slate-200 text-slate-600"
            onClick={() => setMobileOpen(true)}
          >
            ☰
          </button>
          <h1 className="text-base lg:text-lg font-bold text-slate-900 truncate">{title}</h1>
          <SessionMenu />
        </header>
        <main className="p-4 lg:p-6">{children}</main>
      </div>
    </div>
  );
}
