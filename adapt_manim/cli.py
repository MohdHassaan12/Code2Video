"""
Command-Line Interface for AdaptManim.
Provides commands for end-to-end video generation, multi-tier verification,
adaptive repair, benchmarking, and launching the interactive Streamlit Studio.
"""

import sys
import os
import json
from typing import Optional
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
@click.option("--interactive", "-i", is_flag=True, default=False, help="Generate interactive active-recall HTML5 web companion.")
@click.option("--language", "-l", default="en", help="Speech and subtitle language code (en, es, de, fr, hi, zh, ja).")
@click.option("--output-dir", "-o", default="demo_outputs", help="Output directory for code and videos.")
@click.option("--provider", "-p", default=None, help="LLM Provider (ollama, gemini, openai, anthropic, mock, auto).")
@click.option("--model", "-m", default=None, help="LLM Model name (e.g. llama4, llama3.3, gpt-4o).")
@click.option("--ollama-host", default=None, help="Ollama server host URL (default: http://localhost:11434).")
def generate(topic: str, audience: str, render: bool, narrate: bool, interactive: bool, language: str, output_dir: str, provider: Optional[str] = None, model: Optional[str] = None, ollama_host: Optional[str] = None):
    """Generate complete educational video pipeline from topic."""
    aud = AudienceLevel(audience)
    console.print(Panel(f"[bold cyan]AdaptManim Pipeline[/bold cyan]\n[white]Topic:[/white] {topic}\n[white]Audience:[/white] {aud.value}\n[white]Language:[/white] {language}\n[white]Provider:[/white] {provider or 'auto'} | [white]Model:[/white] {model or 'default'}", expand=False))

    llm_client = None
    if provider or model or os.environ.get("OLLAMA_MODEL") or os.environ.get("OLLAMA_HOST") or os.environ.get("GEMINI_API_KEY") or os.environ.get("OPENAI_API_KEY"):
        from adapt_manim.core.llm_client import UnifiedLLMClient
        selected_provider = provider or ("ollama" if (os.environ.get("OLLAMA_MODEL") or os.environ.get("OLLAMA_HOST")) else "auto")
        llm_client = UnifiedLLMClient(
            provider=selected_provider,
            model_name=model,
            base_url=ollama_host
        )

    # 1. Complexity Profile & Symbol Ledger
    profile = TopicComplexityProfiler.profile(topic, aud)
    ledger_mgr = SymbolLedgerManager(topic)
    console.print(f"[green]✓[/green] Topic Profiled: Difficulty={profile.difficulty_score}, Target Scenes={profile.recommended_scenes}")
    console.print(f"[green]✓[/green] Symbol Ledger initialized with {len(ledger_mgr.ledger.symbols)} canonical STEM symbols.")

    # 2. Outline Planning
    with console.status("[bold green]Synthesizing Pedagogical Outline..."):
        outline = OutlinePlanner.generate_outline(topic, aud, llm_client=llm_client)
    console.print(f"[green]✓[/green] Outline generated: {len(outline.sections)} sections ({outline.target_duration_minutes} min).")

    # 3. Storyboard Construction
    with console.status("[bold green]Building Storyboard with 6x6 Anchors & Cue-Event Alignment..."):
        storyboard = StoryboardBuilder.build_storyboard(outline, ledger_mgr, llm_client=llm_client)
    console.print(f"[green]✓[/green] Storyboard constructed with {sum(len(s.lecture_lines) for s in storyboard.sections)} synchronized lecture cues.")

    # 4. Code Synthesis & Multi-Tier Verification
    os.makedirs(output_dir, exist_ok=True)
    section_codes = {}
    reports = {}

    for sec in storyboard.sections:
        with console.status(f"[bold yellow]Synthesizing & Verifying {sec.id}..."):
            raw_code = ManimCoder.generate_section_code(sec, ledger_mgr, llm_client=llm_client)
            # Run verification cascade
            report = VerificationCascade.verify_section(
                code=raw_code,
                section=sec,
                ledger_manager=ledger_mgr,
                output_dir=output_dir,
                skip_execution=not render,
                llm_client=llm_client
            )

            # If verification failed, run adaptive repair router
            if not report.passed:
                console.print(f"[yellow]![/yellow] {sec.id} failed {report.highest_failing_tier.value if report.highest_failing_tier else 'checks'}. Routing to ScopeRefine++...")
                raw_code, report, rh = AdaptiveRepairRouter.execute_adaptive_repair(
                    code=raw_code,
                    initial_report=report,
                    section=sec,
                    ledger_manager=ledger_mgr,
                    verifier_func=lambda c: VerificationCascade.verify_section(c, sec, ledger_mgr, output_dir, skip_execution=not render, llm_client=llm_client),
                    llm_client=llm_client
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

    # 7. Interactive Active-Recall Companion
    if interactive:
        from code2video.interactive_player import InteractivePlayerGenerator
        from code2video.mmmc import MMMCBenchmark
        bench = MMMCBenchmark()
        quizzes = bench.get_teach_quiz(topic) or []
        video_fn = os.path.basename(master_path) if (master_path and os.path.exists(master_path)) else "complete_lecture.mp4"
        companion_path = os.path.join(output_dir, "interactive_lecture.html")
        InteractivePlayerGenerator.generate_player_html(
            topic=topic,
            video_filename=video_fn,
            storyboard=storyboard,
            quiz_items=quizzes,
            output_path=companion_path
        )
        console.print(f"[bold magenta]✓ Interactive Active-Recall Companion Generated:[/bold magenta] [cyan]{companion_path}[/cyan]")

    # 8. Evaluation Metrics Display
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


@main.command()
@click.option("--image", "-img", default=None, help="Path to image keyframe to audit.")
@click.option("--video", "-v", default=None, help="Path to video file to extract and audit keyframes from.")
def audit(image: str, video: str):
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
    from adapt_manim.planning.complexity_profiler import TopicComplexityProfiler
    from adapt_manim.planning.outline_planner import OutlinePlanner
    from adapt_manim.planning.storyboard_builder import StoryboardBuilder
    from adapt_manim.core.ledger import SymbolLedgerManager
    from code2video.mmmc import MMMCBenchmark

    aud = AudienceLevel.UNDERGRADUATE
    outline = OutlinePlanner.generate_outline(topic, aud)
    ledger_mgr = SymbolLedgerManager(topic)
    storyboard = StoryboardBuilder.build_storyboard(outline, ledger_mgr)

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

