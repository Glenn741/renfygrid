"""JWT minimo (HS256) para RenfyGrid -- ver docs/02-arquitectura-general.md SS3
("Autenticacion: JWT propio") y docs/03-diseno.md (rol_permiso, tenant_scope).

Implementado con la libreria estandar (hmac/hashlib/base64/json) a proposito: en este
entorno de desarrollo no hay acceso confirmado a PyPI (ver docs/05-ejecucion.md) y esto
evita bloquear el Sprint 0 en esa duda. Es HS256 puro -- header/payload en JSON,
firma HMAC-SHA256, todo base64url sin padding, comparacion de firma en tiempo
constante (hmac.compare_digest) -- sin criptografia propia, solo la implementacion
del formato JWT sobre primitivas ya auditadas de la libreria estandar. Si mas
adelante hay acceso a PyPI, cambiar a PyJWT es un reemplazo directo de este modulo
(misma firma de create_token/decode_token) sin tocar quien lo llama.

Todo token de RenfyGrid DEBE llevar `tenant_id` -- es el claim que
renmeter_common.db.tenant_scope usa para fijar el contexto de RLS en cada
transaccion. Un token sin tenant_id no se puede crear.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from typing import Any


class TokenError(RuntimeError):
    """Token invalido, expirado, con firma incorrecta, o sin los claims requeridos."""


_ALG = "HS256"
_REQUIRED_CLAIMS = ("tenant_id",)


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def _sign(message: bytes, secret: str) -> bytes:
    return hmac.new(secret.encode("utf-8"), message, hashlib.sha256).digest()


def create_token(claims: dict[str, Any], secret: str, expires_in_seconds: int = 3600) -> str:
    """Crea un JWT HS256. `claims` DEBE incluir tenant_id (ver docstring del modulo).

    No acepta un `exp` ya puesto en `claims` -- el vencimiento siempre lo calcula
    esta funcion a partir de `expires_in_seconds`, para que nunca quede un token
    de vida "fija" decidida en otro lado sin pasar por aca.
    """
    faltantes = [c for c in _REQUIRED_CLAIMS if c not in claims]
    if faltantes:
        raise TokenError(f"Faltan claims obligatorios: {faltantes}")
    if "exp" in claims:
        raise TokenError("No pasar 'exp' en claims -- lo calcula expires_in_seconds")
    if not secret:
        raise TokenError("secret vacio")

    header = {"alg": _ALG, "typ": "JWT"}
    payload = dict(claims)
    payload["iat"] = int(time.time())
    payload["exp"] = payload["iat"] + expires_in_seconds

    header_b64 = _b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    payload_b64 = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
    signature_b64 = _b64url_encode(_sign(signing_input, secret))

    return f"{header_b64}.{payload_b64}.{signature_b64}"


def decode_token(token: str, secret: str) -> dict[str, Any]:
    """Valida firma + expiracion y devuelve los claims. Lanza TokenError si algo falla.

    Nunca decodifica el payload sin haber verificado la firma primero -- evita el
    error clasico de JWT de confiar en datos antes de autenticarlos.
    """
    try:
        header_b64, payload_b64, signature_b64 = token.split(".")
    except ValueError as exc:
        raise TokenError("Formato de token invalido (se esperan 3 partes)") from exc

    signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
    expected_sig = _sign(signing_input, secret)
    try:
        actual_sig = _b64url_decode(signature_b64)
    except Exception as exc:
        raise TokenError("Firma con codificacion invalida") from exc

    if not hmac.compare_digest(expected_sig, actual_sig):
        raise TokenError("Firma invalida")

    try:
        header = json.loads(_b64url_decode(header_b64))
        payload = json.loads(_b64url_decode(payload_b64))
    except Exception as exc:
        raise TokenError("Header/payload con codificacion invalida") from exc

    if header.get("alg") != _ALG:
        raise TokenError(f"Algoritmo no soportado: {header.get('alg')!r}")

    faltantes = [c for c in _REQUIRED_CLAIMS if c not in payload]
    if faltantes:
        raise TokenError(f"Token sin claims obligatorios: {faltantes}")

    if int(time.time()) >= payload.get("exp", 0):
        raise TokenError("Token expirado")

    return payload
