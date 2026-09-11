"""Verificacion end-to-end real de F51 (Nivel 3: detalle y acciones),
Sprint C4 -- via `fastapi.testclient.TestClient` + Postgres real, con un
usuario real.

Que prueba, en espanol llano:
  1. `POST /vee/invalid-readings/edit` edita de verdad una lectura invalida
     real -- confirma que `is_valid` pasa a `true` y que
     `validated_reading_edit` (inmutable) tiene el registro de auditoria.
  2. `GET /control-orders/{id}` devuelve la orden puntual con su historial
     de auditoria completo (`requested`, `pending_approval`, `approved`).
  3. `POST /meters/{id}/reads` (F04, ya existente) sigue funcionando como
     la accion "leer ahora" de la pantalla de detalle de un medidor.

Uso:
    python verify_detail_actions_end_to_end.py "postgresql://renfygrid_app:renfygrid_app_dev_only@localhost:5455/renfygrid"
"""

from __future__ import annotations

import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "hes-adapter-dlms"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import psycopg  # noqa: E402

from renmeter_common.db import tenant_scope  # noqa: E402
from renmeter_common.user_service import create_app_user  # noqa: E402
from simulator.dlms_simulator_server import serve_in_background  # noqa: E402

JWT_SECRET = "e2e-detail-actions-secret"
ORDER_SIGNING_SECRET = "e2e-detail-actions-order-secret"
HOST = "127.0.0.1"
PORT = 22666
OBIS_CODE = "1.0.1.8.0.255"
SIMULATED_VALUE = 555000
BRAND = "test-brand-c4"
MODEL = "test-model-c4"


def run(dsn: str) -> int:
    os.environ["RENFYGRID_DSN"] = dsn
    os.environ["RENFYGRID_JWT_SECRET"] = JWT_SECRET
    os.environ["RENFYGRID_ORDER_SIGNING_SECRET"] = ORDER_SIGNING_SECRET

    import main
    from fastapi.testclient import TestClient

    serve_in_background(HOST, PORT, OBIS_CODE, SIMULATED_VALUE)
    time.sleep(0.3)

    client = TestClient(main.app)

    with psycopg.connect(dsn, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO tenant (name) VALUES (%s) RETURNING id", ("E2E Detail Actions SprintC4",))
            (tenant_id,) = cur.fetchone()
            tenant_id = str(tenant_id)

        try:
            create_app_user(conn, tenant_id, "operador@renfygrid.demo", "clave-super-secreta", "supervisor")
            token = client.post(
                "/auth/login",
                json={"tenant_id": tenant_id, "email": "operador@renfygrid.demo", "password": "clave-super-secreta"},
            ).json()["access_token"]
            headers = {"Authorization": f"Bearer {token}"}

            with conn.transaction():
                with tenant_scope(conn, tenant_id):
                    with conn.cursor() as cur:
                        cur.execute(
                            "INSERT INTO meter (tenant_id, account_number, serial_number, brand, model, protocol) "
                            "VALUES (%s, 'ACC-C4', 'SER-C4', %s, %s, 'DLMS_COSEM') RETURNING id",
                            (tenant_id, BRAND, MODEL),
                        )
                        (meter_id,) = cur.fetchone()
                        meter_id = str(meter_id)

                        cur.execute(
                            "INSERT INTO meter_protocol (tenant_id, brand, model, protocol, obis_mapping) "
                            "VALUES (%s, %s, %s, 'DLMS_COSEM', %s)",
                            (tenant_id, BRAND, MODEL, psycopg.types.json.Json({"active_energy": {"obis_code": OBIS_CODE, "attribute_index": 2}})),
                        )
                        cur.execute(
                            "INSERT INTO gateway (tenant_id, name, transport_protocol, connection) "
                            "VALUES (%s, 'Simulador E2E C4', 'TCP', %s) RETURNING id",
                            (tenant_id, psycopg.types.json.Json({"host": HOST, "port": PORT, "client_address": 16})),
                        )
                        (gateway_id,) = cur.fetchone()
                        cur.execute("INSERT INTO meter_gateway (meter_id, gateway_id) VALUES (%s, %s)", (meter_id, gateway_id))
                        cur.execute("UPDATE meter SET server_address = 1 WHERE id = %s", (meter_id,))

                        reading_ts = datetime.now(timezone.utc)
                        cur.execute(
                            "INSERT INTO validated_reading (tenant_id, meter_id, channel, \"timestamp\", value, source, is_valid, validation_notes) "
                            "VALUES (%s, %s, 'active_energy', %s, 999999, 'real', false, 'fuera de rango')",
                            (tenant_id, meter_id, reading_ts),
                        )

                        cur.execute(
                            "INSERT INTO control_approval_level (tenant_id, order_type, requires_human_approval, min_required_role) "
                            "VALUES (%s, 'suspension', true, 'supervisor')",
                            (tenant_id,),
                        )

            # --- 1: editar una lectura invalida ---
            edit_resp = client.post(
                "/vee/invalid-readings/edit", headers=headers,
                json={
                    "meter_id": meter_id, "channel": "active_energy", "timestamp": reading_ts.isoformat(),
                    "new_value": 4500.0, "user_name": "operador@renfygrid.demo", "justification": "corregido tras inspeccion",
                },
            )
            print(f"POST /vee/invalid-readings/edit: {edit_resp.status_code}")

            with conn.transaction():
                with tenant_scope(conn, tenant_id):
                    with conn.cursor() as cur:
                        cur.execute("SELECT value, is_valid, source FROM validated_reading WHERE meter_id = %s", (meter_id,))
                        edited_value, is_valid, source = cur.fetchone()
                        cur.execute("SELECT count(*) FROM validated_reading_edit WHERE tenant_id = %s", (tenant_id,))
                        (edit_count,) = cur.fetchone()

            ok_edit = (
                edit_resp.status_code == 200 and float(edited_value) == 4500.0
                and is_valid is True and source == "edited" and edit_count == 1
            )
            print(f"Tras editar: value={edited_value}, is_valid={is_valid}, source={source}, filas de auditoria={edit_count}")

            # --- 2: detalle de orden con auditoria ---
            order_id = client.post(
                "/control-orders", headers=headers,
                json={"meter_id": meter_id, "order_type": "suspension", "requested_by": "ana@renfygrid.demo", "justification": "prueba C4"},
            ).json()["order_id"]
            client.post(f"/control-orders/{order_id}/approve", headers=headers, json={"approver_name": "carla@renfygrid.demo", "approver_role": "supervisor"})

            detail_resp = client.get(f"/control-orders/{order_id}", headers=headers)
            detail = detail_resp.json()
            print(f"GET /control-orders/{{id}}: {detail_resp.status_code}, status={detail.get('status')}, audit_len={len(detail.get('audit', []))}")
            ok_detail = (
                detail_resp.status_code == 200 and detail["status"] == "approved"
                and [a["new_status"] for a in detail["audit"]] == ["requested", "pending_approval", "approved"]
            )

            # --- 3: leer ahora (F04, reusado como accion de detalle de medidor) ---
            read_resp = client.post(f"/meters/{meter_id}/reads", headers=headers, json={"channel": "active_energy"})
            print(f"POST /meters/{{id}}/reads: {read_resp.status_code}, value={read_resp.json().get('value')}")
            ok_read_now = read_resp.status_code == 200 and read_resp.json()["value"] == SIMULATED_VALUE

            ok = ok_edit and ok_detail and ok_read_now
            print("SPRINT C4 BACKEND E2E OK" if ok else "SPRINT C4 BACKEND E2E FALLA")
            return 0 if ok else 1
        finally:
            admin_dsn = "postgresql://renfygrid:renfygrid_dev_only@localhost:5455/renfygrid"
            with psycopg.connect(admin_dsn, autocommit=True) as admin_conn:
                with tenant_scope(admin_conn, tenant_id):
                    with admin_conn.cursor() as cur:
                        cur.execute("DELETE FROM validated_reading_edit WHERE tenant_id = %s", (tenant_id,))
                        cur.execute("DELETE FROM control_order_audit WHERE tenant_id = %s", (tenant_id,))
            with conn.transaction():
                with tenant_scope(conn, tenant_id):
                    with conn.cursor() as cur:
                        cur.execute("DELETE FROM control_order WHERE tenant_id = %s", (tenant_id,))
                        cur.execute("DELETE FROM control_approval_level WHERE tenant_id = %s", (tenant_id,))
                        cur.execute("DELETE FROM validated_reading WHERE tenant_id = %s", (tenant_id,))
                        cur.execute("DELETE FROM raw_reading WHERE tenant_id = %s", (tenant_id,))
                        cur.execute("DELETE FROM meter_event WHERE tenant_id = %s", (tenant_id,))
                        cur.execute("DELETE FROM app_user WHERE tenant_id = %s", (tenant_id,))
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
