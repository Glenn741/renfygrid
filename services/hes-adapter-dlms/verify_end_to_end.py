"""Verificacion end-to-end REAL del adaptador HES DLMS/COSEM -- el gap que
quedaba explicitamente abierto en el Sprint 1 (ver docs/05-ejecucion.md):
"no se probo contra un medidor o simulador real".

Cierra ese gap levantando `simulator/dlms_simulator_server.py` (un medidor de
prueba que reusa el protocolo servidor REAL de Gurux, ver el docstring de ese
archivo para los 3 bugs reales de gurux-dlms==1.0.203 que hubo que rodear) y
corriendo el mismo codigo de produccion que usa `main.py`
(GXNet + GXDLMSClient + DlmsSession + read_register + insert_raw_reading)
contra ese simulador por un socket TCP real -- no en memoria, no con mocks.

Que prueba, en espanol llano:
  1. Levanta el simulador en un puerto libre, con un Register de prueba.
  2. Crea un tenant y un medidor de prueba en Postgres (FK real).
  3. Corre el cliente real: asocia, lee el Register por OBIS, normaliza,
     inserta en raw_reading (con RLS activo -- mismo patron que verify_rls.py).
  4. Relee la fila desde Postgres y confirma que el valor coincide.
  5. Limpia los datos de prueba.

Uso:
    python verify_end_to_end.py "postgresql://renfygrid_app:renfygrid_app_dev_only@localhost:5455/renfygrid"
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))

import psycopg  # noqa: E402
from gurux_dlms import GXDLMSClient  # noqa: E402
from gurux_dlms.enums import Authentication, InterfaceType  # noqa: E402
from gurux_net import GXNet  # noqa: E402
from gurux_net.enums import NetworkType  # noqa: E402

from dlms_session import DlmsSession  # noqa: E402
from meter_reader import read_register  # noqa: E402
from reading_store import insert_raw_reading  # noqa: E402
from renmeter_common.db import tenant_scope  # noqa: E402
from simulator.dlms_simulator_server import serve_in_background  # noqa: E402

HOST = "127.0.0.1"
PORT = 22222
OBIS_CODE = "1.0.1.8.0.255"
SIMULATED_VALUE = 4781999
CHANNEL = "active_energy"


def run(dsn: str) -> int:
    serve_in_background(HOST, PORT, OBIS_CODE, SIMULATED_VALUE)
    time.sleep(0.3)  # el hilo del simulador necesita alcanzar a hacer listen()

    with psycopg.connect(dsn, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO tenant (name) VALUES (%s) RETURNING id",
                ("E2E DLMS simulator test",),
            )
            (tenant_id,) = cur.fetchone()
            tenant_id = str(tenant_id)

        try:
            with conn.transaction():
                with tenant_scope(conn, tenant_id):
                    with conn.cursor() as cur:
                        cur.execute(
                            "INSERT INTO meter (tenant_id, account_number, serial_number, brand, protocol) "
                            "VALUES (%s, 'ACC-E2E', 'SER-E2E', 'simulator', 'DLMS_COSEM') "
                            "RETURNING id",
                            (tenant_id,),
                        )
                        (meter_id,) = cur.fetchone()
                        meter_id = str(meter_id)

            media = GXNet(NetworkType.TCP, HOST, PORT)
            client = GXDLMSClient(
                True, 16, 1, Authentication.NONE, None, InterfaceType.WRAPPER
            )
            media.open()
            try:
                session = DlmsSession(client=client, media=media)
                session.associate()
                reading = read_register(session, meter_id, OBIS_CODE, CHANNEL)
                session.disconnect()
            finally:
                media.close()

            print(f"Lectura real via TCP+simulador: {reading.as_row()}")
            if reading.value != SIMULATED_VALUE:
                print(f"FALLA: valor leido {reading.value} != esperado {SIMULATED_VALUE}")
                return 1

            insert_raw_reading(conn, tenant_id, reading)

            with conn.transaction():
                with tenant_scope(conn, tenant_id):
                    with conn.cursor() as cur:
                        cur.execute(
                            "SELECT value, channel FROM raw_reading WHERE meter_id = %s",
                            (meter_id,),
                        )
                        row = cur.fetchone()

            ok = row is not None and int(row[0]) == SIMULATED_VALUE and row[1] == CHANNEL
            print(f"Fila en raw_reading: {row} (esperado: ({SIMULATED_VALUE}, '{CHANNEL}'))")
            print("E2E OK -- simulador + cliente real + raw_reading confirmados" if ok else "E2E FALLA")
            return 0 if ok else 1
        finally:
            with conn.transaction():
                with tenant_scope(conn, tenant_id):
                    with conn.cursor() as cur:
                        cur.execute("DELETE FROM raw_reading WHERE tenant_id = %s", (tenant_id,))
                        cur.execute("DELETE FROM meter WHERE tenant_id = %s", (tenant_id,))
            with conn.cursor() as cur:
                cur.execute("DELETE FROM tenant WHERE id = %s", (tenant_id,))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    sys.exit(run(sys.argv[1]))
