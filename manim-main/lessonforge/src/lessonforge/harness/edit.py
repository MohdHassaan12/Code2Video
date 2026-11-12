"""A person in the loop: read a lesson's script, change it, and have it made again (2026-11-02).

The owner asked for "edit options and a human in the loop". Two ways in, one path:

* **Check the script first.** A lesson started with ``stop_after: "verify"`` stops once its script is written and
  reviewed: nothing is narrated or filmed. The person reads it (``editable``), changes what they want and approves.
* **Edit a finished video.** The same screen on a finished lesson: change a beat's words, ask for a different
  picture on a beat, or take a beat out, then make it again.

Either way the result is a NEW lesson (``service.edit_lesson``); the one it came from is never changed. Its brief
carries ``edit_of`` (the source lesson) and ``edits`` (what was changed), both set by the route only.

What is done to the script is small and checked by code:

* words: the beat says exactly what the person wrote (cleaned for speech the way every beat is, ``writer.discipline``);
  the steps that pointed at its old words are moved to the new ones, or the beat's screen is designed again;
* picture: a beat with a note ("show the beaker cracking", "use a number line") has its screen designed again by the
  same director that designs a pasted script's screen (``scripted.DIRECT_SYSTEM``), the note given as the author's
  DIRECTION, never able to touch a spoken word;
* remove: the beat is taken out (a part left with no beats goes with it; at least one beat must stay).

Nothing else of the lesson is written again. A beat whose words changed is reviewed in report-only mode afterwards
(the person's words are kept, findings are shown), so a slip is pointed out, not silently fixed.
"""
from __future__ import annotations

import copy
import json
import re
from pathlib import Path

from ..longform.contract import Lesson
from . import critic, scripted, writer

EDIT_OF = "edit_of"           # brief key: the lesson this one is an edit of (set by the route only)
EDITS = "edits"               # brief key: what was changed, by beat id
MAX_NOTE = 400                # characters in a picture note
MAX_WORDS = scripted.MAX_BEAT_WORDS * 2

#: Files a lesson's script can be read back from, best first. ``lesson.reviewed.json`` is the script as it stood after
#: its review and before the screen passes (sequence, annotate, look) worked on it: an edit starts there, so those
#: passes run once on the edited lesson rather than twice. A lesson stopped after its review has only ``lesson.json``,
#: which is that same reviewed script. Lessons made before 2026-11-02 have neither, and start from ``lesson.json``.
SOURCES = ("lesson.reviewed.json", "lesson.json")


class EditError(ValueError):
    """The edit asked for cannot be made (unknown beat, empty words, nothing left). Its text is shown to the person."""


def source_file(root: Path) -> Path | None:
    for name in SOURCES:
        if (root / name).is_file():
            return root / name
    return None


def _beats(lesson: dict):
    for chapter in lesson.get("chapters") or []:
        for beat in chapter.get("beats") or []:
            yield chapter, beat


def _figure_label(figure) -> str:
    """A few words on what a beat shows, for a person reading the script (not for any model)."""
    if not isinstance(figure, dict):
        return ""
    kind = str(figure.get("kind") or "")
    for key in ("describe", "ask", "title", "caption", "equation", "use"):
        if figure.get(key):
            return f"{kind}: {str(figure[key])[:160]}"
    return kind


def editable(lesson: dict, verification: dict | None = None) -> dict:
    """The script as a person reads and edits it: parts, beats, what is said and what is shown, what the review said."""
    findings: dict[str, list[str]] = {}
    for finding in (verification or {}).get("findings") or []:
        if isinstance(finding, dict) and finding.get("beat"):
            what = str(finding.get("what") or finding.get("issue") or "").strip()
            if what:
                findings.setdefault(str(finding["beat"]), []).append(
                    (f"[{finding['severity']}] " if finding.get("severity") else "") + what[:300])
    chapters = []
    for chapter in lesson.get("chapters") or []:
        beats = []
        for beat in chapter.get("beats") or []:
            beats.append({
                "id": beat["id"], "narration": beat["narration"], "words": len(beat["narration"].split()),
                "visual": str(beat.get("visual") or ""), "figure": _figure_label(beat.get("figure")),
                "shows": [str(s.get("show") or "") for s in beat.get("steps") or [] if s.get("show")][:6],
                "quiz": (beat.get("quiz") or {}).get("question") if isinstance(beat.get("quiz"), dict) else None,
                "findings": findings.get(str(beat["id"]), []),
            })
        chapters.append({"id": chapter.get("id"), "title": chapter.get("title") or "", "beats": beats})
    return {"title": lesson.get("title") or "", "thesis": lesson.get("thesis") or "", "language": lesson.get("language"),
            "chapters": chapters, "beats": sum(len(c["beats"]) for c in chapters),
            "words": sum(b["words"] for c in chapters for b in c["beats"])}


def clean(lesson: dict, edits) -> dict[str, dict]:
    """The person's edits, checked against the lesson: ``{beat id: {"narration"?, "note"?, "remove"?}}``.

    Only real changes are kept (words identical to the beat's are not an edit). ``EditError`` with a reason a person
    can act on when something cannot be done.
    """
    if edits is None:
        return {}
    if not isinstance(edits, dict):
        raise EditError("edits must be an object of beat id → change")
    known = {beat["id"]: beat for _, beat in _beats(lesson)}
    out: dict[str, dict] = {}
    for raw_id, change in edits.items():
        beat_id = critic.beat_id(raw_id, set(known))
        if beat_id not in known:
            raise EditError(f"there is no beat {raw_id!r} in this lesson")
        if not isinstance(change, dict):
            raise EditError(f"the change to beat {beat_id} must be an object")
        entry: dict = {}
        if change.get("remove"):
            entry["remove"] = True
        else:
            if change.get("narration") is not None:
                words = re.sub(r"\s+", " ", str(change["narration"])).strip()
                if not words:
                    raise EditError(f"beat {beat_id} would have nothing to say: to take it out, remove it")
                if len(words.split()) > MAX_WORDS:
                    raise EditError(f"beat {beat_id} is {len(words.split())} words; at most {MAX_WORDS} fit one beat")
                if words != re.sub(r"\s+", " ", known[beat_id]["narration"]).strip():
                    entry["narration"] = words
            note = re.sub(r"\s+", " ", str(change.get("note") or "")).strip()
            if note:
                entry["note"] = note[:MAX_NOTE]
        if entry:
            out[beat_id] = entry
    if out and len([b for b in known if not out.get(b, {}).get("remove")]) == 0:
        raise EditError("every beat would be removed: at least one must stay")
    return out


def _one_beat(beat: dict, narration: str, brief: dict) -> dict:
    """The beat with new words, cleaned the way ``writer.discipline`` cleans every beat, its steps moved onto them."""
    raw = {"chapters": [{"title": "x", "beats": [{**beat, "narration": narration}]}]}
    made = writer.discipline(raw, brief, scripted.FRAMEWORK)["chapters"]
    if not made or not made[0]["beats"]:
        raise EditError(f"beat {beat['id']} has nothing that can be spoken")
    new = made[0]["beats"][0]
    out = copy.deepcopy(beat)
    out["narration"] = new["narration"]
    out["steps"] = new["steps"] or scripted.plain_steps(new["narration"])
    out["board_text"], out["equation"] = new.get("board_text", ""), new.get("equation", "")
    out["thinking_pause_seconds"] = new.get("thinking_pause_seconds", 0.0)
    if not out["narration"].rstrip().endswith(scripted._ASKS):
        out.pop("quiz", None)                     # a question the words no longer ask is not shown
        out["thinking_pause_seconds"] = 0.0
    return out


def _redesign(lesson: dict, wanted: dict[str, str], brief: dict, llm, log=print) -> dict[str, dict]:
    """New screens for the beats in ``wanted`` (id → the person's note), from the director that designs a pasted
    script's screen. One call; a beat it leaves bare keeps its old screen. Returns id → the director's entry."""
    if not wanted or llm is None:
        return {}
    chapters = [{"title": c.get("title") or "", "beats": [{"id": b["id"], "narration": b["narration"],
                                                          "direction": wanted.get(b["id"], "")} for b in c["beats"]]}
                for c in lesson["chapters"]]
    current = {b["id"]: {k: b.get(k) for k in ("visual", "figure", "steps") if b.get(k)}
               for _, b in _beats(lesson) if b["id"] in wanted}
    prompt = (f"{scripted._context(brief)}\n\nVIDEO: {lesson.get('title', '')} — {lesson.get('thesis', '')}\n\n"
              f"THE WHOLE SCRIPT, for context ([id] marks a beat, ## a part, DIRECTION is what the person asked for):\n"
              f"{scripted._listing(chapters, clip=0, mark=lambda b: b['id'] in wanted)}\n\n"
              "A person watching the video asked for these beats' screens to change. Their DIRECTION is the reason: "
              "follow it. The other beats are not yours to change. The screen each one has now (keep what the direction "
              "does not ask to change, keep its picture when the direction is only about the words on screen):\n"
              f"{json.dumps(current, ensure_ascii=False)[:6000]}\n\n"
              f"Design the screen for these beats, every one of them: {', '.join(wanted)}\n\nJSON shape: {scripted._BEAT_SHAPE}")
    try:
        answer = llm(prompt, scripted.DIRECT_SYSTEM) or {}
    except Exception as exc:  # noqa: BLE001 - BudgetExceeded included: the caller decides
        if type(exc).__name__ == "BudgetExceeded":
            raise
        log(f"[edit] the screen could not be designed again ({type(exc).__name__}: {str(exc)[:120]}); the old one is kept")
        return {}
    known = set(wanted)
    out: dict[str, dict] = {}
    for entry in (answer.get("beats") or []) if isinstance(answer, dict) else []:
        if isinstance(entry, dict):
            beat_id = critic.beat_id(entry.get("id"), known)
            if beat_id in known and scripted._has_screen(entry) and beat_id not in out:
                out[beat_id] = entry
    if isinstance(answer, dict) and isinstance(answer.get("shapes"), dict):
        shapes = lesson.setdefault("shapes", {})
        for name, shape in answer["shapes"].items():
            if isinstance(shape, dict) and str(name) not in shapes:
                shapes[str(name)] = shape
    return out


def _with_screen(beat: dict, entry: dict, brief: dict) -> dict:
    """The beat with the director's new screen, cleaned by ``writer.discipline`` (figure kinds, steps, clamps)."""
    raw = {"chapters": [{"title": "x", "beats": [{**beat, "visual": entry.get("visual") or beat.get("visual", ""),
                                                  "figure": entry.get("figure"), "steps": entry.get("steps") or [],
                                                  "quiz": entry.get("quiz") if beat["narration"].rstrip().endswith(scripted._ASKS) else None}]}]}
    new = writer.discipline(raw, brief, scripted.FRAMEWORK)["chapters"][0]["beats"][0]
    out = copy.deepcopy(beat)
    for key in ("visual", "steps", "board_text", "equation"):
        out[key] = new.get(key, out.get(key))
    for key in ("figure", "figure_issues", "quiz"):
        if new.get(key) is not None:
            out[key] = new[key]
        else:
            out.pop(key, None)
    out.pop("sequence", None)                      # a drawing sequence planned for the old picture
    if not out["steps"] and not out.get("figure"):
        out["steps"] = scripted.plain_steps(out["narration"])
    return out


def apply(lesson: dict, edits: dict[str, dict], brief: dict, llm=None, log=print) -> tuple[dict, dict]:
    """The lesson with the person's edits made. Returns (lesson, summary). ``edits`` from ``clean``."""
    lesson = copy.deepcopy(lesson)
    summary = {"removed": [], "words": [], "screens": [], "screens_kept": []}
    if not edits:
        return lesson, summary
    for chapter in lesson["chapters"]:
        kept = []
        for beat in chapter["beats"]:
            change = edits.get(beat["id"]) or {}
            if change.get("remove"):
                summary["removed"].append(beat["id"])
                continue
            if change.get("narration"):
                beat = _one_beat(beat, change["narration"], brief)
                summary["words"].append(beat["id"])
            kept.append(beat)
        chapter["beats"] = kept
    lesson["chapters"] = [c for c in lesson["chapters"] if c["beats"]]
    if not lesson["chapters"]:
        raise EditError("every beat would be removed: at least one must stay")
    # A beat with a note is designed again; so is one whose new words left its old steps pointing at nothing.
    wanted = {}
    for _, beat in _beats(lesson):
        change = edits.get(beat["id"]) or {}
        if change.get("note"):
            wanted[beat["id"]] = change["note"]
        elif change.get("narration"):
            anchored = [s for s in beat.get("steps") or [] if s.get("say")]
            if not anchored and not beat.get("figure"):
                wanted[beat["id"]] = "The words of this beat were changed: show what they now say."
    designed = _redesign(lesson, wanted, brief, llm, log=log)
    for chapter in lesson["chapters"]:
        for k, beat in enumerate(chapter["beats"]):
            if beat["id"] in designed:
                chapter["beats"][k] = _with_screen(beat, designed[beat["id"]], brief)
                summary["screens"].append(beat["id"])
            elif beat["id"] in wanted:
                summary["screens_kept"].append(beat["id"])
    lesson["continuity"] = writer.continuity(lesson)
    lesson.setdefault("edited", []).append({k: v for k, v in summary.items() if v})
    Lesson.model_validate(lesson)
    log("[edit] " + "; ".join(f"{name}: {', '.join(ids)}" for name, ids in (
        ("words changed", summary["words"]), ("new screen", summary["screens"]), ("removed", summary["removed"]),
        ("screen kept (no new design)", summary["screens_kept"])) if ids) or "[edit] no change: the script is made as it is")
    return lesson, summary
