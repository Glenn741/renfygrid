import { useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ApiError,
  addFollowUpItem,
  createFollowUpCycle,
  getFollowUp,
  reviewFollowUpMilestone,
  updateFollowUpItem,
  type FollowUpItem,
  type FollowUpItemStatus,
  type FollowUpMilestone,
} from "../api";
import { appLocale, isoDay } from "../catalog";

// Seguimiento a 7, 30 y 90 dias (Guia 7, T-09 y seccion 11; migracion 0028).
// Los momentos, que revisar y que evidencia pedir salen del catalogo del
// paquete del programa; la junta abre un ciclo con la fecha de cierre de la
// formacion, acuerda compromisos y registra la revision de cada momento.
// "Hoy" es la fecha en la zona horaria de la organizacion (0029).

export const FOLLOW_UP_QUERY_KEY = ["follow-up"] as const;

const ITEM_STATUS: Record<FollowUpItemStatus, { label: string; active: string }> = {
  pending: { label: "Pendiente", active: "bg-slate-600 border-slate-600 text-white" },
  done: { label: "Cumplido", active: "bg-emerald-600 border-emerald-600 text-white" },
  not_done: { label: "No cumplido", active: "bg-red-600 border-red-600 text-white" },
};

function errText(err: unknown, fallback: string): string {
  return err instanceof ApiError ? err.message : fallback;
}

function formatDay(iso: string): string {
  return new Date(`${iso}T12:00:00`).toLocaleDateString(appLocale(), { day: "numeric", month: "short", year: "numeric" });
}

function milestoneBadge(m: FollowUpMilestone): { text: string; cls: string } {
  if (m.status === "reviewed") return { text: `Revisado el ${formatDay(m.review!.reviewed_on)}`, cls: "bg-emerald-50 text-emerald-700" };
  if (m.status === "due") {
    const late = -m.days_to_due;
    return { text: late === 0 ? "Toca revisar hoy" : `Toca revisar · venció hace ${late} día${late === 1 ? "" : "s"}`, cls: "bg-red-50 text-red-700" };
  }
  return { text: `Faltan ${m.days_to_due} día${m.days_to_due === 1 ? "" : "s"}`, cls: "bg-slate-100 text-slate-700" };
}

function ItemRow({ item }: { item: FollowUpItem }) {
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [situation, setSituation] = useState(item.situation ?? "");
  const [evidence, setEvidence] = useState(item.evidence ?? "");
  const [adjustment, setAdjustment] = useState(item.adjustment_action ?? "");
  const [error, setError] = useState<string | null>(null);
  const mutation = useMutation({
    mutationFn: (body: Parameters<typeof updateFollowUpItem>[1]) => updateFollowUpItem(item.item_id, body),
    onSuccess: () => { setError(null); setOpen(false); queryClient.invalidateQueries({ queryKey: FOLLOW_UP_QUERY_KEY }); },
    onError: (err) => setError(errText(err, "No se pudo guardar el compromiso.")),
  });
  return (
    <li className="py-2">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
        <span className="min-w-0 flex-1 text-sm text-slate-800">
          {item.commitment}
          <span className="block text-xs text-slate-500">
            {[item.responsible && `Responsable: ${item.responsible}`, item.due_date && `Fecha: ${formatDay(item.due_date)}`].filter(Boolean).join(" · ")}
          </span>
          {(item.situation || item.evidence || item.adjustment_action) && (
            <span className="block text-xs text-slate-600">
              {[item.situation && `Situación: ${item.situation}`, item.evidence && `Evidencia: ${item.evidence}`, item.adjustment_action && `Ajuste: ${item.adjustment_action}`].filter(Boolean).join(" · ")}
            </span>
          )}
        </span>
        <div role="radiogroup" aria-label="Estado del compromiso" className="flex gap-1">
          {(Object.keys(ITEM_STATUS) as FollowUpItemStatus[]).map((code) => (
            <button
              key={code}
              role="radio"
              aria-checked={item.status === code}
              onClick={() => item.status !== code && mutation.mutate({ status: code })}
              className={`rounded-lg border-2 px-2 py-0.5 text-xs font-semibold ${item.status === code ? ITEM_STATUS[code].active : "border-slate-300 bg-white text-slate-700 hover:bg-slate-50"}`}
            >
              {ITEM_STATUS[code].label}
            </button>
          ))}
        </div>
        <button onClick={() => setOpen((o) => !o)} className="text-xs font-medium text-indigo-700 hover:underline">
          {open ? "Cerrar" : "Anotar lo encontrado"}
        </button>
      </div>
      {open && (
        <div className="mt-2 grid gap-2 rounded-lg border border-slate-200 bg-slate-50 p-3 sm:grid-cols-3">
          <input aria-label="Situación encontrada" className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm" placeholder="Situación encontrada" value={situation} onChange={(e) => setSituation(e.target.value)} />
          <input aria-label="Evidencia" className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm" placeholder="Evidencia" value={evidence} onChange={(e) => setEvidence(e.target.value)} />
          <input aria-label="Acción de ajuste" className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm" placeholder="Acción de ajuste" value={adjustment} onChange={(e) => setAdjustment(e.target.value)} />
          <div className="sm:col-span-3">
            <button
              onClick={() => mutation.mutate({ situation: situation || null, evidence: evidence || null, adjustment_action: adjustment || null })}
              disabled={mutation.isPending}
              className="rounded-lg bg-indigo-600 px-3 py-1.5 text-sm font-semibold text-white hover:bg-indigo-700 disabled:opacity-50"
            >
              Guardar
            </button>
          </div>
        </div>
      )}
      {error && <p className="mt-1 text-sm text-red-600">{error}</p>}
    </li>
  );
}

function MilestoneCard({ cycleId, milestone, today }: { cycleId: string; milestone: FollowUpMilestone; today: string }) {
  const queryClient = useQueryClient();
  const [commitment, setCommitment] = useState("");
  const [responsible, setResponsible] = useState("");
  const [dueDate, setDueDate] = useState("");
  const [reviewOpen, setReviewOpen] = useState(false);
  const [reviewedOn, setReviewedOn] = useState(today);
  const [summary, setSummary] = useState(milestone.review?.summary ?? "");
  const [error, setError] = useState<string | null>(null);
  const refresh = () => queryClient.invalidateQueries({ queryKey: FOLLOW_UP_QUERY_KEY });

  const add = useMutation({
    mutationFn: () => addFollowUpItem(cycleId, { milestone_code: milestone.code, commitment, responsible: responsible || null, due_date: dueDate || null }),
    onSuccess: () => { setCommitment(""); setResponsible(""); setDueDate(""); setError(null); refresh(); },
    onError: (err) => setError(errText(err, "No se pudo agregar el compromiso.")),
  });
  const review = useMutation({
    mutationFn: () => reviewFollowUpMilestone(cycleId, milestone.code, { reviewed_on: reviewedOn, summary: summary || null }),
    onSuccess: () => { setReviewOpen(false); setError(null); refresh(); },
    onError: (err) => setError(errText(err, "No se pudo registrar la revisión.")),
  });
  const badge = milestoneBadge(milestone);

  return (
    <article className={`flex flex-col rounded-xl border p-4 ${milestone.status === "due" ? "border-red-200" : "border-slate-200"}`}>
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h4 className="text-sm font-semibold text-slate-900">{milestone.label} · {formatDay(milestone.due_date)}</h4>
        <span className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ${badge.cls}`}>{badge.text}</span>
      </div>
      <p className="mt-1 text-xs text-slate-600"><strong>Qué revisar:</strong> {milestone.review_guide}</p>
      <p className="text-xs text-slate-500"><strong>Evidencia:</strong> {milestone.evidence_guide}</p>
      {milestone.review?.summary && <p className="mt-2 rounded-lg bg-emerald-50 p-2 text-xs text-emerald-900">{milestone.review.summary}</p>}

      <h5 className="mt-3 text-xs font-semibold uppercase tracking-wide text-slate-500">
        Compromisos{milestone.items.length > 0 && ` · ${milestone.pending_items} pendiente${milestone.pending_items === 1 ? "" : "s"}`}
      </h5>
      {milestone.items.length === 0 && <p className="text-xs text-slate-500">Todavía no hay compromisos para este momento.</p>}
      <ul className="divide-y divide-slate-100">
        {milestone.items.map((i) => <ItemRow key={i.item_id} item={i} />)}
      </ul>
      <div className="mt-2 grid gap-2 sm:grid-cols-[1fr_10rem_9rem_auto]">
        <input aria-label="Nuevo compromiso" className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm" placeholder="Nuevo compromiso o producto a revisar" value={commitment} onChange={(e) => setCommitment(e.target.value)} />
        <input aria-label="Responsable" className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm" placeholder="Responsable" value={responsible} onChange={(e) => setResponsible(e.target.value)} />
        <input aria-label="Fecha" type="date" className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm" value={dueDate} onChange={(e) => setDueDate(e.target.value)} />
        <button onClick={() => add.mutate()} disabled={add.isPending || !commitment.trim()} className="rounded-lg border border-indigo-300 px-3 py-1.5 text-sm font-medium text-indigo-700 hover:bg-indigo-50 disabled:opacity-50">
          Agregar
        </button>
      </div>

      <div className="mt-3 border-t border-slate-100 pt-3">
        {!reviewOpen ? (
          <button
            onClick={() => setReviewOpen(true)}
            className={`rounded-lg px-3 py-1.5 text-sm font-semibold ${milestone.status === "reviewed" ? "border border-slate-300 text-slate-700 hover:bg-slate-50" : "bg-indigo-600 text-white hover:bg-indigo-700"}`}
          >
            {milestone.status === "reviewed" ? "Corregir la revisión" : "Registrar la revisión"}
          </button>
        ) : (
          <div className="grid gap-2 sm:grid-cols-[10rem_1fr_auto]">
            <input aria-label="Fecha de la revisión" type="date" className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm" value={reviewedOn} onChange={(e) => setReviewedOn(e.target.value)} />
            <input aria-label="Conclusión" className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm" placeholder="Qué se encontró y qué apoyos faltan" value={summary} onChange={(e) => setSummary(e.target.value)} />
            <div className="flex gap-2">
              <button onClick={() => review.mutate()} disabled={review.isPending || !reviewedOn} className="rounded-lg bg-indigo-600 px-3 py-1.5 text-sm font-semibold text-white hover:bg-indigo-700 disabled:opacity-50">Guardar</button>
              <button onClick={() => setReviewOpen(false)} className="px-2 text-sm text-slate-500 hover:text-slate-700">Cancelar</button>
            </div>
          </div>
        )}
      </div>
      {error && <p className="mt-2 text-sm text-red-600">{error}</p>}
    </article>
  );
}

function NewCycleForm({ programs, onCancel }: { programs: { pack_id: string; name: string }[]; onCancel?: () => void }) {
  const queryClient = useQueryClient();
  const [packId, setPackId] = useState(programs[0]?.pack_id ?? "");
  const [anchor, setAnchor] = useState("");
  const [title, setTitle] = useState("");
  const [error, setError] = useState<string | null>(null);
  const mutation = useMutation({
    mutationFn: () => createFollowUpCycle({ pack_id: packId, anchor_date: anchor, title }),
    onSuccess: () => { setError(null); queryClient.invalidateQueries({ queryKey: FOLLOW_UP_QUERY_KEY }); onCancel?.(); },
    onError: (err) => setError(errText(err, "No se pudo abrir el seguimiento.")),
  });
  return (
    <div className="rounded-lg border border-dashed border-slate-300 bg-slate-50 p-4">
      <p className="mb-2 text-sm text-slate-700">
        Abra el seguimiento con la fecha de cierre de la formación (el último día): desde ahí se cuentan los 7, 30 y 90 días.
      </p>
      <div className="grid gap-2 sm:grid-cols-[1fr_10rem_auto]">
        <input aria-label="Nombre" className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm" placeholder="Nombre (p. ej. Taller de capacitación 2026)" value={title} onChange={(e) => setTitle(e.target.value)} />
        <input aria-label="Fecha de cierre de la formación" type="date" className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm" value={anchor} onChange={(e) => setAnchor(e.target.value)} />
        <div className="flex gap-2">
          <button onClick={() => mutation.mutate()} disabled={mutation.isPending || !anchor || !title.trim() || !packId} className="rounded-lg bg-indigo-600 px-3 py-1.5 text-sm font-semibold text-white hover:bg-indigo-700 disabled:opacity-50">
            Abrir seguimiento
          </button>
          {onCancel && <button onClick={onCancel} className="px-2 text-sm text-slate-500 hover:text-slate-700">Cancelar</button>}
        </div>
      </div>
      {programs.length > 1 && (
        <select aria-label="Programa" className="mt-2 rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm" value={packId} onChange={(e) => setPackId(e.target.value)}>
          {programs.map((p) => <option key={p.pack_id} value={p.pack_id}>{p.name}</option>)}
        </select>
      )}
      {error && <p className="mt-2 text-sm text-red-600">{error}</p>}
    </div>
  );
}

export function FollowUpPanel() {
  const { data, error, isLoading } = useQuery({ queryKey: FOLLOW_UP_QUERY_KEY, queryFn: getFollowUp, retry: false });
  const [selected, setSelected] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  // "Hoy" del navegador solo como valor inicial del formulario de revision;
  // los vencimientos los calcula el servidor con la zona de la organizacion.
  const today = isoDay();

  const cycle = data?.cycles.find((c) => c.cycle_id === selected) ?? data?.cycles[0];

  return (
    <section className="mt-4 rounded-lg border border-slate-200 p-3">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h3 className="text-sm font-semibold text-slate-900">Seguimiento a 7, 30 y 90 días</h3>
        {data && data.cycles.length > 0 && !creating && (
          <div className="flex flex-wrap items-center gap-2">
            {data.cycles.length > 1 && (
              <select aria-label="Ciclo de seguimiento" className="rounded-lg border border-slate-300 px-2 py-1 text-xs" value={cycle?.cycle_id} onChange={(e) => setSelected(e.target.value)}>
                {data.cycles.map((c) => <option key={c.cycle_id} value={c.cycle_id}>{c.title} · cierre {formatDay(c.anchor_date)}</option>)}
              </select>
            )}
            <button onClick={() => setCreating(true)} className="text-xs font-medium text-indigo-700 hover:underline">Nuevo ciclo</button>
          </div>
        )}
      </div>
      {isLoading && <p className="text-sm text-slate-500">Cargando…</p>}
      {error && (
        <p className="mt-2 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
          {errText(error, "No se pudo cargar el seguimiento.")}{" "}
          {error instanceof ApiError && error.status === 409 && <Link to="/configuration#timezone" className="font-semibold underline">Ir a Configuración</Link>}
        </p>
      )}
      {data && data.programs.length === 0 && <p className="text-sm text-slate-500">Ningún paquete activo define seguimiento.</p>}
      {data && data.programs.length > 0 && (data.cycles.length === 0 || creating) && (
        <div className="mt-2"><NewCycleForm programs={data.programs} onCancel={creating ? () => setCreating(false) : undefined} /></div>
      )}
      {cycle && !creating && (
        <>
          <p className="mt-1 text-xs text-slate-500">{cycle.title} · cierre de la formación {formatDay(cycle.anchor_date)}</p>
          <div className="mt-3 grid gap-3 xl:grid-cols-3">
            {cycle.milestones.map((m) => <MilestoneCard key={`${cycle.cycle_id}-${m.code}`} cycleId={cycle.cycle_id} milestone={m} today={today} />)}
          </div>
        </>
      )}
    </section>
  );
}
