"""Cache de reglas de anomalia de consumo (F22), mismo patron que
`vee_rules_cache.py`: `consumption_anomaly_rule` en BD es la fuente de
verdad, un snapshot en disco es lo que `run_consumption_pass.py` lee en
caliente.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))

import psycopg  # noqa: E402

from renmeter_common.config_cache import ConfigCache  # noqa: E402
from renmeter_common.db import tenant_scope  # noqa: E402


def fetch_active_consumption_anomaly_rules(conn: psycopg.Connection, tenant_id: str) -> list[dict[str, Any]]:
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id, condition, action FROM consumption_anomaly_rule "
                    "WHERE tenant_id = %s AND is_active AND valid_to IS NULL",
                    (tenant_id,),
                )
                return [
                    {"id": str(row[0]), "condition": row[1], "action": row[2]}
                    for row in cur.fetchall()
                ]


def build_cache(snapshot_path: Path, dsn: str, tenant_id: str) -> ConfigCache:
    def fetch_fn() -> list[dict[str, Any]]:
        with psycopg.connect(dsn, autocommit=True) as conn:
            return fetch_active_consumption_anomaly_rules(conn, tenant_id)

    return ConfigCache(fetch_fn=fetch_fn, snapshot_path=snapshot_path, source_name="consumption_anomaly_rule")
