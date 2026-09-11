"""Pruebas puras de control_engine -- sin BD."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from control_engine import ApprovalLevel, approval_level_for, can_approve, status_after_request


class ApprovalLevelForTests(unittest.TestCase):
    def test_no_configured_level_defaults_to_requiring_human_approval(self):
        """Fail-safe: sin configuracion, nunca se auto-aprueba."""
        approval = approval_level_for("suspension", levels=[])
        self.assertTrue(approval.requires_human_approval)

    def test_configured_level_is_respected(self):
        levels = [{"order_type": "reconnection", "requires_human_approval": False, "min_required_role": "operator"}]
        approval = approval_level_for("reconnection", levels)
        self.assertFalse(approval.requires_human_approval)

    def test_only_matches_the_requested_order_type(self):
        levels = [{"order_type": "suspension", "requires_human_approval": False, "min_required_role": "operator"}]
        approval = approval_level_for("reconnection", levels)
        self.assertTrue(approval.requires_human_approval)  # sin match, fail-safe


class StatusAfterRequestTests(unittest.TestCase):
    def test_requires_approval_goes_to_pending_approval(self):
        approval = ApprovalLevel(requires_human_approval=True, min_required_role="supervisor")
        self.assertEqual(status_after_request(approval), "pending_approval")

    def test_no_approval_needed_goes_straight_to_approved(self):
        approval = ApprovalLevel(requires_human_approval=False, min_required_role="operator")
        self.assertEqual(status_after_request(approval), "approved")


class CanApproveTests(unittest.TestCase):
    def test_exact_role_match_can_approve(self):
        approval = ApprovalLevel(requires_human_approval=True, min_required_role="supervisor")
        self.assertTrue(can_approve("supervisor", approval))

    def test_different_role_cannot_approve(self):
        approval = ApprovalLevel(requires_human_approval=True, min_required_role="supervisor")
        self.assertFalse(can_approve("operator", approval))


if __name__ == "__main__":
    unittest.main()
