"""
Tests for TheoremExplainBench, MultimodalCritic, and Visual Asset Database D_asset.
"""

import os
import pytest
from code2video.theorem_bench import TheoremExplainBench, TheoremUnit
from code2video.multimodal_critic import MultimodalCritic
from scripts.generate_visual_assets import generate_assets
from scripts.generate_paper_tables import generate_table8_latex


def test_theorem_bench_loading():
    tb = TheoremExplainBench()
    assert len(tb.theorems) >= 5
    thm_names = [t.theorem_name for t in tb.theorems]
    assert "Central Limit Theorem" in thm_names
    assert "Fundamental Theorem of Calculus" in thm_names
    assert "Pythagorean Theorem" in thm_names
    assert "Spectral Theorem for Symmetric Matrices" in thm_names


def test_theorem_bench_evaluation():
    tb = TheoremExplainBench()
    sample_code = """
class CentralLimitTheoremScene(TeachingScene):
    def construct(self):
        self.setup_layout("Central Limit Theorem", ["Sum of independent variables converges to Gaussian"])
        self.highlight_lecture(0)
        curve = SafeMathTex(r"\\lim_{n \\to \\infty} P(...)")
        self.place_at_grid(curve, "B2")
        self.play(Create(curve))
    """
    scores = tb.evaluate_code(sample_code, "thm_01")
    assert scores["overall"] >= 0.80
    assert scores["element_layout"] >= 0.85
    assert scores["logical_flow"] >= 0.85


def test_table8_latex_generation(tmp_path):
    out_dir = str(tmp_path / "tables")
    t8 = generate_table8_latex(out_dir)
    assert os.path.exists(t8)
    with open(t8, "r") as f:
        content = f.read()
        assert "TheoremExplainBench" in content
        assert "Code2Video" in content
        assert "AdaptManim" in content


def test_visual_assets_generation(tmp_path):
    out_dir = str(tmp_path / "assets")
    generate_assets(out_dir)
    expected_files = [
        "coordinate_axes.png",
        "unit_circle.png",
        "neural_node.png",
        "vector_arrow.png",
        "bell_curve.png",
        "right_triangle.png"
    ]
    for ef in expected_files:
        p = os.path.join(out_dir, ef)
        assert os.path.exists(p)
        assert os.path.getsize(p) > 500


def test_multimodal_critic_occlusion_detection(tmp_path):
    critic = MultimodalCritic()
    # Test on existing rendered video
    v_path = "demo_outputs/code2video_svm/complete_lecture.mp4"
    if os.path.exists(v_path):
        frames = critic.extract_keyframes(v_path, str(tmp_path), num_frames=2)
        assert len(frames) >= 1
        for fr in frames:
            assert os.path.exists(fr)
            occ = critic.inspect_visual_occlusion(fr)
            assert "has_occlusion" in occ
            assert "lecture_zone_density" in occ

