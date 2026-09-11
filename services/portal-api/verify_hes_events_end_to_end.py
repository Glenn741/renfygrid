"""Verificacion end-to-end real de HES/Ingesta -- eventos/alarmas + cola de
reintentos (Sprint C11-4, sobre el mismo benchmark real que C11-3 hizo para
VEE): un HES de referencia siempre tiene "alarm management" + "communication
statistics" + "gap reconciliation" visibles -- F05 (alarmas), F09
(auditoria de comunicacion) y F08 (cola de reintentos, Sprint C11) ya
estaban construidos en el backend, pero invisibles en el Portal.

Que prueba, en espanol llano, con filas reales (nunca hardcodeadas -- las
mismas que F05/F08/F09 ya escriben en produccion):
  1. `GET /meters/event-summary`: 1 alarma critica real + 2 comunicaciones
     exitosas + 1 fallida reales + 1 medidor real en la cola de reintentos
     -- confirma `alarms_24h=1`, `critical_alarms_24h=1`,
     `comm_failures_24h=1`, `comm_success_rate_24h≈66.7`,
     `meters_in_retry_queue=1`.
  2. `GET /meters/events`: las 4 filas reales aparecen con marca/modelo/
     concentrador; filtrado por `event_type=meter_alarm` trae solo la 1.
  3. `GET /meters/retry-queue`: el medidor real en backoff aparece con su
     `failure_count`/`last_error` reales.

Uso:
    python verify_hes_events_end_to_end.py "postgresql://renfygrid_app:renfygrid_app_dev_only@localhost:5455/renfygrid"
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "hes-adapter-dlms"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))

import psycopg  # noqa: E402

from meter_registry import link_meter_to_gateway, register_gateway, register_meter  # noqa: E402
from renmeter_common.auth import create_token  # noqa: E402
from renmeter_common.db import tenant_scope  # noqa: E402

JWT_SECRET = "e2e-hes-events-secret"
ORDER_SIGNING_SECRET = "e2e-hes-events-order-secret"


def run(dsn: str) -> int:
    os.environ["RENFYGRID_DSN"] = dsn
    os.environ["RENFYGRID_JWT_SECRET"] = JWT_SECRET
    os.environ["RENFYGRID_ORDER_SIGNING_SECRET"] = ORDER_SIGNING_SECRET

    import main
    from fastapi.testclient import TestClient

    client = TestClient(main.app)

    with psycopg.connect(dsn, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO tenant (name) VALUES (%s) RETURNING id", ("E2E HES Events Sprint C11-4",))
            (tenant_id,) = cur.fetchone()
            tenant_id = str(tenant_id)

        try:
            gateway_id = register_gateway(conn, tenant_id, "GW-Events", "TCP", {"host": "127.0.0.1", "port": 1})
            meter_id = register_meter(conn, tenant_id, "ACC-EVENTS", "SER-EVENTS", "BrandE", "DLMS_COSEM", model="ModelE")
            link_meter_to_gateway(conn, tenant_id, meter_id, gateway_id, server_address=1)

            now = datetime.now(timezone.utc)
            with conn.transaction():
                with tenant_scope(conn, tenant_id):
                    with conn.cursor() as cur:
                        cur.execute(
                            "INSERT INTO meter_event (tenant_id, meter_id, type, severity, detail, \"timestamp\") "
                            "VALUES (%s, %s, 'meter_alarm', 'critical', %s, %s)",
                            (tenant_id, meter_id, psycopg.types.json.Json({"event_code": 7, "severity_code": 2}), now),
                        )
                        cur.execute(
                            "INSERT INTO meter_event (tenant_id, meter_id, type, severity, detail, \"timestamp\") VALUES "
                            "(%s, %s, 'communication_success', 'info', %s, %s), "
                            "(%s, %s, 'communication_success', 'info', %s, %s), "
                            "(%s, %s, 'communication_failure', 'warning', %s, %s)",
                            (
                                tenant_id, meter_id, psycopg.types.json.Json({"operation": "poller_read"}), now,
                                tenant_id, meter_id, psycopg.types.json.Json({"operation": "poller_read"}), now,
                                tenant_id, meter_id, psycopg.types.json.Json({"operation": "poller_read", "error": "timeout"}), now,
                            ),
                        )
                        cur.execute(
                            "INSERT INTO poller_retry_queue (tenant_id, meter_id, failure_count, next_retry_at, last_error) "
                            "VALUES (%s, %s, 2, %s, 'ConnectionRefusedError')",
                            (tenant_id, meter_id, now + timedelta(hours=1)),
                        )

            token = create_token({"tenant_id": tenant_id, "role": "supervisor", "email": "ana@renfygrid.demo"}, JWT_SECRET)
            headers = {"Authorization": f"Bearer {token}"}

            summary = client.get("/meters/event-summary", headers=headers).json()
            print(f"GET /meters/event-summary: {summary}")
            ok_summary = (
                summary["alarms_24h"] == 1 and summary["critical_alarms_24h"] == 1
                and summary["comm_failures_24h"] == 1
                and abs(summary["comm_success_rate_24h"] - 66.7) < 0.5
                and summary["meters_in_retry_queue"] == 1
            )

            events = client.get("/meters/events", headers=headers).json()
            print(f"GET /meters/events: {len(events)} filas, primera: {events[0] if events else None}")
            ok_events = len(events) == 4 and all(row["gateway_name"] == "GW-Events" for row in events)

            alarms_only = client.get("/meters/events?event_type=meter_alarm", headers=headers).json()
            print(f"GET /meters/events?event_type=meter_alarm: {alarms_only}")
            ok_filtered = len(alarms_only) == 1 and alarms_only[0]["severity"] == "critical"

            retry_queue = client.get("/meters/retry-queue", headers=headers).json()
            print(f"GET /meters/retry-queue: {retry_queue}")
            ok_retry_queue = (
                len(retry_queue) == 1 and retry_queue[0]["failure_count"] == 2
                and retry_queue[0]["last_error"] == "ConnectionRefusedError"
            )

            ok = ok_summary and ok_events and ok_filtered and ok_retry_queue
            print("SPRINT C11-4 HES EVENTS E2E OK" if ok else "SPRINT C11-4 HES EVENTS E2E FALLA")
            return 0 if ok else 1
        finally:
            with conn.transaction():
                with tenant_scope(conn, tenant_id):
                    with conn.cursor() as cur:
                        cur.execute("DELETE FROM poller_retry_queue WHERE tenant_id = %s", (tenant_id,))
                        cur.execute("DELETE FROM meter_event WHERE tenant_id = %s", (tenant_id,))
                        cur.execute("DELETE FROM meter_gateway WHERE meter_id IN (SELECT id FROM meter WHERE tenant_id = %s)", (tenant_id,))
                        cur.execute("DELETE FROM meter WHERE tenant_id = %s", (tenant_id,))
                        cur.execute("DELETE FROM gateway WHERE tenant_id = %s", (tenant_id,))
            with conn.cursor() as cur:
                cur.execute("DELETE FROM tenant WHERE id = %s", (tenant_id,))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    sys.exit(run(sys.argv[1]))
