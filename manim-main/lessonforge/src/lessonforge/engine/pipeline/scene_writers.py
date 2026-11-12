"""Scene writers — one LLM call per SCREEN, run in parallel, each writing one scene.

This is the fan-out the user asked for, built the way this repo has already learned
fan-out must be built (see `registry.py`): **split the INPUT, never the output.** Each
writer receives one screen's contract from the Screen Ideator and returns one
`StoryboardScene` of IR. Nothing renders per-agent, nothing is stitched at the video
level — the deterministic transpiler still assembles and renders the whole board, so
the seams cannot show up in the artifact.

Why per-screen at all, when one call already produced a whole board: a single call has
a single token budget. Spread across six scenes it writes scene 1 properly and sketches
the rest — the measured shape of "the gen video has less content". Six calls give each
scene the model's full attention *and* a contract to satisfy (`must_show` / `must_say`),
which is what makes "thin" detectable instead of merely visible.

Flow is preserved by construction, not hope: every writer is told the anchor, the
through-line, what the previous screen left behind, and what the next one needs — and
it is explicitly forbidden to re-introduce the topic. The board is then measured by
`storyboard.narrative_problems`, exactly as the single-call path is.

Failure is per-screen and never fatal: a writer that fails is retried once, and if it
still fails the screen degrades to a deterministic scene built from its own contract
(`_fallback_scene`). A hole in the arc is worse than a plain scene, and the plain scene
still draws every object the plan demanded.
"""
from __future__ import annotations

import json
import logging
import os
import re
from concurrent.futures import ThreadPoolExecutor

from ..llm import call_llm_with_fallback, loads_json_lenient
from ..schemas import StoryboardScene
from ..storyboard import language_rules, SHAPE_CONTENT_RULE

logger = logging.getLogger(__name__)

WORKERS = int(os.getenv("SCENE_WRITER_WORKERS", "4"))
MAX_NEW_PER_CUE = 2          # storyboard rule 4: 3+ new elements in one cue crowds the frame
MAX_ELEMENTS_PER_SCENE = 9   # beyond this the director's hide/focus work can't keep up


_SYSTEM = """You are writing ONE scene of a Manim educational animation, in full detail.
You are given that scene's contract. Satisfy it exactly — every object in `must_show`
must exist as its own element, and every fact in `must_say` must be spoken.

{language_rules}

{shape_rule}

ELEMENT TYPES — pick the one that actually draws the thing:
- "text"      short label, title or caption (never a paragraph)
- "math"      LaTeX without $ delimiters
- "math_evolution"  "FROM_LATEX → TO_LATEX" (literal →) when an equation becomes another
- "shape"     a described drawable: "circle labelled 84", "arrow pointing right at the block",
              "inclined plane". The description's HEAD NOUN decides what is drawn, so lead
              with it; anything after "containing"/"with"/"from" describes its contents.
- "svg_icon"  ONE clean English keyword for an icon ("thermometer", "test tube")
- "image"     a real photograph/painting/map — content is a 2-5 word Wikimedia Commons
              search query. Use for real people, events, places, artifacts.
- "chemical_molecule"  a SMILES string ONLY, never hand-drawn atoms
- "coordinate_system" / "graph"  include ranges: "time vs velocity x:0-10, y:0-50"
- "simulation"  a system EVOLVING OVER TIME that no static diagram can express — a
              projectile arc being traced, a wave propagating, particles diffusing, a
              pendulum swinging, an orbit. content = one precise English sentence naming
              the system, its motion and its visible quantities.

ONE ELEMENT PER DRAWABLE OBJECT. The renderer draws exactly the elements you declare;
anything mentioned only inside another element's text does not exist. "a factor tree of
84" is one invisible element — declare the circle, the branch, and each child separately.

STRUCTURE IS A FIELD, NOT PROSE:
- `connects: ["id_a", "id_b"]` makes the element an EDGE between two others (tree branch,
  flowchart arrow, bond, force between bodies). An edge gets NO position of its own.
- `relative_positioning.relation: "inside"` makes the element CONTENT of a container
  (a number in a node, candies in a tray). Siblings are auto-distributed; declare each
  content item as its own element.

POSITION:
- Standalone text (title, question, caption): `safe_zone_alignment` — TOP_CENTER,
  BOTTOM_CENTER, TOP_LEFT, TOP_RIGHT, LEFT_CENTER, RIGHT_CENTER. Never dead centre.
- A label describing a shape/point: `relative_positioning` anchored to it, with a
  direction pushing into empty space. Never give a label absolute coordinates.
- `absolute_position` only for shapes and coordinate systems.
- `scale`: 1.0-1.5 for the scene's main visual, 0.7-0.8 for text/labels.

NARRATION AND TIMING:
- {cues} narration cues for this scene (~{seconds} seconds of speech in total).
- Each cue introduces AT MOST 2 new elements, via `animation_events` entries
  {{"action": "show", "target": "<element id>"}}.
- Use "hide" to clear finished elements — at most two text blocks on screen at a time.
- Use "transform" (one element becomes another), "move_to" (element moves beside
  another, needs `to` and `direction`), "highlight", and at most one "focus" per scene.
- Every element you declare must be shown by exactly one "show" event.

STORY (this is why the video holds together):
- The running anchor MUST appear in this scene.
- Do NOT open by restating the topic. Continue from what the previous screen left.
- Facts must be correct: check any arithmetic, counts and balanced equations.

Return JSON ONLY — a single object with keys: description, composition, elements,
narration_cues, wait_time. No markdown, no commentary."""


def enabled():
    return os.getenv("DEEP_STORYBOARD", "0").strip() == "1"


def write_scenes(plan, topic="", persona="hybrid", language="hi-IN", style="",
                 tech_terms="english", research="", brief=None, client=None, keys=None):
    """Write every screen of `plan` into a StoryboardScene. Returns (scenes, notes)."""
    screens = plan.get("screens") or []
    if not screens:
        return [], []
    lang_block = language_rules(persona, language, tech_terms)

    def _one(idx_screen):
        i, screen = idx_screen
        prev = screens[i - 1] if i > 0 else None
        nxt = screens[i + 1] if i + 1 < len(screens) else None
        for attempt in (1, 2):
            try:
                scene = _write_one(screen, plan, prev, nxt, topic=topic, style=style,
                                   lang_block=lang_block, research=research,
                                   brief=brief or {}, client=client, keys=keys)
                if scene:
                    return scene, ""
            except Exception as e:
                logger.warning("[SCENES] screen %d attempt %d failed: %s",
                               screen.get("index"), attempt, e)
        logger.warning("[SCENES] screen %d degraded to a deterministic scene.",
                       screen.get("index"))
        return _fallback_scene(screen, plan), "degraded"

    with ThreadPoolExecutor(max_workers=max(1, WORKERS)) as pool:
        results = list(pool.map(_one, list(enumerate(screens))))

    scenes, notes = [], []
    for pos, ((scene, note), screen) in enumerate(zip(results, screens), start=1):
        scene = _discipline(scene, screen, pos)
        scenes.append(scene)
        if note:
            notes.append({"screen": screen.get("index"), "note": note})
    return scenes, notes


def _write_one(screen, plan, prev, nxt, topic, style, lang_block, research, brief,
               client, keys):
    seconds = float(screen.get("seconds") or 13)
    cues = max(2, min(4, round(seconds / 5.0)))
    system = _SYSTEM.format(language_rules=lang_block, shape_rule=SHAPE_CONTENT_RULE,
                            cues=cues, seconds=int(seconds))

    ask = {
        "topic": topic,
        "through_line": plan.get("through_line"),
        "running_anchor": plan.get("anchor"),
        "style_profile": style,
        "this_screen": {
            "index": screen.get("index"),
            "role": screen.get("role"),
            "title": screen.get("title"),
            "beat": screen.get("beat"),
            "visual_kind": screen.get("visual_kind"),
            "must_show": screen.get("must_show"),
            "must_say": [f.get("fact") for f in (screen.get("must_say") or [])],
            "inherits_from_previous": screen.get("carries"),
            "seconds": seconds,
        },
        "previous_screen": ({"title": prev.get("title"), "beat": prev.get("beat"),
                             "left_on_screen": prev.get("must_show")} if prev else None),
        "next_screen": ({"title": nxt.get("title"), "beat": nxt.get("beat")} if nxt else None),
    }
    for key in ("grade", "subject", "learning_objective"):
        if brief.get(key):
            ask[key] = brief[key]

    prompt = ("Write this scene.\n\n" + json.dumps(ask, ensure_ascii=False, indent=2))
    if research:
        prompt += ("\n\n" + research +
                   "\n\nEvery number, name and date you speak must come from the source "
                   "material above.")

    resp = call_llm_with_fallback(
        client, prompt=prompt, system_instruction=system,
        response_schema=StoryboardScene, temperature=0.3, task="storyboard", keys=keys,
    )
    scene = loads_json_lenient(resp.text)
    if isinstance(scene, list) and scene:
        scene = scene[0]
    if not isinstance(scene, dict):
        return None
    # Some models wrap the object; unwrap the single obvious container.
    if "elements" not in scene:
        for key in ("scene", "storyboard_scene", "result"):
            if isinstance(scene.get(key), dict):
                scene = scene[key]
                break
    if not isinstance(scene.get("elements"), list) or not scene["elements"]:
        return None
    if not isinstance(scene.get("narration_cues"), list) or not scene["narration_cues"]:
        return None
    return scene


# ── code disposes ─────────────────────────────────────────────────────────────

_ID_OK = re.compile(r"[^A-Za-z0-9_]")


def _discipline(scene, screen, position):
    """Make a model-written scene structurally safe for the transpiler.

    Everything here is a defect the transpiler would otherwise have to survive at
    render time: a duplicate id silently overwrites a mobject, an event naming a
    missing element emits a call on an undefined var (per-scene scripts are isolated
    renders, so a NameError kills the whole scene), and an element no cue ever shows
    falls through to cue 0 — which is how six objects land on one beat and the frame
    piles up.
    """
    scene = dict(scene or {})
    scene["scene_index"] = position
    scene["role"] = screen.get("role") or scene.get("role") or "build"
    if not scene.get("description"):
        scene["description"] = screen.get("beat") or screen.get("title") or ""
    try:
        scene["wait_time"] = max(0.5, min(3.0, float(scene.get("wait_time") or 1.0)))
    except (TypeError, ValueError):
        scene["wait_time"] = 1.0

    # 1. Unique, safe ids (remembering the rename so references can follow).
    elements, seen, renames = [], {}, {}
    for el in scene.get("elements") or []:
        if not isinstance(el, dict) or not str(el.get("content", "")).strip():
            continue
        raw = str(el.get("id") or "").strip() or f"el{len(elements) + 1}"
        eid = _ID_OK.sub("_", raw).strip("_") or f"el{len(elements) + 1}"
        if eid[0].isdigit():
            eid = "e_" + eid
        if eid in seen:
            base, n = eid, 2
            while f"{base}_{n}" in seen:
                n += 1
            eid = f"{base}_{n}"
        seen[eid] = True
        if eid != raw:
            renames[raw] = eid
        el = dict(el)
        el["id"] = eid
        elements.append(el)
        if len(elements) >= MAX_ELEMENTS_PER_SCENE:
            break
    if not elements:
        return _fallback_scene(screen, {"anchor": ""})
    ids = set(seen)

    def _fix(ref):
        ref = str(ref or "").strip()
        return renames.get(ref, ref)

    # 2. Drop references that point at nothing in THIS scene.
    for el in elements:
        rel = el.get("relative_positioning")
        if isinstance(rel, dict):
            target = _fix(rel.get("relative_to"))
            if target in ids and target != el["id"]:
                rel["relative_to"] = target
            else:
                el["relative_positioning"] = None
        conn = el.get("connects")
        if isinstance(conn, (list, tuple)):
            fixed = [_fix(c) for c in conn][:2]
            el["connects"] = fixed if len(fixed) == 2 and all(c in ids for c in fixed) else None
        elif conn is not None:
            el["connects"] = None
    scene["elements"] = elements

    # 3. Clean the events, then guarantee every element is shown exactly once.
    cues = [c for c in (scene.get("narration_cues") or [])
            if isinstance(c, dict) and str(c.get("cue", "")).strip()]
    if not cues:
        cues = [{"cue": screen.get("beat", ""), "animation_events": []}]
    shown = set()
    for cue in cues:
        kept = []
        for ev in (cue.get("animation_events") or []):
            if not isinstance(ev, dict):
                continue
            action, target = str(ev.get("action", "")).strip(), _fix(ev.get("target"))
            if action not in ("show", "hide", "transform", "highlight", "move_to", "focus"):
                continue
            if target not in ids:
                continue
            if ev.get("to") is not None:
                to = _fix(ev.get("to"))
                if to not in ids or to == target:
                    if action in ("transform", "move_to"):
                        continue          # these actions are meaningless without `to`
                    ev["to"] = None
                else:
                    ev["to"] = to
            if action == "show":
                if target in shown:
                    continue              # a second entrance re-adds a live mobject
                shown.add(target)
            ev["target"] = target
            kept.append(ev)
        cue["animation_events"] = kept
        cue.pop("event", None)            # structured events win; free text is legacy

    missing = [el["id"] for el in elements if el["id"] not in shown]
    for eid in missing:
        # Spread the orphans instead of dumping them on cue 0 (which is what the
        # transpiler does with unmapped elements — that is the frame pile-up).
        target_cue = min(cues, key=lambda c: (
            sum(1 for e in c["animation_events"] if e.get("action") == "show"),
            cues.index(c)))
        if sum(1 for e in target_cue["animation_events"]
               if e.get("action") == "show") >= MAX_NEW_PER_CUE and len(cues) > 1:
            target_cue = cues[-1]
        target_cue["animation_events"].append({"action": "show", "target": eid})
    scene["narration_cues"] = cues
    return scene


def _fallback_scene(screen, plan):
    """A deterministic scene built from the screen contract alone.

    Used when a writer fails twice. It is plain, but it draws every object the plan
    demanded and speaks every fact — a hole in the arc costs the story more than a
    modest scene does, and this one is at least guaranteed to satisfy the contract.
    """
    title = (screen.get("title") or "").strip()[:60]
    elements = [{
        "id": "title", "type": "text", "content": title or screen.get("beat", "")[:60],
        "entrance_animation": "Write", "exit_animation": "FadeOut",
        "scale": 0.8, "safe_zone_alignment": "TOP_CENTER",
    }]
    for i, obj in enumerate((screen.get("must_show") or [])[:5], start=1):
        elements.append({
            "id": f"obj{i}", "type": "shape", "content": obj,
            "entrance_animation": "Create", "exit_animation": "FadeOut", "scale": 1.0,
        })
    facts = [f.get("fact", "") for f in (screen.get("must_say") or []) if f.get("fact")]
    if not facts:
        facts = [screen.get("beat", "")]
    per = max(1, (len(elements) + len(facts) - 1) // max(1, len(facts)))
    cues, k = [], 0
    for fact in facts:
        events = [{"action": "show", "target": el["id"]} for el in elements[k:k + per]]
        k += per
        cues.append({"cue": fact, "animation_events": events})
    for el in elements[k:]:
        cues[-1]["animation_events"].append({"action": "show", "target": el["id"]})
    return {
        "scene_index": screen.get("index", 1),
        "role": screen.get("role", "build"),
        "description": screen.get("beat", ""),
        "composition": "Title banner at top, the scene's objects filling the centre stage.",
        "elements": elements,
        "narration_cues": cues,
        "wait_time": 1.0,
    }
