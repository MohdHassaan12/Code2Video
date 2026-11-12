"""Acceptance harness for generated vector assets (app/asset_gen.py).

No API keys and no network — the LLM is stubbed — but the matplotlib subprocess is
REAL: the point of this stage is that model-written drawing code actually executes
and produces a usable SVG, so stubbing that would test nothing.

    .venv/bin/python stem_animation_lab/test_asset_gen.py

What it pins:
  A. The safety gate — model-written code is EXECUTED, so `open(`, `os.`, imports
     outside numpy/math/matplotlib and a missing draw() must be refused *before*
     the subprocess starts, and refusal must not be retried.
  B. End to end — a real drawing produces a real SVG with real primitives, a
     sidecar records what made it, and the second request is a cache HIT that
     spends no LLM call (a metered edge must be billed once per keyword).
  C. Accept-if-usable — "the subprocess exited 0" proves nothing: an empty canvas
     must be rejected, and a crashing draw() must get exactly one repair round.
  D. resolve_generated_assets — svg_icon warnings become absolute paths in the
     board, molecules are left to RDKit/PubChem, unresolved warnings survive, and
     ASSET_GEN=0 disables the whole pass.
"""
import os
import sys
import json
import shutil
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

os.environ.setdefault("ASSET_GEN", "1")
os.environ["ASSET_GEN_REPAIR_ROUNDS"] = "1"

from lessonforge.engine import asset_gen as ag  # noqa: E402

CHECKS = []


def check(name, cond, detail=""):
    CHECKS.append((name, bool(cond)))
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"  — {detail}" if detail and not cond else ""))


# Point the cache at a scratch dir so a test run never pollutes assets/.
TMP = tempfile.mkdtemp(prefix="assetgen_test_")
ag.CACHE_DIR = TMP


class StubLLM:
    """Stands in for call_llm_with_fallback; replies from a scripted list."""

    def __init__(self, *replies):
        self.replies = list(replies)
        self.calls = 0
        self.prompts = []
        self.tasks = []

    def __call__(self, client, prompt, system, temperature=0.2, task="general", keys=None):
        self.calls += 1
        self.prompts.append(prompt)
        self.tasks.append(task)
        text = self.replies[min(self.calls - 1, len(self.replies) - 1)]
        return type("R", (), {"text": text})()


def use(stub):
    ag.call_llm_with_fallback = stub
    ag.get_genai_client = lambda keys=None: None
    return stub


TRIANGLE = """
def draw(ax):
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.plot([20, 80, 50, 20], [20, 20, 80, 20], lw=6, color='black')
    ax.plot([35, 65], [45, 45], lw=6, color='black')
"""

CLOCK = """
def draw(ax):
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.add_patch(patches.Circle((50, 60), 28, fill=False, lw=6, color='black'))
    ax.plot([50, 50], [60, 78], lw=6, color='black')
    ax.plot([50, 64], [60, 60], lw=6, color='black')
    ax.plot([35, 65], [30, 30], lw=6, color='black')
"""

EMPTY = """
def draw(ax):
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
"""

CRASHES = """
def draw(ax):
    ax.plot([0, 1], [0, 1], lw=6, color='black')
    raise ValueError("deliberate failure")
"""


# ── Part A: the safety gate ───────────────────────────────────────────────────
print("\nPart A — model-written code is executed, so it is gated first")

check("A1 forbidden file IO is rejected",
      ag._unsafe_code("def draw(ax):\n    open('/etc/passwd').read()") is not None)
check("A2 os/sys access is rejected",
      ag._unsafe_code("def draw(ax):\n    os.system('ls')") is not None
      and ag._unsafe_code("def draw(ax):\n    sys.exit()") is not None)
check("A3 dynamic execution is rejected",
      ag._unsafe_code("def draw(ax):\n    eval('1+1')") is not None
      and ag._unsafe_code("def draw(ax):\n    __import__('socket')") is not None)
check("A4 an import outside numpy/math/matplotlib is rejected",
      ag._unsafe_code("import requests\ndef draw(ax):\n    pass") is not None)
check("A5 numpy/math/matplotlib imports are tolerated",
      ag._unsafe_code("import numpy as np\nfrom matplotlib import patches\n" + TRIANGLE) is None)
check("A6 code with no draw() is rejected",
      ag._unsafe_code("x = 1") is not None)
check("A7 a clean drawing passes the gate", ag._unsafe_code(TRIANGLE) is None)
check("A8 letters that merely end a variable name are not a refusal (the `ladoos.` false hit)",
      all(ag._unsafe_code("def draw(ax):\n    " + line) is None for line in (
          "ladoos.append(1)", "pos.copy()", "photos.sort()", "plots.showing = 1"))
      and ag._unsafe_code("def draw(ax):\n    plt.show()") is not None
      and ag._unsafe_code("def draw(ax):\n    fig.savefig('x.png')") is not None)

stub = use(StubLLM("def draw(ax):\n    open('/tmp/x','w').write('hi')"))
res = ag.generate_vector_asset("evil icon")
check("A8 unsafe code is never executed and never retried",
      res is None and stub.calls == 1 and not os.path.exists(ag.cached_path("evil icon")),
      f"result={res} calls={stub.calls}")


# ── Part B: end to end, and the cache ─────────────────────────────────────────
print("\nPart B — a real drawing, a real SVG, billed once")

stub = use(StubLLM(TRIANGLE))
path = ag.generate_vector_asset("warning triangle")
check("B1 a drawing produces an SVG file", path and os.path.exists(path), str(path))
check("B2 the SVG passes the usability check", path and ag._svg_problems(path) is None,
      path and str(ag._svg_problems(path)))
svg_text = Path(path).read_text() if path else ""
check("B3 the SVG carries real drawing primitives", "<path" in svg_text or "<polyline" in svg_text)
check("B4 no white background rect is baked in (transparent savefig)",
      "#ffffff" not in svg_text.lower() or "opacity" in svg_text.lower())
side = json.loads(Path(path + ".json").read_text()) if path else {}
check("B5 a sidecar records keyword, code and attempt count",
      side.get("keyword") == "warning triangle" and "def draw" in side.get("code", "")
      and side.get("attempts") == 1)

calls_before = stub.calls
again = ag.generate_vector_asset("warning triangle")
check("B6 the second request is a cache HIT that spends no LLM call",
      again == path and stub.calls == calls_before, f"calls {calls_before}->{stub.calls}")

check("B7 the cache key is the normalized keyword",
      ag.slug("Grandfather Clock!") == "grandfather_clock"
      and ag.cached_path("x").startswith(TMP))


# ── Part C: accept-if-usable, and the repair round ────────────────────────────
print("\nPart C — exit code 0 proves nothing")

stub = use(StubLLM(EMPTY, EMPTY))
res = ag.generate_vector_asset("nothing at all")
check("C1 an empty canvas is rejected even though the code ran fine",
      res is None and stub.calls == 2, f"result={res} calls={stub.calls}")
check("C2 a rejected drawing leaves no partial file behind",
      not os.path.exists(ag.cached_path("nothing at all"))
      and not os.path.exists(ag.cached_path("nothing at all") + ".part"))

stub = use(StubLLM(CRASHES, CLOCK))
res = ag.generate_vector_asset("grandfather clock")
check("C3 code that crashes gets one repair round and the fix is accepted",
      res and os.path.exists(res) and stub.calls == 2, f"result={res} calls={stub.calls}")
side = json.loads(Path(res + ".json").read_text()) if res else {}
check("C4 the sidecar records that it took two attempts", side.get("attempts") == 2)
check("C5 the repair prompt carried the real error and the failed code",
      len(stub.prompts) == 2 and "deliberate failure" in stub.prompts[1]
      and "def draw" in stub.prompts[1])
check("C5b generation is billed to the cheap CODE tier, not the storyboard tier",
      set(stub.tasks) == {"code"}, str(stub.tasks))

check("C6 a non-SVG file is refused", ag._svg_problems(os.path.join(TMP, "nope.svg")) is not None)


# ── Part D: the storyboard pass ───────────────────────────────────────────────
print("\nPart D — splicing generated icons into the board")


def board():
    return {"visual_storyboard": [{
        "scene_index": 1, "description": "A clock ticks while a molecule spins",
        "elements": [
            {"id": "clock", "type": "svg_icon", "content": "pendulum clock"},
            {"id": "mol", "type": "chemical_molecule", "content": "C1=CC=CC=C1"},
            {"id": "title", "type": "text", "content": "Time"},
        ],
    }]}


warnings = [
    {"scene": 1, "element_id": "clock", "type": "svg_icon", "keyword": "pendulum clock",
     "status": "fallback", "provider": "native_shape"},
    {"scene": 1, "element_id": "mol", "type": "chemical_molecule", "keyword": "C1=CC=CC=C1",
     "status": "fallback", "provider": "native_shape"},
]

stub = use(StubLLM(CLOCK))
b = board()
still = ag.resolve_generated_assets(b, warnings)
clock_el = b["visual_storyboard"][0]["elements"][0]
check("D1 the icon element's content becomes an absolute generated path",
      os.path.isabs(clock_el["content"]) and clock_el["content"].endswith(".svg")
      and os.path.exists(clock_el["content"]), clock_el["content"])
check("D2 the molecule is left alone (RDKit/PubChem are authoritative)",
      b["visual_storyboard"][0]["elements"][1]["content"] == "C1=CC=CC=C1"
      and any(w["type"] == "chemical_molecule" for w in still))
check("D3 the resolved icon is no longer an asset warning",
      not any(w["element_id"] == "clock" for w in still), str(still))
check("D4 non-asset elements are untouched",
      b["visual_storyboard"][0]["elements"][2]["content"] == "Time")
check("D5 only one LLM call for one keyword", stub.calls == 1, f"calls={stub.calls}")

stub = use(StubLLM("def draw(ax):\n    raise ValueError('nope')"))
b2 = board()
b2["visual_storyboard"][0]["elements"][0]["content"] = "undrawable widget"
bad_warnings = [{**warnings[0], "keyword": "undrawable widget"}, warnings[1]]
still2 = ag.resolve_generated_assets(b2, bad_warnings)
check("D6 an ungeneratable icon keeps its keyword AND its warning (degrades as before)",
      b2["visual_storyboard"][0]["elements"][0]["content"] == "undrawable widget"
      and any(w["element_id"] == "clock" for w in still2), str(still2))

os.environ["ASSET_GEN"] = "0"
b3 = board()
stub = use(StubLLM(CLOCK))
still3 = ag.resolve_generated_assets(b3, warnings)
check("D7 ASSET_GEN=0 disables the pass entirely (no calls, board untouched)",
      stub.calls == 0 and b3["visual_storyboard"][0]["elements"][0]["content"] == "pendulum clock"
      and len(still3) == len(warnings))
os.environ["ASSET_GEN"] = "1"

check("D8 an empty warning list is a no-op",
      ag.resolve_generated_assets(board(), []) == [])


# ── Part E: resolved-but-wrong icons ──────────────────────────────────────────
# Iconify never says "no" — it answers "grandfather clock" with a plain clock face
# and reports success, so a generic-ancestor icon shipped with nothing flagged
# (reported by the user, 2026-08-14). A wrong hit is worse than a miss.
print("\nPart E — an icon that resolved to a generic ancestor is still wrong")

from lessonforge.engine.assets import icon_match_strength as strength  # noqa: E402

check("E1 an exact icon is strong",
      strength("clock", "mdi:clock") == "strong"
      and strength("test tube", "mdi:test-tube") == "strong")
check("E2 a generic ancestor is not strong",
      strength("grandfather clock", "mdi:clock-time-four") == "partial"
      and strength("water molecule", "mdi:water") == "partial")
check("E3 an unrelated icon is weak", strength("photosynthesis", "mdi:home") == "weak")
check("E4 filler words don't count against the match",
      strength("a simple clock icon", "mdi:clock") == "strong")
check("E5 inflections still count (5-char prefix)",
      strength("batteries", "mdi:battery") == "strong")

partial_probe = {"scene": 1, "element_id": "clock", "type": "svg_icon",
                 "keyword": "carriage clock", "status": "resolved",
                 "provider": "Iconify", "icon_id": "mdi:clock", "match": "partial"}
strong_probe = {"scene": 1, "element_id": "sun", "type": "svg_icon", "keyword": "sun",
                "status": "resolved", "provider": "Iconify", "icon_id": "mdi:sun",
                "match": "strong"}

os.environ.pop("ASSET_GEN_MODE", None)
check("E6 default mode draws partial matches but trusts strong ones",
      ag.should_generate(partial_probe) and not ag.should_generate(strong_probe))
os.environ["ASSET_GEN_MODE"] = "fallback"
check("E7 mode=fallback restores the old behaviour (misses only)",
      not ag.should_generate(partial_probe)
      and ag.should_generate({**partial_probe, "status": "fallback"}))
os.environ["ASSET_GEN_MODE"] = "always"
check("E8 mode=always draws even a strong match", ag.should_generate(strong_probe))
os.environ["ASSET_GEN_MODE"] = "weak"
check("E9 a molecule is never generated, in any mode",
      not ag.should_generate({"type": "chemical_molecule", "status": "fallback"}))

stub = use(StubLLM(CLOCK))
b4 = board()
b4["visual_storyboard"][0]["elements"][0]["content"] = "carriage clock"
still4 = ag.resolve_generated_assets(b4, [], probes=[partial_probe, strong_probe])
check("E10 a partial-match icon is replaced by a drawing",
      os.path.isabs(b4["visual_storyboard"][0]["elements"][0]["content"])
      and stub.calls == 1, b4["visual_storyboard"][0]["elements"][0]["content"])
check("E11 replacing a resolved icon adds no asset warning (it was never a miss)",
      still4 == [])


shutil.rmtree(TMP, ignore_errors=True)
failed = [n for n, ok in CHECKS if not ok]
print(f"\n{len(CHECKS) - len(failed)}/{len(CHECKS)} checks passed")
if failed:
    print("FAILED: " + "; ".join(failed))
sys.exit(1 if failed else 0)
