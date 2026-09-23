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
from pathlib import Path
from typing import Any

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


def get_hes_settings(conn: psycopg.Connection, tenant_id: str) -> dict[str, Any]:
    return {"stale_after_seconds": get_meter_stale_after_seconds(conn, tenant_id)}
