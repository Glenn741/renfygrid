"""Pruebas puras de network_balance_engine -- sin BD, logica de formulas del
estandar IWA (docs/07-track-b-alcance-funcional.md SS1)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from network_balance_engine import (
    WaterBalanceInputs,
    ZoneInfrastructure,
    infrastructure_leakage_index,
    non_revenue_water,
    unavoidable_annual_real_losses_liters_per_day,
    water_losses,
)


class NonRevenueWaterTests(unittest.TestCase):
    def test_nrw_excludes_billed_metered_and_unbilled(self):
        inputs = WaterBalanceInputs(system_input_volume=1000, billed_metered_consumption=700, billed_unbilled_consumption=50)
        self.assertEqual(non_revenue_water(inputs), 250)

    def test_unbilled_authorized_consumption_is_not_subtracted_from_nrw(self):
        # El agua autorizada no facturada (hidrantes, lavado) no genera
        # ingreso pero el estandar la deja FUERA de NRW a proposito.
        with_unbilled_authorized = WaterBalanceInputs(system_input_volume=1000, billed_metered_consumption=700, unbilled_authorized_consumption=100)
        without = WaterBalanceInputs(system_input_volume=1000, billed_metered_consumption=700)
        self.assertEqual(non_revenue_water(with_unbilled_authorized), non_revenue_water(without))


class WaterLossesTests(unittest.TestCase):
    def test_losses_is_apparent_plus_real(self):
        inputs = WaterBalanceInputs(system_input_volume=1000, apparent_losses=30, real_losses=120)
        self.assertEqual(water_losses(inputs), 150)


class UarlTests(unittest.TestCase):
    def test_uarl_with_all_three_required_inputs(self):
        zone = ZoneInfrastructure(network_length_km=100, num_connections=5000, avg_pressure_mca=40)
        uarl = unavoidable_annual_real_losses_liters_per_day(zone)
        # (18*100 + 0.8*5000 + 25*0) * 40 = (1800 + 4000) * 40 = 232000
        self.assertAlmostEqual(uarl, 232000.0)

    def test_uarl_includes_optional_service_connection_length(self):
        zone = ZoneInfrastructure(network_length_km=100, num_connections=5000, avg_pressure_mca=40, avg_service_connection_length_km=10)
        uarl = unavoidable_annual_real_losses_liters_per_day(zone)
        # (1800 + 4000 + 25*10) * 40 = 6050 * 40 = 242000
        self.assertAlmostEqual(uarl, 242000.0)

    def test_uarl_is_none_without_mains_length(self):
        zone = ZoneInfrastructure(num_connections=5000, avg_pressure_mca=40)
        self.assertIsNone(unavoidable_annual_real_losses_liters_per_day(zone))

    def test_uarl_is_none_without_connections(self):
        zone = ZoneInfrastructure(network_length_km=100, avg_pressure_mca=40)
        self.assertIsNone(unavoidable_annual_real_losses_liters_per_day(zone))

    def test_uarl_is_none_without_pressure(self):
        zone = ZoneInfrastructure(network_length_km=100, num_connections=5000)
        self.assertIsNone(unavoidable_annual_real_losses_liters_per_day(zone))


class InfrastructureLeakageIndexTests(unittest.TestCase):
    def test_ili_computed_with_complete_zone_infrastructure(self):
        zone = ZoneInfrastructure(network_length_km=100, num_connections=5000, avg_pressure_mca=40)
        # UARL = 232000 L/dia. real_losses = 6960 m3 en un periodo de 30 dias -> CARL = 6960000/30 = 232000 L/dia.
        inputs = WaterBalanceInputs(system_input_volume=10000, real_losses=6960)
        ili = infrastructure_leakage_index(inputs, zone, period_days=30)
        self.assertAlmostEqual(ili, 1.0)

    def test_ili_is_none_without_zone_infrastructure(self):
        zone = ZoneInfrastructure()
        inputs = WaterBalanceInputs(system_input_volume=10000, real_losses=500)
        self.assertIsNone(infrastructure_leakage_index(inputs, zone, period_days=30))

    def test_ili_is_none_with_zero_or_negative_period_days(self):
        zone = ZoneInfrastructure(network_length_km=100, num_connections=5000, avg_pressure_mca=40)
        inputs = WaterBalanceInputs(system_input_volume=10000, real_losses=500)
        self.assertIsNone(infrastructure_leakage_index(inputs, zone, period_days=0))

    def test_higher_real_losses_gives_higher_ili(self):
        zone = ZoneInfrastructure(network_length_km=100, num_connections=5000, avg_pressure_mca=40)
        low = infrastructure_leakage_index(WaterBalanceInputs(system_input_volume=10000, real_losses=1000), zone, period_days=30)
        high = infrastructure_leakage_index(WaterBalanceInputs(system_input_volume=10000, real_losses=5000), zone, period_days=30)
        self.assertLess(low, high)


if __name__ == "__main__":
    unittest.main()
