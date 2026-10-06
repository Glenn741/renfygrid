import { useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiError, type ProgramObservation, createProgramObservation, getProgramObservations, updateProgramObservation } from "../api";
import { StagePage, EmptyState } from "../components/StagePage";
import { badgeClass, label as codeLabel, options as codeOptions, term, formSuffix, formLink } from "../catalog";

// T-10 Consolidado de observaciones para mejora (Guía 7; Track D, D12.2).
// "Priorizar cambios de contenido, metodología, formato o referencias de las
// seis guías." No evalúa a la persona facilitadora: produce evidencia para
// mejorar contenidos, ejemplos, actividades, formatos y referencias.


function errText(err: unknown, fallback: string) {
  return err instanceof ApiError ? err.message : fallback;
}

function Row({ o, stage, source }: { o: ProgramObservation; stage: string; source: string }) {
  const qc = useQueryClient();
  const [msg, setMsg] = useState<string | null>(null);
  const upd = useMutation({
    mutationFn: (status: string) => updateProgramObservation(o.observation_id, { status }),
    onSuccess: () => { setMsg(null); qc.invalidateQueries({ queryKey: ["program-observations"] }); },
    onError: (e) => setMsg(errText(e, "No se pudo cambiar.")),
  });
  return (
    <tr className="border-b border-slate-100 align-top last:border-0">
      <td className="py-2 pr-3 whitespace-nowrap">{stage}</td>
      <td className="py-2 pr-3">{o.finding}{o.community && <span className="block text-xs text-slate-500">{o.community}</span>}</td>
      <td className="py-2 pr-3 text-xs">{source}</td>
      <td className="py-2 pr-3 text-xs">{o.proposed_change ?? "—"}</td>
      <td className="py-2 pr-3"><span className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ${badgeClass("priority", o.priority)}`}>{codeLabel("priority", o.priority)}</span></td>
      <td className="py-2 pr-3 text-xs">{o.reviewer ?? "—"}</td>
      <td className="py-2">
        <select aria-label="Estado" className="rounded border border-slate-300 px-1 py-0.5 text-xs" value={o.status} onChange={(e) => upd.mutate(e.target.value)}>
          {codeOptions("observation.status").map(({ code: k, label: v }) => <option key={k} value={k}>{v}</option>)}
        </select>
        {msg && <p className="text-xs text-red-600">{msg}</p>}
      </td>
    </tr>
  );
}

export function ProgramObservationsPage() {
  const qc = useQueryClient();
  const { data, error } = useQuery({ queryKey: ["program-observations"], queryFn: getProgramObservations, retry: false });
  const empty = { stage_code: "", source_code: "", finding: "", proposed_change: "", priority: "medium", reviewer: "", community: "" };
  const [f, setF] = useState(empty);
  const [msg, setMsg] = useState<string | null>(null);
  const add = useMutation({
    mutationFn: (body: typeof empty) => createProgramObservation(body),
    onSuccess: () => { setF(empty); setMsg(null); qc.invalidateQueries({ queryKey: ["program-observations"] }); },
    onError: (e) => setMsg(errText(e, "No se pudo registrar.")),
  });
  if (error) return <StagePage title={`Observaciones del programa${formSuffix("program_observations")}`}><p className="text-sm text-amber-800">{errText(error, "")}</p></StagePage>;
  if (!data) return <StagePage title={`Observaciones del programa${formSuffix("program_observations")}`}><p className="text-sm text-slate-500">Cargando…</p></StagePage>;
  const stage = Object.fromEntries(data.stages.map((s) => [s.code, `${s.code} · ${s.title}`]));
  const source = Object.fromEntries(data.sources.map((s) => [s.code, s.label]));
  return (
    <StagePage title={`Observaciones del programa${formSuffix("program_observations")}`}>
      <section className="mb-6 rounded-xl border border-slate-200 bg-white p-5">
        <h2 className="text-base font-semibold text-slate-900">Consolidado de observaciones para mejora</h2>
        <p className="mb-3 mt-1 max-w-3xl text-sm text-slate-600">
          Reúne observaciones territoriales para priorizar cambios de contenido, metodología, lenguaje o formato de los materiales del programa. No evalúa a la persona
          facilitadora: produce evidencia para mejorar.
          {formLink("daily_evaluation") && (<>
            {" "}La evaluación diaria{formSuffix("daily_evaluation")} y la rúbrica de microfacilitación{formSuffix("microfacilitation_rubric")} se aplican en{" "}
            <Link to={formLink("daily_evaluation") as string} className="font-semibold text-indigo-700 hover:underline">Ruta y revisiones</Link>.
          </>)}
        </p>
        <p className="mb-2 text-xs text-slate-600">{data.summary.total} observaciones · {data.summary.open} abiertas · {data.summary.in_review} en revisión · {data.summary.incorporated} incorporadas</p>
        {data.observations.length === 0 ? <EmptyState message="Todavía no hay observaciones." /> : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead><tr className="border-b border-slate-200 text-left text-xs uppercase tracking-wide text-slate-500">
                <th className="py-2 pr-3">Guía</th><th className="py-2 pr-3">Hallazgo</th><th className="py-2 pr-3">Fuente</th><th className="py-2 pr-3">Cambio propuesto</th>
                <th className="py-2 pr-3">Prioridad</th><th className="py-2 pr-3">Revisa</th><th className="py-2">Estado</th></tr></thead>
              <tbody>{data.observations.map((o) => <Row key={`${o.observation_id}:${o.updated_at}`} o={o} stage={stage[o.stage_code] ?? o.stage_code} source={source[o.source_code] ?? o.source_code} />)}</tbody>
            </table>
          </div>
        )}
      </section>

      {data.suggestions.length > 0 && (
        <section className="mb-6 rounded-xl border border-amber-200 bg-amber-50 p-5">
          <h2 className="text-base font-semibold text-slate-900">Lo que propone la CAP</h2>
          <p className="mb-2 text-xs text-slate-600">{data.suggestions[0].hint}</p>
          <ul className="space-y-2">
            {data.suggestions.map((s) => (
              <li key={s.stage_code + s.source_code} className="flex flex-wrap items-center gap-3 text-sm">
                <span className="flex-1">{s.finding}</span>
                <button onClick={() => setF({ ...empty, stage_code: s.stage_code, source_code: s.source_code, finding: s.finding, priority: "high" })}
                  className="rounded-lg border border-indigo-300 bg-white px-3 py-1 text-xs font-semibold text-indigo-700">Usar como observación</button>
              </li>
            ))}
          </ul>
        </section>
      )}

      <section className="rounded-xl border border-slate-200 bg-white p-5">
        <h2 className="mb-3 text-base font-semibold text-slate-900">Registrar una observación</h2>
        <div className="grid gap-2 sm:grid-cols-3">
          <select aria-label="Guía" className="rounded-lg border border-slate-300 px-2 py-1.5 text-sm" value={f.stage_code} onChange={(e) => setF({ ...f, stage_code: e.target.value })}>
            <option value="">— guía —</option>
            {data.stages.map((s) => <option key={s.code} value={s.code}>{s.code} · {s.title}</option>)}
          </select>
          <select aria-label="Fuente" className="rounded-lg border border-slate-300 px-2 py-1.5 text-sm" value={f.source_code} onChange={(e) => setF({ ...f, source_code: e.target.value })}>
            <option value="">— fuente —</option>
            {data.sources.map((s) => <option key={s.code} value={s.code}>{s.label}</option>)}
          </select>
          <select aria-label="Prioridad" className="rounded-lg border border-slate-300 px-2 py-1.5 text-sm" value={f.priority} onChange={(e) => setF({ ...f, priority: e.target.value })}>
            {codeOptions("priority").map(({ code: k, ...v }) => <option key={k} value={k}>Prioridad {v.label.toLowerCase()}</option>)}
          </select>
          <textarea aria-label="Hallazgo" rows={2} className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm sm:col-span-3" placeholder="Hallazgo" value={f.finding} onChange={(e) => setF({ ...f, finding: e.target.value })} />
          <input aria-label="Cambio propuesto" className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm sm:col-span-3" placeholder="Cambio propuesto" value={f.proposed_change} onChange={(e) => setF({ ...f, proposed_change: e.target.value })} />
          <input aria-label="Responsable de revisión" className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm" placeholder="Responsable de revisión" value={f.reviewer} onChange={(e) => setF({ ...f, reviewer: e.target.value })} />
          <input aria-label="Organización o comunidad" className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm" placeholder={`${term("provider", { capital: true })} o comunidad`} value={f.community} onChange={(e) => setF({ ...f, community: e.target.value })} />
          <button onClick={() => add.mutate(f)} disabled={!f.stage_code || !f.source_code || !f.finding.trim()}
            className="rounded-lg bg-indigo-600 px-3 py-1.5 text-sm font-semibold text-white disabled:opacity-50">Registrar</button>
        </div>
        {msg && <p className="mt-1 text-sm text-red-600">{msg}</p>}
      </section>
    </StagePage>
  );
}
