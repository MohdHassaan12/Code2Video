"""
MMMC Batch Benchmark Evaluator & Pareto Frontier Visualizer.
Executes batch evaluations across MMMC STEM domains and plots publication-quality
Pareto trade-off curves (Aesthetics vs Tokens, TeachQuiz vs Latency, Pass Rates).
"""

import os
import json
import time
from typing import Dict, List, Any, Optional
import pandas as pd
import matplotlib.pyplot as plt

from code2video.mmmc import MMMCBenchmark
from adapt_manim.evaluation.benchmark_runner import BenchmarkRunner


class MMMCBatchEvaluator:
    """Runs batch benchmarking and generates visual Pareto frontiers."""

    @classmethod
    def run_suite(
        cls,
        max_topics: Optional[int] = 6,
        output_dir: str = "demo_outputs"
    ) -> Dict[str, Any]:
        """Runs comparative evaluations across benchmark topics."""
        os.makedirs(output_dir, exist_ok=True)
        benchmark = MMMCBenchmark()
        units = benchmark.units[:max_topics] if max_topics else benchmark.units

        all_topic_results = []

        for unit in units:
            res = BenchmarkRunner.run_topic_comparison(unit.topic)
            for paradigm, p_data in res.items():
                p_copy = dict(p_data)
                p_copy["topic"] = unit.topic
                p_copy["category"] = unit.category
                all_topic_results.append(p_copy)

        df = pd.DataFrame(all_topic_results)

        # Save summary CSV and JSON
        csv_path = os.path.join(output_dir, "benchmark_summary.csv")
        json_path = os.path.join(output_dir, "benchmark_results.json")
        df.to_csv(csv_path, index=False)
        with open(json_path, "w") as f:
            json.dump(all_topic_results, f, indent=2)

        # Generate Pareto frontier plots
        plot_path = cls.plot_pareto_frontiers(df, output_dir)

        # Aggregate summary table
        agg_summary = df.groupby("paradigm").agg({
            "time_minutes": "mean",
            "tokens_k": "mean",
            "el": "mean",
            "lf": "mean",
            "aes_avg": "mean",
            "teach_quiz": "mean",
            "pass_at_1": "mean",
            "pass_at_repair": "mean",
            "qcr_score": "mean"
        }).reset_index().round(2)

        return {
            "csv_path": csv_path,
            "json_path": json_path,
            "plot_path": plot_path,
            "summary_df": agg_summary.to_dict(orient="records"),
            "num_topics_evaluated": len(units)
        }

    @classmethod
    def plot_pareto_frontiers(cls, df: pd.DataFrame, output_dir: str = "demo_outputs") -> str:
        """Generates a 4-panel publication-ready comparison plot."""
        plt.style.use("seaborn-v0_8-whitegrid" if "seaborn-v0_8-whitegrid" in plt.style.available else "default")
        fig, axes = plt.subplots(2, 2, figsize=(14, 10))

        agg = df.groupby("paradigm").agg({
            "tokens_k": "mean",
            "aes_avg": "mean",
            "time_minutes": "mean",
            "teach_quiz": "mean",
            "pass_at_1": "mean",
            "pass_at_repair": "mean",
            "qcr_score": "mean"
        }).reset_index()

        colors = {
            "Direct CodeLLM": "#888888",
            "Code2Video": "#FC6255",
            "LLM2Manim": "#58C4DD",
            "AdaptManim (Ours)": "#83C167"
        }

        # 1. Aesthetics vs Tokens (K)
        ax1 = axes[0, 0]
        for _, row in agg.iterrows():
            c = colors.get(row["paradigm"], "#333333")
            ax1.scatter(row["tokens_k"], row["aes_avg"], color=c, s=180, label=row["paradigm"], zorder=5)
            ax1.annotate(row["paradigm"], (row["tokens_k"], row["aes_avg"] + 1.5), fontsize=10, fontweight="bold")
        ax1.set_title("Aesthetic Score (AES) vs Token Consumption", fontsize=12, fontweight="bold")
        ax1.set_xlabel("Average Tokens (K) per Topic [Lower is Better]", fontsize=11)
        ax1.set_ylabel("Aesthetics Score (0-100) [Higher is Better]", fontsize=11)
        ax1.set_ylim(20, 105)

        # 2. TeachQuiz vs Generation Time
        ax2 = axes[0, 1]
        for _, row in agg.iterrows():
            c = colors.get(row["paradigm"], "#333333")
            ax2.scatter(row["time_minutes"], row["teach_quiz"], color=c, s=180, zorder=5)
            ax2.annotate(row["paradigm"], (row["time_minutes"], row["teach_quiz"] + 1.5), fontsize=10, fontweight="bold")
        ax2.set_title("TeachQuiz Relative Gain (eS) vs Synthesis Time", fontsize=12, fontweight="bold")
        ax2.set_xlabel("Average Time (Minutes) [Lower is Better]", fontsize=11)
        ax2.set_ylabel("TeachQuiz Relative Gain (%) [Higher is Better]", fontsize=11)
        ax2.set_ylim(20, 100)

        # 3. Pass Rate @ 1 vs Pass Rate @ Repair
        ax3 = axes[1, 0]
        bar_width = 0.35
        x_indices = range(len(agg))
        ax3.bar([x - bar_width/2 for x in x_indices], agg["pass_at_1"] * 100, width=bar_width, label="Pass @ 1", color="#58C4DD")
        ax3.bar([x + bar_width/2 for x in x_indices], agg["pass_at_repair"] * 100, width=bar_width, label="Pass @ Repair", color="#83C167")
        ax3.set_xticks(list(x_indices))
        ax3.set_xticklabels(agg["paradigm"], rotation=15, ha="right", fontsize=9, fontweight="bold")
        ax3.set_title("Reliability: First-Pass vs Post-Repair Compilation", fontsize=12, fontweight="bold")
        ax3.set_ylabel("Success Rate (%)", fontsize=11)
        ax3.set_ylim(0, 115)
        ax3.legend()

        # 4. Pareto Efficiency: Quality-to-Compute Ratio (QCR)
        ax4 = axes[1, 1]
        bars = ax4.bar(agg["paradigm"], agg["qcr_score"], color=[colors.get(p, "#58C4DD") for p in agg["paradigm"]])
        ax4.set_title("Quality-to-Compute Ratio (QCR Pareto Efficiency)", fontsize=12, fontweight="bold")
        ax4.set_ylabel("QCR Score = AES / (Token_K + 1)", fontsize=11)
        ax4.set_xticks(range(len(agg)))
        ax4.set_xticklabels(agg["paradigm"], rotation=15, ha="right", fontsize=9, fontweight="bold")
        for bar in bars:
            height = bar.get_height()
            ax4.annotate(f"{height:.2f}",
                         xy=(bar.get_x() + bar.get_width() / 2, height),
                         xytext=(0, 3), textcoords="offset points",
                         ha="center", va="bottom", fontweight="bold")

        plt.tight_layout()
        plot_path = os.path.join(output_dir, "pareto_frontier.png")
        plt.savefig(plot_path, dpi=300)
        plt.close()

        return plot_path
