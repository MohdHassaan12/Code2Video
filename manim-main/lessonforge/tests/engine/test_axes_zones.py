"""Axes-aware zones + label slots acceptance test — no manim, no server, no keys.

Pins the roadmap D-3/D-4 contract ("axes-aware zone claiming, label slots
computed by code"):
- a zone whose footprint the axes bbox overlaps is pre-claimed, so zone-placed
  text falls back AROUND the axes instead of under the y-axis (the scene-4
  audit failure);
- zones clear of the axes (title band over a centered axes) are untouched;
- the axes' OWN requested zone is not stolen by the seeding;
- a label attached to an on-axes shape flips its next_to direction away from
  the axis tick strips (the |x2-x1|-through-the-"3"-tick failure);
- zone stacking shifts toward frame centre (BOTTOM zones stack UP, not off-frame);
- both codegen paths (base scene + per-scene scripts) agree, and every
  generated script is valid Python.

Run: .venv/bin/python stem_animation_lab/test_axes_zones.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lessonforge.transpiler import parse_schema_to_base_scene, parse_schema_to_scene_scripts  # noqa: E402

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


def gen(*scenes_):
    return parse_schema_to_base_scene({"visual_storyboard": list(scenes_)})


def line_of(code, var):
    for ln in code.splitlines():
        if ln.strip().startswith(f"{var} ="):
            return ln
    return ""


AXES = {"id": "ax", "type": "coordinate_system", "content": "x:[-5,5] y:[-4,4]", "scale": 0.7}

# 1-2. Centered axes: side-centre zones are claimed, the title band is not.
code = gen(scene([
    dict(AXES),
    {"id": "title", "type": "text", "content": "Distance", "safe_zone_alignment": "TOP_CENTER"},
    {"id": "question", "type": "text", "content": "Find d", "safe_zone_alignment": "LEFT_CENTER"},
]))
check("centered axes: LEFT_CENTER text rerouted off the axes",
      ".to_edge(LEFT" not in line_of(code, "mobj_scene1_question"))
check("centered axes: rerouted to the free top-left corner",
      ".to_corner(UL" in line_of(code, "mobj_scene1_question"))
check("centered axes: title band stays TOP_CENTER",
      ".to_edge(UP, buff=0.3)" in line_of(code, "mobj_scene1_title"))

# 3. Raised axes (the scene-4 failure): top + side zones claimed, title falls to the bottom.
code = gen(scene([
    dict(AXES, absolute_position=[0, 1.5]),
    {"id": "title", "type": "text", "content": "Distance", "safe_zone_alignment": "TOP_CENTER"},
]))
t = line_of(code, "mobj_scene1_title")
check("raised axes: TOP_CENTER text no longer under the y-axis",
      ".to_edge(UP, buff=0.3)" not in t)
check("raised axes: text rerouted to the free bottom band",
      ".to_edge(DOWN" in t)

# 4. No axes in the scene: zones behave exactly as before.
code = gen(scene([
    {"id": "para", "type": "text", "content": "Plain text", "safe_zone_alignment": "LEFT_CENTER"},
]))
check("no axes: LEFT_CENTER untouched",
      ".to_edge(LEFT, buff=0.3)" in line_of(code, "mobj_scene1_para"))

# 5. The axes' own requested zone is not stolen by the seeding.
code = gen(scene([
    dict(AXES, safe_zone_alignment="TOP_CENTER"),
]))
check("axes keeps its own requested zone",
      ".to_edge(UP, buff=0.3)" in line_of(code, "mobj_scene1_ax"))

# 6-8. Label slots: flip away from tick strips, leave far-from-axis labels alone.
code = gen(scene([
    dict(AXES),
    {"id": "leg", "type": "shape", "content": "line", "absolute_position": [2, 0.5]},
    {"id": "lbl", "type": "math", "content": "|x_2-x_1|",
     "relative_positioning": {"relative_to": "leg", "direction": "DOWN", "buffer": 0.3}},
]))
check("label toward the x-axis tick strip flips UP",
      ".next_to(mobj_scene1_leg, UP," in line_of(code, "mobj_scene1_lbl"))

code = gen(scene([
    dict(AXES),
    {"id": "leg", "type": "shape", "content": "line", "absolute_position": [2, 3]},
    {"id": "lbl", "type": "math", "content": "|x_2-x_1|",
     "relative_positioning": {"relative_to": "leg", "direction": "DOWN", "buffer": 0.3}},
]))
check("label far from the axis keeps its direction",
      ".next_to(mobj_scene1_leg, DOWN," in line_of(code, "mobj_scene1_lbl"))

code = gen(scene([
    dict(AXES),
    {"id": "leg", "type": "shape", "content": "line", "absolute_position": [0.5, 2]},
    {"id": "lbl", "type": "math", "content": "|y_2-y_1|",
     "relative_positioning": {"relative_to": "leg", "direction": "LEFT", "buffer": 0.3}},
]))
check("label toward the y-axis tick strip flips RIGHT",
      ".next_to(mobj_scene1_leg, RIGHT," in line_of(code, "mobj_scene1_lbl"))

# 9. Ref off the axes ranges (scene-space) is never slot-adjusted.
code = gen(scene([
    dict(AXES),
    {"id": "note", "type": "shape", "content": "arrow", "absolute_position": [6.5, 0.5]},
    {"id": "lbl", "type": "text", "content": "note",
     "relative_positioning": {"relative_to": "note", "direction": "DOWN", "buffer": 0.3}},
]))
check("off-axes reference keeps its direction",
      ".next_to(mobj_scene1_note, DOWN," in line_of(code, "mobj_scene1_lbl"))

# 10. Zone stacking shifts INTO the frame from a bottom zone.
els = [dict(AXES)] + [
    {"id": f"cap{i}", "type": "text", "content": f"caption {i}",
     "safe_zone_alignment": "BOTTOM_CENTER"}
    for i in range(5)
]
code = gen(scene(els))
check("exhausted bottom zone stacks UP into the frame",
      ".shift(UP * 0.85)" in code and ".to_edge(DOWN, buff=0.3).shift(DOWN" not in code)

# 11. Per-scene scripts path agrees with the base path.
scripts = parse_schema_to_scene_scripts({"visual_storyboard": [
    scene([
        dict(AXES),
        {"id": "question", "type": "text", "content": "Find d",
         "safe_zone_alignment": "LEFT_CENTER"},
    ], scene_index=1),
    scene([{"id": "t2", "type": "text", "content": "Recap",
            "safe_zone_alignment": "TOP_CENTER"}], scene_index=2),
]})
check("per-scene path reroutes the same zone",
      len(scripts) == 2 and ".to_corner(UL" in line_of(scripts[0], "mobj_scene1_question"))

# 12. Every generated script is valid Python.
try:
    compile(code, "<base>", "exec")
    for s in scripts:
        compile(s, "<scene>", "exec")
    check("generated scripts compile", True)
except SyntaxError:
    check("generated scripts compile", False)

failed = [n for n, ok in checks if not ok]
print(f"\n{len(checks) - len(failed)}/{len(checks)} checks passed")
sys.exit(1 if failed else 0)
