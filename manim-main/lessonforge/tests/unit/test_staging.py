"""Video-quality plan S5: a finished graph, table or verdict is drawn in as it is talked about (look key ``staging``).

No render, no voice: the hold-back is checked on the built figures with a stub scene; the animations of a reaction change are
checked by what they are made of. ``staging="whole"`` (every lesson made before 2026-11-09) is the old behaviour."""
import copy
from types import SimpleNamespace

from lessonforge.harness import writer
from lessonforge.longform import figures, kit_figures, reaction_hints, runtime

MOTION = {"kind": "motion", "start_speed": 0, "acceleration": 3, "duration": 4, "marks": [2, 4]}


def quiet(*_):
    pass


scene_obj = None


def stage(figure, steps, due, ready_at=10.0, staged=True, sentences=(), beat_start=10.0):
    global scene_obj
    scene_obj = SimpleNamespace(current={"sentences": list(sentences)}, beat_start=beat_start, _beat_layout={},
                                STAGE_KEEP=runtime.GuidedChapter.STAGE_KEEP, DRAW_IN=runtime.GuidedChapter.DRAW_IN)
    for name in ("_hide", "_graph_stage_times", "_reaction_stage_times", "_show_late", "_value_said"):
        setattr(scene_obj, name, getattr(runtime.GuidedChapter, name).__get__(scene_obj))
    figure.staged_steps = staged
    figure._late = {}
    runtime.GuidedChapter._hold_back_steps(scene_obj, figure, steps, due, ready_at)
    return scene_obj


STEPS = [{"say": "Here is the graph", "focus": "axes"}, {"say": "starts from rest", "focus": "curve0"},
         {"say": "After 2 seconds", "focus": "point0"}, {"say": "After 4 seconds", "focus": "point1"},
         {"say": "So the acceleration is", "focus": "curve0_label"}]
DUE = [10.0, 13.0, 16.0, 20.0, 24.0]


def test_a_graph_draws_each_part_at_the_step_that_names_it():
    fig = kit_figures.motion(MOTION)
    sc = stage(fig, STEPS, DUE)
    late = fig._late
    assert set(late) == {"curve0", "point0", "point0_label", "point1", "point1_label", "curve0_label"}
    assert late["curve0"]["at"] == 13.0 and late["point0"]["at"] == 16.0 and late["point0_label"]["at"] == 16.0
    assert late["point1"]["at"] == 20.0 and late["curve0_label"]["at"] == 24.0
    assert "axes" not in late and "x_label" not in late                      # the frame is there from the start
    assert sc._beat_layout["held_until"]["point1"] == 10.0 and "point1_label" in sc._beat_layout["staged"]
    # hidden until its moment, then drawn in, and everything is shown at the end
    point = fig.parts["point0"]
    assert point.get_fill_opacity() == 0
    runtime.GuidedChapter._show_late(sc, fig, 15.0)
    assert point.get_fill_opacity() == 0
    runtime.GuidedChapter._show_late(sc, fig, 16.0 + runtime.GuidedChapter.DRAW_IN + .01)
    assert point.get_fill_opacity() > 0.9
    runtime.GuidedChapter._show_late(sc, fig, 0.0, everything=True)
    assert fig._late == {} and fig.parts["point1"].get_fill_opacity() > 0.9 and fig.parts["curve0_label"].get_fill_opacity() > 0


def test_a_curve_is_drawn_along_and_the_equation_comes_with_it_when_no_step_names_the_equation():
    fig = kit_figures.motion(MOTION)
    sc = stage(fig, [STEPS[0], STEPS[1], STEPS[2]], DUE[:3])
    curve = fig._late["curve0"]
    assert any(whole is not None for _, _, _, whole in curve["saved"])      # a copy to grow from, not a fade
    assert fig._late["curve0_label"]["at"] == 13.0                            # with the curve
    runtime.GuidedChapter._show_late(sc, fig, 13.0 + .3)
    piece, _, _, whole = next(item for item in curve["saved"] if item[3] is not None)
    assert 0 < len(piece.points) < len(whole.points)                         # part of the curve is drawn, not all of it


def test_a_part_no_step_names_stays_and_a_part_of_the_first_step_still_waits_for_that_cue():
    fig = kit_figures.motion(MOTION)
    stage(fig, [{"say": "x", "focus": "point1"}], [30.0])
    assert set(fig._late) == {"point1", "point1_label"}                      # point0 and the curve were never named: shown
    fig = kit_figures.motion(MOTION)
    stage(fig, [{"say": "x", "focus": "point0"}], [10.0], ready_at=10.0)      # the first step's own part: not there before its cue
    assert set(fig._late) == {"point0", "point0_label"} and fig._late["point0"]["at"] == 10.0


def test_staging_whole_is_the_old_picture():
    fig = kit_figures.motion(MOTION)
    sc = stage(fig, STEPS, DUE, staged=False)
    assert fig._late == {} and fig.parts["point0"].get_fill_opacity() > 0.9 and "staged" not in sc._beat_layout


def test_a_figure_with_no_name_for_the_part_is_left_alone():
    fig = kit_figures.motion(MOTION)
    stage(fig, [{"say": "x", "focus": "nonesuch"}, {"say": "y"}], [20.0, 30.0])
    assert fig._late == {}


def sentence(text, start=0.0, duration=12.0):
    return {"text": text, "start": start, "duration": duration}


SPECIES = [{"formula": "H2", "side": "left", "atoms": [("H", 2)], "n": 1, "unknown": False},
           {"formula": "O2", "side": "left", "atoms": [("O", 2)], "n": 1, "unknown": False},
           {"formula": "H2O", "side": "right", "atoms": [("H", 2), ("O", 1)], "n": 1, "unknown": False}]


def test_the_table_waits_for_the_word_that_counts_and_the_verdict_for_the_word_that_says_it():
    s = [sentence("Hydrogen burns with oxygen and makes water. Count the oxygen atoms on the left: there are 2. "
                  "On the right there is only 1. So the equation is not balanced yet.", 0.0, 14.0)]
    got = reaction_hints.stage_times(s, SPECIES)
    toks = [(w, t) for w, t in reaction_hints._words(s[0])]
    count_at = next(t for w, t in toks if w == "count")
    balanced_at = next(t for w, t in toks if w == "balanced")
    assert abs(got["table"] - count_at) < 1e-9 and abs(got["verdict"] - balanced_at) < 1e-9
    assert got["verdict"] > got["table"]


def test_balance_as_a_verb_is_not_the_verdict_and_a_silent_beat_has_none():
    s = [sentence("To balance it, put 2 in front of hydrogen. Now the oxygen atoms on the left are 2.", 0.0, 10.0)]
    got = reaction_hints.stage_times(s, SPECIES)
    assert got["verdict"] is None and got["table"] is not None
    assert reaction_hints.stage_times([sentence("Hydrogen burns.", 0.0, 3.0)], SPECIES) == {"table": None, "verdict": None}


def reaction(equation):
    fig = figures.reaction({"equation": equation})
    return fig


def test_the_reaction_holds_its_table_and_verdict_for_their_words():
    s = [sentence("Hydrogen burns with oxygen. Count the oxygen atoms on the left. So it is not balanced yet.", 0.0, 12.0)]
    fig = reaction("H2 + O2 -> H2O")
    sc = stage(fig, [], [], ready_at=11.0, sentences=s, beat_start=10.0)
    assert {"count_heads", "left_count", "right_count", "verdict"} <= set(fig._late)
    assert fig._late["left_count"]["at"] < fig._late["verdict"]["at"] and fig._late["left_count"]["at"] >= 11.0
    assert fig.parts["verdict"].get_fill_opacity() == 0
    old = reaction("H2 + O2 -> H2O")
    whole = reaction("H2 + O2 -> H2O")
    assert not getattr(whole, "staged_steps", False) and "held_until" in sc._beat_layout


def kinds(animations):
    return [[type(a).__name__ for a in group.animations] for group in animations]


def test_a_staged_reaction_change_takes_the_old_table_and_verdict_away_before_the_molecules_move():
    old, new = reaction("H2 + O2 -> H2O"), reaction("2H2 + O2 -> 2H2O")
    plain = figures.reaction_change(old, new)
    new.staged_steps = True
    staged = figures.reaction_change(old, new)
    assert len(plain) == 2 and len(staged) == 2
    leaving = [a for a in staged[0].animations]
    assert {type(a).__name__ for a in leaving} == {"FadeOut"} and len(leaving) == 4        # heads, before/after rows, verdict
    assert {m for a in leaving for m in [a.mobject]} == {old.parts[n] for n in ("count_heads", "left_count", "right_count", "verdict")}
    assert all(type(a).__name__ != "FadeOut" or a.mobject not in leaving for a in staged[1].animations)
    # the unstaged change still rolls the numbers over in its second group, as before
    assert any(type(a).__name__ in ("FadeIn", "ReplacementTransform") for a in plain[1].animations)


def lesson(*beats):
    return {"title": "t", "chapters": [{"id": 1, "title": "ONE", "beats": list(beats)}]}


def test_the_writer_names_the_part_a_motion_step_talks_about():
    beat = {"id": "02", "figure": MOTION, "narration": "x", "steps": [
        {"say": "starts from rest", "show": "a"}, {"say": "the line climbs steadily", "show": "b"},
        {"say": "After 2 seconds", "show": "c"}, {"say": "After 4 seconds", "show": "d", "focus": "curve0_label"},
        {"say": "After 9 seconds", "show": "e"}]}
    made = writer.stage_graphs(lesson(beat), log=quiet)
    focus = [s.get("focus") for s in made["chapters"][0]["beats"][0]["steps"]]
    assert focus == [None, "curve0", "point0", "curve0_label", None]            # an author's focus is kept; 9 s is no mark
    again = copy.deepcopy(made)
    assert writer.stage_graphs(again, log=quiet) == made                         # idempotent


def test_the_writer_leaves_a_held_mark_and_other_figures_alone():
    held = {"id": "07", "figure": {**MOTION, "hold_marks": [2]}, "narration": "q?", "steps": [{"say": "After 2 seconds", "show": "x"}]}
    other = {"id": "08", "figure": {"kind": "graph", "functions": ["x"]}, "narration": "q?", "steps": [{"say": "the line climbs", "show": "x"}]}
    before = copy.deepcopy(lesson(held, other))
    assert writer.stage_graphs(lesson(held, other), log=quiet) == before


def test_the_knob_turns_the_writer_pass_off():
    from lessonforge import knobs
    beat = {"id": "02", "figure": MOTION, "narration": "x", "steps": [{"say": "After 2 seconds", "show": "c"}]}
    with knobs.applied({"HARNESS_STAGING": "whole"}):
        out = writer.stage_graphs(lesson(copy.deepcopy(beat)), log=quiet)
    assert "focus" not in out["chapters"][0]["beats"][0]["steps"][0]


def test_a_points_label_waits_for_the_voice_to_say_its_value_while_the_dot_comes_with_the_step():
    fig = kit_figures.motion(MOTION)
    s = [sentence("The line climbs steadily. After 2 seconds its speed is 6 metres per second. After 4 seconds it is 12 metres per second.",
                  0.0, 14.0)]
    steps = [{"say": "The line climbs steadily", "focus": "curve0"}, {"say": "After 2 seconds", "focus": "point0"},
             {"say": "After 4 seconds", "focus": "point1"}]
    due = [10.0, 13.5, 20.0]
    stage(fig, steps, due, ready_at=10.0, sentences=s)
    late = fig._late
    assert late["point0"]["at"] == 13.5 and late["point1"]["at"] == 20.0                # the dots: at their steps
    toks = dict(__import__("lessonforge.longform.shape_hints", fromlist=["tokens"]).tokens(s[0]))
    assert abs(late["point0_label"]["at"] - (10.0 + toks["6"] - runtime.CUE_LEAD)) < 1e-6   # the 6, when it is said
    assert late["point0_label"]["at"] > late["point0"]["at"] + 0.5
    assert late["point1_label"]["at"] > late["point1"]["at"]
    # a value never said keeps the label with its step
    fig = kit_figures.motion(MOTION)
    stage(fig, steps, due, ready_at=10.0, sentences=[sentence("The line climbs. After 2 seconds. After 4 seconds.", 0.0, 8.0)])
    assert fig._late["point0_label"]["at"] == 13.5


def test_the_writer_names_the_start_point_and_the_held_mark_at_the_answers_cue():
    quiz_beat = {"id": "02", "figure": {**MOTION2, "hold_marks": [2.0]}, "narration": "q?",
                 "steps": [{"say": "another cart starts at", "show": "a"}, {"say": "speeds up", "show": "b"}]}
    answer = {"id": "03", "figure": dict(MOTION2), "narration": "It is 8.",
              "steps": [{"say": "It is", "show": "c"}, {"say": "gained", "show": "d"}]}
    made = writer.stage_graphs(lesson(quiz_beat, answer), log=quiet)
    beats = made["chapters"][0]["beats"]
    assert [s.get("focus") for s in beats[0]["steps"]] == ["point0", None]            # "starts at": the point at 0 s
    assert [s.get("focus") for s in beats[1]["steps"]] == ["point1", None]            # the answer's cue: the held 2 s mark
    assert writer.stage_graphs(copy.deepcopy(made), log=quiet) == made


MOTION2 = {"kind": "motion", "start_speed": 4, "acceleration": 2, "duration": 4, "marks": [0, 2, 4]}


def test_a_motion_figure_that_differs_only_by_its_hold_is_swapped_not_morphed():
    import json
    sc = SimpleNamespace(_figure_key=json.dumps(MOTION, sort_keys=True))
    fig = kit_figures.motion(MOTION)
    fig.staged_steps = True
    check = lambda spec, **k: runtime.GuidedChapter._only_a_hold_differs(sc, fig, fig, spec)  # noqa: E731
    assert check({**MOTION, "hold_marks": [2]})
    assert not check(MOTION)                                   # the very same: never reached (the figure is kept)
    assert not check({**MOTION, "acceleration": 2})            # another motion: the old morph
    fig.staged_steps = False
    assert not check({**MOTION, "hold_marks": [2]})            # staging whole: as before
