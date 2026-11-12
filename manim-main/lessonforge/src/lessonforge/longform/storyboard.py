"""The shared storyboard: one record per teaching beat that the voice and the picture are both made from.

A lesson already carries everything in ``lesson.json`` (``contract.py``): each beat's narration, what the picture
does (``visual``, ``figure``), what appears on screen and on which spoken phrase (``steps`` with ``say``), what a
hand marks on the drawing (``annotate``), the question the player stops on (``quiz``) and what the viewer should be
able to do after it (``check``). Those fields were filled by different stages and read by the renderer directly.
This module states them as ONE typed record per beat, the storyboard, and checks it BEFORE any narration is bought:

    lesson_spec.json    who it is for, what they should be able to do, language, length     (stage 1)
    teaching_plan.json  the sequence of ideas: chapter roles, goals, example, method, mistake (stage 2)
    storyboard.json     per beat: narration · visual intent · events and their spoken anchors ·
                        reasoning · validation rules, plus what the gate found                (stage 3)

The gate (``validate``) is code, not a model. It finds what would make the picture and the voice drift apart:
an event whose anchor phrase is not in its beat's narration, events whose anchors run backwards, a beat with no
visual intent, words in the narration a voice cannot read. ``repair`` fixes what code can fix without changing
what is taught (markup left in narration, an anchor that drifted after a rewrite) and touches only the beats
that failed; the rest is reported for the reviewer. Nothing here imports manim or calls a model.

The renderer still reads ``lesson.json``. The storyboard is the renderer-neutral description of the same lesson,
so another renderer (a web player, a different animation library) can be driven from it and from the compiled
timeline (``timeline_compiler.py``) without re-deriving anything.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from .contract import split_sentences

SCHEMA = "lessonforge.storyboard/1"
PLAN_SCHEMA = "lessonforge.teaching_plan/1"
SPEC_SCHEMA = "lessonforge.lesson_spec/1"

#: Markup a model leaves in narration; a voice reads it aloud or stumbles on it. ``writer.discipline`` strips the
#: same set when the script is written; a later rewrite (critic, questions pass) can bring it back.
_MARKUP = re.compile(r"\[[^\]]*\]|[*_#`]")
#: Characters a voice cannot say. "x^2" and "a/b" must be words in narration ("x squared", "a by b").
_UNSAYABLE = re.compile(r"[\^=\\{}<>|]")
#: A sentence longer than this is hard to follow by ear and is often two ideas.
LONG_SENTENCE_WORDS = 45


def norm(text: str) -> str:
    """The renderer's own normalisation (``runtime._norm``): lower case, word characters and spaces kept."""
    return re.sub(r"[^\w ]", "", (text or "").lower())


def phrase_at(sentences: list[str], phrase: str, after: tuple[int, int] = (0, 0)) -> tuple[int, int] | None:
    """Where ``phrase`` is spoken, as (sentence, word), at or after ``after``; ``None`` when it is not.

    The same search the renderer makes (``runtime.LessonScene.locate``): inside ONE sentence, by substring of the
    normalised text, the first match at or after the previous step's. A phrase that runs across a sentence end is
    never found by the renderer, so it is not found here either.
    """
    needle = norm(phrase).strip()
    if not needle:
        return None
    for si, sentence in enumerate(sentences):
        if si < after[0]:
            continue
        hay = norm(sentence)
        position = hay.find(needle)
        while position != -1:
            found = (si, len(hay[:position].split()))
            if found >= after:
                return found
            position = hay.find(needle, position + 1)
    return None


def anchor_for(step: dict, narration: str, after: tuple[int, int] = (0, 0)) -> str:
    """A ``say`` phrase the renderer will find in the narration, or '' (it then spreads the step evenly).

    The phrase the step already has is kept when it is spoken at or after ``after`` (the previous step's place).
    Otherwise the sentence after it that holds most of the step's own words is taken, and three spoken words from
    the first of them, inside that sentence, become its anchor. Same idea as ``writer._anchor_step`` (used when the script is written), held to the
    renderer's per-sentence, in-order search.
    """
    sentences = split_sentences(narration)
    if step.get("say") and phrase_at(sentences, step["say"], after=after) is not None:
        return step["say"]
    tokens = {t for t in norm(step.get("show", "")).split() if len(t) >= 4}
    best = None                    # (words of the step in the sentence, -sentence, first word): most, then earliest
    for si, sentence in enumerate(sentences):
        words = sentence.split()
        hits = [wi for wi, word in enumerate(words) if (si, wi) > after or after == (0, 0)
                if norm(word).strip() in tokens]
        if hits and (best is None or len(hits) > best[0]):
            best = (len(hits), si, hits[0])
    if best is None:
        return ""
    words = sentences[best[1]].split()
    return " ".join(words[best[2]:best[2] + 3])


# ── The records ────────────────────────────────────────────────────────────────────────────────────────────────


class Event(BaseModel):
    """One thing the picture does, and the spoken phrase it waits for."""
    model_config = ConfigDict(extra="allow")

    id: str = Field(description="'<beat>.<n>', unique in the lesson.")
    kind: str = Field(description="'figure' (a picture drawn in), 'step' (words or a formula appear), "
                                  "'mark' (a hand marks the drawing), 'question' (the player stops).")
    action: str = Field("", description="What appears or happens, in the lesson's own words.")
    anchor: str = Field("", description="Words copied from the narration that trigger it; '' = no anchor.")
    focus: str = Field("", description="The part of the figure the event is about, if any.")
    highlight: bool = False


class StoryBeat(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    chapter: int
    narration: str
    visual_intent: str = Field("", description="What the picture must do while the narration plays.")
    figure: Optional[str] = Field(None, description="The kind of picture on screen, if any.")
    events: List[Event] = Field(default_factory=list)
    reasoning: str = Field("", description="What the viewer should be able to see, say or do after the beat.")
    thinking_pause_seconds: float = 0.0
    validation: List[str] = Field(default_factory=list, description="Rules this beat is checked against.")


class Storyboard(BaseModel):
    model_config = ConfigDict(extra="allow")

    schema_: str = Field(SCHEMA, alias="schema")
    title: str
    language: str = "en-US"
    chapters: List[dict] = Field(default_factory=list)
    beats: List[StoryBeat]


# ── Building it from a lesson ──────────────────────────────────────────────────────────────────────────────────


def _visual_intent(beat: dict) -> str:
    if beat.get("picture") == "off":
        return "Words only: no picture for this beat."
    parts = [str(beat.get("visual") or "").strip()]
    figure = beat.get("figure") or {}
    if figure:
        parts.append(str(figure.get("describe") or figure.get("caption") or f"{figure.get('kind')} figure").strip())
    return " ".join(p for p in parts if p)[:400]


def _rules(beat: dict, events: list[Event]) -> list[str]:
    rules = ["narration is speakable text with no stage directions",
             "every event anchor is a phrase of this beat's narration, in the order the events appear"]
    if beat.get("figure"):
        rules.append("the figure's labels and values agree with the narration")
    if any(e.focus for e in events):
        rules.append("each focused part exists on the figure")
    if any(e.kind == "step" and (e.action or "").strip() and "\\" in e.action for e in events):
        rules.append("each formula renders and follows from the line before it")
    if beat.get("quiz"):
        rules.append("the question is asked before its answer is said or shown")
    return rules


def beat_events(beat: dict) -> list[Event]:
    """The beat's events in the order the renderer plays them (``runtime.GuidedChapter``)."""
    events: list[Event] = []
    bid = str(beat["id"])
    figure = beat.get("figure")
    if figure and beat.get("picture") != "off":
        events.append(Event(id=f"{bid}.{len(events) + 1}", kind="figure",
                            action=str(figure.get("describe") or figure.get("kind") or "picture")[:200]))
    for step in beat.get("steps") or []:
        if not str(step.get("show", "")).strip():
            continue
        events.append(Event(id=f"{bid}.{len(events) + 1}", kind="step", action=str(step.get("show")),
                            anchor=str(step.get("say") or ""), focus=str(step.get("focus") or ""),
                            highlight=bool(step.get("highlight")), step_kind=step.get("kind", "point")))
        for mark in step.get("annotate") or []:
            if mark.get("say"):
                events.append(Event(id=f"{bid}.{len(events) + 1}", kind="mark",
                                    action=str(mark.get("text") or mark.get("do") or mark.get("kind") or "mark")[:120],
                                    anchor=str(mark["say"]), focus=str(mark.get("slot") or "")))
    if beat.get("quiz"):
        events.append(Event(id=f"{bid}.{len(events) + 1}", kind="question",
                            action=str((beat["quiz"] or {}).get("question") or "")[:200]))
    return events


def from_lesson(lesson: dict) -> dict:
    """``lesson.json`` → the storyboard, as a plain dict ready for ``storyboard.json``."""
    beats, chapters = [], []
    for chapter in lesson.get("chapters") or []:
        chapters.append({"id": chapter["id"], "title": chapter.get("title", ""), "role": chapter.get("role", ""),
                         "learning_goal": chapter.get("learning_goal", ""),
                         "beats": [str(b["id"]) for b in chapter.get("beats") or []]})
        for beat in chapter.get("beats") or []:
            events = beat_events(beat)
            beats.append(StoryBeat(
                id=str(beat["id"]), chapter=chapter["id"], narration=beat.get("narration", ""),
                visual_intent=_visual_intent(beat), figure=(beat.get("figure") or {}).get("kind"),
                events=events, reasoning=str(beat.get("check") or ""),
                thinking_pause_seconds=float(beat.get("thinking_pause_seconds") or 0.0),
                validation=_rules(beat, events)))
    board = Storyboard(title=lesson.get("title", ""), language=lesson.get("language", "en-US"),
                       chapters=chapters, beats=beats)
    return board.model_dump(by_alias=True)


# ── The gate ───────────────────────────────────────────────────────────────────────────────────────────────────


def _issue(beat: str, check: str, what: str, severity: str = "error", component: str = "storyboard", **extra) -> dict:
    return {"beat": beat, "check": check, "severity": severity, "component": component, "what": what, **extra}


def validate(lesson: dict) -> list[dict]:
    """Every problem the storyboard has, one record each, with the beat it is in. Empty means it passes.

    ``severity`` "error": the voice and the picture will drift apart or the voice will read something wrong.
    "warning": worth a look, not wrong by itself. ``component`` says which stage would fix it.
    """
    issues: list[dict] = []
    for chapter in lesson.get("chapters") or []:
        for beat in chapter.get("beats") or []:
            bid, narration = str(beat["id"]), str(beat.get("narration") or "")
            if not narration.strip():
                issues.append(_issue(bid, "narration", "the beat has no narration", component="script"))
                continue
            if _MARKUP.search(narration):
                issues.append(_issue(bid, "narration", "markup or a bracketed direction in the narration",
                                     component="script", found=_MARKUP.search(narration).group(0)))
            unsayable = sorted(set(_UNSAYABLE.findall(narration)))
            if unsayable:
                issues.append(_issue(bid, "narration", "symbols a voice cannot read: " + " ".join(unsayable),
                                     severity="warning", component="script"))
            for sentence in split_sentences(narration):
                if len(sentence.split()) > LONG_SENTENCE_WORDS:
                    issues.append(_issue(bid, "narration", f"a sentence of {len(sentence.split())} words is hard to "
                                         "follow by ear", severity="warning", component="script",
                                         sentence=sentence[:120]))
            steps = [s for s in beat.get("steps") or [] if str(s.get("show", "")).strip()]
            if not (steps or beat.get("figure") or beat.get("board_text") or beat.get("equation")
                    or beat.get("picture") == "off" or str(beat.get("visual") or "").strip()):
                issues.append(_issue(bid, "visual intent", "nothing is planned for the screen", severity="warning",
                                     component="visuals"))
            sentences, cursor = split_sentences(narration), (0, 0)
            for n, step in enumerate(steps, start=1):
                if not norm(step.get("say", "")).strip():
                    issues.append(_issue(bid, "anchor", f"step {n} has no spoken anchor (it will be spread evenly)",
                                         severity="warning", step=n, show=str(step.get("show"))[:80]))
                    continue
                found = phrase_at(sentences, step["say"], after=cursor)
                if found is None:
                    if phrase_at(sentences, step["say"]) is None:
                        issues.append(_issue(bid, "anchor", f"step {n}'s anchor is not in the narration",
                                             step=n, say=step.get("say")))
                    else:
                        issues.append(_issue(bid, "anchor order", f"step {n}'s anchor is spoken before step {n - 1}'s",
                                             severity="warning", step=n, say=step.get("say")))
                    continue
                cursor = found
            for n, step in enumerate(steps, start=1):
                for mark in step.get("annotate") or []:
                    if mark.get("say") and phrase_at(sentences, mark["say"]) is None:
                        issues.append(_issue(bid, "anchor", f"a mark on step {n} waits for words that are not said",
                                             severity="warning", component="visuals", say=mark.get("say")))
    return issues


def repair(lesson: dict, issues: list[dict] | None = None, keep_words: bool = False, log=print) -> list[str]:
    """Fix, in place, what code can fix without changing what is taught; return the beats that changed.

    Only the beats with an issue are touched (the rest of the lesson stays exactly as reviewed): markup is
    stripped from narration (never with ``keep_words``: an author's script is spoken as written), and a step whose
    anchor is not in the narration is re-anchored on its own words (``anchor_for``), or left unanchored so the
    renderer spreads it rather than waiting for words never said.
    """
    issues = validate(lesson) if issues is None else issues
    wanted = {i["beat"] for i in issues if i["severity"] == "error"}
    changed = []
    for chapter in lesson.get("chapters") or []:
        for beat in chapter.get("beats") or []:
            bid = str(beat["id"])
            if bid not in wanted:
                continue
            before = json.dumps(beat, sort_keys=True, ensure_ascii=False)
            narration = str(beat.get("narration") or "")
            if _MARKUP.search(narration) and not keep_words:
                beat["narration"] = re.sub(r"\s+", " ", _MARKUP.sub(" ", narration)).strip()
            sentences, cursor = split_sentences(beat["narration"]), (0, 0)
            for step in beat.get("steps") or []:
                if str(step.get("show", "")).strip() and step.get("say"):
                    step["say"] = anchor_for(step, beat["narration"], after=cursor)
                    cursor = phrase_at(sentences, step["say"], after=cursor) or cursor
            if json.dumps(beat, sort_keys=True, ensure_ascii=False) != before:
                changed.append(bid)
    if changed:
        log(f"[storyboard] repaired beat(s) {', '.join(changed)}: markup taken out of the narration or an anchor "
            "that was no longer spoken found again")
    return changed


# ── Stage files ────────────────────────────────────────────────────────────────────────────────────────────────


def lesson_spec(lesson: dict) -> dict:
    """Stage 1: what was asked for. Taken from the brief the lesson carries."""
    brief = lesson.get("brief") or {}
    return {
        "schema": SPEC_SCHEMA,
        "topic": brief.get("topic") or lesson.get("title", ""),
        "subject": brief.get("subject", ""),
        "audience": brief.get("audience", ""),
        "level": brief.get("level", ""),
        "learning_objectives": [o for o in [brief.get("goal") or lesson.get("thesis", "")] if o],
        "prerequisites": lesson.get("prerequisites") or [],
        "language": brief.get("language") or lesson.get("language", ""),
        "duration_minutes": brief.get("duration_minutes"),
        "framework": lesson.get("framework") or brief.get("framework", ""),
    }


def teaching_plan(lesson: dict) -> dict:
    """Stage 2: the sequence of ideas, the example that carries them and the mistake the lesson meets."""
    brief = lesson.get("brief") or {}
    return {
        "schema": PLAN_SCHEMA,
        "thesis": lesson.get("thesis", ""),
        "framework": lesson.get("framework") or brief.get("framework", ""),
        "running_example": lesson.get("anchor", ""),
        "small_case": lesson.get("small_case", ""),
        "method": lesson.get("method") or [],
        "misconceptions": [m for m in [brief.get("misconception")] if m],
        "glossary": lesson.get("glossary") or [],
        "sequence": [{"chapter": c["id"], "role": c.get("role", ""), "title": c.get("title", ""),
                      "learning_goal": c.get("learning_goal", ""),
                      "checkpoints": [b.get("check") for b in c.get("beats") or [] if b.get("check")],
                      "questions": [str(b["id"]) for b in c.get("beats") or [] if b.get("quiz")]}
                     for c in lesson.get("chapters") or []],
    }


def _write(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=1, ensure_ascii=False, default=str), encoding="utf-8")
    tmp.replace(path)


def prepare(root: str | Path, lesson: dict, fix: bool = True, keep_words: bool = False, log=print) -> dict:
    """Write stages 1 to 3 into ``<root>/output`` and run the gate; with ``fix``, repair first (in place).

    Returns ``{"issues", "errors", "warnings", "repaired"}``, which is also in ``storyboard.json`` as ``gate``.
    Called again on a finished lesson (after a screen repair has written steps again) it records the storyboard as
    it now stands and keeps the list of beats an earlier call repaired.
    """
    out = Path(root) / "output"
    found = validate(lesson)
    repaired = (repair(lesson, found, keep_words=keep_words, log=log)
                if fix and any(i["severity"] == "error" for i in found) else [])
    if repaired:
        found = validate(lesson)
    try:
        before = (json.loads((out / "storyboard.json").read_text(encoding="utf-8")).get("gate") or {}).get("repaired") or []
    except (OSError, ValueError):
        before = []
    repaired = list(dict.fromkeys([*before, *repaired]))
    gate = {"issues": found, "errors": sum(i["severity"] == "error" for i in found),
            "warnings": sum(i["severity"] == "warning" for i in found), "repaired": repaired}
    _write(out / "lesson_spec.json", lesson_spec(lesson))
    _write(out / "teaching_plan.json", teaching_plan(lesson))
    _write(out / "storyboard.json", {**from_lesson(lesson), "gate": gate})
    log(f"[storyboard] {sum(len(c.get('beats') or []) for c in lesson.get('chapters') or [])} beats; "
        f"{gate['errors']} error(s), {gate['warnings']} warning(s)"
        + (f"; beat(s) {', '.join(repaired)} repaired" if repaired else ""))
    return gate
