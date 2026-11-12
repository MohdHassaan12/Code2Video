"""Two workbench bugs the 2026-11-07 video run found: a lesson added unsettled, and a shape changed under its beats."""
import copy

import pytest

import geometry_fixtures as F
from lessonforge.harness import pack, shapes
from lessonforge.harness import workbench as W
from lessonforge.kits import geometry

ARROW2 = {"points": {"A": [0, 0], "B": [5, 1], "C": [0, 4], "D": [1, 2]}, "polygon": "ABCD", "is": ["concave"]}


def _contract_lesson():
    """A lesson in the contract (ids, steps, continuity) the way the pack writer leaves it, then put back into the
    form a model writes it: gaps in the words and ``{"use": ...}`` figures."""
    beats = [
        {"narration": "Here is a shape with a dent. The dent is at D. It points inward.",
         "figure": {"kind": "shape", "use": "arrow"},
         "steps": [{"say": "Here is a shape with a dent", "show": "A dented shape", "kind": "point"}]},
        {"narration": "The angle at D is {angle D} degrees. That is more than 180 degrees.",
         "figure": {"kind": "shape", "use": "arrow", "angles": ["D"]},
         "steps": [{"say": "The angle at D", "show": "∠D = {angle D}°", "kind": "key"},
                   {"say": "That is more than", "show": "Reflex", "kind": "point"}]},
    ]
    raw = {"title": "Dents", "shapes": {"arrow": copy.deepcopy(F.ARROW)},
           "chapters": [{"title": "ONE", "learning_goal": "g", "role": "explain", "beats": beats}]}
    filled, issues = shapes.settle(raw)
    assert not issues, issues
    lesson = pack.finish(filled, raw)
    lesson["shapes"] = copy.deepcopy(raw["shapes"])                      # as declared: no frame yet
    second = lesson["chapters"][0]["beats"][1]
    second["narration"] = beats[1]["narration"]
    second["steps"][0]["show"] = beats[1]["steps"][0]["show"]
    for k, beat in enumerate(lesson["chapters"][0]["beats"]):
        beat["figure"] = copy.deepcopy(beats[k]["figure"])
    return lesson


@pytest.fixture()
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("LESSONFORGE_HOME", str(tmp_path))
    return tmp_path


# ---------------------------------------------------------------- (a) add() settles a shape lesson first

def test_a_lesson_added_with_gaps_is_saved_filled_and_expanded(home):
    raw = _contract_lesson()
    assert "{angle D}" in raw["chapters"][0]["beats"][1]["narration"]
    added = W.add(raw, "dents")
    saved = W.load(added["lesson_id"], 1)
    beats = saved["chapters"][0]["beats"]
    assert "{" not in beats[1]["narration"] and "{" not in beats[1]["steps"][0]["show"]
    assert "262" in beats[1]["narration"] and beats[1]["steps"][0]["show"] == "∠D = 262°"
    assert beats[0]["figure"]["points"] == F.ARROW["points"] and "use" not in beats[0]["figure"]
    assert beats[1]["figure"]["angles"] == ["D"] and beats[1]["figure"]["frame"]
    assert added["faults"] == [] and W.check(added["lesson_id"])["faults"] == []
    assert W.history(added["lesson_id"])[0]["what"] == "added"


def test_what_check_sees_is_what_is_filmed_for_a_lesson_added_unsettled(home):
    added = W.add(_contract_lesson(), "dents")
    lesson = W.load(added["lesson_id"])
    assert not shapes.unfilled(lesson)
    assert W.craft(lesson)["beats"] == 2          # craft reads the filled steps and figures, not the gaps


def test_adding_a_lesson_that_is_already_settled_changes_nothing(home):
    first = W.add(_contract_lesson(), "dents")
    settled = W.load(first["lesson_id"])
    second = W.add(settled, "dents-again")
    assert W.load(second["lesson_id"]) == settled


def test_a_lesson_with_no_shapes_is_saved_as_given(home):
    plain = {"title": "Plain", "chapters": [{"id": 1, "title": "c", "beats": [
        {"id": "01", "narration": "Here is {a thing} in braces.", "steps": [{"say": "Here", "show": "x"}]}]}]}
    added = W.add(plain, "plain")
    assert "{a thing}" in W.load(added["lesson_id"])["chapters"][0]["beats"][0]["narration"]


def test_a_gap_that_cannot_be_filled_is_a_fault_not_a_crash(home):
    raw = _contract_lesson()
    raw["chapters"][0]["beats"][1]["narration"] = "The weight at D is {mass of D}. More than 180 degrees."
    added = W.add(raw, "dents")
    assert any("mass of D" in f for f in added["faults"])


# ---------------------------------------------------------------- (b) set_shape re-expands the beats that use it

def _bench(home):
    return W.add(_contract_lesson(), "dents")["lesson_id"]


def test_set_shape_points_every_beat_that_shows_it_at_the_new_shape(home):
    bench = _bench(home)
    before = W.load(bench)
    assert before["chapters"][0]["beats"][1]["figure"]["points"] == F.ARROW["points"]
    done = W.edit(bench, [{"op": "set_shape", "name": "arrow", "shape": ARROW2}], keep_if_worse=True)
    assert done["kept"]
    for beat in W.load(bench)["chapters"][0]["beats"]:
        assert beat["figure"]["points"] == ARROW2["points"], beat["id"]
        assert beat["figure"]["frame"] == [0, 0, 5, 4]
    assert W.load(bench)["shapes"]["arrow"]["points"] == ARROW2["points"]
    assert W.load(bench)["chapters"][0]["beats"][1]["figure"]["angles"] == ["D"]       # what the beat said stays


def test_the_words_can_be_re_gapped_in_the_same_edit_and_the_lesson_comes_out_clean(home):
    bench = _bench(home)
    second = W.load(bench)["chapters"][0]["beats"][1]["id"]
    done = W.edit(bench, [
        {"op": "set_shape", "name": "arrow", "shape": ARROW2},
        {"op": "set_beat", "beat": second, "fields": {
            "narration": "The angle at D is {angle D} degrees. That is more than 180 degrees.",
            "steps": [{"say": "The angle at D", "show": "∠D = {angle D}°", "kind": "key"},
                      {"say": "That is more than", "show": "Reflex", "kind": "point"}]}}])
    assert done["kept"] and done["faults"] == []
    beat = W.load(bench)["chapters"][0]["beats"][1]
    angle_d = round(shapes.G.Model({"points": ARROW2["points"], "polygon": "ABCD"}).interior()["D"])
    assert f"{angle_d} degrees" in beat["narration"] and angle_d != 262
    assert beat["figure"]["points"] == ARROW2["points"]


def test_an_edit_that_leaves_old_words_beside_new_points_is_not_kept(home):
    bench = _bench(home)
    done = W.edit(bench, [{"op": "set_shape", "name": "arrow", "shape": ARROW2}])
    assert not done["kept"] and any("262 degrees" in f for f in done["faults"])
    assert W.load(bench)["chapters"][0]["beats"][0]["figure"]["points"] == F.ARROW["points"]


def test_a_beat_that_overrides_a_point_keeps_its_override(home):
    lesson = _contract_lesson()
    lesson["chapters"][0]["beats"][0]["figure"] = {"kind": "shape", "use": "arrow", "points": {"D": [2, 1.5]}}
    bench = W.add(lesson, "dents")["lesson_id"]
    assert W.load(bench)["chapters"][0]["beats"][0]["figure"]["points"]["D"] == [2, 1.5]
    W.edit(bench, [{"op": "set_shape", "name": "arrow", "shape": ARROW2}], keep_if_worse=True)
    points = W.load(bench)["chapters"][0]["beats"][0]["figure"]["points"]
    assert points["D"] == [2, 1.5] and points["B"] == ARROW2["points"]["B"] and points["C"] == ARROW2["points"]["C"]


def test_panels_of_two_shapes_follow_only_the_shape_that_changed(home):
    lesson = _contract_lesson()
    lesson["shapes"]["box"] = copy.deepcopy(F.BOX)
    lesson["chapters"][0]["beats"][0]["figure"] = {"kind": "shape", "panels": [
        {"use": "box", "caption": "convex"}, {"use": "arrow", "caption": "concave"}]}
    bench = W.add(lesson, "dents")["lesson_id"]
    W.edit(bench, [{"op": "set_shape", "name": "arrow", "shape": ARROW2}], keep_if_worse=True)
    panels = W.load(bench)["chapters"][0]["beats"][0]["figure"]["panels"]
    assert panels[0]["points"] == F.BOX["points"] and panels[1]["points"] == ARROW2["points"]
    assert panels[1]["caption"] == "concave"


def test_declaring_a_new_name_touches_no_beat_and_a_stale_frame_is_not_carried_over(home):
    bench = _bench(home)
    W.edit(bench, [{"op": "set_shape", "name": "box", "shape": F.BOX}], keep_if_worse=True)
    assert W.load(bench)["chapters"][0]["beats"][1]["figure"]["points"] == F.ARROW["points"]
    stale = copy.deepcopy(W.load(bench)["shapes"]["arrow"])
    assert stale["frame"]
    W.edit(bench, [{"op": "set_shape", "name": "arrow", "shape": {**ARROW2, "frame": stale["frame"]}}], keep_if_worse=True)
    assert W.load(bench)["shapes"]["arrow"]["frame"] == [0, 0, 5, 4]


def test_the_helpers_work_on_a_plain_lesson_without_the_workbench():
    lesson, _ = shapes.settle({"title": "t", "shapes": {"arrow": copy.deepcopy(F.ARROW)}, "chapters": [{"title": "c", "beats": [
        {"narration": "x", "steps": [], "figure": {"kind": "shape", "use": "arrow", "angles": ["D"]}},
        {"narration": "y", "steps": [], "figure": {"kind": "graph"}}]}]})
    assert geometry.reexpand_users(lesson, "arrow", lesson["shapes"]["arrow"]) == 1
    fig = lesson["chapters"][0]["beats"][0]["figure"]
    assert fig == {"kind": "shape", "angles": ["D"], "use": "arrow"}
    assert geometry.reexpand_users(lesson, "arrow", lesson["shapes"]["arrow"]) == 0       # already a reference
    assert geometry.reexpand_users(lesson, "arrow", None) == 0
