"""Bodega y EPP de la junta (Track D, D4, migracion 0038). Guia 3 de
Municipios Azules, secciones 3.9 y 3.10 y lista 7G.1.

- Articulos por categoria del paquete (quimicos, repuestos, herramientas,
  control, EPP) con su unidad y el stock minimo que fija la junta; un
  quimico puede ligarse al producto de la calculadora de dosificacion (D1.2).
- Movimientos: entradas (con vencimiento), salidas y ajustes por conteo. Una
  salida no puede dejar el stock negativo. `client_id` idempotente.
- Alertas: bajo el minimo y lotes (FIFO) vencidos o que vencen antes de la
  proxima revision 7G.1 (su frecuencia sale del paquete).
- Cruce del cloro: lo aplicado segun la bitacora 7C contra lo que salio de
  bodega de los productos desinfectantes, en el mismo periodo.
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

from pack_engine import (  # noqa: E402
    InvalidRecordError,
    chlorine_reconciliation,
    expiring_lots,
    fifo_remaining_lots,
    stock_level,
    to_base_unit,
)
from pack_service import active_pack_ids, list_checklist_templates  # noqa: E402
from renmeter_common.db import tenant_scope  # noqa: E402

UNITS = ("g", "kg", "ml", "l", "unit", "pair", "m")
REVIEW_TEMPLATE = "MA-7G1"


class WarehouseNotFoundError(LookupError):
    """Articulo, categoria o movimiento inexistente para esta junta."""


class WarehouseConflictError(ValueError):
    """Nombre repetido o salida mayor que la existencia."""


def _check_uuid(value: str | None, what: str) -> None:
    if value is None:
        return
    try:
        uuid.UUID(str(value))
    except ValueError:
        raise WarehouseNotFoundError(f"No existe {what} {value!r}") from None


def warehouse_catalog(conn: psycopg.Connection, tenant_id: str) -> dict:
    packs = active_pack_ids(conn, tenant_id)
    with conn.cursor() as cur:
        cur.execute("SELECT pack_id, code, label, should_include FROM warehouse_category WHERE pack_id = ANY(%s) "
                    "ORDER BY pack_id, sort_order", (packs,))
        cats = [{"pack_id": r[0], "code": r[1], "label": r[2], "should_include": r[3]} for r in cur.fetchall()]
        cur.execute("SELECT task, ppe, care FROM ppe_task WHERE pack_id = ANY(%s) ORDER BY pack_id, sort_order", (packs,))
        ppe = [{"task": r[0], "ppe": r[1], "care": r[2]} for r in cur.fetchall()]
    return {"categories": cats, "ppe_tasks": ppe, "units": list(UNITS)}


def create_item(conn: psycopg.Connection, tenant_id: str, name: str, category_code: str, unit: str,
                min_stock: float | None = None, chemical_product_id: str | None = None) -> dict:
    name = (name or "").strip()
    if not name:
        raise InvalidRecordError("El artículo necesita un nombre")
    if unit not in UNITS:
        raise InvalidRecordError(f"Unidad inválida: {unit!r} (válidas: {list(UNITS)})")
    if min_stock is not None and min_stock < 0:
        raise InvalidRecordError("El stock mínimo no puede ser negativo")
    cats = {c["code"]: c for c in warehouse_catalog(conn, tenant_id)["categories"]}
    if category_code not in cats:
        raise WarehouseNotFoundError(f"Categoría desconocida: {category_code!r}")
    _check_uuid(chemical_product_id, "el producto químico")
    try:
        with conn.transaction():
            with tenant_scope(conn, tenant_id):
                with conn.cursor() as cur:
                    if chemical_product_id:
                        cur.execute("SELECT 1 FROM chemical_product WHERE id = %s AND tenant_id = %s", (chemical_product_id, tenant_id))
                        if cur.fetchone() is None:
                            raise WarehouseNotFoundError(f"No existe el producto químico {chemical_product_id}")
                    cur.execute(
                        "INSERT INTO warehouse_item (tenant_id, pack_id, category_code, name, unit, min_stock, chemical_product_id) "
                        "VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id",
                        (tenant_id, cats[category_code]["pack_id"], category_code, name, unit, min_stock, chemical_product_id),
                    )
                    item_id = str(cur.fetchone()[0])
    except psycopg.errors.UniqueViolation:
        raise WarehouseConflictError(f"Ya existe un artículo llamado {name!r}") from None
    return next(i for i in list_items(conn, tenant_id, date.today(), include_inactive=True) if i["item_id"] == item_id)


def update_item(conn: psycopg.Connection, tenant_id: str, item_id: str, **fields: Any) -> dict:
    unknown = set(fields) - {"name", "min_stock", "active"}
    if unknown:
        raise InvalidRecordError(f"Campos no editables: {sorted(unknown)}")
    _check_uuid(item_id, "el artículo")
    if fields.get("min_stock") is not None and fields["min_stock"] < 0:
        raise InvalidRecordError("El stock mínimo no puede ser negativo")
    if "name" in fields:
        fields["name"] = (fields["name"] or "").strip()
        if not fields["name"]:
            raise InvalidRecordError("El artículo necesita un nombre")
    try:
        with conn.transaction():
            with tenant_scope(conn, tenant_id):
                with conn.cursor() as cur:
                    cur.execute("SELECT 1 FROM warehouse_item WHERE id = %s AND tenant_id = %s", (item_id, tenant_id))
                    if cur.fetchone() is None:
                        raise WarehouseNotFoundError(f"No existe el artículo {item_id}")
                    if fields:
                        cur.execute(f"UPDATE warehouse_item SET {', '.join(f'{k} = %s' for k in fields)} WHERE id = %s",
                                    (*fields.values(), item_id))
    except psycopg.errors.UniqueViolation:
        raise WarehouseConflictError(f"Ya existe un artículo llamado {fields.get('name')!r}") from None
    return next(i for i in list_items(conn, tenant_id, date.today(), include_inactive=True) if i["item_id"] == item_id)


def _horizon_days(conn: psycopg.Connection, tenant_id: str) -> int | None:
    t = next((t for t in list_checklist_templates(conn, tenant_id) if t["id"] == REVIEW_TEMPLATE), None)
    return t["frequency_days"] if t else None


def list_items(conn: psycopg.Connection, tenant_id: str, today: date, include_inactive: bool = False) -> list[dict]:
    horizon = _horizon_days(conn, tenant_id)
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT i.id, i.category_code, c.label, i.name, i.unit, i.min_stock, i.chemical_product_id, i.active "
                    "FROM warehouse_item i JOIN warehouse_category c ON c.pack_id = i.pack_id AND c.code = i.category_code "
                    f"WHERE i.tenant_id = %s {'' if include_inactive else 'AND i.active'} ORDER BY c.sort_order, i.name",
                    (tenant_id,),
                )
                items = cur.fetchall()
                cur.execute("SELECT item_id, kind, quantity, moved_at, expires_on FROM warehouse_movement WHERE tenant_id = %s",
                            (tenant_id,))
                moves = cur.fetchall()
    by_item: dict[str, list[dict]] = {}
    for item_id, kind, qty, at, exp in moves:
        by_item.setdefault(str(item_id), []).append({"kind": kind, "quantity": float(qty), "moved_at": at, "expires_on": exp})
    out = []
    for iid, cat, cat_label, name, unit, min_stock, chem, active in items:
        mv = by_item.get(str(iid), [])
        stock = stock_level(mv)
        ins = [m for m in mv if m["kind"] == "in" or (m["kind"] == "adjust" and m["quantity"] > 0)]
        consumed = sum(m["quantity"] for m in mv if m["kind"] == "out") - sum(m["quantity"] for m in mv
                                                                             if m["kind"] == "adjust" and m["quantity"] < 0)
        lots = fifo_remaining_lots(ins, consumed)
        expiring = expiring_lots(lots, today, horizon) if horizon else []
        out.append({
            "item_id": str(iid), "category_code": cat, "category_label": cat_label, "name": name, "unit": unit,
            "min_stock": float(min_stock) if min_stock is not None else None, "chemical_product_id": str(chem) if chem else None,
            "active": active, "stock": stock,
            "below_min": min_stock is not None and stock < float(min_stock),
            "expiring": [{"expires_on": l["expires_on"].isoformat(), "remaining": l["remaining"], "days_left": l["days_left"],
                          "expired": l["expired"]} for l in expiring],
        })
    return out


def record_movement(
    conn: psycopg.Connection, tenant_id: str, item_id: str, kind: str, quantity: float, moved_at: datetime, recorded_by: str,
    expires_on: date | None = None, reason: str | None = None, maintenance_order_id: str | None = None,
    client_id: str | None = None,
) -> dict:
    if kind not in ("in", "out", "adjust"):
        raise InvalidRecordError(f"Movimiento inválido: {kind!r} (válidos: in, out, adjust)")
    if quantity == 0 or (kind != "adjust" and quantity < 0):
        raise InvalidRecordError("La cantidad debe ser mayor que cero (el ajuste puede ser negativo)")
    if expires_on and kind != "in":
        raise InvalidRecordError("El vencimiento se registra en la entrada del lote")
    _check_uuid(item_id, "el artículo")
    _check_uuid(maintenance_order_id, "la orden de mantenimiento")
    _check_uuid(client_id, "el identificador del dispositivo")
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                if client_id:
                    cur.execute("SELECT id FROM warehouse_movement WHERE tenant_id = %s AND client_id = %s", (tenant_id, client_id))
                    row = cur.fetchone()
                    if row:
                        return {"movement_id": str(row[0]), "duplicate": True}
                cur.execute("SELECT name FROM warehouse_item WHERE id = %s AND tenant_id = %s FOR UPDATE", (item_id, tenant_id))
                if cur.fetchone() is None:
                    raise WarehouseNotFoundError(f"No existe el artículo {item_id}")
                if maintenance_order_id:
                    cur.execute("SELECT 1 FROM maintenance_order WHERE id = %s AND tenant_id = %s", (maintenance_order_id, tenant_id))
                    if cur.fetchone() is None:
                        raise WarehouseNotFoundError(f"No existe la orden {maintenance_order_id}")
                cur.execute("SELECT kind, quantity FROM warehouse_movement WHERE item_id = %s AND tenant_id = %s", (item_id, tenant_id))
                stock = stock_level([{"kind": r[0], "quantity": r[1]} for r in cur.fetchall()])
                delta = quantity if kind in ("in", "adjust") else -quantity
                if stock + delta < 0:
                    raise WarehouseConflictError(f"La salida ({quantity:g}) supera la existencia ({stock:g}); registre primero la entrada o un conteo")
                cur.execute(
                    "INSERT INTO warehouse_movement (tenant_id, item_id, kind, quantity, moved_at, expires_on, reason, "
                    "maintenance_order_id, recorded_by, client_id) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id",
                    (tenant_id, item_id, kind, quantity, moved_at, expires_on, (reason or "").strip() or None,
                     maintenance_order_id, recorded_by, client_id),
                )
                return {"movement_id": str(cur.fetchone()[0]), "duplicate": False, "stock": round(stock + delta, 3)}


def list_movements(conn: psycopg.Connection, tenant_id: str, item_id: str | None = None, limit: int = 100) -> list[dict]:
    _check_uuid(item_id, "el artículo")
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT m.id, m.item_id, i.name, i.unit, m.kind, m.quantity, m.moved_at, m.expires_on, m.reason, "
                    "m.maintenance_order_id, m.recorded_by FROM warehouse_movement m JOIN warehouse_item i ON i.id = m.item_id "
                    f"WHERE m.tenant_id = %s {'AND m.item_id = %s ' if item_id else ''}ORDER BY m.moved_at DESC, m.created_at DESC LIMIT %s",
                    (tenant_id, item_id, limit) if item_id else (tenant_id, limit),
                )
                return [{"movement_id": str(r[0]), "item_id": str(r[1]), "item_name": r[2], "unit": r[3], "kind": r[4],
                         "quantity": float(r[5]), "moved_at": r[6].isoformat(), "expires_on": r[7].isoformat() if r[7] else None,
                         "reason": r[8], "maintenance_order_id": str(r[9]) if r[9] else None, "recorded_by": r[10]}
                        for r in cur.fetchall()]


def chlorine_check(conn: psycopg.Connection, tenant_id: str, since: datetime, until: datetime) -> list[dict]:
    """Cruce por unidad base (g o ml): cloro aplicado en la bitacora 7C vs
    salidas de bodega de articulos ligados a productos desinfectantes."""
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute("SELECT chlorine_applied_unit, sum(chlorine_applied) FROM operation_log_entry "
                            "WHERE tenant_id = %s AND chlorine_applied IS NOT NULL AND logged_at >= %s AND logged_at < %s "
                            "GROUP BY 1", (tenant_id, since, until))
                applied = cur.fetchall()
                cur.execute(
                    "SELECT i.unit, sum(m.quantity) FROM warehouse_movement m JOIN warehouse_item i ON i.id = m.item_id "
                    "JOIN chemical_product p ON p.id = i.chemical_product_id "
                    "WHERE m.tenant_id = %s AND m.kind = 'out' AND p.purpose = 'disinfection' AND m.moved_at >= %s AND m.moved_at < %s "
                    "GROUP BY 1", (tenant_id, since, until))
                issued = cur.fetchall()
    totals: dict[str, dict[str, float]] = {}
    for unit, qty in applied:
        base = to_base_unit(float(qty), unit)
        totals.setdefault(base[0], {"applied": 0.0, "issued": 0.0})["applied"] += base[1]
    for unit, qty in issued:
        base = to_base_unit(float(qty), unit)
        if base:
            totals.setdefault(base[0], {"applied": 0.0, "issued": 0.0})["issued"] += base[1]
    return [{**chlorine_reconciliation(v["applied"], u, v["issued"], u), "since": since.isoformat(), "until": until.isoformat()}
            for u, v in sorted(totals.items())]
