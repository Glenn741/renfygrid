"""Mapa tematico de fronteras (Track F, Q2.5, migracion 0051).
docs/11-mapa-fronteras.md.

Las variables por las que se pinta o filtra son filas de `map_dimension`; aqui
solo se resuelve cada `source` para cada frontera:

    point:<columna>                    columna de metering_point
    equipment:<posicion>:<campo>       campo del equipo instalado en esa posicion
    equipment_attr:<posicion>:<clave>  campo de su ficha tecnica
    equipment_age:<posicion>           anos desde su ano de fabricacion, en los `bins` de la dimension
    computed:periodic                  peor estado de calibracion o prueba de sus equipos
    computed:comms                     si el medidor principal (vinculado al HES por su serie) reporto
                                       dentro de la ventana de la organizacion
    computed:alarm                     eventos no informativos del medidor dentro de esa ventana
    computed:xm_pending                si tiene novedades pendientes de XM
    computed:consumption_range         rango de consumo con los umbrales de los tipos de punto
    computed:pqr_open|pqr_group|pqr_type|pqr_cause   PQR abiertas (las tres ultimas, con varios valores)

El mapa devuelve todas las fronteras con el valor de cada dimension; los
filtros, los conteos y el color se calculan en el navegador al instante. Para
decenas de miles de fronteras esto pasaria a teselas o a agrupar en el
servidor (no hace falta con miles).
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "community"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "portal-api"))

import psycopg  # noqa: E402
from psycopg.types.json import Json  # noqa: E402

import metering_asset_service as svc  # noqa: E402
from customer_request_service import OPEN_STATUSES  # noqa: E402
from form_engine import InvalidFormError  # noqa: E402
from renmeter_common.db import tenant_scope  # noqa: E402
from tenant_settings import get_meter_stale_after_seconds  # noqa: E402

MULTI = {"computed:pqr_group", "computed:pqr_type", "computed:pqr_cause"}


def _dimensions(conn: psycopg.Connection, tenant_id: str, packs: list[str]) -> list[dict]:
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute("SELECT sector_code FROM tenant_sector")
                sectors = [r[0] for r in cur.fetchall()]
    with conn.cursor() as cur:
        cur.execute("SELECT key, group_label, label, role, source, labels_domain, bins, can_paint, can_filter, alert_codes, "
                    "alert_label, description FROM map_dimension WHERE pack_id = ANY(%s) "
                    "AND (sector_code IS NULL OR sector_code = ANY(%s)) ORDER BY sort_order", (packs, sectors))
        return [{"key": r[0], "group": r[1], "label": r[2], "role": r[3], "source": r[4], "labels_domain": r[5], "bins": r[6],
                 "can_paint": r[7], "can_filter": r[8], "alert_codes": r[9], "alert_label": r[10], "description": r[11],
                 "multi": r[4] in MULTI} for r in cur.fetchall()]


def _labels(conn: psycopg.Connection, packs: list[str], domains: list[str]) -> dict[str, list[dict]]:
    with conn.cursor() as cur:
        cur.execute("SELECT domain, code, label, tone FROM code_label WHERE domain = ANY(%s) AND pack_id = ANY(%s) "
                    "ORDER BY domain, sort_order", (domains, packs))
        out: dict[str, list[dict]] = {}
        for domain, code, lbl, tone in cur.fetchall():
            out.setdefault(domain, []).append({"code": code, "label": lbl, "tone": tone})
    return out


def _age_bin(year: int | None, bins: list[dict], today: date) -> str | None:
    if year is None:
        return None
    age = today.year - int(year)
    for b in bins:
        if b.get("max") is None or age < b["max"]:
            return b["code"]
    return None


def _consumption_bin(value: float | None, classes: list[dict]) -> str | None:
    if value is None:
        return None
    for c in sorted(classes, key=lambda c: -c["min_mwh_month"]):
        if value >= c["min_mwh_month"]:
            return c["code"]
    return None


def build_map(conn: psycopg.Connection, tenant_id: str, today: date | None = None) -> dict:
    today = today or date.today()
    ctx = svc._context(conn, tenant_id)
    dims = _dimensions(conn, tenant_id, ctx["packs"])
    listing = svc.list_points(conn, tenant_id, today=today)["points"]
    window = get_meter_stale_after_seconds(conn, tenant_id)
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT i.point_id::text, i.position_code, e.brand, e.model, e.ownership, e.year, e.attributes, lower(btrim(e.serial)) "
                    "FROM equipment_installation i JOIN equipment e ON e.id = i.equipment_id WHERE i.removed_on IS NULL")
                equipment: dict[tuple[str, str], dict] = {
                    (r[0], r[1]): {"brand": r[2], "model": r[3], "ownership": r[4], "year": r[5], "attributes": r[6], "serial": r[7]}
                    for r in cur.fetchall()}
                cur.execute(
                    "SELECT q.point_id::text, q.request_type, c.group_code, q.cause_code FROM customer_request q "
                    "JOIN pqr_cause c ON c.pack_id = q.pack_id AND c.code = q.cause_code "
                    "WHERE q.point_id IS NOT NULL AND q.status = ANY(%s) ORDER BY q.filed_on DESC", (list(OPEN_STATUSES),))
                pqr: dict[str, list[tuple[str, str, str]]] = {}
                for pid, rtype, group, cause in cur.fetchall():
                    pqr.setdefault(pid, []).append((rtype, group, cause))
                meters: dict[str, tuple[bool, bool]] = {}
                if window is not None:
                    cur.execute(
                        "SELECT lower(btrim(m.serial_number)), "
                        "EXISTS (SELECT 1 FROM raw_reading r WHERE r.meter_id = m.id AND r.\"timestamp\" > now() - make_interval(secs => %s)), "
                        "EXISTS (SELECT 1 FROM meter_event ev WHERE ev.meter_id = m.id AND ev.severity <> 'info' "
                        "        AND ev.\"timestamp\" > now() - make_interval(secs => %s)) FROM meter m", (window, window))
                    meters = {r[0]: (r[1], r[2]) for r in cur.fetchall()}
                else:
                    cur.execute("SELECT lower(btrim(serial_number)) FROM meter")
                    meters = {r[0]: (False, False) for r in cur.fetchall()}

    # Opciones de los campos de las fichas tecnicas, para nombrar sus valores.
    form_options: dict[str, dict[str, str]] = {}
    for form in ctx["forms"].values():
        for f in form["form_spec"].get("fields", []):
            if f.get("options"):
                form_options[f["key"]] = {o["code"]: o["label"] for o in f["options"]}
    domains = [d["labels_domain"] for d in dims if d["labels_domain"]]
    labels = _labels(conn, ctx["packs"], domains + ["map.none"])
    cause_labels = {}
    with conn.cursor() as cur:
        cur.execute("SELECT code, label FROM pqr_cause WHERE pack_id = ANY(%s)", (ctx["packs"],))
        cause_labels = dict(cur.fetchall())

    def value(dim: dict, p: dict) -> Any:
        kind, _, rest = dim["source"].partition(":")
        if kind == "point":
            v = p.get(rest)
            return v if dim["role"] == "size" else (str(v) if v not in (None, "") else None)
        if kind in ("equipment", "equipment_attr", "equipment_age"):
            position, _, field = rest.partition(":")
            eq = equipment.get((p["id"], position))
            if eq is None:
                return None
            if kind == "equipment":
                return eq.get(field)
            if kind == "equipment_attr":
                entry = ((eq["attributes"] or {}).get("fields") or {}).get(field)
                return entry.get("value") if isinstance(entry, dict) else None
            return _age_bin(eq.get("year"), dim["bins"] or [], today)
        name = rest
        open_pqr = pqr.get(p["id"], [])
        if name == "periodic":
            return p["periodic_status"]
        if name == "xm_pending":
            return "yes" if p["xm_pending"] else "no"
        if name == "consumption_range":
            return _consumption_bin(p.get("consumption_mwh_month"), ctx["classes"])
        if name == "pqr_open":
            return "yes" if open_pqr else "no"
        if name == "pqr_group":
            return list(dict.fromkeys(g for _, g, _ in open_pqr)) or None
        if name == "pqr_type":
            return list(dict.fromkeys(t for t, _, _ in open_pqr)) or None
        if name == "pqr_cause":
            return list(dict.fromkeys(c for _, _, c in open_pqr)) or None
        if name in ("comms", "alarm"):
            main = equipment.get((p["id"], "main_active"))
            link = meters.get(main["serial"]) if main else None
            if name == "comms":
                if link is None:
                    return "no_link"
                return "no_window" if window is None else ("reporting" if link[0] else "silent")
            if link is None or window is None:
                return None
            return "yes" if link[1] else "no"
        raise InvalidFormError(f"Origen de dimensión desconocido: {dim['source']!r}")

    # `v`: los valores de cada frontera en el orden de `dimensions` (compacto:
    # sin repetir el nombre de cada dimension en cada frontera).
    points = []
    for p in listing:
        points.append({"id": p["id"], "code": p["code"], "name": p["name"], "customer": p["customer_name"], "city": p["city"],
                       "lat": round(p["lat"], 5) if p["lat"] is not None else None,
                       "lon": round(p["lon"], 5) if p["lon"] is not None else None, "v": [value(d, p) for d in dims]})

    out_dims = []
    for index, d in enumerate(dims):
        cats: list[dict] = []
        if d["role"] == "category":
            present: dict[str, int] = {}
            for pt in points:
                vals = pt["v"][index]
                for v in (vals if isinstance(vals, list) else [vals]):
                    key = "__none__" if v is None else str(v)
                    present[key] = present.get(key, 0) + 1
            if d["labels_domain"]:
                cats = [dict(c) for c in labels.get(d["labels_domain"], [])]
            elif d["source"] == "computed:consumption_range":
                ordered = sorted(ctx["classes"], key=lambda c: -c["min_mwh_month"])
                cats = [{"code": c["code"], "label": (f"≥ {c['min_mwh_month']:,.0f} MWh-mes".replace(",", ".") if c["min_mwh_month"] else
                                                       f"< {ordered[i - 1]['min_mwh_month']:,.0f} MWh-mes".replace(",", ".")),
                         "tone": None} for i, c in enumerate(ordered)]
            elif d["source"] == "point:point_class":
                cats = [{"code": c["code"], "label": c["label"], "tone": None} for c in ctx["classes"]]
            elif d["source"] == "computed:pqr_cause":
                cats = [{"code": k, "label": f"{k} · {cause_labels.get(k, k)}", "tone": None} for k in sorted(present) if k != "__none__"]
            elif d["source"].startswith("equipment_attr:"):
                opts = form_options.get(d["source"].rsplit(":", 1)[1], {})
                cats = [{"code": k, "label": opts.get(k, k), "tone": None} for k in sorted(present, key=lambda k: -present[k]) if k != "__none__"]
            elif d["source"].startswith("equipment_age:"):
                cats = [{"code": b["code"], "label": b["label"], "tone": None} for b in d["bins"] or []]
            else:
                cats = [{"code": k, "label": k, "tone": None} for k in sorted(present, key=lambda k: (-present[k], k)) if k != "__none__"]
            for c in cats:
                c["count"] = present.get(c["code"], 0)
            cats = [c for c in cats if c["count"] or d["labels_domain"]]
            if present.get("__none__"):
                none = (labels.get("map.none") or [{"label": "Sin dato", "tone": "neutral"}])[0]
                cats.append({"code": "__none__", "label": none["label"], "tone": none["tone"], "count": present["__none__"]})
        out_dims.append({k: d[k] for k in ("key", "group", "label", "role", "can_paint", "can_filter", "alert_codes", "alert_label",
                                            "description", "multi")} | {"categories": cats})
    return {"dimensions": out_dims, "points": points, "total": len(points), "comms_window_seconds": window,
            "due_soon_days": ctx["due_soon_days"]}


# ── Vistas guardadas ──────────────────────────────────────────────────

def list_views(conn: psycopg.Connection, tenant_id: str) -> list[dict]:
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute("SELECT id, name, config, created_by, created_at FROM map_view ORDER BY lower(name)")
                return [{"id": str(r[0]), "name": r[1], "config": r[2], "created_by": r[3], "created_at": r[4].isoformat()}
                        for r in cur.fetchall()]


def save_view(conn: psycopg.Connection, tenant_id: str, name: str, config: dict, created_by: str) -> dict:
    name = (name or "").strip()
    if not name:
        raise InvalidFormError("Ponga un nombre a la vista")
    allowed = {"paint", "size", "filters", "layers"}
    if not isinstance(config, dict) or set(config) - allowed:
        raise InvalidFormError("Configuración de vista inválida")
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute("SELECT 1 FROM map_view WHERE lower(btrim(name)) = lower(%s)", (name,))
                if cur.fetchone():
                    raise svc.AssetConflictError(f"Ya existe una vista llamada {name!r}")
                cur.execute("INSERT INTO map_view (tenant_id, name, config, created_by) VALUES (%s, %s, %s, %s) RETURNING id",
                            (tenant_id, name, Json(config), created_by))
                return {"id": str(cur.fetchone()[0]), "name": name, "config": config}


def delete_view(conn: psycopg.Connection, tenant_id: str, view_id: str) -> dict:
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute("DELETE FROM map_view WHERE id = %s", (view_id,))
                if cur.rowcount == 0:
                    raise svc.AssetNotFoundError("No existe esa vista")
    return {"deleted": view_id}
