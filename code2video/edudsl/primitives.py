"""
EduDSL: Declarative Pedagogical Primitives for STEM Educational Video Synthesis.
Direction D10: Formalizes 5 core subject kits into typed declarative schemas:
1. Calculus & Analysis: Formula derivations, differential secant-to-tangent limits, Riemann sums.
2. Linear Algebra & Geometry: 2D matrix basis transformations, coordinate grid warps, determinant areas.
3. Physics & Mechanics: Newton's 3rd law action-reaction force pairs, kinematic trajectories.
4. Machine Learning & Optimization: Maximum-margin hyperplane classifiers, support vectors, loss contours.
5. Complex Analysis & Signal Processing: Complex Euler phasor rotation, real/imaginary projections.

Replaces error-prone raw code generation with guaranteed-compiling, constraint-solved visual primitives.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union


class SubjectKitDomain(str, Enum):
    CALCULUS = "calculus"
    LINEAR_ALGEBRA = "linear_algebra"
    PHYSICS = "physics"
    MACHINE_LEARNING = "machine_learning"
    COMPLEX_ANALYSIS = "complex_analysis"


@dataclass
class EduComponent:
    """Base abstract component in the EduDSL declarative hierarchy."""
    component_id: str
    domain: SubjectKitDomain
    anchor_area: Tuple[str, str] = ("A1", "F6")  # Default to full 6x6 visual canvas
    primary_color: str = "#58C4DD"
    secondary_color: str = "#FFFF00"
    title: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "component_id": self.component_id,
            "domain": self.domain.value,
            "anchor_area": self.anchor_area,
            "primary_color": self.primary_color,
            "secondary_color": self.secondary_color,
            "title": self.title,
        }


# =====================================================================
# Kit 1: Calculus & Analysis Kit
# =====================================================================

@dataclass
class DerivationStep:
    equation_latex: str
    explanation: str
    highlight_terms: List[str] = field(default_factory=list)
    pause_sec: float = 1.0


@dataclass
class CalculusDerivation(EduComponent):
    """
    Formal calculus derivation primitive.
    Renders stepwise mathematical derivations with synchronized term highlights
    and differential triangle visualizations (dx, df).
    """
    domain: SubjectKitDomain = SubjectKitDomain.CALCULUS
    steps: List[DerivationStep] = field(default_factory=list)
    show_differential_triangle: bool = True
    x_range: Tuple[float, float, float] = (0.0, 5.0, 1.0)
    function_lambda_str: str = "0.5 * x**2"
    limit_point_x: float = 2.0
    initial_h: float = 1.5

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d.update({
            "steps": [s.__dict__ for s in self.steps],
            "show_differential_triangle": self.show_differential_triangle,
            "x_range": self.x_range,
            "function_lambda_str": self.function_lambda_str,
            "limit_point_x": self.limit_point_x,
            "initial_h": self.initial_h,
        })
        return d


# =====================================================================
# Kit 2: Linear Algebra & Geometry Kit
# =====================================================================

@dataclass
class LinearAlgebraTransform(EduComponent):
    """
    2D Linear transformation and basis mapping primitive.
    Animates basis vectors i_hat, j_hat, grid warping, and the transformed determinant area.
    """
    domain: SubjectKitDomain = SubjectKitDomain.LINEAR_ALGEBRA
    matrix_entries: Tuple[Tuple[float, float], Tuple[float, float]] = ((2.0, 1.0), (0.5, 1.5))
    show_grid_warp: bool = True
    show_basis_vectors: bool = True
    show_determinant_area: bool = True
    vector_labels: Tuple[str, str] = (r"\hat{i}", r"\hat{j}")

    @property
    def determinant(self) -> float:
        ((a, b), (c, d)) = self.matrix_entries
        return (a * d) - (b * c)

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d.update({
            "matrix_entries": self.matrix_entries,
            "determinant": round(self.determinant, 3),
            "show_grid_warp": self.show_grid_warp,
            "show_basis_vectors": self.show_basis_vectors,
            "show_determinant_area": self.show_determinant_area,
            "vector_labels": self.vector_labels,
        })
        return d


# =====================================================================
# Kit 3: Physics & Mechanics Kit
# =====================================================================

@dataclass
class PhysicsKinematics(EduComponent):
    """
    Kinematic motion and Newton's Third Law force pair primitive.
    Renders action-reaction force vectors on two distinct physical bodies,
    eradicating the common misconception that equal-opposite forces cancel out.
    """
    domain: SubjectKitDomain = SubjectKitDomain.PHYSICS
    body_a_name: str = "Body A (Block)"
    body_b_name: str = "Body B (Surface)"
    force_magnitude: float = 15.0
    action_label: str = r"\vec{F}_{A \to B}"
    reaction_label: str = r"\vec{F}_{B \to A}"
    show_distinct_bodies: bool = True
    show_contact_normal: bool = True

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d.update({
            "body_a_name": self.body_a_name,
            "body_b_name": self.body_b_name,
            "force_magnitude": self.force_magnitude,
            "action_label": self.action_label,
            "reaction_label": self.reaction_label,
            "show_distinct_bodies": self.show_distinct_bodies,
            "show_contact_normal": self.show_contact_normal,
        })
        return d


# =====================================================================
# Kit 4: Machine Learning & Optimization Kit
# =====================================================================

@dataclass
class MachineLearningClassifier(EduComponent):
    """
    Support Vector Machine maximum-margin hyperplane classifier primitive.
    Renders 2D linearly separable clusters, the separating boundary w^T x + b = 0,
    the margin boundaries, and calls out support vectors.
    """
    domain: SubjectKitDomain = SubjectKitDomain.MACHINE_LEARNING
    weight_vector: Tuple[float, float] = (1.2, 0.8)
    bias: float = -0.3
    margin_width: float = 1.4
    num_positive_samples: int = 6
    num_negative_samples: int = 6
    show_margin_boundaries: bool = True
    show_support_vectors: bool = True

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d.update({
            "weight_vector": self.weight_vector,
            "bias": self.bias,
            "margin_width": self.margin_width,
            "num_positive_samples": self.num_positive_samples,
            "num_negative_samples": self.num_negative_samples,
            "show_margin_boundaries": self.show_margin_boundaries,
            "show_support_vectors": self.show_support_vectors,
        })
        return d


# =====================================================================
# Kit 5: Complex Analysis & Phasor Kit
# =====================================================================

@dataclass
class ComplexPhasor(EduComponent):
    """
    Euler complex phasor rotation primitive: e^(i theta) = cos(theta) + i sin(theta).
    Renders complex unit circle, rotating phasor vector, and orthogonal real/imaginary projections.
    """
    domain: SubjectKitDomain = SubjectKitDomain.COMPLEX_ANALYSIS
    target_angle_rad: float = 3.141592653589793  # pi
    rotation_duration_sec: float = 3.0
    show_unit_circle: bool = True
    show_real_projection: bool = True
    show_imag_projection: bool = True
    show_euler_identity_label: bool = True

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d.update({
            "target_angle_rad": round(self.target_angle_rad, 4),
            "rotation_duration_sec": self.rotation_duration_sec,
            "show_unit_circle": self.show_unit_circle,
            "show_real_projection": self.show_real_projection,
            "show_imag_projection": self.show_imag_projection,
            "show_euler_identity_label": self.show_euler_identity_label,
        })
        return d


# =====================================================================
# Master EduScene Specification
# =====================================================================

@dataclass
class EduSceneSpec:
    """
    Master declarative specification for an educational video scene.
    Compiled deterministically into certified, zero-collision Manim Python code.
    """
    scene_id: str
    topic: str
    section_title: str
    lecture_lines: List[str]
    components: List[EduComponent]
    target_duration_sec: float = 30.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "scene_id": self.scene_id,
            "topic": self.topic,
            "section_title": self.section_title,
            "lecture_lines": self.lecture_lines,
            "target_duration_sec": self.target_duration_sec,
            "components": [c.to_dict() for c in self.components],
        }
