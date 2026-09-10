"""Prueba meter_reader.read_register -- la normalizacion de una lectura COSEM
a una fila lista para raw_reading, sin necesitar una sesion DLMS real."""

from __future__ import annotations

import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from meter_reader import read_register


class ReadRegisterTests(unittest.TestCase):
    def test_normalizes_to_a_raw_reading_row(self):
        session = mock.MagicMock()
        session.read_attribute.return_value = 4781999

        reading = read_register(
            session,
            meter_id="m-1",
            obis_code="1.0.1.8.0.255",
            channel="active_energy",
        )

        row = reading.as_row()
        self.assertEqual(row["meter_id"], "m-1")
        self.assertEqual(row["channel"], "active_energy")
        self.assertEqual(row["value"], 4781999)
        self.assertEqual(row["source_quality"], "real")
        self.assertLessEqual(
            (datetime.now(timezone.utc) - row["timestamp"]).total_seconds(), 5
        )

    def test_uses_attribute_index_2_by_default(self):
        """El atributo 'value' estandar de un Register (IC 3) es el indice 2 --
        ver docs/03-diseno.md SS5 y el Blue Book de DLMS/COSEM."""
        session = mock.MagicMock()
        session.read_attribute.return_value = 1

        read_register(session, meter_id="m-1", obis_code="1.0.1.8.0.255", channel="x")

        args, _ = session.read_attribute.call_args
        self.assertEqual(args[1], 2)

    def test_custom_attribute_index_is_respected(self):
        session = mock.MagicMock()
        session.read_attribute.return_value = 1

        read_register(
            session,
            meter_id="m-1",
            obis_code="1.0.1.8.0.255",
            channel="x",
            attribute_index=3,
        )

        args, _ = session.read_attribute.call_args
        self.assertEqual(args[1], 3)


if __name__ == "__main__":
    unittest.main()
