"""Edicion manual auditada de una lectura validada (F18, Sprint 4).

`validated_reading.value` SI se actualiza in place (source pasa a 'edited')
-- lo que nunca se puede tocar ni borrar es el rastro de la edicion en
`validated_reading_edit`: esa tabla tiene UPDATE/DELETE revocados al rol de
aplicacion a nivel de BD (migracion 0005), no solo por convencion de codigo.

`user_name` y `justification` son obligatorios (columnas NOT NULL) --
`edit_reading` no acepta editar sin ambos, para que no exista un cambio de
historial sin quien y por que quedar registrado (docs/03-diseno.md SS5).
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))

import psycopg  # noqa: E402

from renmeter_common.db import tenant_scope  # noqa: E402


class ReadingNotFoundError(LookupError):
    """No existe una lectura validada para ese (medidor, canal, timestamp)."""


def edit_reading(
    conn: psycopg.Connection,
    tenant_id: str,
    meter_id: str,
    channel: str,
    timestamp,
    new_value: float,
    user_name: str,
    justification: str,
) -> None:
    if not user_name or not justification:
        raise ValueError("user_name y justification son obligatorios para editar una lectura.")

    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id, value FROM validated_reading "
                    "WHERE meter_id = %s AND channel = %s AND \"timestamp\" = %s "
                    "FOR UPDATE",
                    (meter_id, channel, timestamp),
                )
                row = cur.fetchone()
                if row is None:
                    raise ReadingNotFoundError(
                        f"No hay validated_reading para meter_id={meter_id} channel={channel} timestamp={timestamp}"
                    )
                reading_id, previous_value = row

                cur.execute(
                    "UPDATE validated_reading SET value = %s, source = 'edited' WHERE id = %s",
                    (new_value, reading_id),
                )
                cur.execute(
                    "INSERT INTO validated_reading_edit "
                    "(tenant_id, validated_reading_id, previous_value, new_value, user_name, justification) "
                    "VALUES (%s, %s, %s, %s, %s, %s)",
                    (tenant_id, reading_id, previous_value, new_value, user_name, justification),
                )
