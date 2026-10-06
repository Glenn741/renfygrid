"""Operacion diaria de la junta (Track D, D1.1, migracion 0030). Ver
docs/04-plan-sprints.md SS11.2 y Guia 3 de Municipios Azules, secciones
3.3-3.4 y fichas 7B (cloro residual) y 7C (bitacora diaria).

- Puntos de medicion de la junta, con su tipo del catalogo (`core`) y la
  frecuencia propia o la del tipo.
- Mediciones de campo: se interpretan con la regla vigente del paquete
  normativo adoptado a la fecha de la medicion y se guarda esa
  interpretacion (un cambio de norma no reescribe el historial). Fuera de
  rango -> hallazgo con la prioridad del tramo; si ya hay uno abierto para
  el mismo punto y parametro, la medicion se suma a ese (repetir la medicion
  es parte del procedimiento de la guia y no debe llenar la lista de
  hallazgos).
- Bitacora 7C: tomas con nivel de tanque, cloro aplicado, medicion de cloro
  residual, aspecto del agua y estado; nunca "Bueno" con cloro fuera de rango
  o agua turbia.
- `client_id`: lo genera el dispositivo; reenviar lo mismo (app sin conexion)
  devuelve lo ya guardado en vez de duplicar.

Logica pura en `pack_engine.py`; aqui solo filas reales y transacciones.
"""

from __future__ import annotations

import sys
import uuid
from datetime import date, datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))

import psycopg  # noqa: E402

from pack_engine import (  # noqa: E402
    InvalidRecordError,
    chlorine_product_per_day,
    dosing_guard_codes,
    interpret_reading,
    log_entry_status,
    sampling_points_status,
)
from pack_service import (  # noqa: E402
    RuleNotFoundError,
    _assert_assets_belong,
    active_pack_ids,
    active_rule,
)
from renmeter_common.db import tenant_scope  # noqa: E402


class OperationNotFoundError(LookupError):
    """Punto, medicion, tipo o momento inexistente para esta junta."""


class OperationConflictError(ValueError):
    """Ya existe un punto con ese nombre en la junta."""


def _check_uuid(value: str | None, what: str) -> None:
    if value is None:
        return
    try:
        uuid.UUID(str(value))
    except ValueError:
        raise OperationNotFoundError(f"No existe {what} {value!r}") from None


# ── Catalogos ─────────────────────────────────────────────────────────

def list_sampling_point_kinds(conn: psycopg.Connection, tenant_id: str) -> list[dict]:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT code, label, purpose, frequency_days FROM sampling_point_kind "
            "WHERE pack_id = ANY(%s) ORDER BY sort_order",
            (active_pack_ids(conn, tenant_id),),
        )
        return [{"code": r[0], "label": r[1], "purpose": r[2], "frequency_days": r[3]} for r in cur.fetchall()]


def list_operation_moments(conn: psycopg.Connection, tenant_id: str) -> list[dict]:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT pack_id, code, label, check_text, record_text FROM operation_moment "
            "WHERE pack_id = ANY(%s) ORDER BY pack_id, sort_order",
            (active_pack_ids(conn, tenant_id),),
        )
        return [{"pack_id": r[0], "code": r[1], "label": r[2], "check_text": r[3], "record_text": r[4]}
                for r in cur.fetchall()]


def list_field_parameters(conn: psycopg.Connection, tenant_id: str) -> list[dict]:
    """Parametros que se miden en campo, con la regla vigente si la hay."""
    with conn.cursor() as cur:
        cur.execute("SELECT code, label, unit FROM parameter WHERE measured_by = 'field' ORDER BY code")
        params = cur.fetchall()
    out = []
    for code, label, unit in params:
        try:
            rule = active_rule(conn, tenant_id, code)
            bands, citation = rule["bands"], rule["citation"]
        except RuleNotFoundError:
            bands, citation = None, None
        out.append({"code": code, "label": label, "unit": unit, "bands": bands, "citation": citation})
    return out


# ── Puntos de medicion ────────────────────────────────────────────────

_POINT_COLUMNS = ("p.id, p.kind_code, k.label, p.name, p.asset_id, p.latitude, p.longitude, p.frequency_days, "
                  "k.frequency_days, p.active")


def _point_row(r: tuple) -> dict:
    return {
        "point_id": str(r[0]), "kind_code": r[1], "kind_label": r[2], "name": r[3],
        "asset_id": str(r[4]) if r[4] else None, "latitude": r[5], "longitude": r[6],
        "frequency_days": r[7], "kind_frequency_days": r[8], "active": r[9],
    }


def create_sampling_point(
    conn: psycopg.Connection,
    tenant_id: str,
    kind_code: str,
    name: str,
    asset_id: str | None = None,
    latitude: float | None = None,
    longitude: float | None = None,
    frequency_days: int | None = None,
) -> dict:
    if kind_code not in {k["code"] for k in list_sampling_point_kinds(conn, tenant_id)}:
        raise OperationNotFoundError(f"Tipo de punto desconocido: {kind_code!r}")
    name = name.strip()
    if not name:
        raise InvalidRecordError("El punto necesita un nombre que el operador reconozca")
    if frequency_days is not None and frequency_days <= 0:
        raise InvalidRecordError("La frecuencia debe ser un número de días positivo")
    if asset_id:
        _check_uuid(asset_id, "el componente")
        _assert_assets_belong(conn, tenant_id, {asset_id})
    try:
        with conn.transaction():
            with tenant_scope(conn, tenant_id):
                with conn.cursor() as cur:
                    cur.execute(
                        "INSERT INTO sampling_point (tenant_id, kind_code, name, asset_id, latitude, longitude, frequency_days) "
                        "VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id",
                        (tenant_id, kind_code, name, asset_id, latitude, longitude, frequency_days),
                    )
                    point_id = cur.fetchone()[0]
    except psycopg.errors.UniqueViolation:
        raise OperationConflictError(f"Ya existe un punto llamado {name!r}") from None
    return get_sampling_point(conn, tenant_id, str(point_id))


def get_sampling_point(conn: psycopg.Connection, tenant_id: str, point_id: str) -> dict:
    _check_uuid(point_id, "el punto")
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT {_POINT_COLUMNS} FROM sampling_point p JOIN sampling_point_kind k ON k.code = p.kind_code "
                    "WHERE p.id = %s AND p.tenant_id = %s",
                    (point_id, tenant_id),
                )
                row = cur.fetchone()
    if row is None:
        raise OperationNotFoundError(f"No existe el punto {point_id} para esta junta")
    return _point_row(row)


_POINT_FIELDS = ("name", "frequency_days", "active", "latitude", "longitude", "asset_id")


def update_sampling_point(conn: psycopg.Connection, tenant_id: str, point_id: str, **fields: Any) -> dict:
    unknown = set(fields) - set(_POINT_FIELDS)
    if unknown:
        raise InvalidRecordError(f"Campos no editables: {sorted(unknown)}")
    get_sampling_point(conn, tenant_id, point_id)
    if "name" in fields:
        fields["name"] = (fields["name"] or "").strip()
        if not fields["name"]:
            raise InvalidRecordError("El punto necesita un nombre")
    if fields.get("frequency_days") is not None and fields["frequency_days"] <= 0:
        raise InvalidRecordError("La frecuencia debe ser un número de días positivo")
    if fields.get("asset_id"):
        _check_uuid(fields["asset_id"], "el componente")
        _assert_assets_belong(conn, tenant_id, {fields["asset_id"]})
    if fields:
        sets = ", ".join(f"{k} = %s" for k in fields)
        try:
            with conn.transaction():
                with tenant_scope(conn, tenant_id):
                    conn.execute(f"UPDATE sampling_point SET {sets} WHERE id = %s AND tenant_id = %s",
                                 (*fields.values(), point_id, tenant_id))
        except psycopg.errors.UniqueViolation:
            raise OperationConflictError(f"Ya existe un punto llamado {fields.get('name')!r}") from None
    return get_sampling_point(conn, tenant_id, point_id)


def list_sampling_points(
    conn: psycopg.Connection, tenant_id: str, today: date, tz_name: str, include_inactive: bool = False,
) -> list[dict]:
    """Puntos con su estado de hoy (toca medir / al dia / nunca medido) y su
    ultima medicion de cloro residual. `tz_name`: zona de la organizacion,
    para saber en que dia local cayo cada medicion."""
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT {_POINT_COLUMNS} FROM sampling_point p JOIN sampling_point_kind k ON k.code = p.kind_code "
                    f"WHERE p.tenant_id = %s {'' if include_inactive else 'AND p.active'} ORDER BY k.sort_order, p.name",
                    (tenant_id,),
                )
                points = [_point_row(r) for r in cur.fetchall()]
                cur.execute(
                    "SELECT DISTINCT ON (sampling_point_id) sampling_point_id, measured_at, value, result_label, severity, "
                    "measured_at AT TIME ZONE %s "
                    "FROM field_reading WHERE tenant_id = %s AND sampling_point_id IS NOT NULL "
                    "AND parameter_code = 'free_chlorine' ORDER BY sampling_point_id, measured_at DESC, created_at DESC",
                    (tz_name, tenant_id),
                )
                last = {str(r[0]): r for r in cur.fetchall()}
    rows = sampling_points_status(points, {pid: r[5].date() for pid, r in last.items()}, today)
    for row in rows:
        r = last.get(row["point_id"])
        row["last_chlorine"] = (
            {"measured_at": r[1].isoformat(), "value": float(r[2]), "result_label": r[3], "severity": r[4]} if r else None
        )
    return rows


# ── Mediciones de campo (7B) ──────────────────────────────────────────

_READING_COLUMNS = ("r.id, r.sampling_point_id, sp.name, r.parameter_code, pa.label, pa.unit, r.value, r.measured_at, "
                    "r.measured_by, r.result_code, r.result_label, r.severity, r.action_taken, r.finding_id, r.client_id")


def _reading_row(r: tuple) -> dict:
    return {
        "reading_id": str(r[0]), "point_id": str(r[1]) if r[1] else None, "point_name": r[2],
        "parameter_code": r[3], "parameter_label": r[4], "unit": r[5], "value": float(r[6]),
        "measured_at": r[7].isoformat(), "measured_by": r[8], "result_code": r[9], "result_label": r[10],
        "severity": r[11], "action_taken": r[12], "finding_id": str(r[13]) if r[13] else None,
        "client_id": str(r[14]) if r[14] else None,
    }


def _get_reading(cur: psycopg.Cursor, tenant_id: str, where: str, params: tuple) -> dict | None:
    cur.execute(
        f"SELECT {_READING_COLUMNS} FROM field_reading r JOIN parameter pa ON pa.code = r.parameter_code "
        f"LEFT JOIN sampling_point sp ON sp.id = r.sampling_point_id WHERE r.tenant_id = %s AND {where}",
        (tenant_id, *params),
    )
    row = cur.fetchone()
    return _reading_row(row) if row else None


def record_field_reading(
    conn: psycopg.Connection,
    tenant_id: str,
    parameter_code: str,
    value: float,
    measured_at: datetime,
    measured_by: str,
    sampling_point_id: str | None = None,
    action_taken: str | None = None,
    client_id: str | None = None,
) -> dict:
    """Guarda una medicion de campo con su interpretacion y, si esta fuera de
    rango, la liga a un hallazgo (nuevo o el abierto del mismo punto y
    parametro). Devuelve la medicion con `interpretation` (accion sugerida
    por la guia) y `finding_created`."""
    _check_uuid(sampling_point_id, "el punto")
    _check_uuid(client_id, "el identificador del dispositivo")
    with conn.cursor() as cur:
        cur.execute("SELECT label, unit, measured_by FROM parameter WHERE code = %s", (parameter_code,))
        param = cur.fetchone()
    if param is None:
        raise OperationNotFoundError(f"Parámetro desconocido: {parameter_code!r}")
    if param[2] != "field":
        raise InvalidRecordError(f"{param[0]} se analiza en laboratorio; no es una medición de campo")

    if client_id:
        with conn.transaction():
            with tenant_scope(conn, tenant_id):
                with conn.cursor() as cur:
                    existing = _get_reading(cur, tenant_id, "r.client_id = %s", (client_id,))
        if existing:
            return {**existing, "duplicate": True, "interpretation": None, "finding_created": False}

    point = get_sampling_point(conn, tenant_id, sampling_point_id) if sampling_point_id else None
    try:
        rule = active_rule(conn, tenant_id, parameter_code, measured_at.date())
        interpretation = interpret_reading(rule["bands"], float(value))
        rule_id = rule["rule_id"]
    except RuleNotFoundError:
        rule, interpretation, rule_id = None, None, None

    action_taken = (action_taken or "").strip() or None
    finding_created = False
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                finding_id = None
                if interpretation and interpretation["out_of_range"]:
                    source_ref = f"reading:{sampling_point_id or 'sin-punto'}:{parameter_code}"
                    cur.execute(
                        "SELECT id FROM finding WHERE tenant_id = %s AND source_kind = 'reading' AND source_ref = %s "
                        "AND status <> 'closed' ORDER BY created_at DESC LIMIT 1",
                        (tenant_id, source_ref),
                    )
                    open_row = cur.fetchone()
                    if open_row:
                        finding_id = open_row[0]
                    else:
                        where = f" en {point['name']}" if point else ""
                        description = (f"{param[0]} {value:g} {param[1]}{where} — {interpretation['label']}. "
                                       f"{action_taken or interpretation['action'] or ''}").strip()
                        cur.execute(
                            "INSERT INTO finding (tenant_id, source_kind, source_ref, asset_id, description, priority, created_by) "
                            "VALUES (%s, 'reading', %s, %s, %s, %s, %s) RETURNING id",
                            (tenant_id, source_ref, point["asset_id"] if point else None, description,
                             interpretation["finding_priority"], measured_by),
                        )
                        finding_id = cur.fetchone()[0]
                        finding_created = True
                cur.execute(
                    "INSERT INTO field_reading (tenant_id, sampling_point_id, parameter_code, value, measured_at, measured_by, "
                    "rule_id, result_code, result_label, severity, action_taken, finding_id, client_id) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id",
                    (tenant_id, sampling_point_id, parameter_code, value, measured_at, measured_by, rule_id,
                     interpretation["code"] if interpretation else None,
                     interpretation["label"] if interpretation else None,
                     interpretation["severity"] if interpretation else None,
                     action_taken, finding_id, client_id),
                )
                reading_id = cur.fetchone()[0]
                saved = _get_reading(cur, tenant_id, "r.id = %s", (reading_id,))
    return {**saved, "duplicate": False, "interpretation": interpretation,
            "citation": rule["citation"] if rule else None, "finding_created": finding_created}


def list_field_readings(
    conn: psycopg.Connection,
    tenant_id: str,
    since: datetime | None = None,
    until: datetime | None = None,
    point_id: str | None = None,
    parameter_code: str | None = None,
    limit: int = 200,
) -> list[dict]:
    _check_uuid(point_id, "el punto")
    clauses, params = [], []
    for clause, value in (("r.measured_at >= %s", since), ("r.measured_at < %s", until),
                          ("r.sampling_point_id = %s", point_id), ("r.parameter_code = %s", parameter_code)):
        if value is not None:
            clauses.append(clause)
            params.append(value)
    where = " AND ".join(["TRUE", *clauses])
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT {_READING_COLUMNS} FROM field_reading r JOIN parameter pa ON pa.code = r.parameter_code "
                    f"LEFT JOIN sampling_point sp ON sp.id = r.sampling_point_id "
                    f"WHERE r.tenant_id = %s AND {where} ORDER BY r.measured_at DESC, r.created_at DESC LIMIT %s",
                    (tenant_id, *params, max(1, min(limit, 1000))),
                )
                return [_reading_row(r) for r in cur.fetchall()]


# ── Bitacora diaria (7C) ──────────────────────────────────────────────

_LOG_COLUMNS = ("e.id, e.logged_at, e.pack_id, e.moment_code, m.label, e.tank_level_pct, e.chlorine_applied, "
                "e.chlorine_applied_unit, e.reading_id, r.value, r.result_label, r.severity, e.appearance, e.status, "
                "e.notes, e.logged_by, e.client_id")


def _log_row(r: tuple) -> dict:
    return {
        "entry_id": str(r[0]), "logged_at": r[1].isoformat(), "pack_id": r[2], "moment_code": r[3], "moment_label": r[4],
        "tank_level_pct": float(r[5]) if r[5] is not None else None,
        "chlorine_applied": float(r[6]) if r[6] is not None else None, "chlorine_applied_unit": r[7],
        "reading_id": str(r[8]) if r[8] else None,
        "residual_chlorine": float(r[9]) if r[9] is not None else None, "residual_result": r[10], "residual_severity": r[11],
        "appearance": r[12], "status": r[13], "notes": r[14], "logged_by": r[15],
        "client_id": str(r[16]) if r[16] else None,
    }


def _log_query(where: str) -> str:
    return (f"SELECT {_LOG_COLUMNS} FROM operation_log_entry e "
            "LEFT JOIN operation_moment m ON m.pack_id = e.pack_id AND m.code = e.moment_code "
            f"LEFT JOIN field_reading r ON r.id = e.reading_id WHERE e.tenant_id = %s AND {where}")


def create_log_entry(
    conn: psycopg.Connection,
    tenant_id: str,
    logged_at: datetime,
    logged_by: str,
    moment_code: str | None = None,
    pack_id: str | None = None,
    tank_level_pct: float | None = None,
    chlorine_applied: float | None = None,
    chlorine_applied_unit: str | None = None,
    reading_id: str | None = None,
    appearance: str | None = None,
    status: str | None = None,
    notes: str | None = None,
    client_id: str | None = None,
) -> dict:
    _check_uuid(reading_id, "la medición")
    _check_uuid(client_id, "el identificador del dispositivo")
    if client_id:
        with conn.transaction():
            with tenant_scope(conn, tenant_id):
                with conn.cursor() as cur:
                    cur.execute(_log_query("e.client_id = %s"), (tenant_id, client_id))
                    row = cur.fetchone()
        if row:
            return {**_log_row(row), "duplicate": True}
    if moment_code:
        moments = {(m["pack_id"], m["code"]) for m in list_operation_moments(conn, tenant_id)}
        matches = [m for m in moments if m[1] == moment_code and (pack_id is None or m[0] == pack_id)]
        if len(matches) != 1:
            raise OperationNotFoundError(f"Momento de la rutina desconocido: {moment_code!r}")
        pack_id = matches[0][0]
    else:
        pack_id = None
    if tank_level_pct is not None and not 0 <= tank_level_pct <= 100:
        raise InvalidRecordError("El nivel del tanque va de 0 a 100 %")
    if (chlorine_applied is None) != (chlorine_applied_unit is None):
        raise InvalidRecordError("El cloro aplicado necesita cantidad y unidad (g o ml)")
    if chlorine_applied_unit is not None and chlorine_applied_unit not in ("g", "ml"):
        raise InvalidRecordError("Unidad de cloro aplicado: g o ml")
    if chlorine_applied is not None and chlorine_applied < 0:
        raise InvalidRecordError("El cloro aplicado no puede ser negativo")
    severity = None
    if reading_id:
        with conn.transaction():
            with tenant_scope(conn, tenant_id):
                with conn.cursor() as cur:
                    reading = _get_reading(cur, tenant_id, "r.id = %s", (reading_id,))
        if reading is None:
            raise OperationNotFoundError(f"No existe la medición {reading_id} para esta junta")
        severity = reading["severity"]
    final_status = log_entry_status(status, severity, appearance)
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO operation_log_entry (tenant_id, logged_at, pack_id, moment_code, tank_level_pct, chlorine_applied, "
                    "chlorine_applied_unit, reading_id, appearance, status, notes, logged_by, client_id) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id",
                    (tenant_id, logged_at, pack_id, moment_code, tank_level_pct, chlorine_applied, chlorine_applied_unit,
                     reading_id, appearance, final_status, (notes or "").strip() or None, logged_by, client_id),
                )
                entry_id = cur.fetchone()[0]
                cur.execute(_log_query("e.id = %s"), (tenant_id, entry_id))
                row = cur.fetchone()
    return {**_log_row(row), "duplicate": False}


def list_log_entries(
    conn: psycopg.Connection, tenant_id: str, since: datetime | None = None, until: datetime | None = None, limit: int = 200,
) -> list[dict]:
    clauses, params = ["TRUE"], []
    if since is not None:
        clauses.append("e.logged_at >= %s")
        params.append(since)
    if until is not None:
        clauses.append("e.logged_at < %s")
        params.append(until)
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(_log_query(" AND ".join(clauses)) + " ORDER BY e.logged_at DESC LIMIT %s",
                            (tenant_id, *params, max(1, min(limit, 1000))))
                return [_log_row(r) for r in cur.fetchall()]


def operation_day(
    conn: psycopg.Connection, tenant_id: str, today: date, tz_name: str, day_start: datetime, day_end: datetime,
) -> dict:
    """Vista "Hoy" del operador: la rutina con lo registrado en cada momento,
    los puntos que toca medir y las mediciones del dia."""
    moments = list_operation_moments(conn, tenant_id)
    entries = list_log_entries(conn, tenant_id, day_start, day_end)
    readings = list_field_readings(conn, tenant_id, day_start, day_end)
    for m in moments:
        m["entries"] = [e for e in entries if e["pack_id"] == m["pack_id"] and e["moment_code"] == m["code"]]
    points = list_sampling_points(conn, tenant_id, today, tz_name)
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT count(*) FROM finding WHERE tenant_id = %s AND source_kind = 'reading' AND status <> 'closed'",
                    (tenant_id,),
                )
                open_reading_findings = cur.fetchone()[0]
    return {
        "date": today.isoformat(), "moments": moments,
        "unassigned_entries": [e for e in entries if e["moment_code"] is None],
        "points": points, "readings": readings,
        "summary": {
            "points_due": sum(1 for p in points if p["status"] in ("due", "never")),
            "readings_today": len(readings),
            "out_of_range_today": sum(1 for r in readings if r["severity"] in ("alert", "critical")),
            "entries_today": len(entries),
            "alerts_today": sum(1 for e in entries if e["status"] == "alert"),
            "open_reading_findings": open_reading_findings,
        },
    }


# ── Productos quimicos y dosificacion (0031) ──────────────────────────

_PRODUCT_COLUMNS = "id, name, purpose, form, active_pct, notes, active"
PRODUCT_PURPOSES = ("disinfection", "coagulation", "ph_adjustment")
PRODUCT_FORMS = ("solid", "liquid")


def _product_row(r: tuple) -> dict:
    return {"product_id": str(r[0]), "name": r[1], "purpose": r[2], "form": r[3], "active_pct": float(r[4]),
            "notes": r[5], "active": r[6], "unit": "g" if r[3] == "solid" else "ml"}


def _validate_product(fields: dict) -> None:
    if "name" in fields and not (fields["name"] or "").strip():
        raise InvalidRecordError("El producto necesita un nombre")
    if "purpose" in fields and fields["purpose"] not in PRODUCT_PURPOSES:
        raise InvalidRecordError(f"Uso inválido: {fields['purpose']!r} (válidos: {list(PRODUCT_PURPOSES)})")
    if "form" in fields and fields["form"] not in PRODUCT_FORMS:
        raise InvalidRecordError(f"Presentación inválida: {fields['form']!r} (válidas: {list(PRODUCT_FORMS)})")
    if "active_pct" in fields and not 0 < fields["active_pct"] <= 100:
        raise InvalidRecordError("La concentración va de más de 0 a 100 %")


def list_chemical_products(conn: psycopg.Connection, tenant_id: str, include_inactive: bool = False) -> list[dict]:
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT {_PRODUCT_COLUMNS} FROM chemical_product WHERE tenant_id = %s "
                    f"{'' if include_inactive else 'AND active'} ORDER BY name",
                    (tenant_id,),
                )
                return [_product_row(r) for r in cur.fetchall()]


def get_chemical_product(conn: psycopg.Connection, tenant_id: str, product_id: str) -> dict:
    _check_uuid(product_id, "el producto")
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(f"SELECT {_PRODUCT_COLUMNS} FROM chemical_product WHERE id = %s AND tenant_id = %s",
                            (product_id, tenant_id))
                row = cur.fetchone()
    if row is None:
        raise OperationNotFoundError(f"No existe el producto {product_id} para esta junta")
    return _product_row(row)


def create_chemical_product(
    conn: psycopg.Connection, tenant_id: str, name: str, purpose: str, form: str, active_pct: float,
    notes: str | None = None,
) -> dict:
    _validate_product({"name": name, "purpose": purpose, "form": form, "active_pct": active_pct})
    try:
        with conn.transaction():
            with tenant_scope(conn, tenant_id):
                with conn.cursor() as cur:
                    cur.execute(
                        "INSERT INTO chemical_product (tenant_id, name, purpose, form, active_pct, notes) "
                        f"VALUES (%s, %s, %s, %s, %s, %s) RETURNING {_PRODUCT_COLUMNS}",
                        (tenant_id, name.strip(), purpose, form, active_pct, (notes or "").strip() or None),
                    )
                    return _product_row(cur.fetchone())
    except psycopg.errors.UniqueViolation:
        raise OperationConflictError(f"Ya existe un producto llamado {name.strip()!r}") from None


def update_chemical_product(conn: psycopg.Connection, tenant_id: str, product_id: str, **fields: Any) -> dict:
    unknown = set(fields) - {"name", "purpose", "form", "active_pct", "notes", "active"}
    if unknown:
        raise InvalidRecordError(f"Campos no editables: {sorted(unknown)}")
    _validate_product(fields)
    get_chemical_product(conn, tenant_id, product_id)
    if "name" in fields:
        fields["name"] = fields["name"].strip()
    if fields:
        sets = ", ".join(f"{k} = %s" for k in fields)
        try:
            with conn.transaction():
                with tenant_scope(conn, tenant_id):
                    conn.execute(f"UPDATE chemical_product SET {sets} WHERE id = %s AND tenant_id = %s",
                                 (*fields.values(), product_id, tenant_id))
        except psycopg.errors.UniqueViolation:
            raise OperationConflictError(f"Ya existe un producto llamado {fields.get('name')!r}") from None
    return get_chemical_product(conn, tenant_id, product_id)


def calculate_dosing(
    conn: psycopg.Connection,
    tenant_id: str,
    product_id: str,
    flow_lps: float,
    dose_mg_l: float,
    day_start: datetime,
    day_end: datetime,
) -> dict:
    """Calculo orientativo de la Guia 3 §3.5 con las guardas que aplican
    hoy. No se guarda: lo que se aplica de verdad va a la bitacora 7C y se
    verifica con la medicion siguiente. Un producto que no es desinfectante
    no tiene resultado (va con prueba de jarras y apoyo tecnico)."""
    product = get_chemical_product(conn, tenant_id, product_id)
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT r.result_code, r.result_label, r.value, r.measured_at FROM field_reading r "
                    "JOIN sampling_point p ON p.id = r.sampling_point_id "
                    "WHERE r.tenant_id = %s AND p.kind_code = 'tank_outlet' AND r.parameter_code = 'free_chlorine' "
                    "ORDER BY r.measured_at DESC, r.created_at DESC LIMIT 1",
                    (tenant_id,),
                )
                last = cur.fetchone()
                cur.execute(
                    "SELECT (SELECT count(*) FROM field_reading WHERE tenant_id = %s AND parameter_code = 'turbidity' "
                    "        AND severity IN ('alert', 'critical') AND measured_at >= %s AND measured_at < %s) "
                    "     + (SELECT count(*) FROM operation_log_entry WHERE tenant_id = %s "
                    "        AND appearance IN ('turbid', 'colored') AND logged_at >= %s AND logged_at < %s)",
                    (tenant_id, day_start, day_end, tenant_id, day_start, day_end),
                )
                turbid_today = cur.fetchone()[0] > 0
    measured_today = bool(last and day_start <= last[3] < day_end)
    codes = dosing_guard_codes(product["purpose"], last[0] if last else None, measured_today, turbid_today)
    with conn.cursor() as cur:
        cur.execute(
            "SELECT code, level, message FROM dosing_guidance WHERE pack_id = ANY(%s) ORDER BY sort_order",
            (active_pack_ids(conn, tenant_id),),
        )
        texts = {r[0]: (r[1], r[2]) for r in cur.fetchall()}
    guards = [{"code": c, "level": texts[c][0] if c in texts else None, "message": texts[c][1] if c in texts else None}
              for c in codes]
    result = None
    if product["purpose"] == "disinfection":
        per_day = chlorine_product_per_day(flow_lps, dose_mg_l, product["active_pct"])
        result = {"per_day": round(per_day, 1), "per_hour": round(per_day / 24, 2), "unit": product["unit"]}
    return {
        "product": product, "flow_lps": flow_lps, "dose_mg_l": dose_mg_l, "result": result, "guards": guards,
        "can_apply": not any(g["level"] == "stop" for g in guards),
        "last_tank_residual": (
            {"value": float(last[2]), "result_code": last[0], "result_label": last[1], "measured_at": last[3].isoformat()}
            if last else None
        ),
    }
