"""Servicio del motor de paquetes (Track D, Sprint D0.1). Ver
docs/04-plan-sprints.md SS11.4.

Lee los catalogos globales (`pack`, `component_type`, `parameter_rule`,
`checklist_template`, sin RLS y de solo lectura para el rol de
aplicacion) filtrados por los paquetes que adopto la junta
(`tenant_pack`), y escribe lo que hace la junta (`checklist_run`,
`checklist_answer`, `finding`, con RLS via `tenant_scope`). Toda logica de
evaluacion vive en `pack_engine.py`.

El paquete `core` aplica siempre, sin adoptarse.
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
from psycopg.types.json import Json  # noqa: E402

from pack_engine import (  # noqa: E402
    InvalidRecordError,
    answer_label,
    checklist_status,
    questionnaire_analysis,
    validate_run_context,
    evaluate_bands,
    follow_up_schedule,
    passport_rows,
    passport_summary,
    validate_follow_up_item_status,
    validate_product_status,
    stage_summary,
    findings_from_answers,
    maturity_score,
    system_route,
    treatment_train,
    validate_answers,
    validate_instrumentation,
)
from renmeter_common.db import tenant_scope  # noqa: E402

CORE_PACK = "core"
FINDING_STATUSES = {"open", "in_progress", "closed"}
FINDING_PRIORITIES = {"high", "medium", "low"}
SUPPORT_LEVELS = {"community", "local_government", "specialized"}
INSTRUMENTATION_KEY = "instrumentation"


class PackNotFoundError(LookupError):
    """No existe ese paquete en el catalogo."""


class TemplateNotAvailableError(LookupError):
    """La lista no existe o pertenece a un paquete que la junta no adopto."""


class RuleNotFoundError(LookupError):
    """Ningun paquete adoptado tiene una regla vigente para ese parametro."""


class AmbiguousRuleError(ValueError):
    """Dos paquetes adoptados tienen regla vigente para el mismo parametro.
    No se elige una en silencio: la junta debe quedar con un solo paquete
    normativo por parametro."""


class FindingNotFoundError(LookupError):
    """No existe ese hallazgo para esta junta."""


class InvalidFindingError(ValueError):
    """Prioridad, nivel de apoyo o estado fuera de los valores validos."""


class RunNotFoundError(LookupError):
    """No existe esa aplicacion de lista para esta junta."""


class ProductNotFoundError(LookupError):
    """El producto no existe en el catalogo o su paquete no esta activo."""


class FollowUpNotFoundError(LookupError):
    """Ciclo, compromiso o momento de seguimiento inexistente para esta junta."""


class AssetNotFoundError(LookupError):
    """El activo no existe o es de otra junta. La FK de `finding.asset_id`
    solo comprueba que exista; la pertenencia se verifica aca, igual que
    `asset_service.connect_assets`."""


def _assert_assets_belong(conn: psycopg.Connection, tenant_id: str, asset_ids: set[str]) -> None:
    if not asset_ids:
        return
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id::text FROM network_asset WHERE tenant_id = %s AND id::text = ANY(%s)",
                    (tenant_id, list(asset_ids)),
                )
                found = {r[0] for r in cur.fetchall()}
    missing = asset_ids - found
    if missing:
        raise AssetNotFoundError(f"Activos inexistentes para esta junta: {sorted(missing)}")


# ── Paquetes ──────────────────────────────────────────────────────────

def list_packs(conn: psycopg.Connection) -> list[dict]:
    with conn.cursor() as cur:
        cur.execute("SELECT id, kind, country, name, version, source_note, is_default FROM pack ORDER BY kind, id")
        rows = cur.fetchall()
    return [
        {"pack_id": r[0], "kind": r[1], "country": r[2], "name": r[3], "version": r[4], "source_note": r[5],
         "is_default": r[6]}
        for r in rows
    ]


def active_pack_ids(conn: psycopg.Connection, tenant_id: str) -> list[str]:
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute("SELECT pack_id FROM tenant_pack WHERE tenant_id = %s ORDER BY adopted_at", (tenant_id,))
                adopted = [r[0] for r in cur.fetchall()]
    return [CORE_PACK] + [p for p in adopted if p != CORE_PACK]


def unadopt_pack(conn: psycopg.Connection, tenant_id: str, pack_id: str) -> dict:
    """Desactiva un paquete para esta organizacion (0025): p. ej. para usar
    el paquete normativo de otro pais en lugar del base. `core` no se
    desactiva. Lo ya registrado (revisiones, hallazgos) se conserva."""
    if pack_id == CORE_PACK:
        raise PackNotFoundError("El paquete core no se puede desactivar")
    with conn.cursor() as cur:
        cur.execute("SELECT 1 FROM pack WHERE id = %s", (pack_id,))
        if cur.fetchone() is None:
            raise PackNotFoundError(f"No existe el paquete {pack_id!r}")
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute("DELETE FROM tenant_pack WHERE tenant_id = %s AND pack_id = %s", (tenant_id, pack_id))
    return {"pack_id": pack_id, "active_packs": active_pack_ids(conn, tenant_id)}


def adopt_pack(conn: psycopg.Connection, tenant_id: str, pack_id: str) -> dict:
    with conn.cursor() as cur:
        cur.execute("SELECT kind FROM pack WHERE id = %s", (pack_id,))
        row = cur.fetchone()
    if row is None:
        raise PackNotFoundError(f"No existe el paquete {pack_id!r}")
    if pack_id != CORE_PACK:
        with conn.transaction():
            with tenant_scope(conn, tenant_id):
                with conn.cursor() as cur:
                    cur.execute(
                        "INSERT INTO tenant_pack (tenant_id, pack_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                        (tenant_id, pack_id),
                    )
    return {"pack_id": pack_id, "active_packs": active_pack_ids(conn, tenant_id)}


# ── Tipos de componente ───────────────────────────────────────────────

def list_component_types(conn: psycopg.Connection, tenant_id: str) -> list[dict]:
    packs = active_pack_ids(conn, tenant_id)
    with conn.cursor() as cur:
        cur.execute(
            "SELECT code, pack_id, service, stage_order, is_treatment_stage, label, description "
            "FROM component_type WHERE pack_id = ANY(%s) "
            "ORDER BY service, stage_order NULLS LAST, label",
            (packs,),
        )
        rows = cur.fetchall()
    return [
        {"code": r[0], "pack_id": r[1], "service": r[2], "stage_order": r[3],
         "is_treatment_stage": r[4], "label": r[5], "description": r[6]}
        for r in rows
    ]


def component_type_exists(conn: psycopg.Connection, tenant_id: str, code: str) -> bool:
    return any(t["code"] == code for t in list_component_types(conn, tenant_id))


# ── Parametros y reglas ───────────────────────────────────────────────

def active_rule(conn: psycopg.Connection, tenant_id: str, parameter_code: str, on: date | None = None) -> dict:
    on = on or date.today()
    packs = active_pack_ids(conn, tenant_id)
    with conn.cursor() as cur:
        cur.execute(
            "SELECT r.id, r.pack_id, r.bands, r.citation, p.label, p.unit, p.measured_by "
            "FROM parameter_rule r JOIN parameter p ON p.code = r.parameter_code "
            "WHERE r.parameter_code = %s AND r.pack_id = ANY(%s) "
            "AND (r.valid_from IS NULL OR r.valid_from <= %s) AND (r.valid_to IS NULL OR r.valid_to >= %s)",
            (parameter_code, packs, on, on),
        )
        rows = cur.fetchall()
    if not rows:
        raise RuleNotFoundError(f"Ningún paquete adoptado tiene una regla vigente para {parameter_code!r}")
    if len({r[1] for r in rows}) > 1:
        raise AmbiguousRuleError(
            f"Hay más de un paquete adoptado con regla para {parameter_code!r}: {sorted({r[1] for r in rows})}"
        )
    r = rows[0]
    return {
        "rule_id": str(r[0]), "pack_id": r[1], "bands": r[2], "citation": r[3],
        "parameter": {"code": parameter_code, "label": r[4], "unit": r[5], "measured_by": r[6]},
    }


def list_active_rules(conn: psycopg.Connection, tenant_id: str) -> list[dict]:
    with conn.cursor() as cur:
        cur.execute("SELECT code FROM parameter ORDER BY code")
        codes = [r[0] for r in cur.fetchall()]
    rules = []
    for code in codes:
        try:
            rules.append(active_rule(conn, tenant_id, code))
        except RuleNotFoundError:
            continue
    return rules


def evaluate_parameter(conn: psycopg.Connection, tenant_id: str, parameter_code: str, value: float) -> dict:
    rule = active_rule(conn, tenant_id, parameter_code)
    return {
        "parameter": rule["parameter"], "value": value,
        "result": evaluate_bands(rule["bands"], value),
        "pack_id": rule["pack_id"], "citation": rule["citation"],
    }


# ── Listas de verificacion ────────────────────────────────────────────

def list_checklist_templates(conn: psycopg.Connection, tenant_id: str) -> list[dict]:
    packs = active_pack_ids(conn, tenant_id)
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id, pack_id, kind, title, purpose, scale, items, stage_code, frequency_days, run_fields, analysis "
            "FROM checklist_template "
            "WHERE pack_id = ANY(%s) ORDER BY id",
            (packs,),
        )
        rows = cur.fetchall()
    return [
        {"id": r[0], "pack_id": r[1], "kind": r[2], "title": r[3], "purpose": r[4], "scale": r[5], "items": r[6],
         "stage_code": r[7], "frequency_days": r[8], "run_fields": r[9], "analysis": r[10]}
        for r in rows
    ]


def _template(conn: psycopg.Connection, tenant_id: str, template_id: str) -> dict:
    for template in list_checklist_templates(conn, tenant_id):
        if template["id"] == template_id:
            return template
    raise TemplateNotAvailableError(f"La lista {template_id!r} no existe o su paquete no está adoptado")


def submit_checklist_run(
    conn: psycopg.Connection,
    tenant_id: str,
    template_id: str,
    answers: list[dict],
    performed_by: str,
    notes: str | None = None,
    context: dict | None = None,
) -> dict:
    """Guarda una aplicacion completa de la lista y crea, en la misma
    transaccion, un hallazgo por cada respuesta que la escala marca como
    hallazgo. `answers`: [{item_key, answer_code, observation?, action?,
    responsible?, due_date?, asset_id?}]. `context`: los datos que pide la
    plantilla en `run_fields` (p. ej. momento y codigo de participante)."""
    template = _template(conn, tenant_id, template_id)
    validate_answers(template, answers)
    clean_context = validate_run_context(template, context)
    pending_findings = findings_from_answers(template, answers)
    asset_by_item = {a["item_key"]: a.get("asset_id") for a in answers}
    _assert_assets_belong(conn, tenant_id, {a for a in asset_by_item.values() if a})

    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO checklist_run (tenant_id, template_id, performed_by, notes, context) "
                    "VALUES (%s, %s, %s, %s, %s) RETURNING id, performed_at",
                    (tenant_id, template_id, performed_by, notes, Json(clean_context)),
                )
                run_id, performed_at = cur.fetchone()
                for a in answers:
                    cur.execute(
                        "INSERT INTO checklist_answer (run_id, tenant_id, item_key, answer_code, observation, "
                        "action, responsible, due_date) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                        (run_id, tenant_id, a["item_key"], a["answer_code"], a.get("observation"),
                         a.get("action"), a.get("responsible"), a.get("due_date")),
                    )
                finding_ids = []
                for f in pending_findings:
                    cur.execute(
                        "INSERT INTO finding (tenant_id, source_kind, source_ref, asset_id, description, priority, created_by) "
                        "VALUES (%s, 'checklist', %s, %s, %s, %s, %s) RETURNING id",
                        (tenant_id, f"{run_id}:{f['item_key']}", asset_by_item.get(f["item_key"]),
                         f["description"], f["priority"], performed_by),
                    )
                    finding_ids.append(str(cur.fetchone()[0]))

    return {
        "run_id": str(run_id), "template_id": template_id, "performed_at": performed_at.isoformat(),
        "context": clean_context, "score": maturity_score(template, answers), "findings_created": finding_ids,
    }


def list_checklist_runs(conn: psycopg.Connection, tenant_id: str, template_id: str | None = None) -> list[dict]:
    """Historial con el puntaje y los hallazgos que dejo cada aplicacion,
    para que el historial diga algo sin tener que abrir cada revision."""
    params: list[Any] = [tenant_id]
    clause = ""
    if template_id:
        clause = "AND r.template_id = %s"
        params.append(template_id)
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT r.id, r.template_id, r.performed_at, r.performed_by, r.notes, "
                    "coalesce(jsonb_agg(jsonb_build_object('item_key', a.item_key, 'answer_code', a.answer_code)) "
                    "         FILTER (WHERE a.item_key IS NOT NULL), '[]'::jsonb), "
                    "(SELECT count(*) FROM finding f WHERE f.tenant_id = r.tenant_id AND f.source_ref LIKE r.id::text || ':%%'), "
                    "r.context "
                    "FROM checklist_run r LEFT JOIN checklist_answer a ON a.run_id = r.id "
                    f"WHERE r.tenant_id = %s {clause} GROUP BY r.id ORDER BY r.performed_at DESC",
                    params,
                )
                rows = cur.fetchall()
    templates = {t["id"]: t for t in list_checklist_templates(conn, tenant_id)}
    result = []
    for r in rows:
        template = templates.get(r[1])
        result.append({
            "run_id": str(r[0]), "template_id": r[1], "performed_at": r[2].isoformat(),
            "performed_by": r[3], "notes": r[4], "answer_count": len(r[5]),
            "score": maturity_score(template, r[5]) if template else None,
            "findings_count": r[6], "context": r[7],
        })
    return result


def process_route(conn: psycopg.Connection, tenant_id: str, now: datetime | None = None) -> dict:
    """Ruta del programa (0023): las etapas de los paquetes de programa
    adoptados, en orden, con sus listas y el estado de cada una (sin
    aplicar, al dia, vencida, aplicada). Las listas sin etapa van aparte.
    Las etapas sin listas todavia se muestran: la ruta completa es parte de
    la informacion, aunque la plataforma aun no cubra esa etapa."""
    now = now or datetime.now(timezone.utc)
    packs = active_pack_ids(conn, tenant_id)
    with conn.cursor() as cur:
        cur.execute(
            "SELECT pack_id, code, sort_order, title, source_ref, purpose FROM process_stage "
            "WHERE pack_id = ANY(%s) ORDER BY pack_id, sort_order",
            (packs,),
        )
        stage_rows = cur.fetchall()
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT DISTINCT ON (template_id) template_id, id, performed_at FROM checklist_run "
                    "WHERE tenant_id = %s ORDER BY template_id, performed_at DESC",
                    (tenant_id,),
                )
                last_runs = {r[0]: (str(r[1]), r[2]) for r in cur.fetchall()}

    def describe(t: dict) -> dict:
        run_id, last_at = last_runs.get(t["id"], (None, None))
        st = checklist_status(t["frequency_days"], last_at, now)
        return {
            "template_id": t["id"], "title": t["title"], "kind": t["kind"], "purpose": t["purpose"],
            "item_count": len(t["items"]), "frequency_days": t["frequency_days"],
            "last_run_id": run_id, "last_run_at": last_at.isoformat() if last_at else None,
            "status": st["status"], "days_to_due": st["days_to_due"],
            "next_due_at": st["next_due_at"].isoformat() if st["next_due_at"] else None,
        }

    templates = list_checklist_templates(conn, tenant_id)
    stages = []
    staged: set[str] = set()
    products = passport_rows(_catalog_products(conn, packs), _product_records(conn, tenant_id))
    with conn.cursor() as cur:
        cur.execute("SELECT DISTINCT pack_id, stage_code FROM follow_up_milestone WHERE pack_id = ANY(%s)", (packs,))
        follow_up_stages = {(r[0], r[1]) for r in cur.fetchall()}
    for pack_id, code, order, title, source_ref, purpose in stage_rows:
        stage_products = [p for p in products if p["pack_id"] == pack_id and p["stage_code"] == code]
        lists = [describe(t) for t in templates if t["pack_id"] == pack_id and t["stage_code"] == code]
        staged.update(item["template_id"] for item in lists)
        stages.append({
            "pack_id": pack_id, "code": code, "order": order, "title": title, "source_ref": source_ref,
            "purpose": purpose, "products": stage_products, "products_summary": passport_summary(stage_products),
            "has_follow_up": (pack_id, code) in follow_up_stages,
            "lists": lists, "summary": stage_summary(lists),
        })
    other = [describe(t) for t in templates if t["id"] not in staged]
    return {"stages": stages, "other_lists": other}


def get_checklist_run(conn: psycopg.Connection, tenant_id: str, run_id: str) -> dict:
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT template_id, performed_at, performed_by, notes, context FROM checklist_run "
                    "WHERE id = %s AND tenant_id = %s",
                    (run_id, tenant_id),
                )
                run = cur.fetchone()
                if run is None:
                    raise RunNotFoundError(f"No existe la aplicación {run_id} para esta junta")
                cur.execute(
                    "SELECT item_key, answer_code, observation, action, responsible, due_date "
                    "FROM checklist_answer WHERE run_id = %s AND tenant_id = %s",
                    (run_id, tenant_id),
                )
                answer_rows = cur.fetchall()
    template = _template(conn, tenant_id, run[0])
    by_key = {r[0]: r for r in answer_rows}
    answers = []
    for item in template["items"]:
        r = by_key.get(item["key"])
        if r is None:
            continue
        answers.append({
            "item_key": item["key"], "text": item["text"], "answer_code": r[1],
            "answer_label": answer_label(template, item, r[1]), "observation": r[2], "action": r[3],
            "responsible": r[4], "due_date": r[5].isoformat() if r[5] else None,
        })
    return {
        "run_id": run_id, "template_id": run[0], "title": template["title"], "kind": template["kind"],
        "performed_at": run[1].isoformat(), "performed_by": run[2], "notes": run[3], "context": run[4],
        "answers": answers,
        "score": maturity_score(template, answers),
    }


def questionnaire_report(conn: psycopg.Connection, tenant_id: str, template_id: str) -> dict:
    """Analisis de un cuestionario (CAP: clave y matriz T-05) con todas las
    aplicaciones de la junta. Si un participante respondio dos veces en el
    mismo momento, cuenta su ultima aplicacion."""
    template = _template(conn, tenant_id, template_id)
    if not template.get("analysis"):
        raise TemplateNotAvailableError(f"La lista {template_id!r} no tiene análisis de cuestionario")
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT r.id, r.context, r.performed_at, "
                    "coalesce(jsonb_agg(jsonb_build_object('item_key', a.item_key, 'answer_code', a.answer_code)) "
                    "         FILTER (WHERE a.item_key IS NOT NULL), '[]'::jsonb) "
                    "FROM checklist_run r LEFT JOIN checklist_answer a ON a.run_id = r.id "
                    "WHERE r.tenant_id = %s AND r.template_id = %s GROUP BY r.id ORDER BY r.performed_at",
                    (tenant_id, template_id),
                )
                rows = cur.fetchall()
    compare_by = template["analysis"]["compare_by"]
    participant_key = template["analysis"].get("participant_field")
    latest: dict[tuple, dict] = {}
    for run_id, context, _at, answers in rows:
        key = (context.get(compare_by), context.get(participant_key)) if participant_key else (str(run_id),)
        latest[key] = {"context": context, "answers": answers}
    report = questionnaire_analysis(template, list(latest.values()))
    if participant_key:
        moments = [m["code"] for m in template["analysis"]["compare"]]
        sets = [{k[1] for k in latest if k[0] == m} for m in moments]
        report["paired_participants"] = len(set.intersection(*sets)) if sets else 0
    report["title"] = template["title"]
    return report


def latest_traffic_light(conn: psycopg.Connection, tenant_id: str) -> dict | None:
    """El semaforo vigente: la ultima aplicacion de una lista de tipo
    `traffic_light` de los paquetes adoptados. `None` si nunca se aplico."""
    ids = [t["id"] for t in list_checklist_templates(conn, tenant_id) if t["kind"] == "traffic_light"]
    if not ids:
        return None
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id FROM checklist_run WHERE tenant_id = %s AND template_id = ANY(%s) "
                    "ORDER BY performed_at DESC LIMIT 1",
                    (tenant_id, ids),
                )
                row = cur.fetchone()
    return get_checklist_run(conn, tenant_id, str(row[0])) if row else None


# ── Hallazgos ─────────────────────────────────────────────────────────

def _validate_finding_fields(priority: str | None, support_level: str | None, status: str | None) -> None:
    if priority is not None and priority not in FINDING_PRIORITIES:
        raise InvalidFindingError(f"Prioridad inválida: {priority!r} (válidas: {sorted(FINDING_PRIORITIES)})")
    if support_level is not None and support_level not in SUPPORT_LEVELS:
        raise InvalidFindingError(f"Nivel de apoyo inválido: {support_level!r} (válidos: {sorted(SUPPORT_LEVELS)})")
    if status is not None and status not in FINDING_STATUSES:
        raise InvalidFindingError(f"Estado inválido: {status!r} (válidos: {sorted(FINDING_STATUSES)})")


def create_finding(
    conn: psycopg.Connection,
    tenant_id: str,
    description: str,
    priority: str,
    created_by: str,
    source_kind: str = "manual",
    asset_id: str | None = None,
    location_text: str | None = None,
    geometry: dict | None = None,
    support_level: str | None = None,
) -> dict:
    """Punto critico del mapa tecnico (`critical_point`) o hallazgo manual.
    Los de listas los crea `submit_checklist_run`; los de lecturas, D1."""
    if source_kind not in {"critical_point", "manual"}:
        raise InvalidFindingError("Solo se crean a mano hallazgos 'critical_point' o 'manual'")
    _validate_finding_fields(priority, support_level, None)
    _assert_assets_belong(conn, tenant_id, {asset_id} if asset_id else set())
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO finding (tenant_id, source_kind, asset_id, location_text, geometry, description, "
                    "priority, support_level, created_by) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id",
                    (tenant_id, source_kind, asset_id, location_text, Json(geometry) if geometry else None,
                     description, priority, support_level, created_by),
                )
                (finding_id,) = cur.fetchone()
    return {"finding_id": str(finding_id)}


def _finding_row(r: tuple) -> dict:
    return {
        "finding_id": str(r[0]), "source_kind": r[1], "source_ref": r[2],
        "asset_id": str(r[3]) if r[3] else None, "location_text": r[4], "geometry": r[5],
        "description": r[6], "priority": r[7], "support_level": r[8], "status": r[9],
        "to_improvement_plan": r[10], "created_by": r[11], "created_at": r[12].isoformat(),
        "closed_at": r[13].isoformat() if r[13] else None,
    }


_FINDING_COLUMNS = (
    "id, source_kind, source_ref, asset_id, location_text, geometry, description, priority, "
    "support_level, status, to_improvement_plan, created_by, created_at, closed_at"
)


def list_findings(conn: psycopg.Connection, tenant_id: str, status: str | None = None) -> list[dict]:
    _validate_finding_fields(None, None, status)
    params: list[Any] = [tenant_id]
    clause = ""
    if status:
        clause = "AND status = %s"
        params.append(status)
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT {_FINDING_COLUMNS} FROM finding WHERE tenant_id = %s {clause} "
                    "ORDER BY CASE priority WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END, created_at DESC",
                    params,
                )
                rows = cur.fetchall()
    return [_finding_row(r) for r in rows]


def update_finding(
    conn: psycopg.Connection,
    tenant_id: str,
    finding_id: str,
    status: str | None = None,
    priority: str | None = None,
    support_level: str | None = None,
    to_improvement_plan: bool | None = None,
) -> dict:
    _validate_finding_fields(priority, support_level, status)
    sets, params = [], []
    if status is not None:
        sets.append("status = %s")
        params.append(status)
        sets.append("closed_at = CASE WHEN %s::text = 'closed' THEN now() ELSE NULL END")
        params.append(status)
    if priority is not None:
        sets.append("priority = %s")
        params.append(priority)
    if support_level is not None:
        sets.append("support_level = %s")
        params.append(support_level)
    if to_improvement_plan is not None:
        sets.append("to_improvement_plan = %s")
        params.append(to_improvement_plan)
    if not sets:
        raise InvalidFindingError("No hay nada que actualizar")
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    f"UPDATE finding SET {', '.join(sets)} WHERE id = %s AND tenant_id = %s RETURNING {_FINDING_COLUMNS}",
                    params + [finding_id, tenant_id],
                )
                row = cur.fetchone()
    if row is None:
        raise FindingNotFoundError(f"No existe el hallazgo {finding_id} para esta junta")
    return _finding_row(row)


# ── Reportes que salen de la operacion ────────────────────────────────

def _tenant_assets(conn: psycopg.Connection, tenant_id: str) -> list[dict]:
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id, type, status, attributes, zone_id FROM network_asset WHERE tenant_id = %s",
                    (tenant_id,),
                )
                rows = cur.fetchall()
    return [
        {"asset_id": str(r[0]), "type": r[1], "status": r[2], "attributes": r[3],
         "zone_id": str(r[4]) if r[4] else None}
        for r in rows
    ]


def system_route_report(conn: psycopg.Connection, tenant_id: str) -> dict:
    return system_route(list_component_types(conn, tenant_id), _tenant_assets(conn, tenant_id))


def treatment_train_report(conn: psycopg.Connection, tenant_id: str) -> list[dict]:
    open_findings = [f for f in list_findings(conn, tenant_id) if f["status"] != "closed"]
    return treatment_train(list_component_types(conn, tenant_id), _tenant_assets(conn, tenant_id), open_findings)


# ── Nivel de instrumentacion (tenant.config, sin migracion) ───────────

def get_instrumentation(conn: psycopg.Connection, tenant_id: str) -> dict[str, str]:
    """Modulos sin nivel declarado no aparecen: nunca se asume un nivel."""
    with conn.cursor() as cur:
        cur.execute("SELECT config -> %s FROM tenant WHERE id = %s", (INSTRUMENTATION_KEY, tenant_id))
        row = cur.fetchone()
    return dict(row[0]) if row and row[0] else {}


def set_instrumentation(conn: psycopg.Connection, tenant_id: str, levels: dict[str, str]) -> dict[str, str]:
    validate_instrumentation(levels)
    merged = {**get_instrumentation(conn, tenant_id), **levels}
    with conn.transaction():
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE tenant SET config = config || jsonb_build_object(%s::text, %s::jsonb) WHERE id = %s",
                (INSTRUMENTATION_KEY, Json(merged), tenant_id),
            )
    return merged


# ── Pasaporte de productos (T-07, 0028) ────────────────────────────────

def _catalog_products(conn: psycopg.Connection, packs: list[str]) -> list[dict]:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT p.pack_id, p.code, p.stage_code, p.sort_order, p.title FROM process_product p "
            "JOIN process_stage s ON s.pack_id = p.pack_id AND s.code = p.stage_code "
            "WHERE p.pack_id = ANY(%s) ORDER BY p.pack_id, s.sort_order, p.sort_order",
            (packs,),
        )
        return [{"pack_id": r[0], "code": r[1], "stage_code": r[2], "sort_order": r[3], "title": r[4]} for r in cur.fetchall()]


def _product_records(conn: psycopg.Connection, tenant_id: str) -> dict[tuple[str, str], dict]:
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT pack_id, product_code, status, evidence, to_improvement_plan, updated_at, updated_by "
                    "FROM product_record WHERE tenant_id = %s",
                    (tenant_id,),
                )
                rows = cur.fetchall()
    return {
        (r[0], r[1]): {"status": r[2], "evidence": r[3], "to_improvement_plan": r[4],
                       "updated_at": r[5].isoformat(), "updated_by": r[6]}
        for r in rows
    }


def passport(conn: psycopg.Connection, tenant_id: str) -> dict:
    """Pasaporte completo (T-07): cada etapa de la ruta con sus productos,
    su estado, evidencia y si pasa al Plan de Mejora."""
    packs = active_pack_ids(conn, tenant_id)
    rows = passport_rows(_catalog_products(conn, packs), _product_records(conn, tenant_id))
    with conn.cursor() as cur:
        cur.execute(
            "SELECT pack_id, code, sort_order, title, source_ref FROM process_stage "
            "WHERE pack_id = ANY(%s) ORDER BY pack_id, sort_order",
            (packs,),
        )
        stages = []
        for pack_id, code, order, title, source_ref in cur.fetchall():
            own = [r for r in rows if r["pack_id"] == pack_id and r["stage_code"] == code]
            stages.append({"pack_id": pack_id, "code": code, "order": order, "title": title, "source_ref": source_ref,
                           "products": own, "summary": passport_summary(own)})
    return {"stages": stages, "summary": passport_summary(rows)}


def set_product_record(
    conn: psycopg.Connection,
    tenant_id: str,
    pack_id: str,
    product_code: str,
    status: str,
    updated_by: str,
    evidence: str | None = None,
    to_improvement_plan: bool = False,
) -> dict:
    validate_product_status(status)
    if pack_id not in active_pack_ids(conn, tenant_id):
        raise ProductNotFoundError(f"El paquete {pack_id!r} no está activo para esta junta")
    with conn.cursor() as cur:
        cur.execute("SELECT 1 FROM process_product WHERE pack_id = %s AND code = %s", (pack_id, product_code))
        if cur.fetchone() is None:
            raise ProductNotFoundError(f"No existe el producto {product_code!r} en {pack_id}")
    evidence = (evidence or "").strip() or None
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO product_record (tenant_id, pack_id, product_code, status, evidence, to_improvement_plan, updated_by) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s) "
                    "ON CONFLICT (tenant_id, pack_id, product_code) DO UPDATE SET status = EXCLUDED.status, "
                    "evidence = EXCLUDED.evidence, to_improvement_plan = EXCLUDED.to_improvement_plan, "
                    "updated_by = EXCLUDED.updated_by, updated_at = now() RETURNING updated_at",
                    (tenant_id, pack_id, product_code, status, evidence, to_improvement_plan, updated_by),
                )
                updated_at = cur.fetchone()[0]
    return {"pack_id": pack_id, "code": product_code, "status": status, "evidence": evidence,
            "to_improvement_plan": to_improvement_plan, "updated_at": updated_at.isoformat(), "updated_by": updated_by}


# ── Seguimiento 7-30-90 (T-09, 0028) ───────────────────────────────────

_ITEM_COLUMNS = ("id, cycle_id, milestone_code, commitment, responsible, due_date, status, situation, evidence, "
                 "adjustment_action, created_by, updated_at")


def _item_row(r: tuple) -> dict:
    return {
        "item_id": str(r[0]), "cycle_id": str(r[1]), "milestone_code": r[2], "commitment": r[3], "responsible": r[4],
        "due_date": r[5].isoformat() if r[5] else None, "status": r[6], "situation": r[7], "evidence": r[8],
        "adjustment_action": r[9], "created_by": r[10], "updated_at": r[11].isoformat(),
    }


def _milestones(conn: psycopg.Connection, pack_id: str) -> list[dict]:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT code, stage_code, sort_order, offset_days, label, review, evidence FROM follow_up_milestone "
            "WHERE pack_id = %s ORDER BY sort_order",
            (pack_id,),
        )
        return [{"code": r[0], "stage_code": r[1], "sort_order": r[2], "offset_days": r[3], "label": r[4],
                 "review": r[5], "evidence": r[6]} for r in cur.fetchall()]


def follow_up(conn: psycopg.Connection, tenant_id: str, today: date | None = None) -> dict:
    """Ciclos de seguimiento de la junta (el mas reciente primero), cada uno
    con sus momentos fechados, compromisos y revisiones. `programs`: los
    paquetes activos que definen seguimiento (para abrir un ciclo)."""
    today = today or datetime.now(timezone.utc).date()
    packs = active_pack_ids(conn, tenant_id)
    with conn.cursor() as cur:
        cur.execute(
            "SELECT DISTINCT m.pack_id, p.name FROM follow_up_milestone m JOIN pack p ON p.id = m.pack_id "
            "WHERE m.pack_id = ANY(%s) ORDER BY 1",
            (packs,),
        )
        programs = [{"pack_id": r[0], "name": r[1]} for r in cur.fetchall()]
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id, pack_id, anchor_date, title, created_at, created_by FROM follow_up_cycle "
                    "WHERE tenant_id = %s AND pack_id = ANY(%s) ORDER BY anchor_date DESC, created_at DESC",
                    (tenant_id, packs),
                )
                cycles = cur.fetchall()
                cur.execute(f"SELECT {_ITEM_COLUMNS} FROM follow_up_item WHERE tenant_id = %s ORDER BY created_at",
                            (tenant_id,))
                items = [_item_row(r) for r in cur.fetchall()]
                cur.execute(
                    "SELECT cycle_id, milestone_code, reviewed_on, reviewed_by, summary FROM follow_up_review "
                    "WHERE tenant_id = %s",
                    (tenant_id,),
                )
                reviews = cur.fetchall()
    result = []
    for cid, pack_id, anchor, title, created_at, created_by in cycles:
        own_reviews = {r[1]: {"reviewed_on": r[2].isoformat(), "reviewed_by": r[3], "summary": r[4]}
                       for r in reviews if r[0] == cid}
        own_items = [i for i in items if i["cycle_id"] == str(cid)]
        result.append({
            "cycle_id": str(cid), "pack_id": pack_id, "anchor_date": anchor.isoformat(), "title": title,
            "created_at": created_at.isoformat(), "created_by": created_by,
            "milestones": follow_up_schedule(_milestones(conn, pack_id), anchor, own_reviews, own_items, today),
        })
    return {"programs": programs, "cycles": result}


def create_follow_up_cycle(
    conn: psycopg.Connection, tenant_id: str, pack_id: str, anchor_date: date, title: str, created_by: str,
) -> dict:
    if pack_id not in active_pack_ids(conn, tenant_id) or not _milestones(conn, pack_id):
        raise FollowUpNotFoundError(f"El paquete {pack_id!r} no está activo o no define seguimiento")
    title = title.strip()
    if not title:
        raise InvalidRecordError("El ciclo necesita un nombre (p. ej. la cohorte o el taller)")
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO follow_up_cycle (tenant_id, pack_id, anchor_date, title, created_by) "
                    "VALUES (%s, %s, %s, %s, %s) RETURNING id",
                    (tenant_id, pack_id, anchor_date, title, created_by),
                )
                return {"cycle_id": str(cur.fetchone()[0]), "pack_id": pack_id, "anchor_date": anchor_date.isoformat(),
                        "title": title}


def _uuid_or_not_found(value: str, what: str) -> None:
    try:
        uuid.UUID(value)
    except ValueError:
        raise FollowUpNotFoundError(f"No existe {what} {value!r}") from None


def _cycle_pack(conn: psycopg.Connection, tenant_id: str, cycle_id: str) -> str:
    _uuid_or_not_found(cycle_id, "el ciclo de seguimiento")
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute("SELECT pack_id FROM follow_up_cycle WHERE id = %s AND tenant_id = %s", (cycle_id, tenant_id))
                row = cur.fetchone()
    if row is None:
        raise FollowUpNotFoundError(f"No existe el ciclo de seguimiento {cycle_id} para esta junta")
    return row[0]


def _assert_milestone(conn: psycopg.Connection, pack_id: str, milestone_code: str) -> None:
    if milestone_code not in {m["code"] for m in _milestones(conn, pack_id)}:
        raise FollowUpNotFoundError(f"El momento {milestone_code!r} no existe en el seguimiento de {pack_id}")


def add_follow_up_item(
    conn: psycopg.Connection,
    tenant_id: str,
    cycle_id: str,
    milestone_code: str,
    commitment: str,
    created_by: str,
    responsible: str | None = None,
    due_date: date | None = None,
) -> dict:
    """Compromiso acordado para un momento (A-06 del dia 8)."""
    pack_id = _cycle_pack(conn, tenant_id, cycle_id)
    _assert_milestone(conn, pack_id, milestone_code)
    commitment = commitment.strip()
    if not commitment:
        raise InvalidRecordError("El compromiso no puede ir vacío")
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO follow_up_item (tenant_id, cycle_id, pack_id, milestone_code, commitment, responsible, "
                    f"due_date, created_by) VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING {_ITEM_COLUMNS}",
                    (tenant_id, cycle_id, pack_id, milestone_code, commitment, responsible or None, due_date, created_by),
                )
                return _item_row(cur.fetchone())


_ITEM_FIELDS = ("commitment", "responsible", "due_date", "status", "situation", "evidence", "adjustment_action")


def update_follow_up_item(conn: psycopg.Connection, tenant_id: str, item_id: str, **fields: Any) -> dict:
    """Lo encontrado al revisar el compromiso: situacion, evidencia, accion
    de ajuste y estado (cumplido / no cumplido / pendiente)."""
    unknown = set(fields) - set(_ITEM_FIELDS)
    if unknown:
        raise InvalidRecordError(f"Campos no editables: {sorted(unknown)}")
    _uuid_or_not_found(item_id, "el compromiso")
    if "status" in fields:
        validate_follow_up_item_status(fields["status"])
    if "commitment" in fields and not (fields["commitment"] or "").strip():
        raise InvalidRecordError("El compromiso no puede ir vacío")
    sets = ", ".join(f"{k} = %s" for k in fields)
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    f"UPDATE follow_up_item SET {sets}{', ' if sets else ''}updated_at = now() "
                    f"WHERE id = %s AND tenant_id = %s RETURNING {_ITEM_COLUMNS}",
                    (*fields.values(), item_id, tenant_id),
                )
                row = cur.fetchone()
    if row is None:
        raise FollowUpNotFoundError(f"No existe el compromiso {item_id} para esta junta")
    return _item_row(row)


def review_follow_up_milestone(
    conn: psycopg.Connection,
    tenant_id: str,
    cycle_id: str,
    milestone_code: str,
    reviewed_on: date,
    reviewed_by: str,
    summary: str | None = None,
) -> dict:
    """Registra (o corrige) la revision de un momento del seguimiento."""
    pack_id = _cycle_pack(conn, tenant_id, cycle_id)
    _assert_milestone(conn, pack_id, milestone_code)
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO follow_up_review (tenant_id, cycle_id, pack_id, milestone_code, reviewed_on, reviewed_by, summary) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s) ON CONFLICT (cycle_id, milestone_code) DO UPDATE SET "
                    "reviewed_on = EXCLUDED.reviewed_on, reviewed_by = EXCLUDED.reviewed_by, summary = EXCLUDED.summary",
                    (tenant_id, cycle_id, pack_id, milestone_code, reviewed_on, reviewed_by, (summary or "").strip() or None),
                )
    return {"cycle_id": cycle_id, "milestone_code": milestone_code, "reviewed_on": reviewed_on.isoformat(),
            "reviewed_by": reviewed_by, "summary": (summary or "").strip() or None}
