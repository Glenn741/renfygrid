import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ApiError,
  getFleetSummary,
  getGateways,
  getHesEventSummary,
  getIngestionMetrics,
  getMeterEvents,
  getRetryQueue,
  readMeterNow,
  type MeterEvent,
} from "../api";
import { StagePage, EmptyState } from "../components/StagePage";

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
                  {row.reporting_pct}% reportando
                </span>
              </div>
              <div className="mt-3 h-2 rounded-full bg-slate-100 overflow-hidden">
                <div
                  className={`h-full ${
                    row.reporting_pct >= 90 ? "bg-emerald-500" : row.reporting_pct >= 60 ? "bg-amber-500" : "bg-red-500"
                  }`}
                  style={{ width: `${row.reporting_pct}%` }}
                />
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

      {/* Capa de agregacion (G5) -- concentradores/gateways que agrupan
          medidores de una o varias marcas, con su tasa de exito real de
          polling en 24h (auditada, F09). */}
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

      {/* Cola de reintentos (F08, Sprint C11) -- antes solo backend, ahora
          visible: que medidor esta en backoff, hace cuanto, y por que. */}
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

      {/* Eventos y alarmas (F05 + F09, Sprint C11-4) -- feed real de
          `meter_event`: alarmas del medidor y auditoria de comunicacion,
          antes invisibles salvo el conteo agregado de exito 24h. */}
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

      {/* Detalle por medidor (Sprint C2, extendido con marca/modelo/
          concentrador en C7) -- exception-first: solo importa el que esta
          caido o al que hay que leerle algo ahora. */}
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
                    {meter.is_stale ? (
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
    </StagePage>
  );
}
