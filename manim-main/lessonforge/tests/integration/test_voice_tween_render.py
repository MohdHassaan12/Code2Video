"""A number moves across the sentence that says it, in a real render (video-quality plan S9).

Two beats on one component (the leaf section, opening 1 then 0.3, from the pinned snapshot), a silent timeline, a low-quality
render, frames read back with ffmpeg. The second beat's first step is flagged ``tween: "voice"`` and its sentence is long: with
``LESSONFORGE_COMPONENT_TWEEN=1`` the picture is still changing at several moments spread over the whole sentence (the lead-in
tween of S7 is over in 1.4 s), the card never goes, and it ends on the new drawing. Without the flag the same render moves only
in the lead-in. Free: no voice, no GPU.
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
LONG = ("Now the guard cells lose some water, and slowly, as the water goes out of them, the pore narrows "
        "until much less air and much less water can pass through it.")


def lesson_data(flag):
    span = [{"state": {"opening": 0.3}}, {"state": {"opening": 1}}]

    def beat(n, narration, opening, steps):
        return {"id": n, "narration": narration, "steps": steps,
                "figure": {"kind": "component", "params": {"id": "leaf_section", "state": {"opening": opening}, "span": span}}}
    step = {"say": "Now the guard", "show": "the pore narrows", "kind": "point", **({"tween": "voice"} if flag else {})}
    data = {"title": "A leaf", "thesis": "Pores open and close.", "chapters": [{"id": 1, "title": "THE PORE", "beats": [
        beat("01", "This is a slice across a leaf. The tiny pore in its lower skin is wide open.", 1,
             [{"say": "This is a", "show": "a slice across a leaf", "kind": "point"}]),
        beat("02", LONG, 0.3, [step])]}]}
    data["look"] = look.for_new(data, environ={})
    return data


def frames(tmp_path, flag):
    data = lesson_data(flag)
    root = tmp_path / ("flag" if flag else "plain")
    root.mkdir()
    (root / "lesson.json").write_text(json.dumps(data), encoding="utf-8")
    lesson = Lesson.model_validate(data)
    build_audio(lesson, root, "silent", BuildOptions(granularity="beat", align="off"), log=lambda *a: None)
    env = {"LESSON_VISUALS_DIR": str(SNAPSHOT), "LESSONFORGE_COMPONENT_TWEEN": "1"}
    clip = build.render_chapters(root, lesson, quality="l", only=[1], jobs=1, log=lambda *a: None, extra_env=env)[1]
    said = (root / "logs" / "C01.log").read_text(errors="replace")
    assert "LESSON_NOTE" not in said and "Traceback" not in said, said[-600:]
    timeline = json.loads((root / "timeline.json").read_text())
    beat = timeline[1]
    spoken = beat["start"] + beat["sentences"][0]["start"]
    end = beat["start"] + beat["speech_end"]
    out = []
    for at in np.arange(spoken - 0.3, end - 0.6, 0.5):          # the beat's own last words come in after this
        shot = tmp_path / f"{root.name}_{at:.2f}.png"
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-ss", f"{at:.3f}", "-i", str(clip), "-frames:v", "1", str(shot)], check=True)
        out.append(np.asarray(Image.open(shot).convert("RGB")).astype(int)[60:, :590])
    return out, end - spoken


def moving_steps(shots):
    return [float(np.abs(b - a).mean()) for a, b in zip(shots, shots[1:])]


def test_the_picture_is_moving_through_the_whole_sentence_when_the_step_is_flagged(tmp_path):
    shots, length = frames(tmp_path, flag=True)
    steps = moving_steps(shots)
    assert length > 4.0
    moving = [s > 0.05 for s in steps[3:-1]]
    assert sum(moving) >= len(moving) - 1, f"changing at (nearly) every half second of the sentence: {[round(s, 3) for s in steps]}"
    # (one step in a clip of this length is the encoder's own scene cut, a tint all over the frame; none is the old picture going)
    assert sorted(steps[3:])[-2] < 0.6, f"and no jump when the old picture goes: it was the new one {[round(s, 3) for s in steps]}"


def test_without_the_flag_the_move_is_over_in_the_lead_in(tmp_path):
    shots, length = frames(tmp_path, flag=False)
    steps = moving_steps(shots)
    assert sum(s > 0.004 for s in steps[4:]) <= 1, f"nothing moves once the words have begun: {[round(s, 3) for s in steps]}"
