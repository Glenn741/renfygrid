import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ApiError,
  editReading,
  getEstimatedReadings,
  getInvalidReadings,
  getVeeEdits,
  getVeeSummary,
  type InvalidReading,
} from "../api";
import { StagePage, EmptyState } from "../components/StagePage";

// Validacion (VEE), por etapa -- Sprint C11-3, sobre el feedback directo
// del usuario: "cada letra V.E.E. implica un nivel de procesamiento y
// deberian haber estadisticas y KPIs en esos niveles... la pantalla de
// usuario no dice mucho". Grounded en como lo hacen los MDM de
// referencia (docs/05-ejecucion.md, Sprint C11-3): Oracle Utilities MDM
// separa un dashboard "VEE Exceptions" (Overview/Trend) con tasa de
// excepcion en bandas verde/amarillo/rojo; Itron Enterprise Edition
// distingue "validation sets" de "estimation sets"; Landis+Gyr Core MDMS
// tiene "exception management" como pieza aparte de edicion manual. Por
// eso esta pantalla son 3 secciones -- Validacion / Estimacion / Edicion
// manual -- cada una con sus propios KPIs, no una tabla generica.

const RULE_TYPE_LABEL: Record<string, string> = {
  range: "Rango",
  channel_consistency: "Coherencia entre canales",
  missing_interval: "Intervalo faltante",
  sin_regla_o_formato: "Sin regla / formato",
};

function ruleTypeLabel(type: string | null): string {
  return RULE_TYPE_LABEL[type ?? "sin_regla_o_formato"] ?? type ?? "Sin regla / formato";
}

const METHOD_LABEL: Record<string, string> = {
  linear_interpolation: "Interpolación lineal",
  customer_historical_average: "Promedio histórico del medidor",
  similar_customers_average: "Promedio de medidores similares",
  desconocido: "Método desconocido",
};

function methodLabel(method: string | null): string {
  return METHOD_LABEL[method ?? "desconocido"] ?? method ?? "Método desconocido";
}

type TypeFilter = "todas" | "range" | "channel_consistency" | "missing_interval" | "sin_regla_o_formato";

// Banda de calidad de datos (tasa de excepcion): <2% excelente, 2-5%
// aceptable, >5% preocupante -- benchmark generico de calidad de datos,
// ver docs/05-ejecucion.md Sprint C11-3 (sin uno propio del sector medido
// todavia, se usa el generico en vez de inventar un umbral sin fuente).
function exceptionRateColor(pct: number | null): string {
  if (pct === null) return "text-slate-900";
  if (pct < 2) return "text-emerald-700";
  if (pct <= 5) return "text-amber-700";
  return "text-red-700";
}

function KpiCard({ value, label, colorClass }: { value: string | number; label: string; colorClass?: string }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4">
      <div className={`text-2xl font-bold ${colorClass ?? "text-slate-900"}`}>{value}</div>
      <div className="text-xs text-slate-500 mt-1">{label}</div>
    </div>
  );
}

function SectionHeader({ step, title, subtitle }: { step: string; title: string; subtitle: string }) {
  return (
    <div className="mb-3 flex items-baseline gap-2">
      <span className="flex h-6 w-6 items-center justify-center rounded-full bg-indigo-600 text-white text-xs font-bold shrink-0">
        {step}
      </span>
      <h2 className="text-sm font-bold text-slate-900">{title}</h2>
      <span className="text-xs text-slate-400">— {subtitle}</span>
    </div>
  );
}

function EditReadingRow({ reading }: { reading: InvalidReading }) {
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState(false);
  const [newValue, setNewValue] = useState(String(reading.value));
  const [userName, setUserName] = useState("");
  const [justification, setJustification] = useState("");
  const [error, setError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: () =>
      editReading({
        meter_id: reading.meter_id,
        channel: reading.channel,
        timestamp: reading.timestamp,
        new_value: Number(newValue),
        user_name: userName,
        justification,
      }),
    onSuccess: () => {
      setError(null);
      setEditing(false);
      queryClient.invalidateQueries({ queryKey: ["invalid-readings"] });
      queryClient.invalidateQueries({ queryKey: ["vee-summary"] });
      queryClient.invalidateQueries({ queryKey: ["vee-edits"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard-overview"] });
    },
    onError: (err) => setError(err instanceof ApiError ? err.message : "No se pudo editar la lectura."),
  });

  return (
    <>
      <tr>
        <td className="px-4 py-3 font-medium text-slate-900">{reading.account_number}</td>
        <td className="px-4 py-3 text-slate-600">{reading.channel}</td>
        <td className="px-4 py-3">
          <span className="rounded-full bg-amber-50 px-2 py-0.5 text-xs font-semibold text-amber-700">
            {ruleTypeLabel(reading.rule_type)}
          </span>
        </td>
        <td className="px-4 py-3 text-slate-600">{new Date(reading.timestamp).toLocaleString()}</td>
        <td className="px-4 py-3 tabular-nums">{reading.value}</td>
        <td className="px-4 py-3 text-amber-700">{reading.validation_notes ?? "—"}</td>
        <td className="px-4 py-3">
          <button onClick={() => setEditing((v) => !v)} className="text-xs text-indigo-600 hover:text-indigo-700">
            {editing ? "Cancelar" : "Editar"}
          </button>
        </td>
      </tr>
      {editing && (
        <tr className="bg-slate-50">
          <td colSpan={7} className="px-4 py-3">
            <div className="flex flex-wrap items-end gap-3">
              <div>
                <label className="block text-xs font-medium text-slate-500 mb-1">Valor corregido</label>
                <input className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm w-28" value={newValue} onChange={(e) => setNewValue(e.target.value)} />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-500 mb-1">Quién edita</label>
                <input className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm" value={userName} onChange={(e) => setUserName(e.target.value)} placeholder="nombre@empresa.com" />
              </div>
              <div className="flex-1 min-w-[200px]">
                <label className="block text-xs font-medium text-slate-500 mb-1">Justificación</label>
                <input className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm w-full" value={justification} onChange={(e) => setJustification(e.target.value)} placeholder="por qué se corrige" />
              </div>
              <button
                onClick={() => mutation.mutate()}
                disabled={!userName || !justification || mutation.isPending}
                className="rounded-lg bg-indigo-600 text-white text-xs font-semibold px-3 py-1.5 hover:bg-indigo-700 disabled:opacity-40"
              >
                Guardar
              </button>
            </div>
            {error && <p className="text-sm text-red-600 mt-2">{error}</p>}
          </td>
        </tr>
      )}
    </>
  );
}

function TrendBars({ trend }: { trend: { date: string; total: number; invalid: number }[] }) {
  const max = Math.max(1, ...trend.map((d) => d.total));
  return (
    <div className="flex items-end gap-2 h-20">
      {trend.map((d) => (
        <div key={d.date} className="flex-1 flex flex-col items-center gap-1" title={`${d.date}: ${d.invalid}/${d.total} inválidas`}>
          <div className="w-full flex flex-col justify-end h-14 rounded bg-slate-100 overflow-hidden">
            <div className="w-full bg-red-400" style={{ height: `${(d.invalid / max) * 100}%` }} />
            <div className="w-full bg-emerald-300" style={{ height: `${((d.total - d.invalid) / max) * 100}%` }} />
          </div>
          <span className="text-[10px] text-slate-400">{d.date.slice(5)}</span>
        </div>
      ))}
    </div>
  );
}

export function VeePage() {
  const { data: summary } = useQuery({
    queryKey: ["vee-summary"],
    queryFn: getVeeSummary,
    refetchInterval: 30_000,
  });

  const { data, isLoading } = useQuery({
    queryKey: ["invalid-readings"],
    queryFn: getInvalidReadings,
    refetchInterval: 30_000,
  });

  const { data: estimated, isLoading: estimatedLoading } = useQuery({
    queryKey: ["estimated-readings"],
    queryFn: getEstimatedReadings,
    refetchInterval: 30_000,
  });

  const { data: edits, isLoading: editsLoading } = useQuery({
    queryKey: ["vee-edits"],
    queryFn: getVeeEdits,
    refetchInterval: 30_000,
  });

  const [typeFilter, setTypeFilter] = useState<TypeFilter>("todas");

  const rows = useMemo(() => {
    if (!data) return [];
    if (typeFilter === "todas") return data;
    return data.filter((row) => (row.rule_type ?? "sin_regla_o_formato") === typeFilter);
  }, [data, typeFilter]);

  const typesPresent = useMemo(() => {
    if (!summary) return [];
    return (Object.keys(summary.validation.invalid_by_type) as TypeFilter[]).filter(
      (t) => summary.validation.invalid_by_type[t] > 0
    );
  }, [summary]);

  return (
    <StagePage title="Validación (VEE)">
      {/* Etapa 1: Validacion (F14/F15) */}
      <SectionHeader step="V" title="Validación" subtitle="rango, formato y coherencia entre canales" />
      {summary && (
        <div className="mb-3 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <KpiCard
            value={summary.validation.exception_rate_pct === null ? "—" : `${summary.validation.exception_rate_pct}%`}
            label="Tasa de excepción (histórica)"
            colorClass={exceptionRateColor(summary.validation.exception_rate_pct)}
          />
          <KpiCard value={summary.validation.total_processed} label="Lecturas reales procesadas" />
          <KpiCard value={summary.validation.invalid_total} label="Excepciones pendientes" colorClass={summary.validation.invalid_total > 0 ? "text-amber-700" : undefined} />
          <KpiCard value={summary.validation.active_rules_total} label="Reglas de validación activas" />
        </div>
      )}
      {summary && summary.validation.trend_7d.length > 0 && (
        <div className="mb-4 rounded-xl border border-slate-200 bg-white p-4">
          <div className="text-xs font-medium text-slate-500 mb-2">Últimos 7 días — verde: válidas, rojo: excepciones</div>
          <TrendBars trend={summary.validation.trend_7d} />
        </div>
      )}

      {typesPresent.length > 1 && (
        <div className="mb-3 flex gap-2">
          {(["todas", ...typesPresent] as TypeFilter[]).map((t) => (
            <button
              key={t}
              onClick={() => setTypeFilter(t)}
              className={`rounded-full px-3 py-1 text-xs font-semibold border ${
                typeFilter === t
                  ? "bg-indigo-600 text-white border-indigo-600"
                  : "bg-white text-slate-600 border-slate-200 hover:border-slate-300"
              }`}
            >
              {t === "todas" ? "Todas" : ruleTypeLabel(t)}
            </button>
          ))}
        </div>
      )}

      {isLoading && <p className="text-sm text-slate-500 mb-6">Cargando...</p>}
      {data && data.length === 0 && (
        <div className="mb-8">
          <EmptyState message="Sin lecturas inválidas pendientes. 👍" />
        </div>
      )}
      {rows.length === 0 && data && data.length > 0 && (
        <div className="mb-8">
          <EmptyState message="Sin lecturas de este tipo con el filtro actual." />
        </div>
      )}
      {rows.length > 0 && (
        <div className="mb-8 overflow-x-auto rounded-xl border border-amber-200 bg-white">
          <table className="w-full text-sm">
            <thead className="bg-amber-50 text-left text-xs uppercase tracking-wide text-amber-700">
              <tr>
                <th className="px-4 py-3">Cuenta</th>
                <th className="px-4 py-3">Canal</th>
                <th className="px-4 py-3">Tipo</th>
                <th className="px-4 py-3">Timestamp</th>
                <th className="px-4 py-3">Valor</th>
                <th className="px-4 py-3">Motivo</th>
                <th className="px-4 py-3"></th>
              </tr>
            </thead>
            <tbody>
              {rows.map((reading, i) => (
                <EditReadingRow key={`${reading.meter_id}-${reading.channel}-${reading.timestamp}-${i}`} reading={reading} />
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Etapa 2: Estimacion (F16/F17) */}
      <SectionHeader step="E" title="Estimación" subtitle="huecos detectados y rellenados automáticamente" />
      {summary && (
        <div className="mb-3 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <KpiCard
            value={summary.estimation.fill_rate_pct === null ? "—" : `${summary.estimation.fill_rate_pct}%`}
            label="% de la serie que fue estimada"
          />
          <KpiCard value={summary.estimation.total_estimated} label="Total lecturas estimadas" />
          <KpiCard value={summary.estimation.estimated_24h} label="Estimadas en 24h" colorClass="text-emerald-700" />
          <KpiCard value={summary.estimation.active_rules_total} label="Reglas de intervalo activas" />
        </div>
      )}
      {summary && Object.keys(summary.estimation.by_method).length > 0 && (
        <div className="mb-4 flex flex-wrap gap-2">
          {Object.entries(summary.estimation.by_method).map(([method, count]) => (
            <span key={method} className="rounded-full bg-emerald-50 px-3 py-1 text-xs font-semibold text-emerald-700">
              {methodLabel(method)}: {count}
            </span>
          ))}
        </div>
      )}
      {estimatedLoading && <p className="text-sm text-slate-500 mb-8">Cargando...</p>}
      {estimated && estimated.length === 0 && (
        <div className="mb-8">
          <EmptyState message="Sin huecos estimados todavía." />
        </div>
      )}
      {estimated && estimated.length > 0 && (
        <div className="mb-8 overflow-x-auto rounded-xl border border-slate-200 bg-white">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-4 py-3">Cuenta</th>
                <th className="px-4 py-3">Canal</th>
                <th className="px-4 py-3">Instante estimado</th>
                <th className="px-4 py-3">Valor</th>
                <th className="px-4 py-3">Método</th>
                <th className="px-4 py-3">Generada</th>
              </tr>
            </thead>
            <tbody>
              {estimated.map((row, i) => (
                <tr key={`${row.meter_id}-${row.channel}-${row.timestamp}-${i}`}>
                  <td className="px-4 py-3 font-medium text-slate-900">{row.account_number}</td>
                  <td className="px-4 py-3 text-slate-600">{row.channel}</td>
                  <td className="px-4 py-3 text-slate-600">{new Date(row.timestamp).toLocaleString()}</td>
                  <td className="px-4 py-3 tabular-nums">{row.value}</td>
                  <td className="px-4 py-3">
                    <span className="rounded-full bg-emerald-50 px-2 py-0.5 text-xs font-semibold text-emerald-700">
                      {methodLabel(row.estimation_method)}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-slate-500">{new Date(row.created_at).toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Etapa 3: Edicion manual (F18) */}
      <SectionHeader step="E" title="Edición manual" subtitle="correcciones auditadas, nunca sobre-escritas" />
      {summary && (
        <div className="mb-3 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <KpiCard value={summary.editing.total_edits} label="Total de ediciones" />
          <KpiCard value={summary.editing.edits_24h} label="Ediciones en 24h" colorClass="text-indigo-700" />
          <div className="rounded-xl border border-slate-200 bg-white p-4 sm:col-span-2">
            <div className="text-xs font-medium text-slate-500 mb-2">Quién edita más</div>
            {summary.editing.top_editors.length === 0 ? (
              <div className="text-sm text-slate-400">Sin ediciones todavía.</div>
            ) : (
              <div className="flex flex-wrap gap-2">
                {summary.editing.top_editors.map((row) => (
                  <span key={row.user_name} className="rounded-full bg-indigo-50 px-3 py-1 text-xs font-semibold text-indigo-700">
                    {row.user_name}: {row.count}
                  </span>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
      {editsLoading && <p className="text-sm text-slate-500">Cargando...</p>}
      {edits && edits.length === 0 && <EmptyState message="Sin ediciones manuales todavía." />}
      {edits && edits.length > 0 && (
        <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-4 py-3">Cuenta</th>
                <th className="px-4 py-3">Canal</th>
                <th className="px-4 py-3">Instante de la lectura</th>
                <th className="px-4 py-3">Valor anterior</th>
                <th className="px-4 py-3">Valor nuevo</th>
                <th className="px-4 py-3">Quién</th>
                <th className="px-4 py-3">Justificación</th>
                <th className="px-4 py-3">Cuándo</th>
              </tr>
            </thead>
            <tbody>
              {edits.map((row, i) => (
                <tr key={`${row.meter_id}-${row.channel}-${row.timestamp}-${i}`}>
                  <td className="px-4 py-3 font-medium text-slate-900">{row.account_number}</td>
                  <td className="px-4 py-3 text-slate-600">{row.channel}</td>
                  <td className="px-4 py-3 text-slate-600">{new Date(row.timestamp).toLocaleString()}</td>
                  <td className="px-4 py-3 tabular-nums text-slate-400 line-through">{row.previous_value}</td>
                  <td className="px-4 py-3 tabular-nums font-semibold">{row.new_value}</td>
                  <td className="px-4 py-3 text-slate-600">{row.user_name}</td>
                  <td className="px-4 py-3 text-slate-600">{row.justification}</td>
                  <td className="px-4 py-3 text-slate-500">{new Date(row.edited_at).toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </StagePage>
  );
}
