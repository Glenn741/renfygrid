"""Preparación de datos para facturación, entrega a CIS (F25, Sprint 10).

Alcance real, honesto: sin un CIS concreto elegido para el piloto, no hay
un contrato de integración real que implementar (formato de archivo,
SFTP/API, campos exactos que ese CIS espera) -- eso se define CON el CIS
real, no antes. Lo que sí se puede construir ahora es un export genérico
y razonable (CSV, un renglón por consumo facturable) que sirve de punto de
partida y que un CIS real probablemente pueda ingerir con un mapeo de
columnas mínimo.

Regla de negocio explícita: un consumo `anomaly_status='under_review'`
(F22, una desviación que disparó una orden de relectura/inspección, F23)
NO se incluye -- no se factura un consumo bajo revisión sin resolver.
"""

from __future__ import annotations

import csv
import io
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))

import psycopg  # noqa: E402

from renmeter_common.db import tenant_scope  # noqa: E402

CSV_COLUMNS = ["account_number", "meter_id", "period_start", "period_end", "consumption_value", "unit"]


def billing_ready_consumption(
    conn: psycopg.Connection, tenant_id: str, period_start: date, period_end: date
) -> list[dict]:
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT m.account_number, c.meter_id, lower(c.period), upper(c.period), c.value "
                    "FROM consumption c JOIN meter m ON m.id = c.meter_id "
                    "WHERE c.tenant_id = %s AND c.period && daterange(%s, %s, '[)') "
                    "AND c.anomaly_status != 'under_review' "
                    "ORDER BY m.account_number, c.period",
                    (tenant_id, period_start, period_end),
                )
                return [
                    {
                        "account_number": row[0], "meter_id": str(row[1]),
                        "period_start": row[2].isoformat(), "period_end": row[3].isoformat(),
                        "consumption_value": float(row[4]), "unit": "kWh",
                    }
                    for row in cur.fetchall()
                ]


def to_csv(rows: list[dict]) -> str:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=CSV_COLUMNS)
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue()
