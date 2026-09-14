"""Servicio de Gestion de Mantenimiento (Track B, Sprint B7 + CMMS real
2026-09-14, `docs/04-plan-sprints.md` SS9 y `docs/05-ejecucion.md`) --
genera `maintenance_order` desde una anomalia REAL (nunca sin verificar
la condicion que la motiva), la programa/asigna/cierra con sustancia
real de CMMS (prioridad/SLA, codigos de falla, mantenimiento preventivo
programado, KPIs), y opcionalmente la notifica a BayForce.

Hallazgo real que motivo esta ronda (ver [[reference-bayforce-no-generic-intake-api]]
en la memoria del proyecto, y `contextos/renflow/docs/
BAYFORCE_RENFYGRID_INTEGRATION_NOTE.md`): BayForce no tiene ningun
endpoint de creacion de orden externa generico -- la integracion via
`RENFYGRID_BAYFORCE_WEBHOOK_URL` nunca tuvo un contrato real del otro
lado. Por eso BayForce se mantiene como notificacion de salida OPCIONAL
(exactamente el mismo webhook de B7, sin cambios de comportamiento), y el
ciclo de vida REAL de la orden vive en RenfyGrid: `generated -> scheduled
-> assigned -> in_progress -> completed | cancelled` (mas el ramal
opcional `generated -> sent_to_bayforce -> in_progress -> ...` para quien
si tenga un BayForce real configurado).

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
  - `pm_schedule` (nuevo): generada por `generate_due_pm_orders()` cuando
    un `maintenance_pm_plan` real vence -- nunca a mano con este source.
  - `manual`: sin precondicion -- juicio humano explicito, no hay una
    "anomalia" que verificar por codigo.

SLA: `sla_due_at` se calcula al generar la orden desde
`maintenance_sla_policy(tenant_id, priority)` -- si el tenant no
configuro una politica para esa prioridad, `sla_due_at` queda NULL (nunca
una fecha limite fabricada sin un target real detras, ver
`maintenance_engine.compute_sla_due_at`).

Integracion BayForce: HTTP real (POST JSON) contra un webhook
CONFIGURABLE (`RENFYGRID_BAYFORCE_WEBHOOK_URL`, nunca una URL fija en
codigo) -- BayForce es un sistema externo con su propia base de datos
(MySQL, `core/renflow/bayforce/database.py`), la integracion es por HTTP,
no una tabla compartida.
"""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))

import psycopg  # noqa: E402

from renmeter_common.db import tenant_scope  # noqa: E402
from maintenance_engine import (  # noqa: E402
    advance_pm_plan,
    compute_backlog,
    compute_mttr_hours,
    compute_pm_compliance_pct,
    compute_sla_due_at,
    is_overdue,
    pm_plan_is_due,
)

ORDER_TYPES = {"preventive", "corrective", "inspection"}
ORDER_SOURCES = {"asset_condition", "simulation_result", "balance_anomaly", "pm_schedule", "manual"}
PRIORITIES = {"low", "medium", "high", "emergency"}
TERMINAL_STATUSES = {"completed", "cancelled"}

# generated -> scheduled -> assigned -> in_progress -> completed | cancelled
# (ciclo de vida propio de RenfyGrid, nunca depende de BayForce). El
# ramal `sent_to_bayforce` sigue existiendo tal cual Sprint B7 lo dejo,
# como camino OPCIONAL en paralelo -- notificacion de salida, no columna
# vertebral. Cancelar es valido desde cualquier estado no terminal (una
# orden real se cancela en cualquier punto antes de completarse).
ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "generated": {"scheduled", "sent_to_bayforce", "cancelled"},
    "scheduled": {"assigned", "cancelled"},
    "assigned": {"in_progress", "cancelled"},
    "sent_to_bayforce": {"in_progress", "cancelled"},
    "in_progress": {"completed", "cancelled"},
    "completed": set(),
    "cancelled": set(),
}


class InvalidOrderTypeError(ValueError):
    """`type` fuera de los 3 tipos reales (`0001_init.sql`)."""


class InvalidOrderSourceError(ValueError):
    """`source` fuera de las fuentes reales."""


class InvalidPriorityError(ValueError):
    """`priority` fuera de las 4 prioridades reales."""


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


class InvalidCloseStatusError(ValueError):
    """`close_order()` solo cierra a `completed`/`cancelled` -- distinto
    de `InvalidStatusTransitionError` (que es sobre el estado ACTUAL de
    la orden) para que el endpoint pueda distinguir un 422 (valor de
    cierre invalido) de un 409 (transicion invalida desde el estado
    actual) sin adivinar."""


class FailureCodeNotFoundError(LookupError):
    """No existe ese codigo de falla (o esta inactivo) para este tenant."""


class CrewNotFoundError(LookupError):
    """No existe esa cuadrilla (o esta inactiva) para este tenant."""


class PmPlanNotFoundError(LookupError):
    """No existe ese plan de mantenimiento preventivo para este tenant."""


class BayforceNotConfiguredError(ValueError):
    """No hay `RENFYGRID_BAYFORCE_WEBHOOK_URL` configurado para este
    despliegue -- nunca se simula un envio que no ocurrio."""


class BayforceIntegrationError(RuntimeError):
    """BayForce respondio con un error real, o una respuesta que no se
    pudo interpretar -- se propaga el detalle real, nunca un exito
    fabricado."""


def _now() -> datetime:
    return datetime.now(timezone.utc)


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


def _sla_target_hours(conn: psycopg.Connection, tenant_id: str, priority: str) -> float | None:
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT target_hours FROM maintenance_sla_policy WHERE tenant_id = %s AND priority = %s",
                    (tenant_id, priority),
                )
                row = cur.fetchone()
    return float(row[0]) if row else None


def generate_order(
    conn: psycopg.Connection,
    tenant_id: str,
    asset_id: str,
    order_type: str,
    source: str,
    priority: str,
    reason: str | None = None,
) -> dict[str, Any]:
    """Genera una orden real -- valida la anomalia real para las fuentes
    automaticas ANTES de insertar (`AnomalyNotConfirmedError` si no se
    cumple), nunca una orden fabricada sin condicion real detras.
    `priority` es obligatoria (igual que `type`/`source`) -- el SLA se
    calcula solo si el tenant configuro una politica real para ella."""
    if order_type not in ORDER_TYPES:
        raise InvalidOrderTypeError(f"Tipo de orden invalido: {order_type!r} (validos: {sorted(ORDER_TYPES)})")
    if source not in ORDER_SOURCES:
        raise InvalidOrderSourceError(f"Fuente de orden invalida: {source!r} (validos: {sorted(ORDER_SOURCES)})")
    if priority not in PRIORITIES:
        raise InvalidPriorityError(f"Prioridad invalida: {priority!r} (validas: {sorted(PRIORITIES)})")

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
    # 'simulation_result', 'pm_schedule' (la llama generate_due_pm_orders) y 'manual': sin precondicion aca.

    target_hours = _sla_target_hours(conn, tenant_id, priority)

    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO maintenance_order (tenant_id, asset_id, type, source, priority, status, reason) "
                    "VALUES (%s, %s, %s, %s, %s, 'generated', %s) RETURNING id, created_at",
                    (tenant_id, asset_id, order_type, source, priority, reason),
                )
                (order_id, created_at) = cur.fetchone()
                sla_due_at = compute_sla_due_at(created_at, target_hours)
                if sla_due_at is not None:
                    cur.execute(
                        "UPDATE maintenance_order SET sla_due_at = %s WHERE id = %s AND tenant_id = %s",
                        (sla_due_at, order_id, tenant_id),
                    )
    return _row_dict(
        order_id=str(order_id), asset_id=asset_id, type=order_type, source=source, priority=priority,
        status="generated", reason=reason, bayforce_order_ref=None, created_at=created_at, sla_due_at=sla_due_at,
        failure_code_id=None, scheduled_at=None, assigned_crew_id=None, labor_hours=None, materials_used=None,
        root_cause=None, closed_at=None,
    )


_ORDER_COLUMNS = (
    "id, asset_id, type, source, priority, status, bayforce_order_ref, reason, created_at, sla_due_at, "
    "failure_code_id, scheduled_at, assigned_crew_id, labor_hours, materials_used, root_cause, closed_at"
)


def _row_dict(**kw: Any) -> dict[str, Any]:
    def _iso(v: Any) -> Any:
        return v.isoformat() if isinstance(v, datetime) else v

    return {
        "order_id": kw["order_id"], "asset_id": kw["asset_id"], "type": kw["type"], "source": kw["source"],
        "priority": kw["priority"], "status": kw["status"], "bayforce_order_ref": kw["bayforce_order_ref"],
        "reason": kw["reason"], "created_at": _iso(kw["created_at"]), "sla_due_at": _iso(kw["sla_due_at"]),
        "failure_code_id": str(kw["failure_code_id"]) if kw["failure_code_id"] else None,
        "scheduled_at": _iso(kw["scheduled_at"]),
        "assigned_crew_id": str(kw["assigned_crew_id"]) if kw["assigned_crew_id"] else None,
        "labor_hours": float(kw["labor_hours"]) if kw["labor_hours"] is not None else None,
        "materials_used": kw["materials_used"], "root_cause": kw["root_cause"], "closed_at": _iso(kw["closed_at"]),
        "is_overdue": is_overdue(kw["sla_due_at"], kw["status"], _now()),
    }


def _order_row_to_dict(row: tuple) -> dict[str, Any]:
    return _row_dict(
        order_id=str(row[0]), asset_id=str(row[1]), type=row[2], source=row[3], priority=row[4], status=row[5],
        bayforce_order_ref=row[6], reason=row[7], created_at=row[8], sla_due_at=row[9], failure_code_id=row[10],
        scheduled_at=row[11], assigned_crew_id=row[12], labor_hours=row[13], materials_used=row[14],
        root_cause=row[15], closed_at=row[16],
    )


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
                    f"SELECT {_ORDER_COLUMNS} FROM maintenance_order WHERE tenant_id = %s {' '.join(clauses)} "
                    f"ORDER BY created_at DESC",
                    params,
                )
                rows = cur.fetchall()
    return [_order_row_to_dict(row) for row in rows]


def get_order_detail(conn: psycopg.Connection, tenant_id: str, order_id: str) -> dict[str, Any]:
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT {_ORDER_COLUMNS} FROM maintenance_order WHERE id = %s AND tenant_id = %s",
                    (order_id, tenant_id),
                )
                row = cur.fetchone()
    if row is None:
        raise OrderNotFoundError(f"No existe la orden {order_id} para este tenant")
    return _order_row_to_dict(row)


def _transition(
    conn: psycopg.Connection, tenant_id: str, order_id: str, new_status: str, extra_set: dict[str, Any] | None = None
) -> dict[str, Any]:
    order = get_order_detail(conn, tenant_id, order_id)
    if new_status not in ALLOWED_TRANSITIONS.get(order["status"], set()):
        raise InvalidStatusTransitionError(f"La orden {order_id} esta '{order['status']}', no puede pasar a '{new_status}'")
    extra_set = dict(extra_set or {})
    if new_status in TERMINAL_STATUSES:
        extra_set["closed_at"] = _now()
    set_clause = ", ".join([f"{col} = %s" for col in extra_set] + ["status = %s"])
    params = list(extra_set.values()) + [new_status, order_id, tenant_id]
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    f"UPDATE maintenance_order SET {set_clause} WHERE id = %s AND tenant_id = %s", params
                )
    return get_order_detail(conn, tenant_id, order_id)


def schedule_order(conn: psycopg.Connection, tenant_id: str, order_id: str, scheduled_at: datetime) -> dict[str, Any]:
    """Programa la orden (fecha/hora real de ejecucion) -- solo valida
    desde `generated`."""
    return _transition(conn, tenant_id, order_id, "scheduled", {"scheduled_at": scheduled_at})


def _crew_exists(conn: psycopg.Connection, tenant_id: str, crew_id: str) -> bool:
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT 1 FROM maintenance_crew WHERE id = %s AND tenant_id = %s AND is_active = true",
                    (crew_id, tenant_id),
                )
                return cur.fetchone() is not None


def assign_order(conn: psycopg.Connection, tenant_id: str, order_id: str, crew_id: str) -> dict[str, Any]:
    """Asigna la orden a una cuadrilla real y activa -- `CrewNotFoundError`
    si no existe o esta inactiva. Sin motor de ruteo/optimizacion --
    asignacion simple y explicita, a proposito (ver docs/04-plan-sprints.md SS9)."""
    if not _crew_exists(conn, tenant_id, crew_id):
        raise CrewNotFoundError(f"No existe la cuadrilla {crew_id} (o esta inactiva) para este tenant")
    return _transition(conn, tenant_id, order_id, "assigned", {"assigned_crew_id": crew_id})


def start_order(conn: psycopg.Connection, tenant_id: str, order_id: str) -> dict[str, Any]:
    """Marca el trabajo como iniciado en campo -- valida desde `assigned`
    o `sent_to_bayforce`."""
    return _transition(conn, tenant_id, order_id, "in_progress")


def _failure_code_exists(conn: psycopg.Connection, tenant_id: str, failure_code_id: str) -> bool:
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT 1 FROM maintenance_failure_code WHERE id = %s AND tenant_id = %s",
                    (failure_code_id, tenant_id),
                )
                return cur.fetchone() is not None


def close_order(
    conn: psycopg.Connection,
    tenant_id: str,
    order_id: str,
    new_status: str,
    labor_hours: float | None = None,
    materials_used: str | None = None,
    root_cause: str | None = None,
    failure_code_id: str | None = None,
) -> dict[str, Any]:
    """Cierra la orden real -- `completed` (con lo que de verdad se hizo:
    horas, materiales, causa raiz, codigo de falla) o `cancelled`. Solo
    valido desde `in_progress` (nunca se completa algo que nunca se
    empezo)."""
    if new_status not in ("completed", "cancelled"):
        raise InvalidCloseStatusError(f"close_order solo cierra a 'completed'/'cancelled', no {new_status!r}")
    if failure_code_id is not None and not _failure_code_exists(conn, tenant_id, failure_code_id):
        raise FailureCodeNotFoundError(f"No existe el codigo de falla {failure_code_id} para este tenant")
    extra = {
        "labor_hours": labor_hours, "materials_used": materials_used,
        "root_cause": root_cause, "failure_code_id": failure_code_id,
    }
    return _transition(conn, tenant_id, order_id, new_status, extra)


# ── Catalogos (patron semilla+catalogo, nunca un umbral/lista fija en codigo) ──


def set_sla_policy(conn: psycopg.Connection, tenant_id: str, priority: str, target_hours: float) -> dict[str, Any]:
    if priority not in PRIORITIES:
        raise InvalidPriorityError(f"Prioridad invalida: {priority!r} (validas: {sorted(PRIORITIES)})")
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO maintenance_sla_policy (tenant_id, priority, target_hours) VALUES (%s, %s, %s) "
                    "ON CONFLICT (tenant_id, priority) DO UPDATE SET target_hours = EXCLUDED.target_hours",
                    (tenant_id, priority, target_hours),
                )
    return {"priority": priority, "target_hours": target_hours}


def list_sla_policies(conn: psycopg.Connection, tenant_id: str) -> list[dict]:
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT priority, target_hours FROM maintenance_sla_policy WHERE tenant_id = %s ORDER BY priority",
                    (tenant_id,),
                )
                rows = cur.fetchall()
    return [{"priority": r[0], "target_hours": float(r[1])} for r in rows]


def create_failure_code(conn: psycopg.Connection, tenant_id: str, code: str, label: str) -> dict[str, Any]:
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO maintenance_failure_code (tenant_id, code, label) VALUES (%s, %s, %s) RETURNING id",
                    (tenant_id, code, label),
                )
                (failure_code_id,) = cur.fetchone()
    return {"failure_code_id": str(failure_code_id), "code": code, "label": label, "is_active": True}


def list_failure_codes(conn: psycopg.Connection, tenant_id: str, include_inactive: bool = False) -> list[dict]:
    clause = "" if include_inactive else "AND is_active = true"
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT id, code, label, is_active FROM maintenance_failure_code "
                    f"WHERE tenant_id = %s {clause} ORDER BY code",
                    (tenant_id,),
                )
                rows = cur.fetchall()
    return [{"failure_code_id": str(r[0]), "code": r[1], "label": r[2], "is_active": r[3]} for r in rows]


def deactivate_failure_code(conn: psycopg.Connection, tenant_id: str, failure_code_id: str) -> None:
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE maintenance_failure_code SET is_active = false WHERE id = %s AND tenant_id = %s",
                    (failure_code_id, tenant_id),
                )


def create_crew(conn: psycopg.Connection, tenant_id: str, name: str) -> dict[str, Any]:
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO maintenance_crew (tenant_id, name) VALUES (%s, %s) RETURNING id",
                    (tenant_id, name),
                )
                (crew_id,) = cur.fetchone()
    return {"crew_id": str(crew_id), "name": name, "is_active": True}


def list_crews(conn: psycopg.Connection, tenant_id: str, include_inactive: bool = False) -> list[dict]:
    clause = "" if include_inactive else "AND is_active = true"
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT id, name, is_active FROM maintenance_crew WHERE tenant_id = %s {clause} ORDER BY name",
                    (tenant_id,),
                )
                rows = cur.fetchall()
    return [{"crew_id": str(r[0]), "name": r[1], "is_active": r[2]} for r in rows]


def deactivate_crew(conn: psycopg.Connection, tenant_id: str, crew_id: str) -> None:
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE maintenance_crew SET is_active = false WHERE id = %s AND tenant_id = %s",
                    (crew_id, tenant_id),
                )


# ── Mantenimiento preventivo programado ────────────────────────────────


def create_pm_plan(
    conn: psycopg.Connection,
    tenant_id: str,
    asset_id: str,
    order_type: str,
    priority: str,
    interval_days: int,
    next_due_at: datetime,
) -> dict[str, Any]:
    """Plan real por activo especifico (nunca "por tipo de activo"
    generico) -- `next_due_at` es la fecha real desde la que se cuenta,
    normalmente ahora o una fecha de instalacion/ultima inspeccion real."""
    if order_type not in ("preventive", "inspection"):
        raise InvalidOrderTypeError(f"Tipo de plan PM invalido: {order_type!r} (validos: preventive, inspection)")
    if priority not in PRIORITIES:
        raise InvalidPriorityError(f"Prioridad invalida: {priority!r} (validas: {sorted(PRIORITIES)})")
    _asset_row(conn, tenant_id, asset_id)  # AssetNotFoundError si no existe
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO maintenance_pm_plan (tenant_id, asset_id, order_type, priority, interval_days, next_due_at) "
                    "VALUES (%s, %s, %s, %s, %s, %s) RETURNING id",
                    (tenant_id, asset_id, order_type, priority, interval_days, next_due_at),
                )
                (pm_plan_id,) = cur.fetchone()
    return {
        "pm_plan_id": str(pm_plan_id), "asset_id": asset_id, "order_type": order_type, "priority": priority,
        "interval_days": interval_days, "next_due_at": next_due_at.isoformat(), "last_generated_at": None, "is_active": True,
    }


def _pm_plan_row_to_dict(row: tuple) -> dict[str, Any]:
    return {
        "pm_plan_id": str(row[0]), "asset_id": str(row[1]), "order_type": row[2], "priority": row[3],
        "interval_days": row[4], "next_due_at": row[5].isoformat(), "is_active": row[7],
        "last_generated_at": row[6].isoformat() if row[6] else None,
    }


def list_pm_plans(conn: psycopg.Connection, tenant_id: str) -> list[dict]:
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id, asset_id, order_type, priority, interval_days, next_due_at, last_generated_at, is_active "
                    "FROM maintenance_pm_plan WHERE tenant_id = %s ORDER BY next_due_at",
                    (tenant_id,),
                )
                rows = cur.fetchall()
    return [_pm_plan_row_to_dict(row) for row in rows]


def generate_due_pm_orders(conn: psycopg.Connection, tenant_id: str, now: datetime | None = None) -> list[dict]:
    """Genera una orden real por cada plan PM activo cuyo `next_due_at` ya
    llego (`pm_plan_is_due`) -- nunca un cron adivinando, la condicion
    real es la fecha guardada. Avanza `next_due_at` al proximo real
    (`advance_pm_plan`) y registra `last_generated_at`. Devuelve las
    ordenes generadas (vacio si ningun plan vencio)."""
    now = now or _now()
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id, asset_id, order_type, priority, interval_days, next_due_at "
                    "FROM maintenance_pm_plan WHERE tenant_id = %s AND is_active = true",
                    (tenant_id,),
                )
                plans = cur.fetchall()

    generated: list[dict] = []
    for pm_plan_id, asset_id, order_type, priority, interval_days, next_due_at in plans:
        if not pm_plan_is_due(next_due_at, now):
            continue
        order = generate_order(
            conn, tenant_id, str(asset_id), order_type, "pm_schedule", priority,
            reason=f"Mantenimiento preventivo programado (plan {pm_plan_id}, cada {interval_days} dias)",
        )
        generated.append(order)
        new_due = advance_pm_plan(next_due_at, interval_days, now)
        with conn.transaction():
            with tenant_scope(conn, tenant_id):
                with conn.cursor() as cur:
                    cur.execute(
                        "UPDATE maintenance_pm_plan SET next_due_at = %s, last_generated_at = %s "
                        "WHERE id = %s AND tenant_id = %s",
                        (new_due, now, pm_plan_id, tenant_id),
                    )
    return generated


# ── KPIs ─────────────────────────────────────────────────────────────


def maintenance_kpis(conn: psycopg.Connection, tenant_id: str) -> dict[str, Any]:
    """Resumen real del portafolio de ordenes -- MTTR, backlog, % de
    cumplimiento de mantenimiento preventivo, ordenes vencidas de SLA.
    Todo calculado por `maintenance_engine` sobre filas reales, nunca
    aproximado en SQL."""
    now = _now()
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT status, priority, source, created_at, closed_at, sla_due_at "
                    "FROM maintenance_order WHERE tenant_id = %s",
                    (tenant_id,),
                )
                rows = cur.fetchall()

    orders = [
        {"status": r[0], "priority": r[1], "source": r[2], "created_at": r[3], "closed_at": r[4], "sla_due_at": r[5]}
        for r in rows
    ]
    completed = [o for o in orders if o["status"] == "completed"]
    open_orders = [o for o in orders if o["status"] not in TERMINAL_STATUSES]
    pm_closed = [o for o in orders if o["source"] == "pm_schedule" and o["status"] in TERMINAL_STATUSES]

    by_status: dict[str, int] = {}
    by_priority: dict[str, int] = {}
    for o in orders:
        by_status[o["status"]] = by_status.get(o["status"], 0) + 1
        if o["priority"]:
            by_priority[o["priority"]] = by_priority.get(o["priority"], 0) + 1

    overdue_count = sum(1 for o in orders if is_overdue(o["sla_due_at"], o["status"], now))

    return {
        "total_orders": len(orders),
        "mttr_hours": compute_mttr_hours(completed),
        "backlog": compute_backlog(open_orders, now),
        "pm_compliance_pct": compute_pm_compliance_pct(pm_closed),
        "overdue_count": overdue_count,
        "by_status": by_status,
        "by_priority": by_priority,
    }


# ── BayForce (notificacion de salida OPCIONAL, nunca la columna vertebral) ──


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
        "type": order["type"], "source": order["source"], "priority": order["priority"], "reason": order["reason"],
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

    extra_set: dict[str, Any] = {}
    if new_status in TERMINAL_STATUSES:
        extra_set["closed_at"] = _now()
    set_clause = ", ".join([f"{col} = %s" for col in extra_set] + ["status = %s"])
    params = list(extra_set.values()) + [new_status, order_id, tenant_id]
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(f"UPDATE maintenance_order SET {set_clause} WHERE id = %s AND tenant_id = %s", params)
    return {"order_id": order_id, "status": new_status, "bayforce_order_ref": bayforce_order_ref}
