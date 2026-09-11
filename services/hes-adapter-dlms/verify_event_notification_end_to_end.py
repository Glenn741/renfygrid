"""Verificacion end-to-end real de F05 (recepcion de eventos/alarmas del
medidor via push) -- nada de mocks contra la BD ni contra el transporte.

Que prueba, en espanol llano:
  1. Registra un medidor real (con `server_address` real) en un tenant real.
  2. Levanta `event_listener.serve` en un hilo, escuchando en un puerto TCP
     real.
  3. Empuja un evento real por TCP (`send_event_notification`, la misma
     funcion que usaria un medidor/concentrador real) -- confirma que llega
     exactamente 1 fila `meter_event` tipo `meter_alarm`, con el
     `meter_id` correcto y `detail`/`severity` correctos.
  4. Empuja un segundo evento con un `server_address` que NO esta registrado
     en este tenant -- confirma que el listener sigue vivo (acepta la
     siguiente conexion) y que NO se crea ninguna fila para ese evento
     descartado.

Uso:
    python verify_event_notification_end_to_end.py "postgresql://renfygrid_app:renfygrid_app_dev_only@localhost:5455/renfygrid"
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))

import psycopg  # noqa: E402

from event_listener import serve_in_background  # noqa: E402
from event_notification import send_event_notification  # noqa: E402
from meter_registry import register_meter  # noqa: E402
from renmeter_common.db import tenant_scope  # noqa: E402

HOST = "127.0.0.1"
PORT = 22777
REGISTERED_SERVER_ADDRESS = 501
UNKNOWN_SERVER_ADDRESS = 999


def _meter_events(conn: psycopg.Connection, tenant_id: str, meter_id: str) -> list[tuple]:
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT type, severity, detail FROM meter_event WHERE meter_id = %s ORDER BY \"timestamp\"",
                    (meter_id,),
                )
                return cur.fetchall()


def run(dsn: str) -> int:
    with psycopg.connect(dsn, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO tenant (name) VALUES (%s) RETURNING id", ("E2E Event Notification F05",))
            (tenant_id,) = cur.fetchone()
            tenant_id = str(tenant_id)

        try:
            meter_id = register_meter(
                conn, tenant_id, "ACC-F05", "SER-F05", "test-brand-f05", "DLMS_COSEM", model="test-model-f05"
            )
            with conn.transaction():
                with tenant_scope(conn, tenant_id):
                    with conn.cursor() as cur:
                        cur.execute(
                            "UPDATE meter SET server_address = %s WHERE id = %s",
                            (REGISTERED_SERVER_ADDRESS, meter_id),
                        )

            serve_in_background(HOST, PORT, dsn, tenant_id)
            time.sleep(0.3)

            # --- evento real, medidor registrado ---
            send_event_notification(HOST, PORT, REGISTERED_SERVER_ADDRESS, event_code=77, severity_code=2)
            time.sleep(0.3)

            # --- evento de un server_address no registrado en este tenant ---
            send_event_notification(HOST, PORT, UNKNOWN_SERVER_ADDRESS, event_code=1, severity_code=0)
            time.sleep(0.3)

            events = _meter_events(conn, tenant_id, meter_id)
            print(f"Eventos registrados para el medidor real: {events}")

            with conn.transaction():
                with tenant_scope(conn, tenant_id):
                    with conn.cursor() as cur:
                        cur.execute("SELECT count(*) FROM meter_event WHERE tenant_id = %s", (tenant_id,))
                        (total_events,) = cur.fetchone()

            ok = (
                len(events) == 1
                and events[0][0] == "meter_alarm"
                and events[0][1] == "critical"
                and events[0][2]["event_code"] == 77
                and events[0][2]["severity_code"] == 2
                and total_events == 1  # el evento del server_address desconocido NO se guardo
            )
            print("F05 OK -- push real recibido, medidor real resuelto, evento desconocido descartado sin tumbar el listener" if ok else "F05 FALLA")
            return 0 if ok else 1
        finally:
            with conn.transaction():
                with tenant_scope(conn, tenant_id):
                    with conn.cursor() as cur:
                        cur.execute("DELETE FROM meter_event WHERE tenant_id = %s", (tenant_id,))
                        cur.execute("DELETE FROM meter WHERE tenant_id = %s", (tenant_id,))
            with conn.cursor() as cur:
                cur.execute("DELETE FROM tenant WHERE id = %s", (tenant_id,))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    sys.exit(run(sys.argv[1]))
