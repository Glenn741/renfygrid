"""Pruebas puras de metering_asset_engine (Track F, Q2, 0049) -- sin BD.
Los umbrales y frecuencias de prueba son los del paquete CO-CREG-038
(Resolucion CREG 038 de 2014, art. 6 y art. 28 tabla 4), copiados aqui como
datos de entrada, igual que los entrega la BD."""

from __future__ import annotations

import sys
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from metering_asset_engine import (  # noqa: E402
    add_months,
    event_passed,
    invalidates_calibration,
    periodic_status,
    point_class_for,
    worst_status,
)

CLASSES = [
    {"code": "1", "sort_order": 1, "min_mwh_month": 15000, "min_mva": 30},
    {"code": "2", "sort_order": 2, "min_mwh_month": 500, "min_mva": 1},
    {"code": "3", "sort_order": 3, "min_mwh_month": 50, "min_mva": 0.1},
    {"code": "4", "sort_order": 4, "min_mwh_month": 5, "min_mva": 0.01},
    {"code": "5", "sort_order": 5, "min_mwh_month": 0, "min_mva": 0},
]
TODAY = date(2026, 10, 20)


class PointClassTest(unittest.TestCase):
    def test_by_energy(self):
        self.assertEqual(point_class_for(15000, None, CLASSES), "1")
        self.assertEqual(point_class_for(14999, None, CLASSES), "2")
        self.assertEqual(point_class_for(60, None, CLASSES), "3")
        self.assertEqual(point_class_for(4.9, None, CLASSES), "5")

    def test_most_demanding_of_both(self):
        # 40 MWh-mes es tipo 4, pero 1,5 MVA instalados lo hacen tipo 2.
        self.assertEqual(point_class_for(40, 1.5, CLASSES), "2")

    def test_unknown(self):
        self.assertIsNone(point_class_for(None, None, CLASSES))


class PeriodicStatusTest(unittest.TestCase):
    def status(self, **kw):
        base = dict(activity="calibration", every_months=48, last_done=date(2023, 6, 10), invalidated_after=None,
                    today=TODAY, due_soon_days=90)
        base.update(kw)
        return periodic_status(**base)

    def test_ok_and_due_date(self):
        s = self.status()
        self.assertEqual((s["status"], s["due_on"]), ("ok", "2027-06-10"))

    def test_due_soon_inside_window(self):
        self.assertEqual(self.status(last_done=date(2022, 12, 1))["status"], "due_soon")

    def test_without_window_never_due_soon(self):
        # La organizacion no configuro la ventana: no se inventa una.
        self.assertEqual(self.status(last_done=date(2022, 12, 1), due_soon_days=None)["status"], "ok")

    def test_overdue(self):
        s = self.status(every_months=24, last_done=date(2024, 1, 1))
        self.assertEqual((s["status"], s["due_on"]), ("overdue", "2026-01-01"))

    def test_missing(self):
        self.assertEqual(self.status(last_done=None)["status"], "missing")

    def test_not_required(self):
        self.assertEqual(self.status(activity=None)["status"], "not_required")
        self.assertEqual(self.status(every_months=None)["status"], "not_required")

    def test_invalidated_after_calibration(self):
        s = self.status(invalidated_after=date(2025, 3, 2))
        self.assertEqual((s["status"], s["reason"], s["due_on"]), ("overdue", "invalidated", "2025-03-02"))

    def test_recalibration_clears_invalidation(self):
        self.assertEqual(self.status(last_done=date(2025, 3, 5), invalidated_after=date(2025, 3, 2))["status"], "ok")


class RulesTest(unittest.TestCase):
    def test_invalidates(self):
        self.assertFalse(invalidates_calibration(None, {}))
        self.assertTrue(invalidates_calibration("always", {}))
        self.assertTrue(invalidates_calibration("main_cover", {"fields": {"main_cover": {"value": True}}}))
        self.assertFalse(invalidates_calibration("main_cover", {"fields": {"main_cover": {"value": False}}}))
        self.assertFalse(invalidates_calibration("main_cover", {"fields": {}}))

    def test_event_passed(self):
        self.assertTrue(event_passed({"fields": {"result": {"value": "pass"}}}))
        self.assertTrue(event_passed({"fields": {}}))
        self.assertFalse(event_passed({"fields": {"result": {"value": "fail"}}}))

    def test_add_months_end_of_month(self):
        self.assertEqual(add_months(date(2024, 2, 29), 12), date(2025, 2, 28))
        self.assertEqual(add_months(date(2026, 1, 31), 1), date(2026, 2, 28))

    def test_worst_status(self):
        self.assertEqual(worst_status(["ok", "due_soon", "not_required"]), "due_soon")
        self.assertEqual(worst_status(["ok", "missing", "overdue"]), "overdue")
        self.assertEqual(worst_status([]), "not_required")


if __name__ == "__main__":
    unittest.main()
