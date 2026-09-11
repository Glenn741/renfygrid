"""Tablero general -- Nivel 1 (F48, Sprint C1): un conteo por etapa del
pipeline, cada uno pensado para responder "¿hay algo que atender?", no para
mostrar el dato crudo (patrón exception-first, ver
docs/02-arquitectura-general.md SS9).
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))

import psycopg  # noqa: E402

from observability import ingestion_metrics  # noqa: E402
from renmeter_common.db import tenant_scope  # noqa: E402


def dashboard_overview(conn: psycopg.Connection, tenant_id: str, stale_after_seconds: int = 3600) -> dict:
    ingestion = ingestion_metrics(conn, tenant_id, stale_after_seconds)

    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT count(*) FROM validated_reading WHERE tenant_id = %s AND is_valid = false", (tenant_id,)
                )
                (vee_invalid_pending,) = cur.fetchone()
                cur.execute(
                    "SELECT count(*) FROM consumption WHERE tenant_id = %s AND anomaly_status = 'under_review'", (tenant_id,)
                )
                (consumption_under_review,) = cur.fetchone()
                cur.execute(
                    "SELECT count(*) FROM control_order WHERE tenant_id = %s AND status = 'pending_approval'", (tenant_id,)
                )
                (control_pending_approval,) = cur.fetchone()

    return {
        "hes": {
            "meters_total": len(ingestion["meters"]),
            "meters_stale": len(ingestion["alerts"]),
        },
        "vee": {"invalid_pending": vee_invalid_pending},
        "consumption": {"under_review": consumption_under_review},
        "control": {"pending_approval": control_pending_approval},
    }
