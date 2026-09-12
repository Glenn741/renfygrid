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


def run_simulation(inp_path: str) -> SimulationSummary:
    """Corre una simulacion hidraulica real (EpanetSimulator, motor EPANET
    2.2) y resume presion (nodos) y caudal (enlaces) min/max/promedio en
    toda la duracion simulada -- nunca la serie completa cruda (evita un
    `jsonb` gigante por corrida; suficiente para un panel de KPIs). Lanza
    `SimulationFailedError` si la red no converge, nunca un resultado a
    medias silencioso.

    `EpanetSimulator.run_sim()` escribe archivos temporales (`.inp`/`.rpt`/
    `.bin`) al directorio de trabajo actual con el prefijo `temp` por
    defecto (hallazgo real de esta ronda -- ensuciaba el working tree del
    repo en las pruebas E2E) -- se fuerza un `file_prefix` unico bajo un
    directorio temporal propio, borrado siempre al terminar."""
    wn = load_model(inp_path)
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
