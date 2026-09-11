"""Lectura remota programada (F03, Sprint 1), ahora con mapeo OBIS
configurable por marca/modelo (F06, Sprint 2) y reintentos ante caida de un
concentrador (F08, Sprint 2).

En un intervalo configurable (por argumento, nunca fijo en codigo), recorre
los medidores activos y enlazados a un gateway (`meter.server_address` +
`gateway.connection`, ver `meter_registry.py` y la migracion 0003), busca
el mapeo OBIS vigente de su marca/modelo en el cache (`obis_mapping.py` --
snapshot en disco, refrescado por separado con
`refresh_obis_mapping_cache.py`, nunca leido de BD en este hot path) y lee
cada canal mapeado, guardando cada uno en `raw_reading`.

Alcance explicito de F08, no mas: reintentos acotados (`--read-retries`,
`--retry-backoff-seconds`) DENTRO del mismo ciclo -- si un medidor sigue
fallando despues de agotarlos, se registra el error y se sigue con el resto;
no hay una cola persistente que reintente en un ciclo posterior (eso seria
una pieza aparte, no construida todavia).
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

from communication_audit import audited_communication  # noqa: E402
from dlms_session import DlmsSession  # noqa: E402
from meter_reader import read_register  # noqa: E402
from obis_mapping import ConfigCache, channels_for  # noqa: E402
from reading_store import insert_raw_reading  # noqa: E402
from renmeter_common.db import tenant_scope  # noqa: E402


def due_meters(conn: psycopg.Connection, tenant_id: str) -> list[dict]:
    """Medidores activos, enlazados a un gateway, con direccion DLMS asignada."""
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT m.id, m.brand, m.model, m.server_address, g.connection "
                    "FROM meter m "
                    "JOIN meter_gateway mg ON mg.meter_id = m.id "
                    "JOIN gateway g ON g.id = mg.gateway_id "
                    "WHERE m.status = 'active' AND m.server_address IS NOT NULL"
                )
                return [
                    {
                        "meter_id": str(row[0]),
                        "brand": row[1],
                        "model": row[2],
                        "server_address": row[3],
                        "connection": row[4],
                    }
                    for row in cur.fetchall()
                ]


def read_all_channels(
    meter_id: str,
    server_address: int,
    connection: dict,
    channels: dict[str, dict],
) -> list:
    """Una sola asociacion DLMS, una lectura por canal mapeado."""
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
        readings = [
            read_register(
                session,
                meter_id,
                mapping["obis_code"],
                channel,
                mapping.get("attribute_index", 2),
            )
            for channel, mapping in channels.items()
        ]
        session.disconnect()
    finally:
        media.close()
    return readings


def read_one_meter_with_retries(
    meter: dict,
    channels: dict[str, dict],
    conn: psycopg.Connection,
    tenant_id: str,
    read_retries: int,
    retry_backoff_seconds: float,
) -> None:
    """F08: hasta `read_retries` intentos, con espera fija entre cada uno,
    antes de dar por fallido este medidor en este ciclo."""
    last_error: Exception | None = None
    for attempt in range(1, read_retries + 1):
        try:
            with audited_communication(conn, tenant_id, meter["meter_id"], "poller_read"):
                readings = read_all_channels(
                    meter["meter_id"], meter["server_address"], meter["connection"], channels
                )
                for reading in readings:
                    insert_raw_reading(conn, tenant_id, reading)
            return
        except Exception as exc:  # falla de comunicacion con el concentrador/medidor
            last_error = exc
            if attempt < read_retries:
                time.sleep(retry_backoff_seconds)
    raise last_error  # agotados los reintentos -- el llamador decide que hacer


def run_once(
    dsn: str,
    tenant_id: str,
    mapping_cache: ConfigCache,
    read_retries: int,
    retry_backoff_seconds: float,
) -> None:
    mapping_cache.load()  # hot-reload: un refresh corrido aparte ya se refleja aca
    with psycopg.connect(dsn, autocommit=True) as conn:
        meters = due_meters(conn, tenant_id)
        print(f"Ciclo de polling: {len(meters)} medidor(es) activo(s) para leer")
        for meter in meters:
            channels = channels_for(mapping_cache, meter["brand"], meter["model"])
            if not channels:
                print(f"  SIN MAPEO OBIS meter_id={meter['meter_id']} ({meter['brand']}/{meter['model']}), se omite")
                continue
            try:
                read_one_meter_with_retries(
                    meter, channels, conn, tenant_id, read_retries, retry_backoff_seconds
                )
                print(f"  OK meter_id={meter['meter_id']} ({len(channels)} canal(es))")
            except Exception as exc:  # un medidor caido no debe tumbar el ciclo entero
                print(f"  FALLA meter_id={meter['meter_id']} tras {read_retries} intento(s): {exc}")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dsn", required=True)
    parser.add_argument("--tenant-id", required=True)
    parser.add_argument("--obis-mapping-snapshot", required=True)
    parser.add_argument("--interval-seconds", type=int, required=True)
    parser.add_argument("--read-retries", type=int, default=1)
    parser.add_argument("--retry-backoff-seconds", type=float, default=2.0)
    parser.add_argument(
        "--iterations",
        type=int,
        default=0,
        help="0 = corre indefinidamente; >0 = para pruebas, corre N ciclos y termina",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    mapping_cache = ConfigCache(
        fetch_fn=lambda: [],  # este proceso nunca llama a fetch_fn: solo hace load() del snapshot
        snapshot_path=Path(args.obis_mapping_snapshot),
        source_name="obis_mapping",
    )
    count = 0
    while True:
        run_once(args.dsn, args.tenant_id, mapping_cache, args.read_retries, args.retry_backoff_seconds)
        count += 1
        if args.iterations and count >= args.iterations:
            return 0
        time.sleep(args.interval_seconds)


if __name__ == "__main__":
    sys.exit(main())
