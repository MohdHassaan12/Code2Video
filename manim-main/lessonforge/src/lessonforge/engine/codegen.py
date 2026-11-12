"""Manim code hygiene + repair: sanitize, validate (syntax/logic), self-heal,
deterministic layout lint + the LLM Layout-QA critic, LaTeX->Text fallback.
repair_code_with_gemini / sanitize_generated_code are monkeypatch/call seams."""
import os
import re
import ast
import logging

from .llm import call_llm_with_fallback, strip_code_fences, llm_available
from .rag import _retrieve_past_fixes, _store_repair_pair

logger = logging.getLogger(__name__)

def sanitize_generated_code(code, persona="hybrid"):
    """Clean up hallucinated imports, enforce layout rules, and apply language policy."""
    if not code:
        return ""
    # Clean up hallucinated imports of SarvamService from manim_voiceover
    code = re.sub(
        r'from\s+manim_voiceover\s+import\s+([^\n]*)',
        lambda m: "from manim_voiceover import " + ", ".join([x.strip() for x in m.group(1).split(",") if x.strip() != "SarvamService"]),
        code
    )
    lines = code.splitlines()
    cleaned_lines = []
    for line in lines:
        if "manim_voiceover.services." in line:
            continue
        cleaned_lines.append(line)
    
    code = "\n".join(cleaned_lines)

    # Ensure local helper utilities and monkeypatched services from viz_helpers are always imported.
    # A *selective* import (e.g. `from viz_helpers import UniversalTTSService`, which the codegen
    # prompt asks for) used to satisfy the "already imported" check below, leaving auto_fit_scene /
    # clear_canvas undefined -> NameError at render time, and silently skipping the config.font
    # injection that keys off the star-import line. Normalize any selective form to the star import.
    code = re.sub(
        r'^([ \t]*)from\s+viz_helpers\s+import\s+(?!\*)[^\n]+$',
        lambda m: f"{m.group(1)}from viz_helpers import *",
        code,
        flags=re.MULTILINE,
    )
    if "from viz_helpers import" not in code:
        if "from manim import *" in code:
            code = code.replace("from manim import *", "from manim import *\nfrom viz_helpers import *")
        else:
            code = "from viz_helpers import *\n" + code

    # Set Montserrat as the global default font for a clean, modern look.
    # Hindi/native-script Text objects are unaffected — viz_helpers forces Nirmala UI per-call.
    # Silent no-op if Montserrat is not installed on the host machine.
    if 'config.font = "Montserrat"' not in code:
        code = code.replace(
            "from viz_helpers import *",
            'from viz_helpers import *\nconfig.font = "Montserrat"',
            1,
        )

    # Auto-repair hallucinated SVGMobject calls to fetch_smart_svg
    def replace_svg_mobject(match):
        args_str = match.group(1)
        str_match = re.search(r'["\'](.*?\.svg)["\']', args_str, re.IGNORECASE)
        if str_match:
            filepath = str_match.group(1)
            filename = os.path.basename(filepath)
            keyword, _ = os.path.splitext(filename)
            keyword = keyword.replace("_icon", "").replace("-icon", "").strip()
            new_args = args_str.replace(str_match.group(0), f'"{keyword}"')
            return f"fetch_smart_svg({new_args})"
        return match.group(0)

    code = re.sub(r'\bSVGMobject\((.*?)\)', replace_svg_mobject, code, flags=re.DOTALL)

    # Strip redundant SVGMobject wrapper around custom helper calls
    idx = 0
    while True:
        pos = code.find("SVGMobject(", idx)
        if pos == -1:
            break
        start = pos + len("SVGMobject(")
        depth = 1
        end = start
        while end < len(code) and depth > 0:
            if code[end] == '(':
                depth += 1
            elif code[end] == ')':
                depth -= 1
            end += 1
        if depth == 0:
            inner = code[start:end-1].strip()
            if any(inner.startswith(h) for h in ["fetch_smart_svg", "fetch_molecule_svg", "atom", "molecule"]):
                code = code[:pos] + inner + code[end:]
                idx = pos
                continue
        idx = pos + 1

    # --- Language / script policy ---
    # hybrid/en: on-screen Text() must be English-only. Strip parenthetical Indic
    # translations ("Plant Tissues (पादप ऊतक)" → "Plant Tissues") and stray native
    # characters. Voiceover strings (self.voiceover(text=...)) are NEVER touched.
    # pure-lang (hi, te, bn, …): Indic script on screen is intentional — leave intact.
    _INDIC = (r'ऀ-ॿ'   # Devanagari
              r'ঀ-৿'   # Bengali
              r'਀-੿'   # Gurmukhi
              r'઀-૿'   # Gujarati
              r'଀-୿'   # Oriya
              r'஀-௿'   # Tamil
              r'ఀ-౿'   # Telugu
              r'ಀ-೿'   # Kannada
              r'ഀ-ൿ')  # Malayalam
    if persona in ("hybrid", "en"):
        # Match BOTH quote styles: the transpiler emits Text({repr(content)}),
        # and repr() single-quotes Devanagari — a double-quote-only pattern let
        # every transpiled title through (Dalton run, 2026-07-20: hybrid video
        # shipped with Devanagari headings).
        def _strip_indic(m):
            q, inner = m.group(1), m.group(2)
            inner = re.sub(rf'\s*\([^)]*[{_INDIC}][^)]*\)', '', inner)  # "(देव…)" parens
            inner = re.sub(rf'[{_INDIC}]+', '', inner)                   # stray runs
            inner = re.sub(r'\s{2,}', ' ', inner).strip()
            # Nothing readable left (pure-Indic string, or quote/punctuation
            # shrapnel like "'-' ?") — render nothing rather than junk.
            if not re.search(r'[A-Za-z0-9]', inner):
                inner = ''
            return f'Text({q}{inner}{q}'
        code = re.sub(r'(?<!_)\bText\(\s*(["\'])((?:(?!\1).)*)\1', _strip_indic, code)

    # --- Deterministic layout lint ---
    # (1) font_size multipliers >= 1 on DEFAULT_FONT_SIZE overflow the frame; cap them.
    def _shrink_fontsize(m):
        try:
            k = float(m.group(1))
        except ValueError:
            return m.group(0)
        if k >= 1.0:
            return f"font_size={min(k, 0.9) * 48:.1f}"
        return m.group(0)
    code = re.sub(
        r'font_size\s*=\s*([0-9.]+)\s*\*\s*DEFAULT_FONT_SIZE',
        _shrink_fontsize, code
    )

    # (2) Off-center absolute placement of text is the other overflow root cause.
    #     Flag it non-destructively so the LLM critic has a precise target.
    if ("LAYOUT_LINT" not in code and
            re.search(r'(?:Text|MathTex)\([^\n]*\)\.move_to\(\s*\[\s*-?[1-9]', code)):
        code = ("# LAYOUT_LINT: off-center .move_to on text detected — "
                "prefer VGroup(...).arrange() or [0, TITLE_Y/BODY_Y, 0].\n") + code

    return code


def detect_scene_class(code, fallback="STEMAnimation"):
    """Return the name of the first class extending a *Scene base, else fallback."""
    match = re.search(r"class\s+(\w+)\s*\(\s*[\w.]*Scene\b", code or "")
    return match.group(1) if match else fallback


def validate_python(code):
    """Fast syntax check. Returns (ok: bool, error_message: str|None)."""
    try:
        ast.parse(code or "")
        return True, None
    except SyntaxError as e:
        return False, f"{e.msg} (line {e.lineno}, offset {e.offset})"


def repair_code_with_gemini(client, code, error_msg, scene_class, keys=None):
    """Ask the model to fix a syntax, logic, or execution error in previously generated Manim code."""
    # RAG: inject known fixes for similar past errors at the top of the prompt
    past_fixes = _retrieve_past_fixes(error_msg)
    rag_section = ""
    if past_fixes:
        lines = ["## Past Fixes for Similar Errors\n"]
        for i, fix in enumerate(past_fixes, 1):
            lines.append(f"### Fix {i} (type: {fix['error_type']})")
            lines.append(f"Error pattern: {fix['error'][:300]}")
            lines.append(f"Working fix:\n```python\n{fix['fixed_snippet'][:600]}\n```\n")
        rag_section = "\n".join(lines) + "\n\n"

    system_instruction = (
        "You are an expert Python/Manim developer and code repair agent.\n"
        "Your task is to fix any syntax errors, API compilation errors, logic errors, or layout issues "
        "in a Manim script.\n\n"
        "Please strictly adhere to the following constraints:\n"
        "1. Return ONLY the complete, raw corrected Python code. Do NOT include markdown blocks, code fences (e.g. ```python), or any explanations/commentary.\n"
        f"2. Retain the exact class name `{scene_class}` and keep all required imports (from manim import *, etc.).\n"
        "3. Preserve all narrative speech voiceover blocks and the exact educational flow of the script.\n"
        "4. Fix only what is necessary to resolve the reported error or warning. Ensure all Manim constant names (e.g. UR, DL, UP, DOWN) and mobject usages are 100% correct according to the latest Manim API. Note that legacy classes like `GrowFromBottom`, `GrowFromTop`, `GrowFromLeft`, or `GrowFromRight` do not exist in modern Manim (use `GrowFromEdge(mobject, DOWN/UP/LEFT/RIGHT)` instead). Also, constructors like `Angle` and `Arc` do not accept `end_angle` or `start_angle` keywords — remove them if they appear. If the error is an OSError or FileNotFoundError from `SVGMobject` due to missing local SVG assets (e.g., 'nematode_outline.svg'), replace the SVGMobject with `fetch_smart_svg(keyword)` (where keyword is a search query like 'car' or 'flask' to fetch standard icons dynamically from the Iconify API), or fall back to standard geometric shapes (like Ellipse, Circle, or VGroup).\n"
        "5. You MUST retain the voiceover setup statement EXACTLY as provided. Do not invent other TTS services."
    )
    prompt = (
        rag_section +
        f"The following Manim script contains errors or failed to execute successfully.\n\n"
        f"--- Error / Exception Report ---\n"
        f"{error_msg}\n\n"
        f"--- Original Manim Script ---\n"
        f"{code}\n\n"
        f"Analyze the script and error report. Fix all logical/syntax/layout issues and return the fully functional, complete python script."
    )
    response = call_llm_with_fallback(
        client, prompt=prompt,
        system_instruction=system_instruction, temperature=0.0, task="code", keys=keys,
    )
    return strip_code_fences(response.text)


def validate_manim_logic_with_gemini(client, code, scene_class, keys=None):
    """Ask a validator agent to check the Manim code for logical, semantic, or API usage errors."""
    system_instruction = (
        "You are an expert Python/Manim validator. Your job is to check a Manim script for logical, "
        "semantic, or API usage errors (e.g. using undefined direction constants like 'UP_RIGHT' instead of 'UR', "
        "improper variable usages, method arguments that don't match Manim API, or incorrect layout/coordinates). "
        "If there are errors, describe them clearly so a repair tool can fix them. "
        "If the code has no errors and is completely correct, return ONLY the word 'OK'."
    )
    prompt = f"Validate this Manim script for scene class {scene_class}:\n\n{code}"
    response = call_llm_with_fallback(
        client, prompt=prompt,
        system_instruction=system_instruction, temperature=0.0, task="code", keys=keys,
    )
    res = response.text.strip()
    if res == "OK":
        return True, None
    return False, res


def validate_and_repair(client, code, scene_class, max_rounds=2, keys=None, persona="hybrid"):
    """Validate code (both syntax and logical correctness); attempt up to max_rounds AI repair passes.

    Returns (code, ok, error_message).
    """
    code = sanitize_generated_code(code, persona)
    # Step 1: Syntax check
    ok, err = validate_python(code)

    # Step 2: Logical check (only if syntax is OK)
    if ok and llm_available(client, keys):
        try:
            ok, err = validate_manim_logic_with_gemini(client, code, scene_class, keys=keys)
        except Exception as e:
            logger.warning(f"Logical validation failed, defaulting to syntax check only: {e}")
            ok = True
            err = None

    rounds = 0
    while not ok and llm_available(client, keys) and rounds < max_rounds:
        logger.warning(f"Generated code invalid ({err}). Repair round {rounds + 1}/{max_rounds}...")
        _prev_err = err
        _prev_code = code
        try:
            code = repair_code_with_gemini(client, code, err, scene_class, keys=keys)
            code = sanitize_generated_code(code, persona)
        except Exception as e:
            logger.warning(f"Repair attempt failed: {e}")
            break

        # Re-run checks
        ok, err = validate_python(code)
        if ok:
            try:
                ok, err = validate_manim_logic_with_gemini(client, code, scene_class, keys=keys)
            except Exception:
                ok = True
                err = None
        if ok:
            _store_repair_pair(_prev_err, _prev_code, code, scene_class)
        rounds += 1

    if ok and rounds:
        logger.info(f"Code repaired successfully after {rounds} round(s).")
    return code, ok, err


LAYOUT_RULES = """CRITICAL MANIM LAYOUT RULES — the render pipeline now ENFORCES bounds via
viz_helpers (Text/MathTex auto-clamp width; auto_fit_scene() runs at scene end). Write code
that cooperates with that layer; do NOT fight it with manual oversizing or off-center coords.

1. USE THE SAFE HELPERS (already imported via `from viz_helpers import *`):
   - Text(...) and MathTex(...) auto-clamp to SAFE_W — you do NOT need manual width math.
   - Titles/questions: place at [0, TITLE_Y, 0]. Body content: [0, BODY_Y, 0]. These bands never overlap.
   - End construct() with `auto_fit_scene(self)` as a safety net (the pipeline also injects this).
   - Between beats, call `clear_canvas(self)` instead of enumerating FadeOuts — it can't miss an object.

2. NEVER oversize text. font_size must be `scale * 48` with scale in [0.55, 0.9] (0.8-0.9 titles,
   0.6-0.7 body, 0.55-0.6 captions). NEVER `k * DEFAULT_FONT_SIZE` with k >= 1 — it overflows the
   frame and the sanitizer will shrink it anyway.

3. NEVER `.move_to([x, y, 0])` with x != 0 on Text/MathTex. Off-center absolute placement of
   variable-width text is THE overflow bug. For 2+ related objects the ONLY placement primitive is
   `VGroup(...).arrange(RIGHT|DOWN, buff=..., aligned_edge=LEFT)`. Raw coords allowed only for
   on-center band placement [0, TITLE_Y, 0] / [0, BODY_Y, 0].

4. Canvas frame is 14.22 x 8.0 (x: -7.11..7.11, y: -4..4); safe region ~x[-6.4,6.4], y[-3.4,3.4].
   Do not stretch axes past x_length=12 / y_length=6. Every coordinate is a 3-tuple [x, y, 0], never 2D.

5. Coverage: every Dot/Line/point you plot MUST fall inside the axes x_range/y_range with >=1 unit margin
   (coords_to_point does NOT clip — out-of-range points render off screen). For NumberLine use .n2p(),
   never .coords_to_point().

6. Equations: MathTex with isolated parts, e.g. MathTex(r"{{2}} {{H_2}} + {{O_2}} \\rightarrow {{2}} {{H_2O}}"),
   evolve with TransformMatchingTex. MathTex for math ONLY; Text for prose. Never an equation as a single
   Text with inline coefficients (spacing breaks). Never MarkupText XML sub/sup tags (Pango errors).

7. Text density: at most ~5 short text lines or ~3 blocks on screen at once. Rich VISUALS (shapes, dots,
   arrows, molecules) are encouraged and NOT limited — it is TEXT clutter you avoid. More text than that ->
   sequence into beats with clear_canvas(self) between them, or split the screen.

8. Line labels: never .next_to() a slanted/near-horizontal line (anchors to a far bbox corner). Use the
   midpoint, shifted AWAY from the nearest axis so the label never covers tick numbers (they sit just
   below the x-axis and just left of the y-axis): label.move_to(line.get_center()).shift(UP*0.35) for a
   line on/above the x-axis (DOWN*0.35 if below it), RIGHT*0.35 when the line hugs the y-axis.

9. Dashed lines: use DashedLine(start, end); never pass dash_length/dash_array to Line or set_stroke.

10. NumberLine coordinates: NEVER use .coords_to_point() on a NumberLine — use .n2p(value) or
    .number_to_point(value) instead.

11. Direction constants: translate JSON directions to Manim abbreviations — UP_RIGHT->UR, UP_LEFT->UL,
    DOWN_RIGHT->DR, DOWN_LEFT->DL. Never emit 'DOWN_LEFT' literally.

"""


def review_layout_with_gemini(client, code, scene_class, keys=None):
    """Layout QA Critic: a focused second pass that fixes ONLY spatial/positioning bugs."""
    system_instruction = (
        "You are a Manim Layout QA Expert. Review the provided Manim code and fix spatial/"
        "positioning bugs before execution. Check specifically for:\n"
        "- Elements positioned with .next_to() that may fall off the screen.\n"
        "- Multiple formulas/text objects created independently instead of wrapped in a VGroup.\n"
        "- Axes x_range/y_range that do NOT cover the coordinates of every Dot/Line plotted.\n"
        "- Diagonal/near-horizontal line labels anchored with .next_to() instead of the midpoint, or "
        "shifted toward an axis so they cover its tick numbers.\n"
        "- Scenes mixing a graph and long text without splitting the screen.\n"
        "- NumberLine using .coords_to_point() instead of .n2p() or .number_to_point().\n"
        "- Usage of invalid directional constants like DOWN_LEFT or UP_RIGHT instead of DL, UR, UL, DR.\n"
        "- Equations built as a single Text with inline coefficients/manual spaces (must be MathTex or an arranged token VGroup).\n"
        "- MathTex strings with unbalanced braces or invalid LaTeX, and any leftover MarkupText XML.\n"
        "Rewrite the code to fix these issues: widen axis ranges to contain all points, group and "
        "scale text to fit, and move/scale the graph to make room for text.\n"
        f"Preserve the class name `{scene_class}`, all imports, every narration/voiceover block, the "
        "animation order, and the text/math split (Text for prose, MathTex for equations). Return ONLY "
        "the corrected raw Python script — no markdown, no commentary.\n\n" + LAYOUT_RULES
    )
    prompt = "Review and fix the spatial layout of this Manim script:\n\n" + code
    response = call_llm_with_fallback(
        client, prompt=prompt, system_instruction=system_instruction, temperature=0.1, task="code", keys=keys,
    )
    return strip_code_fences(response.text)


def ensure_layout(client, code, scene_class, keys=None, persona="hybrid"):
    """Deterministic lint first (free), then the LLM Layout QA Critic as fallback.

    Falls back to the linted code if the critic is disabled, errors, or returns code that
    no longer parses or dropped the scene class.
    """
    # Deterministic pass always runs — it's free and can't be argued out of it.
    code = sanitize_generated_code(code, persona)

    if not llm_available(client, keys) or os.getenv("LAYOUT_REVIEW", "1") != "1":
        return code
    try:
        fixed = review_layout_with_gemini(client, code, scene_class, keys=keys)
    except Exception as e:
        logger.warning(f"Layout review failed, keeping deterministic-linted code: {e}")
        return code
    ok, _ = validate_python(fixed)
    if not (ok and "def construct" in fixed and f"class {scene_class}" in fixed):
        logger.warning("Layout review produced invalid/incomplete code; keeping linted version.")
        return code

    # The critic may only ADJUST layout — it must never delete the objects the
    # transpiler decided to draw, or dissolve the structural helpers that bind
    # them. Measured 2026-08-01: asked to tidy a tray of six sweets it collapsed
    # all six into ONE mobject and replaced place_inside() with a hand-rolled
    # arrange_in_grid, silently deleting five elements from the video. Acceptance
    # used to check only "does it parse and keep the class name".
    lost_vars = _element_vars(code) - _element_vars(fixed)
    if lost_vars:
        logger.warning(
            "Layout QA Critic dropped %d element(s) (%s) — keeping deterministic code.",
            len(lost_vars), ", ".join(sorted(lost_vars)[:4]))
        return code
    lost_structure = _structure_losses(code, fixed)
    if lost_structure:
        logger.warning(
            "Layout QA Critic dissolved structural helpers (%s) — keeping deterministic code.",
            "; ".join(lost_structure))
        return code
    lost_anchors = _anchor_losses(code, fixed)
    if lost_anchors:
        logger.warning(
            "Layout QA Critic un-anchored zone-placed elements (%s) — keeping deterministic code.",
            lost_anchors)
        return code

    logger.info("Layout QA Critic pass applied (after deterministic lint).")
    return fixed


# Variables the transpiler emits for storyboard elements: one per drawable object.
_ELEMENT_VAR_RE = re.compile(r"^\s*(mobj_scene\d+_\w+)\s*=", re.M)

# Helpers that encode code-owned structure. Losing a call means a relationship
# (an edge's endpoints, a container's contents, a node's value) became guesswork —
# or, for sustain(), that a beat went back to holding a still frame for its whole
# narration. The critic is asked about LAYOUT; a "tidier" rewrite that drops the
# motion filler is exactly the improve-or-stand-aside violation this list exists
# for, and the geometric probe would never notice (motion is round-trip).
# `drawing(`, `simulation(` and `sim_play(` are here for a second reason on top of
# structure: each one cost an LLM call plus a verification run before it was allowed
# into the script, so a rewrite that "tidies" one away destroys work the critic cannot
# recreate — and swapping a drawn object for an icon leaves a perfectly legal frame, so
# nothing downstream would object. Same rule as `_repair_preserves_assets` on the render
# side; both lists must grow whenever a new generated asset is added.
_STRUCTURE_HELPERS = ("connector(", "place_inside(", "value_in(", "sustain(",
                      "drawing(", "simulation(", "sim_play(")


def _element_vars(code_content: str) -> set:
    return set(_ELEMENT_VAR_RE.findall(code_content or ""))


def _anchor_losses(before: str, after: str):
    """Report zone anchors the rewrite converted to raw coordinates, else None.

    Safe-zone placement is code-owned: the transpiler claims zones, routes around
    axes and stacks toward frame centre. Measured 2026-08-01: the critic rewrote a
    BOTTOM_CENTER caption's `.to_edge(DOWN)` into `.move_to([0, BODY_Y, 0])` — and
    BODY_Y is the frame's MIDDLE — dropping the caption straight through a factor
    tree. Nothing was deleted, so the element/structure guards passed it.
    """
    n_before = (before or "").count(".to_edge(") + (before or "").count(".to_corner(")
    n_after = (after or "").count(".to_edge(") + (after or "").count(".to_corner(")
    if n_after < n_before:
        return f"zone anchors {n_before}->{n_after}"
    return None


def _structure_losses(before: str, after: str) -> list:
    """Structural helper calls the rewrite removed, as human-readable notes."""
    losses = []
    for helper in _STRUCTURE_HELPERS:
        n_before = (before or "").count(helper)
        n_after = (after or "").count(helper)
        if n_after < n_before:
            losses.append(f"{helper[:-1]} {n_before}->{n_after}")
    return losses


_PLAIN_LATEX = (("\\times", "×"), ("\\cdot", "·"), ("\\div", "÷"), ("\\pi", "π"), ("\\theta", "θ"),
                ("\\alpha", "α"), ("\\beta", "β"), ("\\Delta", "Δ"), ("\\circ", "°"), ("\\pm", "±"),
                ("\\le", "≤"), ("\\ge", "≥"), ("\\neq", "≠"), ("\\approx", "≈"), ("\\to", "→"),
                ("\\infty", "∞"), ("\\,", " "), ("\\ ", " "))


def _latex_to_plain(val: str) -> str:
    """LaTeX text as readable plain text for Text(): ``\\frac{a}{b}`` -> ``(a)/(b)``, ``\\text{kg}`` -> ``kg``,
    common symbols as characters, braces dropped. Lossy by design: it only runs when LaTeX itself failed."""
    for _ in range(4):  # nested fractions
        val = re.sub(r"\\[dt]?frac\s*\{([^{}]*)\}\s*\{([^{}]*)\}", r"(\1)/(\2)", val)
    val = re.sub(r"\\(?:text|mathrm|mathbf|mathit|operatorname)\s*\{([^{}]*)\}", r"\1", val)
    val = re.sub(r"\\sqrt\s*\{([^{}]*)\}", r"sqrt(\1)", val).replace("\\sqrt", "sqrt")
    val = re.sub(r"\\(?:left|right|big|Big|bigg|Bigg)(?![a-zA-Z])", "", val)
    for tex, char in _PLAIN_LATEX:
        # a command ends at a non-letter: "\\le" must not eat the start of "\\left" or "\\leftarrow"
        val = re.sub(re.escape(tex) + ("(?![a-zA-Z])" if tex[-1].isalpha() else ""), lambda _m, c=char: c, val)
    val = re.sub(r"\\([a-zA-Z]+)", r"\1", val)
    val = val.replace("{", "(").replace("}", ")").replace("\\", "")
    return re.sub(r"\s+", " ", val).strip()


def _call_end(code: str, open_idx: int):
    """Index of the ``)`` closing the call whose ``(`` is at `open_idx`, skipping brackets inside string literals
    (``MathTex(r"\\left(x\\right)")``); None if it never closes. A backslash escapes the next character in a
    raw string too for the purpose of finding the end of the literal."""
    depth, i, n = 0, open_idx, len(code)
    while i < n:
        c = code[i]
        if c in "'\"":
            q = c * 3 if code[i:i + 3] == c * 3 else c
            i += len(q)
            while i < n and code[i:i + len(q)] != q:
                i += 2 if code[i] == "\\" else 1
            i += len(q)
            continue
        if c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return None


def _strip_mathtex_to_text(code_content: str) -> str:
    """Deterministically replace MathTex/Tex calls with Text equivalents.

    Used both when LaTeX is absent from PATH and as a targeted recovery pass
    after a runtime LaTeX compile error is detected in render logs. The end of each call is found by counting
    brackets outside string literals (the old non-greedy regex stopped at the first ``)``, e.g. in ``\\left(``),
    and the LaTeX is turned into readable text (``\\frac{a}{b}`` -> ``(a)/(b)``).
    """
    def _plain_call(args_str: str) -> str:
        args_str = args_str.strip()
        try:
            node = ast.parse(f"f({args_str})").body[0].value
            parts = []
            for arg in node.args:
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    parts.append(_latex_to_plain(arg.value))
                else:
                    parts.append(ast.unparse(arg))
            kept = [ast.unparse(k) for k in node.keywords if k.arg in ("font_size", "color", "weight")]
            return "Text(" + ", ".join([repr(' '.join(parts))] + kept) + ")"
        except Exception:
            return f"Text({repr(_latex_to_plain(args_str.strip('rR\'\" ')))})"

    pattern = re.compile(r"\b(?:Math)?Tex\(")
    out, pos = [], 0
    while True:
        m = pattern.search(code_content, pos)
        if not m:
            out.append(code_content[pos:])
            break
        end = _call_end(code_content, m.end() - 1)
        if end is None:
            out.append(code_content[pos:])
            break
        out.append(code_content[pos:m.start()])
        out.append(_plain_call(code_content[m.end():end]))
        pos = end + 1
    return "".join(out)
