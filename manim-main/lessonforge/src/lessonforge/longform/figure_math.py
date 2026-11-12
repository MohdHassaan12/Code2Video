"""Geometry the figures are drawn from — pure functions, no Manim, so the critic can use them too.

A model asks for a figure with numbers AND with labels, and the two can disagree. On
the first user-made lesson a right triangle was requested with legs 3 and 4 but
labelled "3 m" on a leg and "4 m" on the hypotenuse: the drawing would have shown a
3-4-5 triangle under words describing a 3-√7-4 one. The rule here is that **the
labelled numbers are what the narration says, so they win**: when two sides carry a
number the third is computed from them and the drawing follows. Anything that cannot
be reconciled is returned as an issue for the critic to report.
"""
from __future__ import annotations

import math
import re

_LATEX = re.compile(r"\\(?:text|mathrm|mathbf|operatorname)\s*\{([^{}]*)\}")
_ANGLE_WORDS = ("\\theta", "θ", "theta", "\\alpha", "α", "alpha", "\\beta", "β", "beta", "\\phi", "φ")


def plain(label: str) -> str:
    """A label with LaTeX wrappers removed (for reading its number, not for display)."""
    text = str(label or "")
    for _ in range(3):
        text = _LATEX.sub(r"\1", text)
    return text.replace("\\,", " ").replace("\\;", " ").replace("\\ ", " ").replace("$", "").strip()


def number_in(label) -> float | None:
    """The side length a label states: '3 m' → 3, 'hypotenuse = 4 m' → 4, 'ground' → None, '√7' → 2.65."""
    text = plain(label)
    root = re.search(r"(?:\\sqrt\s*\{?|√)\s*(\d+(?:\.\d+)?)", str(label or "") + " " + text)
    if root:
        return math.sqrt(float(root.group(1)))
    if any(w in str(label or "").lower() for w in ("?",)) and not re.search(r"\d", text):
        return None
    numbers = re.findall(r"(?<![\w.])(\d+(?:\.\d+)?)(?![\w]*\^)", text)
    if not numbers:
        return None
    value = float(numbers[-1] if "=" in text else numbers[0])
    return value if value > 0 else None


def is_angle_label(label) -> bool:
    """'θ', '\\theta', 'theta' on a SIDE means the model wanted the angle marked, not the side named."""
    text = plain(label).strip().lower()
    return text in ("θ", "theta", "α", "alpha", "β", "beta", "φ", "phi") or str(label or "").strip() in _ANGLE_WORDS


def resolve_right_triangle(params: dict) -> dict:
    """Side lengths to DRAW: ``{"a", "b", "c", "source", "issues"}`` (a horizontal, b vertical, c hypotenuse)."""
    def num(key):
        try:
            value = float(params.get(key))
            return value if value > 0 else None
        except (TypeError, ValueError):
            return None

    labels = params.get("labels") if isinstance(params.get("labels"), dict) else {}
    said = {k: (None if is_angle_label(labels.get(k)) else number_in(labels.get(k))) for k in ("a", "b", "c")}
    given = {k: num(k) for k in ("a", "b", "c")}
    issues: list[str] = []

    def third(a, b, c):
        if a and b:
            return a, b, math.hypot(a, b)
        if a and c and c > a:
            return a, math.sqrt(c * c - a * a), c
        if b and c and c > b:
            return math.sqrt(c * c - b * b), b, c
        return None

    labelled = sum(1 for v in said.values() if v)
    if labelled >= 2:
        if labelled == 3 and abs(said["a"] ** 2 + said["b"] ** 2 - said["c"] ** 2) > 0.02 * said["c"] ** 2:
            issues.append(f"the three labelled sides {said['a']:g}, {said['b']:g}, {said['c']:g} do not make a right triangle")
        sides = third(said["a"], said["b"], None) if labelled == 3 else third(said["a"], said["b"], said["c"])
        if sides is None:
            issues.append("a labelled leg is not shorter than the labelled hypotenuse")
        else:
            a, b, c = sides
            for key, drawn in (("a", a), ("b", b)):
                if given[key] and abs(given[key] - drawn) > 0.03 * max(drawn, given[key]):
                    issues.append(f"side {key} was requested as {given[key]:g} but the labels make it {drawn:g}; "
                                  "drawn from the labels")
            return {"a": a, "b": b, "c": c, "source": "labels", "issues": issues}
    sides = third(given["a"], given["b"], given["c"]) or (3.0, 4.0, 5.0)
    a, b, c = sides
    for key, drawn in (("a", a), ("b", b), ("c", c)):
        if said[key] and abs(said[key] - drawn) > 0.03 * max(drawn, said[key]):
            issues.append(f"side {key} is labelled {said[key]:g} but drawn {drawn:g}")
    return {"a": a, "b": b, "c": c, "source": "params", "issues": issues}


def figure_issues(figure) -> list[str]:
    """What is inconsistent in a requested figure (empty when fine or not checkable)."""
    if not isinstance(figure, dict):
        return []
    params = figure.get("params") if isinstance(figure.get("params"), dict) else figure
    if figure.get("kind") == "right_triangle":
        return resolve_right_triangle(params)["issues"]
    if figure.get("kind") == "bars":
        out = []
        for part in params.get("parts") or []:
            if not isinstance(part, dict):
                continue
            try:
                n, d = int(float(part.get("n", 0))), int(float(part.get("d", 1)))
            except (TypeError, ValueError):
                continue
            match = re.fullmatch(r"\s*(\d+)\s*/\s*(\d+)\s*", plain(part.get("label", "")))
            if match and (int(match.group(1)), int(match.group(2))) != (n, d):
                out.append(f"a bar is labelled {match.group(1)}/{match.group(2)} but drawn as {n}/{d}")
            if d and n > d:
                out.append(f"a bar is asked to fill {n} of {d} parts")
        return out
    if figure.get("kind") == "graph":
        return settle_graph(dict(params))[1]
    from .. import kits  # noqa: PLC0415 - a subject kit's own figure kinds (docs/engine/kits.md)
    kit = kits.serving(figure.get("kind"))
    return kits.guarded(f"{kit.name} figure_issues", lambda: kit.figure_issues(params), []) if kit is not None else []


def settle_graph(spec: dict) -> tuple[dict, list[str]]:
    """A graph spec made to agree with its own functions: a point whose given ``y`` is not on the first curve loses
    its ``y`` (the figure then puts it ON the curve) and its label is rewritten when the label is a coordinate pair.
    Returns ``(spec, issues)``; the spec is a copy. The writer drew a taxi fare with dots off the line (2026-10-16)."""
    import numpy as np  # noqa: PLC0415
    spec = dict(spec)
    issues = []
    functions = [str(f) for f in (spec.get("functions") or [])][:3]
    fs = [graph_function(f) for f in functions]
    for text, f in zip(functions, fs):
        if f is None:
            issues.append(f"the function {text[:40]!r} cannot be drawn")
    first = next((f for f in fs if f is not None), None)
    if first is None:
        if not functions:
            issues.append("a graph with no function")
        return spec, issues
    points = []
    for pt in spec.get("points") or []:
        if not isinstance(pt, dict):
            continue
        pt = dict(pt)
        try:
            x = float(pt.get("x"))
            on = float(first(np.array([x]))[0])
        except (TypeError, ValueError):
            points.append(pt)
            continue
        if pt.get("y") is not None and np.isfinite(on):
            try:
                y = float(pt["y"])
            except (TypeError, ValueError):
                y = float("nan")
            span = max(1.0, abs(on))
            if not (np.isfinite(y) and abs(y - on) <= 0.02 * span):
                issues.append(f"the point at x = {_nice(x):g} was given y = {pt['y']} but the line is at {_nice(on):g}")
                pt.pop("y", None)
                label = str(pt.get("label") or "")
                if re.fullmatch(r"\s*\(\s*-?[\d.]+\s*,\s*-?[\d.]+\s*\)\s*", label):
                    pt["label"] = f"({_nice(x):g}, {_nice(on):g})"
        points.append(pt)
    if "points" in spec:
        spec["points"] = points
    return spec, issues


# ── graphs: y = f(x), read and checked here, drawn by figures.graph ─────────────────────────────────────────────────
#
# A graph arrives from outside (Lesson Forge's computed plots, a lesson file) with its functions as text. Text that is
# evaluated inside a render must not be able to do anything but arithmetic, so it is parsed, every node is checked
# against a short list, and only then compiled. The facts a reader could check (where two curves meet, where a curve
# has a hole or an asymptote) are computed here from the functions themselves, never taken on trust: the first Forge
# plot of 1/(x - 2) came with no asymptote, and the hole of (x^2 - 1)/(x - 1) was not marked.

import ast  # noqa: E402

_ALLOWED_CALLS = {"sin", "cos", "tan", "sqrt", "exp", "log", "log10", "abs", "floor", "ceil", "arcsin", "arccos", "arctan"}
_ALLOWED_NAMES = {"x", "pi", "e"}
_NODES = (ast.Expression, ast.BinOp, ast.UnaryOp, ast.Constant, ast.Name, ast.Load, ast.Call, ast.Attribute,
          ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow, ast.Mod, ast.FloorDiv, ast.USub, ast.UAdd)


def graph_function(text: str):
    """``"2*x - 1"`` (also ``x^2``, ``np.sqrt(x)``, ``math.sin(x)``) → a vectorised numpy function, or None.

    Only numbers, ``x``, ``pi``, ``e``, + - * / // % ** and a short list of functions are accepted.
    """
    import numpy as np  # noqa: PLC0415 - figure_math is imported where numpy is not wanted at import time
    source = str(text or "").strip().replace("^", "**")
    source = re.sub(r"\b(?:np|numpy|math)\.", "", source)
    source = re.sub(r"(\d)\s*([a-z(])", r"\1*\2", source)          # 2x → 2*x, 3(x+1) → 3*(x+1)
    source = re.sub(r"\)\s*([x(\d])", r")*\1", source)               # (x+1)(x-1) → (x+1)*(x-1)
    source = re.sub(r"\bx\s*\(", "x*(", source)
    if not source or len(source) > 160:
        return None
    try:
        tree = ast.parse(source, mode="eval")
    except SyntaxError:
        return None
    for node in ast.walk(tree):
        if not isinstance(node, _NODES):
            return None
        if isinstance(node, ast.Name) and node.id not in _ALLOWED_NAMES | _ALLOWED_CALLS:
            return None
        if isinstance(node, ast.Call) and not (isinstance(node.func, ast.Name) and node.func.id in _ALLOWED_CALLS
                                               and len(node.args) == 1 and not node.keywords):
            return None
        if isinstance(node, ast.Attribute):
            return None
        if isinstance(node, ast.Constant) and not isinstance(node.value, (int, float)):
            return None
    names = {name: getattr(np, name) for name in _ALLOWED_CALLS if name != "abs"} | {"abs": np.abs, "pi": np.pi, "e": np.e}
    code = compile(tree, "<graph>", "eval")

    def f(xs):
        with np.errstate(all="ignore"):
            out = eval(code, {"__builtins__": {}}, {**names, "x": np.asarray(xs, dtype=float)})  # noqa: S307 - checked above
        return np.broadcast_to(np.asarray(out, dtype=float), np.shape(xs)).astype(float)
    try:
        f(np.linspace(-1, 1, 3))
    except Exception:  # noqa: BLE001 - parses but cannot be evaluated (a call on nothing): not a function of x
        return None
    return f


def _nice(value: float) -> float:
    """A value as a reader would write it: 2.0000001 → 2, 0.4999 → 0.5."""
    for digits in (0, 1, 2):
        if abs(value - round(value, digits)) < 1e-6 * max(1.0, abs(value)):
            return float(round(value, digits))
    return float(round(value, 3))


def graph_facts(functions: list[str], x_range=(-5.0, 5.0), y_range=None, samples: int = 2001) -> dict:
    """What a graph shows, computed: ``{"functions", "x_range", "y_range", "asymptotes", "holes", "meeting_points",
    "issues"}``. Functions that cannot be read are left out and named in ``issues``."""
    import numpy as np  # noqa: PLC0415
    issues, fs, kept = [], [], []
    for text in functions or []:
        f = graph_function(text)
        if f is None:
            issues.append(f"the function {str(text)[:40]!r} cannot be drawn")
            continue
        fs.append(f)
        kept.append(str(text))
    a, b = (float(v) for v in (x_range or (-5, 5)))
    if not b > a:
        a, b = -5.0, 5.0
    xs = np.linspace(a, b, samples)
    asymptotes, holes = [], []
    candidates = sorted({_nice(v) for v in np.arange(math.ceil(a * 2) / 2, b + 1e-9, 0.5)} | {0.0} if a < 0 < b else
                        {_nice(v) for v in np.arange(math.ceil(a * 2) / 2, b + 1e-9, 0.5)})
    for n, f in enumerate(fs):
        for c in candidates:
            if not a < c < b:
                continue
            at = f(np.array([c]))[0]
            h = 1e-4
            left, right = f(np.array([c - h]))[0], f(np.array([c + h]))[0]
            if not (np.isfinite(left) and np.isfinite(right)):
                continue
            if not np.isfinite(at) or abs(at) > 1e8:
                if abs(left - right) < 1e-2 and abs(left) < 1e6:     # the curve closes over the gap: a hole
                    holes.append({"curve": n, "x": _nice(c), "y": _nice((left + right) / 2)})
                elif abs(left) > 50 or abs(right) > 50 or np.sign(left) != np.sign(right):
                    asymptotes.append(_nice(c))
            elif abs(left) > 1e3 and abs(right) > 1e3:
                asymptotes.append(_nice(c))
    asymptotes = sorted(set(asymptotes))
    if y_range is None or not (isinstance(y_range, (list, tuple)) and len(y_range) == 2 and float(y_range[1]) > float(y_range[0])):
        values = np.concatenate([f(xs) for f in fs]) if fs else np.array([0.0])
        values = values[np.isfinite(values)]
        if values.size:
            lo, hi = np.percentile(values, [3, 97]) if asymptotes else (values.min(), values.max())
        else:
            lo, hi = -5.0, 5.0
        lo, hi = min(float(lo), 0.0), max(float(hi), 0.0)
        pad = max((hi - lo) * 0.12, 1.0)
        lo, hi = math.floor(lo - pad), math.ceil(hi + pad)
        y_range = (lo, hi)
    lo, hi = (float(v) for v in y_range)
    meeting = []
    if len(fs) >= 2:
        d = fs[0](xs) - fs[1](xs)
        for i in range(len(xs) - 1):
            if not (np.isfinite(d[i]) and np.isfinite(d[i + 1])):
                continue
            if d[i] == 0 or d[i] * d[i + 1] < 0:
                x0, x1 = xs[i], xs[i + 1]
                if d[i] != 0:
                    for _ in range(60):
                        mid = (x0 + x1) / 2
                        dm = fs[0](np.array([mid]))[0] - fs[1](np.array([mid]))[0]
                        if np.sign(dm) == np.sign(fs[0](np.array([x0]))[0] - fs[1](np.array([x0]))[0]):
                            x0 = mid
                        else:
                            x1 = mid
                x = (x0 + x1) / 2 if d[i] != 0 else xs[i]
                y = fs[0](np.array([x]))[0]
                if (np.isfinite(y) and lo <= y <= hi and all(abs(x - m["x"]) > 1e-3 for m in meeting)
                        and not any(abs(x - s) < 1e-3 for s in asymptotes)
                        and not any(abs(x - h["x"]) < 1e-3 for h in holes)):
                    meeting.append({"x": _nice(x), "y": _nice(y)})
    return {"functions": kept, "x_range": [a, b], "y_range": [lo, hi], "asymptotes": asymptotes, "holes": holes,
            "meeting_points": meeting[:4], "issues": issues}


# --- chemical equations (the "reaction" figure) ------------------------------------------------------------------
# A model-written scene labelled two water molecules "H2O2" in a lesson about exactly that mistake (2026-10-20):
# nothing checked that the balls, the formula and the counts agreed. Here code reads the equation and EVERYTHING
# drawn (balls, formula labels, the atom count of each side) comes from that one reading, so they cannot disagree.

_ELEMENT = re.compile(r"([A-Z][a-z]?)(\d*)")
_ARROW = re.compile(r"\s*(?:->|→|=>|⟶|\\rightarrow|\\to|=)\s*")
_SUBSCRIPT = str.maketrans("₀₁₂₃₄₅₆₇₈₉", "0123456789")
MAX_COEFFICIENT = 6


def _plain_formula(text) -> str:
    """'\\mathrm{H_2O}' / 'H₂O' / 'H_{2}O' → 'H2O'."""
    text = re.sub(r"\\(?:mathrm|text|ce)\s*\{([^{}]*)\}", r"\1", str(text))
    text = re.sub(r"_\{?(\d+)\}?", r"\1", text)
    return text.translate(_SUBSCRIPT).replace(" ", "")


def formula_atoms(formula: str) -> list[tuple[str, int]]:
    """'H2O' → [('H', 2), ('O', 1)]; 'Ca(OH)2' → [('Ca', 1), ('O', 2), ('H', 2)] (order of first appearance).

    Raises ValueError for anything that is not a formula (a word, an unclosed bracket).
    """
    text = _plain_formula(formula)
    if not text or not re.fullmatch(r"[A-Za-z0-9()]+", text):
        raise ValueError(f"not a formula: {formula!r}")
    stack: list[dict] = [{}]
    order: list[str] = []
    i = 0
    while i < len(text):
        ch = text[i]
        if ch == "(":
            stack.append({})
            i += 1
        elif ch == ")":
            if len(stack) == 1:
                raise ValueError(f"unbalanced bracket in {formula!r}")
            group = stack.pop()
            m = re.match(r"\d+", text[i + 1:])
            times = int(m.group()) if m else 1
            i += 1 + (len(m.group()) if m else 0)
            for el, n in group.items():
                stack[-1][el] = stack[-1].get(el, 0) + n * times
        else:
            m = _ELEMENT.match(text, i)
            if not m:
                raise ValueError(f"not a formula: {formula!r}")
            el, n = m.group(1), int(m.group(2) or 1)
            if el not in order:
                order.append(el)
            stack[-1][el] = stack[-1].get(el, 0) + n
            i = m.end()
    if len(stack) != 1 or not stack[0]:
        raise ValueError(f"not a formula: {formula!r}")
    return [(el, stack[0][el]) for el in order]


def _species(term: str) -> dict:
    term = term.strip()
    m = re.match(r"^(\?|□|\\square|\[\s*\]|_+|\d+)?\s*(?:\\,|\;)?\s*(.+)$", term)
    if not m:
        raise ValueError(f"not a term: {term!r}")
    coefficient, formula = m.group(1), m.group(2).strip()
    unknown = coefficient is not None and not coefficient.isdigit()
    n = int(coefficient) if coefficient and coefficient.isdigit() else 1
    if not 1 <= n <= MAX_COEFFICIENT:
        raise ValueError(f"coefficient {n} is more than can be drawn")
    formula = _plain_formula(formula)
    return {"n": n, "unknown": unknown, "formula": formula, "atoms": formula_atoms(formula)}


def parse_equation(equation: str) -> dict:
    """'2H2 + O2 -> 2H2O' → {"left": [species…], "right": [species…]}; a species is n, unknown, formula, atoms.

    A coefficient may be unknown ("? N2 + ? H2 -> ? NH3", "□N2"): it is drawn and counted as one.
    """
    text = str(equation or "").replace("\\,", " ")
    sides = _ARROW.split(text, maxsplit=1)
    if len(sides) != 2:
        raise ValueError(f"no arrow in {equation!r}")
    out = {}
    for name, side in zip(("left", "right"), sides):
        terms = [t for t in re.split(r"\s+\+\s+|\s*\+\s*(?=[\d?□\\A-Z(_\[])", side.strip()) if t.strip()]
        if not terms:
            raise ValueError(f"an empty side in {equation!r}")
        out[name] = [_species(t) for t in terms]
    return out


def atom_counts(side: list[dict]) -> dict[str, int]:
    """How many atoms of each element one side holds, in order of first appearance."""
    counts: dict[str, int] = {}
    for sp in side:
        for el, k in sp["atoms"]:
            counts[el] = counts.get(el, 0) + k * sp["n"]
    return counts


def is_balanced(parsed: dict) -> bool:
    return atom_counts(parsed["left"]) == atom_counts(parsed["right"]) and \
        not any(sp["unknown"] for side in parsed.values() for sp in side)


def balance(parsed: dict, fixed: dict | None = None) -> dict | None:
    """The smallest whole coefficients (each 1..MAX_COEFFICIENT) that balance the equation, ignoring the ones it
    gives: ``{"left": [n…], "right": [n…]}``, or None when there are none that small. Brute force: four species at six
    each is 1296 tries. ``fixed`` holds some coefficients: {"right": {0: 3}} asks for a balance with 3 of the first
    product, the smallest such."""
    import itertools
    fixed = fixed or {}
    species = parsed["left"] + parsed["right"]
    split = len(parsed["left"])
    for total in range(len(species), MAX_COEFFICIENT * len(species) + 1):
        for ns in itertools.product(range(1, MAX_COEFFICIENT + 1), repeat=len(species)):
            if sum(ns) != total or any(ns[(0 if part == "left" else split) + i] != n
                                       for part, held in fixed.items() for i, n in held.items()):
                continue
            side = lambda part, numbers: atom_counts([{**sp, "n": n} for sp, n in zip(part, numbers)])  # noqa: E731
            if side(parsed["left"], ns[:split]) == side(parsed["right"], ns[split:]):
                return {"left": list(ns[:split]), "right": list(ns[split:])}
    return None


def formula_latex(sp: dict) -> str:
    """'2', 'H2O' → '2\\,\\mathrm{H_2O}'; an unknown coefficient is a box."""
    body = re.sub(r"(\d+)", r"_{\1}", sp["formula"])
    lead = r"\square\," if sp["unknown"] else (f"{sp['n']}\\," if sp["n"] > 1 else "")
    return lead + r"\mathrm{" + body + "}"


def _round_nice(value: float) -> float:
    """A value as a lesson writes it: whole when it is whole, else two decimals."""
    return float(round(value)) if abs(value - round(value)) < 1e-6 else round(value, 2)


def float_case(params: dict) -> dict:
    """What floats, how deep, from mass, volume and the liquid's density: the numbers a ``float`` figure draws.

    The ice baseline (2026-11-02) had a model-written scene with the cube resting ON the water while the voice said 92
    per cent of it was under; code knows where a floating object sits, so code puts it there. Each object gives two of
    mass (g), volume (cm³) and density (g/cm³); code works out the third, the share under the surface
    (density / liquid density, at most 1) and the volumes below and above. Returns {"liquid": {...}, "objects": [...],
    "issues": [...]}; an object with too little to go on is left out and named in "issues".
    """
    liquid = params.get("liquid") if isinstance(params.get("liquid"), dict) else {}
    rho_l = number_in(liquid.get("density")) if liquid.get("density") is not None else None
    rho_l = rho_l if rho_l and rho_l > 0 else 1.0
    out = {"liquid": {"name": str(liquid.get("name") or "water")[:20], "density": _round_nice(rho_l)},
           "objects": [], "issues": []}
    for i, obj in enumerate((params.get("objects") if isinstance(params.get("objects"), list) else [])[:3]):
        if not isinstance(obj, dict):
            continue
        m, v, rho = (number_in(obj.get(k)) if obj.get(k) is not None else None for k in ("mass", "volume", "density"))
        if m and v:
            rho = m / v
        elif rho and v:
            m = rho * v
        elif rho and m:
            v = m / rho
        if not (rho and rho > 0):
            out["issues"].append(f"object {i} ({obj.get('name', '?')}) needs two of mass, volume, density")
            continue
        v = v or 100.0
        share = min(1.0, rho / rho_l)
        sinks = rho > rho_l + 1e-9
        out["objects"].append({"name": str(obj.get("name") or f"object {i + 1}")[:18], "mass": _round_nice(m) if m else None,
                               "volume": _round_nice(v), "density": round(rho, 2), "share": round(share, 4),
                               "under": _round_nice(share * v), "above": _round_nice(max(0.0, v - share * v)),
                               "sinks": sinks, "role": str(obj.get("role") or "given")})
    return out
