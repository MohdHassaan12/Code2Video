"""Typed stage boundary for the video pipeline.

This documents the pipeline as an explicit, ordered sequence of stages and gives the
scaffold agents a common contract (``PipelineStage.run(ctx) -> ctx``). It is a *seam*,
not a rewrite: the production flow today still calls the stage functions directly
(``generate_storyboard_impl`` -> ``generate_code_impl`` -> ``_run_render_job`` ->
``_repair_overlaps``). The context object below is the shape a future orchestrator would
thread through every stage.

Pipeline stages (● = concrete, ◐ = implemented behind a default-off flag,
△ = external module):

    1. Pedagogy Planner      ● ce/planner_agent.py (PARTS, over HTTP)
    2. Storyboard (DSL)      ● app.storyboard.generate_storyboard_impl + shape/lang gate
    3. Visual Director       ◐ app.pipeline.director.VisualDirectorStage  (VISUAL_DIRECTOR=1)
    4. Layout Engine         △ transpiler.py (zones, c2p, label slots, axes-aware)
    5. Animation Planner     △ transpiler.py (_ENTRANCE_CONFIG, _TIMING, staggering)
    6. Component Retrieval   ● app.rag + △ viz_helpers.py (atoms/molecules/svg)
    7. Codegen / Compiler    ● app.codegen_pipeline.generate_code_impl -> app.render.compile_manim_code
    8. Static Validator      ● app.render dry-run probe (overlap/clip/text-over-shape)
    9. Vision QA             ◐ app.pipeline.vision_qa.VisionQAStage       (VISION_QA=1)
   10. Repair Agent          ● app.render._repair_overlaps / _repair_scenes_parallel
                               + _run_vision_qa (vision findings, accept-if-better)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable


@dataclass
class PipelineContext:
    """Everything the stages read/write as a lesson flows storyboard -> video.

    A stage takes a context, mutates/returns it, and passes it on. Fields are optional
    so a stage only needs to populate what it produces.
    """
    topic: str = ""
    persona: str = "hybrid"
    language: str = "hi-IN"
    style: str = ""
    # Stage outputs, filled in as the pipeline advances:
    storyboard: Optional[dict] = None          # stage 2 (the Scene DSL)
    code: Optional[str] = None                 # stage 7
    scene_scripts: Optional[List[str]] = None  # stage 7 (per-scene parallel scripts)
    scene_class: str = "STEMAnimation"
    video_url: Optional[str] = None            # stage 7 render output
    violations: List[str] = field(default_factory=list)  # stages 8 + 9
    meta: Dict[str, Any] = field(default_factory=dict)   # sidecar / cost / provenance


@runtime_checkable
class PipelineStage(Protocol):
    """A pipeline stage transforms a context in place and returns it.

    Implementations must be **non-fatal**: a stage improves the context or stands aside,
    it never blocks the pipeline (the house rule — a QC gate improves or steps aside,
    and a verified artifact is never lost).
    """

    name: str

    def enabled(self) -> bool:
        """Whether this stage runs (typically an env feature-flag)."""
        ...

    def run(self, ctx: PipelineContext) -> PipelineContext:
        """Transform and return the context. Must not raise on ordinary failure."""
        ...
