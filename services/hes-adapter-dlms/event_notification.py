"""F05 (Sprint 2, retomado 2026-09-11): recepcion de eventos/alarmas del
medidor via push DLMS/COSEM -- codificacion/decodificacion del mensaje, sin
BD ni socket real (eso vive en `event_listener.py`).

Por que DATA_NOTIFICATION y no EVENT_NOTIFICATION (que es semanticamente el
mecanismo "correcto" segun el Blue Book de DLMS para un evento/alarma
espontaneo): bug real encontrado en gurux-dlms==1.0.203, verificado leyendo
el codigo fuente instalado (mismo metodo que los bugs de
`simulator/dlms_simulator_server.py`) -- `GXDLMS.getData` reconoce
`Command.EVENT_NOTIFICATION` del lado de RECEPCION pero su manejo entero es
un `elif cmd == Command.EVENT_NOTIFICATION: pass` (no-op, ver `GXDLMS.py`
cerca de la linea 2729): el valor nunca se decodifica del otro lado, aunque
`GXDLMSNotify.generateReport` si sabe GENERARLO. El lado de
DATA_NOTIFICATION si esta completo en ambas direcciones
(`generateDataNotificationMessages` para generar +
`handleDataNotification`/`getValueFromData` para recibir) -- verificado con
una prueba real (encode -> bytes reales -> decode, y despues por TCP real con
la escritura partida en dos mitades para forzar reensamblado) antes de
construir el resto de este modulo sobre esto.

Estructura del cuerpo de la notificacion: el Blue Book de DLMS NO especifica
una estructura fija para Data-Notification -- "each manufacturer can send
different data" (ver el docstring de `GXDLMSNotify.addData`). La estructura
de abajo es una eleccion propia de RenfyGrid, documentada aca porque no viene
de ningun estandar:

  1. `meter_server_address` (uint16) -- la direccion DLMS del medidor que
     empuja el evento (la misma `meter.server_address` de la migracion
     0003). Va DENTRO del payload a proposito, no se infiere de la
     direccion de origen del encabezado WRAPPER: un concentrador
     movil/GPRS puede tener IP dinamica y la libreria tampoco expone esa
     direccion de forma confiable para este caso (`checkWrapperAddress`
     solo la registra si el receptor fija su propia direccion esperada de
     antemano, que es justo lo que no podemos hacer con un remitente
     desconocido). El listener resuelve el medidor real con esto, buscando
     dentro del tenant al que esta atado ese proceso (ver `event_listener.py`
     -- mismo patron que `poller.py`: un listener corre por tenant, nunca
     mezcla varios).
  2. `event_code` (uint16) -- codigo de alarma especifico del fabricante,
     se guarda tal cual en `meter_event.detail`. Sin tabla de mapeo todavia
     -- mismo criterio que F17 con los metodos de estimacion (Sprint 4):
     se agrega cuando haya un caso real que lo exija, no antes.
  3. `severity_code` (uint8) -- 0/1/2, mapeado a un severity de
     `meter_event` via `SEVERITY_BY_CODE`. Esto NO es una regla de negocio
     configurable (no es un umbral ni un mapeo OBIS) -- es una
     clasificacion fija de transporte, mismo criterio que un codigo de
     estado HTTP, por eso no vive en BD como `vee_rule`/`obis_mapping`.
"""

from __future__ import annotations

from dataclasses import dataclass

from gurux_dlms import GXByteBuffer, GXDLMSClient, GXDLMSNotify, GXReplyData
from gurux_dlms.enums import Authentication, DataType, InterfaceType
from gurux_dlms.internal._GXCommon import _GXCommon

SEVERITY_BY_CODE = {0: "info", 1: "warning", 2: "critical"}
DEFAULT_UNKNOWN_SEVERITY = "warning"  # fail-safe: un codigo no reconocido nunca se degrada a "info"


class MalformedEventNotificationError(ValueError):
    """El cuerpo de la notificacion no tiene la forma STRUCTURE(3) esperada."""


@dataclass(frozen=True)
class EventNotification:
    meter_server_address: int
    event_code: int
    severity_code: int

    @property
    def severity(self) -> str:
        return SEVERITY_BY_CODE.get(self.severity_code, DEFAULT_UNKNOWN_SEVERITY)


def build_push_messages(
    meter_server_address: int,
    event_code: int,
    severity_code: int,
    *,
    hes_client_address: int = 16,
    meter_wrapper_address: int = 1,
) -> list[bytearray]:
    """Construye el/los mensaje(s) DATA_NOTIFICATION ya enmarcados (WRAPPER),
    listos para escribir directo a un socket -- lo que usaria un
    medidor/concentrador real (o el simulador de pruebas) para empujar un
    evento. `hes_client_address`/`meter_wrapper_address` son solo valores de
    encabezado WRAPPER (framing), no la identidad real del medidor -- esa
    viaja en el payload (ver docstring del modulo)."""
    notify = GXDLMSNotify(True, hes_client_address, meter_wrapper_address, InterfaceType.WRAPPER)
    buff = GXByteBuffer()
    buff.setUInt8(DataType.STRUCTURE)
    _GXCommon.setObjectCount(3, buff)
    _GXCommon.setData(notify.settings, buff, DataType.UINT16, meter_server_address)
    _GXCommon.setData(notify.settings, buff, DataType.UINT16, event_code)
    _GXCommon.setData(notify.settings, buff, DataType.UINT8, severity_code)
    return notify.generateDataNotificationMessages(None, buff)


class EventNotificationDecoder:
    """Decodificador con estado para un stream de bytes que puede llegar
    fragmentado (TCP no garantiza un `recv()` por mensaje) -- alimentar con
    `feed(chunk)` cada vez que llegan bytes nuevos; devuelve `None` hasta que
    el mensaje este completo, y la `EventNotification` decodificada en ese
    momento. Una instancia decodifica un solo mensaje; crear una nueva por
    conexion/mensaje (ver `event_listener.py`)."""

    def __init__(self) -> None:
        # clientAddress=0/serverAddress=0: wildcard -- acepta el mensaje sin
        # importar que direcciones haya puesto el remitente en el encabezado
        # WRAPPER (ver checkWrapperAddress en GXDLMS.py: con clientAddress=0
        # nunca lanza por direcciones que no coinciden, y no necesitamos que
        # coincidan porque la identidad real viaja en el payload).
        self._client = GXDLMSClient(True, 0, 0, Authentication.NONE, None, InterfaceType.WRAPPER)
        self._buff = GXByteBuffer()
        self._reply = GXReplyData()

    def feed(self, chunk: bytes) -> EventNotification | None:
        self._buff.set(bytearray(chunk))
        if not self._client.getData(self._buff, self._reply):
            return None
        value = self._reply.value
        if not (isinstance(value, list) and len(value) == 3):
            raise MalformedEventNotificationError(
                f"Cuerpo de notificacion con forma inesperada (se esperaba STRUCTURE de 3 elementos): {value!r}"
            )
        meter_server_address, event_code, severity_code = value
        return EventNotification(
            meter_server_address=int(meter_server_address),
            event_code=int(event_code),
            severity_code=int(severity_code),
        )


def send_event_notification(
    host: str,
    port: int,
    meter_server_address: int,
    event_code: int,
    severity_code: int,
    *,
    timeout_seconds: float = 5.0,
) -> None:
    """Abre una conexion TCP real y empuja un evento -- lo que haria un
    medidor/concentrador real. Usado por el simulador de eventos y por
    `verify_event_notification_end_to_end.py`, nunca por el listener
    (que solo recibe)."""
    import socket

    messages = build_push_messages(meter_server_address, event_code, severity_code)
    with socket.create_connection((host, port), timeout=timeout_seconds) as sock:
        for message in messages:
            sock.sendall(bytes(bytearray(message)))
