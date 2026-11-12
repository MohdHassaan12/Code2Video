"""One quality report per lesson, beat by beat: what is wrong, at which stage, and which pass repairs it.

LGLG's plan for the video pipeline (2026-10-17) ends in "a quality gate and repair: correctness, narration continuity,
visual quality, synchronization, pedagogy", with a ``qa_report.json`` that sends each failure to the component that
caused it, so one beat is repaired instead of the whole lesson made again. Every one of those checks already existed
here, spread over five files nobody reads together (the reviewer's findings in ``job.json``, the stills look in
``composition.json``, the render checks in ``output/final_checks.json``, the frame review in
``output/vision_review.json``, the cue times in each chapter's audit). This module adds two things:

* ``storyboard_findings(lesson)``: the checks code can make on the SHARED STORYBOARD before any audio exists, the
  gate LGLG's plan puts between the storyboard and the voice. Every one of them is a fault seen in a real frame:
  an anchor the narration does not contain, anchors out of order, a beat with nothing on screen, numbers spoken in a
  beat that the screen never shows, a figure one beat late, an unknown side still "?" after the voice states it.
* ``report(lesson_dir, job)``: all findings, old and new, keyed by beat, each with its ``stage`` (script, visual,
  sync, pedagogy, technical), its ``source`` and the ``repair`` pass that owns it. Written to
  ``output/qa_report.json``.

Nothing here calls a model and nothing here changes the lesson.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

#: Which pass repairs which kind of finding. A finding with no owner says so ("report only"): a report that pretends
#: every fault has a cure is worse than one that names the gaps.
REPAIRS = {
    "anchor_missing": "writer.discipline (re-derives the anchor from the step's words)",
    "anchors_out_of_order": "critic.anchors_in_order",
    "no_screen": "report only (the writer's beat had no steps and no picture)",
    "said_not_shown": "writer.figures_and_words / annotate (values written on the drawing)",
    "figure_late": "writer.figures_follow_words",
    "unknown_left": "writer.found_unknowns",
    "stale_picture": "writer.own_pictures (a figure of its own, or the beat shown without the picture)",
    "critic": "critic.revise (the reviewer's rewrite round)",
    "missing": "compose.mend (a drawing of its own, or the beat shown without the picture)",
    "mismatch": "compose.mend / repairs.repair_screen",
    "overlap": "service.chapters_to_relay (compact re-lay of the chapter)",
    "clipped": "service.chapters_to_relay (compact re-lay of the chapter)",
    "bounds": "service.chapters_to_relay (compact re-lay of the chapter)",
    "screen": "repairs.repair_screen (the beat's steps written again)",
    "late_cue": "report only (anchor placed by word position, no aligned time)",
    "check": "report only (a technical check of the finished file)",
}
STAGES = ("script", "visual", "sync", "pedagogy", "technical")
LATE_SECONDS = 0.5           # the render checks' own limit for a cue after its spoken anchor


def _beats(lesson: dict):
    for chapter in lesson.get("chapters") or []:
        for beat in chapter.get("beats") or []:
            yield chapter, beat


def _finding(beat, stage, kind, what, source="storyboard", severity="medium", repair=None) -> dict:
    return {"beat": str(beat) if beat is not None else None, "stage": stage, "kind": kind, "severity": severity,
            "what": what, "source": source, "repair": repair or REPAIRS.get(kind, "report only")}


def _screen_text(beat: dict) -> str:
    """Every piece of text the beat puts on screen, as one string (steps, figure labels, question card, marks)."""
    parts = [str(step.get("show") or "") for step in beat.get("steps") or []]
    figure = beat.get("figure") or {}
    parts += [str(v) for v in (figure.get("labels") or {}).values()] if isinstance(figure.get("labels"), dict) else []
    parts += [str(p.get("label") or "") for p in figure.get("parts") or [] if isinstance(p, dict)]
    quiz = beat.get("quiz") or {}
    parts += [str(quiz.get("question") or "")] + [str(o) for o in quiz.get("options") or []]
    for step in beat.get("steps") or []:
        for mark in step.get("annotate") or []:
            if isinstance(mark, dict):
                parts += [str(t.get("text") or "") for t in mark.get("texts") or [] if isinstance(t, dict)]
                parts.append(str(mark.get("text") or ""))
    return " ".join(parts)


def _canon(number: str) -> str:
    """One spelling per number, so "0.50" on screen is the "0.5" the voice said."""
    try:
        return format(float(number), "g")
    except ValueError:
        return number


def _shown_numbers(beat: dict) -> set[str]:
    from . import annotate, writer
    text = _screen_text(beat)
    shown = set(re.findall(r"\d+(?:\.\d+)?", text)) | annotate.spoken_numbers(text)
    return shown | writer.figure_numbers(beat.get("figure"))


def storyboard_findings(lesson: dict) -> list[dict]:
    """What code can tell is wrong with the shared storyboard before any audio is made (see the module's note)."""
    from . import annotate, writer
    from ..longform import figure_math

    out: list[dict] = []
    for beat, old in writer.stale_pictures(lesson):
        out.append(_finding(beat.get("id"), "visual", "stale_picture", f"the voice talks about other numbers than the "
                            f"picture on screen ({old.get('kind', '?')}, from an earlier case) shows"))
    beats = [beat for _, beat in _beats(lesson)]
    for k, beat in enumerate(beats):
        bid, narration = beat.get("id"), str(beat.get("narration") or "")
        steps = beat.get("steps") or []
        low = narration.lower()
        places = []
        for step in steps:
            say = str(step.get("say") or "").strip()
            if say and say.lower() not in low:
                out.append(_finding(bid, "sync", "anchor_missing", f"the step \"{step.get('show', '')}\" waits for "
                                    f"\"{say}\", which the narration never says"))
            elif say:
                places.append(low.find(say.lower()))
        if places != sorted(places):
            out.append(_finding(bid, "sync", "anchors_out_of_order", "the steps' anchors come in another order than the "
                                "narration says them, so lines arrive together"))
        if not steps and not beat.get("figure") and not beat.get("quiz"):
            out.append(_finding(bid, "visual", "no_screen", "nothing new on screen for this beat", severity="low"))
        said = {n for n in annotate.spoken_numbers(narration) if n not in ("1", "2")}   # "one", "two" are too often words
        shown = {_canon(n) for n in _shown_numbers(beat)}
        unseen = sorted((n for n in said if _canon(n) not in shown), key=float)
        if len(unseen) >= 2:
            out.append(_finding(bid, "visual", "said_not_shown", f"the voice says {', '.join(unseen)} and the screen "
                                "never shows them"))
        own, nxt = beat.get("figure") or {}, (beats[k + 1].get("figure") or {}) if k + 1 < len(beats) else {}
        if own and nxt and own.get("kind") == nxt.get("kind") and own != nxt:
            missing = (annotate.spoken_numbers(narration) - writer.figure_numbers(own)) & writer.figure_numbers(nxt)
            if len(missing) >= 2:
                out.append(_finding(bid, "visual", "figure_late", f"the voice gives {', '.join(sorted(missing, key=float))}"
                                    " over the previous figure; the next beat's figure has them"))
        if own.get("kind") == "right_triangle" and str((own.get("labels") or {}).get("c", "?")).strip() == "?":
            c = figure_math.resolve_right_triangle(own).get("c") or 0
            if c and abs(c - round(c)) < 1e-6 and re.search(r"\b(hypotenuse|longest)\b", low) \
                    and str(round(c)) in annotate.spoken_numbers(narration) \
                    and not any(s.get("focus") == "c" for s in steps):
                out.append(_finding(bid, "visual", "unknown_left", f"the voice states the hypotenuse ({round(c)}) and "
                                    "the drawing still shows \"?\""))
    return out


#: Storyboard findings that send a beat back for its steps to be written again before any audio is made. Each is about
#: the steps alone (what the screen shows and on which words), so a new set of steps can cure it and nothing else
#: changes; "figure_late" and "unknown_left" have code passes of their own (writer.figures_and_words).
MENDABLE = ("said_not_shown", "anchor_missing", "anchors_out_of_order")
MEND_BEATS = 6


def mend_storyboard(lesson: dict, llm, log=print) -> dict:
    """Beats the storyboard check faults get their steps written again, before the voice is made.

    The same step-writer the frame review's repair uses (``repairs.fix_steps``), but here it costs no render and no
    look at a frame: the check is code. A beat keeps its new steps only when the check then finds fewer faults of
    these kinds on it and nothing new; otherwise its steps are put back. Never touches the narration.
    Returns {"tried": [...], "kept": [...], "before": n, "after": n}.
    """
    from . import repairs, writer
    from .. import knobs

    summary = {"tried": [], "kept": [], "before": 0, "after": 0}
    if knobs.get("HARNESS_STORYBOARD_MEND", "1") != "1" or llm is None:
        return summary
    found: dict[str, list[dict]] = {}
    for f in storyboard_findings(lesson):
        if f["kind"] in MENDABLE and f["beat"]:
            found.setdefault(f["beat"], []).append(f)
    summary["before"] = sum(len(v) for v in found.values())
    if not found:
        return summary
    before = json.loads(json.dumps(lesson))
    beats = {str(b.get("id")): b for _, b in _beats(lesson)}

    def on(bid):
        return [(f["kind"], f["what"]) for f in storyboard_findings(lesson) if f["beat"] == bid]

    for bid, faults in sorted(found.items(), key=lambda kv: -len(kv[1]))[:MEND_BEATS]:
        beat = beats.get(bid)
        if beat is None:
            continue
        summary["tried"].append(bid)
        was_steps, was_on = beat.get("steps"), on(bid)
        try:
            new = repairs.fix_steps(beat, [{"what": f["what"], "kind": f["kind"]} for f in faults]
                                    + [{"what": "Fix only this: keep every step that is there, in its place and wording, "
                                                "and add or change only what the screen is missing."}], llm)
        except Exception as exc:  # noqa: BLE001
            log(f"[qa] beat {bid}: steps could not be written again ({type(exc).__name__}: {str(exc)[:100]})")
            continue
        if not new:
            continue
        beat["steps"] = new
        now_on = on(bid)
        mendable_before = sum(1 for k, _ in was_on if k in MENDABLE)
        mendable_now = sum(1 for k, _ in now_on if k in MENDABLE)
        # A mend adds what is missing; a set of steps with fewer lines has taken a right one away (seen on a real
        # lesson: the self-check line went while the missing numbers came in, twice). Every line that was there stays.
        kept_lines = [str(st.get("show")) for st in new]
        if (mendable_now < mendable_before and not set(now_on) - set(was_on)
                and all(str(st.get("show")) in kept_lines for st in was_steps or [])):
            summary["kept"].append(bid)
        else:
            beat["steps"] = was_steps
    if summary["kept"]:
        writer.point_again(lesson, log=log, was=before)
    summary["after"] = sum(1 for f in storyboard_findings(lesson) if f["kind"] in MENDABLE)
    log(f"[qa] storyboard mend: {summary['before']} finding(s) on {len(found)} beat(s); steps written again for "
        f"{', '.join(summary['tried']) or 'none'}; kept {', '.join(summary['kept']) or 'none'}; "
        f"{summary['after']} left")
    return summary


def _read(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def report(lesson_dir, job: dict | None = None, lesson: dict | None = None, dest: str = "output/qa_report.json") -> dict:
    """Every finding about one lesson, keyed by beat; written to ``dest`` and returned."""
    root = Path(lesson_dir)
    lesson = lesson if lesson is not None else (_read(root / "lesson.json") or {})
    job = job if job is not None else (_read(root / "job.json") or {})
    found = list(storyboard_findings(lesson))

    verification = (job.get("verification") or {}).get("findings") or (lesson.get("verification") or {}).get("findings")
    for f in verification or []:
        if isinstance(f, dict) and not f.get("resolved"):
            stage = "pedagogy" if str(f.get("what", "")).lower().startswith(("flow:", "pedagogy")) else "script"
            found.append(_finding(f.get("beat"), stage, "critic", str(f.get("what", ""))[:300], source="reviewer",
                                  severity=str(f.get("severity") or "medium")))
    comp = _read(root / "composition.json") or {}
    for f in comp.get("seen") or []:
        found.append(_finding(f.get("beat"), "visual", f.get("kind") or "mismatch", str(f.get("what", ""))[:300],
                              source="stills look", severity=str(f.get("severity") or "medium")))
    checks = _read(root / "output" / "final_checks.json") or {}
    for f in (checks.get("layout_findings") or {}).get("detail") or []:
        if f.get("counted"):
            found.append(_finding(f.get("beat"), "visual", f.get("kind") or "overlap", str(f.get("detail", ""))[:300],
                                  source="layout probe", severity="high"))
    for f in checks.get("bounds_detail") or []:
        found.append(_finding(f.get("beat") if isinstance(f, dict) else None, "visual", "bounds",
                              json.dumps(f, ensure_ascii=False)[:300], source="bounds check", severity="high"))
    for c in checks.get("checks") or []:
        if not c.get("passed") and not str(c.get("check", "")).startswith("no text overlap"):
            found.append(_finding(None, "technical", "check", f"{c.get('check')}: {c.get('detail', '')}",
                                  source="render checks", severity="high"))
    for audit in sorted((root / "output").glob("chapter_*_audit.json")):
        for cue in (_read(audit) or {}).get("cues") or []:
            late = float(cue.get("actual_before_wait") or 0) - float(cue.get("anchor") or 0)
            if late > LATE_SECONDS:
                found.append(_finding(cue.get("beat"), "sync", "late_cue", f"\"{cue.get('phrase', '')}\" came "
                                      f"{late:.1f}s after its words", source="chapter audit"))
    review = _read(root / "output" / "vision_review.json") or {}
    repaired = {str(b) for b in review.get("repaired_beats") or []}
    for d in review.get("detail") or []:
        for f in d.get("findings") or []:
            screen = f.get("kind") in ("mismatch", "empty", "stale", "unreadable")
            # A collision the frame review sees is not a repair's trigger: the probe measures those, and the review's
            # "clipped" was half-written words more often than not (CLAUDE.md, 2026-10-09 night).
            found.append(_finding(d.get("beat"), "visual", "screen" if screen else (f.get("kind") or "screen"),
                                  str(f.get("what", ""))[:300], source="frame review",
                                  severity=str(f.get("severity") or "medium"),
                                  repair=None if screen else "report only (the layout probe owns collisions)"))

    beats: dict[str, list] = {}
    whole = []
    for f in found:
        (beats.setdefault(f["beat"], []) if f["beat"] else whole).append(f)
    order = [str(b.get("id")) for _, b in _beats(lesson)]
    beats = {b: beats[b] for b in sorted(beats, key=lambda b: order.index(b) if b in order else 10 ** 6)}
    by_stage = {s: sum(1 for f in found if f["stage"] == s) for s in STAGES}
    serious = [f for f in found if f["severity"] in ("high", "major", "critical")]
    result = {
        "version": 1,
        "status": "pass" if not serious else "needs_repair",
        "findings": len(found),
        "by_stage": by_stage,
        "beats_to_repair": [b for b, fs in beats.items() if any(f["severity"] in ("high", "major", "critical")
                                                                 for f in fs)],
        "repaired_beats": sorted(repaired),
        "beats": beats,
        "lesson": whole,
        "sources": ["storyboard", "reviewer", "stills look", "layout probe", "bounds check", "render checks",
                    "chapter audit", "frame review"],
    }
    try:
        out_file = root / dest
        out_file.parent.mkdir(parents=True, exist_ok=True)
        out_file.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    except OSError:
        pass
    return result


def line(result: dict) -> str:
    """One log line for a report."""
    stages = ", ".join(f"{s} {n}" for s, n in result["by_stage"].items() if n)
    todo = ", ".join(result["beats_to_repair"]) or "none"
    return f"[qa] {result['status']}: {result['findings']} finding(s) ({stages or 'none'}); beats to repair: {todo}"
