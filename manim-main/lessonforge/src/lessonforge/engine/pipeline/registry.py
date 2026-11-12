"""The IR-enrichment agent registry — one board, many specialist agents.

This is the "delegate to separate agents and stitch the result" architecture, built
the way this repo has already learned it must be built:

* **Every agent edits the same IR, never its own slice of video.** Splitting the
  *output* (one agent renders the dynamics, another renders the diagrams, a third
  concatenates) sounds modular but puts the seams in the artifact, where they cost
  the most: mismatched styling, duplicated elements, and a stitcher that can only
  cut, never reconcile. Splitting the *input* keeps one deterministic renderer —
  the transpiler is still the sole full-scene codegen path, so the "stitching" is
  code that cannot disagree with itself.
* **Agents propose; code disposes.** Each agent returns an enriched board and every
  edit it proposes is validated deterministically by the agent's own apply step (see
  `motion.apply_motions`, `director._apply_directives`). An agent can only ever
  produce IR the transpiler already knows how to render.
* **An agent improves the board or stands aside.** A failing agent is isolated here:
  the board it was given passes through untouched, the rest of the chain still runs,
  and the failure is logged and recorded. No single agent can take the render down.

Adding an agent is: write a class with `name`, `enabled()` and
`enrich(board, client, keys)`, add it to `AGENTS` in the order it should run.

Order matters and is explicit:
  1. `visual_director`  — hierarchy, scale, lifetimes, focus  (what is on screen, how big)
  2. `motion_director`  — movement and transformation         (what moves, and when)
Later agents see what earlier ones did, so motion is planned against the final
composition rather than the raw board.
"""
from __future__ import annotations

import copy
import time
import logging

from .director import VisualDirectorStage
from .motion import MotionDirectorStage

logger = logging.getLogger(__name__)


class _DirectorAdapter:
    """The Visual Director predates the registry and exposes `direct()`."""

    name = "visual_director"

    def __init__(self):
        self._stage = VisualDirectorStage()

    def enabled(self):
        return self._stage.enabled()

    def enrich(self, board, client=None, keys=None):
        return self._stage.direct(board, client=client, keys=keys)


# Declaration order == execution order.
AGENTS = [
    _DirectorAdapter(),
    MotionDirectorStage(),
]


def _event_count(board):
    """Total animation events on a board — the cheap 'did anything change' metric."""
    return sum(
        len(cue.get("animation_events") or [])
        for scene in (board.get("visual_storyboard") or [])
        for cue in (scene.get("narration_cues") or [])
    )


def enrich_storyboard(storyboard, client=None, keys=None, agents=None):
    """Run every enabled agent over the board, in order. Never raises.

    Returns the enriched board. A provenance trail is attached as
    `board["agent_trace"]` — per agent: whether it ran, how long it took, and how
    many animation events existed afterwards. Long runs must show progress, and a
    pipeline of agents that reports nothing is impossible to debug or to grade.
    """
    board = storyboard
    trace = []
    for agent in (agents if agents is not None else AGENTS):
        name = getattr(agent, "name", agent.__class__.__name__)
        try:
            if not agent.enabled():
                trace.append({"agent": name, "ran": False, "reason": "disabled"})
                continue
            before = _event_count(board)
            t0 = time.time()
            result = agent.enrich(board, client=client, keys=keys)
            elapsed = round(time.time() - t0, 1)
            if not isinstance(result, dict) or not result.get("visual_storyboard"):
                # A stage that returns something unusable is a stage that stood aside.
                logger.warning("[AGENTS] %s returned an unusable board; keeping the previous one.",
                               name)
                trace.append({"agent": name, "ran": True, "seconds": elapsed,
                              "error": "unusable board"})
                continue
            after = _event_count(result)
            board = result
            logger.info("[AGENTS] %s ran in %ss (animation events %d -> %d).",
                        name, elapsed, before, after)
            trace.append({"agent": name, "ran": True, "seconds": elapsed,
                          "events_before": before, "events_after": after})
        except Exception as e:
            # Isolation is the point of the registry: one agent's bad day is not
            # the render's bad day.
            logger.warning("[AGENTS] %s failed (%s); board passed through unchanged.", name, e)
            trace.append({"agent": name, "ran": True, "error": str(e)[:200]})

    if isinstance(board, dict):
        if board is storyboard:
            board = copy.deepcopy(storyboard)
        board["agent_trace"] = trace
    return board
