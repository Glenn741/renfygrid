import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ApiError,
  getChecklistRun,
  getChecklistRuns,
  getChecklistTemplates,
  submitChecklistRun,
  type ChecklistAnswerInput,
  type ChecklistTemplate,
} from "../api";
import { StagePage, EmptyState } from "../components/StagePage";

// Revisiones -- Track D, Sprint D0.3 (docs/04-plan-sprints.md SS11.4).
// Una sola pantalla para TODAS las listas de los paquetes adoptados
// (inspecciones, semaforo, autoevaluaciones): el motor no tiene una pantalla
// por formato. Si otro programa trae otras listas, aparecen aca solas.

const KIND_LABEL: Record<ChecklistTemplate["kind"], string> = {
  traffic_light: "Semáforo",
  inspection: "Inspecciones",
  self_assessment: "Autoevaluaciones",
};
const KIND_ORDER: ChecklistTemplate["kind"][] = ["traffic_light", "inspection", "self_assessment"];

type Draft = Record<string, ChecklistAnswerInput>;

function RunForm({ template, onDone }: { template: ChecklistTemplate; onDone: (message: string) => void }) {
  const queryClient = useQueryClient();
  const [draft, setDraft] = useState<Draft>({});
  const [notes, setNotes] = useState("");
  const [error, setError] = useState<string | null>(null);
  const scale = Object.fromEntries(template.scale.map((s) => [s.code, s]));
  const answered = template.items.filter((i) => draft[i.key]?.answer_code).length;

  const update = (key: string, patch: Partial<ChecklistAnswerInput>) =>
    setDraft((d) => ({ ...d, [key]: { ...d[key], item_key: key, answer_code: d[key]?.answer_code ?? "", ...patch } }));

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
      queryClient.invalidateQueries({ queryKey: ["checklist-runs"] });
      queryClient.invalidateQueries({ queryKey: ["traffic-light"] });
      queryClient.invalidateQueries({ queryKey: ["findings"] });
      const created = result.findings_created.length;
      onDone(`Revisión guardada. Puntaje ${result.score.score}/${result.score.max_score}. ${created === 0 ? "Sin hallazgos nuevos." : `${created} hallazgo${created === 1 ? "" : "s"} nuevo${created === 1 ? "" : "s"} en Mi sistema.`}`);
    },
    onError: (err) => setError(err instanceof ApiError ? err.message : "No se pudo guardar la revisión."),
  });

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5">
      <h2 className="text-base font-semibold text-slate-900">{template.title}</h2>
      <p className="text-sm text-slate-500 mb-4">{template.purpose}</p>
      <ol className="space-y-4">
        {template.items.map((item, idx) => {
          const current = draft[item.key];
          const entry = current?.answer_code ? scale[current.answer_code] : undefined;
          return (
            <li key={item.key} className="border-b border-slate-100 pb-4 last:border-0">
              <fieldset>
                <legend className="text-sm text-slate-800 mb-2">
                  <span className="text-slate-400 mr-1.5 tabular-nums">{idx + 1}.</span>{item.text}
                </legend>
                <div className="flex flex-wrap gap-2">
                  {template.scale.map((s) => {
                    const id = `${template.id}-${item.key}-${s.code}`;
                    const selected = current?.answer_code === s.code;
                    return (
                      <label
                        key={s.code}
                        htmlFor={id}
                        className={`cursor-pointer rounded-lg border px-3 py-1.5 text-sm ${selected ? "border-indigo-600 bg-indigo-50 text-indigo-700 font-semibold" : "border-slate-300 text-slate-700 hover:bg-slate-50"}`}
                      >
                        <input
                          id={id}
                          type="radio"
                          className="sr-only"
                          name={`${template.id}-${item.key}`}
                          checked={selected}
                          onChange={() => update(item.key, { answer_code: s.code })}
                        />
                        {s.label}
                      </label>
                    );
                  })}
                </div>
                {entry?.finding && (
                  <div className="mt-3 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-2">
                    <input aria-label="Qué se observó" className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm" placeholder="Qué se observó" value={current?.observation ?? ""} onChange={(e) => update(item.key, { observation: e.target.value })} />
                    <input aria-label="Acción acordada" className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm" placeholder="Acción acordada" value={current?.action ?? ""} onChange={(e) => update(item.key, { action: e.target.value })} />
                    <input aria-label="Responsable" className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm" placeholder="Responsable" value={current?.responsible ?? ""} onChange={(e) => update(item.key, { responsible: e.target.value })} />
                    <input aria-label="Fecha límite" type="date" className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm" value={current?.due_date ?? ""} onChange={(e) => update(item.key, { due_date: e.target.value })} />
                  </div>
                )}
              </fieldset>
            </li>
          );
        })}
      </ol>
      <label htmlFor={`${template.id}-notes`} className="block text-xs font-medium text-slate-500 mt-4 mb-1">Notas de la revisión (opcional)</label>
      <textarea id={`${template.id}-notes`} rows={2} className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm w-full" value={notes} onChange={(e) => setNotes(e.target.value)} />
      {error && <p className="text-sm text-red-600 mt-2">{error}</p>}
      <div className="mt-4 flex flex-wrap items-center gap-3">
        <button
          onClick={() => mutation.mutate()}
          disabled={answered < template.items.length || mutation.isPending}
          className="rounded-lg bg-indigo-600 text-white text-sm font-semibold px-4 py-1.5 hover:bg-indigo-700 disabled:opacity-40"
        >
          Guardar revisión
        </button>
        <span className="text-xs text-slate-500 tabular-nums">{answered} de {template.items.length} respondidos</span>
      </div>
    </div>
  );
}

function RunDetail({ runId }: { runId: string }) {
  const { data } = useQuery({ queryKey: ["checklist-run", runId], queryFn: () => getChecklistRun(runId) });
  if (!data) return <p className="text-sm text-slate-500 p-3">Cargando…</p>;
  return (
    <div className="overflow-x-auto bg-slate-50 rounded-lg p-3">
      <table className="w-full text-sm">
        <tbody>
          {data.answers.map((a) => (
            <tr key={a.item_key} className="border-b border-slate-200 last:border-0 align-top">
              <td className="py-1.5 pr-3 text-slate-700">{a.text}</td>
              <td className="py-1.5 pr-3 font-medium whitespace-nowrap">{a.answer_label}</td>
              <td className="py-1.5 text-slate-500">{[a.observation, a.action, a.responsible, a.due_date].filter(Boolean).join(" · ") || "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function History({ templates }: { templates: ChecklistTemplate[] }) {
  const { data } = useQuery({ queryKey: ["checklist-runs"], queryFn: () => getChecklistRuns() });
  const [openRun, setOpenRun] = useState<string | null>(null);
  const titles = Object.fromEntries(templates.map((t) => [t.id, t.title]));

  return (
    <section className="rounded-xl border border-slate-200 bg-white p-5">
      <h2 className="text-base font-semibold text-slate-900 mb-3">Historial</h2>
      {data && data.length === 0 && <EmptyState message="Todavía no se hizo ninguna revisión." />}
      <ul className="divide-y divide-slate-100">
        {(data ?? []).map((r) => (
          <li key={r.run_id} className="py-2">
            <button onClick={() => setOpenRun(openRun === r.run_id ? null : r.run_id)} className="w-full text-left flex flex-wrap items-center justify-between gap-2">
              <span className="text-sm text-slate-800">{titles[r.template_id] ?? r.template_id}</span>
              <span className="text-xs text-slate-500">
                {new Date(r.performed_at).toLocaleString("es")} · {r.performed_by.replace(/^portal:/, "")}
              </span>
            </button>
            {openRun === r.run_id && <div className="mt-2"><RunDetail runId={r.run_id} /></div>}
          </li>
        ))}
      </ul>
    </section>
  );
}

export function InspectionsPage() {
  const { data: templates, isLoading } = useQuery({ queryKey: ["checklist-templates"], queryFn: getChecklistTemplates });
  const [selected, setSelected] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const template = templates?.find((t) => t.id === selected);

  return (
    <StagePage title="Revisiones">
      {isLoading && <p className="text-sm text-slate-500">Cargando…</p>}
      {templates && templates.length === 0 && (
        <EmptyState message="No hay listas disponibles. Active el paquete de su programa en Configuración → Paquetes." />
      )}
      {message && (
        <div className="rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-2.5 text-sm text-emerald-800 mb-4">{message}</div>
      )}
      <div className="grid gap-6 lg:grid-cols-[18rem_minmax(0,1fr)]">
        <nav aria-label="Listas disponibles" className="space-y-5">
          {KIND_ORDER.map((kind) => {
            const group = (templates ?? []).filter((t) => t.kind === kind);
            if (group.length === 0) return null;
            return (
              <div key={kind}>
                <div className="text-xs font-semibold uppercase tracking-wide text-slate-500 mb-2">{KIND_LABEL[kind]}</div>
                <ul className="space-y-1">
                  {group.map((t) => (
                    <li key={t.id}>
                      <button
                        onClick={() => { setSelected(t.id); setMessage(null); }}
                        className={`w-full text-left rounded-lg px-3 py-2 text-sm ${selected === t.id ? "bg-indigo-600 text-white" : "bg-white border border-slate-200 text-slate-700 hover:bg-slate-50"}`}
                      >
                        {t.title}
                      </button>
                    </li>
                  ))}
                </ul>
              </div>
            );
          })}
        </nav>
        <div className="space-y-6 min-w-0">
          {template
            ? <RunForm key={template.id} template={template} onDone={(m) => { setMessage(m); setSelected(null); }} />
            : templates && templates.length > 0 && <EmptyState message="Elija una lista para empezar una revisión." />}
          {templates && <History templates={templates} />}
        </div>
      </div>
    </StagePage>
  );
}
