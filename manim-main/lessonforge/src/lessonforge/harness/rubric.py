"""A weighted teaching rubric, scored with evidence: does the lesson teach the way a concept-first demonstrator does?

From the owner's teaching notes of 2026-10-20 (a "Concept-First Demonstrative Teacher" and its evaluator): eight
criteria with weights that add to 100, evidence for every high score, a defect and a repair for every low one, and
"do not reward headings". The reviewer's four 0-4 scores (``critic.RUBRIC``) say how good a script is; they do not say
WHERE it fails as a lesson or what to change, and a judge can give them without pointing at anything.

The house pattern (``coherence.py``, ``questions.LISTEN``): the judge QUOTES before it scores, and code decides.

* A score of 3 or 4 counts only when at least one of its evidence quotes is really in the narration of the beat it
  names. Otherwise the score is capped at 2: a high score with nothing to point at is the reward for headings the
  notes warn about. Only narration is searched, never titles or screen lines.
* A score of 0 or 1 becomes a ``major`` finding (prefix ``teach:``) when its defect quote is really in the beat it
  names, so the reviser rewrites that beat like any other finding; a 2 becomes a ``minor`` one. A defect code cannot
  find is reported in the rubric and acted on by nothing: in doubt, no rewrite is sent after a fault that is not there.
* The weighted total (0 to 100) is a measurement for the log and the audit; nothing is refused on it.

Off unless ``HARNESS_TEACHING_RUBRIC=1`` (one extra small call per review round). Like every new gate it is read on
real lessons for what it breaks before it is on for everyone.
"""
from __future__ import annotations

import re
from typing import Any, Callable

from .. import knobs
from . import writer

LLM = Callable[[str, str], Any]
VERSION = 2

#: (key, weight, what a 4 looks like). Weights add to 100.
CRITERIA: tuple[tuple[str, int, str], ...] = (
    ("conceptual_clarity", 20, "the core idea is said plainly and the learner is shown WHY it must be so, not only told"),
    ("sequencing", 15, "a question or puzzle first, then a prediction, then what happens, then the name or rule, then "
                       "using it on a new case, then a short look back; the idea comes before its name"),
    ("prediction_and_questioning", 15, "the learner is asked to commit to a guess before it is shown; the questions "
                                       "make them think, are few, and each is answered later"),
    ("demonstrations_and_visuals", 15, "something concrete is shown happening and the words follow what is shown; the "
                                       "picture carries the argument, not decoration"),
    ("correctness", 15, "every fact, number and unit is right and every condition the claim needs is stated"),
    ("worked_examples_and_transfer", 10, "one case is worked through step by step, and the idea is then used on a case "
                                         "that comes out differently"),
    ("misconceptions", 5, "the common wrong idea is said the way a learner would say it and shown to fail"),
    ("focus_and_takeaway", 5, "one idea from start to end, said again near the end in new words, ending on a line the "
                              "learner can carry away"),
)
WEIGHTS = {key: weight for key, weight, _ in CRITERIA}
assert sum(WEIGHTS.values()) == 100

SYSTEM = """You evaluate the script of a narrated lesson for school students as a strict teacher-trainer. Score how it
TEACHES, not how it is laid out: a chapter title, a heading or a stage name earns nothing. Return ONLY JSON.

For each criterion give a score from 0 to 4:
  4 = clearly and fully done, 3 = done with a small gap, 2 = partly done, 1 = barely there, 0 = absent or wrong.
QUOTE before you score. "evidence" is one or two quotes, each words copied EXACTLY from the narration (SAY) of the beat
you name, at least six words, that show the criterion being met. A score of 3 or 4 without such a quote is not allowed.
For a score of 2 or less also give "defect": the beat where it goes wrong, words copied EXACTLY from its narration, and
what is wrong, and "repair": one concrete change to that beat's narration, in the lesson's own language. Judge by what
is SAID and SHOWN; a criterion that is promised but not done scores low.
The lesson stops for a question only where its plan says (about once a minute), and its last task is left for the
learner to try after the video on purpose: never mark it down for an unanswered try-it task, and never repair a fault
by adding a question. A repair says the missing thing, it does not ask it.

CRITERIA:
{criteria}

JSON: {{"criteria": [{{"key": str, "score": 0-4, "evidence": [{{"beat": "id", "quote": str}}],
"defect": {{"beat": "id", "quote": str, "what": str}} or null, "repair": str}}]}}"""


def enabled() -> bool:
    return knobs.get("HARNESS_TEACHING_RUBRIC", "0") == "1"


def system() -> str:
    return SYSTEM.format(criteria="\n".join(f"- {key} (weight {weight}): {good}" for key, weight, good in CRITERIA))


def _narration(lesson: dict) -> dict[str, str]:
    return {str(b.get("id")): str(b.get("narration") or "") for c in lesson.get("chapters") or [] for b in c.get("beats") or []}


def _quoted(quote, narration: str, least: int = 4) -> bool:
    """The quote is really in these words (normalised) and long enough to mean something."""
    quote = writer._norm(str(quote or ""))
    return len(quote.split()) >= least and quote in writer._norm(narration)


def _beat_of(beat, quote, said: dict[str, str]) -> str:
    """The beat a quote is in: the one named when it holds the quote, else the one beat that does; '' when none."""
    beat = str(beat or "").strip()
    if beat in said and _quoted(quote, said[beat]):
        return beat
    holding = [b for b, words in said.items() if _quoted(quote, words)]
    return holding[0] if len(holding) == 1 else ""


def _score(value) -> int | None:
    try:
        n = int(round(float(value)))
    except (TypeError, ValueError):
        return None
    return n if 0 <= n <= 4 else None


def _pictures(lesson: dict) -> str:
    """What each beat SHOWS, beyond its lines: the figure's kind or the scene's sentence."""
    out = []
    for chapter in lesson.get("chapters") or []:
        for beat in chapter.get("beats") or []:
            figure = beat.get("figure") if isinstance(beat.get("figure"), dict) else None
            if figure:
                what = figure.get("describe") or figure.get("ask") or figure.get("kind")
                out.append(f"[beat {beat.get('id')}] picture: {str(what)[:160]}")
    return "\n".join(out) or "(no pictures listed)"


def assess(lesson: dict, llm: LLM, script: str, log=print) -> dict:
    """The rubric for this lesson: per criterion its score (as counted), the evidence code found, and the findings."""
    said = _narration(lesson)
    empty = {"version": VERSION, "total": None, "criteria": {}, "findings": []}
    if llm is None or not said:
        return empty
    try:
        raw = llm(f"{script}\n\nWHAT EACH BEAT SHOWS:\n{_pictures(lesson)}", system()) or {}
    except Exception as exc:                                  # advisory: a failed look leaves the review as it was
        log(f"[rubric] the look failed ({exc}); no rubric this round")
        return empty
    rows = {}
    for item in (raw.get("criteria") or []) if isinstance(raw, dict) else []:
        if isinstance(item, dict) and item.get("key") in WEIGHTS and item["key"] not in rows:
            rows[item["key"]] = item
    criteria, findings, total, answered = {}, [], 0.0, 0
    for key, weight, _ in CRITERIA:
        item = rows.get(key)
        given = _score(item.get("score")) if item else None
        if given is None:
            criteria[key] = {"weight": weight, "score": None, "given": None, "evidence": [], "defect": None, "repair": ""}
            continue
        evidence = []
        for ev in item.get("evidence") or []:
            if isinstance(ev, dict):
                beat = _beat_of(ev.get("beat"), ev.get("quote"), said)
                if beat and _quoted(ev.get("quote"), said[beat], least=6):
                    evidence.append({"beat": beat, "quote": str(ev.get("quote"))[:200]})
        score = given if given <= 2 or evidence else 2           # a high score must point at something said
        defect = item.get("defect") if isinstance(item.get("defect"), dict) else None
        found = None
        if defect and score <= 2:
            beat = _beat_of(defect.get("beat"), defect.get("quote"), said)
            if beat:
                found = {"beat": beat, "quote": str(defect.get("quote"))[:200], "what": str(defect.get("what") or "")[:240]}
        repair = str(item.get("repair") or "")[:300]
        criteria[key] = {"weight": weight, "score": score, "given": given, "evidence": evidence, "defect": found,
                         "repair": repair}
        total += weight * score / 4
        answered += weight
        if found and repair:
            findings.append({"severity": "major" if score <= 1 else "minor", "beat": found["beat"], "resolved": False,
                             "what": f"teach: {key.replace('_', ' ')} scored {score} of 4: {found['what']} "
                                     f"(“{found['quote'][:80]}”)",
                             "fix": repair})
    capped = [k for k, c in criteria.items() if c["score"] is not None and c["given"] != c["score"]]
    result = {"version": VERSION, "total": round(100 * total / answered, 1) if answered else None,
              "answered": answered, "criteria": criteria, "findings": findings, "capped": capped}
    if answered:
        low = [f"{k} {c['score']}" for k, c in criteria.items() if c["score"] is not None and c["score"] <= 2]
        log(f"[rubric] teaching {result['total']} of 100" + (f"; low: {', '.join(low)}" if low else "")
            + (f"; {len(capped)} high score(s) with no quote found, counted as 2" if capped else ""))
    return result
