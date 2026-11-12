"""Video-quality plan S10: geometry shown by motion. Two new figure keys, both off unless a beat writes them.

``drag`` (a triangle's corner is dragged round while a live sum line stays at 180) and ``transfer`` (a copy of one angle makes
half a turn and lands on the angle it equals). Pure: no voice, no GPU; frames are made by stepping the figure's own animator."""
import copy
import math

import pytest

from lessonforge.harness import shapes as SH
from lessonforge.longform import geometry as G
from lessonforge.longform import shape_figure as SF

TRI = {"points": {"A": [2.962, 3.53], "B": [0, 0], "C": [5.0, 0], "D": [0.262, 3.53], "E": [5.662, 3.53]},
       "polygon": "ABC", "is": ["convex"]}
SHAPES = {"tri": TRI}
DAB = {"at": "A", "from": "D", "to": "B", "role": "given"}
ALT = {"kind": "shape", "use": "tri", "segments": ["DE"], "parallel": [["DE", "BC"]], "angles": [DAB, {"at": "B"}],
       "transfer": {"from": "B", "to": DAB}}


def expanded(figure, shapes=SHAPES):
    out, issues = SH.expand(copy.deepcopy(figure), copy.deepcopy(shapes))
    return out, issues


def texts(mob):
    return [str(m.text) for m in mob.get_family() if hasattr(m, "text")]


def frame(fig, alpha):
    work = fig.origin.copy()
    animation = fig.animator(work, 3.0)
    animation.begin()
    animation.interpolate(alpha)
    return work.submobjects[0]


# ── drag ──────────────────────────────────────────────────────────────────────────────────────────────────────────

def test_drag_path_is_pure_and_every_point_on_the_way_is_a_real_triangle():
    pts = {"A": [2.962, 3.53], "B": [0, 0], "C": [5.0, 0]}
    path = G.drag_path(pts, "ABC", "A")
    assert path == G.drag_path(dict(pts), "ABC", "A") and len(path) == len(G.DRAG_TOUR) + 1
    assert path[-1] == [2.962, 3.53]                              # it goes home
    spec = {"points": pts, "polygon": "ABC", "move": {"A": path}}
    worst = 180.0
    for i in range(401):
        angles = G.Model(SF.at_alpha(spec, i / 400)).interior()
        assert abs(sum(angles.values()) - 180.0) < 1e-6
        worst = min(worst, *angles.values())
    assert worst >= G.DRAG_MIN
    kinds = {max(G.Model(SF.at_alpha(spec, i / 400)).interior().values()) > 90.0 for i in range(401)}
    assert kinds == {True, False}                                  # it is acute somewhere and obtuse somewhere


@pytest.mark.parametrize("mover,flip", [("A", False), ("B", False), ("C", True)])
def test_drag_path_works_for_any_corner_and_either_side_of_the_base(mover, flip):
    pts = {"A": [1.0, 3.0], "B": [0, 0], "C": [5.0, 0]}
    if flip:
        pts = {k: [v[0], -v[1]] for k, v in pts.items()}
    spec = {"points": pts, "polygon": "ABC", "move": {mover: G.drag_path(pts, "ABC", mover)}}
    for i in range(201):
        assert min(G.Model(SF.at_alpha(spec, i / 200)).interior().values()) >= G.DRAG_MIN


def test_drag_path_refuses_what_is_not_a_triangle_corner():
    quad = {"A": [0, 0], "B": [4, 0], "C": [4, 3], "D": [0, 3]}
    assert G.drag_path(quad, "ABCD", "A") is None
    assert G.drag_path({"A": [0, 0], "B": [1, 0], "C": [2, 0]}, "ABC", "B") is None        # in a line: nothing to drag
    assert G.drag_path({"A": [0, 1], "B": [0, 0], "C": [3, 0]}, "ABC", "Z") is None


def test_drag_key_writes_the_move_and_the_live_sum_and_nothing_else_changes():
    plain, _ = expanded({"kind": "shape", "use": "tri"})
    assert "move" not in plain and "angles" not in plain and "angle_sum" not in plain         # no key: no change
    out, issues = expanded({"kind": "shape", "use": "tri", "drag": "A"})
    assert issues == [] and list(out["move"]) == ["A"] and out["angles"] == ["A", "B", "C"] and out["angle_sum"] is True
    again, issues = SH.expand(copy.deepcopy(out), {})              # a figure settled again is not changed
    assert issues == [] and again["move"] == out["move"]
    mine, _ = expanded({"kind": "shape", "use": "tri", "drag": "A", "angles": ["A"], "angle_sum": False})
    assert mine["angles"] == ["A"] and mine["angle_sum"] is False  # what the beat wrote wins
    own, _ = expanded({"kind": "shape", "use": "tri", "drag": "A", "move": {"A": [[1, 1]]}})
    assert own["move"] == {"A": [[1, 1]]}                           # an authored move is kept


def test_a_bad_drag_is_a_plain_fault():
    _, issues = expanded({"kind": "shape", "use": "tri", "drag": "Q"})
    assert len(issues) == 1 and "one corner of a triangle" in issues[0]


def test_the_frame_holds_the_tour_only_when_a_beat_drags():
    def frame_of(figure):
        lesson = {"shapes": copy.deepcopy(SHAPES), "chapters": [{"beats": [{"narration": "x", "figure": figure}]}]}
        done, _ = SH.settle(lesson)
        return done["chapters"][0]["beats"][0]["figure"]["frame"]
    plain = frame_of({"kind": "shape", "use": "tri"})
    assert plain == [0.0, 0.0, 5.662, 3.53]                          # exactly as before
    dragged = frame_of({"kind": "shape", "use": "tri", "drag": "A"})
    assert dragged[1] < 0 or dragged[3] > 3.53 or dragged[0] < 0 or dragged[2] > 5.662


def test_the_sum_line_stays_at_180_while_the_corner_and_the_angles_move():
    out, _ = expanded({"kind": "shape", "use": "tri", "drag": "A"})
    fig = SF.build(out)
    assert fig.animator is not None
    corners, sums, values = set(), set(), set()
    for k in range(11):
        picture = frame(fig, k / 10)
        said = texts(picture)
        sums |= {t.split("=")[-1].strip() for t in said if "+" in t}
        values |= {t for t in said if t.endswith("°") and "+" not in t}
        corners.add(round(float(picture.parts["A"].get_center()[0]), 2))
    assert sums == {"180°"} and len(corners) >= 6 and len(values) >= 12


# ── transfer ──────────────────────────────────────────────────────────────────────────────────────────────────────

def test_a_copy_of_angle_b_lands_on_angle_dab_for_parallel_lines_and_not_otherwise():
    out, issues = expanded(ALT)
    assert issues == []
    model = G.Model(out)
    assert G.transfer_fault(model, out["transfer"]) is None
    askew = copy.deepcopy(SHAPES)
    askew["tri"]["points"]["E"] = [5.662, 4.5]                         # DE no longer parallel to BC
    askew["tri"]["points"]["D"] = [0.262, 3.0]
    bad, _ = expanded(ALT, askew)
    assert "does not land" in G.transfer_fault(G.Model(bad), bad["transfer"])
    assert "different corners" in G.transfer_fault(model, {"from": "B", "to": "B"})
    assert "not in the picture" in G.transfer_fault(model, {"from": "B", "to": {"at": "Z"}})
    assert "must be" in G.transfer_fault(model, "B")


def test_check_figure_reports_a_transfer_that_does_not_land_or_is_not_listed():
    out, _ = expanded(ALT)
    assert SH.check_figure(out, "Look at angle B.", "beat 1") == []
    unlisted = dict(out, angles=[{"at": "B"}])
    assert any("both angles must be listed" in i for i in SH.check_figure(unlisted, "x", "beat 1"))
    askew = copy.deepcopy(SHAPES)
    askew["tri"]["points"]["E"], askew["tri"]["points"]["D"] = [5.662, 4.5], [0.262, 3.0]
    bad, _ = expanded(ALT, askew)
    assert any("does not land" in i for i in SH.check_figure(bad, "x", "beat 1"))


def test_the_copy_turns_about_the_middle_of_AB_and_the_number_waits_for_it():
    out, _ = expanded(ALT)
    fig = SF.build(out)
    assert fig.animator is not None
    built = {n: fig.parts[n].get_stroke_opacity() if n.endswith("DAB") else None for n in ("angle_DAB",)}
    assert built["angle_DAB"] == 0                                    # the picture that fades in has no landed arc

    start, mid, end = frame(fig, 0.0), frame(fig, 0.475), frame(fig, 1.0)
    b_arc = start.parts["angle_B"].get_center()
    assert "transfer" in start.parts and "transfer" in mid.parts and "transfer" not in end.parts
    assert float(abs(start.parts["transfer"].get_center() - b_arc)[:2].max()) < 0.25          # it starts on angle B
    mid_c = mid.parts["transfer"].get_center()
    assert float(abs(mid_c - b_arc)[:2].max()) > 0.5                                         # and is away from it
    landed = end.parts["angle_DAB"]
    assert end.parts["angle_DAB_value"].get_fill_opacity() > 0.9 and landed.get_stroke_opacity() > 0.9
    for part in ("angle_DAB", "angle_DAB_value"):                                            # hidden until it lands
        assert start.parts[part].get_fill_opacity() == 0 and start.parts[part].get_stroke_opacity() == 0
        assert mid.parts[part].get_fill_opacity() == 0 and mid.parts[part].get_stroke_opacity() == 0
    # the ghost at the half turn's end sits on the arc it lands on
    late = frame(fig, SF.TRANSFER_WINDOW[1] - 1e-4)
    gap = late.parts["transfer"].get_center() - late.parts["angle_DAB"].get_center()
    assert float(abs(gap)[:2].max()) < 0.25          # a wedge's box centre is inside the arc's box


def test_transfer_progress_waits_turns_and_rests():
    lo, hi = SF.TRANSFER_WINDOW
    assert SF.transfer_progress(0) == 0 and SF.transfer_progress(lo) == 0 and SF.transfer_progress(hi) == 1
    assert SF.transfer_progress(1) == 1
    mid = SF.transfer_progress((lo + hi) / 2)
    assert math.isclose(mid, 0.5, abs_tol=1e-9)


# ── the gate: a figure that writes neither key is exactly what it was ─────────────────────────────────────────────

def test_no_key_no_ghost_no_motion_and_at_alpha_is_unchanged():
    out, _ = expanded({"kind": "shape", "use": "tri", "angles": ["A", "B", "C"]})
    fig = SF.build(out)
    assert getattr(fig, "animator", None) is None and "transfer" not in fig.parts
    assert "_t" not in SF.at_alpha({"points": {"A": [0, 0]}, "move": {"A": [[1, 1]]}}, 0.5)
    spec = {"points": {"A": [0, 0]}, "move": {"A": [[1, 1]]}}
    assert SF.at_alpha(spec, 0.5) == {"points": {"A": [0.5, 0.5]}}
    assert "info" not in fig.info.get("angle_geom", {}) and set(fig.info["angle_geom"]) == {"A", "B", "C"}
