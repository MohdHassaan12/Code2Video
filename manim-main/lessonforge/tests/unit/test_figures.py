"""The figure inventory draws from numbers and never raises on bad input."""
import pytest

manim = pytest.importorskip("manim")
from lessonforge.longform import figures  # noqa: E402


def test_right_triangle_marks_the_unknown_and_fits():
    g = figures.build({"kind": "right_triangle", "a": 3, "b": 4, "labels": {"a": "3 m", "b": "4 m", "c": "?"},
                       "unknown": "c"})
    assert g is not None and g.width > 1 and g.height > 1
    g2 = figures.build({"kind": "right_triangle", "params": {"a": 3, "b": 4, "squares": True, "result": "c"}})
    assert g2 is not None and {"square_a", "square_b", "square_c"} <= set(g2.parts)
    assert {"a", "b", "c", "c_label", "right_angle"} <= set(g.parts) and g.kind == "right_triangle"


def test_number_line_and_bars_build():
    nl = figures.build({"kind": "number_line", "min": -5, "max": 5,
                        "points": [{"x": -3, "label": "-3", "role": "given"}, {"x": 3, "role": "result"}],
                        "arrow": {"from": -3, "to": 3, "label": "times -1"}})
    assert nl is not None and nl.width > 4
    b = figures.build({"kind": "bars", "parts": [{"label": "1/2", "n": 1, "d": 2}, {"label": "1/3", "n": 1, "d": 3}]})
    assert b is not None and {"bar0", "bar1", "bar0_label"} <= set(b.parts)


def test_unknown_kind_and_garbage_return_none():
    assert figures.build({"kind": "pie"}) is None
    assert figures.build("right_triangle") is None
    assert figures.build({"kind": "number_line", "min": "x", "max": None, "points": "nope"}) is not None  # defaults


def test_triangle_is_drawn_from_its_labelled_numbers_and_inconsistencies_are_reported():
    from lessonforge.longform import figure_math as fm
    assert fm.number_in("3 m") == 3 and fm.number_in("\\text{hypotenuse} = 4\\text{ m}") == 4
    assert fm.number_in("ground") is None and fm.number_in("?") is None and fm.is_angle_label("\\theta")
    # the tester's lesson, beat 28: legs requested 3 and 4, but labelled 3 m (leg) and 4 m (hypotenuse)
    got = fm.resolve_right_triangle({"a": 3, "b": 4, "labels": {"a": "ground", "b": "3 m", "c": "4 m"}})
    assert got["source"] == "labels" and got["b"] == 3 and got["c"] == 4 and round(got["a"], 2) == 2.65
    assert any("drawn from the labels" in i for i in got["issues"])
    # consistent request: nothing to report, hypotenuse may be given instead of a leg
    assert fm.resolve_right_triangle({"a": 2.65, "b": 3, "labels": {"a": "ground", "b": "3 m", "c": "4 m"}})["issues"] == []
    assert round(fm.resolve_right_triangle({"b": 3, "c": 5})["a"], 6) == 4
    # three labels that cannot be a right triangle is an error only a person can fix
    bad = fm.figure_issues({"kind": "right_triangle", "a": 3, "b": 4, "labels": {"a": "3", "b": "4", "c": "6"}})
    assert any("do not make a right triangle" in i for i in bad)
    assert fm.figure_issues({"kind": "bars", "parts": [{"label": "2/5", "n": 1, "d": 2}]}) == ["a bar is labelled 2/5 but drawn as 1/2"]


def test_latex_labels_are_typeset_and_an_angle_can_be_marked():
    from manim import MathTex
    g = figures.build({"kind": "right_triangle", "b": 3, "c": 4, "angle": "a", "angle_label": "\\theta",
                       "labels": {"a": "\\text{adjacent}", "b": "\\text{opposite} = 3\\text{ m}", "c": "\\text{hypotenuse} = 4\\text{ m}"}})
    assert g is not None
    assert all(isinstance(g.parts[k], MathTex) for k in ("a_label", "b_label", "c_label"))   # typeset, not raw text
    assert "angle" in g.parts
    theta_side = figures.build({"kind": "right_triangle", "a": 2.65, "b": 3, "labels": {"a": "\\theta", "b": "3 m", "c": "4 m"}})
    assert "angle" in theta_side.parts and "a_label" not in theta_side.parts   # θ on a side becomes an angle mark


def test_every_kind_builds_with_named_parts_and_a_construction_order():
    specs = {
        "right_triangle": {"kind": "right_triangle", "a": 3, "b": 4, "squares": True, "unknown": "b"},
        "number_line": {"kind": "number_line", "points": [{"x": 2}], "arrow": {"from": 0, "to": 2, "label": "+2"}},
        "bars": {"kind": "bars", "parts": [{"n": 1, "d": 2}, {"n": 0, "d": 3}]},
        "circle": {"kind": "circle", "r": 7, "labels": {"radius": "7 cm", "diameter": "14 cm", "circumference": "C"}, "unknown": "area"},
        "rectangle": {"kind": "rectangle", "w": 6, "h": 4, "grid": True, "unknown": "area"},
        "graph": {"kind": "graph", "functions": ["2*x - 1", "-x + 5"], "x_range": [-2, 5]},
        "reaction": {"kind": "reaction", "equation": "2H2 + O2 -> 2H2O"},
        "shape": {"kind": "shape", "points": {"A": [0, 0], "B": [4, 0], "C": [5, 3], "D": [1, 3]}, "polygon": "ABCD",
                  "segments": [{"ends": "AC", "dashed": True}], "angles": ["A", "C"], "verdict": True},
    }
    # "scene" is model-written, "diagram" is picture layers and "picture" is one image file: each is tested on
    # its own (test_diagrams.py, test_runtime_layout.py); "float" moves like a scene (test_float_and_stale.py)
    assert set(specs) | {"scene", "diagram", "picture", "float"} == set(figures.KINDS)
    for kind, spec in specs.items():
        fig = figures.build(spec)
        assert fig is not None and fig.kind == kind and fig.parts and fig.build, kind
        assert figures.construct_animation(fig, run_time=1.0) is not None
    cut = figures.build({"kind": "circle", "sectors": 16, "rearranged": True, "labels": {"base": "pi r", "height": "r"}})
    assert len(cut.parts["sectors"]) == 16 and cut.parts["sectors"].width <= 5.7
    # the square on the UNKNOWN side carries "?", the others carry their value
    sq = figures.build(specs["right_triangle"])
    from manim import Text
    assert isinstance(sq.parts["square_b"][1], Text) and not isinstance(sq.parts["square_c"][1], Text)


SCENE_MODULE = '''
def build(width, height):
    flask = RoundedRectangle(width=width * 0.5, height=height * 0.8, corner_radius=0.3, color=WHITE)
    dots = VGroup(*[Dot(flask.get_center() + RIGHT * (i - 1.5) * 0.5, color=ORANGE) for i in range(4)])
    return VGroup(flask, dots)


def animate(group, run_time):
    dots = group[1]
    return UpdateFromAlphaFunc(dots, lambda m, a: m.set_y(group[0].get_center()[1] + 0.8 * np.sin(2 * PI * a)), run_time=run_time)
'''


def test_a_generated_scene_loads_with_its_animator_and_can_be_stepped_by_hand(tmp_path):
    path = tmp_path / "sim_flask.py"
    path.write_text(SCENE_MODULE)
    fig = figures.build({"kind": "scene", "describe": "a flask with moving molecules", "module": str(path)})
    assert fig is not None and fig.kind == "scene" and fig.width <= 6.1 and fig.height <= 4.1
    assert callable(fig.animator) and fig.inner is fig.parts["scene"]
    # stepped exactly as the runtime (and the verifier) step it
    animation = fig.animator(fig.inner, 3.0)
    animation.begin()
    y0 = fig.inner[1].get_y()
    animation.interpolate(0.25)
    assert abs(fig.inner[1].get_y() - y0) > 0.2          # something really moved (the rate function eases in)
    animation.interpolate(1.0)
    animation.finish()
    # a missing or broken module is no figure at all, never a crash
    assert figures.build({"kind": "scene", "module": str(tmp_path / "nope.py")}) is None
    (tmp_path / "bad.py").write_text("def build(w, h):\n    return 1 / 0\n")
    assert figures.build({"kind": "scene", "module": str(tmp_path / "bad.py")}) is None


def test_a_graph_computes_what_it_shows_and_runs_nothing_but_arithmetic():
    from lessonforge.longform import figure_math as fm
    facts = fm.graph_facts(["(x**2 - 1)/(x - 1)", "2*x - 1"], (-3, 4))
    assert facts["holes"] == [{"curve": 0, "x": 1.0, "y": 2.0}]           # the hole is found, not taken on trust
    assert facts["meeting_points"] == [{"x": 2.0, "y": 3.0}]
    assert fm.graph_facts(["1/(x - 2)"], (-2, 6))["asymptotes"] == [2.0]
    assert fm.graph_facts(["x^2", "2x + 3"], (-3, 5))["meeting_points"] == [{"x": -1.0, "y": 1.0}, {"x": 3.0, "y": 9.0}]
    for bad in ("__import__('os')", "x.__class__", "open('f')", "(lambda: 1)()", "[x for x in ()]"):
        assert fm.graph_function(bad) is None, bad
    fig = figures.build({"kind": "graph", "functions": ["1/(x - 2)"], "x_range": [-2, 6], "points": [{"x": 3, "label": "(3, 1)"}]})
    assert {"axes", "curve0", "asym0", "point0", "point0_label"} <= set(fig.parts)


def test_a_short_number_line_gets_ticks_it_can_number_and_close_labels_do_not_sit_on_each_other():
    # seen 2026-10-19 (a lesson on 0.999…): a line from 0.9 to 1 had one tick, numbered "1" at 0.9, and the
    # labels 0.99, 0.999 and 1 printed on top of one another
    from lessonforge.longform import figures as F
    assert F.tick_step(0.9, 1) == (0.02, 2) and F.tick_step(-5, 5) == (1, 0) and F.tick_step(0, 100) == (10, 0)
    fig = F.number_line({"min": 0.9, "max": 1, "points": [{"x": x, "label": str(x)} for x in (0.9, 0.99, 0.999, 1)]})
    labels = [fig.parts[f"point{i}_label"] for i in range(4)]
    for i, a in enumerate(labels):
        for b in labels[i + 1:]:
            apart = a.get_right()[0] < b.get_left()[0] or b.get_right()[0] < a.get_left()[0] \
                or a.get_bottom()[1] > b.get_top()[1] or b.get_bottom()[1] > a.get_top()[1]
            assert apart


def test_graph_point_names_never_lie_on_each_other():
    """Two points at the same height put their names one across the other (an Ohm's law graph, 2026-10-16)."""
    fig = figures.build({"kind": "graph", "functions": ["2*x", "5*x"], "x_range": [0, 12],
                         "points": [{"x": 10, "label": "Toaster (Low R)"}, {"x": 4, "label": "Water Heater (High R)"}]})
    names = [m for n, m in fig.parts.items() if n.endswith("_label")]
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            (ax0, ay0, _), (ax1, ay1, _) = a.get_corner([-1, -1, 0]), a.get_corner([1, 1, 0])
            (bx0, by0, _), (bx1, by1, _) = b.get_corner([-1, -1, 0]), b.get_corner([1, 1, 0])
            assert ax1 < bx0 or bx1 < ax0 or ay1 < by0 or by1 < ay0


def test_number_line_ticks_are_numbers_a_reader_counts_in():
    """0 to 110 was ticked 0, 11, 22 … 99, and "A 100 m" stood over the 99 (2026-10-20)."""
    fig = figures.build({"kind": "number_line", "min": 0, "max": 110, "points": [{"x": 100, "label": "A"}]})
    ticks = [float(n.get_value()) for n in fig.parts["line"].numbers]
    assert ticks[:3] == [0.0, 10.0, 20.0] and 100.0 in ticks


def test_a_graph_hides_where_its_lines_meet_until_asked():
    lines = {"kind": "graph", "functions": ["5 - x", "x - 1"], "x_range": [0, 5]}
    assert "meet0" in figures.build(lines).parts
    assert "meet0" not in figures.build({**lines, "meet": False}).parts


def test_a_reaction_draws_what_its_equation_says_and_nothing_else():
    """A model-written scene labelled two waters "H2O2" in a lesson about that very mistake (2026-10-20). The
    reaction figure reads the equation once and draws the balls, formulas and counts from that reading."""
    from lessonforge.longform import figure_math
    from manim import Circle, Text
    fig = figures.build({"kind": "reaction", "equation": "2H2 + O2 -> 2H2O"})
    balls = lambda part: len([m for m in part.get_family() if isinstance(m, Circle)])  # noqa: E731
    assert balls(fig.parts["mol0"]) == 4 and balls(fig.parts["mol1"]) == 2 and balls(fig.parts["mol2"]) == 6
    counts = [t.text for t in fig.parts["right_count"].get_family() if isinstance(t, Text)]
    assert counts == ["after", "4", "2"]                # a table row: "after", then H and O in the head's order
    assert [t.text for t in fig.parts["verdict"].get_family() if isinstance(t, Text)] == ["balanced"]
    # side by side, start -> product: wider than tall, so it fills the frame's wide picture box
    assert fig.width > fig.height
    # an unknown coefficient is drawn and counted as one; the try-it count shows what does not match yet
    left = figure_math.atom_counts(figure_math.parse_equation("? N2 + ? H2 -> ? NH3")["left"])
    assert left == {"N": 2, "H": 2}
    assert figure_math.parse_equation("Ca(OH)2 + 2HCl -> CaCl2 + 2H2O") and \
        figure_math.is_balanced(figure_math.parse_equation("Ca(OH)2 + 2HCl -> CaCl2 + 2H2O"))
    assert not figure_math.is_balanced(figure_math.parse_equation(r"\mathrm{H_2} + \mathrm{O_2} \rightarrow \mathrm{H_2O}"))
    # an equation code cannot read is no picture at all, never a guess
    from lessonforge.harness import writer
    assert writer.reaction_figure({"kind": "reaction", "equation": "water turns to ice"}) is None
    assert writer.figure_numbers({"kind": "reaction", "equation": "2Mg + O2 -> 2MgO"}) == {"2"}


def test_a_chemical_equation_in_a_formula_step_is_set_upright():
    """"2H_2 + O_2 -> 2H_2O" drew H and O in maths italics, as if they were unknowns (2026-10-20)."""
    from lessonforge.harness import writer
    up = lambda s: writer.mathify(writer.one_line_math(s))  # noqa: E731
    assert up(r"2H_2 + O_2 \rightarrow 2H_2O") == r"2\,\mathrm{H_{2}} + \mathrm{O_{2}} \rightarrow 2\,\mathrm{H_{2}O}"
    assert r"\mathrm{H}" in up(r"4\,H + 2\,O = 4\,H + 2\,O")
    for physics in ("V = IR", "I + R = V", "x + y = z", r"A = l \times b", "E = mc^2"):
        assert r"\mathrm" not in up(physics), physics
