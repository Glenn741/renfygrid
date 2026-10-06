import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { getManualMeters, getOperationsCatalog, getSamplingPoints, type ManualMeter, type OperationsCatalog, type RuleBand, type SamplingPoint } from "../api";
import {
  enqueue,
  listOutbox,
  loadSnapshot,
  pruneSynced,
  removeOutboxItem,
  retryOutboxItem,
  saveSnapshot,
  syncOutbox,
  tokenTenantId,
  type LogPayload,
  type MeterPayload,
  type OutboxItem,
  type ReadingPayload,
} from "../offline/outbox";
import { Icon } from "../components/Icon";
import { appLocale } from "../catalog";

// App del operador (Track D, D1.3): pensada para el telefono y para trabajar
// SIN CONEXION. Lo registrado se guarda primero en el dispositivo y se envia
// al volver la senal (src/offline/outbox.ts). El catalogo (tipos de punto,
// rutina, tramos de interpretacion) y los puntos de la junta se usan desde la
// ultima foto guardada con conexion. La interpretacion que se ve es una vista
// previa con los mismos tramos del paquete; la que vale es la del servidor.

interface Snapshot {
  catalog: OperationsCatalog;
  points: SamplingPoint[];
  /** Medidores con sus canales y ultima lectura (lectura manual, D1.4a). */
  meters?: ManualMeter[];
}

const APPEARANCE: Record<"clear" | "turbid" | "colored", string> = { clear: "Clara", turbid: "Turbia", colored: "Con color" };
const SEVERITY_STYLE: Record<string, string> = {
  ok: "bg-emerald-50 text-emerald-800 border-emerald-200",
  alert: "bg-amber-50 text-amber-900 border-amber-200",
  critical: "bg-red-50 text-red-800 border-red-200",
};

function previewBand(bands: RuleBand[] | null | undefined, value: number): RuleBand | null {
  if (!bands || Number.isNaN(value)) return null;
  for (const b of bands) {
    if (b.upper === null) return b;
    if (b.upper_inclusive === false ? value < b.upper : value <= b.upper) return b;
  }
  return null;
}

function useOnline(): boolean {
  const [online, setOnline] = useState(() => navigator.onLine);
  useEffect(() => {
    const on = () => setOnline(true);
    const off = () => setOnline(false);
    window.addEventListener("online", on);
    window.addEventListener("offline", off);
    return () => { window.removeEventListener("online", on); window.removeEventListener("offline", off); };
  }, []);
  return online;
}

function BigButton({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button onClick={onClick} aria-pressed={active}
      className={`min-h-12 rounded-xl border-2 px-3 py-2 text-left text-base font-semibold ${active ? "border-indigo-600 bg-indigo-600 text-white" : "border-slate-300 bg-white text-slate-800"}`}>
      {children}
    </button>
  );
}

function MeasureForm({ snap, onSaved }: { snap: Snapshot; onSaved: (label: string) => void; }) {
  const tenantId = tokenTenantId()!;
  const [pointId, setPointId] = useState("");
  const [paramCode, setParamCode] = useState("free_chlorine");
  const [value, setValue] = useState("");
  const [action, setAction] = useState("");
  const param = snap.catalog.parameters.find((p) => p.code === paramCode);
  const band = value === "" ? null : previewBand(param?.bands, Number(value));
  const point = snap.points.find((p) => p.point_id === pointId);

  const save = async () => {
    const payload: ReadingPayload = {
      parameter_code: paramCode, value: Number(value), sampling_point_id: pointId || null,
      action_taken: action.trim() || null, measured_at: new Date().toISOString(),
    };
    const label = `${param?.label ?? paramCode} ${value} ${param?.unit ?? ""} · ${point?.name ?? "sin punto"}${band ? ` · ${band.label}` : ""}`;
    await enqueue(tenantId, "reading", payload, label);
    setValue("");
    setAction("");
    onSaved(label);
  };

  return (
    <div className="space-y-4">
      <div>
        <p className="mb-2 text-sm font-semibold text-slate-700">¿Dónde mide?</p>
        <div className="grid gap-2">
          {snap.points.map((p) => (
            <BigButton key={p.point_id} active={pointId === p.point_id} onClick={() => setPointId(p.point_id)}>
              {p.name}<span className="block text-xs font-normal opacity-80">{p.kind_label}</span>
            </BigButton>
          ))}
          {snap.points.length === 0 && <p className="text-sm text-amber-800">Todavía no hay puntos de medición. Créelos en el Portal (Operación diaria → Puntos).</p>}
        </div>
      </div>
      <div className="flex gap-2">
        {snap.catalog.parameters.map((p) => (
          <BigButton key={p.code} active={paramCode === p.code} onClick={() => setParamCode(p.code)}>{p.label}</BigButton>
        ))}
      </div>
      <label className="block text-sm font-semibold text-slate-700">Resultado {param?.unit && `(${param.unit})`}
        <input type="number" inputMode="decimal" step="0.01" min={0} className="mt-1 w-full rounded-xl border-2 border-slate-300 px-4 py-3 text-2xl tabular-nums" value={value} onChange={(e) => setValue(e.target.value)} />
      </label>
      {band && (
        <div className={`rounded-xl border p-3 text-sm ${SEVERITY_STYLE[band.severity]}`}>
          <strong className="text-base">{band.label}.</strong> {band.action}
        </div>
      )}
      <input aria-label="Acción tomada" className="w-full rounded-xl border-2 border-slate-300 px-4 py-3 text-base" placeholder="Acción tomada (si corresponde)" value={action} onChange={(e) => setAction(e.target.value)} />
      <button onClick={save} disabled={!pointId || value === ""} className="w-full rounded-xl bg-indigo-600 py-4 text-lg font-bold text-white disabled:opacity-40">
        Guardar medición
      </button>
    </div>
  );
}

function LogForm({ snap, todayReadings, onSaved }: { snap: Snapshot; todayReadings: OutboxItem[]; onSaved: (label: string) => void }) {
  const tenantId = tokenTenantId()!;
  const [moment, setMoment] = useState("");
  const [tank, setTank] = useState("");
  const [applied, setApplied] = useState("");
  const [unit, setUnit] = useState<"g" | "ml">("g");
  const [readingCid, setReadingCid] = useState("");
  const [appearance, setAppearance] = useState<"clear" | "turbid" | "colored" | "">("");
  const [status, setStatus] = useState<"good" | "alert">("good");
  const [notes, setNotes] = useState("");
  const m = snap.catalog.moments.find((x) => x.code === moment);
  const chlorine = todayReadings.filter((i) => (i.payload as ReadingPayload).parameter_code === "free_chlorine");
  const linked = chlorine.find((i) => i.client_id === readingCid);
  const linkedBand = linked ? previewBand(snap.catalog.parameters.find((p) => p.code === "free_chlorine")?.bands, (linked.payload as ReadingPayload).value) : null;
  // Misma regla que el servidor: nunca "Bueno" con cloro fuera de rango o agua no clara.
  const forcedAlert = (linkedBand && linkedBand.severity !== "ok") || appearance === "turbid" || appearance === "colored";

  const save = async () => {
    const payload: LogPayload = {
      moment_code: moment || null, tank_level_pct: tank ? Number(tank) : null,
      chlorine_applied: applied ? Number(applied) : null, chlorine_applied_unit: applied ? unit : null,
      reading_client_id: readingCid || null, appearance: appearance || null,
      status: forcedAlert ? "alert" : status, notes: notes.trim() || null, logged_at: new Date().toISOString(),
    };
    const label = `Bitácora · ${m?.label ?? "sin momento"}${forcedAlert || status === "alert" ? " · Alerta" : " · Bueno"}`;
    await enqueue(tenantId, "log", payload, label);
    setTank(""); setApplied(""); setReadingCid(""); setAppearance(""); setStatus("good"); setNotes("");
    onSaved(label);
  };

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-2">
        {snap.catalog.moments.map((x) => (
          <BigButton key={`${x.pack_id}-${x.code}`} active={moment === x.code} onClick={() => setMoment(x.code)}>{x.label}</BigButton>
        ))}
      </div>
      {m && <p className="rounded-xl bg-slate-100 p-3 text-sm text-slate-700"><strong>Revisar:</strong> {m.check_text}</p>}
      <div className="grid grid-cols-2 gap-3">
        <label className="text-sm font-semibold text-slate-700">Nivel tanque (%)
          <input type="number" inputMode="numeric" min={0} max={100} className="mt-1 w-full rounded-xl border-2 border-slate-300 px-3 py-3 text-xl" value={tank} onChange={(e) => setTank(e.target.value)} />
        </label>
        <label className="text-sm font-semibold text-slate-700">Cloro aplicado
          <span className="mt-1 flex gap-1">
            <input type="number" inputMode="decimal" min={0} className="w-full rounded-xl border-2 border-slate-300 px-3 py-3 text-xl" value={applied} onChange={(e) => setApplied(e.target.value)} />
            <select aria-label="Unidad" className="rounded-xl border-2 border-slate-300 px-2" value={unit} onChange={(e) => setUnit(e.target.value as "g" | "ml")}>
              <option value="g">g</option><option value="ml">ml</option>
            </select>
          </span>
        </label>
      </div>
      {chlorine.length > 0 && (
        <label className="block text-sm font-semibold text-slate-700">Cloro residual medido hoy
          <select className="mt-1 w-full rounded-xl border-2 border-slate-300 px-3 py-3 text-base" value={readingCid} onChange={(e) => setReadingCid(e.target.value)}>
            <option value="">— sin medición —</option>
            {chlorine.map((i) => <option key={i.client_id} value={i.client_id}>{new Date(i.created_at).toLocaleTimeString(appLocale(), { hour: "2-digit", minute: "2-digit" })} · {i.label}</option>)}
          </select>
        </label>
      )}
      <div>
        <p className="mb-2 text-sm font-semibold text-slate-700">Aspecto del agua</p>
        <div className="grid grid-cols-3 gap-2">
          {(Object.keys(APPEARANCE) as (keyof typeof APPEARANCE)[]).map((a) => (
            <BigButton key={a} active={appearance === a} onClick={() => setAppearance(appearance === a ? "" : a)}>{APPEARANCE[a]}</BigButton>
          ))}
        </div>
      </div>
      <div>
        <p className="mb-2 text-sm font-semibold text-slate-700">Estado</p>
        <div className="grid grid-cols-2 gap-2">
          <BigButton active={!forcedAlert && status === "good"} onClick={() => setStatus("good")}>Bueno</BigButton>
          <BigButton active={forcedAlert || status === "alert"} onClick={() => setStatus("alert")}>Alerta</BigButton>
        </div>
        {forcedAlert && <p className="mt-1 text-xs text-amber-800">Queda en Alerta: el cloro está fuera de rango o el agua no se ve clara.</p>}
      </div>
      <input aria-label="Novedades" className="w-full rounded-xl border-2 border-slate-300 px-4 py-3 text-base" placeholder="Novedades, pendientes" value={notes} onChange={(e) => setNotes(e.target.value)} />
      <button onClick={save} disabled={!moment} className="w-full rounded-xl bg-indigo-600 py-4 text-lg font-bold text-white disabled:opacity-40">
        Guardar toma
      </button>
    </div>
  );
}

function MeterForm({ snap, onSaved }: { snap: Snapshot; onSaved: (label: string) => void }) {
  const tenantId = tokenTenantId()!;
  const [search, setSearch] = useState("");
  const [meterId, setMeterId] = useState("");
  const [channel, setChannel] = useState("");
  const [value, setValue] = useState("");
  const [lowerOk, setLowerOk] = useState(false);
  const [notes, setNotes] = useState("");
  const meters = snap.meters ?? [];
  const q = search.trim().toLowerCase();
  const matches = q ? meters.filter((m) => m.account_number.toLowerCase().includes(q) || m.serial_number.toLowerCase().includes(q)).slice(0, 8) : meters.filter((m) => m.meter_type === "macro");
  const meter = meters.find((m) => m.meter_id === meterId);
  const channels = meter?.channels ?? [];
  const ch = channels.find((c) => c.channel === channel) ?? (channels.length === 1 ? channels[0] : undefined);
  const last = ch?.last_value ?? null;
  const goesDown = value !== "" && last !== null && Number(value) < last;

  const pick = (m: ManualMeter) => {
    setMeterId(m.meter_id);
    setChannel(m.channels?.length === 1 ? m.channels[0].channel : "");
    setValue("");
    setLowerOk(false);
  };

  const save = async () => {
    if (!meter || !ch) return;
    const payload: MeterPayload = {
      meter_id: meter.meter_id, channel: ch.channel, value: Number(value), read_at: new Date().toISOString(),
      lower_confirmed: goesDown && lowerOk, notes: notes.trim() || null,
    };
    const label = `Medidor ${meter.account_number} (${meter.meter_type}) · ${value}${last !== null && !goesDown ? ` · ${(Number(value) - last).toFixed(2)} desde la anterior` : ""}`;
    await enqueue(tenantId, "meter", payload, label);
    // La foto se actualiza con lo leido, para que la proxima lectura compare contra esta.
    ch.last_value = Number(value);
    ch.last_at = payload.read_at;
    setValue(""); setNotes(""); setLowerOk(false); setMeterId(""); setSearch("");
    onSaved(label);
  };

  if (meters.length === 0) return <p className="text-sm text-slate-600">No hay medidores registrados para lectura manual.</p>;

  return (
    <div className="space-y-4">
      {!meter && (
        <>
          <input aria-label="Buscar medidor" className="w-full rounded-xl border-2 border-slate-300 px-4 py-3 text-base" placeholder="Cuenta o serie del medidor" value={search} onChange={(e) => setSearch(e.target.value)} />
          {!q && <p className="text-xs text-slate-500">Macromedidores (escriba para buscar un micromedidor):</p>}
          <div className="grid gap-2">
            {matches.map((m) => (
              <BigButton key={m.meter_id} active={false} onClick={() => pick(m)}>
                {m.account_number}<span className="block text-xs font-normal opacity-80">{m.meter_type === "macro" ? "Macromedidor" : "Micromedidor"} · {m.serial_number}{m.zone_name ? ` · ${m.zone_name}` : ""}</span>
              </BigButton>
            ))}
            {q && matches.length === 0 && <p className="text-sm text-slate-500">Ningún medidor coincide.</p>}
          </div>
        </>
      )}
      {meter && (
        <>
          <div className="rounded-xl border border-slate-200 bg-white p-3">
            <p className="text-base font-semibold text-slate-900">{meter.account_number} · {meter.meter_type === "macro" ? "Macromedidor" : "Micromedidor"}</p>
            <p className="text-xs text-slate-500">{meter.brand} · serie {meter.serial_number}{meter.zone_name ? ` · ${meter.zone_name}` : ""}</p>
            <button onClick={() => setMeterId("")} className="mt-1 text-xs font-semibold text-indigo-700">Cambiar de medidor</button>
          </div>
          {channels.length > 1 && (
            <div className="grid gap-2">
              {channels.map((c) => <BigButton key={c.channel} active={channel === c.channel} onClick={() => setChannel(c.channel)}>{c.channel}</BigButton>)}
            </div>
          )}
          {channels.length === 0 && <p className="text-sm text-amber-800">Este medidor no tiene un canal conocido; regístrelo primero en el Portal.</p>}
          {ch && (
            <p className="text-sm text-slate-600">
              Lectura anterior: {last !== null ? <strong>{last.toLocaleString(appLocale())}</strong> : "ninguna"}
              {ch.last_at && ` · ${new Date(ch.last_at).toLocaleDateString(appLocale(), { day: "numeric", month: "short" })}`}
            </p>
          )}
          <label className="block text-sm font-semibold text-slate-700">Lectura del registro (m³)
            <input type="number" inputMode="decimal" step="any" min={0} className="mt-1 w-full rounded-xl border-2 border-slate-300 px-4 py-3 text-2xl tabular-nums" value={value} onChange={(e) => setValue(e.target.value)} />
          </label>
          {value !== "" && last !== null && !goesDown && <p className="text-sm text-emerald-800">Consumo desde la anterior: {(Number(value) - last).toFixed(2)} m³</p>}
          {goesDown && (
            <label className="flex items-start gap-2 rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
              <input type="checkbox" className="mt-1" checked={lowerOk} onChange={(e) => setLowerOk(e.target.checked)} />
              La lectura es menor que la anterior. Confirmo que el medidor se cambió o se reinició (si no, revise el número).
            </label>
          )}
          <input aria-label="Observaciones" className="w-full rounded-xl border-2 border-slate-300 px-4 py-3 text-base" placeholder="Observaciones (medidor dañado, sin acceso…)" value={notes} onChange={(e) => setNotes(e.target.value)} />
          <button onClick={save} disabled={!ch || value === "" || (goesDown && !lowerOk)} className="w-full rounded-xl bg-indigo-600 py-4 text-lg font-bold text-white disabled:opacity-40">
            Guardar lectura
          </button>
        </>
      )}
    </div>
  );
}

const STATUS_PILL: Record<OutboxItem["status"], { label: string; cls: string }> = {
  pending: { label: "Por enviar", cls: "bg-amber-100 text-amber-900" },
  synced: { label: "Enviado", cls: "bg-emerald-100 text-emerald-800" },
  failed: { label: "Rechazado", cls: "bg-red-100 text-red-800" },
};

export function OperatorPage() {
  const tenantId = tokenTenantId();
  const online = useOnline();
  const [snap, setSnap] = useState<{ saved_at: string; data: Snapshot } | null>(() => (tenantId ? loadSnapshot<Snapshot>(tenantId) : null));
  const [tab, setTab] = useState<"measure" | "log" | "meter" | "outbox">("measure");
  const [items, setItems] = useState<OutboxItem[]>([]);
  const [message, setMessage] = useState<string | null>(null);
  const [syncing, setSyncing] = useState(false);

  const refreshItems = useCallback(async () => {
    if (tenantId) setItems(await listOutbox(tenantId));
  }, [tenantId]);

  const sync = useCallback(async () => {
    if (!tenantId || syncing) return;
    setSyncing(true);
    const report = await syncOutbox(tenantId);
    setSyncing(false);
    await refreshItems();
    if (report.stopped === "session") setMessage("La sesión venció: ingrese de nuevo para enviar lo pendiente. Nada se perdió.");
    else if (report.sent || report.failed) {
      setMessage(`${report.sent} enviado${report.sent === 1 ? "" : "s"}${report.failed ? ` · ${report.failed} rechazado${report.failed === 1 ? "" : "s"} (ver Pendientes)` : ""}.`);
    }
  }, [tenantId, syncing, refreshItems]);

  // Foto del catalogo y los puntos cada vez que hay conexion.
  useEffect(() => {
    if (!tenantId || !online) return;
    Promise.all([getOperationsCatalog(), getSamplingPoints(), getManualMeters({ limit: 1000 })])
      .then(([catalog, points, meters]) => {
        const data = { catalog, points, meters };
        saveSnapshot(tenantId, data);
        setSnap({ saved_at: new Date().toISOString(), data });
      })
      .catch(() => undefined);
  }, [tenantId, online]);

  useEffect(() => {
    if (!tenantId) return;
    const start = new Date();
    start.setHours(0, 0, 0, 0);
    pruneSynced(tenantId, start).then(refreshItems);
  }, [tenantId, refreshItems]);

  // Envia solo al volver la senal (y al abrir con senal).
  useEffect(() => {
    if (online) void sync();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [online]);

  const todayReadings = useMemo(() => {
    const start = new Date();
    start.setHours(0, 0, 0, 0);
    return items.filter((i) => i.kind === "reading" && new Date(i.created_at) >= start);
  }, [items]);
  const pending = items.filter((i) => i.status !== "synced").length;

  const onSaved = async (label: string) => {
    await refreshItems();
    setMessage(online ? `Guardado: ${label}. Enviando…` : `Guardado en el teléfono: ${label}. Se enviará cuando vuelva la señal.`);
    if (online) void sync();
  };

  if (!tenantId) return null;

  return (
    <div className="mx-auto min-h-screen max-w-lg bg-slate-50 pb-10">
      <header className="sticky top-0 z-10 border-b border-slate-200 bg-white px-4 py-3">
        <div className="flex items-center justify-between gap-2">
          <h1 className="text-lg font-bold text-slate-900">Operación del día</h1>
          <span className={`rounded-full px-2.5 py-1 text-xs font-bold ${online ? "bg-emerald-100 text-emerald-800" : "bg-slate-200 text-slate-700"}`}>
            {online ? "Con conexión" : "Sin conexión"}
          </span>
        </div>
        <div className="mt-2 flex items-center justify-between gap-2 text-sm">
          <span className={pending ? "font-semibold text-amber-800" : "text-slate-500"}>{pending ? `${pending} por enviar` : "Todo enviado"}</span>
          <div className="flex gap-3">
            <button onClick={() => void sync()} disabled={!online || syncing || !pending} className="font-semibold text-indigo-700 disabled:text-slate-400">
              {syncing ? "Enviando…" : "Enviar ahora"}
            </button>
            <Link to="/operations" className="text-slate-600 underline">Portal</Link>
          </div>
        </div>
      </header>

      {message && (
        <div role="status" className="mx-4 mt-3 flex items-start justify-between gap-2 rounded-xl border border-indigo-200 bg-indigo-50 p-3 text-sm text-indigo-900">
          <span>{message}</span>
          <button onClick={() => setMessage(null)} aria-label="Cerrar aviso"><Icon name="close" className="h-4 w-4" /></button>
        </div>
      )}

      <nav className="mx-4 mt-3 grid grid-cols-4 gap-2" aria-label="Secciones">
        {([["measure", "Cloro"], ["log", "Bitácora"], ["meter", "Medidor"], ["outbox", `Envíos${pending ? ` (${pending})` : ""}`]] as const).map(([key, label]) => (
          <button key={key} onClick={() => setTab(key)} aria-current={tab === key ? "page" : undefined}
            className={`rounded-xl py-3 text-sm font-bold ${tab === key ? "bg-slate-900 text-white" : "bg-white text-slate-700 border border-slate-300"}`}>
            {label}
          </button>
        ))}
      </nav>

      <main className="mx-4 mt-4">
        {!snap && tab !== "outbox" && (
          <p className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
            Abra esta pantalla una vez con conexión para descargar los puntos de medición y la rutina. Después funciona sin señal.
          </p>
        )}
        {snap && tab === "measure" && <MeasureForm snap={snap.data} onSaved={onSaved} />}
        {snap && tab === "log" && <LogForm snap={snap.data} todayReadings={todayReadings} onSaved={onSaved} />}
        {snap && tab === "meter" && <MeterForm snap={snap.data} onSaved={(label) => { if (tenantId) saveSnapshot(tenantId, snap.data); void onSaved(label); }} />}
        {tab === "outbox" && (
          <ul className="space-y-2">
            {items.length === 0 && <li className="text-sm text-slate-500">Nada registrado hoy en este teléfono.</li>}
            {items.map((i) => (
              <li key={i.client_id} className="rounded-xl border border-slate-200 bg-white p-3 text-sm">
                <div className="flex items-start justify-between gap-2">
                  <span className="text-slate-800">{i.label}</span>
                  <span className={`shrink-0 rounded-full px-2 py-0.5 text-xs font-bold ${STATUS_PILL[i.status].cls}`}>{STATUS_PILL[i.status].label}</span>
                </div>
                <p className="mt-1 text-xs text-slate-500">
                  {new Date(i.created_at).toLocaleString(appLocale(), { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" })}
                  {i.server_note && ` · ${i.server_note}`}
                </p>
                {i.error && (
                  <div className="mt-2 flex flex-wrap items-center gap-3">
                    <span className="text-xs text-red-700">{i.error}</span>
                    <button onClick={async () => { await retryOutboxItem(i); await refreshItems(); }} className="text-xs font-semibold text-indigo-700">Reintentar</button>
                    <button onClick={async () => { if (confirm("¿Descartar este registro? No se enviará.")) { await removeOutboxItem(i.client_id); await refreshItems(); } }} className="text-xs font-semibold text-red-700">Descartar</button>
                  </div>
                )}
              </li>
            ))}
          </ul>
        )}
        {snap && <p className="mt-6 text-center text-[11px] text-slate-400">Datos actualizados {new Date(snap.saved_at).toLocaleString(appLocale(), { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" })}</p>}
      </main>
    </div>
  );
}
