"""Lesson Forge speaks the shared lesson contract (lesson-board ``docs/lesson-contract.md``).

Two directions:

- ``brief_from_scope``: lesson-board sends every video request a ``lesson-board/scope/1`` (objectives, allowed
  concepts, prerequisites, excluded content, length) and a glossary. This turns it into a Lesson Forge brief, so the
  hub can ask this service for a lesson the same way it asks Image Teacher's Video API.
- ``video_timeline``: a finished lesson as ``video-timeline/1`` (one segment per spoken sentence on one clock), the
  shape Image Teacher returns from ``GET /api/v1/videos/{id}/timeline?format=contract``. lesson-board's checks, and
  any benchmark that reads that shape, then work on Lesson Forge videos too.
"""
from __future__ import annotations

import json
from pathlib import Path

SCOPE = "lesson-board/scope/1"
TIMELINE = "video-timeline/1"


def is_scope(brief: dict) -> bool:
    return isinstance(brief.get("scope"), dict) and brief["scope"].get("schema", SCOPE) == SCOPE


def _titles(items) -> list[str]:
    out = []
    for x in items or []:
        t = x.get("title") if isinstance(x, dict) else x
        if t:
            out.append(str(t).strip())
    return out


def brief_from_scope(brief: dict) -> dict:
    """The brief with its ``scope`` (and ``glossary``) turned into the fields the writer reads. Fields the caller
    set itself are kept; the scope fills the rest. The scope stays on the brief as it was sent."""
    scope = brief["scope"]
    out = dict(brief)
    objectives = [str(o).strip().rstrip(".") for o in scope.get("learning_objectives") or [] if str(o).strip()]
    if not out.get("topic"):
        out["topic"] = scope.get("lesson_title") or (objectives[0] if objectives else "")
    if not out.get("goal") and objectives:
        out["goal"] = "; ".join(objectives)
    if not out.get("audience") and scope.get("class"):
        subject = f" {scope['subject']}" if scope.get("subject") else ""
        out["audience"] = f"Class {scope['class']} students (NCERT{subject})"
    if not out.get("subject") and scope.get("chapter_title"):
        out["subject"] = scope["chapter_title"]
    if not out.get("duration_minutes") and scope.get("max_duration_seconds"):
        # the scope gives an upper limit; Lesson Forge's shortest lesson is 3 minutes (intake.MIN_MINUTES)
        out["duration_minutes"] = 3 if scope["max_duration_seconds"] < 360 else 6
    notes = dict(out.get("notes") or {})
    allowed = []
    for c in scope.get("allowed_concepts") or []:
        terms = ", ".join(c.get("key_terms") or [])
        allowed.append(c.get("title", "") + (f" (key terms: {terms})" if terms else ""))
    if allowed:
        notes.setdefault("scope", "Teach only these ideas: " + "; ".join(allowed) + ".")
    if scope.get("prerequisites"):
        notes.setdefault("prerequisites", "Already taught, so name them in a sentence but do not teach them again: "
                         + "; ".join(_titles(scope["prerequisites"])) + ".")
    if scope.get("excluded_content"):
        notes.setdefault("left out", "Later lessons teach these, so do not explain or use them: "
                         + "; ".join(_titles(scope["excluded_content"])) + ".")
    glossary = brief.get("glossary") or []
    if glossary:
        notes.setdefault("words", "Use these words and this notation: " + "; ".join(
            f"{g['term']}" + (f" = {g['meaning']}" if g.get("meaning") else "")
            + (f" (written {g['notation']})" if g.get("notation") else "") for g in glossary if g.get("term")) + ".")
    if notes:
        out["notes"] = notes
    return out


def _sentences(timeline: list) -> list[dict]:
    rows = []
    for beat in timeline:
        start = float(beat.get("start", 0))
        for k, s in enumerate(beat.get("sentences") or []):
            words = s.get("words") or []
            t0 = start + float(s.get("start", 0))
            t1 = start + float(words[-1]["end"]) if words else t0 + 0.35 * len(s.get("text", "").split())
            rows.append({"beat": str(beat.get("id", "")), "chapter": beat.get("chapter"), "k": k,
                         "title": beat.get("chapter_title", ""), "text": s.get("text", ""), "start": t0, "end": t1})
    return rows


def video_timeline(root: str | Path, video_id: str = "") -> dict:
    """``video-timeline/1`` for a finished lesson folder (``lesson.json`` + ``timeline.json``)."""
    root = Path(root)
    lesson = json.loads((root / "lesson.json").read_text(encoding="utf-8"))
    timeline = json.loads((root / "timeline.json").read_text(encoding="utf-8"))
    duration = max((float(b.get("start", 0)) + float(b.get("duration", 0)) for b in timeline), default=0.0)
    beats = {str(b["id"]): b for c in lesson.get("chapters") or [] for b in c.get("beats") or []}
    rows = _sentences(timeline)
    elements, segments = [], []
    for beat in timeline:
        bid = str(beat.get("id", ""))
        b = beats.get(bid, {})
        elements.append({"element_id": f"beat_{bid}", "kind": "equation" if b.get("equation") else "board",
                         "title": beat.get("chapter_title", ""), "parts": []})
    for i, r in enumerate(rows):
        # one clock: each segment ends where the next starts, the last at the end of the video
        end = rows[i + 1]["start"] if i + 1 < len(rows) else max(duration, r["end"])
        b = beats.get(r["beat"], {})
        seg = {"segment_id": f"b{r['beat']}_{r['k'] + 1}", "scene": r["chapter"], "step": r["k"] + 1,
               "role": "explain", "narration": r["text"], "note": r["title"],
               "visual": {"element_id": f"beat_{r['beat']}", "highlight": [], "reveal_state": "none",
                          "reveal_answer": False},
               "timing": {"start": round(r["start"], 3), "end": round(end, 3),
                          "start_ms": int(r["start"] * 1000), "end_ms": int(end * 1000)},
               "highlights": [], "reveals": []}
        if b.get("equation"):
            seg["tex"] = b["equation"]
        segments.append(seg)
    if segments:
        segments[0]["timing"].update(start=0.0, start_ms=0)
    return {"schema": TIMELINE, "video_id": video_id or root.name, "duration": round(duration, 3),
            "title": lesson.get("title", ""), "elements": elements, "segments": segments, "answers": [],
            "objectives": [], "checks": []}
