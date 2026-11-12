"""Craft in a real render (video-quality plan S11): a title card, a closing hold and a thinking pause that leaves nothing stale.

Words-only lessons (no figure, no component library), a silent timeline, a low-quality render, frames read back with ffmpeg.
``craft: crafted`` against ``craft: plain`` on the same lesson. Free: no voice, no GPU.
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

pytestmark = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="needs ffmpeg")


def lesson_data(craft):
    quiz = {"question": "Which way does it go?", "options": ["Left", "Right", "Stays"], "answer_index": 1}
    beats = [
        {"id": "01", "narration": "A ball rolls to the right across the floor. It keeps rolling because nothing stops it.",
         "thinking_pause_seconds": 4.0, "quiz": quiz,
         "steps": [{"say": "A ball rolls", "show": "the ball rolls right", "kind": "point"},
                   {"say": "It keeps rolling", "show": "nothing stops it", "kind": "point"}]},
        {"id": "02", "narration": "The answer is to the right, because nothing pushes it back.",
         "steps": [{"say": "The answer is", "show": "to the right", "kind": "point"}]}]
    data = {"title": "A rolling ball", "thesis": "Things keep moving.", "chapters": [{"id": 1, "title": "ROLLING", "beats": beats}]}
    data["look"] = {**look.for_new(data, environ={}), "craft": craft}
    return data


def film(tmp_path, craft):
    data = lesson_data(craft)
    root = tmp_path / craft
    root.mkdir()
    (root / "lesson.json").write_text(json.dumps(data), encoding="utf-8")
    lesson = Lesson.model_validate(data)
    build_audio(lesson, root, "silent", BuildOptions(granularity="beat", align="off"), log=lambda *a: None)
    clip = build.render_chapters(root, lesson, quality="l", only=[1], jobs=1, log=lambda *a: None, extra_env={})[1]
    said = (root / "logs" / "C01.log").read_text(errors="replace")
    assert "LESSON_NOTE" not in said and "Traceback" not in said, said[-600:]
    return clip, json.loads((root / "timeline.json").read_text())


def frame(clip, at, tmp_path, name):
    shot = tmp_path / f"{name}_{at:.2f}.png"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-ss", f"{at:.3f}", "-i", str(clip), "-frames:v", "1", str(shot)], check=True)
    return np.asarray(Image.open(shot).convert("RGB")).astype(int)


def ink(pixels, top=0.12):
    """How many pixels differ from the page (the corner's colour), below the heading band."""
    page = pixels[-3, 3]
    body = pixels[int(pixels.shape[0] * top):]
    return int((np.abs(body - page).sum(axis=2) > 60).sum())


def heading(pixels):
    """Ink in the heading band at the top (the chapter's title and its number)."""
    page = pixels[-3, 3]
    return int((np.abs(pixels[: int(pixels.shape[0] * 0.12)] - page).sum(axis=2) > 60).sum())


def test_a_crafted_lesson_opens_on_its_title_and_holds_three_seconds_at_the_end(tmp_path):
    clip, crafted = film(tmp_path, "crafted")
    plain_clip, plain = film(tmp_path, "plain")
    assert crafted[-1]["duration"] - crafted[-1]["speech_end"] == pytest.approx(3.0, abs=0.05)
    title = frame(clip, 1.0, tmp_path, "c")
    assert ink(title) > 3000, "the title and its line stand on the page at 1 s"
    assert heading(title) == 0, "the card covers the chapter's heading"
    assert heading(frame(plain_clip, 1.0, tmp_path, "p")) > 300, "a plain lesson has its heading at 1 s"
    assert heading(frame(clip, 2.6, tmp_path, "c")) > 300, "and the crafted one has it back once the card is gone"


def test_a_crafted_pause_takes_the_steps_away_first_and_does_not_give_them_back(tmp_path):
    clip, crafted = film(tmp_path, "crafted")
    plain_clip, plain = film(tmp_path, "plain")
    end = crafted[1]["start"]                                   # the second beat begins where the pause ends
    late = ink(frame(clip, end - 0.15, tmp_path, "c"))
    plain_late = ink(frame(plain_clip, plain[1]["start"] - 0.15, tmp_path, "p"))
    assert plain_late > 1200, "plain: the steps are faded back in for the last moments of the pause (the stale words)"
    assert late < plain_late / 2, f"crafted: nothing of the beat's steps comes back ({late} against {plain_late})"


# ---------------------------------------------------------------- a new picture is drawn while the old one fades

SNAPSHOT = __import__("pathlib").Path(__file__).resolve().parents[1] / "unit" / "fixtures" / "lv_components"
PAPER = np.array([0xF7, 0xF3, 0xEA])


def two_pictures(craft):
    def beat(n, narration, comp, state):
        return {"id": n, "narration": narration, "steps": [{"say": narration.split()[0], "show": "words", "kind": "point"}],
                "figure": {"kind": "component", "params": {"id": comp, "state": state}}}
    data = {"title": "Two things", "chapters": [{"id": 1, "title": "TWO", "beats": [
        beat("01", "This is a slice across a leaf and its pores.", "leaf_section", {"opening": 1}),
        beat("02", "Here is a ball on a string that swings.", "simple_pendulum", {"time_s": 0})]}]}
    data["look"] = {**look.for_new(data, environ={}), "craft": craft}
    return data


def test_the_old_picture_is_never_gone_before_the_new_one_is_there_when_crafted(tmp_path):
    counts = {}
    for craft in ("crafted", "plain"):
        data = two_pictures(craft)
        root = tmp_path / ("x" + craft)
        root.mkdir()
        (root / "lesson.json").write_text(json.dumps(data), encoding="utf-8")
        lesson = Lesson.model_validate(data)
        build_audio(lesson, root, "silent", BuildOptions(granularity="beat", align="off"), log=lambda *a: None)
        clip = build.render_chapters(root, lesson, quality="l", only=[1], jobs=1, log=lambda *a: None,
                                     extra_env={"LESSON_VISUALS_DIR": str(SNAPSHOT)})[1]
        said = (root / "logs" / "C01.log").read_text(errors="replace")
        assert "LESSON_NOTE" not in said and "Traceback" not in said, said[-600:]
        start = json.loads((root / "timeline.json").read_text())[1]["start"]
        shots = [frame(clip, start + dt, tmp_path, "x" + craft) for dt in np.arange(-0.2, 1.6, 0.1)]
        counts[craft] = [int((np.abs(s - s[-3, 3]).sum(axis=2) > 60)[60:, :590].sum()) for s in shots]   # anything but the page
    assert min(counts["plain"]) < 0.5 * max(counts["plain"]), "plain: the card goes out before the next one is drawn in"
    assert min(counts["crafted"]) > 0.35 * max(counts["crafted"]), f"crafted: a picture is always there {counts['crafted']}"
