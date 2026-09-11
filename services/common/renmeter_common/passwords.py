"""Hash de contraseñas para `app_user` (F47, Sprint C1).

PBKDF2-HMAC-SHA256 con la librería estándar (`hashlib.pbkdf2_hmac`) -- mismo
criterio que `auth.py` (JWT propio con stdlib): un algoritmo real, aprobado
(NIST SP 800-132), sin agregar una dependencia externa para esto. Salt
aleatorio por contraseña (`os.urandom`), comparación en tiempo constante
(`hmac.compare_digest`) para no filtrar nada por temporización.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os

_ALGORITHM = "pbkdf2_sha256"
_DEFAULT_ITERATIONS = 200_000


def hash_password(password: str, iterations: int = _DEFAULT_ITERATIONS) -> str:
    if not password:
        raise ValueError("password vacio")
    salt = os.urandom(16)
    derived = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return f"{_ALGORITHM}${iterations}${base64.b64encode(salt).decode()}${base64.b64encode(derived).decode()}"


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        algorithm, iterations_str, salt_b64, derived_b64 = stored_hash.split("$")
    except ValueError:
        return False
    if algorithm != _ALGORITHM:
        return False
    salt = base64.b64decode(salt_b64)
    expected = base64.b64decode(derived_b64)
    actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, int(iterations_str))
    return hmac.compare_digest(actual, expected)
