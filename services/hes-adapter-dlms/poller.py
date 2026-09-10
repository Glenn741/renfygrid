"""Lectura remota programada (F03, Sprint 1): en un intervalo configurable
(por argumento, no fijo en codigo), recorre los medidores activos y
enlazados a un gateway (`meter.server_address` + `gateway.connection`, ver
`meter_registry.py` y la migracion 0003) y les pide una lectura real via
DLMS/COSEM, guardandola en `raw_reading` -- mismo pipeline que `main.py`
para un solo medidor, aca aplicado a todos los que esten listos.

Alcance explicito de Sprint 1, no mas: el codigo OBIS y el canal a leer se
reciben por argumento y se aplican igual a todos los medidores del tenant --
el mapeo OBIS *por marca/modelo* desde BD (F06) es Sprint 2 a proposito, ver
docs/05-ejecucion.md. Tampoco hay cola/reintento ante caida de un
concentrador (F08, Sprint 2): si un medidor falla en un ciclo, se registra el
error y se sigue con el resto -- no se reintenta dentro del mismo ciclo.
"""

from __future__ import annotations

import argparse
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


def due_meters(conn: psycopg.Connection, tenant_id: str) -> list[dict]:
    """Medidores activos, enlazados a un gateway, con direccion DLMS asignada."""
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT m.id, m.server_address, g.connection "
                    "FROM meter m "
                    "JOIN meter_gateway mg ON mg.meter_id = m.id "
                    "JOIN gateway g ON g.id = mg.gateway_id "
                    "WHERE m.status = 'active' AND m.server_address IS NOT NULL"
                )
                return [
                    {"meter_id": str(row[0]), "server_address": row[1], "connection": row[2]}
                    for row in cur.fetchall()
                ]


def read_one_meter(
    meter_id: str,
    server_address: int,
    connection: dict,
    obis_code: str,
    channel: str,
    conn: psycopg.Connection,
    tenant_id: str,
) -> None:
    media = GXNet(NetworkType.TCP, connection["host"], connection["port"])
    client = GXDLMSClient(
        True,
        connection.get("client_address", 16),
        server_address,
        Authentication.NONE,
        None,
        InterfaceType.WRAPPER,
    )
    media.open()
    try:
        session = DlmsSession(client=client, media=media)
        session.associate()
        reading = read_register(session, meter_id, obis_code, channel)
        session.disconnect()
    finally:
        media.close()
    insert_raw_reading(conn, tenant_id, reading)


def run_once(dsn: str, tenant_id: str, obis_code: str, channel: str) -> None:
    with psycopg.connect(dsn, autocommit=True) as conn:
        meters = due_meters(conn, tenant_id)
        print(f"Ciclo de polling: {len(meters)} medidor(es) activo(s) para leer")
        for meter in meters:
            try:
                read_one_meter(
                    meter["meter_id"],
                    meter["server_address"],
                    meter["connection"],
                    obis_code,
                    channel,
                    conn,
                    tenant_id,
                )
                print(f"  OK meter_id={meter['meter_id']}")
            except Exception as exc:  # un medidor caido no debe tumbar el ciclo entero
                print(f"  FALLA meter_id={meter['meter_id']}: {exc}")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dsn", required=True)
    parser.add_argument("--tenant-id", required=True)
    parser.add_argument("--obis-code", required=True)
    parser.add_argument("--channel", required=True)
    parser.add_argument("--interval-seconds", type=int, required=True)
    parser.add_argument(
        "--iterations",
        type=int,
        default=0,
        help="0 = corre indefinidamente; >0 = para pruebas, corre N ciclos y termina",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    count = 0
    while True:
        run_once(args.dsn, args.tenant_id, args.obis_code, args.channel)
        count += 1
        if args.iterations and count >= args.iterations:
            return 0
        time.sleep(args.interval_seconds)


if __name__ == "__main__":
    sys.exit(main())
