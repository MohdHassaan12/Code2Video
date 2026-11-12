"""
Unit tests for Direction D12: Public Benchmark Runner (MMMC & VibeVideoBench).
Verifies comparative evaluations across Direct CodeLLM, Code2Video, Lessonforge,
and Learner-in-the-Loop Hybrid, ensuring correct aggregation and CSV exports across
both MMMC and VibeVideoBench educational tasks.
"""

import csv
from pathlib import Path
from code2video.public_benchmark import PublicBenchmarkRunner, BenchmarkTopicResult


def test_evaluate_topic_all_paradigms():
    runner = PublicBenchmarkRunner()
    results = runner.evaluate_topic_all_paradigms("Snell's Law and Optical Refraction", "Physics & Optics")

    assert len(results) == 4
    paradigms = [r.paradigm for r in results]
    assert "Direct_CodeLLM" in paradigms
    assert "Code2Video" in paradigms
    assert "Lessonforge" in paradigms
    assert "Learner_in_the_Loop_Hybrid" in paradigms

    hybrid = next(r for r in results if r.paradigm == "Learner_in_the_Loop_Hybrid")
    direct = next(r for r in results if r.paradigm == "Direct_CodeLLM")
    c2v = next(r for r in results if r.paradigm == "Code2Video")

    # Hybrid should have higher TeachQuiz gain than baseline
    assert hybrid.teach_quiz_es > direct.teach_quiz_es
    # Hybrid should have higher Pareto QCR efficiency than monolithic Code2Video
    assert hybrid.qcr_score > c2v.qcr_score
    # Hybrid should have lower AV sync drift than Direct CodeLLM
    assert hybrid.av_sync_drift_sec < direct.av_sync_drift_sec


def test_benchmark_suite_aggregation_and_csv(tmp_path):
    runner = PublicBenchmarkRunner()
    results = runner.run_suite(max_topics=2)
    assert len(results) == 8  # 2 topics * 4 paradigms

    summary = runner.aggregate_by_paradigm(results)
    assert len(summary) == 4
    assert summary["Learner_in_the_Loop_Hybrid"]["num_topics"] == 2
    assert summary["Learner_in_the_Loop_Hybrid"]["pass_at_repair"] >= 0.95

    csv_path = tmp_path / "benchmark_test_export.csv"
    exported = runner.export_csv(results, csv_path)
    assert exported.exists()

    with open(exported, "r", encoding="utf-8") as f:
        reader = list(csv.DictReader(f))
        assert len(reader) == 8
        assert reader[0]["topic"] is not None
        assert "qcr_score" in reader[0]


def test_vibevideobench_suite():
    runner = PublicBenchmarkRunner()
    assert len(runner.vibe_tasks) == 34

    vibe_results = runner.run_vibevideobench_suite(max_tasks=3)
    assert len(vibe_results) == 12  # 3 tasks * 4 paradigms

    vibe_summary = runner.aggregate_by_paradigm(vibe_results)
    assert "Learner_in_the_Loop_Hybrid" in vibe_summary
    assert vibe_summary["Learner_in_the_Loop_Hybrid"]["program_check_pass"] > 0.90


def test_run_both_benchmarks():
    runner = PublicBenchmarkRunner()
    combined = runner.run_both_benchmarks(max_mmmc=2, max_vibe=2)

    assert "mmmc" in combined
    assert "vibevideobench" in combined
    assert "combined" in combined
    assert combined["combined"]["total_evaluations"] == 16  # (2 + 2) * 4 paradigms
