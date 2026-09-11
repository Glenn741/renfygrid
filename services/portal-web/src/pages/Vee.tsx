import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ApiError,
  editReading,
  getEstimatedReadings,
  getInvalidReadings,
  getVeeSummary,
  type InvalidReading,
} from "../api";
import { StagePage, EmptyState } from "../components/StagePage";

// Validacion (VEE) -- Sprint C11-2, sobre el gap real que dejo el
// benchmark: F14-F19 (validacion, huecos, estimacion, edicion, coherencia
// entre canales) ya estaban construidos y verificados de punta a punta
// desde Sprint 3-4/C11, pero esta pantalla solo mostraba la cola de
// excepciones invalidas -- sin resumen, sin las lecturas ESTIMADAS
// visibles (el trabajo mas real del motor), y sin distinguir un rango
// fuera de límite de una coherencia entre canales rota.

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
};

type TypeFilter = "todas" | "range" | "channel_consistency" | "missing_interval" | "sin_regla_o_formato";

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

  const [typeFilter, setTypeFilter] = useState<TypeFilter>("todas");

  const rows = useMemo(() => {
    if (!data) return [];
    if (typeFilter === "todas") return data;
    return data.filter((row) => (row.rule_type ?? "sin_regla_o_formato") === typeFilter);
  }, [data, typeFilter]);

  const typesPresent = useMemo(() => {
    if (!summary) return [];
    return (Object.keys(summary.invalid_by_type) as TypeFilter[]).filter((t) => summary.invalid_by_type[t] > 0);
  }, [summary]);

  return (
    <StagePage title="Validación (VEE)">
      {summary && (
        <div className="mb-4 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="rounded-xl border border-slate-200 bg-white p-4">
            <div className={`text-2xl font-bold ${summary.invalid_pending > 0 ? "text-amber-700" : "text-slate-900"}`}>
              {summary.invalid_pending}
            </div>
            <div className="text-xs text-slate-500 mt-1">Lecturas inválidas pendientes</div>
          </div>
          <div className="rounded-xl border border-slate-200 bg-white p-4">
            <div className="text-2xl font-bold text-emerald-700">{summary.estimated_24h}</div>
            <div className="text-xs text-slate-500 mt-1">Estimadas en las últimas 24h</div>
          </div>
          <div className="rounded-xl border border-slate-200 bg-white p-4">
            <div className="text-2xl font-bold text-indigo-700">{summary.edited_24h}</div>
            <div className="text-xs text-slate-500 mt-1">Editadas manualmente en 24h</div>
          </div>
          <div className="rounded-xl border border-slate-200 bg-white p-4">
            <div className="text-2xl font-bold text-slate-900">{summary.active_rules_total}</div>
            <div className="text-xs text-slate-500 mt-1">Reglas VEE activas</div>
          </div>
        </div>
      )}

      <h2 className="text-sm font-semibold text-slate-500 uppercase tracking-wide mb-2">
        Cola de excepciones
      </h2>
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
        <div className="mb-6">
          <EmptyState message="Sin lecturas inválidas pendientes. 👍" />
        </div>
      )}
      {rows.length === 0 && data && data.length > 0 && (
        <div className="mb-6">
          <EmptyState message="Sin lecturas de este tipo con el filtro actual." />
        </div>
      )}
      {rows.length > 0 && (
        <div className="mb-6 overflow-x-auto rounded-xl border border-amber-200 bg-white">
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

      <h2 className="text-sm font-semibold text-slate-500 uppercase tracking-wide mb-2">
        Lecturas estimadas (huecos llenados automáticamente)
      </h2>
      {estimatedLoading && <p className="text-sm text-slate-500">Cargando...</p>}
      {estimated && estimated.length === 0 && (
        <EmptyState message="Sin huecos estimados todavía." />
      )}
      {estimated && estimated.length > 0 && (
        <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white">
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
                      {row.estimation_method ? METHOD_LABEL[row.estimation_method] ?? row.estimation_method : "—"}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-slate-500">{new Date(row.created_at).toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </StagePage>
  );
}
