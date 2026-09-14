import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ApiError,
  assignMaintenanceOrder,
  closeMaintenanceOrder,
  createCrew,
  createMaintenanceOrder,
  createPmPlan,
  generateDuePmOrders,
  getCrews,
  getFailureCodes,
  getMaintenanceKpis,
  getMaintenanceOrders,
  getNetworkAssets,
  getPmPlans,
  scheduleMaintenanceOrder,
  sendMaintenanceOrderToBayforce,
  startMaintenanceOrder,
  type MaintenanceOrder,
} from "../api";
import { StagePage, EmptyState } from "../components/StagePage";
import { SectionNav } from "../components/SectionNav";

// Gestion de Mantenimiento -- CMMS real (2026-09-14, docs/04-plan-sprints.md
// SS9): el panel anterior (Sprint B7) generaba la orden y la enviaba a
// BayForce, pero BayForce nunca tuvo un endpoint real que la recibiera
// (ver docs/05-ejecucion.md) y no habia sustancia de CMMS -- sin
// prioridad/SLA, codigos de falla, mantenimiento preventivo programado,
// planeacion/asignacion ni KPIs. Esta version construye el ciclo de vida
// real y propio (generated -> scheduled -> assigned -> in_progress ->
// completed | cancelled), dejando BayForce como notificacion de salida
// OPCIONAL (el boton "Enviar a BayForce" sigue existiendo, sin ser el
// unico camino).

const SECTIONS = [
  { id: "kpis", label: "Estado general" },
  { id: "orders", label: "Órdenes" },
  { id: "pm-plans", label: "Mantenimiento preventivo" },
];

const TYPE_LABEL: Record<string, string> = {
  preventive: "Preventivo", corrective: "Correctivo", inspection: "Inspección",
};
const SOURCE_LABEL: Record<string, string> = {
  asset_condition: "Condición del activo", simulation_result: "Resultado de simulación",
  balance_anomaly: "Anomalía de balance", pm_schedule: "Preventivo programado", manual: "Manual",
};
const STATUS_LABEL: Record<string, string> = {
  generated: "Generada", scheduled: "Programada", assigned: "Asignada", sent_to_bayforce: "Enviada a BayForce",
  in_progress: "En progreso", completed: "Completada", cancelled: "Cancelada",
};
const STATUS_COLOR: Record<string, string> = {
  generated: "#f59e0b", scheduled: "#0ea5e9", assigned: "#6366f1", sent_to_bayforce: "#3b82f6",
  in_progress: "#8b5cf6", completed: "#10b981", cancelled: "#64748b",
};
const PRIORITY_LABEL: Record<string, string> = {
  low: "Baja", medium: "Media", high: "Alta", emergency: "Emergencia",
};
const PRIORITY_COLOR: Record<string, string> = {
  low: "#64748b", medium: "#0ea5e9", high: "#f59e0b", emergency: "#ef4444",
};

function CreateOrderForm() {
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [assetId, setAssetId] = useState("");
  const [type, setType] = useState("corrective");
  const [source, setSource] = useState("manual");
  const [priority, setPriority] = useState("medium");
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);

  const { data: assets } = useQuery({ queryKey: ["network-assets"], queryFn: () => getNetworkAssets() });

  const mutation = useMutation({
    mutationFn: () => createMaintenanceOrder({ asset_id: assetId, type, source, priority, reason: reason || null }),
    onSuccess: () => {
      setError(null);
      setReason("");
      setOpen(false);
      queryClient.invalidateQueries({ queryKey: ["maintenance-orders"] });
      queryClient.invalidateQueries({ queryKey: ["maintenance-kpis"] });
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
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3">
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
            {Object.entries(SOURCE_LABEL).filter(([v]) => v !== "pm_schedule").map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
        </div>
        <div>
          <label className="block text-xs font-medium text-slate-500 mb-1">Prioridad</label>
          <select className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm w-full bg-white" value={priority} onChange={(e) => setPriority(e.target.value)}>
            {Object.entries(PRIORITY_LABEL).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
        </div>
        <div>
          <label className="block text-xs font-medium text-slate-500 mb-1">Motivo (opcional)</label>
          <input className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm w-full" value={reason} onChange={(e) => setReason(e.target.value)} placeholder="qué se encontró" />
        </div>
      </div>
      <p className="text-xs text-slate-500 mt-2">
        "Condición del activo" exige que el activo esté realmente <em>fuera de servicio</em> o <em>en mantenimiento</em> ahora mismo. "Anomalía de balance" exige que la zona del activo tenga un balance que exceda su tope regulatorio ahora mismo -- si no se cumple, la orden se rechaza (422), nunca se genera igual. El SLA se calcula solo si hay una política configurada para esta prioridad (Configuración → SLA de mantenimiento).
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

function CloseOrderForm({ order, onDone }: { order: MaintenanceOrder; onDone: () => void }) {
  const queryClient = useQueryClient();
  const [status, setStatus] = useState<"completed" | "cancelled">("completed");
  const [laborHours, setLaborHours] = useState("");
  const [materialsUsed, setMaterialsUsed] = useState("");
  const [rootCause, setRootCause] = useState("");
  const [failureCodeId, setFailureCodeId] = useState("");
  const [error, setError] = useState<string | null>(null);

  const { data: failureCodes } = useQuery({ queryKey: ["failure-codes"], queryFn: () => getFailureCodes() });

  const mutation = useMutation({
    mutationFn: () =>
      closeMaintenanceOrder(order.order_id, {
        status,
        labor_hours: laborHours ? Number(laborHours) : null,
        materials_used: materialsUsed || null,
        root_cause: rootCause || null,
        failure_code_id: failureCodeId || null,
      }),
    onSuccess: () => {
      setError(null);
      queryClient.invalidateQueries({ queryKey: ["maintenance-orders"] });
      queryClient.invalidateQueries({ queryKey: ["maintenance-kpis"] });
      onDone();
    },
    onError: (err) => setError(err instanceof ApiError ? err.message : "No se pudo cerrar la orden."),
  });

  return (
    <tr className="bg-slate-50">
      <td colSpan={8} className="px-4 py-3">
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-2">
          <div>
            <label className="block text-[10px] font-medium text-slate-500 mb-1">Resultado</label>
            <select className="rounded-lg border border-slate-300 px-2 py-1 text-xs w-full bg-white" value={status} onChange={(e) => setStatus(e.target.value as "completed" | "cancelled")}>
              <option value="completed">Completada</option>
              <option value="cancelled">Cancelada</option>
            </select>
          </div>
          <div>
            <label className="block text-[10px] font-medium text-slate-500 mb-1">Horas de mano de obra</label>
            <input type="number" className="rounded-lg border border-slate-300 px-2 py-1 text-xs w-full" value={laborHours} onChange={(e) => setLaborHours(e.target.value)} />
          </div>
          <div>
            <label className="block text-[10px] font-medium text-slate-500 mb-1">Materiales usados</label>
            <input className="rounded-lg border border-slate-300 px-2 py-1 text-xs w-full" value={materialsUsed} onChange={(e) => setMaterialsUsed(e.target.value)} />
          </div>
          <div>
            <label className="block text-[10px] font-medium text-slate-500 mb-1">Código de falla</label>
            <select className="rounded-lg border border-slate-300 px-2 py-1 text-xs w-full bg-white" value={failureCodeId} onChange={(e) => setFailureCodeId(e.target.value)}>
              <option value="">— Ninguno —</option>
              {(failureCodes ?? []).map((fc) => <option key={fc.failure_code_id} value={fc.failure_code_id}>{fc.code}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-[10px] font-medium text-slate-500 mb-1">Causa raíz</label>
            <input className="rounded-lg border border-slate-300 px-2 py-1 text-xs w-full" value={rootCause} onChange={(e) => setRootCause(e.target.value)} />
          </div>
        </div>
        {error && <p className="text-xs text-red-600 mt-2">{error}</p>}
        <div className="mt-2 flex gap-2">
          <button onClick={() => mutation.mutate()} disabled={mutation.isPending} className="rounded-lg bg-indigo-600 text-white text-xs font-semibold px-3 py-1.5 hover:bg-indigo-700 disabled:opacity-40">
            Cerrar orden
          </button>
          <button onClick={onDone} className="text-xs text-slate-500 hover:text-slate-700 px-2">Cancelar</button>
        </div>
      </td>
    </tr>
  );
}

function OrderRow({ order }: { order: MaintenanceOrder }) {
  const queryClient = useQueryClient();
  const [scheduling, setScheduling] = useState(false);
  const [assigning, setAssigning] = useState(false);
  const [closing, setClosing] = useState(false);
  const [scheduledAt, setScheduledAt] = useState("");
  const [crewId, setCrewId] = useState("");
  const [error, setError] = useState<string | null>(null);

  const { data: crews } = useQuery({ queryKey: ["crews"], queryFn: () => getCrews(), enabled: assigning });

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["maintenance-orders"] });
    queryClient.invalidateQueries({ queryKey: ["maintenance-kpis"] });
  };

  const sendMutation = useMutation({
    mutationFn: () => sendMaintenanceOrderToBayforce(order.order_id),
    onSuccess: () => { setError(null); invalidate(); },
    onError: (err) => setError(err instanceof ApiError ? err.message : "No se pudo enviar a BayForce."),
  });
  const scheduleMutation = useMutation({
    mutationFn: () => scheduleMaintenanceOrder(order.order_id, new Date(scheduledAt).toISOString()),
    onSuccess: () => { setError(null); setScheduling(false); invalidate(); },
    onError: (err) => setError(err instanceof ApiError ? err.message : "No se pudo programar la orden."),
  });
  const assignMutation = useMutation({
    mutationFn: () => assignMaintenanceOrder(order.order_id, crewId),
    onSuccess: () => { setError(null); setAssigning(false); invalidate(); },
    onError: (err) => setError(err instanceof ApiError ? err.message : "No se pudo asignar la orden."),
  });
  const startMutation = useMutation({
    mutationFn: () => startMaintenanceOrder(order.order_id),
    onSuccess: () => { setError(null); invalidate(); },
    onError: (err) => setError(err instanceof ApiError ? err.message : "No se pudo iniciar la orden."),
  });

  return (
    <>
      <tr className={order.is_overdue ? "bg-red-50/40" : ""}>
        <td className="px-4 py-3 font-medium text-slate-900">
          {TYPE_LABEL[order.type] ?? order.type}
          {order.priority && (
            <span className="ml-2 rounded-full px-2 py-0.5 text-[10px] font-semibold" style={{ background: `${PRIORITY_COLOR[order.priority]}22`, color: PRIORITY_COLOR[order.priority] }}>
              {PRIORITY_LABEL[order.priority] ?? order.priority}
            </span>
          )}
        </td>
        <td className="px-4 py-3 text-slate-600">{SOURCE_LABEL[order.source] ?? order.source}</td>
        <td className="px-4 py-3 text-slate-600">{order.reason ?? "—"}</td>
        <td className="px-4 py-3">
          <span className="rounded-full px-2 py-0.5 text-xs font-semibold" style={{ background: `${STATUS_COLOR[order.status]}22`, color: STATUS_COLOR[order.status] }}>
            {STATUS_LABEL[order.status] ?? order.status}
          </span>
          {order.is_overdue && (
            <span className="ml-2 rounded-full bg-red-100 px-2 py-0.5 text-[10px] font-semibold text-red-700" title={`Venció su SLA (${order.sla_due_at ? new Date(order.sla_due_at).toLocaleString() : ""})`}>
              vencida
            </span>
          )}
        </td>
        <td className="px-4 py-3 text-slate-500">{order.sla_due_at ? new Date(order.sla_due_at).toLocaleString() : "—"}</td>
        <td className="px-4 py-3 text-slate-500 font-mono text-xs">{order.bayforce_order_ref ?? "—"}</td>
        <td className="px-4 py-3 text-slate-500">{new Date(order.created_at).toLocaleString()}</td>
        <td className="px-4 py-3">
          <div className="flex flex-col gap-1 items-start">
            {order.status === "generated" && (
              <>
                <button onClick={() => setScheduling((v) => !v)} className="text-xs text-indigo-600 hover:text-indigo-700">Programar</button>
                <button onClick={() => sendMutation.mutate()} disabled={sendMutation.isPending} className="text-xs text-indigo-600 hover:text-indigo-700 disabled:opacity-40">
                  {sendMutation.isPending ? "Enviando..." : "Enviar a BayForce"}
                </button>
              </>
            )}
            {order.status === "scheduled" && (
              <button onClick={() => setAssigning((v) => !v)} className="text-xs text-indigo-600 hover:text-indigo-700">Asignar cuadrilla</button>
            )}
            {(order.status === "assigned" || order.status === "sent_to_bayforce") && (
              <button onClick={() => startMutation.mutate()} disabled={startMutation.isPending} className="text-xs text-indigo-600 hover:text-indigo-700 disabled:opacity-40">
                Iniciar trabajo
              </button>
            )}
            {order.status === "in_progress" && (
              <button onClick={() => setClosing((v) => !v)} className="text-xs text-indigo-600 hover:text-indigo-700">Cerrar orden</button>
            )}
            {order.status === "completed" && order.labor_hours !== null && (
              <span className="text-[11px] text-slate-400">{order.labor_hours}h · {order.materials_used ?? "sin materiales"}</span>
            )}
            {error && <span className="text-[11px] text-red-600">{error}</span>}
          </div>
        </td>
      </tr>
      {scheduling && (
        <tr className="bg-slate-50">
          <td colSpan={8} className="px-4 py-3">
            <div className="flex flex-wrap items-end gap-3">
              <div>
                <label className="block text-[10px] font-medium text-slate-500 mb-1">Fecha/hora programada</label>
                <input type="datetime-local" className="rounded-lg border border-slate-300 px-2 py-1 text-xs" value={scheduledAt} onChange={(e) => setScheduledAt(e.target.value)} />
              </div>
              <button onClick={() => scheduleMutation.mutate()} disabled={!scheduledAt || scheduleMutation.isPending} className="rounded-lg bg-indigo-600 text-white text-xs font-semibold px-3 py-1.5 hover:bg-indigo-700 disabled:opacity-40">
                Programar
              </button>
              <button onClick={() => setScheduling(false)} className="text-xs text-slate-500 hover:text-slate-700 px-2">Cancelar</button>
            </div>
          </td>
        </tr>
      )}
      {assigning && (
        <tr className="bg-slate-50">
          <td colSpan={8} className="px-4 py-3">
            <div className="flex flex-wrap items-end gap-3">
              <div>
                <label className="block text-[10px] font-medium text-slate-500 mb-1">Cuadrilla</label>
                <select className="rounded-lg border border-slate-300 px-2 py-1 text-xs bg-white" value={crewId} onChange={(e) => setCrewId(e.target.value)}>
                  <option value="">— Elegir —</option>
                  {(crews ?? []).map((c) => <option key={c.crew_id} value={c.crew_id}>{c.name}</option>)}
                </select>
              </div>
              <button onClick={() => assignMutation.mutate()} disabled={!crewId || assignMutation.isPending} className="rounded-lg bg-indigo-600 text-white text-xs font-semibold px-3 py-1.5 hover:bg-indigo-700 disabled:opacity-40">
                Asignar
              </button>
              <button onClick={() => setAssigning(false)} className="text-xs text-slate-500 hover:text-slate-700 px-2">Cancelar</button>
            </div>
          </td>
        </tr>
      )}
      {closing && <CloseOrderForm order={order} onDone={() => setClosing(false)} />}
    </>
  );
}

function CreatePmPlanForm() {
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [assetId, setAssetId] = useState("");
  const [orderType, setOrderType] = useState("preventive");
  const [priority, setPriority] = useState("low");
  const [intervalDays, setIntervalDays] = useState("180");
  const [nextDueAt, setNextDueAt] = useState("");
  const [error, setError] = useState<string | null>(null);

  const { data: assets } = useQuery({ queryKey: ["network-assets"], queryFn: () => getNetworkAssets() });

  const mutation = useMutation({
    mutationFn: () =>
      createPmPlan({
        asset_id: assetId, order_type: orderType, priority,
        interval_days: Number(intervalDays), next_due_at: new Date(nextDueAt).toISOString(),
      }),
    onSuccess: () => {
      setError(null);
      setOpen(false);
      queryClient.invalidateQueries({ queryKey: ["pm-plans"] });
    },
    onError: (err) => setError(err instanceof ApiError ? err.message : "No se pudo crear el plan."),
  });

  if (!open) {
    return (
      <button onClick={() => setOpen(true)} className="rounded-lg bg-indigo-600 text-white text-xs font-semibold px-3 py-1.5 hover:bg-indigo-700">
        + Nuevo plan
      </button>
    );
  }

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 mb-4">
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3">
        <div>
          <label className="block text-xs font-medium text-slate-500 mb-1">Activo</label>
          <select className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm w-full bg-white" value={assetId} onChange={(e) => setAssetId(e.target.value)}>
            <option value="">— Elegir —</option>
            {(assets ?? []).map((a) => <option key={a.asset_id} value={a.asset_id}>{a.type} {a.asset_id.slice(0, 8)}</option>)}
          </select>
        </div>
        <div>
          <label className="block text-xs font-medium text-slate-500 mb-1">Tipo</label>
          <select className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm w-full bg-white" value={orderType} onChange={(e) => setOrderType(e.target.value)}>
            <option value="preventive">Preventivo</option>
            <option value="inspection">Inspección</option>
          </select>
        </div>
        <div>
          <label className="block text-xs font-medium text-slate-500 mb-1">Prioridad</label>
          <select className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm w-full bg-white" value={priority} onChange={(e) => setPriority(e.target.value)}>
            {Object.entries(PRIORITY_LABEL).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
        </div>
        <div>
          <label className="block text-xs font-medium text-slate-500 mb-1">Intervalo (días)</label>
          <input type="number" className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm w-full" value={intervalDays} onChange={(e) => setIntervalDays(e.target.value)} />
        </div>
        <div>
          <label className="block text-xs font-medium text-slate-500 mb-1">Próximo vencimiento</label>
          <input type="datetime-local" className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm w-full" value={nextDueAt} onChange={(e) => setNextDueAt(e.target.value)} />
        </div>
      </div>
      <p className="text-xs text-slate-500 mt-2">
        Plan real por activo específico -- cuando "Próximo vencimiento" ya pasó, "Generar órdenes vencidas" genera la orden real y avanza el plan al siguiente ciclo.
      </p>
      {error && <p className="text-sm text-red-600 mt-2">{error}</p>}
      <div className="mt-3 flex gap-2">
        <button onClick={() => mutation.mutate()} disabled={!assetId || !nextDueAt || mutation.isPending} className="rounded-lg bg-indigo-600 text-white text-xs font-semibold px-3 py-1.5 hover:bg-indigo-700 disabled:opacity-40">
          Crear plan
        </button>
        <button onClick={() => setOpen(false)} className="text-xs text-slate-500 hover:text-slate-700 px-2">Cancelar</button>
      </div>
    </div>
  );
}

function PmPlansSection() {
  const queryClient = useQueryClient();
  const [result, setResult] = useState<string | null>(null);
  const { data: plans, isLoading } = useQuery({ queryKey: ["pm-plans"], queryFn: getPmPlans, refetchInterval: 30_000 });

  const generateMutation = useMutation({
    mutationFn: generateDuePmOrders,
    onSuccess: (orders) => {
      setResult(orders.length === 0 ? "Ningún plan vencido todavía." : `${orders.length} orden(es) generada(s).`);
      queryClient.invalidateQueries({ queryKey: ["pm-plans"] });
      queryClient.invalidateQueries({ queryKey: ["maintenance-orders"] });
      queryClient.invalidateQueries({ queryKey: ["maintenance-kpis"] });
    },
  });

  return (
    <>
      <div className="mb-2 flex items-center justify-between flex-wrap gap-2">
        <h2 className="text-sm font-semibold text-slate-500 uppercase tracking-wide">Planes de mantenimiento preventivo</h2>
        <div className="flex gap-2 items-center">
          {result && <span className="text-xs text-slate-500">{result}</span>}
          <button
            onClick={() => { setResult(null); generateMutation.mutate(); }}
            disabled={generateMutation.isPending}
            className="rounded-lg bg-white border border-slate-300 text-slate-700 text-xs font-semibold px-3 py-1.5 hover:border-indigo-300 disabled:opacity-40"
          >
            {generateMutation.isPending ? "Generando..." : "Generar órdenes vencidas"}
          </button>
          <CreatePmPlanForm />
        </div>
      </div>
      {isLoading && <p className="text-sm text-slate-500">Cargando...</p>}
      {plans && plans.length === 0 && <EmptyState message="Sin planes de mantenimiento preventivo todavía." />}
      {plans && plans.length > 0 && (
        <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-4 py-3">Activo</th>
                <th className="px-4 py-3">Tipo</th>
                <th className="px-4 py-3">Prioridad</th>
                <th className="px-4 py-3">Intervalo</th>
                <th className="px-4 py-3">Próximo vencimiento</th>
                <th className="px-4 py-3">Última generada</th>
              </tr>
            </thead>
            <tbody>
              {plans.map((p) => {
                const due = new Date(p.next_due_at) <= new Date();
                return (
                  <tr key={p.pm_plan_id} className={due ? "bg-amber-50" : ""}>
                    <td className="px-4 py-3 font-mono text-xs text-slate-600">{p.asset_id.slice(0, 8)}</td>
                    <td className="px-4 py-3 text-slate-600">{TYPE_LABEL[p.order_type] ?? p.order_type}</td>
                    <td className="px-4 py-3">
                      <span className="rounded-full px-2 py-0.5 text-[10px] font-semibold" style={{ background: `${PRIORITY_COLOR[p.priority]}22`, color: PRIORITY_COLOR[p.priority] }}>
                        {PRIORITY_LABEL[p.priority] ?? p.priority}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-slate-600">cada {p.interval_days} días</td>
                    <td className="px-4 py-3 text-slate-600">
                      {new Date(p.next_due_at).toLocaleString()}
                      {due && <span className="ml-2 rounded-full bg-amber-100 px-2 py-0.5 text-[10px] font-semibold text-amber-700">vencido</span>}
                    </td>
                    <td className="px-4 py-3 text-slate-500">{p.last_generated_at ? new Date(p.last_generated_at).toLocaleString() : "nunca"}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}

function CreateCrewInline() {
  const queryClient = useQueryClient();
  const [name, setName] = useState("");
  const mutation = useMutation({
    mutationFn: () => createCrew(name),
    onSuccess: () => { setName(""); queryClient.invalidateQueries({ queryKey: ["crews"] }); },
  });
  return (
    <div className="flex gap-2 items-center">
      <input className="rounded-lg border border-slate-300 px-2 py-1 text-xs" placeholder="Nueva cuadrilla" value={name} onChange={(e) => setName(e.target.value)} />
      <button onClick={() => mutation.mutate()} disabled={!name || mutation.isPending} className="rounded-lg bg-white border border-slate-300 text-xs font-semibold px-2 py-1 hover:border-indigo-300 disabled:opacity-40">
        + Agregar
      </button>
    </div>
  );
}

export function MaintenancePage() {
  const [statusFilter, setStatusFilter] = useState<string>("");
  const { data: orders, isLoading } = useQuery({
    queryKey: ["maintenance-orders", statusFilter],
    queryFn: () => getMaintenanceOrders(statusFilter ? { status: statusFilter } : undefined),
    refetchInterval: 30_000,
  });
  const { data: kpis } = useQuery({ queryKey: ["maintenance-kpis"], queryFn: getMaintenanceKpis, refetchInterval: 30_000 });
  const { data: crews } = useQuery({ queryKey: ["crews"], queryFn: () => getCrews() });

  return (
    <StagePage title="Mantenimiento">
      <SectionNav items={SECTIONS} />

      <div id="kpis" className="scroll-mt-24 mb-8">
        <h2 className="text-sm font-semibold text-slate-500 uppercase tracking-wide mb-2">Estado general</h2>
        {kpis && (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
            <div className="rounded-xl border border-slate-200 bg-white p-4">
              <div className="text-2xl font-bold text-slate-900">{kpis.total_orders}</div>
              <div className="text-xs text-slate-500 mt-1">Órdenes totales</div>
            </div>
            <div className="rounded-xl border border-slate-200 bg-white p-4">
              <div className="text-2xl font-bold text-slate-900">{kpis.mttr_hours === null ? "—" : `${kpis.mttr_hours}h`}</div>
              <div className="text-xs text-slate-500 mt-1">MTTR (tiempo medio de reparación)</div>
            </div>
            <div className="rounded-xl border border-slate-200 bg-white p-4">
              <div className={`text-2xl font-bold ${kpis.backlog.count > 0 ? "text-amber-700" : "text-slate-900"}`}>{kpis.backlog.count}</div>
              <div className="text-xs text-slate-500 mt-1">
                Backlog abierto{kpis.backlog.avg_age_hours !== null ? ` (${kpis.backlog.avg_age_hours}h prom.)` : ""}
              </div>
            </div>
            <div className="rounded-xl border border-slate-200 bg-white p-4">
              <div className="text-2xl font-bold text-emerald-700">{kpis.pm_compliance_pct === null ? "—" : `${kpis.pm_compliance_pct}%`}</div>
              <div className="text-xs text-slate-500 mt-1">Cumplimiento de preventivo</div>
            </div>
            <div className="rounded-xl border border-slate-200 bg-white p-4">
              <div className={`text-2xl font-bold ${kpis.overdue_count > 0 ? "text-red-700" : "text-slate-900"}`}>{kpis.overdue_count}</div>
              <div className="text-xs text-slate-500 mt-1">Órdenes vencidas de SLA</div>
            </div>
          </div>
        )}
      </div>

      <div id="orders" className="scroll-mt-24 mb-8">
        <div className="mb-4 flex items-center justify-between flex-wrap gap-2">
          <div className="flex gap-2 flex-wrap">
            {[["", "Todas"], ["generated", "Generadas"], ["scheduled", "Programadas"], ["assigned", "Asignadas"], ["in_progress", "En progreso"], ["completed", "Completadas"]].map(([value, label]) => (
              <button
                key={value}
                onClick={() => setStatusFilter(value)}
                className={`rounded-full px-3 py-1 text-xs font-semibold border ${statusFilter === value ? "bg-indigo-600 text-white border-indigo-600" : "bg-white text-slate-600 border-slate-200 hover:border-slate-300"}`}
              >
                {label}
              </button>
            ))}
          </div>
          <div className="flex gap-3 items-center">
            {(crews ?? []).length === 0 && <CreateCrewInline />}
            <CreateOrderForm />
          </div>
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
                  <th className="px-4 py-3">SLA</th>
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
          <b className="text-slate-900">¿Y BayForce?</b>{" "}
          Sigue disponible como notificación de salida opcional ("Enviar a BayForce" sobre una orden recién generada) -- pero el ciclo de vida real de la orden (programar, asignar, iniciar, cerrar con horas/materiales/causa) ya no depende de eso. BayForce solo notifica el avance por su propio webhook de cierre para las órdenes que sí se le enviaron.
        </div>
      </div>

      <div id="pm-plans" className="scroll-mt-24">
        <PmPlansSection />
      </div>
    </StagePage>
  );
}
