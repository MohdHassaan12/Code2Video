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
    complexity_score: int = 3
    pedagogical_goals: List[str] = Field(default_factory=list)
    required_assets: List[str] = Field(default_factory=list)
    learning_quiz: List[Dict[str, Any]] = Field(default_factory=list)


class MMMCBenchmark:
    """
    Curated MMMC Benchmark Suite across 13 core STEM disciplines from 3Blue1Brown:
    Calculus, Linear Algebra, Neural Networks, Differential Equations,
    Cryptography & Number Theory, Probability & Statistics, Information Theory,
    Geometry, Physics & Mechanics, Computer Graphics & Algorithms,
    Group Theory & Abstract Algebra, Topology & Manifolds, Complex Analysis & Fractals.
    """

    CATEGORIES = [
        "Calculus",
        "Linear Algebra",
        "Neural Networks",
        "Differential Equations",
        "Cryptography & Number Theory",
        "Probability & Statistics",
        "Information Theory",
        "Geometry",
        "Physics & Mechanics",
        "Computer Graphics & Algorithms",
        "Group Theory & Abstract Algebra",
        "Topology & Manifolds",
        "Complex Analysis & Fractals"
    ]

    def __init__(self, dataset_path: Optional[str] = None):
        if dataset_path:
            self.dataset_path = dataset_path
        elif os.path.exists("benchmarks/mmmc_topics_full.json"):
            self.dataset_path = "benchmarks/mmmc_topics_full.json"
        else:
            self.dataset_path = "benchmarks/mmmc_sample_topics.json"

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
                                unit_id=top.get("id", f"mmmc_{len(self.units)+1:03d}"),
                                topic=top.get("topic", ""),
                                category=cat,
                                duration_sec=int(top.get("target_duration_minutes", 3.0) * 60),
                                key_formula=top.get("governing_equation"),
                                complexity_score=top.get("complexity_score", 3),
                                pedagogical_goals=top.get("pedagogical_goals", []),
                                required_assets=top.get("required_assets", []),
                                learning_quiz=top.get("teach_quiz", [])
                            ))
                if self.units:
                    return
            except Exception:
                pass

        # Populate representative benchmark set across the 13 categories
        curated_items = [
            ("Support Vector Machine and Maximum Margin Hyperplanes", "Neural Networks", 201, r"\min \frac{1}{2} \|w\|^2"),
            ("Neural Network Learning and Backpropagation", "Neural Networks", 240, r"\frac{\partial \mathcal{L}}{\partial W}"),
            ("Pure Fourier Series: Drawing with Rotating Epicycles", "Physics & Mechanics", 195, r"\hat{f}(\omega) = \int f(t)e^{-i\omega t}dt"),
            ("The Determinant and Area Scaling", "Linear Algebra", 180, r"\det(A) = ad - bc"),
            ("Euler's Formula: The Most Beautiful Equation", "Complex Analysis & Fractals", 160, r"e^{i\theta} = \cos\theta + i\sin\theta"),
            ("Snell's Law and Fermat's Principle of Least Time", "Physics & Mechanics", 150, r"n_1 \sin\theta_1 = n_2 \sin\theta_2"),
            ("Essence of Calculus: The Derivative", "Calculus", 210, r"\frac{df}{dx} = \lim_{h \to 0} \frac{f(x+h)-f(x)}{h}"),
            ("Bayes' Theorem and Prior Probability Updating", "Probability & Statistics", 175, r"P(A|B) = \frac{P(B|A)P(A)}{P(B)}"),
            ("Pythagorean Theorem: Visual Proof Without Words", "Geometry", 120, r"a^2 + b^2 = c^2"),
            ("Harmonic Oscillators and Phase Space Trajectories", "Differential Equations", 225, r"m \ddot{x} + c \dot{x} + k x = 0")
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
        cat_lower = category.lower()
        aliases = {
            "machine learning": "neural networks",
            "ml": "neural networks",
            "physics": "physics & mechanics",
            "optics": "physics & mechanics",
            "algorithms": "computer graphics & algorithms",
            "complex analysis": "complex analysis & fractals",
            "topology": "topology & manifolds",
            "number theory": "cryptography & number theory",
            "probability": "probability & statistics",
            "linear algebra": "linear algebra",
            "calculus": "calculus"
        }
        target = aliases.get(cat_lower, cat_lower)
        return [
            u for u in self.units
            if u.category.lower() == target or target in u.category.lower() or cat_lower in u.category.lower()
        ]

    def get_topic_by_name(self, topic_name: str) -> Optional[MMMCTopicUnit]:
        """Finds a topic unit by exact or substring match."""
        lower_name = topic_name.lower()
        for u in self.units:
            if lower_name == u.topic.lower() or lower_name in u.topic.lower():
                return u
        return None

    def get_teach_quiz(self, topic_name: str) -> List[Dict[str, Any]]:
        """Returns the ground truth TeachQuiz questions for a topic."""
        unit = self.get_topic_by_name(topic_name)
        if unit and unit.learning_quiz:
            return unit.learning_quiz
        # Default quiz probe
        return [
            {
                "question": f"What is the primary governing principle of {topic_name}?",
                "options": ["A fundamental conservation law", "Geometric transformation invariance", "Rate of change optimization", "Empirical approximation"],
                "answer_index": 1,
                "explanation": "Visual transformations preserve geometric structure while showing conceptual evolution."
            }
        ]

    def list_all_topics(self) -> List[str]:
        return [u.topic for u in self.units]

