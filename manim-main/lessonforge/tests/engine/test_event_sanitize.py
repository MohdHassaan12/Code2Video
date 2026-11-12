"""Free-text `event` sanitizing acceptance test — no manim, no server, no keys.

The storyboard's legacy `event` field is model-authored, and models write prose
("the ball falls and bounces") as readily as animation calls. That text was
pasted straight into `self.play(...)`:

    self.play(the mobj_scene1_ball falls and then bounces twice, run_time=0.4)

— a SyntaxError that kills the entire scene. A bare element id was worse: it
compiled, then raised at render time because `self.play()` demands an
Animation, not a Mobject.

Pins the contract: every generated script compiles, valid fragments survive,
invalid ones are dropped, and a cue left empty by dropping still gets a body.

Run: .venv/bin/python stem_animation_lab/test_event_sanitize.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lessonforge.transpiler import (  # noqa: E402
    parse_schema_to_base_scene,
    parse_schema_to_scene_scripts,
)

checks = []


def check(name, cond):
    checks.append((name, bool(cond)))
    print(("PASS " if cond else "FAIL ") + name)


ELEMENTS = [
    {"id": "ball", "type": "shape", "content": "circle", "position": [0, 0]},
    {"id": "note", "type": "text", "content": "Note", "safe_zone_alignment": "TOP_CENTER"},
]


def storyboard(*events):
    """One scene per event string, so the per-scene path (>1 scene) engages."""
    return {"visual_storyboard": [
        {"scene_index": i + 1, "description": "t", "elements": ELEMENTS,
         "narration_cues": [{"cue": "c", "event": ev}], "wait_time": 1.0}
        for i, ev in enumerate(events)
    ]}


def compiles(src):
    try:
        compile(src, "<gen>", "exec")
        return True
    except SyntaxError:
        return False


def played(src):
    return [l.strip() for l in src.splitlines() if "self.play(" in l and "run_time=0.4" in l]


# 1-5. Prose in the event field must never reach generated code.
PROSE = [
    ("english prose", "the ball falls and then bounces twice"),
    ("devanagari prose", "गेंद नीचे गिरती है"),
    ("prose split on commas", "ball drops, then it bounces"),
    ("prose after a valid call", "FadeOut(ball), and the scene ends"),
    ("bare element id", "ball"),
]
for name, ev in PROSE:
    code = parse_schema_to_base_scene(storyboard(ev))
    check(f"{name}: script compiles", compiles(code))

# 6. A valid call still survives untouched (the gate must not eat real work).
code = parse_schema_to_base_scene(storyboard("Wiggle(ball)"))
check("valid call survives", any("Wiggle(mobj_scene1_ball)" in p for p in played(code)))

# 7. Partial recovery: the good half of a mixed fragment is kept.
code = parse_schema_to_base_scene(storyboard("FadeOut(ball), and the scene ends"))
plays = played(code)
check("mixed fragment keeps the valid call only",
      any("FadeOut(mobj_scene1_ball)" in p for p in plays)
      and not any("scene ends" in p for p in plays))

# 8. A bare Mobject is dropped — it compiles but raises at render time.
code = parse_schema_to_base_scene(storyboard("ball"))
check("bare mobject never reaches self.play", not played(code))

# 9. `.animate` chains are animations and must survive.
code = parse_schema_to_base_scene(storyboard("ball.animate.shift(RIGHT)"))
check("animate chain survives",
      any(".animate.shift(RIGHT)" in p for p in played(code)))

# 10. An unknown/hallucinated animation class is dropped, not emitted.
code = parse_schema_to_base_scene(storyboard("MakeItSparkle(ball)"))
check("unknown animation class dropped", not played(code))

# 11. A cue emptied by dropping still gets a body (else IndentationError).
code = parse_schema_to_base_scene(storyboard("the ball falls"))
check("emptied cue still compiles with a body", compiles(code) and "pass" in code)

# 12-13. The per-scene path (parallel render) must agree — needs >1 scene.
scripts = parse_schema_to_scene_scripts(storyboard("the ball falls", "Wiggle(ball)"))
check("per-scene scripts generated", len(scripts) == 2)
check("every per-scene script compiles", all(compiles(s) for s in scripts))

# 14. Per-scene path also keeps the valid call.
check("per-scene path keeps valid call",
      any("Wiggle(" in p for s in scripts for p in played(s)))

# 15-19. Cross-scene references must never reach a per-scene script.
# Each per-scene script renders in isolation from a blank canvas, so an event
# targeting an EARLIER scene's element has nothing to act on — and the id→var
# lookup would fall back to the raw id, emitting `FadeOut(container)`: a NameError
# that kills the scene and drags the whole video back to the sequential path.
# Measured 2026-07-20 on the Dalton's-law storyboard (3 of 4 scenes died this way).
XSCENE = {"visual_storyboard": [
    {"scene_index": 1, "description": "t",
     "elements": [{"id": "container", "type": "shape", "shape": "square", "content": ""}],
     "narration_cues": [{"cue": "c", "animation_events": [{"action": "show", "target": "container"}]}],
     "wait_time": 1.0},
    {"scene_index": 2, "description": "t",
     "elements": [{"id": "formula", "type": "math", "content": "P = P_1 + P_2"}],
     "narration_cues": [{"cue": "c", "animation_events": [
         {"action": "hide", "target": "container"},          # scene 1's element
         {"action": "highlight", "target": "formula"},        # this scene's — must survive
     ]}],
     "wait_time": 1.0},
]}
xs = parse_schema_to_scene_scripts(XSCENE)
check("cross-scene fixture emits both scenes", len(xs) == 2)
check("every cross-scene script compiles", all(compiles(s) for s in xs))
check("foreign id never emitted as code", "FadeOut(container)" not in xs[1])
check("own-scene event still emitted", "emphasize(mobj_scene2_formula" in xs[1])
# The master (single-script) path shares one namespace, so the same hide is legitimate there.
check("master path keeps the cross-scene hide",
      "FadeOut(mobj_scene1_container)" in parse_schema_to_base_scene(XSCENE))

# 20. The legacy free-text path gets the same guard.
XLEGACY = {"visual_storyboard": [
    {"scene_index": 1, "description": "t",
     "elements": [{"id": "container", "type": "shape", "shape": "square", "content": ""}],
     "narration_cues": [{"cue": "c", "event": ""}], "wait_time": 1.0},
    {"scene_index": 2, "description": "t",
     "elements": [{"id": "formula", "type": "math", "content": "P = P_1"}],
     "narration_cues": [{"cue": "c", "event": "FadeOut(container), Wiggle(formula)"}],
     "wait_time": 1.0},
]}
xl = parse_schema_to_scene_scripts(XLEGACY)
check("legacy path drops the foreign-id call, keeps the local one",
      "FadeOut(container)" not in xl[1] and "Wiggle(mobj_scene2_formula" in xl[1])

# 21-24. The colour flash was removed from the structured `highlight` action
# (2026-08-15, user review). The legacy free-text path is the back door: a model
# writing `Indicate(ball)` in prose would put the flash straight back into the
# scene, so those class names are no longer whitelisted and get dropped like any
# other unrecognised call.
for flash in ("Indicate", "Circumscribe", "Flash", "FocusOn"):
    flashed = parse_schema_to_base_scene(storyboard(f"{flash}(ball)"))
    check(f"legacy path drops the retired colour flash {flash}(...)",
          f"{flash}(" not in flashed and compiles(flashed))

failed = [n for n, ok in checks if not ok]
print(f"\n{len(checks) - len(failed)}/{len(checks)} checks passed")
if failed:
    for n in failed:
        print(f"  FAILED: {n}")
    sys.exit(1)
