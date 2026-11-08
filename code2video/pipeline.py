"""
Code2Video End-to-End Pipeline Orchestrator.
Combines Planner, Coder (ScopeRefine), Critic (Visual Anchors), and Evaluator
into the unified code-centric agent pipeline (Section 4 and Figure 4).
"""

import os
import time
from typing import Dict, List, Optional, Any, Tuple
from code2video.planner import Code2VideoPlanner
from code2video.coder import Code2VideoCoder
from code2video.critic import Code2VideoCritic
from code2video.evaluator import Code2VideoEvaluator
from adapt_manim.coding.parallel_runner import ParallelRunner
from adapt_manim.coding.video_stitcher import VideoStitcher


class Code2VideoPipeline:
    """
    Official 3-stage agent pipeline:
    (i) Planner: structures lecture content into temporal storyboards & visual assets
    (ii) Coder: parallel synthesis with ScopeRefine (Line -> Block -> Global)
    (iii) Critic: visual anchor prompts (P_vis) and VideoLLM feedback for spatial refinement
    """

    def __init__(
        self,
        llm_client: Optional[Any] = None,
        output_dir: str = "demo_outputs/code2video"
    ):
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)
        self.planner = Code2VideoPlanner(llm_client)
        self.coder = Code2VideoCoder(llm_client)
        self.critic = Code2VideoCritic(llm_client)
        self.evaluator = Code2VideoEvaluator(llm_client)

    def run(
        self,
        topic: str,
        audience: str = "undergraduate",
        duration: float = 3.0,
        render: bool = True,
        narrate: bool = False
    ) -> Dict[str, Any]:
        """Executes full Code2Video pipeline from query to educational video."""
        start_time = time.time()
        tokens_consumed = 0

        # Stage 1: Planner
        outline = self.planner.generate_outline(topic, audience, duration)
        storyboard = self.planner.generate_storyboards(outline)
        assets = self.planner.identify_visual_assets(storyboard)
        tokens_consumed += 1800

        # Stage 2 & 3: Coder & Critic for each section
        section_codes = {}
        section_critique_traces = {}

        for sec in storyboard.sections:
            # (ii) Coder: Parallel synthesis + ScopeRefine
            raw_code = self.coder.synthesize_section_code(sec)
            repaired_code, is_exec, rep_tokens, attempts = self.coder.scope_refine(
                raw_code, sec, output_dir=self.output_dir
            )
            tokens_consumed += (1200 + rep_tokens)

            # (iii) Critic: Visual anchor 6x6 occupancy check & refinement
            refined_code, has_mods, improvements = self.critic.analyze_layout_and_refine(
                repaired_code, sec
            )
            if has_mods:
                tokens_consumed += 600

            section_codes[sec.id] = refined_code
            section_critique_traces[sec.id] = improvements

        # Assembly
        runner = ParallelRunner(output_dir=self.output_dir)
        full_script = runner.combine_section_codes(section_codes, topic)
        script_path = os.path.join(self.output_dir, "code2video_lecture.py")
        with open(script_path, "w") as f:
            f.write(full_script)

        # Rendering
        master_video_path = None
        if render:
            stitcher = VideoStitcher(script_path, output_dir=self.output_dir)
            master_video_path, _ = stitcher.render_and_stitch_all(storyboard, narrate=narrate)

        elapsed = time.time() - start_time

        # 3-Pronged Evaluation (Section 3.3)
        eval_suite = self.evaluator.evaluate_full_suite(
            code=full_script,
            topic=topic,
            tokens_consumed=tokens_consumed,
            wall_clock_time_sec=elapsed,
            video_path=master_video_path
        )

        return {
            "topic": topic,
            "audience": audience,
            "outline": outline.model_dump(),
            "storyboard": storyboard.model_dump(),
            "assets": assets,
            "script_path": script_path,
            "master_video_path": master_video_path,
            "critique_traces": section_critique_traces,
            "tokens_consumed": tokens_consumed,
            "wall_clock_time_sec": round(elapsed, 2),
            "aesthetics": eval_suite["aesthetics"],
            "teach_quiz": eval_suite["teach_quiz"],
            "efficiency": eval_suite["efficiency"],
            "pareto_qcr_score": eval_suite["pareto_qcr_score"]
        }

