import pytest

from lessonforge.harness import clip


def test_request_is_checked_and_cues_sorted():
    req = clip.check_request({"brief": "a ball rolls down a slope", "seconds": 10,
                              "cues": [{"at": 6, "do": "it speeds up"}, {"at": 1, "do": "it starts"}]})
    assert [c["at"] for c in req["cues"]] == [1.0, 6.0]
    assert req["width"] % 2 == 0 and req["fps"] == 15


@pytest.mark.parametrize("bad", [{}, {"brief": "x"}, {"brief": "a ball rolls", "seconds": 500},
                                 {"brief": "a ball rolls", "seconds": 5, "cues": [{"at": 9, "do": "late"}]}])
def test_bad_requests_say_why(bad):
    with pytest.raises(clip.ClipError):
        clip.check_request(bad)


def test_description_has_one_stage_per_cue():
    req = clip.check_request({"brief": "a bottle in water", "parts": ["bottle"], "seconds": 12,
                              "cues": [{"at": 0, "do": "held under"}, {"at": 5, "do": "rises"}]})
    d = clip.description(req)
    assert "2 stages" in d and "(1) held under." in d and "(2) rises." in d and "Parts: bottle." in d


def test_force_arrows_inside_water_are_not_refused():
    """A bottle's upthrust drawn inside the water round it is not an arrow poking through an object."""
    from lessonforge.engine import sim_gen
    code = '''
def build(width, height):
    water = Rectangle(width=width * 0.9, height=height * 0.6, fill_color=BLUE, fill_opacity=0.5, stroke_width=0)
    bottle = RoundedRectangle(width=0.6, height=1.0, corner_radius=0.15, color=WHITE).shift(LEFT * 1.5)
    up = Arrow(bottle.get_top(), bottle.get_top() + UP * 0.7, buff=0, color=GREEN)
    return VGroup(water, bottle, up)

def animate(group, run_time):
    water, bottle, up = group
    return AnimationGroup(bottle.animate.shift(RIGHT * 2), up.animate.shift(RIGHT * 2), run_time=run_time)
'''
    result, error = sim_gen._run_harness(code)
    assert result and result.get("ok"), error
    assert not result.get("arrows_through")


def test_a_clip_drawing_may_sit_off_centre_but_not_be_too_big(monkeypatch):
    from lessonforge.engine import sim_gen
    code = '''
def build(width, height):
    return VGroup(Square(side_length=1.5).move_to(LEFT * 2.2), Dot(LEFT * 2.2))

def animate(group, run_time):
    return ApplyMethod(group[1].shift, LEFT * 1.6, run_time=run_time)
'''
    # reaches x = -3.1 + ...: outside a centred 6-wide box, but only about 2 wide
    monkeypatch.setattr(sim_gen, "CENTRED", True)
    centred = sim_gen.verify(code)
    monkeypatch.setattr(sim_gen, "CENTRED", False)
    loose = sim_gen.verify(code)
    assert centred and "leaves its" in str(centred)
    assert not loose or "leaves its" not in str(loose)
