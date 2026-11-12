"""Craft at a lesson's edges and its pauses: the look key ``craft`` (video-quality plan S11), the parts that need no render.

``plain`` (every stored lesson, ``BEFORE``) is the lesson as it was; ``crafted`` (``look.for_new``) gives it a 2 s title card, a
3 s closing hold, pictures that cross-fade, a clean thinking pause and a speed-time graph that starts at 0. Free: no voice, no GPU.
"""
import json
from types import SimpleNamespace

import pytest

from lessonforge import knobs
from lessonforge.longform import audio, figures, look, motion_math
from lessonforge.longform.contract import Lesson


def lesson_dict(craft=None):
    data = {"title": "T", "thesis": "x", "chapters": [{"id": 1, "title": "ONE", "beats": [
        {"id": "01", "narration": "First beat here."}, {"id": "02", "narration": "Second beat here."}]}]}
    if craft is not None:
        data["look"] = {**look.for_new(environ={}), "craft": craft}
    return data


# ---------------------------------------------------------------- the look key

def test_stored_lessons_are_plain_and_new_ones_are_crafted():
    assert look.BEFORE["craft"] == "plain" and look.of(None, environ={})["craft"] == "plain"
    assert look.of({"look": {"frame": "stage"}}, environ={})["craft"] == "plain", "a look that does not say craft"
    assert look.for_new(environ={})["craft"] == "crafted"
    assert look.for_new(environ={"HARNESS_CRAFT": "plain"})["craft"] == "plain"
    assert look.for_new(environ={"HARNESS_FRAME": "columns"}) == look.BEFORE
    assert look.of({"look": {"frame": "stage", "craft": "crafted"}}, environ={})["craft"] == "crafted"
    assert look.of({"look": {"craft": "sparkly"}}, environ={})["craft"] == "plain", "a value nobody knows is not a look"
    assert look.of({"look": {"frame": "stage", "craft": "crafted"}}, environ={"LESSONFORGE_CRAFT": "plain"})["craft"] == "plain"
    assert look.of({"look": {"frame": "stage", "craft": "crafted"}}, environ={"LESSONFORGE_FRAME": "columns"})["craft"] == "plain", \
        "the old frame knows none of it"


def test_the_control_is_listed_and_read():
    control = knobs.BY_ID["HARNESS_CRAFT"]
    assert control.default == "crafted"


# ---------------------------------------------------------------- the timeline makes room for the card and the hold

def timeline(tmp_path, craft):
    data = lesson_dict(craft)
    root = tmp_path / str(craft)
    root.mkdir()
    audio.build_audio(Lesson.model_validate(data), root, "silent", audio.BuildOptions(granularity="beat", align="off"), log=lambda *a: None)
    return json.loads((root / "timeline.json").read_text())


def test_a_crafted_lesson_has_two_seconds_before_its_first_words_and_three_after_its_last(tmp_path):
    plain, crafted = timeline(tmp_path, "plain"), timeline(tmp_path, "crafted")
    assert crafted[0]["lead"] == pytest.approx(plain[0]["lead"] + audio.TITLE_CARD_SECONDS) and audio.TITLE_CARD_SECONDS == 2.0
    assert crafted[1]["lead"] == plain[1]["lead"], "only the lesson's first beat"
    assert crafted[1]["duration"] - crafted[1]["speech_end"] == pytest.approx(audio.CLOSING_HOLD_SECONDS, abs=1 / 30 + 1e-6)
    assert plain[1]["duration"] - plain[1]["speech_end"] == pytest.approx(audio.TAIL_SECONDS, abs=1 / 30 + 1e-6)
    assert crafted[0]["duration"] - plain[0]["duration"] == pytest.approx(2.0, abs=1 / 30 + 1e-6)
    assert audio.CLOSING_HOLD_SECONDS == 3.0


def test_a_lesson_with_no_look_is_timed_as_before(tmp_path):
    beats = timeline(tmp_path, None)
    assert [b["lead"] for b in beats] == [audio.LEAD_SECONDS, audio.LEAD_SECONDS], "a stored lesson: no card"
    assert beats[1]["duration"] - beats[1]["speech_end"] == pytest.approx(audio.TAIL_SECONDS, abs=1 / 30 + 1e-6)


# ---------------------------------------------------------------- the graph starts at 0

def goes(u, a, T=4.0, marks=(2.0,)):
    return motion_math.solve({"start_speed": u, "acceleration": a, "duration": T, "marks": list(marks)})


def test_a_speed_time_graph_of_non_negative_speeds_starts_at_zero_only_when_asked():
    m = goes(0, 2)
    assert motion_math.graph_params(m)["y_range"][0] < 0, "as before: padding below zero"
    crafted = motion_math.graph_params(m, zero_floor=True)["y_range"]
    assert crafted[0] == 0 and crafted[1] == motion_math.graph_params(m)["y_range"][1]
    down = goes(6, -3, T=4)                         # a velocity that goes negative keeps its room below
    assert motion_math.graph_params(down, zero_floor=True)["y_range"] == motion_math.graph_params(down)["y_range"]


def test_the_runtime_passes_the_flag_only_for_crafted_motion_figures(monkeypatch):
    seen = []
    monkeypatch.setattr(figures.kits, "builder_for", lambda kind: (lambda p: seen.append(dict(p)) or SimpleNamespace()))
    spec = {"kind": "motion", "params": {"start_speed": 0, "acceleration": 2, "duration": 4}}
    figures.build(spec)
    figures.build(spec, crafted=True)
    figures.build({"kind": "chem_reaction", "params": {"equation": "H2 + O2 -> H2O"}}, crafted=True)
    assert "zero_floor" not in seen[0] and seen[1]["zero_floor"] is True and "zero_floor" not in seen[2]
    assert spec["params"] == {"start_speed": 0, "acceleration": 2, "duration": 4}, "the lesson's own spec is not touched"
