import ast
import json
import logging
import math
import os
import re
import sys
from collections import deque

from .mathfix import sanitize_math

logger = logging.getLogger(__name__)

# Central visual theme (canvas background, accent, shape palette). Co-located
# with this module; guarded so a missing theme.py degrades to the pre-theme look
# rather than breaking the sole full-scene codegen path.
try:
    from lessonforge.theme import (resolve_theme, shape_default_color, DEFAULT_THEME,
                       harmonize as _harmonize)
    _HAS_THEME = True
except Exception:  # pragma: no cover - defensive
    _HAS_THEME = False
    DEFAULT_THEME = None

    def resolve_theme(style="", background="default"):
        return None

    def shape_default_color(theme, palette_state):
        return None

    def _harmonize(color, theme, kind="shape", background="default"):
        return color or None


def harmonize_color(color, theme, el_type):
    """Model colour → theme-legal colour. Returns None when there was no colour.

    Assets carry their own artwork (a photo, a molecule diagram, a fetched icon),
    so their colour field is not a fill to remap — leave those alone.

    A colour the theme did NOT change comes back EXACTLY as written, name and all:
    `RED` must stay `.set_color(RED)` rather than becoming `.set_color("#FC6255")`.
    Only genuinely remapped colours turn into hex, so the emitted diff shows what
    was actually changed and generated code stays readable.
    """
    if el_type in ("svg_icon", "chemical_molecule", "image"):
        return color or None
    harmonized = _harmonize(color, theme, el_type)
    if harmonized and _HAS_THEME:
        try:
            from lessonforge.theme import _to_hex
            if _to_hex(color) == harmonized:
                return color
        except Exception:  # pragma: no cover - defensive
            pass
    return harmonized

# ---------------------------------------------------------------------------
# Animation configs  (anim_name, extra_kwargs_str)
# Entrances are a calm rise-and-fade (shift=UP*0.25, smooth ease). The former
# scale=0.1 + ease_out_elastic "Kurzgesagt pop" was retired 2026-07-31 after
# user review of the social-science batch: with 4-7 elements per scene every
# beat bounced and the whole video read as SHAKING. One element popping is a
# style; everything wobbling is a defect. Don't reintroduce elastic as a
# default — if a themed "pop" returns, gate it to at most one hero element
# per scene.
# Write handles its own reveal; Create/GrowFromCenter don't accept shift kwarg.
# ---------------------------------------------------------------------------
_CALM_FADE = "shift=UP * 0.25, rate_func=rate_functions.ease_out_cubic"

_ENTRANCE_CONFIG = {
    "text":              ("FadeIn",         _CALM_FADE),
    "math":              ("Write",          ""),
    "math_evolution":    ("Write",          ""),
    "shape":             ("GrowFromCenter", ""),
    "coordinate_system": ("Create",         ""),
    "graph":             ("Create",         ""),
    "svg_icon":          ("FadeIn",         _CALM_FADE),
    "chemical_molecule": ("FadeIn",         _CALM_FADE),
    "image":             ("FadeIn",         _CALM_FADE),
    # A generated simulation is a whole assembled system; FadeIn is the only
    # entrance that reads sensibly (and Write on a VGroup of dots does not).
    "simulation":        ("FadeIn",         _CALM_FADE),
}

_ENTRANCE_ANIMS = frozenset({
    "FadeIn", "Write", "Create", "GrowFromCenter", "DrawBorderThenFill",
    "GrowArrow", "SpinInFromNothing", "FadeInFromPoint", "AddTextLetterByLetter",
    "ShowCreation",
})

_EXIT_ANIMS = frozenset({
    "FadeOut", "Uncreate", "ShrinkToCenter", "FadeOutAndShift", "Unwrite",
})

# ---------------------------------------------------------------------------
# Positioning maps
# ---------------------------------------------------------------------------
_SAFE_ZONE_MAP = {
    "TOP_CENTER":    ".to_edge(UP, buff=0.3)",
    "BOTTOM_CENTER": ".to_edge(DOWN, buff=0.3)",
    "TOP_LEFT":      ".to_corner(UL, buff=0.3)",
    "TOP_RIGHT":     ".to_corner(UR, buff=0.3)",
    "LEFT_CENTER":   ".to_edge(LEFT, buff=0.3)",
    "RIGHT_CENTER":  ".to_edge(RIGHT, buff=0.3)",
    "BOTTOM_LEFT":   ".to_corner(DL, buff=0.3)",
    "BOTTOM_RIGHT":  ".to_corner(DR, buff=0.3)",
}

# Fallback chain when a zone is already occupied — ordered by spatial distance
_ZONE_FALLBACKS = {
    "TOP_CENTER":    ["TOP_LEFT", "TOP_RIGHT", "LEFT_CENTER", "RIGHT_CENTER", "BOTTOM_CENTER"],
    "BOTTOM_CENTER": ["BOTTOM_LEFT", "BOTTOM_RIGHT", "LEFT_CENTER", "RIGHT_CENTER", "TOP_CENTER"],
    "TOP_LEFT":      ["TOP_CENTER", "LEFT_CENTER", "TOP_RIGHT", "BOTTOM_LEFT"],
    "TOP_RIGHT":     ["TOP_CENTER", "RIGHT_CENTER", "TOP_LEFT", "BOTTOM_RIGHT"],
    "LEFT_CENTER":   ["TOP_LEFT", "BOTTOM_LEFT", "TOP_CENTER", "RIGHT_CENTER"],
    "RIGHT_CENTER":  ["TOP_RIGHT", "BOTTOM_RIGHT", "TOP_CENTER", "LEFT_CENTER"],
    "BOTTOM_LEFT":   ["BOTTOM_CENTER", "LEFT_CENTER", "BOTTOM_RIGHT", "TOP_LEFT"],
    "BOTTOM_RIGHT":  ["BOTTOM_CENTER", "RIGHT_CENTER", "BOTTOM_LEFT", "TOP_RIGHT"],
}

_DIRECTION_MAP = {
    "UP": "UP", "DOWN": "DOWN", "LEFT": "LEFT", "RIGHT": "RIGHT",
    "UP_RIGHT": "UR", "UP_LEFT": "UL", "DOWN_RIGHT": "DR", "DOWN_LEFT": "DL",
}

_MANIM_COLORS = frozenset({
    "BLUE", "RED", "GREEN", "WHITE", "BLACK", "YELLOW", "ORANGE",
    "PURPLE", "PINK", "GRAY", "GREY", "TEAL", "GOLD", "MAROON",
    "BLUE_A", "BLUE_B", "BLUE_C", "BLUE_D", "BLUE_E",
    "GREEN_A", "GREEN_B", "GREEN_C", "GREEN_D", "GREEN_E",
    "RED_A", "RED_B", "RED_C", "RED_D", "RED_E",
    "YELLOW_A", "YELLOW_B", "YELLOW_C", "YELLOW_D", "YELLOW_E",
    "LIGHT_GRAY", "LIGHT_GREY", "DARK_GREY", "DARK_GRAY",
})

_Z_INDEX = {
    "shape": 0, "coordinate_system": 0, "graph": 0,
    "svg_icon": 2, "chemical_molecule": 2, "image": 1,
    "math": 5, "text": 10,
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _color_expr(color):
    if not color:
        return None
    c = color.strip()
    if c.upper() in _MANIM_COLORS:
        return c.upper()
    if c.startswith("#"):
        return f'"{c}"'
    return None


def _safe_zone_suffix(requested, used_zones):
    """
    Return a Manim positioning suffix for the requested safe zone.
    If the zone is already claimed this scene, pick the best available
    fallback. If all zones are taken, shift the element down within the
    requested zone. Mutates used_zones in place.
    """
    if not requested or requested not in _SAFE_ZONE_MAP:
        return None
    candidates = [requested] + _ZONE_FALLBACKS.get(requested, [])
    for zone in candidates:
        if zone not in used_zones and zone in _SAFE_ZONE_MAP:
            used_zones[zone] = 1
            return _SAFE_ZONE_MAP[zone]
    # All zones taken — stack within requested zone, shifting toward frame
    # centre (a DOWN shift from a BOTTOM zone walks off-screen).
    n = used_zones.get(requested, 0)
    used_zones[requested] = n + 1
    stack_dir = "UP" if requested.startswith("BOTTOM") else "DOWN"
    return f"{_SAFE_ZONE_MAP[requested]}.shift({stack_dir} * {n * 0.85:.2f})"


# Content-aware timing: how much of the narration beat an entrance should use
# (fraction of tracker.duration) and its floor in seconds. An Axes needs time to
# draw; a formula needs legible Write time; a dot can snap in. run_time is capped
# at the beat so animations never outrun their narration.
_TIMING = {  # el_type: (fraction_of_beat, floor_seconds)
    "coordinate_system": (0.9, 1.5),
    "graph":             (0.9, 1.5),
    "math":              (0.7, 1.0),
    "math_evolution":    (0.7, 1.0),
    "text":              (0.5, 0.8),
    "svg_icon":          (0.5, 0.8),
    "chemical_molecule": (0.5, 0.8),
    "image":             (0.5, 0.8),
    "shape":             (0.35, 0.5),
}


def _run_time_expr(el_types):
    """run_time expression for a cue's entrance play, driven by the heaviest
    element being shown rather than a flat multiplier."""
    frac, floor = max(
        (_TIMING.get(t, (0.5, 0.8)) for t in el_types),
        key=lambda p: p[0],
    )
    return f"min(max({floor}, tracker.duration * {frac}), tracker.duration)"


def _sustain_call(entered_vars, scene_vars, accent, indent=" " * 12):
    """Emit the beat filler for one cue.

    A voiceover block plays its entrances in the first ~half of the narration and
    then holds a STILL FRAME for the rest (measured: 2-3s of animation in an 8-12s
    beat). `sustain` spends that time gesturing at what the cue just introduced —
    or, for a cue that introduced nothing new, at the last few things on screen, so
    a purely narrated beat still moves. Every gesture is round-trip, so the layout
    probe (which measures after every play) sees the same geometry it did before.
    """
    # No `accent=`: every gesture is geometric now that the colour pulse is gone
    # (viz_helpers._sustain_gesture). The parameter is still ACCEPTED there so
    # scripts emitted before the change keep running.
    targets = [v for _, v in entered_vars] or list(scene_vars)[-3:]
    return f"{indent}sustain(self, [{', '.join(targets)}], tracker)"


# Shape vocabulary: ONE table drives both the emitted object and its entrance,
# so the two can no longer drift ("arrow pointing at X" builds a Dot via the
# "point" match, so it must GrowFromCenter, not GrowArrow).
#
# Keywords match as word-START prefixes: "arrows" hits `arrow`, "narrow" does
# not. The old code used plain `in`, the same substring trap that once made
# "grade 1" match "grade 11" in the planner.
_SHAPE_KINDS = [
    (("point", "dot"),                        "Dot(radius=0.1)",      ("GrowFromCenter", "")),
    (("circle", "node", "bubble"),            "Circle()",             ("DrawBorderThenFill", "")),
    (("ellipse", "oval"),                     "Ellipse()",            ("DrawBorderThenFill", "")),
    (("square",),                             "Square()",             ("DrawBorderThenFill", "")),
    (("rect", "frame", "panel", "box", "tray", "tile", "block", "slab", "card"),
                                              "Rectangle()",          ("DrawBorderThenFill", "")),
    (("triangle",),                           "Triangle()",           ("DrawBorderThenFill", "")),
    (("star", "burst", "spark"),              "Star()",               ("DrawBorderThenFill", "")),
    (("cross", "x-mark"),                     "Cross()",              ("Create", "")),
    (("arrow",),                              "Arrow(ORIGIN, RIGHT)", ("GrowArrow", "")),
    (("line", "branch", "segment", "edge", "connector"),
                                              "Line(LEFT, RIGHT)",    ("Create", "")),
]

# Shapes that enclose an area, so a value can sit inside them.
_CLOSED_SHAPES = frozenset({
    "Circle()", "Square()", "Rectangle()", "Triangle()", "Ellipse()", "Star()",
})

# A shape's `content` is prose by schema ("For shape, a description"). Everything
# after one of these words describes the shape's CONTENTS, decoration or
# neighbours — not the shape itself. Matching the whole string turned
# "two chalk branches from 84 to circles containing 12 and 7" into a Circle.
_SHAPE_CLAUSE_RE = re.compile(
    r"\b(?:containing|contains|labell?ed|showing|holding|with|from|to|ending|"
    r"surrounding|around|over|under|beside|next|inside|within|reordered|"
    r"connecting|linking|that|which|as)\b|[,;:]"
)

# "circle containing 84" must render the 84. Without this every node of a factor
# tree drew as an empty ring and the video lost its entire teaching content.
_SHAPE_VALUE_RE = re.compile(
    r"\b(?:containing|contains|labell?ed|showing|reading|marked)\s+"
    r"([A-Za-z0-9²³×÷+\-=./]{1,8})(?=$|[\s,.;:])",
    re.IGNORECASE,
)

# Adjectives/quantifiers that never name the shape, dropped when picking a
# search keyword for the asset cascade.
_SHAPE_STOPWORDS = frozenset({
    "large", "small", "big", "tiny", "wide", "narrow", "tall", "short", "thin", "thick",
    "chalk", "pastel", "neon", "bright", "dark", "light", "soft", "bold", "simple",
    "clean", "the", "and", "single", "double", "two", "three", "four", "five", "six",
    "several", "many", "first", "second", "third", "final", "same", "row", "pair",
    "set", "group", "diagram", "icon", "symbol", "shape", "drawing", "sketch", "style",
    "red", "blue", "green", "yellow", "orange", "purple", "pink", "cyan", "teal",
    "magenta", "white", "black", "grey", "gray", "gold", "coral", "violet", "indigo",
})


def _shape_head(content):
    """The leading fragment of a prose description that names the shape itself."""
    lowered = (content or "").lower()
    head = _SHAPE_CLAUSE_RE.split(lowered, 1)[0].strip()
    return head or lowered


def _shape_keyword_match(text):
    for kws, expr, entrance in _SHAPE_KINDS:
        for kw in kws:
            # "cross-section of a leaf" is not a Cross.
            if kw == "cross" and re.search(r"\bcross[- ]?section", text):
                continue
            if re.search(r"\b" + re.escape(kw), text):
                return expr, entrance
    return None, None


def _resolve_shape(content):
    """Prose shape description -> (manim_expr, entrance) or (None, None).

    Tries the head fragment first, then the whole description. (None, None)
    means no primitive fits and the caller should route to the asset cascade.
    """
    expr, entrance = _shape_keyword_match(_shape_head(content))
    if expr:
        return expr, entrance
    return _shape_keyword_match((content or "").lower())


def _shape_value_label(content):
    """The short value a shape is described as containing, e.g. '84'. None if the
    description names contents that aren't a single drawable value."""
    text = content or ""
    m = _SHAPE_VALUE_RE.search(text)
    if not m:
        return None
    tok = m.group(1).strip(".,;:")
    # A value carries a digit; "containing twelve evenly spaced slots" is prose.
    if not tok or not any(ch.isdigit() for ch in tok):
        return None
    # "containing 12 and 7" / "containing 2, 2, 3 and 5" describe SEVERAL nodes.
    # One shape carrying the first of them would state something false, so draw
    # the bare shape and let the storyboard's own labels do the talking.
    # A separator followed by ANOTHER VALUE means several nodes are described.
    # A separator followed by prose ("containing 60, drawn as a block") does not.
    if re.match(r"\s*(?:,|and|&)\s*[A-Za-z0-9]*\d", text[m.end():], re.IGNORECASE):
        return None
    return tok


def _shape_asset_keyword(content):
    """Best search phrase for the asset cascade, from a prose description."""
    words = [w for w in re.findall(r"[a-z]+", _shape_head(content))
             if len(w) > 2 and w not in _SHAPE_STOPWORDS]
    if not words:
        return ""
    return " ".join(words[-2:]) if len(words) >= 2 else words[0]


def _hero_image_place(el, scene_state, elements):
    """Centre the scene's FIRST free-standing image on the stage.

    Storyboard models park photos in edge zones like ordinary furniture, which
    left the 2026-07-31 social-science batch with small corner-pinned photos
    and an empty stage centre. The primary image IS the stage: it takes centre
    (slightly high so BOTTOM captions fit), its anchored labels ride along, and
    the split-screen minimize still moves it aside if text later piles up.
    Model-authored relative/absolute placement is respected; only zone/unset
    placement is overridden, and only for the first image, only in scenes
    without axes (beside an Axes the zones are correct)."""
    if el.get("type") != "image" or scene_state.get("hero_image_done"):
        return
    if any(e.get("type") in ("coordinate_system", "graph") for e in elements):
        return
    if el.get("relative_positioning") or el.get("absolute_position") or el.get("position"):
        return
    el.pop("safe_zone_alignment", None)
    el["absolute_position"] = [0, 0.3]
    scene_state["hero_image_done"] = True


def _collect_image_ids(storyboard):
    """Element ids of every `image` element in the board — highlight events on
    these must Circumscribe (outline), never Indicate (recolors the bitmap)."""
    return {
        el.get("id")
        for sc in storyboard.get("visual_storyboard", [])
        for el in (sc.get("elements") or [])
        if el.get("type") == "image" and el.get("id")
    }


# Entrances that only work on ONE mobject family. A model-authored
# `entrance_animation` is a WORD, not a guarantee about the object we emit:
# GrowArrow calls `.scale(0, scale_tips=True)`, which every non-Arrow VMobject
# rejects with a TypeError that kills the whole scene at render time.
#
# Measured 2026-08-15: a "velocity arrow" element whose prose head matched
# `point` built `Dot(radius=0.1)` — correctly, per _SHAPE_KINDS — but carried
# entrance_animation="GrowArrow" from the board, and took its scene down.
# _SHAPE_KINDS exists precisely so object and entrance cannot drift; honouring
# the override unconditionally undid that agreement one line later.
_ARROW_MOBJECTS = ("Arrow", "Vector", "DoubleArrow", "CurvedArrow", "LabeledArrow")


def _entrance_supported(anim_name, el_type, obj_expr):
    """Can the object we actually emit take this entrance?

    Only the entrances that RAISE on the wrong family are policed — a merely
    odd-looking entrance is the model's call, a crashing one is not.
    """
    expr = (obj_expr or "").strip()
    head = expr.split("(")[0]
    if anim_name == "GrowArrow":
        if head == "connector":
            # connector() returns an Arrow only when it was asked for one.
            return "arrow=True" in expr
        return head in _ARROW_MOBJECTS
    if anim_name == "AddTextLetterByLetter":
        # Needs `.chars`, which only Text has (MathTex and VGroups do not).
        return el_type == "text"
    return True


def _build_entrance_call(el_type, anim_override, var_name, content="", obj_expr=""):
    """Return an animation call string (no run_time — applied on outer play)."""
    # Force FadeIn for asset types that may not support Write/Create
    # (ImageMobject is not a VMobject — Write/Create/DrawBorderThenFill crash on it)
    if el_type in ("svg_icon", "chemical_molecule", "image", "simulation"):
        anim_name, extra = "FadeIn", _CALM_FADE
    else:
        anim_name, extra = _ENTRANCE_CONFIG.get(el_type, ("FadeIn", _CALM_FADE))
        if el_type == "shape":
            # Same resolver the object builder uses, so the animation always
            # matches the object actually emitted.
            _expr, cfg = _resolve_shape(content)
            if cfg and _entrance_supported(cfg[0], el_type, obj_expr or _expr):
                anim_name, extra = cfg
        # Honour schema override if it's a known safe entrance AND the object we
        # actually emit can take it (the override must not undo the object↔entrance
        # agreement _SHAPE_KINDS just established).
        if anim_override:
            override = anim_override.strip().split("(")[0].strip()
            if override in _ENTRANCE_ANIMS and _entrance_supported(override, el_type, obj_expr):
                anim_name = override
                # strip FadeIn-only kwargs for non-FadeIn animations
                if override not in ("FadeIn", "FadeInFromPoint"):
                    extra = ""
    parts = [var_name]
    if extra:
        parts.append(extra)
    return f"{anim_name}({', '.join(parts)})"


def _split_anim_calls(event_str):
    """Split comma-separated animation call string respecting paren nesting."""
    calls, depth, current = [], 0, []
    for ch in event_str:
        if ch == "(":
            depth += 1
            current.append(ch)
        elif ch == ")":
            depth -= 1
            current.append(ch)
        elif ch == "," and depth == 0:
            tok = "".join(current).strip()
            if tok:
                calls.append(tok)
            current = []
        else:
            current.append(ch)
    tok = "".join(current).strip()
    if tok:
        calls.append(tok)
    return calls


# Animation classes the legacy free-text `event` path is allowed to emit.
# Anything outside this set is dropped rather than pasted into generated code.
_VALID_ANIM_NAMES = frozenset({
    "Transform", "ReplacementTransform", "TransformMatchingTex",
    "TransformMatchingShapes", "FadeTransform", "ClockwiseTransform",
    "CounterclockwiseTransform",
    # Colour-flash emphasis (Indicate / Circumscribe / Flash / FocusOn) is
    # deliberately absent — removed 2026-08-15 on user review. Dropping it here too
    # keeps the legacy free-text path from reintroducing through the back door what
    # the structured `highlight` action no longer emits.
    "Wiggle", "ApplyWave",
    "ShowPassingFlash", "MoveAlongPath", "Rotate", "Rotating", "ScaleInPlace",
    "GrowFromEdge", "GrowFromPoint", "RemoveTextLetterByLetter",
    "ShowIncreasingSubsets",
    "AnimationGroup", "LaggedStart", "LaggedStartMap", "Succession",
}) | _ENTRANCE_ANIMS | _EXIT_ANIMS


def _is_valid_anim_expr(node):
    """True if `node` is an expression that evaluates to a Manim Animation.

    Two accepted shapes: a call to a whitelisted animation class
    (`Indicate(ball)`), or a call on an `.animate` chain
    (`ball.animate.shift(RIGHT)`). A bare name is explicitly NOT valid — it
    is a Mobject, and `self.play(mobj)` raises at runtime.
    """
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    if isinstance(func, ast.Name):
        return func.id in _VALID_ANIM_NAMES
    if isinstance(func, ast.Attribute):
        # Walk the attribute chain looking for `.animate`.
        cur = func
        while isinstance(cur, ast.Attribute):
            if cur.attr == "animate":
                return True
            cur = cur.value
        return False
    return False


def _sanitize_anim_calls(calls, where=""):
    """Keep only the calls that are real animation expressions.

    The storyboard's free-text `event` field is model-authored prose as often
    as it is code ("the ball falls and bounces"). Emitting it verbatim put
    that prose inside `self.play(...)`, which is a SyntaxError that kills the
    whole scene — and a bare element id compiled fine but blew up at render
    time. Structure is the transpiler's to own, so unparseable or non-animation
    fragments are dropped here instead of failing downstream.
    """
    kept = []
    for call in calls:
        try:
            expr = ast.parse(call.strip(), mode="eval").body
        except SyntaxError:
            print(f"[TRANSPILER] dropped unparseable event fragment{where}: {call!r}",
                  flush=True, file=sys.stderr)
            continue
        if _is_valid_anim_expr(expr):
            kept.append(call)
        else:
            print(f"[TRANSPILER] dropped non-animation event fragment{where}: {call!r}",
                  flush=True, file=sys.stderr)
    return kept


def _rewrite_ids(anim_str, id_to_var):
    """Replace bare element IDs with their mobj_scene{N}_ var names."""
    result = anim_str
    for el_id in sorted(id_to_var, key=len, reverse=True):
        result = re.sub(rf"\b{re.escape(el_id)}\b", id_to_var[el_id], result)
    return result


def _make_axis_range(mn: float, mx: float) -> list:
    """Return [min, max, step] with a nice step that yields ~8-12 ticks."""
    if mx <= mn:
        mx = mn + 10.0
    span = mx - mn
    raw = span / 10.0
    for nice in (0.1, 0.2, 0.25, 0.5, 1, 2, 5, 10, 20, 25, 50, 100, 200, 500, 1000, 5000, 10000):
        if raw <= nice:
            return [mn, mx, nice]
    magnitude = 10 ** math.floor(math.log10(raw))
    return [mn, mx, round(math.ceil(raw / magnitude) * magnitude, 10)]


# Compiled once — supports: x:0-14  x:0 to 14  x:[-5,5]  x:-5 to 5
_AXIS_BRACKET_RE = re.compile(
    r'([xy])\s*[=:]\s*[\[\(]\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*[\]\)]',
    re.IGNORECASE,
)
_AXIS_TO_RE = re.compile(
    r'([xy])\s*[=:]\s*(-?\d+(?:\.\d+)?)\s+to\s+(-?\d+(?:\.\d+)?)',
    re.IGNORECASE,
)
_AXIS_DASH_RE = re.compile(
    r'([xy])\s*[=:]\s*(-?\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)',
    re.IGNORECASE,
)


def _parse_axis_range(content: str, axis: str, default: list) -> list:
    """Extract [min, max, step] for `axis` from a content hint string.

    Recognised formats (case-insensitive):
      x:[0,14]   x:(0,14)   — bracket/paren
      x:0 to 14             — 'to' separator (handles negative mins cleanly)
      x:0-14                — dash separator (positive min only to avoid ambiguity)
    Falls back to `default` when nothing matches.
    """
    for pattern in (_AXIS_BRACKET_RE, _AXIS_TO_RE, _AXIS_DASH_RE):
        m = pattern.search(content)
        if m and m.group(1).lower() == axis.lower():
            try:
                return _make_axis_range(float(m.group(2)), float(m.group(3)))
            except (ValueError, IndexError):
                pass
    return default


def _has_positioning(el):
    return bool(
        el.get("safe_zone_alignment") or
        el.get("relative_positioning") or
        el.get("absolute_position")
    )


def _apply_template_zones(elements, template):
    """Assign safe_zone_alignment per layout template (only where no positioning exists)."""
    if not elements or not template:
        return
    if template == "TitleStageCaption":
        if not _has_positioning(elements[0]):
            elements[0]["safe_zone_alignment"] = "TOP_CENTER"
        if len(elements) > 1 and not _has_positioning(elements[-1]):
            elements[-1]["safe_zone_alignment"] = "BOTTOM_CENTER"
    elif template == "SplitScreen":
        side_idx = 0
        for el in elements:
            if not _has_positioning(el):
                el["safe_zone_alignment"] = "LEFT_CENTER" if side_idx % 2 == 0 else "RIGHT_CENTER"
                side_idx += 1
    elif template == "ProcessFlow":
        # A mechanism read left-to-right: first unpositioned element starts LEFT_CENTER,
        # last lands RIGHT_CENTER; intermediate stages are left to the zone allocator so
        # the centre stage (and its collision handling) stays code-owned.
        unpos = [el for el in elements if not _has_positioning(el)]
        if len(unpos) >= 2:
            unpos[0]["safe_zone_alignment"] = "LEFT_CENTER"
            unpos[-1]["safe_zone_alignment"] = "RIGHT_CENTER"
    elif template == "BeforeAfter":
        # First half of unpositioned elements = the BEFORE state (left), second half =
        # the AFTER state (right). Differs from SplitScreen's alternation: the halves
        # stay together, so each state reads as one grouped picture.
        unpos = [el for el in elements if not _has_positioning(el)]
        half = (len(unpos) + 1) // 2
        for i, el in enumerate(unpos):
            el["safe_zone_alignment"] = "LEFT_CENTER" if i < half else "RIGHT_CENTER"


def _element_refs(el):
    """Ids this element must be emitted AFTER: its anchor and both edge endpoints."""
    refs = []
    rel_pos = el.get("relative_positioning")
    if rel_pos:
        ref_id = (rel_pos.get("relative_to") if isinstance(rel_pos, dict)
                  else getattr(rel_pos, "relative_to", ""))
        if ref_id:
            refs.append(ref_id)
    conn = el.get("connects")
    if isinstance(conn, (list, tuple)):
        refs.extend([c for c in conn if isinstance(c, str) and c])
    return refs


# The box a generated simulation is built and VERIFIED inside (app/sim_gen.BOX_W/H).
# Asking for a different box here would place geometry the verifier never checked, so
# these two numbers must move together with sim_gen's.
_SIM_BOX_W = 6.0
_SIM_BOX_H = 4.0


def _is_sim_path(content):
    """True when an element's content is a resolved generated-module path."""
    text = str(content or "").strip()
    return text.endswith(".py") and os.path.isabs(text)


def _drawn_shape_height(scale):
    """On-screen height for a drawn `shape`, from the model's `scale` intent.

    A shape's `scale` is a MULTIPLIER on a primitive (a Manim Circle is ~2 units tall),
    whereas `drawing()` takes a height. Converting rather than passing `scale` straight
    through keeps the model's relative sizing — a scene's 1.4 main visual still reads
    bigger than its 0.7 supporting parts — instead of silently shrinking every drawn
    object to sub-unit size.
    """
    try:
        value = float(scale) if scale else 0.7
    except (TypeError, ValueError):
        value = 0.7
    return round(max(_DRAWN_MIN_H, min(4.0, value * 2.0)), 2)


# A drawn object has INTERNAL STRUCTURE — a hoop has a backboard, a rim and a net — and
# structure needs size to read. The schema default `scale` of 0.7 was chosen for text and
# for flat icon silhouettes; measured 2026-08-15, passing it straight through rendered
# every drawn object under one unit tall in an eight-unit frame, so a frame full of
# correct geometry still read as empty. Same rule the image path already applies:
# anything below the "clearly deliberate" threshold is treated as unset.
_DRAWN_MIN_H = 1.2
_DRAWN_DEFAULT_H = 1.9
_DRAWN_DELIBERATE = 1.5


def _drawn_icon_height(scale):
    """On-screen height for a drawn `svg_icon`, in scene units."""
    try:
        value = float(scale) if scale else 0.0
    except (TypeError, ValueError):
        value = 0.0
    if value >= _DRAWN_DELIBERATE:
        return round(min(4.0, value), 2)
    return _DRAWN_DEFAULT_H


def _sim_play_line(indent, var_name):
    """The line that actually runs a simulation during its beat.

    Timed off the narration's remaining duration, capped: the system should evolve
    while it is being explained, but it must not eat the cues that follow. `sim_play`
    always returns a playable Animation, so this line cannot raise at render time.
    """
    return (f"{indent}self.play(sim_play({var_name}, run_time=min(4.5, max(1.2, "
            f"tracker.get_remaining_duration() * 0.55))))")


def _connects_pair(el, known_ids=None):
    """The two endpoint ids of a valid edge element, else None.

    An edge referencing an element that isn't in this scene is dropped rather
    than emitted — the per-scene render lesson: a script only knows its own ids.
    """
    conn = el.get("connects")
    if not isinstance(conn, (list, tuple)) or len(conn) != 2:
        return None
    a, b = conn[0], conn[1]
    if not (isinstance(a, str) and isinstance(b, str)) or not a or not b or a == b:
        return None
    if known_ids is not None and (a not in known_ids or b not in known_ids):
        return None
    return a, b


def _mark_containment(elements):
    """Annotate 'inside' children with their slot index among siblings.

    Placement is a pure function of (parent, index, total), so a container's
    contents are distributed deterministically instead of stacking on its centre.
    """
    el_ids = {el.get("id", "") for el in elements if el.get("id")}
    groups = {}
    for el in elements:
        rel = el.get("relative_positioning")
        if not isinstance(rel, dict) or rel.get("relation") != "inside":
            continue
        parent = rel.get("relative_to", "")
        if not parent or parent not in el_ids:
            continue
        groups.setdefault(parent, []).append(el)
    for parent, kids in groups.items():
        for i, el in enumerate(kids):
            el["_inside_idx"] = i
            el["_inside_total"] = len(kids)
    return elements


_GRAPH_MIN_NODES = 3          # below this a "graph" is just two shapes and a line
_GRAPH_TOP_Y = 2.35           # keep clear of a TOP_CENTER title
_GRAPH_BOTTOM_Y = -2.45       # keep clear of a BOTTOM_CENTER caption
_GRAPH_HALF_W = 5.6           # keep clear of the left/right margins


def _graph_components(elements):
    """Connected components of the node/edge graph declared via `connects`.

    Returns [(node_ids_in_declaration_order, [(a, b), ...]), ...].
    """
    by_id = {el.get("id"): el for el in elements if el.get("id")}
    edges = []
    for el in elements:
        pair = _connects_pair(el, set(by_id))
        if pair:
            edges.append(pair)
    if not edges:
        return []

    adj = {}
    for a, b in edges:
        adj.setdefault(a, set()).add(b)
        adj.setdefault(b, set()).add(a)

    order = [i for i in by_id if i in adj]
    seen, comps = set(), []
    for start in order:
        if start in seen:
            continue
        stack, members = [start], []
        seen.add(start)
        while stack:
            n = stack.pop()
            members.append(n)
            for m in sorted(adj.get(n, ())):
                if m not in seen:
                    seen.add(m)
                    stack.append(m)
        members.sort(key=order.index)          # deterministic, declaration order
        mset = set(members)
        comps.append((members, [(a, b) for a, b in edges if a in mset and b in mset]))
    return comps


def _graph_layers(nodes, edges):
    """BFS depth per node from the declared root (first node of the component).

    Storyboards declare a tree root-first, so the first-declared node is the
    natural root; for a cyclic or unrooted graph BFS from it still produces a
    sane layering.
    """
    adj = {n: [] for n in nodes}
    for a, b in edges:
        adj[a].append(b)
        adj[b].append(a)
    depth = {nodes[0]: 0}
    queue = [nodes[0]]
    while queue:
        n = queue.pop(0)
        for m in adj[n]:
            if m not in depth:
                depth[m] = depth[n] + 1
                queue.append(m)
    for n in nodes:                            # disconnected stragglers
        depth.setdefault(n, 0)
    return depth


def _apply_graph_layout(elements):
    """Compute node coordinates from the GRAPH, not from the model's guesses.

    The governing rule is that the LLM never emits geometry: it says what
    connects to what, and code decides where those things sit. A storyboard's
    hand-written `absolute_position` for tree nodes is exactly the class of
    guess that produced overlapping, off-balance diagrams — so for nodes that
    participate in a declared graph, layout wins.

    Layered top-down: depth -> row, evenly distributed within each row, scaled
    into the band between a title and a caption. Elements anchored INSIDE a node
    (or to it) are untouched and ride along via their own relations.
    """
    by_id = {el.get("id"): el for el in elements if el.get("id")}
    laid_out = []
    for nodes, edges in _graph_components(elements):
        if len(nodes) < _GRAPH_MIN_NODES:
            continue
        depth = _graph_layers(nodes, edges)
        rows = {}
        for n in nodes:
            rows.setdefault(depth[n], []).append(n)

        n_rows = max(rows) + 1
        if n_rows > 1:
            y_step = (_GRAPH_TOP_Y - _GRAPH_BOTTOM_Y) / (n_rows - 1)
        else:
            y_step = 0.0
        for d, row in sorted(rows.items()):
            y = _GRAPH_TOP_Y - d * y_step if n_rows > 1 else 0.6
            count = len(row)
            if count == 1:
                xs = [0.0]
            else:
                span = min(2 * _GRAPH_HALF_W, 2.4 * count)
                xs = [-span / 2 + span * i / (count - 1) for i in range(count)]
            for x, nid in zip(xs, row):
                el = by_id.get(nid)
                if not el:
                    continue
                rel = el.get("relative_positioning")
                if isinstance(rel, dict) and rel.get("relation") == "inside":
                    continue           # contained items are placed by their parent
                el["absolute_position"] = [round(x, 3), round(y, 3)]
                el.pop("safe_zone_alignment", None)
                el.pop("relative_positioning", None)
                el["_graph_laid_out"] = True
                laid_out.append(nid)
    if laid_out:
        print(f"[TRANSPILER] graph layout placed {len(laid_out)} node(s): "
              f"{', '.join(laid_out[:8])}{'…' if len(laid_out) > 8 else ''}",
              file=sys.stderr)
    return elements


def _topo_sort_elements(elements):
    """
    Sort elements within a cue so that if B depends on A (anchored to it, or an
    edge that joins it), A is emitted before B. Falls back to original order for
    cross-scene/circular refs.
    """
    el_ids = {el.get("id", "") for el in elements if el.get("id")}
    independent, waiting = [], []
    for el in elements:
        refs = [r for r in _element_refs(el) if r in el_ids]
        if refs:
            # Wait on the LAST dependency to be satisfied; the loop below retries
            # until every ref is emitted.
            waiting.append((el, refs))
            continue
        independent.append(el)

    ordered = list(independent)
    seen = {el.get("id", "") for el in ordered}
    for _ in range(len(waiting) + 1):
        still = []
        for el, refs in waiting:
            if all(r in seen for r in refs):
                ordered.append(el)
                seen.add(el.get("id", ""))
            else:
                still.append((el, refs))
        waiting = still
        if not waiting:
            break
    for el, _ in waiting:  # circular/cross-scene — append as-is
        ordered.append(el)
    return ordered


def _build_obj_expr(el, scene_idx, scene_id_to_var, failed_assets=None, used_zones=None,
                    default_color=None, theme=None):
    """
    Build the RHS expression that constructs the Manim mobject including
    positioning suffix. Returns a Python expression string.

    ``default_color`` (a theme colour) fills in when the element carries no
    ``color`` of its own. A model-authored colour is HARMONIZED into the theme
    (theme.harmonize): kept when it is legible on this canvas and looks picked,
    mapped to the nearest palette colour by hue when it is a raw primary or
    unreadable. Measured 2026-08-14: 96% of elements carry a model colour and most
    are pure-channel primaries, so without this the style profile decorated ~4% of
    the frame and a light canvas got white-on-white shapes.
    """
    if used_zones is None:
        used_zones = {}
    failed_assets = failed_assets or set()
    el_type = el.get("type", "text")
    content = el.get("content", "")
    color   = harmonize_color(el.get("color", ""), theme, el_type) or el.get("color", "")
    scale   = el.get("scale", 0.7)
    el_id   = el.get("id", "")

    # --- Object construction ---
    if el_type == "text":
        obj_expr = f"Text({repr(content)})"

    elif el_type in ("math", "math_evolution"):
        if el_type == "math_evolution" and "→" in content:
            # Store both states; entrance shows the "from" form.
            # The "to" form is stored as a comment for reference in event strings.
            from_part, to_part = content.split("→", 1)
            from_fixed = sanitize_math(from_part)
            to_fixed   = sanitize_math(to_part)
            # Encode both as substrings so TransformMatchingTex can match parts
            obj_expr = f'MathTex(r"{from_fixed}", substrings_to_isolate=list(r"{from_fixed}"))'
            # Emit a companion _to var immediately after — handled in cue loop below via _EVOLUTION_MAP
            el["_evolution_to"] = to_fixed
        else:
            content_fixed = sanitize_math(content)
            obj_expr = f'MathTex(r"{content_fixed}")'

    elif el_type == "svg_icon":
        if _is_sim_path(content):
            # The server DREW this one in Manim (sim_gen.resolve_drawn_elements) rather
            # than importing clipart. Its own colours carry meaning, so — unlike an
            # imported SVG, which arrives as a flat silhouette that must be recoloured —
            # it is never tinted here.
            obj_expr = f"drawing({repr(content)}, height={_drawn_icon_height(scale)})"
        elif el_id in failed_assets:
            obj_expr = f"Text({repr(content[:20])})"
            el_type = "text"
        else:
            color_val = _color_expr(color) or "WHITE"
            obj_expr = f"fetch_smart_svg({repr(content)}, color={color_val}, height={scale})"

    elif el_type == "chemical_molecule":
        if el_id in failed_assets:
            obj_expr = f"Text({repr(content[:20])})"
            el_type = "text"
        else:
            obj_expr = f"fetch_molecule_svg({repr(content)}, height={scale})"

    elif el_type == "image":
        if el_id in failed_assets:
            obj_expr = f"Text({repr(content[:24])})"
            el_type = "text"
        else:
            # `scale` is the on-screen height in scene units. The schema default
            # (0.7) is sized for text — treat anything below 1.5 as "unset" and
            # give the image a substantial stage presence instead of a thumbnail.
            img_h = scale if (scale and scale >= 1.5) else 3.0
            obj_expr = f"fetch_real_image({repr(content)}, height={img_h})"

    elif el_type == "simulation":
        # `content` is an absolute path to a verified build/animate module, rewritten
        # server-side by sim_gen.resolve_simulation_elements at codegen time. An
        # unresolved element never reaches here (it is degraded to a shape), but a
        # hand-edited board can still carry a description — draw a placeholder rather
        # than trying to load a file that isn't there.
        if _is_sim_path(content):
            obj_expr = f"simulation({repr(content)}, width={_SIM_BOX_W}, height={_SIM_BOX_H})"
            el["_is_simulation"] = True
        else:
            obj_expr = f"Text({repr(str(content)[:28])})"
            el_type = "text"

    elif el_type == "shape" and _connects_pair(el, set(scene_id_to_var)):
        # An EDGE: geometry comes from the two endpoints, never from a position.
        _a, _b = _connects_pair(el, set(scene_id_to_var))
        _av, _bv = scene_id_to_var.get(_a, _a), scene_id_to_var.get(_b, _b)
        _arrow = "arrow" in (content or "").lower()
        _cexpr = _color_expr(color) or _color_expr(default_color) or "WHITE"
        obj_expr = f"connector({_av}, {_bv}, color={_cexpr}, arrow={_arrow})"
        el["_is_edge"] = True

    elif el_type == "shape" and _is_sim_path(content):
        # The server DREW this object in Manim instead of stamping a primitive from the
        # prose table (sim_gen.resolve_drawn_elements). Re-typing it as svg_icon is not
        # cosmetic: it is what suppresses the `.set_color()` and `.scale()` applied
        # below — a drawing sizes itself via height= and its own colours carry meaning.
        obj_expr = f"drawing({repr(content)}, height={_drawn_shape_height(scale)})"
        el["_render_as"] = "svg_icon"
        el_type = "svg_icon"

    elif el_type == "shape":
        # Points must be Dots (filled), not stroke-only circles.
        obj_expr, _entrance = _resolve_shape(content)
        if obj_expr is None:
            # No primitive fits ("chalk starburst", "check mark"). A generic
            # Circle() here was the old behaviour and drew a meaningless ring;
            # the asset cascade knows these, and its own last resort is a native
            # VGroup, so this never fails to return a mobject.
            keyword = _shape_asset_keyword(content)
            if keyword and el_id not in failed_assets:
                color_val = _color_expr(color) or "WHITE"
                obj_expr = f"fetch_smart_svg({repr(keyword)}, color={color_val}, height={scale})"
                # Entrance must follow the object: an SVGMobject can't Write/Create.
                el["_render_as"] = "svg_icon"
                el_type = "svg_icon"
            else:
                obj_expr = "Circle()"
        elif obj_expr in _CLOSED_SHAPES:
            # "circle containing 84" — draw the 84 inside it. Losing this made a
            # whole factor-tree video render as empty rings.
            value = _shape_value_label(content)
            if value:
                obj_expr = f"value_in({obj_expr}, {repr(value)})"

    elif el_type in ("coordinate_system", "graph"):
        _xr = _parse_axis_range(content, "x", [-5, 5, 1])
        _yr = _parse_axis_range(content, "y", [-4, 4, 1])
        obj_expr = f"Axes(x_range={_xr}, y_range={_yr}, axis_config={{'include_numbers': True}})"

    else:
        obj_expr = f"Text({repr(content)})"

    # --- Z-index ---
    obj_expr += f".set_z_index({_Z_INDEX.get(el_type, 10)})"

    # --- Color ---
    # Model-authored colour wins; the theme's default colour fills the gap so
    # uncoloured shapes pick up the scene palette instead of flat white.
    eff_color = color or default_color
    if eff_color and el_type not in ("svg_icon", "chemical_molecule", "image"):
        c_expr = _color_expr(eff_color)
        if c_expr:
            obj_expr += f".set_color({c_expr})"

    # --- Scale (svg/molecule/image handle size via height= in constructor) ---
    if scale and scale != 1.0 and el_type not in ("svg_icon", "chemical_molecule", "image"):
        obj_expr += f".scale({scale})"

    # --- Positioning: an edge owns its own geometry; else safe_zone > relative > absolute ---
    safe_zone = el.get("safe_zone_alignment")
    rel_pos   = el.get("relative_positioning")
    abs_pos   = el.get("absolute_position")

    if el.get("_is_edge"):
        # connector() already anchored it to both endpoints. Any zone/absolute
        # placement the model also wrote would tear it off its nodes.
        return obj_expr

    _inside_parent = None
    if isinstance(rel_pos, dict) and rel_pos.get("relation") == "inside":
        _pid = rel_pos.get("relative_to", "")
        if _pid and _pid in scene_id_to_var:
            _inside_parent = scene_id_to_var.get(_pid, _pid)

    if _inside_parent:
        # Containment wins over any zone the model also set — an element cannot
        # be both inside a container and pinned to a frame edge.
        obj_expr = (f"place_inside({obj_expr}, {_inside_parent}, "
                    f"index={int(el.get('_inside_idx', 0))}, total={int(el.get('_inside_total', 1))})")

    elif safe_zone:
        suffix = _safe_zone_suffix(safe_zone, used_zones)
        if suffix:
            obj_expr += suffix

    elif rel_pos:
        if isinstance(rel_pos, dict):
            ref_id    = rel_pos.get("relative_to", "")
            direction = rel_pos.get("direction", "RIGHT")
            buffer    = rel_pos.get("buffer", 0.5)
        else:
            ref_id    = getattr(rel_pos, "relative_to", "")
            direction = getattr(rel_pos, "direction", "RIGHT")
            buffer    = getattr(rel_pos, "buffer", 0.5)
        manim_dir = _DIRECTION_MAP.get(direction, "RIGHT")
        ref_var   = scene_id_to_var.get(ref_id, ref_id)
        obj_expr += f".next_to({ref_var}, {manim_dir}, buff={buffer})"

    elif abs_pos and len(abs_pos) >= 2:
        obj_expr += _position_suffix(el, abs_pos[0], abs_pos[1])

    elif el.get("position"):
        pos = el["position"]
        if isinstance(pos, (list, tuple)) and len(pos) >= 2:
            obj_expr += _position_suffix(el, pos[0], pos[1])

    # The entrance builder needs to know what was ACTUALLY emitted, not what the
    # element's prose suggests — see _entrance_supported.
    el["_obj_expr"] = obj_expr
    return obj_expr


def _position_suffix(el, x, y):
    """Positioning for an element with explicit coordinates.

    When the scene has an already-emitted Axes and this element is a shape whose
    coordinates fall inside the axes ranges, the coordinates are DATA-space and
    must go through <axes>.c2p() — the axes' unit is not 1 scene unit, so raw
    .move_to() puts points visibly off the gridlines they are labeled with.
    """
    axes = el.get("_c2p_axes")
    if axes:
        return f".move_to({axes}.c2p({x}, {y}))"
    return f".move_to(RIGHT * {x} + UP * {y})"


def _scene_axes_ctx(elements, scene_id_to_var):
    """Return (axes_id, axes_var, x_range, y_range) for the scene's coordinate
    system, or None. Used to route data-space coordinates through c2p."""
    for e in elements:
        if e.get("type") in ("coordinate_system", "graph"):
            eid = e.get("id", "")
            xr = _parse_axis_range(e.get("content", ""), "x", [-5, 5, 1])
            yr = _parse_axis_range(e.get("content", ""), "y", [-4, 4, 1])
            return eid, scene_id_to_var.get(eid, eid), xr, yr
    return None


def _mark_c2p(el, axes_ctx, axes_emitted):
    """Tag a shape element whose coords are data-space (inside the axes ranges)
    so _position_suffix emits <axes>.c2p(x, y). Only after the axes exists."""
    if not axes_ctx or not axes_emitted or el.get("type") != "shape":
        return
    pos = el.get("absolute_position") or el.get("position")
    if not (isinstance(pos, (list, tuple)) and len(pos) >= 2):
        return
    _, axes_var, xr, yr = axes_ctx
    if xr[0] <= pos[0] <= xr[1] and yr[0] <= pos[1] <= yr[1]:
        el["_c2p_axes"] = axes_var


# ---------------------------------------------------------------------------
# Axes-aware zones + label slots — the zone system must know where the axes
# actually sit. Without this, a scene that shifts its axes up keeps the text
# bands fixed and the y-axis runs straight through the question text (the
# scene-4 audit failure); labels shifted blindly toward an axis land on its
# tick numbers (the |x2-x1|-through-the-"3"-tick failure).
# ---------------------------------------------------------------------------

_FRAME_W, _FRAME_H = 14.22, 8.0
# Default Axes(include_numbers=True) bbox before .scale() — measured 12.32 x 6.13
# on Manim CE for typical ranges; padded slightly for label overhang.
_AXES_BASE_W, _AXES_BASE_H = 12.4, 6.2

# Nominal screen rect (x0, x1, y0, y1) a text block occupies when placed in each
# zone — where zone-placed content actually sits, not the whole frame third.
_ZONE_FOOTPRINT = {
    "TOP_CENTER":    (-2.6, 2.6, 2.6, 3.7),
    "BOTTOM_CENTER": (-2.6, 2.6, -3.7, -2.6),
    "LEFT_CENTER":   (-6.8, -3.2, -1.3, 1.3),
    "RIGHT_CENTER":  (3.2, 6.8, -1.3, 1.3),
    "TOP_LEFT":      (-6.8, -3.8, 2.6, 3.7),
    "TOP_RIGHT":     (3.8, 6.8, 2.6, 3.7),
    "BOTTOM_LEFT":   (-6.8, -3.8, -3.7, -2.6),
    "BOTTOM_RIGHT":  (3.8, 6.8, -3.7, -2.6),
}


def _axes_screen_bbox(el):
    """Estimated screen bbox (x0, x1, y0, y1) of a coordinate_system/graph
    element after the transpiler's own scale and positioning are applied."""
    try:
        scale = float(el.get("scale", 0.7) or 0.7)
    except (TypeError, ValueError):
        scale = 0.7
    w, h = _AXES_BASE_W * scale, _AXES_BASE_H * scale
    cx = cy = 0.0
    zone = el.get("safe_zone_alignment")
    pos = el.get("absolute_position") or el.get("position")
    if zone in _SAFE_ZONE_MAP:
        if "LEFT" in zone:
            cx = -_FRAME_W / 2 + 0.3 + w / 2
        elif "RIGHT" in zone:
            cx = _FRAME_W / 2 - 0.3 - w / 2
        if zone.startswith("TOP"):
            cy = _FRAME_H / 2 - 0.3 - h / 2
        elif zone.startswith("BOTTOM"):
            cy = -_FRAME_H / 2 + 0.3 + h / 2
    elif isinstance(pos, (list, tuple)) and len(pos) >= 2:
        try:
            cx, cy = float(pos[0]), float(pos[1])
        except (TypeError, ValueError):
            cx = cy = 0.0
    return (cx - w / 2, cx + w / 2, cy - h / 2, cy + h / 2)


def _seed_axes_zones(used_zones, elements):
    """Pre-claim every safe zone whose footprint the scene's axes bbox overlaps,
    so the existing fallback chains route text AROUND the axes by construction.
    The axes' own requested zone stays free — the axes claims it at emission."""
    axes_el = next(
        (e for e in elements if e.get("type") in ("coordinate_system", "graph")),
        None,
    )
    if not axes_el:
        return
    x0, x1, y0, y1 = _axes_screen_bbox(axes_el)
    g = 0.15  # gutter: near-touching still reads as a collision
    own_zone = axes_el.get("safe_zone_alignment")
    for zone, (zx0, zx1, zy0, zy1) in _ZONE_FOOTPRINT.items():
        if zone == own_zone:
            continue
        if x0 - g < zx1 and x1 + g > zx0 and y0 - g < zy1 and y1 + g > zy0:
            used_zones[zone] = 1


# Tick numbers hug the axis lines — below the x-axis, left of the y-axis. A
# label pushed toward a nearby axis lands on them, so its slot opens away.
_TICK_STRIP = 1.2  # data units within which a push toward the axis hits ticks


def _fix_label_slots(elements, axes_ctx):
    """Flip a label's next_to direction away from an axis tick strip when its
    reference shape sits on the axes close to that axis. Deterministic slot
    choice — the label never covers tick numbers by construction."""
    if not axes_ctx:
        return
    _, _, xr, yr = axes_ctx
    by_id = {e.get("id", ""): e for e in elements if e.get("id")}
    for el in elements:
        if el.get("type") not in ("text", "math", "math_evolution"):
            continue
        rel = el.get("relative_positioning")
        if not isinstance(rel, dict):
            continue
        ref = by_id.get(rel.get("relative_to", ""))
        if not ref or ref.get("type") != "shape":
            continue
        pos = ref.get("absolute_position") or ref.get("position")
        if not (isinstance(pos, (list, tuple)) and len(pos) >= 2):
            continue
        try:
            rx, ry = float(pos[0]), float(pos[1])
        except (TypeError, ValueError):
            continue
        if not (xr[0] <= rx <= xr[1] and yr[0] <= ry <= yr[1]):
            continue  # scene-space reference, not on the axes
        # Tick numbers sit just BELOW the x-axis and just LEFT of the y-axis,
        # so the flip windows are asymmetric and disjoint: a ref on/above an
        # axis pushes its label further out; a ref just below/right of the
        # strip pushes away from it. The (-0.6, -0.2) band stays as requested.
        d = (rel.get("direction") or "RIGHT").upper()
        if "DOWN" in d and -0.2 <= ry <= _TICK_STRIP:
            d = d.replace("DOWN", "UP")
        elif "UP" in d and -_TICK_STRIP <= ry <= -0.6:
            d = d.replace("UP", "DOWN")
        if "LEFT" in d and -0.2 <= rx <= _TICK_STRIP:
            d = d.replace("LEFT", "RIGHT")
        elif "RIGHT" in d and -_TICK_STRIP <= rx <= -0.6:
            d = d.replace("RIGHT", "LEFT")
        rel["direction"] = d


# Screen management: when a derivation (math elements) starts while a diagram is
# on screen, shrink the diagram to the left half first and stack the derivation
# in the right half — instead of writing on top of the axes.
_MINIMIZE_PLAY = (
    "            self.play({group}.animate.scale(0.55).move_to(LEFT * 3.4), run_time=0.8)"
)


_MINIMIZE_TEXTISH = ("math", "math_evolution", "text")


def _minimize_triggers(cue_els, scene_id_to_var, diagram_vars):
    """Count the cue's free-standing text-ish elements — the ones that would pile up
    over an on-screen diagram. Labels anchored to the diagram (axis titles, point
    names) travel with it when it shrinks, so they never trigger a minimize.

    Widened from math-only after a live render (job bpipueek6) minimized on zero of
    its scenes: real storyboards carry derivation steps as `text`, not `math`.
    """
    n = 0
    for e in cue_els:
        if e.get("type") not in _MINIMIZE_TEXTISH:
            continue
        rel = e.get("relative_positioning") or {}
        rel_to = rel.get("relative_to", "") if isinstance(rel, dict) else ""
        if scene_id_to_var.get(rel_to, rel_to) in diagram_vars:
            continue
        n += 1
    return n


def _maybe_minimize_diagram(lines, cue_els, scene_state, scene_id_to_var, cue_idx=1):
    """If this cue piles free-standing text onto an on-screen diagram (and the scene
    is not yet minimized), emit the minimize play and switch to right-column
    placement for the text. Returns True if the scene is in split-screen mode."""
    if scene_state.get("minimized"):
        return True
    diagram_vars = scene_state.get("diagram_vars") or []
    if not diagram_vars or cue_idx == 0:
        # Cue 0 usually *introduces* the diagram alongside its title — nothing to move aside yet.
        return False
    n_new = _minimize_triggers(cue_els, scene_id_to_var, diagram_vars)
    has_math = any(e.get("type") in ("math", "math_evolution") for e in cue_els)
    # Any math is worth splitting for (derivations are tall); plain prose only once a
    # cue brings more than a single caption-sized line.
    if has_math or n_new >= 2:
        # Group (not VGroup) whenever an ImageMobject may be among the diagram
        # vars — VGroup raises TypeError on non-VMobjects. VGroup is kept for
        # the pure-vector case (the long-proven path).
        group_cls = "Group" if scene_state.get("has_image_diagram") else "VGroup"
        group = f"{group_cls}({', '.join(diagram_vars)})"
        lines.append("            # diagram done — minimize to the left, derivation on the right")
        lines.append(_MINIMIZE_PLAY.format(group=group))
        scene_state["minimized"] = True
        return True
    return False


def _right_column_eligible(el, scene_id_to_var, scene_state):
    """Once split-screen, free-standing text-ish elements move to the right column.
    Diagram-anchored labels stay put — they ride along with the shrunken diagram."""
    if el.get("type") not in _MINIMIZE_TEXTISH:
        return False
    rel = el.get("relative_positioning") or {}
    rel_to = rel.get("relative_to", "") if isinstance(rel, dict) else ""
    return scene_id_to_var.get(rel_to, rel_to) not in (scene_state.get("diagram_vars") or [])


def _right_column_place(el, scene_state):
    """Place a math element in the right-half column (used once minimized)."""
    y = scene_state.setdefault("right_col_y", 2.2)
    el.pop("safe_zone_alignment", None)
    el.pop("relative_positioning", None)
    el.pop("position", None)
    el.pop("_c2p_axes", None)
    el["absolute_position"] = [3.6, y]
    scene_state["right_col_y"] = y - 0.9


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_schema_to_base_scene(
    storyboard,
    language="hi-IN",
    speaker="shubh",
    persona="hybrid",
    background="default",
    tts_provider="sarvam",
    asset_warnings=None,
    style="",
):
    """
    Convert a StoryboardResponse dict/JSON into a complete, renderable
    Manim CE + manim_voiceover script.

    Features:
    - Calm rise-and-fade entrances (shift=UP, ease_out_cubic — elastic pop retired)
    - run_time=tracker.duration * 0.6 syncs animations to voiceover
    - AnimationGroup with lag_ratio=0.15 staggers multi-element reveals
    - Scene-start canvas clear (FadeOut all) before every scene after the first
    - Same-zone collision detection with automatic fallback zone assignment
    - Topological sort of elements by relative_positioning dependencies
    - Asset fallback: failed SVG/molecule → Text primitive
    """
    if isinstance(storyboard, str):
        try:
            storyboard = json.loads(storyboard)
        except Exception:
            match = re.search(r"(\{.*\})", storyboard, re.DOTALL)
            if match:
                storyboard = json.loads(match.group(1))
            else:
                raise ValueError("Invalid storyboard JSON")

    failed_assets = {w["element_id"] for w in (asset_warnings or [])}

    # Resolve the visual theme once (canvas background, accent, shape palette).
    theme = resolve_theme(style or storyboard.get("style_profile", ""), background)
    _accent = theme.accent if theme else "YELLOW"
    _font = theme.body_font if theme else "Montserrat"

    # Pre-build ID→var for cross-scene event ID rewriting.
    #
    # The master script shares ONE construct() namespace, so an event pointing at
    # an earlier scene's mobject is legitimate (a cross-scene FadeOut is how the
    # canvas gets cleared). Pointing at a LATER scene's is not: Python executes
    # top-to-bottom, so the name does not exist yet and the render dies with a
    # NameError. That happened whenever two scenes reused an element id — this
    # map was global and last-writer-wins, so scene 2's `basketball_start` event
    # resolved to `mobj_scene3_basketball_start` (2026-08-15; ids repeat across
    # scenes far more often now that each screen is written by its own LLM call,
    # which only makes ids unique WITHIN a scene).
    #
    # So the map is resolved per scene against what is already DEFINED: the
    # nearest declaration at or before the current scene.
    _defs_by_scene = []          # [(scene_index, {id: var}), ...] in emission order
    for scene in storyboard.get("visual_storyboard", []):
        sidx = scene.get("scene_index", 1)
        _defs_by_scene.append((sidx, {
            el["id"]: f"mobj_scene{sidx}_{el['id']}"
            for el in scene.get("elements", []) if el.get("id")
        }))

    def _visible_id_to_var(upto_scene_idx):
        """ID→var for everything declared at or before `upto_scene_idx`."""
        visible = {}
        for sidx, defs in _defs_by_scene:
            if sidx > upto_scene_idx:
                break
            visible.update(defs)     # a later-but-still-defined scene wins
        return visible

    all_id_to_var = _visible_id_to_var(10 ** 6)
    # Every element id in the whole storyboard; one not yet visible at the current
    # scene is a forward reference — see _drop_foreign_id_calls.
    _story_ids = set(all_id_to_var)
    _image_el_ids = _collect_image_ids(storyboard)

    lines = [
        "from manim import *",
        "from manim_voiceover import VoiceoverScene",
        "from manim.utils.rate_functions import *",
        "from viz_helpers import *",
        f'config.font = "{_font}"',
        "",
        "class STEMAnimation(VoiceoverScene):",
        "    def construct(self):",
    ]

    if persona == "en":
        lines.append(
            f'        self.set_speech_service(UniversalTTSService('
            f'language="en-IN", speaker="{speaker}", provider="{tts_provider}"))'
        )
    else:
        lines.append(
            f'        self.set_speech_service(UniversalTTSService('
            f'language="{language}", speaker="{speaker}", provider="{tts_provider}"))'
        )

    if background and background != "default":
        lines.append(f'        set_realistic_background(self, "{background}", dim=0.5)')
    elif theme and not theme.is_light and theme.background:
        # Dark themed canvas instead of Manim's pure black. Only for dark themes:
        # a light canvas is reached solely via white_canvas (which handles text
        # recolour); painting light here would hide the default white text.
        lines.append(f'        self.camera.background_color = "{theme.background}"')
    lines.append("")

    for scene in storyboard.get("visual_storyboard", []):
        scene_idx = scene.get("scene_index", 1)
        desc            = scene.get("description", "")
        elements        = scene.get("elements", [])
        composition     = scene.get("composition") or ""
        layout_template = scene.get("layout_template")
        cues            = scene.get("narration_cues", []) or [{"cue": "...", "event": ""}]
        wait_time       = scene.get("wait_time", 2.0)

        if composition:
            logger.info("[COMPOSITION] scene %d: %s", scene_idx, composition)
        elif layout_template:
            logger.info("[COMPOSITION] scene %d: layout template '%s' (no composition descriptor)", scene_idx, layout_template)

        if layout_template:
            _apply_template_zones(elements, layout_template)

        lines.append(f"        # ── Scene {scene_idx}: {desc}")

        # ── Canvas clear between scenes ──────────────────────────────────────
        if scene_idx > 1:
            lines.append(f"        _s{scene_idx}_bg = _bg_image(self)")
            lines.append(f"        _s{scene_idx}_ex = [m for m in self.mobjects if m is not _s{scene_idx}_bg]")
            lines.append(f"        if _s{scene_idx}_ex: self.play(FadeOut(*_s{scene_idx}_ex), run_time=0.5)")
            lines.append("")

        # Scene-local ID → var
        scene_id_to_var = {
            el.get("id", ""): f"mobj_scene{scene_idx}_{el.get('id', '')}"
            for el in elements if el.get("id")
        }
        # Cross-scene references may only reach BACKWARDS (see _visible_id_to_var).
        # This scene's own declarations always win over an earlier namesake.
        all_id_to_var = {**_visible_id_to_var(scene_idx), **scene_id_to_var}

        # Per-scene zone tracker for collision detection
        used_zones = {}
        # Per-scene palette cursor: uncoloured shapes cycle the theme palette so
        # every scene opens on the same colour (deterministic, not accumulating).
        palette_state = {"i": 0}
        # Data-space coords (c2p), diagram tracking for minimize-to-side
        axes_ctx = _scene_axes_ctx(elements, scene_id_to_var)
        _seed_axes_zones(used_zones, elements)
        _fix_label_slots(elements, axes_ctx)
        # Structure decides geometry: nodes joined by `connects` are positioned by
        # the graph, overriding whatever coordinates the model guessed.
        _apply_graph_layout(elements)
        # Slot indices must be scene-wide: siblings of one container may enter on
        # different cues, and each still needs its own cell.
        _mark_containment(elements)
        scene_state = {"diagram_vars": [], "minimized": False}
        scene_vars = []   # every var created in this scene, in creation order
        axes_emitted = False

        # Map elements to cues.
        # Structured path: element belongs to cue i if animation_events has a 'show' action for it.
        # Legacy path: element ID appears anywhere in the event string.
        # Falls through to unmapped (→ cue 0) when neither matches.
        cue_to_els = {i: [] for i in range(len(cues))}
        unmapped   = []
        for el in elements:
            eid    = el.get("id", "")
            placed = False
            for i, cue in enumerate(cues):
                anim_events = cue.get("animation_events") or []
                if anim_events:
                    if any(ae.get("action") == "show" and ae.get("target") == eid
                           for ae in anim_events):
                        cue_to_els[i].append(el)
                        placed = True
                        break
                elif eid and re.search(rf"\b{re.escape(eid)}\b", cue.get("event", "")):
                    cue_to_els[i].append(el)
                    placed = True
                    break
            if not placed:
                unmapped.append(el)
        cue_to_els[0].extend(unmapped)

        # Topological sort within each cue
        for i in range(len(cues)):
            cue_to_els[i] = _topo_sort_elements(cue_to_els[i])

        for i, cue in enumerate(cues):
            cue_text  = cue.get("cue", "").strip()
            event_str = cue.get("event", "").strip()
            clean_cue = cue_text.replace("\\", "\\\\").replace('"', '\\"')

            lines.append(f'        with self.voiceover(text="{clean_cue}") as tracker:')

            cue_els      = cue_to_els[i]
            entered_vars = []

            # Screen management: shrink an on-screen diagram aside before a derivation
            _maybe_minimize_diagram(lines, cue_els, scene_state, scene_id_to_var, i)
            # Axes first within its cue so points in the same cue can c2p to it
            cue_els.sort(key=lambda e: 0 if e.get("type") in ("coordinate_system", "graph") else 1)

            # 1. Instantiate all new elements for this cue
            evolution_pairs = []  # (from_var, to_latex_str) for math_evolution
            for el in cue_els:
                eid      = el.get("id", "")
                var_name = scene_id_to_var.get(eid, f"mobj_scene{scene_idx}_{eid}")
                _hero_image_place(el, scene_state, elements)
                if scene_state["minimized"] and _right_column_eligible(el, scene_id_to_var, scene_state):
                    _right_column_place(el, scene_state)
                else:
                    _mark_c2p(el, axes_ctx, axes_emitted)
                _dcolor = (shape_default_color(theme, palette_state)
                           if el.get("type") == "shape" and not el.get("color") else None)
                obj_expr = _build_obj_expr(el, scene_idx, scene_id_to_var, failed_assets,
                                           used_zones, default_color=_dcolor, theme=theme)
                lines.append(f"            {var_name} = {obj_expr}")
                entered_vars.append((el, var_name))
                _etype = el.get("type", "text")
                if _etype in ("coordinate_system", "graph"):
                    axes_emitted = True
                _rel = el.get("relative_positioning") or {}
                _rel_to = _rel.get("relative_to", "") if isinstance(_rel, dict) else ""
                if (_etype in ("coordinate_system", "graph", "shape", "image", "simulation")
                        or scene_id_to_var.get(_rel_to, _rel_to) in scene_state["diagram_vars"]):
                    scene_state["diagram_vars"].append(var_name)
                    if _etype == "image":
                        # Non-VMobject in the diagram set — split-screen must
                        # use Group, not VGroup (see _maybe_minimize_diagram).
                        scene_state["has_image_diagram"] = True
                if el.get("_evolution_to"):
                    to_var = f"{var_name}_to"
                    to_latex = el["_evolution_to"]
                    lines.append(
                        f'            {to_var} = MathTex(r"{to_latex}", substrings_to_isolate=list(r"{to_latex}")).move_to({var_name})'
                    )
                    evolution_pairs.append((var_name, to_var))

            # 2. Play entrance animations, content-aware run_time (see _TIMING)
            if entered_vars:
                anim_calls = [
                    _build_entrance_call(
                        el.get("_render_as") or el.get("type", "text"),
                        el.get("entrance_animation", ""),
                        var_name,
                        content=el.get("content", ""),
                        obj_expr=el.get("_obj_expr", ""),
                    )
                    for el, var_name in entered_vars
                ]
                _rt = _run_time_expr([el.get("type", "text") for el, _ in entered_vars])
                if len(anim_calls) == 1:
                    lines.append(
                        f"            self.play({anim_calls[0]}, run_time={_rt})"
                    )
                else:
                    inner = ", ".join(anim_calls)
                    lines.append(
                        f"            self.play(AnimationGroup({inner}, lag_ratio=0.15), "
                        f"run_time={_rt})"
                    )

            # 2a-sim. Run any simulation that just entered, during its own beat.
            # A simulation whose animation never plays is a static picture of a moving
            # thing — the exact defect the element type exists to remove.
            for _el, _var in entered_vars:
                if _el.get("_is_simulation"):
                    lines.append(_sim_play_line("            ", _var))

            # 2b. TransformMatchingTex for math_evolution elements
            for from_var, to_var in evolution_pairs:
                lines.append(
                    f"            self.play(TransformMatchingTex({from_var}, {to_var}), "
                    f"run_time=tracker.duration * 0.4)"
                )
                # Rebind so future FadeOut references target the final form
                lines.append(f"            {from_var} = {to_var}")

            # 3. Event-driven animations (exits, transforms, emphasis)
            # A target that only exists in a LATER scene is a forward reference —
            # the name is not bound yet, and the `.get(id, id)` fallbacks below
            # would emit it raw and NameError the whole script.
            anim_events = _drop_cross_scene_events(
                cue.get("animation_events"), all_id_to_var, scene_idx)
            _body_mark = len(lines)
            if anim_events:
                # ── Structured path ───────────────────────────────────────────
                # Batch all FadeOuts together; each other action fires in sequence.
                hides = [ae for ae in anim_events if ae.get("action") == "hide"]
                if hides:
                    fade_args = ", ".join(
                        f"FadeOut({all_id_to_var.get(ae['target'], ae['target'])})"
                        for ae in hides
                    )
                    lines.append(f"            self.play({fade_args}, run_time=0.4)")

                for ae in anim_events:
                    action = ae.get("action", "")
                    t_id   = ae.get("target", "")
                    t_var  = all_id_to_var.get(t_id, t_id)
                    if action in ("show", "hide"):
                        continue  # show → entrance handled in step 1; hide batched above
                    elif action == "transform":
                        to_id  = ae.get("to", "")
                        to_var = all_id_to_var.get(to_id, to_id)
                        from_el = next((e for e in elements if e.get("id") == t_id), {})
                        to_el   = next((e for e in elements if e.get("id") == to_id), {})
                        if from_el.get("type") == "math" and to_el.get("type") == "math":
                            lines.append(
                                f"            self.play(TransformMatchingTex({t_var}, {to_var}), run_time=0.6)"
                            )
                        else:
                            lines.append(
                                f"            self.play(ReplacementTransform({t_var}, {to_var}), run_time=0.6)"
                            )
                    elif action == "highlight":
                        # Colourless pulse. `Indicate` recoloured its target to a flat
                        # accent — on a themed frame that reads as the object changing
                        # meaning, and on a raster photo it painted the whole bitmap
                        # (which is why images needed a Circumscribe special case).
                        # Removed 2026-08-15 on user review; `emphasize` is round-trip
                        # and type-agnostic, so both branches collapse into one.
                        lines.append(
                            f"            self.play(emphasize({t_var}), run_time=0.5)"
                        )
                    elif action == "move_to":
                        to_id  = ae.get("to", "")
                        to_var = all_id_to_var.get(to_id, to_id)
                        dirn   = ae.get("direction") or "RIGHT"
                        lines.append(
                            f"            self.play({t_var}.animate.next_to({to_var}, {dirn}, buff=0.3), run_time=0.4)"
                        )
                    elif action == "focus":
                        # Semantic spotlight: dim everything else, then restore. Opacity
                        # only — never camera geometry, which would invalidate the
                        # probe's fixed-frame clipping check (viz_helpers.spotlight_on).
                        lines.append(f"            spotlight_on(self, {t_var})")
                        lines.append(f"            self.wait(0.3)")
                        lines.append(f"            spotlight_off(self)")
            elif event_str:
                # ── Legacy path: free-text comma-separated animation calls ─────
                event_calls  = _split_anim_calls(event_str)
                non_entrance = []
                for call in event_calls:
                    call_name = call.strip().split("(")[0].strip()
                    if call_name not in _ENTRANCE_ANIMS:
                        non_entrance.append(_rewrite_ids(call, all_id_to_var))
                non_entrance = _sanitize_anim_calls(non_entrance, f" (scene {scene_idx})")
                non_entrance = _drop_foreign_id_calls(
                    non_entrance, _story_ids - set(all_id_to_var), scene_idx)
                if non_entrance:
                    lines.append(
                        f"            self.play({', '.join(non_entrance)}, run_time=0.4)"
                    )

            # 4. Sustained motion for the rest of the beat (see viz_helpers.sustain).
            lines.append(_sustain_call(entered_vars, scene_vars, _accent))
            scene_vars.extend(v for _, v in entered_vars)

            # Guard on what was actually emitted, not on the raw event string:
            # a cue whose every event fragment was dropped as prose still needs
            # a body, or the voiceover block is an IndentationError.
            if not entered_vars and len(lines) == _body_mark:
                lines.append("            pass")

        lines.append(f"        self.wait({wait_time})")
        lines.append("")

    # ── Post-render frame-bounds check ─────────────────────────────────────────
    # Runs after the last wait(); logs a [BBOX_WARNING] to stderr for any mobject
    # whose bounding box extends outside the 16:9 frame (x ∈ [-fw/2, fw/2]).
    lines.append("        # [BBOX_CHECK] flag out-of-frame mobjects")
    lines.append("        _fw2 = config.frame_width / 2")
    lines.append("        _fh2 = config.frame_height / 2")
    lines.append("        import sys as _sys")
    lines.append("        for _m in self.mobjects:")
    lines.append("            try:")
    lines.append("                _bb = _m.get_bounding_box()")
    lines.append("                _x0, _x1 = _bb[0][0], _bb[2][0]")
    lines.append("                _y0, _y1 = _bb[0][1], _bb[2][1]")
    lines.append("                if _x0 < -_fw2 or _x1 > _fw2 or _y0 < -_fh2 or _y1 > _fh2:")
    lines.append("                    _msg = f'[BBOX_WARNING] {type(_m).__name__} outside frame:"
                 " x=[{_x0:.2f},{_x1:.2f}] y=[{_y0:.2f},{_y1:.2f}]'")
    lines.append("                    print(_msg, flush=True, file=_sys.stderr)")
    lines.append("            except Exception:")
    lines.append("                pass")
    lines.append("")

    return "\n".join(lines)


def _drop_cross_scene_events(anim_events, id_to_var, scene_idx):
    """Keep only the animation events whose targets exist in THIS scene.

    Per-scene scripts render in isolation, each starting from a blank canvas, so a cue
    that targets an element defined in an earlier scene — overwhelmingly "fade out the
    previous scene's props" — has nothing to act on. Worse, the `.get(id, id)` lookups
    below fall back to the raw storyboard id, emitting `FadeOut(container)` as code:
    a NameError at render time that kills the scene and drags the whole video back to
    the sequential path. Measured 2026-07-20 on the Dalton's-law storyboard: 3 of 4
    scenes died exactly this way, so the parallel path (and with it scene-scoped
    repair) never actually ran in production.
    """
    kept, dropped = [], []
    for ae in anim_events or []:
        ok = ae.get("target") in id_to_var
        if ok and ae.get("action") in ("transform", "move_to"):
            ok = ae.get("to") in id_to_var
        (kept if ok else dropped).append(ae)
    if dropped:
        names = [f"{d.get('action')}:{d.get('target')}" for d in dropped]
        print(f"[TRANSPILER] scene {scene_idx}: dropped {len(dropped)} cross-scene "
              f"animation event(s) {names} — target not defined in this scene.",
              file=sys.stderr)
    return kept


def _drop_foreign_id_calls(calls, foreign_ids, scene_idx):
    """Drop legacy free-text `event` fragments that reference another scene's element.

    Companion to _drop_cross_scene_events for the legacy path: `_rewrite_ids` leaves an
    unmapped id untouched and `_sanitize_anim_calls` only validates call *shape*, so
    `FadeOut(container)` sails through both and NameErrors at render time.
    """
    if not foreign_ids:
        return calls
    kept, dropped = [], []
    for call in calls:
        try:
            names = {n.id for n in ast.walk(ast.parse(call, mode="eval"))
                     if isinstance(n, ast.Name)}
        except SyntaxError:
            names = set()
        (dropped if names & foreign_ids else kept).append(call)
    if dropped:
        print(f"[TRANSPILER] scene {scene_idx}: dropped {len(dropped)} legacy event "
              f"fragment(s) referencing another scene's elements: {dropped}",
              file=sys.stderr)
    return kept


def parse_schema_to_scene_scripts(
    storyboard,
    language="hi-IN",
    speaker="shubh",
    persona="hybrid",
    background="default",
    tts_provider="sarvam",
    asset_warnings=None,
    style="",
):
    """
    Returns one complete standalone Manim script per scene (for parallel rendering).
    Each script is self-contained: same header, own class/construct, NO canvas clear.
    Returns [] when the storyboard has ≤1 scene (no benefit from parallelising).
    """
    if isinstance(storyboard, str):
        try:
            storyboard = json.loads(storyboard)
        except Exception:
            match = re.search(r"(\{.*\})", storyboard, re.DOTALL)
            if match:
                storyboard = json.loads(match.group(1))
            else:
                raise ValueError("Invalid storyboard JSON")

    failed_assets = {w["element_id"] for w in (asset_warnings or [])}

    # Resolve the visual theme once — must match parse_schema_to_base_scene so the
    # parallel per-scene render and the single-script render look identical.
    theme = resolve_theme(style or storyboard.get("style_profile", ""), background)
    _accent = theme.accent if theme else "YELLOW"
    _font = theme.body_font if theme else "Montserrat"

    scenes = storyboard.get("visual_storyboard", [])
    if len(scenes) <= 1:
        return []
    _image_el_ids = _collect_image_ids(storyboard)

    # Every element id in the whole storyboard. An id in here but NOT in the scene
    # currently being emitted is a cross-scene reference — see _drop_cross_scene_events.
    _story_ids = {
        el.get("id") for sc in scenes for el in (sc.get("elements") or []) if el.get("id")
    }

    scripts = []
    for scene in scenes:
        scene_idx = scene.get("scene_index", 1)
        desc = scene.get("description", "")
        elements = scene.get("elements", [])
        composition = scene.get("composition") or ""
        layout_template = scene.get("layout_template")
        cues = scene.get("narration_cues", []) or [{"cue": "...", "event": ""}]
        wait_time = scene.get("wait_time", 2.0)

        if composition:
            logger.info("[COMPOSITION] scene %d: %s", scene_idx, composition)
        elif layout_template:
            logger.info("[COMPOSITION] scene %d: layout template '%s' (no composition descriptor)", scene_idx, layout_template)

        if layout_template:
            _apply_template_zones(elements, layout_template)

        # Per-scene id→var (only this scene's elements)
        scene_id_to_var = {
            el.get("id", ""): f"mobj_scene{scene_idx}_{el.get('id', '')}"
            for el in elements if el.get("id")
        }
        all_id_to_var = dict(scene_id_to_var)  # same scope for per-scene scripts
        _foreign_ids = _story_ids - set(all_id_to_var)

        lines = [
            "from manim import *",
            "from manim_voiceover import VoiceoverScene",
            "from manim.utils.rate_functions import *",
            "from viz_helpers import *",
            f'config.font = "{_font}"',
            "",
            "class STEMAnimation(VoiceoverScene):",
            "    def construct(self):",
        ]

        if persona == "en":
            lines.append(
                f'        self.set_speech_service(UniversalTTSService('
                f'language="en-IN", speaker="{speaker}", provider="{tts_provider}"))'
            )
        else:
            lines.append(
                f'        self.set_speech_service(UniversalTTSService('
                f'language="{language}", speaker="{speaker}", provider="{tts_provider}"))'
            )

        if background and background != "default":
            lines.append(f'        set_realistic_background(self, "{background}", dim=0.5)')
        elif theme and not theme.is_light and theme.background:
            # Same dark themed canvas as the single-script path so concatenated
            # per-scene clips share one background (see parse_schema_to_base_scene).
            lines.append(f'        self.camera.background_color = "{theme.background}"')
        lines.append("")
        lines.append(f"        # ── Scene {scene_idx}: {desc}")

        used_zones = {}
        palette_state = {"i": 0}
        axes_ctx = _scene_axes_ctx(elements, scene_id_to_var)
        _seed_axes_zones(used_zones, elements)
        _fix_label_slots(elements, axes_ctx)
        # Structure decides geometry: nodes joined by `connects` are positioned by
        # the graph, overriding whatever coordinates the model guessed.
        _apply_graph_layout(elements)
        # Slot indices must be scene-wide: siblings of one container may enter on
        # different cues, and each still needs its own cell.
        _mark_containment(elements)
        scene_state = {"diagram_vars": [], "minimized": False}
        scene_vars = []   # every var created in this scene, in creation order
        axes_emitted = False

        # Map elements to cues (same logic as parse_schema_to_base_scene)
        cue_to_els = {i: [] for i in range(len(cues))}
        unmapped = []
        for el in elements:
            eid = el.get("id", "")
            placed = False
            for i, cue in enumerate(cues):
                anim_events = cue.get("animation_events") or []
                if anim_events:
                    if any(ae.get("action") == "show" and ae.get("target") == eid
                           for ae in anim_events):
                        cue_to_els[i].append(el)
                        placed = True
                        break
                elif eid and re.search(rf"\b{re.escape(eid)}\b", cue.get("event", "")):
                    cue_to_els[i].append(el)
                    placed = True
                    break
            if not placed:
                unmapped.append(el)
        cue_to_els[0].extend(unmapped)

        for i in range(len(cues)):
            cue_to_els[i] = _topo_sort_elements(cue_to_els[i])

        for i, cue in enumerate(cues):
            cue_text = cue.get("cue", "").strip()
            event_str = cue.get("event", "").strip()
            clean_cue = cue_text.replace("\\", "\\\\").replace('"', '\\"')

            lines.append(f'        with self.voiceover(text="{clean_cue}") as tracker:')

            cue_els = cue_to_els[i]
            entered_vars = []
            evolution_pairs = []

            _maybe_minimize_diagram(lines, cue_els, scene_state, scene_id_to_var, i)
            cue_els.sort(key=lambda e: 0 if e.get("type") in ("coordinate_system", "graph") else 1)

            for el in cue_els:
                eid = el.get("id", "")
                var_name = scene_id_to_var.get(eid, f"mobj_scene{scene_idx}_{eid}")
                _hero_image_place(el, scene_state, elements)
                if scene_state["minimized"] and _right_column_eligible(el, scene_id_to_var, scene_state):
                    _right_column_place(el, scene_state)
                else:
                    _mark_c2p(el, axes_ctx, axes_emitted)
                _dcolor = (shape_default_color(theme, palette_state)
                           if el.get("type") == "shape" and not el.get("color") else None)
                obj_expr = _build_obj_expr(el, scene_idx, scene_id_to_var, failed_assets,
                                           used_zones, default_color=_dcolor, theme=theme)
                lines.append(f"            {var_name} = {obj_expr}")
                entered_vars.append((el, var_name))
                _etype = el.get("type", "text")
                if _etype in ("coordinate_system", "graph"):
                    axes_emitted = True
                _rel = el.get("relative_positioning") or {}
                _rel_to = _rel.get("relative_to", "") if isinstance(_rel, dict) else ""
                if (_etype in ("coordinate_system", "graph", "shape", "image", "simulation")
                        or scene_id_to_var.get(_rel_to, _rel_to) in scene_state["diagram_vars"]):
                    scene_state["diagram_vars"].append(var_name)
                    if _etype == "image":
                        # Non-VMobject in the diagram set — split-screen must
                        # use Group, not VGroup (see _maybe_minimize_diagram).
                        scene_state["has_image_diagram"] = True
                if el.get("_evolution_to"):
                    to_var = f"{var_name}_to"
                    to_latex = el["_evolution_to"]
                    lines.append(
                        f'            {to_var} = MathTex(r"{to_latex}", '
                        f'substrings_to_isolate=list(r"{to_latex}")).move_to({var_name})'
                    )
                    evolution_pairs.append((var_name, to_var))

            if entered_vars:
                anim_calls = [
                    _build_entrance_call(el.get("_render_as") or el.get("type", "text"),
                                         el.get("entrance_animation", ""), vn,
                                         content=el.get("content", ""),
                                         obj_expr=el.get("_obj_expr", ""))
                    for el, vn in entered_vars
                ]
                _rt = _run_time_expr([el.get("type", "text") for el, _ in entered_vars])
                if len(anim_calls) == 1:
                    lines.append(
                        f"            self.play({anim_calls[0]}, run_time={_rt})"
                    )
                else:
                    inner = ", ".join(anim_calls)
                    lines.append(
                        f"            self.play(AnimationGroup({inner}, lag_ratio=0.15), "
                        f"run_time={_rt})"
                    )

            # Run any simulation that just entered (see the master path's 2a-sim).
            for _el, _var in entered_vars:
                if _el.get("_is_simulation"):
                    lines.append(_sim_play_line("            ", _var))

            for from_var, to_var in evolution_pairs:
                lines.append(
                    f"            self.play(TransformMatchingTex({from_var}, {to_var}), "
                    f"run_time=tracker.duration * 0.4)"
                )
                lines.append(f"            {from_var} = {to_var}")

            anim_events = _drop_cross_scene_events(
                cue.get("animation_events"), all_id_to_var, scene_idx)
            _body_mark = len(lines)
            if anim_events:
                hides = [ae for ae in anim_events if ae.get("action") == "hide"]
                if hides:
                    fade_args = ", ".join(
                        f"FadeOut({all_id_to_var.get(ae['target'], ae['target'])})"
                        for ae in hides
                    )
                    lines.append(f"            self.play({fade_args}, run_time=0.4)")
                for ae in anim_events:
                    action = ae.get("action", "")
                    t_id = ae.get("target", "")
                    t_var = all_id_to_var.get(t_id, t_id)
                    if action in ("show", "hide"):
                        continue
                    elif action == "transform":
                        to_id = ae.get("to", "")
                        to_var = all_id_to_var.get(to_id, to_id)
                        from_el = next((e for e in elements if e.get("id") == t_id), {})
                        to_el = next((e for e in elements if e.get("id") == to_id), {})
                        if from_el.get("type") == "math" and to_el.get("type") == "math":
                            lines.append(
                                f"            self.play(TransformMatchingTex({t_var}, {to_var}), run_time=0.6)"
                            )
                        else:
                            lines.append(
                                f"            self.play(ReplacementTransform({t_var}, {to_var}), run_time=0.6)"
                            )
                    elif action == "highlight":
                        # Colourless pulse — must stay identical to the master path's
                        # highlight, or the two codegen paths disagree on emphasis.
                        lines.append(
                            f"            self.play(emphasize({t_var}), run_time=0.5)"
                        )
                    elif action == "move_to":
                        to_id = ae.get("to", "")
                        to_var = all_id_to_var.get(to_id, to_id)
                        dirn = ae.get("direction") or "RIGHT"
                        lines.append(
                            f"            self.play({t_var}.animate.next_to({to_var}, {dirn}, buff=0.3), run_time=0.4)"
                        )
                    elif action == "focus":
                        # Same emission as the master path — both codegen paths must agree.
                        lines.append(f"            spotlight_on(self, {t_var})")
                        lines.append(f"            self.wait(0.3)")
                        lines.append(f"            spotlight_off(self)")
            elif event_str:
                event_calls = _split_anim_calls(event_str)
                non_entrance = []
                for call in event_calls:
                    if call.strip().split("(")[0].strip() not in _ENTRANCE_ANIMS:
                        non_entrance.append(_rewrite_ids(call, all_id_to_var))
                non_entrance = _sanitize_anim_calls(non_entrance, f" (scene {scene_idx})")
                non_entrance = _drop_foreign_id_calls(non_entrance, _foreign_ids, scene_idx)
                if non_entrance:
                    lines.append(
                        f"            self.play({', '.join(non_entrance)}, run_time=0.4)"
                    )

            # 4. Sustained motion for the rest of the beat (see viz_helpers.sustain).
            lines.append(_sustain_call(entered_vars, scene_vars, _accent))
            scene_vars.extend(v for _, v in entered_vars)

            # Guard on what was actually emitted, not on the raw event string:
            # a cue whose every event fragment was dropped as prose still needs
            # a body, or the voiceover block is an IndentationError.
            if not entered_vars and len(lines) == _body_mark:
                lines.append("            pass")

        lines.append(f"        self.wait({wait_time})")
        lines.append("")

        # BBOX check (same as main transpiler)
        lines.append("        # [BBOX_CHECK] flag out-of-frame mobjects")
        lines.append("        _fw2 = config.frame_width / 2")
        lines.append("        _fh2 = config.frame_height / 2")
        lines.append("        import sys as _sys")
        lines.append("        for _m in self.mobjects:")
        lines.append("            try:")
        lines.append("                _bb = _m.get_bounding_box()")
        lines.append("                _x0, _x1 = _bb[0][0], _bb[2][0]")
        lines.append("                _y0, _y1 = _bb[0][1], _bb[2][1]")
        lines.append("                if _x0 < -_fw2 or _x1 > _fw2 or _y0 < -_fh2 or _y1 > _fh2:")
        lines.append("                    _msg = f'[BBOX_WARNING] {type(_m).__name__} outside frame:"
                     " x=[{_x0:.2f},{_x1:.2f}] y=[{_y0:.2f},{_y1:.2f}]'")
        lines.append("                    print(_msg, flush=True, file=_sys.stderr)")
        lines.append("            except Exception:")
        lines.append("                pass")
        lines.append("")

        scripts.append("\n".join(lines))

    return scripts
