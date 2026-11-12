"""Socratic intake: ask before generating.

A video brief written by guessing is how lessons end up pitched at nobody. The intake
asks one question at a time, says WHY it is asking, and stops as soon as it knows
enough. Three behaviours make it feel like a conversation rather than a form:

* **It listens.** Anything the user already said is not asked again — "Pythagoras
  for class 8 in Hindi, about 5 minutes" answers four questions at once.
* **It pushes back.** A topic too broad to teach in one video ("maths", "physics")
  gets a narrowing question instead of being accepted.
* **It recommends.** The framework question arrives after the level is known, with
  the matching framework first and the reason attached.

The questions and the parsing are deterministic on purpose: the intake must work with
no model configured, must be identical on web and mobile, and must be testable. A
model can later be put in front of it to phrase follow-ups; the brief it fills is
the contract either way.
"""
from __future__ import annotations

import re
from typing import Any

from . import frameworks

LANGUAGES = [
    {"value": "en-IN", "label": "English"},
    {"value": "hi-IN", "label": "Hindi"},
    {"value": "hinglish", "label": "Hinglish (Hindi narration, English terms)"},
    {"value": "te-IN", "label": "Telugu"},
    {"value": "ta-IN", "label": "Tamil"},
]
LEVELS = [
    {"value": "foundation", "label": "New to it", "hint": "First meeting with the idea, or shaky basics"},
    {"value": "standard", "label": "Knows the basics", "hint": "Needs to become fluent and solve problems"},
    {"value": "advanced", "label": "Wants the why", "hint": "Uses the result, wants proof and limits"},
]
STYLES = [
    {"value": "storyteller", "label": "Warm storyteller", "hint": "Unhurried, vivid, one idea at a time"},
    {"value": "tutor", "label": "Crisp tutor", "hint": "Clear, brisk, explains every decision"},
    {"value": "questioner", "label": "Curious questioner", "hint": "Asks, waits, lets you predict first"},
]
# The shortest lesson is three minutes (the owner, 2026-10-09). A lesson has seven stages; two minutes gave each
# chapter about 33 words, which no chapter can be said in, and both two-minute lessons made that day were written
# at 337 and 377 words for "at most 229" and ran 2:30 and 2:57.
MIN_MINUTES = 3
DURATIONS = [
    {"value": 3, "label": "About 3 minutes", "hint": "One idea, one example"},
    {"value": 6, "label": "About 6 minutes", "hint": "Idea, worked example, practice"},
    {"value": 15, "label": "15–20 minutes", "hint": "A full lesson in chapters"},
]
_BROAD = {"math", "maths", "mathematics", "science", "physics", "chemistry", "biology", "algebra",
          "geometry", "history", "english", "economics", "geography", "trigonometry", "calculus"}
_LANGUAGE_WORDS = {"hinglish": "hinglish", "hindi": "hi-IN", "english": "en-IN", "telugu": "te-IN", "tamil": "ta-IN"}


def _question(qid: str, prompt: str, why: str, kind: str = "text", options: list | None = None,
              optional: bool = False, placeholder: str = "") -> dict:
    return {"id": qid, "prompt": prompt, "why": why, "kind": kind, "options": options or [],
            "optional": optional, "placeholder": placeholder}


def absorb(brief: dict, text: str) -> dict:
    """Pull whatever a free-text answer already tells us into the brief (never overwrites)."""
    low = (text or "").lower()
    grade = re.search(r"\b(?:class|grade|std|standard)\s*(\d{1,2})\b|\b(\d{1,2})(?:th|st|nd|rd)\s*(?:class|grade|std)\b", low)
    if grade and "grade" not in brief:
        brief["grade"] = int(grade.group(1) or grade.group(2))
        brief.setdefault("audience", f"Class {brief['grade']} students")
        # The class number says nothing about what THESE learners already know about
        # THIS topic, so the level is always asked (it used to be guessed from the class,
        # which silently skipped the most useful question of the interview).
    for word, code in _LANGUAGE_WORDS.items():
        if re.search(rf"\b{word}\b", low) and "language" not in brief:
            brief["language"] = code
            break
    minutes = re.search(r"\b(\d{1,2})\s*(?:-|to)?\s*(?:\d{1,2}\s*)?min", low)
    if minutes and "duration_minutes" not in brief:
        brief["duration_minutes"] = max(MIN_MINUTES, min(25, int(minutes.group(1))))
    return brief


def _clean_topic(text: str) -> str:
    """The subject itself, with the bits ``absorb`` already took out removed."""
    t = re.sub(r"\b(?:for|to)\s+(?:class|grade|std|standard)\s*\d{1,2}(?:\s+students?)?\b", " ", text, flags=re.I)
    t = re.sub(r"\b(?:class|grade|std|standard)\s*\d{1,2}\b", " ", t, flags=re.I)
    t = re.sub(r"\bin\s+(?:hinglish|hindi|english|telugu|tamil)\b", " ", t, flags=re.I)
    t = re.sub(r"\b(?:about\s+|around\s+)?\d{1,2}\s*(?:-|to)?\s*(?:\d{1,2}\s*)?min(?:ute)?s?\b", " ", t, flags=re.I)
    t = re.sub(r"^\s*(?:explain|teach|a video (?:on|about)|video (?:on|about)|make a video (?:on|about))\s+", "", t, flags=re.I)
    return re.sub(r"\s+", " ", t).strip(" ,.-")


def next_question(brief: dict) -> dict | None:
    """The single most useful thing to ask next, or ``None`` when the brief is complete."""
    topic = brief.get("topic", "")
    if not topic:
        return _question("topic", "What should this video teach?",
                         "Everything else depends on it. Say it the way you would to a colleague — "
                         "you can mention the class, language or length here too.",
                         placeholder="e.g. Why the Pythagorean theorem works, for class 8")
    if not brief.get("audience"):
        return _question("audience", "Who is it for?",
                         "The same idea is explained differently to a 12-year-old and to someone revising for an exam.",
                         placeholder="e.g. Class 8 students, rural government school")
    # Too broad for one video: a whole subject (the list), or a chapter the interviewer
    # model judged too wide (``needs_focus``, set by the service). Asked AFTER the audience,
    # because which idea to pick inside a chapter depends on who is learning it.
    if (topic.lower() in _BROAD or brief.get("needs_focus")) and not brief.get("focus"):
        return _question("focus", f"“{topic}” is a whole subject. Which one idea inside it should this video nail?",
                         "One video can make one idea land. A narrow topic is what lets the explanation go deep.",
                         placeholder="e.g. Why we flip the sign when multiplying an inequality by a negative")
    if not brief.get("level"):
        return _question("level", "How much do they already know about this?",
                         "This decides where the explanation starts and which teaching framework fits.",
                         kind="choice", options=LEVELS)
    if not brief.get("goal"):
        return _question("goal", "After watching, what should they be able to DO that they could not do before?",
                         "A lesson aimed at an action (“find a missing side”, “explain why”) can be checked; "
                         "“understand X” cannot.",
                         placeholder="e.g. Find the diagonal of a rectangle and explain why squaring is involved")
    if not brief.get("framework"):
        best = frameworks.recommend(brief.get("level"))
        ordered = sorted(frameworks.OFFERED, key=lambda f: f["id"] != best)
        options = [{"value": f["id"], "label": f["plain"] + (" (suggested)" if f["id"] == best else ""),
                    "hint": f["plain_hint"]} for f in ordered]
        return _question("framework", "What kind of video should this be?",
                         "The same idea can open with a picture, with a solved example, or with the reason it is "
                         f"true. For the starting point you chose, “{frameworks.get(best)['plain']}” usually works best.",
                         kind="choice", options=options)
    if not brief.get("style"):
        return _question("style", "How should the teacher sound?",
                         "The narration is written for a voice. Choosing it now keeps the whole lesson in one register.",
                         kind="choice", options=STYLES)
    if not brief.get("language"):
        return _question("language", "Which language should it be narrated in?",
                         "Each language gets its own script and its own timing — it is not a translation pass at the end.",
                         kind="choice", options=LANGUAGES)
    if not brief.get("duration_minutes"):
        return _question("duration_minutes", "How long should it be?",
                         "Length follows from how much the learner needs, but a target keeps the script honest.",
                         kind="choice", options=DURATIONS)
    if "context" not in brief:
        # One simple example, not a setting: asked as "a setting they will recognise" (with
        # "cricket ground" as the hint) this produced a Diwali-mela stall for square numbers
        # and a cricket squad's fatigue sensors for gradient descent — examples harder to
        # follow than the ideas they were meant to carry.
        return _question("context", "Is there one simple example it should use?",
                         "One small thing the learner can picture or count makes the idea visible. Simpler is better: "
                         "skip this and the lesson uses plain small numbers.",
                         optional=True, placeholder="e.g. a 3 by 3 tray of sweets, a ladder against a wall — or skip")
    if "misconception" not in brief:
        return _question("misconception", "What do learners usually get wrong here?",
                         "If we know the usual mistake, the lesson can meet it head-on instead of hoping it does not come up.",
                         optional=True, placeholder="e.g. They add the sides instead of squaring — or skip")
    return None


def answer(brief: dict, question_id: str, value: Any) -> dict:
    """Record an answer. Free text is also mined for anything else it reveals."""
    text = "" if value is None else str(value).strip()
    if question_id in ("topic", "focus"):
        absorb(brief, text)
        cleaned = _clean_topic(text)
        if question_id == "focus" and cleaned:
            # Keep the wider subject: the writer uses it to place the idea, not to teach it.
            if brief.get("topic") and brief["topic"].lower() != cleaned.lower():
                brief.setdefault("subject", brief["topic"])
            brief["focus"], brief["topic"] = cleaned, cleaned
            brief.pop("needs_focus", None)
        elif cleaned:
            brief["topic"] = cleaned
    elif question_id == "audience":
        absorb(brief, text)
        brief["audience"] = text or brief.get("audience", "")
    elif question_id == "duration_minutes":
        digits = re.search(r"\d+", text)
        brief["duration_minutes"] = max(MIN_MINUTES, min(25, int(digits.group()))) if digits else 6
    elif question_id in ("context", "misconception"):
        handed_back = bool(re.match(r"^(you|u) (can )?(decide|choose|pick)|^up to you|^anything|^whatever|^(not sure|no idea|idk)",
                                    text, re.I))
        brief[question_id] = "" if handed_back or text.lower() in ("", "skip", "no", "none", "-") else text
    elif question_id in ("level", "framework", "style", "language", "goal"):
        if text:
            brief[question_id] = text
    return brief


def progress(brief: dict) -> dict:
    required = ["topic", "audience", "level", "goal", "framework", "style", "language", "duration_minutes"]
    done = sum(1 for k in required if brief.get(k))
    return {"answered": done, "of": len(required), "complete": next_question(brief) is None}


def summary(brief: dict) -> list[dict]:
    """The brief as label/value rows for a confirmation screen."""
    label = lambda options, value: next((o["label"] for o in options if o["value"] == value), str(value or ""))  # noqa: E731
    rows = [
        ("Topic", brief.get("topic", "")),
        ("For", brief.get("audience", "")),
        ("Starting point", label(LEVELS, brief.get("level"))),
        ("They will be able to", brief.get("goal", "")),
        ("Kind of video", frameworks.get(brief.get("framework", ""))["plain"] if brief.get("framework") else ""),
        ("Voice", label(STYLES, brief.get("style"))),
        ("Language", label(LANGUAGES, brief.get("language"))),
        ("Length", f"about {brief['duration_minutes']} min" if brief.get("duration_minutes") else ""),
        ("Example", brief.get("context", "")),
        ("Known mistake", brief.get("misconception", "")),
    ]
    return [{"label": k, "value": v} for k, v in rows if v]
