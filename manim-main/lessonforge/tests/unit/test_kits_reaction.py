"""Kit routing metadata (subjects, classes, keywords, registry.describe) and the chemistry reaction kit."""
import json

from lessonforge import kits
from lessonforge.kits.base import KitBase


# ---------------------------------------------------------------- routing metadata

def test_describe_is_plain_json_with_the_metadata_of_every_kit():
    rows = {r["name"]: r for r in kits.describe()}
    json.dumps(list(rows.values()))                                  # plain data
    geometry, motion = rows["geometry"], rows["motion"]
    assert geometry["subjects"] == ["maths"] and geometry["classes"] == list(range(1, 13)) and geometry["legacy"] is True
    assert geometry["served"] is False and geometry["figure_kinds"] == ["shape"]
    for word in ("triangle", "angle", "quadrilateral", "polygon", "parallel", "diagonal", "midpoint", "proof"):
        assert word in geometry["keywords"], word
    assert motion["subjects"] == ["physics"] and motion["classes"] == [7, 8, 9] and motion["served"] is True
    for word in ("speed", "velocity", "acceleration", "distance", "displacement", "uniform", "graph"):
        assert word in motion["keywords"], word


def test_a_kit_that_sets_no_metadata_still_works():
    assert KitBase.subjects == () and KitBase.classes == () and KitBase.keywords == ()

    class Bare:
        name, figure_kinds, legacy = "bare", ("bare",), False
    from lessonforge.kits import registry
    registry._KITS["bare"] = Bare()
    try:
        row = next(r for r in kits.describe() if r["name"] == "bare")
        assert row["subjects"] == row["classes"] == row["keywords"] == []
    finally:
        registry._KITS.pop("bare")


# ---------------------------------------------------------------- the chemistry kit

import pytest  # noqa: E402

from lessonforge import knobs  # noqa: E402
from lessonforge.kits.reaction import REACTION_RULES, ReactionKit  # noqa: E402
from lessonforge.longform import reaction_math  # noqa: E402

KIT = kits.get("chemistry")
BAL = {"kind": "chem_reaction", "equation": "2H2 + O2 -> 2H2O"}
UNBAL = {"kind": "chem_reaction", "equation": "H2 + O2 -> H2O"}
UNKNOWN = {"kind": "chem_reaction", "equation": "? N2 + ? H2 -> ? NH3"}


def lesson(*beats):
    return {"title": "t", "chapters": [{"title": "ONE", "learning_goal": "g", "role": "explain", "beats": list(beats)}]}


def beat(narration, figure=None, quiz=None):
    out = {"narration": narration, "steps": [{"say": narration[:20], "show": "x"}]}
    if figure is not None:
        out["figure"] = figure
    if quiz:
        out["quiz"] = quiz
    return out


def issues_of(text, figure=BAL):
    return KIT.settle(lesson(beat(text, figure)))[1]


def test_the_kit_is_registered_served_and_leaves_the_builtin_reaction_kind_alone():
    assert isinstance(KIT, ReactionKit) and not KIT.legacy and KIT.figure_kinds == ("chem_reaction",)
    assert kits.serving("chem_reaction") is KIT and "chem_reaction" in kits.kinds()
    assert kits.for_kind("reaction") is None and kits.serving("reaction") is None     # old lessons are not the kit's
    assert KIT.builder == {"chem_reaction": "lessonforge.longform.kit_figures:chem_reaction"}
    row = next(r for r in kits.describe() if r["name"] == "chemistry")
    assert row["subjects"] == ["chemistry"] and row["classes"] == [7, 8, 9] and "atoms" in row["keywords"]
    assert kits.rules_for("chemistry").startswith("\n\nSUBJECT KIT chemistry") and REACTION_RULES in kits.rules_for("chemistry")
    with knobs.applied({"LESSONFORGE_KITS": "0"}):
        assert kits.serving("chem_reaction") is None and kits.rules_for(["chemistry"]) == ""


def test_an_old_reaction_lesson_is_not_touched_by_the_kit():
    old = lesson(beat("The equation is balanced.", {"kind": "reaction", "equation": "H2 + O2 -> H2O"}))
    assert not KIT.uses(old) and kits.active(old) == [] and kits.lesson_faults(old) == []
    assert kits.settle_active(old) == old


def test_the_rules_name_the_figure_the_gaps_and_the_claims():
    for fragment in ('"kind":"chem_reaction"', '"?"', "{atoms of O left}", "{coefficient of H2}",
                     "{balanced coefficient of H2O}", "balanced", "not balanced", "state symbols"):
        assert fragment in REACTION_RULES, fragment
    assert 8 <= len(REACTION_RULES.splitlines()) <= 20


# ---------------------------------------------------------------- the model

def test_the_model_reads_the_equation_once_through_the_existing_parser():
    m = reaction_math.solve(UNBAL)
    assert (m.before, m.after, m.balanced, m.verdict) == ({"H": 2, "O": 2}, {"H": 2, "O": 1}, False, "not balanced yet")
    assert reaction_math.solve(BAL).balanced and reaction_math.solve(BAL).verdict == "balanced"
    unknown = reaction_math.solve(UNKNOWN)
    assert unknown.unknown and not unknown.balanced and unknown.verdict == "find the numbers"
    assert unknown.solved() == {"left": [1, 3], "right": [2]}
    assert reaction_math.solve({"equation": "Ca(OH)2 + 2HCl -> CaCl2 + 2H2O"}).balanced
    assert reaction_math.solve({**BAL, "counts": False}).shown() == frozenset({2.0})
    assert reaction_math.solve(BAL).shown() == frozenset({2.0, 4.0})


@pytest.mark.parametrize("figure,fragment", [
    ({"equation": ""}, "needs an \"equation\""), ({"equation": "H2 + O2"}, "no arrow"),
    ({"equation": "CaCO3(s) -> CaO + CO2"}, "state symbols"), ({"equation": "H2 <=> O2"}, "cannot read"),
    ({"equation": "Zz2 + O2 -> ZzO"}, "Zz in Zz2 is not an element"), ({"equation": "7H2 + O2 -> H2O"}, "more than can be drawn"),
    ({"equation": "2H2 + O2 -> 2H2O", "role": "wrong", "wrong": ["CO2"]}, "not in the equation"), (None, "needs an"),
])
def test_an_equation_code_cannot_vouch_for_is_refused_in_plain_words(figure, fragment):
    with pytest.raises(kits.KitError) as err:
        KIT.solve(figure)
    assert fragment in str(err.value)


def test_normalise_cleans_the_figure_and_drops_one_it_cannot_solve():
    assert KIT.normalise_figure({"kind": "chem_reaction", "equation": "  2H2 +  O2 ->   2H2O ", "extra": 1}) == BAL
    assert KIT.normalise_figure({**BAL, "counts": False, "role": "wrong", "wrong": ["H2O"]}) == \
        {**BAL, "counts": False, "role": "wrong", "wrong": ["H2O"]}
    assert KIT.normalise_figure({"kind": "chem_reaction", "equation": "Zz2 -> Zz"}) is None


def test_numbers_shown_are_the_ones_the_old_reaction_figure_shows():
    from lessonforge.harness import writer
    for equation in ("2H2 + O2 -> 2H2O", "H2 + O2 -> H2O", "? N2 + ? H2 -> ? NH3"):
        assert KIT.numbers({"kind": "chem_reaction", "equation": equation}) == \
            writer.figure_numbers({"kind": "reaction", "equation": equation}), equation
    assert writer.figure_numbers(BAL) == KIT.numbers(BAL)           # the writer reaches the kit through kits.serving


# ---------------------------------------------------------------- gaps

@pytest.mark.parametrize("gap,figure,expected", [
    ("atoms of O left", UNBAL, "2"), ("atoms of O right", UNBAL, "1"), ("atoms of oxygen after", BAL, "2"),
    ("Atoms Of Hydrogen Before", BAL, "4"), ("atoms of H reactants", BAL, "4"), ("total atoms left", BAL, "6"),
    ("coefficient of H2", BAL, "2"), ("coefficient of O2", BAL, "1"), ("balanced coefficient of H2", UNBAL, "2"),
    ("balanced coefficient of NH3", UNKNOWN, "2"), ("balanced coefficient of H2 left", UNKNOWN, "3"),
    ("atoms of H left + atoms of O left", BAL, "6"), ("atoms of H left * 2", BAL, "8"), ("atoms of H left / 8", BAL, "0.5"),
    ("atoms of O left - atoms of O right", UNBAL, "1"),
])
def test_gaps_fill_with_the_counts_of_the_equation(gap, figure, expected):
    assert KIT.fill_gap(gap, KIT.solve(figure))[0] == expected


@pytest.mark.parametrize("gap,figure,fragment", [
    ("atoms of Na left", BAL, "no Na in the equation"), ("atoms of O up", BAL, "can only hold"),
    ("coefficient of CO2", BAL, "CO2 is not in the equation"), ("coefficient of H2", UNKNOWN, "still asks for this coefficient"),
    ("mass", BAL, "can only hold"), ("atoms of O left / 0", UNBAL, "divides by zero"), ("__import__('os')", BAL, "can only hold"),
    ("atoms of H left +", BAL, "not arithmetic"),
    ("atoms of O left", {**BAL, "counts": False}, "hides its atom counts"),
    ("coefficient of H2O", {"kind": "chem_reaction", "equation": "H2O -> H2O"}, "on both sides"),
])
def test_a_gap_code_cannot_fill_is_a_fault_in_plain_words(gap, figure, fragment):
    with pytest.raises(kits.KitError) as err:
        KIT.fill_gap(gap, KIT.solve(figure))
    assert fragment in str(err.value)


def test_settle_fills_gaps_in_narration_steps_and_quiz():
    quiz = {"question": "How many O on the left?", "options": ["{atoms of O left}", "{atoms of O right}", "{atoms of O left + 1}"],
            "answer_index": 0, "why": ["yes", "that is the right", "that is hydrogen"], "explain": "It is {atoms of O left}."}
    b = beat("Left has {atoms of O left} oxygen atoms.", UNBAL, quiz)
    b["steps"] = [{"say": "Count {atoms of H left}", "show": "{total atoms right}"}]
    filled, issues = KIT.settle(lesson(b))
    out = filled["chapters"][0]["beats"][0]
    assert issues == [] and not KIT.unfilled(filled)
    assert out["narration"] == "Left has 2 oxygen atoms." and out["steps"][0] == {"say": "Count 2", "show": "3"}
    assert out["quiz"]["options"] == ["2", "1", "3"] and out["quiz"]["explain"] == "It is 2."


# ---------------------------------------------------------------- claims

@pytest.mark.parametrize("text,figure", [
    ("The equation is balanced.", UNBAL), ("Now it balances.", UNBAL), ("It is balanced, so we stop.", UNKNOWN),
    ("The equation is not balanced.", BAL), ("It is unbalanced.", BAL), ("It isn't balanced yet.", BAL),
    ("There is the same number of atoms on both sides.", UNBAL),
    ("The oxygen atoms are the same on both sides.", UNBAL),
    ("The atoms are conserved here.", UNBAL),
    ("There are more oxygen atoms on the right.", UNBAL), ("Fewer atoms on the left.", BAL),
    ("There are more hydrogen atoms on the left.", BAL),
])
def test_a_claim_the_counts_deny_is_refused(text, figure):
    assert any("the picture is" in i for i in issues_of(text, figure)), (text, issues_of(text, figure))


@pytest.mark.parametrize("text,figure", [
    ("The equation is balanced.", BAL), ("The equation is not balanced yet.", UNBAL), ("It is not balanced.", UNKNOWN),
    ("Is the equation balanced?", UNBAL), ("Make it balanced.", UNBAL), ("We want the equation balanced.", UNBAL),
    ("If it were balanced, the atoms would match.", UNBAL), ("A balanced equation has the same atoms on both sides.", UNBAL),
    ("Mass is conserved in every reaction.", UNBAL), ("The hydrogen atoms are the same on both sides.", UNBAL),
    ("There are more oxygen atoms on the left.", UNBAL), ("The atoms are conserved here.", BAL),
    ("Balancing means counting atoms.", UNBAL), ("The atoms are not the same on both sides.", UNBAL),
])
def test_a_true_or_hedged_or_general_sentence_is_allowed(text, figure):
    assert issues_of(text, figure) == [], (text, issues_of(text, figure))


def test_a_claim_is_checked_per_element_when_one_is_named():
    both = {"kind": "chem_reaction", "equation": "H2 + O2 -> H2O"}
    assert any("the picture is" in i for i in issues_of("The oxygen atoms are the same on both sides.", both))
    assert issues_of("The hydrogen atoms are the same on both sides.", both) == []


def test_a_gap_that_fails_to_fill_is_not_also_read_as_a_claim():
    got = issues_of("It has {atoms of Na left} atoms.", UNBAL)
    assert any("no Na" in i for i in got) and not any("the picture is" in i for i in got)


# ---------------------------------------------------------------- typed atom counts

@pytest.mark.parametrize("text,figure,what", [
    ("There are 5 oxygen atoms on the right.", UNBAL, "5 O atoms"),
    ("It has six atoms of hydrogen.", BAL, "6 H atoms"),
    ("There are 4 oxygen atoms.", UNBAL, "4 O atoms"),
    ("The right holds 2 oxygen atoms.", UNBAL, "2 O atoms"),           # the right side has 1; the left's 2 is not that side's
    ("That makes 9 atoms.", BAL, "9 atoms"),
    ("There are 3 carbon atoms.", BAL, "3 C atoms"),
])
def test_a_typed_atom_count_the_picture_does_not_show_is_refused(text, figure, what):
    got = issues_of(text, figure)
    assert any(what in i and "which the picture does not show" in i for i in got), (text, got)


@pytest.mark.parametrize("text,figure", [
    ("There are 4 hydrogen atoms on the right.", BAL), ("The left holds 2 oxygen atoms.", UNBAL),
    ("There are 2 oxygen atoms and 1 oxygen atom.", UNBAL), ("A water molecule has 3 atoms.", BAL),
    ("Each H2 has 2 hydrogen atoms.", BAL), ("That is two hydrogen atoms in H2.", BAL),
    ("Both sides have 6 atoms.", BAL), ("Take 2 H2O.", BAL),
])
def test_an_atom_count_the_picture_shows_is_allowed(text, figure):
    assert issues_of(text, figure) == [], (text, issues_of(text, figure))


def test_a_value_filled_from_a_gap_is_never_a_stray_number():
    assert issues_of("Left has {atoms of O left} oxygen atoms and {atoms of H left + 1} hydrogen atoms.", UNBAL) == []


def test_a_wrong_quiz_option_may_name_a_number_the_picture_does_not_show():
    quiz = {"question": "How many oxygen atoms are on the right?", "options": ["1", "7 oxygen atoms", "2"],
            "answer_index": 0, "why": ["yes", "no", "no"]}
    _, issues = KIT.settle(lesson(beat("Look.", UNBAL, quiz)))
    assert issues and all(KIT.expected_fault(i, lesson(beat("Look.", UNBAL, quiz))) for i in issues)
    right = dict(quiz, answer_index=1)
    _, issues = KIT.settle(lesson(beat("Look.", UNBAL, right)))
    assert not all(KIT.expected_fault(i, lesson(beat("Look.", UNBAL, right))) for i in issues)


# ---------------------------------------------------------------- lesson level and conformance

def test_the_shipped_cases_pass_through_the_kits_own_settle():
    cases = KIT.cases()
    assert len(cases.good) >= 1 and len(cases.refused) >= 3
    for good in cases.good:
        filled, issues = KIT.settle(good)
        assert issues == [] and not KIT.unfilled(filled)
    for bad, fragment in cases.refused:
        assert any(fragment in i for i in KIT.settle(bad)[1]), fragment
    for expr, figure, expected in cases.gaps:
        assert KIT.fill_gap(expr, KIT.solve(figure))[0] == expected, expr


def test_a_wrong_balanced_claim_and_a_wrong_count_reach_the_lesson_faults():
    bad = lesson(beat("The equation is balanced. It has 5 oxygen atoms on the right.", UNBAL))
    faults = kits.lesson_faults(bad)
    assert any("“balanced”" in f for f in faults) and any("5 O atoms" in f for f in faults)
    assert kits.lesson_faults(lesson(beat("It is not balanced: {atoms of O left} against {atoms of O right}.", UNBAL))) == []


def test_a_lesson_may_mix_chemistry_with_motion_and_each_kit_checks_its_own_beats():
    motion = {"kind": "motion", "start_speed": 0, "acceleration": 2, "duration": 6, "marks": [3, 6]}
    mixed = lesson(beat("The car speeds up. At 3 s it goes {speed at 3} m/s.", motion),
                   beat("The equation is not balanced: {atoms of O left} against {atoms of O right}.", UNBAL))
    assert kits.multi(mixed) and kits.lesson_faults(mixed) == []
    wrong = lesson(beat("The car speeds up.", motion), beat("The equation is balanced.", UNBAL),
                   beat("The car slows down.", motion))
    faults = kits.lesson_faults(wrong)
    assert any("“balanced”" in f and f.startswith("beat 2") for f in faults)
    assert any("slows down" in f and f.startswith("beat 3") for f in faults)
    assert not any("speeds up" in f for f in faults)


def test_the_repair_prompt_tells_the_writer_what_balances_the_equation():
    prompt = KIT.repair_prompt(lesson(beat("The equation is balanced.", UNBAL)), ["beat 1 (chapter 1): wrong"])
    assert "smallest balancing coefficients: 2 H2, 1 O2, 2 H2O" in prompt           # H2 + O2 -> H2O balances as 2 1 2
    assert "not balanced yet" in prompt and "YOUR LESSON" in prompt


def test_the_builder_draws_through_the_existing_reaction_figure():
    pytest.importorskip("manim")
    from lessonforge.longform import figures
    assert kits.builder_for("chem_reaction").__name__ == "chem_reaction"
    fig = figures.build(BAL)
    assert fig is not None and fig.kind == "reaction" and hasattr(fig, "hint_targets") and fig.species_info
    assert figures.build({"kind": "chem_reaction", "equation": "Zz2 -> Zz"}) is None          # refused, never drawn
    assert figures.build({"kind": "reaction", "equation": "2H2 + O2 -> 2H2O"}) is not None       # the old kind, unchanged
