"""Pruebas puras de vee_engine.validate_reading -- sin BD, sin mocks de red
(a diferencia de hes-adapter-dlms, aca la logica no toca ningun protocolo
externo, asi que se prueba directo)."""

from __future__ import annotations

import math
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vee_engine import Gap, InsufficientHistoryError, detect_gaps, estimate_gap, validate_reading


RANGE_RULE = {"id": "rule-1", "type": "range", "params": {"channel": "active_energy", "min": 0, "max": 10000}, "priority": 100}
CONSISTENCY_RULE = {
    "id": "rule-consistency",
    "type": "channel_consistency",
    "params": {"channel": "reactive_energy", "reference_channel": "active_energy", "min_ratio": 0.0, "max_ratio": 1.0},
    "priority": 100,
}


class ValidateReadingTests(unittest.TestCase):
    def test_value_within_range_is_valid_and_traces_the_rule(self):
        result = validate_reading(5000, "active_energy", [RANGE_RULE])
        self.assertTrue(result.is_valid)
        self.assertEqual(result.vee_rule_id, "rule-1")

    def test_value_above_max_is_invalid(self):
        result = validate_reading(99999, "active_energy", [RANGE_RULE])
        self.assertFalse(result.is_valid)
        self.assertEqual(result.vee_rule_id, "rule-1")
        self.assertIn("max", result.notes)

    def test_value_below_min_is_invalid(self):
        result = validate_reading(-1, "active_energy", [RANGE_RULE])
        self.assertFalse(result.is_valid)
        self.assertIn("min", result.notes)

    def test_no_rule_for_channel_passes_without_a_traceable_rule(self):
        result = validate_reading(5000, "reactive_energy", [RANGE_RULE])
        self.assertTrue(result.is_valid)
        self.assertIsNone(result.vee_rule_id)

    def test_nan_is_invalid_format_regardless_of_range(self):
        result = validate_reading(math.nan, "active_energy", [RANGE_RULE])
        self.assertFalse(result.is_valid)
        self.assertIsNone(result.vee_rule_id)
        self.assertIn("formato", result.notes)

    def test_non_numeric_value_is_invalid_format(self):
        result = validate_reading("not-a-number", "active_energy", [RANGE_RULE])
        self.assertFalse(result.is_valid)

    def test_lowest_priority_number_wins_when_two_range_rules_overlap(self):
        loose_rule = {"id": "rule-loose", "type": "range", "params": {"channel": "active_energy", "min": -1000, "max": 1000000}, "priority": 200}
        strict_rule = {"id": "rule-strict", "type": "range", "params": {"channel": "active_energy", "min": 0, "max": 100}, "priority": 10}

        result = validate_reading(500, "active_energy", [loose_rule, strict_rule])

        self.assertFalse(result.is_valid)
        self.assertEqual(result.vee_rule_id, "rule-strict")

    def test_channel_consistency_within_ratio_is_valid_and_traces_the_rule(self):
        result = validate_reading(60, "reactive_energy", [CONSISTENCY_RULE], reference_value=100)
        self.assertTrue(result.is_valid)
        self.assertEqual(result.vee_rule_id, "rule-consistency")

    def test_channel_consistency_above_max_ratio_is_invalid(self):
        result = validate_reading(150, "reactive_energy", [CONSISTENCY_RULE], reference_value=100)
        self.assertFalse(result.is_valid)
        self.assertEqual(result.vee_rule_id, "rule-consistency")
        self.assertIn("fuera de", result.notes)

    def test_channel_consistency_without_reference_value_passes_unevaluated(self):
        # El canal de referencia no reporto en este instante -- no se
        # adivina el ratio, pero tampoco se invalida por esto.
        result = validate_reading(60, "reactive_energy", [CONSISTENCY_RULE], reference_value=None)
        self.assertTrue(result.is_valid)
        self.assertIn("no evaluada", result.notes)

    def test_channel_consistency_with_zero_reference_passes_unevaluated(self):
        result = validate_reading(60, "reactive_energy", [CONSISTENCY_RULE], reference_value=0)
        self.assertTrue(result.is_valid)
        self.assertIn("no evaluada", result.notes)

    def test_channel_without_consistency_rule_ignores_reference_value(self):
        # active_energy no tiene channel_consistency configurada (solo
        # reactive_energy en CONSISTENCY_RULE) -- un reference_value de
        # sobra no debe activar nada.
        result = validate_reading(5000, "active_energy", [RANGE_RULE, CONSISTENCY_RULE], reference_value=1)
        self.assertTrue(result.is_valid)
        self.assertEqual(result.vee_rule_id, "rule-1")


T0 = datetime(2026, 9, 10, 12, 0, 0, tzinfo=timezone.utc)


class DetectGapsTests(unittest.TestCase):
    def test_no_gap_when_readings_are_on_schedule(self):
        readings = [(T0, 100.0), (T0 + timedelta(minutes=15), 110.0), (T0 + timedelta(minutes=30), 120.0)]
        gaps = detect_gaps(readings, expected_interval_seconds=900, tolerance_seconds=60)
        self.assertEqual(gaps, [])

    def test_small_jitter_within_tolerance_is_not_a_gap(self):
        readings = [(T0, 100.0), (T0 + timedelta(minutes=15, seconds=45), 110.0)]
        gaps = detect_gaps(readings, expected_interval_seconds=900, tolerance_seconds=60)
        self.assertEqual(gaps, [])

    def test_missed_readings_are_counted_correctly(self):
        # 3 intervalos de 15 min faltan entre T0 y T0+60min
        readings = [(T0, 100.0), (T0 + timedelta(minutes=60), 200.0)]
        gaps = detect_gaps(readings, expected_interval_seconds=900, tolerance_seconds=60)
        self.assertEqual(len(gaps), 1)
        self.assertEqual(gaps[0].missing_count, 3)
        self.assertEqual(gaps[0].after_value, 100.0)
        self.assertEqual(gaps[0].before_value, 200.0)

    def test_two_separate_gaps_are_both_reported(self):
        readings = [
            (T0, 100.0),
            (T0 + timedelta(minutes=45), 130.0),  # hueco 1: faltan 2
            (T0 + timedelta(minutes=60), 140.0),
            (T0 + timedelta(minutes=120), 200.0),  # hueco 2: faltan 3
        ]
        gaps = detect_gaps(readings, expected_interval_seconds=900, tolerance_seconds=60)
        self.assertEqual(len(gaps), 2)
        self.assertEqual(gaps[0].missing_count, 2)
        self.assertEqual(gaps[1].missing_count, 3)


class EstimateGapTests(unittest.TestCase):
    def test_linear_interpolation_produces_evenly_spaced_points(self):
        gap = Gap(after_timestamp=T0, before_timestamp=T0 + timedelta(minutes=60), after_value=100.0, before_value=200.0, missing_count=3)

        points = estimate_gap(gap, expected_interval_seconds=900, method="linear_interpolation")

        self.assertEqual(len(points), 3)
        self.assertEqual(points[0].timestamp, T0 + timedelta(minutes=15))
        self.assertAlmostEqual(points[0].value, 125.0)
        self.assertAlmostEqual(points[1].value, 150.0)
        self.assertAlmostEqual(points[2].value, 175.0)

    def test_unrecognized_method_raises_instead_of_guessing(self):
        gap = Gap(after_timestamp=T0, before_timestamp=T0 + timedelta(minutes=60), after_value=100.0, before_value=200.0, missing_count=3)
        with self.assertRaises(NotImplementedError):
            estimate_gap(gap, expected_interval_seconds=900, method="made_up_method")

    def test_customer_historical_average_uses_same_time_of_day_across_days(self):
        # Hueco de 1 punto a las 08:00 de T0+1d. El propio historial del
        # medidor tiene 08:00 en dos dias distintos (100, 120) y un valor a
        # otra hora (999) que no deberia contar.
        gap_day = T0.replace(hour=8, minute=0) + timedelta(days=1)
        gap = Gap(after_timestamp=gap_day - timedelta(hours=1), before_timestamp=gap_day + timedelta(hours=1), after_value=0, before_value=0, missing_count=1)
        historical = [
            (T0.replace(hour=8, minute=0), 100.0),
            (T0.replace(hour=8, minute=0) + timedelta(days=2), 120.0),
            (T0.replace(hour=20, minute=0), 999.0),
        ]

        points = estimate_gap(gap, expected_interval_seconds=3600, method="customer_historical_average", historical_readings=historical, historical_tolerance_seconds=300)

        self.assertEqual(len(points), 1)
        self.assertAlmostEqual(points[0].value, 110.0)

    def test_customer_historical_average_without_any_match_raises_instead_of_guessing(self):
        gap = Gap(after_timestamp=T0, before_timestamp=T0 + timedelta(hours=2), after_value=0, before_value=0, missing_count=1)
        with self.assertRaises(InsufficientHistoryError):
            estimate_gap(gap, expected_interval_seconds=3600, method="customer_historical_average", historical_readings=[], historical_tolerance_seconds=60)

    def test_similar_customers_average_uses_other_meters_near_the_same_instant(self):
        gap = Gap(after_timestamp=T0, before_timestamp=T0 + timedelta(hours=2), after_value=0, before_value=0, missing_count=1)
        target = T0 + timedelta(hours=1)
        historical = [
            (target, 200.0),
            (target + timedelta(seconds=30), 220.0),
            (target + timedelta(hours=5), 999.0),  # demasiado lejos, no cuenta
        ]

        points = estimate_gap(gap, expected_interval_seconds=3600, method="similar_customers_average", historical_readings=historical, historical_tolerance_seconds=60)

        self.assertEqual(len(points), 1)
        self.assertAlmostEqual(points[0].value, 210.0)

    def test_similar_customers_average_without_any_match_raises_instead_of_guessing(self):
        gap = Gap(after_timestamp=T0, before_timestamp=T0 + timedelta(hours=2), after_value=0, before_value=0, missing_count=1)
        with self.assertRaises(InsufficientHistoryError):
            estimate_gap(gap, expected_interval_seconds=3600, method="similar_customers_average", historical_readings=[], historical_tolerance_seconds=60)


if __name__ == "__main__":
    unittest.main()
