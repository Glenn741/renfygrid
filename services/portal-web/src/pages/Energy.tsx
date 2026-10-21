import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import {
  ApiError,
  createCustomerRequest,
  createEquipment,
  createMeteringPoint,
  downloadAssetsTemplate,
  getAssetCatalog,
  getAssetSummary,
  getCustomerRequests,
  getPqrCatalog,
  getEquipment,
  getEquipmentList,
  getMeteringPoint,
  getMeteringPoints,
  getXmPending,
  importAssetsFile,
  installEquipment,
  recordMeteringEvent,
  removeEquipment,
  reportToXm,
  savePointSection,
  updateCustomerRequest,
  updateEquipment,
  updateMeteringPoint,
  type AssetCatalog,
  type AssetImportResult,
  type FieldValue,
  type FormData,
  type FormSpec,
  type MeteringEvent,
  type MeteringPointInput,
  type Periodic,
} from "../api";
import { AppShell } from "../components/AppShell";
import { FieldInput } from "../components/FormEditor";
import { Icon } from "../components/Icon";
import { KpiTile } from "../components/KpiTile";
import { NavSection, SectionNav } from "../components/SectionNav";
import { EmptyState } from "../components/StagePage";
import { appLocale, badgeClass, label, options, toneHex } from "../catalog";
import { sectionsFor } from "../navigation";

// Modulo Energia (Track F, Q2, migraciones 0049 y 0050): fronteras
// comerciales, equipos y su hoja de vida segun el paquete regulatorio de la
// organizacion (en Colombia, el Codigo de Medida CREG 038 de 2014 y el
// formato de la Circular 119 de 2014). Todo lo que la pantalla ofrece --
// tipos de punto, posiciones, tipos de registro, campos de cada ficha -- sale
// del catalogo (`/assets/catalog`); la pantalla no conoce la regulacion.

const CARD = "rounded-xl border border-slate-200 bg-white p-5";
const INPUT = "w-full rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500";
const BTN = "rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-700 disabled:bg-indigo-300";
const BTN2 = "rounded-lg border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50";
const TH = "px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-slate-500";
const TD = "px-3 py-2 text-sm text-slate-700";
const CATALOG_KEY = ["assets", "catalog"] as const;

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

function useCatalog() {
  return useQuery({ queryKey: CATALOG_KEY, queryFn: getAssetCatalog, staleTime: 5 * 60_000 });
}

function PeriodicBadge({ periodic }: { periodic: Pick<Periodic, "status" | "due_on" | "reason"> & { activity?: Periodic["activity"] } }) {
  const what = periodic.activity === "routine_test" ? "Prueba de rutina" : periodic.activity === "calibration" ? "Calibración" : null;
  const title = [what, periodic.reason === "invalidated" ? "se retiró el sello o cambió la programación: recalibrar" : null,
    periodic.due_on ? `vence ${formatDay(periodic.due_on)}` : null].filter(Boolean).join(" · ");
  return (
    <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${badgeClass("periodic.status", periodic.status)}`} title={title}>
      {label("periodic.status", periodic.status)}
    </span>
  );
}

function StatusBadge({ domain, code }: { domain: string; code: string | null | undefined }) {
  return <span className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${badgeClass(domain, code)}`}>{label(domain, code)}</span>;
}

function DueSoonNotice({ days }: { days: number | null | undefined }) {
  if (days !== null && days !== undefined) return null;
  return (
    <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-2 text-sm text-amber-800">
      No se ha definido con cuántos días de anticipación avisar los vencimientos: solo se marca «al día» o «vencida».{" "}
      <Link className="font-semibold underline" to="/configuration#assets">Definirlo en Configuración</Link>.
    </div>
  );
}

// ── Editor de una ficha (datos como {fields: {clave: {value}}}) ───────

function RecordFields({ spec, data, onChange, disabled = false, idPrefix }: {
  spec: FormSpec; data: FormData; onChange: (d: FormData) => void; disabled?: boolean; idPrefix: string;
}) {
  const fields = spec.fields ?? [];
  const groups: { name: string | undefined; items: typeof fields }[] = [];
  for (const f of fields) {
    const last = groups[groups.length - 1];
    if (last && last.name === f.group) last.items.push(f);
    else groups.push({ name: f.group, items: [f] });
  }
  const value = (key: string): FieldValue => (data.fields?.[key]?.value ?? null) as FieldValue;
  const set = (key: string, v: FieldValue) => onChange({ fields: { ...(data.fields ?? {}), [key]: { value: v } } });
  return (
    <div className="space-y-4">
      {groups.map((g, gi) => (
        <fieldset key={`${g.name ?? "g"}-${gi}`}>
          {g.name && <legend className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">{g.name}</legend>}
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {g.items.map((f) => (
              <label key={f.key} className="text-sm font-medium text-slate-800" title={f.verify}>
                <span className="flex items-baseline gap-1">
                  {(f as { ref?: string }).ref && <span className="text-[11px] tabular-nums text-slate-400">{(f as { ref?: string }).ref}</span>}
                  {f.label}{f.required && <span className="text-red-600">*</span>}
                </span>
                <div className="mt-1">
                  <FieldInput def={f} value={value(f.key)} onChange={(v) => set(f.key, v)} disabled={disabled} id={`${idPrefix}-${f.key}`} />
                </div>
              </label>
            ))}
          </div>
        </fieldset>
      ))}
    </div>
  );
}

// ── Registrar en la bitacora ──────────────────────────────────────────

function EventForm({ scope, pointId, equipmentId, onDone }: {
  scope: "point" | "equipment"; pointId?: string; equipmentId?: string; onDone: (msg: string) => void;
}) {
  const queryClient = useQueryClient();
  const { data: cat } = useCatalog();
  const types = (cat?.event_types ?? []).filter((t) => t.manual && (t.scope === scope || t.scope === "any"));
  const [typeCode, setTypeCode] = useState("");
  const [day, setDay] = useState(todayIso());
  const [data, setData] = useState<FormData>({ fields: {} });
  const [notes, setNotes] = useState("");
  const [externalRef, setExternalRef] = useState("");
  const [error, setError] = useState<string | null>(null);
  const type = types.find((t) => t.code === typeCode);
  const save = useMutation({
    mutationFn: () => recordMeteringEvent({ type_code: typeCode, occurred_on: day, point_id: pointId ?? null, equipment_id: equipmentId ?? null,
      data, notes: notes || null, external_ref: externalRef || null }),
    onSuccess: (r) => {
      queryClient.invalidateQueries({ queryKey: ["assets"] });
      setTypeCode(""); setData({ fields: {} }); setNotes(""); setExternalRef(""); setError(null);
      onDone(`${type?.label ?? "Registro"} guardado en la bitácora${r.xm_status === "pending" ? "; queda pendiente de reportar a XM" : ""}.`);
    },
    onError: (err) => setError(errorText(err, "No se pudo guardar el registro.")),
  });
  return (
    <div className="rounded-lg border border-slate-200 bg-slate-50 p-4">
      <div className="grid gap-3 sm:grid-cols-3">
        <label className="text-sm font-medium text-slate-800">Qué se hizo
          <select className={`${INPUT} mt-1`} value={typeCode} onChange={(e) => { setTypeCode(e.target.value); setData({ fields: {} }); }}>
            <option value="">— Elija —</option>
            {types.map((t) => <option key={t.code} value={t.code}>{t.label}</option>)}
          </select>
        </label>
        <label className="text-sm font-medium text-slate-800">Fecha
          <input type="date" className={`${INPUT} mt-1`} value={day} max={todayIso()} onChange={(e) => setDay(e.target.value)} />
        </label>
        <label className="text-sm font-medium text-slate-800">Orden de campo (opcional)
          <input className={`${INPUT} mt-1`} value={externalRef} onChange={(e) => setExternalRef(e.target.value)} placeholder="p. ej. número de la orden" />
        </label>
      </div>
      {type && (
        <div className="mt-3 space-y-3">
          {type.source_ref && <p className="text-xs text-slate-500">Referencia: {type.source_ref}{type.requires_xm_update ? " · obliga a actualizar el registro ante XM" : ""}</p>}
          {(type.data_spec.fields ?? []).length > 0 && <RecordFields spec={type.data_spec} data={data} onChange={setData} idPrefix={`ev-${type.code}`} />}
          <label className="block text-sm font-medium text-slate-800">Observaciones
            <textarea className={`${INPUT} mt-1`} rows={2} value={notes} onChange={(e) => setNotes(e.target.value)} />
          </label>
          {error && <p className="text-sm text-red-700">{error}</p>}
          <button className={BTN} disabled={save.isPending} onClick={() => save.mutate()}>Guardar en la bitácora</button>
        </div>
      )}
    </div>
  );
}

function EventValue({ event }: { event: MeteringEvent }) {
  const spec = event.data_spec?.fields ?? [];
  const parts = spec.map((f) => {
    const v = event.data?.fields?.[f.key]?.value;
    if (v === null || v === undefined || v === "") return null;
    const shown = f.type === "choice" ? f.options?.find((o) => o.code === v)?.label ?? String(v)
      : f.type === "boolean" ? (v ? "Sí" : "No") : f.type === "date" ? formatDay(String(v)) : String(v);
    return `${f.label}: ${shown}`;
  }).filter(Boolean);
  return parts.length ? <span className="text-xs text-slate-500">{parts.join(" · ")}</span> : null;
}

function Timeline({ events, showEquipment = true }: { events: MeteringEvent[]; showEquipment?: boolean }) {
  if (!events.length) return <EmptyState message="Todavía no hay registros en la bitácora." />;
  return (
    <ol className="divide-y divide-slate-100">
      {events.map((e) => (
        <li key={e.id} className="flex flex-wrap items-start gap-x-3 gap-y-1 py-2">
          <span className="w-24 shrink-0 text-xs tabular-nums text-slate-500">{formatDay(e.occurred_on)}</span>
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2 text-sm">
              <span className="font-medium text-slate-900">{e.type_label}</span>
              {showEquipment && e.equipment_serial && (
                <Link className="text-indigo-700 hover:underline" to={`/energy/equipment/${e.equipment_id}`}>{e.equipment_serial}</Link>
              )}
              {e.xm_status && <StatusBadge domain="xm.status" code={e.xm_status} />}
              {e.external_ref && <span className="text-xs text-slate-500">orden {e.external_ref}</span>}
            </div>
            <EventValue event={e} />
            {e.notes && <div className="text-xs text-slate-600">{e.notes}</div>}
          </div>
          <span className="text-xs text-slate-400" title={`Registrado ${new Date(e.recorded_at).toLocaleString(appLocale())}`}>
            {e.recorded_by} · {label("event.source", e.source)}
          </span>
        </li>
      ))}
    </ol>
  );
}

// ── Mapa ──────────────────────────────────────────────────────────────

function PointsMap({ points, height = 380 }: { points: { id: string; code: string; name: string; lat: number; lon: number; periodic_status: string }[]; height?: number }) {
  const ref = useRef<HTMLDivElement>(null);
  const mapRef = useRef<L.Map | null>(null);
  const navigate = useNavigate();
  useEffect(() => {
    if (!ref.current) return;
    if (!mapRef.current) {
      mapRef.current = L.map(ref.current, { scrollWheelZoom: false });
      L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", { attribution: "© OpenStreetMap" }).addTo(mapRef.current);
    }
    const map = mapRef.current;
    const layer = L.layerGroup().addTo(map);
    for (const p of points) {
      L.circleMarker([p.lat, p.lon], { radius: 6, color: "#ffffff", weight: 1, fillColor: toneHex("periodic.status", p.periodic_status), fillOpacity: 0.9 })
        .bindTooltip(`${p.code} · ${p.name} · ${label("periodic.status", p.periodic_status)}`)
        .on("click", () => navigate(`/energy/points/${p.id}`))
        .addTo(layer);
    }
    if (points.length) map.fitBounds(L.latLngBounds(points.map((p) => [p.lat, p.lon] as [number, number])), { padding: [24, 24], maxZoom: 12 });
    else map.setView([4.6, -74.1], 5);
    return () => { layer.remove(); };
  }, [points, navigate]);
  useEffect(() => () => { mapRef.current?.remove(); mapRef.current = null; }, []);
  return <div ref={ref} style={{ height }} className="w-full rounded-lg border border-slate-200" />;
}

// ── Tablero ───────────────────────────────────────────────────────────

export function EnergyDashboardPage() {
  const queryClient = useQueryClient();
  const { data: cat } = useCatalog();
  const classPlural = (code: string) => cat?.equipment_classes.find((c) => c.code === code)?.plural ?? code;
  const { data, isLoading, error } = useQuery({ queryKey: ["assets", "summary"], queryFn: getAssetSummary });
  const { data: pending } = useQuery({ queryKey: ["assets", "xm-pending"], queryFn: getXmPending });
  const [selected, setSelected] = useState<string[]>([]);
  const [reportedOn, setReportedOn] = useState(todayIso());
  const [msg, setMsg] = useState<string | null>(null);
  const report = useMutation({
    mutationFn: () => reportToXm(selected, reportedOn),
    onSuccess: (r) => { setSelected([]); setMsg(`${r.reported} novedad(es) marcadas como reportadas a XM.`); queryClient.invalidateQueries({ queryKey: ["assets"] }); },
  });
  const p = data?.points_by_periodic ?? {};
  return (
    <AppShell title="Tablero de fronteras">
      <SectionNav items={sectionsFor("/energy")} />
      {isLoading && <p className="text-sm text-slate-500">Cargando…</p>}
      {error && <p className="text-sm text-red-700">{errorText(error, "No se pudo cargar el tablero.")}</p>}
      {data && (
        <div className="space-y-6">
          <DueSoonNotice days={data.due_soon_days} />
          {data.points_total === 0 && (
            <div className={CARD}>
              <h2 className="text-base font-semibold text-slate-900">Cómo empezar</h2>
              <ol className="mt-2 list-decimal space-y-1 pl-5 text-sm text-slate-700">
                <li>En <Link className="font-semibold text-indigo-700" to="/energy/points">Fronteras comerciales</Link>, descargue la plantilla y cargue sus fronteras y equipos (o regístrelos uno a uno).</li>
                <li>Cada equipo con su última calibración: el sistema calcula el vencimiento según el tipo de punto.</li>
                <li>Desde la hoja de vida de cada frontera registre visitas, sellos, accesos y cambios de equipo.</li>
              </ol>
            </div>
          )}
          <NavSection id="kpis">
            <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
              <KpiTile label="Fronteras" value={data.points_total} to="/energy/points" hint={`${data.equipment_total} equipos`} />
              <KpiTile label="Vencidas" value={p.overdue ?? 0} alert={(p.overdue ?? 0) > 0} to="/energy/points?periodic=overdue" hint="calibración o prueba" />
              <KpiTile label="Por vencer" value={data.due_soon_days == null ? null : p.due_soon ?? 0} alert={(p.due_soon ?? 0) > 0} to="/energy/points?periodic=due_soon"
                hint={data.due_soon_days == null ? "ventana sin definir" : `próximos ${data.due_soon_days} días`} />
              <KpiTile label="Sin registro" value={p.missing ?? 0} alert={(p.missing ?? 0) > 0} to="/energy/points?periodic=missing" hint="sin calibración cargada" />
              <KpiTile label="Sin medidor principal" value={data.points_without_main_meter} alert={data.points_without_main_meter > 0} to="/energy/points" hint="fronteras activas" />
              <KpiTile label="Novedades para XM" value={data.xm_pending} alert={data.xm_pending > 0} to="/energy#xm" hint="pendientes de reportar" />
            </div>
            <div className="mt-4 grid gap-4 lg:grid-cols-2">
              <div className={CARD}>
                <h2 className="mb-2 text-sm font-semibold text-slate-900">Fronteras por tipo de punto</h2>
                <table className="w-full">
                  <tbody>
                    {Object.entries(data.points_by_class).sort().map(([k, v]) => (
                      <tr key={k} className="border-t border-slate-100"><td className={TD}>{k === "—" ? "Sin tipo" : `Tipo ${k}`}</td><td className={`${TD} text-right tabular-nums`}>{v}</td></tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div className={CARD}>
                <h2 className="mb-2 text-sm font-semibold text-slate-900">Equipos por estado de calibración o prueba</h2>
                <table className="w-full">
                  <thead><tr><th className={TH}>Tipo</th>{["overdue", "due_soon", "missing", "ok"].map((s) => <th key={s} className={`${TH} text-right`}>{label("periodic.status", s)}</th>)}</tr></thead>
                  <tbody>
                    {Object.entries(data.equipment_periodic_by_class).map(([k, v]) => (
                      <tr key={k} className="border-t border-slate-100">
                        <td className={TD}>{classPlural(k)}</td>
                        {["overdue", "due_soon", "missing", "ok"].map((s) => <td key={s} className={`${TD} text-right tabular-nums`}>{v[s] ?? 0}</td>)}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </NavSection>
          <NavSection id="upcoming">
            <div className={CARD}>
              <h2 className="mb-2 text-base font-semibold text-slate-900">Calibraciones y pruebas por atender</h2>
              {data.upcoming.length === 0 ? <EmptyState message="Nada vencido ni por vencer." /> : (
                <table className="w-full">
                  <thead><tr><th className={TH}>Equipo</th><th className={TH}>Frontera</th><th className={TH}>Posición</th><th className={TH}>Estado</th><th className={TH}>Vence</th></tr></thead>
                  <tbody>
                    {data.upcoming.map((e) => (
                      <tr key={e.id} className="border-t border-slate-100">
                        <td className={TD}><Link className="text-indigo-700 hover:underline" to={`/energy/equipment/${e.id}`}>{e.serial}</Link> <span className="text-xs text-slate-500">{e.brand}</span></td>
                        <td className={TD}>{e.location && <Link className="hover:underline" to={`/energy/points/${e.location.point_id}`}>{e.location.point_code}</Link>}</td>
                        <td className={TD}>{e.location?.position_label}</td>
                        <td className={TD}><PeriodicBadge periodic={e.periodic} /></td>
                        <td className={TD}>{formatDay(e.periodic.due_on)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </NavSection>
          <NavSection id="map">
            <div className={CARD}>
              <h2 className="mb-2 text-base font-semibold text-slate-900">Mapa de fronteras</h2>
              <p className="mb-3 text-xs text-slate-500">El color es el estado de calibración de la frontera (el peor de sus equipos). {data.points_total - data.map.length > 0 ? `${data.points_total - data.map.length} frontera(s) sin coordenadas.` : ""}</p>
              <PointsMap points={data.map} />
              <p className="mt-2 text-sm"><Link className="font-semibold text-indigo-700 hover:underline" to="/energy/map">Abrir el mapa temático: pintar y filtrar por estado técnico, comercial, cliente, PQRS y equipos →</Link></p>
            </div>
          </NavSection>
          <NavSection id="xm">
            <div className={CARD}>
              <h2 className="text-base font-semibold text-slate-900">Novedades pendientes de reportar a XM</h2>
              <p className="mb-3 text-xs text-slate-500">Las novedades que obligan a actualizar el registro de la frontera ante el ASIC. Márquelas cuando las haya reportado.</p>
              {msg && <p className="mb-2 text-sm text-emerald-700">{msg}</p>}
              {!pending?.length ? <EmptyState message="No hay novedades pendientes." /> : (
                <>
                  <table className="w-full">
                    <thead><tr><th className={TH}></th><th className={TH}>Fecha</th><th className={TH}>Novedad</th><th className={TH}>Frontera</th><th className={TH}>Equipo</th></tr></thead>
                    <tbody>
                      {pending.slice(0, 200).map((e) => (
                        <tr key={e.id} className="border-t border-slate-100">
                          <td className={TD}><input type="checkbox" checked={selected.includes(e.id)} onChange={() => setSelected(selected.includes(e.id) ? selected.filter((x) => x !== e.id) : [...selected, e.id])} aria-label="Elegir" /></td>
                          <td className={TD}>{formatDay(e.occurred_on)}</td>
                          <td className={TD}>{e.type_label}</td>
                          <td className={TD}>{e.point_id && <Link className="text-indigo-700 hover:underline" to={`/energy/points/${e.point_id}`}>{e.point_code}</Link>}</td>
                          <td className={TD}>{e.equipment_serial}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  <div className="mt-3 flex flex-wrap items-end gap-3">
                    <button className={BTN2} onClick={() => setSelected(selected.length ? [] : pending.map((e) => e.id))}>{selected.length ? "Quitar selección" : "Elegir todas"}</button>
                    <label className="text-sm font-medium text-slate-800">Reportadas el
                      <input type="date" className={`${INPUT} mt-1`} value={reportedOn} max={todayIso()} onChange={(e) => setReportedOn(e.target.value)} />
                    </label>
                    <button className={BTN} disabled={!selected.length || report.isPending} onClick={() => report.mutate()}>Marcar {selected.length || ""} como reportadas</button>
                  </div>
                </>
              )}
            </div>
          </NavSection>
          <NavSection id="recent">
            <div className={CARD}>
              <h2 className="mb-2 text-base font-semibold text-slate-900">Últimos registros (30 días)</h2>
              <Timeline events={data.recent_events} />
            </div>
          </NavSection>
        </div>
      )}
    </AppShell>
  );
}

// ── Fronteras ─────────────────────────────────────────────────────────

const POINT_FIELDS: { key: keyof MeteringPointInput; label: string; type: "text" | "number" | "date"; required?: boolean }[] = [
  { key: "code", label: "Código de la frontera (SIC)", type: "text", required: true },
  { key: "name", label: "Nombre de la frontera", type: "text", required: true },
  { key: "customer_name", label: "Usuario (cliente)", type: "text", required: true },
  { key: "address", label: "Dirección", type: "text" },
  { key: "city", label: "Ciudad o municipio", type: "text" },
  { key: "region", label: "Departamento", type: "text" },
  { key: "lat", label: "Latitud", type: "number" },
  { key: "lon", label: "Longitud", type: "number" },
  { key: "voltage_kv", label: "Tensión de servicio (kV)", type: "number" },
  { key: "capacity_kva", label: "Capacidad instalada (kVA)", type: "number" },
  { key: "consumption_mwh_month", label: "Consumo mensual (MWh)", type: "number" },
  { key: "registered_on", label: "Registro ante el ASIC", type: "date" },
  { key: "verified_on", label: "Verificación inicial", type: "date" },
  { key: "export_code", label: "Código SIC de exportación", type: "text" },
  { key: "niu", label: "NIU", type: "text" },
];

function PointForm({ initial, cat, onSubmit, submitLabel, busy, error }: {
  initial: MeteringPointInput; cat: AssetCatalog | undefined; onSubmit: (v: MeteringPointInput) => void; submitLabel: string; busy: boolean; error: string | null;
}) {
  const [v, setV] = useState<MeteringPointInput>(initial);
  const set = (k: keyof MeteringPointInput, raw: string, type: string) =>
    setV({ ...v, [k]: raw === "" ? null : type === "number" ? Number(raw) : raw });
  return (
    <form className="space-y-3" onSubmit={(e) => { e.preventDefault(); onSubmit(v); }}>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {POINT_FIELDS.map((f) => (
          <label key={f.key} className="text-sm font-medium text-slate-800">{f.label}{f.required && <span className="text-red-600">*</span>}
            <input className={`${INPUT} mt-1`} type={f.type === "number" ? "number" : f.type} step="any" required={f.required}
              value={(v[f.key] as string | number | null | undefined) ?? ""} onChange={(e) => set(f.key, e.target.value, f.type)} />
          </label>
        ))}
        <label className="text-sm font-medium text-slate-800">Tipo de punto
          <select className={`${INPUT} mt-1`} value={v.point_class ?? ""} onChange={(e) => setV({ ...v, point_class: e.target.value || null })}>
            <option value="">— Sin definir —</option>
            {(cat?.point_classes ?? []).map((c) => <option key={c.code} value={c.code}>{c.label} (≥ {c.min_mwh_month.toLocaleString(appLocale())} MWh-mes o ≥ {c.min_mva} MVA)</option>)}
          </select>
        </label>
        <label className="text-sm font-medium text-slate-800">Estado
          <select className={`${INPUT} mt-1`} value={v.status ?? "active"} onChange={(e) => setV({ ...v, status: e.target.value })}>
            {options("metering_point.status").map((o) => <option key={o.code} value={o.code}>{o.label}</option>)}
          </select>
        </label>
        {([["customer_class", "customer.class", "Tipo de cliente"], ["market", "market", "Mercado"],
           ["commercial_status", "commercial.status", "Estado comercial"]] as const).map(([key, domain, title]) => (
          <label key={key} className="text-sm font-medium text-slate-800">{title}
            <select className={`${INPUT} mt-1`} value={(v[key] as string | null | undefined) ?? ""} onChange={(e) => setV({ ...v, [key]: e.target.value || null })}>
              <option value="">— Sin definir —</option>
              {options(domain).map((o) => <option key={o.code} value={o.code}>{o.label}</option>)}
            </select>
          </label>
        ))}
      </div>
      {error && <p className="text-sm text-red-700">{error}</p>}
      <button className={BTN} disabled={busy}>{submitLabel}</button>
    </form>
  );
}

function AssetImportPanel() {
  const queryClient = useQueryClient();
  const [file, setFile] = useState<{ name: string; base64: string } | null>(null);
  const [preview, setPreview] = useState<AssetImportResult | null>(null);
  const [done, setDone] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const readFile = (f: File | undefined) => {
    setPreview(null); setError(null); setDone(null);
    if (!f) { setFile(null); return; }
    const reader = new FileReader();
    reader.onload = () => { const url = String(reader.result ?? ""); setFile({ name: f.name, base64: url.slice(url.indexOf(",") + 1) }); };
    reader.readAsDataURL(f);
  };
  const send = async (dryRun: boolean) => {
    if (!file) return;
    setBusy(true); setError(null);
    try {
      const r = await importAssetsFile({ filename: file.name, content_base64: file.base64, dry_run: dryRun });
      if (dryRun) setPreview(r);
      else {
        setPreview(null); setFile(null);
        queryClient.invalidateQueries({ queryKey: ["assets"] });
        setDone(`Cargado: ${r.points_created} frontera(s) nuevas, ${r.points_updated} actualizadas, ${r.equipment_created} equipo(s), ${r.installed} instalación(es), ${r.calibrations} calibración(es), ${r.routine_tests} prueba(s) de rutina y ${r.requests_created} PQR${r.requests_unlinked ? ` (${r.requests_unlinked} sin frontera encontrada)` : ""}.${r.errors.length ? ` ${r.errors.length} fila(s) no se cargaron.` : ""}`);
      }
    } catch (err) {
      setError(errorText(err, "No se pudo leer el archivo."));
    } finally {
      setBusy(false);
    }
  };
  return (
    <section className={CARD}>
      <h2 className="text-base font-semibold text-slate-900">Cargar fronteras y equipos desde Excel</h2>
      <p className="mb-3 text-xs text-slate-500">
        1) Descargue la plantilla: trae hojas de fronteras, equipos y PQR (los mismos datos del reporte al SUI) y los códigos válidos. 2) Llénela con su inventario (cada equipo con la frontera
        y la posición donde está, y su última calibración). 3) Cárguela: primero verá lo que se va a grabar. Volver a cargar el mismo archivo no duplica nada.
      </p>
      <div className="flex flex-wrap items-end gap-3">
        <button className={BTN2} onClick={() => downloadAssetsTemplate().catch((err) => setError(errorText(err, "No se pudo descargar la plantilla.")))}>
          <span className="inline-flex items-center gap-1.5"><Icon name="download" className="h-4 w-4" />Descargar plantilla</span>
        </button>
        <label className="text-sm font-medium text-slate-800">Archivo (.xlsx o .csv)
          <input type="file" accept=".xlsx,.csv,.txt" className={`${INPUT} mt-1`} onChange={(e) => readFile(e.target.files?.[0])} />
        </label>
        <button className={BTN2} disabled={!file || busy} onClick={() => send(true)}>Ver qué se va a cargar</button>
      </div>
      {error && <p className="mt-3 text-sm text-red-700">{error}</p>}
      {done && <p className="mt-3 text-sm text-emerald-700">{done}</p>}
      {preview && (
        <div className="mt-4 rounded-lg border border-slate-200 bg-slate-50 p-4 text-sm">
          <p className="font-semibold text-slate-900">Vista previa (todavía no se grabó nada)</p>
          <ul className="mt-1 list-disc pl-5 text-slate-700">
            <li>{preview.points_created} frontera(s) nuevas y {preview.points_updated} que se actualizan</li>
            <li>{preview.equipment_created} equipo(s) nuevos ({preview.equipment_existing} ya existían) y {preview.installed} instalación(es)</li>
            <li>{preview.calibrations} calibración(es) y {preview.routine_tests} prueba(s) de rutina para la bitácora</li>
            {(preview.requests_created > 0 || preview.requests_existing > 0) && (
              <li>{preview.requests_created} PQR nuevas ({preview.requests_existing} ya estaban){preview.requests_unlinked ? `; ${preview.requests_unlinked} sin frontera con ese NIU o código` : ""}</li>
            )}
          </ul>
          {preview.errors.length > 0 && (
            <div className="mt-2">
              <p className="font-semibold text-red-700">{preview.errors.length} fila(s) con error (no se cargan):</p>
              <ul className="max-h-48 list-disc overflow-y-auto pl-5 text-xs text-red-700">
                {preview.errors.slice(0, 100).map((e, i) => <li key={i}>{e.sheet}, fila {e.row}: {e.message}</li>)}
              </ul>
            </div>
          )}
          <button className={`${BTN} mt-3`} disabled={busy} onClick={() => send(false)}>Cargar</button>
        </div>
      )}
    </section>
  );
}

export function MeteringPointsPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { data: cat } = useCatalog();
  const initialPeriodic = new URLSearchParams(window.location.search).get("periodic") ?? "";
  const [q, setQ] = useState("");
  const [pointClass, setPointClass] = useState("");
  const [periodic, setPeriodic] = useState(initialPeriodic);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const filters = { q, point_class: pointClass, periodic };
  const { data, isLoading } = useQuery({ queryKey: ["assets", "points", filters], queryFn: () => getMeteringPoints(filters) });
  const create = useMutation({
    mutationFn: createMeteringPoint,
    onSuccess: (p) => { queryClient.invalidateQueries({ queryKey: ["assets"] }); navigate(`/energy/points/${p.id}`); },
    onError: (err) => setError(errorText(err, "No se pudo crear la frontera.")),
  });
  const [page, setPage] = useState(0);
  const PAGE = 100;
  const rows = data?.points ?? [];
  useEffect(() => setPage(0), [q, pointClass, periodic]);
  return (
    <AppShell title="Fronteras comerciales">
      <div className="space-y-5">
        <DueSoonNotice days={data?.due_soon_days} />
        <div className={CARD}>
          <div className="flex flex-wrap items-end gap-3">
            <label className="min-w-[14rem] flex-1 text-sm font-medium text-slate-800">Buscar
              <input className={`${INPUT} mt-1`} value={q} onChange={(e) => setQ(e.target.value)} placeholder="Código, nombre, cliente o ciudad" />
            </label>
            <label className="text-sm font-medium text-slate-800">Tipo de punto
              <select className={`${INPUT} mt-1`} value={pointClass} onChange={(e) => setPointClass(e.target.value)}>
                <option value="">Todos</option>
                {(cat?.point_classes ?? []).map((c) => <option key={c.code} value={c.code}>{c.label}</option>)}
              </select>
            </label>
            <label className="text-sm font-medium text-slate-800">Calibración
              <select className={`${INPUT} mt-1`} value={periodic} onChange={(e) => setPeriodic(e.target.value)}>
                <option value="">Todas</option>
                {options("periodic.status").filter((o) => o.code !== "not_required").map((o) => <option key={o.code} value={o.code}>{o.label}</option>)}
              </select>
            </label>
            <button className={BTN} onClick={() => setCreating(!creating)}>{creating ? "Cerrar" : "Nueva frontera"}</button>
          </div>
          {creating && (
            <div className="mt-4 border-t border-slate-100 pt-4">
              <PointForm initial={{ status: "active" }} cat={cat} onSubmit={(v) => create.mutate(v)} submitLabel="Crear frontera" busy={create.isPending} error={error} />
            </div>
          )}
        </div>
        <div className={`${CARD} overflow-x-auto p-0`}>
          {isLoading ? <p className="p-5 text-sm text-slate-500">Cargando…</p> : rows.length === 0 ? (
            <div className="p-5"><EmptyState message="No hay fronteras con esos filtros." /></div>
          ) : (
            <>
              <table className="w-full min-w-[56rem]">
                <thead className="bg-slate-50"><tr>
                  <th className={TH}>Frontera</th><th className={TH}>Cliente</th><th className={TH}>Ciudad</th><th className={TH}>Tipo</th>
                  <th className={TH}>Estado</th><th className={TH}>Medidor principal</th><th className={TH}>Calibración</th><th className={TH}>Próximo vencimiento</th><th className={TH}>XM</th>
                </tr></thead>
                <tbody>
                  {rows.slice(page * PAGE, (page + 1) * PAGE).map((p) => (
                    <tr key={p.id} className="cursor-pointer border-t border-slate-100 hover:bg-indigo-50/40" onClick={() => navigate(`/energy/points/${p.id}`)}>
                      <td className={TD}><span className="font-medium text-slate-900">{p.code}</span><div className="text-xs text-slate-500">{p.name}</div></td>
                      <td className={TD}>{p.customer_name}</td>
                      <td className={TD}>{p.city}</td>
                      <td className={TD}>{p.point_class ? `Tipo ${p.point_class}` : "—"}</td>
                      <td className={TD}><StatusBadge domain="metering_point.status" code={p.status} /></td>
                      <td className={TD}>{p.main_meter ? `${p.main_meter.brand ?? ""} ${p.main_meter.serial}` : <span className="text-amber-700">Sin medidor</span>}</td>
                      <td className={TD}><PeriodicBadge periodic={{ status: p.periodic_status, due_on: p.next_due }} /></td>
                      <td className={TD}>{formatDay(p.next_due)}</td>
                      <td className={TD}>{p.xm_pending ? <StatusBadge domain="xm.status" code="pending" /> : ""}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <div className="flex items-center justify-between border-t border-slate-100 px-4 py-2 text-xs text-slate-500">
                <span>{rows.length.toLocaleString(appLocale())} fronteras</span>
                {rows.length > PAGE && (
                  <span className="flex items-center gap-2">
                    <button className={BTN2} disabled={page === 0} onClick={() => setPage(page - 1)}>Anterior</button>
                    {page + 1} de {Math.ceil(rows.length / PAGE)}
                    <button className={BTN2} disabled={(page + 1) * PAGE >= rows.length} onClick={() => setPage(page + 1)}>Siguiente</button>
                  </span>
                )}
              </div>
            </>
          )}
        </div>
        <AssetImportPanel />
      </div>
    </AppShell>
  );
}

function Section({ title, children, right, id }: { title: string; children: ReactNode; right?: ReactNode; id?: string }) {
  return (
    <section className={CARD} id={id}>
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-base font-semibold text-slate-900">{title}</h2>
        {right}
      </div>
      {children}
    </section>
  );
}

function InstallPanel({ pointId, onDone }: { pointId: string; onDone: (msg: string) => void }) {
  const queryClient = useQueryClient();
  const { data: cat } = useCatalog();
  const [position, setPosition] = useState("");
  const [search, setSearch] = useState("");
  const [equipmentId, setEquipmentId] = useState("");
  const [day, setDay] = useState(todayIso());
  const [externalRef, setExternalRef] = useState("");
  const [error, setError] = useState<string | null>(null);
  const pos = cat?.positions.find((p) => p.code === position);
  const { data: stock } = useQuery({
    queryKey: ["assets", "equipment", "stock", pos?.equipment_class, search],
    queryFn: () => getEquipmentList({ class_code: pos?.equipment_class, status: "stock", q: search }),
    enabled: Boolean(pos),
  });
  const install = useMutation({
    mutationFn: () => installEquipment(equipmentId, { point_id: pointId, position_code: position, installed_on: day, external_ref: externalRef || null }),
    onSuccess: (r) => {
      queryClient.invalidateQueries({ queryKey: ["assets"] });
      setEquipmentId(""); setPosition(""); setError(null);
      onDone(r.novelty ? "Equipo instalado. Como reemplaza a otro, quedó la novedad para reportar a XM." : "Equipo instalado.");
    },
    onError: (err) => setError(errorText(err, "No se pudo instalar el equipo.")),
  });
  return (
    <div className="rounded-lg border border-slate-200 bg-slate-50 p-4">
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <label className="text-sm font-medium text-slate-800">Posición
          <select className={`${INPUT} mt-1`} value={position} onChange={(e) => { setPosition(e.target.value); setEquipmentId(""); }}>
            <option value="">— Elija —</option>
            {(cat?.positions ?? []).map((p) => <option key={p.code} value={p.code}>{p.label}</option>)}
          </select>
        </label>
        <label className="text-sm font-medium text-slate-800">Buscar en bodega
          <input className={`${INPUT} mt-1`} value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Serie o marca" disabled={!pos} />
        </label>
        <label className="text-sm font-medium text-slate-800">Equipo
          <select className={`${INPUT} mt-1`} value={equipmentId} onChange={(e) => setEquipmentId(e.target.value)} disabled={!pos}>
            <option value="">— {stock?.equipment.length ?? 0} en bodega —</option>
            {(stock?.equipment ?? []).slice(0, 200).map((e) => <option key={e.id} value={e.id}>{e.serial} · {e.brand ?? ""} {e.model ?? ""}</option>)}
          </select>
        </label>
        <label className="text-sm font-medium text-slate-800">Fecha de instalación
          <input type="date" className={`${INPUT} mt-1`} value={day} max={todayIso()} onChange={(e) => setDay(e.target.value)} />
        </label>
        <label className="text-sm font-medium text-slate-800">Orden de campo (opcional)
          <input className={`${INPUT} mt-1`} value={externalRef} onChange={(e) => setExternalRef(e.target.value)} />
        </label>
      </div>
      {error && <p className="mt-2 text-sm text-red-700">{error}</p>}
      <button className={`${BTN} mt-3`} disabled={!equipmentId || install.isPending} onClick={() => install.mutate()}>Instalar</button>
      <p className="mt-2 text-xs text-slate-500">¿El equipo no está registrado? Regístrelo en <Link className="text-indigo-700 underline" to="/energy/equipment">Equipos</Link> y vuelva.</p>
    </div>
  );
}

function RemoveButton({ equipmentId, serial, onDone }: { equipmentId: string; serial: string; onDone: (msg: string) => void }) {
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [day, setDay] = useState(todayIso());
  const [reason, setReason] = useState("");
  const [status, setStatus] = useState("stock");
  const [error, setError] = useState<string | null>(null);
  const remove = useMutation({
    mutationFn: () => removeEquipment(equipmentId, { removed_on: day, reason: reason || null, new_status: status }),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["assets"] }); setOpen(false); onDone(`Equipo ${serial} retirado (${label("equipment.status", status).toLowerCase()}).`); },
    onError: (err) => setError(errorText(err, "No se pudo retirar el equipo.")),
  });
  if (!open) return <button className={BTN2} onClick={() => setOpen(true)}>Retirar</button>;
  return (
    <div className="mt-2 grid gap-2 rounded-lg border border-slate-200 bg-white p-3 sm:grid-cols-4">
      <input type="date" className={INPUT} value={day} max={todayIso()} onChange={(e) => setDay(e.target.value)} aria-label="Fecha de retiro" />
      <select className={INPUT} value={status} onChange={(e) => setStatus(e.target.value)} aria-label="A dónde va">
        {options("equipment.status").filter((o) => o.code !== "installed").map((o) => <option key={o.code} value={o.code}>{o.label}</option>)}
      </select>
      <input className={INPUT} value={reason} onChange={(e) => setReason(e.target.value)} placeholder="Motivo" aria-label="Motivo" />
      <div className="flex gap-2">
        <button className={BTN} disabled={remove.isPending} onClick={() => remove.mutate()}>Retirar</button>
        <button className={BTN2} onClick={() => setOpen(false)}>Cancelar</button>
      </div>
      {error && <p className="text-sm text-red-700 sm:col-span-4">{error}</p>}
    </div>
  );
}

function PointSectionEditor({ pointId, section }: { pointId: string; section: { id: string; title: string; form_spec: FormSpec; data: FormData; version: number; updated_by: string | null; updated_at: string | null; progress: { filled?: number; total?: number }; source_ref: string } }) {
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [data, setData] = useState<FormData>(section.data);
  const [msg, setMsg] = useState<string | null>(null);
  useEffect(() => setData(section.data), [section.data]);
  const save = useMutation({
    mutationFn: () => savePointSection(pointId, section.id, data),
    onSuccess: (r) => { setMsg(`Guardado (versión ${r.version}).`); queryClient.invalidateQueries({ queryKey: ["assets", "point", pointId] }); },
    onError: (err) => setMsg(errorText(err, "No se pudo guardar.")),
  });
  return (
    <div className="rounded-lg border border-slate-200">
      <button className="flex w-full items-center justify-between gap-3 px-4 py-3 text-left" onClick={() => setOpen(!open)} aria-expanded={open}>
        <span className="text-sm font-semibold text-slate-900">{section.title}</span>
        <span className="flex items-center gap-3 text-xs text-slate-500">
          {section.progress.filled ?? 0} de {section.progress.total ?? 0} datos
          {section.version > 0 && <span>· v{section.version} · {section.updated_by}</span>}
          <span className={`transition-transform ${open ? "rotate-90" : ""}`}><Icon name="expand" className="h-3.5 w-3.5" /></span>
        </span>
      </button>
      {open && (
        <div className="border-t border-slate-100 p-4">
          <p className="mb-3 text-xs text-slate-500">{section.source_ref}. Pase el cursor sobre un campo para ver su definición.</p>
          <RecordFields spec={section.form_spec} data={data} onChange={setData} idPrefix={`sec-${section.id}`} />
          <div className="mt-3 flex items-center gap-3">
            <button className={BTN} disabled={save.isPending} onClick={() => save.mutate()}>Guardar sección</button>
            {msg && <span className="text-sm text-slate-600">{msg}</span>}
          </div>
        </div>
      )}
    </div>
  );
}

// ── PQR de la frontera (0051) ─────────────────────────────────────────

function PqrSection({ pointId, account, onDone }: { pointId: string; account: string; onDone: (msg: string) => void }) {
  const queryClient = useQueryClient();
  const { data: list } = useQuery({ queryKey: ["assets", "pqr", pointId], queryFn: () => getCustomerRequests({ point_id: pointId }) });
  const { data: cat } = useQuery({ queryKey: ["assets", "pqr-catalog"], queryFn: getPqrCatalog, staleTime: 5 * 60_000 });
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ filing_number: "", filed_on: todayIso(), request_type: "1", cause_code: "", notes: "" });
  const [error, setError] = useState<string | null>(null);
  const [answering, setAnswering] = useState<string | null>(null);
  const [answer, setAnswer] = useState({ response_code: "", responded_on: todayIso(), status: "answered" });
  const create = useMutation({
    mutationFn: () => createCustomerRequest({ ...form, point_id: pointId, account, notes: form.notes || null }),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["assets"] }); setOpen(false); setError(null); onDone("PQR registrada."); },
    onError: (err) => setError(errorText(err, "No se pudo registrar la PQR.")),
  });
  const respond = useMutation({
    mutationFn: (id: string) => updateCustomerRequest(id, { ...answer, response_code: answer.response_code || null }),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["assets"] }); setAnswering(null); onDone("PQR actualizada."); },
    onError: (err) => setError(errorText(err, "No se pudo actualizar la PQR.")),
  });
  const typeLabel = (code: string) => cat?.request_types.find((t) => t.code === code)?.label ?? code;
  const responseLabel = (code: string | null) => (code ? cat?.responses.find((r) => r.code === code)?.label ?? code : "—");
  const openCount = (list ?? []).filter((q) => q.status === "open" || q.status === "appealed").length;
  return (
    <Section title={`PQR del usuario${openCount ? ` · ${openCount} abierta(s)` : ""}`} right={<button className={BTN2} onClick={() => setOpen(!open)}>{open ? "Cerrar" : "Registrar PQR"}</button>}>
      {open && (
        <div className="mb-4 grid gap-3 rounded-lg border border-slate-200 bg-slate-50 p-4 sm:grid-cols-2 lg:grid-cols-4">
          <label className="text-sm font-medium text-slate-800">Radicado
            <input className={`${INPUT} mt-1`} value={form.filing_number} onChange={(e) => setForm({ ...form, filing_number: e.target.value })} />
          </label>
          <label className="text-sm font-medium text-slate-800">Fecha de radicación
            <input type="date" className={`${INPUT} mt-1`} value={form.filed_on} max={todayIso()} onChange={(e) => setForm({ ...form, filed_on: e.target.value })} />
          </label>
          <label className="text-sm font-medium text-slate-800">Tipo de trámite
            <select className={`${INPUT} mt-1`} value={form.request_type} onChange={(e) => setForm({ ...form, request_type: e.target.value })}>
              {(cat?.request_types ?? []).map((t) => <option key={t.code} value={t.code}>{t.label}</option>)}
            </select>
          </label>
          <label className="text-sm font-medium text-slate-800">Causal (Superservicios)
            <select className={`${INPUT} mt-1`} value={form.cause_code} onChange={(e) => setForm({ ...form, cause_code: e.target.value })}>
              <option value="">— Elija —</option>
              {(["F", "P"] as const).map((g) => (
                <optgroup key={g} label={g === "F" ? "Facturación" : "Prestación"}>
                  {(cat?.causes ?? []).filter((c) => c.group_code === g).map((c) => <option key={c.code} value={c.code} title={c.description}>{c.code} · {c.label}</option>)}
                </optgroup>
              ))}
            </select>
          </label>
          <label className="text-sm font-medium text-slate-800 sm:col-span-2 lg:col-span-4">Observaciones
            <input className={`${INPUT} mt-1`} value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} />
          </label>
          {error && <p className="text-sm text-red-700 sm:col-span-4">{error}</p>}
          <div><button className={BTN} disabled={!form.filing_number || !form.cause_code || create.isPending} onClick={() => create.mutate()}>Registrar</button></div>
        </div>
      )}
      {!list?.length ? <EmptyState message="Esta frontera no tiene PQR registradas." /> : (
        <table className="w-full">
          <thead><tr><th className={TH}>Radicado</th><th className={TH}>Fecha</th><th className={TH}>Trámite</th><th className={TH}>Causal</th>
            <th className={TH}>Estado</th><th className={TH}>Respuesta</th><th className={TH}></th></tr></thead>
          <tbody>
            {list.map((q) => (
              <tr key={q.id} className="border-t border-slate-100 align-top">
                <td className={TD}>{q.filing_number}</td>
                <td className={TD}>{formatDay(q.filed_on)}</td>
                <td className={TD}>{typeLabel(q.request_type)}</td>
                <td className={TD}><span className="font-medium">{q.cause_code}</span> {q.cause_label}<div className="text-xs text-slate-500">{q.cause_group === "F" ? "Facturación" : "Prestación"}</div></td>
                <td className={TD}><StatusBadge domain="pqr.status" code={q.status} /></td>
                <td className={TD}>{responseLabel(q.response_code)}{q.responded_on ? <div className="text-xs text-slate-500">{formatDay(q.responded_on)}</div> : null}</td>
                <td className={TD}>
                  {q.status !== "closed" && answering !== q.id && <button className={BTN2} onClick={() => { setAnswering(q.id); setError(null); }}>Actualizar</button>}
                  {answering === q.id && (
                    <div className="grid gap-2">
                      <select className={INPUT} value={answer.status} onChange={(e) => setAnswer({ ...answer, status: e.target.value })} aria-label="Estado">
                        {options("pqr.status").map((o) => <option key={o.code} value={o.code}>{o.label}</option>)}
                      </select>
                      <select className={INPUT} value={answer.response_code} onChange={(e) => setAnswer({ ...answer, response_code: e.target.value })} aria-label="Respuesta">
                        <option value="">— Respuesta —</option>
                        {(cat?.responses ?? []).map((r) => <option key={r.code} value={r.code}>{r.label}</option>)}
                      </select>
                      <input type="date" className={INPUT} value={answer.responded_on} max={todayIso()} onChange={(e) => setAnswer({ ...answer, responded_on: e.target.value })} aria-label="Fecha de respuesta" />
                      <div className="flex gap-2">
                        <button className={BTN} disabled={respond.isPending} onClick={() => respond.mutate(q.id)}>Guardar</button>
                        <button className={BTN2} onClick={() => setAnswering(null)}>Cancelar</button>
                      </div>
                    </div>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </Section>
  );
}

export function MeteringPointPage() {
  const { pointId = "" } = useParams();
  const queryClient = useQueryClient();
  const { data: cat } = useCatalog();
  const { data: p, isLoading, error } = useQuery({ queryKey: ["assets", "point", pointId], queryFn: () => getMeteringPoint(pointId) });
  const [editing, setEditing] = useState(false);
  const [installing, setInstalling] = useState(false);
  const [recording, setRecording] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [editError, setEditError] = useState<string | null>(null);
  const update = useMutation({
    mutationFn: (v: MeteringPointInput) => updateMeteringPoint(pointId, v),
    onSuccess: () => { setEditing(false); setEditError(null); queryClient.invalidateQueries({ queryKey: ["assets"] }); },
    onError: (err) => setEditError(errorText(err, "No se pudo guardar.")),
  });
  const done = (m: string) => { setMsg(m); setInstalling(false); setRecording(false); };
  return (
    <AppShell title={p ? `Hoja de vida · ${p.code}` : "Hoja de vida"}>
      <div className="mb-3"><Link className="text-sm text-indigo-700 hover:underline" to="/energy/points">← Fronteras comerciales</Link></div>
      {isLoading && <p className="text-sm text-slate-500">Cargando…</p>}
      {error && <p className="text-sm text-red-700">{errorText(error, "No se pudo cargar la frontera.")}</p>}
      {p && (
        <div className="space-y-5">
          {msg && <p className="rounded-lg bg-emerald-50 px-4 py-2 text-sm text-emerald-800">{msg}</p>}
          <Section title={`${p.name} — ${p.customer_name}`} right={
            <div className="flex items-center gap-2">
              <StatusBadge domain="metering_point.status" code={p.status} />
              <PeriodicBadge periodic={{ status: p.periodic_status, due_on: null }} />
              <button className={BTN2} onClick={() => setEditing(!editing)}>{editing ? "Cerrar" : "Editar datos"}</button>
            </div>
          }>
            {editing ? (
              <PointForm initial={p} cat={cat} onSubmit={(v) => update.mutate(v)} submitLabel="Guardar" busy={update.isPending} error={editError} />
            ) : (
              <dl className="grid gap-x-6 gap-y-2 text-sm sm:grid-cols-2 lg:grid-cols-4">
                {[
                  ["Código SIC", p.code], ["NIU", p.niu], ["Tipo de punto", p.point_class ? `Tipo ${p.point_class}` : "Sin definir"],
                  ["Tipo sugerido por consumo/capacidad", p.suggested_point_class ? `Tipo ${p.suggested_point_class}` : "—"],
                  ["Dirección", [p.address, p.city, p.region].filter(Boolean).join(", ") || "—"], ["Tensión", p.voltage_kv != null ? `${p.voltage_kv} kV` : "—"],
                  ["Capacidad instalada", p.capacity_kva != null ? `${p.capacity_kva.toLocaleString(appLocale())} kVA` : "—"],
                  ["Consumo mensual", p.consumption_mwh_month != null ? `${p.consumption_mwh_month.toLocaleString(appLocale())} MWh` : "—"],
                  ["Registro ante el ASIC", formatDay(p.registered_on)], ["Verificación inicial", formatDay(p.verified_on)],
                  ["Tipo de cliente", p.customer_class ? label("customer.class", p.customer_class) : "—"],
                  ["Mercado", p.market ? label("market", p.market) : "—"],
                  ["Estado comercial", p.commercial_status ? label("commercial.status", p.commercial_status) : "—"],
                ].map(([k, v]) => (
                  <div key={k as string}><dt className="text-xs text-slate-500">{k}</dt><dd className="text-slate-900">{v ?? "—"}</dd></div>
                ))}
              </dl>
            )}
            {p.suggested_point_class && p.point_class && p.suggested_point_class !== p.point_class && (
              <p className="mt-3 rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-800">
                Por su consumo o capacidad esta frontera correspondería al tipo {p.suggested_point_class}, pero está registrada como tipo {p.point_class}. La frecuencia de calibración depende del tipo.
              </p>
            )}
          </Section>

          <Section title="Equipos instalados" right={<button className={BTN2} onClick={() => setInstalling(!installing)}>{installing ? "Cerrar" : "Instalar equipo"}</button>}>
            {installing && <div className="mb-4"><InstallPanel pointId={p.id} onDone={done} /></div>}
            {p.equipment.length === 0 ? <EmptyState message="Esta frontera no tiene equipos instalados." /> : (
              <div className="grid gap-3 md:grid-cols-2">
                {p.equipment.map((e) => (
                  <div key={e.installation_id} className="rounded-lg border border-slate-200 p-3">
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">{e.position_label}</div>
                        <Link className="text-sm font-semibold text-indigo-700 hover:underline" to={`/energy/equipment/${e.id}`}>{e.brand} {e.serial}</Link>
                        <div className="text-xs text-slate-500">{e.model} · instalado {formatDay(e.installed_on)}</div>
                      </div>
                      <PeriodicBadge periodic={e.periodic} />
                    </div>
                    <div className="mt-2 text-xs text-slate-600">
                      {e.periodic.activity === null ? "No requiere calibración periódica." :
                        `${e.periodic.activity === "routine_test" ? "Última prueba o calibración" : "Última calibración"}: ${formatDay(e.periodic.last_done)} · vence ${formatDay(e.periodic.due_on)}`}
                    </div>
                    <div className="mt-2"><RemoveButton equipmentId={e.id} serial={e.serial} onDone={done} /></div>
                  </div>
                ))}
              </div>
            )}
          </Section>

          <PqrSection pointId={p.id} account={p.niu ?? p.code} onDone={done} />

          <Section title="Bitácora de la frontera" right={<button className={BTN2} onClick={() => setRecording(!recording)}>{recording ? "Cerrar" : "Registrar"}</button>}>
            {recording && <div className="mb-4"><EventForm scope="point" pointId={p.id} onDone={done} /></div>}
            <Timeline events={p.events} />
          </Section>

          <Section title="Hoja de vida (Circular CREG 119 de 2014)">
            <p className="mb-3 text-xs text-slate-500">
              Los datos de los equipos (sección de cada medidor, CT, PT y módem), los sellos, las calibraciones, los accesos de nivel 2 y las novedades salen
              de los equipos instalados y de la bitácora. Aquí se completan las demás secciones del formato.
            </p>
            <div className="space-y-2">
              {p.sections.map((s) => <PointSectionEditor key={s.id} pointId={p.id} section={s} />)}
            </div>
          </Section>

          <Section title="Historial de instalaciones">
            <table className="w-full">
              <thead><tr><th className={TH}>Posición</th><th className={TH}>Equipo</th><th className={TH}>Instalado</th><th className={TH}>Retirado</th><th className={TH}>Motivo</th></tr></thead>
              <tbody>
                {p.installation_history.map((h) => (
                  <tr key={h.installation_id} className="border-t border-slate-100">
                    <td className={TD}>{cat?.positions.find((x) => x.code === h.position_code)?.label ?? h.position_code}</td>
                    <td className={TD}><Link className="text-indigo-700 hover:underline" to={`/energy/equipment/${h.equipment_id}`}>{h.brand} {h.serial}</Link></td>
                    <td className={TD}>{formatDay(h.installed_on)}</td>
                    <td className={TD}>{formatDay(h.removed_on)}</td>
                    <td className={TD}>{h.removal_reason}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Section>
        </div>
      )}
    </AppShell>
  );
}

// ── Equipos ───────────────────────────────────────────────────────────

export function EquipmentListPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { data: cat } = useCatalog();
  const [q, setQ] = useState("");
  const [klass, setKlass] = useState("");
  const [status, setStatus] = useState("");
  const [periodic, setPeriodic] = useState("");
  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState({ class_code: "meter", serial: "", brand: "", model: "", manufacturer: "", year: "", ownership: "" });
  const [error, setError] = useState<string | null>(null);
  const filters = { q, class_code: klass, status, periodic };
  const { data, isLoading } = useQuery({ queryKey: ["assets", "equipment", filters], queryFn: () => getEquipmentList(filters) });
  const create = useMutation({
    mutationFn: () => createEquipment({ ...form, year: form.year ? Number(form.year) : null, brand: form.brand || null, model: form.model || null,
      manufacturer: form.manufacturer || null, ownership: form.ownership || null }),
    onSuccess: (e) => { queryClient.invalidateQueries({ queryKey: ["assets"] }); navigate(`/energy/equipment/${e.id}`); },
    onError: (err) => setError(errorText(err, "No se pudo registrar el equipo.")),
  });
  const classLabel = useMemo(() => Object.fromEntries((cat?.equipment_classes ?? []).map((c) => [c.code, c.label])), [cat]);
  const rows = data?.equipment ?? [];
  const [page, setPage] = useState(0);
  const PAGE = 100;
  useEffect(() => setPage(0), [q, klass, status, periodic]);
  return (
    <AppShell title="Equipos">
      <div className="space-y-5">
        <div className={CARD}>
          <div className="flex flex-wrap items-end gap-3">
            <label className="min-w-[12rem] flex-1 text-sm font-medium text-slate-800">Buscar
              <input className={`${INPUT} mt-1`} value={q} onChange={(e) => setQ(e.target.value)} placeholder="Serie, marca o modelo" />
            </label>
            <label className="text-sm font-medium text-slate-800">Tipo
              <select className={`${INPUT} mt-1`} value={klass} onChange={(e) => setKlass(e.target.value)}>
                <option value="">Todos</option>
                {(cat?.equipment_classes ?? []).map((c) => <option key={c.code} value={c.code}>{c.plural}</option>)}
              </select>
            </label>
            <label className="text-sm font-medium text-slate-800">Estado
              <select className={`${INPUT} mt-1`} value={status} onChange={(e) => setStatus(e.target.value)}>
                <option value="">Todos</option>
                {options("equipment.status").map((o) => <option key={o.code} value={o.code}>{o.label}</option>)}
              </select>
            </label>
            <label className="text-sm font-medium text-slate-800">Calibración
              <select className={`${INPUT} mt-1`} value={periodic} onChange={(e) => setPeriodic(e.target.value)}>
                <option value="">Todas</option>
                {options("periodic.status").map((o) => <option key={o.code} value={o.code}>{o.label}</option>)}
              </select>
            </label>
            <button className={BTN} onClick={() => setCreating(!creating)}>{creating ? "Cerrar" : "Registrar equipo"}</button>
          </div>
          {creating && (
            <form className="mt-4 grid gap-3 border-t border-slate-100 pt-4 sm:grid-cols-2 lg:grid-cols-4" onSubmit={(e) => { e.preventDefault(); create.mutate(); }}>
              <label className="text-sm font-medium text-slate-800">Tipo
                <select className={`${INPUT} mt-1`} value={form.class_code} onChange={(e) => setForm({ ...form, class_code: e.target.value })}>
                  {(cat?.equipment_classes ?? []).map((c) => <option key={c.code} value={c.code}>{c.label}</option>)}
                </select>
              </label>
              {([["serial", "Número de serie"], ["brand", "Marca"], ["model", "Modelo"], ["manufacturer", "Fabricante"], ["year", "Año de fabricación"]] as const).map(([k, l]) => (
                <label key={k} className="text-sm font-medium text-slate-800">{l}{k === "serial" && <span className="text-red-600">*</span>}
                  <input className={`${INPUT} mt-1`} required={k === "serial"} type={k === "year" ? "number" : "text"} value={form[k]} onChange={(e) => setForm({ ...form, [k]: e.target.value })} />
                </label>
              ))}
              <label className="text-sm font-medium text-slate-800">Propiedad
                <select className={`${INPUT} mt-1`} value={form.ownership} onChange={(e) => setForm({ ...form, ownership: e.target.value })}>
                  <option value="">—</option>
                  {options("equipment.ownership").map((o) => <option key={o.code} value={o.code}>{o.label}</option>)}
                </select>
              </label>
              <div className="flex items-end"><button className={BTN} disabled={create.isPending}>Registrar</button></div>
              {error && <p className="text-sm text-red-700 sm:col-span-4">{error}</p>}
            </form>
          )}
        </div>
        <div className={`${CARD} overflow-x-auto p-0`}>
          {isLoading ? <p className="p-5 text-sm text-slate-500">Cargando…</p> : rows.length === 0 ? (
            <div className="p-5"><EmptyState message="No hay equipos con esos filtros." /></div>
          ) : (
            <>
              <table className="w-full min-w-[52rem]">
                <thead className="bg-slate-50"><tr>
                  <th className={TH}>Serie</th><th className={TH}>Tipo</th><th className={TH}>Marca y modelo</th><th className={TH}>Estado</th>
                  <th className={TH}>Dónde está</th><th className={TH}>Calibración / prueba</th><th className={TH}>Vence</th>
                </tr></thead>
                <tbody>
                  {rows.slice(page * PAGE, (page + 1) * PAGE).map((e) => (
                    <tr key={e.id} className="cursor-pointer border-t border-slate-100 hover:bg-indigo-50/40" onClick={() => navigate(`/energy/equipment/${e.id}`)}>
                      <td className={`${TD} font-medium text-slate-900`}>{e.serial}</td>
                      <td className={TD}>{classLabel[e.class_code] ?? e.class_code}</td>
                      <td className={TD}>{[e.brand, e.model].filter(Boolean).join(" · ")}</td>
                      <td className={TD}><StatusBadge domain="equipment.status" code={e.status} /></td>
                      <td className={TD}>{e.location ? <span>{e.location.point_code}<span className="text-xs text-slate-500"> · {e.location.position_label}</span></span> : "—"}</td>
                      <td className={TD}><PeriodicBadge periodic={e.periodic} /></td>
                      <td className={TD}>{formatDay(e.periodic.due_on)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <div className="flex items-center justify-between border-t border-slate-100 px-4 py-2 text-xs text-slate-500">
                <span>{rows.length.toLocaleString(appLocale())} equipos</span>
                {rows.length > PAGE && (
                  <span className="flex items-center gap-2">
                    <button className={BTN2} disabled={page === 0} onClick={() => setPage(page - 1)}>Anterior</button>
                    {page + 1} de {Math.ceil(rows.length / PAGE)}
                    <button className={BTN2} disabled={(page + 1) * PAGE >= rows.length} onClick={() => setPage(page + 1)}>Siguiente</button>
                  </span>
                )}
              </div>
            </>
          )}
        </div>
      </div>
    </AppShell>
  );
}

export function EquipmentPage() {
  const { equipmentId = "" } = useParams();
  const queryClient = useQueryClient();
  const { data: e, isLoading, error } = useQuery({ queryKey: ["assets", "equipment-detail", equipmentId], queryFn: () => getEquipment(equipmentId) });
  const [attrs, setAttrs] = useState<FormData>({ fields: {} });
  const [editingAttrs, setEditingAttrs] = useState(false);
  const [recording, setRecording] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  useEffect(() => { if (e) setAttrs(e.attributes); }, [e]);
  const saveAttrs = useMutation({
    mutationFn: () => updateEquipment(equipmentId, { attributes: attrs }),
    onSuccess: () => { setMsg("Ficha técnica guardada."); setEditingAttrs(false); queryClient.invalidateQueries({ queryKey: ["assets"] }); },
    onError: (err) => setMsg(errorText(err, "No se pudo guardar la ficha.")),
  });
  const setStatus = useMutation({
    mutationFn: (status: string) => updateEquipment(equipmentId, { status }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["assets"] }),
    onError: (err) => setMsg(errorText(err, "No se pudo cambiar el estado.")),
  });
  return (
    <AppShell title={e ? `${e.class_label} ${e.serial}` : "Equipo"}>
      <div className="mb-3"><Link className="text-sm text-indigo-700 hover:underline" to="/energy/equipment">← Equipos</Link></div>
      {isLoading && <p className="text-sm text-slate-500">Cargando…</p>}
      {error && <p className="text-sm text-red-700">{errorText(error, "No se pudo cargar el equipo.")}</p>}
      {e && (
        <div className="space-y-5">
          {msg && <p className="rounded-lg bg-emerald-50 px-4 py-2 text-sm text-emerald-800">{msg}</p>}
          <Section title={`${e.brand ?? ""} ${e.model ?? ""} · serie ${e.serial}`} right={
            <div className="flex items-center gap-2">
              <StatusBadge domain="equipment.status" code={e.status} />
              <PeriodicBadge periodic={e.periodic} />
            </div>
          }>
            <dl className="grid gap-x-6 gap-y-2 text-sm sm:grid-cols-2 lg:grid-cols-4">
              {[
                ["Tipo", e.class_label], ["Fabricante", e.manufacturer], ["Año de fabricación", e.year], ["Propiedad", e.ownership ? label("equipment.ownership", e.ownership) : "—"],
                ["Dónde está", e.location ? `${e.location.point_code} · ${e.location.position_label}` : label("equipment.status", e.status)],
                ["Instalado desde", formatDay(e.location?.installed_on)],
                [e.periodic.activity === "routine_test" ? "Última prueba o calibración" : "Última calibración", formatDay(e.periodic.last_done)],
                ["Vence", formatDay(e.periodic.due_on)],
              ].map(([k, v]) => <div key={k as string}><dt className="text-xs text-slate-500">{k}</dt><dd className="text-slate-900">{v ?? "—"}</dd></div>)}
            </dl>
            {e.location && <p className="mt-3 text-sm"><Link className="text-indigo-700 hover:underline" to={`/energy/points/${e.location.point_id}`}>Ver la hoja de vida de la frontera {e.location.point_code} →</Link></p>}
            {!e.location && e.status !== "retired" && (
              <div className="mt-3 flex flex-wrap items-center gap-2 text-sm">
                <span className="text-slate-600">Mover a:</span>
                {options("equipment.status").filter((o) => o.code !== "installed" && o.code !== e.status).map((o) => (
                  <button key={o.code} className={BTN2} onClick={() => setStatus.mutate(o.code)}>{o.label}</button>
                ))}
              </div>
            )}
          </Section>

          <Section title="Bitácora del equipo" right={<button className={BTN2} onClick={() => setRecording(!recording)}>{recording ? "Cerrar" : "Registrar"}</button>}>
            {recording && <div className="mb-4"><EventForm scope="equipment" equipmentId={e.id} onDone={(m) => { setMsg(m); setRecording(false); }} /></div>}
            <Timeline events={e.events} showEquipment={false} />
          </Section>

          {e.attributes_form && (
            <Section title={e.attributes_form.title} right={
              <span className="flex items-center gap-2 text-xs text-slate-500">
                {e.attributes_progress?.filled ?? 0} de {e.attributes_progress?.total ?? 0} datos
                <button className={BTN2} onClick={() => setEditingAttrs(!editingAttrs)}>{editingAttrs ? "Cerrar" : "Editar"}</button>
              </span>
            }>
              <p className="mb-3 text-xs text-slate-500">{e.attributes_form.source_ref}</p>
              <RecordFields spec={e.attributes_form.form_spec} data={attrs} onChange={setAttrs} disabled={!editingAttrs} idPrefix="attr" />
              {editingAttrs && <button className={`${BTN} mt-3`} disabled={saveAttrs.isPending} onClick={() => saveAttrs.mutate()}>Guardar ficha técnica</button>}
            </Section>
          )}

          <Section title="Historial de instalaciones">
            {e.installation_history.length === 0 ? <EmptyState message="Este equipo nunca se ha instalado." /> : (
              <table className="w-full">
                <thead><tr><th className={TH}>Frontera</th><th className={TH}>Posición</th><th className={TH}>Instalado</th><th className={TH}>Retirado</th><th className={TH}>Motivo</th></tr></thead>
                <tbody>
                  {e.installation_history.map((h) => (
                    <tr key={h.installation_id} className="border-t border-slate-100">
                      <td className={TD}><Link className="text-indigo-700 hover:underline" to={`/energy/points/${h.point_id}`}>{h.point_code}</Link> <span className="text-xs text-slate-500">{h.point_name}</span></td>
                      <td className={TD}>{h.position_label}</td>
                      <td className={TD}>{formatDay(h.installed_on)}</td>
                      <td className={TD}>{formatDay(h.removed_on)}</td>
                      <td className={TD}>{h.removal_reason}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </Section>
        </div>
      )}
    </AppShell>
  );
}
