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
  getAnnualCalendar,
  getCrews,
  getMaintenanceCommunityCatalog,
  getMaintenanceEvents,
  recordMaintenanceEvent,
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

import { sectionsFor } from "../navigation";
import { badgeClass, label as codeLabel, options as codeOptions, appLocale, formSuffix, term } from "../catalog";
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

const SECTIONS = sectionsFor("/maintenance");


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
            {codeOptions("maintenance.type").map(({ code: v, label: l }) => <option key={v} value={v}>{l}</option>)}
          </select>
        </div>
        <div>
          <label className="block text-xs font-medium text-slate-500 mb-1">Fuente</label>
          <select className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm w-full bg-white" value={source} onChange={(e) => setSource(e.target.value)}>
            {codeOptions("maintenance.source").filter((o) => o.code !== "pm_schedule").map((o) => <option key={o.code} value={o.code}>{o.label}</option>)}
          </select>
        </div>
        <div>
          <label className="block text-xs font-medium text-slate-500 mb-1">Prioridad</label>
          <select className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm w-full bg-white" value={priority} onChange={(e) => setPriority(e.target.value)}>
            {codeOptions("maintenance.priority").map(({ code: v, label: l }) => <option key={v} value={v}>{l}</option>)}
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
  const [steps, setSteps] = useState<number[]>([]);
  const [responsible, setResponsible] = useState("");
  const [pending, setPending] = useState("");
  const [participants, setParticipants] = useState("");
  const [volunteerHours, setVolunteerHours] = useState("");
  const [wasteHandler, setWasteHandler] = useState("");
  const [wasteDestination, setWasteDestination] = useState("");
  const [sludge, setSludge] = useState("");
  const [error, setError] = useState<string | null>(null);

  const { data: failureCodes } = useQuery({ queryKey: ["failure-codes"], queryFn: () => getFailureCodes() });
  const { data: catalog } = useQuery({ queryKey: ["maintenance-community-catalog"], queryFn: getMaintenanceCommunityCatalog });

  const mutation = useMutation({
    mutationFn: () =>
      closeMaintenanceOrder(order.order_id, {
        status,
        labor_hours: laborHours ? Number(laborHours) : null,
        materials_used: materialsUsed || null,
        root_cause: rootCause || null,
        failure_code_id: failureCodeId || null,
        steps_done: steps,
        responsible: responsible || null,
        pending_notes: pending || null,
        community_participants: participants ? Number(participants) : null,
        volunteer_hours: volunteerHours ? Number(volunteerHours) : null,
        waste_handler: wasteHandler || null,
        waste_destination: wasteDestination || null,
        sludge_volume_m3: sludge ? Number(sludge) : null,
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
        {status === "completed" && (catalog?.steps.length ?? 0) > 0 && (
          <div className="mt-3">
            <p className="text-[10px] font-medium text-slate-500 mb-1">Pasos del mantenimiento que se cumplieron</p>
            <div className="flex flex-wrap gap-2">
              {catalog!.steps.map((s) => (
                <label key={s.step_no} className={`inline-flex cursor-pointer items-center gap-1 rounded-full border px-2.5 py-1 text-xs ${steps.includes(s.step_no) ? "border-emerald-600 bg-emerald-50 text-emerald-800" : "border-slate-300 bg-white text-slate-700"}`}>
                  <input type="checkbox" className="sr-only" checked={steps.includes(s.step_no)}
                    onChange={() => setSteps((cur) => (cur.includes(s.step_no) ? cur.filter((x) => x !== s.step_no) : [...cur, s.step_no]))} />
                  {s.step_no}. {s.label}
                </label>
              ))}
            </div>
          </div>
        )}
        {status === "completed" && (
          <div className="mt-2 grid grid-cols-2 sm:grid-cols-4 gap-2">
            <div>
              <label className="block text-[10px] font-medium text-slate-500 mb-1">Responsable</label>
              <input className="rounded-lg border border-slate-300 px-2 py-1 text-xs w-full" value={responsible} onChange={(e) => setResponsible(e.target.value)} />
            </div>
            <div>
              <label className="block text-[10px] font-medium text-slate-500 mb-1">Pendiente</label>
              <input className="rounded-lg border border-slate-300 px-2 py-1 text-xs w-full" value={pending} onChange={(e) => setPending(e.target.value)} placeholder="lo que quedó por hacer" />
            </div>
            <div>
              <label className="block text-[10px] font-medium text-slate-500 mb-1">{term("community_work", { capital: true })}: personas</label>
              <input type="number" min={0} className="rounded-lg border border-slate-300 px-2 py-1 text-xs w-full" value={participants} onChange={(e) => setParticipants(e.target.value)} />
            </div>
            <div>
              <label className="block text-[10px] font-medium text-slate-500 mb-1">{term("community_work", { capital: true })}: horas donadas</label>
              <input type="number" min={0} step="any" className="rounded-lg border border-slate-300 px-2 py-1 text-xs w-full" value={volunteerHours} onChange={(e) => setVolunteerHours(e.target.value)} />
            </div>
          </div>
        )}
        {status === "completed" && (
          <details className="mt-2">
            <summary className="cursor-pointer text-[11px] font-medium text-slate-600">Saneamiento: residuos y lodos{formSuffix("sanitation_register")}</summary>
            <div className="mt-2 grid grid-cols-1 sm:grid-cols-3 gap-2">
              <input aria-label="Quién retiró los residuos" className="rounded-lg border border-slate-300 px-2 py-1 text-xs" placeholder="Quién retiró los residuos" value={wasteHandler} onChange={(e) => setWasteHandler(e.target.value)} />
              <input aria-label="Destino seguro" className="rounded-lg border border-slate-300 px-2 py-1 text-xs" placeholder="Destino seguro" value={wasteDestination} onChange={(e) => setWasteDestination(e.target.value)} />
              <input aria-label="Lodos (m³)" type="number" min={0} step="any" className="rounded-lg border border-slate-300 px-2 py-1 text-xs" placeholder="Lodos retirados (m³)" value={sludge} onChange={(e) => setSludge(e.target.value)} />
            </div>
          </details>
        )}
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
          {codeLabel("maintenance.type", order.type)}
          {order.priority && (
            <span className={`ml-2 rounded-full px-2 py-0.5 text-[10px] font-semibold ${badgeClass("maintenance.priority", order.priority)}`}>
              {codeLabel("maintenance.priority", order.priority)}
            </span>
          )}
        </td>
        <td className="px-4 py-3 text-slate-600">{codeLabel("maintenance.source", order.source)}</td>
        <td className="px-4 py-3 text-slate-600">{order.reason ?? "—"}</td>
        <td className="px-4 py-3">
          <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${badgeClass("maintenance.status", order.status)}`}>
            {codeLabel("maintenance.status", order.status)}
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
            {order.status === "completed" && (order.steps_done?.length || order.community_participants) ? (
              <span className="text-[11px] text-slate-500">
                {order.steps_done?.length ? `${order.steps_done.length} pasos` : ""}
                {order.community_participants ? ` · ${term("community_work")}: ${order.community_participants} personas, ${order.volunteer_hours ?? 0} h` : ""}
                {order.pending_notes ? ` · pendiente: ${order.pending_notes}` : ""}
              </span>
            ) : null}
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
  const [title, setTitle] = useState("");
  const [responsible, setResponsible] = useState("");
  const [events, setEvents] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);

  const { data: assets } = useQuery({ queryKey: ["network-assets"], queryFn: () => getNetworkAssets() });
  const { data: catalog } = useQuery({ queryKey: ["maintenance-community-catalog"], queryFn: getMaintenanceCommunityCatalog });

  const mutation = useMutation({
    mutationFn: () =>
      createPmPlan({
        asset_id: assetId, order_type: orderType, priority,
        interval_days: Number(intervalDays), next_due_at: new Date(nextDueAt).toISOString(),
        title: title || null, responsible: responsible || null, trigger_events: events,
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
            {codeOptions("maintenance.priority").map(({ code: v, label: l }) => <option key={v} value={v}>{l}</option>)}
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
      <div className="mt-3 grid grid-cols-1 sm:grid-cols-2 gap-3">
        <div>
          <label className="block text-xs font-medium text-slate-500 mb-1">Actividad</label>
          <input className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm w-full" value={title} onChange={(e) => setTitle(e.target.value)} placeholder="p. ej. Limpieza de captación y desarenador" />
        </div>
        <div>
          <label className="block text-xs font-medium text-slate-500 mb-1">Responsable</label>
          <input className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm w-full" value={responsible} onChange={(e) => setResponsible(e.target.value)} placeholder={`p. ej. Operador + ${term("community_work")}`} />
        </div>
      </div>
      {(catalog?.event_types.length ?? 0) > 0 && (
        <div className="mt-3">
          <p className="text-xs font-medium text-slate-500 mb-1">Además, después de (revisión extraordinaria):</p>
          <div className="flex flex-wrap gap-2">
            {catalog!.event_types.map((e) => (
              <label key={e.code} className={`inline-flex cursor-pointer items-center rounded-full border px-2.5 py-1 text-xs ${events.includes(e.code) ? "border-indigo-600 bg-indigo-50 text-indigo-800" : "border-slate-300 bg-white text-slate-700"}`}>
                <input type="checkbox" className="sr-only" checked={events.includes(e.code)}
                  onChange={() => setEvents((cur) => (cur.includes(e.code) ? cur.filter((x) => x !== e.code) : [...cur, e.code]))} />
                {e.label}
              </label>
            ))}
          </div>
        </div>
      )}
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
  const { data: catalog } = useQuery({ queryKey: ["maintenance-community-catalog"], queryFn: getMaintenanceCommunityCatalog });
  const eventLabels = Object.fromEntries((catalog?.event_types ?? []).map((e) => [e.code, e.label.toLowerCase()]));

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
                    <td className="px-4 py-3 text-xs text-slate-700">
                      {p.title ?? <span className="font-mono text-slate-600">{p.asset_id.slice(0, 8)}</span>}
                      {p.responsible && <span className="block text-[11px] text-slate-500">{p.responsible}</span>}
                      {(p.trigger_events?.length ?? 0) > 0 && (
                        <span className="block text-[11px] text-indigo-700">
                          y después de: {p.trigger_events!.map((c) => eventLabels[c] ?? c).join(", ")}
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-slate-600">{codeLabel("maintenance.type", p.order_type)}</td>
                    <td className="px-4 py-3">
                      <span className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ${badgeClass("maintenance.priority", p.priority)}`}>
                        {codeLabel("maintenance.priority", p.priority)}
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

function CalendarSection() {
  const { data, error } = useQuery({ queryKey: ["annual-calendar"], queryFn: getAnnualCalendar, retry: false });
  const KIND: Record<string, string> = { maintenance: "Mantenimiento", checklist: "Revisión", lab: "Laboratorio" };
  const pctColor = (p: number | null) => (p === null ? "text-slate-400" : p >= 90 ? "text-emerald-700" : p >= 60 ? "text-amber-700" : "text-red-700");
  return (
    <>
      <h2 className="text-sm font-semibold text-slate-500 uppercase tracking-wide mb-2">Calendario anual de mantenimiento, control y calidad{formSuffix("annual_calendar")}</h2>
      <p className="mb-3 max-w-3xl text-sm text-slate-600">
        Reúne lo ya programado: planes de mantenimiento, revisiones con frecuencia y análisis de laboratorio. La directiva y el operador revisan cada mes el cumplimiento. Las revisiones extraordinarias por lluvias o quejas se cuentan aparte.
      </p>
      {error && <p className="text-sm text-amber-800">{error instanceof ApiError ? error.message : "No se pudo cargar el calendario."}</p>}
      {data && (
        <>
          <div className="mb-3 flex flex-wrap gap-3 text-sm">
            <span className="rounded-xl border border-slate-200 bg-white px-4 py-2">
              <strong className={`text-xl ${pctColor(data.summary.compliance_pct)}`}>{data.summary.compliance_pct === null ? "—" : `${data.summary.compliance_pct}%`}</strong>
              <span className="ml-2 text-slate-600">cumplimiento {data.year} ({data.summary.done} de {data.summary.expected})</span>
            </span>
            <span className={`rounded-xl border px-4 py-2 ${data.summary.overdue ? "border-red-200 bg-red-50 text-red-800" : "border-slate-200 bg-white text-slate-600"}`}>
              {data.summary.overdue} actividad{data.summary.overdue === 1 ? "" : "es"} vencida{data.summary.overdue === 1 ? "" : "s"}
            </span>
          </div>
          {data.items.length === 0 && <EmptyState message="Todavía no hay actividades programadas." />}
          {data.items.length > 0 && (
            <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white">
              <table className="w-full text-sm">
                <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
                  <tr>
                    <th className="px-4 py-3">Actividad</th>
                    <th className="px-4 py-3">Frecuencia</th>
                    <th className="px-4 py-3">Responsable</th>
                    <th className="px-4 py-3">En el año</th>
                    <th className="px-4 py-3">Cumplimiento</th>
                    <th className="px-4 py-3">Próxima</th>
                  </tr>
                </thead>
                <tbody>
                  {data.items.map((i) => (
                    <tr key={`${i.kind}-${i.ref}`} className={`border-t border-slate-100 ${i.overdue ? "bg-red-50/40" : ""}`}>
                      <td className="px-4 py-3 text-slate-800">
                        <span className="mr-2 rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-semibold text-slate-600">{KIND[i.kind]}</span>
                        {i.activity}
                        {i.extraordinary > 0 && <span className="block text-[11px] text-indigo-700">+ {i.extraordinary} extraordinaria(s) por evento ({i.extraordinary_done} cumplidas)</span>}
                        {i.not_generated > 0 && <span className="block text-[11px] text-red-700">{i.not_generated} vencida(s) sin orden generada</span>}
                      </td>
                      <td className="px-4 py-3 text-slate-600">cada {i.frequency_days} días</td>
                      <td className="px-4 py-3 text-slate-600">{i.responsible ?? "—"}</td>
                      <td className="px-4 py-3 tabular-nums text-slate-700">{i.done} de {i.expected}</td>
                      <td className={`px-4 py-3 font-semibold tabular-nums ${pctColor(i.compliance_pct)}`}>{i.compliance_pct === null ? "—" : `${i.compliance_pct}%`}</td>
                      <td className="px-4 py-3 text-slate-600">
                        {i.next_due_at ? new Date(i.next_due_at).toLocaleDateString(appLocale()) : "—"}
                        {i.overdue && <span className="ml-2 rounded-full bg-red-100 px-2 py-0.5 text-[10px] font-semibold text-red-700">vencida</span>}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </>
  );
}

function EventsSection() {
  const queryClient = useQueryClient();
  const { data: catalog } = useQuery({ queryKey: ["maintenance-community-catalog"], queryFn: getMaintenanceCommunityCatalog });
  const { data: events } = useQuery({ queryKey: ["maintenance-events"], queryFn: getMaintenanceEvents });
  const [code, setCode] = useState("");
  const [notes, setNotes] = useState("");
  const [msg, setMsg] = useState<string | null>(null);
  const mutation = useMutation({
    mutationFn: () => recordMaintenanceEvent({ event_type_code: code, notes: notes || null }),
    onSuccess: (r) => {
      setNotes("");
      setMsg(r.orders.length ? `${r.label}: ${r.orders.length} orden(es) de revisión extraordinaria generada(s).` : `${r.label} registrado. Ningún plan espera este evento.`);
      for (const k of ["maintenance-events", "maintenance-orders", "maintenance-kpis"]) queryClient.invalidateQueries({ queryKey: [k] });
    },
    onError: (err) => setMsg(err instanceof ApiError ? err.message : "No se pudo registrar el evento."),
  });
  return (
    <>
      <h2 className="text-sm font-semibold text-slate-500 uppercase tracking-wide mb-2">Eventos que piden revisión</h2>
      <p className="mb-3 max-w-3xl text-sm text-slate-600">
        La guía pide revisar captación, conducción y red no solo por calendario sino también después de lluvias fuertes, movimientos de tierra o quejas. Al registrar el evento se genera una orden por cada plan que lo espera.
      </p>
      <div className="mb-3 flex flex-wrap items-end gap-2 rounded-xl border border-slate-200 bg-white p-4">
        <select aria-label="Evento" className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm bg-white" value={code} onChange={(e) => setCode(e.target.value)}>
          <option value="">— ¿Qué pasó? —</option>
          {(catalog?.event_types ?? []).map((e) => <option key={e.code} value={e.code}>{e.label}</option>)}
        </select>
        <input aria-label="Detalle" className="min-w-[14rem] flex-1 rounded-lg border border-slate-300 px-3 py-1.5 text-sm" placeholder="Detalle (dónde, cuánto duró, qué se vio)" value={notes} onChange={(e) => setNotes(e.target.value)} />
        <button onClick={() => mutation.mutate()} disabled={!code || mutation.isPending} className="rounded-lg bg-indigo-600 text-white text-xs font-semibold px-3 py-2 hover:bg-indigo-700 disabled:opacity-40">
          Registrar evento
        </button>
        {msg && <p className="w-full text-sm text-slate-700">{msg}</p>}
      </div>
      {events && events.length === 0 && <EmptyState message="Sin eventos registrados." />}
      <ul className="divide-y divide-slate-100 rounded-xl border border-slate-200 bg-white">
        {(events ?? []).map((e) => (
          <li key={e.event_id} className="px-4 py-2 text-sm text-slate-700">
            <strong>{e.label}</strong> · {new Date(e.occurred_at).toLocaleString(appLocale())} · {e.orders_generated} orden(es)
            {e.notes && <span className="block text-xs text-slate-500">{e.notes}</span>}
          </li>
        ))}
      </ul>
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
        {kpis?.community && (
          <div className="mt-4 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="rounded-xl border border-emerald-200 bg-emerald-50/40 p-4">
              <div className="text-2xl font-bold text-emerald-800">{kpis.community.mingas}</div>
              <div className="text-xs text-slate-600 mt-1">{term("community_work", { plural: true, capital: true })} en {kpis.community.year}</div>
            </div>
            <div className="rounded-xl border border-emerald-200 bg-emerald-50/40 p-4">
              <div className="text-2xl font-bold text-emerald-800">{kpis.community.participants}</div>
              <div className="text-xs text-slate-600 mt-1">Personas que participaron</div>
            </div>
            <div className="rounded-xl border border-emerald-200 bg-emerald-50/40 p-4">
              <div className="text-2xl font-bold text-emerald-800">{kpis.community.volunteer_hours.toLocaleString(appLocale())} h</div>
              <div className="text-xs text-slate-600 mt-1">Horas donadas por la comunidad</div>
            </div>
            <div className="rounded-xl border border-slate-200 bg-white p-4">
              <div className="text-2xl font-bold text-slate-900">{kpis.community.all_steps_pct === null ? "—" : `${kpis.community.all_steps_pct}%`}</div>
              <div className="text-xs text-slate-500 mt-1">Cierres con los 5 pasos</div>
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

      <div id="pm-plans" className="scroll-mt-24 mb-8">
        <PmPlansSection />
      </div>

      <div id="events" className="scroll-mt-24 mb-8">
        <EventsSection />
      </div>

      <div id="calendar" className="scroll-mt-24">
        <CalendarSection />
      </div>
    </StagePage>
  );
}
