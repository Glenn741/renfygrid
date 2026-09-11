"""F07 (Sprint C5, `docs/06-benchmark-e2e-y-brechas.md` SS2/G2): "ping" --
confirma que el medidor responde sin leer ningun registro, solo la
asociacion DLMS (SNRM/UA + AARQ/AARE) y el cierre ordenado. Es el comando
mas liviano del set estandar de la industria (connect/disconnect/ping/
lectura bajo demanda) -- un CIS externo puede confirmar que un
concentrador esta vivo sin pagar el costo de una lectura completa, y sin
que RenfyGrid tuviera antes ninguna forma de responder eso salvo leyendo
un canal real.
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
from renmeter_common.db import tenant_scope  # noqa: E402


class MeterNotReachableError(RuntimeError):
    """Al medidor le falta conexion de gateway configurada -- no hay a
    donde mandar el ping. Distinto de un ping que sí se intento y fallo
    (esa falla queda auditada igual y se propaga tal cual, mismo criterio
    que `on_demand_reader.read_meter_now`)."""


def _meter_connection(conn: psycopg.Connection, tenant_id: str, meter_id: str) -> dict:
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT m.server_address, g.connection "
                    "FROM meter m "
                    "JOIN meter_gateway mg ON mg.meter_id = m.id "
                    "JOIN gateway g ON g.id = mg.gateway_id "
                    "WHERE m.id = %s",
                    (meter_id,),
                )
                row = cur.fetchone()
                if row is None:
                    raise MeterNotReachableError(f"Medidor {meter_id} sin gateway configurado")
                server_address, connection = row
                return {
                    "server_address": server_address,
                    "host": connection["host"],
                    "port": connection["port"],
                    "client_address": connection.get("client_address", 16),
                }


def ping_meter(conn: psycopg.Connection, tenant_id: str, meter_id: str, requested_by: str | None = None) -> bool:
    """Abre una asociacion DLMS real contra el gateway del medidor y la
    cierra de inmediato -- sin leer ningun objeto COSEM. Devuelve `True`
    si respondio; si no respondio o el medidor la rechazo, la excepcion
    real (timeout, rechazo de asociacion) se propaga tal cual -- la
    auditoria del intento fallido ya quedo escrita por
    `audited_communication` antes de que la excepcion llegue hasta el
    llamador (mismo criterio que `read_meter_now`)."""
    target = _meter_connection(conn, tenant_id, meter_id)

    with audited_communication(conn, tenant_id, meter_id, "ping", requested_by=requested_by):
        media = GXNet(NetworkType.TCP, target["host"], target["port"])
        client = GXDLMSClient(
            True, target["client_address"], target["server_address"], Authentication.NONE, None, InterfaceType.WRAPPER
        )
        media.open()
        try:
            session = DlmsSession(client=client, media=media)
            session.associate()
            session.disconnect()
        finally:
            media.close()
    return True
