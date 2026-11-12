"""
Tests for Spoken-to-Visual Grounding Matrix (Direction D9+).
Verifies:
1. Spoken entity extraction across variables, formulas, concepts, and numbers.
2. Visual entity extraction from Manim Python AST.
3. Grounding matrix computation and Mayer contiguity scoring.
4. Detection of ungrounded spoken terms and orphan visuals.
"""

import pytest
from code2video.grounding_matrix import (
    SpokenEntity, VisualEntity, GroundingMatch, GroundingMatrixReport,
    SpokenVisualGroundingMatrix
)


def test_extract_spoken_entities():
    narration = (
        "We consider the derivative df over dx as limit of h approaches zero. "
        "Here x represents position, theta is the angle, and the constant is 3.14."
    )
    timeline = [
        {"phrase": "We consider the derivative df over dx", "start_sec": 0.0, "duration_sec": 6.0},
        {"phrase": "Here x represents position and theta is angle", "start_sec": 6.0, "duration_sec": 6.0},
    ]

    entities = SpokenVisualGroundingMatrix.extract_spoken_entities(narration, timeline=timeline)
    assert len(entities) > 0

    terms = [e.term.lower() for e in entities]
    assert any("derivative" in t for t in terms)
    assert any("theta" in t for t in terms)
    assert any("df" in t for t in terms)


def test_extract_visual_entities_from_ast():
    sample_code = """from manim import *

class TestScene(Scene):
    def construct(self):
        title = Text("Derivative Intuition").to_edge(UP)
        formula = MathTex(r"\\frac{df}{dx} = \\lim_{h \\to 0} \\frac{f(x+h)-f(x)}{h}")
        dot_p = Dot(ORIGIN, color=YELLOW)
        
        self.play(Write(title), run_time=1.5)
        self.wait(1.0)
        self.play(Create(formula), run_time=2.0)
        self.play(Indicate(dot_p), run_time=1.0)
"""
    visuals = SpokenVisualGroundingMatrix.extract_visual_entities(sample_code)
    assert len(visuals) >= 3

    obj_names = [v.obj_name for v in visuals]
    assert "title" in obj_names
    assert "formula" in obj_names
    assert "dot_p" in obj_names

    actions = [v.action_type for v in visuals]
    assert "Write" in actions
    assert "Create" in actions
    assert "Indicate" in actions


def test_compute_grounding_matrix_well_grounded():
    narration = "The derivative df over dx is evaluated at position dot_p with angle theta."
    code = """from manim import *

class GroundedScene(Scene):
    def construct(self):
        df_dx = MathTex(r"\\frac{df}{dx}")
        dot_p = Dot(color=YELLOW)
        theta_angle = MathTex(r"\\theta")
        
        self.play(Write(df_dx), run_time=1.5)
        self.play(Create(dot_p), run_time=1.0)
        self.play(Write(theta_angle), run_time=1.0)
"""
    timeline = [
        {"phrase": "The derivative df over dx is evaluated", "start_sec": 0.0, "duration_sec": 2.0},
        {"phrase": "at position dot_p with angle theta", "start_sec": 2.0, "duration_sec": 3.0},
    ]

    report = SpokenVisualGroundingMatrix.compute_grounding_matrix(
        topic="Calculus Derivative",
        narration_text=narration,
        code=code,
        timeline=timeline,
        temporal_tolerance_sec=4.0
    )

    assert report.total_spoken_entities > 0
    assert report.grounded_count > 0
    assert report.grounding_ratio >= 0.5
    assert report.mayer_contiguity_score >= 50.0
    assert isinstance(report.to_dict(), dict)


def test_detect_ungrounded_and_orphan():
    narration = "We analyze the secret variable omega and matrix lambda which are never drawn on screen."
    code = """from manim import *

class OrphanScene(Scene):
    def construct(self):
        unspoken_circle = Circle(radius=2.0)
        self.play(Create(unspoken_circle), run_time=1.0)
"""
    report = SpokenVisualGroundingMatrix.compute_grounding_matrix(
        topic="Unspoken Visual Test",
        narration_text=narration,
        code=code,
        temporal_tolerance_sec=2.0
    )

    assert report.ungrounded_count >= 1
    assert any("omega" in u["term"].lower() or "lambda" in u["term"].lower() for u in report.ungrounded_entities)
    assert len(report.orphan_visuals) >= 1
    assert report.orphan_visuals[0]["obj_name"] == "unspoken_circle"
    assert report.passed is False
