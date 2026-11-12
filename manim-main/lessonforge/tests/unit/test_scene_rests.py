"""A staged scene's labels must not lie on each other where the lesson HOLDS it between stages (sim_gen.verify).

The pressure lesson of 2026-10-16 held "0.01 m2" on "20 N" through a whole step: the label arrived in stage two and
sat on the first stage's label until the end, where it had moved away, so the start and end checks both passed.
"""
import pytest

pytest.importorskip("manim")
from lessonforge.engine import sim_gen  # noqa: E402

CLASH_MID = '''
def build(width, height):
    a = Text("20 N", font_size=36).move_to([-1, 0, 0])
    b = Text("0.01 m2", font_size=36).move_to([-0.8, 0, 0]).set_opacity(0)
    box = Square(1).move_to([0, -1.2, 0])
    return VGroup(box, a, b)

def animate(group, run_time):
    box, a, b = group
    return AnimationGroup(box.animate.shift(RIGHT * 0.5), b.animate.set_opacity(1), a.animate.move_to([-2, 1.4, 0]),
                          lag_ratio=1.0, run_time=run_time)
'''

APART = CLASH_MID.replace("move_to([-0.8, 0, 0])", "move_to([1.8, -0.2, 0])")


def test_a_label_held_on_another_between_stages_is_refused():
    why = sim_gen.verify(CLASH_MID)
    assert why and "rests between its stages" in why, why


def test_labels_apart_at_every_rest_pass():
    assert sim_gen.verify(APART) is None
