import { useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ApiError, type ImprovementCandidate, type ImprovementInput, type MinimumPlanRow, createImprovementInput, deleteImprovementInput,
  getImprovementInputs, getMinimumPlan, getProductBoard, saveMinimumPlanEntry, updateImprovementInput,
} from "../api";
import { StagePage, EmptyState } from "../components/StagePage";
import { NavSection, SectionNav } from "../components/SectionNav";
import { sectionsFor } from "../navigation";
import { badgeClass, label as codeLabel, options as codeOptions, appLocale, term, money, formSuffix, formLink, form, currencyCode } from "../catalog";

// Plan mínimo de O&M, ficha 7G.2 y tablero 7H (Track D, D7; Guía 3 sección 4).
// "Al finalizar esta guía, la JAAPS debe salir con un plan mínimo. No es un
// documento complejo. Es una hoja de ruta inmediata."

const SECTIONS = sectionsFor("/improvement");

function errText(err: unknown, fallback: string) {
  return err instanceof ApiError ? err.message : fallback;
}

function Card({ title, description, children }: { title: string; description?: string; children: React.ReactNode }) {
  return (
    <section className="mb-6 rounded-xl border border-slate-200 bg-white p-5">
      <h2 className="text-base font-semibold text-slate-900">{title}</h2>
      {description && <p className="mb-3 mt-1 max-w-3xl text-sm text-slate-600">{description}</p>}
      {children}
    </section>
  );
}

function PlanRow({ row }: { row: MinimumPlanRow }) {
  const qc = useQueryClient();
  const [f, setF] = useState({ decision: row.entry?.decision ?? "", responsible: row.entry?.responsible ?? "", term: row.entry?.term ?? "" });
  const [msg, setMsg] = useState<string | null>(null);
  const save = useMutation({
    mutationFn: () => saveMinimumPlanEntry(row.pack_id, row.code, f),
    onSuccess: () => { setMsg("Guardado"); qc.invalidateQueries({ queryKey: ["minimum-plan"] }); qc.invalidateQueries({ queryKey: ["product-board"] }); },
    onError: (e) => setMsg(errText(e, "No se pudo guardar.")),
  });
  const dirty = f.decision !== (row.entry?.decision ?? "") || f.responsible !== (row.entry?.responsible ?? "") || f.term !== (row.entry?.term ?? "");
  return (
    <article className="rounded-lg border border-slate-200 p-3">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h3 className="text-sm font-semibold text-slate-900">{row.sort_order}. {row.component}</h3>
        {row.entry ? <span className="text-[11px] text-emerald-700">Decidido · {row.entry.updated_by.replace(/^portal:/, "")}</span>
          : <span className="text-[11px] text-amber-700">Sin decidir</span>}
      </div>
      <p className="text-xs text-slate-500">{row.guidance}</p>
      {row.suggestions.length > 0 && (
        <ul className="mt-2 space-y-0.5 rounded-md bg-slate-50 p-2 text-xs text-slate-700">
          {row.suggestions.map((s, i) => <li key={i}>• {s}</li>)}
        </ul>
      )}
      <div className="mt-2 grid gap-2 sm:grid-cols-[1fr_12rem_10rem_auto]">
        <textarea aria-label="Decisión" rows={2} className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm"
          placeholder={row.example_decision ? `Ejemplo: ${row.example_decision}` : "Decisión concreta"}
          value={f.decision} onChange={(e) => setF({ ...f, decision: e.target.value })} />
        <input aria-label="Responsable" className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm"
          placeholder={row.example_responsible ? `Ej.: ${row.example_responsible}` : "Responsable"}
          value={f.responsible} onChange={(e) => setF({ ...f, responsible: e.target.value })} />
        <input aria-label="Plazo" className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm"
          placeholder={row.example_term ? `Ej.: ${row.example_term}` : "Plazo"}
          value={f.term} onChange={(e) => setF({ ...f, term: e.target.value })} />
        <button onClick={() => save.mutate()} disabled={!f.decision.trim() || !dirty || save.isPending}
          className="h-fit rounded-lg bg-indigo-600 px-3 py-1.5 text-sm font-semibold text-white disabled:opacity-50">Guardar</button>
      </div>
      {msg && <p className={`mt-1 text-xs ${msg === "Guardado" ? "text-emerald-700" : "text-red-600"}`}>{msg}</p>}
    </article>
  );
}

function MinimumPlanSection() {
  const { data, error } = useQuery({ queryKey: ["minimum-plan"], queryFn: getMinimumPlan, retry: false });
  if (error) return <Card title="Plan mínimo de operación y mantenimiento"><p className="text-sm text-amber-800">{errText(error, "")}</p></Card>;
  if (!data) return null;
  return (
    <Card title="Plan mínimo de operación y mantenimiento"
      description={`Hoja de ruta inmediata: una decisión concreta, un responsable y un plazo por fila. Bajo cada fila, lo que el sistema ya sabe de su operación. ${data.summary.decided} de ${data.summary.total} filas decididas.`}>
      {data.rows.length === 0 && <EmptyState message="Ningún paquete adoptado trae un plan mínimo." />}
      <div className="space-y-3">{data.rows.map((r) => <PlanRow key={`${r.pack_id}:${r.code}:${r.entry?.updated_at ?? ""}`} row={r} />)}</div>
    </Card>
  );
}

function InputEditor({ input }: { input: ImprovementInput }) {
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [f, setF] = useState({
    proposed_action: input.proposed_action ?? "", community_action: input.community_action ?? "",
    support_required: input.support_required ?? "", support_level: input.support_level ?? "",
    cost_estimate: input.cost_estimate !== null ? String(input.cost_estimate) : "", cost_note: input.cost_note ?? "",
    term: input.term ?? "", priority: input.priority,
  });
  const [msg, setMsg] = useState<string | null>(null);
  const refresh = () => { qc.invalidateQueries({ queryKey: ["improvement-inputs"] }); qc.invalidateQueries({ queryKey: ["minimum-plan"] }); };
  const save = useMutation({
    mutationFn: () => updateImprovementInput(input.input_id, {
      ...f, support_level: f.support_level || null, cost_estimate: f.cost_estimate ? Number(f.cost_estimate) : null,
    }),
    onSuccess: () => { setMsg(null); setOpen(false); refresh(); },
    onError: (e) => setMsg(errText(e, "No se pudo guardar.")),
  });
  const remove = useMutation({
    mutationFn: () => deleteImprovementInput(input.input_id),
    onSuccess: refresh,
    onError: (e) => setMsg(errText(e, "No se pudo quitar.")),
  });
  return (
    <tr className="border-b border-slate-100 align-top last:border-0">
      <td className="py-2 pr-3"><span className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ${badgeClass("priority", input.priority)}`}>{codeLabel("priority", input.priority)}</span></td>
      <td className="py-2 pr-3 font-medium text-slate-800">{input.problem}</td>
      <td className="py-2 pr-3 text-xs text-slate-600">{input.evidence ?? "—"}</td>
      <td className="py-2 pr-3 text-xs">
        {!open ? (
          <div className="space-y-0.5 text-slate-700">
            {input.proposed_action && <p><strong>Acción:</strong> {input.proposed_action}</p>}
            {input.community_action && <p><strong>{term("provider", { capital: true })}:</strong> {input.community_action}</p>}
            {(input.support_required || input.support_level) && <p><strong>Apoyo:</strong> {input.support_required ?? ""}{input.support_level ? ` (${codeLabel("support_level", input.support_level)})` : ""}</p>}
            <p><strong>Costo:</strong> {input.cost_estimate !== null ? money(input.cost_estimate) : "—"}{input.cost_note ? ` · ${input.cost_note}` : ""}
              {input.term && <> · <strong>Plazo:</strong> {input.term}</>}</p>
            <button onClick={() => setOpen(true)} className="mt-1 font-semibold text-indigo-700 hover:underline">Completar</button>
            <button onClick={() => remove.mutate()} className="ml-3 text-slate-500 hover:text-red-600">Quitar</button>
          </div>
        ) : (
          <div className="grid gap-1.5">
            <input aria-label="Acción propuesta" className="rounded border border-slate-300 px-2 py-1" placeholder="Acción propuesta" value={f.proposed_action} onChange={(e) => setF({ ...f, proposed_action: e.target.value })} />
            <input aria-label="Qué se puede hacer con recursos propios" className="rounded border border-slate-300 px-2 py-1" placeholder="Qué se puede hacer con recursos propios" value={f.community_action} onChange={(e) => setF({ ...f, community_action: e.target.value })} />
            <input aria-label="Apoyo técnico o institucional" className="rounded border border-slate-300 px-2 py-1" placeholder="Apoyo técnico o institucional" value={f.support_required} onChange={(e) => setF({ ...f, support_required: e.target.value })} />
            <div className="grid grid-cols-2 gap-1.5">
              <select aria-label="Nivel de apoyo" className="rounded border border-slate-300 px-1 py-1" value={f.support_level} onChange={(e) => setF({ ...f, support_level: e.target.value })}>
                <option value="">— nivel de apoyo —</option>
                {codeOptions("support_level").map(({ code: k, label: v }) => <option key={k} value={k}>{v}</option>)}
              </select>
              <select aria-label="Prioridad" className="rounded border border-slate-300 px-1 py-1" value={f.priority} onChange={(e) => setF({ ...f, priority: e.target.value as ImprovementInput["priority"] })}>
                {codeOptions("priority").map(({ code: k, ...v }) => <option key={k} value={k}>Prioridad {v.label.toLowerCase()}</option>)}
              </select>
              <input aria-label="Costo estimado" type="number" min={0} step="any" className="rounded border border-slate-300 px-2 py-1" placeholder={`Costo${currencyCode() ? ` (${currencyCode()})` : ""}`} value={f.cost_estimate} onChange={(e) => setF({ ...f, cost_estimate: e.target.value })} />
              <input aria-label="Nota del costo" className="rounded border border-slate-300 px-2 py-1" placeholder="por cotizar / estimación" value={f.cost_note} onChange={(e) => setF({ ...f, cost_note: e.target.value })} />
            </div>
            <input aria-label="Plazo" className="rounded border border-slate-300 px-2 py-1" placeholder="Plazo" value={f.term} onChange={(e) => setF({ ...f, term: e.target.value })} />
            <div className="flex gap-2">
              <button onClick={() => save.mutate()} className="rounded bg-indigo-600 px-2 py-1 font-semibold text-white">Guardar</button>
              <button onClick={() => setOpen(false)} className="text-slate-500">Cancelar</button>
            </div>
          </div>
        )}
        {msg && <p className="mt-1 text-red-600">{msg}</p>}
      </td>
    </tr>
  );
}

function Candidate({ c }: { c: ImprovementCandidate }) {
  const qc = useQueryClient();
  const [priority, setPriority] = useState(c.priority ?? "");
  const [msg, setMsg] = useState<string | null>(null);
  const move = useMutation({
    mutationFn: () => createImprovementInput({ source_ref: c.source_ref, priority: priority || null }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["improvement-inputs"] }); qc.invalidateQueries({ queryKey: ["minimum-plan"] }); },
    onError: (e) => setMsg(errText(e, "No se pudo trasladar.")),
  });
  return (
    <li className="flex flex-wrap items-start gap-3 py-2 text-sm">
      <div className="min-w-0 flex-1">
        <p className="text-slate-800">{c.problem}</p>
        {c.evidence && <p className="text-xs text-slate-500">{c.evidence}</p>}
        {msg && <p className="text-xs text-red-600">{msg}</p>}
      </div>
      <select aria-label="Prioridad" className="rounded-lg border border-slate-300 px-2 py-1 text-xs" value={priority} onChange={(e) => setPriority(e.target.value)}>
        <option value="">— prioridad —</option>
        {codeOptions("priority").map(({ code: k, ...v }) => <option key={k} value={k}>{v.label}</option>)}
      </select>
      <button onClick={() => move.mutate()} disabled={!priority || move.isPending} className="rounded-lg border border-indigo-300 px-3 py-1 text-xs font-semibold text-indigo-700 disabled:opacity-50">Llevar a los insumos{formSuffix("improvement_inputs")}</button>
    </li>
  );
}

function InputsSection() {
  const qc = useQueryClient();
  const { data } = useQuery({ queryKey: ["improvement-inputs"], queryFn: getImprovementInputs, retry: false });
  // La ficha es de la guía del tablero 7H: por defecto propone la evidencia de
  // esa etapa (y la que no tiene etapa); el resto, a pedido.
  const [allStages, setAllStages] = useState(false);
  const [manual, setManual] = useState({ problem: "", priority: "medium" });
  const [msg, setMsg] = useState<string | null>(null);
  const add = useMutation({
    mutationFn: () => createImprovementInput(manual),
    onSuccess: () => { setManual({ problem: "", priority: "medium" }); setMsg(null); qc.invalidateQueries({ queryKey: ["improvement-inputs"] }); },
    onError: (e) => setMsg(errText(e, "No se pudo agregar.")),
  });
  if (!data) return null;
  const stage = form("improvement_inputs")?.stage_code ?? null;
  const candidates = data.candidates.filter((c) => allStages || !stage || c.stage_code === null || c.stage_code === stage);
  const hidden = data.candidates.length - candidates.length;
  return (
    <Card title={`Insumos para el Plan de Mejora${formSuffix("improvement_inputs")}`}
      description="Lista breve de problemas técnicos priorizados, con la evidencia que los respalda, lista para la matriz del Plan de Mejora. Los costos son referenciales: antes de aprobar una inversión, pida cotizaciones y, cuando corresponda, estudios o asistencia técnica.">
      <p className="mb-2 text-xs text-slate-600">{data.summary.inputs} problemas · {money(data.summary.cost_estimate_total)} estimados · {data.summary.to_quote} por cotizar</p>
      {data.inputs.length === 0 ? <EmptyState message="Todavía no hay problemas en la ficha. Lleve los de la evidencia de abajo." /> : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead><tr className="border-b border-slate-200 text-left text-xs uppercase tracking-wide text-slate-500">
              <th className="py-2 pr-3">Prioridad</th><th className="py-2 pr-3">Problema</th><th className="py-2 pr-3">Evidencia</th><th className="py-2">Acción, apoyo, costo y plazo</th></tr></thead>
            <tbody>{data.inputs.map((i) => <InputEditor key={`${i.input_id}:${i.updated_at}`} input={i} />)}</tbody>
          </table>
        </div>
      )}
      <div className="mt-3 flex flex-wrap gap-2">
        <input aria-label="Problema manual" className="min-w-[16rem] flex-1 rounded-lg border border-slate-300 px-3 py-1.5 text-sm" placeholder="Otro problema priorizado" value={manual.problem} onChange={(e) => setManual({ ...manual, problem: e.target.value })} />
        <select aria-label="Prioridad manual" className="rounded-lg border border-slate-300 px-2 py-1.5 text-sm" value={manual.priority} onChange={(e) => setManual({ ...manual, priority: e.target.value })}>
          {codeOptions("priority").map(({ code: k, ...v }) => <option key={k} value={k}>{v.label}</option>)}
        </select>
        <button onClick={() => add.mutate()} disabled={!manual.problem.trim()} className="rounded-lg bg-indigo-600 px-3 py-1.5 text-sm font-semibold text-white disabled:opacity-50">Agregar</button>
      </div>
      {msg && <p className="mt-1 text-sm text-red-600">{msg}</p>}
      <h3 className="mt-5 text-sm font-semibold text-slate-900">Lo que la evidencia propone llevar ({candidates.length})</h3>
      <p className="text-xs text-slate-500">Hallazgos abiertos (semáforo, listas, cloro, laboratorio, mapa), fosas sin retiro de lodos y descargas productivas sin controlar.
        {stage && (hidden > 0 || allStages) && (
          <button onClick={() => setAllStages(!allStages)} className="ml-2 font-semibold text-indigo-700 hover:underline">
            {allStages ? "Solo la evidencia de esta guía" : `Ver también ${hidden} de otras guías`}
          </button>
        )}
      </p>
      {candidates.length === 0 ? <EmptyState message="No hay evidencia abierta pendiente de trasladar." />
        : <ul className="divide-y divide-slate-100">{candidates.map((c) => <Candidate key={c.source_ref} c={c} />)}</ul>}
    </Card>
  );
}

function ProductsSection() {
  const templateId = form("products_board")?.template_id ?? null;
  const { data, error } = useQuery({ queryKey: ["product-board", templateId], queryFn: () => getProductBoard(templateId as string), retry: false, enabled: !!templateId });
  if (!templateId) return null;
  if (error) return <Card title={`Productos finales${formSuffix("products_board")}`}><p className="text-sm text-amber-800">{errText(error, "")}</p></Card>;
  if (!data) return null;
  return (
    <Card title={data.title} description={data.purpose}>
      <p className="mb-2 text-xs text-slate-600">
        {data.summary.complete} de {data.summary.total} completos · {data.summary.with_evidence} con registro en el sistema
        {data.last_run ? ` · última verificación ${new Date(data.last_run.performed_at).toLocaleDateString(appLocale())} por ${data.last_run.performed_by.replace(/^portal:/, "")}` : " · nunca verificado"}
      </p>
      <ul className="divide-y divide-slate-100">
        {data.items.map((i) => (
          <li key={i.key} className="flex flex-wrap items-center gap-3 py-2 text-sm">
            <span className="flex-1 text-slate-800">{i.text}
              {i.note && <span className="block text-xs text-slate-500">{i.note}</span>}
            </span>
            <span className={`text-xs ${i.has_evidence ? "text-slate-600" : "text-slate-400"}`}>
              {i.has_evidence ? `${i.evidence.count} registro${i.evidence.count === 1 ? "" : "s"}${i.evidence.last_at ? ` · ${new Date(i.evidence.last_at).toLocaleDateString(appLocale())}` : ""}` : "sin registro"}
            </span>
            <span className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ${i.status === "complete" ? "bg-emerald-50 text-emerald-700" : "bg-amber-50 text-amber-800"}`}>
              {i.status === "complete" ? "Completo" : "Pendiente"}
            </span>
            {i.check && <span className="text-[11px] font-semibold text-red-600">Revisar: completo sin registro</span>}
          </li>
        ))}
      </ul>
      {formLink("products_board") && <p className="mt-3 text-sm"><Link to={formLink("products_board") as string} className="font-semibold text-indigo-700 hover:underline">Verificar los productos ›</Link></p>}
    </Card>
  );
}

export function ImprovementPage() {
  return (
    <StagePage title="Plan mínimo y Plan de Mejora">
      <SectionNav items={SECTIONS} />
      <NavSection id="minimum-plan"><MinimumPlanSection /></NavSection>
      <NavSection id="inputs"><InputsSection /></NavSection>
      <NavSection id="products"><ProductsSection /></NavSection>
    </StagePage>
  );
}
