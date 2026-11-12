"""The timeline compiler: every visual event of the storyboard placed on the measured narration, before rendering.

    storyboard (lesson.json beats, steps, marks, questions) ─┐
    timeline.json (measured beats, sentences, aligned words) ─┴─▶ compile_timeline ─▶ output/sync_timeline.json

The renderer has always worked out WHEN each step appears while it films a chapter (``runtime.GuidedChapter``:
each step waits for its ``say`` phrase in the beat's spoken sentences). That answer existed only inside a render.
This module computes the same answer from the same data with the same search (``locate`` is the renderer's
``LessonScene.locate``, moved here so both use one function), so the schedule of a lesson can be read, checked and
handed to another player without filming anything:

* every event with its time on the lesson's clock, the spoken word it waits for, and how that time was obtained
  (``aligned`` from heard words, ``word-position/...`` estimated inside a measured sentence, ``fallback-spread``
  when its words were not found, ``lead-in`` for a picture drawn before the voice starts);
* the checks that need the audio's clock and not a render: beats laid end to end, every beat narrated, events
  whose words are never spoken, events crowded closer than the eye can follow, a line replaced before it can be
  read, a change after the voice has finished.

It reads, it never changes anything, and it imports no manim.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

SCHEMA = "lessonforge.sync_timeline/1"
#: Seconds the picture leads the spoken word on aligned anchors (``runtime.CUE_LEAD``).
CUE_LEAD = 0.25
#: Two events closer than this inside a beat are hard to follow.
MIN_EVENT_GAP = 0.6
#: A line of words needs about this many words a second to be read while listening, plus a moment to find it.
READ_WORDS_PER_SECOND = 3.0
READ_FIND_SECONDS = 0.3

_norm = lambda s: re.sub(r"[^\w ]", "", (s or "").lower())  # noqa: E731 - the renderer's own normalisation


def locate(sentences: list[dict], phrase: str, after: float = 0.0):
    """Where ``phrase`` is spoken in a beat: ``(seconds into the beat, source)`` or ``None``.

    ``sentences`` are a timeline beat's ``sentences`` (start and duration in seconds from the beat's start, and
    ``words`` with their own times when the narration was aligned). ``after`` makes the search start there, so
    steps are matched in the order they are shown. The sentence start comes from the timeline; the position INSIDE
    the sentence is the aligned word time when there is one, else a word-count estimate, and the source says which.
    """
    needle = _norm(phrase).strip()
    if not needle:
        return None
    for sentence in sentences:
        hay = _norm(sentence["text"])
        position = hay.find(needle)
        while position != -1:
            index = len(hay[:position].split())
            words = sentence.get("words")
            if words and index < len(words):
                found = (words[index]["start"], "aligned")
            else:
                found = (sentence["start"] + sentence["duration"] * index / max(1, len(hay.split())),
                         "word-position/" + sentence.get("timing_source", "measured"))
            if found[0] >= after - 1e-6:
                return found
            position = hay.find(needle, position + 1)
    return None


def _steps(beat: dict, entry: dict) -> list[dict]:
    """The beat's steps as the renderer shows them, including the stand-in for a beat that has none."""
    steps = [dict(s) for s in beat.get("steps") or [] if str(s.get("show", "")).strip()]
    if not steps and entry.get("sentences"):
        first = " ".join(entry["sentences"][0]["text"].split()[:3])
        steps = [{"say": first, "show": beat[k], "kind": kind}
                 for k, kind in (("board_text", "key"), ("equation", "math")) if beat.get(k)]
    return steps


def _issue(beat: str, check: str, what: str, severity: str = "warning", component: str = "sync", **extra) -> dict:
    return {"beat": beat, "check": check, "severity": severity, "component": component, "what": what, **extra}


def compile_timeline(lesson: dict, timeline: list[dict], fps: int = 30) -> dict:
    """Place every event on the lesson's clock and check the schedule. Pure: returns the ``sync_timeline`` dict."""
    entries = {str(t["id"]): t for t in timeline}
    issues: list[dict] = []
    frame = 1.0 / max(1, fps)
    columns = ((lesson.get("look") or {}).get("frame") or "columns") == "columns"

    # The audio's own shape: every beat narrated, laid end to end.
    ordered = sorted(timeline, key=lambda t: t["start"])
    for previous, current in zip(ordered, ordered[1:]):
        gap = current["start"] - (previous["start"] + previous["duration"])
        if abs(gap) > frame + 1e-6:
            issues.append(_issue(str(current["id"]), "beats end to end",
                                 f"{gap:+.3f}s between beat {previous['id']} and this one", "error", "audio"))

    beats, figure_key = [], None
    for chapter in lesson.get("chapters") or []:
        for beat in chapter.get("beats") or []:
            bid = str(beat["id"])
            entry = entries.get(bid)
            if entry is None:
                issues.append(_issue(bid, "narrated", "the beat has no narration in timeline.json", "error", "audio"))
                continue
            start, lead = float(entry["start"]), float(entry.get("lead", 0.5))
            end, speech_end = start + float(entry["duration"]), start + float(entry.get("speech_end", entry["duration"]))
            spoken = " ".join(s["text"] for s in entry.get("sentences") or [])
            if len(_norm(spoken).split()) < len(_norm(beat.get("narration", "")).split()):
                issues.append(_issue(bid, "narrated", "the timeline's sentences hold fewer words than the narration",
                                     "error", "audio"))
            events = []

            figure = beat.get("figure")
            if beat.get("picture") == "off":
                figure_key = None
            elif figure:
                key = json.dumps(figure, sort_keys=True, default=str)
                if key != figure_key:
                    events.append({"kind": "figure", "time": round(start, 3), "source": "lead-in",
                                   "action": str(figure.get("describe") or figure.get("kind") or "picture")[:120]})
                figure_key = key

            steps = _steps(beat, entry)
            speech = max(float(entry.get("speech_end", entry["duration"])) - lead, .5)
            cursor = 0.0
            for i, step in enumerate(steps):
                found = locate(entry.get("sentences") or [], step.get("say", ""), after=cursor)
                if found:
                    cursor = found[0]
                    offset = found[0] - (CUE_LEAD if found[1] == "aligned" else 0.0)
                    source, anchor_time = found[1], round(start + found[0], 3)
                else:
                    offset = cursor = max(cursor, lead + speech * i / max(1, len(steps)))
                    source, anchor_time = "fallback-spread", None
                    if step.get("say"):
                        issues.append(_issue(bid, "anchor spoken", f"step {i + 1}'s words are never spoken in order "
                                             "(it is spread evenly instead)", say=step.get("say")))
                events.append({"kind": "step", "time": round(start + max(0.0, offset), 3), "anchor_time": anchor_time,
                               "say": step.get("say", ""), "source": source, "action": str(step.get("show", ""))[:160],
                               "step_kind": step.get("kind", "point"), "focus": step.get("focus", "")})
                for mark in step.get("annotate") or []:
                    if not mark.get("say"):
                        continue
                    got = locate(entry.get("sentences") or [], mark["say"])
                    events.append({"kind": "mark", "time": round(start + got[0], 3) if got else None,
                                   "say": mark["say"], "source": got[1] if got else "unplaced",
                                   "action": str(mark.get("text") or mark.get("kind") or "mark")[:80]})

            if beat.get("quiz"):
                events.append({"kind": "question", "time": round(speech_end, 3), "source": "speech-end",
                               "action": str((beat["quiz"] or {}).get("question") or "")[:160],
                               "pause": float(beat.get("thinking_pause_seconds") or 0.0)})
                if not beat.get("thinking_pause_seconds"):
                    issues.append(_issue(bid, "question pause", "a question with no time to answer it", "error",
                                         "storyboard"))

            # Checks on the schedule of this beat's steps.
            timed = [e for e in events if e["kind"] == "step"]
            for a, b in zip(timed, timed[1:]):
                if b["time"] - a["time"] < MIN_EVENT_GAP:
                    issues.append(_issue(bid, "events crowded", f"two steps {b['time'] - a['time']:.2f}s apart",
                                         component="visuals", at=b["time"]))
            for k, e in enumerate(timed):
                if e["time"] > speech_end + 0.1 and e["source"] != "fallback-spread":
                    issues.append(_issue(bid, "after the voice", "a step appears after the voice has finished",
                                         at=e["time"]))
                if columns or e["step_kind"] == "math":
                    continue           # lines stay on screen in the column frame; working stays up in every frame
                until = timed[k + 1]["time"] if k + 1 < len(timed) else end
                need = len(e["action"].split()) / READ_WORDS_PER_SECOND + READ_FIND_SECONDS
                if until - e["time"] < need:
                    issues.append(_issue(bid, "reading time", f"a line of {len(e['action'].split())} words is up "
                                         f"{until - e['time']:.1f}s; it needs about {need:.1f}s", component="visuals",
                                         at=e["time"]))
            beats.append({"id": bid, "chapter": chapter["id"], "start": round(start, 3), "end": round(end, 3),
                          "speech_end": round(speech_end, 3), "events": events})

    sources: dict[str, int] = {}
    for b in beats:
        for e in b["events"]:
            sources[e["source"].split("/")[0]] = sources.get(e["source"].split("/")[0], 0) + 1
    steps_total = sum(1 for b in beats for e in b["events"] if e["kind"] == "step")
    return {
        "schema": SCHEMA,
        "fps": fps,
        "duration": round(sum(float(t["duration"]) for t in timeline), 3),
        "beats": beats,
        "summary": {"events": sum(len(b["events"]) for b in beats), "steps": steps_total,
                    "by_source": sources,
                    "steps_on_heard_words": sum(1 for b in beats for e in b["events"]
                                                if e["kind"] == "step" and e["source"] == "aligned"),
                    "errors": sum(i["severity"] == "error" for i in issues),
                    "warnings": sum(i["severity"] == "warning" for i in issues)},
        "issues": issues,
    }


def compile_lesson(root: str | Path, lesson: dict | None = None, fps: int = 30, log=print) -> dict:
    """Read ``lesson.json`` and ``timeline.json`` from a lesson folder, write ``output/sync_timeline.json``."""
    root = Path(root)
    lesson = lesson if lesson is not None else json.loads((root / "lesson.json").read_text(encoding="utf-8"))
    timeline = json.loads((root / "timeline.json").read_text(encoding="utf-8"))
    compiled = compile_timeline(lesson, timeline, fps=fps)
    out = root / "output"
    out.mkdir(parents=True, exist_ok=True)
    (out / "sync_timeline.json").write_text(json.dumps(compiled, indent=1, ensure_ascii=False), encoding="utf-8")
    s = compiled["summary"]
    log(f"[timeline] {s['events']} events on the narration's clock ({s['steps_on_heard_words']} of {s['steps']} steps "
        f"on heard words); {s['errors']} error(s), {s['warnings']} warning(s)")
    return compiled
