"""A number that moves across the sentence that says it (video-quality plan S9).

The step cue caps every animation at 0.9 s and the lead-in tween (S7) at 1.4 s. A beat's step flagged ``tween: "voice"``
(written by the components kit when the beat's drawing differs from the last beat's only by a listed number knob, with
``LESSONFORGE_COMPONENT_TWEEN`` on) is moved by ``GuidedChapter._start_tween`` for the whole sentence: stepped by hand from a
driver mobject at ``tween_progress`` of the scene clock. Hermetic (the pinned six components), no voice, no GPU: the clock is a
fake and the frames are Manim's own camera.
"""
from types import SimpleNamespace

import numpy as np
import pytest

from lessonforge import kits, knobs
from lessonforge.kits import components as C
from lessonforge.longform import component_lib as lib

REASON = lib.unavailable_reason()
pytestmark = pytest.mark.skipif(bool(REASON), reason=f"components are not available here: {REASON}")
KIT = kits.get("components")
ON = {"LESSONFORGE_COMPONENT_TWEEN": "1"}


def runtime():
    pytest.importorskip("manim", reason="manim is not installed here")
    from lessonforge.longform import runtime as R
    return R


# ---------------------------------------------------------------- the clock

def test_progress_runs_evenly_across_the_sentence_and_rests_a_hair_before_its_end():
    R = runtime()
    p = R.tween_progress
    assert p(10.0, 10.0, 16.0) == 0.0 and p(5.0, 10.0, 16.0) == 0.0, "nothing moves before the words"
    run = 6.0 - 0.4
    assert p(10.0 + run / 2, 10.0, 16.0) == pytest.approx(0.5)
    assert p(10.0 + run, 10.0, 16.0) == 1.0 and p(16.0, 10.0, 16.0) == 1.0 and p(99.0, 10.0, 16.0) == 1.0
    xs = [p(10.0 + k * .25, 10.0, 16.0) for k in range(25)]
    assert xs == sorted(xs) and len({round(b - a, 9) for a, b in zip(xs, xs[1:]) if 0 < a < 1 and b < 1}) == 1, "linear: no easing"
    # the step cue's stage clock plays "soon and then waits" (the first 2.4 s of a 6 s sentence); this one is going on at its middle
    assert R.stage_progress(13.0, 10.0, 6.0, [10.0]) == 1.0 and 0.4 < p(13.0, 10.0, 16.0) < 0.6


def test_a_very_short_window_still_moves_and_never_divides_by_zero():
    R = runtime()
    assert R.tween_progress(1.0, 1.0, 1.0) == 0.0 and R.tween_progress(1.3, 1.0, 1.0) == 1.0


# ---------------------------------------------------------------- the window

def chapter(beat_start=100.0, speech_end=9.0):
    R = runtime()
    return SimpleNamespace(beat_start=beat_start, current={"speech_end": speech_end}, window=R.GuidedChapter._voice_window)


def window(me, steps, due, located):
    return me.window(me, steps, due, located)


def test_the_window_is_the_flagged_steps_sentence_up_to_the_next_steps_words_or_the_end_of_the_speech():
    me = chapter()
    steps = [{"say": "a"}, {"say": "b", "tween": "voice"}, {"say": "c"}]
    assert window(me, steps, [100.5, 103.0, 107.5], [True] * 3) == (103.0, 107.5)
    assert window(me, steps, [100.5, 103.0, 103.02], [True] * 3) == (103.0, 109.0), "two steps on one word: the next one that is later"
    assert window(me, steps[:2], [100.5, 103.0], [True, True]) == (103.0, 109.0), "the last step: to the end of the speech"
    assert window(me, [{"say": "a", "tween": "voice"}], [100.5], [True]) == (100.5, 109.0)


def test_no_window_when_the_step_is_not_flagged_was_guessed_follows_a_focus_or_is_too_short():
    me = chapter()
    plain = [{"say": "a"}, {"say": "b"}]
    assert window(me, plain, [100.5, 103.0], [True, True]) is None, "no flag: the lead-in tween, as in S7"
    flagged = [{"say": "a"}, {"say": "b", "tween": "voice"}]
    assert window(me, flagged, [100.5, 103.0], [True, False]) is None, "an even spread is a guess: V1"
    assert window(me, [{"say": "a", "focus": "pore"}, flagged[1]], [100.5, 103.0], [True, True]) is None, \
        "an earlier step names a part of the picture that is under the old one"
    assert window(me, flagged, [100.5, 103.0], [True, True]) == (103.0, 109.0)
    assert window(chapter(speech_end=3.5), flagged, [100.5, 103.0], [True, True]) is None, "under a second"


# ---------------------------------------------------------------- the kit writes the flag

def beats(*states, comp="leaf_section"):
    def fig(state):
        if comp == "number_line":
            return {"kind": "component", "params": {"id": comp, "params": state}}
        return {"kind": "component", "params": {"id": comp, "state": state}}
    out = []
    for i, state in enumerate(states):
        steps = [{"say": "Beat", "show": "first words"}, {"say": "then", "show": "more words"}]
        out.append({"id": f"{i + 1:02}", "narration": "Beat one. Then more.", "steps": steps, "figure": fig(state)})
    return {"title": "t", "chapters": [{"id": 1, "title": "ONE", "learning_goal": "g", "role": "explain", "beats": out}]}


def flags(lesson):
    return [[s.get("tween") for s in b["steps"]] for c in lesson["chapters"] for b in c["beats"]]


def settle(lesson, on=True):
    with knobs.applied(ON if on else {"LESSONFORGE_COMPONENT_TWEEN": "0"}):
        out, issues = KIT.settle(lesson)
    assert issues == [], issues
    return out


def test_the_first_step_of_a_beat_whose_number_moved_is_flagged_when_the_control_is_on():
    out = settle(beats({"opening": 1}, {"opening": 0.3}, {"opening": 0.3}, {"opening": 0.8}))
    assert flags(out) == [[None, None], ["voice", None], [None, None], ["voice", None]], \
        "the first beat has nothing before it; a beat that keeps the numbers moves nothing"


def test_nothing_is_written_with_the_control_off_or_for_a_change_that_is_not_a_listed_number():
    assert flags(settle(beats({"opening": 1}, {"opening": 0.3}), on=False)) == [[None, None]] * 2
    assert flags(settle(beats({"stoma": "open"}, {"stoma": "closed"}))) == [[None, None]] * 2, "a preset is not moved"
    unlisted = settle(beats({"jumps": 2}, {"jumps": 3}, comp="number_line"))
    assert flags(unlisted) == [[None, None]] * 2, "a number nobody listed (number_line's jumps) is not moved"


def test_a_beat_after_another_component_or_picture_is_not_flagged():
    lesson = beats({"opening": 1}, {"opening": 0.3})
    lesson["chapters"][0]["beats"].insert(1, {"id": "09", "narration": "Here.", "steps": [{"say": "Here", "show": "x"}],
                                              "figure": {"kind": "component", "params": {"id": "simple_pendulum", "state": {"time_s": 0}}}})
    assert flags(settle(lesson)) == [[None, None], [None], [None, None]], "a run broken by another component starts over"


def test_a_stale_flag_goes_and_a_hand_placed_one_stays_where_it_was_put():
    lesson = beats({"opening": 1}, {"opening": 0.3})
    lesson["chapters"][0]["beats"][0]["steps"][0]["tween"] = "voice"          # on the first beat, which moves nothing
    lesson["chapters"][0]["beats"][1]["steps"][1]["tween"] = "voice"          # on the second step of the beat that does move
    out = settle(lesson)
    assert flags(out) == [[None, None], [None, "voice"]]
    assert flags(settle(out)) == [[None, None], [None, "voice"]], "idempotent"
    out["chapters"][0]["beats"][1]["figure"]["params"]["state"] = {"opening": 1}
    assert flags(settle(out)) == [[None, None], [None, None]], "the number no longer moves: the flag goes"
    assert flags(settle(beats({"opening": 1}, {"opening": 0.3}, {"opening": 0.3}))) [2] == [None, None]


# ---------------------------------------------------------------- the driver

def settled_pair(opening_a=1, opening_b=0.3):
    out = settle(beats({"opening": opening_a}, {"opening": opening_b}))
    return [b["figure"] for b in out["chapters"][0]["beats"]]


def placed(CF, figure, by=1.7, at=(1.0, 0.4, 0.0)):
    f = CF.component(figure["params"])
    f.scale(by).move_to(np.array(at, dtype=float))
    return f


def picture(group, width=640, height=360):
    from manim import Camera
    camera = Camera(pixel_width=width, pixel_height=height, frame_width=8.0, frame_height=4.5, background_color="#101010")
    camera.capture_mobject(group)
    return np.asarray(camera.pixel_array, dtype=float)[:, :, :3]


class Scene:
    """Just enough of a scene for ``_start_tween``: a clock, ``add``/``remove`` and ``bring_to_back``."""

    def __init__(self, R):
        self.renderer = SimpleNamespace(time=0.0)
        self.mobjects = []
        self.start = lambda *a, **k: R.GuidedChapter._start_tween(self, *a, **k)
        self.stop = lambda h: R.GuidedChapter._stop_tween(self, h)

    def add(self, *m):
        self.mobjects += [x for x in m if x not in self.mobjects]

    def remove(self, *m):
        self.mobjects = [x for x in self.mobjects if not any(x is y for y in m)]

    def bring_to_back(self, *m):
        self.remove(*m)
        self.mobjects = list(m) + self.mobjects


def driven():
    R = runtime()
    from lessonforge.longform import component_figure as CF
    figures = settled_pair()
    old, new = placed(CF, figures[0]), placed(CF, figures[1])
    with knobs.applied(ON):
        (group,) = new.change_from(old)
    scene = Scene(R)
    scene.add(new, old)
    handle = scene.start(old, group, 10.0, 16.0)
    assert handle is not None
    driver, tick, ghost, until = handle
    assert until == 16.0
    return scene, handle, old, new


def at(scene, handle, now):
    scene.renderer.time = now
    handle[1](None, 1 / 30)


def test_the_old_picture_follows_the_voices_clock_and_is_the_new_one_at_the_end_of_the_sentence():
    scene, handle, old, new = driven()
    assert scene.mobjects[0] is handle[0], "the driver is behind everything (see _start_motion)"
    start = picture(old)
    at(scene, handle, 9.0)
    assert np.array_equal(picture(old), start), "before the words: still the old picture"
    seen = []
    for now in (10.0, 11.0, 12.5, 14.0, 15.5):
        at(scene, handle, now)
        seen.append(picture(old))
    end = picture(new)
    assert np.abs(seen[0] - start).mean() < 0.05, "nothing has moved at the first word"
    assert all(np.abs(a - b).mean() > 0.02 for a, b in zip(seen[1:], seen[2:])), "it is still moving at every one of these times"
    assert all(np.abs(s - start).mean() > 0.02 for s in seen[2:]) and np.abs(seen[2] - end).mean() > 0.05, "neither end at the middle"
    at(scene, handle, 16.0)
    assert all(float(m.get_fill_opacity()) == 0 and float(m.get_stroke_opacity()) == 0 for m in old.family_members_with_points()), \
        "the ghost is gone once the sentence is over"
    assert np.abs(picture(new) - end).max() == 0, "and the new picture below was not touched"
    # the move is finished: the new picture is what is on screen, the same as it was drawn
    scene.stop(handle)
    assert handle[0] not in scene.mobjects and handle[2] not in scene.mobjects and new in scene.mobjects


def test_a_knob_that_moves_along_a_curve_is_driven_by_the_voice_too_a_succession_of_stations_has_no_scene_of_its_own():
    """Plan S13: the pendulum's change is a Succession of legs (S8); begin() raised AttributeError ('scene') and the move fell
    back to the lead-in tween, so the bob had finished swinging before the words."""
    from manim import Succession
    R = runtime()
    from lessonforge.longform import component_figure as CF
    out = settle(beats({"time_s": 0}, {"time_s": 0.9}, comp="simple_pendulum"))
    figures = [b["figure"] for b in out["chapters"][0]["beats"]]
    old, new = placed(CF, figures[0]), placed(CF, figures[1])
    with knobs.applied(ON):
        (group,) = new.change_from(old)
    assert any(isinstance(a, Succession) for a in group.animations), "the stations of a nonlinear knob"
    scene = Scene(R)
    scene.add(new, old)
    handle = scene.start(old, group, 10.0, 16.0)
    assert handle is not None, "it can be driven (it was None: the AttributeError was caught and the lead-in played)"
    start = picture(old)
    seen = []
    for now in (10.5, 11.5, 12.5, 13.5, 14.5, 15.4):
        at(scene, handle, now)
        seen.append(picture(old))
    assert all(np.abs(a - b).mean() > 0.01 for a, b in zip(seen, seen[1:])), "the bob is still moving at every one of these times"
    assert np.abs(seen[0] - start).mean() > 0.01 and np.abs(seen[-1] - picture(new)).mean() < 1.0, "from the old state to the new one"
    scene.stop(handle)


def test_the_new_pictures_words_wait_under_the_old_one_so_two_numbers_are_never_printed_over_each_other():
    """Plan S13: the pendulum's "time 1.8 s" faded out over "time 3.6 s" for the whole sentence (the new picture is under the
    old one from the first frame, words at full strength). Taken away while the old picture is moved, back when it goes."""
    R = runtime()
    from lessonforge.longform import component_figure as CF
    out = settle(beats({"time_s": 0}, {"time_s": 0.9}, comp="simple_pendulum"))
    figures = [b["figure"] for b in out["chapters"][0]["beats"]]
    old, new = placed(CF, figures[0]), placed(CF, figures[1])
    with knobs.applied(ON):
        (group,) = new.change_from(old)
    members = [m for t in new.labels for m in t.family_members_with_points()]
    assert members and all(float(m.get_fill_opacity()) > 0.5 for m in members)
    scene = Scene(R)
    scene.add(new, old)
    handle = scene.start(old, group, 10.0, 16.0, figure=new)
    assert handle is not None
    assert all(float(m.get_fill_opacity()) == 0 and float(m.get_stroke_opacity()) == 0 for m in members), "waiting under the old picture"
    at(scene, handle, 13.0)
    assert all(float(m.get_fill_opacity()) == 0 for m in members), "still waiting in the middle of the move"
    at(scene, handle, 16.0)
    assert all(float(m.get_fill_opacity()) > 0.5 for m in members), "back when the old picture is gone"
    # a move that is stopped early gives the words back too, and a call without the figure changes nothing
    scene2 = Scene(R)
    scene2.add(new, old)
    handle2 = scene2.start(old, group, 10.0, 16.0, figure=new)
    scene2.stop(handle2)
    assert all(float(m.get_fill_opacity()) > 0.5 for m in members)


def test_the_move_at_the_last_moment_equals_the_new_drawing_pixel_for_pixel_inside_the_card():
    scene, handle, old, new = driven()
    at(scene, handle, 15.59)
    shot_old = picture(old)
    shot_new = picture(new)
    inside = np.abs(shot_old - shot_new).mean()
    assert inside < 0.6, f"at the end of the move the old picture IS the new one (mean difference {inside:.3f})"


def test_a_focus_pulse_on_the_new_picture_does_not_move_the_old_one_being_moved():
    scene, handle, old, new = driven()
    at(scene, handle, 12.5)
    before = {id(m): np.array(m.points) for m in old.get_family() if len(m.points)}
    part = next(name for name, g in new.parts.items() if len(g.family_members_with_points()) and name in new.shown)
    (pulse,) = new.focus_animations(part)
    pulse.begin()
    pulse.interpolate(0.5)
    for m in old.get_family():
        if len(m.points):
            assert np.array_equal(before[id(m)], np.array(m.points)), "the old picture is the one being moved, and nothing else touches it"
    pulse.finish()


def test_a_driver_that_cannot_start_leaves_the_scene_as_it_was_and_a_frame_that_raises_shows_the_new_picture():
    R = runtime()
    scene = Scene(R)
    broken = SimpleNamespace(rate_func=None, begin=lambda: (_ for _ in ()).throw(RuntimeError("no")))
    ghost = SimpleNamespace()
    assert scene.start(ghost, broken, 0.0, 5.0) is None and scene.mobjects == []
    scene2, handle, old, new = driven()
    # the tick is a closure over the animation: make it raise on the next frame
    for cell in handle[1].__closure__:
        if hasattr(cell.cell_contents, "interpolate"):
            cell.cell_contents.interpolate = lambda p: (_ for _ in ()).throw(ValueError("bad frame"))
    at(scene2, handle, 12.0)
    assert all(float(m.get_fill_opacity()) == 0 for m in old.family_members_with_points()), "the new picture below is shown"


def test_inside_one_long_wait_the_clock_is_the_frames_own_because_manims_time_moves_only_between_plays():
    scene, handle, old, new = driven()
    scene.renderer.time = 10.0                         # a wait of many seconds: renderer.time stays at 10.0 throughout
    shots = []
    for frame in range(150):                           # 5 s at 30 fps
        handle[1](None, 1 / 30)
        if frame in (0, 60, 120):
            shots.append(picture(old))
    assert np.abs(shots[1] - shots[0]).mean() > 0.01 and np.abs(shots[2] - shots[1]).mean() > 0.01, "it moves while time stands still"
