"""Motion Director — the agent that makes things MOVE.

The gap it fills, measured 2026-08-14 across three live storyboards: the model wrote
**92 `show`, 42 `hide`, 6 `highlight` and ZERO `transform`/`move_to`/`focus`**. Half
the event vocabulary the transpiler already renders was dead in production, so every
video was things appearing, sitting still, and disappearing. `viz_helpers.sustain`
(same day) fills dead air with gestures, but gesturing at a thing is not the thing
moving — "the video is not animated" was still true afterwards, and correctly so.

Same contract as the Visual Director, because it is the contract that works here:
**the LLM proposes, code disposes.** The agent only ever returns directives naming
existing elements and cues; every one is validated against the scene's own structure
and either applied deterministically or dropped. Nothing it can say can produce code
the transpiler wouldn't have produced itself.

The vocabulary is deliberately limited to what the transpiler ALREADY emits —
`move_to` (next_to another element in a direction), `transform` (one element becomes
another), `focus` (semantic spotlight), `highlight` (Indicate). Inventing IR the
transpiler can't render would just move the failure downstream.

Safety gates (each one is a real way to break a scene):
  * a target must EXIST in this scene — a per-scene render has only its own elements;
  * it must be BORN by that cue and not yet dead — moving something not on screen
    crashes, moving something faded out animates a ghost;
  * an EDGE (`connects`) and an `inside` child are never moved — they derive their
    geometry from other mobjects, so a position of their own tears them off (the
    structural-IR rule this repo already learned the hard way);
  * axes/graphs are never moved — they are the coordinate frame everything else is
    placed against (`c2p`);
  * caps per cue and per scene, so a scene doesn't turn into a slot machine.
"""
from __future__ import annotations

import os
import copy
import json
import logging

from ..llm import call_llm_with_fallback, loads_json_lenient
from .stages import PipelineContext

logger = logging.getLogger(__name__)

# The transpiler's own move_to vocabulary (transpiler emits `.next_to(to, DIR)`).
_DIRECTIONS = {"RIGHT", "LEFT", "UP", "DOWN",
               "UP+RIGHT", "UP+LEFT", "DOWN+RIGHT", "DOWN+LEFT"}

# Never moved: axes/graphs are the frame other elements are positioned against, and a
# simulation carries its own verified motion inside a box it must not leave.
_STATIC_TYPES = {"coordinate_system", "graph", "simulation"}

MAX_PER_CUE = int(os.getenv("MOTION_MAX_PER_CUE", "2"))
MAX_PER_SCENE = int(os.getenv("MOTION_MAX_PER_SCENE", "4"))


_SYSTEM = (
    "You are the motion director for an educational animation. The scenes below "
    "already have their elements and their narration; what they lack is MOVEMENT — "
    "right now things appear, sit still, and vanish.\n\n"
    "For each scene, propose motion that CARRIES MEANING: a force arrow sliding to "
    "the object it acts on, a formula becoming its simplified form, a label moving to "
    "the part it names, a spotlight on the thing being explained at that moment. "
    "Motion that merely decorates is worse than none.\n\n"
    "Rules:\n"
    "- Only these actions: move_to (element moves next to another element), transform "
    "(element BECOMES another element), focus (spotlight one element), highlight.\n"
    "- Only reference element ids and cue indices given to you, in the SAME scene.\n"
    "- An element can only move in a cue at or after the cue that shows it.\n"
    "- move_to needs `to` (the element to move beside) and `direction` "
    "(RIGHT/LEFT/UP/DOWN/UP+RIGHT/UP+LEFT/DOWN+RIGHT/DOWN+LEFT).\n"
    "- transform needs `to` — the element it turns into. Use it for a formula or "
    "diagram becoming its next form; the original is consumed.\n"
    "- Never move a coordinate system or graph; never move an element that is drawn "
    "between two others (an arrow/line connecting them) or one placed inside another.\n"
    f"- At most {MAX_PER_CUE} motions per cue and {MAX_PER_SCENE} per scene. Fewer, "
    "meaningful ones beat many.\n\n"
    'Reply with JSON ONLY: {"scenes": [{"scene_index": <int>, "motions": '
    '[{"cue": <int>, "action": "move_to|transform|focus|highlight", '
    '"target": "<el_id>", "to": "<el_id>", "direction": "RIGHT"}]}]}'
)


def _scene_digest(scene):
    """What the motion agent needs to see: what exists, when it appears, what is said."""
    els = []
    for el in scene.get("elements", []) or []:
        d = {"id": el.get("id"), "type": el.get("type"),
             "content": str(el.get("content", ""))[:60]}
        if _is_edge(el):
            d["is_edge"] = True
        rel = el.get("relative_positioning") or {}
        if isinstance(rel, dict) and rel.get("relation") == "inside":
            d["inside"] = rel.get("relative_to")
        els.append(d)
    cues = []
    for i, cue in enumerate(scene.get("narration_cues", []) or []):
        events = cue.get("animation_events") or []
        cues.append({
            "cue": i,
            "text": str(cue.get("cue", ""))[:100],
            "shows": [e.get("target") for e in events if e.get("action") == "show"],
            "already_moving": [e.get("action") for e in events
                               if e.get("action") in ("move_to", "transform", "focus")],
        })
    return {"scene_index": scene.get("scene_index"), "elements": els, "cues": cues}


def _is_edge(el):
    """True for an element whose geometry comes from the two things it connects."""
    conn = el.get("connects")
    return isinstance(conn, (list, tuple)) and len(conn) >= 2


def _is_contained(el):
    rel = el.get("relative_positioning") or {}
    return isinstance(rel, dict) and rel.get("relation") == "inside"


def _lifetimes(scene):
    """(birth, death) cue index per element id, from the events already present."""
    birth, death = {}, {}
    for i, cue in enumerate(scene.get("narration_cues", []) or []):
        for ev in (cue.get("animation_events") or []):
            act, tgt = ev.get("action"), ev.get("target")
            if act == "show" and tgt not in birth:
                birth[tgt] = i
            elif act in ("hide", "transform") and tgt not in death:
                death[tgt] = i
    return birth, death


def apply_motions(storyboard, directives):
    """Apply motion directives to a deep copy of the board. Pure: no LLM, no I/O.

    Returns (board, stats). Every proposal is validated on its own; anything unsafe
    or malformed is dropped and counted, so a bad response degrades to "no motion
    added" rather than to a broken scene.
    """
    board = copy.deepcopy(storyboard)
    stats = {"move_to": 0, "transform": 0, "focus": 0, "highlight": 0, "rejected": 0}
    by_index = {s.get("scene_index"): s for s in board.get("visual_storyboard", []) or []}

    for entry in (directives.get("scenes") or []):
        if not isinstance(entry, dict):
            stats["rejected"] += 1
            continue
        scene = by_index.get(entry.get("scene_index"))
        if scene is None:
            stats["rejected"] += 1
            continue

        elements = {el.get("id"): el for el in (scene.get("elements") or []) if el.get("id")}
        cues = scene.get("narration_cues") or []
        birth, death = _lifetimes(scene)
        shown_ids = set(birth)
        per_cue = {}
        scene_total = 0

        for m in (entry.get("motions") or []):
            if not isinstance(m, dict):
                stats["rejected"] += 1
                continue
            action = str(m.get("action") or "").strip()
            target = str(m.get("target") or "").strip()
            to_id = str(m.get("to") or "").strip()

            try:
                cue_idx = int(m.get("cue"))
            except (TypeError, ValueError):
                stats["rejected"] += 1
                continue

            def _reject(why):
                logger.debug("[MOTION] rejected %s(%s) in scene %s cue %s: %s",
                             action, target, entry.get("scene_index"), cue_idx, why)
                stats["rejected"] += 1

            if action not in ("move_to", "transform", "focus", "highlight"):
                _reject("unknown action"); continue
            if not (0 <= cue_idx < len(cues)):
                _reject("cue out of range"); continue
            if scene_total >= MAX_PER_SCENE or per_cue.get(cue_idx, 0) >= MAX_PER_CUE:
                _reject("cap reached"); continue

            el = elements.get(target)
            if el is None:
                _reject("target not in this scene"); continue
            # Born yet? An element with no `show` event is on stage from the start.
            if target in birth and cue_idx < birth[target]:
                _reject("moves before it appears"); continue
            if target in death and cue_idx >= death[target]:
                _reject("moves after it is gone"); continue

            if action in ("move_to", "transform"):
                if el.get("type") in _STATIC_TYPES:
                    _reject("axes/graph are the coordinate frame"); continue
                if _is_edge(el):
                    _reject("an edge derives its geometry from its endpoints"); continue
                if _is_contained(el):
                    _reject("a contained child is placed by its container"); continue
                dest = elements.get(to_id)
                if dest is None or to_id == target:
                    _reject("`to` missing or self-referential"); continue
                if to_id in birth and cue_idx < birth[to_id]:
                    _reject("`to` has not appeared yet"); continue

            cue = cues[cue_idx]
            events = cue.setdefault("animation_events", []) or []
            cue["animation_events"] = events
            if any(e.get("action") == action and e.get("target") == target for e in events):
                _reject("duplicate of an existing event"); continue

            event = {"action": action, "target": target}
            if action == "move_to":
                direction = str(m.get("direction") or "RIGHT").strip().upper()
                if direction not in _DIRECTIONS:
                    direction = "RIGHT"
                event["to"] = to_id
                event["direction"] = direction
            elif action == "transform":
                event["to"] = to_id
                # The original is consumed and the destination is now on stage —
                # record both so later proposals see the real lifetimes.
                death.setdefault(target, cue_idx)
                birth.setdefault(to_id, cue_idx)
            elif action == "highlight" and m.get("color"):
                event["color"] = str(m["color"])

            events.append(event)
            per_cue[cue_idx] = per_cue.get(cue_idx, 0) + 1
            scene_total += 1
            stats[action] += 1
            shown_ids.add(target)

    return board, stats


class MotionDirectorStage:
    """Authors real movement into the IR. Proposes with an LLM, applies with code."""

    name = "motion_director"

    def enabled(self) -> bool:
        # ON by default, unlike the Visual Director: a video with no motion was the
        # reported defect, not an enhancement. MOTION_DIRECTOR=0 turns it off.
        return os.getenv("MOTION_DIRECTOR", "1") == "1"

    def enrich(self, storyboard, client=None, keys=None):
        """Return an annotated deep copy; stand aside (unchanged board) on any failure."""
        if not self.enabled():
            return storyboard
        board = copy.deepcopy(storyboard)
        try:
            digest = [_scene_digest(s) for s in board.get("visual_storyboard", []) or []]
            if not digest:
                return board
            response = call_llm_with_fallback(
                client,
                prompt="Scenes:\n" + json.dumps(digest, ensure_ascii=False),
                system_instruction=_SYSTEM,
                temperature=0.3,
                task="storyboard",
                keys=keys,
            )
            directives = loads_json_lenient(response.text)
            if not isinstance(directives, dict) or not isinstance(directives.get("scenes"), list):
                logger.warning("[MOTION] malformed directives; board passed through.")
                return board
            moved, stats = apply_motions(board, directives)
            added = stats["move_to"] + stats["transform"] + stats["focus"] + stats["highlight"]
            logger.info("[MOTION] added %d motion event(s): %d move_to, %d transform, "
                        "%d focus, %d highlight (%d proposals rejected).",
                        added, stats["move_to"], stats["transform"], stats["focus"],
                        stats["highlight"], stats["rejected"])
            return moved
        except Exception as e:
            logger.warning("[MOTION] stood aside (%s).", e)
            return board

    def run(self, ctx: PipelineContext) -> PipelineContext:
        if ctx.storyboard:
            ctx.storyboard = self.enrich(ctx.storyboard)
        return ctx
