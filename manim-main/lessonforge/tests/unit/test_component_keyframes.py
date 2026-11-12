"""A knob that moves a picture along a curve is morphed through the drawings it passes through (video-quality plan S8).

``component_lib.morph_plan`` / ``keyframes`` find the stations (one Node batch, at most 9 draws, several probes);
``ComponentFigure.change_from`` then moves each part's art through them. A swinging bob is the case: the straight morph from
the bob at 0 s to the bob at 2.4 s is a chord, 100 pixels off the arc. Hermetic (the pinned six components and one temporary
component), no voice, no GPU, no network.
"""
import math
import time

import numpy as np
import pytest

from lessonforge import kits, knobs
from lessonforge.longform import component_lib as lib

REASON = lib.unavailable_reason()
pytestmark = pytest.mark.skipif(bool(REASON), reason=f"components are not available here: {REASON}")

KIT = kits.get("components")
ON = {"LESSONFORGE_COMPONENT_TWEEN": "1"}
SWING = """export const meta = {
  id: "swing", title: "A dot on a swing", subject: "physics", ncert: ["Class 8, Ch 1 Mini"], size: [200, 200] as [number, number],
  params: { n: { type: "number", min: 0, max: 10, default: 3, say: "how many" } },
  parts: ["frame", "dot"], states: { phase: { type: "number", min: 0, max: 1, default: 0, say: "how far through one swing" } },
  anchors: ["mid"], example: { n: 3 },
};
export function validate(p: { n: number }): string[] { return p.n >= 0 && p.n <= 10 ? [] : ["n must be between 0 and 10"]; }
export function draw(p: { n: number }, state: { phase?: number } = {}) {
  const f = state.phase ?? 0, y = Math.round((100 + 60 * Math.sin(2 * Math.PI * f)) * 10) / 10;
  return {
    parts: { frame: `<rect x="10" y="10" width="180" height="180" fill="none" stroke="#1B2033"/>`, dot: `<circle cx="100" cy="${y}" r="8" fill="#B4236B"/>` },
    anchors: { mid: [100, 100] },
    labels: [{ part: "frame", text: "a dot", at: [100, 196], side: "below" }],
  };
}
"""


def manim_side():
    pytest.importorskip("manim", reason="manim is not installed here")
    from lessonforge.longform import component_figure as CF
    return CF


def pend(t0, t1):
    return {"state": {"time_s": t0}}, {"state": {"time_s": t1}}


@pytest.fixture
def swing(tmp_path, monkeypatch):
    root = tmp_path / "lv"
    (root / "components" / "physics").mkdir(parents=True)
    (root / "components" / "physics" / "swing.ts").write_text(SWING)
    monkeypatch.setenv(lib.ENV_DIR, str(root))
    monkeypatch.setitem(lib.TWEEN_KNOBS, "swing", ("phase",))
    return root


# ---------------------------------------------------------------- the library: stations, measured

def test_a_swinging_bob_needs_stations_and_a_linear_knob_needs_none():
    stations = lib.keyframes("simple_pendulum", *pend(0, 2.4))
    assert len(stations) >= 6, "the bob swings through more than one period: the chord is nowhere near the arc"
    assert [s["t"] for s in stations] == sorted({s["t"] for s in stations}) and 0 < stations[0]["t"] and stations[-1]["t"] < 1
    assert all(abs(s["state"]["time_s"] - 2.4 * s["t"]) < 1e-5 for s in stations), "each station is the component at that value"
    assert lib.keyframes("leaf_section", {"state": {"opening": 1}}, {"state": {"opening": 0.3}}) == [], "linear: none"


def test_a_preset_an_integer_or_structural_parameter_or_an_unlisted_knob_gets_no_stations_and_no_draw(monkeypatch):
    asked = []
    real = lib.prefetch
    monkeypatch.setattr(lib, "prefetch", lambda specs, **kw: (asked.append(list(specs)), real(specs, **kw))[1])
    assert lib.keyframes("leaf_section", {"state": {"stoma": "open"}}, {"state": {"stoma": "closed"}}) == [], "a list state"
    assert lib.keyframes("number_line", {"params": {"jump": 1}}, {"params": {"jump": 2}}) == [], "an integer parameter"
    assert lib.keyframes("number_line", {"state": {"hops_done": 0}}, {"state": {"hops_done": 2}}) == [], "a knob nobody listed"
    # a listed knob together with a name: never interpolated, never half-moved (the whole change is refused)
    entry = lib.get("leaf_section")
    assert lib.tweenable(entry, {"state": {"opening": 1}}, {"state": {"opening": 0.5, "stoma": "closed"}}) == []
    assert asked == [], "nothing was drawn for the refused changes"


def test_all_the_draws_of_a_plan_are_one_batch_of_at_most_nine(monkeypatch):
    batches = []
    real = lib.prefetch
    monkeypatch.setattr(lib, "prefetch", lambda specs, **kw: (batches.append(list(specs)), real(specs, **kw))[1])
    lib.keyframes("simple_pendulum", *pend(0.05, 2.35))
    assert len(batches) == 1 and len(batches[0]) == 2 ** lib.KEY_DEPTH + 1 == 9


def test_a_batch_of_sixty_four_draws_is_far_inside_the_node_timeout():
    specs = [("simple_pendulum", {"length_cm": 40 + i % 60}, {"time_s": round(0.07 * i, 3)}) for i in range(64)]
    began = time.time()
    lib.prefetch(specs)
    assert time.time() - began < 2.0 and lib.RUN_TIMEOUT == 20.0
    assert all(lib.draw(*spec)["parts"] for spec in specs)


def test_a_symmetric_curve_is_not_fooled_because_the_probes_are_several(swing):
    a, b = {"state": {"phase": 0}}, {"state": {"phase": 1}}
    ends = [lib.draw("swing", {}, a["state"]), lib.draw("swing", {}, b["state"])]
    mid = lib.draw("swing", {}, {"phase": 0.5})
    quarter = lib.draw("swing", {}, {"phase": 0.25})
    assert ends[0]["parts"] == ends[1]["parts"], "one whole swing: the drawing at the end is the one at the start"
    assert lib.deviation_px(ends[0], ends[1], mid, 0.5, {"dot"}) < 1e-6, "a midpoint-only test sees the chord and passes"
    assert lib.deviation_px(ends[0], ends[1], quarter, 0.25, {"dot"}) > 50, "the quarter point does not"
    stations = lib.keyframes("swing", a, b)
    assert len(stations) >= 3 and {0.25, 0.5, 0.75} <= {s["t"] for s in stations}, "so the grid is cut"


def test_a_knob_in_the_list_that_is_straight_is_measured_straight_and_a_circle_of_stations_stays_inside_the_tolerance(swing):
    """Every leg of the plan stays within the tolerance of the drawing at every grid point it spans."""
    a, b = {"state": {"phase": 0}}, {"state": {"phase": 0.2}}
    stations = lib.keyframes("swing", a, b)
    ts = [0.0] + [s["t"] for s in stations] + [1.0]
    draws = {t: lib.draw("swing", {}, {"phase": round(0.2 * t, 6)}) for t in [j / 8 for j in range(9)]}
    for lo, hi in zip(ts, ts[1:]):
        for t in (x for x in draws if lo < x < hi):
            assert lib.deviation_px(draws[lo], draws[hi], draws[t], (t - lo) / (hi - lo), {"dot"}) <= lib.KEY_TOL_PX + 1e-9


# ---------------------------------------------------------------- the Manim side: through the stations

def placed(CF, figure, by=1.0, at=(0.0, 0.0, 0.0)):
    f = CF.component(figure["params"])
    f.scale(by).move_to(np.array(at, dtype=float))
    return f


def pair(t0, t1):
    figs = []
    for t in (t0, t1):
        figs.append({"kind": "component", "params": {"id": "simple_pendulum", "state": {"time_s": t}}})
    out, issues = KIT.settle({"title": "t", "chapters": [{"id": 1, "title": "ONE", "learning_goal": "g", "role": "explain", "beats": [
        {"id": "01", "narration": "Beat a.", "steps": [{"say": "Beat", "show": "x"}], "figure": figs[0]},
        {"id": "02", "narration": "Beat b.", "steps": [{"say": "Beat", "show": "x"}], "figure": figs[1]}]}]})
    assert issues == [], issues
    return [b["figure"] for b in out["chapters"][0]["beats"]]


def scene():
    from manim import Scene
    return Scene()


def run(group, alpha):
    group._setup_scene(scene())
    group.begin()
    group.interpolate(alpha)


def bob_centre(figure):
    return np.array(figure.art["bob"].get_center()[:2], dtype=float)


def sweep(CF, t0, t1, steps):
    """The bob's distance (scene units, picture not scaled) from the component drawn at the same value of the knob, at ``steps``
    moments of the change, and the same for the straight chord, for comparison."""
    figs = pair(t0, t1)
    with knobs.applied(ON):
        old, new = placed(CF, figs[0]), placed(CF, figs[1])
        (group,) = new.change_from(old)
    assert any(type(a).__name__ == "Succession" for a in group.animations), "a part that moves along a curve goes through stations"
    group._setup_scene(scene())
    group.begin()
    errors = []
    for alpha in np.linspace(0, 1, steps):                      # the group's own easing maps alpha to the knob's t
        group.interpolate(float(alpha))
        t = float(group.rate_func(float(alpha)))
        truth = placed(CF, {"params": {"id": "simple_pendulum", "state": {"time_s": round(t0 + (t1 - t0) * t, 6)}}})
        errors.append(float(np.linalg.norm(bob_centre(old) - bob_centre(truth))))
    start, end = placed(CF, figs[0]), placed(CF, figs[1])
    chord = [float(np.linalg.norm(((1 - u) * bob_centre(start) + u * bob_centre(end))
                                  - bob_centre(placed(CF, {"params": {"id": "simple_pendulum", "state": {"time_s": round(t0 + (t1 - t0) * u, 6)}}}))))
             for u in np.linspace(0, 1, steps)]
    return errors, chord


def test_the_bob_goes_round_the_arc_not_along_the_chord():
    CF = manim_side()
    errors, chord = sweep(CF, 0.4, 0.8, 9)                      # one step of the library's own "one swing" situation
    assert max(errors) < 0.02, f"within two hundredths of a unit of the component drawn at that time, all the way: {max(errors):.4f}"
    assert max(chord) > max(errors), "(and the straight chord between the two ends is worse)"
    errors, chord = sweep(CF, 0, 2.4, 9)                        # a swing and a half in one change: nothing but stations helps
    assert errors[4] < 0.005, "half way (a station) it is the component at 1.2 s"
    assert max(errors) < 0.13 < max(chord), f"worst between two stations {max(errors):.3f} units, the chord {max(chord):.3f}"


def test_start_and_end_are_the_old_and_the_new_pixel_for_pixel_and_the_flip_holds_at_every_station():
    CF = manim_side()
    from manim import Camera
    figs = pair(0, 1.2)

    def picture(group):
        camera = Camera(pixel_width=640, pixel_height=360, frame_width=8.0, frame_height=4.5, background_color="#101010")
        camera.capture_mobject(group)
        return np.asarray(camera.pixel_array, dtype=float)[:, :, :3]
    with knobs.applied(ON):
        old, new = placed(CF, figs[0]), placed(CF, figs[1])
        (group,) = new.change_from(old)
    want_old, want_new = picture(placed(CF, figs[0])), picture(placed(CF, figs[1]))
    group._setup_scene(scene())
    group.begin()
    for alpha in (0.0, 0.25, 0.5, 0.75, 1.0):
        group.interpolate(alpha)
        assert float(old.art["support"].get_center()[1]) > float(old.art["bob"].get_center()[1]) + 0.5, "support above the bob (the flip)"
        assert float(old.art["string"].get_top()[1]) > float(old.art["bob"].get_center()[1]), f"string hangs from above at {alpha}"
        if alpha == 0.0:
            assert np.abs(picture(old) - want_old).mean() < 0.05
    group.finish()
    assert np.abs(picture(old) - want_new).mean() < 0.05, "at the end it is the new drawing"


def test_a_part_that_appears_or_goes_is_cross_faded_never_morphed_across_stations():
    CF = manim_side()
    from manim import Text
    figs = pair(0, 0.4)
    with knobs.applied(ON):
        old, new = placed(CF, figs[0]), placed(CF, figs[1])
        (group,) = new.change_from(old)
    assert old.svg["speed_arrow"] is None and new.svg["speed_arrow"] is not None, "the arrow is not drawn at rest"
    group._setup_scene(scene())
    group.begin()
    group.interpolate(0.5)
    coming = [m for m in old.art["speed_arrow"].family_members_with_points()]
    assert coming and 0 < max(float(m.get_stroke_opacity()) for m in coming) < 1, "the arrow fades in: half there at 0.5"
    assert not any(isinstance(a.mobject, Text) for a in group.animations if hasattr(a, "target_mobject")), "no word is morphed"
    group.interpolate(1.0)
    group.finish()
    assert all(float(m.get_stroke_opacity()) == pytest.approx(1.0) for m in old.art["speed_arrow"].family_members_with_points()
               if float(m.get_stroke_width()) > 0)


def test_a_straight_knob_still_uses_no_stations_and_a_curve_is_off_unless_the_control_is_on():
    CF = manim_side()
    figs = pair(0, 2.4)
    old, new = placed(CF, figs[0]), placed(CF, figs[1])
    assert new.change_from(old) == [], "off: the old fade"
    leaf = [{"kind": "component", "params": {"id": "leaf_section", "state": {"opening": o}}} for o in (1, 0.3)]
    out, _ = KIT.settle({"title": "t", "chapters": [{"id": 1, "title": "ONE", "learning_goal": "g", "role": "explain", "beats": [
        {"id": "01", "narration": "Beat a.", "steps": [{"say": "Beat", "show": "x"}], "figure": leaf[0]},
        {"id": "02", "narration": "Beat b.", "steps": [{"say": "Beat", "show": "x"}], "figure": leaf[1]}]}]})
    fs = [b["figure"] for b in out["chapters"][0]["beats"]]
    with knobs.applied(ON):
        (group,) = placed(CF, fs[1]).change_from(placed(CF, fs[0]))
    assert not any(type(a).__name__ == "Succession" for a in group.animations)
