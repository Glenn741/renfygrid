"""Panel unificado de "Service Orders" (Sprint C5, F51-adyacente, ver
`docs/06-benchmark-e2e-y-brechas.md` SS2/G3) -- el termino real de
industria para "el CIS pide o dispara algo sobre un medidor" (Oracle
Service Order Management: connect/disconnect/ping/lectura bajo demanda,
todas orquestadas por el MDM y rastreadas como una sola cosa).

RenfyGrid ya tenia la mecanica repartida en dos lugares sin unificar:
`control_order` (suspension/reconexion/desconexion, con su propio flujo de
aprobacion) y las lecturas bajo demanda/pings (auditados en `meter_event`
desde Sprint 9, F09). Esta funcion los junta en un solo feed ordenado por
tiempo -- no crea ninguna tabla nueva, solo lee las dos que ya existen con
la convencion de `requested_by` que agrego este mismo sprint
(`auth_dependency.requested_by_label`).
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))

import psycopg  # noqa: E402

from renmeter_common.db import tenant_scope  # noqa: E402


def _origin(requested_by: str | None) -> str:
    if not requested_by:
        return "desconocido"
    prefix = requested_by.split(":", 1)[0]
    return {"cis": "CIS externo", "portal": "Portal (operador)", "system": "Sistema"}.get(prefix, "desconocido")


def list_service_orders(conn: psycopg.Connection, tenant_id: str, limit: int = 50) -> list[dict]:
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT co.id, co.type, co.meter_id, m.account_number, co.status, "
                    "       co.requested_by, co.approved_by, co.requested_at "
                    "FROM control_order co JOIN meter m ON m.id = co.meter_id "
                    "WHERE co.tenant_id = %s ORDER BY co.requested_at DESC LIMIT %s",
                    (tenant_id, limit),
                )
                orders = cur.fetchall()

                cur.execute(
                    "SELECT me.id, me.type, me.meter_id, m.account_number, me.severity, "
                    "       me.detail, me.\"timestamp\" "
                    "FROM meter_event me JOIN meter m ON m.id = me.meter_id "
                    "WHERE me.tenant_id = %s AND me.detail->>'operation' IN ('on_demand_read', 'ping') "
                    "ORDER BY me.\"timestamp\" DESC LIMIT %s",
                    (tenant_id, limit),
                )
                comm_events = cur.fetchall()

    rows: list[dict] = []
    for row in orders:
        order_id, order_type, meter_id, account_number, status, requested_by, approved_by, requested_at = row
        # Automatico: el propio sistema aprobo sin humano de por medio
        # (`control_service.request_order`, Sprint 6). Manual: espera o
        # espero aprobacion humana.
        mode = "automatico" if approved_by == "system:auto_approval" else "manual"
        rows.append(
            {
                "kind": "control_order",
                "id": str(order_id),
                "type": order_type,
                "meter_id": str(meter_id),
                "account_number": account_number,
                "status": status,
                "requested_by": requested_by,
                "origin": _origin(requested_by),
                "mode": mode,
                "timestamp": requested_at.isoformat() if requested_at else None,
            }
        )

    for row in comm_events:
        event_id, event_type, meter_id, account_number, severity, detail, timestamp = row
        operation = detail.get("operation") if detail else None
        requested_by = detail.get("requested_by") if detail else None
        rows.append(
            {
                "kind": "on_demand_read" if operation == "on_demand_read" else "ping",
                "id": str(event_id),
                "type": operation,
                "meter_id": str(meter_id),
                "account_number": account_number,
                "status": "completada" if event_type == "communication_success" else "fallida",
                "requested_by": requested_by,
                "origin": _origin(requested_by),
                "mode": "automatico",  # lecturas/pings no pasan por aprobacion humana, ver docs
                "timestamp": timestamp.isoformat() if timestamp else None,
            }
        )

    rows.sort(key=lambda r: r["timestamp"] or "", reverse=True)
    return rows[:limit]
