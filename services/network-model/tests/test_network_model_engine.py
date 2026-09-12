"""Pruebas reales de network_model_engine -- sin BD, contra archivos .inp
reales (EPANET), no mocks de WNTR. `fixtures/valid_net.inp` es una red real
minima (deposito + 2 nudos + tanque, 3 tuberias) escrita a mano en formato
EPANET estandar -- suficiente para que WNTR/EPANET la resuelva de verdad."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from network_model_engine import InvalidModelError, SimulationSummary, load_model, run_simulation  # noqa: E402

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


if __name__ == "__main__":
    unittest.main()
