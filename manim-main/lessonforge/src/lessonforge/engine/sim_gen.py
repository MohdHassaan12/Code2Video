"""Generated simulations — the one place an LLM is allowed to write Manim.

The gap, stated precisely: the transpiler renders a storyboard *deterministically*, and
that is why layout, structure, theming and the overlap probe all hold. But its
vocabulary describes a **composition** — things that appear, sit, move next to each
other, and leave. It has no way to say *this system evolves*: a projectile tracing its
arc, a wave propagating, particles diffusing, a pendulum swinging, an orbit closing.
Every one of those becomes a static picture of a moving thing, which is the single
biggest reason a physics explainer reads as a slideshow.

Filling that with prompts would mean handing whole-scene codegen back to an LLM — the
exact move this repo removed on purpose ("code owns structure, models own content").
So the scope is inverted instead: the model writes **one bounded function pair for one
element**, never a scene, and the transpiler still owns everything around it.

    def build(width, height) -> Mobject      # the system at t=0, inside a w x h box
    def animate(group, run_time) -> Animation # how it evolves; nothing else changes

That is the same shape as `asset_gen`'s `def draw(ax)`, for the same reason: the
harness owns the figure so the model cannot get the figure wrong.

**Verification is what makes this safe — not the prompt.** A generated simulation is
accepted only if it *runs*: the harness steps the animation frame by frame with no
renderer at all (`begin()` / `interpolate(alpha)` / `finish()`, ~1s, no ffmpeg, no
video) and rejects it unless

  * `build()` returns a real Mobject with actual points (an empty `VGroup` runs fine
    and renders nothing — "exit code 0 proves nothing", the blank-icon lesson),
  * the geometry stays INSIDE its allocated box for the whole animation (a simulation
    that wanders would manufacture clipped-text violations and send the repair agent
    chasing ghosts — the same round-trip discipline `viz_helpers.sustain` follows), and
  * something actually MOVES (a model that returns a no-op animation is the moving
    equivalent of a blank icon).

Everything else follows the house pattern: metered once per description and cached
forever (`assets/simulation_cache/`), resolved SERVER-SIDE at codegen time so the
render subprocess needs no key and no network, and degrading to a static element on
every failure path. Knobs: `SIM_GEN` (1), `SIM_GEN_TIMEOUT` (90s),
`SIM_GEN_REPAIR_ROUNDS` (1).
"""
import hashlib
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor

from .llm import call_llm_with_fallback, strip_code_fences, get_genai_client
from . import manim_context
from .code_safety import forbidden_reason

logger = logging.getLogger(__name__)

from .. import paths as _paths
CACHE_DIR = str(_paths.cache("assets", "simulation", create=False))

TIMEOUT = int(os.getenv("SIM_GEN_TIMEOUT", "90"))
REPAIR_ROUNDS = int(os.getenv("SIM_GEN_REPAIR_ROUNDS", "1"))

# The box a simulation is built into. Chosen to leave room for a title band and a
# caption; the transpiler places the returned group like any other diagram.
BOX_W = 6.0
BOX_H = 4.0
# A lesson places the drawing's box centred in its frame, so the drawing must stay inside that box. A motion clip
# (harness/clip.py) frames its camera on wherever the drawing really goes, so there only its SIZE must fit the box:
# a parallelogram drawn off to the left (x from -3.6 to 0.1, 3.7 wide in a 6-wide box) was refused twice for it.
CENTRED = True
# Containment tolerance: the box is a contract, but a stroke's half-width legitimately
# pokes past the geometric bound.
BOX_SLACK = 1.12
#: Shortest a piece of text may be, as a share of its box's height (0.1 units in a 4-unit box, about 17 px in a lesson).
MIN_TEXT_SHARE = 0.025


def enabled():
    return os.getenv("SIM_GEN", "1") != "0"


def slug(description):
    s = re.sub(r"[^a-z0-9]+", "_", (description or "").strip().lower()).strip("_")
    return (s or "sim")[:56]


def _keyed(prefix, folder, description):
    """The cache file for ONE description. The name used to be its first 56 letters alone, so two descriptions that
    begin alike shared a file: on the ice lesson (2026-10-19) a scene asked for again with what it had to show added
    at its END got the old scene back from the cache, and a look at the identical picture called it cured. A longer
    description now carries a hash of all of it. A file under the old name is still used when its sidecar says it
    was made for exactly this description, so nothing already paid for is made again."""
    desc = (description or "").strip()
    whole = re.sub(r"[^a-z0-9]+", "_", desc.lower()).strip("_")
    legacy = os.path.join(folder, f"{prefix}_{slug(desc)}.py")
    if len(whole) <= 56:
        return legacy
    keyed = os.path.join(folder, f"{prefix}_{slug(desc)}_{hashlib.sha1(desc.encode('utf-8')).hexdigest()[:10]}.py")
    if not os.path.exists(keyed) and os.path.exists(legacy):
        try:
            with open(legacy + ".json", encoding="utf-8") as f:
                if (json.load(f).get("description") or "").strip() == desc:
                    return legacy
        except (OSError, ValueError):
            pass
    return keyed


def cached_path(description):
    return _keyed("sim", CACHE_DIR, description)


# ── The prompt ────────────────────────────────────────────────────────────────

_SYSTEM = (
    "You write Manim animation code for educational physics/maths simulations. You "
    "reply with Python source ONLY — no markdown fences, no prose, no explanation."
)

_PROMPT = """Write a Manim simulation of: {description}

Reply with exactly two module-level functions and nothing else:

    def build(width, height):
        \"\"\"Return ONE Mobject (usually a VGroup) showing the system at t = 0.\"\"\"

    def animate(group, run_time):
        \"\"\"Return ONE Animation that evolves `group` over run_time seconds.\"\"\"

Hard rules — the harness around you owns everything else:
- `from manim import *` and `import numpy as np` are ALREADY done. Import nothing.
- Never call eval, exec, compile, open, getattr, setattr, delattr, globals or locals: code that
  does is refused unread, with no second try. Use plain attribute access (`mob.width`).
- You get NO Scene. Never reference `self`, never call `self.play`, `self.add`,
  `add_updater`, `always_redraw` or `TracedPath` — those need a live scene and will
  silently do nothing here. All motion must come from the Animation you return.
- `animate` must return a SINGLE Animation. Combine parts with AnimationGroup(...).
  `UpdateFromAlphaFunc(mobj, fn, run_time=run_time)` is the general workhorse:
  `fn(mob, alpha)` is called with alpha going 0 -> 1.
- Things that happen ONE AFTER ANOTHER: `AnimationGroup(a, b, c, lag_ratio=1.0,
  run_time=run_time)`. Each part plays in its turn and takes an equal share of the time, and
  a part that makes something APPEAR (FadeIn, Create, GrowFromCenter) keeps it unseen until
  its turn — so build everything in `build`, including what appears later. Never
  `Succession`: it needs a live scene and fails here.
- **`animate` receives ONLY `(group, run_time)`** — `width` and `height` are arguments to
  `build` and do not exist inside `animate`. Anything it needs must be read back off the
  geometry (`group[1].get_center()`, `circle.width / 2`, `line.get_start()`), which is
  also what keeps the two halves consistent when the group is rescaled.
- Everything must fit INSIDE a box of `width` x `height` scene units centred on the
  ORIGIN, **for the entire animation** — not just at the start. Compute positions from
  `width`/`height`, never with hard-coded screen coordinates. A simulation that wanders
  outside its box is rejected.
- Something must visibly MOVE or CHANGE across the animation. A static picture is
  rejected.
- The picture is ON SCREEN before anything moves: when the animation starts, something
  must already be visible (the ground, the outline of what will be built, the first
  object). Parts that appear later start unseen — never ALL of it.
- `animate` must not add or remove mobjects, and must not depend on module state.
- Use no randomness (no `random`, no `np.random`) — the same input must always draw the
  same thing.
- NO narration, NO titles, NO explanatory text labels: the storyboard already places
  text around you. Short in-diagram tick/axis labels are fine.
- Any text you do draw (a label the description names, a "?") must be readable: at
  least 0.2 units tall, e.g. `Text("ice", font_size=28)`. Never `.scale()` text by a
  tiny factor: a label 0.01 units tall is the same as no label.
- Keep it to the essentials that make the mechanism readable: 2-6 distinct parts.

{context}
"""

_REPAIR = """Your simulation code was rejected. Fix it and return the corrected
`build` and `animate` functions only — same rules as before.

Problem:
{error}

Your code:
{code}
"""


# ── Two gates, because there are two different mistakes ───────────────────────
#
# Measured on the first live run (2026-08-15, "Projectile motion"): only ONE of four
# simulations survived. The three that died were all *trajectory-tracing* descriptions,
# and every one of them reached for `TracedPath` — which the first cut of this file
# listed alongside `open(` as a "forbidden construct", so each was killed on the spot
# with no repair round.
#
# That conflated two unlike things. Reaching for `open(` is a model doing something it
# was told not to do, and retrying invites it to try again — that rule stands. Reaching
# for `TracedPath` is a model *misunderstanding the contract*: it is the obvious way to
# trace a path in Manim, it just needs a live Scene, so here it silently draws nothing.
# That is exactly the kind of mistake a repair round exists to fix, and it is the same
# lesson `_classify_render_failure` already encodes one stage down: **classify before
# repairing** — an infra failure and a code failure need different responses, and so do
# a security violation and a contract violation.

# Tier 1 — security. Never executed, never retried. The list lives in code_safety.py and
# matches TOKENS: as substrings, "os." refused every scene whose code said `ladoos.`.

# Tier 2 — contract. Rejected, but handed back to the model as a repair brief: each of
# these needs a live Scene, so here it runs without error and animates nothing.
_SCENE_BOUND = ("add_updater", "always_redraw", "TracedPath", "self.")

_IMPORT_OK = re.compile(r"^\s*(import\s+(numpy|math|manim)[\w. ]*|"
                        r"from\s+(numpy|math|manim)[\w.]*\s+import\s+[\w, *]+)\s*$")


def _unsafe_code(code):
    """Return the reason this code must not be EXECUTED, or None. Never retried."""
    reason = forbidden_reason(code)
    if reason:
        return reason
    for line in code.splitlines():
        stripped = line.strip()
        if (stripped.startswith("import ") or stripped.startswith("from ")) \
                and not _IMPORT_OK.match(line):
            return f"disallowed import: {stripped[:60]!r}"
    return None


def _contract_problem(code, require_animate=True):
    """Return the reason this code cannot satisfy the contract, or None. Repairable."""
    if "def build(" not in code:
        return "no build(width, height) function was defined"
    if require_animate and "def animate(" not in code:
        return "no animate(group, run_time) function was defined"
    if re.search(r"\bSuccession\s*\(", code):
        # The prompt itself used to recommend it. Stepped by hand it raises ('Succession' object has no
        # attribute 'scene'), and with that patched its later parts stand in full view until their turn.
        return ("`Succession(...)` needs a live Scene and cannot run here. Write the same sequence as "
                "`AnimationGroup(a, b, c, lag_ratio=1.0, run_time=run_time)`: the parts play one after "
                "another, each for an equal share of the time, and a part that makes something appear "
                "(FadeIn, Create, GrowFromCenter) keeps it unseen until its turn.")
    for bad in _SCENE_BOUND:
        if bad in code:
            return (
                f"`{bad}` requires a live Scene, which this code never gets — it runs "
                f"without error and animates NOTHING. Remove it. To trace a path, "
                f"pre-compute the curve in build() (e.g. ax.plot(...) or "
                f"ParametricFunction) and reveal it from animate() with Create(...), or "
                f"redraw the geometry each frame inside UpdateFromAlphaFunc(mob, fn)."
            )
    return None


# ── The harness the model's functions run inside ──────────────────────────────
#
# No renderer, no ffmpeg, no video: a Manim Animation can be stepped by hand, and
# stepping it exercises exactly the code that would run during a render. Verification
# therefore costs about a second, which is what makes it affordable to reject and
# retry rather than ship and hope.

_HARNESS = '''\
import json, math, sys
import numpy as np
from manim import *

{code}

{tidy}

W, H = {w!r}, {h!r}
SAMPLES = 24


def _fingerprint(mob):
    """What the viewer would see change: where every point is, and how strongly each part is drawn.

    Geometry alone called a scene whose parts APPEAR one after another "nothing moved": blocks
    fading in where they stand change no point. Opacity and stroke width count too.
    """
    total = 0.0
    for m in mob.family_members_with_points():
        pts = m.get_points()
        if len(pts):
            total += float(np.abs(pts).sum())
        try:
            fill, stroke = float(m.get_fill_opacity()), float(m.get_stroke_opacity()) * min(float(m.get_stroke_width()), 8.0)
            total += 7.0 * fill + 11.0 * stroke
            # ... and in which colour, weighted by how much of it shows (a part that lights up has changed).
            total += fill * float(np.dot(m.get_fill_color().to_rgb(), [1.3, 1.7, 1.9]))
            total += min(stroke, 1.0) * float(np.dot(m.get_stroke_color().to_rgb(), [2.3, 2.9, 3.1]))
        except Exception:
            pass
    return round(total, 5)


def _bbox(mob):
    pts = [m.get_points() for m in mob.family_members_with_points() if len(m.get_points())]
    if not pts:
        return None
    allp = np.concatenate(pts)
    return [float(allp[:, 0].min()), float(allp[:, 0].max()),
            float(allp[:, 1].min()), float(allp[:, 1].max())]


_TEXT_TYPES = tuple(t for t in (globals().get(n) for n in ("Text", "MarkupText", "Paragraph", "MathTex", "Tex",
                                                             "DecimalNumber", "Integer")) if t is not None)


def _labels(mob, out=None):
    """The scene's pieces of text, outermost first (a MathTex is one label, not its glyphs)."""
    out = [] if out is None else out
    if isinstance(mob, _TEXT_TYPES):
        out.append(mob)
        return out
    for sub in mob.submobjects:
        _labels(sub, out)
    return out


def _visible(mob):
    for m in mob.family_members_with_points():
        try:
            if m.get_fill_opacity() > 0.05 or (m.get_stroke_opacity() > 0.05 and m.get_stroke_width() > 0.05):
                return True
        except Exception:
            return True
    return False


def _opacity(mob):
    best = 0.0
    for m in mob.family_members_with_points():
        try:
            best = max(best, float(m.get_fill_opacity()), float(m.get_stroke_opacity()) if m.get_stroke_width() > 0.05 else 0.0)
        except Exception:
            return 1.0
    return best


def _shown(label):
    """A label counts as on screen when its glyphs are, OR when the label itself still says it is. A module that
    fades a label with set_opacity(alpha) inside one animation while a FadeIn of the same label runs beside it ends
    with the glyphs at 0 and the label at 1; the lesson then fades the whole picture in and the label is drawn in
    full ("2000 N/m2" in the pressure lesson, 2026-10-18), while this check called it hidden. The label's own value
    is trusted only once the animation has FINISHED: mid-animation a Transform leaves it at its old value (a label
    fading out in a hand-over still says 1 at alpha 1, and only finish() sets it)."""
    if _FINISHED[0]:
        try:
            if label.get_fill_opacity() > 0.05:
                return True
        except Exception:
            pass
    return _visible(label)


_FINISHED = [False]


def _name(mob):
    for attr in ("original_text", "text", "tex_string"):
        value = getattr(mob, attr, None)
        if isinstance(value, str) and value.strip():
            return value.strip()[:24]
    number = getattr(mob, "number", None)
    return ("%g" % number) if isinstance(number, (int, float)) else type(mob).__name__


def _label_boxes(group):
    """Every visible label of the scene as {{id: (name, box)}}."""
    found = {{}}
    for m in _labels(group):
        if _shown(m):
            b = _bbox(m)
            if b is not None:
                found[id(m)] = (_name(m), tuple(round(v, 3) for v in b))
    return found


def _still_state(group):
    """Every part's points and opacity, to tell a scene at rest from one in motion."""
    out = []
    for m in group.family_members_with_points():
        try:
            op = float(m.get_fill_opacity()) + float(m.get_stroke_opacity())
        except Exception:
            op = 0.0
        out.append((np.array(m.get_points(), dtype=float).copy(), op))
    return out


def _is_still(a, b, tol=1e-3):
    """Nothing moved or faded by more than ``tol`` between two states (an eased part settling counts as still)."""
    if len(a) != len(b):
        return False
    for (pa, oa), (pb, ob) in zip(a, b):
        if pa.shape != pb.shape or abs(oa - ob) > tol:
            return False
        if len(pa) and float(np.abs(pa - pb).max()) > tol:
            return False
    return True


def _label_overlaps(group, keep=None):
    """Pairs of visible labels lying on top of each other: over 30% of the smaller one, or letters on letters
    (wider than 0.2 units and taller than a third of the shorter label). "0.01 m2" lay a third of its width over
    "20 N" in a filmed pressure lesson at a 19% share, and the 30% rule alone passed it.

    ``keep(id_a, id_b)`` may refuse a pair (used for the moments a staged scene waits between its stages)."""
    found = _label_boxes(group)
    boxes = [(key, n, b) for key, (n, b) in found.items()]
    hits = []
    for i in range(len(boxes)):
        for j in range(i + 1, len(boxes)):
            (ka, na, a), (kb, nb, b) = boxes[i], boxes[j]
            if keep is not None and not keep(ka, kb):
                continue
            w = min(a[1], b[1]) - max(a[0], b[0])
            h = min(a[3], b[3]) - max(a[2], b[2])
            if w <= 0 or h <= 0:
                continue
            smaller = min((a[1] - a[0]) * (a[3] - a[2]), (b[1] - b[0]) * (b[3] - b[2]))
            shorter = min(a[3] - a[2], b[3] - b[2])
            if (smaller > 0 and w * h > 0.3 * smaller) or (w > 0.2 and h > shorter / 3):
                hits.append([na, nb])
    return hits[:4]


TALLEST = {{}}


def _note_sizes(group):
    """The height of every label while it is drawn at full strength (the tallest it ever is, per label)."""
    for m in _labels(group):
        if _opacity(m) >= 0.6:
            key = id(m)
            TALLEST[key] = (_name(m), max(float(m.height), TALLEST.get(key, ("", 0.0))[1]))


def _text_on_lines(group):
    """Visible labels that a visible line or outline runs THROUGH (its stroke enters the label's box, shrunk by a
    margin so a line that only grazes an edge passes). "2000 N/m2" sat half behind a dent's arc in a filmed pressure
    lesson; the label check compares text with text only. Returns [label, shape] pairs."""
    texts = [m for m in _labels(group) if _shown(m)]
    if not texts:
        return []
    inside_text = set()
    for t in texts:
        inside_text.update(id(m) for m in t.get_family())
    strokes = []
    for m in group.family_members_with_points():
        if id(m) in inside_text:
            continue
        try:
            if m.get_stroke_opacity() <= 0.3 or m.get_stroke_width() <= 0.5:
                continue
        except Exception:
            continue
        pts = np.asarray(m.get_points(), dtype=float)
        if len(pts) < 4:
            continue
        n = (len(pts) // 4) * 4
        curves = pts[:n].reshape(-1, 4, 3)
        ts = np.linspace(0.0, 1.0, 9)[:, None, None]
        a, b, c, d = curves[:, 0], curves[:, 1], curves[:, 2], curves[:, 3]
        samples = ((1 - ts) ** 3 * a + 3 * (1 - ts) ** 2 * ts * b + 3 * (1 - ts) * ts ** 2 * c + ts ** 3 * d).reshape(-1, 3)
        strokes.append((type(m).__name__, samples))
    hits = []
    for t in texts:
        box = _bbox(t)
        if box is None:
            continue
        # The margin passes a line that only grazes a corner of the box. It was 12% / 20% and passed a dent's arc
        # whose ends sat on the tops of "0.01 m2" in a filmed lesson (2026-10-19): at 5% / 8%, 3 more of 32 kept
        # scenes are refused and all 3 touch on a still.
        mx = max(0.02, 0.05 * (box[1] - box[0]))
        my = max(0.012, 0.08 * (box[3] - box[2]))
        x0, x1, y0, y1 = box[0] + mx, box[1] - mx, box[2] + my, box[3] - my
        if x0 >= x1 or y0 >= y1:
            continue
        for kind, samples in strokes:
            inside = (samples[:, 0] > x0) & (samples[:, 0] < x1) & (samples[:, 1] > y0) & (samples[:, 1] < y1)
            if inside.any():
                hits.append([_name(t), kind])
                break
    return hits[:4]


def _arrows_through(group):
    """Visible arrows whose shaft runs THROUGH a filled shape, past a fifth of the shaft. A force drawn on a block
    ends at its top face; a redrawn pressure scene had both force arrows run down through the blocks into the sand
    (2026-10-19), and no check looked at anything but text. Returns [arrow, shape] pairs."""
    arrow_types = tuple(t for t in (globals().get(n) for n in ("Arrow", "Vector", "DoubleArrow")) if t is not None)
    closed = tuple(t for t in (globals().get(n) for n in ("Rectangle", "Polygon", "RoundedRectangle", "Circle", "Ellipse", "Square"))
                   if t is not None)
    arrows = [m for m in group.get_family() if isinstance(m, arrow_types) and _visible(m)]
    hits = []
    for a in arrows:
        inside_arrow = set(id(x) for x in a.get_family())
        try:
            p0, p1 = np.array(a.get_start(), dtype=float), np.array(a.get_end(), dtype=float)
        except Exception:
            continue
        if np.linalg.norm(p1 - p0) < 0.1:
            continue
        samples = [p0 + (p1 - p0) * t for t in np.linspace(0.0, 1.0, 21)]
        for m in group.get_family():
            if id(m) in inside_arrow or not isinstance(m, closed) or isinstance(m, _TEXT_TYPES):
                continue
            try:
                if m.get_fill_opacity() <= 0.3 or not len(m.points):
                    continue
            except Exception:
                continue
            box = _bbox(m)
            if box is None:
                continue
            mx, my = 0.1 * (box[1] - box[0]), 0.1 * (box[3] - box[2])
            # A MEDIUM the whole arrow sits in (the water round a floating bottle, the air round a falling ball) is
            # not an object the force pokes through: both ends inside a shape far bigger than the arrow. Without
            # this, every force drawn on a thing under water was refused (2026-11-03, the bottle's upthrust).
            length = float(np.linalg.norm(p1 - p0))
            def _in(q):
                return box[0] <= q[0] <= box[1] and box[2] <= q[1] <= box[3]
            if _in(p0) and _in(p1) and (box[1] - box[0]) * (box[3] - box[2]) > 6 * length * length:
                continue
            n = sum(1 for q in samples if box[0] + mx < q[0] < box[1] - mx and box[2] + my < q[1] < box[3] - my)
            if n > len(samples) / 5:
                hits.append([type(a).__name__, type(m).__name__])
                break
    return hits[:3]


def _open_arcs(group):
    # The same rule as longform.figures.arcs_stay_open, which the lesson applies: an open arc is never filled.
    return [m for m in group.get_family() if isinstance(m, Arc) and not isinstance(m, (Circle, Sector, AnnularSector, Annulus, Dot))
            and abs(getattr(m, "angle", 0.0)) < TAU - 1e-3]


def _filled_curves(group):
    """Open arcs that end up FILLED: `set_opacity(a)` sets the fill too, so a dent drawn as an arc became a solid
    bowl in a filmed pressure lesson. A closed shape (circle, sector, polygon) may be filled; a straight line's fill
    has no area and shows nothing, so lines and arrows are not asked about."""
    hits = []
    for m in group.get_family():
        if not isinstance(m, Arc) or isinstance(m, (Circle, Sector, AnnularSector, Annulus, Dot)):
            continue
        if isinstance(m, Arc) and abs(getattr(m, "angle", 0.0)) >= TAU - 1e-3:
            continue
        try:
            if m.get_fill_opacity() > 0.05 and len(m.points):
                hits.append(type(m).__name__)
        except Exception:
            pass
    return hits[:3]


def _tiny_labels(group):
    """Labels too small to read. A redrawn pressure scene sized its text as font_size=int(min(width, height) * 0.04),
    which is 0 in a 6x4 box: every label had no height, so none could overlap anything and the scene passed every
    check while the film showed a picture with no numbers (2026-10-19)."""
    out = []
    for m in _labels(group):
        name = _name(m)
        if not any(ch.isalnum() for ch in name):
            continue
        try:
            if float(m.height) < 0.1:
                out.append(name)
        except Exception:
            pass
    return out[:3]


def _parts(group):
    """The pieces build() returned, looking inside plain groups."""
    out = []
    for m in group.submobjects:
        if type(m) in (VGroup, Group):
            out += _parts(m)
        else:
            out.append(m)
    return out


def _mark_seen(parts, seen):
    for i, m in enumerate(parts):
        if i not in seen and (_shown(m) if isinstance(m, _TEXT_TYPES) else _visible(m)):
            seen.add(i)


def _never_seen(parts, seen):
    """Pieces that are never visible, from build() through the end of the animation. The same pressure scene hid its
    second block with set_opacity(0) and then played FadeIn on it: FadeIn returns a mobject to its OWN opacity, which
    was 0, so the block never appeared while the voice talked about it."""
    out = []
    for i, m in enumerate(parts):
        if i in seen or not m.family_members_with_points():
            continue
        try:
            if max(float(m.width), float(m.height)) < 0.05:
                continue
        except Exception:
            continue
        out.append(_name(m))
    return out[:3]


result = {{"ok": False}}
try:
    group = build(W, H)
    if not isinstance(group, Mobject):
        raise TypeError("build() must return a Mobject, got %s" % type(group).__name__)
    for _arc in _open_arcs(group):
        _arc.set_fill(opacity=0)
    # Code moves a label off a line that grazes it, exactly as the lesson's loader does (scene_tidy).
    result["tidied"] = clear_grazed_labels(group, globals().get("animate"), box=(W, H))
    result["parts"] = len(group.family_members_with_points())
    result["tiny_labels"] = _tiny_labels(group)
    _pieces, _seen = _parts(group), set()
    _mark_seen(_pieces, _seen)
    boxes, prints = [], [_fingerprint(group)]
    b0 = _bbox(group)
    if b0 is None:
        raise ValueError("build() returned a Mobject with no drawable points")
    boxes.append(b0)
    overlaps = [pair + ["before it moves"] for pair in _label_overlaps(group)]
    _note_sizes(group)

    # A STATIC drawing defines no animate(); it is verified on build() alone. Same
    # harness either way, so a drawing and a simulation cannot drift apart on what
    # "stays inside its box" or "actually drew something" means.
    anim_fn = globals().get("animate")
    if anim_fn is not None:
        anim = anim_fn(group, 3.0)
        if not isinstance(anim, Animation):
            raise TypeError("animate() must return an Animation, got %s" % type(anim).__name__)
        # As a lesson steps it: evenly through its run (the lesson times the stages itself and takes the
        # animation's own easing off, see longform.runtime._start_motion).
        try:
            anim.rate_func = linear
        except Exception:
            pass
        _arcs = _open_arcs(group)
        if _arcs:
            _step = anim.interpolate

            def _interpolate(alpha, _step=_step, _arcs=_arcs):
                _step(alpha)
                for _arc in _arcs:
                    _arc.set_fill(opacity=0)
            anim.interpolate = _interpolate
        anim.begin()
        # Evenly spaced moments AND the exact boundaries between stages (halves, thirds, quarters, fifths).
        # A lesson holds a staged scene at those boundaries while the voice moves on, and that is where a
        # stage's shapes are at their zero point: one scene passed 24 even samples and then raised on
        # every frame it was held at one third (an arrow of no length), which cost a lesson its last chapter.
        bounds = sorted(set(k / n for n in (2, 3, 4, 5) for k in range(1, n)))      # exact: a lesson rests there
        near = [b + d for b in bounds for d in (-0.02, 0.02)]
        alphas = sorted(set([i / (SAMPLES - 1.0) for i in range(SAMPLES)] + bounds + near))
        seen = {{}}
        for i, alpha in enumerate(alphas):
            anim.interpolate(alpha)
            if alpha in bounds or alpha in near:
                seen[alpha] = _label_boxes(group)
                if alpha in bounds:
                    # Only labels at full strength: one fading out as another fades in is a hand-over caught mid-way.
                    solid = {{id(m) for m in _labels(group) if _opacity(m) >= 0.6}}
                    # The lesson WAITS here while the voice goes on (runtime.stage_progress): two labels that lie on
                    # each other at a boundary, both standing still, are read that way for seconds. The Monty Hall
                    # lesson (2026-10-19) had "switching wins two in three" under "staying wins one in three" through
                    # a whole stage, and the scene had passed because only its first and last frames were looked at.
                    def still(key, a=alpha):
                        here = seen[a].get(key)
                        return here is not None and key in solid and any(
                            (seen.get(a + d) or {{}}).get(key) == here for d in (-0.02, 0.02))
                    overlaps += [pair + ["when it rests between its stages"]
                                 for pair in _label_overlaps(group, keep=lambda x, y: still(x) and still(y))]
            for member in group.get_family():
                pts = member.points
                if getattr(pts, "ndim", 2) != 2 or (len(pts) and pts.shape[1] != 3):
                    raise ValueError("at %.3f of the animation a %s has a malformed point array %s: every shape's "
                                     "points must stay an (n, 3) array (use set_points_as_corners([...]) with full "
                                     "[x, y, z] points, never a single flat vector)" % (alpha, type(member).__name__, pts.shape))
            _note_sizes(group)
            if i == 0:
                result["seen_at_start"] = _visible(group)
            _mark_seen(_pieces, _seen)
            b = _bbox(group)
            if b is not None:
                boxes.append(b)
            prints.append(_fingerprint(group))
        # Where things come to REST is what the viewer reads. (Labels may cross while moving.)
        overlaps += [pair + ["when it has finished moving"] for pair in _label_overlaps(group)]
        # ... and a lesson also holds a staged scene still just before each stage boundary while the voice moves on
        # (longform.runtime.stage_progress). A label lying on another THERE was seen for seconds: the pressure
        # lesson of 2026-10-16 held "0.01 m2" on "20 N" through a whole step. Checked only where the scene is
        # still (nothing changes over the last stretch before the boundary), so labels crossing in motion pass.
        seen_rest = set()
        for n in (2, 3, 4, 5):
            for k in range(1, n):
                b = k / n
                if round(b, 6) in seen_rest:
                    continue
                anim.interpolate(b - 0.003)
                early = _still_state(group)
                anim.interpolate(b - 0.0008)
                late = _still_state(group)
                if _is_still(early, late):
                    seen_rest.add(round(b, 6))
                    for pair in _label_overlaps(group):
                        if pair + ["when it rests between its stages"] not in overlaps:
                            overlaps.append(pair + ["when it rests between its stages"])
        anim.interpolate(1.0)
        anim.finish()
        for _arc in _open_arcs(group):          # a group's finish() steps its parts, not the wrapped interpolate
            _arc.set_fill(opacity=0)
        _FINISHED[0] = True
        _mark_seen(_pieces, _seen)
        result["never_seen"] = _never_seen(_pieces, _seen)
        result["end_labels"] = [[_name(m), float(m.get_center()[0]), float(m.get_center()[1])]
                                for m in _labels(group) if _shown(m)][:40]
        for pair in _label_overlaps(group):
            if pair + ["when it has finished moving"] not in overlaps:
                overlaps.append(pair + ["when it has finished moving"])

    result["ok"] = True
    result["filled_curves"] = _filled_curves(group)
    result["text_on_lines"] = _text_on_lines(group)
    result["arrows_through"] = _arrows_through(group)
    result["label_overlaps"] = overlaps[:4]
    result["label_heights"] = sorted(TALLEST.values(), key=lambda item: item[1])[:6]
    result["bbox"] = [min(b[0] for b in boxes), max(b[1] for b in boxes),
                      min(b[2] for b in boxes), max(b[3] for b in boxes)]
    result["moved"] = len(set(prints)) > 1
except Exception as e:
    import traceback
    result["error"] = traceback.format_exc()[-1500:]

print("SIM_RESULT:" + json.dumps(result))
'''


def _tidy_source():
    """``scene_tidy``'s source, pasted into the sandbox so the checker moves grazed labels as the lesson does."""
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scene_tidy.py")
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _run_harness(code, work_dir=None, box=None):
    """Step the model's animation in an isolated subprocess. Returns (result, error)."""
    work = work_dir or tempfile.mkdtemp(prefix="simgen_")
    script = os.path.join(work, "sim_check.py")
    bw, bh = box or (BOX_W, BOX_H)
    try:
        with open(script, "w", encoding="utf-8") as f:
            f.write(_HARNESS.format(code=code, tidy=_tidy_source(), w=bw, h=bh))
        env = {
            "PATH": os.environ.get("PATH", ""),
            "HOME": work,
            "MPLBACKEND": "Agg",
            "MPLCONFIGDIR": work,
        }
        # Not -I here: manim lives in the active virtualenv, and isolated mode would
        # drop the site-packages that make the check possible at all. The gate above
        # plus a scrubbed env and a scratch cwd carry the boundary.
        proc = subprocess.run([sys.executable, script], cwd=work, env=env,
                              capture_output=True, text=True, timeout=TIMEOUT)
        for line in (proc.stdout or "").splitlines():
            if line.startswith("SIM_RESULT:"):
                return json.loads(line[len("SIM_RESULT:"):]), ""
        return None, (proc.stderr or proc.stdout or "no result from the harness")[-1200:]
    except subprocess.TimeoutExpired:
        return None, f"simulation exceeded the {TIMEOUT}s time limit"
    except Exception as e:
        return None, str(e)
    finally:
        if work_dir is None:
            shutil.rmtree(work, ignore_errors=True)


_NUM = r"\d+(?:\.\d+)?"
_OBJECT_RE = re.compile(r"\b(" + _NUM + r")\s*(?:n|newtons?|kg|g|cm|m|mm|l|ml|v|a|ohms?|j|w)\b\s+(?:[a-z-]+\s+){0,2}?"
                        r"(?:block|brick|box|ball|weight|object|load|stone|cube|bar|car|book|mass|body|cylinder|tin|bag)s?\b", re.I)
_LISTED_RE = re.compile(r"\b(?:labels?|values?|numbers?|readings?|pressures?|areas?)\s+((?:" + _NUM + r"\s*(?:,|and)\s*)+" + _NUM + r")"
                        r"[^.;]*?\b(?:(?:sit|go|are|appear|show|placed|written)\s+)?(?:under|beneath|below|above|over|beside|next to|on)\s+(?:them|each)\b"
                        r"|\b((?:" + _NUM + r"\s*(?:,|and)\s*)+" + _NUM + r")[^.;]*?\brespectively\b", re.I)


def value_pairs(description):
    """What a description pairs: [(object's number, its value)] when it lists values for objects it named before
    ("a 20 N block … a 40 N block …, then the labels 400 and 200 N/m2 sit under them"). The first value goes with
    the first object named. That scene came back with 400 under the 40 N block and 200 under the 20 N one: the
    physics backwards, and every other check passed it (2026-10-18)."""
    text = description or ""
    for m in _LISTED_RE.finditer(text):
        values = re.findall(_NUM, m.group(1) or m.group(2))
        objects = []
        for o in _OBJECT_RE.finditer(text[:m.start()]):
            if o.group(1) not in objects and o.group(1) not in values:
                objects.append(o.group(1))
        if len(values) >= 2 and len(objects) == len(values):
            return list(zip(objects, values))
    return []


def _label_with(labels, number):
    """The one label whose own numbers include `number` (None when none or several)."""
    hits = [lab for lab in labels if number in re.findall(_NUM, str(lab[0]).replace(",", ""))]
    return hits[0] if len(hits) == 1 else None


def _swapped_pairs(labels, pairs):
    """A pair whose value stands under the wrong object: the objects' left-to-right order and their values' must agree."""
    found = []
    for obj, val in pairs:
        a, b = _label_with(labels, obj), _label_with(labels, val)
        if b is not None and a is None and not any(obj in re.findall(_NUM, str(lab[0])) for lab in labels):
            return obj, None            # its value is shown, and nothing says which object is the obj one
        if a is None or b is None:
            return None
        found.append((obj, val, a[1], b[1]))
    objs = sorted(found, key=lambda f: f[2])
    vals = sorted(found, key=lambda f: f[3])
    if any(abs(x[2] - y[2]) < 0.2 for x, y in zip(objs, objs[1:])) or any(abs(x[3] - y[3]) < 0.2 for x, y in zip(vals, vals[1:])):
        return None                     # side by side is the only layout read; stacked objects are not judged
    for o, v in zip(objs, vals):
        if o is not v:
            return o[0], o[1]
    return None


def verify(code, motion=True, min_parts=1, box=None, description=None):
    """Why this code is not usable, or None if it is. Never raises.

    `motion=False` verifies a STATIC drawing (build() only). `min_parts` is the
    complexity floor — for a drawing it is what stops the model from "drawing" a
    grandfather clock as one circle, which is the failure the drawing path exists to
    replace in the first place.
    """
    what = "simulation" if motion else "drawing"
    bw, bh = box or (BOX_W, BOX_H)
    reason = _unsafe_code(code) or _contract_problem(code, require_animate=motion)
    if reason:
        return reason
    result, err = _run_harness(code, box=(bw, bh))
    if result is None:
        return f"the {what} could not be run: {err}"
    if not result.get("ok"):
        return result.get("error") or f"the {what} raised"
    pairs = value_pairs(description) if motion else []
    swapped = _swapped_pairs(result.get("end_labels") or [], pairs) if pairs else None
    if swapped and swapped[1] is None:
        return (f"the object the description calls {swapped[0]} carries no label, so nobody can tell which value is "
                f"its own — write its {swapped[0]} beside it, as the description names it")
    if swapped:
        listing = ", ".join(f"{v!r} with the {o} object" for o, v in pairs)
        return (f"a value stands under the wrong object: the description pairs {listing} in that order (the first "
                f"value goes with the first object named), but {swapped[1]!r} is not beside the {swapped[0]} object "
                "when the animation has finished — put each value beside its own object")
    if result.get("tiny_labels"):
        return (f"the label {result['tiny_labels'][0]!r} is too small to read (under 0.1 units tall), so nobody can read it — give every "
                "piece of text a plain font_size between 20 and 36; never work it out from width or height "
                "(int(min(width, height) * 0.04) is 0)")
    if motion and result.get("never_seen"):
        return (f"a {result['never_seen'][0]} never becomes visible — every part build() returns must be seen at some "
                "point. Check that animate() picks parts by the same order build() returns them in, and remember that "
                "FadeIn returns a mobject to its OWN opacity, so one hidden with set_opacity(0) stays hidden: build it "
                "at full opacity and FadeIn it, or show it with .animate.set_opacity(1)")
    if result.get("label_overlaps"):
        # Two lessons failed their layout check on text inside a scene ('74' on '80', '2' on '12'):
        # the scene had been verified to draw, move and stay in its box, and nothing else.
        first, second, when = result["label_overlaps"][0]
        return (f"two labels lie on top of each other {when} ({first!r} and {second!r}) — give every piece of text "
                f"its own place, clear of the others, at the start, at the end and at every pause between stages; a label a later stage replaces is faded out by that stage")
    if motion and result.get("text_on_lines"):     # scenes only for now: drawings were not measured with it
        label, shape = result["text_on_lines"][0]
        return (f"a {shape} runs through the label {label!r} when the animation has finished — put every label in "
                "clear space beside what it names, never on a line, an arrow, an outline or another shape")
    if motion and result.get("arrows_through"):
        arrow, shape = result["arrows_through"][0]
        return (f"an {arrow} runs through a filled {shape} when the animation has finished — an arrow that shows a force "
                "on an object ends at the object's edge (a push down on a block ends at its top face), it never passes "
                "through it")
    if result.get("filled_curves"):
        return (f"an open {result['filled_curves'][0]} (a curve, not a closed shape) ends up filled, so it is drawn as a solid shape — "
                "set_opacity(a) sets the fill as well as the outline: show or hide an outline with "
                "set_stroke(opacity=a) and leave its fill at 0")
    tiny = [(name, h) for name, h in result.get("label_heights") or [] if h < MIN_TEXT_SHARE * bh]
    if tiny:
        # Measured over the scene cache on 2026-10-19: 13 labels in 6 scenes were under 0.1 units tall in a 4-unit
        # box (a "?" of 0.005, "water" and "ice" of 0.012): the model scales text by a factor meant for font size,
        # the scene passes every other check, and a vision look rightly says the label is not there at all.
        name, h = tiny[0]
        return (f"the text {name!r} is only {h:.3f} units tall in a {bw}x{bh} box: nobody can read it"
                + (f" (and {len(tiny) - 1} more)" if len(tiny) > 1 else "")
                + f". Make every piece of text at least {MIN_TEXT_SHARE * bh * 2:.2f} units tall (Text(..., font_size=28) "
                  "or MathTex(...).scale_to_fit_height(...)); never scale text by a tiny factor")
    parts = int(result.get("parts") or 0)
    if parts < 1:
        return "build() drew nothing (no mobjects with points)"
    if parts < min_parts:
        return (f"build() produced only {parts} drawable part(s) — that is not a drawing "
                f"of the subject, it is a placeholder. Build it from at least "
                f"{min_parts} distinguishable parts that make the object recognisable.")
    if motion and not result.get("moved"):
        return ("nothing moved across the animation — animate() must actually change "
                "the geometry over alpha 0 -> 1")
    if motion and result.get("seen_at_start") is False:
        # A lesson scene waits at its start until the words about it are spoken. A staircase whose every
        # block "appears" opened a lesson on six seconds of empty frame.
        return ("nothing is visible when the animation starts — the viewer looks at an empty picture until the "
                "first thing appears. Keep the setting drawn from the start (the ground, the outline of what "
                "will be built, the first object) and animate only what changes or appears after it.")
    x0, x1, y0, y1 = result.get("bbox") or [0, 0, 0, 0]
    if (x1 - x0) < 0.2 and (y1 - y0) < 0.2:
        return f"the {what} is degenerate (smaller than 0.2 scene units)"
    if CENTRED and (max(abs(x0), abs(x1)) > bw / 2 * BOX_SLACK
                    or max(abs(y0), abs(y1)) > bh / 2 * BOX_SLACK) or (
            not CENTRED and ((x1 - x0) > bw * BOX_SLACK or (y1 - y0) > bh * BOX_SLACK)):
        return (f"the {what} leaves its {bw}x{bh} box"
                f"{' during the animation' if motion else ''} "
                f"(reached x=[{x0:.2f},{x1:.2f}] y=[{y0:.2f},{y1:.2f}]) — compute every "
                f"position from width/height and keep it inside"
                f"{' for the WHOLE animation' if motion else ''}")
    return None


# ── Public API ────────────────────────────────────────────────────────────────

# Why the last attempt at a description produced nothing — for callers that must tell a
# person (the lesson harness), since the return value is only a path or None.
_WHY: dict[str, str] = {}


def why_failed(description):
    """The reason the most recent attempt at this description gave no simulation, or ''."""
    return _WHY.get((description or "").strip(), "")


def generate_simulation(description, keys=None, client=None):
    """Write, verify and cache a simulation for `description`. Returns a path or None."""
    if not enabled():
        return None
    desc = (description or "").strip()
    if len(desc) < 4:
        return None
    _WHY.pop(desc, None)

    out = cached_path(desc)
    if os.path.exists(out):
        logger.info("[SIM] cache HIT for %r", desc[:60])
        _verify_again(out, desc, keys, client)
        return out

    os.makedirs(CACHE_DIR, exist_ok=True)
    if client is None:
        client = get_genai_client(keys)

    context = manim_context.context_for(desc)
    prompt = _PROMPT.format(description=desc, context=context)
    code, error = None, ""

    for attempt in range(1 + max(0, REPAIR_ROUNDS)):
        try:
            resp = call_llm_with_fallback(
                client,
                prompt=(prompt if attempt == 0 else
                        _REPAIR.format(error=error, code=code or "")),
                system_instruction=_SYSTEM,
                temperature=0.2,
                task="code",
                keys=keys,
            )
            candidate = strip_code_fences(resp.text or "")
        except Exception as e:
            logger.warning("[SIM] LLM call failed for %r: %s", desc[:50], e)
            _WHY[desc] = f"the model call failed ({type(e).__name__}: {str(e)[:80]})"
            return None
        if not candidate.strip():
            _WHY[desc] = "the model returned no code"
            return None

        reason = _unsafe_code(candidate)
        if reason:
            _WHY[desc] = f"refused before running: {reason}"
            # A model that reached for `open(` will reach again — never retry unsafe
            # code (asset_gen learned this; the same rule applies verbatim). A CONTRACT
            # mistake is different and is deliberately NOT handled here: it falls
            # through to verify() below, so the model gets told what it did wrong.
            logger.warning("[SIM] rejected unsafe simulation code for %r: %s", desc[:50], reason)
            return None

        code = candidate
        error = verify(code, description=desc)
        if error is None:
            break
        logger.warning("[SIM] attempt %d rejected for %r: %s",
                       attempt + 1, desc[:50], error.splitlines()[-1][:160])

    if error is not None:
        logger.warning("[SIM] giving up on %r after %d attempt(s) — element degrades to "
                       "a static visual.", desc[:60], 1 + max(0, REPAIR_ROUNDS))
        _WHY[desc] = error.splitlines()[-1][:200]
        return None

    try:
        tmp_out = f"{out}.tmp.{os.getpid()}"
        with open(tmp_out, "w", encoding="utf-8") as f:
            f.write("# Generated simulation — verified by app/sim_gen.verify().\n"
                    "# Contract: build(width, height) -> Mobject; "
                    "animate(group, run_time) -> Animation.\n\n")
            f.write(code)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_out, out)

        tmp_side = f"{out}.json.tmp.{os.getpid()}"
        with open(tmp_side, "w", encoding="utf-8") as f:
            json.dump({"description": desc, "box": [BOX_W, BOX_H],
                       "attempts": attempt + 1, "verified_with": VERIFY_REV}, f, indent=1)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_side, out + ".json")
    except Exception as e:
        logger.warning("[SIM] could not cache simulation for %r: %s", desc[:50], e)
        return None
    logger.info("[SIM] generated and verified %r -> %s", desc[:60], os.path.basename(out))
    return out


#: Raised when ``verify`` learns to refuse something it used to pass: a cached scene verified before is checked
#: once more on its next use and, when it now fails, drawn again (2026-10-19: text too small to read).
VERIFY_REV = "2026-10-19-text"


def _verify_again(path, description, keys=None, client=None):
    """A cached simulation verified by an older ``verify``: check it now; when it fails, have it drawn again.

    The first file is kept beside it (``.first.py``) and stays in use when no new version passes: a scene that
    works with a fault is better than none. Never raises.
    """
    side = path + ".json"
    try:
        meta = json.load(open(side, encoding="utf-8")) if os.path.exists(side) else {}
        if meta.get("published") or meta.get("verified_with") == VERIFY_REV:
            return
        code = open(path, encoding="utf-8").read()
        error = verify(code)
        if error is not None:
            logger.warning("[SIM] cached %r now fails verification (%s); drawing it again", description[:50], error[:120])
            new = revise_simulation(description, code, error, keys=keys, client=client)
            if new is None:
                meta["verify_failed"] = error[:300]
            else:
                first = path[:-3] + ".first.py"
                if not os.path.exists(first):
                    tmp_first = f"{first}.tmp.{os.getpid()}"
                    with open(tmp_first, "w", encoding="utf-8") as f:
                        f.write(code)
                    os.replace(tmp_first, first)
                tmp_path = f"{path}.tmp.{os.getpid()}"
                with open(tmp_path, "w", encoding="utf-8") as f:
                    f.write("# Generated simulation — verified by app/sim_gen.verify() (drawn again: " + error[:80].replace("\n", " ") + ").\n\n" + new)
                os.replace(tmp_path, path)
                meta.pop("verify_failed", None)
                meta["redrawn_for"] = error[:300]
        meta["verified_with"] = VERIFY_REV
        tmp_side = f"{side}.tmp.{os.getpid()}"
        with open(tmp_side, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=1)
        os.replace(tmp_side, side)
    except Exception as e:  # noqa: BLE001 - a cached scene stays usable whatever happens here
        logger.warning("[SIM] could not verify the cached %r again: %s", description[:50], e)


def revise_simulation(description, code, brief, keys=None, client=None):
    """A verified new version of a cached simulation that runs but does not show what ``brief`` says it lacks.

    For ``harness.scene_look``: the scene was looked at and things it was asked for are missing. One call with the
    look's findings, then one repair round on a verify failure, exactly as a first attempt gets. Returns the code
    (not written anywhere: the caller decides whether it is better) or None. Never raises.
    """
    if client is None:
        client = get_genai_client(keys)
    problem, current = brief, code
    for _ in range(1 + max(0, REPAIR_ROUNDS)):
        try:
            resp = call_llm_with_fallback(client, prompt=_REPAIR.format(error=problem, code=current),
                                          system_instruction=_SYSTEM, temperature=0.2, task="code", keys=keys)
            candidate = strip_code_fences(resp.text or "")
        except Exception as e:  # noqa: BLE001
            logger.warning("[SIM] redraw call failed for %r: %s", (description or "")[:50], e)
            return None
        if not candidate.strip() or _unsafe_code(candidate):
            return None
        if candidate.strip() == (code or "").strip():
            return None                      # the same scene back is no redraw
        error = verify(candidate)
        if error is None:
            return candidate
        problem, current = brief + "\n\nYour new version was also rejected:\n" + error, candidate
    return None


# ── Drawn objects: Manim draws the subject instead of importing clipart ───────
#
# User report, 2026-08-15, after watching the first live video: *"remove the svg import
# and let the content be generated by manim itself — the current one is very bad."*
# The frames backed it up. That board declared 14 `svg_icon` elements and **every one
# of them was the same keyword, "basketball"** — so the entire visual vocabulary of a
# 105-second physics explainer was one piece of flat clipart, repeated, floating on a
# dark canvas. An icon can say *which noun* a thing is; it cannot show structure, and a
# lesson about structure made of icons is a lesson about nothing.
#
# So the same machinery that draws simulations draws objects: an LLM writes `build()`,
# we execute and verify it, and the result is Manim geometry — parts that the storyboard
# can label, that the theme colours, and that the layout engine can place. It is also
# the same 1-call-per-keyword economics: that 14-icon board costs ONE call.
#
# `min_parts` is the load-bearing check. Iconify's failure mode was returning *something*
# for every query, and a one-circle "drawing" is the same failure wearing a different
# hat — it is precisely the bare `Circle()` this path exists to replace.

DRAW_CACHE_DIR = str(_paths.cache("assets", "drawing", create=False))
DRAW_BOX_W = 4.0
DRAW_BOX_H = 4.0
DRAW_MIN_PARTS = int(os.getenv("DRAW_MIN_PARTS", "3"))


def draw_enabled():
    """Manim-drawn objects instead of imported SVG icons. On by default."""
    return os.getenv("DRAW_WITH_MANIM", "1") != "0"


def drawing_cached_path(description):
    return _keyed("draw", DRAW_CACHE_DIR, description)


_DRAW_SYSTEM = (
    "You draw educational diagrams as Manim geometry. You reply with Python source "
    "ONLY — no markdown fences, no prose, no explanation."
)

_DRAW_PROMPT = """Draw, in Manim, a clear educational diagram of: {description}

Reply with exactly ONE module-level function and nothing else:

    def build(width, height):
        \"\"\"Return ONE Mobject (usually a VGroup) drawing the subject.\"\"\"

This replaces a clipart icon, so it must do what clipart cannot: show the STRUCTURE a
student needs to see. Draw the parts, in their real spatial relationship.

Hard rules — the harness around you owns everything else:
- `from manim import *` and `import numpy as np` are ALREADY done. Import nothing.
- Never call eval, exec, compile, open, getattr, setattr, delattr, globals or locals: code that
  does is refused unread, with no second try. Use plain attribute access (`mob.width`).
- There is NO Scene. Never reference `self`, `add_updater`, `always_redraw` or
  `TracedPath`. Return geometry only — no animation.
- Everything must fit INSIDE a box of `width` x `height` scene units centred on the
  ORIGIN. Compute every position from `width`/`height`; never hard-code screen
  coordinates. It is scaled to its final size afterwards, so build it to fill the box.
- Use at least {min_parts} distinguishable parts. A single circle or square is a
  REJECTED answer — that is the placeholder this is replacing.
- Build from Manim primitives: Circle, Ellipse, Arc, Line, Arrow, Polygon, Rectangle,
  Square, Sector, AnnularSector, Annulus, ParametricFunction, CubicBezier, VGroup.
  `ParametricFunction(lambda t: np.array([...]), t_range=[a, b, step])` draws any curve
  you can write down — use it for anything organic.
- Colour parts to distinguish them (`color=`, `fill_opacity=`), and give the subject's
  own colours where they carry meaning. Assume a DARK background: never use black, and
  never rely on white alone to separate two parts.
- NO text and NO labels — the storyboard places its own labels around you, and a text
  glyph inside the drawing collides with them.
- Aim for the recognisable essentials, not an illustration: 4-12 shapes.
- Use no randomness — the same input must always draw the same thing.

{context}
"""

_DRAW_REPAIR = """Your drawing was rejected. Fix it and return the corrected `build`
function only — same rules as before.

Problem:
{error}

Your code:
{code}
"""


# A description made only of these names a PRIMITIVE, not a thing. Sending "circle" to
# the drawing model is worse than drawing a circle: with a complexity floor to satisfy it
# would invent parts the storyboard never asked for. So a bare primitive keeps its
# primitive, and `SHAPE_CONTENT_RULE` + the `[ELEMENTS]` counter push the storyboard to
# stop emitting them at the source, which is where the actual defect is.
_PRIMITIVE_WORDS = frozenset({
    "circle", "circles", "dot", "dots", "point", "points", "square", "squares",
    "rectangle", "rectangles", "box", "line", "lines", "arrow", "arrows", "triangle",
    "polygon", "ellipse", "oval", "ring", "curve", "arc", "shape", "marker",
    "small", "large", "big", "tiny", "short", "long", "thin", "thick", "horizontal",
    "vertical", "dashed", "dotted", "solid", "filled", "hollow", "left", "right", "up",
    "down", "upward", "downward", "pointing", "a", "an", "the", "and", "of", "with",
})


def is_bare_primitive(text):
    """True when a description names a primitive and nothing else."""
    words = re.findall(r"[a-z]+", str(text or "").lower())
    return bool(words) and all(w in _PRIMITIVE_WORDS for w in words)


# Nouns where the primitive IS the subject. Manim's Line, Arrow and Dot are exactly
# right for these, and a generated drawing would be strictly worse: with a complexity
# floor to satisfy, a model asked for "a dashed line showing the horizontal path" adds
# parts a line should not have.
#
# Measured 2026-08-15: after SHAPE_CONTENT_RULE landed, a board went from 14/16
# content-free shapes to 0/19 — but 11 of those 19 were well-described *lines and
# arrows* ("dashed vertical line from basketball_start to horizontal_path", "downward
# gravity arrow"). Routing those to the drawing model would have spent 11 calls making
# them worse. The user's complaint was that OBJECTS became generic circles, not that
# arrows were arrows.
_PRIMITIVE_SUBJECTS = frozenset({
    "line", "lines", "arrow", "arrows", "vector", "vectors", "dot", "dots", "point",
    "points", "segment", "ray", "rays", "tick", "ticks", "marker", "markers",
    "bracket", "brace", "axis", "dash", "dashes",
})


def is_primitive_subject(text):
    """True when the described thing IS a primitive, however well it is described.

    Looks only at the HEAD of the description — everything after a clause word
    describes purpose, not shape ("a dashed line **representing** the initial path" is
    still a line). Same head-noun discipline as the transpiler's `_shape_head`.
    """
    words = re.findall(r"[a-z]+", str(text or "").lower())
    head = []
    for w in words:
        if w in ("representing", "showing", "indicating", "from", "containing",
                 "with", "labelled", "labeled", "marking", "connecting", "for", "that"):
            break
        head.append(w)
    return any(w in _PRIMITIVE_SUBJECTS for w in head[:5])


def generate_drawing(description, keys=None, client=None, min_parts=None):
    """Draw `description` as Manim geometry. Returns a module path, or None.

    Cached per keyword, so a board that says "basketball" fourteen times spends one
    call. Every failure returns None and the caller keeps whatever fallback it had.
    """
    if not (enabled() and draw_enabled()):
        return None
    desc = (description or "").strip()
    if len(desc) < 2:
        return None

    out = drawing_cached_path(desc)
    if os.path.exists(out):
        logger.info("[DRAW] cache HIT for %r", desc[:60])
        return out

    os.makedirs(DRAW_CACHE_DIR, exist_ok=True)
    if client is None:
        client = get_genai_client(keys)

    floor = int(min_parts or DRAW_MIN_PARTS)
    prompt = _DRAW_PROMPT.format(
        description=desc, min_parts=floor,
        context=manim_context.context_for(desc, api_limit=16, pattern_limit=1),
    )
    code, error = None, ""
    for attempt in range(1 + max(0, REPAIR_ROUNDS)):
        try:
            resp = call_llm_with_fallback(
                client,
                prompt=(prompt if attempt == 0 else
                        _DRAW_REPAIR.format(error=error, code=code or "")),
                system_instruction=_DRAW_SYSTEM, temperature=0.25, task="code", keys=keys,
            )
            candidate = strip_code_fences(resp.text or "")
        except Exception as e:
            logger.warning("[DRAW] LLM call failed for %r: %s", desc[:50], e)
            return None
        if not candidate.strip():
            return None
        reason = _unsafe_code(candidate)
        if reason:
            logger.warning("[DRAW] rejected unsafe drawing code for %r: %s", desc[:50], reason)
            return None
        code = candidate
        error = verify(code, motion=False, min_parts=floor,
                       box=(DRAW_BOX_W, DRAW_BOX_H))
        if error is None:
            break
        logger.warning("[DRAW] attempt %d rejected for %r: %s",
                       attempt + 1, desc[:50], error.splitlines()[-1][:160])

    if error is not None:
        logger.warning("[DRAW] giving up on %r — falling back to the icon cascade.", desc[:60])
        return None

    try:
        with open(out, "w", encoding="utf-8") as f:
            f.write("# Generated drawing — verified by app/sim_gen.verify(motion=False).\n"
                    "# Contract: build(width, height) -> Mobject.\n\n")
            f.write(code)
        with open(out + ".json", "w", encoding="utf-8") as f:
            json.dump({"description": desc, "box": [DRAW_BOX_W, DRAW_BOX_H],
                       "attempts": attempt + 1}, f, indent=1)
    except Exception as e:
        logger.warning("[DRAW] could not cache drawing for %r: %s", desc[:50], e)
        return None
    logger.info("[DRAW] drew %r -> %s", desc[:60], os.path.basename(out))
    return out


DRAW_WORKERS = int(os.getenv("DRAW_WORKERS", "4"))
# A shape may legitimately be simpler than an icon ("the ground line the ball lands on"),
# so its complexity floor is lower — but still above one, which is the bare primitive.
DRAW_SHAPE_MIN_PARTS = int(os.getenv("DRAW_SHAPE_MIN_PARTS", "2"))


def _draw_candidates(storyboard):
    """(element, description, min_parts) for everything the model should DRAW.

    Two deliberate exceptions, both of them cases where geometry is not the model's to
    invent:

    * **An edge (`connects`) is never drawn.** Its endpoints are computed from the two
      mobjects it joins (`viz_helpers.connector`), so a drawing of its own would tear it
      off the nodes — the structural-IR rule this repo learned from a factor tree that
      rendered as one circle plus floating stubs.
    * **A bare primitive is never drawn.** "circle" carries no subject; with a
      complexity floor to satisfy, the model would invent parts nobody asked for. The
      real defect is upstream, and `SHAPE_CONTENT_RULE` addresses it there.
    """
    out = []
    for scene in storyboard.get("visual_storyboard") or []:
        known = {e.get("id") for e in (scene.get("elements") or []) if isinstance(e, dict)}
        for el in (scene.get("elements") or []):
            if not isinstance(el, dict):
                continue
            etype, content = el.get("type"), str(el.get("content") or "").strip()
            if not content or _is_sim_module(content):
                continue                       # empty, or already resolved
            if etype == "svg_icon":
                out.append((el, content, DRAW_MIN_PARTS))
            elif etype == "shape":
                conn = el.get("connects")
                if isinstance(conn, (list, tuple)) and len(conn) == 2 and all(
                        isinstance(c, str) and c in known for c in conn):
                    continue                   # an edge — geometry comes from its ends
                if is_bare_primitive(content) or is_primitive_subject(content):
                    continue                   # the primitive IS the subject
                out.append((el, content, DRAW_SHAPE_MIN_PARTS))
    return out


def resolve_drawn_elements(storyboard, asset_warnings=None, keys=None, client=None):
    """Have Manim DRAW the objects, instead of importing clipart or stamping primitives.

    Covers `svg_icon` (was: an Iconify download) and `shape` (was: a fixed prose→
    primitive table, which is how a lesson about structure became scattered rings).
    Runs BEFORE the icon preflight so a drawn element never spends a network probe.

    Anything that fails to draw is left exactly as it was: the icon cascade and the
    transpiler's shape resolver both still stand behind this. Geometry beats an icon,
    an icon beats a primitive, and any of them beats a blank frame.
    """
    warnings = list(asset_warnings or [])
    if not (isinstance(storyboard, dict) and enabled() and draw_enabled()):
        return warnings
    targets = _draw_candidates(storyboard)
    if not targets:
        return warnings

    # One call per DISTINCT description, in parallel. The 2026-08-15 board asked for the
    # same keyword 14 times, and a board of 16 distinct shapes generated serially would
    # add minutes to codegen for no reason.
    jobs = {}
    for _el, desc, floor in targets:
        jobs.setdefault(desc, floor)
        jobs[desc] = min(jobs[desc], floor)

    def _one(item):
        desc, floor = item
        try:
            return desc, generate_drawing(desc, keys=keys, client=client, min_parts=floor)
        except Exception as e:
            logger.warning("[DRAW] generation raised for %r: %s", desc[:50], e)
            return desc, None

    with ThreadPoolExecutor(max_workers=max(1, DRAW_WORKERS)) as pool:
        results = dict(pool.map(_one, list(jobs.items())))

    drawn = missed = 0
    for el, desc, _floor in targets:
        path = results.get(desc)
        if path:
            el["content"] = path
            el["_drawn_from"] = desc[:60]
            drawn += 1
        else:
            missed += 1
    logger.info("[DRAW] board pass: %d element(s) drawn in Manim from %d distinct "
                "description(s), %d left to the old resolvers.",
                drawn, len(jobs), missed)
    return warnings


def _is_sim_module(content):
    text = str(content or "").strip()
    return text.endswith(".py") and os.path.isabs(text) and os.path.exists(text)


def resolve_simulation_elements(storyboard, asset_warnings=None, keys=None, client=None):
    """Resolve every `simulation` element in a board to a local, verified module path.

    Called from `codegen_pipeline` right after the image and generated-asset passes,
    for the same reason those run there: the render subprocess must never need a key,
    a network, or an LLM. An element that cannot be generated degrades to a `shape`
    (which routes through the normal asset cascade) and is recorded in
    `asset_warnings`, exactly like an unresolvable image query.

    Returns the (possibly extended) asset-warning list, matching the shape the codegen
    prompt already formats: scene / element_id / type / keyword / provider.
    """
    warnings = list(asset_warnings or [])
    if not isinstance(storyboard, dict):
        return warnings
    scenes = storyboard.get("visual_storyboard") or []
    resolved = degraded = drawn_still = 0

    for scene in scenes:
        for el in (scene.get("elements") or []):
            if not isinstance(el, dict) or el.get("type") != "simulation":
                continue
            content = str(el.get("content") or "").strip()
            if content.endswith(".py") and os.path.isabs(content) and os.path.exists(content):
                continue                       # already resolved (re-render, cached board)
            path = None
            try:
                path = generate_simulation(content, keys=keys, client=client)
            except Exception as e:
                logger.warning("[SIM] generation raised for %r: %s", content[:50], e)
            if path:
                el["content"] = path
                resolved += 1
            else:
                # Before giving up on motion, try to at least DRAW the system. The old
                # fallback set type="shape", whose prose head-noun ("a ball rolling off
                # a table…") resolves to a bare `Circle()` — six of them in the first
                # live run, and a bare circle is exactly the placeholder this whole
                # module exists to stop shipping. A still, correct drawing of the
                # apparatus is worth far more than a ring.
                still = None
                try:
                    still = generate_drawing(content, keys=keys, client=client)
                except Exception as e:
                    logger.warning("[SIM] still-drawing fallback raised for %r: %s",
                                   content[:50], e)
                if still:
                    el["type"] = "svg_icon"      # emitted via drawing(), no motion
                    el["content"] = still
                    el["_drawn_from"] = content[:60]
                    el["scale"] = max(float(el.get("scale") or 0) or 0, 3.0)
                    drawn_still += 1
                    continue
                el["type"] = "shape"
                degraded += 1
                warnings.append({
                    "scene": scene.get("scene_index"), "element_id": el.get("id"),
                    "type": "simulation", "keyword": content[:80],
                    "status": "fallback", "provider": "static_shape",
                })
    if resolved or degraded or drawn_still:
        logger.info("[SIM] board pass: %d simulation(s) animated, %d drawn as stills, "
                    "%d degraded to a primitive.", resolved, drawn_still, degraded)
    return warnings
