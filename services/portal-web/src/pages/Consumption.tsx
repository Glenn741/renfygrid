import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ApiError,
  getConsumptionOrders,
  getConsumptionSummary,
  getConsumptionUnderReview,
  resolveConsumptionAnomaly,
  type Consumption,
} from "../api";
import { StagePage, EmptyState } from "../components/StagePage";

// Gestion de Consumos (Sprint C11-6, benchmark real: docs/05-ejecucion.md
// -- Bynry: "MDMS reporting and analytics covers... billing validation
// reports, usage exception reports... non-revenue loss analysis"). F21-F24
// ya estaban completos; el panel solo mostraba la cola "under_review", sin
// resumen, sin las ordenes de relectura/inspeccion (F23) visibles, y sin
// forma de cerrar una anomalia investigada.

const ACTION_LABEL: Record<string, string> = {
  reread_order: "Orden de relectura",
  inspection_order: "Orden de inspección",
};

function actionLabel(action: string): string {
  return ACTION_LABEL[action] ?? action;
}

function periodFromRangeText(period: string): { start: string; end: string } {
  // "[2026-08-01,2026-09-01)" -> extraer las dos fechas para el POST de resolucion.
  const match = period.match(/(\d{4}-\d{2}-\d{2}).*?(\d{4}-\d{2}-\d{2})/);
  return { start: match?.[1] ?? "", end: match?.[2] ?? "" };
}

function ResolveRow({ row }: { row: Consumption }) {
  const queryClient = useQueryClient();
  const [resolving, setResolving] = useState(false);
  const [notes, setNotes] = useState("");
  const [error, setError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: () => {
      const { start, end } = periodFromRangeText(row.period);
      return resolveConsumptionAnomaly({ meter_id: row.meter_id, period_start: start, period_end: end, notes });
    },
    onSuccess: () => {
      setError(null);
      setResolving(false);
      queryClient.invalidateQueries({ queryKey: ["consumption-under-review"] });
      queryClient.invalidateQueries({ queryKey: ["consumption-summary"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard-overview"] });
    },
    onError: (err) => setError(err instanceof ApiError ? err.message : "No se pudo resolver la anomalía."),
  });

  return (
    <>
      <tr>
        <td className="px-4 py-3 font-medium text-slate-900">{row.account_number}</td>
        <td className="px-4 py-3 text-slate-600">{row.period}</td>
        <td className="px-4 py-3 tabular-nums">{row.value}</td>
        <td className="px-4 py-3 text-amber-700">En revisión</td>
        <td className="px-4 py-3">
          <button onClick={() => setResolving((v) => !v)} className="text-xs text-indigo-600 hover:text-indigo-700">
            {resolving ? "Cancelar" : "Resolver"}
          </button>
        </td>
      </tr>
      {resolving && (
        <tr className="bg-slate-50">
          <td colSpan={5} className="px-4 py-3">
            <div className="flex flex-wrap items-end gap-3">
              <div className="flex-1 min-w-[240px]">
                <label className="block text-xs font-medium text-slate-500 mb-1">Notas de la investigación</label>
                <input
                  className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm w-full"
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  placeholder="qué se encontró al investigar"
                />
              </div>
              <button
                onClick={() => mutation.mutate()}
                disabled={!notes || mutation.isPending}
                className="rounded-lg bg-indigo-600 text-white text-xs font-semibold px-3 py-1.5 hover:bg-indigo-700 disabled:opacity-40"
              >
                Confirmar resolución
              </button>
            </div>
            {error && <p className="text-sm text-red-600 mt-2">{error}</p>}
          </td>
        </tr>
      )}
    </>
  );
}

export function ConsumptionPage() {
  const { data: summary } = useQuery({
    queryKey: ["consumption-summary"],
    queryFn: getConsumptionSummary,
    refetchInterval: 30_000,
  });

  const { data, isLoading } = useQuery({
    queryKey: ["consumption-under-review"],
    queryFn: getConsumptionUnderReview,
    refetchInterval: 30_000,
  });

  const { data: orders, isLoading: ordersLoading } = useQuery({
    queryKey: ["consumption-orders"],
    queryFn: getConsumptionOrders,
    refetchInterval: 30_000,
  });

  return (
    <StagePage title="Consumos">
      {summary && (
        <div className="mb-6 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="rounded-xl border border-slate-200 bg-white p-4">
            <div className={`text-2xl font-bold ${(summary.anomaly_rate_pct ?? 0) > 5 ? "text-red-700" : "text-slate-900"}`}>
              {summary.anomaly_rate_pct === null ? "—" : `${summary.anomaly_rate_pct}%`}
            </div>
            <div className="text-xs text-slate-500 mt-1">Tasa de anomalía</div>
          </div>
          <div className="rounded-xl border border-slate-200 bg-white p-4">
            <div className="text-2xl font-bold text-emerald-700">
              {summary.billing_ready_pct === null ? "—" : `${summary.billing_ready_pct}%`}
            </div>
            <div className="text-xs text-slate-500 mt-1">Listo para facturar</div>
          </div>
          <div className="rounded-xl border border-slate-200 bg-white p-4">
            <div className="text-2xl font-bold text-slate-900">{summary.total_processed}</div>
            <div className="text-xs text-slate-500 mt-1">Consumos procesados</div>
          </div>
          <div className="rounded-xl border border-slate-200 bg-white p-4">
            <div className="text-xs font-medium text-slate-500 mb-2">Órdenes generadas</div>
            {Object.keys(summary.orders_by_action).length === 0 ? (
              <div className="text-sm text-slate-400">Ninguna todavía</div>
            ) : (
              <div className="flex flex-wrap gap-1.5">
                {Object.entries(summary.orders_by_action).map(([action, count]) => (
                  <span key={action} className="rounded-full bg-amber-50 px-2 py-0.5 text-xs font-semibold text-amber-700">
                    {actionLabel(action)}: {count}
                  </span>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      <h2 className="text-sm font-semibold text-slate-500 uppercase tracking-wide mb-2">
        En revisión
      </h2>
      {isLoading && <p className="text-sm text-slate-500 mb-8">Cargando...</p>}
      {data && data.length === 0 && (
        <div className="mb-8">
          <EmptyState message="Sin consumos en revisión. Nada retenido de facturación." />
        </div>
      )}
      {data && data.length > 0 && (
        <div className="mb-8 overflow-x-auto rounded-xl border border-amber-200 bg-white">
          <table className="w-full text-sm">
            <thead className="bg-amber-50 text-left text-xs uppercase tracking-wide text-amber-700">
              <tr>
                <th className="px-4 py-3">Cuenta</th>
                <th className="px-4 py-3">Periodo</th>
                <th className="px-4 py-3">Consumo</th>
                <th className="px-4 py-3">Estado</th>
                <th className="px-4 py-3"></th>
              </tr>
            </thead>
            <tbody>
              {data.map((row) => (
                <ResolveRow key={`${row.meter_id}-${row.period}`} row={row} />
              ))}
            </tbody>
          </table>
        </div>
      )}

      <h2 className="text-sm font-semibold text-slate-500 uppercase tracking-wide mb-2">
        Órdenes de relectura / inspección
      </h2>
      {ordersLoading && <p className="text-sm text-slate-500">Cargando...</p>}
      {orders && orders.length === 0 && <EmptyState message="Sin órdenes generadas todavía." />}
      {orders && orders.length > 0 && (
        <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-4 py-3">Cuenta</th>
                <th className="px-4 py-3">Orden</th>
                <th className="px-4 py-3">Periodo</th>
                <th className="px-4 py-3">Consumo</th>
                <th className="px-4 py-3">Estado actual</th>
                <th className="px-4 py-3">Generada</th>
              </tr>
            </thead>
            <tbody>
              {orders.map((row, i) => (
                <tr key={`${row.meter_id}-${row.timestamp}-${i}`}>
                  <td className="px-4 py-3 font-medium text-slate-900">{row.account_number}</td>
                  <td className="px-4 py-3">
                    <span className="rounded-full bg-amber-50 px-2 py-0.5 text-xs font-semibold text-amber-700">
                      {actionLabel(row.action)}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-slate-600">{row.period}</td>
                  <td className="px-4 py-3 tabular-nums">{row.value}</td>
                  <td className="px-4 py-3 text-slate-600">{row.anomaly_status}</td>
                  <td className="px-4 py-3 text-slate-500">{new Date(row.timestamp).toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </StagePage>
  );
}
