"""Visual theme / palette contract — no manim, no server, no keys.

Pins the theme system (theme.py) wired into the deterministic transpiler. The
style-profile the user picks in the UI used to be dead on the transpiler path —
every video shipped on Manim's pure-black canvas with flat-white shapes and a
hard-coded YELLOW emphasis colour. Now the profile drives a themed canvas
background, cycles a cohesive palette onto uncoloured shapes, and sets the
emphasis (Indicate) accent.

Contract asserted here:
- resolve_theme maps each of the five UI style profiles to its Theme; an unknown
  style falls back to the 3blue1brown default; a white_canvas background forces
  the light powerpoint theme regardless of style.
- Dark themes paint camera.background_color on a "default" background; a
  white_canvas / image background suppresses that paint (that canvas owns the
  background) — but palette + accent still apply.
- Uncoloured shapes cycle theme.palette; model-authored colour is NEVER
  overridden; the palette cursor resets per scene.
- highlight events emit the theme accent instead of YELLOW.
- style falls back to the storyboard's own style_profile when the arg is blank.
- Both codegen paths (base scene + per-scene scripts) agree and emit valid Python.

Run: .venv/bin/python stem_animation_lab/test_theme.py
"""
import ast
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lessonforge.theme import (  # noqa: E402
    Theme, THEMES, DEFAULT_THEME, resolve_theme, shape_default_color,
)
from lessonforge.transpiler import (  # noqa: E402
    parse_schema_to_base_scene,
    parse_schema_to_scene_scripts,
)

checks = []


def check(name, cond):
    checks.append((name, bool(cond)))
    print(("PASS " if cond else "FAIL ") + name)


def scene(elements, scene_index=1, cues=None):
    return {
        "scene_index": scene_index,
        "description": "test scene",
        "elements": elements,
        "narration_cues": cues or [{"cue": "test", "event": ""}],
        "wait_time": 1.0,
    }


def board(scenes, style_profile=None):
    b = {"visual_storyboard": scenes}
    if style_profile is not None:
        b["style_profile"] = style_profile
    return b


def base(storyboard, **kw):
    return parse_schema_to_base_scene(storyboard, persona="en", **kw)


def _valid(src):
    try:
        ast.parse(src)
        return True
    except SyntaxError:
        return False


# ── Part A: resolve_theme routing ──────────────────────────────────────────
check("3blue1brown/minimalist/neon → 3blue1brown theme",
      resolve_theme("3blue1brown/minimalist/neon").key == "3blue1brown")
check("chalkboard/chalk/pastel → chalkboard theme",
      resolve_theme("chalkboard/chalk/pastel").key == "chalkboard")
check("cyberpunk/retrowave/orange → cyberpunk theme",
      resolve_theme("cyberpunk/retrowave/orange").key == "cyberpunk")
check("minimalist/dark/mono → minimalist-mono theme",
      resolve_theme("minimalist/dark/mono").key == "minimalist-mono")
check("powerpoint/clean → powerpoint theme",
      resolve_theme("powerpoint/clean").key == "powerpoint")
check("unknown style falls back to the default (3blue1brown)",
      resolve_theme("no-such-style").key == DEFAULT_THEME.key)
check("empty style falls back to the default",
      resolve_theme("").key == DEFAULT_THEME.key)
check("white_canvas background forces the light powerpoint theme, any style",
      resolve_theme("cyberpunk/retrowave/orange", "white_canvas").key == "powerpoint")
check("only powerpoint is a light theme; the rest are dark",
      THEMES["powerpoint"].is_light
      and not any(t.is_light for k, t in THEMES.items() if k != "powerpoint"))

# shape_default_color cycles and resets
_ps = {"i": 0}
_seq = [shape_default_color(THEMES["3blue1brown"], _ps) for _ in range(8)]
_pal = THEMES["3blue1brown"].palette
check("shape_default_color cycles the palette in order",
      _seq[:len(_pal)] == list(_pal) and _seq[len(_pal)] == _pal[0])


# ── Part B: themed canvas background ────────────────────────────────────────
dark = base(board([scene([
    {"id": "t", "type": "text", "content": "Hi", "safe_zone_alignment": "TOP_CENTER"},
])]), style="3blue1brown/minimalist/neon", background="default")
check("dark theme paints camera.background_color on a default background",
      f'self.camera.background_color = "{THEMES["3blue1brown"].background}"' in dark)
check("base scene with themed background is valid Python", _valid(dark))

white = base(board([scene([
    {"id": "t", "type": "text", "content": "Hi", "safe_zone_alignment": "TOP_CENTER"},
])]), style="powerpoint/clean", background="white_canvas")
check("white_canvas suppresses camera.background_color (canvas owns the bg)",
      "camera.background_color" not in white)
check("white_canvas still routes through set_realistic_background",
      'set_realistic_background(self, "white_canvas"' in white)

image = base(board([scene([
    {"id": "s", "type": "shape", "content": "circle"},
])]), style="cyberpunk/retrowave/orange", background="space.jpg")
check("image background suppresses camera.background_color",
      "camera.background_color" not in image)
check("image background keeps the palette (uncoloured shape gets a theme colour)",
      any(c in image for c in THEMES["cyberpunk"].palette))


# ── Part C: shape palette + explicit-colour precedence ──────────────────────
shapes = base(board([scene([
    {"id": "a", "type": "shape", "content": "circle"},
    {"id": "b", "type": "shape", "content": "square"},
    {"id": "c", "type": "shape", "content": "triangle", "color": "RED"},
], cues=[{"cue": "x", "event": "",
          "animation_events": [{"action": "show", "target": "a"},
                               {"action": "show", "target": "b"},
                               {"action": "show", "target": "c"}]}])]),
    style="3blue1brown/minimalist/neon", background="default")
_p = THEMES["3blue1brown"].palette
check("first uncoloured shape gets palette[0]", f'.set_color("{_p[0]}")' in shapes)
check("second uncoloured shape gets palette[1]", f'.set_color("{_p[1]}")' in shapes)
check("model-authored colour (RED) is not overridden by the palette",
      ".set_color(RED)" in shapes)
check("a coloured shape does NOT also receive a palette hex",
      shapes.count(".set_color(") == 3)  # a, b (palette) + c (RED)

# text is left at its default (no forced palette colour on text)
text_only = base(board([scene([
    {"id": "t1", "type": "text", "content": "Alpha"},
    {"id": "t2", "type": "text", "content": "Beta"},
])]), style="3blue1brown/minimalist/neon", background="default")
check("uncoloured text is not palette-coloured (stays legible default)",
      ".set_color(" not in text_only)


# ── Part D: emphasis is COLOURLESS (2026-08-15) ─────────────────────────────
# `highlight` used to emit Indicate(target, color=theme.accent) — a flat accent
# repaint for half a second, which on a themed frame reads as the object changing
# meaning, and on a raster photo painted the whole bitmap (hence the Circumscribe
# special case for images). Removed on user review: emphasis is now a round-trip
# scale pulse carrying no colour, so neither the theme's accent nor a
# model-authored highlight colour reaches it. The palette still colours the
# OBJECT — this only retires the flash.
hl = base(board([scene([
    {"id": "s", "type": "shape", "content": "square"},
], cues=[{"cue": "look", "event": "",
          "animation_events": [{"action": "show", "target": "s"},
                               {"action": "highlight", "target": "s"}]}])]),
    style="cyberpunk/retrowave/orange", background="space.jpg")
check("highlight emits a colourless emphasize(), not Indicate",
      "emphasize(mobj_scene1_s)" in hl and "Indicate(" not in hl)
check("no colour flash survives anywhere in the scene",
      "Circumscribe(" not in hl and "color=YELLOW" not in hl
      and f"color='{THEMES['cyberpunk'].accent}')" not in hl)
check("the shape itself is still palette-coloured (only the flash went)",
      f"set_color(\"{THEMES['cyberpunk'].palette[0]}\")" in hl)
check("a model-authored highlight colour no longer paints anything",
      "'#ABCDEF'" not in base(board([scene([
          {"id": "s", "type": "shape", "content": "square"},
      ], cues=[{"cue": "look", "event": "",
                "animation_events": [{"action": "show", "target": "s"},
                                     {"action": "highlight", "target": "s",
                                      "color": "#ABCDEF"}]}])]),
          style="cyberpunk/retrowave/orange"))
check("the beat filler no longer carries an accent either",
      "sustain(self, [mobj_scene1_s], tracker)" in hl and "accent=" not in hl)


# ── Part E: style_profile fallback + both paths agree ───────────────────────
# style arg blank → fall back to the storyboard's own style_profile.
fb = base(board([scene([
    {"id": "s", "type": "shape", "content": "square"},
], cues=[{"cue": "look", "event": "",
          "animation_events": [{"action": "show", "target": "s"},
                               {"action": "highlight", "target": "s"}]}])],
    style_profile="cyberpunk/retrowave/orange"), style="", background="space.jpg")
# Observed through the PALETTE, not the emphasis accent: the accent stopped
# reaching generated code when the colour flash was removed, so the old signal
# would now pass vacuously for every style.
check("blank style arg falls back to storyboard.style_profile",
      f"set_color(\"{THEMES['cyberpunk'].palette[0]}\")" in fb)

two = board([
    scene([{"id": "s1", "type": "shape", "content": "circle"}], scene_index=1),
    scene([{"id": "s2", "type": "shape", "content": "square"}], scene_index=2),
], style_profile="3blue1brown/minimalist/neon")
scripts = parse_schema_to_scene_scripts(two, persona="en", style="3blue1brown/minimalist/neon",
                                        background="default")
check("per-scene path returns one script per scene", len(scripts) == 2)
check("every per-scene script is valid Python", all(_valid(s) for s in scripts))
check("per-scene scripts paint the same themed background as the base path",
      all(f'self.camera.background_color = "{THEMES["3blue1brown"].background}"' in s
          for s in scripts))
check("per-scene path palette cursor resets per scene (both scenes open on palette[0])",
      all(f'.set_color("{THEMES["3blue1brown"].palette[0]}")' in s for s in scripts))


# ── Part F: colour harmonization ────────────────────────────────────────────
# Why: measured 2026-08-14 over six cached boards, 190/198 elements (96%) carry a
# model-authored colour, and they are mostly raw primaries (#FF00FF, #00FFCC,
# #FFFF00). The palette only ever filled in for UNCOLOURED shapes, so the style
# profile decorated ~4% of the frame — "the style profile and the background are
# not matching, and the gen content is stale".
from lessonforge.theme import (harmonize, contrast_ratio, is_raw_primary, nearest_palette_color,  # noqa: E402
                   MIN_CONTRAST, _to_hex)

DARK = THEMES["3blue1brown"]
LIGHT = THEMES["powerpoint"]

check("F1 a raw primary is mapped into the palette",
      harmonize("#FF00FF", DARK) in DARK.palette and harmonize("#FFFF00", DARK) in DARK.palette)
check("F2 the mapping keeps HUE, so distinct things stay distinct",
      harmonize("#FF00FF", DARK) != harmonize("#FFFF00", DARK))
check("F3 a colour already in the palette is untouched",
      harmonize(DARK.palette[0], DARK) == DARK.palette[0])
check("F4 a designed non-palette colour with good contrast survives",
      harmonize("#7AE582", DARK) == "#7AE582")
check("F5 an illegible shape colour is remapped (black on a dark canvas)",
      harmonize("#111111", DARK) in DARK.palette)
check("F6 illegible TEXT goes to the theme's text colour, not a hue snap",
      harmonize("#111111", DARK, "text") == DARK.text
      and harmonize("BLACK", DARK, "math") == DARK.text)
check("F7 legible text keeps its colour (no gratuitous tinting)",
      harmonize("#FFFFFF", DARK, "text") == "#FFFFFF")
check("F8 white shapes on a WHITE canvas are rescued (the washed-out case)",
      contrast_ratio("#FFFFFF", "#FFFFFF") < MIN_CONTRAST
      and harmonize("#FFFFFF", LIGHT) in LIGHT.palette)
check("F9 white TEXT on a white canvas becomes the dark text colour",
      harmonize("WHITE", LIGHT, "text") == LIGHT.text)
check("F10 manim colour NAMES are understood, not just hex",
      _to_hex("RED") == "#FC6255" and _to_hex("#f0a") == "#FF00AA" and _to_hex("nope") is None)
check("F11 no colour in means no colour out (the caller's default applies)",
      harmonize("", DARK) is None and harmonize(None, DARK) is None)
check("F12 a themeless caller keeps the old behaviour",
      harmonize("#FF00FF", None) == "#FF00FF")
check("F13 pure black and white are not treated as raw primaries",
      not is_raw_primary("#FFFFFF") and not is_raw_primary("#000000")
      and is_raw_primary("#00FFFF"))
check("F14 a remap never produces an illegible colour",
      all(contrast_ratio(harmonize(c, t) or t.text,
                         "#FFFFFF" if t.is_light else t.background) >= MIN_CONTRAST
          for t in (DARK, LIGHT)
          for c in ("#FF00FF", "#FFFF00", "#111111", "#FFFFFF", "#00FF00")))

# The light-theme-on-a-dark-canvas mismatch, which is what the user actually saw.
check("F15 a LIGHT style on a non-white background is adapted, not shipped mismatched",
      not resolve_theme("powerpoint/clean", "default").is_light
      and not resolve_theme("powerpoint/clean", "chalkboard.jpg").is_light)
check("F16 powerpoint + white_canvas is still the light theme",
      resolve_theme("powerpoint/clean", "white_canvas").is_light)
check("F17 the adapted dark palette is legible on its own canvas",
      all(contrast_ratio(c, resolve_theme("powerpoint/clean", "default").background) >= MIN_CONTRAST
          for c in resolve_theme("powerpoint/clean", "default").palette))

# End to end through the transpiler.
_harm = base(board([scene([
    {"id": "a", "type": "shape", "content": "a circle", "color": "#FF00FF"},
    {"id": "b", "type": "text", "content": "Label", "color": "#111111"},
    {"id": "c", "type": "shape", "content": "a square", "color": "RED"},
])]), style="3blue1brown/minimalist/neon", background="default")
check("F18 the emitted code carries harmonized colour, not the raw primary",
      "#FF00FF" not in _harm and any(p in _harm for p in DARK.palette))
check("F19 an unchanged named colour stays a NAME in the emitted code",
      ".set_color(RED)" in _harm)
check("F20 illegible text was rescued in the emitted code",
      f'.set_color("{DARK.text}")' in _harm)


# ── Summary ─────────────────────────────────────────────────────────────────
passed = sum(1 for _, ok in checks if ok)
total = len(checks)
print(f"\n{passed}/{total} checks passed")
sys.exit(0 if passed == total else 1)
