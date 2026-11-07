"""
Compute Tracker & Pareto Frontier Module.
Tracks token consumption, execution wall-clock time, repair passes,
and models Quality-Compute trade-offs across educational video synthesis pipelines.
"""

from typing import Dict, List, Any
from adapt_manim.core.types import ComputeMetrics, QualityMetrics


class ComputeTracker:
    """Tracks resource consumption and computes Pareto frontier trade-offs."""

    COST_PER_MILLION_PROMPT_USD = 1.25
    COST_PER_MILLION_COMPLETION_USD = 5.00

    def __init__(self):
        self.metrics = ComputeMetrics()

    def record_planning(self, tokens: int):
        self.metrics.planning_tokens += tokens
        self.metrics.total_tokens += tokens

    def record_coding(self, tokens: int):
        self.metrics.coding_tokens += tokens
        self.metrics.total_tokens += tokens

    def record_verification(self, tokens: int):
        self.metrics.verification_tokens += tokens
        self.metrics.total_tokens += tokens

    def record_repair(self, tokens: int):
        self.metrics.repair_tokens += tokens
        self.metrics.total_tokens += tokens
        self.metrics.repair_iterations += 1

    def finalize(self, wall_clock_sec: float, pass_at_1: bool, pass_at_repair: bool):
        self.metrics.wall_clock_time_sec = round(wall_clock_sec, 2)
        self.metrics.pass_at_1 = pass_at_1
        self.metrics.pass_at_repair = pass_at_repair
        # Estimate USD cost
        est_cost = (
            (self.metrics.total_tokens * 0.75 / 1e6) * self.COST_PER_MILLION_PROMPT_USD +
            (self.metrics.total_tokens * 0.25 / 1e6) * self.COST_PER_MILLION_COMPLETION_USD
        )
        self.metrics.estimated_cost_usd = round(est_cost, 4)

    @staticmethod
    def compute_pareto_tradeoff(quality: QualityMetrics, compute: ComputeMetrics) -> Dict[str, float]:
        """
        Calculates Pareto efficiency metrics:
        Quality-to-Compute Ratio (QCR) = Overall AES / (Token_Cost_K + 1)
        """
        token_k = compute.total_tokens / 1000.0
        time_min = compute.wall_clock_time_sec / 60.0

        # Quality-to-Compute Ratio
        qcr = quality.overall_aes / (token_k + 1.0)

        # TeachQuiz efficiency per token
        quiz_eff = quality.teach_quiz_relative / (token_k + 1.0)

        return {
            "token_k": round(token_k, 2),
            "time_minutes": round(time_min, 2),
            "quality_aes": quality.overall_aes,
            "teach_quiz_relative": quality.teach_quiz_relative,
            "qcr_pareto_score": round(qcr, 3),
            "quiz_efficiency_score": round(quiz_eff, 3)
        }
