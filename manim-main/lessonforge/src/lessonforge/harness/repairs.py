"""Findings that cause a repair, not only a line in a report.

The owner, 2026-10-09, after reading a lesson's reviews: "This critic is giving some things
but we are not able to improve by using those critic things." Until then two of the three
reviews only reported: the layout probe had one repair (re-lay the chapter smaller), the
frame review and the teaching checks had none.

This module is the frame review's repair. The review looks at one frame per beat and says
when the SCREEN does not show what the voice is saying at that moment ("the narrator asks
to guess between nine, six or three, but these numbers are not on screen"). The fault is
then almost always in the beat's steps (what is written on screen, and on which words),
which are cheap to change: nothing is narrated or drawn again.

    1. the beats the review faulted for what is on screen (``SCREEN_KINDS``), a few at most;
    2. for each, a model is shown the narration, the steps as they are, the picture and
       the finding, and returns the steps again (the writer's own step rules, cleaned by
       the same code that cleans a writer's steps);
    3. the chapters that changed are rendered again (free), the checks are run again, and
       ONLY those beats' frames are reviewed again (a fraction of a cent each);
    4. a chapter keeps its new steps only if its faulted beats now have FEWER findings and
       the layout checks are no worse. Otherwise its first render and steps are put back.

Same shape as every repair in this repository: accept if measurably better, never lose
what was there. ``HARNESS_SCREEN_REPAIR=0`` switches it off.
"""
from __future__ import annotations

import copy
import json
import os
import re
import shutil
from pathlib import Path

from .. import knobs
from ..longform import build as lesson_build
from ..longform.contract import Lesson
from . import diagrams, vision_review, writer

#: Findings that say the screen shows the wrong thing for the words (not that things collide: that is layout).
SCREEN_KINDS = ("mismatch", "empty", "stale", "unreadable")
#: How many beats one lesson may have repaired this way (each is one model call and one frame review).
MAX_BEATS = 6


def max_beats() -> int:
    """``HARNESS_SCREEN_REPAIR_BEATS`` for this lesson, else ``MAX_BEATS``."""
    return int(knobs.get("HARNESS_SCREEN_REPAIR_BEATS", str(MAX_BEATS)))

FIX_SYSTEM = """You correct what ONE moment of a narrated lesson video puts on screen.
A reviewer looked at a frame of the video while the narrator was speaking and found that the screen did not show
what the words were saying. You are given the narration of that beat (it is already recorded: you cannot change a
word of it), the picture on screen, the steps as they are, and what the reviewer found.
Return ONLY JSON: {"steps": [...]} with the beat's steps written again so that, at every moment, the screen shows
what the narrator is saying then. Keep steps that were right. Rules, checked by code after you answer:
""" + writer.STEP_RULES + writer.SCREEN_TEXT_RULE + """- When the narrator offers choices or asks the viewer to guess between values, those values are ON SCREEN at that
  moment, in one step, as the narrator says them ("9, 6 or 3?").
- A step appears when its "say" words are spoken. Never show a result before the words that give it.
- Keep every "focus" that was right; give no focus the picture does not have."""


def enabled() -> bool:
    return knobs.get("HARNESS_SCREEN_REPAIR", "1") == "1"


def targets(review: dict | None) -> dict[str, list[dict]]:
    """The beats whose frame was faulted for what is on screen, with those findings, worst first."""
    found = {}
    for row in (review or {}).get("detail") or []:
        wrong = [f for f in row.get("findings") or [] if f.get("kind") in SCREEN_KINDS]
        if wrong and row.get("beat") is not None:
            found[str(row["beat"])] = wrong
    ordered = sorted(found.items(), key=lambda item: -len(item[1]))[:max_beats()]
    return dict(ordered)


def clean_steps(raw_steps, narration: str) -> list[dict]:
    """A model's steps for one beat, made safe to render: the same cleaning ``writer.discipline`` gives a writer's.

    (Kept in step with it by ``tests/unit/test_repairs.py``, which runs both on the same steps.)
    """
    steps, highlights = [], 0
    for step in [s for s in (raw_steps or []) if isinstance(s, dict)][:writer.MAX_STEPS]:
        show = str(step.get("show", "")).strip()
        if not show:
            continue
        kind = step.get("kind") if step.get("kind") in ("point", "key", "math") else "point"
        if kind != "math" and writer._MATH_MARKERS.search(show):
            kind = "math"
        if kind == "math":
            show = writer.mathify(writer.one_line_math(show))
        show = writer.shown(show, kind)
        if not show:
            continue                            # a note about the screen is not a line (writer.SCREEN_TALK): as discipline does
        highlight = bool(step.get("highlight")) and highlights < writer.MAX_HIGHLIGHTS
        highlights += highlight
        entry = {"say": writer._anchor_step(step, narration), "show": show, "kind": kind, "highlight": highlight}
        focus = re.sub(r"[^a-z0-9_]", "", str(step.get("focus") or "").lower())[:24]
        if focus:
            entry["focus"] = focus
        steps.append(entry)
    return steps


def fix_steps(beat: dict, findings: list[dict], llm) -> list[dict] | None:
    """The beat's steps written again for these findings, cleaned; None when there is nothing usable or new."""
    figure = beat.get("figure") or {}
    picture = (figure.get("describe") or figure.get("ask")
               or json.dumps({k: v for k, v in figure.items() if k not in ("module", "manifest", "file", "panels", "panel_boxes", "points")},
                             ensure_ascii=False)) if figure else "(no picture: words and formulas only)"
    known = {str(s.get("focus")) for s in beat.get("steps") or [] if s.get("focus")}
    parts = ""
    if figure.get("kind") == "diagram" and figure.get("manifest"):
        # A prepared drawing: its parts are lit or drawn in when a step names one as its focus. The steps handed
        # in may have lost theirs (an earlier rewrite), so the names come from the drawing itself.
        ready = diagrams.ready_from(figure["manifest"]) or {}
        if ready.get("parts"):
            known = set(ready["parts"])
            parts = ("\nIt is a prepared drawing. Its parts: "
                     + ", ".join(f'"{name}" ({ready["names"].get(name, name)})' for name in ready["parts"][:14])
                     + ". A step that talks about one part gives that name as its \"focus\": that is what makes the part "
                       "appear or light up as the voice names it. Give every step you can a focus.")
    if figure.get("kind") == "picture" and isinstance(figure.get("points"), dict) and figure["points"]:
        # A drawing shown whole whose printed labels can be marked (harness/typeset.py).
        known = set(figure["points"]) | {str(s.get("focus")) for s in beat.get("steps") or []
                                         if re.fullmatch(r"panel\d+", str(s.get("focus") or ""))}
        parts = ("\nIt is a drawing shown whole. These printed labels on it can be marked as the voice names them: "
                 + ", ".join(f'"{name}" ({entry.get("name", name)})' for name, entry in list(figure["points"].items())[:14])
                 + ". A step that talks about one gives that name as its \"focus\". Give every step you can a focus.")
    prompt = (f"NARRATION OF THE BEAT (recorded, unchangeable):\n{beat['narration']}\n\n"
              f"THE PICTURE ON SCREEN: {str(picture)[:500]}{parts}\n\n"
              f"THE STEPS AS THEY ARE:\n{json.dumps(beat.get('steps') or [], ensure_ascii=False, indent=1)}\n\n"
              "WHAT THE REVIEWER FOUND IN THE FRAME:\n" + "\n".join(f"- {str(f.get('what') or f.get('kind'))[:300]}" for f in findings)
              + ('\n\nA QUESTION CARD FOLLOWS THIS BEAT; its question is: ' + str((beat.get("quiz") or {}).get("question"))
                 if beat.get("quiz") else ""))
    answer = llm(prompt, FIX_SYSTEM) or {}
    steps = clean_steps(answer.get("steps") if isinstance(answer, dict) else None, beat["narration"])
    for step in steps:                       # a focus the picture was never given a part for is not invented here
        if step.get("focus") and known and step["focus"] not in known:
            step.pop("focus")
    if not steps or steps == (beat.get("steps") or []):
        return None
    return steps


def _beats(lesson_dict: dict) -> dict[str, tuple[dict, dict]]:
    return {str(b["id"]): (c, b) for c in lesson_dict["chapters"] for b in c["beats"]}


def _count(review: dict | None, beats) -> int | float:
    if review is None or review.get("error"):
        return float("inf")
    wanted = {str(b) for b in beats}
    if not wanted:
        return 0
    total = 0
    seen_beats = set()
    for row in review.get("detail") or []:
        b_str = str(row.get("beat"))
        if b_str in wanted:
            seen_beats.add(b_str)
            if row.get("error"):
                # Treat an error row as not improved: a crashed or refused review cannot cure a fault
                return float("inf")
            total += len([f for f in row.get("findings") or [] if f.get("kind") in SCREEN_KINDS])
    if not seen_beats:
        return float("inf")
    return total


def repair_screen(root: Path, lesson_dict: dict, video: Path, clips: dict, report: dict, review: dict,
                  llm, judge, quality: str, log=print) -> tuple[Path, dict, dict, dict]:
    """Try to cure the frame review's screen findings. Returns ``(video, checks report, review, summary)``.

    ``summary``: ``{"tried": [beats], "kept": [beats], "undone": [beats], "findings_before", "findings_after"}``.
    Everything it changes is put back unless it is measurably better; see the module's note.
    """
    wanted = targets(review)
    summary = {"tried": [], "kept": [], "undone": [], "findings_before": _count(review, wanted), "findings_after": None}
    if not wanted or llm is None or judge is None:
        return video, report, review, summary
    index = _beats(lesson_dict)
    before = copy.deepcopy(lesson_dict)
    changed: dict[int, list[str]] = {}
    for beat_id, findings in wanted.items():
        if beat_id not in index:
            continue
        chapter, beat = index[beat_id]
        try:
            steps = fix_steps(beat, findings, llm)
        except Exception as exc:  # noqa: BLE001 - one beat that cannot be fixed must not stop the others
            log(f"[screen] beat {beat_id}: no new steps ({type(exc).__name__}: {str(exc)[:100]})")
            continue
        if not steps:
            log(f"[screen] beat {beat_id}: the model returned nothing new")
            continue
        beat["steps"] = steps
        beat["board_text"] = next((s["show"] for s in steps if s["kind"] != "math"), "")
        beat["equation"] = next((s["show"] for s in steps if s["kind"] == "math"), "")
        changed.setdefault(int(chapter["id"]), []).append(beat_id)
        summary["tried"].append(beat_id)
    if not changed:
        return video, report, review, summary
    # A rewritten step has lost the part of the drawing it pointed at, and the frame reviewer cannot see that it
    # has: the first lesson repaired here on a prepared drawing came out with the drawing bare through the two
    # chapters whose steps were "cured" (writer.point_again has the story). Pointed again BEFORE the render, so
    # the second look judges the picture as it will be.
    try:
        writer.point_again(lesson_dict, log=log, was=before)
    except Exception as exc:  # noqa: BLE001 - the repair goes on with the steps as they are
        log(f"[screen] the steps could not be pointed at the drawing again ({type(exc).__name__}: {str(exc)[:100]})")
    # ... and the parts of the drawing its steps brought in (``step["draw"]``, harness/sequence.with_words): a part no
    # step brings is on the board from the start, in the chapters filmed again and in no other.
    try:
        from . import sequence  # noqa: PLC0415
        sequence.keep_draws(lesson_dict, before)
    except Exception as exc:  # noqa: BLE001
        log(f"[screen] the steps' parts of the drawing could not be kept ({type(exc).__name__}: {str(exc)[:100]})")
    # ... and re-timed on the measured narration: rewritten steps come after the pipeline's own sync repair, and on
    # the Monty Hall lesson four of them were anchored too close together to be read (longform/sync_repair.py).
    try:
        from ..longform import sync_repair  # noqa: PLC0415
        timeline = json.loads((root / "timeline.json").read_text(encoding="utf-8"))
        sync_repair.repair(lesson_dict, timeline, log=log)
        index = _beats(lesson_dict)
    except Exception as exc:  # noqa: BLE001
        log(f"[screen] the rewritten steps could not be re-timed ({type(exc).__name__}: {str(exc)[:100]})")
    first = {int(c["id"]): c for c in before["chapters"]}
    # ... which can change what the drawing shows in chapters no step was rewritten in (one set of names for the
    # whole lesson): those are rendered again too, or their clips would no longer be what lesson.json says.
    beyond = [int(c["id"]) for c in lesson_dict["chapters"] if int(c["id"]) not in changed and c != first[int(c["id"])]]

    out = root / "output"
    chapters = sorted(set(changed) | set(beyond))
    log(f"[screen] {summary['findings_before']} finding(s) about what is on screen; steps written again for beat(s) "
        f"{', '.join(summary['tried'])}; rendering chapter(s) {chapters} again")
    kept_clips = {cid: shutil.copy2(clips[cid], str(clips[cid]) + ".first") for cid in chapters}
    audits = {cid: (out / f"chapter_{cid:02}_audit.json").read_text(encoding="utf-8") for cid in chapters}

    def write(lesson_now: dict) -> Lesson:
        (root / "lesson.json").write_text(json.dumps(lesson_now, indent=2, ensure_ascii=False), encoding="utf-8")
        return Lesson.model_validate(lesson_now)

    def put_back(cids) -> None:
        nonlocal index
        for cid in cids:
            shutil.copy2(kept_clips[cid], clips[cid])
            (out / f"chapter_{cid:02}_audit.json").write_text(audits[cid], encoding="utf-8")
            for i, ch in enumerate(lesson_dict.get("chapters") or []):
                if int(ch.get("id")) == cid:
                    lesson_dict["chapters"][i] = copy.deepcopy(first[cid])
                    break
            summary["undone"] += changed.get(cid, [])
        index = _beats(lesson_dict)

    try:
        lesson = write(lesson_dict)
        lesson_build.render_chapters(root, lesson, quality=quality, jobs=knobs.render_jobs(), only=chapters, log=log,
                                     extra_env=knobs.render_env())
        new_video = lesson_build.assemble(root, clips, lesson, log=log)
        new_report = lesson_build.run_checks(root, new_video, lesson, quality=quality, log=log)
        again = vision_review.review_video(root, new_video, llm_call=judge, log=log, only=set(summary["tried"]))
        from .service import layout_faults      # late: service imports this module
        undo = [cid for cid in changed if _count(again, changed[cid]) >= _count(review, changed[cid])]
        if layout_faults(new_report) > layout_faults(report):
            undo = chapters                     # the screen may read better; the layout must not pay for it
        elif undo and beyond:
            undo = chapters                     # the drawing keeps ONE set of names: all of the change, or none of it
    except Exception as exc:  # noqa: BLE001 - the first render is the fallback for every failure here
        log(f"[screen] the repair could not be finished ({type(exc).__name__}: {str(exc)[:120]}); the first render is kept")
        undo, again = chapters, None
    if undo:
        put_back(undo)
        lesson = write(lesson_dict)
        new_video = lesson_build.assemble(root, clips, lesson, log=log)
        new_report = lesson_build.run_checks(root, new_video, lesson, quality=quality, log=log)
    summary["kept"] = [b for cid in chapters if cid not in undo for b in changed.get(cid, [])]
    for backup in kept_clips.values():
        Path(backup).unlink(missing_ok=True)
    if summary["kept"] and again:
        review = vision_review.merge(review, again, summary["kept"])
        (out / "vision_review.json").write_text(json.dumps(review, indent=2, ensure_ascii=False), encoding="utf-8")
    summary["findings_after"] = _count(review, wanted)
    log(f"[screen] kept for beat(s) {', '.join(summary['kept']) or 'none'}"
        + (f"; put back for {', '.join(summary['undone'])} (not better)" if summary["undone"] else "")
        + f": {summary['findings_before']} → {summary['findings_after']} finding(s) about what is on screen")
    return new_video, new_report, review, summary
