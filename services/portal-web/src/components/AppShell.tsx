import { useEffect, useState, type ReactNode } from "react";
import { Link, useLocation } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { getProcessRoute } from "../api";
import { NAV_GROUPS, type NavBadge, type NavItemDef } from "../navigation";
import { ActiveSectionProvider, scrollToSection, useActiveSection } from "./activeSection";
import { SessionMenu, useSessionInfo } from "./SessionMenu";
import { ROUTE_QUERY_KEY, STAGE_STATE_STYLE, stageState } from "./routeStatus";
import { Icon } from "./Icon";

// Shell visual compartido (Sprint C9; menu agrupado por proceso y submenus
// contextuales 2026-10-05, a pedido del usuario: "la vision de proceso no es
// claramente visible en el menu" y "optimiza asi los otros menus").
//
// Cada modulo con secciones internas muestra esas secciones como submenu:
//   - aparece solo dentro del modulo, o si el usuario lo despliega con la
//     flecha (se recuerda por navegador);
//   - marca la seccion visible (estado compartido con la barra de secciones
//     de la pagina) y lleva directo a cualquier seccion desde otro modulo;
//   - las secciones que piden atencion muestran un contador.
// "Ruta y revisiones" muestra en cambio las etapas de la ruta del paquete de
// la organizacion. La estructura vive en src/navigation.ts.

const OPEN_KEY = "renfygrid.nav.open";

function readOpen(): Record<string, boolean> {
  try {
    const raw = window.localStorage.getItem(OPEN_KEY);
    return raw ? (JSON.parse(raw) as Record<string, boolean>) : {};
  } catch {
    return {};
  }
}

function writeOpen(value: Record<string, boolean>): void {
  try {
    window.localStorage.setItem(OPEN_KEY, JSON.stringify(value));
  } catch {
    // preferencia de vista; si el navegador no deja guardar, no pasa nada
  }
}

function isActive(pathname: string, to: string): boolean {
  if (to === "/") return pathname === "/";
  return pathname === to || pathname.startsWith(`${to}/`);
}

const SUBITEM_CLASS = "flex items-center gap-2 rounded-md px-2 py-1.5 text-[13px] transition-colors";
const SUBITEM_ACTIVE = "bg-white/10 font-semibold text-white";
const SUBITEM_IDLE = "text-slate-400 hover:bg-white/5 hover:text-white";

function BadgeCount({ badge }: { badge: NavBadge }) {
  const { data } = useQuery({ queryKey: badge.queryKey, queryFn: badge.fetch, staleTime: 60_000 });
  if (!data) return null;
  const tone = badge.tone === "alert" ? "bg-red-500/90 text-white" : "bg-white/15 text-slate-200";
  return (
    <span className={`shrink-0 rounded-full px-1.5 text-[10px] font-bold leading-4 tabular-nums ${tone}`} aria-label={`${data} ${badge.meaning}`} title={`${data} ${badge.meaning}`}>
      {data > 99 ? "99+" : data}
    </span>
  );
}

function SectionSubmenu({ item, pathname, onNavigate }: { item: NavItemDef; pathname: string; onNavigate?: () => void }) {
  const { active } = useActiveSection();
  const here = pathname === item.to;
  return (
    <ol className="mt-0.5 mb-1 ml-5 space-y-0.5 border-l border-white/10 pl-2" aria-label={`Secciones de ${item.label}`}>
      {(item.sections ?? []).map((s) => {
        const current = here && active === s.id;
        return (
          <li key={s.id}>
            <Link
              to={`${item.to}#${s.id}`}
              onClick={() => {
                // En la misma pantalla, el hash puede no cambiar (mismo destino dos veces): llevar igual.
                if (here) scrollToSection(s.id);
                onNavigate?.();
              }}
              aria-current={current ? "location" : undefined}
              className={`${SUBITEM_CLASS} ${current ? SUBITEM_ACTIVE : SUBITEM_IDLE}`}
            >
              <span className="min-w-0 flex-1 truncate">{s.label}</span>
              {s.badge && <BadgeCount badge={s.badge} />}
            </Link>
          </li>
        );
      })}
    </ol>
  );
}

/** Etapas de la ruta del paquete de la organizacion; sin ruta no muestra nada. */
function RouteSubmenu({ basePath, pathname, onNavigate }: { basePath: string; pathname: string; onNavigate?: () => void }) {
  const { data } = useQuery({ queryKey: ROUTE_QUERY_KEY, queryFn: getProcessRoute, staleTime: 60_000 });
  if (!data || data.stages.length === 0) return null;
  return (
    <ol className="mt-0.5 mb-1 ml-5 space-y-0.5 border-l border-white/10 pl-2" aria-label="Etapas de la ruta">
      {data.stages.map((s) => {
        const to = `${basePath}/${s.code}`;
        const current = pathname === to;
        const style = STAGE_STATE_STYLE[stageState(s)];
        return (
          <li key={s.code}>
            <Link
              to={to}
              onClick={onNavigate}
              aria-current={current ? "page" : undefined}
              title={`${s.title} · ${style.label}`}
              className={`${SUBITEM_CLASS} ${current ? SUBITEM_ACTIVE : SUBITEM_IDLE}`}
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

function SidebarContent({ onNavigate }: { onNavigate?: () => void }) {
  const location = useLocation();
  const { data: session } = useSessionInfo();
  const [open, setOpen] = useState<Record<string, boolean>>(readOpen);
  const toggle = (to: string) => {
    setOpen((current) => {
      const next = { ...current, [to]: !current[to] };
      writeOpen(next);
      return next;
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
                const hasSubmenu = Boolean(item.dynamic || (item.sections && item.sections.length > 1));
                const expanded = hasSubmenu && (active || Boolean(open[item.to]));
                return (
                  <div key={item.to}>
                    <div className="flex items-center">
                      <Link
                        to={item.to}
                        onClick={onNavigate}
                        aria-current={location.pathname === item.to ? "page" : undefined}
                        className={`flex flex-1 items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
                          active
                            ? "bg-indigo-600 text-white"
                            : "text-slate-300 hover:bg-white/5 hover:text-white"
                        }`}
                      >
                        <Icon name={item.icon} className="h-4 w-4 shrink-0" />
                        {item.label}
                      </Link>
                      {hasSubmenu && !active && (
                        <button
                          onClick={() => toggle(item.to)}
                          aria-expanded={expanded}
                          aria-label={expanded ? `Ocultar el contenido de ${item.label}` : `Mostrar el contenido de ${item.label}`}
                          title={expanded ? "Ocultar" : "Mostrar contenido"}
                          className="ml-1 flex h-8 w-8 items-center justify-center rounded-lg text-slate-400 hover:bg-white/5 hover:text-white focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-400"
                        >
                          <span className={`transition-transform ${expanded ? "rotate-90" : ""}`}><Icon name="expand" className="h-3.5 w-3.5" /></span>
                        </button>
                      )}
                    </div>
                    {expanded && item.dynamic === "route" && (
                      <RouteSubmenu basePath={item.to} pathname={location.pathname} onNavigate={onNavigate} />
                    )}
                    {expanded && !item.dynamic && <SectionSubmenu item={item} pathname={location.pathname} onNavigate={onNavigate} />}
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

/** Al llegar con #seccion (desde el submenu de otro modulo), llevar a esa
 * seccion. Se reintenta una vez porque los datos de la pagina pueden mover
 * la posicion mientras cargan. */
function useScrollToHash() {
  const { pathname, hash } = useLocation();
  useEffect(() => {
    if (!hash) return;
    const id = decodeURIComponent(hash.slice(1));
    const first = window.setTimeout(() => scrollToSection(id), 80);
    const second = window.setTimeout(() => scrollToSection(id), 700);
    return () => { window.clearTimeout(first); window.clearTimeout(second); };
  }, [pathname, hash]);
}

interface AppShellProps {
  title: string;
  children: ReactNode;
}

export function AppShell({ title, children }: AppShellProps) {
  return (
    <ActiveSectionProvider>
      <ShellLayout title={title}>{children}</ShellLayout>
    </ActiveSectionProvider>
  );
}

function ShellLayout({ title, children }: AppShellProps) {
  const [mobileOpen, setMobileOpen] = useState(false);
  useScrollToHash();

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
            <Icon name="menu" className="h-4 w-4" />
          </button>
          <h1 className="text-base lg:text-lg font-bold text-slate-900 truncate">{title}</h1>
          <SessionMenu />
        </header>
        <main className="p-4 lg:p-6">{children}</main>
      </div>
    </div>
  );
}
