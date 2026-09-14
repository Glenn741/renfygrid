import { useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ApiError,
  createNetworkZone,
  generateNetworkModelFromTwin,
  getNetworkBalanceSummary,
  getNetworkBalances,
  getNetworkZones,
  getNetworkZonesGeojson,
  submitNetworkBalance,
  type NetworkBalance,
  type NetworkZone,
} from "../api";
import { StagePage, EmptyState } from "../components/StagePage";
import { NetworkMap, nrwColorForMap } from "../components/NetworkMap";

// Balance de Red -- Track B, Sprint B1/B1-2 (docs/07-track-b-alcance-funcional.md):
// matriz de Balance Hidrico IWA completa. Venta modular -- este panel no
// depende del HES/VEE propio de RenfyGrid (01-planteamiento.md SS3): una
// zona puede recibir su balance de un CIS/HES externo (`data_source`).

const ZONE_TYPE_LABEL: Record<string, string> = {
  dma: "DMA (Distrito Hidrométrico)",
  circuit: "Circuito",
  district: "Distrito",
  pressure_zone: "Zona de presión",
};

const METHOD_LABEL: Record<string, string> = {
  top_down: "Top-Down (auditoría)",
  bottom_up: "Bottom-Up (componentes)",
};

function nrwColor(pct: number | null, exceeds: boolean | null): string {
  if (pct === null) return "text-slate-400";
  if (exceeds === true) return "text-red-700";
  if (pct >= 20) return "text-amber-700";
  return "text-emerald-700";
}

function iliColor(ili: number | null): string {
  // ILI 1-4: bueno; 4-8: aceptable; >8: pobre (banda IWA estandar).
  if (ili === null) return "text-slate-400";
  if (ili > 8) return "text-red-700";
  if (ili > 4) return "text-amber-700";
  return "text-emerald-700";
}

function RegisterZoneForm() {
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [type, setType] = useState("dma");
  const [dataSource, setDataSource] = useState("external");
  const [networkLengthKm, setNetworkLengthKm] = useState("");
  const [numConnections, setNumConnections] = useState("");
  const [avgPressureMca, setAvgPressureMca] = useState("");
  const [nrwThresholdPct, setNrwThresholdPct] = useState("30");
  const [centroidLat, setCentroidLat] = useState("");
  const [centroidLon, setCentroidLon] = useState("");
  const [error, setError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: () =>
      createNetworkZone({
        name,
        type,
        data_source: dataSource,
        network_length_km: networkLengthKm ? Number(networkLengthKm) : null,
        num_connections: numConnections ? Number(numConnections) : null,
        avg_pressure_mca: avgPressureMca ? Number(avgPressureMca) : null,
        nrw_threshold_pct: nrwThresholdPct ? Number(nrwThresholdPct) : null,
        centroid_lat: centroidLat ? Number(centroidLat) : null,
        centroid_lon: centroidLon ? Number(centroidLon) : null,
      }),
    onSuccess: () => {
      setError(null);
      setName("");
      setNetworkLengthKm("");
      setNumConnections("");
      setAvgPressureMca("");
      setOpen(false);
      queryClient.invalidateQueries({ queryKey: ["network-zones"] });
      queryClient.invalidateQueries({ queryKey: ["network-balance-summary"] });
    },
    onError: (err) => setError(err instanceof ApiError ? err.message : "No se pudo registrar la zona."),
  });

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        className="rounded-lg bg-indigo-600 text-white text-xs font-semibold px-3 py-1.5 hover:bg-indigo-700"
      >
        + Registrar zona
      </button>
    );
  }

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 mb-4">
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
        <div>
          <label className="block text-xs font-medium text-slate-500 mb-1">Nombre de la zona</label>
          <input
            className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm w-full"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="ej. DMA Centro"
          />
        </div>
        <div>
          <label className="block text-xs font-medium text-slate-500 mb-1">Tipo</label>
          <select
            className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm w-full bg-white"
            value={type}
            onChange={(e) => setType(e.target.value)}
          >
            {Object.entries(ZONE_TYPE_LABEL).map(([value, label]) => (
              <option key={value} value={value}>{label}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-xs font-medium text-slate-500 mb-1">Origen del dato</label>
          <select
            className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm w-full bg-white"
            value={dataSource}
            onChange={(e) => setDataSource(e.target.value)}
          >
            <option value="external">Externo (CIS/HES de terceros)</option>
            <option value="renfygrid">RenfyGrid (medidores propios)</option>
          </select>
        </div>
        <div>
          <label className="block text-xs font-medium text-slate-500 mb-1">Longitud de red (km)</label>
          <input
            type="number"
            className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm w-full"
            value={networkLengthKm}
            onChange={(e) => setNetworkLengthKm(e.target.value)}
            placeholder="opcional -- para ILI"
          />
        </div>
        <div>
          <label className="block text-xs font-medium text-slate-500 mb-1">N.º de conexiones</label>
          <input
            type="number"
            className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm w-full"
            value={numConnections}
            onChange={(e) => setNumConnections(e.target.value)}
            placeholder="opcional -- para ILI"
          />
        </div>
        <div>
          <label className="block text-xs font-medium text-slate-500 mb-1">Presión promedio (m.c.a.)</label>
          <input
            type="number"
            className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm w-full"
            value={avgPressureMca}
            onChange={(e) => setAvgPressureMca(e.target.value)}
            placeholder="opcional -- para ILI"
          />
        </div>
        <div>
          <label className="block text-xs font-medium text-slate-500 mb-1">Tope de NRW (%)</label>
          <input
            type="number"
            className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm w-full"
            value={nrwThresholdPct}
            onChange={(e) => setNrwThresholdPct(e.target.value)}
            placeholder="ej. 30 (CRA/IANC Colombia) -- según regulador"
          />
        </div>
        <div>
          <label className="block text-xs font-medium text-slate-500 mb-1">Latitud (centroide)</label>
          <input
            type="number"
            className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm w-full"
            value={centroidLat}
            onChange={(e) => setCentroidLat(e.target.value)}
            placeholder="opcional -- para el mapa"
          />
        </div>
        <div>
          <label className="block text-xs font-medium text-slate-500 mb-1">Longitud (centroide)</label>
          <input
            type="number"
            className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm w-full"
            value={centroidLon}
            onChange={(e) => setCentroidLon(e.target.value)}
            placeholder="opcional -- para el mapa"
          />
        </div>
      </div>
      <p className="text-xs text-slate-500 mt-2">
        Longitud de red, conexiones y presión son opcionales, pero sin los tres el ILI de esta zona quedará sin calcular (nunca se inventa con un supuesto no declarado). El tope de NRW es configurable por zona -- cada regulador define el suyo. Sin latitud/longitud, la zona no aparece en el mapa (abajo) pero funciona igual en el resto del panel.
      </p>
      {error && <p className="text-sm text-red-600 mt-2">{error}</p>}
      <div className="mt-3 flex gap-2">
        <button
          onClick={() => mutation.mutate()}
          disabled={!name || mutation.isPending}
          className="rounded-lg bg-indigo-600 text-white text-xs font-semibold px-3 py-1.5 hover:bg-indigo-700 disabled:opacity-40"
        >
          Registrar
        </button>
        <button onClick={() => setOpen(false)} className="text-xs text-slate-500 hover:text-slate-700 px-2">
          Cancelar
        </button>
      </div>
    </div>
  );
}

function SubmitBalanceForm({ zone, onDone }: { zone: NetworkZone; onDone: () => void }) {
  const queryClient = useQueryClient();
  const today = new Date().toISOString().slice(0, 10);
  const [periodStart, setPeriodStart] = useState(today);
  const [periodEnd, setPeriodEnd] = useState(today);
  const [method, setMethod] = useState("top_down");
  const [siv, setSiv] = useState("");
  const [billedMetered, setBilledMetered] = useState("");
  const [billedUnbilled, setBilledUnbilled] = useState("");
  const [unbilledAuthorized, setUnbilledAuthorized] = useState("");
  const [apparentLosses, setApparentLosses] = useState("");
  const [realLosses, setRealLosses] = useState("");
  const [error, setError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: () =>
      submitNetworkBalance(zone.zone_id, {
        period_start: periodStart,
        period_end: periodEnd,
        method,
        system_input_volume: Number(siv),
        billed_metered_consumption: billedMetered ? Number(billedMetered) : 0,
        billed_unbilled_consumption: billedUnbilled ? Number(billedUnbilled) : 0,
        unbilled_authorized_consumption: unbilledAuthorized ? Number(unbilledAuthorized) : 0,
        apparent_losses: apparentLosses ? Number(apparentLosses) : 0,
        real_losses: realLosses ? Number(realLosses) : 0,
      }),
    onSuccess: () => {
      setError(null);
      queryClient.invalidateQueries({ queryKey: ["network-balances"] });
      queryClient.invalidateQueries({ queryKey: ["network-balance-summary"] });
      onDone();
    },
    onError: (err) => setError(err instanceof ApiError ? err.message : "No se pudo registrar el balance."),
  });

  return (
    <tr className="bg-slate-50">
      <td colSpan={6} className="px-4 py-3">
        <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-8 gap-2">
          <div className="col-span-1">
            <label className="block text-[10px] font-medium text-slate-500 mb-1">Inicio</label>
            <input type="date" className="rounded-lg border border-slate-300 px-2 py-1 text-xs w-full" value={periodStart} onChange={(e) => setPeriodStart(e.target.value)} />
          </div>
          <div className="col-span-1">
            <label className="block text-[10px] font-medium text-slate-500 mb-1">Fin</label>
            <input type="date" className="rounded-lg border border-slate-300 px-2 py-1 text-xs w-full" value={periodEnd} onChange={(e) => setPeriodEnd(e.target.value)} />
          </div>
          <div className="col-span-1">
            <label className="block text-[10px] font-medium text-slate-500 mb-1">Método</label>
            <select className="rounded-lg border border-slate-300 px-2 py-1 text-xs w-full bg-white" value={method} onChange={(e) => setMethod(e.target.value)}>
              {Object.entries(METHOD_LABEL).map(([value, label]) => (
                <option key={value} value={value}>{label}</option>
              ))}
            </select>
          </div>
          <div className="col-span-1">
            <label className="block text-[10px] font-medium text-slate-500 mb-1">System Input Volume *</label>
            <input type="number" className="rounded-lg border border-slate-300 px-2 py-1 text-xs w-full" value={siv} onChange={(e) => setSiv(e.target.value)} />
          </div>
          <div className="col-span-1">
            <label className="block text-[10px] font-medium text-slate-500 mb-1">Facturado medido</label>
            <input type="number" className="rounded-lg border border-slate-300 px-2 py-1 text-xs w-full" value={billedMetered} onChange={(e) => setBilledMetered(e.target.value)} />
          </div>
          <div className="col-span-1">
            <label className="block text-[10px] font-medium text-slate-500 mb-1">Facturado no medido</label>
            <input type="number" className="rounded-lg border border-slate-300 px-2 py-1 text-xs w-full" value={billedUnbilled} onChange={(e) => setBilledUnbilled(e.target.value)} />
          </div>
          <div className="col-span-1">
            <label className="block text-[10px] font-medium text-slate-500 mb-1">Autorizado no facturado</label>
            <input type="number" className="rounded-lg border border-slate-300 px-2 py-1 text-xs w-full" value={unbilledAuthorized} onChange={(e) => setUnbilledAuthorized(e.target.value)} />
          </div>
          <div className="col-span-1">
            <label className="block text-[10px] font-medium text-slate-500 mb-1">Pérdidas aparentes</label>
            <input type="number" className="rounded-lg border border-slate-300 px-2 py-1 text-xs w-full" value={apparentLosses} onChange={(e) => setApparentLosses(e.target.value)} />
          </div>
          <div className="col-span-1">
            <label className="block text-[10px] font-medium text-slate-500 mb-1">Pérdidas reales</label>
            <input type="number" className="rounded-lg border border-slate-300 px-2 py-1 text-xs w-full" value={realLosses} onChange={(e) => setRealLosses(e.target.value)} />
          </div>
        </div>
        {error && <p className="text-sm text-red-600 mt-2">{error}</p>}
        <div className="mt-3 flex gap-2">
          <button
            onClick={() => mutation.mutate()}
            disabled={!siv || !periodStart || !periodEnd || mutation.isPending}
            className="rounded-lg bg-indigo-600 text-white text-xs font-semibold px-3 py-1.5 hover:bg-indigo-700 disabled:opacity-40"
          >
            Registrar balance
          </button>
          <button onClick={onDone} className="text-xs text-slate-500 hover:text-slate-700 px-2">
            Cancelar
          </button>
        </div>
      </td>
    </tr>
  );
}

function ZoneRow({ zone }: { zone: NetworkZone }) {
  const [submitting, setSubmitting] = useState(false);
  const [genError, setGenError] = useState<string | null>(null);
  const [genOk, setGenOk] = useState<string | null>(null);
  const hasInfra = zone.network_length_km !== null && zone.num_connections !== null && zone.avg_pressure_mca !== null;

  const generateMutation = useMutation({
    mutationFn: () => generateNetworkModelFromTwin(zone.zone_id, `${zone.name} (desde Gemelo Digital)`),
    onSuccess: (model) => { setGenError(null); setGenOk(model.name); },
    onError: (err) => setGenError(err instanceof ApiError ? err.message : "No se pudo generar el modelo."),
  });

  return (
    <>
      <tr>
        <td className="px-4 py-3 font-medium text-slate-900">{zone.name}</td>
        <td className="px-4 py-3 text-slate-600">{ZONE_TYPE_LABEL[zone.type] ?? zone.type}</td>
        <td className="px-4 py-3 text-slate-600">{zone.data_source === "renfygrid" ? "RenfyGrid" : "Externo"}</td>
        <td className="px-4 py-3">
          {hasInfra ? (
            <span className="rounded-full bg-emerald-50 px-2 py-0.5 text-xs font-semibold text-emerald-700">calcula ILI</span>
          ) : (
            <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs font-semibold text-slate-500" title="Faltan longitud de red, conexiones o presión">sin insumos ILI</span>
          )}
        </td>
        <td className="px-4 py-3 text-slate-600">{zone.nrw_threshold_pct === null ? "—" : `${zone.nrw_threshold_pct}%`}</td>
        <td className="px-4 py-3">
          <div className="flex flex-col gap-1 items-start">
            <button onClick={() => setSubmitting((v) => !v)} className="text-xs text-indigo-600 hover:text-indigo-700">
              {submitting ? "Cancelar" : "Ingestar balance"}
            </button>
            <button
              onClick={() => { setGenOk(null); setGenError(null); generateMutation.mutate(); }}
              disabled={generateMutation.isPending}
              className="text-xs text-indigo-600 hover:text-indigo-700 disabled:opacity-40"
              title="Genera un modelo EPANET real desde los activos y conectividad registrados en el Gemelo Digital para esta zona"
            >
              {generateMutation.isPending ? "Generando..." : "Generar modelo (Gemelo Digital)"}
            </button>
            {genOk && (
              <span className="text-[11px] text-emerald-700">
                "{genOk}" generado —{" "}
                <Link to="/network-model" className="underline">ver en Modelado Hidráulico</Link>
              </span>
            )}
            {genError && <span className="text-[11px] text-red-600">{genError}</span>}
          </div>
        </td>
      </tr>
      {submitting && <SubmitBalanceForm zone={zone} onDone={() => setSubmitting(false)} />}
    </>
  );
}

export function NetworkBalancePage() {
  const { data: summary } = useQuery({
    queryKey: ["network-balance-summary"],
    queryFn: getNetworkBalanceSummary,
    refetchInterval: 30_000,
  });

  const { data: zones, isLoading: zonesLoading } = useQuery({
    queryKey: ["network-zones"],
    queryFn: getNetworkZones,
    refetchInterval: 30_000,
  });

  const { data: balances, isLoading: balancesLoading } = useQuery({
    queryKey: ["network-balances"],
    queryFn: () => getNetworkBalances(),
    refetchInterval: 30_000,
  });

  const { data: zonesGeo } = useQuery({
    queryKey: ["network-zones-geojson"],
    queryFn: getNetworkZonesGeojson,
    refetchInterval: 30_000,
  });

  return (
    <StagePage title="Balance de Red">
      {summary && (
        <div className="mb-6 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="rounded-xl border border-slate-200 bg-white p-4">
            <div className={`text-2xl font-bold ${nrwColor(summary.avg_nrw_pct, summary.zones_exceeding_threshold > 0 ? true : null)}`}>
              {summary.avg_nrw_pct === null ? "—" : `${summary.avg_nrw_pct}%`}
            </div>
            <div className="text-xs text-slate-500 mt-1">NRW% promedio</div>
          </div>
          <div className="rounded-xl border border-slate-200 bg-white p-4">
            <div className={`text-2xl font-bold ${summary.zones_exceeding_threshold > 0 ? "text-red-700" : "text-emerald-700"}`}>
              {summary.zones_exceeding_threshold}
            </div>
            <div className="text-xs text-slate-500 mt-1">Zonas sobre su tope regulatorio</div>
          </div>
          <div className={`rounded-xl border border-slate-200 bg-white p-4`}>
            <div className={`text-2xl font-bold ${iliColor(summary.worst_ili)}`}>
              {summary.worst_ili === null ? "—" : summary.worst_ili}
            </div>
            <div className="text-xs text-slate-500 mt-1">Peor ILI (Infrastructure Leakage Index)</div>
          </div>
          <div className="rounded-xl border border-slate-200 bg-white p-4">
            <div className="text-2xl font-bold text-slate-900">
              {summary.zones_with_balance}<span className="text-base text-slate-400">/{summary.total_zones}</span>
            </div>
            <div className="text-xs text-slate-500 mt-1">Zonas con balance registrado</div>
          </div>
        </div>
      )}

      <h2 className="text-sm font-semibold text-slate-500 uppercase tracking-wide mb-2">Mapa de zonas</h2>
      <div className="mb-2">
        <NetworkMap
          geojson={zonesGeo}
          height={340}
          emptyMessage="Ninguna zona tiene latitud/longitud cargada todavía -- agrégalas al registrar una zona para verla aquí."
          pointColor={(p) => nrwColorForMap(typeof p.nrw_pct === "number" ? p.nrw_pct : null, p.exceeds_threshold as boolean | null)}
          pointRadius={() => 10}
          popupHtml={(p) => `<div style="font-size:12px"><strong>${p.name}</strong><br/>` +
            (typeof p.nrw_pct === "number" ? `NRW: ${(p.nrw_pct as number).toFixed(1)}%` : "Sin balance registrado") +
            (p.exceeds_threshold === true ? ' <span style="color:#ef4444;font-weight:600">excede tope</span>' : "") +
            (typeof p.ili === "number" ? `<br/>ILI: ${(p.ili as number).toFixed(2)}` : "") +
            `</div>`}
        />
      </div>
      <div className="mb-6 flex flex-wrap gap-4 text-xs text-slate-500">
        <span><span className="inline-block w-2.5 h-2.5 rounded-full mr-1" style={{ background: "#10b981" }} />NRW baja</span>
        <span><span className="inline-block w-2.5 h-2.5 rounded-full mr-1" style={{ background: "#f59e0b" }} />NRW ≥20%</span>
        <span><span className="inline-block w-2.5 h-2.5 rounded-full mr-1" style={{ background: "#ef4444" }} />Excede tope regulatorio</span>
        <span><span className="inline-block w-2.5 h-2.5 rounded-full mr-1" style={{ background: "#94a3b8" }} />Sin balance/tope</span>
      </div>

      <div className="mb-2 flex items-center justify-between">
        <h2 className="text-sm font-semibold text-slate-500 uppercase tracking-wide">Zonas de red (DMA)</h2>
        <RegisterZoneForm />
      </div>
      {zonesLoading && <p className="text-sm text-slate-500 mb-8">Cargando...</p>}
      {zones && zones.length === 0 && (
        <div className="mb-8">
          <EmptyState message="Sin zonas registradas todavía. Registra una zona (DMA) para empezar a ingestar balances." />
        </div>
      )}
      {zones && zones.length > 0 && (
        <div className="mb-8 overflow-x-auto rounded-xl border border-slate-200 bg-white">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-4 py-3">Zona</th>
                <th className="px-4 py-3">Tipo</th>
                <th className="px-4 py-3">Origen</th>
                <th className="px-4 py-3">Infraestructura</th>
                <th className="px-4 py-3">Tope NRW</th>
                <th className="px-4 py-3"></th>
              </tr>
            </thead>
            <tbody>
              {zones.map((zone) => (
                <ZoneRow key={zone.zone_id} zone={zone} />
              ))}
            </tbody>
          </table>
        </div>
      )}

      <h2 className="text-sm font-semibold text-slate-500 uppercase tracking-wide mb-2">
        Balances por período (última versión de cada zona/período)
      </h2>
      {balancesLoading && <p className="text-sm text-slate-500">Cargando...</p>}
      {balances && balances.length === 0 && <EmptyState message="Sin balances registrados todavía." />}
      {balances && balances.length > 0 && (
        <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-4 py-3">Zona</th>
                <th className="px-4 py-3">Período</th>
                <th className="px-4 py-3">Método</th>
                <th className="px-4 py-3">NRW</th>
                <th className="px-4 py-3">ILI</th>
                <th className="px-4 py-3">Consistencia</th>
                <th className="px-4 py-3">Versión</th>
              </tr>
            </thead>
            <tbody>
              {balances.map((row: NetworkBalance) => (
                <tr key={row.balance_id}>
                  <td className="px-4 py-3 font-medium text-slate-900">{row.zone_name}</td>
                  <td className="px-4 py-3 text-slate-600">{row.period}</td>
                  <td className="px-4 py-3 text-slate-600">{METHOD_LABEL[row.method] ?? row.method}</td>
                  <td className={`px-4 py-3 font-semibold tabular-nums ${nrwColor(row.nrw_pct, row.exceeds_threshold)}`}>
                    {row.nrw_pct === null ? "—" : `${row.nrw_pct.toFixed(1)}%`}
                    {row.exceeds_threshold === true && (
                      <span className="ml-2 rounded-full bg-red-100 px-2 py-0.5 text-[10px] font-semibold text-red-700" title="Excede el tope regulatorio configurado para esta zona">
                        excede tope
                      </span>
                    )}
                  </td>
                  <td className={`px-4 py-3 tabular-nums ${iliColor(row.ili)}`}>
                    {row.ili === null ? "—" : row.ili.toFixed(2)}
                  </td>
                  <td className="px-4 py-3 tabular-nums text-slate-500" title="Cuánto se aleja la suma de los 5 componentes del System Input Volume declarado">
                    {row.balance_check_pct === null ? "—" : `${row.balance_check_pct.toFixed(1)}%`}
                  </td>
                  <td className="px-4 py-3 text-slate-500">v{row.version}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="mt-4 rounded-xl border border-indigo-100 bg-indigo-50/40 p-4 text-sm text-slate-600">
        <b className="text-slate-900">¿Qué es NRW e ILI?</b>{" "}
        NRW (Non-Revenue Water) es el % del agua que entra a la red y no genera ingreso -- en Colombia la CRA exige mantenerla bajo el 30% (IANC, Resolución 315/2005) para poder trasladar costos. ILI (Infrastructure Leakage Index) compara las pérdidas reales contra el mínimo técnicamente alcanzable para el tamaño de esa red específica -- solo se calcula si la zona tiene longitud de red, conexiones y presión configuradas.
      </div>
    </StagePage>
  );
}
