"""Editor de niveles de aprobacion de control (F50, Sprint C3).

A diferencia de `vee_rule`/`consumption_anomaly_rule`, `control_approval_level`
SI tiene una clave de version bien definida: `(tenant_id, order_type)` --
`UNIQUE (tenant_id, order_type, valid_from)` en el esquema (0001_init.sql), y
`control_engine.approval_level_for` toma la primera fila activa que matchea
ese `order_type`. Por eso `create_approval_level` SI cierra la version
anterior para ese mismo `order_type` -- dejar dos filas activas para el
mismo tipo de orden seria una condicion de carrera real (cual gana depende
del orden de filas que devuelva Postgres, no de una regla explicita).
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))

import psycopg  # noqa: E402

from renmeter_common.db import tenant_scope  # noqa: E402


def list_approval_levels(conn: psycopg.Connection, tenant_id: str, active_only: bool = True) -> list[dict]:
    clause = "AND valid_to IS NULL" if active_only else ""
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT id, order_type, requires_human_approval, min_required_role, version, valid_from, valid_to "
                    f"FROM control_approval_level WHERE tenant_id = %s {clause} ORDER BY order_type",
                    (tenant_id,),
                )
                return [
                    {
                        "id": str(row[0]), "order_type": row[1], "requires_human_approval": row[2],
                        "min_required_role": row[3], "version": row[4],
                        "valid_from": row[5].isoformat() if row[5] else None,
                        "valid_to": row[6].isoformat() if row[6] else None,
                    }
                    for row in cur.fetchall()
                ]


def create_approval_level(
    conn: psycopg.Connection, tenant_id: str, order_type: str, requires_human_approval: bool, min_required_role: str
) -> str:
    """Cierra (`valid_to = now()`) la version anterior activa para el mismo
    `order_type`, si existe, antes de crear la nueva -- mantiene la
    invariante "a lo sumo una version activa por tipo de orden" que
    `approval_level_for` asume."""
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE control_approval_level SET valid_to = now() "
                    "WHERE tenant_id = %s AND order_type = %s AND valid_to IS NULL",
                    (tenant_id, order_type),
                )
                cur.execute(
                    "INSERT INTO control_approval_level (tenant_id, order_type, requires_human_approval, min_required_role) "
                    "VALUES (%s, %s, %s, %s) RETURNING id",
                    (tenant_id, order_type, requires_human_approval, min_required_role),
                )
                (level_id,) = cur.fetchone()
                return str(level_id)
