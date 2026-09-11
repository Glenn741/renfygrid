"""Pruebas puras de order_signing -- sin BD."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from order_signing import sign_order, verify_order_signature


class OrderSigningTests(unittest.TestCase):
    def test_signature_verifies_against_the_same_fields(self):
        signature = sign_order("order-1", "meter-1", "suspension", secret="s3cret")
        self.assertTrue(verify_order_signature("order-1", "meter-1", "suspension", signature, secret="s3cret"))

    def test_tampering_the_order_type_invalidates_the_signature(self):
        """Si un mensaje interceptado cambia el tipo de orden (ej. de
        'reconnection' a 'suspension'), la firma ya no coincide."""
        signature = sign_order("order-1", "meter-1", "reconnection", secret="s3cret")
        self.assertFalse(verify_order_signature("order-1", "meter-1", "suspension", signature, secret="s3cret"))

    def test_wrong_secret_invalidates_the_signature(self):
        signature = sign_order("order-1", "meter-1", "suspension", secret="s3cret")
        self.assertFalse(verify_order_signature("order-1", "meter-1", "suspension", signature, secret="wrong-secret"))

    def test_replaying_the_signature_for_a_different_order_id_fails(self):
        """Evita que la firma de una orden se reuse para otra (repeticion en el bus)."""
        signature = sign_order("order-1", "meter-1", "suspension", secret="s3cret")
        self.assertFalse(verify_order_signature("order-2", "meter-1", "suspension", signature, secret="s3cret"))


if __name__ == "__main__":
    unittest.main()
