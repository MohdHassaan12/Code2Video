"""Code moves a scene's label off a line that grazes it, so a near miss never costs a redraw.

A model-written scene (``engine.sim_gen``) places its own labels. When a dent's arc or an outline ends on the top
of a label ("0.01 m2" in a filmed pressure lesson, 2026-10-19), the checker refuses the scene and the only cure was
another model call, which fixed that and broke something else three times out of three. Position is layout, and
layout belongs to code: ``clear_grazed_labels`` finds the labels a stroke runs into at the scene's FINISHED state
and moves each by the smallest step that clears it, without landing on another label or leaving the box.

Imported by ``longform.figures.scene`` (the lesson) and pasted verbatim into ``engine.sim_gen``'s sandbox harness
(the checker), so what is verified is what is filmed. It must import nothing but manim and numpy.
"""
import numpy as np
from manim import Animation, AnnularSector, Annulus, Arc, Circle, Dot, Sector

try:
    from manim import DecimalNumber, Integer, MarkupText, MathTex, Paragraph, Tex, Text
    _TIDY_TEXT = (Text, MarkupText, Paragraph, MathTex, Tex, DecimalNumber, Integer)
except Exception:                        # pragma: no cover - every manim this runs on has them
    _TIDY_TEXT = ()

TIDY_STEPS = (0.04, 0.08, 0.12, 0.16, 0.22, 0.3, 0.4)
# A graze is cured by a small step; a line through the middle of a label is the scene's own fault and stays refused.
# A label is moved by at most half its height, so it never wanders off the thing it names.
TIDY_REACH = 0.5
TIDY_GAP = 0.05       # a moved label is clear of every line by this much (scene units; the box is 6 by 4)
_TIDY_DIRS = ((0, -1), (0, 1), (1, 0), (-1, 0), (0.7, -0.7), (-0.7, -0.7), (0.7, 0.7), (-0.7, 0.7))


def _tidy_box(mob):
    pts = [m.get_points() for m in mob.family_members_with_points() if len(m.get_points())]
    if not pts:
        return None
    p = np.concatenate(pts)
    return [float(p[:, 0].min()), float(p[:, 0].max()), float(p[:, 1].min()), float(p[:, 1].max())]


def _tidy_visible(mob):
    for m in mob.family_members_with_points():
        try:
            if m.get_fill_opacity() > 0.05 or (m.get_stroke_opacity() > 0.05 and m.get_stroke_width() > 0.05):
                return True
        except Exception:
            return True
    return False


def _tidy_labels(mob, out):
    if isinstance(mob, _TIDY_TEXT):
        out.append(mob)
        return out
    for sub in mob.submobjects:
        _tidy_labels(sub, out)
    return out


def _tidy_open_arcs(group):
    return [m for m in group.get_family() if isinstance(m, Arc) and not isinstance(m, (Circle, Sector, AnnularSector, Annulus, Dot))
            and abs(getattr(m, "angle", 0.0)) < 2 * np.pi - 1e-3]


def _tidy_strokes(group, skip):
    """Sampled paths of every visible stroke that is not part of a label: (n, 3) arrays."""
    out = []
    for m in group.family_members_with_points():
        if id(m) in skip:
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
        c = pts[:n].reshape(-1, 4, 3)
        t = np.linspace(0.0, 1.0, 9)[:, None, None]
        a, b, cc, d = c[:, 0], c[:, 1], c[:, 2], c[:, 3]
        out.append(((1 - t) ** 3 * a + 3 * (1 - t) ** 2 * t * b + 3 * (1 - t) * t ** 2 * cc + t ** 3 * d).reshape(-1, 3))
    return out


def _tidy_inner(box, mx_share, my_share, mx_least, my_least):
    if mx_least < 0 or my_least < 0:                 # a negative margin GROWS the box by that much
        mx, my = mx_least, my_least
    else:
        mx = max(mx_least, mx_share * (box[1] - box[0]))
        my = max(my_least, my_share * (box[3] - box[2]))
    return box[0] + mx, box[1] - mx, box[2] + my, box[3] - my


def _tidy_hit(box, strokes, margin):
    x0, x1, y0, y1 = _tidy_inner(box, *margin)
    if x0 >= x1 or y0 >= y1:
        return False
    for s in strokes:
        if ((s[:, 0] > x0) & (s[:, 0] < x1) & (s[:, 1] > y0) & (s[:, 1] < y1)).any():
            return True
    return False


def _tidy_overlap(a, b):
    return min(a[1], b[1]) - max(a[0], b[0]) > 0 and min(a[3], b[3]) - max(a[2], b[2]) > 0


def clear_grazed_labels(group, animate=None, box=(6.0, 4.0), margin=(0.05, 0.08, 0.02, 0.012)):
    """Move, in ``group`` as built, every label a stroke runs into once ``animate`` has finished. Returns the moved
    labels' texts. A clear place has no line within ``TIDY_GAP`` of the label's box (so a moved label is clear by a
    visible gap), never on another label, never outside the box. A label no step clears stays where it was, and the
    checker still refuses the scene. Never raises: anything unexpected leaves the scene as it was."""
    try:
        work = group.copy()
        if animate is not None:
            anim = animate(work, 3.0)
            if isinstance(anim, Animation):
                try:
                    from manim import linear
                    anim.rate_func = linear
                except Exception:
                    pass
                anim.begin()
                anim.interpolate(1.0)
                anim.finish()
        for arc in _tidy_open_arcs(work):
            arc.set_fill(opacity=0)
        built, done = list(group.get_family()), list(work.get_family())
        if len(built) != len(done):
            return []
        where = {id(m): i for i, m in enumerate(done)}
        labels = [m for m in _tidy_labels(work, []) if _tidy_visible(m) or m.get_fill_opacity() > 0.05]
        if not labels:
            return []
        in_text = set()
        for t in labels:
            in_text.update(id(m) for m in t.get_family())
        strokes = _tidy_strokes(work, in_text)
        clear = (0.0, 0.0, -TIDY_GAP, -TIDY_GAP)     # the label's box GROWN by a gap: a shrunk box would pass a touch
        boxes = {id(t): _tidy_box(t) for t in labels}
        moved = []
        for t in labels:
            b = boxes[id(t)]
            if b is None or not _tidy_hit(b, strokes, margin):
                continue
            best = None
            reach = max(TIDY_STEPS[0], TIDY_REACH * (b[3] - b[2]))
            for step in TIDY_STEPS:
                if step > reach:
                    break
                for dx, dy in _TIDY_DIRS:
                    nb = [b[0] + dx * step, b[1] + dx * step, b[2] + dy * step, b[3] + dy * step]
                    if nb[0] < -box[0] / 2 or nb[1] > box[0] / 2 or nb[2] < -box[1] / 2 or nb[3] > box[1] / 2:
                        continue
                    if _tidy_hit(nb, strokes, clear):
                        continue
                    if any(_tidy_overlap(nb, boxes[id(o)]) for o in labels if o is not t and boxes[id(o)] is not None):
                        continue
                    best = (dx * step, dy * step)
                    break
                if best:
                    break
            if not best:
                continue
            shift = np.array([best[0], best[1], 0.0])
            built[where[id(t)]].shift(shift)
            t.shift(shift)
            boxes[id(t)] = _tidy_box(t)
            for attr in ("original_text", "text", "tex_string"):
                v = getattr(t, attr, None)
                if isinstance(v, str) and v.strip():
                    moved.append(v.strip()[:24])
                    break
            else:
                moved.append(type(t).__name__)
        return moved
    except Exception:
        return []
