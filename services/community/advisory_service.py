"""Asesoria de la ONG a operadores de agua (Track E, E1, migracion 0047).
Ver docs/04-plan-sprints.md §12.

La ONG (organizacion de tipo 'advisor', p. ej. APT) acompana a operadores
con talleres y asesoria. Las guias son la esencia de ese apoyo:

- Cada operador asesorado es un registro de la ONG (`advised_operator`). Lo
  que el asesor levanta con el -- listas aplicadas, fichas y tablas -- queda
  en la ONG marcado con el operador (decision del usuario, 19-oct).
- Un taller reune a varios operadores; los formularios llenados en el
  quedan marcados con el taller. Las guias "vistas" con un operador son las
  de los talleres a los que asistio.
- Cuando el operador lo solicita, se crea su organizacion con esos datos
  (`transfer_operator`): las listas se vuelven a aplicar alla (y alla nacen
  sus hallazgos) y las fichas y tablas se copian con su contenido. Desde
  entonces el registro de la ONG queda de solo lectura: el operador sigue
  desde su organizacion.
- El tablero y el mapa leen la ficha que el paquete de programa declara en
  `advisory_map_layer` (que campo da la ubicacion, el tamano, el color y la
  forma); nada de eso esta escrito aqui.
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

from form_engine import field_value, guide_coverage  # noqa: E402
from form_service import entries_for, form_template, get_form, merge_record, save_form  # noqa: E402
from organization_service import (  # noqa: E402
    OrganizationConflictError,
    config_from,
    create_organization,
    require_kind,
)
from pack_engine import InvalidRecordError  # noqa: E402
from pack_service import (  # noqa: E402
    CORE_PACK,
    active_pack_ids,
    get_checklist_run,
    list_checklist_runs,
    process_route,
    submit_checklist_run,
)
from renmeter_common.db import tenant_scope  # noqa: E402

STATUSES = ("active", "transferred", "inactive")
ORIGINS = ("workshop", "direct", "import")


class AdvisoryNotFoundError(LookupError):
    """Operador, taller o asistente inexistente para esta ONG."""


class AdvisoryConflictError(RuntimeError):
    """La operacion no corresponde al estado actual (p. ej. operador ya traspasado)."""


def _require_advisor(conn: psycopg.Connection, tenant_id: str) -> None:
    try:
        require_kind(conn, tenant_id, "advisor", "Esta función es de las organizaciones que asesoran (ONG).")
    except OrganizationConflictError as exc:
        raise AdvisoryConflictError(str(exc)) from None


def _uuid(value: str, what: str) -> str:
    try:
        return str(uuid.UUID(str(value)))
    except ValueError:
        raise AdvisoryNotFoundError(f"No existe {what} {value!r}") from None


def _text(value: Any) -> str | None:
    text = str(value).strip() if value is not None else ""
    return text or None


# ── Capas del mapa (catalogo del paquete) ─────────────────────────────

def map_layers(conn: psycopg.Connection, tenant_id: str) -> dict[str, dict]:
    packs = active_pack_ids(conn, tenant_id)
    with conn.cursor() as cur:
        cur.execute("SELECT role, template_id, field_key, label FROM advisory_map_layer WHERE pack_id = ANY(%s) ORDER BY pack_id",
                    (packs,))
        rows = cur.fetchall()
    layers: dict[str, dict] = {}
    for role, template_id, field_key, label in rows:
        layers.setdefault(role, {"template_id": template_id, "field_key": field_key, "label": label})
    return layers


def _layer_options(conn: psycopg.Connection, tenant_id: str, layer: dict | None) -> list[dict]:
    if not layer:
        return []
    spec = form_template(conn, tenant_id, layer["template_id"])["form_spec"] or {}
    field = next((f for f in spec.get("fields") or [] if f["key"] == layer["field_key"]), None)
    return [{"code": o["code"], "label": o["label"]} for o in (field or {}).get("options") or []]


def _profile(layers: dict[str, dict], entries: dict[str, dict]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for role, layer in layers.items():
        entry = entries.get(layer["template_id"])
        out[role] = field_value(entry["data"], layer["field_key"]) if entry else None
    return out


# ── Operadores ────────────────────────────────────────────────────────

_OP_COLS = ("id, name, community, contact_name, contact_phone, contact_email, origin, status, notes, "
            "transferred_tenant_id, transferred_at, transferred_by, created_at, created_by")


def _op_row(r: tuple, transferred_name: str | None = None) -> dict:
    return {
        "operator_id": str(r[0]), "name": r[1], "community": r[2], "contact_name": r[3], "contact_phone": r[4],
        "contact_email": r[5], "origin": r[6], "status": r[7], "notes": r[8],
        "transferred_tenant_id": str(r[9]) if r[9] else None, "transferred_tenant_name": transferred_name,
        "transferred_at": r[10].isoformat() if r[10] else None, "transferred_by": r[11],
        "created_at": r[12].isoformat(), "created_by": r[13],
    }


def _tenant_names(conn: psycopg.Connection, ids: list[str]) -> dict[str, str]:
    if not ids:
        return {}
    with conn.cursor() as cur:
        cur.execute("SELECT id, name FROM tenant WHERE id = ANY(%s::uuid[])", (ids,))
        return {str(r[0]): r[1] for r in cur.fetchall()}


def _operator(conn: psycopg.Connection, tenant_id: str, operator_id: str) -> dict:
    operator_id = _uuid(operator_id, "el operador")
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(f"SELECT {_OP_COLS} FROM advised_operator WHERE id = %s AND tenant_id = %s", (operator_id, tenant_id))
                r = cur.fetchone()
    if r is None:
        raise AdvisoryNotFoundError(f"No existe el operador {operator_id} en esta organización")
    names = _tenant_names(conn, [str(r[9])] if r[9] else [])
    return _op_row(r, names.get(str(r[9])) if r[9] else None)


def _editable(op: dict) -> None:
    if op["status"] == "transferred":
        raise AdvisoryConflictError(
            f"Los datos de {op['name']} ya se traspasaron a su organización ({op['transferred_tenant_name'] or 'creada'}): "
            "desde ahora se actualizan allá.")
    if op["status"] == "inactive":
        raise AdvisoryConflictError(f"{op['name']} está inactivo: actívelo para registrar información.")


def _workshops_by_operator(conn: psycopg.Connection, tenant_id: str) -> dict[str, list[dict]]:
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT wo.operator_id, w.id, w.title, w.held_on, w.stage_codes FROM workshop_operator wo "
                    "JOIN workshop w ON w.id = wo.workshop_id WHERE wo.tenant_id = %s ORDER BY w.held_on",
                    (tenant_id,),
                )
                rows = cur.fetchall()
    out: dict[str, list[dict]] = {}
    for op_id, wid, title, held_on, stages in rows:
        out.setdefault(str(op_id), []).append({"workshop_id": str(wid), "title": title, "held_on": held_on.isoformat(),
                                               "stage_codes": list(stages)})
    return out


def _summary(conn: psycopg.Connection, tenant_id: str, op: dict, layers: dict, workshops: list[dict]) -> dict:
    route = process_route(conn, tenant_id, advised_operator_id=op["operator_id"])
    coverage = guide_coverage(route["stages"])
    seen = sorted({c for w in workshops for c in w["stage_codes"]})
    entries = entries_for(conn, tenant_id, op["operator_id"])
    return {**op, "coverage": coverage, "stages_in_workshops": seen, "workshops": workshops,
            "profile": _profile(layers, entries)}


def list_operators(conn: psycopg.Connection, tenant_id: str) -> list[dict]:
    _require_advisor(conn, tenant_id)
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(f"SELECT {_OP_COLS} FROM advised_operator WHERE tenant_id = %s ORDER BY lower(name)", (tenant_id,))
                rows = cur.fetchall()
    names = _tenant_names(conn, [str(r[9]) for r in rows if r[9]])
    layers = map_layers(conn, tenant_id)
    by_op = _workshops_by_operator(conn, tenant_id)
    return [_summary(conn, tenant_id, _op_row(r, names.get(str(r[9])) if r[9] else None), layers, by_op.get(str(r[0]), []))
            for r in rows]


def get_operator(conn: psycopg.Connection, tenant_id: str, operator_id: str) -> dict:
    _require_advisor(conn, tenant_id)
    op = _operator(conn, tenant_id, operator_id)
    summary = _summary(conn, tenant_id, op, map_layers(conn, tenant_id),
                       _workshops_by_operator(conn, tenant_id).get(op["operator_id"], []))
    summary["route"] = process_route(conn, tenant_id, advised_operator_id=op["operator_id"])
    return summary


def find_operator_by_name(conn: psycopg.Connection, tenant_id: str, name: str) -> dict | None:
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(f"SELECT {_OP_COLS} FROM advised_operator WHERE tenant_id = %s AND lower(btrim(name)) = lower(btrim(%s))",
                            (tenant_id, name))
                r = cur.fetchone()
    return _op_row(r) if r else None


def create_operator(
    conn: psycopg.Connection,
    tenant_id: str,
    actor: str,
    name: str,
    community: str | None = None,
    contact_name: str | None = None,
    contact_phone: str | None = None,
    contact_email: str | None = None,
    origin: str = "workshop",
    notes: str | None = None,
    workshop_id: str | None = None,
    profile: dict[str, Any] | None = None,
) -> dict:
    """Registra un operador. `profile`: campos de la ficha del mapa (p. ej.
    canton, parroquia, ubicacion, usuarios) que se guardan en esa ficha,
    asi el registro del taller ya lo pone en el mapa."""
    _require_advisor(conn, tenant_id)
    clean_name = _text(name)
    if not clean_name:
        raise InvalidRecordError("Escriba el nombre del operador (junta o sistema de agua)")
    if origin not in ORIGINS:
        raise InvalidRecordError(f"Origen inválido: {origin!r}")
    if find_operator_by_name(conn, tenant_id, clean_name):
        raise AdvisoryConflictError(f"Ya hay un operador registrado como {clean_name!r}")
    if workshop_id:
        _workshop(conn, tenant_id, workshop_id)
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO advised_operator (tenant_id, name, community, contact_name, contact_phone, contact_email, "
                    "origin, notes, created_by) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id",
                    (tenant_id, clean_name, _text(community), _text(contact_name), _text(contact_phone),
                     _text(contact_email), origin, _text(notes), actor),
                )
                operator_id = str(cur.fetchone()[0])
                if workshop_id:
                    cur.execute("INSERT INTO workshop_operator (workshop_id, operator_id, tenant_id) VALUES (%s, %s, %s)",
                                (workshop_id, operator_id, tenant_id))
            if profile:
                layer = map_layers(conn, tenant_id).get("location")
                if not layer:
                    raise InvalidRecordError("El paquete de programa no declara la ficha del operador")
                save_form(conn, tenant_id, layer["template_id"],
                          {"fields": {k: {"value": v} for k, v in profile.items() if v not in (None, "")}},
                          actor, advised_operator_id=operator_id, workshop_id=workshop_id)
    return get_operator(conn, tenant_id, operator_id)


def update_operator(conn: psycopg.Connection, tenant_id: str, operator_id: str, actor: str, **changes: Any) -> dict:
    _require_advisor(conn, tenant_id)
    op = _operator(conn, tenant_id, operator_id)
    allowed = {"name", "community", "contact_name", "contact_phone", "contact_email", "notes", "status"}
    unknown = set(changes) - allowed
    if unknown:
        raise InvalidRecordError(f"Campos que no se pueden cambiar: {sorted(unknown)}")
    sets, params = [], []
    for key, value in changes.items():
        if key == "status":
            if value not in ("active", "inactive"):
                raise InvalidRecordError("El estado solo puede ser activo o inactivo (el traspaso se hace aparte)")
            if op["status"] == "transferred":
                raise AdvisoryConflictError("El operador ya se traspasó a su organización")
        elif key == "name":
            value = _text(value)
            if not value:
                raise InvalidRecordError("El nombre no puede quedar vacío")
            other = find_operator_by_name(conn, tenant_id, value)
            if other and other["operator_id"] != op["operator_id"]:
                raise AdvisoryConflictError(f"Ya hay un operador registrado como {value!r}")
        else:
            value = _text(value)
        sets.append(f"{key} = %s")
        params.append(value)
    if sets:
        with conn.transaction():
            with tenant_scope(conn, tenant_id):
                conn.execute(f"UPDATE advised_operator SET {', '.join(sets)} WHERE id = %s AND tenant_id = %s",
                             (*params, op["operator_id"], tenant_id))
    return get_operator(conn, tenant_id, op["operator_id"])


# ── Formularios de un operador ────────────────────────────────────────

def operator_runs(conn: psycopg.Connection, tenant_id: str, operator_id: str) -> list[dict]:
    _require_advisor(conn, tenant_id)
    op = _operator(conn, tenant_id, operator_id)
    return list_checklist_runs(conn, tenant_id, advised_operator_id=op["operator_id"])


def operator_run(conn: psycopg.Connection, tenant_id: str, operator_id: str, run_id: str) -> dict:
    _require_advisor(conn, tenant_id)
    op = _operator(conn, tenant_id, operator_id)
    return get_checklist_run(conn, tenant_id, run_id, advised_operator_id=op["operator_id"])


def submit_operator_run(conn: psycopg.Connection, tenant_id: str, operator_id: str, template_id: str, answers: list[dict],
                        actor: str, notes: str | None = None, context: dict | None = None,
                        workshop_id: str | None = None) -> dict:
    _require_advisor(conn, tenant_id)
    op = _operator(conn, tenant_id, operator_id)
    _editable(op)
    if workshop_id:
        _workshop(conn, tenant_id, workshop_id)
    return submit_checklist_run(conn, tenant_id, template_id, answers, actor, notes=notes, context=context,
                                advised_operator_id=op["operator_id"], workshop_id=workshop_id)


def operator_form(conn: psycopg.Connection, tenant_id: str, operator_id: str, template_id: str) -> dict:
    _require_advisor(conn, tenant_id)
    op = _operator(conn, tenant_id, operator_id)
    return get_form(conn, tenant_id, template_id, advised_operator_id=op["operator_id"])


def save_operator_form(conn: psycopg.Connection, tenant_id: str, operator_id: str, template_id: str, data: dict,
                       actor: str, workshop_id: str | None = None, source: str = "portal") -> dict:
    _require_advisor(conn, tenant_id)
    op = _operator(conn, tenant_id, operator_id)
    _editable(op)
    if workshop_id:
        _workshop(conn, tenant_id, workshop_id)
    return save_form(conn, tenant_id, template_id, data, actor, advised_operator_id=op["operator_id"],
                     workshop_id=workshop_id, source=source)


def merge_operator_record(conn: psycopg.Connection, tenant_id: str, operator_id: str, template_id: str, data: dict,
                          actor: str, workshop_id: str | None = None, source: str = "import") -> dict:
    current = get_form(conn, tenant_id, template_id, advised_operator_id=operator_id)["data"]
    return save_operator_form(conn, tenant_id, operator_id, template_id, merge_record(current, data), actor,
                              workshop_id=workshop_id, source=source)


# ── Talleres ──────────────────────────────────────────────────────────

def _workshop(conn: psycopg.Connection, tenant_id: str, workshop_id: str) -> dict:
    workshop_id = _uuid(workshop_id, "el taller")
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute("SELECT id, title, held_on, place, stage_codes, facilitators, notes, created_at, created_by "
                            "FROM workshop WHERE id = %s AND tenant_id = %s", (workshop_id, tenant_id))
                r = cur.fetchone()
    if r is None:
        raise AdvisoryNotFoundError(f"No existe el taller {workshop_id} en esta organización")
    return {"workshop_id": str(r[0]), "title": r[1], "held_on": r[2].isoformat(), "place": r[3],
            "stage_codes": list(r[4]), "facilitators": r[5], "notes": r[6], "created_at": r[7].isoformat(),
            "created_by": r[8]}


def _stage_codes(conn: psycopg.Connection, tenant_id: str, codes: list[str]) -> list[str]:
    packs = active_pack_ids(conn, tenant_id)
    with conn.cursor() as cur:
        cur.execute("SELECT code FROM process_stage WHERE pack_id = ANY(%s) ORDER BY sort_order", (packs,))
        valid = [r[0] for r in cur.fetchall()]
    unknown = sorted(set(codes) - set(valid))
    if unknown:
        raise InvalidRecordError(f"Guías desconocidas: {unknown}")
    return [c for c in valid if c in set(codes)]


def _set_workshop_operators(conn: psycopg.Connection, tenant_id: str, workshop_id: str, operator_ids: list[str]) -> None:
    ids = {_uuid(o, "el operador") for o in operator_ids}
    for oid in ids:
        _operator(conn, tenant_id, oid)
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute("DELETE FROM workshop_operator WHERE workshop_id = %s AND tenant_id = %s AND NOT (operator_id = ANY(%s::uuid[]))",
                            (workshop_id, tenant_id, list(ids)))
                for oid in ids:
                    cur.execute("INSERT INTO workshop_operator (workshop_id, operator_id, tenant_id) VALUES (%s, %s, %s) "
                                "ON CONFLICT DO NOTHING", (workshop_id, oid, tenant_id))


def create_workshop(conn: psycopg.Connection, tenant_id: str, actor: str, title: str, held_on: date,
                    stage_codes: list[str], place: str | None = None, facilitators: str | None = None,
                    notes: str | None = None, operator_ids: list[str] | None = None) -> dict:
    _require_advisor(conn, tenant_id)
    if not _text(title):
        raise InvalidRecordError("Escriba el nombre del taller")
    stages = _stage_codes(conn, tenant_id, stage_codes or [])
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO workshop (tenant_id, title, held_on, place, stage_codes, facilitators, notes, created_by) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id",
                    (tenant_id, _text(title), held_on, _text(place), stages, _text(facilitators), _text(notes), actor),
                )
                workshop_id = str(cur.fetchone()[0])
        _set_workshop_operators(conn, tenant_id, workshop_id, operator_ids or [])
    return get_workshop(conn, tenant_id, workshop_id)


def update_workshop(conn: psycopg.Connection, tenant_id: str, workshop_id: str, **changes: Any) -> dict:
    _require_advisor(conn, tenant_id)
    w = _workshop(conn, tenant_id, workshop_id)
    operator_ids = changes.pop("operator_ids", None)
    allowed = {"title", "held_on", "place", "stage_codes", "facilitators", "notes"}
    unknown = set(changes) - allowed
    if unknown:
        raise InvalidRecordError(f"Campos que no se pueden cambiar: {sorted(unknown)}")
    sets, params = [], []
    for key, value in changes.items():
        if key == "stage_codes":
            value = _stage_codes(conn, tenant_id, value or [])
        elif key == "held_on":
            if value is None:
                raise InvalidRecordError("Indique la fecha del taller")
        else:
            value = _text(value)
            if key == "title" and not value:
                raise InvalidRecordError("El nombre del taller no puede quedar vacío")
        sets.append(f"{key} = %s")
        params.append(value)
    with conn.transaction():
        if sets:
            with tenant_scope(conn, tenant_id):
                conn.execute(f"UPDATE workshop SET {', '.join(sets)} WHERE id = %s AND tenant_id = %s",
                             (*params, w["workshop_id"], tenant_id))
        if operator_ids is not None:
            _set_workshop_operators(conn, tenant_id, w["workshop_id"], operator_ids)
    return get_workshop(conn, tenant_id, w["workshop_id"])


def get_workshop(conn: psycopg.Connection, tenant_id: str, workshop_id: str) -> dict:
    _require_advisor(conn, tenant_id)
    w = _workshop(conn, tenant_id, workshop_id)
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute("SELECT o.id, o.name FROM workshop_operator wo JOIN advised_operator o ON o.id = wo.operator_id "
                            "WHERE wo.workshop_id = %s ORDER BY lower(o.name)", (w["workshop_id"],))
                w["operators"] = [{"operator_id": str(r[0]), "name": r[1]} for r in cur.fetchall()]
                cur.execute("SELECT id, operator_id, full_name, role_label, sector, support_needs FROM workshop_attendee "
                            "WHERE workshop_id = %s ORDER BY created_at", (w["workshop_id"],))
                w["attendees"] = [{"attendee_id": str(r[0]), "operator_id": str(r[1]) if r[1] else None, "full_name": r[2],
                                   "role_label": r[3], "sector": r[4], "support_needs": r[5]} for r in cur.fetchall()]
    return w


def list_workshops(conn: psycopg.Connection, tenant_id: str) -> list[dict]:
    _require_advisor(conn, tenant_id)
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT w.id, (SELECT count(*) FROM workshop_operator wo WHERE wo.workshop_id = w.id), "
                    "(SELECT count(*) FROM workshop_attendee a WHERE a.workshop_id = w.id) "
                    "FROM workshop w WHERE w.tenant_id = %s ORDER BY w.held_on DESC, w.created_at DESC",
                    (tenant_id,),
                )
                rows = cur.fetchall()
    out = []
    for wid, n_ops, n_people in rows:
        w = _workshop(conn, tenant_id, str(wid))
        out.append({**w, "operator_count": n_ops, "attendee_count": n_people})
    return out


def add_attendee(conn: psycopg.Connection, tenant_id: str, workshop_id: str, full_name: str,
                 operator_id: str | None = None, role_label: str | None = None, sector: str | None = None,
                 support_needs: str | None = None) -> dict:
    _require_advisor(conn, tenant_id)
    w = _workshop(conn, tenant_id, workshop_id)
    if not _text(full_name):
        raise InvalidRecordError("Escriba el nombre de la persona")
    op_id = _operator(conn, tenant_id, operator_id)["operator_id"] if operator_id else None
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO workshop_attendee (tenant_id, workshop_id, operator_id, full_name, role_label, sector, support_needs) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                    (tenant_id, w["workshop_id"], op_id, _text(full_name), _text(role_label), _text(sector), _text(support_needs)),
                )
                if op_id:
                    cur.execute("INSERT INTO workshop_operator (workshop_id, operator_id, tenant_id) VALUES (%s, %s, %s) "
                                "ON CONFLICT DO NOTHING", (w["workshop_id"], op_id, tenant_id))
    return get_workshop(conn, tenant_id, w["workshop_id"])


def remove_attendee(conn: psycopg.Connection, tenant_id: str, workshop_id: str, attendee_id: str) -> dict:
    _require_advisor(conn, tenant_id)
    w = _workshop(conn, tenant_id, workshop_id)
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute("DELETE FROM workshop_attendee WHERE id = %s AND workshop_id = %s AND tenant_id = %s",
                            (_uuid(attendee_id, "la persona"), w["workshop_id"], tenant_id))
                if cur.rowcount == 0:
                    raise AdvisoryNotFoundError("Esa persona no está en la asistencia del taller")
    return get_workshop(conn, tenant_id, w["workshop_id"])


# ── Tablero y mapa ────────────────────────────────────────────────────

def dashboard(conn: psycopg.Connection, tenant_id: str) -> dict:
    """Tablero de la ONG: que operadores se han capacitado, que guias se han
    cubierto con cada uno y el mapa tematico."""
    _require_advisor(conn, tenant_id)
    operators = list_operators(conn, tenant_id)
    workshops = list_workshops(conn, tenant_id)
    packs = active_pack_ids(conn, tenant_id)
    with conn.cursor() as cur:
        cur.execute("SELECT code, title, sort_order FROM process_stage WHERE pack_id = ANY(%s) AND audience = 'operator' "
                    "ORDER BY sort_order", (packs,))
        stages = [{"code": r[0], "title": r[1], "order": r[2]} for r in cur.fetchall()]
    layers = map_layers(conn, tenant_id)
    legend = {role: {"label": layers[role]["label"], "options": _layer_options(conn, tenant_id, layers[role])}
              for role in ("color", "shape") if role in layers}
    if "size" in layers:
        legend["size"] = {"label": layers["size"]["label"]}

    features, without_location = [], []
    for op in operators:
        loc = op["profile"].get("location")
        if not loc:
            if op["status"] != "inactive":
                without_location.append({"operator_id": op["operator_id"], "name": op["name"]})
            continue
        features.append({
            "operator_id": op["operator_id"], "name": op["name"], "status": op["status"],
            "lat": loc["lat"], "lon": loc["lon"],
            "size": op["profile"].get("size"), "color": op["profile"].get("color"), "shape": op["profile"].get("shape"),
            "stages_in_workshops": op["stages_in_workshops"],
            "complete_pct": _overall_pct(op["coverage"]),
        })

    active = [op for op in operators if op["status"] != "inactive"]
    by_stage = []
    for s in stages:
        pcts = [op["coverage"].get(s["code"], {}).get("pct") for op in active]
        pcts = [p for p in pcts if p is not None]
        by_stage.append({**s, "operators_trained": sum(1 for op in active if s["code"] in op["stages_in_workshops"]),
                         "avg_complete_pct": round(sum(pcts) / len(pcts), 1) if pcts else None})
    return {
        "kpis": {
            "operators": len(active),
            "trained": sum(1 for op in active if op["workshops"]),
            "transferred": sum(1 for op in operators if op["status"] == "transferred"),
            "workshops": len(workshops),
            "attendees": sum(w["attendee_count"] for w in workshops),
            "users_covered": sum(op["profile"].get("size") or 0 for op in active),
        },
        "stages": by_stage,
        "operators": [{k: op[k] for k in ("operator_id", "name", "community", "status", "coverage", "stages_in_workshops",
                                          "workshops", "profile", "transferred_tenant_name")} for op in operators],
        "map": {"features": features, "without_location": without_location, "legend": legend, "layers": layers},
        "recent_workshops": workshops[:5],
    }


def _overall_pct(coverage: dict[str, dict]) -> float | None:
    total = sum(c["total"] for c in coverage.values())
    done = sum(c["complete"] for c in coverage.values())
    return round(100.0 * done / total, 1) if total else None


# ── Traspaso: crear la organizacion del operador con sus datos ────────

def transfer_operator(conn: psycopg.Connection, tenant_id: str, operator_id: str, actor: str, code: str,
                      admin_username: str, admin_password: str) -> dict:
    """Crea la organizacion del operador (prestador) con lo levantado por la
    ONG, en una sola transaccion. Hereda de la ONG zona horaria, sesion,
    moneda y region, y adopta sus mismos paquetes."""
    _require_advisor(conn, tenant_id)
    op = _operator(conn, tenant_id, operator_id)
    _editable(op)
    packs = [p for p in active_pack_ids(conn, tenant_id) if p != CORE_PACK]
    runs = list(reversed(list_checklist_runs(conn, tenant_id, advised_operator_id=op["operator_id"])))
    entries = entries_for(conn, tenant_id, op["operator_id"])
    with conn.transaction():
        org = create_organization(conn, code, "provider", admin_username, admin_password, actor,
                                  config=config_from(conn, tenant_id), packs=packs, display_name=op["name"])
        new_id = org["tenant_id"]
        copied_runs = findings = 0
        for r in runs:
            detail = get_checklist_run(conn, tenant_id, r["run_id"], advised_operator_id=op["operator_id"])
            answers = [{k: a[k] for k in ("item_key", "answer_code", "observation", "action", "responsible", "due_date")}
                       for a in detail["answers"]]
            result = submit_checklist_run(conn, new_id, detail["template_id"], answers, detail["performed_by"],
                                          notes=detail["notes"], context=detail["context"],
                                          performed_at=datetime.fromisoformat(r["performed_at"]))
            copied_runs += 1
            findings += len(result["findings_created"])
        for template_id, entry in entries.items():
            save_form(conn, new_id, template_id, entry["data"], actor, source="transfer")
        with tenant_scope(conn, tenant_id):
            conn.execute(
                "UPDATE advised_operator SET status = 'transferred', transferred_tenant_id = %s, transferred_at = now(), "
                "transferred_by = %s WHERE id = %s AND tenant_id = %s",
                (new_id, actor, op["operator_id"], tenant_id),
            )
    return {"organization": org, "copied_runs": copied_runs, "copied_forms": len(entries), "findings_created": findings,
            "operator": get_operator(conn, tenant_id, op["operator_id"])}
