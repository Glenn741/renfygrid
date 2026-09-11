"""Retención histórica configurable por tenant (F12, Sprint 10) --
`tenant.config` (jsonb, ya existía desde 0001_init.sql como "overrides
puntuales por tenant") trae `raw_reading_retention_days` /
`validated_reading_retention_days`.

Fail-safe explícito: un tenant SIN retención configurada no pierde datos --
este job nunca borra por un default adivinado (ver
docs/07-requisitos-no-funcionales, "mínimo sugerido: 5 años" es una
sugerencia de negocio, no un valor que este código deba asumir solo).
Borrar historial es una operación destructiva; se necesita una decisión
explícita del tenant, nunca un default silencioso.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "services" / "common"))

import psycopg  # noqa: E402

from renmeter_common.db import tenant_scope  # noqa: E402


def tenants_with_retention(conn: psycopg.Connection) -> list[dict]:
    """Solo tenants que de verdad configuraron un valor -- el resto queda
    afuera, no se les aplica ningun retention por defecto."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id, config->>'raw_reading_retention_days', config->>'validated_reading_retention_days' "
            "FROM tenant WHERE config ? 'raw_reading_retention_days' OR config ? 'validated_reading_retention_days'"
        )
        return [
            {
                "tenant_id": str(row[0]),
                "raw_reading_retention_days": int(row[1]) if row[1] is not None else None,
                "validated_reading_retention_days": int(row[2]) if row[2] is not None else None,
            }
            for row in cur.fetchall()
        ]


def prune_tenant(conn: psycopg.Connection, tenant_id: str, raw_reading_days: int | None, validated_reading_days: int | None) -> dict:
    deleted = {"raw_reading": 0, "validated_reading": 0}
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                if raw_reading_days is not None:
                    cur.execute(
                        "DELETE FROM raw_reading WHERE tenant_id = %s AND \"timestamp\" < now() - (%s || ' days')::interval",
                        (tenant_id, raw_reading_days),
                    )
                    deleted["raw_reading"] = cur.rowcount
                if validated_reading_days is not None:
                    cur.execute(
                        "DELETE FROM validated_reading WHERE tenant_id = %s AND \"timestamp\" < now() - (%s || ' days')::interval",
                        (tenant_id, validated_reading_days),
                    )
                    deleted["validated_reading"] = cur.rowcount
    return deleted


def run_retention(dsn: str) -> dict[str, dict]:
    results = {}
    with psycopg.connect(dsn, autocommit=True) as conn:
        for tenant in tenants_with_retention(conn):
            results[tenant["tenant_id"]] = prune_tenant(
                conn, tenant["tenant_id"], tenant["raw_reading_retention_days"], tenant["validated_reading_retention_days"]
            )
    return results


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dsn", required=True)
    args = parser.parse_args()
    for tenant_id, deleted in run_retention(args.dsn).items():
        print(f"{tenant_id}: {deleted}")
