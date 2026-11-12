"""A model writes geometry as points and gaps; code fills the values and catches every claim the points deny."""
import copy
import json

from lessonforge.harness import pack, shapes, writer

ARROW = {"points": {"A": [0, 0], "B": [4.4, 1.6], "C": [0, 3.2], "D": [1.4, 1.6]}, "polygon": "ABCD", "is": ["concave"]}
BOX = {"points": {"A": [0, 0], "B": [4, 0.3], "C": [4.6, 3.2], "D": [0.4, 2.8]}, "polygon": "ABCD", "is": ["convex"]}


def _lesson(beats, shape_table=None):
    return {"title": "t", "shapes": shape_table or {"arrow": ARROW, "box": BOX},
            "chapters": [{"title": "ONE", "learning_goal": "g", "role": "explain", "beats": beats}]}


def _beat(narration, figure, steps=None, quiz=None):
    beat = {"narration": narration, "figure": figure, "steps": steps or [{"say": narration.split(".")[0][:30], "show": "x"}]}
    if quiz:
        beat["quiz"] = quiz
    return beat


def test_gaps_are_filled_from_the_points_and_add_up():
    beat = _beat("The angle at D is {angle D} degrees. A, B and C add to {angle A + angle B + angle C}.",
                 {"kind": "shape", "use": "arrow", "angles": ["D"]},
                 steps=[{"say": "The angle at D", "show": "∠D = {angle D}°"}])
    filled, issues = shapes.settle(_lesson([beat]))
    assert not issues, issues
    b = filled["chapters"][0]["beats"][0]
    d = int(b["steps"][0]["show"].split("= ")[1].rstrip("°"))
    assert d > 180 and f"is {d} degrees" in b["narration"]
    abc = int(b["narration"].split("add to ")[1].rstrip("."))
    assert abc + d == 360                       # the shown angles add up exactly, as the picture writes them
    assert b["figure"]["points"] == ARROW["points"] and b["figure"]["frame"]


def test_a_typed_angle_the_picture_does_not_show_is_a_fault():
    beat = _beat("The angle at D is 230 degrees.", {"kind": "shape", "use": "arrow", "angles": ["D"]})
    _, issues = shapes.settle(_lesson([beat]))
    assert any("230 degrees" in i for i in issues)
    beat = _beat("The angle at D is two hundred and thirty degrees.", {"kind": "shape", "use": "arrow", "angles": ["D"]})
    _, issues = shapes.settle(_lesson([beat]))
    assert any("230 degrees" in i for i in issues)


def test_a_claim_the_points_deny_is_a_fault_and_a_true_one_is_not():
    _, issues = shapes.settle(_lesson([_beat("So ABCD is convex.", {"kind": "shape", "use": "arrow"})]))
    assert any("ABCD is convex" in i for i in issues)
    _, issues = shapes.settle(_lesson([_beat("So ABCD is concave.", {"kind": "shape", "use": "arrow"})]))
    assert not issues
    _, issues = shapes.settle(_lesson([_beat("It is not convex.", {"kind": "shape", "use": "arrow"})]))
    assert not issues


def test_a_shape_that_is_not_what_the_lesson_needs_is_a_fault():
    _, issues = shapes.settle(_lesson([], {"para": {"points": {"A": [0, 0], "B": [4, 0], "C": [5, 3], "D": [1, 2.9]},
                                                    "polygon": "ABCD", "is": ["parallelogram"]}}))
    assert any("must be parallelogram" in i for i in issues)


def test_on_a_segment_puts_the_moving_corner_exactly_on_it():
    fig = {"kind": "shape", "use": "box", "move": {"D": [[1.5, 2.2], "on AC", [3.0, 1.4]]}, "verdict": True}
    beat = _beat("Before the line it is convex. On the line it has collapsed. Past it, concave.", fig)
    filled, issues = shapes.settle(_lesson([beat]))
    assert not issues, issues
    mid = filled["chapters"][0]["beats"][0]["figure"]["move"]["D"][1]
    from lessonforge.longform import geometry as G
    assert G.collinear(BOX["points"]["A"], mid, BOX["points"]["C"])
    # without the exact way-point the words promise a collapse that never happens
    fig2 = {"kind": "shape", "use": "box", "move": {"D": [[1.5, 2.2], [2.4, 1.6], [3.0, 1.4]]}}
    _, issues = shapes.settle(_lesson([_beat("On the line it has collapsed.", fig2)]))
    assert any("collapsed" in i for i in issues)


def test_options_that_come_out_equal_are_a_fault():
    quiz = {"question": "What is angle D?", "options": ["{angle D}°", "{360 - angle A - angle B - angle C}°"],
            "answer_index": 0, "why": ["a", "b"]}
    _, issues = shapes.settle(_lesson([_beat("What is angle D?", {"kind": "shape", "use": "arrow"}, quiz=quiz)]))
    assert any("same once filled" in i for i in issues)


def test_the_hand_made_units_pass_the_claim_checks():
    """The nine hand-made quadrilateral lessons are right; the checker must not call them wrong (their typed
    practice numbers are the only findings, and those are what a gap is for)."""
    import importlib.util
    import pathlib
    import sys
    here = pathlib.Path(__file__).resolve().parents[2] / "examples" / "quadrilaterals"
    sys.path.insert(0, str(here))
    try:
        for unit in (1, 2, 4, 6, 7, 8):
            spec = importlib.util.spec_from_file_location(f"unit{unit}", here / f"unit{unit}.py")
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            _, issues = shapes.settle(mod.L)
            assert not issues, (unit, issues)
    finally:
        sys.path.remove(str(here))


PACK = """# Rules

# Mathematical corrections and safeguards

- Angle sum is 360.

# Revised scripts
# 3. Convex versus non-convex

## A — notice the dent

Narration: "One corner is pushed inward."

## B — angle sum

Narration: "The angles add to 360."

# Validation checklist

- nothing
"""


def test_pack_units_and_rules_are_read():
    units = pack.units(PACK)
    assert [u["number"] for u in units] == [3]
    assert [s["title"] for s in units[0]["sections"]] == ["A — notice the dent", "B — angle sum"]
    assert "Validation" not in units[0]["text"]
    assert "360" in pack.rules(PACK)


def test_the_pack_writer_repairs_what_code_finds():
    bad = _lesson([
        _beat("Here is a dent. ABCD is convex.", {"kind": "shape", "use": "arrow"},
              steps=[{"say": "Here is a dent", "show": "A dent"}]),
        _beat("The angle at D is {angle D} degrees.", {"kind": "shape", "use": "arrow", "angles": ["D"]},
              steps=[{"say": "The angle at D", "show": "∠D = {angle D}°"}])])
    good = copy.deepcopy(bad)
    good["chapters"][0]["beats"][0]["narration"] = "Here is a dent. ABCD is concave."
    asked = []

    def llm(prompt, system):
        asked.append(prompt)
        return good if len(asked) > 1 else bad
    lesson = pack.write_unit(pack.units(PACK)[0], pack.rules(PACK), llm, log=lambda *_: None)
    assert len(asked) == 2 and "ABCD is convex" in asked[1]
    assert lesson["geometry_check"]["faults_by_round"][-1] == 0 and not lesson["geometry_check"]["faults_left"]
    assert lesson["generated_by"] == pack.GENERATED_BY
    said = lesson["chapters"][0]["beats"][1]["narration"]
    assert "{" not in said and "degrees" in said and not any(ch.isdigit() for ch in said)   # spoken as words


def test_writer_offers_the_shape_figure():
    assert "shape" in writer.FIGURE_KINDS and '"kind":"shape"' in writer.SYSTEM


def test_the_pack_writer_stops_when_a_repair_returns_the_same_faults():
    bad = _lesson([_beat("Here is a dent. ABCD is convex.", {"kind": "shape", "use": "arrow"},
                         steps=[{"say": "Here is a dent", "show": "A dent"}])])
    asked = []

    def llm(prompt, system):
        asked.append(prompt)
        return copy.deepcopy(bad)        # the "repair" changes nothing
    lesson = pack.write_unit(pack.units(PACK)[0], pack.rules(PACK), llm, log=lambda *_: None)
    assert len(asked) == 2               # one draft, one repair; not MAX_REPAIRS of the same answer
    assert lesson["geometry_check"]["faults_left"]
