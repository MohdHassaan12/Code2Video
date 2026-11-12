"""A labelled diagram taken apart: its parts found, named from its own labels, and lit one at a time."""
import json

import numpy as np
import pytest

from lessonforge.harness import diagrams, writer

OFFICE_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 600">
 <defs><clipPath id="c"><rect width="1000" height="600"/></clipPath></defs>
 <g><g class="Slide"><g class="Page">
   <g class="Group"><path d="M 300,100 L 700,100 700,500 300,500 Z" fill="rgb(250,250,140)"/></g>
   <g class="Group"><circle cx="450" cy="300" r="60" fill="rgb(200,0,90)"/></g>
   <g class="com.sun.star.drawing.CustomShape"><rect x="590" y="190" width="30" height="20" fill="rgb(240,180,180)"/></g>
   <g class="com.sun.star.drawing.CustomShape"><g id="id1"><text><tspan x="60" y="305">Nucleus</tspan></text></g></g>
   <g class="com.sun.star.drawing.LineShape"><g id="id2"><path fill="none" stroke="rgb(147,147,147)" d="M 150,300 L 385,300"/></g></g>
   <g class="com.sun.star.drawing.CustomShape"><g id="id3"><text><tspan x="820" y="205">Mito</tspan><tspan x="820" y="225">chondria</tspan></text></g></g>
   <g class="com.sun.star.drawing.LineShape"><g id="id4"><path fill="none" stroke="rgb(147,147,147)" d="M 810,200 L 630,200"/></g></g>
 </g></g></g>
 <g id="anchored-labels"><text x="990" y="590">Art: Somebody, CC BY 3.0</text></g>
</svg>"""


def test_a_part_name_is_cut_the_way_a_steps_focus_is():
    import re
    for name in ("Golgi apparatus", "Rough endoplasmic reticulum", "Cell-membrane"):
        written = name.lower().replace(" ", "_").replace("-", "_")
        assert diagrams.slug(name) == re.sub(r"[^a-z0-9_]", "", written)[:24]     # writer.discipline's own cut


def test_an_office_export_is_read_into_parts_labels_with_pointers_and_a_credit(tmp_path):
    svg = tmp_path / "source.svg"
    svg.write_text(OFFICE_SVG, encoding="utf-8")
    found = diagrams.read(svg)
    assert len(found["parts"]) == 3                                   # the two groups and the lone shape; no words, no pointers
    assert [l["name"] for l in found["labels"]] == ["Nucleus", "Mito chondria"]
    assert found["labels"][0]["pointer"] == ((150.0, 300.0), (385.0, 300.0)) and found["labels"][0]["at"] == (60.0, 305.0)
    assert found["credit"] == "Art: Somebody, CC BY 3.0"
    assert found["container"].get("class") == "Page"                  # not the wrapper, where the whole drawing is one child


def test_a_drawing_with_too_many_shapes_keeps_the_biggest_parts_not_the_first(tmp_path, monkeypatch):
    dots = "".join(f'<circle cx="{i}" cy="5" r="1"/>' for i in range(8))
    big = '<g class="Group">' + "".join(f'<rect x="{i}" y="50" width="5" height="5"/>' for i in range(30)) + "</g>"
    svg = tmp_path / "source.svg"
    svg.write_text(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">{dots}{big}</svg>', encoding="utf-8")
    monkeypatch.setattr(diagrams, "MAX_PARTS", 3)
    found = diagrams.read(svg)
    assert 8 in found["parts"] and len(found["parts"]) == 3           # the organelle survives the cut; stray dots do not crowd it out


def _layer(name, x0, y0, x1, y1, shape=(200, 300)):
    alpha = np.zeros(shape, dtype=np.uint8)
    alpha[y0:y1, x0:x1] = 255
    return {"id": name, "alpha": alpha, "area": int((alpha > 40).sum())}


def test_a_label_names_the_smallest_layer_its_pointer_reaches():
    layers = [_layer("body", 20, 20, 280, 180), _layer("nucleus", 120, 80, 160, 120), _layer("dot", 200, 60, 206, 66)]
    labels = [{"name": "Nucleus", "from": [10, 100], "tip": [125, 100]},            # ends on it
              {"name": "Dot", "from": [290, 63], "tip": [215, 63]},                # stops nine pixels short
              {"name": "Cytoplasm", "from": [10, 170], "tip": [60, 165]},          # only the body is there
              {"name": "Title", "from": [5, 5], "tip": None}]
    diagrams.name_parts(labels, layers, 300, 200)
    assert [l["part"] for l in labels] == ["nucleus", "dot", None, None]
    assert labels[0]["found"] == "at the pointer's end" and "past the pointer's end" in labels[1]["found"]
    assert labels[2]["found"] == "only the body is there" and labels[3]["found"] == "no pointer"


def test_an_svg_with_a_script_or_an_outside_link_is_refused():
    assert diagrams.safe(b'<svg viewBox="0 0 1 1"><rect/></svg>') is None
    for bad in (b'<svg><script>alert(1)</script></svg>', b'<svg><image href="https://x.example/a.png"/></svg>',
                b'<svg onload="x()"></svg>', b'<svg><foreignObject/></svg>', b"<html></html>"):
        assert diagrams.safe(bad), bad


def _lesson(focuses, kind="diagram"):
    beats = [{"id": f"{i:02d}", "narration": "n", "figure": {"kind": kind, "junk": 1},
              "steps": [{"say": "s", "show": "x", "kind": "point", "focus": f}]} for i, f in enumerate(focuses, 1)]
    return {"chapters": [{"beats": beats}]}


READY = {"ask": "Labelled diagram of an animal cell", "manifest": "/lib/cell/manifest.json",
         "parts": ["nucleus", "golgi_apparatus", "mitochondria"], "credit": "Art: Somebody, CC BY 3.0",
         "names": {"nucleus": "Nucleus", "golgi_apparatus": "Golgi apparatus", "mitochondria": "Mitochondria"}}


def test_the_writers_diagram_becomes_the_prepared_one_and_only_real_parts_are_pointed_at():
    lesson = writer.use_diagram(_lesson(["nucleus", "golgiapparatus", "chloroplast", "nucleus"]), {"diagram": READY}, log=lambda *_: None)
    beats = lesson["chapters"][0]["beats"]
    assert all(b["figure"] == {"kind": "diagram", "manifest": "/lib/cell/manifest.json", "labels": ["nucleus", "golgi_apparatus"],
                               "ask": READY["ask"]} for b in beats)                  # the SAME figure on every beat, so it stays
    assert [b["steps"][0].get("focus") for b in beats] == ["nucleus", "golgi_apparatus", None, "nucleus"]
    assert lesson["credits"] == ["Art: Somebody, CC BY 3.0"]


def test_a_diagram_nobody_prepared_is_taken_out():
    lesson = writer.use_diagram(_lesson(["nucleus"]), None, log=lambda *_: None)
    assert "figure" not in lesson["chapters"][0]["beats"][0] and "credits" not in lesson
    kept = writer.use_diagram(_lesson(["a"], kind="bars"), {"diagram": READY}, log=lambda *_: None)
    assert kept["chapters"][0]["beats"][0]["figure"]["kind"] == "bars"               # other figures are left alone


def test_the_card_tells_the_writer_the_exact_names_it_may_point_at():
    from lessonforge.harness import card as teaching_card
    card = teaching_card.shape({"big_idea": {"text": "b"}, "diagram_ask": "Labelled diagram of an animal cell"})
    assert card["diagram_ask"] == "Labelled diagram of an animal cell" and "DIAGRAM IS READY" not in teaching_card.for_writer(card)
    card["diagram"] = READY
    told = teaching_card.for_writer(card)
    assert "A LABELLED DIAGRAM IS READY" in told and "nucleus, golgi_apparatus, mitochondria" in told and '{"kind": "diagram"}' in told


def test_a_part_lights_when_named_and_the_one_before_it_goes_out(tmp_path):
    pytest.importorskip("manim")
    from PIL import Image
    from lessonforge.longform import figures
    Image.new("RGBA", (200, 120), (250, 250, 140, 255)).save(tmp_path / "art.png")
    Image.new("RGBA", (40, 40), (200, 0, 90, 255)).save(tmp_path / "part_01.png")
    manifest = {"version": 2, "width": 400, "height": 200, "art": "art.png", "art_box": [100, 40, 300, 160], "folder": str(tmp_path),
                "credit": "Art: Somebody, CC BY 3.0",
                "parts": [{"id": "part_01", "png": "part_01.png", "box": [180, 80, 220, 120], "area": 1600}],
                "labels": [{"name": "Nucleus", "slug": "nucleus", "part": "part_01", "tip": [185, 100], "from": [60, 100]},
                           {"name": "Cytoplasm", "slug": "cytoplasm", "part": None, "tip": [250, 150], "from": [340, 170]},
                           {"name": "Vacuole", "slug": "vacuole", "part": None, "tip": [120, 60], "from": [30, 30]}]}
    (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    fig = figures.build({"kind": "diagram", "manifest": str(tmp_path / "manifest.json"), "labels": ["nucleus", "cytoplasm"]})
    assert fig is not None and fig.kind == "diagram" and set(fig.parts) == {"nucleus", "cytoplasm"}     # only the names the lesson uses
    assert figures.construct_animation(fig, run_time=1.0) is not None and fig.credit.startswith("Art:")
    layer = fig.labels["nucleus"]["layer"]
    assert abs(layer.get_center()[0] - fig.art.get_center()[0]) < 1e-6 and layer.height < fig.art.height   # exactly over its place
    first = fig.focus_animations("nucleus")
    assert len(first) == 4 and fig._lit is layer                       # art dims, layer lights, pointer and words are written
    second = fig.focus_animations("cytoplasm")
    assert fig._lit is None and fig._ring is fig.labels["cytoplasm"]["ring"] and len(second) >= 4       # the nucleus goes out, a ring comes
    assert len(fig.focus_animations("nucleus")) == 3                   # named before: it lights again, its label is not rewritten
    assert fig.focus_animations("chloroplast") == []
    words = fig.labels["nucleus"]["words"]
    assert fig.card.get_left()[0] < words.get_left()[0] and fig.card.get_right()[0] > fig.labels["cytoplasm"]["words"].get_right()[0]


def test_a_step_that_names_a_part_points_at_it_even_without_a_focus():
    ready = {**READY, "parts": ["cell_membrane", "mitochondria", "smooth_endoplasmic_retic", "rough_endoplasmic_reticu"],
             "names": {"cell_membrane": "Cell membrane", "mitochondria": "Mitochondria",
                       "smooth_endoplasmic_retic": "Smooth endoplasmic reticulum", "rough_endoplasmic_reticu": "Rough endoplasmic reticulum"}}
    lesson = _lesson([None, None, None, None, None])
    shows = ["Mitochondria: usable energy", "Membrane: exchange", "Reticulum carries proteins", "Rough endoplasmic reticulum", "Four jobs"]
    for beat, show in zip(lesson["chapters"][0]["beats"], shows):
        beat["steps"][0].update(show=show, focus=None)
    writer.use_diagram(lesson, {"diagram": ready}, log=lambda *_: None)
    got = [b["steps"][0].get("focus") for b in lesson["chapters"][0]["beats"]]
    # one word that only one part owns is enough; a word two parts share is not; nothing named, nothing lit
    assert got == ["mitochondria", "cell_membrane", None, "rough_endoplasmic_reticu", None]


# ── asking the service (2026-10-09: one waiting request, a key, a verdict on quality) ──────────────────

METER: list = []           # what the budget guard and the ledger were told (no test writes to the real ledger)


class _Reply:
    def __init__(self, body, status=200):
        self._body, self.status_code, self.ok = body, status, status < 400

    def json(self):
        return self._body


def _service(monkeypatch, tmp_path, post, get=None, key="k-123"):
    import requests
    calls = []
    monkeypatch.setattr(diagrams, "root", lambda *parts: (tmp_path.joinpath(*parts).mkdir(parents=True, exist_ok=True) or tmp_path.joinpath(*parts)))
    monkeypatch.setenv("DIAGRAM_API_URL", "https://diagrams.example/")
    monkeypatch.setenv("DIAGRAM_API_KEY", key) if key else monkeypatch.delenv("DIAGRAM_API_KEY", raising=False)
    monkeypatch.delenv("DIAGRAM_MIN_QUALITY", raising=False)
    monkeypatch.setattr(diagrams.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(diagrams.spend, "check", lambda estimate=0.0, what="": METER.append(("check", estimate)))
    monkeypatch.setattr(diagrams.spend, "record", lambda kind, model, cost, **kw: METER.append((kind, cost, kw.get("estimated"))))
    del METER[:]

    def posted(url, **kw):
        calls.append(("POST", url, kw))
        return post(url, **kw)

    def got(url, **kw):
        calls.append(("GET", url, kw))
        return get(url, **kw)

    monkeypatch.setattr(requests, "post", posted)
    monkeypatch.setattr(requests, "get", got)
    return calls


def test_one_waiting_request_carries_the_key_and_the_drawing_is_kept_so_it_is_never_asked_for_twice(tmp_path, monkeypatch):
    import base64
    png = base64.b64encode(b"\x89PNG-not-really").decode()
    calls = _service(monkeypatch, tmp_path, lambda url, **kw: _Reply({"svg": OFFICE_SVG, "png_base64": png, "quality": "student_ready", "seconds": 31}))
    said = []
    saved = diagrams.fetch("A school bus, side view", klass=8, language="hinglish", log=said.append, labels=False)
    kind, url, sent = calls[0]
    assert (kind, url) == ("POST", "https://diagrams.example/v1/diagrams") and sent["params"] == {"wait": 90}
    assert sent["headers"] == {"X-API-Key": "k-123"}
    assert sent["json"] == {"prompt": "A school bus, side view", "labels": False, "language": "hi", "class_level": 8,
                            "min_quality": "review_needed"}                    # told the least it may return, the service redraws by itself
    assert saved.read_text(encoding="utf-8") == OFFICE_SVG and (saved.parent / "source.png").read_bytes().startswith(b"\x89PNG")
    assert json.loads((saved.parent / "source.json").read_text())["quality"] == "student_ready" and "student ready" in said[-1]
    assert diagrams.fetch("A school bus, side view", klass=8, language="hinglish", log=said.append, labels=False) == saved
    assert len(calls) == 1                                           # the library's copy answered the second time
    assert METER == [("diagram", 0.0, False)]                        # the owner's own service: counted in the ledger, charged nothing
    labelled = diagrams.fetch("A school bus, side view", klass=8, language="hinglish", log=said.append)
    assert len(calls) == 2 and labelled.parent != saved.parent       # with and without labels are two drawings


def test_a_labelled_diagram_is_still_found_under_the_name_it_was_saved_with_before(tmp_path, monkeypatch):
    import hashlib
    calls = _service(monkeypatch, tmp_path, lambda url, **kw: _Reply({"svg": OFFICE_SVG}))
    ask = "Labelled diagram of an animal cell"
    old = hashlib.sha256(f"{ask.lower()}|8|hinglish".encode()).hexdigest()[:10]          # the key every saved diagram has
    folder = tmp_path / f"{diagrams.slug(ask)[:40]}-{old}"
    folder.mkdir()
    (folder / "source.svg").write_text(OFFICE_SVG, encoding="utf-8")
    assert diagrams.fetch(ask, klass=8, language="hinglish", log=lambda line: None) == folder / "source.svg" and not calls


def test_a_drawing_that_failed_the_services_own_checks_is_kept_aside_and_not_used(tmp_path, monkeypatch):
    calls = _service(monkeypatch, tmp_path, lambda url, **kw: _Reply({"svg": OFFICE_SVG, "quality": "failed_checks"}))
    said = []
    assert diagrams.fetch("Human heart with its four chambers", log=said.append) is None
    kept = list(tmp_path.glob("*/refused.svg"))
    assert len(kept) == 1 and not list(tmp_path.glob("*/source.svg")) and "failed checks" in said[-1]
    monkeypatch.setenv("DIAGRAM_MIN_QUALITY", "failed_checks")        # the owner may decide to look at everything
    assert diagrams.fetch("Human heart with its four chambers", log=said.append) is not None and len(calls) == 2
    monkeypatch.setenv("DIAGRAM_MIN_QUALITY", "student_ready")
    monkeypatch.setattr("requests.post", lambda url, **kw: _Reply({"svg": OFFICE_SVG, "quality": "review_needed"}))
    assert diagrams.fetch("A leaf cut across", log=said.append) is None and "review needed" in said[-1]


def test_a_slow_drawing_comes_back_as_an_id_and_is_asked_for_with_the_same_key(tmp_path, monkeypatch):
    answers = iter([{"id": "abc", "status": "running"}, {"id": "abc", "status": "done", "svg": OFFICE_SVG, "quality": "review_needed"}])
    calls = _service(monkeypatch, tmp_path, lambda url, **kw: _Reply({"id": "abc", "status": "queued"}),
                     get=lambda url, **kw: _Reply(next(answers)))
    saved = diagrams.fetch("Section of a flower", log=lambda line: None)
    assert saved is not None and [c[0] for c in calls] == ["POST", "GET", "GET"]
    assert calls[1][1] == "https://diagrams.example/v1/diagrams/abc" and calls[2][2]["headers"] == {"X-API-Key": "k-123"}


def test_a_drawing_from_the_owners_service_is_free_and_only_a_metered_one_asks_the_budget(tmp_path, monkeypatch):
    calls = _service(monkeypatch, tmp_path, lambda url, **kw: _Reply({"svg": OFFICE_SVG}))

    def no_room(estimate=0.0, what=""):
        raise diagrams.spend.BudgetExceeded("budget 35.00 USD: the key has used 36.87")

    monkeypatch.setattr(diagrams.spend, "check", no_room)
    said = []
    assert diagrams.fetch("Section of a stem", log=said.append) is not None and len(calls) == 1   # free: the budget is not asked
    monkeypatch.setenv("DIAGRAM_COST_ESTIMATE", "0.4")                   # a service that is metered one day
    assert diagrams.cost_estimate() == 0.4
    assert diagrams.fetch("Section of a root", log=said.append) is None and len(calls) == 1 and "was not asked for" in said[-1]
    monkeypatch.setenv("DIAGRAM_COST_ESTIMATE", "free")
    assert diagrams.cost_estimate() == 0.0


def test_without_a_key_the_log_says_which_line_is_missing_and_a_failed_job_ends_the_wait(tmp_path, monkeypatch):
    said = []
    _service(monkeypatch, tmp_path, lambda url, **kw: _Reply({"detail": "key"}, status=401), key="")
    assert diagrams.fetch("Section of a flower", log=said.append) is None and "DIAGRAM_API_KEY" in said[-1]
    calls = _service(monkeypatch, tmp_path, lambda url, **kw: _Reply({"id": "abc", "status": "queued"}),
                     get=lambda url, **kw: _Reply({"id": "abc", "status": "failed", "detail": "could not draw"}))
    assert diagrams.fetch("Section of a root", log=said.append) is None and "could not draw" in said[-1]
    assert [c[0] for c in calls] == ["POST", "GET", "POST", "GET"]            # a failed job ends the wait; it is asked for once more, not for ever


# ── the second kind of drawing: a flat poster with boxes of words (the water cycle, 2026-10-09) ──────────

POSTER_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 600"><title>The water cycle</title>
<rect x="0" y="0" width="1000" height="600" fill="#bde"/>
<line x1="700" y1="150" x2="690" y2="200" stroke="#2563eb" stroke-width="3"/>
<line x1="720" y1="150" x2="710" y2="200" stroke="#2563eb" stroke-width="3"/>
<circle cx="100" cy="100" r="50" fill="#fd0" stroke="#f59e0b"/>
<path d="M 150 500 Q 130 400 160 300" fill="none" stroke="#f97316" stroke-width="5"/>
<polygon points="160,300 145,318 165,322" fill="#f97316"/>
<rect x="30" y="380" width="200" height="80" rx="12" fill="#fff" stroke="#f97316"/>
<text x="42" y="405" font-weight="bold">1. Evaporation</text>
<text x="42" y="427">The sun heats water;</text>
<path d="M 500 100 Q 600 80 650 100" fill="none" stroke="#94a3b8" stroke-width="5"/>
<polygon points="650,100 634,93 627,112" fill="#94a3b8"/>
<rect x="760" y="190" width="180" height="80" rx="12" fill="#fff" stroke="#2563eb"/>
<text x="772" y="217" font-weight="bold">3. Precipitation</text>
<text x="772" y="239">Water falls as rain</text>
<rect x="700" y="500" width="240" height="50" rx="12" fill="#fff" stroke="#a16207"/>
<text x="712" y="525">Some water soaks into the</text>
<text x="712" y="545">ground (groundwater)</text>
<rect x="400" y="10" width="200" height="40" rx="14" fill="#eff" stroke="#1d4ed8"/>
<text x="500" y="38" text-anchor="middle" font-weight="bold">The water cycle</text>
</svg>"""


def test_a_box_of_words_becomes_one_label_and_the_arrows_drawn_for_it_are_its_part(tmp_path):
    svg = tmp_path / "source.svg"
    svg.write_text(POSTER_SVG, encoding="utf-8")
    found = diagrams.read(svg)
    by_name = {label["name"]: label for label in found["labels"]}
    assert list(by_name) == ["Evaporation", "Precipitation", "groundwater"]     # a heading without its number; a word in brackets; no title
    children = found["children"]
    kinds = lambda name: sorted(diagrams._tag(children[i]) for i in by_name[name]["marks"])  # noqa: E731
    assert kinds("Evaporation") == ["path", "polygon"]                           # the arrow just before its box, head and all
    assert kinds("Precipitation") == ["line", "line", "path", "polygon"]         # the arrow before it AND the rain in the box's own colour
    assert by_name["groundwater"]["marks"] == []                                 # a box before which nothing was drawn points at nothing
    drawn = {diagrams._tag(children[i]) for i in found["parts"]}
    boxes = [i for i, c in enumerate(children) if diagrams._tag(c) == "rect" and c.get("rx")]
    assert not set(boxes) & set(found["parts"]) and "text" not in drawn          # the boxes and their words leave the art
    assert all(label["pointer"] is None for label in found["labels"])            # so no layer has to be drawn to follow a pointer


def test_a_rect_with_words_somewhere_over_it_is_not_a_box_of_words():
    import xml.etree.ElementTree as ET
    sky = ET.fromstring('<svg xmlns="http://www.w3.org/2000/svg"><rect x="0" y="0" width="900" height="500"/>'
                        '<circle cx="5" cy="5" r="2"/><text x="100" y="100">Sun</text></svg>')
    assert diagrams.callouts(list(sky)) == []                                    # its words do not follow it directly


def test_the_browsers_window_is_asked_for_taller_than_the_drawing(tmp_path, monkeypatch):
    import xml.etree.ElementTree as ET
    from PIL import Image
    asked = []

    def run(command, **kw):
        asked.append(command)
        size = next(c for c in command if c.startswith("--window-size=")).split("=")[1].split(",")
        shot = next(c for c in command if c.startswith("--screenshot=")).split("=", 1)[1]
        # a headless window's page is shorter than the window: 87 px here
        Image.new("RGBA", (int(size[0]), int(size[1]) - 87), (10, 20, 30, 255)).save(shot)

    monkeypatch.setattr(diagrams.subprocess, "run", run)
    tree = ET.ElementTree(ET.fromstring(POSTER_SVG))
    image = diagrams._shot(tree, None, 200, 120, tmp_path, "whole", "chrome", words=True)
    assert image.shape[:2] == (120, 200)                                         # the whole drawing, cut back to its own size
    assert f"--window-size=200,{120 + diagrams.WINDOW_MARGIN}" in asked[0]
    monkeypatch.setattr(diagrams, "WINDOW_MARGIN", 40)                           # a page still shorter than the drawing is no picture
    assert diagrams._shot(tree, None, 200, 120, tmp_path, "whole", "chrome") is None


def test_a_posters_labels_stay_on_the_drawing_each_on_a_plate_and_the_card_is_the_art(tmp_path):
    pytest.importorskip("manim")
    from PIL import Image
    from lessonforge.longform import figures
    Image.new("RGBA", (400, 200), (180, 220, 250, 255)).save(tmp_path / "art.png")
    Image.new("RGBA", (30, 60), (240, 110, 20, 255)).save(tmp_path / "marks_00.png")
    manifest = {"version": 3, "style": "boxes", "width": 400, "height": 200, "art": "art.png", "art_box": [0, 0, 400, 200],
                "folder": str(tmp_path), "credit": "",
                "parts": [{"id": "marks_00", "png": "marks_00.png", "box": [60, 60, 90, 120], "area": 1800}],
                "labels": [{"name": "Evaporation", "slug": "evaporation", "part": "marks_00", "tip": [60, 100], "from": [50, 100]},
                           {"name": "Precipitation", "slug": "precipitation", "part": None, "tip": [370, 60], "from": [380, 60]}]}
    (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    fig = figures.build({"kind": "diagram", "manifest": str(tmp_path / "manifest.json")})
    for name in ("evaporation", "precipitation"):                       # both would have run past an edge of the drawing
        words, plate = fig.labels[name]["words"], fig.labels[name]["plate"]
        assert fig.art.get_left()[0] < words.get_left()[0] and words.get_right()[0] < fig.art.get_right()[0]
        assert plate is not None and plate.width > words.width and plate.get_fill_opacity() == 0
    assert abs(fig.card.width - (fig.art.width + 0.36)) < 1e-6          # the card hugs the art: no strip of white for the labels
    shown = fig.focus_animations("evaporation")
    assert len(shown) == 5                                              # art dims, arrows light, pointer, words and plate arrive
    assert figures.DiagramFigure.DIM >= 0.45                            # the picture stays a picture while a part is lit
    manifest["style"] = "pointers"                                      # a diagram with pointer lines keeps its labels in the margins
    (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    plain = figures.build({"kind": "diagram", "manifest": str(tmp_path / "manifest.json")})
    assert plain.labels["evaporation"]["plate"] is None and plain.card.width > plain.art.width + 0.5


# ── the picture a topic is KNOWN BY (the owner, 2026-10-09: "a visual, not just some arbitrary thing") ──────────

INERTIA = {"topic": "Newton's first law of motion (inertia)", "audience": "Class 9 students", "goal": "Explain why a moving object keeps moving"}
COIN = ("A coin resting on a card on top of a glass, and beside it the same glass after the card is flicked away "
        "sideways with the coin fallen straight down into the glass")


def test_a_topic_said_again_is_not_a_picture_and_a_described_one_is():
    asked = []

    def model(prompt, system):
        asked.append((prompt, system))
        return {"visuals": [{"ask": "Newton's first law of motion: inertia", "shows": "inertia", "kind": "standard diagram"},
                            {"ask": "Inertia diagram", "shows": "x", "kind": "x"},
                            {"ask": COIN, "shows": "A thing at rest stays at rest.", "kind": "demonstration"},
                            {"ask": COIN, "shows": "again", "kind": "demonstration"},
                            "nonsense"]}

    found = diagrams.visuals_for(INERTIA, model, log=lambda *_: None)
    assert [v["ask"] for v in found] == [COIN] and found[0]["kind"] == "demonstration"
    prompt, system = asked[0]
    assert "TOPIC: Newton's first law" in prompt and "CLASS: 9" in prompt
    assert diagrams.VISUAL_RULE in system and "Ask for a PICTURE, never for a topic" in system and "coin resting on a card" in system
    assert diagrams.visuals_for(INERTIA, lambda p, s: 1 / 0, log=lambda *_: None) == []      # no model answer, no picture
    assert diagrams.visuals_for(INERTIA, None) == []


def _drawing(tmp_path, name, labels, whole=True):
    folder = tmp_path / name
    folder.mkdir(parents=True, exist_ok=True)
    if whole:
        (folder / "whole.png").write_bytes(b"png")
    manifest = {"version": 3, "folder": str(folder), "whole": "whole.png", "labels": labels, "style": "boxes", "credit": ""}
    (folder / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    pointed = [l for l in labels if l.get("part") or l.get("tip")]
    return {"ask": name, "manifest": str(folder / "manifest.json"), "parts": [l["slug"] for l in pointed],
            "names": {l["slug"]: l["name"] for l in pointed}, "credit": "", "style": "boxes"}


def test_a_drawing_is_shown_by_its_parts_when_three_can_be_named_and_whole_otherwise(tmp_path):
    named = [{"name": n, "slug": n.lower(), "part": f"marks_{i:02d}", "tip": [1, 1]} for i, n in enumerate(("Evaporation", "Condensation", "Rain"))]
    assert diagrams.showable(_drawing(tmp_path, "cycle", named))["shown"] == "parts"
    whole = diagrams.showable(_drawing(tmp_path, "coin", []))                   # its words are outlines: nothing to name
    assert whole["shown"] == "whole" and whole["file"].endswith("coin/whole.png")
    assert diagrams.showable(_drawing(tmp_path, "empty", named[:1], whole=False)) is None and diagrams.showable(None) is None


def test_the_first_picture_in_the_teachers_order_that_can_be_shown_is_kept_for_the_topic(tmp_path, monkeypatch):
    monkeypatch.setenv("HARNESS_TOPIC_PICTURES", "1")
    monkeypatch.setattr(diagrams, "available", lambda: True)
    monkeypatch.setattr(diagrams, "root", lambda *parts: tmp_path.joinpath(*parts))
    drawn, models = [], []
    ready = {"A puck on ice with a force arrow drawn on it clearly": None,                # the service could not draw it
             COIN: _drawing(tmp_path, "coin", []),
             "A third picture that would also have been fine to use": _drawing(tmp_path, "third", [])}

    def prepare(ask, klass=None, language="en", log=print, subject=""):
        drawn.append((ask, klass, language))
        return ready[ask]

    def model(prompt, system):
        models.append(prompt)
        return {"visuals": [{"ask": a, "shows": "A thing at rest stays at rest.", "kind": "demonstration"} for a in ready]}

    monkeypatch.setattr(diagrams, "prepare", prepare)
    said = []
    got = diagrams.for_brief(INERTIA, llm=model, log=said.append)
    assert got["ask"] == COIN and got["shown"] == "whole" and got["shows"] == "A thing at rest stays at rest."
    assert [d[0] for d in drawn] == list(ready)[:2] and all(d[1:] == (9, "en") for d in drawn)   # one at a time; the third was never asked for
    assert "shown whole" in said[-1]
    kept = json.loads((tmp_path / "topics.json").read_text())
    assert list(kept.values())[0]["ask"] == COIN and "no usable drawing" in list(kept.values())[0]["tried"]
    again = diagrams.for_brief(INERTIA, llm=lambda p, s: 1 / 0, log=said.append)             # the choice is remembered
    assert again["shown"] == "whole" and len(models) == 1
    monkeypatch.setenv("HARNESS_TOPIC_PICTURES", "0")
    assert diagrams.for_brief(INERTIA, llm=model) is None                                    # switched off: nothing is asked


def test_a_topic_nothing_could_be_drawn_for_is_not_asked_about_again(tmp_path, monkeypatch):
    monkeypatch.setenv("HARNESS_TOPIC_PICTURES", "1")
    monkeypatch.setattr(diagrams, "available", lambda: True)
    monkeypatch.setattr(diagrams, "root", lambda *parts: tmp_path.joinpath(*parts))
    monkeypatch.setattr(diagrams, "prepare", lambda *a, **k: None)
    calls = []

    def model(prompt, system):
        calls.append(prompt)
        return {"visuals": [{"ask": COIN, "shows": "s", "kind": "demonstration"}]}

    assert diagrams.for_brief(INERTIA, llm=model, log=lambda *_: None) is None and len(calls) == 2      # one picture given: asked for more, once
    assert diagrams.for_brief(INERTIA, llm=model, log=lambda *_: None) is None and len(calls) == 2      # and then not asked about again


def test_a_lesson_with_no_card_is_written_on_its_topics_picture(tmp_path, monkeypatch):
    from lessonforge.harness import card as teaching_card
    whole = diagrams.showable(_drawing(tmp_path, "coin", []))
    picture = {**whole, "ask": COIN, "shows": "A thing at rest stays at rest.", "visual_kind": "demonstration"}
    monkeypatch.setattr(diagrams, "topic_pictures", lambda: True)
    monkeypatch.setattr(diagrams, "for_brief", lambda brief, llm=None, log=print: picture)
    seen = []

    def model(prompt, system):
        seen.append((prompt, system))
        return {"title": "Inertia", "thesis": "t", "anchor": "a coin on a card", "anchor_name": "the coin", "small_case": "one coin",
                "method": ["predict"], "glossary": [],
                "chapters": [{"title": f"Part {i}", "learning_goal": "g", "beats": [
                    {"narration": "The coin rests on the card over the glass and it stays where it is until something pushes it away from there, "
                                  "however long we wait and whatever else in the room is moving about.",
                     "visual": "v", "check": "c", "figure": {"kind": "diagram"},
                     "steps": [{"say": "coin rests on", "show": "Coin at rest", "kind": "point", "focus": "coin"}]}]} for i in range(7)]}

    brief = {"topic": INERTIA["topic"], "audience": "Class 9 students", "level": "foundation", "goal": "explain", "style": "tutor",
             "language": "en-IN", "framework": "concrete_first", "duration_minutes": 3}
    lesson = writer.write_lesson(brief, model, log=lambda *_: None)
    assert all(system == writer.SYSTEM for _, system in seen)                    # the standing rules are untouched
    assert "A DRAWING IS READY" in seen[0][0] and COIN in seen[0][0] and "WHAT IT SHOWS: A thing at rest stays at rest." in seen[0][0]
    figures = [beat["figure"] for chapter in lesson["chapters"] for beat in chapter["beats"]]
    assert figures and all(f == {"kind": "picture", "file": whole["file"], "ask": COIN} for f in figures)
    assert not any("focus" in step for chapter in lesson["chapters"] for beat in chapter["beats"] for step in beat["steps"])
    assert lesson["picture"]["shown"] == "whole" and lesson["picture"]["ask"] == COIN
    named = {"ask": "Water cycle", "parts": ["evaporation", "condensation", "rain"], "shown": "parts", "shows": "Water goes round."}
    assert "A LABELLED DIAGRAM IS READY" in teaching_card.block_for(named) and "WHAT IT SHOWS: Water goes round." in teaching_card.block_for(named)
    assert teaching_card.block_for(None) == "" and "It is shown whole" in teaching_card.block_for(picture)
    # A caller that keeps written scripts looks for the picture itself and hands it in: the writer then asks nobody.
    monkeypatch.setattr(diagrams, "for_brief", lambda *a, **k: 1 / 0)
    seen.clear()
    handed = writer.write_lesson(brief, model, log=lambda *_: None, picture=picture)
    assert handed["picture"]["ask"] == COIN and "A DRAWING IS READY" in seen[0][0]
    seen.clear()
    bare = writer.write_lesson(brief, model, log=lambda *_: None, picture=False)       # "looked, there is none"
    assert "picture" not in bare and "A DRAWING IS READY" not in seen[0][0]
    assert not any(beat.get("figure") for chapter in bare["chapters"] for beat in chapter["beats"])   # nothing prepared: the mark is removed


def test_a_layer_every_label_points_into_is_the_drawing_itself_and_not_a_part(tmp_path, monkeypatch):
    """The heart came from the service as one group: all ten labels "named" it and each lit the whole heart."""
    import numpy as np
    svg = tmp_path / "source.svg"
    labels = "".join(f'''<g class="com.sun.star.drawing.CustomShape"><text><tspan x="10" y="{40 + 40 * i}">Part {i}</tspan></text></g>
        <g class="com.sun.star.drawing.LineShape"><path fill="none" stroke="rgb(1,1,1)" d="M 60,{40 + 40 * i} L 200,{40 + 40 * i}"/></g>''' for i in range(4))
    svg.write_text(f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 200"><g><g class="Slide"><g class="Page">
        <g class="Group"><rect x="180" y="20" width="120" height="170" fill="rgb(200,0,0)"/></g>
        <g class="Group"><circle cx="350" cy="30" r="8" fill="rgb(0,0,200)"/></g>{labels}</g></g></g></svg>''', encoding="utf-8")

    def shot(tree, keep, width, height, folder, name, chrome, words=False, view=None):
        image = np.zeros((height, width, 4), dtype=np.uint8)
        scale = width / 400
        if keep is None or 0 in keep:
            image[int(20 * scale):int(190 * scale), int(180 * scale):int(300 * scale)] = (200, 0, 0, 255)
        if keep is None or 1 in keep:
            image[int(22 * scale):int(38 * scale), int(342 * scale):int(358 * scale)] = (0, 0, 200, 255)
        return image

    monkeypatch.setattr(diagrams, "_shot", shot)
    monkeypatch.setattr(diagrams, "browser", lambda: "chrome")
    manifest = diagrams.take_apart(svg, log=lambda *_: None, width=400)
    assert [label["part"] for label in manifest["labels"]] == [None] * 4 and manifest["parts"] == []
    assert all(label["tip"] and label["found"] == "the drawing is in one piece there" for label in manifest["labels"])
    assert len(diagrams.pointable(manifest)) == 4                     # still pointed at: a ring at each pointer's end



def test_a_pointer_written_before_its_words_is_that_labels_own(tmp_path):
    """The service's anatomy drawings write line, dot, words: read as "the line after the words", every name was one place off."""
    svg = tmp_path / "source.svg"
    svg.write_text('''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 600">
      <g><path d="M 400 100 L 700 100 700 500 400 500 Z" fill="#c00"/></g>
      <g>
        <line x1="150" y1="120" x2="420" y2="150" stroke="#555"/><circle cx="420" cy="150" r="3" fill="#555"/>
        <text x="140" y="124" text-anchor="end">Right atrium</text>
        <line x1="150" y1="320" x2="450" y2="350" stroke="#555"/><circle cx="450" cy="350" r="3" fill="#555"/>
        <text x="140" y="324" text-anchor="end">Right ventricle</text>
        <line x1="850" y1="220" x2="650" y2="200" stroke="#555"/><circle cx="650" cy="200" r="3" fill="#555"/>
        <text x="860" y="224">Aorta</text>
      </g></svg>''', encoding="utf-8")
    found = diagrams.read(svg)
    tips = {label["name"]: label["pointer"] for label in found["labels"]}
    assert tips == {"Right atrium": ((150.0, 120.0), (420.0, 150.0)), "Right ventricle": ((150.0, 320.0), (450.0, 350.0)),
                    "Aorta": ((850.0, 220.0), (650.0, 200.0))}
    assert found["parts"] == []                     # no pointer and no pointer's dot is left behind as part of the drawing


def test_a_wide_two_panel_picture_is_relaid_with_the_second_panel_under_the_first():
    image = np.zeros((100, 600, 4), dtype=np.uint8)
    image[20:80, 30:230] = (200, 0, 0, 255)              # "before"
    image[30:90, 380:560] = (0, 0, 200, 255)             # "after", beyond an empty gutter
    relaid = diagrams.stacked(image)
    assert relaid is not None and relaid.shape[1] == 200 and relaid.shape[0] >= 60 + 60 + 8
    assert tuple(relaid[5, 100]) == (200, 0, 0, 255) and tuple(relaid[-5, 100]) == (0, 0, 200, 255)   # first on top, second below
    image[40:60, 230:380] = (0, 150, 0, 255)             # something joins the halves: it is one picture
    assert diagrams.stacked(image) is None
    square = np.zeros((300, 400, 4), dtype=np.uint8)
    square[10:290, 10:190] = (1, 1, 1, 255)
    square[10:290, 210:390] = (1, 1, 1, 255)
    assert diagrams.stacked(square) is None              # not wide: it fills its box as it is


# ── using the pieces (the owner, 2026-10-09: dim-and-light was "a raw way of using" a drawing) ─────────────

def test_an_arrows_path_is_read_from_the_svg_in_the_direction_it_is_drawn():
    import xml.etree.ElementTree as ET
    element = lambda text: ET.fromstring(text)  # noqa: E731
    assert diagrams._polyline(element('<line x1="1" y1="2" x2="3" y2="4"/>')) == [(1.0, 2.0), (3.0, 4.0)]
    curve = diagrams._polyline(element('<path d="M 150 585 Q 128 470 160 330" fill="none" stroke="#f97316"/>'))
    assert curve[0] == (150.0, 585.0) and curve[-1] == (160.0, 330.0) and len(curve) == 15
    assert all(curve[k][1] > curve[k + 1][1] for k in range(len(curve) - 1))            # it rises, as the arrow does
    assert diagrams._polyline(element('<path d="M 10 10 A 5 5 0 0 1 20 20"/>')) is None   # an arc: no path beats a wrong one
    assert diagrams._polyline(element('<circle cx="1" cy="1" r="1"/>')) is None


def test_a_drawing_that_names_its_own_parts_is_believed(tmp_path):
    svg = tmp_path / "source.svg"
    svg.write_text('''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 600">
      <rect x="0" y="0" width="1000" height="600" fill="#bde"/>
      <path data-part="Evaporation" d="M 150 500 Q 130 400 160 300" fill="none" stroke="#f97316"/>
      <polygon data-part="Evaporation" points="160,300 145,318 165,322" fill="#f97316"/>
      <g data-part="Rain"><line x1="700" y1="150" x2="690" y2="200" stroke="#00f"/><line x1="720" y1="150" x2="710" y2="200" stroke="#00f"/></g>
    </svg>''', encoding="utf-8")
    found = diagrams.read(svg)
    by_name = {label["name"]: label for label in found["labels"]}
    assert set(by_name) == {"Evaporation", "Rain"}
    assert [diagrams._tag(found["children"][i]) for i in by_name["Evaporation"]["marks"]] == ["path", "polygon"]
    assert by_name["Rain"]["named"] == "data-part" and len(by_name["Rain"]["marks"]) == 1


def test_a_two_panel_picture_gives_its_panels_and_where_each_sits_when_relaid(tmp_path):
    image = np.zeros((100, 600, 4), dtype=np.uint8)
    image[20:80, 30:230] = (200, 0, 0, 255)
    image[30:90, 380:560] = (0, 0, 200, 255)
    cut = diagrams.panels(image)
    assert [p.shape[:2] for p in cut] == [(60, 200), (60, 180)]
    relaid, boxes = diagrams.stacked(image, with_boxes=True)
    assert boxes[0] == [0, 0, 200, 60] and boxes[1][1] >= 60 + 8 and boxes[1][3] == relaid.shape[0]
    assert diagrams.panels(np.zeros((300, 400, 4), dtype=np.uint8)) == []
    # what a lesson is handed: the re-laid drawing, its panels and their places
    folder = tmp_path / "coin"
    folder.mkdir()
    for name in ("whole_stacked.png", "panel_1.png", "panel_2.png"):
        (folder / name).write_bytes(b"png")
    manifest = {"folder": str(folder), "whole": "whole.png", "whole_stacked": "whole_stacked.png", "panels": ["panel_1.png", "panel_2.png"],
                "panel_boxes": boxes, "labels": []}
    (folder / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    ready = diagrams.showable({"ask": "coin", "manifest": str(folder / "manifest.json"), "parts": [], "names": {}})
    assert ready["shown"] == "whole" and ready["file"].endswith("whole_stacked.png")
    assert [f.rsplit("/", 1)[-1] for f in ready["panels"]] == ["panel_1.png", "panel_2.png"] and ready["panel_boxes"] == boxes
    from lessonforge.harness import card as teaching_card
    told = teaching_card.picture_block({**ready, "shows": ""})
    assert "It has 2 panels" in told and '"focus": "panel2"' in told


def _png(path, size, colour=(10, 120, 200, 255)):
    from PIL import Image
    Image.new("RGBA", size, colour).save(path)


def test_a_poster_is_built_up_and_beads_run_along_its_arrows_wherever_the_figure_is_put(tmp_path):
    pytest.importorskip("manim")
    from lessonforge.longform import figures
    _png(tmp_path / "art.png", (400, 200))
    _png(tmp_path / "base.png", (400, 200), (180, 220, 250, 255))
    _png(tmp_path / "marks_00.png", (30, 120), (240, 110, 20, 255))
    manifest = {"version": 8, "style": "boxes", "width": 400, "height": 200, "art": "art.png", "base": "base.png",
                "art_box": [0, 0, 400, 200], "folder": str(tmp_path), "credit": "",
                "parts": [{"id": "marks_00", "png": "marks_00.png", "box": [60, 40, 90, 160], "area": 3600}],
                "labels": [{"name": "Evaporation", "slug": "evaporation", "part": "marks_00", "tip": [75, 100], "from": [120, 100],
                            "colour": "#f97316", "flows": [[[75, 160], [70, 100], [75, 40]]]},
                           {"name": "Sun", "slug": "sun", "part": None, "tip": None, "from": [300, 40], "flows": [], "colour": ""}]}
    (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    fig = figures.build({"kind": "diagram", "manifest": str(tmp_path / "manifest.json")})
    assert fig.mode == "built" and abs(fig.card.width - (fig.art.width + 0.36)) < 1e-6
    label = fig.labels["evaporation"]
    assert label["beads"] is not None and len(label["beads"]) >= 1 and fig.labels["sun"]["beads"] is None
    fig.scale(1.4).shift(np.array([-3.0, 0.5, 0.0]))                    # what fitting it into its box does, AFTER it is built
    shown = fig.focus_animations("evaporation")
    assert len(shown) == 5 and fig._flowing is None                     # asked while the step is PREPARED: nothing has started
    assert not label["beads"].get_updaters()
    shown[0].begin()                                                    # played, at the step's words: now the beads run
    assert fig._flowing is label["beads"]                               # arrows drawn in (kept), pointer, name and plate: nothing dims
    assert fig.art.get_fill_opacity() if hasattr(fig.art, "get_fill_opacity") else True
    assert label["beads"].get_updaters()
    for moment in (0.3, 0.6, 0.9):
        label["beads"].update(moment)
        for bead in label["beads"]:
            x, y = bead.get_center()[:2]
            assert fig.art.get_left()[0] < x < fig.art.get_right()[0] and fig.art.get_bottom()[1] < y < fig.art.get_top()[1]
            share = (x - fig.art.get_left()[0]) / fig.art.width
            assert 0.16 < share < 0.2                                   # on the arrow (x = 70 to 75 of 400), not where it had been
    after = fig.focus_animations("sun")
    assert fig._flowing is label["beads"] and label["beads"].get_updaters()        # still this process's turn until the next is played
    after[0].begin()
    assert fig._flowing is None and not label["beads"].get_updaters()  # the next subject: these beads stop, the arrows stay
    assert label["layer"] is not None

    # a later chapter is a render of its own: it opens with what the earlier ones drew in, and nothing moving
    later = figures.build({"kind": "diagram", "manifest": str(tmp_path / "manifest.json")})
    part, name = later.labels["evaporation"], later.labels["sun"]
    assert not part["shown"] and not name["shown"]
    later.resume(["evaporation", "a name it does not have"])
    assert part["shown"] and not name["shown"] and later._flowing is None and not part["beads"].get_updaters()
    again = later.focus_animations("evaporation")
    assert len(again) == 2 and later._flowing is None                   # already drawn in and named: its part again, and its beads when played
    again[0].begin()
    assert later._flowing is part["beads"]
    assert len(later.focus_animations("sun")) >= 1 and name["shown"]    # a name not resumed is still written when its turn comes


def test_an_anatomy_drawing_cross_fades_to_a_close_up_of_the_named_place(tmp_path):
    pytest.importorskip("manim")
    from lessonforge.longform import figures
    _png(tmp_path / "art.png", (300, 400), (240, 200, 200, 255))
    for name in ("detail_right_atrium.png", "detail_aorta.png"):
        _png(tmp_path / name, (300, 400), (200, 40, 60, 255))
    manifest = {"version": 9, "style": "pointers", "width": 600, "height": 600, "art": "art.png", "base": "", "art_box": [150, 100, 450, 500], "frame": 1.5,
                "folder": str(tmp_path), "credit": "Art: Somebody, CC BY 3.0", "parts": [],
                "labels": [{"name": "Right atrium", "slug": "right_atrium", "part": None, "tip": [250, 300], "from": [60, 300],
                            "detail": {"png": "detail_right_atrium.png", "box": [200, 230, 330, 403]}},
                           {"name": "Aorta", "slug": "aorta", "part": None, "tip": [320, 150], "from": [520, 150],
                            "detail": {"png": "detail_aorta.png", "box": [250, 100, 380, 273]}},
                           {"name": "Left ventricle", "slug": "left_ventricle", "part": None, "tip": None, "from": [520, 400]}]}
    (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    fig = figures.build({"kind": "diagram", "manifest": str(tmp_path / "manifest.json")})
    assert fig.mode == "zoomed" and set(fig.labels) == {"right_atrium", "aorta"}      # a name with nowhere to zoom to is not offered
    # An upright drawing gets a window 1.5 wide for 1 high, the whole drawing centred in it: the close-ups fill that.
    assert abs(fig.frame.width - 1.5 * fig.art.height) < 1e-6 and abs(fig.card.width - (fig.frame.width + 0.36)) < 1e-6
    assert abs(fig.art.get_center()[0] - fig.frame.get_center()[0]) < 1e-6 and fig.credit.startswith("Art:")
    first = fig.focus_animations("right_atrium")
    assert len(first) == 7 and fig._close is fig.labels["right_atrium"]              # close-up, ring, name, plate, region, overview x2
    close = fig.labels["right_atrium"]["close"]
    assert abs(close.width - fig.frame.width) < 1e-6 and abs(close.height - fig.frame.height) < 1e-6
    ring = fig.labels["right_atrium"]["ring"]
    assert fig.frame.get_left()[0] < ring.get_center()[0] < fig.frame.get_right()[0] and ring.get_fill_opacity() == 0
    second = fig.focus_animations("aorta")
    assert len(second) == 10 and fig._close is fig.labels["aorta"]                    # five things leave, five arrive
    assert fig.focus_animations("left_ventricle") == []


def test_a_pictures_second_panel_waits_for_its_step(tmp_path):
    pytest.importorskip("manim")
    from lessonforge.longform import figures
    _png(tmp_path / "whole_stacked.png", (200, 300), (255, 255, 255, 255))
    _png(tmp_path / "panel_1.png", (200, 120))
    _png(tmp_path / "panel_2.png", (180, 150))
    spec = {"kind": "picture", "file": str(tmp_path / "whole_stacked.png"), "ask": "coin and card",
            "panels": [str(tmp_path / "panel_1.png"), str(tmp_path / "panel_2.png")], "panel_boxes": [[0, 0, 200, 120], [10, 150, 190, 300]]}
    fig = figures.build(spec)
    assert fig.kind == "picture" and fig.parts == {} and len(fig.panels) == 2
    before, after = fig.panels
    assert after.get_center()[1] < before.get_center()[1] and before.get_top()[1] <= fig.art.get_top()[1] + 1e-6   # where it sits in the whole
    assert abs(after.width - 180 / 200 * fig.art.width) < 1e-6
    assert fig.focus_animations("coin") == [] and fig.focus_animations("panel5") == [] and fig.focus_animations("panel1") == []
    assert len(fig.focus_animations("panel2")) == 1
    whole = figures.build({"kind": "picture", "file": str(tmp_path / "whole_stacked.png"), "ask": "coin and card"})
    assert whole.panels == [] and whole.focus_animations("panel2") == []


# ── a drawing is looked at, and a wrong one is asked for again saying what was wrong ──────────────────────

def _prepared(tmp_path, name, ask):
    from PIL import Image
    folder = tmp_path / name
    folder.mkdir(parents=True, exist_ok=True)
    Image.new("RGBA", (300, 200), (200, 220, 240, 255)).save(folder / "whole.png")
    (folder / "source.json").write_text(json.dumps({"ask": ask}), encoding="utf-8")
    manifest = {"version": 9, "folder": str(folder), "whole": "whole.png", "labels": [], "style": "pointers", "credit": ""}
    (folder / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return {"ask": ask, "manifest": str(folder / "manifest.json"), "parts": [], "names": {}, "credit": "", "style": "pointers"}


def test_a_drawing_found_wrong_is_asked_for_again_with_what_was_wrong(tmp_path, monkeypatch):
    monkeypatch.setenv("HARNESS_JUDGE_PICTURES", "1")
    asked, looked = [], []

    def prepare(ask, klass=None, language="en", log=print, subject=""):
        asked.append(ask)
        return _prepared(tmp_path, f"try{len(asked)}", ask)

    def look(prompt, system, jpeg):
        looked.append((prompt, system, len(jpeg)))
        return ({"shows": False, "readable": True, "problems": ["two bars lie across the flower", "the stigma is not labelled"]}
                if len(looked) == 1 else {"shows": True, "readable": True, "problems": []})

    monkeypatch.setattr(diagrams, "prepare", prepare)
    said = []
    ready = diagrams.prepare_checked("Parts of a flower cut open, with petal, sepal, stigma and ovary labelled", 6, "en", log=said.append, look=look)
    assert ready["shown"] == "whole" and ready["ask"].startswith("Parts of a flower") and ready["judged"]["ok"] is True
    assert len(asked) == 2 and "Draw it again and avoid what was wrong with the last drawing: two bars lie across the flower" in asked[1]
    assert "THE REQUEST: Parts of a flower" in looked[0][0] and "Look only at the picture" in looked[0][1] and looked[0][2] > 100
    assert any("looked at and found wrong (two bars lie across the flower" in line and "asking for it again" in line for line in said)
    assert json.loads((tmp_path / "try1" / "judged.json").read_text())["ok"] is False        # the verdict is kept beside the drawing
    assert diagrams.judge(_prepared(tmp_path, "try1", "x"), look=lambda *a: 1 / 0)["ok"] is False   # and not asked for twice


def test_two_wrong_drawings_mean_no_picture_and_nobody_looking_means_it_is_used(tmp_path, monkeypatch):
    monkeypatch.setenv("HARNESS_JUDGE_PICTURES", "1")
    count, where = [], ["bad"]
    monkeypatch.setattr(diagrams, "prepare", lambda ask, klass=None, language="en", log=print, subject="":
                        count.append(ask) or _prepared(tmp_path, f"{where[0]}{len(count)}", ask))
    said = []
    wrong = lambda prompt, system, jpeg: {"shows": True, "readable": False, "problems": ["labels overlap"]}  # noqa: E731
    assert diagrams.prepare_checked("A simple circuit with a cell, a switch and a bulb", log=said.append, look=wrong) is None
    assert len(count) == diagrams.JUDGE_TRIES == 3 and "not used" in said[-1]
    count.clear()
    where[0] = "unseen"                                   # another drawing: nothing kept beside it yet
    broken = lambda prompt, system, jpeg: 1 / 0  # noqa: E731
    used = diagrams.prepare_checked("A food chain of grass, grasshopper, frog and snake", log=said.append, look=broken)
    assert used is not None and used["judged"] is None and len(count) == 1               # the look failed: the drawing is used as before
    monkeypatch.setenv("HARNESS_JUDGE_PICTURES", "0")
    assert diagrams.judge(used, look=wrong) is None



# ── a lesson made with a card asks for its picture whether or not the card's model thought to (2026-10-09) ────

def test_a_card_that_names_no_drawing_still_gets_its_topics_picture(tmp_path, monkeypatch):
    from lessonforge.harness import card as teaching_card
    from lessonforge.harness import library
    monkeypatch.setenv("HARNESS_TOPIC_PICTURES", "1")
    monkeypatch.setattr(diagrams, "available", lambda: True)
    picture = {"manifest": str(tmp_path / "m.json"), "shown": "parts", "parts": ["evaporation", "condensation", "precipitation"]}
    asked, checked = [], []
    monkeypatch.setattr(diagrams, "for_brief", lambda brief, llm=None, log=print: asked.append(brief) or picture)
    monkeypatch.setattr(diagrams, "prepare_checked", lambda *a, **k: checked.append(a) or None)
    card = {"topic": "Water cycle", "klass": 7, "diagram_ask": "",
            "picture": {"text": "a sea, land with one tree and a blank sky; arrows rise, a cloud forms, rain falls", "standard": "the water cycle diagram"}}
    typed = {"topic": "watr cycel", "audience": "new learners", "language": "hinglish", "goal": "say where rain comes from"}
    assert teaching_card.add_diagram(card, typed, log=lambda *_: None) is True and card["diagram"] is picture
    assert checked == []                                                # the card asked for nothing itself
    sent = asked[0]
    assert sent["topic"] == "Water cycle"                               # the topic as it was READ, not as it was typed
    assert library.school_class(sent) == 7                              # the class the sources were found for
    assert sent["picture_plan"].startswith("the water cycle diagram a sea, land with one tree")
    assert typed == {"topic": "watr cycel", "audience": "new learners", "language": "hinglish", "goal": "say where rain comes from"}

    # the card's own request comes first; the topic's picture only when that drawing cannot be used
    asked.clear()
    own = {**card, "diagram_ask": "Labelled diagram of the water cycle with a sea, a cloud and rain"}
    own.pop("diagram")
    assert teaching_card.add_diagram(own, typed, log=lambda *_: None) is True and own["diagram"] is picture
    assert checked[0][0] == own["diagram_ask"] and checked[0][1] == 7 and len(asked) == 1
    good = {"manifest": str(tmp_path / "g.json"), "shown": "whole"}
    monkeypatch.setattr(diagrams, "prepare_checked", lambda *a, **k: good)
    asked.clear()
    mine = {**own}
    mine.pop("diagram")
    assert teaching_card.add_diagram(mine, typed, log=lambda *_: None) is True and mine["diagram"] is good and asked == []

    # switched off, or no service: a card without a request gets nothing, as before
    monkeypatch.setenv("HARNESS_TOPIC_PICTURES", "0")
    bare = {"topic": "Water cycle", "klass": 7, "diagram_ask": ""}
    assert teaching_card.add_diagram(bare, typed, log=lambda *_: None) is False and "diagram" not in bare and asked == []


def test_the_one_who_thinks_of_a_picture_is_told_the_cards_plan_only_when_there_is_one():
    seen = []

    def model(prompt, system):
        seen.append(prompt)
        return {"visuals": [{"ask": COIN, "shows": "A thing at rest stays at rest.", "kind": "demonstration"}]}

    diagrams.visuals_for(INERTIA, model, log=lambda *_: None)
    diagrams.visuals_for({**INERTIA, "picture_plan": "a coin on a card over a tumbler; the card is flicked away"}, model, log=lambda *_: None)
    assert "THE LESSON'S PLAN FOR ITS ONE PICTURE" not in seen[0] and seen[0].count("\n") == 2          # no card: the request as it always was
    assert seen[1].startswith(seen[0]) and "make it the FIRST visual" in seen[1] and "the card is flicked away" in seen[1]


def test_a_cards_request_for_a_drawing_is_not_cut_short():
    from lessonforge.harness import card as teaching_card
    long = ("A coin resting on a card on top of a glass, and beside it the same glass after the card is flicked away "
            "sideways with the coin fallen straight down into the glass")
    assert len(long) > 120 and teaching_card.shape({"big_idea": {"text": "b"}, "diagram_ask": long})["diagram_ask"] == long


# ── the judge is read for what IT breaks (2026-10-09: a textbook water cycle thrown away over the colour of its arrows) ──

def test_the_judge_is_told_a_request_is_not_a_specification():
    said = diagrams.JUDGE_SYSTEM
    assert "it is not a\nspecification" in said and "NEVER a fault: a colour" in said and '("collection" for "runoff")' in said
    assert "something extra that is correct" in said


def test_a_verdict_belongs_to_the_judge_that_gave_it(tmp_path, monkeypatch):
    monkeypatch.setenv("HARNESS_JUDGE_PICTURES", "1")
    from PIL import Image
    Image.new("RGBA", (40, 30), (10, 120, 200, 255)).save(tmp_path / "whole.png")
    ready = {"manifest": str(tmp_path / "manifest.json"), "ask": "The water cycle with its arrows labelled"}
    (tmp_path / "judged.json").write_text(json.dumps({"ok": False, "shows": False, "readable": True,
                                                      "problems": ["evaporation arrows are orange, not blue"]}))   # the old judge
    looks = []

    def look(prompt, system, image):
        looks.append(system)
        return {"shows": True, "readable": True, "problems": []}

    verdict = diagrams.judge(ready, look=look, log=lambda *_: None)
    assert verdict["ok"] and verdict["judge"] == diagrams.JUDGE_VERSION and len(looks) == 1        # looked at again
    assert diagrams.judge(ready, look=lambda *a: 1 / 0, log=lambda *_: None) == verdict             # and then kept


def test_a_topic_an_older_judge_turned_down_is_asked_about_again(tmp_path, monkeypatch):
    monkeypatch.setenv("HARNESS_TOPIC_PICTURES", "1")
    monkeypatch.setattr(diagrams, "available", lambda: True)
    monkeypatch.setattr(diagrams, "root", lambda *parts: tmp_path.joinpath(*parts))
    from lessonforge.harness import library
    key = f"{library.slug(INERTIA['topic'])}|{library.school_class(INERTIA)}"
    (tmp_path / "topics.json").write_text(json.dumps({key: {"topic": INERTIA["topic"], "ask": "", "tried": "no usable drawing"}}))
    drawing = _drawing(tmp_path, "coin", [])
    monkeypatch.setattr(diagrams, "prepare", lambda *a, **k: drawing)
    calls = []

    def model(prompt, system):
        calls.append(prompt)
        return {"visuals": [{"ask": COIN, "shows": "A thing at rest stays at rest.", "kind": "demonstration"}]}

    got = diagrams.for_brief(INERTIA, llm=model, log=lambda *_: None)
    assert got and got["ask"] == COIN and len(calls) == 2                                           # the old "nothing" did not stand (one picture given: asked for more)
    kept = json.loads((tmp_path / "topics.json").read_text())[key]
    assert kept["ask"] == COIN and kept["judge"] == "off"                                           # judging is off in tests


def test_a_cards_one_picture_has_the_topics_own_pictures_behind_it(tmp_path, monkeypatch):
    monkeypatch.setenv("HARNESS_TOPIC_PICTURES", "1")
    monkeypatch.setattr(diagrams, "available", lambda: True)
    monkeypatch.setattr(diagrams, "root", lambda *parts: tmp_path.joinpath(*parts))
    custom = "A landscape with a blue sea, green land with one tree and a yellow Sun, with arrows rising"
    textbook = "A standard diagram of the water cycle with evaporation, condensation and precipitation labelled"
    drawing = _drawing(tmp_path, "cycle", [])
    asked, prompts = [], []

    def prepare(ask, klass=None, language="en", log=print, subject=""):
        asked.append(ask)
        return drawing if ask == textbook else None            # the service cannot draw the custom one

    def model(prompt, system):
        prompts.append(prompt)
        if "THE LESSON'S PLAN" in prompt:
            return {"visuals": [{"ask": custom, "shows": "Water goes round.", "kind": "standard diagram"}]}
        return {"visuals": [{"ask": custom, "shows": "Water goes round.", "kind": "standard diagram"},      # said again: tried once
                            {"ask": textbook, "shows": "Water goes round.", "kind": "standard diagram"}]}

    monkeypatch.setattr(diagrams, "prepare", prepare)
    brief = {"topic": "Water cycle", "audience": "class 7 students", "goal": "say where rain comes from",
             "picture_plan": "a sea, land with one tree and a blank sky; arrows rise, a cloud forms, rain falls"}
    got = diagrams.for_brief(brief, llm=model, log=lambda *_: None)
    assert got and got["ask"] == textbook and asked == [custom, textbook]
    assert len(prompts) == 2 and "THE LESSON'S PLAN" in prompts[0] and "THE LESSON'S PLAN" not in prompts[1]


def test_nothing_usable_is_a_note_for_a_day_not_for_good(tmp_path, monkeypatch):
    import time
    monkeypatch.setenv("HARNESS_TOPIC_PICTURES", "1")
    monkeypatch.setattr(diagrams, "available", lambda: True)
    monkeypatch.setattr(diagrams, "root", lambda *parts: tmp_path.joinpath(*parts))
    from lessonforge.harness import library
    key = f"{library.slug(INERTIA['topic'])}|{library.school_class(INERTIA)}"
    old = time.strftime("%Y-%m-%d %H:%M", time.localtime(time.time() - 30 * 3600))
    (tmp_path / "topics.json").write_text(json.dumps({key: {"topic": INERTIA["topic"], "ask": "", "judge": "off", "when": old,
                                                             "asking": diagrams.ASKING_VERSION}}))
    monkeypatch.setattr(diagrams, "prepare", lambda *a, **k: None)
    calls = []

    def model(prompt, system):
        calls.append(prompt)
        return {"visuals": [{"ask": COIN, "shows": "s", "kind": "demonstration"}]}

    assert diagrams.for_brief(INERTIA, llm=model, log=lambda *_: None) is None and len(calls) == 2      # a day old: asked again (and for more)
    assert diagrams.for_brief(INERTIA, llm=model, log=lambda *_: None) is None and len(calls) == 2      # just now: not again



def test_drawings_can_be_taken_apart_several_at_once(tmp_path):
    """A script's pictures are asked for three at a time: together must give what one at a time gives."""
    import concurrent.futures
    if diagrams.browser() is None:
        pytest.skip("no headless browser on this machine")
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 300" width="400" height="300">'
           '<g><circle cx="{x}" cy="150" r="60" fill="#3b82f6"/></g><g><rect x="250" y="90" width="90" height="120" fill="#22c55e"/></g></svg>')
    folders = []
    for n in range(4):
        folder = tmp_path / f"d{n}"
        folder.mkdir()
        (folder / "source.svg").write_text(svg.format(x=90 + 10 * n))
        folders.append(folder)
    tree = [diagrams.ET.parse(f / "source.svg") for f in folders]

    def shot(n):
        return diagrams._shot(tree[n], None, 400, 300, folders[n], "art", diagrams.browser())

    alone = [shot(n) for n in range(4)]
    with concurrent.futures.ThreadPoolExecutor(4) as pool:
        together = list(pool.map(shot, range(4)))
    assert all(a is not None and b is not None and a.shape == (300, 400, 4) and (a == b).all() for a, b in zip(alone, together))
    assert not (alone[0] == alone[3]).all()                                   # each got its OWN drawing back, not a neighbour's
    assert all(sorted(p.name for p in f.iterdir()) == ["source.svg"] for f in folders)      # nothing left behind


# ── "as many as from the drawings" (the owner, 2026-10-09): a scene is offered to the drawing service first ──

def test_scenes_are_turned_into_requests_and_each_distinct_one_is_drawn_once(monkeypatch):
    first = "A standard diagram of the water cycle showing the Sun, a sea, a cloud and rain with arrows"
    other = "A labelled diagram of a pot of boiling water showing steam rising to a cold lid"
    prompts, drawn = [], []

    def model(prompt, system):
        prompts.append((prompt, system))
        return {"pictures": [{"scene": 1, "ask": first}, {"scene": 2, "same_as": 1}, {"scene": 3, "ask": "too short"},
                             {"scene": 4, "ask": other}, {"scene": 5, "same_as": 9}, {"scene": 9, "ask": first}, "junk"]}

    def checked(ask, klass=None, language="en", log=print, look=None):
        drawn.append((ask, klass, language))
        return None if ask == other else {"ask": ask, "manifest": f"/lib/{len(drawn)}/manifest.json", "shown": "whole"}

    monkeypatch.setattr(diagrams, "prepare_checked", checked)
    scenes = [{"describe": f"scene {n}: first one thing appears, then another", "said": f"words {n}"} for n in range(1, 6)]
    got = diagrams.stills_for(scenes, {"topic": "Water cycle", "audience": "class 7 students"}, llm=model, log=lambda *_: None)
    assert [g and g["ask"] for g in got] == [first, first, None, None, None]        # 2 shares 1's; 3 had no request; 4 could not be drawn
    assert sorted(drawn) == sorted([(first, 7, "en"), (other, 7, "en")])           # each distinct request once
    prompt, system = prompts[0]
    assert "SCENE 2: scene 2: first one thing appears" in prompt and "ITS WORDS: words 2" in prompt and "CLASS: 7" in prompt
    assert diagrams.VISUAL_RULE in system and "A still picture cannot move" in system and '"same_as"' in system
    assert diagrams.stills_for(scenes, {"topic": "Water cycle"}, llm=lambda p, s: 1 / 0, log=lambda *_: None) == [None] * 5
    assert diagrams.stills_for([], {"topic": "Water cycle"}, llm=model) == []


def _scene_lesson():
    def beat(n, describe, shows, **figure):
        return {"id": f"{n:02d}", "narration": f"Beat {n} talks about water.", "figure": {"kind": "scene", "describe": describe, **figure},
                "steps": [{"say": "talks about", "show": show, "kind": "point", "highlight": False, "focus": "arrow"} for show in shows]}
    return {"chapters": [
        {"beats": [beat(1, "A sea under the Sun; first the sea appears, then arrows rise.", ["Evaporation from the sea", "Sun warms water"]),
                   beat(2, "The same sea with a cloud; first vapour cools, then drops form.", ["Condensation makes a cloud"])]},
        {"beats": [beat(3, "A ball rolling down a ramp; first it is still, then it rolls.", ["Ball speeds up"]),
                   beat(4, "A scene already written.", ["Kept"], module="/cache/sim_x.py"),
                   {"id": "05", "narration": "n", "figure": {"kind": "bars", "values": [1, 2]}, "steps": []}]}]}


def test_a_lessons_scenes_become_the_services_drawings_and_the_rest_stay_scenes(tmp_path, monkeypatch):
    monkeypatch.setattr(diagrams, "topic_pictures", lambda: True)
    named = [{"name": n, "slug": n.lower(), "part": f"marks_{i:02d}", "tip": [1, 1]} for i, n in enumerate(("Evaporation", "Condensation", "Precipitation"))]
    cycle = diagrams.showable({**_drawing(tmp_path, "cycle", named), "ask": "A standard diagram of the water cycle showing sea, cloud and rain"})
    asked = []

    def stills(scenes, brief, log=print):
        asked.append(scenes)
        return [cycle, cycle, None]                         # two scenes share the drawing; the ramp could not be drawn

    said = []
    lesson = writer.drawings_for_scenes(_scene_lesson(), {"topic": "Water cycle"}, log=said.append, stills=stills)
    beats = [b for c in lesson["chapters"] for b in c["beats"]]
    assert [s["describe"][:10] for s in asked[0]] == ["A sea unde", "The same s", "A ball rol"]     # the written scene and the bars were not offered
    assert asked[0][0]["said"] == "Beat 1 talks about water."
    assert beats[0]["figure"] == beats[1]["figure"] == {"kind": "diagram", "manifest": cycle["manifest"],
                                                         "labels": ["evaporation", "condensation"], "ask": cycle["ask"]}
    assert [s.get("focus") for s in beats[0]["steps"]] == ["evaporation", None] and beats[1]["steps"][0]["focus"] == "condensation"
    assert beats[2]["figure"]["kind"] == "scene" and beats[3]["figure"]["module"] == "/cache/sim_x.py" and beats[4]["figure"]["kind"] == "bars"
    assert lesson["pictures"] == [{"ask": cycle["ask"], "shown": "parts", "beats": ["01", "02"]}]
    assert "2 beat(s) show 1 drawing(s) from the service" in said[-1] and "2 scene(s) are left for a model to write" in said[-1]


def test_a_drawing_whose_parts_the_steps_do_not_name_is_shown_whole(tmp_path, monkeypatch):
    monkeypatch.setattr(diagrams, "topic_pictures", lambda: True)
    named = [{"name": n, "slug": n.lower(), "part": f"marks_{i:02d}", "tip": [1, 1]} for i, n in enumerate(("Anode", "Cathode", "Electrolyte"))]
    cell = diagrams.showable({**_drawing(tmp_path, "cell", named), "ask": "A labelled diagram of a simple cell showing its two plates"})
    lesson = writer.drawings_for_scenes(_scene_lesson(), {"topic": "Water cycle"}, log=lambda *_: None,
                                        stills=lambda scenes, brief, log=print: [cell, None, None])
    beat = lesson["chapters"][0]["beats"][0]
    assert beat["figure"] == {"kind": "picture", "file": str(tmp_path / "cell" / "whole.png"), "ask": cell["ask"]}
    assert all("focus" not in step for step in beat["steps"])                       # nothing in a whole picture can be lit
    assert lesson["chapters"][0]["beats"][1]["figure"]["kind"] == "scene" and lesson["pictures"][0]["shown"] == "whole"

    # a drawing with no file to show leaves the scene exactly as it was
    (tmp_path / "cell" / "whole.png").unlink()
    again = _scene_lesson()
    writer.drawings_for_scenes(again, {"topic": "Water cycle"}, log=lambda *_: None, stills=lambda scenes, brief, log=print: [cell, None, None])
    assert again == _scene_lesson()


def test_no_drawing_is_asked_for_when_topic_pictures_are_off(monkeypatch):
    monkeypatch.setattr(diagrams, "topic_pictures", lambda: False)
    lesson = writer.drawings_for_scenes(_scene_lesson(), {"topic": "Water cycle"}, stills=lambda *a, **k: 1 / 0)
    assert lesson == _scene_lesson()


def test_a_request_is_worded_so_that_pieces_come_back():
    assert 'Begin with what it is ("A standard diagram of …", "A labelled diagram of …")' in diagrams.VISUAL_RULE
    assert diagrams.VISUAL_RULE in diagrams.VISUAL_SYSTEM and diagrams.VISUAL_RULE in diagrams.STILLS_SYSTEM
    assert "at most 35 words and six things" in diagrams.VISUAL_RULE          # four long requests failed the service's checks in one evening


def test_steps_are_matched_to_a_drawings_parts_and_only_real_names_are_kept(tmp_path, monkeypatch):
    monkeypatch.setattr(diagrams, "topic_pictures", lambda: True)
    named = [{"name": n, "slug": n.lower(), "part": f"marks_{i:02d}", "tip": [1, 1]} for i, n in enumerate(("Evaporation", "Condensation", "Groundwater"))]
    cycle = diagrams.showable({**_drawing(tmp_path, "cycle", named), "ask": "A standard diagram of the water cycle"})
    beats = [{"id": "04", "narration": "Paani bhap banke upar jaata hai.", "steps": [{"show": "Sea to vapour"}, {"show": "Why does it rise?"}]},
             {"id": "05", "narration": "Kuch paani zameen mein jaata hai.", "steps": [{"show": "Water soaks into soil"}]}]
    seen = []

    def model(prompt, system):
        seen.append((prompt, system))
        return {"points": [{"beat": "04", "step": 1, "part": "Evaporation"}, {"beat": "05", "step": 1, "part": "ground water"},
                           {"beat": "04", "step": 2, "part": "the sun"}, {"beat": "09", "step": 1, "part": "evaporation"},
                           {"beat": "05", "step": 7, "part": "evaporation"}, "junk"]}

    got = diagrams.point_steps(cycle, beats, llm=model, log=lambda *_: None)
    assert got == {("04", 0): "evaporation", ("05", 0): "groundwater"}             # a name the drawing lacks, a beat or step that is not there: dropped
    prompt, system = seen[0]
    assert "ITS PARTS: evaporation; condensation; groundwater" in prompt       # a name that only repeats its slug is not said twice
    assert "step 1: Sea to vapour" in prompt and "spoken: Paani bhap banke" in prompt and "exactly as listed" in system
    assert diagrams.point_steps(cycle, beats, llm=lambda p, s: 1 / 0, log=lambda *_: None) == {}
    bare = [{"beat": "04", "step": 1, "part": "evaporation"}, {"beat": "04", "step": 2, "part": "none"}]       # the list without its wrapper
    assert diagrams.point_steps(cycle, beats, llm=lambda p, s: bare, log=lambda *_: None) == {("04", 0): "evaporation"}

    # in a lesson: the matched steps light their parts, so the drawing is shown by its parts
    lesson = _scene_lesson()
    for beat in lesson["chapters"][0]["beats"]:
        for step in beat["steps"]:
            step["show"] = "Something in other words"                               # no step NAMES a part
    out = writer.drawings_for_scenes(lesson, {"topic": "Water cycle"}, log=lambda *_: None,
                                     stills=lambda scenes, brief, log=print: [cycle, cycle, None],
                                     pointer=lambda ready, beats, log=print: {("01", 0): "evaporation", ("02", 0): "condensation"})
    first, second = out["chapters"][0]["beats"]
    assert first["figure"]["kind"] == "diagram" and first["figure"]["labels"] == ["evaporation", "condensation"]
    assert first["steps"][0]["focus"] == "evaporation" and second["steps"][0]["focus"] == "condensation"


# ── a rewrite of steps must not leave the drawing bare (the first pipeline lesson on a service drawing, 2026-10-09) ──

def test_steps_written_again_point_at_the_drawing_again(tmp_path):
    named = [{"name": n, "slug": n.lower(), "part": f"marks_{i:02d}", "tip": [1, 1]} for i, n in enumerate(("Evaporation", "Condensation", "Precipitation"))]
    cycle = diagrams.showable({**_drawing(tmp_path, "cycle", named), "ask": "A standard diagram of the water cycle"})
    spec = {"kind": "diagram", "manifest": cycle["manifest"], "labels": ["evaporation", "condensation"], "ask": cycle["ask"]}

    def beat(n, steps):
        return {"id": f"{n:02d}", "narration": "n", "figure": dict(spec), "steps": [dict(s, kind="point") for s in steps]}

    lesson = {"chapters": [{"beats": [
        beat(1, [{"say": "a", "show": "Sea water", "focus": "evaporation"}]),                                 # kept as it was
        beat(2, [{"say": "b", "show": "Rain, snow or hail falls"}, {"say": "c", "show": "Precipitation"}]),   # written again, no focus
        beat(3, [{"say": "d", "show": "Cooler air makes drops", "focus": "the sky"}]),                        # a focus the drawing lacks
        {"id": "04", "narration": "n", "figure": {"kind": "bars", "values": [1]}, "steps": [{"say": "e", "show": "x", "kind": "point"}]}]}]}
    asked = []

    def pointer(ready, beats, log=print):
        asked.append(([b["id"] for b in beats], ready["parts"]))
        return {("02", 0): "precipitation", ("03", 0): "condensation", ("01", 0): "condensation"}

    said = []
    out = writer.point_again(lesson, log=said.append, pointer=pointer)
    one, two, three, four = out["chapters"][0]["beats"]
    assert asked == [(["02", "03"], ["evaporation", "condensation", "precipitation"])]      # only the beats with a bare step were asked about
    assert one["steps"][0]["focus"] == "evaporation"                                         # a focus that was there is never replaced
    assert [s["focus"] for s in two["steps"]] == ["precipitation", "precipitation"] and three["steps"][0]["focus"] == "condensation"
    assert one["figure"] == two["figure"] == three["figure"] and set(one["figure"]["labels"]) == {"evaporation", "precipitation", "condensation"}
    assert four["figure"] == {"kind": "bars", "values": [1]} and "focus" not in four["steps"][0]
    assert "point at its parts again: 1 → 4 of 4 step(s) on 3 beat(s)" in said[-1]
    # without a model, the steps' own words still do what they can; a drawing that is gone changes nothing
    again = writer.point_again({"chapters": [{"beats": [beat(2, [{"say": "c", "show": "Precipitation"}, {"say": "b", "show": "Rain falls"}])]}]},
                               log=lambda *_: None, pointer=False)
    assert [s.get("focus") for s in again["chapters"][0]["beats"][0]["steps"]] == ["precipitation", None]
    gone = {"chapters": [{"beats": [{"id": "01", "narration": "n", "figure": {"kind": "diagram", "manifest": "/nowhere/manifest.json"},
                                     "steps": [{"say": "a", "show": "x", "kind": "point"}]}]}]}
    assert writer.point_again(json.loads(json.dumps(gone)), log=lambda *_: None, pointer=False) == gone


def test_a_rewritten_step_takes_the_focus_of_the_step_it_replaces(tmp_path):
    named = [{"name": n, "slug": n.lower(), "part": f"marks_{i:02d}", "tip": [1, 1]} for i, n in enumerate(("Evaporation", "Condensation", "Precipitation"))]
    cycle = diagrams.showable({**_drawing(tmp_path, "cycle", named), "ask": "A standard diagram of the water cycle"})
    spec = {"kind": "diagram", "manifest": cycle["manifest"], "labels": ["evaporation"], "ask": cycle["ask"]}

    def lesson(*beats):
        return {"chapters": [{"beats": [{"id": f"{n:02d}", "narration": "n", "figure": dict(spec), "steps": [dict(s, kind="point") for s in steps]}
                                        for n, steps in enumerate(beats, 1)]}]}

    was = lesson([{"say": "puddle sukh", "show": "Sunny puddle", "focus": "evaporation"}, {"say": "baarish hoti", "show": "Rain falls", "focus": "precipitation"}],
                 [{"say": "sun garam", "show": "Sun heats sea", "focus": "evaporation"}, {"say": "thandi hawa", "show": "Cool air", "focus": "condensation"}])
    now = lesson([{"say": "puddle sukh", "show": "Sunny puddle shrinks"}, {"say": "baarish hoti", "show": "Rain, snow or hail falls"}],   # same places
                 [{"say": "pehle socho", "show": "A new first line"}, {"say": "sun garam", "show": "Sun heats sea water"},                # one more step:
                  {"say": "kuch aur", "show": "Cool air"}])                                                                               # by anchor, by wording
    out = writer.point_again(now, log=lambda *_: None, pointer=False, was=was)
    first, second = out["chapters"][0]["beats"]
    assert [s.get("focus") for s in first["steps"]] == ["evaporation", "precipitation"]
    assert [s.get("focus") for s in second["steps"]] == [None, "evaporation", "condensation"]
    # the same place counts only while the line still shares a word: one written again to say something else is not it
    moved = lesson([{"say": "kuch naya", "show": "Sunny puddle shrinks"}, {"say": "aur naya", "show": "Why not clouds at once?"}])
    out = writer.point_again(moved, log=lambda *_: None, pointer=False, was=was)
    assert [s.get("focus") for s in out["chapters"][0]["beats"][0]["steps"]] == ["evaporation", None]
    assert set(first["figure"]["labels"]) == {"evaporation", "precipitation", "condensation"} and first["figure"] == second["figure"]


# ── the service fails its own drawing now and then; one candidate is no pipeline (the owner's lesson, 2026-10-09) ──

def test_a_request_the_service_failed_is_asked_once_more(tmp_path, monkeypatch):
    answers = iter([{"id": "a1", "status": "failed", "detail": "The drawing was rated failed_checks, below the requested review_needed."},
                    {"svg": OFFICE_SVG, "quality": "student_ready", "seconds": 52}])
    calls = _service(monkeypatch, tmp_path, lambda url, **kw: _Reply(next(answers)))
    said = []
    saved = diagrams.fetch("A simple circuit with a cell, a switch and a bulb", log=said.append)
    assert saved is not None and [c[0] for c in calls] == ["POST", "POST"] and calls[0][2]["json"] == calls[1][2]["json"]
    assert any("failed its own drawing" in line and "asking once more" in line for line in said) and "student ready" in said[-1]
    assert METER == [("diagram", 0.0, False), ("diagram", 0.0, False)]                 # both asks are in the ledger, at nothing

    failing = _service(monkeypatch, tmp_path, lambda url, **kw: _Reply({"id": "b", "status": "failed", "detail": "failed_checks"}))
    assert diagrams.fetch("Six air molecules with a white beam", log=said.append) is None and len(failing) == 2     # twice, then no more
    refused = _service(monkeypatch, tmp_path, lambda url, **kw: _Reply({}, status=503))
    assert diagrams.fetch("Another picture altogether here", log=said.append) is None and len(refused) == 1        # a service that is down is not asked again


def test_a_topic_given_one_picture_to_try_is_asked_for_more(tmp_path, monkeypatch):
    monkeypatch.setenv("HARNESS_TOPIC_PICTURES", "1")
    monkeypatch.setattr(diagrams, "available", lambda: True)
    monkeypatch.setattr(diagrams, "root", lambda *parts: tmp_path.joinpath(*parts))
    beaker = "A standard diagram of a light beam passing through a glass beaker of milky water"
    prism = "A labelled diagram of sunlight entering the air and blue light scattering in all directions"
    drawing = _drawing(tmp_path, "sky", [])
    tried, prompts = [], []

    def prepare(ask, klass=None, language="en", log=print, subject=""):
        tried.append(ask)
        return drawing if ask == prism else None

    def model(prompt, system):
        prompts.append(prompt)
        if "GIVE THREE DIFFERENT PICTURES" in prompt:
            return {"visuals": [{"ask": beaker, "shows": "Light scatters.", "kind": "demonstration"},
                                {"ask": prism, "shows": "Blue scatters most.", "kind": "labelled diagram"}]}
        return {"visuals": [{"ask": beaker, "shows": "Light scatters.", "kind": "demonstration"}]}

    monkeypatch.setattr(diagrams, "prepare", prepare)
    got = diagrams.for_brief({"topic": "Why sky is blue", "audience": "class 6 students", "goal": "explain it"}, llm=model, log=lambda *_: None)
    assert got and got["ask"] == prism and tried == [beaker, prism] and len(prompts) == 2
    assert "GIVE THREE DIFFERENT PICTURES" not in prompts[0]                     # the first question is the one it always was


def test_nothing_usable_noted_by_an_older_way_of_asking_does_not_stand(tmp_path, monkeypatch):
    import time
    monkeypatch.setenv("HARNESS_TOPIC_PICTURES", "1")
    monkeypatch.setattr(diagrams, "available", lambda: True)
    monkeypatch.setattr(diagrams, "root", lambda *parts: tmp_path.joinpath(*parts))
    from lessonforge.harness import library
    key = f"{library.slug(INERTIA['topic'])}|{library.school_class(INERTIA)}"
    note = {"topic": INERTIA["topic"], "ask": "", "judge": "off", "when": time.strftime("%Y-%m-%d %H:%M")}      # just now, but asked the old way
    (tmp_path / "topics.json").write_text(json.dumps({key: note}))
    monkeypatch.setattr(diagrams, "prepare", lambda *a, **k: None)
    calls = []
    assert diagrams.for_brief(INERTIA, llm=lambda p, s: calls.append(p) or {"visuals": []}, log=lambda *_: None) is None and calls



# ── a whole drawing's printed labels can be pointed at (harness.typeset reads them; 2026-10-09) ───────────────

def _typeset_drawing(tmp_path, name, names, size=(400, 200), painted=None):
    from PIL import Image
    folder = tmp_path / name
    folder.mkdir(parents=True, exist_ok=True)
    image = np.zeros((size[1], size[0], 4), dtype=np.uint8)
    for x0, y0, x1, y1 in painted or [(0, 0, size[0], size[1])]:
        image[y0:y1, x0:x1] = (20, 90, 200, 255)
    Image.fromarray(image).save(folder / "whole.png")
    manifest = {"version": 9, "folder": str(folder), "whole": "whole.png", "whole_stacked": "", "labels": [], "style": "pointers",
                "width": size[0], "height": size[1], "credit": "", "typeset": {"version": 2, "names": names}}
    (folder / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return {"ask": f"A labelled diagram of {name}", "manifest": str(folder / "manifest.json"), "parts": [], "names": {}, "credit": ""}


def test_a_whole_drawings_printed_labels_are_handed_on_as_points(tmp_path):
    names = {"glass_prism": {"name": "Glass Prism", "box": [0.3, 0.8, 0.5, 0.9]}, "white light": {"name": "White Light", "box": [0.05, 0.4, 0.2, 0.5]},
             "spectrum": {"name": "Spectrum", "box": [0.8, 0.5, 0.95, 0.6]},
             "panel2": {"name": "Panel 2", "box": [0.1, 0.1, 0.2, 0.2]}, "broken": {"name": "Broken", "box": [0.5, 0.5, 0.4, 0.6]},
             "no_box": {"name": "No box"}}
    ready = diagrams.showable(_typeset_drawing(tmp_path, "prism", names))
    assert ready["shown"] == "whole" and ready["file"].endswith("whole.png")
    assert ready["points"] == {"glass_prism": {"name": "Glass Prism", "box": [0.3, 0.8, 0.5, 0.9]},
                               "white_light": {"name": "White Light", "box": [0.05, 0.4, 0.2, 0.5]},
                               "spectrum": {"name": "Spectrum", "box": [0.8, 0.5, 0.95, 0.6]}}           # keyed as a focus is cleaned; a panel's name, a bad box and none are left out
    assert diagrams.whole_of(ready)["points"] == ready["points"]
    assert "points" not in diagrams.showable(_typeset_drawing(tmp_path, "bare", {}))
    # one or two labels are not a picture to point into: the triangle drawing's ONE label was its formula, lit under "24 or 12?"
    lone = {"area_of_triangle": {"name": "Area of Triangle", "box": [0.1, 0.8, 0.4, 0.9]}, "b": {"name": "b", "box": [0.2, 0.6, 0.25, 0.65]}}
    assert "points" not in diagrams.showable(_typeset_drawing(tmp_path, "lone", lone))


def test_a_label_moves_with_its_panel_when_a_wide_drawing_is_shown_relaid(tmp_path):
    from PIL import Image
    # two panels side by side on a clear ground, 3.75 to 1: shown with the second under the first
    names = {"before": {"name": "Before", "box": [0.10, 0.30, 0.20, 0.50]},          # in the left panel
             "glass": {"name": "Glass", "box": [0.25, 0.55, 0.35, 0.70]},            # in the left panel too
             "after": {"name": "After", "box": [0.70, 0.30, 0.80, 0.50]},            # in the right panel
             "between": {"name": "Between", "box": [0.47, 0.30, 0.53, 0.50]}}        # in the gutter: in neither panel
    drawing = _typeset_drawing(tmp_path, "pair", names, size=(600, 160), painted=[(20, 20, 260, 140), (340, 20, 580, 140)])
    folder = tmp_path / "pair"
    whole = np.asarray(Image.open(folder / "whole.png").convert("RGBA"))
    relaid, places = diagrams.stacked(whole, with_boxes=True)
    Image.fromarray(relaid).save(folder / "whole_stacked.png")
    manifest = json.loads((folder / "manifest.json").read_text())
    manifest.update(whole_stacked="whole_stacked.png")
    (folder / "manifest.json").write_text(json.dumps(manifest))
    ready = diagrams.showable(drawing)
    assert ready["file"].endswith("whole_stacked.png") and set(ready["points"]) == {"before", "glass", "after"}
    high, wide = relaid.shape[:2]
    for key, (px0, py0, px1, py1) in zip(("before", "after"), places):
        x0, y0, x1, y1 = ready["points"][key]["box"]
        assert px0 / wide <= x0 < x1 <= px1 / wide + 1e-6 and py0 / high <= y0 < y1 <= py1 / high + 1e-6     # inside ITS panel's new place
    assert ready["points"]["after"]["box"][1] > ready["points"]["before"]["box"][3]                           # the second panel is now below the first
    # the label kept its place within its panel: 40 px from the left panel's edge and 28 px down, as in the source
    assert abs(ready["points"]["before"]["box"][0] * wide - (places[0][0] + 40)) <= 1 and abs(ready["points"]["before"]["box"][1] * high - (places[0][1] + 28)) <= 1


def test_steps_about_a_printed_label_mark_it_in_a_lesson(tmp_path, monkeypatch):
    monkeypatch.setattr(diagrams, "topic_pictures", lambda: True)
    names = {"glass_prism": {"name": "Glass Prism", "box": [0.3, 0.8, 0.5, 0.9]}, "spectrum": {"name": "Spectrum", "box": [0.8, 0.5, 0.95, 0.6]},
             "white_ray": {"name": "White ray", "box": [0.05, 0.4, 0.2, 0.5]}}
    prism = diagrams.showable(_typeset_drawing(tmp_path, "prism", names))
    seen = []

    def model(prompt, system):
        seen.append(prompt)
        return [{"beat": "01", "step": 1, "part": "glass_prism"}, {"beat": "01", "step": 2, "part": "none"}, {"beat": "02", "step": 1, "part": "Spectrum"}]

    beats = [{"id": "01", "narration": "n", "steps": [{"show": "Light enters the glass"}, {"show": "What comes out?"}]},
             {"id": "02", "narration": "n", "steps": [{"show": "A band of colours"}]}]
    assert diagrams.point_steps(prism, beats, llm=model, log=lambda *_: None) == {("01", 0): "glass_prism", ("02", 0): "spectrum"}
    assert "ITS PARTS: glass_prism (Glass Prism); spectrum; white_ray (White ray)" in seen[0]

    lesson = _scene_lesson()
    out = writer.drawings_for_scenes(lesson, {"topic": "Light"}, log=lambda *_: None,
                                     stills=lambda scenes, brief, log=print: [prism, None, None],
                                     pointer=lambda ready, beats, log=print: {("01", 0): "glass_prism", ("01", 1): "not_on_it"})
    beat = out["chapters"][0]["beats"][0]
    assert beat["figure"]["kind"] == "picture" and beat["figure"]["points"] == prism["points"]
    assert [s.get("focus") for s in beat["steps"]] == ["glass_prism", None]            # only a label the drawing has is kept

    # a rewrite that drops the mark gets it back: from the step it replaces, from the label's own name, then from the reader
    was = json.loads(json.dumps(out))
    beat["steps"] = [{"say": "talks about", "show": "Light enters the glass", "kind": "point"},        # same anchor as before
                     {"say": "something else", "show": "The spectrum appears", "kind": "point"},       # names a label
                     {"say": "and more", "show": "Colours fan out", "kind": "point", "focus": "glass_prism_of_old"}]
    said = []
    again = writer.point_again(out, log=said.append, was=was, pointer=lambda ready, beats, log=print: {("01", 2): "spectrum"})
    assert [s.get("focus") for s in again["chapters"][0]["beats"][0]["steps"]] == ["glass_prism", "spectrum", "spectrum"]
    assert "mark its printed labels again: 0 → 3 of 3 step(s)" in said[-1]


def test_a_two_panel_drawing_is_shown_in_whichever_layout_is_larger_on_screen(tmp_path):
    from PIL import Image

    def pair(name, size, painted):
        labels = {"left": {"name": "Left", "box": [0.1, 0.3, 0.2, 0.5]}, "lower": {"name": "Lower", "box": [0.1, 0.6, 0.2, 0.7]},
                  "right": {"name": "Right", "box": [0.7, 0.3, 0.8, 0.5]}}
        drawing = _typeset_drawing(tmp_path, name, labels, size=size, painted=painted)
        folder = tmp_path / name
        whole = np.asarray(Image.open(folder / "whole.png").convert("RGBA"))
        relaid, places = diagrams.stacked(whole, with_boxes=True)
        Image.fromarray(relaid).save(folder / "whole_stacked.png")
        for n, half in enumerate(diagrams.panels(whole), 1):
            Image.fromarray(half).save(folder / f"panel_{n}.png")
        manifest = json.loads((folder / "manifest.json").read_text())
        manifest.update(whole_stacked="whole_stacked.png", panels=["panel_1.png", "panel_2.png"], panel_boxes=places)
        (folder / "manifest.json").write_text(json.dumps(manifest))
        return diagrams.showable(drawing), places

    # 3.3 to 1 (a tumbler before and after): re-laid it is larger in the 8.85 by 5.7 box
    strip, places = pair("strip", (1280, 389), [(40, 40, 600, 349), (680, 40, 1240, 349)])
    assert strip["file"].endswith("whole_stacked.png") and strip["panel_boxes"] == places and len(strip["panels"]) == 2
    # 2.2 to 1 (two circuits side by side): as drawn it fills the box's width; re-laid it would be a narrow column
    wide, _ = pair("wide", (1280, 577), [(40, 40, 600, 537), (680, 40, 1240, 537)])
    assert wide["file"].endswith("whole.png") and len(wide["panels"]) == 2
    assert wide["panel_boxes"] == [[40, 40, 600, 537], [680, 40, 1240, 537]]            # each panel's place in the drawing as drawn
    assert wide["points"]["left"]["box"] == [0.1, 0.3, 0.2, 0.5]                        # and its labels where the drawing has them
    assert diagrams.whole_of(wide)["file"].endswith("whole.png") and "panels" not in diagrams.whole_of(wide)


# ── from the first end-to-end trial lesson (photosynthesis, 2026-10-10) ───────────────────────────────────────

def test_an_arrows_filled_head_goes_with_its_arrow_even_when_other_things_are_drawn_between(tmp_path):
    # as the service drew the oxygen arrow: the arrow, its head, three bubbles, THEN the box of words
    svg = tmp_path / "source.svg"
    svg.write_text("""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 600">
<rect x="0" y="0" width="1000" height="600" fill="#bde"/>
<polygon points="300,300 320,320 290,330" fill="#f97316"/>
<polygon points="100,500 400,520 380,560 90,540" fill="#0ea5e9"/>
<path d="M 790 285 Q 880 250 965 300" fill="none" stroke="#0ea5e9" stroke-width="7"/>
<polygon points="965,300 947,272 932,298" fill="#0ea5e9"/>
<circle cx="820" cy="250" r="9" fill="#e0f2fe" stroke="#0ea5e9"/>
<circle cx="850" cy="240" r="9" fill="#e0f2fe" stroke="#0ea5e9"/>
<rect x="760" y="190" width="180" height="80" rx="12" fill="#fff" stroke="#0ea5e9"/>
<text x="772" y="217" font-weight="bold">Oxygen</text>
<text x="772" y="239">is given out</text>
</svg>""", encoding="utf-8")
    found = diagrams.read(svg)
    label = found["labels"][0]
    marks = [(diagrams._tag(found["children"][i]), found["children"][i].get("fill")) for i in label["marks"]]
    assert label["name"] == "Oxygen" and ("path", "none") in marks and ("polygon", "#0ea5e9") in marks    # the head is the arrow's
    assert ("polygon", "#f97316") not in marks                                   # another colour's head is not
    assert len([m for m in marks if m[0] == "polygon"]) == 2                     # (a four-cornered shape in the colour counts as a head, as before)


def test_taking_a_drawing_apart_again_keeps_what_another_module_put_in_its_manifest(tmp_path):
    if diagrams.browser() is None:
        pytest.skip("no headless browser on this machine")
    svg = tmp_path / "source.svg"
    svg.write_text(POSTER_SVG, encoding="utf-8")
    first = diagrams.take_apart(svg, log=lambda *_: None)
    assert first and first["version"] == diagrams.MANIFEST_VERSION and "typeset" not in first
    kept = {"version": 2, "names": {"sun": {"name": "Sun", "box": [0.05, 0.1, 0.15, 0.25]}}}
    (tmp_path / "manifest.json").write_text(json.dumps({**first, "version": diagrams.MANIFEST_VERSION - 1, "typeset": kept, "stale": 1}))
    again = diagrams.take_apart(svg, log=lambda *_: None)                        # an older manifest: taken apart afresh
    assert again["version"] == diagrams.MANIFEST_VERSION and again["typeset"] == kept and "stale" not in again
    assert json.loads((tmp_path / "manifest.json").read_text())["typeset"] == kept


# ── a drawing in panels brings every panel in, or is shown whole (the triangle-area trial lesson, 2026-10-10) ──

def _panel_lesson(file="/lib/tri/whole.png", focus_at=None):
    spec = {"kind": "picture", "file": file, "ask": "a triangle and the parallelogram two of them make",
            "panels": ["/lib/tri/panel_1.png", "/lib/tri/panel_2.png"], "panel_boxes": [[0, 0, 10, 10], [20, 0, 30, 10]]}
    beats = []
    for n, lines in enumerate((["Base: 6 cm", "Height: 4 cm"], ["Matching copy rotates", "Two equal triangles"], ["Half of b times h"]), 1):
        steps = [{"say": f"words {n} {k}", "show": line, "kind": "point"} for k, line in enumerate(lines)]
        beats.append({"id": f"{n:02d}", "narration": "n", "figure": json.loads(json.dumps(spec)), "steps": steps})
    if focus_at:
        beats[focus_at[0]]["steps"][focus_at[1]]["focus"] = "panel2"
    return {"chapters": [{"beats": beats}]}


def test_a_panel_a_rewrite_stopped_asking_for_is_asked_for_again():
    was = _panel_lesson(focus_at=(1, 0))                                   # the writer brought panel 2 in at "Matching copy rotates"
    now = _panel_lesson()
    now["chapters"][0]["beats"][1]["steps"] = [{"say": "new words", "show": "Only part covered", "kind": "point"},
                                               {"say": "words 2 0", "show": "A matching copy turns round", "kind": "point"}]   # rewritten: no focus
    said = []
    out = writer.point_again(now, log=said.append, pointer=False, was=was)
    steps = out["chapters"][0]["beats"][1]["steps"]
    assert [s.get("focus") for s in steps] == [None, "panel2"]            # on the step with the old anchor words, not the first one
    assert len(out["chapters"][0]["beats"][0]["figure"]["panels"]) == 2 and any("put back: panel2 at beat 02" in line for line in said)
    # the same line kept, or only the place: still put back
    same_line = _panel_lesson()
    same_line["chapters"][0]["beats"][1]["steps"][0]["say"] = "other words"
    assert writer.settle_panels(same_line, was=was, log=lambda *_: None)["chapters"][0]["beats"][1]["steps"][0]["focus"] == "panel2"


def test_a_drawing_no_step_ever_brings_the_second_panel_of_is_shown_whole():
    said = []
    out = writer.settle_panels(_panel_lesson(), log=said.append)
    assert all("panels" not in b["figure"] and "panel_boxes" not in b["figure"] for b in out["chapters"][0]["beats"])
    assert out["chapters"][0]["beats"][0]["figure"]["file"] == "/lib/tri/whole.png" and "shown whole from the start" in said[-1]
    asked = writer.settle_panels(_panel_lesson(focus_at=(1, 0)), log=said.append)                 # asked for: nothing changes
    assert asked == _panel_lesson(focus_at=(1, 0))


def test_a_picture_is_asked_for_without_the_lessons_conclusion_written_in_it():
    from lessonforge.harness import card as teaching_card
    assert "no formula, result, rule or summary written in the picture" in diagrams.VISUAL_RULE
    assert "with no formula, result or rule written in it" in teaching_card.SHAPE



# ── the size a picture gets is the frame's to say (longform.look); 2026-10-10 ────────────────────────────────

def test_a_pictures_scale_is_the_largest_it_gets_in_any_box_of_the_frame():
    columns, stage = [(8.85, 5.7)], [(9.0, 6.8), (13.3, 5.15)]
    assert abs(diagrams.picture_scale(1280, 577, columns) - 8.85 / 1280) < 1e-9
    assert abs(diagrams.picture_scale(1280, 389, stage) - 13.3 / 1280) < 1e-9          # a strip takes the frame's width, under its line of words
    assert abs(diagrams.picture_scale(600, 900, stage) - 6.8 / 900) < 1e-9             # an upright one takes the height, beside the words
    from lessonforge.longform import look
    assert diagrams.picture_scale(1000, 500) == diagrams.picture_scale(1000, 500, look.picture_boxes())   # the frame in force, when none is named


def test_the_same_strip_is_relaid_in_the_old_frame_and_shown_as_drawn_in_the_new(tmp_path):
    from PIL import Image
    # 2.8 to 1: re-laid it is larger in the old frame's one box; as drawn it takes the new frame's full width under a line of words
    drawing = _typeset_drawing(tmp_path, "strip", {}, size=(1280, 450), painted=[(40, 40, 600, 410), (680, 40, 1240, 410)])
    folder = tmp_path / "strip"
    whole = np.asarray(Image.open(folder / "whole.png").convert("RGBA"))
    relaid, places = diagrams.stacked(whole, with_boxes=True)
    Image.fromarray(relaid).save(folder / "whole_stacked.png")
    for n, half in enumerate(diagrams.panels(whole), 1):
        Image.fromarray(half).save(folder / f"panel_{n}.png")
    manifest = json.loads((folder / "manifest.json").read_text())
    manifest.update(whole_stacked="whole_stacked.png", panels=["panel_1.png", "panel_2.png"], panel_boxes=places)
    (folder / "manifest.json").write_text(json.dumps(manifest))
    old = diagrams.showable(drawing, boxes=[(8.85, 5.7)])
    new = diagrams.showable(drawing, boxes=[(9.0, 6.8), (13.3, 5.15)])
    assert old["file"].endswith("whole_stacked.png") and old["panel_boxes"] == places
    assert new["file"].endswith("whole.png") and new["panel_boxes"] == [[40, 40, 600, 410], [680, 40, 1240, 410]] and len(new["panels"]) == 2


# ── a drawing that sorts ITSELF into scene / arrows / labels is believed (the owner's decision, 2026-10-10) ──

SORTED_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 600"><title>The water cycle</title>
<g id="scene">
 <rect x="0" y="0" width="1000" height="600" fill="#bde"/>
 <circle cx="100" cy="100" r="50" fill="#fd0" stroke="#f59e0b"/>
 <polygon points="300,300 320,320 290,330" fill="#f97316"/>
 <text x="80" y="105">Sun</text>
</g>
<g id="arrows" stroke-width="5">
 <g data-part="Evaporation"><path d="M 150 500 Q 130 400 160 300" fill="none" stroke="#f97316"/><polygon points="160,300 145,318 165,322" fill="#f97316"/></g>
 <g data-part="Rain"><line x1="700" y1="150" x2="690" y2="200" stroke="#2563eb"/><line x1="720" y1="150" x2="710" y2="200" stroke="#2563eb"/></g>
</g>
<g id="labels" font-family="sans-serif">
 <g data-part="Evaporation"><rect x="30" y="380" width="200" height="80" rx="12" fill="#fff" stroke="#2563eb"/>
  <text x="42" y="405" font-weight="bold">1. Evaporation</text><text x="42" y="427">The sun heats water;</text></g>
 <g data-part="Rain"><rect x="760" y="190" width="180" height="80" rx="12" fill="#fff" stroke="#f97316"/>
  <text x="772" y="217" font-weight="bold">3. Precipitation</text><text x="772" y="239">Water falls as rain</text></g>
 <g data-part="Groundwater"><rect x="700" y="500" width="240" height="50" rx="12" fill="#fff" stroke="#a16207"/>
  <text x="712" y="525">Some water soaks into the ground</text></g>
 <g data-part="title"><rect x="400" y="10" width="200" height="40" rx="14" fill="#eff" stroke="#1d4ed8"/>
  <text x="500" y="38" text-anchor="middle" font-weight="bold">The water cycle</text></g>
</g>
</svg>"""


def test_a_drawing_sorted_into_scene_arrows_and_labels_is_read_by_what_it_says(tmp_path):
    svg = tmp_path / "source.svg"
    svg.write_text(SORTED_SVG, encoding="utf-8")
    found = diagrams.read(svg)
    children = found["children"]
    by_name = {label["name"]: label for label in found["labels"]}
    assert list(by_name) == ["Evaporation", "Rain", "Groundwater"]                 # the names it GAVE (not "Precipitation" from the heading); no title
    arrows = {name: [children[i].get("data-arrow") for i in label["marks"]] for name, label in by_name.items()}
    # Its boxes' colours are swapped on purpose: guessing by colour would give each label the other's arrow.
    assert arrows == {"Evaporation": ["Evaporation"], "Rain": ["Rain"], "Groundwater": []}
    scene = next(i for i, c in enumerate(children) if c.get("id") == "scene")
    assert scene in found["parts"] and all(i in found["parts"] for label in by_name.values() for i in label["marks"])
    assert not any(diagrams._tag(children[i]) in ("rect", "text") for i in found["parts"])        # boxes and words leave the art
    assert "Sun" not in by_name                                                     # a word drawn in the scenery is scenery
    assert diagrams._container(found["tree"].getroot()) is found["tree"].getroot()  # read again (for a layer), the same children
    plain = tmp_path / "plain.svg"
    plain.write_text(POSTER_SVG, encoding="utf-8")
    assert list({label["name"] for label in diagrams.read(plain)["labels"]}) and not diagrams.read(plain)["tree"].getroot().get("data-sorted")


def test_a_sorted_drawing_comes_apart_into_a_scene_and_its_arrows(tmp_path):
    if diagrams.browser() is None:
        pytest.skip("no headless browser on this machine")
    svg = tmp_path / "source.svg"
    svg.write_text(SORTED_SVG, encoding="utf-8")
    manifest = diagrams.take_apart(svg, log=lambda *_: None)
    labels = {label["name"]: label for label in manifest["labels"]}
    assert manifest["style"] == "boxes" and manifest["base"] and (tmp_path / manifest["base"]).is_file()
    assert labels["Evaporation"]["part"] and labels["Rain"]["part"] and not labels["Groundwater"]["part"]
    assert len(labels["Evaporation"]["flows"]) == 1 and len(labels["Rain"]["flows"]) == 2      # dots run along the strokes INSIDE its arrow group
    from PIL import Image
    base = np.asarray(Image.open(tmp_path / manifest["base"]).convert("RGBA"))
    part = np.asarray(Image.open(tmp_path / next(p["png"] for p in manifest["parts"] if p["id"] == labels["Evaporation"]["part"])).convert("RGBA"))
    assert base[:, :, 3].max() > 0 and part[:, :, 3].max() > 0                    # a scene, and the arrow as a layer of its own
    assert part.shape[0] < base.shape[0] and part.shape[1] < base.shape[1]         # the layer is the arrow, not the whole drawing
