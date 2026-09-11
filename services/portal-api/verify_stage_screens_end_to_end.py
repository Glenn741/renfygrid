"""Verificacion end-to-end real de las 3 piezas de backend nuevas para
Sprint C2 (Nivel 2): `GET /vee/invalid-readings`, `GET /consumption?anomaly_status=`,
`GET /control-orders?status=` -- via `fastapi.testclient.TestClient` + Postgres
real, con un usuario real (no un JWT emitido a mano).

Que prueba, en espanol llano:
  1. Una lectura invalida real aparece en `/vee/invalid-readings` con su
     `account_number` y `validation_notes` -- una valida NO aparece.
  2. Un consumo `under_review` aparece en `/consumption?anomaly_status=under_review`
     -- uno `ok` NO aparece con ese filtro.
  3. Una orden `pending_approval` aparece en `/control-orders?status=pending_approval`
     -- al aprobarla (mismo endpoint de Sprint 8), desaparece de esa cola.

Uso:
    python verify_stage_screens_end_to_end.py "postgresql://renfygrid_app:renfygrid_app_dev_only@localhost:5455/renfygrid"
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import psycopg  # noqa: E402

from renmeter_common.db import tenant_scope  # noqa: E402
from renmeter_common.user_service import create_app_user  # noqa: E402

JWT_SECRET = "e2e-stage-screens-secret"
ORDER_SIGNING_SECRET = "e2e-stage-screens-order-secret"


def run(dsn: str) -> int:
    os.environ["RENFYGRID_DSN"] = dsn
    os.environ["RENFYGRID_JWT_SECRET"] = JWT_SECRET
    os.environ["RENFYGRID_ORDER_SIGNING_SECRET"] = ORDER_SIGNING_SECRET

    import main
    from fastapi.testclient import TestClient

    client = TestClient(main.app)

    with psycopg.connect(dsn, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO tenant (name) VALUES (%s) RETURNING id", ("E2E Stage Screens SprintC2",))
            (tenant_id,) = cur.fetchone()
            tenant_id = str(tenant_id)

        try:
            create_app_user(conn, tenant_id, "operador@renfygrid.demo", "clave-super-secreta", "supervisor")
            login_resp = client.post(
                "/auth/login",
                json={"tenant_id": tenant_id, "email": "operador@renfygrid.demo", "password": "clave-super-secreta"},
            )
            token = login_resp.json()["access_token"]
            headers = {"Authorization": f"Bearer {token}"}

            with conn.transaction():
                with tenant_scope(conn, tenant_id):
                    with conn.cursor() as cur:
                        cur.execute(
                            "INSERT INTO meter (tenant_id, account_number, serial_number, brand, protocol) "
                            "VALUES (%s, 'ACC-C2', 'SER-C2', 'test-brand', 'DLMS_COSEM') RETURNING id",
                            (tenant_id,),
                        )
                        (meter_id,) = cur.fetchone()

                        cur.execute(
                            "INSERT INTO validated_reading (tenant_id, meter_id, channel, \"timestamp\", value, source, is_valid, validation_notes) "
                            "VALUES (%s, %s, 'active_energy', now(), 999999, 'real', false, 'fuera de rango')",
                            (tenant_id, meter_id),
                        )
                        cur.execute(
                            "INSERT INTO validated_reading (tenant_id, meter_id, channel, \"timestamp\", value, source, is_valid) "
                            "VALUES (%s, %s, 'reactive_energy', now(), 100, 'real', true)",
                            (tenant_id, meter_id),
                        )

                        cur.execute(
                            "INSERT INTO consumption (tenant_id, meter_id, period, value, anomaly_status) "
                            "VALUES (%s, %s, daterange('2026-09-01','2026-10-01','[)'), 5000, 'under_review')",
                            (tenant_id, meter_id),
                        )
                        cur.execute(
                            "INSERT INTO consumption (tenant_id, meter_id, period, value, anomaly_status) "
                            "VALUES (%s, %s, daterange('2026-08-01','2026-09-01','[)'), 400, 'ok')",
                            (tenant_id, meter_id),
                        )
                        cur.execute(
                            "INSERT INTO control_approval_level (tenant_id, order_type, requires_human_approval, min_required_role) "
                            "VALUES (%s, 'suspension', true, 'supervisor')",
                            (tenant_id,),
                        )

            resp_vee = client.get("/vee/invalid-readings", headers=headers)
            vee_rows = resp_vee.json()
            print(f"GET /vee/invalid-readings: {resp_vee.status_code}, {vee_rows}")
            ok_vee = (
                resp_vee.status_code == 200 and len(vee_rows) == 1
                and vee_rows[0]["account_number"] == "ACC-C2" and vee_rows[0]["validation_notes"] == "fuera de rango"
            )

            resp_consumption = client.get("/consumption?anomaly_status=under_review", headers=headers)
            consumption_rows = resp_consumption.json()
            print(f"GET /consumption?anomaly_status=under_review: {resp_consumption.status_code}, {consumption_rows}")
            ok_consumption = (
                resp_consumption.status_code == 200 and len(consumption_rows) == 1
                and consumption_rows[0]["value"] == 5000.0
            )

            order_resp = client.post(
                "/control-orders",
                headers=headers,
                # Sprint C5: requested_by ya no va en el body -- sale del actor
                # autenticado (el login de arriba, "operador@renfygrid.demo").
                json={"meter_id": str(meter_id), "order_type": "suspension", "justification": "prueba C2"},
            )
            order_id = order_resp.json()["order_id"]

            resp_pending = client.get("/control-orders?status=pending_approval", headers=headers)
            pending_rows = resp_pending.json()
            print(f"GET /control-orders?status=pending_approval (antes de aprobar): {resp_pending.status_code}, {pending_rows}")
            ok_pending_before = len(pending_rows) == 1 and pending_rows[0]["order_id"] == order_id

            # Sprint C5: approver_name/approver_role ya no van en el body --
            # el mismo usuario logueado (rol 'supervisor') aprueba con su
            # identidad real, tomada del JWT.
            approve_resp = client.post(f"/control-orders/{order_id}/approve", headers=headers, json={})
            print(f"POST approve: {approve_resp.status_code}")

            resp_pending_after = client.get("/control-orders?status=pending_approval", headers=headers)
            ok_pending_after = len(resp_pending_after.json()) == 0

            ok = ok_vee and ok_consumption and ok_pending_before and approve_resp.status_code == 200 and ok_pending_after
            print("SPRINT C2 BACKEND E2E OK" if ok else "SPRINT C2 BACKEND E2E FALLA")
            return 0 if ok else 1
        finally:
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
                        cur.execute("DELETE FROM consumption WHERE tenant_id = %s", (tenant_id,))
                        cur.execute("DELETE FROM validated_reading WHERE tenant_id = %s", (tenant_id,))
                        cur.execute("DELETE FROM app_user WHERE tenant_id = %s", (tenant_id,))
                        cur.execute("DELETE FROM meter WHERE tenant_id = %s", (tenant_id,))
            with conn.cursor() as cur:
                cur.execute("DELETE FROM tenant WHERE id = %s", (tenant_id,))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    sys.exit(run(sys.argv[1]))
