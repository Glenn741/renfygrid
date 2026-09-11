"""Dependencia de FastAPI que exige un JWT valido (Sprint 0,
`renmeter_common/auth.py`, primer uso real) y devuelve el `tenant_id` del
token -- NUNCA el `tenant_id` de un query param o del body. Es lo unico que
hace que el aislamiento entre tenants (F33) sea real: el filtro por tenant
sale de un claim firmado, no de algo que el cliente HTTP pueda elegir.

Sprint C5 (E16, `docs/06-benchmark-e2e-y-brechas.md` SS2/G1): mismo
principio aplicado a QUIEN pide algo, no solo a DE QUE tenant -- antes
`requested_by`/`approver_name`/`approver_role` llegaban como texto libre en
el body (cualquiera con un JWT valido podia escribir "cis:facturacion" sin
serlo). `get_actor` devuelve la identidad completa del token, y
`requested_by_label` es la convencion real de origen: `cis:<email>` si el
`app_user` tiene rol `integration` (la cuenta de servicio que usaria un CIS
externo para autenticarse), `portal:<email>` para cualquier otro humano
autenticado. Los actores puramente automaticos del propio backend
(`system:auto_approval`, `system:scr_dispatch`) siguen escribiendose tal
cual desde `control_service.py` -- no pasan por aca porque no hay un
request HTTP de por medio.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))

from fastapi import Header, HTTPException, Request  # noqa: E402

from renmeter_common.auth import TokenError, decode_token  # noqa: E402

INTEGRATION_ROLE = "integration"


def _decode(request: Request, authorization: str | None) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Falta el header Authorization: Bearer <token>")
    token = authorization.removeprefix("Bearer ").strip()
    try:
        return decode_token(token, request.app.state.settings.jwt_secret)
    except TokenError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


def get_tenant_id(request: Request, authorization: str | None = Header(default=None)) -> str:
    return _decode(request, authorization)["tenant_id"]


def get_actor(request: Request, authorization: str | None = Header(default=None)) -> dict:
    """Identidad completa del JWT -- `tenant_id`/`role`/`user_id`/`email`,
    todos firmados, ninguno del body. `email` solo existe en tokens
    emitidos desde Sprint C5 en adelante; un token viejo sin ese claim cae
    a `user_id` para no romper en caliente."""
    claims = _decode(request, authorization)
    return {
        "tenant_id": claims["tenant_id"],
        "role": claims.get("role"),
        "user_id": claims.get("user_id"),
        "email": claims.get("email") or claims.get("user_id"),
    }


def requested_by_label(actor: dict) -> str:
    """La convencion real de origen (G1): `cis:<email>` para la cuenta de
    servicio de integracion, `portal:<email>` para cualquier humano. Nunca
    texto libre del cliente."""
    prefix = "cis" if actor.get("role") == INTEGRATION_ROLE else "portal"
    return f"{prefix}:{actor['email']}"
