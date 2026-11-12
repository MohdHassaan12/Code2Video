"""The motion kit: gaps, claims, stray numbers, expected faults and the cases it ships."""
import copy

import pytest

from lessonforge import kits, knobs
from lessonforge.kits.base import STRAY_RE
from lessonforge.kits.motion import MOTION_RULES, MotionKit

KIT = kits.get("motion")
SPEEDING = {"kind": "motion", "start_speed": 0, "acceleration": 2, "duration": 6, "marks": [3, 6]}
BRAKING = {"kind": "motion", "start_speed": 10, "acceleration": -2, "duration": 4}
STEADY = {"kind": "motion", "start_speed": 5, "acceleration": 0, "duration": 6}
REVERSING = {"kind": "motion", "start_speed": 10, "acceleration": -2, "duration": 8, "marks": [5]}


def lesson(*beats):
    return {"title": "t", "chapters": [{"title": "ONE", "learning_goal": "g", "role": "explain", "beats": list(beats)}]}


def beat(narration, figure=None, quiz=None, steps=None):
    out = {"narration": narration, "steps": steps if steps is not None else [{"say": narration[:20], "show": "x"}]}
    if figure is not None:
        out["figure"] = figure
    if quiz:
        out["quiz"] = quiz
    return out


def issues_of(text, figure=SPEEDING):
    return KIT.settle(lesson(beat(text, figure)))[1]


# ---------------------------------------------------------------- registration

def test_the_motion_kit_is_registered_and_served():
    assert isinstance(KIT, MotionKit) and kits.for_kind("motion") is KIT and kits.serving("motion") is KIT
    assert "motion" in kits.kinds() and not KIT.legacy and KIT.data_key is None
    assert KIT.builder == {"motion": "lessonforge.longform.kit_figures:motion"}
    assert kits.rules_for(["motion"]).startswith("\n\nSUBJECT KIT motion") and MOTION_RULES in kits.rules_for("motion")
    assert kits.rules_for(None) == ""
    with knobs.applied({"LESSONFORGE_KITS": "0"}):
        assert kits.serving("motion") is None and kits.kinds() == () and kits.rules_for(["motion"]) == ""


def test_the_rules_name_the_figure_the_gaps_and_the_claims():
    for fragment in ('"kind":"motion"', "THREE of start_speed, end_speed, acceleration, duration", "{speed at 3}",
                     "{distance at duration}", "{stop time}", "speeds up", "slows down", "comes to rest", "starts from rest",
                     "turns back", "NEW motion figure"):
        assert fragment in MOTION_RULES, fragment
    assert 8 <= len(MOTION_RULES.splitlines()) <= 20


# ---------------------------------------------------------------- gaps

@pytest.mark.parametrize("gap,figure,expected", [
    ("speed at 3", SPEEDING, "6"), ("speed at 6", SPEEDING, "12"), ("speed at 0", SPEEDING, "0"),
    ("speed at 6 - speed at 3", SPEEDING, "6"), ("distance at duration", SPEEDING, "36"), ("distance at 3", SPEEDING, "9"),
    ("speed at 3 + 2", SPEEDING, "8"), ("speed at 3 * 2", SPEEDING, "12"), ("speed at duration - speed at 3", SPEEDING, "6"),
    ("acceleration", BRAKING, "-2"), ("start speed", BRAKING, "10"), ("end speed", BRAKING, "2"),
    ("duration", BRAKING, "4"), ("stop time", REVERSING, "5"), ("distance at 8", REVERSING, "34"),
    ("speed at 8", REVERSING, "-6"), ("Speed At 3", SPEEDING, "6"), ("start  speed", BRAKING, "10"),
    ("speed at 3 / 4", {"kind": "motion", "start_speed": 1, "acceleration": 1, "duration": 3}, "1"),
])
def test_gaps_fill_with_the_models_numbers(gap, figure, expected):
    assert KIT.fill_gap(gap, KIT.solve(figure))[0] == expected


def test_a_gap_value_is_rounded_to_what_is_printed():
    text, value = KIT.fill_gap("speed at 1", KIT.solve({"kind": "motion", "start_speed": 0, "end_speed": 1, "duration": 3, "marks": [1]}))
    assert (text, value) == ("0.33", 0.33)
    assert KIT.fill_gap("speed at 3 - speed at 3", KIT.solve(SPEEDING)) == ("0", 0.0)         # never "-0"


@pytest.mark.parametrize("gap,fragment", [
    ("mass", "can only hold speed at T"), ("speed at 9", "outside the run"), ("speed at 2.5", "not a time the figure marks"),
    ("distance at 4", "add 4 to the figure"), ("speed at x", "can only hold"),
    ("distance at -1", "can only hold"), ("stop time", "does not come to rest"), ("speed at 3 / 0", "divides by zero"),
    ("speed at 3 +", "not arithmetic"), ("__import__('os')", "can only hold"), ("2 ** 3", "not arithmetic"),
])
def test_a_gap_code_cannot_fill_is_a_fault_in_words(gap, fragment):
    with pytest.raises(kits.KitError, match=fragment):
        KIT.fill_gap(gap, KIT.solve(SPEEDING))


def test_gaps_in_every_text_of_a_beat_are_filled():
    quiz = {"question": "Speed at {duration} s?", "options": ["{speed at 3} m/s", "{speed at 3 + 2} m/s", "{speed at 3 - 2} m/s"],
            "answer_index": 0, "why": ["It is {speed at 3} m/s.", "Too fast.", "Too slow."], "explain": "{acceleration} m/s^2 for 3 s."}
    steps = [{"say": "At 3 s", "show": "v = {speed at 3} m/s"}]
    out, issues = KIT.settle(lesson(beat("At 3 s it moves at {speed at 3} m/s.", SPEEDING, quiz=quiz, steps=steps)))
    b = out["chapters"][0]["beats"][0]
    assert issues == []
    assert b["narration"] == "At 3 s it moves at 6 m/s." and b["steps"][0]["show"] == "v = 6 m/s"
    assert b["quiz"]["options"] == ["6 m/s", "8 m/s", "4 m/s"] and b["quiz"]["question"] == "Speed at 6 s?"
    assert b["quiz"]["explain"] == "2 m/s^2 for 3 s." and not KIT.unfilled(out)


def test_a_gap_on_a_beat_with_no_motion_figure_is_a_fault_and_leaves_it_unfilled():
    out, issues = KIT.settle(lesson(beat("Its speed is {speed at 3} m/s.")))
    assert any("on a beat with no motion figure" in i for i in issues) and KIT.unfilled(out)
    _, issues = KIT.settle(lesson(beat("Its speed is {speed at 3} m/s.", {"kind": "graph", "functions": ["x"]})))
    assert any("no motion figure" in i for i in issues)


def test_an_unsolvable_figure_is_one_fault_and_its_gaps_are_left_alone():
    out, issues = KIT.settle(lesson(beat("It reaches {end speed} m/s.", {"kind": "motion", "start_speed": 0, "duration": 6})))
    assert len(issues) == 1 and "three numbers" in issues[0] and "beat 1 (chapter 1):" in issues[0]
    assert "{end speed}" in out["chapters"][0]["beats"][0]["narration"]


def test_two_quiz_options_that_come_out_equal_are_a_fault():
    quiz = {"question": "q", "options": ["{speed at 3} m/s", "6 m/s"], "answer_index": 0, "why": ["a", "b"]}
    _, issues = KIT.settle(lesson(beat("Count it.", SPEEDING, quiz=quiz)))
    assert any("two options come out the same once filled" in i for i in issues)


# ---------------------------------------------------------------- claims

@pytest.mark.parametrize("text,figure,bad", [
    ("The car speeds up.", BRAKING, True), ("The car speeds up.", SPEEDING, False), ("The car speeds up.", STEADY, True),
    ("It accelerates smoothly.", BRAKING, True), ("It is speeding up.", SPEEDING, False),
    ("The car slows down.", SPEEDING, True), ("The car slows down.", BRAKING, False), ("The driver brakes hard.", SPEEDING, True),
    ("It decelerates.", SPEEDING, True), ("It slows down.", STEADY, True),
    ("It moves at a constant speed.", SPEEDING, True), ("It moves at a constant speed.", STEADY, False),
    ("A steady velocity.", BRAKING, True), ("Uniform speed all along.", STEADY, False),
    ("The car comes to rest.", BRAKING, True), ("The car comes to rest.", REVERSING, False),
    ("It stops.", SPEEDING, True), ("It comes to a stop.", SPEEDING, True), ("It stops after a while.", REVERSING, False),
    ("The car starts from rest.", SPEEDING, False), ("The car starts from rest.", BRAKING, True),
    ("It begins at rest.", STEADY, True),
    ("It turns back.", BRAKING, True), ("It turns back.", REVERSING, False), ("It reverses.", SPEEDING, True),
    ("It slows down, stops and turns back.", REVERSING, False),          # a reversing run does all three
    ("It speeds up again on the way back.", REVERSING, False),
])
def test_a_claim_the_numbers_deny_is_a_fault_and_a_true_one_is_not(text, figure, bad):
    found = issues_of(text, figure)
    assert bool(found) is bad, (text, found)
    if bad:
        assert "the words say" in found[0] and "the picture is:" in found[0]


@pytest.mark.parametrize("text", [
    "It does not slow down.", "The car never speeds up.", "It doesn't come to rest.", "It cannot turn back.",
    "If it slows down, what happens?", "Does the car speed up?", "Would it come to rest or keep going?",
    "It is not moving at a constant speed.", "It will not stop without a brake.",
])
def test_negated_conditional_and_asked_forms_are_not_claims(text):
    assert issues_of(text, SPEEDING if "slow" not in text and "rest" not in text else SPEEDING) == []


def test_claims_in_a_step_show_and_the_question_are_read_but_an_option_may_be_wrong_on_purpose():
    quiz = {"question": "Why does it slow down?", "options": ["Because it slows down.", "Because it speeds up."],
            "answer_index": 0, "why": ["a", "b"], "explain": "It slows down here."}
    _, issues = KIT.settle(lesson(beat("Watch.", SPEEDING, quiz=quiz, steps=[{"say": "Watch", "show": "It slows down"}])))
    assert any("step 1:" in i and "slows down" in i for i in issues)
    assert any("quiz explain:" in i for i in issues)
    assert not any("quiz option" in i for i in issues) and not any("quiz question" in i for i in issues)


def test_the_words_inside_an_unfilled_gap_are_not_claims():
    _, issues = KIT.settle(lesson(beat("The stop time is {stop time} s.", SPEEDING)))
    assert issues and all("does not come to rest" in i for i in issues)               # the gap, and no "stop" claim
    assert issues_of("The stopwatch shows the stop time.", SPEEDING) == []
    assert issues_of("It stops after {stop time} s.", SPEEDING) != []                     # but "stops" outside the gap is a claim


# ---------------------------------------------------------------- typed numbers with units

@pytest.mark.parametrize("text,figure,what", [
    ("At 3 s the speed is 20 m/s.", SPEEDING, ["20 m/s"]),
    ("The acceleration is 5 m/s^2.", SPEEDING, ["5 m/s^2"]),
    ("The acceleration is 5 m/s2.", SPEEDING, ["5 m/s^2"]),
    ("The acceleration is 5 m/s².", SPEEDING, ["5 m/s^2"]),
    ("It travels 100 m.", SPEEDING, ["100 m"]), ("It travels 100 metres.", SPEEDING, ["100 m"]),
    ("It takes 9 seconds.", SPEEDING, ["9 s"]), ("It takes 9 s.", SPEEDING, ["9 s"]),
    ("At 7.5 meters per second.", SPEEDING, ["7.5 m/s"]),
    ("It goes from 3 m/s to 4 m/s.", SPEEDING, ["3 m/s", "4 m/s"]),
])
def test_a_typed_quantity_the_picture_does_not_show_is_a_fault(text, figure, what):
    model = KIT.solve(figure)
    assert KIT.stray_numbers(text, model, []) == what
    found = issues_of(text, figure)
    assert any(STRAY_RE.match(i) is None and "which the picture does not show" in i for i in found)


@pytest.mark.parametrize("text", [
    "It starts at 0 m/s and reaches 12 m/s after 6 s.", "At 3 s the speed is 6 m/s.", "The acceleration is 2 m/s^2.",
    "The acceleration is 2 m/s2.", "It covers 36 m.", "It covers 9 metres in 3 s.", "The speed is 6 meters per second.",
    "Between 3 s and 6 s.", "A speed of 12 m/s.", "No numbers here at all.", "It has 5 wheels and 2 doors.",
    "It takes 3 minutes.", "About 2 m/s squared.",
])
def test_quantities_the_picture_shows_are_not_stray(text):
    assert KIT.stray_numbers(text, KIT.solve(SPEEDING), []) == []


@pytest.mark.parametrize("text,gap,should", [
    ("The acceleration is {acceleration} metres per second.", "{acceleration}", "m/s squared (or metres per second squared)"),
    ("It gains {acceleration} m/s every second.", "{acceleration}", "m/s squared (or metres per second squared)"),
    ("At 3 s the speed is {speed at 3} m/s^2.", "a speed gap", "m/s (or metres per second)"),
    ("The run lasts {duration} m.", "a time gap", "s (or seconds)"),
    ("It covers {distance at duration} s.", "{distance at T}", "m (or metres)"),
])
def test_a_wrong_unit_after_a_filled_gap_names_the_unit_not_a_stray_number(text, gap, should):
    found = issues_of(text)
    assert len(found) == 1, found
    assert f"the unit after {gap}" in found[0] and f"should be {should}" in found[0]
    assert "which the picture does not show" not in found[0] and "write a gap instead" not in found[0]


@pytest.mark.parametrize("text", [
    "The acceleration is {acceleration} m/s^2.", "The acceleration is {acceleration} metres per second squared.",
    "The acceleration is {acceleration} m/s squared.",     # the very words MOTION_RULES and the wrong-unit message ask for
    "At 3 s the speed is {speed at 3} metres per second.", "The run lasts {duration} seconds and covers {distance at duration} m.",
    "Then the speed is {speed at 3 + 2} m/s.",           # arithmetic on gaps: no single quantity, so no unit rule
])
def test_the_right_unit_after_a_filled_gap_is_clean(text):
    assert issues_of(text) == []


def test_m_per_s_squared_in_words_is_an_acceleration_not_a_speed():
    assert KIT.stray_numbers("The acceleration is 5 m/s squared.", KIT.solve(SPEEDING), []) == ["5 m/s^2"]
    assert KIT.stray_numbers("The acceleration is 2 m/s squared.", KIT.solve(SPEEDING), []) == []


def test_a_typed_number_with_a_wrong_unit_is_still_the_stray_message():
    found = issues_of("The acceleration is 5 metres per second.")
    assert found and "says 5 m/s, which the picture does not show" in found[0]


def test_the_rules_allow_a_mixed_lesson_and_do_not_ask_for_one_subject():
    flat = " ".join(MOTION_RULES.split()).lower()
    assert "may mix subjects" in flat and "one subject" not in flat and "single subject" not in flat
    assert 8 <= len(MOTION_RULES.splitlines()) <= 20


def test_a_negative_value_may_be_said_as_its_size():
    model = KIT.solve(REVERSING)
    assert KIT.stray_numbers("It brakes at 2 m/s^2 and ends at 6 m/s backwards.", model, []) == []
    assert KIT.stray_numbers("It brakes at 3 m/s^2.", model, []) == ["3 m/s^2"]


def test_a_value_filled_from_a_gap_is_not_stray_and_an_arithmetic_distractor_is_allowed_once_filled():
    out, issues = KIT.settle(lesson(beat("It reaches {speed at 3 + 2} m/s, say 8 m/s.", SPEEDING)))
    assert issues == []
    _, issues = KIT.settle(lesson(beat("It reaches {speed at 3} m/s, not 7 m/s.", SPEEDING)))
    assert len(issues) == 1 and "7 m/s" in issues[0]


def test_acceleration_speed_time_and_distance_are_matched_by_their_own_unit():
    model = KIT.solve(SPEEDING)                 # 2 is the acceleration and not a speed; 6 is a time and a speed
    assert KIT.stray_numbers("It is 2 m/s.", model, []) == ["2 m/s"]
    assert KIT.stray_numbers("It is 12 s.", model, []) == ["12 s"]
    assert KIT.stray_numbers("It is 36 m.", model, []) == [] and KIT.stray_numbers("It is 36 m/s.", model, []) == ["36 m/s"]
    assert KIT.stray_numbers("After 3 s", model, []) == [] and KIT.stray_numbers("After 4 s", model, []) == ["4 s"]


def test_the_message_is_the_shared_stray_message():
    _, issues = KIT.settle(lesson(beat("At 3 s the speed is 20 m/s.", SPEEDING)))
    assert issues == ["beat 1 (chapter 1) narration: says 20 m/s, which the picture does not show "
                      "(write a gap instead of a typed value)"]


# ---------------------------------------------------------------- expected faults

def test_a_deliberate_wrong_quiz_option_is_an_expected_fault_and_a_wrong_answer_is_not():
    quiz = {"question": "What is the speed at 3 s?", "options": ["{speed at 3} m/s", "20 m/s"], "answer_index": 0,
            "why": ["a", "b"]}
    work = lesson(beat("Ask.", SPEEDING, quiz=quiz))
    _, issues = KIT.settle(work)
    assert len(issues) == 1 and STRAY_RE.match(issues[0])
    assert KIT.expected_fault(issues[0], work) is True
    wrong = copy.deepcopy(work)
    wrong["chapters"][0]["beats"][0]["quiz"]["answer_index"] = 1
    assert KIT.expected_fault(issues[0], wrong) is False                 # option 2 is the answer: a typed value there is a fault
    assert KIT.expected_fault("beat 1 (chapter 1) narration: says 20 m/s, which the picture does not show", work) is False
    assert KIT.expected_fault("some other fault", work) is False
    assert kits.lesson_faults(work) == []                                # the registry drops it as well


def test_the_registry_reports_the_faults_of_a_motion_lesson():
    found = kits.lesson_faults(lesson(beat("The car speeds up.", BRAKING)))
    assert len(found) == 1 and "speeds up" in found[0]
    assert kits.lesson_faults(lesson(beat("No figure here.", None))) == []


def test_a_lesson_that_mixes_geometry_and_motion_gets_the_one_subject_fault_only_while_mixing_is_off():
    mixed = lesson(beat("A car.", SPEEDING), beat("A shape.", {"kind": "shape", "points": {"A": [0, 0]}}))
    declared = {**lesson(beat("A car.", SPEEDING)), "shapes": {"a": {"points": {"A": [0, 0]}}}}
    with knobs.applied({"LESSONFORGE_KITS_MIXED": "0"}):
        assert kits.lesson_faults(mixed) == [kits.ONE_SUBJECT.format(names="geometry, motion")]
        assert any("two subject kits (geometry, motion)" in f for f in kits.lesson_faults(declared))
    assert not any("two subject kits" in f for f in kits.lesson_faults(mixed))        # the default: mixing is on
    assert not any("two subject kits" in f for f in kits.lesson_faults(declared))
    with knobs.applied({"LESSONFORGE_KITS": "0"}):
        assert kits.lesson_faults(mixed) == []


# ---------------------------------------------------------------- figure level

def test_figure_level_answers_follow_the_model():
    assert KIT.figure_issues(SPEEDING) == []
    assert "three numbers" in KIT.figure_issues({"kind": "motion", "start_speed": 1})[0]
    assert "you gave" in KIT.figure_issues({**SPEEDING, "end_speed": 15})[0]
    assert KIT.numbers(SPEEDING) == {"0", "12", "2", "6", "3"} and KIT.numbers({"kind": "motion"}) == set()
    good = KIT.normalise_figure({**SPEEDING, "caption": "junk", "extra": 1})
    assert good == {"kind": "motion", "start_speed": 0, "acceleration": 2, "duration": 6, "marks": [3.0, 6.0]}
    assert KIT.normalise_figure({"kind": "motion", "start_speed": 1}) is None and KIT.normalise_figure("no") is None
    text = KIT.describe(REVERSING)
    assert "starts at 10 m/s" in text and "comes to rest at 5 s" in text and "5 s -> 0 m/s" in text
    assert "three numbers" in KIT.describe({"kind": "motion"})


def test_uses_recognises_a_motion_lesson_by_its_figure_only():
    assert KIT.uses(lesson(beat("a", SPEEDING))) and KIT.uses_figures(lesson(beat("a", SPEEDING)))
    assert not KIT.uses(lesson(beat("a"))) and not KIT.uses(lesson(beat("a", {"kind": "graph"})))
    assert not KIT.uses(lesson(beat("a", {"kind": "shape", "use": "x"})), after_edit=True)
    assert kits.active(lesson(beat("a", SPEEDING))) == [KIT] and kits.active(lesson(beat("a"))) == []


def test_the_repair_prompt_tells_the_model_what_the_numbers_make():
    work = lesson(beat("The car speeds up.", BRAKING))
    _, found = KIT.settle(work)
    text = KIT.repair_prompt(work, found)
    assert "speeds up" in text and "starts at 10 m/s, ends at 2 m/s after 4 s" in text
    assert "Return the WHOLE lesson again as JSON" in text


# ---------------------------------------------------------------- the cases the kit ships

def test_the_kits_cases_meet_the_conformance_rules():
    cases = KIT.cases()
    assert len(cases.good) >= 1 and len(cases.refused) >= 6 and len(cases.gaps) >= 8
    for good in cases.good:
        out, issues = KIT.settle(good)
        assert issues == [] and not KIT.unfilled(out)
    classes = set()
    for bad, fragment in cases.refused:
        _, issues = KIT.settle(bad)
        assert any(fragment in i for i in issues), (fragment, issues)
        classes.add(fragment)
    assert {"speeds up", "slows down", "constant speed", "comes to rest", "starts from rest", "turns back", "20 m/s",
            "you gave", "no motion figure"} <= classes
    for expr, figure, expected in cases.gaps:
        assert KIT.fill_gap(expr, KIT.solve(figure))[0] == expected, expr


def test_the_good_case_is_idempotent_and_survives_a_second_check():
    good = KIT.cases().good[0]
    once, issues = KIT.settle(good)
    twice, again = KIT.settle(once)
    assert issues == [] and once == twice
    # a second check meets the filled distractor ("8 m/s") as a typed number: an expected fault, so not reported
    assert all(KIT.expected_fault(i, once) for i in again) and kits.lesson_faults(once) == []


# ---------------------------------------------------------------- the picture (Manim side)

def test_the_motion_figure_builds_from_the_model_with_graph_parts():
    pytest.importorskip("manim")
    from lessonforge.longform import figures
    fig = figures.build(SPEEDING)
    assert fig is not None and fig.kind == "motion" and fig.build
    assert {"axes", "x_label", "y_label", "curve0", "curve0_label", "point0", "point0_label", "point1"} <= set(fig.parts)
    assert figures.construct_animation(fig, run_time=1.0) is not None
    for part in KIT.focus_parts["motion"]:               # every name a step may focus on is a name the builder knows
        assert part in ("axes", "x_label", "y_label", "curve0", "curve0_label") or part.startswith("point")
    assert figures.build({"kind": "motion", "params": SPEEDING}).kind == "motion"      # the params form too
    assert figures.build(BRAKING).parts and figures.build(REVERSING).parts


def test_a_motion_figure_the_model_cannot_solve_builds_nothing(capsys):
    pytest.importorskip("manim")
    from lessonforge.longform import figures
    for bad in ({"kind": "motion", "start_speed": 0, "acceleration": 2},                                  # two inputs
                {"kind": "motion", "start_speed": 0, "acceleration": 2, "duration": 6, "end_speed": 15},  # over-determined
                {"kind": "motion", "start_speed": 0, "acceleration": 2, "duration": -1},
                {"kind": "motion", "start_speed": "fast", "acceleration": 2, "duration": 6}):
        assert figures.build(bad) is None
    assert "the previous picture stays" in capsys.readouterr().out


def test_the_kind_builds_only_while_the_switch_is_on():
    pytest.importorskip("manim")
    from lessonforge.longform import figures
    with knobs.applied({"LESSONFORGE_KITS": "0"}):
        assert figures.build(SPEEDING) is None
    assert figures.build(SPEEDING) is not None
    assert "motion" not in figures.BUILDERS and "motion" not in figures.KINDS       # additions only


# ---------------------------------------------------------------- the writer and figure_math seams

def _discipline(*figures):
    from lessonforge.harness import frameworks, writer
    raw = {"chapters": [{"beats": [{"narration": f"Beat {i}.", "steps": [], **({"figure": f} if f is not None else {})}
                                   for i, f in enumerate(figures)]}]}
    lesson = writer.discipline(raw, {"topic": "t"}, frameworks.get("worked_examples"))
    return [b.get("figure") for c in lesson["chapters"] for b in c["beats"]]


def test_a_good_motion_figure_survives_the_writers_discipline_and_a_bad_one_is_dropped():
    kept, dropped = _discipline(SPEEDING, {"kind": "motion", "start_speed": 0, "acceleration": 2})
    assert kept == SPEEDING and dropped is None
    messy, = _discipline({**SPEEDING, "junk": 1, "marks": [3, 3, 6]})
    assert messy == {"kind": "motion", "start_speed": 0, "acceleration": 2, "duration": 6, "marks": [3, 6]}


def test_with_the_switch_off_the_writer_drops_a_motion_figure_as_before():
    with knobs.applied({"LESSONFORGE_KITS": "0"}):
        assert _discipline(SPEEDING) == [None]


def test_figure_issues_and_figure_numbers_follow_the_model():
    from lessonforge.harness import writer
    from lessonforge.longform import figure_math
    assert figure_math.figure_issues(SPEEDING) == []
    assert figure_math.figure_issues({"kind": "motion", "start_speed": 0, "acceleration": 2})      # the solve message
    assert figure_math.figure_issues({"kind": "motion", "params": SPEEDING}) == []
    assert writer.figure_numbers(SPEEDING) == {"0", "2", "3", "6", "12"}
    assert writer.figure_numbers({"kind": "motion", "start_speed": 0}) == set()
    with knobs.applied({"LESSONFORGE_KITS": "0"}):
        assert writer.figure_numbers(SPEEDING) == set()
        assert figure_math.figure_issues({"kind": "motion", "start_speed": 0}) == []


def test_a_kit_that_crashes_in_a_seam_costs_nothing(monkeypatch):
    from lessonforge.harness import writer
    from lessonforge.longform import figure_math

    def boom(*_a, **_k):
        raise RuntimeError("boom")
    monkeypatch.setattr(KIT, "numbers", boom, raising=False)
    monkeypatch.setattr(KIT, "figure_issues", boom, raising=False)
    monkeypatch.setattr(KIT, "normalise_figure", boom, raising=False)
    assert writer.figure_numbers(SPEEDING) == set() and figure_math.figure_issues(SPEEDING) == []
    assert _discipline(SPEEDING) == [SPEEDING]


def test_the_rules_travel_in_a_per_lesson_addendum_and_nothing_else_changes():
    from lessonforge.harness import writer
    seen = []
    plain = writer.write_lesson(_BRIEF, _stub_llm(seen), log=lambda *_: None)
    assert all(system == writer.SYSTEM for _, system in seen)      # no brief["kits"]: the prompt is the one it always was
    assert plain["kit_check"]["kits"] == ["motion"]                # the figures alone select the kit for the check
    seen.clear()
    said = []
    lesson = writer.write_lesson({**_BRIEF, "kits": ["motion", "nonsense"]}, _stub_llm(seen), log=said.append)
    assert all(system == writer.SYSTEM + kits.rules_for(["motion"]) for _, system in seen)
    assert MOTION_RULES in seen[0][1] and any("kit 'nonsense' is not registered" in line for line in said)
    assert lesson["kit_check"] == {"kits": ["motion"], "faults_left": []}
    assert lesson["chapters"][0]["beats"][0]["figure"]["kind"] == "motion"
    assert "{" not in lesson["chapters"][0]["beats"][0]["narration"]          # the gap is filled by code


_BRIEF = {"topic": "Speed and acceleration", "audience": "Class 9 students", "level": "foundation", "goal": "read a speed-time graph",
          "style": "tutor", "language": "en-IN", "framework": "concrete_first", "duration_minutes": 6}


def _stub_llm(seen, narration="The car starts from rest and speeds up. At 3 s its speed is {speed at 3} m/s."):
    def chapter(i):
        return {"title": f"Part {i}", "learning_goal": "g", "beats": [
            {"narration": narration + " Look at how the line climbs on the graph as the seconds go by.",
             "visual": "v", "check": "c", "figure": SPEEDING, "steps": [{"say": "speeds up", "show": "v = 2t", "kind": "point"}]}]}

    def llm(prompt, system):
        seen.append((prompt, system))
        if "Plan a" in prompt:
            return {"title": "Motion", "thesis": "t", "anchor": "a car", "anchor_name": "the car", "small_case": "2 m/s^2",
                    "method": ["read"], "glossary": [], "moves": ["question", "guess"],
                    "chapters": [{"title": f"c{i}", "learning_goal": "g", "enters_with": "a", "leaves_with": f"b{i}"} for i in range(7)]}
        return {**chapter(len(seen)), "uses_from_before": [], "running_example_step": "not used", "hands_forward": "next",
                "ledger_update": {"established_add": [], "glossary_add": []}}
    return llm


def _raw(narration, figure=SPEEDING):
    return {"title": "t", "chapters": [{"title": "ONE", "beats": [
        {"narration": narration, "steps": [{"say": "x", "show": "y"}], "figure": figure}]}]}


def _quiet(*_a, **_k):
    return None


def test_kit_pass_leaves_a_lesson_with_no_served_kit_alone_and_fills_a_clean_one_without_the_model():
    from lessonforge.harness import writer

    def llm(prompt, system):
        raise AssertionError("no model call needed")
    plain = {"title": "t", "chapters": [{"title": "c", "beats": [{"narration": "Look.", "steps": []}]}]}
    assert writer.kit_pass(plain, llm, "S", log=_quiet) is plain
    out = writer.kit_pass(_raw("At 3 s the speed is {speed at 3} m/s."), llm, "S", log=_quiet)
    assert out["_kit_faults"] == [] and out["chapters"][0]["beats"][0]["narration"] == "At 3 s the speed is 6 m/s."


def test_kit_pass_asks_the_model_to_repair_a_wrong_typed_speed_and_keeps_the_better_draft():
    from lessonforge.harness import writer
    seen = []

    def llm(prompt, system):
        seen.append((prompt, system))
        return _raw("At 3 s the speed is {speed at 3} m/s.")

    out = writer.kit_pass(_raw("At 3 s the speed is 20 m/s."), llm, "THE SYSTEM", log=_quiet)
    assert len(seen) == 1 and seen[0][1] == "THE SYSTEM"
    assert "20 m/s" in seen[0][0] and "What your figures make" in seen[0][0] and "starts at 0 m/s" in seen[0][0]
    assert out["_kit_faults"] == [] and out["chapters"][0]["beats"][0]["narration"] == "At 3 s the speed is 6 m/s."


def test_kit_pass_stops_at_the_limit_keeps_the_old_draft_when_the_repair_is_worse_and_survives_a_failing_model():
    from lessonforge.harness import writer
    bad = _raw("At 3 s the speed is 20 m/s.")
    worse = _raw("It brakes at 20 m/s and 30 m/s.")
    calls = []

    def llm(prompt, system):
        calls.append(1)
        return worse
    out = writer.kit_pass(bad, llm, "S", log=_quiet)
    assert len(calls) == writer.KIT_REPAIRS == 2
    assert len(out["_kit_faults"]) == 1 and "20 m/s" in out["_kit_faults"][0]

    def broken(prompt, system):
        raise RuntimeError("boom")
    assert len(writer.kit_pass(bad, broken, "S", log=_quiet)["_kit_faults"]) == 1


def test_a_deliberate_wrong_quiz_option_is_no_fault_for_the_writer():
    from lessonforge.harness import writer
    raw = _raw("It speeds up.")
    raw["chapters"][0]["beats"][0]["quiz"] = {"question": "What is the speed at 3 s?", "options": ["{speed at 3} m/s", "20 m/s"],
                                              "answer_index": 0, "why": ["right", "too fast"]}
    out = writer.kit_pass(raw, lambda p, s: 1 / 0, "S", log=_quiet)
    assert out["_kit_faults"] == []


def test_kit_pass_asks_for_one_subject_when_a_lesson_mixes_two_and_mixing_is_off():
    from lessonforge.harness import writer
    raw = _raw("It speeds up.")
    raw["chapters"][0]["beats"].append({"narration": "Now a shape.", "steps": [],
                                        "figure": {"kind": "shape", "points": {"A": [0, 0], "B": [4, 0], "C": [0, 3]}, "polygon": "ABC"}})
    with knobs.applied({"LESSONFORGE_KITS_MIXED": "0"}):
        out = writer.kit_pass(raw, lambda p, s: raw, "S", log=_quiet)
        assert any("two subject kits" in f for f in out["_kit_faults"])
    out = writer.kit_pass(raw, lambda p, s: raw, "S", log=_quiet)
    assert not any("two subject kits" in f for f in out["_kit_faults"])


def test_the_pinned_prompts_do_not_change_with_a_kit_registered():
    from lessonforge.harness import pack, writer
    assert MOTION_RULES not in writer.SYSTEM and MOTION_RULES not in writer.FIGURE_RULES and MOTION_RULES not in pack.SYSTEM
