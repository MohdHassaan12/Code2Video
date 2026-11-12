"""A script the requester wrote → a lesson contract.

The second way into the harness. ``writer.py`` starts from an INTENT — a brief filled
by the intake — and has a model write the words. Here the words already exist: someone
pasted the narration they want spoken. So the split of work moves:

* **the words are the author's** and are spoken as written. Code only makes them
  speakable (digits and symbols become words, as for any script) and takes out what
  was never meant for the voice: headings, ``[directions]``, markdown, speaker labels;
* **code owns the structure**: headings become chapters, paragraphs become beats, a
  long paragraph is cut at sentence ends, ids are assigned here;
* **a model designs only the screen**: for each beat, what is drawn and what moves
  while those words are spoken (steps, a figure, a question card where the script
  itself asks one). Its answer goes through ``writer.discipline`` like any script, so
  every step is anchored to words that are really in the narration.

A script is often a production TABLE pasted from a document (Scene | Time | On-screen
visual | Voiceover), with character notes above it and a teacher's answer key below. Then
only the Voiceover column is spoken; the visual column directs the picture for its row and
everything outside the table is a note for the director (``_script_table``). The first real
script a user pasted had this shape, and every cell of it was read aloud.

Any OTHER structured document (a screenplay with "VO:" lines, notes mixed into prose) is
shown to a small reader model that only LABELS LINES (``script_reader``); the spoken script
is then cut from the author's own lines. Its reading is used only when it speaks clearly
less than the plain reading would, and it is cached by the document, so the read-back and
the job that follows it read the document the same way and pay for it once.

``preview`` is the read-back before anything is spent: no model call for narration or a
table; one small, cached reader call (about a third of a cent) for a structured document.
With no model configured, ``plain_lesson`` narrates the script over plain text and
says so — the words are real, the screen is a placeholder.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import os
import re
from pathlib import Path

from .. import knobs
from .. import paths
from ..longform.contract import Lesson, split_sentences
from ..spend import BudgetExceeded
from . import critic, diagrams, intake, library, tryit, writer

MIN_WORDS = 20
MAX_WORDS = 3500                 # about 28 minutes at the measured pace
MAX_CHARS = 60_000
MAX_BEAT_WORDS = 75              # the writer's own ceiling for one beat
SMALL_PARAGRAPH = 18             # a paragraph shorter than this joins the next one
MAX_CHAPTER_BEATS = 8            # chapters above ~6 beats have not been rendered by GuidedChapter
EVEN_CHAPTER_BEATS = 5           # when nobody chose the parts: about a minute each
FULL_CONTEXT_WORDS = 1500        # above this the director gets a map of the script, not all of it
READER_MIN_SIGNS = 3             # lines that look like structure before the reader model is asked
READER_GAIN = 0.9                # its reading is used only when it speaks less than this share of the plain one
LANGUAGE_CODES = tuple(o["value"] for o in intake.LANGUAGES)
#: Not a teaching framework: one stage of no particular role, so ``writer.discipline`` caps nothing.
#: (``writer.continuity`` knows the id "script": a pasted script is not asked for a running example.)
FRAMEWORK = {"id": "script", "name": "The author's own script", "voice": "",
             "stages": [{"role": "script", "title": "Part", "job": ""}]}
GENERATED_BY = "script"
NO_MODEL = "script (no model configured — the words are yours; the screen shows plain text, not a designed picture)"

_NUMBER = r"(?:\d{1,3}|[ivxlc]{1,6}|one|two|three|four|five|six|seven|eight|nine|ten)"
_HEADING_MD = re.compile(r"^(#{1,6})\s+(.+?)\s*#*$")
# "Scene 3", "Part 2: The idea", "Scene 4 (0:30–2:00)": a time in brackets after it is not part of the name.
_HEADING_WORD = re.compile(rf"^(?:chapter|part|section|scene|unit)\s+{_NUMBER}\s*(?:[(\[][^)\]]{{0,24}}[)\]])?\s*(?:[:.\-–—]\s*(.*))?$", re.I)
_TITLE_LINE = re.compile(r"^title\s*[:\-–—]\s*(.+)$", re.I)
_SPEAKER = re.compile(r"^(?:narrator|narration|teacher|voice[- ]?over|v\.?o\.?|host|speaker)\s*(?:\([^)]{0,30}\))?\s*:\s*", re.I)
# The same label in the middle of a cell ("… likha." Narrator: Is chhote …): the label goes, the words stay.
_SPEAKER_INSIDE = re.compile(r"(?<=[.!?…\"”’)]\s)(?:narrator|narration|voice[- ]?over|v\.?o\.?)\s*:\s*", re.I)
# A labelled line that is for the people making the video, never for the voice. The first group may carry a
# few words before its colon ("Characters (flat 2D, consistent across scenes): …"); the second are also
# ordinary sentence openers, so they count only when the colon follows at once ("Answer: 49").
_DIRECTION_LINE = re.compile(
    r"^(?:(?:visuals?|on[- ]?screen(?: visuals?| text| action)?|text on screen|animation|graphics?|b-?roll|camera|sfx|"
    r"sound effects?|scene description|characters?|look and feel)\b[^:\n]{0,60}"
    r"|(?:screen|show|picture|shot|music|setting|style|tone|mood|props|transition|time|timing|timestamp|duration|"
    r"answers?|notes))\s*:\s*(.+)$", re.I)
_BULLET = re.compile(r"^(?:[-–—•*]\s+|\d{1,2}[.)]\s+)")
# A direction in square brackets, on one line. Long on purpose: a production script's visual cell runs to
# several hundred characters, and one that did not match was read aloud.
_BRACKET = re.compile(r"\[([^\]\n]{0,1500})\]")
_LINK = re.compile(r"\[([^\]\n]+)\]\(\s*https?://[^)\s]*\s*\)")
_URL = re.compile(r"https?://\S+")
_ABBREVIATION = re.compile(r"(?:\b(?:e\.g|i\.e|etc|vs|Dr|Mr|Mrs|Ms|Prof|Fig|approx)\.|\b[A-Z]\.)$")
# A year after one of these words is read as a year ("nineteen oh five"), not as a count.
_YEAR = re.compile(r"\b((?:in|since|year|until|till|during|around|circa)\s+)(1[5-9]\d\d|20\d\d)\b(?![.,]?\d)", re.I)
_SYMBOLS = re.compile(r"[\d=+×÷%^]")
# A lone heading that names the document, not the lesson: neither a title nor a part.
_GENERIC_HEADINGS = {"introduction", "intro", "opening", "script", "narration", "voiceover", "voice over",
                     "video script", "lesson script"}
_ASKS = ("?", "?\"", "?”", "?'", "?’")
#: "Asha: …", "Kabir (smiling): …": a character's name before their line in a dialogue script. A name counts as a
#: speaker only when it opens at least two lines; these openers are words of the script itself, never names.
_CAST = re.compile(r"^([A-Z][A-Za-z]{1,14}(?: [A-Z][A-Za-z]{1,14})?)\s*(?:\([^)]{0,30}\))?\s*:\s+(?=\S)")
_NOT_A_NAME = {"note", "question", "answer", "example", "step", "hint", "tip", "remember", "rule", "formula", "definition",
               "given", "find", "solution", "because", "so", "then", "now", "first", "second", "third", "finally", "predict",
               "think", "try", "observe", "result", "conclusion", "summary", "recap", "warning", "safety"}
#: A heading that is a LABEL, not a name for what the part teaches: its part is named when the picture is planned.
_LABEL_HEADING = re.compile(r"^\[?\s*(?:scene|part|shot|section|segment|chapter|act|slide|pause|break|intro|outro)\s*[\divxlc]*\s*\]?$", re.I)


def is_script(brief: dict | None) -> bool:
    return (brief or {}).get("mode") == "script"


def keeps_words(brief: dict | None) -> bool:
    """Whether the reviewer may only REPORT on this lesson (the author's words stay as written)."""
    return is_script(brief) and (brief or {}).get("script_edit") != "fix"


def detect_language(text: str) -> str:
    """The narration language of a pasted script, by its letters and its small words."""
    letters = [ch for ch in text if ch.isalpha()]
    if not letters:
        return "en-IN"
    share = lambda lo, hi: sum(lo <= ch <= hi for ch in letters) / len(letters)  # noqa: E731
    if share("ऀ", "ॿ") > 0.3:
        return "hi-IN"
    if share("ఀ", "౿") > 0.3:
        return "te-IN"
    if share("஀", "௿") > 0.3:
        return "ta-IN"
    words = re.findall(r"[A-Za-z']+", text.lower())
    hindi = sum(w in critic._HINDI_MARKERS for w in words)
    return "hinglish" if hindi >= 3 and hindi / max(1, len(words)) >= 0.08 else "en-IN"


def _year_words(year: int) -> str:
    high, low = divmod(year, 100)
    if year % 1000 == 0:
        return writer.number_words(year)                        # two thousand
    if 2000 < year < 2010:
        return "two thousand " + writer.number_words(low)
    if low == 0:
        return writer.number_words(high) + " hundred"
    return writer.number_words(high) + (" oh " if low < 10 else " ") + writer.number_words(low)


def spoken(text: str, language: str) -> str:
    """The author's words as the voice gets them — a fixed point of what ``writer.discipline`` does to any script."""
    t = _BRACKET.sub(" ", _URL.sub(" ", _LINK.sub(r"\1", text)))
    t = re.sub(r"(?<=\d)\s*\*\s*(?=\d)", " × ", t)             # a product, before the markdown stars go
    t = re.sub(r"[*_#`]", " ", t)
    # What a voice cannot read and ``speakable`` does not know: 9² and n × n (it turns × into words between digits only).
    t = t.replace("²", " squared").replace("³", " cubed")
    t = re.sub(r"(?<=[A-Za-z)])\s*×\s*(?=[A-Za-z(\d])|(?<=\d)\s*×\s*(?=[A-Za-z(])",
               " into " if str(language).lower() in ("hinglish", "hi-in") else " times ", t)
    t = _SPEAKER_INSIDE.sub("", t)
    t = _YEAR.sub(lambda m: m.group(1) + _year_words(int(m.group(2))), t)
    t = writer.speakable(re.sub(r"\s+", " ", t).strip(), language)
    return re.sub(r"\s+([,.;:!?।])", r"\1", re.sub(r"\s+", " ", t)).strip()


def sentences(text: str) -> list[str]:
    """Sentences, without breaking after an abbreviation ("e.g. a ladder")."""
    out: list[str] = []
    for part in split_sentences(text):
        if out and _ABBREVIATION.search(out[-1]):
            out[-1] += " " + part
        else:
            out.append(part)
    return out


def pack(parts: list[str], limit: int = MAX_BEAT_WORDS) -> list[str]:
    """Sentences → beats of at most ``limit`` words, of about equal length (a sentence is never cut)."""
    total = sum(len(p.split()) for p in parts)
    if total <= limit:
        return [" ".join(parts)] if parts else []
    wanted = math.ceil(total / limit)
    target = total / wanted
    beats, current, count = [], [], 0
    for part in parts:
        size = len(part.split())
        if current and (count + size > limit or (count + size / 2 > target and len(beats) < wanted - 1)):
            beats.append(" ".join(current))
            current, count = [], 0
        current.append(part)
        count += size
    if current:
        beats.append(" ".join(current))
    return beats


def _implicit_heading(line: str) -> str:
    """A short line on its own that reads as a heading (Title Case, ALL CAPS, or ending in a colon), else ''."""
    text = re.sub(r"[*_`]", "", line).strip()
    words = text.split()
    if not words or len(words) > 8 or len(text) > 70:
        return ""
    if text.endswith(":"):
        return text.rstrip(":").strip()
    if text[-1] in ".?!।,;" or not re.search(r"[A-Za-z]{3}", text):
        return ""
    if text.isupper():
        return text
    lettered = [re.sub(r"[^A-Za-z]", "", w) for w in words]
    significant = [w for w in lettered if len(w) > 3]
    if lettered[0][:1].isupper() and significant and all(w[0].isupper() for w in significant):
        return text
    return ""


# ── a production table pasted as text ─────────────────────────────────────────

_COLUMN = (
    ("scene", re.compile(r"^(?:scene|shot|slide|beat|part|#|s\.?\s*no\.?|sr\.?\s*no\.?|no\.?)\s*(?:no\.?|number|#)?$", re.I)),
    ("time", re.compile(r"^(?:time|timing|timestamp|time ?code|duration|length)\b.{0,14}$", re.I)),
    ("spoken", re.compile(r"^(?:voice[- ]?over|v\.?o\.?|narration|narrator|audio|dialogue|spoken words?|what (?:we|you) hear|"
                          r"commentary|script)\b.{0,24}$", re.I)),
    ("visual", re.compile(r"^(?:on[- ]?screen(?: visuals?| text| action)?|text on screen|visuals?|video|picture|animation|"
                          r"what (?:we|you) see|screen|shot description|scene description|action|notes?|sfx|music)\b.{0,24}$", re.I)),
)
_ROW_NUMBER = re.compile(r"^(?:scene\s*)?\d{1,3}[.)]?$", re.I)
_TIME_CELL = re.compile(r"^\(?\d{1,2}[:.]\d{2}")


def _column(cell: str) -> str:
    cell = re.sub(r"[*_`|]", "", cell).strip()
    return next((kind for kind, pattern in _COLUMN if pattern.match(cell)), "") if 0 < len(cell) <= 40 else ""


def _cells(line: str) -> list[str]:
    """One pasted line as table cells: split on tabs or on ``|`` (a markdown table); else the line itself."""
    if "\t" in line:
        return [c.strip() for c in line.split("\t")]
    if line.count("|") >= 2:
        return [c.strip() for c in line.strip().strip("|").split("|")]
    return [line.strip()]


def _script_table(lines: list[str]) -> dict | None:
    """A Scene | Time | Visual | Voiceover table inside pasted text, or None.

    Two shapes are read: one row per line (cells split by tabs or ``|``), and one CELL per line,
    which is how a table copied from a document arrives. Returns the rows with their cells sorted
    into ``spoken`` and ``visual``, and the lines before and after the table.
    """
    for at, line in enumerate(lines):
        cells = _cells(line)
        kinds = [_column(c) for c in cells] if len(cells) >= 2 else []
        wide = len(cells) >= 2
        if not wide:                                    # a header given one cell per line
            kinds, k = [], at
            while k < len(lines) and len(kinds) < 6 and _column(lines[k]):
                kinds.append(_column(lines[k]))
                k += 1
        if len(kinds) < 2 or kinds.count("spoken") != 1 or not all(kinds):
            continue
        rest = lines[at + (1 if wide else len(kinds)):]
        rows, after = [], []
        if wide:
            for i, row in enumerate(rest):
                cells = _cells(row)
                if not row.strip() or (len(cells) >= 2 and not any(c.strip("-: ") for c in cells)):
                    continue                            # a blank line, or the |---|---| rule under the header
                if len(cells) < 2:
                    after = [x for x in rest[i:] if x.strip()]
                    break
                rows.append(dict(zip(kinds, cells)) | {"extra": cells[len(kinds):]})
        else:
            body = [x for x in rest if x.strip()]
            starts_with = kinds[0]
            if starts_with not in ("scene", "time"):    # no numbering to find the rows by: they come in fixed groups
                groups = [body[i:i + len(kinds)] for i in range(0, len(body), len(kinds))]
            else:
                begins = _ROW_NUMBER if starts_with == "scene" else _TIME_CELL
                groups = []
                for x in body:
                    if begins.match(x) or not groups:
                        groups.append([])
                    groups[-1].append(x)
            usual = max(set(map(len, groups)), key=[len(g) for g in groups].count) if groups else 0
            for group in groups:
                cells = list(group)
                if usual == len(kinds) and len(cells) > usual:
                    after += cells[usual:]              # one cell a line everywhere else: the rest is below the table
                    cells = cells[:usual]
                row, left = {}, list(kinds)
                for kind in ("scene", "time"):
                    if left and left[0] == kind and cells:
                        if kind == "scene" or _TIME_CELL.match(cells[0]):
                            row[kind] = cells.pop(0)
                        left.pop(0)
                if len(cells) > len(left) and left:     # a cell that ran over several lines: the last column takes them
                    cells = cells[:len(left) - 1] + [" ".join(cells[len(left) - 1:])]
                row.update(zip(left, cells))
                rows.append(row)
        rows = [r for r in rows if str(r.get("spoken") or "").strip()]
        if len(rows) >= 2:
            return {"columns": kinds, "rows": rows, "before": [x for x in lines[:at] if x.strip()], "after": after}
    return None


def _reading(text: str, log=None) -> dict | None:
    """What the reader model made of a structured document (``script_reader.read``), cached by the document.

    None when the text is plain narration, when no model is configured, when it is switched off
    (``HARNESS_SCRIPT_READER=0``) or when the model's answer was refused. A refusal is cached too,
    so the same document is not paid for twice.
    """
    from . import script_reader
    if knobs.get("HARNESS_SCRIPT_READER", "1") != "1" or script_reader.looks_structured(text) < READER_MIN_SIGNS:
        return None
    # Keyed on the document without the blank edges: the read-back sends it as typed, a job keeps it trimmed.
    saved = paths.cache("script_reads") / (hashlib.sha256(text.strip().encode("utf-8")).hexdigest()[:24] + ".json")
    if saved.is_file():
        try:
            return json.loads(saved.read_text(encoding="utf-8")) or None
        except ValueError:
            pass
    llm = script_reader.default_llm()
    if llm is None:
        return None
    try:
        reading = script_reader.read(text, llm, log or (lambda *_: None))
    except Exception:  # noqa: BLE001 - a reader that cannot be reached leaves the plain reading (nothing is cached)
        return None
    try:
        saved.write_text(json.dumps(reading, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass
    return reading


def parse_script(text: str, language: str | None = None, log=None) -> dict:
    """Pasted text → sections of beats, read as a table, as a labelled document, or as plain narration.

    The plain reading (``_parse``) is always made. When it found no table and the document
    still looks structured, the reader model's reading is parsed too and replaces it only if
    it speaks clearly less: a well-marked script reads the same both ways and stays as it was.
    """
    raw = str(text or "").replace("\r\n", "\n").replace("\r", "\n").replace("\ufeff", "")
    try:
        plain, problem = _parse(raw, language), None
    except ValueError as exc:                  # too long as it stands: the spoken part of it may still fit
        plain, problem = None, exc
    if plain is not None and plain["table"]:
        return plain
    reading = _reading(raw, log) if len(raw) <= MAX_CHARS else None
    if reading and reading.get("script"):
        script = str(reading["script"])
        if len(re.findall(r"(?m)^#{1,6} ", script)) > MAX_CHAPTER_BEATS:
            script = re.sub(r"(?m)^#{1,6} .*\n?", "", script)     # a heading per scene is not a part: the parts are planned
        try:
            read = _parse(script, language or (plain or {}).get("language"))
        except ValueError:
            read = None
        if read and (plain is None or read["words"] < READER_GAIN * plain["words"]):
            outside = [str(reading.get("notes") or "")] + [str(q) for q in (reading.get("questions") or [])]
            read["notes"] = re.sub(r"\s+", " ", " ".join(x for x in outside if x)).strip()[:2400]
            # The reader names the document; a lone "# Scene 1" it wrote above the words is not a title.
            named = re.sub(r"\s+", " ", str(reading.get("title") or "")).strip()[:90]
            read["title"] = named or ("" if re.fullmatch(r"(?i)(?:scene|part)\s+\d+", read["title"]) else read["title"])
            read["reading"] = reading.get("report") or {}
            return read
    if plain is None:
        raise problem
    return plain


def _parse(text: str, language: str | None = None) -> dict:
    """Pasted text → sections of beats. Raises ``ValueError`` when there is too little or too much to narrate.

    Headings (``# Title``, ``Chapter 2: …``, or a short Title Case line on its own) open a
    section; a blank line ends a paragraph; ``[square brackets]`` and ``Visual: …`` lines
    are directions for the picture, kept with their paragraph and never spoken.
    """
    raw = str(text or "").replace("\r\n", "\n").replace("\r", "\n").replace("﻿", "")
    if len(raw) > MAX_CHARS:
        raise ValueError(f"That script is too long for one video: keep it under {MAX_WORDS} words "
                         f"(about {MAX_WORDS // writer.WORDS_PER_MINUTE} minutes).")
    if language not in LANGUAGE_CODES:
        # Read from what will be SPOKEN: an English picture column must not make a Hinglish voiceover English.
        rows = _script_table(raw.split("\n"))
        voice = " ".join(str(r["spoken"]) for r in rows["rows"]) if rows else \
            " ".join(x for x in _BRACKET.sub(" ", raw).split("\n") if not _DIRECTION_LINE.match(re.sub(r"\*\*|__", "", x).strip()))
        language = detect_language(voice)
    # Bold markers go first, so "**Visual:** a triangle" and "**Voiceover:** …" are read as their labels.
    lines = [re.sub(r"\*\*|__", "", line).strip() for line in raw.split("\n")]
    title, items, buffer, directions, implicit = "", [], [], [], 0
    table = _script_table([re.sub(r"\*\*|__", "", line) for line in raw.split("\n")])
    notes: list[str] = []
    if table:
        # Only the voiceover column is spoken. Its row's other cells direct the picture, and whatever
        # stands outside the table (characters, look and feel, an answer key) is a note for the director.
        notes = [re.sub(r"\s+", " ", x).strip() for x in table["before"] + table["after"]]
        lines = []
        for row in table["rows"]:
            seen = "; ".join(re.sub(r"\s+", " ", str(row[k])).strip() for k in table["columns"]
                             if k == "visual" and row.get(k))
            lines += ([f"Visual: {seen}"] if seen else []) + [_SPEAKER.sub("", str(row["spoken"]).strip()), ""]

    def flush():
        joined = " ".join(buffer)
        found = directions + [d.strip() for d in _BRACKET.findall(_LINK.sub(r"\1", joined))
                              if len(d.strip()) > 2 and not d.strip().isdigit()]
        said = spoken(joined, language)
        if said:
            items.append({"kind": "para", "text": said, "directions": found,
                          "changed": bool(_SYMBOLS.search(_BRACKET.sub(" ", joined)))})
        elif found:
            items.append({"kind": "direction", "directions": found})
        buffer.clear()
        directions.clear()

    # The cast of a dialogue script: names that open two lines or more. They are labels, not words to speak
    # (the first dialogue script through the app had "Asha:" and "Kabir:" read aloud before every line of theirs).
    openers = [m.group(1).lower() for m in (_CAST.match(line) for line in lines) if m]
    cast = {name for name in set(openers) if openers.count(name) >= 2 and name not in _NOT_A_NAME
            and not _DIRECTION_LINE.match(name + ": x")}

    for i, line in enumerate(lines):
        if not line:
            flush()
            continue
        if re.fullmatch(r"\[[^\]]{1,1500}\]", line):
            # A line that is ONLY a direction ("[Pause]") is a direction. Standing alone and short, it used to
            # be taken for a heading, and a lesson got three chapters called "[PAUSE]".
            if len(line) > 4 and not line[1:-1].strip().isdigit():
                directions.append(line[1:-1].strip())
            continue
        markdown = _HEADING_MD.match(line)
        worded = None if markdown else _HEADING_WORD.match(line)
        if worded and (len(line.split()) > 12 or line[-1] in ".?!।"):
            worded = None                                   # "Part 2 is harder." is a sentence
        if markdown or worded:
            flush()
            # "Scene 4 (0:30–2:00)" is named "Scene 4": the time in brackets is not part of the name.
            name = markdown.group(2) if markdown else (worded.group(1) or re.sub(r"\s*[(\[][^)\]]{0,24}[)\]]\s*$", "", line))
            items.append({"kind": "heading", "text": re.sub(r"[*_`]", "", name).strip(" :"), "explicit": True,
                          "level": len(markdown.group(1)) if markdown else 0})
            continue
        named = _TITLE_LINE.match(line)
        if named and not title and not items and not buffer:
            title = re.sub(r"[*_`]", "", named.group(1)).strip()
            continue
        direction = _DIRECTION_LINE.match(line)
        if direction:
            directions.append(direction.group(1).strip())
            continue
        line = _SPEAKER.sub("", line)
        named_speaker = _CAST.match(line)
        if named_speaker and named_speaker.group(1).lower() in cast:
            line = line[named_speaker.end():]
        if not line:
            continue                                        # "Narrator:" on a line of its own
        alone = (i == 0 or not lines[i - 1]) and (i == len(lines) - 1 or not lines[i + 1]) and not buffer
        heading = _implicit_heading(line) if alone else ""
        if heading:
            flush()
            items.append({"kind": "heading", "text": heading, "explicit": False, "line": line, "level": 0})
            continue
        buffer.append(_BULLET.sub("", line))
    flush()

    # A heading nothing is said under: a title when it comes first, a spoken line when it only
    # LOOKED like a heading (never lose the author's words), otherwise dropped.
    dropped = []
    for index, item in enumerate(items):
        if item["kind"] != "heading":
            continue
        body = False
        for later in items[index + 1:]:
            if later["kind"] == "heading":
                break
            body = body or later["kind"] == "para"
        if body:
            continue
        first = not any(x["kind"] != "direction" for x in items[:index])
        if first and not title:
            title, item["kind"] = item["text"], "gone"
        elif not item["explicit"] and spoken(item["line"], language):
            item.update(kind="para", text=spoken(item["line"], language), directions=[], changed=False)
        else:
            dropped.append(item["text"])
            item["kind"] = "gone"
    items = [x for x in items if x["kind"] != "gone"]
    headings = [x for x in items if x["kind"] == "heading"]
    # A heading at the very top is the title of the whole script, not the name of its first part, when
    # it is the only heading or a markdown level above all the others ("# Title", then "## Part" …).
    if headings and not title and not any(x["kind"] == "para" for x in items[:items.index(headings[0])]):
        top, rest = headings[0], headings[1:]
        if not rest or (top["level"] and all(h["level"] > top["level"] for h in rest)):
            title = "" if top["text"].lower() in _GENERIC_HEADINGS else top["text"]
            items.remove(top)
            headings = rest
    implicit = sum(1 for h in headings if not h["explicit"])

    sections, pending = [{"title": None, "paragraphs": []}], []
    for item in items:
        if item["kind"] == "heading":
            if pending and sections[-1]["paragraphs"]:
                sections[-1]["paragraphs"][-1]["directions"] += pending
                pending = []
            sections.append({"title": item["text"], "paragraphs": []})
        elif item["kind"] == "direction":
            pending += item["directions"]                   # a direction on its own belongs to what follows it
        else:
            sections[-1]["paragraphs"].append({"text": item["text"], "directions": pending + item["directions"],
                                               "changed": item["changed"]})
            pending = []
    if pending and sections[-1]["paragraphs"]:
        sections[-1]["paragraphs"][-1]["directions"] += pending

    out, number, changed, directed = [], 0, 0, 0
    for section in sections:
        paragraphs = section["paragraphs"]
        merged = []
        for paragraph in paragraphs:
            last = merged[-1] if merged else None
            if last and last["small"] and len((last["text"] + " " + paragraph["text"]).split()) <= MAX_BEAT_WORDS:
                last["text"] += " " + paragraph["text"]
                last["directions"] += paragraph["directions"]
                last["changed"] = last["changed"] or paragraph["changed"]
            else:
                merged.append(dict(paragraph, directions=list(paragraph["directions"])))
            merged[-1]["small"] = len(merged[-1]["text"].split()) < SMALL_PARAGRAPH
        # A short paragraph that could not join what follows it (a closing question, say) joins what came before.
        for k in range(len(merged) - 1, 0, -1):
            if merged[k]["small"] and len((merged[k - 1]["text"] + " " + merged[k]["text"]).split()) <= MAX_BEAT_WORDS:
                merged[k - 1]["text"] += " " + merged[k]["text"]
                merged[k - 1]["directions"] += merged[k]["directions"]
                merged[k - 1]["changed"] = merged[k - 1]["changed"] or merged[k]["changed"]
                del merged[k]
        beats = []
        for paragraph in merged:
            changed += paragraph["changed"]
            for k, narration in enumerate(pack(sentences(paragraph["text"]))):
                number += 1
                note = "; ".join(paragraph["directions"])[:400] if k == 0 else ""
                directed += bool(note)
                beats.append({"id": f"{number:02}", "narration": narration, "direction": note})
        if beats:
            out.append({"title": section["title"], "beats": beats})
    words = sum(len(b["narration"].split()) for s in out for b in s["beats"])
    if words < MIN_WORDS:
        raise ValueError(f"That is too short to make a video from: paste the words to be spoken "
                         f"(at least {MIN_WORDS}; this has {words}).")
    if words > MAX_WORDS:
        raise ValueError(f"That script has {words} words, about {round(words / writer.WORDS_PER_MINUTE)} minutes. "
                         f"One video takes up to {MAX_WORDS}; split it into parts.")
    return {"title": title[:90], "language": language, "sections": out, "words": words, "beats": number,
            "headings": len([s for s in out if s["title"]]), "implicit_headings": implicit,
            "directions": directed, "changed": changed, "dropped_headings": dropped,
            # Set when the script was a table: its columns, how many rows were read, and the author's lines
            # outside it (never spoken; given to the director as notes).
            "table": {"columns": table["columns"], "rows": len(table["rows"])} if table else None,
            "notes": " ".join(notes)[:2400],
            # Set by ``parse_script`` when the reader model's reading was used: its word counts.
            "reading": None}


def _beats(parsed: dict) -> list[dict]:
    return [b for s in parsed["sections"] for b in s["beats"]]


def title_of(parsed: dict) -> str:
    """The script's title, or its opening words when it has none."""
    if parsed["title"]:
        return parsed["title"]
    opening = _beats(parsed)[0]["narration"].split()
    return " ".join(opening[:8]).rstrip(",;:") + ("…" if len(opening) > 8 else "")


def chapterise(parsed: dict, planned: list | None = None) -> tuple[list[dict], str]:
    """Beats → chapters, and who chose them: the author's ``headings``, the ``model``'s plan, or an ``even`` split."""
    sections, beats = parsed["sections"], _beats(parsed)
    known = {b["id"]: i for i, b in enumerate(beats)}
    starts: dict[int, str] = {}
    for entry in planned or []:
        if isinstance(entry, dict):
            at = known.get(critic.beat_id(entry.get("first_beat"), known))
            if at is not None and at not in starts:
                starts[at] = re.sub(r"\s+", " ", str(entry.get("title") or "")).strip()[:60]
    if len(sections) > 1 or sections[0]["title"]:
        # The author's headings start the parts. Two things the plan may add: a NAME for a part whose heading is
        # only a label ("Scene 1", "[Pause]"), and the places to cut a part that is too long for one chapter.
        # Without them a 35-paragraph "Scene 1" became chapters "SCENE 1", "SCENE 1 (2)" … "SCENE 1 (5)".
        chapters = []
        for section in sections:
            if not section["beats"]:
                continue
            first, last = known[section["beats"][0]["id"]], known[section["beats"][-1]["id"]]
            own = "" if _LABEL_HEADING.match(str(section["title"] or "")) else (section["title"] or "")
            inner = [i for i in sorted(starts) if first < i <= last] if len(section["beats"]) > MAX_CHAPTER_BEATS else []
            cuts = [first] + inner + [last + 1]
            for a, b in zip(cuts, cuts[1:]):
                before = [starts[i] for i in sorted(starts) if i <= a and starts[i]]
                title = own if (a == first and own) else (starts.get(a) or (before[-1] if before and not own else ""))
                # With no plan to name it, the author's label is still the best name there is.
                chapters.append({"title": title or own or section["title"] or (f"Part {len(chapters) + 1}" if chapters else "Opening"),
                                 "beats": beats[a:b]})
        source = "headings"
    else:
        if starts and 0 not in starts:
            starts[0] = "Opening"
        order = sorted(starts)
        # A plan of one-beat parts would be a render and a model call per paragraph: not a plan.
        if order and (len(order) <= 3 or len(beats) / len(order) >= 2):
            chapters = [{"title": starts[a] or f"Part {k}", "beats": beats[a:b]}
                        for k, (a, b) in enumerate(zip(order, order[1:] + [len(beats)]), 1)]
            source = "model"
        else:
            parts = math.ceil(len(beats) / EVEN_CHAPTER_BEATS)
            size = math.ceil(len(beats) / parts)
            chapters = [{"title": f"Part {k + 1}" if parts > 1 else (parsed["title"] or "The lesson"),
                         "beats": beats[k * size:(k + 1) * size]} for k in range(parts)]
            source = "even"
    out = []
    for chapter in chapters:
        parts = math.ceil(len(chapter["beats"]) / MAX_CHAPTER_BEATS)
        size = math.ceil(len(chapter["beats"]) / parts)
        for k in range(parts):
            out.append({"title": chapter["title"] if k == 0 else f"{chapter['title']} ({k + 1})",
                        "beats": chapter["beats"][k * size:(k + 1) * size]})
    return [c for c in out if c["beats"]], source


# ── the read-back before anything is spent ────────────────────────────────────

def preview(text: str, language: str | None = None) -> dict:
    """What a pasted script will become: length, parts, language, and what will not be spoken. No model call."""
    parsed = parse_script(text, language)
    words, minutes = parsed["words"], parsed["words"] / writer.WORDS_PER_MINUTE
    by_headings = len(parsed["sections"]) > 1 or bool(parsed["sections"][0]["title"])
    chapters = []
    if by_headings:
        chapters = [{"title": c["title"], "beats": len(c["beats"]),
                     "words": sum(len(b["narration"].split()) for b in c["beats"]),
                     "opens": " ".join(c["beats"][0]["narration"].split()[:12])} for c in chapterise(parsed)[0]]
    notes = []
    if parsed["table"]:
        outside = len(parsed["notes"].split())
        notes.append(f"This is a script table with {parsed['table']['rows']} rows. Only its voiceover column is spoken; "
                     "the visual column guides the picture for each row."
                     + (f" The {outside} words outside the table (notes on characters, style, answers) are not spoken "
                        "either: they are passed on as notes for the picture." if outside else ""))
    if parsed["reading"]:
        report = parsed["reading"]
        notes.append(f"This document holds more than narration. A reader model picked out the spoken lines: {words} of "
                     f"about {report.get('words', '?')} words are spoken. Descriptions of the picture guide what is drawn; "
                     "notes and answers for the teacher are not spoken. Check the opening words above before generating.")
    if parsed["directions"] and not parsed["table"] and not parsed["reading"]:
        n = parsed["directions"]
        notes.append(f"{n} direction{'s' if n != 1 else ''} for the picture found (in [square brackets] or on a "
                     "“Visual:” line). They guide what is drawn and are not spoken.")
    if parsed["changed"]:
        notes.append("Numbers and symbols are read out as words (3/4 is said “three by four”). Write a number in "
                     "words if you want it said another way.")
    if parsed["implicit_headings"]:
        notes.append("A short line on its own was read as a heading, so it names a part and is not spoken. "
                     "End it with a full stop to have it spoken.")
    if parsed["dropped_headings"]:
        notes.append(f"Nothing is said under the heading “{parsed['dropped_headings'][0]}”, so it was left out.")
    if not by_headings and not parsed["table"] and not parsed["reading"]:
        notes.append("No headings found, so the parts are chosen from the script. Start a line with # to name "
                     "the parts yourself.")
    if minutes > 12:
        notes.append(f"This is a long video (about {round(minutes)} minutes), so it takes a while to make.")
    label = next((o["label"] for o in intake.LANGUAGES if o["value"] == parsed["language"]), parsed["language"])
    length = f"about {max(1, round(minutes))} min" if minutes >= 1.5 else f"about {max(10, round(minutes * 6) * 10)} seconds"
    summary = [
        {"label": "Title", "value": title_of(parsed)},
        {"label": "Length", "value": f"{length} · {words} words"},
        {"label": "Parts", "value": (f"{len(chapters)}, from your headings" if by_headings
                                     else "chosen from the script when the video is planned")},
        {"label": "Language", "value": label},
    ]
    return {"title": title_of(parsed), "language": parsed["language"], "words": words, "minutes": round(minutes, 1),
            "beats": parsed["beats"], "parts_from": "headings" if by_headings else "planned", "chapters": chapters,
            "opens": " ".join(_beats(parsed)[0]["narration"].split()[:16]), "directions": parsed["directions"],
            "notes": notes, "summary": summary, "languages": intake.LANGUAGES,
            "limits": {"min_words": MIN_WORDS, "max_words": MAX_WORDS}}


def prepare(brief: dict) -> dict:
    """A script brief as a job keeps it: validated, with the language and a title filled in. Raises ``ValueError``."""
    text = str(brief.get("script") or "").strip()
    parsed = parse_script(text, brief.get("language"))
    out = {"mode": "script", "script": text, "language": parsed["language"],
           "topic": re.sub(r"\s+", " ", str(brief.get("topic") or "")).strip()[:90] or title_of(parsed),
           "script_edit": "fix" if brief.get("script_edit") == "fix" else "keep"}
    if isinstance(brief.get("shapes"), dict) and brief["shapes"]:
        out["shapes"] = brief["shapes"]         # the author's own points for the figures (checked by shapes.settle)
    audience = re.sub(r"\s+", " ", str(brief.get("audience") or "")).strip()[:160]
    if audience:
        out["audience"] = audience
        grade = intake.absorb({}, audience).get("grade")       # "Class 8 students" → the readability band
        if grade:
            out["grade"] = grade
    return out


# ── the screen ────────────────────────────────────────────────────────────────

_DIRECTOR = """You are the director of a narrated, animated lesson video. The script is ALREADY WRITTEN: its words are final and
will be spoken exactly as given. You never write, rewrite, shorten or reorder a spoken word. Your job is the
SCREEN: what is drawn and what moves while those words are spoken, so that the picture shows the very thing the
voice is talking about at that moment.
"""

PLAN_SYSTEM = _DIRECTOR + """
Before the screen is designed beat by beat, plan the whole video. Return ONLY JSON:
{"title": "the script's own title if it has one, else at most 8 words naming what it teaches",
 "thesis": "one sentence: what the viewer knows or can do after watching",
 "anchor": "the ONE example or object the script keeps coming back to, with its numbers — or an empty string",
 "glossary": [{"term": "a technical term the script uses", "meaning": "one line, as this script uses it"}],
 "picture_plan": "two or three sentences: the ONE visual storyline — which picture carries the video, how it changes as the script moves on, what stays on screen throughout",
 "diagram_ask": "a request for the ONE picture this script's subject is known by, written as PICTURE REQUEST below says — or an empty string. Give one only when a single picture can stay up for most of the script: it explains one real thing, one demonstration or one standard diagram. A script that tells a story, moves through several different examples, or is about numbers and things to count gets an empty string: those are drawn here, beat by beat",
 "chapters": [{"first_beat": "01", "title": "at most 5 words, in English", "picture": "a PICTURE REQUEST (below) for the ONE picture this part is told with; repeat the request of the part before EXACTLY to keep its picture; an empty string only when nothing in the part can be drawn"}],
 "try_it": {...} or null}
Chapters: group the beats, in order, into parts of 2 to 6 beats, a new part where the script moves to its next idea.
A line starting with ## is the author's own heading: it always starts a part and keeps its title.
"try_it" is ONE task the viewer does by hand AFTER the video, about the script's one main idea, written in simple
English. It is shown in the app, not spoken, so it adds no words to the script. Give null when the idea cannot be
tried safely with things found at home.
{"title": "at most 6 words",
 "kind": "hands" (objects) | "paper" (pencil and paper) | "simulation",
 "materials": ["at most 6 things found in any home or classroom: paper, a pencil, coins, beans, thread, a ruler, a glass of water, a torch. Nothing that burns, cuts or has to be bought"],
 "stands_for": "one line: what each object stands for in the idea",
 "predict": "the guess to make BEFORE doing it, as a question about what will happen",
 "steps": ["at most 5 short steps, in the order they are done"],
 "observe": "what they will see when it is done correctly",
 "question": "ONE question that asks WHY, which the script's idea answers",
 "expected": "the answer with its reason, in one or two sentences, using the script's own idea and numbers",
 "write": "the two lines the learner should write or say at the end",
 "in_class": "the same task for a teacher with a full class and five minutes"}
A task that only repeats a calculation from the script is not a task: the hands must show the idea.

PICTURES COME FROM A DRAWING SERVICE. It draws what it is asked for the way a textbook prints it: a labelled real
thing, a demonstration, a standard diagram, and for mathematics a grid of tiles, fraction strips, a number line, a
division ladder, a factor tree, a labelled triangle. Give EVERY part a "picture" wherever what is said in it can be
drawn. A part's picture stays on screen for the whole part and its pieces are shown as the voice names them, so ask
for the picture that holds everything the part talks about. Parts that talk about the same thing keep the same
picture: repeat the request word for word, and write that shared request so that it holds everything ALL of those
parts talk about (a water cycle asked for in the part on evaporation must already show the rain, the river and the
ground that the next part speaks of: a picture cannot gain them later). Prefer the wording "A labelled diagram of
<the thing> showing <each piece the script names>": it is drawn with its pieces separate, so each can be shown as
it is named. A video with one picture for each idea, kept and pointed at, teaches; a new picture every paragraph
does not.

PICTURE REQUEST (how "diagram_ask" and each part's "picture" are written):
""" + diagrams.VISUAL_RULE

DIRECT_SYSTEM = _DIRECTOR + """
Return ONLY JSON. Rules that are checked by code after you answer:
- Answer for every beat you are asked for, by its "id". Never return "narration".
""" + writer.STEP_RULES + writer.SCREEN_TEXT_RULE + writer.FIGURE_RULES + """- THE PICTURE CARRIES THE VIDEO. A beat that talks about anything that can be drawn — a shape, a quantity, a graph,
  a process, an object, a comparison, a change over time — gets a "figure"; lines of wording alone are the last
  resort, for a beat that is only talk. Keep ONE picture across the beats that discuss the same thing and change it
  only when the script moves on. Every number, name and label comes from the narration: never show a value the
  voice does not say or directly imply.
- A SCENE MOVES WITH THE WORDS. Write a "scene"'s motion as STAGES, one for each step of its beat, in the order the
  steps are spoken: "<what is drawn>; first <what happens at step 1's words>, then <at step 2's words>, then <at step
  3's words>". The picture reaches each stage when that step's words are said and waits there, so every stage shows
  what those very words say: when the voice counts a row, that row lights up; when it says the answer, the answer
  appears in the picture. Nothing in the picture happens before the words that describe it. Three steps, three
  stages. What is drawn BEFORE the first stage is something the viewer sees from the first word (the ground, the
  empty plate, the outline of what will be built): the picture is never empty, and a beat's first step belongs to
  its first or second sentence. Keep the whole description under 400 characters.
- A beat marked DIRECTION carries the author's own wish for the screen there: follow it.
- "visual": one sentence saying what the viewer sees during the beat.
- "depth": who the beat is for — "basics" (prerequisites and the slow build-up), "core" (the idea itself, its rule,
  the main worked example, the recap), "practice" (your-turn questions, further examples) or "extra" (enrichment,
  edge cases). A viewer who is revising watches only the core beats: about a third to a half of the beats.
- "quiz": ONLY for a beat whose narration ENDS with a question the learner is really meant to answer and which the
  NEXT beat answers: {"question": "at most 14 words", "options": ["three short answers, one to three words each: a name, a number, an outcome, never a sentence"],
  "answer_index": 0, "explain": "one short sentence shown after the reveal"}. Exactly one option is right, the
  others are mistakes learners really make, and the right answer is the one the script itself gives next. For
  every other beat "quiz" is null: never add a question the script does not ask."""

_BEAT_SHAPE = ('{"shapes": {"<name>": {"points": {...}, "polygon": "ABCD", "is": [...]}} (only shapes not declared yet), '
               '"beats": [{"id": "05", "visual": str, "figure": {...} or null, "depth": "basics|core|practice|extra", '
               '"quiz": {...} or null, "steps": [{"say": str, "show": str, "kind": "point|key|math", '
               '"highlight": bool, "focus": str}]}]}')


def _context(brief: dict, notes: str = "") -> str:
    return (f"AUDIENCE: {brief.get('audience') or 'school students'}\n"
            f"LANGUAGE OF THE NARRATION: {critic._language_line({'brief': brief})}. On-screen text stays in English."
            + (f"\nTHE AUTHOR'S OWN NOTES, written beside the script and never spoken (characters, look, questions to "
               f"show, answers for the teacher). Follow them where the picture can: {notes}" if notes else ""))


def _listing(chapters: list[dict], clip: int = 0, mark=None) -> str:
    """The script as the director reads it: ``##`` a part, ``[id]`` a beat, the author's directions under it."""
    lines = []
    for chapter in chapters:
        if chapter.get("title"):
            lines.append(f"## {chapter['title']}")
        for beat in chapter["beats"]:
            words = beat["narration"].split()
            text = beat["narration"] if not clip or len(words) <= clip else " ".join(words[:clip]) + " …"
            lines.append(f"[{beat['id']}] {text}")
            if beat.get("direction") and (mark is None or mark(beat)):
                lines.append(f"     DIRECTION: {beat['direction']}")
    return "\n".join(lines)


def part_pictures(chapters: list[dict], plan: dict, index: dict[str, int]) -> list[str]:
    """The picture request of each part, in order ('' for a part that has none and none before it).

    The plan gives requests by the beat its parts start at; the lesson's parts may be cut elsewhere (the
    author's headings, a long part divided), so a part takes the request of the plan's part its first beat
    falls in. No request there: the part before's, then the script's own ("diagram_ask").
    """
    def tidy(text) -> str:
        return re.sub(r"\s+", " ", str(text or "")).strip()[:300]
    starts = []
    for entry in plan.get("chapters") or []:
        if isinstance(entry, dict):
            at = index.get(critic.beat_id(entry.get("first_beat"), index))
            if at is not None:
                starts.append((at, tidy(entry.get("picture"))))
    starts.sort()
    whole, out, last = tidy(plan.get("diagram_ask")), [], ""
    for chapter in chapters:
        first = index[chapter["beats"][0]["id"]]
        here = [ask for at, ask in starts if at <= first]
        ask = (here[-1] if here else "") or last or whole
        out.append(ask)
        last = ask or last
    return out


def fetch_pictures(asks: list[str], brief: dict, prepare, log=print) -> dict[str, dict | None]:
    """Each distinct request → its prepared picture (or None), asked for side by side. Never raises."""
    wanted = list(dict.fromkeys(a for a in asks if a))[:max_pictures()]
    found: dict[str, dict | None] = {}
    if not wanted:
        return found
    from concurrent.futures import ThreadPoolExecutor

    def one(ask):
        try:
            return prepare(ask, brief, log)
        except BudgetExceeded:
            raise
        except Exception as exc:  # noqa: BLE001 - a picture is an improvement, never a requirement
            log(f"[script] no prepared picture for “{ask[:60]}” ({type(exc).__name__}: {str(exc)[:100]})")
            return None
    with ThreadPoolExecutor(max_workers=3) as pool:
        for ask, ready in zip(wanted, pool.map(knobs.wrap(one), wanted)):
            found[ask] = ready
    return found


#: How many different drawings one script may ask the service for.
MAX_PICTURES = 8


def max_pictures() -> int:
    """``HARNESS_SCRIPT_MAX_PICTURES`` for this lesson, else ``MAX_PICTURES``."""
    return int(knobs.get("HARNESS_SCRIPT_MAX_PICTURES", str(MAX_PICTURES)))


def prepared_picture(ask: str, brief: dict, log=print) -> dict | None:
    """The diagram service's drawing of what the script explains, ready to show, or None.

    ``harness/diagrams.py`` fetches it, takes it apart, and says how it can be shown
    (``diagrams.showable``, the ONE rule for both the script path and the writer's): ``"parts"`` when
    enough of the drawing can be named (a cell with pointer lines, a poster whose boxes of words the tool
    tied to their arrows: a step lights the part it names, through ``writer.use_diagram``), ``"whole"``
    otherwise (shown as the service drew it, words and all; ``file`` is the picture, re-laid in two rows
    when it is a wide before-and-after strip). A drawing that can be shown neither way is not used, and
    the director is never told about it. ``HARNESS_SCRIPT_PICTURES=0`` switches the asking off. A drawing
    is paid for (the service draws with a model): ``diagrams.fetch`` checks the spending cap and writes
    the ledger row.
    """
    ask = re.sub(r"\s+", " ", str(ask or "")).strip()[:300]
    if not ask or knobs.get("HARNESS_SCRIPT_PICTURES", "1") != "1" or not diagrams.available():
        return None
    try:
        # ``prepare_checked``: the drawing is looked at once against its request and asked for again when it
        # is wrong (two drawings at most); neither of two wrong ones is used.
        shown = diagrams.showable(diagrams.prepare_checked(ask, library.school_class(brief), "en", log=log))
    except BudgetExceeded:
        raise
    except Exception as exc:  # noqa: BLE001 - a picture is an improvement, never a requirement
        log(f"[script] no prepared picture ({type(exc).__name__}: {str(exc)[:120]})")
        return None
    if not shown:
        log("[script] no prepared picture that can be shown (nothing came back, or nothing in it can be named and it has no whole drawing)")
    return shown


def _picture_note(ready: dict | None) -> str:
    """What the director is told about a prepared picture."""
    if not ready:
        return ""
    head = (f"\n\nA PREPARED PICTURE is ready for this part: “{ready['ask']}”, drawn the way a textbook draws it. It is "
            "this part's picture. On EVERY beat of the part that it can serve give \"figure\": {\"kind\": \"diagram\"} "
            "(the same on each, so it stays up) and never write a \"scene\" of the same thing. A \"scene\" is a rough "
            "sketch made on the spot: write one only for a beat this picture truly cannot serve. ")
    if ready["shown"] == "parts":
        names = ", ".join(f'"{slug_}" ({ready["names"].get(slug_, slug_)})' for slug_ in ready["parts"][:14])
        return head + f"Its parts: {names}. A step that talks about one part gives that name as its \"focus\"."
    words = "; ".join(dict.fromkeys(str(n) for n in ready.get("names", {}).values()))[:420]
    panels = len(ready.get("panels") or [])
    if panels > 1:
        # A before-and-after drawing must not show the AFTER while the lesson is still asking what will happen.
        marks = ", ".join(f'"{key}" ({entry["name"]})' for key, entry in list(_points(ready).items())[:14])
        return head + (f"It has {panels} panels, one after the other (before, then after). Only the first is on screen "
                       "at the start. The step whose words reveal the next panel gives \"focus\": \"panel2\""
                       + (", the one after it \"panel3\"" if panels > 2 else "")
                       + (f". Its printed labels can be marked too, as the voice names them: {marks}; a step about one of "
                          "them gives that name as its \"focus\" (a label in a panel not yet shown brings its panel in). "
                          "No other focus. " if marks else "; no other step has a focus. ")
                       + "Never let a panel appear before the words that say what it shows.")
    points = _points(ready)
    if points:
        # Its printed labels were found and read (harness/typeset.py): a step can have one marked as the voice names it.
        marks = ", ".join(f'"{key}" ({entry["name"]})' for key, entry in list(points.items())[:14])
        return head + ("It is shown whole, with its own words printed on it. These printed labels can be marked, the way a "
                       f"teacher runs a highlighter over a word: {marks}. A step that talks about one of them gives that name "
                       "as its \"focus\"; give every step you can one, and no other focus.")
    return head + ("It is shown whole, with its own words already written on it" + (f" ({words})" if words else "")
                   + ". Give no \"focus\"; let each step tell the viewer where to look, in the picture's own words.")


def _points(ready: dict | None) -> dict[str, dict]:
    """A whole picture's printed labels that a step may name as its focus: ``{focus: {"name", "box"}}``.

    Keyed the way a step's focus is cleaned everywhere (lower case, letters digits and "_", 24 characters),
    so the same string survives the writer's cleaning, a repair's, and reaches the figure.
    """
    out = {}
    for key, entry in ((ready or {}).get("points") or {}).items():
        focus = re.sub(r"[^a-z0-9_]", "", str(key).strip().lower().replace(" ", "_"))[:24]
        box = entry.get("box") if isinstance(entry, dict) else None
        if focus and focus not in out and isinstance(box, (list, tuple)) and len(box) == 4 and not re.fullmatch(r"panel_?\d+", focus):
            out[focus] = {"name": str(entry.get("name") or key)[:48], "box": [float(v) for v in box]}
    return out


def place_picture(lesson: dict, ready: dict | None, log=print, revealed: set | None = None) -> dict:
    """Give every ``{"kind": "diagram"}`` beat the prepared picture, in the way it can be shown.

    The director only marks the beats; code supplies the file (a model never names a path). With parts to
    point at, this is ``writer.use_diagram``; shown whole, the figure becomes ``{"kind": "picture"}``; with
    nothing prepared the mark is removed, as ``use_diagram`` does.
    """
    if not ready or ready.get("shown") == "parts":
        return writer.use_diagram(lesson, {"diagram": ready} if ready else None, log=log)
    spec = {"kind": "picture", "file": ready["file"], "ask": ready["ask"]}
    panels = [str(p) for p in ready.get("panels") or []]
    seen = revealed if revealed is not None else set()
    if len(panels) > 1 and len(seen) >= len(panels) - 1:
        panels = []          # every panel was revealed in an earlier part: from here the drawing stands whole
    if len(panels) > 1:
        # A drawing in panels (before, after) shows its first panel and brings in each next one when a step
        # says so (``figures.PictureFigure``): the boxes say where each panel sits in the whole drawing.
        spec["panels"] = panels
        if ready.get("panel_boxes"):
            spec["panel_boxes"] = ready["panel_boxes"]
    reveals = {f"panel{n}" for n in range(2, len(panels) + 1)}
    points = _points(ready)
    if points:
        spec["points"] = points                  # its printed labels: ``figures.PictureFigure`` marks the one a step names
    marked = [beat for chapter in lesson["chapters"] for beat in chapter["beats"]
              if (beat.get("figure") or {}).get("kind") == "diagram"]
    for beat in marked:
        beat["figure"] = copy.deepcopy(spec)
        for step in beat.get("steps") or []:
            label = re.sub(r"[^a-z0-9_]", "", str(step.get("focus") or "").replace(" ", "_").lower())[:24]
            focus = label.replace("_", "")
            if focus in reveals and focus not in seen:
                step["focus"] = focus            # each panel is revealed once, by the first step that asks
                seen.add(focus)
            elif label in points:
                step["focus"] = label            # a printed label of this drawing
            else:
                step.pop("focus", None)          # nothing else in a whole picture can be lit
    if marked and ready.get("credit"):
        lesson["credits"] = [ready["credit"]]
    log(f"[script] the prepared picture “{ready['ask']}” is shown whole on {len(marked)} beat(s)")
    return lesson


def _has_screen(entry) -> bool:
    """Did the director give this beat anything to show: a step or a figure?"""
    return isinstance(entry, dict) and (any(isinstance(step, dict) for step in entry.get("steps") or [])
                                        or isinstance(entry.get("figure"), dict))


def plain_steps(narration: str) -> list[dict]:
    """One line of the beat's own opening words — what a beat shows when nobody designed its screen."""
    opening = sentences(narration)[0] if narration.strip() else ""
    if not opening or any(ch.isalpha() and not ch.isascii() for ch in opening):
        return []                         # on-screen text is English: other scripts get the title only
    words = opening.rstrip(".!?").split()
    show = " ".join(words[:9]) + ("…" if len(words) > 9 else "")
    return [{"say": " ".join(narration.split()[:3]), "show": show, "kind": "point", "highlight": False}]


def whole_once_brought_in(lesson: dict, log=print) -> list[str]:
    """After the chapter that brings a drawing's last panel in, later chapters show that drawing whole. Returns the files.

    A chapter is a render of its own and a picture in panels opens every chapter on its first panel. So a second
    panel brought in during chapter 4 was gone again when chapter 5 opened (the triangle lesson of 2026-10-10,
    rendered again with the panel put back: the parallelogram came, stayed twenty seconds and vanished for the rest
    of the lesson). A pasted script's parts are given the whole drawing once a panel has been revealed
    (``_finish``); this is the same rule for any lesson, applied when the steps are final. Within the chapter that
    brings the panel in nothing changes: the picture stays as that chapter left it.
    """
    changed = []
    done: dict[str, set] = {}                                       # per drawing: the panels brought in so far
    for chapter in lesson.get("chapters", []):
        opened_whole = {file for file, seen in done.items() if seen.get("all")}
        for beat in chapter.get("beats", []):
            figure = beat.get("figure") or {}
            if figure.get("kind") != "picture" or len(figure.get("panels") or []) < 2:
                continue
            file = str(figure.get("file"))
            if file in opened_whole:
                figure.pop("panels", None)
                figure.pop("panel_boxes", None)
                if file not in changed:
                    changed.append(file)
                continue
            seen = done.setdefault(file, {"count": len(figure["panels"]), "in": {1}})
            for step in beat.get("steps") or []:
                named = re.fullmatch(r"panel_?(\d+)", str(step.get("focus") or "").strip().lower())
                if named:
                    seen["in"].add(int(named.group(1)))
            seen["all"] = all(n in seen["in"] for n in range(1, seen["count"] + 1))
    if changed:
        log(f"[picture] {len(changed)} drawing(s) in panels are shown whole in the chapters after the one that brings the last panel in")
    return changed


def _finish(raw: dict, brief: dict, parsed: dict, meta: dict, log=print, pictures: list | None = None) -> dict:
    from . import shapes  # noqa: PLC0415
    if any(isinstance(b.get("figure"), dict) and b["figure"].get("kind") == "shape"
           for c in raw.get("chapters") or [] for b in c.get("beats") or [] if isinstance(b, dict)):
        # Shapes drawn by name are expanded and the screen's gaps filled from their points; the author's words stay.
        raw, faults = shapes.settle(raw)
        if faults:
            log(f"[script] {len(faults)} geometry fault(s) on the designed screen, e.g. {faults[0][:140]}")
    lesson = writer.discipline(raw, brief, FRAMEWORK)
    # Each part's marked beats get that part's picture (the marks of a part with none are removed).
    credits: list[str] = []
    revealed: dict[str, set] = {}             # per drawing: the panels already brought in by an earlier part
    for k, chapter in enumerate(lesson["chapters"]):
        part, ready = {"chapters": [chapter]}, (pictures[k] if pictures and k < len(pictures) else None)
        place_picture(part, ready, log=log, revealed=revealed.setdefault(ready["ask"], set()) if ready else None)
        credits += [c for c in part.get("credits") or [] if c not in credits]
    if credits:
        lesson["credits"] = credits
    said = [b["narration"] for c in lesson["chapters"] for b in c["beats"]]
    if said != [b["narration"] for b in _beats(parsed)]:
        log("[script] WARNING: the narration is not word for word what was parsed from the script")
    for chapter in lesson["chapters"]:
        for beat in chapter["beats"]:
            # Time to think is given where the SCRIPT asks the learner something (a quiz the
            # director attached). A rhetorical question in someone's own script gets no silence.
            if not beat.get("quiz"):
                beat["thinking_pause_seconds"] = 0.0
    lesson["script"] = {"words": parsed["words"], "beats": parsed["beats"], "directions": parsed["directions"], **meta}
    lesson["continuity"] = writer.continuity(lesson)
    Lesson.model_validate(lesson)
    return lesson


def _reference_note(reference: dict | None) -> str:
    """What reference lessons SHOW for this script's topic, for the screen's designer only.

    The owner, 2026-10-09: "fetch reference videos for the script also. This is just for fine-tuning the
    given narration for visuals. We won't improve the audio voiceover but we'll improve the visuals with
    that." So it is handed to the model that plans and designs the screen, which cannot change a word.
    """
    notes = str((reference or {}).get("notes") or "").strip()
    return ("\n\n" + notes[:3500] + "\n(The narration is final: this is for the PICTURES and what appears on screen, nothing else.)"
            ) if notes else ""


def script_lesson(brief: dict, llm, log=print, prepare=None, reference: dict | None = None) -> dict:
    """The author's script with a model-designed screen. One planning call, then one call per chapter.

    ``prepare(ask, brief, log)`` fetches a prepared picture when the plan asks for one
    (``prepared_picture`` unless a test hands in its own). ``reference`` is what
    ``library.reference_for_script`` found about how lectures on this topic show it
    (looked up by the caller, so that it is part of what a kept screen plan was made from).
    """
    parsed = parse_script(brief.get("script", ""), brief.get("language"))
    beats = _beats(parsed)
    log(f"[script] your script: {parsed['words']} words in {len(beats)} beats"
        + (f", {parsed['headings']} headed part(s)" if parsed["headings"] else "")
        + (f", {parsed['directions']} direction(s) for the picture" if parsed["directions"] else ""))
    plan = {}
    try:
        plan = llm(f"{_context(brief, parsed['notes'])}{_reference_note(reference)}\n\nTHE SCRIPT ([id] marks a beat):\n"
                   f"{_listing([{'title': s['title'], 'beats': s['beats']} for s in parsed['sections']])}",
                   PLAN_SYSTEM) or {}
    except BudgetExceeded:
        raise
    except Exception as exc:  # noqa: BLE001 - the parts can be chosen without it
        log(f"[script] planning call failed ({type(exc).__name__}: {str(exc)[:120]}); parts chosen by length")
    plan = plan if isinstance(plan, dict) else {}
    chapters, source = chapterise(parsed, plan.get("chapters"))
    title = str(plan.get("title") or "").strip() if not parsed["title"] else parsed["title"]
    # Each part's picture is ASKED FOR from the drawing service instead of being sketched by a model beat by
    # beat (2026-10-09, the owner: "the visuals are bad"; a lesson had 33 separate model-written pictures, the
    # same tree in four shapes). The plan names one picture per part; a part with none takes the part's
    # before, then the script's own ("diagram_ask"). Asked for side by side: a drawing takes seconds.
    part_asks = part_pictures(chapters, plan, {b["id"]: i for i, b in enumerate(beats)})
    ready_for = fetch_pictures(part_asks, brief, prepare or prepared_picture, log)
    part_picture = [ready_for.get(ask) if ask else None for ask in part_asks]
    missed = sorted({ask for ask in part_asks if ask and not ready_for.get(ask)})
    for ask, ready in ready_for.items():
        if ready:
            log(f"[script] a prepared picture: “{ready['ask']}” ("
                + ("its parts are pointed at" if ready["shown"] == "parts" else "shown whole") + ") for part(s) "
                + ", ".join(str(k) for k, a in enumerate(part_asks, 1) if a == ask))
    known = {b["id"] for b in beats}
    # Shapes a "shape" figure names by "use". The director's answer used to have nowhere to declare them, so every
    # shape figure named a shape that did not exist and the geometry was dropped from the whole video (2026-10-26,
    # a parallelogram lesson rendered with words only). Shapes given in the brief come first; the director may add.
    declared: dict[str, dict] = {str(k): v for k, v in (brief.get("shapes") or {}).items() if isinstance(v, dict)}
    whole = _listing(chapters, clip=0 if parsed["words"] <= FULL_CONTEXT_WORDS else 14, mark=lambda b: False)
    used: list[str] = []
    raw_chapters, undesigned, reasons = [], [], []
    for k, chapter in enumerate(chapters, 1):
        log(f"[script] the screen for part {k}/{len(chapters)}: {chapter['title']}")
        pictures = ("\nPICTURES ALREADY USED EARLIER (to continue one, repeat its JSON object EXACTLY; write a new "
                    "one only when the picture must change):\n" + "\n".join(f"  {u}" for u in used[-5:])) if used else ""
        prompt = (f"{_context(brief, parsed['notes'])}\n\nVIDEO: {title or title_of(parsed)} — {plan.get('thesis', '')}\n"
                  f"THE PICTURE PLAN: {plan.get('picture_plan', '') or '(none: decide here)'}\n"
                  f"THE EXAMPLE THE SCRIPT USES: {plan.get('anchor', '') or '(none named)'}\n\n"
                  f"THE WHOLE SCRIPT, for context ([id] marks a beat, ## a part):\n{whole}\n{pictures}"
                  f"{_picture_note(part_picture[k - 1])}{_reference_note(reference)}"
                  + (f"\nSHAPES ALREADY DECLARED (a \"shape\" figure names one by \"use\"; keep using these):\n"
                     f"{json.dumps(declared, ensure_ascii=False)}" if declared else "") + "\n\n"
                  f"Design the screen for part {k} of {len(chapters)}, “{chapter['title']}” — these beats, every "
                  f"one of them:\n{_listing([{'beats': chapter['beats']}])}\n\nJSON shape: {_BEAT_SHAPE}")
        designed: dict[str, dict] = {}
        bare: list[str] = []
        for attempt in (1, 2):
            try:
                again = (f"\n\nYour last answer gave beat(s) {', '.join(bare)} no steps and no figure. Every beat gets "
                         "steps, and a figure wherever what is said can be drawn.") if bare else ""
                answer = llm(prompt + again, DIRECT_SYSTEM) or {}
                for name, shape in ((answer.get("shapes") or {}) if isinstance(answer, dict) and isinstance(answer.get("shapes"), dict) else {}).items():
                    if isinstance(shape, dict) and str(name) not in declared:
                        declared[str(name)] = shape
                for entry in (answer.get("beats") or []) if isinstance(answer, dict) else []:
                    if isinstance(entry, dict):
                        beat_id = critic.beat_id(entry.get("id"), known)
                        if beat_id not in designed or (_has_screen(entry) and not _has_screen(designed[beat_id])):
                            designed[beat_id] = entry          # the first design of a beat stands; a bare one is filled
                # One beat left bare is asked for once more. The first real script through the browser on
                # 2026-10-09 had a part of one beat come back with nothing: twenty seconds of video showed its
                # three opening words, and nothing had asked the model again because the beat was "named".
                bare = [b["id"] for b in chapter["beats"] if not _has_screen(designed.get(b["id"]))]
                if not bare:
                    break
                reasons.append(f"no screen for beat(s) {', '.join(bare)}" if any(b["id"] in designed for b in chapter["beats"])
                               else "the answer named none of the beats asked for")
            except BudgetExceeded:
                raise
            except Exception as exc:  # noqa: BLE001 - one more try, then this part falls back to plain text
                reasons.append(f"{type(exc).__name__}: {str(exc)[:120]}")
            log(f"[script] part {k}: no usable answer ({reasons[-1]})" + ("; trying once more" if attempt == 1 else ""))
        out, pictured = [], False
        for beat in chapter["beats"]:
            entry = designed.get(beat["id"]) or {}
            steps = [s for s in (entry.get("steps") or []) if isinstance(s, dict)]
            figure = entry.get("figure") if isinstance(entry.get("figure"), dict) else None
            asks = beat["narration"].rstrip().endswith(_ASKS)
            if not steps and not figure:
                undesigned.append(beat["id"])
                steps = [] if pictured else plain_steps(beat["narration"])     # a picture already up stays up
            if figure:
                pictured = True
                key = json.dumps(figure, ensure_ascii=False, sort_keys=True)
                if key not in used:
                    used.append(key)
            out.append({"narration": beat["narration"], "visual": str(entry.get("visual") or beat["direction"] or ""),
                        "figure": figure, "steps": steps, "depth": entry.get("depth"), "check": "",
                        "quiz": entry.get("quiz") if asks else None})
        raw_chapters.append({"title": chapter["title"], "learning_goal": "", "beats": out})
    if len(undesigned) == len(beats):
        raise RuntimeError("The picture could not be planned for any part of the script "
                           f"({reasons[-1] if reasons else 'no answer from the model'}). Nothing was narrated or "
                           "rendered, so nothing more was spent.")
    if undesigned:
        log(f"[script] {len(undesigned)} of {len(beats)} beat(s) got no designed screen and show plain text: {undesigned[:8]}")
    glossary = [{"term": str(g["term"]), "meaning": str(g.get("meaning", ""))} for g in (plan.get("glossary") or [])
                if isinstance(g, dict) and g.get("term")][:20]
    raw = {"title": title or title_of(parsed), "thesis": str(plan.get("thesis") or ""),
           "anchor": str(plan.get("anchor") or ""), "glossary": glossary, "chapters": raw_chapters,
           **({"shapes": declared} if declared else {})}
    lesson = _finish(raw, brief, parsed, {"parts_from": source, "undesigned": undesigned,
                                         "picture_plan": str(plan.get("picture_plan") or "")[:600],
                                         **({"pictures": [{"ask": r["ask"], "shown": r["shown"],
                                                          "parts": [k for k, a in enumerate(part_asks, 1) if a == ask]}
                                                         for ask, r in ready_for.items() if r]} if any(ready_for.values()) else {}),
                                         # the lectures whose way of SHOWING the topic the screen was designed with
                                         # (titles and links only; never their words)
                                         **({"references": [{"title": str(src.get("title") or "")[:140], "url": str(src.get("url") or "")}
                                                            for src in (reference or {}).get("sources") or []][:4]}
                                            if (reference or {}).get("notes") else {}),
                                         # the plan asked for a picture and none could be had: said, so this
                                         # screen is not the one kept for the script (harness/store.py)
                                         **({"picture_missed": "; ".join(missed)[:300]} if missed else {})},
                     log=log, pictures=part_picture)
    lesson["generated_by"] = GENERATED_BY
    # The task is the director's, the decision to show it is code's (tryit.clean: shape, limits, nothing unsafe).
    task, why_not = tryit.clean(plan.get("try_it"))
    if task:
        lesson["try_it"] = task
        log(f"[script] a try-it-yourself task goes with the video: {task['title'] or task['question'][:60]}")
    elif plan.get("try_it"):
        log(f"[script] the try-it-yourself task was left out: {why_not}")
    return lesson


def plain_lesson(brief: dict, log=print) -> dict:
    """No model configured: the script is narrated as written over plain text. Says what it is."""
    parsed = parse_script(brief.get("script", ""), brief.get("language"))
    chapters, source = chapterise(parsed)
    raw = {"title": brief.get("topic") or title_of(parsed), "thesis": "", "anchor": "", "glossary": [],
           "chapters": [{"title": c["title"], "learning_goal": "", "beats": [
               {"narration": b["narration"], "visual": b["direction"], "steps": plain_steps(b["narration"])}
               for b in c["beats"]]} for c in chapters]}
    lesson = _finish(raw, brief, parsed, {"parts_from": source, "undesigned": [b["id"] for b in _beats(parsed)],
                                         "picture_plan": ""}, log=log)
    lesson["generated_by"] = NO_MODEL
    return lesson
