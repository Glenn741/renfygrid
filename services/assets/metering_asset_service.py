"""Fronteras, equipos y su bitacora con BD (Track F, Q2, migraciones 0049 y
0050). docs/10-caso-energia-fronteras.md.

- La frontera (`metering_point`) es el lugar; el equipo (`equipment`) es el
  aparato por numero de serie; `equipment_installation` dice que equipo
  estuvo en que frontera y posicion, y desde/hasta cuando.
- La bitacora (`metering_event`) solo crece. Instalar o retirar un equipo la
  escribe sola; cambiar un equipo de una frontera que ya tuvo otro en esa
  posicion genera ademas la novedad de la hoja de vida (p. ej. "Cambio de
  medidor principal") pendiente de reportar a XM.
- Las frecuencias, los tipos de punto, los tipos de registro y las fichas
  de la hoja de vida salen del paquete regulatorio que la organizacion
  adopto (`CO-CREG-038` en Colombia). La ventana de "por vencer" es un
  parametro de la organizacion (`tenant.config`); sin configurar no se
  inventa.
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "community"))

import psycopg  # noqa: E402
from psycopg.types.json import Json  # noqa: E402

from metering_asset_engine import invalidates_calibration, periodic_status, point_class_for, worst_status  # noqa: E402
from form_engine import InvalidFormError, clean_record, completeness  # noqa: E402
from pack_service import active_pack_ids  # noqa: E402
from renmeter_common.db import tenant_scope  # noqa: E402

DUE_SOON_KEY = "asset_due_soon_days"
POINT_STATUSES = ("active", "suspended", "failure", "cancelled")
EQUIPMENT_STATUSES = ("installed", "stock", "lab", "retired")
OWNERSHIPS = ("user", "rf", "or")
SOURCES = ("manual", "import", "field", "system")


class AssetNotFoundError(LookupError):
    """La frontera, el equipo o el registro no existe en esta organizacion."""


class AssetConflictError(RuntimeError):
    """Frontera o equipo repetido, posicion ocupada, equipo ya instalado..."""


# ── Contexto: paquete, catalogos y parametros de la organizacion ─────

def due_soon_days(conn: psycopg.Connection, tenant_id: str) -> int | None:
    with conn.cursor() as cur:
        cur.execute("SELECT config ->> %s FROM tenant WHERE id = %s", (DUE_SOON_KEY, tenant_id))
        row = cur.fetchone()
    return int(row[0]) if row and row[0] is not None else None


def set_due_soon_days(conn: psycopg.Connection, tenant_id: str, days: int) -> dict:
    if not isinstance(days, int) or days <= 0:
        raise InvalidFormError("La ventana de aviso debe ser un número de días mayor que cero")
    with conn.cursor() as cur:
        cur.execute("UPDATE tenant SET config = config || jsonb_build_object(%s::text, %s::int) WHERE id = %s",
                    (DUE_SOON_KEY, days, tenant_id))
    return {"due_soon_days": days}


def _context(conn: psycopg.Connection, tenant_id: str) -> dict[str, Any]:
    packs = active_pack_ids(conn, tenant_id)
    with conn.cursor() as cur:
        cur.execute("SELECT pack_id, code, sort_order, label, min_mwh_month, min_mva FROM metering_point_class "
                    "WHERE pack_id = ANY(%s) ORDER BY pack_id, sort_order", (packs,))
        classes = [{"pack_id": r[0], "code": r[1], "sort_order": r[2], "label": r[3],
                    "min_mwh_month": float(r[4]), "min_mva": float(r[5])} for r in cur.fetchall()]
        cur.execute("SELECT pack_id, point_class, equipment_class, activity, every_months, citation "
                    "FROM maintenance_frequency WHERE pack_id = ANY(%s)", (packs,))
        frequencies = {(r[0], r[1], r[2], r[3]): {"every_months": r[4], "citation": r[5]} for r in cur.fetchall()}
        cur.execute("SELECT code, label, plural, periodic_activity, sector_code FROM equipment_class ORDER BY sort_order")
        eq_classes = {r[0]: {"code": r[0], "label": r[1], "plural": r[2], "periodic_activity": r[3], "sector_code": r[4]}
                      for r in cur.fetchall()}
        cur.execute("SELECT code, equipment_class, label, novelty_type, sort_order FROM installation_position ORDER BY sort_order")
        positions = {r[0]: {"code": r[0], "equipment_class": r[1], "label": r[2], "novelty_type": r[3], "sort_order": r[4]}
                     for r in cur.fetchall()}
        cur.execute("SELECT code, label, scope, activity, requires_xm_update, invalidates_calibration, manual, data_spec, "
                    "source_ref, sort_order FROM metering_event_type WHERE pack_id = ANY(%s) ORDER BY sort_order", (packs,))
        event_types = {r[0]: {"code": r[0], "label": r[1], "scope": r[2], "activity": r[3], "requires_xm_update": r[4],
                              "invalidates_calibration": r[5], "manual": r[6], "data_spec": r[7], "source_ref": r[8]}
                       for r in cur.fetchall()}
        cur.execute("SELECT id, scope, equipment_class, sort_order, title, form_spec, source_ref FROM asset_form "
                    "WHERE pack_id = ANY(%s) ORDER BY scope, sort_order", (packs,))
        forms = {r[0]: {"id": r[0], "scope": r[1], "equipment_class": r[2], "title": r[4], "form_spec": r[5],
                        "source_ref": r[6]} for r in cur.fetchall()}
    regulatory = classes[0]["pack_id"] if classes else None
    return {"packs": packs, "pack_id": regulatory, "classes": [c for c in classes if c["pack_id"] == regulatory],
            "frequencies": frequencies, "equipment_classes": eq_classes, "positions": positions,
            "event_types": event_types, "forms": forms, "due_soon_days": due_soon_days(conn, tenant_id)}


def catalog(conn: psycopg.Connection, tenant_id: str) -> dict:
    ctx = _context(conn, tenant_id)
    freq = [{"point_class": k[1], "equipment_class": k[2], "activity": k[3], **v}
            for k, v in sorted(ctx["frequencies"].items()) if k[0] == ctx["pack_id"]]
    return {"pack_id": ctx["pack_id"], "point_classes": ctx["classes"], "frequencies": freq,
            "equipment_classes": list(ctx["equipment_classes"].values()), "positions": list(ctx["positions"].values()),
            "event_types": list(ctx["event_types"].values()), "forms": list(ctx["forms"].values()),
            "due_soon_days": ctx["due_soon_days"]}


# ── Estado periodico (calibracion / prueba de rutina) ─────────────────

def _periodic_map(cur: psycopg.Cursor, ctx: dict, equipment: list[dict], today: date) -> dict[str, dict]:
    """Estado de la actividad periodica de cada equipo. `equipment`: dicts
    con id, class_code y point_class (None si no esta instalado). Para un CT
    o PT la prueba de rutina se cuenta desde la ultima prueba o, si no hay,
    desde su calibracion inicial (CREG 038 art. 11)."""
    ids = [e["id"] for e in equipment]
    if not ids:
        return {}
    cur.execute(
        "SELECT e.equipment_id::text, t.activity, max(e.occurred_on) "
        "FROM metering_event e JOIN metering_event_type t ON t.code = e.type_code "
        "WHERE t.activity IS NOT NULL AND e.equipment_id = ANY(%s::uuid[]) "
        "AND coalesce(e.data -> 'fields' -> 'result' ->> 'value', '') <> 'fail' GROUP BY 1, 2", (ids,))
    last: dict[tuple[str, str], date] = {(r[0], r[1]): r[2] for r in cur.fetchall()}
    cur.execute(
        "SELECT e.equipment_id::text, e.occurred_on, t.invalidates_calibration, e.data "
        "FROM metering_event e JOIN metering_event_type t ON t.code = e.type_code "
        "WHERE t.invalidates_calibration IS NOT NULL AND e.equipment_id = ANY(%s::uuid[])", (ids,))
    invalid: dict[str, date] = {}
    for eq_id, day, rule, data in cur.fetchall():
        if invalidates_calibration(rule, data) and (eq_id not in invalid or day > invalid[eq_id]):
            invalid[eq_id] = day
    out = {}
    for e in equipment:
        activity = ctx["equipment_classes"][e["class_code"]]["periodic_activity"]
        freq = ctx["frequencies"].get((ctx["pack_id"], e.get("point_class"), e["class_code"], activity)) if activity else None
        done = last.get((e["id"], activity)) if activity else None
        if activity == "routine_test":
            initial = last.get((e["id"], "calibration"))
            done = max(d for d in (done, initial) if d) if (done or initial) else None
        status = periodic_status(activity=activity, every_months=freq["every_months"] if freq else None, last_done=done,
                                 invalidated_after=invalid.get(e["id"]) if activity == "calibration" else None,
                                 today=today, due_soon_days=ctx["due_soon_days"])
        status["activity"] = activity
        out[e["id"]] = status
    return out


# ── Fronteras ─────────────────────────────────────────────────────────

POINT_COLUMNS = ("code", "export_code", "niu", "name", "customer_name", "address", "city", "region", "lat", "lon",
                 "point_class", "voltage_kv", "capacity_kva", "consumption_mwh_month", "status", "registered_on", "verified_on")
_POINT_SELECT = ("SELECT id, " + ", ".join(POINT_COLUMNS) + ", created_by, created_at, updated_at FROM metering_point")


def _point_row(r: tuple) -> dict:
    out: dict[str, Any] = {"id": str(r[0])}
    for i, col in enumerate(POINT_COLUMNS, start=1):
        value = r[i]
        if isinstance(value, date):
            value = value.isoformat()
        elif value is not None and col in ("lat", "lon", "voltage_kv", "capacity_kva", "consumption_mwh_month"):
            value = float(value)
        out[col] = value
    out.update(created_by=r[-3], created_at=r[-2].isoformat(), updated_at=r[-1].isoformat())
    return out


def _clean_point(ctx: dict, data: dict, partial: bool = False) -> dict:
    clean: dict[str, Any] = {}
    for col in POINT_COLUMNS:
        if col not in data:
            continue
        value = data[col]
        if isinstance(value, str):
            value = value.strip() or None
        clean[col] = value
    for col in ("code", "name", "customer_name"):
        if (not partial or col in clean) and not clean.get(col):
            raise InvalidFormError({"code": "El código de la frontera es obligatorio", "name": "El nombre de la frontera es obligatorio",
                                    "customer_name": "El nombre del usuario (cliente) es obligatorio"}[col])
    if "status" in clean and clean["status"] is None:
        clean.pop("status")
    if clean.get("status") and clean["status"] not in POINT_STATUSES:
        raise InvalidFormError(f"Estado de frontera desconocido: {clean['status']!r}")
    if clean.get("point_class") is not None:
        clean["point_class"] = str(clean["point_class"])
        if clean["point_class"] not in {c["code"] for c in ctx["classes"]}:
            raise InvalidFormError(f"Tipo de punto desconocido: {clean['point_class']!r}")
    for col in ("lat", "lon", "voltage_kv", "capacity_kva", "consumption_mwh_month"):
        if clean.get(col) is not None:
            try:
                clean[col] = float(str(clean[col]).replace(",", "."))
            except ValueError:
                raise InvalidFormError(f"{col}: se esperaba un número") from None
    for col in ("registered_on", "verified_on"):
        if clean.get(col) is not None and not isinstance(clean[col], date):
            try:
                clean[col] = date.fromisoformat(str(clean[col])[:10])
            except ValueError:
                raise InvalidFormError(f"{col}: fecha inválida (use AAAA-MM-DD)") from None
    return clean


def _create_point(cur: psycopg.Cursor, tenant_id: str, ctx: dict, data: dict, created_by: str) -> str:
    clean = _clean_point(ctx, data)
    clean["pack_id"] = ctx["pack_id"] if clean.get("point_class") else None
    cols = list(clean) + ["tenant_id", "created_by"]
    cur.execute("SELECT 1 FROM metering_point WHERE lower(btrim(code)) = lower(%s)", (clean["code"],))
    if cur.fetchone():
        raise AssetConflictError(f"Ya existe la frontera {clean['code']!r}")
    cur.execute(f"INSERT INTO metering_point ({', '.join(cols)}) VALUES ({', '.join(['%s'] * len(cols))}) RETURNING id",
                [*clean.values(), tenant_id, created_by])
    return str(cur.fetchone()[0])


def create_point(conn: psycopg.Connection, tenant_id: str, data: dict, created_by: str) -> dict:
    ctx = _context(conn, tenant_id)
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                point_id = _create_point(cur, tenant_id, ctx, data, created_by)
    return get_point(conn, tenant_id, point_id)


def update_point(conn: psycopg.Connection, tenant_id: str, point_id: str, data: dict) -> dict:
    ctx = _context(conn, tenant_id)
    clean = _clean_point(ctx, data, partial=True)
    if "point_class" in clean:
        clean["pack_id"] = ctx["pack_id"] if clean["point_class"] else None
    if clean:
        with conn.transaction():
            with tenant_scope(conn, tenant_id):
                with conn.cursor() as cur:
                    if "code" in clean:
                        cur.execute("SELECT 1 FROM metering_point WHERE lower(btrim(code)) = lower(%s) AND id <> %s",
                                    (clean["code"], point_id))
                        if cur.fetchone():
                            raise AssetConflictError(f"Ya existe la frontera {clean['code']!r}")
                    sets = ", ".join(f"{c} = %s" for c in clean)
                    cur.execute(f"UPDATE metering_point SET {sets}, updated_at = now() WHERE id = %s",
                                [*clean.values(), point_id])
                    if cur.rowcount == 0:
                        raise AssetNotFoundError("No existe esa frontera")
    return get_point(conn, tenant_id, point_id)


def _current_installations(cur: psycopg.Cursor, point_ids: list[str] | None = None) -> list[dict]:
    where = "i.removed_on IS NULL" + (" AND i.point_id = ANY(%s::uuid[])" if point_ids is not None else "")
    cur.execute(
        "SELECT i.id, i.point_id::text, i.position_code, i.installed_on, e.id::text, e.class_code, e.serial, e.brand, "
        "e.model, p.point_class FROM equipment_installation i JOIN equipment e ON e.id = i.equipment_id "
        f"JOIN metering_point p ON p.id = i.point_id WHERE {where}", (point_ids,) if point_ids is not None else None)
    return [{"installation_id": str(r[0]), "point_id": r[1], "position_code": r[2], "installed_on": r[3].isoformat(),
             "id": r[4], "class_code": r[5], "serial": r[6], "brand": r[7], "model": r[8], "point_class": r[9]}
            for r in cur.fetchall()]


def list_points(conn: psycopg.Connection, tenant_id: str, q: str | None = None, status: str | None = None,
                point_class: str | None = None, periodic: str | None = None, today: date | None = None) -> dict:
    """Todas las fronteras con su estado de calibracion (el peor de sus
    equipos instalados), su medidor principal y las novedades pendientes."""
    today = today or date.today()
    ctx = _context(conn, tenant_id)
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                where, params = [], []
                if q:
                    where.append("(code ILIKE %s OR name ILIKE %s OR customer_name ILIKE %s OR city ILIKE %s)")
                    params += [f"%{q.strip()}%"] * 4
                if status:
                    where.append("status = %s")
                    params.append(status)
                if point_class:
                    where.append("point_class = %s")
                    params.append(point_class)
                cur.execute(_POINT_SELECT + (" WHERE " + " AND ".join(where) if where else "") + " ORDER BY code", params)
                points = [_point_row(r) for r in cur.fetchall()]
                installs = _current_installations(cur)
                periodic_map = _periodic_map(cur, ctx, installs, today)
                cur.execute("SELECT point_id::text, count(*) FROM metering_event WHERE xm_status = 'pending' "
                            "AND point_id IS NOT NULL GROUP BY 1")
                pending = dict(cur.fetchall())
    by_point: dict[str, list[dict]] = {}
    for inst in installs:
        by_point.setdefault(inst["point_id"], []).append(inst)
    rows = []
    for p in points:
        mine = by_point.get(p["id"], [])
        statuses = [periodic_map[i["id"]]["status"] for i in mine]
        main = next((i for i in mine if i["position_code"] == "main_active"), None)
        p.update(periodic_status=worst_status(statuses) if mine else "missing",
                 main_meter={"id": main["id"], "serial": main["serial"], "brand": main["brand"]} if main else None,
                 equipment_count=len(mine), xm_pending=pending.get(p["id"], 0),
                 next_due=min((periodic_map[i["id"]]["due_on"] for i in mine if periodic_map[i["id"]]["due_on"]), default=None))
        if periodic and p["periodic_status"] != periodic:
            continue
        rows.append(p)
    return {"points": rows, "total": len(rows), "due_soon_days": ctx["due_soon_days"]}


def _events(cur: psycopg.Cursor, ctx: dict, where: str, params: tuple) -> list[dict]:
    cur.execute(
        "SELECT ev.id, ev.point_id::text, ev.equipment_id::text, ev.type_code, ev.occurred_on, ev.data, ev.notes, "
        "ev.source, ev.external_ref, ev.recorded_by, ev.recorded_at, ev.xm_status, ev.xm_reported_on, ev.xm_reported_by, "
        "e.serial, e.class_code, p.code FROM metering_event ev LEFT JOIN equipment e ON e.id = ev.equipment_id "
        f"LEFT JOIN metering_point p ON p.id = ev.point_id WHERE {where} ORDER BY ev.occurred_on DESC, ev.recorded_at DESC",
        params)
    out = []
    for r in cur.fetchall():
        etype = ctx["event_types"].get(r[3], {"label": r[3], "data_spec": {"fields": []}})
        out.append({"id": str(r[0]), "point_id": r[1], "equipment_id": r[2], "type_code": r[3], "type_label": etype["label"],
                    "occurred_on": r[4].isoformat(), "data": r[5], "notes": r[6], "source": r[7], "external_ref": r[8],
                    "recorded_by": r[9], "recorded_at": r[10].isoformat(), "xm_status": r[11],
                    "xm_reported_on": r[12].isoformat() if r[12] else None, "xm_reported_by": r[13],
                    "equipment_serial": r[14], "equipment_class": r[15], "point_code": r[16],
                    "data_spec": etype.get("data_spec")})
    return out


def get_point(conn: psycopg.Connection, tenant_id: str, point_id: str, today: date | None = None) -> dict:
    """La hoja de vida de la frontera: datos, secciones (fichas de la
    Circular 119), equipos instalados con su estado, historial de
    instalaciones y bitacora."""
    today = today or date.today()
    ctx = _context(conn, tenant_id)
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(_POINT_SELECT + " WHERE id = %s", (point_id,))
                row = cur.fetchone()
                if row is None:
                    raise AssetNotFoundError("No existe esa frontera")
                point = _point_row(row)
                installs = _current_installations(cur, [point_id])
                periodic_map = _periodic_map(cur, ctx, installs, today)
                cur.execute(
                    "SELECT i.id, i.position_code, i.installed_on, i.removed_on, i.installed_by, i.removed_by, i.removal_reason, "
                    "e.id::text, e.class_code, e.serial, e.brand, e.model FROM equipment_installation i "
                    "JOIN equipment e ON e.id = i.equipment_id WHERE i.point_id = %s ORDER BY i.installed_on DESC", (point_id,))
                history = [{"installation_id": str(r[0]), "position_code": r[1], "installed_on": r[2].isoformat(),
                            "removed_on": r[3].isoformat() if r[3] else None, "installed_by": r[4], "removed_by": r[5],
                            "removal_reason": r[6], "equipment_id": r[7], "class_code": r[8], "serial": r[9], "brand": r[10],
                            "model": r[11]} for r in cur.fetchall()]
                cur.execute("SELECT form_id, data, version, updated_by, updated_at FROM metering_point_section WHERE point_id = %s",
                            (point_id,))
                saved = {r[0]: {"data": r[1], "version": r[2], "updated_by": r[3], "updated_at": r[4].isoformat()}
                         for r in cur.fetchall()}
                events = _events(cur, ctx, "ev.point_id = %s", (point_id,))
    sections = []
    for form in (f for f in ctx["forms"].values() if f["scope"] == "point"):
        entry = saved.get(form["id"])
        data = entry["data"] if entry else {"fields": {}}
        sections.append({**form, "data": data, "version": entry["version"] if entry else 0,
                         "updated_by": entry["updated_by"] if entry else None,
                         "updated_at": entry["updated_at"] if entry else None,
                         "progress": completeness("record", form["form_spec"], data)})
    equipment = []
    for inst in sorted(installs, key=lambda i: ctx["positions"][i["position_code"]]["sort_order"]):
        equipment.append({**inst, "position_label": ctx["positions"][inst["position_code"]]["label"],
                          "periodic": periodic_map[inst["id"]]})
    suggested = point_class_for(point["consumption_mwh_month"],
                                point["capacity_kva"] / 1000 if point["capacity_kva"] is not None else None, ctx["classes"])
    return {**point, "suggested_point_class": suggested, "equipment": equipment, "installation_history": history,
            "sections": sections, "events": events,
            "periodic_status": worst_status([e["periodic"]["status"] for e in equipment]) if equipment else "missing",
            "xm_pending": sum(1 for e in events if e["xm_status"] == "pending"),
            "due_soon_days": ctx["due_soon_days"]}


def save_point_section(conn: psycopg.Connection, tenant_id: str, point_id: str, form_id: str, data: dict,
                       saved_by: str) -> dict:
    ctx = _context(conn, tenant_id)
    form = ctx["forms"].get(form_id)
    if form is None or form["scope"] != "point":
        raise AssetNotFoundError(f"La sección {form_id!r} no existe en el paquete de la organización")
    clean = clean_record(form["form_spec"], data)
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute("SELECT 1 FROM metering_point WHERE id = %s", (point_id,))
                if cur.fetchone() is None:
                    raise AssetNotFoundError("No existe esa frontera")
                cur.execute(
                    "INSERT INTO metering_point_section (tenant_id, point_id, form_id, data, version, updated_by) "
                    "VALUES (%s, %s, %s, %s, 1, %s) ON CONFLICT (point_id, form_id) DO UPDATE SET data = EXCLUDED.data, "
                    "version = metering_point_section.version + 1, updated_by = EXCLUDED.updated_by, updated_at = now() "
                    "RETURNING version", (tenant_id, point_id, form_id, Json(clean), saved_by))
                version = cur.fetchone()[0]
                cur.execute("INSERT INTO metering_point_section_version (tenant_id, point_id, form_id, version, data, saved_by) "
                            "VALUES (%s, %s, %s, %s, %s, %s)", (tenant_id, point_id, form_id, version, Json(clean), saved_by))
    return {"form_id": form_id, "version": version, "data": clean,
            "progress": completeness("record", form["form_spec"], clean)}


# ── Equipos ───────────────────────────────────────────────────────────

EQUIPMENT_COLUMNS = ("class_code", "serial", "brand", "model", "manufacturer", "year", "ownership", "status")


def _equipment_row(r: tuple) -> dict:
    return {"id": str(r[0]), "class_code": r[1], "serial": r[2], "brand": r[3], "model": r[4], "manufacturer": r[5],
            "year": r[6], "ownership": r[7], "status": r[8], "attributes": r[9], "created_by": r[10],
            "created_at": r[11].isoformat(), "updated_at": r[12].isoformat()}


_EQUIPMENT_SELECT = ("SELECT id, class_code, serial, brand, model, manufacturer, year, ownership, status, attributes, "
                     "created_by, created_at, updated_at FROM equipment")


def _attributes_form(ctx: dict, class_code: str) -> dict | None:
    return next((f for f in ctx["forms"].values() if f["scope"] == "equipment" and f["equipment_class"] == class_code), None)


def _clean_equipment(ctx: dict, data: dict, partial: bool = False, class_code: str | None = None) -> dict:
    clean: dict[str, Any] = {}
    for col in EQUIPMENT_COLUMNS:
        if col in data:
            value = data[col]
            clean[col] = (value.strip() or None) if isinstance(value, str) else value
    klass = clean.get("class_code") or class_code
    if not partial or "class_code" in clean:
        if klass not in ctx["equipment_classes"]:
            raise InvalidFormError(f"Tipo de equipo desconocido: {klass!r}")
    if (not partial or "serial" in clean) and not clean.get("serial"):
        raise InvalidFormError("El número de serie es obligatorio")
    if clean.get("year") is not None:
        try:
            clean["year"] = int(clean["year"])
        except (TypeError, ValueError):
            raise InvalidFormError("El año de fabricación debe ser un número") from None
    if clean.get("ownership") and clean["ownership"] not in OWNERSHIPS:
        raise InvalidFormError(f"Propiedad desconocida: {clean['ownership']!r}")
    if "status" in clean:
        if clean["status"] not in ("stock", "lab", "retired"):
            raise InvalidFormError("El estado se cambia a bodega, laboratorio o baja; 'instalado' lo pone la instalación")
    if "attributes" in data:
        form = _attributes_form(ctx, klass)
        if form is None:
            raise InvalidFormError("Este tipo de equipo no tiene ficha técnica en el paquete")
        clean["attributes"] = Json(clean_record(form["form_spec"], data["attributes"]))
    return clean


def find_equipment(cur: psycopg.Cursor, class_code: str, brand: str | None, serial: str) -> str | None:
    cur.execute("SELECT id::text FROM equipment WHERE class_code = %s AND lower(coalesce(brand, '')) = lower(coalesce(%s, '')) "
                "AND lower(btrim(serial)) = lower(btrim(%s))", (class_code, brand, serial))
    row = cur.fetchone()
    return row[0] if row else None


def _create_equipment(cur: psycopg.Cursor, tenant_id: str, ctx: dict, data: dict, created_by: str) -> str:
    clean = _clean_equipment(ctx, data)
    clean.setdefault("status", "stock")
    cols = list(clean) + ["tenant_id", "created_by"]
    if find_equipment(cur, clean["class_code"], clean.get("brand"), clean["serial"]):
        raise AssetConflictError(f"Ya existe el equipo {clean.get('brand') or ''} {clean['serial']}".strip())
    cur.execute(f"INSERT INTO equipment ({', '.join(cols)}) VALUES ({', '.join(['%s'] * len(cols))}) RETURNING id",
                [*clean.values(), tenant_id, created_by])
    return str(cur.fetchone()[0])


def create_equipment(conn: psycopg.Connection, tenant_id: str, data: dict, created_by: str) -> dict:
    ctx = _context(conn, tenant_id)
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                equipment_id = _create_equipment(cur, tenant_id, ctx, data, created_by)
    return get_equipment(conn, tenant_id, equipment_id)


def update_equipment(conn: psycopg.Connection, tenant_id: str, equipment_id: str, data: dict) -> dict:
    ctx = _context(conn, tenant_id)
    current = get_equipment(conn, tenant_id, equipment_id)
    if data.get("status") and current["status"] == "installed":
        raise AssetConflictError("El equipo está instalado: retírelo de la frontera para cambiar su estado")
    clean = _clean_equipment(ctx, data, partial=True, class_code=current["class_code"])
    clean.pop("class_code", None)
    if clean:
        with conn.transaction():
            with tenant_scope(conn, tenant_id):
                with conn.cursor() as cur:
                    sets = ", ".join(f"{c} = %s" for c in clean)
                    cur.execute(f"UPDATE equipment SET {sets}, updated_at = now() WHERE id = %s", [*clean.values(), equipment_id])
    return get_equipment(conn, tenant_id, equipment_id)


def list_equipment(conn: psycopg.Connection, tenant_id: str, q: str | None = None, class_code: str | None = None,
                   status: str | None = None, periodic: str | None = None, today: date | None = None) -> dict:
    today = today or date.today()
    ctx = _context(conn, tenant_id)
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                where, params = [], []
                if q:
                    where.append("(serial ILIKE %s OR brand ILIKE %s OR model ILIKE %s)")
                    params += [f"%{q.strip()}%"] * 3
                if class_code:
                    where.append("class_code = %s")
                    params.append(class_code)
                if status:
                    where.append("status = %s")
                    params.append(status)
                cur.execute(_EQUIPMENT_SELECT + (" WHERE " + " AND ".join(where) if where else "") + " ORDER BY class_code, serial",
                            params)
                items = [_equipment_row(r) for r in cur.fetchall()]
                installs = {i["id"]: i for i in _current_installations(cur)}
                cur.execute("SELECT id::text, code, name FROM metering_point")
                points = {r[0]: {"code": r[1], "name": r[2]} for r in cur.fetchall()}
                periodic_map = _periodic_map(cur, ctx, [{"id": e["id"], "class_code": e["class_code"],
                                                         "point_class": installs.get(e["id"], {}).get("point_class")}
                                                        for e in items], today)
    rows = []
    for e in items:
        e.pop("attributes")
        inst = installs.get(e["id"])
        e["location"] = ({"point_id": inst["point_id"], "point_code": points[inst["point_id"]]["code"],
                          "point_name": points[inst["point_id"]]["name"], "position_code": inst["position_code"],
                          "position_label": ctx["positions"][inst["position_code"]]["label"], "installed_on": inst["installed_on"]}
                         if inst else None)
        e["periodic"] = periodic_map[e["id"]]
        if periodic and e["periodic"]["status"] != periodic:
            continue
        rows.append(e)
    return {"equipment": rows, "total": len(rows), "due_soon_days": ctx["due_soon_days"]}


def get_equipment(conn: psycopg.Connection, tenant_id: str, equipment_id: str, today: date | None = None) -> dict:
    today = today or date.today()
    ctx = _context(conn, tenant_id)
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(_EQUIPMENT_SELECT + " WHERE id = %s", (equipment_id,))
                row = cur.fetchone()
                if row is None:
                    raise AssetNotFoundError("No existe ese equipo")
                eq = _equipment_row(row)
                cur.execute(
                    "SELECT i.id, i.point_id::text, p.code, p.name, p.point_class, i.position_code, i.installed_on, i.removed_on, "
                    "i.installed_by, i.removed_by, i.removal_reason FROM equipment_installation i "
                    "JOIN metering_point p ON p.id = i.point_id WHERE i.equipment_id = %s ORDER BY i.installed_on DESC",
                    (equipment_id,))
                history = [{"installation_id": str(r[0]), "point_id": r[1], "point_code": r[2], "point_name": r[3],
                            "point_class": r[4], "position_code": r[5], "position_label": ctx["positions"][r[5]]["label"],
                            "installed_on": r[6].isoformat(), "removed_on": r[7].isoformat() if r[7] else None,
                            "installed_by": r[8], "removed_by": r[9], "removal_reason": r[10]} for r in cur.fetchall()]
                current = next((h for h in history if h["removed_on"] is None), None)
                periodic = _periodic_map(cur, ctx, [{"id": equipment_id, "class_code": eq["class_code"],
                                                     "point_class": current["point_class"] if current else None}], today)
                events = _events(cur, ctx, "ev.equipment_id = %s", (equipment_id,))
    form = _attributes_form(ctx, eq["class_code"])
    return {**eq, "class_label": ctx["equipment_classes"][eq["class_code"]]["label"], "location": current,
            "installation_history": history, "periodic": periodic[equipment_id], "events": events,
            "attributes_form": form,
            "attributes_progress": completeness("record", form["form_spec"], eq["attributes"]) if form else None}


# ── Instalar y retirar ────────────────────────────────────────────────

def _insert_event(cur: psycopg.Cursor, tenant_id: str, ctx: dict, *, type_code: str, point_id: str | None,
                  equipment_id: str | None, occurred_on: date, data: dict | None, notes: str | None, source: str,
                  external_ref: str | None, recorded_by: str) -> str:
    etype = ctx["event_types"][type_code]
    cur.execute(
        "INSERT INTO metering_event (tenant_id, point_id, equipment_id, type_code, occurred_on, data, notes, source, "
        "external_ref, recorded_by, xm_status) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id",
        (tenant_id, point_id, equipment_id, type_code, occurred_on, Json(data or {"fields": {}}), notes, source, external_ref,
         recorded_by, "pending" if etype["requires_xm_update"] else None))
    return str(cur.fetchone()[0])


def _as_date(value: Any, label: str) -> date:
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        raise InvalidFormError(f"{label}: fecha inválida (use AAAA-MM-DD)") from None


def _install(cur: psycopg.Cursor, tenant_id: str, ctx: dict, equipment_id: str, point_id: str, position_code: str,
             installed_on: Any, installed_by: str, notes: str | None, source: str, external_ref: str | None) -> dict:
    position = ctx["positions"].get(position_code)
    if position is None:
        raise InvalidFormError(f"Posición desconocida: {position_code!r}")
    day = _as_date(installed_on, "Fecha de instalación")
    cur.execute("SELECT class_code, status, serial FROM equipment WHERE id = %s FOR UPDATE", (equipment_id,))
    eq = cur.fetchone()
    if eq is None:
        raise AssetNotFoundError("No existe ese equipo")
    if eq[0] != position["equipment_class"]:
        raise InvalidFormError(f"En «{position['label']}» va un {ctx['equipment_classes'][position['equipment_class']]['label'].lower()}, "
                               f"no un {ctx['equipment_classes'][eq[0]]['label'].lower()}")
    if eq[1] == "retired":
        raise AssetConflictError(f"El equipo {eq[2]} está dado de baja")
    cur.execute("SELECT 1 FROM metering_point WHERE id = %s", (point_id,))
    if cur.fetchone() is None:
        raise AssetNotFoundError("No existe esa frontera")
    cur.execute("SELECT 1 FROM equipment_installation WHERE equipment_id = %s AND removed_on IS NULL", (equipment_id,))
    if cur.fetchone():
        raise AssetConflictError(f"El equipo {eq[2]} ya está instalado en otra frontera: retírelo primero")
    cur.execute("SELECT e.serial FROM equipment_installation i JOIN equipment e ON e.id = i.equipment_id "
                "WHERE i.point_id = %s AND i.position_code = %s AND i.removed_on IS NULL", (point_id, position_code))
    busy = cur.fetchone()
    if busy:
        raise AssetConflictError(f"En «{position['label']}» ya está el equipo {busy[0]}: retírelo primero")
    cur.execute("SELECT 1 FROM equipment_installation WHERE point_id = %s AND position_code = %s", (point_id, position_code))
    replacing = cur.fetchone() is not None
    cur.execute("INSERT INTO equipment_installation (tenant_id, equipment_id, point_id, position_code, installed_on, "
                "installed_by) VALUES (%s, %s, %s, %s, %s, %s) RETURNING id",
                (tenant_id, equipment_id, point_id, position_code, day, installed_by))
    installation_id = str(cur.fetchone()[0])
    cur.execute("UPDATE equipment SET status = 'installed', updated_at = now() WHERE id = %s", (equipment_id,))
    _insert_event(cur, tenant_id, ctx, type_code="installed", point_id=point_id, equipment_id=equipment_id,
                  occurred_on=day, data={"fields": {"position": {"value": position_code}}}, notes=notes,
                  source=source, external_ref=external_ref, recorded_by=installed_by)
    if replacing and position["novelty_type"] in ctx["event_types"]:
        _insert_event(cur, tenant_id, ctx, type_code=position["novelty_type"], point_id=point_id,
                      equipment_id=equipment_id, occurred_on=day, data=None, notes=notes, source=source,
                      external_ref=external_ref, recorded_by=installed_by)
    return {"installation_id": installation_id, "novelty": replacing}


def install(conn: psycopg.Connection, tenant_id: str, equipment_id: str, point_id: str, position_code: str,
            installed_on: Any, installed_by: str, notes: str | None = None, source: str = "manual",
            external_ref: str | None = None) -> dict:
    ctx = _context(conn, tenant_id)
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                return _install(cur, tenant_id, ctx, equipment_id, point_id, position_code, installed_on, installed_by,
                                notes, source, external_ref)


def remove(conn: psycopg.Connection, tenant_id: str, equipment_id: str, removed_on: Any, removed_by: str,
           reason: str | None = None, new_status: str = "stock", source: str = "manual", external_ref: str | None = None) -> dict:
    ctx = _context(conn, tenant_id)
    if new_status not in ("stock", "lab", "retired"):
        raise InvalidFormError("Al retirarlo el equipo va a bodega, a laboratorio o se da de baja")
    day = _as_date(removed_on, "Fecha de retiro")
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute("SELECT id, point_id::text, installed_on FROM equipment_installation "
                            "WHERE equipment_id = %s AND removed_on IS NULL FOR UPDATE", (equipment_id,))
                row = cur.fetchone()
                if row is None:
                    raise AssetConflictError("El equipo no está instalado")
                if day < row[2]:
                    raise InvalidFormError("La fecha de retiro es anterior a la de instalación")
                cur.execute("UPDATE equipment_installation SET removed_on = %s, removed_by = %s, removal_reason = %s WHERE id = %s",
                            (day, removed_by, reason, row[0]))
                cur.execute("UPDATE equipment SET status = %s, updated_at = now() WHERE id = %s", (new_status, equipment_id))
                _insert_event(cur, tenant_id, ctx, type_code="removed", point_id=row[1], equipment_id=equipment_id,
                              occurred_on=day, data={"fields": {"new_status": {"value": new_status}}}, notes=reason,
                              source=source, external_ref=external_ref, recorded_by=removed_by)
    return {"installation_id": str(row[0]), "status": new_status}


# ── Bitacora ──────────────────────────────────────────────────────────

def record_event(conn: psycopg.Connection, tenant_id: str, *, type_code: str, occurred_on: Any, recorded_by: str,
                 point_id: str | None = None, equipment_id: str | None = None, data: dict | None = None,
                 notes: str | None = None, source: str = "manual", external_ref: str | None = None) -> dict:
    """Agrega un registro a la bitacora. Un registro de un equipo instalado
    queda tambien en la hoja de vida de su frontera."""
    ctx = _context(conn, tenant_id)
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                return _record(cur, tenant_id, ctx, type_code=type_code, occurred_on=occurred_on, recorded_by=recorded_by,
                               point_id=point_id, equipment_id=equipment_id, data=data, notes=notes, source=source,
                               external_ref=external_ref)


def _record(cur: psycopg.Cursor, tenant_id: str, ctx: dict, *, type_code: str, occurred_on: Any, recorded_by: str,
            point_id: str | None, equipment_id: str | None, data: dict | None, notes: str | None, source: str,
            external_ref: str | None) -> dict:
    etype = ctx["event_types"].get(type_code)
    if etype is None:
        raise InvalidFormError(f"Tipo de registro desconocido: {type_code!r}")
    if not etype["manual"] and source == "manual":
        raise InvalidFormError(f"«{etype['label']}» lo registra el sistema al instalar o retirar equipos")
    if source not in SOURCES:
        raise InvalidFormError(f"Origen desconocido: {source!r}")
    if etype["scope"] == "point" and not point_id:
        raise InvalidFormError(f"«{etype['label']}» se registra sobre una frontera")
    if etype["scope"] == "equipment" and not equipment_id:
        raise InvalidFormError(f"«{etype['label']}» se registra sobre un equipo")
    if not point_id and not equipment_id:
        raise InvalidFormError("Indique la frontera o el equipo")
    clean = clean_record(etype["data_spec"], data)
    progress = completeness("record", etype["data_spec"], clean)
    if etype["data_spec"].get("fields") and progress["missing_required"]:
        raise InvalidFormError("Faltan datos obligatorios: " + ", ".join(progress["missing_required"]))
    day = _as_date(occurred_on, "Fecha")
    if day > date.today():
        raise InvalidFormError("La fecha del registro no puede ser futura")
    if equipment_id:
        cur.execute("SELECT 1 FROM equipment WHERE id = %s", (equipment_id,))
        if cur.fetchone() is None:
            raise AssetNotFoundError("No existe ese equipo")
        if not point_id:
            cur.execute("SELECT point_id::text FROM equipment_installation WHERE equipment_id = %s "
                        "AND removed_on IS NULL", (equipment_id,))
            row = cur.fetchone()
            point_id = row[0] if row else None
    if point_id:
        cur.execute("SELECT 1 FROM metering_point WHERE id = %s", (point_id,))
        if cur.fetchone() is None:
            raise AssetNotFoundError("No existe esa frontera")
    event_id = _insert_event(cur, tenant_id, ctx, type_code=type_code, point_id=point_id, equipment_id=equipment_id,
                             occurred_on=day, data=clean, notes=(notes or "").strip() or None, source=source,
                             external_ref=external_ref, recorded_by=recorded_by)
    return {"id": event_id, "type_code": type_code, "point_id": point_id, "equipment_id": equipment_id,
            "xm_status": "pending" if etype["requires_xm_update"] else None}


def pending_xm(conn: psycopg.Connection, tenant_id: str) -> list[dict]:
    ctx = _context(conn, tenant_id)
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                return _events(cur, ctx, "ev.xm_status = 'pending'", ())


def mark_reported(conn: psycopg.Connection, tenant_id: str, event_ids: list[str], reported_on: Any, reported_by: str) -> dict:
    day = _as_date(reported_on, "Fecha de reporte")
    if not event_ids:
        raise InvalidFormError("Elija las novedades reportadas")
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute("UPDATE metering_event SET xm_status = 'reported', xm_reported_on = %s, xm_reported_by = %s "
                            "WHERE id = ANY(%s::uuid[]) AND xm_status = 'pending'", (day, reported_by, event_ids))
                updated = cur.rowcount
    return {"reported": updated}


# ── Tablero ───────────────────────────────────────────────────────────

def summary(conn: psycopg.Connection, tenant_id: str, today: date | None = None) -> dict:
    today = today or date.today()
    ctx = _context(conn, tenant_id)
    points = list_points(conn, tenant_id, today=today)["points"]
    equipment = list_equipment(conn, tenant_id, today=today)["equipment"]
    by_class: dict[str, int] = {}
    by_status: dict[str, int] = {}
    by_periodic: dict[str, int] = {}
    for p in points:
        by_class[p["point_class"] or "—"] = by_class.get(p["point_class"] or "—", 0) + 1
        by_status[p["status"]] = by_status.get(p["status"], 0) + 1
        by_periodic[p["periodic_status"]] = by_periodic.get(p["periodic_status"], 0) + 1
    eq_status: dict[str, int] = {}
    eq_periodic: dict[str, dict[str, int]] = {}
    for e in equipment:
        eq_status[e["status"]] = eq_status.get(e["status"], 0) + 1
        bucket = eq_periodic.setdefault(e["class_code"], {})
        bucket[e["periodic"]["status"]] = bucket.get(e["periodic"]["status"], 0) + 1
    # Primero lo vencido, luego lo que no tiene registro y al final lo que esta por vencer; dentro de cada uno, lo mas antiguo.
    rank = {"overdue": 0, "missing": 1, "due_soon": 2}
    upcoming = sorted((e for e in equipment if e["periodic"]["status"] in rank and e["location"]),
                      key=lambda e: (rank[e["periodic"]["status"]], e["periodic"]["due_on"] or ""))[:20]
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute("SELECT count(*) FROM metering_event WHERE xm_status = 'pending'")
                xm = cur.fetchone()[0]
                recent = _events(cur, ctx, "ev.type_code NOT IN ('installed', 'removed') AND ev.recorded_at > now() - interval '30 days'", ())[:10]
    without_main = sum(1 for p in points if p["status"] == "active" and p["main_meter"] is None)
    return {"points_total": len(points), "points_by_class": by_class, "points_by_status": by_status,
            "points_by_periodic": by_periodic, "points_without_main_meter": without_main,
            "equipment_total": len(equipment), "equipment_by_status": eq_status, "equipment_periodic_by_class": eq_periodic,
            "xm_pending": xm, "upcoming": upcoming, "recent_events": recent, "due_soon_days": ctx["due_soon_days"],
            "map": [{"id": p["id"], "code": p["code"], "name": p["name"], "lat": p["lat"], "lon": p["lon"],
                     "point_class": p["point_class"], "periodic_status": p["periodic_status"]}
                    for p in points if p["lat"] is not None and p["lon"] is not None]}
