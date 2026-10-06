"""Plan de emergencia de la junta (Track D, D5, migracion 0037). Guia 3 de
Municipios Azules, seccion 3.11 y Actividad participativa 6.

- Plan: los tipos del catalogo del paquete (6 en Municipios Azules) con lo
  que la junta ajusto (responsable y primera accion, mensaje a la comunidad,
  apoyo externo, recursos) y emergencias propias. Lo no ajustado se muestra
  con el texto del catalogo.
- Contactos institucionales de la junta (la guia no trae telefonos).
- Activacion manual o automatica (regla del paquete: E. coli presente ->
  contaminacion). Una emergencia del mismo tipo ya activa no se duplica: el
  nuevo disparo se anota en la activa.
- Revision del plan con el plazo del paquete (antes de lluvias, una vez al
  ano).
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

from pack_engine import InvalidRecordError, checklist_status  # noqa: E402
from pack_service import active_pack_ids  # noqa: E402
from renmeter_common.db import tenant_scope  # noqa: E402

PLAN_FIELDS = ("responsible", "first_action", "community_message", "external_support", "resources", "active")


class EmergencyNotFoundError(LookupError):
    """Tipo, entrada del plan, contacto o activacion inexistente para la junta."""


def _check_uuid(value: str | None, what: str) -> None:
    if value is None:
        return
    try:
        uuid.UUID(str(value))
    except ValueError:
        raise EmergencyNotFoundError(f"No existe {what} {value!r}") from None


def _clean(v: Any) -> Any:
    return (v.strip() or None) if isinstance(v, str) else v


def _catalog(conn: psycopg.Connection, tenant_id: str) -> list[dict]:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT pack_id, code, label, signals, first_action, notify, example_responsible, example_message, example_support "
            "FROM emergency_type WHERE pack_id = ANY(%s) ORDER BY pack_id, sort_order",
            (active_pack_ids(conn, tenant_id),),
        )
        return [{"pack_id": r[0], "code": r[1], "label": r[2], "signals": r[3], "first_action": r[4], "notify": r[5],
                 "example_responsible": r[6], "example_message": r[7], "example_support": r[8]} for r in cur.fetchall()]


def emergency_plan(conn: psycopg.Connection, tenant_id: str, now: datetime) -> dict:
    catalog = _catalog(conn, tenant_id)
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id, pack_id, type_code, custom_label, responsible, first_action, community_message, external_support, "
                    "resources, active, updated_at, updated_by FROM emergency_plan_entry WHERE tenant_id = %s ORDER BY custom_label",
                    (tenant_id,),
                )
                rows = cur.fetchall()
                cur.execute("SELECT id, institution, person, phone, notes FROM emergency_contact WHERE tenant_id = %s "
                            "ORDER BY institution, person", (tenant_id,))
                contacts = [{"contact_id": str(r[0]), "institution": r[1], "person": r[2], "phone": r[3], "notes": r[4]}
                            for r in cur.fetchall()]
                cur.execute("SELECT reviewed_on, reviewed_by, notes FROM emergency_plan_review WHERE tenant_id = %s "
                            "ORDER BY reviewed_on DESC, created_at DESC LIMIT 1", (tenant_id,))
                review = cur.fetchone()
    own = {(r[1], r[2]): r for r in rows if r[2]}
    entries = []
    for t in catalog:
        r = own.get((t["pack_id"], t["code"]))
        entries.append({
            "entry_id": str(r[0]) if r else None, "pack_id": t["pack_id"], "type_code": t["code"], "label": t["label"],
            "signals": t["signals"], "notify": t["notify"], "customized": r is not None,
            "responsible": (r[4] if r else None) or t["example_responsible"],
            "first_action": (r[5] if r else None) or t["first_action"],
            "community_message": (r[6] if r else None) or t["example_message"],
            "external_support": (r[7] if r else None) or t["example_support"] or t["notify"],
            "resources": r[8] if r else None, "active": r[9] if r else True,
            "updated_at": r[10].isoformat() if r else None, "updated_by": r[11] if r else None,
        })
    for r in rows:
        if r[3]:
            entries.append({
                "entry_id": str(r[0]), "pack_id": None, "type_code": None, "label": r[3], "signals": None, "notify": None,
                "customized": True, "responsible": r[4], "first_action": r[5], "community_message": r[6],
                "external_support": r[7], "resources": r[8], "active": r[9], "updated_at": r[10].isoformat(), "updated_by": r[11],
            })
    with conn.cursor() as cur:
        cur.execute("SELECT value_days, source FROM program_rule WHERE code = 'emergency_plan_review_days' AND pack_id = ANY(%s) "
                    "ORDER BY pack_id LIMIT 1", (active_pack_ids(conn, tenant_id),))
        rule = cur.fetchone()
    review_at = datetime.combine(review[0], datetime.min.time(), tzinfo=now.tzinfo) if review else None
    st = checklist_status(rule[0], review_at, now) if rule else None
    return {
        "entries": entries, "contacts": contacts, "active": list_activations(conn, tenant_id, only_active=True),
        "review": {"last_reviewed_on": review[0].isoformat() if review else None, "reviewed_by": review[1] if review else None,
                   "notes": review[2] if review else None, "period_days": rule[0] if rule else None,
                   "source": rule[1] if rule else None, "status": st["status"] if st else None,
                   "next_due_at": st["next_due_at"].isoformat() if st and st["next_due_at"] else None},
    }


def save_plan_entry(
    conn: psycopg.Connection, tenant_id: str, actor: str, type_code: str | None = None, custom_label: str | None = None,
    **fields: Any,
) -> dict:
    """Ajusta un tipo del catalogo (`type_code`) o crea/ajusta una emergencia
    propia (`custom_label`)."""
    unknown = set(fields) - set(PLAN_FIELDS)
    if unknown:
        raise InvalidRecordError(f"Campos no editables: {sorted(unknown)}")
    custom_label = _clean(custom_label)
    if (type_code is None) == (custom_label is None):
        raise InvalidRecordError("Indique un tipo del catálogo o el nombre de una emergencia propia (uno de los dos)")
    pack_id = None
    if type_code:
        match = [t for t in _catalog(conn, tenant_id) if t["code"] == type_code]
        if not match:
            raise EmergencyNotFoundError(f"Tipo de emergencia desconocido: {type_code!r}")
        pack_id = match[0]["pack_id"]
    values = {k: _clean(v) for k, v in fields.items()}
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                if type_code:
                    cur.execute("SELECT id FROM emergency_plan_entry WHERE tenant_id = %s AND pack_id = %s AND type_code = %s",
                                (tenant_id, pack_id, type_code))
                else:
                    cur.execute("SELECT id FROM emergency_plan_entry WHERE tenant_id = %s AND custom_label = %s",
                                (tenant_id, custom_label))
                row = cur.fetchone()
                if row:
                    sets = ", ".join(f"{k} = %s" for k in values)
                    cur.execute(f"UPDATE emergency_plan_entry SET {sets}{', ' if sets else ''}updated_at = now(), updated_by = %s "
                                "WHERE id = %s", (*values.values(), actor, row[0]))
                else:
                    cols = ["tenant_id", "pack_id", "type_code", "custom_label", "updated_by", *values]
                    cur.execute(f"INSERT INTO emergency_plan_entry ({', '.join(cols)}) VALUES ({', '.join(['%s'] * len(cols))})",
                                (tenant_id, pack_id, type_code, custom_label, actor, *values.values()))
    return emergency_plan(conn, tenant_id, datetime.now().astimezone())


def add_contact(conn: psycopg.Connection, tenant_id: str, institution: str, phone: str, person: str | None = None,
                notes: str | None = None) -> dict:
    institution, phone = _clean(institution), _clean(phone)
    if not institution or not phone:
        raise InvalidRecordError("El contacto necesita institución y teléfono")
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute("INSERT INTO emergency_contact (tenant_id, institution, person, phone, notes) VALUES (%s, %s, %s, %s, %s) "
                            "RETURNING id", (tenant_id, institution, _clean(person), phone, _clean(notes)))
                return {"contact_id": str(cur.fetchone()[0]), "institution": institution, "person": _clean(person),
                        "phone": phone, "notes": _clean(notes)}


def delete_contact(conn: psycopg.Connection, tenant_id: str, contact_id: str) -> None:
    _check_uuid(contact_id, "el contacto")
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute("DELETE FROM emergency_contact WHERE id = %s AND tenant_id = %s", (contact_id, tenant_id))
                if cur.rowcount == 0:
                    raise EmergencyNotFoundError(f"No existe el contacto {contact_id} para esta junta")


_ACT_COLUMNS = ("id, pack_id, type_code, plan_entry_id, label, trigger, trigger_ref, activated_at, activated_by, notes, status, "
                "closed_at, closed_by, closing_notes")


def _act_row(r: tuple) -> dict:
    return {"activation_id": str(r[0]), "pack_id": r[1], "type_code": r[2], "plan_entry_id": str(r[3]) if r[3] else None,
            "label": r[4], "trigger": r[5], "trigger_ref": r[6], "activated_at": r[7].isoformat(), "activated_by": r[8],
            "notes": r[9], "status": r[10], "closed_at": r[11].isoformat() if r[11] else None, "closed_by": r[12],
            "closing_notes": r[13]}


def list_activations(conn: psycopg.Connection, tenant_id: str, only_active: bool = False, limit: int = 50) -> list[dict]:
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(f"SELECT {_ACT_COLUMNS} FROM emergency_activation WHERE tenant_id = %s "
                            f"{'AND status = %s ' if only_active else ''}ORDER BY activated_at DESC LIMIT %s",
                            (tenant_id, "active", limit) if only_active else (tenant_id, limit))
                return [_act_row(r) for r in cur.fetchall()]


def activate_emergency(
    conn: psycopg.Connection, tenant_id: str, actor: str, type_code: str | None = None, plan_entry_id: str | None = None,
    trigger: str = "manual", trigger_ref: str | None = None, notes: str | None = None,
) -> dict:
    """Activa una emergencia del plan. Si ya hay una activa del mismo tipo (o
    de la misma emergencia propia) devuelve esa, con el nuevo disparo anotado
    (`duplicate`)."""
    if (type_code is None) == (plan_entry_id is None):
        raise InvalidRecordError("Indique el tipo de emergencia o la entrada propia del plan (uno de los dos)")
    _check_uuid(plan_entry_id, "la entrada del plan")
    label, pack_id = None, None
    if type_code:
        match = [t for t in _catalog(conn, tenant_id) if t["code"] == type_code]
        if not match:
            raise EmergencyNotFoundError(f"Tipo de emergencia desconocido: {type_code!r}")
        label, pack_id = match[0]["label"], match[0]["pack_id"]
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                if plan_entry_id:
                    cur.execute("SELECT custom_label, pack_id, type_code FROM emergency_plan_entry WHERE id = %s AND tenant_id = %s",
                                (plan_entry_id, tenant_id))
                    row = cur.fetchone()
                    if row is None:
                        raise EmergencyNotFoundError(f"No existe la entrada {plan_entry_id} del plan")
                    label = row[0] or label
                    cur.execute(f"SELECT {_ACT_COLUMNS} FROM emergency_activation WHERE tenant_id = %s AND status = 'active' "
                                "AND plan_entry_id = %s LIMIT 1", (tenant_id, plan_entry_id))
                else:
                    cur.execute(f"SELECT {_ACT_COLUMNS} FROM emergency_activation WHERE tenant_id = %s AND status = 'active' "
                                "AND pack_id = %s AND type_code = %s LIMIT 1", (tenant_id, pack_id, type_code))
                existing = cur.fetchone()
                if existing:
                    note = f"{datetime.now().astimezone().isoformat(timespec='minutes')} · nuevo disparo ({trigger}" + \
                           (f": {trigger_ref}" if trigger_ref else "") + ")" + (f" · {notes}" if notes else "")
                    cur.execute("UPDATE emergency_activation SET notes = concat_ws(E'\\n', notes, %s::text) WHERE id = %s", (note, existing[0]))
                    cur.execute(f"SELECT {_ACT_COLUMNS} FROM emergency_activation WHERE id = %s", (existing[0],))
                    return {**_act_row(cur.fetchone()), "duplicate": True}
                cur.execute(
                    "INSERT INTO emergency_activation (tenant_id, pack_id, type_code, plan_entry_id, label, trigger, trigger_ref, "
                    f"activated_by, notes) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING {_ACT_COLUMNS}",
                    (tenant_id, pack_id, type_code, plan_entry_id, label, trigger, trigger_ref, actor, _clean(notes)),
                )
                return {**_act_row(cur.fetchone()), "duplicate": False}


def close_activation(conn: psycopg.Connection, tenant_id: str, activation_id: str, actor: str, notes: str | None = None) -> dict:
    _check_uuid(activation_id, "la activación")
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE emergency_activation SET status = 'closed', closed_at = now(), closed_by = %s, closing_notes = %s "
                    f"WHERE id = %s AND tenant_id = %s AND status = 'active' RETURNING {_ACT_COLUMNS}",
                    (actor, _clean(notes), activation_id, tenant_id),
                )
                row = cur.fetchone()
    if row is None:
        raise EmergencyNotFoundError(f"No hay una emergencia activa {activation_id} en esta junta")
    return _act_row(row)


def auto_activate_from_results(conn: psycopg.Connection, tenant_id: str, results: list[dict], trigger_ref: str,
                               actor: str) -> list[dict]:
    """Aplica las reglas del paquete (parametro + severidad -> tipo) a los
    resultados recien guardados. `results`: [{parameter_code, severity}]."""
    hits = [(r["parameter_code"], r["severity"]) for r in results if r.get("severity") in ("alert", "critical")]
    if not hits:
        return []
    with conn.cursor() as cur:
        cur.execute("SELECT parameter_code, severity, emergency_type_code FROM emergency_auto_trigger WHERE pack_id = ANY(%s)",
                    (active_pack_ids(conn, tenant_id),))
        rules = {(r[0], r[1]): r[2] for r in cur.fetchall()}
    out = []
    for param, severity in hits:
        code = rules.get((param, severity))
        if code:
            out.append(activate_emergency(conn, tenant_id, actor, type_code=code, trigger="auto", trigger_ref=trigger_ref,
                                          notes=f"Activada automáticamente: {param} con severidad {severity}."))
    return out


def review_emergency_plan(conn: psycopg.Connection, tenant_id: str, reviewed_on: date, actor: str, notes: str | None = None) -> None:
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            conn.execute("INSERT INTO emergency_plan_review (tenant_id, reviewed_on, reviewed_by, notes) VALUES (%s, %s, %s, %s)",
                         (tenant_id, reviewed_on, actor, _clean(notes)))
