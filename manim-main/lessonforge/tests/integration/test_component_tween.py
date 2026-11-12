"""A library component whose number moves between two beats is MOVED in a real render (video-quality plan S7).

Two beats on one component (the leaf section, its stoma at opening 1 and then 0.3, from the pinned snapshot in
``tests/unit/fixtures/lv_components``), a silent timeline, a low-quality render, frames read back with ffmpeg. With
``LESSONFORGE_COMPONENT_TWEEN=1`` the card stays on screen through the change and the drawing passes through states that
are neither the old nor the new one; with it unset the card fades out and is drawn again, as before. Free: no voice, no GPU.
"""
import json
import shutil
import subprocess
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from lessonforge.longform import build, look
from lessonforge.longform.audio import BuildOptions, build_audio
from lessonforge.longform.contract import Lesson

pytestmark = pytest.mark.skipif(not shutil.which("ffmpeg") or not shutil.which("node"), reason="needs ffmpeg and node")

SNAPSHOT = Path(__file__).resolve().parents[1] / "unit" / "fixtures" / "lv_components"
PAPER = np.array([0xF7, 0xF3, 0xEA])


def lesson_data():
    span = [{"state": {"opening": 0.3}}, {"state": {"opening": 1}}]

    def beat(n, narration, opening, steps):
        return {"id": n, "narration": narration, "steps": steps,
                "figure": {"kind": "component", "params": {"id": "leaf_section", "state": {"opening": opening}, "span": span}}}
    first = "This is a slice across a leaf. The tiny pore in its lower skin is wide open, so air can pass through it."
    second = "Now the guard cells lose some water and the pore narrows, so less air and less water can pass."
    data = {"title": "A leaf", "thesis": "Pores open and close.", "chapters": [{"id": 1, "title": "THE PORE", "beats": [
        beat("01", first, 1, [{"say": "This is a", "show": "a slice across a leaf", "kind": "point"}]),
        beat("02", second, 0.3, [{"say": "Now the guard", "show": "the pore narrows", "kind": "point"}])]}]}
    data["look"] = look.for_new(data, environ={})
    return data


def frame(clip, at, tmp_path):
    """The picture's half of the frame (the words come in on the other side), under the heading."""
    shot = tmp_path / f"f_{at:.2f}.png"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-ss", f"{at:.3f}", "-i", str(clip), "-frames:v", "1", str(shot)], check=True)
    return np.asarray(Image.open(shot).convert("RGB")).astype(int)[60:, :590]


def paper(pixels):
    return int((np.abs(pixels - PAPER).sum(axis=2) < 8).sum())


def film(tmp_path, name, tween):
    data = lesson_data()
    root = tmp_path / name
    root.mkdir()
    (root / "lesson.json").write_text(json.dumps(data), encoding="utf-8")
    lesson = Lesson.model_validate(data)
    build_audio(lesson, root, "silent", BuildOptions(granularity="beat", align="off"), log=lambda *a: None)
    env = {"LESSON_VISUALS_DIR": str(SNAPSHOT), **({"LESSONFORGE_COMPONENT_TWEEN": "1"} if tween else {})}
    clip = build.render_chapters(root, lesson, quality="l", only=[1], jobs=1, log=lambda *a: None, extra_env=env)[1]
    said = (root / "logs" / "C01.log").read_text(errors="replace")
    assert "LESSON_NOTE" not in said and "Traceback" not in said, said[-600:]
    start = json.loads((root / "timeline.json").read_text())[1]["start"]
    return clip, start


def window(clip, start, tmp_path):
    """Frames every 0.1 s from just before the second beat to 2.2 s into it."""
    return [frame(clip, start + dt, tmp_path) for dt in np.arange(-0.1, 2.25, 0.1)]


def test_the_card_stays_and_the_drawing_passes_through_new_states_when_the_control_is_on(tmp_path):
    clip, start = film(tmp_path, "on", tween=True)
    frames = window(clip, start, tmp_path)
    before, after = frames[0], frames[-1]
    assert paper(before) > 20000 and paper(after) > 20000, "a card of paper in both beats"
    assert min(paper(f) for f in frames) > 0.85 * min(paper(before), paper(after)), "the card is never blank or half-built in between"
    between = [np.abs(f - before).mean() for f in frames[1:-1]], [np.abs(f - after).mean() for f in frames[1:-1]]
    middle = [i for i, (a, b) in enumerate(zip(*between)) if a > 0.15 and b > 0.15]
    assert middle, "some frame is neither the old picture nor the new one: the pore is moving"
    assert np.abs(frames[-1] - frames[-2]).mean() < 0.05, "and it ends still, on the new drawing"


def test_without_the_control_the_card_fades_and_is_drawn_again_as_before(tmp_path):
    clip, start = film(tmp_path, "off", tween=False)
    frames = window(clip, start, tmp_path)
    before = frames[0]
    assert min(paper(f) for f in frames) < 0.6 * paper(before), "the old picture fades out first (the fade this step replaces)"


def test_a_chapter_that_opens_on_the_screen_the_last_one_left_moves_the_carried_drawing_too(tmp_path):
    """Each chapter is a render of its own: the carried-over drawing (``GuidedChapter._carry_over``) is built again from
    the lesson's JSON, with its span, and the first beat of the next chapter morphs it."""
    data = lesson_data()
    beats = data["chapters"][0]["beats"]
    data["chapters"] = [{"id": 1, "title": "THE PORE", "beats": [beats[0]]}, {"id": 2, "title": "NARROWING", "beats": [beats[1]]}]
    root = tmp_path / "carried"
    root.mkdir()
    (root / "lesson.json").write_text(json.dumps(data), encoding="utf-8")
    lesson = Lesson.model_validate(data)
    build_audio(lesson, root, "silent", BuildOptions(granularity="beat", align="off"), log=lambda *a: None)
    env = {"LESSON_VISUALS_DIR": str(SNAPSHOT), "LESSONFORGE_COMPONENT_TWEEN": "1"}
    clip = build.render_chapters(root, lesson, quality="l", only=[2], jobs=1, log=lambda *a: None, extra_env=env)[2]
    said = (root / "logs" / "C02.log").read_text(errors="replace")
    assert "LESSON_NOTE" not in said and "Traceback" not in said, said[-600:]
    frames = [frame(clip, dt, tmp_path) for dt in np.arange(0.0, 3.0, 0.1)]
    before, after = frames[0], frames[-1]
    assert min(paper(f) for f in frames) > 0.85 * min(paper(before), paper(after)), "the card never goes"
    assert any(np.abs(f - before).mean() > 0.15 and np.abs(f - after).mean() > 0.15 for f in frames[1:-1]), "and the pore moves on it"
