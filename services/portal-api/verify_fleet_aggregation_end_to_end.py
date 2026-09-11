"""Verificacion end-to-end real de Sprint C7 (`docs/06-benchmark-e2e-y-brechas.md`
G4/G5): flota por marca/modelo y la capa de agregacion (concentradores) --
por HTTP real (FastAPI TestClient), Postgres real.

Que prueba, en espanol llano:
  1. Dos marcas reales (BrandA/BrandB), 3 medidores: 2 de BrandA en un
     concentrador (uno reportando, otro sin lecturas -- "caido"), 1 de
     BrandB en otro concentrador (reportando).
  2. `GET /meters/fleet-summary` -- BrandA da 2 total/1 reportando (50%),
     BrandB da 1 total/1 reportando (100%).
  3. `GET /gateways` -- el concentrador de BrandA agrupa 2 medidores de esa
     sola marca; el de BrandB agrupa 1. Ambos con su tasa de exito 24h real
     (auditada en `meter_event`, F09) segun los eventos que se insertaron.
  4. `GET /observability/ingestion` -- cada medidor ahora trae su
     marca/modelo/concentrador (antes no los traia).

Uso:
    python verify_fleet_aggregation_end_to_end.py "postgresql://renfygrid_app:renfygrid_app_dev_only@localhost:5455/renfygrid"
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "hes-adapter-dlms"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import psycopg  # noqa: E402

from meter_registry import link_meter_to_gateway, register_gateway, register_meter  # noqa: E402
from renmeter_common.auth import create_token  # noqa: E402
from renmeter_common.db import tenant_scope  # noqa: E402

JWT_SECRET = "e2e-c7-secret"
ORDER_SIGNING_SECRET = "e2e-c7-order-secret"


def run(dsn: str) -> int:
    os.environ["RENFYGRID_DSN"] = dsn
    os.environ["RENFYGRID_JWT_SECRET"] = JWT_SECRET
    os.environ["RENFYGRID_ORDER_SIGNING_SECRET"] = ORDER_SIGNING_SECRET

    import main  # importado despues de fijar el entorno
    from fastapi.testclient import TestClient

    client = TestClient(main.app)

    with psycopg.connect(dsn, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO tenant (name) VALUES (%s) RETURNING id", ("E2E Fleet Aggregation Sprint C7",))
            (tenant_id,) = cur.fetchone()
            tenant_id = str(tenant_id)

        try:
            gw_a = register_gateway(conn, tenant_id, "GW-BrandA", "TCP", {"host": "127.0.0.1", "port": 1})
            gw_b = register_gateway(conn, tenant_id, "GW-BrandB", "TCP", {"host": "127.0.0.1", "port": 2})

            meter_a1 = register_meter(conn, tenant_id, "ACC-A1", "SER-A1", "BrandA", "DLMS_COSEM", model="ModelA")
            meter_a2 = register_meter(conn, tenant_id, "ACC-A2", "SER-A2", "BrandA", "DLMS_COSEM", model="ModelA")
            meter_b1 = register_meter(conn, tenant_id, "ACC-B1", "SER-B1", "BrandB", "DLMS_COSEM", model="ModelB")
            link_meter_to_gateway(conn, tenant_id, meter_a1, gw_a, server_address=1)
            link_meter_to_gateway(conn, tenant_id, meter_a2, gw_a, server_address=2)
            link_meter_to_gateway(conn, tenant_id, meter_b1, gw_b, server_address=1)

            with conn.transaction():
                with tenant_scope(conn, tenant_id):
                    with conn.cursor() as cur:
                        # meter_a1 reporta (lectura reciente + poll exitoso); meter_a2 nunca reporto.
                        cur.execute(
                            "INSERT INTO raw_reading (tenant_id, meter_id, \"timestamp\", channel, value) "
                            "VALUES (%s, %s, now(), 'active_energy', 100)",
                            (tenant_id, meter_a1),
                        )
                        cur.execute(
                            "INSERT INTO raw_reading (tenant_id, meter_id, \"timestamp\", channel, value) "
                            "VALUES (%s, %s, now(), 'active_energy', 200)",
                            (tenant_id, meter_b1),
                        )
                        # ciclos de polling reales auditados (F09): GW-BrandA con 1 exito + 1 falla (50%), GW-BrandB 100%.
                        cur.execute(
                            "INSERT INTO meter_event (tenant_id, meter_id, type, severity, detail) VALUES "
                            "(%s, %s, 'communication_success', 'info', '{\"operation\":\"poller_read\"}'), "
                            "(%s, %s, 'communication_failure', 'warning', '{\"operation\":\"poller_read\"}')",
                            (tenant_id, meter_a1, tenant_id, meter_a2),
                        )
                        cur.execute(
                            "INSERT INTO meter_event (tenant_id, meter_id, type, severity, detail) "
                            "VALUES (%s, %s, 'communication_success', 'info', '{\"operation\":\"poller_read\"}')",
                            (tenant_id, meter_b1),
                        )

            token = create_token({"tenant_id": tenant_id, "role": "supervisor", "email": "ana@renfygrid.demo"}, JWT_SECRET)
            headers = {"Authorization": f"Bearer {token}"}

            fleet = client.get("/meters/fleet-summary", headers=headers).json()
            print(f"GET /meters/fleet-summary: {fleet}")
            by_brand = {row["brand"]: row for row in fleet}
            ok_fleet = (
                by_brand["BrandA"]["total"] == 2 and by_brand["BrandA"]["reporting"] == 1
                and by_brand["BrandA"]["reporting_pct"] == 50.0
                and by_brand["BrandB"]["total"] == 1 and by_brand["BrandB"]["reporting_pct"] == 100.0
            )

            gateways = client.get("/gateways", headers=headers).json()
            print(f"GET /gateways: {gateways}")
            by_gw = {row["name"]: row for row in gateways}
            ok_gateways = (
                by_gw["GW-BrandA"]["meter_count"] == 2 and by_gw["GW-BrandA"]["brands"] == ["BrandA"]
                and by_gw["GW-BrandA"]["success_rate_24h"] == 50.0
                and by_gw["GW-BrandB"]["meter_count"] == 1 and by_gw["GW-BrandB"]["success_rate_24h"] == 100.0
            )

            ingestion = client.get("/observability/ingestion", headers=headers).json()
            meters_by_account = {m["account_number"]: m for m in ingestion["meters"]}
            print(f"GET /observability/ingestion (extendido): {meters_by_account['ACC-A1']}")
            ok_ingestion = (
                meters_by_account["ACC-A1"]["brand"] == "BrandA"
                and meters_by_account["ACC-A1"]["model"] == "ModelA"
                and meters_by_account["ACC-A1"]["gateway_name"] == "GW-BrandA"
                and meters_by_account["ACC-B1"]["gateway_name"] == "GW-BrandB"
            )

            ok = ok_fleet and ok_gateways and ok_ingestion
            print("SPRINT C7 E2E OK" if ok else "SPRINT C7 E2E FALLA")
            return 0 if ok else 1
        finally:
            with conn.transaction():
                with tenant_scope(conn, tenant_id):
                    with conn.cursor() as cur:
                        cur.execute("DELETE FROM meter_event WHERE tenant_id = %s", (tenant_id,))
                        cur.execute("DELETE FROM raw_reading WHERE tenant_id = %s", (tenant_id,))
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
