import { useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ApiError,
  createFinding,
  createNetworkAsset,
  getChecklistTemplates,
  getComponentTypes,
  getFindings,
  getSystemRoute,
  getTrafficLight,
  getTreatmentTrain,
  updateFinding,
  type ChecklistTemplate,
  type Finding,
  type RouteStage,
} from "../api";
import { StagePage, EmptyState } from "../components/StagePage";
import { NavSection, SectionNav } from "../components/SectionNav";

import { sectionsFor } from "../navigation";
// "Mi sistema" -- Track D, Sprint D0.3 (docs/04-plan-sprints.md SS11.4).
// Pantalla de operacion, no de formato: el recorrido, el semaforo, el tren
// de tratamiento y los hallazgos salen de lo que la junta registra. Los
// formatos de la guia (mapa tecnico, actividad 2, actividad 3) son la misma
// informacion vista como reporte. Ningun texto de aca depende de un pais:
// tipos, etiquetas y escalas vienen del paquete adoptado.

const SECTIONS = sectionsFor("/system");

const SERVICE_LABEL: Record<string, string> = { water: "Agua potable", sanitation: "Saneamiento", support: "Soporte" };
const STATUS_LABEL: Record<string, string> = { operational: "Operativo", maintenance: "En mantenimiento", out_of_service: "Fuera de servicio" };
const STATUS_DOT: Record<string, string> = { operational: "bg-emerald-500", maintenance: "bg-amber-500", out_of_service: "bg-red-500" };
const PRIORITY_LABEL: Record<string, string> = { high: "Alta", medium: "Media", low: "Baja" };
const PRIORITY_STYLE: Record<string, string> = {
  high: "bg-red-50 text-red-700", medium: "bg-amber-50 text-amber-700", low: "bg-slate-100 text-slate-600",
};
const FINDING_STATUS_LABEL: Record<string, string> = { open: "Abierto", in_progress: "En curso", closed: "Cerrado" };
const SOURCE_LABEL: Record<string, string> = {
  critical_point: "Punto crítico", checklist: "Lista de verificación", reading: "Lectura", manual: "Manual",
};
const SUPPORT_LABEL: Record<string, string> = {
  community: "La comunidad puede resolverlo", local_government: "Apoyo del gobierno local", specialized: "Asistencia especializada",
};

function SectionCard({ title, description, action, children }: {
  title: string; description: string; action?: React.ReactNode; children: React.ReactNode;
}) {
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-5 mb-6">
      <div className="flex flex-wrap items-start justify-between gap-3 mb-4">
        <div>
          <h2 className="text-base font-semibold text-slate-900">{title}</h2>
          <p className="text-sm text-slate-500 max-w-3xl">{description}</p>
        </div>
        {action}
      </div>
      {children}
    </section>
  );
}

function assetName(asset: RouteStage["assets"][number]): string | null {
  const name = asset.attributes?.name;
  return typeof name === "string" && name ? name : null;
}

function AddComponentForm() {
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [type, setType] = useState("");
  const [name, setName] = useState("");
  const [location, setLocation] = useState("");
  const [status, setStatus] = useState("operational");
  const [error, setError] = useState<string | null>(null);
  const { data: types } = useQuery({ queryKey: ["component-types"], queryFn: getComponentTypes });

  const mutation = useMutation({
    mutationFn: () => createNetworkAsset({
      type, status, attributes: { ...(name ? { name } : {}), ...(location ? { location } : {}) },
    }),
    onSuccess: () => {
      setError(null);
      setName("");
      setLocation("");
      setOpen(false);
      queryClient.invalidateQueries({ queryKey: ["system-route"] });
      queryClient.invalidateQueries({ queryKey: ["treatment-train"] });
      queryClient.invalidateQueries({ queryKey: ["network-assets"] });
    },
    onError: (err) => setError(err instanceof ApiError ? err.message : "No se pudo registrar el componente."),
  });

  if (!open) {
    return (
      <button onClick={() => setOpen(true)} className="rounded-lg bg-indigo-600 text-white text-xs font-semibold px-3 py-1.5 hover:bg-indigo-700">
        + Registrar componente
      </button>
    );
  }

  const grouped = ["water", "sanitation", "support"].map((service) => ({
    service, items: (types ?? []).filter((t) => t.service === service),
  }));

  return (
    <div className="w-full rounded-lg border border-slate-200 bg-slate-50 p-4">
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
        <div>
          <label htmlFor="comp-type" className="block text-xs font-medium text-slate-500 mb-1">Tipo</label>
          <select id="comp-type" className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm w-full bg-white" value={type} onChange={(e) => setType(e.target.value)}>
            <option value="">— Elegir —</option>
            {grouped.map((g) => (
              <optgroup key={g.service} label={SERVICE_LABEL[g.service]}>
                {g.items.map((t) => <option key={t.code} value={t.code}>{t.label}</option>)}
              </optgroup>
            ))}
          </select>
        </div>
        <div>
          <label htmlFor="comp-name" className="block text-xs font-medium text-slate-500 mb-1">Nombre (opcional)</label>
          <input id="comp-name" className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm w-full" value={name} onChange={(e) => setName(e.target.value)} placeholder="Captación vertiente El Molino" />
        </div>
        <div>
          <label htmlFor="comp-location" className="block text-xs font-medium text-slate-500 mb-1">Dónde está (opcional)</label>
          <input id="comp-location" className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm w-full" value={location} onChange={(e) => setLocation(e.target.value)} placeholder="Parte alta, junto a la quebrada" />
        </div>
        <div>
          <label htmlFor="comp-status" className="block text-xs font-medium text-slate-500 mb-1">Estado</label>
          <select id="comp-status" className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm w-full bg-white" value={status} onChange={(e) => setStatus(e.target.value)}>
            {Object.entries(STATUS_LABEL).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
        </div>
      </div>
      {error && <p className="text-sm text-red-600 mt-2">{error}</p>}
      <div className="mt-3 flex gap-2">
        <button onClick={() => mutation.mutate()} disabled={!type || mutation.isPending} className="rounded-lg bg-indigo-600 text-white text-xs font-semibold px-3 py-1.5 hover:bg-indigo-700 disabled:opacity-40">
          Registrar
        </button>
        <button onClick={() => setOpen(false)} className="text-xs text-slate-500 hover:text-slate-700 px-2">Cancelar</button>
      </div>
    </div>
  );
}

function RouteSection() {
  const { data, isLoading } = useQuery({ queryKey: ["system-route"], queryFn: getSystemRoute });
  const services = data ? Object.entries(data.services) : [];

  return (
    <SectionCard
      title="Recorrido del sistema"
      description="Los componentes en el orden en que pasa el agua, desde la fuente hasta las viviendas, y el camino del agua usada. Es la base del mapa técnico."
      action={<AddComponentForm />}
    >
      {isLoading && <p className="text-sm text-slate-500">Cargando…</p>}
      {data && services.length === 0 && data.accessories.length === 0 && (
        <EmptyState message="Todavía no hay componentes registrados. Empiece por la fuente y la captación." />
      )}
      <div className="space-y-5">
        {services.map(([service, stages]) => (
          <div key={service}>
            <div className="text-xs font-semibold uppercase tracking-wide text-slate-500 mb-2">{SERVICE_LABEL[service] ?? service}</div>
            <ol className="flex flex-wrap items-stretch gap-2">
              {stages.map((stage, i) => (
                <li key={stage.type} className="flex items-stretch gap-2">
                  <div className="rounded-lg border border-slate-200 px-3 py-2 min-w-[9rem]">
                    <div className="text-sm font-semibold text-slate-800">{stage.label}</div>
                    <ul className="mt-1 space-y-0.5">
                      {stage.assets.map((a) => (
                        <li key={a.asset_id} className="flex items-center gap-1.5 text-xs text-slate-600">
                          <span className={`h-2 w-2 rounded-full ${STATUS_DOT[a.status] ?? "bg-slate-400"}`} title={STATUS_LABEL[a.status] ?? a.status} />
                          {assetName(a) ?? STATUS_LABEL[a.status] ?? a.status}
                        </li>
                      ))}
                    </ul>
                  </div>
                  {i < stages.length - 1 && <span aria-hidden className="self-center text-slate-300">→</span>}
                </li>
              ))}
            </ol>
          </div>
        ))}
        {data && data.accessories.length > 0 && (
          <div>
            <div className="text-xs font-semibold uppercase tracking-wide text-slate-500 mb-2">Accesorios</div>
            <div className="flex flex-wrap gap-2">
              {data.accessories.map((s) => (
                <span key={s.type} className="rounded-full border border-slate-200 px-2.5 py-0.5 text-xs text-slate-600">
                  {s.label} · {s.assets.length}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>
    </SectionCard>
  );
}

function scoreTone(template: ChecklistTemplate | undefined, code: string): string {
  if (!template) return "bg-slate-300";
  const max = Math.max(...template.scale.map((s) => s.score));
  const entry = template.scale.find((s) => s.code === code);
  if (!entry) return "bg-slate-300";
  if (entry.score === max) return "bg-emerald-500";
  if (entry.score === 0) return "bg-red-500";
  return "bg-amber-400";
}

function TrafficLightSection() {
  const { data } = useQuery({ queryKey: ["traffic-light"], queryFn: getTrafficLight });
  const { data: templates } = useQuery({ queryKey: ["checklist-templates"], queryFn: getChecklistTemplates });
  const run = data?.run ?? null;
  const template = templates?.find((t) => t.id === run?.template_id);

  return (
    <SectionCard
      title="Semáforo del sistema"
      description="El estado de cada parte del sistema en la última revisión, con la acción que se acordó. Lo que está en amarillo o rojo queda como hallazgo."
      action={<Link to="/inspections" className="rounded-lg border border-slate-300 text-slate-700 text-xs font-semibold px-3 py-1.5 hover:bg-slate-50">Hacer una revisión</Link>}
    >
      {!run && <EmptyState message="Todavía no se hizo ninguna revisión del semáforo." />}
      {run && (
        <>
          <p className="text-xs text-slate-500 mb-3">
            Revisión del {new Date(run.performed_at).toLocaleDateString("es")} · {run.performed_by.replace(/^portal:/, "")}
          </p>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs uppercase tracking-wide text-slate-500 border-b border-slate-200">
                  <th className="py-2 pr-3 font-semibold">Componente</th>
                  <th className="py-2 pr-3 font-semibold">Estado</th>
                  <th className="py-2 font-semibold">Acción acordada</th>
                </tr>
              </thead>
              <tbody>
                {run.answers.map((a) => (
                  <tr key={a.item_key} className="border-b border-slate-100 last:border-0">
                    <td className="py-2 pr-3 text-slate-800">{a.text}</td>
                    <td className="py-2 pr-3 whitespace-nowrap">
                      <span className={`inline-block h-2.5 w-2.5 rounded-full mr-2 align-middle ${scoreTone(template, a.answer_code)}`} />
                      {a.answer_label}
                    </td>
                    <td className="py-2 text-slate-600">{a.action ?? <span className="text-slate-400">—</span>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </SectionCard>
  );
}

function TreatmentSection() {
  const { data } = useQuery({ queryKey: ["treatment-train"], queryFn: getTreatmentTrain });
  return (
    <SectionCard
      title="Tren de tratamiento"
      description="Qué etapas tiene el sistema, cuáles funcionan y qué problemas siguen abiertos. Una etapa que no existe también es información: puede pasar al plan de mejora."
    >
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-xs uppercase tracking-wide text-slate-500 border-b border-slate-200">
              <th className="py-2 pr-3 font-semibold">Etapa</th>
              <th className="py-2 pr-3 font-semibold">¿Existe?</th>
              <th className="py-2 pr-3 font-semibold">¿Funciona?</th>
              <th className="py-2 font-semibold">Problemas abiertos</th>
            </tr>
          </thead>
          <tbody>
            {(data ?? []).map((row) => (
              <tr key={row.type} className="border-b border-slate-100 last:border-0">
                <td className="py-2 pr-3 text-slate-800">{row.label}</td>
                <td className="py-2 pr-3">{row.exists ? `Sí (${row.asset_count})` : <span className="text-slate-400">No</span>}</td>
                <td className="py-2 pr-3">
                  {row.works === null ? <span className="text-slate-400">—</span>
                    : row.works ? <span className="text-emerald-700">Sí</span>
                    : <span className="text-amber-700 font-medium">No del todo</span>}
                </td>
                <td className="py-2 text-slate-600">
                  {row.open_findings.length === 0 ? <span className="text-slate-400">—</span>
                    : row.open_findings.map((f) => <div key={f.finding_id}>{f.description}</div>)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </SectionCard>
  );
}

function AddCriticalPointForm() {
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [location, setLocation] = useState("");
  const [description, setDescription] = useState("");
  const [priority, setPriority] = useState("high");
  const [support, setSupport] = useState("");
  const [error, setError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: () => createFinding({
      description, priority, source_kind: "critical_point",
      location_text: location || null, support_level: support || null,
    }),
    onSuccess: () => {
      setError(null);
      setLocation("");
      setDescription("");
      setOpen(false);
      queryClient.invalidateQueries({ queryKey: ["findings"] });
    },
    onError: (err) => setError(err instanceof ApiError ? err.message : "No se pudo registrar el punto crítico."),
  });

  if (!open) {
    return (
      <button onClick={() => setOpen(true)} className="rounded-lg bg-indigo-600 text-white text-xs font-semibold px-3 py-1.5 hover:bg-indigo-700">
        + Punto crítico
      </button>
    );
  }

  return (
    <div className="w-full rounded-lg border border-slate-200 bg-slate-50 p-4">
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
        <div>
          <label htmlFor="cp-location" className="block text-xs font-medium text-slate-500 mb-1">Dónde está</label>
          <input id="cp-location" className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm w-full" value={location} onChange={(e) => setLocation(e.target.value)} placeholder="Cruce de la quebrada" />
        </div>
        <div className="lg:col-span-2">
          <label htmlFor="cp-description" className="block text-xs font-medium text-slate-500 mb-1">Problema observado</label>
          <input id="cp-description" className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm w-full" value={description} onChange={(e) => setDescription(e.target.value)} placeholder="La tubería pierde agua y el sector alto queda con baja presión" />
        </div>
        <div>
          <label htmlFor="cp-priority" className="block text-xs font-medium text-slate-500 mb-1">Prioridad</label>
          <select id="cp-priority" className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm w-full bg-white" value={priority} onChange={(e) => setPriority(e.target.value)}>
            {Object.entries(PRIORITY_LABEL).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
        </div>
        <div className="lg:col-span-2">
          <label htmlFor="cp-support" className="block text-xs font-medium text-slate-500 mb-1">¿Quién puede resolverlo?</label>
          <select id="cp-support" className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm w-full bg-white" value={support} onChange={(e) => setSupport(e.target.value)}>
            <option value="">Sin definir todavía</option>
            {Object.entries(SUPPORT_LABEL).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
        </div>
      </div>
      {error && <p className="text-sm text-red-600 mt-2">{error}</p>}
      <div className="mt-3 flex gap-2">
        <button onClick={() => mutation.mutate()} disabled={!description || mutation.isPending} className="rounded-lg bg-indigo-600 text-white text-xs font-semibold px-3 py-1.5 hover:bg-indigo-700 disabled:opacity-40">
          Registrar
        </button>
        <button onClick={() => setOpen(false)} className="text-xs text-slate-500 hover:text-slate-700 px-2">Cancelar</button>
      </div>
    </div>
  );
}

function FindingRow({ finding }: { finding: Finding }) {
  const queryClient = useQueryClient();
  const mutation = useMutation({
    mutationFn: (body: Parameters<typeof updateFinding>[1]) => updateFinding(finding.finding_id, body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["findings"] });
      queryClient.invalidateQueries({ queryKey: ["treatment-train"] });
    },
  });

  return (
    <li className="py-3 flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-2 mb-1">
          <span className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ${PRIORITY_STYLE[finding.priority]}`}>{PRIORITY_LABEL[finding.priority]}</span>
          <span className="text-[11px] text-slate-500">{SOURCE_LABEL[finding.source_kind]}</span>
          <span className="text-[11px] text-slate-500">· {FINDING_STATUS_LABEL[finding.status]}</span>
          {finding.to_improvement_plan && <span className="rounded-full bg-indigo-50 px-2 py-0.5 text-[11px] font-semibold text-indigo-700">Plan de mejora</span>}
        </div>
        <p className="text-sm text-slate-800">{finding.description}</p>
        {(finding.location_text || finding.support_level) && (
          <p className="text-xs text-slate-500 mt-0.5">
            {finding.location_text}{finding.location_text && finding.support_level ? " · " : ""}{finding.support_level ? SUPPORT_LABEL[finding.support_level] : ""}
          </p>
        )}
      </div>
      <div className="flex flex-wrap gap-2 shrink-0">
        {finding.status === "open" && (
          <button onClick={() => mutation.mutate({ status: "in_progress" })} className="text-xs rounded-lg border border-slate-300 px-2.5 py-1 text-slate-700 hover:bg-slate-50">Atender</button>
        )}
        {finding.status !== "closed" && (
          <button onClick={() => mutation.mutate({ status: "closed" })} className="text-xs rounded-lg border border-slate-300 px-2.5 py-1 text-slate-700 hover:bg-slate-50">Cerrar</button>
        )}
        <button
          onClick={() => mutation.mutate({ to_improvement_plan: !finding.to_improvement_plan })}
          className="text-xs rounded-lg border border-slate-300 px-2.5 py-1 text-slate-700 hover:bg-slate-50"
        >
          {finding.to_improvement_plan ? "Quitar del plan" : "Pasar al plan de mejora"}
        </button>
      </div>
    </li>
  );
}

function FindingsSection() {
  const [filter, setFilter] = useState("open");
  const { data, isLoading } = useQuery({
    queryKey: ["findings", filter],
    queryFn: () => getFindings(filter === "all" ? undefined : filter),
  });

  return (
    <SectionCard
      title="Hallazgos"
      description="Puntos críticos del mapa técnico y problemas encontrados en las revisiones, ordenados por prioridad. Los que se marcan para el plan de mejora se usan después para pedir apoyo con evidencia."
      action={<AddCriticalPointForm />}
    >
      <div className="flex flex-wrap gap-1.5 mb-3">
        {[["open", "Abiertos"], ["in_progress", "En curso"], ["closed", "Cerrados"], ["all", "Todos"]].map(([value, label]) => (
          <button
            key={value}
            onClick={() => setFilter(value)}
            className={`rounded-full px-3 py-1 text-xs font-medium ${filter === value ? "bg-indigo-600 text-white" : "bg-slate-100 text-slate-600 hover:bg-slate-200"}`}
          >
            {label}
          </button>
        ))}
      </div>
      {isLoading && <p className="text-sm text-slate-500">Cargando…</p>}
      {data && data.length === 0 && <EmptyState message="No hay hallazgos en este estado." />}
      {data && data.length > 0 && (
        <ul className="divide-y divide-slate-100">
          {data.map((f) => <FindingRow key={f.finding_id} finding={f} />)}
        </ul>
      )}
    </SectionCard>
  );
}

export function SystemPage() {
  return (
    <StagePage title="Mi sistema">
      <SectionNav items={SECTIONS} />
      <NavSection id="route"><RouteSection /></NavSection>
      <NavSection id="traffic-light"><TrafficLightSection /></NavSection>
      <NavSection id="treatment"><TreatmentSection /></NavSection>
      <NavSection id="findings"><FindingsSection /></NavSection>
    </StagePage>
  );
}
