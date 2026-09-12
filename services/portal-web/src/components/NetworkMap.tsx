import { useEffect, useRef } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";

// Modulo de georreferenciacion (Track B, docs/07-track-b-alcance-funcional.md
// SS7) -- mismo patron que "Mapa de Deuda" de RenFlow
// (core/renflow/frontend/js/modules/map.js), revisado antes de construir
// esto: Leaflet + tiles de OpenStreetMap (sin API key), backend expone
// GeoJSON real (nunca HTML armado en el servidor), color/tamano de cada
// elemento derivado de una metrica real ya calculada (presion, caudal,
// NRW%) -- nunca un color fijo ni inventado. Componente generico: lo usan
// tanto Balance de Red (zonas, puntos) como Modelado Hidraulico (nudos +
// tuberias, puntos y lineas).

type GeoProps = Record<string, unknown>;

export interface NetworkMapProps {
  geojson: GeoJSON.FeatureCollection | undefined;
  height?: number;
  pointColor?: (props: GeoProps) => string;
  pointRadius?: (props: GeoProps) => number;
  lineColor?: (props: GeoProps) => string;
  lineWeight?: (props: GeoProps) => number;
  popupHtml?: (props: GeoProps, geometryType: string) => string;
  emptyMessage?: string;
}

const DEFAULT_CENTER: [number, number] = [4.6, -74.1]; // Colombia, si no hay datos aun
const DEFAULT_ZOOM = 6;

export function NetworkMap({
  geojson, height = 420, pointColor, pointRadius, lineColor, lineWeight, popupHtml, emptyMessage,
}: NetworkMapProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<L.Map | null>(null);
  const layerRef = useRef<L.LayerGroup | null>(null);

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;
    const map = L.map(containerRef.current).setView(DEFAULT_CENTER, DEFAULT_ZOOM);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution: "&copy; OpenStreetMap contributors", maxZoom: 19,
    }).addTo(map);
    layerRef.current = L.layerGroup().addTo(map);
    mapRef.current = map;

    const ro = new ResizeObserver(() => map.invalidateSize());
    ro.observe(containerRef.current);

    return () => {
      ro.disconnect();
      map.remove();
      mapRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    const layer = layerRef.current;
    if (!map || !layer) return;
    layer.clearLayers();
    if (!geojson || geojson.features.length === 0) return;

    const bounds: [number, number][] = [];

    for (const feature of geojson.features) {
      const props = (feature.properties ?? {}) as GeoProps;

      if (feature.geometry.type === "Point") {
        const [lon, lat] = feature.geometry.coordinates as [number, number];
        const color = pointColor ? pointColor(props) : "#185fa5";
        const radius = pointRadius ? pointRadius(props) : 8;
        const marker = L.circleMarker([lat, lon], {
          radius, color: "#fff", weight: 1.5, fillColor: color, fillOpacity: 0.9,
        });
        if (popupHtml) marker.bindPopup(popupHtml(props, "Point"));
        marker.addTo(layer);
        bounds.push([lat, lon]);
      } else if (feature.geometry.type === "LineString") {
        const coords = (feature.geometry.coordinates as [number, number][]).map(
          ([lon, lat]) => [lat, lon] as [number, number],
        );
        const color = lineColor ? lineColor(props) : "#64748b";
        const weight = lineWeight ? lineWeight(props) : 3;
        const line = L.polyline(coords, { color, weight, opacity: 0.85 });
        if (popupHtml) line.bindPopup(popupHtml(props, "LineString"));
        line.addTo(layer);
        coords.forEach((c) => bounds.push(c));
      }
    }

    if (bounds.length > 0) map.fitBounds(bounds, { padding: [24, 24] });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [geojson]);

  const isEmpty = !geojson || geojson.features.length === 0;

  return (
    <div className="relative rounded-xl overflow-hidden border border-slate-200" style={{ height }}>
      <div ref={containerRef} className="h-full w-full" />
      {isEmpty && (
        <div className="absolute inset-0 flex items-center justify-center bg-white/85 text-sm text-slate-500 pointer-events-none px-4 text-center">
          {emptyMessage ?? "Sin datos georreferenciados para mostrar."}
        </div>
      )}
    </div>
  );
}

// ── Utilidades de color compartidas (mismas bandas que las tablas) ──────────

export function pressureColor(mca: number | null | undefined): string {
  if (mca == null) return "#94a3b8";
  if (mca < 10) return "#ef4444";   // muy baja
  if (mca < 20) return "#f59e0b";
  if (mca < 60) return "#10b981";   // rango operativo tipico
  return "#3b82f6";                 // alta
}

export function flowColorScale(absFlow: number, maxAbsFlow: number): string {
  if (maxAbsFlow <= 0) return "#94a3b8";
  const t = Math.min(1, Math.abs(absFlow) / maxAbsFlow);
  // Escala azul (bajo) -> naranja (alto), mismo criterio que las capas tematicas de RenFlow.
  const stops: [number, number, number][] = [[0x93, 0xc5, 0xfd], [0xf5, 0x9e, 0x0b], [0xef, 0x44, 0x44]];
  const idx = t * (stops.length - 1);
  const lo = Math.min(stops.length - 2, Math.floor(idx));
  const hi = lo + 1;
  const frac = idx - lo;
  const lerp = (a: number, b: number) => Math.round(a + (b - a) * frac);
  const [r, g, b] = [0, 1, 2].map((i) => lerp(stops[lo][i], stops[hi][i]));
  const hex = (v: number) => v.toString(16).padStart(2, "0");
  return `#${hex(r)}${hex(g)}${hex(b)}`;
}

export function nrwColorForMap(pct: number | null | undefined, exceeds: boolean | null | undefined): string {
  if (pct == null) return "#94a3b8";
  if (exceeds === true) return "#ef4444";
  if (pct >= 20) return "#f59e0b";
  return "#10b981";
}
