"""Alta de organizaciones y de su primer usuario (Track E, E1, 0047).

Pedido del usuario (19-oct): "importante que se puedan crear usuarios nuevos y
tenant nuevos". Hasta ahora una organizacion solo nacia por script.

- La organizacion de la plataforma (tipo 'platform') crea organizaciones de
  cualquier tipo: prestador (junta), agrupacion, ONG que asesora u otra de
  plataforma. Ninguna otra organizacion puede, aunque su rol tenga el permiso.
- La ONG crea la organizacion de un operador asesorado con los datos que
  levanto (`advisory_service.transfer_operator`), por el mismo camino.

Toda organizacion nace igual: el nucleo (trigger de 0025), los paquetes que
se indiquen, zona horaria, duracion de la sesion, moneda y region, y un
usuario administrador. El nombre es el codigo con el que se inicia sesion
(p. ej. "jaas001"), unico sin distinguir mayusculas.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "portal-api"))

import psycopg  # noqa: E402
from psycopg.types.json import Json  # noqa: E402

from pack_engine import InvalidRecordError  # noqa: E402
from pack_service import PackNotFoundError, adopt_pack  # noqa: E402

KINDS = ("provider", "group", "advisor", "platform")
ADMIN_ROLE = "supervisor"
# Lo que una organizacion nueva hereda de la que la crea si no se indica.
INHERITED_CONFIG = ("timezone", "session_ttl_seconds", "currency", "locale")
_CODE = re.compile(r"^[a-z0-9][a-z0-9._-]{2,39}$")


class OrganizationConflictError(RuntimeError):
    """La organizacion ya existe o quien pide no puede crearla."""


def tenant_kind(conn: psycopg.Connection, tenant_id: str) -> str | None:
    with conn.cursor() as cur:
        cur.execute("SELECT kind FROM tenant WHERE id = %s", (tenant_id,))
        row = cur.fetchone()
    return row[0] if row else None


def require_kind(conn: psycopg.Connection, tenant_id: str, kind: str, what: str) -> None:
    if tenant_kind(conn, tenant_id) != kind:
        raise OrganizationConflictError(what)


def validate_code(name: str) -> str:
    code = (name or "").strip().lower()
    if not _CODE.match(code):
        raise InvalidRecordError(
            "El código de la organización (con el que se inicia sesión) debe tener de 3 a 40 caracteres: "
            "letras minúsculas sin tilde, números, punto, guion o guion bajo (p. ej. jaas-sanjuan)")
    return code


def _code_taken(conn: psycopg.Connection, code: str) -> bool:
    with conn.cursor() as cur:
        cur.execute("SELECT 1 FROM tenant WHERE lower(name) = lower(%s)", (code,))
        return cur.fetchone() is not None


def config_from(conn: psycopg.Connection, tenant_id: str) -> dict[str, Any]:
    with conn.cursor() as cur:
        cur.execute("SELECT config FROM tenant WHERE id = %s", (tenant_id,))
        row = cur.fetchone()
    config = (row[0] if row else None) or {}
    return {k: config[k] for k in INHERITED_CONFIG if k in config}


def _clean_config(config: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    tz = config.get("timezone")
    if tz:
        try:
            ZoneInfo(tz)
        except (ZoneInfoNotFoundError, ValueError):
            raise InvalidRecordError(f"Zona horaria desconocida: {tz!r}") from None
        out["timezone"] = tz
    ttl = config.get("session_ttl_seconds")
    if ttl is not None:
        if not isinstance(ttl, int) or ttl <= 0:
            raise InvalidRecordError("La duración de la sesión debe ser un número de segundos mayor que cero")
        out["session_ttl_seconds"] = ttl
    for key in ("currency", "locale"):
        if config.get(key):
            out[key] = config[key]
    return out


def create_organization(
    conn: psycopg.Connection,
    name: str,
    kind: str,
    admin_username: str,
    admin_password: str,
    created_by: str,
    config: dict[str, Any] | None = None,
    packs: list[str] | None = None,
    display_name: str | None = None,
) -> dict:
    """Crea la organizacion, adopta sus paquetes y crea su administrador, todo
    en una transaccion: si algo falla no queda una organizacion a medias."""
    # Import tardio: permissions vive en portal-api y valida usuario/clave
    # con las mismas reglas de Configuracion -> Usuarios.
    from permissions import create_user

    code = validate_code(name)
    if kind not in KINDS:
        raise InvalidRecordError(f"Tipo de organización inválido: {kind!r}")
    clean_config = _clean_config(config or {})
    if "session_ttl_seconds" not in clean_config:
        raise InvalidRecordError("Indique la duración de la sesión de la organización")
    if display_name and display_name.strip():
        clean_config["display_name"] = display_name.strip()
    clean_config["created_by"] = created_by
    with conn.transaction():
        if _code_taken(conn, code):
            raise OrganizationConflictError(f"Ya existe una organización con el código {code!r}")
        with conn.cursor() as cur:
            cur.execute("INSERT INTO tenant (name, plan, config, kind) VALUES (%s, 'pilot', %s, %s) RETURNING id, created_at",
                        (code, Json(clean_config), kind))
            tenant_id, created_at = cur.fetchone()
        tenant_id = str(tenant_id)
        for pack_id in packs or []:
            try:
                adopt_pack(conn, tenant_id, pack_id)
            except PackNotFoundError as exc:
                raise InvalidRecordError(str(exc)) from None
        # En la organizacion de la plataforma su administrador es el rol que crea organizaciones.
        admin = create_user(conn, tenant_id, admin_username, admin_password, "platform" if kind == "platform" else ADMIN_ROLE)
    return {"tenant_id": tenant_id, "name": code, "kind": kind, "display_name": clean_config.get("display_name"),
            "created_at": created_at.isoformat(), "admin": admin, "packs": packs or []}


def list_organizations(conn: psycopg.Connection) -> list[dict]:
    """Todas las organizaciones (solo para la organizacion de la plataforma;
    `tenant` no tiene RLS y `app_user` se cuenta por organizacion)."""
    with conn.cursor() as cur:
        cur.execute("SELECT id, name, kind, is_active, created_at, config ->> 'display_name' FROM tenant ORDER BY created_at")
        rows = cur.fetchall()
    return [{"tenant_id": str(r[0]), "name": r[1], "kind": r[2], "is_active": r[3], "created_at": r[4].isoformat(),
             "display_name": r[5]} for r in rows]
