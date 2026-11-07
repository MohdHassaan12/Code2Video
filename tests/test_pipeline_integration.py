"""
End-to-end integration tests for AdaptManim pipeline.
"""

import pytest
import os
from adapt_manim.core.types import AudienceLevel
from adapt_manim.core.ledger import SymbolLedgerManager
from adapt_manim.planning.outline_planner import OutlinePlanner
from adapt_manim.planning.storyboard_builder import StoryboardBuilder
from adapt_manim.coding.coder import ManimCoder
from adapt_manim.verification.cascade import VerificationCascade
from adapt_manim.evaluation.aesthetic_judge import AestheticJudge
from adapt_manim.evaluation.teach_quiz import TeachQuizEvaluator


def test_full_pipeline_synthesis():
    topic = "Support Vector Machine"
    audience = AudienceLevel.UNDERGRADUATE

    # 1. Planning
    outline = OutlinePlanner.generate_outline(topic, audience)
    assert len(outline.sections) >= 2

    # 2. Memory / Ledger
    ledger_mgr = SymbolLedgerManager(topic)
    assert len(ledger_mgr.ledger.symbols) > 0

    # 3. Storyboard
    storyboard = StoryboardBuilder.build_storyboard(outline, ledger_mgr)
    assert len(storyboard.sections) == len(outline.sections)

    # 4. Code Generation
    sec = storyboard.sections[0]
    code = ManimCoder.generate_section_code(sec, ledger_mgr)
    assert "class " in code
    assert "TeachingScene" in code
    assert "self.place_at_grid" in code or "self.place_in_area" in code

    # 5. Verification Cascade (headless render)
    report = VerificationCascade.verify_section(
        code=code,
        section=sec,
        ledger_manager=ledger_mgr,
        output_dir="demo_outputs",
        skip_execution=False
    )
    assert report.passed
    assert report.execution_time_sec > 0

    # 6. Aesthetics and TeachQuiz Evaluation
    qm = AestheticJudge.evaluate(code, topic)
    assert qm.overall_aes >= 70.0

    tq = TeachQuizEvaluator.evaluate_relative_gain(topic, is_video_grounded=True, pedagogical_score=qm.overall_aes)
    assert tq["es_gain"] > 50.0
