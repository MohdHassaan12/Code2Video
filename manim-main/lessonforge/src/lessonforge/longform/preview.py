"""A lesson as STILLS: how every step, pause and beat will look, with measurements, in seconds and without a voice.

The owner, 2026-10-10, on composition: "Render previews, detect problems, apply localized fixes, rerender, and run
regression tests. Add vision-based assessment for issues that bounding boxes cannot detect." Until then a lesson was
looked at only after its narration had been bought and every chapter filmed: a column of working that had to be
shrunk to fit, or a picture left small beside it, was found ten minutes and most of the lesson's cost too late, if
at all (thirteen checks passed on a lesson with six faults a viewer sees).

A beat is laid out ONCE, with every step in its place, before anything moves (``runtime.GuidedChapter``). So its
looks do not depend on the voice: with a timeline of estimated lengths and manim's ``-s`` (every animation jumps to
its end) the same code that films a chapter saves a picture after each step instead, and says what it measured
there (``runtime.LessonScene.still``). A seven-chapter lesson is previewed in well under a minute.

What comes back (``stills``):

* ``stills``: one record per picture: the file, the beat, what it shows ("step", "pause", "end"), and at each
  beat's end the layout's own numbers (how much of the frame, and of its own room, the picture has; the real size of
  every line);
* ``bounds`` and ``layout``: what the renderer's own checks found (outside the stage; overlap, clipping);
* ``findings`` (``measure``): the same, plus what the numbers say, each with the beat it is in and a ``fix`` a
  program can try. A phone held upright shows the frame about 203 points high: type smaller than
  ``SMALL_POINTS`` there is under 9 points, which is the size of a footnote.

Nothing here is paid for. What a vision model makes of the stills is ``harness/vision_review.assess``.
"""
from __future__ import annotations

import concurrent.futures
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

from .. import layout_probe
from . import build
from .audio import BuildOptions, build_audio
from .contract import Lesson

#: One point of type in the frame, in the points of a phone held upright (the frame is 8 units and about 203 points
#: high there; a 30-point line is 0.38 units of type).
PHONE_POINTS = 0.38 / 30 * 203 / 8
#: A line that stands alone is set at 44 points or more. Below this a line is small on a phone (under 9 points) …
SMALL_POINTS = 28.0
#: … and below this it cannot be read there (under 7).
UNREADABLE_POINTS = 22.0
#: A picture spans at least this much of the room the frame gave it, in width or in height; less, and it is a thumbnail
#: in a stage that had room for more. (Its share of the frame's AREA says nothing here: a strip of fraction bars or a
#: ball on a line is thin by nature and still reaches from one side of its room to the other.)
SMALL_PICTURE = 0.6
PREVIEW_TIMEOUT = 600


def stills(lesson_dir: str | Path, work: str | Path | None = None, quality: str = "l", jobs: int = 8,
           only: list[int] | None = None, env: dict | None = None, log=print, lesson: dict | None = None) -> dict:
    """Render a lesson's chapters as stills into ``work`` (default ``<lesson>/preview``) and return what was seen.

    The lesson folder itself is not written to. Its ``timeline.json`` is used when it has one (the real lengths);
    otherwise lengths are estimated from the words, which changes when a step appears and nothing about where.
    ``lesson``: the lesson to preview when it is not (yet) the folder's ``lesson.json``, or is that lesson with
    another look to be tried.
    """
    root = Path(lesson_dir).resolve()
    work = Path(work).resolve() if work else root / "preview"
    began = time.time()
    if work.exists():
        shutil.rmtree(work)
    (work / "logs").mkdir(parents=True)
    lesson_dict = lesson if lesson is not None else json.loads((root / "lesson.json").read_text(encoding="utf-8"))
    (work / "lesson.json").write_text(json.dumps(lesson_dict, ensure_ascii=False), encoding="utf-8")
    lesson = Lesson.model_validate(lesson_dict)
    for script in root.glob("*.py") if root.is_dir() else []:                       # hand-written chapters, when a lesson has them
        if script.name != build.AUTO_SCENES:
            shutil.copy2(script, work / script.name)
    if (root / "timeline.json").is_file():
        shutil.copy2(root / "timeline.json", work / "timeline.json")
        timing = "the lesson's own"
    else:
        build_audio(lesson, work, "silent", BuildOptions(granularity="beat", align="off"), log=lambda *a: None)
        timing = "estimated from the words"
    scenes = build.find_scenes(work, lesson)
    missing = [c.id for c in lesson.chapters if c.scene_name not in scenes]
    if missing:
        auto = build.write_auto_scenes(work, lesson, missing)
        scenes.update({f"C{i:02}": auto for i in missing})
    out = work / "stills"
    environment = {**os.environ, "LESSONFORGE_LESSON_DIR": str(work), "LESSONFORGE_STILLS": str(out), **(env or {})}

    def one(chapter):
        name = chapter.scene_name
        command = [sys.executable, "-m", "manim", f"-q{quality}", "-s", "--media_dir", str(work / "media" / name), str(scenes[name]), name]
        try:
            done = subprocess.run(command, capture_output=True, text=True, env=environment, cwd=work, timeout=PREVIEW_TIMEOUT)
            text, ok = (done.stdout or "") + (done.stderr or ""), done.returncode == 0
        except subprocess.TimeoutExpired:
            text, ok = f"LESSON_NOTE: the preview of {name} was stopped after {PREVIEW_TIMEOUT} s\n", False
        (work / "logs" / f"{name}.log").write_text(text, encoding="utf-8")
        return chapter.id, ok, text

    chapters = [c for c in lesson.chapters if not only or c.id in only]
    seen, bounds, layout, failed, notes = [], [], [], [], []
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, jobs)) as pool:
        for chapter_id, ok, text in pool.map(one, chapters):
            if not ok:
                failed.append(chapter_id)
                log(f"[preview] chapter {chapter_id:02} could not be previewed (logs/C{chapter_id:02}.log)")
            notes += [f"chapter {chapter_id:02}: {line.strip()[:200]}" for line in text.splitlines() if "LESSON_NOTE" in line]
            try:
                seen += json.loads((out / f"stills_c{chapter_id:02}.json").read_text(encoding="utf-8"))
            except (OSError, ValueError):
                pass
            try:
                audit = json.loads((work / "output" / f"chapter_{chapter_id:02}_audit.json").read_text(encoding="utf-8"))
                bounds += [{"chapter": chapter_id, "beat": record["beat"], **violation}
                           for record in audit.get("bounds") or [] for violation in record.get("bounds_violations") or []]
                beats = {record["beat"]: record.get("layout") for record in audit.get("bounds") or []}
            except (OSError, ValueError, KeyError):
                beats = {}
            for still in seen:
                if still.get("chapter") == chapter_id and still.get("beat") in beats and beats[still["beat"]]:
                    still.setdefault("layout", beats[still["beat"]])
            beat = None
            for line in text.splitlines():                 # the probe's own findings, each under the beat it was printed in
                mark = build._BEAT_MARK.search(line)
                if mark:
                    beat = mark.group(1)
                    continue
                layout += [{"chapter": chapter_id, "beat": beat, **found} for found in layout_probe.parse(line)]
    result = {"folder": str(out), "timing": timing, "chapters": len(chapters), "failed": failed, "stills": seen, "bounds": bounds,
              "layout": layout, "notes": notes, "seconds": round(time.time() - began, 1)}
    result["findings"] = measure(result)
    (work / "preview.json").write_text(json.dumps(result, indent=1, ensure_ascii=False), encoding="utf-8")
    log(f"[preview] {len(seen)} stills of {len(chapters)} chapter(s) in {result['seconds']:.0f} s ({timing} timing); "
        f"{len(result['findings'])} finding(s)" + (f"; chapters not previewed: {failed}" if failed else ""))
    return result


def faults(result: dict) -> int:
    """What must not get worse when a look is tried: chapters that could not be previewed, the renderer's own notes,
    things outside the stage, and collisions the layout probe counts."""
    return (len(result.get("failed") or []) + len(result.get("notes") or []) + len(result.get("bounds") or [])
            + sum(1 for item in result.get("layout") or [] if item.get("counted")))


def measure(result: dict) -> list[dict]:
    """What the stills' own numbers say is wrong, one finding per fault, each with the beat it is in.

    ``kind``: ``outside`` (something ends outside the stage), ``overlap`` (the layout probe counted a collision or a
    clipping), ``unreadable`` / ``small`` (a line of words set too small for a phone), ``thumbnail`` (the picture spans
    too little of the room it was given), ``small_label`` (the smallest writing inside the
    picture is under ``SMALL_POINTS``: medium from ``UNREADABLE_POINTS`` up, high below; reported only, never part of
    ``faults``). ``fix`` names what a program can try: ``split`` (show the beat's lines over more than one screen instead
    of shrinking them), ``enlarge``, ``compact``, or nothing.
    """
    found = []
    for violation in result.get("bounds") or []:
        found.append({"beat": violation.get("beat"), "chapter": violation.get("chapter"), "kind": "outside", "severity": "high",
                      "what": f"a {violation.get('type')} ends outside the stage", "fix": "compact"})
    for item in result.get("layout") or []:
        if item.get("counted"):
            found.append({"beat": item.get("beat"), "chapter": item.get("chapter"), "kind": "overlap", "severity": "high",
                          "what": f"{item.get('kind')}: {str(item.get('detail'))[:120]}", "fix": "compact"})
    for still in result.get("stills") or []:
        if still.get("what") != "end":
            continue
        lines = [line for line in still.get("lines") or [] if line.get("points")]
        tiny = [line for line in lines if line["points"] < UNREADABLE_POINTS]
        small = [line for line in lines if UNREADABLE_POINTS <= line["points"] < SMALL_POINTS]
        for group, kind, severity in ((tiny, "unreadable", "high"), (small, "small", "medium")):
            if group:
                worst = min(group, key=lambda line: line["points"])
                found.append({"beat": still["beat"], "chapter": still.get("chapter"), "kind": kind, "severity": severity,
                              "what": f"{len(group)} line(s) set at {worst['points']:.0f} points or less "
                                      f"({worst['points'] * PHONE_POINTS:.0f} on a phone): “{worst['show'][:50]}”",
                              "fix": "split" if len(lines) > 1 else ""})
        picture = still.get("picture")
        if picture and picture.get("fill") is not None and picture["fill"] < SMALL_PICTURE and lines:
            found.append({"beat": still["beat"], "chapter": still.get("chapter"), "kind": "thumbnail", "severity": "medium",
                          "what": f"the picture ({picture.get('kind')}) spans {picture['fill'] * 100:.0f}% of the room it was given "
                                  f"({(picture.get('share') or 0) * 100:.0f}% of the frame)", "fix": "enlarge"})
        points = (picture or {}).get("type_points")
        if points is not None and points < SMALL_POINTS:           # writing INSIDE the picture (a figure's labels), not the lines of words
            found.append({"beat": still["beat"], "chapter": still.get("chapter"), "kind": "small_label",
                          "severity": "medium" if points >= UNREADABLE_POINTS else "high",
                          "what": f"smallest label {points:.1f} points ({points * PHONE_POINTS:.1f} on a phone) in the "
                                  f"{picture.get('kind')} picture", "fix": ""})
    return found


def sheet(result: dict, file: str | Path, columns: int = 4, width: int = 480, what: tuple = ("end", "pause")) -> Path | None:
    """The stills of one kind on one sheet to look at, each with its beat written under it. None when there are none."""
    from PIL import Image, ImageDraw  # noqa: PLC0415
    picked = [s for s in result.get("stills") or [] if s.get("what") in what]
    if not picked:
        return None
    folder = Path(result["folder"])
    tiles = []
    for still in picked:
        try:
            image = Image.open(folder / still["file"]).convert("RGB")
        except OSError:
            continue
        image = image.resize((width, round(image.height * width / image.width)))
        layout = still.get("layout") or {}
        small = min((line["points"] for line in still.get("lines") or [] if line.get("points")), default=None)
        note = (f"{still['beat']} {still['what']}  {layout.get('mode', '')}/{layout.get('words', '')}"
                + (f"  picture {still['picture']['share'] * 100:.0f}%" if still.get("picture") else "")
                + (f"  smallest line {small:.0f} pt" if small else ""))
        tile = Image.new("RGB", (width, image.height + 18), "#202020")
        tile.paste(image, (0, 0))
        ImageDraw.Draw(tile).text((4, image.height + 3), note[:90], fill="white")
        tiles.append(tile)
    if not tiles:
        return None
    rows = (len(tiles) + columns - 1) // columns
    made = Image.new("RGB", (columns * width, rows * tiles[0].height), "black")
    for n, tile in enumerate(tiles):
        made.paste(tile, ((n % columns) * width, (n // columns) * tiles[0].height))
    file = Path(file)
    file.parent.mkdir(parents=True, exist_ok=True)
    made.save(file, quality=82)
    return file
