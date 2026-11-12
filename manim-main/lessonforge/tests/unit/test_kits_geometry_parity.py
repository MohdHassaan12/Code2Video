"""The geometry kit is an adapter: over every Phase 0 fixture it must answer exactly what ``harness.shapes`` and the
workbench's own rules answer today. If any of these fail, geometry is no longer byte-for-byte what it was."""
import copy
import json

import pytest

import geometry_fixtures as F
from lessonforge import kits
from lessonforge.harness import edit, shapes, writer
from lessonforge.harness import workbench as W

KIT = kits.get("geometry")
NAMES = sorted(F.fixtures())


def test_geometry_is_registered_as_a_legacy_adapter_that_seams_never_serve():
    assert KIT is not None and kits.for_kind("shape") is KIT
    assert KIT.legacy and kits.serving("shape") is None and "shape" not in kits.kinds()
    assert (KIT.name, KIT.figure_kinds, KIT.data_key, KIT.generated_by, KIT.check_key) == (
        "geometry", ("shape",), "shapes", "geometry pack", "geometry_check")
    assert kits.builder_for("shape") is None
    assert kits.active(F.fixtures()["claim_true"]) == []                 # served kits only: geometry is not one


@pytest.mark.parametrize("name", NAMES)
def test_settle_equals_shapes_settle(name):
    lesson = F.fixtures()[name]
    assert KIT.settle(copy.deepcopy(lesson)) == shapes.settle(copy.deepcopy(lesson))


@pytest.mark.parametrize("name", NAMES)
def test_unfilled_and_repair_prompt_equal_shapes(name):
    lesson = F.fixtures()[name]
    filled, issues = shapes.settle(lesson)
    assert KIT.unfilled(filled) == shapes.unfilled(filled) and KIT.unfilled(lesson) == shapes.unfilled(lesson)
    assert KIT.repair_prompt(lesson, issues) == shapes.repair_prompt(lesson, issues)


@pytest.mark.parametrize("name", NAMES)
def test_expected_fault_equals_the_workbenchs_rule_on_every_issue(name):
    lesson = F.fixtures()[name]
    _, issues = shapes.settle(lesson)
    for issue in issues:
        assert KIT.expected_fault(issue, lesson) == W._expected_fault(issue, lesson), issue


def test_expected_fault_agrees_on_the_wrong_option_and_the_answer_option():
    for name, expected in (("deliberate_wrong_option", True), ("wrong_answer_option", False)):
        lesson = F.fixtures()[name]
        issue = next(i for i in shapes.settle(lesson)[1] if "quiz option" in i)
        assert KIT.expected_fault(issue, lesson) is W._expected_fault(issue, lesson) is expected
    assert KIT.expected_fault("beat 1 (chapter 1): anything else", F.fixtures()["claim_true"]) is False


def test_the_rules_are_shape_rules_and_the_gap_pattern_is_shapes():
    assert KIT.rules is shapes.SHAPE_RULES or KIT.rules == shapes.SHAPE_RULES
    assert kits.GAP.pattern == shapes._GAP.pattern


def _matrix():
    plain = {"title": "t", "chapters": [{"title": "c", "beats": [{"id": "01", "narration": "x"}]}]}
    shape_fig = {"kind": "shape", "points": {"A": [0, 0]}}
    out = {
        "plain": plain,
        "declared_shapes_only": {**plain, "shapes": {"a": F.ARROW}},
        "empty_shapes": {**plain, "shapes": {}},
        "shape_figure": {**plain, "chapters": [{"title": "c", "beats": [{"id": "01", "narration": "x", "figure": shape_fig}]}]},
        "use_figure": {**plain, "chapters": [{"title": "c", "beats": [{"id": "01", "narration": "x", "figure": {"kind": "shape", "use": "a"}}]}]},
        "use_without_kind": {**plain, "chapters": [{"title": "c", "beats": [{"id": "01", "narration": "x", "figure": {"use": "a"}}]}]},
        "other_figure": {**plain, "chapters": [{"title": "c", "beats": [{"id": "01", "narration": "x", "figure": {"kind": "graph"}}]}]},
        "figure_null": {**plain, "chapters": [{"title": "c", "beats": [{"id": "01", "narration": "x", "figure": None}]}]},
    }
    out.update({f"fixture_{n}": F.fixtures()[n] for n in NAMES})
    return out


@pytest.mark.parametrize("name", sorted(_matrix()))
def test_the_is_this_geometry_predicates_agree_with_the_ones_they_replace(name):
    lesson = _matrix()[name]
    beats = [b for ch in lesson.get("chapters") or [] for b in ch.get("beats") or []]
    # workbench.faults_of (:218), which also decides pack.faults vs structure_issues
    faults_form = bool(lesson.get("shapes") or any((b.get("figure") or {}).get("kind") == "shape" for b in beats))
    # writer.geometry_pass's `drawn` (:2002) and scripted._finish (:1040)
    figures_form = any(isinstance(b.get("figure"), dict) and b["figure"].get("kind") == "shape" for b in beats)
    # workbench.apply_edits (:310)
    edit_form = bool(lesson.get("shapes") or any((b.get("figure") or {}).get("use") for b in beats))
    assert KIT.uses(lesson) == faults_form
    assert KIT.uses_figures(lesson) == figures_form
    assert KIT.uses(lesson, after_edit=True) == edit_form


def test_the_set_shape_op_declares_a_shape_exactly_as_the_workbench_does():
    lesson = {"title": "t", "chapters": [{"id": 1, "title": "c", "beats": [{"id": "01", "narration": "x"}]}]}
    via_kit = copy.deepcopy(lesson)
    KIT.edit_ops["set_shape"](via_kit, {"op": "set_shape", "name": "box", "shape": F.BOX})
    via_bench = W.apply_edits(lesson, [{"op": "set_shape", "name": "box", "shape": F.BOX}])
    assert via_kit["shapes"] == {"box": F.BOX} and via_bench["shapes"] == via_kit["shapes"]
    for bad in ({"name": "x"}, {"shape": F.BOX}, {"name": "x", "shape": "no"}):
        with pytest.raises(kits.KitError, match="needs a name and a shape"):
            KIT.edit_ops["set_shape"](copy.deepcopy(lesson), bad)


def test_merge_declared_equals_the_edit_paths_merge():
    answer = {"beats": [], "shapes": {"box": F.BOX, "arrow": {"points": {}}, "bad": "no"}}
    via_kit = {"title": "t", "shapes": {"arrow": F.ARROW}}
    KIT.merge_declared(via_kit, answer)
    via_edit = {"title": "t", "shapes": {"arrow": F.ARROW}, "chapters": [{"title": "c", "beats": [{"id": "01", "narration": "Look."}]}]}
    edit._redesign(via_edit, {"01": "x"}, {"topic": "t", "language": "en-US"}, lambda p, s: answer, log=lambda *_: None)
    assert via_kit["shapes"] == via_edit["shapes"] == {"arrow": F.ARROW, "box": F.BOX}
    empty = {"title": "t"}
    KIT.merge_declared(empty, {"beats": []})
    assert "shapes" not in empty


def test_the_kit_adds_nothing_to_the_writers_numbers_or_a_fixtures_figures():
    for name in NAMES:
        for beat in [b for ch in F.fixtures()[name].get("chapters") or [] for b in ch.get("beats") or []]:
            fig = beat.get("figure")
            if isinstance(fig, dict):
                assert KIT.numbers(fig) == writer.figure_numbers(fig) == set()


def test_figure_issues_and_describe_read_an_expanded_figure():
    filled, _ = shapes.settle(F.fixtures()["gaps_fill_and_add_up"])
    fig = filled["chapters"][0]["beats"][0]["figure"]
    assert KIT.figure_issues(fig) == [] and "concave" in KIT.describe(fig)
    assert KIT.figure_issues({"kind": "shape", "use": "arrow"}) == [] and KIT.describe({"kind": "shape", "use": "arrow"}) == "a shape"
    assert KIT.normalise_figure(fig) == fig and KIT.normalise_figure("no") is None


def test_the_kits_own_cases_are_what_shapes_says_they_are():
    cases = KIT.cases()
    assert len(cases.good) >= 1 and len(cases.refused) >= 3
    for good in cases.good:
        assert shapes.settle(good)[1] == []
    for bad, fragment in cases.refused:
        assert any(fragment in i for i in shapes.settle(bad)[1]), fragment
    for expr, figure, expected in cases.gaps:
        assert shapes.gap_value(expr, figure)[0] == expected, expr
    json.dumps([cases.good, cases.refused, cases.gaps])           # plain data, so it can be pinned and shared
