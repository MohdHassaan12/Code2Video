"""The code-drawn figure agrees with what the voice says (writer.figures_and_words; trig + fractions remakes, 2026-10-17)."""
from lessonforge.harness import writer


def tri(a, b, c="?"):
    return {"kind": "right_triangle", "a": a, "b": b, "labels": {"a": f"{a} m", "b": f"{b} m", "c": c}, "unknown": "c"}


def bars(*parts):
    return {"kind": "bars", "parts": [{"label": f"{n}/{d}", "n": n, "d": d} for n, d in parts]}


def lesson(*beats):
    return {"chapters": [{"beats": [dict(b, id=f"{i + 1:02d}") for i, b in enumerate(beats)]}]}


def beats_of(l):
    return l["chapters"][0]["beats"]


def test_a_beat_that_speaks_the_next_figures_numbers_shows_that_figure():
    l = lesson({"narration": "Our triangle. Double every side: base six, perpendicular eight. What happens?", "figure": tri(3, 4)},
               {"narration": "It stays the same.", "figure": tri(6, 8)})
    writer.figures_follow_words(l, log=lambda *_: None)
    assert beats_of(l)[0]["figure"]["a"] == 6


def test_a_beat_that_only_asks_about_the_next_case_keeps_its_figure():
    # the next bars would show the answer to "two fifths or two ninths?"
    l = lesson({"narration": "Four ninths beats two ninths. Some say two ninths beats two fifths. Two fifths or two ninths?",
                "figure": bars((4, 9), (2, 9))},
               {"narration": "Two fifths is greater.", "figure": bars((2, 5), (2, 9))})
    writer.figures_follow_words(l, log=lambda *_: None)
    assert beats_of(l)[0]["figure"]["parts"][0]["d"] == 9


def test_another_kind_or_one_number_is_not_enough():
    l = lesson({"narration": "Base six.", "figure": tri(3, 4)}, {"narration": "x", "figure": tri(6, 8)},
               {"narration": "Base twelve, perpendicular five.", "figure": tri(6, 8)},
               {"narration": "y", "figure": bars((12, 5))})
    writer.figures_follow_words(l, log=lambda *_: None)
    assert beats_of(l)[0]["figure"]["a"] == 3 and beats_of(l)[2]["figure"]["kind"] == "right_triangle"


def test_the_unknown_side_is_found_where_the_voice_says_it_and_stays_found():
    l = lesson({"narration": "Find the longest side.", "figure": tri(3, 4)},
               {"narration": "Three squared plus four squared is twenty-five, so the longest side is five. Next idea.",
                "steps": [{"say": "Three squared", "show": "3^2+4^2=25", "kind": "math"},
                          {"say": "Next idea", "show": "Next", "kind": "point"}],
                "figure": tri(3, 4)},
               {"narration": "Tan is four over three.", "figure": tri(3, 4)})
    writer.found_unknowns(l, log=lambda *_: None)
    b = beats_of(l)
    assert b[0]["figure"]["labels"]["c"] == "?"                         # not said yet
    added = [s for s in b[1]["steps"] if s.get("focus") == "c"]
    assert added and added[0]["show"] == "c = 5\\,\\text{m}" and added[0]["say"] in b[1]["narration"]
    assert [s["show"] for s in b[1]["steps"]].index("c = 5\\,\\text{m}") == 1    # in the order it is said
    assert b[2]["figure"]["labels"]["c"] == "5 m"


def test_a_line_that_ends_on_the_side_gets_the_focus_instead_of_a_new_line():
    l = lesson({"narration": "So the hypotenuse is thirteen.",
                "steps": [{"say": "So the", "show": "c = 13", "kind": "math"}], "figure": tri(12, 5)})
    writer.found_unknowns(l, log=lambda *_: None)
    steps = beats_of(l)[0]["steps"]
    assert len(steps) == 1 and steps[0]["focus"] == "c"


def test_a_number_said_about_something_else_finds_nothing():
    l = lesson({"narration": "Five over twelve is tan theta.", "figure": tri(12, 5)},
               {"narration": "Base three, perpendicular four, five apples.", "figure": tri(3, 4)})
    writer.found_unknowns(l, log=lambda *_: None)
    assert all(b["figure"]["labels"]["c"] == "?" and not b.get("steps") for b in beats_of(l))


def test_a_scaled_copy_carries_the_triangle_it_was_scaled_from():
    l = lesson({"narration": "a", "figure": tri(3, 4)}, {"narration": "b", "figure": tri(6, 8)},
               {"narration": "c", "figure": tri(12, 5)})
    writer.scaled_copies(l, log=lambda *_: None)
    b = beats_of(l)
    assert b[1]["figure"]["ghost"] == {"a": 3, "b": 4}
    assert "ghost" not in b[0]["figure"] and "ghost" not in b[2]["figure"]


def test_figure_numbers():
    assert writer.figure_numbers(tri(3, 4)) == {"3", "4", "5"}
    assert writer.figure_numbers(tri(2, 3)) == {"2", "3"}
    assert writer.figure_numbers(bars((3, 10), (7, 10))) == {"3", "7", "10"}
    assert writer.figure_numbers({"kind": "diagram"}) == set()


def test_a_unit_after_a_number_is_set_upright():
    assert writer.mathify("c = 13 m") == "c = 13\\,\\text{m}"
    assert writer.mathify("P = 20/0.05 = 400N/m^2") == "P = 20/0.05 = 400\\,\\text{N/m}^2"
    assert writer.mathify("v = 3 m/s") == "v = 3\\,\\text{m/s}"
    # a letter that is a variable stays a variable
    for line in ("2A + B", "3m = x", "F = 3 ma", "y = 2 m x", "2x + 3 = 11"):
        assert writer.mathify(line) == line
