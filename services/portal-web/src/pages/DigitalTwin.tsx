import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ApiError,
  connectNetworkAssets,
  createNetworkAsset,
  getNetworkAssetDetail,
  getNetworkAssets,
  getNetworkAssetsGeojson,
  getNetworkZones,
  updateNetworkAssetStatus,
  type NetworkAsset,
} from "../api";
import { StagePage, EmptyState } from "../components/StagePage";
import { NetworkMap } from "../components/NetworkMap";

// Gemelo Digital -- Track B, Sprint B5 (docs/07-track-b-alcance-funcional.md
// SS5): inventario de activos de red (tuberías, válvulas, tanques, bombas,
// medidores, sensores) y su conectividad real. Catastro operativo mínimo,
// no un SIG completo (SS6) -- un cliente que ya tiene ArcGIS/QGIS sigue
// usándolo; esto vincula Balance de Red (zona) y, más adelante,
// Mantenimiento (B7) con activos reales.

const ASSET_TYPE_LABEL: Record<string, string> = {
  pipe: "Tubería", valve: "Válvula", tank: "Tanque", pump: "Bomba", meter: "Medidor", sensor: "Sensor",
};
const STATUS_LABEL: Record<string, string> = {
  operational: "Operativo", out_of_service: "Fuera de servicio", maintenance: "En mantenimiento",
};
const STATUS_COLOR: Record<string, string> = {
  operational: "#10b981", out_of_service: "#ef4444", maintenance: "#f59e0b",
};

function RegisterAssetForm() {
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [assetType, setAssetType] = useState("pipe");
  const [zoneId, setZoneId] = useState("");
  const [notes, setNotes] = useState("");
  const [lat, setLat] = useState("");
  const [lon, setLon] = useState("");
  const [error, setError] = useState<string | null>(null);

  const { data: zones } = useQuery({ queryKey: ["network-zones"], queryFn: getNetworkZones });

  const mutation = useMutation({
    mutationFn: () =>
      createNetworkAsset({
        type: assetType,
        zone_id: zoneId || null,
        attributes: notes ? { notes } : {},
        geometry: lat && lon ? { type: "Point", coordinates: [Number(lon), Number(lat)] } : null,
      }),
    onSuccess: () => {
      setError(null);
      setNotes(""); setLat(""); setLon(""); setZoneId("");
      setOpen(false);
      queryClient.invalidateQueries({ queryKey: ["network-assets"] });
      queryClient.invalidateQueries({ queryKey: ["network-assets-geojson"] });
    },
    onError: (err) => setError(err instanceof ApiError ? err.message : "No se pudo registrar el activo."),
  });

  if (!open) {
    return (
      <button onClick={() => setOpen(true)} className="rounded-lg bg-indigo-600 text-white text-xs font-semibold px-3 py-1.5 hover:bg-indigo-700">
        + Registrar activo
      </button>
    );
  }

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 mb-4">
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
        <div>
          <label className="block text-xs font-medium text-slate-500 mb-1">Tipo</label>
          <select className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm w-full bg-white" value={assetType} onChange={(e) => setAssetType(e.target.value)}>
            {Object.entries(ASSET_TYPE_LABEL).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
        </div>
        <div>
          <label className="block text-xs font-medium text-slate-500 mb-1">Zona (opcional)</label>
          <select className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm w-full bg-white" value={zoneId} onChange={(e) => setZoneId(e.target.value)}>
            <option value="">— Sin vincular —</option>
            {(zones ?? []).map((z) => <option key={z.zone_id} value={z.zone_id}>{z.name}</option>)}
          </select>
        </div>
        <div>
          <label className="block text-xs font-medium text-slate-500 mb-1">Notas (opcional)</label>
          <input className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm w-full" value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="material, diámetro, código externo del SIG..." />
        </div>
        <div>
          <label className="block text-xs font-medium text-slate-500 mb-1">Latitud (opcional)</label>
          <input type="number" className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm w-full" value={lat} onChange={(e) => setLat(e.target.value)} placeholder="para el mapa" />
        </div>
        <div>
          <label className="block text-xs font-medium text-slate-500 mb-1">Longitud (opcional)</label>
          <input type="number" className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm w-full" value={lon} onChange={(e) => setLon(e.target.value)} placeholder="para el mapa" />
        </div>
      </div>
      {error && <p className="text-sm text-red-600 mt-2">{error}</p>}
      <div className="mt-3 flex gap-2">
        <button onClick={() => mutation.mutate()} disabled={mutation.isPending} className="rounded-lg bg-indigo-600 text-white text-xs font-semibold px-3 py-1.5 hover:bg-indigo-700 disabled:opacity-40">
          Registrar
        </button>
        <button onClick={() => setOpen(false)} className="text-xs text-slate-500 hover:text-slate-700 px-2">Cancelar</button>
      </div>
    </div>
  );
}

function ConnectAssetsForm({ assets }: { assets: NetworkAsset[] }) {
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [sourceId, setSourceId] = useState("");
  const [targetId, setTargetId] = useState("");
  const [connectionType, setConnectionType] = useState("flows_into");
  const [error, setError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: () => connectNetworkAssets({ source_asset_id: sourceId, target_asset_id: targetId, connection_type: connectionType }),
    onSuccess: () => {
      setError(null);
      setOpen(false);
      queryClient.invalidateQueries({ queryKey: ["network-assets-geojson"] });
      queryClient.invalidateQueries({ queryKey: ["network-asset-detail"] });
    },
    onError: (err) => setError(err instanceof ApiError ? err.message : "No se pudo conectar los activos."),
  });

  if (!open) {
    return (
      <button onClick={() => setOpen(true)} className="text-xs text-indigo-600 hover:text-indigo-700">
        + Conectar activos
      </button>
    );
  }

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 mb-4">
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        <div>
          <label className="block text-xs font-medium text-slate-500 mb-1">Origen</label>
          <select className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm w-full bg-white" value={sourceId} onChange={(e) => setSourceId(e.target.value)}>
            <option value="">— Elegir —</option>
            {assets.map((a) => <option key={a.asset_id} value={a.asset_id}>{ASSET_TYPE_LABEL[a.type]} {a.asset_id.slice(0, 8)}</option>)}
          </select>
        </div>
        <div>
          <label className="block text-xs font-medium text-slate-500 mb-1">Destino</label>
          <select className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm w-full bg-white" value={targetId} onChange={(e) => setTargetId(e.target.value)}>
            <option value="">— Elegir —</option>
            {assets.map((a) => <option key={a.asset_id} value={a.asset_id}>{ASSET_TYPE_LABEL[a.type]} {a.asset_id.slice(0, 8)}</option>)}
          </select>
        </div>
        <div>
          <label className="block text-xs font-medium text-slate-500 mb-1">Tipo de conexión</label>
          <input className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm w-full" value={connectionType} onChange={(e) => setConnectionType(e.target.value)} placeholder="ej. flows_into" />
        </div>
      </div>
      {error && <p className="text-sm text-red-600 mt-2">{error}</p>}
      <div className="mt-3 flex gap-2">
        <button
          onClick={() => mutation.mutate()}
          disabled={!sourceId || !targetId || sourceId === targetId || mutation.isPending}
          className="rounded-lg bg-indigo-600 text-white text-xs font-semibold px-3 py-1.5 hover:bg-indigo-700 disabled:opacity-40"
        >
          Conectar
        </button>
        <button onClick={() => setOpen(false)} className="text-xs text-slate-500 hover:text-slate-700 px-2">Cancelar</button>
      </div>
    </div>
  );
}

function AssetRow({ asset }: { asset: NetworkAsset }) {
  const queryClient = useQueryClient();
  const [showDetail, setShowDetail] = useState(false);

  const { data: detail } = useQuery({
    queryKey: ["network-asset-detail", asset.asset_id],
    queryFn: () => getNetworkAssetDetail(asset.asset_id),
    enabled: showDetail,
  });

  const statusMutation = useMutation({
    mutationFn: (status: string) => updateNetworkAssetStatus(asset.asset_id, status),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["network-assets"] });
      queryClient.invalidateQueries({ queryKey: ["network-asset-detail", asset.asset_id] });
    },
  });

  const notes = (asset.attributes as Record<string, unknown>)?.notes as string | undefined;

  return (
    <>
      <tr>
        <td className="px-4 py-3 font-medium text-slate-900">{ASSET_TYPE_LABEL[asset.type] ?? asset.type}</td>
        <td className="px-4 py-3 text-slate-500 font-mono text-xs">{asset.asset_id.slice(0, 8)}</td>
        <td className="px-4 py-3 text-slate-600">{notes ?? "—"}</td>
        <td className="px-4 py-3">
          <select
            className="rounded-full px-2 py-0.5 text-xs font-semibold border-0"
            style={{ background: `${STATUS_COLOR[asset.status]}22`, color: STATUS_COLOR[asset.status] }}
            value={asset.status}
            onChange={(e) => statusMutation.mutate(e.target.value)}
          >
            {Object.entries(STATUS_LABEL).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
        </td>
        <td className="px-4 py-3 text-slate-500">v{asset.version}</td>
        <td className="px-4 py-3">
          <button onClick={() => setShowDetail((v) => !v)} className="text-xs text-indigo-600 hover:text-indigo-700">
            {showDetail ? "Ocultar" : "Conectividad"}
          </button>
        </td>
      </tr>
      {showDetail && (
        <tr className="bg-slate-50">
          <td colSpan={6} className="px-4 py-3">
            {detail && detail.connectivity.length === 0 && <EmptyState message="Sin conexiones registradas para este activo." />}
            {detail && detail.connectivity.length > 0 && (
              <ul className="text-xs text-slate-600 space-y-1">
                {detail.connectivity.map((c, i) => (
                  <li key={i}>
                    <span className="font-mono">{c.source_asset_id.slice(0, 8)}</span> → <span className="font-mono">{c.target_asset_id.slice(0, 8)}</span> ({c.connection_type})
                  </li>
                ))}
              </ul>
            )}
          </td>
        </tr>
      )}
    </>
  );
}

export function DigitalTwinPage() {
  const { data: assets, isLoading } = useQuery({ queryKey: ["network-assets"], queryFn: () => getNetworkAssets(), refetchInterval: 30_000 });
  const { data: geojson } = useQuery({ queryKey: ["network-assets-geojson"], queryFn: getNetworkAssetsGeojson, refetchInterval: 30_000 });

  const byType = useMemo(() => {
    const counts: Record<string, number> = {};
    (assets ?? []).forEach((a) => { counts[a.type] = (counts[a.type] ?? 0) + 1; });
    return counts;
  }, [assets]);
  const byStatus = useMemo(() => {
    const counts: Record<string, number> = {};
    (assets ?? []).forEach((a) => { counts[a.status] = (counts[a.status] ?? 0) + 1; });
    return counts;
  }, [assets]);

  return (
    <StagePage title="Gemelo Digital">
      {assets && (
        <div className="mb-6 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="rounded-xl border border-slate-200 bg-white p-4">
            <div className="text-2xl font-bold text-slate-900">{assets.length}</div>
            <div className="text-xs text-slate-500 mt-1">Activos registrados</div>
          </div>
          <div className="rounded-xl border border-slate-200 bg-white p-4">
            <div className={`text-2xl font-bold ${(byStatus.out_of_service ?? 0) > 0 ? "text-red-700" : "text-emerald-700"}`}>
              {byStatus.operational ?? 0}
            </div>
            <div className="text-xs text-slate-500 mt-1">Operativos</div>
          </div>
          <div className="rounded-xl border border-slate-200 bg-white p-4">
            <div className={`text-2xl font-bold ${(byStatus.out_of_service ?? 0) > 0 ? "text-red-700" : "text-slate-900"}`}>
              {byStatus.out_of_service ?? 0}
            </div>
            <div className="text-xs text-slate-500 mt-1">Fuera de servicio</div>
          </div>
          <div className="rounded-xl border border-slate-200 bg-white p-4">
            <div className="text-xs font-medium text-slate-500 mb-2">Por tipo</div>
            {Object.keys(byType).length === 0 ? (
              <div className="text-sm text-slate-400">Ninguno todavía</div>
            ) : (
              <div className="flex flex-wrap gap-1.5">
                {Object.entries(byType).map(([t, n]) => (
                  <span key={t} className="rounded-full bg-slate-100 px-2 py-0.5 text-xs font-semibold text-slate-600">
                    {ASSET_TYPE_LABEL[t] ?? t}: {n}
                  </span>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      <h2 className="text-sm font-semibold text-slate-500 uppercase tracking-wide mb-2">Mapa de activos</h2>
      <div className="mb-2">
        <NetworkMap
          geojson={geojson}
          height={340}
          emptyMessage="Ningún activo tiene latitud/longitud cargada todavía -- agrégalas al registrar un activo para verlo aquí."
          pointColor={(p) => STATUS_COLOR[p.status as string] ?? "#94a3b8"}
          pointRadius={() => 7}
          lineColor={() => "#64748b"}
          popupHtml={(p, geomType) => {
            if (geomType === "Point") {
              return `<div style="font-size:12px"><strong>${ASSET_TYPE_LABEL[p.asset_type as string] ?? p.asset_type}</strong><br/>Estado: ${STATUS_LABEL[p.status as string] ?? p.status}</div>`;
            }
            return `<div style="font-size:12px">${p.connection_type}</div>`;
          }}
        />
      </div>
      <div className="mb-6 flex flex-wrap gap-4 text-xs text-slate-500">
        <span><span className="inline-block w-2.5 h-2.5 rounded-full mr-1" style={{ background: STATUS_COLOR.operational }} />Operativo</span>
        <span><span className="inline-block w-2.5 h-2.5 rounded-full mr-1" style={{ background: STATUS_COLOR.maintenance }} />En mantenimiento</span>
        <span><span className="inline-block w-2.5 h-2.5 rounded-full mr-1" style={{ background: STATUS_COLOR.out_of_service }} />Fuera de servicio</span>
      </div>

      <div className="mb-2 flex items-center justify-between flex-wrap gap-2">
        <h2 className="text-sm font-semibold text-slate-500 uppercase tracking-wide">Activos</h2>
        <div className="flex gap-3">
          <ConnectAssetsForm assets={assets ?? []} />
          <RegisterAssetForm />
        </div>
      </div>
      {isLoading && <p className="text-sm text-slate-500">Cargando...</p>}
      {assets && assets.length === 0 && <EmptyState message="Sin activos registrados todavía. Registra uno para empezar el catastro." />}
      {assets && assets.length > 0 && (
        <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-4 py-3">Tipo</th>
                <th className="px-4 py-3">ID</th>
                <th className="px-4 py-3">Notas</th>
                <th className="px-4 py-3">Estado</th>
                <th className="px-4 py-3">Versión</th>
                <th className="px-4 py-3"></th>
              </tr>
            </thead>
            <tbody>
              {assets.map((asset) => <AssetRow key={asset.asset_id} asset={asset} />)}
            </tbody>
          </table>
        </div>
      )}

      <div className="mt-4 rounded-xl border border-indigo-100 bg-indigo-50/40 p-4 text-sm text-slate-600">
        <b className="text-slate-900">¿Qué es esto?</b>{" "}
        Un catastro operativo mínimo de activos de red (tuberías, válvulas, tanques, bombas, medidores, sensores) y su conectividad -- no reemplaza un SIG completo (ArcGIS/QGIS) si ya lo tienes. Vincula un activo a una zona de Balance de Red para tenerlo en el mismo contexto que su NRW/ILI.
      </div>
    </StagePage>
  );
}
