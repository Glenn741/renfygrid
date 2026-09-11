import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiError, approveControlOrder, getControlOrders, getControlSummary, type ControlOrder } from "../api";
import { StagePage, EmptyState } from "../components/StagePage";

// Control (SCR) -- Sprint C11-5, benchmark real (docs/05-ejecucion.md):
// "utilities can configure KPI tracking... percentage of successful
// reads, command success rates, or retry backlog" (Grid/EPRI). Antes solo
// existia la cola de `pending_approval`, sin historial ni tasa de exito de
// comando -- y ninguna cuenta protegida contra suspension/desconexion
// (Ley 142 + normas CRA/CREG en Colombia, Resolucion CREG 108/1997).

const TYPE_LABEL: Record<string, string> = {
  suspension: "Suspensión",
  reconnection: "Reconexión",
  disconnection: "Desconexión",
};

const STATUS_LABEL: Record<string, string> = {
  requested: "Solicitada",
  pending_approval: "Pendiente de aprobación",
  approved: "Aprobada",
  sent: "Enviada",
  confirmed: "Confirmada",
  failed: "Fallida",
};

const STATUS_CLASS: Record<string, string> = {
  pending_approval: "bg-amber-50 text-amber-700",
  confirmed: "bg-emerald-50 text-emerald-700",
  failed: "bg-red-50 text-red-600",
  approved: "bg-indigo-50 text-indigo-700",
  sent: "bg-indigo-50 text-indigo-700",
  requested: "bg-slate-50 text-slate-500",
};

type StatusFilter = "pending_approval" | "todas";

export function ControlPage() {
  const queryClient = useQueryClient();

  const { data: summary } = useQuery({
    queryKey: ["control-summary"],
    queryFn: getControlSummary,
    refetchInterval: 30_000,
  });

  const [statusFilter, setStatusFilter] = useState<StatusFilter>("pending_approval");
  const { data, isLoading } = useQuery({
    queryKey: ["control-orders", statusFilter],
    queryFn: () => getControlOrders(statusFilter === "pending_approval" ? "pending_approval" : undefined),
    refetchInterval: 30_000,
  });

  const [error, setError] = useState<string | null>(null);

  const approveMutation = useMutation({
    mutationFn: (orderId: string) => approveControlOrder(orderId),
    onSuccess: () => {
      setError(null);
      queryClient.invalidateQueries({ queryKey: ["control-orders"] });
      queryClient.invalidateQueries({ queryKey: ["control-summary"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard-overview"] });
    },
    onError: (err) => setError(err instanceof ApiError ? err.message : "No se pudo aprobar la orden."),
  });

  const typeChips = useMemo(() => (summary ? Object.entries(summary.by_type) : []), [summary]);

  return (
    <StagePage title="Control (SCR)">
      {summary && (
        <div className="mb-4 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="rounded-xl border border-slate-200 bg-white p-4">
            <div className={`text-2xl font-bold ${summary.command_success_rate_pct !== null && summary.command_success_rate_pct < 80 ? "text-red-700" : "text-emerald-700"}`}>
              {summary.command_success_rate_pct === null ? "—" : `${summary.command_success_rate_pct}%`}
            </div>
            <div className="text-xs text-slate-500 mt-1">Tasa de éxito de comando</div>
          </div>
          <div className="rounded-xl border border-slate-200 bg-white p-4">
            <div className={`text-2xl font-bold ${summary.pending_approval > 0 ? "text-amber-700" : "text-slate-900"}`}>
              {summary.pending_approval}
            </div>
            <div className="text-xs text-slate-500 mt-1">Pendientes de aprobación</div>
          </div>
          <div className="rounded-xl border border-slate-200 bg-white p-4">
            <div className="text-2xl font-bold text-slate-900">{summary.total_orders}</div>
            <div className="text-xs text-slate-500 mt-1">Órdenes totales</div>
          </div>
          <div className="rounded-xl border border-slate-200 bg-white p-4">
            <div className="text-xs font-medium text-slate-500 mb-2">Por tipo</div>
            {typeChips.length === 0 ? (
              <div className="text-sm text-slate-400">Ninguna todavía</div>
            ) : (
              <div className="flex flex-wrap gap-1.5">
                {typeChips.map(([type, count]) => (
                  <span key={type} className="rounded-full bg-slate-100 px-2 py-0.5 text-xs font-semibold text-slate-600">
                    {TYPE_LABEL[type] ?? type}: {count}
                  </span>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      <div className="mb-4 flex gap-2">
        {(["pending_approval", "todas"] as StatusFilter[]).map((f) => (
          <button
            key={f}
            onClick={() => setStatusFilter(f)}
            className={`rounded-full px-3 py-1 text-xs font-semibold border ${
              statusFilter === f
                ? "bg-indigo-600 text-white border-indigo-600"
                : "bg-white text-slate-600 border-slate-200 hover:border-slate-300"
            }`}
          >
            {f === "pending_approval" ? "Pendientes" : "Todas (historial)"}
          </button>
        ))}
      </div>

      {error && (
        <div className="mb-4 rounded-xl border border-red-200 bg-red-50 p-3">
          <p className="text-sm text-red-600">{error}</p>
        </div>
      )}

      {isLoading && <p className="text-sm text-slate-500">Cargando...</p>}
      {data && data.length === 0 && <EmptyState message="Sin órdenes que mostrar con este filtro." />}
      {data && data.length > 0 && (
        <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-4 py-3">Cuenta</th>
                <th className="px-4 py-3">Tipo</th>
                <th className="px-4 py-3">Estado</th>
                <th className="px-4 py-3">Solicitada por</th>
                <th className="px-4 py-3">Justificación</th>
                <th className="px-4 py-3"></th>
              </tr>
            </thead>
            <tbody>
              {data.map((order: ControlOrder) => (
                <tr key={order.order_id} className={order.meter_protected ? "bg-red-50/40" : ""}>
                  <td className="px-4 py-3 font-medium text-slate-900">
                    <Link to={`/control/${order.order_id}`} className="text-indigo-600 hover:text-indigo-700">
                      {order.account_number}
                    </Link>
                    {order.meter_protected && (
                      <span className="ml-2 rounded-full bg-red-100 px-2 py-0.5 text-[10px] font-semibold text-red-700" title="Cuenta protegida contra suspensión/desconexión">
                        protegida
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-slate-600">{TYPE_LABEL[order.type] ?? order.type}</td>
                  <td className="px-4 py-3">
                    <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${STATUS_CLASS[order.status] ?? "bg-slate-50 text-slate-500"}`}>
                      {STATUS_LABEL[order.status] ?? order.status}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-slate-600">{order.requested_by}</td>
                  <td className="px-4 py-3 text-slate-600">{order.justification ?? "—"}</td>
                  <td className="px-4 py-3">
                    {order.status === "pending_approval" && (
                      <button
                        disabled={approveMutation.isPending}
                        onClick={() => approveMutation.mutate(order.order_id)}
                        className="rounded-lg bg-indigo-600 text-white text-xs font-semibold px-3 py-1.5 hover:bg-indigo-700 disabled:opacity-40"
                      >
                        Aprobar
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="mt-4 rounded-xl border border-indigo-100 bg-indigo-50/40 p-4 text-sm text-slate-600">
        <b className="text-slate-900">¿Qué cuentas no se pueden suspender/desconectar?</b>{" "}
        La lista de cuentas protegidas (hospitales, colegios, etc., según la regulación vigente) se administra en{" "}
        <Link to="/configuration" className="text-indigo-600 hover:text-indigo-700 font-medium">
          Configuración → Cuentas protegidas
        </Link>
        .
      </div>
    </StagePage>
  );
}
