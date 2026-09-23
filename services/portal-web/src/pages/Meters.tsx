import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ApiError,
  getConsumptionDistribution,
  getExceptionRateByBrand,
  getFleetSummary,
  getGateways,
  getHesEventSummary,
  getIngestionMetrics,
  getMeterEvents,
  getMetersGeojson,
  getRetryQueue,
  getSectorSummary,
  readMeterNow,
  type MeterEvent,
} from "../api";
import { StagePage, EmptyState } from "../components/StagePage";
import { SectionNav } from "../components/SectionNav";
import { NetworkMap } from "../components/NetworkMap";

// Pulido de usabilidad (2026-09-14): 5 secciones reales apiladas (flota,
// concentradores, cola de reintentos, eventos/alarmas, medidores) sin
// forma de saltar entre ellas -- mismo patron de barra de secciones que
// el resto del portal (ver Configuration.tsx).
//
// Mapa de medidores + distribucion estadistica + sectores hidraulicos
// (2026-09-15, a pedido explicito del usuario): un medidor puede ser
// MICRO (cliente/inmueble individual) o MACRO (medidor de bloque en la
// entrada de un sector hidraulico/DMA, junto a la valvula reguladora de
// presion -- mide el inflow TOTAL, la diferencia contra el consumo micro
// sumado es el NRW real de ese sector). Grounded en el estandar real de
// DMA/smart metering (KROHNE, McCrometer -- ver docs/05-ejecucion.md).
const SECTIONS = [
  { id: "map", label: "Mapa de medidores" },
  { id: "distribution", label: "Distribución estadística" },
  { id: "fleet", label: "Flota" },
  { id: "gateways", label: "Concentradores" },
  { id: "retry-queue", label: "Cola de reintentos" },
  { id: "events", label: "Eventos y alarmas" },
  { id: "meters-list", label: "Medidores" },
];

const METER_TYPE_LABEL: Record<string, string> = { micro: "Micro (cliente)", macro: "Macro (sector)" };
const METER_TYPE_COLOR: Record<string, string> = { micro: "#0ea5e9", macro: "#7c3aed" };
const STALE_COLOR = { online: "#10b981", offline: "#ef4444", unknown: "#94a3b8" };

type MapLayer = "status" | "type" | "brand";

const BRAND_PALETTE = ["#0ea5e9", "#f59e0b", "#10b981", "#ef4444", "#7c3aed", "#64748b", "#ec4899", "#14b8a6"];
function brandColor(brand: string | null): string {
  if (!brand) return "#94a3b8";
  let hash = 0;
  for (let i = 0; i < brand.length; i++) hash = (hash * 31 + brand.charCodeAt(i)) % BRAND_PALETTE.length;
  return BRAND_PALETTE[hash];
}

function MetersMapSection() {
  const [layer, setLayer] = useState<MapLayer>("status");
  const { data: geojson, isLoading } = useQuery({ queryKey: ["meters-geojson"], queryFn: getMetersGeojson, refetchInterval: 30_000 });

  const colorFor = (p: Record<string, unknown>): string => {
    if (layer === "type") return METER_TYPE_COLOR[p.meter_type as string] ?? "#94a3b8";
    if (layer === "brand") return brandColor(p.brand as string | null);
    // layer === "status"
    if (p.is_stale === null || p.is_stale === undefined) return STALE_COLOR.unknown;
    return p.is_stale ? STALE_COLOR.offline : STALE_COLOR.online;
  };

  return (
    <>
      <div className="mb-2 flex items-center justify-between flex-wrap gap-2">
        <h2 className="text-sm font-semibold text-slate-500 uppercase tracking-wide">Mapa de medidores</h2>
        <div className="flex gap-2">
          {([["status", "Estado"], ["type", "Tipo (micro/macro)"], ["brand", "Marca"]] as [MapLayer, string][]).map(([value, label]) => (
            <button
              key={value}
              onClick={() => setLayer(value)}
              className={`rounded-full px-3 py-1 text-xs font-semibold border ${layer === value ? "bg-indigo-600 text-white border-indigo-600" : "bg-white text-slate-600 border-slate-200 hover:border-slate-300"}`}
            >
              {label}
            </button>
          ))}
        </div>
      </div>
      {isLoading && <p className="text-sm text-slate-500 mb-2">Cargando...</p>}
      <NetworkMap
        geojson={geojson}
        height={360}
        emptyMessage="Ningún medidor tiene coordenadas cargadas todavía."
        pointColor={colorFor}
        pointRadius={(p) => (p.meter_type === "macro" ? 11 : 6)}
        popupHtml={(p) => {
          const statusText = p.is_stale === null || p.is_stale === undefined ? "sin umbral configurado" : p.is_stale ? "caído" : "en línea";
          return `<div style="font-size:12px"><strong>${p.account_number}</strong> (${METER_TYPE_LABEL[p.meter_type as string] ?? p.meter_type})<br/>` +
            `${p.brand ?? "—"} ${p.model ?? ""}<br/>Sector: ${p.zone_name ?? "sin asignar"}<br/>Estado: ${statusText}` +
            `${(p.invalid_count as number) > 0 ? `<br/><span style="color:#b45309">${p.invalid_count} excepción(es) pendiente(s)</span>` : ""}</div>`;
        }}
      />
      <div className="mt-2 flex flex-wrap gap-4 text-xs text-slate-500">
        {layer === "status" && (
          <>
            <span><span className="inline-block w-2.5 h-2.5 rounded-full mr-1" style={{ background: STALE_COLOR.online }} />En línea</span>
            <span><span className="inline-block w-2.5 h-2.5 rounded-full mr-1" style={{ background: STALE_COLOR.offline }} />Caído</span>
            <span><span className="inline-block w-2.5 h-2.5 rounded-full mr-1" style={{ background: STALE_COLOR.unknown }} />Umbral sin configurar</span>
          </>
        )}
        {layer === "type" && (
          <>
            <span><span className="inline-block w-2.5 h-2.5 rounded-full mr-1" style={{ background: METER_TYPE_COLOR.micro }} />Micro (cliente)</span>
            <span><span className="inline-block w-3 h-3 rounded-full mr-1" style={{ background: METER_TYPE_COLOR.macro }} />Macro (sector, círculo más grande)</span>
          </>
        )}
        {layer === "brand" && <span>Color por marca — ver el detalle al hacer clic en cada punto.</span>}
      </div>
    </>
  );
}

function Histogram({ buckets, max }: { buckets: { label: string; count: number }[]; max: number }) {
  return (
    <div className="flex items-end gap-2 h-32">
      {buckets.map((b) => (
        <div key={b.label} className="flex-1 flex flex-col items-center gap-1" title={`${b.label}: ${b.count} medidor(es)`}>
          <div className="w-full flex items-end h-24">
            <div className="w-full bg-indigo-400 rounded-t" style={{ height: `${max > 0 ? (b.count / max) * 100 : 0}%`, minHeight: b.count > 0 ? 3 : 0 }} />
          </div>
          <span className="text-[9px] text-slate-400 text-center leading-tight">{b.label}</span>
        </div>
      ))}
    </div>
  );
}

function DistributionSection() {
  const { data: dist } = useQuery({ queryKey: ["consumption-distribution"], queryFn: getConsumptionDistribution, refetchInterval: 60_000 });
  const { data: byBrand } = useQuery({ queryKey: ["exception-rate-by-brand"], queryFn: getExceptionRateByBrand, refetchInterval: 60_000 });
  const { data: sectors } = useQuery({ queryKey: ["sector-summary"], queryFn: getSectorSummary, refetchInterval: 60_000 });

  const maxBucket = Math.max(1, ...(dist?.buckets.map((b) => b.count) ?? [0]));
  const maxExceptionRate = Math.max(1, ...((byBrand ?? []).map((b) => b.exception_rate_pct ?? 0)));

  return (
    <>
      <h2 className="text-sm font-semibold text-slate-500 uppercase tracking-wide mb-2">Distribución estadística de la medición</h2>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-4">
        <div className="rounded-xl border border-slate-200 bg-white p-4">
          <div className="flex items-center justify-between mb-2">
            <div className="text-xs font-medium text-slate-500">Consumo por medidor micro — últimos {dist?.window_days ?? 30} días</div>
            {dist && <div className="text-xs text-slate-400">prom. {dist.avg_m3 ?? "—"} m³ ({dist.meters_with_data} medidores)</div>}
          </div>
          {dist && dist.buckets.length > 0 ? <Histogram buckets={dist.buckets} max={maxBucket} /> : <p className="text-sm text-slate-400 h-32 flex items-center">Sin datos suficientes todavía.</p>}
        </div>
        <div className="rounded-xl border border-slate-200 bg-white p-4">
          <div className="text-xs font-medium text-slate-500 mb-2">Tasa de excepción real por marca</div>
          {byBrand && byBrand.length > 0 ? (
            <div className="space-y-2">
              {byBrand.map((b) => (
                <div key={b.brand}>
                  <div className="flex justify-between text-xs text-slate-600 mb-0.5">
                    <span>{b.brand}</span>
                    <span className="tabular-nums font-semibold">{b.exception_rate_pct === null ? "—" : `${b.exception_rate_pct}%`}</span>
                  </div>
                  <div className="h-1.5 rounded-full bg-slate-100 overflow-hidden">
                    <div className="h-full bg-amber-500" style={{ width: `${((b.exception_rate_pct ?? 0) / maxExceptionRate) * 100}%` }} />
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-slate-400 h-32 flex items-center">Sin datos todavía.</p>
          )}
        </div>
      </div>

      <div className="text-xs font-medium text-slate-500 mb-2">Sectores hidráulicos — macro vs. micro medición</div>
      {sectors && sectors.filter((s) => s.micro_count > 0 || s.macro_meter_id).length === 0 && (
        <EmptyState message="Sin sectores hidráulicos con medidores clasificados todavía." />
      )}
      {sectors && sectors.filter((s) => s.micro_count > 0 || s.macro_meter_id).length > 0 && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {sectors.filter((s) => s.micro_count > 0 || s.macro_meter_id).map((s) => (
            <div key={s.zone_id} className="rounded-xl border border-slate-200 bg-white p-4">
              <div className="text-sm font-bold text-slate-900 mb-1">{s.zone_name}</div>
              <div className="text-xs text-slate-500 mb-2">{s.micro_count} micro-medidores{s.macro_meter_id ? " · 1 macro-medidor" : " · sin macro-medidor"}</div>
              {s.nrw_pct !== null ? (
                <>
                  <div className={`text-2xl font-bold ${s.nrw_pct > 30 ? "text-red-700" : s.nrw_pct > 20 ? "text-amber-700" : "text-emerald-700"}`}>{s.nrw_pct}%</div>
                  <div className="text-xs text-slate-500">NRW operativo ({s.window})</div>
                  <div className="mt-2 text-xs text-slate-500">Macro: {s.macro_volume_m3} m³ · Micro: {s.micro_total_m3} m³</div>
                </>
              ) : (
                <div className="text-sm text-slate-400">Sin datos suficientes para NRW todavía.</div>
              )}
            </div>
          ))}
        </div>
      )}
    </>
  );
}

// HES / Ingesta (Sprint C7/C8, `docs/06-benchmark-e2e-y-brechas.md` G4/G5,
// mas Sprint C11-4): el benchmark E2E encontro que faltaban flota por
// marca/modelo (G4) y capa de agregacion de concentradores (G5). Despues
// el usuario pidio el mismo ejercicio de mercado que se hizo con VEE --
// lo que aparece consistente en HES de referencia (Genus/Kimbal/tblocks,
// ScienceDirect "Data Concentrator", Eaton Brightlayer -- fuentes en
// docs/05-ejecucion.md Sprint C11-4) es "operational dashboards,
// communication statistics, meter reachability reports, and alarm
// management". Eso ya estaba CONSTRUIDO desde F05 (alarmas reales via
// push DLMS) y F08/F09 (cola de reintentos + auditoria de comunicacion)
// pero nunca se via en el Portal -- las 2 secciones nuevas (cola de
// reintentos, eventos/alarmas) muestran esas mismas filas reales, nada
// inventado.

function ratePillClass(pct: number | null): string {
  if (pct === null) return "bg-slate-50 text-slate-500";
  if (pct >= 90) return "bg-emerald-50 text-emerald-700";
  if (pct >= 60) return "bg-amber-50 text-amber-700";
  return "bg-red-50 text-red-600";
}

function rateTextClass(pct: number | null): string {
  if (pct === null) return "text-slate-900";
  if (pct >= 90) return "text-emerald-700";
  if (pct >= 60) return "text-amber-700";
  return "text-red-700";
}

const SEVERITY_CLASS: Record<string, string> = {
  critical: "bg-red-50 text-red-700",
  warning: "bg-amber-50 text-amber-700",
  info: "bg-slate-50 text-slate-500",
};

const EVENT_TYPE_LABEL: Record<string, string> = {
  meter_alarm: "Alarma del medidor",
  communication_success: "Comunicación exitosa",
  communication_failure: "Falla de comunicación",
};

function eventTypeLabel(type: string): string {
  return EVENT_TYPE_LABEL[type] ?? type;
}

function relativeFromNow(iso: string): string {
  const diffMs = new Date(iso).getTime() - Date.now();
  const diffMin = Math.round(diffMs / 60000);
  if (diffMin <= 0) return "ya venció";
  if (diffMin < 60) return `en ${diffMin} min`;
  const diffH = Math.round(diffMin / 60);
  return `en ${diffH}h`;
}

function eventDetailText(event: MeterEvent): string {
  const detail = event.detail ?? {};
  if (event.type === "meter_alarm") {
    return `código ${detail.event_code ?? "?"}`;
  }
  if (detail.operation && detail.error) return `${detail.operation}: ${detail.error}`;
  if (detail.operation) return String(detail.operation);
  return "—";
}

export function MetersPage() {
  const queryClient = useQueryClient();

  const { data: eventSummary } = useQuery({
    queryKey: ["hes-event-summary"],
    queryFn: getHesEventSummary,
    refetchInterval: 30_000,
  });

  const { data: fleet, isLoading: fleetLoading } = useQuery({
    queryKey: ["fleet-summary"],
    queryFn: getFleetSummary,
    refetchInterval: 30_000,
  });

  const { data: gateways, isLoading: gatewaysLoading } = useQuery({
    queryKey: ["gateways"],
    queryFn: getGateways,
    refetchInterval: 30_000,
  });

  const { data: retryQueue, isLoading: retryQueueLoading } = useQuery({
    queryKey: ["retry-queue"],
    queryFn: getRetryQueue,
    refetchInterval: 30_000,
  });

  const [eventTypeFilter, setEventTypeFilter] = useState<string | undefined>(undefined);
  const { data: events, isLoading: eventsLoading } = useQuery({
    queryKey: ["meter-events", eventTypeFilter],
    queryFn: () => getMeterEvents(eventTypeFilter),
    refetchInterval: 30_000,
  });

  const { data, isLoading } = useQuery({
    queryKey: ["ingestion-metrics"],
    queryFn: () => getIngestionMetrics(),
    refetchInterval: 30_000,
  });

  const [channel, setChannel] = useState("active_energy");
  const [error, setError] = useState<string | null>(null);
  const [lastRead, setLastRead] = useState<{ meterId: string; value: number } | null>(null);

  const readNowMutation = useMutation({
    mutationFn: (meterId: string) => readMeterNow(meterId, channel),
    onSuccess: (reading, meterId) => {
      setError(null);
      setLastRead({ meterId, value: reading.value });
      queryClient.invalidateQueries({ queryKey: ["ingestion-metrics"] });
      queryClient.invalidateQueries({ queryKey: ["fleet-summary"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard-overview"] });
    },
    onError: (err) => setError(err instanceof ApiError ? err.message : "No se pudo leer el medidor ahora."),
  });

  return (
    <StagePage title="Medidores / HES / Ingesta">
      <SectionNav items={SECTIONS} />

      <div id="map" className="scroll-mt-24 mb-8">
        <MetersMapSection />
      </div>

      <div id="distribution" className="scroll-mt-24 mb-8">
        <DistributionSection />
      </div>

      {/* KPIs generales del modulo -- alarmas, salud de comunicacion y cola
          de reintentos, lo que un HES de referencia llama "communication
          statistics" + "alarm management" (Sprint C11-4). */}
      {eventSummary && (
        <div className="mb-6 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="rounded-xl border border-slate-200 bg-white p-4">
            <div className={`text-2xl font-bold ${eventSummary.critical_alarms_24h > 0 ? "text-red-700" : "text-slate-900"}`}>
              {eventSummary.alarms_24h}
            </div>
            <div className="text-xs text-slate-500 mt-1">Alarmas en 24h ({eventSummary.critical_alarms_24h} críticas)</div>
          </div>
          <div className="rounded-xl border border-slate-200 bg-white p-4">
            <div className={`text-2xl font-bold ${rateTextClass(eventSummary.comm_success_rate_24h)}`}>
              {eventSummary.comm_success_rate_24h === null ? "—" : `${eventSummary.comm_success_rate_24h}%`}
            </div>
            <div className="text-xs text-slate-500 mt-1">Éxito de comunicación 24h</div>
          </div>
          <div className="rounded-xl border border-slate-200 bg-white p-4">
            <div className="text-2xl font-bold text-amber-700">{eventSummary.comm_failures_24h}</div>
            <div className="text-xs text-slate-500 mt-1">Fallas de comunicación 24h</div>
          </div>
          <div className="rounded-xl border border-slate-200 bg-white p-4">
            <div className={`text-2xl font-bold ${eventSummary.meters_in_retry_queue > 0 ? "text-amber-700" : "text-slate-900"}`}>
              {eventSummary.meters_in_retry_queue}
            </div>
            <div className="text-xs text-slate-500 mt-1">Medidores en cola de reintento</div>
          </div>
        </div>
      )}

      {/* Flota por marca/modelo (G4) -- lo primero que pregunta un operador
          de HES: "¿cuántos medidores de cada marca tengo y qué porcentaje
          está reportando ahora?" */}
      <div id="fleet" className="scroll-mt-24">
      <h2 className="text-sm font-semibold text-slate-500 uppercase tracking-wide mb-2">
        Flota por marca / modelo
      </h2>
      {fleetLoading && <p className="text-sm text-slate-500 mb-4">Cargando...</p>}
      {fleet && fleet.length === 0 && (
        <div className="mb-6">
          <EmptyState message="No hay medidores registrados todavía." />
        </div>
      )}
      {fleet && fleet.length > 0 && (
        <div className="mb-6 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {fleet.map((row) => (
            <div key={`${row.brand}-${row.model ?? ""}`} className="rounded-xl border border-slate-200 bg-white p-4">
              <div className="flex items-baseline justify-between">
                <div>
                  <div className="text-sm font-bold text-slate-900">{row.brand}</div>
                  <div className="text-xs text-slate-500">{row.model ?? "modelo sin especificar"}</div>
                </div>
                <span
                  className={`rounded-full px-2 py-0.5 text-xs font-semibold ${ratePillClass(row.reporting_pct)}`}
                >
                  {row.reporting_pct === null ? "sin umbral configurado" : `${row.reporting_pct}% reportando`}
                </span>
              </div>
              <div className="mt-3 h-2 rounded-full bg-slate-100 overflow-hidden">
                {row.reporting_pct !== null && (
                  <div
                    className={`h-full ${
                      row.reporting_pct >= 90 ? "bg-emerald-500" : row.reporting_pct >= 60 ? "bg-amber-500" : "bg-red-500"
                    }`}
                    style={{ width: `${row.reporting_pct}%` }}
                  />
                )}
              </div>
              <div className="mt-2 flex justify-between text-xs text-slate-500">
                <span>{row.total} medidores</span>
                <span>{row.active} activos</span>
                <span>{row.reporting} reportando</span>
              </div>
            </div>
          ))}
        </div>
      )}
      </div>

      {/* Capa de agregacion (G5) -- concentradores/gateways que agrupan
          medidores de una o varias marcas, con su tasa de exito real de
          polling en 24h (auditada, F09). */}
      <div id="gateways" className="scroll-mt-24">
      <h2 className="text-sm font-semibold text-slate-500 uppercase tracking-wide mb-2">
        Concentradores (capa de agregación)
      </h2>
      {gatewaysLoading && <p className="text-sm text-slate-500 mb-4">Cargando...</p>}
      {gateways && gateways.length === 0 && (
        <div className="mb-6">
          <EmptyState message="No hay concentradores registrados todavía." />
        </div>
      )}
      {gateways && gateways.length > 0 && (
        <div className="mb-6 overflow-x-auto rounded-xl border border-slate-200 bg-white">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-4 py-3">Concentrador</th>
                <th className="px-4 py-3">Conexión</th>
                <th className="px-4 py-3">Medidores</th>
                <th className="px-4 py-3">Marcas</th>
                <th className="px-4 py-3">Último ciclo de polling</th>
                <th className="px-4 py-3">Éxito 24h</th>
              </tr>
            </thead>
            <tbody>
              {gateways.map((gw) => (
                <tr key={gw.gateway_id}>
                  <td className="px-4 py-3 font-medium text-slate-900">{gw.name}</td>
                  <td className="px-4 py-3 text-slate-600">
                    {gw.host ? `${gw.host}${gw.port ? `:${gw.port}` : ""}` : "—"}
                  </td>
                  <td className="px-4 py-3 tabular-nums">{gw.meter_count}</td>
                  <td className="px-4 py-3 text-slate-600">
                    {gw.brands.length > 0 ? gw.brands.join(", ") : "—"}
                  </td>
                  <td className="px-4 py-3 text-slate-600">
                    {gw.last_poll_at ? new Date(gw.last_poll_at).toLocaleString() : "nunca"}
                  </td>
                  <td className="px-4 py-3">
                    <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${ratePillClass(gw.success_rate_24h)}`}>
                      {gw.success_rate_24h === null ? "sin datos" : `${gw.success_rate_24h}%`}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      </div>

      {/* Cola de reintentos (F08, Sprint C11) -- antes solo backend, ahora
          visible: que medidor esta en backoff, hace cuanto, y por que. */}
      <div id="retry-queue" className="scroll-mt-24">
      <h2 className="text-sm font-semibold text-slate-500 uppercase tracking-wide mb-2">
        Cola de reintentos
      </h2>
      {retryQueueLoading && <p className="text-sm text-slate-500 mb-4">Cargando...</p>}
      {retryQueue && retryQueue.length === 0 && (
        <div className="mb-6">
          <EmptyState message="Ningún medidor en cola de reintento. 👍" />
        </div>
      )}
      {retryQueue && retryQueue.length > 0 && (
        <div className="mb-6 overflow-x-auto rounded-xl border border-amber-200 bg-white">
          <table className="w-full text-sm">
            <thead className="bg-amber-50 text-left text-xs uppercase tracking-wide text-amber-700">
              <tr>
                <th className="px-4 py-3">Cuenta</th>
                <th className="px-4 py-3">Marca / modelo</th>
                <th className="px-4 py-3">Intentos fallidos</th>
                <th className="px-4 py-3">Último error</th>
                <th className="px-4 py-3">Próximo intento</th>
              </tr>
            </thead>
            <tbody>
              {retryQueue.map((row) => (
                <tr key={row.meter_id}>
                  <td className="px-4 py-3 font-medium text-slate-900">{row.account_number}</td>
                  <td className="px-4 py-3 text-slate-600">
                    {row.brand ?? "—"}
                    {row.model ? ` / ${row.model}` : ""}
                  </td>
                  <td className="px-4 py-3 tabular-nums">{row.failure_count}</td>
                  <td className="px-4 py-3 text-red-600">{row.last_error ?? "—"}</td>
                  <td className="px-4 py-3 text-slate-600">{relativeFromNow(row.next_retry_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      </div>

      {/* Eventos y alarmas (F05 + F09, Sprint C11-4) -- feed real de
          `meter_event`: alarmas del medidor y auditoria de comunicacion,
          antes invisibles salvo el conteo agregado de exito 24h. */}
      <div id="events" className="scroll-mt-24">
      <h2 className="text-sm font-semibold text-slate-500 uppercase tracking-wide mb-2">
        Eventos y alarmas
      </h2>
      <div className="mb-3 flex gap-2">
        {[undefined, "meter_alarm", "communication_failure", "communication_success"].map((t) => (
          <button
            key={t ?? "todos"}
            onClick={() => setEventTypeFilter(t)}
            className={`rounded-full px-3 py-1 text-xs font-semibold border ${
              eventTypeFilter === t
                ? "bg-indigo-600 text-white border-indigo-600"
                : "bg-white text-slate-600 border-slate-200 hover:border-slate-300"
            }`}
          >
            {t ? eventTypeLabel(t) : "Todos"}
          </button>
        ))}
      </div>
      {eventsLoading && <p className="text-sm text-slate-500 mb-8">Cargando...</p>}
      {events && events.length === 0 && (
        <div className="mb-8">
          <EmptyState message="Sin eventos todavía." />
        </div>
      )}
      {events && events.length > 0 && (
        <div className="mb-8 overflow-x-auto rounded-xl border border-slate-200 bg-white">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-4 py-3">Cuenta</th>
                <th className="px-4 py-3">Marca / modelo</th>
                <th className="px-4 py-3">Concentrador</th>
                <th className="px-4 py-3">Tipo</th>
                <th className="px-4 py-3">Severidad</th>
                <th className="px-4 py-3">Detalle</th>
                <th className="px-4 py-3">Cuándo</th>
              </tr>
            </thead>
            <tbody>
              {events.map((ev, i) => (
                <tr key={`${ev.meter_id}-${ev.timestamp}-${i}`}>
                  <td className="px-4 py-3 font-medium text-slate-900">{ev.account_number}</td>
                  <td className="px-4 py-3 text-slate-600">
                    {ev.brand ?? "—"}
                    {ev.model ? ` / ${ev.model}` : ""}
                  </td>
                  <td className="px-4 py-3 text-slate-600">{ev.gateway_name ?? "—"}</td>
                  <td className="px-4 py-3 text-slate-600">{eventTypeLabel(ev.type)}</td>
                  <td className="px-4 py-3">
                    <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${SEVERITY_CLASS[ev.severity] ?? SEVERITY_CLASS.info}`}>
                      {ev.severity}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-slate-500">{eventDetailText(ev)}</td>
                  <td className="px-4 py-3 text-slate-500">{new Date(ev.timestamp).toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      </div>

      {/* Detalle por medidor (Sprint C2, extendido con marca/modelo/
          concentrador en C7) -- exception-first: solo importa el que esta
          caido o al que hay que leerle algo ahora. */}
      <div id="meters-list" className="scroll-mt-24">
      <h2 className="text-sm font-semibold text-slate-500 uppercase tracking-wide mb-2">
        Medidores
      </h2>
      <div className="mb-4 flex flex-wrap items-end gap-3 rounded-xl border border-slate-200 bg-white p-4">
        <div>
          <label className="block text-xs font-medium text-slate-500 mb-1">Canal para "Leer ahora"</label>
          <input
            className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm"
            value={channel}
            onChange={(e) => setChannel(e.target.value)}
          />
        </div>
        {error && <p className="text-sm text-red-600">{error}</p>}
        {lastRead && !error && (
          <p className="text-sm text-emerald-700">Última lectura bajo demanda: {lastRead.value}</p>
        )}
      </div>

      {isLoading && <p className="text-sm text-slate-500">Cargando...</p>}
      {data && data.meters.length === 0 && <EmptyState message="No hay medidores activos todavía." />}
      {data && data.meters.length > 0 && (
        <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-4 py-3">Cuenta</th>
                <th className="px-4 py-3">Marca / modelo</th>
                <th className="px-4 py-3">Concentrador</th>
                <th className="px-4 py-3">Estado</th>
                <th className="px-4 py-3">Última lectura</th>
                <th className="px-4 py-3">Lecturas 24h</th>
                <th className="px-4 py-3">Fallas de comunicación 24h</th>
                <th className="px-4 py-3"></th>
              </tr>
            </thead>
            <tbody>
              {data.meters.map((meter) => (
                <tr key={meter.meter_id} className={meter.is_stale ? "bg-amber-50" : ""}>
                  <td className="px-4 py-3 font-medium text-slate-900">{meter.account_number}</td>
                  <td className="px-4 py-3 text-slate-600">
                    {meter.brand ?? "—"}
                    {meter.model ? ` / ${meter.model}` : ""}
                  </td>
                  <td className="px-4 py-3 text-slate-600">{meter.gateway_name ?? "—"}</td>
                  <td className="px-4 py-3">
                    {meter.is_stale === null ? (
                      <span className="text-slate-400" title="Configura el umbral en Configuración → HES">Sin umbral</span>
                    ) : meter.is_stale ? (
                      <span className="text-amber-700">⚠ Caído</span>
                    ) : (
                      <span className="text-slate-500">Activo</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-slate-600">
                    {meter.last_reading_at ? new Date(meter.last_reading_at).toLocaleString() : "nunca"}
                  </td>
                  <td className="px-4 py-3 tabular-nums">{meter.readings_24h}</td>
                  <td className="px-4 py-3 tabular-nums">{meter.communication_failures_24h}</td>
                  <td className="px-4 py-3">
                    <button
                      onClick={() => readNowMutation.mutate(meter.meter_id)}
                      disabled={readNowMutation.isPending}
                      className="rounded-lg bg-indigo-600 text-white text-xs font-semibold px-3 py-1.5 hover:bg-indigo-700 disabled:opacity-40"
                    >
                      Leer ahora
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      </div>
    </StagePage>
  );
}
