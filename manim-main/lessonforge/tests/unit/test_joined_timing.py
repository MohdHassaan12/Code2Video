"""How long the silences are between beats and between chapters of a joined lesson (``audio._joined_leads``)."""
from types import SimpleNamespace as NS

import pytest

from lessonforge.longform import audio

A, B = {"kind": "bars", "n": 1}, {"kind": "circle", "r": 2}


def beats(*rows):
    """(chapter, figure, picture) per beat."""
    return [{"chapter": NS(id=ch), "beat": NS(figure=fig, picture=pic)} for ch, fig, pic in rows]


def test_a_picture_followed_across_chapters_needs_no_time_to_draw_and_beats_inside_a_chapter_breathe_shorter():
    made = beats((1, A, None), (1, None, None), (2, None, None), (2, B, None), (3, B, None), (3, None, "off"), (3, None, None))
    audio._joined_leads(made, audio.BuildOptions())
    leads = [round(b["lead"], 2) for b in made]
    tails = [round(b["tail"], 2) for b in made]
    # 1: drawn; 2: same picture; 3: a chapter's first beat that keeps it; 4: a new one drawn; 5: kept across the join;
    # 6: spoken without a picture; 7: the last one named, drawn in again
    assert leads == [1.5, .3, .5, 1.3, .5, .3, 1.3]
    assert tails == [.35, .6, .35, .6, .35, .35, .6]


def test_a_lesson_that_says_nothing_of_its_joins_keeps_its_old_timing(tmp_path):
    from lessonforge.longform.contract import Lesson
    data = {"title": "T", "thesis": "x.", "chapters": [
        {"id": 1, "title": "ONE", "beats": [{"id": "01", "narration": "One two three.", "figure": A},
                                            {"id": "02", "narration": "Four five six."}]},
        {"id": 2, "title": "TWO", "beats": [{"id": "03", "narration": "Seven eight nine."}]}]}
    for said, expected in ((None, [1.5, .5, .5]), ({"frame": "stage", "joins": "carried"}, [1.5, .3, .5])):
        lesson = Lesson.model_validate({**data, **({"look": said} if said else {})})
        root = tmp_path / str(bool(said))
        audio.build_audio(lesson, root, "silent", audio.BuildOptions(align="off"), log=lambda *a: None)
        import json
        timeline = json.loads((root / "timeline.json").read_text())
        assert [round(t["lead"], 2) for t in timeline] == pytest.approx(expected)
