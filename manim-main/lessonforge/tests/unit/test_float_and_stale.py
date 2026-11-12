"""A floating object sits as deep as its density says, and no picture outlives the case it was drawn for."""
from lessonforge.harness import qa, writer
from lessonforge.longform import figure_math

ICE = {"kind": "float", "liquid": {"name": "water", "density": 1.0}, "objects": [{"name": "ice", "mass": 92, "volume": 100}]}


def _lesson(*beats):
    return {"chapters": [{"title": "t", "beats": [dict(b, id=f"{i:02}") for i, b in enumerate(beats)]}]}


def test_float_case_works_out_density_share_and_sinking():
    case = figure_math.float_case({"objects": [{"name": "ice", "mass": 92, "volume": 100},
                                               {"name": "cube", "mass": 92, "volume": 50},
                                               {"name": "wood", "density": 0.6, "volume": 100}]})
    ice, cube, wood = case["objects"]
    assert (ice["density"], ice["under"], ice["above"], ice["sinks"]) == (0.92, 92, 8, False)
    assert cube["sinks"] and cube["density"] == 1.84 and cube["share"] == 1.0
    assert wood["mass"] == 60 and wood["under"] == 60


def test_float_case_names_an_object_it_cannot_place():
    case = figure_math.float_case({"objects": [{"name": "blob", "mass": 10}]})
    assert not case["objects"] and case["issues"]


def test_float_figure_shows_its_worked_numbers():
    assert {"92", "100", "0.92", "8"} <= writer.figure_numbers(ICE)
    assert "float" in writer.FIGURE_KINDS and '"kind":"float"' in writer.SYSTEM


def test_ice_bars_over_the_wooden_block_are_stale():
    bars = {"kind": "bars", "parts": [{"label": "under water: 92 cm³", "n": 92, "d": 100}, {"label": "above", "n": 8, "d": 100}]}
    lesson = _lesson({"narration": "Ninety-two of the hundred cubic centimetres are under water.", "figure": bars},
                     {"narration": "Eight cubic centimetres stay above, out of one hundred."},
                     {"narration": "Now the wooden block: sixty grams in one hundred cubic centimetres gives zero point six zero, "
                                   "so zero point six of it is under, sixty cubic centimetres."})
    stale = writer.stale_pictures(lesson)
    assert [b["id"] for b, _ in stale] == ["02"]
    assert any(f["kind"] == "stale_picture" and f["beat"] == "02" for f in qa.storyboard_findings(lesson))


def test_a_scene_worked_on_the_same_case_is_not_stale():
    scene = {"kind": "scene", "describe": "A torch ray at 60 degrees enters water and bends towards the normal"}
    lesson = _lesson({"narration": "A ray at sixty degrees enters water.", "figure": scene},
                     {"narration": "Sine of sixty is zero point eight seven; divide by one point three three to get zero point six five."},
                     {"narration": "Now a ray at thirty degrees enters glass of index one point five: zero point five over one point five."})
    assert [b["id"] for b, _ in writer.stale_pictures(lesson)] == ["02"]


def _wood_lesson():
    return _lesson({"narration": "An ice cube of ninety-two grams and one hundred cubic centimetres floats.", "figure": ICE},
                   {"narration": "A wooden block of sixty grams and eighty cubic centimetres: zero point seven five, so it floats."},
                   {"narration": "Sixty of its eighty cubic centimetres are under water, about zero point seven five."})


def test_own_pictures_takes_a_figure_with_the_beats_numbers():
    wood = {"kind": "float", "objects": [{"name": "wood", "mass": 60, "volume": 80}]}
    lesson = writer.own_pictures(_wood_lesson(), lambda prompt, system: {"figure": wood}, log=lambda *_: None)
    assert lesson["chapters"][0]["beats"][1]["figure"] == wood and not writer.stale_pictures(lesson)
    assert lesson["own_pictures"]["fixed"] == ["01"] and lesson["own_pictures"]["calls"] == 1


def test_own_pictures_drops_the_picture_when_the_answer_does_not_fit():
    lesson = writer.own_pictures(_wood_lesson(), lambda prompt, system: {"figure": ICE}, log=lambda *_: None)
    beats = lesson["chapters"][0]["beats"]
    assert beats[1]["picture"] == "off" and not writer.stale_pictures(lesson)


def test_own_pictures_without_a_model_shows_words_alone():
    lesson = writer.own_pictures(_wood_lesson(), None, log=lambda *_: None)
    assert all(b.get("picture") == "off" for b in lesson["chapters"][0]["beats"][1:])


def test_the_float_figure_settles_each_object_where_its_density_says():
    from lessonforge.longform import figures
    fig = figures.build({"kind": "float", "objects": [{"name": "ice", "mass": 92, "volume": 100},
                                                      {"name": "iron", "mass": 790, "volume": 100}]})
    work = fig.origin.copy()
    anim = fig.animator(work, 3.0)
    anim.begin()
    anim.finish()
    ice, iron, surface = work[4], None, work[1]
    level = surface.get_center()[1]
    under = (level - ice.get_bottom()[1]) / ice.height
    assert abs(under - 0.92) < 0.01                      # 92 per cent of the cube is under the surface
    iron = next(m for m in work if getattr(m, "side_length", None) and m is not ice)
    assert iron.get_top()[1] < level                     # the iron block is all the way under
