"""Does the lesson hold together as ONE explanation? Three things a listener notices, asked of a judge and checked by code.

The owner's complaint since 2026-10-07 has been that the narration is "poor and lacks coherence", and the open research
question RQ-04 asks for "each block has one clear explanatory purpose and a connection to its neighbors". The writer
already carries a ledger between chapters and the critic already cuts repeats (``critic.repetition_gate``). What was
left to the reviewer's general rubric, as advice only ("terms introduced before use; the opening question is
answered"), is checked here, one decision per item:

* **Seams.** Each chapter after the first must pick up from where the one before ended. ``writer.continuity`` counts
  cold opens with a regex and only warns; a chapter that jumps to a new thing without a word of connection is not
  caught by any regex.
* **Terms.** A term of the lesson's glossary is used before the beat that says what it means.
* **The opening question.** The question the lesson opens with is never answered by name.

The pattern is the house one (``questions.LISTEN``, ``vision_review.ASSESS``): the judge QUOTES before it decides, and
code keeps a finding only when the quote is really in the beat it names. In doubt, nothing is reported: a false finding
sends a paid rewrite after a fault that is not there. Findings are ``major`` with the prefix ``flow:``, so the
reviser rewrites them like any other reviewer finding (``critic.verify``).

Off unless ``HARNESS_COHERENCE=1`` (one extra small call per review round). Like every new gate it must be read on real
lessons for what it breaks before it is switched on for everyone (CLAUDE.md: "A new critic gate must be read on a real
run for what IT breaks").
"""
from __future__ import annotations

import re
from typing import Any, Callable

from .. import knobs
from . import writer

LLM = Callable[[str, str], Any]
VERSION = 1
MAX_TERMS = 12

SYSTEM = """You read the script of a narrated lesson for school students the way a listener hears it, from start to end,
and answer three narrow questions about whether it holds together. Return ONLY JSON. QUOTE before you decide: every
quote is words copied EXACTLY from the beat you name (at least four words). When in doubt, answer the way that reports
no problem.

1. SEAMS. For every chapter after the first: copy the first words of its first beat ("opening"), then copy the words
   near the END of the chapter before it that this opening picks up from ("picks_up"; "" if it picks up nothing), then
   decide "verdict":
     "continues" — it carries on from what came before: it answers the question the last chapter left, uses what was
                   just found, or names the next step of the same idea. A short link is enough.
     "restarts"  — it opens as if the lesson were starting again: greets, re-introduces the topic, the example or the
                   viewer ("Today we will learn...", "Let us understand X").
     "jumps"     — it starts on something new with no word tying it to what came just before.
2. TERMS. For each term listed: the beat where the script first says what the term MEANS ("explained_in", a beat id),
   and those words ("quote"). "known" if a listener at this level already knows the word and the script never needs to
   explain it; "none" if it is needed and never explained.
3. OPENING. For the opening question given: the beat whose words answer it ("answered_in", a beat id, or "none") and
   those words ("quote"); if "none", the beat where the answer belongs ("belongs_in").

JSON: {"seams": [{"chapter": 2, "opening": str, "picks_up": str, "verdict": "continues|restarts|jumps"}],
"terms": [{"term": str, "explained_in": "beat id | known | none", "quote": str}],
"opening": {"answered_in": "beat id | none", "quote": str, "belongs_in": "beat id"}}"""


def enabled() -> bool:
    return knobs.get("HARNESS_COHERENCE", "0") == "1"


def _beats(lesson: dict) -> list[tuple[dict, dict]]:
    return [(c, b) for c in lesson.get("chapters") or [] for b in c.get("beats") or []]


def _quoted(quote, narration: str) -> bool:
    """The quote is really in these words (normalised), and long enough to mean something."""
    quote = writer._norm(str(quote or ""))
    return len(quote.split()) >= 3 and quote in writer._norm(narration)


def _uses(term: str, narration: str) -> bool:
    words = writer._norm(term)
    return bool(words) and re.search(rf"\b{re.escape(words)}", writer._norm(narration)) is not None


def opening_question(lesson: dict) -> str:
    """The question the lesson opens with: the teaching card's, else the first question chapter 1 asks."""
    card = lesson.get("card") if isinstance(lesson.get("card"), dict) else {}
    asked = (card.get("opening_question") or {}) if isinstance(card.get("opening_question"), dict) else {}
    if str(asked.get("question") or "").strip():
        return str(asked["question"]).strip()
    chapters = lesson.get("chapters") or []
    for beat in (chapters[0].get("beats") or []) if chapters else []:
        for sentence in re.split(r"(?<=[.!?।])\s+", str(beat.get("narration") or "")):
            if sentence.strip().endswith("?"):
                return sentence.strip()
    return ""


def terms(lesson: dict) -> list[str]:
    """The lesson's own glossary terms that its narration actually uses."""
    spoken = " ".join(str(b.get("narration") or "") for _, b in _beats(lesson))
    out = []
    for entry in lesson.get("glossary") or []:
        term = str((entry.get("term") if isinstance(entry, dict) else entry) or "").strip()
        if term and term.lower() not in {t.lower() for t in out} and _uses(term, spoken):
            out.append(term)
    return out[:MAX_TERMS]


def _script(lesson: dict, terms_: list[str], question: str) -> str:
    lines = [f"LESSON: {lesson.get('title', '')}", f"AUDIENCE: {(lesson.get('brief') or {}).get('audience', '')}"]
    for chapter in lesson.get("chapters") or []:
        lines.append(f"\n## Chapter {chapter['id']}: {chapter.get('title', '')}")
        lines += [f"[beat {b['id']}] {b.get('narration', '')}" for b in chapter.get("beats") or []]
    lines.append("\nTERMS: " + ("; ".join(terms_) if terms_ else "(none)"))
    lines.append(f"OPENING QUESTION: {question or '(none)'}")
    return "\n".join(lines)


def findings(lesson: dict, llm: LLM, log=print) -> list[dict]:
    """The flow findings code could confirm from the judge's quotes; [] when the judge fails or finds nothing."""
    beats = _beats(lesson)
    chapters = [c for c in lesson.get("chapters") or [] if c.get("beats")]
    if len(chapters) < 2 or llm is None:
        return []
    by_id = {b["id"]: b for _, b in beats}
    order = {b["id"]: i for i, (_, b) in enumerate(beats)}
    terms_, question = terms(lesson), opening_question(lesson)
    try:
        raw = llm(_script(lesson, terms_, question), SYSTEM) or {}
    except Exception as exc:  # noqa: BLE001 - a look that fails reports nothing; the review goes on
        log(f"[flow] the look failed ({type(exc).__name__}: {str(exc)[:100]}): no flow findings")
        return []
    from .critic import beat_id   # noqa: PLC0415 - critic imports this module
    out: list[dict] = []

    # 1. Seams: a chapter that restarts or jumps, confirmed by its own opening words.
    index = {str(c["id"]): k for k, c in enumerate(chapters)}
    for seam in raw.get("seams") or []:
        if not isinstance(seam, dict) or seam.get("verdict") not in ("restarts", "jumps"):
            continue
        k = index.get(str(seam.get("chapter")).strip())
        if not k:                                    # unknown chapter, or the first (nothing comes before it)
            continue
        first = chapters[k]["beats"][0]
        if not _quoted(seam.get("opening"), " ".join(first["narration"].split()[:40])):
            continue
        before = re.split(r"(?<=[.!?।])\s+", chapters[k - 1]["beats"][-1]["narration"].strip())[-1]
        how = "starts the lesson again" if seam["verdict"] == "restarts" else "jumps to something new"
        out.append({"severity": "major", "beat": first["id"], "resolved": False,
                    "what": f"flow: chapter {chapters[k]['id']} {how} instead of picking up where chapter "
                            f"{chapters[k - 1]['id']} ended (“{before[:90]}”)",
                    "fix": f"open with one short sentence or clause that picks up from the end of chapter {chapters[k - 1]['id']}"
                           " (its question, its result, or the next step of the same idea); never re-introduce the topic, "
                           "the example or the viewer. Keep everything else the beat says"})

    # 2. Terms: used before the beat that explains them. The first use is found by code, not asked.
    asked = {t.lower(): t for t in terms_}
    for item in raw.get("terms") or []:
        if not isinstance(item, dict):
            continue
        term = asked.get(str(item.get("term") or "").strip().lower())
        where = str(item.get("explained_in") or "").strip().lower()
        if not term or where == "known":
            continue
        first = next((b for _, b in beats if _uses(term, b["narration"])), None)
        if first is None:
            continue
        if where == "none":
            out.append({"severity": "major", "beat": first["id"], "resolved": False,
                        "what": f"flow: “{term}” is used but the lesson never says what it means",
                        "fix": f"where “{term}” first comes, say in a few plain words what it means"})
            continue
        explained = beat_id(item.get("explained_in"), by_id)
        if explained not in by_id or not _quoted(item.get("quote"), by_id[explained]["narration"]):
            continue                                  # an unchecked claim reports nothing
        if order[explained] > order[first["id"]]:
            out.append({"severity": "major", "beat": first["id"], "resolved": False,
                        "what": f"flow: “{term}” is used here before the lesson says what it means (beat {explained})",
                        "fix": f"say in a few plain words what “{term}” means here, or use plain words until beat {explained}"})

    # 3. The opening question, answered by name somewhere after it is asked.
    opening = raw.get("opening") if isinstance(raw.get("opening"), dict) else {}
    if question and str(opening.get("answered_in") or "").strip().lower() == "none":
        belongs = beat_id(opening.get("belongs_in"), by_id)
        if belongs not in by_id or by_id[belongs] in chapters[0]["beats"]:
            belongs = chapters[-2]["beats"][-1]["id"] if len(chapters) > 1 else chapters[-1]["beats"][-1]["id"]
        out.append({"severity": "major", "beat": belongs, "resolved": False,
                    "what": f"flow: the lesson never answers the question it opened with (“{question[:100]}”)",
                    "fix": "answer that question here by name, in one plain sentence that uses what the lesson has shown"})

    seams = sum(1 for f in out if "chapter" in f["what"] and "picking up" in f["what"])
    log(f"[flow] {len(chapters) - 1} seam(s), {len(terms_)} term(s), opening question "
        f"{'given' if question else 'none'}: {len(out)} finding(s) ({seams} seam)")
    return out
