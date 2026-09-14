import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ApiError,
  createMaintenanceOrder,
  getMaintenanceOrders,
  getNetworkAssets,
  sendMaintenanceOrderToBayforce,
  type MaintenanceOrder,
} from "../api";
import { StagePage, EmptyState } from "../components/StagePage";

// Gestion de Mantenimiento -- Track B, Sprint B7 (docs/07-track-b-alcance-funcional.md
// SS5): genera ordenes reales desde una anomalia REAL (activo fuera de
// servicio, o zona con balance que excede su tope regulatorio -- nunca
// "porque si" para una fuente automatica) y las envia a BayForce, ya en
// el portafolio (core/renflow/bayforce) -- integracion HTTP real contra
// un webhook configurable por tenant.

const TYPE_LABEL: Record<string, string> = {
  preventive: "Preventivo", corrective: "Correctivo", inspection: "Inspección",
};
const SOURCE_LABEL: Record<string, string> = {
  asset_condition: "Condición del activo", simulation_result: "Resultado de simulación",
  balance_anomaly: "Anomalía de balance", manual: "Manual",
};
const STATUS_LABEL: Record<string, string> = {
  generated: "Generada", sent_to_bayforce: "Enviada a BayForce",
  in_progress: "En progreso", completed: "Completada", cancelled: "Cancelada",
};
const STATUS_COLOR: Record<string, string> = {
  generated: "#f59e0b", sent_to_bayforce: "#3b82f6", in_progress: "#8b5cf6",
  completed: "#10b981", cancelled: "#64748b",
};

function CreateOrderForm() {
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [assetId, setAssetId] = useState("");
  const [type, setType] = useState("corrective");
  const [source, setSource] = useState("manual");
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);

  const { data: assets } = useQuery({ queryKey: ["network-assets"], queryFn: () => getNetworkAssets() });

  const mutation = useMutation({
    mutationFn: () => createMaintenanceOrder({ asset_id: assetId, type, source, reason: reason || null }),
    onSuccess: () => {
      setError(null);
      setReason("");
      setOpen(false);
      queryClient.invalidateQueries({ queryKey: ["maintenance-orders"] });
    },
    onError: (err) => setError(err instanceof ApiError ? err.message : "No se pudo generar la orden."),
  });

  if (!open) {
    return (
      <button onClick={() => setOpen(true)} className="rounded-lg bg-indigo-600 text-white text-xs font-semibold px-3 py-1.5 hover:bg-indigo-700">
        + Generar orden
      </button>
    );
  }

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 mb-4">
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
        <div>
          <label className="block text-xs font-medium text-slate-500 mb-1">Activo</label>
          <select className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm w-full bg-white" value={assetId} onChange={(e) => setAssetId(e.target.value)}>
            <option value="">— Elegir —</option>
            {(assets ?? []).map((a) => <option key={a.asset_id} value={a.asset_id}>{a.type} {a.asset_id.slice(0, 8)} ({a.status})</option>)}
          </select>
        </div>
        <div>
          <label className="block text-xs font-medium text-slate-500 mb-1">Tipo</label>
          <select className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm w-full bg-white" value={type} onChange={(e) => setType(e.target.value)}>
            {Object.entries(TYPE_LABEL).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
        </div>
        <div>
          <label className="block text-xs font-medium text-slate-500 mb-1">Fuente</label>
          <select className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm w-full bg-white" value={source} onChange={(e) => setSource(e.target.value)}>
            {Object.entries(SOURCE_LABEL).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
        </div>
        <div>
          <label className="block text-xs font-medium text-slate-500 mb-1">Motivo (opcional)</label>
          <input className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm w-full" value={reason} onChange={(e) => setReason(e.target.value)} placeholder="qué se encontró" />
        </div>
      </div>
      <p className="text-xs text-slate-500 mt-2">
        "Condición del activo" exige que el activo esté realmente <em>fuera de servicio</em> o <em>en mantenimiento</em> ahora mismo. "Anomalía de balance" exige que la zona del activo tenga un balance que exceda su tope regulatorio ahora mismo -- si no se cumple, la orden se rechaza (422), nunca se genera igual.
      </p>
      {error && <p className="text-sm text-red-600 mt-2">{error}</p>}
      <div className="mt-3 flex gap-2">
        <button onClick={() => mutation.mutate()} disabled={!assetId || mutation.isPending} className="rounded-lg bg-indigo-600 text-white text-xs font-semibold px-3 py-1.5 hover:bg-indigo-700 disabled:opacity-40">
          Generar
        </button>
        <button onClick={() => setOpen(false)} className="text-xs text-slate-500 hover:text-slate-700 px-2">Cancelar</button>
      </div>
    </div>
  );
}

function OrderRow({ order }: { order: MaintenanceOrder }) {
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);

  const sendMutation = useMutation({
    mutationFn: () => sendMaintenanceOrderToBayforce(order.order_id),
    onSuccess: () => {
      setError(null);
      queryClient.invalidateQueries({ queryKey: ["maintenance-orders"] });
    },
    onError: (err) => setError(err instanceof ApiError ? err.message : "No se pudo enviar a BayForce."),
  });

  return (
    <tr>
      <td className="px-4 py-3 font-medium text-slate-900">{TYPE_LABEL[order.type] ?? order.type}</td>
      <td className="px-4 py-3 text-slate-600">{SOURCE_LABEL[order.source] ?? order.source}</td>
      <td className="px-4 py-3 text-slate-600">{order.reason ?? "—"}</td>
      <td className="px-4 py-3">
        <span className="rounded-full px-2 py-0.5 text-xs font-semibold" style={{ background: `${STATUS_COLOR[order.status]}22`, color: STATUS_COLOR[order.status] }}>
          {STATUS_LABEL[order.status] ?? order.status}
        </span>
      </td>
      <td className="px-4 py-3 text-slate-500 font-mono text-xs">{order.bayforce_order_ref ?? "—"}</td>
      <td className="px-4 py-3 text-slate-500">{new Date(order.created_at).toLocaleString()}</td>
      <td className="px-4 py-3">
        {order.status === "generated" && (
          <button onClick={() => sendMutation.mutate()} disabled={sendMutation.isPending} className="text-xs text-indigo-600 hover:text-indigo-700 disabled:opacity-40">
            {sendMutation.isPending ? "Enviando..." : "Enviar a BayForce"}
          </button>
        )}
        {error && <p className="text-[11px] text-red-600 mt-1">{error}</p>}
      </td>
    </tr>
  );
}

export function MaintenancePage() {
  const [statusFilter, setStatusFilter] = useState<string>("");
  const { data: orders, isLoading } = useQuery({
    queryKey: ["maintenance-orders", statusFilter],
    queryFn: () => getMaintenanceOrders(statusFilter ? { status: statusFilter } : undefined),
    refetchInterval: 30_000,
  });

  const pendingCount = (orders ?? []).filter((o) => o.status === "generated").length;
  const inFlightCount = (orders ?? []).filter((o) => o.status === "sent_to_bayforce" || o.status === "in_progress").length;
  const completedCount = (orders ?? []).filter((o) => o.status === "completed").length;

  return (
    <StagePage title="Mantenimiento">
      {orders && (
        <div className="mb-6 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="rounded-xl border border-slate-200 bg-white p-4">
            <div className="text-2xl font-bold text-slate-900">{orders.length}</div>
            <div className="text-xs text-slate-500 mt-1">Órdenes totales</div>
          </div>
          <div className="rounded-xl border border-slate-200 bg-white p-4">
            <div className={`text-2xl font-bold ${pendingCount > 0 ? "text-amber-700" : "text-slate-900"}`}>{pendingCount}</div>
            <div className="text-xs text-slate-500 mt-1">Por enviar a BayForce</div>
          </div>
          <div className="rounded-xl border border-slate-200 bg-white p-4">
            <div className="text-2xl font-bold text-indigo-700">{inFlightCount}</div>
            <div className="text-xs text-slate-500 mt-1">En BayForce</div>
          </div>
          <div className="rounded-xl border border-slate-200 bg-white p-4">
            <div className="text-2xl font-bold text-emerald-700">{completedCount}</div>
            <div className="text-xs text-slate-500 mt-1">Completadas</div>
          </div>
        </div>
      )}

      <div className="mb-4 flex items-center justify-between flex-wrap gap-2">
        <div className="flex gap-2">
          {[["", "Todas"], ["generated", "Por enviar"], ["sent_to_bayforce", "En BayForce"], ["completed", "Completadas"]].map(([value, label]) => (
            <button
              key={value}
              onClick={() => setStatusFilter(value)}
              className={`rounded-full px-3 py-1 text-xs font-semibold border ${statusFilter === value ? "bg-indigo-600 text-white border-indigo-600" : "bg-white text-slate-600 border-slate-200 hover:border-slate-300"}`}
            >
              {label}
            </button>
          ))}
        </div>
        <CreateOrderForm />
      </div>

      {isLoading && <p className="text-sm text-slate-500">Cargando...</p>}
      {orders && orders.length === 0 && <EmptyState message="Sin órdenes de mantenimiento todavía." />}
      {orders && orders.length > 0 && (
        <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-4 py-3">Tipo</th>
                <th className="px-4 py-3">Fuente</th>
                <th className="px-4 py-3">Motivo</th>
                <th className="px-4 py-3">Estado</th>
                <th className="px-4 py-3">Ref. BayForce</th>
                <th className="px-4 py-3">Generada</th>
                <th className="px-4 py-3"></th>
              </tr>
            </thead>
            <tbody>
              {orders.map((order) => <OrderRow key={order.order_id} order={order} />)}
            </tbody>
          </table>
        </div>
      )}

      <div className="mt-4 rounded-xl border border-indigo-100 bg-indigo-50/40 p-4 text-sm text-slate-600">
        <b className="text-slate-900">¿Cómo se cierra una orden?</b>{" "}
        BayForce notifica el avance (en progreso / completada / cancelada) por su propio webhook de cierre -- no hay un botón manual para eso acá, refleja el estado real del trabajo en campo.
      </div>
    </StagePage>
  );
}
