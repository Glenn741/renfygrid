"""Pruebas reales de twin_export -- sin BD, contra listas de assets/
conectividad ya armadas (como las devolveria asset_service). El .inp
generado se valida cargandolo/simulandolo con WNTR real (no un mock) via
network_model_engine, confirmando que un modelo generado desde el Gemelo
Digital simula igual que uno cargado a mano (criterio real de aceptacion
del Sprint B6)."""

from __future__ import annotations

import contextlib
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "network-model"))

from twin_export import (  # noqa: E402
    AmbiguousPipeConnectivityError,
    MissingGeometryError,
    MissingTankHeadError,
    NoSourceAssetError,
    export_to_inp,
)

from network_model_engine import load_model, run_simulation  # noqa: E402


def _tank_pipe_valve_graph():
    assets = [
        {"asset_id": "tank0001", "type": "tank", "attributes": {"head_m": 100},
         "geometry": {"type": "Point", "coordinates": [-74.0464, 4.6572]}},
        {"asset_id": "pipe0001", "type": "pipe", "attributes": {"diameter_mm": 250, "roughness": 140}, "geometry": None},
        {"asset_id": "valve001", "type": "valve", "attributes": {"elevation_m": 10},
         "geometry": {"type": "Point", "coordinates": [-74.053, 4.654]}},
    ]
    connectivity = [
        {"source_asset_id": "tank0001", "target_asset_id": "pipe0001", "connection_type": "flows_into"},
        {"source_asset_id": "pipe0001", "target_asset_id": "valve001", "connection_type": "flows_into"},
    ]
    return assets, connectivity


class ExportToInpTests(unittest.TestCase):
    def test_generates_a_real_loadable_model(self):
        assets, connectivity = _tank_pipe_valve_graph()
        inp_text = export_to_inp(assets, connectivity)
        with _tmp_inp(inp_text) as path:
            wn = load_model(path)
            self.assertEqual(set(wn.reservoir_name_list), {"Ntank0001"})
            self.assertEqual(set(wn.junction_name_list), {"Nvalve001"})
            self.assertEqual(len(wn.pipe_name_list), 1)

    def test_generated_model_simulates_exactly_like_a_hand_written_one(self):
        # Sin demanda, la presion en el nudo debe ser exactamente Head - Elevacion.
        assets, connectivity = _tank_pipe_valve_graph()
        inp_text = export_to_inp(assets, connectivity)
        with _tmp_inp(inp_text) as path:
            summary = run_simulation(path)
            self.assertAlmostEqual(summary.nodes["Nvalve001"].avg_pressure, 90.0, places=1)
            self.assertEqual(summary.num_nodes, 2)
            self.assertEqual(summary.num_links, 1)

    def test_pipe_length_is_real_haversine_distance(self):
        assets, connectivity = _tank_pipe_valve_graph()
        inp_text = export_to_inp(assets, connectivity)
        # Distancia real Bogota entre esas dos coordenadas ~800m (ver Sprint B1-2 en bitacora).
        self.assertIn("813", inp_text)

    def test_direct_connection_without_pipe_asset_uses_generic_diameter(self):
        assets = [
            {"asset_id": "tank0001", "type": "tank", "attributes": {"head_m": 50},
             "geometry": {"type": "Point", "coordinates": [-76.53, 3.45]}},
            {"asset_id": "meter001", "type": "meter", "attributes": {},
             "geometry": {"type": "Point", "coordinates": [-76.531, 3.451]}},
        ]
        connectivity = [{"source_asset_id": "tank0001", "target_asset_id": "meter001", "connection_type": "flows_into"}]
        inp_text = export_to_inp(assets, connectivity)
        self.assertIn("150.0", inp_text)  # DEFAULT_PIPE_DIAMETER_MM

    def test_raises_without_any_tank(self):
        assets = [{"asset_id": "valve001", "type": "valve", "attributes": {}, "geometry": {"type": "Point", "coordinates": [0, 0]}}]
        with self.assertRaises(NoSourceAssetError):
            export_to_inp(assets, [])

    def test_raises_when_tank_missing_head(self):
        assets = [{"asset_id": "tank0001", "type": "tank", "attributes": {}, "geometry": {"type": "Point", "coordinates": [0, 1]}}]
        with self.assertRaises(MissingTankHeadError):
            export_to_inp(assets, [])

    def test_raises_when_a_node_lacks_geometry(self):
        assets = [
            {"asset_id": "tank0001", "type": "tank", "attributes": {"head_m": 50}, "geometry": None},
        ]
        with self.assertRaises(MissingGeometryError):
            export_to_inp(assets, [])

    def test_raises_when_a_pipe_asset_has_wrong_connection_count(self):
        assets, connectivity = _tank_pipe_valve_graph()
        # Agregar un tercer vecino al pipe -- topologia ambigua.
        assets.append({"asset_id": "extra001", "type": "sensor", "attributes": {"elevation_m": 5},
                        "geometry": {"type": "Point", "coordinates": [-74.05, 4.65]}})
        connectivity.append({"source_asset_id": "pipe0001", "target_asset_id": "extra001", "connection_type": "flows_into"})
        with self.assertRaises(AmbiguousPipeConnectivityError):
            export_to_inp(assets, connectivity)


@contextlib.contextmanager
def _tmp_inp(text: str):
    fd, path = tempfile.mkstemp(suffix=".inp")
    try:
        with os.fdopen(fd, "w") as f:
            f.write(text)
        yield path
    finally:
        os.unlink(path)


if __name__ == "__main__":
    unittest.main()
