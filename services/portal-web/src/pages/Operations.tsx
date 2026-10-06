import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ApiError,
  calculateDosing,
  createChemicalProduct,
  createOperationLogEntry,
  createSamplingPoint,
  getChemicalProducts,
  getFieldReadings,
  getManualMeterReadings,
  getOperationLog,
  getOperationsCatalog,
  getOperationsToday,
  getSamplingPoints,
  recordFieldReading,
  updateSamplingPoint,
  type ChemicalProduct,
  type FieldParameter,
  type FieldReading,
  type OperationLogEntry,
  type OperationMoment,
  type RuleBand,
  type SamplingPoint,
} from "../api";
import { StagePage, EmptyState } from "../components/StagePage";
import { NavSection, SectionNav } from "../components/SectionNav";
import { sectionsFor } from "../navigation";
import { appLocale, term, formSuffix } from "../catalog";

// Operacion diaria de la junta (Track D, D1.1; Guia 3 §3.3-3.4, fichas 7B y
// 7C). Todo sale del catalogo: los tipos de punto, la rutina de 5 momentos y
// la interpretacion de cada parametro (tramos del paquete normativo, con su
// "que hacer"). La interpretacion que se ve al escribir el valor es solo una
// vista previa con los mismos tramos; la que vale es la que guarda el
// servidor con la regla vigente.

const SECTIONS = sectionsFor("/operations");
const TODAY_KEY = ["operations-today"] as const;

const SEVERITY_STYLE: Record<string, string> = {
  ok: "bg-emerald-50 text-emerald-700",
  alert: "bg-amber-50 text-amber-800",
  critical: "bg-red-50 text-red-700",
};
const APPEARANCE: Record<"clear" | "turbid" | "colored", string> = { clear: "Clara", turbid: "Turbia", colored: "Con color" };
const LOG_STATUS: Record<"good" | "alert", { label: string; cls: string }> = {
  good: { label: "Bueno", cls: "bg-emerald-50 text-emerald-700" },
  alert: { label: "Alerta", cls: "bg-red-50 text-red-700" },
};

function errText(err: unknown, fallback: string): string {
  return err instanceof ApiError ? err.message : fallback;
}

function newClientId(): string {
  return typeof crypto !== "undefined" && "randomUUID" in crypto ? crypto.randomUUID() : `${Date.now()}-${Math.random()}`;
}

function time(iso: string): string {
  return new Date(iso).toLocaleTimeString(appLocale(), { hour: "2-digit", minute: "2-digit" });
}

function dateTime(iso: string): string {
  return new Date(iso).toLocaleString(appLocale(), { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
}

/** Vista previa con los tramos del paquete (misma regla que el motor). */
function previewBand(bands: RuleBand[] | null, value: number): RuleBand | null {
  if (!bands || Number.isNaN(value)) return null;
  for (const b of bands) {
    if (b.upper === null) return b;
    if (b.upper_inclusive === false ? value < b.upper : value <= b.upper) return b;
  }
  return null;
}

function useInvalidateOperations() {
  const queryClient = useQueryClient();
  return () => {
    for (const key of [TODAY_KEY, ["sampling-points"], ["field-readings"], ["operation-log"], ["findings"]]) {
      queryClient.invalidateQueries({ queryKey: key });
    }
  };
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

// ── Hoy ───────────────────────────────────────────────────────────────

function LogEntryForm({ moment, readings, onDone }: { moment: OperationMoment; readings: FieldReading[]; onDone: () => void }) {
  const invalidate = useInvalidateOperations();
  const [tank, setTank] = useState("");
  const [applied, setApplied] = useState("");
  const [unit, setUnit] = useState<"g" | "ml">("g");
  const [readingId, setReadingId] = useState("");
  const [appearance, setAppearance] = useState<"clear" | "turbid" | "colored" | "">("");
  const [status, setStatus] = useState<"good" | "alert">("good");
  const [notes, setNotes] = useState("");
  const [error, setError] = useState<string | null>(null);
  const chlorine = readings.filter((r) => r.parameter_code === "free_chlorine");
  const mutation = useMutation({
    mutationFn: () => createOperationLogEntry({
      moment_code: moment.code,
      tank_level_pct: tank ? Number(tank) : null,
      chlorine_applied: applied ? Number(applied) : null,
      chlorine_applied_unit: applied ? unit : null,
      reading_id: readingId || null,
      appearance: appearance || null,
      status,
      notes: notes || null,
      client_id: newClientId(),
    }),
    // Si el servidor la deja en Alerta (cloro fuera de rango, agua no clara), la linea de la toma lo muestra.
    onSuccess: () => { invalidate(); onDone(); },
    onError: (err) => setError(errText(err, "No se pudo guardar la toma.")),
  });
  return (
    <div className="mt-2 space-y-2 rounded-lg border border-slate-200 bg-slate-50 p-3">
      <p className="text-xs text-slate-600"><strong>Registrar:</strong> {moment.record_text}</p>
      <div className="grid gap-2 sm:grid-cols-3">
        <label className="text-xs text-slate-600">Nivel del tanque (%)
          <input type="number" min={0} max={100} className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm" value={tank} onChange={(e) => setTank(e.target.value)} />
        </label>
        <label className="text-xs text-slate-600">Cloro aplicado
          <span className="mt-1 flex gap-1">
            <input type="number" min={0} step="any" className="w-full rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm" value={applied} onChange={(e) => setApplied(e.target.value)} />
            <select aria-label="Unidad" className="rounded-lg border border-slate-300 bg-white px-2 text-sm" value={unit} onChange={(e) => setUnit(e.target.value as "g" | "ml")}>
              <option value="g">g</option>
              <option value="ml">ml</option>
            </select>
          </span>
        </label>
        <label className="text-xs text-slate-600">Cloro residual (medición de hoy)
          <select className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-2 py-1.5 text-sm" value={readingId} onChange={(e) => setReadingId(e.target.value)}>
            <option value="">— sin medición —</option>
            {chlorine.map((r) => (
              <option key={r.reading_id} value={r.reading_id}>{time(r.measured_at)} · {r.point_name ?? "sin punto"} · {r.value} {r.unit} ({r.result_label ?? "sin regla"})</option>
            ))}
          </select>
        </label>
      </div>
      <div className="flex flex-wrap items-center gap-2 text-xs text-slate-600">
        Aspecto:
        {(Object.keys(APPEARANCE) as (keyof typeof APPEARANCE)[]).map((a) => (
          <button key={a} onClick={() => setAppearance(appearance === a ? "" : a)} aria-pressed={appearance === a}
            className={`rounded-lg border-2 px-3 py-1 text-sm font-semibold ${appearance === a ? "border-indigo-600 bg-indigo-600 text-white" : "border-slate-300 bg-white text-slate-700"}`}>
            {APPEARANCE[a]}
          </button>
        ))}
        <span className="ml-3">Estado:</span>
        {(Object.keys(LOG_STATUS) as ("good" | "alert")[]).map((s) => (
          <button key={s} onClick={() => setStatus(s)} aria-pressed={status === s}
            className={`rounded-lg border-2 px-3 py-1 text-sm font-semibold ${status === s ? (s === "good" ? "border-emerald-600 bg-emerald-600 text-white" : "border-red-600 bg-red-600 text-white") : "border-slate-300 bg-white text-slate-700"}`}>
            {LOG_STATUS[s].label}
          </button>
        ))}
      </div>
      <input aria-label="Novedades" className="w-full rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm" placeholder="Novedades, acción tomada, pendientes" value={notes} onChange={(e) => setNotes(e.target.value)} />
      {error && <p className="text-sm text-red-600">{error}</p>}
      <div className="flex gap-2">
        <button onClick={() => mutation.mutate()} disabled={mutation.isPending} className="rounded-lg bg-indigo-600 px-3 py-1.5 text-sm font-semibold text-white hover:bg-indigo-700 disabled:opacity-50">
          {mutation.isPending ? "Guardando…" : "Guardar toma"}
        </button>
        <button onClick={onDone} className="px-2 text-sm text-slate-500 hover:text-slate-700">Cancelar</button>
      </div>
    </div>
  );
}

function EntryLine({ e }: { e: OperationLogEntry }) {
  const parts = [
    e.tank_level_pct !== null && `tanque ${e.tank_level_pct} %`,
    e.chlorine_applied !== null && `aplicado ${e.chlorine_applied} ${e.chlorine_applied_unit}`,
    e.residual_chlorine !== null && `residual ${e.residual_chlorine} mg/L (${e.residual_result ?? "sin regla"})`,
    e.appearance && APPEARANCE[e.appearance],
  ].filter(Boolean);
  return (
    <li className="flex flex-wrap items-center gap-2 py-1 text-sm">
      <span className="tabular-nums text-slate-500">{time(e.logged_at)}</span>
      <span className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ${LOG_STATUS[e.status].cls}`}>{LOG_STATUS[e.status].label}</span>
      <span className="text-slate-700">{parts.join(" · ") || "—"}</span>
      {e.notes && <span className="text-slate-500">· {e.notes}</span>}
    </li>
  );
}

function TodaySection() {
  const { data, error, isLoading } = useQuery({ queryKey: TODAY_KEY, queryFn: getOperationsToday, retry: false });
  const [open, setOpen] = useState<string | null>(null);
  if (isLoading) return <SectionCard title="Hoy"><p className="text-sm text-slate-500">Cargando…</p></SectionCard>;
  if (error) {
    return (
      <SectionCard title="Hoy">
        <p className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
          {errText(error, "No se pudo cargar el día.")}{" "}
          {error instanceof ApiError && error.status === 409 && <Link to="/configuration#timezone" className="font-semibold underline">Ir a Configuración</Link>}
        </p>
      </SectionCard>
    );
  }
  if (!data) return null;
  const s = data.summary;
  return (
    <SectionCard
      title={`Hoy · ${new Date(`${data.date}T12:00:00`).toLocaleDateString(appLocale(), { weekday: "long", day: "numeric", month: "long" })}`}
      description="La rutina diaria en el orden de la guía. Registre cada toma en su momento; si el cloro sale fuera de rango, la toma queda en alerta y se abre un hallazgo para la directiva."
    >
      {s.active_emergencies > 0 && (
        <Link to="/emergencies#active" className="mb-4 flex items-center justify-between gap-3 rounded-lg border border-red-400 bg-red-100 p-3 text-sm text-red-900 hover:bg-red-200">
          <span><strong>Emergencia activa:</strong> {s.active_emergencies} emergencia{s.active_emergencies === 1 ? "" : "s"} en curso. Siga el plan: primera acción, mensaje a la comunidad y a quién avisar.</span>
          <span className="font-semibold">Ver ›</span>
        </Link>
      )}
      {s.critical_quality_open > 0 && (
        <Link to="/quality#alerts" className="mb-4 flex items-center justify-between gap-3 rounded-lg border border-red-300 bg-red-50 p-3 text-sm text-red-900 hover:bg-red-100">
          <span><strong>Alerta crítica de calidad:</strong> {s.critical_quality_open} resultado{s.critical_quality_open === 1 ? "" : "s"} de laboratorio con contaminación (E. coli). Informe a la {term("board")} y coordine con {term("local_government")}, {term("health_authority")} o {term("regulator")}.</span>
          <span className="font-semibold">Ver ›</span>
        </Link>
      )}
      <Link to="/operator" className="mb-4 flex items-center justify-between gap-3 rounded-lg border border-indigo-200 bg-indigo-50 p-3 text-sm text-indigo-900 hover:bg-indigo-100">
        <span><strong>App del operador:</strong> para el teléfono, funciona sin conexión y envía al volver la señal.</span>
        <span className="font-semibold">Abrir ›</span>
      </Link>
      <div className="mb-4 flex flex-wrap gap-2 text-xs">
        <span className={`rounded-full px-2.5 py-1 font-semibold ${s.points_due ? "bg-amber-50 text-amber-800" : "bg-emerald-50 text-emerald-700"}`}>{s.points_due} punto{s.points_due === 1 ? "" : "s"} por medir</span>
        <span className="rounded-full bg-slate-100 px-2.5 py-1 font-semibold text-slate-700">{s.readings_today} mediciones hoy</span>
        <span className={`rounded-full px-2.5 py-1 font-semibold ${s.out_of_range_today ? "bg-red-50 text-red-700" : "bg-slate-100 text-slate-700"}`}>{s.out_of_range_today} fuera de rango</span>
        <span className="rounded-full bg-slate-100 px-2.5 py-1 font-semibold text-slate-700">{s.entries_today} tomas en bitácora</span>
        {s.open_reading_findings > 0 && (
          <Link to="/system#findings" className="rounded-full bg-red-50 px-2.5 py-1 font-semibold text-red-700 hover:underline">{s.open_reading_findings} hallazgo{s.open_reading_findings === 1 ? "" : "s"} de calidad abierto{s.open_reading_findings === 1 ? "" : "s"} ›</Link>
        )}
      </div>
      {data.moments.length === 0 && <EmptyState message="Ningún paquete activo define una rutina diaria." />}
      <ol className="space-y-3">
        {data.moments.map((m, i) => (
          <li key={`${m.pack_id}-${m.code}`} className="rounded-lg border border-slate-200 p-3">
            <div className="flex flex-wrap items-start justify-between gap-2">
              <div className="min-w-0 flex-1">
                <h3 className="text-sm font-semibold text-slate-900">
                  <span className={`mr-2 inline-flex h-6 w-6 items-center justify-center rounded-full text-xs font-bold ${m.entries.length ? "bg-emerald-600 text-white" : "bg-slate-200 text-slate-700"}`}>{i + 1}</span>
                  {m.label}
                </h3>
                <p className="mt-1 text-xs text-slate-600"><strong>Revisar:</strong> {m.check_text}</p>
              </div>
              {open !== m.code && (
                <button onClick={() => setOpen(m.code)} className="rounded-lg bg-indigo-600 px-3 py-1.5 text-sm font-semibold text-white hover:bg-indigo-700">
                  {m.entries.length ? "Agregar otra toma" : "Registrar toma"}
                </button>
              )}
            </div>
            {m.entries.length > 0 && <ul className="mt-2 divide-y divide-slate-100">{m.entries.map((e) => <EntryLine key={e.entry_id} e={e} />)}</ul>}
            {open === m.code && <LogEntryForm moment={m} readings={data.readings} onDone={() => setOpen(null)} />}
          </li>
        ))}
      </ol>
    </SectionCard>
  );
}

// ── Medir ─────────────────────────────────────────────────────────────

function MeasureSection() {
  const invalidate = useInvalidateOperations();
  const { data: catalog } = useQuery({ queryKey: ["operations-catalog"], queryFn: getOperationsCatalog });
  const { data: points } = useQuery({ queryKey: ["sampling-points"], queryFn: () => getSamplingPoints(), retry: false });
  const [pointId, setPointId] = useState("");
  const [paramCode, setParamCode] = useState("free_chlorine");
  const [value, setValue] = useState("");
  const [action, setAction] = useState("");
  const [result, setResult] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const param: FieldParameter | undefined = catalog?.parameters.find((p) => p.code === paramCode);
  const band = useMemo(() => (value === "" ? null : previewBand(param?.bands ?? null, Number(value))), [param, value]);

  const mutation = useMutation({
    mutationFn: () => recordFieldReading({
      parameter_code: paramCode, value: Number(value), sampling_point_id: pointId || null,
      action_taken: action || null, measured_at: new Date().toISOString(), client_id: newClientId(),
    }),
    onSuccess: (r) => {
      invalidate();
      setError(null);
      setValue("");
      setAction("");
      setResult(`${r.parameter_label} ${r.value} ${r.unit}${r.point_name ? ` en ${r.point_name}` : ""}: ${r.result_label ?? "guardada sin regla del paquete"}.${r.finding_created ? " Se abrió un hallazgo para la directiva." : r.finding_id ? " Se sumó al hallazgo abierto de este punto." : ""}`);
    },
    onError: (err) => setError(errText(err, "No se pudo guardar la medición.")),
  });

  return (
    <SectionCard title={`Registrar medición${formSuffix("field_readings")}`} description="Mida en el punto, anote el resultado y la acción tomada. Repita toda medición dudosa antes de ajustar la dosis.">
      <div className="grid gap-3 sm:grid-cols-[1fr_12rem_9rem]">
        <label className="text-xs text-slate-600">Punto
          <select className="mt-1 w-full rounded-lg border border-slate-300 px-2 py-1.5 text-sm" value={pointId} onChange={(e) => setPointId(e.target.value)}>
            <option value="">— elija el punto —</option>
            {(points ?? []).map((p) => <option key={p.point_id} value={p.point_id}>{p.kind_label} · {p.name}</option>)}
          </select>
        </label>
        <label className="text-xs text-slate-600">Parámetro
          <select className="mt-1 w-full rounded-lg border border-slate-300 px-2 py-1.5 text-sm" value={paramCode} onChange={(e) => setParamCode(e.target.value)}>
            {(catalog?.parameters ?? []).map((p) => <option key={p.code} value={p.code}>{p.label}</option>)}
          </select>
        </label>
        <label className="text-xs text-slate-600">Resultado {param?.unit && `(${param.unit})`}
          <input type="number" step="0.01" min={0} inputMode="decimal" className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-1.5 text-sm" value={value} onChange={(e) => setValue(e.target.value)} />
        </label>
      </div>
      {points && points.length === 0 && <p className="mt-2 text-xs text-amber-800">Todavía no hay puntos de medición: créelos abajo, en "Puntos de medición".</p>}
      {band && (
        <div className={`mt-3 rounded-lg p-3 text-sm ${SEVERITY_STYLE[band.severity]}`}>
          <strong>{band.label}.</strong> {band.action}
        </div>
      )}
      {param && !param.bands && <p className="mt-2 text-xs text-slate-500">Ningún paquete activo tiene regla para este parámetro: se guardará sin interpretación.</p>}
      {param?.citation && <p className="mt-1 text-[11px] text-slate-500">{param.citation}</p>}
      <input aria-label="Acción tomada" className="mt-3 w-full rounded-lg border border-slate-300 px-3 py-1.5 text-sm" placeholder="Acción tomada (si corresponde)" value={action} onChange={(e) => setAction(e.target.value)} />
      {error && <p className="mt-2 text-sm text-red-600">{error}</p>}
      {result && <p role="status" className="mt-2 text-sm text-emerald-800">{result}</p>}
      <button
        onClick={() => mutation.mutate()}
        disabled={mutation.isPending || value === "" || !pointId}
        className="mt-3 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-700 disabled:opacity-50"
      >
        {mutation.isPending ? "Guardando…" : "Guardar medición"}
      </button>
    </SectionCard>
  );
}

// ── Dosificacion (Guia 3 §3.5) ────────────────────────────────────────

const PURPOSE_LABEL: Record<ChemicalProduct["purpose"], string> = {
  disinfection: "Desinfección (cloro)",
  coagulation: "Coagulante",
  ph_adjustment: "Regulador de pH",
};
const GUARD_STYLE: Record<string, string> = {
  stop: "border-red-200 bg-red-50 text-red-900",
  warn: "border-amber-200 bg-amber-50 text-amber-900",
  info: "border-slate-200 bg-slate-50 text-slate-700",
};

function DosingSection() {
  const queryClient = useQueryClient();
  const { data: products } = useQuery({ queryKey: ["chemical-products"], queryFn: () => getChemicalProducts() });
  const [productId, setProductId] = useState("");
  const [flow, setFlow] = useState("");
  const [dose, setDose] = useState("");
  const [calcError, setCalcError] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [purpose, setPurpose] = useState<ChemicalProduct["purpose"]>("disinfection");
  const [form, setForm] = useState<ChemicalProduct["form"]>("solid");
  const [pct, setPct] = useState("");
  const [prodError, setProdError] = useState<string | null>(null);

  const calc = useMutation({
    mutationFn: () => calculateDosing({ product_id: productId, flow_lps: Number(flow), dose_mg_l: Number(dose) }),
    onSuccess: () => setCalcError(null),
    onError: (err) => setCalcError(errText(err, "No se pudo calcular.")),
  });
  const create = useMutation({
    mutationFn: () => createChemicalProduct({ name, purpose, form, active_pct: Number(pct) }),
    onSuccess: (p) => { setName(""); setPct(""); setProdError(null); setProductId(p.product_id); queryClient.invalidateQueries({ queryKey: ["chemical-products"] }); },
    onError: (err) => setProdError(errText(err, "No se pudo guardar el producto.")),
  });
  const r = calc.data;

  return (
    <SectionCard
      title="Dosificación de cloro"
      description="Cálculo orientativo de la guía: gramos de producto por día = caudal (L/s) × 86.400 × dosis (mg/L) ÷ (% de cloro activo × 10). Antes de cambiar la dosis, mida; después de aplicar, vuelva a medir."
    >
      <div className="grid gap-3 sm:grid-cols-[1fr_9rem_9rem_auto]">
        <label className="text-xs text-slate-600">Producto
          <select className="mt-1 w-full rounded-lg border border-slate-300 px-2 py-1.5 text-sm" value={productId} onChange={(e) => { setProductId(e.target.value); calc.reset(); }}>
            <option value="">— elija el producto —</option>
            {(products ?? []).map((p) => <option key={p.product_id} value={p.product_id}>{p.name} · {p.active_pct} % · {PURPOSE_LABEL[p.purpose]}</option>)}
          </select>
        </label>
        <label className="text-xs text-slate-600">Caudal (L/s)
          <input type="number" step="any" min={0} inputMode="decimal" className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-1.5 text-sm" value={flow} onChange={(e) => setFlow(e.target.value)} />
        </label>
        <label className="text-xs text-slate-600">Dosis (mg/L)
          <input type="number" step="any" min={0} inputMode="decimal" className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-1.5 text-sm" value={dose} onChange={(e) => setDose(e.target.value)} />
        </label>
        <button onClick={() => calc.mutate()} disabled={!productId || !flow || !dose || calc.isPending}
          className="self-end rounded-lg bg-indigo-600 px-4 py-1.5 text-sm font-semibold text-white hover:bg-indigo-700 disabled:opacity-50">
          Calcular
        </button>
      </div>
      {calcError && <p className="mt-2 text-sm text-red-600">{calcError}</p>}
      {r && (
        <div className="mt-4 space-y-2">
          {r.result && (
            <div className={`rounded-lg border p-4 ${r.can_apply ? "border-emerald-200 bg-emerald-50" : "border-red-200 bg-white"}`}>
              <p className="text-2xl font-bold tabular-nums text-slate-900">{r.result.per_day.toLocaleString(appLocale())} {r.result.unit}/día</p>
              <p className="text-sm text-slate-600 tabular-nums">{r.result.per_hour.toLocaleString(appLocale())} {r.result.unit}/hora · {r.product.name} al {r.product.active_pct} %</p>
              {!r.can_apply && <p className="mt-1 text-sm font-semibold text-red-700">No aplicar sin revisar la causa y sin apoyo técnico (ver abajo).</p>}
            </div>
          )}
          {r.last_tank_residual && (
            <p className="text-xs text-slate-600">
              Último cloro en la salida del tanque: <strong>{r.last_tank_residual.value} mg/L</strong> ({r.last_tank_residual.result_label ?? "sin regla"}) · {dateTime(r.last_tank_residual.measured_at)}
            </p>
          )}
          {r.guards.map((g) => (
            <p key={g.code} className={`rounded-lg border p-3 text-sm ${GUARD_STYLE[g.level ?? "info"]}`}>
              {g.level === "stop" && <strong>Alto. </strong>}{g.level === "warn" && <strong>Revisar antes. </strong>}
              {g.message ?? g.code}
            </p>
          ))}
        </div>
      )}

      <h3 className="mt-6 text-sm font-semibold text-slate-900">Productos químicos</h3>
      <ul className="divide-y divide-slate-100">
        {(products ?? []).map((p) => (
          <li key={p.product_id} className="flex flex-wrap items-center gap-2 py-1.5 text-sm">
            <span className="flex-1 text-slate-800">{p.name}</span>
            <span className="text-xs text-slate-500">{PURPOSE_LABEL[p.purpose]} · {p.form === "solid" ? "sólido (g)" : "líquido (ml)"} · {p.active_pct} %</span>
          </li>
        ))}
        {products && products.length === 0 && <li className="py-2 text-sm text-slate-500">Todavía no hay productos registrados.</li>}
      </ul>
      <div className="mt-2 grid gap-2 rounded-lg border border-dashed border-slate-300 bg-slate-50 p-3 sm:grid-cols-[1fr_11rem_8rem_7rem_auto]">
        <input aria-label="Nombre del producto" className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm" placeholder="Nombre (p. ej. Hipoclorito de calcio 65 %)" value={name} onChange={(e) => setName(e.target.value)} />
        <select aria-label="Uso" className="rounded-lg border border-slate-300 bg-white px-2 py-1.5 text-sm" value={purpose} onChange={(e) => setPurpose(e.target.value as ChemicalProduct["purpose"])}>
          {(Object.keys(PURPOSE_LABEL) as ChemicalProduct["purpose"][]).map((k) => <option key={k} value={k}>{PURPOSE_LABEL[k]}</option>)}
        </select>
        <select aria-label="Presentación" className="rounded-lg border border-slate-300 bg-white px-2 py-1.5 text-sm" value={form} onChange={(e) => setForm(e.target.value as ChemicalProduct["form"])}>
          <option value="solid">Sólido</option>
          <option value="liquid">Líquido</option>
        </select>
        <input aria-label="Concentración (%)" type="number" min={0} max={100} step="any" className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm" placeholder="% activo" value={pct} onChange={(e) => setPct(e.target.value)} />
        <button onClick={() => create.mutate()} disabled={!name.trim() || !pct || create.isPending} className="rounded-lg bg-indigo-600 px-3 py-1.5 text-sm font-semibold text-white hover:bg-indigo-700 disabled:opacity-50">Agregar</button>
        {prodError && <p className="text-sm text-red-600 sm:col-span-5">{prodError}</p>}
      </div>
    </SectionCard>
  );
}

// ── Bitacora e historial ──────────────────────────────────────────────

function LogSection() {
  const { data } = useQuery({ queryKey: ["operation-log"], queryFn: () => getOperationLog({ limit: 100 }) });
  return (
    <SectionCard title={`Bitácora diaria${formSuffix("operation_log")}`} description={`Las últimas tomas registradas. La ${term("board")} la revisa periódicamente.`}>
      {data && data.length === 0 && <EmptyState message="Todavía no hay tomas en la bitácora." />}
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-200 text-left text-xs uppercase tracking-wide text-slate-500">
              <th className="py-2 pr-3 font-semibold">Fecha y hora</th>
              <th className="py-2 pr-3 font-semibold">Momento</th>
              <th className="py-2 pr-3 font-semibold">Nivel tanque</th>
              <th className="py-2 pr-3 font-semibold">Cloro aplicado</th>
              <th className="py-2 pr-3 font-semibold">Cloro residual</th>
              <th className="py-2 pr-3 font-semibold">Aspecto</th>
              <th className="py-2 pr-3 font-semibold">Estado</th>
              <th className="py-2 font-semibold">Novedades</th>
            </tr>
          </thead>
          <tbody>
            {(data ?? []).map((e) => (
              <tr key={e.entry_id} className="border-b border-slate-100 align-top last:border-0">
                <td className="whitespace-nowrap py-2 pr-3 tabular-nums text-slate-700">{dateTime(e.logged_at)}</td>
                <td className="py-2 pr-3 text-slate-700">{e.moment_label ?? "—"}</td>
                <td className="py-2 pr-3 tabular-nums">{e.tank_level_pct !== null ? `${e.tank_level_pct} %` : "—"}</td>
                <td className="py-2 pr-3 tabular-nums">{e.chlorine_applied !== null ? `${e.chlorine_applied} ${e.chlorine_applied_unit}` : "—"}</td>
                <td className="py-2 pr-3 tabular-nums">{e.residual_chlorine !== null ? `${e.residual_chlorine} mg/L` : "—"}</td>
                <td className="py-2 pr-3">{e.appearance ? APPEARANCE[e.appearance] : "—"}</td>
                <td className="py-2 pr-3"><span className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ${LOG_STATUS[e.status].cls}`}>{LOG_STATUS[e.status].label}</span></td>
                <td className="py-2 text-slate-600">{e.notes ?? ""}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </SectionCard>
  );
}

function ReadingsSection() {
  const { data: points } = useQuery({ queryKey: ["sampling-points"], queryFn: () => getSamplingPoints(), retry: false });
  const [pointId, setPointId] = useState("");
  const { data } = useQuery({ queryKey: ["field-readings", pointId], queryFn: () => getFieldReadings({ point_id: pointId || undefined, limit: 200 }) });
  return (
    <SectionCard title={`Mediciones${formSuffix("field_readings")}`} description="Mediciones fechadas, interpretadas y con la acción tomada. La interpretación es la de la regla vigente cuando se midió.">
      <select aria-label="Filtrar por punto" className="mb-3 rounded-lg border border-slate-300 px-2 py-1.5 text-sm" value={pointId} onChange={(e) => setPointId(e.target.value)}>
        <option value="">Todos los puntos</option>
        {(points ?? []).map((p) => <option key={p.point_id} value={p.point_id}>{p.name}</option>)}
      </select>
      {data && data.length === 0 && <EmptyState message="Todavía no hay mediciones." />}
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-200 text-left text-xs uppercase tracking-wide text-slate-500">
              <th className="py-2 pr-3 font-semibold">Fecha y hora</th>
              <th className="py-2 pr-3 font-semibold">Punto</th>
              <th className="py-2 pr-3 font-semibold">Parámetro</th>
              <th className="py-2 pr-3 font-semibold">Resultado</th>
              <th className="py-2 pr-3 font-semibold">Interpretación</th>
              <th className="py-2 font-semibold">Acción tomada</th>
            </tr>
          </thead>
          <tbody>
            {(data ?? []).map((r) => (
              <tr key={r.reading_id} className="border-b border-slate-100 align-top last:border-0">
                <td className="whitespace-nowrap py-2 pr-3 tabular-nums text-slate-700">{dateTime(r.measured_at)}</td>
                <td className="py-2 pr-3 text-slate-700">{r.point_name ?? "—"}</td>
                <td className="py-2 pr-3 text-slate-700">{r.parameter_label}</td>
                <td className="whitespace-nowrap py-2 pr-3 tabular-nums">{r.value} {r.unit}</td>
                <td className="py-2 pr-3">
                  {r.result_label
                    ? <span className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ${SEVERITY_STYLE[r.severity ?? "ok"]}`}>{r.result_label}</span>
                    : <span className="text-xs text-slate-400">sin regla</span>}
                  {r.finding_id && <Link to="/system#findings" className="ml-2 text-xs font-medium text-indigo-700 hover:underline">hallazgo ›</Link>}
                </td>
                <td className="py-2 text-slate-600">{r.action_taken ?? ""}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </SectionCard>
  );
}

// ── Lecturas manuales de medidores (0032) ─────────────────────────────

function ManualReadingsSection() {
  const { data } = useQuery({ queryKey: ["manual-readings"], queryFn: () => getManualMeterReadings({ limit: 100 }) });
  return (
    <SectionCard
      title="Lecturas manuales de medidores"
      description="Lecturas de micro y macromedidores tomadas a mano (en la app del operador, también sin conexión). Entran al mismo camino que la telemetría: las valida el motor VEE y de ahí salen consumo y balance."
    >
      <Link to="/operator" className="mb-3 inline-block text-sm font-semibold text-indigo-700 hover:underline">Tomar lecturas en la app del operador ›</Link>
      {data && data.length === 0 && <EmptyState message="Todavía no hay lecturas manuales." />}
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-200 text-left text-xs uppercase tracking-wide text-slate-500">
              <th className="py-2 pr-3 font-semibold">Fecha y hora</th>
              <th className="py-2 pr-3 font-semibold">Medidor</th>
              <th className="py-2 pr-3 font-semibold">Lectura</th>
              <th className="py-2 pr-3 font-semibold">Desde la anterior</th>
              <th className="py-2 pr-3 font-semibold">Leído por</th>
              <th className="py-2 font-semibold">Observaciones</th>
            </tr>
          </thead>
          <tbody>
            {(data ?? []).map((r) => (
              <tr key={r.manual_reading_id} className="border-b border-slate-100 align-top last:border-0">
                <td className="whitespace-nowrap py-2 pr-3 tabular-nums text-slate-700">{dateTime(r.read_at)}</td>
                <td className="py-2 pr-3 text-slate-700">{r.account_number} <span className="text-xs text-slate-500">({r.meter_type === "macro" ? "macro" : "micro"})</span></td>
                <td className="py-2 pr-3 tabular-nums">{r.value.toLocaleString(appLocale())} <span className="text-xs text-slate-500">{r.channel}</span></td>
                <td className="py-2 pr-3 tabular-nums">
                  {r.lower_confirmed ? <span className="text-xs font-semibold text-amber-800">medidor cambiado</span>
                    : r.previous_value !== null ? (r.value - r.previous_value).toLocaleString(appLocale(), { maximumFractionDigits: 3 }) : "—"}
                </td>
                <td className="py-2 pr-3 text-slate-600">{r.read_by.replace(/^portal:/, "")}</td>
                <td className="py-2 text-slate-600">{r.notes ?? ""}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </SectionCard>
  );
}

// ── Puntos de medicion ────────────────────────────────────────────────

const POINT_STATUS: Record<SamplingPoint["status"], { label: (p: SamplingPoint) => string; cls: string }> = {
  never: { label: () => "Sin medir", cls: "bg-slate-100 text-slate-700" },
  due: { label: () => "Toca medir", cls: "bg-amber-50 text-amber-800" },
  ok: { label: (p) => (p.days_since === 0 ? "Medido hoy" : `Hace ${p.days_since} día${p.days_since === 1 ? "" : "s"}`), cls: "bg-emerald-50 text-emerald-700" },
};

function PointsSection() {
  const invalidate = useInvalidateOperations();
  const { data: catalog } = useQuery({ queryKey: ["operations-catalog"], queryFn: getOperationsCatalog });
  const { data: points, error } = useQuery({ queryKey: ["sampling-points", "all"], queryFn: () => getSamplingPoints(true), retry: false });
  const [kind, setKind] = useState("");
  const [name, setName] = useState("");
  const [freq, setFreq] = useState("");
  const [msg, setMsg] = useState<string | null>(null);
  const create = useMutation({
    mutationFn: () => createSamplingPoint({ kind_code: kind, name, frequency_days: freq ? Number(freq) : null }),
    onSuccess: () => { setName(""); setFreq(""); setMsg(null); invalidate(); },
    onError: (err) => setMsg(errText(err, "No se pudo crear el punto.")),
  });
  const toggle = useMutation({
    mutationFn: (p: SamplingPoint) => updateSamplingPoint(p.point_id, { active: !p.active }),
    onSuccess: () => invalidate(),
  });
  const kindDefault = catalog?.point_kinds.find((k) => k.code === kind);

  return (
    <SectionCard title="Puntos de medición" description="Dónde se mide: la salida del tanque todos los días y puntos de la red en rotación (medio, lejano y crítico).">
      {error && <p className="mb-2 text-sm text-amber-800">{errText(error, "")}</p>}
      <ul className="divide-y divide-slate-100">
        {(points ?? []).map((p) => (
          <li key={p.point_id} className={`flex flex-wrap items-center gap-3 py-2 ${p.active ? "" : "opacity-50"}`}>
            <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[11px] font-medium text-slate-600">{p.kind_label}</span>
            <span className="min-w-0 flex-1 text-sm text-slate-800">
              {p.name}
              <span className="block text-xs text-slate-500">
                {p.effective_frequency_days ? `Cada ${p.effective_frequency_days} día${p.effective_frequency_days === 1 ? "" : "s"}` : "En rotación (sin frecuencia fija)"}
                {p.last_chlorine && ` · último cloro ${p.last_chlorine.value} mg/L (${p.last_chlorine.result_label ?? "sin regla"})`}
              </span>
            </span>
            {p.active && <span className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ${POINT_STATUS[p.status].cls}`}>{POINT_STATUS[p.status].label(p)}</span>}
            <button onClick={() => toggle.mutate(p)} className="text-xs font-medium text-slate-600 hover:underline">{p.active ? "Desactivar" : "Activar"}</button>
          </li>
        ))}
      </ul>
      <div className="mt-3 grid gap-2 rounded-lg border border-dashed border-slate-300 bg-slate-50 p-3 sm:grid-cols-[12rem_1fr_9rem_auto]">
        <select aria-label="Tipo de punto" className="rounded-lg border border-slate-300 bg-white px-2 py-1.5 text-sm" value={kind} onChange={(e) => setKind(e.target.value)}>
          <option value="">— tipo de punto —</option>
          {(catalog?.point_kinds ?? []).map((k) => <option key={k.code} value={k.code}>{k.label}</option>)}
        </select>
        <input aria-label="Nombre del punto" className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm" placeholder="Nombre que reconozca el operador (p. ej. Escuela del barrio)" value={name} onChange={(e) => setName(e.target.value)} />
        <input aria-label="Frecuencia en días" type="number" min={1} className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm" placeholder={kindDefault?.frequency_days ? `${kindDefault.frequency_days} (del tipo)` : "Cada N días"} value={freq} onChange={(e) => setFreq(e.target.value)} />
        <button onClick={() => create.mutate()} disabled={!kind || !name.trim() || create.isPending} className="rounded-lg bg-indigo-600 px-3 py-1.5 text-sm font-semibold text-white hover:bg-indigo-700 disabled:opacity-50">Agregar</button>
        {kindDefault && <p className="text-xs text-slate-500 sm:col-span-4">{kindDefault.purpose}</p>}
        {msg && <p className="text-sm text-red-600 sm:col-span-4">{msg}</p>}
      </div>
    </SectionCard>
  );
}

export function OperationsPage() {
  return (
    <StagePage title="Operación diaria">
      <SectionNav items={SECTIONS} />
      <NavSection id="today"><TodaySection /></NavSection>
      <NavSection id="measure"><MeasureSection /></NavSection>
      <NavSection id="dosing"><DosingSection /></NavSection>
      <NavSection id="log"><LogSection /></NavSection>
      <NavSection id="readings"><ReadingsSection /></NavSection>
      <NavSection id="meters"><ManualReadingsSection /></NavSection>
      <NavSection id="points"><PointsSection /></NavSection>
    </StagePage>
  );
}
