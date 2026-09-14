"""Tablero general -- Nivel 1 (F48, Sprint C1): un conteo por etapa del
pipeline, cada uno pensado para responder "¿hay algo que atender?", no para
mostrar el dato crudo (patrón exception-first, ver
docs/02-arquitectura-general.md SS9).

Pulido de usabilidad (2026-09-14, a pedido del usuario -- "la navegacion
dentro de cada menu no se ve intuitiva"): el tablero solo cubria los 4
modulos de Track A, dejando los 4 de Track B (Balance de Red, Gemelo
Digital, Modelado Hidraulico, Mantenimiento) invisibles desde la pantalla
de entrada -- un usuario nuevo no tenia forma de saber que existian salvo
por el sidebar. Se agregan 3 conteos reales mas (no los 4: Modelado
Hidraulico no tiene una nocion de "excepcion pendiente" propia todavia --
una simulacion falla o no falla al pedirla, no queda una cola pendiente
de revisar -- forzar un tile ahi violaria el patron exception-first en
vez de servirlo).
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "network-balance"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "digital-twin"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "maintenance"))

import psycopg  # noqa: E402

from balance_service import balance_summary  # noqa: E402
from asset_service import list_assets  # noqa: E402
from order_service import list_orders  # noqa: E402
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

    balance = balance_summary(conn, tenant_id)
    assets_out_of_service = sum(1 for a in list_assets(conn, tenant_id) if a["status"] == "out_of_service")
    orders_pending = len(list_orders(conn, tenant_id, status="generated"))

    return {
        "hes": {
            "meters_total": len(ingestion["meters"]),
            "meters_stale": len(ingestion["alerts"]),
        },
        "vee": {"invalid_pending": vee_invalid_pending},
        "consumption": {"under_review": consumption_under_review},
        "control": {"pending_approval": control_pending_approval},
        "network_balance": {"zones_exceeding_threshold": balance["zones_exceeding_threshold"]},
        "digital_twin": {"assets_out_of_service": assets_out_of_service},
        "maintenance": {"orders_pending": orders_pending},
    }
