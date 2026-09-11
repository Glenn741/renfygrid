"""Puerta de entrada a ordenes de control (SCR) desde el Portal/API (Sprint 8)
-- el modulo SCR "no expone API publica directa... solo se llega a el a
traves del servicio de Gestion de Consumos/CIS, nunca desde el portal web
sin pasar por esa capa de negocio" (docs/02-arquitectura-general.md SS6,
punto 4). El Portal (`services/portal-api`) llama esta funcion, nunca
`services/control` directo.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "control"))

import psycopg  # noqa: E402

from control_service import request_order  # noqa: E402


def request_control_order(
    conn: psycopg.Connection,
    tenant_id: str,
    meter_id: str,
    order_type: str,
    requested_by: str,
    justification: str,
    approval_levels: list[dict],
    override_protection: bool = False,
    override_justification: str | None = None,
) -> str:
    return request_order(
        conn, tenant_id, meter_id, order_type, requested_by, justification, approval_levels,
        override_protection, override_justification,
    )
