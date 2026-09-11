"""Verificacion end-to-end real del Portal/API (F33, Sprint 8) -- el
objetivo del sprint tal cual esta escrito en el plan: "un usuario del
tenant piloto solo ve sus propios datos, verificado con un segundo tenant
de prueba" (04-plan-sprints.md SS4).

Usa `fastapi.testclient.TestClient` (real ASGI, no mocks) contra la app de
`main.py` -- pasa por auth_dependency, RLS, y Postgres real, todo real
excepto el socket TCP en si (TestClient invoca la app directo).

Que prueba, en espanol llano:
  1. Crea 2 tenants con 1 medidor cada uno. Emite un JWT real (F32, mismo
     renmeter_common.auth) por tenant.
  2. `GET /meters` con el token del tenant A -- devuelve UN medidor, el de A
     (no ve el de B, aunque la BD tenga ambos).
  3. Repite con el token del tenant B -- ve solo el suyo.
  4. Sin token -- 401. Con un token de firma invalida -- 401.
  5. `POST /control-orders` con el token de A crea una orden real para un
     medidor de A -- confirma F26/F27 alcanzables via HTTP.
  6. `POST /meters/{id}/reads` (F04, lectura bajo demanda) contra un medidor
     de A apuntando al simulador real de Sprint 1 -- confirma que el valor
     leido via HTTP coincide con el configurado en el simulador.

Uso:
    python verify_portal_api_end_to_end.py "postgresql://renfygrid_app:renfygrid_app_dev_only@localhost:5455/renfygrid"
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "hes-adapter-dlms"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))
# El propio directorio va AL FINAL (queda primero en sys.path): tanto este
# script como hes-adapter-dlms tienen un modulo llamado "main" -- sin esto,
# "import main" mas abajo resuelve al main.py equivocado (el del adaptador
# HES, no el de este servicio).
sys.path.insert(0, str(Path(__file__).resolve().parent))

import psycopg  # noqa: E402

from renmeter_common.auth import create_token  # noqa: E402
from renmeter_common.db import tenant_scope  # noqa: E402
from simulator.dlms_simulator_server import serve_in_background  # noqa: E402

JWT_SECRET = "e2e-portal-secret"
ORDER_SIGNING_SECRET = "e2e-portal-order-secret"
HOST = "127.0.0.1"
PORT = 22444
OBIS_CODE = "1.0.1.8.0.255"
SIMULATED_VALUE = 777000
BRAND = "test-brand-s8"
MODEL = "test-model-s8"


def run(dsn: str) -> int:
    os.environ["RENFYGRID_DSN"] = dsn
    os.environ["RENFYGRID_JWT_SECRET"] = JWT_SECRET
    os.environ["RENFYGRID_ORDER_SIGNING_SECRET"] = ORDER_SIGNING_SECRET

    import main  # importado ACA, despues de fijar el entorno (Settings.from_env corre al importar)
    from fastapi.testclient import TestClient

    serve_in_background(HOST, PORT, OBIS_CODE, SIMULATED_VALUE)
    time.sleep(0.3)

    client = TestClient(main.app)

    with psycopg.connect(dsn, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO tenant (name) VALUES (%s), (%s) RETURNING id", ("Portal E2E A", "Portal E2E B"))
            tenant_a_id, tenant_b_id = (str(row[0]) for row in cur.fetchall())

        try:
            meter_ids = {}
            for tenant_id, label in ((tenant_a_id, "A"), (tenant_b_id, "B")):
                with conn.transaction():
                    with tenant_scope(conn, tenant_id):
                        with conn.cursor() as cur:
                            cur.execute(
                                "INSERT INTO meter (tenant_id, account_number, serial_number, brand, model, protocol) "
                                "VALUES (%s, %s, %s, %s, %s, 'DLMS_COSEM') RETURNING id",
                                (tenant_id, f"ACC-{label}", f"SER-{label}", BRAND, MODEL),
                            )
                            meter_ids[tenant_id] = str(cur.fetchone()[0])

            # solo el medidor de A queda con conexion real al simulador + mapeo OBIS
            with conn.transaction():
                with tenant_scope(conn, tenant_a_id):
                    with conn.cursor() as cur:
                        cur.execute(
                            "INSERT INTO meter_protocol (tenant_id, brand, model, protocol, obis_mapping) "
                            "VALUES (%s, %s, %s, 'DLMS_COSEM', %s)",
                            (
                                tenant_a_id, BRAND, MODEL,
                                psycopg.types.json.Json({"active_energy": {"obis_code": OBIS_CODE, "attribute_index": 2}}),
                            ),
                        )
                        cur.execute(
                            "INSERT INTO gateway (tenant_id, name, transport_protocol, connection) "
                            "VALUES (%s, 'Simulador E2E Portal', 'TCP', %s) RETURNING id",
                            (tenant_a_id, psycopg.types.json.Json({"host": HOST, "port": PORT, "client_address": 16})),
                        )
                        (gateway_id,) = cur.fetchone()
                        cur.execute(
                            "INSERT INTO meter_gateway (meter_id, gateway_id) VALUES (%s, %s)",
                            (meter_ids[tenant_a_id], gateway_id),
                        )
                        cur.execute(
                            "UPDATE meter SET server_address = 1 WHERE id = %s", (meter_ids[tenant_a_id],)
                        )
                        cur.execute(
                            "INSERT INTO control_approval_level (tenant_id, order_type, requires_human_approval, min_required_role) "
                            "VALUES (%s, 'suspension', true, 'supervisor')",
                            (tenant_a_id,),
                        )

            token_a = create_token({"tenant_id": tenant_a_id, "role": "operator"}, JWT_SECRET)
            token_b = create_token({"tenant_id": tenant_b_id, "role": "operator"}, JWT_SECRET)

            resp_a = client.get("/meters", headers={"Authorization": f"Bearer {token_a}"})
            resp_b = client.get("/meters", headers={"Authorization": f"Bearer {token_b}"})
            resp_no_auth = client.get("/meters")
            resp_bad_token = client.get("/meters", headers={"Authorization": "Bearer not-a-real-token"})

            meters_a = [m["id"] for m in resp_a.json()]
            meters_b = [m["id"] for m in resp_b.json()]
            print(f"GET /meters con token A: {resp_a.status_code}, {len(meters_a)} medidor(es)")
            print(f"GET /meters con token B: {resp_b.status_code}, {len(meters_b)} medidor(es)")
            print(f"GET /meters sin token: {resp_no_auth.status_code}")
            print(f"GET /meters con token invalido: {resp_bad_token.status_code}")

            ok_rls = (
                resp_a.status_code == 200 and meters_a == [meter_ids[tenant_a_id]]
                and resp_b.status_code == 200 and meters_b == [meter_ids[tenant_b_id]]
                and meter_ids[tenant_b_id] not in meters_a
                and meter_ids[tenant_a_id] not in meters_b
                and resp_no_auth.status_code == 401
                and resp_bad_token.status_code == 401
            )
            print("F33 (RLS end-to-end via HTTP) OK" if ok_rls else "F33 FALLA")

            resp_order = client.post(
                "/control-orders",
                headers={"Authorization": f"Bearer {token_a}"},
                json={
                    "meter_id": meter_ids[tenant_a_id], "order_type": "suspension",
                    "requested_by": "ana@renfygrid.demo", "justification": "Prueba E2E Portal",
                },
            )
            print(f"POST /control-orders: {resp_order.status_code}, body={resp_order.json()}")
            ok_control = resp_order.status_code == 201 and "order_id" in resp_order.json()

            resp_read = client.post(
                f"/meters/{meter_ids[tenant_a_id]}/reads",
                headers={"Authorization": f"Bearer {token_a}"},
                json={"channel": "active_energy"},
            )
            print(f"POST /meters/{{id}}/reads: {resp_read.status_code}, body={resp_read.json()}")
            ok_read = resp_read.status_code == 200 and resp_read.json()["value"] == SIMULATED_VALUE

            # el token de B no puede leer bajo demanda el medidor de A
            resp_read_wrong_tenant = client.post(
                f"/meters/{meter_ids[tenant_a_id]}/reads",
                headers={"Authorization": f"Bearer {token_b}"},
                json={"channel": "active_energy"},
            )
            print(f"POST /meters/{{id_de_A}}/reads con token B: {resp_read_wrong_tenant.status_code}")
            ok_cross_tenant_blocked = resp_read_wrong_tenant.status_code == 422  # RLS: para B, ese meter_id no existe

            ok = ok_rls and ok_control and ok_read and ok_cross_tenant_blocked
            print("SPRINT 8 E2E OK" if ok else "SPRINT 8 E2E FALLA")
            return 0 if ok else 1
        finally:
            for tenant_id in (tenant_a_id, tenant_b_id):
                admin_dsn = "postgresql://renfygrid:renfygrid_dev_only@localhost:5455/renfygrid"
                with psycopg.connect(admin_dsn, autocommit=True) as admin_conn:
                    with tenant_scope(admin_conn, tenant_id):
                        with admin_conn.cursor() as cur:
                            cur.execute("DELETE FROM control_order_audit WHERE tenant_id = %s", (tenant_id,))
                with conn.transaction():
                    with tenant_scope(conn, tenant_id):
                        with conn.cursor() as cur:
                            cur.execute("DELETE FROM raw_reading WHERE tenant_id = %s", (tenant_id,))
                            cur.execute("DELETE FROM control_order WHERE tenant_id = %s", (tenant_id,))
                            cur.execute("DELETE FROM control_approval_level WHERE tenant_id = %s", (tenant_id,))
                            cur.execute("DELETE FROM meter_gateway WHERE meter_id IN (SELECT id FROM meter WHERE tenant_id = %s)", (tenant_id,))
                            cur.execute("DELETE FROM meter WHERE tenant_id = %s", (tenant_id,))
                            cur.execute("DELETE FROM gateway WHERE tenant_id = %s", (tenant_id,))
                            cur.execute("DELETE FROM meter_protocol WHERE tenant_id = %s", (tenant_id,))
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM tenant WHERE id = %s", (tenant_id,))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    sys.exit(run(sys.argv[1]))
