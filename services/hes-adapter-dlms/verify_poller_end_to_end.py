"""Verificacion end-to-end real de F01/F11 (registro) + F03 (polling
programado), Sprint 1 -- mismo espiritu que verify_end_to_end.py pero
probando el camino completo "registrar medidor+gateway -> el poller lo
encuentra solo -> lee 2 ciclos reales via el simulador -> quedan 2 filas en
raw_reading", no un solo disparo manual.

Uso:
    python verify_poller_end_to_end.py "postgresql://renfygrid_app:renfygrid_app_dev_only@localhost:5455/renfygrid"
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))

import psycopg  # noqa: E402

from meter_registry import link_meter_to_gateway, register_gateway, register_meter  # noqa: E402
from poller import main as poller_main  # noqa: E402
from renmeter_common.db import tenant_scope  # noqa: E402
from simulator.dlms_simulator_server import serve_in_background  # noqa: E402

HOST = "127.0.0.1"
PORT = 22223
OBIS_CODE = "1.0.1.8.0.255"
SIMULATED_VALUE = 12345
CHANNEL = "active_energy"


def run(dsn: str) -> int:
    serve_in_background(HOST, PORT, OBIS_CODE, SIMULATED_VALUE)
    time.sleep(0.3)

    with psycopg.connect(dsn, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO tenant (name) VALUES (%s) RETURNING id",
                ("E2E poller test",),
            )
            (tenant_id,) = cur.fetchone()
            tenant_id = str(tenant_id)

        try:
            gateway_id = register_gateway(
                conn, tenant_id, "Simulador E2E", "TCP",
                {"host": HOST, "port": PORT, "client_address": 16},
            )
            meter_id = register_meter(
                conn, tenant_id, "ACC-POLLER", "SER-POLLER", "simulator", "DLMS_COSEM",
            )
            link_meter_to_gateway(conn, tenant_id, meter_id, gateway_id, server_address=1)

            poller_main(
                [
                    "--dsn", dsn,
                    "--tenant-id", tenant_id,
                    "--obis-code", OBIS_CODE,
                    "--channel", CHANNEL,
                    "--interval-seconds", "1",
                    "--iterations", "2",
                ]
            )

            with conn.transaction():
                with tenant_scope(conn, tenant_id):
                    with conn.cursor() as cur:
                        cur.execute(
                            "SELECT count(*), max(value) FROM raw_reading WHERE meter_id = %s",
                            (meter_id,),
                        )
                        row_count, max_value = cur.fetchone()

            print(f"Filas en raw_reading tras 2 ciclos: {row_count} (esperado: 2), valor: {max_value}")
            ok = row_count == 2 and int(max_value) == SIMULATED_VALUE
            print("E2E poller OK" if ok else "E2E poller FALLA")
            return 0 if ok else 1
        finally:
            with conn.transaction():
                with tenant_scope(conn, tenant_id):
                    with conn.cursor() as cur:
                        cur.execute("DELETE FROM raw_reading WHERE tenant_id = %s", (tenant_id,))
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
