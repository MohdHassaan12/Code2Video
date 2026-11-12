"""Acceptance harness for the IR-enrichment agent pipeline.

No manim, no keys, no network (the LLM is stubbed).

    .venv/bin/python stem_animation_lab/test_agent_pipeline.py

Two things are pinned:

  A/B/C. **The Motion Director** — the agent that authors real movement, added
     2026-08-14 after "the video is not animated". Across three live boards the
     storyboard model wrote 92 `show`, 42 `hide`, 6 `highlight` and ZERO
     transform/move_to/focus, so half the transpiler's event vocabulary was dead.
     The agent proposes; THIS harness pins that code disposes — every gate below is
     a real way to break a scene (moving something before it exists, moving an edge
     off its endpoints, moving the axes everything is positioned against).

  D. **The registry** — order, isolation and provenance. One agent failing must
     never take the render down, and a chain of agents that reports nothing is
     impossible to debug.
"""
import sys
import copy
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import os  # noqa: E402
os.environ["MOTION_DIRECTOR"] = "1"

from lessonforge.engine.pipeline import motion as M  # noqa: E402
from lessonforge.engine.pipeline import registry as R  # noqa: E402

CHECKS = []


def check(name, cond, detail=""):
    CHECKS.append((name, bool(cond)))
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"  — {detail}" if detail and not cond else ""))


def board():
    """One scene: a ball shown at cue 0, an arrow at cue 1, axes, an edge, a child."""
    return {"visual_storyboard": [{
        "scene_index": 1, "description": "Forces on a ball",
        "elements": [
            {"id": "ball", "type": "shape", "content": "a circle"},
            {"id": "arrow", "type": "shape", "content": "an arrow"},
            {"id": "hoop", "type": "shape", "content": "a ring"},
            {"id": "axes", "type": "coordinate_system", "content": "x:0-10, y:0-10"},
            {"id": "link", "type": "shape", "content": "a line", "connects": ["ball", "hoop"]},
            {"id": "value", "type": "text", "content": "9.8",
             "relative_positioning": {"relative_to": "ball", "relation": "inside"}},
            {"id": "eq", "type": "math", "content": "F = ma"},
            {"id": "eq2", "type": "math", "content": "a = F/m"},
        ],
        "narration_cues": [
            {"cue": "A ball sits still.", "animation_events": [
                {"action": "show", "target": "ball"}, {"action": "show", "target": "axes"}]},
            {"cue": "A force acts on it.", "animation_events": [
                {"action": "show", "target": "arrow"}, {"action": "show", "target": "hoop"}]},
            {"cue": "So it accelerates.", "animation_events": [
                {"action": "show", "target": "eq"}, {"action": "show", "target": "eq2"}]},
            {"cue": "And that is the law.", "animation_events": []},
        ],
    }]}


def motions(*ms):
    return {"scenes": [{"scene_index": 1, "motions": list(ms)}]}


def events_of(b, cue):
    return b["visual_storyboard"][0]["narration_cues"][cue]["animation_events"]


print("\nPart A — the agent authors motion the storyboard never had")

src = board()
out, stats = M.apply_motions(src, motions(
    {"cue": 1, "action": "move_to", "target": "arrow", "to": "ball", "direction": "LEFT"},
    {"cue": 2, "action": "transform", "target": "eq", "to": "eq2"},
))
check("A1 a move_to is applied with its target, destination and direction",
      any(e == {"action": "move_to", "target": "arrow", "to": "ball", "direction": "LEFT"}
          for e in events_of(out, 1)), str(events_of(out, 1)))
check("A2 a transform is applied", any(e["action"] == "transform" and e["to"] == "eq2"
                                       for e in events_of(out, 2)))
check("A3 stats report what was added", stats["move_to"] == 1 and stats["transform"] == 1
      and stats["rejected"] == 0, str(stats))
check("A4 the input board is never mutated",
      src == board(), "apply_motions must work on a deep copy")
check("A5 existing events survive alongside the new ones",
      any(e["action"] == "show" and e["target"] == "arrow" for e in events_of(out, 1)))


print("\nPart B — the gates (each one is a way to break a scene)")

_, s = M.apply_motions(board(), motions(
    {"cue": 0, "action": "move_to", "target": "arrow", "to": "ball", "direction": "UP"}))
check("B1 an element cannot move BEFORE the cue that shows it",
      s["move_to"] == 0 and s["rejected"] == 1, str(s))

_, s = M.apply_motions(board(), motions(
    {"cue": 1, "action": "move_to", "target": "ghost", "to": "ball", "direction": "UP"}))
check("B2 a target that is not in this scene is dropped (per-scene renders are isolated)",
      s["move_to"] == 0 and s["rejected"] == 1)

_, s = M.apply_motions(board(), motions(
    {"cue": 1, "action": "move_to", "target": "axes", "to": "ball", "direction": "UP"}))
check("B3 axes/graphs are never moved — they are the coordinate frame",
      s["move_to"] == 0 and s["rejected"] == 1)

_, s = M.apply_motions(board(), motions(
    {"cue": 1, "action": "move_to", "target": "link", "to": "axes", "direction": "UP"}))
check("B4 an EDGE is never moved — its geometry comes from its endpoints",
      s["move_to"] == 0 and s["rejected"] == 1)

_, s = M.apply_motions(board(), motions(
    {"cue": 1, "action": "move_to", "target": "value", "to": "hoop", "direction": "UP"}))
check("B5 a contained child is never moved — its container places it",
      s["move_to"] == 0 and s["rejected"] == 1)

_, s = M.apply_motions(board(), motions(
    {"cue": 0, "action": "move_to", "target": "ball", "to": "arrow", "direction": "UP"}))
check("B6 an element cannot move next to something that has not appeared yet",
      s["move_to"] == 0 and s["rejected"] == 1)

_, s = M.apply_motions(board(), motions(
    {"cue": 1, "action": "move_to", "target": "ball", "to": "ball", "direction": "UP"}))
check("B7 a self-referential move is dropped", s["move_to"] == 0 and s["rejected"] == 1)

out, s = M.apply_motions(board(), motions(
    {"cue": 1, "action": "move_to", "target": "ball", "to": "hoop", "direction": "SIDEWAYS"}))
check("B8 an invalid direction falls back to RIGHT rather than emitting nonsense",
      s["move_to"] == 1 and events_of(out, 1)[-1]["direction"] == "RIGHT")

_, s = M.apply_motions(board(), motions(
    {"cue": 9, "action": "focus", "target": "ball"},
    {"cue": "x", "action": "focus", "target": "ball"},
    {"cue": 1, "action": "explode", "target": "ball"},
    "not-a-dict",
))
check("B9 out-of-range cues, unparseable cues and unknown actions are all dropped",
      s["focus"] == 0 and s["rejected"] == 4, str(s))

out, s = M.apply_motions(board(), motions(
    {"cue": 2, "action": "transform", "target": "eq", "to": "eq2"},
    {"cue": 3, "action": "move_to", "target": "eq", "to": "ball", "direction": "UP"}))
check("B10 an element consumed by a transform cannot move afterwards",
      s["transform"] == 1 and s["move_to"] == 0 and s["rejected"] == 1, str(s))

out, s = M.apply_motions(board(), motions(
    {"cue": 1, "action": "focus", "target": "ball"},
    {"cue": 1, "action": "focus", "target": "ball"}))
check("B11 a duplicate event in the same cue is dropped", s["focus"] == 1 and s["rejected"] == 1)


print("\nPart C — caps, and standing aside")

many = motions(*[{"cue": 1, "action": "focus", "target": t}
                 for t in ("ball", "arrow", "hoop", "axes", "eq")])
_, s = M.apply_motions(board(), many)
check("C1 motions per cue are capped", s["focus"] <= M.MAX_PER_CUE, str(s))

spread = motions(*[{"cue": c, "action": "highlight", "target": t}
                   for c, t in [(0, "ball"), (0, "axes"), (1, "arrow"), (1, "hoop"),
                                (2, "eq"), (2, "eq2")]])
_, s = M.apply_motions(board(), spread)
check("C2 motions per scene are capped", s["highlight"] <= M.MAX_PER_SCENE, str(s))

_, s = M.apply_motions(board(), {"scenes": [{"scene_index": 99, "motions": [
    {"cue": 0, "action": "focus", "target": "ball"}]}]})
check("C3 a directive for a scene that does not exist is dropped", s["rejected"] == 1)

check("C4 a malformed response leaves the board untouched",
      M.apply_motions(board(), {"nonsense": True})[0] == board()
      and M.apply_motions(board(), {"scenes": "not a list"})[0] == board())


class StubLLM:
    def __init__(self, text, boom=False):
        self.text, self.boom, self.calls = text, boom, 0

    def __call__(self, client, prompt, system_instruction=None, temperature=0.2,
                 task="general", keys=None, **kw):
        self.calls += 1
        if self.boom:
            raise RuntimeError("provider down")
        return type("R", (), {"text": self.text})()


stage = M.MotionDirectorStage()
M.call_llm_with_fallback = StubLLM('{"scenes":[{"scene_index":1,"motions":['
                                   '{"cue":1,"action":"move_to","target":"arrow",'
                                   '"to":"ball","direction":"LEFT"}]}]}')
b = board()
enriched = stage.enrich(b)
check("C5 the stage applies motion end to end",
      any(e["action"] == "move_to" for e in enriched["visual_storyboard"][0]
          ["narration_cues"][1]["animation_events"]))
check("C6 the stage never mutates the board it was given", b == board())

M.call_llm_with_fallback = StubLLM("", boom=True)
check("C7 an LLM failure means 'stand aside', not a crash",
      stage.enrich(board()) == board())

M.call_llm_with_fallback = StubLLM("I am not JSON at all")
check("C8 an unparseable response means 'stand aside'", stage.enrich(board()) == board())

os.environ["MOTION_DIRECTOR"] = "0"
M.call_llm_with_fallback = StubLLM('{"scenes":[]}')
check("C9 MOTION_DIRECTOR=0 is a pure pass-through (no call at all)",
      stage.enrich(board()) == board() and M.call_llm_with_fallback.calls == 0)
os.environ["MOTION_DIRECTOR"] = "1"


print("\nPart D — the registry: order, isolation, provenance")


class FakeAgent:
    def __init__(self, name, fn, on=True):
        self.name, self.fn, self.on = name, fn, on
        self.saw = None

    def enabled(self):
        return self.on

    def enrich(self, b, client=None, keys=None):
        self.saw = copy.deepcopy(b)
        return self.fn(b)


def add_event(tag):
    def _f(b):
        b = copy.deepcopy(b)
        b["visual_storyboard"][0]["narration_cues"][0]["animation_events"].append(
            {"action": "focus", "target": tag})
        return b
    return _f


a1 = FakeAgent("first", add_event("ball"))
a2 = FakeAgent("second", add_event("axes"))
out = R.enrich_storyboard(board(), agents=[a1, a2])
targets = [e.get("target") for e in out["visual_storyboard"][0]["narration_cues"][0]
           ["animation_events"] if e["action"] == "focus"]
check("D1 agents run in declaration order", targets == ["ball", "axes"], str(targets))
check("D2 a later agent sees what the earlier one did",
      any(e.get("action") == "focus" for e in a2.saw["visual_storyboard"][0]
          ["narration_cues"][0]["animation_events"]))

boom = FakeAgent("boom", lambda b: (_ for _ in ()).throw(RuntimeError("kaboom")))
survivor = FakeAgent("survivor", add_event("hoop"))
out = R.enrich_storyboard(board(), agents=[boom, survivor])
check("D3 one agent failing does not stop the chain",
      any(e.get("target") == "hoop" for e in out["visual_storyboard"][0]
          ["narration_cues"][0]["animation_events"]))
check("D4 the failure is recorded in the trace, not swallowed",
      any(t["agent"] == "boom" and "error" in t for t in out["agent_trace"]),
      str(out.get("agent_trace")))

junk = FakeAgent("junk", lambda b: {"not": "a board"})
out = R.enrich_storyboard(board(), agents=[junk, survivor])
check("D5 an agent returning an unusable board is ignored, previous board kept",
      out["visual_storyboard"][0]["scene_index"] == 1
      and any(e.get("target") == "hoop" for e in out["visual_storyboard"][0]
              ["narration_cues"][0]["animation_events"]))

off = FakeAgent("off", add_event("nope"), on=False)
out = R.enrich_storyboard(board(), agents=[off])
check("D6 a disabled agent is skipped and says so",
      any(t["agent"] == "off" and t["ran"] is False for t in out["agent_trace"])
      and not any(e.get("target") == "nope" for e in out["visual_storyboard"][0]
                  ["narration_cues"][0]["animation_events"]))
check("D7 the trace counts events before and after each agent",
      all({"events_before", "events_after"} <= set(t)
          for t in R.enrich_storyboard(board(), agents=[a1])["agent_trace"] if t.get("ran")))
check("D8 the input board is never mutated by the registry",
      (lambda b: (R.enrich_storyboard(b, agents=[a1]), b == board())[1])(board()))
check("D9 the real registry declares director before motion",
      [a.name for a in R.AGENTS] == ["visual_director", "motion_director"],
      str([a.name for a in R.AGENTS]))

failed = [n for n, ok in CHECKS if not ok]
print(f"\n{len(CHECKS) - len(failed)}/{len(CHECKS)} checks passed")
if failed:
    print("FAILED: " + "; ".join(failed))
sys.exit(1 if failed else 0)
