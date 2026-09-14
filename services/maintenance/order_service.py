"""Servicio de Gestion de Mantenimiento (Track B, Sprint B7, F44/F45,
`docs/07-track-b-alcance-funcional.md` SS5) -- genera `maintenance_order`
desde una anomalia REAL (nunca sin verificar la condicion que la motiva)
y la integra con BayForce, ya en el portafolio (`core/renflow/bayforce`).

Reglas de generacion (Sprint B7, verificadas contra datos reales antes de
insertar, nunca "porque el operador lo pidio" sin mas para las fuentes
automaticas):
  - `asset_condition`: el activo debe estar realmente `out_of_service` o
    `maintenance` en este momento (`network_asset.status`).
  - `balance_anomaly`: la zona del activo debe tener un balance reciente
    con `exceeds_threshold = True` (Sprint B1-2/B4) -- el activo tiene que
    estar vinculado a una zona (`zone_id`), si no hay nada que verificar.
  - `simulation_result`: la validacion automatica contra una corrida real
    (presion fuera de rango) queda para un sprint futuro -- por ahora se
    acepta igual que `manual` (una persona la respalda), documentado, no
    una promesa incumplida en silencio.
  - `manual`: sin precondicion -- juicio humano explicito, no hay una
    "anomalia" que verificar por codigo.

Integracion BayForce: HTTP real (POST JSON) contra un webhook
CONFIGURABLE (`RENFYGRID_BAYFORCE_WEBHOOK_URL`, nunca una URL fija en
codigo) -- BayForce es un sistema externo con su propia base de datos
(MySQL, `core/renflow/bayforce/database.py`), la integracion es por HTTP,
no una tabla compartida. El cierre llega por el MISMO mecanismo de
autenticacion que ya usa el portal para un CIS externo (JWT del tenant,
`auth_dependency.requested_by_label`, ver `service_orders.py`) -- no se
inventa un esquema de firma nuevo para esto.
"""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))

import psycopg  # noqa: E402

from renmeter_common.db import tenant_scope  # noqa: E402

ORDER_TYPES = {"preventive", "corrective", "inspection"}
ORDER_SOURCES = {"asset_condition", "simulation_result", "balance_anomaly", "manual"}

# generated -> sent_to_bayforce -> in_progress -> completed | cancelled
# (mismo comentario de estados que ya trae `0001_init.sql` en `maintenance_order`).
ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "generated": {"sent_to_bayforce"},
    "sent_to_bayforce": {"in_progress", "cancelled"},
    "in_progress": {"completed", "cancelled"},
    "completed": set(),
    "cancelled": set(),
}


class InvalidOrderTypeError(ValueError):
    """`type` fuera de los 3 tipos reales (`0001_init.sql`)."""


class InvalidOrderSourceError(ValueError):
    """`source` fuera de las 4 fuentes reales."""


class AssetNotFoundError(LookupError):
    """No existe ese `network_asset` para este tenant."""


class AnomalyNotConfirmedError(ValueError):
    """La condicion real que justificaria esta orden NO se cumple ahora
    mismo (activo operativo, o zona sin balance que exceda su tope) --
    nunca se genera una orden "porque si" para una fuente automatica."""


class OrderNotFoundError(LookupError):
    """No existe esa `maintenance_order` (o ese `bayforce_order_ref`) para
    este tenant."""


class InvalidStatusTransitionError(ValueError):
    """La transicion de estado pedida no es valida desde el estado actual
    -- ver `ALLOWED_TRANSITIONS`."""


class BayforceNotConfiguredError(ValueError):
    """No hay `RENFYGRID_BAYFORCE_WEBHOOK_URL` configurado para este
    despliegue -- nunca se simula un envio que no ocurrio."""


class BayforceIntegrationError(RuntimeError):
    """BayForce respondio con un error real, o una respuesta que no se
    pudo interpretar -- se propaga el detalle real, nunca un exito
    fabricado."""


def _asset_row(conn: psycopg.Connection, tenant_id: str, asset_id: str) -> tuple[str, str | None]:
    """`(status, zone_id)` del activo -- `AssetNotFoundError` si no existe
    para este tenant."""
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT status, zone_id FROM network_asset WHERE id = %s AND tenant_id = %s",
                    (asset_id, tenant_id),
                )
                row = cur.fetchone()
    if row is None:
        raise AssetNotFoundError(f"No existe el activo {asset_id} para este tenant")
    return row[0], (str(row[1]) if row[1] else None)


def _zone_exceeds_threshold(conn: psycopg.Connection, tenant_id: str, zone_id: str) -> bool:
    """`exceeds_threshold` del balance mas reciente (por periodo, luego
    version) de esa zona -- `False` si la zona no tiene ningun balance
    (nunca se asume que excede sin datos reales)."""
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT exceeds_threshold FROM network_balance WHERE tenant_id = %s AND zone_id = %s "
                    "ORDER BY upper(period) DESC, version DESC LIMIT 1",
                    (tenant_id, zone_id),
                )
                row = cur.fetchone()
    return bool(row and row[0] is True)


def generate_order(
    conn: psycopg.Connection,
    tenant_id: str,
    asset_id: str,
    order_type: str,
    source: str,
    reason: str | None = None,
) -> dict[str, Any]:
    """Genera una orden real -- valida la anomalia real para las fuentes
    automaticas ANTES de insertar (`AnomalyNotConfirmedError` si no se
    cumple), nunca una orden fabricada sin condicion real detras."""
    if order_type not in ORDER_TYPES:
        raise InvalidOrderTypeError(f"Tipo de orden invalido: {order_type!r} (validos: {sorted(ORDER_TYPES)})")
    if source not in ORDER_SOURCES:
        raise InvalidOrderSourceError(f"Fuente de orden invalida: {source!r} (validos: {sorted(ORDER_SOURCES)})")

    status, zone_id = _asset_row(conn, tenant_id, asset_id)

    if source == "asset_condition":
        if status not in ("out_of_service", "maintenance"):
            raise AnomalyNotConfirmedError(
                f"El activo {asset_id} esta '{status}' -- no hay condicion real que justifique una orden por 'asset_condition'"
            )
    elif source == "balance_anomaly":
        if zone_id is None:
            raise AnomalyNotConfirmedError(f"El activo {asset_id} no esta vinculado a ninguna zona -- nada que verificar")
        if not _zone_exceeds_threshold(conn, tenant_id, zone_id):
            raise AnomalyNotConfirmedError(
                f"La zona {zone_id} del activo {asset_id} no tiene ningun balance que exceda su tope regulatorio ahora mismo"
            )
    # 'simulation_result' y 'manual': sin precondicion automatica en esta v1 (ver docstring del modulo).

    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO maintenance_order (tenant_id, asset_id, type, source, status, reason) "
                    "VALUES (%s, %s, %s, %s, 'generated', %s) RETURNING id, created_at",
                    (tenant_id, asset_id, order_type, source, reason),
                )
                (order_id, created_at) = cur.fetchone()
    return {
        "order_id": str(order_id), "asset_id": asset_id, "type": order_type, "source": source,
        "status": "generated", "reason": reason, "bayforce_order_ref": None, "created_at": created_at.isoformat(),
    }


def _order_row_to_dict(row: tuple) -> dict[str, Any]:
    return {
        "order_id": str(row[0]), "asset_id": str(row[1]), "type": row[2], "source": row[3],
        "status": row[4], "bayforce_order_ref": row[5], "reason": row[6], "created_at": row[7].isoformat(),
    }


def list_orders(conn: psycopg.Connection, tenant_id: str, status: str | None = None, asset_id: str | None = None) -> list[dict]:
    clauses = []
    params: list[Any] = [tenant_id]
    if status:
        clauses.append("AND status = %s")
        params.append(status)
    if asset_id:
        clauses.append("AND asset_id = %s")
        params.append(asset_id)
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT id, asset_id, type, source, status, bayforce_order_ref, reason, created_at "
                    f"FROM maintenance_order WHERE tenant_id = %s {' '.join(clauses)} ORDER BY created_at DESC",
                    params,
                )
                rows = cur.fetchall()
    return [_order_row_to_dict(row) for row in rows]


def get_order_detail(conn: psycopg.Connection, tenant_id: str, order_id: str) -> dict[str, Any]:
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id, asset_id, type, source, status, bayforce_order_ref, reason, created_at "
                    "FROM maintenance_order WHERE id = %s AND tenant_id = %s",
                    (order_id, tenant_id),
                )
                row = cur.fetchone()
    if row is None:
        raise OrderNotFoundError(f"No existe la orden {order_id} para este tenant")
    return _order_row_to_dict(row)


def _post_json(url: str, payload: dict, timeout: float = 10.0) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 -- URL siempre configurable, nunca del usuario final
            body = resp.read()
    except (urllib.error.URLError, TimeoutError) as exc:
        raise BayforceIntegrationError(f"No se pudo contactar BayForce ({url}): {exc}") from exc
    try:
        return json.loads(body)
    except json.JSONDecodeError as exc:
        raise BayforceIntegrationError(f"Respuesta invalida de BayForce (no es JSON): {body[:200]!r}") from exc


def send_to_bayforce(conn: psycopg.Connection, tenant_id: str, order_id: str, webhook_url: str | None) -> dict[str, Any]:
    """Envia la orden real a BayForce (HTTP real, `POST` al webhook
    configurado) -- `BayforceNotConfiguredError` si no hay URL (nunca se
    simula un envio); `BayforceIntegrationError` si BayForce no responde
    o responde algo no interpretable; `InvalidStatusTransitionError` si la
    orden no esta en `generated` (nunca se reenvia una orden ya en curso)."""
    if not webhook_url:
        raise BayforceNotConfiguredError(
            "RENFYGRID_BAYFORCE_WEBHOOK_URL no esta configurado para este despliegue -- no se puede enviar a BayForce"
        )
    order = get_order_detail(conn, tenant_id, order_id)
    if "sent_to_bayforce" not in ALLOWED_TRANSITIONS.get(order["status"], set()):
        raise InvalidStatusTransitionError(f"La orden {order_id} esta '{order['status']}', no se puede enviar a BayForce desde ahi")

    response = _post_json(webhook_url, {
        "renfygrid_order_id": order["order_id"], "tenant_id": tenant_id, "asset_id": order["asset_id"],
        "type": order["type"], "source": order["source"], "reason": order["reason"],
    })
    bayforce_ref = response.get("bayforce_order_ref")
    if not bayforce_ref:
        raise BayforceIntegrationError(f"BayForce no devolvio 'bayforce_order_ref' en su respuesta: {response!r}")

    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE maintenance_order SET status = 'sent_to_bayforce', bayforce_order_ref = %s "
                    "WHERE id = %s AND tenant_id = %s",
                    (bayforce_ref, order_id, tenant_id),
                )
    return {"order_id": order_id, "status": "sent_to_bayforce", "bayforce_order_ref": bayforce_ref}


def close_from_webhook(conn: psycopg.Connection, tenant_id: str, bayforce_order_ref: str, new_status: str) -> dict[str, Any]:
    """BayForce (o el modulo de integraciones que ya recibe sus webhooks,
    ver `core/renflow/bayforce/main.py` `/wfms/events`) llama aca para
    avanzar el estado real de la orden -- `InvalidStatusTransitionError`
    si el salto no es valido desde el estado actual (nunca se acepta
    cualquier transicion)."""
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id, status FROM maintenance_order WHERE tenant_id = %s AND bayforce_order_ref = %s",
                    (tenant_id, bayforce_order_ref),
                )
                row = cur.fetchone()
    if row is None:
        raise OrderNotFoundError(f"No existe ninguna orden con bayforce_order_ref={bayforce_order_ref!r} para este tenant")
    order_id, current_status = str(row[0]), row[1]
    if new_status not in ALLOWED_TRANSITIONS.get(current_status, set()):
        raise InvalidStatusTransitionError(f"La orden {order_id} esta '{current_status}', no puede pasar a '{new_status}'")

    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE maintenance_order SET status = %s WHERE id = %s AND tenant_id = %s",
                    (new_status, order_id, tenant_id),
                )
    return {"order_id": order_id, "status": new_status, "bayforce_order_ref": bayforce_order_ref}
