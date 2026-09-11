"""Prueba pura de la convencion de origen (Sprint C5, G1) -- sin HTTP, sin
JWT real: solo la funcion que decide `cis:<email>` vs `portal:<email>`."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from auth_dependency import requested_by_label


class RequestedByLabelTests(unittest.TestCase):
    def test_integration_role_is_tagged_as_cis(self):
        actor = {"role": "integration", "email": "facturacion@empresa.com"}
        self.assertEqual(requested_by_label(actor), "cis:facturacion@empresa.com")

    def test_any_other_role_is_tagged_as_portal(self):
        for role in ("supervisor", "operator", None, ""):
            actor = {"role": role, "email": "ana@utility.com"}
            self.assertEqual(requested_by_label(actor), "portal:ana@utility.com")

    def test_role_string_similar_to_integration_is_not_matched_loosely(self):
        """Solo el valor exacto 'integration' cuenta -- nunca un match parcial
        que pudiera colarse por error de tipeo en otro lado."""
        actor = {"role": "integration_admin", "email": "x@y.com"}
        self.assertEqual(requested_by_label(actor), "portal:x@y.com")


if __name__ == "__main__":
    unittest.main()
