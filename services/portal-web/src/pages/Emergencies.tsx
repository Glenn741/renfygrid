import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ApiError,
  activateEmergency,
  addEmergencyContact,
  closeEmergency,
  deleteEmergencyContact,
  getEmergencyActivations,
  getEmergencyPlan,
  reviewEmergencyPlan,
  saveEmergencyPlanEntry,
  type EmergencyEntry,
} from "../api";
import { StagePage, EmptyState } from "../components/StagePage";
import { NavSection, SectionNav } from "../components/SectionNav";
import { sectionsFor } from "../navigation";
import { appLocale, isoDay, term } from "../catalog";

// Plan de emergencia (Track D, D5; Guia 3 §3.11 y Actividad participativa 6).
// "Las emergencias no se improvisan": quien activa, quien comunica, que se
// hace primero y a que institucion se informa. El plan parte del catalogo del
// paquete y cada junta lo ajusta. Una emergencia se activa a mano o sola (E.
// coli presente -> contaminacion).

const SECTIONS = sectionsFor("/emergencies");
const KEY = ["emergency-plan"];

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

function useRefresh() {
  const qc = useQueryClient();
  return () => { for (const k of [KEY, ["emergency-activations"], ["operations-today"]]) qc.invalidateQueries({ queryKey: k }); };
}

function ActiveSection() {
  const refresh = useRefresh();
  const { data, error } = useQuery({ queryKey: KEY, queryFn: getEmergencyPlan, retry: false });
  const [closing, setClosing] = useState<string | null>(null);
  const [notes, setNotes] = useState("");
  const [choice, setChoice] = useState("");
  const [why, setWhy] = useState("");
  const [msg, setMsg] = useState<string | null>(null);
  const close = useMutation({
    mutationFn: (id: string) => closeEmergency(id, notes || null),
    onSuccess: () => { setClosing(null); setNotes(""); refresh(); },
    onError: (err) => setMsg(errText(err, "No se pudo cerrar.")),
  });
  const activate = useMutation({
    mutationFn: () => {
      const e = data!.entries.find((x) => (x.type_code ?? x.entry_id) === choice)!;
      return activateEmergency({ type_code: e.type_code, plan_entry_id: e.type_code ? null : e.entry_id, notes: why || null });
    },
    onSuccess: (a) => { setWhy(""); setMsg(a.duplicate ? `${a.label} ya estaba activa: se anotó el nuevo aviso.` : `${a.label} activada.`); refresh(); },
    onError: (err) => setMsg(errText(err, "No se pudo activar.")),
  });
  if (error) return <Card title="Emergencias activas"><p className="text-sm text-amber-800">{errText(error, "")}</p></Card>;
  if (!data) return null;
  const entryFor = (typeCode: string | null, entryId: string | null) =>
    data.entries.find((e) => (typeCode ? e.type_code === typeCode : e.entry_id === entryId));
  return (
    <Card title="Emergencias activas" description="Lo que está pasando ahora y qué dice el plan que hay que hacer.">
      {data.active.length === 0 && <EmptyState message="No hay emergencias activas." />}
      <div className="space-y-3">
        {data.active.map((a) => {
          const e = entryFor(a.type_code, a.plan_entry_id);
          return (
            <article key={a.activation_id} className="rounded-xl border-2 border-red-300 bg-red-50 p-4">
              <div className="flex flex-wrap items-baseline justify-between gap-2">
                <h3 className="text-base font-bold text-red-900">{a.label}</h3>
                <span className="text-xs text-red-800">
                  {a.trigger === "auto" ? "Activada automáticamente" : `Activada por ${a.activated_by.replace(/^portal:/, "")}`} · {new Date(a.activated_at).toLocaleString(appLocale())}
                </span>
              </div>
              {e && (
                <dl className="mt-2 grid gap-2 text-sm text-slate-800 sm:grid-cols-2">
                  <div><dt className="text-xs font-semibold text-slate-500">Primera acción</dt><dd>{e.first_action}</dd></div>
                  <div><dt className="text-xs font-semibold text-slate-500">Responsable</dt><dd>{e.responsible ?? "—"}</dd></div>
                  <div><dt className="text-xs font-semibold text-slate-500">Mensaje a la comunidad</dt>
                    <dd>{e.community_message ?? <span className="text-amber-800">Sin mensaje en el plan: defínalo abajo.</span>}
                      {e.community_message && (
                        <button onClick={() => navigator.clipboard?.writeText(e.community_message!)} className="ml-2 text-xs font-semibold text-indigo-700 hover:underline">Copiar</button>
                      )}
                    </dd>
                  </div>
                  <div><dt className="text-xs font-semibold text-slate-500">A quién avisar</dt><dd>{e.external_support ?? e.notify}</dd></div>
                </dl>
              )}
              {a.notes && <p className="mt-2 whitespace-pre-line text-xs text-slate-600">{a.notes}</p>}
              {closing === a.activation_id ? (
                <div className="mt-3 flex flex-wrap gap-2">
                  <input aria-label="Cómo se resolvió" className="min-w-[14rem] flex-1 rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm" placeholder="Cómo se resolvió" value={notes} onChange={(ev) => setNotes(ev.target.value)} />
                  <button onClick={() => close.mutate(a.activation_id)} className="rounded-lg bg-emerald-600 px-3 py-1.5 text-sm font-semibold text-white">Cerrar emergencia</button>
                  <button onClick={() => setClosing(null)} className="px-2 text-sm text-slate-500">Cancelar</button>
                </div>
              ) : (
                <button onClick={() => setClosing(a.activation_id)} className="mt-3 rounded-lg border border-red-300 bg-white px-3 py-1.5 text-sm font-semibold text-red-800 hover:bg-red-100">Dar por resuelta</button>
              )}
            </article>
          );
        })}
      </div>
      <div className="mt-4 flex flex-wrap items-end gap-2 rounded-lg border border-dashed border-slate-300 bg-slate-50 p-3">
        <select aria-label="Emergencia" className="rounded-lg border border-slate-300 bg-white px-2 py-1.5 text-sm" value={choice} onChange={(e) => setChoice(e.target.value)}>
          <option value="">— Activar una emergencia —</option>
          {data.entries.filter((e) => e.active).map((e) => <option key={e.type_code ?? e.entry_id!} value={(e.type_code ?? e.entry_id)!}>{e.label}</option>)}
        </select>
        <input aria-label="Qué se observó" className="min-w-[14rem] flex-1 rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm" placeholder="Qué se observó" value={why} onChange={(e) => setWhy(e.target.value)} />
        <button onClick={() => activate.mutate()} disabled={!choice || activate.isPending} className="rounded-lg bg-red-600 px-3 py-1.5 text-sm font-semibold text-white hover:bg-red-700 disabled:opacity-50">Activar</button>
        {msg && <p className="w-full text-sm text-slate-700">{msg}</p>}
      </div>
    </Card>
  );
}

function EntryEditor({ entry, onDone }: { entry: EmergencyEntry; onDone: () => void }) {
  const refresh = useRefresh();
  const [f, setF] = useState({ responsible: entry.responsible ?? "", first_action: entry.first_action ?? "", community_message: entry.community_message ?? "",
    external_support: entry.external_support ?? "", resources: entry.resources ?? "" });
  const [err, setErr] = useState<string | null>(null);
  const save = useMutation({
    mutationFn: () => saveEmergencyPlanEntry(entry.type_code ? { type_code: entry.type_code, ...f } : { custom_label: entry.label, ...f }),
    onSuccess: () => { refresh(); onDone(); },
    onError: (e) => setErr(errText(e, "No se pudo guardar.")),
  });
  const field = (k: keyof typeof f, label: string) => (
    <label className="block text-xs text-slate-600">{label}
      <textarea rows={2} className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-1.5 text-sm" value={f[k]} onChange={(e) => setF({ ...f, [k]: e.target.value })} />
    </label>
  );
  return (
    <div className="mt-2 grid gap-2 sm:grid-cols-2">
      {field("responsible", "Responsable")}{field("first_action", "Primera acción")}{field("community_message", "Mensaje a la comunidad")}
      {field("external_support", "Apoyo externo")}{field("resources", "Recursos necesarios")}
      <div className="flex items-end gap-2">
        <button onClick={() => save.mutate()} className="rounded-lg bg-indigo-600 px-3 py-1.5 text-sm font-semibold text-white">Guardar</button>
        <button onClick={onDone} className="px-2 text-sm text-slate-500">Cancelar</button>
        {err && <span className="text-sm text-red-600">{err}</span>}
      </div>
    </div>
  );
}

function PlanSection() {
  const refresh = useRefresh();
  const { data } = useQuery({ queryKey: KEY, queryFn: getEmergencyPlan, retry: false });
  const [editing, setEditing] = useState<string | null>(null);
  const [custom, setCustom] = useState("");
  const [reviewNotes, setReviewNotes] = useState("");
  const [msg, setMsg] = useState<string | null>(null);
  const addCustom = useMutation({
    mutationFn: () => saveEmergencyPlanEntry({ custom_label: custom }),
    onSuccess: () => { setCustom(""); refresh(); },
    onError: (e) => setMsg(errText(e, "No se pudo agregar.")),
  });
  const review = useMutation({
    mutationFn: () => reviewEmergencyPlan({ reviewed_on: isoDay(), notes: reviewNotes || null }),
    onSuccess: () => { setReviewNotes(""); refresh(); },
    onError: (e) => setMsg(errText(e, "No se pudo registrar.")),
  });
  if (!data) return null;
  return (
    <Card title="Plan de emergencia" description="Para cada emergencia: señales, primera acción segura, quién la activa, el mensaje a la comunidad y la institución que apoya. Ajústelo a su sistema.">
      <div className={`mb-4 rounded-lg border p-3 text-sm ${data.review.status === "ok" ? "border-emerald-200 bg-emerald-50 text-emerald-900" : "border-amber-200 bg-amber-50 text-amber-900"}`}>
        <strong>Revisión del plan:</strong> {data.review.last_reviewed_on ? `última el ${new Date(`${data.review.last_reviewed_on}T12:00:00`).toLocaleDateString(appLocale())}` : "todavía no se revisó"}
        {data.review.status === "overdue" && " · vencida"}
        {data.review.source && <span className="block text-xs opacity-80">{data.review.source}</span>}
        <span className="mt-2 flex flex-wrap gap-2">
          <input aria-label="Conclusión" className="min-w-[14rem] flex-1 rounded-lg border border-slate-300 bg-white px-3 py-1 text-sm text-slate-800" placeholder="Qué se revisó" value={reviewNotes} onChange={(e) => setReviewNotes(e.target.value)} />
          <button onClick={() => review.mutate()} className="rounded-lg bg-indigo-600 px-3 py-1 text-sm font-semibold text-white">Registrar revisión de hoy</button>
        </span>
      </div>
      <div className="space-y-3">
        {data.entries.map((e) => {
          const key = (e.type_code ?? e.entry_id)!;
          return (
            <article key={key} className="rounded-lg border border-slate-200 p-3">
              <div className="flex flex-wrap items-baseline justify-between gap-2">
                <h3 className="text-sm font-semibold text-slate-900">{e.label}{e.customized && <span className="ml-2 rounded-full bg-indigo-50 px-2 py-0.5 text-[11px] font-semibold text-indigo-700">ajustado</span>}</h3>
                {editing !== key && <button onClick={() => setEditing(key)} className="text-xs font-medium text-indigo-700 hover:underline">Ajustar</button>}
              </div>
              {e.signals && <p className="text-xs text-slate-500">Señales: {e.signals}</p>}
              {editing === key ? <EntryEditor entry={e} onDone={() => setEditing(null)} /> : (
                <dl className="mt-1 grid gap-x-4 gap-y-1 text-xs text-slate-700 sm:grid-cols-2">
                  <div><dt className="inline font-semibold">Primera acción: </dt><dd className="inline">{e.first_action ?? "—"}</dd></div>
                  <div><dt className="inline font-semibold">Responsable: </dt><dd className="inline">{e.responsible ?? "—"}</dd></div>
                  <div><dt className="inline font-semibold">Mensaje: </dt><dd className="inline">{e.community_message ?? <span className="text-amber-700">sin definir</span>}</dd></div>
                  <div><dt className="inline font-semibold">Avisar a: </dt><dd className="inline">{e.external_support ?? e.notify ?? "—"}</dd></div>
                  {e.resources && <div><dt className="inline font-semibold">Recursos: </dt><dd className="inline">{e.resources}</dd></div>}
                </dl>
              )}
            </article>
          );
        })}
      </div>
      <div className="mt-3 flex flex-wrap gap-2">
        <input aria-label="Emergencia propia" className="min-w-[14rem] flex-1 rounded-lg border border-slate-300 px-3 py-1.5 text-sm" placeholder="Agregar una emergencia propia (p. ej. incendio forestal)" value={custom} onChange={(e) => setCustom(e.target.value)} />
        <button onClick={() => addCustom.mutate()} disabled={!custom.trim()} className="rounded-lg border border-indigo-300 px-3 py-1.5 text-sm font-medium text-indigo-700 disabled:opacity-50">Agregar</button>
        {msg && <p className="w-full text-sm text-red-600">{msg}</p>}
      </div>
    </Card>
  );
}

function ContactsSection() {
  const refresh = useRefresh();
  const { data } = useQuery({ queryKey: KEY, queryFn: getEmergencyPlan, retry: false });
  const [f, setF] = useState({ institution: "", person: "", phone: "" });
  const [msg, setMsg] = useState<string | null>(null);
  const add = useMutation({
    mutationFn: () => addEmergencyContact({ institution: f.institution, phone: f.phone, person: f.person || null }),
    onSuccess: () => { setF({ institution: "", person: "", phone: "" }); setMsg(null); refresh(); },
    onError: (e) => setMsg(errText(e, "No se pudo agregar.")),
  });
  const del = useMutation({ mutationFn: deleteEmergencyContact, onSuccess: refresh });
  return (
    <Card title="Contactos institucionales" description={`Números a mano para operación y dirección: ${term("local_government")}, ${term("health_authority")}, ${term("regulator")}, ${term("civil_protection")}, ${term("emergency_line")}, técnico de apoyo.`}>
      {data && data.contacts.length === 0 && <EmptyState message="Todavía no hay contactos." />}
      <ul className="divide-y divide-slate-100">
        {(data?.contacts ?? []).map((c) => (
          <li key={c.contact_id} className="flex flex-wrap items-center gap-3 py-2 text-sm">
            <span className="flex-1 text-slate-800">{c.institution}{c.person && <span className="text-slate-500"> · {c.person}</span>}</span>
            <a href={`tel:${c.phone.replace(/\s/g, "")}`} className="font-semibold text-indigo-700 tabular-nums">{c.phone}</a>
            <button onClick={() => del.mutate(c.contact_id)} className="text-xs text-slate-500 hover:text-red-700">Quitar</button>
          </li>
        ))}
      </ul>
      <div className="mt-3 grid gap-2 sm:grid-cols-[1fr_1fr_10rem_auto]">
        <input aria-label="Institución" className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm" placeholder="Institución" value={f.institution} onChange={(e) => setF({ ...f, institution: e.target.value })} />
        <input aria-label="Persona" className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm" placeholder="Persona (opcional)" value={f.person} onChange={(e) => setF({ ...f, person: e.target.value })} />
        <input aria-label="Teléfono" type="tel" className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm" placeholder="Teléfono" value={f.phone} onChange={(e) => setF({ ...f, phone: e.target.value })} />
        <button onClick={() => add.mutate()} disabled={!f.institution.trim() || !f.phone.trim()} className="rounded-lg bg-indigo-600 px-3 py-1.5 text-sm font-semibold text-white disabled:opacity-50">Agregar</button>
        {msg && <p className="text-sm text-red-600 sm:col-span-4">{msg}</p>}
      </div>
    </Card>
  );
}

function HistorySection() {
  const { data } = useQuery({ queryKey: ["emergency-activations"], queryFn: getEmergencyActivations });
  return (
    <Card title="Historial de emergencias">
      {data && data.length === 0 && <EmptyState message="Sin emergencias registradas." />}
      <ul className="divide-y divide-slate-100">
        {(data ?? []).map((a) => (
          <li key={a.activation_id} className="py-2 text-sm text-slate-700">
            <strong>{a.label}</strong> · {new Date(a.activated_at).toLocaleString(appLocale())} · {a.trigger === "auto" ? "automática" : "manual"} ·{" "}
            {a.status === "active" ? <span className="font-semibold text-red-700">activa</span> : `resuelta ${a.closed_at ? new Date(a.closed_at).toLocaleDateString(appLocale()) : ""}`}
            {a.closing_notes && <span className="block text-xs text-slate-500">{a.closing_notes}</span>}
          </li>
        ))}
      </ul>
    </Card>
  );
}

export function EmergenciesPage() {
  return (
    <StagePage title="Emergencias">
      <SectionNav items={SECTIONS} />
      <NavSection id="active"><ActiveSection /></NavSection>
      <NavSection id="plan"><PlanSection /></NavSection>
      <NavSection id="contacts"><ContactsSection /></NavSection>
      <NavSection id="history"><HistorySection /></NavSection>
    </StagePage>
  );
}
