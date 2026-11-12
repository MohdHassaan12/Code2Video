"""Vision review of a finished lesson video: one frame per beat, judged against the words.

The engine's Vision QA sampled six evenly spaced frames and flagged "dead frame" on
every one of them — because the sampler landed on scene starts, before anything was
drawn (docs/research/engine/problem-catalogue.md). This pass samples each BEAT at
the moment its key step should be on screen (the midpoint between the key step's cue
and the beat's end, or the beat midpoint), and gives the judge the sentence being
spoken at that instant plus what the script says should be visible. The question is
then specific — "is the picture showing what the voice is saying?" — rather than
"is this a good frame?".

It is a REPORT, never a gate: a vision model's agreement with humans on layout is
moderate and on pedagogy weak (research-agenda: ρ≈0.42 / 0.14–0.17), so findings are
written next to the deterministic probe results for a person to weigh. Cost is about
a tenth of a US cent per frame at 640 px through OpenRouter.
"""
from __future__ import annotations

import base64
import hashlib
import json
import re
import subprocess
import tempfile
from pathlib import Path

from .. import knobs

FINDING_KINDS = ("overlap", "clipped", "unreadable", "stale", "mismatch", "empty", "other")
JUDGE_MODELS = ("google/gemini-2.5-flash",)
SYSTEM = """You review ONE frame of an animated maths/science lesson for school students.
You are told what the narrator is saying at this instant and what the script intended to be on screen.
Report only what you can SEE. Return ONLY JSON:
{"findings": [{"kind": "overlap|clipped|unreadable|stale|mismatch|empty|other", "severity": "high|medium|low",
  "what": "one sentence, naming the on-screen elements"}],
 "shows_intended": true|false, "readable": true|false, "note": "≤20 words"}
kinds: overlap = two elements collide so one hides part of the other; clipped = cut by the frame edge;
unreadable = text too small/low contrast; stale = something on screen belongs to an earlier point and now
misleads; mismatch = what is shown contradicts or does not relate to what is being said; empty = nothing
but the chrome is on screen while the voice is explaining something visual. Do not report style preferences."""


def _frame(video: Path, at: float, out: Path, width: int = 960) -> None:
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{at:.3f}", "-i", str(video), "-frames:v", "1",
                    "-vf", f"scale={width}:-1", "-q:v", "4", str(out)], check=True)


KEY_STEP_SETTLE = 1.6      # seconds after a step's cue: its entrance (≤0.9 s) and highlight box (0.5 s) are done
ARRIVING = 1.2             # for this long after its cue a step is still being written: never look then


def shown_at(root: Path, timeline: list[dict]) -> dict[str, list[tuple[str, float]]]:
    """When each step REALLY began to appear, on the video's clock: ``{beat: [(the step's phrase, seconds), …]}``.

    Read from the render's own record (``output/chapter_NN_audit.json``: every cue's ``target``, or the
    moment the renderer got to it when it was already late) and not worked out a second time here. This
    module's own working-out differs from the renderer's whenever a step's phrase is placed by estimate
    (a block that was not timed from heard words, a phrase the narration does not hold): in one lesson the
    review looked 0.2 and 0.4 seconds after two steps had begun, saw "Predic" and "Attractio", and
    reported both as text clipped by the frame. Of the 21 "clipped" findings in the lessons made by
    2026-10-09, the ones looked at were all of this kind or not clipped at all.
    A chapter's clock starts with its first beat. A chapter without a record gives nothing (estimates stand).
    """
    zero: dict = {}
    for entry in timeline:
        zero[entry["chapter"]] = min(zero.get(entry["chapter"], entry["start"]), entry["start"])
    out: dict[str, list[tuple[str, float]]] = {}
    for chapter, begins in zero.items():
        try:
            cues = json.loads((root / "output" / f"chapter_{int(chapter):02}_audit.json").read_text(encoding="utf-8"))["cues"]
            for cue in cues:
                when = begins + max(float(cue["target"]), float(cue["actual_before_wait"]))
                out.setdefault(str(cue["beat"]), []).append((str(cue["phrase"]).lower().strip(), when))
        except (OSError, ValueError, KeyError, TypeError):
            continue
    return out


def laid_out(root: Path, timeline: list[dict]) -> dict[str, dict]:
    """How the render laid each beat out: ``{beat: {"frame", "mode", "words"}}`` from the chapters' own records.

    Since 2026-10-10 a beat that has a picture shows ONE line of words at a time (``words: "caption"``): the line
    before it has gone when the next one comes. A reviewer told "these are on screen by now" would report every
    earlier line as missing, and a finding of that kind starts a repair. Nothing for a chapter without a record.
    """
    out: dict[str, dict] = {}
    for chapter in sorted({entry["chapter"] for entry in timeline}):
        try:
            records = json.loads((root / "output" / f"chapter_{int(chapter):02}_audit.json").read_text(encoding="utf-8"))["bounds"]
            out.update({str(r["beat"]): r["layout"] for r in records if isinstance(r.get("layout"), dict)})
        except (OSError, ValueError, KeyError, TypeError):
            continue
    return out


def sample_points(timeline: list[dict], lesson: dict, shown: dict | None = None, layouts: dict | None = None) -> list[dict]:
    """One instant per beat: when the key step (or the last step) should be visible.

    ``shown`` (from ``shown_at``) is when the render put each step up; without it, when it should have.
    ``layouts`` (from ``laid_out``) says how each beat's words are shown; it goes into the point as ``words``.
    """
    steps_by_beat = {b["id"]: b.get("steps", []) for c in lesson["chapters"] for b in c["beats"]}
    # A prepared drawing carries labels of its own, and one that is built up keeps every part an earlier beat
    # pointed at (``runtime.GuidedChapter._pointed_at_before``). The judge is told, per beat, which picture is up
    # and what it holds by then: left to guess, it reported "Precipitation is visible but not intended yet" on
    # the first lesson whose chapters opened with what earlier chapters had drawn in.
    drawing_by_beat, seen = {}, {}
    for chapter in lesson["chapters"]:
        for beat in chapter["beats"]:
            figure = beat.get("figure") or {}
            if figure.get("kind") in ("diagram", "picture"):
                key = str(figure.get("manifest") or figure.get("file") or "")
                focuses = [str(s["focus"]) for s in beat.get("steps") or [] if s.get("focus")]
                drawing_by_beat[beat["id"]] = {"of": str(figure.get("ask") or "")[:160], "kept": list(seen.get(key, [])),
                                               "whole": figure.get("kind") == "picture"}
                seen.setdefault(key, [])
                seen[key] += [f for f in focuses if f not in seen[key] and not f.startswith("panel")]
    # A beat shown WITHOUT the picture on purpose (``"picture": "off"``: the picture up before it is of something else).
    without = {b["id"] for c in lesson["chapters"] for b in c["beats"] if b.get("picture") == "off"}
    points = []
    for entry in timeline:
        beat_id = entry["id"]
        start, duration, speech_end = entry["start"], entry["duration"], entry.get("speech_end", entry["duration"])
        sentences = entry.get("sentences", [])
        recorded = list((shown or {}).get(str(beat_id)) or [])
        # When does each step appear? What the render recorded; else the aligned word if the timeline has
        # it, else the sentence start — the same rule the scene runtime uses to fire the cue.
        onsets = []
        for s in steps_by_beat.get(beat_id, []):
            needle = str(s.get("say", "")).lower().strip()
            onset = None
            match = next((r for r in recorded if needle and r[0] == needle), None)
            if match:
                recorded.remove(match)           # a phrase said twice: each step takes its own cue, in order
                onsets.append(match[1] - start)
                continue
            for sent in sentences:
                hay = sent["text"].lower()
                if needle and needle in hay:
                    index = len(hay[:hay.index(needle)].split())
                    words = sent.get("words") or []
                    onset = words[index]["start"] if index < len(words) else sent["start"]
                    break
            onsets.append(onset)
        key_index = next((i for i, s in enumerate(steps_by_beat.get(beat_id, [])) if s.get("highlight")), None)
        if key_index is not None and onsets[key_index] is not None:
            # After the key step has finished arriving. One second caught it half-written: eight
            # "clipped" findings across fifteen lessons were text still being drawn ("coll" of
            # "colloid"), which sent readers looking for a layout bug that was not there.
            at = start + onsets[key_index] + KEY_STEP_SETTLE
        else:
            at = start + min(speech_end, duration) * 0.6
        last = start + duration - 0.2
        at = min(at, last)
        # Never while a step is being written: look once it is whole, or, when the beat ends before that,
        # just before it began (it is then listed as not expected yet).
        arriving = [o for o in onsets if o is not None and 0 <= at - (start + o) < ARRIVING]
        if arriving:
            began = start + max(arriving)
            at = min(began + KEY_STEP_SETTLE, last) if last - began >= ARRIVING else max(start, began - 0.15)
        # A drawing that is drawn part by part (``runtime._start_paint``) is not whole for its first seconds: look
        # once it stands. When the beat is over before that, the look is told the drawing is still being drawn.
        painted = float(((layouts or {}).get(str(beat_id)) or {}).get("painted") or 0)
        if painted and at < start + painted + .5:
            at = min(start + painted + .5, last)
        steps = steps_by_beat.get(beat_id, [])
        visible = [f"{s['kind']}: {s['show']}" for s, o in zip(steps, onsets) if o is None or start + o <= at]
        later = [f"{s['kind']}: {s['show']}" for s, o in zip(steps, onsets) if o is not None and start + o > at]
        spoken = next((s["text"] for s in sentences if s["start"] <= at - start < s["start"] + s["duration"]), "")
        layout = (layouts or {}).get(str(beat_id)) or {}
        drawing = None if beat_id in without else drawing_by_beat.get(beat_id)
        if drawing and layout.get("built"):
            drawing = {**drawing, "built": True}         # being drawn with the words: parts of it are still to come
        if drawing and layout.get("annotations"):
            drawing = {**drawing, "annotated": True}     # a hand has written on it (harness/annotate.py)
        points.append({"beat": beat_id, "chapter": entry["chapter"], "at": round(at, 3), "spoken": spoken,
                       "intended": visible, "later": later, "drawing": drawing,
                       "words": layout.get("words"), "mode": layout.get("mode"), "no_picture": beat_id in without,
                       "being_drawn": bool(painted and at < start + painted)})
    return points


def _intended_note(point: dict) -> str:
    """What the judge is told about the words on screen at that instant, by how the beat was laid out."""
    lines = "\n".join(f"  - {x}" for x in point["intended"])
    if point.get("words") == "caption" and point["intended"]:
        where = {"bleed": "on a dark plate lying on the picture, which fills the whole frame", "top": "above the picture"}.get(
            point.get("mode"), "beside the picture")
        return (f"This beat shows ONE line of words at a time, {where}; each line leaves when the next one comes. By this instant "
                f"the script has been through these, and only the LAST of them is meant to be on screen now:\n{lines}\n"
                "An earlier line that is no longer there is intended: do not report it as missing, and do not report the "
                "frame as empty because it holds one line.")
    if point.get("words") == "pinned" and point["intended"]:
        return ("This beat works something out beside the picture. Its formula lines (math:) STAY and pile up, the earlier ones "
                "dimmed; its other lines come ONE at a time above them, each leaving when the next one comes; and working "
                "that no longer fits has made room by leaving too. By this instant the script has been through these:\n"
                f"{lines}\nA line of words that is no longer there, or early working that has gone, is intended: do not "
                "report it as missing.")
    return f"By this instant the script has put these on screen (earlier ones are dimmed, that is intended):\n{lines}"


def _drawing_note(drawing: dict | None) -> str:
    """What the judge is told about a prepared drawing on screen: its own labels are the drawing, not leftovers."""
    if not drawing:
        return ""
    if drawing.get("annotated"):
        return _drawing_note({k: v for k, v in drawing.items() if k != "annotated"}) + (
            " Marks in RED on the drawing (a value written at an angle or a side, a ring, an arrow with a word or two, a line "
            "gone over, a cross) are the teacher's own annotations, made as the voice speaks: they are intended, and a value "
            "written earlier in this part of the lesson is meant to stand.")
    of = f" of: {drawing['of']}" if drawing.get("of") else ""
    if drawing.get("built"):
        return (f"\n\nTHE PICTURE is a textbook drawing{of}. It is being DRAWN through the lesson, with the words: a line, a "
                "mark or a label is drawn in when the voice first speaks of it, and then stays. At this instant only part of "
                "it is on the paper, on purpose: do not report a part that is not drawn yet as missing, the picture as empty "
                "or unfinished, or a part that is already there as stale or early. A highlighted label is the one the "
                "voice has just named.")
    if drawing.get("whole"):
        return (f"\n\nTHE PICTURE is a finished textbook drawing{of}. It is shown whole from the start, with ALL its printed "
                "labels; one label at a time is highlighted as the voice names it. A label of the drawing that the narrator "
                "has not reached yet is intended: do not report it as stale, early or not expected.")
    kept = ", ".join(drawing.get("kept") or [])
    return (f"\n\nTHE PICTURE is a textbook drawing{of}. It is built up through the lesson: a part and its label are drawn in "
            "when the voice first names them and then STAY for the rest of the lesson"
            + (f". Brought in before this beat, and intended to be there now: {kept}" if kept else "")
            + ". Do not report such a part or label as stale, early or not expected.")


def review_video(lesson_dir: str | Path, video: str | Path, llm_call=None, log=print, max_frames: int = 40,
                 only: set | None = None) -> dict:
    """Judge one frame per beat. Writes ``output/vision_review.json`` and returns it.

    With ``only`` (beat ids) just those beats' frames are judged and NOTHING is written: that is the
    second look a repair takes at the beats it changed (``harness/repairs.py``); ``merge`` puts it into
    the lesson's report when the repair is kept.
    """
    root = Path(lesson_dir)
    lesson = json.loads((root / "lesson.json").read_text(encoding="utf-8"))
    timeline = json.loads((root / "timeline.json").read_text(encoding="utf-8"))
    points = sample_points(timeline, lesson, shown_at(root, timeline), laid_out(root, timeline))[:max_frames]
    if only is not None:
        points = [p for p in points if str(p["beat"]) in {str(b) for b in only}]
    if llm_call is None:
        llm_call = default_judge()
    results, counts = [], {k: 0 for k in FINDING_KINDS}
    with tempfile.TemporaryDirectory() as tmp:
        for p in points:
            frame = Path(tmp) / f"beat_{p['beat']}.jpg"
            _frame(Path(video), p["at"], frame)
            b64 = base64.b64encode(frame.read_bytes()).decode("ascii")
            prompt = (f"At t={p['at']:.1f}s the narrator is saying: «{p['spoken']}»\n"
                      + _intended_note(p)
                      + ("\n\nThese come LATER in the beat and are NOT expected yet:\n" + "\n".join(f"  - {x}" for x in p["later"])
                         if p.get("later") else "")
                      + _drawing_note(p.get("drawing"))
                      + ("\n\nThis beat is shown WITHOUT a picture, on purpose: the picture that was up before it is about "
                         "something else, so only the beat's lines of words stand in the frame. Do not report the frame as "
                         "empty, a picture as missing, or the earlier picture as gone." if p.get("no_picture") else "")
                      + ("\n\nThe drawing in this frame is still being DRAWN, part by part, as a hand draws it: a part or a "
                         "label that is not there yet is intended, and is not a fault." if p.get("being_drawn") else ""))
            try:
                verdict = llm_call(prompt, SYSTEM, b64) or {}
            except Exception as exc:  # noqa: BLE001 - one bad frame must not kill the report
                verdict = {"error": f"{type(exc).__name__}: {str(exc)[:120]}"}
            findings = [f for f in (verdict.get("findings") or []) if isinstance(f, dict)]
            for f in findings:
                counts[f.get("kind") if f.get("kind") in FINDING_KINDS else "other"] += 1
            results.append({**p, "findings": findings, "shows_intended": verdict.get("shows_intended"),
                            "readable": verdict.get("readable"), "note": verdict.get("note", ""),
                            "error": verdict.get("error")})
            log(f"[vision] beat {p['beat']} t={p['at']:.1f}s: {len(findings)} finding(s)"
                + (f" — {findings[0].get('what', '')[:90]}" if findings else ""))
    report = {
        "frames": len(results), "findings": sum(counts.values()), "by_kind": counts,
        "frames_showing_intended": sum(1 for r in results if r["shows_intended"]),
        "frames_unreadable": sum(1 for r in results if r["readable"] is False),
        "detail": results,
        "limits": ["One frame per beat, judged by a vision model: moderate agreement with humans on layout, "
                   "weak on pedagogy. Weigh against the deterministic probe; this is not acceptance."],
    }
    if only is None:
        (root / "output" / "vision_review.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return report


HOLDS = """You look at ONE drawing made for a school lesson and write down what it holds, so that a script can be checked against it.
Return ONLY JSON: {"things": ["each thing drawn: what it is and where, three to eight words"],
 "print": ["every word, letter, number or formula printed in the drawing, exactly as printed"]}
List only what IS drawn or printed, large and small (three small drops, a dashed line, a right-angle mark). Do not explain
the drawing, do not say what it means, and do not list what a drawing of this subject usually has. At most sixteen things
and twenty printed items."""
HOLDS_VERSION = hashlib.sha256(HOLDS.encode("utf-8")).hexdigest()[:10]


def picture_file(figure: dict | None) -> Path | None:
    """The file a prepared drawing is seen as (its whole drawing, words and all); None for a picture code draws."""
    if not isinstance(figure, dict):
        return None
    try:
        if figure.get("kind") == "picture":
            file = Path(str(figure.get("file") or (figure.get("params") or {}).get("file") or ""))
            return file if file.is_file() else None
        if figure.get("kind") == "diagram":
            path = Path(str(figure.get("manifest") or (figure.get("params") or {}).get("manifest") or ""))
            manifest = json.loads(path.read_text(encoding="utf-8"))
            folder = Path(manifest.get("folder") or path.parent)
            return next((folder / str(name) for name in (manifest.get("whole"), manifest.get("art")) if name and (folder / str(name)).is_file()), None)
    except (OSError, ValueError, TypeError):
        return None
    return None


def holds(figure: dict | None, llm_call=None, log=print) -> dict | None:
    """What a prepared drawing HOLDS, read from the drawing itself: ``{"things": […], "print": […]}``, or None.

    The writer of a lesson is told what a drawing was ASKED for and never what came back, so its words speak of
    "faint squares" and "six centimetres" over a drawing that has neither (every one of the three lessons read on
    2026-10-10). One look per drawing, kept beside it (``holds.json``): whoever checks or mends a script against the
    drawing reads this list instead of guessing. None for a picture drawn by code, with no judge, or on any failure.
    """
    file = picture_file(figure)
    if file is None:
        return None
    kept = file.parent / "holds.json"
    try:
        before = json.loads(kept.read_text(encoding="utf-8"))
        entry = (before.get("files") or {}).get(file.name) if before.get("version") == HOLDS_VERSION else None
        if entry:
            return entry
    except (OSError, ValueError):
        before = {}
    if llm_call is None:
        llm_call = default_judge(temperature=0.0)
    if llm_call is None:
        return None
    try:
        import io  # noqa: PLC0415
        from PIL import Image  # noqa: PLC0415
        image = Image.open(file).convert("RGBA")
        ground = Image.new("RGBA", image.size, "white")
        ground.alpha_composite(image)
        ground = ground.convert("RGB")
        ground.thumbnail((1400, 1400))
        sent = io.BytesIO()
        ground.save(sent, format="JPEG", quality=88)
        raw = llm_call("Write down what this drawing holds.", HOLDS, base64.b64encode(sent.getvalue()).decode("ascii")) or {}
    except Exception as exc:  # noqa: BLE001 - a list of what a drawing holds is a help, never a requirement
        log(f"[look] the drawing was not read ({type(exc).__name__}: {str(exc)[:100]})")
        return None
    entry = {"things": [str(x).strip()[:80] for x in raw.get("things") or [] if str(x).strip()][:16],
             "print": [str(x).strip()[:60] for x in raw.get("print") or [] if str(x).strip()][:20]}
    if not entry["things"] and not entry["print"]:
        return None
    try:
        files = {**(before.get("files") or {}), file.name: entry} if before.get("version") == HOLDS_VERSION else {file.name: entry}
        kept.write_text(json.dumps({"version": HOLDS_VERSION, "files": files}, indent=1, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass
    return entry


def holds_line(entry: dict | None) -> str:
    """What a drawing holds, as one paragraph for a prompt ('' when it is not known)."""
    if not entry:
        return ""
    return ("things: " + "; ".join(entry.get("things") or ["(none listed)"])
            + (". Printed in it: " + "; ".join(f"“{p}”" for p in entry["print"]) if entry.get("print") else ". Nothing is printed in it"))


ASSESS_KINDS = ("mismatch", "missing", "unreadable", "half", "note", "crowded", "lonely")
ASSESS = """You look at ONE still picture of an animated school lesson: the screen as it stands at the END of one part of it.
You are told what the narrator says during that part and which lines of words the script put on the screen, and, when
it is known, what the drawing HOLDS (a list read from the drawing itself at full size: a thing on it IS in the drawing,
even where this still shows it small or a drawing built up part by part has not brought it in yet).
Answer four things, each from what you can SEE.
1. "subject": is the drawing a picture of the SAME subject the words are about, or of a DIFFERENT object or situation?
   same: the words explain, sum up or ask about what the drawing shows, even when they give steps, numbers or cases the
   drawing does not show (a summing-up of how a lever works over a drawing of a see-saw; a sum with other numbers over
   a number line). different: the words are about another object or situation altogether, which a learner would look
   for in the drawing and not find (a paper boat to float in a bucket, over a drawing of the heart). In doubt: same.
   When there is no drawing on screen: "none".
2. "pointed_at": every place where the words POINT AT the picture: they tell the learner to look, or say "this", "here",
   "that dotted line", "the valve in the picture", or describe how a thing in the picture looks or where it is. For
   each, copy the words EXACTLY as written (four to fourteen words, from the narration or from a line); list EVERY
   thing those words say is in the picture ("this pulley hangs from a red hook on a wooden beam" says three: a pulley,
   a red hook, a wooden beam); then list those of them that are NOT in the picture. Check each thing by itself: words
   that point at a thing that is there often add one that is not. Do NOT quote words that only state a fact, give a
   number or a size, name the topic, or ask the learner to imagine, draw or try something.
3. "notes": any line on screen, copied exactly, that is an instruction to whoever draws the lesson or talks about the
   screen itself, and is not something said to the learner.
4. "findings": only these, and only when plain to see: unreadable (writing INSIDE the drawing too small or faint to
   read), half (a large part of the drawing's own area is blank, as if a part had not arrived), crowded (so many things
   at once that a learner cannot tell where to look), lonely (the drawing is small and lost in a mostly empty frame).
Return ONLY JSON: {"shows": "what the drawing shows, at most eight words", "words_about": "at most eight words",
 "subject": "same|different|none",
 "pointed_at": [{"quote": "the exact words", "says_is_there": ["each thing"], "not_there": ["each that is not"]}],
 "notes": ["the exact line"],
 "findings": [{"kind": "unreadable|half|crowded|lonely", "severity": "high|medium|low", "what": "one sentence"}]}
Colours, style, a plain drawing, one line of words on screen at a time, a label the narrator has not reached yet: none
of these is a fault. Empty lists are good answers."""


def _said(quote: str, text: str) -> bool:
    """Whether ``quote`` was really written: the same words in the same order, whatever the case, spacing and marks."""
    words = lambda t: re.findall(r"[^\W_]+", str(t).lower())
    q, t = words(quote), words(text)
    return len(q) >= 3 and any(t[i:i + len(q)] == q for i in range(len(t) - len(q) + 1))


def _held(thing: str, held: dict | None) -> bool:
    """Whether the reading of the drawing itself lists ``thing`` (most of an item's words are in it, or it in an item)."""
    said = _words_of(thing)
    for item in list((held or {}).get("things") or []) + list((held or {}).get("print") or []):
        words = _words_of(item)
        if words and said and (len(words & said) >= 0.75 * len(words) or len(words & said) >= 0.75 * len(said)):
            return True
    return False


def findings_of(answer: dict, beat: dict, held: dict | None) -> list[dict]:
    """The look's answer as findings, each one checked by code where code can check it.

    Asked openly for "faults", the look wrote twenty a lesson and most were not faults: it checked the still against
    the request the drawing was made from, called a number missing where the drawing prints a letter, and reported
    lines that had left the screen (five lessons read, 2026-10-11). Now it QUOTES. A "missing" finding stands only
    when the quoted words are really in the beat's narration or lines, they themselves name the thing the look says
    is not there, and the reading of the drawing does not list it; a "note" only when the quoted line is one of the beat's
    lines; "mismatch" is the one answer to the one question whether the drawing is of another thing.
    """
    narration = str(beat.get("narration") or "")
    lines = [str(s.get("show") or "") for s in beat.get("steps") or []]
    found = []
    if str(answer.get("subject") or "").strip().lower() == "different":
        found.append({"kind": "mismatch", "severity": "high",
                      "what": f"the drawing shows {str(answer.get('shows') or 'one thing')[:80]}; the words are about "
                              f"{str(answer.get('words_about') or 'another')[:80]}"})
    for claim in answer.get("pointed_at") or []:
        if not isinstance(claim, dict):
            continue
        quote = str(claim.get("quote") or "").strip()
        if not (_said(quote, narration) or any(_said(quote, line) for line in lines)):
            continue
        for thing in claim.get("not_there") or []:
            thing = str(thing).strip()
            # ... and the thing is one the quoted words themselves name, and the drawing's own reading does not list it
            if thing and _words_of(thing) & _words_of(quote) and not _held(thing, held):
                found.append({"kind": "missing", "severity": "medium", "quote": quote[:120], "thing": thing[:80],
                              "what": f"the words point at {thing[:80]} (“{quote[:120]}”), which is not in the drawing"})
    for note in answer.get("notes") or []:
        line = next((l for l in lines if isinstance(note, str) and note.strip() and " ".join(note.lower().split()) == " ".join(l.lower().split())), None)
        if line:
            found.append({"kind": "note", "severity": "medium", "quote": line[:120],
                          "what": f"a line on screen is a note to whoever draws the lesson: “{line[:120]}”"})
    for f in answer.get("findings") or []:
        if isinstance(f, dict) and f.get("kind") in ("unreadable", "half", "crowded", "lonely") and not _ABOUT_THE_ASK.search(str(f.get("what") or "")):
            found.append({"kind": f["kind"], "severity": str(f.get("severity") or "low"), "what": str(f.get("what") or "")[:240]})
    return found


RECHECK = """You look at ONE still picture of an animated school lesson, after that part of the lesson was changed to cure faults
that had been found in it. You are given those faults, NUMBERED, what the narrator says NOW, the lines the script NOW
puts on screen and, when it is known, what the drawing HOLDS (a list read from the drawing itself: trust it for what is
and is not drawn). For EACH numbered fault, judge it against the words as they are NOW and the picture in front of you:
cured: it is no longer true. The words no longer speak of the thing as being in the drawing; or they now ask the learner
  to imagine, draw or try it; or they tie a number once to a letter the drawing prints ("the base, marked b, is six
  centimetres"); or the drawing that was of something else is no longer on screen.
still: it is as true now as it was.
Then list what is NEW: a thing the words now speak of as being IN the drawing ("look at the grid", "the red arrow shows")
that is not in it. A thing on the HOLDS list is never new, and neither is a thing the learner is asked to imagine, draw
or try. Most changes add nothing new: an empty list is a good answer.
Return ONLY JSON: {"faults": [{"n": 1, "now": "cured|still", "because": "at most twelve words"}], "new": ["one sentence each"]}"""


_ABOUT_THE_ASK = re.compile(r"\bdrawing(?:'s)? (?:request|instructions?|description)\b|\bas (?:requested|instructed)\b|"
                            r"\bholds? list\b|\brequested drawing\b|\bdrawing was (?:asked|supposed|meant)\b|"
                            r"\bsupposed to show\b", re.I)


def _words_of(text: str) -> set:
    return {w for w in re.findall(r"[a-z0-9]{3,}", str(text).lower()) if w not in ("the", "and", "with", "from", "into", "that", "this")}


FITS = """A drawing was made for ONE part of a school lesson. You see the drawing and are told what the narrator says while it
is on screen. Decide whether the drawing shows the situation those words describe.
fits is false when the drawing is of another object, another experiment or another case than the words describe, even
on the same topic (the words: a ball rolling down a slope, the drawing: a ball hanging from a string; the words: ice
melting in a glass, the drawing: water boiling in a kettle), or when a main thing in the drawing goes against the words.
More labels, more detail or another style than the words have: not a reason.
Return ONLY JSON: {"drawing_shows": "at most ten words", "words_describe": "at most ten words", "fits": true,
 "against": ["each thing in the drawing that goes against the words; empty when none"]}"""

TELLS = """A drawing was made to stand on screen while a school lesson ASKS its learner a question and waits for the answer.
You see the drawing and are given the question. Decide ONE thing: does the drawing already tell the answer?
It does when anything in it shows, prints or points to how the question comes out: the outcome drawn, an arrow of the
motion or change that is being asked about, a result or a rule written down, a label naming what happens, one of the
choices marked. It does not when it shows only the things and the set-up the question is about.
First list what in the drawing could tell an answer, then decide. In doubt, say it tells.
Return ONLY JSON: {"asked": "what the learner must work out, at most twelve words",
 "could_tell": ["each arrow, label, number or drawn outcome that bears on the answer, with what it says"], "tells": true}"""


def fits(figure: dict | None, beat: dict, llm_call=None, log=print) -> dict | None:
    """Whether a drawing made for ONE beat shows what that beat's words describe: ``{"fits", "against",
    "drawing_shows", "words_describe"}``; None when nobody could look (then the drawing is not used).

    For a drawing asked of the service for a beat whose words are about another situation than the lesson's picture
    (``compose.mend``). The request for it is written by a small model from the beat's words and can drift: asked for
    the experiment of a leaf half kept without carbon dioxide, it wrote "a leaf partially covered with a black paper
    strip", which is another experiment. A picture of the wrong experiment is worse than the lesson's own drawing.
    """
    lines = [str(s.get("show")) for s in beat.get("steps") or [] if str(s.get("show", "")).strip()]
    answer = _at_the_drawing(figure, f"THE NARRATOR SAYS: «{str(beat.get('narration') or '')[:900]}»"
                             + ("\nLINES OF WORDS ON SCREEN: " + " | ".join(lines) if lines else ""), FITS, llm_call, log)
    if answer is None or not isinstance(answer.get("fits"), bool):
        return None
    return {"fits": answer["fits"],
            "against": [str(x).strip()[:160] for x in answer.get("against") or [] if isinstance(x, str) and x.strip()][:4],
            "drawing_shows": str(answer.get("drawing_shows") or "")[:90], "words_describe": str(answer.get("words_describe") or "")[:90]}


def tells(figure: dict | None, question: str, llm_call=None, log=print) -> dict | None:
    """Whether a drawing already tells the answer to the question that is asked over it: ``{"tells", "could_tell"}``;
    None when nobody could look (then the drawing is not used).

    The drawing the service made for "blow up a balloon, pinch its neck; if the air goes backward, which way does the
    balloon go?" carried an arrow labelled "Predicted direction of motion". Asked in one breath with ``fits`` whether
    the drawing answers the beat, the look said no; asked this ONE thing, told to list first what could tell and to
    say "tells" in doubt, it named the arrow. No answer is taken as "it tells".
    """
    answer = _at_the_drawing(figure, f"THE QUESTION the learner is asked, in the narrator's words: «{str(question)[:500]}»", TELLS, llm_call, log)
    if answer is None:
        return None
    return {"tells": answer.get("tells") is not False,
            "could_tell": [str(x).strip()[:160] for x in answer.get("could_tell") or [] if isinstance(x, str) and x.strip()][:4]}


def _at_the_drawing(figure: dict | None, prompt: str, system: str, llm_call=None, log=print) -> dict | None:
    """One question asked of a prepared drawing itself, at its full size (not of a frame it stands in); None on any failure."""
    file = picture_file(figure)
    if file is None:
        return None
    if llm_call is None:
        llm_call = default_judge(temperature=0.0)
    if llm_call is None:
        return None
    try:
        import io  # noqa: PLC0415
        from PIL import Image  # noqa: PLC0415
        image = Image.open(file).convert("RGBA")
        ground = Image.new("RGBA", image.size, "white")
        ground.alpha_composite(image)
        ground = ground.convert("RGB")
        ground.thumbnail((1400, 1400))
        sent = io.BytesIO()
        ground.save(sent, format="JPEG", quality=88)
        answer = llm_call(prompt, system, base64.b64encode(sent.getvalue()).decode("ascii"))
    except Exception as exc:  # noqa: BLE001 - a drawing nobody could look at is a drawing that is not used
        log(f"[look] the new drawing was not looked at ({type(exc).__name__}: {str(exc)[:100]})")
        return None
    return answer if isinstance(answer, dict) and answer else None


def _showing(lesson: dict) -> dict:
    """``{beat id: the picture that beat SHOWS}``: its own, else the one still up from before; None for a beat marked
    ``"picture": "off"`` and for a beat before any picture."""
    showing, last = {}, None
    for chapter in lesson.get("chapters") or []:
        for beat in chapter.get("beats") or []:
            last = beat["figure"] if isinstance(beat.get("figure"), dict) else last
            showing[str(beat["id"])] = None if beat.get("picture") == "off" else last
    return showing


def _told(beat: dict, figure: dict, held: dict | None) -> str:
    """What a look at one beat's still is told: its words, its lines, and what is known of the drawing on screen."""
    lines = [f"  - {s.get('kind', 'point')}: {s.get('show')}" for s in beat.get("steps") or [] if str(s.get("show", "")).strip()]
    return (f"THE NARRATOR SAYS, during this part: «{str(beat.get('narration') or '')[:900]}»\n"
            + ("THE SCRIPT PUT THESE LINES ON SCREEN, one after another:\n" + "\n".join(lines) if lines else "The script put no line of words on screen.")
            + (f"\nTHE DRAWING is meant to be a picture of: {str(figure.get('ask') or figure.get('describe') or '')[:200]}\n"
               "(That sentence says what the picture is OF. It is not a list to check the picture against: never report "
               "that something named in it is not drawn.)" if figure.get("ask") or figure.get("describe") else "")
            + ("\nIt is a finished textbook drawing with printed labels of its own." if figure.get("kind") in ("diagram", "picture") else "")
            + ("\nIt is an ANIMATION seen here at its end: what moved, appeared for a moment or changed on the way cannot be "
               "seen in a still, and is not a fault." if figure.get("kind") == "scene" else "")
            + ("\nIt may be built up through the lesson: a part and its label are drawn in when the voice first names them."
               if figure.get("kind") == "diagram" else "")
            + (f"\nTHE DRAWING HOLDS: {holds_line(held)}" if held else "")
            + ("\nNo drawing is meant to be on screen in this part: only words." if beat.get("picture") == "off" else ""))


def recheck(result: dict, lesson: dict, before: dict, llm_call=None, log=print, workers: int = 6) -> dict:
    """A second look at beats that were changed to cure what the first look found, FAULT BY FAULT.

    ``before``: ``{beat id: [finding, …]}`` from ``assess``; ``result``: the preview of the lesson as it is now.
    Counting what an open look finds the second time says little: the same still gave two findings once and six the
    next time (five lessons, 2026-10-11), so rewrites that had cured their fault were thrown away and one that had
    not was kept. Asked about each earlier fault by its number, and then for anything the new words claim to show that
    is not there, the answer is about the change. Returns ``{beat: {"cured": [finding, …], "still": [finding, …],
    "new": [sentence, …]}}``; a fault the look does not answer is still there, and a beat that could not be looked at
    has every fault still.
    """
    import concurrent.futures  # noqa: PLC0415
    if llm_call is None:
        llm_call = default_judge(temperature=0.0)
    beats = {str(b["id"]): b for c in lesson.get("chapters") or [] for b in c.get("beats") or []}
    folder = Path(result["folder"])
    ends = {str(s["beat"]): s for s in result.get("stills") or [] if s.get("what") == "end"}
    showing = _showing(lesson)
    read = {}
    for beat in before:
        figure = showing.get(str(beat))
        key = json.dumps(figure, sort_keys=True)
        if figure and key not in read and llm_call is not None:
            read[key] = holds(figure, llm_call, log=log)

    def one(beat):
        faults = list(before[beat])
        nothing = {"cured": [], "still": faults, "new": []}
        still = ends.get(str(beat))
        if llm_call is None or still is None or str(beat) not in beats:
            return beat, nothing
        figure = showing.get(str(beat)) or {}
        prompt = (_told(beats[str(beat)], figure, read.get(json.dumps(figure, sort_keys=True)))
                  + "\n\nTHE FAULTS FOUND BEFORE THE CHANGE:\n" + "\n".join(f"  {n}. [{f.get('kind')}] {f.get('what')}" for n, f in enumerate(faults, 1)))
        try:
            answer = llm_call(prompt, RECHECK, base64.b64encode((folder / still["file"]).read_bytes()).decode("ascii")) or {}
        except Exception as exc:  # noqa: BLE001 - a change nobody could look at is a change that is not kept
            log(f"[look] beat {beat} was not looked at again ({type(exc).__name__}: {str(exc)[:100]})")
            return beat, nothing
        said = {}
        for row in answer.get("faults") or []:
            try:
                said[int(row.get("n"))] = str(row.get("now") or "").strip().lower()
            except (AttributeError, TypeError, ValueError):
                continue
        cured = [f for n, f in enumerate(faults, 1) if said.get(n) == "cured"]
        new = [str(x).strip()[:240] for x in answer.get("new") or [] if isinstance(x, str) and str(x).strip()]
        return beat, {"cured": cured, "still": [f for f in faults if f not in cured], "new": new}

    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        return dict(pool.map(knobs.wrap(one), list(before)))


def assess(result: dict, lesson: dict, llm_call=None, log=print, only: set | None = None, workers: int = 6) -> dict:
    """What a vision model makes of a lesson's preview stills (``longform/preview.stills``): one look per beat.

    The stills exist before any narration is bought and before anything is filmed, so what is found here can be put
    right for the price of another preview. The beat's END still is looked at (and nothing else of the beat): by
    then every line it shows has arrived. Returns ``{"frames", "findings", "by_kind", "detail": [{"beat", "file",
    "shows", "findings"}]}``; a REPORT, like ``review_video``: what is done about a finding is code's decision.
    """
    import concurrent.futures  # noqa: PLC0415
    if llm_call is None:
        llm_call = default_judge(temperature=0.0)
    beats = {str(b["id"]): (c, b) for c in lesson.get("chapters") or [] for b in c.get("beats") or []}
    folder = Path(result["folder"])
    picked = [s for s in result.get("stills") or [] if s.get("what") == "end" and (only is None or str(s["beat"]) in {str(x) for x in only})]
    showing = _showing(lesson)
    read = {}                                              # one reading per drawing, whichever beats show it

    def one(still):
        chapter, beat = beats.get(str(still["beat"]), ({}, {}))
        figure = showing.get(str(still["beat"])) or {}
        held = read.get(json.dumps(figure, sort_keys=True))
        prompt = _told(beat, figure, held)
        try:
            answer = llm_call(prompt, ASSESS, base64.b64encode((folder / still["file"]).read_bytes()).decode("ascii")) or {}
        except Exception as exc:  # noqa: BLE001 - one still that cannot be looked at must not lose the report
            return {"beat": still["beat"], "file": still["file"], "shows": "", "findings": [], "error": f"{type(exc).__name__}: {str(exc)[:120]}"}
        return {"beat": still["beat"], "file": still["file"], "shows": str(answer.get("shows") or "")[:80],
                "words_about": str(answer.get("words_about") or "")[:80], "findings": findings_of(answer, beat, held)}

    if llm_call is None or not picked:
        return {"frames": 0, "findings": 0, "by_kind": {}, "detail": []}
    for still in picked:
        figure = showing.get(str(still["beat"]))
        key = json.dumps(figure, sort_keys=True)
        if figure and key not in read:
            read[key] = holds(figure, llm_call, log=log)
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        detail = list(pool.map(knobs.wrap(one), picked))
    counts: dict = {}
    for row in detail:
        for finding in row["findings"]:
            counts[finding["kind"]] = counts.get(finding["kind"], 0) + 1
            log(f"[look] beat {row['beat']} [{finding['kind']}/{finding['severity']}] {finding['what'][:120]}")
    held = {beat: holds_line(read.get(json.dumps(figure, sort_keys=True))) for beat, figure in showing.items() if figure}
    return {"frames": len(detail), "findings": sum(counts.values()), "by_kind": counts, "detail": detail,
            "holds": {beat: line for beat, line in held.items() if line}}


def merge(full: dict, second: dict, beats) -> dict:
    """``full`` with its rows for ``beats`` replaced by the second look's, and its totals counted again."""
    again = {str(row["beat"]): row for row in second.get("detail") or []}
    wanted = {str(b) for b in beats}
    rows = [again[str(row["beat"])] if str(row["beat"]) in wanted and str(row["beat"]) in again else row
            for row in full.get("detail") or []]
    counts = {k: 0 for k in FINDING_KINDS}
    for row in rows:
        for f in row.get("findings") or []:
            counts[f.get("kind") if f.get("kind") in FINDING_KINDS else "other"] += 1
    return {**full, "frames": len(rows), "findings": sum(counts.values()), "by_kind": counts,
            "frames_showing_intended": sum(1 for r in rows if r.get("shows_intended")),
            "frames_unreadable": sum(1 for r in rows if r.get("readable") is False), "detail": rows,
            "repaired_beats": sorted(set(full.get("repaired_beats") or []) | wanted)}


def default_judge(models: tuple[str, ...] = JUDGE_MODELS, temperature: float = 0.1, max_tokens: int = 600):
    """A (prompt, system, jpeg_b64) -> parsed JSON judge over OpenRouter, metered; None without a key.

    ``temperature`` 0 for a judge whose answer decides something in code (asked twice at 0.2, one judge answered a
    borderline question once each way).
    """
    import os
    key = (os.getenv("OPENROUTER_API_KEY") or "").strip()
    if not key:
        return None
    import httpx
    from .. import spend
    from ..engine.llm import cached_of, loads_json_lenient, system_message, thinking_for

    def call(prompt: str, system: str, jpeg_b64: str):
        spend.check(estimate=0.003, what="vision review frame")
        body = {"model": models[0], "temperature": temperature, "max_tokens": max_tokens, "usage": {"include": True},
                "response_format": {"type": "json_object"},
                "messages": [system_message(models[0], system),
                             {"role": "user", "content": [{"type": "text", "text": prompt},
                                                          {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{jpeg_b64}"}}]}]}
        if thinking_for(models[0]):                      # a model that answers better without thinking is asked that way here too
            body["reasoning"] = thinking_for(models[0])
        r = httpx.post("https://openrouter.ai/api/v1/chat/completions", json=body, timeout=90.0,
                       headers={"Authorization": f"Bearer {key}", "X-Title": "lessonforge"})
        if r.status_code != 200:
            raise RuntimeError(f"vision HTTP {r.status_code}: {r.text[:160]}")
        payload = r.json()
        usage = payload.get("usage") or {}
        spend.record("vision", models[0], usage.get("cost"), prompt_tokens=usage.get("prompt_tokens", 0),
                     completion_tokens=usage.get("completion_tokens", 0), generation_id=payload.get("id"),
                     note="frame", estimated=usage.get("cost") is None, cached_tokens=cached_of(usage))
        return loads_json_lenient(payload["choices"][0]["message"]["content"])
    return call
