"""
Unit tests for ScopeRefine++ and Adaptive Repair Router.
"""

import pytest
from adapt_manim.core.types import (
    StoryboardSection, VerificationIssue, VerificationTier, IssueSeverity, RepairScope
)
from adapt_manim.core.ledger import SymbolLedgerManager
from adapt_manim.repair.scope_refine import ScopeRefineRepairer
from adapt_manim.repair.router import AdaptiveRepairRouter
from adapt_manim.verification.cascade import VerificationCascade


def test_zero_token_autogrid_resolves_collision():
    initial_code = """
self.place_at_grid(dot1, 'B2')
self.place_at_grid(dot2, 'B2')
"""
    issue = VerificationIssue(
        tier=VerificationTier.TIER4_SPATIAL,
        severity=IssueSeverity.WARNING,
        message="Visual overlap collision at anchor B2. Relocate 'dot2' to nearest vacant anchor B1.",
        line_number=3,
        offending_code="self.place_at_grid(dot2, 'B2')",
        suggested_scope="autogrid"
    )

    repaired, success = ScopeRefineRepairer.repair_zero_token_autogrid(initial_code, issue)
    assert success
    assert "self.place_at_grid(dot2, 'B1')" in repaired


def test_zero_token_migrates_resize():
    code = "obj.resize(0.8)"
    issue = VerificationIssue(
        tier=VerificationTier.TIER1_AST,
        severity=IssueSeverity.CRITICAL,
        message="Deprecated method resize",
        line_number=1,
        offending_code="obj.resize(0.8)",
        suggested_scope="autogrid"
    )
    repaired, success = ScopeRefineRepairer.repair_zero_token_autogrid(code, issue)
    assert success
    assert "obj.scale(0.8)" in repaired

