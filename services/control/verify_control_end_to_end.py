"""Verificacion end-to-end real del flujo SCR (F26/F27 + parte de F28),
Sprint 6 -- nada de mocks contra la BD.

Que prueba, en espanol llano:
  1. Configura `control_approval_level`: `suspension` requiere aprobacion
     humana de un `supervisor`; `reconnection` se auto-aprueba.
  2. Pide una orden de `suspension` -- confirma que queda `pending_approval`.
  3. Un rol insuficiente ('operator') intenta aprobarla -- rechazado.
  4. El rol correcto ('supervisor') la aprueba -- confirma `approved` +
     `is_ready_to_execute` = True, con 3 filas de auditoria trazables
     (requested -> pending_approval -> approved).
  5. Pide una orden de `reconnection` -- confirma que queda `approved` de
     inmediato (auto-aprobada), sin que nadie la apruebe a mano.
  6. Confirma que `control_order_audit` es verdaderamente append-only
     (UPDATE rechazado por Postgres con el rol de aplicacion real).

Uso:
    python verify_control_end_to_end.py "postgresql://renfygrid_app:renfygrid_app_dev_only@localhost:5455/renfygrid"
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))

import psycopg  # noqa: E402

from approval_levels_cache import build_cache  # noqa: E402
from control_service import (  # noqa: E402
    InsufficientRoleError,
    approve_order,
    is_ready_to_execute,
    request_order,
)
from renmeter_common.db import tenant_scope  # noqa: E402


def run(dsn: str) -> int:
    with psycopg.connect(dsn, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO tenant (name) VALUES (%s) RETURNING id", ("E2E Control Sprint6",))
            (tenant_id,) = cur.fetchone()
            tenant_id = str(tenant_id)

        try:
            with conn.transaction():
                with tenant_scope(conn, tenant_id):
                    with conn.cursor() as cur:
                        cur.execute(
                            "INSERT INTO meter (tenant_id, account_number, serial_number, brand, protocol) "
                            "VALUES (%s, 'ACC-S6', 'SER-S6', 'test-brand', 'DLMS_COSEM') RETURNING id",
                            (tenant_id,),
                        )
                        (meter_id,) = cur.fetchone()
                        meter_id = str(meter_id)

                        cur.execute(
                            "INSERT INTO control_approval_level (tenant_id, order_type, requires_human_approval, min_required_role) "
                            "VALUES (%s, 'suspension', true, 'supervisor'), (%s, 'reconnection', false, 'operator')",
                            (tenant_id, tenant_id),
                        )

            with tempfile.TemporaryDirectory() as tmp_dir:
                snapshot_path = Path(tmp_dir) / "control_approval_level.json"
                cache = build_cache(snapshot_path, dsn, tenant_id)
                cache.refresh()
                cache.load()
                levels = cache.get_all()

            # --- suspension: requiere aprobacion humana ---
            suspension_id = request_order(
                conn, tenant_id, meter_id, "suspension",
                requested_by="ana.cobranzas@renfygrid.demo",
                justification="Cartera vencida > 90 dias", approval_levels=levels,
            )
            with conn.transaction():
                with tenant_scope(conn, tenant_id):
                    with conn.cursor() as cur:
                        cur.execute("SELECT status FROM control_order WHERE id = %s", (suspension_id,))
                        (status_after_request,) = cur.fetchone()
            ok_request = status_after_request == "pending_approval"
            print(f"Suspension tras solicitarla: status={status_after_request} (esperado: pending_approval)")

            wrong_role_rejected = False
            try:
                approve_order(conn, tenant_id, suspension_id, "operador.raso@renfygrid.demo", "operator", levels)
            except InsufficientRoleError:
                wrong_role_rejected = True
            print(f"Aprobacion con rol insuficiente rechazada: {wrong_role_rejected}")

            approve_order(conn, tenant_id, suspension_id, "carla.supervisora@renfygrid.demo", "supervisor", levels)
            ready = is_ready_to_execute(conn, tenant_id, suspension_id)
            with conn.transaction():
                with tenant_scope(conn, tenant_id):
                    with conn.cursor() as cur:
                        cur.execute(
                            "SELECT previous_status, new_status, actor FROM control_order_audit "
                            "WHERE order_id = %s ORDER BY \"timestamp\"", (suspension_id,),
                        )
                        audit_rows = cur.fetchall()
            print(f"Suspension aprobada: ready_to_execute={ready}, auditoria={audit_rows}")
            ok_suspension = (
                ok_request and wrong_role_rejected and ready and len(audit_rows) == 3
                and [r[1] for r in audit_rows] == ["requested", "pending_approval", "approved"]
            )

            # --- reconnection: auto-aprobada ---
            reconnection_id = request_order(
                conn, tenant_id, meter_id, "reconnection",
                requested_by="sistema.facturacion@renfygrid.demo",
                justification="Pago confirmado", approval_levels=levels,
            )
            with conn.transaction():
                with tenant_scope(conn, tenant_id):
                    with conn.cursor() as cur:
                        cur.execute("SELECT status, approved_by FROM control_order WHERE id = %s", (reconnection_id,))
                        recon_status, recon_approver = cur.fetchone()
            ok_auto = recon_status == "approved" and recon_approver == "system:auto_approval"
            print(f"Reconnection auto-aprobada: status={recon_status}, approved_by={recon_approver}")

            # --- inmutabilidad real de la auditoria ---
            immutable_ok = False
            try:
                with psycopg.connect(dsn, autocommit=True) as guard_conn:
                    with tenant_scope(guard_conn, tenant_id):
                        with guard_conn.cursor() as cur:
                            cur.execute(
                                "UPDATE control_order_audit SET actor = 'hacked' WHERE tenant_id = %s", (tenant_id,)
                            )
            except psycopg.errors.InsufficientPrivilege:
                immutable_ok = True
            print(f"control_order_audit es append-only (UPDATE rechazado): {immutable_ok}")

            ok = ok_suspension and ok_auto and immutable_ok
            print("SPRINT 6 E2E OK" if ok else "SPRINT 6 E2E FALLA")
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
                        cur.execute("DELETE FROM meter WHERE tenant_id = %s", (tenant_id,))
            with conn.cursor() as cur:
                cur.execute("DELETE FROM tenant WHERE id = %s", (tenant_id,))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    sys.exit(run(sys.argv[1]))
