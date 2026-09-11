"""Prueba control_executor.py con un DlmsSession simulado -- no repite las
pruebas de protocolo de dlms_session (ver test_dlms_session.py)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from control_executor import execute_control_order


class ExecuteControlOrderTests(unittest.TestCase):
    def test_suspension_calls_remote_disconnect(self):
        session = mock.MagicMock()
        with mock.patch("control_executor.GXDLMSDisconnectControl") as ControlCls:
            control_obj = ControlCls.return_value
            control_obj.remoteDisconnect.return_value = b"\x01"

            execute_control_order(session, "0.0.96.3.10.255", "suspension")

            control_obj.remoteDisconnect.assert_called_once_with(session.client)
            control_obj.remoteReconnect.assert_not_called()
            session.invoke_action.assert_called_once_with(b"\x01")

    def test_reconnection_calls_remote_reconnect(self):
        session = mock.MagicMock()
        with mock.patch("control_executor.GXDLMSDisconnectControl") as ControlCls:
            control_obj = ControlCls.return_value
            control_obj.remoteReconnect.return_value = b"\x02"

            execute_control_order(session, "0.0.96.3.10.255", "reconnection")

            control_obj.remoteReconnect.assert_called_once_with(session.client)
            control_obj.remoteDisconnect.assert_not_called()
            session.invoke_action.assert_called_once_with(b"\x02")

    def test_disconnection_also_maps_to_disconnect(self):
        session = mock.MagicMock()
        with mock.patch("control_executor.GXDLMSDisconnectControl") as ControlCls:
            control_obj = ControlCls.return_value

            execute_control_order(session, "0.0.96.3.10.255", "disconnection")

            control_obj.remoteDisconnect.assert_called_once()

    def test_unknown_order_type_raises(self):
        session = mock.MagicMock()
        with self.assertRaises(ValueError):
            execute_control_order(session, "0.0.96.3.10.255", "not-a-real-type")


if __name__ == "__main__":
    unittest.main()
