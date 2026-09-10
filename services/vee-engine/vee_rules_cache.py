"""Cache de reglas VEE (F19: versionado/trazabilidad), mismo patron que
`obis_mapping.py` y `renmeter_common.config_cache`: `vee_rule` en BD es la
fuente de verdad; un snapshot en disco es lo unico que el pase de
validacion (`run_vee_pass.py`) lee en caliente -- refrescado por
`refresh_vee_rules_cache.py`, un job aparte, nunca en el hot path.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))

import psycopg  # noqa: E402

from renmeter_common.config_cache import ConfigCache  # noqa: E402
from renmeter_common.db import tenant_scope  # noqa: E402


def fetch_active_vee_rules(conn: psycopg.Connection, tenant_id: str) -> list[dict[str, Any]]:
    """Solo reglas vigentes (`is_active` y `valid_to IS NULL`) -- ver el
    patron de configuracion versionada en 0001_init.sql."""
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id, type, params, priority FROM vee_rule "
                    "WHERE tenant_id = %s AND is_active AND valid_to IS NULL",
                    (tenant_id,),
                )
                return [
                    {"id": str(row[0]), "type": row[1], "params": row[2], "priority": row[3]}
                    for row in cur.fetchall()
                ]


def build_cache(snapshot_path: Path, dsn: str, tenant_id: str) -> ConfigCache:
    def fetch_fn() -> list[dict[str, Any]]:
        with psycopg.connect(dsn, autocommit=True) as conn:
            return fetch_active_vee_rules(conn, tenant_id)

    return ConfigCache(fetch_fn=fetch_fn, snapshot_path=snapshot_path, source_name="vee_rule")
