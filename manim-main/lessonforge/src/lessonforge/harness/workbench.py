"""A lesson on the workbench: draft it, check it, look at it, change it in small steps, film it, measure the film.

The quadrilateral videos of 2026-10-20 were made by hand: a person (Claude in a chat) wrote every word and point,
looked at stills, changed the lesson and filmed it again. Lessonforge drew, voiced and assembled. This module turns
that loop into calls a program can make, so another program can drive it: the MCP server (``lessonforge.mcp_server``)
for Claude in a chat or in Claude Code, and the improver (``harness/improver.py``) for Claude over the API.

Every call but ``draft`` is free: checks are code, stills are manim at low quality, filming uses a local voice, and
the measurements read the video file. A lesson lives in ``<workspace>/workbench/<id>/`` as numbered versions
(``v001.json`` ...), each with what changed it and who, so a run can always go back to its best version.

The edits are small on purpose (``edit``): a beat's fields set, a beat put in or taken out, a shape declared. A
model that answers with a few edits instead of the whole lesson costs a tenth as much and cannot drop a chapter by
accident. After every edit the lesson is checked again by the same code as a fresh draft (``shapes.settle`` fills
``{angle D}`` gaps from the points and refuses claims the points do not make true), so an edit cannot bring in a
wrong value.
"""
from __future__ import annotations

import copy
import json
import re
import shutil
import subprocess
import time
import uuid
from pathlib import Path

from .. import kits, paths
from ..longform.contract import Lesson

BEAT_FIELDS = ("narration", "steps", "figure", "quiz", "thinking_pause_seconds", "depth", "board_text", "equation")
DEFAULT_VOICE = "kokoro:af_heart@0.8"
#: A beat that holds this many sentences with no new on-screen step leaves the picture still for that long.
HELD_SENTENCES = 2
#: Two video frames (sampled at ``SAMPLE_FPS``) differ when this share of pixels changed noticeably.
CHANGED_SHARE = 0.002
SAMPLE_FPS = 2


class WorkbenchError(ValueError):
    """An edit or request that cannot be done; the message says why, in words a model can act on."""


# ---------------------------------------------------------------- storage

def root() -> Path:
    return paths.sub("workbench")


def _folder(lesson_id: str) -> Path:
    if not re.fullmatch(r"[\w.-]{1,80}", str(lesson_id)) or str(lesson_id).startswith("."):
        raise WorkbenchError(f"no lesson {lesson_id!r}")
    folder = root() / lesson_id
    if not folder.is_dir():
        raise WorkbenchError(f"no lesson {lesson_id!r} on the workbench")
    return folder


def _versions(folder: Path) -> list[Path]:
    return sorted(folder.glob("v[0-9][0-9][0-9].json"))


def _log(folder: Path, record: dict) -> None:
    with (folder / "history.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), **record}, ensure_ascii=False) + "\n")


def _save(folder: Path, lesson: dict, note: dict) -> int:
    number = len(_versions(folder)) + 1
    (folder / f"v{number:03}.json").write_text(json.dumps(lesson, indent=1, ensure_ascii=False), encoding="utf-8")
    _log(folder, {"version": number, **note})
    return number


def _settled(lesson: dict) -> dict:
    """A shape lesson with its gaps filled and its ``use`` figures expanded (``shapes.settle``), as every edit leaves it.

    A lesson put on the bench straight from a model (``{angle D}`` gaps, ``{"use": "arrow"}`` figures) used to be
    saved as written, so its first check, craft and preview saw unfilled gaps and figures with no points. Idempotent:
    a lesson that is already settled comes back unchanged. Faults are reported by ``check``, not raised here.
    """
    if lesson.get("shapes") or any(isinstance(b.get("figure"), dict) and (b["figure"].get("use") or b["figure"].get("kind") == "shape")
                                   for _, b in _beats(lesson)):
        from . import shapes
        lesson, _ = shapes.settle(lesson)
    return kits.settle_active(lesson)          # a served subject kit's gaps (motion), filled the same way


def add(lesson: dict, name: str | None = None, source: str = "given") -> dict:
    """Put a lesson on the workbench (a draft, a lesson made elsewhere). Returns its id and first check."""
    lesson = _settled(_normalise(copy.deepcopy(lesson)))
    Lesson.model_validate(lesson)
    slug = re.sub(r"[^a-z0-9]+", "-", str(name or lesson.get("title") or "lesson").lower()).strip("-")[:40] or "lesson"
    lesson_id = f"{slug}-{uuid.uuid4().hex[:6]}"
    folder = root() / lesson_id
    folder.mkdir(parents=True)
    _save(folder, lesson, {"by": source, "what": "added"})
    return {"lesson_id": lesson_id, **check(lesson_id)}


def load(lesson_id: str, version: int | None = None) -> dict:
    folder = _folder(lesson_id)
    found = _versions(folder)
    if not found:
        raise WorkbenchError(f"lesson {lesson_id!r} has no versions")
    file = found[-1] if version is None else folder / f"v{int(version):03}.json"
    if not file.is_file():
        raise WorkbenchError(f"lesson {lesson_id!r} has no version {version}")
    return json.loads(file.read_text(encoding="utf-8"))


def history(lesson_id: str) -> list[dict]:
    file = _folder(lesson_id) / "history.jsonl"
    return [json.loads(line) for line in file.read_text(encoding="utf-8").splitlines() if line.strip()] if file.is_file() else []


def lessons() -> list[dict]:
    out = []
    for folder in sorted(root().iterdir()) if root().is_dir() else []:
        found = _versions(folder)
        if found:
            title = json.loads(found[-1].read_text(encoding="utf-8")).get("title", "")
            out.append({"lesson_id": folder.name, "title": title, "versions": len(found)})
    return out


# ---------------------------------------------------------------- drafting (the one paid call)

def draft_pack(pack_file: str, unit: int, language: str = "en-US", llm=None, log=print) -> dict:
    """A unit of a teaching pack written by lessonforge's own pack writer (``harness/pack.py``), put on the bench."""
    from . import pack, writer
    text = Path(pack_file).read_text(encoding="utf-8")
    lesson = pack.lesson_for(pack.brief_for(text, int(unit), language), llm or writer.default_llm(), log=log)
    return add(lesson, name=f"unit{unit}", source="pack writer")


def units(pack_file: str) -> list[dict]:
    from . import pack
    return [{"unit": u["number"], "title": u["title"], "sections": [s["title"] for s in u["sections"]]}
            for u in pack.units(Path(pack_file).read_text(encoding="utf-8"))]


# ---------------------------------------------------------------- checks (free)

def _beats(lesson: dict) -> list[tuple[int, dict]]:
    return [(ch.get("id"), b) for ch in lesson.get("chapters") or [] for b in ch.get("beats") or []]


def _sentences(text: str) -> list[str]:
    return [s for s in re.split(r"(?<=[.?!])\s+", str(text).strip()) if s]


def _norm(text: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9 ]", " ", str(text).lower()).split())


def _expected_fault(issue: str, lesson: dict) -> bool:
    """A wrong quiz option that names a number the picture does not show is the point of the option.

    A pack lesson is written with gaps ({360 - angle D}); once filled, the re-check cannot tell a deliberate wrong
    answer from a typed number, and a model told to "fix" it would remove the distractor that teaches the mistake.
    """
    if kits.is_expected_fault(issue, lesson):          # a served kit's own matcher (kits.base.STRAY_RE)
        return True
    m = re.match(r"beat (\d+) \(chapter \d+\) quiz option (\d+): says .* which the picture does not show", issue)
    if not m:
        return False
    beats = [b for _, b in _beats(lesson)]
    k = int(m.group(1)) - 1
    quiz = beats[k].get("quiz") if 0 <= k < len(beats) else None
    return isinstance(quiz, dict) and int(m.group(2)) - 1 != int(quiz.get("answer_index", -1))


def craft(lesson: dict) -> dict:
    """How the lesson will move, read from its script alone (no render): what makes a picture stand still.

    * a sentence with no step starting in it shows the same screen as the sentence before it;
    * a beat whose figure is the same as the beat before it changes nothing when it starts;
    * on-screen words longer than 9 words are read instead of listened to.
    """
    held, beats_still, long_show, sentences, steps = [], [], [], 0, 0
    previous = None
    for chapter, b in _beats(lesson):
        said = _sentences(b.get("narration", ""))
        sentences += len(said)
        starts = [_norm(s.get("say", "")) for s in b.get("steps") or []]
        steps += len(starts)
        run = 0
        for s in said:
            if any(st and st in _norm(s) for st in starts):
                run = 0
            else:
                run += 1
                if run == HELD_SENTENCES:
                    held.append(b["id"])
        fig = json.dumps(b.get("figure"), sort_keys=True) if b.get("figure") else None
        if fig is not None and fig == previous and not b.get("quiz"):
            beats_still.append(b["id"])
        previous = fig
        long_show += [f"{b['id']}: {s.get('show')!r}" for s in b.get("steps") or [] if len(str(s.get("show", "")).split()) > 9]
    beats = _beats(lesson)
    story = _story(lesson)
    return {"story_stage_talk": story["stage_talk"], "story_out_of_band": story["out_of_band"], "beats": len(beats), "sentences": sentences, "steps": steps,
            "screen_changes_per_sentence": round(steps / sentences, 2) if sentences else 0.0,
            "beats_with_held_sentences": sorted(set(held)), "beats_same_picture_as_before": beats_still,
            "long_screen_words": long_show,
            "words": sum(len(str(b.get("narration", "")).split()) for _, b in beats),
            "questions": sum(1 for _, b in beats if b.get("quiz"))}


def _story(lesson: dict) -> dict:
    """The story framework's free checks (``storyflow``, from the explainer benchmark): lines that say the lesson's
    plan aloud, and the flow measures that fall outside where good explainers fall (p10-p90)."""
    from . import storyflow
    stage = [f"{f['beat']}: {f['what']}" for f in storyflow.story_gate(lesson)]
    try:
        rows = storyflow.report(storyflow.lesson_sentences(lesson)).get("measures") or {}
    except Exception:  # noqa: BLE001 - a measure that cannot be taken is not a fault
        rows = {}
    out = [f"{k}: {v['value']:.2f} is {v['where']} (good explainers {v['p10']:.2f}-{v['p90']:.2f})"
           for k, v in rows.items() if isinstance(v, dict) and v.get("where") not in (None, "in range")
           and v.get("p10") is not None and v.get("p90") is not None]
    return {"stage_talk": stage, "out_of_band": out}


def faults_of(lesson: dict) -> list[str]:
    """Every fault code finds: the lesson contract, and for a geometry lesson every value and claim (``shapes``)."""
    from . import pack
    try:
        Lesson.model_validate(lesson)
    except Exception as exc:  # noqa: BLE001 - pydantic's message is what the model needs
        return [f"lesson contract: {str(exc)[:600]}"]
    one = kits.mixed(lesson)
    if one:                    # LESSONFORGE_KITS_MIXED off: ONE clear fault, not the false ones each checker would add
        return [one]           # (on, each kit checks its own beats and the others stay quiet about them)
    if lesson.get("shapes") or any((b.get("figure") or {}).get("kind") == "shape" for _, b in _beats(lesson)):
        _, issues = pack.faults(lesson)
    else:
        issues = pack.structure_issues(lesson)
    issues = [i for i in issues if not _expected_fault(i, lesson)]
    return issues + kits.lesson_faults(lesson)         # a served kit's claims and typed values (already without the expected)


def check(lesson_id: str) -> dict:
    lesson = load(lesson_id)
    return {"faults": faults_of(lesson), "craft": craft(lesson), "versions": len(_versions(_folder(lesson_id)))}


# ---------------------------------------------------------------- edits

def _normalise(lesson: dict) -> dict:
    """Steps get the fields the writer's own steps carry (a step written by an edit or by hand may lack them)."""
    for _, b in _beats(lesson):
        for st in b.get("steps") or []:
            st.setdefault("kind", "point")
            st.setdefault("highlight", st["kind"] == "key")
    return lesson


def _find(lesson: dict, beat_id: str) -> tuple[dict, int]:
    for ch in lesson.get("chapters") or []:
        for k, b in enumerate(ch.get("beats") or []):
            if str(b.get("id")) == str(beat_id):
                return ch, k
    raise WorkbenchError(f"no beat {beat_id!r} (beats are {[b['id'] for _, b in _beats(lesson)]})")


def _new_id(lesson: dict, after: str) -> str:
    taken = {str(b.get("id")) for _, b in _beats(lesson)}
    for letter in "abcdefghij":
        if f"{after}{letter}" not in taken:
            return f"{after}{letter}"
    raise WorkbenchError(f"too many beats inserted after {after}")


def apply_edits(lesson: dict, edits: list[dict]) -> dict:
    """``lesson`` with ``edits`` made, in order. Each edit is one of:

    * ``{"op": "set_beat", "beat": "04", "fields": {"narration": ..., "steps": [...], "figure": {...}, "quiz": ...}}``
      (a field set to null is removed);
    * ``{"op": "insert_beat", "after": "04", "beat": {"narration": ..., "steps": [...], "figure": ...}}``;
    * ``{"op": "delete_beat", "beat": "04"}``;
    * ``{"op": "set_shape", "name": "arrow", "shape": {"points": {...}, "polygon": "ABCD", "is": ["concave"]}}``
      (a shape a figure can then ``"use"``).
    """
    out = copy.deepcopy(lesson)
    extra_ops = kits.edit_ops()               # ops a served kit adds; {} today, so the message below stays as it was
    if not isinstance(edits, list) or not edits:
        raise WorkbenchError("edits must be a non-empty list")
    for n, e in enumerate(edits, start=1):
        if not isinstance(e, dict):
            raise WorkbenchError(f"edit {n} is not an object")
        op = e.get("op")
        if op == "set_beat":
            ch, k = _find(out, e.get("beat"))
            fields = e.get("fields") or {}
            if not fields:
                raise WorkbenchError(f"edit {n}: set_beat needs \"fields\" with what to change (it changed nothing)")
            bad = [f for f in fields if f not in BEAT_FIELDS]
            if bad:
                raise WorkbenchError(f"edit {n}: fields {bad} cannot be set (allowed: {list(BEAT_FIELDS)})")
            for f, v in fields.items():
                if v is None:
                    ch["beats"][k].pop(f, None)
                else:
                    ch["beats"][k][f] = v
        elif op == "insert_beat":
            ch, k = _find(out, e.get("after"))
            beat = dict(e.get("beat") or {})
            bad = [f for f in beat if f not in BEAT_FIELDS + ("id",)]
            if bad or not beat.get("narration"):
                raise WorkbenchError(f"edit {n}: a new beat needs narration and only these fields: {list(BEAT_FIELDS)}")
            template = {k2: v for k2, v in ch["beats"][k].items() if k2 not in BEAT_FIELDS}
            beat = {**template, "steps": [], **beat, "id": _new_id(out, str(e["after"]))}
            beat.setdefault("thinking_pause_seconds", 0.0)
            ch["beats"].insert(k + 1, beat)
        elif op == "delete_beat":
            ch, k = _find(out, e.get("beat"))
            if len(ch["beats"]) == 1:
                raise WorkbenchError(f"edit {n}: beat {e.get('beat')} is its chapter's only beat")
            del ch["beats"][k]
        elif op == "set_shape":
            name, shape = str(e.get("name") or ""), e.get("shape")
            if not name or not isinstance(shape, dict):
                raise WorkbenchError(f"edit {n}: set_shape needs a name and a shape")
            from ..kits.geometry import declare_shape
            declare_shape(out, name, shape)       # beats that show this shape are pointed at the new one
        elif op in extra_ops:
            try:
                extra_ops[op](out, e)
            except kits.KitError as exc:
                raise WorkbenchError(f"edit {n}: {exc}") from exc
        else:
            more = "".join(f", {x}" for x in extra_ops)
            raise WorkbenchError(f"edit {n}: unknown op {op!r} (set_beat, insert_beat, delete_beat, set_shape{more})")
    _normalise(out)
    if out.get("shapes") or any((b.get("figure") or {}).get("use") for _, b in _beats(out)):
        from . import shapes
        out, _ = shapes.settle(out)           # gaps filled and "use" expanded, exactly as for a fresh draft
    out = kits.settle_active(out, after_edit=True)      # the gaps of a served kit's figure, filled the same way
    try:
        Lesson.model_validate(out)
    except Exception as exc:  # noqa: BLE001
        raise WorkbenchError(f"the edited lesson breaks the lesson contract: {str(exc)[:600]}") from exc
    return out


def edit(lesson_id: str, edits: list[dict], by: str = "claude", why: str = "", keep_if_worse: bool = False) -> dict:
    """Make the edits, check the result, and keep it as a new version unless it has more faults than before."""
    folder = _folder(lesson_id)
    before = load(lesson_id)
    after = apply_edits(before, edits)
    old, new = faults_of(before), faults_of(after)
    if len(new) > len(old) and not keep_if_worse:
        return {"kept": False, "faults": new, "faults_before": len(old),
                "note": "not kept: the edit brought in faults; fix them in the same edit list and send it again"}
    number = _save(folder, after, {"by": by, "what": "edit", "why": why, "edits": edits})
    return {"kept": True, "version": number, "faults": new, "craft": craft(after)}


def revert(lesson_id: str, version: int, by: str = "claude") -> dict:
    folder = _folder(lesson_id)
    lesson = load(lesson_id, version)
    number = _save(folder, lesson, {"by": by, "what": f"back to version {version}"})
    return {"version": number, **check(lesson_id)}


# ---------------------------------------------------------------- looking (free)

def film_layout(lesson: dict) -> dict:
    """A copy of ``lesson`` carrying the look the FILM will give it, for a preview only (never saved).

    A film overwrites any stored look: ``service`` writes ``look.for_new`` for a new job and then ``compose.settle`` picks
    ``pictures`` by previewing both. The preview used to render the lesson with no look at all, which is the old
    ``columns`` frame (a picture in a left column), so it showed figures far smaller than the film draws them (a card of
    19 to 28% of the frame and 30 point steps, against 41 to 58% and 42 to 48 points in the film). Here the look is always
    ``for_new`` (``HARNESS_FRAME=columns`` still gives the old frame), and ``pictures`` is ``fill`` when the lesson has a
    figure code draws and the compose step is on (what ``compose.settle`` chooses when the fill preview is no worse);
    otherwise ``kept``. ``compose.settle`` itself is NOT called: it asks a vision model, which is a paid call.
    """
    from .. import knobs
    from ..longform import look as lesson_look
    from . import compose

    framed = {**lesson, "look": lesson_look.for_new(lesson, environ=knobs.environ())}
    framed["look"]["pictures"] = ("fill" if framed["look"]["frame"] == "stage" and compose.enabled() and compose.drawn_by_code(lesson)
                                  else "kept")
    return framed


def preview(lesson_id: str, chapters: list[int] | None = None, columns: int = 4, log=print) -> dict:
    """Free stills of every step (no voice, no model), a contact sheet per call, and the layout's own findings.

    Laid out as the film lays the lesson out (``film_layout``), not as the old columns frame. The timing is estimated
    from the words, so it is seconds to a few minutes (one Manim still per step), depending on the lesson's length.
    Sizes in ``findings`` are of the CARD (the paper a component is drawn on), not of the drawing inside it.
    """
    from ..longform import preview as P
    folder = _folder(lesson_id)
    number = len(_versions(folder))
    work = folder / "preview" / f"v{number:03}"
    stage = folder / "stage"
    stage.mkdir(exist_ok=True)
    lesson = load(lesson_id)
    (stage / "lesson.json").write_text(json.dumps(lesson, ensure_ascii=False), encoding="utf-8")
    result = P.stills(stage, work=work, jobs=4, only=chapters, log=log, lesson=film_layout(lesson))
    sheet = P.sheet(result, work / "sheet.jpg", columns=columns, width=360, what=("step", "pause", "end"))
    return {"version": number, "stills": len(result["stills"]), "sheet": str(sheet) if sheet else None,
            "folder": result["folder"], "findings": result["findings"], "failed_chapters": result["failed"]}


# ---------------------------------------------------------------- filming (free with a local voice)

def film(lesson_id: str, voice: str = DEFAULT_VOICE, quality: str = "m", wait: bool = True, log=print,
         paid_checks: bool = False, force: bool = False) -> dict:
    """Film the newest version through lessonforge's own service, as the hand-made videos were filmed.

    The lesson is marked as checked (``generated_by``) so the service renders it as written and writes nothing.
    ``paid_checks`` False (the default) films with no paid key in sight (every name in ``env.PAID_KEYS``, not only
    OpenRouter's), so nothing in the service spends: with a key, filming also paid for word alignment and a per-beat
    vision review (about 1.5 US cents a lesson in the 2026-11-07 pilot), which ``frame_judge`` does per sentence
    anyway. A paid voice therefore needs ``paid_checks=True``.
    """
    import os

    from ..env import PAID_KEYS
    hidden = {k: os.environ[k] for k in PAID_KEYS if os.environ.get(k)}
    if not paid_checks and hidden:
        for k in hidden:
            os.environ.pop(k)
        try:
            return film(lesson_id, voice, quality, True, log, paid_checks=True, force=force)
        finally:
            os.environ.update(hidden)
    from . import service, writer
    folder = _folder(lesson_id)
    lesson = load(lesson_id)
    if faults_of(lesson) and not force:      # force: a lesson whose "faults" a person has read and accepted
        raise WorkbenchError("the lesson still has faults; film it once check() finds none")
    by = str(lesson.get("generated_by") or "")
    if not (by in ("model", "geometry pack") or by.startswith(writer.HAND_WRITTEN)):
        lesson["generated_by"] = f"{writer.HAND_WRITTEN} (workbench)"
    lesson["continuity"] = writer.continuity(_normalise(lesson))      # edits may have changed what it counts
    number = len(_versions(folder))
    draft = folder / f"film_v{number:03}.json"
    draft.write_text(json.dumps(lesson, ensure_ascii=False), encoding="utf-8")
    job = service.start_job({"topic": lesson.get("title") or lesson_id, "draft_file": str(draft),
                             "language": lesson.get("language") or "en-US"}, quality=quality, voice=voice)
    _log(folder, {"by": "film", "what": f"filming version {number}", "job_id": job["job_id"]})
    if not wait:
        return {"job_id": job["job_id"], "status": job["status"]}
    while True:
        state = service.get_job(job["job_id"])
        if state.get("status") not in ("queued", "running"):
            break
        time.sleep(5)
    video = _video_of(job["job_id"])
    if video:
        shutil.copy2(video, folder / f"v{number:03}.mp4")
    return {"job_id": job["job_id"], "status": state.get("status"), "error": state.get("error"),
            "video": str(folder / f"v{number:03}.mp4") if video else None, "cost_usd": state.get("cost_usd")}


def _video_of(job_id: str) -> Path | None:
    lesson_root = paths.sub("lessons", job_id, create=False)
    found = sorted(lesson_root.rglob("*.mp4"), key=lambda p: p.stat().st_size, reverse=True) if lesson_root.is_dir() else []
    finals = [p for p in found if "chapter" not in p.name and "media" not in p.parts]
    return (finals or found or [None])[0]


# ---------------------------------------------------------------- measuring a film (free)

def measure_video(video: str | Path) -> dict:
    """What a viewer sees, measured the same way as the 2026-10-21 review of the hand-made videos.

    ``moving``: the share of half-seconds in which something on screen changes (Khan Academy measured 81-92%);
    ``longest_still``: the longest stretch with no change; ``silence``: the share of time under -35 dB.
    """
    import numpy as np
    video = str(video)
    w, h = 160, 90
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", video, "-vf", f"fps={SAMPLE_FPS},scale={w}:{h},format=gray",
                          "-f", "rawvideo", "-"], capture_output=True, check=True).stdout
    frames = np.frombuffer(raw, dtype=np.uint8).reshape(-1, h, w).astype(np.int16)
    changed = (np.abs(np.diff(frames, axis=0)) > 12).mean(axis=(1, 2)) > CHANGED_SHARE
    longest = run = 0
    for c in changed:
        run = 0 if c else run + 1
        longest = max(longest, run)
    probe = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", video],
                           capture_output=True, text=True).stdout.strip()
    duration = float(probe or 0)
    sd = subprocess.run(["ffmpeg", "-v", "info", "-i", video, "-af", "silencedetect=n=-35dB:d=0.4", "-f", "null", "-"],
                        capture_output=True, text=True).stderr
    silent = sum(float(x) for x in re.findall(r"silence_duration: ([\d.]+)", sd))
    return {"seconds": round(duration, 1), "moving": round(float(changed.mean()), 3) if len(changed) else 0.0,
            "longest_still_s": round(longest / SAMPLE_FPS, 1), "silence": round(silent / duration, 3) if duration else 0.0}


def review(lesson_id: str) -> dict:
    """The newest film of the lesson measured, with the script's own numbers beside it."""
    folder = _folder(lesson_id)
    films = sorted(folder.glob("v[0-9][0-9][0-9].mp4"))
    if not films:
        raise WorkbenchError("the lesson has not been filmed yet")
    lesson = load(lesson_id, int(films[-1].stem[1:]))
    numbers = measure_video(films[-1])
    c = craft(lesson)
    numbers["words_per_minute"] = round(c["words"] / (numbers["seconds"] / 60), 0) if numbers["seconds"] else 0
    return {"video": str(films[-1]), "video_numbers": numbers, "craft": c}
