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
@click.option("--audit-grounding", is_flag=True, default=False, help="Run Spoken-to-Visual Grounding Matrix audit (Direction D9+).")
@click.option("--motion-budget", is_flag=True, default=False, help="Enforce dead-hold motion budget & dynamic telestration.")
@click.option("--language", "-l", default="en", help="Speech and subtitle language code (en, es, de, fr, hi, zh, ja).")
@click.option("--output-dir", "-o", default="demo_outputs/code2video", help="Output directory.")
@click.option("--provider", "-p", default=None, help="LLM Provider (ollama, gemini, openai, anthropic, mock, auto).")
@click.option("--model", "-m", default=None, help="LLM Model name (e.g. llama4, llama3.3, gpt-4o).")
@click.option("--ollama-host", default=None, help="Ollama server host URL (default: http://localhost:11434).")
def generate(topic: str, audience: str, render: bool, narrate: bool, interactive: bool, audit_vision: bool, audit_grounding: bool, motion_budget: bool, language: str, output_dir: str, provider: Optional[str] = None, model: Optional[str] = None, ollama_host: Optional[str] = None):
    """Execute the full 3-stage Code2Video agent pipeline (Planner -> Coder -> Critic)."""
    console.print(Panel(f"[bold cyan]Code2Video Generation Pipeline[/bold cyan]\nTopic: {topic}\nAudience: {audience}\nNarrate: {narrate} | Language: {language} | Interactive: {interactive}\nGrounding: {audit_grounding} | Motion Budget: {motion_budget}\nProvider: {provider or 'auto'} | Model: {model or 'default'}", expand=False))

    llm_client = None
    if provider or model or os.environ.get("OLLAMA_MODEL") or os.environ.get("OLLAMA_HOST") or os.environ.get("GEMINI_API_KEY") or os.environ.get("OPENAI_API_KEY"):
        from adapt_manim.core.llm_client import UnifiedLLMClient
        selected_provider = provider or ("ollama" if (os.environ.get("OLLAMA_MODEL") or os.environ.get("OLLAMA_HOST")) else "auto")
        llm_client = UnifiedLLMClient(
            provider=selected_provider,
            model_name=model,
            base_url=ollama_host
        )

    pipeline = Code2VideoPipeline(llm_client=llm_client, output_dir=output_dir)
    with console.status("[bold green]Executing Planner, Coder (ScopeRefine), and Critic..."):
        res = pipeline.run(
            topic=topic,
            audience=audience,
            render=render,
            narrate=narrate,
            interactive=interactive,
            audit_vision=audit_vision,
            audit_grounding=audit_grounding,
            enforce_motion_budget=motion_budget,
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

    # Spoken-to-Visual Grounding Matrix Output (Direction D9+)
    if res.get("grounding_audit"):
        ga = res["grounding_audit"]
        g_table = Table(title="Spoken-to-Visual Grounding Matrix (Direction D9+)")
        g_table.add_column("Metric", style="cyan")
        g_table.add_column("Value", style="magenta")
        g_table.add_column("Status / Threshold", style="green")
        g_table.add_row("Total Spoken Entities", str(ga.get("total_spoken_entities", 0)), "Variables, formulas, terms")
        g_table.add_row("Grounded Visual Entities", str(ga.get("grounded_count", 0)), "Synchronized in animation")
        g_table.add_row("Ungrounded Spoken Terms", str(ga.get("ungrounded_count", 0)), "Talking-head warnings" if ga.get("ungrounded_count", 0) > 0 else "0 ungrounded")
        g_table.add_row("Grounding Ratio", f"{ga.get('grounding_ratio', 0.0) * 100:.1f}%", "[bold green]PASS (>= 70%)[/bold green]" if ga.get("passed") else "[bold red]FAIL (< 70%)[/bold red]")
        g_table.add_row("Mayer Contiguity Score", f"{ga.get('mayer_contiguity_score', 0.0):.1f} / 100", "Temporal audio-visual alignment")
        console.print(g_table)

    # Dead-Hold Motion Budget Output
    if res.get("motion_budget"):
        mb = res["motion_budget"]
        m_table = Table(title="Dead-Hold Motion Budget & Density (Direction D9+)")
        m_table.add_column("Parameter", style="cyan")
        m_table.add_column("Measurement", style="magenta")
        m_table.add_column("Standard", style="green")
        m_table.add_row("Total Duration", f"{mb.get('total_duration_sec', 0.0):.1f}s", "Rendered timeline")
        m_table.add_row("Active Motion Density", f"{mb.get('active_density_ratio', 0.0) * 100:.1f}%", "[bold green]PASS (>= 70%)[/bold green]" if mb.get("passed") else "[bold yellow]BELOW TARGET (< 70%)[/bold yellow]")
        m_table.add_row("Max Dead Hold Span", f"{mb.get('max_dead_hold_sec', 0.0):.1f}s", "<= 2.5s (Khan Academy target)")
        m_table.add_row("Detected Dead Holds", str(mb.get("dead_holds_count", 0)), "0 static stalls" if mb.get("dead_holds_count", 0) == 0 else f"{mb.get('dead_holds_count')} stalls repaired")
        console.print(m_table)

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
@click.option("--script", "-s", required=True, help="Path to Manim Python script.")
@click.option("--narration", "-n", default=None, help="Spoken narration text or transcript.")
@click.option("--topic", "-t", default="Educational Topic", help="Instructional topic name.")
def grounding(script: str, narration: Optional[str], topic: str):
    """Audit Spoken-to-Visual Grounding Matrix and Mayer Contiguity (Direction D9+)."""
    from code2video.grounding_matrix import SpokenVisualGroundingMatrix

    if not os.path.exists(script):
        console.print(f"[red]Error: script file '{script}' not found.[/red]")
        return

    with open(script, "r") as f:
        code_content = f.read()

    narr_text = narration or "We analyze the function f of x, taking derivative df over dx as limit approaches zero."

    console.print(Panel(f"[bold cyan]Spoken-to-Visual Grounding Audit[/bold cyan]\nScript: {script}\nTopic: {topic}", expand=False))
    rep = SpokenVisualGroundingMatrix.compute_grounding_matrix(
        topic=topic,
        narration_text=narr_text,
        code=code_content
    )

    t = Table(title=f"Grounding Matrix Evaluation: {topic}")
    t.add_column("Spoken Term", style="cyan")
    t.add_column("Category", style="yellow")
    t.add_column("Spoken Sec", justify="right")
    t.add_column("Visual Target", style="magenta")
    t.add_column("Visual Sec", justify="right")
    t.add_column("Drift (s)", justify="right")
    t.add_column("Status", style="green")

    for m in rep.matches[:12]:
        status_color = "green" if m.is_grounded else "red"
        t.add_row(
            m.spoken_entity.term,
            m.spoken_entity.category,
            f"{m.spoken_entity.start_sec:.1f}s",
            m.visual_entity.obj_name if m.visual_entity else "NONE",
            f"{m.visual_entity.animation_timestamp:.1f}s" if m.visual_entity else "N/A",
            f"{m.time_delta_sec:.1f}s" if m.visual_entity else "N/A",
            f"[{status_color}]{m.status}[/{status_color}]"
        )
    console.print(t)

    console.print(f"Grounding Ratio: [bold]{rep.grounding_ratio * 100:.1f}%[/bold] | Mayer Contiguity: [bold]{rep.mayer_contiguity_score:.1f}/100[/bold] | Verdict: {'[bold green]PASSED[/bold green]' if rep.passed else '[bold red]FAILED[/bold red]'}")


@main.command()
@click.option("--script", "-s", required=True, help="Path to Manim Python script.")
@click.option("--inject-fixes", "-i", is_flag=True, default=False, help="Automatically inject dynamic telestrations into dead holds.")
@click.option("--output", "-o", default=None, help="Output path for modified script.")
def motion(script: str, inject_fixes: bool, output: Optional[str]):
    """Analyze and enforce Dead-Hold Motion Budget (Khan Academy standard >= 75%)."""
    from code2video.motion_budget import MotionBudgetMonitor

    if not os.path.exists(script):
        console.print(f"[red]Error: script file '{script}' not found.[/red]")
        return

    with open(script, "r") as f:
        code_content = f.read()

    rep = MotionBudgetMonitor.analyze_code_motion(code_content)
    console.print(Panel(f"[bold cyan]Dead-Hold Motion Budget Audit[/bold cyan]\nScript: {script}\nTotal Duration: {rep.total_duration_sec:.1f}s | Active Density: {rep.active_density_ratio * 100:.1f}%", expand=False))

    if rep.dead_holds:
        t = Table(title=f"Detected Dead Holds ({len(rep.dead_holds)} static spans > 2.5s)")
        t.add_column("Span (sec)", style="cyan")
        t.add_column("Duration", style="magenta")
        t.add_column("Detail", style="yellow")
        for dh in rep.dead_holds:
            t.add_row(f"{dh.start_sec:.1f}s - {dh.end_sec:.1f}s", f"{dh.duration_sec:.1f}s", dh.context)
        console.print(t)
    else:
        console.print("[bold green]✓ No dead holds detected. Visual animation density satisfies pedagogical standard.[/bold green]")

    if inject_fixes and rep.dead_holds:
        enhanced_code, mods = MotionBudgetMonitor.inject_dynamic_telestration(code_content, rep.dead_holds)
        out_path = output or script
        with open(out_path, "w") as f:
            f.write(enhanced_code)
        console.print(f"[bold green]✓ Injected {len(mods)} dynamic telestrations to eliminate dead holds.[/bold green] Saved to: [cyan]{out_path}[/cyan]")


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
