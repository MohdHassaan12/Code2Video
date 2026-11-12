"""The workbench keeps every edit checked by code, and the improver never spends past its cap."""
import pytest

from lessonforge.harness import improver, pack, shapes
from lessonforge.harness import workbench as W

ARROW = {"points": {"A": [0, 0], "B": [4.4, 1.6], "C": [0, 3.2], "D": [1.4, 1.6]}, "polygon": "ABCD", "is": ["concave"]}


def _lesson():
    beats = [
        {"narration": "Here is a shape with a dent. The dent is at D. It points inward.",
         "figure": {"kind": "shape", "use": "arrow"},
         "steps": [{"say": "Here is a shape with a dent", "show": "A dented shape", "kind": "point"}]},
        {"narration": "The angle at D is {angle D} degrees. That is more than 180 degrees.",
         "figure": {"kind": "shape", "use": "arrow", "angles": ["D"]},
         "steps": [{"say": "The angle at D", "show": "∠D = {angle D}°", "kind": "key"},
                   {"say": "That is more than", "show": "Reflex", "kind": "point"}]},
    ]
    raw = {"title": "Dents", "shapes": {"arrow": ARROW},
           "chapters": [{"title": "ONE", "learning_goal": "g", "role": "explain", "beats": beats}]}
    filled, issues = shapes.settle(raw)
    assert not issues, issues
    return pack.finish(filled, raw)


@pytest.fixture()
def bench(tmp_path, monkeypatch):
    monkeypatch.setenv("LESSONFORGE_HOME", str(tmp_path))
    return W.add(_lesson(), "dents")["lesson_id"]


def test_a_new_lesson_is_checked_and_its_craft_measured(bench):
    found = W.check(bench)
    assert found["faults"] == []
    assert found["craft"]["beats"] == 2 and found["craft"]["steps"] == 3
    assert found["craft"]["beats_with_held_sentences"] == ["01"]      # two sentences in a row with no new step


def test_an_edit_with_a_gap_is_filled_by_code(bench):
    beat = W.load(bench)["chapters"][0]["beats"][0]
    done = W.edit(bench, [{"op": "insert_beat", "after": beat["id"], "beat": {
        "narration": "Measure it. The angle at D is {angle D} degrees.",
        "steps": [{"say": "The angle at D", "show": "∠D = {angle D}°", "kind": "key"}],
        "figure": {"kind": "shape", "use": "arrow", "angles": ["D"]}}}])
    assert done["kept"] and not done["faults"]
    new = W.load(bench)["chapters"][0]["beats"][1]
    assert "{" not in new["narration"] and "degrees" in new["narration"]
    assert new["figure"]["points"] == ARROW["points"]


def test_an_edit_that_adds_a_wrong_value_is_not_kept(bench):
    second = W.load(bench)["chapters"][0]["beats"][1]["id"]
    done = W.edit(bench, [{"op": "set_beat", "beat": second, "fields": {
        "narration": "The angle at D is 200 degrees. That is more than 180 degrees."}}])
    assert not done["kept"] and any("200 degrees" in f for f in done["faults"])
    assert W.check(bench)["versions"] == 1


def test_unknown_ops_and_beats_are_refused_in_words(bench):
    with pytest.raises(W.WorkbenchError, match="unknown op"):
        W.edit(bench, [{"op": "rewrite_everything"}])
    with pytest.raises(W.WorkbenchError, match="no beat"):
        W.edit(bench, [{"op": "delete_beat", "beat": "99"}])


def test_revert_brings_back_an_old_version(bench):
    first = W.load(bench)
    W.edit(bench, [{"op": "set_beat", "beat": first["chapters"][0]["beats"][0]["id"],
                    "fields": {"narration": "Here is a shape with a dent. Look at D."}}])
    W.revert(bench, 1)
    assert W.load(bench)["chapters"] == first["chapters"] and W.check(bench)["versions"] == 3


def test_the_improver_stops_at_its_cap(bench):
    calls = []

    def ask(tier, system, text, image):
        calls.append(tier)
        return {"edits": [], "why": "fine"}, 0.08, {"in": 1, "out": 1, "cached": 0}

    out = improver.improve(bench, cap_usd=0.005, rounds=3, look=False, ask=ask, log=lambda *a: None)
    assert calls == [] and out["spent_usd"] == 0      # even the first call's guess would pass the cap

    out = improver.improve(bench, cap_usd=0.10, rounds=3, look=False, ask=ask, log=lambda *a: None)
    assert len(calls) == 1 and out["spent_usd"] == 0.08


def test_the_improver_keeps_its_best_version(bench):
    first_id = W.load(bench)["chapters"][0]["beats"][0]["id"]

    def ask(tier, system, text, image):
        assert "FAULTS FOUND BY CODE" in text and "SHAPE FIGURES" in system
        return ({"edits": [{"op": "set_beat", "beat": first_id, "fields": {"steps": [
            {"say": "Here is a shape with a dent", "show": "A dented shape", "kind": "point"},
            {"say": "The dent is at D", "show": "Dent at D", "kind": "key"}]}}], "why": "a step per sentence"},
            0.002, {"in": 1, "out": 1, "cached": 0})

    out = improver.improve(bench, cap_usd=0.10, rounds=2, look=False, ask=ask, log=lambda *a: None)
    assert out["best_score"] < 3 and out["spent_usd"] <= 0.1
    assert W.check(bench)["craft"]["beats_with_held_sentences"] == []


def test_a_finished_lesson_rechecked_keeps_its_panel_names():
    """A gap that names its panel ({arrow: angle D}) still finds it when a finished lesson is checked again."""
    box = {"points": {"A": [0, 0], "B": [4, 0.3], "C": [4.6, 3.2], "D": [0.4, 2.8]}, "polygon": "ABCD", "is": ["convex"]}
    raw = {"title": "t", "shapes": {"arrow": ARROW, "box": box}, "chapters": [{"title": "ONE", "learning_goal": "g",
           "role": "explain", "beats": [{"narration": "The dent's angle is {arrow: angle D} degrees.",
                                         "figure": {"kind": "shape", "panels": [{"use": "box"}, {"use": "arrow"}]},
                                         "steps": [{"say": "The dent's angle", "show": "∠D = {arrow: angle D}°"}]}]}]}
    filled, issues = shapes.settle(raw)
    assert not issues
    again = W.apply_edits(pack.finish(filled, raw), [{"op": "set_beat", "beat": "01", "fields": {
        "narration": "Look again. The dent's angle is {arrow: angle D} degrees."}}])
    assert not W.faults_of(again) and "{" not in again["chapters"][0]["beats"][0]["narration"]


def test_sentence_times_are_global_and_faults_read_plainly():
    from lessonforge.harness import frame_judge
    timeline = [{"id": "01", "start": 0.0, "sentences": [{"text": "One.", "start": 1.0, "duration": 2.0}]},
                {"id": "02", "start": 10.0, "sentences": [{"text": "Two.", "start": 0.5, "duration": 1.0}]}]
    pts = frame_judge.sentence_times(timeline)
    assert [p["t"] for p in pts] == [2.6, 11.3]
    faults = frame_judge.as_faults({"problems": [{"beat": "02", "t": 11.3, "text": "Two.", "verdict": "mismatch",
                                                  "what": "shows a square"}], "held": [{"beat": "01", "t": 2.6, "text": "One."}]})
    assert "mismatch" in faults[0] and "does not change" in faults[1]


def test_an_empty_set_beat_is_refused(bench):
    first = W.load(bench)["chapters"][0]["beats"][0]["id"]
    with pytest.raises(W.WorkbenchError, match="changed nothing"):
        W.edit(bench, [{"op": "set_beat", "beat": first}])
