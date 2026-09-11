"""Lectura remota bajo demanda (F04, Sprint 8): mismo pipeline que `main.py`
(un solo medidor, un solo canal) pero resolviendo la conexion del gateway y
el mapeo OBIS desde BD en vez de recibirlos por argumento -- pensado para
que el Portal/API lo llame por un medidor puntual, no para correr como
proceso aparte (ver `poller.py`, que es la version programada de esto).
"""

from __future__ import annotations

import sys
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
from meter_reader import NormalizedReading, read_register  # noqa: E402
from reading_store import insert_raw_reading  # noqa: E402
from renmeter_common.db import tenant_scope  # noqa: E402


class MeterNotReadableError(RuntimeError):
    """Al medidor le falta conexion de gateway o mapeo OBIS del canal pedido."""


def _meter_connection_and_mapping(conn: psycopg.Connection, tenant_id: str, meter_id: str, channel: str) -> dict:
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT m.server_address, g.connection, mp.obis_mapping "
                    "FROM meter m "
                    "JOIN meter_gateway mg ON mg.meter_id = m.id "
                    "JOIN gateway g ON g.id = mg.gateway_id "
                    "JOIN meter_protocol mp ON mp.tenant_id = m.tenant_id "
                    "  AND mp.brand = m.brand AND mp.model = m.model AND mp.valid_to IS NULL "
                    "WHERE m.id = %s",
                    (meter_id,),
                )
                row = cur.fetchone()
                if row is None:
                    raise MeterNotReadableError(f"Medidor {meter_id} sin gateway/mapeo OBIS configurado")
                server_address, connection, obis_mapping = row
                channel_mapping = obis_mapping.get(channel)
                if channel_mapping is None:
                    raise MeterNotReadableError(f"Medidor {meter_id} sin mapeo OBIS para el canal '{channel}'")
                return {
                    "server_address": server_address,
                    "host": connection["host"],
                    "port": connection["port"],
                    "client_address": connection.get("client_address", 16),
                    "obis_code": channel_mapping["obis_code"],
                    "attribute_index": channel_mapping.get("attribute_index", 2),
                }


def read_meter_now(
    conn: psycopg.Connection, tenant_id: str, meter_id: str, channel: str, requested_by: str | None = None
) -> NormalizedReading:
    """Lee AHORA (no espera al proximo ciclo del poller) y guarda el
    resultado en `raw_reading` igual que cualquier otra lectura real.
    `requested_by` (Sprint C5) queda en la auditoria para el panel de
    Integraciones/Service Orders -- ver `communication_audit.py`."""
    target = _meter_connection_and_mapping(conn, tenant_id, meter_id, channel)

    with audited_communication(conn, tenant_id, meter_id, "on_demand_read", requested_by=requested_by):
        media = GXNet(NetworkType.TCP, target["host"], target["port"])
        client = GXDLMSClient(
            True, target["client_address"], target["server_address"], Authentication.NONE, None, InterfaceType.WRAPPER
        )
        media.open()
        try:
            session = DlmsSession(client=client, media=media)
            session.associate()
            reading = read_register(session, meter_id, target["obis_code"], channel, target["attribute_index"])
            session.disconnect()
        finally:
            media.close()

        insert_raw_reading(conn, tenant_id, reading)
    return reading
