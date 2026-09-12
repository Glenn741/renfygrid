import { useState, type ReactNode } from "react";
import { Link, useLocation } from "react-router-dom";
import { useAuth } from "../auth";

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

const NAV_ITEMS: NavItem[] = [
  { to: "/", label: "Vista general", icon: "⌂" },
  { to: "/meters", label: "HES / Ingesta", icon: "\u{1F4E1}" },
  { to: "/vee", label: "VEE", icon: "✓" },
  { to: "/consumption", label: "Consumo", icon: "\u{1F4C8}" },
  { to: "/control", label: "Control (SCR)", icon: "⚡" },
  { to: "/network-balance", label: "Balance de Red", icon: "\u{1F4A7}" },
  { to: "/network-model", label: "Modelado Hidráulico", icon: "\u{1F30A}" },
  { to: "/integrations", label: "Integraciones (CIS)", icon: "\u{1F517}" },
  { to: "/observability", label: "Observabilidad", icon: "\u{1FA7A}" },
  { to: "/configuration", label: "Configuración", icon: "⚙" },
];

function isActive(pathname: string, to: string): boolean {
  if (to === "/") return pathname === "/";
  return pathname === to || pathname.startsWith(`${to}/`);
}

function SidebarContent({ onNavigate }: { onNavigate?: () => void }) {
  const location = useLocation();
  const { logout } = useAuth();

  return (
    <div className="flex h-full flex-col">
      <div className="px-5 py-5 flex items-center gap-2">
        <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-indigo-600 text-white font-bold text-sm">
          R
        </span>
        <div>
          <div className="text-sm font-bold text-white leading-tight">RenfyGrid</div>
          <div className="text-[11px] text-slate-400 leading-tight">Portal operativo</div>
        </div>
      </div>

      <nav className="flex-1 px-3 space-y-0.5 overflow-y-auto">
        {NAV_ITEMS.map((item) => {
          const active = isActive(location.pathname, item.to);
          return (
            <Link
              key={item.to}
              to={item.to}
              onClick={onNavigate}
              className={`flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
                active
                  ? "bg-indigo-600 text-white"
                  : "text-slate-300 hover:bg-white/5 hover:text-white"
              }`}
            >
              <span className="text-base leading-none">{item.icon}</span>
              {item.label}
            </Link>
          );
        })}
      </nav>

      <div className="px-3 pb-4 pt-2 border-t border-white/10">
        <button
          onClick={logout}
          className="flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium text-slate-300 hover:bg-white/5 hover:text-white"
        >
          <span className="text-base leading-none">&#8630;</span>
          Cerrar sesión
        </button>
      </div>
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
          <h1 className="text-base lg:text-lg font-bold text-slate-900">{title}</h1>
        </header>
        <main className="p-4 lg:p-6">{children}</main>
      </div>
    </div>
  );
}
