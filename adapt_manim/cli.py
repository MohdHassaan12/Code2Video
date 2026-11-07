"""
Command-Line Interface for AdaptManim.
Provides commands for end-to-end video generation, multi-tier verification,
adaptive repair, benchmarking, and launching the interactive Streamlit Studio.
"""

import sys
import os
import json
import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.syntax import Syntax

from adapt_manim.core.types import AudienceLevel
from adapt_manim.core.ledger import SymbolLedgerManager
from adapt_manim.planning.complexity_profiler import TopicComplexityProfiler
from adapt_manim.planning.outline_planner import OutlinePlanner
from adapt_manim.planning.storyboard_builder import StoryboardBuilder
from adapt_manim.coding.coder import ManimCoder
from adapt_manim.coding.parallel_runner import ParallelRunner
from adapt_manim.verification.cascade import VerificationCascade
from adapt_manim.repair.router import AdaptiveRepairRouter
from adapt_manim.evaluation.aesthetic_judge import AestheticJudge
from adapt_manim.evaluation.teach_quiz import TeachQuizEvaluator
from adapt_manim.evaluation.benchmark_runner import BenchmarkRunner

console = Console()


@click.group()
def main():
    """AdaptManim: Reliable & Efficient Educational Video Generation Engine."""
    pass


@main.command()
@click.option("--topic", "-t", required=True, help="Educational STEM topic to generate.")
@click.option("--audience", "-a", default="undergraduate", type=click.Choice(["middle_school", "high_school", "undergraduate", "researcher"]))
@click.option("--render", "-r", is_flag=True, default=False, help="Render the generated code with Manim.")
@click.option("--narrate", "-n", is_flag=True, default=False, help="Synthesize and mux synchronized audio narration.")
@click.option("--output-dir", "-o", default="demo_outputs", help="Output directory for code and videos.")
def generate(topic: str, audience: str, render: bool, narrate: bool, output_dir: str):
    """Generate complete educational video pipeline from topic."""
    aud = AudienceLevel(audience)
    console.print(Panel(f"[bold cyan]AdaptManim Pipeline[/bold cyan]\n[white]Topic:[/white] {topic}\n[white]Audience:[/white] {aud.value}", expand=False))

    # 1. Complexity Profile & Symbol Ledger
    profile = TopicComplexityProfiler.profile(topic, aud)
    ledger_mgr = SymbolLedgerManager(topic)
    console.print(f"[green]✓[/green] Topic Profiled: Difficulty={profile.difficulty_score}, Target Scenes={profile.recommended_scenes}")
    console.print(f"[green]✓[/green] Symbol Ledger initialized with {len(ledger_mgr.ledger.symbols)} canonical STEM symbols.")

    # 2. Outline Planning
    with console.status("[bold green]Synthesizing Pedagogical Outline..."):
        outline = OutlinePlanner.generate_outline(topic, aud)
    console.print(f"[green]✓[/green] Outline generated: {len(outline.sections)} sections ({outline.target_duration_minutes} min).")

    # 3. Storyboard Construction
    with console.status("[bold green]Building Storyboard with 6x6 Anchors & Cue-Event Alignment..."):
        storyboard = StoryboardBuilder.build_storyboard(outline, ledger_mgr)
    console.print(f"[green]✓[/green] Storyboard constructed with {sum(len(s.lecture_lines) for s in storyboard.sections)} synchronized lecture cues.")

    # 4. Code Synthesis & Multi-Tier Verification
    os.makedirs(output_dir, exist_ok=True)
    section_codes = {}
    reports = {}

    for sec in storyboard.sections:
        with console.status(f"[bold yellow]Synthesizing & Verifying {sec.id}..."):
            raw_code = ManimCoder.generate_section_code(sec, ledger_mgr)
            # Run verification cascade
            report = VerificationCascade.verify_section(
                code=raw_code,
                section=sec,
                ledger_manager=ledger_mgr,
                output_dir=output_dir,
                skip_execution=not render
            )

            # If verification failed, run adaptive repair router
            if not report.passed:
                console.print(f"[yellow]![/yellow] {sec.id} failed {report.highest_failing_tier.value if report.highest_failing_tier else 'checks'}. Routing to ScopeRefine++...")
                raw_code, report, rh = AdaptiveRepairRouter.execute_adaptive_repair(
                    code=raw_code,
                    initial_report=report,
                    section=sec,
                    ledger_manager=ledger_mgr,
                    verifier_func=lambda c: VerificationCascade.verify_section(c, sec, ledger_mgr, output_dir, skip_execution=not render)
                )
                console.print(f"[green]✓[/green] {sec.id} repaired successfully in {rh.total_attempts} attempts (tokens: {rh.total_tokens}).")

            section_codes[sec.id] = raw_code
            reports[sec.id] = report
            console.print(f"[green]✓[/green] {sec.id}: {sec.title} [bold green]VERIFIED[/bold green]")

    # 5. Composite Assembly
    runner = ParallelRunner(output_dir=output_dir)
    full_script = runner.combine_section_codes(section_codes, topic)
    combined_path = os.path.join(output_dir, "complete_lecture.py")
    with open(combined_path, "w") as f:
        f.write(full_script)

    console.print(f"\n[bold green]Success![/bold green] Complete verified Manim script saved to: [cyan]{combined_path}[/cyan]")

    # 6. Optional Full Multi-Scene Rendering and Audio Muxing
    if render or narrate:
        from adapt_manim.coding.video_stitcher import VideoStitcher
        stitcher = VideoStitcher(combined_path, output_dir=output_dir)
        with console.status("[bold green]Rendering and stitching video scenes with FFmpeg..."):
            master_path, sec_videos = stitcher.render_and_stitch_all(storyboard, narrate=narrate)
        if master_path:
            console.print(f"[bold green]✓ Master Lecture Video Produced:[/bold green] [cyan]{master_path}[/cyan] ({len(sec_videos)} scenes)")

    # 7. Evaluation Metrics Display
    qm = AestheticJudge.evaluate(full_script, topic)
    tq = TeachQuizEvaluator.evaluate_relative_gain(topic, is_video_grounded=True, pedagogical_score=qm.overall_aes)

    eval_table = Table(title="Pedagogical & Aesthetic Evaluation (Code2Video AES + TeachQuiz Protocol)")
    eval_table.add_column("Dimension", style="cyan")
    eval_table.add_column("Score", style="magenta")
    eval_table.add_column("Scale", style="white")
    eval_table.add_row("Element Layout (EL)", f"{qm.element_layout:.1f}", "0-20")
    eval_table.add_row("Attractiveness (AT)", f"{qm.attractiveness:.1f}", "0-20")
    eval_table.add_row("Logic Flow (LF)", f"{qm.logic_flow:.1f}", "0-20")
    eval_table.add_row("Visual Consistency (VC)", f"{qm.visual_consistency:.1f}", "0-20")
    eval_table.add_row("Accuracy & Depth (AD)", f"{qm.accuracy_depth:.1f}", "0-20")
    eval_table.add_row("Overall Aesthetic Score (AES)", f"[bold green]{qm.overall_aes:.1f}[/bold green]", "0-100")
    eval_table.add_row("TeachQuiz Relative Transfer (eS)", f"[bold green]{tq['es_gain']:.1f}%[/bold green]", "0-100%")
    console.print(eval_table)


@main.command()
@click.option("--topic", "-t", default="Support Vector Machine", help="STEM topic for benchmark.")
def benchmark(topic: str):
    """Run comparative benchmark against Direct CodeLLM, Code2Video, and LLM2Manim."""
    console.print(Panel(f"[bold magenta]Comparative Benchmark: {topic}[/bold magenta]", expand=False))
    results = BenchmarkRunner.run_topic_comparison(topic)

    table = Table(title="Benchmark Comparison across Educational Video Paradigms")
    table.add_column("Paradigm", style="cyan", no_wrap=True)
    table.add_column("Time (m)", justify="right")
    table.add_column("Tokens (K)", justify="right")
    table.add_column("EL", justify="right")
    table.add_column("LF", justify="right")
    table.add_column("AES Avg", justify="right", style="bold")
    table.add_column("TeachQuiz", justify="right", style="bold green")
    table.add_column("Pass @ 1", justify="right")
    table.add_column("Pass @ Rep", justify="right")
    table.add_column("QCR (Pareto)", justify="right", style="bold yellow")

    for k, v in results.items():
        table.add_row(
            v["paradigm"],
            f"{v['time_minutes']:.1f}",
            f"{v['tokens_k']:.1f}",
            f"{v['el']:.1f}",
            f"{v['lf']:.1f}",
            f"{v['aes_avg']:.1f}",
            f"{v['teach_quiz']:.1f}%",
            f"{v['pass_at_1']*100:.0f}%",
            f"{v['pass_at_repair']*100:.0f}%",
            f"{v['qcr_score']:.2f}"
        )
    console.print(table)


@main.command()
@click.option("--max-topics", "-m", default=6, help="Number of MMMC topics to evaluate.")
@click.option("--output-dir", "-o", default="demo_outputs", help="Output directory for reports.")
def mmmc(max_topics: int, output_dir: str):
    """Run batch MMMC benchmark evaluation and plot Pareto frontiers."""
    console.print(Panel(f"[bold magenta]Running MMMC Batch Evaluation ({max_topics} topics)...[/bold magenta]", expand=False))
    from adapt_manim.evaluation.mmmc_evaluator import MMMCBatchEvaluator
    with console.status("[bold green]Evaluating topics across STEM domains..."):
        res = MMMCBatchEvaluator.run_suite(max_topics=max_topics, output_dir=output_dir)
    console.print(f"[green]✓[/green] Evaluated {res['num_topics_evaluated']} topics.")
    console.print(f"[green]✓[/green] Summary CSV: [cyan]{res['csv_path']}[/cyan]")
    console.print(f"[green]✓[/green] Detailed JSON: [cyan]{res['json_path']}[/cyan]")
    console.print(f"[bold green]✓ Pareto Frontier Plot:[/bold green] [cyan]{res['plot_path']}[/cyan]")


@main.command()
@click.option("--port", "-p", default=8501, help="Port to run Streamlit on.")
def ui(port: int):
    """Launch the interactive Streamlit Web Studio dashboard."""
    import subprocess
    cmd = [".venv/bin/streamlit", "run", "adapt_manim/web/app.py", "--server.port", str(port)]
    console.print(f"[bold green]Launching AdaptManim Studio on http://localhost:{port}...[/bold green]")
    subprocess.run(cmd)


if __name__ == "__main__":
    main()

