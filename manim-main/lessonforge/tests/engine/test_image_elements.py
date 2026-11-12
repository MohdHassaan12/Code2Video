"""Acceptance harness for `image` elements (Wikimedia raster images).

No manim, no API keys, no network — the Commons resolver is stubbed.

Pins the contract added 2026-07-31:
- transpiler emits fetch_real_image(...) for type "image" (both codegen paths),
  treating `scale` as height with the text-sized default (0.7) upgraded to 3.0;
- images are never recolored, never re-scaled via .scale(), and their entrance
  is forced to FadeIn (ImageMobject is not a VMobject — Write/Create crash);
- a failed image degrades to a Text placeholder via asset_warnings;
- an image counts as a diagram for screen management, and the split-screen
  minimize play uses Group (VGroup raises TypeError on ImageMobject) while
  pure-vector scenes keep the proven VGroup path;
- app/assets.py resolve_image_elements rewrites resolved queries to local
  absolute paths and returns probe-style warnings for unresolvable ones.

Run: .venv/bin/python stem_animation_lab/test_image_elements.py
"""
import importlib.util
import os
import sys

LAB = os.path.dirname(os.path.abspath(__import__("lessonforge").__file__))  # the installed package dir
sys.path.insert(0, LAB)

from lessonforge.transpiler import parse_schema_to_base_scene, parse_schema_to_scene_scripts

PASSED = FAILED = 0


def check(name, cond, detail=""):
    global PASSED, FAILED
    if cond:
        PASSED += 1
        print(f"PASS {name}")
    else:
        FAILED += 1
        print(f"FAIL {name} {detail}")


def board(elements, cues=None, scenes=None):
    if scenes is None:
        scenes = [{
            "scene_index": 1,
            "description": "test",
            "elements": elements,
            "narration_cues": cues or [{"cue": "intro", "event": ""}],
            "wait_time": 1,
        }]
    return {"topic": "t", "visual_storyboard": scenes}


IMG = {
    "id": "bastille_img", "type": "image",
    "content": "Storming of the Bastille painting",
    "entrance_animation": "Create", "exit_animation": "FadeOut", "scale": 0.7,
}


# ── Part A: object construction ─────────────────────────────────────────────
code = parse_schema_to_base_scene(board([dict(IMG)]))
check("A1 image emits fetch_real_image with the query",
      "fetch_real_image('Storming of the Bastille painting'" in code)
check("A2 text-sized default scale (0.7) upgrades to height=3.0",
      "height=3.0" in code)
check("A3 entrance override 'Create' is forced to FadeIn",
      "Create(mobj_scene1_bastille_img" not in code and "FadeIn(mobj_scene1_bastille_img" in code)
img_line = next(l for l in code.splitlines() if "fetch_real_image" in l)
check("A4 image is never recolored", ".set_color(" not in img_line)
check("A5 image is never .scale()d (height= owns sizing)", ".scale(" not in img_line)

big = dict(IMG, scale=3.5)
code = parse_schema_to_base_scene(board([big]))
check("A6 explicit scale >= 1.5 becomes the height", "height=3.5" in code)

code = parse_schema_to_base_scene(
    board([dict(IMG)]),
    asset_warnings=[{"element_id": "bastille_img", "type": "image",
                     "keyword": IMG["content"], "status": "fallback"}],
)
check("A7 failed image degrades to a Text placeholder",
      "fetch_real_image" not in code and "Text('Storming of the Bastille" in code)

import ast
try:
    ast.parse(parse_schema_to_base_scene(board([dict(IMG)])))
    ok = True
except SyntaxError:
    ok = False
check("A8 generated script is valid Python", ok)

# Regression (2026-07-31 live run): transpiler used `logger` without defining it,
# so any board carrying a `composition` descriptor NameError'd the whole
# transpiler and silently fell back to LLM codegen — sol storyboards always set
# composition, so the deterministic path was dead on 100% of production boards.
comp_board = board([dict(IMG)])
comp_board["visual_storyboard"][0]["composition"] = "Large painting centre, caption below."
try:
    code = parse_schema_to_base_scene(comp_board)
    ok = "fetch_real_image" in code
except NameError:
    ok = False
check("A8b a board WITH a composition descriptor still transpiles", ok)

# Per-scene scripts only exist for multi-scene boards (single scene returns []).
two_scene = board([dict(IMG)])
two_scene["visual_storyboard"].append({
    "scene_index": 2, "description": "second",
    "elements": [TXT_EL := {"id": "t2", "type": "text", "content": "Recap",
                            "entrance_animation": "FadeIn", "exit_animation": "FadeOut",
                            "scale": 0.7}],
    "narration_cues": [{"cue": "recap", "event": ""}], "wait_time": 1,
})
scripts = parse_schema_to_scene_scripts(two_scene)
check("A9 per-scene (parallel) path also emits fetch_real_image",
      bool(scripts) and any("fetch_real_image" in s for s in scripts))

# ── Part B: screen management with an image diagram ────────────────────────
TXT = lambda i: {"id": f"step{i}", "type": "text", "content": f"Step {i}",
                 "entrance_animation": "FadeIn", "exit_animation": "FadeOut", "scale": 0.7}
pile_scene = board(
    [dict(IMG)] + [TXT(1), TXT(2)],
    cues=[
        {"cue": "look at this painting", "event": ""},
        {"cue": "two consequences follow", "event": ""},
    ],
    scenes=None,
)
# route the two texts to cue 2 by element order: transpiler assigns elements to
# cues via animation_events or round-robin; use explicit show events.
pile_scene["visual_storyboard"][0]["narration_cues"] = [
    {"cue": "look at this painting",
     "animation_events": [{"action": "show", "target": "bastille_img"}]},
    {"cue": "two consequences follow",
     "animation_events": [{"action": "show", "target": "step1"},
                          {"action": "show", "target": "step2"}]},
]
code = parse_schema_to_base_scene(pile_scene)
check("B1 text pile-up on an image triggers the split-screen minimize",
      ".animate.scale(0.55).move_to(LEFT * 3.4)" in code)
check("B2 image diagram minimize uses Group, not VGroup",
      "Group(mobj_scene1_bastille_img" in code and "VGroup(mobj_scene1_bastille_img" not in code)

vec_scene = board(
    [{"id": "ax", "type": "coordinate_system", "content": "x:0-10, y:0-10",
      "entrance_animation": "Create", "exit_animation": "FadeOut", "scale": 1.0},
     TXT(1), TXT(2)],
)
vec_scene["visual_storyboard"][0]["narration_cues"] = [
    {"cue": "here are the axes",
     "animation_events": [{"action": "show", "target": "ax"}]},
    {"cue": "now the derivation",
     "animation_events": [{"action": "show", "target": "step1"},
                          {"action": "show", "target": "step2"}]},
]
code = parse_schema_to_base_scene(vec_scene)
check("B3 pure-vector scenes keep the proven VGroup minimize",
      "VGroup(mobj_scene1_ax" in code)

# ── Part B2: highlight events never recolor an image ───────────────────────
# Was: images got Circumscribe (an outline) while everything else got Indicate (a
# recolour), because Indicate paints a whole bitmap solid. The colour flash was
# removed entirely on 2026-08-15, so the special case is gone with it — both types
# now take the same colourless `emphasize` pulse, which is safe on an ImageMobject
# for the same reason the geometric sustain gestures always were.
hl_board = board([dict(IMG)])
hl_board["visual_storyboard"][0]["narration_cues"] = [
    {"cue": "look here",
     "animation_events": [{"action": "show", "target": "bastille_img"},
                          {"action": "highlight", "target": "bastille_img", "color": "YELLOW"}]},
]
code = parse_schema_to_base_scene(hl_board)
check("B4 highlight on an image never recolors it (no Indicate, no Circumscribe box)",
      "emphasize(mobj_scene1_bastille_img)" in code
      and "Indicate(mobj_scene1_bastille_img" not in code
      and "Circumscribe(" not in code
      and "'YELLOW'" not in code and "color=YELLOW" not in code)

# ── Part B3: calm entrances + hero-image centering (2026-07-31 user review:
# elastic pop on every element read as SHAKING; corner-zone photos left the
# stage empty) ───────────────────────────────────────────────────────────────
code = parse_schema_to_base_scene(board([dict(IMG), TXT(1)]))
check("B5 no elastic pop anywhere (retired — everything bounced = shaking)",
      "ease_out_elastic" not in code and "scale=0.1" not in code)
check("B6 text/image entrances are calm rise-and-fade",
      "shift=UP * 0.25" in code and "ease_out_cubic" in code)

hero = dict(IMG)
hero["safe_zone_alignment"] = "TOP_LEFT"          # zone placement is overridden
code = parse_schema_to_base_scene(board([hero, TXT(1)]))
img_line = next(l for l in code.splitlines() if "fetch_real_image" in l)
check("B7 first free-standing image is centered (hero), not corner-zoned",
      ".move_to(RIGHT * 0 + UP * 0.3)" in img_line and ".to_corner" not in img_line)

hero2, second = dict(IMG), dict(IMG, id="img2")
second["safe_zone_alignment"] = "RIGHT_CENTER"
code = parse_schema_to_base_scene(board([hero2, second]))
lines_ = [l for l in code.splitlines() if "fetch_real_image" in l]
check("B8 only the FIRST image is hero-centered; the second keeps its zone",
      ".move_to(RIGHT * 0 + UP * 0.3)" in lines_[0] and ".to_edge(RIGHT" in lines_[1])

ax_img = dict(IMG)
ax_img["safe_zone_alignment"] = "TOP_LEFT"
code = parse_schema_to_base_scene(board([
    {"id": "ax", "type": "coordinate_system", "content": "x:0-10, y:0-10",
     "entrance_animation": "Create", "exit_animation": "FadeOut", "scale": 1.0},
    ax_img]))
img_line = next(l for l in code.splitlines() if "fetch_real_image" in l)
check("B9 beside an Axes the image keeps its zone (no hero centering)",
      ".move_to([0, 0.3, 0])" not in img_line)

# ── Part C: server-side resolution pass (app/assets.py, standalone load) ────
spec = importlib.util.spec_from_file_location("lab_assets", os.path.join(LAB, "engine", "assets.py"))
lab_assets = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lab_assets)

fake_path = os.path.join(LAB, "assets", "wikimedia_cache", "wm_test.jpg")
calls = []


def fake_resolver(query, thumb_width=1024):
    calls.append(query)
    if "unfindable" in query:
        return None
    return {"path": fake_path, "width": 1024, "height": 768, "title": "File:x.jpg",
            "source_url": "https://commons.wikimedia.org/x", "license": "Public domain",
            "artist": "", "query": query}


lab_assets.resolve_wikimedia_image = fake_resolver
b = board([dict(IMG), dict(IMG, id="ghost", content="unfindable thing xyz")])
warnings = lab_assets.resolve_image_elements(b)
els = b["visual_storyboard"][0]["elements"]
check("C1 resolved query is rewritten to the local absolute path",
      els[0]["content"] == fake_path)
check("C2 unresolvable image yields a probe-style fallback warning",
      len(warnings) == 1 and warnings[0]["element_id"] == "ghost"
      and warnings[0]["status"] == "fallback" and warnings[0]["provider"] == "wikimedia")
check("C3 unresolved content is left as the query (render-time fallback input)",
      els[1]["content"] == "unfindable thing xyz")
check("C4 resolver is only called for image elements", len(calls) == 2)

warnings2 = lab_assets.resolve_image_elements(b)
check("C5 already-resolved (absolute path) elements are not re-resolved",
      len(calls) == 3 and not any(c == fake_path for c in calls[2:]))

check("C6 non-image boards are a no-op",
      lab_assets.resolve_image_elements(board([TXT(1)])) == [])

# ── Part D: export contract (source-level — viz_helpers imports manim) ─────
# Regression (2026-07-31 live): viz_helpers has an explicit __all__, so a new
# helper that isn't listed silently vanishes from `from viz_helpers import *`
# and every scene using it NameErrors at render — the self-heal repair then
# "fixes" the NameError by swapping photos for icons (t02 Mohenjo-daro lost all
# 7 photos this way). Same trap for `_bg_image` (underscore ⇒ star-import only
# exports it via __all__), which master-script scene transitions depend on.
import re as _re
_src = open(os.path.join(LAB, "viz_helpers.py"), encoding="utf-8").read()
_m = _re.search(r"__all__\s*=\s*\[(.*?)\]", _src, _re.DOTALL)
_all_block = _m.group(1) if _m else ""
check("D1 fetch_real_image is exported in viz_helpers.__all__",
      '"fetch_real_image"' in _all_block)
check("D2 _bg_image is exported for master-script scene transitions",
      '"_bg_image"' in _all_block)

print(f"\n{PASSED}/{PASSED + FAILED} checks passed")
sys.exit(1 if FAILED else 0)
