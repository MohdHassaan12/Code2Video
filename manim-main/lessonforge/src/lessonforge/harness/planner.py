"""A whole chapter → an ordered series of single-idea lessons.

One video can make one idea land (``intake`` pushes back on "Trigonometry" for that
reason). A learner still has to get through the chapter, so this is the step before
the intake: a curriculum designer's cut of a chapter into the smallest sequence of
lessons an INTRODUCTORY student can follow — each naming its one idea, what it leans
on, a goal that can be checked and a running example — which the batch runner
(``lessonforge harness BRIEFS.json``) or the client can then generate one by one.

Within each lesson the same idea continues one level down: beats carry a ``depth``
(basics / core / practice / extra), so a single video can be watched in full, with
the basics skipped, as a quick revision or as a summary (``service.write_outline``).

Code owns the structure here too: the order is re-numbered, prerequisites may only
point backwards, lengths are clamped, and a plan with fewer than two usable lessons
is refused rather than passed on.
"""
from __future__ import annotations

import re
from typing import Any, Callable

from . import frameworks, intake

LLM = Callable[[str, str], Any]
MAX_LESSONS = 14

SYSTEM = """You are a curriculum designer for Indian school mathematics and science. You are given a chapter (or a
broad topic) and the learners. Split it into the SMALLEST ordered sequence of video lessons an introductory
student can follow, where each lesson teaches exactly ONE idea and uses only ideas from earlier lessons.
Follow the NCERT order for that class when the chapter is an NCERT chapter. Return ONLY JSON:
{"chapter": "the chapter as you understood it",
 "for": "who it is for",
 "lessons": [{
    "title": "at most 9 words, names the idea",
    "idea": "the one idea, as a sentence a student could repeat",
    "prerequisites": [1, 2],            // numbers of EARLIER lessons in this list it relies on; [] for the first
    "outside_prerequisites": ["what must already be known from before this chapter"],
    "goal": "what the learner can DO afterwards — an action that can be checked",
    "running_example": "one concrete everyday setting with numbers, familiar to these learners",
    "misconception": "the mistake students usually make on this idea",
    "minutes": 5,                       // 3 to 8
    "level": "foundation | standard | advanced",
    "revision_note": "the one line a student revising must remember"
 }]}
Rules: 4 to 12 lessons. No lesson may be a 'summary' or 'introduction' with no idea of its own. Technical terms in
English. Do not skip a step a beginner needs; do not pad with enrichment."""


def _text(value, limit: int) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()[:limit]


def plan_chapter(subject: str, audience: str, llm: LLM, language: str = "en-IN") -> dict:
    """The lesson series for a chapter. Raises ``ValueError`` when the model's plan is unusable."""
    raw = llm(f"CHAPTER / TOPIC: {subject}\nLEARNERS: {audience or 'school students'}\n"
              f"NARRATION LANGUAGE (for wording the examples only): {language}", SYSTEM)
    if not isinstance(raw, dict):
        raise ValueError("the planner model did not return an object")
    lessons = []
    for item in (raw.get("lessons") or [])[:MAX_LESSONS]:
        if not isinstance(item, dict):
            continue
        title, idea = _text(item.get("title"), 90), _text(item.get("idea"), 220)
        if not title or not idea:
            continue
        order = len(lessons) + 1
        prerequisites = sorted({int(p) for p in (item.get("prerequisites") or [])
                                if str(p).strip().lstrip("-").isdigit() and 1 <= int(p) < order})
        try:
            minutes = max(3, min(8, int(item.get("minutes") or 5)))
        except (TypeError, ValueError):
            minutes = 5
        level = str(item.get("level") or "").lower()
        lessons.append({
            "order": order, "title": title, "idea": idea, "prerequisites": prerequisites,
            "outside_prerequisites": [_text(p, 120) for p in (item.get("outside_prerequisites") or [])[:4] if _text(p, 120)],
            "goal": _text(item.get("goal"), 200), "running_example": _text(item.get("running_example"), 200),
            "misconception": _text(item.get("misconception"), 200), "minutes": minutes,
            "level": level if level in ("foundation", "standard", "advanced") else "foundation",
            "revision_note": _text(item.get("revision_note"), 200),
        })
    if len(lessons) < 2:
        raise ValueError("the plan has fewer than two usable lessons")
    return {"chapter": _text(raw.get("chapter") or subject, 120), "for": _text(raw.get("for") or audience, 160),
            "language": language, "lessons": lessons,
            "minutes_total": sum(lesson["minutes"] for lesson in lessons)}


def to_briefs(plan: dict, style: str = "storyteller") -> list[dict]:
    """One generation brief per planned lesson (the fields the intake would have filled)."""
    briefs = []
    by_order = {lesson["order"]: lesson for lesson in plan["lessons"]}
    for lesson in plan["lessons"]:
        brief = {"topic": lesson["title"], "subject": plan["chapter"], "audience": plan["for"],
                 "level": lesson["level"], "goal": lesson["goal"] or f"Explain and use: {lesson['idea']}",
                 "framework": frameworks.recommend(lesson["level"]), "style": style,
                 "language": plan.get("language", "en-IN"), "duration_minutes": lesson["minutes"],
                 "context": lesson["running_example"], "misconception": lesson["misconception"],
                 "notes": {"idea": lesson["idea"],
                           "builds on": "; ".join(by_order[p]["title"] for p in lesson["prerequisites"]) or
                                        "; ".join(lesson["outside_prerequisites"]) or "nothing earlier in this chapter"},
                 "series": {"chapter": plan["chapter"], "order": lesson["order"], "of": len(plan["lessons"])}}
        intake.absorb(brief, plan["for"])          # class number → grade
        briefs.append(brief)
    return briefs


def default_llm() -> LLM | None:
    """The writer's model chain (a plan is read by people and reused many times: quality over speed)."""
    from . import writer
    return writer.default_llm(temperature=0.3)
