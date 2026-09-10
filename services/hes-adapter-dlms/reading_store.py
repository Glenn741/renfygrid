"""Inserta una lectura normalizada en raw_reading, dentro del contexto RLS del
tenant -- reusa renmeter_common.db.tenant_scope (services/common), el mismo
patron ya verificado en infra/db/verify_rls.py.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))

import psycopg  # noqa: E402

from renmeter_common.db import tenant_scope  # noqa: E402

from meter_reader import NormalizedReading  # noqa: E402


def insert_raw_reading(conn: psycopg.Connection, tenant_id: str, reading: NormalizedReading) -> None:
    row = reading.as_row()
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO raw_reading "
                    '(tenant_id, meter_id, "timestamp", channel, value, source_quality) '
                    "VALUES (%s, %s, %s, %s, %s, %s)",
                    (
                        tenant_id,
                        row["meter_id"],
                        row["timestamp"],
                        row["channel"],
                        row["value"],
                        row["source_quality"],
                    ),
                )
