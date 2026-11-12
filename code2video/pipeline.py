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
        narrate: bool = False,
        interactive: bool = False,
        audit_vision: bool = False,
        audit_grounding: bool = False,
        enforce_motion_budget: bool = False,
        learner_in_the_loop: bool = False,
        language: str = "en"
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

        # Enforce Dead-Hold Motion Budget (Direction D9+)
        motion_report = None
        if enforce_motion_budget:
            from code2video.motion_budget import MotionBudgetMonitor
            initial_motion = MotionBudgetMonitor.analyze_code_motion(full_script)
            if initial_motion.dead_holds:
                full_script, mods = MotionBudgetMonitor.inject_dynamic_telestration(
                    full_script, initial_motion.dead_holds
                )
            motion_report = MotionBudgetMonitor.analyze_code_motion(full_script).to_dict()

        script_path = os.path.join(self.output_dir, "code2video_lecture.py")
        with open(script_path, "w") as f:
            f.write(full_script)

        # Spoken-to-Visual Grounding Matrix Audit (Direction D9+)
        grounding_report = None
        if audit_grounding:
            from code2video.grounding_matrix import SpokenVisualGroundingMatrix
            # Compile narration lines and cues from storyboard
            all_narration = []
            timeline_cues = []
            accum_t = 0.0
            for sec in storyboard.sections:
                for line in sec.lecture_lines:
                    all_narration.append(line)
                    timeline_cues.append({
                        "phrase": line,
                        "narration": line,
                        "start_sec": accum_t,
                        "duration_sec": 8.0
                    })
                    accum_t += 8.0
            full_narration_text = " ".join(all_narration)
            g_rep = SpokenVisualGroundingMatrix.compute_grounding_matrix(
                topic=topic,
                narration_text=full_narration_text,
                code=full_script,
                timeline=timeline_cues
            )
            grounding_report = g_rep.to_dict()

        # Stage 4: Closed-Loop Learner-in-the-Loop Diagnostic Repair (Direction D2)
        learner_loop_report = None
        if learner_in_the_loop:
            from code2video.learner_loop import ClosedLoopLearnerRepair
            from code2video.grounding_matrix import SpokenVisualGroundingMatrix
            from code2video.motion_budget import MotionBudgetMonitor

            # Compute telemetry for learner diagnosis
            all_narr = " ".join([line for s in storyboard.sections for line in s.lecture_lines])
            g_rep_obj = SpokenVisualGroundingMatrix.compute_grounding_matrix(
                topic=topic,
                narration_text=all_narr,
                code=full_script
            )
            m_rep_obj = MotionBudgetMonitor.analyze_code_motion(full_script)

            section_codes, learner_rep = ClosedLoopLearnerRepair.execute_closed_loop_repair(
                topic=topic,
                storyboard=storyboard,
                section_codes=section_codes,
                grounding_report=g_rep_obj,
                motion_report=m_rep_obj
            )
            # Re-assemble script with surgically remediated sections
            full_script = runner.combine_section_codes(section_codes, topic)
            with open(script_path, "w") as f:
                f.write(full_script)

            tokens_consumed += (len(learner_rep.repaired_sections) * 450)
            learner_loop_report = learner_rep.to_dict()

        # Rendering
        master_video_path = None
        if render:
            stitcher = VideoStitcher(script_path, output_dir=self.output_dir)
            master_video_path, _ = stitcher.render_and_stitch_all(storyboard, narrate=narrate)

        elapsed = time.time() - start_time

        # Interactive Active-Recall Companion Export
        interactive_player_path = None
        if interactive:
            from code2video.interactive_player import InteractivePlayerGenerator
            from code2video.mmmc import MMMCBenchmark
            bench = MMMCBenchmark()
            quizzes = bench.get_teach_quiz(topic) or []
            video_fn = os.path.basename(master_video_path) if master_video_path else "code2video_lecture.mp4"
            interactive_player_path = os.path.join(self.output_dir, "interactive_lecture.html")
            InteractivePlayerGenerator.generate_player_html(
                topic=topic,
                video_filename=video_fn,
                storyboard=storyboard,
                quiz_items=quizzes,
                output_path=interactive_player_path
            )

        # Static Computer Vision & Accessibility Audit
        vision_audit_results = None
        if audit_vision:
            from code2video.vision_auditor import VisionAccessibilityAuditor
            from code2video.multimodal_critic import MultimodalCritic
            critic = MultimodalCritic()
            keyframes = critic.extract_keyframes(master_video_path, self.output_dir, num_frames=2) if (master_video_path and os.path.exists(master_video_path)) else []
            if keyframes:
                vision_audit_results = VisionAccessibilityAuditor.audit_keyframe(keyframes[0])
            else:
                preview_img = os.path.join(self.output_dir, "media", "images", "section_1_sandbox", "section_1_preview.png")
                if os.path.exists(preview_img):
                    vision_audit_results = VisionAccessibilityAuditor.audit_keyframe(preview_img)

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
            "language": language,
            "outline": outline.model_dump(),
            "storyboard": storyboard.model_dump(),
            "assets": assets,
            "script_path": script_path,
            "master_video_path": master_video_path,
            "interactive_player_path": interactive_player_path,
            "vision_audit": vision_audit_results,
            "grounding_audit": grounding_report,
            "motion_budget": motion_report,
            "learner_loop": learner_loop_report,
            "critique_traces": section_critique_traces,
            "tokens_consumed": tokens_consumed,
            "wall_clock_time_sec": round(elapsed, 2),
            "aesthetics": eval_suite["aesthetics"],
            "teach_quiz": eval_suite["teach_quiz"],
            "efficiency": eval_suite["efficiency"],
            "pareto_qcr_score": eval_suite["pareto_qcr_score"]
        }

