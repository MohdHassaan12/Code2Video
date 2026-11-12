"""A prepared drawing is DRAWN, part by part, when it arrives (a real render with a real browser).

The owner, 2026-10-12: "the visuals are static … different parts of the visual should be coming in a sequence".
The drawing's SVG is taken apart into a sequence of parts (``harness/sequence.py``), and a lesson whose look says
``drawings: painted`` films the picture being drawn from it while the beat's words begin
(``figures.PictureFigure.paint``, ``runtime.GuidedChapter._start_paint``). An older lesson shows it as before.
"""
import json
import shutil
import subprocess

import numpy as np
import pytest
from PIL import Image, ImageDraw

from lessonforge.harness import diagrams, sequence
from lessonforge.longform import build, look
from lessonforge.longform.audio import BuildOptions, build_audio
from lessonforge.longform.contract import Lesson

pytestmark = pytest.mark.skipif(not shutil.which("ffmpeg") or not diagrams.browser(), reason="needs ffmpeg and a headless browser")

SVG = ("<svg xmlns='http://www.w3.org/2000/svg' width='400' height='240' viewBox='0 0 400 240'>"
       "<path d='M 40 200 L 200 30 L 360 200 Z' fill='rgb(204,216,255)' stroke='rgb(0,0,153)' stroke-width='4'/>"
       "<line x1='20' y1='30' x2='380' y2='30' stroke='rgb(102,102,102)' stroke-width='3' stroke-dasharray='10 8'/>"
       "<circle cx='200' cy='150' r='26' fill='none' stroke='rgb(153,77,0)' stroke-width='4'/>"
       "<text x='188' y='226' font-size='22'>BC</text></svg>")


def the_drawing(tmp_path):
    folder = tmp_path / "library" / "a_triangle-0123456789"
    folder.mkdir(parents=True)
    (folder / "source.svg").write_text(SVG, encoding="utf-8")
    whole = Image.new("RGB", (800, 480), "white")
    pen = ImageDraw.Draw(whole)
    pen.polygon([(80, 400), (400, 60), (720, 400)], fill="#ccd8ff", outline="#000099")
    pen.line([(40, 60), (760, 60)], fill="#666666", width=4)
    pen.ellipse([348, 248, 452, 352], outline="#994d00", width=6)
    whole.save(folder / "whole.png")
    (folder / "manifest.json").write_text(json.dumps({"whole": "whole.png", "width": 800, "height": 480}), encoding="utf-8")
    return folder


def ink(clip, at, tmp_path):
    """How much of the frame at ``at`` seconds is not paper: the drawing's own ink, whatever its colour."""
    shot = tmp_path / f"frame_{at}.png"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-ss", str(at), "-i", str(clip), "-frames:v", "1", str(shot)], check=True)
    pixels = np.asarray(Image.open(shot).convert("RGB")).astype(int)
    left = pixels[60:, : pixels.shape[1] // 2]                     # the picture's half of the frame, under the heading
    return int((np.abs(left - left[5, 5]).sum(axis=2) > 60).sum())


def test_the_drawing_is_drawn_part_by_part_and_stands_finished_afterwards(tmp_path):
    folder = the_drawing(tmp_path)
    made = sequence.sequence(folder, log=lambda *a: None)
    assert made and [p["kind"] for p in made["parts"]].count("text") == 1 and len(made["parts"]) == 4
    figure = {"kind": "picture", "file": str(folder / "whole.png")}
    step = lambda words: [{"say": " ".join(words.split()[:3]), "show": "The triangle", "kind": "point"}]      # noqa: E731
    first = "Here is a triangle with a line through its top. Look at its three corners, one after another, slowly and carefully."
    data = {"title": "A triangle", "thesis": "Three corners.", "chapters": [{"id": 1, "title": "CORNERS", "beats": [
        {"id": "01", "narration": first, "figure": figure, "steps": step(first)},
        {"id": "02", "narration": "The line through the top is parallel to the base.", "steps": step("The line through")}]}]}
    data["look"] = look.for_new(data, environ={})
    assert data["look"]["drawings"] == "painted"
    root = tmp_path / "lesson"
    root.mkdir()
    (root / "lesson.json").write_text(json.dumps(data), encoding="utf-8")
    lesson = Lesson.model_validate(data)
    build_audio(lesson, root, "silent", BuildOptions(granularity="beat", align="off"), log=lambda *a: None)
    clip = build.render_chapters(root, lesson, quality="l", only=[1], jobs=1, log=lambda *a: None)[1]
    said = (root / "logs" / "C01.log").read_text(errors="replace")
    assert "LESSON_NOTE" not in said and "Traceback" not in said
    layouts = {record["beat"]: record["layout"] for record in json.loads((root / "output" / "chapter_01_audit.json").read_text())["bounds"]}
    assert layouts["01"]["painted"] >= 1.2 and "painted" not in layouts["02"]     # drawn once, in the beat that brings it
    early, late = ink(clip, 0.7, tmp_path), ink(clip, layouts["01"]["painted"] + 1.5, tmp_path)
    assert 0 < early < 0.6 * late                                   # under way at first, and whole once the pen is done
    assert abs(ink(clip, layouts["01"]["painted"] + 3.0, tmp_path) - late) < 0.05 * late      # … and it stays as it is

    # the same lesson made before today says nothing of it: its drawing is shown whole from its first moment
    before = {**data, "look": {k: v for k, v in data["look"].items() if k != "drawings"}}
    old = tmp_path / "older"
    old.mkdir()
    (old / "lesson.json").write_text(json.dumps(before), encoding="utf-8")
    shutil.copy2(root / "timeline.json", old / "timeline.json")
    shutil.copytree(root / "audio", old / "audio")
    clip = build.render_chapters(old, Lesson.model_validate(before), quality="l", only=[1], jobs=1, log=lambda *a: None)[1]
    shown = {record["beat"]: record["layout"] for record in json.loads((old / "output" / "chapter_01_audit.json").read_text())["bounds"]}
    assert "painted" not in shown["01"]


def test_a_part_waits_for_the_step_whose_words_bring_it_and_the_next_chapter_finds_it_there(tmp_path):
    """A drawing drawn WITH the words (``harness/sequence.with_words`` plans it; here the steps carry the plan): what a
    later step brings is not on the paper before its words, is drawn when they come, and stands in the next chapter,
    which is a render of its own. A reference lecture's board holds nothing before it is spoken of; ours held the
    whole proof from the fifth second (docs/research/approaches/12)."""
    folder = the_drawing(tmp_path)
    made = sequence.sequence(folder, log=lambda *a: None)
    dashed = next(p["n"] for p in made["parts"] if p.get("dashed"))
    ring = next(p["n"] for p in made["parts"] if p["kind"] == "stroke" and not p.get("dashed"))
    figure = {"kind": "picture", "file": str(folder / "whole.png")}
    first = ("Here is a triangle, standing on its own for a while, so we can look at it. "
             "Now a dashed line is drawn through its top, slowly and carefully, from one side to the other side.")
    second = "A ring is drawn inside the triangle now. It stays there until the very end of this short lesson."
    data = {"title": "A triangle", "thesis": "Three corners.", "chapters": [
        {"id": 1, "title": "CORNERS", "beats": [{"id": "01", "narration": first, "figure": dict(figure), "steps": [
            {"say": "Here is a", "show": "The triangle", "kind": "point"},
            {"say": "Now a dashed", "show": "A line through the top", "kind": "point", "draw": [dashed]}]}]},
        {"id": 2, "title": "A RING", "beats": [{"id": "02", "narration": second, "figure": dict(figure), "steps": [
            {"say": "A ring is", "show": "A ring inside", "kind": "point", "draw": [ring]}]}]}]}
    data["look"] = look.for_new(data, environ={})
    root = tmp_path / "lesson"
    root.mkdir()
    (root / "lesson.json").write_text(json.dumps(data), encoding="utf-8")
    lesson = Lesson.model_validate(data)
    build_audio(lesson, root, "silent", BuildOptions(granularity="beat", align="off"), log=lambda *a: None)
    clips = build.render_chapters(root, lesson, quality="l", jobs=2, log=lambda *a: None)
    for chapter in (1, 2):
        said = (root / "logs" / f"C{chapter:02d}.log").read_text(errors="replace")
        assert "LESSON_NOTE" not in said and "Traceback" not in said
    audits = {n: json.loads((root / "output" / f"chapter_{n:02d}_audit.json").read_text()) for n in (1, 2)}
    assert audits[1]["bounds"][0]["layout"]["built"] is True and audits[1]["bounds"][0]["layout"]["painted"] >= 1.2
    line_said = next(c["anchor"] for c in audits[1]["cues"] if c["phrase"].startswith("Now a dashed"))
    alone = ink(clips[1], line_said - .4, tmp_path)                 # the triangle has been drawn; the line's words have not come
    with_line = ink(clips[1], line_said + 3.2, tmp_path)
    assert alone > 0 and with_line - alone > 300                    # the line was drawn when it was spoken of (a thin line: pixels)
    assert abs(ink(clips[1], line_said - 1.2, tmp_path) - alone) < 150               # ... and nothing crept in before
    # the next chapter opens on the drawing as this one left it: triangle and line, no ring yet
    opens = ink(clips[2], 0.4, tmp_path)
    assert abs(opens - with_line) < 200
    ring_said = next(c["anchor"] for c in audits[2]["cues"] if c["phrase"].startswith("A ring is"))

    def ring_pixels(at):                            # the ring's own colour (the finished picture's ink differs from the pen's)
        shot = tmp_path / f"ring_{at}.png"
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-ss", str(at), "-i", str(clips[2]), "-frames:v", "1", str(shot)], check=True)
        pixels = np.asarray(Image.open(shot).convert("RGB")).astype(int)
        return int((np.abs(pixels - np.array([153, 77, 0])).sum(axis=2) < 90).sum())
    assert ring_pixels(0.4) < 20 and ring_pixels(ring_said + 3.2) > 150      # the ring comes with its words
    assert audits[2]["bounds"][0]["layout"]["built"] is True        # when the beat began, a part was still to come


def test_a_hand_writes_on_the_drawing_when_its_words_are_spoken_and_the_record_says_from_when_to_when(tmp_path):
    """What a hand adds to a drawing (``harness/annotate.py`` ideates and places it; here the steps carry the marks): a
    value is written when the voice says it and stays, a ring leaves with its beat, and the chapter's record has each
    mark's start and end. The owner, 2026-10-12: "the image is not being annotated … starting and ending time stamps
    for synchrony"."""
    import math
    folder = the_drawing(tmp_path)
    sequence.sequence(folder, log=lambda *a: None)
    figure = {"kind": "picture", "file": str(folder / "whole.png")}
    ring = {"id": "m1", "slot": "", "kind": "ring", "life": "beat", "say": "", "text": "",
            "prims": [{"shape": "path", "closed": True, "points": [[.5 + .12 * math.cos(i / 6), .62 + .16 * math.sin(i / 6)] for i in range(38)]}]}
    value = {"id": "m2", "slot": "value:1", "kind": "value", "life": "stays", "say": "sixty degrees", "text": "60°", "needs": [1],
             "prims": [{"shape": "text", "box": [.56, .3, .76, .42], "text": "60°"}]}
    first = ("Here is a triangle, standing on its own for a little while so that we can look at it. "
             "Its top corner measures sixty degrees, and that is what we write down on the picture now.")
    data = {"title": "A triangle", "thesis": "Three corners.", "chapters": [{"id": 1, "title": "CORNERS", "beats": [
        {"id": "01", "narration": first, "figure": dict(figure), "steps": [
            {"say": "Here is a", "show": "The triangle", "kind": "point", "annotate": [ring]},
            {"say": "Its top corner", "show": "Top corner", "kind": "point", "annotate": [value]}]},
        {"id": "02", "narration": "The value stays on the picture for the rest of this short lesson, and the ring has gone.", "figure": dict(figure),
         "steps": [{"say": "The value stays", "show": "It stays", "kind": "point"}]}]}]}
    data["look"] = look.for_new(data, environ={})
    root = tmp_path / "lesson"
    root.mkdir()
    (root / "lesson.json").write_text(json.dumps(data), encoding="utf-8")
    lesson = Lesson.model_validate(data)
    build_audio(lesson, root, "silent", BuildOptions(granularity="beat", align="off"), log=lambda *a: None)
    clip = build.render_chapters(root, lesson, quality="l", only=[1], jobs=1, log=lambda *a: None)[1]
    said = (root / "logs" / "C01.log").read_text(errors="replace")
    assert "LESSON_NOTE" not in said and "Traceback" not in said
    layouts = {record["beat"]: record["layout"] for record in json.loads((root / "output" / "chapter_01_audit.json").read_text())["bounds"]}
    marks = {m["id"]: m for m in layouts["01"]["annotations"]}
    assert marks["m2"]["text"] == "60°" and marks["m2"]["with"] == "words" and marks["m2"]["end"] is None      # with its own words; it stays
    # the ring is a gesture: it comes with its step and leaves after a few seconds, long before the beat is over
    assert marks["m1"]["start"] < marks["m2"]["start"] and abs(marks["m1"]["end"] - marks["m1"]["start"] - 4.5) < 0.3
    assert "annotations" not in layouts["02"]

    def red(at):                                        # the hand's own ink (the drawing's brown ring is another colour)
        shot = tmp_path / f"red_{at}.png"
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-ss", str(at), "-i", str(clip), "-frames:v", "1", str(shot)], check=True)
        pixels = np.asarray(Image.open(shot).convert("RGB")).astype(int)
        picture = pixels[60:, : pixels.shape[1] // 2]              # the picture's half of the frame: the words beside it have colours of their own
        return int((np.abs(picture - np.array([198, 40, 40])).sum(axis=2) < 100).sum())
    before, ring_there = red(max(0.2, marks["m1"]["start"] - .4)), red(marks["m1"]["start"] + 1.5)
    ring_gone = red(marks["m1"]["end"] + .5)
    written, next_beat = red(marks["m2"]["start"] + 1.2), red(17.5)
    seen = json.dumps({"before": before, "ring": ring_there, "gone": ring_gone, "written": written, "next beat": next_beat, "marks": marks})
    assert before < 20 < ring_there and ring_gone < 20, seen           # nothing; the ring; nothing again
    assert written > 100 and abs(next_beat - written) < 0.15 * written, seen      # the value is written, and stands in the next beat
