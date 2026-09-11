"""Prueba pura de to_csv -- sin BD."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from billing_export import to_csv


class ToCsvTests(unittest.TestCase):
    def test_produces_a_header_and_one_row_per_entry(self):
        rows = [
            {"account_number": "ACC-1", "meter_id": "m-1", "period_start": "2026-09-01", "period_end": "2026-10-01", "consumption_value": 500.0, "unit": "kWh"},
        ]
        csv_text = to_csv(rows)
        lines = csv_text.strip().splitlines()
        self.assertEqual(lines[0], "account_number,meter_id,period_start,period_end,consumption_value,unit")
        self.assertEqual(lines[1], "ACC-1,m-1,2026-09-01,2026-10-01,500.0,kWh")

    def test_empty_rows_still_produces_the_header(self):
        csv_text = to_csv([])
        self.assertEqual(csv_text.strip(), "account_number,meter_id,period_start,period_end,consumption_value,unit")


if __name__ == "__main__":
    unittest.main()
