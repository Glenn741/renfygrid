import { useEffect, useMemo, useRef } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import type { AdvisoryDashboard } from "../api";

// Mapa tematico de la ONG (Track E, 0047): cada operador es un simbolo cuyo
// tamano, color y forma salen de su ficha, segun las capas que declara el
// paquete de programa (`advisory_map_layer`). El color y la forma se asignan
// por el orden de las opciones del catalogo, no por su codigo: otro programa
// con otras opciones se ve igual de claro.

export const LAYER_COLORS = ["#2563eb", "#d97706", "#dc2626", "#7c3aed", "#0d9488", "#64748b"];
export const LAYER_SHAPES = ["circle", "square", "triangle", "diamond"] as const;
const NO_DATA_COLOR = "#94a3b8";

type Feature = AdvisoryDashboard["map"]["features"][number];
type Legend = AdvisoryDashboard["map"]["legend"];

export function shapeSvg(shape: string, size: number, fill: string, stroke = "#ffffff"): string {
  const s = size;
  const h = s / 2;
  const common = `fill="${fill}" fill-opacity="0.85" stroke="${stroke}" stroke-width="2"`;
  switch (shape) {
    case "square":
      return `<rect x="2" y="2" width="${s - 4}" height="${s - 4}" rx="2" ${common}/>`;
    case "triangle":
      return `<polygon points="${h},2 ${s - 2},${s - 2} 2,${s - 2}" ${common}/>`;
    case "diamond":
      return `<polygon points="${h},2 ${s - 2},${h} ${h},${s - 2} 2,${h}" ${common}/>`;
    case "none":
      return `<circle cx="${h}" cy="${h}" r="${h - 2}" fill="${fill}" fill-opacity="0.35" stroke="${fill}" stroke-width="2" stroke-dasharray="3 2"/>`;
    default:
      return `<circle cx="${h}" cy="${h}" r="${h - 2}" ${common}/>`;
  }
}

export function symbolFor(legend: Legend, color: string | null, shape: string | null) {
  const colorIdx = legend.color?.options.findIndex((o) => o.code === color) ?? -1;
  const shapeIdx = legend.shape?.options.findIndex((o) => o.code === shape) ?? -1;
  return {
    fill: colorIdx >= 0 ? LAYER_COLORS[colorIdx % LAYER_COLORS.length] : NO_DATA_COLOR,
    shape: shapeIdx >= 0 ? LAYER_SHAPES[shapeIdx % LAYER_SHAPES.length] : "none",
  };
}

function escapeHtml(text: string): string {
  return text.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c] ?? c);
}

export function OperatorsMap({ features, legend, height = 460, onSelect }: {
  features: Feature[]; legend: Legend; height?: number; onSelect?: (operatorId: string) => void;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<L.Map | null>(null);
  const layerRef = useRef<L.LayerGroup | null>(null);
  const onSelectRef = useRef(onSelect);
  onSelectRef.current = onSelect;
  const maxSize = useMemo(() => Math.max(1, ...features.map((f) => f.size ?? 0)), [features]);

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;
    const map = L.map(containerRef.current).setView([0, 0], 2);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution: "&copy; OpenStreetMap contributors", maxZoom: 19,
    }).addTo(map);
    layerRef.current = L.layerGroup().addTo(map);
    mapRef.current = map;
    const ro = new ResizeObserver(() => map.invalidateSize());
    ro.observe(containerRef.current);
    return () => { ro.disconnect(); map.remove(); mapRef.current = null; };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    const layer = layerRef.current;
    if (!map || !layer) return;
    layer.clearLayers();
    const bounds: L.LatLngExpression[] = [];
    // Los grandes primero: los chicos quedan encima y se pueden tocar.
    for (const f of [...features].sort((a, b) => (b.size ?? 0) - (a.size ?? 0))) {
      const size = Math.round(16 + 30 * Math.sqrt((f.size ?? 0) / maxSize));
      const sym = symbolFor(legend, f.color, f.shape);
      const icon = L.divIcon({
        className: "",
        html: `<svg width="${size}" height="${size}" viewBox="0 0 ${size} ${size}" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="${escapeHtml(f.name)}">${shapeSvg(sym.shape, size, sym.fill)}</svg>`,
        iconSize: [size, size],
        iconAnchor: [size / 2, size / 2],
      });
      const colorLabel = legend.color?.options.find((o) => o.code === f.color)?.label ?? "Sin dato";
      const shapeLabel = legend.shape?.options.find((o) => o.code === f.shape)?.label ?? "Sin dato";
      const marker = L.marker([f.lat, f.lon], { icon, title: f.name }).bindPopup(
        `<strong>${escapeHtml(f.name)}</strong><br/>${escapeHtml(legend.size?.label ?? "Tamaño")}: ${f.size ?? "sin dato"}` +
        `<br/>${escapeHtml(legend.color?.label ?? "")}: ${escapeHtml(colorLabel)}<br/>${escapeHtml(legend.shape?.label ?? "")}: ${escapeHtml(shapeLabel)}` +
        `<br/>Guías vistas en taller: ${f.stages_in_workshops.length ? f.stages_in_workshops.join(", ") : "ninguna"}` +
        `<br/>Formularios completos: ${f.complete_pct ?? 0} %`,
      );
      marker.on("dblclick", () => onSelectRef.current?.(f.operator_id));
      marker.addTo(layer);
      bounds.push([f.lat, f.lon]);
    }
    if (bounds.length === 1) map.setView(bounds[0], 12);
    else if (bounds.length > 1) map.fitBounds(L.latLngBounds(bounds), { padding: [40, 40], maxZoom: 13 });
  }, [features, legend, maxSize]);

  return <div ref={containerRef} style={{ height }} className="w-full rounded-lg border border-slate-200" role="region" aria-label="Mapa de operadores" />;
}

export function LegendSymbol({ shape, fill, size = 16 }: { shape: string; fill: string; size?: number }) {
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} aria-hidden dangerouslySetInnerHTML={{ __html: shapeSvg(shape, size, fill, "#334155") }} />
  );
}
