"""A library component's number moves between two beats instead of fading out and being redrawn (video-quality plan S7).

``ComponentFigure.change_from(old)`` is the hook ``GuidedChapter`` already plays for a figure that changes part by part. It
answers ``[]`` (the old fade) unless the control ``LESSONFORGE_COMPONENT_TWEEN`` is on, both figures carry the same ``span``,
the only change is a listed number knob and the library MEASURED that the straight morph is within a pixel of the truth
(``component_lib.morph_plan``). Hermetic (the pinned six components), no voice, no GPU, no network. The Manim animations are
driven by hand (``begin``, ``interpolate``, ``finish``) and the frames compared as pixels with Manim's own camera.
"""
import json

import numpy as np
import pytest

from lessonforge import kits, knobs
from lessonforge.kits import components as C
from lessonforge.longform import component_lib as lib

REASON = lib.unavailable_reason()
pytestmark = pytest.mark.skipif(bool(REASON), reason=f"components are not available here: {REASON}")

KIT = kits.get("components")
ON = {"LESSONFORGE_COMPONENT_TWEEN": "1"}


def manim_side():
    pytest.importorskip("manim", reason="manim is not installed here")
    from lessonforge.longform import component_figure as CF
    return CF


def settled_pair(cid, state_a, state_b, params=None, reveal_b=None):
    """The figure dicts of two consecutive beats on one component, as ``settle`` writes them (one span)."""
    def fig(state):
        inner = {"id": cid, **({"params": params} if params else {}), "state": state}
        return {"kind": "component", "params": inner}
    beats = [{"id": f"{i + 1:02}", "narration": f"Beat {'ab'[i]}.", "steps": [{"say": "Beat", "show": "x"}], "figure": fig(s)}
             for i, s in enumerate((state_a, state_b))]
    out, issues = KIT.settle({"title": "t", "chapters": [{"id": 1, "title": "ONE", "learning_goal": "g", "role": "explain", "beats": beats}]})
    assert issues == [], issues
    figures = [b["figure"] for b in out["chapters"][0]["beats"]]
    assert figures[0]["params"]["span"] == figures[1]["params"]["span"]
    return figures


def placed(CF, figure, by=1.7, at=(1.0, 0.4, 0.0), **extra):
    """A figure built from a settled dict and put where the stage puts a picture (scaled about its card, moved)."""
    inner = {**figure["params"], **extra}
    f = CF.component(inner)
    f.scale(by).move_to(np.array(at, dtype=float))
    return f


def picture(group, width=640, height=360):
    """The group drawn to pixels by Manim's own camera: a frame to compare."""
    from manim import Camera
    camera = Camera(pixel_width=width, pixel_height=height, frame_width=8.0, frame_height=4.5, background_color="#101010")
    camera.capture_mobject(group)
    return np.asarray(camera.pixel_array, dtype=float)[:, :, :3]


def play(animations, alpha):
    """Drive ``animations`` (the list ``change_from`` returned) to ``alpha`` by hand and leave them there."""
    for anim in animations:
        anim.begin()
    for anim in animations:
        anim.interpolate(alpha)


def leaf(a=1, b=0.3):
    CF = manim_side()
    figures = settled_pair("leaf_section", {"opening": a}, {"opening": b})
    return CF, figures, placed(CF, figures[0]), placed(CF, figures[1])


# ---------------------------------------------------------------- when it moves and when it does not

def test_it_is_off_unless_the_control_is_on_and_the_control_is_read_at_render_time():
    CF, figures, old, new = leaf()
    assert knobs.get("LESSONFORGE_COMPONENT_TWEEN", "0") == "0" and knobs.BY_ID["LESSONFORGE_COMPONENT_TWEEN"].default == "0"
    assert new.change_from(old) == [], "off: the old fade, exactly as before"
    with knobs.applied(ON):
        assert len(new.change_from(old)) == 1
    assert knobs.BY_ID["LESSONFORGE_COMPONENT_TWEEN"].render is True
    with knobs.applied(ON):
        assert knobs.render_env() == ON, "a render subprocess is told"


def test_only_a_listed_number_knob_the_library_has_measured_is_moved():
    CF = manim_side()
    with knobs.applied(ON):
        # a preset (not a number): never
        figs = settled_pair("leaf_section", {"stoma": "open"}, {"stoma": "closed"})
        assert placed(CF, figs[1]).change_from(placed(CF, figs[0])) == []
        # a number knob nobody listed (number_line's hops_done): never
        figs = settled_pair("number_line", {"hops_done": 0}, {"hops_done": 1})
        assert placed(CF, figs[1]).change_from(placed(CF, figs[0])) == []
        # a number set on one side only: undefined, cut
        figs = settled_pair("leaf_section", {"stoma": "open"}, {"opening": 0.3})
        assert placed(CF, figs[1]).change_from(placed(CF, figs[0])) == []
        # listed, but a curve: the straight morph of a swinging bob cuts across the arc, so it goes through stations
        # (plan step S8, test_component_keyframes.py); a knob whose plan the library refuses is not moved
        figs = settled_pair("simple_pendulum", {"time_s": 0}, {"time_s": 2.4})
        old, new = placed(CF, figs[0]), placed(CF, figs[1])
        assert lib.morph_plan("simple_pendulum", {"state": {"time_s": 0}}, {"state": {"time_s": 2.4}})["stations"]
        assert len(new.change_from(old)) == 1
        # listed and straight: yes
        figs = settled_pair("leaf_section", {"opening": 1}, {"opening": 0.3})
        assert len(placed(CF, figs[1]).change_from(placed(CF, figs[0]))) == 1


def test_it_needs_the_same_component_the_same_span_and_the_same_card():
    CF, figures, old, new = leaf()
    other = placed(CF, settled_pair("simple_pendulum", {"time_s": 0}, {"time_s": 1})[0])
    alone_new = CF.component({k: v for k, v in figures[1]["params"].items() if k != "span"})
    alone_new.scale(1.7).move_to(np.array([1.0, 0.4, 0.0]))
    placed_apart = placed(CF, figures[1], by=1.4)
    with knobs.applied(ON):
        assert len(new.change_from(old)) == 1
        assert new.change_from(other) == [], "another component"
        assert alone_new.change_from(old) == [] and new.change_from(alone_new) == [], "no span, or not the same span"
        assert placed_apart.change_from(old) == [], "not placed alike: a morph would slide the whole card"
        assert new.change_from(new) == [] and new.change_from(None) == [] and new.change_from(object()) == []


# ---------------------------------------------------------------- what it does on screen

def sub_animations(group):
    return list(group.animations)


def test_the_art_is_transformed_the_labels_cross_fade_and_the_part_group_is_never_tweened():
    from manim import Text, Transform, VGroup
    CF, figures, old, new = leaf()
    with knobs.applied(ON):
        (group,) = new.change_from(old)
    moved = [a for a in sub_animations(group) if isinstance(a, Transform)]
    assert moved, "the guard cells changed shape: their art is transformed"
    for anim in moved:
        assert type(anim.mobject).__name__ == "SVGMobject" and not isinstance(anim.mobject, (Text, VGroup))
        assert anim.mobject in [m for art in old.art.values() for m in art.submobjects], "an SVG file of the OLD drawing's art"
        assert anim.target_mobject in [m for art in new.art.values() for m in art.submobjects]
        assert all(anim.mobject is not part for part in old.parts.values()), "never the part VGroup"
    fades = [a for a in sub_animations(group) if type(a).__name__ == "_Opacity"]
    assert fades and not any(isinstance(a, Transform) and isinstance(a.mobject, Text) for a in sub_animations(group))
    assert not any(a.mobject in list(old.anchors.values()) for a in sub_animations(group)), "the invisible anchors are ignored"
    assert all(a.mobject is not old.card for a in sub_animations(group)), "equal cards: nothing to do to the card"


def test_start_middle_and_end_are_the_old_a_blend_and_the_new_and_nothing_is_blank_in_between():
    CF, figures, old, new = leaf()
    reference_old, reference_new = picture(placed(CF, figures[0])), picture(placed(CF, figures[1]))
    assert np.abs(reference_old - reference_new).mean() > 0.05, "the two beats differ"
    with knobs.applied(ON):
        (group,) = new.change_from(old)
    group.begin()
    group.interpolate(0.0)
    start = picture(old)
    group.interpolate(0.5)
    middle = picture(old)
    group.interpolate(1.0)
    group.finish()
    end = picture(old)
    assert np.abs(start - reference_old).mean() < 0.02, "at alpha 0 it is the old drawing"
    assert np.abs(end - reference_new).mean() < 0.02, "at alpha 1 it is the new drawing, pixel for pixel (the runtime then swaps the figure in)"
    assert np.abs(middle - reference_old).mean() > 0.01 and np.abs(middle - reference_new).mean() > 0.01, "half way differs from both ends"
    card = np.array([0xF7, 0xF3, 0xEA], dtype=float)
    paper = (np.abs(middle - card).sum(axis=2) < 6).mean()
    assert paper > 0.2 and (np.abs(middle - np.array([16, 16, 16.0])).sum(axis=2) > 30).mean() > 0.3, "the card is never blank at 0.5"


def test_the_manim_flip_holds_under_the_transform_each_part_keeps_its_place_head_up():
    CF, figures, old, new = leaf()
    top, bottom = "upper_epidermis", "lower_epidermis"
    height = lambda f, n: float(f.art[n].get_center()[1])     # noqa: E731
    assert height(old, top) > height(old, bottom), "to begin with, the upper layer is above the lower"
    with knobs.applied(ON):
        (group,) = new.change_from(old)
    group.begin()
    for alpha in (0.0, 0.25, 0.5, 0.75, 1.0):
        group.interpolate(alpha)
        assert height(old, top) > height(old, bottom) + 0.5, f"the flip was undone per part and stays undone at {alpha}"
        guard = old.art["stoma"]
        assert float(guard.get_center()[1]) < height(old, top), "the guard cells stay under the upper epidermis"
    group.finish()
    for name in old.art:
        if len(new.art[name].submobjects):
            assert old.art[name].get_center()[:2] == pytest.approx(new.art[name].get_center()[:2], abs=1e-3), name
            assert old.art[name].width == pytest.approx(new.art[name].width, abs=1e-3)
            assert old.art[name].height == pytest.approx(new.art[name].height, abs=1e-3)


def test_a_part_the_new_drawing_keeps_back_is_gone_after_the_tween_and_nothing_hidden_is_shown():
    CF = manim_side()
    figures = settled_pair("leaf_section", {"opening": 1}, {"opening": 0.3})
    old = placed(CF, figures[0])
    new = placed(CF, figures[1], reveal=["stoma", "light"])           # the new drawing waits to show the stoma and the light
    assert set(new.hidden) == {"stoma", "light"} and "stoma" in old.shown
    with knobs.applied(ON):
        (group,) = new.change_from(old)
    group.begin()
    group.interpolate(0.4)
    mid = max(float(m.get_stroke_opacity()) for m in old.parts["stoma"].family_members_with_points())
    group.interpolate(1.0)
    group.finish()
    for name in new.hidden:
        assert all(m.get_stroke_opacity() == 0 and m.get_fill_opacity() == 0 for m in old.parts[name].family_members_with_points()), name
    assert 0 < mid < 1, "it fades out (FadeOut), it is not cut"
    assert all(m.get_stroke_opacity() == 0 for m in new.parts["stoma"].family_members_with_points()), "the new figure is untouched"


def test_a_part_kept_back_before_and_shown_now_comes_in_and_the_old_drawing_is_the_one_animated():
    CF = manim_side()
    figures = settled_pair("leaf_section", {"opening": 1}, {"opening": 0.3})
    old = placed(CF, figures[0], reveal=["light"])
    new = placed(CF, figures[1])
    before = len(old.parts["light"].family_members_with_points())
    with knobs.applied(ON):
        (group,) = new.change_from(old)
    group.begin()
    group.interpolate(0.5)
    group.interpolate(1.0)
    group.finish()
    sun = [m for m in old.parts["light"].family_members_with_points() if float(m.get_stroke_opacity()) > 0 or float(m.get_fill_opacity()) > 0]
    assert sun and len(old.parts["light"].family_members_with_points()) > before, "a copy of the new part was brought in"
    assert all(m not in new.get_family() for m in old.get_family() if m is not old), "nothing of the new figure is put in the old one"


def test_words_are_never_morphed_a_label_that_changes_fades_out_as_the_new_one_fades_in():
    from manim import Text
    CF, figures, old, new = leaf()
    old_words = [t.text for t in old.labels]
    new_words = [t.text for t in new.labels]
    assert "stoma(open)" in old_words and "half-openstoma" in new_words            # Text drops the spaces of its ``text``
    with knobs.applied(ON):
        (group,) = new.change_from(old)
    group.begin()
    seen = lambda m: float(max(g.get_fill_opacity() for g in m.family_members_with_points()))      # noqa: E731 - what the glyphs show
    words = lambda: {m.text: seen(m) for m in old.get_family() if isinstance(m, Text) and hasattr(m, "text")}      # noqa: E731
    group.interpolate(0.15)
    early = words()
    assert 0 < early["stoma(open)"] < 1 and early["half-openstoma"] == 0, "the old word is going out in the first 30%"
    group.interpolate(0.5)
    middle = words()
    assert middle["stoma(open)"] == 0 and middle["half-openstoma"] == 0, "at the middle neither is there: two numbers are never printed over each other (S13)"
    group.interpolate(0.85)
    late = words()
    assert late["stoma(open)"] == 0 and 0 < late["half-openstoma"] < 1, "the new word comes in in the last 30%"
    assert late["cuticle"] == 1 and early["cuticle"] == 1, "a label that did not change is not touched"
    group.interpolate(1.0)
    group.finish()
    final = {m.text: seen(m) for m in old.get_family() if isinstance(m, Text) and hasattr(m, "text")}
    assert final["half-openstoma"] == 1 and final["stoma(open)"] == 0


def test_an_exception_while_planning_falls_back_to_the_old_fade(monkeypatch, capsys):
    CF, figures, old, new = leaf()

    def boom(*a, **k):
        raise RuntimeError("node is gone")
    monkeypatch.setattr(lib, "morph_plan", boom)
    with knobs.applied(ON):
        assert new.change_from(old) == []
    assert "LESSON_NOTE" in capsys.readouterr().out


# ---------------------------------------------------------------- the library: what is listed and what is measured

def test_the_listed_knobs_exist_in_the_owners_library_when_a_real_tree_is_there():
    assert "sound_wave" not in lib.TWEEN_KNOBS and "clock" not in lib.TWEEN_KNOBS, "a periodic knob is never listed"
    entry = lib.get("leaf_section")
    assert lib.is_knob(entry["states"]["opening"]) and "leaf_section" in lib.TWEEN_KNOBS
    for cid, names in lib.TWEEN_KNOBS.items():
        try:
            real = lib.get(cid)
        except lib.ComponentError:
            continue                                         # not in this tree (the pinned snapshot has six files)
        for name in names:
            assert lib.is_knob(real["states"].get(name)) or any(p["name"] == name and p["type"] == "number" for p in real["params"]), (cid, name)


def test_a_change_is_only_ever_a_listed_number_and_nothing_else_moves_with_it():
    entry = lib.get("leaf_section")
    a, b = {"state": {"opening": 1}}, {"state": {"opening": 0.3}}
    assert lib.tweenable(entry, a, b) == [("state", "opening")]
    assert lib.tweenable(entry, a, {"state": {"opening": 0.3, "stoma": "closed"}}) == [], "a preset moves with it"
    assert lib.tweenable(entry, a, {"state": {"opening": 0.3}, "params": {"label": "other"}}) == [], "a text moves with it"
    assert lib.tweenable(entry, a, a) == [] and lib.tweenable(entry, {"state": {"light": 1, "opening": 1}}, {"state": {"light": 0.2, "opening": 1}}) == []
    assert lib.tweenable(lib.get("number_line"), {"state": {"hops_done": 0}}, {"state": {"hops_done": 2}}) == [], "not listed"


def test_the_morph_is_measured_a_straight_line_that_is_wrong_is_refused_not_trusted():
    straight = lib.morph_plan("leaf_section", {"state": {"opening": 1}}, {"state": {"opening": 0.3}})
    assert straight["stations"] == [] and "stoma" in straight["stable"] and "gases" in straight["stable"]
    appearing = lib.morph_plan("leaf_section", {"state": {"opening": 0}}, {"state": {"opening": 1}})
    assert "stoma" in appearing["stable"] and "gases" not in appearing["stable"], "the gas arrows appear: that part is cross-faded"
    curved = lib.morph_plan("simple_pendulum", {"state": {"time_s": 0}}, {"state": {"time_s": 2.4}})
    assert len(curved["stations"]) >= 3, "the bob's arc is not a chord: measured, so stations are needed"
    assert lib.morph_plan("number_line", {"state": {"hops_done": 0}}, {"state": {"hops_done": 2}}) is None
    assert lib.morph_plan("no_such_component", {}, {}) is None
    assert lib.morph_plan("leaf_section", {"state": {"opening": 1}}, {"state": {"opening": 0.3}}, max_depth=0) is None


def test_the_probes_are_several_so_a_symmetric_curve_is_not_fooled():
    """A bob released at the side is back at the side after one period: the drawings at 0 and at T are the same and the
    drawing at T/2 is the mirror image. A test of the midpoint alone against the straight line between the ends sees the
    ends equal and the midpoint as the one odd point; here a quarter point must fail too, and every kept station is a probe."""
    entry = lib.get("simple_pendulum")
    period = 2 * np.pi * np.sqrt(0.64 / 9.8)
    plan = lib.morph_plan("simple_pendulum", {"state": {"time_s": 0}}, {"state": {"time_s": round(float(period), 4)}})
    assert plan["stations"], "the whole swing is a closed curve: the chord is wrong everywhere"
    ts = [round(s["state"]["time_s"], 3) for s in plan["stations"]]
    assert ts == sorted(ts) and 0 < ts[0] and ts[-1] < period
    assert len({round(t, 3) for t in ts}) == len(ts) and entry["id"] == "simple_pendulum"


def test_svg_numbers_see_shapes_and_positions_apart_and_ignore_colours():
    skeleton, nums = lib.svg_numbers('<circle cx="10.5" cy="-4" r="3" fill="#1B2033" stroke="#22cc11"/>')
    assert nums == [10.5, -4.0, 3.0] and "#1B2033" not in skeleton and skeleton.count("#") >= 3
    same, _ = lib.svg_numbers('<circle cx="99" cy="1" r="30" fill="#1B2033" stroke="#22cc11"/>')
    assert same == skeleton, "the same shape in another place"
    other, _ = lib.svg_numbers('<ellipse cx="99" cy="1" r="30" fill="#1B2033" stroke="#22cc11"/>')
    assert other != skeleton


def test_the_figure_remembers_what_it_is_for_the_morph_and_the_dict_round_trips():
    CF, figures, old, new = leaf()
    assert new.drawing["id"] == "leaf_section" and new.drawing["state"]["opening"] == 0.3
    assert new.span == figures[1]["params"]["span"] and json.dumps(new.span)
    assert set(new.sig) == set(new.parts) and new.svg["stoma"] is not None
    assert C.figure_extras(figures[1])["span"] == new.span
