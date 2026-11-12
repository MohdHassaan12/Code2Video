"""Video-quality plan S4: a quiz's answer is not on the screen or said before it is asked. Pure: no render, no voice."""
import copy

from lessonforge import knobs
from lessonforge.harness import quiz_leaks as Q
from lessonforge.harness import writer

MOTION = {"kind": "motion", "start_speed": 4, "acceleration": 2, "duration": 4, "marks": [0, 2, 4]}


def quiz(options=("4 m/s", "8 m/s", "12 m/s"), answer=1, question="What is the cart's speed after 2 seconds?", **more):
    return {"question": question, "options": list(options), "answer_index": answer, "why": ["a", "b", "c"], **more}


def beat(id, narration="", figure=None, steps=(), **more):
    out = {"id": id, "narration": narration, "steps": [{"say": s[:12], "show": s} for s in steps], **more}
    if figure is not None:
        out["figure"] = figure
    return out


def lesson(*beats):
    return {"title": "t", "chapters": [{"id": 1, "title": "ONE", "beats": list(beats)}]}


def asks(**more):
    return beat("07", "Back to the cart. It starts at 4 metres per second. What is its speed after 2 seconds?", MOTION,
                ["Starts at 4 m/s"], quiz=quiz(**more))


def test_the_mark_that_shows_the_answer_is_held_and_the_others_are_not():
    made = writer.quiz_leaks(lesson(asks()), log=lambda *_: None)
    figure = made["chapters"][0]["beats"][0]["figure"]
    assert figure["hold_marks"] == [2]                      # 2 s, 8 m/s is the answer; 0 s, 4 m/s and 4 s, 12 m/s are options
    assert {k: v for k, v in figure.items() if k != "hold_marks"} == MOTION


def test_the_pass_is_idempotent_and_a_lesson_with_no_quiz_is_untouched():
    once = writer.quiz_leaks(lesson(asks()), log=lambda *_: None)
    twice = writer.quiz_leaks(copy.deepcopy(once), log=lambda *_: None)
    assert once == twice
    plain = lesson(beat("01", "The cart speeds up.", MOTION, ["x"]), beat("02", "No question here.", None, ["y"]))
    before = copy.deepcopy(plain)
    assert writer.quiz_leaks(plain, log=lambda *_: None) == before


def test_an_authors_own_hold_list_is_kept_and_other_figures_are_left_alone():
    own = lesson(beat("07", "q?", {**MOTION, "hold_marks": [4]}, ["x"], quiz=quiz()))
    assert writer.quiz_leaks(own, log=lambda *_: None)["chapters"][0]["beats"][0]["figure"]["hold_marks"] == [4]
    other = lesson(beat("07", "q?", {"kind": "graph", "functions": ["x"]}, ["x"], quiz=quiz()))
    assert "hold_marks" not in writer.quiz_leaks(other, log=lambda *_: None)["chapters"][0]["beats"][0]["figure"]


def test_a_time_answer_holds_the_mark_at_that_time_but_a_given_time_does_not():
    ask_time = beat("07", "When does it reach eight metres per second?", MOTION, ["x"],
                    quiz=quiz(("1 s", "2 s", "4 s"), 1, "When does the speed reach 8 m/s?"))
    assert Q.leaking_marks(ask_time) == [2]
    given = beat("07", "q?", MOTION, ["x"], quiz=quiz(("1 s", "2 s", "4 s"), 1, "After 2 seconds, how fast, in m/s?"))
    assert Q.leaking_marks(given) == []                      # 2 is in the question: it is given, not the answer


def test_the_graph_leaves_the_held_point_and_label_off_but_keeps_its_scale():
    from lessonforge.longform import kit_figures
    whole, held = kit_figures.motion(MOTION), kit_figures.motion({**MOTION, "hold_marks": [2]})
    assert {"point0", "point1", "point2", "point2_label"} <= set(whole.parts)
    assert "point1" not in held.parts and "point1_label" not in held.parts and {"point0", "point2"} <= set(held.parts)
    # the others keep their names and their places, so a step's focus and the label layout are the answer beat's
    for name in ("point0", "point2", "point0_label", "point2_label", "curve0_label"):
        assert abs(held.parts[name].get_center() - whole.parts[name].get_center()).max() < 1e-6
    assert [round(float(x), 3) for x in (held.parts["axes"].y_range)] == [round(float(x), 3) for x in (whole.parts["axes"].y_range)]


def test_an_answer_said_in_an_earlier_beat_is_a_finding_with_the_beat_and_the_place():
    said = lesson(beat("05", "After two seconds the cart goes at 8 metres per second.", MOTION, ["2 s: 8 m/s"]), asks())
    found = Q.find(said)
    assert {f["kind"] for f in found} == {"narration", "screen", "figure"} and all(f["beat"] == "07" for f in found)
    assert any("beat 05" in f["where"] and f["number"] == "8" for f in found)
    assert "beat 07: the answer 8 is already in view" in Q.describe(found[0])


def test_a_clean_lesson_and_a_deliberate_setup_have_no_finding():
    assert Q.find(lesson(beat("05", "The cart speeds up.", None, ["x"]), asks()), assume_hold=True) == []
    deliberate = lesson(beat("05", "At 8 metres per second it is fast.", None, ["x"]), beat("07", "q?", None, ["x"], quiz=quiz(allow_seen=True)))
    assert Q.find(deliberate) == []
    # a bare small number is in every lesson: not looked for
    assert Q.find(lesson(beat("01", "There are 2 cats.", None, ["2 cats"]), beat("02", "q?", None, ["x"], quiz=quiz(("1", "2", "3"), 1)))) == []


def test_the_question_beats_own_figure_counts_unless_the_mark_is_held():
    alone = lesson(asks())
    assert [f["kind"] for f in Q.find(alone, assume_hold=False)] == ["figure"]
    assert Q.find(alone, assume_hold=True) == []
    held = writer.quiz_leaks(copy.deepcopy(alone), log=lambda *_: None)
    assert Q.find(held, assume_hold=False) == []


def test_the_pass_notes_what_it_cannot_fix_and_keeps_the_words():
    said = lesson(beat("05", "After two seconds the cart goes at 8 metres per second.", None, ["x"]), asks())
    out = writer.quiz_leaks(copy.deepcopy(said), log=lambda *_: None)
    assert out["quiz_leaks"] and "beat 05" in out["quiz_leaks"][0]
    assert out["chapters"][0]["beats"][0]["narration"] == said["chapters"][0]["beats"][0]["narration"]


def test_the_knob_turns_the_pass_off():
    with knobs.applied({"HARNESS_QUIZ_LEAKS": "0"}):
        before = copy.deepcopy(lesson(asks()))
        assert writer.quiz_leaks(lesson(asks()), log=lambda *_: None) == before


def test_figures_and_words_runs_it():
    made = writer.figures_and_words(lesson(asks()), log=lambda *_: None)
    assert made["chapters"][0]["beats"][0]["figure"]["hold_marks"] == [2]


def test_the_kit_pipeline_counts_a_leak_as_a_fault_but_not_a_motion_mark():
    from lessonforge.harness import kit_pipeline as KP
    said = lesson(beat("05", "After two seconds the cart goes at 8 metres per second.", None, ["x"]), asks())
    _, faults = KP.settled_faults(said)
    assert [f for f in faults if f.startswith(KP.QUIZ_LEAK)] and "beat 05" in " ".join(faults)
    _, clean = KP.settled_faults(lesson(asks()))
    assert not [f for f in clean if f.startswith(KP.QUIZ_LEAK)]            # its own mark is held back by the pass instead
    with knobs.applied({"HARNESS_QUIZ_LEAKS": "0"}):
        assert not [f for f in KP.settled_faults(said)[1] if f.startswith(KP.QUIZ_LEAK)]


TRI = {"A": [1.2, 2.3], "B": [0, 0], "C": [5, 0], "F": [6.8, 0]}


def shape_quiz(answer_index=0):
    ext = {"at": "C", "from": "A", "to": "F", "role": "unknown"}
    figure = {"kind": "shape", "points": TRI, "polygon": "ABC", "segments": ["CF"], "angles": [{"at": "A", "role": "given"}, "B", ext]}
    from lessonforge.longform import geometry as G
    m = G.Model(figure)
    whole = G.round_to_total(m.interior(), 180)
    far = whole["A"] + whole["B"]
    return beat("03", "Extend BC to F. What is angle ACF?", figure, ["Extend BC"],
                quiz=quiz((f"{far} degrees", "70 degrees", "35 degrees"), answer_index, "What is angle ACF?")), far


def test_a_shape_quiz_keeps_the_answers_arc_but_not_its_number():
    asked, far = shape_quiz()
    original = copy.deepcopy(asked["figure"])
    made = writer.quiz_leaks(lesson(asked), log=lambda *_: None)
    angles = made["chapters"][0]["beats"][0]["figure"]["angles"]
    assert angles[2]["value"] is False and angles[2]["from"] == "A"              # ACF: the arc stays, the number waits
    assert angles[0] == {"at": "A", "role": "given"} and angles[1] == "B"        # the far corners still say their numbers
    from lessonforge.longform import shape_figure as SF
    held = SF.build(made["chapters"][0]["beats"][0]["figure"])
    shown = SF.build(original)
    assert "angle_ACF" in held.parts and "angle_ACF_value" not in held.parts and "angle_ACF_value" in shown.parts
    assert far == shown.info["angle_deg"]["ACF"]                                  # the rounding is the figure's own


def test_the_shape_hold_is_idempotent_and_leaves_an_authors_label_and_a_wrong_option_alone():
    asked, far = shape_quiz()
    once = writer.quiz_leaks(lesson(asked), log=lambda *_: None)
    assert writer.quiz_leaks(copy.deepcopy(once), log=lambda *_: None) == once
    asked2, _ = shape_quiz()
    asked2["figure"]["angles"][2]["value"] = "x"                                  # the author wrote the label
    assert writer.quiz_leaks(lesson(asked2), log=lambda *_: None)["chapters"][0]["beats"][0]["figure"]["angles"][2]["value"] == "x"
    plain, _ = shape_quiz()
    plain["quiz"]["options"] = ["99 degrees", "70 degrees", "35 degrees"]         # no option is any arc's number
    assert "value" not in str(writer.quiz_leaks(lesson(plain), log=lambda *_: None)["chapters"][0]["beats"][0]["figure"]["angles"])


def test_geometry_round_to_total_is_the_figures_rule():
    from lessonforge.longform import geometry as G
    from lessonforge.longform import shape_figure as SF
    values = {"A": 69.6, "B": 50.4, "C": 59.6}
    assert G.round_to_total(values, 180) == SF.round_to_total(values, 180)
