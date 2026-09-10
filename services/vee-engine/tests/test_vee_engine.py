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

from vee_engine import Gap, detect_gaps, estimate_gap, validate_reading


RANGE_RULE = {"id": "rule-1", "type": "range", "params": {"channel": "active_energy", "min": 0, "max": 10000}, "priority": 100}


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

    def test_unsupported_method_raises_instead_of_guessing(self):
        gap = Gap(after_timestamp=T0, before_timestamp=T0 + timedelta(minutes=60), after_value=100.0, before_value=200.0, missing_count=3)
        with self.assertRaises(NotImplementedError):
            estimate_gap(gap, expected_interval_seconds=900, method="customer_historical_average")


if __name__ == "__main__":
    unittest.main()
