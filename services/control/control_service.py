"""Orquestacion del flujo de control (SCR) -- F26/F27 (Sprint 6: solicitud,
aprobacion), F28/F29/F30 (Sprint 7: firma, ejecucion real via adaptador HES,
confirmacion).

Cada transicion de estado escribe una fila en `control_order_audit`
(inmutable a nivel de Postgres desde la migracion 0007 -- ver
docs/03-diseno.md SS6, punto 3) ademas de actualizar `control_order.status`.

El modulo SCR "unicamente habla con los adaptadores HES"
(docs/02-arquitectura-general.md SS6, punto 4) -- `send_and_execute_order`
importa `hes-adapter-dlms/control_executor.py` directo (sin bus todavia,
igual que el resto de RenfyGrid hasta ahora), nunca abre un socket DLMS por
su cuenta.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "hes-adapter-dlms"))

import psycopg  # noqa: E402

from control_engine import approval_level_for, can_approve, status_after_request  # noqa: E402
from control_executor import dispatch_control_order  # noqa: E402
from order_signing import sign_order  # noqa: E402
from renmeter_common.db import tenant_scope  # noqa: E402


class InvalidTransitionError(RuntimeError):
    """La orden no esta en el estado desde el que se puede hacer esta transicion."""


class InsufficientRoleError(RuntimeError):
    """El rol de quien intenta aprobar no alcanza el minimo configurado para este tipo de orden."""


def _write_audit(cur, tenant_id: str, order_id: str, previous_status: str | None, new_status: str, actor: str, detail: dict | None = None) -> None:
    cur.execute(
        "INSERT INTO control_order_audit (tenant_id, order_id, previous_status, new_status, actor, detail) "
        "VALUES (%s, %s, %s, %s, %s, %s)",
        (tenant_id, order_id, previous_status, new_status, actor, psycopg.types.json.Json(detail) if detail else None),
    )


def request_order(
    conn: psycopg.Connection,
    tenant_id: str,
    meter_id: str,
    order_type: str,
    requested_by: str,
    justification: str,
    approval_levels: list[dict],
) -> str:
    """F26 + el ruteo de F27 en la misma solicitud: la orden nace
    `requested` y de inmediato transiciona a `pending_approval` o, si el
    tenant configuro que este tipo de orden se auto-aprueba, a `approved`
    (actor `system:auto_approval`, trazable en la auditoria igual que
    cualquier otra transicion)."""
    approval = approval_level_for(order_type, approval_levels)
    next_status = status_after_request(approval)

    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO control_order (tenant_id, meter_id, type, status, requested_by, justification) "
                    "VALUES (%s, %s, %s, 'requested', %s, %s) RETURNING id",
                    (tenant_id, meter_id, order_type, requested_by, justification),
                )
                (order_id,) = cur.fetchone()
                order_id = str(order_id)
                _write_audit(cur, tenant_id, order_id, None, "requested", requested_by)

                if next_status == "approved":
                    cur.execute(
                        "UPDATE control_order SET status = 'approved', approved_by = %s, approved_at = now() WHERE id = %s",
                        ("system:auto_approval", order_id),
                    )
                    _write_audit(
                        cur, tenant_id, order_id, "requested", "approved", "system:auto_approval",
                        detail={"reason": "control_approval_level.requires_human_approval = false"},
                    )
                else:
                    cur.execute(
                        "UPDATE control_order SET status = 'pending_approval' WHERE id = %s", (order_id,)
                    )
                    _write_audit(cur, tenant_id, order_id, "requested", "pending_approval", requested_by)
    return order_id


def approve_order(
    conn: psycopg.Connection,
    tenant_id: str,
    order_id: str,
    approver_name: str,
    approver_role: str,
    approval_levels: list[dict],
) -> None:
    """F27: un humano con el rol minimo configurado aprueba una orden que
    esta esperando aprobacion. Rechaza (sin cambiar nada) si la orden no
    esta en `pending_approval`, o si el rol no alcanza."""
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT status, type FROM control_order WHERE id = %s FOR UPDATE", (order_id,)
                )
                row = cur.fetchone()
                if row is None:
                    raise InvalidTransitionError(f"No existe control_order {order_id}")
                status, order_type = row
                if status != "pending_approval":
                    raise InvalidTransitionError(
                        f"La orden {order_id} esta en '{status}', no se puede aprobar (se esperaba 'pending_approval')"
                    )

                approval = approval_level_for(order_type, approval_levels)
                if not can_approve(approver_role, approval):
                    raise InsufficientRoleError(
                        f"El rol '{approver_role}' no alcanza el minimo requerido ('{approval.min_required_role}') para aprobar ordenes de tipo '{order_type}'"
                    )

                cur.execute(
                    "UPDATE control_order SET status = 'approved', approved_by = %s, approved_at = now() WHERE id = %s",
                    (approver_name, order_id),
                )
                _write_audit(cur, tenant_id, order_id, "pending_approval", "approved", approver_name)


def is_ready_to_execute(conn: psycopg.Connection, tenant_id: str, order_id: str) -> bool:
    """F28 (porcion de Sprint 6): una orden solo esta lista para que el
    adaptador HES la ejecute (Sprint 7) si llego a `approved` -- ninguna
    otra combinacion de estado habilita el envio."""
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute("SELECT status FROM control_order WHERE id = %s", (order_id,))
                row = cur.fetchone()
                return row is not None and row[0] == "approved"


def _meter_connection(conn: psycopg.Connection, tenant_id: str, meter_id: str) -> dict | None:
    """Conexion del gateway del medidor + OBIS del objeto de control, desde
    `meter_protocol.obis_mapping['control']` -- mismo mapeo de Sprint 2/5,
    ninguna tabla nueva. None si al medidor le falta cualquiera de las dos
    piezas (no se ejecuta una orden sin saber donde/como)."""
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT m.server_address, g.connection, mp.obis_mapping "
                    "FROM meter m "
                    "JOIN meter_gateway mg ON mg.meter_id = m.id "
                    "JOIN gateway g ON g.id = mg.gateway_id "
                    "JOIN meter_protocol mp ON mp.tenant_id = m.tenant_id "
                    "  AND mp.brand = m.brand AND mp.model = m.model AND mp.valid_to IS NULL "
                    "WHERE m.id = %s",
                    (meter_id,),
                )
                row = cur.fetchone()
                if row is None:
                    return None
                server_address, connection, obis_mapping = row
                control_mapping = obis_mapping.get("control")
                if control_mapping is None:
                    return None
                return {
                    "server_address": server_address,
                    "host": connection["host"],
                    "port": connection["port"],
                    "client_address": connection.get("client_address", 16),
                    "control_obis_code": control_mapping["obis_code"],
                }


def send_and_execute_order(
    conn: psycopg.Connection, tenant_id: str, order_id: str, signing_secret: str
) -> str:
    """F28 (firma) + F29 (ejecucion real via adaptador HES) + F30 (confirmacion):
    firma la orden, transiciona `approved -> sent`, ejecuta el comando DLMS
    real (o contra el simulador, ver docs/05-ejecucion.md Sprint 1) y
    transiciona a `confirmed` o `failed` segun el resultado -- nunca deja la
    orden en `sent` sin resolver. Devuelve el estado final."""
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute("SELECT meter_id, type, status FROM control_order WHERE id = %s FOR UPDATE", (order_id,))
                row = cur.fetchone()
                if row is None:
                    raise InvalidTransitionError(f"No existe control_order {order_id}")
                meter_id, order_type, status = str(row[0]), row[1], row[2]
                if status != "approved":
                    raise InvalidTransitionError(
                        f"La orden {order_id} esta en '{status}', no se puede ejecutar (se esperaba 'approved')"
                    )

                signature = sign_order(order_id, meter_id, order_type, signing_secret)
                cur.execute("UPDATE control_order SET status = 'sent' WHERE id = %s", (order_id,))
                _write_audit(
                    cur, tenant_id, order_id, "approved", "sent", "system:scr_dispatch",
                    detail={"signed": True, "signature_prefix": signature[:8]},
                )

    connection = _meter_connection(conn, tenant_id, meter_id)
    if connection is None:
        return _finish_as_failed(conn, tenant_id, order_id, "No hay conexion de gateway u OBIS de control configurado para este medidor")

    try:
        dispatch_control_order(
            connection["host"], connection["port"], connection["client_address"],
            connection["server_address"], connection["control_obis_code"], order_type,
        )
    except Exception as exc:  # el medidor/concentrador no respondio o rechazo la accion
        return _finish_as_failed(conn, tenant_id, order_id, str(exc))

    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE control_order SET status = 'confirmed', confirmed_at = now() WHERE id = %s", (order_id,)
                )
                _write_audit(cur, tenant_id, order_id, "sent", "confirmed", "system:scr_dispatch")
    return "confirmed"


def _finish_as_failed(conn: psycopg.Connection, tenant_id: str, order_id: str, reason: str) -> str:
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute("UPDATE control_order SET status = 'failed' WHERE id = %s", (order_id,))
                _write_audit(cur, tenant_id, order_id, "sent", "failed", "system:scr_dispatch", detail={"reason": reason})
    return "failed"
