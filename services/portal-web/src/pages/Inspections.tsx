import { useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ApiError,
  getChecklistRun,
  getChecklistRuns,
  getChecklistTemplates,
  getProcessRoute,
  submitChecklistRun,
  type ChecklistAnswerInput,
  type ChecklistTemplate,
  type RouteList,
  type RouteStageInfo,
  type ScaleEntry,
} from "../api";
import { StagePage, EmptyState } from "../components/StagePage";

// Ruta y revisiones -- rediseno de usabilidad (2026-10-05, a pedido del
// usuario: "un usuario no logra percibir que debe hacer click" y "la vision
// de proceso no es claramente visible").
//
// 1. La pagina abre en la RUTA del programa: las etapas en orden (catalogo
//    `process_stage` del paquete, 0023), cada una con sus listas y el estado
//    de cada lista (sin aplicar / al dia / vencida / aplicada). Responde "en
//    que etapa estamos y que toca hacer ahora".
// 2. Cada lista es una tarjeta con UN boton principal explicito ("Aplicar
//    revision") -- nada depende de adivinar que un texto es clicable.
// 3. El formulario usa botones de respuesta grandes con color e icono, avisa
//    cuando una respuesta genera un hallazgo, y tiene una barra fija con el
//    progreso, "ir al siguiente sin responder" y Guardar.
// 4. El historial muestra puntaje y hallazgos y cada fila dice "Ver detalle".
// Nada de esto depende de un pais: etapas, listas, escalas y frecuencias
// vienen del paquete adoptado.

const KIND_LABEL: Record<ChecklistTemplate["kind"], string> = {
  traffic_light: "Semáforo",
  inspection: "Inspección",
  self_assessment: "Autoevaluación",
};

const STATUS_STYLE: Record<RouteList["status"], { label: string; pill: string; dot: string }> = {
  never: { label: "Sin aplicar", pill: "bg-slate-100 text-slate-700", dot: "bg-slate-400" },
  done: { label: "Aplicada", pill: "bg-emerald-50 text-emerald-700", dot: "bg-emerald-500" },
  ok: { label: "Al día", pill: "bg-emerald-50 text-emerald-700", dot: "bg-emerald-500" },
  overdue: { label: "Vencida", pill: "bg-red-50 text-red-700", dot: "bg-red-500" },
};

function formatDate(iso: string | null): string {
  return iso ? new Date(iso).toLocaleDateString("es", { day: "numeric", month: "short", year: "numeric" }) : "—";
}

function dueText(item: RouteList): string {
  if (item.status === "never") return item.frequency_days ? `Se aplica cada ${item.frequency_days} días` : "Se aplica cuando corresponda";
  if (item.status === "done") return "Se aplica cuando corresponda";
  if (item.days_to_due === null) return "";
  if (item.status === "overdue") return `Vencida hace ${Math.abs(item.days_to_due)} día${Math.abs(item.days_to_due) === 1 ? "" : "s"}`;
  return item.days_to_due === 0 ? "Toca hoy" : `Próxima en ${item.days_to_due} día${item.days_to_due === 1 ? "" : "s"}`;
}

/** Tono de una respuesta segun su lugar en la escala del paquete (mejor -> verde, peor -> rojo). */
function answerTone(scale: ScaleEntry[], entry: ScaleEntry) {
  const scores = scale.map((s) => s.score);
  const max = Math.max(...scores);
  const min = Math.min(...scores);
  if (entry.score === max) return { icon: "✓", idle: "border-emerald-300 text-emerald-800 hover:bg-emerald-50", active: "bg-emerald-600 border-emerald-600 text-white" };
  if (entry.score === min) return { icon: "✕", idle: "border-red-300 text-red-800 hover:bg-red-50", active: "bg-red-600 border-red-600 text-white" };
  return { icon: "~", idle: "border-amber-300 text-amber-800 hover:bg-amber-50", active: "bg-amber-500 border-amber-500 text-white" };
}

// ── Ruta ──────────────────────────────────────────────────────────────

function stageTone(stage: RouteStageInfo): string {
  if (stage.summary.overdue > 0) return "bg-red-500 text-white";
  if (stage.summary.total > 0 && stage.summary.applied === stage.summary.total) return "bg-emerald-600 text-white";
  if (stage.summary.applied > 0) return "bg-indigo-600 text-white";
  return "bg-slate-200 text-slate-700";
}

function RouteStepper({ stages, selected, onSelect }: { stages: RouteStageInfo[]; selected: string; onSelect: (code: string) => void }) {
  return (
    <nav aria-label="Etapas de la ruta" className="overflow-x-auto pb-1">
      <ol className="flex min-w-max items-stretch gap-2">
        {stages.map((s, i) => {
          const active = s.code === selected;
          return (
            <li key={s.code} className="flex items-center gap-2">
              <button
                onClick={() => onSelect(s.code)}
                aria-current={active ? "step" : undefined}
                className={`group flex w-44 items-start gap-3 rounded-xl border px-3 py-2.5 text-left transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 ${
                  active ? "border-indigo-600 bg-indigo-50 shadow-sm" : "border-slate-200 bg-white hover:border-indigo-300 hover:bg-slate-50"
                }`}
              >
                <span className={`mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-xs font-bold ${stageTone(s)}`}>{s.order}</span>
                <span className="min-w-0">
                  <span className={`block text-sm font-semibold leading-tight ${active ? "text-indigo-900" : "text-slate-800"}`}>{s.title}</span>
                  <span className="mt-1 block text-[11px] text-slate-500">
                    {s.summary.total === 0 ? "Sin listas todavía" : `${s.summary.applied} de ${s.summary.total} aplicadas`}
                    {s.summary.overdue > 0 && <span className="ml-1 font-semibold text-red-600">· {s.summary.overdue} vencida{s.summary.overdue === 1 ? "" : "s"}</span>}
                  </span>
                </span>
              </button>
              {i < stages.length - 1 && <span aria-hidden className="text-slate-300">›</span>}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}

function ListCard({ item, onApply, onViewLast }: { item: RouteList; onApply: () => void; onViewLast: () => void }) {
  const st = STATUS_STYLE[item.status];
  return (
    <article className={`flex flex-col rounded-xl border bg-white p-4 ${item.status === "overdue" ? "border-red-200" : "border-slate-200"}`}>
      <div className="flex items-start justify-between gap-2">
        <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[11px] font-medium text-slate-600">{KIND_LABEL[item.kind]}</span>
        <span className={`inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-[11px] font-semibold ${st.pill}`}>
          <span className={`h-1.5 w-1.5 rounded-full ${st.dot}`} />{st.label}
        </span>
      </div>
      <h3 className="mt-2 text-sm font-semibold text-slate-900">{item.title}</h3>
      <p className="mt-1 text-xs text-slate-500 line-clamp-2">{item.purpose}</p>
      <dl className="mt-3 grid grid-cols-2 gap-x-3 gap-y-1 text-xs">
        <dt className="text-slate-500">Última</dt>
        <dd className="text-slate-800 tabular-nums">{formatDate(item.last_run_at)}</dd>
        <dt className="text-slate-500">Frecuencia</dt>
        <dd className={`tabular-nums ${item.status === "overdue" ? "font-semibold text-red-700" : "text-slate-800"}`}>{dueText(item)}</dd>
        <dt className="text-slate-500">Ítems</dt>
        <dd className="text-slate-800 tabular-nums">{item.item_count}</dd>
      </dl>
      <div className="mt-4 flex flex-wrap gap-2 pt-1">
        <button
          onClick={onApply}
          className="rounded-lg bg-indigo-600 px-3 py-1.5 text-sm font-semibold text-white hover:bg-indigo-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 focus-visible:ring-offset-1"
        >
          {item.status === "never" ? "Aplicar revisión" : "Aplicar de nuevo"}
        </button>
        {item.last_run_id && (
          <button onClick={onViewLast} className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50">
            Ver la última ›
          </button>
        )}
      </div>
    </article>
  );
}

function StagePanel({ stage, onApply, onView }: { stage: RouteStageInfo; onApply: (id: string) => void; onView: (runId: string) => void }) {
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-5">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="text-base font-semibold text-slate-900">
          Etapa {stage.order} · {stage.title}
        </h2>
        <span className="text-xs text-slate-500">{stage.source_ref}</span>
      </div>
      <p className="mt-1 max-w-3xl text-sm text-slate-600">{stage.purpose}</p>
      <div className="mt-3 flex flex-wrap gap-1.5" aria-label="Productos de la etapa">
        {stage.products.map((p) => (
          <span key={p} className="rounded-full border border-slate-200 px-2.5 py-0.5 text-[11px] text-slate-600">{p}</span>
        ))}
      </div>
      {stage.lists.length === 0 ? (
        <div className="mt-4 rounded-lg border border-dashed border-slate-300 bg-slate-50 p-4 text-sm text-slate-600">
          Esta etapa todavía no tiene listas de revisión en la plataforma. Arriba están los productos que pide la guía; se irán incorporando.
        </div>
      ) : (
        <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {stage.lists.map((item) => (
            <ListCard key={item.template_id} item={item} onApply={() => onApply(item.template_id)} onViewLast={() => item.last_run_id && onView(item.last_run_id)} />
          ))}
        </div>
      )}
    </section>
  );
}

// ── Formulario ────────────────────────────────────────────────────────

type Draft = Record<string, ChecklistAnswerInput>;

function RunForm({ template, onCancel, onDone }: { template: ChecklistTemplate; onCancel: () => void; onDone: (message: string) => void }) {
  const queryClient = useQueryClient();
  const [draft, setDraft] = useState<Draft>({});
  const [notes, setNotes] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [showMissing, setShowMissing] = useState(false);
  const itemRefs = useRef<Record<string, HTMLLIElement | null>>({});
  const scale = useMemo(() => Object.fromEntries(template.scale.map((s) => [s.code, s])), [template]);
  const missing = template.items.filter((i) => !draft[i.key]?.answer_code);
  const answered = template.items.length - missing.length;
  const pct = Math.round((100 * answered) / template.items.length);

  const update = (key: string, patch: Partial<ChecklistAnswerInput>) =>
    setDraft((d) => ({ ...d, [key]: { ...d[key], item_key: key, answer_code: d[key]?.answer_code ?? "", ...patch } }));

  const goToFirstMissing = () => {
    setShowMissing(true);
    const first = missing[0];
    if (first) itemRefs.current[first.key]?.scrollIntoView({ behavior: "smooth", block: "center" });
  };

  const mutation = useMutation({
    mutationFn: () => submitChecklistRun({
      template_id: template.id,
      answers: template.items.map((i) => {
        const a = draft[i.key];
        return {
          item_key: i.key, answer_code: a.answer_code,
          observation: a.observation || null, action: a.action || null,
          responsible: a.responsible || null, due_date: a.due_date || null,
        };
      }),
      notes: notes || null,
    }),
    onSuccess: (result) => {
      for (const key of ["checklist-runs", "traffic-light", "findings", "process-route"]) {
        queryClient.invalidateQueries({ queryKey: [key] });
      }
      const created = result.findings_created.length;
      onDone(`Revisión "${template.title}" guardada. Puntaje ${result.score.score} de ${result.score.max_score}. ${created === 0 ? "Sin hallazgos nuevos." : `${created} hallazgo${created === 1 ? "" : "s"} nuevo${created === 1 ? "" : "s"} en Mi sistema → Hallazgos.`}`);
    },
    onError: (err) => setError(err instanceof ApiError ? err.message : "No se pudo guardar la revisión."),
  });

  return (
    <section className="rounded-xl border border-slate-200 bg-white">
      <div className="border-b border-slate-200 p-5">
        <button onClick={onCancel} className="mb-2 text-sm font-medium text-indigo-700 hover:underline">← Volver a la ruta</button>
        <div className="flex flex-wrap items-center gap-2">
          <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[11px] font-medium text-slate-600">{KIND_LABEL[template.kind]}</span>
          <h2 className="text-base font-semibold text-slate-900">{template.title}</h2>
        </div>
        <p className="mt-1 max-w-3xl text-sm text-slate-600">{template.purpose}</p>
        <p className="mt-2 text-xs text-slate-500">
          Responda cada ítem tocando una opción. Si la respuesta indica un problema, se abre un recuadro para anotar qué se hará: esa información queda como hallazgo en <strong>Mi sistema</strong>.
        </p>
      </div>

      <ol className="divide-y divide-slate-100">
        {template.items.map((item, idx) => {
          const current = draft[item.key];
          const entry = current?.answer_code ? scale[current.answer_code] : undefined;
          const isMissing = showMissing && !entry;
          return (
            <li key={item.key} ref={(el) => { itemRefs.current[item.key] = el; }} className={`p-5 ${isMissing ? "bg-amber-50" : ""}`}>
              <fieldset>
                <legend className="flex gap-3 text-sm text-slate-900">
                  <span className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-[11px] font-bold ${entry ? "bg-indigo-600 text-white" : "bg-slate-200 text-slate-600"}`}>{idx + 1}</span>
                  <span className="pt-0.5">{item.text}</span>
                </legend>
                <div className="mt-3 flex flex-wrap gap-2 pl-9" role="radiogroup">
                  {template.scale.map((s) => {
                    const id = `${template.id}-${item.key}-${s.code}`;
                    const selected = current?.answer_code === s.code;
                    const tone = answerTone(template.scale, s);
                    return (
                      <label
                        key={s.code}
                        htmlFor={id}
                        className={`inline-flex min-w-[7rem] cursor-pointer items-center justify-center gap-2 rounded-lg border-2 px-4 py-2 text-sm font-semibold shadow-sm transition-colors has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-indigo-500 ${selected ? tone.active : `bg-white ${tone.idle}`}`}
                      >
                        <input id={id} type="radio" className="sr-only" name={`${template.id}-${item.key}`} checked={selected} onChange={() => update(item.key, { answer_code: s.code })} />
                        <span aria-hidden>{tone.icon}</span>{s.label}
                      </label>
                    );
                  })}
                </div>
                {isMissing && <p className="mt-2 pl-9 text-xs font-semibold text-amber-800">Falta responder este ítem.</p>}
                {entry?.finding && (
                  <div className="mt-3 ml-9 rounded-lg border border-amber-200 bg-amber-50 p-3">
                    <p className="mb-2 text-xs font-semibold text-amber-900">
                      Esta respuesta genera un hallazgo{entry.finding_priority ? ` de prioridad ${entry.finding_priority === "high" ? "alta" : entry.finding_priority === "medium" ? "media" : "baja"}` : ""}. Anote qué se acordó (opcional, pero ayuda al seguimiento):
                    </p>
                    <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-4">
                      <input aria-label="Qué se observó" className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm" placeholder="Qué se observó" value={current?.observation ?? ""} onChange={(e) => update(item.key, { observation: e.target.value })} />
                      <input aria-label="Acción acordada" className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm" placeholder="Acción acordada" value={current?.action ?? ""} onChange={(e) => update(item.key, { action: e.target.value })} />
                      <input aria-label="Responsable" className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm" placeholder="Responsable" value={current?.responsible ?? ""} onChange={(e) => update(item.key, { responsible: e.target.value })} />
                      <input aria-label="Fecha límite" type="date" className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm" value={current?.due_date ?? ""} onChange={(e) => update(item.key, { due_date: e.target.value })} />
                    </div>
                  </div>
                )}
              </fieldset>
            </li>
          );
        })}
      </ol>

      <div className="border-t border-slate-200 p-5">
        <label htmlFor={`${template.id}-notes`} className="mb-1 block text-xs font-medium text-slate-500">Notas de la revisión (opcional)</label>
        <textarea id={`${template.id}-notes`} rows={2} className="w-full rounded-lg border border-slate-300 px-3 py-1.5 text-sm" value={notes} onChange={(e) => setNotes(e.target.value)} />
        {error && <p className="mt-2 text-sm text-red-600">{error}</p>}
      </div>

      <div className="sticky bottom-0 z-20 flex flex-wrap items-center gap-3 rounded-b-xl border-t border-slate-200 bg-white/95 px-5 py-3 backdrop-blur">
        <div className="min-w-[10rem] flex-1">
          <div className="flex justify-between text-xs text-slate-600 tabular-nums">
            <span>{answered} de {template.items.length} respondidos</span><span>{pct}%</span>
          </div>
          <div className="mt-1 h-2 overflow-hidden rounded-full bg-slate-200" role="progressbar" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100}>
            <div className="h-full rounded-full bg-indigo-600 transition-all" style={{ width: `${pct}%` }} />
          </div>
        </div>
        {missing.length > 0 && (
          <button onClick={goToFirstMissing} className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50">
            Ir al siguiente sin responder
          </button>
        )}
        <button onClick={onCancel} className="px-2 text-sm text-slate-500 hover:text-slate-700">Cancelar</button>
        <button
          onClick={() => (missing.length > 0 ? goToFirstMissing() : mutation.mutate())}
          disabled={mutation.isPending}
          className={`rounded-lg px-4 py-2 text-sm font-semibold text-white ${missing.length > 0 ? "bg-indigo-300 cursor-help" : "bg-indigo-600 hover:bg-indigo-700"}`}
          title={missing.length > 0 ? `Faltan ${missing.length} ítems por responder` : "Guardar la revisión"}
        >
          {mutation.isPending ? "Guardando…" : missing.length > 0 ? `Faltan ${missing.length}` : "Guardar revisión"}
        </button>
      </div>
    </section>
  );
}

// ── Detalle e historial ───────────────────────────────────────────────

function RunDetail({ runId, onClose }: { runId: string; onClose: () => void }) {
  const { data } = useQuery({ queryKey: ["checklist-run", runId], queryFn: () => getChecklistRun(runId) });
  return (
    <section className="rounded-xl border border-indigo-200 bg-white p-5">
      <button onClick={onClose} className="mb-2 text-sm font-medium text-indigo-700 hover:underline">← Volver a la ruta</button>
      {!data ? <p className="text-sm text-slate-500">Cargando…</p> : (
        <>
          <h2 className="text-base font-semibold text-slate-900">{data.title}</h2>
          <p className="mb-3 text-xs text-slate-500">
            {new Date(data.performed_at).toLocaleString("es")} · {data.performed_by.replace(/^portal:/, "")} · puntaje {data.score.score} de {data.score.max_score}
          </p>
          {data.notes && <p className="mb-3 text-sm text-slate-600">{data.notes}</p>}
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-200 text-left text-xs uppercase tracking-wide text-slate-500">
                  <th className="py-2 pr-3 font-semibold">Ítem</th>
                  <th className="py-2 pr-3 font-semibold">Respuesta</th>
                  <th className="py-2 font-semibold">Acción acordada</th>
                </tr>
              </thead>
              <tbody>
                {data.answers.map((a) => (
                  <tr key={a.item_key} className="border-b border-slate-100 align-top last:border-0">
                    <td className="py-2 pr-3 text-slate-700">{a.text}</td>
                    <td className="whitespace-nowrap py-2 pr-3 font-medium">{a.answer_label}</td>
                    <td className="py-2 text-slate-600">{[a.observation, a.action, a.responsible, a.due_date].filter(Boolean).join(" · ") || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </section>
  );
}

function History({ titles, onView }: { titles: Record<string, string>; onView: (runId: string) => void }) {
  const { data } = useQuery({ queryKey: ["checklist-runs"], queryFn: () => getChecklistRuns() });
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-5">
      <h2 className="mb-1 text-base font-semibold text-slate-900">Historial de revisiones</h2>
      <p className="mb-3 text-xs text-slate-500">Toque una revisión para ver sus respuestas.</p>
      {data && data.length === 0 && <EmptyState message="Todavía no se hizo ninguna revisión." />}
      <ul className="divide-y divide-slate-100">
        {(data ?? []).map((r) => (
          <li key={r.run_id}>
            <button
              onClick={() => onView(r.run_id)}
              className="group flex w-full flex-wrap items-center gap-x-4 gap-y-1 rounded-lg px-2 py-2.5 text-left hover:bg-slate-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500"
            >
              <span className="min-w-0 flex-1 text-sm font-medium text-slate-800">{titles[r.template_id] ?? r.template_id}</span>
              <span className="text-xs text-slate-500 tabular-nums">{new Date(r.performed_at).toLocaleDateString("es")}</span>
              {r.score && <span className="rounded-full bg-indigo-50 px-2 py-0.5 text-[11px] font-semibold text-indigo-700 tabular-nums">{r.score.score}/{r.score.max_score}</span>}
              <span className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ${r.findings_count ? "bg-amber-50 text-amber-800" : "bg-slate-100 text-slate-600"}`}>
                {r.findings_count} hallazgo{r.findings_count === 1 ? "" : "s"}
              </span>
              <span className="text-sm font-medium text-indigo-700 group-hover:underline">Ver detalle ›</span>
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}

// ── Pagina ────────────────────────────────────────────────────────────

type View = { mode: "route" } | { mode: "apply"; templateId: string } | { mode: "detail"; runId: string };

function defaultStage(stages: RouteStageInfo[]): string | undefined {
  return (
    stages.find((s) => s.summary.overdue > 0)?.code
    ?? stages.find((s) => s.summary.never > 0)?.code
    ?? stages.find((s) => s.summary.total > 0)?.code
    ?? stages[0]?.code
  );
}

export function InspectionsPage() {
  const { data: route, isLoading } = useQuery({ queryKey: ["process-route"], queryFn: getProcessRoute });
  const { data: templates } = useQuery({ queryKey: ["checklist-templates"], queryFn: getChecklistTemplates });
  const [chosenStage, setStageCode] = useState<string | undefined>();
  const [view, setView] = useState<View>({ mode: "route" });
  const [message, setMessage] = useState<string | null>(null);
  // Sin eleccion del usuario, la etapa que mas pide atencion (vencida, luego sin aplicar).
  const stageCode = chosenStage ?? (route ? defaultStage(route.stages) : undefined);

  useEffect(() => { window.scrollTo({ top: 0 }); }, [view]);

  const titles = Object.fromEntries((templates ?? []).map((t) => [t.id, t.title]));
  const stage = route?.stages.find((s) => s.code === stageCode);
  const template = view.mode === "apply" ? templates?.find((t) => t.id === view.templateId) : undefined;
  const totals = route?.stages.reduce((acc, s) => ({ applied: acc.applied + s.summary.applied, total: acc.total + s.summary.total, overdue: acc.overdue + s.summary.overdue }), { applied: 0, total: 0, overdue: 0 });

  return (
    <StagePage title="Ruta y revisiones">
      {isLoading && <p className="text-sm text-slate-500">Cargando…</p>}
      {route && route.stages.length === 0 && route.other_lists.length === 0 && (
        <EmptyState message="No hay listas disponibles. Active el paquete de su programa en Configuración → Paquetes." />
      )}
      {message && (
        <div role="status" className="mb-4 flex items-start justify-between gap-3 rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-2.5 text-sm text-emerald-800">
          <span>{message}</span>
          <button onClick={() => setMessage(null)} aria-label="Cerrar aviso" className="text-emerald-700 hover:text-emerald-900">✕</button>
        </div>
      )}

      {view.mode === "route" && route && route.stages.length > 0 && (
        <div className="space-y-5">
          <div className="flex flex-wrap items-end justify-between gap-2">
            <p className="max-w-3xl text-sm text-slate-600">
              La ruta del programa en orden. Elija una etapa para ver sus revisiones y aplicar la que corresponda. Las etapas con revisiones vencidas se marcan en rojo.
            </p>
            {totals && totals.total > 0 && (
              <span className="text-xs text-slate-600 tabular-nums">
                {totals.applied} de {totals.total} revisiones aplicadas{totals.overdue > 0 && <span className="font-semibold text-red-600"> · {totals.overdue} vencida{totals.overdue === 1 ? "" : "s"}</span>}
              </span>
            )}
          </div>
          {stageCode && <RouteStepper stages={route.stages} selected={stageCode} onSelect={setStageCode} />}
          {stage && (
            <StagePanel
              stage={stage}
              onApply={(id) => { setMessage(null); setView({ mode: "apply", templateId: id }); }}
              onView={(runId) => setView({ mode: "detail", runId })}
            />
          )}
          {route.other_lists.length > 0 && (
            <section className="rounded-xl border border-slate-200 bg-white p-5">
              <h2 className="mb-3 text-base font-semibold text-slate-900">Otras revisiones</h2>
              <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
                {route.other_lists.map((item) => (
                  <ListCard key={item.template_id} item={item} onApply={() => setView({ mode: "apply", templateId: item.template_id })} onViewLast={() => item.last_run_id && setView({ mode: "detail", runId: item.last_run_id })} />
                ))}
              </div>
            </section>
          )}
          <History titles={titles} onView={(runId) => setView({ mode: "detail", runId })} />
        </div>
      )}

      {view.mode === "apply" && template && (
        <RunForm
          key={template.id}
          template={template}
          onCancel={() => setView({ mode: "route" })}
          onDone={(m) => { setMessage(m); setView({ mode: "route" }); }}
        />
      )}
      {view.mode === "detail" && <RunDetail runId={view.runId} onClose={() => setView({ mode: "route" })} />}
    </StagePage>
  );
}
