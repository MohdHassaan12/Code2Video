"""Visual Director stage (pipeline stage 3): composition decisions as IR annotations.

The storyboard says WHAT to show; the director decides what matters — and expresses
every decision as ordinary Storyboard-IR constructs, so the deterministic transpiler
needs no new vocabulary and a disabled director leaves the board byte-identical
(strip-invariance, reference-architecture.md §6.4):

  - **visual hierarchy** — the LLM ranks each element primary/secondary/tertiary;
    code applies scale tiers (primary x1.2, tertiary x0.8, clamped). Axes/graphs are
    never rescaled: their footprint seeds the layout engine's zone claims.
  - **object lifetime** — the LLM proposes "element E is finished after cue k";
    code appends a standard ``{"action": "hide", "target": E}`` event at cue k,
    but ONLY when that is provably safe (E is alive, nothing references E later,
    no living element is anchored to E). Stale-text clutter is the recurring
    overlap class the repair loop otherwise has to clean up (roadmap §D).
  - **semantic highlighting** — the LLM names the element the narration is about;
    code appends a standard ``highlight`` event (capped: 1/cue, 3/scene).

The LLM never emits geometry, scales, or code — it returns rankings and cue indices
(principle P2); ``_apply_directives`` is pure and deterministic, and rejects every
unsafe or malformed proposal individually (the stage stands aside per proposal, not
just per call). Enable with ``VISUAL_DIRECTOR=1``.
"""
from __future__ import annotations

import copy
import json
import logging
import os

from ..llm import call_llm_with_fallback, loads_json_lenient
from .stages import PipelineContext

logger = logging.getLogger(__name__)

IMPORTANCE_SCALE = {"primary": 1.2, "secondary": 1.0, "tertiary": 0.8}
_SCALE_MIN, _SCALE_MAX = 0.4, 1.15
# Never rescaled: axes are the coordinate frame, an image is a fixed aspect, and a
# simulation was VERIFIED to stay inside a 6x4 box — scaling it up would place geometry
# outside the box the verifier actually checked.
_NO_RESCALE_TYPES = {"coordinate_system", "graph", "image", "simulation"}
_MAX_HIGHLIGHTS_PER_SCENE = 3

# Enlarge-to-fill: the deterministic half of the dead-frame fix. Measured live
# 2026-07-21 — the vision reviewer flagged 6/6 sampled frames as `dead-frame`, and a
# manual frame pull confirmed one small diagram floating in ~85% black. A scene with
# few elements at the 0.7 default fills almost none of a 16:9 frame, so scale it up.
# Conservative on purpose: over-enlarging trades a dead frame for clipped text (the
# probe would then pay for it), so the boost is modest and the ceiling separate.
_SPARSE_MAX_ELEMENTS = 4
_SPARSE_BOOST = 1.3
_SPARSE_SCALE_MAX = 1.4


def _enlarge_sparse_scenes(board):
    """Boost element scales in scenes too sparse to fill the frame. Pure/deterministic.

    Skips scenes containing a coordinate system or graph (an axes footprint already
    fills the stage, and rescaling axes would invalidate the layout engine's zone
    claims). Returns the number of elements rescaled.
    """
    if os.getenv("DIRECTOR_ENLARGE_SPARSE", "1") != "1":
        return 0
    try:
        limit = int(os.getenv("DIRECTOR_SPARSE_MAX_ELEMENTS", str(_SPARSE_MAX_ELEMENTS)))
    except (TypeError, ValueError):
        limit = _SPARSE_MAX_ELEMENTS
    boosted = 0
    for scene in board.get("visual_storyboard", []):
        elements = scene.get("elements", []) or []
        if not elements or len(elements) > limit:
            continue
        if any(el.get("type") in _NO_RESCALE_TYPES for el in elements):
            continue
        for el in elements:
            if el.get("type") in _NO_RESCALE_TYPES:
                continue
            base = el.get("scale") or 0.7
            new = round(min(_SPARSE_SCALE_MAX, base * _SPARSE_BOOST), 3)
            if new > base:
                el["scale"] = new
                boosted += 1
    return boosted

_SYSTEM = (
    "You are the Visual Director for an educational STEM animation. You do NOT write "
    "code or choose positions — you make composition calls on the storyboard you are "
    "given.\nFor each scene decide:\n"
    "1. importance: rank each element id primary (THE thing this scene teaches — "
    "usually exactly one), secondary (supports it), or tertiary (context/decoration).\n"
    "2. hide_after: for each element that is FINISHED before the scene ends (the "
    "narration has moved on), the 0-based cue index after which it should fade out. "
    "Only propose this when keeping it on screen would clutter later cues.\n"
    "3. highlight: at most one element per cue that the narration is naming RIGHT "
    "THEN and that deserves a flash of emphasis. Use sparingly.\n"
    "4. focus: AT MOST ONE per scene — the single beat carrying the scene's key idea. "
    "Everything else dims while that element holds the screen. Omit it entirely for "
    "scenes with no such moment; a spotlight on every scene is worth nothing.\n"
    "Return ONLY a JSON object (no markdown, no prose):\n"
    '{"scenes": [{"scene_index": <int>, "importance": {"<el_id>": "primary|secondary|'
    'tertiary"}, "hide_after": {"<el_id>": <cue_index>}, '
    '"highlight": [{"cue": <cue_index>, "target": "<el_id>"}], '
    '"focus": {"cue": <cue_index>, "target": "<el_id>"}}]}'
)


def _scene_digest(scene):
    """Compact, cheap description of one scene for the director call."""
    els = []
    for el in scene.get("elements", []):
        d = {"id": el.get("id"), "type": el.get("type"),
             "content": str(el.get("content", ""))[:60]}
        rel = el.get("relative_positioning") or {}
        if rel.get("relative_to"):
            d["anchored_to"] = rel["relative_to"]
        els.append(d)
    cues = []
    for i, cue in enumerate(scene.get("narration_cues", [])):
        events = cue.get("animation_events") or []
        cues.append({
            "cue": i, "text": str(cue.get("cue", ""))[:80],
            "shows": [e.get("target") for e in events if e.get("action") == "show"],
            "hides": [e.get("target") for e in events if e.get("action") == "hide"],
        })
    return {"scene_index": scene.get("scene_index"), "elements": els, "cues": cues}


def _element_lifetimes(scene):
    """(birth, death) cue index per element id from the EXISTING events.

    birth = first `show` (None = on stage from the start); death = first `hide` of
    the element or `transform` FROM it (None = alive to scene end).
    """
    birth, death = {}, {}
    for i, cue in enumerate(scene.get("narration_cues", [])):
        for ev in (cue.get("animation_events") or []):
            act, tgt = ev.get("action"), ev.get("target")
            if act == "show" and tgt not in birth:
                birth[tgt] = i
            elif act in ("hide", "transform") and tgt not in death:
                death[tgt] = i
    return birth, death


def _last_reference(scene):
    """Last cue index that references each element (as target or `to`)."""
    last = {}
    for i, cue in enumerate(scene.get("narration_cues", [])):
        for ev in (cue.get("animation_events") or []):
            for ref in (ev.get("target"), ev.get("to")):
                if ref:
                    last[ref] = i
    return last


def _apply_directives(storyboard, directives):
    """Deterministically apply director directives to a deep copy of the board.

    Every proposal is validated individually; unsafe/malformed ones are dropped
    (counted in stats). Returns (annotated_board, stats). Pure: no LLM, no I/O.
    """
    board = copy.deepcopy(storyboard)
    stats = {"rescaled": 0, "hides": 0, "highlights": 0, "focus": 0, "rejected": 0}
    by_index = {s.get("scene_index"): s for s in board.get("visual_storyboard", [])}

    for d in directives.get("scenes", []):
        if not isinstance(d, dict):
            stats["rejected"] += 1
            continue
        scene = by_index.get(d.get("scene_index"))
        if scene is None:
            stats["rejected"] += 1
            continue
        elements = {el.get("id"): el for el in scene.get("elements", [])}
        cues = scene.get("narration_cues", [])
        birth, death = _element_lifetimes(scene)
        accepted_death = dict(death)   # grows as hide proposals are accepted below
        last_ref = _last_reference(scene)
        anchors = {}  # anchor id -> ids anchored to it
        for el in scene.get("elements", []):
            rel = (el.get("relative_positioning") or {}).get("relative_to")
            if rel:
                anchors.setdefault(rel, []).append(el.get("id"))

        # 1. Hierarchy -> scale tiers (never axes/graphs: they seed zone claims).
        imp = d.get("importance") or {}
        if isinstance(imp, dict):
            for el_id, rank in imp.items():
                el = elements.get(el_id)
                if el is None or rank not in IMPORTANCE_SCALE or \
                        el.get("type") in _NO_RESCALE_TYPES:
                    stats["rejected"] += 1
                    continue
                base = el.get("scale") or 0.7
                el["scale"] = round(
                    min(_SCALE_MAX, max(_SCALE_MIN, base * IMPORTANCE_SCALE[rank])), 3)
                stats["rescaled"] += 1

        # 2. Lifetime -> appended standard `hide` events, safety-checked.
        proposals = d.get("hide_after") or {}
        if isinstance(proposals, dict):
            for el_id, k in sorted(proposals.items(),
                                   key=lambda kv: kv[1] if isinstance(kv[1], int) else 1 << 30):
                ok = (
                    isinstance(k, int)
                    and el_id in elements
                    and el_id not in accepted_death              # not already removed
                    and 0 <= k < len(cues) - 1                   # never the final cue
                    and k > birth.get(el_id, -1)                 # after it appeared
                    and last_ref.get(el_id, -1) <= k             # nothing needs it later
                    # every element anchored to it is already gone by cue k
                    and all(accepted_death.get(dep, 1 << 30) <= k
                            for dep in anchors.get(el_id, []))
                )
                if not ok:
                    stats["rejected"] += 1
                    continue
                cue = cues[k]
                if not isinstance(cue.get("animation_events"), list):
                    cue["animation_events"] = []   # schema default is None, not []
                cue["animation_events"].append({"action": "hide", "target": el_id})
                accepted_death[el_id] = k
                stats["hides"] += 1

        # 3. Semantic highlighting -> appended standard `highlight` events, capped.
        hl_count = 0
        hl = d.get("highlight") or []
        if isinstance(hl, list):
            for item in hl:
                if hl_count >= _MAX_HIGHLIGHTS_PER_SCENE:
                    stats["rejected"] += 1
                    continue
                k = item.get("cue") if isinstance(item, dict) else None
                el_id = item.get("target") if isinstance(item, dict) else None
                cue = cues[k] if isinstance(k, int) and 0 <= k < len(cues) else None
                events = (cue.get("animation_events") or []) if cue else []
                ok = (
                    cue is not None and el_id in elements
                    # element is on stage at cue k (born, not yet dead — including
                    # deaths accepted from this same directive pass)
                    and birth.get(el_id, 0) <= k
                    and not (el_id in accepted_death and accepted_death[el_id] <= k)
                    # one highlight per cue, no duplicates
                    and not any(e.get("action") == "highlight" for e in events)
                )
                if not ok:
                    stats["rejected"] += 1
                    continue
                if not isinstance(cue.get("animation_events"), list):
                    cue["animation_events"] = []
                cue["animation_events"].append({"action": "highlight", "target": el_id})
                hl_count += 1
                stats["highlights"] += 1

        # 4. Camera language -> ONE semantic spotlight per scene (opacity only; see
        # viz_helpers.spotlight_on for why camera moves are deliberately excluded).
        focus = d.get("focus")
        if isinstance(focus, dict):
            k = focus.get("cue")
            el_id = focus.get("target")
            cue = cues[k] if isinstance(k, int) and 0 <= k < len(cues) else None
            events = (cue.get("animation_events") or []) if cue else []
            ok = (
                cue is not None and el_id in elements
                and birth.get(el_id, 0) <= k
                and not (el_id in accepted_death and accepted_death[el_id] <= k)
                # a spotlight competes with a flash on the same beat, and with itself
                and not any(e.get("action") in ("focus", "highlight") for e in events)
            )
            if ok:
                if not isinstance(cue.get("animation_events"), list):
                    cue["animation_events"] = []
                cue["animation_events"].append({"action": "focus", "target": el_id})
                stats["focus"] += 1
            else:
                stats["rejected"] += 1
    return board, stats


class VisualDirectorStage:
    """LLM ranks and schedules; code applies. Stands aside on any failure."""

    name = "visual_director"

    def enabled(self) -> bool:
        return os.getenv("VISUAL_DIRECTOR", "0") == "1"

    def direct(self, storyboard, client=None, keys=None):
        """Return an annotated deep copy of the storyboard.

        Two halves with different failure semantics:
          * **deterministic** (enlarge-to-fill) — pure code, cannot fail, so it applies
            even when the model is unreachable. This is why a provider outage still
            gets you the free half of the dead-frame fix.
          * **LLM directives** (hierarchy / lifetime / highlighting) — best effort; on
            any failure the stage stands aside and returns the board with only the
            deterministic half applied.
        The input object is never mutated. Flag off ⇒ pure pass-through.
        """
        if not self.enabled():
            return storyboard
        board = copy.deepcopy(storyboard)
        boosted = _enlarge_sparse_scenes(board)
        if boosted:
            logger.info("[DIRECTOR] enlarge-to-fill: scaled %d element(s) in sparse scene(s).",
                        boosted)
        try:
            digest = [_scene_digest(s) for s in board.get("visual_storyboard", [])]
            if not digest:
                return board
            response = call_llm_with_fallback(
                client,
                prompt="Storyboard digest:\n" + json.dumps(digest, ensure_ascii=False),
                system_instruction=_SYSTEM,
                temperature=0.2,
                task="storyboard",
                keys=keys,
            )
            directives = loads_json_lenient(response.text)
            if not isinstance(directives, dict) or \
                    not isinstance(directives.get("scenes"), list):
                logger.warning("[DIRECTOR] malformed directives; passing storyboard through.")
                return board
            directed, stats = _apply_directives(board, directives)
            logger.info("[DIRECTOR] applied: %d rescaled, %d hides, %d highlights, "
                        "%d focus (%d proposals rejected).", stats["rescaled"],
                        stats["hides"], stats["highlights"], stats["focus"],
                        stats["rejected"])
            return directed
        except Exception as e:
            logger.warning("[DIRECTOR] stood aside (%s).", e)
            return board

    def run(self, ctx: PipelineContext) -> PipelineContext:
        if ctx.storyboard:
            ctx.storyboard = self.direct(ctx.storyboard)
        return ctx
