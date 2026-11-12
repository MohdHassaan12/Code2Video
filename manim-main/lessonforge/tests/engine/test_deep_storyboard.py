"""Acceptance harness for the deep (multi-agent) storyboard front half.

No manim, no keys, no network (every LLM call and every fetch is stubbed).

    .venv/bin/python stem_animation_lab/test_deep_storyboard.py

What is pinned, and why each check exists:

  A. **Source intake** (`app/sources.py`) — chunking is citable and stable, the pack
     digest is the cache-freshness signal (same contract `grounding_chunks` already
     had), a budgeted pack truncates every source's tail instead of deleting whole
     sources, and every ingestion tier degrades to a warning rather than raising. A
     dead link must never fail a video.

  B. **Screen Ideator** (`app/pipeline/screens.py`) — the model proposes, code
     disposes: counts are clamped, the arc is forced (first screen opens, last one
     closes), junk screens are dropped, list-as-prose is tolerated, and an unusable
     plan returns None so the caller falls back to the single-call board.

  C. **Scene writers** (`app/pipeline/scene_writers.py`) — `_discipline` is the
     transpiler's bodyguard. Each check is a real render-time failure: a duplicate id
     silently overwrites a mobject; an event naming a missing element emits a call on
     an undefined variable, and per-scene scripts are isolated renders so that is a
     NameError that kills the whole scene; an element no cue shows falls through to
     cue 0, which is how six objects land on one beat. Plus: a failed writer degrades
     to a deterministic scene rather than leaving a hole in the arc.

  D. **Wiring** — the deep path is off by default; its cache key is a separate variant
     (turning the feature off must return the exact keys, and therefore the exact
     cached boards, that existed before it); and both prompts share ONE language-rule
     source, because two stages encoding one rule is the twin this repo's roadmap
     warns about.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import os  # noqa: E402

from lessonforge.engine import sources as S  # noqa: E402
from lessonforge.engine.pipeline import screens as SC  # noqa: E402
from lessonforge.engine.pipeline import scene_writers as SW  # noqa: E402
from lessonforge.engine.pipeline import deep_storyboard as D  # noqa: E402
from lessonforge.engine import storyboard as SB  # noqa: E402

CHECKS = []


def check(name, cond, detail=""):
    CHECKS.append((name, bool(cond)))
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"  — {detail}" if detail and not cond else ""))


# ─────────────────────────────────────────────────────────────────────────────
print("\nA. Source intake — citable, content-addressed, and never fatal")

pack = S.ingest(["Boiling is a phase change. Water boils at 100 degrees Celsius at "
                 "sea level. At altitude the pressure is lower, so water boils cooler."])
check("A1 pasted text becomes a usable source", pack.ok and len(pack.sources) == 1)
check("A2 the pack renders with citation tags", "[S1#1]" in pack.as_prompt())
check("A3 the digest is a content hash", len(pack.digest) == 16)

same = S.ingest(["Boiling is a phase change. Water boils at 100 degrees Celsius at "
                 "sea level. At altitude the pressure is lower, so water boils cooler."])
edited = S.ingest(["Boiling is a phase change. Water boils at 99 degrees Celsius."])
check("A4 identical sources give the same digest (cache hit)", same.digest == pack.digest)
check("A5 an edited source changes the digest (auto-regeneration)",
      edited.digest != pack.digest)

empty = S.ingest([])
check("A6 no sources is legal and yields an empty pack", not empty.ok and empty.digest == "")
check("A7 an empty pack renders no prompt text", empty.as_prompt() == "")

# A budget cut must not delete whole sources — with one long transcript and three
# short notes, plain concatenation silently drops the notes.
long_pack = S.ingest([{"kind": "text", "title": "long", "text": "Alpha sentence. " * 400},
                      {"kind": "text", "title": "short", "text": "Beta fact is unique."}])
budgeted = long_pack.as_prompt(char_budget=1500)
check("A8 a budgeted pack still contains every source", "[S2#1]" in budgeted)
check("A9 the budget is respected", len(budgeted) <= 1800, f"{len(budgeted)} chars")

bad = S.ingest([{"kind": "youtube", "url": "https://example.com/not-a-video"}])
check("A10 a malformed YouTube ref degrades to a warning, not an exception",
      not bad.ok and bad.warnings)
check("A11 youtube ids are extracted from every URL form",
      S.youtube_id("https://youtu.be/dQw4w9WgXcQ") == "dQw4w9WgXcQ"
      and S.youtube_id("https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=1") == "dQw4w9WgXcQ"
      and S.youtube_id("https://www.youtube.com/shorts/dQw4w9WgXcQ") == "dQw4w9WgXcQ"
      and S.youtube_id("a webpage") is None)
check("A12 html is reduced to readable text with scripts stripped",
      "keepme" in S.html_to_text("<html><script>var x=1</script><p>keepme</p></html>")
      and "var x" not in S.html_to_text("<html><script>var x=1</script><p>keepme</p></html>"))
check("A13 pre-resolved grounding chunks flow through the same machinery",
      S.pack_from_chunks(["chunk one text here", "chunk two text here"]).ok)
manifest = pack.manifest()
check("A14 the manifest carries provenance for the sidecar/UI",
      manifest["digest"] == pack.digest and manifest["sources"][0]["kind"] == "text")


# ─────────────────────────────────────────────────────────────────────────────
print("\nB. Screen Ideator — the model proposes, code disposes")

good_plan = {
    "through_line": "Why does a thrown ball land where it does?",
    "anchor": "a basketball thrown at a hoop",
    "screens": [
        {"index": 1, "role": "build", "title": "The throw", "beat": "A ball leaves the hand",
         "visual_kind": "simulation", "must_show": ["basketball at the hand", "hoop on the right",
                                                    "dashed arc"], "must_say": [
             {"fact": "The ball follows a curved path", "cite": "S1#1"}], "seconds": 12},
        {"index": 2, "role": "build", "title": "Two motions", "beat": "Split into x and y",
         "visual_kind": "diagram", "carries": "the same ball",
         "must_show": ["ball", "horizontal arrow", "vertical arrow"],
         "must_say": [{"fact": "Horizontal speed never changes", "cite": "S1#2"}]},
        {"index": 3, "role": "build", "title": "Predicting", "beat": "Compute the landing spot",
         "visual_kind": "derivation", "must_show": ["range formula", "ball", "landing marker"],
         "must_say": [{"fact": "Range is v squared sin 2 theta over g", "cite": ""}]},
    ],
}
plan = SC._normalize(json.loads(json.dumps(good_plan)), "Projectile motion", 5, 8)
check("B1 a well-formed plan normalizes", plan is not None and len(plan["screens"]) == 3)
check("B2 the first screen is forced to open the arc", plan["screens"][0]["role"] == "hook")
check("B3 the last screen is forced to close it", plan["screens"][-1]["role"] in ("recap", "payoff"))
check("B4 screen indices are renumbered by code",
      [s["index"] for s in plan["screens"]] == [1, 2, 3])
check("B5 the anchor survives", plan["anchor"] == "a basketball thrown at a hoop")

thin = json.loads(json.dumps(good_plan))
thin["screens"].append({"index": 4, "role": "recap", "title": "x", "beat": "",
                        "must_show": [], "must_say": []})
plan2 = SC._normalize(thin, "Projectile motion", 5, 8)
check("B6 a screen with nothing to show is dropped", len(plan2["screens"]) == 3)

capped = json.loads(json.dumps(good_plan))
capped["screens"] = capped["screens"] * 5          # 15 screens
plan3 = SC._normalize(capped, "T", 5, 8)
check("B7 screen count is clamped to the maximum", len(plan3["screens"]) == 8)

noisy = json.loads(json.dumps(good_plan))
noisy["screens"][0]["must_show"] = "circle labelled 84\ncircle labelled 84\nbranch to 12"
noisy["screens"][0]["visual_kind"] = "interpretive dance"
noisy["screens"][0]["seconds"] = "not a number"
plan4 = SC._normalize(noisy, "T", 5, 8)
first = plan4["screens"][0]
check("B8 a prose list is parsed and deduped", first["must_show"] == ["circle labelled 84",
                                                                     "branch to 12"])
check("B9 an unknown visual_kind falls back to a valid one",
      first["visual_kind"] in SC.VISUAL_KINDS)
check("B10 a non-numeric duration falls back", isinstance(first["seconds"], float))

no_anchor = json.loads(json.dumps(good_plan))
no_anchor["anchor"] = ""
check("B11 a missing anchor never stays empty (it disables every continuity check)",
      SC._normalize(no_anchor, "Projectile motion", 5, 8)["anchor"] == "Projectile motion")

check("B12 a plan with one usable screen is rejected",
      SC._normalize({"screens": [good_plan["screens"][0]]}, "T", 5, 8) is None)
check("B13 a non-dict response is rejected", SC._normalize(["nope"], "T", 5, 8) is None)
check("B14 an empty screens list is rejected", SC._normalize({"screens": []}, "T", 5, 8) is None)

cov = SC.coverage(plan["screens"][0], {
    "elements": [{"id": "a"}, {"id": "b"}],
    "narration_cues": [{"cue": "The ball follows a curved path to the hoop."}]})
check("B15 coverage counts planned objects against written elements",
      cov["objects_required"] == 3 and cov["elements_written"] == 2)
check("B16 a spoken fact is not reported missing", cov["missing_facts"] == [])
cov2 = SC.coverage(plan["screens"][0], {"elements": [], "narration_cues": [{"cue": "hello"}]})
check("B17 an unspoken required fact is reported", len(cov2["missing_facts"]) == 1)


# ─────────────────────────────────────────────────────────────────────────────
print("\nC. Scene writers — every gate is a real render-time failure")

screen = plan["screens"][0]

messy = {
    "description": "The throw",
    "elements": [
        {"id": "ball", "type": "shape", "content": "a basketball"},
        {"id": "ball", "type": "shape", "content": "a duplicate id"},
        {"id": "9lives", "type": "text", "content": "bad id start"},
        {"id": "hoop", "type": "shape", "content": "a ring"},
        {"id": "arc", "type": "shape", "content": "a curve", "connects": ["ball", "ghost"]},
        {"id": "label", "type": "text", "content": "speed",
         "relative_positioning": {"relative_to": "ghost", "direction": "UP"}},
        {"id": "blank", "type": "text", "content": "   "},
    ],
    "narration_cues": [
        {"cue": "A ball leaves the hand.", "animation_events": [
            {"action": "show", "target": "ball"},
            {"action": "show", "target": "ghost"},
            {"action": "show", "target": "ball"},
            {"action": "transform", "target": "hoop", "to": "ghost"},
            {"action": "teleport", "target": "hoop"},
        ]},
        {"cue": "It curves toward the hoop.", "animation_events": []},
    ],
    "wait_time": 99,
}
scene = SW._discipline(json.loads(json.dumps(messy)), screen, 1)
ids = [e["id"] for e in scene["elements"]]
check("C1 duplicate ids are made unique", len(ids) == len(set(ids)))
check("C2 an id that cannot be a variable name is repaired",
      all(not i[0].isdigit() for i in ids))
check("C3 an element with blank content is dropped", "blank" not in ids)
check("C4 an edge to a non-existent element is dropped, not emitted",
      all(e.get("connects") is None for e in scene["elements"]))
check("C5 a relative anchor to a missing element is dropped",
      all(e.get("relative_positioning") in (None, {}) or
          e["relative_positioning"]["relative_to"] in ids for e in scene["elements"]))
events = [ev for c in scene["narration_cues"] for ev in c["animation_events"]]
check("C6 events naming a missing element are dropped (per-scene renders are isolated)",
      all(ev["target"] in ids for ev in events))
check("C7 an unknown action is dropped", all(ev["action"] != "teleport" for ev in events))
check("C8 a transform with no valid destination is dropped",
      all(not (ev["action"] == "transform" and not ev.get("to")) for ev in events))
shows = [ev["target"] for ev in events if ev["action"] == "show"]
check("C9 every element is shown exactly once", sorted(shows) == sorted(ids))
check("C10 a duplicate entrance is dropped", len(shows) == len(set(shows)))
per_cue = [sum(1 for ev in c["animation_events"] if ev["action"] == "show")
           for c in scene["narration_cues"]]
check("C11 orphan elements are spread, not dumped on cue 0", max(per_cue) < len(ids),
      f"per cue: {per_cue}")
check("C12 wait_time is clamped to something sane", 0.5 <= scene["wait_time"] <= 3.0)
check("C13 the scene index and role come from the plan, not the model",
      scene["scene_index"] == 1 and scene["role"] == "hook")

fb = SW._fallback_scene(screen, plan)
fb_ids = [e["id"] for e in fb["elements"]]
check("C14 a failed writer still draws every planned object",
      len(fb["elements"]) == len(screen["must_show"]) + 1)
check("C15 the fallback speaks every required fact",
      len(fb["narration_cues"]) == len(screen["must_say"]))
check("C16 the fallback shows every element it declares",
      sorted(ev["target"] for c in fb["narration_cues"]
             for ev in c["animation_events"]) == sorted(fb_ids))

empty_scene = SW._discipline({"elements": [], "narration_cues": []}, screen, 2)
check("C17 a scene with no usable elements degrades instead of emitting an empty render",
      len(empty_scene["elements"]) > 0)

no_cue_scene = SW._discipline(
    {"elements": [{"id": "x", "type": "text", "content": "hi"}], "narration_cues": []},
    screen, 3)
check("C18 a scene with no cues still gets one (a beat with no narration renders nothing)",
      len(no_cue_scene["narration_cues"]) == 1
      and no_cue_scene["narration_cues"][0]["animation_events"])

# The writers fan out over screens; a failure in one must not lose the others.
_orig_write_one = SW._write_one
try:
    calls = {"n": 0}

    def _flaky(screen, *a, **k):
        calls["n"] += 1
        if screen["index"] == 2:
            raise RuntimeError("model down")
        return {"elements": [{"id": "e1", "type": "text", "content": screen["title"]}],
                "narration_cues": [{"cue": screen["beat"], "animation_events": []}]}

    SW._write_one = _flaky
    scenes, notes = SW.write_scenes(plan, topic="Projectile motion", client=None)
    check("C19 every screen produces a scene even when one writer fails",
          len(scenes) == len(plan["screens"]))
    check("C20 the failed screen is recorded as degraded, not silently dropped",
          [n["screen"] for n in notes] == [2])
    check("C21 a failing writer is retried once before degrading", calls["n"] == 4,
          f"{calls['n']} calls")
    check("C22 scene indices are sequential after the fan-in",
          [s["scene_index"] for s in scenes] == [1, 2, 3])
finally:
    SW._write_one = _orig_write_one


# ─────────────────────────────────────────────────────────────────────────────
print("\nD. Wiring — off by default, separately keyed, one language contract")

os.environ.pop("DEEP_STORYBOARD", None)
check("D1 the deep path is off by default", not D.enabled())
os.environ["DEEP_STORYBOARD"] = "1"
check("D2 DEEP_STORYBOARD=1 turns it on", D.enabled())
os.environ.pop("DEEP_STORYBOARD")

base = SB._CACHE.path("Topic", "hybrid", "hi-IN", "s", "9", "Physics", "", "", "english")
deep = SB._CACHE.path("Topic", "hybrid", "hi-IN", "s", "9", "Physics", "", "", "english",
                      variant=f"deep:{D.DEEP_VERSION}")
again = SB._CACHE.path("Topic", "hybrid", "hi-IN", "s", "9", "Physics", "", "", "english",
                       variant="")
check("D3 the deep path uses a separate cache key", base != deep)
check("D4 turning it off returns the exact pre-existing key", base == again)

rules_hybrid = SB.language_rules("hybrid", "hi-IN", "english")
rules_native = SB.language_rules("native", "ta-IN", "native")
check("D5 the shared language rules distinguish personas", rules_hybrid != rules_native)
check("D6 hybrid rules demand code-mix", "code-mixed" in rules_hybrid)
check("D7 the tech-terms policy reaches the shared rules",
      "ENGLISH ONLY" in rules_hybrid and "NATIVE" in rules_native)
check("D8 on-screen language is governed separately from narration",
      "ON-SCREEN TEXT LANGUAGE" in rules_hybrid)
check("D9 the scene writers use the SAME rule source as the single-call prompt "
      "(a twin would ship half a video in the wrong language)",
      "language_rules" in Path(SW.__file__).read_text()
      and "from ..storyboard import language_rules" in
      Path(SW.__file__).read_text())

sw_src = Path(SW.__file__).read_text()
check("D10 the writer prompt carries the structural-IR rules the transpiler needs",
      "connects" in sw_src and '"inside"' in sw_src and "ONE ELEMENT PER DRAWABLE OBJECT" in sw_src)
check("D11 the writer prompt offers the simulation type", '"simulation"' in sw_src)

# A `shape` naming only a primitive draws a bare ring on an empty canvas. It raises no
# asset warning — nothing failed — so it reads as healthy while the frame is empty.
# Measured on the 2026-08-15 live board: 14 of 16 shapes were "circle" / "point" /
# "arrow pointing right", which is why that video looked like scattered dots.
from lessonforge.engine.codegen_pipeline import _content_free_shapes  # noqa: E402

empty_board = [{"elements": [
    {"type": "shape", "content": "circle"},
    {"type": "shape", "content": "small circle"},
    {"type": "shape", "content": "arrow pointing right"},
    {"type": "shape", "content": "vertical dashed line"},
]}]
real_board = [{"elements": [
    {"type": "shape", "content": "the basketball at the top of its arc"},
    {"type": "shape", "content": "velocity arrow pointing right, constant length"},
    {"type": "shape", "content": "the ground line the ball lands on"},
    {"type": "shape", "content": "horizontal ground line"},
]}]
check("D15 a shape naming only a primitive is detected",
      len(_content_free_shapes(empty_board)) == 4)
check("D16 a shape naming a real object is never flagged",
      _content_free_shapes(real_board) == [], str(_content_free_shapes(real_board)))
check("D17 non-shape elements are out of scope",
      _content_free_shapes([{"elements": [{"type": "text", "content": "circle"}]}]) == [])
check("D18 both prompts carry the SAME shape rule (a twin would drift on the next edit)",
      SB.SHAPE_CONTENT_RULE in SW._SYSTEM.format(
          language_rules="L", shape_rule=SB.SHAPE_CONTENT_RULE, cues=3, seconds=12)
      and "NAME THE OBJECT" in SB.SHAPE_CONTENT_RULE)

board = D._assemble("Projectile motion", "3blue1brown", plan, [
    {"elements": [{"id": "m", "type": "math", "content": "v^2 = u^2 + 2as"}],
     "narration_cues": [{"cue": "hi"}]}])
check("D19 the assembled board matches the StoryboardResponse contract",
      set(["topic", "narrative", "key_theorems", "key_terms", "style_profile",
           "aspect_ratio", "visual_storyboard"]).issubset(board))
check("D20 the narrative spine is carried from the plan",
      board["narrative"]["anchor"] == plan["anchor"])
check("D21 key_theorems are derived from the board, not a second LLM call",
      board["key_theorems"] == ["v^2 = u^2 + 2as"])


# ─────────────────────────────────────────────────────────────────────────────
passed = sum(1 for _, ok in CHECKS if ok)
print(f"\n{passed}/{len(CHECKS)} checks passed")
sys.exit(0 if passed == len(CHECKS) else 1)
