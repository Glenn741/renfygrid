"""API interna de consulta de consumo por periodo (F24, Sprint 5).

"API" aca es un contrato de funcion Python entre servicios (ver
docs/03-diseno.md SS3, "Contratos de API entre servicios") -- todavia no hay
Portal/API HTTP publica (eso es Sprint 8, F33); este es el mismo nivel de
API interna que ya usan el resto de los servicios de RenfyGrid entre si.
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))

import psycopg  # noqa: E402
from psycopg.types.range import Range  # noqa: E402

from renmeter_common.db import tenant_scope  # noqa: E402


def get_consumption(
    conn: psycopg.Connection,
    tenant_id: str,
    meter_id: str | None = None,
    period_start: date | None = None,
    period_end: date | None = None,
) -> list[dict]:
    """Sin filtros, devuelve todo el consumo del tenant. Con `period_start`/
    `period_end`, solo los periodos que se solapan con ese rango (operador
    `&&` de rangos de Postgres) -- con `meter_id`, solo ese medidor."""
    clauses = ["tenant_id = %s"]
    params: list = [tenant_id]

    if meter_id is not None:
        clauses.append("meter_id = %s")
        params.append(meter_id)
    if period_start is not None and period_end is not None:
        clauses.append("period && %s")
        params.append(Range(period_start, period_end, bounds="[)"))

    query = (
        "SELECT meter_id, period, value, anomaly_status, created_at FROM consumption "
        f"WHERE {' AND '.join(clauses)} ORDER BY period"
    )
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(query, params)
                return [
                    {
                        "meter_id": str(row[0]),
                        "period": row[1],
                        "value": float(row[2]),
                        "anomaly_status": row[3],
                        "created_at": row[4],
                    }
                    for row in cur.fetchall()
                ]
