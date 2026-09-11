"""Verificacion end-to-end real del panel de Gestion de Consumos (Sprint
C11-6, benchmark real: docs/05-ejecucion.md) -- por HTTP real (FastAPI
TestClient), Postgres real.

Que prueba, en espanol llano, con datos reales (nunca hardcodeados):
  1. `GET /consumption/summary`: 1 consumo `ok` + 1 `under_review` (con su
     orden real de relectura en `meter_event`, F23) + 1 `resolved`
     preexistente -- confirma `total_processed=3`, `anomaly_rate_pct≈33.3`,
     `billing_ready_pct≈66.7`, `orders_by_action` trae la orden real.
  2. `GET /consumption/orders`: la orden real de relectura aparece con su
     periodo/valor/cuenta reales.
  3. `POST /consumption/resolve` sobre el consumo `under_review` real ->
     200; el resumen despues confirma `under_review=0`, `resolved=2`,
     `anomaly_rate_pct=0.0` -- nunca se adivina, se vuelve a leer de BD.
  4. Resolver DE NUEVO el mismo periodo (ya no esta `under_review`) -> 404,
     no un 200 falso.

Uso:
    python verify_consumption_summary_end_to_end.py "postgresql://renfygrid_app:renfygrid_app_dev_only@localhost:5455/renfygrid"
"""

from __future__ import annotations

import os
import sys
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import psycopg  # noqa: E402
from psycopg.types.range import Range  # noqa: E402

from renmeter_common.auth import create_token  # noqa: E402
from renmeter_common.db import tenant_scope  # noqa: E402

JWT_SECRET = "e2e-c11-6-secret"
ORDER_SIGNING_SECRET = "e2e-c11-6-order-secret"


def run(dsn: str) -> int:
    os.environ["RENFYGRID_DSN"] = dsn
    os.environ["RENFYGRID_JWT_SECRET"] = JWT_SECRET
    os.environ["RENFYGRID_ORDER_SIGNING_SECRET"] = ORDER_SIGNING_SECRET

    import main
    from fastapi.testclient import TestClient

    client = TestClient(main.app)

    with psycopg.connect(dsn, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO tenant (name) VALUES (%s) RETURNING id", ("E2E Consumption Summary Sprint C11-6",))
            (tenant_id,) = cur.fetchone()
            tenant_id = str(tenant_id)

        try:
            meter_id = None
            period_ok = Range(date(2026, 7, 1), date(2026, 8, 1), bounds="[)")
            period_review = Range(date(2026, 8, 1), date(2026, 9, 1), bounds="[)")
            period_resolved = Range(date(2026, 6, 1), date(2026, 7, 1), bounds="[)")

            with conn.transaction():
                with tenant_scope(conn, tenant_id):
                    with conn.cursor() as cur:
                        cur.execute(
                            "INSERT INTO meter (tenant_id, account_number, serial_number, brand, protocol) "
                            "VALUES (%s, 'ACC-CONSUM', 'SER-CONSUM', 'test-brand', 'DLMS_COSEM') RETURNING id",
                            (tenant_id,),
                        )
                        (meter_id,) = cur.fetchone()
                        meter_id = str(meter_id)

                        cur.execute(
                            "INSERT INTO consumption (tenant_id, meter_id, period, value, anomaly_status) "
                            "VALUES (%s, %s, %s, 500, 'ok')",
                            (tenant_id, meter_id, period_ok),
                        )
                        cur.execute(
                            "INSERT INTO consumption (tenant_id, meter_id, period, value, anomaly_status) "
                            "VALUES (%s, %s, %s, 900, 'resolved')",
                            (tenant_id, meter_id, period_resolved),
                        )
                        cur.execute(
                            "INSERT INTO consumption (tenant_id, meter_id, period, value, anomaly_status) "
                            "VALUES (%s, %s, %s, 5000, 'under_review') RETURNING id",
                            (tenant_id, meter_id, period_review),
                        )
                        (consumption_id,) = cur.fetchone()
                        cur.execute(
                            "INSERT INTO meter_event (tenant_id, meter_id, type, severity, consumption_id, \"timestamp\") "
                            "VALUES (%s, %s, 'reread_order', 'warning', %s, %s)",
                            (tenant_id, meter_id, consumption_id, datetime.now(timezone.utc)),
                        )

            token = create_token({"tenant_id": tenant_id, "role": "supervisor", "email": "ana@renfygrid.demo"}, JWT_SECRET)
            headers = {"Authorization": f"Bearer {token}"}

            summary = client.get("/consumption/summary", headers=headers).json()
            print(f"GET /consumption/summary: {summary}")
            ok_summary = (
                summary["total_processed"] == 3
                and abs(summary["anomaly_rate_pct"] - 33.3) < 0.5
                and abs(summary["billing_ready_pct"] - 66.7) < 0.5
                and summary["orders_by_action"].get("reread_order") == 1
            )

            orders = client.get("/consumption/orders", headers=headers).json()
            print(f"GET /consumption/orders: {orders}")
            ok_orders = len(orders) == 1 and orders[0]["action"] == "reread_order" and orders[0]["value"] == 5000.0

            resolve_resp = client.post(
                "/consumption/resolve", headers=headers,
                json={
                    "meter_id": meter_id, "period_start": "2026-08-01", "period_end": "2026-09-01",
                    "notes": "Relectura confirmo el consumo real, se factura tal cual",
                },
            )
            print(f"POST /consumption/resolve: {resolve_resp.status_code}")
            ok_resolve = resolve_resp.status_code == 200

            summary_after = client.get("/consumption/summary", headers=headers).json()
            print(f"GET /consumption/summary (tras resolver): {summary_after}")
            ok_summary_after = (
                summary_after["by_status"].get("under_review", 0) == 0
                and summary_after["by_status"].get("resolved") == 2
                and summary_after["anomaly_rate_pct"] == 0.0
            )

            resolve_again = client.post(
                "/consumption/resolve", headers=headers,
                json={"meter_id": meter_id, "period_start": "2026-08-01", "period_end": "2026-09-01", "notes": "x"},
            )
            print(f"POST /consumption/resolve otra vez: {resolve_again.status_code}")
            ok_no_double_resolve = resolve_again.status_code == 404

            ok = ok_summary and ok_orders and ok_resolve and ok_summary_after and ok_no_double_resolve
            print("SPRINT C11-6 CONSUMPTION PANEL E2E OK" if ok else "SPRINT C11-6 CONSUMPTION PANEL E2E FALLA")
            return 0 if ok else 1
        finally:
            with conn.transaction():
                with tenant_scope(conn, tenant_id):
                    with conn.cursor() as cur:
                        cur.execute("DELETE FROM meter_event WHERE tenant_id = %s", (tenant_id,))
                        cur.execute("DELETE FROM consumption WHERE tenant_id = %s", (tenant_id,))
                        cur.execute("DELETE FROM meter WHERE tenant_id = %s", (tenant_id,))
            with conn.cursor() as cur:
                cur.execute("DELETE FROM tenant WHERE id = %s", (tenant_id,))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    sys.exit(run(sys.argv[1]))
