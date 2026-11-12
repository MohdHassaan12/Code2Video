"""A registered inventory of figures the model may ask for; code draws AND animates them.

The first real build showed frames that were mostly empty, because the writer's
free-text ``visual`` was never rendered; the first user review said the videos had
"very minimal dynamics". Both have the same answer: a CLOSED inventory of parametric
figures, chosen by the model with numbers, drawn deterministically with code-owned
geometry — and built so that they MOVE with the explanation:

* a figure is constructed in front of the viewer (strokes drawn, fills grown, labels
  arriving), not faded in whole — ``construct_animation``;
* every figure names its parts (``fig.parts``), so a step that is "about side c" can
  make that side pulse and send its label travelling into the formula
  (``runtime.GuidedChapter``);
* two figures of the same kind morph into each other, so "the unknown side turns
  into 5 m" is seen happening.

Colours carry meaning (teaching palette): what is GIVEN, what is UNKNOWN, what is a
RESULT, what is WRONG — and colour is never the only signal (labels say it).
Geometry comes from ``figure_math``: the drawing follows the labelled numbers.
"""
from __future__ import annotations

import json
import math
import re
import textwrap
from pathlib import Path

import numpy as np
from manim import (DOWN, LEFT, RIGHT, UP, UR, ORIGIN, Animation, AnimationGroup, AnnularSector, Arc, Arrow, Axes, Circle, Create, Dot,
                   DashedLine, DashedVMobject, DrawBorderThenFill, Elbow, FadeIn, Group, GrowArrow, GrowFromCenter, GrowFromPoint, ImageMobject, LaggedStart, Line, MathTex,
                   MarkupText, Mobject, NumberLine, Polygon, Rectangle, RoundedRectangle, Square, Succession, Text, VGroup, VMobject, WHITE,
                   smooth)

from .. import kits
from . import figure_math

INK = "#F2F3F5"
MUTED = "#A8B0BD"
GIVEN = "#80B1E7"     # blue — known quantities (7.4:1 on the background)
UNKNOWN = "#D19461"   # amber — what we are looking for (6.4:1)
RESULT = "#56FAAA"    # green — what we found (12.3:1)
WRONG = "#E57A9E"     # rose — a mistake being shown (6.0:1)
FONT = "Lato"
KINDS = ("right_triangle", "number_line", "bars", "circle", "rectangle", "graph", "reaction", "scene", "diagram", "picture",
         "shape", "float")
ROLES = {"given": GIVEN, "unknown": UNKNOWN, "result": RESULT, "wrong": WRONG}
_LATEX = re.compile(r"\\[A-Za-z]+|\^|_\{|\$")
_GREEK = {"theta": r"\theta", "θ": r"\theta", "alpha": r"\alpha", "α": r"\alpha", "beta": r"\beta", "β": r"\beta",
          "phi": r"\phi", "φ": r"\phi", "pi": r"\pi", "π": r"\pi"}


class Figure(VGroup):
    """A drawn figure with named parts and a construction order.

    ``parts``: name → mobject a step can focus on (``"c"``, ``"c_label"``, ``"bar0"`` …).
    ``build``: ``[("draw" | "grow" | "fade", [mobjects])]`` in the order they are constructed.
    """

    def __init__(self, kind: str = "figure"):
        super().__init__()
        self.kind, self.parts, self.build = kind, {}, []

    def stage(self, how: str, *mobs, **named):
        mobs = [m for m in list(mobs) + list(named.values()) if m is not None]
        if mobs:
            self.build.append((how, mobs))
            self.add(*mobs)
        self.parts.update({k: v for k, v in named.items() if v is not None})
        return self


def construct_animation(fig, run_time: float = 1.2):
    """Draw the figure the way a teacher would: outline, fills, then labels."""
    stages = []
    for how, mobs in getattr(fig, "build", None) or [("fade", list(fig.submobjects))]:
        if how == "draw":
            stages.append(LaggedStart(*[Create(m) for m in mobs], lag_ratio=0.55))
        elif how == "grow":
            stages.append(LaggedStart(*[GrowArrow(m) if isinstance(m, Arrow) else GrowFromCenter(m) for m in mobs],
                                      lag_ratio=0.25))
        else:
            stages.append(LaggedStart(*[FadeIn(m, shift=UP * 0.12) for m in mobs], lag_ratio=0.2))
    if not stages:
        return FadeIn(fig, run_time=run_time)
    return Succession(*stages, run_time=run_time)


def _label(text, colour: str = INK, size: int = 26):
    """A label as the model wrote it: LaTeX is typeset, plain words use the lesson font."""
    text = str(text)
    latex = _GREEK.get(text.strip().lower()) or (text if _LATEX.search(text) else None)
    if latex:
        try:
            return MathTex(latex.replace("$", ""), font_size=size * 1.25, color=colour)
        except Exception:  # noqa: BLE001 - LaTeX the model got wrong: show its words, not its markup
            text = figure_math.plain(text)
    return Text(text, font=FONT, font_size=size, color=colour)


def _num(value, default=0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _beside(label, segment_mid, outward, buff: float = 0.16):
    """Put ``label`` just outside a side: clear of the line whatever the label's length."""
    outward = outward / max(np.linalg.norm(outward), 1e-6)
    reach = abs(outward[0]) * label.width / 2 + abs(outward[1]) * label.height / 2
    return label.move_to(segment_mid + outward * (reach + buff))


def right_triangle(p: dict) -> Figure:
    """Legs ``a`` (horizontal) and ``b`` (vertical), hypotenuse ``c``; right angle at the origin corner.

    Any two of ``a``, ``b``, ``c`` fix the triangle; when the ``labels`` carry numbers
    the drawing follows THEM. ``unknown`` / ``result``: the side sought / found.
    ``angle``: "a" marks the angle between leg a and the hypotenuse, "b" the other acute
    angle (``angle_label``, default θ). ``squares``: the three squares on the sides.
    Parts: a, b, c (+ ``_label``), angle, right_angle, square_a/b/c.
    """
    sides_drawn = figure_math.resolve_right_triangle(p)
    a, b = max(0.3, sides_drawn["a"]), max(0.3, sides_drawn["b"])
    scale = min(3.2 / max(a, b), 1.2) if not p.get("squares") else min(2.0 / max(a, b), 0.8)
    A, B = a * scale, b * scale
    O, X, Y = ORIGIN, RIGHT * A, UP * B
    unknown, result = str(p.get("unknown", "")).lower(), str(p.get("result", "")).lower()
    colours = {s: (RESULT if s == result else UNKNOWN if s == unknown else GIVEN) for s in ("a", "b", "c")}
    fig = Figure("right_triangle")
    tri = Polygon(O, X, Y, color=INK, stroke_width=0, fill_color=INK, fill_opacity=0.05)
    side = {"a": Line(O, X, color=colours["a"], stroke_width=5), "b": Line(O, Y, color=colours["b"], stroke_width=5),
            "c": Line(Y, X, color=colours["c"], stroke_width=5)}
    corner = Elbow(width=0.25, angle=0, color=MUTED, stroke_width=2)
    labels = dict(p.get("labels") or {})
    angle_at, angle_label = str(p.get("angle") or "").lower(), p.get("angle_label")
    for key in ("a", "b"):          # a side "labelled" θ was a request to mark the angle at its far end
        if figure_math.is_angle_label(labels.get(key)):
            angle_at, angle_label = angle_at or key, angle_label or labels[key]
            labels[key] = ""
    defaults = {"a": f"{sides_drawn['a']:.3g}", "b": f"{sides_drawn['b']:.3g}", "c": "?"}
    mids = {"a": (O + X) / 2, "b": (O + Y) / 2, "c": (X + Y) / 2}
    normals = {"a": DOWN, "b": LEFT, "c": np.array([B, A, 0.0]) / math.hypot(A, B)}
    made = {}
    for key in ("a", "b", "c"):
        if key in labels and not str(labels[key]).strip():
            continue
        lab = _label(labels.get(key, defaults[key]), colours[key])
        if lab.width > 3.0:
            lab.scale_to_fit_width(3.0)
        made[key] = _beside(lab, mids[key], normals[key])
    squares = {}
    if p.get("squares"):
        def outward_square(P, Q, away, colour):
            d = Q - P
            n = np.array([-d[1], d[0], 0.0])
            if np.dot(n, away - P) > 0:
                n = -n
            n = n / np.linalg.norm(n) * np.linalg.norm(d)
            return Polygon(P, Q, Q + n, P + n, color=colour, stroke_width=2, fill_opacity=0.14)

        said = {k: (None if figure_math.is_angle_label(labels.get(k)) else figure_math.number_in(labels.get(k)))
                for k in ("a", "b", "c")}
        for name, (P, Q, away) in {"a": (O, X, Y), "b": (O, Y, X), "c": (X, Y, O)}.items():
            sq = outward_square(P, Q, away, colours[name])
            custom = labels.get(f"{name}2")
            if custom:
                mark = _label(custom, colours[name], 26)
            elif name == unknown and name != result:
                mark = _label("?", colours[name], 30)
            else:
                value = said[name] if said[name] else sides_drawn[name]
                mark = MathTex(rf"{value:.3g}^2 = {value * value:.4g}", font_size=34, color=colours[name])
            room = 0.78 * float(np.linalg.norm(sq.get_vertices()[1] - sq.get_vertices()[0]))
            if mark.width > room:
                mark.scale_to_fit_width(room)
            squares[name] = VGroup(sq, mark.move_to(sq.get_center()))
        made = {}                    # the squares carry the numbers; three side labels inside a small triangle collide
    fig.stage("draw", tri, a=side["a"], b=side["b"])
    fig.stage("draw", c=side["c"], right_angle=corner)
    ghost = p.get("ghost") if isinstance(p.get("ghost"), dict) else None
    if ghost and not squares:
        # the triangle this one was scaled from, at its true relative size in the same corner (writer.scaled_copies)
        ga, gb = figure_math.number_in(ghost.get("a")), figure_math.number_in(ghost.get("b"))
        if ga and gb and ga * scale < A * .98 and gb * scale < B * .98:
            small = Polygon(O, RIGHT * ga * scale, UP * gb * scale)
            shade = small.copy().set_stroke(width=0).set_fill(MUTED, opacity=.22)
            outline = DashedVMobject(small, num_dashes=44).set_stroke(INK, width=3, opacity=.85)
            fig.stage("draw", ghost=VGroup(shade, outline))
    if squares:
        fig.stage("grow", **{f"square_{k}": v for k, v in squares.items()})
    if angle_at in ("a", "b"):
        vertex = X if angle_at == "a" else Y
        if angle_at == "a":
            start, sweep = math.atan2(B, -A), math.pi - math.atan2(B, -A)
        else:
            start, sweep = -math.pi / 2, math.atan2(-B, A) + math.pi / 2
        radius = min(0.55, 0.3 * min(A, B) + 0.15)
        arc = Arc(radius=radius, start_angle=start, angle=sweep, arc_center=vertex, color=UNKNOWN, stroke_width=3)
        bisector = start + sweep / 2
        mark = _label(angle_label or "θ", UNKNOWN, 28)
        mark.move_to(vertex + (radius + 0.28) * np.array([math.cos(bisector), math.sin(bisector), 0.0]))
        fig.stage("draw", angle=VGroup(arc, mark))
    fig.stage("fade", **{f"{k}_label": v for k, v in made.items()})
    return fig


def tick_step(lo: float, hi: float) -> tuple[float, int]:
    """A tick spacing of 1, 2 or 5 times a power of ten giving five to ten ticks, and the decimals it needs.

    The step was ``max(1, round(span / 10))``: a line from 0.9 to 1 (the lesson on 0.999…, 2026-10-19) had ONE tick,
    numbered "1" at 0.9, under labels saying 0.9, 0.99 and 0.999.
    """
    span = max(hi - lo, 1e-9)
    power = 10 ** math.floor(math.log10(span / 10))
    for m in (1, 2, 5, 10, 20):
        step = m * power
        places = max(0, -int(math.floor(math.log10(step) + 1e-9)))
        if span / step <= (12 if places == 0 else 5):     # numbers with decimals are wider: fewer of them
            return step, places
    return step, places


def _unstack(labels: list) -> None:
    """Labels of points that sit too close to share a row are lifted to the lowest row above that is free."""
    rows: list[list] = []
    for label in sorted(labels, key=lambda m: m.get_center()[0]):
        base = label.get_center()[1]
        for k in range(len(rows) + 1):
            if k == len(rows):
                rows.append([])
            if all(label.get_left()[0] > other.get_right()[0] + 0.12 or label.get_right()[0] < other.get_left()[0] - 0.12
                   for other in rows[k]):
                label.set_y(base + k * (label.height + 0.16))
                rows[k].append(label)
                break


def number_line(p: dict) -> Figure:
    """``min``/``max``, ``points`` [{"x", "label", "role"}], optional ``arrow`` {from, to, label, role}.

    Parts: line, point0…, point0_label…, arrow.
    """
    lo, hi = _num(p.get("min"), -5), _num(p.get("max"), 5)
    if hi <= lo:
        lo, hi = -5, 5
    step, places = tick_step(lo, hi)
    # Ticks on the step's multiples: round(110 / 10) once put ticks at 0, 11, 22 … 99, and "A 100 m" stood over the
    # 99 (speed and velocity, 2026-10-20).
    lo = round(math.floor(lo / step + 1e-9) * step, places)
    hi = round(math.ceil(hi / step - 1e-9) * step, places)
    line = NumberLine(x_range=[lo, hi, step], length=5.6, include_numbers=True, color=MUTED, font_size=20,
                      decimal_number_config={"color": MUTED, "num_decimal_places": places}, label_direction=DOWN)
    fig = Figure("number_line").stage("draw", line=line)
    dots, tags = {}, {}
    for i, pt in enumerate(p.get("points") if isinstance(p.get("points"), list) else []):
        if not isinstance(pt, dict):
            continue
        x = min(hi, max(lo, _num(pt.get("x"))))
        colour = ROLES.get(str(pt.get("role", "given")), GIVEN)
        dot = Dot(line.n2p(x), color=colour, radius=0.1)
        dots[f"point{i}"] = dot
        tags[f"point{i}_label"] = _label(pt.get("label", f"{x:g}"), colour, 24).next_to(dot, UP, buff=0.18)
    _unstack(list(tags.values()))
    fig.stage("grow", **dots)
    fig.stage("fade", **tags)
    arrow = p.get("arrow")
    if isinstance(arrow, dict):
        x0, x1 = _num(arrow.get("from")), _num(arrow.get("to"))
        colour = ROLES.get(str(arrow.get("role", "unknown")), UNKNOWN)
        shaft = Arrow(line.n2p(x0) + DOWN * 0.85, line.n2p(x1) + DOWN * 0.85, color=colour, buff=0, stroke_width=4)
        fig.stage("grow", arrow=shaft)
        if arrow.get("label"):
            fig.stage("fade", arrow_label=_label(arrow["label"], colour, 22).next_to(
                line.n2p((x0 + x1) / 2) + DOWN * 0.85, DOWN, buff=0.15))
    return fig


def bars(p: dict) -> Figure:
    """Fraction/part bars: ``parts`` [{"label", "n", "d", "role"}] — each bar is ``n`` of ``d`` filled.

    Parts: bar0…, bar0_label… (the cells of a bar fill one after another).
    """
    fig = Figure("bars")
    rows, frames, fills, tags = [], {}, {}, {}
    for i, part in enumerate((p.get("parts") if isinstance(p.get("parts"), list) else [])[:4]):
        if not isinstance(part, dict):
            continue
        n, d = max(0, int(_num(part.get("n"), 1))), max(1, int(_num(part.get("d"), 2)))
        colour = ROLES.get(str(part.get("role", "given")), GIVEN)
        width, height = 5.0, 0.62
        cells = VGroup(*[Rectangle(width=width / d, height=height, color=MUTED, stroke_width=2) for _ in range(d)])
        cells.arrange(RIGHT, buff=0)
        filled = VGroup(*[Rectangle(width=width / d, height=height, stroke_width=0, fill_color=colour,
                                    fill_opacity=0.6) for _ in range(min(n, d))])
        label = _label(part.get("label", f"{n}/{d}"), colour, 26)
        rows.append((label, cells, filled))
        frames[f"frame{i}"], fills[f"bar{i}"], tags[f"bar{i}_label"] = cells, filled, label
    if rows:
        VGroup(*[r[1] for r in rows]).arrange(DOWN, buff=0.4, aligned_edge=LEFT)
        for label, cells, filled in rows:
            label.next_to(cells, LEFT, buff=0.25)
            for k, cell in enumerate(filled):
                cell.move_to(cells[k])
    fig.stage("draw", **frames)
    for name, filled in fills.items():           # each bar fills cell by cell
        if len(filled):
            fig.build.append(("fade", list(filled)))
            fig.add(filled)
        fig.parts[name] = VGroup(filled, frames["frame" + name[3:]])
    fig.stage("fade", **tags)
    return fig


def circle(p: dict) -> Figure:
    """A circle of radius ``r`` with labelled radius / diameter / circumference; or cut into ``sectors``.

    ``sectors`` n > 0 cuts the disc into n equal sectors in two alternating colours;
    ``rearranged`` lays them side by side, alternately up and down — the picture that
    turns a circle into (nearly) a rectangle of base πr and height r.
    Parts: circumference, radius, diameter, centre, sectors (+ ``_label``).
    """
    labels = dict(p.get("labels") or {})
    unknown, result = str(p.get("unknown", "")).lower(), str(p.get("result", "")).lower()
    tone = lambda name: RESULT if name == result else UNKNOWN if name == unknown else GIVEN  # noqa: E731
    R = 1.7
    n = int(max(0, min(48, _num(p.get("sectors"), 0))))
    fig = Figure("circle")
    if n >= 4 and p.get("rearranged"):
        theta = 2 * math.pi / n
        half = R * math.sin(theta / 2)
        pieces = VGroup()
        for i in range(n):
            up = i % 2 == 0
            piece = AnnularSector(inner_radius=0, outer_radius=R, angle=theta,
                                  start_angle=(math.pi / 2 if up else -math.pi / 2) - theta / 2,
                                  color=GIVEN if up else RESULT, fill_opacity=0.55, stroke_width=1, stroke_color=INK)
            piece.shift(RIGHT * (i * half) + (ORIGIN if up else UP * R * math.cos(theta / 2)))
            pieces.add(piece)
        pieces.move_to(ORIGIN)
        if pieces.width > 5.6:
            pieces.scale_to_fit_width(5.6)
        fig.stage("grow", sectors=pieces)
        base = labels.get("base") or labels.get("length")
        height = labels.get("height") or labels.get("radius")
        if base:
            fig.stage("fade", base_label=_label(base, tone("base"), 26).next_to(pieces, DOWN, buff=0.2))
        if height:
            fig.stage("fade", height_label=_label(height, tone("radius"), 26).next_to(pieces, LEFT, buff=0.2))
        return fig
    rim = Circle(radius=R, color=tone("circumference"), stroke_width=5)
    centre = Dot(ORIGIN, color=INK, radius=0.06)
    if n >= 2:
        theta = 2 * math.pi / n
        pieces = VGroup(*[AnnularSector(inner_radius=0, outer_radius=R, angle=theta, start_angle=i * theta,
                                        color=GIVEN if i % 2 == 0 else RESULT, fill_opacity=0.5, stroke_width=1,
                                        stroke_color=INK) for i in range(n)])
        fig.stage("grow", sectors=pieces)
    fig.stage("draw", circumference=rim, centre=centre)
    radius = Line(ORIGIN, RIGHT * R, color=tone("radius"), stroke_width=5)
    fig.stage("draw", radius=radius)
    tags = {}
    radius_text = labels.get("radius", f"r = {_num(p.get('r'), 1):g}")
    if str(radius_text).strip():
        tags["radius_label"] = _label(radius_text, tone("radius"), 26).next_to(radius, UP, buff=0.12)
    if str(labels.get("diameter", "")).strip():
        tilt = math.pi / 3
        along = np.array([math.cos(tilt), math.sin(tilt), 0.0])
        across = np.array([-math.sin(tilt), math.cos(tilt), 0.0])
        diameter = Line(-along * R, along * R, color=tone("diameter"), stroke_width=4)
        fig.stage("draw", diameter=diameter)
        tags["diameter_label"] = _label(labels["diameter"], tone("diameter"), 24).move_to(-along * R * 0.5 + across * 0.35)
    if str(labels.get("circumference", "")).strip():
        tags["circumference_label"] = _label(labels["circumference"], tone("circumference"), 24).next_to(rim, UP, buff=0.15)
    if str(labels.get("area", "")).strip() or unknown == "area":
        tags["area_label"] = _label(labels.get("area") or "Area = ?", tone("area"), 26).next_to(rim, DOWN, buff=0.2)
    fig.stage("fade", **tags)
    return fig


def rectangle(p: dict) -> Figure:
    """A ``w`` × ``h`` rectangle with labelled sides; ``grid`` draws the unit squares (area by counting).

    Parts: length (bottom side), width (left side), area, grid (+ ``_label``).
    """
    w, h = max(0.2, _num(p.get("w"), 6)), max(0.2, _num(p.get("h"), 4))
    labels = dict(p.get("labels") or {})
    unknown, result = str(p.get("unknown", "")).lower(), str(p.get("result", "")).lower()
    tone = lambda name: RESULT if name == result else UNKNOWN if name == unknown else GIVEN  # noqa: E731
    scale = min(4.6 / w, 3.0 / h)
    W, H = w * scale, h * scale
    fig = Figure("rectangle")
    body = Rectangle(width=W, height=H, color=INK, stroke_width=2, fill_color=tone("area"), fill_opacity=0.12)
    corner = body.get_corner(DOWN + LEFT)
    length = Line(corner, corner + RIGHT * W, color=tone("w"), stroke_width=5)
    width = Line(corner, corner + UP * H, color=tone("h"), stroke_width=5)
    fig.stage("draw", length=length, width=width)
    fig.stage("draw", area=body)
    if p.get("grid") and w <= 14 and h <= 10 and float(w).is_integer() and float(h).is_integer():
        lines = VGroup(*[Line(corner + RIGHT * scale * i, corner + RIGHT * scale * i + UP * H, color=MUTED, stroke_width=1)
                         for i in range(1, int(w))],
                       *[Line(corner + UP * scale * j, corner + UP * scale * j + RIGHT * W, color=MUTED, stroke_width=1)
                         for j in range(1, int(h))])
        if len(lines):
            fig.stage("draw", grid=lines)
            # The unit squares themselves, unseen until the area is found: the renderer fills them one row
            # after another when a step's working ends on the area ("4 x 4 = 16"), so the count is watched.
            fig.cells = VGroup(*[Rectangle(width=scale, height=scale, stroke_width=0, fill_color=RESULT, fill_opacity=0)
                                 .move_to(corner + RIGHT * scale * (i + .5) + UP * scale * (int(h) - j - .5))
                                 for j in range(int(h)) for i in range(int(w))])
            fig.add(fig.cells)
    tags = {}
    if str(labels.get("w", f"{w:g}")).strip():
        tags["length_label"] = _label(labels.get("w", f"{w:g}"), tone("w"), 26).next_to(length, DOWN, buff=0.16)
    if str(labels.get("h", f"{h:g}")).strip():
        tags["width_label"] = _label(labels.get("h", f"{h:g}"), tone("h"), 26).next_to(width, LEFT, buff=0.16)
    if str(labels.get("area", "")).strip() or unknown == "area":
        mark = _label(labels.get("area") or "?", tone("area"), 30)
        if mark.width > W * 0.8:
            mark.scale_to_fit_width(W * 0.8)
        mark.move_to(body.get_center())
        if p.get("grid"):
            # On a grid the label sits on the lines: "16 cells" was crossed by them and counted
            # as text-over-shape. A backing plate keeps it legible (and the probe exempts it).
            mark.add_background_rectangle(color="#1C1F26", opacity=0.85, buff=0.1)
        tags["area_label"] = mark
    fig.stage("fade", **tags)
    return fig


GRAPH_COLOURS = (GIVEN, UNKNOWN, "#C9A0F0")


def graph(p: dict) -> Figure:
    """Axes and up to three curves y = f(x): ``functions`` (text, read by ``figure_math.graph_function``), ``x_range``,
    optional ``y_range``, ``labels`` {curve0: "y = 2x - 1"}, ``points`` [{"x", "y"?, "label", "role", "open"}],
    ``x_label``/``y_label``, ``meet`` (false: where the curves meet is not marked yet). Asymptotes, holes and where two curves meet are COMPUTED (``figure_math.graph_facts``):
    a dashed line, an open circle, a green dot with its coordinates.

    Parts: axes, curve0…, curve0_label…, asym0…, hole0…, point0…, point0_label…, meet0…, meet0_label….
    """
    functions = [str(f) for f in (p.get("functions") or [])[:3]]
    facts = figure_math.graph_facts(functions, p.get("x_range") or (-5, 5), p.get("y_range"))
    fs = [figure_math.graph_function(f) for f in facts["functions"]]
    if not fs:
        raise ValueError("no function that can be drawn")
    (a, b), (lo, hi) = facts["x_range"], facts["y_range"]

    def tick(span: float) -> float:
        for s in (0.5, 1, 2, 5, 10, 20, 50, 100, 200, 500, 1000):
            if span / s <= 8:
                return s
        return span / 8
    # A step under 1 needs a decimal place, or the axis reads "0 1 1 2 2" (seen on a V-I graph, 2026-10-16).
    xs, ys = tick(b - a), tick(hi - lo)
    axes = Axes(x_range=[a, b, xs], y_range=[lo, hi, ys], x_length=6.2, y_length=4.2, tips=False,
                axis_config={"color": MUTED, "stroke_width": 2, "include_numbers": True, "font_size": 20},
                x_axis_config={"decimal_number_config": {"color": MUTED, "num_decimal_places": 0 if xs >= 1 else 1}},
                y_axis_config={"decimal_number_config": {"color": MUTED, "num_decimal_places": 0 if ys >= 1 else 1}})
    fig = Figure("graph").stage("draw", axes=axes)
    names = {}
    if p.get("x_label"):
        names["x_label"] = _label(p["x_label"], MUTED, 22).next_to(axes.x_axis.get_end(), RIGHT, buff=0.15)
    if p.get("y_label"):
        names["y_label"] = _label(p["y_label"], MUTED, 22).next_to(axes.y_axis.get_end(), UP, buff=0.12)
    fig.stage("fade", **names)
    labels = dict(p.get("labels") or {})
    breaks = sorted(set(facts["asymptotes"]) | {h["x"] for h in facts["holes"]})
    margin = (hi - lo) * 0.04
    curves = []                                            # (n, colour, pieces of scene points)
    for n, f in enumerate(fs):
        xs = np.linspace(a, b, 900)
        ys = f(xs)
        inside = np.isfinite(ys) & (ys >= lo - margin) & (ys <= hi + margin)
        for x in breaks:                                   # never join across an asymptote or a hole
            inside &= np.abs(xs - x) > (b - a) / 900 * 1.5
        pieces, run = [], []
        for x, y, ok in zip(xs, ys, inside):
            if ok:
                run.append(axes.c2p(x, min(hi, max(lo, y))))
            elif run:
                pieces.append(run)
                run = []
        if run:
            pieces.append(run)
        pieces = [piece for piece in pieces if len(piece) >= 2]
        if pieces:
            curves.append((n, GRAPH_COLOURS[n % len(GRAPH_COLOURS)], pieces))
    # Each curve is named where the name is clear of the axes and their numbers, every curve, every asymptote, the other
    # names and the frame: places along its longest piece are tried in turn. One fixed place put the name of y = -x + 5 on
    # the y axis, and then on the other line (layout findings, 2026-10-16).
    box = axes.get_left()[0], axes.get_right()[0], axes.get_bottom()[1], axes.get_top()[1]
    origin = axes.c2p(0 if a <= 0 <= b else a, 0 if lo <= 0 <= hi else lo)
    drawn = np.array([pt for _, _, pieces in curves for piece in pieces for pt in piece[::3]])
    walls = [axes.c2p(x, 0)[0] for x in facts["asymptotes"]]
    placed = []
    meets = facts["meeting_points"][:3] if p.get("meet", True) is not False else []   # writer.graph_reveals: not yet said
    for m in meets + [q for q in (p.get("points") or []) if isinstance(q, dict) and q.get("x") is not None][:4]:
        try:                                               # a marked point and the label beside it (up and right) stay clear
            c = axes.c2p(float(m["x"]), float(m.get("y") if m.get("y") is not None else fs[0](np.array([float(m["x"])]))[0]))
        except (TypeError, ValueError):
            continue
        if np.all(np.isfinite(c)):
            placed.append((c + np.array([-0.2, -0.2, 0]), c + np.array([1.4, 0.55, 0])))

    def clear(m) -> bool:
        (x0, y0, _), (x1, y1, _) = m.get_corner(DOWN + LEFT), m.get_corner(UP + RIGHT)
        if x0 < box[0] or x1 > box[1] or y0 < box[2] or y1 > box[3]:
            return False
        if x0 < origin[0] + 0.1 and x1 > origin[0] - 0.6 or y0 < origin[1] + 0.1 and y1 > origin[1] - 0.42:   # an axis, its numbers
            return False
        if any(x0 - 0.08 < w < x1 + 0.08 for w in walls):
            return False
        if len(drawn) and np.any((drawn[:, 0] > x0 - 0.06) & (drawn[:, 0] < x1 + 0.06) & (drawn[:, 1] > y0 - 0.06) & (drawn[:, 1] < y1 + 0.06)):
            return False
        return all(x1 < o[0][0] or x0 > o[1][0] or y1 < o[0][1] or y0 > o[1][1] for o in placed)
    reserved = len(placed)
    for n, colour, pieces in curves:
        fig.stage("draw", **{f"curve{n}": VGroup(*[VMobject(color=colour, stroke_width=4).set_points_smoothly(piece) for piece in pieces])})
        for piece_mob in fig.parts[f"curve{n}"]:
            piece_mob.grows_in = True              # a curve held back for its step (runtime._hold_back_steps) is drawn along, not faded
        text = labels.get(f"curve{n}") or ("y = " + figure_math.plain(facts["functions"][n]).replace("**", "^").replace("*", ""))
        tag = _label(text, colour, 22)
        piece = max(pieces, key=len)
        found = False
        for buff in (0.15, 0.4, 0.8):                     # as close to its own curve as it can be
            for share in (0.82, 0.62, 0.42, 0.25, 0.92, 0.1):
                at = piece[int((len(piece) - 1) * share)]
                for side in (UP + LEFT * 0.4, DOWN + RIGHT * 0.4, UP + RIGHT * 0.4, DOWN + LEFT * 0.4):
                    tag.next_to(at, side, buff=buff)
                    if clear(tag):
                        found = True
                        break
                if found:
                    break
            if found:
                break
        if not found:                                     # in a free corner of the axes, else on a plate where it is
            for corner in (UP + RIGHT, UP + LEFT, DOWN + RIGHT, DOWN + LEFT):
                tag.move_to(axes.get_corner(corner) - corner * np.array([tag.width / 2 + 0.1, tag.height / 2 + 0.1, 0]))
                if clear(tag):
                    found = True
                    break
        if not found:
            tag.next_to(piece[int((len(piece) - 1) * 0.82)], UP + LEFT * 0.4, buff=0.2)
            tag.add_background_rectangle(color="#14161B", opacity=0.85, buff=0.05)
        placed.append((tag.get_corner(DOWN + LEFT), tag.get_corner(UP + RIGHT)))
        fig.stage("fade", **{f"curve{n}_label": tag})
    for x in facts["asymptotes"]:                         # an axis number under a dashed asymptote would be struck through
        for number in list(getattr(axes.x_axis, "numbers", [])):
            if abs(float(number.get_value()) - x) < 1e-6:
                axes.x_axis.numbers.remove(number)
    for i, x in enumerate(facts["asymptotes"][:3]):
        fig.stage("draw", **{f"asym{i}": DashedLine(axes.c2p(x, lo), axes.c2p(x, hi), color=MUTED, stroke_width=2, dash_length=0.12)})
    for i, hole in enumerate(facts["holes"][:3]):
        if lo <= hole["y"] <= hi:
            ring = Circle(radius=0.085, color=GRAPH_COLOURS[hole["curve"] % 3], stroke_width=3, fill_color="#14161B", fill_opacity=1)
            fig.stage("grow", **{f"hole{i}": ring.move_to(axes.c2p(hole["x"], hole["y"]))})
    dots, tags = {}, {}
    for i, pt in enumerate([q for q in (p.get("points") or []) if isinstance(q, dict)][:4]):
        x = _num(pt.get("x"), float("nan"))
        if not (np.isfinite(x) and a <= x <= b):
            continue
        y = pt.get("y")
        y = _num(y) if y is not None else float(fs[0](np.array([x]))[0])     # a point on the first curve unless told
        if not (np.isfinite(y) and lo <= y <= hi):
            continue
        if pt.get("hold"):
            continue                       # ``kit_figures.motion``: a quiz asks about this point; it is drawn on the next beat
        colour = ROLES.get(str(pt.get("role", "given")), GIVEN)
        dot = (Circle(radius=0.09, color=colour, stroke_width=3, fill_color="#14161B", fill_opacity=1) if pt.get("open")
               else Dot(radius=0.09, color=colour)).move_to(axes.c2p(x, y))
        dots[f"point{i}"] = dot
        tags[f"point{i}_label"] = _label(pt.get("label") or f"({figure_math._nice(x):g}, {figure_math._nice(y):g})",
                                         colour, 22)
    for i, m in enumerate(meets):
        dot = Dot(radius=0.1, color=RESULT).move_to(axes.c2p(m["x"], m["y"]))
        dots[f"meet{i}"] = dot
        tags[f"meet{i}_label"] = _label(f"({m['x']:g}, {m['y']:g})", RESULT, 22)
    # Each point's name goes on the first side of its dot that is clear of the other names, the dots, the curves and the
    # curve names. Always up and right put "Toaster (Low R)" across "Water Heater (High R)" when two points sat at the
    # same height (an Ohm's law graph, 2026-10-16); a name with no clear side is put up and right on a plate.
    taken = [(d.get_corner(DOWN + LEFT), d.get_corner(UP + RIGHT)) for d in dots.values()] + placed[reserved:]
    taken += [(np.array([box[0], origin[1] - 0.42, 0]), np.array([box[1], origin[1] + 0.1, 0])),   # an axis, its numbers
              (np.array([origin[0] - 0.6, box[2], 0]), np.array([origin[0] + 0.1, box[3], 0]))]
    for name, tag in tags.items():
        dot = dots[name[:-len("_label")]]
        best = None
        for side in (UP + RIGHT, UP + LEFT, DOWN + RIGHT, DOWN + LEFT, RIGHT, LEFT, UP, DOWN):
            tag.next_to(dot, side, buff=0.08)
            (x0, y0, _), (x1, y1, _) = tag.get_corner(DOWN + LEFT), tag.get_corner(UP + RIGHT)
            cost = 0                                   # another name or a dot under it is worst, then the frame, then curves
            if x0 < box[0] - 0.5 or x1 > box[1] + 0.5 or y0 < box[2] or y1 > box[3] + 0.3:
                cost += 50
            cost += 100 * sum(not (x1 + 0.04 < a[0] or x0 - 0.04 > b[0] or y1 + 0.04 < a[1] or y0 - 0.04 > b[1]) for a, b in taken)
            if len(drawn):
                cost += int(np.sum((drawn[:, 0] > x0 - 0.04) & (drawn[:, 0] < x1 + 0.04) & (drawn[:, 1] > y0 - 0.04) & (drawn[:, 1] < y1 + 0.04)))
            if best is None or cost < best[0]:
                best = (cost, side)
            if cost == 0:
                break
        tag.next_to(dot, best[1], buff=0.08)
        plated = best[0] > 0                           # a curve still runs under it: on a plate, as a curve's name is
        if plated:
            tag.add_background_rectangle(color="#14161B", opacity=0.85, buff=0.04)
        if name.startswith("meet") and not plated:     # a meeting point's coordinates sit where two curves cross
            tag.add_background_rectangle(color="#14161B", opacity=0.8, buff=0.04)
        taken.append((tag.get_corner(DOWN + LEFT), tag.get_corner(UP + RIGHT)))
    fig.stage("grow", **dots)
    fig.stage("fade", **tags)
    fig.facts = facts
    return fig


SCENE_BOX = (6.0, 4.0)      # the box engine.sim_gen verifies a generated scene in


def _open_arcs(group) -> list:
    """The arcs in a scene that are curves, not closed shapes (a dent, a bend, an angle mark)."""
    return [m for m in group.get_family() if isinstance(m, Arc) and not isinstance(m, (Circle, AnnularSector))
            and type(m).__name__ not in ("Sector", "Annulus", "Dot") and abs(getattr(m, "angle", 0.0)) < 2 * math.pi - 1e-3]


def arcs_stay_open(animate):
    """``animate`` with every open arc's fill kept at nothing, frame after frame.

    A model fades a part in with ``set_opacity(a)``, which sets the fill too: the sand's dents, drawn as arcs,
    came out as solid bowls in a filmed pressure lesson (2026-10-18), and the model kept doing it when told why.
    An open arc filled is never what was meant, so code holds it; ``engine.sim_gen``'s checker does the same,
    so what it verified is what the lesson shows.
    """
    if animate is None:
        return None

    def wrapped(group, run_time):
        anim = animate(group, run_time)
        arcs = _open_arcs(group)
        if arcs and isinstance(anim, Animation):
            step, end = anim.interpolate, anim.finish

            def interpolate(alpha):
                step(alpha)
                for arc in arcs:
                    arc.set_fill(opacity=0)

            def finish():                       # a group's finish() steps its parts, not this interpolate
                end()
                for arc in arcs:
                    arc.set_fill(opacity=0)
            anim.interpolate, anim.finish = interpolate, finish
        return anim
    return wrapped


def scene(p: dict) -> Figure:
    """A picture the inventory cannot draw, written AND animated by a model, verified before it gets here.

    ``module`` is the path of a cached ``engine.sim_gen`` module holding exactly two
    functions — ``build(width, height) -> Mobject`` and ``animate(group, run_time) ->
    Animation`` — that already passed the sandbox (it draws something, something moves,
    nothing leaves its box, no file or network access). The module is told to import
    nothing, so the namespace is supplied here exactly as the verifier supplied it.
    ``fig.animator`` is what ``runtime.GuidedChapter`` runs for the length of a beat.
    """
    path = str(p.get("module") or "")
    namespace: dict = {}
    exec("from manim import *\nimport numpy as np\nimport math", namespace)   # noqa: S102 - vetted module, see docstring
    with open(path, encoding="utf-8") as fh:
        exec(compile(fh.read(), path, "exec"), namespace)                        # noqa: S102
    group = namespace["build"](*SCENE_BOX)
    for arc in _open_arcs(group):
        arc.set_fill(opacity=0)
    # A label a line grazes is moved by code, as the checker moved it before it passed the scene.
    from lessonforge.scene_tidy import clear_grazed_labels
    clear_grazed_labels(group, arcs_stay_open(namespace.get("animate")), box=SCENE_BOX)
    if group.width > SCENE_BOX[0] * 1.02:
        group.scale_to_fit_width(SCENE_BOX[0])
    if group.height > SCENE_BOX[1] * 1.02:
        group.scale_to_fit_height(SCENE_BOX[1])
    fig = Figure("scene").stage("fade", scene=group)
    # ``origin`` is the picture exactly where the verifier saw it (centred on the origin).
    # The lesson moves ``inner`` into its column; the animation is always run on a copy of
    # ``origin`` and mirrored across, because a module that animates with absolute
    # coordinates is correct at the origin and wrong anywhere else.
    fig.inner, fig.origin, fig.animator = group, group.copy(), arcs_stay_open(namespace.get("animate"))
    return fig


PAPER = "#FFFFFF"        # a diagram is art made for a white page: it sits on a white card
PAPER_INK = "#1D2733"    # words on that card
POINTER = "#5B6675"


class _Then(Animation):
    """Does one thing at the moment it is PLAYED, and draws nothing.

    A figure is asked what a focus does when the step is PREPARED; the renderer then waits for the
    step's words and plays what it was given. Anything the figure did at once, when asked, happened
    early: on the first lesson written on a built-up poster the beads of a process ran along an
    arrow that was not drawn yet, a step ahead of the voice (carbon dioxide's beads at 29.9 s, its
    arrow at 31 s; oxygen's six seconds early). A change of state therefore travels with the
    animations, and happens when they begin.
    """

    def __init__(self, mobject, action):
        super().__init__(mobject, run_time=0.05, suspend_mobject_updating=False)
        self._action = action

    def create_starting_mobject(self):
        return Mobject()                       # nothing of the mobject is drawn or changed: no copy of a picture is made

    def begin(self) -> None:
        self._action()
        super().begin()

    def interpolate_mobject(self, alpha: float) -> None:
        return None


class DiagramFigure(Group):
    """A labelled diagram of a real thing, shown as exact picture layers (``harness/diagrams.py``).

    The art is a picture a browser drew from the diagram's SVG; each named part is a
    cut-out of the same drawing, placed exactly over it. The parts are NOT VMobjects:
    never hand one to ``Indicate`` or ``set_color``, which paint an image flat. A step
    that names a part gets ``focus_animations(name)`` instead.

    What a focus does depends on what the drawing can do (``self.mode``), because lighting
    a part in a dimmed picture was all the first lessons did with a drawing they had gone
    to the trouble of taking apart (the owner: "a raw way of using"):

    * ``built`` — a poster with boxes of words (the water cycle). The scene stands alone
      at first; a process's arrows are drawn in when it is named and STAY, its name is
      written on a plate, and small beads run along the arrows (the SVG's own paths)
      while it is the subject. Nothing is dimmed: the picture grows as it is told.
    * ``zoomed`` — an anatomy drawing with pointer lines (the heart, the cell). The card
      cross-fades to a sharp close-up of the named place with a ring and its name, and
      a small overview in the corner shows where that is. No camera moves: the close-up
      is another picture of the same SVG, on the same card.
    * ``poster`` / ``pointers`` — a manifest from before these pieces existed: the part
      stays, the rest fades to ``DIM``, the label is written (and a name with no layer
      of its own gets a ring at the pointer's end).

    Every layer, close-up, bead and label is a submobject from the start, at zero opacity,
    so the figure's box never changes after it is laid out and one FadeOut takes all of it.
    In the first two modes the labels live ON the art, so the card is exactly the art.
    """
    DIM = 0.5          # 0.28 left the picture a pale wash for most of a lesson; at 0.5 the lit part still stands out
    PLATE = 0.9
    FLOW = 1.5         # scene units a bead travels in a second
    MINI = 0.25        # the overview's width, as a share of the card's

    def __init__(self, manifest: dict, labels: list[str] | None = None, height: float = 4.3):
        super().__init__()
        self.kind, self.parts, self.build = "diagram", {}, []
        folder = Path(manifest["folder"])
        ax0, ay0, ax1, ay1 = manifest.get("art_box") or [0, 0, manifest["width"], manifest["height"]]
        wanted = [l for l in manifest.get("labels", []) if labels is None or l["slug"] in labels]
        poster = manifest.get("style") == "boxes"
        has = lambda name: bool(name) and (folder / str(name)).is_file()  # noqa: E731
        if poster and has(manifest.get("base")):
            self.mode = "built"
        elif not poster and any(has((l.get("detail") or {}).get("png")) for l in wanted):
            self.mode = "zoomed"
        else:
            self.mode = "poster" if poster else "pointers"
        self.art = ImageMobject(str(folder / (manifest["base"] if self.mode == "built" else manifest["art"])))
        self.art.scale_to_fit_height(height)
        per_px = self.art.width / float(ax1 - ax0)          # the art is the drawing cut to what is drawn
        corner = self.art.get_corner(UP + LEFT)
        at = lambda x, y: corner + RIGHT * (x - ax0) * per_px + DOWN * (y - ay0) * per_px  # noqa: E731
        boxes = {p["id"]: p for p in manifest.get("parts", [])}
        layers, closeups, self.labels, written = {}, [], {}, []
        self.mini = self.mini_frame = None
        # Where labels may stand and what a close-up fills. For a zoomed drawing it is a window at least as wide as
        # the manifest's "frame" says (1.5 to 1), with the whole drawing centred in it: an upright heart in an
        # upright card was a quarter of the frame wide, close-ups and all.
        self.frame = self.art
        if self.mode == "zoomed":
            shape = float(manifest.get("frame") or 0) or self.art.width / self.art.height
            self.frame = Rectangle(width=max(self.art.width, self.art.height * shape), height=self.art.height, stroke_width=0,
                                   fill_opacity=0).move_to(self.art.get_center())
            self.mini = ImageMobject(str(folder / manifest["art"]))
            self.mini.scale_to_fit_height(self.MINI * self.frame.height * 1.3)
            self.mini.move_to(self.frame.get_corner(DOWN + RIGHT) + LEFT * (self.mini.width / 2 + 0.1) + UP * (self.mini.height / 2 + 0.1))
            self.mini_frame = RoundedRectangle(width=self.mini.width + 0.08, height=self.mini.height + 0.08, corner_radius=0.05,
                                               stroke_color=POINTER, stroke_width=1.5, fill_color=PAPER, fill_opacity=1)
            self.mini_frame.move_to(self.mini.get_center())
            self.mini.set_opacity(0)
            self.mini_frame.set_opacity(0)
        for label in wanted:
            entry = {"layer": None, "words": None, "line": None, "ring": None, "plate": None, "shown": False,
                     "beads": None, "close": None, "region": None}
            part = boxes.get(label.get("part") or "")
            detail = label.get("detail") or {}
            if self.mode == "zoomed":
                if not (label.get("tip") and has(detail.get("png"))):
                    continue                            # nothing to zoom to: the name is not offered a focus
                close = ImageMobject(str(folder / detail["png"]))
                close.stretch_to_fit_width(self.frame.width).stretch_to_fit_height(self.frame.height).move_to(self.frame.get_center())
                dx0, dy0, dx1, dy1 = detail["box"]
                inside = lambda x, y: (self.frame.get_corner(UP + LEFT) + RIGHT * (x - dx0) / (dx1 - dx0) * self.frame.width  # noqa: E731
                                       + DOWN * (y - dy0) / (dy1 - dy0) * self.frame.height)
                spot = inside(*label["tip"])
                ring = Circle(radius=0.3, color=UNKNOWN, stroke_width=6).move_to(spot)
                words = Text("\n".join(textwrap.wrap(label["name"], 18)) or label["name"], font=FONT, font_size=24, color=PAPER_INK,
                             line_spacing=0.7)
                # beside the ring on the side that has room for the whole name, else under or over it: never on it
                sides = (RIGHT, LEFT, DOWN, UP) if spot[0] < self.frame.get_center()[0] else (LEFT, RIGHT, DOWN, UP)
                for side in sides:
                    words.next_to(ring, side, buff=0.18)
                    if (self.frame.get_left()[0] + 0.1 <= words.get_left()[0] and words.get_right()[0] <= self.frame.get_right()[0] - 0.1
                            and self.frame.get_bottom()[1] + 0.1 <= words.get_bottom()[1] and words.get_top()[1] <= self.frame.get_top()[1] - 0.1):
                        break
                else:
                    self._keep_inside(words)
                plate = self._plate(words)
                mini_at = lambda x, y: (self.mini.get_corner(UP + LEFT) + RIGHT * (x - ax0) / (ax1 - ax0) * self.mini.width  # noqa: E731
                                        + DOWN * (y - ay0) / (ay1 - ay0) * self.mini.height)
                a, b = mini_at(dx0, dy0), mini_at(dx1, dy1)
                region = Rectangle(width=abs(b[0] - a[0]), height=abs(b[1] - a[1]), stroke_color=UNKNOWN, stroke_width=3)
                region.move_to((a + b) / 2)
                entry.update(close=close.set_opacity(0), ring=ring, words=words, plate=plate, region=region)
                closeups.append(close)
                for mob in (plate, words, ring, region):
                    mob.set_opacity(0)
                    written.append(mob)
                ring.set_fill(opacity=0)
            else:
                if part and part["id"] not in layers:
                    x0, y0, x1, y1 = part["box"]
                    layer = ImageMobject(str(folder / part["png"]))
                    layer.scale_to_fit_height(max((y1 - y0) * per_px, 1e-3)).move_to(at((x0 + x1) / 2, (y0 + y1) / 2))
                    layers[part["id"]] = layer.set_opacity(0)
                start = at(*label["from"])
                tip = at(*label["tip"]) if label.get("tip") else None
                words = Text("\n".join(textwrap.wrap(label["name"], 17)) or label["name"], font=FONT, font_size=19, color=PAPER_INK,
                             line_spacing=0.7)
                left_of_tip = tip is not None and start[0] <= tip[0]
                words.next_to(start, LEFT if left_of_tip or tip is None else RIGHT, buff=0.07)
                plate = None
                if poster:
                    # inside the art, whichever side it was put on, and readable over whatever is drawn there
                    self._keep_inside(words)
                    plate = self._plate(words)
                line = Line(start, tip, color=POINTER, stroke_width=2.2) if tip is not None else None
                ring = None
                if part is None and tip is not None:
                    ring = Circle(radius=0.16, color=UNKNOWN, stroke_width=4).move_to(tip)
                beads = self._beads(label, at) if self.mode == "built" else None
                for mob in (line, beads, plate, words, ring):   # in this order: pointer and beads run UNDER the name's plate
                    if mob is not None:
                        mob.set_opacity(0)
                        written.append(mob)
                entry.update(layer=layers.get(part["id"]) if part else None, words=words, line=line, ring=ring, plate=plate,
                             beads=beads)
            self.labels[label["slug"]] = entry
            self.parts[label["slug"]] = self          # so a focus on it is known; never pulsed (see docstring)
        # The card covers the art AND every label, whichever of them is on screen: a label that
        # ran past the art's edge would otherwise be dark words on the dark background.
        ink = Group(self.art, self.frame, *written) if self.frame is not self.art else Group(self.art, *written)
        self.card = RoundedRectangle(width=ink.width + 0.36, height=ink.height + 0.36, corner_radius=0.12, stroke_width=0,
                                     fill_color=PAPER, fill_opacity=1).move_to(ink.get_center())
        overview = [m for m in (self.mini_frame, self.mini) if m is not None]
        window = [self.frame] if self.frame is not self.art else []
        self.add(self.card, *window, self.art, *layers.values(), *closeups, *overview, *written)
        self.build = [("fade", [self.card, self.art])]
        self.credit = str(manifest.get("credit") or "")
        self._lit = self._ring = self._flowing = self._close = None

    def _keep_inside(self, words) -> None:
        pad, box = 0.1, self.frame
        over = [max(0.0, box.get_left()[0] + pad - words.get_left()[0]) - max(0.0, words.get_right()[0] - box.get_right()[0] + pad),
                max(0.0, box.get_bottom()[1] + pad - words.get_bottom()[1]) - max(0.0, words.get_top()[1] - box.get_top()[1] + pad)]
        words.shift(RIGHT * over[0] + UP * over[1])

    def _plate(self, words):
        plate = RoundedRectangle(width=words.width + 0.2, height=words.height + 0.16, corner_radius=0.07, stroke_width=0,
                                 fill_color=PAPER, fill_opacity=1).move_to(words.get_center())
        words.background_rectangle = plate            # the layout probe's sign that these words are MEANT to sit on linework
        return plate

    def _beads(self, label: dict, at):
        """Small beads that run along a process's arrows, in the direction they were drawn. None when it has no paths."""
        colour = label.get("colour") or POINTER
        beads, tracks = VGroup(), []
        origin, across, down = self.art.get_corner(UP + LEFT), self.art.width, self.art.height
        for line in label.get("flows") or []:
            points = np.array([at(x, y) for x, y in line])
            total = float(np.linalg.norm(np.diff(points, axis=0), axis=1).sum())
            if total < 0.2 or not np.all(np.isfinite(points)):
                continue
            count = 1 if total < 1.2 else 2 if total < 2.6 else 3
            # A track is kept as shares of the art's own rectangle, not as places on the screen: the figure is
            # scaled and moved AFTER it is built (to fit its box), and the first beads ran where the arrows had been.
            shares = np.array([[(q[0] - origin[0]) / across, (origin[1] - q[1]) / down] for q in points])
            for k in range(count):
                beads.add(Circle(radius=0.1, stroke_color=colour, stroke_width=4, fill_color=WHITE, fill_opacity=1).move_to(points[0]))
                tracks.append((shares, k / count))
        if not tracks:
            return None
        clock = {"t": 0.0}

        def run(mob, dt):
            clock["t"] += dt
            origin, across, down = self.art.get_corner(UP + LEFT), self.art.width, self.art.height
            for bead, (shares, phase) in zip(mob, tracks):
                points = origin + np.outer(shares[:, 0] * across, RIGHT) + np.outer(shares[:, 1] * down, DOWN)
                steps = np.linalg.norm(np.diff(points, axis=0), axis=1)
                along, total = np.concatenate([[0.0], np.cumsum(steps)]), float(steps.sum())
                u = (clock["t"] / max(0.9, total / self.FLOW) + phase) % 1.0
                d = u * total
                i = int(min(max(np.searchsorted(along, d, side="right") - 1, 0), len(points) - 2))
                bead.move_to(points[i] + (points[i + 1] - points[i]) * ((d - along[i]) / max(along[i + 1] - along[i], 1e-9)))
                bead.set_opacity(min(1.0, 6 * u, 6 * (1 - u)))          # it arrives and leaves softly, so the loop has no jump

        beads.run = run
        return beads

    def _stop_flow(self) -> None:
        if self._flowing is not None:
            self._flowing.clear_updaters()
            self._flowing.set_opacity(0)
            self._flowing = None

    def resume(self, names) -> None:
        """Stand as after these focuses, with no animation: what earlier chapters drew in is there from the first frame.

        A chapter is a render of its own, so a drawing that is built up by its parts began every
        chapter bare: in the first lesson made on one (2026-10-09) the evaporation arrows the
        learner had watched being drawn in chapter 3 were gone when chapter 4 opened. The chapter
        runtime calls this with the focuses of every earlier beat on the same drawing. For a
        poster (``built``) the part and its name are put back; for the older kinds only the name
        (lighting one part is of the moment); for a drawing shown by close-ups nothing is, since
        it opens on the whole drawing each time. Nothing flows until the next focus.
        """
        if self.mode == "zoomed":
            return
        for name in names or []:
            label = self.labels.get(str(name))
            if label is None:
                continue
            if self.mode == "built" and label["layer"] is not None:
                label["layer"].set_opacity(1)
            if not label["shown"]:
                label["shown"] = True
                for mob in (label["line"], label["words"]):
                    if mob is not None:
                        mob.set_opacity(1)
                if label.get("plate") is not None:
                    label["plate"].set_opacity(self.PLATE)

    def focus_animations(self, name: str) -> list:
        """What happens on screen when a step is about ``name``. [] for a name this diagram does not have."""
        label = self.labels.get(name)
        if label is None:
            return []
        out = []
        if self.mode == "zoomed":
            previous = self._close
            if previous is not None and previous is not label:
                out += [m.animate.set_opacity(0) for m in (previous["close"], previous["words"], previous["plate"])]
                out += [m.animate.set_stroke(opacity=0) for m in (previous["ring"], previous["region"])]
            out += [label["close"].animate.set_opacity(1), label["ring"].animate.set_stroke(opacity=1),
                    label["words"].animate.set_opacity(1), label["plate"].animate.set_opacity(self.PLATE),
                    label["region"].animate.set_stroke(opacity=1)]
            if previous is None:
                out += [self.mini_frame.animate.set_opacity(1), self.mini.animate.set_opacity(1)]
            self._close = label
            return out
        layer = label["layer"]
        if self.mode == "built":
            beads = label["beads"]

            def flow(beads=beads) -> None:                                # when the step is PLAYED, not when it is prepared
                self._stop_flow()
                if beads is not None:
                    beads.add_updater(beads.run)
                    self._flowing = beads

            out.append(_Then(beads if beads is not None else self.art, flow))
            if layer is not None:
                out.append(layer.animate.set_opacity(1))                # drawn in, and it stays
        else:
            if self._lit is not None and self._lit is not layer:
                out.append(self._lit.animate.set_opacity(0))
            if self._ring is not None and self._ring is not label["ring"]:
                out.append(self._ring.animate.set_stroke(opacity=0))
            if layer is not None:
                out += [self.art.animate.set_opacity(self.DIM), layer.animate.set_opacity(1)]
            else:
                out.append(self.art.animate.set_opacity(1))
                if label["ring"] is not None:
                    out.append(label["ring"].animate.set_stroke(opacity=1))
            self._lit, self._ring = layer, label["ring"]
        if not label["shown"]:
            label["shown"] = True
            out += [m.animate.set_opacity(1) for m in (label["line"], label["words"]) if m is not None]
            if label.get("plate") is not None:
                out.append(label["plate"].animate.set_opacity(self.PLATE))
        return out


def diagram(p: dict) -> DiagramFigure:
    """A diagram already taken apart: ``manifest`` is the path ``harness.diagrams.take_apart`` wrote."""
    manifest = json.loads(Path(str(p["manifest"])).read_text(encoding="utf-8"))
    labels = [str(n) for n in p["labels"]] if isinstance(p.get("labels"), list) else None
    return DiagramFigure(manifest, labels)


class PictureFigure(Group):
    """A finished picture shown WHOLE, words and all (the diagram service's own drawing).

    For a drawing in which nothing can be pointed at: it is still the picture a textbook prints, which
    a model-written scene is not. One image on a white card. An image is not a VMobject: nothing may
    ``Indicate`` it or set its colour, so the renderer treats it as it treats a diagram and leaves it
    alone. The file is named by code (``harness.scripted.place_picture``), never by a model.

    With ``panels`` (a before-and-after drawing cut at its gutter, ``harness.diagrams.panels``) only the
    FIRST panel is on screen at the start, in the place it has in the whole drawing, and
    ``focus_animations("panel2")`` fades the next one in where it belongs and keeps it. The first demo
    showed the coin already lying in the glass while the voice was still asking what would happen to it.

    With ``points`` (the drawing's own printed labels, found by ``harness.typeset``: ``{name: {"box": x0, y0, x1,
    y1}}`` as shares of the picture shown) ``focus_animations(name)`` marks that label the way a teacher runs a
    highlighter over a word, and takes the mark off the one before. About half of what the drawing service
    returns is typeset, and such a drawing used to stand still through everything said about it. The marks are
    made when the figure is BUILT and are its children, so they keep their places when the renderer fits the
    figure into its box; only their opacity changes afterwards.
    """

    MARK, MARK_EDGE = "#FFD84D", "#B77900"          # a highlighter on white paper, and its edge

    def __init__(self, file: Path, height: float = 4.6, credit: str = "", panels: list | None = None, boxes: list | None = None,
                 points: dict | None = None, bleed: bool = False, sequence: dict | None = None):
        super().__init__()
        self.kind, self.parts = "picture", {}
        self.art = ImageMobject(str(file))
        self.art.scale_to_fit_height(height)
        # ``bleed``: an illustration with no print of its own (a scene, a place, a thing) fills the frame edge to edge
        # and the words lie on it; it has no card, and a part is marked by a bright outline, not by a highlighter.
        self.bleeds = bool(bleed)
        pad = 0.0 if self.bleeds else 0.16
        self.card = RoundedRectangle(width=self.art.width + pad, height=self.art.height + pad, corner_radius=0.1 if pad else 0.001,
                                     stroke_width=0, fill_color=PAPER, fill_opacity=0 if self.bleeds else 1).move_to(self.art.get_center())
        self.panels = []
        files = [Path(str(f)) for f in panels or []]
        if len(files) >= 2 and all(f.is_file() for f in files):
            pixels = self.art.pixel_array.shape[1], self.art.pixel_array.shape[0]
            if not (isinstance(boxes, list) and len(boxes) == len(files)):
                boxes = None
            top = self.art.get_top()[1]
            for n, panel_file in enumerate(files):
                panel = ImageMobject(str(panel_file))
                if boxes:                                # where this panel sits in the whole drawing, in its pixels
                    x0, y0, x1, y1 = boxes[n]
                    panel.stretch_to_fit_width((x1 - x0) / pixels[0] * self.art.width)
                    panel.stretch_to_fit_height((y1 - y0) / pixels[1] * self.art.height)
                    panel.move_to(self.art.get_corner(UP + LEFT) + RIGHT * (x0 + x1) / 2 / pixels[0] * self.art.width
                                  + DOWN * (y0 + y1) / 2 / pixels[1] * self.art.height)
                else:                                    # no boxes given: one under the other, each as wide as it is
                    panel.scale_to_fit_height(self.art.height * 0.94 / len(files))
                    if panel.width > self.art.width * 0.96:
                        panel.scale_to_fit_width(self.art.width * 0.96)
                    panel.move_to([self.art.get_center()[0], top - self.art.height * (n + 0.5) / len(files), 0])
                self.panels.append(panel if n == 0 else panel.set_opacity(0))
            self.art.set_opacity(0)                      # the whole drawing only lends its box
            self.add(self.card, self.art, *self.panels)
            self.build = [("fade", [self.card, self.panels[0]])]
            self._panel_boxes = [[float(v) for v in b] for b in boxes] if boxes else []
            self._pixels = pixels
        else:
            if self.bleeds:
                self.add(self.art)
                self.build = [("fade", [self.art])]
            else:
                self.add(self.card, self.art)
                self.build = [("fade", [self.card, self.art])]
            self._panel_boxes, self._pixels = [], (1, 1)
        self._brought = {1}                              # the panels on screen
        self.marks, self._marked = {}, None
        corner, w, h = self.art.get_corner(UP + LEFT), self.art.width, self.art.height
        for name, point in (points or {}).items() if isinstance(points, dict) else ():
            try:
                x0, y0, x1, y1 = (min(1.0, max(0.0, float(v))) for v in point["box"])
            except (TypeError, ValueError, KeyError):
                continue
            if x1 - x0 < 0.004 or y1 - y0 < 0.004 or (self.bleeds and (x1 - x0) * (y1 - y0) > 0.3):
                continue
            pad = 0.07                                   # round the words, not on them
            mark = RoundedRectangle(width=(x1 - x0) * w + 2 * pad, height=(y1 - y0) * h + 2 * pad, corner_radius=0.06,
                                    stroke_color=self.MARK if self.bleeds else self.MARK_EDGE, stroke_width=7 if self.bleeds else 3,
                                    fill_color=self.MARK)
            mark.set_fill(opacity=0).set_stroke(opacity=0)
            mark.move_to(corner + RIGHT * (x0 + x1) / 2 * w + DOWN * (y0 + y1) / 2 * h)
            mark.at = ((x0 + x1) / 2, (y0 + y1) / 2)
            self.marks[str(name)] = mark
            self.add(mark)
        self.credit = str(credit or "")
        # The drawing as a sequence of its parts (``harness/sequence.py``): what ``paint`` draws, part by part.
        self._sequence = sequence if isinstance(sequence, dict) and sequence.get("parts") and not self.panels and not self.bleeds else None
        # which taking-apart of the drawing this is: a plan of drawing it with the words names its parts by their numbers
        self.sequence_id = ":".join(str(sequence.get(k) or "") for k in ("version", "of", "named")) if self._sequence else ""
        self._painted, self._waiting = [], None
        # Drawn WITH the words (``hold_back``): the pen-work of every part by its number, the parts not drawn yet, and
        # how many pens are at work this moment (the one that draws it when it arrives, and a step's).
        self._pens, self._hidden, self._staged, self._painting = {}, set(), False, 0
        # What a hand has added (``annotate``): the marks that stand, by their slot, and the one gesture of the moment.
        self._notes, self._gesture = {}, None
        self._ready, self._spent = {}, []                # marks made and waiting unseen; marks that have left (``prepare_marks``)

    #: How a part is drawn by hand: the least pen a line gets, how far a hand strays from the true line (as a share of
    #: the drawing's width), and how long the whole drawing may take.
    PEN_LEAST, HAND, PAINT_SECONDS = 2.2, 0.0012, (2.4, 5.5)

    def paint(self, numbers=None):
        """``(animation, seconds)`` that DRAWS the picture part by part, or None when it has no sequence of parts.

        The owner, 2026-10-12: "the visuals are static … different parts of the visual should be coming in a sequence
        … then you take the pattern and style it". Every line and shape of the drawing's SVG is drawn with a pen in
        its own colour along its own outline, in the order of the sequence (a slight unevenness of the hand in each
        stroke); a filled shape is outlined and then filled; a label arrives beside the shape it names; and the
        finished drawing itself, exactly as the service made it, comes in over the pen-work at the end. The parts
        are made HERE, when the figure has its place and size in the frame: a stroke's width does not follow a later
        scaling. At its start nothing but the card is to be seen; at its end the figure is as it always was.
        """
        if not self._sequence:
            return None
        if self._staged:
            return self._paint_staged(numbers)
        if numbers is not None:
            return None                                  # nothing is held back: a step has nothing to bring
        for old in self._painted:
            self.remove(old)
        made, pen = self._pen_work()
        if len(made) < 2:
            return None
        self._painted = [mob for mob, _, _ in made]
        # under the finished picture and its marks: with the picture on top of them nothing of the pen-work shows
        under = self.submobjects.index(self.art)
        self.submobjects[under:under] = self._painted
        drawn = LaggedStart(*self._strokes(made), lag_ratio=0.55)
        seconds = min(self.PAINT_SECONDS[1], max(self.PAINT_SECONDS[0], 1.6 + 0.45 * pen + 0.04 * len(made)))
        self.art.set_opacity(0)
        return AnimationGroup(drawn, FadeIn(self.art, run_time=0.35), lag_ratio=1.0), seconds

    @staticmethod
    def _fill_opacity(part: dict) -> float:
        """How strongly a filled part is filled: its fill's OWN opacity (a pale wash under a dark edge was painted solid
        when the edge's opacity was taken for it)."""
        value = part.get("fill_opacity")
        return min(1.0, float((part.get("opacity") if value in (None, "") else value) or 1.0))

    @staticmethod
    def _strokes(made) -> list:
        return [DrawBorderThenFill(mob, run_time=seconds, rate_func=smooth) if part["kind"] == "fill" and part.get("fill")
                else FadeIn(mob, run_time=seconds, scale=0.92) if part["kind"] == "text"
                else Create(mob, run_time=seconds, rate_func=smooth) for mob, part, seconds in made]

    def _pen_work(self):
        """``([(mobject, part, seconds), …], pen)``: every part of the sequence as something a pen can draw, made where
        the figure stands NOW, and how much pen they take together."""
        corner, w, h = self.art.get_corner(UP + LEFT), self.art.width, self.art.height
        rng = np.random.default_rng(len(self._sequence["parts"]))
        pixels = self.art.pixel_array
        made, pen = [], 0.0
        for part in self._sequence["parts"]:
            x0, y0, x1, y1 = part["box"]
            if part["kind"] == "text":
                pad_x, pad_y = 0.004, 0.006
                left, top = max(0, int((x0 - pad_x) * pixels.shape[1])), max(0, int((y0 - pad_y) * pixels.shape[0]))
                right, bottom = min(pixels.shape[1], int((x1 + pad_x) * pixels.shape[1]) + 1), min(pixels.shape[0], int((y1 + pad_y) * pixels.shape[0]) + 1)
                if right - left < 2 or bottom - top < 2:
                    continue
                words = ImageMobject(pixels[top:bottom, left:right].copy())
                words.stretch_to_fit_width((right - left) / pixels.shape[1] * w)
                words.stretch_to_fit_height((bottom - top) / pixels.shape[0] * h)
                words.move_to(corner + RIGHT * (left + right) / 2 / pixels.shape[1] * w + DOWN * (top + bottom) / 2 / pixels.shape[0] * h)
                made.append((words, part, 0.35))
                continue
            points = np.clip(np.array(part["points"], dtype=float), 0.0, 1.0)    # a shape the drawing's edge cuts is cut there
            if len(points) < 2:
                continue
            if str(part.get("fill") or "").lower() in ("#ffffff", "#fff") and not part.get("stroke"):
                continue                                 # a white plate behind a label: paper on paper
            if len(points) > 6 and part["length"] > 0.04:                   # the hand: a slow, slight wander, none at the ends
                drift = np.cumsum(rng.standard_normal((len(points), 2)), axis=0)
                drift -= np.linspace(0, 1, len(points))[:, None] * drift[-1]
                drift *= self.HAND / (np.abs(drift).max() + 1e-9)
                points = points + drift
            path = VMobject()
            path.set_points_as_corners([corner + RIGHT * x * w + DOWN * y * h for x, y in points])
            colour = part.get("stroke") or part.get("fill") or "#1F2933"
            width = max(self.PEN_LEAST, float(part.get("width") or 0) * w * 100)
            path.set_stroke(colour, width=width, opacity=1.0)
            if part.get("dashed") and part["kind"] == "stroke":          # a dashed line is drawn dash by dash
                dashes = max(4, min(120, round(float(part["length"]) / max(float(part.get("dash") or 0.0), 0.004))))
                path = DashedVMobject(path, num_dashes=dashes, dashed_ratio=0.5)
            if part["kind"] == "fill" and part.get("fill"):
                path.set_fill(part["fill"], opacity=self._fill_opacity(part))
            else:
                path.set_fill(opacity=0)
            made.append((path, part, max(0.3, min(1.6, 0.35 + 1.5 * float(part["length"]) ** 0.6))))
            pen += float(part["length"])
        return made, pen

    # ── drawn WITH the words ─────────────────────────────────────────────────────────────────────────────────────
    #: How long the parts one step brings are drawn for, at least and at most (the step's own room may shorten it).
    STEP_SECONDS = (0.7, 2.6)

    def hold_back(self, waiting, planned: str = "") -> bool:
        """Hold back the parts (their numbers in the sequence) that the words have not reached yet. True when any is.

        A drawing that drew itself at once was finished five seconds into the lesson and held the whole proof before
        a word of it (a reference lecture beside ours, 2026-10-12: nothing is on its board before it is spoken of).
        With parts held back the figure is its PEN-WORK: what has been drawn stands as drawn, ``paint(numbers)`` draws
        the parts a step brings, and the finished picture takes the pen-work's place when the last part is there.
        (Not named ``stage``: a code-drawn ``Figure`` has a method of that name, and the renderer asks a figure whether
        it can do this by the name.) Called once the figure has its place and size, before it is shown. Nothing of this for a figure with no
        sequence, with panels, or when none of the numbers is a part of it: then it is as it always was. Nor when the
        plan was made for another taking-apart of the drawing than the one on disk now (``planned``, from the
        lesson's figure): its numbers would name other parts, and the wrong lines would wait for the wrong words.
        """
        if not self._sequence or self._staged:
            return self._staged
        waiting = {int(n) for n in waiting or () if str(n).lstrip("-").isdigit()}
        if not waiting or (planned and str(planned) != self.sequence_id):
            return False
        made, _ = self._pen_work()
        waiting &= {int(part["n"]) for _, part, _ in made}
        if len(made) < 2 or not waiting:
            return False
        for old in self._painted:
            self.remove(old)
        self._painted = [mob for mob, _, _ in made]
        under = self.submobjects.index(self.art)
        self.submobjects[under:under] = self._painted
        self._pens = {int(part["n"]): (mob, part, seconds) for mob, part, seconds in made}
        self._hidden = waiting
        for n in waiting:
            self._pens[n][0].set_opacity(0)
        self.art.set_opacity(0)
        self._staged = True
        return True

    def _show(self, n: int) -> None:
        mob, part, _ = self._pens[n]
        if part["kind"] == "text":
            mob.set_opacity(1)
        else:
            mob.set_stroke(opacity=1.0)
            if part["kind"] == "fill" and part.get("fill"):
                mob.set_fill(opacity=self._fill_opacity(part))
        self._hidden.discard(n)

    def reveal(self, numbers) -> None:
        """Those parts are there, at once (a preview of stills; a part that could not be drawn in)."""
        for n in numbers or ():
            if n in self._hidden:
                self._show(n)
        if self._staged and not self._hidden and not self._painting:
            self.painted()

    def _paint_staged(self, numbers):
        """``(animation, seconds)`` for the parts that are there when the drawing arrives (``numbers`` None) or for the
        ones a step brings; None when there is nothing to draw."""
        if numbers is None:
            which = [n for n in self._pens if n not in self._hidden]
        else:
            which = [n for n in dict.fromkeys(int(n) for n in numbers) if n in self._hidden]
            for n in which:
                self._show(n)
        made = [self._pens[n] for n in which]
        if not made:
            return None
        pen = sum(float(part["length"]) for _, part, _ in made if part["kind"] != "text")
        drawn = LaggedStart(*self._strokes(made), lag_ratio=0.55)
        if numbers is None:
            seconds = min(self.PAINT_SECONDS[1], max(1.2, 1.2 + 0.45 * pen + 0.04 * len(made)))
        else:
            seconds = self._step_seconds(made)
        self._painting += 1
        return drawn, seconds

    def _step_seconds(self, made) -> float:
        pen = sum(float(part["length"]) for _, part, _ in made if part["kind"] != "text")
        return min(self.STEP_SECONDS[1], max(self.STEP_SECONDS[0], 0.5 + 0.9 * pen + 0.12 * len(made)))

    def pen_seconds(self, numbers) -> float:
        """How long the pen will be at work on the parts a step brings (what ``paint(numbers)`` will say), without
        drawing anything: a mark of the hand that stands on one of them waits that long (``runtime._marks_due``)."""
        made = [self._pens[n] for n in dict.fromkeys(int(n) for n in numbers or ()) if n in self._pens]
        return self._step_seconds(made) if made else 0.0

    def painted(self):
        """The drawing stands finished: the picture itself, and nothing of the pen-work under it."""
        if self._staged:
            # Parts are still held back: what the pen drew stays as drawn. When the last part is there, the finished
            # picture takes the pen-work's place.
            self._painting = max(0, self._painting - 1)
            if not self._hidden and not self._painting:  # not while another pen is still drawing the last of it
                self._staged = False
                self.painted()
                return
            mark, self._waiting = getattr(self, "_waiting", None), None
            if mark is not None:
                self._mark_now(mark)
            return
        self.art.set_opacity(1)
        for old in self._painted:
            self.remove(old)
        self._painted = []
        mark, self._waiting = getattr(self, "_waiting", None), None
        if mark is not None:                             # the label a step pointed at while the pen was still at work
            self._mark_now(mark)

    def _mark_now(self, mark) -> None:
        if self._staged and self._label_under(mark) is not None:
            return                                       # its label is not drawn yet: see ``focus_animations``
        if self._marked is not None:
            self._marked.set_fill(opacity=0).set_stroke(opacity=0)
        mark.set_fill(opacity=0.38).set_stroke(opacity=1)
        self._marked = mark

    def _label_under(self, mark):
        """The number of the printed label a mark lies on, when that label is a part still held back; else None."""
        x, y = mark.at
        for n in list(self._hidden):
            part = self._pens[n][1]
            x0, y0, x1, y1 = part["box"]
            if part["kind"] == "text" and x0 - 0.01 <= x <= x1 + 0.01 and y0 - 0.012 <= y <= y1 + 0.012:
                return n
        return None

    # ── what a hand adds (harness/annotate.py) ───────────────────────────────────────────────────────────────────────
    HAND_INK = "#C62828"                             # a teacher's red pen on white paper

    def _mark(self, mark: dict):
        """A mark's primitives (paths and pieces of text, in shares of the drawing) as mobjects standing on the picture,
        or None when it draws nothing (a wipe)."""
        corner, w, h = self.art.get_corner(UP + LEFT), self.art.width, self.art.height
        at = lambda x, y: corner + RIGHT * float(x) * w + DOWN * float(y) * h                      # noqa: E731
        made = VGroup()
        for prim in mark.get("prims") or []:
            if prim.get("shape") == "path" and len(prim.get("points") or []) >= 2:
                points = [at(x, y) for x, y in prim["points"]]
                line = VMobject()
                line.set_points_as_corners(points + (points[:1] if prim.get("closed") else []))
                if prim.get("soft"):                     # a highlighter pass: broad and see-through, the line under it stays readable
                    line.set_stroke(self.HAND_INK, width=11.0, opacity=0.3).set_fill(opacity=0)
                else:
                    line.set_stroke(self.HAND_INK, width=1.6 if prim.get("thin") else 4.0, opacity=1.0).set_fill(opacity=0)
                made.add(line)
                if prim.get("arrow"):                    # its head: two short strokes back from the tip
                    tip, back = points[-1], points[-2]
                    along = (tip - back) / max(float(np.linalg.norm(tip - back)), 1e-6)
                    across = np.array([-along[1], along[0], 0.0])
                    size = 0.022 * w
                    for side in (1, -1):
                        barb = VMobject()
                        barb.set_points_as_corners([tip, tip - along * size * 1.6 + across * size * side])
                        made.add(barb.set_stroke(self.HAND_INK, width=4.0, opacity=1.0))
            elif prim.get("shape") == "text" and str(prim.get("text") or "").strip():
                x0, y0, x1, y1 = prim["box"]
                words = Text(str(prim["text"]), font=FONT, color=self.HAND_INK, weight="BOLD")
                words.scale_to_fit_height(max(0.05, (y1 - y0) * h * 0.74))
                if words.width > (x1 - x0) * w * 1.04:
                    words.scale_to_fit_width((x1 - x0) * w * 1.04)
                words.move_to(at((x0 + x1) / 2, (y0 + y1) / 2))
                words.add_background_rectangle(color=PAPER, opacity=0.86, buff=0.03)       # readable over a line of the drawing
                made.add(words)
        return made if len(made) else None

    def prepare_marks(self, marks) -> None:
        """Make the mobjects of the marks a beat is going to add and put them on the picture UNSEEN, before the beat's
        first frame.

        A scene draws, through one play, the list of mobjects it took when the play began: a mobject added in the middle
        of a wait is not drawn until the next play starts, and one removed is drawn until then. A value recorded at
        10.3 s was not on screen at 11.5 s, and a ring that had "left" at 6.0 s was still there at 6.5 s (the filmed
        test, 2026-10-12). So nothing is added or removed while a beat runs: a mark is there from the start, unseen,
        and only what can be SEEN of it changes (``annotate``, ``clear_gesture``); ``sweep`` takes the spent ones away
        when the beat is over.
        """
        for mark in marks or ():
            key = id(mark)
            if key in self._ready or not mark.get("prims"):
                continue
            made = self._mark(mark)
            if made is None:
                continue
            made.save_state()
            made.set_opacity(0)
            self.add(made)
            self._ready[key] = made

    def annotate(self, marks, now: bool = False) -> list:
        """A hand adds these marks to the picture; returns the animations that draw them (none with ``now``: a still, a
        chapter that finds them standing). A mark that STAYS takes its slot: what stood there leaves, and a mark with
        nothing to draw only wipes it. A gesture (a ring, a line gone over, an arrow) is there until the next one:
        the hand is in one place at a time. ``self.left`` lists the ids of the marks that left."""
        out, self.left = [], []
        for mark in marks or ():
            stays = mark.get("life") == "stays"
            if stays:
                old = self._notes.pop(str(mark.get("slot")), None)
            else:
                old, self._gesture = self._gesture, None
            if old is not None:
                old[1].set_opacity(0)                    # unseen at once; taken away when the beat is over (``sweep``)
                self._spent.append(old[1])
                self.left.append(old[0])
            made = self._ready.pop(id(mark), None)
            if made is not None:
                made.restore()                           # as it was made: seen
            else:
                made = self._mark(mark)                  # not prepared (a still, a chapter's start): made now
                if made is None:
                    continue
                self.add(made)
            if stays:
                self._notes[str(mark.get("slot"))] = (mark.get("id"), made)
            else:
                self._gesture = (mark.get("id"), made)
            if not now:
                out.append(LaggedStart(*[FadeIn(part, scale=0.9, run_time=0.4) if isinstance(part, Text) else Create(part, run_time=0.5)
                                         for part in made], lag_ratio=0.5))
        return out

    def clear_gesture(self) -> None:
        """The hand's gesture leaves; what was written stays."""
        self.left = []
        if self._gesture is not None:
            self._gesture[1].set_opacity(0)
            self._spent.append(self._gesture[1])
            self.left.append(self._gesture[0])
            self._gesture = None

    def sweep(self) -> None:
        """The beat is over: marks that left, and marks that were prepared and never made, are taken off the picture."""
        for made in self._spent + list(self._ready.values()):
            self.remove(made)
        self._spent, self._ready = [], {}

    def _panel_of(self, at: tuple) -> int:
        """The panel (1, 2, …) a place in the picture belongs to; 0 when the picture has none or it is in none."""
        px, py = at[0] * self._pixels[0], at[1] * self._pixels[1]
        for n, (x0, y0, x1, y1) in enumerate(self._panel_boxes, 1):
            if x0 <= px <= x1 and y0 <= py <= y1:
                return n
        return 0

    def _bring(self, number: int) -> list:
        if not 2 <= number <= len(self.panels) or number in self._brought:
            return []
        self._brought.add(number)
        return [self.panels[number - 1].animate.set_opacity(1)]

    def focus_animations(self, name: str) -> list:
        """``panel2``, ``panel3`` … brings that panel in and keeps it; a printed label's name marks that label.

        A label in a panel that is not on screen yet brings its panel in with it: a mark on an empty
        place would point at nothing. Anything else: nothing.
        """
        key = str(name or "").strip().lower()
        found = re.fullmatch(r"panel_?(\d+)", key)
        if found:
            return self._bring(int(found.group(1)))
        mark = self.marks.get(key)
        if mark is None or mark is self._marked:
            return []
        if self._painting if self._staged else self._painted:
            # The drawing is still being drawn (``paint``): a highlighter on a label that is not there yet marked an
            # empty place for two seconds. The mark waits and is there when the drawing stands (``painted``).
            self._waiting = mark
            return []
        if self._staged and self._label_under(mark) is not None:
            # The label is not drawn yet (its step is still to come): a highlighter on bare paper points at nothing,
            # and bringing the label in alone put a "5" beside a line that was not there. What is on the board is
            # decided by the steps' ``draw`` alone, so every chapter can put it back as it was.
            return []
        out = self._bring(self._panel_of(mark.at))
        if self._marked is not None:
            out.append(self._marked.animate.set_fill(opacity=0).set_stroke(opacity=0))
        out.append(mark.animate.set_fill(opacity=0.08 if self.bleeds else 0.38).set_stroke(opacity=1))
        self._marked = mark
        return out


def picture(p: dict) -> PictureFigure:
    """A picture file already on this machine: ``file`` is its path (a PNG the diagram tool kept)."""
    file = Path(str(p["file"]))
    if not file.is_file() or file.suffix.lower() not in (".png", ".jpg", ".jpeg"):
        raise ValueError(f"no picture at {file.name}")
    panels = [str(f) for f in p["panels"]] if isinstance(p.get("panels"), list) else None
    sequence = None
    if file.name == "whole.png" and not panels:          # the drawing as drawn: its parts are where its SVG has them
        try:
            sequence = json.loads((file.parent / "sequence.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            sequence = None
    return PictureFigure(file, credit=str(p.get("credit") or ""), panels=panels, boxes=p.get("panel_boxes"),
                         points=p.get("points") if isinstance(p.get("points"), dict) else None, bleed=bool(p.get("bleed")),
                         sequence=sequence)


# --- a chemical reaction drawn as ball molecules ------------------------------------------------------------------
#: Atom colours that read on the dark page (roughly the usual model-kit colours). An element not listed takes the
#: next of ``_SPARE`` in order of appearance, so two elements never share a colour in one picture.
ATOM_COLOURS = {"H": "#F2F3F5", "O": "#E8505B", "N": "#5B8DEF", "C": "#9AA0A8", "Mg": "#9AD06A", "Cl": "#3FD0A0",
                "Na": "#B07CE8", "S": "#F2D04B", "Fe": "#E0904A", "Ca": "#E6C8A0", "K": "#C08AE0", "Cu": "#D08A55",
                "Zn": "#A9B8D8", "Al": "#C8CED6", "P": "#F59A3C", "Ag": "#D9DDE3", "Br": "#B5524A", "I": "#9B5FC0"}
_SPARE = ("#F2A7C3", "#B9E36B", "#6FC7E8", "#E8C36F")
_BALL = 0.26


def _ball(element: str, colour: str):
    r = _BALL * (0.78 if element == "H" else 1.0)
    return Circle(radius=r, stroke_color="#0E1014", stroke_width=1.5, fill_color=colour, fill_opacity=1)


def _molecule(atoms: list[tuple[str, int]], colours: dict) -> VGroup:
    """One molecule as touching balls: a lone atom in the middle when there is one (H2O, NH3, CO2), else a row."""
    flat = [el for el, k in atoms for _ in range(k)]
    balls = [_ball(el, colours[el]) for el in flat]
    for ball, el in zip(balls, flat):
        ball.element = el                          # what the voice-led hints light (``hint_targets``)
    singles = [el for el, k in atoms if k == 1]
    if 3 <= len(flat) <= 5 and singles and len({el for el in flat if el != singles[0]}) == 1:
        centre_el = singles[0]
        centre = balls[flat.index(centre_el)]
        others = [b for b, el in zip(balls, flat) if b is not centre]
        reach = centre.width / 2 + others[0].width / 2 - 0.03
        spread = {2: (210, 330), 3: (90, 210, 330), 4: (45, 135, 225, 315)}[len(others)]
        if len(others) == 2 and centre_el == "C":
            spread = (180, 0)                      # CO2 is straight
        for b, deg in zip(others, spread):
            b.move_to(centre.get_center() + reach * np.array([math.cos(math.radians(deg)), math.sin(math.radians(deg)), 0]))
        return VGroup(*others, centre)             # the centre on top
    group = VGroup(*balls)
    for i, (prev, b) in enumerate(zip(balls, balls[1:])):
        b.next_to(prev, RIGHT, buff=-0.08)
        if len(balls) >= 4:                        # a chain of four or more bends, as H2O2 does
            b.shift(UP * (0.12 if i % 2 == 0 else -0.12))
    return group


def _formula_text(sp: dict, colour: str, size: int = 30):
    """A species' formula in the lesson font with real subscripts ("2 H₂O"); an unknown coefficient is a box."""
    body = re.sub(r"(\d+)", r"<sub>\1</sub>", sp["formula"])
    text = MarkupText(body, font=FONT, font_size=size, color=colour)
    if sp["unknown"]:
        box = Square(side_length=text.height * 0.95, color=UNKNOWN, stroke_width=3)
        return VGroup(box, text).arrange(RIGHT, buff=0.12)
    if sp["n"] > 1:
        return VGroup(Text(str(sp["n"]), font=FONT, font_size=size, color=colour), text).arrange(RIGHT, buff=0.1,
                                                                                                aligned_edge=DOWN)
    return text


def reaction(p: dict) -> Figure:
    """A chemical equation drawn as molecules: ``equation`` ("2H2 + O2 -> 2H2O", an unknown coefficient as "?").

    Code reads the equation once (``figure_math.parse_equation``) and draws every molecule, every formula and the
    atom count of each side from that reading, so the picture cannot show two waters labelled "H2O2" or a count the
    formula does not have. Start, arrow and product stand on one line; under them a small table, one column per
    element and a "before" and an "after" row, so each count stands straight under the other side's, and a verdict
    (balanced / not balanced yet / find the numbers / formula changed) under the table. ``counts`` (default true)
    shows the counts. ``role: "wrong"`` marks a forbidden formula change: the formulas named in ``wrong`` (default:
    the products) are drawn in the WRONG colour, the rest are left alone.
    Parts: left, right, mol0… (each species' molecules), formula0…, arrow, left_count, right_count, count_<el>, verdict.
    """
    parsed = figure_math.parse_equation(p.get("equation", ""))
    order = []
    for side in ("left", "right"):
        for sp in parsed[side]:
            for el, _ in sp["atoms"]:
                if el not in order:
                    order.append(el)
    spare = iter(_SPARE)
    colours = {el: ATOM_COLOURS.get(el) or next(spare, MUTED) for el in order}
    wrong = set()
    if str(p.get("role", "")) == "wrong":
        named = p.get("wrong")
        wrong = {re.sub(r"\s+", "", figure_math._plain_formula(w)) for w in named} if isinstance(named, list) and named \
            else {sp["formula"] for sp in parsed["right"]}
    fig = Figure("reaction")
    fig.species_info, fig.atom_balls, fig.tally_pieces, fig.formula_labels = [], [], {}, []
    rows, formulas, mols, pluses, k = {}, {}, {}, {}, 0
    for side in ("left", "right"):
        row = VGroup()
        for j, sp in enumerate(parsed[side]):
            copies = VGroup(*[_molecule(sp["atoms"], colours) for _ in range(sp["n"])])
            if sp["n"] > 1:
                copies.arrange_in_grid(cols=min(3, sp["n"]), buff=0.3)
            label = _formula_text(sp, WRONG if sp["formula"] in wrong else INK)
            label.next_to(copies, DOWN, buff=0.25)
            if j:
                plus = Text("+", font=FONT, font_size=40, color=MUTED)
                pluses[f"plus{len(pluses)}"] = plus
                row.add(plus)
            row.add(VGroup(copies, label))
            mols[f"mol{k}"], formulas[f"formula{k}"] = copies, label
            fig.species_info.append({"formula": sp["formula"], "side": side, "atoms": sp["atoms"], "n": sp["n"],
                                     "unknown": sp["unknown"]})
            fig.formula_labels.append(label)
            fig.atom_balls += [{"side": side, "element": b.element, "species": k, "ball": b}
                               for b in copies.get_family() if hasattr(b, "element")]
            k += 1
        row.arrange(RIGHT, buff=0.5)
        for item in row:                               # a "+" sits level with the balls, not with the labels
            if isinstance(item, Text):
                item.match_y(VGroup(*[m for m in row if not isinstance(m, Text)])[0][0])
        rows[side] = row
    # One line, start -> product, with the count table under it: the frame is wide, so a picture laid out
    # side by side is limited by the box's height last and comes out larger than a column (2026-10-20 sheets).
    arrow = Arrow(LEFT * 0.5, RIGHT * 0.5, buff=0, color=MUTED, stroke_width=5, max_tip_length_to_length_ratio=0.3)
    VGroup(rows["left"], arrow, rows["right"]).arrange(RIGHT, buff=0.45)
    balls_y = VGroup(*[m[0] for m in rows["left"] if not isinstance(m, Text)])[0].get_center()[1]
    arrow.set_y(balls_y)
    fig.stage("grow", **mols)
    fig.stage("draw", arrow=arrow)
    fig.stage("fade", **formulas, **pluses)
    fig.parts["left"], fig.parts["right"] = rows["left"], rows["right"]
    fig.parts["arrow"] = arrow
    if p.get("counts", True) is not False:
        left, right = figure_math.atom_counts(parsed["left"]), figure_math.atom_counts(parsed["right"])
        # A small table under the picture: one column per element, "before" and "after" rows, so each count stands
        # straight under the other side's (beside the rows it was crowded against the words column, 2026-10-20).
        pic = VGroup(rows["left"], arrow, rows["right"])
        col_w, size = 1.15, 32
        heads = VGroup(*[VGroup(_ball(el, colours[el]).scale(0.8), Text(el, font=FONT, font_size=size, color=INK)
                                ).arrange(RIGHT, buff=0.1) for el in order])
        names = {"left": Text("before", font=FONT, font_size=26, color=MUTED),
                 "right": Text("after", font=FONT, font_size=26, color=MUTED)}
        name_w = max(n.width for n in names.values()) + 0.35
        table_w = name_w + col_w * len(order)
        x_start = pic.get_center()[0] - table_w / 2
        y = pic.get_bottom()[1] - 0.55
        for c, head in enumerate(heads):
            head.move_to([x_start + name_w + col_w * (c + .5), y, 0])
        tallies = {}
        for r, (side, counts, other) in enumerate((("left", left, right), ("right", right, left))):
            yy = y - 0.62 * (r + 1)
            names[side].move_to([x_start, yy, 0], aligned_edge=LEFT)
            words = VGroup(names[side])
            for c, el in enumerate(order):
                if el not in counts:
                    continue
                tone = RESULT if counts[el] == other.get(el) else WRONG
                piece = Text(str(counts[el]), font=FONT, font_size=size, color=tone)
                piece.move_to([x_start + name_w + col_w * (c + .5), yy, 0])
                words.add(piece)
                fig.tally_pieces[(side, el)] = piece
                fig.parts.setdefault(f"count_{el.lower()}", VGroup()).add(piece)
            tallies[f"{side}_count"] = words
        fig.stage("fade", count_heads=heads)
        unknown = any(sp["unknown"] for side in parsed.values() for sp in side)
        if wrong:                                      # the atoms may match, and it is still not this reaction
            verdict = Text("formula changed: not allowed", font=FONT, font_size=28, color=WRONG)
        elif unknown:
            verdict = Text("find the numbers", font=FONT, font_size=30, color=UNKNOWN)
        elif left == right:
            verdict = Text("balanced", font=FONT, font_size=32, color=RESULT)
        else:
            verdict = Text("not balanced yet", font=FONT, font_size=30, color=WRONG)
        verdict.move_to([pic.get_center()[0], y - 0.62 * 3 + 0.05, 0])
        fig.stage("fade", **tallies)
        fig.stage("fade", verdict=verdict)
    fig.element_order = order
    fig.hint_targets = lambda event: _reaction_targets(fig, event)
    fig.change_from = lambda old: reaction_change(old, fig)
    return fig


def reaction_change(old, new) -> list:
    """How one reaction picture BECOMES the next: ``[(animation, ...)]`` in the order they play (``runtime`` plays them).

    A coefficient that rises is new molecules growing out of the ones already there, a formula that changes is its
    molecule rebuilt in place, then every count that changes rolls to its new number (owner, 2026-10-20: "less
    dynamic"; the visual-teaching module's step 7, "animate a correct coefficient change", then step 8, "recount").
    Molecules, formulas and counts are matched by side, formula and element, so only what changed moves.
    Returns [] when ``old`` is not a reaction picture (the caller then morphs the figures whole)."""
    from manim import FadeOut, ReplacementTransform, Transform
    if getattr(old, "kind", None) != "reaction" or not hasattr(old, "species_info"):
        return []
    first, second = [], []
    used = set()
    for k, sp in enumerate(new.species_info):
        j = next((i for i, o in enumerate(old.species_info) if i not in used and o["side"] == sp["side"]
                  and o["formula"] == sp["formula"]), None)
        mols, label = new.parts[f"mol{k}"], new.parts[f"formula{k}"]
        if j is None:                                   # a formula that changed: its molecule is rebuilt in place
            j = next((i for i, o in enumerate(old.species_info) if i not in used and o["side"] == sp["side"]), None)
            if j is None:
                first.append(FadeIn(VGroup(mols, label)))
                continue
            used.add(j)
            first += [ReplacementTransform(old.parts[f"mol{j}"], mols),
                      ReplacementTransform(old.parts[f"formula{j}"], label)]
            continue
        used.add(j)
        before, after = list(old.parts[f"mol{j}"]), list(mols)
        for a, b in zip(before, after):
            first.append(ReplacementTransform(a, b))
        for b in after[len(before):]:                   # the coefficient rose: a copy grows out of the last one there
            source = before[-1] if before else b
            first.append(GrowFromPoint(b, source.get_center()))
        for a in before[len(after):]:
            first.append(FadeOut(a, scale=0.5))
        first.append(ReplacementTransform(old.parts[f"formula{j}"], label))
    for i, o in enumerate(old.species_info):
        if i not in used:
            first.append(FadeOut(VGroup(old.parts[f"mol{i}"], old.parts[f"formula{i}"])))
    for name in [n for n in new.parts if n.startswith("plus") or n == "arrow"]:
        first.append(ReplacementTransform(old.parts[name], new.parts[name]) if name in old.parts
                     else FadeIn(new.parts[name]))
    for name in [n for n in old.parts if (n.startswith("plus") or n == "arrow") and n not in new.parts]:
        first.append(FadeOut(old.parts[name]))
    if getattr(new, "staged_steps", False):
        # look ``staging: steps`` (video-quality plan S5): the old counts and verdict LEAVE first, then the molecules change,
        # and the new table and verdict are drawn at their own words (``runtime._hold_back_steps``). Before, the old '4' and
        # '1' and the old verdict stood among the moving molecules (the 120.0 to 121.8 s ghosts), or rolled over to numbers
        # the voice had not counted yet.
        gone = [old.parts[n] for n in ("count_heads", "left_count", "right_count", "verdict") if n in old.parts]
        return ([AnimationGroup(*[FadeOut(m) for m in gone])] if gone else []) + [AnimationGroup(*first)]
    # the recount: a number that stays slides into place, one that changes rolls over to its new value
    old_t, new_t = getattr(old, "tally_pieces", {}), getattr(new, "tally_pieces", {})
    for key, piece in new_t.items():
        was = old_t.get(key)
        if was is not None and was.text == piece.text:
            second.append(ReplacementTransform(was, piece))
        elif was is not None:
            second += [FadeOut(was, shift=UP * 0.25), FadeIn(piece, shift=UP * 0.25, scale=1.4)]
        else:
            second.append(FadeIn(piece))
    for key, was in old_t.items():
        if key not in new_t:
            second.append(FadeOut(was))
    for name in ("count_heads", "left_count", "right_count", "verdict"):
        a, b = old.parts.get(name), new.parts.get(name)
        rest = lambda m, pieces: VGroup(*[x for x in m if x not in pieces]) if m is not None else None  # noqa: E731
        if name in ("left_count", "right_count"):      # the row's name ("before"/"after"); its numbers are above
            a, b = rest(a, set(old_t.values())), rest(b, set(new_t.values()))
        if a is not None and b is not None and name != "verdict":
            second.append(ReplacementTransform(a, b))
        elif name == "verdict" and b is not None:
            second += ([FadeOut(a, shift=DOWN * 0.2)] if a is not None else []) + [FadeIn(b, shift=DOWN * 0.2)]
        elif b is not None:
            second.append(FadeIn(b))
        elif a is not None:
            second.append(FadeOut(a))
    return [AnimationGroup(*first), AnimationGroup(*second, lag_ratio=0.08)] if second else [AnimationGroup(*first)]


def _reaction_targets(fig, event: dict) -> list:
    """What one voice-led hint lights: ``[(mobject, delay seconds)]`` (``reaction_hints.plan`` says when).

    Balls light one after another (a count you can follow), then the count they add up to."""
    kind, el, side = event.get("kind"), event.get("element"), event.get("side")
    balls = lambda s, e=None: [a["ball"] for a in fig.atom_balls if a["side"] == s and (e is None or a["element"] == e)]  # noqa: E731
    tally = lambda s, e: [fig.tally_pieces[(s, e)]] if (s, e) in fig.tally_pieces else []  # noqa: E731
    out: list = []

    def walk(mobs, start, step):
        out.extend((m, start + i * step) for i, m in enumerate(mobs))
        return start + len(mobs) * step

    if kind == "atoms" and el:
        for s in ("left", "right") if side is None else (side,):
            t = walk(balls(s, el), 0.0 if s == "left" or side else 0.55, 0.09)
            walk(tally(s, el), t, 0)
    elif kind == "tally" and el and side:
        walk(tally(side, el), walk(balls(side, el), 0.0, 0.14), 0)
    elif kind == "species" and 0 <= int(event.get("species", -1)) < len(fig.formula_labels):
        k = int(event["species"])
        walk([a["ball"] for a in fig.atom_balls if a["species"] == k], 0.0, 0.05)
        out.append((fig.formula_labels[k], 0.0))
    elif kind == "count":
        n = sum(1 for _ in fig.atom_balls) + len(fig.tally_pieces)
        step, t = min(0.22, 3.0 / max(1, n)), 0.0
        for el in fig.element_order:
            for s in ("left", "right"):
                t = walk(balls(s, el), t, step)
                t = walk(tally(s, el), t, step)
    elif kind == "front":
        out.extend((label, 0.0) for label, sp in zip(fig.formula_labels, fig.species_info) if sp["n"] > 1 or sp["unknown"])
    elif kind == "both":
        els = [el] if el else fig.element_order
        out.extend((fig.tally_pieces[(s, e)], 0.1 * j) for j, e in enumerate(els) for s in ("left", "right")
                   if (s, e) in fig.tally_pieces)
    return out


def shape(p: dict):
    """Points, sides, diagonals, angles and marks from ONE coordinate model (``longform/shape_figure.py``)."""
    from .shape_figure import build as build_shape  # noqa: PLC0415 - it imports this module
    return build_shape(p)


_MATERIAL = {"ice": "#DCEFF7", "wood": "#B98A57", "cork": "#C9A27A", "iron": "#8E99A6", "steel": "#8E99A6",
             "stone": "#9C9488", "plastic": "#E8C468", "wax": "#EFE3C0", "oil": "#E3B341", "gold": "#E2B93B",
             "aluminium": "#C3CBD3", "rubber": "#4F5862", "apple": "#D9574E", "egg": "#F1E6D2", "coin": "#C9A85A"}


def _fmt(value) -> str:
    if value is None:
        return ""
    return f"{value:g}" if abs(value - round(value)) > 1e-6 else str(int(round(value)))


def _seen(mob, opacity: float) -> None:
    """Show or hide a label or a line without filling the line in (``set_opacity`` would fill a bracket's corners)."""
    if isinstance(mob, Text):
        mob.set_fill(opacity=opacity)
    else:
        mob.set_stroke(opacity=opacity)


class _Settle(Animation):
    """Each object is let go just above the liquid and settles where its density puts it: a floater dips, bobs and
    rests with ``share`` of its height under the surface; a sinker goes down slowly to the floor. The liquid rises by
    what each one pushes aside. Stepped by alpha only (the runtime cuts it into the beat's stages), and every
    position is computed from the case, so the last frame is exactly the settled picture."""

    def __init__(self, group, plan, **kwargs):
        self.plan = plan
        super().__init__(group, **kwargs)

    def interpolate_mobject(self, alpha: float) -> None:
        plan, group = self.plan, self.mobject
        n = max(1, len(plan["objects"]))
        level = plan["level0"]
        for i, obj in enumerate(plan["objects"]):
            t = min(1.0, max(0.0, alpha * n - i))      # the objects go in one after another
            if t >= 1.0:
                bottom = obj["y_end"]
            elif obj["sinks"]:
                bottom = obj["y_start"] + (obj["y_end"] - obj["y_start"]) * smooth(t)
            else:
                bottom = obj["y_end"] + (obj["y_start"] - obj["y_end"]) * math.exp(-5.0 * t) * math.cos(2.6 * math.pi * t)
            group[obj["index"]].move_to([obj["x"], bottom + obj["side"] / 2, 0])
            show = 1.0 if t >= .92 else 0.0
            for j in obj["after"]:                       # what is computed (the bracket, "92 cm³ under") comes at rest
                _seen(group[j], show)
            submerged = min(obj["side"], max(0.0, obj["level_end"] - bottom))
            level += obj["side"] * submerged / plan["inner_w"]
        liquid = group[plan["liquid"]]
        height = max(.05, level - plan["floor"])
        liquid.stretch_to_fit_height(height)
        liquid.move_to([plan["cx"], plan["floor"] + height / 2, 0])
        group[plan["surface"]].move_to([plan["cx"], level, 0])


def float_figure(p: dict) -> Figure:
    """Objects in a tank of liquid, each sitting exactly as deep as its density says (``figure_math.float_case``).

    ``liquid`` {"name", "density"}; ``objects`` [{"name", "mass", "volume" | "density", "role"}] (up to three).
    Code draws the tank, the liquid and each object; works out its density and the share under the surface; and
    animates each one being let go and settling (a floater bobs to rest, a sinker goes to the floor) while the liquid
    rises by what it pushes aside. ``"show": "under"`` adds a bracket with the volume under the surface.
    Moves like a scene (``fig.animator``), so its steps take no focus.
    """
    case = figure_math.float_case(p)
    objs = case["objects"]
    if not objs:
        raise ValueError("a float figure needs at least one object with two of mass, volume and density")
    show_under = str(p.get("show", "under")).lower() != "none"
    inner_w, tank_h = 4.2, 2.5
    floor, cx = -tank_h / 2 - .35, 0.0
    level0 = floor + 1.25
    biggest = max(o["volume"] for o in objs)
    group, plan = VGroup(), {"objects": [], "inner_w": inner_w, "floor": floor, "cx": cx}
    left, right = cx - inner_w / 2, cx + inner_w / 2
    liquid = Rectangle(width=inner_w, height=level0 - floor, stroke_width=0, fill_color="#2E6F86", fill_opacity=.55)
    liquid.move_to([cx, (level0 + floor) / 2, 0])
    surface = Line([left, level0, 0], [right, level0, 0], color="#8FD0E6", stroke_width=3)
    walls = VMobject(color=INK, stroke_width=4).set_points_as_corners(
        [[left - .04, floor + tank_h, 0], [left - .04, floor - .04, 0], [right + .04, floor - .04, 0], [right + .04, floor + tank_h, 0]])
    name = Text(f"{case['liquid']['name']}  {case['liquid']['density']:.2f} g/cm³", font=FONT, font_size=20, color="#BFE3EF")
    name.move_to([cx, floor - .32, 0])
    plan["liquid"], plan["surface"] = 0, 1
    group.add(liquid, surface, walls, name)
    slots = [cx + (k - (len(objs) - 1) / 2) * inner_w / max(len(objs), 1) for k in range(len(objs))]
    level = level0
    sizes = [0.95 * (o["volume"] / biggest) ** (1 / 3) for o in objs]
    for o, side in zip(objs, sizes):                       # the surface every object ends under
        level += side * min(side, side * o["share"]) / inner_w
    for k, (o, side, x) in enumerate(zip(objs, sizes, slots)):
        colour = next((c for key, c in _MATERIAL.items() if key in o["name"].lower()), ROLES.get(o["role"], GIVEN))
        body = Square(side_length=side, stroke_color=INK, stroke_width=2, fill_color=colour, fill_opacity=.95)
        y_start = level0 + .3
        y_end = floor + .02 if o["sinks"] else level - o["share"] * side
        body.move_to([x, y_start + side / 2, 0])
        index = len(group)
        group.add(body)
        facts = f"{_fmt(o['mass'])} g, {_fmt(o['volume'])} cm³" if o["mass"] else f"{_fmt(o['volume'])} cm³"
        verdict = ("sinks" if o["sinks"] else "floats") + f", ρ = {o['density']:.2f}"
        under = f"{_fmt(o['under'])} cm³ under" if show_under and not o["sinks"] and o["share"] > .05 else ""
        lines = [Text(o["name"], font=FONT, font_size=22, color=INK), Text(facts, font=FONT, font_size=17, color=MUTED),
                 Text(verdict, font=FONT, font_size=17, color=WRONG if o["sinks"] else RESULT)]
        if under:
            lines.append(Text(under, font=FONT, font_size=17, color=RESULT))
        tag = VGroup(*lines).arrange(DOWN, buff=.06)
        room = inner_w / len(objs) - .15
        if tag.width > room:
            tag.scale_to_fit_width(room)
        tag.move_to([x, floor + tank_h + .15, 0], aligned_edge=DOWN)
        group.add(*lines[:2])
        after = list(range(len(group), len(group) + len(lines) - 2))      # worked out: shown once it is at rest
        group.add(*lines[2:])
        tags = []
        if under:
            under_h = o["share"] * side
            x_b = x + side / 2 + .1
            bracket = VMobject(color=RESULT, stroke_width=3).set_points_as_corners(
                [[x_b - .06, level, 0], [x_b, level, 0], [x_b, level - under_h, 0], [x_b - .06, level - under_h, 0]])
            after.append(len(group))
            group.add(bracket)
        plan["objects"].append({"index": index, "tags": tags, "after": after, "x": x, "side": side, "sinks": o["sinks"],
                                "y_start": y_start, "y_end": y_end, "level_end": level})
    plan["level0"] = level0
    for o in plan["objects"]:
        for j in o["after"]:
            _seen(group[j], 0.0)                        # the static picture is the moment before they are let go
    fig = Figure("float").stage("fade", tank=group)
    fig.case = case

    def animate(work, run_time):
        return _Settle(work, plan, run_time=run_time)
    # The same driver a scene uses: run on a copy where it was built, mirrored into the layout (runtime._start_motion).
    # The plan's coordinates are the unscaled ones, so the group is never rescaled here; the layout scales ``inner``.
    fig.inner, fig.origin, fig.animator = group, group.copy(), animate
    return fig


BUILDERS = {"shape": shape, "right_triangle": right_triangle, "number_line": number_line, "bars": bars, "circle": circle,
            "rectangle": rectangle, "graph": graph, "reaction": reaction, "scene": scene, "float": float_figure, "diagram": diagram, "picture": picture}


def build(figure: dict | None, crafted: bool = False):
    """The figure for a beat, or None when the request is not in the inventory.

    ``crafted`` (look ``craft``, S11): a speed-time graph (kind ``motion``) whose speeds are never negative starts its y axis at 0."""
    if not isinstance(figure, dict):
        return None
    kind = str(figure.get("kind", "")).strip()
    try:
        # A subject kit's figure (docs/engine/kits.md) when the built-in table has no entry for the kind.
        builder = BUILDERS.get(kind) or kits.builder_for(kind)
    except Exception as exc:  # noqa: BLE001 - a kit that cannot load costs its picture, never the chapter
        print(f"LESSON_NOTE: the kit builder for '{kind}' could not be loaded ({type(exc).__name__}: {str(exc)[:120]}); "
              "the previous picture stays", flush=True)
        return None
    if builder is None:
        return None
    try:
        params = figure.get("params") if isinstance(figure.get("params"), dict) else figure
        if crafted and kind == "motion":
            params = {**params, "zero_floor": True}
        return builder(params)
    except Exception as exc:  # noqa: BLE001 - a bad parameter set must not kill a chapter render
        # ... but it must be SAID: the beat then keeps the previous picture, and a wrong picture with no
        # message is how a renderer bug hid for a whole test render (a grid that never appeared, 2026-10-09).
        print(f"LESSON_NOTE: figure '{kind}' could not be built ({type(exc).__name__}: {str(exc)[:120]}); "
              "the previous picture stays", flush=True)
        return None
