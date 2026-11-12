"""Entrance-animation vocabulary census — no manim, no server, no keys.

Pins the roadmap D6 contract ("videos read as static slideware" because every
element faded in identically): the transpiler owns a deterministic per-type
entrance map, refined by shape keyword, and a storyboard with one element of
each type must emit a genuinely diverse animation vocabulary.

- ≥4 distinct entrance animation classes across a mixed-type scene (census);
- shape keywords map to their idiomatic entrance (arrow→GrowArrow,
  line→Create, point→GrowFromCenter, circle→DrawBorderThenFill);
- keyword precedence mirrors _build_obj_expr, so the animation always matches
  the object actually emitted ("arrow pointing at X" builds a Dot via the
  "point" match and must NOT GrowArrow);
- a schema-provided entrance_animation override still wins;
- both codegen paths (base scene + per-scene scripts) agree, and every
  generated script is valid Python.

Run: .venv/bin/python stem_animation_lab/test_entrance_map.py
"""
import ast
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lessonforge.transpiler import (  # noqa: E402
    parse_schema_to_base_scene,
    parse_schema_to_scene_scripts,
    _build_entrance_call,
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


def entrance_classes(code):
    """Animation class names used inside self.play entrance lines."""
    names = set()
    for m in re.finditer(r"self\.play\((.*)\)", code):
        names.update(re.findall(
            r"\b(FadeIn|Write|Create|GrowFromCenter|GrowArrow|DrawBorderThenFill|SpinInFromNothing)\(",
            m.group(1)))
    return names


def _valid(src):
    try:
        ast.parse(src)
        return True
    except SyntaxError:
        return False


# 1. Census: one element of each major type ⇒ ≥4 distinct entrance classes.
mixed = scene([
    {"id": "title", "type": "text", "content": "Newton's Law", "safe_zone_alignment": "TOP_CENTER"},
    {"id": "eq", "type": "math", "content": "F = ma"},
    {"id": "ax", "type": "coordinate_system", "content": "x:[-5,5] y:[-4,4]"},
    {"id": "arr", "type": "shape", "content": "arrow showing force"},
    {"id": "box", "type": "shape", "content": "square block"},
], cues=[{"cue": "test", "event": "", "elements_to_show": ["title", "eq", "ax", "arr", "box"]}])
code = parse_schema_to_base_scene({"visual_storyboard": [mixed]})
classes = entrance_classes(code)
check(f"mixed-type scene emits >=4 distinct entrance classes (got {sorted(classes)})",
      len(classes) >= 4)
check("base scene script is valid Python", _valid(code))


# 2. Shape keyword → idiomatic entrance.
check("arrow shape gets GrowArrow",
      _build_entrance_call("shape", "", "v", content="arrow showing force").startswith("GrowArrow("))
check("line shape gets Create",
      _build_entrance_call("shape", "", "v", content="dashed line").startswith("Create("))
check("point shape gets GrowFromCenter",
      _build_entrance_call("shape", "", "v", content="point A").startswith("GrowFromCenter("))
check("circle shape gets DrawBorderThenFill",
      _build_entrance_call("shape", "", "v", content="circle").startswith("DrawBorderThenFill("))
check("unknown shape keeps GrowFromCenter default",
      _build_entrance_call("shape", "", "v", content="mystery blob").startswith("GrowFromCenter("))

# 3. Precedence mirrors _build_obj_expr: "arrow pointing at X" builds a Dot.
check("'arrow pointing at X' must NOT GrowArrow (object is a Dot)",
      _build_entrance_call("shape", "", "v", content="arrow pointing at X").startswith("GrowFromCenter("))

# 4. Non-shape types unchanged.
check("math gets Write", _build_entrance_call("math", "", "v").startswith("Write("))
# 2026-07-31: elastic pop retired after user review (every element bouncing
# read as shaking) — text now enters with a calm rise-and-fade.
check("text gets calm FadeIn (elastic pop retired)",
      "ease_out_cubic" in _build_entrance_call("text", "", "v")
      and "ease_out_elastic" not in _build_entrance_call("text", "", "v"))
check("axes get Create", _build_entrance_call("coordinate_system", "", "v").startswith("Create("))

# 5. Schema override still wins — but only where the emitted object can take it.
check("entrance_animation override beats the keyword map",
      _build_entrance_call("shape", "SpinInFromNothing", "v", content="arrow").startswith("SpinInFromNothing("))

# 5b. An override must not undo the object↔entrance agreement (2026-08-15).
# GrowArrow calls `.scale(0, scale_tips=True)`; every non-Arrow VMobject raises
# TypeError and the whole scene dies at render. A "velocity arrow" whose prose
# head matched `point` built a Dot and carried entrance_animation="GrowArrow".
check("GrowArrow override is refused when the object is a Dot",
      _build_entrance_call("shape", "GrowArrow", "v", content="velocity arrow pointing right",
                           obj_expr="Dot(radius=0.1)").startswith("GrowFromCenter("))
check("GrowArrow override is honoured on a real Arrow",
      _build_entrance_call("shape", "GrowArrow", "v", content="arrow showing force",
                           obj_expr="Arrow(ORIGIN, RIGHT)").startswith("GrowArrow("))
check("GrowArrow is honoured on an arrow-headed connector",
      _build_entrance_call("shape", "GrowArrow", "v", content="arrow from a to b",
                           obj_expr="connector(a, b, color=WHITE, arrow=True)").startswith("GrowArrow("))
check("GrowArrow is refused on a headless connector (it is a Line)",
      not _build_entrance_call("shape", "GrowArrow", "v", content="link from a to b",
                               obj_expr="connector(a, b, color=WHITE, arrow=False)").startswith("GrowArrow("))
check("AddTextLetterByLetter is refused on a non-text element",
      not _build_entrance_call("shape", "AddTextLetterByLetter", "v", content="circle",
                               obj_expr="Circle()").startswith("AddTextLetterByLetter("))
check("AddTextLetterByLetter is honoured on text",
      _build_entrance_call("text", "AddTextLetterByLetter", "v",
                           obj_expr="Text('hi')").startswith("AddTextLetterByLetter("))

# 5c. Whole-board: every GrowArrow emitted must target something with a tip.
_arrowish = ("Arrow", "Vector", "DoubleArrow", "CurvedArrow", "LabeledArrow")
def _growarrow_targets_are_arrows(code):
    ctor = {}
    for ln in code.split("\n"):
        m = re.match(r"\s*(mobj_\w+)\s*=\s*(\w+)\(", ln)
        if m:
            ctor[m.group(1)] = (m.group(2), ln)
    for ln in code.split("\n"):
        for v in re.findall(r"GrowArrow\((mobj_\w+)\)", ln):
            head, decl = ctor.get(v, ("?", ""))
            if head in _arrowish:
                continue
            if head == "connector" and "arrow=True" in decl:
                continue
            return False, f"GrowArrow({v}) on {head}"
    return True, ""

_trap = scene([
    {"id": "vel", "type": "shape", "content": "velocity arrow pointing right",
     "entrance_animation": "GrowArrow", "position": [0, 0]},
    {"id": "force", "type": "shape", "content": "arrow showing force",
     "entrance_animation": "GrowArrow", "position": [2, 0]},
], scene_index=1)
_ok, _why = _growarrow_targets_are_arrows(
    parse_schema_to_base_scene({"visual_storyboard": [_trap]}))
check(f"base scene: no GrowArrow on a non-arrow ({_why or 'clean'})", _ok)

# 6. Per-scene scripts agree with the base scene path (the per-scene emitter
# only engages for multi-scene storyboards).
closer = scene([{"id": "recap", "type": "text", "content": "Recap"}], scene_index=2)
scripts = parse_schema_to_scene_scripts({"visual_storyboard": [mixed, closer]})
sc = scripts[0] if scripts else ""
check("per-scene script emits GrowArrow for the arrow too", "GrowArrow(" in sc)
check("per-scene script is valid Python", _valid(sc))

failed = [n for n, ok in checks if not ok]
print(f"\n{len(checks) - len(failed)}/{len(checks)} checks passed")
if failed:
    sys.exit(1)
