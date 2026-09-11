"""Verificacion end-to-end real de F25 (preparacion de datos para
facturacion), Sprint 10 -- via `fastapi.testclient.TestClient` + Postgres
real.

Que prueba, en espanol llano:
  1. Un medidor con un consumo `anomaly_status='ok'` -- aparece en el CSV.
  2. Otro con `anomaly_status='under_review'` -- NO aparece (regla de
     negocio: no se factura un consumo bajo revision sin resolver).

Uso:
    python verify_billing_export_end_to_end.py "postgresql://renfygrid_app:renfygrid_app_dev_only@localhost:5455/renfygrid"
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import psycopg  # noqa: E402

from renmeter_common.auth import create_token  # noqa: E402
from renmeter_common.db import tenant_scope  # noqa: E402

JWT_SECRET = "e2e-billing-export-secret"
ORDER_SIGNING_SECRET = "e2e-billing-export-order-secret"


def run(dsn: str) -> int:
    os.environ["RENFYGRID_DSN"] = dsn
    os.environ["RENFYGRID_JWT_SECRET"] = JWT_SECRET
    os.environ["RENFYGRID_ORDER_SIGNING_SECRET"] = ORDER_SIGNING_SECRET

    import main
    from fastapi.testclient import TestClient

    client = TestClient(main.app)

    with psycopg.connect(dsn, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO tenant (name) VALUES (%s) RETURNING id", ("E2E Billing Export Sprint10",))
            (tenant_id,) = cur.fetchone()
            tenant_id = str(tenant_id)

        try:
            with conn.transaction():
                with tenant_scope(conn, tenant_id):
                    with conn.cursor() as cur:
                        cur.execute(
                            "INSERT INTO meter (tenant_id, account_number, serial_number, brand, protocol) "
                            "VALUES (%s, 'ACC-OK', 'SER-OK', 'test-brand', 'DLMS_COSEM') RETURNING id",
                            (tenant_id,),
                        )
                        (meter_ok_id,) = cur.fetchone()
                        cur.execute(
                            "INSERT INTO meter (tenant_id, account_number, serial_number, brand, protocol) "
                            "VALUES (%s, 'ACC-REVIEW', 'SER-REVIEW', 'test-brand', 'DLMS_COSEM') RETURNING id",
                            (tenant_id,),
                        )
                        (meter_review_id,) = cur.fetchone()

                        cur.execute(
                            "INSERT INTO consumption (tenant_id, meter_id, period, value, anomaly_status) "
                            "VALUES (%s, %s, daterange('2026-09-01','2026-10-01','[)'), 500, 'ok')",
                            (tenant_id, meter_ok_id),
                        )
                        cur.execute(
                            "INSERT INTO consumption (tenant_id, meter_id, period, value, anomaly_status) "
                            "VALUES (%s, %s, daterange('2026-09-01','2026-10-01','[)'), 5000, 'under_review')",
                            (tenant_id, meter_review_id),
                        )

            token = create_token({"tenant_id": tenant_id, "role": "operator"}, JWT_SECRET)
            resp = client.get(
                "/billing-export?period_start=2026-09-01&period_end=2026-10-01",
                headers={"Authorization": f"Bearer {token}"},
            )
            print(f"GET /billing-export: {resp.status_code}")
            print(resp.text)

            ok = (
                resp.status_code == 200
                and "ACC-OK" in resp.text
                and "ACC-REVIEW" not in resp.text
                and "500.0" in resp.text
            )
            print("F25 OK -- CSV excluye lo under_review" if ok else "F25 FALLA")
            return 0 if ok else 1
        finally:
            with conn.transaction():
                with tenant_scope(conn, tenant_id):
                    with conn.cursor() as cur:
                        cur.execute("DELETE FROM consumption WHERE tenant_id = %s", (tenant_id,))
                        cur.execute("DELETE FROM meter WHERE tenant_id = %s", (tenant_id,))
            with conn.cursor() as cur:
                cur.execute("DELETE FROM tenant WHERE id = %s", (tenant_id,))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    sys.exit(run(sys.argv[1]))
