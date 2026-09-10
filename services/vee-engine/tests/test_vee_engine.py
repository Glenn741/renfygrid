"""Pruebas puras de vee_engine.validate_reading -- sin BD, sin mocks de red
(a diferencia de hes-adapter-dlms, aca la logica no toca ningun protocolo
externo, asi que se prueba directo)."""

from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vee_engine import validate_reading


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


if __name__ == "__main__":
    unittest.main()
