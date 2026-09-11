"""Prueba pura del mapeo de origen del panel de Service Orders (Sprint C5,
G3) -- sin BD."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from service_orders import _origin


class OriginTests(unittest.TestCase):
    def test_cis_prefix(self):
        self.assertEqual(_origin("cis:facturacion@empresa.com"), "CIS externo")

    def test_portal_prefix(self):
        self.assertEqual(_origin("portal:ana@utility.com"), "Portal (operador)")

    def test_system_prefix(self):
        self.assertEqual(_origin("system:auto_approval"), "Sistema")

    def test_none_is_unknown_not_a_guess(self):
        """Sin requested_by (peticiones de antes de este sprint), nunca se
        adivina un origen -- queda explicito como desconocido."""
        self.assertEqual(_origin(None), "desconocido")

    def test_unrecognized_prefix_is_unknown_not_a_guess(self):
        self.assertEqual(_origin("otracosa:x"), "desconocido")


if __name__ == "__main__":
    unittest.main()
