"""Catalogos de la organizacion para la interfaz (base generica, 0045).

Todo lo que la pantalla nombra sale de aqui, no del codigo: etiquetas de
codigos, terminologia, formatos del paquete, moneda y region. Resolucion:
nucleo < paquete normativo < paquete de programa < la propia organizacion
(solo terminologia). Asi un mismo RenfyGrid habla de "junta" y "ARCA" en una
organizacion ecuatoriana del programa, y de "organizacion" y "ente rector"
en una que no adopto esos paquetes.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))

import psycopg  # noqa: E402

from pack_engine import InvalidRecordError  # noqa: E402
from pack_service import active_pack_ids  # noqa: E402
from renmeter_common.db import tenant_scope  # noqa: E402

CURRENCY_KEY = "currency"
LOCALE_KEY = "locale"
KIND_ORDER = {"core": 0, "regulatory": 1, "program": 2}


def _ordered_packs(conn: psycopg.Connection, tenant_id: str) -> list[str]:
    packs = active_pack_ids(conn, tenant_id)
    with conn.cursor() as cur:
        cur.execute("SELECT id, kind FROM pack WHERE id = ANY(%s)", (packs,))
        kinds = dict(cur.fetchall())
    return sorted(packs, key=lambda p: (KIND_ORDER.get(kinds.get(p), 9), p))


def region(conn: psycopg.Connection, tenant_id: str) -> dict[str, Any]:
    """Moneda y region de la organizacion, con lo necesario para formatear.
    Sin configurar: `None` en cada parte (la interfaz lo dice; no se supone)."""
    with conn.cursor() as cur:
        cur.execute("SELECT config ->> %s, config ->> %s FROM tenant WHERE id = %s", (CURRENCY_KEY, LOCALE_KEY, tenant_id))
        cur_code, loc_code = cur.fetchone() or (None, None)
        currency = loc = None
        if cur_code:
            cur.execute("SELECT code, label, decimals FROM currency WHERE code = %s", (cur_code,))
            r = cur.fetchone()
            currency = {"code": r[0], "label": r[1], "decimals": r[2]} if r else None
        if loc_code:
            cur.execute("SELECT code, label, decimal_sep, group_sep FROM locale_option WHERE code = %s", (loc_code,))
            r = cur.fetchone()
            loc = {"code": r[0], "label": r[1], "decimal_sep": r[2], "group_sep": r[3]} if r else None
    return {"currency": currency, "locale": loc}


def set_region(conn: psycopg.Connection, tenant_id: str, currency: str, locale: str) -> dict[str, Any]:
    with conn.cursor() as cur:
        cur.execute("SELECT 1 FROM currency WHERE code = %s", (currency,))
        if cur.fetchone() is None:
            raise InvalidRecordError(f"Moneda desconocida: {currency!r}")
        cur.execute("SELECT 1 FROM locale_option WHERE code = %s", (locale,))
        if cur.fetchone() is None:
            raise InvalidRecordError(f"Región desconocida: {locale!r}")
        cur.execute("UPDATE tenant SET config = config || jsonb_build_object(%s::text, %s::text, %s::text, %s::text) WHERE id = %s",
                    (CURRENCY_KEY, currency, LOCALE_KEY, locale, tenant_id))
    return region(conn, tenant_id)


def number_separators(conn: psycopg.Connection, tenant_id: str) -> tuple[str, str] | None:
    loc = region(conn, tenant_id)["locale"]
    return (loc["decimal_sep"], loc["group_sep"]) if loc else None


def terms(conn: psycopg.Connection, tenant_id: str) -> dict[str, dict]:
    packs = _ordered_packs(conn, tenant_id)
    with conn.cursor() as cur:
        cur.execute("SELECT pack_id, key, label, plural FROM term WHERE pack_id = ANY(%s)", (packs,))
        rows = cur.fetchall()
    out: dict[str, dict] = {}
    for pack in packs:
        for p, key, label, plural in rows:
            if p == pack:
                out[key] = {"label": label, "plural": plural, "source": pack}
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute("SELECT key, label, plural FROM tenant_term WHERE tenant_id = %s", (tenant_id,))
                for key, label, plural in cur.fetchall():
                    if key in out:
                        out[key] = {"label": label, "plural": plural, "source": "organization"}
    return out


def term(conn: psycopg.Connection, tenant_id: str, key: str, plural: bool = False) -> str:
    t = terms(conn, tenant_id).get(key)
    if t is None:
        return key
    return t["plural"] if plural else t["label"]


def set_terms(conn: psycopg.Connection, tenant_id: str, actor: str, changes: dict[str, dict | None]) -> dict[str, dict]:
    """Cambia como la organizacion nombra cada termino. `None` vuelve al del
    paquete. Solo terminos que existen en el catalogo."""
    known = terms(conn, tenant_id)
    for key, value in changes.items():
        if key not in known:
            raise InvalidRecordError(f"Término desconocido: {key!r}")
        if value is not None and (not (value.get("label") or "").strip() or not (value.get("plural") or "").strip()):
            raise InvalidRecordError(f"Escriba el singular y el plural de {key!r}")
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                for key, value in changes.items():
                    if value is None:
                        cur.execute("DELETE FROM tenant_term WHERE tenant_id = %s AND key = %s", (tenant_id, key))
                    else:
                        cur.execute(
                            "INSERT INTO tenant_term (tenant_id, key, label, plural, updated_by) VALUES (%s, %s, %s, %s, %s) "
                            "ON CONFLICT (tenant_id, key) DO UPDATE SET label = EXCLUDED.label, plural = EXCLUDED.plural, "
                            "updated_by = EXCLUDED.updated_by, updated_at = now()",
                            (tenant_id, key, value["label"].strip(), value["plural"].strip(), actor))
    return terms(conn, tenant_id)


def labels(conn: psycopg.Connection, tenant_id: str) -> dict[str, dict[str, dict]]:
    packs = _ordered_packs(conn, tenant_id)
    with conn.cursor() as cur:
        cur.execute("SELECT pack_id, domain, code, sort_order, label, tone FROM code_label WHERE pack_id = ANY(%s)", (packs,))
        rows = cur.fetchall()
    out: dict[str, dict[str, dict]] = {}
    for pack in packs:
        for p, domain, code, sort, label, tone in rows:
            if p == pack:
                out.setdefault(domain, {})[code] = {"label": label, "tone": tone, "sort": sort}
    # Los tipos de activo ya tienen su catalogo (component_type): se exponen
    # desde ahi, sin copiarlos a code_label.
    with conn.cursor() as cur:
        cur.execute("SELECT code, label, coalesce(stage_order, 1000) FROM component_type WHERE pack_id = ANY(%s) "
                    "ORDER BY coalesce(stage_order, 1000), label", (packs,))
        out["asset.type"] = {code: {"label": label, "tone": None, "sort": sort} for code, label, sort in cur.fetchall()}
    return out


def forms(conn: psycopg.Connection, tenant_id: str) -> dict[str, dict]:
    packs = _ordered_packs(conn, tenant_id)
    with conn.cursor() as cur:
        cur.execute("SELECT pack_id, domain, code, title, stage_code, template_id FROM pack_form WHERE pack_id = ANY(%s)", (packs,))
        rows = cur.fetchall()
    out: dict[str, dict] = {}
    for pack in packs:
        for p, domain, code, title, stage, template in rows:
            if p == pack:
                out[domain] = {"code": code, "title": title, "stage_code": stage, "template_id": template}
    return out


def form_code(conn: psycopg.Connection, tenant_id: str, domain: str) -> str | None:
    f = forms(conn, tenant_id).get(domain)
    return f["code"] if f else None


def ui_catalog(conn: psycopg.Connection, tenant_id: str) -> dict[str, Any]:
    with conn.cursor() as cur:
        cur.execute("SELECT code, label, decimals FROM currency ORDER BY code")
        currencies = [{"code": r[0], "label": r[1], "decimals": r[2]} for r in cur.fetchall()]
        cur.execute("SELECT code, label FROM locale_option ORDER BY label")
        locales = [{"code": r[0], "label": r[1]} for r in cur.fetchall()]
    return {**region(conn, tenant_id), "terms": terms(conn, tenant_id), "labels": labels(conn, tenant_id),
            "forms": forms(conn, tenant_id), "currencies": currencies, "locales": locales}
