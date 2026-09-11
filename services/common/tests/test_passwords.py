"""Pruebas puras de renmeter_common.passwords -- sin BD."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from renmeter_common.passwords import hash_password, verify_password


class PasswordsTests(unittest.TestCase):
    def test_correct_password_verifies(self):
        stored = hash_password("correct-horse-battery-staple", iterations=1000)
        self.assertTrue(verify_password("correct-horse-battery-staple", stored))

    def test_wrong_password_fails(self):
        stored = hash_password("correct-horse-battery-staple", iterations=1000)
        self.assertFalse(verify_password("wrong-password", stored))

    def test_two_hashes_of_the_same_password_are_different(self):
        """Salt aleatorio -- dos hashes de la misma contraseña no deben ser iguales."""
        first = hash_password("same-password", iterations=1000)
        second = hash_password("same-password", iterations=1000)
        self.assertNotEqual(first, second)
        self.assertTrue(verify_password("same-password", first))
        self.assertTrue(verify_password("same-password", second))

    def test_empty_password_is_rejected(self):
        with self.assertRaises(ValueError):
            hash_password("")

    def test_garbage_stored_hash_fails_closed(self):
        self.assertFalse(verify_password("anything", "not-a-real-hash"))


if __name__ == "__main__":
    unittest.main()
