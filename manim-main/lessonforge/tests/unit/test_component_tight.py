"""Video-quality plan S12: larger writing inside a library component's card (control ``LESSONFORGE_COMPONENT_TIGHT``, default off).

Measured first, on the library's 28 components (``docs/engine/kits.md``, "Larger writing in the card"): the card is already the box of
the drawing's parts and labels plus a margin, so there is no hidden reserve to crop; what can grow is the label size (14 px, so 18
to 35 pt on the stage) and the 0.18 margin. Off, a figure is built exactly as before. On, labels are as large as the room between
them allows (``tight_px``: no new pair of labels on each other, the picture at most 3% smaller), one size for a run of beats on one
card, and the margin is 0.10. Hermetic (the pinned six components), no voice, no GPU."""
import numpy as np
import pytest

from lessonforge import knobs
from lessonforge.longform import component_lib as lib

REASON = lib.unavailable_reason()
pytestmark = pytest.mark.skipif(bool(REASON), reason=f"components are not available here: {REASON}")
ON = {"LESSONFORGE_COMPONENT_TIGHT": "1"}
IDS = ["force_block", "leaf_section", "test_tube", "number_line", "child", "simple_pendulum"]


def manim_side():
    pytest.importorskip("manim", reason="manim is not installed here")
    from lessonforge.longform import component_figure as CF
    return CF


def test_the_control_is_off_by_default_and_a_render_subprocess_is_told():
    assert knobs.BY_ID["LESSONFORGE_COMPONENT_TIGHT"].default == "0" and knobs.BY_ID["LESSONFORGE_COMPONENT_TIGHT"].render is True
    assert knobs.get("LESSONFORGE_COMPONENT_TIGHT", "0") == "0"
    with knobs.applied(ON):
        assert knobs.render_env() == ON


@pytest.mark.parametrize("cid", IDS)
def test_off_a_figure_is_built_as_it_always_was(cid):
    CF = manim_side()
    fig = CF.component({"id": cid})
    old = CF.ComponentFigure(lib.draw(cid, None, None))              # the constructor's own defaults are the old values
    assert fig.label_px == CF.LABEL_PX == 14.0 and fig.pad == CF.CARD_PAD == 0.18
    assert (fig.card.width, fig.card.height) == pytest.approx((old.card.width, old.card.height), abs=1e-12)
    # the refactored label placement is the old one: every label at the same place with the same size
    assert [np.round(m.get_center(), 9).tolist() for m in fig.labels] == [np.round(m.get_center(), 9).tolist() for m in old.labels]
    assert [float(m.font_size) for m in fig.labels] == [float(m.font_size) for m in old.labels]


@pytest.mark.parametrize("cid", IDS)
def test_on_the_writing_is_larger_and_the_picture_is_not_smaller_by_more_than_3_percent(cid):
    CF = manim_side()
    from lessonforge.longform import look
    off = CF.component({"id": cid})
    with knobs.applied(ON):
        on = CF.component({"id": cid})
    assert on.pad == CF.TIGHT_PAD and on.label_px >= CF.LABEL_PX
    if off.labels:
        assert min(float(m.font_size) for m in on.labels) >= min(float(m.font_size) for m in off.labels) - 1e-9
    room = lambda f: max(min(bw / f.card.width, bh / f.card.height) for bw, bh in look.picture_boxes(look.for_new()))   # noqa: E731
    assert room(on) >= CF.TIGHT_KEEP * room(off) - 1e-9
    # the number of label pairs on each other did not grow
    assert CF.label_collisions(lib.draw(cid, None, None), on.label_px) <= CF.label_collisions(lib.draw(cid, None, None), CF.LABEL_PX)


def test_a_size_that_puts_one_label_on_another_is_not_used():
    CF = manim_side()
    drawn = lib.draw("force_block", None, None)
    first = dict(drawn["labels"][0], at=[100, 100], side="right", text="12345678")          # its box ends 70 px on from its anchor at 14 px

    def two(gap):
        return {**drawn, "labels": [first, dict(first, at=[100 + 6 + 64 + gap - 6, 100], text="x")]}      # the next one starts gap px on
    wide = two(14)
    assert CF.label_collisions(wide, 14.0) == 0
    px = CF.tight_px([wide])
    assert px > CF.LABEL_PX and CF.label_collisions(wide, px) == 0           # the largest size at which nothing lands on anything
    assert all(CF.label_collisions(wide, bigger) > 0 for bigger in CF.TIGHT_PX if bigger > px)
    gaps = [g for g in range(0, 14) if CF.label_collisions(two(g), 14.0) == 0 and CF.label_collisions(two(g), CF.TIGHT_PX[-1]) > 0]
    assert gaps, "a gap that is clear at 14 px and not at 15 px"
    assert CF.tight_px([two(gaps[0])]) == CF.LABEL_PX            # no larger size helps: the old one, never a worse one
    far = {**drawn, "labels": [dict(first, at=[10, 10], text="a"), dict(first, at=[200, 200], text="b")]}
    assert CF.tight_px([far]) == CF.TIGHT_PX[0]


def test_label_collisions_grow_with_the_size_by_the_library_check_boxes():
    CF = manim_side()
    drawn = lib.draw("force_block", None, None)
    a = dict(drawn["labels"][0], at=[100, 100], side="right", text="12345678")
    b = dict(drawn["labels"][0], at=[100 + 6 + 8 * 8 + 4, 100], side="right", text="x")        # 4 px clear of a at 14 px
    two = {**drawn, "labels": [a, b]}
    assert CF.label_collisions(two, 14.0) == 0 and CF.label_collisions(two, 18.0) == 1


def test_a_run_of_beats_shares_one_label_size_and_one_card():
    CF = manim_side()
    from lessonforge import kits
    kit = kits.get("components")
    beats = [{"id": f"{i + 1:02}", "narration": "A hop.", "steps": [{"say": "Beat", "show": "x"}],
              "figure": {"kind": "component", "params": {"id": "number_line", "state": {"hops_done": n}}}} for i, n in enumerate((0, 1, 3))]
    out, issues = kit.settle({"title": "t", "chapters": [{"id": 1, "title": "ONE", "learning_goal": "g", "role": "explain", "beats": beats}]})
    assert issues == []
    with knobs.applied(ON):
        figs = [CF.component(b["figure"]["params"]) for b in out["chapters"][0]["beats"]]
    assert len({f.label_px for f in figs}) == 1 and len({round(float(f.card.width), 6) for f in figs}) == 1
    assert len({round(float(f.card.height), 6) for f in figs}) == 1
    assert figs[0].pad == CF.TIGHT_PAD
