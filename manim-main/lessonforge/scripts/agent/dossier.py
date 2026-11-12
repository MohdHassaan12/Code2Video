"""One lesson's evidence, stage by stage, in one folder a reviewer (person or Claude Code agent) can read.

    python scripts/agent/dossier.py <job id | lesson folder> [-o OUT] [--per-beat 3] [--no-frames]

Writes, into OUT (default ``<lesson>/dossier/``):
  dossier.md     what each stage produced and what it reported (request, research, script, verify, visuals,
                 compose/sequence/annotate, speech, render, check, repair, review), the log lines that say
                 something was skipped or fell back, and the spend in the lesson's time window
  dossier.json   the same numbers as data (``scripts/agent/compare.py`` reads two of them)
  frames.md      for every beat: what the narrator says at each sampled instant and what the script meant
                 to be on screen then, next to the sheet that holds the frames
  sheets/chapter_NN.jpg   the frames of one chapter, one row per beat (start, the key moment, end)

No model is called and nothing is spent: it only reads the lesson folder, the ledger and the video.
The frame instants are the ones ``harness/vision_review.sample_points`` picks (when the key step should
be visible), plus one just after the beat starts and one just before it ends, so a reader can see what
changed while the beat was spoken.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from collections import defaultdict
from pathlib import Path

ALARMS = ("skipped", "failed", "fallback", "unavailable", "rejected", "refused", "timed out", "error",
          "silent", "placeholder", "none of the", "degraded", "not paid", "could not")


def _read(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def lesson_dirs() -> list[tuple[str, Path]]:
    """Where lessons are, in the order a job id is looked up: ``own`` (``<workspace>/lessons``: for the improver,
    its own workspace, whose lessons never enter the app's list), then ``live`` (``$IMPROVER_LIVE_HOME/lessons``,
    the app's list) when the improver set it and it is another folder."""
    from lessonforge import paths
    own = paths.sub("lessons", create=False)
    dirs = [("own", own)]
    live = os.getenv("IMPROVER_LIVE_HOME", "").strip()
    if live:
        live_dir = (Path(live).expanduser() / "lessons").resolve()
        if live_dir != own.resolve():
            dirs.append(("live", live_dir))
    return dirs


def find_lesson(arg: str) -> Path:
    given = Path(arg)
    if given.is_dir():
        return given.resolve()
    looked = []
    for _, folder in lesson_dirs():
        root = folder / arg
        if root.is_dir():
            return root
        looked.append(str(root))
    sys.exit(f"no lesson folder for {arg!r} (looked in {' and '.join(looked)})")


def spend_window(start: float | None, end: float | None) -> dict:
    """Ledger rows written while the lesson was being made, by what they were for and by model.

    The ledger carries no lesson id, so this is the time window between the job's creation and its last
    save: anything else that spent in that window (another lesson, a test) is counted too.
    """
    if not start or not end:
        return {}
    try:
        from lessonforge import spend
        rows = [r for r in spend.entries() if start - 1 <= float(r.get("at") or 0) <= end + 5]
    except Exception as exc:  # noqa: BLE001 - a dossier without spend is still a dossier
        return {"error": f"{type(exc).__name__}: {exc}"}
    by_note, by_model = defaultdict(float), defaultdict(float)
    for r in rows:
        by_note[(r.get("note") or r.get("kind") or "?").split(":")[0]] += float(r.get("cost") or 0)
        by_model[r.get("model") or "?"] += float(r.get("cost") or 0)
    return {"calls": len(rows), "total_usd": round(sum(by_note.values()), 4),
            "by_note": {k: round(v, 4) for k, v in sorted(by_note.items(), key=lambda kv: -kv[1])},
            "by_model": {k: round(v, 4) for k, v in sorted(by_model.items(), key=lambda kv: -kv[1])},
            "window_caveat": "time window, not a lesson id: anything else spending at the same time is included"}


def _beats(lesson: dict) -> list[dict]:
    return [b for c in lesson.get("chapters") or [] for b in c.get("beats") or []]


def summarise(root: Path) -> dict:
    job = _read(root / "job.json") or {}
    lesson = _read(root / "lesson.json") or _read(root / "lesson.draft.json") or {}
    draft = _read(root / "lesson.draft.json") or {}
    checks = _read(root / "output" / "final_checks.json") or {}
    vision = _read(root / "output" / "vision_review.json") or {}
    card = _read(root / "teaching_card.json")
    brief = job.get("brief") or lesson.get("brief") or {}
    ver = job.get("verification") or lesson.get("verification") or {}
    cont = job.get("continuity") or lesson.get("continuity") or {}
    beats = _beats(lesson)
    figures = defaultdict(int)
    for b in beats:
        figures[(b.get("figure") or {}).get("kind") or "none"] += 1
    unresolved = [f for f in ver.get("findings") or [] if not f.get("resolved")]
    end = (root / "job.json").stat().st_mtime if (root / "job.json").exists() else None
    progress = job.get("progress") or []
    s = {
        "lesson": str(root), "job_id": job.get("job_id") or root.name, "status": job.get("status"),
        "stage": job.get("stage"), "error": job.get("error"), "title": job.get("title") or lesson.get("title"),
        "brief": brief,
        "minutes_asked": brief.get("duration_minutes"),
        "research": {"card": bool(card), "big_idea": ((card or {}).get("big_idea") or {}).get("text")},
        "script": {"generated_by": job.get("generated_by") or lesson.get("generated_by"),
                   "chapters": len(lesson.get("chapters") or []), "beats": len(beats),
                   "words": cont.get("words"), "target_words": cont.get("target_words"),
                   "warnings": cont.get("warnings") or [], "figures": dict(figures),
                   "beats_changed_by_review": sum(1 for a, b in zip(_beats(draft), beats)
                                                  if a.get("narration") != b.get("narration")) if draft else None},
        "verify": {"status": ver.get("status"), "scores": ver.get("scores"),
                   "critical_unresolved": ver.get("critical_unresolved"),
                   "claims_checked": ver.get("claims_checked"), "claims_failed": len(ver.get("claims_failed") or []),
                   "unresolved_findings": len(unresolved), "questions": ver.get("questions")},
        "visuals": job.get("scenes"),
        "composition": job.get("composition"), "drawn_with_words": job.get("drawn_with_words"),
        "annotated": job.get("annotated"), "repaint": job.get("repaint"), "drawing_look": job.get("drawing_look"),
        "speech": {"voice": job.get("voice"), "voice_note": job.get("voice_note"), "alignment": job.get("alignment")},
        "check": {"status": checks.get("status"), "duration_seconds": checks.get("duration_seconds"),
                  "bounds_violations": checks.get("bounds_violations"),
                  "layout_counted": (checks.get("layout_findings") or {}).get("counted"),
                  "layout_reported_only": (checks.get("layout_findings") or {}).get("reported_only"),
                  "anchor_timing": checks.get("anchor_timing"), "sentence_timing": checks.get("sentence_timing"),
                  "animatic_chapters": checks.get("animatic_chapters"),
                  "failed_checks": [c.get("name") for c in checks.get("checks") or [] if not c.get("passed")]},
        "screen_repair": job.get("screen_repair"),
        "review": {"frames": vision.get("frames"), "findings": vision.get("findings"), "by_kind": vision.get("by_kind"),
                   "frames_showing_intended": vision.get("frames_showing_intended")},
        "spend": spend_window(job.get("created"), end),
        "alarms": [line for line in progress if any(a in line.lower() for a in ALARMS)],
        "_unresolved": unresolved[:30],
        "_vision_detail": [{"beat": r.get("beat"), "at": r.get("at"), "findings": r.get("findings")}
                           for r in vision.get("detail") or [] if r.get("findings")][:40],
        "_layout_detail": (checks.get("layout_findings") or {}).get("detail", [])[:30],
        "_progress_tail": progress[-25:],
    }
    return s


def _md(s: dict) -> str:
    j = lambda x: json.dumps(x, ensure_ascii=False)  # noqa: E731
    out = [f"# Dossier: {s['title']}", "",
           f"- lesson `{s['job_id']}`: **{s['status']}** (stage {s['stage']})" + (f", error: {s['error']}" if s["error"] else ""),
           f"- folder: `{s['lesson']}`", "", "## Request (brief)", "```json", json.dumps(s["brief"], indent=1, ensure_ascii=False)[:3000],
           "```", "", "## research", j(s["research"]), "", "## script", j(s["script"]), "",
           "## verify (critic)", j(s["verify"]), ""]
    if s["_unresolved"]:
        out += ["Unresolved findings:"] + [f"- beat {f.get('beat')}: [{f.get('severity')}] {f.get('what')}" for f in s["_unresolved"]] + [""]
    out += ["## visuals (generated scenes)", j(s["visuals"]), "",
            "## compose / sequence / annotate", j({k: s[k] for k in ("composition", "drawn_with_words", "annotated", "repaint", "drawing_look")}), "",
            "## speech", j(s["speech"]), "", "## render + check", j(s["check"]), ""]
    if s["_layout_detail"]:
        out += ["Layout findings:"] + [f"- {j(f)}" for f in s["_layout_detail"]] + [""]
    out += ["## repair (screen)", j(s["screen_repair"]), "", "## review (the pipeline's own frame judge)", j(s["review"]), ""]
    if s["_vision_detail"]:
        out += [f"- beat {v['beat']} at {v['at']}s: {j(v['findings'])}" for v in s["_vision_detail"]] + [""]
    out += ["## spend in this lesson's window", j(s["spend"]), "", "## log lines that say something was skipped, refused or fell back"]
    out += [f"- {a}" for a in s["alarms"]] or ["- none"]
    out += ["", "## last log lines", "```"] + s["_progress_tail"] + ["```", ""]
    return "\n".join(out)


def _instants(entry: dict, point: dict | None, per_beat: int) -> list[float]:
    start, dur = float(entry["start"]), float(entry["duration"])
    key = float(point["at"]) if point else start + dur * 0.6
    if per_beat <= 1:
        return [key]
    picks = [min(start + 1.0, start + dur * 0.25), key, start + dur - 0.3]
    return sorted({round(t, 2) for t in picks})


def frames(root: Path, out: Path, per_beat: int) -> dict:
    lesson, timeline = _read(root / "lesson.json"), _read(root / "timeline.json")
    checks = _read(root / "output" / "final_checks.json") or {}
    video = root / "output" / str(checks.get("video", ""))
    if not (lesson and timeline and video.is_file()):
        return {"skipped": "no finished video, lesson.json or timeline.json"}
    try:
        from lessonforge.harness import vision_review as vr
        points = {str(p["beat"]): p for p in vr.sample_points(timeline, lesson, vr.shown_at(root, timeline), vr.laid_out(root, timeline))}
    except Exception as exc:  # noqa: BLE001 - fall back to plain instants
        print(f"[dossier] sample_points unavailable ({type(exc).__name__}: {exc}); using plain instants")
        points = {}
    from PIL import Image, ImageDraw
    sheets_dir = out / "sheets"
    sheets_dir.mkdir(parents=True, exist_ok=True)
    md = ["# Frames: what is said, what was meant to show, and what shows", "",
          "Each chapter sheet has one row per beat; the columns are the instants listed below, left to right.", ""]
    by_chapter = defaultdict(list)
    for entry in timeline:
        by_chapter[entry["chapter"]].append(entry)
    tile_w = 480
    with tempfile.TemporaryDirectory() as tmp:
        for chapter, entries in sorted(by_chapter.items()):
            rows = []
            md += [f"## Chapter {chapter}  (sheet: sheets/chapter_{int(chapter):02}.jpg)", ""]
            for entry in entries:
                point = points.get(str(entry["id"]))
                tiles = []
                md.append(f"### beat {entry['id']}  ({entry['start']:.1f}s to {entry['start'] + entry['duration']:.1f}s)")
                for t in _instants(entry, point, per_beat):
                    path = Path(tmp) / f"{entry['id']}_{t}.jpg"
                    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.3f}", "-i", str(video), "-frames:v", "1",
                                    "-vf", f"scale={tile_w}:-1", "-q:v", "4", str(path)], check=False)
                    if path.is_file():
                        tiles.append((t, Image.open(path).convert("RGB")))
                    local = t - float(entry["start"])
                    said = next((x["text"] for x in entry.get("sentences", [])
                                 if x["start"] <= local < x["start"] + x["duration"]), "(silence)")
                    md.append(f"- t={t:.1f}s says: «{said}»")
                if point:
                    md.append(f"- meant to be on screen at the key moment: {point.get('intended')}")
                    if point.get("later"):
                        md.append(f"- comes later in the beat: {point['later']}")
                    if point.get("drawing"):
                        md.append(f"- picture: {json.dumps(point['drawing'], ensure_ascii=False)}")
                md.append("")
                rows.append((entry["id"], tiles))
            if not rows or not any(t for _, t in rows):
                continue
            th = max(img.height for _, tiles in rows for _, img in tiles) if any(t for _, t in rows) else 270
            cols = max(len(t) for _, t in rows)
            band = 18
            sheet = Image.new("RGB", (cols * tile_w, len(rows) * (th + band)), (255, 255, 255))
            draw = ImageDraw.Draw(sheet)
            for r, (beat_id, tiles) in enumerate(rows):
                y = r * (th + band)
                for c, (t, img) in enumerate(tiles):
                    sheet.paste(img, (c * tile_w, y + band))
                    draw.text((c * tile_w + 4, y + 2), f"beat {beat_id}  t={t:.1f}s", fill=(0, 0, 0))
            sheet.save(sheets_dir / f"chapter_{int(chapter):02}.jpg", quality=80)
    (out / "frames.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    return {"sheets": len(list(sheets_dir.glob("*.jpg"))), "beats": len(timeline), "per_beat": per_beat}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("lesson", help="job id (looked up in <workspace>/lessons, then $IMPROVER_LIVE_HOME/lessons) "
                                   "or a lesson folder")
    ap.add_argument("-o", "--out", default=None, help="output folder (default <lesson>/dossier)")
    ap.add_argument("--per-beat", type=int, default=3, help="frames per beat: 1 (key moment) or 3 (start, key, end)")
    ap.add_argument("--no-frames", action="store_true")
    args = ap.parse_args(argv)
    import lessonforge
    root = find_lesson(args.lesson)
    out = Path(args.out) if args.out else root / "dossier"
    out.mkdir(parents=True, exist_ok=True)
    s = summarise(root)
    s["code_from"] = str(Path(lessonforge.__file__).parent)   # which checkout's code made THIS dossier
    s["made_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    if not args.no_frames:
        s["frames"] = frames(root, out, args.per_beat)
    (out / "dossier.json").write_text(json.dumps(s, indent=1, ensure_ascii=False), encoding="utf-8")
    (out / "dossier.md").write_text(_md(s), encoding="utf-8")
    print(f"[dossier] {s['job_id']}: {s['status']}; written to {out}")
    print(f"[dossier] lessonforge code read from {s['code_from']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
