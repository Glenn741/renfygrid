"""Auditoria de comunicacion con dispositivos (F09, Sprint 9) -- cada
intento real de hablar con un medidor/concentrador (lectura programada,
bajo demanda, o accion de control) deja una fila en `meter_event`, exitoso
o no. Reusa la tabla existente (ya usada para F05 eventos/alarmas y F23
ordenes) en vez de crear una nueva -- `detail` (migracion 0008) es lo que
la diferencia de un evento de negocio real del medidor.
"""

from __future__ import annotations

import sys
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))

import psycopg  # noqa: E402

from renmeter_common.db import tenant_scope  # noqa: E402


def log_communication(
    conn: psycopg.Connection,
    tenant_id: str,
    meter_id: str,
    operation: str,
    success: bool,
    duration_ms: float,
    error: str | None = None,
    requested_by: str | None = None,
) -> None:
    severity = "info" if success else "warning"
    event_type = "communication_success" if success else "communication_failure"
    detail = {"operation": operation, "duration_ms": duration_ms, "error": error}
    if requested_by is not None:
        # Sprint C5 (G1/G3, `06-benchmark-e2e-y-brechas.md`): quien pidio
        # esto -- `cis:<email>`/`portal:<email>` (auth_dependency.py) o
        # `system:<que>` para lo que dispara el propio backend (poller). Sin
        # este dato, `service_orders.py` no puede distinguir una lectura que
        # pidio el CIS de una que pidio un operador desde el Portal.
        detail["requested_by"] = requested_by
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO meter_event (tenant_id, meter_id, type, severity, detail) "
                    "VALUES (%s, %s, %s, %s, %s)",
                    (tenant_id, meter_id, event_type, severity, psycopg.types.json.Json(detail)),
                )


@contextmanager
def audited_communication(
    conn: psycopg.Connection, tenant_id: str, meter_id: str, operation: str, requested_by: str | None = None
) -> Iterator[None]:
    """Envuelve un bloque de comunicacion real con un medidor y deja la
    auditoria sola, exitosa o no, sin que el llamador tenga que acordarse
    de hacerlo en cada branch (ver `poller.py`/`on_demand_reader.py`)."""
    start = time.monotonic()
    try:
        yield
    except Exception as exc:
        log_communication(conn, tenant_id, meter_id, operation, success=False, duration_ms=(time.monotonic() - start) * 1000, error=str(exc), requested_by=requested_by)
        raise
    else:
        log_communication(conn, tenant_id, meter_id, operation, success=True, duration_ms=(time.monotonic() - start) * 1000, requested_by=requested_by)
