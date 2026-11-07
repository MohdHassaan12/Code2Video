"""
Tests for Advanced Code2Video Functionality, MMMC Full Corpus,
LaTeX Table Generation, and Scientific Visualization.
"""

import os
import pytest
from code2video.mmmc import MMMCBenchmark, MMMCTopicUnit
from scripts.generate_paper_tables import (
    generate_table1_latex,
    generate_table2_latex,
    generate_table3_latex,
    generate_table7_latex
)
from scripts.generate_paper_plots import (
    plot_pareto_frontier,
    plot_aes_radar,
    plot_grid_heatmap,
    plot_repair_efficiency
)


def test_mmmc_full_corpus_13_categories():
    benchmark = MMMCBenchmark("benchmarks/mmmc_topics_full.json")
    assert len(benchmark.CATEGORIES) == 13
    assert len(benchmark.units) >= 13

    # Check representative categories
    calc_units = benchmark.get_topics_by_category("Calculus")
    assert len(calc_units) >= 1
    assert any("Derivative" in u.topic for u in calc_units)

    nn_units = benchmark.get_topics_by_category("Neural Networks")
    assert len(nn_units) >= 1
    assert any("Support Vector Machine" in u.topic for u in nn_units)

    geom_units = benchmark.get_topics_by_category("Geometry")
    assert len(geom_units) >= 1
    assert any("Pythagorean" in u.topic for u in geom_units)

    comp_units = benchmark.get_topics_by_category("Complex Analysis & Fractals")
    assert len(comp_units) >= 1
    assert any("Euler's Formula" in u.topic for u in comp_units)


def test_mmmc_topic_lookup_and_quiz():
    benchmark = MMMCBenchmark("benchmarks/mmmc_topics_full.json")
    svm_unit = benchmark.get_topic_by_name("Support Vector Machine")
    assert svm_unit is not None
    assert svm_unit.category == "Neural Networks"
    assert svm_unit.key_formula is not None
    assert len(svm_unit.learning_quiz) >= 1

    quiz = benchmark.get_teach_quiz("Support Vector Machine")
    assert len(quiz) >= 1
    assert "question" in quiz[0]
    assert "options" in quiz[0]
    assert "answer_index" in quiz[0]


def test_latex_table_generation(tmp_path):
    out_dir = str(tmp_path / "tables")
    t1 = generate_table1_latex(out_dir)
    t2 = generate_table2_latex(out_dir)
    t3 = generate_table3_latex(out_dir)
    t7 = generate_table7_latex(out_dir)

    assert os.path.exists(t1)
    assert os.path.exists(t2)
    assert os.path.exists(t3)
    assert os.path.exists(t7)

    with open(t1, "r") as f:
        content = f.read()
        assert "Code2Video" in content
        assert "AdaptManim" in content
        assert "3Blue1Brown" in content


def test_scientific_plot_generation():
    p1 = plot_pareto_frontier()
    p2 = plot_aes_radar()
    p3 = plot_grid_heatmap()
    p4 = plot_repair_efficiency()

    assert os.path.exists(p1)
    assert os.path.exists(p2)
    assert os.path.exists(p3)
    assert os.path.exists(p4)
    assert os.path.getsize(p1) > 10000
    assert os.path.getsize(p2) > 10000
    assert os.path.getsize(p3) > 10000
    assert os.path.getsize(p4) > 10000
