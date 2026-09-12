"""Motor de Modelado Hidraulico (Track B, Sprint B3, F39/F40,
`docs/07-track-b-alcance-funcional.md` SS5) -- carga y simula un modelo
EPANET (`.inp`) real via WNTR (Water Network Tool for Resilience, USEPA),
el mismo motor de simulacion (EPANET 2.2) que usan Bentley WaterGEMS/
OpenFlows e Innovyze InfoWater por debajo (SS3 del documento de alcance).
Logica pura sobre archivo -- sin BD, mismo principio que
`network_balance_engine.py`.

Nota de compatibilidad real: WNTR >= 1.3 requiere Python >= 3.10; el
toolchain de Nuitka del portafolio esta fijo en Python 3.9
(`feedback_no_source_on_server_nuitka`). Se fija `wntr==1.2.0` (ultima
version con wheel manylinux para cp39) en `requirements.txt` -- documentado
aca y en la bitacora, no un detalle silencioso.
"""

from __future__ import annotations

import tempfile
import uuid
from dataclasses import dataclass, field
from pathlib import Path

import wntr
from wntr.epanet.exceptions import EpanetException


class InvalidModelError(ValueError):
    """El archivo `.inp` no es un modelo EPANET valido -- nunca se guarda
    ni se simula un modelo que no carga."""


class SimulationFailedError(RuntimeError):
    """WNTR/EPANET no pudo resolver la simulacion (red no converge, datos
    hidraulicamente inconsistentes) -- se reporta el fallo real, nunca un
    resultado fabricado."""


@dataclass
class NodeStats:
    min_pressure: float
    max_pressure: float
    avg_pressure: float


@dataclass
class LinkStats:
    min_flowrate: float
    max_flowrate: float
    avg_flowrate: float


@dataclass
class SimulationSummary:
    duration_hours: float
    num_nodes: int
    num_links: int
    nodes: dict[str, NodeStats] = field(default_factory=dict)
    links: dict[str, LinkStats] = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Forma serializable a `jsonb` (`simulation_result.results`)."""
        return {
            "duration_hours": self.duration_hours,
            "num_nodes": self.num_nodes,
            "num_links": self.num_links,
            "nodes": {
                node_id: {"min_pressure": s.min_pressure, "max_pressure": s.max_pressure, "avg_pressure": s.avg_pressure}
                for node_id, s in self.nodes.items()
            },
            "links": {
                link_id: {"min_flowrate": s.min_flowrate, "max_flowrate": s.max_flowrate, "avg_flowrate": s.avg_flowrate}
                for link_id, s in self.links.items()
            },
        }


def load_model(inp_path: str) -> wntr.network.WaterNetworkModel:
    """Carga y valida un `.inp` real -- `InvalidModelError` si el archivo no
    es un modelo EPANET valido (sintaxis, referencias cruzadas rotas,
    etc.), nunca una excepcion cruda de WNTR sin traducir."""
    try:
        return wntr.network.WaterNetworkModel(inp_path)
    except EpanetException as exc:
        raise InvalidModelError(f"Modelo EPANET invalido: {exc}") from exc
    except Exception as exc:  # noqa: BLE001 -- WNTR tambien lanza ValueError/KeyError crudos en algunos parseos rotos
        raise InvalidModelError(f"No se pudo interpretar el archivo .inp: {exc}") from exc


def _simulate_wn(wn: wntr.network.WaterNetworkModel) -> SimulationSummary:
    """Corre `EpanetSimulator` sobre un `WaterNetworkModel` YA CARGADO (y
    opcionalmente modificado en memoria -- ver `calibrate_and_simulate`) y
    resume presion/caudal min/max/promedio. Lanza `SimulationFailedError`
    si la red no converge, nunca un resultado a medias silencioso.

    `EpanetSimulator.run_sim()` escribe archivos temporales (`.inp`/`.rpt`/
    `.bin`) al directorio de trabajo actual con el prefijo `temp` por
    defecto (hallazgo real de esta ronda -- ensuciaba el working tree del
    repo en las pruebas E2E) -- se fuerza un `file_prefix` unico bajo un
    directorio temporal propio, borrado siempre al terminar."""
    with tempfile.TemporaryDirectory(prefix="renfygrid_epanet_") as tmp_dir:
        file_prefix = str(Path(tmp_dir) / f"sim_{uuid.uuid4().hex}")
        try:
            sim = wntr.sim.EpanetSimulator(wn)
            results = sim.run_sim(file_prefix=file_prefix, convergence_error=True)
        except EpanetException as exc:
            raise SimulationFailedError(f"La simulacion no convergio: {exc}") from exc

    pressure = results.node["pressure"]
    flowrate = results.link["flowrate"]
    if pressure.empty or flowrate.empty:
        raise SimulationFailedError("La simulacion no produjo resultados (serie de tiempo vacia)")

    duration_hours = wn.options.time.duration / 3600.0

    return SimulationSummary(
        duration_hours=duration_hours,
        num_nodes=len(pressure.columns),
        num_links=len(flowrate.columns),
        nodes={
            node_id: NodeStats(
                min_pressure=float(pressure[node_id].min()),
                max_pressure=float(pressure[node_id].max()),
                avg_pressure=float(pressure[node_id].mean()),
            )
            for node_id in pressure.columns
        },
        links={
            link_id: LinkStats(
                min_flowrate=float(flowrate[link_id].min()),
                max_flowrate=float(flowrate[link_id].max()),
                avg_flowrate=float(flowrate[link_id].mean()),
            )
            for link_id in flowrate.columns
        },
    )


def run_simulation(inp_path: str) -> SimulationSummary:
    """Carga el `.inp` y corre una simulacion hidraulica real (sin
    calibrar) -- ver `_simulate_wn` para el detalle de la corrida."""
    wn = load_model(inp_path)
    return _simulate_wn(wn)


class CalibrationInputError(ValueError):
    """`real_losses_m3`/`period_days` invalidos para calibrar -- nunca se
    inventa una fuga sin un balance real detras."""


@dataclass
class CalibrationResult:
    """Resultado de calibrar el modelo con perdidas reales de un balance
    (`network_balance.real_losses`, Track B Sprint B4,
    `docs/07-track-b-alcance-funcional.md` SS5) -- tecnica de emisores por
    presion (estandar IWA/EPANET para representar fugas distribuidas): el
    volumen real de perdidas del periodo se reparte entre los nudos
    (proporcional a su demanda base, o parejo si ninguno tiene demanda
    base) y se calibra un emisor `q = C * P^n` por nudo usando la presion
    de una corrida SIN fugas como referencia -- despues se vuelve a
    simular CON los emisores calibrados."""

    real_losses_m3: float
    period_days: float
    target_leak_lps: float
    node_leak_lps: dict[str, float]
    skipped_nodes: list[str]
    simulation: SimulationSummary

    def to_dict(self) -> dict:
        return {
            "real_losses_m3": self.real_losses_m3,
            "period_days": self.period_days,
            "target_leak_lps": self.target_leak_lps,
            "node_leak_lps": self.node_leak_lps,
            "skipped_nodes": self.skipped_nodes,
            **self.simulation.to_dict(),
        }


def calibrate_and_simulate(inp_path: str, real_losses_m3: float, period_days: float) -> CalibrationResult:
    """B4: usa `network_balance.real_losses` como INSUMO real de
    calibracion (no solo una comparacion cosmetica) -- nunca "datos de
    ejemplo hardcodeados" en el escenario de simulacion.

    1. Corre una simulacion base SIN fugas para estimar la presion de
       cada nudo.
    2. Reparte el volumen real de perdidas del periodo entre los nudos,
       proporcional a su demanda base (si ningun nudo tiene demanda base
       declarada, se reparte parejo -- nunca 0 fugas por falta de dato).
    3. Calibra un emisor por nudo (`emitter_coefficient`) para que, a la
       presion base estimada, produzca su parte del caudal de fuga
       objetivo. Un nudo con presion base <= 0 (deposito/tanque, o un
       nudo sin presion positiva) se omite -- nunca se divide por 0/negativo.
    4. Vuelve a simular CON los emisores calibrados -- ese es el
       resultado final."""
    if real_losses_m3 <= 0 or period_days <= 0:
        raise CalibrationInputError(
            "real_losses_m3 y period_days deben ser positivos para calibrar -- "
            "sin un balance real con perdidas > 0 no hay nada que calibrar"
        )

    wn = load_model(inp_path)
    baseline = _simulate_wn(wn)

    exponent = wn.options.hydraulic.emitter_exponent or 0.5
    junction_names = wn.junction_name_list
    if not junction_names:
        raise CalibrationInputError("El modelo no tiene nudos de consumo (junctions) donde calibrar fugas")

    base_demands = {
        name: sum(ts.base_value for ts in wn.get_node(name).demand_timeseries_list)
        for name in junction_names
    }
    total_base_demand = sum(base_demands.values())

    target_leak_lps = (real_losses_m3 * 1000) / (period_days * 86400)

    node_leak_lps: dict[str, float] = {}
    skipped: list[str] = []
    for name in junction_names:
        share = (base_demands[name] / total_base_demand) if total_base_demand > 0 else (1.0 / len(junction_names))
        leak_lps = target_leak_lps * share
        pressure_stats = baseline.nodes.get(name)
        if pressure_stats is None or pressure_stats.avg_pressure <= 0:
            skipped.append(name)
            continue
        # WNTR guarda TODO internamente en SI (m3/s, metros) sin importar
        # las unidades declaradas en el .inp (aqui LPS) -- `emitter_coefficient`
        # asignado directo en Python (no via parseo de archivo) espera
        # m3/s, no L/s. Sin esta conversion la fuga calibrada queda 1000x
        # mas grande que la real (hallazgo real de esta ronda, visto en
        # vivo: la presion colapsaba a ~0 en vez de estabilizarse).
        leak_m3s = leak_lps / 1000.0
        coefficient = leak_m3s / (pressure_stats.avg_pressure ** exponent)
        wn.get_node(name).emitter_coefficient = coefficient
        node_leak_lps[name] = round(leak_lps, 4)

    # Reload fresco de nuevo: reusar el mismo `wn` ya simulado una vez con
    # WNTR a veces deja estado residual del solver -- recargar y volver a
    # aplicar los emisores calibrados es mas seguro que reusar el objeto.
    wn2 = load_model(inp_path)
    for name, coeff in ((n, wn.get_node(n).emitter_coefficient) for n in node_leak_lps):
        wn2.get_node(name).emitter_coefficient = coeff
    calibrated_summary = _simulate_wn(wn2)

    return CalibrationResult(
        real_losses_m3=real_losses_m3,
        period_days=period_days,
        target_leak_lps=round(target_leak_lps, 4),
        node_leak_lps=node_leak_lps,
        skipped_nodes=skipped,
        simulation=calibrated_summary,
    )


def _has_real_coordinates(coords: tuple[float, float] | list[float]) -> bool:
    """WNTR devuelve exactamente `(0, 0)` para un nudo sin `[COORDINATES]`
    real en el `.inp` -- nunca se pinta un marcador ahi (seria "null
    island", no un dato real)."""
    x, y = coords
    return not (x == 0 and y == 0)


def model_topology_geojson(inp_path: str, simulation: SimulationSummary | None = None) -> dict:
    """GeoJSON real del modelo (Track B, modulo de georreferenciacion,
    `docs/07-track-b-alcance-funcional.md` SS7) -- nudos como `Point`,
    tuberias como `LineString`, tomados de `[COORDINATES]` del `.inp` (no
    un layout de grafo inventado). Si se pasa una simulacion ya corrida,
    cada feature trae sus estadisticas reales de presion/caudal en
    `properties` -- si no, esas propiedades quedan ausentes, nunca en 0 o
    inventadas. Nudos/enlaces sin coordenadas reales se omiten (ver
    `_has_real_coordinates`) en vez de dibujarse en `(0, 0)`."""
    wn = load_model(inp_path)
    features: list[dict] = []

    for name in wn.node_name_list:
        node = wn.get_node(name)
        coords = node.coordinates
        if not _has_real_coordinates(coords):
            continue
        props: dict = {
            "id": name,
            "node_type": node.node_type,
            "elevation": float(getattr(node, "elevation", 0.0) or 0.0),
        }
        if simulation is not None and name in simulation.nodes:
            s = simulation.nodes[name]
            props["min_pressure"] = s.min_pressure
            props["max_pressure"] = s.max_pressure
            props["avg_pressure"] = s.avg_pressure
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [coords[0], coords[1]]},
            "properties": props,
        })

    for name in wn.link_name_list:
        link = wn.get_link(name)
        start = wn.get_node(link.start_node_name)
        end = wn.get_node(link.end_node_name)
        if not (_has_real_coordinates(start.coordinates) and _has_real_coordinates(end.coordinates)):
            continue
        props = {
            "id": name,
            "link_type": link.link_type,
            "start_node": link.start_node_name,
            "end_node": link.end_node_name,
            "diameter": float(getattr(link, "diameter", 0.0) or 0.0) or None,
            "length": float(getattr(link, "length", 0.0) or 0.0) or None,
        }
        if simulation is not None and name in simulation.links:
            s = simulation.links[name]
            props["min_flowrate"] = s.min_flowrate
            props["max_flowrate"] = s.max_flowrate
            props["avg_flowrate"] = s.avg_flowrate
        features.append({
            "type": "Feature",
            "geometry": {
                "type": "LineString",
                "coordinates": [
                    [start.coordinates[0], start.coordinates[1]],
                    [end.coordinates[0], end.coordinates[1]],
                ],
            },
            "properties": props,
        })

    return {"type": "FeatureCollection", "features": features}
