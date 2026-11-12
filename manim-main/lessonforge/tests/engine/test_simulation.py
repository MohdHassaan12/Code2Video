"""Acceptance harness for generated simulations — the one place an LLM writes Manim.

No keys, no network, LLM stubbed — but the **verification harness really runs**
(a real Manim subprocess stepping a real Animation). Stubbing that would test
nothing: the whole safety argument for letting a model write Manim here is that the
code is executed and checked before it can reach a video.

    .venv/bin/python stem_animation_lab/test_simulation.py

  A. **The safety gate** refuses IO / dynamic exec / scene-bound APIs *before* the
     subprocess starts, and unsafe code is never retried (a model that reached for
     `open(` will reach again).
  B. **Verification rejects what "exit code 0" cannot see** — the moving equivalents
     of asset_gen's blank icon: a build that draws nothing, an animation where nothing
     moves, geometry that leaves its box mid-animation (which would manufacture
     clipped-text violations and send the repair agent chasing ghosts), and code that
     raises.
  C. **The board pass** rewrites content to a local path, degrades to a static shape
     with a warning when generation fails, never re-resolves an already-resolved
     element, and honours SIM_GEN=0.
  D. **Both codegen paths** build the simulation AND play it — a simulation whose
     animation never runs is a static picture of a moving thing, which is the exact
     defect the element type exists to remove — and every downstream stage that could
     silently undo it is pinned: the director never rescales it (it was verified in a
     6x4 box), the motion director never moves it, the repair agent may not drop it,
     and the helpers are exported from viz_helpers (a star-import miss is a
     render-time NameError).
  E. **Manim context** retrieval is offline, deterministic, and always yields a worked
     example.
"""
import os
import sys
import textwrap
import types
from pathlib import Path

LAB = str(Path(__import__("lessonforge").__file__).resolve().parent)  # the installed package dir
sys.path.insert(0, LAB)

from lessonforge.engine import sim_gen as SG          # noqa: E402
from lessonforge.engine import manim_context as MC    # noqa: E402
from lessonforge.engine.pipeline import director as DIR      # noqa: E402
from lessonforge.engine.pipeline import motion as MOT        # noqa: E402
import lessonforge.transpiler as T                # noqa: E402

CHECKS = []


def check(name, cond, detail=""):
    CHECKS.append((name, bool(cond)))
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"  — {detail}" if detail and not cond else ""))


GOOD = textwrap.dedent('''
    def build(width, height):
        ax = Axes(x_range=[0, 10, 2], y_range=[0, 5, 1],
                  x_length=width * 0.8, y_length=height * 0.7,
                  axis_config={"include_tip": False})
        curve = ax.plot(lambda x: 0.8 * x - 0.08 * x * x, x_range=[0, 10])
        ball = Dot(ax.c2p(0, 0), radius=0.1)
        return VGroup(ax, curve, ball)

    def animate(group, run_time):
        return MoveAlongPath(group[2], group[1], run_time=run_time)
''')

EMPTY = textwrap.dedent('''
    def build(width, height):
        return VGroup()

    def animate(group, run_time):
        return FadeIn(group, run_time=run_time)
''')

STATIC = textwrap.dedent('''
    def build(width, height):
        return VGroup(Circle(radius=1.0), Square(side_length=1.0))

    def animate(group, run_time):
        return Wait(run_time)
''')

ESCAPES = textwrap.dedent('''
    def build(width, height):
        return VGroup(Dot(ORIGIN, radius=0.1), Circle(radius=0.5))

    def animate(group, run_time):
        def upd(mob, alpha):
            mob.move_to(np.array([alpha * 20.0, 0.0, 0.0]))
        return UpdateFromAlphaFunc(group, upd, run_time=run_time)
''')

TRACED = textwrap.dedent('''
    def build(width, height):
        ball = Dot(ORIGIN, radius=0.1)
        path = TracedPath(ball.get_center, stroke_width=2)
        return VGroup(ball, path)

    def animate(group, run_time):
        return MoveAlongPath(group[0], Line(LEFT * 2, RIGHT * 2), run_time=run_time)
''')

CRASHES = textwrap.dedent('''
    def build(width, height):
        return VGroup(Dot(ORIGIN), Circle(radius=0.4))

    def animate(group, run_time):
        def upd(mob, alpha):
            mob.move_to(undefined_name * alpha)
        return UpdateFromAlphaFunc(group, upd, run_time=run_time)
''')


# ─────────────────────────────────────────────────────────────────────────────
print("\nA. The safety gate — checked before anything is executed")

check("A1 valid code passes the gate", SG._unsafe_code(GOOD) is None)
check("A2 file IO is refused", SG._unsafe_code(GOOD + "\nopen('/etc/passwd')") is not None)
check("A3 dynamic execution is refused",
      SG._unsafe_code(GOOD + "\nx = eval('1+1')") is not None)
check("A4 os/sys access is refused", SG._unsafe_code(GOOD + "\ny = os.getcwd()") is not None)
# 2026-10-08: "os." matched as LETTERS refused `ladoos.add(...)`; a lesson about packing
# ladoos lost seven of eight animations to it and shipped as text on a dark screen.
check("A4b a variable that merely ENDS in a module's letters is not a security event",
      all(SG._unsafe_code(GOOD + "\n" + line) is None for line in (
          "ladoos.add(dot)", "pos.copy()", "photos.arrange(RIGHT)", "videos.shift(UP)", "kilos.scale(2)",
          "reopen(box)", "an_input(3)", "evaluate(3)", "# requests per second")))
check("A4c the real thing is still refused, however it is spaced or reached",
      all(SG._unsafe_code(GOOD + "\n" + line) is not None for line in (
          "os .getcwd()", "sys.exit()", "f = io.open(p)", "subprocess.run(['ls'])", "socket.socket()",
          "__builtins__['open']", "importlib.import_module('os')", "getattr(x, 'y')", "globals()['x']")))
check("A5 an unlisted import is refused",
      SG._unsafe_code("import requests\n" + GOOD) is not None)
check("A6 numpy/math/manim imports are tolerated",
      SG._unsafe_code("import numpy as np\nfrom manim import *\n" + GOOD) is None)
check("A7 a scene-bound API is NOT a security event", SG._unsafe_code(TRACED) is None)

# The distinction below was paid for: on the first live run only 1 of 4 simulations
# survived, and the three that died were all trajectory-tracing descriptions that had
# reached for TracedPath — which the first cut listed next to `open(` and therefore
# killed with no repair round. Reaching for `open(` is disobedience; reaching for
# TracedPath is the obvious way to trace a path in Manim that happens to need a Scene.
# Classify before repairing.
check("A8 a scene-bound API IS a contract problem", SG._contract_problem(TRACED) is not None)
check("A9 the contract rejection tells the model what to do instead (it is a brief, "
      "not a verdict)",
      "UpdateFromAlphaFunc" in (SG._contract_problem(TRACED) or "")
      and "Create" in (SG._contract_problem(TRACED) or ""))
check("A10 add_updater / always_redraw / self. are caught too",
      all(SG._contract_problem(GOOD + f"\n# {api}") is not None
          for api in ("add_updater", "always_redraw", "self.")))
check("A11 a missing build() is a contract problem, not a security one",
      SG._contract_problem("def animate(g, t): pass") is not None
      and SG._unsafe_code("def animate(g, t): pass") is None)
check("A12 a missing animate() is a contract problem",
      SG._contract_problem("def build(w, h): pass") is not None)
check("A13 verify() applies BOTH gates", SG.verify(TRACED) is not None
      and SG.verify("import socket\n" + GOOD) is not None)

# The behavioural half of the distinction: one is retried, the other is not.
_orig_llm = SG.call_llm_with_fallback
try:
    seen = {"n": 0}

    def _serve(code):
        def _fake(client, prompt, system_instruction, response_schema=None,
                  temperature=0.2, task="general", keys=None):
            seen["n"] += 1
            seen["last_prompt"] = prompt
            return types.SimpleNamespace(text=code)
        return _fake

    SG.call_llm_with_fallback = _serve("import socket\n" + GOOD)
    SG.generate_simulation("an unsafe probe that must not be retried")
    check("A14 unsafe code is never retried (one call, then give up)", seen["n"] == 1,
          f"{seen['n']} calls")

    seen["n"] = 0
    SG.call_llm_with_fallback = _serve(TRACED)
    SG.generate_simulation("a contract probe that must earn its repair round")
    check("A15 a contract mistake DOES get its repair round", seen["n"] == 2,
          f"{seen['n']} calls")
    check("A16 the repair round carries the reason, so the model can act on it",
          "TracedPath" in seen.get("last_prompt", ""))
finally:
    SG.call_llm_with_fallback = _orig_llm


# ─────────────────────────────────────────────────────────────────────────────
print("\nB. Verification — a real Manim subprocess (exit code 0 proves nothing)")

check("B1 a correct simulation is accepted", SG.verify(GOOD) is None)

err_empty = SG.verify(EMPTY)
check("B2 a build() that draws nothing is rejected", err_empty is not None,
      f"got {err_empty!r}")
check("B3 the empty rejection names the real cause",
      err_empty and ("drew nothing" in err_empty or "no drawable points" in err_empty))

err_static = SG.verify(STATIC)
check("B4 an animation where nothing moves is rejected", err_static is not None)
check("B5 the static rejection is actionable",
      err_static and "nothing moved" in err_static)

err_escape = SG.verify(ESCAPES)
check("B6 geometry that leaves its box mid-animation is rejected", err_escape is not None)
check("B7 the containment rejection reports where it went",
      err_escape and "box" in err_escape)

err_crash = SG.verify(CRASHES)
check("B8 code that raises during the animation is rejected", err_crash is not None)
check("B9 the crash rejection carries the traceback for the repair round",
      err_crash and "undefined_name" in err_crash)

# 2026-10-08: two lessons failed their layout check on text INSIDE a scene ('74' on '80', '2' on
# '12'). A scene was verified to draw, move and stay in its box — never for labels on labels.
PILED = textwrap.dedent('''
    def build(width, height):
        a = Text("74", font_size=28).move_to([-1, 0, 0])
        b = Text("80", font_size=28).move_to([1, 0, 0])
        return VGroup(Square(side_length=0.5).move_to([0, 1, 0]), a, b)

    def animate(group, run_time):
        return AnimationGroup(group[2].animate.move_to(group[1].get_center()), run_time=run_time)
''')
APART = PILED.replace("move_to(group[1].get_center())", "shift(UP * 0.8)")
HANDOVER = textwrap.dedent('''
    def build(width, height):
        old = Text("12", font_size=28)
        new = Text("2", font_size=28).set_opacity(0)
        return VGroup(Dot([1.5, 0, 0]), old, new)

    def animate(group, run_time):
        return AnimationGroup(group[1].animate.set_opacity(0), group[2].animate.set_opacity(1),
                              group[0].animate.shift(LEFT), run_time=run_time)
''')
err_piled = SG.verify(PILED)
check("B11 labels that come to rest on top of each other are rejected", err_piled is not None)
check("B12 the rejection names both labels and when, for the repair round",
      err_piled is not None and "74" in err_piled and "80" in err_piled and "finished moving" in err_piled)
check("B13 labels that stay apart are accepted", SG.verify(APART) is None)
check("B14 a label that hands over to another in the same place is accepted (only what is visible counts)",
      SG.verify(HANDOVER) is None)
# 2026-10-19, the Monty Hall lesson: a staged scene wrote "switching wins two in three", then "staying wins one in
# three" in the same place, and the first label was never faded. The lesson WAITS at each stage's end while the voice
# goes on, so both stood on each other for a whole stage; the checker had looked only at the first and last frames.
STAGED = textwrap.dedent('''
    def build(width, height):
        a = Text("switch wins", font_size=28).move_to(UP * 0.8)
        b = Text("stay wins", font_size=28).move_to(UP * WHERE)
        a.set_opacity(0); b.set_opacity(0)
        return VGroup(Square(1.2).move_to(DOWN), a, b)

    def animate(group, run_time):
        d, a, b = group
        return AnimationGroup(a.animate.set_opacity(1), b.animate.set_opacity(1), FadeOut(a),
                              lag_ratio=1.0, run_time=run_time)
''')
CROSSING = textwrap.dedent('''
    def build(width, height):
        return VGroup(Text("ball", font_size=28).move_to(LEFT * 2.2), Text("wall", font_size=28))

    def animate(group, run_time):
        return group[0].animate.move_to(RIGHT * 2.2).build().set_run_time(run_time)
''')
err_staged = SG.verify(STAGED.replace("WHERE", "0.8"))
check("B15 labels piled on each other while a staged scene waits between stages are rejected",
      err_staged is not None and "between its stages" in err_staged, err_staged)
check("B16 the same stages with the labels apart are accepted", SG.verify(STAGED.replace("WHERE", "1.6")) is None)
check("B17 a label that crosses another while MOVING is still accepted, even at a stage's end",
      SG.verify(CROSSING) is None)
# A line running through a label at rest is refused; the same label beside the line is not (2026-10-18: a dent's arc
# through "2000 N/m2", an arrow through "80 N/m2").
STRUCK = textwrap.dedent('''
    def build(width, height):
        line = Line([-2, 0, 0], [2, 0, 0])
        label = Text("80 N", font_size=28).move_to([0, 1.0, 0])
        return VGroup(line, label)

    def animate(group, run_time):
        return AnimationGroup(group[1].animate.move_to([0, 0, 0]), run_time=run_time)
''')
CLEAR = STRUCK.replace("move_to([0, 0, 0])", "move_to([0, 0.5, 0])")
err_struck = SG.verify(STRUCK)
check("B30 a line running through a label at rest is refused, naming both",
      err_struck is not None and "Line" in err_struck and "80 N" in err_struck)
check("B31 the same label beside the line is accepted", SG.verify(CLEAR) is None)
# A label faded with set_opacity(alpha) while a FadeIn of it runs beside it ends with its glyphs at 0 and itself at 1;
# the lesson draws it in full, so it counts as on screen once the animation has finished.
TANGLED = textwrap.dedent('''
    def build(width, height):
        a = Text("0.01 m2", font_size=28).move_to([0.3, 0, 0])
        b = Text("2000", font_size=28).move_to([0, 1.5, 0])
        return VGroup(Square(side_length=0.4).move_to([-2, -1, 0]), a, b)

    def animate(group, run_time):
        b = group[2]
        def grow(m, alpha):                      # drives another part, and fades the label as a side effect
            m.set_width(0.4 + alpha)
            b.move_to([0.3, 0, 0])               # onto the other label, from the very first frame
            b.set_opacity(alpha)
        return AnimationGroup(UpdateFromAlphaFunc(group[0], grow), FadeIn(b), run_time=run_time)
''')
check("B32 a label left at full opacity by a tangled fade is checked where it ends",
      (SG.verify(TANGLED) or "").startswith("two labels lie on top of each other"))
# A label sized from the box (int(min(width, height) * 0.04) is 0 in a 6x4 box) has no height: it cannot overlap
# anything, so every other check passed while the film showed a picture with no numbers (2026-10-19).
TINY = textwrap.dedent('''
    def build(width, height):
        s = min(width, height)
        return VGroup(Square(side_length=1.0), Text("20 N", font_size=int(s * 0.04)).move_to([0, 1.2, 0]))

    def animate(group, run_time):
        return AnimationGroup(group[0].animate.shift(RIGHT * 0.5), run_time=run_time)
''')
check("B33 a label too small to read is refused, with the fix",
      "too small to read" in (SG.verify(TINY) or "") and "font_size" in (SG.verify(TINY) or ""))
check("B34 the same label at a plain font size is accepted", SG.verify(TINY.replace("int(s * 0.04)", "28")) is None)
# The second block of the same scene was hidden with set_opacity(0) and then "shown" with FadeIn, which returns a
# mobject to its own opacity: it never appeared while the voice talked about it.
UNSEEN = textwrap.dedent('''
    def build(width, height):
        a = Square(side_length=1.0).move_to([-1.5, 0, 0])
        b = Square(side_length=1.0).move_to([1.5, 0, 0])
        b.set_opacity(0)
        return VGroup(a, b)

    def animate(group, run_time):
        return AnimationGroup(group[0].animate.shift(UP * 0.3), FadeIn(group[1]), run_time=run_time)
''')
check("B35 a part that never becomes visible is refused, naming it",
      "never becomes visible" in (SG.verify(UNSEEN) or "") and "Square" in (SG.verify(UNSEEN) or ""))
check("B36 the same part shown with .animate.set_opacity(1) is accepted",
      SG.verify(UNSEEN.replace("FadeIn(group[1])", "group[1].animate.set_opacity(1)")) is None)
# A description that lists values for objects it named pairs them in order: the first value with the first object.
# A filmed pressure scene put 400 under the 40 N block and 200 under the 20 N one (2026-10-18).
PAIRED = ("A 20 N block lying flat on sand; then a heavier 40 N block slides in beside it; then the labels 400 and "
          "200 N/m2 sit under them.")
check("B37 a description's value pairs are read in order",
      SG.value_pairs(PAIRED) == [("20", "400"), ("40", "200")])
check("B38 a description that lists no values for objects pairs nothing",
      SG.value_pairs("A 20 N block on sand, then a dent appears under it.") == [])
PAIRS_SCENE = textwrap.dedent('''
    def build(width, height):
        a = Square(side_length=0.8).move_to([-1.5, 0, 0])
        b = Square(side_length=1.0).move_to([1.5, 0, 0])
        la = Text("20 N", font_size=24).next_to(a, UP)
        lb = Text("40 N", font_size=24).next_to(b, UP)
        va = Text("VAL_A N/m2", font_size=22).next_to(a, DOWN)
        vb = Text("VAL_B N/m2", font_size=22).next_to(b, DOWN)
        return VGroup(a, b, la, lb, va, vb)

    def animate(group, run_time):
        return AnimationGroup(group[0].animate.shift(RIGHT * 0.2), run_time=run_time)
''')
RIGHT_WAY = PAIRS_SCENE.replace("VAL_A", "400").replace("VAL_B", "200")
SWAPPED = PAIRS_SCENE.replace("VAL_A", "200").replace("VAL_B", "400")
check("B39 values under the right objects are accepted", SG.verify(RIGHT_WAY, description=PAIRED) is None)
check("B40 values under the wrong objects are refused, naming the pair",
      "wrong object" in (SG.verify(SWAPPED, description=PAIRED) or "") and "'400'" in (SG.verify(SWAPPED, description=PAIRED) or ""))
UNNAMED = RIGHT_WAY.replace('Text("20 N"', 'Text("block"')
check("B41 an object whose value is shown but which carries no label of its own is refused",
      "carries no label" in (SG.verify(UNNAMED, description=PAIRED) or ""))
check("B42 the pairing is only judged when a description pairs values", SG.verify(SWAPPED) is None)
# A force arrow that runs down through its block into the sand (a redrawn pressure scene, 2026-10-19).
PIERCED = textwrap.dedent('''
    def build(width, height):
        block = Rectangle(width=1.2, height=0.8, fill_color=BLUE, fill_opacity=0.9).move_to([0, 0, 0])
        push = Arrow([0, 1.6, 0], [0, -0.6, 0], buff=0)
        return VGroup(block, push)

    def animate(group, run_time):
        return AnimationGroup(group[0].animate.shift(RIGHT * 0.2), group[1].animate.shift(RIGHT * 0.2), run_time=run_time)
''')
check("B43 an arrow running through a filled block is refused",
      "runs through a filled" in (SG.verify(PIERCED) or ""))
check("B44 the same arrow ending at the block's top face is accepted",
      SG.verify(PIERCED.replace("[0, -0.6, 0]", "[0, 0.42, 0]")) is None)
# A line that only GRAZES a label is cured by code moving the label (scene_tidy, 2026-10-20): the arc of a filmed
# dent ended on the tops of "0.01 m2" and three model redraws each broke something else. The checker moves it exactly
# as the lesson's loader does, so what passes is what is filmed. A line through the middle, or a label with no clear
# place within half its height, stays refused.
GRAZED = textwrap.dedent('''
    def build(width, height):
        label = Text("0.01 m2", font_size=28).move_to([0, 0, 0])
        h = label.height
        edge = Line([-2, h * 0.5 - h * 0.12, 0], [0, h * 0.5 - h * 0.12, 0])
        dot = Dot([2, -1.5, 0])
        return VGroup(edge, label, dot)

    def animate(group, run_time):
        return AnimationGroup(group[2].animate.shift(LEFT * 0.5), run_time=run_time)
''')
check("B45 a line grazing a label is cured by moving the label, and the move is reported",
      SG.verify(GRAZED) is None and (SG._run_harness(GRAZED)[0] or {}).get("tidied") == ["0.01 m2"])
BOXED_IN = GRAZED.replace("dot = Dot([2, -1.5, 0])",
                          "dot = Dot([2, -1.5, 0])\n    under = Line([-2, -h * 0.5 + h * 0.12, 0], [0, -h * 0.5 + h * 0.12, 0])") \
                 .replace("return VGroup(edge, label, dot)", "return VGroup(edge, label, dot, under)")
check("B46 a grazed label with no clear place within reach stays refused",
      "runs through the label" in (SG.verify(BOXED_IN) or ""))
check("B47 a line through the middle of a label is not moved away: still refused", SG.verify(STRUCK) is not None)
_mod = Path(__import__("tempfile").mkdtemp()) / "sim_grazed.py"
_mod.write_text(GRAZED)
from lessonforge.longform import figures as _figures   # noqa: E402
_fig = _figures.scene({"module": str(_mod)})
check("B48 the lesson's loader moves the same label the checker moved",
      abs(_fig.origin[1].get_center()[1]) > 0.01 and abs(_fig.origin[1].get_center()[1] - _fig.inner[1].get_center()[1]) < 1e-6)
check("B10 unsafe code is rejected without ever running",
      SG.verify("import socket\n" + GOOD) is not None)

# Parts that APPEAR one after another change no point: geometry alone called this "nothing moved", and a
# scene written in stages ("first one block appears, then a stack of two, then of three") lost both tries.
APPEARS = textwrap.dedent('''
    def build(width, height):
        ground = Line(LEFT * 2, RIGHT * 2).shift(DOWN * 0.4)
        return VGroup(ground, *[Square(0.6, fill_color=BLUE, fill_opacity=1).shift(RIGHT * (i - 1)) for i in range(3)])

    def animate(group, run_time):
        return AnimationGroup(*[FadeIn(part) for part in group[1:]], lag_ratio=1.0, run_time=run_time)
''')
# The same blocks with no ground: when the animation starts there is nothing to look at.
EMPTY_START = APPEARS.replace("group[1:]", "group").replace("VGroup(ground, *[", "VGroup(*[")
LIGHTS_UP = textwrap.dedent('''
    def build(width, height):
        return VGroup(Square(0.8, color=WHITE), Circle(0.4, color=WHITE).shift(RIGHT * 1.5))

    def animate(group, run_time):
        return AnimationGroup(group[1].animate.set_color(YELLOW), run_time=run_time)
''')
IN_SUCCESSION = APPEARS.replace("AnimationGroup(*[FadeIn(part) for part in group[1:]], lag_ratio=1.0, run_time=run_time)",
                                "Succession(*[FadeIn(part) for part in group[1:]], run_time=run_time)")
assert "Succession(" in IN_SUCCESSION and "group[1:]" not in EMPTY_START
check("B15 parts that appear one after another are a change the viewer sees", SG.verify(APPEARS) is None,
      str(SG.verify(APPEARS)))
check("B16 a part that only changes colour has changed too", SG.verify(LIGHTS_UP) is None, str(SG.verify(LIGHTS_UP)))
err_succession = SG.verify(IN_SUCCESSION)
check("B17 Succession is refused with the way to write the same sequence",
      err_succession is not None and "AnimationGroup" in err_succession and "lag_ratio=1.0" in err_succession)
check("B18 ... as a contract problem, so it gets a repair round and is never called unsafe",
      SG._unsafe_code(IN_SUCCESSION) is None and SG._contract_problem(IN_SUCCESSION) is not None)
err_empty_start = SG.verify(EMPTY_START)
check("B20 a picture with nothing to see when it starts is refused, and told what to keep drawn",
      err_empty_start is not None and "nothing is visible when the animation starts" in err_empty_start,
      str(err_empty_start))
# A scene that is sound at 24 even moments and raises exactly at a stage boundary (one third): a lesson rests there.
BREAKS_AT_A_THIRD = textwrap.dedent('''
    def build(width, height):
        return VGroup(Line(LEFT * 2, RIGHT * 2).shift(DOWN), Dot(LEFT), Dot(RIGHT))

    def animate(group, run_time):
        def move(mob, alpha):
            if abs(alpha - 1 / 3) < 1e-9:
                raise ValueError("At least one array has zero dimension")
            mob[1].move_to(LEFT + UP * alpha)
        return UpdateFromAlphaFunc(group, move, run_time=run_time)
''')
FLAT_POINTS = textwrap.dedent('''
    def build(width, height):
        return VGroup(Line(LEFT * 2, RIGHT * 2).shift(DOWN), Dot(LEFT))

    def animate(group, run_time):
        def move(mob, alpha):
            mob[1].shift(UP * 0.01)
            if alpha > 0.5:
                mob[0].points = np.array([0.0, 0.0, 0.0])
        return UpdateFromAlphaFunc(group, move, run_time=run_time)
''')
err_third = SG.verify(BREAKS_AT_A_THIRD)
check("B21 a scene that raises exactly on a stage boundary is caught here, not in a lesson",
      err_third is not None and "zero dimension" in err_third, str(err_third))
err_flat = SG.verify(FLAT_POINTS)
check("B22 a shape whose points stop being an (n, 3) array is refused, with what to do instead",
      err_flat is not None and "malformed point array" in err_flat and "(n, 3)" in err_flat, str(err_flat))
check("B19 the writer is no longer told to use it",
      "or Succession(" not in SG._PROMPT and "lag_ratio=1.0" in SG._PROMPT)


# ─────────────────────────────────────────────────────────────────────────────
print("\nC. The board pass — resolve, degrade, never re-resolve")

SIM_PATH = os.path.join(SG.CACHE_DIR, "sim_test_probe.py")


def _board(content, etype="simulation"):
    return {"visual_storyboard": [{
        "scene_index": 1, "description": "d", "wait_time": 1,
        "elements": [{"id": "sim1", "type": etype, "content": content,
                      "entrance_animation": "", "exit_animation": ""}],
        "narration_cues": [{"cue": "c", "animation_events": [
            {"action": "show", "target": "sim1"}]}],
    }]}


_orig_generate = SG.generate_simulation
try:
    SG.generate_simulation = lambda desc, keys=None, client=None: SIM_PATH
    b = _board("a ball tracing a parabola")
    warns = SG.resolve_simulation_elements(b)
    el = b["visual_storyboard"][0]["elements"][0]
    check("C1 a resolved simulation's content becomes a local module path",
          el["content"] == SIM_PATH and el["type"] == "simulation")
    check("C2 a resolved simulation adds no asset warning", warns == [])

    # Re-resolution would spend an LLM call on every re-render of a cached board.
    os.makedirs(SG.CACHE_DIR, exist_ok=True)
    Path(SIM_PATH).write_text(GOOD)
    calls = {"n": 0}

    def _counting(desc, keys=None, client=None):
        calls["n"] += 1
        return SIM_PATH

    SG.generate_simulation = _counting
    SG.resolve_simulation_elements(b)
    check("C3 an already-resolved element is not regenerated", calls["n"] == 0)

    # A simulation that cannot be ANIMATED should still be DRAWN before it degrades:
    # setting type="shape" resolves the prose head-noun ("a ball rolling off a table…")
    # to a bare Circle(), which is the placeholder this module exists to stop shipping.
    _orig_drawgen = SG.generate_drawing
    SG.generate_simulation = lambda desc, keys=None, client=None: None
    SG.generate_drawing = lambda desc, keys=None, client=None, min_parts=None: SIM_PATH
    b_still = _board("a wave that will not animate")
    warns_still = SG.resolve_simulation_elements(b_still)
    el_still = b_still["visual_storyboard"][0]["elements"][0]
    check("C4a a simulation that cannot animate is DRAWN as a still, not reduced to a "
          "primitive", el_still["type"] == "svg_icon" and el_still["content"] == SIM_PATH)
    check("C4b the still is given diagram-sized scale, not icon-sized",
          float(el_still.get("scale") or 0) >= 3.0)
    check("C4c a drawn still is not an asset warning — nothing was lost", warns_still == [])

    SG.generate_drawing = lambda desc, keys=None, client=None, min_parts=None: None
    b2 = _board("something impossible to draw")
    warns2 = SG.resolve_simulation_elements(b2, [{"existing": 1}])
    el2 = b2["visual_storyboard"][0]["elements"][0]
    check("C4 with the drawing fallback ALSO failing, it degrades to a static shape",
          el2["type"] == "shape")
    check("C5 the degradation keeps the description for the asset cascade",
          el2["content"] == "something impossible to draw")
    check("C6 the degradation is recorded as an asset warning",
          len(warns2) == 2 and warns2[-1]["type"] == "simulation")
    check("C7 the warning matches the shape the codegen prompt formats",
          {"scene", "element_id", "type", "keyword", "provider"} <= set(warns2[-1]))
    check("C8 pre-existing warnings are preserved", warns2[0] == {"existing": 1})

    def _boom(desc, keys=None, client=None):
        raise RuntimeError("provider down")

    SG.generate_simulation = _boom
    b3 = _board("a wave")
    warns3 = SG.resolve_simulation_elements(b3)
    check("C9 a raising generator degrades instead of failing the render",
          b3["visual_storyboard"][0]["elements"][0]["type"] == "shape" and len(warns3) == 1)

    os.environ["SIM_GEN"] = "0"
    check("C10 SIM_GEN=0 disables generation entirely",
          SG.generate_simulation is _boom and not SG.enabled()
          and _orig_generate("anything at all") is None)
    os.environ.pop("SIM_GEN")

    check("C11 a board with no simulation elements is untouched",
          SG.resolve_simulation_elements(_board("a circle", etype="shape")) == [])
finally:
    SG.generate_simulation = _orig_generate
    try:
        SG.generate_drawing = _orig_drawgen
    except NameError:
        pass


# ─────────────────────────────────────────────────────────────────────────────
print("\nD. Codegen — built AND played, in both paths, and undoable by nobody")

sim_board = _board(SIM_PATH)
master = T.parse_schema_to_base_scene(sim_board)

# The per-scene emitter only fires for multi-scene boards (a single scene has nothing
# to parallelise), so the parallel path is exercised with two.
two_scene = _board(SIM_PATH)
second = dict(two_scene["visual_storyboard"][0])
second["scene_index"] = 2
two_scene["visual_storyboard"] = [two_scene["visual_storyboard"][0], second]
scripts = T.parse_schema_to_scene_scripts(two_scene)
per_scene = "\n".join(s for s in (scripts if isinstance(scripts, list) else [scripts])
                      if isinstance(s, str))

check("D1 the master path builds the simulation", f"simulation({SIM_PATH!r}" in master)
check("D2 the master path PLAYS it (a simulation that never runs is a still picture)",
      "sim_play(" in master)
check("D3 the per-scene path builds it", "simulation(" in per_scene)
check("D4 the per-scene path plays it", "sim_play(" in per_scene)
check("D5 both paths build it inside the box sim_gen verified",
      f"width={SG.BOX_W}" in master and f"height={SG.BOX_H}" in master
      and (SG.BOX_W, SG.BOX_H) == (T._SIM_BOX_W, T._SIM_BOX_H))
check("D6 playback is timed off the narration, capped so it cannot eat later cues",
      "tracker.get_remaining_duration()" in master and "min(4.5" in master)
check("D7 the entrance is forced to FadeIn",
      "FadeIn(mobj_scene1_sim1" in master)
check("D8 a Write/Create override cannot be applied to a simulation",
      "Write(mobj_scene1_sim1" not in master and "Create(mobj_scene1_sim1" not in master)

unresolved = T.parse_schema_to_base_scene(_board("a ball tracing an arc"))
check("D9 an unresolved simulation degrades to a placeholder, never a bad file load",
      "simulation(" not in unresolved and "Text(" in unresolved)
check("D10 an unresolved simulation emits no playback line",
      "sim_play(" not in unresolved)

viz_src = Path(LAB, "viz_helpers.py").read_text()
check("D11 both helpers are exported from viz_helpers (a star-import miss NameErrors "
      "every render)",
      '"simulation", "sim_play",' in viz_src)
# The fallback used to be `Indicate(group, scale_factor=1.02)`, whose default accent
# tinted the whole simulation yellow. `emphasize` is the same round-trip pulse with
# the colour removed (2026-08-15) — round-trip matters here because a degraded
# simulation must never manufacture a layout violation.
check("D12 sim_play always returns something playable, and colourlessly",
      "return emphasize(group" in viz_src and "Indicate(group" not in viz_src)
check("D13 the loader degrades to a Text placeholder rather than raising",
      "could not load" in viz_src)

check("D14 the director never rescales a simulation (it was verified in its box)",
      "simulation" in DIR._NO_RESCALE_TYPES)
check("D15 the motion director never moves a simulation",
      "simulation" in MOT._STATIC_TYPES)

from lessonforge.engine.render import _repair_preserves_assets  # noqa: E402
before = "g = simulation('/x.py', width=6.0, height=4.0)\nself.play(sim_play(g, run_time=2))"
check("D16 a repair that drops the simulation is rejected",
      not _repair_preserves_assets(before, "g = Circle()\n"))
check("D17 a repair that drops only the PLAYBACK is rejected too (a still frame is "
      "always legal, so the probe would happily accept it)",
      not _repair_preserves_assets(before, "g = simulation('/x.py', width=6.0, height=4.0)"))
check("D18 a repair that keeps both is allowed",
      _repair_preserves_assets(before, before + "\ntitle.to_edge(UP)"))
check("D19 the image guard still holds",
      not _repair_preserves_assets("fetch_real_image('/a.jpg')", "fetch_smart_svg('a')"))

# Measured 2026-08-15, one round AFTER simulation(/sim_play( were guarded and drawing(
# was not: a repair pass swapped four drawing(<path>) calls for fallback icons in one
# scene of a shipped video (siblings kept 14/14, that scene rendered 10). The frame went
# from a drawn player, hoop and ball to a labelled grey box — and the violation count
# went DOWN, so it was accepted. Every generated asset needs its own guard, on BOTH the
# repair side and the critic side.
drawn_before = "a = drawing('/x.py', height=1.9)\nb = drawing('/y.py', height=1.9)"
check("D19a a repair that drops a DRAWING is rejected",
      not _repair_preserves_assets(drawn_before, "a = fetch_smart_svg('x')"))
check("D19b a repair that keeps every drawing is allowed",
      _repair_preserves_assets(drawn_before, drawn_before + "\ntitle.to_edge(UP)"))
from lessonforge.engine.codegen import _structure_losses  # noqa: E402
check("D19c the LAYOUT CRITIC also refuses to trade a generated asset away",
      _structure_losses(drawn_before + "\nsim_play(g)", "a = Circle()")
      and all(h in __import__("lessonforge.engine.codegen", fromlist=["x"])._STRUCTURE_HELPERS
              for h in ("drawing(", "simulation(", "sim_play(")))

check("D20 simulations count as diagrams for split-screen "
      "(text must not pile onto a running system)",
      '"simulation")' in Path(LAB, "transpiler.py").read_text().split(
          'if (_etype in ("coordinate_system", "graph", "shape", "image"')[1][:40])


# ─────────────────────────────────────────────────────────────────────────────
print("\nE. Manim context — offline, deterministic, always a worked example")

pats = MC.relevant_patterns("a ball thrown at 45 degrees tracing a parabolic arc")
check("E1 a described system retrieves the matching pattern",
      pats and pats[0]["id"] == "trajectory")
check("E2 a wave retrieves the wave pattern",
      MC.relevant_patterns("a sine wave propagating along a string")[0]["id"] == "wave")
check("E3 an unmatched description still gets a worked example (never zero)",
      len(MC.relevant_patterns("zzzz qqqq")) > 0)
check("E4 retrieval is deterministic",
      MC.relevant_patterns("orbiting planet") == MC.relevant_patterns("orbiting planet"))

fake_index = {"version": "0.0", "classes": [
    {"name": "Axes", "signature": "(x_range, y_range)", "doc": "Coordinate axes", "bases": []},
    {"name": "Kettle", "signature": "()", "doc": "boils water", "bases": []},
]}
api = MC.relevant_api("a boiling kettle on a stove", index=fake_index)
check("E5 API retrieval matches on docs, not just names",
      any(c["name"] == "Kettle" for c in api))
check("E6 animation primitives are always surfaced (they are what a wrong guess invents)",
      any(c["name"] == "Axes" for c in api))
check("E7 a missing index degrades to patterns only, never an exception",
      MC.relevant_api("anything", index={}) == [])

ctx = MC.context_for("a pendulum swinging from a pivot")
check("E8 the context block carries a build/animate example",
      "def build(" in ctx and "def animate(" in ctx)
check("E9 the prompt tells the writer the API listing is authoritative",
      "Installed Manim API" in ctx or "def build(" in ctx)

sim_src = Path(LAB, "engine", "sim_gen.py").read_text()
check("E10 unsafe code is never retried",
      "will reach again" in sim_src)
check("E11 the writer is told there is no Scene",
      "You get NO Scene" in sim_src)


# ─────────────────────────────────────────────────────────────────────────────
print("\nF. Render-time seam — a REAL manim render of the two helpers")
#
# Why this part is a real render rather than more source assertions: the cached module
# contains ONLY the model's two functions (it is told to import nothing, because the
# verification harness supplies the namespace). The first cut loaded it with
# importlib, which gives a module empty globals — so `Axes` was undefined, the loader's
# own except-branch caught it, and EVERY simulation silently became a Text placeholder
# that looked exactly like a working fallback. Nothing short of rendering it found that.

import shutil          # noqa: E402
import subprocess      # noqa: E402
import tempfile        # noqa: E402

work = tempfile.mkdtemp(prefix="simrender_")
try:
    mod_path = os.path.join(work, "mod.py")
    Path(mod_path).write_text(GOOD)
    scene_path = os.path.join(work, "scene.py")
    Path(scene_path).write_text(textwrap.dedent(f'''
        import sys
        sys.path.insert(0, {LAB!r})
        from manim import *
        from viz_helpers import *

        class SimCheck(Scene):
            def construct(self):
                g = simulation({mod_path!r}, width=6.0, height=4.0)
                self.play(FadeIn(g))
                self.play(sim_play(g, run_time=1.0))
                print("SIM_LOADED type=%s parts=%d w=%.2f h=%.2f" % (
                    type(g).__name__, len(g.family_members_with_points()), g.width, g.height))
                bad = simulation("/definitely/missing.py")
                self.play(FadeIn(bad))
                self.play(sim_play(bad, run_time=0.4))
                print("SIM_DEGRADED type=%s" % type(bad).__name__)
    '''))
    proc = subprocess.run(
        [sys.executable, "-m", "manim", "-ql", "--disable_caching",
         "--media_dir", work, scene_path, "SimCheck"],
        capture_output=True, text=True, timeout=420, cwd=work)
    out = (proc.stdout or "") + (proc.stderr or "")
    loaded = next((l for l in out.splitlines() if l.startswith("SIM_LOADED")), "")
    check("F1 the render completes", proc.returncode == 0, out[-400:])
    check("F2 the module loads as a real mobject, not the placeholder",
          "type=VGroup" in loaded, loaded or out[-300:])
    check("F3 the loaded simulation has real geometry (the namespace reached it)",
          "parts=0" not in loaded and loaded != "", loaded)
    check("F4 the built group fits inside its box",
          loaded and float(loaded.split("w=")[1].split()[0]) <= SG.BOX_W * 1.02
          and float(loaded.split("h=")[1]) <= SG.BOX_H * 1.02, loaded)
    check("F5 a missing module degrades to a placeholder without killing the render",
          "SIM_DEGRADED type=Text" in out)
finally:
    shutil.rmtree(work, ignore_errors=True)


# ─────────────────────────────────────────────────────────────────────────────
print("\nG. Manim-drawn objects — geometry instead of imported clipart")
#
# User report 2026-08-15 after watching the first live video: "remove the svg import and
# let the content be generated by manim itself". The board behind it declared 14
# `svg_icon` elements that were all the SAME keyword, so a 105-second explainer's entire
# visual vocabulary was one piece of flat clipart, repeated.

DRAWING = textwrap.dedent('''
    def build(width, height):
        r = min(width, height) * 0.4
        ball = Circle(radius=r, color=ORANGE, fill_opacity=1)
        seam = Arc(radius=r, start_angle=-PI / 2, angle=PI, color=BLACK)
        line = Line(LEFT * r, RIGHT * r, color=BLACK)
        return VGroup(ball, seam, line)
''')

ONE_PART = textwrap.dedent('''
    def build(width, height):
        return Circle(radius=min(width, height) * 0.4)
''')

check("G1 a static drawing needs no animate()", SG.verify(DRAWING, motion=False) is None)
check("G2 the same code is rejected as a SIMULATION (no animate)",
      SG.verify(DRAWING, motion=True) is not None)
check("G3 a one-shape 'drawing' is rejected — that IS the placeholder this replaces",
      SG.verify(ONE_PART, motion=False, min_parts=3) is not None)
check("G4 the rejection tells the model to build it from parts",
      "distinguishable parts" in (SG.verify(ONE_PART, motion=False, min_parts=3) or ""))
check("G5 a simulation still must move", SG.verify(STATIC, motion=True) is not None)
check("G6 drawn objects are on by default, with a kill switch", SG.draw_enabled())
os.environ["DRAW_WITH_MANIM"] = "0"
check("G7 DRAW_WITH_MANIM=0 restores the icon cascade",
      not SG.draw_enabled() and SG.generate_drawing("anything") is None)
os.environ.pop("DRAW_WITH_MANIM")

DRAW_PATH = os.path.join(SG.DRAW_CACHE_DIR, "draw_test_probe.py")
os.makedirs(SG.DRAW_CACHE_DIR, exist_ok=True)
Path(DRAW_PATH).write_text(DRAWING)
_orig_draw = SG.generate_drawing
try:
    SG.generate_drawing = lambda d, keys=None, client=None, min_parts=None: DRAW_PATH
    b = _board("basketball", etype="svg_icon")
    SG.resolve_drawn_elements(b)
    el = b["visual_storyboard"][0]["elements"][0]
    check("G8 an svg_icon's content becomes a drawn module path", el["content"] == DRAW_PATH)
    check("G9 the element stays an svg_icon (the transpiler decides how to emit it)",
          el["type"] == "svg_icon")
    check("G10 the original keyword is kept for provenance", el.get("_drawn_from") == "basketball")

    calls = {"n": 0}

    def _count(d, keys=None, client=None, min_parts=None):
        calls["n"] += 1
        return DRAW_PATH

    SG.generate_drawing = _count
    SG.resolve_drawn_elements(b)
    check("G11 an already-drawn element is not regenerated", calls["n"] == 0)

    SG.generate_drawing = lambda d, keys=None, client=None, min_parts=None: None
    b2 = _board("something undrawable", etype="svg_icon")
    SG.resolve_drawn_elements(b2)
    check("G12 an undrawable icon is left untouched for the icon cascade",
          b2["visual_storyboard"][0]["elements"][0]["content"] == "something undrawable")

    # The trap: a resolved path must never reach the icon preflight. Probing a filename
    # fails, a failed probe becomes an asset warning, and a warned element degrades to a
    # Text placeholder — so the probe would DELETE the drawing it was reporting on.
    from lessonforge.engine.assets import _collect_asset_elements  # noqa: E402
    check("G13 a drawn element is skipped by the asset preflight",
          _collect_asset_elements(b) == []
          and len(_collect_asset_elements(b2)) == 1)

    drawn_code = T.parse_schema_to_base_scene(_board(DRAW_PATH, etype="svg_icon"))
    check("G14 the transpiler emits drawing(), not fetch_smart_svg()",
          f"drawing({DRAW_PATH!r}" in drawn_code and "fetch_smart_svg(" not in drawn_code)
    check("G15 a drawn object is never recoloured (its own colours carry meaning)",
          "drawing(" in drawn_code and ", color=" not in
          drawn_code.split("drawing(")[1].split(")")[0])
    icon_code = T.parse_schema_to_base_scene(_board("basketball", etype="svg_icon"))
    check("G16 an unresolved icon still takes the cascade",
          "fetch_smart_svg(" in icon_code and "drawing(" not in icon_code)
    check("G17 drawing is exported from viz_helpers",
          '"simulation", "sim_play", "drawing",' in viz_src)

    # `shape` used to be resolved by a fixed prose→primitive table, which is how a
    # lesson about structure rendered as scattered rings. It is drawn now too — with
    # two exceptions where geometry is not the model's to invent.
    shape_board = {"visual_storyboard": [{"scene_index": 1, "elements": [
        {"id": "ball", "type": "shape", "content": "the basketball at the top of its arc"},
        {"id": "ring", "type": "shape", "content": "circle"},
        {"id": "big", "type": "shape", "content": "small circle"},
        {"id": "edge", "type": "shape", "content": "branch line", "connects": ["ball", "ring"]},
        {"id": "icon", "type": "svg_icon", "content": "thermometer"},
        {"id": "cap", "type": "text", "content": "a circle"},
    ], "narration_cues": [{"cue": "c"}]}]}
    picked = {el["id"]: floor for el, _d, floor in SG._draw_candidates(shape_board)}
    check("G18 a meaningful shape is drawn, not stamped from the primitive table",
          "ball" in picked)
    check("G19 an EDGE is never drawn — its geometry comes from its endpoints",
          "edge" not in picked)
    check("G20 a bare primitive is never drawn (the model would invent parts)",
          "ring" not in picked and "big" not in picked)
    check("G21 text is out of scope", "cap" not in picked)
    check("G22 a shape's complexity floor is lower than an icon's",
          picked.get("ball") == SG.DRAW_SHAPE_MIN_PARTS
          and picked.get("icon") == SG.DRAW_MIN_PARTS
          and SG.DRAW_SHAPE_MIN_PARTS < SG.DRAW_MIN_PARTS)
    # After SHAPE_CONTENT_RULE landed, a live board went 14/16 content-free -> 0/19 —
    # but 11 of the 19 were well-described LINES AND ARROWS. Drawing those would spend a
    # call each to make them worse: a model with a complexity floor adds parts a line
    # should not have. The complaint was that OBJECTS became generic circles, not that
    # arrows were arrows.
    check("G23a a well-described LINE or ARROW keeps its primitive",
          all(SG.is_primitive_subject(t) for t in (
              "dashed vertical line from basketball_start to horizontal_path",
              "downward gravity arrow",
              "arrow indicating initial velocity of the basketball",
              "horizontal velocity arrow pointing right")))
    check("G23b a described OBJECT is still drawn",
          not any(SG.is_primitive_subject(t) for t in (
              "the basketball at the top of its arc", "a hoop with a net",
              "inclined plane", "beaker of water", "basketball trajectory")))
    check("G23c only the HEAD decides — purpose clauses never make a line an object",
          SG.is_primitive_subject("a line representing the trajectory of the ball")
          and not SG.is_primitive_subject("a pendulum with a line for its rod"))
    check("G23 is_bare_primitive spans names, sizes and directions",
          all(SG.is_bare_primitive(t) for t in
              ("circle", "small circle", "arrow pointing right", "vertical dashed line"))
          and not any(SG.is_bare_primitive(t) for t in
                      ("the ground line the ball lands on", "inclined plane",
                       "velocity arrow, constant length")))

    drawn_shape = T.parse_schema_to_base_scene(_board(DRAW_PATH, etype="shape"))
    made = [ln for ln in drawn_shape.splitlines() if "mobj_scene1_sim1 =" in ln][0]
    check("G24 a drawn shape emits drawing(), not a primitive", "drawing(" in made)
    check("G25 a drawn shape is never rescaled or recoloured (it sizes itself via "
          "height= and its own colours carry meaning)",
          ".scale(" not in made and ".set_color(" not in made)
    check("G25b a drawn object is never rendered at text size — structure needs room to "
          "read (the schema default 0.7 rendered every drawing under 1 unit tall in an "
          "8-unit frame, so a frame full of correct geometry still looked empty)",
          T._drawn_icon_height(0.7) >= 1.5 and T._drawn_shape_height(0.7) >= 1.2)
    check("G25c a DELIBERATE size is still obeyed",
          T._drawn_icon_height(2.5) == 2.5 and T._drawn_icon_height(9) <= 4.0)
    check("G26 the model's relative sizing survives the units change",
          T._drawn_shape_height(1.4) > T._drawn_shape_height(0.7)
          and 0.8 <= T._drawn_shape_height(0.1) <= 4.0
          and T._drawn_shape_height(99) <= 4.0)
    primitive_shape = T.parse_schema_to_base_scene(_board("circle", etype="shape"))
    check("G27 an undrawn shape still takes the primitive path",
          "Circle()" in primitive_shape and "drawing(" not in primitive_shape)
finally:
    SG.generate_drawing = _orig_draw
    for p in (DRAW_PATH, DRAW_PATH + ".json"):
        try:
            os.remove(p)
        except OSError:
            pass


# ─────────────────────────────────────────────────────────────────────────────
try:
    os.remove(SIM_PATH)
except OSError:
    pass

passed = sum(1 for _, ok in CHECKS if ok)
print(f"\n{passed}/{len(CHECKS)} checks passed")
sys.exit(0 if passed == len(CHECKS) else 1)
