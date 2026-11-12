"""A unit of a teaching pack → a geometry lesson, written by a model and checked by code (``shapes``).

The owner's quadrilaterals pack (2026-10-20) has, for every unit, sections A, B, C, D, each with its narration,
"visual events", interaction and adaptive feedback. The first nine videos from it were written out by hand, because
model-drawn geometry got angles and labels wrong. Here the model writes the lesson the same way the hand-made ones
are built, and code holds it to its pictures:

* one chapter per section of the unit, then a short recap; the section's interaction is where the lesson stops for
  a question, and its adaptive feedback becomes the reason shown for each wrong option;
* every picture is a ``shape`` figure over shapes declared once by their points (``shapes.SHAPE_RULES``); every
  measured value in the words is a gap that code fills from those points;
* ``shapes.settle`` finds every fault (a claim the points do not make true, a number the picture does not show, a
  gap that cannot be filled, a step whose words are not in its beat) and the model is shown exactly those faults
  and asked again, up to ``MAX_REPAIRS`` times. A lesson with faults left is still returned, with them listed, and
  ``service`` refuses to film one whose gaps are still open.

No person writes or corrects a word. The model is the writer's own chain (``writer.default_llm``).
"""
from __future__ import annotations

import copy
import json
import re

from ..longform.contract import Lesson
from . import shapes, writer

GENERATED_BY = "geometry pack"
MAX_REPAIRS = 3
_UNIT = re.compile(r"^#\s+(\d+)\.\s+(.+?)\s*$", re.M)
_SECTION = re.compile(r"^##\s+(.+?)\s*$", re.M)
_RULES_HEADINGS = ("mathematical corrections", "safeguards", "framework contract", "conventions")


def is_pack(brief: dict) -> bool:
    return isinstance(brief, dict) and brief.get("mode") == "pack"


def units(text: str) -> list[dict]:
    """``[{"number", "title", "text", "sections": [{"title", "text"}]}]`` from a pack's ``# N. Title`` headings."""
    found = list(_UNIT.finditer(text))
    out = []
    for k, m in enumerate(found):
        end = found[k + 1].start() if k + 1 < len(found) else len(text)
        body = text[m.end():end]
        stop = re.search(r"^#\s+(?!\d+\.)", body, re.M)       # "# Validation checklist" after the last unit
        if stop:
            body = body[:stop.start()]
        heads = list(_SECTION.finditer(body))
        sections = [{"title": h.group(1), "text": body[h.end():(heads[i + 1].start() if i + 1 < len(heads) else len(body))].strip()}
                    for i, h in enumerate(heads)]
        out.append({"number": int(m.group(1)), "title": m.group(2), "text": body.strip(), "sections": sections})
    return out


def rules(text: str) -> str:
    """The pack's own rules (its corrections and safeguards), which every unit is held to."""
    keep = []
    for m in re.finditer(r"^#\s+(.+?)\s*$", text, re.M):
        if any(h in m.group(1).lower() for h in _RULES_HEADINGS):
            nxt = re.search(r"^#\s+", text[m.end():], re.M)
            keep.append(text[m.end(): m.end() + (nxt.start() if nxt else len(text))].strip())
    return "\n\n".join(keep)[:4000]


SYSTEM = (writer._SYSTEM_OPENING + writer.STEP_RULES.replace(
    """  "focus" — the part of this beat's figure the step is about""", """  "focus" — (not used with a shape figure) the part of this beat's figure the step is about""")
    + """- A beat may carry ONE "figure" drawn by code. In this lesson every picture is a shape figure:
""" + shapes.SHAPE_RULES + """
- A QUESTION STOP: a beat whose narration ENDS with the question, with "thinking_pause_seconds" 6 to 8 and a "quiz":
  {"question": "at most 14 words, ends with ?", "options": ["2 to 4 short answers"], "answer_index": 0,
   "why": ["one sentence for EACH option, in order: why it is right, or what makes it tempting and why it fails"],
   "kind": "predict|spot|apply|recall"}. The NEXT beat opens by saying the answer. Vary where the right option sits.
""" + writer.QUESTION_RULES + """
- WRITING: one beat is 25 to 70 spoken words. Short, plain sentences a teacher says to one learner, one claim each.
  Name points by their letters ("side AB", "angle D", "the diagonal AC") so the picture can light them as they are
  said. No stock phrases, no lesson plan said aloud, no "in this video". On-screen words are short (at most 9
  words), never a sentence of narration.
""")

SHAPE_OF_ANSWER = ('{"title": str, "shapes": {"<name>": {"points": {"A": [x, y], ...}, "polygon": "ABCD", '
                   '"is": ["convex"]}}, "chapters": [{"title": "SHORT CAPS TITLE", "learning_goal": str, '
                   '"role": "explain|predict|practice|recap", "beats": [{"narration": str, "figure": {...} or null, '
                   '"steps": [{"say": str, "show": str, "kind": "point|key|math"}], "quiz": {...} or null, '
                   '"thinking_pause_seconds": number, "depth": "basics|core|practice|extra"}]}]}')


def prompt_for(unit: dict, pack_rules: str, language: str = "en-US", words: int = 560) -> str:
    sections = "\n\n".join(f"SECTION {s['title']}\n{s['text']}" for s in unit["sections"]) or unit["text"]
    return (f"Write the narrated lesson for unit {unit['number']} of a teaching pack: {unit['title']}.\n\n"
            f"THE PACK'S RULES (every claim must respect them):\n{pack_rules}\n\n"
            f"THE UNIT, as the pack's author wrote it:\n{sections}\n\n"
            "HOW TO TURN IT INTO A LESSON:\n"
            f"- One chapter for each section above, in order, then one short recap chapter ({len(unit['sections']) + 1} "
            "chapters). The section's Narration is what the chapter teaches (say it in your own plain words, more "
            "fully); its Visual events are what the pictures show; its Interaction is where that chapter STOPS for a "
            "question; its Adaptive feedback and hints become the reasons under the wrong options.\n"
            "- Declare every shape ONCE in \"shapes\" with points that really make it what the lesson says: a convex "
            "example, a concave example, a thin but convex one, and so on. Reuse a shape by name on every beat that "
            "shows it, adding to it as the voice goes: first the bare shape, then its angles, then its diagonals, "
            "then a verdict. Put two shapes side by side (panels) when the lesson compares them.\n"
            "- A slider in the pack becomes a corner that moves (\"move\") while the voice describes each phase.\n"
            "- Where the lesson finds a value (a missing angle, a sum), the question gives the known values as gaps "
            "and the options are gaps too: the right one and the values a real mistake gives "
            "({360 - angle D} for the outside angle, {180 - angle A - angle B - angle C} for using 180).\n"
            "- The recap asks first (a recall question) and then says the ideas again in new, shorter words.\n"
            f"- About {words} spoken words in all: 3 to 4 beats a chapter.\n"
            + ("- LANGUAGE: " + writer._LANGUAGE_NOTES.get(language, "") + "\n" if language in writer._LANGUAGE_NOTES else "")
            + f"\nReturn ONLY JSON of this shape:\n{SHAPE_OF_ANSWER}")


def structure_issues(lesson: dict) -> list[str]:
    """What the hand-made lessons' ``common.check`` holds them to: steps in order, questions that are questions."""
    issues = []
    number = 0
    beats = [b for c in lesson.get("chapters") or [] for b in c.get("beats") or []]
    for ci, ch in enumerate(lesson.get("chapters") or [], start=1):
        for b in ch.get("beats") or []:
            number += 1
            ref = f"beat {number} (chapter {ci})"
            said = " ".join(writer._norm(b.get("narration", "")).split())
            at = 0
            for k, st in enumerate(b.get("steps") or []):
                say = " ".join(writer._norm(st.get("say", "")).split())
                hit = said.find(say, at) if say else -1
                if hit < 0:
                    issues.append(f"{ref} step {k + 1}: its \"say\" “{st.get('say', '')}” is not in the narration "
                                  "(in order, word for word)")
                else:
                    at = hit
            quiz = b.get("quiz")
            if isinstance(quiz, dict):
                if not str(b.get("narration", "")).rstrip().endswith("?"):
                    issues.append(f"{ref}: a question stop must END with its question")
                if len(quiz.get("why") or []) != len(quiz.get("options") or []):
                    issues.append(f"{ref} quiz: give one reason for each option")
                if b is beats[-1]:
                    issues.append(f"{ref}: the lesson ends on a question; a beat after it must give the answer")
                try:
                    if not 0 <= int(quiz.get("answer_index")) < len(quiz.get("options") or []):
                        raise ValueError
                except (TypeError, ValueError):
                    issues.append(f"{ref} quiz: answer_index must point at one of the options")
            if not (b.get("steps") or []):
                issues.append(f"{ref}: give 1 to 4 steps")
    if not number:
        issues.append("the lesson has no beats")
    return issues


def faults(raw: dict) -> tuple[dict, list[str]]:
    filled, issues = shapes.settle(raw)
    return filled, issues + structure_issues(filled)


def write_unit(unit: dict, pack_rules: str, llm, language: str = "en-US", log=print) -> dict:
    """The lesson for one unit: the model writes, code checks, the model fixes what code found, up to MAX_REPAIRS."""
    raw = llm(prompt_for(unit, pack_rules, language), SYSTEM)
    filled, issues = faults(raw)
    rounds = [len(issues)]
    log(f"[pack] unit {unit['number']}: first draft, {len(issues)} fault(s)")
    for i in range(MAX_REPAIRS):
        if not issues:
            break
        for line in issues[:6]:
            log(f"[pack]   {line[:180]}")
        try:
            again = llm(shapes.repair_prompt(raw, issues) + f"\n\nThe answer's JSON shape: {SHAPE_OF_ANSWER}", SYSTEM)
        except Exception as exc:  # noqa: BLE001 - the best draft so far stands
            log(f"[pack] repair {i + 1} failed ({type(exc).__name__}: {str(exc)[:100]})")
            break
        filled2, issues2 = faults(again)
        log(f"[pack] repair {i + 1}: {len(issues2)} fault(s)")
        rounds.append(len(issues2))
        repeated = set(issues2) == set(issues)
        if len(issues2) <= len(issues):
            raw, filled, issues = again, filled2, issues2
        if repeated:
            # ce-library measured this (#33): 4 of 4 second repairs returned exactly the faults of the first.
            # Asking the same model the same thing again only pays for the same answer.
            log(f"[pack] repair {i + 1} left the same {len(issues2)} fault(s); stopping")
            break
    lesson = finish(filled, raw, language)
    lesson["geometry_check"] = {"faults_by_round": rounds, "faults_left": issues, "unfilled_gaps": shapes.unfilled(lesson)}
    return lesson


def finish(filled: dict, raw: dict, language: str = "en-US") -> dict:
    """The checked lesson in the contract every lesson is rendered from (``writer.discipline``)."""
    chapters = filled.get("chapters") or []
    framework = {"id": "pack", "name": "teaching pack", "voice": "",
                 "stages": [{"role": str(c.get("role") or "explain"), "title": str(c.get("title") or "Part"),
                             "job": str(c.get("learning_goal") or "")} for c in chapters] or
                           [{"role": "explain", "title": "Part", "job": ""}]}
    kinds = [str((b.get("quiz") or {}).get("kind") or "") for c in chapters for b in c.get("beats") or []]
    brief = {"topic": filled.get("title") or "", "language": language}
    lesson = writer.discipline(copy.deepcopy(filled), brief, framework)
    beats = [b for c in lesson["chapters"] for b in c["beats"]]
    if len(beats) == len(kinds):
        for b, kind in zip(beats, kinds):
            if b.get("quiz") and kind:
                b["quiz"]["kind"] = kind
    for b in beats:                       # the beat's own pause length, kept from the model within 3..8 s
        if b.get("quiz") and b["thinking_pause_seconds"] < 5:
            b["thinking_pause_seconds"] = 6.0
    lesson["shapes"] = filled.get("shapes") or {}
    lesson["generated_by"] = GENERATED_BY
    lesson["continuity"] = writer.continuity(lesson)
    Lesson.model_validate(lesson)
    return lesson


def lesson_for(brief: dict, llm, log=print) -> dict:
    """``service``'s way in: a brief ``{"mode": "pack", "pack": <the pack's text>, "unit": 3}``."""
    found = {u["number"]: u for u in units(str(brief.get("pack") or ""))}
    number = int(brief.get("unit") or 0)
    if number not in found:
        raise ValueError(f"the pack has no unit {number} (it has {sorted(found) or 'none'})")
    if llm is None:
        raise ValueError("a pack lesson needs the writer model: no key is configured")
    return write_unit(found[number], rules(str(brief["pack"])), llm, brief.get("language") or "en-US", log=log)


def brief_for(text: str, number: int, language: str = "en-US") -> dict:
    found = {u["number"]: u for u in units(text)}
    if number not in found:
        raise ValueError(f"the pack has no unit {number} (it has {sorted(found) or 'none'})")
    return {"mode": "pack", "pack": text, "unit": number, "topic": found[number]["title"], "language": language}


def report(lesson: dict) -> str:
    check = lesson.get("geometry_check") or {}
    rounds = check.get("faults_by_round") or []
    words = sum(len(b["narration"].split()) for c in lesson["chapters"] for b in c["beats"])
    return (f"{lesson['title']}: {len(lesson['chapters'])} chapters, "
            f"{sum(len(c['beats']) for c in lesson['chapters'])} beats, {words} words; faults by round "
            f"{' -> '.join(map(str, rounds))}" + (f"; LEFT: {json.dumps(check.get('faults_left'))[:400]}"
                                                  if check.get("faults_left") else ""))
