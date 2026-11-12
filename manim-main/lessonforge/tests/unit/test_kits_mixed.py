"""Lessons that mix subjects (LESSONFORGE_KITS_MIXED): each beat is checked by the kit of its own figure.

A geometry beat ({angle A}) and a motion beat ({speed at 3}) in one lesson settle with no fault and both values filled;
a wrong typed value in either is refused with that kit's own message; a one-subject lesson behaves exactly as before;
switched off, the one-subject fault is back.
"""
import copy

import pytest

from lessonforge import kits, knobs
from lessonforge.harness import pack, shapes, writer
from lessonforge.harness import workbench as W

OFF = {"LESSONFORGE_KITS_MIXED": "0"}
SPEEDING = {"kind": "motion", "start_speed": 0, "acceleration": 2, "duration": 6, "marks": [3, 6]}
BRAKING = {"kind": "motion", "start_speed": 10, "acceleration": -2, "duration": 4}
TRIANGLE = {"kind": "shape", "points": {"A": [0, 0], "B": [4, 0], "C": [0, 3]}, "polygon": "ABC", "angles": ["A"]}


def _beat(bid, narration, figure=None, quiz=None):
    beat = {"id": bid, "narration": narration, "steps": [{"say": narration.split(".")[0], "show": "x", "kind": "point"}]}
    if figure is not None:
        beat["figure"] = figure
    if quiz:
        beat["quiz"] = quiz
    return beat


def _lesson(*beats):
    return {"title": "Two subjects", "chapters": [{"id": 1, "title": "ONE", "learning_goal": "g", "role": "explain",
                                                  "beats": list(beats)}]}


GEOM = ("01", "In this triangle the angle at A is {angle A} degrees.", TRIANGLE)
MOTION = ("02", "The car starts from rest and speeds up. At 3 s its speed is {speed at 3} m/s.", SPEEDING)


def mixed(geom=GEOM, motion=MOTION):
    return _lesson(_beat(*geom), _beat(*motion))


def narrations(lesson):
    return [b["narration"] for ch in lesson["chapters"] for b in ch["beats"]]


@pytest.fixture()
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("LESSONFORGE_HOME", str(tmp_path))
    return tmp_path


# ---------------------------------------------------------------- ownership

def test_a_beat_belongs_to_the_kit_that_serves_its_figure_kind():
    assert kits.owner_of_beat(_beat(*GEOM)) is kits.get("geometry")
    assert kits.owner_of_beat(_beat(*MOTION)) is kits.get("motion")
    assert kits.owner_of_beat(_beat("03", "No picture.")) is None
    assert kits.owner_of_beat(_beat("03", "A bar picture.", {"kind": "bars"})) is None      # a built-in kind no kit owns
    assert kits.owner_of_beat("not a beat") is None


def test_multi_needs_two_kits_and_the_switch():
    assert kits.multi(mixed()) is True
    assert kits.multi(_lesson(_beat(*GEOM))) is False and kits.multi(_lesson(_beat(*MOTION))) is False
    with knobs.applied(OFF):
        assert kits.multi(mixed()) is False
    with knobs.applied({"LESSONFORGE_KITS": "0"}):
        assert kits.multi(mixed()) is False and kits.mixed_enabled() is False


def test_the_switch_is_a_listed_control_on_by_default():
    control = next(c for c in knobs.CONTROLS if c.id == "LESSONFORGE_KITS_MIXED")
    assert control.default == "1" and control.kind == "toggle"
    assert knobs.validate(OFF) == OFF and knobs.validate({"LESSONFORGE_KITS_MIXED": "1"}) == {}


# ---------------------------------------------------------------- a geometry beat and a motion beat

def test_a_geometry_beat_and_a_motion_beat_settle_with_no_fault_and_both_values_filled(home):
    lesson = mixed()
    assert W.faults_of(lesson) == []
    settled = W._settled(copy.deepcopy(lesson))
    first, second = narrations(settled)
    assert first == "In this triangle the angle at A is 90 degrees."
    assert second == "The car starts from rest and speeds up. At 3 s its speed is 6 m/s."
    assert not shapes.unfilled(settled) and not kits.get("motion").unfilled(settled)
    added = W.add(lesson, "mixed")
    assert added["faults"] == []
    assert narrations(W.load(added["lesson_id"])) == [first, second]


def test_each_kit_alone_reports_nothing_on_the_other_kits_beat():
    lesson = mixed()
    filled, geometry_issues = shapes.settle(lesson)
    assert geometry_issues == [] and "{speed at 3}" in narrations(filled)[1]          # left for motion, no fault
    filled2, motion_issues = kits.get("motion").settle(lesson)
    assert motion_issues == [] and "{angle A}" in narrations(filled2)[0]               # left for geometry, no fault
    assert pack.faults(lesson)[1] == []


def test_the_writers_kit_pass_fills_both_without_asking_the_model():
    def llm(prompt, system):
        raise AssertionError("no model call needed")
    raw = {**mixed(), "generated_by": "model"}
    out = writer.kit_pass(raw, llm, "S", log=lambda *_a, **_k: None)
    assert out["_kit_faults"] == [] and out["_kit_names"] == ["motion"]
    assert narrations(out)[1].endswith("its speed is 6 m/s.")


def test_the_registry_settles_the_served_kit_and_leaves_geometry_to_its_own_pass():
    out = kits.settle_active(mixed())
    assert "6 m/s" in narrations(out)[1] and "{angle A}" in narrations(out)[0]


# ---------------------------------------------------------------- a wrong typed value is refused by its own kit

def test_a_wrong_typed_angle_is_refused_with_the_geometry_message(home):
    lesson = mixed(geom=("01", "In this triangle the angle at A is 40 degrees.", TRIANGLE))
    found = W.faults_of(lesson)
    assert len(found) == 1 and "says 40 degrees, which the picture does not show" in found[0] and "beat 1" in found[0]
    assert W.add(lesson, "bad-angle")["faults"] == found


def test_a_wrong_typed_speed_is_refused_with_the_motion_message(home):
    lesson = mixed(motion=("02", "The car speeds up. At 3 s its speed is 20 m/s.", SPEEDING))
    found = W.faults_of(lesson)
    assert len(found) == 1 and "20 m/s" in found[0] and "the picture does not show" in found[0] and "beat 2" in found[0]


def test_a_claim_the_picture_denies_is_refused_by_the_kit_that_owns_the_beat(home):
    found = W.faults_of(mixed(motion=("02", "The car speeds up.", BRAKING)))
    assert len(found) == 1 and "speeds up" in found[0] and "beat 2" in found[0]
    found = W.faults_of(mixed(geom=("01", "The triangle has no right angle at all, so it is acute.", TRIANGLE)))
    assert all("beat 1" in f for f in found)               # whatever geometry finds is on its own beat


def test_a_gap_of_one_subject_on_a_beat_of_the_other_gets_that_beats_kit_message(home):
    swapped = mixed(geom=("01", "Look at it. In this triangle the speed is {speed at 3} m/s.", TRIANGLE),
                    motion=("02", "The car moves. The angle at A is {angle A} degrees.", SPEEDING))
    found = W.faults_of(swapped)
    assert any("beat 1" in f and "can only hold angle X" in f for f in found)           # shapes' message
    assert any("beat 2" in f and "angle A" in f for f in found)                         # motion's message
    assert len(found) == 2


def test_a_wrong_typed_value_in_the_kit_pass_goes_back_to_the_model_with_both_kits_facts():
    seen = []
    clean = {**mixed(), "generated_by": "model"}

    def llm(prompt, system):
        seen.append(prompt)
        return clean
    bad = {**mixed(motion=("02", "At 3 s its speed is 20 m/s.", SPEEDING)), "generated_by": "model"}
    out = writer.kit_pass(bad, llm, "S", log=lambda *_a, **_k: None)
    assert len(seen) == 1 and "20 m/s" in seen[0] and "starts at 0 m/s" in seen[0]
    assert "What the other subject's figures make" in seen[0] and "angle" in seen[0].lower()
    assert out["_kit_faults"] == [] and narrations(out)[1].endswith("6 m/s.")


# ---------------------------------------------------------------- a gap on a beat no kit owns

def test_in_a_mixed_lesson_a_gap_with_no_figure_asks_which_subject_it_is_from_once(home):
    lesson = _lesson(_beat(*GEOM), _beat(*MOTION), _beat("03", "Back to the road. Its speed is {speed at 3} m/s."))
    found = W.faults_of(lesson)
    assert len(found) == 1
    assert "beat 3" in found[0] and "which subject is this value from" in found[0] and "{speed at 3}" in found[0]
    assert kits.orphan_gaps(lesson) == found
    assert kits.lesson_faults(lesson) == found


def test_with_one_kit_a_gap_with_no_figure_is_reported_by_that_kit_as_before(home):
    only_motion = _lesson(_beat(*MOTION), _beat("03", "Back to the road. Its speed is {speed at 3} m/s."))
    found = W.faults_of(only_motion)
    assert len(found) == 1 and "no motion figure" in found[0] and "which subject" not in found[0]
    only_geometry = _lesson(_beat(*GEOM), _beat("03", "Look again. The angle is {angle A} degrees."))
    found = W.faults_of(only_geometry)
    assert len(found) == 1 and "no shape figure" in found[0] and "which subject" not in found[0]
    assert kits.orphan_gaps(only_motion) == [] and kits.orphan_gaps(only_geometry) == []


# ---------------------------------------------------------------- one-subject lessons are exactly as they were

@pytest.mark.parametrize("lesson", [
    _lesson(_beat(*GEOM), _beat("03", "Look again. The angle is {angle A} degrees.")),
    _lesson(_beat("01", "In this triangle the angle at A is 40 degrees.", TRIANGLE)),
    _lesson(_beat(*MOTION), _beat("02", "At 6 s it is {speed at 6} m/s.", SPEEDING), _beat("03", "Look again. It is {speed at 3} m/s.")),
    _lesson(_beat("02", "The car speeds up. At 3 s its speed is 20 m/s.", SPEEDING)),
    _lesson(_beat("02", "The car speeds up.", BRAKING)),
])
def test_a_one_subject_lesson_gets_the_same_answers_with_the_switch_on_or_off(lesson, home):
    on = (W.faults_of(lesson), shapes.settle(lesson), kits.get("motion").settle(lesson), kits.lesson_faults(lesson),
          kits.settle_active(lesson), pack.faults(lesson))
    with knobs.applied(OFF):
        off = (W.faults_of(lesson), shapes.settle(lesson), kits.get("motion").settle(lesson), kits.lesson_faults(lesson),
               kits.settle_active(lesson), pack.faults(lesson))
    assert on == off


def test_a_geometry_lesson_with_a_stray_gap_is_flagged_by_shapes_exactly_as_before():
    lesson = _lesson(_beat(*GEOM), _beat("03", "Look again. The angle is {angle A} degrees."))
    _, issues = shapes.settle(lesson)
    assert issues == ["beat 2 (chapter 1) narration: gap {angle A} on a beat with no shape figure"]
    assert shapes.fill_text("{angle A}", None) == ("{angle A}", ["gap {angle A} on a beat with no shape figure"], [])
    assert shapes.fill_text("{angle A}", None, quiet=True) == ("{angle A}", [], [])


# ---------------------------------------------------------------- the switch off restores the one-subject fault

def test_the_switch_off_restores_the_one_subject_fault_everywhere(home):
    lesson = mixed()
    one = kits.ONE_SUBJECT.format(names="geometry, motion")
    with knobs.applied(OFF):
        assert kits.mixed(lesson) == one
        assert W.faults_of(lesson) == [one]
        assert W.add(lesson, "off")["faults"] == [one]
        assert kits.lesson_faults(lesson) == [one]
        out = writer.kit_pass({**lesson, "generated_by": "model"}, lambda p, s: lesson, "S", log=lambda *_a, **_k: None)
        assert one in out["_kit_faults"]
    assert kits.mixed(lesson) is None and W.faults_of(lesson) == []


# ---------------------------------------------------------------- the writer's rules

def test_one_kit_named_gets_the_same_addendum_as_before_and_several_get_a_header_each():
    single = kits.rules_for(["motion"])
    assert single.startswith("\n\nSUBJECT KIT motion (this lesson's figures come from it):\n")
    assert kits.rules_for(["motion", "motion"]) == single and kits.rules_for(["geometry"]) == ""
    assert kits.rules_for(["motion", "nonsense"], log=lambda *_a: None) == single
    several = kits.rules_for(["geometry", "motion"])
    assert several != single and kits.get("motion").rules in several
    assert several.count("SUBJECT KIT ") == 2 and "THIS LESSON MIXES SUBJECTS" in several
    assert "SUBJECT KIT geometry (beats whose figure is shape" in several and "SUBJECT KIT motion (beats whose figure is motion" in several
    with knobs.applied(OFF):
        assert kits.rules_for(["geometry", "motion"]) == single                  # switch off: the previous addendum
    with knobs.applied({"LESSONFORGE_KITS": "0"}):
        assert kits.rules_for(["geometry", "motion"]) == ""


def test_the_improver_is_told_both_subjects_rules_for_a_mixed_lesson():
    assert kits.rules_for_lesson(_lesson(_beat(*MOTION))) == kits.rules_for(["motion"])
    both = kits.rules_for_lesson(mixed())
    assert "THIS LESSON MIXES SUBJECTS" in both and kits.get("motion").rules in both
    with knobs.applied(OFF):
        assert kits.rules_for_lesson(mixed()) == kits.rules_for(["motion"])
