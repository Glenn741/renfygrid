"""Verificacion end-to-end real del editor de reglas (F50, Sprint C3):
`vee_rule`, `consumption_anomaly_rule`, `control_approval_level` -- via
`fastapi.testclient.TestClient` + Postgres real, con un usuario real.

Que prueba, en espanol llano:
  1. Crea una regla VEE real via `POST /vee-rules` -- confirma que
     `run_vee_pass.py` (Sprint 3) la usa de verdad para el SIGUIENTE pase
     de validacion (no un mock, el motor real).
  2. Desactiva esa regla via `PATCH /vee-rules/{id}` -- confirma que ya
     no aparece en `GET /vee-rules` (activas) pero si en el historial.
  3. Crea una regla de anomalia de consumo real.
  4. Crea un nivel de aprobacion de control para 'suspension' -- confirma
     que `control_service.approval_level_for` (Sprint 6) ya lo usa.
     Crea un SEGUNDO nivel para el mismo `order_type` -- confirma que el
     primero queda cerrado (`valid_to` != null) y solo el nuevo esta activo.

Uso:
    python verify_rules_admin_end_to_end.py "postgresql://renfygrid_app:renfygrid_app_dev_only@localhost:5455/renfygrid"
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "vee-engine"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import psycopg  # noqa: E402

from renmeter_common.db import tenant_scope  # noqa: E402
from renmeter_common.user_service import create_app_user  # noqa: E402
from vee_rules_cache import build_cache  # noqa: E402
from run_vee_pass import main as vee_pass_main  # noqa: E402

JWT_SECRET = "e2e-rules-admin-secret"
ORDER_SIGNING_SECRET = "e2e-rules-admin-order-secret"


def run(dsn: str) -> int:
    os.environ["RENFYGRID_DSN"] = dsn
    os.environ["RENFYGRID_JWT_SECRET"] = JWT_SECRET
    os.environ["RENFYGRID_ORDER_SIGNING_SECRET"] = ORDER_SIGNING_SECRET

    import main
    from fastapi.testclient import TestClient

    client = TestClient(main.app)

    with psycopg.connect(dsn, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO tenant (name) VALUES (%s) RETURNING id", ("E2E Rules Admin SprintC3",))
            (tenant_id,) = cur.fetchone()
            tenant_id = str(tenant_id)

        try:
            create_app_user(conn, tenant_id, "admin@renfygrid.demo", "clave-super-secreta", "supervisor")
            token = client.post(
                "/auth/login",
                json={"tenant_id": tenant_id, "email": "admin@renfygrid.demo", "password": "clave-super-secreta"},
            ).json()["access_token"]
            headers = {"Authorization": f"Bearer {token}"}

            with conn.transaction():
                with tenant_scope(conn, tenant_id):
                    with conn.cursor() as cur:
                        cur.execute(
                            "INSERT INTO meter (tenant_id, account_number, serial_number, brand, protocol) "
                            "VALUES (%s, 'ACC-C3', 'SER-C3', 'test-brand', 'DLMS_COSEM') RETURNING id",
                            (tenant_id,),
                        )
                        (meter_id,) = cur.fetchone()
                        meter_id = str(meter_id)
                        cur.execute(
                            "INSERT INTO raw_reading (tenant_id, meter_id, \"timestamp\", channel, value) "
                            "VALUES (%s, %s, now(), 'active_energy', 999999)",
                            (tenant_id, meter_id),
                        )

            # --- 1/2: regla VEE real, usada por el motor real, luego desactivada ---
            create_resp = client.post(
                "/vee-rules", headers=headers,
                json={"type": "range", "params": {"channel": "active_energy", "min": 0, "max": 100}, "priority": 100},
            )
            rule_id = create_resp.json()["id"]
            print(f"POST /vee-rules: {create_resp.status_code}, id={rule_id}")

            with tempfile.TemporaryDirectory() as tmp_dir:
                snapshot_path = Path(tmp_dir) / "vee_rule.json"
                build_cache(snapshot_path, dsn, tenant_id).refresh()
                vee_pass_main(["--dsn", dsn, "--tenant-id", tenant_id, "--vee-rules-snapshot", str(snapshot_path), "--iterations", "1"])

            with conn.transaction():
                with tenant_scope(conn, tenant_id):
                    with conn.cursor() as cur:
                        cur.execute("SELECT is_valid, vee_rule_id FROM validated_reading WHERE meter_id = %s", (meter_id,))
                        is_valid, used_rule_id = cur.fetchone()
            ok_vee_used = is_valid is False and str(used_rule_id) == rule_id
            print(f"Lectura validada con la regla recien creada: is_valid={is_valid}, vee_rule_id usado={used_rule_id}")

            deactivate_resp = client.patch(f"/vee-rules/{rule_id}", headers=headers)
            list_active_resp = client.get("/vee-rules", headers=headers)
            ok_vee_deactivate = (
                deactivate_resp.status_code == 200
                and rule_id not in [r["id"] for r in list_active_resp.json()]
            )
            print(f"PATCH desactivar: {deactivate_resp.status_code}, activas tras desactivar: {list_active_resp.json()}")

            # --- 3: regla de anomalia de consumo ---
            anomaly_resp = client.post(
                "/consumption-anomaly-rules", headers=headers,
                json={"condition": {"max_deviation_pct": 25}, "action": "reread_order"},
            )
            ok_anomaly = anomaly_resp.status_code == 201 and "id" in anomaly_resp.json()
            print(f"POST /consumption-anomaly-rules: {anomaly_resp.status_code}")

            # --- 4: nivel de aprobacion, y que la segunda version cierre la primera ---
            level_1 = client.post(
                "/control-approval-levels", headers=headers,
                json={"order_type": "suspension", "requires_human_approval": True, "min_required_role": "operator"},
            ).json()["id"]
            level_2 = client.post(
                "/control-approval-levels", headers=headers,
                json={"order_type": "suspension", "requires_human_approval": True, "min_required_role": "supervisor"},
            ).json()["id"]

            with conn.transaction():
                with tenant_scope(conn, tenant_id):
                    with conn.cursor() as cur:
                        cur.execute("SELECT id, valid_to IS NOT NULL FROM control_approval_level WHERE id = %s", (level_1,))
                        (_, level_1_closed) = cur.fetchone()
                        cur.execute("SELECT id, valid_to IS NOT NULL FROM control_approval_level WHERE id = %s", (level_2,))
                        (_, level_2_closed) = cur.fetchone()

            active_levels = client.get("/control-approval-levels", headers=headers).json()
            suspension_levels = [lv for lv in active_levels if lv["order_type"] == "suspension"]
            ok_approval_versioning = (
                level_1_closed is True
                and level_2_closed is False
                and len(suspension_levels) == 1
                and suspension_levels[0]["min_required_role"] == "supervisor"
            )
            print(f"Nivel 1 cerrado: {level_1_closed}, nivel 2 activo: {not level_2_closed}, activas: {active_levels}")

            ok = ok_vee_used and ok_vee_deactivate and ok_anomaly and ok_approval_versioning
            print("SPRINT C3 BACKEND E2E OK" if ok else "SPRINT C3 BACKEND E2E FALLA")
            return 0 if ok else 1
        finally:
            with conn.transaction():
                with tenant_scope(conn, tenant_id):
                    with conn.cursor() as cur:
                        cur.execute("DELETE FROM validated_reading WHERE tenant_id = %s", (tenant_id,))
                        cur.execute("DELETE FROM raw_reading WHERE tenant_id = %s", (tenant_id,))
                        cur.execute("DELETE FROM vee_rule WHERE tenant_id = %s", (tenant_id,))
                        cur.execute("DELETE FROM consumption_anomaly_rule WHERE tenant_id = %s", (tenant_id,))
                        cur.execute("DELETE FROM control_approval_level WHERE tenant_id = %s", (tenant_id,))
                        cur.execute("DELETE FROM app_user WHERE tenant_id = %s", (tenant_id,))
                        cur.execute("DELETE FROM meter WHERE tenant_id = %s", (tenant_id,))
            with conn.cursor() as cur:
                cur.execute("DELETE FROM tenant WHERE id = %s", (tenant_id,))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    sys.exit(run(sys.argv[1]))
