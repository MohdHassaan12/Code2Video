"""Central visual theme / palette resolution for the deterministic transpiler.

House rule "Code owns structure, models own content": the UI has offered a
style-profile dropdown for a long time, but until now that choice only reached
the *LLM* codegen path as prose in a prompt. The deterministic transpiler — the
sole full-scene codegen path — ignored it entirely, so every video shipped on
Manim's default pure-black canvas with flat white shapes and a hard-coded YELLOW
emphasis colour, no matter which style the user picked.

This module maps a style-profile string (plus the already-resolved background)
to a concrete ``Theme``: the canvas background colour, an ``accent`` colour for
emphasis (``Indicate`` / highlight), and an ordered ``palette`` used to
auto-colour otherwise-uncoloured shapes so diagrams read as designed rather than
a wash of white strokes.

Consumed by ``transpiler.parse_schema_to_base_scene`` /
``parse_schema_to_scene_scripts``. **No manim import here** — this is pure data,
so the "no manim, no keys" test harnesses can load it standalone.

Design notes (the traps to keep in mind):
- ``background`` reaching the transpiler is already resolved (``determine_background``
  ran upstream). The transpiler only paints ``theme.background`` onto the canvas
  when ``background == "default"``; an image background or ``white_canvas`` owns
  the canvas itself via ``set_realistic_background``.
- ``theme.background`` is therefore applied **only for dark themes** (``is_light``
  False). A light canvas is reached exclusively through ``white_canvas``, where
  ``viz_helpers`` flips the ``IS_WHITE_BACKGROUND`` recolour path on. Painting a
  light ``camera.background_color`` directly would leave white text invisible, so
  we never do it.
- Every palette is chosen to be legible on that theme's own canvas: the light
  ``powerpoint`` theme uses dark saturated hexes, the dark themes use bright ones.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Theme:
    """A resolved visual theme. All colours are hex strings ("#RRGGBB")."""

    key: str
    # Canvas background — painted via camera.background_color, but ONLY when the
    # resolved background is "default" AND the theme is dark (see module docstring).
    background: str
    # True → a light canvas (reached only via white_canvas). Suppresses the dark
    # background paint and the dark-theme text/math default colouring.
    is_light: bool
    # Primary on-canvas text/heading colour (reserved for future title theming).
    text: str
    # Emphasis colour — replaces the hard-coded YELLOW default of Indicate/highlight.
    accent: str
    # Secondary accent (reserved for future title underlines / axis accents).
    accent2: str
    # config.font family. Kept at "Montserrat" for every theme in this revision so
    # the emitted line is byte-identical to the pre-theme output (a font-family
    # swap shifts text metrics and would need a fresh overlap-probe pass — a
    # separate, deliberate lever, not a side effect of theming colour).
    body_font: str
    # Default colour for uncoloured math (reserved; math stays white for now).
    math_color: str
    # Rotating colours applied to uncoloured *shapes* so diagrams are cohesive
    # rather than flat white. Legible on this theme's canvas.
    palette: tuple


# ---------------------------------------------------------------------------
# Theme table — keyed to the five style-profile options in the UI dropdown
# (stem_animation_lab/static/index.html #style-select).
# ---------------------------------------------------------------------------
_THREE_B_ONE_B = Theme(
    key="3blue1brown",
    background="#0E1116",          # near-black deep slate, not pure #000
    is_light=False,
    text="#ECEFF4",
    accent="#FFD24A",              # warm gold — the classic 3b1b highlight
    accent2="#58C4DD",             # 3b1b signature blue
    body_font="Montserrat",
    math_color="#FFFFFF",
    palette=("#58C4DD", "#FFD24A", "#83C167", "#FC6255", "#CF89E8", "#FF9F40"),
)

_CHALKBOARD = Theme(
    key="chalkboard",
    background="#14261C",           # deep board green (unused: style→chalkboard.jpg)
    is_light=False,
    text="#F3EFD8",                 # chalk cream
    accent="#FFE08A",
    accent2="#8FD9B6",
    body_font="Montserrat",
    math_color="#F3EFD8",
    palette=("#F6C6A8", "#A8D8C0", "#F5E1A4", "#C9B7E8", "#F4A7A7", "#9FD3E8"),
)

_CYBERPUNK = Theme(
    key="cyberpunk",
    background="#0B0221",           # deep violet-black (unused: style→space.jpg)
    is_light=False,
    text="#F5E9FF",
    accent="#FF5F1F",               # retrowave orange
    accent2="#FF2FB9",              # neon magenta
    body_font="Montserrat",
    math_color="#F5E9FF",
    palette=("#FF5F1F", "#FF2FB9", "#22D3EE", "#A855F7", "#FDE047", "#38BDF8"),
)

_MINIMALIST_MONO = Theme(
    key="minimalist-mono",
    background="#0A0A0A",           # near-black
    is_light=False,
    text="#FFFFFF",
    accent="#00E5FF",               # single restrained cyan accent
    accent2="#B8B8B8",
    body_font="Montserrat",
    math_color="#FFFFFF",
    palette=("#FFFFFF", "#00E5FF", "#C7C7C7", "#8A8A8A"),
)

_POWERPOINT = Theme(
    key="powerpoint",
    background="#FFFFFF",           # unused: powerpoint→white_canvas owns the canvas
    is_light=True,
    text="#1A1A1A",
    accent="#2563EB",               # corporate blue
    accent2="#DB2777",
    body_font="Montserrat",
    math_color="#111111",
    palette=("#2563EB", "#DC2626", "#059669", "#D97706", "#7C3AED", "#0891B2"),
)

# The same "clean corporate" identity, adapted to the canvas it will ACTUALLY land
# on. Reached when a light style is chosen with a non-white background — see
# resolve_theme. Without it, `powerpoint` + `default` background resolved to the
# light theme, the transpiler skipped painting (light themes never paint), and dark
# navy/maroon shapes were drawn on Manim's pure-black canvas: the exact "style
# profile and background are not matching" the user reported (2026-08-14).
_POWERPOINT_DARK = Theme(
    key="powerpoint",
    background="#12161C",
    is_light=False,
    text="#F2F4F8",
    accent="#5B9CFF",
    accent2="#FF7AB6",
    body_font="Montserrat",
    math_color="#FFFFFF",
    palette=("#5B9CFF", "#FF6B6B", "#37D399", "#FFB454", "#B98CFF", "#3FC7E0"),
)

DEFAULT_THEME = _THREE_B_ONE_B

THEMES = {
    "3blue1brown": _THREE_B_ONE_B,
    "chalkboard": _CHALKBOARD,
    "cyberpunk": _CYBERPUNK,
    "minimalist-mono": _MINIMALIST_MONO,
    "powerpoint": _POWERPOINT,
}


def _match_style(style):
    """Map a free-form style-profile string to a theme key by keyword.

    The UI values are slash-joined ("3blue1brown/minimalist/neon"); we match on
    the most specific keyword so future profile strings still route sensibly.
    """
    s = (style or "").lower()
    if "powerpoint" in s or "clean" in s:
        return "powerpoint"
    if "chalk" in s:
        return "chalkboard"
    if "cyberpunk" in s or "retrowave" in s:
        return "cyberpunk"
    if "3blue1brown" in s or "3b1b" in s or "neon" in s:
        return "3blue1brown"
    if "mono" in s or "minimalist" in s:
        return "minimalist-mono"
    return DEFAULT_THEME.key


def resolve_theme(style="", background="default"):
    """Return the :class:`Theme` for a style-profile string.

    A ``white_canvas`` background forces the light ``powerpoint`` theme
    regardless of style, because that is the only canvas where ``viz_helpers``
    turns on light-mode text recolouring — a dark-theme palette would be
    illegible there.
    """
    bg = (background or "").strip().lower()
    if bg == "white_canvas":
        return THEMES["powerpoint"]
    theme = THEMES.get(_match_style(style), DEFAULT_THEME)
    if theme.is_light:
        # A light theme on any canvas that is NOT white_canvas would paint nothing
        # (light themes never paint) and hand out dark-on-light colours for a
        # black/image canvas. Adapt instead of shipping the mismatch.
        return _POWERPOINT_DARK
    return theme


def shape_default_color(theme, palette_state):
    """Next palette colour for an uncoloured shape, advancing ``palette_state``.

    ``palette_state`` is a mutable ``{"i": int}`` owned by the caller (reset per
    scene so every scene starts from the same colour). Returns a hex string, or
    ``None`` when the theme has no palette.
    """
    if theme is None:
        return None
    pal = theme.palette
    if not pal:
        return None
    color = pal[palette_state.get("i", 0) % len(pal)]
    palette_state["i"] = palette_state.get("i", 0) + 1
    return color


# ---------------------------------------------------------------------------
# Colour harmonization — the style profile has to reach the CONTENT, not just
# the canvas.
#
# Why this exists (2026-08-14, user: "the style profile and the background are
# not matching and the gen content is stale"). Measured over the last six cached
# storyboards: **190 of 198 elements (96%) carry a model-authored colour**, and
# the palette only ever filled in for *uncoloured* shapes — so the style profile
# was decorating ~4% of the frame and changing it barely changed the video. Worse,
# what the model writes is raw RGB primaries: #FF00FF, #00FFCC, #FFFF00, #00FFFF,
# #FF0000 (30 distinct colours across 6 boards, mostly pure channels). That is why
# the output looks garish on a dark canvas and washed out on a light one — nobody
# picked those colours for this canvas, or for each other.
#
# The old rule was "model-authored colour is NEVER overridden". That protected the
# model's INTENT — "these two things must read as different" — and it is worth
# protecting. But a hex value is not intent; it is a guess made without knowing
# which canvas it lands on. So the rule becomes: **keep the model's colour when it
# works on this canvas and belongs to this design system; otherwise map it to the
# nearest palette colour by HUE**, which preserves distinctness (a "red" thing
# stays the warm one, a "blue" thing stays the cool one) while making the frame
# cohere. Contrast is checked with the WCAG relative-luminance formula.
# ---------------------------------------------------------------------------

# Manim's named colours, so a model that writes "YELLOW" is harmonized on the same
# footing as one that writes "#FFFF00". Values match manim.constants.
MANIM_COLOR_HEX = {
    "WHITE": "#FFFFFF", "BLACK": "#000000", "GRAY": "#888888", "GREY": "#888888",
    "LIGHT_GRAY": "#BBBBBB", "LIGHT_GREY": "#BBBBBB", "DARK_GRAY": "#444444",
    "DARK_GREY": "#444444", "BLUE": "#58C4DD", "DARK_BLUE": "#236B8E",
    "LIGHT_BLUE": "#7ED0E8", "TEAL": "#5CD0B3", "GREEN": "#83C167",
    "DARK_GREEN": "#4C8A3B", "YELLOW": "#FFF176", "GOLD": "#F0AC5F",
    "ORANGE": "#FF862F", "RED": "#FC6255", "DARK_RED": "#B33A32",
    "MAROON": "#C55F73", "PURPLE": "#9A72AC", "PINK": "#D147BD",
    "MAGENTA": "#FF00FF", "CYAN": "#00FFFF",
}

# Below this WCAG contrast ratio against the canvas, a colour is not readable as a
# graphic element. 3.0 is the WCAG AA bar for large text and UI graphics.
MIN_CONTRAST = 3.0


def _to_hex(color):
    """Normalize a model colour ('RED', '#ff0000', ' #FFF ') to '#RRGGBB', or None."""
    if not color:
        return None
    c = str(color).strip()
    if not c:
        return None
    named = MANIM_COLOR_HEX.get(c.upper())
    if named:
        return named
    if not c.startswith("#"):
        return None
    h = c[1:]
    if len(h) == 3:
        h = "".join(ch * 2 for ch in h)
    if len(h) != 6:
        return None
    try:
        int(h, 16)
    except ValueError:
        return None
    return "#" + h.upper()


def _rgb(hex_color):
    h = hex_color.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))


def relative_luminance(hex_color):
    """WCAG relative luminance of a hex colour (0.0 black … 1.0 white)."""
    def _lin(c):
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (_lin(c) for c in _rgb(hex_color))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(fg_hex, bg_hex):
    """WCAG contrast ratio between two hex colours (1.0 … 21.0)."""
    l1, l2 = relative_luminance(fg_hex), relative_luminance(bg_hex)
    lo, hi = sorted((l1, l2))
    return (hi + 0.05) / (lo + 0.05)


def _hue(hex_color):
    """Hue in degrees (0-360); -1 for a greyscale colour."""
    r, g, b = _rgb(hex_color)
    mx, mn = max(r, g, b), min(r, g, b)
    if mx - mn < 1e-6:
        return -1.0
    if mx == r:
        h = 60 * (((g - b) / (mx - mn)) % 6)
    elif mx == g:
        h = 60 * (((b - r) / (mx - mn)) + 2)
    else:
        h = 60 * (((r - g) / (mx - mn)) + 4)
    return h % 360


def _saturation(hex_color):
    r, g, b = _rgb(hex_color)
    mx, mn = max(r, g, b), min(r, g, b)
    return 0.0 if mx <= 0 else (mx - mn) / mx


def is_raw_primary(hex_color):
    """True for the 'nobody picked this' colours — pure channel values.

    #FF00FF, #00FF00, #FFFF00, #00FFFF: fully saturated with every channel pinned
    to 0 or 255. These dominate what the storyboard model emits and are the reason
    the output reads as garish rather than designed.
    """
    h = (hex_color or "").lstrip("#").upper()
    if len(h) != 6:
        return False
    channels = [h[0:2], h[2:4], h[4:6]]
    return all(c in ("00", "FF") for c in channels) and h not in ("FFFFFF", "000000")


def nearest_palette_color(hex_color, palette):
    """Palette entry closest in HUE to `hex_color` — keeps things distinguishable.

    Hue, not RGB distance: the model's point in colouring two shapes differently is
    that they READ differently, and hue is what carries that. Greyscale input maps
    to the first palette entry.
    """
    if not palette:
        return hex_color
    h = _hue(hex_color)
    if h < 0:
        return palette[0]
    def _dist(p):
        d = abs(_hue(p) - h)
        return min(d, 360 - d)
    return min(palette, key=_dist)


def harmonize(color, theme, kind="shape", background="default"):
    """Map a model-authored colour into `theme`, or return it unchanged.

    Returns a hex string (or None when there was no colour to begin with, so the
    caller's own default applies). Rules, in order:

    1. Unparseable colour → None (let the caller's default win).
    2. No theme → unchanged (themeless callers keep the old behaviour).
    3. Text and math on a canvas they can't be read on → the theme's `text` colour.
       "Drawn but unreadable is the same failure as dropped."
    4. A raw primary (#FF00FF …) → nearest palette colour by hue. These are never
       a deliberate design choice, and they are what the model actually emits.
    5. Too little contrast against the canvas → nearest palette colour by hue.
    6. Otherwise → unchanged. A model colour that is legible and looks picked is
       left exactly as it is; the model still owns *distinction*.
    """
    hex_color = _to_hex(color)
    if hex_color is None:
        return None
    if theme is None:
        return hex_color

    canvas = "#FFFFFF" if theme.is_light else theme.background
    # An image background is an unknown canvas — the theme's own is the best proxy
    # we have, and a colour legible on it is a safe bet either way.
    ratio = contrast_ratio(hex_color, canvas)

    if kind in ("text", "math", "math_evolution"):
        # Text carries meaning, not decoration: legibility beats palette fidelity,
        # and hue-snapping a heading would tint the whole frame.
        if ratio < MIN_CONTRAST:
            return theme.text
        return hex_color

    if is_raw_primary(hex_color) or ratio < MIN_CONTRAST:
        candidate = nearest_palette_color(hex_color, theme.palette)
        # Never trade one illegible colour for another.
        if contrast_ratio(candidate, canvas) >= MIN_CONTRAST:
            return candidate
        return theme.text if ratio < MIN_CONTRAST else hex_color
    return hex_color
