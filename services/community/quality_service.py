"""Calidad del agua y laboratorio (Track D, D2, migracion 0034). Guia 3 de
Municipios Azules, seccion 3.4 y calendario 7G.

- Muestras de laboratorio con sus resultados. Cada resultado se interpreta
  con la regla vigente del paquete normativo A LA FECHA DE LA MUESTRA y se
  guarda esa interpretacion. Sin regla (limites de la NTE INEN 1108 aun no
  cargados) se guarda sin interpretar. '<'/'>' que no permiten concluir
  quedan "no concluyente" (pack_engine.interpret_lab_result).
- Fuera de rango -> hallazgo con la prioridad del tramo; si ya hay uno
  abierto del mismo punto y parametro, el resultado se suma a ese.
  Severidad critica (E. coli presente) se informa como alerta critica.
- Plan de muestreo de la junta: que analizar, donde y cada cuanto (la junta
  lo fija segun su categoria ARCA). Estado por plan: sin muestra / al dia /
  vencido. Revision del plan con el plazo del paquete de programa.
"""

from __future__ import annotations

import sys
import uuid
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))

import psycopg  # noqa: E402

from pack_engine import InvalidRecordError, checklist_status, interpret_lab_result  # noqa: E402
from emergency_service import auto_activate_from_results  # noqa: E402
from pack_service import RuleNotFoundError, active_pack_ids, active_rule  # noqa: E402
from renmeter_common.db import tenant_scope  # noqa: E402

SAMPLE_REASONS = ("plan", "alert", "other")


class QualityNotFoundError(LookupError):
    """Muestra, plan, punto o parametro inexistente para esta junta."""


class QualityConflictError(ValueError):
    """Nombre de plan repetido."""


def _check_uuid(value: str | None, what: str) -> None:
    if value is None:
        return
    try:
        uuid.UUID(str(value))
    except ValueError:
        raise QualityNotFoundError(f"No existe {what} {value!r}") from None


def _assert_point(cur: psycopg.Cursor, tenant_id: str, point_id: str | None) -> str | None:
    if point_id is None:
        return None
    _check_uuid(point_id, "el punto")
    cur.execute("SELECT name FROM sampling_point WHERE id = %s AND tenant_id = %s", (point_id, tenant_id))
    row = cur.fetchone()
    if row is None:
        raise QualityNotFoundError(f"No existe el punto {point_id} para esta organización")
    return row[0]


def list_quality_parameters(conn: psycopg.Connection, tenant_id: str) -> list[dict]:
    """Todos los parametros (campo y laboratorio) con su regla vigente, si la hay."""
    with conn.cursor() as cur:
        cur.execute("SELECT code, label, unit, measured_by FROM parameter ORDER BY measured_by DESC, label")
        params = cur.fetchall()
    out = []
    for code, label, unit, measured_by in params:
        try:
            rule = active_rule(conn, tenant_id, code)
            bands, citation = rule["bands"], rule["citation"]
        except RuleNotFoundError:
            bands, citation = None, None
        out.append({"code": code, "label": label, "unit": unit, "measured_by": measured_by, "bands": bands, "citation": citation})
    return out


# ── Plan de muestreo ──────────────────────────────────────────────────

_PLAN_COLUMNS = "p.id, p.name, p.parameters, p.sampling_point_id, sp.name, p.frequency_days, p.source_note, p.active"


def _plan_row(r: tuple) -> dict:
    return {"plan_item_id": str(r[0]), "name": r[1], "parameters": list(r[2]), "point_id": str(r[3]) if r[3] else None,
            "point_name": r[4], "frequency_days": r[5], "source_note": r[6], "active": r[7]}


def _validate_parameters(conn: psycopg.Connection, codes: list[str]) -> list[str]:
    codes = sorted(set(codes or []))
    if not codes:
        raise InvalidRecordError("El plan necesita al menos un parámetro")
    with conn.cursor() as cur:
        cur.execute("SELECT code FROM parameter WHERE code = ANY(%s)", (codes,))
        known = {r[0] for r in cur.fetchall()}
    unknown = sorted(set(codes) - known)
    if unknown:
        raise QualityNotFoundError(f"Parámetros desconocidos: {unknown}")
    return codes


def create_plan_item(
    conn: psycopg.Connection, tenant_id: str, name: str, parameters: list[str], frequency_days: int,
    sampling_point_id: str | None = None, source_note: str | None = None,
) -> dict:
    name = (name or "").strip()
    if not name:
        raise InvalidRecordError("El plan necesita un nombre")
    if frequency_days <= 0:
        raise InvalidRecordError("La frecuencia debe ser un número de días positivo")
    codes = _validate_parameters(conn, parameters)
    try:
        with conn.transaction():
            with tenant_scope(conn, tenant_id):
                with conn.cursor() as cur:
                    _assert_point(cur, tenant_id, sampling_point_id)
                    cur.execute(
                        "INSERT INTO lab_plan_item (tenant_id, name, parameters, sampling_point_id, frequency_days, source_note) "
                        "VALUES (%s, %s, %s, %s, %s, %s) RETURNING id",
                        (tenant_id, name, codes, sampling_point_id, frequency_days, (source_note or "").strip() or None),
                    )
                    plan_id = str(cur.fetchone()[0])
    except psycopg.errors.UniqueViolation:
        raise QualityConflictError(f"Ya existe un plan llamado {name!r}") from None
    return next(p for p in list_plan(conn, tenant_id, datetime.now(timezone.utc), include_inactive=True)["items"]
                if p["plan_item_id"] == plan_id)


def update_plan_item(conn: psycopg.Connection, tenant_id: str, plan_item_id: str, **fields: Any) -> dict:
    allowed = {"name", "parameters", "frequency_days", "sampling_point_id", "source_note", "active"}
    unknown = set(fields) - allowed
    if unknown:
        raise InvalidRecordError(f"Campos no editables: {sorted(unknown)}")
    _check_uuid(plan_item_id, "el plan")
    if "parameters" in fields:
        fields["parameters"] = _validate_parameters(conn, fields["parameters"])
    if "name" in fields:
        fields["name"] = (fields["name"] or "").strip()
        if not fields["name"]:
            raise InvalidRecordError("El plan necesita un nombre")
    if fields.get("frequency_days") is not None and fields["frequency_days"] <= 0:
        raise InvalidRecordError("La frecuencia debe ser un número de días positivo")
    try:
        with conn.transaction():
            with tenant_scope(conn, tenant_id):
                with conn.cursor() as cur:
                    if fields.get("sampling_point_id"):
                        _assert_point(cur, tenant_id, fields["sampling_point_id"])
                    cur.execute("SELECT 1 FROM lab_plan_item WHERE id = %s AND tenant_id = %s", (plan_item_id, tenant_id))
                    if cur.fetchone() is None:
                        raise QualityNotFoundError(f"No existe el plan {plan_item_id} para esta organización")
                    if fields:
                        sets = ", ".join(f"{k} = %s" for k in fields)
                        cur.execute(f"UPDATE lab_plan_item SET {sets} WHERE id = %s AND tenant_id = %s",
                                    (*fields.values(), plan_item_id, tenant_id))
    except psycopg.errors.UniqueViolation:
        raise QualityConflictError(f"Ya existe un plan llamado {fields.get('name')!r}") from None
    return next(p for p in list_plan(conn, tenant_id, datetime.now(timezone.utc), include_inactive=True)["items"]
                if p["plan_item_id"] == plan_item_id)


def _review_days(conn: psycopg.Connection, tenant_id: str) -> tuple[int | None, str | None]:
    with conn.cursor() as cur:
        cur.execute("SELECT value_days, source FROM program_rule WHERE code = 'sampling_plan_review_days' "
                    "AND pack_id = ANY(%s) ORDER BY pack_id LIMIT 1", (active_pack_ids(conn, tenant_id),))
        row = cur.fetchone()
    return (row[0], row[1]) if row else (None, None)


def list_plan(conn: psycopg.Connection, tenant_id: str, now: datetime, include_inactive: bool = False) -> dict:
    """Plan de muestreo con el estado de cada parte y de la revision del plan."""
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT {_PLAN_COLUMNS} FROM lab_plan_item p LEFT JOIN sampling_point sp ON sp.id = p.sampling_point_id "
                    f"WHERE p.tenant_id = %s {'' if include_inactive else 'AND p.active'} ORDER BY p.name",
                    (tenant_id,),
                )
                items = [_plan_row(r) for r in cur.fetchall()]
                cur.execute(
                    "SELECT DISTINCT ON (plan_item_id) plan_item_id, id, sampled_at FROM lab_sample "
                    "WHERE tenant_id = %s AND plan_item_id IS NOT NULL ORDER BY plan_item_id, sampled_at DESC",
                    (tenant_id,),
                )
                last = {str(r[0]): (str(r[1]), r[2]) for r in cur.fetchall()}
                cur.execute("SELECT reviewed_on, reviewed_by, notes FROM lab_plan_review WHERE tenant_id = %s "
                            "ORDER BY reviewed_on DESC, created_at DESC LIMIT 1", (tenant_id,))
                review = cur.fetchone()
    for item in items:
        sample_id, at = last.get(item["plan_item_id"], (None, None))
        st = checklist_status(item["frequency_days"], at, now)
        item.update({"last_sample_id": sample_id, "last_sampled_at": at.isoformat() if at else None,
                     "status": st["status"], "days_to_due": st["days_to_due"],
                     "next_due_at": st["next_due_at"].isoformat() if st["next_due_at"] else None})
    days, source = _review_days(conn, tenant_id)
    review_at = datetime.combine(review[0], datetime.min.time(), tzinfo=timezone.utc) if review else None
    review_status = checklist_status(days, review_at, now) if days else None
    return {
        "items": items,
        "review": {
            "last_reviewed_on": review[0].isoformat() if review else None, "reviewed_by": review[1] if review else None,
            "notes": review[2] if review else None, "period_days": days, "source": source,
            "status": review_status["status"] if review_status else None,
            "next_due_at": review_status["next_due_at"].isoformat() if review_status and review_status["next_due_at"] else None,
        },
    }


def review_plan(conn: psycopg.Connection, tenant_id: str, reviewed_on: date, reviewed_by: str, notes: str | None = None) -> dict:
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            conn.execute("INSERT INTO lab_plan_review (tenant_id, reviewed_on, reviewed_by, notes) VALUES (%s, %s, %s, %s)",
                         (tenant_id, reviewed_on, reviewed_by, (notes or "").strip() or None))
    return list_plan(conn, tenant_id, datetime.now(timezone.utc))["review"]


# ── Muestras y resultados ─────────────────────────────────────────────

def record_lab_sample(
    conn: psycopg.Connection,
    tenant_id: str,
    sampled_at: datetime,
    laboratory: str,
    results: list[dict],
    recorded_by: str,
    sampling_point_id: str | None = None,
    plan_item_id: str | None = None,
    report_ref: str | None = None,
    reason: str = "plan",
    notes: str | None = None,
    discharge_id: str | None = None,
) -> dict:
    """Guarda una muestra con sus resultados. `results`: [{parameter_code,
    value, qualifier?}]. Devuelve la muestra con cada resultado
    interpretado, los hallazgos y si hubo un resultado critico."""
    laboratory = (laboratory or "").strip()
    if not laboratory:
        raise InvalidRecordError("Indique el laboratorio que hizo el análisis")
    if reason not in SAMPLE_REASONS:
        raise InvalidRecordError(f"Motivo inválido: {reason!r} (válidos: {list(SAMPLE_REASONS)})")
    if not results:
        raise InvalidRecordError("La muestra necesita al menos un resultado")
    codes = [r.get("parameter_code") for r in results]
    if len(set(codes)) != len(codes):
        raise InvalidRecordError("Un parámetro aparece dos veces en la misma muestra")
    with conn.cursor() as cur:
        cur.execute("SELECT code, label, unit FROM parameter WHERE code = ANY(%s)", (codes,))
        params = {r[0]: (r[1], r[2]) for r in cur.fetchall()}
    unknown = sorted(set(codes) - set(params))
    if unknown:
        raise QualityNotFoundError(f"Parámetros desconocidos: {unknown}")
    _check_uuid(plan_item_id, "el plan")
    _check_uuid(discharge_id, "la descarga")

    interpreted = []
    for r in results:
        qualifier = r.get("qualifier") or "="
        try:
            rule = active_rule(conn, tenant_id, r["parameter_code"], sampled_at.date())
            interp = interpret_lab_result(rule["bands"], float(r["value"]), qualifier)
            rule_id = rule["rule_id"]
            status = "interpreted" if interp else "inconclusive"
        except RuleNotFoundError:
            if float(r["value"]) < 0:
                raise InvalidRecordError("El resultado no puede ser negativo") from None
            if qualifier not in ("=", "<", ">"):
                raise InvalidRecordError(f"Calificador invalido: {qualifier!r}") from None
            interp, rule_id, status = None, None, "no_rule"
        interpreted.append({**r, "qualifier": qualifier, "interp": interp, "rule_id": rule_id, "status": status})

    findings_created = 0
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                point_name = _assert_point(cur, tenant_id, sampling_point_id)
                if plan_item_id:
                    cur.execute("SELECT 1 FROM lab_plan_item WHERE id = %s AND tenant_id = %s", (plan_item_id, tenant_id))
                    if cur.fetchone() is None:
                        raise QualityNotFoundError(f"No existe el plan {plan_item_id} para esta organización")
                if discharge_id:
                    cur.execute("SELECT 1 FROM productive_discharge WHERE id = %s AND tenant_id = %s", (discharge_id, tenant_id))
                    if cur.fetchone() is None:
                        raise QualityNotFoundError(f"No existe la descarga {discharge_id} para esta organización")
                cur.execute(
                    "INSERT INTO lab_sample (tenant_id, sampling_point_id, plan_item_id, sampled_at, laboratory, report_ref, reason, "
                    "notes, recorded_by, discharge_id) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id",
                    (tenant_id, sampling_point_id, plan_item_id, sampled_at, laboratory, (report_ref or "").strip() or None,
                     reason, (notes or "").strip() or None, recorded_by, discharge_id),
                )
                sample_id = str(cur.fetchone()[0])
                for item in interpreted:
                    interp = item["interp"]
                    finding_id = None
                    if interp and interp["out_of_range"]:
                        source_ref = f"lab:{sampling_point_id or 'sin-punto'}:{item['parameter_code']}"
                        cur.execute(
                            "SELECT id FROM finding WHERE tenant_id = %s AND source_kind = 'reading' AND source_ref = ANY(%s) "
                            "AND status <> 'closed' ORDER BY created_at DESC LIMIT 1",
                            (tenant_id, [source_ref, source_ref.replace("lab:", "reading:", 1)]),
                        )
                        open_row = cur.fetchone()
                        if open_row:
                            finding_id = open_row[0]
                        else:
                            label, unit = params[item["parameter_code"]]
                            shown = f"{'' if item['qualifier'] == '=' else item['qualifier']}{float(item['value']):g}"
                            where = f" en {point_name}" if point_name else ""
                            critical = "ALERTA CRÍTICA. " if interp["severity"] == "critical" else ""
                            description = (f"{critical}Laboratorio: {label} {shown} {unit}{where} — {interp['label']}. "
                                           f"{interp['action'] or ''}").strip()
                            cur.execute(
                                "INSERT INTO finding (tenant_id, source_kind, source_ref, description, priority, created_by) "
                                "VALUES (%s, 'reading', %s, %s, %s, %s) RETURNING id",
                                (tenant_id, source_ref, description, interp["finding_priority"], recorded_by),
                            )
                            finding_id = cur.fetchone()[0]
                            findings_created += 1
                    cur.execute(
                        "INSERT INTO lab_result (tenant_id, sample_id, parameter_code, value, qualifier, rule_id, result_code, "
                        "result_label, severity, finding_id) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                        (tenant_id, sample_id, item["parameter_code"], item["value"], item["qualifier"], item["rule_id"],
                         interp["code"] if interp else None, interp["label"] if interp else None,
                         interp["severity"] if interp else None, finding_id),
                    )
    sample = get_lab_sample(conn, tenant_id, sample_id)
    # D5: un resultado que cumple una regla del paquete (E. coli presente)
    # activa la emergencia correspondiente (sin duplicar una ya activa).
    emergencies = auto_activate_from_results(conn, tenant_id, sample["results"], f"lab:{sample_id}", recorded_by)
    return {**sample, "findings_created": findings_created,
            "critical": any(r["severity"] == "critical" for r in sample["results"]),
            "emergencies": emergencies}


_SAMPLE_COLUMNS = ("s.id, s.sampling_point_id, sp.name, s.plan_item_id, pl.name, s.sampled_at, s.laboratory, s.report_ref, "
                   "s.reason, s.notes, s.recorded_by")


def _sample_head(r: tuple) -> dict:
    return {"sample_id": str(r[0]), "point_id": str(r[1]) if r[1] else None, "point_name": r[2],
            "plan_item_id": str(r[3]) if r[3] else None, "plan_name": r[4], "sampled_at": r[5].isoformat(),
            "laboratory": r[6], "report_ref": r[7], "reason": r[8], "notes": r[9], "recorded_by": r[10]}


def _results(cur: psycopg.Cursor, tenant_id: str, sample_ids: list[str]) -> dict[str, list[dict]]:
    cur.execute(
        "SELECT r.sample_id, r.parameter_code, p.label, p.unit, r.value, r.qualifier, r.result_code, r.result_label, "
        "r.severity, r.finding_id, r.rule_id FROM lab_result r JOIN parameter p ON p.code = r.parameter_code "
        "WHERE r.tenant_id = %s AND r.sample_id = ANY(%s) ORDER BY p.label",
        (tenant_id, sample_ids),
    )
    out: dict[str, list[dict]] = {}
    for r in cur.fetchall():
        out.setdefault(str(r[0]), []).append({
            "parameter_code": r[1], "parameter_label": r[2], "unit": r[3], "value": float(r[4]), "qualifier": r[5],
            "result_code": r[6], "result_label": r[7], "severity": r[8], "finding_id": str(r[9]) if r[9] else None,
            "interpretation": "interpreted" if r[6] else ("inconclusive" if r[10] else "no_rule"),
        })
    return out


def _sample_query(where: str) -> str:
    return (f"SELECT {_SAMPLE_COLUMNS} FROM lab_sample s LEFT JOIN sampling_point sp ON sp.id = s.sampling_point_id "
            f"LEFT JOIN lab_plan_item pl ON pl.id = s.plan_item_id WHERE s.tenant_id = %s AND {where}")


def get_lab_sample(conn: psycopg.Connection, tenant_id: str, sample_id: str) -> dict:
    _check_uuid(sample_id, "la muestra")
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(_sample_query("s.id = %s"), (tenant_id, sample_id))
                row = cur.fetchone()
                if row is None:
                    raise QualityNotFoundError(f"No existe la muestra {sample_id} para esta organización")
                head = _sample_head(row)
                head["results"] = _results(cur, tenant_id, [sample_id]).get(sample_id, [])
    return head


def list_lab_samples(conn: psycopg.Connection, tenant_id: str, point_id: str | None = None, limit: int = 100) -> list[dict]:
    _check_uuid(point_id, "el punto")
    where, params = ("s.sampling_point_id = %s", [point_id]) if point_id else ("TRUE", [])
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(_sample_query(where) + " ORDER BY s.sampled_at DESC LIMIT %s",
                            (tenant_id, *params, max(1, min(limit, 500))))
                heads = [_sample_head(r) for r in cur.fetchall()]
                results = _results(cur, tenant_id, [h["sample_id"] for h in heads]) if heads else {}
    for h in heads:
        h["results"] = results.get(h["sample_id"], [])
    return heads


def quality_overview(conn: psycopg.Connection, tenant_id: str, now: datetime) -> dict:
    """Alertas de calidad abiertas (hallazgos de mediciones y laboratorio sin
    cerrar, las criticas aparte), plan vencido y revision del plan."""
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT f.id, f.description, f.priority, f.status, f.created_at, "
                    "EXISTS (SELECT 1 FROM lab_result r WHERE r.finding_id = f.id AND r.severity = 'critical') "
                    "FROM finding f WHERE f.tenant_id = %s AND f.source_kind = 'reading' AND f.status <> 'closed' "
                    "ORDER BY f.created_at DESC",
                    (tenant_id,),
                )
                alerts = [{"finding_id": str(r[0]), "description": r[1], "priority": r[2], "status": r[3],
                           "created_at": r[4].isoformat(), "critical": r[5]} for r in cur.fetchall()]
    plan = list_plan(conn, tenant_id, now)
    return {
        "alerts": alerts,
        "critical_open": sum(1 for a in alerts if a["critical"]),
        "plan_overdue": sum(1 for p in plan["items"] if p["status"] in ("overdue", "never")),
        "plan": plan,
    }
