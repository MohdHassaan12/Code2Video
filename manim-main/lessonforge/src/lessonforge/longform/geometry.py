"""One coordinate model for a plane-geometry picture (no Manim here, so it can be tested).

The quadrilaterals pack (owner, 2026-10-20) asks for it in so many words: "coordinate geometry, angle labels, side
lengths, intersection status and answer keys must come from one geometry model". Earlier the same day both a
model-written scene and the owner's drawing service drew a 35 degree angle as 55 and a Moon turning backwards. So a
picture of points, sides and angles is described by its POINTS only; every length, angle, verdict ("convex",
"sides cross"), midpoint and crossing point is computed here, and the figure (``figures.shape``), the voice-led
hints (``shape_hints``) and a lesson's answer keys all read it from this module.

A spec (``figure.kind == "shape"``)::

    {"points": {"A": [0, 0], "B": [4, 0], "C": [5, 3], "D": [1, 3]},
     "polygon": "ABCD",                      # the boundary, in order ("" for loose points and segments)
     "midpoints": {"P": "AB"},               # computed points
     "meet": {"E": ["AC", "BD"]},            # where two segments (or, failing that, their lines) cross
     "divide": {"G": ["A", "D", 0.6667]},    # the point a fraction of the way from A to D
     "segments": ["AC", {"ends": "BD", "dashed": true, "role": "given"}],
     "lines": ["AB"],                        # whole lines, drawn across the picture
     "angles": ["A", {"at": "E", "from": "A", "to": "B"}],   # interior angle at a polygon vertex, or between two rays
     "equal": [["AB", "CD"], ["AD", "BC"]],  # tick marks: dropped (and said) when the lengths are not equal
     "parallel": [["AB", "CD"]],             # arrow marks: dropped (and said) when the sides are not parallel
     "verdict": true,                        # "convex" / "concave" / "sides cross" / "three corners in a line"
     ...}
"""
from __future__ import annotations

import math
import re

EPS = 1e-9
#: How close two lengths (as a share of the larger) or two directions (degrees) must be to count as equal / parallel.
LENGTH_TOL = 0.02
ANGLE_TOL = 1.0


def _pt(value) -> tuple[float, float] | None:
    try:
        x, y = float(value[0]), float(value[1])
    except (TypeError, ValueError, IndexError, KeyError):
        return None
    if not (math.isfinite(x) and math.isfinite(y)):
        return None
    return (x, y)


def names(text) -> list[str]:
    """'ABCD' → ['A','B','C','D']; "A'B" → ["A'", 'B']; 'P1Q' → ['P1', 'Q']. A point name is a capital letter,
    optionally followed by digits and primes."""
    return re.findall(r"[A-Z]\d*'*", str(text or ""))


def sub(a, b):
    return (a[0] - b[0], a[1] - b[1])


def cross(o, a, b) -> float:
    """The z of (a - o) x (b - o): positive when o → a → b turns left."""
    return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])


def dist(a, b) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def midpoint(a, b):
    return ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)


def lerp(a, b, t):
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)


def direction(a, b) -> float:
    """The direction of the line through a and b, in degrees in [0, 180)."""
    return math.degrees(math.atan2(b[1] - a[1], b[0] - a[0])) % 180.0


def are_parallel(a, b, c, d, tol: float = ANGLE_TOL) -> bool:
    diff = abs(direction(a, b) - direction(c, d)) % 180.0
    return min(diff, 180.0 - diff) <= tol


def are_equal(x: float, y: float, tol: float = LENGTH_TOL) -> bool:
    return abs(x - y) <= tol * max(abs(x), abs(y), EPS)


def collinear(a, b, c, tol: float = 1e-6) -> bool:
    scale = max(dist(a, b), dist(b, c), dist(a, c), EPS)
    return abs(cross(a, b, c)) <= tol * scale * scale


def on_segment(p, a, b, tol: float = 1e-9) -> bool:
    return (min(a[0], b[0]) - tol <= p[0] <= max(a[0], b[0]) + tol and
            min(a[1], b[1]) - tol <= p[1] <= max(a[1], b[1]) + tol)


def segments_cross(a, b, c, d) -> bool:
    """True when segment ab and segment cd share a point (touching counts)."""
    d1, d2, d3, d4 = cross(c, d, a), cross(c, d, b), cross(a, b, c), cross(a, b, d)
    if ((d1 > EPS and d2 < -EPS) or (d1 < -EPS and d2 > EPS)) and ((d3 > EPS and d4 < -EPS) or (d3 < -EPS and d4 > EPS)):
        return True
    return ((abs(d1) <= EPS and on_segment(a, c, d)) or (abs(d2) <= EPS and on_segment(b, c, d)) or
            (abs(d3) <= EPS and on_segment(c, a, b)) or (abs(d4) <= EPS and on_segment(d, a, b)))


def line_meet(a, b, c, d):
    """Where line ab meets line cd, or None when they are parallel."""
    den = (a[0] - b[0]) * (c[1] - d[1]) - (a[1] - b[1]) * (c[0] - d[0])
    if abs(den) < EPS:
        return None
    t = ((a[0] - c[0]) * (c[1] - d[1]) - (a[1] - c[1]) * (c[0] - d[0])) / den
    return (a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1]))


def signed_area(poly: list) -> float:
    return sum(p[0] * q[1] - q[0] * p[1] for p, q in zip(poly, poly[1:] + poly[:1])) / 2.0


def ray_angle(vertex, p, q) -> float:
    """The (non-reflex) angle p-vertex-q in degrees, 0 to 180."""
    v1, v2 = sub(p, vertex), sub(q, vertex)
    n = math.hypot(*v1) * math.hypot(*v2)
    if n < EPS:
        return 0.0
    c = max(-1.0, min(1.0, (v1[0] * v2[0] + v1[1] * v2[1]) / n))
    return math.degrees(math.acos(c))


def interior_angles(poly: list) -> list[float]:
    """Interior angle at each vertex of a SIMPLE polygon, reflex angles included (they add to (n - 2) x 180)."""
    n = len(poly)
    orient = 1.0 if signed_area(poly) >= 0 else -1.0
    out = []
    for i in range(n):
        prev, here, nxt = poly[i - 1], poly[i], poly[(i + 1) % n]
        small = ray_angle(here, prev, nxt)
        turn = cross(prev, here, nxt) * orient          # > 0: a left turn on a counter-clockwise walk, a convex corner
        out.append(small if turn >= 0 else 360.0 - small)
    return out


def round_to_total(values: dict, total: float) -> dict:
    """Whole degrees that add up to the rounded total (largest remainder): the same numbers a ``shape`` figure writes at its
    arcs (``shape_figure.round_to_total`` is the same rule; this copy has no Manim, for the quiz check)."""
    floors = {k: math.floor(v) for k, v in values.items()}
    left = int(round(total)) - sum(floors.values())
    order = sorted(values, key=lambda k: values[k] - floors[k], reverse=True)
    for k in order[:max(0, left)]:
        floors[k] += 1
    return floors


def status(poly: list, labels: list[str] | None = None) -> dict:
    """What a closed boundary through these points is, with the reason a teacher would give.

    {"kind": "convex" | "concave" | "crossed" | "degenerate" | "too_few", "why": str, "reflex": [label],
     "cross": [(side, side)], "collinear": [label of the middle point]}"""
    labels = labels or [chr(65 + i) for i in range(len(poly))]
    n = len(poly)
    if n < 3:
        return {"kind": "too_few", "why": "fewer than three corners", "reflex": [], "cross": [], "collinear": []}
    flat = [labels[i] for i in range(n) if collinear(poly[i - 1], poly[i], poly[(i + 1) % n])]
    same = [labels[i] for i in range(n) for j in range(i + 1, n) if dist(poly[i], poly[j]) < 1e-9]
    if same or flat:
        mid = flat[0] if flat else same[0]
        k = labels.index(mid)
        trio = f"{labels[k - 1]}, {mid} and {labels[(k + 1) % n]}"
        return {"kind": "degenerate", "why": f"{trio} lie on one line, so the shape has collapsed",
                "reflex": [], "cross": [], "collinear": flat}
    crossings = []
    for i in range(n):
        for j in range(i + 1, n):
            if (j == i + 1) or (i == 0 and j == n - 1):
                continue                            # neighbouring sides share a corner: that is not a crossing
            if segments_cross(poly[i], poly[(i + 1) % n], poly[j], poly[(j + 1) % n]):
                crossings.append((labels[i] + labels[(i + 1) % n], labels[j] + labels[(j + 1) % n]))
    if crossings:
        a, b = crossings[0]
        return {"kind": "crossed", "why": f"side {a} crosses side {b}", "reflex": [], "cross": crossings, "collinear": []}
    angles = interior_angles(poly)
    reflex = [labels[i] for i, a in enumerate(angles) if a > 180.0 + 1e-6]
    if reflex:
        return {"kind": "concave", "why": f"the angle at {reflex[0]} is {angles[labels.index(reflex[0])]:.0f}°, more than 180°",
                "reflex": reflex, "cross": [], "collinear": []}
    return {"kind": "convex", "why": "every interior angle is less than 180°", "reflex": [], "cross": [], "collinear": []}


VERDICT_WORDS = {"convex": "convex", "concave": "concave (non-convex)", "crossed": "sides cross: not valid",
                 "degenerate": "collapsed: not valid", "too_few": "not a polygon"}


def _seg_name(item) -> str:
    if isinstance(item, dict):
        return str(item.get("ends") or item.get("name") or "")
    return str(item or "")


class Model:
    """Every point of a spec, given and computed, and what can be measured between them."""

    def __init__(self, spec: dict):
        self.spec = spec if isinstance(spec, dict) else {}
        self.notes: list[str] = []
        self.points: dict[str, tuple[float, float]] = {}
        for name, value in (self.spec.get("points") or {}).items():
            p = _pt(value)
            if p is None or not names(name) or names(name)[0] != name:
                self.notes.append(f"point {name!r} left out: not a capital-letter name with two numbers")
                continue
            self.points[name] = p
        for name, ends in (self.spec.get("midpoints") or {}).items():
            a, b = (names(ends) + [None, None])[:2]
            if a in self.points and b in self.points:
                self.points[name] = midpoint(self.points[a], self.points[b])
            else:
                self.notes.append(f"midpoint {name} of {ends!r} left out: unknown ends")
        for name, how in (self.spec.get("divide") or {}).items():
            try:
                a, b, t = how[0], how[1], float(how[2])
                self.points[name] = lerp(self.points[a], self.points[b], t)
            except (KeyError, IndexError, TypeError, ValueError):
                self.notes.append(f"point {name} left out: divide needs [from, to, fraction] of known points")
        for name, pair in (self.spec.get("meet") or {}).items():
            try:
                (a, b), (c, d) = names(pair[0]), names(pair[1])
                P = [self.points[k] for k in (a, b, c, d)]
            except (KeyError, IndexError, TypeError, ValueError):
                self.notes.append(f"crossing {name} left out: it needs two segments of known points")
                continue
            m = line_meet(*P)
            if m is None:
                self.notes.append(f"crossing {name} left out: {pair[0]} and {pair[1]} are parallel")
                continue
            self.points[name] = m
            inside = on_segment(m, P[0], P[1], 1e-6) and on_segment(m, P[2], P[3], 1e-6)
            if not inside:
                self.notes.append(f"{name} is where the LINES {pair[0]} and {pair[1]} meet: the segments themselves do not")
        self.boundary = [n for n in names(self.spec.get("polygon")) if n in self.points]

    # ── measurements ────────────────────────────────────────────────────────────────────────
    def seg(self, name):
        a, b = (names(name) + [None, None])[:2]
        if a not in self.points or b not in self.points:
            return None
        return self.points[a], self.points[b]

    def length(self, name) -> float | None:
        s = self.seg(name)
        return dist(*s) if s else None

    def poly(self) -> list:
        return [self.points[n] for n in self.boundary]

    def status(self) -> dict:
        return status(self.poly(), self.boundary)

    def interior(self) -> dict[str, float]:
        """Interior angle at each boundary vertex (reflex included), only for a simple boundary."""
        st = self.status()
        if st["kind"] not in ("convex", "concave"):
            return {}
        return dict(zip(self.boundary, interior_angles(self.poly())))

    def angle(self, item) -> dict | None:
        """{"at", "from", "to", "value", "reflex"}: an interior angle of the boundary, or the angle between two rays."""
        if isinstance(item, str):
            item = {"at": item}
        if not isinstance(item, dict):
            return None
        at = str(item.get("at") or "")
        if at not in self.points:
            return None
        if item.get("from") and item.get("to"):
            p, q = str(item["from"]), str(item["to"])
            if p not in self.points or q not in self.points:
                return None
            value = ray_angle(self.points[at], self.points[p], self.points[q])
            return {"at": at, "from": p, "to": q, "value": value, "reflex": False}
        if at not in self.boundary:
            return None
        k = self.boundary.index(at)
        p, q = self.boundary[k - 1], self.boundary[(k + 1) % len(self.boundary)]
        values = self.interior()
        if at not in values:                       # not a simple shape: the smaller angle between the two sides
            return {"at": at, "from": p, "to": q, "value": ray_angle(self.points[at], self.points[p], self.points[q]),
                    "reflex": False}
        return {"at": at, "from": p, "to": q, "value": values[at], "reflex": values[at] > 180.0 + 1e-6}

    def sides(self) -> list[str]:
        b = self.boundary
        return [b[i] + b[(i + 1) % len(b)] for i in range(len(b))] if len(b) >= 2 else []

    def diagonals(self) -> list[str]:
        b = self.boundary
        if len(b) < 4:
            return []
        return [b[i] + b[j] for i in range(len(b)) for j in range(i + 2, len(b)) if not (i == 0 and j == len(b) - 1)]

    def checked_marks(self, key: str) -> list[list[str]]:
        """``equal`` / ``parallel`` groups that the coordinates bear out; a group they do not is dropped and noted."""
        kept = []
        for group in self.spec.get(key) or []:
            group = [g for g in (group if isinstance(group, (list, tuple)) else [group]) if self.seg(g)]
            if len(group) < 2:
                continue
            if key == "equal":
                lengths = [self.length(g) for g in group]
                ok = all(are_equal(lengths[0], x) for x in lengths[1:])
            else:
                ok = all(are_parallel(*self.seg(group[0]), *self.seg(g)) for g in group[1:])
            if ok:
                kept.append(group)
            else:
                self.notes.append(f"{key} mark on {' and '.join(group)} dropped: the drawing does not bear it out")
        return kept

    def facts(self) -> dict:
        """Everything a lesson's words and answer keys may quote about this picture."""
        st = self.status() if len(self.boundary) >= 3 else None
        inner = self.interior()
        out = {"points": {k: [round(v[0], 4), round(v[1], 4)] for k, v in self.points.items()},
               "sides": {s: round(self.length(s), 4) for s in self.sides()},
               "diagonals": {d: round(self.length(d), 4) for d in self.diagonals()},
               "status": st, "angles": {k: round(v, 2) for k, v in inner.items()},
               "angle_sum": round(sum(inner.values()), 2) if inner else None}
        if len(self.boundary) == 4 and self.diagonals():
            (a, c), (b, d) = (names(x) for x in self.diagonals())
            pts = [self.points[k] for k in (a, c, b, d)]
            meet = line_meet(*pts)
            out["diagonals_meet_inside"] = bool(segments_cross(*pts))
            out["diagonals_meet_at"] = [round(meet[0], 4), round(meet[1], 4)] if meet else None
        return out


def parallelogram_tests(model: Model) -> dict:
    """Which of the five parallelogram tests the drawing satisfies (for ABCD in boundary order)."""
    b = model.boundary
    if len(b) != 4:
        return {}
    A, B, C, D = (model.points[k] for k in b)
    ab, bc, cd, da = (b[0] + b[1], b[1] + b[2], b[2] + b[3], b[3] + b[0])
    L = model.length
    ang = model.interior()
    out = {
        "both_pairs_parallel": are_parallel(A, B, D, C) and are_parallel(A, D, B, C),
        "both_pairs_equal": are_equal(L(ab), L(cd)) and are_equal(L(bc), L(da)),
        "opposite_angles_equal": bool(ang) and abs(ang[b[0]] - ang[b[2]]) < ANGLE_TOL and abs(ang[b[1]] - ang[b[3]]) < ANGLE_TOL,
        "one_pair_equal_and_parallel": (are_parallel(A, B, D, C) and are_equal(L(ab), L(cd))) or
                                       (are_parallel(A, D, B, C) and are_equal(L(bc), L(da))),
    }
    meet = line_meet(A, C, B, D)
    out["diagonals_bisect"] = bool(meet) and are_equal(dist(A, meet), dist(C, meet)) and are_equal(dist(B, meet), dist(D, meet))
    return out


# ── a corner dragged round a triangle (video-quality plan S10; the spec key ``drag``) ─────────────────────────────────

#: Where a dragged corner goes, as (along the base, height), both in base lengths from the first base corner: a wide
#: triangle leaning left, a right angle at the first base corner, a tall narrow one, a wide one leaning right. Then it
#: goes home. Every stop and every point between two stops is a triangle whose smallest angle is at least ``DRAG_MIN``.
DRAG_TOUR = ((-0.30, 0.50), (0.0, 0.70), (0.90, 1.10), (1.25, 0.50))
DRAG_MIN = 15.0


def drag_path(points: dict, polygon, mover: str) -> list[list[float]] | None:
    """The way-points for ``mover``, a corner of a triangle, that show the angles changing and their sum staying put.

    The other two corners stay; the mover visits ``DRAG_TOUR`` on its own side of the base and then returns to where it
    began, in whole straight legs (the same legs ``shape_figure.at_alpha`` walks). ``None`` when this is not a triangle
    with that corner, or the triangle has no area (nothing to drag). Pure: the same points give the same path."""
    ring = names(polygon)
    if len(ring) != 3 or mover not in ring:
        return None
    pts = {n: _pt(points.get(n)) for n in ring}
    if any(p is None for p in pts.values()):
        return None
    base_a, base_b = (pts[n] for n in ring if n != mover)
    here = pts[mover]
    length = dist(base_a, base_b)
    if length < 1e-6:
        return None
    u = ((base_b[0] - base_a[0]) / length, (base_b[1] - base_a[1]) / length)
    n = (-u[1], u[0])
    side = (here[0] - base_a[0]) * n[0] + (here[1] - base_a[1]) * n[1]
    if abs(side) < 1e-6 * length:
        return None
    sign = 1.0 if side > 0 else -1.0
    path = [[round(base_a[0] + (s * u[0] + sign * h * n[0]) * length, 4),
             round(base_a[1] + (s * u[1] + sign * h * n[1]) * length, 4)] for s, h in DRAG_TOUR]
    path.append([round(here[0], 4), round(here[1], 4)])
    return path


def transfer_fault(model: Model, move) -> str | None:
    """Why a ``transfer`` (a copy of one angle turned half a turn about the middle of the line between two corners) does NOT land
    on the angle it says, or ``None`` when it does (so the picture says "equal, because they fit" only when they fit).

    ``move`` is ``{"from": <angle>, "to": <angle>}``, each an angle as ``Model.angle`` takes it (a corner, or
    ``{"at", "from", "to"}``). Half a turn keeps an angle's size and turns each ray the opposite way, so the angle lands exactly
    when the two corners' rays are opposite, pair by pair (alternate angles between parallel lines are such a pair)."""
    if not isinstance(move, dict):
        return "transfer must be {\"from\": <an angle>, \"to\": <an angle>}"
    a, b = model.angle(move.get("from")), model.angle(move.get("to"))
    if not a or not b:
        return "transfer names an angle that is not in the picture"
    if a["at"] == b["at"]:
        return "transfer needs two angles at different corners"

    def rays(x):
        v = model.points[x["at"]]
        return [direction_deg(v, model.points[x["from"]]), direction_deg(v, model.points[x["to"]])]
    mine, theirs = [(r + 180.0) % 360.0 for r in rays(a)], rays(b)

    def same(u, w):
        d = abs(u - w) % 360.0
        return min(d, 360.0 - d) <= ANGLE_TOL
    if not ((same(mine[0], theirs[0]) and same(mine[1], theirs[1])) or (same(mine[0], theirs[1]) and same(mine[1], theirs[0]))):
        return (f"the copy of angle {a['at']} does not land on angle {b['at']}: half a turn about the middle of "
                f"{a['at']}{b['at']} turns its sides to the opposite directions, and those are not the sides of angle {b['at']}")
    return None


def direction_deg(a, b) -> float:
    """The direction from a to b in degrees in [0, 360)."""
    return math.degrees(math.atan2(b[1] - a[1], b[0] - a[0])) % 360.0
