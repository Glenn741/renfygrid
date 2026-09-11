import { Link } from "react-router-dom";

interface KpiTileProps {
  label: string;
  value: number;
  alert?: boolean;
  hint?: string;
  to: string;
}

// Patron "exception-first" (docs/02-arquitectura-general.md SS9): un tile
// normal es neutro -- solo se resalta cuando hay algo que atender. Cada
// tile es un link a su pantalla de Nivel 2 (Nivel 1 -> Nivel 2).
export function KpiTile({ label, value, alert = false, hint, to }: KpiTileProps) {
  return (
    <Link
      to={to}
      className={`rounded-xl border p-4 flex flex-col gap-1 transition-shadow hover:shadow-md ${
        alert ? "border-amber-300 bg-amber-50" : "border-slate-200 bg-white"
      }`}
    >
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium uppercase tracking-wide text-slate-500">
          {label}
        </span>
        {alert && (
          <span className="text-amber-600" aria-label="atención requerida" title="Atención requerida">
            ⚠
          </span>
        )}
      </div>
      <span className={`text-3xl font-bold tabular-nums ${alert ? "text-amber-700" : "text-slate-900"}`}>
        {value}
      </span>
      {hint && <span className="text-xs text-slate-500">{hint}</span>}
    </Link>
  );
}
