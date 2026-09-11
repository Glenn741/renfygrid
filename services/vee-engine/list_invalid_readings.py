"""Cola de excepciones de VEE (F49, Sprint C2): lecturas `validated_reading`
con `is_valid = false`, trazables a la regla que las marco (F19). Mismo
principio "exception-first" que el resto del Portal Web -- esto ES la
pantalla de Validacion de Nivel 2, no una tabla generica.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))

import psycopg  # noqa: E402

from renmeter_common.db import tenant_scope  # noqa: E402


def list_invalid_readings(conn: psycopg.Connection, tenant_id: str, limit: int = 100) -> list[dict]:
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT vr.meter_id, m.account_number, vr.channel, vr.\"timestamp\", vr.value, "
                    "       vr.vee_rule_id, vr.validation_notes "
                    "FROM validated_reading vr JOIN meter m ON m.id = vr.meter_id "
                    "WHERE vr.tenant_id = %s AND vr.is_valid = false "
                    "ORDER BY vr.\"timestamp\" DESC LIMIT %s",
                    (tenant_id, limit),
                )
                return [
                    {
                        "meter_id": str(row[0]),
                        "account_number": row[1],
                        "channel": row[2],
                        "timestamp": row[3].isoformat(),
                        "value": float(row[4]),
                        "vee_rule_id": str(row[5]) if row[5] else None,
                        "validation_notes": row[6],
                    }
                    for row in cur.fetchall()
                ]
