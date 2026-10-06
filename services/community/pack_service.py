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
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))

import psycopg  # noqa: E402
from psycopg.types.json import Json  # noqa: E402

from pack_engine import (  # noqa: E402
    checklist_status,
    evaluate_bands,
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
            "SELECT id, pack_id, kind, title, purpose, scale, items, stage_code, frequency_days FROM checklist_template "
            "WHERE pack_id = ANY(%s) ORDER BY id",
            (packs,),
        )
        rows = cur.fetchall()
    return [
        {"id": r[0], "pack_id": r[1], "kind": r[2], "title": r[3], "purpose": r[4], "scale": r[5], "items": r[6],
         "stage_code": r[7], "frequency_days": r[8]}
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
) -> dict:
    """Guarda una aplicacion completa de la lista y crea, en la misma
    transaccion, un hallazgo por cada respuesta que la escala marca como
    hallazgo. `answers`: [{item_key, answer_code, observation?, action?,
    responsible?, due_date?, asset_id?}]."""
    template = _template(conn, tenant_id, template_id)
    validate_answers(template, answers)
    pending_findings = findings_from_answers(template, answers)
    asset_by_item = {a["item_key"]: a.get("asset_id") for a in answers}
    _assert_assets_belong(conn, tenant_id, {a for a in asset_by_item.values() if a})

    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO checklist_run (tenant_id, template_id, performed_by, notes) "
                    "VALUES (%s, %s, %s, %s) RETURNING id, performed_at",
                    (tenant_id, template_id, performed_by, notes),
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
        "score": maturity_score(template, answers), "findings_created": finding_ids,
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
                    "coalesce(jsonb_agg(jsonb_build_object('answer_code', a.answer_code)) "
                    "         FILTER (WHERE a.item_key IS NOT NULL), '[]'::jsonb), "
                    "(SELECT count(*) FROM finding f WHERE f.tenant_id = r.tenant_id AND f.source_ref LIKE r.id::text || ':%%') "
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
            "findings_count": r[6],
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
            "SELECT pack_id, code, sort_order, title, source_ref, purpose, products FROM process_stage "
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
    for pack_id, code, order, title, source_ref, purpose, products in stage_rows:
        lists = [describe(t) for t in templates if t["pack_id"] == pack_id and t["stage_code"] == code]
        staged.update(item["template_id"] for item in lists)
        stages.append({
            "pack_id": pack_id, "code": code, "order": order, "title": title, "source_ref": source_ref,
            "purpose": purpose, "products": products, "lists": lists, "summary": stage_summary(lists),
        })
    other = [describe(t) for t in templates if t["id"] not in staged]
    return {"stages": stages, "other_lists": other}


def get_checklist_run(conn: psycopg.Connection, tenant_id: str, run_id: str) -> dict:
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT template_id, performed_at, performed_by, notes FROM checklist_run "
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
    scale = {s["code"]: s for s in template["scale"]}
    by_key = {r[0]: r for r in answer_rows}
    answers = []
    for item in template["items"]:
        r = by_key.get(item["key"])
        if r is None:
            continue
        answers.append({
            "item_key": item["key"], "text": item["text"], "answer_code": r[1],
            "answer_label": scale[r[1]]["label"], "observation": r[2], "action": r[3],
            "responsible": r[4], "due_date": r[5].isoformat() if r[5] else None,
        })
    return {
        "run_id": run_id, "template_id": run[0], "title": template["title"], "kind": template["kind"],
        "performed_at": run[1].isoformat(), "performed_by": run[2], "notes": run[3],
        "answers": answers,
        "score": maturity_score(template, [{"answer_code": a["answer_code"]} for a in answers]),
    }


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
