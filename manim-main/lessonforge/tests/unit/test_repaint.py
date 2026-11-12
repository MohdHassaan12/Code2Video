"""A poster's scene repainted on this machine: what code decides around the image model and the vision judge.

No GPU and no network here: the model is a function that returns a picture, the judge a function that returns JSON.
"""
import json

import pytest
from PIL import Image, ImageDraw

from lessonforge.harness import repaint


def poster(tmp_path, base=True):
    """A drawing folder as ``diagrams.take_apart`` leaves a poster: its art, its scene, one arrow layer, a manifest."""
    folder = tmp_path / "water_cycle-0123456789"
    folder.mkdir(parents=True)
    scene = Image.new("RGBA", (320, 200), "#bfe3ff")
    pen = ImageDraw.Draw(scene)
    pen.rectangle([0, 140, 320, 200], fill="#2f6fd6")                    # the sea
    pen.ellipse([20, 20, 70, 70], fill="#ffcf33")                        # the Sun
    for x, y in ((200, 100), (212, 108), (224, 98)):                     # three drops, a few pixels across
        pen.ellipse([x, y, x + 5, y + 7], fill="#1b4fd0")
    scene.save(folder / "base.png")
    arrow = Image.new("RGBA", (10, 60), (0, 0, 0, 0))
    ImageDraw.Draw(arrow).line([5, 60, 5, 0], fill="#e8590c", width=3)
    arrow.save(folder / "marks_00.png")
    art = scene.copy()
    art.alpha_composite(arrow, (150, 70))
    art.save(folder / "art.png")
    whole = art.copy()
    ImageDraw.Draw(whole).rectangle([230, 20, 300, 44], fill="white", outline="#e8590c")       # a box of words
    whole.save(folder / "whole.png")
    manifest = {"version": 10, "width": 320, "height": 200, "art": "art.png", "art_box": [0, 0, 320, 200], "style": "boxes",
                "base": "base.png" if base else "", "whole": "whole.png", "folder": str(folder),
                "parts": [{"id": "marks_00", "png": "marks_00.png", "box": [150, 70, 160, 130], "area": 180}],
                "labels": [{"name": "Evaporation", "slug": "evaporation", "part": "marks_00", "tip": [155, 100], "from": [240, 30]}]}
    (folder / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return folder


THINGS = [{"thing": "the Sun", "where": "top left"}, {"thing": "the sea", "where": "bottom"}, {"thing": "three drops", "where": "right"}]


def judge(kind="scene", verdicts=(), new=()):
    """A vision judge: says what kind the scene is, then answers each comparison with the next verdict in turn."""
    asked = {"kind": 0, "same": 0}
    answers = list(verdicts)

    def look(prompt, system, jpeg):
        if system is repaint.KIND:
            asked["kind"] += 1
            return {"kind": kind, "things": THINGS, "why": "a landscape"}
        asked["same"] += 1
        said = answers.pop(0) if answers else "same"
        if said is None:
            return None
        return {"checks": [{"n": n, "thing": t["thing"], "in_b": said if n == 3 else "same", "seen": ""} for n, t in enumerate(THINGS, 1)],
                "new_in_b": list(new) if asked["same"] == 1 else []}
    look.asked = asked
    return look


@pytest.fixture
def painter(monkeypatch):
    """The image model: gives the scene back a little warmer, and counts how often it was asked."""
    calls = []

    def paint(url, picture, prompt, strength, seed=7):
        calls.append((strength, seed, prompt))
        return Image.eval(picture.convert("RGB"), lambda v: min(255, v + 8))
    monkeypatch.setattr(repaint, "paint", paint)
    return calls


def test_it_is_off_until_it_is_asked_for(monkeypatch):
    monkeypatch.delenv("HARNESS_REPAINT", raising=False)
    assert repaint.enabled() is False
    lesson = {"chapters": [{"beats": [{"figure": {"kind": "diagram", "manifest": "/nowhere/manifest.json"}}]}]}
    assert repaint.restyle_lesson(lesson) == {"asked": 0, "repainted": 0, "kept_as_drawn": 0}
    monkeypatch.setenv("HARNESS_REPAINT", "1")
    assert repaint.enabled() is True


def test_a_scene_the_judge_finds_unchanged_becomes_a_drawing_of_its_own_beside_the_original(tmp_path, painter):
    folder, look = poster(tmp_path), judge()
    original = (folder / "base.png").read_bytes()
    done = repaint.styled(folder / "manifest.json", ask="the water cycle", look=look, url="http://x", log=lambda *a: None)
    assert done == str(folder / "styled" / "manifest.json")
    made = json.loads((folder / "styled" / "manifest.json").read_text())
    assert made["folder"] == str((folder / "styled").resolve()) and made["styled"]["strength"] == repaint.TRIES[0][0]
    assert made["parts"] == json.loads((folder / "manifest.json").read_text())["parts"] and made["labels"][0]["slug"] == "evaporation"
    # the library's own drawing is untouched; the repainted scene, art and whole drawing are new files beside it
    assert (folder / "base.png").read_bytes() == original
    assert (folder / "styled" / "base.png").read_bytes() != original
    assert (folder / "styled" / "marks_00.png").read_bytes() == (folder / "marks_00.png").read_bytes()
    assert all((folder / "styled" / name).is_file() for name in ("art.png", "whole.png", "compared_1.jpg"))
    # the arrow lies on the repainted art where the drawing has it, pixel for pixel
    assert Image.open(folder / "styled" / "art.png").convert("RGB").getpixel((155, 100)) == Image.open(folder / "art.png").convert("RGB").getpixel((155, 100))
    # the prompt does not name what is in the picture: told "water drops", the model painted more of them
    assert len(painter) == 1 and "drop" not in painter[0][2].lower() and "sea" not in painter[0][2].lower()
    # decided once: asked again, nothing is painted and nobody is asked
    assert repaint.styled(folder / "manifest.json", look=look, url="http://x", log=lambda *a: None) == done
    assert len(painter) == 1 and look.asked == {"kind": 1, "same": 1}
    assert repaint.styled(done, look=look, url="http://x") == done          # a repainted drawing is not repainted again


def test_a_repainting_that_is_not_the_same_scene_is_tried_again_and_then_left(tmp_path, painter):
    said = []
    folder, look = poster(tmp_path), judge(verdicts=["gone", "different", "same"])
    done = repaint.styled(folder / "manifest.json", look=look, url="http://x", log=said.append)
    # the third try was accepted: another seed first, then more gently
    assert done and [(strength, seed) for strength, seed, _ in painter] == list(repaint.TRIES[:3])
    assert json.loads((folder / "styled" / "manifest.json").read_text())["styled"]["strength"] == repaint.TRIES[2][0]
    assert sum("not the same drawing" in line for line in said) == 2 and "three drops: gone" in said[0]

    other = poster(tmp_path / "second")
    never = judge(verdicts=["gone"] * len(repaint.TRIES))
    painter.clear()
    assert repaint.styled(other / "manifest.json", look=never, url="http://x", log=lambda *a: None) is None
    assert len(painter) == len(repaint.TRIES) and not (other / "styled" / "manifest.json").exists()
    refused = json.loads((other / "styled" / "refused.json").read_text())
    assert "not the same scene" in refused["why"] and len(refused["detail"]) == len(repaint.TRIES)
    # a refusal is kept too: the same drawing is not painted, or looked at, a second time
    painter.clear()
    assert repaint.styled(other / "manifest.json", look=never, url="http://x", log=lambda *a: None) is None and not painter


def test_something_added_is_a_refusal_as_much_as_something_gone(tmp_path, painter):
    folder = poster(tmp_path)
    look = judge(verdicts=["same", "same"], new=["an extra cloud, top right"])
    assert repaint.styled(folder / "manifest.json", look=look, url="http://x", log=lambda *a: None)
    assert len(painter) == 2                                              # the first try had a cloud nobody drew


def test_only_a_scene_of_things_and_places_is_repainted(tmp_path, painter):
    folder = poster(tmp_path)
    look = judge(kind="inside")
    assert repaint.styled(folder / "manifest.json", look=look, url="http://x", log=lambda *a: None) is None
    assert not painter and "not a scene" in json.loads((folder / "styled" / "refused.json").read_text())["why"]
    assert repaint.styled(folder / "manifest.json", look=look, url="http://x") is None and look.asked["kind"] == 1
    # a drawing with no scene layer (a typeset one, an anatomy drawing) is never a candidate, and nobody is asked
    plain = poster(tmp_path / "plain", base=False)
    assert repaint.styled(plain / "manifest.json", look=look, url="http://x") is None and look.asked["kind"] == 1


def test_nothing_is_kept_when_nobody_could_answer(tmp_path, painter):
    folder = poster(tmp_path)
    assert repaint.styled(folder / "manifest.json", look=None, url=None) is None                  # no judge, no model
    assert repaint.styled(folder / "manifest.json", look=judge(kind=""), url="http://x", log=lambda *a: None) is None
    assert repaint.styled(folder / "manifest.json", look=judge(verdicts=[None]), url="http://x", log=lambda *a: None) is None
    assert not (folder / "styled" / "refused.json").exists() and not (folder / "styled" / "manifest.json").exists()
    # ... so the next lesson that shows this drawing asks again
    assert repaint.kept(folder, json.loads((folder / "manifest.json").read_text())) == (False, None)


def test_a_thing_the_judge_does_not_answer_for_is_not_the_same():
    before = Image.new("RGB", (64, 40), "white")

    def half(prompt, system, jpeg):
        assert "1. the Sun (top left)" in prompt and "3. three drops (right)" in prompt
        return {"checks": [{"n": 1, "in_b": "same"}, {"n": "x", "in_b": "same"}, {"n": 9, "in_b": "same"}], "new_in_b": []}
    found = repaint.changes(before, before, half, THINGS)
    assert [(c["thing"], c["how"]) for c in found] == [("the sea", "not answered"), ("three drops", "not answered")]
    assert repaint.changes(before, before, lambda *a: {"checks": "none"}, THINGS) is None


def test_a_small_thing_the_repainting_lost_is_put_back_and_what_it_kept_is_left(tmp_path):
    scene = Image.open(poster(tmp_path) / "base.png")
    painted = Image.eval(scene.convert("RGB"), lambda v: min(255, v + 8))
    ImageDraw.Draw(painted).rectangle([196, 94, 234, 120], fill="#c7e7ff")          # the model painted sky over the drops
    assert painted.getpixel((202, 103))[2] > 200 and painted.getpixel((202, 103))[0] > 150
    back, count = repaint.restore_small(scene, painted)
    assert count == 3
    red, green, blue = back.getpixel((202, 103))
    assert blue > 150 and red < 90                                          # the drop is the drawing's own again
    assert back.getpixel((45, 45)) == painted.getpixel((45, 45))            # the Sun, which it kept, is as it painted it
    kept = Image.eval(scene.convert("RGB"), lambda v: min(255, v + 8))             # a repainting that lost nothing
    same, none = repaint.restore_small(scene, kept)
    assert none == 0 and same.getpixel((202, 103)) == kept.getpixel((202, 103))


def test_a_lessons_beats_are_pointed_at_the_repainted_drawing(tmp_path, painter, monkeypatch):
    monkeypatch.setenv("HARNESS_REPAINT", "1")
    folder = poster(tmp_path)
    path = str(folder / "manifest.json")
    lesson = {"chapters": [{"beats": [{"figure": {"kind": "diagram", "manifest": path, "ask": "the water cycle"}},
                                      {"figure": {"kind": "picture", "file": "/x.png"}}, {"figure": None}]},
                           {"beats": [{"figure": {"kind": "diagram", "manifest": path, "labels": ["evaporation"]}}]}]}
    assert repaint.candidates(lesson) == {path: "the water cycle"}

    class Up:
        def __enter__(self):
            return "http://x"

        def __exit__(self, *a):
            return False
    started = []
    monkeypatch.setattr(repaint, "server", lambda log=print: started.append(1) or Up())
    assert repaint.restyle_lesson(lesson, look=judge(), log=lambda *a: None) == {"asked": 1, "repainted": 1, "kept_as_drawn": 0}
    new = str(folder / "styled" / "manifest.json")
    assert [b["figure"]["manifest"] for c in lesson["chapters"] for b in c["beats"] if (b["figure"] or {}).get("kind") == "diagram"] == [new, new]
    assert lesson["chapters"][1]["beats"][0]["figure"]["labels"] == ["evaporation"] and started == [1]
    # the same drawing in another lesson: decided before, so no image server is started and nothing is painted
    painter.clear()
    again = {"chapters": [{"beats": [{"figure": {"kind": "diagram", "manifest": path}}]}]}
    assert repaint.restyle_lesson(again, look=judge(), log=lambda *a: None)["repainted"] == 1
    assert again["chapters"][0]["beats"][0]["figure"]["manifest"] == new and started == [1] and not painter


def test_no_room_on_a_gpu_leaves_the_drawing_as_drawn(tmp_path, painter, monkeypatch):
    monkeypatch.setenv("HARNESS_REPAINT", "1")
    monkeypatch.setenv("LESSONFORGE_HOME", str(tmp_path / "home"))
    monkeypatch.setattr(repaint, "_answers", lambda url, timeout=4.0: False)
    monkeypatch.setattr(repaint, "installed", lambda: True)
    monkeypatch.setattr(repaint, "gpu_room", lambda: [(0, 10.3), (3, 9.9)])
    said = []
    folder = poster(tmp_path)
    lesson = {"chapters": [{"beats": [{"figure": {"kind": "diagram", "manifest": str(folder / "manifest.json")}}]}]}
    assert repaint.restyle_lesson(lesson, look=judge(), log=said.append) == {"asked": 1, "repainted": 0, "kept_as_drawn": 1}
    assert any("no GPU has room" in line and "10 GB on GPU 0" in line for line in said) and not painter
    assert lesson["chapters"][0]["beats"][0]["figure"]["manifest"] == str(folder / "manifest.json")
    assert not (folder / "styled").exists()                                 # not decided: asked again when there is room


def test_free_memory_is_asked_of_torch_when_nvidia_smi_cannot_say(monkeypatch):
    asked = []

    class Done:
        def __init__(self, code, out):
            self.returncode, self.stdout = code, out

    def run(command, **kwargs):
        asked.append(command[0])
        if command[0] == "nvidia-smi":
            return Done(255, "Failed to initialize NVML: Driver/library version mismatch")
        return Done(0, "a warning\n[[0, 12.4], [4, 30.0], [2, 0.6]]\n")
    monkeypatch.setattr(repaint.subprocess, "run", run)
    assert repaint.gpu_room() == [(4, 30.0), (0, 12.4), (2, 0.6)] and asked[0] == "nvidia-smi" and len(asked) == 2
    monkeypatch.setattr(repaint.subprocess, "run", lambda command, **kw: Done(0, "0, 20480\n1, 4096\n"))
    assert repaint.gpu_room() == [(0, 20.0), (1, 4.0)]
