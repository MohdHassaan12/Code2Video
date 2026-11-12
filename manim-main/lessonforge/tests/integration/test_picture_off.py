"""A beat marked ``"picture": "off"`` is shown without the picture, and the picture comes back after it (a real preview).

``harness/compose.mend`` sets the mark on a beat that has no picture of its own and is spoken over a drawing of
something else (a balloon to try at home, over a foot and a ball). The renderer has to take the picture away for
that beat only: within a chapter, across a chapter's end, and when the next beat names the same picture again.
"""
import shutil

import pytest

from lessonforge.longform import look, preview

pytestmark = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg not installed")

TRIANGLE = {"kind": "right_triangle", "a": 4, "b": 3, "unknown": "c"}


def beat(number, words, show, **more):
    return {"id": f"{number:02}", "narration": words, "steps": [{"say": " ".join(words.split()[:3]), "show": show, "kind": "point"}], **more}


def test_the_picture_leaves_for_that_beat_only_and_comes_back(tmp_path):
    lesson = {"title": "A ladder against a wall", "thesis": "The longest side faces the right angle.", "chapters": [
        {"id": 1, "title": "THE LADDER", "beats": [
            beat(1, "A ladder leans on a wall. The wall and the ground make a right angle.", "Wall and ground", figure=dict(TRIANGLE)),
            beat(2, "Now take a sheet of paper and fold one corner down. What shape do you get?", "Fold a corner", picture="off")]},
        {"id": 2, "title": "THE SIDES", "beats": [
            beat(3, "Back to the ladder. Its two short sides meet at the corner.", "Two short sides"),
            beat(4, "Find a book and stand it on a table. Where is its right angle?", "Stand a book up", picture="off"),
            beat(5, "The ladder is the longest side. It faces the right angle.", "Longest side", figure=dict(TRIANGLE))]},
        {"id": 3, "title": "AGAIN", "beats": [
            beat(6, "Say it once more. The longest side faces the right angle.", "Say it back")]}]}
    lesson["look"] = look.for_new(lesson, environ={})
    root = tmp_path / "lesson"
    root.mkdir()
    result = preview.stills(root, work=tmp_path / "preview", lesson=lesson, jobs=3, log=lambda *a: None)
    assert result["failed"] == [] and preview.faults(result) == 0, result["notes"]
    shown = {s["beat"]: bool(s.get("picture")) for s in result["stills"] if s["what"] == "end"}
    # 02 and 04 stand without it; 03 opens a chapter after a beat without it and gets it drawn in again; 05 names it
    # again; 06 opens a chapter that takes it over from the one before, as always
    assert shown == {"01": True, "02": False, "03": True, "04": False, "05": True, "06": True}
    # a beat without the picture has the frame for its words: they are not set in a column beside an empty space
    layouts = {s["beat"]: s.get("layout") or {} for s in result["stills"] if s["what"] == "end"}
    assert layouts["02"].get("mode") == layouts["04"].get("mode") == "words" and layouts["01"].get("mode") in ("side", "top")


def test_the_look_at_the_stills_takes_the_picture_off_the_beat_it_has_nothing_to_do_with(tmp_path, monkeypatch):
    """The whole step as a lesson meets it (``compose.settle``): preview, a look at each beat's end still, the picture
    taken off the beats that are about something else, their chapters previewed again, and the record written."""
    import json

    from lessonforge.harness import compose
    monkeypatch.setenv("HARNESS_COMPOSE_MEND", "pictures")
    monkeypatch.setenv("HARNESS_VISION_REVIEW", "1")
    lesson = {"title": "A ladder against a wall", "thesis": "The longest side faces the right angle.", "chapters": [
        {"id": 1, "title": "THE LADDER", "beats": [
            beat(1, "A ladder leans on a wall. The wall and the ground make a right angle.", "Wall and ground", figure=dict(TRIANGLE)),
            beat(2, "Now take a sheet of paper and fold one corner down. What shape do you get?", "Fold a corner")]},
        {"id": 2, "title": "THE SIDES", "beats": [
            beat(3, "Back to the ladder. Its two short sides meet at the corner.", "Two short sides"),
            beat(4, "The ladder is the longest side. It faces the right angle.", "Longest side", figure=dict(TRIANGLE))]}]}
    lesson["look"] = look.for_new(lesson, environ={})
    looks = []

    def judge(prompt, system, picture):
        looks.append(prompt)
        other = "sheet of paper" in prompt
        return {"shows": "a right triangle", "words_about": "folding paper" if other else "the ladder",
                "subject": "different" if other else "same", "pointed_at": [], "notes": [], "findings": []}
    root = tmp_path / "lesson"
    root.mkdir()
    said = []
    summary = compose.settle(lesson, root, judge=judge, log=said.append)
    beats = {b["id"]: b for c in lesson["chapters"] for b in c["beats"]}
    assert beats["02"].get("picture") == "off" and not any(beats[b].get("picture") for b in ("01", "03", "04"))
    assert summary["mended"]["picture_off"] == ["02"] and summary["mended"]["undone"] == [] and len(looks) == 4
    assert [f["kind"] for f in summary["seen"]] == ["mismatch"] and summary["seen"][0]["beat"] == "02"
    assert json.loads((root / "composition.json").read_text())["mended"]["kept"] == ["02"]
    assert any("beat 02: shown without the picture" in line for line in said)
    # what the lesson will be filmed as: previewed once more, the beat stands without the picture and the next has it back
    again = preview.stills(root, work=tmp_path / "again", lesson=lesson, jobs=2, log=lambda *a: None)
    assert {s["beat"]: bool(s.get("picture")) for s in again["stills"] if s["what"] == "end"} == {"01": True, "02": False, "03": True, "04": True}
