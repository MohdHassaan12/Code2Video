"""A typeset drawing's printed words: found by measuring, named by one look, kept with the drawing."""
import json

import pytest

from lessonforge.harness import diagrams, typeset


def glyphs(word_starts, y, height=28, letter=14, letters=4):
    """Letters of ``letters`` glyphs each, starting at the given x positions on one line."""
    return [[x + k * (letter + 2), y, x + k * (letter + 2) + letter, y + height] for x in word_starts for k in range(letters)]


def test_letters_on_a_line_become_one_label_and_a_far_word_or_another_line_does_not():
    # "complete path": two words a word space apart (14 px at a 28 px letter); a third word far to the right; a line below
    boxes = typeset.labels_of(glyphs([100, 178], 300) + glyphs([600], 300) + glyphs([100], 360)
                              + [[118, 312, 126, 316]])                      # a dash inside the first word's line
    assert len(boxes) == 3
    assert boxes[0][0] == 100 and boxes[0][2] == 178 + 3 * 16 + 14 and boxes[1][0] == 600 and boxes[2][1] == 360
    assert typeset.labels_of([]) == []


def test_a_word_space_as_wide_as_a_ray_diagrams_is_still_one_label():
    """A ray diagram, 2026-10-12: "Reflected ray" was read as two labels (its word space was 0.82 of a tall letter), and
    the lesson marked "ray" alone under words about the incident ray."""
    word, tall = 62, 25                             # the first word ends at 100 + 62 = 162
    close = typeset.labels_of(glyphs([100], 300, height=tall) + glyphs([162 + 20.6], 300, height=tall))
    assert len(close) == 1 and close[0][0] == 100
    apart = typeset.labels_of(glyphs([100], 300, height=tall) + glyphs([162 + 30], 300, height=tall))
    assert len(apart) == 2                          # two labels side by side stay two


def test_a_name_is_short_and_a_formula_is_one_thing():
    assert typeset.pointable(" Glass  tumbler ") == "Glass tumbler"
    assert typeset.pointable("36 = 2 × 2 × 3 × 3") == "36 = 2 × 2 × 3 × 3"            # nine "words", one thing
    assert typeset.pointable("The card is flicked away and the coin falls") == ""     # a sentence printed on the drawing
    assert typeset.pointable("×") == "" and typeset.pointable("") == "" and typeset.pointable("18") == "18"
    assert typeset.pointable("(a)") == "" and typeset.pointable("Rows (n):") == "Rows (n)"   # a mark is not a name


def test_a_heading_set_large_is_one_label_and_upright_text_is_one_label():
    """First run over the library: "Square Number" in bold came out as two names, and a label written up along an
    arrow as one name per letter."""
    small = glyphs([100, 178], 300) + glyphs([100, 178, 256, 334], 700, letters=5)   # usual print: 28 px letters, most of the drawing
    heading = [[400 + k * 34, 80, 400 + k * 34 + 30, 140] for k in range(4)] + \
              [[400 + 4 * 34 + 40 + k * 34, 80, 400 + 4 * 34 + 40 + k * 34 + 30, 140] for k in range(4)]   # a 40 px space
    upright = [[900, 200 + k * 16, 914, 200 + k * 16 + 13] for k in range(6)]  # letters one above the other, 3 px apart
    two_lines = glyphs([100], 500) + glyphs([100], 548)                       # 20 px between the lines: two labels
    column = [[1100, 300, 1114, 328], [1100, 345, 1114, 373]]                 # "4" over "4" in a table: two labels
    boxes = typeset.labels_of(small + heading + upright + two_lines + column)
    assert len(boxes) == 8
    assert [400, 80] == boxes[0][:2] and boxes[0][2] == 400 + 4 * 34 + 40 + 3 * 34 + 30
    assert any(b[0] == 900 and b[1] == 200 and b[3] == 200 + 5 * 16 + 13 for b in boxes)


def test_a_label_broken_over_two_lines_with_a_hyphen_is_one_name():
    boxes = [[100, 50, 240, 78], [80, 86, 260, 114], [600, 50, 760, 78], [100, 300, 180, 328]]
    found = typeset.named(boxes, {0: "Prime Fac-", 1: "tors (Divisors)", 2: "Quo-", 3: "18"}, 1000.0, 500.0)
    assert set(found) == {diagrams.slug("Prime Factors (Divisors)"), "18"}    # "Quo-" has no second line: no name
    joined = found[diagrams.slug("Prime Factors (Divisors)")]
    assert joined["name"] == "Prime Factors (Divisors)" and joined["box"] == [0.08, 0.1, 0.26, 0.228]


def test_two_boxes_that_read_the_same_name_neither_and_boxes_are_shares_of_the_drawing():
    """A division ladder prints "3" twice (a divisor and a quotient): a ring on the wrong one is worse than none."""
    boxes = [[100, 50, 200, 80], [300, 50, 340, 80], [300, 150, 340, 180], [600, 300, 760, 340]]
    found = typeset.named(boxes, {0: "bulb", 1: "3", 2: "3", 3: "Glass tumbler", 7: "outside"}, 1000.0, 500.0)
    assert set(found) == {"bulb", diagrams.slug("Glass tumbler")}
    assert found["bulb"] == {"name": "bulb", "box": [0.1, 0.1, 0.2, 0.16]}


def test_the_names_are_made_once_and_kept_in_the_drawings_own_manifest(tmp_path, monkeypatch):
    from PIL import Image
    folder = tmp_path / "a_simple_circuit-0001"
    folder.mkdir()
    (folder / "source.svg").write_text("<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 50'></svg>")
    Image.new("RGB", (1280, 640), "white").save(folder / "whole.png")
    manifest = folder / "manifest.json"
    manifest.write_text(json.dumps({"version": 9, "whole": "whole.png", "parts": [], "labels": []}))
    monkeypatch.setattr(typeset, "measure", lambda svg, chrome=None: {
        "width": 1280, "height": 640, "texts": 0, "glyphs": glyphs([100], 100) + glyphs([600], 100) + glyphs([100], 400)})
    looks = []

    def look(prompt, system, jpeg):
        looks.append(prompt)
        return {"1": "bulb", "2": "wire", "box 3": "complete path"}

    # switched off (as in every test): nobody looks and nothing is kept
    assert typeset.names(manifest, look=look, log=lambda *_: None) == {} and not looks
    assert "typeset" not in json.loads(manifest.read_text())
    monkeypatch.setenv("HARNESS_TYPESET_NAMES", "1")
    found = typeset.names(manifest, look=look, log=lambda *_: None)
    assert set(found) == {"bulb", "wire", "complete_path"} and len(looks) == 1 and "3 numbered boxes" in looks[0]
    assert 0 < found["bulb"]["box"][0] < found["wire"]["box"][0] < 1 and found["complete_path"]["box"][1] > found["bulb"]["box"][3]
    kept = json.loads(manifest.read_text())
    assert kept["typeset"]["names"] == found and kept["version"] == 9 and kept["whole"] == "whole.png"     # the rest untouched
    assert typeset.names(manifest, look=look, log=lambda *_: None) == found and len(looks) == 1            # not looked at twice

    # a look that fails is not kept as "no names": the next lesson asks again
    manifest.write_text(json.dumps({"version": 9, "whole": "whole.png"}))
    assert typeset.names(manifest, look=lambda *a: None, log=lambda *_: None) == {}
    assert "typeset" not in json.loads(manifest.read_text())
    # a drawing with real <text> is not this module's: noted once as having no typeset names, without a look
    monkeypatch.setattr(typeset, "measure", lambda svg, chrome=None: {"width": 1280, "height": 640, "texts": 5, "glyphs": []})
    assert typeset.names(manifest, look=look, log=lambda *_: None) == {} and len(looks) == 1
    assert json.loads(manifest.read_text())["typeset"] == {"version": typeset.VERSION, "names": {}}
    assert typeset.names(tmp_path / "nowhere" / "manifest.json") == {}


def test_a_browser_measures_where_the_glyphs_are(tmp_path):
    if diagrams.browser() is None:
        pytest.skip("no headless browser on this machine")
    svg = tmp_path / "source.svg"
    svg.write_text("""<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="200" height="100" viewBox="0 0 200 100">
<defs><g><g id="glyph-0-0"><path d="M 0 0 L 6 0 L 6 -8 L 0 -8 Z"/></g></g></defs>
<path d="M 10 90 L 190 90" stroke="black"/>
<g fill="black"><use xlink:href="#glyph-0-0" x="20" y="40"/><use xlink:href="#glyph-0-0" x="28" y="40"/>
<use xlink:href="#glyph-0-0" x="120" y="40"/></g></svg>""")
    measured = typeset.measure(svg)
    assert measured and measured["width"] == 1280 and round(measured["height"]) == 640 and measured["texts"] == 0
    assert len(measured["glyphs"]) == 3                                   # the line is not a glyph; the glyph in <defs> is not drawn
    labels = typeset.labels_of(measured["glyphs"])
    assert len(labels) == 2 and abs(labels[0][0] - 20 * 6.4) < 2 and abs(labels[1][0] - 120 * 6.4) < 2
    # a drawing that carries a script is never handed to a browser
    bad = tmp_path / "bad.svg"
    bad.write_text("<svg xmlns='http://www.w3.org/2000/svg'><script>alert(1)</script></svg>")
    assert typeset.measure(bad) is None


def test_a_stacked_fraction_is_one_name_and_letters_in_an_upright_sliver_are_none():
    """Read back from real drawings: "1 2" for a half set as one number over the other, and "vapour" for half of a
    label written up along an arrow."""
    boxes = [[100, 100, 114, 150], [300, 100, 314, 150], [500, 200, 520, 290], [700, 100, 780, 128]]
    found = typeset.named(boxes, {0: "1 2", 1: "5 6", 2: "vapour", 3: "3 4"}, 1000.0, 500.0)
    assert {entry["name"] for entry in found.values()} == {"1/2", "5/6", "3 4"}      # the wide "3 4" is two numbers in a row
    assert all("vapour" != entry["name"] for entry in found.values())
