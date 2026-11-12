"""sanitize_math: what a model writes for a `math` element, made safe for MathTex(r"...")."""
import pytest

from lessonforge.mathfix import sanitize_math as f
from lessonforge.engine.codegen import _strip_mathtex_to_text, _latex_to_plain


@pytest.mark.parametrize("raw,expected", [
    ("x^2 + y^2", "x^2 + y^2"),
    ("$x^2$", "x^2"),
    ("\\(a+b\\)", "a+b"),
    ("Area = 4\u03c0r\u00b2", "\\text{Area }= 4\\pi r^2"),
    ("90\u00b0", "90^\\circ"),
    ("13 m", "13\\,\\text{m}"),
    ("Units: \\text{cm}^2", "\\text{Units: }\\text{cm}^2"),
    ("text(speed) = 5 text(m/s)", "\\text{speed} = 5 \\text{m/s}"),
    ("text(f(x) in R)", "\\text{f(x) in R}"),
    ("a\u00d7b \u2192 c", "a\\times b \\to c"),
    ("\\frac{a}{b}", "\\frac{a}{b}"),
])
def test_sanitize_cases(raw, expected):
    assert f(raw) == expected


@pytest.mark.parametrize("raw", ["x \\text{cm}", "dx \\cdot 3", "\\sin\\theta \\text{rad}"])
def test_variable_before_a_command_is_not_turned_into_text(raw):
    assert f(raw) == raw


def test_safe_inside_a_raw_python_string():
    out = f('say "hi"\nnext \\')
    assert '"' not in out and "\n" not in out and not out.endswith("\\")
    compile(f'x = r"{out}"', "<t>", "exec")      # the line the transpiler emits must be valid Python


@pytest.mark.parametrize("raw", ["Area = 4\u03c0r\u00b2", "13 m", "Units: \\text{cm}^2", "$x$", "a \\\\"])
def test_idempotent(raw):
    once = f(raw)
    assert f(once) == once


def test_never_empty():
    assert f("") == " " and f(None) == " "


def test_aligned_blocks_are_left_alone():
    s = "\\begin{aligned} a &= b \\\\ c &= d \\end{aligned}"
    assert f(s) == s


def test_transpiler_emits_a_clean_mathtex_line():
    from lessonforge.transpiler import parse_schema_to_base_scene
    board = {"visual_storyboard": [{
        "scene_index": 1, "description": "d", "wait_time": 1,
        "elements": [{"id": "m1", "type": "math", "content": "Area = 4\u03c0r\u00b2 text(cm)"}],
        "narration_cues": [{"cue": "Look.", "animation_events": [{"action": "show", "target": "m1"}]}]}]}
    code = parse_schema_to_base_scene(board)
    code = code[0] if isinstance(code, tuple) else code
    assert "\u03c0" not in code and "\u00b2" not in code
    assert "\\pi" in code and "MathTex(" in code


# ---- the Text() fallback used after a LaTeX failure -------------------------------------------------------------
def test_fallback_keeps_nested_brackets_and_fractions():
    code = 't = MathTex(r"\\frac{a}{b} + \\left(x\\right) \\le 3").move_to(UP)'
    out = _strip_mathtex_to_text(code)
    assert out == "t = Text('(a)/(b) + (x) \u2264 3').move_to(UP)"
    compile(out, "<t>", "exec")


def test_fallback_keeps_font_size_and_colour():
    out = _strip_mathtex_to_text('x = Tex(r"\\text{kg} \\times 5", font_size=36, color=RED)')
    assert out == "x = Text('kg \u00d7 5', font_size=36, color=RED)"


def test_latex_command_names_are_not_eaten():
    assert "left" not in _latex_to_plain("\\left(x\\right)") and _latex_to_plain("\\leftarrow") == "leftarrow"
