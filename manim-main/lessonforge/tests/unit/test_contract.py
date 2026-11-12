"""Lesson Forge and the shared lesson contract (lesson-board docs/lesson-contract.md): scope/1 in, video-timeline/1 out."""
import json

from lessonforge.harness import contract

SCOPE = {"schema": "lesson-board/scope/1", "chapter_title": "Quadrilaterals", "lesson_title": "Diagonals of a parallelogram",
         "class": 9, "subject": "Mathematics",
         "learning_objectives": ["Show that the diagonals of a parallelogram bisect each other."],
         "allowed_concepts": [{"id": "c7", "title": "Diagonals bisect each other", "key_terms": ["diagonal", "bisect"]}],
         "prerequisites": [{"id": "c3", "title": "Opposite sides of a parallelogram are equal", "lesson_id": "u1"}],
         "excluded_content": [{"id": "c12", "title": "The mid-point theorem", "lesson_id": "u5"}],
         "max_duration_seconds": 420}


def test_a_scope_becomes_a_brief_the_writer_reads():
    b = contract.brief_from_scope({"scope": SCOPE, "glossary": [{"term": "diagonal", "meaning": "joins opposite corners",
                                                                  "notation": "AC, BD"}]})
    assert b["topic"] == "Diagonals of a parallelogram"
    assert b["goal"] == "Show that the diagonals of a parallelogram bisect each other"
    assert b["audience"] == "Class 9 students (NCERT Mathematics)" and b["duration_minutes"] == 6
    assert "Diagonals bisect each other (key terms: diagonal, bisect)" in b["notes"]["scope"]
    assert "Opposite sides" in b["notes"]["prerequisites"] and "mid-point theorem" in b["notes"]["left out"]
    assert "diagonal = joins opposite corners (written AC, BD)" in b["notes"]["words"]
    assert b["scope"] is SCOPE


def test_the_callers_own_fields_win_over_the_scope():
    b = contract.brief_from_scope({"scope": SCOPE, "topic": "Why diagonals cut each other in half", "duration_minutes": 3})
    assert b["topic"] == "Why diagonals cut each other in half" and b["duration_minutes"] == 3
    assert contract.is_scope({"scope": SCOPE}) and not contract.is_scope({"topic": "x"})


def test_a_finished_lesson_reads_as_a_video_timeline(tmp_path):
    lesson = {"title": "Diagonals", "chapters": [{"beats": [{"id": "01", "narration": "..."},
                                                            {"id": "02", "narration": "...", "equation": "AO = OC"}]}]}
    words = lambda t, a: [{"word": w, "start": a + i * 0.3, "end": a + i * 0.3 + 0.25} for i, w in enumerate(t.split())]
    timeline = [{"id": "01", "chapter": 1, "chapter_title": "Start", "start": 0.0, "duration": 4.0,
                 "sentences": [{"text": "Look at the shape.", "start": 0.5, "words": words("Look at the shape.", 0.5)}]},
                {"id": "02", "chapter": 2, "chapter_title": "Proof", "start": 4.0, "duration": 6.0,
                 "sentences": [{"text": "AO equals OC.", "start": 0.4, "words": words("AO equals OC.", 0.4)},
                               {"text": "So they bisect.", "start": 2.0, "words": words("So they bisect.", 2.0)}]}]
    (tmp_path / "lesson.json").write_text(json.dumps(lesson))
    (tmp_path / "timeline.json").write_text(json.dumps(timeline))
    vt = contract.video_timeline(tmp_path, "job1")
    assert vt["schema"] == "video-timeline/1" and vt["duration"] == 10.0 and vt["video_id"] == "job1"
    segs = vt["segments"]
    assert [s["narration"] for s in segs] == ["Look at the shape.", "AO equals OC.", "So they bisect."]
    assert segs[0]["timing"]["start"] == 0.0 and segs[-1]["timing"]["end"] == 10.0
    assert all(a["timing"]["end"] == b["timing"]["start"] for a, b in zip(segs, segs[1:]))   # one clock
    assert segs[1]["timing"]["start"] == 4.4 and segs[1]["tex"] == "AO = OC"
    assert {e["element_id"] for e in vt["elements"]} == {s["visual"]["element_id"] for s in segs}
