"""Ejecucion real de una orden de control SCR via DLMS/COSEM (F29, Sprint 7)
-- usa el objeto `GXDLMSDisconnectControl` (IC 70) de Gurux, mismo principio
que el resto del adaptador: reusar el protocolo real, no reimplementarlo.

El OBIS del objeto de control es por medidor/marca (llega como parametro,
igual que `obis_code` en `meter_reader.py` -- ver `meter_protocol.obis_mapping`
con una entrada `"control"`, no un OBIS fijo en codigo).
"""

from __future__ import annotations

from gurux_dlms import GXDLMSClient
from gurux_dlms.enums import Authentication, InterfaceType
from gurux_dlms.objects import GXDLMSDisconnectControl
from gurux_net import GXNet
from gurux_net.enums import NetworkType

from dlms_session import DlmsSession

ACTION_BY_ORDER_TYPE = {
    "suspension": "disconnect",
    "disconnection": "disconnect",
    "reconnection": "reconnect",
}


def execute_control_order(session: DlmsSession, control_obis_code: str, order_type: str) -> None:
    """Lanza `ValueError` si `order_type` no mapea a una accion DLMS conocida
    -- no se adivina que hacer con un tipo de orden no reconocido."""
    action = ACTION_BY_ORDER_TYPE.get(order_type)
    if action is None:
        raise ValueError(f"Tipo de orden no soportado para ejecucion SCR: {order_type!r}")

    control_object = GXDLMSDisconnectControl(control_obis_code)
    if action == "disconnect":
        request = control_object.remoteDisconnect(session.client)
    else:
        request = control_object.remoteReconnect(session.client)
    session.invoke_action(request)


def dispatch_control_order(
    host: str,
    port: int,
    client_address: int,
    server_address: int,
    control_obis_code: str,
    order_type: str,
) -> None:
    """Punto de entrada de alto nivel para el modulo SCR (Sprint 7, F29):
    abre la conexion DLMS, se asocia, ejecuta la accion y cierra -- mismo
    ciclo de vida que `main.py`, empaquetado en una sola llamada para que
    `services/control` no tenga que conocer `GXNet`/`DlmsSession` -- el
    modulo SCR "unicamente habla con los adaptadores HES"
    (docs/02-arquitectura-general.md SS6, punto 4), esta funcion es esa
    frontera."""
    media = GXNet(NetworkType.TCP, host, port)
    client = GXDLMSClient(True, client_address, server_address, Authentication.NONE, None, InterfaceType.WRAPPER)
    media.open()
    try:
        session = DlmsSession(client=client, media=media)
        session.associate()
        execute_control_order(session, control_obis_code, order_type)
        session.disconnect()
    finally:
        media.close()
