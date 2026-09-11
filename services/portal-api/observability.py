"""Panel de observabilidad minimo (F34, Sprint 9): metricas de ingesta por
medidor + alertas de caida (un medidor que dejo de reportar).

Nada de umbral fijo: `stale_after_seconds` (cuanto tiempo sin una lectura
cuenta como "caido") llega por parametro -- distinto para un medidor que
deberia reportar cada 15 minutos que para uno que reporta cada hora.
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))

import psycopg  # noqa: E402

from renmeter_common.db import tenant_scope  # noqa: E402


def ingestion_metrics(conn: psycopg.Connection, tenant_id: str, stale_after_seconds: int) -> dict:
    """Por medidor: cuantas lecturas reales llegaron en las ultimas 24h,
    cuando fue la ultima, y si esta "caido" (sin lectura hace mas de
    `stale_after_seconds`). Un medidor sin ninguna lectura nunca (nuevo,
    recien registrado) no cuenta como caido -- no hay con que compararlo
    todavia, no se adivina una alerta sin datos.

    `brand`/`model`/`gateway_name` (Sprint C7, G4/G5): la fila ya existia,
    solo le faltaba mostrar de que marca es y a que concentrador esta
    enlazado -- el gap real que encontro el benchmark E2E, no un dato
    nuevo que haya que capturar."""
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT m.id, m.account_number, m.brand, m.model, g.name, "
                    "  (SELECT count(*) FROM raw_reading r WHERE r.meter_id = m.id AND r.\"timestamp\" > now() - interval '24 hours') AS readings_24h, "
                    "  (SELECT max(r.\"timestamp\") FROM raw_reading r WHERE r.meter_id = m.id) AS last_reading_at, "
                    "  (SELECT count(*) FROM meter_event e WHERE e.meter_id = m.id AND e.type = 'communication_failure' "
                    "     AND e.\"timestamp\" > now() - interval '24 hours') AS communication_failures_24h "
                    "FROM meter m "
                    "LEFT JOIN meter_gateway mg ON mg.meter_id = m.id "
                    "LEFT JOIN gateway g ON g.id = mg.gateway_id "
                    "WHERE m.status = 'active'"
                )
                rows = cur.fetchall()

    now = datetime.now(timezone.utc)
    meters = []
    alerts = []
    for meter_id, account_number, brand, model, gateway_name, readings_24h, last_reading_at, failures_24h in rows:
        is_stale = last_reading_at is not None and (now - last_reading_at).total_seconds() > stale_after_seconds
        meter_metrics = {
            "meter_id": str(meter_id),
            "account_number": account_number,
            "brand": brand,
            "model": model,
            "gateway_name": gateway_name,
            "readings_24h": readings_24h,
            "last_reading_at": last_reading_at.isoformat() if last_reading_at else None,
            "communication_failures_24h": failures_24h,
            "is_stale": is_stale,
        }
        meters.append(meter_metrics)
        if is_stale:
            alerts.append(
                {
                    "meter_id": str(meter_id),
                    "account_number": account_number,
                    "type": "ingestion_stale",
                    "detail": f"Sin lectura desde {last_reading_at.isoformat()} (umbral: {stale_after_seconds}s)",
                }
            )

    return {"meters": meters, "alerts": alerts}
