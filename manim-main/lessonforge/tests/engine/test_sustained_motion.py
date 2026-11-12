"""Acceptance harness for sustained motion — the beat filler (viz_helpers.sustain).

The complaint this pins (2026-08-14, from the user): "there are no dynamic motion in
the gen video". Measured cause: a voiceover block plays its entrances for ~half the
narration and then holds a STILL FRAME for the rest, and the storyboards never
rescue it — across three live boards the model emitted 92 `show`, 42 `hide`, 6
`highlight` and ZERO transform/move_to/focus events. So motion is code's job.

Part A runs with NO manim (transpiler emission only). Part B does a REAL manim
render of a scene that calls sustain(), because the whole point is that the
gestures actually play — a mocked scene would prove nothing. No API keys, no
network: the render has no voiceover, and sustain takes `seconds=` instead.

    .venv/bin/python stem_animation_lab/test_sustained_motion.py [--keep]
"""
import ast
import inspect
import os
import re
import sys
import shutil
import subprocess
import tempfile
from pathlib import Path

HERE = Path(__import__("lessonforge").__file__).resolve().parent  # the installed package dir
sys.path.insert(0, str(HERE))

import lessonforge.transpiler as T  # noqa: E402

CHECKS = []


def check(name, cond, detail=""):
    CHECKS.append((name, bool(cond)))
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"  — {detail}" if detail and not cond else ""))


def scene(i, extra_cue=False):
    cues = [
        {"cue": "Here is the heading for this scene.",
         "animation_events": [{"action": "show", "target": f"t{i}"}]},
        {"cue": "And now a circle appears beside it.",
         "animation_events": [{"action": "show", "target": f"b{i}"}]},
    ]
    if extra_cue:
        # A beat that introduces NOTHING — the classic dead-air case.
        cues.append({"cue": "Nothing new appears; the narrator just explains.",
                     "animation_events": []})
    return {
        "scene_index": i, "description": f"Scene {i}",
        "elements": [
            {"id": f"t{i}", "type": "text", "content": f"Heading {i}",
             "safe_zone_alignment": "TOP_CENTER"},
            {"id": f"b{i}", "type": "shape", "content": "a circle"},
        ],
        "narration_cues": cues,
    }


# ── Part A: emission (no manim) ───────────────────────────────────────────────
print("\nPart A — every beat gets a filler, in both codegen paths")

board = {"visual_storyboard": [scene(1, extra_cue=True), scene(2)]}
master = T.parse_schema_to_base_scene(board, "hybrid")
scripts = T.parse_schema_to_scene_scripts(board, persona="hybrid")

beats = len(re.findall(r"with self\.voiceover", master))
fills = len(re.findall(r"\bsustain\(self,", master))
check("A1 every voiceover beat ends with a sustain call", beats == fills and beats == 5,
      f"{beats} beats, {fills} fillers")
check("A2 the master script still compiles", compile(master, "m", "exec") or True)

check("A3 a cue gestures the elements IT introduced",
      "sustain(self, [mobj_scene1_t1], tracker" in master
      and "sustain(self, [mobj_scene1_b1], tracker" in master)
dead_air = [ln for ln in master.splitlines() if "sustain(" in ln][2]
check("A4 a beat that introduces nothing falls back to what is on screen",
      "mobj_scene1_t1" in dead_air and "mobj_scene1_b1" in dead_air, dead_air.strip())

check("A5 both codegen paths agree", len(scripts) == 2
      and all("sustain(self," in s for s in scripts)
      and all(compile(s, "s", "exec") or True for s in scripts))
# A6: the filler carries NO colour. The accent used to be threaded through so the
# Indicate gesture matched the theme; the colour pulse was removed on 2026-08-15
# (user review, "remove the object highlight") and every gesture is geometric now,
# so an `accent=` in generated code would be a dead argument pointing at a gesture
# that no longer exists. `sustain` still ACCEPTS the kwarg — scripts emitted before
# the change must keep running.
check("A6 the filler carries no colour argument",
      re.search(r"sustain\(self, \[[^\]]*\], tracker\)", master) is not None
      and "accent=" not in master)
check("A6b sustain still accepts a legacy accent kwarg",
      "accent" in inspect.signature(
          __import__("lessonforge.viz_helpers", fromlist=["x"]).sustain).parameters)
def _viz_all():
    """The real `__all__` list, read without importing manim.

    Parsed with ast rather than sliced out of the source: the first cut split on
    the literal "__all__" and stopped at the next "]", so the COMMENT inside the
    list warning that a name missing from __all__ NameErrors every render cut the
    slice short and failed this check while the export was perfectly fine.
    """
    tree = ast.parse((HERE / "viz_helpers.py").read_text())
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
                getattr(t, "id", "") == "__all__" for t in node.targets):
            return [e.value for e in node.value.elts if isinstance(e, ast.Constant)]
    return []


check("A7 sustain is exported from viz_helpers (a star-import miss is a NameError)",
      "sustain" in _viz_all())


# ── Part B: a real render ─────────────────────────────────────────────────────
print("\nPart B — the gestures actually play (real manim render)")

SCENE_SRC = '''
import sys
sys.path.insert(0, {lab!r})
from manim import *
from viz_helpers import *
import numpy as np

class MotionProbe(Scene):
    def construct(self):
        title = Text("Sustained", font_size=36).to_edge(UP)
        ring = Circle(radius=1.0, color=BLUE)
        img = None
        self.play(FadeIn(title), Create(ring), run_time=0.6)
        before = [title.get_center().copy(), ring.get_center().copy(),
                  title.height, ring.height]
        sustain(self, [title, ring], seconds=6.0, accent=YELLOW)
        after = [title.get_center().copy(), ring.get_center().copy(),
                 title.height, ring.height]
        moved = (np.linalg.norm(before[0] - after[0]) + np.linalg.norm(before[1] - after[1]))
        resized = abs(before[2] - after[2]) + abs(before[3] - after[3])
        print(f"PROBE_ROUNDTRIP moved={{moved:.6f}} resized={{resized:.6f}}")
        # A mobject that was removed must never be gestured.
        self.remove(ring)
        sustain(self, [ring], seconds=3.0)
        print("PROBE_REMOVED_OK")
        # No mobjects at all, and a zero budget: must not raise.
        sustain(self, [], seconds=2.0)
        sustain(self, [title], seconds=0.0)
        print("PROBE_EDGE_OK")
        # `emphasize` is what every `highlight` event now plays. It must be a real
        # Animation, round-trip, and leave the colour untouched (the whole point of
        # replacing Indicate). The probe measures after every self.play, so a pulse
        # that ended even slightly large would manufacture violations.
        e_before = [title.get_center().copy(), title.height, title.color]
        self.play(emphasize(title), run_time=0.5)
        e_after = [title.get_center().copy(), title.height, title.color]
        e_moved = float(np.linalg.norm(e_before[0] - e_after[0]))
        e_resized = abs(e_before[1] - e_after[1])
        print(f"PROBE_EMPHASIZE moved={{e_moved:.6f}} resized={{e_resized:.6f}} "
              f"recolored={{e_before[2] != e_after[2]}}")
'''

work = tempfile.mkdtemp(prefix="sustain_test_")
src = os.path.join(work, "motion_probe.py")
Path(src).write_text(SCENE_SRC.format(lab=str(HERE)))
cmd = [sys.executable, "-m", "manim", "-ql", "--disable_caching",
       "--media_dir", os.path.join(work, "media"), src, "MotionProbe"]
proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
out = (proc.stdout or "") + (proc.stderr or "")

check("B1 the render succeeds with sustain in the scene", proc.returncode == 0,
      out[-700:])

m = re.search(r"PROBE_ROUNDTRIP moved=([0-9.]+) resized=([0-9.]+)", out)
check("B2 every gesture is round-trip — geometry ends where it started",
      m and float(m.group(1)) < 1e-3 and float(m.group(2)) < 1e-3,
      m.group(0) if m else "marker not found")
check("B3 a mobject no longer on screen is skipped, not animated",
      "PROBE_REMOVED_OK" in out)
check("B4 empty target list and zero time are safe", "PROBE_EDGE_OK" in out)

# The render must actually contain more animation than the entrance alone.
anims = len(re.findall(r"Animation \d+", out))
check("B5 the filler adds real animations to the beat", anims >= 4, f"{anims} animations")

em = re.search(r"PROBE_EMPHASIZE moved=([0-9.]+) resized=([0-9.]+) recolored=(\w+)", out)
check("B6 emphasize() is round-trip and never recolors its target",
      em and float(em.group(1)) < 1e-3 and float(em.group(2)) < 1e-3
      and em.group(3) == "False",
      em.group(0) if em else "marker not found")

if "--keep" in sys.argv:
    print(f"  (kept: {work})")
else:
    shutil.rmtree(work, ignore_errors=True)

failed = [n for n, ok in CHECKS if not ok]
print(f"\n{len(CHECKS) - len(failed)}/{len(CHECKS)} checks passed")
if failed:
    print("FAILED: " + "; ".join(failed))
sys.exit(1 if failed else 0)
