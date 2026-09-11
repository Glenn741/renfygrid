"""Editor de reglas VEE (F50, Sprint C3) -- CRUD real sobre `vee_rule` desde
el Portal Web, en vez de SQL directo (unico camino hasta ahora). No inventa
un mecanismo de versionado nuevo: usa el que ya existe
(`valid_from`/`valid_to`/`is_active`, docs/03-diseno.md SS2).

A diferencia de `control_approval_level` (una fila activa por
`(tenant_id, order_type)`), una regla VEE no tiene una clave de version
unica -- puede haber varias reglas `range` activas a la vez para distintos
canales del mismo tenant (`params.channel` las distingue, no algo que la BD
pueda validar solo). Por eso `create_vee_rule` NUNCA cierra otra fila sola:
el operador desactiva la vieja el mismo si corresponde (`deactivate_vee_rule`),
en vez de que el sistema adivine cual reemplaza a cual.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))

import psycopg  # noqa: E402

from renmeter_common.db import tenant_scope  # noqa: E402


def list_vee_rules(conn: psycopg.Connection, tenant_id: str, active_only: bool = True) -> list[dict]:
    clause = "AND is_active AND valid_to IS NULL" if active_only else ""
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT id, type, params, priority, is_active, version, valid_from, valid_to "
                    f"FROM vee_rule WHERE tenant_id = %s {clause} ORDER BY type, priority",
                    (tenant_id,),
                )
                return [
                    {
                        "id": str(row[0]), "type": row[1], "params": row[2], "priority": row[3],
                        "is_active": row[4], "version": row[5],
                        "valid_from": row[6].isoformat() if row[6] else None,
                        "valid_to": row[7].isoformat() if row[7] else None,
                    }
                    for row in cur.fetchall()
                ]


def create_vee_rule(
    conn: psycopg.Connection, tenant_id: str, rule_type: str, params: dict[str, Any], priority: int = 100
) -> str:
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO vee_rule (tenant_id, type, params, priority) VALUES (%s, %s, %s, %s) RETURNING id",
                    (tenant_id, rule_type, psycopg.types.json.Json(params), priority),
                )
                (rule_id,) = cur.fetchone()
                return str(rule_id)


class RuleNotFoundError(LookupError):
    """No existe esa regla para este tenant."""


def deactivate_vee_rule(conn: psycopg.Connection, tenant_id: str, rule_id: str) -> None:
    """Cierra la regla (`valid_to = now()`, `is_active = false`) -- nunca se
    borra (mismo principio de trazabilidad que el resto de la configuracion
    versionada)."""
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE vee_rule SET is_active = false, valid_to = now() "
                    "WHERE id = %s AND tenant_id = %s",
                    (rule_id, tenant_id),
                )
                if cur.rowcount == 0:
                    raise RuleNotFoundError(f"No existe vee_rule {rule_id} para este tenant")
