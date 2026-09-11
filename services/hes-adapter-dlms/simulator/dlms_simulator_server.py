"""Simulador DLMS/COSEM minimo, para poder verificar el adaptador HES real
(dlms_session.py/meter_reader.py/main.py) de punta a punta -- sin necesitar
hardware ni el simulador oficial de Gurux (Gurux.DLMS.Simulator.Net, que
requiere .NET SDK, no disponible en este entorno).

Reusa el protocolo servidor REAL de Gurux (gurux_dlms.GXDLMSServer: parseo de
SNRM/AARQ/GET a nivel de bytes) -- lo unico que se escribe aqui es el "meollo"
de negocio de un medidor de prueba: que objetos COSEM existen y que valor
tiene cada uno. Mismo principio que el resto de RenfyGrid
(docs/02-arquitectura-general.md SS1, principio 5): no reimplementar lo que
Gurux ya resolvio.

BUGS REALES encontrados en gurux-dlms==1.0.203 (paquete pip, version mas
reciente disponible), verificados leyendo el codigo fuente instalado y
reproduciendo cada uno de forma aislada -- documentados aqui porque los
parches de abajo dependen de ellos y desaparecen si Gurux los corrige en una
version futura:

1. `GXDLMSServer.handleRequest` llama a `sr.setReply(...)` y
   `sr.getConnectionInfo()` sobre una instancia de `GXServerReply`, pero esa
   clase (gurux_dlms/GXServerReply.py) no define ninguno de los dos metodos
   -- solo tiene el atributo `reply` y `connectionInfo`. Sin parche, CUALQUIER
   solicitud (asociacion o lectura) revienta con AttributeError, silenciada
   por el propio `except Exception` de `handleRequest` (no se ve el error,
   simplemente no llega respuesta). Parche: agregar ambos metodos como alias
   simples de los atributos existentes.
2. `GXDLMSServer.initialize()` crea el objeto de asociacion automaticamente
   si no se agrego uno explicito, con
   `ln.objectList.append(self.items)` -- pero `.append()` exige un
   `GXDLMSObject` individual, no una coleccion completa, y lanza `TypeError`.
   Evitado creando nosotros mismos el `GXDLMSAssociationLogicalName` con
   `objectList.extend(...)` (que si acepta una coleccion) antes de llamar a
   `initialize()`.
3. `notifyRead()` se invoca desde `GXDLMSLNCommandHandler` en el camino de un
   GET de un solo atributo sin seleccion (el caso de un `Register` comun, que
   es exactamente lo que hace `meter_reader.py`) pero no existe ningun
   default en `GXDLMSServer` -- cada subclase debe definirlo. Se define aqui
   como no-op.
4. (Sprint 7) `GXDLMSLNCommandHandler` llama a `server.onPreAction(list(e))`
   para CUALQUIER accion/metodo COSEM (ej. remoteDisconnect/remoteReconnect
   de un `GXDLMSDisconnectControl`) -- pero `list(e)` intenta ITERAR el
   `ValueEventArgs e`, que no implementa `__iter__`. Sin parche, cualquier
   accion revienta con `TypeError` antes de que nuestro propio `onPreAction`
   llegue a ejecutarse. Parche: agregar `__iter__` a `ValueEventArgs` (devuelve
   `[self]`, que es lo que el resto de los call sites de Gurux ya hacen a mano
   en otros puntos del mismo archivo, ej. `server.onPreRead([arg])`).

Los cuatro se verificaron reproduciendo un handshake completo (AARQ/AARE + GET
o accion) en proceso antes de escribir este servidor real -- ver
docs/05-ejecucion.md Sprint 1 y Sprint 7 para el detalle completo. Este
archivo es un DOBLE DE PRUEBA, no
tiene ninguna intencion de ser un medidor DLMS conforme a todos los casos de
uso del estandar (ej. `isTarget`/`onValidateAuthentication` aceptan cualquier
conexion, sin las verificaciones de seguridad que si tiene el resto de
RenfyGrid en su propio dominio -- eso vive en `control_order`/RLS, no aqui).
"""

from __future__ import annotations

import argparse
import socket
import threading

from gurux_dlms import GXByteBuffer, GXDLMSServer, GXServerReply, ValueEventArgs
from gurux_dlms.enums import (
    AccessMode,
    ErrorCode,
    InterfaceType,
    MethodAccessMode,
    SourceDiagnostic,
)
from gurux_dlms.objects import (
    GXDLMSAssociationLogicalName,
    GXDLMSDisconnectControl,
    GXDLMSRegister,
)

if not hasattr(GXServerReply, "setReply"):
    GXServerReply.setReply = lambda self, value: setattr(self, "reply", value)
if not hasattr(GXServerReply, "getConnectionInfo"):
    GXServerReply.getConnectionInfo = lambda self: self.connectionInfo
if not hasattr(ValueEventArgs, "__iter__"):
    ValueEventArgs.__iter__ = lambda self: iter([self])


class _SimulatedDisconnectControl(GXDLMSDisconnectControl):
    """`remoteDisconnect`/`remoteReconnect` (metodos 1/2, ver Gurux) llegan
    aca via `invoke()` -- el punto de extension real que Gurux deja para que
    cada dispositivo defina que hace (la implementacion de la libreria en si
    solo lanza `ValueError`, es responsabilidad del firmware/simulador)."""

    def __init__(self, ln: str):
        super().__init__(ln)
        self.is_connected = True

    def invoke(self, settings, e):
        if e.index == 1:
            self.is_connected = False
        elif e.index == 2:
            self.is_connected = True
        else:
            e.error = ErrorCode.READ_WRITE_DENIED
        return None


class SimulatedMeterServer(GXDLMSServer):
    """Un medidor DLMS/COSEM de prueba con un `Register` (OBIS/valor
    configurables) y, opcionalmente, un `DisconnectControl` (Sprint 7, F29 --
    suspension/reconexion real via DLMS) -- alcanza para que un cliente real
    se asocie, lea, y ejecute un comando de control."""

    def __init__(self, obis_code: str, initial_value: int, control_obis_code: str | None = None):
        super().__init__(True, InterfaceType.WRAPPER)
        register = GXDLMSRegister(obis_code)
        register.value = initial_value
        self.items.append(register)
        self.control: _SimulatedDisconnectControl | None = None
        if control_obis_code:
            self.control = _SimulatedDisconnectControl(control_obis_code)
            self.items.append(self.control)
        association = GXDLMSAssociationLogicalName()
        association.objectList.extend(self.items)
        self.items.append(association)
        self.initialize()

    def notifyRead(self):
        pass

    def isTarget(self, serverAddress, clientAddress):
        return True

    def onValidateAuthentication(self, authentication, password):
        return SourceDiagnostic.NONE

    def onFindObject(self, objectType, sn, ln):
        return None

    def onGetAttributeAccess(self, arg):
        return AccessMode.READ

    def onGetMethodAccess(self, arg):
        return MethodAccessMode.ACCESS

    def onPreRead(self, args=None):
        pass

    def onPostRead(self, args=None):
        pass

    def onPreWrite(self, args=None):
        pass

    def onPostWrite(self, args=None):
        pass

    def onPreGet(self, args=None):
        pass

    def onPostGet(self, args=None):
        pass

    def onPreAction(self, args=None):
        pass

    def onPostAction(self, args=None):
        pass

    def onConnected(self, connectionInfo):
        pass

    def onDisconnected(self, connectionInfo):
        pass

    def onInvalidConnection(self, connectionInfo):
        pass


def _serve_one_connection(server: SimulatedMeterServer, conn: socket.socket) -> None:
    with conn:
        while True:
            chunk = conn.recv(4096)
            if not chunk:
                return
            sr = GXServerReply(GXByteBuffer(chunk))
            server.handleRequest(sr)
            if sr.reply:
                conn.sendall(bytes(bytearray(sr.reply)))


def serve(
    host: str,
    port: int,
    obis_code: str,
    initial_value: int,
    control_obis_code: str | None = None,
    server: SimulatedMeterServer | None = None,
) -> None:
    """Corre indefinidamente, aceptando una conexion de cliente a la vez
    (alcanza para pruebas -- no es un simulador multi-cliente concurrente).
    `server` ya construido es para cuando el llamador necesita inspeccionar
    su estado despues (ej. `server.control.is_connected`, ver
    `serve_in_background` y `verify_control_execution_end_to_end.py`)."""
    if server is None:
        server = SimulatedMeterServer(obis_code, initial_value, control_obis_code)
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind((host, port))
        listener.listen(1)
        print(f"Simulador DLMS escuchando en {host}:{port} (OBIS {obis_code}={initial_value})")
        while True:
            conn, addr = listener.accept()
            print(f"Conexion aceptada desde {addr}")
            _serve_one_connection(server, conn)
            print(f"Conexion cerrada: {addr}")


def serve_in_background(
    host: str, port: int, obis_code: str, initial_value: int, control_obis_code: str | None = None
) -> tuple[threading.Thread, SimulatedMeterServer]:
    """Para pruebas automatizadas: corre `serve()` en un hilo daemon y
    devuelve `(hilo, instancia del servidor)` -- la instancia sirve para
    inspeccionar estado despues (ej. `server.control.is_connected`). Usar
    junto con un `time.sleep` corto o un retry-connect en el llamador, no
    hay senal explicita de 'listo'."""
    server = SimulatedMeterServer(obis_code, initial_value, control_obis_code)
    thread = threading.Thread(
        target=serve, args=(host, port, obis_code, initial_value, control_obis_code), kwargs={"server": server}, daemon=True
    )
    thread.start()
    return thread, server


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--obis-code", required=True)
    parser.add_argument("--value", type=int, required=True)
    parser.add_argument("--control-obis-code", default=None)
    return parser.parse_args(argv)


if __name__ == "__main__":
    args = parse_args()
    serve(args.host, args.port, args.obis_code, args.value, args.control_obis_code)
