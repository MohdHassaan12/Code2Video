"""
EduDSL: Declarative Pedagogical Animation Language.
Direction D10: Formalizes 5 core subject kits into typed declarative schemas
and compiles deterministically into certified Manim Community Python code.
"""

from code2video.edudsl.primitives import (
    SubjectKitDomain, EduComponent, EduSceneSpec, DerivationStep,
    CalculusDerivation, LinearAlgebraTransform, PhysicsKinematics,
    MachineLearningClassifier, ComplexPhasor
)
from code2video.edudsl.compiler import EduDSLCompiler

__all__ = [
    "SubjectKitDomain",
    "EduComponent",
    "EduSceneSpec",
    "DerivationStep",
    "CalculusDerivation",
    "LinearAlgebraTransform",
    "PhysicsKinematics",
    "MachineLearningClassifier",
    "ComplexPhasor",
    "EduDSLCompiler",
]
