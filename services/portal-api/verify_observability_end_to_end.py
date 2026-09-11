"""Verificacion end-to-end real de F34 (observabilidad minima), Sprint 9 --
via `fastapi.testclient.TestClient` (ASGI real) + Postgres real.

Que prueba, en espanol llano:
  1. Un medidor con una lectura reciente (hace 1 minuto) -- no aparece
     como caido con un umbral de 1 hora.
  2. Un medidor con su ultima lectura hace 2 horas -- SI aparece como
     caido con ese mismo umbral de 1 hora.
  3. Un medidor sin ninguna lectura nunca -- NO aparece como caido (no hay
     con que comparar, no se adivina una alerta sin datos).
  4. Una falla de comunicacion real (F09) se refleja en
     `communication_failures_24h` del medidor correspondiente.

Uso:
    python verify_observability_end_to_end.py "postgresql://renfygrid_app:renfygrid_app_dev_only@localhost:5455/renfygrid"
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import psycopg  # noqa: E402

from renmeter_common.auth import create_token  # noqa: E402
from renmeter_common.db import tenant_scope  # noqa: E402

JWT_SECRET = "e2e-observability-secret"
ORDER_SIGNING_SECRET = "e2e-observability-order-secret"


def run(dsn: str) -> int:
    os.environ["RENFYGRID_DSN"] = dsn
    os.environ["RENFYGRID_JWT_SECRET"] = JWT_SECRET
    os.environ["RENFYGRID_ORDER_SIGNING_SECRET"] = ORDER_SIGNING_SECRET

    import main
    from fastapi.testclient import TestClient

    client = TestClient(main.app)

    with psycopg.connect(dsn, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO tenant (name) VALUES (%s) RETURNING id", ("E2E Observability Sprint9",))
            (tenant_id,) = cur.fetchone()
            tenant_id = str(tenant_id)

        try:
            now = datetime.now(timezone.utc)
            with conn.transaction():
                with tenant_scope(conn, tenant_id):
                    with conn.cursor() as cur:
                        meter_ids = {}
                        for label in ("fresco", "caido", "nunca_leido"):
                            cur.execute(
                                "INSERT INTO meter (tenant_id, account_number, serial_number, brand, protocol) "
                                "VALUES (%s, %s, %s, 'test-brand', 'DLMS_COSEM') RETURNING id",
                                (tenant_id, f"ACC-{label}", f"SER-{label}"),
                            )
                            meter_ids[label] = str(cur.fetchone()[0])

                        cur.execute(
                            "INSERT INTO raw_reading (tenant_id, meter_id, \"timestamp\", channel, value) VALUES (%s, %s, %s, 'active_energy', 100)",
                            (tenant_id, meter_ids["fresco"], now - timedelta(minutes=1)),
                        )
                        cur.execute(
                            "INSERT INTO raw_reading (tenant_id, meter_id, \"timestamp\", channel, value) VALUES (%s, %s, %s, 'active_energy', 200)",
                            (tenant_id, meter_ids["caido"], now - timedelta(hours=2)),
                        )
                        cur.execute(
                            "INSERT INTO meter_event (tenant_id, meter_id, type, severity, detail) "
                            "VALUES (%s, %s, 'communication_failure', 'warning', %s)",
                            (tenant_id, meter_ids["caido"], psycopg.types.json.Json({"operation": "poller_read", "error": "timeout simulado"})),
                        )

            token = create_token({"tenant_id": tenant_id, "role": "operator"}, JWT_SECRET)
            resp = client.get("/observability/ingestion?stale_after_seconds=3600", headers={"Authorization": f"Bearer {token}"})
            data = resp.json()
            print(f"GET /observability/ingestion: {resp.status_code}")
            for m in data["meters"]:
                print(" ", m)
            print("alerts:", data["alerts"])

            by_id = {m["meter_id"]: m for m in data["meters"]}
            alert_ids = {a["meter_id"] for a in data["alerts"]}

            ok = (
                resp.status_code == 200
                and by_id[meter_ids["fresco"]]["is_stale"] is False
                and by_id[meter_ids["caido"]]["is_stale"] is True
                and by_id[meter_ids["nunca_leido"]]["is_stale"] is False
                and meter_ids["caido"] in alert_ids
                and meter_ids["fresco"] not in alert_ids
                and meter_ids["nunca_leido"] not in alert_ids
                and by_id[meter_ids["caido"]]["communication_failures_24h"] == 1
            )
            print("F34 OK -- metricas de ingesta y alerta de caida correctas" if ok else "F34 FALLA")
            return 0 if ok else 1
        finally:
            with conn.transaction():
                with tenant_scope(conn, tenant_id):
                    with conn.cursor() as cur:
                        cur.execute("DELETE FROM meter_event WHERE tenant_id = %s", (tenant_id,))
                        cur.execute("DELETE FROM raw_reading WHERE tenant_id = %s", (tenant_id,))
                        cur.execute("DELETE FROM meter WHERE tenant_id = %s", (tenant_id,))
            with conn.cursor() as cur:
                cur.execute("DELETE FROM tenant WHERE id = %s", (tenant_id,))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    sys.exit(run(sys.argv[1]))
