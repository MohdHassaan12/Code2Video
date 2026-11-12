"""
Layout-safety + language-policy acceptance harness (Manim Community v0.20.1).

Part 1 (no Manim needed): unit-tests sanitize_generated_code persona strip logic.
Part 2 (needs Manim):     renders overflow/collision scenes and checks enforcement.

Usage:
    python test_layout_safety.py            # all cases
    python test_layout_safety.py --keep     # keep mp4s + logs
    python test_layout_safety.py --unit     # Part 1 only (fast, no render)
    LAYOUT_STRICT=1 python test_layout_safety.py

Exit 0 = all pass, 1 = any fail (CI-friendly).
"""
import os, sys, re, shutil, subprocess, textwrap

KEEP      = "--keep" in sys.argv
UNIT_ONLY = "--unit" in sys.argv
ROOT = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.join(ROOT, "_layout_test_renders")
os.makedirs(WORK, exist_ok=True)
HAS_LATEX = bool(shutil.which("latex") or shutil.which("pdflatex") or shutil.which("xelatex"))


# ── Part 1: persona strip logic ──────────────────────────────────────────────

def test_persona_logic():
    print("Part 1 — persona strip logic (no render)\n")
    try:
        sys.path.insert(0, ROOT)
        from lessonforge.engine import sanitize_generated_code
    except Exception as e:
        print(f"  – SKIP: could not import app.sanitize_generated_code ({e})")
        return []

    DEV = "पादप"    # Devanagari
    TEL = "సారాంశం"  # Telugu

    # (input_code, persona, must_contain, must_NOT_contain, name)
    cases = [
        (f'Text("Plant Tissues ({DEV})")',        "hybrid", "Plant Tissues", DEV,  "hybrid_strips_devanagari"),
        (f'Text("Summary ({TEL})")',              "hybrid", "Summary",       TEL,  "hybrid_strips_telugu"),
        (f'self.voiceover(text="Aaj hum {DEV}")', "hybrid", DEV,             None, "hybrid_keeps_voiceover"),
        (f'Text("Plant Tissues ({DEV})")',        "hi",     DEV,             None, "pure_hi_keeps_devanagari"),
        (f'Text("Summary ({TEL})")',              "te",     TEL,             None, "pure_te_keeps_telugu"),
        ('Text("x", font_size=1.5 * DEFAULT_FONT_SIZE)', "hybrid", "font_size=", "1.5 * DEFAULT", "shrinks_oversize_font"),
    ]

    results = []
    for code, persona, must, must_not, name in cases:
        out = sanitize_generated_code(code, persona)
        ok = (must in out) and (must_not is None or must_not not in out)
        mark = "✓" if ok else "✗"
        status = "PASS" if ok else "FAIL"
        if ok:
            print(f"  {mark} {name.ljust(36)} {status}")
        else:
            print(f"  {mark} {name.ljust(36)} {status}  got: {out!r}")
        results.append((name, status, f"persona={persona}"))
    print()
    return results


# ── Part 2: render scenes ─────────────────────────────────────────────────────

SCENE_LONG_BULLET = '''
from manim import *
from viz_helpers import *
config.font = "Montserrat"
class LongBulletScene(Scene):
    def construct(self):
        t = Text(
            "2. Tissues perform specific functions across the entire organism via division of labor",
            font_size=0.7 * 48,
        ).move_to([0, BODY_Y, 0])
        self.add(t)
        auto_fit_scene(self)
'''

SCENE_TWO_COLUMN = '''
from manim import *
from viz_helpers import *
config.font = "Montserrat"
class TwoColumnScene(Scene):
    def construct(self):
        a = Text("Supportive Tissues and structures", font_size=0.6 * 48).move_to([-3, 0, 0])
        b = Text("More Living Tissues and functions", font_size=0.6 * 48).move_to([3, 0, 0])
        self.add(a, b)
        auto_fit_scene(self)
'''

SCENE_WIDE_MATHTEX = '''
from manim import *
from viz_helpers import *
config.font = "Montserrat"
class WideMathScene(Scene):
    def construct(self):
        eq = MathTex(
            r"{{2}} {{H_2}} + {{O_2}} \\rightarrow {{2}} {{H_2O}} \\;\\; E = mc^2 \\;\\; a^2+b^2=c^2"
        )
        eq.move_to([0, BODY_Y, 0])
        self.add(eq)
        auto_fit_scene(self)
'''

SCENE_FORCED_VIOLATION = '''
from manim import *
from viz_helpers import *
config.font = "Montserrat"
class ForcedViolationScene(Scene):
    def construct(self):
        d = Dot().move_to([20, 0, 0])
        self.add(d)
        _fw, _fh = config.frame_width / 2, config.frame_height / 2
        for _m in self.mobjects:
            try:
                if (_m.get_right()[0] > _fw + 0.05 or _m.get_left()[0] < -_fw - 0.05 or
                        _m.get_top()[1] > _fh + 0.05 or _m.get_bottom()[1] < -_fh - 0.05):
                    print(f"LAYOUT_VIOLATION: {type(_m).__name__} off-frame")
            except Exception:
                continue
'''

RENDER_CASES = [
    ("long_bullet",      "LongBulletScene",      SCENE_LONG_BULLET,      "clamped"),
    ("two_column",       "TwoColumnScene",       SCENE_TWO_COLUMN,       "clamped"),
    ("wide_mathtex",     "WideMathScene",        SCENE_WIDE_MATHTEX,     "no_crash"),
    ("forced_violation", "ForcedViolationScene", SCENE_FORCED_VIOLATION, "violation"),
]


def stage_viz_helpers():
    for cand in (
        os.path.join(os.path.dirname(os.path.abspath(__import__("lessonforge").__file__)), "viz_helpers.py"),
    ):
        if os.path.exists(cand):
            shutil.copy(cand, os.path.join(WORK, "viz_helpers.py"))
            return
    print("  ! viz_helpers.py not found — adjust ROOT")


def run_render(name, scene_class, code, expectation):
    script = os.path.join(WORK, f"{name}.py")
    with open(script, "w", encoding="utf-8") as f:
        f.write(textwrap.dedent(code))
    media = os.path.join(WORK, f"media_{name}")
    cmd = [
        sys.executable, "-m", "manim", "-ql", "--disable_caching",
        script, scene_class, "--media_dir", media,
    ]
    env = os.environ.copy()
    env["PYTHONPATH"] = WORK + os.pathsep + ROOT + os.pathsep + env.get("PYTHONPATH", "")
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=180)
        out = (proc.stdout or "") + (proc.stderr or "")
    except subprocess.TimeoutExpired:
        return name, "FAIL", "timeout"
    except FileNotFoundError:
        return name, "SKIP", "manim not installed"
    finally:
        if not KEEP:
            shutil.rmtree(media, ignore_errors=True)

    rendered = proc.returncode == 0
    violated = "LAYOUT_VIOLATION:" in out
    if KEEP:
        with open(os.path.join(WORK, f"{name}.log"), "w") as f:
            f.write(out)

    if expectation == "no_crash":
        ok, d = rendered, f"rendered={rendered} latex={'y' if HAS_LATEX else 'n'}"
    elif expectation == "clamped":
        ok, d = (rendered and not violated), f"rendered={rendered} violation={violated}"
    elif expectation == "violation":
        ok, d = violated, f"violation_emitted={violated}"
    else:
        ok, d = False, "unknown expectation"

    return name, ("PASS" if ok else "FAIL"), d


def main():
    print(
        f"Layout-safety harness  "
        f"(LaTeX={'y' if HAS_LATEX else 'n'}  "
        f"STRICT={os.getenv('LAYOUT_STRICT', '0')})\n"
    )
    all_results = test_persona_logic()

    if not UNIT_ONLY:
        print("Part 2 — render enforcement\n")
        if not shutil.which("ffmpeg"):
            print("  ! ffmpeg missing — renders will likely fail\n")
        stage_viz_helpers()
        for c in RENDER_CASES:
            n, s, d = run_render(*c)
            mark = {"PASS": "✓", "FAIL": "✗", "SKIP": "–"}[s]
            print(f"  {mark} {n.ljust(22)} {s:4}  {d}")
            all_results.append((n, s, d))
        print()

    if not KEEP:
        shutil.rmtree(WORK, ignore_errors=True)

    fails = [r for r in all_results if r[1] == "FAIL"]
    print(f"{'FAILED' if fails else 'ALL PASSED'} — {len(fails)} failure(s) / {len(all_results)} total")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
