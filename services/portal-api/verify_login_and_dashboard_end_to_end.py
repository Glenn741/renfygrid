"""Verificacion end-to-end real de F47 (login real) y F48 (tablero Nivel 1),
Sprint C1 -- via `fastapi.testclient.TestClient` + Postgres real.

Que prueba, en espanol llano:
  1. Da de alta un usuario real (`create_app_user`, con contraseña hasheada
     -- nunca en texto plano) y hace login real via `POST /auth/login`.
  2. Contraseña incorrecta -- 401. Usuario desactivado -- 401.
  3. Con el JWT real que devolvio el login (no uno emitido a mano), pide
     `GET /dashboard/overview` -- confirma que refleja datos reales: un
     medidor caido, una lectura VEE invalida, un consumo en revision y una
     orden de control pendiente de aprobacion, cada uno contado
     correctamente.

Uso:
    python verify_login_and_dashboard_end_to_end.py "postgresql://renfygrid_app:renfygrid_app_dev_only@localhost:5455/renfygrid"
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import psycopg  # noqa: E402

from renmeter_common.db import tenant_scope  # noqa: E402
from renmeter_common.user_service import create_app_user  # noqa: E402

JWT_SECRET = "e2e-login-dashboard-secret"
ORDER_SIGNING_SECRET = "e2e-login-dashboard-order-secret"


def run(dsn: str) -> int:
    os.environ["RENFYGRID_DSN"] = dsn
    os.environ["RENFYGRID_JWT_SECRET"] = JWT_SECRET
    os.environ["RENFYGRID_ORDER_SIGNING_SECRET"] = ORDER_SIGNING_SECRET

    import main
    from fastapi.testclient import TestClient

    client = TestClient(main.app)

    with psycopg.connect(dsn, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO tenant (name) VALUES (%s) RETURNING id", ("E2E Login Dashboard SprintC1",))
            (tenant_id,) = cur.fetchone()
            tenant_id = str(tenant_id)

        try:
            create_app_user(conn, tenant_id, "operador@renfygrid.demo", "clave-super-secreta", "operator")
            with conn.transaction():
                with tenant_scope(conn, tenant_id):
                    with conn.cursor() as cur:
                        cur.execute(
                            "INSERT INTO app_user (tenant_id, email, password_hash, role, is_active) "
                            "VALUES (%s, 'inactivo@renfygrid.demo', %s, 'operator', false)",
                            (tenant_id, "pbkdf2_sha256$1$AAAA$BBBB"),
                        )

            resp_ok = client.post("/auth/login", json={"tenant_id": tenant_id, "email": "operador@renfygrid.demo", "password": "clave-super-secreta"})
            resp_wrong_password = client.post("/auth/login", json={"tenant_id": tenant_id, "email": "operador@renfygrid.demo", "password": "incorrecta"})
            resp_inactive = client.post("/auth/login", json={"tenant_id": tenant_id, "email": "inactivo@renfygrid.demo", "password": "cualquiera"})

            print(f"login OK: {resp_ok.status_code}")
            print(f"login password incorrecta: {resp_wrong_password.status_code}")
            print(f"login usuario inactivo: {resp_inactive.status_code}")

            ok_login = (
                resp_ok.status_code == 200 and "access_token" in resp_ok.json()
                and resp_wrong_password.status_code == 401
                and resp_inactive.status_code == 401
            )
            token = resp_ok.json().get("access_token")

            # --- datos reales para que el tablero tenga algo que mostrar ---
            now = datetime.now(timezone.utc)
            with conn.transaction():
                with tenant_scope(conn, tenant_id):
                    with conn.cursor() as cur:
                        cur.execute(
                            "INSERT INTO meter (tenant_id, account_number, serial_number, brand, protocol, status) "
                            "VALUES (%s, 'ACC-STALE', 'SER-STALE', 'test-brand', 'DLMS_COSEM', 'active') RETURNING id",
                            (tenant_id,),
                        )
                        (meter_id,) = cur.fetchone()
                        cur.execute(
                            "INSERT INTO raw_reading (tenant_id, meter_id, \"timestamp\", channel, value) VALUES (%s, %s, %s, 'active_energy', 1)",
                            (tenant_id, meter_id, now - timedelta(hours=2)),
                        )
                        cur.execute(
                            "INSERT INTO validated_reading (tenant_id, meter_id, channel, \"timestamp\", value, source, is_valid) "
                            "VALUES (%s, %s, 'active_energy', %s, 999999, 'real', false)",
                            (tenant_id, meter_id, now),
                        )
                        cur.execute(
                            "INSERT INTO consumption (tenant_id, meter_id, period, value, anomaly_status) "
                            "VALUES (%s, %s, daterange('2026-09-01','2026-10-01','[)'), 5000, 'under_review')",
                            (tenant_id, meter_id),
                        )
                        cur.execute(
                            "INSERT INTO control_order (tenant_id, meter_id, type, status, requested_by) "
                            "VALUES (%s, %s, 'suspension', 'pending_approval', 'ana@renfygrid.demo')",
                            (tenant_id, meter_id),
                        )

            resp_dashboard = client.get(
                "/dashboard/overview?stale_after_seconds=3600", headers={"Authorization": f"Bearer {token}"}
            )
            data = resp_dashboard.json()
            print(f"GET /dashboard/overview: {resp_dashboard.status_code}, {data}")

            ok_dashboard = (
                resp_dashboard.status_code == 200
                and data["hes"]["meters_stale"] == 1
                and data["vee"]["invalid_pending"] == 1
                and data["consumption"]["under_review"] == 1
                and data["control"]["pending_approval"] == 1
            )
            print("F47/F48 OK" if (ok_login and ok_dashboard) else "F47/F48 FALLA")
            return 0 if (ok_login and ok_dashboard) else 1
        finally:
            with conn.transaction():
                with tenant_scope(conn, tenant_id):
                    with conn.cursor() as cur:
                        cur.execute("DELETE FROM control_order WHERE tenant_id = %s", (tenant_id,))
                        cur.execute("DELETE FROM consumption WHERE tenant_id = %s", (tenant_id,))
                        cur.execute("DELETE FROM validated_reading WHERE tenant_id = %s", (tenant_id,))
                        cur.execute("DELETE FROM raw_reading WHERE tenant_id = %s", (tenant_id,))
                        cur.execute("DELETE FROM app_user WHERE tenant_id = %s", (tenant_id,))
                        cur.execute("DELETE FROM meter WHERE tenant_id = %s", (tenant_id,))
            with conn.cursor() as cur:
                cur.execute("DELETE FROM tenant WHERE id = %s", (tenant_id,))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    sys.exit(run(sys.argv[1]))
