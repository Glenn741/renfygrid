"""Prueba el JWT minimo de RenfyGrid (renmeter_common.auth) -- ver docs/03-diseno.md
y el requisito de que todo token lleve tenant_id (lo que despues usa
renmeter_common.db.tenant_scope para fijar el contexto de RLS).

Correr con:  python -m unittest tests.test_auth -v
"""

from __future__ import annotations

import sys
import time
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from renmeter_common.auth import TokenError, create_token, decode_token


class AuthTests(unittest.TestCase):
    def test_round_trip_returns_the_same_claims(self):
        token = create_token({"tenant_id": "t1", "role": "operator"}, secret="s3cret")
        claims = decode_token(token, secret="s3cret")
        self.assertEqual(claims["tenant_id"], "t1")
        self.assertEqual(claims["role"], "operator")
        self.assertIn("iat", claims)
        self.assertIn("exp", claims)

    def test_cannot_create_without_tenant_id(self):
        with self.assertRaises(TokenError):
            create_token({"role": "operator"}, secret="s3cret")

    def test_does_not_allow_passing_exp_manually(self):
        with self.assertRaises(TokenError):
            create_token({"tenant_id": "t1", "exp": 9999999999}, secret="s3cret")

    def test_wrong_secret_fails(self):
        token = create_token({"tenant_id": "t1"}, secret="s3cret")
        with self.assertRaises(TokenError):
            decode_token(token, secret="other-secret")

    def test_expired_token_fails(self):
        with mock.patch("renmeter_common.auth.time.time", return_value=1_000_000):
            token = create_token({"tenant_id": "t1"}, secret="s3cret", expires_in_seconds=10)
        with mock.patch("renmeter_common.auth.time.time", return_value=1_000_011):
            with self.assertRaises(TokenError):
                decode_token(token, secret="s3cret")

    def test_tampered_payload_fails_signature_check(self):
        token = create_token({"tenant_id": "t1", "role": "operator"}, secret="s3cret")
        header_b64, payload_b64, sig_b64 = token.split(".")
        # Intento de escalar de "operator" a "admin" tocando el payload sin re-firmar
        tampered_token = f"{header_b64}.{payload_b64}XYZ.{sig_b64}"
        with self.assertRaises(TokenError):
            decode_token(tampered_token, secret="s3cret")

    def test_invalid_format_fails_with_clear_message(self):
        with self.assertRaises(TokenError):
            decode_token("not-a-jwt", secret="s3cret")

    def test_token_really_expires_with_the_real_clock(self):
        """Igual a test_expired_token_fails pero sin mockear time -- confirma que
        expires_in_seconds=0 vence de inmediato con el reloj real del sistema."""
        token = create_token({"tenant_id": "t1"}, secret="s3cret", expires_in_seconds=0)
        time.sleep(1.1)
        with self.assertRaises(TokenError):
            decode_token(token, secret="s3cret")


if __name__ == "__main__":
    unittest.main()
