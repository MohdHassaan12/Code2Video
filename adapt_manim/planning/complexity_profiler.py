"""
Complexity Profiler module.
Analyzes topic abstractness, mathematical density, and audience level
to dynamically adapt planning, temporal segmentation, and verification compute budgets.
"""

from typing import Dict, Any
from adapt_manim.core.types import AudienceLevel


class TopicComplexityProfile:
    """Contains cognitive and computational profiling parameters for a topic."""

    def __init__(
        self,
        topic: str,
        audience: AudienceLevel,
        difficulty_score: float,  # 0.0 (simple) to 1.0 (highly abstract/complex)
        recommended_scenes: int,
        scene_duration_sec: int,
        search_budget_tier: str,  # "low", "medium", "high"
        requires_symbol_ledger: bool = True
    ):
        self.topic = topic
        self.audience = audience
        self.difficulty_score = difficulty_score
        self.recommended_scenes = recommended_scenes
        self.scene_duration_sec = scene_duration_sec
        self.search_budget_tier = search_budget_tier
        self.requires_symbol_ledger = requires_symbol_ledger


class TopicComplexityProfiler:
    """Profiles educational topics to guide adaptive resource allocation."""

    ABSTRACT_KEYWORDS = [
        "fourier", "topology", "quantum", "backpropagation", "eigen", "tensor",
        "manifold", "differential", "stochastic", "vector space", "group theory"
    ]

    CONCRETE_KEYWORDS = [
        "addition", "gravity", "pythagorean", "projectile", "pendulum",
        "velocity", "triangle", "sorting", "binary search", "circle"
    ]

    @classmethod
    def profile(cls, topic: str, audience: AudienceLevel = AudienceLevel.UNDERGRADUATE) -> TopicComplexityProfile:
        t_lower = topic.lower()

        # Score abstraction based on terminology
        abstract_hits = sum(1 for kw in cls.ABSTRACT_KEYWORDS if kw in t_lower)
        concrete_hits = sum(1 for kw in cls.CONCRETE_KEYWORDS if kw in t_lower)

        base_score = 0.5
        if abstract_hits > 0:
            base_score = min(0.95, 0.5 + 0.15 * abstract_hits)
        elif concrete_hits > 0:
            base_score = max(0.2, 0.5 - 0.15 * concrete_hits)

        # Audience adjustments
        if audience == AudienceLevel.MIDDLE_SCHOOL:
            recommended_scenes = 2 if base_score < 0.6 else 3
            scene_duration = 60  # Shorter attention span
            budget_tier = "medium" if base_score > 0.6 else "low"
        elif audience == AudienceLevel.HIGH_SCHOOL:
            recommended_scenes = 3
            scene_duration = 75
            budget_tier = "medium"
        elif audience == AudienceLevel.UNDERGRADUATE:
            recommended_scenes = 3 if base_score < 0.7 else 4
            scene_duration = 90
            budget_tier = "high" if base_score > 0.65 else "medium"
        else:  # Researcher
            recommended_scenes = 4
            scene_duration = 105
            budget_tier = "high"

        return TopicComplexityProfile(
            topic=topic,
            audience=audience,
            difficulty_score=round(base_score, 2),
            recommended_scenes=recommended_scenes,
            scene_duration_sec=scene_duration,
            search_budget_tier=budget_tier,
            requires_symbol_ledger=True
        )
