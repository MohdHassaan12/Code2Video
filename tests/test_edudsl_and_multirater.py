"""
Tests for EduDSL Subject Kits and Multi-Rater Cross-Validation (Phase 3).
Verifies:
1. Formalization of 5 core EduDSL declarative primitives (Calculus, Linear Algebra, Physics, ML, Complex Analysis).
2. Deterministic compilation of EduDSL to certified, AST-valid Manim Community Python code.
3. Multi-rater cross-validation across Claude 3.5 Sonnet, GPT-4o, and Gemini 2.5 Pro.
4. Krippendorff's alpha and Spearman rho inter-rater reliability calculations.
5. Export of publication LaTeX Table 11.
"""

import ast
from pathlib import Path
import pytest

from code2video.edudsl.primitives import (
    EduSceneSpec, CalculusDerivation, LinearAlgebraTransform,
    PhysicsKinematics, MachineLearningClassifier, ComplexPhasor,
    DerivationStep, SubjectKitDomain
)
from code2video.edudsl.compiler import EduDSLCompiler
from code2video.multi_rater_eval import MultiRaterCrossValidator, MultiRaterCrossValidationSummary


def test_edudsl_compile_calculus_kit():
    calc_comp = CalculusDerivation(
        component_id="calc_test",
        steps=[DerivationStep(r"\frac{df}{dx} = 2x", "Derivative of x^2", ["2x"])],
        limit_point_x=2.0
    )
    spec = EduSceneSpec(
        scene_id="sec_calc",
        topic="Calculus Limits",
        section_title="Calculus Derivative Limit",
        lecture_lines=["Secant approaches tangent.", "The instantaneous limit is 2x."],
        components=[calc_comp]
    )
    code = EduDSLCompiler.compile_scene(spec)
    assert "class CalculusDerivativeLimit(TeachingScene):" in code
    assert "self.setup_layout" in code
    assert "self.place_in_area" in code
    # Must be valid Python syntax
    ast.parse(code)


def test_edudsl_compile_linear_algebra_kit():
    linalg_comp = LinearAlgebraTransform(
        component_id="linalg_test",
        matrix_entries=((2.0, 0.0), (0.0, 3.0))
    )
    assert linalg_comp.determinant == 6.0
    spec = EduSceneSpec(
        scene_id="sec_linalg",
        topic="Linear Algebra",
        section_title="Matrix Basis Transform",
        lecture_lines=["i_hat and j_hat transformation.", "Area scaling factor det(A)."],
        components=[linalg_comp]
    )
    code = EduDSLCompiler.compile_scene(spec)
    assert "NumberPlane" in code
    assert "det_tex" in code
    ast.parse(code)


def test_edudsl_compile_physics_kit():
    phys_comp = PhysicsKinematics(
        component_id="phys_test",
        body_a_name="Block A",
        body_b_name="Table B"
    )
    spec = EduSceneSpec(
        scene_id="sec_phys",
        topic="Physics",
        section_title="Newtons Third Law",
        lecture_lines=["Action and reaction force pairs.", "Act on distinct bodies."],
        components=[phys_comp]
    )
    code = EduDSLCompiler.compile_scene(spec)
    assert "f_action" in code
    assert "f_reaction" in code
    ast.parse(code)


def test_edudsl_compile_machine_learning_kit():
    ml_comp = MachineLearningClassifier(
        component_id="ml_test",
        weight_vector=(1.0, 1.0),
        bias=0.0
    )
    spec = EduSceneSpec(
        scene_id="sec_ml",
        topic="Machine Learning",
        section_title="SVM Hyperplane Margin",
        lecture_lines=["Linearly separable points.", "Maximum margin boundary."],
        components=[ml_comp]
    )
    code = EduDSLCompiler.compile_scene(spec)
    assert "hyperplane" in code
    assert "margin_lbl" in code
    ast.parse(code)


def test_edudsl_compile_complex_phasor_kit():
    phasor_comp = ComplexPhasor(
        component_id="phasor_test",
        target_angle_rad=3.14159
    )
    spec = EduSceneSpec(
        scene_id="sec_phasor",
        topic="Complex Analysis",
        section_title="Euler Phasor",
        lecture_lines=["Rotation on unit circle.", "e^(i pi) + 1 = 0."],
        components=[phasor_comp]
    )
    code = EduDSLCompiler.compile_scene(spec)
    assert "ComplexPlane" in code
    assert "Rotate(phasor" in code
    ast.parse(code)


def test_multi_rater_krippendorff_and_spearman():
    # Exact concordance gives alpha = 1.0
    perfect_matrix = [[80.0, 80.0, 80.0], [90.0, 90.0, 90.0]]
    alpha_perf = MultiRaterCrossValidator.compute_krippendorff_alpha(perfect_matrix)
    assert alpha_perf == 1.0

    # Perfect monotonic ranking gives rho = 1.0
    list_a = [10.0, 20.0, 30.0, 40.0]
    list_b = [15.0, 25.0, 35.0, 45.0]
    rho = MultiRaterCrossValidator.compute_spearman_rho(list_a, list_b)
    assert rho == 1.0


def test_multi_rater_cross_validation_run(tmp_path):
    summary = MultiRaterCrossValidator.run_benchmark_cross_validation()
    assert summary.total_topics >= 12
    assert "Claude_3.5_Sonnet" in summary.models_evaluated
    assert "GPT_4o" in summary.models_evaluated
    assert "Gemini_2.5_Pro" in summary.models_evaluated
    assert -1.0 <= summary.krippendorff_alpha_aes <= 1.0
    assert summary.position_swap_consistency >= 90.0

    # Test export
    out_tex = str(tmp_path / "test_table11.tex")
    res_path = MultiRaterCrossValidator.export_latex_table(summary, output_path=out_tex)
    assert Path(res_path).exists()
    assert "Claude 3.5" in Path(res_path).read_text()
