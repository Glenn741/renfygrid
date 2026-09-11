"""Editor de reglas de anomalia de consumo (F50, Sprint C3) -- mismo
principio que `vee-engine/vee_rules_admin.py`: `consumption_anomaly_rule`
tampoco tiene una clave de version unica (puede haber varias reglas de
desviacion activas con distinto umbral, ver `consumption_engine.detect_deviation`
-- la mas estricta gana), asi que crear una nueva nunca cierra otra sola.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))

import psycopg  # noqa: E402

from renmeter_common.db import tenant_scope  # noqa: E402


def list_consumption_anomaly_rules(conn: psycopg.Connection, tenant_id: str, active_only: bool = True) -> list[dict]:
    clause = "AND is_active AND valid_to IS NULL" if active_only else ""
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT id, condition, action, is_active, version, valid_from, valid_to "
                    f"FROM consumption_anomaly_rule WHERE tenant_id = %s {clause} ORDER BY valid_from DESC",
                    (tenant_id,),
                )
                return [
                    {
                        "id": str(row[0]), "condition": row[1], "action": row[2], "is_active": row[3],
                        "version": row[4],
                        "valid_from": row[5].isoformat() if row[5] else None,
                        "valid_to": row[6].isoformat() if row[6] else None,
                    }
                    for row in cur.fetchall()
                ]


def create_consumption_anomaly_rule(
    conn: psycopg.Connection, tenant_id: str, condition: dict[str, Any], action: str
) -> str:
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO consumption_anomaly_rule (tenant_id, condition, action) VALUES (%s, %s, %s) RETURNING id",
                    (tenant_id, psycopg.types.json.Json(condition), action),
                )
                (rule_id,) = cur.fetchone()
                return str(rule_id)


class RuleNotFoundError(LookupError):
    """No existe esa regla para este tenant."""


def deactivate_consumption_anomaly_rule(conn: psycopg.Connection, tenant_id: str, rule_id: str) -> None:
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE consumption_anomaly_rule SET is_active = false, valid_to = now() "
                    "WHERE id = %s AND tenant_id = %s",
                    (rule_id, tenant_id),
                )
                if cur.rowcount == 0:
                    raise RuleNotFoundError(f"No existe consumption_anomaly_rule {rule_id} para este tenant")
