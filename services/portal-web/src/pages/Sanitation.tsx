import { useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiError, addDischargeFollowup, createDischarge, getSanitation, verifySanitationDestination } from "../api";
import { StagePage, EmptyState } from "../components/StagePage";
import { NavSection, SectionNav } from "../components/SectionNav";
import { sectionsFor } from "../navigation";

// Saneamiento (Track D, D6; Guia 3 §3.7-3.8, AP5, ficha 7F). "El agua potable
// entra segura a la casa. El saneamiento evita que el agua usada salga
// contaminando a la comunidad."

const SECTIONS = sectionsFor("/sanitation");
const KEY = ["sanitation"];
const DSTATUS: Record<string, { label: string; cls: string }> = {
  identified: { label: "Identificada", cls: "bg-amber-50 text-amber-800" },
  agreement: { label: "Con acuerdo", cls: "bg-indigo-50 text-indigo-700" },
  controlled: { label: "Controlada", cls: "bg-emerald-50 text-emerald-700" },
  closed: { label: "Cerrada", cls: "bg-slate-100 text-slate-600" },
};

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

function day(iso: string | null) {
  return iso ? new Date(iso).toLocaleDateString("es") : "—";
}

function ComponentsSection() {
  const { data, error } = useQuery({ queryKey: KEY, queryFn: getSanitation, retry: false });
  if (error) return <Card title="Componentes de saneamiento"><p className="text-sm text-amber-800">{errText(error, "")}</p></Card>;
  if (!data) return null;
  return (
    <Card title="Componentes de saneamiento" description={data.sludge_rule ? data.sludge_rule.source : undefined}>
      {data.components.length === 0 && <EmptyState message="No hay componentes de saneamiento registrados en el Gemelo Digital." />}
      <ul className="divide-y divide-slate-100">
        {data.components.map((c) => (
          <li key={c.asset_id} className="flex flex-wrap items-center gap-3 py-2 text-sm">
            <span className="flex-1 text-slate-800">{c.type_label}{c.name ? ` · ${c.name}` : ""}
              <span className="block text-xs text-slate-500">Última intervención: {day(c.last_intervention_at)}</span>
            </span>
            {c.sludge && (
              <span className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ${c.sludge.status === "ok" ? "bg-emerald-50 text-emerald-700" : "bg-red-50 text-red-700"}`}>
                {c.sludge.status === "never" ? "Sin retiro de lodos registrado" : c.sludge.status === "overdue" ? `Retiro de lodos vencido (último ${day(c.last_sludge_extraction_at)})` : `Lodos retirados ${day(c.last_sludge_extraction_at)}`}
              </span>
            )}
          </li>
        ))}
      </ul>
      <p className="mt-3 text-sm">
        <Link to="/maintenance#orders" className="font-semibold text-indigo-700 hover:underline">Programar limpieza o retiro de lodos ›</Link>
        <span className="mx-2 text-slate-300">·</span>
        <Link to="/inspections/G3" className="font-semibold text-indigo-700 hover:underline">Aplicar la lista 7E de saneamiento ›</Link>
      </p>
    </Card>
  );
}

function RegisterSection() {
  const qc = useQueryClient();
  const { data } = useQuery({ queryKey: KEY, queryFn: getSanitation, retry: false });
  const [msg, setMsg] = useState<string | null>(null);
  const verify = useMutation({
    mutationFn: verifySanitationDestination,
    onSuccess: () => { setMsg(null); qc.invalidateQueries({ queryKey: KEY }); },
    onError: (e) => setMsg(errText(e, "No se pudo verificar.")),
  });
  if (!data) return null;
  return (
    <Card title="Registro de limpieza, lodos y saneamiento (7F)" description="Cada intervención en una caja, fosa o planta: quién retiró los residuos y a qué sitio seguro fueron llevados. La directiva verifica el destino seguro.">
      {data.register_7f.length === 0 && <EmptyState message="Todavía no hay intervenciones de saneamiento cerradas." />}
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead><tr className="border-b border-slate-200 text-left text-xs uppercase tracking-wide text-slate-500">
            <th className="py-2 pr-3">Fecha</th><th className="py-2 pr-3">Componente</th><th className="py-2 pr-3">Actividad</th>
            <th className="py-2 pr-3">Retiró</th><th className="py-2 pr-3">Destino seguro</th><th className="py-2">Verificación</th></tr></thead>
          <tbody>
            {data.register_7f.map((e) => (
              <tr key={e.order_id} className="border-b border-slate-100 align-top last:border-0">
                <td className="py-2 pr-3 whitespace-nowrap">{day(e.closed_at)}</td>
                <td className="py-2 pr-3">{e.component}</td>
                <td className="py-2 pr-3">{e.activity ?? "—"}{e.sludge_volume_m3 !== null && <span className="block text-xs text-slate-500">{e.sludge_volume_m3} m³ de lodos</span>}</td>
                <td className="py-2 pr-3">{e.waste_handler ?? "—"}</td>
                <td className="py-2 pr-3">{e.waste_destination ?? <span className="text-xs text-slate-400">no aplica</span>}</td>
                <td className="py-2">
                  {e.verified_by ? <span className="text-xs text-emerald-700">Verificado por {e.verified_by.replace(/^portal:/, "")}</span>
                    : e.needs_verification ? <button onClick={() => verify.mutate(e.order_id)} className="rounded-lg bg-indigo-600 px-2 py-1 text-xs font-semibold text-white">Verificar destino</button>
                    : <span className="text-xs text-slate-400">—</span>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {msg && <p className="mt-2 text-sm text-red-600">{msg}</p>}
    </Card>
  );
}

function DischargesSection() {
  const qc = useQueryClient();
  const { data } = useQuery({ queryKey: KEY, queryFn: getSanitation, retry: false });
  const [f, setF] = useState({ activity_code: "cheese_factory", name: "", owner: "", location_text: "", problem: "" });
  const [note, setNote] = useState<Record<string, { note: string; status: string; agreement: string }>>({});
  const [msg, setMsg] = useState<string | null>(null);
  const refresh = () => qc.invalidateQueries({ queryKey: KEY });
  const create = useMutation({
    mutationFn: () => createDischarge(f),
    onSuccess: () => { setF({ ...f, name: "", owner: "", location_text: "", problem: "" }); setMsg(null); refresh(); },
    onError: (e) => setMsg(errText(e, "No se pudo registrar.")),
  });
  const follow = useMutation({
    mutationFn: (id: string) => addDischargeFollowup(id, { note: note[id].note, new_status: note[id].status || null, agreement: note[id].agreement || null }),
    onSuccess: (_, id) => { setNote({ ...note, [id]: { note: "", status: "", agreement: "" } }); refresh(); },
    onError: (e) => setMsg(errText(e, "No se pudo guardar el seguimiento.")),
  });
  if (!data) return null;
  return (
    <Card title="Descargas productivas" description="Queseras, chancheras, camales, lavanderías, textileras u otras actividades que descargan a la red o cerca de la fuente. La DBO y la DQO las analiza un laboratorio y las interpreta personal técnico.">
      {data.discharges.length === 0 && <EmptyState message="Sin descargas productivas registradas." />}
      <div className="space-y-3">
        {data.discharges.map((d) => {
          const n = note[d.discharge_id] ?? { note: "", status: "", agreement: "" };
          return (
            <article key={d.discharge_id} className="rounded-lg border border-slate-200 p-3">
              <div className="flex flex-wrap items-baseline justify-between gap-2">
                <h3 className="text-sm font-semibold text-slate-900">{d.name} <span className="font-normal text-slate-500">· {d.activity_label}{d.owner ? ` · ${d.owner}` : ""}</span></h3>
                <span className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ${DSTATUS[d.status].cls}`}>{DSTATUS[d.status].label}</span>
              </div>
              {d.location_text && <p className="text-xs text-slate-500">{d.location_text}</p>}
              {d.problem && <p className="mt-1 text-sm text-slate-700">{d.problem}</p>}
              {d.agreement && <p className="mt-1 text-sm text-indigo-800"><strong>Acuerdo:</strong> {d.agreement}</p>}
              {d.samples.map((s) => (
                <p key={s.sample_id} className="mt-1 text-xs text-slate-600">
                  Análisis {day(s.sampled_at)} ({s.laboratory}): DBO {s.bod5 ?? "—"} mg/L · DQO {s.cod ?? "—"} mg/L
                  {s.bod_cod_ratio !== null && <> · relación DBO/DQO <strong>{s.bod_cod_ratio}</strong> (pida interpretación técnica)</>}
                </p>
              ))}
              {d.followups.length > 0 && (
                <ul className="mt-2 border-l-2 border-slate-200 pl-3 text-xs text-slate-600">
                  {d.followups.map((x, i) => <li key={i}>{day(x.noted_at)} · {x.note}{x.new_status ? ` → ${DSTATUS[x.new_status].label}` : ""}</li>)}
                </ul>
              )}
              <div className="mt-2 grid gap-2 sm:grid-cols-[1fr_9rem_auto]">
                <input aria-label="Seguimiento" className="rounded-lg border border-slate-300 px-3 py-1 text-sm" placeholder="Seguimiento (visita, reunión, compromiso)" value={n.note}
                  onChange={(e) => setNote({ ...note, [d.discharge_id]: { ...n, note: e.target.value } })} />
                <select aria-label="Nuevo estado" className="rounded-lg border border-slate-300 px-2 py-1 text-sm" value={n.status}
                  onChange={(e) => setNote({ ...note, [d.discharge_id]: { ...n, status: e.target.value } })}>
                  <option value="">— mismo estado —</option>
                  {Object.entries(DSTATUS).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}
                </select>
                <button onClick={() => follow.mutate(d.discharge_id)} disabled={!n.note.trim()} className="rounded-lg border border-indigo-300 px-3 py-1 text-sm font-medium text-indigo-700 disabled:opacity-50">Anotar</button>
                {n.status === "agreement" && (
                  <input aria-label="Acuerdo" className="rounded-lg border border-slate-300 px-3 py-1 text-sm sm:col-span-3" placeholder="Texto del acuerdo" value={n.agreement}
                    onChange={(e) => setNote({ ...note, [d.discharge_id]: { ...n, agreement: e.target.value } })} />
                )}
              </div>
            </article>
          );
        })}
      </div>
      <div className="mt-4 grid gap-2 rounded-lg border border-dashed border-slate-300 bg-slate-50 p-3 sm:grid-cols-2">
        <select aria-label="Actividad" className="rounded-lg border border-slate-300 bg-white px-2 py-1.5 text-sm" value={f.activity_code} onChange={(e) => setF({ ...f, activity_code: e.target.value })}>
          {data.activities.map((a) => <option key={a.code} value={a.code}>{a.label}</option>)}
        </select>
        <input aria-label="Nombre" className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm" placeholder="Nombre del negocio" value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} />
        <input aria-label="Propietario" className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm" placeholder="Propietario" value={f.owner} onChange={(e) => setF({ ...f, owner: e.target.value })} />
        <input aria-label="Ubicación" className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm" placeholder="Ubicación" value={f.location_text} onChange={(e) => setF({ ...f, location_text: e.target.value })} />
        <input aria-label="Problema" className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm sm:col-span-2" placeholder="Problema observado" value={f.problem} onChange={(e) => setF({ ...f, problem: e.target.value })} />
        <button onClick={() => create.mutate()} disabled={!f.name.trim()} className="rounded-lg bg-indigo-600 px-3 py-1.5 text-sm font-semibold text-white disabled:opacity-50 sm:w-fit">Registrar descarga</button>
        {msg && <p className="text-sm text-red-600 sm:col-span-2">{msg}</p>}
      </div>
      <p className="mt-2 text-xs text-slate-500">Para registrar DBO/DQO: Calidad del agua → Registrar análisis (los análisis ligados a una descarga aparecen aquí).</p>
    </Card>
  );
}

export function SanitationPage() {
  return (
    <StagePage title="Saneamiento">
      <SectionNav items={SECTIONS} />
      <NavSection id="components"><ComponentsSection /></NavSection>
      <NavSection id="register"><RegisterSection /></NavSection>
      <NavSection id="discharges"><DischargesSection /></NavSection>
    </StagePage>
  );
}
