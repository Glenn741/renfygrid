"""Pruebas puras de la aritmetica de meses de partition_maintenance.py (F10,
Sprint C11) -- sin Postgres, la parte que toca BD se prueba end-to-end en
`infra/db/verify_partitioning_end_to_end.py`."""

from __future__ import annotations

import sys
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from renmeter_common.partition_maintenance import _add_months, _month_start


class MonthStartTests(unittest.TestCase):
    def test_mid_month_date_truncates_to_day_one(self):
        self.assertEqual(_month_start(date(2026, 9, 15)), date(2026, 9, 1))

    def test_already_day_one_is_unchanged(self):
        self.assertEqual(_month_start(date(2026, 9, 1)), date(2026, 9, 1))


class AddMonthsTests(unittest.TestCase):
    def test_add_within_same_year(self):
        self.assertEqual(_add_months(date(2026, 9, 1), 2), date(2026, 11, 1))

    def test_add_rolls_over_to_next_year(self):
        self.assertEqual(_add_months(date(2026, 11, 1), 3), date(2027, 2, 1))

    def test_add_zero_is_unchanged(self):
        self.assertEqual(_add_months(date(2026, 9, 1), 0), date(2026, 9, 1))

    def test_add_twelve_advances_exactly_one_year(self):
        self.assertEqual(_add_months(date(2026, 3, 1), 12), date(2027, 3, 1))


if __name__ == "__main__":
    unittest.main()
