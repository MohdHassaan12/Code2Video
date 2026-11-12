"""Geometry as it behaves today, pinned before the subject-kit registry exists.

Everything here is written against unchanged code. The kit work adds a registry beside the geometry paths and must
leave these answers exactly as they are: ``shapes.settle`` on a set of fixture lessons, the writer's geometry repair
loop, the edit path's shape merge, the workbench's message for an unknown op and its expected-fault rule.
"""
import hashlib
import json

import pytest

import geometry_fixtures as F
from lessonforge.harness import edit, shapes, writer
from lessonforge.harness import workbench as W

#: sha256 (first 24 hex) of ``json.dumps(shapes.settle(lesson), sort_keys=True)`` for each fixture lesson.
GOLDEN = {
    "gaps_fill_and_add_up": "cb9dd6506792fdaf35bfffb6",
    "typed_angle": "d42290bee9d19054e3c69fc2",
    "typed_angle_in_words": "89780acc07d2b69b86f96787",
    "claim_denied": "c9d170189d8293a64a0909a1",
    "claim_true": "7f4e32108bb09d51bc8e088d",
    "claim_negated": "3f989744e23c1c238591ff9e",
    "shape_not_what_is_needed": "cbf714bead3eb018bed3025b",
    "moving_corner_on_segment": "63e5757754c8e80addace396",
    "moving_corner_misses": "494034f522aa4fc57824ca9d",
    "options_equal_after_filling": "c705a12d48c6f321d8973982",
    "deliberate_wrong_option": "cff2e1ec466802f0b8004637",
    "wrong_answer_option": "48159d2d8e329de19cfe1070",
    "gap_on_beat_without_shape": "0a7863822d2d3d84eb0b4543",
    "gap_cannot_be_filled": "f89f069c848ba995b170148e",
    "unknown_shape_name": "734a5e543af91163263d943e",
    "use_without_kind": "1cdabf396d4314ff3ac67ee0",
    "two_panels": "a8e3bc2eba43cb9f8ac80144",
    "no_shape_at_all": "a8023c531c57ddcf01a5dc2b",
    "hand_made_unit1": "d15dd8f7171a9b72097b7c9f",
    "hand_made_unit2": "e8d20d4e3a7d709bd2788fe8",
    "hand_made_unit4": "71cb7b2b8b2ae6916595a65b",
    "hand_made_unit6": "ec1f80aa5685b1b9b5605f5c",
    "hand_made_unit7": "c782f5e4c52776a700ec6e15",
    "hand_made_unit8": "aff596d4c9380393e9424042",
}

#: How many faults each fixture has (the hand-made units are right: none).
FAULT_COUNTS = {
    "gaps_fill_and_add_up": 0, "typed_angle": 1, "typed_angle_in_words": 1, "claim_denied": 1, "claim_true": 0,
    "claim_negated": 0, "shape_not_what_is_needed": 1, "moving_corner_on_segment": 0, "moving_corner_misses": 1,
    "options_equal_after_filling": 1, "deliberate_wrong_option": 1, "wrong_answer_option": 1,
    "gap_on_beat_without_shape": 2, "gap_cannot_be_filled": 2, "unknown_shape_name": 1, "use_without_kind": 1,
    "two_panels": 0, "no_shape_at_all": 0, **{f"hand_made_unit{u}": 0 for u in F.HAND_MADE_UNITS},
}


def _digest(name: str) -> str:
    out = shapes.settle(F.fixtures()[name])
    return hashlib.sha256(json.dumps(out, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()[:24]


def test_every_fixture_has_a_golden():
    assert set(F.fixtures()) == set(GOLDEN) == set(FAULT_COUNTS)


@pytest.mark.parametrize("name", sorted(GOLDEN))
def test_settle_gives_the_same_lesson_and_faults_as_before(name):
    assert _digest(name) == GOLDEN[name]
    assert len(shapes.settle(F.fixtures()[name])[1]) == FAULT_COUNTS[name]


def test_settle_never_changes_the_lesson_it_is_given():
    for name, lesson in F.fixtures().items():
        before = json.dumps(lesson, sort_keys=True)
        shapes.settle(lesson)
        assert json.dumps(lesson, sort_keys=True) == before, name


def test_settle_twice_is_the_same_as_settle_once():
    for name in ("gaps_fill_and_add_up", "claim_true", "two_panels", "moving_corner_on_segment"):
        once, issues = shapes.settle(F.fixtures()[name])
        twice, issues2 = shapes.settle(once)
        assert issues == issues2 == [], name
        assert not shapes.unfilled(twice)


def test_unfilled_sees_a_gap_in_words_and_not_in_a_figure():
    assert shapes.unfilled(shapes.settle(F.fixtures()["gap_cannot_be_filled"])[0])
    assert not shapes.unfilled(shapes.settle(F.fixtures()["gaps_fill_and_add_up"])[0])
    # points serialised as JSON look like a gap but are not words
    assert not shapes.unfilled({"chapters": [{"beats": [{"figure": {"kind": "shape", "points": {"A": [1, 1]}}}]}]})
    assert shapes.unfilled({"chapters": [{"beats": [{"figure": {"caption": "angle {angle D}"}}]}]})


def test_repair_prompt_lists_the_faults_the_shapes_facts_and_the_whole_lesson():
    raw = F.fixtures()["claim_denied"]
    _, issues = shapes.settle(raw)
    text = shapes.repair_prompt(raw, issues)
    assert text.startswith("Code checked your lesson against its own pictures and found these faults:\n- ")
    assert issues[0] in text and "What your shapes' points make, worked out by code:" in text
    assert "Return the WHOLE lesson again as JSON" in text
    assert text.endswith(json.dumps(raw, ensure_ascii=False))


def test_gap_pattern_is_the_one_in_shapes():
    assert shapes._GAP.pattern == r"(?<![A-Za-z}^_\\])\{([^{}]{1,80})\}"


# ---------------------------------------------------------------- writer.geometry_pass with a stub model

def _quiet(*_a, **_k):
    return None


def test_geometry_pass_leaves_a_lesson_with_no_shape_figure_alone():
    raw = F.fixtures()["no_shape_at_all"]

    def llm(prompt, system):
        raise AssertionError("no model call for a lesson that draws no shape")

    assert writer.geometry_pass(raw, llm, "SYSTEM", log=_quiet) is raw


def test_geometry_pass_fills_a_clean_lesson_without_asking_the_model():
    calls = []
    out = writer.geometry_pass(F.fixtures()["gaps_fill_and_add_up"], lambda p, s: calls.append(1), "SYSTEM", log=_quiet)
    assert calls == [] and out["_geometry_faults"] == []
    assert "{" not in out["chapters"][0]["beats"][0]["narration"]


def test_geometry_pass_asks_once_to_repair_and_keeps_the_better_draft():
    bad, good = F.fixtures()["typed_angle"], F.fixtures()["gaps_fill_and_add_up"]
    seen = []

    def llm(prompt, system):
        seen.append((prompt, system))
        return good

    out = writer.geometry_pass(bad, llm, "THE SYSTEM", log=_quiet)
    assert len(seen) == 1 and seen[0][1] == "THE SYSTEM"
    assert seen[0][0].startswith("Code checked your lesson against its own pictures")
    assert out["_geometry_faults"] == []


def test_geometry_pass_keeps_the_old_draft_when_the_repair_is_worse_and_stops_at_the_limit():
    bad, worse = F.fixtures()["typed_angle"], F.fixtures()["gap_on_beat_without_shape"]
    calls = []

    def llm(prompt, system):
        calls.append(1)
        return worse

    out = writer.geometry_pass(bad, llm, "S", log=_quiet)
    assert len(calls) == writer.GEOMETRY_REPAIRS == 2
    assert len(out["_geometry_faults"]) == 1 and "230 degrees" in out["_geometry_faults"][0]


def test_geometry_pass_survives_a_model_that_fails():
    def llm(prompt, system):
        raise RuntimeError("boom")

    out = writer.geometry_pass(F.fixtures()["typed_angle"], llm, "S", log=_quiet)
    assert len(out["_geometry_faults"]) == 1


# ---------------------------------------------------------------- edit.py: a director's new shapes are merged

def _plain_lesson():
    return {"title": "t", "chapters": [{"title": "c", "beats": [{"id": "01", "narration": "Look at the shape."}]}]}


def test_a_redesign_adds_the_shapes_the_director_declared_and_keeps_existing_ones():
    lesson = _plain_lesson()
    lesson["shapes"] = {"arrow": F.ARROW}
    answer = {"beats": [{"id": "01", "visual": "a dent", "figure": {"kind": "shape", "use": "box"},
                         "steps": [{"say": "Look", "show": "x"}]}],
              "shapes": {"box": F.BOX, "arrow": {"points": {}}, "bad": "not a dict"}}
    out = edit._redesign(lesson, {"01": "show a convex shape"}, {"topic": "t", "language": "en-US"}, lambda p, s: answer,
                         log=_quiet)
    assert set(out) == {"01"}
    assert lesson["shapes"]["box"] == F.BOX              # new name merged into the lesson
    assert lesson["shapes"]["arrow"] == F.ARROW          # a name the lesson has is never replaced
    assert "bad" not in lesson["shapes"]


def test_a_redesign_without_a_model_changes_nothing():
    lesson = _plain_lesson()
    assert edit._redesign(lesson, {"01": "x"}, {}, None) == {} and "shapes" not in lesson


# ---------------------------------------------------------------- the workbench's rules

def test_unknown_op_message_lists_the_ops():
    with pytest.raises(W.WorkbenchError) as err:
        W.apply_edits(F.fixtures()["claim_true"], [{"op": "rewrite_everything"}])
    assert str(err.value) == ("edit 1: unknown op 'rewrite_everything' "
                              "(set_beat, insert_beat, delete_beat, set_shape)")


def test_set_shape_needs_a_name_and_a_shape():
    with pytest.raises(W.WorkbenchError, match="set_shape needs a name and a shape"):
        W.apply_edits(F.fixtures()["claim_true"], [{"op": "set_shape", "name": "x"}])


def _quiz_lesson(answer_index):
    quiz = {"question": "What is angle D?", "options": ["262°", "100°"], "answer_index": answer_index,
            "why": ["a", "b"]}
    lesson = F.lesson([F.beat("What is angle D?", {"kind": "shape", "use": "arrow"}, quiz=quiz)])
    return lesson


def test_a_wrong_quiz_option_is_an_expected_fault_and_the_answer_option_is_not():
    issue = "beat 1 (chapter 1) quiz option 2: says 100 degrees, which the picture does not show (write a gap such as {angle D} instead of a number)"
    assert W._expected_fault(issue, _quiz_lesson(0)) is True          # option 2 is wrong: the distractor's point
    assert W._expected_fault(issue, _quiz_lesson(1)) is False         # option 2 IS the answer: a real fault
    assert W._expected_fault(issue.replace("option 2", "option 1"), _quiz_lesson(0)) is False


def test_other_faults_and_other_beats_are_not_expected():
    lesson = _quiz_lesson(0)
    assert not W._expected_fault("beat 1 (chapter 1): the words say something", lesson)
    assert not W._expected_fault("beat 9 (chapter 1) quiz option 2: says 100 degrees, which the picture does not show", lesson)
    assert not W._expected_fault("beat 1 (chapter 1) narration: says 100 degrees, which the picture does not show", lesson)
