import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { getSession } from "../api";
import { useAuth } from "../auth";

// Menu de sesion del encabezado (2026-10-05, a pedido del usuario: "en el
// banner superior hacen falta datos basicos de la sesion: tenant, usuario,
// tiempo en sesion"). Patron estandar de portales SaaS: organizacion activa,
// usuario y acciones de cuenta arriba a la derecha; el menu lateral queda
// solo para navegar. Vale para cualquier tenant: todo sale de /auth/me.

const ROLE_LABEL: Record<string, string> = {
  supervisor: "Supervisor",
  integration: "Integración",
};

function formatDuration(ms: number): string {
  const totalMinutes = Math.max(0, Math.floor(ms / 60000));
  const hours = Math.floor(totalMinutes / 60);
  const minutes = totalMinutes % 60;
  if (hours === 0) return `${minutes} min`;
  return `${hours} h ${String(minutes).padStart(2, "0")} min`;
}

function initials(email: string): string {
  const name = email.split("@")[0] ?? "";
  const parts = name.split(/[._-]+/).filter(Boolean);
  return ((parts[0]?.[0] ?? "") + (parts[1]?.[0] ?? parts[0]?.[1] ?? "")).toUpperCase() || "?";
}

export function useSessionInfo() {
  return useQuery({ queryKey: ["session"], queryFn: getSession, staleTime: 5 * 60 * 1000 });
}

export function SessionMenu() {
  const { logout } = useAuth();
  const { data } = useSessionInfo();
  const [now, setNow] = useState(() => Date.now());
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const id = window.setInterval(() => setNow(Date.now()), 30000);
    return () => window.clearInterval(id);
  }, []);

  useEffect(() => {
    if (!open) return;
    const onClick = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", onClick);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onClick);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const expiresAt = data ? new Date(data.expires_at).getTime() : null;
  const issuedAt = data?.issued_at ? new Date(data.issued_at).getTime() : null;
  const remaining = expiresAt !== null ? expiresAt - now : null;
  const elapsed = issuedAt !== null ? now - issuedAt : null;

  // Sesion vencida: salir de forma ordenada en vez de esperar al primer 401.
  useEffect(() => {
    if (remaining !== null && remaining <= 0) {
      logout();
      window.location.href = "/login";
    }
  }, [remaining, logout]);

  if (!data) return null;
  const nearExpiry = remaining !== null && remaining < 15 * 60000;
  const role = data.role ? ROLE_LABEL[data.role] ?? data.role : null;

  return (
    <div ref={ref} className="relative ml-auto flex items-center gap-3">
      <span className="hidden md:inline-flex items-center gap-1.5 rounded-full bg-indigo-50 px-3 py-1 text-xs font-semibold text-indigo-700" title={`Organización: ${data.tenant_name ?? data.tenant_id}`}>
        <span aria-hidden>🏢</span>{data.tenant_name ?? data.tenant_id.slice(0, 8)}
      </span>
      {remaining !== null && (
        <span className={`hidden lg:inline text-xs tabular-nums ${nearExpiry ? "text-amber-700 font-semibold" : "text-slate-500"}`}>
          {elapsed !== null && <>En sesión {formatDuration(elapsed)} · </>}vence en {formatDuration(remaining)}
        </span>
      )}
      <button
        onClick={() => setOpen((o) => !o)}
        aria-haspopup="menu"
        aria-expanded={open}
        className="flex items-center gap-2 rounded-lg border border-slate-200 px-2 py-1 hover:bg-slate-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500"
      >
        <span className="flex h-7 w-7 items-center justify-center rounded-full bg-indigo-600 text-[11px] font-bold text-white">{initials(data.email)}</span>
        <span className="hidden sm:block text-left leading-tight">
          <span className="block text-xs font-semibold text-slate-800 max-w-[14rem] truncate">{data.email}</span>
          {role && <span className="block text-[11px] text-slate-500">{role}</span>}
        </span>
        <span aria-hidden className="text-slate-400 text-xs">▾</span>
      </button>

      {open && (
        <div role="menu" className="absolute right-0 top-full mt-2 w-72 rounded-xl border border-slate-200 bg-white p-4 shadow-lg z-50">
          <dl className="space-y-2 text-sm">
            <div>
              <dt className="text-[11px] uppercase tracking-wide text-slate-500">Organización</dt>
              <dd className="font-semibold text-slate-800">{data.tenant_name ?? "—"}</dd>
              <dd className="text-[11px] text-slate-400 font-mono break-all">{data.tenant_id}</dd>
            </div>
            <div>
              <dt className="text-[11px] uppercase tracking-wide text-slate-500">Usuario</dt>
              <dd className="text-slate-800 break-all">{data.email}{role ? ` · ${role}` : ""}</dd>
            </div>
            <div>
              <dt className="text-[11px] uppercase tracking-wide text-slate-500">Sesión</dt>
              <dd className="text-slate-800 tabular-nums">
                {issuedAt !== null && <>Inició {new Date(issuedAt).toLocaleTimeString("es", { hour: "2-digit", minute: "2-digit" })} · </>}
                {elapsed !== null && <>{formatDuration(elapsed)} en sesión</>}
              </dd>
              {remaining !== null && (
                <dd className={`tabular-nums ${nearExpiry ? "text-amber-700 font-semibold" : "text-slate-500"}`}>
                  Vence a las {new Date(expiresAt!).toLocaleTimeString("es", { hour: "2-digit", minute: "2-digit" })} (en {formatDuration(remaining)})
                </dd>
              )}
            </div>
          </dl>
          <button
            role="menuitem"
            onClick={() => { logout(); window.location.href = "/login"; }}
            className="mt-4 w-full rounded-lg border border-slate-300 px-3 py-1.5 text-sm font-semibold text-slate-700 hover:bg-slate-50"
          >
            Cerrar sesión
          </button>
        </div>
      )}
    </div>
  );
}
