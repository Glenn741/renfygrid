"""Plan minimo de O&M, ficha 7G.2 y tablero 7H (Track D, D7, migracion
0040). Guia 3 de Municipios Azules, seccion 4 y fichas 7G.2 y 7H.

- Plan minimo: las filas son catalogo del paquete; la junta escribe su
  decision, responsable y plazo. Cada fila muestra la evidencia viva que la
  respalda (bitacora, puntos de cloro, preventivos, lodos, bodega, ...).
- Ficha 7G.2: lo que la evidencia propone llevar al Plan de Mejora
  (hallazgos abiertos, fosas sin retiro, descargas sin controlar) con la
  evidencia ya citada; la junta completa accion, apoyo, costo y plazo.
- Tablero 7H: cada producto de la guia con lo que el sistema tiene
  registrado y su ultimo estado verificado (lista `products`).
"""

from __future__ import annotations

import sys
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))

import psycopg  # noqa: E402

from pack_engine import (  # noqa: E402
    InvalidRecordError,
    improvement_candidates,
    minimum_plan_view,
    products_board,
)
from pack_service import active_pack_ids, list_checklist_templates  # noqa: E402
from renmeter_common.db import tenant_scope  # noqa: E402
from sanitation_service import sanitation_overview  # noqa: E402
from warehouse_service import list_items  # noqa: E402

PRIORITIES = ("high", "medium", "low")
SUPPORT_LEVELS = ("community", "local_government", "specialized")
INPUT_FIELDS = ("problem", "evidence", "proposed_action", "community_action", "support_required", "support_level",
                "cost_estimate", "cost_note", "term", "priority")


class ImprovementNotFoundError(LookupError):
    """Fila, origen o lista inexistente para esta junta."""


class ImprovementConflictError(RuntimeError):
    """Esa evidencia ya esta en la ficha 7G.2."""


def _check_uuid(value: str | None, what: str) -> None:
    if value is None:
        return
    try:
        uuid.UUID(str(value))
    except ValueError:
        raise ImprovementNotFoundError(f"No existe {what} {value!r}") from None


def _clean(v: Any) -> Any:
    return (v.strip() or None) if isinstance(v, str) else v


def _num(v: Any) -> str:
    return f"{float(v):g}"


# ── Plan minimo ───────────────────────────────────────────────────────

def _suggestions(conn: psycopg.Connection, tenant_id: str, today: date, day_start: datetime,
                 tz_name: str) -> dict[str, list[str]]:
    packs = active_pack_ids(conn, tenant_id)
    week_start = day_start - timedelta(days=6)
    month_end = day_start + timedelta(days=31)
    with conn.cursor() as cur:
        cur.execute("SELECT label FROM operation_moment WHERE pack_id = ANY(%s) ORDER BY pack_id, sort_order", (packs,))
        moments = [r[0] for r in cur.fetchall()]
        cur.execute("SELECT label FROM emergency_type WHERE pack_id = ANY(%s) ORDER BY pack_id, sort_order", (packs,))
        emergency_labels = [r[0] for r in cur.fetchall()]
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute("SELECT count(DISTINCT (logged_at AT TIME ZONE %s)::date) FROM operation_log_entry "
                            "WHERE tenant_id = %s AND logged_at >= %s", (tz_name, tenant_id, week_start))
                log_days = cur.fetchone()[0]
                cur.execute("SELECT k.label, p.name FROM sampling_point p JOIN sampling_point_kind k ON k.code = p.kind_code "
                            "WHERE p.tenant_id = %s AND p.active ORDER BY k.sort_order, p.name", (tenant_id,))
                points = cur.fetchall()
                cur.execute("SELECT f.description FROM finding f WHERE f.tenant_id = %s AND f.source_kind = 'reading' "
                            "AND f.status <> 'closed' ORDER BY f.created_at", (tenant_id,))
                reading_findings = [r[0] for r in cur.fetchall()]
                cur.execute("SELECT p.title, p.next_due_at, a.attributes->>'name', t.label FROM maintenance_pm_plan p "
                            "JOIN network_asset a ON a.id = p.asset_id JOIN component_type t ON t.code = a.type "
                            "WHERE p.tenant_id = %s AND p.is_active AND p.next_due_at < %s ORDER BY p.next_due_at",
                            (tenant_id, month_end))
                pm_due = cur.fetchall()
                cur.execute("SELECT count(*) FROM maintenance_order WHERE tenant_id = %s AND type = 'preventive' "
                            "AND status NOT IN ('completed', 'cancelled')", (tenant_id,))
                open_preventive = cur.fetchone()[0]
                # Hallazgos abiertos de saneamiento: sobre un componente de
                # saneamiento, o de un item de lista marcado como tal.
                cur.execute("SELECT f.description FROM finding f WHERE f.tenant_id = %s AND f.status <> 'closed' AND ("
                            " EXISTS (SELECT 1 FROM network_asset a JOIN component_type c ON c.code = a.type "
                            "         WHERE a.id = f.asset_id AND c.service = 'sanitation') "
                            " OR (f.source_kind = 'checklist' AND EXISTS ("
                            "   SELECT 1 FROM checklist_run r JOIN checklist_template t ON t.id = r.template_id, "
                            "   jsonb_array_elements(t.items) i WHERE r.id::text = split_part(f.source_ref, ':', 1) "
                            "   AND i->>'key' = split_part(f.source_ref, ':', 2) AND i->>'component_service' = 'sanitation'))"
                            ") ORDER BY f.created_at", (tenant_id,))
                sanitation_findings = [r[0] for r in cur.fetchall()]
                cur.execute("SELECT coalesce(e.custom_label, t.label), count(*) FROM emergency_activation a "
                            "JOIN emergency_plan_entry e ON e.id = a.plan_entry_id "
                            "LEFT JOIN emergency_type t ON t.pack_id = e.pack_id AND t.code = e.type_code "
                            "WHERE a.tenant_id = %s GROUP BY 1 ORDER BY 2 DESC, 1", (tenant_id,))
                activations = cur.fetchall()
                cur.execute("SELECT description, support_level FROM finding WHERE tenant_id = %s AND status <> 'closed' "
                            "AND support_level IN ('local_government', 'specialized') ORDER BY created_at", (tenant_id,))
                support = cur.fetchall()
                cur.execute("SELECT problem FROM improvement_input WHERE tenant_id = %s "
                            "ORDER BY CASE priority WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END, created_at", (tenant_id,))
                inputs = [r[0] for r in cur.fetchall()]
    sanitation = sanitation_overview(conn, tenant_id, today)
    items = list_items(conn, tenant_id, today)

    out: dict[str, list[str]] = {}
    out["daily_routine"] = ([f"Rutina del paquete: {', '.join(moments)}."] if moments else []) + [
        f"Bitácora 7C con registros en {log_days} de los últimos 7 días."]
    out["chlorine_points"] = [f"{kind}: {name}" for kind, name in points] or ["No hay puntos de medición configurados."]
    out["chlorine_points"] += [f"Sin cerrar: {d}" for d in reading_findings]
    out["monthly_maintenance"] = [
        f"{title or label}{f' ({name})' if name else ''}: {due.date().isoformat()}" for title, due, name, label in pm_due
    ] + ([f"{open_preventive} órdenes preventivas abiertas."] if open_preventive else [])
    out["sanitation_priority"] = [
        c["type_label"] + (f" ({c['name']})" if c["name"] else "") + ": "
        + ("sin retiro de lodos registrado" if c["sludge"]["status"] == "never" else "retiro de lodos vencido")
        for c in sanitation["components"] if c["sludge"] and c["sludge"]["status"] in ("never", "overdue")
    ] + [f"Descarga: {d['name']} ({d['activity_label']})" for d in sanitation["discharges"]
         if d["status"] in ("identified", "agreement")] + sanitation_findings
    out["warehouse_ppe"] = [
        f"{i['name']}: {_num(i['stock'])} de mínimo {_num(i['min_stock'])}" for i in items if i["below_min"]
    ] + [f"{i['name']}: lote vence {l['expires_on']}" for i in items for l in i["expiring"]]
    out["likely_emergency"] = ([f"Activada antes: {label} ({n})" for label, n in activations]
                               or ([f"Tipos del plan: {', '.join(emergency_labels)}."] if emergency_labels else []))
    out["technical_support"] = [d for d, _ in support]
    out["improvement_inputs"] = inputs
    return out


def minimum_plan(conn: psycopg.Connection, tenant_id: str, today: date, day_start: datetime, tz_name: str) -> dict:
    packs = active_pack_ids(conn, tenant_id)
    with conn.cursor() as cur:
        cur.execute("SELECT pack_id, code, sort_order, component, guidance, example_decision, example_responsible, example_term, "
                    "suggestion_source FROM minimum_plan_row WHERE pack_id = ANY(%s) ORDER BY pack_id, sort_order", (packs,))
        cols = ("pack_id", "code", "sort_order", "component", "guidance", "example_decision", "example_responsible",
                "example_term", "suggestion_source")
        rows = [dict(zip(cols, r)) for r in cur.fetchall()]
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute("SELECT pack_id, row_code, decision, responsible, term, due_date, updated_at, updated_by "
                            "FROM minimum_plan_entry WHERE tenant_id = %s", (tenant_id,))
                entries = {(r[0], r[1]): {"decision": r[2], "responsible": r[3], "term": r[4],
                                          "due_date": r[5].isoformat() if r[5] else None,
                                          "updated_at": r[6].isoformat(), "updated_by": r[7]} for r in cur.fetchall()}
    return minimum_plan_view(rows, entries, _suggestions(conn, tenant_id, today, day_start, tz_name))


def save_minimum_plan_entry(conn: psycopg.Connection, tenant_id: str, pack_id: str, row_code: str, actor: str,
                            decision: str, responsible: str | None = None, term: str | None = None,
                            due_date: date | None = None) -> dict:
    decision = _clean(decision)
    if not decision:
        raise InvalidRecordError("Escriba la decisión concreta de la junta")
    if pack_id not in active_pack_ids(conn, tenant_id):
        raise ImprovementNotFoundError(f"El paquete {pack_id!r} no está adoptado")
    with conn.cursor() as cur:
        cur.execute("SELECT 1 FROM minimum_plan_row WHERE pack_id = %s AND code = %s", (pack_id, row_code))
        if cur.fetchone() is None:
            raise ImprovementNotFoundError(f"No existe la fila {row_code!r} del plan mínimo")
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO minimum_plan_entry (tenant_id, pack_id, row_code, decision, responsible, term, due_date, updated_by) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s) ON CONFLICT (tenant_id, pack_id, row_code) DO UPDATE SET "
                    "decision = EXCLUDED.decision, responsible = EXCLUDED.responsible, term = EXCLUDED.term, "
                    "due_date = EXCLUDED.due_date, updated_by = EXCLUDED.updated_by, updated_at = now() RETURNING updated_at",
                    (tenant_id, pack_id, row_code, decision, _clean(responsible), _clean(term), due_date, actor),
                )
                updated_at = cur.fetchone()[0]
    return {"pack_id": pack_id, "row_code": row_code, "decision": decision, "responsible": _clean(responsible),
            "term": _clean(term), "due_date": due_date.isoformat() if due_date else None,
            "updated_at": updated_at.isoformat(), "updated_by": actor}


# ── Ficha 7G.2 ────────────────────────────────────────────────────────

def _labels(conn: psycopg.Connection, tenant_id: str) -> tuple[dict[str, str], dict[str, str | None]]:
    """Como se cita cada origen y a que etapa de la ruta pertenece."""
    with conn.cursor() as cur:
        cur.execute("SELECT DISTINCT ON (source_kind) source_kind, label, stage_code FROM evidence_label WHERE pack_id = ANY(%s) "
                    "ORDER BY source_kind, pack_id", (active_pack_ids(conn, tenant_id),))
        rows = cur.fetchall()
    return {r[0]: r[1] for r in rows}, {r[0]: r[2] for r in rows}


def _finding_candidates(conn: psycopg.Connection, tenant_id: str, labels: dict[str, str],
                        stages: dict[str, str | None]) -> list[dict]:
    templates = {t["id"]: t for t in list_checklist_templates(conn, tenant_id)}
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute("SELECT id, source_kind, source_ref, description, priority, support_level, status, created_at, "
                            "location_text FROM finding WHERE tenant_id = %s AND status <> 'closed'", (tenant_id,))
                findings = cur.fetchall()
                cur.execute("SELECT r.finding_id, r.value, p.unit, p.label, sp.name, r.measured_at FROM field_reading r "
                            "JOIN parameter p ON p.code = r.parameter_code LEFT JOIN sampling_point sp ON sp.id = r.sampling_point_id "
                            "WHERE r.tenant_id = %s AND r.finding_id IS NOT NULL "
                            "UNION ALL SELECT r.finding_id, r.value, p.unit, p.label, sp.name, s.sampled_at FROM lab_result r "
                            "JOIN lab_sample s ON s.id = r.sample_id JOIN parameter p ON p.code = r.parameter_code "
                            "LEFT JOIN sampling_point sp ON sp.id = s.sampling_point_id "
                            "WHERE r.tenant_id = %s AND r.finding_id IS NOT NULL ORDER BY 6", (tenant_id, tenant_id))
                values: dict[str, list] = {}
                for fid, v, unit, plabel, point, _ in cur.fetchall():
                    values.setdefault(str(fid), []).append((float(v), unit, plabel, point))
                cur.execute("SELECT a.run_id::text || ':' || a.item_key, r.template_id, a.answer_code, r.performed_at "
                            "FROM checklist_answer a JOIN checklist_run r ON r.id = a.run_id WHERE a.tenant_id = %s", (tenant_id,))
                answers = {r[0]: r[1:] for r in cur.fetchall()}
    out = []
    for fid, kind, ref, desc, prio, support, status, created, location in findings:
        fid = str(fid)
        stage = None
        if kind == "reading":
            vals = values.get(fid, [])
            src = "lab" if (ref or "").startswith("lab:") else "reading"
            stage = stages.get(src)
            if vals:
                unit, plabel, point = vals[0][1], vals[0][2], vals[0][3]
                evidence = (f"{len(vals)} {'medición' if len(vals) == 1 else 'mediciones'} de {plabel}"
                            f"{f' en {point}' if point else ''}: {'; '.join(_num(v[0]) for v in vals)} {unit or ''}".rstrip()
                            + f". {labels.get(src, '')}".rstrip())
            else:
                evidence = labels.get(src)
        elif kind == "checklist":
            src = "checklist"
            a = answers.get(ref or "")
            if a:
                t = templates.get(a[0])
                answer_label = next((s["label"] for s in (t["scale"] if t else []) if s["code"] == a[1]), a[1])
                stage = t["stage_code"] if t else None
                evidence = f"{t['title'] if t else a[0]}: respuesta «{answer_label}» ({a[2].date().isoformat()})."
            else:
                evidence = labels.get("checklist")
        else:
            src = kind
            evidence = labels.get(kind)
            stage = stages.get(kind)
        out.append({"finding_id": fid, "source_kind": src, "stage_code": stage, "problem": desc, "evidence": evidence, "priority": prio,
                    "support_level": support, "status": status, "since": created.isoformat(), "location_text": location})
    return out


def _derived_candidates(conn: psycopg.Connection, tenant_id: str, today: date, labels: dict[str, str],
                        stages: dict[str, str | None]) -> list[dict]:
    s = sanitation_overview(conn, tenant_id, today)
    out = []
    for c in s["components"]:
        st = c["sludge"]
        if st and st["status"] in ("never", "overdue"):
            what = "sin retiro de lodos registrado" if st["status"] == "never" else f"retiro de lodos vencido desde {st['due_on']}"
            rule = f" (plazo: {s['sludge_rule']['max_days']} días)" if s["sludge_rule"] else ""
            out.append({"source_ref": f"sludge:{c['asset_id']}", "source_kind": "sludge", "stage_code": stages.get("sludge"),
                        "finding_id": None,
                        "problem": c["type_label"] + (f" ({c['name']})" if c["name"] else "") + f": {what}",
                        "evidence": f"{labels.get('sludge', '')}{rule}.".lstrip(), "priority": None, "support_level": None,
                        "since": c["last_sludge_extraction_at"], "location_text": None})
    for d in s["discharges"]:
        if d["status"] in ("identified", "agreement"):
            out.append({"source_ref": f"discharge:{d['discharge_id']}", "source_kind": "discharge",
                        "stage_code": stages.get("discharge"), "finding_id": None,
                        "problem": f"{d['name']} ({d['activity_label']}): {d['problem'] or 'descarga productiva sin controlar'}",
                        "evidence": f"{labels.get('discharge', '')}; estado: {d['status']}"
                                    + "".join(f"; DBO {_num(m['bod5'])} / DQO {_num(m['cod'])} mg/L"
                                              for m in d["samples"] if m["bod5"] is not None and m["cod"] is not None),
                        "priority": None, "support_level": None, "since": d["created_at"], "location_text": d["location_text"]})
    return out


def _input_row(r: tuple) -> dict:
    return {
        "input_id": str(r[0]), "source_kind": r[1], "source_ref": r[2], "finding_id": str(r[3]) if r[3] else None,
        "problem": r[4], "evidence": r[5], "proposed_action": r[6], "community_action": r[7], "support_required": r[8],
        "support_level": r[9], "cost_estimate": float(r[10]) if r[10] is not None else None, "cost_note": r[11], "term": r[12],
        "priority": r[13], "created_by": r[14], "created_at": r[15].isoformat(), "updated_at": r[16].isoformat(),
    }


_INPUT_SELECT = ("SELECT id, source_kind, source_ref, finding_id, problem, evidence, proposed_action, community_action, "
                 "support_required, support_level, cost_estimate, cost_note, term, priority, created_by, created_at, updated_at "
                 "FROM improvement_input ")


def improvement_overview(conn: psycopg.Connection, tenant_id: str, today: date) -> dict:
    labels, stages = _labels(conn, tenant_id)
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(_INPUT_SELECT + "WHERE tenant_id = %s "
                            "ORDER BY CASE priority WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END, created_at", (tenant_id,))
                inputs = [_input_row(r) for r in cur.fetchall()]
    taken = {i["source_ref"] for i in inputs if i["source_ref"]}
    candidates = improvement_candidates(_finding_candidates(conn, tenant_id, labels, stages),
                                        _derived_candidates(conn, tenant_id, today, labels, stages), taken)
    total = sum(i["cost_estimate"] or 0 for i in inputs)
    return {"inputs": inputs, "candidates": candidates,
            "summary": {"inputs": len(inputs), "candidates": len(candidates), "cost_estimate_total": total,
                        "to_quote": sum(1 for i in inputs if i["cost_estimate"] is None)}}


def _validate_input(fields: dict) -> None:
    if "problem" in fields and not _clean(fields["problem"]):
        raise InvalidRecordError("Describa el problema priorizado")
    if fields.get("priority") is not None and fields["priority"] not in PRIORITIES:
        raise InvalidRecordError(f"Prioridad inválida: {fields['priority']!r}")
    if fields.get("support_level") is not None and fields["support_level"] not in SUPPORT_LEVELS:
        raise InvalidRecordError(f"Nivel de apoyo inválido: {fields['support_level']!r}")
    if fields.get("cost_estimate") is not None and float(fields["cost_estimate"]) < 0:
        raise InvalidRecordError("El costo estimado no puede ser negativo")


def create_improvement_input(conn: psycopg.Connection, tenant_id: str, actor: str, today: date,
                             source_ref: str | None = None, **fields: Any) -> dict:
    """Lleva una fila a la 7G.2. Con `source_ref` (id de hallazgo,
    `sludge:<activo>` o `discharge:<id>`) el origen y la evidencia salen del
    sistema; lo que envie la junta prevalece. Sin `source_ref` es manual."""
    fields = {k: _clean(v) for k, v in fields.items() if k in INPUT_FIELDS}
    source_kind, finding_id = "manual", None
    if source_ref:
        overview = improvement_overview(conn, tenant_id, today)
        if source_ref in {i["source_ref"] for i in overview["inputs"]}:
            raise ImprovementConflictError("Esa evidencia ya está en la ficha 7G.2")
        cand = next((c for c in overview["candidates"] if c["source_ref"] == source_ref), None)
        if cand is None:
            raise ImprovementNotFoundError(f"No hay evidencia abierta {source_ref!r} para esta junta")
        source_kind, finding_id = cand["source_kind"], cand["finding_id"]
        for k in ("problem", "evidence", "priority", "support_level"):
            if fields.get(k) is None and cand.get(k) is not None:
                fields[k] = cand[k]
    if fields.get("priority") is None:
        raise InvalidRecordError("Indique la prioridad (alta, media o baja)")
    fields.setdefault("problem", None)
    _validate_input(fields)
    cols = [k for k in INPUT_FIELDS if fields.get(k) is not None]
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    f"INSERT INTO improvement_input (tenant_id, source_kind, source_ref, finding_id, created_by, {', '.join(cols)}) "
                    f"VALUES (%s, %s, %s, %s, %s, {', '.join(['%s'] * len(cols))}) RETURNING id",
                    (tenant_id, source_kind, source_ref, finding_id, actor, *[fields[k] for k in cols]),
                )
                new_id = cur.fetchone()[0]
                if finding_id:
                    cur.execute("UPDATE finding SET to_improvement_plan = true WHERE id = %s AND tenant_id = %s",
                                (finding_id, tenant_id))
                cur.execute(_INPUT_SELECT + "WHERE id = %s", (new_id,))
                return _input_row(cur.fetchone())


def update_improvement_input(conn: psycopg.Connection, tenant_id: str, input_id: str, **fields: Any) -> dict:
    _check_uuid(input_id, "la fila")
    fields = {k: _clean(v) for k, v in fields.items() if k in INPUT_FIELDS}
    _validate_input(fields)
    if "priority" in fields and fields["priority"] is None:
        raise InvalidRecordError("La prioridad es obligatoria")
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                if fields:
                    sets = ", ".join(f"{k} = %s" for k in fields)
                    cur.execute(f"UPDATE improvement_input SET {sets}, updated_at = now() WHERE id = %s AND tenant_id = %s",
                                (*fields.values(), input_id, tenant_id))
                cur.execute(_INPUT_SELECT + "WHERE id = %s AND tenant_id = %s", (input_id, tenant_id))
                row = cur.fetchone()
    if row is None:
        raise ImprovementNotFoundError(f"No existe la fila {input_id} de la ficha 7G.2")
    return _input_row(row)


def delete_improvement_input(conn: psycopg.Connection, tenant_id: str, input_id: str) -> None:
    """Quita la fila; el hallazgo de origen deja de estar marcado para el
    Plan de Mejora y vuelve a aparecer como candidato."""
    _check_uuid(input_id, "la fila")
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute("DELETE FROM improvement_input WHERE id = %s AND tenant_id = %s RETURNING finding_id",
                            (input_id, tenant_id))
                row = cur.fetchone()
                if row is None:
                    raise ImprovementNotFoundError(f"No existe la fila {input_id} de la ficha 7G.2")
                if row[0]:
                    cur.execute("UPDATE finding SET to_improvement_plan = false WHERE id = %s AND tenant_id = %s", (row[0], tenant_id))


# ── Tablero de productos (7H) ─────────────────────────────────────────

_EVIDENCE_SQL = {
    "assets_mapped": ("SELECT count(*), NULL::timestamptz FROM network_asset WHERE tenant_id = %(t)s AND geometry IS NOT NULL", False),
    "checklist_runs": ("SELECT count(*), max(performed_at) FROM checklist_run WHERE tenant_id = %(t)s AND template_id = %(ref)s", True),
    "treatment_stages": ("SELECT count(*), NULL::timestamptz FROM network_asset a JOIN component_type c ON c.code = a.type "
                         "WHERE a.tenant_id = %(t)s AND c.is_treatment_stage", False),
    "field_readings": ("SELECT count(*), max(measured_at) FROM field_reading WHERE tenant_id = %(t)s AND parameter_code = %(ref)s", True),
    "operation_log": ("SELECT count(*), max(logged_at) FROM operation_log_entry WHERE tenant_id = %(t)s", False),
    "pm_plans": ("SELECT count(*), NULL::timestamptz FROM maintenance_pm_plan WHERE tenant_id = %(t)s AND is_active", False),
    "sanitation_register": ("SELECT count(*), max(o.closed_at) FROM maintenance_order o JOIN network_asset a ON a.id = o.asset_id "
                            "JOIN component_type c ON c.code = a.type WHERE o.tenant_id = %(t)s AND c.service = 'sanitation' "
                            "AND o.status = 'completed'", False),
    "emergency_plan": ("SELECT count(*), max(updated_at) FROM emergency_plan_entry WHERE tenant_id = %(t)s", False),
    "minimum_plan": ("SELECT count(*), max(updated_at) FROM minimum_plan_entry WHERE tenant_id = %(t)s", False),
    "improvement_inputs": ("SELECT count(*), max(updated_at) FROM improvement_input WHERE tenant_id = %(t)s", False),
    "lab_plan": ("SELECT count(*), max(created_at) FROM lab_plan_item WHERE tenant_id = %(t)s", False),
}


def product_board(conn: psycopg.Connection, tenant_id: str, template_id: str) -> dict:
    template = next((t for t in list_checklist_templates(conn, tenant_id) if t["id"] == template_id), None)
    if template is None or template["kind"] != "products":
        raise ImprovementNotFoundError(f"La lista de productos {template_id!r} no existe o su paquete no está adoptado")
    evidence: dict[str, dict] = {}
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                for it in template["items"]:
                    spec = it.get("evidence")
                    if not spec or spec.get("kind") not in _EVIDENCE_SQL:
                        continue
                    sql, needs_ref = _EVIDENCE_SQL[spec["kind"]]
                    if needs_ref and not spec.get("ref"):
                        continue
                    cur.execute(sql, {"t": tenant_id, "ref": spec.get("ref")})
                    n, last = cur.fetchone()
                    evidence[it["key"]] = {"count": n, "last_at": last.isoformat() if last else None}
                cur.execute("SELECT id, performed_at, performed_by FROM checklist_run WHERE tenant_id = %s AND template_id = %s "
                            "ORDER BY performed_at DESC LIMIT 1", (tenant_id, template_id))
                run = cur.fetchone()
                answers = {}
                if run:
                    cur.execute("SELECT item_key, answer_code, observation FROM checklist_answer WHERE run_id = %s", (run[0],))
                    answers = {r[0]: {"answer_code": r[1], "observation": r[2]} for r in cur.fetchall()}
    board = products_board(template["items"], answers, evidence)
    return {"template_id": template_id, "title": template["title"], "purpose": template["purpose"],
            "stage_code": template["stage_code"],
            "last_run": {"run_id": str(run[0]), "performed_at": run[1].isoformat(), "performed_by": run[2]} if run else None,
            **board}
