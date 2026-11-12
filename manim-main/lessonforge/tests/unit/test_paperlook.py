"""The look of paint on paper for a poster's scene, by arithmetic (harness/paperlook.py; the owner's go-ahead, 2026-10-12).

No model: what is pinned is that nothing can go missing. The scene keeps its size and its colours, a thin light line on
a dark ground keeps its brightness (the first filter darkened a plant's roots into the soil), arrows and labels are the
drawing's own, a drawing in one piece is left alone, and a look made once is used again.
"""
import json

import numpy as np
from PIL import Image, ImageDraw

from lessonforge.harness import paperlook
from test_repaint import poster


def scene():
    made = Image.new("RGB", (640, 400), "#bfe3ff")
    pen = ImageDraw.Draw(made)
    pen.rectangle([0, 260, 640, 400], fill="#7a4a12")                    # soil
    pen.rectangle([0, 250, 640, 262], fill="#5aa02c")                    # grass
    pen.line([320, 262, 300, 340], fill="#fff2c2", width=3)              # a root: a thin light line on dark ground
    pen.ellipse([40, 30, 120, 110], fill="#ffcf33")                      # the Sun
    return made


def test_the_scene_keeps_its_size_its_colours_and_its_thin_light_lines():
    before = scene()
    after = paperlook.paper(before, seed=5)
    assert after.size == before.size and after.mode == "RGB"
    a, b = np.asarray(before).astype(float), np.asarray(after).astype(float)
    assert np.abs(a - b).mean() > 1.0                                    # it is not the same picture: grain, rims, blotches …
    for box in ((200, 20, 600, 200), (40, 290, 260, 390)):               # … but the sky is still that blue and the soil that brown
        x0, y0, x1, y1 = box
        assert np.abs(a[y0:y1, x0:x1].mean(axis=(0, 1)) - b[y0:y1, x0:x1].mean(axis=(0, 1))).max() < 12
    root_before, root_after = a[268:335, 296:324].max(axis=2), b[268:335, 296:324].max(axis=2)
    brightest = lambda g: np.sort(g.ravel())[-40:].mean()                # noqa: E731
    assert brightest(root_after) > 0.93 * brightest(root_before)
    # the same scene and seed give the same picture; another seed another grain
    assert np.array_equal(np.asarray(paperlook.paper(before, seed=5)), np.asarray(after))
    assert not np.array_equal(np.asarray(paperlook.paper(before, seed=6)), np.asarray(after))


def test_a_poster_gets_a_copy_with_the_look_once_and_its_arrows_and_words_are_its_own(tmp_path):
    folder = poster(tmp_path)
    said = []
    made = paperlook.looked(folder / "manifest.json", log=said.append)
    assert made == str(folder / "paper" / "manifest.json") and "paint on paper" in said[0]
    copy = json.loads((folder / "paper" / "manifest.json").read_text())
    assert copy["paper"]["version"] == paperlook.VERSION and copy["folder"] == str((folder / "paper").resolve())
    assert copy["parts"] == json.loads((folder / "manifest.json").read_text())["parts"]
    # the arrow layer is the original's, byte for byte; the scene is not; the original drawing is untouched
    assert (folder / "paper" / "marks_00.png").read_bytes() == (folder / "marks_00.png").read_bytes()
    assert (folder / "paper" / "base.png").read_bytes() != (folder / "base.png").read_bytes()
    original = np.asarray(Image.open(folder / "art.png").convert("RGB")).astype(int)
    looked = np.asarray(Image.open(folder / "paper" / "art.png").convert("RGB")).astype(int)
    assert original.shape == looked.shape
    assert np.abs(original[75:125, 154:157] - looked[75:125, 154:157]).max() <= 2        # the arrow's own pixels, laid back on top
    whole = np.asarray(Image.open(folder / "paper" / "whole.png").convert("RGB")).astype(int)
    assert (whole[26:38, 240:290] > 250).all()                                             # the box of words is as it was printed
    # asked again: the copy that is there, not made again
    stamp = (folder / "paper" / "base.png").stat().st_mtime_ns
    assert paperlook.looked(folder / "manifest.json", log=said.append) == made and len(said) == 1
    assert (folder / "paper" / "base.png").stat().st_mtime_ns == stamp
    # a copy is never given a look on top of its look
    assert paperlook.looked(folder / "paper" / "manifest.json") is None


def test_a_drawing_in_one_piece_is_left_as_drawn_and_the_switch_leaves_every_drawing(tmp_path, monkeypatch):
    whole = poster(tmp_path / "one", base=False)
    assert paperlook.looked(whole / "manifest.json") is None and not (whole / "paper").exists()
    assert paperlook.looked(tmp_path / "nowhere" / "manifest.json", log=lambda *a: None) is None
    folder = poster(tmp_path / "two")
    path = str(folder / "manifest.json")
    lesson = {"chapters": [{"beats": [{"id": "01", "figure": {"kind": "diagram", "manifest": path, "ask": "the water cycle"}},
                                      {"id": "02", "figure": {"kind": "diagram", "manifest": path}},
                                      {"id": "03", "figure": {"kind": "picture", "file": str(folder / "whole.png")}},
                                      {"id": "04"}]}]}
    monkeypatch.setenv("HARNESS_DRAWING_LOOK", "0")
    assert paperlook.apply(lesson, log=lambda *a: None) == {"asked": 0, "given": 0} and lesson["chapters"][0]["beats"][0]["figure"]["manifest"] == path
    monkeypatch.delenv("HARNESS_DRAWING_LOOK")
    assert paperlook.apply(lesson, log=lambda *a: None) == {"asked": 1, "given": 1}
    beats = lesson["chapters"][0]["beats"]
    assert beats[0]["figure"]["manifest"] == beats[1]["figure"]["manifest"] == str(folder / "paper" / "manifest.json")
    assert beats[0]["figure"]["ask"] == "the water cycle" and beats[2]["figure"]["file"] == str(folder / "whole.png")
    assert paperlook.apply(lesson, log=lambda *a: None) == {"asked": 1, "given": 0}       # already pointed at the copy
