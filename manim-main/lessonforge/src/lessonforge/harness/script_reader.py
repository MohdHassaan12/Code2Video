"""Reading a script someone pasted, whatever shape it has.

People do not paste narration. On 2026-10-09 a tester pasted a production document: a
synopsis, character sheets, a "look and feel" paragraph, a table of thirteen scenes
(Scene | Time | On-screen visual | Voiceover, one cell per line as a document copies
it) and a teacher's answer key. All 2012 words were narrated: the lesson read out camera
directions, time codes and the answers to its own closing questions, and 21 of 32
reviewed frames did not match the voice. ``scripted._script_table`` now recognises that
exact table by its header. This module is for every other shape (a screenplay with
"VO:" lines, "Scene 3 / Visual / Narration" blocks, notes mixed into prose) that no
fixed rule will list in advance.

The split of work is the harness's usual one, and here it matters more than usual
because **the words are the author's**:

* a model LABELS LINES. It is shown the document with every line numbered and says, for
  each scene, which lines are spoken, which describe the picture and which give the
  time; and which lines are notes for the makers, or for the teacher only. It never
  writes a word of the script;
* code SLICES and CHECKS. The spoken script is cut from the author's own lines by
  number, so it is theirs word for word by construction. A line the model did not label
  is never spoken. An answer that labels nearly everything "spoken" in a document that
  visibly has structure, or labels nothing, is refused and the caller falls back to what
  it did before.

The result is a script in the plain form ``scripted.parse_script`` already reads
(``# heading``, ``[a direction for the picture]``, paragraphs), the author's notes for
the screen designer, the questions without their answers, and a report of what will and
will not be spoken, to show the author before anything is spent.
"""
from __future__ import annotations

import os
import re
from typing import Any, Callable
from .. import knobs

LLM = Callable[[str, str], Any]
MAX_LINES = 500
MAX_LINE_CHARS = 1600
READER_MODELS_DEFAULT = "google/gemini-3.5-flash-lite,google/gemini-2.5-flash,openai/gpt-5.4-nano"

#: Signs that a pasted text is more than narration. Cheap, so a model is asked only when one is there.
_SIGNS = (
    re.compile(r"^\s*(scene|shot|slide|frame)\s*\d*\s*[:.\-–|]?\s*$", re.I),
    re.compile(r"^\s*(on[- ]?screen( visual| text)?|visuals?|video|picture|animation|b-?roll|camera)\s*[:|]", re.I),
    re.compile(r"^\s*(voice[- ]?over|v\.?o\.?|narration|narrator|audio|dialogue)\b[^.?!]{0,24}[:|(]", re.I),
    re.compile(r"^\s*(on[- ]?screen visual|voiceover|voice[- ]?over|narration|time|duration)\s*(\([^)]*\))?\s*$", re.I),
    re.compile(r"^\s*\d{1,2}:\d{2}\s*[-–—to]+\s*\d{1,2}:\d{2}\s*$"),
    re.compile(r"\b(answer|ans|solution)\s*[:\-]", re.I),
    re.compile(r"^\s*(characters?|look and feel|style|music|sfx|sound effects?|notes? for|teacher'?s? (notes?|key))\b.{0,40}:", re.I),
    re.compile(r"\|.+\|"),
)

_BRACKETS = re.compile(r"[\[\]]")       # a direction is written in brackets, so it may not contain any

SYSTEM = """You sort the lines of a document that someone pasted as the script for a narrated teaching video.
The document may hold much more than the words to be spoken: a synopsis, character and style notes, a table of
scenes with a column for what is seen and a column for what is said, time codes, music notes, questions with
answers meant only for the teacher. A table copied from a document arrives with ONE CELL PER LINE.

You are given every line with its number. You never rewrite anything: you answer with line numbers only.
Return ONLY JSON:
{"kind": "table | screenplay | blocks | prose with notes | plain narration",
 "title": "the lesson's title if the document gives one, else empty",
 "scenes": [{"name": "the scene's own name or number as written, short",
             "time": [line numbers that only give a time or duration],
             "picture": [line numbers that describe what is SEEN: visuals, camera, on-screen text, animation],
             "spoken": [line numbers whose words are SPOKEN by the narrator or a character]}],
 "notes": [line numbers for the people making the video: synopsis, characters, look and feel, music, production notes],
 "teacher": [line numbers meant for the teacher only: answer keys, marking notes, questions that carry their answers],
 "skip": [line numbers that are only table headers, column names, rules or numbering],
 "questions": [{"line": n, "answer_starts_at": "the exact words where the answer begins on that line, or empty"}]}

Rules:
- Every line number appears in exactly one place. When in doubt whether a line is spoken, it is NOT spoken.
- "spoken" is only what a voice says. A description of a sound, a camera move, a banner or a caption is "picture",
  even when it quotes words that appear on screen.
- Keep scenes in the document's order. Prose with no scenes is one scene.
- A line of questions for the learner that also gives the answers is "teacher", and is listed in "questions"."""


def reader_models() -> list[str]:
    raw = knobs.get("HARNESS_READER_MODELS", READER_MODELS_DEFAULT)
    return [m.strip() for m in raw.split(",") if m.strip()]


def default_llm() -> LLM | None:
    """A small, fast model through OpenRouter, metered as "reader". None without a key."""
    key = (os.getenv("OPENROUTER_API_KEY") or "").strip()
    if not key:
        return None
    from ..engine import llm as engine_llm  # noqa: PLC0415

    def call(prompt: str, system: str):
        text = engine_llm.call_openrouter(key, prompt, system, temperature=0.0, models=reader_models(),
                                          max_tokens=None, json_object=True, note="reader", timeout=120.0)
        return engine_llm.loads_json_lenient(text)
    return call


def looks_structured(text: str) -> int:
    """How many lines carry a sign of structure. 0 means plain narration: no model is asked."""
    return sum(1 for line in str(text).splitlines() if any(sign.search(line) for sign in _SIGNS))


def _numbers(value, limit: int) -> list[int]:
    out = []
    for item in value if isinstance(value, list) else []:
        try:
            n = int(item)
        except (TypeError, ValueError):
            continue
        if 1 <= n <= limit and n not in out:
            out.append(n)
    return out


def _words(text: str) -> int:
    return len(str(text).split())


def read(text: str, llm: LLM, log=print) -> dict | None:
    """Sort a pasted document into what is spoken, what is seen and what is neither.

    Returns ``{"script", "notes", "teacher", "questions", "title", "report"}`` or None when
    the document is too long, the model's answer cannot be used, or nothing was gained.
    None always means: do what you did before.
    """
    lines = [line.rstrip() for line in str(text).replace("\r\n", "\n").split("\n")]
    kept = [(i, line) for i, line in enumerate(lines, 1) if line.strip()]
    if not kept or len(kept) > MAX_LINES:
        return None
    listing = "\n".join(f"{n}: {line[:MAX_LINE_CHARS]}" for n, line in kept)
    try:
        raw = llm(f"THE DOCUMENT, {len(kept)} lines:\n{listing}", SYSTEM)
    except Exception as exc:  # noqa: BLE001 - reading is an improvement, never a requirement
        log(f"[reader] not used: {type(exc).__name__}: {str(exc)[:120]}")
        return None
    if not isinstance(raw, dict) or not isinstance(raw.get("scenes"), list):
        log("[reader] not used: the answer had no scenes")
        return None
    by_number, last = dict(kept), len(lines)
    role: dict[int, str] = {}

    def claim(numbers: list[int], name: str) -> list[int]:
        """First label wins: a line the model put in two places is spoken only if it said so first."""
        mine = [n for n in numbers if n in by_number and n not in role]
        for n in mine:
            role[n] = name
        return mine

    # The answer key is claimed before anything else: a line listed both as spoken and as a
    # question with its answer must never be narrated.
    teacher = claim(_numbers(raw.get("teacher"), last), "teacher")
    cuts = {}
    for q in raw.get("questions") if isinstance(raw.get("questions"), list) else []:
        if isinstance(q, dict) and q.get("line") in by_number:
            n = int(q["line"])
            if role.get(n) in (None, "teacher"):
                role[n] = "teacher"
                teacher.append(n) if n not in teacher else None
                cuts[n] = str(q.get("answer_starts_at") or "").strip()
    scenes = []
    for k, scene in enumerate(s for s in raw["scenes"] if isinstance(s, dict)):
        spoken = claim(_numbers(scene.get("spoken"), last), "spoken")
        picture = claim(_numbers(scene.get("picture"), last), "picture")
        claim(_numbers(scene.get("time"), last), "time")
        if spoken:
            name = re.sub(r"\s+", " ", str(scene.get("name") or "")).strip()[:60]
            scenes.append({"name": name if name and not name.isdigit() else f"Scene {name or k + 1}",
                           "spoken": sorted(spoken), "picture": sorted(picture)})
    notes = claim(_numbers(raw.get("notes"), last), "notes")
    claim(_numbers(raw.get("skip"), last), "skip")
    unlabelled = [n for n, _ in kept if n not in role]
    for n in unlabelled:                               # never spoken by default
        role[n] = "notes"
    notes = sorted(notes + unlabelled)

    total = sum(_words(line) for _, line in kept)
    said = sum(_words(by_number[n]) for s in scenes for n in s["spoken"])
    signs = looks_structured(text)
    if not scenes or said < 20:
        log("[reader] not used: it found almost nothing to speak")
        return None
    if signs >= 3 and said > 0.97 * total:
        log("[reader] not used: it called nearly every line spoken in a document that has structure")
        return None

    parts = []
    for scene in scenes:
        block = [f"# {scene['name']}"]
        block += ["[" + _BRACKETS.sub("", by_number[n]).strip() + "]" for n in scene["picture"]]
        block += ["", "\n\n".join(by_number[n].strip() for n in scene["spoken"])]
        parts.append("\n".join(block))
    questions = []
    for n in sorted(set(teacher)):
        line = by_number[n].strip()
        marker = cuts.get(n) or ""
        at = line.find(marker) if marker else -1
        if at < 0:
            found = re.search(r"\b(answer|ans|solution)\s*[:\-]", line, re.I)
            at = found.start() if found else -1
        if at > 0 and "?" in line[:at] or (at > 0 and n in cuts):
            questions.append(line[:at].strip(" -–:;"))
    report = {"kind": str(raw.get("kind") or "")[:40], "scenes": len(scenes), "words": total, "spoken_words": said,
              "picture_words": sum(_words(by_number[n]) for n, r in role.items() if r == "picture"),
              "notes_words": sum(_words(by_number[n]) for n in notes),
              "teacher_words": sum(_words(by_number[n]) for n in set(teacher)), "unlabelled_lines": len(unlabelled)}
    log(f"[reader] {report['kind'] or 'a document'}: {len(scenes)} scene(s); {said} of {total} words are spoken; "
        f"{report['picture_words']} describe the picture; {report['notes_words']} are notes; {report['teacher_words']} are for the teacher")
    return {"script": "\n\n".join(parts), "title": re.sub(r"\s+", " ", str(raw.get("title") or "")).strip()[:90],
            "notes": "\n".join(by_number[n].strip() for n in notes), "teacher": "\n".join(by_number[n].strip() for n in sorted(set(teacher))),
            "questions": questions, "report": report}
