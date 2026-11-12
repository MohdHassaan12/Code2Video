"""Pipeline stage scaffold.

The video pipeline is a sequence of stages (see ``stages.py`` for the full list).
Most already exist as concrete code across the package and in ``transpiler.py`` /
``viz_helpers.py``; the two GENUINELY MISSING agents — the Visual Director and the
Vision-QA reviewer — are scaffolded here as wired stubs (feature-flagged off, no-op)
so that implementing them later is a config flip plus filling in one class, not a graft
into the monolith.

Nothing here is on the default runtime path yet; importing this package has no effect
on behavior.
"""
from .stages import PipelineContext, PipelineStage  # noqa: F401
from .director import VisualDirectorStage  # noqa: F401
from .motion import MotionDirectorStage  # noqa: F401
from .vision_qa import VisionQAStage  # noqa: F401
from .registry import AGENTS, enrich_storyboard  # noqa: F401

__all__ = ["PipelineContext", "PipelineStage", "VisualDirectorStage",
           "MotionDirectorStage", "VisionQAStage", "AGENTS", "enrich_storyboard"]
