"""Pruebas puras de codificacion/decodificacion del push de eventos (F05) --
sin BD, sin socket real. La ida-y-vuelta usa la libreria Gurux real (no un
mock del protocolo): construye bytes DATA_NOTIFICATION reales y los
decodifica, igual que se hizo para confirmar el mecanismo antes de escribir
`event_listener.py` (ver docstring de `event_notification.py`)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from event_notification import (  # noqa: E402
    EventNotificationDecoder,
    MalformedEventNotificationError,
    SEVERITY_BY_CODE,
    build_push_messages,
)


class BuildAndDecodeRoundTripTests(unittest.TestCase):
    def test_round_trip_single_feed(self):
        messages = build_push_messages(meter_server_address=1001, event_code=42, severity_code=2)
        decoder = EventNotificationDecoder()
        event = None
        for message in messages:
            event = decoder.feed(bytes(bytearray(message)))
        self.assertIsNotNone(event)
        self.assertEqual(event.meter_server_address, 1001)
        self.assertEqual(event.event_code, 42)
        self.assertEqual(event.severity_code, 2)

    def test_round_trip_fragmented_feed(self):
        """El mensaje llega partido en dos mitades -- TCP no garantiza un
        recv() por mensaje, el decodificador debe reensamblarlo."""
        (message,) = build_push_messages(meter_server_address=7, event_code=99, severity_code=0)
        data = bytes(bytearray(message))
        half = len(data) // 2
        decoder = EventNotificationDecoder()
        self.assertIsNone(decoder.feed(data[:half]))
        event = decoder.feed(data[half:])
        self.assertIsNotNone(event)
        self.assertEqual(event.meter_server_address, 7)
        self.assertEqual(event.event_code, 99)
        self.assertEqual(event.severity_code, 0)

    def test_severity_mapping_known_codes(self):
        for code, name in SEVERITY_BY_CODE.items():
            (message,) = build_push_messages(meter_server_address=1, event_code=1, severity_code=code)
            decoder = EventNotificationDecoder()
            event = decoder.feed(bytes(bytearray(message)))
            self.assertEqual(event.severity, name)

    def test_unknown_severity_code_defaults_to_warning_not_info(self):
        """Fail-safe: un codigo de severidad no reconocido nunca se degrada
        a 'info' -- mismo criterio que F12 (retencion) nunca borra datos por
        default."""
        (message,) = build_push_messages(meter_server_address=1, event_code=1, severity_code=99)
        decoder = EventNotificationDecoder()
        event = decoder.feed(bytes(bytearray(message)))
        self.assertEqual(event.severity, "warning")

    def test_two_independent_messages_need_two_decoders(self):
        (first,) = build_push_messages(meter_server_address=1, event_code=10, severity_code=0)
        (second,) = build_push_messages(meter_server_address=2, event_code=20, severity_code=1)
        decoder_a = EventNotificationDecoder()
        decoder_b = EventNotificationDecoder()
        event_a = decoder_a.feed(bytes(bytearray(first)))
        event_b = decoder_b.feed(bytes(bytearray(second)))
        self.assertEqual((event_a.meter_server_address, event_a.event_code), (1, 10))
        self.assertEqual((event_b.meter_server_address, event_b.event_code), (2, 20))


class MalformedBodyTests(unittest.TestCase):
    def test_wrong_shape_raises_instead_of_guessing(self):
        """Un cuerpo DATA_NOTIFICATION que no es la STRUCTURE(3) esperada
        (ej. de otro fabricante, o corrupto) debe fallar explicito, no
        intentar adivinar una interpretacion."""
        from gurux_dlms import GXByteBuffer, GXDLMSNotify
        from gurux_dlms.enums import DataType, InterfaceType
        from gurux_dlms.internal._GXCommon import _GXCommon

        notify = GXDLMSNotify(True, 16, 1, InterfaceType.WRAPPER)
        buff = GXByteBuffer()
        buff.setUInt8(DataType.STRUCTURE)
        _GXCommon.setObjectCount(1, buff)
        _GXCommon.setData(notify.settings, buff, DataType.UINT16, 123)
        (message,) = notify.generateDataNotificationMessages(None, buff)

        decoder = EventNotificationDecoder()
        with self.assertRaises(MalformedEventNotificationError):
            decoder.feed(bytes(bytearray(message)))


if __name__ == "__main__":
    unittest.main()
