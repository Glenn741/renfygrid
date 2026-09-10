"""Pruebas puras de consumption_engine -- sin BD."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from consumption_engine import compute_consumption, detect_deviation


class ComputeConsumptionTests(unittest.TestCase):
    def test_consumption_is_closing_minus_opening(self):
        self.assertEqual(compute_consumption(opening_value=1000, closing_value=1450), 450)


STRICT_RULE = {"id": "rule-strict", "condition": {"max_deviation_pct": 20}, "action": "reread_order"}
LOOSE_RULE = {"id": "rule-loose", "condition": {"max_deviation_pct": 50}, "action": "inspection_order"}


class DetectDeviationTests(unittest.TestCase):
    def test_no_previous_consumption_means_no_anomaly(self):
        result = detect_deviation(current_value=500, previous_value=None, rules=[STRICT_RULE])
        self.assertFalse(result.is_anomalous)
        self.assertIsNone(result.deviation_pct)

    def test_small_deviation_within_threshold_is_not_anomalous(self):
        result = detect_deviation(current_value=105, previous_value=100, rules=[STRICT_RULE])
        self.assertFalse(result.is_anomalous)
        self.assertAlmostEqual(result.deviation_pct, 5.0)

    def test_large_deviation_above_threshold_is_anomalous_and_traces_the_rule(self):
        result = detect_deviation(current_value=200, previous_value=100, rules=[STRICT_RULE])
        self.assertTrue(result.is_anomalous)
        self.assertEqual(result.rule_id, "rule-strict")
        self.assertEqual(result.action, "reread_order")

    def test_stricter_rule_wins_when_several_apply(self):
        result = detect_deviation(current_value=130, previous_value=100, rules=[LOOSE_RULE, STRICT_RULE])
        self.assertTrue(result.is_anomalous)
        self.assertEqual(result.rule_id, "rule-strict")

    def test_no_rules_configured_means_no_anomaly_but_still_reports_deviation(self):
        result = detect_deviation(current_value=200, previous_value=100, rules=[])
        self.assertFalse(result.is_anomalous)
        self.assertAlmostEqual(result.deviation_pct, 100.0)


if __name__ == "__main__":
    unittest.main()
