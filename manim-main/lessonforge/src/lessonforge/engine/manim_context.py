"""Manim context — what an LLM needs to know to write Manim that actually runs here.

The question this answers ("how do I give the code-writing agent Manim knowledge —
docs? GitHub? a search model? MCP?") has three plausible answers and one right one for
this repo:

* **A web-search model** (OpenRouter `:online`, a search plugin) reads *the internet's*
  Manim — a decade of ManimGL/ManimCE-0.x blog posts whose APIs no longer exist. It is
  also unmeterable and uncacheable: a per-call web spend on every icon-sized task, with
  a different answer each time. This repo meters every LLM edge on purpose.
* **An MCP docs server** is a live dependency. A headless bulk run or a cron job with no
  MCP session would silently lose its context and start guessing.
* **The installed package is the ground truth.** `manim==0.20.1` is sitting on disk, and
  it is the exact version whose signatures the generated code must satisfy. Introspecting
  it is free, offline, deterministic, and cannot drift from what will run.

So: the index is built by introspecting the installed Manim (in a subprocess, so the
server process never pays the import), cached as JSON, and retrieved with plain keyword
scoring — no vector DB, no embedding call, no new dependency. Alongside it sits a small
curated corpus of *simulation patterns* written against this repo's own contract, which
is the part the API listing cannot teach: how a physical system is expressed as
`build()` + `animate()`.

And the honest caveat, which is why the design does not lean harder on context: what
makes model-written Manim safe here is not how well it was briefed, it is that the code
is executed and verified before it is ever allowed near a video (`sim_gen.verify`).
Context reduces retries; the verifier is what makes a failure impossible to ship.
"""
from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import sys
import time

logger = logging.getLogger(__name__)

from .. import paths as _paths
INDEX_PATH = str(_paths.cache() / "manim_api_index.json")
INDEX_TTL = float(os.getenv("MANIM_INDEX_TTL", str(30 * 24 * 3600)))   # 30 days

# Introspection runs out-of-process: importing manim costs seconds and pulls in a
# graphics stack the API server has no reason to hold.
_DUMP_SCRIPT = r"""
import inspect, json, sys
import manim
out = []
names = getattr(manim, "__all__", None) or dir(manim)
for name in names:
    if name.startswith("_"):
        continue
    obj = getattr(manim, name, None)
    if not inspect.isclass(obj):
        continue
    try:
        sig = str(inspect.signature(obj))
    except (ValueError, TypeError):
        sig = "(...)"
    doc = (inspect.getdoc(obj) or "").strip().split("\n")[0][:180]
    bases = [b.__name__ for b in getattr(obj, "__mro__", [])[1:5]]
    out.append({"name": name, "signature": sig[:300], "doc": doc, "bases": bases})
json.dump({"version": getattr(manim, "__version__", "?"), "classes": out}, sys.stdout)
"""


def _load_cached():
    try:
        if not os.path.exists(INDEX_PATH):
            return None
        if time.time() - os.path.getmtime(INDEX_PATH) > INDEX_TTL:
            return None
        with open(INDEX_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if data.get("classes") else None
    except Exception:
        return None


def build_index(force=False):
    """Introspect the installed Manim into a cached JSON index. Never raises."""
    if not force:
        cached = _load_cached()
        if cached:
            return cached
    try:
        proc = subprocess.run([sys.executable, "-c", _DUMP_SCRIPT],
                              capture_output=True, text=True, timeout=180)
        if proc.returncode != 0 or not proc.stdout.strip():
            logger.warning("[MANIM-CTX] introspection failed (rc=%s): %s",
                           proc.returncode, (proc.stderr or "")[-300:])
            return None
        data = json.loads(proc.stdout)
    except Exception as e:
        logger.warning("[MANIM-CTX] introspection unavailable: %s", e)
        return None
    try:
        os.makedirs(os.path.dirname(INDEX_PATH), exist_ok=True)
        with open(INDEX_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f)
    except Exception:
        pass
    logger.info("[MANIM-CTX] indexed %d Manim classes (v%s)",
                len(data.get("classes") or []), data.get("version"))
    return data


# ── curated simulation patterns ───────────────────────────────────────────────
# Written against THIS repo's contract (build/animate, no Scene access, everything
# self-contained). The API listing above can teach signatures; only worked examples
# can teach the shape of the answer — which is the part models get wrong.

PATTERNS = [
    {
        "id": "trajectory",
        "keywords": "projectile trajectory parabola thrown ball launch arc path flight motion under gravity",
        "title": "A body moving along a computed path, with the path revealed behind it",
        "code": '''
def build(width, height):
    ax = Axes(x_range=[0, 10, 2], y_range=[0, 5, 1],
              x_length=width * 0.9, y_length=height * 0.8,
              axis_config={"include_tip": False, "stroke_width": 2})
    def y(x):
        return 0.8 * x - 0.08 * x * x
    curve = ax.plot(y, x_range=[0, 10], stroke_width=3)
    curve.set_stroke(opacity=0.35)
    ball = Dot(ax.c2p(0, 0), radius=0.11)
    return VGroup(ax, curve, ball)

def animate(group, run_time):
    ax, curve, ball = group[0], group[1], group[2]
    return AnimationGroup(
        MoveAlongPath(ball, curve, run_time=run_time),
        Create(curve.copy().set_stroke(opacity=1.0), run_time=run_time),
        lag_ratio=0.0,
    )
''',
    },
    {
        "id": "wave",
        "keywords": "wave oscillation sine propagate vibration string sound light amplitude frequency period",
        "title": "A travelling wave — the general shape for anything that oscillates",
        "code": '''
def build(width, height):
    ax = Axes(x_range=[0, 4 * PI, PI], y_range=[-1.5, 1.5, 1],
              x_length=width * 0.9, y_length=height * 0.6,
              axis_config={"include_tip": False, "stroke_width": 2})
    wave = ax.plot(lambda x: np.sin(x), x_range=[0, 4 * PI], stroke_width=4)
    return VGroup(ax, wave)

def animate(group, run_time):
    ax, wave = group[0], group[1]
    def update(mob, alpha):
        phase = alpha * 2 * TAU
        mob.become(ax.plot(lambda x: np.sin(x - phase),
                           x_range=[0, 4 * PI], stroke_width=4))
    return UpdateFromAlphaFunc(wave, update, run_time=run_time)
''',
    },
    {
        "id": "orbit",
        "keywords": "orbit revolve circular motion planet electron satellite rotation around centre period",
        "title": "One body orbiting another — parametric position from alpha",
        "code": '''
def build(width, height):
    r = min(width, height) * 0.32
    sun = Dot(ORIGIN, radius=0.22, color=YELLOW)
    orbit = Circle(radius=r, stroke_width=2, stroke_opacity=0.4)
    planet = Dot(RIGHT * r, radius=0.11, color=BLUE)
    return VGroup(sun, orbit, planet)

def animate(group, run_time):
    orbit, planet = group[1], group[2]
    r = orbit.width / 2
    def update(mob, alpha):
        theta = alpha * TAU
        mob.move_to(np.array([r * np.cos(theta), r * np.sin(theta), 0.0]))
    return UpdateFromAlphaFunc(planet, update, run_time=run_time)
''',
    },
    {
        "id": "pendulum",
        "keywords": "pendulum swing rod bob oscillate angle simple harmonic",
        "title": "A rigid body swinging about a pivot — rebuild the geometry each frame",
        "code": '''
def build(width, height):
    pivot = UP * (height * 0.35)
    length = height * 0.6
    theta0 = 0.5
    end = pivot + length * np.array([np.sin(theta0), -np.cos(theta0), 0.0])
    rod = Line(pivot, end, stroke_width=4)
    bob = Dot(end, radius=0.18, color=BLUE)
    hinge = Dot(pivot, radius=0.06)
    return VGroup(hinge, rod, bob)

def animate(group, run_time):
    hinge, rod, bob = group[0], group[1], group[2]
    pivot = hinge.get_center()
    length = np.linalg.norm(bob.get_center() - pivot)
    def update(mob, alpha):
        theta = 0.5 * np.cos(alpha * 2 * TAU)
        end = pivot + length * np.array([np.sin(theta), -np.cos(theta), 0.0])
        mob[1].put_start_and_end_on(pivot, end)
        mob[2].move_to(end)
    return UpdateFromAlphaFunc(group, update, run_time=run_time)
''',
    },
    {
        "id": "particles",
        "keywords": "particles gas molecules diffusion random brownian collision temperature kinetic",
        "title": "Many bodies moving independently — deterministic pseudo-random paths",
        "code": '''
def build(width, height):
    box = Rectangle(width=width * 0.8, height=height * 0.8, stroke_width=2)
    dots = VGroup()
    for i in range(12):
        a = i * 0.7
        start = np.array([np.cos(a * 3) * width * 0.3, np.sin(a * 5) * height * 0.3, 0.0])
        dots.add(Dot(start, radius=0.07, color=BLUE))
    return VGroup(box, dots)

def animate(group, run_time):
    box, dots = group[0], group[1]
    starts = [d.get_center().copy() for d in dots]
    w, h = box.width / 2 - 0.1, box.height / 2 - 0.1
    def update(mob, alpha):
        for i, d in enumerate(mob):
            vx, vy = np.cos(i * 2.1 + 1), np.sin(i * 1.7 + 2)
            x = starts[i][0] + vx * alpha * 4
            y = starts[i][1] + vy * alpha * 4
            # Reflect off the walls instead of leaving the box.
            x = w - abs((abs(x + w) % (4 * w)) - 2 * w)
            y = h - abs((abs(y + h) % (4 * h)) - 2 * h)
            d.move_to(np.array([x, y, 0.0]))
    return UpdateFromAlphaFunc(dots, update, run_time=run_time)
''',
    },
    {
        "id": "growing_graph",
        "keywords": "graph plot curve data grows over time value increases decay exponential temperature chart",
        "title": "A curve drawn as its independent variable advances, with a moving readout dot",
        "code": '''
def build(width, height):
    ax = Axes(x_range=[0, 10, 2], y_range=[0, 10, 2],
              x_length=width * 0.85, y_length=height * 0.75,
              axis_config={"include_tip": False, "stroke_width": 2})
    curve = ax.plot(lambda x: 10 * (1 - np.exp(-0.4 * x)), x_range=[0, 10], stroke_width=4)
    dot = Dot(ax.c2p(0, 0), radius=0.09, color=YELLOW)
    return VGroup(ax, curve, dot)

def animate(group, run_time):
    ax, curve, dot = group[0], group[1], group[2]
    return AnimationGroup(
        Create(curve, run_time=run_time),
        MoveAlongPath(dot, curve, run_time=run_time),
        lag_ratio=0.0,
    )
''',
    },
    {
        "id": "flow",
        "keywords": "flow field current arrows vector field wind fluid streamlines force field magnetic electric",
        "title": "A field of arrows whose lengths change — a system's state, not an object's position",
        "code": '''
def build(width, height):
    arrows = VGroup()
    for i in range(-2, 3):
        for j in range(-1, 2):
            start = np.array([i * width * 0.16, j * height * 0.22, 0.0])
            arrows.add(Arrow(start, start + RIGHT * 0.5, buff=0, stroke_width=3,
                             max_tip_length_to_length_ratio=0.35))
    return arrows

def animate(group, run_time):
    starts = [a.get_start().copy() for a in group]
    def update(mob, alpha):
        for i, arrow in enumerate(mob):
            mag = 0.25 + 0.5 * (1 + np.sin(alpha * TAU + starts[i][0])) / 2
            arrow.put_start_and_end_on(starts[i], starts[i] + RIGHT * mag)
    return UpdateFromAlphaFunc(group, update, run_time=run_time)
''',
    },
    {
        "id": "transform_shape",
        "keywords": "morph transform rearrange split merge area proof rearrangement geometry pieces",
        "title": "Geometry rearranging into other geometry — motion that carries an argument",
        "code": '''
def build(width, height):
    s = min(width, height) * 0.3
    square = Square(side_length=s, stroke_width=3)
    pieces = VGroup(*[
        Square(side_length=s / 2, stroke_width=2).move_to(
            square.get_center() + np.array([(i % 2 - 0.5) * s / 2, (i // 2 - 0.5) * s / 2, 0.0]))
        for i in range(4)
    ])
    return VGroup(square, pieces)

def animate(group, run_time):
    square, pieces = group[0], group[1]
    targets = pieces.copy()
    for i, piece in enumerate(targets):
        piece.shift(np.array([(i % 2 - 0.5) * 1.4, (i // 2 - 0.5) * 1.0, 0.0]))
    return AnimationGroup(
        FadeOut(square, run_time=run_time * 0.3),
        Transform(pieces, targets, run_time=run_time),
        lag_ratio=0.2,
    )
''',
    },
]


# ── retrieval ─────────────────────────────────────────────────────────────────

_STOP = {"the", "a", "an", "of", "and", "with", "for", "in", "on", "to", "is", "are",
         "as", "at", "by", "that", "this", "it", "its", "into", "over", "show", "shows",
         "showing", "animation", "animated", "scene", "simulation", "simulate"}


def _tokens(text):
    return [w for w in re.findall(r"[a-z]+", (text or "").lower())
            if len(w) > 2 and w not in _STOP]


def _score(query_tokens, blob):
    """Overlap score with a 5-character prefix match, so inflections count.

    Same heuristic as `assets.icon_match_strength` — deliberately: this repo already
    learned that exact-token matching under-hits on plurals and participles.
    """
    if not query_tokens:
        return 0
    hay = set(_tokens(blob))
    hay_prefix = {w[:5] for w in hay}
    return sum(1 for q in query_tokens if q in hay or q[:5] in hay_prefix)


def relevant_patterns(query, limit=2):
    """The curated simulation patterns closest to a description."""
    qt = _tokens(query)
    ranked = sorted(PATTERNS, key=lambda p: -_score(qt, p["keywords"] + " " + p["title"]))
    hits = [p for p in ranked if _score(qt, p["keywords"] + " " + p["title"]) > 0]
    if not hits:                      # never leave the writer with no worked example
        hits = [p for p in PATTERNS if p["id"] in ("trajectory", "wave")]
    return hits[:limit]


def relevant_api(query, limit=14, index=None):
    """Signatures of the installed Manim classes closest to a description."""
    data = index if index is not None else build_index()
    if not data:
        return []
    qt = _tokens(query)
    scored = []
    for cls in data.get("classes") or []:
        blob = f"{cls['name']} {cls.get('doc', '')} {' '.join(cls.get('bases') or [])}"
        s = _score(qt, blob)
        # Anything an animation is built from is worth surfacing even on a weak
        # keyword match — these are the names a wrong guess most often invents.
        if cls["name"] in _ALWAYS:
            s += 3
        if s:
            scored.append((s, cls))
    scored.sort(key=lambda t: (-t[0], t[1]["name"]))
    return [c for _, c in scored[:limit]]


_ALWAYS = {"Axes", "NumberPlane", "VGroup", "Dot", "Line", "Arrow", "Circle", "Square",
           "Rectangle", "Polygon", "MoveAlongPath", "UpdateFromAlphaFunc", "Rotate",
           "Transform", "AnimationGroup", "Create", "FadeIn", "FadeOut",   # no Succession: it needs a live scene
           "ValueTracker", "ParametricFunction", "Arc", "Text", "MathTex"}


def context_for(description, api_limit=14, pattern_limit=2):
    """The prompt block handed to the simulation writer for one element."""
    blocks = []
    api = relevant_api(description, limit=api_limit)
    if api:
        lines = [f"{c['name']}{c['signature']}" + (f"   # {c['doc']}" if c.get("doc") else "")
                 for c in api]
        blocks.append("## Installed Manim API (version on this machine — these signatures "
                      "are authoritative; anything not listed may not exist)\n"
                      + "\n".join(lines))
    pats = relevant_patterns(description, limit=pattern_limit)
    if pats:
        blocks.append("## Worked patterns in the required build/animate form\n" + "\n".join(
            f"### {p['title']}\n```python{p['code']}```" for p in pats))
    return "\n\n".join(blocks)
