"""The ``shape`` figure: points, sides, diagonals, angles and marks, drawn by code from ONE coordinate model.

Everything shown is computed by ``longform.geometry`` from the spec's points: an angle's arc and its value, whether two
sides really are equal or parallel before a tick or an arrow is drawn on them, whether the boundary is convex, concave,
crossed or collapsed. A spec cannot make the picture say something its coordinates do not (the quadrilaterals pack,
owner 2026-10-20: "coordinate geometry, angle labels, side lengths, intersection status and answer keys must come from
one geometry model").

What it can do, beyond a still drawing:
* ``panels``: two to four shapes side by side, each with its caption (a valid example beside a non-example);
* ``change_from``: the next beat's shape grows out of this one part by part (a vertex slides, a diagonal is drawn in,
  an angle's value rolls over), so a proof is BUILT in front of the learner rather than swapped;
* ``move``: a vertex travels through way-points while the voice speaks, angles and the verdict recomputed every frame
  (the convexity tipping point);
* ``hint_plan`` / ``hint_targets``: what the voice names ("side AB", "angle C", "the diagonals", "ABCD") lights up as
  it is said (``shape_hints``; ``runtime._start_hints`` plays it).
"""
from __future__ import annotations

import math
import re

import numpy as np
from manim import (DOWN, LEFT, ORIGIN, RIGHT, UP, Animation, AnimationGroup, Arc, Circle, Create, DashedLine, Dot,
                   FadeIn, FadeOut, Line, Polygon, Rectangle, ReplacementTransform, Sector, Text, VGroup, VMobject)

from . import geometry as G
from .figures import FONT, GIVEN, INK, MUTED, RESULT, UNKNOWN, WRONG, Figure

ROLE = {"given": GIVEN, "unknown": UNKNOWN, "result": RESULT, "wrong": WRONG, "muted": MUTED, "ink": INK}
#: Angle arcs that are equal share a colour; otherwise each vertex keeps its own, so "angle A" is always the same colour.
ANGLE_COLOURS = ["#F2C94C", "#80B1E7", "#56FAAA", "#E57A9E", "#C792EA", "#F2994A"]
BOX_W, BOX_H, BAND = 6.4, 4.0, 0.8          # scene units the model's frame is mapped into, and the words' band below it
GOLD = "#FFD166"


def _pt3(p) -> np.ndarray:
    return np.array([p[0], p[1], 0.0])


def _role(spec_item, default=INK):
    if isinstance(spec_item, dict):
        return ROLE.get(str(spec_item.get("role") or ""), default)
    return default


def _text(words, colour=INK, size=26):
    return Text(str(words), font=FONT, font_size=size, color=colour)


def _mark_line(mob, light=True, grow=0.0):
    """A part that lights by its stroke and does not grow when the voice names it (``runtime._start_hints``)."""
    for m in mob.get_family():
        m.lights_up = light
    mob.hint_grow = grow
    return mob


class Frame:
    """Model coordinates → scene coordinates, the same for every way-point a moving vertex passes."""

    def __init__(self, x0, y0, x1, y1, width=BOX_W, height=BOX_H):
        span_x, span_y = max(x1 - x0, 1e-6), max(y1 - y0, 1e-6)
        pad = 0.14 * max(span_x, span_y)
        self.x0, self.y0, self.x1, self.y1 = x0 - pad, y0 - pad, x1 + pad, y1 + pad
        self.s = min(width / (self.x1 - self.x0), height / (self.y1 - self.y0))
        self.cx, self.cy = (self.x0 + self.x1) / 2, (self.y0 + self.y1) / 2

    def __call__(self, p) -> np.ndarray:
        return np.array([(p[0] - self.cx) * self.s, (p[1] - self.cy) * self.s, 0.0])

    def rect(self) -> tuple[float, float]:
        return (self.x1 - self.x0) * self.s, (self.y1 - self.y0) * self.s


def frame_for(spec: dict, model: G.Model) -> Frame:
    pts = list(model.points.values())
    for path in (spec.get("move") or {}).values():
        pts += [p for p in (G._pt(q) for q in path) if p]
    for p in (spec.get("tests") or {}).values():
        q = G._pt(p)
        if q:
            pts.append(q)
    given = spec.get("frame")
    if isinstance(given, (list, tuple)) and len(given) == 4:
        x0, y0, x1, y1 = (float(v) for v in given)
        xs, ys = [x0, x1] + [p[0] for p in pts], [y0, y1] + [p[1] for p in pts]
    else:
        xs, ys = [p[0] for p in pts] or [0, 1], [p[1] for p in pts] or [0, 1]
    width = float(spec.get("_width") or BOX_W)
    height = float(spec.get("_height") or BOX_H)
    return Frame(min(xs), min(ys), max(xs), max(ys), width, height)


def _project(spec: dict, model: G.Model):
    """Points with a ``lift`` are drawn in an oblique view: the plane as a tilted sheet, a lifted point above it."""
    lift = spec.get("lift") or {}
    if not lift and spec.get("view") != "oblique":
        return None
    shown = {}
    for name, (x, y) in model.points.items():
        z = float(lift.get(name, 0.0))
        shown[name] = (x + 0.5 * y, 0.45 * y + z)
    return shown


# ── building ──────────────────────────────────────────────────────────────────────────────────────────────────────


def _away(point, centre, d=0.36):
    v = point - centre
    n = np.linalg.norm(v)
    if n < 1e-6:
        v, n = np.array([0.0, 1.0, 0.0]), 1.0
    return point + v / n * d


def _ticks(a, b, count, colour):
    mid, d = (a + b) / 2, b - a
    d = d / max(np.linalg.norm(d), 1e-6)
    n = np.array([-d[1], d[0], 0.0])
    group = VGroup()
    for k in range(count):
        off = (k - (count - 1) / 2) * 0.1
        c = mid + d * off
        group.add(Line(c - n * 0.13, c + n * 0.13, color=colour, stroke_width=4))
    return group


def _chevrons(a, b, count, colour, flip=False, along=0.0):
    mid, d = (a + b) / 2, b - a
    mid = mid + d / max(np.linalg.norm(d), 1e-6) * along
    d = d / max(np.linalg.norm(d), 1e-6)
    if flip:
        d = -d
    n = np.array([-d[1], d[0], 0.0])
    group = VGroup()
    for k in range(count):
        tip = mid + d * (0.12 + 0.13 * k - 0.065 * (count - 1))
        group.add(VMobject(color=colour, stroke_width=4).set_points_as_corners(
            [tip - d * 0.15 + n * 0.12, tip, tip - d * 0.15 - n * 0.12]))
    return group


def _arc(vertex, start, sweep, radius, colour, right=False):
    if right and abs(sweep - math.pi / 2) < 0.02:
        u = np.array([math.cos(start), math.sin(start), 0.0]) * radius * 0.75
        v = np.array([math.cos(start + sweep), math.sin(start + sweep), 0.0]) * radius * 0.75
        return VMobject(color=colour, stroke_width=4).set_points_as_corners([vertex + u, vertex + u + v, vertex + v])
    return Arc(radius=radius, start_angle=start, angle=sweep, arc_center=vertex, color=colour, stroke_width=4)


def _direction(a, b):
    return math.atan2(b[1] - a[1], b[0] - a[0])


def _clear_part(spec: dict, at: str, v, pos: dict, start: float, sweep: float) -> tuple[float, float]:
    """The widest stretch of an angle's sweep (offsets from ``start``) that no drawn segment from its vertex cuts."""
    cuts = []
    for item in list(spec.get("segments") or []) + list(spec.get("lines") or []):
        ends = item if isinstance(item, str) else (item or {}).get("ends", "")
        names = G.names(str(ends))
        if len(names) != 2 or at not in names:
            continue
        other = names[1] if names[0] == at else names[0]
        if other not in pos:
            continue
        rel = (_direction(v, pos[other]) - start) % (2 * math.pi)
        if 0.05 < rel < sweep - 0.05:
            cuts.append(rel)
    edges = [0.0] + sorted(cuts) + [sweep]
    return max(zip(edges, edges[1:]), key=lambda g: g[1] - g[0])



def draw(spec: dict, model: G.Model, T, fig: Figure, prefix: str = "", shown=None) -> dict:
    """Add one shape's parts to ``fig`` (named with ``prefix``). Returns what the hints need to know about it."""
    pos = {k: T(v) for k, v in (shown or model.points).items()}
    info = {"segments": {}, "angles": {}, "points": set(), "polygon": "".join(model.boundary), "prefix": prefix,
            "diagonals": [], "sides": [], "words": {}}
    poly = [pos[n] for n in model.boundary]
    centre = np.mean(poly, axis=0) if poly else np.mean(list(pos.values()), axis=0) if pos else ORIGIN
    st = model.status() if len(model.boundary) >= 3 else None
    roles = spec.get("roles") or {}
    P = lambda name: prefix + name  # noqa: E731

    # whole lines, under everything
    lines = VGroup()
    w, h = T.rect() if hasattr(T, "rect") else (BOX_W, BOX_H)
    for name in spec.get("lines") or []:
        seg = [pos.get(n) for n in G.names(name)[:2]]
        if any(x is None for x in seg):
            continue
        a, b = seg
        d = (b - a) / max(np.linalg.norm(b - a), 1e-6)
        reach = 2 * max(w, h)
        line = Line(a - d * reach, b + d * reach, color=MUTED, stroke_width=2, stroke_opacity=0.8)
        # clip to the frame's rectangle so a full line never runs over the words beside the picture
        line.put_start_and_end_on(*_clip(a - d * reach, b + d * reach, w / 2 + 0.2, h / 2 + 0.2))
        info["segments"]["line_" + name] = P("line_" + name)
        fig.parts[P("line_" + name)] = _mark_line(line)
        lines.add(line)
    if len(lines):
        fig.stage("draw", *lines)

    # filled regions (a triangle of a proof), then the shape's own fill
    fills = VGroup()
    for k, item in enumerate(spec.get("fills") or []):
        corners = [pos.get(n) for n in G.names(item.get("poly") if isinstance(item, dict) else item)]
        if len(corners) < 3 or any(x is None for x in corners):
            continue
        colour = _role(item, GIVEN)
        shade = Polygon(*corners, stroke_width=0, fill_color=colour, fill_opacity=0.22)
        shade.hint_grow, shade.lights_fill = 0.0, True        # named, it brightens in place; grown, it left the shape
        name = "fill_" + "".join(G.names(item.get("poly") if isinstance(item, dict) else item))
        fig.parts[P(name)] = shade
        info["segments"][name] = P(name)
        fills.add(shade)
    if len(poly) >= 3 and st and st["kind"] in ("convex", "concave") and spec.get("fill", True):
        body = Polygon(*poly, stroke_width=0, fill_color=INK, fill_opacity=0.06)
        fig.parts[P("body")] = body
        fills.add(body)
    if len(fills):
        fig.stage("fade", *fills)

    # the boundary, side by side
    sides = VGroup()
    for name in model.sides():
        a, b = (pos[n] for n in G.names(name))
        colour = ROLE.get(str(roles.get(name, "")), INK)
        side = _mark_line(Line(a, b, color=colour, stroke_width=5))
        fig.parts[P(name)] = side
        info["segments"][name] = P(name)
        info["sides"].append(name)
        sides.add(side)
    if len(sides):
        fig.stage("draw", *sides)

    # segments: diagonals, medians, midpoint joins
    segs = VGroup()
    for item in spec.get("segments") or []:
        name = "".join(G.names(item.get("ends") if isinstance(item, dict) else item)[:2])
        ends = [pos.get(n) for n in G.names(name)]
        if len(ends) != 2 or any(x is None for x in ends):
            continue
        colour = _role(item, GIVEN) if isinstance(item, dict) and item.get("role") else ROLE.get(str(roles.get(name, "")), GIVEN)
        dashed = isinstance(item, dict) and item.get("dashed")
        seg = (DashedLine(*ends, color=colour, stroke_width=4, dash_length=0.12) if dashed
               else Line(*ends, color=colour, stroke_width=4))
        _mark_line(seg)
        fig.parts[P(name)] = seg
        info["segments"][name] = P(name)
        if name in model.diagonals() or "".join(reversed(G.names(name))) in model.diagonals():
            info["diagonals"].append(name)
        segs.add(seg)
    if len(segs):
        fig.stage("draw", *segs)

    # crossing point of a crossed boundary
    if st and st["kind"] == "crossed" and spec.get("verdict"):
        (s1, s2) = st["cross"][0]
        a, b = (model.points[n] for n in G.names(s1))
        c, d = (model.points[n] for n in G.names(s2))
        m = G.line_meet(a, b, c, d)
        if m:
            ring = Circle(radius=0.17, color=WRONG, stroke_width=4).move_to(T(m) if not shown else pos.get("_", T(m)))
            fig.parts[P("crossing")] = ring
            info["segments"]["crossing"] = P("crossing")
            fig.stage("draw", ring)

    # angles
    equal_angles = [g for g in (spec.get("equal_angles") or []) if isinstance(g, (list, tuple))]
    group_of = {v: k for k, g in enumerate(equal_angles) for v in g}
    arcs = VGroup()
    values = VGroup()
    shown_values = spec.get("angle_values", True)
    rounded = {}
    inner = model.interior()
    if inner:
        rounded = round_to_total(inner, 180.0 * (len(inner) - 2))
    outside = {}                         # vertex -> direction its value was put in, outside the corner
    placed = []
    arc_mids = {}                        # vertex -> directions its drawn angle arcs open toward
    for k, item in enumerate(spec.get("angles") or []):
        a = model.angle(item)
        if not a:
            continue
        key = a["at"] if not (isinstance(item, dict) and item.get("from")) else f"{a['from']}{a['at']}{a['to']}"
        v = pos[a["at"]]
        p_, q_ = pos[a["from"]], pos[a["to"]]
        if a["at"] in inner and not (isinstance(item, dict) and item.get("from")):
            orient = 1.0 if G.signed_area(model.poly()) >= 0 else -1.0
            first, second = (q_, p_) if orient > 0 else (p_, q_)
            start = _direction(v, first)
            sweep = math.radians(a["value"])
        else:
            start, end = _direction(v, p_), _direction(v, q_)
            sweep = (end - start + math.pi) % (2 * math.pi) - math.pi
            if sweep < 0:
                start, sweep = end, -sweep
        near = min(np.linalg.norm(p_ - v), np.linalg.norm(q_ - v))
        radius = max(0.22, min(0.55, 0.32 * near))
        if a["reflex"]:
            radius *= 0.8
        if isinstance(item, dict) and item.get("radius"):
            radius = float(item["radius"])          # set by the author where arcs crowd one point (a tiling's corner)
        colour = ANGLE_COLOURS[group_of.get(a["at"], k) % len(ANGLE_COLOURS)] if not (isinstance(item, dict) and item.get("role")) \
            else _role(item)
        if a["reflex"]:
            colour = WRONG if not (isinstance(item, dict) and item.get("role")) else colour
        right = abs(a["value"] - 90) < 0.5
        arc = _arc(v, start, sweep, radius, colour, right=right and not a["reflex"])
        rings = VGroup(arc)
        for extra in range(group_of.get(a["at"], -1) + 1 if a["at"] in group_of else 0):
            if extra == 0:
                continue
            rings.add(Arc(radius=radius + 0.07 * extra, start_angle=start, angle=sweep, arc_center=v, color=colour,
                          stroke_width=3))
        _mark_line(rings)
        fig.parts[P("angle_" + key)] = rings
        info["angles"][key] = P("angle_" + key)
        info.setdefault("angle_geom", {})[key] = (v, start, sweep, radius, colour)
        arcs.add(rings)
        arc_mids.setdefault(a["at"], []).append((start + sweep / 2) % (2 * math.pi))
        show_value = (isinstance(item, dict) and item.get("value") not in (None, False)) or (
            shown_values and not (isinstance(item, dict) and item.get("value") is False))
        if show_value:
            if isinstance(item, dict) and isinstance(item.get("value"), str):
                words = item["value"]
            else:
                deg = rounded.get(a["at"], round(a["value"])) if key == a["at"] else round(a["value"])
                words = f"{deg:g}°"
                info.setdefault("angle_deg", {})[key] = deg          # what the voice has to say for the number to appear
            # a diagonal drawn from this vertex runs through the angle: the value goes in the wider of the two parts,
            # or the line crosses it (the probe's text-over-shape, seen on the first test render)
            lo, hi = _clear_part(spec, a["at"], v, pos, start, sweep)
            mid = start + (lo + hi) / 2
            label = _text(words, colour, 22)
            # far enough along the bisector that the words clear both sides, however narrow the angle
            half = math.hypot(label.width, label.height) / 2
            part = hi - lo
            fit = (half + 0.06) / max(math.sin(min(part, math.pi) / 2), 0.12)     # where the wedge is wide enough
            dist = max(radius + 0.12 + half, fit)
            along = np.array([math.cos(mid), math.sin(mid), 0.0])
            if not a["reflex"] and (fit > 0.42 * near or sweep < math.radians(45)):
                # Too narrow to hold its value: inside the wedge the value sat far from its corner, on another
                # angle's value (an arrowhead's 29° and 40° lay on each other near its dent). It goes just
                # OUTSIDE the corner, behind the vertex, and the vertex's name steps aside for it.
                label.move_to(v - (0.2 + half) * along)
                outside[a["at"]] = -along
            else:
                label.move_to(v + dist * along)
            placed.append((label, v, along, half, a["at"], a["reflex"], sweep))
            label.hint_grow = 0.18
            fig.parts[P("angle_" + key + "_value")] = label
            info["words"]["angle_" + key + "_value"] = P("angle_" + key + "_value")
            values.add(label)
    # Two values on each other (a narrow corner's value reaching across to the dent's): the narrower corner's
    # value goes outside its corner, as above.
    def _hit(m1, m2):
        return (min(m1.get_right()[0], m2.get_right()[0]) - max(m1.get_left()[0], m2.get_left()[0]) > 0.02 and
                min(m1.get_top()[1], m2.get_top()[1]) - max(m1.get_bottom()[1], m2.get_bottom()[1]) > 0.02)
    for i in range(len(placed)):
        for j in range(len(placed)):
            if i == j or not _hit(placed[i][0], placed[j][0]):
                continue
            label, v, along, half, at, reflex, sweep = placed[i]
            if reflex or at in outside or sweep > placed[j][6]:
                continue
            label.move_to(v - (0.2 + half) * along)
            outside[at] = -along
    _transfer_ghost(spec, fig, info, P)
    if len(arcs):
        fig.stage("draw", *arcs)

    # equal ticks and parallel arrows, only where the coordinates bear them out
    marks = VGroup()
    for k, group in enumerate(model.checked_marks("equal")):
        for name in group:
            a, b = (pos[n] for n in G.names(name))
            colour = ROLE.get(str(roles.get(name, "")), INK)
            t = _mark_line(_ticks(a, b, k + 1, colour), grow=0.0)
            fig.parts[P("ticks_" + name)] = t
            info["segments"]["ticks_" + name] = P("ticks_" + name)
            marks.add(t)
    for k, group in enumerate(model.checked_marks("parallel")):
        ref = None
        for name in group:
            a, b = (pos[n] for n in G.names(name))
            d = b - a
            flip = ref is not None and float(np.dot(d, ref)) < 0
            ref = d if ref is None else ref
            ticked = any(name in g or name[::-1] in g for g in model.checked_marks("equal"))
            c = _mark_line(_chevrons(a, b, k + 1, GIVEN, flip, along=0.42 if ticked else 0.0), grow=0.0)
            fig.parts[P("arrows_" + name)] = c
            info["segments"]["arrows_" + name] = P("arrows_" + name)
            marks.add(c)
    if len(marks):
        fig.stage("fade", *marks)
    if len(values):
        fig.stage("fade", *values)

    # points and their names
    named = set(model.boundary)
    for item in spec.get("segments") or []:
        named |= set(G.names(item.get("ends") if isinstance(item, dict) else item))
    for key in ("midpoints", "meet", "divide"):
        named |= set((spec.get(key) or {}).keys())
    named |= set(spec.get("show_points") or [])
    named -= set(spec.get("hide_points") or [])
    dots, labels = VGroup(), VGroup()
    label_dirs = spec.get("label_dirs") or {}
    for name in sorted(named):
        if name not in pos:
            continue
        p = pos[name]
        colour = ROLE.get(str((spec.get("point_roles") or {}).get(name, "")), INK)
        dot = Dot(p, radius=0.06, color=colour)
        dot.hint_grow = 0.9
        fig.parts[P("dot_" + name)] = dot
        if name in label_dirs:
            ang = math.radians(float(label_dirs[name]))
            gap = float((spec.get("label_gap") or {}).get(name, 0.34))
            place = p + gap * np.array([math.cos(ang), math.sin(ang), 0.0])
        elif name in model.boundary and len(poly) >= 3:
            k = model.boundary.index(name)
            before, after = pos[model.boundary[k - 1]], pos[model.boundary[(k + 1) % len(model.boundary)]]
            u = (p - before) / max(np.linalg.norm(p - before), 1e-6) + (p - after) / max(np.linalg.norm(p - after), 1e-6)
            if np.linalg.norm(u) < 1e-3:
                u = p - centre
            inside = Polygon(*poly).get_center()
            if st and st["kind"] == "concave" and name in st["reflex"]:
                u = -u                                      # the dent's name sits inside the dent's mouth, not on the fill
            if np.dot(u, p - inside) < 0 and not (st and st["kind"] == "concave" and name in st["reflex"]):
                u = -u
            place = p + u / max(np.linalg.norm(u), 1e-6) * 0.36
            if name in outside:
                # the corner's value sits where the name would: the name goes to the side of it, away from the shape
                w = outside[name]
                sides = [np.array([-w[1], w[0], 0.0]), np.array([w[1], -w[0], 0.0])]
                u = max(sides, key=lambda d: float(np.dot(d, p - inside)))
                place = p + u * 0.36 + w * 0.12
        else:
            place = _away(p, centre, 0.34)
            rays = []
            for item in list(spec.get("segments") or []) + [model.boundary[i] + model.boundary[(i + 1) % len(model.boundary)]
                                                           for i in range(len(model.boundary))]:
                ends = G.names(item.get("ends") if isinstance(item, dict) else item)
                if len(ends) != 2 or any(e not in pos for e in ends):
                    continue
                a_, b_ = pos[ends[0]], pos[ends[1]]
                ab = b_ - a_
                t = float(np.dot(p - a_, ab) / max(np.dot(ab, ab), 1e-9))
                if -1e-6 <= t <= 1 + 1e-6 and np.linalg.norm(a_ + t * ab - p) < 1e-3:
                    for e in (a_, b_):
                        if np.linalg.norm(e - p) > 1e-3:
                            rays.append(_direction(p, e))
            if len(rays) >= 2:
                # A point where lines meet (the diagonals' E) had its name put away from the middle of the shape,
                # which is where the diagonals run: the name sat on a diagonal. It goes in the widest gap instead.
                # one ray per direction: a segment listed twice (PQ inside side PR) made a zero gap, read as a full turn
                rays = sorted({round(r % (2 * math.pi), 6) for r in rays})
                gaps = [((rays[(i + 1) % len(rays)] - rays[i]) % (2 * math.pi) or 2 * math.pi, rays[i])
                        for i in range(len(rays))]
                # a gap that holds an angle's arc (the vertically opposite angles at E) is not free for the name
                taken = arc_mids.get(name, [])
                free = [g for g in gaps if not any((m - g[1]) % (2 * math.pi) < g[0] for m in taken)] or gaps
                width, start_ = max(free)
                ang = start_ + width / 2
                place = p + 0.34 * np.array([math.cos(ang), math.sin(ang), 0.0])
        label = _text(name, colour, 28).move_to(place)
        label.hint_grow = 0.3
        fig.parts[P(name)] = label
        info["points"].add(name)
        info["words"][name] = P(name)
        dots.add(dot)
        labels.add(label)
    if len(dots):
        fig.stage("fade", *dots)

    # test points (where can D go?): a tick or a cross worked out from the shape they would make
    tests = VGroup()
    for name, value in (spec.get("tests") or {}).items():
        q = G._pt(value)
        if not q or not model.boundary:
            continue
        trial = G.status(model.poly() + [q], model.boundary + [name])
        good = trial["kind"] in ("convex", "concave")
        p = T(q)
        mark = _text("✓" if good else "✗", RESULT if good else WRONG, 30).next_to(_pt3(p), UR_DIR, buff=0.05)
        tests.add(VGroup(Dot(p, radius=0.07, color=RESULT if good else WRONG), mark))
        fig.parts[P("test_" + name)] = tests[-1]
        info["segments"]["test_" + name] = P("test_" + name)
    if len(tests):
        fig.stage("fade", *tests)
    if len(labels):
        fig.stage("fade", *labels)
    info["status"] = st
    info["rounded"] = rounded
    info["midpoints"] = [m for m in (spec.get("midpoints") or {}) if m in pos]
    return info


UR_DIR = UP + RIGHT

#: Where in a beat's run (0 to 1) a transferred angle starts to turn and where it has landed (``transfer``, plan S10).
TRANSFER_WINDOW = (0.15, 0.80)


def angle_key(item) -> str:
    """The name an angle item has in ``info["angles"]``: its vertex, or ``<from><at><to>`` for an angle between two rays."""
    if isinstance(item, dict) and item.get("from"):
        return f"{item.get('from')}{item.get('at')}{item.get('to')}"
    return str(item.get("at") if isinstance(item, dict) else item or "")


def transfer_progress(alpha) -> float:
    """0 to 1 for a ``transfer`` at moment ``alpha`` of its beat: waits, turns (eased), then rests landed."""
    lo, hi = TRANSFER_WINDOW
    x = min(max((float(alpha) - lo) / (hi - lo), 0.0), 1.0)
    return x * x * (3 - 2 * x)


def _hide_landing(fig: Figure, spec: dict) -> None:
    """The built (still) picture of a ``transfer`` beat, as it first appears: the target angle's arc and number are not there yet."""
    move = spec.get("transfer")
    key = angle_key(move.get("to")) if isinstance(move, dict) else ""
    for name in ("angle_" + key, "angle_" + key + "_value"):
        mob = fig.parts.get(name)
        if mob is not None:
            mob.set_opacity(0)


def _transfer_ghost(spec: dict, fig: Figure, info: dict, P) -> None:
    """``transfer`` (plan S10): a copy of one angle's wedge makes a half turn about the middle of the line between its corner
    and the other angle's corner, and lands on that other angle (alternate angles: the picture of "equal, because they fit").
    Only while the figure is replaying a moment (``_t`` set by ``at_alpha``); a built, still picture has no ghost. Until the
    wedge has landed, the target's own arc and number are hidden: the number appears where the copy arrives."""
    move, t = spec.get("transfer"), spec.get("_t")
    if not isinstance(move, dict) or t is None:
        return
    geom = info.get("angle_geom") or {}
    src, dst = angle_key(move.get("from")), angle_key(move.get("to"))
    if src not in geom or dst not in geom or src == dst:
        return
    (v1, start, sweep, r1, colour), (v2, _, _, r2, _) = geom[src], geom[dst]
    p = transfer_progress(t)
    if p >= 1.0:
        return
    for name in ("angle_" + dst, "angle_" + dst + "_value"):
        mob = fig.parts.get(P(name))
        if mob is not None:
            mob.set_opacity(0)
    ghost = Sector(radius=r1 + (r2 - r1) * p, start_angle=start, angle=sweep, arc_center=v1, color=colour,
                   stroke_width=4, fill_opacity=0.4)
    ghost.rotate(math.pi * p, about_point=(v1 + v2) / 2)
    fig.parts[P("transfer")] = ghost
    fig.add(ghost)


def _clip(a, b, half_w, half_h):
    """Liang-Barsky: the part of segment ab inside the box |x| <= half_w, |y| <= half_h."""
    t0, t1 = 0.0, 1.0
    d = b - a
    for p, q in ((-d[0], a[0] + half_w), (d[0], half_w - a[0]), (-d[1], a[1] + half_h), (d[1], half_h - a[1])):
        if abs(p) < 1e-12:
            if q < 0:
                return a, a
            continue
        r = q / p
        if p < 0:
            t0 = max(t0, r)
        else:
            t1 = min(t1, r)
    return a + d * t0, a + d * t1


def round_to_total(values: dict, total: float) -> dict:
    """Whole degrees that add up to the rounded total (largest remainder), so a shown sum is never 359°."""
    floors = {k: math.floor(v) for k, v in values.items()}
    left = int(round(total)) - sum(floors.values())
    order = sorted(values, key=lambda k: values[k] - floors[k], reverse=True)
    for k in order[:max(0, left)]:
        floors[k] += 1
    return floors


def _band_words(spec: dict, model: G.Model, info: dict, colour=None):
    """The line under a shape: its caption, the verdict worked out from its points, or its angle sum."""
    bits = []
    st = info.get("status")
    verdict_words = ""
    if spec.get("verdict") and st:
        kind = st["kind"]
        verdict_words = spec.get("verdict") if isinstance(spec.get("verdict"), str) else G.VERDICT_WORDS.get(kind, kind)
    caption = str(spec.get("caption") or "").strip()
    # A caption that only says what the verdict under it says ("convex" over "convex") is said once (first
    # automatic pack lesson, 2026-10-25).
    if caption and not (verdict_words and caption.lower().rstrip(".") in str(verdict_words).lower()):
        bits.append((caption, colour or INK))
    if spec.get("verdict") and st:
        kind = st["kind"]
        words = spec.get("verdict") if isinstance(spec.get("verdict"), str) else G.VERDICT_WORDS.get(kind, kind)
        bits.append((words, RESULT if kind in ("convex",) else UNKNOWN if kind == "concave" else WRONG))
    if spec.get("angle_sum") and info.get("rounded"):
        r = info["rounded"]
        parts = " + ".join(f"{r[k]:g}°" for k in model.boundary)
        bits.append((f"{parts} = {sum(r.values()):g}°", RESULT))
    if spec.get("readout"):
        for name in spec["readout"]:
            if ":" in str(name):
                # a ratio of two lengths, worked out from the points ("AG:GD" stays 2 : 1 however the triangle moves)
                top, bottom = (model.length(n.strip()) for n in str(name).split(":", 1))
                if top and bottom:
                    left, right = (n.strip() for n in str(name).split(":", 1))
                    bits.append((f"{left} : {right} = {top / bottom:.2f} : 1", UNKNOWN))
                continue
            if len(G.names(str(name))) == 2 and model.length(str(name)):
                unit = str(spec.get("unit") or "")
                scale = float(spec.get("unit_scale") or 1.0)
                bits.append((f"{name} = {model.length(str(name)) * scale:.1f}{(' ' + unit) if unit else ''}", UNKNOWN))
                continue
            a = model.angle(name)
            if a:
                # the same whole degrees as the value at the arc (``round_to_total``), never one apart from it
                deg = (info.get("rounded") or {}).get(name, round(a["value"]))
                bits.append((f"∠{name} = {deg:g}°", WRONG if a["reflex"] else UNKNOWN))
    return bits


def build_single(spec: dict, fig: Figure, prefix: str = "", width=BOX_W, height=BOX_H, centre=ORIGIN):
    model = G.Model(spec)
    spec = dict(spec)
    spec["_width"], spec["_height"] = width, height
    T = frame_for(spec, model)
    shown = _project(spec, model)
    if shown:
        xs0, ys0 = [p[0] for p in model.points.values()], [p[1] for p in model.points.values()]
        sheet_pts = [shown[n] for n in model.points] + [(x + 0.5 * y, 0.45 * y) for x in (min(xs0) - .8, max(xs0) + .8)
                                                         for y in (min(ys0) - .8, max(ys0) + .8)]
        T = Frame(min(p[0] for p in sheet_pts), min(p[1] for p in sheet_pts), max(p[0] for p in sheet_pts),
                  max(p[1] for p in sheet_pts), width, height)
        # the plane: a light sheet under the shape (drawn first)
        xs, ys = [p[0] for p in model.points.values()], [p[1] for p in model.points.values()]
        pad = 0.8
        flat = [(min(xs) - pad, min(ys) - pad), (max(xs) + pad, min(ys) - pad), (max(xs) + pad, max(ys) + pad),
                (min(xs) - pad, max(ys) + pad)]
        corners = [(x + 0.5 * y, 0.45 * y) for (x, y) in flat]          # the plane's own rectangle, seen slanting
        sheet = Polygon(*[T(c) for c in corners], stroke_color=MUTED, stroke_width=1.5, fill_color=GIVEN, fill_opacity=0.08)
        fig.parts[prefix + "plane"] = sheet
        fig.stage("fade", sheet)
        for name, z in (spec.get("lift") or {}).items():
            if name in model.points:
                x, y = model.points[name]
                foot = T((x + 0.5 * y, 0.45 * y))
                drop = DashedLine(foot, T(shown[name]), color=MUTED, stroke_width=3, dash_length=0.1)
                shadow = Circle(radius=0.07, color=MUTED, stroke_width=2).move_to(foot)
                fig.parts[prefix + "drop_" + name] = VGroup(drop, shadow)
                fig.stage("draw", drop, shadow)
    box = Rectangle(width=T.rect()[0], height=T.rect()[1], stroke_opacity=0, fill_opacity=0).move_to(ORIGIN)
    fig.parts[prefix + "frame"] = box
    fig.add(box)
    info = draw(spec, model, T, fig, prefix, shown=shown)
    bits = _band_words(spec, model, info)
    # what the voice-led plan needs to know about the line under the shape (``shape_hints``, look ``values``)
    info["band_eq"] = bool((spec.get("angle_sum") and info.get("rounded")) or spec.get("readout"))
    info["band_verdict"] = bool(spec.get("verdict") and info.get("status"))
    info["band_total"] = sum(info["rounded"].values()) if spec.get("angle_sum") and info.get("rounded") else None
    band = VGroup()
    size = 26 if width > 4 else 22
    for k, (words, colour) in enumerate(bits):
        t = _text(words, colour, size)
        if t.width > width and " " in words:
            cut = words.split()
            half = max(1, len(cut) // 2)
            t = VGroup(_text(" ".join(cut[:half]), colour, size), _text(" ".join(cut[half:]), colour, size)).arrange(DOWN, buff=0.06)
        if t.width > width:
            t.scale_to_fit_width(width)
        band.add(t)
    if len(band):
        band.arrange(DOWN, buff=0.12).next_to(box, DOWN, buff=0.12)
        band.hint_grow = 0.08
        fig.parts[prefix + "band"] = band
        info["words"]["band"] = prefix + "band"
        fig.stage("fade", band)
    group_members = [m for m in fig.submobjects]
    info["model"] = model
    info["frame"] = T
    return info, group_members


class ShapeFigure(Figure):
    """A ``shape``: its parts by name, what the voice can point at, and how it becomes the next shape."""

    def change_from(self, old):
        return change_from(self, old)

    def hint_plan(self, sentences):
        from .shape_hints import plan  # noqa: PLC0415
        if getattr(self, "animator", None) is not None:
            return []                     # a moving picture is rebuilt every frame: nothing of it stays to light
        return plan(sentences, self.info, self.panel_info or None, bool(getattr(self, "values_spoken", False)))

    def buildable(self) -> set:
        """Parts that may wait for the words that name them (2026-10-21 review: the picture stood still for half of
        what was said, because a beat's figure arrived whole before its first word). The outline itself, its corners
        and the frame always come first: a diagonal, a midpoint, a shaded triangle, an angle's arc or the verdict
        under the shape can be drawn in when the voice gets to it."""
        keep = {"body", "frame"}
        for info in [self.info] if self.info else list(self.panel_info or []):
            ring = re.findall(r"[A-Z]\d*", str(info.get("polygon") or ""))
            prefix = str(info.get("prefix") or "")
            for k, p in enumerate(ring):
                q = ring[(k + 1) % len(ring)]
                keep |= {prefix + p, prefix + "dot_" + p, prefix + p + q, prefix + q + p}
        return {name for name in self.parts if name not in keep and not name.endswith("body") and not name.endswith("frame")}

    def hint_targets(self, event):
        out = []
        for k, name in enumerate(event.get("parts") or []):
            mob = self.parts.get(name)
            if mob is not None:
                out.append((mob, k * float(event.get("gap") or 0.0)))
        return out


def build(p: dict) -> Figure:
    fig = ShapeFigure("shape")
    fig.spec = p
    panels = p.get("panels")
    if isinstance(panels, list) and panels:
        n = len(panels)
        width = (BOX_W + 2.4) / n - 0.7
        fig.panel_info = []
        for i, sub in enumerate(panels):
            sub = dict(sub)
            before = set(id(m) for m in fig.submobjects)
            info, _ = build_single(sub, fig, prefix=f"p{i}_", width=width, height=BOX_H * (0.8 if n > 2 else 0.9))
            mine = [m for m in fig.submobjects if id(m) not in before]
            shift = RIGHT * ((i - (n - 1) / 2) * (width + 0.7))
            VGroup(*mine).shift(shift)
            info["caption"] = str(sub.get("caption") or "")
            info["key"] = str(sub.get("key") or sub.get("caption") or "").lower()
            fig.panel_info.append(info)
        fig.info = None
    else:
        info, _ = build_single(p, fig)
        fig.info = info
        fig.panel_info = []
        if p.get("transfer"):
            _hide_landing(fig, p)             # the picture that cross-fades in must not show the angle before the copy lands
        if p.get("move") or p.get("transfer"):
            _with_motion(fig, p)
            fig.voice_paced = p.get("pace") == "voice"      # video-quality plan S13: the motion goes on across the whole sentence
    return fig


# ── motion: a vertex travelling while the voice speaks ─────────────────────────────────────────────────────────────


class _Travel(Animation):
    """Rebuilds the shape every frame with the moving points where they are at this moment."""

    def __init__(self, holder, spec, frame, run_time):
        self.spec, self.frame = spec, frame
        super().__init__(holder, run_time=run_time)

    def interpolate_mobject(self, alpha: float) -> None:
        spec = at_alpha(self.spec, alpha)
        picture = Figure("shape")
        model = G.Model(spec)
        # the same invisible box ``build_single`` puts round the drawing, so this frame and the built figure
        # have the same extent and the runtime's mirror (``inner.width / origin.width``) keeps the scale
        w, h = self.frame.rect()
        picture.add(Rectangle(width=w, height=h, stroke_opacity=0, fill_opacity=0).move_to(ORIGIN))
        info = draw(spec, model, self.frame, picture)
        band = VGroup(*[_text(w, c, 26) for w, c in _band_words(spec, model, info)])
        if len(band):
            box_h = self.frame.rect()[1]
            band.arrange(DOWN, buff=0.12).move_to(DOWN * (box_h / 2 + 0.12 + band.height / 2))
            picture.add(band)
        if len(self.mobject.points):
            self.mobject.reset_points()
        self.mobject.submobjects = [picture]


def at_alpha(spec: dict, alpha: float) -> dict:
    """The spec with every moving point where it is at ``alpha`` (way-points reached in equal shares of the run)."""
    out = {k: v for k, v in spec.items() if k != "move"}
    if spec.get("transfer"):
        out["_t"] = min(max(float(alpha), 0.0), 1.0)         # how far the copied angle has come (``_transfer_ghost``)
    points = dict(spec.get("points") or {})
    for name, path in (spec.get("move") or {}).items():
        way = [points.get(name)] + list(path)
        way = [w for w in way if w is not None]
        if len(way) < 2:
            continue
        legs = len(way) - 1
        x = min(max(alpha, 0.0), 1.0) * legs
        if abs(x - round(x)) < 0.005:
            # the renderer rests a finished stage a hair before its end (``runtime.stage_progress``): a corner
            # meant to stop ON the line stopped 0.1% short, the readout said 180° and the verdict "convex"
            x = float(round(x))
        k = min(int(x), legs - 1)
        t = x - k
        a, b = way[k], way[k + 1]
        points[name] = [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t]
    out["points"] = points
    return out


def _with_motion(fig: Figure, spec: dict) -> None:
    """The drawing becomes ONE group the renderer replays frame by frame (``runtime._start_motion``), as a scene is."""
    model = G.Model(spec)
    frame = frame_for(dict(spec, _width=BOX_W, _height=BOX_H), model)
    origin = VGroup()
    _Travel(origin, spec, frame, 1.0).interpolate_mobject(0.0)
    inner = VGroup(*fig.submobjects)
    fig.submobjects = []
    fig.add(inner)
    fig.inner = inner
    fig.origin = origin
    fig.animator = lambda work, run_time: _Travel(work, spec, frame, run_time)


# ── one shape becoming the next ───────────────────────────────────────────────────────────────────────────────────


def change_from(new: Figure, old) -> list:
    """The next beat's shape grows out of this one: parts with the same name move to their new place (a vertex
    slides, a value rolls over), new parts are drawn in, parts that are gone fade. ``[]`` when ``old`` is another
    kind of picture; a moving picture (either side) cross-fades."""
    if getattr(old, "kind", None) != "shape":
        return []
    if getattr(old, "animator", None) is not None or getattr(new, "animator", None) is not None:
        # A moving picture is rebuilt every frame, so nothing in it can morph part by part; and a plain
        # Transform into it padded families and left a second "D" and a second readout on screen while the
        # vertex moved (first test film). It cross-fades instead.
        return [AnimationGroup(FadeOut(old), FadeIn(new))]
    return _morph(new, old)


def _morph(new: Figure, old) -> list:
    move, gone, come = [], [], []
    for name, mob in new.parts.items():
        was = old.parts.get(name)
        if was is not None:
            move.append(ReplacementTransform(was, mob))
        elif isinstance(mob, (Line, DashedLine, Arc, Polygon, Circle)) or (
                isinstance(mob, VGroup) and any(isinstance(m, (Line, Arc, VMobject)) and not isinstance(m, Text)
                                                for m in mob.submobjects) and not isinstance(mob, Text)):
            come.append(Create(mob))
        else:
            come.append(FadeIn(mob, scale=1.15))
    for name, mob in old.parts.items():
        if name not in new.parts:
            gone.append(FadeOut(mob))
    stages = []
    if move or gone:
        stages.append(AnimationGroup(*gone, *move))
    if come:
        stages.append(AnimationGroup(*come, lag_ratio=0.2))
    return stages
