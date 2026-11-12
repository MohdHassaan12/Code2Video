"""Video-quality plan S13: a dragged corner or a turning angle goes on across the whole sentence (figure key ``pace: voice``).

``runtime.stage_progress`` plays a stage SOON AND THEN WAITS (40% of the gap to the next step, at least 1.2 s): right for a block
that appears, wrong for a corner that is dragged. ``across=True`` takes the whole gap. Off (every stored lesson, every figure
without the key) the numbers are exactly what they were. Pure: no voice, no GPU."""
import copy

import pytest

from lessonforge.longform import runtime as R
from lessonforge.longform import shape_figure as SF
from lessonforge.harness import shapes as SH

TRI = {"points": {"A": [2.962, 3.53], "B": [0, 0], "C": [5.0, 0], "D": [0.262, 3.53], "E": [5.662, 3.53]},
       "polygon": "ABC", "is": ["convex"]}


def old_stage_progress(now, start, total, edges):
    """The function as it was before ``across`` was added (copied)."""
    if not edges:
        return min(1.0, max(0.0, (now - start) / max(total, 1e-6)))
    if now <= edges[0]:
        return 0.0
    last = len(edges) - 1
    k = max(i for i, e in enumerate(edges) if now >= e)
    until = edges[k + 1] if k < last else max(start + total, edges[k] + 1.0)
    done = min(1.0, (now - edges[k]) / R.stage_seconds(until - edges[k]))
    return (k + (done if k == last else min(done, .999))) / len(edges)


@pytest.mark.parametrize("edges", [[], [10.0], [10.0, 14.0], [10.0, 14.0, 21.0]])
def test_without_across_the_progress_is_exactly_what_it_was(edges):
    for i in range(0, 400):
        now = 8.0 + i * 0.05
        assert R.stage_progress(now, 10.0, 16.0, edges) == old_stage_progress(now, 10.0, 16.0, edges)
        assert R.stage_progress(now, 10.0, 16.0, edges, False) == old_stage_progress(now, 10.0, 16.0, edges)


def test_across_takes_the_whole_gap_to_the_next_step_and_not_the_first_part_of_it():
    edges = [10.0, 20.0]
    p = lambda now, **kw: R.stage_progress(now, 10.0, 20.0, edges, **kw)  # noqa: E731
    assert p(10.0, across=True) == 0.0 and p(9.0, across=True) == 0.0       # nothing moves before the first step
    assert p(15.0, across=True) == pytest.approx(0.25)                      # halfway through stage 1 of 2
    assert p(15.0) == pytest.approx(0.4995)                                 # soon-and-waits has already finished it
    assert p(19.9, across=True) == pytest.approx(0.495, abs=0.001) and p(20.0, across=True) == pytest.approx(0.5)
    assert p(25.0, across=True) == pytest.approx(0.75)                      # stage 2 runs from 20 to the end of the speech (30)
    assert p(30.0, across=True) == 1.0 and p(99.0, across=True) == 1.0


def test_across_is_monotone_and_moves_at_every_moment_of_the_voice():
    edges = [10.0, 13.0, 19.0]
    seen = [R.stage_progress(10.0 + i * 0.1, 10.0, 12.0, edges, True) for i in range(0, 120)]
    assert all(b >= a for a, b in zip(seen, seen[1:]))
    assert all(b > a for a, b in zip(seen[:-1], seen[1:])) or sum(b == a for a, b in zip(seen, seen[1:])) <= 3


def test_the_figure_key_sets_the_flag_and_nothing_else_changes():
    shapes = {"tri": copy.deepcopy(TRI)}

    def built(figure):
        out, issues = SH.expand(copy.deepcopy(figure), copy.deepcopy(shapes))
        assert issues == []
        return SF.build(out)

    plain = built({"kind": "shape", "use": "tri", "drag": "A"})
    paced = built({"kind": "shape", "use": "tri", "drag": "A", "pace": "voice"})
    assert plain.voice_paced is False and paced.voice_paced is True
    assert plain.animator is not None and paced.animator is not None
    still = built({"kind": "shape", "use": "tri"})
    assert not getattr(still, "voice_paced", False) and getattr(still, "animator", None) is None
    other = built({"kind": "shape", "use": "tri", "drag": "A", "pace": "even"})
    assert other.voice_paced is False                                       # only the one word turns it on
