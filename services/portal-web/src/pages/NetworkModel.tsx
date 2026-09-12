import { useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ApiError,
  createNetworkModel,
  getNetworkModelGeojson,
  getNetworkModelSimulations,
  getNetworkModels,
  simulateNetworkModel,
  type NetworkModel,
  type SimulationResult,
} from "../api";
import { StagePage, EmptyState } from "../components/StagePage";
import { NetworkMap, pressureColor, flowColorScale } from "../components/NetworkMap";

// Modelado Hidraulico -- Track B, Sprint B3 (docs/07-track-b-alcance-funcional.md
// SS5): carga y versionado de un modelo EPANET real (.inp) + simulacion via
// WNTR (motor EPANET 2.2 -- el mismo que usan Bentley WaterGEMS/OpenFlows e
// Innovyze InfoWater por debajo). Venta modular: no depende de HES/VEE ni
// de Balance de Red propios.

function UploadModelForm() {
  const queryClient = useQueryClient();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [inpContent, setInpContent] = useState("");
  const [fileName, setFileName] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: () => createNetworkModel({ name, inp_content: inpContent }),
    onSuccess: () => {
      setError(null);
      setName("");
      setInpContent("");
      setFileName(null);
      setOpen(false);
      queryClient.invalidateQueries({ queryKey: ["network-models"] });
    },
    onError: (err) => setError(err instanceof ApiError ? err.message : "No se pudo registrar el modelo."),
  });

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setFileName(file.name);
    if (!name) setName(file.name.replace(/\.inp$/i, ""));
    const reader = new FileReader();
    reader.onload = () => setInpContent(String(reader.result ?? ""));
    reader.readAsText(file);
  };

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        className="rounded-lg bg-indigo-600 text-white text-xs font-semibold px-3 py-1.5 hover:bg-indigo-700"
      >
        + Cargar modelo (.inp)
      </button>
    );
  }

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 mb-4">
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-3">
        <div>
          <label className="block text-xs font-medium text-slate-500 mb-1">Nombre del modelo</label>
          <input
            className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm w-full"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="ej. Red Centro"
          />
        </div>
        <div>
          <label className="block text-xs font-medium text-slate-500 mb-1">Archivo EPANET (.inp)</label>
          <input
            ref={fileInputRef}
            type="file"
            accept=".inp,.txt"
            onChange={handleFileChange}
            className="text-sm text-slate-600 w-full"
          />
          {fileName && <p className="text-xs text-slate-400 mt-1">{fileName} -- {inpContent.length} caracteres leídos</p>}
        </div>
      </div>
      <p className="text-xs text-slate-500 mb-2">
        Si el nombre ya existe, esto registra una nueva versión (el historial completo se conserva). Un archivo que no sea un modelo EPANET válido se rechaza -- nunca se guarda un modelo roto.
      </p>
      {error && <p className="text-sm text-red-600 mb-2">{error}</p>}
      <div className="flex gap-2">
        <button
          onClick={() => mutation.mutate()}
          disabled={!name || !inpContent || mutation.isPending}
          className="rounded-lg bg-indigo-600 text-white text-xs font-semibold px-3 py-1.5 hover:bg-indigo-700 disabled:opacity-40"
        >
          Registrar modelo
        </button>
        <button onClick={() => setOpen(false)} className="text-xs text-slate-500 hover:text-slate-700 px-2">
          Cancelar
        </button>
      </div>
    </div>
  );
}

function SimulationRow({ sim }: { sim: SimulationResult }) {
  const [expanded, setExpanded] = useState(false);
  const nodeEntries = Object.entries(sim.nodes);
  const linkEntries = Object.entries(sim.links);

  return (
    <>
      <tr>
        <td className="px-4 py-3 font-medium text-slate-900">{sim.scenario}</td>
        <td className="px-4 py-3 text-slate-600">{sim.duration_hours}h</td>
        <td className="px-4 py-3 text-slate-600">{sim.num_nodes}</td>
        <td className="px-4 py-3 text-slate-600">{sim.num_links}</td>
        <td className="px-4 py-3 text-slate-500">{new Date(sim.calculated_at).toLocaleString()}</td>
        <td className="px-4 py-3">
          <button onClick={() => setExpanded((v) => !v)} className="text-xs text-indigo-600 hover:text-indigo-700">
            {expanded ? "Ocultar" : "Ver detalle"}
          </button>
        </td>
      </tr>
      {expanded && (
        <tr className="bg-slate-50">
          <td colSpan={6} className="px-4 py-3">
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              <div>
                <div className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-1">Presión por nudo (m.c.a.)</div>
                <table className="w-full text-xs">
                  <thead className="text-left text-slate-400">
                    <tr><th className="py-1">Nudo</th><th className="py-1">Mín</th><th className="py-1">Máx</th><th className="py-1">Prom</th></tr>
                  </thead>
                  <tbody>
                    {nodeEntries.map(([id, s]) => (
                      <tr key={id}>
                        <td className="py-0.5 font-medium text-slate-700">{id}</td>
                        <td className="py-0.5 tabular-nums">{s.min_pressure.toFixed(1)}</td>
                        <td className="py-0.5 tabular-nums">{s.max_pressure.toFixed(1)}</td>
                        <td className="py-0.5 tabular-nums">{s.avg_pressure.toFixed(1)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div>
                <div className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-1">Caudal por tubería (m³/s)</div>
                <table className="w-full text-xs">
                  <thead className="text-left text-slate-400">
                    <tr><th className="py-1">Tubería</th><th className="py-1">Mín</th><th className="py-1">Máx</th><th className="py-1">Prom</th></tr>
                  </thead>
                  <tbody>
                    {linkEntries.map(([id, s]) => (
                      <tr key={id}>
                        <td className="py-0.5 font-medium text-slate-700">{id}</td>
                        <td className="py-0.5 tabular-nums">{s.min_flowrate.toFixed(3)}</td>
                        <td className="py-0.5 tabular-nums">{s.max_flowrate.toFixed(3)}</td>
                        <td className="py-0.5 tabular-nums">{s.avg_flowrate.toFixed(3)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </td>
        </tr>
      )}
    </>
  );
}

function ModelMap({ modelId }: { modelId: string }) {
  const { data: geojson, isLoading } = useQuery({
    queryKey: ["network-model-geojson", modelId],
    queryFn: () => getNetworkModelGeojson(modelId),
  });

  const flows = (geojson?.features ?? [])
    .map((f) => (f.properties as Record<string, unknown> | null)?.max_flowrate)
    .filter((v): v is number => typeof v === "number")
    .map(Math.abs);
  const maxFlow = flows.length ? Math.max(...flows) : 0;

  return (
    <div className="pl-2">
      {isLoading && <p className="text-sm text-slate-500 mb-2">Cargando mapa...</p>}
      <NetworkMap
        geojson={geojson}
        height={360}
        emptyMessage="Este modelo no tiene coordenadas reales cargadas ([COORDINATES] del .inp) -- nada que georreferenciar."
        pointColor={(p) => pressureColor(typeof p.max_pressure === "number" ? p.max_pressure : null)}
        pointRadius={(p) => (p.node_type === "Reservoir" || p.node_type === "Tank" ? 10 : 6)}
        lineColor={(p) => flowColorScale(typeof p.max_flowrate === "number" ? p.max_flowrate : 0, maxFlow)}
        lineWeight={(p) => Math.max(2, Math.min(8, ((typeof p.diameter === "number" ? p.diameter : 100) / 40)))}
        popupHtml={(p, geomType) => {
          if (geomType === "Point") {
            return `<div style="font-size:12px"><strong>${p.id}</strong> (${p.node_type})<br/>` +
              `Elevación: ${p.elevation ?? "—"} m<br/>` +
              (typeof p.max_pressure === "number"
                ? `Presión: ${(p.min_pressure as number).toFixed(1)}–${(p.max_pressure as number).toFixed(1)} m.c.a.`
                : "Sin simular todavía") +
              `</div>`;
          }
          return `<div style="font-size:12px"><strong>${p.id}</strong> (${p.link_type})<br/>` +
            `Ø ${p.diameter ?? "—"} mm, ${p.length ?? "—"} m<br/>` +
            (typeof p.max_flowrate === "number"
              ? `Caudal: ${(p.min_flowrate as number).toFixed(3)}–${(p.max_flowrate as number).toFixed(3)} m³/s`
              : "Sin simular todavía") +
            `</div>`;
        }}
      />
      <div className="mt-2 flex flex-wrap gap-4 text-xs text-slate-500">
        <span><span className="inline-block w-2.5 h-2.5 rounded-full mr-1" style={{ background: "#3b82f6" }} />Presión alta</span>
        <span><span className="inline-block w-2.5 h-2.5 rounded-full mr-1" style={{ background: "#10b981" }} />Rango operativo</span>
        <span><span className="inline-block w-2.5 h-2.5 rounded-full mr-1" style={{ background: "#f59e0b" }} />Baja</span>
        <span><span className="inline-block w-2.5 h-2.5 rounded-full mr-1" style={{ background: "#ef4444" }} />Crítica (&lt;10 m.c.a.)</span>
      </div>
    </div>
  );
}

function ModelRow({ model }: { model: NetworkModel }) {
  const queryClient = useQueryClient();
  const [scenario, setScenario] = useState("base");
  const [error, setError] = useState<string | null>(null);
  const [showSims, setShowSims] = useState(false);
  const [showMap, setShowMap] = useState(false);

  const { data: sims } = useQuery({
    queryKey: ["network-model-simulations", model.model_id],
    queryFn: () => getNetworkModelSimulations(model.model_id),
    enabled: showSims,
  });

  const mutation = useMutation({
    mutationFn: () => simulateNetworkModel(model.model_id, scenario),
    onSuccess: () => {
      setError(null);
      setShowSims(true);
      queryClient.invalidateQueries({ queryKey: ["network-model-simulations", model.model_id] });
    },
    onError: (err) => setError(err instanceof ApiError ? err.message : "La simulación no convergió."),
  });

  return (
    <>
      <tr>
        <td className="px-4 py-3 font-medium text-slate-900">{model.name}</td>
        <td className="px-4 py-3 text-slate-500">v{model.version}</td>
        <td className="px-4 py-3 text-slate-500">{new Date(model.valid_from).toLocaleString()}</td>
        <td className="px-4 py-3">
          <div className="flex items-center gap-2">
            <input
              className="rounded-lg border border-slate-300 px-2 py-1 text-xs w-28"
              value={scenario}
              onChange={(e) => setScenario(e.target.value)}
              placeholder="escenario"
            />
            <button
              onClick={() => mutation.mutate()}
              disabled={mutation.isPending}
              className="rounded-lg bg-indigo-600 text-white text-xs font-semibold px-3 py-1.5 hover:bg-indigo-700 disabled:opacity-40"
            >
              Simular
            </button>
            <button onClick={() => setShowSims((v) => !v)} className="text-xs text-indigo-600 hover:text-indigo-700">
              {showSims ? "Ocultar corridas" : "Ver corridas"}
            </button>
            <button onClick={() => setShowMap((v) => !v)} className="text-xs text-indigo-600 hover:text-indigo-700">
              {showMap ? "Ocultar mapa" : "Ver mapa"}
            </button>
          </div>
          {error && <p className="text-xs text-red-600 mt-1">{error}</p>}
        </td>
      </tr>
      {showMap && (
        <tr>
          <td colSpan={4} className="px-4 pb-3">
            <ModelMap modelId={model.model_id} />
          </td>
        </tr>
      )}
      {showSims && (
        <tr>
          <td colSpan={4} className="px-4 pb-3">
            {sims && sims.length === 0 && (
              <div className="pl-2"><EmptyState message="Sin simulaciones registradas para este modelo todavía." /></div>
            )}
            {sims && sims.length > 0 && (
              <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white ml-2">
                <table className="w-full text-sm">
                  <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
                    <tr>
                      <th className="px-4 py-2">Escenario</th>
                      <th className="px-4 py-2">Duración</th>
                      <th className="px-4 py-2">Nudos</th>
                      <th className="px-4 py-2">Tuberías</th>
                      <th className="px-4 py-2">Calculada</th>
                      <th className="px-4 py-2"></th>
                    </tr>
                  </thead>
                  <tbody>
                    {sims.map((sim) => (
                      <SimulationRow key={sim.simulation_id} sim={sim} />
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </td>
        </tr>
      )}
    </>
  );
}

export function NetworkModelPage() {
  const { data: models, isLoading } = useQuery({
    queryKey: ["network-models"],
    queryFn: getNetworkModels,
    refetchInterval: 30_000,
  });

  return (
    <StagePage title="Modelado Hidráulico">
      <div className="mb-2 flex items-center justify-between">
        <h2 className="text-sm font-semibold text-slate-500 uppercase tracking-wide">Modelos EPANET (.inp)</h2>
        <UploadModelForm />
      </div>

      {isLoading && <p className="text-sm text-slate-500">Cargando...</p>}
      {models && models.length === 0 && (
        <EmptyState message="Sin modelos cargados todavía. Carga un archivo EPANET (.inp) para empezar a simular." />
      )}
      {models && models.length > 0 && (
        <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-4 py-3">Modelo</th>
                <th className="px-4 py-3">Versión</th>
                <th className="px-4 py-3">Cargado</th>
                <th className="px-4 py-3">Simular</th>
              </tr>
            </thead>
            <tbody>
              {models.map((model) => (
                <ModelRow key={model.model_id} model={model} />
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="mt-4 rounded-xl border border-indigo-100 bg-indigo-50/40 p-4 text-sm text-slate-600">
        <b className="text-slate-900">¿Qué motor corre por debajo?</b>{" "}
        Cada simulación resuelve el modelo con EPANET 2.2 (vía WNTR, el paquete de la EPA de EE. UU.) -- el mismo motor hidráulico que usan Bentley WaterGEMS/OpenFlows e Innovyze InfoWater. Presión (nudos) y caudal (tuberías) se calculan en toda la duración del modelo y se resumen en mínimo/máximo/promedio -- nunca un resultado fabricado si la red no converge.
      </div>
    </StagePage>
  );
}
