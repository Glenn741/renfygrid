"""T-10 Consolidado de observaciones para mejora (Track D, D12.2, 0043).
Guia 7 de Municipios Azules: "reune observaciones territoriales y permite
priorizar mejoras de contenido, metodologia, lenguaje o formato" de las
guias. Lo usa el programa o la agrupacion que facilita.

Ademas de lo que anota quien facilita, propone como observacion las guias
que quedaron en el rango mas bajo de un cuestionario con analisis (la CAP):
"Si una guia muestra bajo avance en sus tres items, revise claridad del
lenguaje, pertinencia del ejemplo, tiempo, dinamica, formato y dificultad
tecnica" (T-05). El rango y el nombre de cada grupo salen del paquete.
"""

from __future__ import annotations

import sys
import uuid
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))

import psycopg  # noqa: E402

from catalog_service import number_separators  # noqa: E402
from pack_engine import InvalidRecordError, format_number  # noqa: E402
from pack_service import active_pack_ids, list_checklist_templates, questionnaire_report  # noqa: E402
from renmeter_common.db import tenant_scope  # noqa: E402

PRIORITIES = ("high", "medium", "low")
STATUSES = ("open", "in_review", "incorporated", "discarded")
FIELDS = ("stage_code", "source_code", "finding", "proposed_change", "priority", "reviewer", "status", "community")


class ObservationNotFoundError(LookupError):
    """Observacion, guia o fuente inexistente para esta organizacion."""


def _clean(v: Any) -> Any:
    return (v.strip() or None) if isinstance(v, str) else v


def _catalog(conn: psycopg.Connection, tenant_id: str) -> dict:
    packs = active_pack_ids(conn, tenant_id)
    with conn.cursor() as cur:
        cur.execute("SELECT pack_id, code, title FROM process_stage WHERE pack_id = ANY(%s) ORDER BY pack_id, sort_order", (packs,))
        stages = [{"pack_id": r[0], "code": r[1], "title": r[2]} for r in cur.fetchall()]
        cur.execute("SELECT pack_id, code, label FROM observation_source WHERE pack_id = ANY(%s) ORDER BY pack_id, sort_order", (packs,))
        sources = [{"pack_id": r[0], "code": r[1], "label": r[2]} for r in cur.fetchall()]
    return {"stages": stages, "sources": sources}


def _row(r: tuple) -> dict:
    return {"observation_id": str(r[0]), "pack_id": r[1], "stage_code": r[2], "source_code": r[3], "finding": r[4],
            "proposed_change": r[5], "priority": r[6], "reviewer": r[7], "status": r[8], "community": r[9],
            "created_by": r[10], "created_at": r[11].isoformat(), "updated_at": r[12].isoformat()}


_SELECT = ("SELECT id, pack_id, stage_code, source_code, finding, proposed_change, priority, reviewer, status, community, "
           "created_by, created_at, updated_at FROM program_observation ")


def _suggestions(conn: psycopg.Connection, tenant_id: str, stage_codes: set[str], existing: list[dict]) -> list[dict]:
    """Guias en el rango mas bajo del ultimo momento de un cuestionario con
    analisis y rangos, que aun no tienen una observacion de esa fuente."""
    taken = {(o["stage_code"], o["source_code"]) for o in existing if o["status"] != "discarded"}
    sep = number_separators(conn, tenant_id)
    out = []
    for t in list_checklist_templates(conn, tenant_id):
        spec = t.get("analysis") or {}
        if t["kind"] != "questionnaire" or not spec.get("levels"):
            continue
        lowest = sorted(spec["levels"], key=lambda b: b["min_pct"])[0]["label"]
        report = questionnaire_report(conn, tenant_id, t["id"])
        # El ultimo momento con respuestas (la CAP final, o la inicial si
        # todavia no hay final).
        last = next((m["code"] for m in reversed(spec["compare"]) if report["participants"].get(m["code"])), None)
        if last is None:
            continue
        for g in report["groupings"]:
            for row in g["rows"]:
                cell = row["moments"].get(last) or {}
                if row["code"] in stage_codes and cell.get("level") == lowest and (row["code"], "cap") not in taken:
                    out.append({"stage_code": row["code"], "source_code": "cap",
                                "finding": f"{t['title']}: {row['label']} quedó en {format_number(cell['pct'], sep)} % ({lowest}) en "
                                           f"{next(m['label'] for m in spec['compare'] if m['code'] == last)} (n={cell['n']}).",
                                "hint": spec.get("note")})
    return out


def list_observations(conn: psycopg.Connection, tenant_id: str) -> dict:
    cat = _catalog(conn, tenant_id)
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(_SELECT + "WHERE tenant_id = %s ORDER BY CASE status WHEN 'open' THEN 0 WHEN 'in_review' THEN 1 ELSE 2 END, "
                            "CASE priority WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END, created_at", (tenant_id,))
                rows = [_row(r) for r in cur.fetchall()]
    return {**cat, "observations": rows,
            "suggestions": _suggestions(conn, tenant_id, {s["code"] for s in cat["stages"]}, rows),
            "summary": {"total": len(rows), **{s: sum(1 for r in rows if r["status"] == s) for s in STATUSES}}}


def _validate(conn: psycopg.Connection, tenant_id: str, fields: dict, creating: bool) -> str | None:
    if creating:
        for k in ("stage_code", "source_code", "finding", "priority"):
            if not fields.get(k):
                raise InvalidRecordError(f"Falta {k}")
    if "finding" in fields and not fields["finding"]:
        raise InvalidRecordError("Describa el hallazgo")
    if fields.get("priority") is not None and fields["priority"] not in PRIORITIES:
        raise InvalidRecordError(f"Prioridad inválida: {fields['priority']!r}")
    if fields.get("status") is not None and fields["status"] not in STATUSES:
        raise InvalidRecordError(f"Estado inválido: {fields['status']!r}")
    cat = _catalog(conn, tenant_id)
    pack = None
    if fields.get("stage_code"):
        st = next((s for s in cat["stages"] if s["code"] == fields["stage_code"]), None)
        if st is None:
            raise ObservationNotFoundError(f"No existe la guía {fields['stage_code']!r}")
        pack = st["pack_id"]
    if fields.get("source_code") and not any(s["code"] == fields["source_code"] and (pack is None or s["pack_id"] == pack)
                                             for s in cat["sources"]):
        raise ObservationNotFoundError(f"No existe la fuente {fields['source_code']!r}")
    return pack


def create_observation(conn: psycopg.Connection, tenant_id: str, actor: str, **fields: Any) -> dict:
    fields = {k: _clean(v) for k, v in fields.items() if k in FIELDS and k != "status"}
    pack = _validate(conn, tenant_id, fields, True)
    cols = [k for k in FIELDS if fields.get(k) is not None]
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(f"INSERT INTO program_observation (tenant_id, pack_id, created_by, {', '.join(cols)}) "
                            f"VALUES (%s, %s, %s, {', '.join(['%s'] * len(cols))}) RETURNING id",
                            (tenant_id, pack, actor, *[fields[k] for k in cols]))
                new_id = cur.fetchone()[0]
                cur.execute(_SELECT + "WHERE id = %s", (new_id,))
                return _row(cur.fetchone())


def update_observation(conn: psycopg.Connection, tenant_id: str, observation_id: str, **fields: Any) -> dict:
    try:
        uuid.UUID(str(observation_id))
    except ValueError:
        raise ObservationNotFoundError(f"No existe la observación {observation_id!r}") from None
    fields = {k: _clean(v) for k, v in fields.items() if k in FIELDS and k not in ("stage_code", "source_code")}
    _validate(conn, tenant_id, fields, False)
    if "priority" in fields and fields["priority"] is None:
        raise InvalidRecordError("La prioridad es obligatoria")
    if "status" in fields and fields["status"] is None:
        raise InvalidRecordError("El estado es obligatorio")
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                if fields:
                    sets = ", ".join(f"{k} = %s" for k in fields)
                    cur.execute(f"UPDATE program_observation SET {sets}, updated_at = now() WHERE id = %s AND tenant_id = %s",
                                (*fields.values(), observation_id, tenant_id))
                cur.execute(_SELECT + "WHERE id = %s AND tenant_id = %s", (observation_id, tenant_id))
                row = cur.fetchone()
    if row is None:
        raise ObservationNotFoundError(f"No existe la observación {observation_id}")
    return _row(row)
