"""
Code2Video Evaluator Module.
Implements the 3-pronged evaluation: Aesthetics (P_aesth), Knowledge Transfer (TeachQuiz),
and Efficiency (Time and Token Consumption) based on Section 3.3.
"""

from typing import Dict, List, Any, Optional
from code2video.prompts import PROMPT_AESTHETICS, PROMPT_UNLEARN, PROMPT_LEARN
from adapt_manim.evaluation.aesthetic_judge import AestheticJudge
from adapt_manim.evaluation.teach_quiz import TeachQuizEvaluator


class Code2VideoEvaluator:
    """
    Official Evaluator of Code2Video:
    - VLM-as-a-Judge Aesthetic Score (EL, AT, LF, VC, AD, Overall)
    - TeachQuiz relative knowledge transfer: eS(V) = S(V) - S(V|unlearn)
    - Code efficiency (Tokens and Generation Time)
    """

    def __init__(self, llm_client: Optional[Any] = None):
        self.llm_client = llm_client

    def evaluate_aesthetics(self, code: str, topic: str) -> Dict[str, Any]:
        """Evaluates video code across EL, AT, LF, VC, AD (100-point scale)."""
        qm = AestheticJudge.evaluate(code, topic)
        return {
            "element_layout": qm.element_layout,
            "attractiveness": qm.attractiveness,
            "logic_flow": qm.logic_flow,
            "visual_consistency": qm.visual_consistency,
            "accuracy_depth": qm.accuracy_depth,
            "overall_aes": qm.overall_aes,
            "verdict": qm.verdict
        }

    def evaluate_teach_quiz(self, topic: str, video_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Calculates relative knowledge transfer:
        eS(V) = S(V) - S(V|unlearn)
        """
        return TeachQuizEvaluator.evaluate_relative_gain(topic, is_video_grounded=True)

