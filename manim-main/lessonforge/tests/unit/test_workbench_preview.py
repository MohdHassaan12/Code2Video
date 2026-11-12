"""workbench.preview lays the lesson out as the FILM does (S1 of the video-quality plan), and writes nothing into the lesson.

Free: ``longform.preview.stills`` and ``sheet`` are replaced by recorders, so no Manim runs, and ``compose.settle`` (which
asks a vision model) is made to fail loudly if anything calls it.
"""
import pytest

from lessonforge.harness import compose
from lessonforge.harness import workbench as W
from lessonforge.longform import preview as P

SPEEDING = {"kind": "motion", "start_speed": 0, "acceleration": 2, "duration": 6, "marks": [3, 6]}


def _lesson(figure=SPEEDING, look=None):
    beat = {"id": "01", "narration": "The car speeds up.", "steps": [{"say": "The car speeds up", "show": "v = 2t", "kind": "point"}]}
    if figure is not None:
        beat["figure"] = figure
    lesson = {"title": "Speeding up", "chapters": [{"id": 1, "title": "ONE", "learning_goal": "g", "role": "explain", "beats": [beat]}]}
    if look is not None:
        lesson["look"] = look
    return lesson


@pytest.fixture()
def seen(tmp_path, monkeypatch):
    """Record what ``preview`` hands the renderer; no Manim, and the paid settle step is forbidden."""
    monkeypatch.setenv("LESSONFORGE_HOME", str(tmp_path))
    for name in ("HARNESS_FRAME", "HARNESS_COMPOSE", "HARNESS_PAGE", "HARNESS_CAPTIONS"):
        monkeypatch.delenv(name, raising=False)
    calls = []

    def stills(root, work=None, lesson=None, **kw):
        calls.append(lesson)
        return {"stills": [], "findings": [], "failed": [], "folder": str(work)}

    monkeypatch.setattr(P, "stills", stills)
    monkeypatch.setattr(P, "sheet", lambda *a, **k: None)
    monkeypatch.setattr(compose, "settle", lambda *a, **k: pytest.fail("the preview must not call compose.settle (a vision judge)"))
    return calls


def _add(lesson):
    return W.add(lesson, "t")["lesson_id"]


def test_a_code_drawn_lesson_is_previewed_in_the_stage_frame_with_filled_pictures(seen):
    lid = _add(_lesson())
    W.preview(lid, log=lambda *a: None)
    (got,) = seen
    assert got["look"]["frame"] == "stage" and got["look"]["pictures"] == "fill" and got["look"]["captions"] == "outside"
    assert got["look"]["working"] == "pinned" and got["look"]["joins"] == "carried"       # the film's other new-lesson keys
    assert "look" not in W.load(lid)                                                      # never saved into the lesson


def test_pictures_stay_kept_when_compose_is_off_or_nothing_is_drawn_by_code(seen, monkeypatch):
    lid = _add(_lesson(figure=None))
    W.preview(lid, log=lambda *a: None)
    assert seen[-1]["look"]["frame"] == "stage" and seen[-1]["look"]["pictures"] == "kept"
    lid = _add(_lesson())
    monkeypatch.setenv("HARNESS_COMPOSE", "0")
    W.preview(lid, log=lambda *a: None)
    assert seen[-1]["look"]["frame"] == "stage" and seen[-1]["look"]["pictures"] == "kept"


def test_the_columns_setting_keeps_the_old_preview(seen, monkeypatch):
    monkeypatch.setenv("HARNESS_FRAME", "columns")
    lid = _add(_lesson())
    W.preview(lid, log=lambda *a: None)
    assert seen[-1]["look"]["frame"] == "columns" and seen[-1]["look"]["pictures"] == "kept"


def test_a_stored_look_is_replaced_as_the_film_replaces_it_and_the_stored_lesson_is_untouched(seen):
    old = {"frame": "columns", "captions": "band", "page": "night", "pictures": "kept", "working": "column",
           "drawings": "shown", "joins": "cut", "math": "serif"}
    lid = _add(_lesson(look=old))
    before = W.load(lid)
    W.preview(lid, log=lambda *a: None)
    assert seen[-1]["look"]["frame"] == "stage" and seen[-1]["look"]["pictures"] == "fill"
    assert W.load(lid) == before and before["look"] == old and len(W._versions(W._folder(lid))) == 1


def test_film_layout_is_a_copy(seen):
    lesson = _lesson()
    framed = W.film_layout(lesson)
    assert "look" not in lesson and framed is not lesson and framed["chapters"] == lesson["chapters"]
    assert W.film_layout(framed)["look"] == framed["look"]                                # idempotent
