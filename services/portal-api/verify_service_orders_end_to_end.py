"""Verificacion end-to-end real de Sprint C5 (`docs/06-benchmark-e2e-y-brechas.md`
G1-G3): la convencion de origen de la peticion, el comando de ping, y el
panel unificado de Service Orders -- todo por HTTP real (FastAPI TestClient),
Postgres real, y el simulador DLMS real.

Que prueba, en espanol llano:
  1. Un usuario `portal` (rol supervisor) y una cuenta de servicio `cis`
     (rol `integration`) hacen login real -- cada JWT lleva su propio email.
  2. Ambos hacen ping real (asociacion DLMS contra el simulador) sobre el
     mismo medidor -- ninguno de los dos puede decirle al backend quien es,
     eso lo decide el JWT.
  3. Ambos piden una orden de control (suspension) sobre medidores
     distintos -- de nuevo, sin poder mentir sobre `requested_by`.
  4. `GET /integrations/service-orders` devuelve las 4 filas (2 pings +
     2 ordenes) con el origen correcto (`CIS externo` / `Portal (operador)`)
     resuelto solo, sin que nadie lo haya escrito a mano.
  5. Un ping a un medidor sin gateway configurado da 422, no 500 ni un
     "exito" fabricado.

Uso:
    python verify_service_orders_end_to_end.py "postgresql://renfygrid_app:renfygrid_app_dev_only@localhost:5455/renfygrid"
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "hes-adapter-dlms"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))
# El propio directorio al final (mismo motivo que verify_portal_api_end_to_end.py):
# este script y hes-adapter-dlms tienen cada uno su propio "main.py".
sys.path.insert(0, str(Path(__file__).resolve().parent))

import psycopg  # noqa: E402

from meter_registry import link_meter_to_gateway, register_gateway, register_meter  # noqa: E402
from renmeter_common.db import tenant_scope  # noqa: E402
from renmeter_common.user_service import create_app_user  # noqa: E402
from simulator.dlms_simulator_server import serve_in_background  # noqa: E402

JWT_SECRET = "e2e-c5-secret"
ORDER_SIGNING_SECRET = "e2e-c5-order-secret"
HOST = "127.0.0.1"
PORT = 22888
BRAND = "test-brand-c5"
MODEL = "test-model-c5"


def run(dsn: str) -> int:
    os.environ["RENFYGRID_DSN"] = dsn
    os.environ["RENFYGRID_JWT_SECRET"] = JWT_SECRET
    os.environ["RENFYGRID_ORDER_SIGNING_SECRET"] = ORDER_SIGNING_SECRET

    serve_in_background(HOST, PORT, "1.0.1.8.0.255", 111000)
    time.sleep(0.3)

    import main  # importado ACA, despues de fijar el entorno (Settings.from_env corre al importar)
    from fastapi.testclient import TestClient

    client = TestClient(main.app)

    with psycopg.connect(dsn, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO tenant (name) VALUES (%s) RETURNING id", ("E2E Service Orders Sprint C5",))
            (tenant_id,) = cur.fetchone()
            tenant_id = str(tenant_id)

        try:
            create_app_user(conn, tenant_id, "ana@renfygrid.demo", "clave-portal-1", "supervisor")
            create_app_user(conn, tenant_id, "facturacion@empresa-cis.com", "clave-cis-1", "integration")

            gateway_id = register_gateway(
                conn, tenant_id, "Simulador E2E C5", "TCP", {"host": HOST, "port": PORT, "client_address": 16}
            )
            meter_portal_id = register_meter(conn, tenant_id, "ACC-C5-P", "SER-C5-P", BRAND, "DLMS_COSEM", model=MODEL)
            meter_cis_id = register_meter(conn, tenant_id, "ACC-C5-C", "SER-C5-C", BRAND, "DLMS_COSEM", model=MODEL)
            meter_no_gw_id = register_meter(conn, tenant_id, "ACC-C5-X", "SER-C5-X", BRAND, "DLMS_COSEM", model=MODEL)
            link_meter_to_gateway(conn, tenant_id, meter_portal_id, gateway_id, server_address=1)
            link_meter_to_gateway(conn, tenant_id, meter_cis_id, gateway_id, server_address=1)

            with conn.transaction():
                with tenant_scope(conn, tenant_id):
                    with conn.cursor() as cur:
                        cur.execute(
                            "INSERT INTO control_approval_level (tenant_id, order_type, requires_human_approval, min_required_role) "
                            "VALUES (%s, 'suspension', true, 'supervisor')",
                            (tenant_id,),
                        )

            token_portal = client.post(
                "/auth/login",
                json={"tenant_id": tenant_id, "email": "ana@renfygrid.demo", "password": "clave-portal-1"},
            ).json()["access_token"]
            token_cis = client.post(
                "/auth/login",
                json={"tenant_id": tenant_id, "email": "facturacion@empresa-cis.com", "password": "clave-cis-1"},
            ).json()["access_token"]
            headers_portal = {"Authorization": f"Bearer {token_portal}"}
            headers_cis = {"Authorization": f"Bearer {token_cis}"}

            # --- 2: ping real, ambos actores ---
            ping_portal = client.post(f"/meters/{meter_portal_id}/ping", headers=headers_portal)
            ping_cis = client.post(f"/meters/{meter_cis_id}/ping", headers=headers_cis)
            print(f"POST ping (portal): {ping_portal.status_code} {ping_portal.json()}")
            print(f"POST ping (cis): {ping_cis.status_code} {ping_cis.json()}")
            ok_ping = (
                ping_portal.status_code == 200 and ping_portal.json()["reachable"] is True
                and ping_cis.status_code == 200 and ping_cis.json()["reachable"] is True
            )

            # --- 5: ping a un medidor sin gateway -> 422, no 500 ---
            ping_no_gw = client.post(f"/meters/{meter_no_gw_id}/ping", headers=headers_portal)
            ok_no_gw = ping_no_gw.status_code == 422

            # --- 3: orden de control, ambos actores, sin poder elegir requested_by ---
            order_portal = client.post(
                "/control-orders", headers=headers_portal,
                json={"meter_id": meter_portal_id, "order_type": "suspension", "justification": "mora"},
            ).json()["order_id"]
            order_cis = client.post(
                "/control-orders", headers=headers_cis,
                json={"meter_id": meter_cis_id, "order_type": "suspension", "justification": "no pago"},
            ).json()["order_id"]

            # --- 4: panel unificado ---
            feed = client.get("/integrations/service-orders", headers=headers_portal).json()
            by_id = {row["id"]: row for row in feed}
            print(f"GET /integrations/service-orders -- {len(feed)} filas")
            for row in feed:
                print(f"  {row['kind']:16s} origin={row['origin']:20s} mode={row['mode']:11s} requested_by={row['requested_by']}")

            ok_feed = (
                by_id.get(order_portal, {}).get("origin") == "Portal (operador)"
                and by_id.get(order_portal, {}).get("requested_by") == "portal:ana@renfygrid.demo"
                and by_id.get(order_cis, {}).get("origin") == "CIS externo"
                and by_id.get(order_cis, {}).get("requested_by") == "cis:facturacion@empresa-cis.com"
                and any(r["kind"] == "ping" and r["origin"] == "Portal (operador)" for r in feed)
                and any(r["kind"] == "ping" and r["origin"] == "CIS externo" for r in feed)
            )

            ok = ok_ping and ok_no_gw and ok_feed
            print("SPRINT C5 E2E OK" if ok else "SPRINT C5 E2E FALLA")
            return 0 if ok else 1
        finally:
            # control_order_audit es append-only para renfygrid_app (migracion
            # 0007) -- igual que verify_control_end_to_end.py, limpiar esas
            # filas de prueba exige el rol admin, nunca el rol de aplicacion.
            admin_dsn = "postgresql://renfygrid:renfygrid_dev_only@localhost:5455/renfygrid"
            with psycopg.connect(admin_dsn, autocommit=True) as admin_conn:
                with tenant_scope(admin_conn, tenant_id):
                    with admin_conn.cursor() as cur:
                        cur.execute("DELETE FROM control_order_audit WHERE tenant_id = %s", (tenant_id,))
            with conn.transaction():
                with tenant_scope(conn, tenant_id):
                    with conn.cursor() as cur:
                        cur.execute("DELETE FROM control_order WHERE tenant_id = %s", (tenant_id,))
                        cur.execute("DELETE FROM control_approval_level WHERE tenant_id = %s", (tenant_id,))
                        cur.execute("DELETE FROM meter_event WHERE tenant_id = %s", (tenant_id,))
                        cur.execute("DELETE FROM app_user WHERE tenant_id = %s", (tenant_id,))
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
