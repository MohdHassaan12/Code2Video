"""Acceptance harness for the duration contract + composition variety rule.

No manim, no keys, no network.

    .venv/bin/python stem_animation_lab/test_duration_contract.py

What is pinned, and why each check exists:

  A. **Duration contract** (`app/storyboard.py`) — the knob used to die at the HTTP
     boundary (ce/ computed spec["duration"] and never sent it; the lab had no
     duration field at all). Rules that must hold: an UNSET target yields the legacy
     prompt line BYTE-IDENTICAL and the exact prior cache key (nothing already
     rendered re-bills — the tech_terms/deep-variant precedent); a SET target
     partitions the cache and derives scene count + narration word budget from ONE
     helper (a twin in the deep path would drift); garbage sanitizes to None and a
     huge request clamps to the ceiling §6's chapterized design owns.

  B. **Template variety** (`enforce_template_variety`) — the NLM variety rule in
     code: the 3rd+ consecutive scene reusing one layout_template is RESET to None
     (handed back to the zone allocator — code never invents a layout the model
     didn't ask for), while runs of ≤2 and template-less scenes are untouched.

  C. **Archetype zone templates** (`transpiler._apply_template_zones`) — ProcessFlow
     pins first/last unpositioned elements LEFT/RIGHT and leaves the middle to the
     allocator; BeforeAfter halves the unpositioned elements left/right so each state
     reads as one grouped picture; explicit positioning is never overridden (the
     rule the existing templates already follow).

  D. **Vividness floor metric** (`app/pipeline/screens.coverage`) — `sparse` counts
     the "one emblem plus a label" frame; measured, not enforced.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lessonforge.engine import storyboard as SB  # noqa: E402
from lessonforge.engine.pipeline import screens as SC  # noqa: E402
import lessonforge.transpiler as T  # noqa: E402

CHECKS = []


def check(name, cond, detail=""):
    CHECKS.append((name, bool(cond)))
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"  — {detail}" if detail and not cond else ""))


# ─────────────────────────────────────────────────────────────────────────────
print("\nA. Duration contract")

check("A1 unset target returns the legacy line byte-identical",
      SB.duration_directive(None) == SB._LEGACY_DURATION_LINE
      and SB.duration_directive(0) == SB._LEGACY_DURATION_LINE)
check("A2 legacy line is the exact pre-knob prompt text",
      SB._LEGACY_DURATION_LINE == ("* Target **4–6 scenes** for a 60–90 second video. "
                                   "More than 8 scenes wastes render budget without adding clarity."))

_d90 = SB.duration_directive(90)
lo, hi, words = SB.duration_scene_budget(90)
check("A3 set target names its budget in the directive",
      "~90-second" in _d90 and f"{words} words" in _d90 and f"{lo}–{hi} scenes" in _d90)
check("A4 word budget follows the planning wpm", words == int(90 / 60 * SB.WPM_SPOKEN))
check("A5 scene budget is a sane ordered range", 3 <= lo < hi <= 12)
_lo6, _hi6, _ = SB.duration_scene_budget(600)
check("A6 long target still respects the scene ceiling", _hi6 <= 12 and _lo6 <= 10)

check("A7 sanitize: garbage and non-positive are None",
      SB.sanitize_target_duration("abc") is None
      and SB.sanitize_target_duration(None) is None
      and SB.sanitize_target_duration(-5) is None
      and SB.sanitize_target_duration(0) is None)
check("A8 sanitize: clamps to [20, 600] and accepts numeric strings",
      SB.sanitize_target_duration(5) == 20
      and SB.sanitize_target_duration(10_000) == 600
      and SB.sanitize_target_duration("95") == 95)

cache = SB.StoryboardCache()
_base = cache.path("t", "hybrid", "hi-IN", "s", "g", "sub", "nt")
check("A9 unset target keeps the exact prior cache key",
      _base == cache.path("t", "hybrid", "hi-IN", "s", "g", "sub", "nt", variant=""))
check("A10 set target partitions the cache",
      _base != cache.path("t", "hybrid", "hi-IN", "s", "g", "sub", "nt", variant="dur:90"))
check("A11 different targets partition from each other",
      cache.path("t", "hybrid", "hi-IN", "s", "g", "sub", "nt", variant="dur:90")
      != cache.path("t", "hybrid", "hi-IN", "s", "g", "sub", "nt", variant="dur:120"))

_board = {"visual_storyboard": [
    {"narration_cues": [{"cue": "one two three"}, {"cue": "four five"}]},
    {"narration_cues": [{"cue": "six"}]},
]}
check("A12 narration_word_count sums every cue of every scene",
      SB.narration_word_count(_board) == 6)
check("A13 word count survives a malformed board",
      SB.narration_word_count({}) == 0
      and SB.narration_word_count({"visual_storyboard": [{}]}) == 0)

import inspect  # noqa: E402
check("A14 ideator accepts the target hint",
      "target_seconds" in inspect.signature(SC.plan_screens).parameters)
check("A15 storyboard impl accepts the target",
      "target_duration_s" in inspect.signature(SB.generate_storyboard_impl).parameters)

# ─────────────────────────────────────────────────────────────────────────────
print("\nB. Template variety rule")


def _scenes(*templates):
    return {"visual_storyboard": [{"layout_template": t} for t in templates]}


b = _scenes("SplitScreen", "SplitScreen", "SplitScreen", "SplitScreen")
n = SB.enforce_template_variety(b)
check("B1 3rd+ consecutive same template is reset",
      n == 2 and [s["layout_template"] for s in b["visual_storyboard"]]
      == ["SplitScreen", "SplitScreen", None, None])

b = _scenes("SplitScreen", "SplitScreen", "ProcessFlow", "SplitScreen")
check("B2 a run of two is never touched",
      SB.enforce_template_variety(b) == 0
      and b["visual_storyboard"][3]["layout_template"] == "SplitScreen")

b = _scenes(None, None, None, None)
check("B3 template-less scenes are untouched", SB.enforce_template_variety(b) == 0)

b = _scenes("FullCanvas", "FullCanvas", "FullCanvas", "TitleStageCaption",
            "TitleStageCaption", "TitleStageCaption")
n = SB.enforce_template_variety(b)
check("B4 each run is judged independently",
      n == 2 and b["visual_storyboard"][2]["layout_template"] is None
      and b["visual_storyboard"][5]["layout_template"] is None)

# ─────────────────────────────────────────────────────────────────────────────
print("\nC. Archetype zone templates")


def _els(n, positioned=()):
    out = []
    for i in range(n):
        el = {"id": f"e{i}"}
        if i in positioned:
            el["safe_zone_alignment"] = "TOP_CENTER"
        out.append(el)
    return out


els = _els(3)
T._apply_template_zones(els, "ProcessFlow")
check("C1 ProcessFlow pins first LEFT, last RIGHT, middle stays with the allocator",
      els[0].get("safe_zone_alignment") == "LEFT_CENTER"
      and "safe_zone_alignment" not in els[1]
      and els[2].get("safe_zone_alignment") == "RIGHT_CENTER")

els = _els(1)
T._apply_template_zones(els, "ProcessFlow")
check("C2 ProcessFlow with one unpositioned element does nothing",
      "safe_zone_alignment" not in els[0])

els = _els(4)
T._apply_template_zones(els, "BeforeAfter")
check("C3 BeforeAfter halves left/right (states stay grouped, not alternated)",
      [e.get("safe_zone_alignment") for e in els]
      == ["LEFT_CENTER", "LEFT_CENTER", "RIGHT_CENTER", "RIGHT_CENTER"])

els = _els(3)
T._apply_template_zones(els, "BeforeAfter")
check("C4 BeforeAfter odd count puts the extra element in the BEFORE half",
      [e.get("safe_zone_alignment") for e in els]
      == ["LEFT_CENTER", "LEFT_CENTER", "RIGHT_CENTER"])

els = _els(3, positioned=(0,))
T._apply_template_zones(els, "ProcessFlow")
check("C5 explicit positioning is never overridden",
      els[0]["safe_zone_alignment"] == "TOP_CENTER"
      and els[1].get("safe_zone_alignment") == "LEFT_CENTER"
      and els[2].get("safe_zone_alignment") == "RIGHT_CENTER")

# ─────────────────────────────────────────────────────────────────────────────
print("\nD. Vividness floor metric")

_screen = {"index": 1, "must_show": ["a", "b", "c"], "must_say": []}
check("D1 a two-element scene is flagged sparse",
      SC.coverage(_screen, {"elements": [{}, {}], "narration_cues": []})["sparse"] is True)
check("D2 a three-element scene is not sparse",
      SC.coverage(_screen, {"elements": [{}, {}, {}], "narration_cues": []})["sparse"] is False)

# ─────────────────────────────────────────────────────────────────────────────
failed = [n for n, ok in CHECKS if not ok]
print(f"\n{len(CHECKS) - len(failed)} passed, {len(failed)} failed")
if failed:
    for n in failed:
        print(f"  FAILED: {n}")
    sys.exit(1)
