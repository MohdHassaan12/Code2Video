"""A run of beats on one library component shares one card (video-quality plan S6, ``docs/engine/kits.md``).

The kit pass ``_focus`` writes ``span`` (the distinct {params, state} of the run) on every figure of a run of consecutive
beats on one component id; ``component_figure.component`` measures them all in one Node batch and sets the card to their
union plus the anchors; the runtime treats figures that share a span as one run. Hermetic: ``conftest.py`` points the
kit at the pinned six components. No voice, no GPU, no network.
"""
import copy
import json
import types

import pytest

from lessonforge import kits, knobs
from lessonforge.kits import components as C
from lessonforge.longform import component_lib as lib

REASON = lib.unavailable_reason()
pytestmark = pytest.mark.skipif(bool(REASON), reason=f"components are not available here: {REASON}")

KIT = kits.get("components")


def fig(cid="number_line", state=None, params=None, **extra):
    inner = {"id": cid, **extra}
    if params is not None:
        inner["params"] = params
    if state is not None:
        inner["state"] = state
    return {"kind": "component", "params": inner}


def beat(n, figure=None, steps=None):
    out = {"id": f"{n:02}", "narration": f"Beat number {n}.", "steps": steps or [{"say": "Beat number", "show": "x"}]}
    if figure is not None:
        out["figure"] = figure
    return out


def lesson(*beats):
    return {"title": "t", "chapters": [{"id": 1, "title": "ONE", "learning_goal": "g", "role": "explain", "beats": list(beats)}]}


def settled(*beats):
    out, issues = KIT.settle(lesson(*beats))
    assert not [i for i in issues if "span" in i or "focus" in i], issues
    return [b.get("figure") for b in out["chapters"][0]["beats"]], out


def spans(figures):
    return [(f or {}).get("params", {}).get("span") for f in figures]


# ---------------------------------------------------------------- the kit pass: which beats get a span

def test_every_beat_of_a_run_gets_the_same_span_and_a_run_of_one_gets_none():
    figures, _ = settled(beat(1, fig(state={"hops_done": 0})), beat(2, fig(state={"hops_done": 1})), beat(3, fig(state={"hops_done": 3})),
                         beat(4, fig("simple_pendulum")), beat(5, fig("leaf_section")))
    one, two, three, pend, leaf = spans(figures)
    assert one == two == three and len(one) == 3, one
    assert one == sorted(one, key=lambda e: json.dumps(e, sort_keys=True)), "written in a fixed order"
    assert {json.dumps(e, sort_keys=True) for e in one} == {json.dumps({"state": {"hops_done": v}}, sort_keys=True) for v in (0, 1, 3)}
    assert pend is None and leaf is None, "a run of one drawing has no span: nothing to share"


def test_a_figure_repeated_on_a_later_beat_adds_nothing_and_a_beat_with_no_figure_does_not_break_the_run():
    figures, _ = settled(beat(1, fig(state={"hops_done": 0})), beat(2), beat(3, fig(state={"hops_done": 1})), beat(4, fig(state={"hops_done": 0})))
    got = spans([figures[0], figures[2], figures[3]])
    assert got[0] == got[1] == got[2] and len(got[0]) == 2
    assert "figure" not in lesson(beat(2))["chapters"][0]["beats"][0]


def test_another_component_or_another_kits_picture_ends_the_run():
    shape = {"kind": "shape", "points": {"A": [0, 0], "B": [4, 0], "C": [0, 3]}, "polygon": "ABC"}
    figures, _ = settled(beat(1, fig(state={"hops_done": 0})), beat(2, fig(state={"hops_done": 1})), beat(3, fig("simple_pendulum")),
                         beat(4, fig(state={"hops_done": 0})), beat(5, shape), beat(6, fig(state={"hops_done": 1})))
    got = spans(figures)
    assert got[0] == got[1] and len(got[0]) == 2
    assert got[2] is None and got[3] is None and got[5] is None, "the pendulum ends the first run; the shape ends the second"


def test_a_run_is_cut_at_the_limit_and_the_next_state_starts_a_new_span():
    states = [{"hops_done": i / 4} for i in range(14)]          # 14 distinct drawings
    figures, _ = settled(*[beat(i + 1, fig(state=s)) for i, s in enumerate(states)])
    got = spans(figures)
    assert max(len(g) for g in got) == C.SPAN_LIMIT == 12
    assert got[0] == got[11] and got[12] == got[13] and got[0] != got[12] and len(got[12]) == 2


def test_a_stale_span_is_rewritten_on_every_settle_and_never_carried_by_normalise_figure():
    figures, out = settled(beat(1, fig(state={"hops_done": 0})), beat(2, fig(state={"hops_done": 1})))
    stale = copy.deepcopy(out)
    stale["chapters"][0]["beats"][0]["figure"]["params"]["span"] = [{"state": {"hops_done": 6}}]
    stale["chapters"][0]["beats"][1]["figure"]["params"]["span"] = [{"state": {"hops_done": 6}}]
    again, _ = KIT.settle(stale)
    assert spans([b["figure"] for b in again["chapters"][0]["beats"]]) == spans(figures)
    solo, _ = settled(beat(1, fig(state={"hops_done": 0}, span=[{"state": {"hops_done": 6}}])))
    assert spans(solo) == [None], "a span left on a figure whose run has one drawing is dropped"
    canon = KIT.normalise_figure(figures[0])
    assert "span" not in canon["params"]
    assert canon["manifest"] == figures[0]["manifest"], "the span is not part of the drawing's name"
    assert C.override_figure(figures[0], state={"hops_done": 3})["params"].get("span") is None


def test_the_reveal_of_a_drawing_is_unchanged_by_the_span():
    steps = [{"say": "Beat number", "show": "x", "focus": "frog"}]
    figures, _ = settled(beat(1, fig(state={"hops_done": 0}), steps), beat(2, fig(state={"hops_done": 1})))
    assert figures[0]["params"]["reveal"] == ["frog"] and "reveal" not in figures[1]["params"]


def test_the_switch_turns_it_off_and_a_stored_lesson_without_a_span_is_as_it_was():
    with knobs.applied({"LESSONFORGE_COMPONENT_FRAME": "0"}):
        figures, _ = settled(beat(1, fig(state={"hops_done": 0})), beat(2, fig(state={"hops_done": 1})))
    assert spans(figures) == [None, None]
    assert "span" not in json.dumps(figures)
    assert knobs.BY_ID["LESSONFORGE_COMPONENT_FRAME"].default == "1"


def test_span_is_checked_in_plain_words():
    for bad in ([], "x", [1], [{"params": 1}], [{"colour": {}}], [{"state": {}}] * 13):
        with pytest.raises(kits.KitError, match="span must be a list"):
            C.figure_extras(fig(span=bad))
    assert C.figure_extras(fig(span=[{"state": {"hops_done": 1}}]))["span"] == [{"state": {"hops_done": 1}}]
    # the writer cannot be asked for it: the rules never mention it, and a flat figure with a span still parses
    assert "span" not in C.COMPONENT_RULES
    assert C.parse_figure(fig(span=[{"state": {"hops_done": 1}}]))[0] == "number_line"


# ---------------------------------------------------------------- the Manim side: one card, one place

def _manim():
    pytest.importorskip("manim", reason="manim is not installed here")
    from lessonforge.longform import component_figure as CF
    return CF


def _box(mob):
    return (float(mob.get_left()[0]), float(mob.get_right()[0]), float(mob.get_bottom()[1]), float(mob.get_top()[1]))


def test_states_of_one_span_have_one_card_and_one_size_while_alone_they_differ():
    CF = _manim()
    figures, _ = settled(beat(1, fig(state={"hops_done": 0})), beat(2, fig(state={"hops_done": 1})), beat(3, fig(state={"hops_done": 3})))
    built = [CF.component(f["params"]) for f in figures]
    for f in built[1:]:
        assert f.card.width == pytest.approx(built[0].card.width, abs=1e-6)
        assert f.card.height == pytest.approx(built[0].card.height, abs=1e-6)
        assert [float(x) for x in f.card.get_center()] == pytest.approx([float(x) for x in built[0].card.get_center()], abs=1e-6)
        assert (f.width, f.height) == pytest.approx((built[0].width, built[0].height), abs=1e-6), "what the stage scales by"
    alone = [CF.component({k: v for k, v in f["params"].items() if k != "span"}) for f in figures]
    assert abs(alone[0].card.height - alone[1].card.height) > 0.3, "today the card changes size between the states"
    assert built[0].card.height >= max(a.card.height for a in alone) - 1e-9, "and the span holds the largest"


def test_the_card_holds_every_drawing_and_every_anchor_of_every_state():
    CF = _manim()
    figures, _ = settled(beat(1, fig(state={"hops_done": 0})), beat(2, fig(state={"hops_done": 1.5})), beat(3, fig(state={"hops_done": 3})))
    built = [CF.component(f["params"]) for f in figures]
    left, right, bottom, top = _box(built[0].card)
    for f in built:
        for name, dot in f.anchors.items():
            x, y = float(dot.get_center()[0]), float(dot.get_center()[1])
            assert left <= x <= right and bottom <= y <= top, f"anchor {name} lies inside the shared card"
        for part in f.art.values():
            if len(part.submobjects):
                b = _box(part)
                assert left - 1e-6 <= b[0] and b[1] <= right + 1e-6 and bottom - 1e-6 <= b[2] and b[3] <= top + 1e-6
    # the frog anchor moves from the line to the air: both positions are inside the card in every state's figure
    ys = [float(f.anchors["frog"].get_center()[1]) for f in built]
    assert len({round(y, 3) for y in ys}) > 1 and bottom <= min(ys) and max(ys) <= top


def test_the_figures_own_drawing_is_always_in_the_union_even_when_the_span_forgot_it():
    CF = _manim()
    inner = fig(state={"hops_done": 3})["params"]
    inner["span"] = [{"state": {"hops_done": 0}}]               # a hand-written span that lacks this figure's own state
    f = CF.component(inner)
    own = CF.component({"id": "number_line", "state": {"hops_done": 3}})
    assert f.card.height >= own.card.height - 1e-9 and f.card.width >= own.card.width - 1e-9
    assert _box(f.card)[2] <= own.extent[2] and _box(f.card)[3] >= own.extent[3]


def test_a_span_that_cannot_be_drawn_falls_back_to_the_figures_own_card():
    CF = _manim()
    inner = fig(state={"hops_done": 1})["params"]
    inner["span"] = [{"state": {"hops_done": 0}}, {"state": {"hops_done": 99}}]       # out of range: ComponentError
    f = CF.component(inner)
    own = CF.component({"id": "number_line", "state": {"hops_done": 1}})
    assert f.span is None
    assert (f.card.width, f.card.height) == pytest.approx((own.card.width, own.card.height), abs=1e-9)


def test_a_figure_with_no_span_is_built_exactly_as_before():
    CF = _manim()
    f = CF.component({"id": "number_line", "state": {"hops_done": 0}})
    content = [g for g in f.art.values() if len(g.submobjects)] + f.labels
    left = min(float(m.get_left()[0]) for m in content)
    right = max(float(m.get_right()[0]) for m in content)
    assert f.card.width == pytest.approx(right - left + 2 * CF.CARD_PAD, abs=1e-9)
    assert f.span is None and f.span_box is None


def test_the_span_is_measured_in_one_batch_and_each_drawing_once_per_process(monkeypatch):
    CF = _manim()
    calls = []
    real = lib.prefetch
    monkeypatch.setattr(lib, "prefetch", lambda specs, **kw: (calls.append(list(specs)), real(specs, **kw))[1])
    inner = fig(state={"hops_done": 0})["params"]
    inner["span"] = [{"state": {"hops_done": v}} for v in (0, 1, 2, 3)]
    CF.component(inner)
    assert len(calls) == 1 and len(calls[0]) >= 4, "all the drawings of the span are asked for in ONE prefetch"
    built = []
    real_init = CF.ComponentFigure.__init__
    monkeypatch.setattr(CF.ComponentFigure, "__init__", lambda self, *a, **kw: (built.append(1), real_init(self, *a, **kw))[1])
    CF.component(inner)
    assert len(built) == 1, "the other states' boxes come from the cache: only the figure itself is built again"


# ---------------------------------------------------------------- the runtime: one run

def test_the_runtime_treats_beats_that_share_a_span_as_one_run_and_others_as_before():
    pytest.importorskip("manim", reason="manim is not installed here")
    from lessonforge.longform.runtime import GuidedChapter
    figures, out = settled(beat(1, fig(state={"hops_done": 0})), beat(2, fig(state={"hops_done": 1})), beat(3, fig("simple_pendulum")))
    key = GuidedChapter._run_key
    assert key(figures[0]) == key(figures[1]) != key(figures[2])
    plain = fig(state={"hops_done": 0})
    assert key(plain) == json.dumps(plain, sort_keys=True), "no span: the figure itself, as before"
    assert key(None) is None and key({}) is None
    # a figure of another kind never takes the span path
    assert key({"kind": "shape", "params": {"span": [1]}}) == json.dumps({"kind": "shape", "params": {"span": [1]}}, sort_keys=True)
    # _run_board answers for the whole run: a formula in the SECOND beat makes the FIRST beat's picture a board too
    chapter = out["chapters"][0]
    chapter["beats"][1]["steps"] = [{"say": "Beat", "show": "a = 1 + 2", "kind": "math"}]
    me = types.SimpleNamespace(lesson=out, _run_key=key)
    assert GuidedChapter._run_board(me, chapter["beats"][0]) is True
    assert GuidedChapter._run_board(me, chapter["beats"][2]) is False
    unsettled = lesson(beat(1, fig(state={"hops_done": 0})), beat(2, fig(state={"hops_done": 1})))
    unsettled["chapters"][0]["beats"][1]["steps"] = [{"say": "Beat", "show": "a = 1 + 2", "kind": "math"}]
    old = types.SimpleNamespace(lesson=unsettled, _run_key=key)
    assert GuidedChapter._run_board(old, unsettled["chapters"][0]["beats"][0]) is False, "a stored lesson without a span: as it was"
