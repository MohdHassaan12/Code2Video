"""Straight-line motion at constant acceleration: the pure model behind the motion kit."""
import sys

import pytest

from lessonforge.longform import motion_math as M


def test_each_triple_gives_the_same_motion():
    base = M.solve({"start_speed": 2, "acceleration": 3, "duration": 4})                  # u, a, T
    assert (base.u, base.a, base.T, base.end_speed) == (2, 3, 4, 14)
    assert M.solve({"start_speed": 2, "end_speed": 14, "duration": 4}) == base            # u, v, T
    assert M.solve({"start_speed": 2, "end_speed": 14, "acceleration": 3}) == base        # u, v, a
    assert M.solve({"end_speed": 14, "acceleration": 3, "duration": 4}) == base           # v, a, T
    assert M.solve({"start_speed": 2, "end_speed": 14, "acceleration": 3, "duration": 4}) == base   # all four, consistent


def test_fewer_than_three_numbers_are_refused_and_the_message_says_what_to_give():
    for spec in ({}, {"start_speed": 1}, {"start_speed": 1, "duration": 2}, {"acceleration": None, "duration": 3, "start_speed": None}):
        with pytest.raises(M.MotionError, match="three numbers.*give THREE of start_speed, end_speed, acceleration, duration"):
            M.solve(spec)
    with pytest.raises(M.MotionError, match="needs numbers"):
        M.solve("fast")


def test_four_numbers_that_disagree_are_refused_with_the_sum():
    with pytest.raises(M.MotionError, match=r"0 \+ 2 x 6 = 12, not the 15 you gave"):
        M.solve({"start_speed": 0, "acceleration": 2, "duration": 6, "end_speed": 15})


@pytest.mark.parametrize("spec,match", [
    ({"start_speed": 0, "acceleration": 2, "duration": 0}, "duration must be more than 0"),
    ({"start_speed": 0, "acceleration": 2, "duration": -3}, "duration must be more than 0"),
    ({"start_speed": 0, "acceleration": 2, "duration": 601}, "at most 600"),
    ({"start_speed": 0, "acceleration": 2, "duration": float("nan")}, "finite"),
    ({"start_speed": 0, "acceleration": float("inf"), "duration": 2}, "finite"),
    ({"start_speed": 1e9, "acceleration": 2, "duration": 2}, "out of range"),
    ({"start_speed": 0, "acceleration": 1e4, "duration": 600}, "out of range"),          # end speed would be 6e6
    ({"start_speed": "fast", "acceleration": 2, "duration": 2}, "plain number"),
    ({"start_speed": True, "acceleration": 2, "duration": 2}, "must be a number"),
    ({"start_speed": 0, "end_speed": 10, "acceleration": 0}, "cannot be worked out"),
    ({"start_speed": 0, "end_speed": 10, "acceleration": -2}, "would take -5 s"),
    ({"start_speed": 0, "end_speed": 10, "acceleration": 0.001}, "would take 10000 s"),
])
def test_incoherent_numbers_are_refused(spec, match):
    with pytest.raises(M.MotionError, match=match):
        M.solve(spec)


def test_a_numeric_string_is_read_as_a_number():
    assert M.solve({"start_speed": "0", "acceleration": "2", "duration": " 6 "}).end_speed == 12


def test_marks_are_sorted_unique_and_inside_the_run():
    m = M.solve({"start_speed": 0, "acceleration": 2, "duration": 6, "marks": [6, 3, 3, 0]})
    assert m.marks == (0.0, 3.0, 6.0)
    for marks, match in (([7], "outside the run"), ([-1], "outside the run"), ("3", "list of times"),
                         ([1, 2, 3, 4, 5], "at most 4"), (["x"], "plain number")):
        with pytest.raises(M.MotionError, match=match):
            M.solve({"start_speed": 0, "acceleration": 2, "duration": 6, "marks": marks})


def test_speed_at_the_end_is_u_plus_aT_and_displacement_is_the_area_under_the_line():
    for u, a, T in [(0, 2, 6), (10, -2, 5), (-4, 3, 8), (5, 0, 7), (20, -4, 9), (0.5, 0.25, 3.3)]:
        m = M.solve({"start_speed": u, "acceleration": a, "duration": T})
        assert m.v(T) == pytest.approx(u + a * T, abs=1e-12)
        steps = 2000
        area = sum((m.v(i * T / steps) + m.v((i + 1) * T / steps)) / 2 * (T / steps) for i in range(steps))
        assert m.s(T) == pytest.approx(area, abs=1e-9)
        assert M.speed_at(m, 1.0) == m.v(1.0) and M.displacement_at(m, 2.0) == m.s(2.0)


def test_the_stop_time_exists_only_when_the_body_slows_to_rest_within_the_run():
    slowing = M.solve({"start_speed": 10, "acceleration": -2, "duration": 8})              # stops at 5 s, then goes back
    assert slowing.stop_time() == pytest.approx(5)
    assert M.solve({"start_speed": 10, "acceleration": -2, "duration": 5}).stop_time() == pytest.approx(5)   # exactly at the end
    assert M.solve({"start_speed": 10, "acceleration": -2, "duration": 4}).stop_time() is None               # not yet at rest
    assert M.solve({"start_speed": 0, "acceleration": 2, "duration": 6}).stop_time() is None                 # speeding up
    assert M.solve({"start_speed": 5, "acceleration": 0, "duration": 6}).stop_time() is None
    assert M.solve({"start_speed": 5, "acceleration": 1, "duration": 6}).stop_time() is None
    backwards = M.solve({"start_speed": -6, "acceleration": 2, "duration": 6})
    assert backwards.stop_time() == pytest.approx(3) and M.stop_time(backwards) == backwards.stop_time()


def test_distance_exceeds_the_displacement_after_a_reversal():
    m = M.solve({"start_speed": 10, "acceleration": -2, "duration": 8})
    assert m.s(8) == pytest.approx(16)                      # 80 - 64
    assert m.distance(8) == pytest.approx(25 + 9)           # 25 m out, 9 m back
    assert m.distance(8) > abs(m.s(8))
    assert m.distance(3) == pytest.approx(abs(m.s(3)))      # before the stop the two agree
    plain = M.solve({"start_speed": 0, "acceleration": 2, "duration": 6})
    assert plain.distance(6) == plain.s(6) == pytest.approx(36) and M.distance_at(plain, 3) == pytest.approx(9)


@pytest.mark.parametrize("spec,expected", [
    ({"start_speed": 0, "acceleration": 2, "duration": 6}, "speeding up"),
    ({"start_speed": 10, "acceleration": -2, "duration": 4}, "slowing down"),
    ({"start_speed": 10, "acceleration": -2, "duration": 5}, "slowing down"),         # comes to rest exactly at the end
    ({"start_speed": 5, "acceleration": 0, "duration": 6}, "steady"),
    ({"start_speed": 10, "acceleration": -2, "duration": 8}, "reverses"),
    ({"start_speed": -4, "acceleration": -2, "duration": 4}, "speeding up"),          # backwards and faster
    ({"start_speed": -4, "acceleration": 1, "duration": 3}, "slowing down"),          # backwards and slower
])
def test_phase_of_the_run(spec, expected):
    m = M.solve(spec)
    assert m.phase() == expected == M.phase(m)


def test_phase_of_part_of_the_run():
    m = M.solve({"start_speed": 10, "acceleration": -2, "duration": 8})
    assert m.phase(0, 4) == "slowing down" and m.phase(5, 8) == "speeding up" and m.phase(0, 8) == "reverses"
    assert m.phase(2, 2) == "steady"


def test_trends_say_what_the_speed_does_somewhere_in_the_run():
    assert M.solve({"start_speed": 0, "acceleration": 2, "duration": 6}).trends() == {"speeding up"}
    assert M.solve({"start_speed": 10, "acceleration": -2, "duration": 8}).trends() == {"slowing down", "speeding up", "reverses"}
    assert M.solve({"start_speed": 5, "acceleration": 0, "duration": 6}).trends() == {"steady"}


def test_facts_and_shown_carry_every_number_the_screen_may_say():
    m = M.solve({"start_speed": 0, "acceleration": 2, "duration": 6, "marks": [3, 6]})
    facts = m.facts()
    assert facts["start speed"] == 0 and facts["end speed"] == 12 and facts["acceleration"] == 2
    assert facts["duration"] == 6 and facts["displacement"] == 36 and facts["distance"] == 36
    assert facts["stop time"] is None and facts["speed at 3"] == 6 and facts["speed at 6"] == 12
    assert m.shown() == frozenset({0.0, 12.0, 2.0, 6.0, 3.0})
    assert m.notes == ()


def test_the_graph_is_drawn_only_from_the_model():
    m = M.solve({"start_speed": 2, "acceleration": -0.5, "duration": 8, "marks": [4, 8]})
    p = M.graph_params(m)
    assert p["functions"] == ["2 + (-0.5)*x"] and p["x_range"] == [0, 8]
    assert p["x_label"] == "time (s)" and p["labels"] == {"curve0": "v = 2 - 0.5t"}
    assert p["y_label"] == "velocity (m/s)"                                   # it ends below zero: the body goes back
    assert [(q["x"], q["y"]) for q in p["points"]] == [(4.0, 0.0), (8.0, -2.0)]
    lo, hi = p["y_range"]
    assert lo < -2 and hi > 2 and all(lo <= q["y"] <= hi for q in p["points"])
    start = M.solve({"start_speed": 0, "acceleration": 2, "duration": 6})
    assert M.graph_params(start)["y_label"] == "speed (m/s)"
    assert M.graph_params(start)["labels"] == {"curve0": "v = 2t"} and M.graph_params(start)["points"] == []
    assert M.graph_params(M.solve({"start_speed": 5, "acceleration": 0, "duration": 6}))["labels"] == {"curve0": "v = 5"}
    assert M.graph_params(start, marks=[3])["points"][0]["label"] == "3 s, 6 m/s"


def test_the_graph_function_reads_back_as_the_same_line():
    pytest.importorskip("numpy")
    from lessonforge.longform import figure_math
    for u, a in [(0, 2), (10, -2), (-3, 0.5), (4, 0)]:
        m = M.solve({"start_speed": u, "acceleration": a, "duration": 6})
        f = figure_math.graph_function(M.graph_params(m)["functions"][0])
        for t in (0, 1.5, 6):
            assert float(f([t])[0]) == pytest.approx(m.v(t), abs=1e-6)


def test_the_module_is_stdlib_only():
    import ast
    import pathlib
    tree = ast.parse(pathlib.Path(M.__file__).read_text())
    roots = {n.module.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module and not n.level}
    roots |= {a.name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    assert not [n for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.level], "no package-relative import"
    assert roots <= set(sys.stdlib_module_names) | {"__future__"}, roots
