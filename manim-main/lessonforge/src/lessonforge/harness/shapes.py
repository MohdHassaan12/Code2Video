"""Geometry pictures a model writes as POINTS, with every value filled and every claim checked by code.

The quadrilateral videos of 2026-10-20 were right because a person typed the corner points and code
(``longform.geometry``) worked out every angle, mark, verdict and quiz answer. A model asked to draw the same
pictures itself got angles and labels wrong. This module lets a model write such a lesson without being trusted
with a single measured value:

* **Named shapes.** The lesson declares its shapes once (``"shapes": {"arrow": {"points": ..., "polygon": "ABCD",
  "is": ["concave"]}}``) and a beat's figure says ``{"kind": "shape", "use": "arrow", "angles": ["D"]}``. Every beat
  that shows "arrow" shows the same points, in the same frame. ``is`` is what the lesson needs the shape to be; code
  checks the points really make it so.
* **Gaps instead of numbers.** Narration, steps and quiz text write ``{angle D}``, ``{side AB}`` or
  ``{360 - angle A - angle B - angle C}``; code fills in the value from the points (angles rounded so they add up
  exactly, as the picture shows them). A bare number of degrees that the picture does not bear out is a fault.
* **Claims.** "ABCD is a parallelogram", "this shape is concave", a mark of equal or parallel sides, a moving corner
  meant to pass through the collapsed state: each is checked against the points.

``check`` returns the faults; ``repair_prompt`` tells the model exactly what to change; ``fill`` puts the values
in. ``harness/pack.py`` runs that loop for a unit of a teaching pack, and ``writer`` offers the same figure.
"""
from __future__ import annotations

import ast
import copy
import json
import math
import operator
import re

from ..longform import geometry as G

#: What a model is told about the figure. Shared by ``writer.FIGURE_RULES`` and ``pack``.
SHAPE_RULES = """    {"kind":"shape","use":"<a shape named in the lesson's \"shapes\">", ...what to show}
      ANY plane-geometry picture: polygons, their sides, angles, diagonals, midpoints, crossings. The lesson declares
      each shape ONCE in its top-level "shapes": {"<name>": {"points": {"A":[0,0],"B":[4,0.3],"C":[4.6,3.2],
      "D":[0.4,2.8]}, "polygon": "ABCD", "is": ["convex"]}}. Coordinates are plain numbers (about 0 to 6); capital
      letters name points. "is" lists what the lesson NEEDS the shape to be, from: convex, concave, crossed,
      collapsed, parallelogram, rectangle, rhombus, square, kite, trapezium, not parallelogram; code checks the
      points really make it so. Code computes every angle, length, crossing and verdict from the points, so you
      never write a measured value anywhere — see GAPS below.
      What a beat shows (all optional, given beside "use"):
        "angles": ["A", "D"] interior angles with their values; {"at":"D","value":"?","role":"unknown"} hides one;
        "angle_values": false draws the arcs without numbers; "angle_sum": true writes the sum under the shape;
        "segments": ["AC", {"ends":"BD","dashed":true,"role":"wrong"}] diagonals or other segments;
        "midpoints": {"P":"AB"}, "meet": {"E":["AC","BD"]} new points worked out by code;
        "equal": [["AB","CD"]], "parallel": [["AB","DC"]] tick and arrow marks (only if the points bear them out);
        "fills": [{"poly":"ABC","role":"given"}] shaded regions; "verdict": true writes convex / concave / sides
        cross / collapsed under the shape, worked out by code; "readout": ["D", "AB"] a live value under it;
        "hide_points": ["A","B","C","D"] hides the letters; "caption": "short words";
        "move": {"D": [[1.5,2.2], "on AC", [3.0,1.4]]} the corner D travels through these way-points while the
        beat is spoken (angles, readout and verdict follow it every frame). "on AC" is a way-point code puts
        EXACTLY on segment AC between its neighbours, so the shape really collapses there.
      Two to three shapes side by side: {"kind":"shape","panels":[{"use":"first","caption":"convex"},
        {"use":"arrow","caption":"concave","angles":["D"]}]}.
      Keep the SAME "use" on every beat that keeps discussing that shape, so it grows instead of being redrawn:
      each later beat adds what the voice now talks about (an angle, a diagonal, a verdict).
      Steps beside a shape take no "focus": the part the voice names ("side AB", "angle D", "the diagonals")
      lights up by itself as it is said.
      GAPS: never type a value the picture decides. Write a gap and code fills it from the points: {angle D},
      {side AB}, {diagonal AC}, or arithmetic on them: {360 - angle A - angle B - angle C}, {angle A + angle C}.
      A gap names its shape when the beat shows more than one: {arrow: angle D}. Use gaps in the narration
      ("the angle at D is {angle D} degrees"), in a step's "show" ("∠D = {angle D}°") and in a quiz's question,
      options and reasons ("{angle D}°"). 90, 180 and 360 are facts and may be written; every other number of
      degrees must be a gap.
"""

_NEGATION = re.compile(r"\b(?:not|never|no longer|isn't|isnt|cannot|can't|nor|neither|unless|if|would|could|"
                       r"might|may|whether|or)\b", re.I)
#: The names a claim can use, and how code decides each one.
PROPERTY_WORDS = {
    "convex": "convex", "concave": "concave", "non-convex": "concave", "nonconvex": "concave",
    "self-intersecting": "crossed", "crossed": "crossed", "collapsed": "collapsed", "degenerate": "collapsed",
    "parallelogram": "parallelogram", "rectangle": "rectangle", "rhombus": "rhombus", "square": "square",
    "kite": "kite", "trapezium": "trapezium", "trapezoid": "trapezium",
}
_CLAIM = re.compile(
    r"\b(?P<who>this shape|that shape|this quadrilateral|that quadrilateral|the shape|the quadrilateral|it|"
    r"this one|[A-Z]{3,4})\s+(?:is|becomes|stays|remains|turns into|is now|is still)\s+(?:now\s+|still\s+|also\s+)?"
    r"(?:an?\s+)?(?P<word>" + "|".join(sorted(map(re.escape, PROPERTY_WORDS), key=len, reverse=True)) + r")\b")
_DEGREES = re.compile(r"(?<![\w.])(\d+(?:\.\d+)?)\s*(?:°|degrees?\b)", re.I)
# A gap stands on its own ("is {angle D} degrees"). Braces that follow a letter, a closing brace, ^, _ or a
# backslash belong to LaTeX (\text{ BAC }, \frac{a}{b}, ^{\circ}) and are not gaps (2026-11-02 fact test).
_GAP = re.compile(r"(?<![A-Za-z}^_\\])\{([^{}]{1,80})\}")
FACT_DEGREES = {90.0, 180.0, 360.0, 0.0}

_ONES = ("zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen "
         "seventeen eighteen nineteen").split()
_TENS = {"twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90}
_WORD_NUMBER = re.compile(r"\b((?:(?:zero|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|"
                          r"fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty|thirty|forty|fifty|sixty|"
                          r"seventy|eighty|ninety|hundred|and)[\s-]+)+)degrees?\b", re.I)


def _strict_number(tokens: list[str]) -> float | None:
    """[ones hundred [and]] [tens [ones] | ones]; None for anything else ("ninety five one hundred")."""
    i, value = 0, 0
    if len(tokens) >= 2 and tokens[1] == "hundred" and tokens[0] in _ONES[1:10]:
        value, i = _ONES.index(tokens[0]) * 100, 2
        if i < len(tokens) and tokens[i] == "and":
            i += 1
            if i == len(tokens):
                return None
    if i < len(tokens) and tokens[i] in _TENS:
        value += _TENS[tokens[i]]
        i += 1
        if i < len(tokens) and tokens[i] in _ONES[1:10]:
            value += _ONES.index(tokens[i])
            i += 1
    elif i < len(tokens) and tokens[i] in _ONES:
        value += _ONES.index(tokens[i])
        i += 1
    return float(value) if i == len(tokens) and tokens else None


def words_to_number(text: str) -> float | None:
    """The number said just before "degrees": 'seventy, ninety-five and one hundred and ten' -> 110."""
    tokens = [t for t in re.split(r"[\s,-]+", text.lower().strip()) if t]
    best = None
    for start in range(len(tokens) - 1, -1, -1):
        value = _strict_number(tokens[start:])
        if value is not None:
            best = value
    return best


# ── shapes ────────────────────────────────────────────────────────────────────────────────────────────────────────


def _one_shape(spec: dict, shapes: dict) -> tuple[dict, list[str]]:
    """A panel or a single figure with its ``use`` expanded into the named shape's points."""
    issues = []
    out = {k: v for k, v in spec.items() if k not in ("use", "kind")}
    name = str(spec.get("use") or "").strip()
    if name:
        base = shapes.get(name)
        if not isinstance(base, dict):
            return out, [f"the figure uses a shape called '{name}', but the lesson's \"shapes\" has no such shape "
                         f"(it has: {', '.join(shapes) or 'none'})"]
        out = {**{k: copy.deepcopy(v) for k, v in base.items() if k not in ("is", "frame")}, **out}
        out["points"] = {**copy.deepcopy(base.get("points") or {}), **(spec.get("points") or {})}
        if base.get("frame"):
            out.setdefault("frame", base["frame"])
    if not out.get("points"):
        issues.append("a shape figure has no points: give \"use\" with a shape from \"shapes\"")
    # A figure checked a second time (a finished lesson re-checked after an edit) has no "use" any more: it keeps
    # the name it was expanded from, or a gap naming its shape ({dart: angle D}) could no longer find it.
    out["_name"] = name or str(spec.get("_name") or "")
    return out, issues


def _place_on(spec: dict) -> list[str]:
    """Turn "on AC" way-points into points exactly on that segment, between the way-points beside them."""
    issues = []
    points = spec.get("points") or {}
    for mover, path in list((spec.get("move") or {}).items()):
        if not isinstance(path, list):
            issues.append(f"move of {mover} must be a list of way-points")
            continue
        start = points.get(mover)
        fixed = []
        for k, way in enumerate(path):
            if isinstance(way, str):
                m = re.match(r"\s*on\s+([A-Z]\d*'*)([A-Z]\d*'*)\s*$", way)
                if not m or m.group(1) not in points or m.group(2) not in points:
                    issues.append(f"way-point {way!r} of {mover}: write \"on XY\" with two points of the shape")
                    continue
                a, b = G._pt(points[m.group(1)]), G._pt(points[m.group(2)])
                before = G._pt(fixed[-1]) if fixed else G._pt(start)
                after = next((G._pt(w) for w in path[k + 1:] if not isinstance(w, str)), None)
                hit = G.line_meet(before, after, a, b) if before and after else None
                if hit is None or not G.on_segment(hit, a, b, 1e-6):
                    t = 0.5
                    if before:     # the point of AC nearest the way-point before
                        d = G.sub(b, a)
                        t = max(0.05, min(0.95, ((before[0] - a[0]) * d[0] + (before[1] - a[1]) * d[1]) /
                                          max(d[0] ** 2 + d[1] ** 2, 1e-9)))
                    hit = G.lerp(a, b, t)
                fixed.append([round(hit[0], 6), round(hit[1], 6)])
            elif G._pt(way):
                fixed.append([float(way[0]), float(way[1])])
            else:
                issues.append(f"way-point {way!r} of {mover} is not two numbers or \"on XY\"")
        spec["move"][mover] = fixed
    return issues


def expand(figure: dict, shapes: dict) -> tuple[dict, list[str]]:
    """A beat's ``shape`` figure as ``shape_figure`` draws it: points filled in from the named shapes."""
    issues: list[str] = []
    if isinstance(figure.get("panels"), list) and figure["panels"]:
        panels = []
        for i, panel in enumerate(figure["panels"][:3]):
            if not isinstance(panel, dict):
                continue
            one, bad = _one_shape(panel, shapes)
            issues += [f"panel {i + 1}: {b}" for b in bad]
            one.setdefault("key", str(one.get("caption") or one.get("_name") or "").lower())
            panels.append(one)
        return {"kind": "shape", "panels": panels}, issues
    one, bad = _one_shape(figure, shapes)
    issues += bad
    issues += _place_on(one)
    issues += _drag(one)
    return {"kind": "shape", **one}, issues


def _drag(spec: dict) -> list[str]:
    """``"drag": "A"`` on a triangle: code chooses the way-points of corner A (``geometry.drag_path``), so the angles change
    on the screen while their sum line stays at 180 (video-quality plan S10). Only where the key is present; a figure that
    already has a ``move`` keeps it (so a figure expanded a second time is not changed). Without ``angles`` the three
    interior angles are shown, and ``angle_sum`` is on: the live sum is the point of the picture."""
    if "drag" not in spec:
        return []
    mover = spec.get("drag")
    mover = mover.get("vertex") if isinstance(mover, dict) else mover
    mover = str(mover or "").strip()
    path = G.drag_path(spec.get("points") or {}, spec.get("polygon"), mover)
    if path is None:
        return [f"drag {mover!r}: \"drag\" names one corner of a triangle (a shape whose polygon has three points, "
                "not in a line), for example \"drag\": \"A\""]
    if spec.get("move"):
        return []
    spec["move"] = {mover: path}
    spec.setdefault("angles", G.names(spec.get("polygon")))
    spec.setdefault("angle_sum", True)
    return []


def models(figure: dict) -> list[tuple[str, G.Model, dict]]:
    """(name, model, spec) for each shape a figure shows."""
    parts = figure.get("panels") if isinstance(figure.get("panels"), list) else [figure]
    return [(str(p.get("_name") or ""), G.Model(p), p) for p in parts if isinstance(p, dict)]


def properties(model: G.Model) -> set[str]:
    """Every name from ``PROPERTY_WORDS`` the points make true."""
    if len(model.boundary) < 3:
        return set()
    st = model.status()["kind"]
    out = {{"degenerate": "collapsed"}.get(st, st)}
    if len(model.boundary) != 4 or st not in ("convex", "concave"):
        return out
    A, B, C, D = (model.points[k] for k in model.boundary)
    par1, par2 = G.are_parallel(A, B, D, C), G.are_parallel(A, D, B, C)
    ab, bc, cd, da = G.dist(A, B), G.dist(B, C), G.dist(C, D), G.dist(D, A)
    right = all(abs(v - 90.0) < G.ANGLE_TOL for v in model.interior().values())
    if par1 and par2:
        out.add("parallelogram")
        if right:
            out.add("rectangle")
        if G.are_equal(ab, bc):
            out.add("rhombus")
        if right and G.are_equal(ab, bc):
            out.add("square")
    else:
        out.add("not parallelogram")
    if (par1 != par2) and st == "convex":
        out.add("trapezium")
    if (G.are_equal(ab, bc) and G.are_equal(cd, da)) or (G.are_equal(bc, cd) and G.are_equal(da, ab)):
        out.add("kite")
    return out


def describe(name: str, model: G.Model) -> str:
    """One line of facts a repair is given, so the model sees what its points really make."""
    if len(model.boundary) < 3:
        return f"{name}: points {json.dumps(model.points)}"
    st = model.status()
    angles = shown_angles(model)
    bits = [f"{name} ({''.join(model.boundary)}): {st['kind']} — {st['why']}"]
    if angles:
        bits.append("angles " + ", ".join(f"{k} {v:g}°" for k, v in angles.items()))
    props = sorted(properties(model) - {st["kind"], "collapsed"})
    if props:
        bits.append("also " + ", ".join(props))
    facts = model.facts()
    if "diagonals_meet_inside" in facts:
        bits.append("diagonals cross inside" if facts["diagonals_meet_inside"] else "diagonals do NOT cross")
    return "; ".join(bits)


def shown_angles(model: G.Model) -> dict:
    """Interior angles in whole degrees as the picture writes them (they add up exactly)."""
    from ..longform.shape_figure import round_to_total  # noqa: PLC0415 - the picture's own rounding (imports manim)
    inner = model.interior()
    return round_to_total(inner, 180.0 * (len(inner) - 2)) if inner else {}


def _round_angles(model: G.Model) -> dict:
    try:
        return shown_angles(model)
    except ImportError:                    # no manim: the same largest-remainder rounding
        inner = model.interior()
        floors = {k: math.floor(v) for k, v in inner.items()}
        left = int(round(180.0 * (len(inner) - 2))) - sum(floors.values())
        for k in sorted(inner, key=lambda k: inner[k] - floors[k], reverse=True)[:max(0, left)]:
            floors[k] += 1
        return floors


# ── gaps ──────────────────────────────────────────────────────────────────────────────────────────────────────────

_OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv}


def _evaluate(expr: str) -> float:
    def ev(node):
        if isinstance(node, ast.Expression):
            return ev(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return float(node.value)
        if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
            return _OPS[type(node.op)](ev(node.left), ev(node.right))
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
            return -ev(node.operand)
        raise ValueError("only numbers, + - * / and brackets")
    return ev(ast.parse(expr, mode="eval"))


def _nice(value: float, kind: str) -> str:
    if kind == "angle":
        return f"{round(value):g}"
    v = round(value, 1)
    return f"{v:g}"


def gap_value(text: str, figure: dict) -> tuple[str | None, float | None, str]:
    """('228', 228.0, '') for '{angle D}', or (None, None, why it cannot be filled)."""
    shown = models(figure)
    body = text.strip()
    which = None
    m = re.match(r"^\s*([\w -]+?)\s*:\s*(.+)$", body)
    if m and not re.match(r"^(?:angle|side|diagonal|length)\b", m.group(1), re.I):
        which, body = m.group(1).strip(), m.group(2)
    chosen = [s for s in shown if which is None or s[0] == which or str(s[2].get("caption") or "") == which]
    if which is not None and not chosen:
        return None, None, f"gap {{{text}}} names the shape '{which}', which this beat does not show"
    kind = "length"

    def ref(match):
        nonlocal kind
        what, name = match.group(1).lower(), match.group(2)
        hits = []
        for _, model, _spec in chosen:
            if what == "angle":
                if name in model.boundary:
                    rounded = _round_angles(model)
                    if name in rounded:
                        hits.append(float(rounded[name]))
                elif len(G.names(name)) == 3:            # angle ABC between two rays
                    p, at, q = G.names(name)
                    a = model.angle({"at": at, "from": p, "to": q})
                    if a:
                        hits.append(a["value"])
            else:
                length = model.length(name)
                if length is not None:
                    hits.append(length)
        if what == "angle":
            kind = "angle"
        if not hits:
            raise KeyError(f"{what} {name}")
        if len(set(round(h, 6) for h in hits)) > 1:
            raise LookupError(f"{what} {name}")
        return repr(hits[0])
    try:
        expr = re.sub(r"\b(angle|side|diagonal|length)\s+([A-Z]\d*'*(?:[A-Z]\d*'*){0,2})", ref, body, flags=re.I)
        if re.search(r"[A-Za-z]", expr):
            return None, None, (f"gap {{{text}}} can only hold angle X, side XY, diagonal XY, numbers and + - * /")
        value = _evaluate(expr)
    except KeyError as exc:
        return None, None, f"gap {{{text}}}: this beat's picture has no {exc.args[0]}"
    except LookupError as exc:
        return None, None, f"gap {{{text}}}: {exc.args[0]} differs between the shapes shown; name one: {{name: ...}}"
    except (ValueError, SyntaxError, ZeroDivisionError) as exc:
        return None, None, f"gap {{{text}}} is not arithmetic code can work out ({exc})"
    return _nice(value, kind), value, ""


def fill_text(text: str, figure: dict | None, quiet: bool = False) -> tuple[str, list[str], list[float]]:
    """Text with its gaps filled from the figure, the faults, and the values used.

    ``quiet`` (a lesson that mixes subject kits, ``settle`` decides): a gap on a beat with no shape figure belongs to
    another kit, or to no kit, and is reported there (``kits.orphan_gaps``), so it is left as written without a fault.
    """
    issues, values = [], []
    if not isinstance(text, str) or "{" not in text:
        return text, issues, values

    def put(match):
        if not figure or figure.get("kind") != "shape":
            if not quiet:
                issues.append(f"gap {{{match.group(1)}}} on a beat with no shape figure")
            return match.group(0)
        shown, value, why = gap_value(match.group(1), figure)
        if shown is None:
            issues.append(why)
            return match.group(0)
        values.append(value)
        return shown
    return _GAP.sub(put, text), issues, values


# ── the checks ───────────────────────────────────────────────────────────────────────────────────────────────────


def _degree_numbers(text: str) -> list[float]:
    out = [float(m.group(1)) for m in _DEGREES.finditer(text or "")]
    for m in _WORD_NUMBER.finditer(text or ""):
        n = words_to_number(m.group(1))
        if n is not None:
            out.append(n)
    return out


def _allowed_degrees(figure: dict | None, filled: list[float]) -> set[float]:
    allowed = set(FACT_DEGREES) | {round(v) for v in filled}
    if figure and figure.get("kind") == "shape":
        for _, model, spec in models(figure):
            for v in _round_angles(model).values():
                allowed.add(float(v))
            for item in spec.get("angles") or []:
                a = model.angle(item)
                if a:
                    allowed.add(float(round(a["value"])))
    return allowed


def check_shapes(shapes: dict) -> list[str]:
    """Faults in the lesson's declared shapes: missing points, and an "is" the points do not make true."""
    issues = []
    if not isinstance(shapes, dict):
        return ["\"shapes\" must be an object of named shapes"]
    for name, spec in shapes.items():
        if not isinstance(spec, dict):
            issues.append(f"shape '{name}' is not an object")
            continue
        model = G.Model(spec)
        issues += [f"shape '{name}': {n}" for n in model.notes]
        missing = [p for p in G.names(spec.get("polygon")) if p not in model.points]
        if missing:
            issues.append(f"shape '{name}': polygon names {', '.join(missing)} but those points are not given")
        need = spec.get("is") or []
        need = [need] if isinstance(need, str) else need
        have = properties(model)
        for want in need:
            w = PROPERTY_WORDS.get(str(want).lower().strip(), str(want).lower().strip())
            if w == "not parallelogram":
                ok = "parallelogram" not in have
            else:
                ok = w in have
            if not ok:
                issues.append(f"shape '{name}' must be {want}, but its points make it: {describe(name, model)}. "
                              "Move its points so it is " + str(want))
    return issues


def check_figure(figure: dict, narration: str, beat_ref: str) -> list[str]:
    """Faults in one beat's (expanded) shape figure against its own words."""
    issues = []
    shown = models(figure)
    for name, model, spec in shown:
        label = f"shape '{name}'" if name else "the shape"
        for note in model.notes:
            issues.append(f"{beat_ref}: {label}: {note}")
        model.checked_marks("equal")
        model.checked_marks("parallel")
        for note in model.notes:
            if "dropped" in note and f"{beat_ref}: {label}: {note}" not in issues:
                issues.append(f"{beat_ref}: {label}: {note}")
        for item in spec.get("angles") or []:
            if not model.angle(item):
                issues.append(f"{beat_ref}: {label}: angle {item!r} is not an angle of this picture")
        for item in spec.get("segments") or []:
            ends = item.get("ends") if isinstance(item, dict) else item
            if not model.seg(str(ends or "")):
                issues.append(f"{beat_ref}: {label}: segment {ends!r} joins points that are not in the picture")
        for k in spec.get("hide_points") or []:
            if k not in model.points:
                issues.append(f"{beat_ref}: {label}: hide_points names {k!r}, not a point")
    # A moving corner: what the words say happens must happen on the way.
    single = figure.get("panels") is None and shown
    if single and figure.get("move"):
        from ..longform.shape_figure import at_alpha  # noqa: PLC0415
        seen = []
        legs = max(len(path) for path in figure["move"].values()) or 1
        moments = sorted({i / 100 for i in range(101)} | {k / legs for k in range(legs + 1)})
        for t in moments:
            kind = G.Model(at_alpha(figure, t)).status()["kind"]
            kind = {"degenerate": "collapsed"}.get(kind, kind)
            if not seen or seen[-1] != kind:
                seen.append(kind)
        said = {PROPERTY_WORDS[w] for w in PROPERTY_WORDS if re.search(rf"\b{re.escape(w)}\b", narration, re.I)}
        for kind in said & {"convex", "concave", "collapsed", "crossed"}:
            if kind not in seen:
                issues.append(f"{beat_ref}: the words say the moving shape is {kind} at some point, but along its "
                              f"way-points it is only {' then '.join(seen)}. Change the way-points (\"on XY\" puts one "
                              "exactly on a segment)")
    # A transferred angle: the copy must land on the angle it is said to equal (video-quality plan S10).
    if single and figure.get("transfer"):
        from ..longform.shape_figure import angle_key  # noqa: PLC0415
        move = figure["transfer"]
        why = G.transfer_fault(shown[0][1], move)
        if why:
            issues.append(f"{beat_ref}: {why}")
        elif not all(angle_key(move.get(k)) in {angle_key(i) for i in figure.get("angles") or []} for k in ("from", "to")):
            issues.append(f"{beat_ref}: transfer: both angles must be listed in \"angles\" (the copy leaves one and lands on the other)")
    elif figure.get("transfer") or figure.get("drag"):
        if figure.get("panels"):
            issues.append(f"{beat_ref}: \"transfer\" and \"drag\" work on one shape, not on panels")
    # Claims about THIS shape: "ABCD is a parallelogram", "the shape is now concave".
    if not figure.get("move"):
        for sentence in re.split(r"(?<=[.!?])\s+", narration):
            for m in _CLAIM.finditer(sentence):
                before = sentence[:m.start("word")]
                if _NEGATION.search(before[max(0, len(before) - 40):]):
                    continue
                want = PROPERTY_WORDS[m.group("word").lower()]
                who = m.group("who")
                named = bool(re.fullmatch(r"[A-Z]{3,4}", who))
                # a pronoun is checked only against a quadrilateral (a triangle with test points is no claim's subject)
                pool = [(n, md) for n, md, _ in shown if
                        (("".join(md.boundary) == who or set(G.names(who)) == set(md.boundary)) if named
                         else len(md.boundary) == 4)]
                if pool and not any(want in properties(md) for _, md in pool):
                    facts = "; ".join(describe(n or "the shape", md) for n, md in pool)
                    issues.append(f"{beat_ref}: the words say “{m.group(0)}”, but the picture is: {facts}")
    return issues


def _quiz_texts(quiz: dict) -> list[tuple[str, str]]:
    out = [("question", quiz.get("question")), ("explain", quiz.get("explain"))]
    out += [(f"option {i + 1}", o) for i, o in enumerate(quiz.get("options") or [])]
    out += [(f"reason {i + 1}", o) for i, o in enumerate(quiz.get("why") or [])]
    return [(k, v) for k, v in out if isinstance(v, str)]


def _mixed_lesson(lesson: dict) -> bool:
    """True when ``lesson`` draws from several subject kits and mixing is on: beats of another kit are not ours to flag."""
    try:
        from .. import kits  # noqa: PLC0415 - the kits package is pure; the import stays out of module load
        return kits.multi(lesson)
    except Exception:  # noqa: BLE001 - geometry checks go on exactly as before if the registry cannot answer
        return False


def settle(raw: dict) -> tuple[dict, list[str]]:
    """The model's lesson with shapes expanded and gaps filled, and every fault found on the way.

    The returned lesson is drawable even with faults (a broken gap is left as written, a mark the points do not bear
    out is dropped by the figure itself); the faults are what a repair is asked to fix.
    """
    lesson = copy.deepcopy(raw)
    shapes = lesson.get("shapes") or {}
    issues = check_shapes(shapes) if shapes else []
    # One frame per named shape, so it keeps its size from beat to beat (way-points of its moves included).
    spans: dict[str, list[float]] = {}
    for ch in lesson.get("chapters") or []:
        for beat in ch.get("beats") or []:
            fig = beat.get("figure")
            if not isinstance(fig, dict) or fig.get("kind") != "shape":
                continue
            for part in (fig.get("panels") if isinstance(fig.get("panels"), list) else [fig]):
                name = str((part or {}).get("use") or "")
                base = shapes.get(name) if isinstance(shapes, dict) else None
                if not isinstance(base, dict):
                    continue
                pts = [G._pt(p) for p in (base.get("points") or {}).values()]
                pts += [G._pt(w) for path in ((part or {}).get("move") or {}).values() for w in (path or [])
                        if not isinstance(w, str)]
                if (part or {}).get("drag"):             # the corner's tour is part of the frame, in every beat of this shape
                    mover = (part["drag"].get("vertex") if isinstance(part["drag"], dict) else part["drag"])
                    tour = G.drag_path({**(base.get("points") or {}), **(part.get("points") or {})},
                                       base.get("polygon") or part.get("polygon"), str(mover or "").strip())
                    pts += [G._pt(w) for w in tour or []]
                pts = [p for p in pts if p]
                if pts:
                    box = spans.setdefault(name, [math.inf, math.inf, -math.inf, -math.inf])
                    box[:] = [min(box[0], *(p[0] for p in pts)), min(box[1], *(p[1] for p in pts)),
                              max(box[2], *(p[0] for p in pts)), max(box[3], *(p[1] for p in pts))]
    for name, box in spans.items():
        if isinstance(shapes.get(name), dict) and not shapes[name].get("frame"):
            shapes[name]["frame"] = [round(v, 3) for v in box]
    quiet = _mixed_lesson(raw)          # False for every geometry-only lesson, so nothing below changes for it
    number = 0
    for ci, ch in enumerate(lesson.get("chapters") or [], start=1):
        for beat in ch.get("beats") or []:
            number += 1
            ref = f"beat {number} (chapter {ci})"
            fig = beat.get("figure")
            if isinstance(fig, dict) and fig.get("kind") == "shape":
                fig, bad = expand(fig, shapes)
                issues += [f"{ref}: {b}" for b in bad]
                beat["figure"] = fig
            elif isinstance(fig, dict) and fig.get("use"):
                issues.append(f"{ref}: a figure with \"use\" must have \"kind\": \"shape\"")
            fig = beat.get("figure") if isinstance(beat.get("figure"), dict) else None
            used: list[float] = []
            text, bad, vals = fill_text(str(beat.get("narration") or ""), fig, quiet)
            beat["narration"], used = text, used + vals
            issues += [f"{ref} narration: {b}" for b in bad]
            for k, step in enumerate(beat.get("steps") or []):
                for field in ("say", "show"):
                    text, bad, vals = fill_text(str(step.get(field) or ""), fig, quiet)
                    step[field], used = text, used + vals
                    issues += [f"{ref} step {k + 1} {field}: {b}" for b in bad]
            quiz = beat.get("quiz") if isinstance(beat.get("quiz"), dict) else None
            if quiz:
                for field in ("question", "explain"):
                    text, bad, vals = fill_text(str(quiz.get(field) or ""), fig, quiet)
                    quiz[field], used = text, used + vals
                    issues += [f"{ref} quiz {field}: {b}" for b in bad]
                for field in ("options", "why"):
                    filled = []
                    for i, item in enumerate(quiz.get(field) or []):
                        text, bad, vals = fill_text(str(item), fig, quiet)
                        filled.append(text)
                        used += vals
                        issues += [f"{ref} quiz {field[:-1] if field == 'options' else 'reason'} {i + 1}: {b}" for b in bad]
                    quiz[field] = filled
                opts = [re.sub(r"\s+", " ", o.strip().lower()) for o in quiz.get("options") or []]
                if len(set(opts)) < len(opts) and not (quiet and not (fig and fig.get("kind") == "shape")):
                    issues.append(f"{ref} quiz: two options come out the same once filled ({quiz.get('options')}): "
                                  "each wrong option must be a different number or answer")
            if fig and fig.get("kind") == "shape":
                issues += check_figure(fig, beat["narration"], ref)
            if not (fig and fig.get("kind") == "shape"):
                continue                 # numbers on a beat with no shape are not about a shape
            allowed = _allowed_degrees(fig, used)
            texts = [("narration", beat["narration"])] + [(f"step {k + 1}", s.get("show") or "")
                                                          for k, s in enumerate(beat.get("steps") or [])]
            texts += [(f"quiz {k}", v) for k, v in (_quiz_texts(quiz) if quiz else [])]
            for where, text in texts:
                for n in _degree_numbers(text):
                    if round(n) not in allowed and n not in allowed:
                        issues.append(f"{ref} {where}: says {n:g} degrees, which the picture does not show "
                                      f"(write a gap such as {{angle D}} instead of a number)")
    return lesson, issues


def unfilled(lesson: dict) -> bool:
    """True while any gap is left unfilled (such a lesson must not be filmed)."""
    # Only the words: a figure's points serialised as JSON ({"A": [1, 1], ...}) read like a gap and failed a whole
    # lesson that had none (2026-10-26, unit 1 of the new quadrilaterals file). Captions are still read.
    def words(x):
        if isinstance(x, str):
            yield x
        elif isinstance(x, dict):
            for v in x.values():
                yield from words(v)
        elif isinstance(x, list):
            for v in x:
                yield from words(v)
    return any(_GAP.search(w) for c in lesson.get("chapters") or [] for w in words(c.get("beats")))


def repair_prompt(raw: dict, issues: list[str]) -> str:
    shapes = raw.get("shapes") or {}
    facts = "\n".join("- " + describe(n, G.Model(s)) for n, s in shapes.items() if isinstance(s, dict))
    return ("Code checked your lesson against its own pictures and found these faults:\n"
            + "\n".join(f"- {i}" for i in issues[:40])
            + ("\n\nWhat your shapes' points make, worked out by code:\n" + facts if facts else "")
            + "\n\nReturn the WHOLE lesson again as JSON in the same shape, with every fault fixed. Change only what a "
              "fault needs: move points, fix a gap, change a word. Keep every other word as it is.\n\nYOUR LESSON:\n"
            + json.dumps(raw, ensure_ascii=False))
