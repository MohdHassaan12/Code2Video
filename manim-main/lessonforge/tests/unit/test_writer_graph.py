"""The writer is offered the ``graph`` figure, and a point it gives is put back on its line (2026-10-20).

The writer path drew a taxi-fare graph as a model-written scene with its dots off the line: nobody had told it that
``graph`` exists (it was an imported kind only)."""
from lessonforge.harness import writer
from lessonforge.longform import figure_math


def test_the_writer_is_told_about_graphs():
    assert "graph" in writer.FIGURE_KINDS
    assert '"kind":"graph"' in writer.FIGURE_RULES
    assert '"kind":"graph"' in writer.SYSTEM


def test_a_point_off_its_line_is_put_back_on_it():
    spec, issues = figure_math.settle_graph(
        {"kind": "graph", "functions": ["40 + 12*x"], "points": [{"x": 5, "y": 90, "label": "(5, 90)"}, {"x": 2, "y": 64}]})
    assert issues and "x = 5" in issues[0]
    assert "y" not in spec["points"][0] and spec["points"][0]["label"] == "(5, 100)"
    assert spec["points"][1] == {"x": 2, "y": 64}          # on the line: left alone


def test_a_function_that_cannot_be_read_is_an_issue():
    assert figure_math.figure_issues({"kind": "graph", "functions": ["__import__('os')"]})
    assert figure_math.figure_issues({"kind": "graph", "functions": ["2*x + 1"]}) == []


def _lesson(*beats):
    return {"chapters": [{"beats": [{"id": f"{i:02}", "narration": n, "figure": dict(f)} for i, (n, f) in enumerate(beats, 1)]}]}


LINES = {"kind": "graph", "functions": ["5 - x", "x - 1"], "x_range": [0, 5]}


def test_the_crossing_point_waits_until_the_voice_says_it():
    """The computed meeting point stood on screen while the voice asked for it (2026-10-20)."""
    lesson = writer.graph_reveals(_lesson(("Where do these two lines cross?", LINES),
                                          ("They cross at three, two.", LINES),
                                          ("So x is three and y is two.", LINES)), log=lambda *_: None)
    meets = [b["figure"].get("meet") for b in lesson["chapters"][0]["beats"]]
    assert meets == [False, None, None]


def test_a_point_the_writer_marks_there_carries_it():
    marked = {**LINES, "points": [{"x": 3, "label": "(3, 2)"}]}
    lesson = writer.graph_reveals(_lesson(("It crosses at three, two.", marked)), log=lambda *_: None)
    assert lesson["chapters"][0]["beats"][0]["figure"]["meet"] is False
