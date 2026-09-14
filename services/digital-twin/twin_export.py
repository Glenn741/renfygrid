"""Exportador de Gemelo Digital -> modelo EPANET real (Track B, Sprint B6,
F43, `docs/07-track-b-alcance-funcional.md` SS5) -- convierte el grafo de
`network_asset`+`asset_connectivity` de una zona en un archivo `.inp` real
que WNTR puede cargar y simular exactamente igual que uno cargado a mano
(reusa `model_service.register_model()`, mismo camino de validacion).
Logica pura sobre listas de dicts ya leidos de BD -- sin BD aca, mismo
principio que `network_balance_engine.py`/`network_model_engine.py`.

Criterio de mapeo activo -> elemento EPANET (documentado explicitamente,
nunca una regla implicita):

- `tank`   -> RESERVOIR (cabeza fija, `attributes.head_m` obligatorio --
             el catastro no rastrea nivel/volumen en el tiempo, mapear a
             TANK real seria fabricar datos que no existen).
- `valve`/`pump`/`meter`/`sensor` -> JUNCTION (nudo de paso; en esta v1
             NO se modela el comportamiento de control real de una
             valvula/bomba EPANET -- eso es una mejora futura, declarada,
             no una promesa incumplida en silencio).
- Un activo `pipe` que conecta EXACTAMENTE otros dos activos no-pipe
  describe las propiedades REALES de ese tramo (`attributes.diameter_mm`/
  `material`/`roughness`) -- se "contrae" en un enlace `PIPE` entre sus
  dos vecinos (asi es como un SIG real modela una tuberia: una linea
  entre dos nudos, no un tercer nudo intermedio).
- Una conexion DIRECTA entre dos activos no-pipe (sin un activo `pipe`
  describiendola) tambien genera un enlace `PIPE`, con un diametro/
  rugosidad GENERICO documentado (`DEFAULT_PIPE_DIAMETER_MM`/
  `DEFAULT_PIPE_ROUGHNESS`) -- nunca se omite el enlace, pero tampoco se
  inventa un diametro "real" que no existe.
- Todo nudo incluido debe tener geometria `Point` real (para
  `[COORDINATES]` y para calcular la longitud real de cada tuberia por
  Haversine) -- si falta, `MissingGeometryError` lista exactamente que
  activos, nunca se adivina una posicion.
- Un activo `pipe` con 0, 1, o mas de 2 conexiones es un error de
  topologia real -- `AmbiguousPipeConnectivityError`, nunca una
  suposicion silenciosa sobre a que conecta.
- Sin ningun `tank` en el grafo -> `NoSourceAssetError` (una red sin
  fuente no se puede simular, EPANET lo rechazaria igual)."""

from __future__ import annotations

import math
from dataclasses import dataclass, field

DEFAULT_PIPE_DIAMETER_MM = 150.0
DEFAULT_PIPE_ROUGHNESS = 120.0  # Hazen-Williams C, generico (fierro fundido/asbesto-cemento envejecido)


class NoSourceAssetError(ValueError):
    """El grafo no tiene ningun activo `tank` (unica fuente de cabeza fija
    soportada en esta v1) -- nada que simular."""


class MissingGeometryError(ValueError):
    """Uno o mas activos incluidos en el modelo no tienen `geometry` real
    -- nunca se inventa una posicion."""

    def __init__(self, asset_ids: list[str]):
        super().__init__(f"Activos sin geometria real, no se puede generar el modelo: {asset_ids}")
        self.asset_ids = asset_ids


class MissingTankHeadError(ValueError):
    """Un activo `tank` (mapeado a RESERVOIR, cabeza fija) no tiene
    `attributes.head_m` -- dato obligatorio, nunca se asume un valor."""

    def __init__(self, asset_id: str):
        super().__init__(f"El activo tank {asset_id} no tiene attributes.head_m (obligatorio para generar el modelo)")
        self.asset_id = asset_id


class AmbiguousPipeConnectivityError(ValueError):
    """Un activo `pipe` no tiene EXACTAMENTE 2 conexiones -- no hay forma
    honesta de "contraerlo" en un enlace entre dos vecinos."""

    def __init__(self, asset_id: str, connection_count: int):
        super().__init__(
            f"El activo pipe {asset_id} tiene {connection_count} conexion(es) -- "
            "se esperan exactamente 2 para representarlo como tramo entre dos nudos"
        )
        self.asset_id = asset_id


@dataclass
class _Edge:
    node_a: str
    node_b: str
    diameter_mm: float
    roughness: float
    source_pipe_asset_id: str | None = None


def _haversine_m(coord_a: list[float], coord_b: list[float]) -> float:
    """Distancia real entre dos `[lon, lat]` en metros (formula de
    Haversine) -- usada para la `Length` real de cada tuberia generada."""
    lon1, lat1, lon2, lat2 = coord_a[0], coord_a[1], coord_b[0], coord_b[1]
    r = 6_371_000.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return r * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _point_coords(asset: dict) -> list[float] | None:
    geom = asset.get("geometry")
    if not geom or geom.get("type") != "Point":
        return None
    coords = geom.get("coordinates")
    if not coords or len(coords) != 2:
        return None
    return coords


def export_to_inp(assets: list[dict], connectivity: list[dict], title: str = "Modelo generado desde el Gemelo Digital") -> str:
    """Construye el texto `.inp` real -- levanta un error CLARO en vez de
    adivinar cuando falta algo (fuente, geometria, topologia de un `pipe`).
    El resultado, cargado por WNTR, simula igual que un `.inp` escrito a
    mano (mismo camino de validacion/simulacion, `network_model_engine.py`)."""
    assets_by_id = {a["asset_id"]: a for a in assets}

    # Grado de cada activo dentro de este grafo (para detectar pipes mal conectados).
    neighbors: dict[str, list[str]] = {a["asset_id"]: [] for a in assets}
    for edge in connectivity:
        s, t = edge["source_asset_id"], edge["target_asset_id"]
        if s in neighbors and t in neighbors:
            neighbors[s].append(t)
            neighbors[t].append(s)

    pipe_ids = {a["asset_id"] for a in assets if a["type"] == "pipe"}
    non_pipe_assets = [a for a in assets if a["type"] != "pipe"]
    tanks = [a for a in non_pipe_assets if a["type"] == "tank"]
    if not tanks:
        raise NoSourceAssetError("El grafo no tiene ningun activo 'tank' -- no hay fuente de cabeza fija para simular")

    # Contraer cada `pipe` en un enlace entre sus dos vecinos no-pipe.
    edges: list[_Edge] = []
    handled_direct: set[tuple[str, str]] = set()
    for pipe_id in pipe_ids:
        conns = neighbors[pipe_id]
        if len(conns) != 2:
            raise AmbiguousPipeConnectivityError(pipe_id, len(conns))
        a, b = conns
        pipe_asset = assets_by_id[pipe_id]
        attrs = pipe_asset.get("attributes") or {}
        edges.append(_Edge(
            node_a=a, node_b=b,
            diameter_mm=float(attrs.get("diameter_mm", DEFAULT_PIPE_DIAMETER_MM)),
            roughness=float(attrs.get("roughness", DEFAULT_PIPE_ROUGHNESS)),
            source_pipe_asset_id=pipe_id,
        ))
        handled_direct.add(tuple(sorted((a, b))))

    # Conexiones directas entre no-pipes que NO pasan por un activo pipe -> diametro generico.
    for edge in connectivity:
        s, t = edge["source_asset_id"], edge["target_asset_id"]
        if s not in assets_by_id or t not in assets_by_id:
            continue
        if s in pipe_ids or t in pipe_ids:
            continue
        key = tuple(sorted((s, t)))
        if key in handled_direct:
            continue
        handled_direct.add(key)
        edges.append(_Edge(node_a=s, node_b=t, diameter_mm=DEFAULT_PIPE_DIAMETER_MM, roughness=DEFAULT_PIPE_ROUGHNESS))

    # Geometria real obligatoria para todo nudo incluido.
    missing_geom = [a["asset_id"] for a in non_pipe_assets if _point_coords(a) is None]
    if missing_geom:
        raise MissingGeometryError(missing_geom)

    # ── Construir las secciones del .inp ────────────────────────────────
    reservoir_ids = {a["asset_id"] for a in tanks}
    junctions = [a for a in non_pipe_assets if a["asset_id"] not in reservoir_ids]

    def node_label(asset_id: str) -> str:
        return f"N{asset_id[:8]}"

    lines: list[str] = [f"[TITLE]\n{title}\n"]

    lines.append("[JUNCTIONS]")
    lines.append(";ID              Elev        Demand      Pattern")
    for j in junctions:
        elevation = float((j.get("attributes") or {}).get("elevation_m", 0.0))
        lines.append(f" {node_label(j['asset_id']):<16} {elevation:<10} 0")
    lines.append("")

    lines.append("[RESERVOIRS]")
    lines.append(";ID              Head        Pattern")
    for t in tanks:
        attrs = t.get("attributes") or {}
        if "head_m" not in attrs:
            raise MissingTankHeadError(t["asset_id"])
        lines.append(f" {node_label(t['asset_id']):<16} {float(attrs['head_m'])}")
    lines.append("")

    lines.append("[PIPES]")
    lines.append(";ID              Node1           Node2           Length      Diameter    Roughness   MinorLoss   Status")
    for i, edge in enumerate(edges, start=1):
        coord_a = _point_coords(assets_by_id[edge.node_a])
        coord_b = _point_coords(assets_by_id[edge.node_b])
        length_m = max(1.0, round(_haversine_m(coord_a, coord_b)))
        lines.append(
            f" P{i:<15} {node_label(edge.node_a):<15} {node_label(edge.node_b):<15} "
            f"{length_m:<11} {edge.diameter_mm:<11} {edge.roughness:<11} 0           Open"
        )
    lines.append("")

    lines.append("[TIMES]")
    lines.append(" Duration            24:00")
    lines.append(" Hydraulic Timestep  1:00")
    lines.append(" Pattern Timestep    1:00")
    lines.append("")

    lines.append("[OPTIONS]")
    lines.append(" Units               LPS")
    lines.append(" Headloss            H-W")
    lines.append("")

    lines.append("[COORDINATES]")
    lines.append(";Node            X-Coord         Y-Coord")
    for asset in non_pipe_assets:
        coords = _point_coords(asset)
        lines.append(f" {node_label(asset['asset_id']):<16} {coords[0]}        {coords[1]}")
    lines.append("")

    lines.append("[END]\n")
    return "\n".join(lines)
