"""
Cognitive Metrics Module.
Evaluates instructional multimedia design adherence to Mayer's Cognitive Theory
of Multimedia Learning (Segmentation, Signaling, Temporal Contiguity, Dual Coding)
as formalized in LLM2Manim (Sections I and II).
"""

from typing import Dict, Any
from adapt_manim.core.types import Storyboard, StoryboardSection


class CognitiveMetricsEvaluator:
    """Measures pedagogical cognitive load and multimedia learning compliance."""

    @classmethod
    def evaluate(cls, code: str, storyboard: Storyboard) -> Dict[str, Any]:
        results = {}

        # 1. Signaling Score: percentage of lecture lines with synchronized highlighting
        signaling_calls = code.count("highlight_lecture")
        total_lecture_lines = sum(len(s.lecture_lines) for s in storyboard.sections)
        signaling_pct = (signaling_calls / max(1, total_lecture_lines)) * 100.0
        results["signaling_compliance_pct"] = round(min(100.0, signaling_pct), 1)

        # 2. Segmentation Score: 60-120 seconds target per scene
        durations = [len(s.lecture_lines) * 20 for s in storyboard.sections]  # approx 20s per bullet
        valid_segments = sum(1 for d in durations if 50 <= d <= 130)
        segmentation_score = (valid_segments / max(1, len(durations))) * 100.0
        results["segmentation_score"] = round(segmentation_score, 1)

        # 3. Temporal Contiguity Score: presence of wait pauses after each animation step
        wait_calls = code.count("self.wait(")
        contiguity_score = min(100.0, (wait_calls / max(1, total_lecture_lines)) * 100.0)
        results["temporal_contiguity_score"] = round(contiguity_score, 1)

        # 4. Dual Coding Compliance: presence of graphical constructs alongside text
        has_visuals = any(kw in code for kw in ["Dot(", "Line(", "Circle(", "Square(", "Arrow(", "Axes(", "MathTex("])
        results["dual_coding_present"] = has_visuals

        # Aggregate Cognitive Learning Index (CLI) (0-100)
        cli = (results["signaling_compliance_pct"] * 0.35 +
               results["segmentation_score"] * 0.30 +
               results["temporal_contiguity_score"] * 0.35)
        results["cognitive_learning_index"] = round(cli, 1)

        return results

