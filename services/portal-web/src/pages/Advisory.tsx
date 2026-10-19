import { useMemo, useState, type ReactNode } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ApiError,
  addWorkshopAttendee,
  createAdvisedOperator,
  createWorkshop,
  downloadImportTemplate,
  getAdvisedOperator,
  getAdvisedOperators,
  getAdvisoryDashboard,
  getChecklistTemplates,
  getWorkshop,
  getWorkshops,
  importGuidesFile,
  operatorScope,
  removeWorkshopAttendee,
  transferAdvisedOperator,
  updateAdvisedOperator,
  updateWorkshop,
  type AdvisedOperator,
  type AdvisoryDashboard,
  type FieldValue,
  type FormFieldDef,
  type ImportResult,
  type StageCoverage,
} from "../api";
import { AppShell } from "../components/AppShell";
import { EmptyState } from "../components/StagePage";
import { FieldInput } from "../components/FormEditor";
import { Icon } from "../components/Icon";
import { LAYER_COLORS, LAYER_SHAPES, LegendSymbol, OperatorsMap, symbolFor } from "../components/OperatorsMap";
import { GuidesWorkspace } from "./Inspections";
import { appLocale } from "../catalog";

// Asesoria de la ONG (Track E, 2026-10-19, migracion 0047). La ONG (p. ej.
// APT) acompana a operadores con talleres; las guias son la esencia de ese
// apoyo. Sus asesores solo ven esto: tablero, operadores y talleres. Los
// formularios que levantan con cada operador son registros de la ONG hasta
// que, si el operador lo pide, se crea su organizacion con esos datos.

const CARD = "rounded-xl border border-slate-200 bg-white p-5";
const INPUT = "w-full rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500";
const BTN = "rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-700 disabled:bg-indigo-300";
const BTN2 = "rounded-lg border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50";

function errorText(err: unknown, fallback: string): string {
  return err instanceof ApiError ? err.message : fallback;
}

function formatDay(iso: string | null | undefined): string {
  return iso ? new Date(`${iso.slice(0, 10)}T12:00:00`).toLocaleDateString(appLocale(), { day: "numeric", month: "short", year: "numeric" }) : "—";
}

function todayIso(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

function Notice({ message, onClose, tone = "ok" }: { message: ReactNode; onClose: () => void; tone?: "ok" | "error" }) {
  const style = tone === "ok" ? "border-emerald-200 bg-emerald-50 text-emerald-800" : "border-red-200 bg-red-50 text-red-800";
  return (
    <div role="status" className={`mb-4 flex items-start justify-between gap-3 rounded-lg border px-4 py-2.5 text-sm ${style}`}>
      <span>{message}</span>
      <button onClick={onClose} aria-label="Cerrar aviso"><Icon name="close" className="h-4 w-4" /></button>
    </div>
  );
}

const STATUS_PILL: Record<AdvisedOperator["status"], { label: string; cls: string }> = {
  active: { label: "En acompañamiento", cls: "bg-indigo-50 text-indigo-700" },
  transferred: { label: "Con organización propia", cls: "bg-emerald-50 text-emerald-700" },
  inactive: { label: "Inactivo", cls: "bg-slate-100 text-slate-600" },
};

function CoverageCell({ cov, seen }: { cov: StageCoverage | undefined; seen: boolean }) {
  const pct = cov?.pct ?? null;
  return (
    <div className="min-w-[5.5rem]">
      <div className="flex items-center gap-1.5">
        {seen
          ? <span className="rounded bg-indigo-600 px-1.5 text-[10px] font-bold text-white" title="Vista en un taller">Taller</span>
          : <span className="rounded bg-slate-100 px-1.5 text-[10px] font-medium text-slate-500" title="No vista en un taller">—</span>}
        <span className="text-[11px] tabular-nums text-slate-600">{cov && cov.total ? `${cov.complete}/${cov.total}` : "—"}</span>
      </div>
      <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-slate-200" role="progressbar" aria-valuenow={pct ?? 0} aria-valuemin={0} aria-valuemax={100}>
        <div className={`h-full rounded-full ${pct === 100 ? "bg-emerald-500" : "bg-indigo-500"}`} style={{ width: `${pct ?? 0}%` }} />
      </div>
    </div>
  );
}

// ── Tablero ───────────────────────────────────────────────────────────

function MapCard({ data }: { data: AdvisoryDashboard }) {
  const navigate = useNavigate();
  const { legend } = data.map;
  const [hiddenColors, setHiddenColors] = useState<Set<string>>(new Set());
  const [hiddenShapes, setHiddenShapes] = useState<Set<string>>(new Set());
  const [stage, setStage] = useState("");
  const toggle = (set: Set<string>, setter: (s: Set<string>) => void, code: string) => {
    const next = new Set(set);
    if (next.has(code)) next.delete(code); else next.add(code);
    setter(next);
  };
  const features = data.map.features.filter((f) =>
    !hiddenColors.has(f.color ?? "") && !hiddenShapes.has(f.shape ?? "") && (!stage || f.stages_in_workshops.includes(stage)));
  return (
    <section className={CARD} id="map">
      <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="text-base font-semibold text-slate-900">Mapa de operadores</h2>
        <span className="text-xs text-slate-500">{features.length} de {data.map.features.length} en el mapa · toque un símbolo para ver su resumen; doble toque abre el operador</span>
      </div>
      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_16rem]">
        <OperatorsMap features={features} legend={legend} onSelect={(id) => navigate(`/advisory/operators/${id}`)} />
        <div className="space-y-4 text-sm">
          {legend.size && (
            <div>
              <h3 className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-500">Tamaño</h3>
              <p className="flex items-center gap-2 text-slate-700">
                <LegendSymbol shape="circle" fill="#94a3b8" size={10} /><LegendSymbol shape="circle" fill="#94a3b8" size={18} /><LegendSymbol shape="circle" fill="#94a3b8" size={26} />
                {legend.size.label}
              </p>
            </div>
          )}
          {legend.color && (
            <fieldset>
              <legend className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-500">Color · {legend.color.label}</legend>
              {legend.color.options.map((o, i) => (
                <label key={o.code} className="flex cursor-pointer items-center gap-2 py-0.5 text-slate-700">
                  <input type="checkbox" checked={!hiddenColors.has(o.code)} onChange={() => toggle(hiddenColors, setHiddenColors, o.code)} />
                  <LegendSymbol shape="circle" fill={LAYER_COLORS[i % LAYER_COLORS.length]} />{o.label}
                </label>
              ))}
            </fieldset>
          )}
          {legend.shape && (
            <fieldset>
              <legend className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-500">Forma · {legend.shape.label}</legend>
              {legend.shape.options.map((o, i) => (
                <label key={o.code} className="flex cursor-pointer items-center gap-2 py-0.5 text-slate-700">
                  <input type="checkbox" checked={!hiddenShapes.has(o.code)} onChange={() => toggle(hiddenShapes, setHiddenShapes, o.code)} />
                  <LegendSymbol shape={LAYER_SHAPES[i % LAYER_SHAPES.length]} fill="#64748b" />{o.label}
                </label>
              ))}
              <p className="mt-1 flex items-center gap-2 text-xs text-slate-500"><LegendSymbol shape="none" fill="#94a3b8" />Sin dato todavía</p>
            </fieldset>
          )}
          <div>
            <label htmlFor="map-stage" className="mb-1 block text-xs font-semibold uppercase tracking-wide text-slate-500">Vieron en taller</label>
            <select id="map-stage" className={INPUT} value={stage} onChange={(e) => setStage(e.target.value)}>
              <option value="">Todas las guías</option>
              {data.stages.map((s) => <option key={s.code} value={s.code}>{s.code} · {s.title}</option>)}
            </select>
          </div>
          {data.map.without_location.length > 0 && (
            <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-xs text-amber-900">
              <p className="font-semibold">Sin ubicación ({data.map.without_location.length})</p>
              <ul className="mt-1 space-y-0.5">
                {data.map.without_location.map((o) => <li key={o.operator_id}><Link className="underline" to={`/advisory/operators/${o.operator_id}/G1`}>{o.name}</Link></li>)}
              </ul>
            </div>
          )}
        </div>
      </div>
    </section>
  );
}

export function AdvisoryDashboardPage() {
  const { data, isLoading, error } = useQuery({ queryKey: ["advisory", "dashboard"], queryFn: getAdvisoryDashboard });
  return (
    <AppShell title="Tablero de asesoría">
      {isLoading && <p className="text-sm text-slate-500">Cargando…</p>}
      {error && <EmptyState message={errorText(error, "No se pudo cargar el tablero.")} />}
      {data && (
        <div className="space-y-5">
          <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
            {([
              ["Operadores", data.kpis.operators, "acompañados", "/advisory/operators"],
              ["Capacitados", data.kpis.trained, "con al menos un taller", "/advisory/operators"],
              ["Talleres", data.kpis.workshops, "realizados", "/advisory/workshops"],
              ["Asistentes", data.kpis.attendees, "personas registradas", "/advisory/workshops"],
              ["Usuarios", data.kpis.users_covered, "de los acueductos acompañados", "/advisory/operators"],
              ["Con organización", data.kpis.transferred, "propia en la plataforma", "/advisory/operators"],
            ] as const).map(([label, value, hint, to]) => (
              <Link key={label} to={to} className="rounded-xl border border-slate-200 bg-white p-4 hover:shadow-md">
                <span className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</span>
                <span className="block text-3xl font-bold tabular-nums text-slate-900">{value.toLocaleString(appLocale())}</span>
                <span className="text-xs text-slate-500">{hint}</span>
              </Link>
            ))}
          </div>

          <MapCard data={data} />

          <section className={CARD}>
            <h2 className="mb-1 text-base font-semibold text-slate-900">Guías por operador</h2>
            <p className="mb-3 text-xs text-slate-500">"Taller" = la guía se vio con el operador en un taller. La barra es el avance de sus formularios (completos de total).</p>
            {data.operators.length === 0 ? <EmptyState message="Todavía no hay operadores. Regístrelos en Operadores o cárguelos desde un archivo." /> : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-slate-200 text-left text-xs uppercase tracking-wide text-slate-500">
                      <th className="py-2 pr-3 font-semibold">Operador</th>
                      {data.stages.map((s) => <th key={s.code} className="py-2 pr-3 font-semibold" title={s.title}>{s.code}</th>)}
                    </tr>
                  </thead>
                  <tbody>
                    {data.operators.map((op) => (
                      <tr key={op.operator_id} className="border-b border-slate-100 last:border-0">
                        <td className="py-2 pr-3">
                          <Link to={`/advisory/operators/${op.operator_id}`} className="font-medium text-indigo-700 hover:underline">{op.name}</Link>
                          <span className={`ml-2 rounded-full px-2 py-0.5 text-[10px] font-semibold ${STATUS_PILL[op.status].cls}`}>{STATUS_PILL[op.status].label}</span>
                        </td>
                        {data.stages.map((s) => (
                          <td key={s.code} className="py-2 pr-3">
                            <Link to={`/advisory/operators/${op.operator_id}/${s.code}`} aria-label={`${op.name}, ${s.title}`}>
                              <CoverageCell cov={op.coverage[s.code]} seen={op.stages_in_workshops.includes(s.code)} />
                            </Link>
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                  <tfoot>
                    <tr className="border-t border-slate-200 text-xs text-slate-600">
                      <td className="py-2 pr-3 font-semibold">Capacitados / avance promedio</td>
                      {data.stages.map((s) => (
                        <td key={s.code} className="py-2 pr-3 tabular-nums">{s.operators_trained} · {s.avg_complete_pct ?? 0} %</td>
                      ))}
                    </tr>
                  </tfoot>
                </table>
              </div>
            )}
          </section>
        </div>
      )}
    </AppShell>
  );
}

// ── Operadores ────────────────────────────────────────────────────────

function useProfileFields(layers: AdvisoryDashboard["map"]["layers"] | undefined) {
  const { data: templates } = useQuery({ queryKey: ["checklist-templates"], queryFn: getChecklistTemplates });
  return useMemo(() => {
    const templateId = layers?.location?.template_id;
    const template = templates?.find((t) => t.id === templateId);
    const layerKeys = new Set(Object.values(layers ?? {}).map((l) => l?.field_key));
    const fields = (template?.form_spec?.fields ?? []).filter((f) => f.required || layerKeys.has(f.key));
    return { template, fields };
  }, [templates, layers]);
}

function RegisterOperator({ onDone }: { onDone: (msg: string) => void }) {
  const queryClient = useQueryClient();
  const { data: dash } = useQuery({ queryKey: ["advisory", "dashboard"], queryFn: getAdvisoryDashboard });
  const { data: workshops } = useQuery({ queryKey: ["advisory", "workshops"], queryFn: getWorkshops });
  const { fields } = useProfileFields(dash?.map.layers);
  const [form, setForm] = useState({ name: "", community: "", contact_name: "", contact_phone: "", contact_email: "", workshop_id: "" });
  const [profile, setProfile] = useState<Record<string, FieldValue>>({});
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();
  const mutation = useMutation({
    mutationFn: () => createAdvisedOperator({
      ...form, workshop_id: form.workshop_id || null, origin: form.workshop_id ? "workshop" : "direct",
      profile: Object.fromEntries(Object.entries(profile).filter(([, v]) => v !== null && v !== "")),
    }),
    onSuccess: (op) => {
      queryClient.invalidateQueries({ queryKey: ["advisory"] });
      onDone(`${op.name} quedó registrado.`);
      navigate(`/advisory/operators/${op.operator_id}`);
    },
    onError: (err) => setError(errorText(err, "No se pudo registrar.")),
  });
  const set = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => setForm({ ...form, [k]: e.target.value });
  return (
    <section className={CARD}>
      <h2 className="text-base font-semibold text-slate-900">Registrar operador</h2>
      <p className="mb-4 text-xs text-slate-500">Con lo mínimo basta para empezar; el resto se completa en sus guías. La ubicación y el número de usuarios lo ponen en el mapa.</p>
      <div className="grid gap-3 md:grid-cols-2">
        <label className="text-sm font-medium text-slate-800">Nombre del operador (junta o sistema) <span className="text-red-600">*</span>
          <input className={`${INPUT} mt-1`} value={form.name} onChange={set("name")} placeholder="p. ej. Junta de Agua San Juan" />
        </label>
        <label className="text-sm font-medium text-slate-800">Comunidad o sector
          <input className={`${INPUT} mt-1`} value={form.community} onChange={set("community")} />
        </label>
        <label className="text-sm font-medium text-slate-800">Persona de contacto
          <input className={`${INPUT} mt-1`} value={form.contact_name} onChange={set("contact_name")} />
        </label>
        <div className="grid grid-cols-2 gap-3">
          <label className="text-sm font-medium text-slate-800">Teléfono
            <input className={`${INPUT} mt-1`} value={form.contact_phone} onChange={set("contact_phone")} inputMode="tel" />
          </label>
          <label className="text-sm font-medium text-slate-800">Correo
            <input className={`${INPUT} mt-1`} value={form.contact_email} onChange={set("contact_email")} type="email" />
          </label>
        </div>
        <label className="text-sm font-medium text-slate-800 md:col-span-2">Taller en el que participa
          <select className={`${INPUT} mt-1`} value={form.workshop_id} onChange={set("workshop_id")}>
            <option value="">— Sin taller (registro directo) —</option>
            {(workshops ?? []).map((w) => <option key={w.workshop_id} value={w.workshop_id}>{formatDay(w.held_on)} · {w.title}</option>)}
          </select>
        </label>
      </div>
      {fields.length > 0 && (
        <div className="mt-4 rounded-lg border border-slate-200 bg-slate-50 p-4">
          <h3 className="mb-3 text-xs font-semibold uppercase tracking-wide text-slate-500">Datos de la ficha básica (Guía 1)</h3>
          <div className="grid gap-3 md:grid-cols-2">
            {fields.map((f: FormFieldDef) => (
              <div key={f.key} className={f.type === "geo" ? "md:col-span-2" : undefined}>
                <label htmlFor={`reg-${f.key}`} className="mb-1 block text-sm font-medium text-slate-800">{f.label}</label>
                <FieldInput id={`reg-${f.key}`} def={f} value={profile[f.key] ?? null} onChange={(v) => setProfile({ ...profile, [f.key]: v })} />
              </div>
            ))}
          </div>
        </div>
      )}
      {error && <p className="mt-3 text-sm text-red-600">{error}</p>}
      <div className="mt-4 flex justify-end">
        <button className={BTN} disabled={!form.name.trim() || mutation.isPending} onClick={() => mutation.mutate()}>
          {mutation.isPending ? "Registrando…" : "Registrar operador"}
        </button>
      </div>
    </section>
  );
}

function ImportPanel({ onDone }: { onDone: (msg: string) => void }) {
  const queryClient = useQueryClient();
  const { data: dash } = useQuery({ queryKey: ["advisory", "dashboard"], queryFn: getAdvisoryDashboard });
  const { data: workshops } = useQuery({ queryKey: ["advisory", "workshops"], queryFn: getWorkshops });
  const [stages, setStages] = useState<string[]>([]);
  const [file, setFile] = useState<{ name: string; base64: string } | null>(null);
  const [workshopId, setWorkshopId] = useState("");
  const [preview, setPreview] = useState<ImportResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const readFile = (f: File | undefined) => {
    setPreview(null);
    setError(null);
    if (!f) { setFile(null); return; }
    const reader = new FileReader();
    reader.onload = () => {
      const url = String(reader.result ?? "");
      setFile({ name: f.name, base64: url.slice(url.indexOf(",") + 1) });
    };
    reader.readAsDataURL(f);
  };
  const send = async (dryRun: boolean) => {
    if (!file) return;
    setBusy(true);
    setError(null);
    try {
      const result = await importGuidesFile({ filename: file.name, content_base64: file.base64, dry_run: dryRun, workshop_id: workshopId || null });
      if (dryRun) setPreview(result);
      else {
        queryClient.invalidateQueries({ queryKey: ["advisory"] });
        queryClient.invalidateQueries({ queryKey: ["guides"] });
        setPreview(null);
        setFile(null);
        onDone(`Archivo cargado: ${result.operators_created.length} operador(es) nuevo(s), ${result.lists_saved} lista(s) y ${result.forms_saved} ficha(s) o tabla(s).${result.errors.length ? ` ${result.errors.length} dato(s) no se cargaron.` : ""}`);
      }
    } catch (err) {
      setError(errorText(err, "No se pudo leer el archivo."));
    } finally {
      setBusy(false);
    }
  };
  return (
    <section className={CARD}>
      <h2 className="text-base font-semibold text-slate-900">Cargar desde Excel o archivo plano</h2>
      <p className="mb-4 text-xs text-slate-500">
        Para lo que se llenó en papel durante el taller. 1) Descargue la plantilla de las guías que necesite; trae una hoja por formulario con los operadores ya escritos.
        2) Llénela y cárguela: primero verá lo que se va a grabar. También acepta un archivo plano (.csv) con las columnas operador, formulario, campo, fila, valor, estimado, observacion.
      </p>
      <div className="flex flex-wrap items-end gap-3">
        <fieldset className="flex flex-wrap gap-2">
          <legend className="mb-1 text-xs font-semibold text-slate-600">Guías de la plantilla</legend>
          {(dash?.stages ?? []).map((s) => (
            <label key={s.code} className={`inline-flex cursor-pointer items-center gap-1 rounded-lg border px-2.5 py-1 text-sm ${stages.includes(s.code) ? "border-indigo-600 bg-indigo-50 text-indigo-800" : "border-slate-300 text-slate-700"}`} title={s.title}>
              <input type="checkbox" className="sr-only" checked={stages.includes(s.code)} onChange={() => setStages(stages.includes(s.code) ? stages.filter((c) => c !== s.code) : [...stages, s.code])} />
              {s.code}
            </label>
          ))}
        </fieldset>
        <button className={BTN2} onClick={() => downloadImportTemplate(stages).catch((err) => setError(errorText(err, "No se pudo descargar la plantilla.")))}>
          <span className="inline-flex items-center gap-1.5"><Icon name="download" className="h-4 w-4" />Descargar plantilla{stages.length ? ` (${stages.join(", ")})` : " (todas)"}</span>
        </button>
      </div>
      <div className="mt-4 grid gap-3 md:grid-cols-2">
        <label className="text-sm font-medium text-slate-800">Archivo (.xlsx o .csv)
          <input type="file" accept=".xlsx,.csv,.txt" className={`${INPUT} mt-1`} onChange={(e) => readFile(e.target.files?.[0])} />
        </label>
        <label className="text-sm font-medium text-slate-800">Se llenó en el taller
          <select className={`${INPUT} mt-1`} value={workshopId} onChange={(e) => setWorkshopId(e.target.value)}>
            <option value="">— Ninguno —</option>
            {(workshops ?? []).map((w) => <option key={w.workshop_id} value={w.workshop_id}>{formatDay(w.held_on)} · {w.title}</option>)}
          </select>
        </label>
      </div>
      {error && <p className="mt-3 text-sm text-red-600">{error}</p>}
      <div className="mt-4 flex justify-end gap-2">
        <button className={BTN2} disabled={!file || busy} onClick={() => send(true)}>{busy && !preview ? "Revisando…" : "Revisar el archivo"}</button>
      </div>
      {preview && (
        <div className="mt-4 rounded-lg border border-indigo-200 bg-indigo-50/50 p-4 text-sm">
          <h3 className="font-semibold text-slate-900">Esto es lo que se va a grabar</h3>
          <ul className="mt-2 space-y-1 text-slate-700">
            {preview.operators_created.length > 0 && <li>Operadores nuevos: {preview.operators_created.join(", ")}</li>}
            {preview.by_operator.filter((o) => o.lists.length || o.forms.length).map((o) => (
              <li key={o.operator}><strong>{o.operator}:</strong> {[...o.lists, ...o.forms].join(" · ")}</li>
            ))}
            {preview.lists_saved + preview.forms_saved === 0 && preview.operators_created.length === 0 && <li>El archivo no trae datos nuevos.</li>}
          </ul>
          {preview.errors.length > 0 && (
            <div className="mt-3 rounded-lg border border-amber-200 bg-amber-50 p-3 text-amber-900">
              <p className="font-semibold">No se cargará ({preview.errors.length}):</p>
              <ul className="mt-1 list-disc space-y-0.5 pl-5 text-xs">
                {preview.errors.map((e, i) => <li key={i}>{e.sheet && `${e.sheet}${e.row ? `, fila ${e.row}` : ""}: `}{e.message}</li>)}
              </ul>
            </div>
          )}
          <div className="mt-3 flex justify-end gap-2">
            <button className={BTN2} onClick={() => setPreview(null)}>Cancelar</button>
            <button className={BTN} disabled={busy || preview.lists_saved + preview.forms_saved + preview.operators_created.length === 0} onClick={() => send(false)}>
              {busy ? "Grabando…" : "Grabar"}
            </button>
          </div>
        </div>
      )}
    </section>
  );
}

export function AdvisoryOperatorsPage() {
  const { data: operators, isLoading } = useQuery({ queryKey: ["advisory", "operators"], queryFn: getAdvisedOperators });
  const { data: dash } = useQuery({ queryKey: ["advisory", "dashboard"], queryFn: getAdvisoryDashboard });
  const [panel, setPanel] = useState<"none" | "register" | "import">("none");
  const [message, setMessage] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const legend = dash?.map.legend;
  const shown = (operators ?? []).filter((o) => !query.trim() || `${o.name} ${o.community ?? ""}`.toLowerCase().includes(query.trim().toLowerCase()));
  return (
    <AppShell title="Operadores">
      {message && <Notice message={message} onClose={() => setMessage(null)} />}
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <input className={`${INPUT} max-w-xs`} placeholder="Buscar operador" value={query} onChange={(e) => setQuery(e.target.value)} aria-label="Buscar operador" />
        <span className="mr-auto text-xs text-slate-500">{shown.length} operador{shown.length === 1 ? "" : "es"}</span>
        <button className={panel === "import" ? BTN : BTN2} onClick={() => setPanel(panel === "import" ? "none" : "import")}>
          <span className="inline-flex items-center gap-1.5"><Icon name="upload" className="h-4 w-4" />Cargar archivo</span>
        </button>
        <button className={panel === "register" ? BTN2 : BTN} onClick={() => setPanel(panel === "register" ? "none" : "register")}>
          {panel === "register" ? "Cerrar" : "+ Registrar operador"}
        </button>
      </div>
      <div className="space-y-5">
        {panel === "register" && <RegisterOperator onDone={(m) => { setMessage(m); setPanel("none"); }} />}
        {panel === "import" && <ImportPanel onDone={(m) => { setMessage(m); setPanel("none"); }} />}
        {isLoading && <p className="text-sm text-slate-500">Cargando…</p>}
        {operators && operators.length === 0 && <EmptyState message="Todavía no hay operadores registrados." />}
        {shown.length > 0 && (
          <section className={CARD}>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-slate-200 text-left text-xs uppercase tracking-wide text-slate-500">
                    <th className="py-2 pr-3 font-semibold">Operador</th>
                    <th className="py-2 pr-3 font-semibold">{legend?.size?.label ?? "Usuarios"}</th>
                    <th className="py-2 pr-3 font-semibold">Servicios</th>
                    <th className="py-2 pr-3 font-semibold">Talleres</th>
                    {(dash?.stages ?? []).map((s) => <th key={s.code} className="py-2 pr-3 font-semibold" title={s.title}>{s.code}</th>)}
                  </tr>
                </thead>
                <tbody>
                  {shown.map((op) => {
                    const sym = legend ? symbolFor(legend, op.profile.color ?? null, op.profile.shape ?? null) : null;
                    return (
                      <tr key={op.operator_id} className="border-b border-slate-100 align-top last:border-0">
                        <td className="py-2.5 pr-3">
                          <Link to={`/advisory/operators/${op.operator_id}`} className="font-medium text-indigo-700 hover:underline">{op.name}</Link>
                          <div className="text-xs text-slate-500">{op.community ?? ""}</div>
                          <span className={`mt-1 inline-block rounded-full px-2 py-0.5 text-[10px] font-semibold ${STATUS_PILL[op.status].cls}`}>{STATUS_PILL[op.status].label}</span>
                        </td>
                        <td className="py-2.5 pr-3 tabular-nums">{op.profile.size ?? "—"}</td>
                        <td className="py-2.5 pr-3 text-xs text-slate-600">
                          {sym && <span className="mr-1 inline-block align-middle"><LegendSymbol shape={sym.shape} fill={sym.fill} /></span>}
                          {legend?.color?.options.find((o) => o.code === op.profile.color)?.label ?? "Sin dato"}
                          <div>{legend?.shape?.options.find((o) => o.code === op.profile.shape)?.label ?? ""}</div>
                        </td>
                        <td className="py-2.5 pr-3 text-xs text-slate-600">{op.workshops.length ? op.workshops.map((w) => formatDay(w.held_on)).join(", ") : "—"}</td>
                        {(dash?.stages ?? []).map((s) => (
                          <td key={s.code} className="py-2.5 pr-3">
                            <Link to={`/advisory/operators/${op.operator_id}/${s.code}`} aria-label={`${op.name}, ${s.title}`}>
                              <CoverageCell cov={op.coverage[s.code]} seen={op.stages_in_workshops.includes(s.code)} />
                            </Link>
                          </td>
                        ))}
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </section>
        )}
      </div>
    </AppShell>
  );
}

// ── Un operador: sus guias ────────────────────────────────────────────

function TransferPanel({ op, onClose }: { op: AdvisedOperator; onClose: () => void }) {
  const queryClient = useQueryClient();
  const suggested = op.name.toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "").slice(0, 40);
  const [code, setCode] = useState(suggested);
  const [user, setUser] = useState("admin");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);
  const mutation = useMutation({
    mutationFn: () => transferAdvisedOperator(op.operator_id, { code, admin_username: user, admin_password: password }),
    onSuccess: (r) => {
      queryClient.invalidateQueries({ queryKey: ["advisory"] });
      queryClient.invalidateQueries({ queryKey: ["guides", "operator", op.operator_id] });
      setDone(`Organización "${r.organization.name}" creada con ${r.copied_runs} lista(s) y ${r.copied_forms} ficha(s) o tabla(s); ${r.findings_created} hallazgo(s) quedaron en su organización. Entregue al operador: organización ${r.organization.name}, usuario ${r.organization.admin.email} y la clave que acaba de escribir.`);
    },
    onError: (err) => setError(errorText(err, "No se pudo crear la organización.")),
  });
  return (
    <section className="rounded-xl border border-emerald-200 bg-emerald-50/40 p-5">
      <h2 className="text-base font-semibold text-slate-900">Crear la organización de {op.name}</h2>
      {done ? (
        <>
          <p className="mt-2 text-sm text-emerald-900">{done}</p>
          <button className={`${BTN2} mt-3`} onClick={onClose}>Cerrar</button>
        </>
      ) : (
        <>
          <p className="mt-1 text-xs text-slate-600">
            Se crea su propia organización en la plataforma con todo lo levantado hasta hoy (listas, fichas y tablas) y su primer usuario administrador.
            Desde ese momento, el operador sigue llenando sus guías desde su organización y aquí quedan de solo lectura. Hágalo cuando el operador lo solicite.
          </p>
          <div className="mt-3 grid gap-3 md:grid-cols-3">
            <label className="text-sm font-medium text-slate-800">Código para iniciar sesión
              <input className={`${INPUT} mt-1`} value={code} onChange={(e) => setCode(e.target.value.toLowerCase())} />
              <span className="text-[11px] font-normal text-slate-500">Letras sin tilde, números, punto o guion</span>
            </label>
            <label className="text-sm font-medium text-slate-800">Usuario administrador
              <input className={`${INPUT} mt-1`} value={user} onChange={(e) => setUser(e.target.value.toLowerCase())} />
            </label>
            <label className="text-sm font-medium text-slate-800">Clave (mínimo 8)
              <input type="password" className={`${INPUT} mt-1`} value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="new-password" />
            </label>
          </div>
          {error && <p className="mt-2 text-sm text-red-600">{error}</p>}
          <div className="mt-3 flex justify-end gap-2">
            <button className={BTN2} onClick={onClose}>Cancelar</button>
            <button className={BTN} disabled={!code || !user || password.length < 8 || mutation.isPending} onClick={() => mutation.mutate()}>
              {mutation.isPending ? "Creando…" : "Crear organización"}
            </button>
          </div>
        </>
      )}
    </section>
  );
}

export function AdvisoryOperatorPage() {
  const { operatorId = "", stageCode } = useParams<{ operatorId: string; stageCode?: string }>();
  const queryClient = useQueryClient();
  const { data: op, isLoading, error } = useQuery({ queryKey: ["guides", "operator", operatorId], queryFn: () => getAdvisedOperator(operatorId) });
  const { data: workshops } = useQuery({ queryKey: ["advisory", "workshops"], queryFn: getWorkshops });
  const [workshopId, setWorkshopId] = useState<string | null>(null);
  const [showTransfer, setShowTransfer] = useState(false);
  const statusMutation = useMutation({
    mutationFn: (status: "active" | "inactive") => updateAdvisedOperator(operatorId, { status }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["guides", "operator", operatorId] }),
  });
  // Por defecto, lo que se llena hoy queda en el taller de hoy al que asiste.
  const todays = op?.workshops.find((w) => w.held_on === todayIso())?.workshop_id ?? null;
  const activeWorkshop = workshopId === null ? todays : workshopId || null;
  const readOnly = !op ? null
    : op.status === "transferred" ? `Estos datos ya se traspasaron a su organización (${op.transferred_tenant_name ?? "propia"}): el operador los actualiza desde allí.`
    : op.status === "inactive" ? "El operador está inactivo: actívelo para registrar información." : null;
  const scope = useMemo(() => operatorScope(operatorId, activeWorkshop, readOnly), [operatorId, activeWorkshop, readOnly]);

  return (
    <AppShell title={op?.name ?? "Operador"}>
      {isLoading && <p className="text-sm text-slate-500">Cargando…</p>}
      {error && <EmptyState message={errorText(error, "No se encontró el operador.")} />}
      {op && (
        <div className="space-y-5">
          <section className={CARD}>
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <Link to="/advisory/operators" className="text-sm font-medium text-indigo-700 hover:underline">← Operadores</Link>
                <h2 className="mt-1 text-lg font-bold text-slate-900">{op.name}</h2>
                <p className="text-sm text-slate-600">
                  {[op.community, op.contact_name, op.contact_phone, op.contact_email].filter(Boolean).join(" · ") || "Sin datos de contacto"}
                </p>
                <div className="mt-2 flex flex-wrap items-center gap-2 text-xs">
                  <span className={`rounded-full px-2 py-0.5 font-semibold ${STATUS_PILL[op.status].cls}`}>{STATUS_PILL[op.status].label}</span>
                  {op.workshops.map((w) => (
                    <span key={w.workshop_id} className="rounded-full bg-slate-100 px-2 py-0.5 text-slate-700">Taller {formatDay(w.held_on)} · {w.stage_codes.join(", ")}</span>
                  ))}
                  {op.profile.size != null && <span className="rounded-full bg-slate-100 px-2 py-0.5 text-slate-700">{op.profile.size} usuarios</span>}
                </div>
              </div>
              <div className="flex flex-wrap gap-2">
                {op.status === "active" && <button className={BTN} onClick={() => setShowTransfer(true)}>Crear su organización</button>}
                {op.status !== "transferred" && (
                  <button className={BTN2} disabled={statusMutation.isPending} onClick={() => statusMutation.mutate(op.status === "active" ? "inactive" : "active")}>
                    {op.status === "active" ? "Marcar inactivo" : "Activar"}
                  </button>
                )}
              </div>
            </div>
            {op.status === "active" && (
              <div className="mt-4 flex flex-wrap items-center gap-2 border-t border-slate-100 pt-3">
                <label htmlFor="ws" className="text-sm font-medium text-slate-700">Lo que se llene ahora queda en el taller:</label>
                <select id="ws" className={`${INPUT} max-w-md`} value={activeWorkshop ?? ""} onChange={(e) => setWorkshopId(e.target.value || "")}>
                  <option value="">— Fuera de taller (asesoría) —</option>
                  {(workshops ?? []).map((w) => <option key={w.workshop_id} value={w.workshop_id}>{formatDay(w.held_on)} · {w.title}</option>)}
                </select>
              </div>
            )}
          </section>
          {showTransfer && <TransferPanel op={op} onClose={() => setShowTransfer(false)} />}
          <GuidesWorkspace
            scope={scope}
            basePath={`/advisory/operators/${operatorId}`}
            stageParam={stageCode}
            intro={`Las guías de ${op.name}. Elija una guía y llene con el operador sus fichas, tablas y listas. Se puede guardar a medias y seguir en otra sesión o en otro taller.`}
          />
        </div>
      )}
    </AppShell>
  );
}

// ── Talleres ──────────────────────────────────────────────────────────

function WorkshopDetail({ id, stages }: { id: string; stages: AdvisoryDashboard["stages"] }) {
  const queryClient = useQueryClient();
  const { data: w } = useQuery({ queryKey: ["advisory", "workshop", id], queryFn: () => getWorkshop(id) });
  const { data: operators } = useQuery({ queryKey: ["advisory", "operators"], queryFn: getAdvisedOperators });
  const [person, setPerson] = useState({ full_name: "", operator_id: "", role_label: "", sector: "", support_needs: "" });
  const [error, setError] = useState<string | null>(null);
  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ["advisory"] });
  };
  const opsMutation = useMutation({
    mutationFn: (ids: string[]) => updateWorkshop(id, { operator_ids: ids }),
    onSuccess: refresh,
    onError: (err) => setError(errorText(err, "No se pudo actualizar.")),
  });
  const stagesMutation = useMutation({
    mutationFn: (codes: string[]) => updateWorkshop(id, { stage_codes: codes }),
    onSuccess: refresh,
  });
  const addMutation = useMutation({
    mutationFn: () => addWorkshopAttendee(id, { ...person, operator_id: person.operator_id || null }),
    onSuccess: () => { setPerson({ ...person, full_name: "", role_label: "", support_needs: "" }); setError(null); refresh(); },
    onError: (err) => setError(errorText(err, "No se pudo agregar.")),
  });
  const removeMutation = useMutation({ mutationFn: (aid: string) => removeWorkshopAttendee(id, aid), onSuccess: refresh });
  if (!w) return <p className="text-sm text-slate-500">Cargando…</p>;
  const inWorkshop = new Set((w.operators ?? []).map((o) => o.operator_id));
  const names = Object.fromEntries((operators ?? []).map((o) => [o.operator_id, o.name]));
  return (
    <section className={CARD}>
      <h2 className="text-base font-semibold text-slate-900">{w.title}</h2>
      <p className="text-sm text-slate-600">{formatDay(w.held_on)}{w.place ? ` · ${w.place}` : ""}{w.facilitators ? ` · ${w.facilitators}` : ""}</p>
      <fieldset className="mt-3 flex flex-wrap gap-2">
        <legend className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-500">Guías que cubre</legend>
        {stages.map((s) => {
          const on = w.stage_codes.includes(s.code);
          return (
            <label key={s.code} title={s.title} className={`inline-flex cursor-pointer items-center rounded-lg border px-2.5 py-1 text-sm ${on ? "border-indigo-600 bg-indigo-50 font-semibold text-indigo-800" : "border-slate-300 text-slate-600"}`}>
              <input type="checkbox" className="sr-only" checked={on} onChange={() => stagesMutation.mutate(on ? w.stage_codes.filter((c) => c !== s.code) : [...w.stage_codes, s.code])} />
              {s.code}
            </label>
          );
        })}
      </fieldset>
      <div className="mt-4 grid gap-5 lg:grid-cols-2">
        <div>
          <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">Operadores que asisten ({inWorkshop.size})</h3>
          <ul className="max-h-80 space-y-1 overflow-y-auto">
            {(operators ?? []).filter((o) => o.status !== "inactive").map((o) => (
              <li key={o.operator_id}>
                <label className="flex cursor-pointer items-center gap-2 text-sm text-slate-800">
                  <input type="checkbox" checked={inWorkshop.has(o.operator_id)} disabled={opsMutation.isPending}
                    onChange={() => opsMutation.mutate(inWorkshop.has(o.operator_id) ? [...inWorkshop].filter((x) => x !== o.operator_id) : [...inWorkshop, o.operator_id])} />
                  {o.name}
                  {inWorkshop.has(o.operator_id) && <Link to={`/advisory/operators/${o.operator_id}`} className="ml-auto text-xs text-indigo-700 hover:underline">Llenar sus guías ›</Link>}
                </label>
              </li>
            ))}
          </ul>
          {!operators && <p className="text-sm text-slate-500">Cargando…</p>}
          {operators && operators.length === 0 && <p className="text-sm text-slate-500">Registre operadores en la pantalla Operadores.</p>}
        </div>
        <div>
          <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">Asistencia (T-02 / T-03) · {w.attendees?.length ?? 0} personas</h3>
          <p className="mb-2 text-[11px] text-slate-500">Solo lo necesario para participar: no registre diagnósticos personales.</p>
          <div className="grid gap-2 sm:grid-cols-2">
            <input className={INPUT} placeholder="Nombre y apellido *" value={person.full_name} onChange={(e) => setPerson({ ...person, full_name: e.target.value })} />
            <select className={INPUT} value={person.operator_id} onChange={(e) => setPerson({ ...person, operator_id: e.target.value })} aria-label="Operador">
              <option value="">— Operador o institución —</option>
              {(operators ?? []).map((o) => <option key={o.operator_id} value={o.operator_id}>{o.name}</option>)}
            </select>
            <input className={INPUT} placeholder="Rol (presidencia, operador…)" value={person.role_label} onChange={(e) => setPerson({ ...person, role_label: e.target.value })} />
            <input className={INPUT} placeholder="Apoyo para participar (letra grande…)" value={person.support_needs} onChange={(e) => setPerson({ ...person, support_needs: e.target.value })} />
          </div>
          <button className={`${BTN} mt-2`} disabled={!person.full_name.trim() || addMutation.isPending} onClick={() => addMutation.mutate()}>Agregar a la asistencia</button>
          {error && <p className="mt-2 text-sm text-red-600">{error}</p>}
          <ul className="mt-3 divide-y divide-slate-100 text-sm">
            {(w.attendees ?? []).map((a) => (
              <li key={a.attendee_id} className="flex items-center gap-2 py-1.5">
                <span className="flex-1"><strong className="font-medium">{a.full_name}</strong>{a.role_label ? ` · ${a.role_label}` : ""}{a.operator_id ? ` · ${names[a.operator_id] ?? ""}` : ""}</span>
                <button aria-label={`Quitar a ${a.full_name}`} className="text-slate-400 hover:text-red-600" onClick={() => removeMutation.mutate(a.attendee_id)}><Icon name="close" className="h-4 w-4" /></button>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </section>
  );
}

export function WorkshopsPage() {
  const queryClient = useQueryClient();
  const { data: workshops, isLoading } = useQuery({ queryKey: ["advisory", "workshops"], queryFn: getWorkshops });
  const { data: dash } = useQuery({ queryKey: ["advisory", "dashboard"], queryFn: getAdvisoryDashboard });
  const [selected, setSelected] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState({ title: "", held_on: todayIso(), place: "", facilitators: "" });
  const [stages, setStages] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const mutation = useMutation({
    mutationFn: () => createWorkshop({ ...form, stage_codes: stages }),
    onSuccess: (w) => { queryClient.invalidateQueries({ queryKey: ["advisory"] }); setCreating(false); setSelected(w.workshop_id); setError(null); },
    onError: (err) => setError(errorText(err, "No se pudo crear el taller.")),
  });
  const current = selected ?? workshops?.[0]?.workshop_id ?? null;
  return (
    <AppShell title="Talleres">
      <div className="mb-4 flex justify-end">
        <button className={creating ? BTN2 : BTN} onClick={() => setCreating(!creating)}>{creating ? "Cerrar" : "+ Nuevo taller"}</button>
      </div>
      {creating && (
        <section className={`${CARD} mb-5`}>
          <h2 className="mb-3 text-base font-semibold text-slate-900">Nuevo taller</h2>
          <div className="grid gap-3 md:grid-cols-2">
            <label className="text-sm font-medium text-slate-800">Nombre <span className="text-red-600">*</span>
              <input className={`${INPUT} mt-1`} value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} placeholder="p. ej. Taller Guías 1 a 3 — Gualaceo" />
            </label>
            <label className="text-sm font-medium text-slate-800">Fecha <span className="text-red-600">*</span>
              <input type="date" className={`${INPUT} mt-1`} value={form.held_on} onChange={(e) => setForm({ ...form, held_on: e.target.value })} />
            </label>
            <label className="text-sm font-medium text-slate-800">Lugar
              <input className={`${INPUT} mt-1`} value={form.place} onChange={(e) => setForm({ ...form, place: e.target.value })} />
            </label>
            <label className="text-sm font-medium text-slate-800">Personas facilitadoras
              <input className={`${INPUT} mt-1`} value={form.facilitators} onChange={(e) => setForm({ ...form, facilitators: e.target.value })} />
            </label>
          </div>
          <fieldset className="mt-3 flex flex-wrap gap-2">
            <legend className="mb-1 text-sm font-medium text-slate-800">Guías que cubre</legend>
            {(dash?.stages ?? []).map((s) => (
              <label key={s.code} className={`inline-flex cursor-pointer items-center rounded-lg border px-2.5 py-1 text-sm ${stages.includes(s.code) ? "border-indigo-600 bg-indigo-50 font-semibold text-indigo-800" : "border-slate-300 text-slate-600"}`}>
                <input type="checkbox" className="sr-only" checked={stages.includes(s.code)} onChange={() => setStages(stages.includes(s.code) ? stages.filter((c) => c !== s.code) : [...stages, s.code])} />
                {s.code} · {s.title}
              </label>
            ))}
          </fieldset>
          {error && <p className="mt-2 text-sm text-red-600">{error}</p>}
          <div className="mt-3 flex justify-end">
            <button className={BTN} disabled={!form.title.trim() || !form.held_on || mutation.isPending} onClick={() => mutation.mutate()}>Crear taller</button>
          </div>
        </section>
      )}
      {isLoading && <p className="text-sm text-slate-500">Cargando…</p>}
      {workshops && workshops.length === 0 && !creating && <EmptyState message="Todavía no hay talleres. Cree el primero con “Nuevo taller”." />}
      {workshops && workshops.length > 0 && (
        <div className="grid gap-5 lg:grid-cols-[18rem_minmax(0,1fr)]">
          <ul className="space-y-2">
            {workshops.map((w) => (
              <li key={w.workshop_id}>
                <button onClick={() => setSelected(w.workshop_id)} className={`w-full rounded-xl border p-3 text-left ${current === w.workshop_id ? "border-indigo-600 bg-indigo-50" : "border-slate-200 bg-white hover:border-indigo-300"}`}>
                  <span className="block text-sm font-semibold text-slate-900">{w.title}</span>
                  <span className="block text-xs text-slate-500">{formatDay(w.held_on)} · {w.stage_codes.join(", ") || "sin guías"}</span>
                  <span className="block text-xs text-slate-500">{w.operator_count} operadores · {w.attendee_count} personas</span>
                </button>
              </li>
            ))}
          </ul>
          {current && <WorkshopDetail key={current} id={current} stages={dash?.stages ?? []} />}
        </div>
      )}
    </AppShell>
  );
}
