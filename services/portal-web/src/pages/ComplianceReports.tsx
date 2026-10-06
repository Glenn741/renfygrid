import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiError, type ComplianceReport, generateComplianceReport, getComplianceReport, getComplianceReports, markComplianceReportSent } from "../api";
import { StagePage, EmptyState } from "../components/StagePage";

// Informe de cumplimiento al ente rector (Track D, D12.3). La junta genera
// una foto del periodo y decide enviarla; el ente rector no entra al sistema.

function errText(err: unknown, fallback: string) {
  return err instanceof ApiError ? err.message : fallback;
}

function isoDay(d: Date) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

function n(v: number | null | undefined, suffix = "") {
  return v === null || v === undefined ? "—" : `${v.toLocaleString("es")}${suffix}`;
}

/* eslint-disable @typescript-eslint/no-explicit-any */
function SectionBody({ detector, data }: { detector: string; data: any }) {
  if (detector === "lab_quality") {
    if (!data.samples.length) return <p className="text-sm text-slate-500">Sin análisis de laboratorio en el periodo.</p>;
    return (
      <>
        <p className="text-sm">{data.summary.samples} muestras · {data.summary.results} resultados · {data.summary.out_of_range} fuera de rango ({data.summary.critical} críticos) · {data.summary.without_rule} sin valor de referencia</p>
        <table className="mt-2 w-full text-xs">
          <thead><tr className="border-b text-left text-slate-500"><th className="py-1 pr-2">Fecha</th><th className="pr-2">Punto</th><th className="pr-2">Laboratorio / informe</th><th className="pr-2">Parámetro</th><th className="pr-2">Resultado</th><th>Interpretación (fuente)</th></tr></thead>
          <tbody>
            {data.samples.flatMap((s: any, i: number) => s.results.map((r: any, j: number) => (
              <tr key={`${i}-${j}`} className="border-b border-slate-100 align-top">
                <td className="py-1 pr-2 whitespace-nowrap">{new Date(s.sampled_at).toLocaleDateString("es")}</td>
                <td className="pr-2">{s.point ?? "—"}</td>
                <td className="pr-2">{s.laboratory}{s.report_ref ? ` · ${s.report_ref}` : ""}</td>
                <td className="pr-2">{r.parameter}</td>
                <td className="pr-2 whitespace-nowrap">{r.qualifier !== "=" ? r.qualifier : ""}{n(r.value)} {r.unit}</td>
                <td>{r.interpretation ?? "Sin valor de referencia"}{r.rule_source ? <span className="block text-slate-500">{r.rule_source}</span> : null}</td>
              </tr>
            )))}
          </tbody>
        </table>
      </>
    );
  }
  if (detector === "field_readings") {
    if (!data.total) return <p className="text-sm text-slate-500">Sin mediciones de {data.parameter?.label ?? "campo"} en el periodo.</p>;
    return (
      <table className="w-full text-xs">
        <thead><tr className="border-b text-left text-slate-500"><th className="py-1 pr-2">Tipo de punto</th><th className="pr-2">Mediciones</th><th className="pr-2">Dentro del rango</th><th className="pr-2">Mínimo</th><th>Máximo</th></tr></thead>
        <tbody>
          {data.by_point_kind.map((k: any) => (
            <tr key={k.kind} className="border-b border-slate-100">
              <td className="py-1 pr-2">{k.label}</td><td className="pr-2">{k.n}</td><td className="pr-2">{k.in_range} ({n(k.in_range_pct, " %")})</td>
              <td className="pr-2">{n(k.min)} {data.parameter.unit}</td><td>{n(k.max)} {data.parameter.unit}</td>
            </tr>
          ))}
        </tbody>
      </table>
    );
  }
  if (detector === "sampling_plan") {
    if (!data.items.length) return <p className="text-sm text-slate-500">La junta no tiene plan de muestreo registrado.</p>;
    return (
      <>
        <p className="text-sm">Cumplimiento: {n(data.compliance_pct, " %")} ({data.taken} tomadas de {data.expected} esperadas)</p>
        <ul className="mt-1 text-xs">{data.items.map((i: any) => <li key={i.item_id}>{i.name} — cada {i.frequency_days} días: {i.taken} de {i.expected}{i.source_note ? ` · ${i.source_note}` : ""}</li>)}</ul>
      </>
    );
  }
  if (detector === "alerts_emergencies") {
    return (
      <>
        <p className="text-sm">{data.out_of_range_alerts} resultados fuera de rango en el periodo; {data.alerts_closed} cerrados.</p>
        {data.emergencies.length === 0 ? <p className="text-xs text-slate-500">Sin emergencias activadas.</p>
          : <ul className="mt-1 text-xs">{data.emergencies.map((e: any, i: number) => <li key={i}>{e.label} — {new Date(e.activated_at).toLocaleString("es")} ({e.trigger === "auto" ? "automática" : "manual"}){e.closed_at ? `, cerrada ${new Date(e.closed_at).toLocaleDateString("es")}` : ", activa"}</li>)}</ul>}
      </>
    );
  }
  if (detector === "maintenance_calendar") {
    return <p className="text-sm">Cumplimiento del calendario anual: {n(data.compliance_pct, " %")} ({data.done} de {data.expected} actividades)</p>;
  }
  if (detector === "sanitation") {
    return (
      <ul className="text-sm">
        <li>{data.interventions} intervenciones de saneamiento; {n(data.sludge_m3)} m³ de lodos retirados; destino verificado en {data.destination_verified} ({data.pending_verification} por verificar)</li>
        {data.sludge_overdue.length > 0 && <li>Retiro de lodos pendiente: {data.sludge_overdue.join(", ")}</li>}
        {data.open_discharges.length > 0 && <li>Descargas productivas sin controlar: {data.open_discharges.join(", ")}</li>}
      </ul>
    );
  }
  return <pre className="text-xs">{JSON.stringify(data, null, 2)}</pre>;
}
/* eslint-enable @typescript-eslint/no-explicit-any */

function ReportView({ id, onClose }: { id: string; onClose: () => void }) {
  const qc = useQueryClient();
  const { data } = useQuery({ queryKey: ["compliance-report", id], queryFn: () => getComplianceReport(id) });
  const [f, setF] = useState({ sent_to: "", sent_on: isoDay(new Date()), note: "" });
  const [msg, setMsg] = useState<string | null>(null);
  const sent = useMutation({
    mutationFn: () => markComplianceReportSent(id, f),
    onSuccess: () => { setMsg(null); qc.invalidateQueries({ queryKey: ["compliance-report", id] }); qc.invalidateQueries({ queryKey: ["compliance-reports"] }); },
    onError: (e) => setMsg(errText(e, "No se pudo registrar.")),
  });
  if (!data?.content) return null;
  const c = data.content;
  const download = () => {
    const blob = new Blob([JSON.stringify(c, null, 2)], { type: "application/json" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `informe-${c.organization}-${c.period.from}-${c.period.to}.json`;
    a.click();
  };
  return (
    <section className="mb-6 rounded-xl border border-slate-200 bg-white p-6 print:border-0 print:p-0">
      <div className="mb-3 flex flex-wrap gap-2 print:hidden">
        <button onClick={() => window.print()} className="rounded-lg bg-indigo-600 px-3 py-1.5 text-sm font-semibold text-white">Imprimir / guardar PDF</button>
        <button onClick={download} className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm">Descargar datos (JSON)</button>
        <button onClick={onClose} className="ml-auto text-sm text-slate-500">Cerrar</button>
      </div>
      <h2 className="text-lg font-semibold text-slate-900">{c.template.title}</h2>
      <p className="text-sm text-slate-700">{c.organization} · periodo {new Date(c.period.from + "T00:00").toLocaleDateString("es")} al {new Date(c.period.to + "T00:00").toLocaleDateString("es")}</p>
      <p className="text-xs text-slate-500">Generado {new Date(c.generated_at).toLocaleString("es")} por {c.generated_by.replace(/^portal:/, "")} · dirigido a: {c.template.recipient}</p>
      <p className="mt-2 rounded-lg border border-amber-200 bg-amber-50 p-2 text-xs text-amber-900">{c.template.format_note}</p>
      {c.sections.map((s) => (
        <div key={s.code} className="mt-4 break-inside-avoid">
          <h3 className="text-sm font-semibold text-slate-900">{s.title}</h3>
          <p className="mb-1 text-xs text-slate-500">{s.description}</p>
          <SectionBody detector={s.detector} data={s.data} />
        </div>
      ))}
      <div className="mt-6 border-t border-slate-200 pt-3 text-sm">
        {data.sent_on ? (
          <p className="text-emerald-700">Enviado a {data.sent_to} el {new Date(data.sent_on + "T00:00").toLocaleDateString("es")} por {data.sent_by?.replace(/^portal:/, "")}{data.sent_note ? ` · ${data.sent_note}` : ""}</p>
        ) : (
          <div className="flex flex-wrap gap-2 print:hidden">
            <input aria-label="Enviado a" className="min-w-[14rem] flex-1 rounded-lg border border-slate-300 px-3 py-1.5" placeholder="Enviado a (ARCA, GAD…)" value={f.sent_to} onChange={(e) => setF({ ...f, sent_to: e.target.value })} />
            <input aria-label="Fecha de envío" type="date" className="rounded-lg border border-slate-300 px-2 py-1.5" value={f.sent_on} onChange={(e) => setF({ ...f, sent_on: e.target.value })} />
            <input aria-label="Nota" className="rounded-lg border border-slate-300 px-3 py-1.5" placeholder="N.º de oficio u observación" value={f.note} onChange={(e) => setF({ ...f, note: e.target.value })} />
            <button onClick={() => sent.mutate()} disabled={!f.sent_to.trim()} className="rounded-lg border border-indigo-300 px-3 py-1.5 font-semibold text-indigo-700 disabled:opacity-50">Registrar envío</button>
            {msg && <p className="w-full text-red-600">{msg}</p>}
          </div>
        )}
      </div>
    </section>
  );
}

export function ComplianceReportsPage() {
  const qc = useQueryClient();
  const { data, error } = useQuery({ queryKey: ["compliance-reports"], queryFn: getComplianceReports, retry: false });
  const today = new Date();
  const monthAgo = new Date(today.getFullYear(), today.getMonth() - 1, today.getDate());
  const [period, setPeriod] = useState({ from: isoDay(monthAgo), to: isoDay(today) });
  const [open, setOpen] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const gen = useMutation({
    mutationFn: (code: string) => generateComplianceReport({ report_code: code, period_from: period.from, period_to: period.to }),
    onSuccess: (r: ComplianceReport) => { setMsg(null); setOpen(r.report_id); qc.invalidateQueries({ queryKey: ["compliance-reports"] }); },
    onError: (e) => setMsg(errText(e, "No se pudo generar.")),
  });
  if (error) return <StagePage title="Informe de cumplimiento"><p className="text-sm text-amber-800">{errText(error, "")}</p></StagePage>;
  if (!data) return <StagePage title="Informe de cumplimiento"><p className="text-sm text-slate-500">Cargando…</p></StagePage>;
  return (
    <StagePage title="Informe de cumplimiento">
      {open && <ReportView id={open} onClose={() => setOpen(null)} />}
      <div className="print:hidden">
        {data.templates.length === 0 && <EmptyState message="Ningún paquete adoptado trae un informe de cumplimiento." />}
        {data.templates.map((t) => (
          <section key={t.pack_id + t.code} className="mb-6 rounded-xl border border-slate-200 bg-white p-5">
            <h2 className="text-base font-semibold text-slate-900">{t.title}</h2>
            <p className="mt-1 max-w-3xl text-sm text-slate-600">{t.purpose}</p>
            <p className="mt-1 text-xs text-amber-800">{t.format_note}</p>
            <p className="mt-2 text-xs text-slate-500">Incluye: {t.sections.map((s) => s.title).join(" · ")}</p>
            <div className="mt-3 flex flex-wrap items-center gap-2 text-sm">
              <label>Desde <input type="date" className="rounded-lg border border-slate-300 px-2 py-1" value={period.from} onChange={(e) => setPeriod({ ...period, from: e.target.value })} /></label>
              <label>hasta <input type="date" className="rounded-lg border border-slate-300 px-2 py-1" value={period.to} onChange={(e) => setPeriod({ ...period, to: e.target.value })} /></label>
              <button onClick={() => gen.mutate(t.code)} disabled={gen.isPending} className="rounded-lg bg-indigo-600 px-3 py-1.5 font-semibold text-white disabled:opacity-50">Generar informe</button>
            </div>
            {msg && <p className="mt-1 text-sm text-red-600">{msg}</p>}
          </section>
        ))}
        <section className="rounded-xl border border-slate-200 bg-white p-5">
          <h2 className="mb-2 text-base font-semibold text-slate-900">Informes generados</h2>
          <p className="mb-2 text-xs text-slate-500">Cada informe es una foto de lo que el sistema tenía al generarlo; no cambia después. Si algo cambia, genere otro.</p>
          {data.reports.length === 0 ? <EmptyState message="Todavía no hay informes." /> : (
            <ul className="divide-y divide-slate-100">
              {data.reports.map((r) => (
                <li key={r.report_id} className="flex flex-wrap items-center gap-3 py-2 text-sm">
                  <span className="flex-1">{r.title} · {new Date(r.period_from + "T00:00").toLocaleDateString("es")} – {new Date(r.period_to + "T00:00").toLocaleDateString("es")}
                    <span className="block text-xs text-slate-500">Generado {new Date(r.generated_at).toLocaleString("es")} por {r.generated_by.replace(/^portal:/, "")}</span></span>
                  {r.sent_on ? <span className="rounded-full bg-emerald-50 px-2 py-0.5 text-[11px] font-semibold text-emerald-700">Enviado a {r.sent_to}</span>
                    : <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[11px] font-semibold text-slate-600">No enviado</span>}
                  <button onClick={() => setOpen(r.report_id)} className="text-xs font-semibold text-indigo-700 hover:underline">Ver</button>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </StagePage>
  );
}
