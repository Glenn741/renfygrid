"""Agrupacion de juntas y su tablero (Track D, D12.1, migracion 0042).

Una asociacion, ACC o programa es una organizacion de tipo 'group'. Invita a
juntas; cada junta acepta (o no) y decide que indicadores comparte, y puede
cambiarlos o salir cuando quiera. El tablero calcula cada indicador
compartido leyendo la junta con SU alcance (RLS de la junta), nunca con un
acceso general: lo que no se compartio no se calcula ni se devuelve.
"""

from __future__ import annotations

import sys
import uuid
from datetime import date, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))

import psycopg  # noqa: E402

from calendar_service import annual_calendar  # noqa: E402
from emergency_service import list_activations  # noqa: E402
from improvement_service import product_board  # noqa: E402
from pack_engine import InvalidRecordError, group_rollup, maturity_progress  # noqa: E402
from pack_service import list_checklist_runs, list_checklist_templates  # noqa: E402
from renmeter_common.db import tenant_scope  # noqa: E402
from sanitation_service import sanitation_overview  # noqa: E402

KINDS = ("provider", "group")
CLOSED = ("declined", "left", "removed")


class GroupNotFoundError(LookupError):
    """Organizacion o membresia inexistente para quien pregunta."""


class GroupConflictError(RuntimeError):
    """La operacion no corresponde al estado actual de la membresia."""


def _uuid(value: str, what: str) -> str:
    try:
        return str(uuid.UUID(str(value)))
    except ValueError:
        raise GroupNotFoundError(f"No existe {what} {value!r}") from None


def _tenant(conn: psycopg.Connection, tenant_id: str) -> dict:
    with conn.cursor() as cur:
        cur.execute("SELECT id, name, kind, config->>'timezone' FROM tenant WHERE id = %s AND is_active", (tenant_id,))
        r = cur.fetchone()
    if r is None:
        raise GroupNotFoundError("Organización inexistente")
    return {"tenant_id": str(r[0]), "name": r[1], "kind": r[2], "timezone": r[3]}


def indicator_catalog(conn: psycopg.Connection) -> list[dict]:
    with conn.cursor() as cur:
        cur.execute("SELECT code, label, description, params, available, unavailable_note FROM group_indicator ORDER BY sort_order")
        return [{"code": r[0], "label": r[1], "description": r[2], "params": r[3], "available": r[4], "unavailable_note": r[5]}
                for r in cur.fetchall()]


def set_organization_kind(conn: psycopg.Connection, tenant_id: str, kind: str) -> dict:
    if kind not in KINDS:
        raise InvalidRecordError(f"Tipo de organización inválido: {kind!r}")
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute("SELECT count(*) FROM group_membership WHERE group_tenant_id = %s AND status IN ('invited', 'accepted')",
                            (tenant_id,))
                if kind == "provider" and cur.fetchone()[0]:
                    raise GroupConflictError("La agrupación todavía tiene organizaciones invitadas o activas; retírelas primero")
                cur.execute("SELECT count(*) FROM group_membership WHERE member_tenant_id = %s AND status IN ('invited', 'accepted')",
                            (tenant_id,))
                if kind == "group" and cur.fetchone()[0]:
                    raise GroupConflictError("Esta organización es miembro de una agrupación; una agrupación no puede ser miembro")
                cur.execute("UPDATE tenant SET kind = %s WHERE id = %s", (kind, tenant_id))
    return _tenant(conn, tenant_id)


def _membership_rows(conn: psycopg.Connection, tenant_id: str, as_group: bool) -> list[dict]:
    side, other = ("group_tenant_id", "member_tenant_id") if as_group else ("member_tenant_id", "group_tenant_id")
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT m.{other}, t.name, m.status, m.shared, m.invited_by, m.invited_at, m.decided_by, m.decided_at "
                    f"FROM group_membership m JOIN tenant t ON t.id = m.{other} WHERE m.{side} = %s ORDER BY t.name",
                    (tenant_id,),
                )
                rows = cur.fetchall()
    key = "member_tenant_id" if as_group else "group_tenant_id"
    return [{key: str(r[0]), "name": r[1], "status": r[2], "shared": list(r[3]), "invited_by": r[4],
             "invited_at": r[5].isoformat(), "decided_by": r[6], "decided_at": r[7].isoformat() if r[7] else None} for r in rows]


def memberships(conn: psycopg.Connection, tenant_id: str) -> dict:
    t = _tenant(conn, tenant_id)
    return {
        "organization": {k: t[k] for k in ("tenant_id", "name", "kind")},
        "members": _membership_rows(conn, tenant_id, True) if t["kind"] == "group" else [],
        "groups": _membership_rows(conn, tenant_id, False),
        "indicators": indicator_catalog(conn),
    }


def invite_member(conn: psycopg.Connection, group_id: str, member_name: str, actor: str) -> dict:
    """Invita a una junta por su nombre de organizacion (el mismo del login)."""
    if _tenant(conn, group_id)["kind"] != "group":
        raise GroupConflictError("Solo una organización de tipo agrupación puede invitar organizaciones")
    name = (member_name or "").strip()
    with conn.cursor() as cur:
        cur.execute("SELECT id, kind FROM tenant WHERE lower(name) = lower(%s) AND is_active", (name,))
        rows = cur.fetchall()
    if len(rows) != 1:
        raise GroupNotFoundError(f"No hay una organización llamada {name!r}")
    member_id, kind = str(rows[0][0]), rows[0][1]
    if member_id == group_id:
        raise GroupConflictError("La agrupación no puede invitarse a sí misma")
    if kind != "provider":
        raise GroupConflictError("Solo se invitan organizaciones prestadoras, no otra agrupación")
    with conn.transaction():
        with tenant_scope(conn, group_id):
            with conn.cursor() as cur:
                cur.execute("SELECT status FROM group_membership WHERE group_tenant_id = %s AND member_tenant_id = %s",
                            (group_id, member_id))
                row = cur.fetchone()
                if row and row[0] in ("invited", "accepted"):
                    raise GroupConflictError("Esa organización ya está invitada o es miembro")
                cur.execute(
                    "INSERT INTO group_membership (group_tenant_id, member_tenant_id, status, shared, invited_by) "
                    "VALUES (%s, %s, 'invited', '{}', %s) ON CONFLICT (group_tenant_id, member_tenant_id) DO UPDATE SET "
                    "status = 'invited', shared = '{}', invited_by = EXCLUDED.invited_by, invited_at = now(), "
                    "decided_by = NULL, decided_at = NULL",
                    (group_id, member_id, actor),
                )
    return next(m for m in _membership_rows(conn, group_id, True) if m["member_tenant_id"] == member_id)


def remove_member(conn: psycopg.Connection, group_id: str, member_id: str, actor: str) -> dict:
    member_id = _uuid(member_id, "la organización")
    with conn.transaction():
        with tenant_scope(conn, group_id):
            with conn.cursor() as cur:
                cur.execute("UPDATE group_membership SET status = 'removed', shared = '{}', decided_by = %s, decided_at = now() "
                            "WHERE group_tenant_id = %s AND member_tenant_id = %s AND status IN ('invited', 'accepted') "
                            "RETURNING 1", (actor, group_id, member_id))
                if cur.fetchone() is None:
                    raise GroupNotFoundError("Esa organización no está invitada ni es miembro de la agrupación")
    return next(m for m in _membership_rows(conn, group_id, True) if m["member_tenant_id"] == member_id)


def _validate_shared(conn: psycopg.Connection, shared: list[str]) -> list[str]:
    catalog = {i["code"]: i for i in indicator_catalog(conn)}
    out = []
    for code in shared or []:
        if code not in catalog:
            raise InvalidRecordError(f"Indicador desconocido: {code!r}")
        if not catalog[code]["available"]:
            raise InvalidRecordError(f"{catalog[code]['label']}: {catalog[code]['unavailable_note']}")
        if code not in out:
            out.append(code)
    return out


def decide_membership(conn: psycopg.Connection, member_id: str, group_id: str, actor: str, action: str,
                      shared: list[str] | None = None) -> dict:
    """La junta acepta (con los indicadores que comparte), rechaza, cambia lo
    que comparte o sale. `action`: accept, decline, share, leave."""
    group_id = _uuid(group_id, "la agrupación")
    if action not in ("accept", "decline", "share", "leave"):
        raise InvalidRecordError(f"Acción inválida: {action!r}")
    codes = _validate_shared(conn, shared or []) if action in ("accept", "share") else []
    if action in ("accept", "share") and not codes:
        raise InvalidRecordError("Elija al menos un indicador para compartir (o rechace la invitación)")
    allowed = {"accept": ("invited",), "decline": ("invited",), "share": ("accepted",), "leave": ("accepted",)}[action]
    status = {"accept": "accepted", "decline": "declined", "share": "accepted", "leave": "left"}[action]
    with conn.transaction():
        with tenant_scope(conn, member_id):
            with conn.cursor() as cur:
                cur.execute("SELECT status FROM group_membership WHERE group_tenant_id = %s AND member_tenant_id = %s FOR UPDATE",
                            (group_id, member_id))
                row = cur.fetchone()
                if row is None:
                    raise GroupNotFoundError("Su organización no tiene invitación ni membresía en esa agrupación")
                if row[0] not in allowed:
                    raise GroupConflictError(f"No se puede {'aceptar' if action == 'accept' else 'hacer eso'} en estado {row[0]!r}")
                cur.execute("UPDATE group_membership SET status = %s, shared = %s, decided_by = %s, decided_at = now() "
                            "WHERE group_tenant_id = %s AND member_tenant_id = %s", (status, codes, actor, group_id, member_id))
    return next(m for m in _membership_rows(conn, member_id, False) if m["group_tenant_id"] == group_id)


# ── Indicadores de una junta ───────────────────────────────────────────

def _member_now(tz_name: str | None) -> tuple[datetime | None, date | None]:
    if not tz_name:
        return None, None
    now = datetime.now(ZoneInfo(tz_name))
    return now, now.date()


def _indicator(conn: psycopg.Connection, member: dict, code: str, params: dict) -> Any:
    mid = member["tenant_id"]
    now, today = _member_now(member["timezone"])
    if code == "maturity":
        templates = {t["id"]: t for t in list_checklist_templates(conn, mid)}
        out = []
        for tid in params.get("template_ids", []):
            if tid in templates:
                prog = maturity_progress(list_checklist_runs(conn, mid, tid))
                if prog["runs"]:
                    out.append({"template_id": tid, "title": templates[tid]["title"], **prog})
        return out
    if code == "quality_alerts":
        with conn.transaction():
            with tenant_scope(conn, mid):
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT count(*), count(*) FILTER (WHERE EXISTS (SELECT 1 FROM field_reading r WHERE r.finding_id = f.id "
                        "AND r.severity = 'critical') OR EXISTS (SELECT 1 FROM lab_result l WHERE l.finding_id = f.id "
                        "AND l.severity = 'critical')) FROM finding f WHERE f.tenant_id = %s AND f.source_kind = 'reading' "
                        "AND f.status <> 'closed'", (mid,))
                    n, crit = cur.fetchone()
        return {"open": n, "critical": crit}
    if code == "calendar":
        if now is None:
            return {"compliance_pct": None, "note": "La organización no tiene zona horaria configurada"}
        s = annual_calendar(conn, mid, datetime(now.year, 1, 1, tzinfo=now.tzinfo), now)["summary"]
        return {"compliance_pct": s["compliance_pct"], "expected": s["expected"], "done": s["done"]}
    if code == "products":
        complete = total = 0
        for t in list_checklist_templates(conn, mid):
            if t["kind"] == "products":
                b = product_board(conn, mid, t["id"])
                complete += b["summary"]["complete"]
                total += b["summary"]["total"]
        return {"complete": complete, "total": total}
    if code == "improvement":
        with conn.transaction():
            with tenant_scope(conn, mid):
                with conn.cursor() as cur:
                    cur.execute("SELECT count(*), coalesce(sum(cost_estimate), 0), count(*) FILTER (WHERE cost_estimate IS NULL) "
                                "FROM improvement_input WHERE tenant_id = %s", (mid,))
                    n, cost, to_quote = cur.fetchone()
        return {"inputs": n, "cost_estimate_total": float(cost), "to_quote": to_quote}
    if code == "sanitation":
        if today is None:
            return None
        s = sanitation_overview(conn, mid, today)
        return {"sludge_overdue": s["summary"]["sludge_overdue"],
                "open_discharges": sum(1 for d in s["discharges"] if d["status"] in ("identified", "agreement"))}
    if code == "emergencies":
        return {"active": len(list_activations(conn, mid, only_active=True))}
    return None


def group_dashboard(conn: psycopg.Connection, group_id: str) -> dict:
    org = _tenant(conn, group_id)
    if org["kind"] != "group":
        raise GroupConflictError("Esta organización no es una agrupación")
    catalog = {i["code"]: i for i in indicator_catalog(conn)}
    members = []
    for m in _membership_rows(conn, group_id, True):
        if m["status"] != "accepted":
            continue
        member = _tenant(conn, m["member_tenant_id"])
        indicators = {code: _indicator(conn, member, code, catalog[code]["params"])
                      for code in m["shared"] if code in catalog and catalog[code]["available"]}
        members.append({"member_tenant_id": member["tenant_id"], "name": member["name"], "shared": m["shared"],
                        "since": m["decided_at"], "indicators": indicators})
    pending = [m for m in _membership_rows(conn, group_id, True) if m["status"] == "invited"]
    return {"organization": {"tenant_id": org["tenant_id"], "name": org["name"]}, "members": members,
            "pending_invitations": len(pending), "rollup": group_rollup(members), "indicators": list(catalog.values())}
