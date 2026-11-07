"""
Unit and integration tests for Code2Video (arXiv:2510.01174).
"""

import pytest
import os
from code2video.planner import Code2VideoPlanner
from code2video.coder import Code2VideoCoder
from code2video.critic import Code2VideoCritic
from code2video.mmmc import MMMCBenchmark
from code2video.pipeline import Code2VideoPipeline
from code2video.evaluator import Code2VideoEvaluator


def test_mmmc_benchmark_loading():
    bench = MMMCBenchmark()
    assert len(bench.units) >= 6
    assert "Calculus" in bench.CATEGORIES
    assert "Neural Networks" in bench.CATEGORIES

    ml_topics = bench.get_topics_by_category("Machine Learning")
    assert len(ml_topics) >= 1
    assert any("Support Vector" in t.topic for t in ml_topics)


def test_code2video_planner():
    planner = Code2VideoPlanner()
    outline = planner.generate_outline("Support Vector Machine", audience="undergraduate", duration=3.0)
    assert len(outline.sections) >= 2

    storyboard = planner.generate_storyboards(outline)
    assert len(storyboard.sections) == len(outline.sections)

    assets = planner.identify_visual_assets(storyboard)
    assert isinstance(assets, list)


def test_code2video_coder_and_scope_refine():
    planner = Code2VideoPlanner()
    outline = planner.generate_outline("Support Vector Machine")
    storyboard = planner.generate_storyboards(outline)

    coder = Code2VideoCoder()
    sec = storyboard.sections[0]
    code = coder.synthesize_section_code(sec)
    assert "class " in code
    assert "TeachingScene" in code

    repaired, is_exec, tokens, attempts = coder.scope_refine(code, sec, output_dir="demo_outputs/test_coder")
    assert is_exec


def test_code2video_critic():
    critic = Code2VideoCritic()
    code_with_collision = """
self.place_at_grid(cat_icon, 'B2')
self.place_at_grid(formula_label, 'B2')
"""
    from adapt_manim.core.types import StoryboardSection
    sec = StoryboardSection(
        id="section_1",
        title="Test",
        lecture_lines=["Test statement"],
        animations=["Test animation"]
    )
    refined_code, has_mods, imps = critic.analyze_layout_and_refine(code_with_collision, sec)
    assert has_mods
    assert len(imps) > 0
    # Confirms one of them moved to a vacant anchor (e.g. A2, B1, C2)
    assert "'A2'" in refined_code or "'B1'" in refined_code or "'C2'" in refined_code


def test_code2video_end_to_end_pipeline():
    pipeline = Code2VideoPipeline(output_dir="demo_outputs/test_pipeline")
    res = pipeline.run("Support Vector Machine", render=False)

    assert res["topic"] == "Support Vector Machine"
    assert os.path.exists(res["script_path"])
    assert res["aesthetics"]["overall_aes"] > 70.0
    assert res["teach_quiz"]["es_gain"] > 50.0
