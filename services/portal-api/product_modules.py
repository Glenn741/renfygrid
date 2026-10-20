"""Modulos del Portal y sectores de cada organizacion (Track F, Q1, migracion
0048). docs/09-multi-industria.md §4 y §5.

El menu deja de ser un literal del frontend: cada modulo es una fila de
`product_module` con su grupo, su orden, los tipos de organizacion y los
sectores que lo ven. Una organizacion ve un modulo si:

- su tipo esta en `kinds`, y
- el modulo es transversal (`sectors` NULL) o comparte un sector con ella,

salvo que `tenant_module` lo apague; un `tenant_module` encendido lo agrega
aunque no le toque por sector ("a la carte").
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))

import psycopg  # noqa: E402

from renmeter_common.db import tenant_scope  # noqa: E402


class UnknownSectorError(ValueError):
    """Sector que no existe en el catalogo."""


def list_sectors(conn: psycopg.Connection) -> list[dict]:
    with conn.cursor() as cur:
        cur.execute("SELECT code, label, icon, billing_unit, description FROM sector ORDER BY sort_order")
        return [{"code": r[0], "label": r[1], "icon": r[2], "billing_unit": r[3], "description": r[4]} for r in cur.fetchall()]


def tenant_sectors(conn: psycopg.Connection, tenant_id: str) -> list[str]:
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute("SELECT ts.sector_code FROM tenant_sector ts JOIN sector s ON s.code = ts.sector_code "
                            "ORDER BY s.sort_order")
                return [r[0] for r in cur.fetchall()]


def set_tenant_sectors(conn: psycopg.Connection, tenant_id: str, sectors: list[str]) -> list[str]:
    """Reemplaza los sectores de la organizacion (dentro de la transaccion de
    quien llama, p. ej. el alta de la organizacion)."""
    known = {s["code"] for s in list_sectors(conn)}
    unknown = sorted(set(sectors) - known)
    if unknown:
        raise UnknownSectorError(f"Sector desconocido: {', '.join(unknown)}")
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute("DELETE FROM tenant_sector WHERE tenant_id = %s", (tenant_id,))
                for code in dict.fromkeys(sectors):
                    cur.execute("INSERT INTO tenant_sector (tenant_id, sector_code) VALUES (%s, %s)", (tenant_id, code))
    return tenant_sectors(conn, tenant_id)


def modules_for(conn: psycopg.Connection, tenant_id: str, kind: str | None) -> list[dict]:
    """Modulos visibles para la organizacion, en el orden del menu."""
    sectors = tenant_sectors(conn, tenant_id)
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute("SELECT module_code, enabled FROM tenant_module")
                overrides = dict(cur.fetchall())
                cur.execute(
                    "SELECT m.code, m.path, m.label, m.icon, m.description, m.kinds, m.sectors, "
                    "g.code, g.label, g.sort_order, m.sort_order FROM product_module m "
                    "JOIN nav_group g ON g.code = m.group_code ORDER BY g.sort_order, m.sort_order")
                rows = cur.fetchall()
    out = []
    for code, path, label, icon, description, kinds, mod_sectors, group_code, group_label, group_sort, sort in rows:
        visible = (kind or "provider") in kinds and (mod_sectors is None or bool(set(mod_sectors) & set(sectors)))
        if code in overrides:
            visible = overrides[code]
        if visible:
            out.append({"code": code, "path": path, "label": label, "icon": icon, "description": description,
                        "group": {"code": group_code, "label": group_label, "sort_order": group_sort}, "sort_order": sort,
                        "sectors": mod_sectors})
    return out
