"""Unit 9: tiling the plane with any quadrilateral. The pack has only a production brief; the outcome was agreed with
the owner: any quadrilateral tiles the plane, because its four angles add to 360 degrees.

The brief suggests a half turn about the midpoint of a DIAGONAL; that copy lands on top of the first tile instead of
beside it, so the standard construction is used: a half turn about the midpoint of a SIDE. Two half turns about the
midpoints of neighbouring sides make a slide by a diagonal, so every tile below is the shape itself or its half-turned
copy, slid by whole steps of AC and BD (worked out here, never drawn by hand)."""
import math
import sys
from common import B, C, Q, S, lesson, write
from lessonforge.longform import geometry as G

Q4 = {"A": [0.0, 0.0], "B": [3.4, 0.5], "C": [3.0, 2.7], "D": [0.6, 1.8]}
DART = {"A": [0.0, 0.0], "B": [3.0, 0.3], "C": [3.4, 2.6], "D": [1.9, 1.15]}
F1 = [-0.6, -0.6, 7.0, 3.8]


def add(p, q):
    return [p[0] + q[0], p[1] + q[1]]


def turned(shape, centre):
    """The half turn of every corner about ``centre``."""
    return {k: [2 * centre[0] - x, 2 * centre[1] - y] for k, (x, y) in shape.items()}


def tiles(shape, window, reach=4):
    """Every tile (the shape and its half-turned copy about the midpoint of BC, slid by i·AC + j·BD) whose centre
    lies inside ``window`` = [x0, y0, x1, y1]. Returns a list of (kind, {corner: point})."""
    A, Bp, Cp, D = (shape[k] for k in "ABCD")
    u = [Cp[0] - A[0], Cp[1] - A[1]]
    v = [D[0] - Bp[0], D[1] - Bp[1]]
    copy = turned(shape, G.midpoint(Bp, Cp))
    out = []
    for i in range(-reach, reach + 1):
        for j in range(-reach, reach + 1):
            t = [i * u[0] + j * v[0], i * u[1] + j * v[1]]
            for kind, base in (("first", shape), ("turned", copy)):
                moved = {k: add(p, t) for k, p in base.items()}
                cx = sum(p[0] for p in moved.values()) / 4
                cy = sum(p[1] for p in moved.values()) / 4
                if window[0] <= cx <= window[2] and window[1] <= cy <= window[3]:
                    out.append((kind, moved))
    return out


def tiling(shape, window, frame, keep=True, hide_own=False, **more):
    """A ``shape`` spec of the tiling: ABCD itself named, every other tile filled and outlined with hidden points."""
    pts, fills, segs, hidden, seen = dict(shape), [], [], [], set()
    n = 0
    for kind, corners in tiles(shape, window):
        if all(abs(corners[k][0] - shape[k][0]) < 1e-9 and abs(corners[k][1] - shape[k][1]) < 1e-9 for k in "ABCD"):
            continue
        n += 1
        names = {k: f"{'WXYZ'['ABCD'.index(k)]}{n}" for k in "ABCD"}
        for k, p in corners.items():
            pts[names[k]] = p
            hidden.append(names[k])
        ring = "".join(names[k] for k in "ABCD")
        fills.append({"poly": ring, "role": "given" if kind == "first" else "result"})
        for a, b in zip("ABCD", "BCDA"):
            key = tuple(sorted((tuple(round(c, 6) for c in corners[a]), tuple(round(c, 6) for c in corners[b]))))
            if key not in seen:
                seen.add(key)
                segs.append({"ends": names[a] + names[b], "role": "muted"})
    spec = {"kind": "shape", "points": pts, "polygon": "ABCD", "fills": fills, "segments": segs,
            "hide_points": hidden + (list("ABCD") if hide_own else []), "frame": frame,
            "label_dirs": INSIDE, "fill": keep}
    spec.update(more)
    return spec


# names inside the first tile, where no other tile's edge runs
INSIDE = {"C": 235}


# the half turn about M, the midpoint of BC, in eight steps of 22.5 degrees
M = G.midpoint(Q4["B"], Q4["C"])


def spun(p, deg):
    a = math.radians(deg)
    x, y = p[0] - M[0], p[1] - M[1]
    return [M[0] + x * math.cos(a) - y * math.sin(a), M[1] + x * math.sin(a) + y * math.cos(a)]


COPY = {k + "1": p for k, p in turned(Q4, M).items()}            # A1 B1 C1 D1: the copy where it ends
# three resting way-points first: the copy stays on the tile while "Mark M" is said and turns with "turn it"
TURN = {k + "1": [Q4[k]] * 3 + [spun(Q4[k], d) for d in range(0, 181, 30)][1:] for k in "ABCD"}
assert all(abs(TURN[k][-1][0] - COPY[k][0]) < 1e-9 for k in COPY)


def pair(points_copy, frame=F1, **more):
    pts = dict(Q4, **points_copy)
    spec = {"kind": "shape", "points": pts, "polygon": "ABCD", "fills": [{"poly": "A1B1C1D1", "role": "result"}],
            "segments": [{"ends": e, "role": "result"} for e in ("A1B1", "B1C1", "C1D1", "D1A1")],
            "hide_points": ["B1", "C1"], "frame": frame}
    spec.update(more)
    return spec


# the corner C in the tiling: the four tiles that meet there, and their angles (one of each corner of ABCD)
A, Bq, Cq, D = (Q4[k] for k in "ABCD")
CORNER = dict(Q4, E=[Bq[0] + Cq[0] - A[0], Bq[1] + Cq[1] - A[1]], H=[Cq[0] + D[0] - A[0], Cq[1] + D[1] - A[1]])
WIN = [-2.6, -1.4, 6.0, 4.2]
FRAME = [-2.2, -1.2, 5.8, 4.0]
# one colour each and a larger arc: the four corners must read as four different angles, not one ring
ANG = [{"at": "C", "from": "D", "to": "B", "value": True, "radius": 0.4},
       {"at": "C", "from": "B", "to": "E", "value": True, "radius": 0.4},
       {"at": "C", "from": "E", "to": "H", "value": True, "radius": 0.4},
       {"at": "C", "from": "H", "to": "D", "value": True, "radius": 0.4}]
PLAIN = [dict(a, value=False) for a in ANG]
m = G.Model({"points": CORNER, "polygon": "ABCD"})
inner = m.interior()
total = sum(G.ray_angle(CORNER["C"], CORNER[a["from"]], CORNER[a["to"]]) for a in ANG)
assert abs(total - 360) < 1e-6, total
assert abs(sum(inner.values()) - 360) < 1e-6
SUMS = {"angles": PLAIN}
ADDED = " + ".join(f"{round(inner[k])}°" for k in "ABCD") + " = 360°"
assert sum(round(inner[k]) for k in "ABCD") == 360, ADDED


def around(**more):
    spec = tiling(Q4, WIN, FRAME)
    spec["points"].update({"E": CORNER["E"], "H": CORNER["H"]})
    spec["hide_points"] = spec["hide_points"] + ["E", "H"] + list(more.pop("hide", []))
    if more.get("angles"):
        spec["label_gap"] = {"C": 0.64}                  # the name clears the four arcs around C
    spec.update(more)
    return spec


ch1 = C(1, "PREDICT", "Predict whether an irregular quadrilateral can cover a floor with no gaps", [
    B("01", "Floors are often covered with square or rectangular tiles. Copies of a rectangle fit together "
            "with no gaps and no overlaps. Here is a different tile, ABCD. No two sides are equal and no two "
            "sides are parallel.",
      {"kind": "shape", "points": Q4, "polygon": "ABCD", "frame": F1},
      [S("Copies of a rectangle fit together", "Rectangles tile a floor"),
       S("Here is a different tile, ABCD", "Tile ABCD", "key"),
       S("No two sides are equal", "No equal sides, no parallel sides")]),
    B("02", "Predict first. If we use only copies of this tile, turned around but never cut, can they cover "
            "a whole floor with no gaps?",
      {"kind": "shape", "points": Q4, "polygon": "ABCD", "frame": F1},
      [S("Predict first", "Predict"),
       S("turned around but never cut", "Copies may turn, never be cut"),
       S("can they cover a whole floor with no gaps", "No gaps, no overlaps?", "key")],
      Q("Can copies of this irregular quadrilateral cover a floor with no gaps or overlaps?",
        ["Yes, always", "No, there will be gaps", "Only if we cut some copies"], 0,
        ["That is the prediction. Now let us build the floor and see why.",
         "Many people guess that, since the tile is irregular. Watch the construction before deciding.",
         "No cutting is needed. Watch what a half turn does."], kind="predict"), pause=8),
])

ch2 = C(2, "THE HALF TURN", "Make a matching copy with a half turn about the midpoint of a side", [
    B("03", "Mark M, the midpoint of side BC. Now take a copy of the tile and turn it half way round, "
            "through one hundred and eighty degrees, about M.",
      pair({k: Q4[k[0]] for k in COPY}, midpoints={"M": "BC"}, move=TURN,
           hide_points=["A1", "B1", "C1", "D1"]),
      [S("Mark M, the midpoint of side BC", "M: midpoint of BC", "key"),
       S("turn it half way round", "Half turn: 180° about M", "key"),
       S("about M", "The copy turns about M")]),
    B("04", "Look where the copy lands. B and C swap places, so the copy's side lands exactly on BC. "
            "Same length, so the two tiles share that side, with no gap and no overlap.",
      pair(COPY, midpoints={"M": "BC"}, hide_points=["A1", "B1", "C1", "D1"], roles={"BC": "given"}),
      [S("B and C swap places", "B and C swap places"),
       S("the copy's side lands exactly on BC", "The copy's side lands on BC", "key"),
       S("with no gap and no overlap", "No gap, no overlap")]),
    B("05", "We can do this for every side of every tile: turn a copy about the midpoint of that side. "
            "Keep going, and the copies spread out across the floor.",
      tiling(Q4, WIN, FRAME),
      [S("for every side of every tile", "Half turn about each side's midpoint"),
       S("the copies spread out across the floor", "The tiles cover the floor", "key")]),
])

ch3 = C(3, "WHY THERE ARE NO GAPS", "Explain the fit with the angle sum of 360 degrees", [
    B("06", "Sides match, but what about the corners? Look at the point C. Four tiles meet there. "
            "Which angles of ABCD fill the space around it?",
      around(),
      [S("what about the corners", "And the corners?"),
       S("Four tiles meet there", "Four tiles meet at C", "key"),
       S("Which angles of ABCD fill the space around it", "Which angles meet at C?", "key")],
      Q("Four tiles meet at the point C. Which angles of ABCD are around it?",
        ["One of each: A, B, C and D", "Four copies of angle C", "Two of C and two of A"], 0,
        ["Yes. Each tile brings a different corner, so A, B, C and D each appear once.",
         "Look at the four tiles again: each one touches C at a different corner.",
         "Count the corners again: each tile touches C with a different one."], kind="spot"), pause=8),
    B("07", "One of each. The four angles of ABCD meet at C, and the four angles of any quadrilateral add "
            "up to three hundred and sixty degrees. That is exactly a full turn, so the corners close up "
            "with no gap.",
      around(**SUMS),
      [S("The four angles of ABCD meet at C", "A, B, C, D meet at C", "key"),
       S("add up to three hundred and sixty degrees", ADDED, "key"),
       S("That is exactly a full turn", "A full turn is 360°", "key"),
       S("with no gap", "No gap at any corner")]),
    B("08", "Try it with numbers. Three of the angles meeting at a point are seventy, ninety-five and one hundred "
            "and ten degrees. What must the fourth angle be?",
      around(angles=PLAIN),
      [S("seventy, ninety-five and one hundred and ten degrees", "70°, 95°, 110°"),
       S("What must the fourth angle be", "Fourth angle = ?", "key")],
      Q("At a point of the tiling, three angles are 70°, 95° and 110°. What is the fourth?",
        ["85°", "95°", "180°"], 0,
        ["Yes. 70 + 95 + 110 = 275, and 360 − 275 = 85°.",
         "The fourth corner is a different angle of the tile. Use the full turn: 360 minus the three.",
         "180° is a straight line. Around a point the angles make a full turn, 360°."]), pause=9),
    B("09", "Eighty-five degrees. Seventy plus ninety-five plus one hundred and ten is two hundred and "
            "seventy-five, and three hundred and sixty take away two hundred and seventy-five is eighty-five.",
      around(angles=PLAIN),
      [S("two hundred and seventy-five", "70 + 95 + 110 = 275°"),
       S("is eighty-five", "360 − 275 = 85°", "key")]),
])

ch4 = C(4, "EVERY QUADRILATERAL", "See that the same construction works for a concave tile, and state the limit", [
    B("10", "This works for a concave tile too, like this arrowhead shape. The half turns about the side "
            "midpoints still fit, because its four angles still add to three hundred and sixty degrees.",
      tiling(DART, [-1.6, -0.8, 5.2, 3.6], [-1.6, -1.0, 5.6, 3.8], hide_own=True),
      [S("a concave tile too", "A concave tile"),
       S("The half turns about the side midpoints still fit", "Half turns still fit", "key"),
       S("its four angles still add to three hundred and sixty", "Angles still add to 360°")]),
    B("11", "There is one limit. The tile must be a true quadrilateral, so its sides must not cross. "
            "A crossed shape is not a quadrilateral, and it cannot tile like this.",
      {"kind": "shape", "points": {"A": [0, 0], "B": [3, 1.6], "C": [3, 0], "D": [0, 1.6]}, "polygon": "ABCD",
       "verdict": True, "frame": [-0.6, -0.6, 3.6, 2.2]},
      [S("its sides must not cross", "The sides must not cross", "key"),
       S("A crossed shape is not a quadrilateral", "Crossed: not a quadrilateral")]),
])

ch5 = C(5, "IN SHORT", "Recall why any quadrilateral tiles the plane", [
    B("12", "So, any quadrilateral can tile a floor. Turn a copy half way round about the midpoint of a side, "
            "and the sides match. At every corner the four angles meet, one of each, and since they add to "
            "three hundred and sixty degrees, they close up with no gap.",
      around(**SUMS),
      [S("any quadrilateral can tile a floor", "Any quadrilateral tiles the plane", "key"),
       S("about the midpoint of a side", "Half turn about a side's midpoint"),
       S("the four angles meet, one of each", "At each corner: A, B, C, D once"),
       S("they add to three hundred and sixty degrees", "Sum 360°: no gap", "key")]),
], role="recap")

L = lesson("Quadrilaterals 9: tiling the plane with any quadrilateral", [ch1, ch2, ch3, ch4, ch5])
if __name__ == "__main__":
    write(L, sys.argv[1] if len(sys.argv) > 1 else "/home/user/lfhome/drafts/quad_u9.json")
