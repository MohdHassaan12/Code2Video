"""Deep Storyboard — the multi-agent front half, composed.

    sources.ingest ──► ResearchPack (cited chunks)
           │
           ▼
    screens.plan_screens ──► ScreenPlan   (what is on each screen, countable)
           │
           ▼
    scene_writers.write_scenes ──► one LLM call per screen, in parallel
           │
           ▼
    assemble ──► a StoryboardResponse-shaped board, measured and returned

Everything after this point is unchanged: the shape/language gate, the on-screen
language heal, the storyboard cache, the agent registry (visual/motion director) and
the deterministic transpiler all receive exactly the IR they received before. This
stage produces a *better-filled* board, not a different contract — which is why it can
be turned on and off with one env var and why every failure path falls back to the
single-call storyboard instead of failing the request.

`DEEP_STORYBOARD=1` enables it. It costs 1 + N LLM calls instead of 1, so it is
off by default: turning it on is a billing change.
"""
from __future__ import annotations

import logging
import os
import re

from .. import sources as sources_mod
from . import screens as screens_mod
from . import scene_writers

logger = logging.getLogger(__name__)

# Bump when the ideator/writer prompts change in a way meant to change output — it
# joins the storyboard cache key, so without a bump the 48 h cache keeps serving boards
# written by the old prompts and the improvement silently doesn't apply. Same rule as
# storyboard.PROMPT_VERSION; bumping is a billing change.
DEEP_VERSION = "2026-08-15-deep3-vividness"  # bumped: ideator gained the vividness floor


def enabled():
    return os.getenv("DEEP_STORYBOARD", "0").strip() == "1"


def build_pack(topic, context=None):
    """Resolve source material for a topic from whatever the caller supplied.

    Order: explicit `context["sources"]` refs (URLs / pasted text / YouTube links) →
    pre-resolved `context["grounding_chunks"]` (what `ce/` already passes) → optional
    auto-search (`SOURCE_AUTO_SEARCH=1`, needs a search key). Returns a ResearchPack,
    possibly empty — an empty pack is legal and means "no grounding", the behaviour
    every caller had before this module existed.
    """
    context = context or {}
    refs = context.get("sources") or context.get("source_refs") or []
    pack = sources_mod.ingest(
        refs, topic=topic,
        grade=str(context.get("grade") or ""), subject=str(context.get("subject") or ""),
    )
    if not pack.ok and context.get("grounding_chunks"):
        pack = sources_mod.pack_from_chunks(
            context["grounding_chunks"], context.get("grounding_source", "content_store"))
    return pack


def generate(topic, persona="hybrid", language="hi-IN", style="", tech_terms="english",
             context=None, client=None, keys=None, pack=None, target_duration_s=None):
    """Run the deep pipeline. Returns a board dict, or None to fall back.

    Returning None (rather than raising) is the contract every stage in this repo
    follows: a stage improves the artifact or stands aside.
    """
    context = context or {}
    pack = pack if pack is not None else build_pack(topic, context)
    research = pack.as_prompt()
    if pack.ok:
        logger.info("[DEEP] grounded on %d source(s): %s", len(pack.sources),
                    ", ".join(f"{s.id}={s.kind}" for s in pack.sources if s.chunks))
    else:
        logger.info("[DEEP] no source material — planning from the topic alone.")

    brief = {k: context.get(k) for k in
             ("grade", "subject", "learning_objective", "node_type", "pedagogical_plan")
             if context.get(k)}

    # Duration contract: the screen budget is derived by the ONE helper in
    # app/storyboard.py (a twin here would drift on the next tuning pass); the
    # screen count is the deep path's length lever the way the scene count is the
    # single call's. Local import: storyboard imports this module inside a function,
    # so a module-level import here would not cycle, but the local form matches how
    # the two modules already reach each other.
    lo = hi = None
    if target_duration_s:
        from .. import storyboard as storyboard_mod
        lo, hi, _ = storyboard_mod.duration_scene_budget(target_duration_s)

    plan = screens_mod.plan_screens(topic, research=research, brief=brief,
                                    client=client, keys=keys,
                                    min_screens=lo, max_screens=hi,
                                    target_seconds=target_duration_s)
    if not plan:
        return None

    scenes, notes = scene_writers.write_scenes(
        plan, topic=topic, persona=persona, language=language, style=style,
        tech_terms=tech_terms, research=research, brief=brief, client=client, keys=keys)
    if not scenes:
        logger.warning("[DEEP] no scenes written — falling back to the single-call board.")
        return None

    board = _assemble(topic, style, plan, scenes)
    board["research"] = pack.manifest()
    board["screen_plan"] = plan
    board["deep_trace"] = {
        "version": DEEP_VERSION,
        "screens": len(plan["screens"]),
        "degraded": [n["screen"] for n in notes if n.get("note") == "degraded"],
        "coverage": [screens_mod.coverage(sc, scene)
                     for sc, scene in zip(plan["screens"], scenes)],
    }
    _log_coverage(board["deep_trace"])
    return board


def _assemble(topic, style, plan, scenes):
    """Build the StoryboardResponse-shaped board the rest of the pipeline expects."""
    theorems, terms = [], []
    for scene in scenes:
        for el in scene.get("elements") or []:
            content = str(el.get("content") or "").strip()
            if el.get("type") in ("math", "math_evolution") and content:
                if content not in theorems:
                    theorems.append(content[:120])
    for screen in plan["screens"]:
        for fact in screen.get("must_say") or []:
            for term in re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b", fact.get("fact", "")):
                if 3 < len(term) < 40 and term not in terms:
                    terms.append(term)
    return {
        "topic": topic,
        "narrative": {"through_line": plan["through_line"], "anchor": plan["anchor"]},
        "key_theorems": theorems[:8],
        "key_terms": terms[:12],
        "style_profile": style or "3blue1brown/minimalist/neon",
        "aspect_ratio": "widescreen",
        "visual_storyboard": scenes,
    }


def _log_coverage(trace):
    """Long runs show progress — and a contract nobody reports is a contract nobody keeps."""
    total_req = sum(c["objects_required"] for c in trace["coverage"])
    total_got = sum(c["elements_written"] for c in trace["coverage"])
    missed = [f for c in trace["coverage"] for f in c["missing_facts"]]
    logger.info("[DEEP] %d screens | objects planned %d -> elements written %d | "
                "facts unspoken %d | degraded screens %s",
                trace["screens"], total_req, total_got, len(missed),
                trace["degraded"] or "none")
    for c in trace["coverage"]:
        if c["elements_written"] < c["objects_required"]:
            logger.warning("[DEEP]   screen %s under-delivered: %d elements for %d planned objects",
                           c["screen"], c["elements_written"], c["objects_required"])
        for fact in c["missing_facts"]:
            logger.warning("[DEEP]   screen %s never says: %s", c["screen"], fact)
