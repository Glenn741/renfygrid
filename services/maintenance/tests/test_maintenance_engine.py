"""Pruebas puras de maintenance_engine -- sin BD, logica de SLA/mora/KPIs
del CMMS (docs/04-plan-sprints.md SS9, docs/05-ejecucion.md 2026-09-14)."""

from __future__ import annotations

import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from maintenance_engine import (
    advance_pm_plan,
    compute_backlog,
    compute_mttr_hours,
    compute_pm_compliance_pct,
    compute_sla_due_at,
    is_overdue,
    pm_plan_is_due,
)

NOW = datetime(2026, 9, 14, 12, 0, tzinfo=timezone.utc)


class ComputeSlaDueAtTests(unittest.TestCase):
    def test_none_target_hours_gives_none(self):
        self.assertIsNone(compute_sla_due_at(NOW, None))

    def test_adds_target_hours(self):
        self.assertEqual(compute_sla_due_at(NOW, 24), NOW + timedelta(hours=24))


class IsOverdueTests(unittest.TestCase):
    def test_no_sla_never_overdue(self):
        self.assertFalse(is_overdue(None, "in_progress", NOW))

    def test_terminal_status_never_overdue(self):
        past = NOW - timedelta(hours=1)
        self.assertFalse(is_overdue(past, "completed", NOW))
        self.assertFalse(is_overdue(past, "cancelled", NOW))

    def test_open_past_sla_is_overdue(self):
        past = NOW - timedelta(hours=1)
        self.assertTrue(is_overdue(past, "in_progress", NOW))

    def test_open_before_sla_not_overdue(self):
        future = NOW + timedelta(hours=1)
        self.assertFalse(is_overdue(future, "in_progress", NOW))


class ComputeMttrHoursTests(unittest.TestCase):
    def test_no_completed_orders_gives_none(self):
        self.assertIsNone(compute_mttr_hours([]))

    def test_averages_real_durations(self):
        orders = [
            {"created_at": NOW - timedelta(hours=10), "closed_at": NOW},
            {"created_at": NOW - timedelta(hours=20), "closed_at": NOW},
        ]
        self.assertEqual(compute_mttr_hours(orders), 15.0)

    def test_ignores_orders_missing_timestamps(self):
        orders = [{"created_at": NOW - timedelta(hours=10), "closed_at": NOW}, {"created_at": NOW, "closed_at": None}]
        self.assertEqual(compute_mttr_hours(orders), 10.0)


class ComputeBacklogTests(unittest.TestCase):
    def test_no_open_orders_gives_zero_count_none_age(self):
        result = compute_backlog([], NOW)
        self.assertEqual(result, {"count": 0, "avg_age_hours": None})

    def test_counts_and_averages_age(self):
        orders = [{"created_at": NOW - timedelta(hours=5)}, {"created_at": NOW - timedelta(hours=15)}]
        result = compute_backlog(orders, NOW)
        self.assertEqual(result["count"], 2)
        self.assertEqual(result["avg_age_hours"], 10.0)


class ComputePmCompliancePctTests(unittest.TestCase):
    def test_no_orders_with_sla_gives_none(self):
        self.assertIsNone(compute_pm_compliance_pct([]))
        self.assertIsNone(compute_pm_compliance_pct([{"closed_at": NOW, "sla_due_at": None}]))

    def test_on_time_and_late_split_correctly(self):
        orders = [
            {"closed_at": NOW, "sla_due_at": NOW + timedelta(hours=1)},   # on time
            {"closed_at": NOW, "sla_due_at": NOW - timedelta(hours=1)},   # late
            {"closed_at": NOW, "sla_due_at": NOW},                        # exactly on time
        ]
        self.assertEqual(compute_pm_compliance_pct(orders), round(100 * 2 / 3, 1))


class PmPlanSchedulingTests(unittest.TestCase):
    def test_pm_plan_is_due(self):
        self.assertTrue(pm_plan_is_due(NOW - timedelta(days=1), NOW))
        self.assertTrue(pm_plan_is_due(NOW, NOW))
        self.assertFalse(pm_plan_is_due(NOW + timedelta(days=1), NOW))

    def test_advance_pm_plan_single_step(self):
        next_due = NOW - timedelta(days=1)
        self.assertEqual(advance_pm_plan(next_due, 30, NOW), next_due + timedelta(days=30))

    def test_advance_pm_plan_multiple_missed_intervals(self):
        # Vencido hace 70 dias, intervalo de 30 -- avanza hasta quedar en
        # el futuro real, nunca solo un salto (una orden por intervalo
        # vencido se genera aparte, esto solo mueve el proximo vencimiento).
        next_due = NOW - timedelta(days=70)
        result = advance_pm_plan(next_due, 30, NOW)
        self.assertGreater(result, NOW)
        self.assertEqual(result, next_due + timedelta(days=90))


if __name__ == "__main__":
    unittest.main()
