"""
Tests for Dead-Hold Motion Budget Monitor & Dynamic Telestration (Direction D9+).
Verifies:
1. Active motion density analysis (percentage of active half-seconds).
2. Dead-hold detection for static intervals exceeding 2.5s.
3. 0-token dynamic telestration injection (breaking dead holds into subtle Indicate pulses).
4. Channel scoring integration (grounding & motion budget predicting visual uplift).
"""

import pytest
from code2video.motion_budget import MotionBudgetMonitor, DeadHoldSpan, MotionBudgetReport
from code2video.channel_scoring import MultimodalChannelScorer


def test_motion_budget_dense_animation():
    dense_code = """from manim import *

class DenseScene(Scene):
    def construct(self):
        dot = Dot()
        circle = Circle()
        self.play(Create(dot), run_time=1.0)
        self.play(Create(circle), run_time=1.0)
        self.play(Indicate(circle), run_time=1.0)
        self.wait(0.5)
        self.play(Transform(dot, circle), run_time=1.0)
"""
    report = MotionBudgetMonitor.analyze_code_motion(dense_code)
    assert report.total_duration_sec >= 4.0
    assert report.active_density_ratio >= 0.70
    assert len(report.dead_holds) == 0
    assert report.passed is True


def test_motion_budget_dead_hold_detection():
    stagnant_code = """from manim import *

class StagnantScene(Scene):
    def construct(self):
        dot = Dot()
        self.play(Create(dot), run_time=1.0)
        # Dead hold: 6 seconds of static waiting while narration speaks
        self.wait(6.0)
        self.play(Indicate(dot), run_time=1.0)
"""
    report = MotionBudgetMonitor.analyze_code_motion(stagnant_code)
    assert report.max_dead_hold_sec >= 5.0
    assert len(report.dead_holds) >= 1
    assert report.dead_holds[0].duration_sec >= 5.0
    assert report.passed is False


def test_dynamic_telestration_injection():
    stagnant_code = """from manim import *

class StagnantScene(Scene):
    def construct(self):
        vector_w = Arrow(ORIGIN, UP)
        self.play(Create(vector_w), run_time=1.0)
        self.wait(5.0)
"""
    initial_report = MotionBudgetMonitor.analyze_code_motion(stagnant_code)
    assert len(initial_report.dead_holds) >= 1

    enhanced_code, mods = MotionBudgetMonitor.inject_dynamic_telestration(
        stagnant_code, initial_report.dead_holds
    )
    assert len(mods) >= 1
    assert "Indicate" in enhanced_code

    # Re-analyzing enhanced code should reduce or eliminate long dead holds
    enhanced_report = MotionBudgetMonitor.analyze_code_motion(enhanced_code)
    assert enhanced_report.active_density_ratio > initial_report.active_density_ratio


def test_channel_scoring_with_grounding_and_motion():
    # Scenario 1: Ungrounded talking head (low grounding, static canvas)
    bad_res = MultimodalChannelScorer.score_from_grounding_and_motion(
        topic="Uninformative Video",
        grounding_ratio=0.25,
        motion_density=0.30
    )
    assert bad_res.visual_uplift <= 0.0
    assert bad_res.verdict == "visual_redundant"

    # Scenario 2: Grounded and dynamically telestrated video (Mayer's Dual Coding)
    good_res = MultimodalChannelScorer.score_from_grounding_and_motion(
        topic="Calculus with Active Telestration",
        grounding_ratio=0.88,
        motion_density=0.84
    )
    assert good_res.visual_uplift >= 20.0
    assert good_res.verdict == "strong_multimodal"
    assert good_res.s_multimodal > good_res.s_voice_only
