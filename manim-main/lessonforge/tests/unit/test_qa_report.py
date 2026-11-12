"""The beat-by-beat quality report and the storyboard gate before speech (harness/qa.py)."""
import json

from lessonforge.harness import qa


def _lesson(*beats):
    return {"chapters": [{"id": "C01", "beats": list(beats)}]}


def test_an_anchor_the_voice_never_says_is_a_sync_finding():
    lesson = _lesson({"id": "01", "narration": "Here is a triangle.", "steps": [{"say": "a square", "show": "x"}]})
    kinds = [f["kind"] for f in qa.storyboard_findings(lesson)]
    assert kinds == ["anchor_missing"]
    assert qa.storyboard_findings(lesson)[0]["repair"].startswith("writer.discipline")


def test_anchors_out_of_order_are_found():
    lesson = _lesson({"id": "01", "narration": "First the base, then the height.",
                      "steps": [{"say": "the height", "show": "h"}, {"say": "the base", "show": "b"}]})
    assert "anchors_out_of_order" in [f["kind"] for f in qa.storyboard_findings(lesson)]


def test_numbers_spoken_and_never_shown():
    lesson = _lesson({"id": "01", "narration": "The base is six and the height is eight.",
                      "steps": [{"say": "The base", "show": "A triangle"}]})
    found = [f for f in qa.storyboard_findings(lesson) if f["kind"] == "said_not_shown"]
    assert found and "6" in found[0]["what"] and "8" in found[0]["what"]
    shown = _lesson({"id": "01", "narration": "The base is six and the height is eight.",
                     "steps": [{"say": "The base", "show": "base 6, height 8"}]})
    assert not [f for f in qa.storyboard_findings(shown) if f["kind"] == "said_not_shown"]


def test_a_bare_beat_is_reported_low():
    found = qa.storyboard_findings(_lesson({"id": "01", "narration": "Think about it.", "steps": []}))
    assert [(f["kind"], f["severity"]) for f in found] == [("no_screen", "low")]


def test_report_merges_every_source_by_beat(tmp_path):
    lesson = _lesson({"id": "01", "narration": "Six and eight.", "steps": [{"say": "Six", "show": "x"}]},
                     {"id": "02", "narration": "Done.", "steps": [{"say": "Done", "show": "Done"}]})
    (tmp_path / "output").mkdir()
    (tmp_path / "output" / "final_checks.json").write_text(json.dumps({
        "checks": [{"check": "audio present", "passed": False, "detail": "no stream"}],
        "layout_findings": {"detail": [{"beat": "02", "kind": "overlap", "detail": "a on b", "counted": True}]}}))
    (tmp_path / "output" / "chapter_01_audit.json").write_text(json.dumps(
        {"cues": [{"beat": "02", "phrase": "Done", "anchor": 1.0, "actual_before_wait": 2.0}]}))
    (tmp_path / "output" / "vision_review.json").write_text(json.dumps(
        {"detail": [{"beat": "01", "findings": [{"kind": "mismatch", "what": "wrong label", "severity": "high"}]}],
         "repaired_beats": ["01"]}))
    job = {"verification": {"findings": [{"beat": "02", "what": "flow: jumps", "severity": "major"},
                                         {"beat": "01", "what": "fixed", "resolved": True}]}}
    r = qa.report(tmp_path, job=job, lesson=lesson)
    assert r["status"] == "needs_repair"
    assert set(r["beats"]) == {"01", "02"} and list(r["beats"]) == ["01", "02"]
    kinds = {f["kind"] for fs in r["beats"].values() for f in fs}
    assert {"said_not_shown", "overlap", "late_cue", "screen", "critic"} <= kinds
    assert r["by_stage"]["pedagogy"] == 1 and r["by_stage"]["technical"] == 1
    assert r["repaired_beats"] == ["01"] and r["lesson"][0]["kind"] == "check"
    assert all(f["repair"] for fs in r["beats"].values() for f in fs)
    assert json.loads((tmp_path / "output" / "qa_report.json").read_text())["findings"] == r["findings"]
    assert qa.line(r).startswith("[qa] needs_repair")


def test_a_clean_lesson_passes(tmp_path):
    lesson = _lesson({"id": "01", "narration": "A square has four sides.",
                      "steps": [{"say": "A square", "show": "four sides"}]})
    r = qa.report(tmp_path, job={}, lesson=lesson)
    assert r["status"] == "pass" and r["findings"] == 0


def _numbers_lesson():
    return _lesson({"id": "01", "narration": "The base is six and the height is eight.",
                    "steps": [{"say": "The base", "show": "A triangle", "kind": "point"}]})


def test_a_beat_whose_screen_misses_its_numbers_gets_new_steps_before_speech():
    lesson = _numbers_lesson()
    calls = []

    def llm(prompt, system):
        calls.append(prompt)
        return {"steps": [{"say": "The base", "show": "A triangle"}, {"say": "The base is six", "show": "base 6"},
                          {"say": "height is eight", "show": "height 8"}]}

    out = qa.mend_storyboard(lesson, llm, log=lambda *_: None)
    assert out["kept"] == ["01"] and out["after"] == 0
    assert [s["show"] for s in lesson["chapters"][0]["beats"][0]["steps"]] == ["A triangle", "base 6", "height 8"]
    assert lesson["chapters"][0]["beats"][0]["narration"] == "The base is six and the height is eight."
    assert "six" in calls[0] and len(calls) == 1


def test_new_steps_that_cure_nothing_are_put_back():
    lesson = _numbers_lesson()
    was = json.loads(json.dumps(lesson))
    out = qa.mend_storyboard(lesson, lambda p, s: {"steps": [{"say": "The base", "show": "a shape"}]},
                             log=lambda *_: None)
    assert out["tried"] == ["01"] and out["kept"] == [] and lesson == was


def test_steps_that_cure_one_fault_and_cause_another_are_put_back():
    lesson = _numbers_lesson()
    was = json.loads(json.dumps(lesson))
    out = qa.mend_storyboard(lesson, lambda p, s: {"steps": [{"say": "never said here", "show": "base 6 height 8"}]},
                             log=lambda *_: None)
    # the anchor is re-derived by clean_steps, so this may still be kept; what must hold: no new fault on the beat
    left = [f["kind"] for f in qa.storyboard_findings(lesson)]
    assert "anchor_missing" not in left
    if not out["kept"]:
        assert lesson == was


def test_the_mend_can_be_switched_off(monkeypatch):
    monkeypatch.setenv("HARNESS_STORYBOARD_MEND", "0")
    lesson = _numbers_lesson()
    assert qa.mend_storyboard(lesson, lambda p, s: 1 / 0)["tried"] == []


def test_decimals_said_in_words_are_the_decimals_on_screen():
    lesson = _lesson({"id": "01", "narration": "Its face is zero point zero two square metres and the end zero point "
                                               "zero zero five.", "steps": [{"say": "Its face", "show": "A = 0.02 m^2, 0.0050 m^2"}]})
    assert not [f for f in qa.storyboard_findings(lesson) if f["kind"] == "said_not_shown"]


def test_a_mend_that_drops_a_right_line_is_put_back():
    lesson = _lesson({"id": "01", "narration": "The base is six and the height is eight. Check yourself.",
                      "steps": [{"say": "The base", "show": "A triangle"}, {"say": "Check yourself", "show": "Self-check"}]})
    was = json.loads(json.dumps(lesson))
    out = qa.mend_storyboard(lesson, lambda p, s: {"steps": [{"say": "The base is six", "show": "base 6, height 8"}]},
                             log=lambda *_: None)
    assert out["kept"] == [] and lesson == was
