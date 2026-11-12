"""A drawing as a sequence of its parts, and the picture that draws itself from it (2026-10-12).

The owner: "the visuals are static … take the SVG and divide the SVG components into JSON. Different parts of the
visual should be coming in a sequence … then you take the pattern and style it." No browser and no render here but
for one test that is skipped without a browser: the sequence is ordered by code, and the figure's pen-work is stepped
by hand, as the renderer steps it.
"""
import json

import numpy as np
import pytest
from PIL import Image

from lessonforge.harness import diagrams, sequence, vision_review
from lessonforge.longform import figures, look, runtime


def shape(order, box, length, stroke="", fill="", closed=False, dashed=False):
    x0, y0, x1, y1 = box
    return {"order": order, "tag": "path", "box": box, "points": [[x0, y0], [x1, y0], [x1, y1], [x0, y1]] if closed else [[x0, y0], [x1, y1]],
            "closed": closed, "stroke": stroke, "fill": fill, "width": 0.003, "dashed": dashed, "dash": 0.01 if dashed else 0, "opacity": 1.0,
            "length": length, "svg": f"<path id='p{order}'/>"}


def test_the_parts_come_in_the_order_a_hand_would_draw_them():
    shapes = [shape(1, [0.1, 0.1, 0.5, 0.8], 2.0, fill="#ffcccc", closed=True),            # a balloon's fill …
              shape(2, [0.1, 0.1, 0.5, 0.8], 2.0, stroke="#800000", closed=True),          # … and its edge: one part
              shape(3, [0.6, 0.4, 0.9, 0.4], 0.3, stroke="#000099"),                       # an arrow's line
              shape(4, [0.2, 0.9, 0.4, 0.9], 0.2, stroke="#666666", dashed=True),          # a dashed line, written before the arrow's head
              shape(5, [0.89, 0.39, 0.91, 0.41], 0.02, stroke="#000099", fill="#000099", closed=True)]   # the arrow's head
    labels = [{"order": 9, "box": [0.62, 0.30, 0.80, 0.36], "text": "", "svg": ""},        # beside the arrow
              {"order": 8, "box": [0.2, 0.84, 0.3, 0.88], "text": "Neck", "svg": "<text>Neck</text>"}]
    names = {"push": {"name": "Push of the air", "box": [0.62, 0.30, 0.80, 0.36]}}
    parts = sequence.order_parts(shapes, labels, names)
    assert [(p["n"], p["kind"], p["text"]) for p in parts] == [(1, "fill", ""), (2, "stroke", ""), (3, "fill", ""), (4, "text", "Push of the air"),
                                                                (5, "stroke", ""), (6, "text", "Neck")]
    balloon, arrow, head, _, dashed, _ = parts
    assert balloon["fill"] == "#ffcccc" and balloon["stroke"] == "#800000" and "p1" in balloon["svg"] and "p2" in balloon["svg"]
    assert arrow["box"] == [0.6, 0.4, 0.9, 0.4] and head["length"] == 0.02       # the head follows the line it touches
    assert dashed["dashed"] and dashed["dash"] == 0.01
    assert all(set(p) >= {"n", "kind", "svg", "text", "box", "points", "closed", "stroke", "fill", "width", "dashed", "length"} for p in parts)


def drawing(tmp_path, svg="<svg xmlns='http://www.w3.org/2000/svg' width='200' height='100' viewBox='0 0 200 100'>"
                           "<path d='M 10 90 L 100 10 L 190 90 Z' fill='none' stroke='rgb(0,0,153)' stroke-width='2'/>"
                           "<line x1='10' y1='10' x2='190' y2='10' stroke='#666' stroke-dasharray='4 4'/>"
                           "<text x='95' y='60' font-size='12'>A</text></svg>"):
    folder = tmp_path / "a_triangle-0123456789"
    folder.mkdir(parents=True)
    (folder / "source.svg").write_text(svg, encoding="utf-8")
    (folder / "manifest.json").write_text(json.dumps({"whole": "whole.png"}), encoding="utf-8")
    Image.new("RGBA", (400, 200), "white").save(folder / "whole.png")
    return folder


MEASURED = {"width": 1280, "height": 640, "texts": [{"order": 3, "box": [0.46, 0.5, 0.5, 0.62], "text": "A", "svg": "<text>A</text>"}],
            "shapes": [shape(1, [0.05, 0.1, 0.95, 0.9], 1.6, stroke="#000099", closed=True), shape(2, [0.05, 0.1, 0.95, 0.1], 0.9, stroke="#666666", dashed=True)]}


def test_a_drawing_is_taken_apart_once_and_kept_beside_it(tmp_path, monkeypatch):
    folder = drawing(tmp_path)
    asked = []
    monkeypatch.setattr(sequence, "measure", lambda path, chrome=None: asked.append(path) or json.loads(json.dumps(MEASURED)))
    made = sequence.sequence(folder, log=lambda *a: None)
    assert [p["kind"] for p in made["parts"]] == ["stroke", "text", "stroke"] and made["version"] == sequence.VERSION
    assert json.loads((folder / "sequence.json").read_text())["parts"] == made["parts"]
    assert sequence.sequence(folder, log=lambda *a: None)["parts"] == made["parts"] and len(asked) == 1       # kept: the browser is not asked again
    (folder / "source.svg").write_text((folder / "source.svg").read_text() + " ", encoding="utf-8")          # another drawing: asked again
    sequence.sequence(folder, log=lambda *a: None)
    assert len(asked) == 2
    # one shape is not a drawing to draw by hand, and neither is one of three hundred parts: shown as before, and that is kept too
    monkeypatch.setattr(sequence, "measure", lambda path, chrome=None: {**MEASURED, "shapes": MEASURED["shapes"][:1], "texts": []})
    other = drawing(tmp_path / "other")
    assert sequence.sequence(other, log=lambda *a: None) is None and json.loads((other / "sequence.json").read_text())["parts"] == []
    assert sequence.sequence(tmp_path / "nowhere") is None
    lesson = {"chapters": [{"beats": [{"id": "01", "figure": {"kind": "picture", "file": str(folder / "whole.png")}},
                                      {"id": "02", "figure": {"kind": "picture", "file": str(folder / "whole_stacked.png")}},
                                      {"id": "03", "figure": {"kind": "diagram", "manifest": str(folder / "manifest.json")}}]}]}
    monkeypatch.setattr(sequence, "measure", lambda path, chrome=None: json.loads(json.dumps(MEASURED)))
    assert sequence.for_lesson(lesson, log=lambda *a: None) == {"drawings": 1, "made": 1}
    monkeypatch.setenv("HARNESS_SEQUENCE", "0")
    assert sequence.for_lesson(lesson, log=lambda *a: None) == {"drawings": 0, "made": 0}


def test_a_browser_finds_the_parts_of_a_real_svg(tmp_path):
    if not diagrams.browser():
        pytest.skip("no headless browser on this machine")
    measured = sequence.measure(drawing(tmp_path) / "source.svg")
    assert measured and len(measured["shapes"]) == 2 and [t["text"] for t in measured["texts"]] == ["A"]
    triangle, line = measured["shapes"]
    assert triangle["closed"] and triangle["stroke"] == "#000099" and not triangle["fill"] and len(triangle["points"]) > 20
    assert line["dashed"] and line["dash"] > 0 and abs(line["points"][0][1] - 0.1) < 0.01 and abs(line["points"][-1][0] - 0.95) < 0.01
    assert all(0 <= v <= 1 for p in triangle["points"] for v in p)


def a_picture(tmp_path, with_sequence=True):
    folder = drawing(tmp_path)
    parts = sequence.order_parts(MEASURED["shapes"], [dict(t) for t in MEASURED["texts"]], {})
    if with_sequence:
        (folder / "sequence.json").write_text(json.dumps({"version": sequence.VERSION, "parts": parts}), encoding="utf-8")
    return figures.build({"kind": "picture", "file": str(folder / "whole.png"), "points": {"a": {"box": [0.46, 0.5, 0.5, 0.62]}}})


def test_the_picture_draws_itself_part_by_part_and_ends_as_it_always_was(tmp_path):
    figure = a_picture(tmp_path)
    alpha = lambda: int(figure.art.pixel_array[..., 3].max())        # noqa: E731
    assert alpha() == 255 and figure._painted == []                  # built finished: every other path of the renderer sees it whole
    children = len(figure.submobjects)
    animation, seconds = figure.paint()
    assert figures.PictureFigure.PAINT_SECONDS[0] <= seconds <= figures.PictureFigure.PAINT_SECONDS[1]
    assert alpha() == 0 and len(figure._painted) == 3                # a triangle, the label beside it, a dashed line
    pens = figure._painted
    assert figure.submobjects.index(pens[0]) < figure.submobjects.index(figure.art) < figure.submobjects.index(figure.marks["a"])
    assert isinstance(pens[2], figures.DashedVMobject) and isinstance(pens[1], figures.ImageMobject)
    # a step points at the label while the pen is still at work: the mark waits for the drawing
    assert figure.focus_animations("a") == [] and figure.marks["a"].get_fill_opacity() == 0
    animation.begin()
    for share in (0.0, 0.3, 0.7, 1.0):                               # stepped by hand, as the renderer steps it
        animation.interpolate(share)
    animation.finish()
    figure.painted()
    assert alpha() == 255 and figure._painted == [] and len(figure.submobjects) == children
    assert figure.marks["a"].get_fill_opacity() > 0.3                # … and is there when the drawing stands
    # a picture with no sequence beside it, or one shown in panels, is shown as before
    assert a_picture(tmp_path / "plain", with_sequence=False).paint() is None


def test_a_pause_card_shows_the_beats_line_for_the_screen_never_the_spoken_sentence():
    beat = {"narration": "Ab socho: agar air backward nikle, balloon backward, forward, ya still rahega?",
            "steps": [{"show": "Inflated balloon", "kind": "point"}, {"show": "F = ma", "kind": "math"}, {"show": "Which way?", "kind": "key"},
                      {"show": "Predict first", "kind": "point"}]}
    assert runtime.screen_question(beat) == "Which way?"             # the line that asks, when one does
    assert runtime.screen_question({**beat, "steps": beat["steps"][:2]}) == "Inflated balloon"
    assert runtime.screen_question({"narration": "Kya hoga?", "steps": []}) == ""


def test_a_lesson_made_now_has_its_drawings_painted_and_an_older_one_has_them_shown():
    assert look.for_new({"chapters": []}, environ={})["drawings"] == "painted"
    assert look.of({"look": {"frame": "stage"}}, environ={})["drawings"] == "shown" == look.BEFORE["drawings"]
    assert look.of({"look": {"frame": "stage", "drawings": "painted"}}, environ={})["drawings"] == "painted"
    assert look.of({"look": {"frame": "stage", "drawings": "painted"}}, environ={"LESSONFORGE_DRAWINGS": "shown"})["drawings"] == "shown"
    assert look.for_new({"chapters": []}, environ={"HARNESS_DRAWINGS": "shown"})["drawings"] == "shown"


def test_the_frame_reviewer_looks_once_a_painted_drawing_stands():
    lesson = {"chapters": [{"id": 1, "beats": [{"id": "01", "steps": [{"say": "a", "show": "A", "kind": "point", "highlight": True}]},
                                                {"id": "02", "steps": []}]}]}
    timeline = [{"id": "01", "chapter": 1, "start": 10.0, "duration": 12.0, "speech_end": 11.0, "sentences": [{"text": "a b c", "start": 0.2, "duration": 3.0}]},
                {"id": "02", "chapter": 1, "start": 22.0, "duration": 3.0, "speech_end": 2.5, "sentences": []}]
    plain = vision_review.sample_points(timeline, lesson, layouts={})
    painted = vision_review.sample_points(timeline, lesson, layouts={"01": {"painted": 5.0}, "02": {"painted": 5.0}})
    assert plain[0]["at"] < 10.0 + 5.0 and painted[0]["at"] >= 10.0 + 5.0 + .5 and not painted[0]["being_drawn"]
    assert painted[1]["being_drawn"] and painted[1]["at"] <= 25.0     # a beat that ends before the drawing stands: the look is told
