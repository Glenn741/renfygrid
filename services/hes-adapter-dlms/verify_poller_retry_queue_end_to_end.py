"""Verificacion end-to-end real de F08 -- cola persistente de reintentos
(Sprint C11, migracion 0010) -- sobre Postgres real, sin mocks.

Que prueba, en espanol llano:
  1. Un medidor apuntando a un puerto TCP cerrado (nadie escucha): un ciclo
     de polling agota los reintentos internos y el medidor entra a
     `poller_retry_queue` con `failure_count=1` y `next_retry_at` en el
     futuro.
  2. Un SEGUNDO ciclo, corrido de inmediato (mismo intervalo que cualquier
     medidor sano): `due_meters` lo EXCLUYE -- cero intentos nuevos, el
     medidor no se martilla mientras su backoff no haya vencido.
  3. Se adelanta `next_retry_at` al pasado a mano (simula que ya paso el
     tiempo de espera, sin depender de un `sleep()` real largo en la
     prueba) y se levanta el simulador real en ese mismo puerto: el
     siguiente ciclo SI lo intenta, tiene exito, y la fila desaparece de la
     cola (recuperacion real, no solo teorica).

Uso:
    python verify_poller_retry_queue_end_to_end.py "postgresql://renfygrid_app:renfygrid_app_dev_only@localhost:5455/renfygrid"
"""

from __future__ import annotations

import sys
import tempfile
import time
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))

import psycopg  # noqa: E402

from meter_registry import link_meter_to_gateway, register_gateway, register_meter  # noqa: E402
from obis_mapping import build_cache  # noqa: E402
from poller import main as poller_main  # noqa: E402
from renmeter_common.db import tenant_scope  # noqa: E402
from simulator.dlms_simulator_server import serve_in_background  # noqa: E402

HOST = "127.0.0.1"
CLOSED_PORT = 9  # puerto "discard" -- nadie escucha ahi, mismo puerto ya usado en la prueba manual original de F08
OBIS_CODE = "1.0.1.8.0.255"
SIMULATED_VALUE = 54321
CHANNEL = "active_energy"
BRAND = "simulator"
MODEL = "SIM-RETRY"


def queue_row(conn: psycopg.Connection, tenant_id: str, meter_id: str):
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT failure_count, next_retry_at FROM poller_retry_queue "
                    "WHERE tenant_id = %s AND meter_id = %s",
                    (tenant_id, meter_id),
                )
                return cur.fetchone()


def run(dsn: str) -> int:
    with psycopg.connect(dsn, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO tenant (name) VALUES (%s) RETURNING id", ("E2E Poller Retry Queue Sprint C11",))
            (tenant_id,) = cur.fetchone()
            tenant_id = str(tenant_id)

        try:
            gateway_id = register_gateway(
                conn, tenant_id, "Concentrador caido E2E", "TCP",
                {"host": HOST, "port": CLOSED_PORT, "client_address": 16},
            )
            meter_id = register_meter(
                conn, tenant_id, "ACC-RETRY", "SER-RETRY", BRAND, "DLMS_COSEM", model=MODEL,
            )
            link_meter_to_gateway(conn, tenant_id, meter_id, gateway_id, server_address=1)

            with conn.transaction():
                with tenant_scope(conn, tenant_id):
                    with conn.cursor() as cur:
                        cur.execute(
                            "INSERT INTO meter_protocol (tenant_id, brand, model, protocol, obis_mapping) "
                            "VALUES (%s, %s, %s, 'DLMS_COSEM', %s)",
                            (
                                tenant_id, BRAND, MODEL,
                                psycopg.types.json.Json({CHANNEL: {"obis_code": OBIS_CODE, "attribute_index": 2}}),
                            ),
                        )

            with tempfile.TemporaryDirectory() as tmp_dir:
                snapshot_path = Path(tmp_dir) / "obis_mapping.json"
                build_cache(snapshot_path, dsn, tenant_id).refresh()

                base_args = [
                    "--dsn", dsn, "--tenant-id", tenant_id, "--obis-mapping-snapshot", str(snapshot_path),
                    "--interval-seconds", "1", "--read-retries", "1", "--retry-backoff-seconds", "0.1",
                    "--retry-queue-base-seconds", "3600", "--retry-queue-max-seconds", "7200",
                ]

                # Ciclo 1: falla (puerto cerrado) -> entra a la cola.
                poller_main(base_args + ["--iterations", "1"])
                row1 = queue_row(conn, tenant_id, meter_id)
                print(f"Tras ciclo 1 (falla): poller_retry_queue = {row1}")
                ok_enqueued = row1 is not None and row1[0] == 1

                # Ciclo 2, de inmediato: debe EXCLUIRLO (backoff de 1h, no vencido).
                poller_main(base_args + ["--iterations", "1"])
                row2 = queue_row(conn, tenant_id, meter_id)
                print(f"Tras ciclo 2 (deberia excluirlo): poller_retry_queue = {row2}")
                ok_excluded = row2 is not None and row2[0] == 1  # failure_count NO subio -- no se reintento

                # Adelantar next_retry_at al pasado (simula que ya paso la espera)
                # y levantar el simulador real en el mismo puerto -- ahora si debe
                # reintentar, tener exito, y salir de la cola.
                with conn.transaction():
                    with tenant_scope(conn, tenant_id):
                        with conn.cursor() as cur:
                            cur.execute(
                                "UPDATE poller_retry_queue SET next_retry_at = now() - interval '1 second' "
                                "WHERE tenant_id = %s AND meter_id = %s",
                                (tenant_id, meter_id),
                            )
                serve_in_background(HOST, CLOSED_PORT, OBIS_CODE, SIMULATED_VALUE)
                time.sleep(0.3)

                poller_main(base_args + ["--iterations", "1"])
                row3 = queue_row(conn, tenant_id, meter_id)
                print(f"Tras ciclo 3 (backoff vencido + simulador arriba): poller_retry_queue = {row3}")
                ok_recovered = row3 is None

            ok = ok_enqueued and ok_excluded and ok_recovered
            print("SPRINT C11 F08 E2E OK -- cola persistente: encola, excluye durante backoff, recupera" if ok else "SPRINT C11 F08 E2E FALLA")
            return 0 if ok else 1
        finally:
            with conn.transaction():
                with tenant_scope(conn, tenant_id):
                    with conn.cursor() as cur:
                        cur.execute("DELETE FROM poller_retry_queue WHERE tenant_id = %s", (tenant_id,))
                        cur.execute("DELETE FROM meter_event WHERE tenant_id = %s", (tenant_id,))
                        cur.execute("DELETE FROM raw_reading WHERE tenant_id = %s", (tenant_id,))
                        cur.execute("DELETE FROM meter_protocol WHERE tenant_id = %s", (tenant_id,))
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
