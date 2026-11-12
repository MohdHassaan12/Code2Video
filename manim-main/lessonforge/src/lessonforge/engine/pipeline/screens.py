"""Screen Ideator — decide WHAT IS ON EACH SCREEN before anyone writes a scene.

The measured problem this fills (user report, 2026-08-15: *"the gen video has less
content and not good flow"*): the whole board — narrative spine, every scene, every
element, every cue, in every language — came out of **one** LLM call. One call has one
token budget, and a model spreading it over six scenes writes the first scene properly
and sketches the rest. There was also nothing anywhere that stated, before generation,
how much a scene was *supposed* to contain, so "thin" was unmeasurable: you could only
watch the video and feel it.

So this stage produces a **plan, not prose**: an ordered list of screens, each with an
explicit, countable contract —

    must_show:  the drawable objects that MUST exist on that screen
    must_say:   the facts that MUST be spoken, each citing its source chunk
    beat:       the one thing the viewer learns here
    carries:    what this screen inherits from the one before (the flow)

`must_show` is the load-bearing field. It is written as *one entry per drawable
object*, which is the storyboard prompt's rule 4c stated as data instead of advice —
and because it is data, the scene writer can be graded against it (`coverage()`), and
a thin scene becomes a number in the log rather than a feeling about a video.

Doctrine, unchanged from the rest of the pipeline: **the model proposes, code
disposes.** Everything the model returns here passes through `_normalize`, which
clamps counts, fixes the role arc, dedupes, and drops anything malformed. A plan that
cannot be repaired is discarded and the caller falls back to the single-call path —
this stage improves the board or stands aside.
"""
from __future__ import annotations

import json
import logging
import os
import re

from ..llm import call_llm_with_fallback, loads_json_lenient

logger = logging.getLogger(__name__)

MIN_SCREENS = int(os.getenv("SCREENS_MIN", "5"))
MAX_SCREENS = int(os.getenv("SCREENS_MAX", "8"))
MIN_MUST_SHOW = int(os.getenv("SCREENS_MIN_OBJECTS", "3"))
MAX_MUST_SHOW = int(os.getenv("SCREENS_MAX_OBJECTS", "6"))
DEFAULT_SECONDS = 13.0

ROLES = ("hook", "build", "turn", "payoff", "recap")
VISUAL_KINDS = ("diagram", "simulation", "derivation", "comparison", "image", "data")


_SYSTEM = """You are the scene ideator for a short educational animation — the stage
that decides what appears on each SCREEN, before anyone writes narration or draws
anything.

You produce a SHOT LIST, not prose. Every screen is a contract the later stages must
satisfy, so be concrete and countable: name the objects, not the topic.

THE ARC (this is what makes it a video and not a slideshow):
- Pick ONE concrete running anchor — a specific thing the viewer can picture ("a
  basketball thrown at a hoop", "a single water droplet on a leaf"), never a topic
  name ("projectile motion").
- Write a through-line: the one question the whole video answers.
- Screen 1 opens that question with the anchor. Every later screen CONTINUES from the
  previous one — it may never re-introduce the topic from scratch. The last screen
  answers the question by name.
- `carries` states, in a few words, what this screen inherits from the previous one
  (the object still on screen, the number just derived, the contradiction just found).

must_show — THE MOST IMPORTANT FIELD:
- List every object that must be DRAWN, one entry per object. "a factor tree" is
  wrong; "circle labelled 84", "branch from 84 to 12", "circle labelled 12" is right.
- {min_show}-{max_show} objects per screen. Fewer than {min_show} renders as a dead
  frame — a title and one small shape on an empty canvas.
- Include the whole process, not just the props: the incoming ray AND the slab AND the
  bent ray; the mass AND the spring AND the arrow showing the stretch.
- Say what carries meaning, e.g. "dashed parabola tracing where the ball will land",
  not "a curve".
- VIVIDNESS FLOOR: the screen's main visual must show the idea HAPPENING — the
  object, the action on it, AND the outcome, with the source's REAL values on
  screen (the number from the fact, not "a value"). A lone emblem with a label
  satisfies the count and still reads as a dead frame — it does not satisfy this.

must_say:
- The facts the narration must state on this screen, in English, one per entry.
- If SOURCE MATERIAL is provided, every number, name, date and definition MUST come
  from it, and you MUST put the source tag (e.g. "S1#2") in `cite`. Never invent a
  figure. If the sources do not support a fact, leave it out. With no sources given,
  set cite to "" and stay with textbook-standard facts.

visual_kind — pick the honest one:
  diagram (a labelled construction) · simulation (a system evolving over time: a
  trajectory, a wave, an orbit, particles, a mechanism in motion) · derivation (an
  equation being built or transformed) · comparison (two things side by side) ·
  image (a real photograph/painting/map is the point — history, people, places) ·
  data (a plotted graph of real values)
Prefer `simulation` whenever the idea is about CHANGE OVER TIME — a static picture of
a moving thing is the commonest way these videos fall flat.

Return JSON ONLY:
{{"through_line": "...", "anchor": "...", "screens": [
  {{"index": 1, "role": "hook", "title": "...", "beat": "...",
    "visual_kind": "diagram", "carries": "",
    "must_show": ["...", "..."], "must_say": [{{"fact": "...", "cite": "S1#2"}}],
    "seconds": 12}}
]}}
Produce {min_screens}-{max_screens} screens covering hook -> build -> turn -> payoff -> recap."""


def enabled():
    return os.getenv("DEEP_STORYBOARD", "0").strip() == "1"


def plan_screens(topic, research="", brief=None, client=None, keys=None,
                 min_screens=None, max_screens=None, target_seconds=None):
    """Return a normalized screen plan dict, or None if the stage could not produce one.

    `research` is `ResearchPack.as_prompt()` output (may be empty).
    `brief` carries grade/subject/objective/node_type when the caller has them.
    `target_seconds` (duration contract) rides only when set, so a targetless
    request's prompt stays byte-identical — the cache-preservation rule.
    """
    brief = brief or {}
    lo = int(min_screens or MIN_SCREENS)
    hi = int(max_screens or MAX_SCREENS)
    system = _SYSTEM.format(min_screens=lo, max_screens=hi,
                            min_show=MIN_MUST_SHOW, max_show=MAX_MUST_SHOW)

    parts = [f"Topic: {topic}"]
    if target_seconds:
        parts.append(f"Target total duration: ~{int(target_seconds)} seconds. Set each "
                     f"screen's `seconds` so the screens SUM to that — trim beats "
                     f"rather than rushing every screen.")
    for key, label in (("grade", "Audience grade"), ("subject", "Subject"),
                       ("learning_objective", "Learning objective"),
                       ("node_type", "Segment type")):
        if brief.get(key):
            parts.append(f"{label}: {brief[key]}")
    if brief.get("pedagogical_plan"):
        parts.append("An upstream pedagogical plan is provided — keep its teaching order "
                     "and its beats; your job is to make each beat VISUAL and countable.\n"
                     + json.dumps(brief["pedagogical_plan"], ensure_ascii=False)[:6000])
    if research:
        parts.append(research)
    else:
        parts.append("(No source material provided — do not cite, and stay with "
                     "textbook-standard facts.)")

    try:
        resp = call_llm_with_fallback(
            client,
            prompt="\n\n".join(parts),
            system_instruction=system,
            temperature=0.35,
            task="storyboard",
            keys=keys,
        )
        raw = loads_json_lenient(resp.text)
    except Exception as e:
        logger.warning("[SCREENS] ideation failed (%s) — falling back to the single-call board.", e)
        return None

    plan = _normalize(raw, topic, lo, hi)
    if not plan:
        logger.warning("[SCREENS] ideation returned an unusable plan — standing aside.")
        return None
    logger.info("[SCREENS] %d screens planned | anchor=%r | objects=%s",
                len(plan["screens"]), plan["anchor"],
                [len(s["must_show"]) for s in plan["screens"]])
    for s in plan["screens"]:
        logger.info("[SCREENS]   %d. %-7s %-11s %s", s["index"], s["role"],
                    s["visual_kind"], s["beat"][:70])
    return plan


# ── code disposes ─────────────────────────────────────────────────────────────

def _normalize(raw, topic, lo, hi):
    """Clamp, repair and validate a model-authored plan. Returns None if unusable."""
    if not isinstance(raw, dict):
        return None
    screens_in = raw.get("screens")
    if not isinstance(screens_in, list) or not screens_in:
        return None

    screens = []
    for item in screens_in:
        if not isinstance(item, dict):
            continue
        must_show = _clean_list(item.get("must_show"))[:MAX_MUST_SHOW]
        must_say = _clean_facts(item.get("must_say"))
        beat = _clean_str(item.get("beat")) or _clean_str(item.get("title"))
        if not beat or not must_show:
            # A screen with nothing to show or nothing to teach is not a screen.
            continue
        kind = _clean_str(item.get("visual_kind")).lower()
        role = _clean_str(item.get("role")).lower()
        try:
            seconds = float(item.get("seconds") or DEFAULT_SECONDS)
        except (TypeError, ValueError):
            seconds = DEFAULT_SECONDS
        screens.append({
            "index": len(screens) + 1,
            "role": role if role in ROLES else "build",
            "title": _clean_str(item.get("title"))[:80] or beat[:80],
            "beat": beat[:400],
            "visual_kind": kind if kind in VISUAL_KINDS else "diagram",
            "carries": _clean_str(item.get("carries"))[:200],
            "must_show": must_show,
            "must_say": must_say,
            "seconds": max(6.0, min(30.0, seconds)),
        })
        if len(screens) >= hi:
            break

    if len(screens) < 2:
        return None
    # The arc is code's call, not the model's: whatever it labelled, the first screen
    # opens and the last one closes. A board that opens on "build" reads as arriving
    # mid-lesson — the exact "no story" complaint that produced the narrative spine.
    screens[0]["role"] = "hook"
    screens[0]["carries"] = ""
    if len(screens) >= 3 and screens[-1]["role"] not in ("recap", "payoff"):
        screens[-1]["role"] = "recap"

    if len(screens) < lo:
        logger.warning("[SCREENS] only %d screens planned (wanted >= %d) — accepting, "
                       "the video will be short.", len(screens), lo)

    anchor = _clean_str(raw.get("anchor"))
    through = _clean_str(raw.get("through_line"))
    if not anchor:
        # An empty anchor silently disables every continuity check downstream, so it is
        # never left empty; the topic is a weak anchor but a checkable one.
        anchor = topic
        logger.warning("[SCREENS] no anchor returned — defaulting to the topic, "
                       "continuity will be weak.")
    return {
        "topic": topic,
        "through_line": through or f"What is {topic}, and why does it work that way?",
        "anchor": anchor,
        "screens": screens,
    }


def _clean_str(v):
    if not isinstance(v, str):
        return ""
    return re.sub(r"\s+", " ", v).strip()


def _clean_list(v):
    """Deduped, non-empty strings. Accepts a newline/semicolon blob as a courtesy —
    models write lists as prose often enough that rejecting it wastes a whole call."""
    items = []
    if isinstance(v, str):
        v = re.split(r"[\n;]+|(?<=[a-z])\s*,\s*(?=[a-z])", v)
    if not isinstance(v, list):
        return []
    seen = set()
    for item in v:
        if isinstance(item, dict):
            item = item.get("object") or item.get("name") or item.get("text") or ""
        s = _clean_str(item).lstrip("-•* ").strip()
        if len(s) < 3:
            continue
        key = s.lower()
        if key in seen:
            continue
        seen.add(key)
        items.append(s[:160])
    return items


def _clean_facts(v):
    out, seen = [], set()
    if isinstance(v, str):
        v = [v]
    for item in (v if isinstance(v, list) else []):
        if isinstance(item, dict):
            fact, cite = _clean_str(item.get("fact")), _clean_str(item.get("cite"))
        else:
            fact, cite = _clean_str(item), ""
        if len(fact) < 4 or fact.lower() in seen:
            continue
        seen.add(fact.lower())
        out.append({"fact": fact[:300], "cite": cite[:24]})
    return out


# ── grading ───────────────────────────────────────────────────────────────────

def coverage(screen, scene):
    """How much of a screen's contract the written scene actually honours.

    Returns {objects_required, elements_written, facts_required, missing_facts}.
    Deliberately a *measurement*, not a gate: a scene that under-delivers still
    renders, and rejecting on a soft metric would spend a full regeneration to chase
    it. The same call this repo made for `narrative_problems` — but without the number
    there is no way to tell whether a prompt change helped.
    """
    els = [e for e in (scene.get("elements") or []) if isinstance(e, dict)]
    said = " ".join(str(c.get("cue", "")) for c in (scene.get("narration_cues") or [])).lower()
    missing = []
    for fact in screen.get("must_say") or []:
        words = [w for w in re.findall(r"[a-zA-Z]{4,}", fact.get("fact", "").lower())][:6]
        if words and sum(1 for w in words if w in said) < max(1, len(words) // 2):
            missing.append(fact.get("fact", "")[:60])
    return {
        "screen": screen.get("index"),
        "objects_required": len(screen.get("must_show") or []),
        "elements_written": len(els),
        "facts_required": len(screen.get("must_say") or []),
        "missing_facts": missing,
        # Vividness floor, the countable half: <3 elements is the "one small emblem
        # plus a label" frame the NLM pipeline measured — technically compliant with
        # an anchor rule, still a dead frame. Measured, not enforced, like the rest.
        "sparse": len(els) < 3,
    }
