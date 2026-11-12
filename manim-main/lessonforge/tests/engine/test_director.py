"""Acceptance harness for the Visual Director (pipeline stage 3). No manim, no keys.

Pins the stage's two contracts (reference-architecture.md §6.4 / §7.3):
  * The LLM only ranks and schedules; application is deterministic and expressed as
    ordinary Storyboard-IR constructs (scale + appended hide/highlight events).
  * Strip-invariance / stand-aside: malformed or unsafe proposals are rejected
    individually, a malformed response leaves the board untouched, and the flag off
    means the original object passes through.

Run: .venv/bin/python stem_animation_lab/test_director.py
"""
import copy
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lessonforge.engine.pipeline import director as D  # noqa: E402

PASS, FAIL = [], []


def check(name, cond):
    (PASS if cond else FAIL).append(name)
    print(f"{'PASS' if cond else 'FAIL'} {name}")


def board():
    return {
        "topic": "t",
        "visual_storyboard": [{
            "scene_index": 1,
            "elements": [
                {"id": "title", "type": "text", "content": "Title"},
                {"id": "ax", "type": "coordinate_system", "content": "x:0-5, y:0-5"},
                {"id": "dot1", "type": "shape", "content": "point"},
                {"id": "lbl", "type": "text", "content": "P",
                 "relative_positioning": {"relative_to": "dot1", "direction": "UP",
                                          "buffer": 0.3}},
                {"id": "step1", "type": "text", "content": "Step 1", "scale": 1.0},
            ],
            "narration_cues": [
                {"cue": "c0", "animation_events": [
                    {"action": "show", "target": "title"},
                    {"action": "show", "target": "ax"}]},
                {"cue": "c1", "animation_events": [
                    {"action": "show", "target": "dot1"},
                    {"action": "show", "target": "lbl"}]},
                {"cue": "c2", "animation_events": [
                    {"action": "show", "target": "step1"}]},
                {"cue": "c3", "animation_events": [
                    {"action": "highlight", "target": "step1"}]},
            ],
            "wait_time": 1.0,
        }],
    }


def scene(b):
    return b["visual_storyboard"][0]


def events(b, k):
    return scene(b)["narration_cues"][k].get("animation_events") or []


# ── hierarchy → scale tiers ─────────────────────────────────────────────────
out, stats = D._apply_directives(board(), {"scenes": [{
    "scene_index": 1,
    "importance": {"title": "primary", "step1": "tertiary", "ax": "primary",
                   "ghost": "primary", "dot1": "sideways"},
}]})
els = {e["id"]: e for e in scene(out)["elements"]}
check("primary text is scaled up from the 0.7 default",
      els["title"]["scale"] == round(0.7 * 1.2, 3))
check("tertiary is scaled down from its own base scale",
      els["step1"]["scale"] == round(1.0 * 0.8, 3))
check("axes are never rescaled (zone claims depend on their footprint)",
      "scale" not in els["ax"])
check("unknown element id and unknown rank are rejected, not applied",
      stats["rejected"] >= 2 and "scale" not in els["dot1"])

big, _ = D._apply_directives(
    {"topic": "t", "visual_storyboard": [{
        "scene_index": 1,
        "elements": [{"id": "h", "type": "text", "content": "x", "scale": 1.1}],
        "narration_cues": [{"cue": "c"}], "wait_time": 0}]},
    {"scenes": [{"scene_index": 1, "importance": {"h": "primary"}}]})
check("scale tier is clamped at the ceiling",
      scene(big)["elements"][0]["scale"] == 1.15)

# ── lifetime → appended hide events, safety-checked ─────────────────────────
out, stats = D._apply_directives(board(), {"scenes": [{
    "scene_index": 1, "hide_after": {"title": 2},
}]})
check("a safe hide proposal appends a standard hide event at its cue",
      {"action": "hide", "target": "title"} in events(out, 2))

out, stats = D._apply_directives(board(), {"scenes": [{
    "scene_index": 1, "hide_after": {"title": 3},
}]})
check("a hide at the final cue is rejected",
      stats["hides"] == 0 and stats["rejected"] == 1)

out, stats = D._apply_directives(board(), {"scenes": [{
    "scene_index": 1, "hide_after": {"step1": 2},
}]})
check("a hide at (or before) the element's own birth cue is rejected",
      stats["hides"] == 0)

out, stats = D._apply_directives(board(), {"scenes": [{
    "scene_index": 1, "hide_after": {"dot1": 2},
}]})
check("hiding an anchor whose label is still alive is rejected",
      stats["hides"] == 0)

out, stats = D._apply_directives(board(), {"scenes": [{
    "scene_index": 1, "hide_after": {"lbl": 2, "dot1": 2},
}]})
check("anchor may die once its dependents die in the same pass",
      stats["hides"] == 2
      and {"action": "hide", "target": "dot1"} in events(out, 2))

dead = board()
scene(dead)["narration_cues"][1]["animation_events"].append(
    {"action": "hide", "target": "title"})
out, stats = D._apply_directives(dead, {"scenes": [{
    "scene_index": 1, "hide_after": {"title": 2},
}]})
check("an element the board already removes is never double-hidden",
      stats["hides"] == 0)

none_cue = board()
scene(none_cue)["narration_cues"][2]["animation_events"] = None
out, stats = D._apply_directives(none_cue, {"scenes": [{
    "scene_index": 1, "hide_after": {"title": 2},
}]})
check("a cue whose animation_events is None (schema default) still takes the hide",
      {"action": "hide", "target": "title"} in events(out, 2))

# ── semantic highlighting ───────────────────────────────────────────────────
out, stats = D._apply_directives(board(), {"scenes": [{
    "scene_index": 1, "highlight": [{"cue": 2, "target": "title"}],
}]})
check("a valid highlight is appended at its cue",
      {"action": "highlight", "target": "title"} in events(out, 2))

out, stats = D._apply_directives(board(), {"scenes": [{
    "scene_index": 1, "highlight": [{"cue": 3, "target": "title"}],
}]})
check("a cue that already highlights something is not given a second one",
      stats["highlights"] == 0)

out, stats = D._apply_directives(board(), {"scenes": [{
    "scene_index": 1,
    "hide_after": {"title": 1},
    "highlight": [{"cue": 2, "target": "title"}],
}]})
check("an element hidden earlier in the SAME pass cannot be highlighted after death",
      stats["highlights"] == 0 and stats["hides"] == 1)

out, stats = D._apply_directives(board(), {"scenes": [{
    "scene_index": 1, "highlight": [{"cue": 1, "target": "step1"}],
}]})
check("highlighting an element before it is born is rejected",
      stats["highlights"] == 0)

# ── strip-invariance / determinism / stand-aside ────────────────────────────
orig = board()
out, stats = D._apply_directives(orig, {"scenes": []})
check("empty directives leave the board byte-identical",
      json.dumps(out, sort_keys=True) == json.dumps(board(), sort_keys=True))
check("the input board object is never mutated (deep-copy application)",
      json.dumps(orig, sort_keys=True) == json.dumps(board(), sort_keys=True))

directives = {"scenes": [{"scene_index": 1, "importance": {"title": "primary"},
                          "hide_after": {"title": 2}}]}
a, _ = D._apply_directives(board(), directives)
b, _ = D._apply_directives(board(), directives)
check("application is deterministic (same directives, same board)",
      json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True))

out, stats = D._apply_directives(board(), {"scenes": [
    "garbage", {"scene_index": 99, "importance": {"title": "primary"}}]})
check("garbage scene entries and unknown scene_index are rejected wholesale",
      stats["rejected"] == 2 and stats["rescaled"] == 0)

# ── direct(): the LLM seam, stubbed ─────────────────────────────────────────
os.environ["VISUAL_DIRECTOR"] = "1"
stage = D.VisualDirectorStage()


class _Resp:
    def __init__(self, text):
        self.text = text


_real_call = D.call_llm_with_fallback
D.call_llm_with_fallback = lambda *a, **kw: _Resp(json.dumps(
    {"scenes": [{"scene_index": 1, "importance": {"title": "primary"},
                 "hide_after": {"title": 2}}]}))
out = stage.direct(board())
check("direct() applies stubbed directives (rescale + hide land in the board)",
      {"action": "hide", "target": "title"} in events(out, 2)
      and {e["id"]: e for e in scene(out)["elements"]}["title"]["scale"] == 0.84)

D.call_llm_with_fallback = lambda *a, **kw: _Resp("utter nonsense, not JSON {{{")
orig = board()
out = stage.direct(orig)
check("a malformed model response stands aside (no directives applied)",
      json.dumps(out, sort_keys=True) == json.dumps(board(), sort_keys=True))

D.call_llm_with_fallback = lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("boom"))
orig = board()
out = stage.direct(orig)
check("an LLM crash stands aside (no directives applied, input unmutated)",
      json.dumps(out, sort_keys=True) == json.dumps(board(), sort_keys=True)
      and json.dumps(orig, sort_keys=True) == json.dumps(board(), sort_keys=True))

# ── enlarge-to-fill (deterministic half; must survive an LLM outage) ────────
SPARSE = {"topic": "t", "visual_storyboard": [{
    "scene_index": 1,
    "elements": [{"id": "slab", "type": "shape", "content": "glass slab"},
                 {"id": "lbl", "type": "text", "content": "Glass Slab"}],
    "narration_cues": [{"cue": "c0", "animation_events": [
        {"action": "show", "target": "slab"}]}],
    "wait_time": 1.0}]}
out = stage.direct(SPARSE)   # LLM still raising from the check above
check("enlarge-to-fill applies even when the LLM is down (sparse scene boosted)",
      out["visual_storyboard"][0]["elements"][0]["scale"] == round(0.7 * 1.3, 3))
check("the sparse input board itself is never mutated",
      "scale" not in SPARSE["visual_storyboard"][0]["elements"][0])

dense = board()   # 5 elements — not sparse
check("a scene with enough elements is NOT boosted",
      D._enlarge_sparse_scenes(dense) == 0)

axes_sparse = {"topic": "t", "visual_storyboard": [{
    "scene_index": 1,
    "elements": [{"id": "ax", "type": "coordinate_system", "content": "x:0-5, y:0-5"},
                 {"id": "c", "type": "text", "content": "Caption"}],
    "narration_cues": [{"cue": "c0"}], "wait_time": 1.0}]}
check("a sparse scene containing axes is skipped (axes footprint already fills)",
      D._enlarge_sparse_scenes(axes_sparse) == 0)

capped = {"topic": "t", "visual_storyboard": [{
    "scene_index": 1,
    "elements": [{"id": "a", "type": "shape", "content": "box", "scale": 1.3}],
    "narration_cues": [{"cue": "c0"}], "wait_time": 1.0}]}
D._enlarge_sparse_scenes(capped)
check("enlarge-to-fill is clamped at its own ceiling",
      capped["visual_storyboard"][0]["elements"][0]["scale"] == D._SPARSE_SCALE_MAX)

# ── camera language: one semantic spotlight per scene ───────────────────────
out, stats = D._apply_directives(board(), {"scenes": [{
    "scene_index": 1, "focus": {"cue": 2, "target": "title"}}]})
check("a valid focus directive appends a standard focus event",
      {"action": "focus", "target": "title"} in events(out, 2) and stats["focus"] == 1)

out, stats = D._apply_directives(board(), {"scenes": [{
    "scene_index": 1,
    "highlight": [{"cue": 2, "target": "title"}],
    "focus": {"cue": 2, "target": "step1"}}]})
check("focus never shares a beat with a highlight (competing emphasis)",
      stats["focus"] == 0 and stats["highlights"] == 1)

out, stats = D._apply_directives(board(), {"scenes": [{
    "scene_index": 1, "hide_after": {"title": 1},
    "focus": {"cue": 2, "target": "title"}}]})
check("focus on an element already hidden in this pass is rejected",
      stats["focus"] == 0)

out, stats = D._apply_directives(board(), {"scenes": [{
    "scene_index": 1, "focus": {"cue": 9, "target": "title"}}]})
check("focus at an out-of-range cue is rejected", stats["focus"] == 0)

D.call_llm_with_fallback = _real_call
os.environ["VISUAL_DIRECTOR"] = "0"
orig = board()
check("flag off: direct() is a pure pass-through", stage.direct(orig) is orig)

print(f"\n{len(PASS)}/{len(PASS) + len(FAIL)} checks passed")
sys.exit(1 if FAIL else 0)
