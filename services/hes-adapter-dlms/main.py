"""Punto de entrada real del adaptador HES DLMS/COSEM (Sprint 1).

Nada de host/puerto/tenant/medidor fijo en el codigo -- todo llega por
argumentos (en un despliegue real vendria de `meter`/`meter_protocol`, ver
docs/03-diseno.md). Uso:

    python main.py --host 127.0.0.1 --port 4059 --tenant-id <uuid> \
        --meter-id <uuid> --obis-code 1.0.1.8.0.255 --channel active_energy \
        --dsn "postgresql://renfygrid_app:...@localhost:5455/renfygrid"

ESTADO: no corrido todavia contra un medidor/simulador real -- ver el docstring
de dlms_session.py y docs/05-ejecucion.md (Sprint 1).
"""

from __future__ import annotations

import argparse
import sys
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


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", required=True)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--tenant-id", required=True)
    parser.add_argument("--meter-id", required=True)
    parser.add_argument("--obis-code", required=True)
    parser.add_argument("--channel", required=True)
    parser.add_argument("--client-address", type=int, default=16)
    parser.add_argument("--server-address", type=int, default=1)
    parser.add_argument("--dsn", required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    media = GXNet(NetworkType.TCP, args.host, args.port)
    client = GXDLMSClient(
        True,
        args.client_address,
        args.server_address,
        Authentication.NONE,
        None,
        InterfaceType.WRAPPER,
    )

    media.open()
    try:
        session = DlmsSession(client=client, media=media)
        session.associate()
        reading = read_register(session, args.meter_id, args.obis_code, args.channel)
        session.disconnect()
    finally:
        media.close()

    with psycopg.connect(args.dsn, autocommit=True) as conn:
        insert_raw_reading(conn, args.tenant_id, reading)

    print(f"OK: {reading.as_row()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
