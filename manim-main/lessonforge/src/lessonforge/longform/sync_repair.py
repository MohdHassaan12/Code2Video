"""Repairing a beat's schedule on the measured narration, before anything is filmed (or again after).

    lesson.json + timeline.json ─▶ compile_timeline ─▶ issues per beat ─▶ re-anchor the steps of the faulted beats
                                                                       ─▶ compile again, keep a beat's change only
                                                                          when its schedule is measurably better

The timeline compiler finds where the picture will be out of step with the voice before a frame is drawn: a step
whose words are never spoken (it is spread evenly instead), two steps closer than the eye can follow, a line
replaced before it can be read, a step after the voice has ended. Each of those is about WHICH spoken words a
step waits for, and nothing else: the narration is already recorded and is never touched here, nor (but for ``thin`` below) what a
step shows. So the repair is a choice of anchors among the words actually heard, made by code:

* a step whose anchor is fine and leaves room for the step before it is kept as it is;
* otherwise it is given the three spoken words, after the step before and late enough for that step to be read,
  from the sentence that holds most of the step's own words (earliest first);
* the beat is compiled again on its own and the change is kept only when its issues score lower and it has no
  error it did not have before. A beat that cannot be improved is left exactly as it was.

Moving anchors cannot make room that the narration does not have: a beat whose words give its lines too little
time to be read (the Moon lesson, 2026-10-19: a six-word line up 1.7 s at the end of its beat; a line 0.5 s before
the next) is THINNED when re-anchoring alone leaves it faulted (``thin``, ``HARNESS_SYNC_THIN``): a line is cut to
its first clause ("It must spin, once per orbit" → "It must spin"), or a line the voice says anyway is taken off
the screen. Never a line that asks, works something out (``math``), points at the picture (``focus``) or draws
part of it (``draw``); a hand's mark on a line taken off goes to its neighbour (marks wait for their own words).
The last key line of a beat is never taken off. Each cut is kept only when it lowers the score.

``mend`` does the same on a finished lesson and renders again only the chapters whose beats changed, keeping
the first render unless the new one's layout checks are no worse (the repair loop's rule: never lose a verified
artifact). Nothing here calls a model or changes a word that is spoken.
"""
from __future__ import annotations

import json
import os
import re
import shutil
from pathlib import Path

from .timeline_compiler import (CUE_LEAD, MIN_EVENT_GAP, READ_FIND_SECONDS, READ_WORDS_PER_SECOND, _norm,
                                compile_timeline, locate)

#: The compiler's checks this repair can act on (all of them are about which words a step waits for).
FIXABLE = ("anchor spoken", "events crowded", "reading time", "after the voice")
#: How many spoken words make an anchor (the writer's own anchors are three words).
ANCHOR_WORDS = 3


def score(issues: list[dict]) -> int:
    """An error weighs ten warnings: a change that trades one error for warnings is better, never the reverse."""
    return sum(10 if i["severity"] == "error" else 1 for i in issues)


def _alone(lesson: dict, chapter: dict, beat: dict) -> dict:
    """The lesson cut down to one beat, so it can be compiled and checked by itself."""
    return {"look": lesson.get("look") or {}, "chapters": [{"id": chapter["id"], "beats": [beat]}]}


def beat_issues(lesson: dict, chapter: dict, beat: dict, entry: dict, fps: int = 30) -> list[dict]:
    """The compiler's issues for one beat, as compiled against its own measured narration."""
    entry = {**entry, "start": 0.0}
    compiled = compile_timeline(_alone(lesson, chapter, beat), [entry], fps=fps)
    return [i for i in compiled["issues"] if i["check"] in FIXABLE]


def _need(step: dict, columns: bool) -> float:
    """Seconds a step's line must stay up before the next one replaces it (the compiler's reading-time rule)."""
    if columns or step.get("kind") == "math":
        return MIN_EVENT_GAP
    return max(MIN_EVENT_GAP, len(str(step.get("show", "")).split()) / READ_WORDS_PER_SECOND + READ_FIND_SECONDS)


def _candidates(sentences: list[dict]) -> list[tuple[int, int, str]]:
    """Every run of ``ANCHOR_WORDS`` spoken words as (sentence, first word, phrase), in the order they are said."""
    found = []
    for si, sentence in enumerate(sentences):
        words = sentence["text"].split()
        for wi in range(len(words)):
            phrase = " ".join(words[wi:wi + ANCHOR_WORDS])
            if len(_norm(phrase).split()) >= min(ANCHOR_WORDS, len(_norm(sentence["text"]).split())):
                found.append((si, wi, phrase))
    return found


def reschedule(beat: dict, entry: dict, columns: bool) -> dict:
    """A copy of ``beat`` whose steps wait for words that leave each step the time it needs. Pure."""
    beat = json.loads(json.dumps(beat))
    sentences = entry.get("sentences") or []
    speech_end = float(entry.get("speech_end", entry.get("duration", 0.0)))
    steps = [s for s in beat.get("steps") or [] if str(s.get("show", "")).strip()]
    if not steps or not sentences:
        return beat
    candidates = _candidates(sentences)
    cursor, previous_time, previous_need = 0.0, None, 0.0
    for index, step in enumerate(steps):
        earliest = (previous_time + previous_need + CUE_LEAD) if previous_time is not None else 0.0
        # Leave room for the steps still to come, so moving one does not push the next ones past the voice.
        latest = speech_end - MIN_EVENT_GAP * (len(steps) - index - 1)
        found = locate(sentences, step.get("say", ""), after=cursor) if step.get("say") else None
        if found and found[0] >= earliest - 1e-6 and found[0] <= latest + 1e-6:
            cursor, previous_time, previous_need = found[0], found[0], _need(step, columns)
            continue
        tokens = {t for t in _norm(step.get("show", "")).split() if len(t) >= 4}
        best = None              # (words of the step in its sentence, -time, time, phrase)
        for si, wi, phrase in candidates:
            got = locate(sentences, phrase, after=cursor)
            if not got or got[0] < earliest - 1e-6 or got[0] > latest + 1e-6:
                continue
            hits = sum(1 for word in _norm(sentences[si]["text"]).split() if word in tokens)
            key = (hits, -got[0])
            if best is None or key > best[0]:
                best = (key, got[0], phrase)
        if best is None:
            if found:            # its own words are said, only too soon or too late: the best there is
                cursor, previous_time, previous_need = found[0], found[0], _need(step, columns)
            continue
        step["say"] = best[2]
        cursor, previous_time, previous_need = best[1], best[1], _need(step, columns)
    return beat


#: Where a line may be cut to its first clause: a comma, semicolon, colon or dash between words.
_CLAUSE = re.compile(r"\s*(?:[,;:]|\s[-–—])\s+")


def _first_clause(show: str) -> str | None:
    """``show`` cut at its first clause break, or None when it has none or the clause would be under two words."""
    parts = _CLAUSE.split(show.strip(), maxsplit=1)
    if len(parts) < 2:
        return None
    head = parts[0].strip().rstrip(".,;:")
    return head if len(head.split()) >= 2 and len(head.split()) < len(show.split()) else None


def _may_drop(steps: list[dict], index: int) -> bool:
    """Whether a step may be taken off the screen: one the voice says anyway and nothing else depends on."""
    step = steps[index]
    if len(steps) < 2 or step.get("kind") == "math" or step.get("focus") or step.get("draw"):
        return False
    if str(step.get("show", "")).rstrip().endswith("?"):
        return False                   # the question card is made from the beat's last line that asks
    if step.get("kind") == "key" and sum(1 for s in steps if s.get("kind") == "key") == 1:
        return False
    return True


def _content(text: str) -> set[str]:
    return {w[:5] for w in _norm(text).split() if len(w) >= 3}


def _repeats_another(steps: list[dict], index: int) -> bool:
    """Whether half or more of a line's own words are on another line of the beat (it says little of its own)."""
    own = _content(str(steps[index].get("show", "")))
    others = set().union(*[_content(str(s.get("show", ""))) for k, s in enumerate(steps) if k != index] or [set()])
    return bool(own) and len(own & others) * 2 >= len(own)


def _edits(beat: dict) -> list[tuple[int, str, dict]]:
    """Every single thinning of ``beat``: (preference, what, new beat). Lower preference is tried first on a tie."""
    steps = [s for s in beat.get("steps") or [] if str(s.get("show", "")).strip()]
    out = []
    for index, step in enumerate(steps):
        if step.get("kind") != "math":
            head = _first_clause(str(step.get("show", "")))
            if head:
                made = json.loads(json.dumps(beat))
                kept = [s for s in made["steps"] if str(s.get("show", "")).strip()]
                kept[index]["show"] = head
                out.append((0, f"cut «{step['show']}» to «{head}»", made))
        if _may_drop(steps, index):
            made = json.loads(json.dumps(beat))
            kept = [s for s in made["steps"] if str(s.get("show", "")).strip()]
            gone = kept[index]
            if gone.get("annotate"):
                neighbour = kept[index - 1] if index > 0 else kept[index + 1]
                neighbour["annotate"] = list(neighbour.get("annotate") or []) + list(gone["annotate"])
            made["steps"] = [s for s in made["steps"] if s is not gone]
            # A line that mostly repeats another goes before any line is shortened; then points before keys.
            rank = -1 if _repeats_another(steps, index) else (1 if step.get("kind") == "point" else 2)
            out.append((rank, f"took «{step['show']}» off the screen", made))
    return out


def thin(lesson: dict, chapter: dict, beat: dict, entry: dict, columns: bool, fps: int = 30) -> tuple[dict, list[str]]:
    """``beat`` with the fewest lines cut or taken off that leaves it readable in its time; and what was done. Pure.

    Greedy: at each round every single cut is re-anchored and compiled, and the best one is taken when it scores
    lower than the beat does now and adds no error. Stops when the beat has no reading or crowding issue left.
    """
    errors = lambda found: sum(i["severity"] == "error" for i in found)   # noqa: E731
    current = beat
    found = beat_issues(lesson, chapter, current, entry, fps)
    done: list[str] = []
    for _ in range(len(beat.get("steps") or [])):
        if not any(i["check"] in ("reading time", "events crowded") for i in found):
            break
        best = None
        for preference, what, made in _edits(current):
            made = reschedule(made, entry, columns)
            got = beat_issues(lesson, chapter, made, entry, fps)
            if errors(got) > errors(found) or score(got) >= score(found):
                continue
            key = (score(got), preference)
            if best is None or key < best[0]:
                best = (key, what, made, got)
        if best is None:
            break
        _, what, current, found = best
        done.append(what)
    return current, done


def repair(lesson: dict, timeline: list[dict], fps: int = 30, log=print, thin_lines: bool | None = None) -> dict:
    """Re-anchor, in place, the steps of every beat the compiler faults; return what was tried and kept.

    ``{"tried": [beat ids], "kept": [beat ids], "before": score, "after": score, "thinned": {beat: [what]}}``.
    A beat is changed only when its own schedule scores lower and gains no error; every other beat is exactly as
    it was. ``thin_lines`` (default: ``HARNESS_SYNC_THIN``) lets a beat re-anchoring cannot cure lose lines.
    """
    entries = {str(t["id"]): t for t in timeline}
    columns = ((lesson.get("look") or {}).get("frame") or "columns") == "columns"
    tried, kept, before, after = [], [], 0, 0
    thinned: dict[str, list[str]] = {}
    if thin_lines is None:
        from .. import knobs  # noqa: PLC0415
        thin_lines = knobs.get("HARNESS_SYNC_THIN", "1") == "1"
    thinning = thin_lines
    for chapter in lesson.get("chapters") or []:
        beats = chapter.get("beats") or []
        for position, beat in enumerate(beats):
            entry = entries.get(str(beat["id"]))
            if entry is None:
                continue
            issues = beat_issues(lesson, chapter, beat, entry, fps)
            before += score(issues)
            if not issues:
                continue
            tried.append(str(beat["id"]))
            candidate = reschedule(beat, entry, columns)
            mended = beat_issues(lesson, chapter, candidate, entry, fps)
            if thinning and any(i["check"] in ("reading time", "events crowded") for i in mended):
                # Thinned from the beat as written (each cut re-anchored), not from the re-anchored copy: moving
                # anchors can push a line onto the beat's last words, where no cut then gives it time.
                fewer, cuts = thin(lesson, chapter, beat, entry, columns, fps)
                got = beat_issues(lesson, chapter, fewer, entry, fps) if cuts else mended
                if cuts and score(got) < score(mended):
                    candidate, mended = fewer, got
                    thinned[str(beat["id"])] = cuts
            errors = lambda found: sum(i["severity"] == "error" for i in found)   # noqa: E731
            if score(mended) < score(issues) and errors(mended) <= errors(issues):
                beats[position] = candidate
                kept.append(str(beat["id"]))
                after += score(mended)
            else:
                thinned.pop(str(beat["id"]), None)
                after += score(issues)
    if tried:
        log(f"[sync repair] {len(tried)} beat(s) out of step with the voice; re-anchored {len(kept)} "
            f"({', '.join(kept) or 'none'}): schedule issues scored {before} → {after}")
    for bid, cuts in thinned.items():
        log(f"[sync repair] beat {bid} had more lines than its words give time to read: " + "; ".join(cuts))
    return {"tried": tried, "kept": kept, "before": before, "after": after, "thinned": thinned}


def mend(root: str | Path, quality: str = "m", fps: int = 30, log=print) -> dict:
    """The sync repair on a FINISHED lesson: re-render only the chapters whose beats changed, keep the better.

    The first render, its audits and ``lesson.json`` are kept aside and put back unless the new render's layout
    checks are no worse (overlaps plus things outside the stage). Then the timeline, the QA report and the bundle
    are written again for the lesson as it stands.
    """
    from . import build, qa, storyboard, timeline_compiler
    from .contract import Lesson

    root = Path(root).resolve()
    raw = json.loads((root / "lesson.json").read_text(encoding="utf-8"))
    timeline = json.loads((root / "timeline.json").read_text(encoding="utf-8"))
    original = json.dumps(raw, indent=1, ensure_ascii=False)
    result = repair(raw, timeline, fps=fps, log=log)
    result["chapters"] = sorted({c["id"] for c in raw.get("chapters") or []
                                 for b in c.get("beats") or [] if str(b["id"]) in result["kept"]})
    result["accepted"] = False
    if not result["chapters"]:
        return result
    lesson = Lesson.model_validate(raw)
    clips = build.find_clips(root, lesson)
    video = root / "output" / f"{build.slugify(lesson.title)}.mp4"
    previous = json.loads((root / "output" / "final_checks.json").read_text(encoding="utf-8")) \
        if (root / "output" / "final_checks.json").exists() else None
    faults = lambda r: int(r["layout_findings"]["counted"]) + int(r.get("bounds_violations") or 0)  # noqa: E731
    keep = {cid: Path(shutil.copy2(clips[cid], str(clips[cid]) + ".keep")) for cid in result["chapters"]}
    audits = {cid: (root / "output" / f"chapter_{cid:02}_audit.json") for cid in result["chapters"]}
    audit_text = {cid: p.read_text(encoding="utf-8") for cid, p in audits.items() if p.exists()}
    (root / "lesson.json").write_text(json.dumps(raw, indent=1, ensure_ascii=False), encoding="utf-8")
    try:
        new = build.render_chapters(root, lesson, quality=quality, fps=fps, jobs=8, only=result["chapters"], log=log)
        clips.update(new)
        video = build.assemble(root, clips, lesson, log=log)
        report = build.run_checks(root, video, lesson, quality=quality, fps=fps, log=log)
        result["accepted"] = previous is None or faults(report) <= faults(previous)
    except Exception as exc:  # noqa: BLE001 - a failed re-render keeps the first one
        log(f"[sync repair] the re-render failed ({type(exc).__name__}: {str(exc)[:160]}); the first render stays")
    if not result["accepted"]:
        log("[sync repair] rejected: the re-rendered chapters were not as clean; restoring the first render")
        (root / "lesson.json").write_text(original, encoding="utf-8")
        for cid, backup in keep.items():
            shutil.move(str(backup), str(clips[cid]))
            os.utime(clips[cid])          # the newest clip of a chapter is the one ``find_clips`` takes
            if cid in audit_text:
                audits[cid].write_text(audit_text[cid], encoding="utf-8")
        lesson = Lesson.model_validate(json.loads(original))
        video = build.assemble(root, clips, lesson, log=log)
        build.run_checks(root, video, lesson, quality=quality, fps=fps, log=log)
    for backup in keep.values():
        backup.unlink(missing_ok=True)
    final = json.loads((root / "lesson.json").read_text(encoding="utf-8"))
    storyboard.prepare(root, final, fix=False, log=log)
    timeline_compiler.compile_lesson(root, final, fps=fps, log=log)
    qa.write_qa(root, log=log)
    qa.write_bundle(root, video, log=log)
    log(f"[sync repair] chapters {result['chapters']} rendered again; "
        f"{'kept' if result['accepted'] else 'first render kept'}")
    return result
