"""Prueba la ORQUESTACION de dlms_session.py (reintentos, secuencia de
asociacion) con un GXDLMSClient y un medio simulados (unittest.mock) --
NO prueba el protocolo DLMS/COSEM en si (eso lo prueba/garantiza Gurux), y NO
reemplaza una verificacion real contra un medidor/simulador (ver el docstring
de dlms_session.py y docs/05-ejecucion.md Sprint 1).

Correr con:  python -m unittest discover -s tests -v
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "common"))

from gurux_dlms.enums import Authentication, InterfaceType

from dlms_session import ActionError, DlmsSession, TimeoutError_


def make_session(**client_overrides) -> tuple[DlmsSession, mock.MagicMock, mock.MagicMock]:
    client = mock.MagicMock()
    client.interfaceType = InterfaceType.WRAPPER
    client.authentication = Authentication.NONE
    for key, value in client_overrides.items():
        setattr(client, key, value)
    media = mock.MagicMock()
    # MagicMock.__exit__ devuelve un MagicMock (truthy) por defecto, lo que
    # suprimiria cualquier excepcion lanzada dentro de "with media.getSynchronous():"
    # -- se fuerza False para que las excepciones (ej. TimeoutError_) sigan
    # propagando, como pasa con el gurux_net.GXNet real.
    media.getSynchronous.return_value.__exit__.return_value = False
    session = DlmsSession(client=client, media=media, max_retries=3)
    return session, client, media


class SendAndReceiveTests(unittest.TestCase):
    def test_no_data_does_nothing(self):
        session, client, media = make_session()
        session._send_and_receive(None, mock.MagicMock())
        media.send.assert_not_called()

    def test_happy_path_needs_no_receive_round(self):
        """Si getData ya da la respuesta completa sin recibir mas bytes, no se
        llama a media.receive -- caso feliz minimo."""
        session, client, media = make_session()
        client.getData.return_value = True
        reply = mock.MagicMock()
        reply.data.size = 0

        session._send_and_receive(b"\x01\x02", reply)

        media.send.assert_called_once_with(b"\x01\x02")
        media.receive.assert_not_called()

    def test_one_receive_round_completes_the_reply(self):
        session, client, media = make_session()
        client.getData.side_effect = [False, True]

        def fake_receive(params):
            params.reply = b"fake-bytes"
            return True

        media.receive.side_effect = fake_receive
        reply = mock.MagicMock()
        reply.data.size = 0

        session._send_and_receive(b"\x01", reply)

        self.assertEqual(media.receive.call_count, 1)
        self.assertEqual(media.send.call_count, 1)

    def test_gives_up_after_max_retries_and_raises(self):
        session, client, media = make_session()
        client.getData.return_value = False
        media.receive.return_value = False
        reply = mock.MagicMock()
        reply.data.size = 0

        with self.assertRaises(TimeoutError_):
            session._send_and_receive(b"\x01", reply)

        self.assertEqual(media.receive.call_count, 3)


class AssociateTests(unittest.TestCase):
    def test_skips_application_association_for_authentication_none(self):
        """Con Authentication.NONE (<= LOW) no debe llamarse
        getApplicationAssociationRequest -- ver dlms_session.associate()."""
        session, client, media = make_session()
        client.snrmRequest.return_value = b"\x7e...snrm...\x7e"
        client.aarqRequest.return_value = b"\x03\x00...aarq..."
        client.getData.return_value = True

        session.associate()

        client.parseUAResponse.assert_called_once()
        client.parseAareResponse.assert_called_once()
        client.getApplicationAssociationRequest.assert_not_called()

    def test_skips_snrm_when_client_does_not_need_it(self):
        """Algunos interfaces (ej. WRAPPER puro sobre TCP) no requieren SNRM --
        snrmRequest() puede devolver None/vacio y no se debe intentar parsear UA."""
        session, client, media = make_session()
        client.snrmRequest.return_value = None
        client.aarqRequest.return_value = b"\x03\x00...aarq..."
        client.getData.return_value = True

        session.associate()

        client.parseUAResponse.assert_not_called()
        client.parseAareResponse.assert_called_once()


class ReadAttributeTests(unittest.TestCase):
    def test_reads_and_updates_the_object_value(self):
        session, client, media = make_session()
        client.read.return_value = b"\x01\x02"
        client.getData.return_value = True
        dlms_object = mock.MagicMock()
        dlms_object.value = 4781999

        result = session.read_attribute(dlms_object, 2)

        client.read.assert_called_once_with(dlms_object, 2)
        client.updateValue.assert_called_once()
        self.assertEqual(result, 4781999)


class InvokeActionTests(unittest.TestCase):
    def test_successful_action_does_not_raise(self):
        session, client, media = make_session()
        client.getData.return_value = True

        session.invoke_action(b"\x01\x02")  # no debe lanzar

    def test_error_response_raises_action_error(self):
        session, client, media = make_session()

        def fake_get_data(rd, reply, notify):
            reply.error = 3  # cualquier codigo de error DLMS != 0
            return True

        client.getData.side_effect = fake_get_data

        with self.assertRaises(ActionError):
            session.invoke_action(b"\x01\x02")


if __name__ == "__main__":
    unittest.main()
