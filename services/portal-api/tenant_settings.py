"""Configuracion real por tenant, editable desde el Portal Web (2026-09-15,
a pedido EXPLICITO del usuario: "Nada HARCODEADO. NO es opcional. Debe ser
parametro editable en UI").

Hallazgo real que motivo esto: `stale_after_seconds` (cuanto sin una
lectura cuenta como "medidor caido") tenia un valor fijo de 3600s (1h) en
tres lugares distintos (`dashboard.py`, `fleet_aggregation.py`, y el
default de query param en `main.py`/`api.ts`) -- una ventana de 1h no
tiene sentido para un medidor de agua que reporta cada 4h (siempre se ve
"caido"), pero tampoco para uno que reporta cada 15 minutos (una hora
entera sin alertar es demasiado). El umbral correcto depende de la
cadencia REAL de reporte de ESE tenant, nunca un numero adivinado en
codigo.

Se guarda en `tenant.config` (jsonb, ya existe desde `0001_init.sql`,
pensado exactamente para esto) -- sin migracion nueva. `tenant` no tiene
RLS (es la tabla raiz que define quienes son los tenants, ver comentario
en `0001_init.sql`), asi que el filtro `WHERE id = %s` es responsabilidad
explicita de esta capa, igual que ya hace el resto del codigo que toca
`tenant` directo (autenticacion)."""

from __future__ import annotations

import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

sys.path.insert(0, str(Path(__file__).resolve().parent))

import psycopg  # noqa: E402

STALE_AFTER_SECONDS_KEY = "meter_stale_after_seconds"


def get_meter_stale_after_seconds(conn: psycopg.Connection, tenant_id: str) -> int | None:
    """`None` si el tenant todavia no configuro este umbral -- nunca un
    numero fabricado. El llamador decide que hacer con "sin configurar"
    (nunca inventar un umbral, ver `observability.py`/`dashboard.py`/
    `fleet_aggregation.py`)."""
    with conn.cursor() as cur:
        cur.execute("SELECT config ->> %s FROM tenant WHERE id = %s", (STALE_AFTER_SECONDS_KEY, tenant_id))
        row = cur.fetchone()
    if row is None or row[0] is None:
        return None
    return int(row[0])


def set_meter_stale_after_seconds(conn: psycopg.Connection, tenant_id: str, seconds: int) -> None:
    if seconds <= 0:
        raise ValueError("stale_after_seconds debe ser un numero positivo de segundos")
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE tenant SET config = config || jsonb_build_object(%s::text, %s::int) WHERE id = %s",
            (STALE_AFTER_SECONDS_KEY, seconds, tenant_id),
        )
        if cur.rowcount == 0:
            raise LookupError(f"No existe el tenant {tenant_id}")


SESSION_TTL_KEY = "session_ttl_seconds"
MIN_SESSION_TTL_SECONDS = 300  # una sesion de menos de 5 min no permite trabajar; limite de validacion, no un valor de uso


class SessionTtlNotConfiguredError(LookupError):
    """La organizacion no tiene definida la duracion de sesion -- el login
    lo dice en vez de inventar una (2026-10-05)."""


def get_session_ttl_seconds(conn: psycopg.Connection, tenant_id: str) -> int | None:
    """Duracion de la sesion del Portal para esta organizacion (0022).
    `None` si no esta configurada -- nunca un valor fabricado."""
    with conn.cursor() as cur:
        cur.execute("SELECT config ->> %s FROM tenant WHERE id = %s", (SESSION_TTL_KEY, tenant_id))
        row = cur.fetchone()
    if row is None or row[0] is None:
        return None
    return int(row[0])


def set_session_ttl_seconds(conn: psycopg.Connection, tenant_id: str, seconds: int) -> None:
    if seconds < MIN_SESSION_TTL_SECONDS:
        raise ValueError(f"La sesión debe durar al menos {MIN_SESSION_TTL_SECONDS // 60} minutos")
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE tenant SET config = config || jsonb_build_object(%s::text, %s::int) WHERE id = %s",
            (SESSION_TTL_KEY, seconds, tenant_id),
        )
        if cur.rowcount == 0:
            raise LookupError(f"No existe el tenant {tenant_id}")


TIMEZONE_KEY = "timezone"


class TimezoneNotConfiguredError(LookupError):
    """La organizacion no tiene zona horaria: lo que depende de "hoy" (el
    seguimiento 7-30-90) lo dice en vez de usar la fecha UTC (0029)."""


def get_timezone(conn: psycopg.Connection, tenant_id: str) -> str | None:
    """Zona horaria IANA de la organizacion. `None` si no esta configurada."""
    with conn.cursor() as cur:
        cur.execute("SELECT config ->> %s FROM tenant WHERE id = %s", (TIMEZONE_KEY, tenant_id))
        row = cur.fetchone()
    return row[0] if row else None


def set_timezone(conn: psycopg.Connection, tenant_id: str, name: str) -> None:
    try:
        ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        raise ValueError(f"Zona horaria desconocida: {name!r} (use un nombre IANA, p. ej. America/Guayaquil)") from None
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE tenant SET config = config || jsonb_build_object(%s::text, %s::text) WHERE id = %s",
            (TIMEZONE_KEY, name, tenant_id),
        )
        if cur.rowcount == 0:
            raise LookupError(f"No existe el tenant {tenant_id}")


def tenant_today(conn: psycopg.Connection, tenant_id: str) -> date:
    """Fecha de hoy en la zona horaria de la organizacion."""
    name = get_timezone(conn, tenant_id)
    if not name:
        raise TimezoneNotConfiguredError(
            "La organización no tiene zona horaria. Defínala en Configuración → Zona horaria."
        )
    return datetime.now(ZoneInfo(name)).date()


def get_hes_settings(conn: psycopg.Connection, tenant_id: str) -> dict[str, Any]:
    return {"stale_after_seconds": get_meter_stale_after_seconds(conn, tenant_id)}
