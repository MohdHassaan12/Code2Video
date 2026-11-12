#!/usr/bin/env python3
"""
Direction D12: Public Benchmark Evaluation Runner.
Executes head-to-head evaluations across:
- MMMC (17 topics, 13 disciplines)
- VibeVideoBench (34 educational tasks, 9 domains)
across 4 paradigms:
1. Direct CodeLLM
2. Code2Video (arXiv:2510.01174)
3. Lessonforge (Audio-first deterministic transpiler)
4. Learner-in-the-Loop Hybrid (Code2Video + Lessonforge + D2 Learner Repair)
"""

import json
from pathlib import Path
from code2video.public_benchmark import PublicBenchmarkRunner


def main():
    print("=" * 80)
    print("DIRECTION D12: PUBLIC BENCHMARK EVALUATIONS (MMMC & VIBEVIDEOBENCH)")
    print("=" * 80)

    runner = PublicBenchmarkRunner()
    out_dir = Path("benchmarks")
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1. Run MMMC
    print(f"\n[1/3] Running MMMC Benchmark ({len(runner.mmmc_benchmark.units)} topics)...")
    mmmc_results = runner.run_mmmc_suite()
    mmmc_csv = runner.export_csv(mmmc_results, out_dir / "mmmc_head_to_head_results.csv")
    mmmc_summary = runner.aggregate_by_paradigm(mmmc_results)
    mmmc_domains = runner.aggregate_by_domain(mmmc_results)
    (out_dir / "mmmc_benchmark_summary.json").write_text(
        json.dumps({"summary": mmmc_summary, "domains": mmmc_domains}, indent=2),
        encoding="utf-8"
    )
    print(f" -> Generated {len(mmmc_results)} evaluations. Saved to {mmmc_csv}")

    # 2. Run VibeVideoBench
    print(f"\n[2/3] Running VibeVideoBench Educational Benchmark ({len(runner.vibe_tasks)} tasks)...")
    vibe_results = runner.run_vibevideobench_suite()
    vibe_csv = runner.export_csv(vibe_results, out_dir / "vibevideobench_head_to_head_results.csv")
    vibe_summary = runner.aggregate_by_paradigm(vibe_results)
    vibe_domains = runner.aggregate_by_domain(vibe_results)
    (out_dir / "vibevideobench_benchmark_summary.json").write_text(
        json.dumps({"summary": vibe_summary, "domains": vibe_domains}, indent=2),
        encoding="utf-8"
    )
    print(f" -> Generated {len(vibe_results)} evaluations. Saved to {vibe_csv}")

    # 3. Aggregate Combined Benchmark
    print("\n[3/3] Aggregating Combined Multi-Corpus Report...")
    combined_results = mmmc_results + vibe_results
    combined_csv = runner.export_csv(combined_results, out_dir / "combined_head_to_head_results.csv")
    combined_summary = runner.aggregate_by_paradigm(combined_results)
    combined_domains = runner.aggregate_by_domain(combined_results)
    (out_dir / "combined_public_benchmark_summary.json").write_text(
        json.dumps({
            "total_evaluations": len(combined_results),
            "summary": combined_summary,
            "domains": combined_domains,
        }, indent=2),
        encoding="utf-8"
    )
    print(f" -> Total {len(combined_results)} evaluations. Saved to {combined_csv}")

    # Print summary tables
    print("\n" + "=" * 80)
    print("MMMC SUMMARY TABLE (17 Topics x 4 Paradigms = 68 Runs)")
    print("=" * 80)
    print(f"{'Paradigm':<28} | {'AES':<5} | {'eS (%)':<6} | {'Up (%)':<6} | {'Prog (%)':<8} | {'Drift(s)':<8} | {'Tok (K)':<7} | {'Time(m)':<7} | {'QCR':<6}")
    print("-" * 105)
    for p, s in mmmc_summary.items():
        print(f"{p:<28} | {s['aes_avg']:<5.1f} | {s['teach_quiz_es']:<6.1f} | {s['visual_uplift']:<6.1f} | {s['program_check_pass']*100:<8.1f} | {s['av_sync_drift_sec']:<8.2f} | {s['tokens_k']:<7.1f} | {s['time_minutes']:<7.1f} | {s['qcr_score']:<6.1f}")

    print("\n" + "=" * 80)
    print("VIBEVIDEOBENCH SUMMARY TABLE (34 Tasks x 4 Paradigms = 136 Runs)")
    print("=" * 80)
    print(f"{'Paradigm':<28} | {'AES':<5} | {'eS (%)':<6} | {'Up (%)':<6} | {'Prog (%)':<8} | {'Drift(s)':<8} | {'Tok (K)':<7} | {'Time(m)':<7} | {'QCR':<6}")
    print("-" * 105)
    for p, s in vibe_summary.items():
        print(f"{p:<28} | {s['aes_avg']:<5.1f} | {s['teach_quiz_es']:<6.1f} | {s['visual_uplift']:<6.1f} | {s['program_check_pass']*100:<8.1f} | {s['av_sync_drift_sec']:<8.2f} | {s['tokens_k']:<7.1f} | {s['time_minutes']:<7.1f} | {s['qcr_score']:<6.1f}")

    print("\n" + "=" * 80)
    print("COMBINED BENCHMARK TOTALS (51 Topics x 4 Paradigms = 204 Runs)")
    print("=" * 80)
    print(f"{'Paradigm':<28} | {'AES':<5} | {'eS (%)':<6} | {'Up (%)':<6} | {'Prog (%)':<8} | {'Drift(s)':<8} | {'Tok (K)':<7} | {'Time(m)':<7} | {'QCR':<6}")
    print("-" * 105)
    for p, s in combined_summary.items():
        print(f"{p:<28} | {s['aes_avg']:<5.1f} | {s['teach_quiz_es']:<6.1f} | {s['visual_uplift']:<6.1f} | {s['program_check_pass']*100:<8.1f} | {s['av_sync_drift_sec']:<8.2f} | {s['tokens_k']:<7.1f} | {s['time_minutes']:<7.1f} | {s['qcr_score']:<6.1f}")


if __name__ == "__main__":
    main()

