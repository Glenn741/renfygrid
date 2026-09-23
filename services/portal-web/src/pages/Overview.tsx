import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  getControlSummary,
  getConsumptionSummary,
  getDashboardOverview,
  getFleetSummary,
  getNetworkBalanceSummary,
  getNetworkZonesGeojson,
  getVeeSummary,
} from "../api";
import { KpiTile } from "../components/KpiTile";
import { AppShell } from "../components/AppShell";
import { NetworkMap, nrwColorForMap } from "../components/NetworkMap";
import { TrendBars } from "../components/TrendBars";
import { SectionNav } from "../components/SectionNav";

// Nivel 1 (F48, Sprint C1) -- rediseñada 2026-09-14 a pedido directo del
// usuario: la version anterior solo tenia 4 tiles de Track A y se veia
// "escueta... como una plataforma escolar". Esta version es un reflejo
// real de TODA la plataforma -- los 7 modulos con nocion de excepcion
// (patron exception-first, docs/02-arquitectura-general.md SS9), un mapa
// real de la red (zonas por NRW, mismo componente que Balance de Red), 2
// graficos reales (tendencia VEE 7 dias, flota HES por marca) y un
// lanzador con los 11 modulos del portal -- todo con datos reales ya
// expuestos por los endpoints existentes, nada inventado para "verse
// lleno".

const SECTIONS = [
  { id: "kpis", label: "Estado general" },
  { id: "map", label: "Mapa de la red" },
  { id: "trends", label: "Tendencias" },
  { id: "modules", label: "Todos los módulos" },
];

interface ModuleCard {
  to: string;
  icon: string;
  label: string;
  description: string;
}

const MODULES: ModuleCard[] = [
  { to: "/meters", icon: "\u{1F4E1}", label: "HES / Ingesta", description: "Medidores, concentradores, flota y eventos/alarmas" },
  { to: "/vee", icon: "✓", label: "VEE", description: "Validación, estimación y edición manual de lecturas" },
  { to: "/consumption", icon: "\u{1F4C8}", label: "Consumo", description: "Consumo facturable y anomalías bajo revisión" },
  { to: "/control", icon: "⚡", label: "Control (SCR)", description: "Suspensión, corte y reconexión remota" },
  { to: "/network-balance", icon: "\u{1F4A7}", label: "Balance de Red", description: "NRW, ILI y balance hídrico IWA por zona" },
  { to: "/network-model", icon: "\u{1F30A}", label: "Modelado Hidráulico", description: "Simulación EPANET (WNTR) de presión y caudal" },
  { to: "/digital-twin", icon: "\u{1F5FA}", label: "Gemelo Digital", description: "Inventario georreferenciado de activos de red" },
  { to: "/maintenance", icon: "\u{1F527}", label: "Mantenimiento", description: "Órdenes de mantenimiento e integración BayForce" },
  { to: "/integrations", icon: "\u{1F517}", label: "Integraciones (CIS)", description: "Feed unificado de órdenes y lecturas bajo demanda" },
  { to: "/observability", icon: "\u{1FA7A}", label: "Observabilidad", description: "Alertas activas de ingesta en tiempo real" },
  { to: "/configuration", icon: "⚙", label: "Configuración", description: "Reglas VEE/consumo, aprobación SCR, OBIS, cuentas protegidas" },
];

function StatCard({ label, value, colorClass, hint }: { label: string; value: string; colorClass?: string; hint?: string }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4">
      <div className={`text-2xl font-bold ${colorClass ?? "text-slate-900"}`}>{value}</div>
      <div className="text-xs text-slate-500 mt-1">{label}{hint && <span className="text-slate-400"> — {hint}</span>}</div>
    </div>
  );
}

export function OverviewPage() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["dashboard-overview"],
    queryFn: getDashboardOverview,
    refetchInterval: 30_000,
  });

  const { data: zonesGeo } = useQuery({
    queryKey: ["network-zones-geojson"],
    queryFn: getNetworkZonesGeojson,
    refetchInterval: 30_000,
  });

  const { data: veeSummary } = useQuery({ queryKey: ["vee-summary"], queryFn: getVeeSummary, refetchInterval: 30_000 });
  const { data: fleet } = useQuery({ queryKey: ["fleet-summary"], queryFn: getFleetSummary, refetchInterval: 30_000 });
  const { data: balanceSummary } = useQuery({
    queryKey: ["network-balance-summary"],
    queryFn: getNetworkBalanceSummary,
    refetchInterval: 30_000,
  });
  const { data: controlSummary } = useQuery({ queryKey: ["control-summary"], queryFn: getControlSummary, refetchInterval: 30_000 });
  const { data: consumptionSummary } = useQuery({
    queryKey: ["consumption-summary"],
    queryFn: getConsumptionSummary,
    refetchInterval: 30_000,
  });

  const topFleet = [...(fleet ?? [])]
    .filter((r) => r.reporting_pct !== null)
    .sort((a, b) => (a.reporting_pct as number) - (b.reporting_pct as number))
    .slice(0, 5);

  return (
    <AppShell title="Vista general">
      <SectionNav items={SECTIONS} />
      {isLoading && <p className="text-sm text-slate-500">Cargando...</p>}
      {error && <p className="text-sm text-red-600">No se pudo cargar el tablero.</p>}

      {data && (
        <div id="kpis" className="scroll-mt-24 mb-8">
          <h2 className="text-sm font-semibold text-slate-500 uppercase tracking-wide mb-2">Estado general — toda la plataforma</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <KpiTile
              to="/meters"
              label="Medidores caídos"
              value={data.hes.meters_stale}
              alert={!!data.hes.meters_stale && data.hes.meters_stale > 0}
              hint={data.hes.meters_stale === null ? "umbral sin configurar" : `de ${data.hes.meters_total} activos`}
            />
            <KpiTile
              to="/vee"
              label="Lecturas VEE inválidas"
              value={data.vee.invalid_pending}
              alert={data.vee.invalid_pending > 0}
              hint="pendientes de revisión"
            />
            <KpiTile
              to="/consumption"
              label="Consumos en revisión"
              value={data.consumption.under_review}
              alert={data.consumption.under_review > 0}
              hint="retenidos de facturación"
            />
            <KpiTile
              to="/control"
              label="Órdenes por aprobar"
              value={data.control.pending_approval}
              alert={data.control.pending_approval > 0}
              hint="control (SCR)"
            />
            <KpiTile
              to="/network-balance"
              label="Zonas sobre su tope de NRW"
              value={data.network_balance.zones_exceeding_threshold}
              alert={data.network_balance.zones_exceeding_threshold > 0}
              hint="balance de red"
            />
            <KpiTile
              to="/digital-twin"
              label="Activos fuera de servicio"
              value={data.digital_twin.assets_out_of_service}
              alert={data.digital_twin.assets_out_of_service > 0}
              hint="gemelo digital"
            />
            <KpiTile
              to="/maintenance"
              label="Órdenes por enviar a BayForce"
              value={data.maintenance.orders_pending}
              alert={data.maintenance.orders_pending > 0}
              hint="mantenimiento"
            />
          </div>
        </div>
      )}

      <div id="map" className="scroll-mt-24 mb-8">
        <h2 className="text-sm font-semibold text-slate-500 uppercase tracking-wide mb-2">Mapa de la red — zonas por NRW</h2>
        <NetworkMap
          geojson={zonesGeo}
          height={300}
          emptyMessage="Ninguna zona tiene latitud/longitud cargada todavía — agrégalas en Balance de Red para verla aquí."
          pointColor={(p) => nrwColorForMap(typeof p.nrw_pct === "number" ? p.nrw_pct : null, p.exceeds_threshold as boolean | null)}
          pointRadius={() => 9}
          popupHtml={(p) => `<div style="font-size:12px"><strong>${p.name}</strong><br/>` +
            (typeof p.nrw_pct === "number" ? `NRW: ${(p.nrw_pct as number).toFixed(1)}%` : "Sin balance registrado") +
            `</div>`}
        />
        <div className="mt-2 flex flex-wrap gap-4 text-xs text-slate-500">
          <span><span className="inline-block w-2.5 h-2.5 rounded-full mr-1" style={{ background: "#10b981" }} />NRW baja</span>
          <span><span className="inline-block w-2.5 h-2.5 rounded-full mr-1" style={{ background: "#f59e0b" }} />NRW ≥20%</span>
          <span><span className="inline-block w-2.5 h-2.5 rounded-full mr-1" style={{ background: "#ef4444" }} />Excede tope regulatorio</span>
          <Link to="/network-balance" className="ml-auto text-indigo-600 hover:text-indigo-700 font-medium">Ver Balance de Red →</Link>
        </div>
      </div>

      <div id="trends" className="scroll-mt-24 mb-8">
        <h2 className="text-sm font-semibold text-slate-500 uppercase tracking-wide mb-2">Tendencias</h2>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-4">
          <div className="rounded-xl border border-slate-200 bg-white p-4">
            <div className="flex items-center justify-between mb-2">
              <div className="text-xs font-medium text-slate-500">VEE — últimos 7 días (verde: válidas, rojo: excepciones)</div>
              <Link to="/vee" className="text-xs text-indigo-600 hover:text-indigo-700 font-medium">Ver VEE →</Link>
            </div>
            {veeSummary && veeSummary.validation.trend_7d.length > 0 ? (
              <TrendBars trend={veeSummary.validation.trend_7d} />
            ) : (
              <p className="text-sm text-slate-400 h-20 flex items-center">Sin lecturas procesadas todavía.</p>
            )}
          </div>
          <div className="rounded-xl border border-slate-200 bg-white p-4">
            <div className="flex items-center justify-between mb-2">
              <div className="text-xs font-medium text-slate-500">HES — flota con menor % reportando</div>
              <Link to="/meters" className="text-xs text-indigo-600 hover:text-indigo-700 font-medium">Ver HES / Ingesta →</Link>
            </div>
            {topFleet.length > 0 ? (
              <div className="space-y-2">
                {topFleet.map((row) => (
                  <div key={`${row.brand}-${row.model ?? ""}`}>
                    <div className="flex justify-between text-xs text-slate-600 mb-0.5">
                      <span>{row.brand}{row.model ? ` / ${row.model}` : ""}</span>
                      <span className="tabular-nums font-semibold">{row.reporting_pct}%</span>
                    </div>
                    <div className="h-1.5 rounded-full bg-slate-100 overflow-hidden">
                      <div
                        className={`h-full ${row.reporting_pct! >= 90 ? "bg-emerald-500" : row.reporting_pct! >= 60 ? "bg-amber-500" : "bg-red-500"}`}
                        style={{ width: `${row.reporting_pct}%` }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-slate-400 h-20 flex items-center">Sin medidores registrados todavía.</p>
            )}
          </div>
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          <StatCard
            label="NRW% promedio"
            value={balanceSummary?.avg_nrw_pct == null ? "—" : `${balanceSummary.avg_nrw_pct}%`}
            colorClass={balanceSummary && balanceSummary.zones_exceeding_threshold > 0 ? "text-red-700" : "text-emerald-700"}
            hint="balance de red"
          />
          <StatCard
            label="Peor ILI"
            value={balanceSummary?.worst_ili == null ? "—" : String(balanceSummary.worst_ili)}
            hint="infraestructura"
          />
          <StatCard
            label="Éxito de comando"
            value={controlSummary?.command_success_rate_pct == null ? "—" : `${controlSummary.command_success_rate_pct}%`}
            colorClass={controlSummary && controlSummary.command_success_rate_pct !== null && controlSummary.command_success_rate_pct < 80 ? "text-red-700" : "text-emerald-700"}
            hint="control (SCR)"
          />
          <StatCard
            label="Listo para facturar"
            value={consumptionSummary?.billing_ready_pct == null ? "—" : `${consumptionSummary.billing_ready_pct}%`}
            colorClass="text-emerald-700"
            hint="consumo"
          />
        </div>
      </div>

      <div id="modules" className="scroll-mt-24">
        <h2 className="text-sm font-semibold text-slate-500 uppercase tracking-wide mb-2">Todos los módulos</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {MODULES.map((m) => (
            <Link
              key={m.to}
              to={m.to}
              className="rounded-xl border border-slate-200 bg-white p-4 flex items-start gap-3 hover:border-indigo-300 hover:shadow-sm transition-shadow"
            >
              <span className="text-xl leading-none shrink-0 mt-0.5">{m.icon}</span>
              <div>
                <div className="text-sm font-semibold text-slate-900">{m.label}</div>
                <div className="text-xs text-slate-500 mt-0.5">{m.description}</div>
              </div>
            </Link>
          ))}
        </div>
      </div>
    </AppShell>
  );
}
