"""Verificacion end-to-end real de Control/SCR -- lista de cuentas
protegidas contra suspension/desconexion + KPIs reales (Sprint C11-5,
benchmark real: docs/05-ejecucion.md). Por HTTP real (FastAPI TestClient),
Postgres real -- sin mocks.

Que prueba, en espanol llano:
  1. Un medidor real marcado como protegido (`POST /meters/{id}/protection`).
  2. `POST /control-orders` tipo `suspension` sobre ese medidor SIN override
     -> 422, la orden NUNCA se crea (ni siquiera en `requested`).
  3. La misma solicitud CON `override_protection=true` +
     `override_justification` propia -> 201, la orden se crea, y su
     auditoria de "requested" (via `GET /control-orders/{id}`) trae el
     detalle real del override (motivo de proteccion + justificacion del
     override) -- trazabilidad real para debido proceso, no solo un flag.
  4. Carga masiva (`POST /meters/protection/bulk`): una cuenta real +
     una que no existe -- confirma `marked`/`not_found` reales, sin
     inventar ninguna.
  5. `GET /meters/protected` refleja la lista real.
  6. `GET /control-orders/summary`: sin ordenes despachadas, la tasa de
     exito es `None` (no 0% inventado); con 1 confirmada real + 1 fallida
     real insertadas, la tasa sube a 50.0 exacto.

Uso:
    python verify_meter_protection_end_to_end.py "postgresql://renfygrid_app:renfygrid_app_dev_only@localhost:5455/renfygrid"
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "hes-adapter-dlms"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import psycopg  # noqa: E402

from meter_registry import register_meter  # noqa: E402
from renmeter_common.db import tenant_scope  # noqa: E402
from renmeter_common.user_service import create_app_user  # noqa: E402

JWT_SECRET = "e2e-c11-5-secret"
ORDER_SIGNING_SECRET = "e2e-c11-5-order-secret"


def run(dsn: str) -> int:
    os.environ["RENFYGRID_DSN"] = dsn
    os.environ["RENFYGRID_JWT_SECRET"] = JWT_SECRET
    os.environ["RENFYGRID_ORDER_SIGNING_SECRET"] = ORDER_SIGNING_SECRET

    import main
    from fastapi.testclient import TestClient

    client = TestClient(main.app)

    with psycopg.connect(dsn, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO tenant (name) VALUES (%s) RETURNING id", ("E2E Meter Protection Sprint C11-5",))
            (tenant_id,) = cur.fetchone()
            tenant_id = str(tenant_id)

        try:
            create_app_user(conn, tenant_id, "ana@renfygrid.demo", "clave-portal-1", "supervisor")
            meter_id = register_meter(conn, tenant_id, "ACC-PROT-1", "SER-PROT-1", "test-brand", "DLMS_COSEM")

            with conn.transaction():
                with tenant_scope(conn, tenant_id):
                    with conn.cursor() as cur:
                        cur.execute(
                            "INSERT INTO control_approval_level (tenant_id, order_type, requires_human_approval, min_required_role) "
                            "VALUES (%s, 'suspension', false, 'supervisor')",
                            (tenant_id,),
                        )

            token = client.post(
                "/auth/login", json={"tenant_id": tenant_id, "email": "ana@renfygrid.demo", "password": "clave-portal-1"}
            ).json()["access_token"]
            headers = {"Authorization": f"Bearer {token}"}

            # 1. Marcar el medidor como protegido.
            mark_resp = client.post(
                f"/meters/{meter_id}/protection", headers=headers,
                json={"protected": True, "reason": "Hospital -- Ley 142/CREG"},
            )
            print(f"POST /meters/{{id}}/protection: {mark_resp.status_code}")
            ok_mark = mark_resp.status_code == 200

            # 2. Sin override -> 422, la orden nunca se crea.
            blocked_resp = client.post(
                "/control-orders", headers=headers,
                json={"meter_id": meter_id, "order_type": "suspension", "justification": "mora de 3 meses"},
            )
            print(f"POST /control-orders sin override: {blocked_resp.status_code}, {blocked_resp.json()}")
            ok_blocked = blocked_resp.status_code == 422 and "protegida" in blocked_resp.json()["detail"]

            # 3. Con override -> 201, y la auditoria trae el detalle real.
            override_resp = client.post(
                "/control-orders", headers=headers,
                json={
                    "meter_id": meter_id, "order_type": "suspension", "justification": "mora de 3 meses",
                    "override_protection": True,
                    "override_justification": "Autorizado por gerencia tras verificar cese de actividad hospitalaria",
                },
            )
            print(f"POST /control-orders con override: {override_resp.status_code}")
            ok_override = override_resp.status_code == 201
            order_id = override_resp.json()["order_id"] if ok_override else None

            detail = client.get(f"/control-orders/{order_id}", headers=headers).json() if order_id else {}
            requested_audit = next((row for row in detail.get("audit", []) if row["new_status"] == "requested"), None)
            print(f"Auditoria 'requested': {requested_audit}")
            ok_audit = (
                requested_audit is not None and requested_audit["detail"] is not None
                and requested_audit["detail"].get("protection_reason") == "Hospital -- Ley 142/CREG"
                and "gerencia" in requested_audit["detail"].get("override_justification", "")
            )

            # 4. Carga masiva.
            bulk_resp = client.post(
                "/meters/protection/bulk", headers=headers,
                json={"account_numbers": ["ACC-PROT-1", "ACC-NO-EXISTE"], "reason": "Colegio -- Ley 142/CREG"},
            ).json()
            print(f"POST /meters/protection/bulk: {bulk_resp}")
            ok_bulk = bulk_resp["marked"] == ["ACC-PROT-1"] and bulk_resp["not_found"] == ["ACC-NO-EXISTE"]

            # 5. Lista real.
            protected_list = client.get("/meters/protected", headers=headers).json()
            print(f"GET /meters/protected: {protected_list}")
            ok_list = len(protected_list) == 1 and protected_list[0]["account_number"] == "ACC-PROT-1"

            # 6. Resumen -- primero sin nada despachado (None, no 0%).
            summary_empty = client.get("/control-orders/summary", headers=headers).json()
            print(f"GET /control-orders/summary (antes de despachar nada): {summary_empty}")
            ok_summary_none = summary_empty["command_success_rate_pct"] is None and summary_empty["total_orders"] == 1

            with conn.transaction():
                with tenant_scope(conn, tenant_id):
                    with conn.cursor() as cur:
                        cur.execute(
                            "INSERT INTO control_order (tenant_id, meter_id, type, status, requested_by, justification) "
                            "VALUES (%s, %s, 'reconnection', 'confirmed', 'system:test', 'x'), "
                            "       (%s, %s, 'reconnection', 'failed', 'system:test', 'x')",
                            (tenant_id, meter_id, tenant_id, meter_id),
                        )

            summary_after = client.get("/control-orders/summary", headers=headers).json()
            print(f"GET /control-orders/summary (1 confirmada + 1 fallida reales): {summary_after}")
            ok_summary_rate = summary_after["command_success_rate_pct"] == 50.0 and summary_after["total_orders"] == 3

            ok = ok_mark and ok_blocked and ok_override and ok_audit and ok_bulk and ok_list and ok_summary_none and ok_summary_rate
            print("SPRINT C11-5 METER PROTECTION E2E OK" if ok else "SPRINT C11-5 METER PROTECTION E2E FALLA")
            return 0 if ok else 1
        finally:
            # control_order_audit es append-only para renfygrid_app (migracion
            # 0007, REVOKE UPDATE, DELETE) -- limpiarla necesita el rol admin,
            # mismo patron ya usado en verify_service_orders_end_to_end.py.
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
                        cur.execute("DELETE FROM meter WHERE tenant_id = %s", (tenant_id,))
                        cur.execute("DELETE FROM app_user WHERE tenant_id = %s", (tenant_id,))
            with conn.cursor() as cur:
                cur.execute("DELETE FROM tenant WHERE id = %s", (tenant_id,))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    sys.exit(run(sys.argv[1]))
