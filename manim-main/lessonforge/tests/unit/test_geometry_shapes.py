"""The geometry model behind the ``shape`` figure, its voice-led hints, and how point names are spoken.

Each case is a fault the quadrilaterals pack named or a first film showed: a picture must never say what its
coordinates do not (a tick on unequal sides, "convex" on a dented shape), and the voice must say "A" as a letter."""
import pytest

from lessonforge.longform import geometry as G
from lessonforge.longform import shape_hints
from lessonforge.longform.speech import letter_names

SQ = {"A": [0, 0], "B": [4, 0], "C": [4, 4], "D": [0, 4]}


def test_status_tells_convex_concave_crossed_and_collapsed():
    A, B, C = (0, 0), (4, 0), (1.5, 3)
    assert G.status([A, B, C, (-0.6, 2.2)])["kind"] == "convex"
    dent = G.status([A, B, C, (1.8, 1.0)], list("ABCD"))
    assert dent["kind"] == "concave" and dent["reflex"] == ["D"]
    crossed = G.status([A, B, C, (2.0, -1.2)], list("ABCD"))
    assert crossed["kind"] == "crossed" and crossed["cross"]
    flat = G.status([(0, 0), (2.5, 0), (5, 0), (2, 3)], list("ABCD"))
    assert flat["kind"] == "degenerate" and flat["collinear"] == ["B"]


def test_interior_angles_count_the_reflex_angle_and_add_to_360():
    poly = [(0, 0), (4.4, 1.6), (0, 3.2), (1.4, 1.6)]
    angles = G.interior_angles(poly)
    assert max(angles) > 180
    assert sum(angles) == pytest.approx(360)


def test_marks_are_drawn_only_where_the_coordinates_bear_them_out():
    kite = {"A": [0, 1.5], "B": [2, 0], "C": [6, 1.5], "D": [2, 3]}
    m = G.Model({"points": kite, "polygon": "ABCD", "equal": [["AB", "CD"], ["AB", "DA"]]})
    kept = m.checked_marks("equal")
    assert ["AB", "DA"] in [list(g) for g in kept] and not any("CD" in g and "AB" in g for g in kept)


def test_parallelogram_tests_need_the_same_pair_equal_and_parallel():
    trap = {"A": [0, 0], "B": [5, 0], "C": [3.8, 2.4], "D": [1.2, 2.4]}
    assert not any(G.parallelogram_tests(G.Model({"points": trap, "polygon": "ABCD"})).values())
    par = {"A": [0, 0], "B": [4.5, 0], "C": [6, 2.8], "D": [1.5, 2.8]}
    assert all(G.parallelogram_tests(G.Model({"points": par, "polygon": "ABCD"})).values())


def test_hints_read_point_names_by_their_case():
    info = {"segments": {"AB": "AB", "BC": "BC", "CD": "CD", "DA": "DA"}, "angles": {"C": "angle_C"},
            "points": set("ABCD"), "words": {"A": "A", "B": "B"}, "polygon": "ABCD", "sides": ["AB", "BC", "CD", "DA"]}
    sentence = {"text": "A diagonal is not side AB. Angle C is here.", "start": 0.0, "duration": 4.0}
    events = shape_hints.plan([sentence], info)
    kinds = [e["kind"] for e in events]
    assert "segment" in kinds and "angle" in kinds
    assert not any(e["kind"] == "point" and "A" in e["parts"] for e in events)     # the article is not vertex A


def test_point_names_are_spoken_as_letters():
    assert "Eigh" in letter_names("Here is ABCD.")
    assert letter_names("A diagonal joins two corners.").startswith("A diagonal")
    assert "Eigh" in letter_names("Join A to C.")


def test_a_point_inside_a_side_names_itself_off_every_line():
    # Q is the middle of side RP and of AC, and PQ is drawn too: PQ listed the ray QP twice, the zero gap read as a
    # full turn and "Q" was put on the line PR (unit 6 of the quadrilaterals lessons).
    from lessonforge.longform import shape_figure as SF
    pts = {"A": [1.8, 3.8], "B": [0, 0], "C": [6, 0], "P": [0.9, 1.9], "Q": [3.9, 1.9], "R": [6.9, 1.9]}
    fig = SF.build({"kind": "shape", "points": pts, "polygon": "PBCR", "segments": ["AP", "AC", "PQ"]})
    label, dot = fig.parts["Q"].get_center(), fig.parts["dot_Q"].get_center()
    assert abs(label[1] - dot[1]) > 0.1                       # not on the horizontal line through Q


def test_times_and_divide_signs_survive_in_a_formula():
    from lessonforge.longform import runtime
    for char in "×÷":
        assert char in runtime._SILENT_GLYPHS


def test_a_moving_corner_rests_on_its_waypoint_not_a_hair_before():
    from lessonforge.longform import shape_figure as SF
    spec = {"points": {"A": [0, 0], "B": [4, 0], "C": [4, 4], "D": [0, 4]}, "move": {"D": [[2, 2], [3, 1]]}}
    resting = SF.at_alpha(spec, (0 + .999) / 2)                # stage 1 of 2 over, as the renderer holds it
    assert resting["points"]["D"] == [2.0, 2.0]


def test_a_named_triangle_of_a_proof_brightens_and_does_not_grow():
    from lessonforge.longform import shape_figure as SF
    pts = {"A": [0, 0], "B": [4.5, 0], "C": [6, 2.8], "D": [1.5, 2.8]}
    fig = SF.build({"kind": "shape", "points": pts, "polygon": "ABCD", "fills": [{"poly": "ABC"}]})
    shade = fig.parts["fill_ABC"]
    assert shade.hint_grow == 0.0 and shade.lights_fill
