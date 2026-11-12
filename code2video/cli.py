"""
Official Command-Line Interface for Code2Video.
Provides commands to run Code2Video generation, visual critic analysis,
MMMC benchmark inspection, and side-by-side comparative evaluations.
"""

import os
import json
from typing import Optional
import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from code2video.pipeline import Code2VideoPipeline
from code2video.mmmc import MMMCBenchmark
from code2video.critic import Code2VideoCritic
from code2video.evaluator import Code2VideoEvaluator
from adapt_manim.evaluation.benchmark_runner import BenchmarkRunner

console = Console()


@click.group()
def main():
    """Code2Video: A Code-Centric Paradigm for Educational Video Generation (Show Lab, NUS)."""
    pass


@main.command()
@click.option("--topic", "-t", required=True, help="Learning topic query Q.")
@click.option("--audience", "-a", default="undergraduate", help="Target audience level.")
@click.option("--render", "-r", is_flag=True, default=False, help="Render the generated Manim code.")
@click.option("--narrate", "-n", is_flag=True, default=False, help="Synthesize neural narration audio with dynamic audio-visual pacing.")
@click.option("--interactive", "-i", is_flag=True, default=False, help="Generate interactive active-recall HTML5 web companion.")
@click.option("--audit-vision", is_flag=True, default=False, help="Run zero-token static computer vision WCAG contrast and clutter audit.")
@click.option("--language", "-l", default="en", help="Speech and subtitle language code (en, es, de, fr, hi, zh, ja).")
@click.option("--output-dir", "-o", default="demo_outputs/code2video", help="Output directory.")
def generate(topic: str, audience: str, render: bool, narrate: bool, interactive: bool, audit_vision: bool, language: str, output_dir: str):
    """Execute the full 3-stage Code2Video agent pipeline (Planner -> Coder -> Critic)."""
    console.print(Panel(f"[bold cyan]Code2Video Generation Pipeline[/bold cyan]\nTopic: {topic}\nAudience: {audience}\nNarrate: {narrate} | Language: {language} | Interactive: {interactive}", expand=False))

    pipeline = Code2VideoPipeline(output_dir=output_dir)
    with console.status("[bold green]Executing Planner, Coder (ScopeRefine), and Critic..."):
        res = pipeline.run(
            topic=topic,
            audience=audience,
            render=render,
            narrate=narrate,
            interactive=interactive,
            audit_vision=audit_vision,
            language=language
        )

    console.print(f"[green]✓[/green] Completed in {res['wall_clock_time_sec']}s (Est. Tokens: {res['tokens_consumed']}).")
    console.print(f"[green]✓[/green] Code written to: [cyan]{res['script_path']}[/cyan]")
    if res.get("master_video_path"):
        console.print(f"[bold green]✓ Master Video Rendered:[/bold green] [cyan]{res['master_video_path']}[/cyan]")
    if res.get("interactive_player_path"):
        console.print(f"[bold magenta]✓ Interactive Active-Recall Companion:[/bold magenta] [cyan]{res['interactive_player_path']}[/cyan]")

    # Static Vision & Accessibility Audit Output
    if res.get("vision_audit"):
        va = res["vision_audit"]
        wcag = va.get("wcag_contrast", {})
        clutter = va.get("visual_clutter", {})
        v_table = Table(title="Computer Vision & WCAG Accessibility Audit")
        v_table.add_column("Criterion", style="cyan")
        v_table.add_column("Measurement", style="magenta")
        v_table.add_column("Standard", style="green")
        v_table.add_row("WCAG Contrast Ratio", f"{wcag.get('contrast_ratio', 0.0)}:1", f"{wcag.get('rating', 'N/A')}")
        v_table.add_row("Visual Clutter Index", f"{clutter.get('clutter_index', 0.0)} / 100", f"{clutter.get('status', 'N/A')}")
        v_table.add_row("Composite Accessibility Score", f"[bold green]{va.get('composite_accessibility_score', 0.0)} / 100[/bold green]", "Zero-Token CV Gate")
        console.print(v_table)

    # Aesthetic & TeachQuiz Table
    aes = res["aesthetics"]
    tq = res["teach_quiz"]

    table = Table(title="Code2Video Evaluation (VLM-as-a-Judge AES & TeachQuiz)")
    table.add_column("Dimension", style="cyan")
    table.add_column("Score", style="magenta")
    table.add_column("Scale", style="white")
    table.add_row("Element Layout (EL)", f"{aes['element_layout']:.1f}", "0-20")
    table.add_row("Attractiveness (AT)", f"{aes['attractiveness']:.1f}", "0-20")
    table.add_row("Logic Flow (LF)", f"{aes['logic_flow']:.1f}", "0-20")
    table.add_row("Visual Consistency (VC)", f"{aes['visual_consistency']:.1f}", "0-20")
    table.add_row("Accuracy & Depth (AD)", f"{aes['accuracy_depth']:.1f}", "0-20")
    table.add_row("Overall Aesthetic Score (AES)", f"[bold green]{aes['overall_aes']:.1f}[/bold green]", "0-100")
    table.add_row("TeachQuiz Relative Transfer (eS)", f"[bold green]{tq['es_gain']:.1f}%[/bold green]", "0-100%")
    table.add_row("Pareto Efficiency (QCR Index)", f"[bold yellow]{res.get('pareto_qcr_score', 0.0):.2f}[/bold yellow]", "Higher is better")
    console.print(table)


@main.command()
@click.option("--category", "-c", default=None, help="Filter by MMMC category (e.g. Calculus, Neural Networks).")
def mmmc(category: Optional[str]):
    """Inspect the MMMC (Multimodal Manim Mastery Corpus) benchmark dataset."""
    benchmark = MMMCBenchmark()
    console.print(Panel(f"[bold magenta]MMMC Benchmark (3Blue1Brown Corpus - 13 Subject Areas)[/bold magenta]", expand=False))

    units = benchmark.get_topics_by_category(category) if category else benchmark.units
    table = Table(title=f"MMMC Topics ({len(units)} units)")
    table.add_column("ID", style="dim")
    table.add_column("Topic", style="cyan")
    table.add_column("Category", style="yellow")
    table.add_column("Duration", justify="right")
    table.add_column("Key Formula", style="green")

    for u in units:
        table.add_row(u.unit_id, u.topic, u.category, f"{u.duration_sec}s", u.key_formula or "N/A")
    console.print(table)


@main.command()
@click.option("--topic", "-t", default="Support Vector Machine", help="Topic to compare.")
def compare(topic: str):
    """Run side-by-side head-to-head comparison between Code2Video and AdaptManim."""
    console.print(Panel(f"[bold yellow]Head-to-Head Comparison: {topic}[/bold yellow]", expand=False))
    results = BenchmarkRunner.run_topic_comparison(topic)

    table = Table(title="Head-to-Head Architectural Comparison")
    table.add_column("Paradigm", style="cyan")
    table.add_column("Time (min)", justify="right")
    table.add_column("Tokens (K)", justify="right")
    table.add_column("AES Avg", justify="right", style="bold")
    table.add_column("TeachQuiz", justify="right", style="bold green")
    table.add_column("Pass Rate", justify="right")
    table.add_column("Pareto Score (QCR)", justify="right", style="bold yellow")

    for k in ["Direct_CodeLLM", "Code2Video", "LLM2Manim", "AdaptManim"]:
        if k in results:
            v = results[k]
            table.add_row(
                v["paradigm"],
                f"{v['time_minutes']:.1f}",
                f"{v['tokens_k']:.1f}",
                f"{v['aes_avg']:.1f}",
                f"{v['teach_quiz']:.1f}%",
                f"{v['pass_at_repair']*100:.0f}%",
                f"{v['qcr_score']:.2f}"
            )
    console.print(table)


@main.command()
@click.option("--id", "-i", default=None, help="Specific theorem ID (e.g. thm_01).")
def theorem(id: Optional[str]):
    """Inspect TheoremExplainBench evaluation suite (Appendix A.1.4, Table 8)."""
    from code2video.theorem_bench import TheoremExplainBench
    tb = TheoremExplainBench()
    console.print(Panel("[bold magenta]TheoremExplainBench (Ku et al., 2025; Code2Video Table 8)[/bold magenta]", expand=False))

    theorems = [t for t in tb.theorems if t.id == id] if id else tb.theorems

    table = Table(title=f"Mathematical Theorems ({len(theorems)} entries)")
    table.add_column("ID", style="dim")
    table.add_column("Theorem Name", style="cyan")
    table.add_column("Domain", style="yellow")
    table.add_column("Duration", justify="right")
    table.add_column("Key Visual Elements", style="green")

    for t in theorems:
        table.add_row(t.id, t.theorem_name, t.domain, f"{t.target_duration_sec}s", ", ".join(t.key_visuals))
    console.print(table)

    # Baselines comparison summary
    console.print("\n")
    b_table = Table(title="TheoremExplainBench Baseline Comparison (Table 8)")
    b_table.add_column("Method", style="cyan")
    b_table.add_column("AD", justify="right")
    b_table.add_column("VR", justify="right")
    b_table.add_column("LF", justify="right")
    b_table.add_column("EL", justify="right")
    b_table.add_column("VC", justify="right")
    b_table.add_column("Overall", justify="right", style="bold green")

    for k, v in tb.BASELINE_RESULTS.items():
        b_table.add_row(
            v["method"],
            f"{v['accuracy_depth']:.2f}",
            f"{v['visual_relevance']:.2f}",
            f"{v['logical_flow']:.2f}",
            f"{v['element_layout']:.2f}",
            f"{v['visual_consistency']:.2f}",
            f"{v['overall']:.2f}"
        )
    console.print(b_table)


@main.command()
@click.option("--image", "-img", default=None, help="Path to image keyframe to audit.")
@click.option("--video", "-v", default=None, help="Path to video file to extract and audit keyframes from.")
def audit(image: Optional[str], video: Optional[str]):
    """Run zero-token static computer vision WCAG contrast and clutter audit."""
    from code2video.vision_auditor import VisionAccessibilityAuditor
    target_img = image

    if video and os.path.exists(video):
        from code2video.multimodal_critic import MultimodalCritic
        critic = MultimodalCritic()
        frames = critic.extract_keyframes(video, "demo_outputs/audit_temp", num_frames=1)
        if frames:
            target_img = frames[0]

    if not target_img or not os.path.exists(target_img):
        console.print("[red]Error: Please specify a valid --image or --video to audit.[/red]")
        return

    console.print(Panel(f"[bold cyan]Vision & WCAG Accessibility Audit[/bold cyan]\nTarget: {target_img}", expand=False))
    res = VisionAccessibilityAuditor.audit_keyframe(target_img)

    wcag = res["wcag_contrast"]
    clutter = res["visual_clutter"]
    contiguity = res["spatial_contiguity"]

    table = Table(title="Computer Vision Accessibility Scorecard")
    table.add_column("Criterion", style="cyan")
    table.add_column("Measurement", style="magenta")
    table.add_column("Compliance / Status", style="green")

    table.add_row("WCAG Contrast Ratio", f"{wcag['contrast_ratio']}:1", f"{wcag['rating']}")
    table.add_row("Visual Clutter Index", f"{clutter['clutter_index']} / 100", f"{clutter['status']}")
    table.add_row("Spatial Contiguity Score", f"{contiguity['spatial_contiguity_score']}%", f"{contiguity['split_attention_level']} Split Attention")
    table.add_row("Overall Accessibility Score", f"[bold green]{res['composite_accessibility_score']} / 100[/bold green]", "Zero-Token Static Vision Pass")

    console.print(table)


@main.command()
@click.option("--topic", "-t", required=True, help="Topic of the lecture.")
@click.option("--video", "-v", default="demo_outputs/complete_lecture.mp4", help="Path to rendered MP4 video.")
@click.option("--output", "-o", default="demo_outputs/interactive_lecture.html", help="Output HTML file path.")
def interactive(topic: str, video: str, output: str):
    """Generate standalone active-recall HTML5 interactive companion player."""
    from code2video.interactive_player import InteractivePlayerGenerator
    from code2video.planner import Code2VideoPlanner
    from code2video.mmmc import MMMCBenchmark

    planner = Code2VideoPlanner()
    outline = planner.generate_outline(topic)
    storyboard = planner.generate_storyboards(outline)

    bench = MMMCBenchmark()
    quizzes = bench.get_teach_quiz(topic) or []

    out = InteractivePlayerGenerator.generate_player_html(
        topic=topic,
        video_filename=os.path.basename(video),
        storyboard=storyboard,
        quiz_items=quizzes,
        output_path=output
    )
    console.print(f"[bold green]✓ Interactive Active-Recall Companion Produced:[/bold green] [cyan]{out}[/cyan]")
    console.print("[dim]Open this HTML file in any browser to experience interactive chapter pauses and real-time concept checks.[/dim]")


@main.command()
@click.option("--concept", "-c", type=click.Choice(["euler", "svm"]), default="euler", help="Mathematical concept playground.")
@click.option("--output", "-o", default="demo_outputs/playground.html", help="Output HTML path.")
def playground(concept: str, output: str):
    """Generate interactive parameter exploration sandbox (Euler Phasor, SVM Margin)."""
    from code2video.math_playground import MathPlaygroundGenerator
    if concept == "euler":
        p = MathPlaygroundGenerator.generate_euler_playground(output)
    else:
        p = MathPlaygroundGenerator.generate_svm_playground(output)
    console.print(f"[bold green]✓ Interactive Parameter Sandbox Exported:[/bold green] [cyan]{p}[/cyan]")


@main.command()
def languages():
    """List supported multi-lingual TTS voice synthesizers and language codes."""
    from code2video.multilingual import MultiLingualEngine
    langs = MultiLingualEngine.get_supported_languages()

    table = Table(title="Supported Multi-Lingual Neural Synthesizers (Dynamic Re-Pacing)")
    table.add_column("Code", style="cyan")
    table.add_column("Language", style="magenta")
    table.add_column("Neural TTS Voice (Edge-TTS)", style="green")

    for l in langs:
        table.add_row(l["code"], l["name"], l["voice"])
    console.print(table)


if __name__ == "__main__":
    main()
