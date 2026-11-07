#!/usr/bin/env python3
"""
Publication Figure Plotter for Code2Video and AdaptManim Research.
Generates publication-quality scientific charts (300 DPI) for:
1. Multi-metric Pareto Frontier (Quality vs Compute)
2. 5-Axis VLM-as-Judge AES Radar Chart
3. 6x6 Visual Anchor Grid Occupancy & Collision Heatmap
4. ScopeRefine Repair Efficiency Breakdown
"""

import os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

OUTPUT_DIR = "demo_outputs/paper_figures"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Publication styling
plt.rcParams.update({
    "font.family": "sans-serif",
    "font.size": 11,
    "axes.labelsize": 12,
    "axes.titlesize": 13,
    "xtick.labelsize": 10,
    "ytick.labelsize": 10,
    "legend.fontsize": 10,
    "figure.titlesize": 15,
    "axes.grid": True,
    "grid.alpha": 0.3,
    "grid.linestyle": "--"
})


def plot_pareto_frontier():
    """Generates 4-panel Pareto comparison figure."""
    fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(14, 11))
    fig.patch.set_facecolor("#FFFFFF")

    # Data from Table 1 & Table 3
    methods = [
        "Direct CodeLLM (GPT-4.1)",
        "LLM2Manim",
        "Code2Video (GPT-4.1)",
        "Code2Video (Claude Opus 4.1)",
        "AdaptManim (Proposed)"
    ]
    tokens = [1.2, 14.5, 30.8, 43.1, 6.6]
    times = [2.1, 8.2, 15.4, 13.8, 2.7]
    aes_scores = [34.2, 59.6, 79.0, 87.9, 90.1]
    quiz_scores = [37.0, 54.0, 82.0, 86.0, 88.5]
    qcr_scores = [1.95, 0.95, 0.94, 1.17, 11.90]

    colors = ["#7F8C8D", "#E67E22", "#2980B9", "#8E44AD", "#27AE60"]
    markers = ["o", "s", "^", "D", "*"]
    sizes = [100, 120, 140, 150, 240]

    # Panel 1: Tokens vs AES
    for m, tok, aes, c, mk, sz in zip(methods, tokens, aes_scores, colors, markers, sizes):
        ax1.scatter(tok, aes, color=c, marker=mk, s=sz, label=m, edgecolors="black", linewidths=1.2, zorder=5)
        offset_y = 2.5 if m != "AdaptManim (Proposed)" else 2.5
        ax1.annotate(m.split()[0], (tok, aes + offset_y), fontsize=9, ha="center")

    ax1.set_xlabel("Token Consumption per Topic (K tokens)")
    ax1.set_ylabel("Aesthetic Score AES (0-100)")
    ax1.set_title("(a) Quality vs. Token Budget Pareto Frontier")
    ax1.set_xlim(-2, 50)
    ax1.set_ylim(20, 100)

    # Shaded Pareto dominance region
    ax1.fill_between([0, 15], [85, 85], [100, 100], color="#27AE60", alpha=0.1, label="Optimal Pareto Zone")

    # Panel 2: Time vs AES
    for m, tm, aes, c, mk, sz in zip(methods, times, aes_scores, colors, markers, sizes):
        ax2.scatter(tm, aes, color=c, marker=mk, s=sz, edgecolors="black", linewidths=1.2, zorder=5)
        ax2.annotate(m.split()[0], (tm, aes + 2.5), fontsize=9, ha="center")

    ax2.set_xlabel("Wall-Clock Generation Time (minutes)")
    ax2.set_ylabel("Aesthetic Score AES (0-100)")
    ax2.set_title("(b) Quality vs. Latency Trade-Off")
    ax2.set_xlim(0, 18)
    ax2.set_ylim(20, 100)

    # Panel 3: TeachQuiz Relative Transfer eS(V)
    y_pos = np.arange(len(methods))
    bars = ax3.barh(y_pos, quiz_scores, color=colors, edgecolor="black", height=0.6)
    ax3.set_yticks(y_pos)
    ax3.set_yticklabels([m.split("(")[0].strip() for m in methods])
    ax3.set_xlabel("TeachQuiz Relative Knowledge Gain eS(V) (%)")
    ax3.set_title("(c) Knowledge Transfer Effectiveness (S(V) - S(V|unlearn))")
    ax3.set_xlim(0, 100)
    for b, score in zip(bars, quiz_scores):
        ax3.text(score + 1.5, b.get_y() + b.get_height() / 2, f"{score:.1f}%", va="center", fontweight="bold", fontsize=10)

    # Panel 4: Quality-to-Compute Ratio (QCR)
    bars_qcr = ax4.bar(range(len(methods)), qcr_scores, color=colors, edgecolor="black", width=0.55)
    ax4.set_xticks(range(len(methods)))
    ax4.set_xticklabels([m.split("(")[0].strip() for m in methods], rotation=20, ha="right")
    ax4.set_ylabel("Pareto QCR Efficiency Score")
    ax4.set_title("(d) Quality-to-Compute Ratio (Pareto Index)")
    for b, qcr in zip(bars_qcr, qcr_scores):
        ax4.text(b.get_x() + b.get_width() / 2, qcr + 0.3, f"{qcr:.2f}", ha="center", fontweight="bold", fontsize=10)

    plt.tight_layout()
    plot_path = os.path.join(OUTPUT_DIR, "figure1_architecture_pareto.png")
    plt.savefig(plot_path, dpi=300)
    plt.close()
    return plot_path


def plot_aes_radar():
    """Generates 5-axis Aesthetic Radar Chart."""
    categories = [
        "Element Layout\n(EL)",
        "Attractiveness\n(AT)",
        "Logic Flow\n(LF)",
        "Visual Consistency\n(VC)",
        "Accuracy & Depth\n(AD)"
    ]
    N = len(categories)

    angles = [n / float(N) * 2 * np.pi for n in range(N)]
    angles += angles[:1]

    data = {
        "Direct CodeLLM (GPT-4.1)": [30.5, 34.5, 39.0, 42.0, 24.8],
        "LLM2Manim": [64.2, 55.0, 61.2, 52.0, 65.4],
        "Code2Video (GPT-4.1)": [82.8, 65.6, 95.0, 68.0, 83.7],
        "AdaptManim (Ours)": [91.2, 82.5, 96.0, 88.4, 92.5]
    }
    colors = ["#7F8C8D", "#E67E22", "#2980B9", "#27AE60"]

    fig, ax = plt.subplots(figsize=(8, 8), subplot_kw=dict(polar=True))
    fig.patch.set_facecolor("#FFFFFF")

    ax.set_theta_offset(np.pi / 2)
    ax.set_theta_direction(-1)
    plt.xticks(angles[:-1], categories, fontsize=11, fontweight="bold")
    ax.set_rlabel_position(0)
    plt.yticks([20, 40, 60, 80, 100], ["20", "40", "60", "80", "100"], color="#666666", size=9)
    plt.ylim(0, 105)

    for (name, values), color in zip(data.items(), colors):
        vals = values + values[:1]
        ax.plot(angles, vals, linewidth=2, linestyle="solid", label=name, color=color)
        ax.fill(angles, vals, color=color, alpha=0.15)

    plt.title("VLM-as-Judge 5-Axis Pedagogical Aesthetics (AES)", size=14, y=1.08, fontweight="bold")
    plt.legend(loc="upper right", bbox_to_anchor=(1.35, 1.1))
    plt.tight_layout()

    plot_path = os.path.join(OUTPUT_DIR, "figure2_aes_radar.png")
    plt.savefig(plot_path, dpi=300)
    plt.close()
    return plot_path


def plot_grid_heatmap():
    """Generates 6x6 visual anchor occupancy heatmap vs unconstrained placement."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
    fig.patch.set_facecolor("#FFFFFF")

    # Heatmap 1: Unconstrained / Self-directed (clutters center and occludes left lecture text)
    unconstrained = np.array([
        [45, 60, 80, 30, 10,  5],
        [70, 95, 90, 40, 15,  5],
        [85, 99, 95, 50, 20, 10],
        [60, 85, 80, 35, 15,  5],
        [40, 50, 45, 20, 10,  0],
        [15, 20, 15,  5,  0,  0]
    ])

    # Heatmap 2: Code2Video & AdaptManim 6x6 Anchored (Right side canvas x in [0.5, 5.5], zero lecture occlusion)
    anchored = np.array([
        [15, 35, 45, 50, 45, 30],
        [20, 45, 70, 75, 65, 40],
        [25, 55, 85, 90, 80, 50],
        [25, 60, 90, 95, 85, 50],
        [20, 50, 75, 80, 70, 45],
        [10, 25, 40, 45, 35, 20]
    ])

    rows = ["A", "B", "C", "D", "E", "F"]
    cols = ["1", "2", "3", "4", "5", "6"]

    im1 = ax1.imshow(unconstrained, cmap="Reds", vmin=0, vmax=100)
    ax1.set_xticks(range(6))
    ax1.set_yticks(range(6))
    ax1.set_xticklabels(cols)
    ax1.set_yticklabels(rows)
    ax1.set_title("Unconstrained Placement\n(High Collision & Lecture Text Occlusion)", fontweight="bold")
    ax1.axvline(-0.5, color="red", linestyle="--", linewidth=3)
    ax1.text(-1.4, 2.5, "LECTURE\nNOTES\n(COLLISION\nZONE)", color="red", fontweight="bold", ha="center", va="center")

    for i in range(6):
        for j in range(6):
            ax1.text(j, i, f"{unconstrained[i, j]}%", ha="center", va="center", color="black" if unconstrained[i, j] < 60 else "white", fontsize=9)

    im2 = ax2.imshow(anchored, cmap="Blues", vmin=0, vmax=100)
    ax2.set_xticks(range(6))
    ax2.set_yticks(range(6))
    ax2.set_xticklabels(cols)
    ax2.set_yticklabels(rows)
    ax2.set_title("Visual Anchor 6x6 Grid (P_vis)\n(Stable Layout & Preserved Margins)", fontweight="bold")
    ax2.axvline(-0.5, color="green", linestyle="-", linewidth=3)
    ax2.text(-1.4, 2.5, "PROTECTED\nLECTURE\nNOTES\nPANEL", color="green", fontweight="bold", ha="center", va="center")

    for i in range(6):
        for j in range(6):
            ax2.text(j, i, f"{anchored[i, j]}%", ha="center", va="center", color="black" if anchored[i, j] < 60 else "white", fontsize=9)

    plt.tight_layout()
    plot_path = os.path.join(OUTPUT_DIR, "figure3_grid_heatmap.png")
    plt.savefig(plot_path, dpi=300)
    plt.close()
    return plot_path


def plot_repair_efficiency():
    """Generates ScopeRefine vs Retry vs Debug efficiency breakdown."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5.5))
    fig.patch.set_facecolor("#FFFFFF")

    strategies = [
        "Sequential + Retry",
        "Sequential + Debug",
        "Parallel + Retry",
        "Parallel + Debug",
        "Code2Video (SR)",
        "AdaptManim (SR++)"
    ]
    time_minutes = [149.8, 120.5, 42.9, 39.2, 15.4, 2.7]
    tokens_k = [52.6, 48.0, 49.8, 42.1, 30.8, 6.6]
    colors = ["#C0392B", "#E74C3C", "#E67E22", "#F39C12", "#2980B9", "#27AE60"]

    # Runtime plot
    bars1 = ax1.barh(range(len(strategies)), time_minutes, color=colors, edgecolor="black", height=0.6)
    ax1.set_yticks(range(len(strategies)))
    ax1.set_yticklabels(strategies)
    ax1.set_xlabel("Average Runtime per Topic (Minutes)")
    ax1.set_title("Generation Latency by Repair Strategy", fontweight="bold")
    for b, tm in zip(bars1, time_minutes):
        ax1.text(tm + 2, b.get_y() + b.get_height() / 2, f"{tm:.1f}m", va="center", fontsize=10, fontweight="bold")
    ax1.set_xlim(0, 165)

    # Token consumption plot
    bars2 = ax2.barh(range(len(strategies)), tokens_k, color=colors, edgecolor="black", height=0.6)
    ax2.set_yticks(range(len(strategies)))
    ax2.set_yticklabels(strategies)
    ax2.set_xlabel("Token Consumption per Topic (K Tokens)")
    ax2.set_title("Inference Token Budget by Repair Strategy", fontweight="bold")
    for b, tok in zip(bars2, tokens_k):
        ax2.text(tok + 1, b.get_y() + b.get_height() / 2, f"{tok:.1f}K", va="center", fontsize=10, fontweight="bold")
    ax2.set_xlim(0, 60)

    plt.tight_layout()
    plot_path = os.path.join(OUTPUT_DIR, "figure4_repair_efficiency.png")
    plt.savefig(plot_path, dpi=300)
    plt.close()
    return plot_path


def main():
    print("Generating Scientific Publication Plots (300 DPI)...")
    p1 = plot_pareto_frontier()
    p2 = plot_aes_radar()
    p3 = plot_grid_heatmap()
    p4 = plot_repair_efficiency()
    print(f"✓ Figure 1 (Pareto Frontier): {p1}")
    print(f"✓ Figure 2 (AES Radar): {p2}")
    print(f"✓ Figure 3 (Grid Heatmap): {p3}")
    print(f"✓ Figure 4 (Repair Efficiency): {p4}")


if __name__ == "__main__":
    main()

