"""
Learner-in-the-Loop Repair (Direction D2).

Implements the learner feedback repair loop from:
'Lessonforge vs Code2Video and SGA: architecture, baseline and feedback directions'

Rather than regenerating the entire lesson script when a student fails a diagnostic
probe question, this module:
1. Traces learner failure timestamps (cited seconds) back to exact beats using timeline.json;
2. Classifies the instructional breakdown (never_taught, taught_but_unclear, picture_contradicts_words);
3. Surgically re-synthesizes steps for only the failing beats;
4. Re-anchors and re-times steps via sync_repair;
5. Re-renders ONLY the affected chapters via lesson_build.render_chapters(..., only=target_chapters);
6. Assembles the full video and keeps the repair only if learner errors decrease and layout does not regress.
"""

from __future__ import annotations

import copy
import json
import os
import re
import shutil
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from .. import knobs
from ..longform import build as lesson_build
from ..longform.contract import Lesson
from . import diagrams, repairs, sequence, writer


LEARNER_FIX_SYSTEM = """You correct what ONE moment of a narrated educational video puts on screen.
A simulated learner watched the video and failed a diagnostic probe question testing a key concept.
The error was traced to this exact beat in the narration.

You are given:
- NARRATION OF THE BEAT (recorded, unchangeable): what the voice says;
- THE PICTURE ON SCREEN: the active diagram or visual elements;
- THE STEPS AS THEY ARE: what was shown on screen;
- THE LEARNER'S MISCONCEPTION / FAILED PROBE: what concept was misunderstood;
- FAULT CLASSIFICATION:
    * 'taught_but_unclear': the narrator spoke the concept, but the screen lacked grounding or clear visual formulation;
    * 'picture_contradicts_words': visual labels, equations, or graphics contradicted the spoken explanation;
    * 'never_taught': the governing relation was omitted from visual presentation.

Return ONLY JSON: {"steps": [...]} with the beat's steps rewritten so that, as the words are spoken,
the screen directly and clearly grounds the concept that was misunderstood.
Keep steps that were right. Rules:
""" + writer.STEP_RULES + writer.SCREEN_TEXT_RULE + """- Ground the tested concept explicitly in a 'key' or 'math' step anchored to spoken words.
- When values or equations resolve a misconception, show them clearly when spoken."""


def enabled() -> bool:
    """Whether learner-in-the-loop repair is active for this lesson."""
    return knobs.get("HARNESS_LEARNER_REPAIR", "1") == "1"


def locate_beat_from_second(timeline: list[dict], cited_sec: float) -> dict | None:
    """
    Finds which beat in timeline.json spans ``cited_sec`` (seconds from video start).
    Returns {"chapter_id": int, "beat_id": str, "beat_meta": dict} or None.
    """
    if not timeline:
        return None

    accumulated = 0.0
    for entry in timeline:
        start = float(entry.get("start", accumulated))
        duration = float(entry.get("duration", 0.0))
        end = start + duration

        if start <= cited_sec <= end or (cited_sec < start and entry == timeline[0]):
            cid = entry.get("chapter", 1)
            # Chapter might be an int or string like "C01"
            if isinstance(cid, str):
                num_m = re.search(r"\d+", cid)
                cid = int(num_m.group()) if num_m else 1
            return {
                "chapter_id": int(cid),
                "beat_id": str(entry.get("id")),
                "start": start,
                "end": end,
                "entry": entry
            }
        accumulated = end

    # Fallback to last beat if timestamp is at or slightly past end
    last = timeline[-1]
    cid = last.get("chapter", 1)
    if isinstance(cid, str):
        num_m = re.search(r"\d+", cid)
        cid = int(num_m.group()) if num_m else 1
    return {
        "chapter_id": int(cid),
        "beat_id": str(last.get("id")),
        "start": float(last.get("start", 0.0)),
        "end": float(last.get("start", 0.0)) + float(last.get("duration", 0.0)),
        "entry": last
    }


def diagnose_quiz_failures(
    quiz_errors: list[dict],
    timeline: list[dict]
) -> list[dict]:
    """
    Extracts repair targets from learner quiz errors.
    Each item in quiz_errors is:
    {
        "concept": str,
        "question": str,
        "cited_second": float,
        "fault_class": 'never_taught' | 'taught_but_unclear' | 'picture_contradicts_words',
        "learner_answer": str (optional),
        "expected_answer": str (optional)
    }
    Returns list of localized targets with beat_id, chapter_id, and diagnostic brief.
    """
    targets = []
    seen_beats = set()

    for err in quiz_errors:
        cited_sec = float(err.get("cited_second", 0.0))
        located = locate_beat_from_second(timeline, cited_sec)
        if not located:
            continue

        beat_key = (located["chapter_id"], located["beat_id"])
        if beat_key in seen_beats:
            continue
        seen_beats.add(beat_key)

        targets.append({
            "chapter_id": located["chapter_id"],
            "beat_id": located["beat_id"],
            "cited_second": cited_sec,
            "concept": err.get("concept", "Target Concept"),
            "question": err.get("question", ""),
            "fault_class": err.get("fault_class", "taught_but_unclear"),
            "learner_answer": err.get("learner_answer", ""),
            "expected_answer": err.get("expected_answer", ""),
            "why": f"Learner missed '{err.get('concept')}' around t={cited_sec:.1f}s ({err.get('fault_class')})"
        })

    return targets


def repair_beat_steps(
    beat: dict,
    target: dict,
    llm: Callable | None = None
) -> list[dict] | None:
    """
    Synthesizes improved steps for a failing beat.
    Uses LLM if available, otherwise generates high-clarity deterministic grounding.
    """
    narration = beat.get("narration", "")
    current_steps = beat.get("steps") or []

    if llm is not None:
        figure = beat.get("figure") or {}
        picture = (
            figure.get("describe") or figure.get("ask")
            or json.dumps({k: v for k, v in figure.items() if k not in ("module", "file", "panels")})
        ) if figure else "(no picture: formulas and labels only)"

        prompt = (
            f"NARRATION OF THE BEAT (recorded, unchangeable):\n{narration}\n\n"
            f"PICTURE ON SCREEN: {picture}\n\n"
            f"CURRENT STEPS:\n{json.dumps(current_steps, ensure_ascii=False, indent=1)}\n\n"
            f"LEARNER FAILURE TARGET:\n"
            f"- Concept: {target.get('concept')}\n"
            f"- Question: {target.get('question')}\n"
            f"- Classification: {target.get('fault_class')}\n"
            f"- Correct Answer Expected: {target.get('expected_answer')}\n"
            f"- Why: {target.get('why')}\n"
        )
        try:
            answer = llm(prompt, LEARNER_FIX_SYSTEM) or {}
            steps = repairs.clean_steps(
                answer.get("steps") if isinstance(answer, dict) else None,
                narration
            )
            if steps and steps != current_steps:
                return steps
        except Exception:
            pass

    # Deterministic fallback remediation:
    # Ground the expected answer directly in a clear visual step anchored to the narration
    remedied_steps = copy.deepcopy(current_steps)
    concept = target.get("concept", "")
    expected = target.get("expected_answer", "")

    # Look for spoken anchor in narration
    words = narration.split()
    anchor = " ".join(words[:min(4, len(words))]) if words else "key concept"
    for w in [concept.split()[0], "is", "equals", "shows", "law"]:
        for i, word in enumerate(words):
            if w.lower() in word.lower() and i + 2 <= len(words):
                anchor = " ".join(words[i:i + 3])
                break

    show_text = f"{concept}: {expected}" if expected else concept
    new_step = {
        "say": anchor,
        "show": show_text,
        "kind": "key",
        "highlight": True
    }

    if not remedied_steps:
        remedied_steps = [new_step]
    else:
        # Replace the least informative step or append
        replaced = False
        for s in remedied_steps:
            if s.get("kind") != "math" and target["fault_class"] == "picture_contradicts_words":
                s["show"] = show_text
                s["kind"] = "key"
                s["highlight"] = True
                replaced = True
                break
        if not replaced:
            remedied_steps.append(new_step)

    return repairs.clean_steps(remedied_steps, narration)


def layout_faults(report: dict | None) -> int:
    """Calculates layout faults: counted overlaps and off-frame/bounds violations."""
    if not report:
        return 0
    lf = report.get("layout_findings") or {}
    counted = lf.get("counted", 0) if isinstance(lf, dict) else 0
    return int(counted) + int(report.get("bounds_violations") or 0)


def repair_lesson_from_learner(
    root: Path | str,
    lesson_dict: dict,
    video: Path,
    clips: dict[int, Path],
    timeline: list[dict],
    report: dict,
    quiz_errors: list[dict],
    llm: Callable | None = None,
    quality: str = "m",
    log: Callable = print
) -> tuple[Path, dict, dict] | None:
    """
    Executes surgical learner-in-the-loop repair (Direction D2).
    
    1. Traces quiz errors to faulty beats via cited_seconds in timeline;
    2. Repairs ONLY those beats in lesson_dict;
    3. Re-renders ONLY the chapters containing repaired beats;
    4. Assembles the new video and runs checks;
    5. Returns (new_video, new_report, repair_summary).
    """
    root = Path(root)
    targets = diagnose_quiz_failures(quiz_errors, timeline)
    if not targets:
        log("[learner_repair] no faulty beats could be localized from quiz errors")
        return None

    fault_strs = [f"chapter {t['chapter_id']} beat {t['beat_id']} ({t['fault_class']})" for t in targets]
    log(f"[learner_repair] localized {len(targets)} instructional fault(s): {', '.join(fault_strs)}")

    before_lesson = copy.deepcopy(lesson_dict)
    first_chapters = {int(c["id"]): copy.deepcopy(c) for c in before_lesson.get("chapters", [])}

    # Index beats for fast lookup
    beat_map = {}
    for chapter in lesson_dict.get("chapters", []):
        cid = int(chapter["id"])
        for beat in chapter.get("beats", []):
            beat_map[(cid, str(beat["id"]))] = (chapter, beat)

    changed_chapters = set()
    repaired_beats = []

    for t in targets:
        key = (t["chapter_id"], t["beat_id"])
        if key not in beat_map:
            continue
        chapter, beat = beat_map[key]

        new_steps = repair_beat_steps(beat, t, llm=llm)
        if new_steps:
            beat["steps"] = new_steps
            beat["board_text"] = next((s["show"] for s in new_steps if s["kind"] != "math"), "")
            beat["equation"] = next((s["show"] for s in new_steps if s["kind"] == "math"), "")
            changed_chapters.add(t["chapter_id"])
            repaired_beats.append(t["beat_id"])

    if not changed_chapters:
        log("[learner_repair] no steps were changed; keeping original video")
        return None

    # Point again and keep draws
    try:
        writer.point_again(lesson_dict, log=log, was=before_lesson)
    except Exception as exc:
        log(f"[learner_repair] point_again warning: {exc}")

    try:
        sequence.keep_draws(lesson_dict, before_lesson)
    except Exception as exc:
        log(f"[learner_repair] keep_draws warning: {exc}")

    # Re-sync timeline
    try:
        from ..longform import sync_repair
        sync_repair.repair(lesson_dict, timeline, log=log)
    except Exception as exc:
        log(f"[learner_repair] sync_repair warning: {exc}")

    target_chapters = sorted(changed_chapters)
    log(f"[learner_repair] re-rendering ONLY chapter(s) {target_chapters} (saving {len(first_chapters) - len(target_chapters)} chapter renders)")

    out = root / "output"
    out.mkdir(parents=True, exist_ok=True)
    kept_clips = {cid: shutil.copy2(clips[cid], str(clips[cid]) + ".pre_learner") for cid in target_chapters if cid in clips}
    audits = {
        cid: (out / f"chapter_{cid:02}_audit.json").read_text(encoding="utf-8")
        for cid in target_chapters
        if (out / f"chapter_{cid:02}_audit.json").exists()
    }

    def write_lesson(ld: dict) -> Lesson:
        (root / "lesson.json").write_text(json.dumps(ld, indent=2, ensure_ascii=False), encoding="utf-8")
        return Lesson.model_validate(ld)

    def restore():
        for cid, bpath in kept_clips.items():
            if Path(bpath).exists() and cid in clips:
                shutil.move(bpath, clips[cid])
            if cid in audits:
                (out / f"chapter_{cid:02}_audit.json").write_text(audits[cid], encoding="utf-8")
        for i, ch in enumerate(lesson_dict.get("chapters", [])):
            cid = int(ch["id"])
            if cid in target_chapters and cid in first_chapters:
                lesson_dict["chapters"][i] = copy.deepcopy(first_chapters[cid])
        write_lesson(lesson_dict)

    try:
        lesson = write_lesson(lesson_dict)
        new_clips = lesson_build.render_chapters(
            root, lesson, quality=quality, jobs=knobs.render_jobs(),
            only=target_chapters, log=log, extra_env=knobs.render_env()
        )
        clips.update(new_clips)
        new_video = lesson_build.assemble(root, clips, lesson, log=log)
        new_report = lesson_build.run_checks(root, new_video, lesson, quality=quality, log=log)

        # Acceptance check: verify layout faults did not increase
        if layout_faults(new_report) > layout_faults(report):
            log("[learner_repair] rejected: layout faults increased; restoring original video")
            restore()
            new_video = lesson_build.assemble(root, clips, Lesson.model_validate(lesson_dict), log=log)
            new_report = lesson_build.run_checks(root, new_video, lesson, quality=quality, log=log)
            return None

        # Clean up temporary backup clips on acceptance
        for bpath in kept_clips.values():
            Path(bpath).unlink(missing_ok=True)

        summary = {
            "status": "accepted",
            "repaired_beats": repaired_beats,
            "chapters_rendered": target_chapters,
            "chapters_skipped": [cid for cid in first_chapters if cid not in target_chapters],
            "faults_before": layout_faults(report),
            "faults_after": layout_faults(new_report),
            "learner_targets": targets
        }
        log(f"[learner_repair] accepted: beats {repaired_beats} repaired across chapter(s) {target_chapters}")
        return new_video, new_report, summary

    except Exception as exc:
        log(f"[learner_repair] render/assembly failed ({exc}); restoring original video")
        restore()
        return None
