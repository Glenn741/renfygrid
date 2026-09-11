"""F05 (Sprint 2, retomado 2026-09-11): listener TCP que recibe eventos/
alarmas empujados por un medidor/concentrador (push DLMS, ver
`event_notification.py`) y los deja en `meter_event`.

Corre por tenant, igual que `poller.py`/`on_demand_reader.py` -- un
concentrador movil/GPRS puede tener IP dinamica, asi que la identidad real
del medidor viaja en el propio payload (`meter_server_address`), pero saber
A QUE TENANT pertenece ese payload es una decision de despliegue (que rango
de concentradores llega a este listener), no algo que se pueda inferir del
mensaje -- mismo criterio que el resto del adaptador HES, nunca se cruza
tenants dentro de un mismo proceso.

Un medidor con `server_address` desconocido (no registrado en este tenant)
se registra igual como evento, pero SIN `meter_id` resuelto -- se descarta
la conexion con una advertencia en vez de inventar un medidor o tumbar el
listener completo (mismo principio de "un medidor no debe tumbar el resto"
que `poller.py::run_once`).
"""

from __future__ import annotations

import argparse
import socket
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))

import psycopg  # noqa: E402

from renmeter_common.db import tenant_scope  # noqa: E402

from event_notification import EventNotification, EventNotificationDecoder, MalformedEventNotificationError  # noqa: E402


def meter_id_for_server_address(conn: psycopg.Connection, tenant_id: str, server_address: int) -> str | None:
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute("SELECT id FROM meter WHERE server_address = %s", (server_address,))
                row = cur.fetchone()
                return str(row[0]) if row else None


def record_event(conn: psycopg.Connection, tenant_id: str, meter_id: str, event: EventNotification) -> None:
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO meter_event (tenant_id, meter_id, type, severity, detail) "
                    "VALUES (%s, %s, %s, %s, %s)",
                    (
                        tenant_id,
                        meter_id,
                        "meter_alarm",
                        event.severity,
                        psycopg.types.json.Json(
                            {"event_code": event.event_code, "severity_code": event.severity_code}
                        ),
                    ),
                )


def receive_one_event(sock: socket.socket, recv_buffer_size: int = 4096) -> EventNotification | None:
    """Lee de una conexion ya aceptada hasta tener un evento completo, o
    hasta que el remitente cierre sin haber terminado de mandarlo."""
    decoder = EventNotificationDecoder()
    while True:
        chunk = sock.recv(recv_buffer_size)
        if not chunk:
            return None
        event = decoder.feed(chunk)
        if event is not None:
            return event


def handle_connection(sock: socket.socket, conn: psycopg.Connection, tenant_id: str) -> None:
    with sock:
        try:
            event = receive_one_event(sock)
        except MalformedEventNotificationError as exc:
            print(f"  DESCARTADA: cuerpo de notificacion invalido ({exc})")
            return
        if event is None:
            print("  DESCARTADA: conexion cerrada antes de completar el mensaje")
            return
        meter_id = meter_id_for_server_address(conn, tenant_id, event.meter_server_address)
        if meter_id is None:
            print(f"  DESCARTADA: server_address={event.meter_server_address} no registrado en este tenant")
            return
        record_event(conn, tenant_id, meter_id, event)
        print(
            f"  OK meter_id={meter_id} event_code={event.event_code} severity={event.severity}"
        )


def serve(host: str, port: int, dsn: str, tenant_id: str, *, iterations: int = 0) -> None:
    """Corre indefinidamente aceptando conexiones (una a la vez -- alcanza
    para el volumen de un piloto, mismo alcance que
    `simulator/dlms_simulator_server.py::serve`). `iterations` > 0 es solo
    para pruebas: procesa N conexiones y termina."""
    with psycopg.connect(dsn, autocommit=True) as conn:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            listener.bind((host, port))
            listener.listen(5)
            print(f"Listener de eventos escuchando en {host}:{port} (tenant {tenant_id})")
            count = 0
            while True:
                client_sock, addr = listener.accept()
                print(f"Push recibido desde {addr}")
                handle_connection(client_sock, conn, tenant_id)
                count += 1
                if iterations and count >= iterations:
                    return


def serve_in_background(host: str, port: int, dsn: str, tenant_id: str) -> threading.Thread:
    """Para pruebas: corre `serve()` en un hilo daemon. El llamador debe
    esperar un momento (o reintentar la conexion) antes de que el listener
    este realmente aceptando -- no hay senal explicita de 'listo', mismo
    patron que `simulator.dlms_simulator_server.serve_in_background`."""
    thread = threading.Thread(target=serve, args=(host, port, dsn, tenant_id), daemon=True)
    thread.start()
    return thread


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--dsn", required=True)
    parser.add_argument("--tenant-id", required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    serve(args.host, args.port, args.dsn, args.tenant_id)
    return 0


if __name__ == "__main__":
    sys.exit(main())
