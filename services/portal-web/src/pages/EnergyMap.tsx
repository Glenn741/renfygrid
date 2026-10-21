import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import "leaflet.markercluster";
import "leaflet.markercluster/dist/MarkerCluster.css";
import {
  ApiError,
  deleteMapView,
  getFrontierMap,
  getMapViews,
  saveMapView,
  type MapDimension,
  type MapPoint,
  type MapViewConfig,
} from "../api";
import { AppShell } from "../components/AppShell";
import { Icon } from "../components/Icon";
import { appLocale } from "../catalog";

// Mapa tematico de fronteras (Track F, Q2.5, migracion 0051;
// docs/11-mapa-fronteras.md). Lo que hace, como lo hace el mercado:
//   - pintar por UNA variable a la vez, con la leyenda y su conteo (clic en
//     una categoria la oculta o la muestra);
//   - tamano por magnitud, en cinco rangos que salen de los datos;
//   - filtros por facetas con conteo cruzado (cada faceta cuenta con los
//     demas filtros aplicados);
//   - capas de excepcion superpuestas (anillo rojo);
//   - agrupamiento cuyo color muestra la composicion del grupo;
//   - ficha al pasar, clic a la hoja de vida, seleccion por area, lista
//     sincronizada exportable y vistas guardadas.
// Las variables y sus categorias llegan del servidor (`map_dimension`); esta
// pantalla no conoce ninguna.

const CARD = "rounded-xl border border-slate-200 bg-white p-4";
const INPUT = "w-full rounded-lg border border-slate-300 bg-white px-2.5 py-1.5 text-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500";
const BTN = "rounded-lg bg-indigo-600 px-3 py-1.5 text-sm font-semibold text-white hover:bg-indigo-700 disabled:bg-indigo-300";
const BTN2 = "rounded-lg border border-slate-300 px-2.5 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50";
const TH = "px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-slate-500";
const TD = "px-3 py-1.5 text-sm text-slate-700";
const NONE = "__none__";
// Colores: los de su tono cuando la categoria tiene tono en el catalogo; si
// no, una paleta categorica en el orden de las categorias.
const TONE_HEX: Record<string, string> = { success: "#10b981", warning: "#f59e0b", danger: "#ef4444", info: "#6366f1", neutral: "#94a3b8" };
const PALETTE = ["#2563eb", "#d97706", "#059669", "#db2777", "#7c3aed", "#0891b2", "#65a30d", "#ea580c", "#4f46e5", "#be123c", "#0d9488", "#a16207"];
const ALERT_RING = "#dc2626";

function errorText(err: unknown, fallback: string): string {
  return err instanceof ApiError ? err.message : fallback;
}

function valuesOf(p: MapPoint, index: number): string[] {
  const v = p.v[index];
  if (v === null || v === undefined || v === "") return [NONE];
  return Array.isArray(v) ? (v.length ? v.map(String) : [NONE]) : [String(v)];
}

function colorsFor(dim: MapDimension | undefined): Record<string, string> {
  const out: Record<string, string> = {};
  let i = 0;
  for (const c of dim?.categories ?? []) {
    if (c.code === NONE) out[c.code] = TONE_HEX.neutral;
    else if (c.tone) out[c.code] = TONE_HEX[c.tone];
    else out[c.code] = PALETTE[i++ % PALETTE.length];
  }
  return out;
}

function escapeHtml(text: string): string {
  return text.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c] ?? c);
}

/** Cinco rangos de tamano a partir de los quintiles de los datos visibles. */
function sizeScale(values: number[]): (v: number | null) => number {
  const sorted = values.filter((v) => Number.isFinite(v)).sort((a, b) => a - b);
  if (!sorted.length) return () => 6;
  const cuts = [0.2, 0.4, 0.6, 0.8].map((q) => sorted[Math.floor(q * (sorted.length - 1))]);
  return (v) => (v === null || !Number.isFinite(v) ? 4 : 4 + 2.5 * cuts.filter((c) => v > c).length);
}

interface Selection { south: number; west: number; north: number; east: number }

function FrontierLeafletMap({ points, paintIndex, colors, sizeIndex, alertIndexes, alerts, cluster, selection, onSelect, selecting, labelOf }: {
  points: MapPoint[]; paintIndex: number; colors: Record<string, string>; sizeIndex: number | null; alertIndexes: number[];
  alerts: Record<number, string[]>; cluster: boolean; selection: Selection | null; onSelect: (s: Selection | null) => void;
  selecting: boolean; labelOf: (index: number, code: string) => string;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const mapRef = useRef<L.Map | null>(null);
  const layerRef = useRef<L.Layer | null>(null);
  const selRef = useRef<L.Rectangle | null>(null);
  const fitted = useRef(false);
  const navigate = useNavigate();

  useEffect(() => {
    if (!ref.current || mapRef.current) return;
    mapRef.current = L.map(ref.current, { scrollWheelZoom: true, preferCanvas: true });
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", { attribution: "© OpenStreetMap", maxZoom: 19 }).addTo(mapRef.current);
    mapRef.current.setView([4.6, -74.1], 5);
    return () => { mapRef.current?.remove(); mapRef.current = null; };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    layerRef.current?.remove();
    const located = points.filter((p) => p.lat !== null && p.lon !== null);
    const scale = sizeIndex === null ? null : sizeScale(located.map((p) => Number(p.v[sizeIndex])));
    const markers: L.Marker[] = [];
    for (const p of located) {
      const code = valuesOf(p, paintIndex)[0];
      const fill = colors[code] ?? TONE_HEX.neutral;
      const r = scale ? scale(p.v[sizeIndex as number] === null ? null : Number(p.v[sizeIndex as number])) : 6;
      const flagged = alertIndexes.filter((i) => valuesOf(p, i).some((c) => alerts[i]?.includes(c)));
      const ring = flagged.length ? `<circle cx="${r + 3}" cy="${r + 3}" r="${r + 2}" fill="none" stroke="${ALERT_RING}" stroke-width="2.5"/>` : "";
      const size = 2 * r + 6;
      const icon = L.divIcon({
        className: "",
        iconSize: [size, size],
        iconAnchor: [size / 2, size / 2],
        html: `<svg width="${size}" height="${size}">${ring}<circle cx="${r + 3}" cy="${r + 3}" r="${r}" fill="${fill}" fill-opacity="0.9" stroke="#fff" stroke-width="1.5"/></svg>`,
      });
      const m = L.marker([p.lat as number, p.lon as number], { icon, keyboard: false }) as L.Marker & { _paint?: string; _alert?: boolean };
      m._paint = code;
      m._alert = flagged.length > 0;
      const flags = flagged.map((i) => `<div style="color:${ALERT_RING}">● ${escapeHtml(labelOf(-1 - i, ""))}</div>`).join("");
      m.bindTooltip(`<div style="font-size:12px;line-height:1.35"><b>${escapeHtml(p.code)}</b> · ${escapeHtml(p.name)}<br>${escapeHtml(p.customer)}${p.city ? ` · ${escapeHtml(p.city)}` : ""}<br><span style="color:${fill}">■</span> ${escapeHtml(labelOf(paintIndex, code))}${flags}</div>`, { direction: "top", offset: [0, -r] });
      m.on("click", () => navigate(`/energy/points/${p.id}`));
      markers.push(m);
    }
    let layer: L.Layer;
    if (cluster) {
      const group = L.markerClusterGroup({
        showCoverageOnHover: false,
        maxClusterRadius: 45,
        disableClusteringAtZoom: 13,
        chunkedLoading: true,
        iconCreateFunction: (c) => {
          const counts: Record<string, number> = {};
          let flaggedN = 0;
          for (const child of c.getAllChildMarkers() as (L.Marker & { _paint?: string; _alert?: boolean })[]) {
            const k = child._paint ?? NONE;
            counts[k] = (counts[k] ?? 0) + 1;
            if (child._alert) flaggedN += 1;
          }
          const total = c.getChildCount();
          let acc = 0;
          const stops = Object.entries(counts).sort((a, b) => b[1] - a[1]).map(([k, n]) => {
            const from = (acc / total) * 360;
            acc += n;
            return `${colors[k] ?? TONE_HEX.neutral} ${from}deg ${(acc / total) * 360}deg`;
          }).join(", ");
          const d = total < 50 ? 34 : total < 300 ? 42 : 50;
          return L.divIcon({
            className: "",
            iconSize: [d, d],
            // El numero rojo: cuantas fronteras del grupo estan en una capa de alerta activa.
            html: `<div title="${total} fronteras${flaggedN ? ` · ${flaggedN} con alerta` : ""}" style="position:relative;width:${d}px;height:${d}px;border-radius:50%;background:conic-gradient(${stops});display:flex;align-items:center;justify-content:center;box-shadow:0 1px 3px rgba(0,0,0,.35)"><div style="width:${d - 14}px;height:${d - 14}px;border-radius:50%;background:#fff;display:flex;align-items:center;justify-content:center;font:600 11px system-ui;color:#0f172a">${total}</div>${flaggedN ? `<div style="position:absolute;top:-6px;right:-8px;min-width:18px;height:18px;padding:0 4px;border-radius:9px;background:${ALERT_RING};color:#fff;font:700 10px/18px system-ui;text-align:center;box-shadow:0 0 0 2px #fff">${flaggedN}</div>` : ""}</div>`,
          });
        },
      });
      group.addLayers(markers);
      layer = group;
    } else {
      layer = L.layerGroup(markers);
    }
    layer.addTo(map);
    layerRef.current = layer;
    if (!fitted.current && located.length) {
      map.fitBounds(L.latLngBounds(located.map((p) => [p.lat as number, p.lon as number] as [number, number])), { padding: [20, 20], maxZoom: 12 });
      fitted.current = true;
    }
  }, [points, paintIndex, colors, sizeIndex, alertIndexes, alerts, cluster, navigate, labelOf]);

  // Seleccion por area: con el modo activo, arrastrar dibuja un rectangulo.
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    if (!selecting) { map.dragging.enable(); return; }
    map.dragging.disable();
    let start: L.LatLng | null = null;
    let rect: L.Rectangle | null = null;
    const down = (e: L.LeafletMouseEvent) => { start = e.latlng; };
    const move = (e: L.LeafletMouseEvent) => {
      if (!start) return;
      const b = L.latLngBounds(start, e.latlng);
      if (rect) rect.setBounds(b); else rect = L.rectangle(b, { color: "#4f46e5", weight: 2, fillOpacity: 0.08, dashArray: "4 3" }).addTo(map);
    };
    const up = (e: L.LeafletMouseEvent) => {
      if (!start) return;
      const b = L.latLngBounds(start, e.latlng);
      rect?.remove();
      start = null;
      rect = null;
      onSelect({ south: b.getSouth(), west: b.getWest(), north: b.getNorth(), east: b.getEast() });
    };
    map.on("mousedown", down);
    map.on("mousemove", move);
    map.on("mouseup", up);
    return () => { map.off("mousedown", down); map.off("mousemove", move); map.off("mouseup", up); map.dragging.enable(); rect?.remove(); };
  }, [selecting, onSelect]);

  useEffect(() => {
    const map = mapRef.current;
    selRef.current?.remove();
    selRef.current = null;
    if (map && selection) {
      selRef.current = L.rectangle([[selection.south, selection.west], [selection.north, selection.east]],
        { color: "#4f46e5", weight: 2, fillOpacity: 0.05 }).addTo(map);
    }
  }, [selection]);

  return <div ref={ref} className={`h-[560px] w-full rounded-lg border border-slate-200 ${selecting ? "cursor-crosshair" : ""}`} />;
}

function downloadCsv(name: string, rows: string[][]): void {
  const csv = rows.map((r) => r.map((c) => (/[",;\n]/.test(c) ? `"${c.replace(/"/g, '""')}"` : c)).join(";")).join("\n");
  const url = URL.createObjectURL(new Blob([`﻿${csv}`], { type: "text/csv;charset=utf-8" }));
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  URL.revokeObjectURL(url);
}

export function EnergyMapPage() {
  const queryClient = useQueryClient();
  const { data, isLoading, error } = useQuery({ queryKey: ["assets", "map"], queryFn: getFrontierMap, staleTime: 60_000 });
  const { data: views } = useQuery({ queryKey: ["assets", "map-views"], queryFn: getMapViews });
  const [paint, setPaint] = useState("calibration");
  const [size, setSize] = useState<string | null>(null);
  const [filters, setFilters] = useState<Record<string, string[]>>({});
  const [layers, setLayers] = useState<string[]>([]);
  const [cluster, setCluster] = useState(true);
  const [selecting, setSelecting] = useState(false);
  const [selection, setSelection] = useState<Selection | null>(null);
  const [openGroups, setOpenGroups] = useState<Record<string, boolean>>({});
  const [viewName, setViewName] = useState("");
  const [msg, setMsg] = useState<string | null>(null);
  const [page, setPage] = useState(0);
  const navigate = useNavigate();

  const dims = data?.dimensions ?? [];
  const index = useMemo(() => Object.fromEntries(dims.map((d, i) => [d.key, i])), [dims]);
  const categoryDims = dims.filter((d) => d.role === "category");
  const paintDim = dims[index[paint]] ?? categoryDims.find((d) => d.can_paint);
  const paintIndex = paintDim ? index[paintDim.key] : 0;
  const colors = useMemo(() => colorsFor(paintDim), [paintDim]);
  const labelMaps = useMemo(() => dims.map((d) => Object.fromEntries(d.categories.map((c) => [c.code, c.label]))), [dims]);
  const labelOf = useMemo(() => (i: number, code: string) => {
    if (i < 0) return dims[-1 - i]?.alert_label ?? "";
    return labelMaps[i]?.[code] ?? code;
  }, [dims, labelMaps]);

  const matches = useMemo(() => (p: MapPoint, except?: string) => {
    for (const [key, codes] of Object.entries(filters)) {
      if (key === except || !codes.length || index[key] === undefined) continue;
      if (!valuesOf(p, index[key]).some((c) => codes.includes(c))) return false;
    }
    if (selection && (p.lat === null || p.lon === null || p.lat < selection.south || p.lat > selection.north
      || p.lon < selection.west || p.lon > selection.east)) return false;
    return true;
  }, [filters, index, selection]);

  const shown = useMemo(() => (data?.points ?? []).filter((p) => matches(p)), [data, matches]);
  // Conteo cruzado: cada faceta cuenta con todos los filtros menos el suyo.
  const facetCounts = useMemo(() => {
    const out: Record<string, Record<string, number>> = {};
    for (const d of categoryDims) {
      const i = index[d.key];
      const counts: Record<string, number> = {};
      for (const p of data?.points ?? []) {
        if (!matches(p, d.key)) continue;
        for (const c of valuesOf(p, i)) counts[c] = (counts[c] ?? 0) + 1;
      }
      out[d.key] = counts;
    }
    return out;
  }, [data, categoryDims, index, matches]);

  const alertDims = dims.filter((d) => d.alert_codes && d.alert_codes.length);
  const alertIndexes = useMemo(() => layers.filter((k) => index[k] !== undefined).map((k) => index[k]), [layers, index]);
  const alerts = useMemo(() => Object.fromEntries(alertDims.map((d) => [index[d.key], d.alert_codes ?? []])), [alertDims, index]);
  const sizeIndex = size && index[size] !== undefined ? index[size] : null;
  const sizeDims = dims.filter((d) => d.role === "size");

  useEffect(() => setPage(0), [filters, selection]);

  const toggle = (key: string, code: string) => {
    const current = filters[key] ?? [];
    const next = current.includes(code) ? current.filter((c) => c !== code) : [...current, code];
    setFilters({ ...filters, [key]: next });
  };
  // La leyenda filtra el color actual: ocultar una categoria = filtrar las demas.
  const legendToggle = (code: string) => {
    const all = (paintDim?.categories ?? []).map((c) => c.code);
    const current = filters[paintDim?.key ?? ""]?.length ? filters[paintDim!.key] : all;
    const next = current.includes(code) ? current.filter((c) => c !== code) : [...current, code];
    setFilters({ ...filters, [paintDim!.key]: next.length === all.length ? [] : next });
  };
  const activeFilters = Object.entries(filters).filter(([, v]) => v.length);
  const config: MapViewConfig = { paint, size, filters: Object.fromEntries(activeFilters), layers };
  const applyView = (c: MapViewConfig) => { setPaint(c.paint); setSize(c.size); setFilters(c.filters ?? {}); setLayers(c.layers ?? []); setSelection(null); };

  const save = useMutation({
    mutationFn: () => saveMapView(viewName, config),
    onSuccess: () => { setViewName(""); setMsg("Vista guardada."); queryClient.invalidateQueries({ queryKey: ["assets", "map-views"] }); },
    onError: (err) => setMsg(errorText(err, "No se pudo guardar la vista.")),
  });
  const remove = useMutation({
    mutationFn: deleteMapView,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["assets", "map-views"] }),
  });

  const exportCsv = () => {
    const cats = categoryDims;
    const header = ["Código", "Frontera", "Cliente", "Ciudad", "Latitud", "Longitud", ...cats.map((d) => d.label)];
    const rows = shown.map((p) => [p.code, p.name, p.customer, p.city ?? "", String(p.lat ?? ""), String(p.lon ?? ""),
      ...cats.map((d) => valuesOf(p, index[d.key]).filter((c) => c !== NONE).map((c) => labelOf(index[d.key], c)).join(" | "))]);
    downloadCsv("fronteras-filtradas.csv", [header, ...rows]);
  };

  const groups = useMemo(() => {
    const out: { name: string; dims: MapDimension[] }[] = [];
    for (const d of categoryDims.filter((x) => x.can_filter)) {
      const g = out.find((x) => x.name === d.group);
      if (g) g.dims.push(d); else out.push({ name: d.group, dims: [d] });
    }
    return out;
  }, [categoryDims]);

  const kpi = (key: string, codes: string[]) => index[key] === undefined ? null
    : shown.filter((p) => valuesOf(p, index[key]).some((c) => codes.includes(c))).length;
  const PAGE = 100;

  return (
    <AppShell title="Mapa de fronteras">
      {isLoading && <p className="text-sm text-slate-500">Cargando el mapa…</p>}
      {error && <p className="text-sm text-red-700">{errorText(error, "No se pudo cargar el mapa.")}</p>}
      {data && (
        <div className="space-y-4">
          <div className="grid gap-4 xl:grid-cols-[320px_1fr]">
            {/* Panel de capas y filtros */}
            <aside className="space-y-3">
              <div className={CARD}>
                <label className="text-xs font-semibold uppercase tracking-wide text-slate-500">Pintar por
                  <select className={`${INPUT} mt-1`} value={paintDim?.key ?? ""} onChange={(e) => setPaint(e.target.value)}>
                    {Array.from(new Set(categoryDims.filter((d) => d.can_paint).map((d) => d.group))).map((g) => (
                      <optgroup key={g} label={g}>
                        {categoryDims.filter((d) => d.can_paint && d.group === g).map((d) => <option key={d.key} value={d.key}>{d.label}</option>)}
                      </optgroup>
                    ))}
                  </select>
                </label>
                {paintDim?.description && <p className="mt-1 text-xs text-slate-500">{paintDim.description}</p>}
                <ul className="mt-2 space-y-0.5" aria-label="Leyenda">
                  {paintDim?.categories.map((c) => {
                    const hidden = (filters[paintDim.key] ?? []).length > 0 && !(filters[paintDim.key] ?? []).includes(c.code);
                    return (
                      <li key={c.code}>
                        <button className={`flex w-full items-center gap-2 rounded px-1.5 py-1 text-left text-sm hover:bg-slate-50 ${hidden ? "opacity-40" : ""}`}
                          onClick={() => legendToggle(c.code)} title={hidden ? "Mostrar" : "Ocultar"}>
                          <span className="h-3 w-3 shrink-0 rounded-full" style={{ background: colors[c.code] }} />
                          <span className="min-w-0 flex-1 truncate">{c.label}</span>
                          <span className="tabular-nums text-xs text-slate-500">{(facetCounts[paintDim.key]?.[c.code] ?? 0).toLocaleString(appLocale())}</span>
                        </button>
                      </li>
                    );
                  })}
                </ul>
                <div className="mt-3 grid grid-cols-2 gap-2">
                  <label className="text-xs font-semibold uppercase tracking-wide text-slate-500">Tamaño por
                    <select className={`${INPUT} mt-1`} value={size ?? ""} onChange={(e) => setSize(e.target.value || null)}>
                      <option value="">Igual para todas</option>
                      {sizeDims.map((d) => <option key={d.key} value={d.key}>{d.label}</option>)}
                    </select>
                  </label>
                  <label className="mt-5 flex items-center gap-2 text-sm text-slate-700">
                    <input type="checkbox" checked={cluster} onChange={(e) => setCluster(e.target.checked)} /> Agrupar
                  </label>
                </div>
              </div>

              <div className={CARD}>
                <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">Capas de alerta</h3>
                <ul className="mt-1 space-y-0.5">
                  {alertDims.map((d) => {
                    const n = (d.alert_codes ?? []).reduce((acc, c) => acc + (facetCounts[d.key]?.[c] ?? 0), 0);
                    return (
                      <li key={d.key}>
                        <label className="flex cursor-pointer items-center gap-2 rounded px-1.5 py-1 text-sm hover:bg-slate-50">
                          <input type="checkbox" checked={layers.includes(d.key)} onChange={() => setLayers(layers.includes(d.key) ? layers.filter((k) => k !== d.key) : [...layers, d.key])} />
                          <span className="h-3 w-3 shrink-0 rounded-full border-2" style={{ borderColor: ALERT_RING }} />
                          <span className="min-w-0 flex-1">{d.alert_label}</span>
                          <span className="tabular-nums text-xs text-slate-500">{n.toLocaleString(appLocale())}</span>
                        </label>
                      </li>
                    );
                  })}
                </ul>
              </div>

              <div className={CARD}>
                <div className="flex items-center justify-between">
                  <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">Filtros</h3>
                  {activeFilters.length > 0 && <button className="text-xs font-semibold text-indigo-700" onClick={() => setFilters({})}>Quitar filtros</button>}
                </div>
                <div className="mt-1 space-y-2">
                  {groups.map((g) => (
                    <div key={g.name}>
                      <button className="flex w-full items-center justify-between py-1 text-left text-sm font-semibold text-slate-800"
                        onClick={() => setOpenGroups({ ...openGroups, [g.name]: !openGroups[g.name] })} aria-expanded={Boolean(openGroups[g.name])}>
                        {g.name}
                        <span className="flex items-center gap-1 text-xs font-normal text-indigo-700">
                          {g.dims.reduce((n, d) => n + (filters[d.key]?.length ? 1 : 0), 0) || ""}
                          <span className={`transition-transform ${openGroups[g.name] ? "rotate-90" : ""}`}><Icon name="expand" className="h-3.5 w-3.5" /></span>
                        </span>
                      </button>
                      {openGroups[g.name] && g.dims.map((d) => (
                        <fieldset key={d.key} className="mb-2 ml-1">
                          <legend className="text-xs font-medium text-slate-600">{d.label}</legend>
                          <div className="max-h-44 overflow-y-auto">
                            {d.categories.filter((c) => (facetCounts[d.key]?.[c.code] ?? 0) > 0 || (filters[d.key] ?? []).includes(c.code)).map((c) => (
                              <label key={c.code} className="flex cursor-pointer items-center gap-2 py-0.5 text-sm text-slate-700">
                                <input type="checkbox" checked={(filters[d.key] ?? []).includes(c.code)} onChange={() => toggle(d.key, c.code)} />
                                <span className="min-w-0 flex-1 truncate" title={c.label}>{c.label}</span>
                                <span className="tabular-nums text-xs text-slate-500">{(facetCounts[d.key]?.[c.code] ?? 0).toLocaleString(appLocale())}</span>
                              </label>
                            ))}
                          </div>
                        </fieldset>
                      ))}
                    </div>
                  ))}
                </div>
              </div>

              <div className={CARD}>
                <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">Vistas guardadas</h3>
                <ul className="mt-1 space-y-0.5">
                  {(views ?? []).map((v) => (
                    <li key={v.id} className="flex items-center gap-2">
                      <button className="min-w-0 flex-1 truncate rounded px-1.5 py-1 text-left text-sm text-indigo-700 hover:bg-indigo-50" onClick={() => applyView(v.config)}>{v.name}</button>
                      <button className="text-xs text-slate-400 hover:text-red-600" title="Borrar la vista" onClick={() => remove.mutate(v.id)}>✕</button>
                    </li>
                  ))}
                  {!views?.length && <li className="text-xs text-slate-500">Todavía no hay vistas. Arme una combinación y guárdela.</li>}
                </ul>
                <div className="mt-2 flex gap-2">
                  <input className={INPUT} value={viewName} onChange={(e) => setViewName(e.target.value)} placeholder="Nombre de la vista actual" />
                  <button className={BTN} disabled={!viewName.trim() || save.isPending} onClick={() => save.mutate()}>Guardar</button>
                </div>
                {msg && <p className="mt-1 text-xs text-slate-600">{msg}</p>}
              </div>
            </aside>

            {/* Mapa */}
            <section className="space-y-3">
              <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
                {[
                  ["Fronteras en el mapa", shown.length, `de ${data.total.toLocaleString(appLocale())}`],
                  ["Calibración vencida o sin registro", kpi("calibration", ["overdue", "missing"]), "de las mostradas"],
                  ["Sin reportar", kpi("comms", ["silent"]), data.comms_window_seconds ? `ventana de ${Math.round(data.comms_window_seconds / 3600)} h` : "ventana sin definir"],
                  ["Con PQR abierta", kpi("pqr_open", ["yes"]), "de las mostradas"],
                  ["En corte o suspendidas", kpi("commercial_status", ["disconnection", "suspended_debt"]), "estado comercial"],
                ].map(([label, value, hint]) => (
                  <div key={label as string} className="rounded-xl border border-slate-200 bg-white p-3">
                    <div className="text-[11px] font-medium uppercase tracking-wide text-slate-500">{label}</div>
                    <div className="text-2xl font-bold tabular-nums text-slate-900">{value === null ? "—" : (value as number).toLocaleString(appLocale())}</div>
                    <div className="text-xs text-slate-500">{hint}</div>
                  </div>
                ))}
              </div>
              <div className={CARD}>
                <div className="mb-2 flex flex-wrap items-center gap-2">
                  <button className={selecting ? BTN : BTN2} onClick={() => setSelecting(!selecting)}>
                    {selecting ? "Arrastre sobre el mapa para seleccionar…" : "Seleccionar un área"}
                  </button>
                  {selection && <button className={BTN2} onClick={() => setSelection(null)}>Quitar la selección</button>}
                  {activeFilters.length > 0 && (
                    <span className="text-xs text-slate-600">
                      Filtros: {activeFilters.map(([k, v]) => `${dims[index[k]]?.label} (${v.map((c) => labelOf(index[k], c)).join(", ")})`).join(" · ")}
                    </span>
                  )}
                  <span className="ml-auto text-xs text-slate-500">
                    {shown.filter((p) => p.lat === null).length ? `${shown.filter((p) => p.lat === null).length} sin coordenadas (solo en la lista)` : ""}
                  </span>
                </div>
                <FrontierLeafletMap points={shown} paintIndex={paintIndex} colors={colors} sizeIndex={sizeIndex} alertIndexes={alertIndexes}
                  alerts={alerts} cluster={cluster} selection={selection} onSelect={(s) => { setSelection(s); setSelecting(false); }}
                  selecting={selecting} labelOf={labelOf} />
                <p className="mt-2 text-xs text-slate-500">
                  Pase el cursor sobre una frontera para ver su ficha; clic para abrir su hoja de vida. Los grupos muestran en su borde cuántas
                  fronteras hay de cada color y, en rojo, cuántas están en una capa de alerta activa. El anillo rojo marca esas fronteras.
                </p>
              </div>
            </section>
          </div>

          <div className={`${CARD} overflow-x-auto p-0`}>
            <div className="flex items-center justify-between px-4 py-3">
              <h2 className="text-base font-semibold text-slate-900">Fronteras que cumplen el filtro{selection ? " y la selección" : ""}</h2>
              <button className={BTN2} disabled={!shown.length} onClick={exportCsv}>
                <span className="inline-flex items-center gap-1.5"><Icon name="download" className="h-4 w-4" />Exportar ({shown.length.toLocaleString(appLocale())})</span>
              </button>
            </div>
            <table className="w-full min-w-[56rem]">
              <thead className="bg-slate-50"><tr>
                <th className={TH}>Frontera</th><th className={TH}>Cliente</th><th className={TH}>Ciudad</th>
                <th className={TH}>{paintDim?.label}</th><th className={TH}>Alertas</th>
              </tr></thead>
              <tbody>
                {shown.slice(page * PAGE, (page + 1) * PAGE).map((p) => {
                  const flags = alertDims.filter((d) => valuesOf(p, index[d.key]).some((c) => d.alert_codes?.includes(c)));
                  return (
                    <tr key={p.id} className="cursor-pointer border-t border-slate-100 hover:bg-indigo-50/40" onClick={() => navigate(`/energy/points/${p.id}`)}>
                      <td className={TD}><span className="font-medium text-slate-900">{p.code}</span><div className="text-xs text-slate-500">{p.name}</div></td>
                      <td className={TD}>{p.customer}</td>
                      <td className={TD}>{p.city}</td>
                      <td className={TD}>
                        <span className="inline-flex items-center gap-1.5">
                          <span className="h-2.5 w-2.5 rounded-full" style={{ background: colors[valuesOf(p, paintIndex)[0]] }} />
                          {valuesOf(p, paintIndex).map((c) => labelOf(paintIndex, c)).join(", ")}
                        </span>
                      </td>
                      <td className={TD}>
                        <div className="flex flex-wrap gap-1">
                          {flags.map((d) => <span key={d.key} className="rounded-full bg-red-50 px-2 py-0.5 text-xs text-red-700">{d.alert_label}</span>)}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
            <div className="flex items-center justify-between border-t border-slate-100 px-4 py-2 text-xs text-slate-500">
              <span>{shown.length.toLocaleString(appLocale())} fronteras</span>
              {shown.length > PAGE && (
                <span className="flex items-center gap-2">
                  <button className={BTN2} disabled={page === 0} onClick={() => setPage(page - 1)}>Anterior</button>
                  {page + 1} de {Math.ceil(shown.length / PAGE)}
                  <button className={BTN2} disabled={(page + 1) * PAGE >= shown.length} onClick={() => setPage(page + 1)}>Siguiente</button>
                </span>
              )}
            </div>
          </div>
          <p className="text-xs text-slate-500">
            El tipo de cliente, el estado comercial y las PQR se cargan con la plantilla de{" "}
            <Link className="text-indigo-700 underline" to="/energy/points">Fronteras comerciales</Link> o desde la hoja de vida de cada frontera.
          </p>
        </div>
      )}
    </AppShell>
  );
}

