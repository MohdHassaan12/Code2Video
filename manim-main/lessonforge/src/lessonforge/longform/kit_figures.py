"""Manim-side builders for subject-kit figures (the kit itself is pure: ``lessonforge.kits``).

``figures.build`` resolves a kit's builder from ``kits.builder_for(kind)`` when ``BUILDERS`` has no entry. A builder is
``(params) -> Figure`` and may raise: ``build`` then says so and the previous picture stays.
"""
from __future__ import annotations

from . import figures, motion_math, reaction_math


def motion(p: dict) -> figures.Figure:
    """A speed-time graph drawn only from the model: the line, the y range and each labelled point come from
    ``motion_math`` (``graph_params``), through the existing graph builder, so parts and draw order are the graph's:
    axes, x_label, y_label, curve0, curve0_label, point0, point0_label, ...

    Raises ``motion_math.MotionError`` (a ``ValueError``) for numbers that are not a coherent motion.
    """
    m = motion_math.solve(p)
    params = motion_math.graph_params(m, zero_floor=bool(p.get("zero_floor")))
    held = [float(t) for t in (p.get("hold_marks") or []) if isinstance(t, (int, float)) and not isinstance(t, bool)]
    if held:
        # ``harness.quiz_leaks.hold``: a quiz is asked about these marks, so their points and labels wait for the beat
        # after it. Only the drawing waits: the y range above still comes from every mark, so the graph does not rescale
        # when the answer is drawn in, and the model (every number the kit checks) is untouched.
        # The point keeps its place in the list (``hold``: the graph builder skips drawing it), so the others keep their
        # names (``point2`` stays the 4 s mark that a step may focus on) and their label places.
        params["points"] = [{**q, "hold": True} if any(abs(q["x"] - t) <= 1e-9 + 0.005 for t in held) else q
                            for q in params["points"]]
    fig = figures.graph(params)
    fig.kind = "motion"
    return fig


def chem_reaction(p: dict) -> figures.Figure:
    """A chemical equation, drawn by the existing ``reaction`` figure (molecules, atom-count table, verdict).

    The equation is read by ``reaction_math`` first, so a made-up element or an unreadable equation raises
    ``reaction_math.ReactionError`` (a ``ValueError``) instead of drawing. ``fig.kind`` stays ``"reaction"``, so the
    voice-led hints and the coefficient-change animation (which key on the figure, not the spec kind) keep working.
    """
    m = reaction_math.solve(p)
    return figures.reaction({**p, "equation": m.equation})
