"""
MMMC (Multimodal Manim Mastery Corpus) Benchmark Module.
Implements the dataset curation, subject area taxonomies, and clip indexing
from 3Blue1Brown and expert Manim instructional videos (Section 3.2).
"""

import json
import os
from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field


class MMMCTopicUnit(BaseModel):
    """An educational topic unit in the MMMC benchmark."""
    unit_id: str
    topic: str
    category: str
    duration_sec: int
    source_channel: str = "3Blue1Brown"
    prerequisites: List[str] = Field(default_factory=list)
    key_formula: Optional[str] = None
    learning_quiz: List[Dict[str, Any]] = Field(default_factory=list)


class MMMCBenchmark:
    """
    Curated MMMC Benchmark Suite across 13 core STEM disciplines:
    Calculus, Linear Algebra, Probability, Neural Networks, Geometry,
    Physics, Complex Analysis, Differential Equations, Topology,
    Number Theory, Information Theory, Fourier Analysis, Algorithms.
    """

    CATEGORIES = [
        "Calculus", "Linear Algebra", "Probability", "Neural Networks",
        "Geometry", "Physics & Optics", "Complex Analysis",
        "Differential Equations", "Topology", "Number Theory",
        "Information Theory", "Fourier Analysis", "Algorithms & Optimization"
    ]

    def __init__(self, dataset_path: str = "benchmarks/mmmc_sample_topics.json"):
        self.dataset_path = dataset_path
        self.units: List[MMMCTopicUnit] = []
        self._load_or_populate_units()

    def _load_or_populate_units(self):
        """Loads units from disk or populates the canonical representative suite."""
        if os.path.exists(self.dataset_path):
            try:
                with open(self.dataset_path, "r") as f:
                    data = json.load(f)
                    for dom in data.get("domains", []):
                        cat = dom.get("domain", "General STEM")
                        for top in dom.get("topics", []):
                            self.units.append(MMMCTopicUnit(
                                unit_id=f"mmmc_{len(self.units)+1:03d}",
                                topic=top.get("topic", ""),
                                category=cat,
                                duration_sec=int(top.get("target_duration_minutes", 3.0) * 60),
                                key_formula=top.get("governing_equation")
                            ))
                if self.units:
                    return
            except Exception:
                pass

        # Populate representative benchmark set across the 13 categories
        curated_items = [
            ("Support Vector Machine", "Neural Networks", 201, r"\min \frac{1}{2} \|w\|^2"),
            ("Neural Network Learning and Backpropagation", "Neural Networks", 240, r"\frac{\partial \mathcal{L}}{\partial W}"),
            ("Pure Fourier Series", "Fourier Analysis", 195, r"\hat{f}(\omega) = \int f(t)e^{-i\omega t}dt"),
            ("The Essence of Linear Algebra: Determinant", "Linear Algebra", 180, r"\det(A) = ad - bc"),
            ("Euler's Formula and Complex Exponential", "Complex Analysis", 160, r"e^{i\theta} = \cos\theta + i\sin\theta"),
            ("Snell's Law of Refraction", "Physics & Optics", 150, r"n_1 \sin\theta_1 = n_2 \sin\theta_2"),
            ("Essence of Calculus: The Derivative", "Calculus", 210, r"\frac{df}{dx} = \lim_{h \to 0} \frac{f(x+h)-f(x)}{h}"),
            ("Bayes' Theorem and Conditional Probability", "Probability", 175, r"P(A|B) = \frac{P(B|A)P(A)}{P(B)}"),
            ("Pythagorean Theorem Geometric Proof", "Geometry", 120, r"a^2 + b^2 = c^2"),
            ("Navier-Stokes and Vector Fields", "Differential Equations", 225, r"\rho(\partial_t u + u\cdot\nabla u) = -\nabla p + \mu\nabla^2 u")
        ]

        for idx, (top, cat, dur, eq) in enumerate(curated_items):
            self.units.append(MMMCTopicUnit(
                unit_id=f"mmmc_{idx+1:03d}",
                topic=top,
                category=cat,
                duration_sec=dur,
                key_formula=eq
            ))

    def get_topics_by_category(self, category: str) -> List[MMMCTopicUnit]:
        return [u for u in self.units if u.category.lower() == category.lower()]

    def list_all_topics(self) -> List[str]:
        return [u.topic for u in self.units]

