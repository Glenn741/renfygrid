import { useEffect, useState } from "react";
import { getUiCatalog, type UiCatalog } from "./api";

// Catalogo de la organizacion (base generica, migracion 0045): todo lo que la
// interfaz nombra sale de aqui y no del codigo -- etiquetas de codigos,
// terminologia ("junta", "ente rector"...), formatos del paquete ("7G.2"),
// moneda y region. Se carga una vez por sesion; la pantalla se pinta cuando
// esta disponible. Sin red (app del operador) se usa la ultima copia guardada
// en el dispositivo; sin ninguna, se muestran los codigos tal cual.

let current: UiCatalog | null = null;
const CACHE_KEY = "renfygrid.catalog";

function readCache(): UiCatalog | null {
  try {
    const raw = localStorage.getItem(CACHE_KEY);
    return raw ? (JSON.parse(raw) as UiCatalog) : null;
  } catch {
    return null;
  }
}

function writeCache(c: UiCatalog) {
  try {
    localStorage.setItem(CACHE_KEY, JSON.stringify(c));
  } catch {
    /* sin almacenamiento: se vuelve a pedir en la proxima sesion */
  }
}

export function resetCatalog() {
  current = null;
  try {
    localStorage.removeItem(CACHE_KEY);
  } catch {
    /* nada que borrar */
  }
}

export function CatalogGate({ children }: { children: React.ReactNode }) {
  const [ready, setReady] = useState(current !== null);
  useEffect(() => {
    if (current) return;
    let alive = true;
    getUiCatalog()
      .then((c) => { current = c; writeCache(c); })
      .catch(() => { current = readCache(); })
      .finally(() => { if (alive) setReady(true); });
    return () => { alive = false; };
  }, []);
  if (!ready) return <p className="p-6 text-sm text-slate-500">Cargando…</p>;
  return <>{children}</>;
}

/** Vuelve a leer el catalogo (tras cambiar region o terminologia). */
export async function reloadCatalog() {
  const c = await getUiCatalog();
  current = c;
  writeCache(c);
  return c;
}

export function catalog(): UiCatalog | null {
  return current;
}

// ── Etiquetas de codigos ──────────────────────────────────────────────

export function label(domain: string, code: string | null | undefined): string {
  if (code === null || code === undefined) return "—";
  return current?.labels[domain]?.[code]?.label ?? code;
}

export function options(domain: string): { code: string; label: string }[] {
  const d = current?.labels[domain] ?? {};
  return Object.entries(d).sort((a, b) => a[1].sort - b[1].sort).map(([code, v]) => ({ code, label: v.label }));
}

export type Tone = "success" | "warning" | "danger" | "info" | "neutral";

// El estilo de cada tono es de la interfaz; el tono de cada estado es dato.
const BADGE: Record<Tone, string> = {
  success: "bg-emerald-50 text-emerald-700",
  warning: "bg-amber-50 text-amber-800",
  danger: "bg-red-50 text-red-700",
  info: "bg-indigo-50 text-indigo-700",
  neutral: "bg-slate-100 text-slate-600",
};
const TEXT: Record<Tone, string> = {
  success: "text-emerald-700", warning: "text-amber-700", danger: "text-red-700", info: "text-indigo-700", neutral: "text-slate-600",
};
const DOT: Record<Tone, string> = {
  success: "bg-emerald-500", warning: "bg-amber-500", danger: "bg-red-500", info: "bg-indigo-500", neutral: "bg-slate-400",
};

// Para mapas y graficos (colores en hex, no clases).
const HEX: Record<Tone, string> = {
  success: "#10b981", warning: "#f59e0b", danger: "#ef4444", info: "#6366f1", neutral: "#94a3b8",
};

export function toneHex(domain: string, code: string | null | undefined) {
  return HEX[tone(domain, code)];
}

export function tone(domain: string, code: string | null | undefined): Tone {
  return ((code && current?.labels[domain]?.[code]?.tone) as Tone | null) ?? "neutral";
}

export function badgeClass(domain: string, code: string | null | undefined) {
  return BADGE[tone(domain, code)];
}

export function textClass(domain: string, code: string | null | undefined) {
  return TEXT[tone(domain, code)];
}

export function dotClass(domain: string, code: string | null | undefined) {
  return DOT[tone(domain, code)];
}

// ── Terminologia y formatos del paquete ───────────────────────────────

export function term(key: string, opts: { plural?: boolean; capital?: boolean } = {}): string {
  const t = current?.terms[key];
  let s = t ? (opts.plural ? t.plural : t.label) : key;
  if (opts.capital && s) s = s.charAt(0).toUpperCase() + s.slice(1);
  return s;
}

/** Formato que el paquete adoptado declara para un registro, o null. */
export function form(domain: string): { code: string; title: string; stage_code: string | null; template_id: string | null } | null {
  return current?.forms[domain] ?? null;
}

/** Donde se aplica la lista de un formato (etapa de la ruta), o null. */
export function formLink(domain: string): string | null {
  const f = form(domain);
  return f?.stage_code ? `/inspections/${f.stage_code}` : null;
}

/** Codigo con que el paquete adoptado conoce un registro ("7G.2"), o null. */
export function formCode(domain: string): string | null {
  return current?.forms[domain]?.code ?? null;
}

/** " (7G.2)" si el paquete declara el formato; "" si no. */
export function formSuffix(domain: string): string {
  const c = formCode(domain);
  return c ? ` (${c})` : "";
}

// ── Numeros, moneda y fechas con la region de la organizacion ─────────

function localeCode(): string | undefined {
  return current?.locale?.code ?? undefined;
}

/** Region de la organizacion para Intl; sin configurar, la del navegador. */
export function appLocale(): string | undefined {
  return localeCode();
}

export function num(v: number | null | undefined, maxDecimals = 2): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  return v.toLocaleString(localeCode(), { maximumFractionDigits: maxDecimals });
}

export function pct(v: number | null | undefined): string {
  return v === null || v === undefined ? "—" : `${num(v, 1)} %`;
}

/** Monto en la moneda de la organizacion; sin moneda configurada, el numero solo. */
export function money(v: number | null | undefined): string {
  if (v === null || v === undefined) return "—";
  const c = current?.currency;
  if (!c) return num(v);
  return v.toLocaleString(localeCode(), { style: "currency", currency: c.code, minimumFractionDigits: c.decimals, maximumFractionDigits: c.decimals });
}

export function currencyCode(): string | null {
  return current?.currency?.code ?? null;
}

export function date(v: string | Date | null | undefined): string {
  if (!v) return "—";
  const d = typeof v === "string" && /^\d{4}-\d{2}-\d{2}$/.test(v) ? new Date(`${v}T00:00`) : new Date(v);
  return d.toLocaleDateString(localeCode());
}

export function dateTime(v: string | Date | null | undefined): string {
  if (!v) return "—";
  return new Date(v).toLocaleString(localeCode());
}

export function time(v: string | Date | null | undefined, opts: Intl.DateTimeFormatOptions = { hour: "2-digit", minute: "2-digit" }): string {
  if (!v) return "—";
  return new Date(v).toLocaleTimeString(localeCode(), opts);
}

/** AAAA-MM-DD en la hora local (para campos de fecha), sin depender de una region. */
export function isoDay(d: Date = new Date()): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}
