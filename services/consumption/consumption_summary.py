"""Panel real de Gestion de Consumos (Sprint C11-6, mismo benchmark real
que ya se hizo para VEE/HES/Control): "MDMS reporting and analytics covers
six operational outputs: billing validation reports, usage exception
reports, VEE summary reports, TOU and demand rate consumption reports,
non-revenue loss analysis, and customer usage trend reports" (Bynry --
docs/05-ejecucion.md Sprint C11-6 tiene la fuente completa). La pantalla
de Consumos solo mostraba la cola de `under_review`, sin resumen, sin las
ordenes de relectura/inspeccion visibles (F23, ya se generaban en
`meter_event` desde Sprint 5), y sin forma de CERRAR una anomalia ya
investigada -- `anomaly_status='resolved'` existia en el esquema desde el
dia 1 pero nada lo escribia nunca.
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


class ConsumptionNotFoundError(LookupError):
    """No existe un consumo `under_review` para ese medidor/periodo en este tenant."""


def consumption_summary(conn: psycopg.Connection, tenant_id: str) -> dict:
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT anomaly_status, count(*) FROM consumption WHERE tenant_id = %s GROUP BY anomaly_status",
                    (tenant_id,),
                )
                by_status = dict(cur.fetchall())

                cur.execute(
                    "SELECT type, count(*) FROM meter_event WHERE tenant_id = %s "
                    "AND type IN ('reread_order', 'inspection_order') GROUP BY type",
                    (tenant_id,),
                )
                orders_by_action = dict(cur.fetchall())

    total = sum(by_status.values())
    under_review = by_status.get("under_review", 0)
    return {
        "total_processed": total,
        "by_status": by_status,
        "orders_by_action": orders_by_action,
        # None (nada procesado todavia), no 0% -- mismo fail-safe que el
        # resto de las tasas del proyecto.
        "anomaly_rate_pct": round(100.0 * under_review / total, 1) if total else None,
        "billing_ready_pct": round(100.0 * (total - under_review) / total, 1) if total else None,
    }


def list_consumption_orders(conn: psycopg.Connection, tenant_id: str, limit: int = 100) -> list[dict]:
    """Feed real de las ordenes de relectura/inspeccion (F23) -- vivian
    solo en `meter_event`, invisibles en el Portal desde que se
    construyeron en Sprint 5."""
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT e.meter_id, m.account_number, e.type, e.\"timestamp\", "
                    "       c.period, c.value, c.anomaly_status "
                    "FROM meter_event e "
                    "JOIN consumption c ON c.id = e.consumption_id "
                    "JOIN meter m ON m.id = e.meter_id "
                    "WHERE e.tenant_id = %s AND e.type IN ('reread_order', 'inspection_order') "
                    "ORDER BY e.\"timestamp\" DESC LIMIT %s",
                    (tenant_id, limit),
                )
                rows = cur.fetchall()

    return [
        {
            "meter_id": str(meter_id),
            "account_number": account_number,
            "action": action,
            "timestamp": timestamp.isoformat(),
            "period": str(period),
            "value": float(value),
            "anomaly_status": anomaly_status,
        }
        for meter_id, account_number, action, timestamp, period, value, anomaly_status in rows
    ]


def resolve_anomaly(
    conn: psycopg.Connection,
    tenant_id: str,
    meter_id: str,
    period_start: date,
    period_end: date,
    resolved_by: str,
    notes: str,
) -> None:
    """Cierra una anomalia investigada -- `anomaly_status` pasa de
    `under_review` a `resolved` (el estado ya existia en el esquema desde
    Sprint 0, nunca se escribia). Deja rastro real en `meter_event`
    (`type='anomaly_resolved'`, mismo principio de reusar la tabla que ya
    usa F23) -- nunca se sobre-escribe en silencio."""
    period = Range(period_start, period_end, bounds="[)")
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE consumption SET anomaly_status = 'resolved' "
                    "WHERE tenant_id = %s AND meter_id = %s AND period = %s AND anomaly_status = 'under_review' "
                    "RETURNING id",
                    (tenant_id, meter_id, period),
                )
                row = cur.fetchone()
                if row is None:
                    raise ConsumptionNotFoundError(
                        f"No hay un consumo 'under_review' para meter_id={meter_id}, periodo={period} en este tenant"
                    )
                (consumption_id,) = row
                cur.execute(
                    "INSERT INTO meter_event (tenant_id, meter_id, type, severity, detail, consumption_id) "
                    "VALUES (%s, %s, 'anomaly_resolved', 'info', %s, %s)",
                    (tenant_id, meter_id, psycopg.types.json.Json({"resolved_by": resolved_by, "notes": notes}), consumption_id),
                )
