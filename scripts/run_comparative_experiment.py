#!/usr/bin/env python3
"""
Automated Comparative Benchmark Experiment Runner.
Executes systematic empirical evaluations comparing:
1. Direct CodeLLM (One-shot code synthesis)
2. Code2Video (Show Lab, NUS 3-agent pipeline with ScopeRefine)
3. LLM2Manim (Two-stage planning + execution repair)
4. AdaptManim (Adaptive Pareto-optimal pipeline)

Calculates complete metrics:
- Aesthetics (EL, AT, LF, VC, AD, Overall AES)
- Knowledge Transfer (TeachQuiz eS(V) = S(V) - S(V|unlearn))
- Efficiency (Tokens consumed, Wall-clock time, Pass rate)
- Pareto Quality-to-Compute Ratio (QCR Index)
"""

import os
import sys
import json
import csv
import time
from typing import List, Dict, Any, Optional
import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from code2video.mmmc import MMMCBenchmark
from code2video.pipeline import Code2VideoPipeline
from adapt_manim.evaluation.benchmark_runner import BenchmarkRunner

console = Console()


@click.command()
@click.option("--topics", "-t", default=None, help="Comma-separated topic names to evaluate.")
@click.option("--category", "-c", default=None, help="Filter topics by MMMC category (e.g. Calculus, Neural Networks).")
@click.option("--max-topics", "-m", default=3, help="Max topics to run in this experiment.")
@click.option("--output-dir", "-o", default="demo_outputs/experiments", help="Output directory.")
def run_experiment(topics: Optional[str], category: Optional[str], max_topics: int, output_dir: str):
    """Executes multi-paradigm comparative benchmark experiments across MMMC topics."""
    os.makedirs(output_dir, exist_ok=True)
    benchmark = MMMCBenchmark()

    # Determine topic list
    selected_units = []
    if topics:
        topic_names = [t.strip() for t in topics.split(",")]
        for name in topic_names:
            u = benchmark.get_topic_by_name(name)
            if u:
                selected_units.append(u)
            else:
                console.print(f"[yellow]Warning: Topic '{name}' not found in canonical corpus, creating custom unit.[/yellow]")
                from code2video.mmmc import MMMCTopicUnit
                selected_units.append(MMMCTopicUnit(
                    unit_id=f"custom_{len(selected_units)+1}",
                    topic=name,
                    category=category or "Custom",
                    duration_sec=180
                ))
    elif category:
        selected_units = benchmark.get_topics_by_category(category)
    else:
        # Default representative topics from different domains
        rep_topics = [
            "Support Vector Machine and Maximum Margin Hyperplanes",
            "The Determinant and Area Scaling",
            "Euler's Formula: The Most Beautiful Equation"
        ]
        for t in rep_topics:
            u = benchmark.get_topic_by_name(t)
            if u:
                selected_units.append(u)

    selected_units = selected_units[:max_topics]

    console.print(Panel(
        f"[bold cyan]MMMC Comparative Benchmark Experiment[/bold cyan]\n"
        f"Evaluating {len(selected_units)} topic units across 4 paradigms:\n"
        f"1. Direct CodeLLM | 2. Code2Video | 3. LLM2Manim | 4. AdaptManim",
        expand=False
    ))

    all_results = []
    summary_rows = []

    for idx, unit in enumerate(selected_units, 1):
        console.rule(f"[bold yellow]Topic {idx}/{len(selected_units)}: {unit.topic} ({unit.category})[/bold yellow]")
        
        topic_res = BenchmarkRunner.run_topic_comparison(unit.topic)
        all_results.append({
            "unit_id": unit.unit_id,
            "topic": unit.topic,
            "category": unit.category,
            "key_formula": unit.key_formula,
            "results": topic_res
        })

        for paradigm_key in ["Direct_CodeLLM", "Code2Video", "LLM2Manim", "AdaptManim"]:
            if paradigm_key in topic_res:
                data = topic_res[paradigm_key]
                summary_rows.append({
                    "Topic": unit.topic,
                    "Category": unit.category,
                    "Paradigm": data["paradigm"],
                    "Tokens_K": data["tokens_k"],
                    "Time_Min": data["time_minutes"],
                    "AES_Avg": data["aes_avg"],
                    "TeachQuiz_Gain": data["teach_quiz"],
                    "Pass_Rate": data["pass_at_repair"] * 100,
                    "QCR_Score": data["qcr_score"]
                })

    # Save JSON results
    json_path = os.path.join(output_dir, "comparative_results.json")
    with open(json_path, "w") as f:
        json.dump(all_results, f, indent=2)

    # Save CSV summary
    csv_path = os.path.join(output_dir, "comparative_summary.csv")
    if summary_rows:
        keys = summary_rows[0].keys()
        with open(csv_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            writer.writerows(summary_rows)

    # Display Aggregate Table
    console.print("\n")
    table = Table(title="Aggregated Experimental Comparison Across Evaluated Topics")
    table.add_column("Paradigm", style="cyan", no_wrap=True)
    table.add_column("Mean Time (m)", justify="right")
    table.add_column("Mean Tokens (K)", justify="right")
    table.add_column("Mean AES", justify="right", style="bold")
    table.add_column("TeachQuiz Gain", justify="right", style="bold green")
    table.add_column("Pass Rate", justify="right")
    table.add_column("Mean QCR Index", justify="right", style="bold yellow")

    for paradigm in ["Direct CodeLLM", "Code2Video", "LLM2Manim", "AdaptManim"]:
        p_rows = [r for r in summary_rows if r["Paradigm"].startswith(paradigm) or paradigm in r["Paradigm"]]
        if p_rows:
            avg_time = sum(r["Time_Min"] for r in p_rows) / len(p_rows)
            avg_tokens = sum(r["Tokens_K"] for r in p_rows) / len(p_rows)
            avg_aes = sum(r["AES_Avg"] for r in p_rows) / len(p_rows)
            avg_tq = sum(r["TeachQuiz_Gain"] for r in p_rows) / len(p_rows)
            avg_pass = sum(r["Pass_Rate"] for r in p_rows) / len(p_rows)
            avg_qcr = sum(r["QCR_Score"] for r in p_rows) / len(p_rows)

            table.add_row(
                paradigm,
                f"{avg_time:.2f}",
                f"{avg_tokens:.2f}",
                f"{avg_aes:.1f}",
                f"{avg_tq:.1f}%",
                f"{avg_pass:.0f}%",
                f"{avg_qcr:.2f}"
            )

    console.print(table)
    console.print(f"\n[green]✓[/green] Complete JSON records written to: [cyan]{json_path}[/cyan]")
    console.print(f"[green]✓[/green] CSV summary written to: [cyan]{csv_path}[/cyan]")


if __name__ == "__main__":
    run_experiment()
