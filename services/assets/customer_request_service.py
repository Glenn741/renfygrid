"""PQR de los usuarios por frontera (Track F, Q2.5, migraciones 0051 y 0052).

Las peticiones, quejas y reclamos se clasifican con la taxonomia de la
Superservicios que trae el paquete adoptado (`CO-SSPD`): tipo de tramite,
grupo de causal (facturacion o prestacion) y detalle de causal de 3 digitos.
Cada PQR se liga a la frontera por el NIU o por el codigo de la frontera con
que llega (igual que en el reporte al SUI, donde la unidad de registro es
radicado + cuenta + causal).

Estados: abierta -> respondida -> (en recurso) -> cerrada. Una PQR abierta o en
recurso cuenta como "abierta" en el mapa.
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

from form_engine import InvalidFormError  # noqa: E402
from metering_asset_service import AssetConflictError, AssetNotFoundError  # noqa: E402
from pack_service import active_pack_ids  # noqa: E402
from renmeter_common.db import tenant_scope  # noqa: E402

STATUSES = ("open", "answered", "appealed", "closed")
OPEN_STATUSES = ("open", "appealed")


def catalog(conn: psycopg.Connection, tenant_id: str) -> dict:
    """Causales y codigos de PQR de los paquetes adoptados, filtrados por los
    sectores de la organizacion."""
    packs = active_pack_ids(conn, tenant_id)
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute("SELECT sector_code FROM tenant_sector")
                sectors = [r[0] for r in cur.fetchall()]
    with conn.cursor() as cur:
        cur.execute("SELECT pack_id, code, group_code, request_kind, label, description, sectors FROM pqr_cause "
                    "WHERE pack_id = ANY(%s) ORDER BY code", (packs,))
        causes = [{"pack_id": r[0], "code": r[1], "group_code": r[2], "request_kind": r[3], "label": r[4], "description": r[5]}
                  for r in cur.fetchall() if r[6] is None or set(r[6]) & set(sectors)]
        cur.execute("SELECT domain, code, label FROM code_label WHERE domain IN ('pqr.request_type', 'pqr.response') "
                    "AND pack_id = ANY(%s) ORDER BY domain, sort_order", (packs,))
        codes: dict[str, list[dict]] = {}
        for domain, code, lbl in cur.fetchall():
            codes.setdefault(domain, []).append({"code": code, "label": lbl})
    return {"causes": causes, "request_types": codes.get("pqr.request_type", []), "responses": codes.get("pqr.response", [])}


def _resolve_point(cur: psycopg.Cursor, point_id: str | None, account: str | None) -> str | None:
    if point_id:
        cur.execute("SELECT id::text FROM metering_point WHERE id = %s", (point_id,))
        row = cur.fetchone()
        if row is None:
            raise AssetNotFoundError("No existe esa frontera")
        return row[0]
    if account:
        cur.execute("SELECT id::text FROM metering_point WHERE lower(btrim(niu)) = lower(btrim(%s)) "
                    "OR lower(btrim(code)) = lower(btrim(%s)) LIMIT 2", (account, account))
        rows = cur.fetchall()
        if len(rows) == 1:
            return rows[0][0]
    return None


def _clean(cat: dict, data: dict, partial: bool = False) -> dict[str, Any]:
    clean: dict[str, Any] = {}
    for key in ("point_id", "account", "filing_number", "filed_on", "request_type", "cause_code", "status", "response_code",
                "responded_on", "invoice_number", "notes"):
        if key in data:
            value = data[key]
            clean[key] = (value.strip() or None) if isinstance(value, str) else value
    if not partial:
        for key, label in (("filing_number", "el número de radicado"), ("filed_on", "la fecha de radicación"),
                           ("request_type", "el tipo de trámite"), ("cause_code", "la causal")):
            if not clean.get(key):
                raise InvalidFormError(f"Falta {label}")
    if clean.get("request_type") is not None:
        types = {t["code"]: t["label"] for t in cat["request_types"]}
        value = str(clean["request_type"])
        clean["request_type"] = value if value in types else next((c for c, lbl in types.items() if lbl.lower() == value.lower()), None)
        if clean["request_type"] is None:
            raise InvalidFormError(f"Tipo de trámite desconocido: {value!r}")
    if clean.get("cause_code") is not None:
        value = str(clean["cause_code"]).split(" ")[0].strip()
        cause = next((c for c in cat["causes"] if c["code"] == value), None)
        if cause is None:
            raise InvalidFormError(f"Causal desconocida o que no aplica a su sector: {clean['cause_code']!r}")
        clean["cause_code"] = cause["code"]
        clean["pack_id"] = cause["pack_id"]
    if clean.get("status") is not None and clean["status"] not in STATUSES:
        raise InvalidFormError(f"Estado desconocido: {clean['status']!r}")
    if clean.get("response_code") is not None:
        clean["response_code"] = str(clean["response_code"])
        if clean["response_code"] not in {r["code"] for r in cat["responses"]}:
            raise InvalidFormError(f"Tipo de respuesta desconocido: {clean['response_code']!r}")
    for key in ("filed_on", "responded_on"):
        if clean.get(key) is not None and not isinstance(clean[key], date):
            try:
                clean[key] = date.fromisoformat(str(clean[key])[:10])
            except ValueError:
                raise InvalidFormError(f"{key}: fecha inválida (use AAAA-MM-DD)") from None
        if clean.get(key) is not None and clean[key] > date.today():
            raise InvalidFormError("Las fechas no pueden ser futuras")
    if clean.get("filed_on") and clean.get("responded_on") and clean["responded_on"] < clean["filed_on"]:
        raise InvalidFormError("La respuesta no puede ser anterior a la radicación")
    return clean


def _row(r: tuple, cause_labels: dict[str, str]) -> dict:
    return {"id": str(r[0]), "point_id": str(r[1]) if r[1] else None, "point_code": r[2], "account": r[3], "filing_number": r[4],
            "filed_on": r[5].isoformat(), "request_type": r[6], "cause_code": r[7], "cause_label": cause_labels.get(r[7], r[7]),
            "cause_group": r[8], "status": r[9], "response_code": r[10], "responded_on": r[11].isoformat() if r[11] else None,
            "invoice_number": r[12], "notes": r[13], "source": r[14], "created_by": r[15]}


_SELECT = ("SELECT q.id, q.point_id, p.code, q.account, q.filing_number, q.filed_on, q.request_type, q.cause_code, c.group_code, "
           "q.status, q.response_code, q.responded_on, q.invoice_number, q.notes, q.source, q.created_by FROM customer_request q "
           "JOIN pqr_cause c ON c.pack_id = q.pack_id AND c.code = q.cause_code LEFT JOIN metering_point p ON p.id = q.point_id")


def list_requests(conn: psycopg.Connection, tenant_id: str, point_id: str | None = None, status: str | None = None,
                  unlinked: bool = False) -> list[dict]:
    cat = catalog(conn, tenant_id)
    labels = {c["code"]: c["label"] for c in cat["causes"]}
    where, params = [], []
    if point_id:
        where.append("q.point_id = %s")
        params.append(point_id)
    if status == "open":
        where.append("q.status = ANY(%s)")
        params.append(list(OPEN_STATUSES))
    elif status:
        where.append("q.status = %s")
        params.append(status)
    if unlinked:
        where.append("q.point_id IS NULL")
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(_SELECT + (" WHERE " + " AND ".join(where) if where else "") + " ORDER BY q.filed_on DESC, q.filing_number",
                            params)
                return [_row(r, labels) for r in cur.fetchall()]


def _create(cur: psycopg.Cursor, tenant_id: str, cat: dict, data: dict, created_by: str, source: str) -> tuple[str, bool]:
    clean = _clean(cat, data)
    clean["point_id"] = _resolve_point(cur, clean.get("point_id"), clean.get("account"))
    clean.setdefault("status", "answered" if clean.get("response_code") and clean["response_code"] not in ("9", "10") else "open")
    cur.execute("SELECT id FROM customer_request WHERE filing_number = %s AND coalesce(account, '') = coalesce(%s, '') "
                "AND cause_code = %s", (clean["filing_number"], clean.get("account"), clean["cause_code"]))
    if cur.fetchone():
        raise AssetConflictError(f"Ya existe la PQR {clean['filing_number']} con esa causal")
    cols = list(clean) + ["tenant_id", "created_by", "source"]
    cur.execute(f"INSERT INTO customer_request ({', '.join(cols)}) VALUES ({', '.join(['%s'] * len(cols))}) RETURNING id",
                [*clean.values(), tenant_id, created_by, source])
    return str(cur.fetchone()[0]), clean["point_id"] is not None


def create_request(conn: psycopg.Connection, tenant_id: str, data: dict, created_by: str) -> dict:
    cat = catalog(conn, tenant_id)
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                request_id, linked = _create(cur, tenant_id, cat, data, created_by, "manual")
    return {"id": request_id, "linked": linked}


def update_request(conn: psycopg.Connection, tenant_id: str, request_id: str, data: dict) -> dict:
    cat = catalog(conn, tenant_id)
    clean = _clean(cat, data, partial=True)
    for key in ("filing_number", "cause_code", "pack_id", "account"):
        clean.pop(key, None)
    if not clean:
        raise InvalidFormError("Nada que cambiar")
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                if "point_id" in clean:
                    clean["point_id"] = _resolve_point(cur, clean["point_id"], None)
                sets = ", ".join(f"{k} = %s" for k in clean)
                cur.execute(f"UPDATE customer_request SET {sets}, updated_at = now() WHERE id = %s RETURNING id",
                            [*clean.values(), request_id])
                if cur.fetchone() is None:
                    raise AssetNotFoundError("No existe esa PQR")
    return {"id": request_id, **{k: (v.isoformat() if isinstance(v, date) else v) for k, v in clean.items()}}
