"""Acceptance harness for screen management: the minimize-to-side split screen and
the viz_helpers import normalization. No manim, no API keys — pure codegen checks.

Both behaviours are pinned from real failures on live render job `bpipueek6`:
  * The scene minimized on ZERO of its scenes because the trigger only fired on
    `math` elements, and that storyboard carried its derivation steps as `text`.
  * The generated script called `auto_fit_scene(self)` while importing only
    `UniversalTTSService` from viz_helpers — a guaranteed NameError. The
    "already imported?" guard in sanitize_generated_code was satisfied by the
    selective import, so the star import (and the config.font line keyed off it)
    was never added.

Run: python test_minimize_split.py
"""
import os
import sys

import lessonforge.transpiler as T

PASS, FAIL = [], []


def check(name, cond):
    (PASS if cond else FAIL).append(name)
    print(f"{'PASS' if cond else 'FAIL'} {name}")


AXES = {"id": "ax", "type": "coordinate_system", "x_range": [0, 6, 1], "y_range": [0, 6, 1]}
MINIMIZED = "animate.scale(0.55)"


def two_cue_board(later_els):
    """Scene where the axes land in cue 0 and `later_els` arrive in cue 1."""
    return {"visual_storyboard": [{
        "scene_index": 1, "description": "d",
        "elements": [AXES] + later_els,
        "narration_cues": [
            {"cue": "axes", "animation_events": [{"action": "show", "target": "ax"}]},
            {"cue": "next", "animation_events": [
                {"action": "show", "target": e["id"]} for e in later_els]},
        ],
    }]}


def anchored(eid, content):
    return {"id": eid, "type": "text", "content": content,
            "relative_positioning": {"relative_to": "ax", "direction": "DOWN"}}


# ── Minimize trigger ────────────────────────────────────────────────────────
code = T.parse_schema_to_base_scene(two_cue_board([
    {"id": "s1", "type": "text", "content": "Step one: subtract"},
    {"id": "s2", "type": "text", "content": "Step two: square"},
]))
check("two prose steps over a diagram trigger the split", MINIMIZED in code)
check("split text lands in the right column", "RIGHT * 3.6" in code)
check("right column stacks downward", "UP * 2.2" in code and "UP * 1.3" in code)

code = T.parse_schema_to_base_scene(two_cue_board([
    {"id": "m", "type": "math", "content": "a^2+b^2"}]))
check("a single formula is enough to split (derivations are tall)", MINIMIZED in code)

code = T.parse_schema_to_base_scene(two_cue_board([
    {"id": "t", "type": "text", "content": "A one-line caption"}]))
check("a lone caption does NOT split the screen", MINIMIZED not in code)

code = T.parse_schema_to_base_scene(two_cue_board([anchored("l1", "x"), anchored("l2", "y")]))
check("diagram-anchored labels never trigger a split", MINIMIZED not in code)

# Cue 0 introduces the diagram itself — nothing to move aside yet.
code = T.parse_schema_to_base_scene({"visual_storyboard": [{
    "scene_index": 1, "description": "d",
    "elements": [AXES,
                 {"id": "a", "type": "text", "content": "one"},
                 {"id": "b", "type": "text", "content": "two"}],
    "narration_cues": [{"cue": "all", "animation_events": [
        {"action": "show", "target": x} for x in ("ax", "a", "b")]}],
}]})
check("cue 0 does not split (the diagram is still arriving)", MINIMIZED not in code)

# The diagram and its labels shrink together as one group.
code = T.parse_schema_to_base_scene({"visual_storyboard": [{
    "scene_index": 1, "description": "d",
    "elements": [AXES, anchored("axlbl", "x-axis"),
                 {"id": "s1", "type": "text", "content": "Step one"},
                 {"id": "s2", "type": "text", "content": "Step two"}],
    "narration_cues": [
        {"cue": "axes", "animation_events": [
            {"action": "show", "target": "ax"}, {"action": "show", "target": "axlbl"}]},
        {"cue": "steps", "animation_events": [
            {"action": "show", "target": "s1"}, {"action": "show", "target": "s2"}]},
    ],
}]})
check("anchored label shrinks with the diagram, not into the column",
      "VGroup(mobj_scene1_ax, mobj_scene1_axlbl)" + ".animate.scale(0.55)" in code)

# The per-scene (parallel render) path must behave identically. It returns [] for a
# single-scene storyboard by design, so the board here carries a filler second scene.
split_board = two_cue_board([
    {"id": "s1", "type": "text", "content": "Step one: subtract"},
    {"id": "s2", "type": "text", "content": "Step two: square"},
])
split_board["visual_storyboard"].append({
    "scene_index": 2, "description": "filler",
    "elements": [{"id": "z", "type": "text", "content": "The end"}],
    "narration_cues": [{"cue": "done", "animation_events": [
        {"action": "show", "target": "z"}]}],
})
scripts = T.parse_schema_to_scene_scripts(split_board)
check("per-scene path emits one script per scene", len(scripts) == 2)
per_scene = "\n".join(s if isinstance(s, str) else s.get("code", "") for s in scripts)
check("per-scene path splits the same way", MINIMIZED in per_scene)

# ── viz_helpers import normalization ────────────────────────────────────────
# Anchor on this file's directory, NOT "." — from the repo root, "." would put the
# root-level Streamlit app.py ahead of stem_animation_lab/app/ and import the wrong app.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lessonforge.engine as app  # noqa: E402  (imported late: it pulls in the whole server module)

selective = (
    "from manim import *\n"
    "from manim_voiceover import VoiceoverScene\n"
    "from viz_helpers import UniversalTTSService\n\n"
    "class STEMAnimation(VoiceoverScene):\n"
    "    def construct(self):\n"
    "        auto_fit_scene(self)\n"
)
out = app.sanitize_generated_code(selective)
check("selective viz_helpers import is widened to a star import",
      "from viz_helpers import *" in out)
check("the selective form is gone (no shadowing import left behind)",
      "import UniversalTTSService" not in out)
check("config.font injection is restored by the star import",
      'config.font = "Montserrat"' in out)

already_star = selective.replace("import UniversalTTSService", "import *")
out = app.sanitize_generated_code(already_star)
check("an existing star import is left alone (not duplicated)",
      out.count("from viz_helpers import *") == 1)

# ── Indic strip: both quote styles (transpiler emits repr → single quotes) ──
# Dalton run 2026-07-20: a hybrid video shipped Devanagari headings because the
# strip only matched Text("...") while the transpiler emitted Text('...').
single_q = "t = Text('आंशिक दबाव = यदि केवल एक गैस होती तो उसका दबाव')"
out = app.sanitize_generated_code(single_q, "hybrid")
check("single-quoted Devanagari Text is stripped (hybrid)", "आंशिक" not in out)
check("pure-Indic string strips to empty, not punctuation junk",
      "Text('')" in out)

shrapnel = 't = Text("\'गैर-क्रियाशील\' ?")'
out = app.sanitize_generated_code(shrapnel, "hybrid")
check("quote/punctuation shrapnel ('-' ? on screen) is emptied",
      "'-'" not in out and '?"' not in out)

mixed = "t = Text('Plant Tissues (पादप ऊतक)')"
out = app.sanitize_generated_code(mixed, "hybrid")
check("mixed content keeps its English part", "Plant Tissues" in out and "पादप" not in out)

apos = 't = Text("Dalton\'s Law")'
out = app.sanitize_generated_code(apos, "hybrid")
check("apostrophe inside double quotes survives", "Dalton's Law" in out)

out = app.sanitize_generated_code(single_q, "native")
check("native persona keeps Devanagari on screen", "आंशिक" in out)

print(f"\n{len(PASS)}/{len(PASS) + len(FAIL)} checks passed")
sys.exit(1 if FAIL else 0)
