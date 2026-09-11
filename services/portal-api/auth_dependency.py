"""Dependencia de FastAPI que exige un JWT valido (Sprint 0,
`renmeter_common/auth.py`, primer uso real) y devuelve el `tenant_id` del
token -- NUNCA el `tenant_id` de un query param o del body. Es lo unico que
hace que el aislamiento entre tenants (F33) sea real: el filtro por tenant
sale de un claim firmado, no de algo que el cliente HTTP pueda elegir.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))

from fastapi import Header, HTTPException, Request  # noqa: E402

from renmeter_common.auth import TokenError, decode_token  # noqa: E402


def get_tenant_id(request: Request, authorization: str | None = Header(default=None)) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Falta el header Authorization: Bearer <token>")
    token = authorization.removeprefix("Bearer ").strip()
    try:
        claims = decode_token(token, request.app.state.settings.jwt_secret)
    except TokenError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    return claims["tenant_id"]
