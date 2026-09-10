"""Sesion DLMS/COSEM minima sobre gurux-dlms -- adaptada del cliente de referencia
oficial de Gurux (Gurux.DLMS.Client.Example.python/GXDLMSReader.py), recortada a lo
esencial: asociacion (SNRM/UA + AARQ/AARE) y una lectura de un objeto via GET.

Por que adaptar el ejemplo de Gurux en vez de escribir el protocolo desde cero:
mismo principio que el resto de RenfyGrid (docs/02-arquitectura-general.md SS1,
principio 5) -- Gurux ya resolvio el framing/reintentos/reensamblado de tramas,
reimplementarlo a mano seria repetir trabajo ya hecho y probado.

ESTADO REAL (ver docs/05-ejecucion.md, Sprint 1): este modulo compila y sus
piezas de orquestacion estan probadas con un cliente/medio simulados (ver
tests/), pero **no se probo todavia contra un medidor o simulador DLMS/COSEM
real** -- no hay hardware ni un simulador Gurux disponible en este entorno
(Gurux.DLMS.Simulator.Net requiere .NET SDK, no instalado). El protocolo en si
(SNRM/AARQ/framing) es exactamente el que usa el cliente de referencia oficial
de Gurux, no una reimplementacion propia -- lo que falta verificar es la
integracion end-to-end con un peer DLMS real, no la logica de este modulo.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from gurux_common import ReceiveParameters
from gurux_dlms import GXByteBuffer, GXDLMSClient, GXReplyData
from gurux_dlms.enums import Authentication, InterfaceType


class Media(Protocol):
    """Lo minimo que dlms_session necesita de un medio de transporte (TCP real via
    gurux_net.GXNet, o un doble de prueba en tests/)."""

    def open(self) -> None: ...
    def close(self) -> None: ...
    def send(self, data: Any, receiver: Any = None) -> None: ...
    def receive(self, args: ReceiveParameters) -> bool: ...


class TimeoutError_(RuntimeError):
    """El peer no respondio dentro de los reintentos permitidos."""


@dataclass
class DlmsSession:
    """Una sesion DLMS/COSEM: un GXDLMSClient + un medio de transporte ya abierto.

    `client` y `media` se inyectan (no se construyen adentro) para poder probar
    la orquestacion con dobles de prueba -- mismo patron de dependency injection
    que ConfigCache.fetch_fn (services/common/renmeter_common/config_cache.py).
    """

    client: GXDLMSClient
    media: Media
    wait_time: int = 5000
    max_retries: int = 3

    def _send_and_receive(self, data, reply: GXReplyData) -> None:
        """Adaptado de GXDLMSReader.readDLMSPacket2 (ver docstring del modulo)."""
        if not data:
            return
        notify = GXReplyData()
        reply.error = 0
        eop = None if self.client.interfaceType == InterfaceType.WRAPPER else 0x7E
        params = ReceiveParameters()
        params.eop = eop
        params.allData = True
        params.waitTime = self.wait_time
        params.count = 8 if eop is None else 5
        rd = GXByteBuffer()
        self.media.send(data)
        pos = 0
        while not self.client.getData(rd, reply, notify):
            if notify.data.size != 0:
                if not notify.isMoreData():
                    notify.clear()
                continue
            if eop is not None:
                params.count = self.client.getFrameSize(rd)
            while not self.media.receive(params):
                pos += 1
                if pos == self.max_retries:
                    raise TimeoutError_(
                        "El medidor/simulador no respondio dentro de los reintentos permitidos."
                    )
                self.media.send(data)
            rd.set(params.reply)
            params.reply = None

    def _read_data_block(self, data, reply: GXReplyData) -> None:
        if not data:
            return
        if isinstance(data, list):
            for part in data:
                reply.clear()
                self._read_data_block(part, reply)
            return
        self._send_and_receive(data, reply)
        while reply.isMoreData():
            data = None if reply.isStreaming() else self.client.receiverReady(reply)
            self._send_and_receive(data, reply)

    def associate(self) -> None:
        """SNRM/UA + AARQ/AARE -- deja la sesion lista para leer/escribir."""
        reply = GXReplyData()
        data = self.client.snrmRequest()
        if data:
            self._send_and_receive(data, reply)
            self.client.parseUAResponse(reply.data)
        reply.clear()
        self._read_data_block(self.client.aarqRequest(), reply)
        self.client.parseAareResponse(reply.data)
        reply.clear()
        if self.client.authentication > Authentication.LOW:
            for part in self.client.getApplicationAssociationRequest():
                self._send_and_receive(part, reply)
            self.client.parseApplicationAssociationResponse(reply.data)

    def read_attribute(self, dlms_object, attribute_index: int) -> Any:
        """Lee un atributo de un objeto COSEM (ej. un GXDLMSRegister) y devuelve
        el valor ya actualizado en el objeto (dlms_object.value o equivalente)."""
        reply = GXReplyData()
        self._read_data_block(self.client.read(dlms_object, attribute_index), reply)
        self.client.updateValue(dlms_object, attribute_index, reply.value)
        return dlms_object.value

    def disconnect(self) -> None:
        reply = GXReplyData()
        self._send_and_receive(self.client.disconnectRequest(), reply)
