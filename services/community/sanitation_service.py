"""Saneamiento de la junta (Track D, D6, migracion 0039). Guia 3 de
Municipios Azules, secciones 3.7-3.8, Actividad participativa 5, ficha 7F.

- Componentes de saneamiento (catalogo `component_type` con service
  'sanitation') con su ultima intervencion y, en los que acumulan lodos
  (fosa, planta), el estado del retiro frente al plazo del paquete.
- Registro 7F: ordenes del CMMS completadas sobre componentes de
  saneamiento, con quien retiro los residuos, el destino seguro y los lodos;
  la directiva verifica el destino.
- Descargas productivas con seguimiento y sus analisis (DBO/DQO).
"""

from __future__ import annotations

import sys
import uuid
from datetime import date
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))

import psycopg  # noqa: E402

from pack_engine import InvalidRecordError, bod_cod_ratio, sludge_status  # noqa: E402
from pack_service import active_pack_ids  # noqa: E402
from renmeter_common.db import tenant_scope  # noqa: E402

DISCHARGE_STATUSES = ("identified", "agreement", "controlled", "closed")


class SanitationNotFoundError(LookupError):
    """Descarga, orden o actividad inexistente para esta junta."""


def _check_uuid(value: str | None, what: str) -> None:
    if value is None:
        return
    try:
        uuid.UUID(str(value))
    except ValueError:
        raise SanitationNotFoundError(f"No existe {what} {value!r}") from None


def _clean(v: Any) -> Any:
    return (v.strip() or None) if isinstance(v, str) else v


def discharge_activities(conn: psycopg.Connection, tenant_id: str) -> list[dict]:
    with conn.cursor() as cur:
        cur.execute("SELECT pack_id, code, label FROM discharge_activity WHERE pack_id = ANY(%s) ORDER BY pack_id, sort_order",
                    (active_pack_ids(conn, tenant_id),))
        return [{"pack_id": r[0], "code": r[1], "label": r[2]} for r in cur.fetchall()]


def sanitation_overview(conn: psycopg.Connection, tenant_id: str, today: date) -> dict:
    with conn.cursor() as cur:
        cur.execute("SELECT value_days, source FROM program_rule WHERE code = 'sludge_extraction_max_days' AND pack_id = ANY(%s) "
                    "ORDER BY pack_id LIMIT 1", (active_pack_ids(conn, tenant_id),))
        rule = cur.fetchone()
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT a.id, a.type, t.label, t.accumulates_sludge, a.status, a.attributes->>'name', "
                    "(SELECT max(o.closed_at) FROM maintenance_order o WHERE o.asset_id = a.id AND o.status = 'completed'), "
                    "(SELECT max(o.closed_at) FROM maintenance_order o WHERE o.asset_id = a.id AND o.status = 'completed' "
                    "   AND o.sludge_volume_m3 IS NOT NULL) "
                    "FROM network_asset a JOIN component_type t ON t.code = a.type "
                    "WHERE a.tenant_id = %s AND t.service = 'sanitation' ORDER BY t.stage_order NULLS LAST, t.label",
                    (tenant_id,),
                )
                assets = cur.fetchall()
                cur.execute(
                    "SELECT o.id, o.asset_id, t.label, o.type, o.closed_at, o.reason, o.responsible, o.waste_handler, "
                    "o.waste_destination, o.sludge_volume_m3, o.destination_verified_by, o.destination_verified_at, o.pending_notes "
                    "FROM maintenance_order o JOIN network_asset a ON a.id = o.asset_id JOIN component_type t ON t.code = a.type "
                    "WHERE o.tenant_id = %s AND t.service = 'sanitation' AND o.status = 'completed' ORDER BY o.closed_at DESC LIMIT 100",
                    (tenant_id,),
                )
                register = cur.fetchall()
    comps = []
    for aid, atype, label, sludge, status, name, last_any, last_sludge in assets:
        st = sludge_status(last_sludge.date() if last_sludge else None, rule[0] if rule else None, today) if sludge else None
        comps.append({"asset_id": str(aid), "type": atype, "type_label": label, "name": name, "status": status,
                      "accumulates_sludge": sludge, "last_intervention_at": last_any.isoformat() if last_any else None,
                      "last_sludge_extraction_at": last_sludge.isoformat() if last_sludge else None, "sludge": st})
    entries = [{
        "order_id": str(r[0]), "asset_id": str(r[1]), "component": r[2], "type": r[3], "closed_at": r[4].isoformat() if r[4] else None,
        "activity": r[5], "responsible": r[6], "waste_handler": r[7], "waste_destination": r[8],
        "sludge_volume_m3": float(r[9]) if r[9] is not None else None, "verified_by": r[10],
        "verified_at": r[11].isoformat() if r[11] else None, "pending_notes": r[12],
        "needs_verification": bool(r[8]) and r[10] is None,
    } for r in register]
    return {
        "components": comps, "register_7f": entries,
        "sludge_rule": {"max_days": rule[0], "source": rule[1]} if rule else None,
        "summary": {
            "sludge_overdue": sum(1 for c in comps if c["sludge"] and c["sludge"]["status"] in ("overdue", "never")),
            "pending_verification": sum(1 for e in entries if e["needs_verification"]),
        },
        "discharges": list_discharges(conn, tenant_id),
        "activities": discharge_activities(conn, tenant_id),
    }


def verify_destination(conn: psycopg.Connection, tenant_id: str, order_id: str, actor: str) -> dict:
    """La directiva verifica el destino seguro de una intervencion 7F."""
    _check_uuid(order_id, "la orden")
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT o.status, o.waste_destination, t.service FROM maintenance_order o JOIN network_asset a ON a.id = o.asset_id "
                    "JOIN component_type t ON t.code = a.type WHERE o.id = %s AND o.tenant_id = %s",
                    (order_id, tenant_id),
                )
                row = cur.fetchone()
                if row is None or row[2] != "sanitation":
                    raise SanitationNotFoundError(f"No existe una intervención de saneamiento {order_id} en esta junta")
                if row[0] != "completed" or not row[1]:
                    raise InvalidRecordError("Solo se verifica una intervención completada con destino registrado")
                cur.execute("UPDATE maintenance_order SET destination_verified_by = %s, destination_verified_at = now() WHERE id = %s",
                            (actor, order_id))
    return {"order_id": order_id, "verified_by": actor}


def _discharge_row(r: tuple) -> dict:
    return {"discharge_id": str(r[0]), "activity_code": r[1], "activity_label": r[2], "name": r[3], "owner": r[4],
            "location_text": r[5], "asset_id": str(r[6]) if r[6] else None, "problem": r[7], "status": r[8],
            "agreement": r[9], "created_at": r[10].isoformat()}


def list_discharges(conn: psycopg.Connection, tenant_id: str) -> list[dict]:
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT d.id, d.activity_code, a.label, d.name, d.owner, d.location_text, d.asset_id, d.problem, d.status, "
                    "d.agreement, d.created_at FROM productive_discharge d "
                    "JOIN discharge_activity a ON a.pack_id = d.pack_id AND a.code = d.activity_code "
                    "WHERE d.tenant_id = %s ORDER BY d.status = 'closed', d.created_at DESC", (tenant_id,))
                rows = [_discharge_row(r) for r in cur.fetchall()]
                cur.execute("SELECT discharge_id, noted_at, note, new_status, noted_by FROM productive_discharge_followup "
                            "WHERE tenant_id = %s ORDER BY noted_at DESC", (tenant_id,))
                follow = cur.fetchall()
                cur.execute(
                    "SELECT s.discharge_id, s.id, s.sampled_at, s.laboratory, "
                    "max(r.value) FILTER (WHERE r.parameter_code = 'bod5'), max(r.value) FILTER (WHERE r.parameter_code = 'cod') "
                    "FROM lab_sample s LEFT JOIN lab_result r ON r.sample_id = s.id "
                    "WHERE s.tenant_id = %s AND s.discharge_id IS NOT NULL GROUP BY s.id ORDER BY s.sampled_at DESC", (tenant_id,))
                samples = cur.fetchall()
    for d in rows:
        d["followups"] = [{"noted_at": f[1].isoformat(), "note": f[2], "new_status": f[3], "noted_by": f[4]}
                          for f in follow if str(f[0]) == d["discharge_id"]]
        d["samples"] = [{"sample_id": str(s[1]), "sampled_at": s[2].isoformat(), "laboratory": s[3],
                         "bod5": float(s[4]) if s[4] is not None else None, "cod": float(s[5]) if s[5] is not None else None,
                         "bod_cod_ratio": bod_cod_ratio(float(s[4]) if s[4] is not None else None,
                                                        float(s[5]) if s[5] is not None else None)}
                        for s in samples if str(s[0]) == d["discharge_id"]]
    return rows


def create_discharge(conn: psycopg.Connection, tenant_id: str, actor: str, activity_code: str, name: str,
                     owner: str | None = None, location_text: str | None = None, asset_id: str | None = None,
                     problem: str | None = None) -> dict:
    acts = {a["code"]: a for a in discharge_activities(conn, tenant_id)}
    if activity_code not in acts:
        raise SanitationNotFoundError(f"Actividad desconocida: {activity_code!r}")
    name = _clean(name)
    if not name:
        raise InvalidRecordError("La descarga necesita un nombre (p. ej. el negocio)")
    _check_uuid(asset_id, "el componente")
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                if asset_id:
                    cur.execute("SELECT 1 FROM network_asset WHERE id = %s AND tenant_id = %s", (asset_id, tenant_id))
                    if cur.fetchone() is None:
                        raise SanitationNotFoundError(f"No existe el componente {asset_id}")
                cur.execute(
                    "INSERT INTO productive_discharge (tenant_id, pack_id, activity_code, name, owner, location_text, asset_id, problem, "
                    "created_by) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id",
                    (tenant_id, acts[activity_code]["pack_id"], activity_code, name, _clean(owner), _clean(location_text), asset_id,
                     _clean(problem), actor),
                )
                did = str(cur.fetchone()[0])
    return next(d for d in list_discharges(conn, tenant_id) if d["discharge_id"] == did)


def add_discharge_followup(conn: psycopg.Connection, tenant_id: str, discharge_id: str, actor: str, note: str,
                           new_status: str | None = None, agreement: str | None = None) -> dict:
    _check_uuid(discharge_id, "la descarga")
    note = _clean(note)
    if not note:
        raise InvalidRecordError("El seguimiento necesita una nota")
    if new_status is not None and new_status not in DISCHARGE_STATUSES:
        raise InvalidRecordError(f"Estado inválido: {new_status!r} (válidos: {list(DISCHARGE_STATUSES)})")
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute("SELECT 1 FROM productive_discharge WHERE id = %s AND tenant_id = %s", (discharge_id, tenant_id))
                if cur.fetchone() is None:
                    raise SanitationNotFoundError(f"No existe la descarga {discharge_id}")
                cur.execute("INSERT INTO productive_discharge_followup (tenant_id, discharge_id, note, new_status, noted_by) "
                            "VALUES (%s, %s, %s, %s, %s)", (tenant_id, discharge_id, note, new_status, actor))
                sets, params = [], []
                if new_status:
                    sets.append("status = %s")
                    params.append(new_status)
                if _clean(agreement):
                    sets.append("agreement = %s")
                    params.append(_clean(agreement))
                if sets:
                    cur.execute(f"UPDATE productive_discharge SET {', '.join(sets)} WHERE id = %s", (*params, discharge_id))
    return next(d for d in list_discharges(conn, tenant_id) if d["discharge_id"] == discharge_id)
