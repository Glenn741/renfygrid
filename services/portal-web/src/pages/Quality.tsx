import { useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ApiError,
  createLabPlanItem,
  getLabSamples,
  getQualityOverview,
  getQualityParameters,
  getSamplingPoints,
  recordLabSample,
  reviewLabPlan,
  updateLabPlanItem,
  type LabResult,
  type QualityParameter,
} from "../api";
import { StagePage, EmptyState } from "../components/StagePage";
import { NavSection, SectionNav } from "../components/SectionNav";
import { sectionsFor } from "../navigation";
import { badgeClass, label as codeLabel, options as codeOptions, appLocale, isoDay, term } from "../catalog";

// Calidad del agua y laboratorio (Track D, D2; Guia 3 §3.4 y calendario 7G).
// Los limites salen de las reglas del paquete normativo; un parametro sin
// regla (p. ej. arsenico, cuya norma NTE INEN 1108 aun no esta cargada) se
// guarda sin interpretar. El plan de muestreo lo define la junta con la
// frecuencia que le indique ARCA o el GAD: aqui no se inventa ninguna.

const SECTIONS = sectionsFor("/quality");
const SEVERITY_STYLE: Record<string, string> = {
  ok: "bg-emerald-50 text-emerald-700",
  alert: "bg-amber-50 text-amber-800",
  critical: "bg-red-100 text-red-800",
};

function errText(err: unknown, fallback: string) {
  return err instanceof ApiError ? err.message : fallback;
}

function dateTime(iso: string) {
  return new Date(iso).toLocaleString(appLocale(), { day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" });
}

function SectionCard({ title, description, children }: { title: string; description?: string; children: React.ReactNode }) {
  return (
    <section className="mb-6 rounded-xl border border-slate-200 bg-white p-5">
      <h2 className="text-base font-semibold text-slate-900">{title}</h2>
      {description && <p className="mb-3 mt-1 max-w-3xl text-sm text-slate-600">{description}</p>}
      {children}
    </section>
  );
}

function ResultChip({ r }: { r: LabResult }) {
  const shown = `${r.qualifier === "=" ? "" : r.qualifier}${r.value.toLocaleString(appLocale())} ${r.unit}`;
  const tag = r.interpretation === "interpreted"
    ? <span className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ${SEVERITY_STYLE[r.severity ?? "ok"]}`}>{r.result_label}</span>
    : <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[11px] text-slate-600">{r.interpretation === "inconclusive" ? "no concluyente" : "sin regla"}</span>;
  return <span className="inline-flex flex-wrap items-center gap-1.5 text-sm">{r.parameter_label}: <strong className="tabular-nums">{shown}</strong> {tag}</span>;
}

function useInvalidate() {
  const qc = useQueryClient();
  return () => { for (const k of ["quality-overview", "lab-samples", "operations-today", "findings"]) qc.invalidateQueries({ queryKey: [k] }); };
}

function AlertsSection() {
  const { data } = useQuery({ queryKey: ["quality-overview"], queryFn: getQualityOverview });
  if (!data) return null;
  return (
    <SectionCard title="Alertas de calidad" description="Mediciones y análisis fuera de rango con su hallazgo abierto. Un E. coli presente es una alerta crítica: informe a la directiva, corrija y coordine con las autoridades.">
      {data.alerts.length === 0 && <EmptyState message="No hay alertas de calidad abiertas." />}
      <ul className="space-y-2">
        {data.alerts.map((a) => (
          <li key={a.finding_id} className={`rounded-lg border p-3 text-sm ${a.critical ? "border-red-300 bg-red-50 text-red-900" : "border-amber-200 bg-amber-50 text-amber-900"}`}>
            <span className="font-semibold">{a.critical ? "Crítica · " : ""}</span>{a.description}
            <span className="ml-2 text-xs opacity-75">{dateTime(a.created_at)}</span>
          </li>
        ))}
      </ul>
      {data.alerts.length > 0 && <Link to="/system#findings" className="mt-3 inline-block text-sm font-semibold text-indigo-700 hover:underline">Gestionar en Hallazgos ›</Link>}
    </SectionCard>
  );
}

interface Row { parameter_code: string; qualifier: "=" | "<" | ">"; value: string }

function LabSection({ params }: { params: QualityParameter[] }) {
  const invalidate = useInvalidate();
  const { data: points } = useQuery({ queryKey: ["sampling-points"], queryFn: () => getSamplingPoints(), retry: false });
  const { data: overview } = useQuery({ queryKey: ["quality-overview"], queryFn: getQualityOverview });
  const [pointId, setPointId] = useState("");
  const [planId, setPlanId] = useState("");
  const [when, setWhen] = useState(() => new Date(Date.now() - new Date().getTimezoneOffset() * 60000).toISOString().slice(0, 16));
  const [lab, setLab] = useState("");
  const [report, setReport] = useState("");
  const [reason, setReason] = useState("plan");
  const [rows, setRows] = useState<Row[]>([{ parameter_code: "e_coli", qualifier: "=", value: "" }]);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const plan = overview?.plan.items ?? [];

  const choosePlan = (id: string) => {
    setPlanId(id);
    const item = plan.find((p) => p.plan_item_id === id);
    if (item) {
      setRows(item.parameters.map((c) => ({ parameter_code: c, qualifier: "=", value: "" })));
      if (item.point_id) setPointId(item.point_id);
      setReason("plan");
    }
  };

  const save = useMutation({
    mutationFn: () => recordLabSample({
      sampled_at: new Date(when).toISOString(), laboratory: lab, report_ref: report || null, reason,
      sampling_point_id: pointId || null, plan_item_id: planId || null,
      results: rows.filter((r) => r.value !== "").map((r) => ({ parameter_code: r.parameter_code, qualifier: r.qualifier, value: Number(r.value) })),
    }),
    onSuccess: (s) => {
      invalidate();
      setRows(rows.map((r) => ({ ...r, value: "" })));
      setMsg({ ok: !s.critical, text: s.critical
        ? "Guardado. ALERTA CRÍTICA: hay E. coli presente. Se abrió un hallazgo de prioridad alta; informe de inmediato a la directiva."
        : `Guardado.${s.findings_created ? ` ${s.findings_created} resultado(s) fuera de rango abrieron hallazgo.` : ""}` });
    },
    onError: (err) => setMsg({ ok: false, text: errText(err, "No se pudo guardar el análisis.") }),
  });

  return (
    <SectionCard title="Registrar análisis de laboratorio" description="Copie los resultados del informe del laboratorio. Para E. coli, si el informe dice «Ausencia» o «<1», registre 0. Use «<» cuando el informe da un valor bajo el límite de detección.">
      <div className="grid gap-3 sm:grid-cols-3">
        <label className="text-xs text-slate-600">Parte del plan (opcional)
          <select className="mt-1 w-full rounded-lg border border-slate-300 px-2 py-1.5 text-sm" value={planId} onChange={(e) => choosePlan(e.target.value)}>
            <option value="">— fuera del plan —</option>
            {plan.map((p) => <option key={p.plan_item_id} value={p.plan_item_id}>{p.name}</option>)}
          </select>
        </label>
        <label className="text-xs text-slate-600">Punto de muestreo
          <select className="mt-1 w-full rounded-lg border border-slate-300 px-2 py-1.5 text-sm" value={pointId} onChange={(e) => setPointId(e.target.value)}>
            <option value="">— sin punto —</option>
            {(points ?? []).map((p) => <option key={p.point_id} value={p.point_id}>{p.kind_label} · {p.name}</option>)}
          </select>
        </label>
        <label className="text-xs text-slate-600">Fecha y hora de la toma
          <input type="datetime-local" className="mt-1 w-full rounded-lg border border-slate-300 px-2 py-1.5 text-sm" value={when} onChange={(e) => setWhen(e.target.value)} />
        </label>
        <label className="text-xs text-slate-600">Laboratorio
          <input className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-1.5 text-sm" placeholder="Nombre del laboratorio" value={lab} onChange={(e) => setLab(e.target.value)} />
        </label>
        <label className="text-xs text-slate-600">N.º de informe
          <input className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-1.5 text-sm" value={report} onChange={(e) => setReport(e.target.value)} />
        </label>
        <label className="text-xs text-slate-600">Motivo
          <select className="mt-1 w-full rounded-lg border border-slate-300 px-2 py-1.5 text-sm" value={reason} onChange={(e) => setReason(e.target.value)}>
            {codeOptions("sample.reason").map(({ code: k, label: v }) => <option key={k} value={k}>{v}</option>)}
          </select>
        </label>
      </div>
      <div className="mt-4 space-y-2">
        {rows.map((row, i) => {
          const p = params.find((x) => x.code === row.parameter_code);
          return (
            <div key={i} className="grid gap-2 sm:grid-cols-[1fr_5rem_9rem_auto] sm:items-center">
              <select aria-label="Parámetro" className="rounded-lg border border-slate-300 px-2 py-1.5 text-sm" value={row.parameter_code}
                onChange={(e) => setRows(rows.map((r, j) => (j === i ? { ...r, parameter_code: e.target.value } : r)))}>
                {params.map((x) => <option key={x.code} value={x.code}>{x.label} ({x.unit || "—"}){x.bands ? "" : " · sin regla"}</option>)}
              </select>
              <select aria-label="Calificador" className="rounded-lg border border-slate-300 px-2 py-1.5 text-sm" value={row.qualifier}
                onChange={(e) => setRows(rows.map((r, j) => (j === i ? { ...r, qualifier: e.target.value as Row["qualifier"] } : r)))}>
                <option value="=">=</option><option value="<">&lt;</option><option value=">">&gt;</option>
              </select>
              <input aria-label="Valor" type="number" step="any" min={0} className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm" placeholder={p?.unit ?? ""} value={row.value}
                onChange={(e) => setRows(rows.map((r, j) => (j === i ? { ...r, value: e.target.value } : r)))} />
              <button onClick={() => setRows(rows.filter((_, j) => j !== i))} className="text-xs text-slate-500 hover:text-red-700" aria-label="Quitar">Quitar</button>
            </div>
          );
        })}
        <button onClick={() => setRows([...rows, { parameter_code: params[0]?.code ?? "e_coli", qualifier: "=", value: "" }])} className="text-sm font-medium text-indigo-700 hover:underline">
          + Agregar parámetro
        </button>
      </div>
      {msg && <p role="status" className={`mt-3 rounded-lg p-3 text-sm ${msg.ok ? "bg-emerald-50 text-emerald-800" : "bg-red-50 text-red-800"}`}>{msg.text}</p>}
      <button onClick={() => save.mutate()} disabled={!lab.trim() || !rows.some((r) => r.value !== "") || save.isPending}
        className="mt-3 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-700 disabled:opacity-50">
        {save.isPending ? "Guardando…" : "Guardar análisis"}
      </button>
    </SectionCard>
  );
}

function PlanSection({ params }: { params: QualityParameter[] }) {
  const invalidate = useInvalidate();
  const { data: overview } = useQuery({ queryKey: ["quality-overview"], queryFn: getQualityOverview });
  const { data: points } = useQuery({ queryKey: ["sampling-points"], queryFn: () => getSamplingPoints(), retry: false });
  const [name, setName] = useState("");
  const [selected, setSelected] = useState<string[]>([]);
  const [freq, setFreq] = useState("");
  const [pointId, setPointId] = useState("");
  const [source, setSource] = useState("");
  const [reviewNotes, setReviewNotes] = useState("");
  const [msg, setMsg] = useState<string | null>(null);
  const create = useMutation({
    mutationFn: () => createLabPlanItem({ name, parameters: selected, frequency_days: Number(freq), sampling_point_id: pointId || null, source_note: source || null }),
    onSuccess: () => { setName(""); setSelected([]); setFreq(""); setSource(""); setMsg(null); invalidate(); },
    onError: (err) => setMsg(errText(err, "No se pudo guardar.")),
  });
  const toggle = useMutation({ mutationFn: (p: { id: string; active: boolean }) => updateLabPlanItem(p.id, { active: p.active }), onSuccess: invalidate });
  const review = useMutation({
    mutationFn: () => reviewLabPlan({ reviewed_on: isoDay(), notes: reviewNotes || null }),
    onSuccess: () => { setReviewNotes(""); invalidate(); },
    onError: (err) => setMsg(errText(err, "No se pudo registrar la revisión.")),
  });
  const plan = overview?.plan;
  const label = (code: string) => params.find((p) => p.code === code)?.label ?? code;

  return (
    <SectionCard title="Plan de muestreo" description={`Qué analizar, dónde y cada cuánto. La frecuencia se define según la población servida y los lineamientos de ${term("regulator")} o ${term("local_government")}; anote de dónde sale.`}>
      {plan && (
        <div className={`mb-4 rounded-lg border p-3 text-sm ${plan.review.status === "ok" ? "border-emerald-200 bg-emerald-50 text-emerald-900" : "border-amber-200 bg-amber-50 text-amber-900"}`}>
          <strong>Revisión del plan:</strong>{" "}
          {plan.review.last_reviewed_on ? `última el ${new Date(`${plan.review.last_reviewed_on}T12:00:00`).toLocaleDateString(appLocale())}` : "todavía no se revisó"}
          {plan.review.status === "overdue" && " · vencida"}
          {plan.review.source && <span className="block text-xs opacity-80">{plan.review.source}</span>}
          <span className="mt-2 flex flex-wrap gap-2">
            <input aria-label="Conclusión de la revisión" className="min-w-[14rem] flex-1 rounded-lg border border-slate-300 bg-white px-3 py-1 text-sm text-slate-800" placeholder="Qué se revisó (población, fuente, cambios del sistema)" value={reviewNotes} onChange={(e) => setReviewNotes(e.target.value)} />
            <button onClick={() => review.mutate()} className="rounded-lg bg-indigo-600 px-3 py-1 text-sm font-semibold text-white hover:bg-indigo-700">Registrar revisión de hoy</button>
          </span>
        </div>
      )}
      {plan && plan.items.length === 0 && <EmptyState message="Todavía no hay plan de muestreo." />}
      <ul className="divide-y divide-slate-100">
        {(plan?.items ?? []).map((p) => (
          <li key={p.plan_item_id} className="flex flex-wrap items-center gap-3 py-2 text-sm">
            <span className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ${badgeClass("quality.plan_status", p.status)}`}>{codeLabel("quality.plan_status", p.status)}</span>
            <span className="min-w-0 flex-1 text-slate-800">
              {p.name}
              <span className="block text-xs text-slate-500">
                {p.parameters.map(label).join(", ")} · cada {p.frequency_days} días{p.point_name ? ` · ${p.point_name}` : ""}
                {p.last_sampled_at && ` · última muestra ${new Date(p.last_sampled_at).toLocaleDateString(appLocale())}`}
                {p.source_note && ` · ${p.source_note}`}
              </span>
            </span>
            <button onClick={() => toggle.mutate({ id: p.plan_item_id, active: false })} className="text-xs text-slate-500 hover:underline">Quitar del plan</button>
          </li>
        ))}
      </ul>
      <div className="mt-3 space-y-2 rounded-lg border border-dashed border-slate-300 bg-slate-50 p-3">
        <div className="grid gap-2 sm:grid-cols-[1fr_8rem_1fr]">
          <input aria-label="Nombre" className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm" placeholder="Nombre (p. ej. Microbiológico en red)" value={name} onChange={(e) => setName(e.target.value)} />
          <input aria-label="Cada cuántos días" type="number" min={1} className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm" placeholder="Cada N días" value={freq} onChange={(e) => setFreq(e.target.value)} />
          <select aria-label="Punto" className="rounded-lg border border-slate-300 bg-white px-2 py-1.5 text-sm" value={pointId} onChange={(e) => setPointId(e.target.value)}>
            <option value="">— punto (opcional) —</option>
            {(points ?? []).map((p) => <option key={p.point_id} value={p.point_id}>{p.name}</option>)}
          </select>
        </div>
        <div className="flex flex-wrap gap-2">
          {params.filter((p) => p.measured_by === "lab").map((p) => (
            <label key={p.code} className={`inline-flex cursor-pointer items-center gap-1 rounded-full border px-2.5 py-1 text-xs ${selected.includes(p.code) ? "border-indigo-600 bg-indigo-50 text-indigo-800" : "border-slate-300 bg-white text-slate-700"}`}>
              <input type="checkbox" className="sr-only" checked={selected.includes(p.code)} onChange={() => setSelected((s) => (s.includes(p.code) ? s.filter((c) => c !== p.code) : [...s, p.code]))} />
              {p.label}
            </label>
          ))}
        </div>
        <input aria-label="Fuente de la frecuencia" className="w-full rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm" placeholder={`De dónde sale la frecuencia (oficio de ${term("regulator")}, ${term("local_government")}, laboratorio)`} value={source} onChange={(e) => setSource(e.target.value)} />
        <button onClick={() => create.mutate()} disabled={!name.trim() || !selected.length || !freq || create.isPending} className="rounded-lg bg-indigo-600 px-3 py-1.5 text-sm font-semibold text-white hover:bg-indigo-700 disabled:opacity-50">
          Agregar al plan
        </button>
        {msg && <p className="text-sm text-red-600">{msg}</p>}
      </div>
    </SectionCard>
  );
}

function ResultsSection() {
  const { data } = useQuery({ queryKey: ["lab-samples"], queryFn: () => getLabSamples(100) });
  return (
    <SectionCard title="Resultados de laboratorio" description="Informe y archivo de calidad. La interpretación es la de la regla vigente cuando se tomó la muestra.">
      {data && data.length === 0 && <EmptyState message="Todavía no hay análisis registrados." />}
      <ul className="divide-y divide-slate-100">
        {(data ?? []).map((s) => (
          <li key={s.sample_id} className="py-3">
            <p className="text-sm text-slate-800">
              <strong>{dateTime(s.sampled_at)}</strong> · {s.point_name ?? "sin punto"} · {s.laboratory}{s.report_ref ? ` · informe ${s.report_ref}` : ""}
              <span className="ml-2 rounded-full bg-slate-100 px-2 py-0.5 text-[11px] text-slate-600">{codeLabel("sample.reason", s.reason)}{s.plan_name ? ` · ${s.plan_name}` : ""}</span>
            </p>
            <div className="mt-1 flex flex-wrap gap-x-5 gap-y-1">{s.results.map((r) => <ResultChip key={r.parameter_code} r={r} />)}</div>
          </li>
        ))}
      </ul>
    </SectionCard>
  );
}

export function QualityPage() {
  const { data: params } = useQuery({ queryKey: ["quality-parameters"], queryFn: getQualityParameters });
  return (
    <StagePage title="Calidad del agua">
      <SectionNav items={SECTIONS} />
      <NavSection id="alerts"><AlertsSection /></NavSection>
      <NavSection id="lab"><LabSection params={params ?? []} /></NavSection>
      <NavSection id="plan"><PlanSection params={params ?? []} /></NavSection>
      <NavSection id="results"><ResultsSection /></NavSection>
    </StagePage>
  );
}
