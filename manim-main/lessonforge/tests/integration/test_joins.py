"""A chapter opens on the screen the chapter before left (a real render).

Each chapter is a render of its own and the chapters are joined by a cut. The owner, 2026-10-15: "a somewhat choppy
experience. It is not continuous". With ``joins: carried`` (``look.py``) the first frame of a chapter is the last
frame of the one before, less the heading, which cross-fades; the picture then changes from there. A lesson made
before says nothing of its joins and is cut as it always was.
"""
import json
import shutil
import subprocess

import numpy as np
import pytest
from PIL import Image

from lessonforge.longform import build, look
from lessonforge.longform.audio import BuildOptions, build_audio
from lessonforge.longform.contract import Lesson

pytestmark = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg not installed")

TRIANGLE = {"kind": "right_triangle", "a": 4, "b": 3, "unknown": "c"}
BARS = {"kind": "bars", "parts": [{"label": "1/2", "n": 1, "d": 2}, {"label": "2/4", "n": 2, "d": 4}]}


def beat(number, words, show, **more):
    return {"id": f"{number:02}", "narration": words, "steps": [{"say": " ".join(words.split()[:3]), "show": show, "kind": "point"}], **more}


def a_lesson(joins):
    data = {"title": "A ladder against a wall", "thesis": "The longest side faces the right angle.", "chapters": [
        {"id": 1, "title": "THE LADDER", "beats": [
            beat(1, "A ladder leans on a wall. The wall and the ground make a right angle.", "Wall and ground", figure=dict(TRIANGLE)),
            beat(2, "Its foot is three metres out and it reaches four metres up.", "Three out, four up")]},
        {"id": 2, "title": "THE LENGTHS", "beats": [
            beat(3, "Put the three lengths side by side. The ladder is the longest of them.", "Side by side", figure=dict(BARS)),
            beat(4, "Five is more than three and more than four.", "Five is the longest")]},
        {"id": 3, "title": "AGAIN", "beats": [
            beat(5, "Say it once more. The longest side faces the right angle.", "Say it back")]}]}
    data["look"] = {**look.for_new(data, environ={}), "joins": joins}
    return data


def frame(clip, tmp_path, name, last=False):
    shot = tmp_path / f"{name}.png"
    where = ["-sseof", "-0.1"] if last else ["-ss", "0"]
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", *where, "-i", str(clip), "-frames:v", "1", "-update", "1", str(shot)], check=True)
    pixels = np.asarray(Image.open(shot).convert("RGB")).astype(int)
    return pixels[pixels.shape[0] // 8:]                     # the stage, under the line of heading


def changed(a, b):
    """Share of the stage's pixels that differ between two frames."""
    return float((np.abs(a - b).sum(axis=2) > 60).mean())


def ink(pixels):
    return float((np.abs(pixels - pixels[5, 5]).sum(axis=2) > 60).mean())


def film(tmp_path, joins):
    data = a_lesson(joins)
    root = tmp_path / joins
    root.mkdir()
    (root / "lesson.json").write_text(json.dumps(data), encoding="utf-8")
    lesson = Lesson.model_validate(data)
    build_audio(lesson, root, "silent", BuildOptions(granularity="beat", align="off"), log=lambda *a: None)
    clips = build.render_chapters(root, lesson, quality="l", jobs=3, log=lambda *a: None)
    for n in (1, 2, 3):
        said = (root / "logs" / f"C0{n}.log").read_text(errors="replace")
        assert "LESSON_NOTE" not in said and "Traceback" not in said, said[-2000:]
    timeline = json.loads((root / "timeline.json").read_text())
    return clips, timeline


def test_a_chapter_opens_on_the_screen_the_last_one_left(tmp_path):
    clips, timeline = film(tmp_path, "carried")
    for before, after in ((1, 2), (2, 3)):
        end, start = frame(clips[before], tmp_path, f"end{before}", last=True), frame(clips[after], tmp_path, f"start{after}")
        assert ink(start) > .01                               # the picture and the words are there at once
        assert changed(end, start) < .02, (before, after)     # ... as the chapter before left them
    # chapter 3 keeps the bars it took over, and its first beat draws nothing: it needs no time to draw
    leads = {t["id"]: t["lead"] for t in timeline}
    assert leads["03"] == pytest.approx(1.5) and leads["05"] == pytest.approx(.5) and leads["04"] == pytest.approx(.3)


def test_a_lesson_that_says_nothing_of_its_joins_is_cut_as_before(tmp_path):
    clips, timeline = film(tmp_path, "cut")
    end, start = frame(clips[1], tmp_path, "end1", last=True), frame(clips[2], tmp_path, "start2")
    assert ink(start) < .002 and changed(end, start) > .01    # an empty stage after the cut
    leads = {t["id"]: t["lead"] for t in timeline}
    assert leads["03"] == pytest.approx(1.5) and leads["05"] == pytest.approx(.5) and leads["04"] == pytest.approx(.5)
