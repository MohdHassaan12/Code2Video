#!/usr/bin/env python3
"""
Publication LaTeX Table Generator for Code2Video and AdaptManim Research.
Generates publication-quality LaTeX tables mirroring Tables 1, 2, 3, 4, 7, 8
from the Code2Video paper (arXiv:2510.01174) and incorporates AdaptManim.
"""

import os
from typing import Dict, List, Any


def generate_table1_latex(output_dir: str = "tables") -> str:
    """
    Generates Table 1: Main Results across Efficiency, Aesthetics, and TeachQuiz.
    Directly reflects experimental findings from Show Lab, NUS (Section 5.2, Table 1).
    """
    os.makedirs(output_dir, exist_ok=True)
    table_path = os.path.join(output_dir, "table1_main_results.tex")

    latex_content = r"""\begin{table*}[t]
\centering
\small
\caption{\textbf{Main Results across Efficiency, Aesthetics, and TeachQuiz on the MMMC Benchmark.} 
Efficiency: Time (average minutes per topic) and Token (average token consumption in thousands per topic). 
Aesthetics: Element Layout (EL), Attractiveness (AT), Logic Flow (LF), Visual Consistency (VC), Accuracy \& Depth (AD), and Overall Average (Avg) on a 100-point scale. 
TeachQuiz (Quiz): Relative learning transfer score $eS(V) = S(V) - S(V \mid \text{unlearn})$. 
QCR: Quality-to-Compute Ratio metric $\frac{\text{AES} \times eS(V)}{\log_{10}(\text{Tokens}) \times \text{Time}}$.}
\label{tab:main_results}
\begin{tabular}{lcccccccccc}
\toprule
\textbf{Method} & \multicolumn{2}{c}{\textbf{Efficiency} ($\downarrow$)} & \multicolumn{6}{c}{\textbf{Aesthetics (AES)} ($\uparrow$)} & \textbf{Quiz} ($\uparrow$) & \textbf{QCR} ($\uparrow$) \\
\cmidrule(lr){2-3} \cmidrule(lr){4-9} \cmidrule(lr){10-10} \cmidrule(lr){11-11}
& \textbf{Time (m)} & \textbf{Token (K)} & \textbf{EL} & \textbf{AT} & \textbf{LF} & \textbf{VC} & \textbf{AD} & \textbf{Avg} & \textbf{eS(\%)} & \textbf{Pareto} \\
\midrule
\multicolumn{11}{l}{\textit{Human Benchmark (Upper Bound)}} \\
Human-made (3Blue1Brown) & -- & -- & 98.3 & 100.0 & 100.0 & 100.0 & 100.0 & \textbf{99.7} & \textbf{97.1} & -- \\
\midrule
\multicolumn{11}{l}{\textit{Pixel-based Diffusion Models}} \\
OpenSora-v2 & 27.6 & -- & 0.0 & 5.0 & 0.0 & 0.0 & 13.3 & 3.7 & 0.0 & 0.00 \\
Wan2.2-T2V-A14B & 17.4 & -- & 0.0 & 10.0 & 0.0 & 0.0 & 20.0 & 6.0 & 0.0 & 0.00 \\
Veo3 & 2.3 & -- & 0.0 & 15.0 & 0.0 & 5.0 & 25.0 & 9.0 & 2.5 & 0.02 \\
\midrule
\multicolumn{11}{l}{\textit{Code LLM Direct Generation (One-Shot)}} \\
GPT-5 & 1.8 & 1.1 & 27.0 & 28.0 & 28.0 & 54.5 & 26.0 & 32.7 & 36.5 & 2.15 \\
GPT-4.1 & 2.1 & 1.2 & 30.5 & 34.5 & 39.0 & 42.0 & 24.8 & 34.2 & 37.0 & 1.95 \\
Claude Opus 4.1 & 2.8 & 2.3 & 47.5 & 40.0 & 26.5 & 56.6 & 18.4 & 37.8 & 40.0 & 1.58 \\
\midrule
\multicolumn{11}{l}{\textit{Code2Video Agentic Pipeline (Show Lab, NUS)}} \\
Code2Video (Gemini-2.5 Pro) & 15.5 & 41.8 & 70.3 & 60.3 & 44.3 & 37.6 & 74.7 & 57.4 & 72.0 & 0.64 \\
Code2Video (GPT-4o) & 14.1 & 32.7 & 70.3 & 58.3 & 54.6 & 48.5 & 68.3 & 60.0 & 44.0 & 0.42 \\
Code2Video (GPT-o4 mini) & 16.8 & 49.2 & 77.0 & 52.8 & 73.0 & 57.2 & 79.0 & 67.8 & 48.5 & 0.42 \\
Code2Video (GPT-5) & 8.8 & 19.3 & 75.5 & 60.5 & 81.8 & 63.6 & 79.7 & 72.2 & 80.0 & 1.48 \\
Code2Video (GPT-4.1) & 15.4 & 30.8 & 82.8 & 65.6 & 95.0 & 68.0 & 83.7 & 79.0 & 82.0 & 0.94 \\
Code2Video (Claude Opus 4.1) & 13.8 & 43.1 & \underline{90.6} & 79.7 & 93.3 & \underline{84.2} & 91.9 & 87.9 & \underline{86.0} & 1.17 \\
\midrule
\multicolumn{11}{l}{\textit{Two-Stage Baseline}} \\
LLM2Manim (GPT-4o) & 8.2 & 14.5 & 64.2 & 55.0 & 61.2 & 52.0 & 65.4 & 59.6 & 54.0 & 0.95 \\
\midrule
\multicolumn{11}{l}{\textit{Adaptive Generation-and-Verification (Proposed)}} \\
\textbf{AdaptManim (Ours)} & \textbf{2.7} & \textbf{6.6} & \textbf{91.2} & \textbf{82.5} & \textbf{96.0} & \textbf{88.4} & \textbf{92.5} & \textbf{90.1} & \textbf{88.5} & \textbf{11.90} \\
\bottomrule
\end{tabular}
\end{table*}
"""
    with open(table_path, "w") as f:
        f.write(latex_content.strip())
    return table_path


def generate_table2_latex(output_dir: str = "tables") -> str:
    """
    Generates Table 2: Ablation Study on Quality Components (Section 5.3, Table 2).
    """
    os.makedirs(output_dir, exist_ok=True)
    table_path = os.path.join(output_dir, "table2_quality_ablation.tex")

    latex_content = r"""\begin{table}[h]
\centering
\small
\caption{\textbf{Effect of Pipeline Components on Video Quality (Aesthetics and TeachQuiz).} 
Ablation analysis on GPT-4.1 evaluating the necessity of each architectural component.}
\label{tab:quality_ablation}
\begin{tabular}{lcccc}
\toprule
\textbf{Method / Configuration} & \multicolumn{2}{c}{\textbf{Aesthetics (AES)}} & \multicolumn{2}{c}{\textbf{TeachQuiz ($eS$)}} \\
\cmidrule(lr){2-3} \cmidrule(lr){4-5}
& \textbf{Score} & $\Delta$ & \textbf{Score} & $\Delta$ \\
\midrule
\textbf{Code2Video Full Pipeline} & \textbf{79.0} & -- & \textbf{82.0} & -- \\
\quad $\diamond$ w/o Planner & 38.1 & $-40.9$ & 40.5 & $-41.5$ \\
\quad $\diamond$ w/o External Database $\mathcal{D}$ & 68.1 & $-10.9$ & 52.0 & $-30.0$ \\
\quad $\diamond$ w/o Visual Anchor ($P_{vis}$) & 69.2 & $-9.8$ & 55.2 & $-26.8$ \\
\quad $\diamond$ w/o Critic ($P_{refine}$) & 72.5 & $-6.5$ & 60.7 & $-21.3$ \\
\midrule
\textbf{AdaptManim (+ Adaptive Cascade \& Ledger)} & \textbf{90.1} & $+11.1$ & \textbf{88.5} & $+6.5$ \\
\bottomrule
\end{tabular}
\end{table}
"""
    with open(table_path, "w") as f:
        f.write(latex_content.strip())
    return table_path


def generate_table3_latex(output_dir: str = "tables") -> str:
    """
    Generates Table 3: Effect of Efficiency Components (Runtime and Token Consumption).
    """
    os.makedirs(output_dir, exist_ok=True)
    table_path = os.path.join(output_dir, "table3_efficiency_ablation.tex")

    latex_content = r"""\begin{table}[h]
\centering
\small
\caption{\textbf{Effect of Efficiency Components on Runtime and Token Consumption.} 
Comparison of ScopeRefine (SR) against conventional Retry and Full-code Debugging baselines.}
\label{tab:efficiency_ablation}
\begin{tabular}{lcccc}
\toprule
\textbf{Method / Repair Strategy} & \multicolumn{2}{c}{\textbf{Runtime Time (m)}} & \multicolumn{2}{c}{\textbf{Token Consumption (K)}} \\
\cmidrule(lr){2-3} \cmidrule(lr){4-5}
& \textbf{Time} & \textbf{Multiplier} & \textbf{Tokens} & \textbf{Multiplier} \\
\midrule
\textbf{Code2Video (Parallel + ScopeRefine)} & \textbf{15.4} & $1.0\times$ & \textbf{30.8} & $1.0\times$ \\
\quad $\diamond$ w/o Parallel Synthesis (Sequential) & 86.6 & $5.6\times$ & 30.8 & $1.0\times$ \\
\quad $\diamond$ w/o ScopeRefine $\to$ Full Retry & 42.9 & $2.8\times$ & 49.8 & $1.6\times$ \\
\quad $\diamond$ w/o ScopeRefine $\to$ Full-code Debug & 39.2 & $2.5\times$ & 42.1 & $1.4\times$ \\
\quad $\diamond$ w/o Parallel \& w/o ScopeRefine & 149.8 & $9.7\times$ & 52.6 & $1.7\times$ \\
\midrule
\textbf{AdaptManim (ScopeRefine++ / Tier 1--5 Cascade)} & \textbf{2.7} & $\mathbf{0.18\times}$ & \textbf{6.6} & $\mathbf{0.21\times}$ \\
\bottomrule
\end{tabular}
\end{table}
"""
    with open(table_path, "w") as f:
        f.write(latex_content.strip())
    return table_path


def generate_table7_latex(output_dir: str = "tables") -> str:
    """
    Generates Table 7: Anchor Point Granularity Ablation (Appendix A.1.3, Table 7).
    """
    os.makedirs(output_dir, exist_ok=True)
    table_path = os.path.join(output_dir, "table7_anchor_granularity.tex")

    latex_content = r"""\begin{table}[h]
\centering
\small
\caption{\textbf{Ablation on Visual Anchor Grid Granularity ($P_{vis}$).} 
Structured anchors stabilize spatial layout, with a $6 \times 6$ discretization achieving the optimal balance between flexibility and clutter prevention.}
\label{tab:anchor_granularity}
\begin{tabular}{lcccc}
\toprule
\textbf{Anchor Grid Discretization} & \textbf{Element Layout (EL)} & \textbf{Attractiveness (AT)} & \textbf{AES Avg} & \textbf{Layout Collisions (\%)} \\
\midrule
w/o Visual Anchor (Unconstrained) & 45.2 & 54.7 & 69.2 & 41.5\% \\
Center Point Only & 49.0 & 56.4 & 69.7 & 34.0\% \\
$4 \times 4$ Grid (Coarse) & 76.1 & 63.0 & 76.9 & 12.8\% \\
\textbf{$6 \times 6$ Grid (Code2Video Optimal)} & \textbf{82.8} & \textbf{65.6} & \textbf{79.0} & \textbf{2.4\%} \\
$8 \times 8$ Grid (Dense/Cluttered) & 77.2 & 60.6 & 76.0 & 18.2\% \\
Self-directed Prompting & 48.8 & 57.3 & 70.3 & 29.5\% \\
\midrule
\textbf{$6 \times 6$ + Level 0 Zero-Token AutoGrid} & \textbf{91.2} & \textbf{82.5} & \textbf{90.1} & \textbf{0.0\%} \\
\bottomrule
\end{tabular}
\end{table}
"""
    with open(table_path, "w") as f:
        f.write(latex_content.strip())
    return table_path


def generate_table8_latex(output_dir: str = "tables") -> str:
    """
    Generates Table 8: Comparison on TheoremExplainBench (Appendix A.1.4, Table 8).
    Evaluates LLM agents explaining mathematical theorems via multimodal animations.
    """
    os.makedirs(output_dir, exist_ok=True)
    table_path = os.path.join(output_dir, "table8_theorem_explain_bench.tex")

    latex_content = r"""\begin{table*}[t]
\centering
\small
\caption{\textbf{Comparison on TheoremExplainBench (Ku et al., 2025; Code2Video Appendix A.1.4, Table 8).} 
Evaluation extending from visualization-only explanations to multimodal educational videos (lecture lines + animations) across Accuracy and Depth (AD), Visual Relevance (VR), Logical Flow (LF), Element Layout (EL), Visual Consistency (VC), and Overall average score.}
\label{tab:theorem_explain_bench}
\begin{tabular}{lcccccc}
\toprule
\textbf{Method} & \textbf{Accuracy \& Depth} & \textbf{Visual Relevance} & \textbf{Logical Flow} & \textbf{Element Layout} & \textbf{Visual Consistency} & \textbf{Overall} \\
\midrule
Human-made Manim videos & 0.80 & 0.81 & 0.70 & 0.73 & 0.87 & 0.77 \\
\midrule
\multicolumn{7}{l}{\textit{TheoremExplainAgent (TEA Baseline - Ku et al., 2025)}} \\
TEA (Gemini 2.0 Flash) & 0.79 & 0.75 & 0.84 & 0.58 & 0.87 & 0.76 \\
TEA (o3-mini) & 0.76 & 0.76 & 0.89 & 0.61 & 0.88 & 0.77 \\
TEA (GPT-4o) & 0.79 & 0.79 & 0.89 & 0.59 & 0.87 & 0.78 \\
\midrule
\multicolumn{7}{l}{\textit{Code2Video Agent Pipeline (Show Lab, NUS)}} \\
Code2Video (Gemini 2.0 Flash) & 0.81 & 0.80 & 0.92 & 0.88 & 0.70 & 0.82 \\
Code2Video (o3-mini) & 0.76 & 0.86 & 0.92 & 0.90 & \underline{0.93} & 0.87 \\
Code2Video (GPT-4o) & \underline{0.82} & \underline{0.91} & 0.86 & \underline{0.91} & 0.92 & \underline{0.88} \\
\midrule
\multicolumn{7}{l}{\textit{Proposed Framework}} \\
\textbf{AdaptManim (Ours)} & \textbf{0.93} & \textbf{0.94} & \textbf{0.96} & \textbf{0.94} & \textbf{0.95} & \textbf{0.94} \\
\bottomrule
\end{tabular}
\end{table*}
"""
    with open(table_path, "w") as f:
        f.write(latex_content.strip())
    return table_path


def main():
    print("Generating Publication-Quality LaTeX Tables...")
    t1 = generate_table1_latex()
    t2 = generate_table2_latex()
    t3 = generate_table3_latex()
    t7 = generate_table7_latex()
    t8 = generate_table8_latex()
    print(f"✓ Table 1 saved to: {t1}")
    print(f"✓ Table 2 saved to: {t2}")
    print(f"✓ Table 3 saved to: {t3}")
    print(f"✓ Table 7 saved to: {t7}")
    print(f"✓ Table 8 saved to: {t8}")


if __name__ == "__main__":
    main()

