"""The small pure pieces of the guided renderer's layout and scene timing (no render)."""
from lessonforge.longform import runtime


def test_the_value_a_line_of_working_ends_on():
    assert runtime.found_value(r"4 \times 4 = 16") == "16"
    assert runtime.found_value(r"9 \times 9 = 81 \text{ m}") == "81 m"
    assert runtime.found_value("s^2") == ""
    assert runtime.found_value(r"16 = 4 \times 4") == ""          # it ends on the working, not on a value
    assert runtime.found_value("") == ""


def test_a_long_list_is_cut_in_two_at_an_item_comma_and_nothing_else_is():
    assert runtime.math_rows("17^2 = 289, 18^2 = 324, 19^2 = 361, 20^2 = 400") == \
        ["17^2 = 289, 18^2 = 324,", "19^2 = 361, 20^2 = 400"]
    assert runtime.math_rows(r"4 \times 4 = 16") == []
    assert runtime.math_rows("1{,}000 + 2{,}000") == []           # a thousands comma in braces
    assert runtime.math_rows(r"a\,b = 1,000") == []               # a thin space, and "1,000"
    assert runtime.math_rows("f(x, y) = x + y") == []             # a comma inside brackets
    assert runtime.math_rows(r"\begin{aligned} a, b \\ c \end{aligned}") == []


def test_scene_motion_waits_for_each_steps_words():
    # A beat that starts at 10 s and speaks for 12 s; its three steps are said at 12, 16 and 19 s.
    start, total = 10.0, 12.0
    edges = runtime.stage_marks([16.0, 12.0, 19.0], start)
    assert edges == [12.0, 16.0, 19.0]
    at = lambda now: runtime.stage_progress(now, start, total, edges)  # noqa: E731
    assert at(10.5) == 0.0 and at(12.0) == 0.0                     # nothing moves before the first words
    # A stage is played SOON after its words begin (here 1.6 s of a 4 s gap) and then waits for the next.
    assert runtime.stage_seconds(4.0) == 1.6
    assert abs(at(12.8) - (0.5 / 3)) < 1e-9                        # halfway through stage one after 0.8 s
    # done, and waiting a hair BEFORE the boundary (on it, the next stage's shapes are at their zero point)
    assert abs(at(13.6) - .999 / 3) < 1e-9 and at(15.9) == at(13.6) and at(13.6) < 1 / 3
    assert abs(at(16.0) - 1 / 3) < 1e-9                            # stage two begins on its own words
    assert abs(at(19.0) - 2 / 3) < 1e-9
    assert at(22.0) == 1.0 and at(30.0) == 1.0                     # done when the speech ends
    values = [at(10 + k * .1) for k in range(140)]
    assert all(b >= a for a, b in zip(values, values[1:]))         # it never runs backwards


def test_how_long_a_stage_plays():
    assert runtime.stage_seconds(0.8) == 0.8                       # a short gap is used whole
    assert runtime.stage_seconds(2.0) == 1.2                       # never rushed below 1.2 s when there is room
    assert runtime.stage_seconds(10.0) == 4.0                      # a long gap: a slower, longer move
    assert runtime.stage_seconds(0.1) == 0.4                       # and never a divide by nearly nothing


def test_scene_motion_without_step_times_runs_evenly_and_marks_are_tidied():
    assert runtime.stage_progress(13.0, 10.0, 12.0, []) == 0.25
    assert runtime.stage_progress(40.0, 10.0, 12.0, []) == 1.0
    # A step due before the scene is up starts with it; two steps on one word are one stage.
    assert runtime.stage_marks([8.0, 12.0, 12.02], 10.0) == [10.0, 12.0]
    assert runtime.stage_marks(None, 10.0) == []


def test_a_whole_picture_is_built_from_a_picture_file_and_from_nothing_else(tmp_path):
    from PIL import Image
    from lessonforge.longform import figures
    file = tmp_path / "source.png"
    Image.new("RGB", (90, 61), "white").save(file)
    fig = figures.build({"kind": "picture", "file": str(file), "ask": "Water cycle"})
    assert fig.kind == "picture" and abs(fig.art.height - 4.6) < 1e-6 and fig.card.width > fig.art.width
    assert fig.focus_animations("1_evaporation") == [] and fig.parts == {}      # an image is never pulsed or recoloured
    assert figures.build({"kind": "picture", "file": str(tmp_path / "missing.png")}) is None
    assert figures.build({"kind": "picture", "file": "/etc/passwd"}) is None    # only a picture file is a picture


def test_a_whole_pictures_printed_label_is_marked_when_a_step_names_it_and_the_mark_moves_with_the_picture(tmp_path):
    """Half of what the drawing service returns is typeset (a circuit, a division ladder): shown whole, it stood still
    through everything said about it. Its printed labels are found (harness/typeset.py) and marked as they are named."""
    from PIL import Image
    from lessonforge.longform import figures
    file = tmp_path / "whole.png"
    Image.new("RGB", (400, 200), "white").save(file)
    points = {"bulb": {"name": "Bulb", "box": [0.45, 0.05, 0.55, 0.15]}, "cell": {"name": "Cell", "box": [0.45, 0.85, 0.55, 0.95]},
              "broken": {"box": [0.2, 0.2]}, "speck": {"box": [0.5, 0.5, 0.501, 0.501]}}       # two that cannot be marked
    fig = figures.build({"kind": "picture", "file": str(file), "points": points})
    assert set(fig.marks) == {"bulb", "cell"}
    bulb, cell = fig.marks["bulb"], fig.marks["cell"]
    assert bulb.get_fill_opacity() == 0 and bulb.get_stroke_opacity() == 0             # nothing is marked until a step says so
    # where the label is in the picture: near the top, in the middle; the cell's is near the bottom
    assert abs(bulb.get_center()[0] - fig.art.get_center()[0]) < 1e-6 and bulb.get_center()[1] > fig.art.get_center()[1] > cell.get_center()[1]
    assert abs((fig.art.get_top()[1] - bulb.get_center()[1]) - 0.1 * fig.art.height) < 1e-6
    # the renderer fits the figure into its box AFTER it is built: the mark is the figure's child and goes with it
    fig.scale(0.5).shift([2.0, 1.0, 0.0])
    assert abs((fig.art.get_top()[1] - bulb.get_center()[1]) - 0.1 * fig.art.height) < 1e-6
    first = fig.focus_animations("bulb")
    assert len(first) == 1 and fig.focus_animations("bulb") == []                      # already marked: nothing to do
    second = fig.focus_animations("cell")
    assert len(second) == 2                                                            # the mark leaves "Bulb" and lands on "Cell"
    assert fig.focus_animations("nothing_here") == [] and fig.focus_animations("") == []


def test_a_label_in_a_panel_not_yet_shown_brings_its_panel_in(tmp_path):
    from PIL import Image
    from lessonforge.longform import figures
    whole, one, two = tmp_path / "whole_stacked.png", tmp_path / "panel_1.png", tmp_path / "panel_2.png"
    Image.new("RGB", (400, 400), "white").save(whole)
    Image.new("RGB", (400, 190), "white").save(one)
    Image.new("RGB", (400, 190), "white").save(two)
    fig = figures.build({"kind": "picture", "file": str(whole), "panels": [str(one), str(two)],
                         "panel_boxes": [[0, 0, 400, 190], [0, 210, 400, 400]],
                         "points": {"before": {"box": [0.4, 0.1, 0.6, 0.2]}, "after": {"box": [0.4, 0.7, 0.6, 0.8]}}})
    assert len(fig.focus_animations("before")) == 1                    # in the panel already on screen: only the mark
    assert len(fig.focus_animations("after")) == 3                     # its panel comes in, the old mark goes, the new one lands
    assert fig.focus_animations("panel2") == []                        # ... so the panel is not brought in a second time


def test_a_chapter_opens_its_drawing_as_every_earlier_chapter_left_it():
    """A chapter is a render of its own: the arrows a learner watched being drawn in chapter 3 were gone when chapter 4
    opened. The renderer hands the figure what every earlier beat on the SAME drawing pointed at, in order."""
    import types
    water = {"kind": "diagram", "manifest": "/lib/water/manifest.json", "labels": ["evaporation", "condensation"]}
    cell = {"kind": "diagram", "manifest": "/lib/cell/manifest.json"}
    lesson = {"chapters": [
        {"id": 1, "beats": [{"id": "01", "figure": water, "steps": [{"focus": "evaporation"}, {"show": "no focus"}]}]},
        {"id": 2, "beats": [{"id": "02", "figure": cell, "steps": [{"focus": "nucleus"}]},
                            {"id": "03", "steps": [{"focus": "stray"}]}]},
        {"id": 3, "beats": [{"id": "04", "figure": water, "steps": [{"focus": "condensation"}]},
                            {"id": "05", "figure": water, "steps": [{"focus": "precipitation"}]}]}]}
    me = types.SimpleNamespace(lesson=lesson)
    before = runtime.GuidedChapter._pointed_at_before
    assert before(me, water, lesson["chapters"][0]["beats"][0]) == []                         # the first beat: nothing yet
    assert before(me, water, lesson["chapters"][2]["beats"][0]) == ["evaporation"]            # not the cell's, not a bare beat's
    assert before(me, water, lesson["chapters"][2]["beats"][1]) == ["evaporation", "condensation"]
    assert before(me, cell, lesson["chapters"][2]["beats"][1]) == ["nucleus"]
    assert before(me, {"kind": "scene"}, lesson["chapters"][2]["beats"][1]) == []            # only a drawing with a manifest


def test_the_box_a_drawing_is_laid_out_for_is_the_box_it_is_rendered_in():
    """``diagrams`` picks a two-panel drawing's layout (as drawn, or the second panel under the first) by which comes out
    larger in the renderer's drawing box. A 2.2-to-1 circuit was shown re-laid at 24% of the frame's width when as drawn
    it fills 62%: the choice had been made for a box the renderer no longer used."""
    from lessonforge.harness import diagrams
    from lessonforge.longform import look
    assert tuple(diagrams.SHOWN_IN) == tuple(runtime.GuidedChapter.DRAWING_BOX[:2]) == tuple(look.COLUMNS_DRAWING)
    # ... and in the stage frame the boxes are worked out from the numbers the renderer itself lays out by
    chapter = runtime.GuidedChapter
    assert (chapter.WORDS, chapter.BOARD, chapter.LINE, chapter.GAP) == (look.WORDS, look.BOARD, look.LINE, look.GAP)
    for captions in look.CAPTIONS:
        scene = chapter.__new__(chapter)
        scene.CAPTION_BAND = captions == "band"
        x0, x1, y0, y1 = scene._stage_box()
        assert look.picture_boxes({"frame": "stage", "captions": captions}) == [
            (round(x1 - x0 - chapter.WORDS - chapter.GAP, 3), round(y1 - y0, 3)), (round(x1 - x0, 3), round(y1 - y0 - chapter.LINE - chapter.GAP, 3))]


def test_a_steps_wording_is_cut_at_a_word_when_it_is_far_too_long_for_the_screen():
    long = "Say the route, highlight the sea to cloud, cloud to ground and return legs with labels evaporation, condensati"
    shown = runtime.screen_words(long)
    assert shown == "Say the route, highlight the sea to cloud, cloud to ground and return legs …"
    assert runtime.screen_words("3 rows of 3") == "3 rows of 3" and runtime.screen_words("  spaced   out  ") == "spaced out"
    assert len(runtime.screen_words(long).split()) <= 15


def test_two_statements_joined_by_a_semicolon_are_cut_at_the_semicolon():
    # seen 2026-10-19: cut at "=", the second line began "= 1 × 10 = 10N; …"
    assert runtime.math_rows(r"F = mg = 1 \times 10 = 10N; a = 10/1 = 10") == [r"F = mg = 1 \times 10 = 10N", "a = 10/1 = 10"]
