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

from account_protection import is_protected  # noqa: E402
from control_engine import approval_level_for, can_approve, status_after_request  # noqa: E402
from control_executor import dispatch_control_order  # noqa: E402
from order_signing import sign_order  # noqa: E402
from renmeter_common.db import tenant_scope  # noqa: E402

# Tipos de orden que de verdad cortan el servicio -- el chequeo de cuenta
# protegida (Sprint C11-5) aplica solo aca, nunca a 'reconnection' (jamas
# hace falta proteger a alguien de que le reconecten el servicio).
_SUSPENDING_ORDER_TYPES = ("suspension", "disconnection")


class InvalidTransitionError(RuntimeError):
    """La orden no esta en el estado desde el que se puede hacer esta transicion."""


class InsufficientRoleError(RuntimeError):
    """El rol de quien intenta aprobar no alcanza el minimo configurado para este tipo de orden."""


class ProtectedAccountError(RuntimeError):
    """Cuenta marcada como protegida contra suspension/desconexion (Ley 142 +
    normas CRA/CREG u otra norma vigente, Sprint C11-5) -- nunca se aprueba
    en silencio; requiere override explicito con su propia justificacion,
    trazable aparte en la auditoria."""


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
    override_protection: bool = False,
    override_justification: str | None = None,
) -> str:
    """F26 + el ruteo de F27 en la misma solicitud: la orden nace
    `requested` y de inmediato transiciona a `pending_approval` o, si el
    tenant configuro que este tipo de orden se auto-aprueba, a `approved`
    (actor `system:auto_approval`, trazable en la auditoria igual que
    cualquier otra transicion).

    Sprint C11-5: para `suspension`/`disconnection`, primero chequea si la
    cuenta esta en la lista de protegidas -- si lo esta, la solicitud se
    RECHAZA de entrada (nunca llega ni a `requested`) salvo que quien pide
    la orden mande `override_protection=True` CON su propia
    `override_justification` (nunca la misma `justification` del pedido
    original -- el override necesita su propio motivo documentado, para
    que el debido proceso quede trazable de verdad)."""
    protection_override_detail = None
    if order_type in _SUSPENDING_ORDER_TYPES:
        protection = is_protected(conn, tenant_id, meter_id)
        if protection["protected"]:
            if not override_protection or not override_justification:
                raise ProtectedAccountError(
                    f"Cuenta protegida contra suspension/desconexion ({protection['reason'] or 'sin razon registrada'}, "
                    f"marcada por {protection['marked_by']}) -- requiere override explicito con su propia justificacion."
                )
            if override_justification.strip().lower() == justification.strip().lower():
                # No alcanza con repetir el motivo original -- el override
                # necesita su PROPIO motivo (por que se pasa por encima de
                # la proteccion), no la razon original de la suspension.
                raise ProtectedAccountError(
                    "override_justification no puede ser igual a justification -- el override necesita su propio "
                    "motivo documentado (por que se pasa por encima de la proteccion), no repetir el motivo original."
                )
            protection_override_detail = {
                "protection_reason": protection["reason"],
                "protection_marked_by": protection["marked_by"],
                "override_justification": override_justification,
            }

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
                _write_audit(cur, tenant_id, order_id, None, "requested", requested_by, detail=protection_override_detail)

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


def list_control_orders(conn: psycopg.Connection, tenant_id: str, status: str | None = None) -> list[dict]:
    """Cola/historial de ordenes (F49, Sprint C2, pantalla de Control de
    Nivel 2) -- sin `status`, devuelve todas; con `status='pending_approval'`,
    solo la cola de excepciones que de verdad importa ahi."""
    clauses = ["co.tenant_id = %s"]
    params: list = [tenant_id]
    if status is not None:
        clauses.append("co.status = %s")
        params.append(status)

    query = (
        "SELECT co.id, co.meter_id, m.account_number, co.type, co.status, "
        "       co.requested_by, co.justification, co.requested_at, co.approved_by, co.approved_at, "
        "       m.protected_from_suspension "
        "FROM control_order co JOIN meter m ON m.id = co.meter_id "
        f"WHERE {' AND '.join(clauses)} ORDER BY co.requested_at DESC"
    )
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(query, params)
                return [
                    {
                        "order_id": str(row[0]),
                        "meter_id": str(row[1]),
                        "account_number": row[2],
                        "type": row[3],
                        "status": row[4],
                        "requested_by": row[5],
                        "justification": row[6],
                        "requested_at": row[7].isoformat() if row[7] else None,
                        "approved_by": row[8],
                        "approved_at": row[9].isoformat() if row[9] else None,
                        "meter_protected": row[10],
                    }
                    for row in cur.fetchall()
                ]


def control_summary(conn: psycopg.Connection, tenant_id: str) -> dict:
    """KPIs de Control/SCR (Sprint C11-5, benchmark real): "command success
    rates, or retry backlog" es justo el tipo de metrica que un CIS/MDM de
    referencia expone para ordenes de conexion/desconexion remota -- aca
    nunca existia, solo la cola de `pending_approval`."""
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT type, count(*) FROM control_order WHERE tenant_id = %s GROUP BY type",
                    (tenant_id,),
                )
                by_type = dict(cur.fetchall())

                cur.execute(
                    "SELECT status, count(*) FROM control_order WHERE tenant_id = %s GROUP BY status",
                    (tenant_id,),
                )
                by_status = dict(cur.fetchall())

    confirmed = by_status.get("confirmed", 0)
    failed = by_status.get("failed", 0)
    dispatched_total = confirmed + failed
    return {
        "total_orders": sum(by_type.values()),
        "by_type": by_type,
        "by_status": by_status,
        "pending_approval": by_status.get("pending_approval", 0),
        # None (no se ha despachado ninguna todavia), no 0% -- mismo
        # fail-safe que el resto de las tasas de exito del proyecto.
        "command_success_rate_pct": round(100.0 * confirmed / dispatched_total, 1) if dispatched_total else None,
    }


def get_control_order_detail(conn: psycopg.Connection, tenant_id: str, order_id: str) -> dict | None:
    """Nivel 3 (F51, Sprint C4): la orden puntual + su historial de auditoria
    completo -- `control_order_audit` es inmutable (migracion 0007), asi que
    esto es un registro real e intacto de cada transicion, no un resumen."""
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT co.id, co.meter_id, m.account_number, co.type, co.status, "
                    "       co.requested_by, co.justification, co.requested_at, "
                    "       co.approved_by, co.approved_at, co.confirmed_at, m.protected_from_suspension "
                    "FROM control_order co JOIN meter m ON m.id = co.meter_id "
                    "WHERE co.id = %s AND co.tenant_id = %s",
                    (order_id, tenant_id),
                )
                row = cur.fetchone()
                if row is None:
                    return None

                cur.execute(
                    "SELECT previous_status, new_status, actor, \"timestamp\", detail "
                    "FROM control_order_audit WHERE order_id = %s ORDER BY \"timestamp\"",
                    (order_id,),
                )
                audit = [
                    {
                        "previous_status": audit_row[0],
                        "new_status": audit_row[1],
                        "actor": audit_row[2],
                        "timestamp": audit_row[3].isoformat(),
                        "detail": audit_row[4],
                    }
                    for audit_row in cur.fetchall()
                ]

    return {
        "order_id": str(row[0]),
        "meter_id": str(row[1]),
        "account_number": row[2],
        "type": row[3],
        "status": row[4],
        "requested_by": row[5],
        "justification": row[6],
        "requested_at": row[7].isoformat() if row[7] else None,
        "approved_by": row[8],
        "approved_at": row[9].isoformat() if row[9] else None,
        "confirmed_at": row[10].isoformat() if row[10] else None,
        "meter_protected": row[11],
        "audit": audit,
    }
