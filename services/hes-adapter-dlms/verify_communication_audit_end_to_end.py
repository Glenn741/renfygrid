"""Verificacion end-to-end real de F09 (auditoria de comunicacion con
dispositivos), Sprint 9 -- nada de mocks contra la BD ni contra DLMS.

Que prueba, en espanol llano:
  1. Registra un medidor+gateway+mapeo apuntando al simulador real.
  2. Corre `poller.py` 1 ciclo exitoso -- confirma una fila `meter_event`
     `type='communication_success'` con `detail.operation='poller_read'`.
  3. Apunta el gateway a un puerto cerrado y corre otro ciclo -- confirma
     una fila `communication_failure` con el error real en `detail`.
  4. Llama `on_demand_reader.read_meter_now` contra el simulador real (con
     el gateway ya apuntando de nuevo al puerto correcto) -- confirma una
     fila `communication_success` con `detail.operation='on_demand_read'`.

Uso:
    python verify_communication_audit_end_to_end.py "postgresql://renfygrid_app:renfygrid_app_dev_only@localhost:5455/renfygrid"
"""

from __future__ import annotations

import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))

import psycopg  # noqa: E402

from meter_registry import link_meter_to_gateway, register_gateway, register_meter  # noqa: E402
from obis_mapping import build_cache  # noqa: E402
from on_demand_reader import read_meter_now  # noqa: E402
from poller import main as poller_main  # noqa: E402
from renmeter_common.db import tenant_scope  # noqa: E402
from simulator.dlms_simulator_server import serve_in_background  # noqa: E402

HOST = "127.0.0.1"
PORT = 22555
CLOSED_PORT = 22556
OBIS_CODE = "1.0.1.8.0.255"
SIMULATED_VALUE = 333222
CHANNEL = "active_energy"
BRAND = "test-brand-s9"
MODEL = "test-model-s9"


def run(dsn: str) -> int:
    serve_in_background(HOST, PORT, OBIS_CODE, SIMULATED_VALUE)
    time.sleep(0.3)

    with psycopg.connect(dsn, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO tenant (name) VALUES (%s) RETURNING id", ("E2E Communication Audit Sprint9",))
            (tenant_id,) = cur.fetchone()
            tenant_id = str(tenant_id)

        try:
            gateway_id = register_gateway(
                conn, tenant_id, "Simulador E2E Audit", "TCP", {"host": HOST, "port": PORT, "client_address": 16}
            )
            meter_id = register_meter(conn, tenant_id, "ACC-S9", "SER-S9", BRAND, "DLMS_COSEM", model=MODEL)
            link_meter_to_gateway(conn, tenant_id, meter_id, gateway_id, server_address=1)

            with conn.transaction():
                with tenant_scope(conn, tenant_id):
                    with conn.cursor() as cur:
                        cur.execute(
                            "INSERT INTO meter_protocol (tenant_id, brand, model, protocol, obis_mapping) "
                            "VALUES (%s, %s, %s, 'DLMS_COSEM', %s)",
                            (tenant_id, BRAND, MODEL, psycopg.types.json.Json({CHANNEL: {"obis_code": OBIS_CODE, "attribute_index": 2}})),
                        )

            with tempfile.TemporaryDirectory() as tmp_dir:
                snapshot_path = Path(tmp_dir) / "obis_mapping.json"
                build_cache(snapshot_path, dsn, tenant_id).refresh()
                poller_main([
                    "--dsn", dsn, "--tenant-id", tenant_id,
                    "--obis-mapping-snapshot", str(snapshot_path),
                    "--interval-seconds", "1", "--iterations", "1",
                ])

            # --- ciclo fallido: gateway apuntando a un puerto cerrado ---
            with conn.transaction():
                with tenant_scope(conn, tenant_id):
                    with conn.cursor() as cur:
                        cur.execute(
                            "UPDATE gateway SET connection = %s WHERE id = %s",
                            (psycopg.types.json.Json({"host": HOST, "port": CLOSED_PORT, "client_address": 16}), gateway_id),
                        )
            with tempfile.TemporaryDirectory() as tmp_dir:
                snapshot_path = Path(tmp_dir) / "obis_mapping.json"
                build_cache(snapshot_path, dsn, tenant_id).refresh()
                poller_main([
                    "--dsn", dsn, "--tenant-id", tenant_id,
                    "--obis-mapping-snapshot", str(snapshot_path),
                    "--interval-seconds", "1", "--iterations", "1",
                    "--read-retries", "1",
                ])

            # --- gateway restaurado, lectura bajo demanda ---
            with conn.transaction():
                with tenant_scope(conn, tenant_id):
                    with conn.cursor() as cur:
                        cur.execute(
                            "UPDATE gateway SET connection = %s WHERE id = %s",
                            (psycopg.types.json.Json({"host": HOST, "port": PORT, "client_address": 16}), gateway_id),
                        )
            read_meter_now(conn, tenant_id, meter_id, CHANNEL)

            with conn.transaction():
                with tenant_scope(conn, tenant_id):
                    with conn.cursor() as cur:
                        cur.execute(
                            "SELECT type, detail FROM meter_event WHERE meter_id = %s ORDER BY \"timestamp\"",
                            (meter_id,),
                        )
                        events = cur.fetchall()

            print(f"Eventos de comunicacion registrados: {events}")
            types = [e[0] for e in events]
            ok = (
                types == ["communication_success", "communication_failure", "communication_success"]
                and events[0][1]["operation"] == "poller_read"
                and events[1][1]["error"] is not None
                and events[2][1]["operation"] == "on_demand_read"
            )
            print("F09 OK -- exito, falla y bajo-demanda auditados con el detalle correcto" if ok else "F09 FALLA")
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
                        cur.execute("DELETE FROM meter_protocol WHERE tenant_id = %s", (tenant_id,))
            with conn.cursor() as cur:
                cur.execute("DELETE FROM tenant WHERE id = %s", (tenant_id,))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    sys.exit(run(sys.argv[1]))
