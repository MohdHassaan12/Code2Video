"""What a teacher's hand ADDS to a drawing while talking: the annotation harness on top of a drawing's SVG.

The owner, 2026-10-12, of a lesson on reflection whose voice says thirty, forty and fifty degrees over one drawing that
prints only the letters i and r: "the visual is not matching audio … we can't able to see the 30 deg 40 deg", then:
"the image is not being annotated; there should be an annotation harness on top of the SVG which will ideate the
annotations, not just stale text", and: "it should be intelligent enough to update and change so it is not giving bad
annotations or overlapping things; … based on the current image SVG reference and minimal inputs, and also the starting
and ending time stamps for synchrony; … extendable for any topics; come up with generalized frameworks."
Measured that day on six lessons: of 39 values the voice says, 37 are not in the picture.

THE FRAMEWORK. Its inputs are a drawing's SVG (as ``sequence.json``: its parts, their outlines, its printed words) and
the lesson's words with the moments its lines come up. Nothing about any topic.

1. IDEATE (``ideate``): a model that sees the drawing with its things tagged and reads the words lists every value the
   voice says about the picture and WHAT MEASURES IT, and what the hand does besides (ring, trace, point, cross …).
   It names things by their tags and quotes the words a mark comes with. It never names a place.
2. KEEP IT HONEST (``honest``): code keeps an idea only when it can stand behind it: a mark of a kind it knows, on
   things that are on the board by then, a written NUMBER that the voice says in that beat, words that are in the
   narration. A value the voice gives for a mark the drawing plan has not drawn yet makes the hand draw it then.
3. PLACE (``KINDS``; each kind brings its own ``place``): where a mark goes is worked out from the drawing's own
   geometry and from what STANDS ON THE BOARD AT THAT MOMENT (``Board.write`` tries the places round a thing, takes the
   clearest, and writes further off with a leader line when every near place is taken).
4. CHECK AND CHANGE (``problems``, ``improve``): code measures what is wrong with the result (writing on writing, on
   the drawing's ink, outside the picture); then the model LOOKS at its own annotated drawing, mark by mark, and what it
   calls wrong is moved to the thing it names or dropped. A change is kept only when code finds no more wrong than before.
5. TIME: every mark carries ``say``, the words it comes with, so the renderer gives it a START from the voice's own
   word times and an END (the next mark in its slot, the next gesture, the end of its part of the lesson), and writes
   both into the chapter's record.

A mark is DATA: ``{"id", "kind", "slot", "life", "say", "text", "on", "prims"}`` on the step it belongs to, where
``prims`` are paths and pieces of text in shares of the drawing. A renderer draws only those two primitives, so the
same marks draw in a film (``figures.PictureFigure.annotate``) and in a browser, and a NEW KIND of mark is one entry in
``KINDS`` (a line for the model, a function that places it): no renderer changes.
"""
from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .. import knobs
from . import sequence

VERSION = "annotate-1"
MAX_PER_DRAWING = 48
REVIEW_ROUNDS = 1             # how often the model looks at its own annotated drawing and changes it
#: Who is asked (the same model that plans the drawing: ``sequence.PLAN_MODEL`` has the story; since 2026-10-12 the
#: small one, with code doing more of the work: ``honest``, ``lay_out``, ``problems``).
MODEL = sequence.PLAN_MODEL

_ONES = {w: i for i, w in enumerate("zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen "
                                    "seventeen eighteen nineteen".split())}
_TENS = {w: 10 * (i + 2) for i, w in enumerate("twenty thirty forty fifty sixty seventy eighty ninety".split())}
_LENGTHS = re.compile(r"\b(mm|cm|m|km|inch|inches|ft|feet|metres?|meters?|centimetres?|centimeters?)\b", re.I)      # not "units": a reading is no length


def _hundreds(words: list[str], i: int) -> tuple[int, int] | None:
    """A number below a thousand said from ``words[i]`` on: ``(value, the index after it)``, or None."""
    w = words[i] if i < len(words) else ""
    if w not in _TENS and w not in _ONES:
        return None
    value, j = _TENS.get(w, _ONES.get(w, 0)), i + 1
    if w in _ONES and j < len(words) and words[j] == "hundred":
        value, j = value * 100, j + 1
        if j < len(words) and words[j] == "and":
            j += 1
        if j < len(words) and words[j] in _TENS:
            value, j = value + _TENS[words[j]], j + 1
            if j < len(words) and words[j] in _ONES and 0 < _ONES[words[j]] < 10:
                value, j = value + _ONES[words[j]], j + 1
        elif j < len(words) and words[j] in _ONES:
            value, j = value + _ONES[words[j]], j + 1
    elif w in _TENS and j < len(words) and words[j] in _ONES and 0 < _ONES[words[j]] < 10:
        value, j = value + _ONES[words[j]], j + 1
    return value, j


def spoken_numbers(text: str) -> set[str]:
    """The numbers in a piece of narration, as digits ("thirty-five degrees" → 35). "fifty, sixty, or seventy" is three.

    "one thousand eight hundred" is 1800 (it was read as 1 and 800, and a question card about 1800 looked unsaid), and a
    comma ends a number ("eight hundred, two thousand" is not 802). "zero point zero two" is 0.02.
    """
    words = re.findall(r"[a-z]+|\d+(?:\.\d+)?|[,.;:?!]", str(text).lower().replace("-", " "))     # a stop ends a number
    out, i = set(), 0
    while i < len(words):
        w = words[i]
        if re.fullmatch(r"\d+(?:\.\d+)?", w):
            out.add(w)
            i += 1
            continue
        said = _hundreds(words, i)
        if said:
            value, j = said
            if j < len(words) and words[j] == "thousand":
                value, j = value * 1000, j + 1
                if j < len(words) and words[j] == "and":
                    j += 1
                rest = _hundreds(words, j)
                if rest:
                    value, j = value + rest[0], rest[1]
            # "zero point zero two" is 0.02, not 0 and 2: a screen showing "0.02" shows what was said
            digits = []
            if j + 1 < len(words) and words[j] == "point":
                k = j + 1
                while k < len(words) and words[k] in _ONES and _ONES[words[k]] < 10:
                    digits.append(str(_ONES[words[k]]))
                    k += 1
                if digits:
                    j = k
            out.add(f"{value}.{''.join(digits)}" if digits else str(value))
            i = j
            continue
        i += 1
    return out


# ── the board: a drawing as the placer sees it ───────────────────────────────────────────────────────────────────────

def _overlap(a: list[float], b: list[float]) -> float:
    """How much of the smaller of two boxes lies in the other (0 to 1)."""
    w, h = min(a[2], b[2]) - max(a[0], b[0]), min(a[3], b[3]) - max(a[1], b[1])
    if w <= 0 or h <= 0:
        return 0.0
    least = min((a[2] - a[0]) * (a[3] - a[1]), (b[2] - b[0]) * (b[3] - b[1]))
    return min(1.0, w * h / least) if least > 0 else 1.0


def _text(box: list[float], text: str) -> dict:
    return {"shape": "text", "box": [round(v, 4) for v in box], "text": text}


def _path(points: list, closed: bool = False, arrow: bool = False, thin: bool = False, soft: bool = False) -> dict:
    """``thin``: a leader line. ``soft``: a broad, see-through pass, as of a highlighter: what lies under it stays readable.
    A hand's line stays inside the picture: a mark on a thing at the edge is drawn up to the edge."""
    inside = lambda v: round(min(0.996, max(0.004, float(v))), 4)                              # noqa: E731
    return {"shape": "path", "points": [[inside(x), inside(y)] for x, y in points], "closed": closed, "arrow": arrow, "thin": thin, "soft": soft}


def _by_hand(points: list, aspect: float, seed: str, sway: float = 0.0035) -> list:
    """A line as a hand draws it: a slight bow and a tremor that dies away at both ends (after the recipe of the
    AI-Whiteboard project, read 2026-10-12). Seeded by what the mark is, so the same mark is the same line in every
    render and after every repair."""
    import random  # noqa: PLC0415
    if len(points) < 2:
        return points
    rng = random.Random(seed)
    if len(points) == 2:                                 # a straight stroke: give it points to sway on
        (x0, y0), (x1, y1) = points
        points = [(x0 + (x1 - x0) * i / 10, y0 + (y1 - y0) * i / 10) for i in range(11)]
    bow, a, b = rng.uniform(-1, 1) * sway * 1.4, rng.uniform(0, 6.28), rng.uniform(0, 6.28)
    out, last = [], len(points) - 1
    for i, (x, y) in enumerate(points):
        (px, py), (qx, qy) = points[max(0, i - 1)], points[min(last, i + 1)]
        dx, dy = qx - px, (qy - py) * aspect
        length = math.hypot(dx, dy) or 1.0
        nx, ny = -dy / length, dx / length
        t = i / last
        taper = math.sin(math.pi * t)                    # nothing at the ends: a line still starts and ends where it should
        off = taper * (bow * math.sin(math.pi * t) + sway * 0.5 * (math.sin(a + t * 9) + 0.6 * math.sin(b + t * 23)))
        out.append((x + nx * off, y + ny * off / aspect))
    return out


def boxes_of(prims: list[dict], aspect: float = 1.0) -> list[list[float]]:
    """The room a mark takes on the board: its writing, and its lines as a string of small boxes."""
    out = [prim["box"] for prim in prims if prim["shape"] == "text"]
    for prim in prims:
        if prim["shape"] == "path" and not prim.get("thin"):
            points = prim["points"]
            out += [[x - 0.012, y - 0.012 / aspect, x + 0.012, y + 0.012 / aspect] for x, y in points[2:-2:3]] if len(points) > 6 else []
    return out


def _through(prims: list[dict], words: list[list[float]]) -> bool:
    """True when a line of these primitives runs through writing (the inner part of one of the boxes ``words``): solid
    ink over a number leaves it unread. A see-through pass of the pen does not count."""
    for prim in prims:
        if prim["shape"] != "path" or prim.get("soft"):
            continue
        points = prim["points"]
        for (x0, y0), (x1, y1) in zip(points, points[1:]):
            for k in range(5):
                x, y = x0 + (x1 - x0) * k / 4, y0 + (y1 - y0) * k / 4
                for a, b, c, d in words:
                    if a + 0.12 * (c - a) < x < c - 0.12 * (c - a) and b + 0.12 * (d - b) < y < d - 0.12 * (d - b):
                        return True
    return False


class Board:
    """A drawing as the placer sees it: its things, every outline point, the boxes of its printed words."""

    def __init__(self, made: dict):
        self.aspect = float(made.get("height") or 1) / max(float(made.get("width") or 1), 1.0)
        self.parts = made["parts"]
        self.things = sequence.things_of(self.parts, self.aspect)
        self.points = [pt for p in self.parts if p["kind"] != "text" for pt in (p.get("points") or [])]     # every point: a thin line is found
        self.words = [p["box"] for p in self.parts if p["kind"] == "text"]
        heights = sorted(b[3] - b[1] for b in self.words)
        # a line of our writing: a little larger than the drawing's own print (a value has to be read in a small picture)
        self.letter = min(0.085, max(0.05, heights[len(heights) // 2] * 1.3)) if heights else 0.06

    def text_box(self, text: str, centre: tuple) -> list[float]:
        wide = max(2, len(text)) * 0.58 * self.letter * self.aspect
        return [centre[0] - wide / 2, centre[1] - self.letter / 2, centre[0] + wide / 2, centre[1] + self.letter / 2]

    def ink(self, box: list[float]) -> float:
        x0, y0, x1, y1 = box[0] - 0.004, box[1] - 0.006, box[2] + 0.004, box[3] + 0.006
        return sum(1.0 for x, y in self.points if x0 <= x <= x1 and y0 <= y <= y1)

    def clutter(self, box: list[float], taken: list) -> float:
        """How much is already in a box: the drawing's ink, its printed words, marks that stand; outside the picture is out."""
        cost = self.ink(box)                             # a line under our writing can still be read round (it has a plate) …
        cost += sum(400.0 for other in self.words if _overlap(box, other) > 0)       # … the drawing's own words under it cannot
        cost += sum(600.0 for other in taken if _overlap(box, other) > 0)
        if box[0] < 0.005 or box[1] < 0.005 or box[2] > 0.995 or box[3] > 0.995:
            cost += 1000.0
        return cost

    def anchor(self, thing: dict) -> tuple[list[float], bool]:
        """The small place a mark on a thing belongs to: its printed letter when it is a mark with one, the mark itself,
        or a clear place on a long line. ``(box, lettered)``."""
        main = thing["main"]
        if not thing["big"] and thing["labels"]:
            return list(thing["labels"][0]["box"]), True
        if main["kind"] == "text":
            return list(main["box"]), True
        if not thing["big"]:
            return list(main["box"]), False
        points = main.get("points") or []
        if not points:
            x, y = (main["box"][0] + main["box"][2]) / 2, (main["box"][1] + main["box"][3]) / 2
        else:
            # a place ON the line where the least else is going on: a mark at its middle sat on the point where four
            # lines meet (a mirror's middle is the point of incidence)
            def around(point):
                box = [point[0] - 0.05, point[1] - 0.05 / self.aspect, point[0] + 0.05, point[1] + 0.05 / self.aspect]
                return self.ink(box) + 30.0 * sum(1 for w in self.words if _overlap(box, w) > 0)
            spots = [points[min(len(points) - 1, int(len(points) * share))] for share in (0.5, 0.3, 0.7, 0.2, 0.8)]
            x, y = min(spots, key=lambda q: (around(q), spots.index(q)))
        return [x - 0.012, y - 0.012 / self.aspect, x + 0.012, y + 0.012 / self.aspect], False

    def write(self, text: str, anchor: list[float], taken: list, prefer: str = "", lead: bool = True) -> tuple[list[dict], list[float], str]:
        """A piece of writing next to an anchor, in the clearest place: ``(prims, box, side)``.

        The eight places round the anchor are tried first; when every one of them lies on writing or on a mark that
        stands, places further off are tried and the writing is tied to its anchor by a thin leader line. ``prefer``
        ("left", "right", "above", "below") is tried first when it is as clear as the best.
        """
        ax0, ay0, ax1, ay1 = anchor
        cx, cy = (ax0 + ax1) / 2, (ay0 + ay1) / 2
        probe = self.text_box(text, (0, 0))
        w, h = probe[2] - probe[0], probe[3] - probe[1]
        gx, gy = 0.012, 0.012 / self.aspect
        near = [("right", (ax1 + gx + w / 2, cy)), ("below", (cx, ay1 + gy + h / 2)), ("above", (cx, ay0 - gy - h / 2)),
                ("left", (ax0 - gx - w / 2, cy)), ("right-up", (ax1 + gx + w / 2, ay0 - gy - h / 2)), ("right-down", (ax1 + gx + w / 2, ay1 + gy + h / 2)),
                ("left-up", (ax0 - gx - w / 2, ay0 - gy - h / 2)), ("left-down", (ax0 - gx - w / 2, ay1 + gy + h / 2))]
        order = sorted(near, key=lambda spot: (0 if prefer and spot[0] == prefer else 1, near.index(spot)))
        cost, _, side, centre = min((self.clutter(self.text_box(text, c), taken), n, s, c) for n, (s, c) in enumerate(order))
        if cost < 55 or not lead:                        # not on writing and not on a standing mark: it goes there
            box = self.text_box(text, centre)
            return [_text(box, text)], box, side
        far = []
        for reach in (0.11, 0.16, 0.22, 0.3):
            for i in range(12):
                angle = 2 * math.pi * i / 12
                c = (cx + (reach + w / 2) * math.cos(angle), cy + (reach / self.aspect + h / 2) * math.sin(angle))
                far.append((self.clutter(self.text_box(text, c), taken) + 8 * reach, len(far), c))
        far_cost, _, far_centre = min(far)
        if far_cost >= cost:
            box = self.text_box(text, centre)
            return [_text(box, text)], box, side
        box = self.text_box(text, far_centre)
        edge = (min(max(cx, box[0]), box[2]), min(max(cy, box[1]), box[3]))
        return [_path([edge, (cx, cy)], thin=True), _text(box, text)], box, "away"


def _union(parts: list[dict]) -> list[float]:
    return [min(p["box"][0] for p in parts), min(p["box"][1] for p in parts), max(p["box"][2] for p in parts), max(p["box"][3] for p in parts)]


def _line_of(thing: dict):
    """A thing as a straight line ``(start, end)``, or None when it is not one (a closed shape, a word, a curl)."""
    main = thing["main"]
    points = main.get("points") or []
    if main["kind"] == "text" or main.get("closed") or len(points) < 2:
        return None
    points = [points[0]] + [p for m in thing["marks"] if m["kind"] == "stroke" and float(m.get("length") or 0) >= sequence.BIG
                            for p in (m.get("points") or [])[:1] + (m.get("points") or [])[-1:]] + [points[-1]]
    a, b = min(points, key=lambda p: (p[0], p[1])), max(points, key=lambda p: (p[0], p[1]))
    if abs(a[0] - b[0]) < 1e-4:                         # upright: take the highest and the lowest point
        a, b = min(points, key=lambda p: p[1]), max(points, key=lambda p: p[1])
    return a, b


# ── the kinds of mark: each places itself ───────────────────────────────────────────────────────────────────────────

def _place_value(board: Board, things: list, text: str, taken: list, prefer: str = "") -> list[dict] | None:
    if not text:
        return []                                        # a wipe: nothing is drawn, the slot is emptied
    anchor, lettered = board.anchor(things[0])
    if lettered and len(text) <= 6 and not prefer:       # beside the picture's own letter it reads "i = 30°"
        prims, box, side = board.write("= " + text, anchor, taken, prefer="right", lead=False)
        if side == "right" and board.clutter(box, taken) < 55:
            taken.append(box)
            return prims
    prims, box, _ = board.write(text, anchor, taken, prefer=prefer)
    taken.append(box)
    return prims


def _place_angle(board: Board, things: list, text: str, taken: list, prefer: str = "") -> list[dict] | None:
    first, second = (_line_of(t) for t in things)
    if not first or not second:
        return None
    k = board.aspect
    (ax, ay), (bx, by) = (first[0][0], first[0][1] * k), (first[1][0], first[1][1] * k)
    (cx, cy), (dx, dy) = (second[0][0], second[0][1] * k), (second[1][0], second[1][1] * k)
    denom = (bx - ax) * (dy - cy) - (by - ay) * (dx - cx)
    if abs(denom) < 1e-9:
        return None                                      # the two lines do not meet
    t = ((cx - ax) * (dy - cy) - (cy - ay) * (dx - cx)) / denom
    px, py = ax + t * (bx - ax), ay + t * (by - ay)

    def ways(p, q):                                      # the directions a line leaves the meeting point in
        out = []
        for end in (p, q):
            length = math.hypot(end[0] - px, end[1] - py)
            if length > 0.03:
                out.append(((end[0] - px) / length, (end[1] - py) / length))
        return out
    pairs = [(u, v) for u in ways((ax, ay), (bx, by)) for v in ways((cx, cy), (dx, dy))]
    if not pairs or not (-0.05 <= t <= 1.05):
        return None
    between = lambda pair: math.acos(max(-1.0, min(1.0, pair[0][0] * pair[1][0] + pair[0][1] * pair[1][1])))      # noqa: E731
    least = min(between(pair) for pair in pairs)
    if least < math.radians(4):
        return None

    def arc_of(pair, radius):
        start, end = math.atan2(pair[0][1], pair[0][0]), math.atan2(pair[1][1], pair[1][0])
        sweep = (end - start + math.pi) % (2 * math.pi) - math.pi
        return start, sweep, [(px + radius * math.cos(start + sweep * i / 16), (py + radius * math.sin(start + sweep * i / 16)) / k) for i in range(17)]

    def busy(points):
        return sum(board.clutter([x - 0.008, y - 0.008 / k, x + 0.008, y + 0.008 / k], taken) for x, y in points[2:-2])
    # Of the sectors with this angle (a right angle has two, a crossing four) the one with the least in it, at a radius
    # where the arc lies clear of the picture's own marks: an arc drawn on an arc reads as one.
    choices = [(busy(arc_of(pair, radius)[2]), n, radius, pair) for n, pair in enumerate(pairs) if between(pair) <= least + math.radians(3)
               for radius in (0.07, 0.1, 0.13)]
    _, _, radius, pair = min(choices, key=lambda choice: choice[:3])
    start, sweep, arc = arc_of(pair, radius)
    prims = [_path(arc)]
    taken.extend([x - 0.01, y - 0.01 / k, x + 0.01, y + 0.01 / k] for x, y in arc[4:-4:4])
    if text:
        spots = []
        for share in (0.5, 0.3, 0.7):                    # along the arc, its middle first; outside it, then further out
            for reach in (radius + 0.035 + 0.011 * len(text), radius + 0.08 + 0.011 * len(text)):
                middle = start + sweep * share
                box = board.text_box(text, (px + reach * math.cos(middle), (py + reach * math.sin(middle)) / k))
                spots.append((board.clutter(box, taken), len(spots), box))
        box = min(spots)[2]
        prims.append(_text(box, text))
        taken.append(box)
    return prims


def _place_span(board: Board, things: list, text: str, taken: list, prefer: str = "") -> list[dict] | None:
    """A length shown along a line: a measuring line beside it with a tick at each end, and the value at its middle."""
    line = _line_of(things[0])
    if not line or not text:
        return _place_value(board, things, text, taken, prefer)
    k = board.aspect
    (ax, ay), (bx, by) = (line[0][0], line[0][1] * k), (line[1][0], line[1][1] * k)
    length = math.hypot(bx - ax, by - ay)
    if length < 0.06:
        return _place_value(board, things, text, taken, prefer)
    ux, uy = (bx - ax) / length, (by - ay) / length
    sides = []
    for sign in (1, -1):
        nx, ny = -uy * sign, ux * sign
        gap = 0.04
        a, b = (ax + nx * gap + ux * 0.01, ay + ny * gap + uy * 0.01), (bx + nx * gap - ux * 0.01, by + ny * gap - uy * 0.01)
        centre = ((a[0] + b[0]) / 2 + nx * 0.04, ((a[1] + b[1]) / 2 + ny * 0.04) / k)
        box = board.text_box(text, centre)
        along = [(a[0] + (b[0] - a[0]) * i / 8, (a[1] + (b[1] - a[1]) * i / 8) / k) for i in range(9)]
        cost = board.clutter(box, taken) + sum(board.ink([x - 0.008, y - 0.008 / k, x + 0.008, y + 0.008 / k]) for x, y in along)
        ticks = [[(p[0] - nx * 0.012, (p[1] - ny * 0.012) / k), (p[0] + nx * 0.012, (p[1] + ny * 0.012) / k)] for p in (a, b)]
        sides.append((cost, sign, [_path([(a[0], a[1] / k), (b[0], b[1] / k)]), _path(ticks[0]), _path(ticks[1]), _text(box, text)], box))
    _, _, prims, box = min(sides, key=lambda side: side[:2])
    taken.append(box)
    return prims


def _place_label(board: Board, things: list, text: str, taken: list, prefer: str = "") -> list[dict] | None:
    if not text:
        return []
    anchor, _ = board.anchor(things[0])
    prims, box, _ = board.write(text, anchor, taken, prefer=prefer)
    taken.append(box)
    return prims


def _place_ring(board: Board, things: list, text: str, taken: list, prefer: str = "") -> list[dict] | None:
    thing = things[0]
    parts = [thing["main"]] + thing["labels"] if not thing["big"] else (thing["labels"][:1] or None)
    box = _union(parts) if parts else board.anchor(thing)[0]
    k = board.aspect
    rx, ry = (box[2] - box[0]) / 2 + 0.018, (box[3] - box[1]) / 2 + 0.018 / k
    mx, my = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
    import random  # noqa: PLC0415
    rng = random.Random(f"ring:{thing['numbers']}")
    start, over, drift = rng.uniform(0, 6.28), rng.uniform(0.16, 0.46), rng.uniform(-0.035, 0.035)
    steps = 44                                           # a hand's ring: begun anywhere, run a little past its start, not quite closed on itself
    inside = lambda v: min(0.994, max(0.006, v))         # noqa: E731 - a thing at the picture's edge is ringed up to the edge
    return [_path([(inside(mx + rx * (1 + drift * i / steps) * math.cos(start + (2 * math.pi + over) * i / steps)),
                    inside(my + ry * (1 + drift * i / steps) * math.sin(start + (2 * math.pi + over) * i / steps))) for i in range(steps + 1)])]


def _place_trace(board: Board, things: list, text: str, taken: list, prefer: str = "") -> list[dict] | None:
    main = things[0]["main"]
    lines = [main] + [m for m in things[0]["marks"] if m["kind"] == "stroke" and float(m.get("length") or 0) >= sequence.BIG]
    prims = []
    for part in lines:
        points = part.get("points") or []
        if len(points) >= 2:
            step = max(1, len(points) // 90)
            # a broad see-through pass: gone over in solid ink, the line under it (its dashes, its arrowhead) was hidden
            prims.append(_path(points[::step] + [points[-1]], closed=bool(part.get("closed")), soft=True))
    return prims or None


def _place_arrow(board: Board, things: list, text: str, taken: list, prefer: str = "") -> list[dict] | None:
    anchor, _ = board.anchor(things[0])
    centre = ((anchor[0] + anchor[2]) / 2, (anchor[1] + anchor[3]) / 2)
    k, reach, spots = board.aspect, 0.15, []
    for i in range(8):
        angle = 2 * math.pi * i / 8 - math.pi / 4
        tail = (centre[0] + reach * math.cos(angle), centre[1] + reach * math.sin(angle) / k)
        note = board.text_box(text, (tail[0] + (0.02 + 0.3 * len(text) * board.letter * k) * math.cos(angle), tail[1] + (0.035 / k) * math.sin(angle))) \
            if text else [tail[0] - 0.02, tail[1] - 0.02 / k, tail[0] + 0.02, tail[1] + 0.02 / k]
        along = [(centre[0] + (tail[0] - centre[0]) * s / 6, centre[1] + (tail[1] - centre[1]) * s / 6) for s in range(2, 7)]
        crossed = sum(board.ink([x - 0.01, y - 0.01 / k, x + 0.01, y + 0.01 / k]) for x, y in along)
        out = 1000.0 if not (0.01 <= tail[0] <= 0.99 and 0.01 <= tail[1] <= 0.99) else 0.0       # an arrow starts inside the picture
        spots.append((board.clutter(note, taken) + 0.5 * crossed + out, i, tail, note))
    _, _, tail, note = min(spots)
    head = (centre[0] + (tail[0] - centre[0]) * 0.2, centre[1] + (tail[1] - centre[1]) * 0.2)
    prims = [_path(_by_hand([tail, head], k, f"arrow:{things[0]['numbers']}"), arrow=True)]
    if text:
        prims.append(_text(note, text))
        taken.append(note)
    return prims


def _place_cross(board: Board, things: list, text: str, taken: list, prefer: str = "") -> list[dict] | None:
    anchor, _ = board.anchor(things[0])
    cx, cy, r, k = (anchor[0] + anchor[2]) / 2, (anchor[1] + anchor[3]) / 2, 0.028, board.aspect
    seed = f"cross:{things[0]['numbers']}"
    return [_path(_by_hand([(cx - r, cy - r / k), (cx + r, cy + r / k)], k, seed + "a")),
            _path(_by_hand([(cx - r, cy + r / k), (cx + r, cy - r / k)], k, seed + "b"))]


def _place_tick(board: Board, things: list, text: str, taken: list, prefer: str = "") -> list[dict] | None:
    anchor, _ = board.anchor(things[0])
    _, box, _ = board.write("OK", anchor, taken, prefer=prefer, lead=False)                # the room a tick takes
    cx, cy, r, k = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2, 0.022, board.aspect
    return [_path([(cx - r, cy), (cx - r * 0.3, cy + r * 0.8 / k), (cx + r, cy - r / k)])]


def _place_equal(board: Board, things: list, text: str, taken: list, prefer: str = "") -> list[dict] | None:
    """The same small stroke across each of two things: "these two are equal"."""
    prims, k = [], board.aspect
    for thing in things:
        points = thing["main"].get("points") or []
        if len(points) < 3:
            return None
        m = len(points) // 2
        (x0, y0), (x1, y1), (mx, my) = points[max(0, m - 2)], points[min(len(points) - 1, m + 2)], points[m]
        dx, dy = x1 - x0, (y1 - y0) * k
        length = math.hypot(dx, dy) or 1.0
        nx, ny = -dy / length * 0.016, dx / length * 0.016
        prims.append(_path([(mx - nx, my - ny / k), (mx + nx, my + ny / k)]))
    return prims


@dataclass(frozen=True)
class Kind:
    """One kind of mark a hand can add. ``things``: how many things it is on. ``says``: what it writes ("value", "words",
    ""). ``life``: "stays" (until another takes its slot, or its part of the lesson ends) or "beat" (until the hand's
    next gesture). ``brief``: the line that tells the model what it is ("" for a kind made from what is HEARD, which
    the model never asks for by name). ``place``: where it goes. For a mark that CLAIMS something (two things are
    equal), ``heard`` is what the sentence it comes with must say and ``never`` what it must not, as patterns: a claim
    the voice does not make is not drawn."""
    name: str
    things: int
    says: str
    life: str
    brief: str
    place: Callable
    heard: str = ""
    never: str = ""


#: The stroke that means "equal in size" was put on two PARALLEL lines for the words "the two lines stay the same distance
#: apart" (Angles in a Triangle, 2026-10-12). The sentence must compare two things (said in many ways: the list is wide
#: on purpose, a fair "is fifty degrees too" must pass), and a sentence about parallel lines is not about equal size.
_ALIKE = (r"\bequal\w*|\bcongruent\b|\bsame\b|\btoo\b|\balso\b|\bas well\b|\bmatch\w*|\bidentical\b|\bboth\b|\bas \w+ as\b"
          r"|\bbarabar\b|\bsamaan\b|\bbhi\b|\bdono\b|बराबर|समान|भी|दोनों|=")
_PARALLEL = r"\bparallel\w*|\bapart\b|\bsam+a+ntar\b|समांतर|समानांतर"


#: What a hand can add. A new kind is one entry here: the prompt is made from these lines, and a renderer draws only the
#: paths and pieces of text ``place`` returns.
KINDS = {kind.name: kind for kind in (
    Kind("value", 1, "value", "stays", "", _place_value),
    Kind("angle", 2, "value", "stays", "", _place_angle),
    Kind("span", 1, "value", "stays", "", _place_span),
    Kind("ring", 1, "", "beat", "ring a thing the words are speaking of right now", _place_ring),
    Kind("trace", 1, "", "beat", "go over a thing's own line again, to say \"this one\"", _place_trace),
    Kind("arrow", 1, "words", "beat", "point an arrow at a thing, with one to three words if they help (\"measure from here\")", _place_arrow),
    Kind("cross", 1, "", "beat", "cross out a thing the words tell the learner NOT to use (the wrong line to measure from, a wrong path); never a thing "
                                 "of the picture that is itself right, and never for a wrong result the words only imagine (it is not in the picture)",
         _place_cross),
    Kind("tick", 1, "", "beat", "tick a thing the words have just found right", _place_tick),
    Kind("label", 1, "words", "stays", "write a NAME (one to three words) at a thing the picture does not name, when the words name it", _place_label),
    Kind("equal", 2, "", "stays", "put the same small stroke on two things the words call EQUAL IN SIZE: two angles, or two lengths (\"on\": [\"#6\", "
                                  "\"#7\"]); never on parallel lines, and never on things that are only alike", _place_equal, _ALIKE, _PARALLEL),
)}
GESTURES = [kind for kind in KINDS.values() if kind.brief]


def ideate_system() -> str:
    gestures = "\n".join(f"- \"{kind.name}\": {kind.brief};" for kind in GESTURES)
    return f"""You are a teacher's HAND at a board. The picture is drawn (some of its things come during the lesson: the list says
when). While the voice speaks you ADD to the picture what a good teacher adds, so that what is said can be SEEN on the
picture at that moment, not only heard.

You get the picture with its things tagged in red (#1, #2, …; a red tag with a hash sign is OUR tag, a bare number or
letter is the picture's own print), the things as a list, and the lesson's words beat by beat. The moments a new line
comes up are numbered S1, S2, …; everything you add belongs to one of them.

FIRST, "heard": go through the words and list EVERY value the voice says about the picture (the size of an angle, a
length, a reading, a count of something shown), each at the step where it is said:
- "says": the few words of the voice that say it, copied exactly;
- "value": as it is written on a board, with its unit: "30°", "6 cm", "8 N", "2 units";
- "of": what it is the value of, in a few words;
- "measures": the thing whose size it is: the tag of the MARK that measures it (an angle's arc or its letter, a side, a
  scale's pointer), not a neighbouring line. When the picture has no mark for it but it is the angle between two lines
  of the picture, give those two tags: ["#4", "#1"]. When nothing in the picture measures it, null;
- "open": true when the voice only ASKS for this value here (it is an option of a question, or the answer comes later):
  it is then not written. A value is written at the step where the voice GIVES it as true.
When the voice moves to a new case (other numbers for the same picture), list the new values at their steps: they
replace the old ones on the same thing. A case is ALL its values: when one of them changes, every other value written
for the old case is wrong from that moment. List each of those again at that step, on its thing: with the new value when
the voice gives it, with "value": "?" when the voice asks for it or leaves it to the learner.

THEN, "add": what the hand does besides writing values. Use exactly these:
{gestures}
Each with "says": the few words of the voice it comes with, copied exactly. Whenever the words speak of ONE particular
thing of the picture by name or point at it ("the normal", "this ray", "the mirror surface"), do one of these on it: a
learner's eye should be led to it. A step that is about no particular thing gets nothing; at most one of these at a
step; only on a thing that is on the board by that step; never a place of your own, always a tagged thing.

Answer in JSON only:
{{"heard": [{{"at": "S4", "says": "thirty degrees from the normal", "value": "30°", "of": "the angle of incidence", "measures": "#6", "open": false}},
           {{"at": "S21", "says": "forty degrees from the mirror surface", "value": "40°", "of": "the angle to the surface", "measures": ["#4", "#1"], "open": false}}],
 "add": [{{"at": "S3", "do": "trace", "on": "#3", "says": "the dashed normal"}},
         {{"at": "S12", "do": "arrow", "on": "#2", "text": "measure from here", "says": "measure turns from"}}]}}"""


REVIEW_SYSTEM = """You check a teacher's annotations on a drawing. Each tile shows the drawing at one moment of a lesson with what the
teacher's hand has added in red; every addition carries a small blue tag (m1, m2, …). The list says what each was meant
to be: the words it came with, its kind, what it writes, the thing it was put on.

For EVERY tag say whether it is right. Look at the tile, not at the list:
- "ok": it is on the right thing, can be read, and helps.
- "wrong_thing": it is on or beside the wrong thing (an angle's value on a line that is not that angle; a ring round
  something the words are not about). Give "on": the tag of the thing it belongs to (#n), from the things listed.
- "unreadable": it lies on other writing or on lines of the drawing so that it cannot be read. Give "side": "left",
  "right", "above" or "below", where there is room.
- "pointless": it adds nothing, repeats another addition, or would confuse a learner. It is removed.
In doubt, "ok". Answer in JSON only: {"marks": {"m1": {"is": "ok"}, "m2": {"is": "wrong_thing", "on": "#6"}, "m3": {"is": "unreadable", "side": "left"}}}"""


# ── the ideas, kept honest ───────────────────────────────────────────────────────────────────────────────────────────

def _tag(value) -> int:
    digits = re.sub(r"\D", "", str(value or ""))
    return int(digits) if digits else 0


def _said_in(words, narration: str) -> str:
    """The quoted words when they are literally in the narration (so the renderer can find when they are spoken), else ""."""
    plain = lambda text: re.sub(r"[^a-z0-9 ]", "", re.sub(r"\s+", " ", str(text).lower())).strip()            # noqa: E731
    quote = re.sub(r"\s+", " ", str(words or "")).strip().strip("“”\"'.,;:!?")
    return quote if quote and len(quote.split()) <= 12 and plain(quote) in plain(narration) else ""


def _sentence_of(words, narration: str) -> str:
    """The sentence of the narration that holds the quoted words ("" when they are not in it; the whole of it when they
    run over a sentence's end)."""
    if not _said_in(words, narration):
        return ""
    plain = lambda text: re.sub(r"[^a-z0-9 ]", "", re.sub(r"\s+", " ", str(text).lower())).strip()            # noqa: E731
    quote = plain(re.sub(r"\s+", " ", str(words or "")).strip().strip("“”\"'.,;:!?"))
    return next((part for part in re.split(r"(?<=[.?!।])\s+", str(narration)) if quote in plain(part)), str(narration))


def honest(answer, board: Board, moments: dict, narrations: dict, shown: dict, drawn_at: dict, log=print) -> list[dict]:
    """The model's ideas, kept only when code can stand behind them: a mark of a known kind, on things that exist and
    are on the board by then, at a real step, a written NUMBER that the voice says in that beat (or its lines show), one
    gesture at a step, a CLAIM (``Kind.heard``, ``Kind.never``) only where the sentence it comes with makes it. Every value the model HEARD and found a thing for is written (what is heard is seen, by
    construction); a value it heard only asked is not. ``moments``: step number → (beat id, step index);
    ``narrations``: beat id → the voice's words; ``shown``: beat id → numbers in its lines; ``drawn_at``: thing number →
    the step it is drawn at."""
    out, gestures, dropped = [], set(), []
    things = lambda tags: [board.things[t - 1] for t in tags]                               # noqa: E731

    def usable(tags, at) -> str:
        if not tags or any(not 1 <= t <= len(board.things) for t in tags) or len(set(tags)) != len(tags):
            return "not a thing of the picture"
        return "the thing is not on the board yet" if any(drawn_at.get(t, 1) > at for t in tags) else ""
    heard = answer.get("heard") if isinstance(answer, dict) else None
    for raw in heard if isinstance(heard, list) else []:
        if not isinstance(raw, dict) or raw.get("open") is True or raw.get("measures") in (None, "", []):
            continue
        at = _tag(raw.get("at"))
        measures = raw["measures"] if isinstance(raw["measures"], (list, tuple)) else [raw["measures"]]
        tags = [_tag(v) for v in measures][:2]
        if len(tags) == 2 and all(1 <= t <= len(board.things) for t in tags) and tags[0] != tags[1]:
            # "The angle between these two lines", where the drawing has its OWN mark for that angle (an arc that rests on
            # both): the value belongs at the mark. A small model gave every angle of a ray diagram as a pair of lines and
            # the hand drew a second arc beside the printed one, seven times (2026-10-12).
            own = [m for m, other in enumerate(board.things, 1) if not other["big"] and m not in tags
                   and all(sequence._rests_on(other, board.things[t - 1], board.aspect) for t in tags)]
            if len(own) == 1:
                tags = own
        text = re.sub(r"\s+", " ", str(raw.get("value") or "")).strip()[:14]
        numbers = re.findall(r"\d+(?:\.\d+)?", text)
        why = "not a step" if at not in moments else usable(tags, at)
        heard_in = moments[at][0] if at in moments else ""                   # the beat whose voice says it
        pull = why == "the thing is not on the board yet" and len(tags) == 1 and text != "?"
        if pull:
            # The voice gives its value now: the hand draws the mark now (``pulls``). But not before the lines it is
            # drawn ON are there (an angle's arc needs both its arms): a script gave "thirty degrees" in its first
            # sentence, before the mirror, and the arc with its "30°" hung in the empty picture.
            why, thing = "", board.things[tags[0] - 1]
            arms = [drawn_at.get(m, 1) for m, other in enumerate(board.things, 1) if other["big"] and other["main"]["kind"] == "stroke"
                    and m != tags[0] and sequence._rests_on(thing, other, board.aspect)]
            at = max([at] + [step for step in arms if step in moments])
        beat = moments[at][0] if at in moments else ""
        if not why and text != "?" and not numbers:
            why = "a value with no number"
        if not why and not all(n in spoken_numbers(narrations.get(heard_in, "")) | shown.get(heard_in, set()) for n in numbers):
            why = "a number the voice does not say in that beat"
        if why:
            dropped.append(f"S{at} {text!r}: {why}")
            continue
        kind = "angle" if len(tags) == 2 else "span" if board.things[tags[0] - 1]["big"] and _LENGTHS.search(text) else "value"
        out.append({"at": at, "kind": kind, "things": things(tags), "tags": tags, "text": text, "pull": pull,
                    "say": _said_in(raw.get("says"), narrations.get(beat, "")) if beat == heard_in else ""})
        if pull:
            drawn_at[tags[0]] = at
    listed = answer.get("add") if isinstance(answer, dict) else None
    for raw in listed if isinstance(listed, list) else []:
        if not isinstance(raw, dict):
            continue
        name, at = str(raw.get("do") or "").strip().lower(), _tag(raw.get("at"))
        kind = KINDS.get(name)
        on = raw.get("on") if isinstance(raw.get("on"), (list, tuple)) else [raw.get("on")]
        tags = [_tag(v) for v in on]
        text = re.sub(r"\s+", " ", str(raw.get("text") or "")).strip()[:28] if kind and kind.says == "words" else ""
        why = "not a gesture or not a step" if kind is None or not kind.brief or at not in moments else \
            "not the number of things it needs" if len(tags) != kind.things else usable(tags, at)
        if not why and len(text.split()) > 4:
            why = "too many words"
        if not why and kind.name == "label" and not text:
            why = "a name with no words"
        if not why and (kind.heard or kind.never):
            sentence = _sentence_of(raw.get("says"), narrations.get(moments[at][0], ""))
            if (kind.heard and not re.search(kind.heard, sentence, re.I)) or (kind.never and re.search(kind.never, sentence, re.I)):
                why = "the voice does not say what this mark says"
        if not why and kind.life == "beat" and at in gestures:
            why = "more than one gesture at a step"
        if why:
            dropped.append(f"S{at} {name} {text!r}: {why}")
            continue
        if kind.life == "beat":
            gestures.add(at)
        out.append({"at": at, "kind": kind.name, "things": things(tags), "tags": tags, "text": text, "pull": False,
                    "say": _said_in(raw.get("says"), narrations.get(moments[at][0], ""))})
    if dropped:
        log(f"[annotate] {len(dropped)} idea(s) not taken: " + "; ".join(dropped)[:520])
    out = sorted(out, key=lambda idea: idea["at"])[:MAX_PER_DRAWING]
    for n, idea in enumerate(out, 1):
        idea["id"] = f"m{n}"
    return out


def lay_out(board: Board, ideas: list[dict], moments: dict, chapter_of: dict, log=print) -> tuple[dict, dict]:
    """Ideas → marks on their steps, each placed by what stands on the board AT THAT STEP: ``(marks by step, pulls)``.

    What is written belongs to the part of the lesson it was written in. A teacher wipes the numbers of one example
    before the next; left standing, the thirty degrees of the opening sat beside the fifty of the last example. So at
    the first step of each new chapter every value still standing is wiped, and the voice's own values of the new
    chapter are written at their steps after it. A value that was wiped three chapters ago takes no room.

    A value of the OLD case never stands beside one of the new (read on the film of "Laws of Reflection": "40°" at one
    angle beside the last part's "30°" at the other for two seconds, then "35°" beside the "40°" it had just replaced).
    So the wipe at a part's first step stays a wipe even when a new value is written at that place a moment later, and a
    "?" that takes the place of a standing value comes with the new case's own value, not with its later words.
    """
    by_step: dict[int, list] = {}
    for idea in ideas:
        by_step.setdefault(idea["at"], []).append(idea)
    out, pulls, standing, last_chapter = {}, {}, {}, None
    for number in sorted(moments):
        key = moments[number]
        chapter, marks = chapter_of.get(key[0]), []
        if last_chapter is not None and chapter != last_chapter and standing:
            marks += [{"id": "", "slot": slot, "kind": held["kind"], "life": "stays", "say": "", "text": "", "on": held["on"], "prims": []}
                      for slot, held in standing.items()]
            standing = {}
        last_chapter = chapter
        given = next((other.get("say") for other in by_step.get(number, []) if KINDS[other["kind"]].says == "value"
                      and other["text"] not in ("", "?") and other.get("say")), "")
        for idea in by_step.get(number, []):
            kind = KINDS[idea["kind"]]
            stays = kind.life == "stays"
            slot = f"{'value' if idea['kind'] == 'span' else idea['kind']}:{'+'.join(str(t) for t in sorted(idea['tags']))}" if stays else ""
            taken = [box for other, held in standing.items() if other != slot for box in held["boxes"]]
            prims = kind.place(board, idea["things"], idea["text"], taken, idea.get("prefer", ""))
            if prims is None:
                log(f"[annotate] S{number} {idea['kind']}: no place for it on the drawing")
                continue
            if not stays and _through(prims, [box for held in standing.values() for box in held["words"]]):
                # A ring round the displaced water ran through the "2 units" written beside it at that very step
                # (Why Water Pushes Up, 2026-10-12). What is written there already leads the eye: the gesture is left out.
                log(f"[annotate] S{number} {idea['kind']}: it would run through what is written there; left out")
                continue
            if stays and not prims and slot not in standing:
                continue                                 # a wipe of what is not there
            say = idea.get("say", "")
            if stays and idea["text"] == "?" and slot in standing and given:
                say = given                              # the value standing there is wrong from the moment the case changes
            if stays:
                if prims:
                    standing[slot] = {"kind": idea["kind"], "on": idea["tags"], "boxes": boxes_of(prims, board.aspect),
                                      "words": [prim["box"] for prim in prims if prim["shape"] == "text"]}
                else:
                    standing.pop(slot, None)
            if idea.get("pull"):
                pulls.setdefault(key, []).extend(idea["things"][0]["numbers"])
            marks.append({"id": idea["id"], "slot": slot, "kind": idea["kind"], "life": kind.life, "say": say,
                          "text": idea["text"], "on": idea["tags"], "needs": [int(thing["main"]["n"]) for thing in idea["things"]],
                          "prims": prims})
        if marks:
            out[key] = marks
    return out, pulls


# ── check, and change ────────────────────────────────────────────────────────────────────────────────────────────────

def states(marks_by_step: dict, moments: dict) -> list[tuple]:
    """The board after every step that adds something: ``[(step number, standing marks, the gesture of that step)]``."""
    out, standing = [], {}
    for number in sorted(moments):
        marks = marks_by_step.get(moments[number], [])
        gesture = None
        for mark in marks:
            if mark["life"] == "stays":
                if mark["prims"]:
                    standing[mark["slot"]] = mark
                else:
                    standing.pop(mark["slot"], None)
            else:
                gesture = mark
        if marks:
            out.append((number, list(standing.values()), gesture))
    return out


def problems(board: Board, marks_by_step: dict, moments: dict) -> list[dict]:
    """What code can see is wrong with the marks as they will stand, moment by moment: writing on other writing, on the
    drawing's printed words, on its lines, or outside the picture; a gesture drawn through what is written. ``[{"id", "what", "step"}]``, each mark once."""
    found, seen = [], set()
    for number, standing, gesture in states(marks_by_step, moments):
        here = standing + ([gesture] if gesture else [])
        texts = [(mark, prim["box"]) for mark in here for prim in mark["prims"] if prim["shape"] == "text"]
        for i, (mark, box) in enumerate(texts):
            what = ""
            if box[0] < 0 or box[1] < 0 or box[2] > 1 or box[3] > 1:
                what = "outside the picture"
            elif any(_overlap(box, other) > 0.15 for _, other in texts[:i] + texts[i + 1:]):
                what = "on other writing of the hand"
            elif any(_overlap(box, word) > 0.15 for word in board.words):
                what = "on the drawing's own words"
            elif board.ink([box[0] + 0.2 * (box[2] - box[0]), box[1] + 0.2 * (box[3] - box[1]),
                            box[2] - 0.2 * (box[2] - box[0]), box[3] - 0.2 * (box[3] - box[1])]) > 12:
                what = "on the drawing's lines"          # through its middle, not a line that grazes its edge (four fair values were called wrong)
            if what and mark["id"] not in seen:
                seen.add(mark["id"])
                found.append({"id": mark["id"], "what": what, "step": number})
        if gesture and gesture["id"] not in seen and _through(gesture["prims"], [box for mark, box in texts if mark is not gesture]):
            seen.add(gesture["id"])
            found.append({"id": gesture["id"], "what": "through what the hand has written", "step": number})
    return found


def picture_with(folder, standing: list[dict], gesture: dict | None = None, tags: bool = False, width: int = 900):
    """The drawing on white with marks drawn on it in red (and, with ``tags``, each mark's id in blue): what the model
    looks at when it checks its own work, and what a person looks at before a film is made."""
    from PIL import Image, ImageDraw, ImageFont  # noqa: PLC0415
    art = Image.open(Path(folder) / "whole.png").convert("RGBA")
    image = Image.new("RGBA", art.size, "white")
    image.alpha_composite(art)
    image = image.convert("RGB").resize((width, round(width * art.height / art.width)))
    pen, (W, H) = ImageDraw.Draw(image), image.size

    def font(size):
        try:
            return ImageFont.truetype("DejaVuSans-Bold.ttf", size)
        except OSError:
            return ImageFont.load_default()
    red, blue = (198, 40, 40), (25, 80, 200)
    for mark in list(standing) + ([gesture] if gesture else []):
        where = None
        for prim in mark["prims"]:
            if prim["shape"] == "path":
                points = [(x * W, y * H) for x, y in prim["points"]]
                pen.line(points + (points[:1] if prim.get("closed") else []), fill=(240, 150, 150) if prim.get("soft") else red,
                         width=1 if prim.get("thin") else 9 if prim.get("soft") else 4)
                if prim.get("arrow"):
                    x1, y1 = points[-1]
                    pen.ellipse([x1 - 7, y1 - 7, x1 + 7, y1 + 7], fill=red)
                where = where or points[len(points) // 2]
            else:
                x0, y0, x1, y1 = prim["box"]
                pen.rectangle([x0 * W, y0 * H, x1 * W, y1 * H], fill=(255, 255, 255))
                pen.text((x0 * W + 2, y0 * H), prim["text"], fill=red, font=font(max(10, int((y1 - y0) * H * 0.82))))
                where = (x1 * W, y0 * H)
        if tags and where and mark.get("id"):
            label = mark["id"]
            pen.rectangle([where[0] + 2, where[1] - 14, where[0] + 6 + 8 * len(label), where[1] + 1], fill=(255, 255, 255), outline=blue)
            pen.text((where[0] + 4, where[1] - 14), label, fill=blue, font=font(12))
    return image


def improve(folder, board: Board, ideas: list[dict], marks_by_step: dict, pulls: dict, moments: dict, chapter_of: dict,
            lines: list[str], look, log=print) -> tuple[dict, dict]:
    """The model looks at its own annotated drawing, mark by mark, and what it calls wrong is changed: put on the thing
    it names, written on the side it names, or dropped. The change is kept only when code then finds no more wrong
    with the board than before (``problems``): a look improves the marks or stands aside."""
    import base64  # noqa: PLC0415
    import io  # noqa: PLC0415
    from PIL import Image  # noqa: PLC0415
    shown = states(marks_by_step, moments)
    if not shown:
        return marks_by_step, pulls
    # every mark is in at least one tile: the moments where the most stands first, then where a mark is not yet covered
    wanted, covered = [], set()
    for number, standing, gesture in sorted(shown, key=lambda s: -(len(s[1]) + (1 if s[2] else 0))):
        ids = {m["id"] for m in standing} | ({gesture["id"]} if gesture else set())
        if not ids <= covered:
            wanted.append((number, standing, gesture))
            covered |= ids
        if len(wanted) >= 9:
            break
    wanted.sort(key=lambda s: s[0])
    tiles = [picture_with(folder, standing, gesture, tags=True, width=760) for _, standing, gesture in wanted]
    w, h = tiles[0].size
    columns = 3 if len(tiles) > 4 else 2 if len(tiles) > 1 else 1
    sheet = Image.new("RGB", (columns * w, ((len(tiles) + columns - 1) // columns) * h), "white")
    for i, tile in enumerate(tiles):
        sheet.paste(tile, ((i % columns) * w, (i // columns) * h))
    sheet.thumbnail((2400, 2400))
    buffer = io.BytesIO()
    sheet.save(buffer, format="JPEG", quality=86)
    by_id = {mark["id"]: (number, mark) for number in sorted(moments) for mark in marks_by_step.get(moments[number], [])
             if mark.get("id") and mark["prims"] and mark["id"] in covered}
    listed = [f"  {mark_id}: at S{number}, with the words “{mark['say'] or '(its step)'}”: {mark['kind']}"
              + (f" “{mark['text']}”" if mark["text"] else "") + " on " + " and ".join(f"#{t}" for t in mark["on"])
              for mark_id, (number, mark) in by_id.items()]
    described = [f"  #{n}: {sequence._described(thing)}" for n, thing in enumerate(board.things, 1)]
    try:
        answer = look("\n".join(["THE THINGS IN THE PICTURE:"] + described + ["", "THE ADDITIONS:"] + listed + ["", "THE WORDS:"] + lines),
                      REVIEW_SYSTEM, base64.b64encode(buffer.getvalue()).decode())
    except Exception as exc:  # noqa: BLE001 - nobody looked: the marks stand as they are
        log(f"[annotate] nobody looked at the annotated drawing ({type(exc).__name__}: {str(exc)[:100]})")
        return marks_by_step, pulls
    verdicts = answer.get("marks") if isinstance(answer, dict) and isinstance(answer.get("marks"), dict) else {}
    index = {idea["id"]: idea for idea in ideas}
    changed, said = [], []
    for mark_id, verdict in verdicts.items():
        idea = index.get(str(mark_id))
        if not isinstance(verdict, dict) or idea is None or str(mark_id) not in by_id:
            continue
        what = str(verdict.get("is") or "").strip().lower()
        if what == "pointless":
            idea["_drop"] = True
            changed.append(idea)
            said.append(f"{mark_id} dropped")
        elif what == "wrong_thing":
            tag = _tag(verdict.get("on"))
            if 1 <= tag <= len(board.things) and len(idea["tags"]) == 1 and tag != idea["tags"][0]:
                idea["_was"] = (idea["tags"], idea["things"])
                idea["tags"], idea["things"] = [tag], [board.things[tag - 1]]
                changed.append(idea)
                said.append(f"{mark_id} moved to #{tag}")
        elif what == "unreadable":
            side = str(verdict.get("side") or "").strip().lower()
            if side in ("left", "right", "above", "below"):
                idea["prefer"] = side
                changed.append(idea)
                said.append(f"{mark_id} written {side}")
    if not changed:
        log(f"[annotate] looked at {len(by_id)} mark(s) on the drawing: nothing to change")
        return marks_by_step, pulls
    before = len(problems(board, marks_by_step, moments))
    again, again_pulls = lay_out(board, [idea for idea in ideas if not idea.get("_drop")], moments, chapter_of, log=lambda *a: None)
    after = len(problems(board, again, moments))
    if after > before:
        for idea in changed:                             # the look made it worse by code's measure: it stands aside
            idea.pop("_drop", None)
            idea.pop("prefer", None)
            if "_was" in idea:
                idea["tags"], idea["things"] = idea.pop("_was")
        log(f"[annotate] looked at the annotated drawing and asked for {len(changed)} change(s), not kept: {before} → {after} thing(s) wrong by code's measure")
        return marks_by_step, pulls
    for idea in changed:
        idea.pop("_was", None)
    ideas[:] = [idea for idea in ideas if not idea.get("_drop")]
    log(f"[annotate] looked at the annotated drawing: {'; '.join(said)[:300]} ({before} → {after} wrong by code's measure)")
    return again, again_pulls


# ── the whole of it ──────────────────────────────────────────────────────────────────────────────────────────────────

def seen_right(board: Board, marks: dict, moments: dict, log=print) -> tuple[dict, list]:
    """``(marks, what is still wrong)`` with everything left out that code counts as wrong AND a viewer would see as
    wrong: writing on the drawing's own words or on the hand's other writing hides both, and a line through what is
    written leaves it unread. (A mark known to be wrong used to be kept and only reported; with a small model ideating,
    that is where a bad mark got through: the atom lesson, 2026-10-12.) Writing across a line of the drawing stays: its
    plate keeps it readable. A value that stays leaves its place empty (a wipe), so the order of its slot holds."""
    wrong = problems(board, marks, moments)
    hidden = {p["id"] for p in wrong if p["what"] != "on the drawing's lines"}
    if not hidden:
        return marks, wrong
    left = [f"{mark['id']} {mark['kind']}" for step in marks.values() for mark in step if mark["id"] in hidden and mark["prims"]]
    kept = {}
    for key, step in marks.items():
        here = []
        for mark in step:
            if mark["id"] in hidden and mark["life"] != "stays":
                continue
            here.append({**mark, "prims": [], "text": ""} if mark["id"] in hidden else mark)
        if here:
            kept[key] = here
    log(f"[annotate] {len(left)} mark(s) left out, wrong by code's measure after the look: " + "; ".join(left)[:200])
    return kept, problems(board, kept, moments)


def enabled() -> bool:
    import os  # noqa: PLC0415
    return sequence.enabled() and (knobs.get("HARNESS_ANNOTATE") or "1").strip() != "0"


def ideate(folder, beats: list[dict], look=None, log=print) -> dict | None:
    """``{"marks": {(beat id, step index): [mark, …]}, "pulls": {…}, "wrong": n}`` for one drawing and the beats that show
    it; None when there is nothing to add or nobody to ask."""
    made = sequence.sequence(folder, log=lambda *a: None)
    if not made or made.get("faithful") is False:
        return None
    board = Board(made)
    if not 2 <= len(board.things) <= sequence.MAX_THINGS:
        return None
    if look is None:
        import os  # noqa: PLC0415
        from . import vision_review  # noqa: PLC0415
        look = vision_review.default_judge(models=((knobs.get("HARNESS_ANNOTATE_MODEL") or MODEL).strip(),), temperature=0.0, max_tokens=4000)
    if look is None:
        return None
    import base64  # noqa: PLC0415
    import io  # noqa: PLC0415
    number_of = {int(part["n"]): n for n, thing in enumerate(board.things, 1) for part in [thing["main"]] + thing["marks"] + thing["labels"]}
    moments, narrations, shown, drawn_at, number, lines = {}, {}, {}, {}, 0, []
    for beat in beats:
        beat_id = str(beat.get("id"))
        narrations[beat_id] = str(beat.get("narration") or "")
        shown[beat_id] = {n for step in beat.get("steps") or [] for n in re.findall(r"\d+(?:\.\d+)?", str(step.get("show") or ""))}
        lines.append(f"BEAT {beat_id}. The voice: “{' '.join(narrations[beat_id].split())}”")
        for index, step in enumerate(beat.get("steps") or []):
            if not str(step.get("show") or "").strip():
                continue
            number += 1
            moments[number] = (beat_id, index)
            for n in step.get("draw") or []:
                if n in number_of:
                    drawn_at.setdefault(number_of[n], number)
            lines.append(f"  S{number}, when the voice says “{str(step.get('say') or '').strip()}”: the line “{str(step.get('show')).strip()[:80]}” comes up")
    if number < 1:
        return None
    described = [f"  #{n}: {sequence._described(thing)}" + (f" (drawn at S{drawn_at[n]})" if drawn_at.get(n, 1) > 1 else " (there from the start)")
                 for n, thing in enumerate(board.things, 1)]
    sheet = sequence.numbered(Path(folder) / "whole.png", board.things)
    sheet.thumbnail((2200, 2200))
    buffer = io.BytesIO()
    sheet.save(buffer, format="JPEG", quality=88)
    try:
        answer = look("\n".join(["THE THINGS IN THE PICTURE:"] + described + ["", "THE WORDS:"] + lines), ideate_system(),
                      base64.b64encode(buffer.getvalue()).decode())
    except Exception as exc:  # noqa: BLE001 - no ideas: the drawing stands as it is
        log(f"[annotate] nobody to ideate ({type(exc).__name__}: {str(exc)[:100]})")
        return None
    ideas = honest(answer, board, moments, narrations, shown, drawn_at, log=log)
    chapter_of = {str(beat.get("id")): beat.get("_chapter") for beat in beats}
    marks, pulls = lay_out(board, ideas, moments, chapter_of, log=log)
    if not any(mark["prims"] for step in marks.values() for mark in step):
        return None
    for _ in range(REVIEW_ROUNDS):
        marks, pulls = improve(folder, board, ideas, marks, pulls, moments, chapter_of, lines, look, log=log)
    marks, wrong = seen_right(board, marks, moments, log=log)
    kinds: dict[str, int] = {}
    for step in marks.values():
        for mark in step:
            if mark["prims"]:
                kinds[mark["kind"]] = kinds.get(mark["kind"], 0) + 1
    log("[annotate] on the drawing, with the words: " + ", ".join(f"{count} {kind}" for kind, count in sorted(kinds.items()))
        + f" at {len(marks)} step(s)" + (f"; {len(pulls)} mark(s) drawn earlier, when their value is said" if pulls else "")
        + ("; still wrong by code's measure: " + "; ".join(f"{p['id']} {p['what']}" for p in wrong)[:200] if wrong else ""))
    return {"marks": marks, "pulls": pulls, "wrong": len(wrong)}


def for_lesson(lesson: dict, look=None, log=print) -> dict:
    """Give the steps of every drawing a lesson shows whole what a hand adds to it (``step["annotate"]``).
    ``{"drawings", "annotated", "marks", "wrong"}``. A lesson that already has such steps is left as it is; nothing here
    raises."""
    summary = {"drawings": 0, "annotated": 0, "marks": 0, "wrong": 0}
    if not enabled():
        return summary
    beats_all = [beat for chapter in lesson.get("chapters") or [] for beat in chapter.get("beats") or []]
    if any(step.get("annotate") for beat in beats_all for step in beat.get("steps") or []):
        return summary
    seen = set()
    for beat in beats_all:
        figure = beat.get("figure") if isinstance(beat.get("figure"), dict) else {}
        file = Path(str(figure.get("file") or ""))
        if figure.get("kind") != "picture" or file.name != "whole.png" or figure.get("panels") or str(file) in seen:
            continue
        seen.add(str(file))
        summary["drawings"] += 1
        beats = sequence._beats_on(lesson, str(file))
        try:
            for chapter in lesson.get("chapters") or []:
                for shown in chapter.get("beats") or []:
                    shown["_chapter"] = chapter.get("id")
            made = ideate(file.parent, beats, look=look, log=log)
        except Exception as exc:  # noqa: BLE001 - a drawing nobody can annotate stands as it is
            log(f"[annotate] the drawing stands as it is ({type(exc).__name__}: {str(exc)[:120]})")
            continue
        finally:
            for shown in beats_all:
                shown.pop("_chapter", None)
        if not made:
            continue
        summary["annotated"] += 1
        summary["wrong"] += made["wrong"]
        by_id = {str(b.get("id")): b for b in beats}
        for (beat_id, index), marks in made["marks"].items():
            by_id[beat_id]["steps"][index]["annotate"] = marks
            summary["marks"] += sum(1 for mark in marks if mark["prims"])
        # A mark whose value the voice gives before the plan drew it is drawn at that step instead (``sequence.with_words``
        # had it wait for a later mention): its parts leave the step that brought them and come with the value.
        for (beat_id, index), numbers in made["pulls"].items():
            for other in beats:
                for step in other.get("steps") or []:
                    if step.get("draw"):
                        left = [n for n in step["draw"] if n not in numbers]
                        if left:
                            step["draw"] = left
                        else:
                            step.pop("draw")
            target = by_id[beat_id]["steps"][index]
            target["draw"] = sorted(set(target.get("draw") or []) | set(numbers))
    return summary


def timed(root, log=print) -> dict | None:
    """Every mark of a FILMED lesson with its start and end on the lesson's own clock (seconds of its video), written to
    ``output/annotations.json``. The owner, 2026-10-12: "the starting and ending time stamps for synchrony".

    The times are the film's own record (each chapter's audit says when a mark was made and when it left, on that
    chapter's clock); nothing is worked out a second time. A mark that stays has no end in its own chapter's record:
    it ends when its place is written again or wiped (the first step of the next part of the lesson), else with the
    lesson. With its primitives (shares of the drawing), a file like this is all another player needs to draw the
    marks in step with the voice. None when the lesson has no marks on film.
    """
    root = Path(root)
    try:
        lesson = json.loads((root / "lesson.json").read_text(encoding="utf-8"))
        timeline = {str(entry["id"]): entry for entry in json.loads((root / "timeline.json").read_text(encoding="utf-8"))}
    except (OSError, ValueError, KeyError, TypeError):
        return None
    filmed = {}
    for chapter in lesson.get("chapters") or []:
        audit = root / "output" / f"chapter_{int(chapter['id']):02d}_audit.json"
        first = timeline.get(str(chapter["beats"][0]["id"])) if chapter.get("beats") else None
        if not audit.is_file() or first is None:
            continue
        try:
            records = json.loads(audit.read_text(encoding="utf-8")).get("bounds") or []
        except (OSError, ValueError):
            continue
        for record in records:
            for entry in (record.get("layout") or {}).get("annotations") or []:
                filmed[(str(record.get("beat")), entry.get("id"))] = (float(first["start"]), entry)
    if not filmed:
        return None
    out, standing, end_of_lesson = [], {}, 0.0
    for chapter in lesson["chapters"]:
        for beat in chapter["beats"]:
            entry = timeline.get(str(beat["id"]))
            if entry is None:
                continue
            end_of_lesson = max(end_of_lesson, float(entry["start"]) + float(entry["duration"]))
            figure = beat.get("figure") if isinstance(beat.get("figure"), dict) else {}
            drawing = Path(str(figure.get("file") or "")).parent.name
            for step in beat.get("steps") or []:
                for mark in step.get("annotate") or []:
                    record = filmed.get((str(beat["id"]), mark.get("id"))) if mark.get("prims") else None
                    at = round(record[0] + float(record[1]["start"]), 2) if record else round(float(entry["start"]) + 0.05, 2)
                    stays = mark.get("life") == "stays"
                    if stays:
                        old = standing.pop((drawing, mark.get("slot")), None)
                        if old is not None and old["end"] is None:
                            old["end"] = at
                    if not record:
                        continue                         # a wipe, or a mark the film did not make
                    left = record[1].get("end")
                    item = {"id": mark.get("id"), "chapter": chapter.get("id"), "beat": str(beat["id"]), "drawing": drawing,
                            "kind": mark.get("kind"), "text": mark.get("text", ""), "say": mark.get("say", ""), "on": mark.get("on") or [],
                            "with": record[1].get("with"), "start": at, "end": None if left is None else round(record[0] + float(left), 2),
                            "prims": mark["prims"]}
                    if stays and item["end"] is None:
                        standing[(drawing, mark.get("slot"))] = item
                    out.append(item)
    for item in out:
        if item["end"] is None:
            item["end"] = round(end_of_lesson, 2)
    made = {"version": VERSION, "clock": "seconds from the start of the lesson's video",
            "note": "A mark is on its DRAWING from start to end. While the lesson shows another picture, that drawing and its marks are off screen.",
            "marks": sorted(out, key=lambda item: item["start"])}
    try:
        (root / "output" / "annotations.json").write_text(json.dumps(made, ensure_ascii=False, indent=1), encoding="utf-8")
    except OSError as exc:
        log(f"[annotate] the marks' times could not be written ({exc})")
        return None
    log(f"[annotate] {len(out)} mark(s) with their start and end on the lesson's clock: output/annotations.json")
    return made
