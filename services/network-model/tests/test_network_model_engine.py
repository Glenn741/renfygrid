"""Pruebas reales de network_model_engine -- sin BD, contra archivos .inp
reales (EPANET), no mocks de WNTR. `fixtures/valid_net.inp` es una red real
minima (deposito + 2 nudos + tanque, 3 tuberias) escrita a mano en formato
EPANET estandar -- suficiente para que WNTR/EPANET la resuelva de verdad."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from network_model_engine import (  # noqa: E402
    CalibrationInputError,
    InvalidModelError,
    SimulationSummary,
    calibrate_and_simulate,
    load_model,
    model_topology_geojson,
    run_simulation,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures"
VALID_INP = str(FIXTURES / "valid_net.inp")
INVALID_INP = str(FIXTURES / "invalid_net.inp")


class LoadModelTests(unittest.TestCase):
    def test_loads_a_real_valid_inp_file(self):
        wn = load_model(VALID_INP)
        self.assertEqual(set(wn.junction_name_list), {"J1", "J2"})
        self.assertEqual(set(wn.reservoir_name_list), {"R1"})
        self.assertEqual(set(wn.tank_name_list), {"T1"})

    def test_raises_invalid_model_error_on_garbage_content(self):
        with self.assertRaises(InvalidModelError):
            load_model(INVALID_INP)

    def test_raises_invalid_model_error_on_missing_file(self):
        with self.assertRaises(InvalidModelError):
            load_model(str(FIXTURES / "no_existe.inp"))


class RunSimulationTests(unittest.TestCase):
    def test_runs_a_real_epanet_simulation_and_returns_stats(self):
        summary = run_simulation(VALID_INP)
        self.assertIsInstance(summary, SimulationSummary)
        self.assertEqual(summary.num_nodes, 4)  # J1, J2, R1, T1
        self.assertEqual(summary.num_links, 3)  # P1, P2, P3
        self.assertGreater(summary.duration_hours, 0)

    def test_pressure_stats_are_real_computed_values_not_fabricated(self):
        # Mismos numeros que la corrida manual verificada contra WNTR en
        # t=0h (el minimo de la serie -- el tanque T1 se llena durante las
        # 24h simuladas, subiendo la presion aguas arriba con el tiempo):
        # J1 = 78.39 mca, J2 = 41.56 mca -- ver docs/05-ejecucion.md.
        summary = run_simulation(VALID_INP)
        self.assertAlmostEqual(summary.nodes["J1"].min_pressure, 78.39, places=1)
        self.assertAlmostEqual(summary.nodes["J2"].min_pressure, 41.56, places=1)
        # El reservorio R1 tiene presion ~0 (nivel de referencia) -- ni un
        # valor inventado ni omitido de las estadisticas.
        self.assertAlmostEqual(summary.nodes["R1"].avg_pressure, 0.0, places=1)

    def test_flow_stats_present_for_every_pipe(self):
        summary = run_simulation(VALID_INP)
        self.assertEqual(set(summary.links.keys()), {"P1", "P2", "P3"})
        for stats in summary.links.values():
            self.assertGreater(stats.max_flowrate, 0)

    def test_to_dict_is_json_serializable_shape(self):
        summary = run_simulation(VALID_INP)
        as_dict = summary.to_dict()
        self.assertIn("nodes", as_dict)
        self.assertIn("links", as_dict)
        self.assertEqual(as_dict["nodes"]["J1"]["max_pressure"], summary.nodes["J1"].max_pressure)

    def test_raises_invalid_model_error_on_garbage_before_simulating(self):
        with self.assertRaises(InvalidModelError):
            run_simulation(INVALID_INP)


class ModelTopologyGeojsonTests(unittest.TestCase):
    """Track B, modulo de georreferenciacion (docs/07-track-b-alcance-funcional.md SS7)."""

    def test_returns_a_point_per_node_and_a_linestring_per_pipe(self):
        geojson = model_topology_geojson(VALID_INP)
        self.assertEqual(geojson["type"], "FeatureCollection")
        points = [f for f in geojson["features"] if f["geometry"]["type"] == "Point"]
        lines = [f for f in geojson["features"] if f["geometry"]["type"] == "LineString"]
        self.assertEqual({f["properties"]["id"] for f in points}, {"J1", "J2", "R1", "T1"})
        self.assertEqual({f["properties"]["id"] for f in lines}, {"P1", "P2", "P3"})

    def test_linestring_uses_real_endpoint_coordinates(self):
        geojson = model_topology_geojson(VALID_INP)
        p2 = next(f for f in geojson["features"] if f["properties"].get("id") == "P2")
        # P2 conecta J1(10,0) -> J2(110,0) en el fixture.
        self.assertEqual(p2["geometry"]["coordinates"], [[10.0, 0.0], [110.0, 0.0]])

    def test_without_simulation_no_pressure_or_flow_properties(self):
        geojson = model_topology_geojson(VALID_INP)
        j1 = next(f for f in geojson["features"] if f["properties"].get("id") == "J1")
        self.assertNotIn("max_pressure", j1["properties"])

    def test_with_simulation_includes_real_pressure_and_flow(self):
        summary = run_simulation(VALID_INP)
        geojson = model_topology_geojson(VALID_INP, summary)
        j1 = next(f for f in geojson["features"] if f["properties"].get("id") == "J1")
        p2 = next(f for f in geojson["features"] if f["properties"].get("id") == "P2")
        self.assertEqual(j1["properties"]["max_pressure"], summary.nodes["J1"].max_pressure)
        self.assertEqual(p2["properties"]["max_flowrate"], summary.links["P2"].max_flowrate)

    def test_node_without_real_coordinates_is_omitted_not_plotted_at_origin(self):
        # Un nudo agregado sin [COORDINATES] cae en (0,0) por defecto en WNTR
        # -- nunca debe aparecer como si fuera un dato real.
        import wntr
        wn = load_model(VALID_INP)
        wn.add_junction("J_SIN_COORD", base_demand=0, elevation=0)
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".inp", delete=False, mode="w") as f:
            wntr.network.write_inpfile(wn, f.name)
            path = f.name
        geojson = model_topology_geojson(path)
        ids = {f["properties"]["id"] for f in geojson["features"] if f["geometry"]["type"] == "Point"}
        self.assertNotIn("J_SIN_COORD", ids)


class CalibrateAndSimulateTests(unittest.TestCase):
    """Track B, Sprint B4 -- vinculo Modelo<->Balance
    (docs/07-track-b-alcance-funcional.md SS5): `network_balance.real_losses`
    real como insumo de calibracion (emisores por presion), no una
    comparacion cosmetica."""

    def test_raises_on_non_positive_real_losses(self):
        with self.assertRaises(CalibrationInputError):
            calibrate_and_simulate(VALID_INP, real_losses_m3=0, period_days=1)

    def test_raises_on_non_positive_period(self):
        with self.assertRaises(CalibrationInputError):
            calibrate_and_simulate(VALID_INP, real_losses_m3=100, period_days=0)

    def test_distributes_leak_proportional_to_base_demand(self):
        # J1 tiene demanda base 0, J2 tiene 10 LPS -- toda la fuga debe
        # asignarse a J2, nada a J1 (0/10 = 0% de participacion).
        result = calibrate_and_simulate(VALID_INP, real_losses_m3=864, period_days=1)
        self.assertAlmostEqual(result.target_leak_lps, 10.0, places=2)
        self.assertEqual(result.node_leak_lps["J1"], 0.0)
        self.assertAlmostEqual(result.node_leak_lps["J2"], 10.0, places=2)
        self.assertEqual(result.skipped_nodes, [])

    def test_calibrated_flow_increases_over_baseline_by_about_the_leak(self):
        baseline = run_simulation(VALID_INP)
        result = calibrate_and_simulate(VALID_INP, real_losses_m3=864, period_days=1)
        # El caudal promedio de P1 (tuberia troncal desde el deposito) debe
        # subir en un orden de magnitud consistente con los 10 LPS de fuga
        # agregados -- no explotar (bug real de esta ronda: sin convertir
        # LPS -> m3/s al fijar `emitter_coefficient`, la presion colapsaba).
        delta_m3s = result.simulation.links["P1"].avg_flowrate - baseline.links["P1"].avg_flowrate
        self.assertGreater(delta_m3s, 0.005)   # > 5 LPS de aumento real
        self.assertLess(delta_m3s, 0.015)      # pero no un orden de magnitud de mas
        # Las presiones siguen siendo fisicamente razonables (no colapsan a ~0).
        self.assertGreater(result.simulation.nodes["J2"].min_pressure, 10.0)

    def test_returns_calibrated_summary_type_and_dict_shape(self):
        result = calibrate_and_simulate(VALID_INP, real_losses_m3=864, period_days=1)
        self.assertIsInstance(result.simulation, SimulationSummary)
        as_dict = result.to_dict()
        self.assertIn("target_leak_lps", as_dict)
        self.assertIn("node_leak_lps", as_dict)
        self.assertIn("nodes", as_dict)  # de SimulationSummary.to_dict() aplanado


if __name__ == "__main__":
    unittest.main()
