"""The per-play layout probe — one measurement, shared by both production paths.

``PROBE_SNIPPET`` is source text, not a function, on purpose: the engine appends it to
a dry-run copy of a generated scene script (``engine/render.py``), where it must work
with nothing imported but manim. It patches ``Scene.play`` and, after every play,
prints one parseable line per finding:

    LAYOUT_VIOLATION: overlap ...          text on text (>=15% of the smaller box)
    LAYOUT_VIOLATION: off-frame ...        text partially clipped by the frame edge
    LAYOUT_VIOLATION: text-over-shape ...  a diagram's stroke path crosses a text box
    LAYOUT_VIOLATION: shape-overlap ...    shape on shape (reported, not yet counted)

The long-form runtime (``longform/runtime.py``) calls :func:`install` inside the manim
process instead, so hand-written chapter scenes are measured after every play too —
the original long-form audit only checked bounds at beat ends and so missed
collisions that came and went in between.

Known traps are documented in ``docs/engine/layout_framework.md`` and CLAUDE.md
(family-aware visibility for MathTex, containers that carry points AND submobjects,
NumberPlane/ComplexPlane as backdrops).
"""
from __future__ import annotations

import re

PROBE_SNIPPET = '''
# --- injected overlap probe (dry-run only): measure text overlap after every play() ---
try:
    from manim import Scene as _OvlScene
    import manim as _ovl_mn

    _OVL_TYPES = tuple(
        _t for _t in (
            getattr(_ovl_mn, _n, None)
            for _n in ("Text", "MarkupText", "Paragraph", "MathTex", "Tex",
                       "SingleStringMathTex", "DecimalNumber", "Integer", "BulletedList")
        ) if isinstance(_t, type)
    )
    # Grid-like backdrops: text over them is normal, never a violation.
    _OVL_PLANES = tuple(
        _t for _t in (getattr(_ovl_mn, _n, None) for _n in ("NumberPlane", "ComplexPlane"))
        if isinstance(_t, type)
    )
    # Raster images: their .points are just 4 bbox corners and they carry no
    # stroke/fill accessors, so the generic scan would register them as opaque
    # shapes and flag every caption near a photo as text-over-shape. Captions
    # ON an image are usually intentional — skip images entirely.
    _OVL_IMAGES = tuple(
        _t for _t in (getattr(_ovl_mn, _n, None) for _n in ("ImageMobject",))
        if isinstance(_t, type)
    )
    _OVL_SEEN = set()
    _OVL_STATE = {"beat": 0}
    _OVL_MAX_PER_KIND = 12
    _OVL_COUNTS = {"overlap": 0, "off-frame": 0, "text-over-shape": 0, "shape-overlap": 0}
    _OVL_TRUNCATED = set()

    def _ovl_report(kind, msg, tag=None):
        if _OVL_COUNTS.get(kind, 0) >= _OVL_MAX_PER_KIND:
            if kind not in _OVL_TRUNCATED:
                _OVL_TRUNCATED.add(kind)
                print(f"LAYOUT_VIOLATION: {kind} report truncated (limit reached)")
            return False
        _OVL_COUNTS[kind] = _OVL_COUNTS.get(kind, 0) + 1
        suffix = f" after {tag}" if tag else ""
        print(f"LAYOUT_VIOLATION: {kind} {msg}{suffix}")
        return True

    def _ovl_scan(mobs):
        # One walk: maximal text nodes (don't descend into glyphs) and stroked/filled
        # shape leaves, each tagged with its top-level root so intentionally grouped
        # label+shape pairs (same root) can be exempted from cross-checks.
        texts, shapes = [], []
        for _root in mobs:
            _rid = id(_root)
            _stack = [(_root, isinstance(_root, _OVL_PLANES))]
            while _stack:
                _m, _in_plane = _stack.pop()
                if isinstance(_m, _OVL_TYPES):
                    texts.append((_m, _rid))
                    continue
                _subs = getattr(_m, "submobjects", None) or []
                if _subs:
                    _stack.extend(
                        (_s, _in_plane or isinstance(_s, _OVL_PLANES)) for _s in _subs
                    )
                # A node can carry its own geometry AND submobjects (NumberLine =
                # line + tick children, Arrow = line + tip) — check its points too.
                if _in_plane or getattr(_m, "z_index", 0) <= -50:
                    continue
                if _OVL_IMAGES and isinstance(_m, _OVL_IMAGES):
                    continue
                _pts = getattr(_m, "points", None)
                if _pts is None or len(_pts) < 2:
                    continue
                try:
                    _op = max(_m.get_stroke_opacity() or 0, _m.get_fill_opacity() or 0)
                except Exception:
                    _op = 1.0
                if _op >= 0.3:
                    shapes.append((_m, _rid))
        return texts, shapes

    # Edges must touch their endpoints, so a linear mobject can never be a collision.
    _OVL_EDGEISH = ("Line", "DashedLine", "Arrow", "DoubleArrow", "Vector",
                    "CurvedArrow", "Elbow", "TangentLine")

    def _ovl_shape_pair_check(shapes, tag):
        """Shape-on-shape collisions — the class the text-only checks never saw.

        Reported under its OWN name (`shape-overlap`) and deliberately NOT counted
        by _overlap_violations, exactly like the vision-* namespace: it is a new
        measurement, and a metric gets to prove itself before it is allowed to
        trigger repairs.

        Structurally legitimate contacts are exempt, so this stays false-positive
        safe: same-root groups (value_in's shape+label, an Axes' parts), any edge
        touching what it links, and full containment (place_inside children).
        """
        for _i in range(len(shapes)):
            for _j in range(_i + 1, len(shapes)):
                _a, _ra = shapes[_i]
                _b, _rb = shapes[_j]
                if _ra == _rb:
                    continue
                if (type(_a).__name__ in _OVL_EDGEISH) or (type(_b).__name__ in _OVL_EDGEISH):
                    continue
                try:
                    _al, _ar = _a.get_left()[0], _a.get_right()[0]
                    _ab, _at = _a.get_bottom()[1], _a.get_top()[1]
                    _bl, _br = _b.get_left()[0], _b.get_right()[0]
                    _bb, _bt = _b.get_bottom()[1], _b.get_top()[1]
                    _xo = min(_ar, _br) - max(_al, _bl)
                    _yo = min(_at, _bt) - max(_ab, _bb)
                    if _xo <= 0.05 or _yo <= 0.05:
                        continue
                    _aa = max((_ar - _al) * (_at - _ab), 1e-6)
                    _ba = max((_br - _bl) * (_bt - _bb), 1e-6)
                    # Containment (a child placed inside its container) is intended.
                    if (_al >= _bl - 0.02 and _ar <= _br + 0.02
                            and _ab >= _bb - 0.02 and _at <= _bt + 0.02):
                        continue
                    if (_bl >= _al - 0.02 and _br <= _ar + 0.02
                            and _bb >= _ab - 0.02 and _bt <= _at + 0.02):
                        continue
                    if _xo * _yo < 0.15 * min(_aa, _ba):
                        continue
                except Exception:
                    continue
                _key = ("shape-overlap", type(_a).__name__, type(_b).__name__,
                        round(float(_a.get_center()[0]), 1), round(float(_b.get_center()[0]), 1))
                if _key in _OVL_SEEN:
                    continue
                _OVL_SEEN.add(_key)
                _ovl_report("shape-overlap", f"{type(_a).__name__} x {type(_b).__name__} depth {_xo:.2f}x{_yo:.2f}", tag)

    def _ovl_excerpt(m):
        # original_text preserves spaces; Text.text strips them
        for _attr in ("original_text", "text", "tex_string"):
            _v = getattr(m, _attr, None)
            if isinstance(_v, str) and _v.strip():
                return _v.strip().replace("\\n", " ")[:40]
        return type(m).__name__

    def _ovl_visible(m):
        # Top-level get_fill_opacity() is 0.0 for MathTex (only glyph descendants
        # carry fill) — check the family before declaring something invisible.
        try:
            for _sm in list(m.get_family())[:50]:
                try:
                    if (_sm.get_fill_opacity() or 0) >= 0.05 or \\
                            (_sm.get_stroke_opacity() or 0) >= 0.05:
                        return True
                except Exception:
                    continue
            return False
        except Exception:
            return True

    def _ovl_clip_check(texts, tag):
        # Clipped text: partially cut off by the frame edge mid-scene. Fully
        # off-screen text is skipped — it's often parked for a slide-in and is
        # invisible rather than visually broken.
        try:
            from manim import config as _ovl_cfg
            _fw, _fh = _ovl_cfg.frame_width / 2, _ovl_cfg.frame_height / 2
            for _m in texts:
                try:
                    _l, _r = _m.get_left()[0], _m.get_right()[0]
                    _b, _t = _m.get_bottom()[1], _m.get_top()[1]
                    _area = max((_r - _l) * (_t - _b), 1e-6)
                    _vx = max(0.0, min(_r, _fw) - max(_l, -_fw))
                    _vy = max(0.0, min(_t, _fh) - max(_b, -_fh))
                    _vis = (_vx * _vy) / _area
                except Exception:
                    continue
                if 0.05 < _vis < 0.85:
                    _key = ("clip", type(_m).__name__, _ovl_excerpt(_m))
                    if _key in _OVL_SEEN:
                        continue
                    _OVL_SEEN.add(_key)
                    _ovl_report("off-frame", f"{_key[1]}({_key[2]!r}) bbox x[{_l:.2f},{_r:.2f}] y[{_b:.2f},{_t:.2f}] only {_vis:.0%} visible", tag)
        except Exception:
            pass

    def _ovl_shape_check(texts, shapes, tag):
        # Text struck through by a diagram: a shape's stroke path passes through the
        # text's (shrunk) bbox. Text fully inside a box, or beside a curve, never
        # trips this — only an actual crossing does.
        for _t, _tr in texts:
            try:
                if not _ovl_visible(_t):
                    continue
                # A label carrying its own opaque backing plate (add_background_rectangle)
                # is MEANT to sit on linework: the plate hides what runs behind it, so a
                # value printed on a gridded square is legible, not struck through.
                _plate = getattr(_t, "background_rectangle", None)
                if _plate is not None and (_plate.get_fill_opacity() or 0) >= 0.6:
                    continue
                _l, _r = _t.get_left()[0], _t.get_right()[0]
                _b, _tp = _t.get_bottom()[1], _t.get_top()[1]
            except Exception:
                continue
            _w, _h = _r - _l, _tp - _b
            if _w <= 0 or _h <= 0:
                continue
            _l2, _r2 = _l + 0.1 * _w, _r - 0.1 * _w
            _b2, _t2 = _b + 0.1 * _h, _tp - 0.1 * _h
            for _s, _sr in shapes:
                if _sr == _tr:
                    continue
                _key = ("shape", _ovl_excerpt(_t), type(_s).__name__)
                if _key in _OVL_SEEN:
                    continue
                try:
                    _pts = _s.points
                    _step = max(1, len(_pts) // 200)
                    _hit = False
                    _prev = None
                    for _i in range(0, len(_pts), _step):
                        _p = _pts[_i]
                        if _prev is not None:
                            for _f in (0.0, 0.34, 0.67, 1.0):
                                _x = _prev[0] + (_p[0] - _prev[0]) * _f
                                _y = _prev[1] + (_p[1] - _prev[1]) * _f
                                if _l2 < _x < _r2 and _b2 < _y < _t2:
                                    _hit = True
                                    break
                        if _hit:
                            break
                        _prev = _p
                    if _hit:
                        _OVL_SEEN.add(_key)
                        _ovl_report("text-over-shape", f"{type(_t).__name__}({_key[1]!r}) at [{_t.get_center()[0]:.1f},{_t.get_center()[1]:.1f}] is crossed by {type(_s).__name__}", tag)
                except Exception:
                    continue

    def _ovl_check(scene, tag):
        try:
            _texts_r, _shapes = _ovl_scan(scene.mobjects)
            _texts = [_t for _t, _rid in _texts_r]
            _ovl_clip_check(_texts, tag)
            _ovl_shape_check(_texts_r, _shapes, tag)
            _ovl_shape_pair_check(_shapes, tag)
            for _i in range(len(_texts)):
                for _j in range(_i + 1, len(_texts)):
                    _a, _b = _texts[_i], _texts[_j]
                    if not _ovl_visible(_a) or not _ovl_visible(_b):
                        continue
                    try:
                        _xo = min(_a.get_right()[0], _b.get_right()[0]) - max(_a.get_left()[0], _b.get_left()[0])
                        _yo = min(_a.get_top()[1], _b.get_top()[1]) - max(_a.get_bottom()[1], _b.get_bottom()[1])
                        _amin = min(_a.width * _a.height, _b.width * _b.height)
                    except Exception:
                        continue
                    # Flag real pile-ups, not pixel-grazes: both axes penetrated and
                    # the intersection covers >=15% of the smaller bounding box.
                    if _xo > 0.05 and _yo > 0.05 and _xo * _yo >= 0.15 * max(_amin, 1e-6):
                        _key = (type(_a).__name__, _ovl_excerpt(_a), type(_b).__name__, _ovl_excerpt(_b))
                        if _key in _OVL_SEEN:
                            continue
                        _OVL_SEEN.add(_key)
                        _ca, _cb = _a.get_center(), _b.get_center()
                        _ovl_report("overlap", f"{_key[0]}({_key[1]!r}) at [{_ca[0]:.1f},{_ca[1]:.1f}] x {_key[2]}({_key[3]!r}) at [{_cb[0]:.1f},{_cb[1]:.1f}] depth {_xo:.2f}x{_yo:.2f}", tag)
        except Exception:
            pass

    _ovl_orig_play = _OvlScene.play

    def _ovl_play(self, *args, **kwargs):
        _r = _ovl_orig_play(self, *args, **kwargs)
        _OVL_STATE["beat"] += 1
        _ovl_check(self, f"play#{_OVL_STATE['beat']}")
        return _r

    _OvlScene.play = _ovl_play
except Exception as _ovl_exc:
    print(f"LAYOUT_PROBE_ERROR: {_ovl_exc}")
'''


# Classes that count toward repair/acceptance. ``shape-overlap`` is deliberately absent:
# a new measurement proves itself before it is allowed to trigger anything.
COUNTED = ("overlap", "off-frame", "text-over-shape", "truncation")

_LINE = re.compile(r"LAYOUT_VIOLATION:\s*(?P<kind>shape-overlap|text-over-shape|off-frame|overlap|truncation)\b(?P<rest>.*)")
_TRUNC = re.compile(r"LAYOUT_VIOLATION:\s*(?P<tkind>[\w-]+)\s+report truncated\b(?P<rest>.*)")
_installed = False


def install() -> bool:
    """Patch ``Scene.play`` in this process. Idempotent; True when the probe is active."""
    global _installed
    if not _installed:
        exec(compile(PROBE_SNIPPET, "<lessonforge.layout_probe>", "exec"), {})
        _installed = True
    return _installed


def parse(log_text: str) -> list[dict]:
    """``LAYOUT_VIOLATION`` lines → ``[{kind, detail, counted}]`` (unknown kinds are skipped)."""
    found = []
    for line in (log_text or "").splitlines():
        tm = _TRUNC.search(line)
        if tm:
            tkind = tm.group("tkind")
            # Truncation of any counted violation is treated as a counted fault
            counted = tkind in ("overlap", "off-frame", "text-over-shape")
            found.append({"kind": "truncation", "detail": line.strip(), "counted": counted})
            continue
        m = _LINE.search(line)
        if m:
            kind = m.group("kind")
            found.append({"kind": kind, "detail": m.group("rest").strip(), "counted": kind in COUNTED})
    return found
