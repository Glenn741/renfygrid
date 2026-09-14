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
    balance_check_pct,
    bottom_up_real_losses_from_mnf,
    compute_top_down_real_losses,
    infrastructure_leakage_index,
    non_revenue_water,
    non_revenue_water_pct,
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


class NonRevenueWaterPctTests(unittest.TestCase):
    def test_pct_of_system_input_volume(self):
        inputs = WaterBalanceInputs(system_input_volume=1000, billed_metered_consumption=750)
        self.assertAlmostEqual(non_revenue_water_pct(inputs), 25.0)

    def test_none_when_system_input_volume_is_zero(self):
        inputs = WaterBalanceInputs(system_input_volume=0)
        self.assertIsNone(non_revenue_water_pct(inputs))

    def test_none_when_system_input_volume_is_negative(self):
        inputs = WaterBalanceInputs(system_input_volume=-5)
        self.assertIsNone(non_revenue_water_pct(inputs))


class BalanceCheckPctTests(unittest.TestCase):
    def test_zero_when_components_sum_to_system_input_volume(self):
        inputs = WaterBalanceInputs(
            system_input_volume=1000, billed_metered_consumption=700, billed_unbilled_consumption=50,
            unbilled_authorized_consumption=20, apparent_losses=30, real_losses=200,
        )
        self.assertAlmostEqual(balance_check_pct(inputs), 0.0)

    def test_positive_when_components_undercount_system_input_volume(self):
        inputs = WaterBalanceInputs(system_input_volume=1000, billed_metered_consumption=700)
        self.assertAlmostEqual(balance_check_pct(inputs), 30.0)

    def test_none_when_system_input_volume_is_zero(self):
        inputs = WaterBalanceInputs(system_input_volume=0)
        self.assertIsNone(balance_check_pct(inputs))


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


class ComputeTopDownRealLossesTests(unittest.TestCase):
    """Sprint B2: metodo Top-Down real (AWWA M36) -- perdidas reales como
    RESIDUAL del balance, nunca medidas directo."""

    def test_residual_equals_siv_minus_the_four_known_components(self):
        result = compute_top_down_real_losses(
            system_input_volume=10000, billed_metered_consumption=7000,
            billed_unbilled_consumption=200, unbilled_authorized_consumption=100, apparent_losses=300,
        )
        self.assertAlmostEqual(result, 2400.0)  # 10000 - 7000 - 200 - 100 - 300

    def test_defaults_to_siv_when_no_other_component_declared(self):
        self.assertAlmostEqual(compute_top_down_real_losses(system_input_volume=5000), 5000.0)

    def test_none_when_siv_is_zero_or_negative(self):
        self.assertIsNone(compute_top_down_real_losses(system_input_volume=0))
        self.assertIsNone(compute_top_down_real_losses(system_input_volume=-10))

    def test_negative_residual_is_not_clamped_real_data_signal(self):
        # Componentes declarados EXCEDEN el SIV -- dato inconsistente real,
        # nunca se esconde recortando a 0.
        result = compute_top_down_real_losses(system_input_volume=1000, billed_metered_consumption=1200)
        self.assertAlmostEqual(result, -200.0)


class BottomUpRealLossesFromMnfTests(unittest.TestCase):
    """Sprint B2: metodo Bottom-Up real (IWA) -- perdidas reales medidas/
    estimadas directo por Caudal Minimo Nocturno, no como residual."""

    def test_real_volume_from_mnf_ndf_and_period(self):
        # NNF = 10 - 3 = 7 LPS; tasa promedio = 7*1.8 = 12.6 LPS;
        # volumen = 12.6 * 30 * 86400 / 1000 = 32659.2 m3.
        result = bottom_up_real_losses_from_mnf(
            minimum_night_flow_lps=10, legitimate_night_use_lps=3, night_day_factor=1.8, period_days=30,
        )
        self.assertAlmostEqual(result, 32659.2, places=1)

    def test_none_when_period_is_zero_or_negative(self):
        self.assertIsNone(bottom_up_real_losses_from_mnf(10, 3, 1.8, period_days=0))

    def test_none_when_legitimate_use_exceeds_mnf(self):
        # Mas "consumo legitimo" declarado que flujo medido -- dato de
        # entrada inconsistente, nunca una fuga negativa fabricada.
        self.assertIsNone(bottom_up_real_losses_from_mnf(
            minimum_night_flow_lps=5, legitimate_night_use_lps=8, night_day_factor=1.8, period_days=30,
        ))

    def test_all_inputs_are_required_no_hidden_default_for_ndf(self):
        import inspect
        sig = inspect.signature(bottom_up_real_losses_from_mnf)
        for name in ("minimum_night_flow_lps", "legitimate_night_use_lps", "night_day_factor", "period_days"):
            self.assertEqual(sig.parameters[name].default, inspect.Parameter.empty, f"{name} no deberia tener default")


if __name__ == "__main__":
    unittest.main()
