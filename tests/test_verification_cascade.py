"""
Unit tests for Verification Cascade.
"""

import pytest
from adapt_manim.core.types import (
    StoryboardSection, LectureCue, AnimationStep,
    VerificationTier, IssueSeverity
)
from adapt_manim.core.ledger import SymbolLedgerManager
from adapt_manim.verification.cascade import VerificationCascade
from adapt_manim.verification.tier1_ast import Tier1AstVerifier
from adapt_manim.verification.tier4_spatial import Tier4SpatialVerifier


def test_tier1_catches_deprecated_method():
    code = "obj = Dot()\nobj.resize(0.5)\n"
    issues = Tier1AstVerifier.verify(code)
    assert any(i.tier == VerificationTier.TIER1_AST and i.severity == IssueSeverity.CRITICAL for i in issues)


def test_tier4_detects_collision():
    code = """
self.place_at_grid(cat_icon, 'B2')
self.place_at_grid(formula_label, 'B2')
"""
    issues, table = Tier4SpatialVerifier.verify(code)
    assert any(i.tier == VerificationTier.TIER4_SPATIAL and "collision" in i.message.lower() for i in issues)
    assert len(table.collisions) > 0


def test_cascade_early_exit_on_syntax_error():
    broken_code = "def construct(self):\n   x = [1, 2"
    sec = StoryboardSection(
        id="section_1",
        title="Test Section",
        lecture_lines=["Test statement"],
        animations=["FadeIn dot"]
    )
    ledger_mgr = SymbolLedgerManager("Test")
    report = VerificationCascade.verify_section(
        code=broken_code,
        section=sec,
        ledger_manager=ledger_mgr,
        skip_execution=True
    )
    assert not report.passed
    assert report.highest_failing_tier == VerificationTier.TIER1_AST
