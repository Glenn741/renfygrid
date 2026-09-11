"""Verificacion end-to-end real de F28/F29/F30 (Sprint 7) -- firma +
ejecucion real via el adaptador HES/simulador DLMS + confirmacion. Nada de
mocks contra BD ni contra el protocolo DLMS.

Que prueba, en espanol llano:
  1. Registra un medidor+gateway apuntando al simulador de
     `dlms_simulator_server.py` con un objeto `DisconnectControl` real
     (Sprint 7), y un mapeo `meter_protocol.obis_mapping['control']`.
  2. Pide y aprueba una orden de `suspension` (reusa el flujo de Sprint 6).
  3. `send_and_execute_order` la firma, la ejecuta REALMENTE contra el
     simulador (un `remoteDisconnect` DLMS de verdad, no un mock) y confirma
     que termina `confirmed`, con las 4 transiciones completas en
     `control_order_audit` (`requested→pending_approval→approved→sent`) mas
     la de `confirmed` -- 5 en total.
  4. Confirma que el simulador de verdad quedo "desconectado"
     (`server.control.is_connected == False`) -- no es un resultado
     simulado, es el efecto real de la accion DLMS.
  5. Con una segunda orden, apunta a un puerto CERRADO (concentrador caido)
     y confirma que `send_and_execute_order` la deja `failed`, con la razon
     en la auditoria -- nunca la deja `sent` sin resolver.

Uso:
    python verify_control_execution_end_to_end.py "postgresql://renfygrid_app:renfygrid_app_dev_only@localhost:5455/renfygrid"
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "hes-adapter-dlms"))

import psycopg  # noqa: E402

from approval_levels_cache import fetch_active_approval_levels  # noqa: E402
from control_service import approve_order, request_order, send_and_execute_order  # noqa: E402
from renmeter_common.db import tenant_scope  # noqa: E402
from simulator.dlms_simulator_server import serve_in_background  # noqa: E402

HOST = "127.0.0.1"
PORT = 22333
CLOSED_PORT = 22334  # nadie escucha aca -- simula un concentrador caido
OBIS_CODE = "1.0.1.8.0.255"
CONTROL_OBIS_CODE = "0.0.96.3.10.255"
BRAND = "test-brand-s7"
MODEL = "test-model-s7"
SIGNING_SECRET = "sprint7-e2e-secret"


def run(dsn: str) -> int:
    _, simulator = serve_in_background(HOST, PORT, OBIS_CODE, 1000, CONTROL_OBIS_CODE)
    time.sleep(0.3)

    with psycopg.connect(dsn, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO tenant (name) VALUES (%s) RETURNING id", ("E2E Control Execution Sprint7",))
            (tenant_id,) = cur.fetchone()
            tenant_id = str(tenant_id)

        try:
            with conn.transaction():
                with tenant_scope(conn, tenant_id):
                    with conn.cursor() as cur:
                        cur.execute(
                            "INSERT INTO meter (tenant_id, account_number, serial_number, brand, model, protocol) "
                            "VALUES (%s, 'ACC-S7', 'SER-S7', %s, %s, 'DLMS_COSEM') RETURNING id",
                            (tenant_id, BRAND, MODEL),
                        )
                        (meter_id,) = cur.fetchone()
                        meter_id = str(meter_id)

                        cur.execute(
                            "INSERT INTO meter_protocol (tenant_id, brand, model, protocol, obis_mapping) "
                            "VALUES (%s, %s, %s, 'DLMS_COSEM', %s)",
                            (
                                tenant_id, BRAND, MODEL,
                                psycopg.types.json.Json({"control": {"obis_code": CONTROL_OBIS_CODE}}),
                            ),
                        )

                        cur.execute(
                            "INSERT INTO gateway (tenant_id, name, transport_protocol, connection) "
                            "VALUES (%s, 'Concentrador simulador Sprint7', 'TCP', %s) RETURNING id",
                            (tenant_id, psycopg.types.json.Json({"host": HOST, "port": PORT, "client_address": 16})),
                        )
                        (gateway_id,) = cur.fetchone()
                        gateway_id = str(gateway_id)
                        cur.execute(
                            "INSERT INTO meter_gateway (meter_id, gateway_id) VALUES (%s, %s)", (meter_id, gateway_id)
                        )
                        cur.execute("UPDATE meter SET server_address = 1 WHERE id = %s", (meter_id,))

                        cur.execute(
                            "INSERT INTO control_approval_level (tenant_id, order_type, requires_human_approval, min_required_role) "
                            "VALUES (%s, 'suspension', true, 'supervisor')",
                            (tenant_id,),
                        )

            levels = fetch_active_approval_levels(conn, tenant_id)

            order_id = request_order(
                conn, tenant_id, meter_id, "suspension",
                requested_by="ana.cobranzas@renfygrid.demo", justification="Cartera vencida", approval_levels=levels,
            )
            approve_order(conn, tenant_id, order_id, "carla.supervisora@renfygrid.demo", "supervisor", levels)

            final_status = send_and_execute_order(conn, tenant_id, order_id, SIGNING_SECRET)
            print(f"Estado final tras ejecucion real: {final_status}")
            print(f"Simulador is_connected tras la orden: {simulator.control.is_connected}")

            with conn.transaction():
                with tenant_scope(conn, tenant_id):
                    with conn.cursor() as cur:
                        cur.execute(
                            "SELECT new_status FROM control_order_audit WHERE order_id = %s ORDER BY \"timestamp\"",
                            (order_id,),
                        )
                        audit_statuses = [row[0] for row in cur.fetchall()]
            print(f"Auditoria completa: {audit_statuses}")

            ok_confirmed = (
                final_status == "confirmed"
                and simulator.control.is_connected is False
                and audit_statuses == ["requested", "pending_approval", "approved", "sent", "confirmed"]
            )
            print("F28/F29/F30 (camino exitoso) OK" if ok_confirmed else "F28/F29/F30 (camino exitoso) FALLA")

            # --- camino de falla: concentrador caido (puerto cerrado) ---
            with conn.transaction():
                with tenant_scope(conn, tenant_id):
                    with conn.cursor() as cur:
                        cur.execute(
                            "UPDATE gateway SET connection = %s WHERE id = %s",
                            (psycopg.types.json.Json({"host": HOST, "port": CLOSED_PORT, "client_address": 16}), gateway_id),
                        )

            order_id_2 = request_order(
                conn, tenant_id, meter_id, "suspension",
                requested_by="ana.cobranzas@renfygrid.demo", justification="Segunda prueba", approval_levels=levels,
            )
            approve_order(conn, tenant_id, order_id_2, "carla.supervisora@renfygrid.demo", "supervisor", levels)
            failed_status = send_and_execute_order(conn, tenant_id, order_id_2, SIGNING_SECRET)

            with conn.transaction():
                with tenant_scope(conn, tenant_id):
                    with conn.cursor() as cur:
                        cur.execute(
                            "SELECT new_status, detail FROM control_order_audit WHERE order_id = %s ORDER BY \"timestamp\"",
                            (order_id_2,),
                        )
                        audit_rows_2 = cur.fetchall()

            print(f"Estado tras concentrador caido: {failed_status}, auditoria: {audit_rows_2}")
            ok_failed = failed_status == "failed" and audit_rows_2[-1][0] == "failed" and audit_rows_2[-1][1] is not None
            print("F28/F29/F30 (camino de falla) OK" if ok_failed else "F28/F29/F30 (camino de falla) FALLA")

            return 0 if (ok_confirmed and ok_failed) else 1
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
