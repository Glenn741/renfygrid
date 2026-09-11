"""Prueba audited_communication con log_communication mockeado -- no toca BD."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import communication_audit
from communication_audit import audited_communication


class AuditedCommunicationTests(unittest.TestCase):
    def test_success_logs_success_true(self):
        conn = mock.MagicMock()
        with mock.patch.object(communication_audit, "log_communication") as log_mock:
            with audited_communication(conn, "tenant-1", "meter-1", "poller_read"):
                pass

        log_mock.assert_called_once()
        args, kwargs = log_mock.call_args
        self.assertEqual(args[:4], (conn, "tenant-1", "meter-1", "poller_read"))
        self.assertTrue(kwargs["success"])
        self.assertIsNone(kwargs.get("error"))

    def test_failure_logs_success_false_and_reraises(self):
        conn = mock.MagicMock()
        with mock.patch.object(communication_audit, "log_communication") as log_mock:
            with self.assertRaises(ValueError):
                with audited_communication(conn, "tenant-1", "meter-1", "poller_read"):
                    raise ValueError("boom")

        log_mock.assert_called_once()
        _, kwargs = log_mock.call_args
        self.assertFalse(kwargs["success"])
        self.assertEqual(kwargs["error"], "boom")


if __name__ == "__main__":
    unittest.main()
