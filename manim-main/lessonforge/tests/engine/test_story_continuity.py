"""Acceptance harness for story continuity (app/storyboard.narrative_problems).

No manim, no keys, no network.

    .venv/bin/python stem_animation_lab/test_story_continuity.py

The failure this pins is a real one, reported 2026-08-14: "there is no story in the
video being narrated, all the scenes are disconnected". The board behind it was a
*correct syllabus* — intro → components → independence → equations → quiz → summary —
and every symptom below is quoted from it:

  scene 2: "Projectile Motion ko samajhne ke liye, humein Initial Velocity ko..."
  scene 3: "Projectile Motion ki sabse important baat ye hai..."
  scene 4: "Ab dekhte hain Projectile Motion ke kuch important equations."

Every scene cold-starts by restating the topic, and the ball thrown in scene 1 never
comes back. The metric must flag exactly that, and must NOT flag a board that opens
each scene by continuing the previous one and carries its running example through.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lessonforge.engine import storyboard as SB  # noqa: E402

CHECKS = []


def check(name, cond, detail=""):
    CHECKS.append((name, bool(cond)))
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"  — {detail}" if detail and not cond else ""))


def scene(idx, cues, role=None, elements=None):
    return {"scene_index": idx, "role": role,
            "narration_cues": [{"cue": c} for c in cues],
            "elements": elements or []}


# The board as it actually came out (abridged, verbatim openings).
DISCONNECTED = {
    "topic": "Projectile Motion",
    "visual_storyboard": [
        scene(1, ["Namaste dosto! [SPEED: SPRINT] Aaj hum Projectile Motion ke bare mein sikhenge."]),
        scene(2, ["Projectile Motion ko samajhne ke liye, humein Initial Velocity ko break karna hoga."]),
        scene(3, ["Projectile Motion ki sabse important baat ye hai ki motions independent hote hain."]),
        scene(4, ["Ab dekhte hain Projectile Motion ke kuch important equations."]),
        scene(5, ["Chaliye, ek quick challenge karte hain! Horizontal Range ka formula kya hai?"]),
        scene(6, ["To, aaj humne Projectile Motion ke bare mein kya seekha?"]),
    ],
}

# The same lesson told as one story: an anchor that recurs, openings that continue.
CONNECTED = {
    "topic": "Projectile Motion",
    "narrative": {
        "through_line": "Can we predict where a thrown basketball will land before it lands?",
        "anchor": "a basketball thrown toward a hoop",
    },
    "visual_storyboard": [
        scene(1, ["Ye basketball hoop ki taraf ja rahi hai. [PAUSE] Kya hum bata sakte hain ye kahan girega?"],
              role="hook"),
        scene(2, ["Us basketball ki speed ko do hisson mein todte hain — aage aur upar."],
              role="build"),
        scene(3, ["Yahi twist hai: ball ka upar-neeche aur aage jaana ek dusre se independent hai."],
              role="turn"),
        scene(4, ["Ab in dono ko jodkar hum basketball ka landing point nikaal sakte hain."],
              role="payoff"),
        scene(5, ["To shuru wali basketball — humne uska landing spot predict kar liya."],
              role="recap"),
    ],
}


print("\nPart A — the board that caused the complaint must be flagged")
probs = SB.narrative_problems(DISCONNECTED)
blob = " | ".join(probs)
check("A1 the disconnected board is flagged at all", len(probs) >= 2, blob)
check("A2 cold opens are named with their scene numbers",
      any("cold open" in p for p in probs) and "2" in blob and "3" in blob and "4" in blob, blob)
check("A3 scene 1 is exempt — it is allowed to introduce the topic",
      not any(p.startswith("scenes 1") or ", 1," in p for p in probs), blob)
check("A4 the missing running example is named",
      any("running example" in p or "anchor" in p for p in probs), blob)
check("A5 a board with no roles is called a list of sections",
      any("not an arc" in p for p in probs), blob)


print("\nPart B — a board that tells one story must pass clean")
probs2 = SB.narrative_problems(CONNECTED)
check("B1 the connected board has no continuity problems", probs2 == [], str(probs2))

print("\nPart C — the parts of the metric, separately")

# An anchor that is declared but never returns is the exact 'ball never comes back' bug.
absent_anchor = {
    "topic": "Projectile Motion",
    "narrative": {"through_line": "q", "anchor": "a basketball thrown toward a hoop"},
    "visual_storyboard": [
        scene(1, ["Ye basketball hoop ki taraf ja rahi hai."], role="hook"),
        scene(2, ["Velocity ko components mein todte hain."], role="build"),
        scene(3, ["Dono motions independent hote hain."], role="turn"),
        scene(4, ["Equations se position nikaalte hain."], role="payoff"),
        scene(5, ["Yahi hai poora concept."], role="recap"),
    ],
}
p3 = SB.narrative_problems(absent_anchor)
check("C1 an anchor that never returns is flagged with its count",
      any("running example" in p and "1/5" in p for p in p3), str(p3))

# The anchor may be carried by a VISUAL, not only by narration.
visual_anchor = {
    "topic": "Projectile Motion",
    "narrative": {"through_line": "q", "anchor": "a basketball thrown toward a hoop"},
    "visual_storyboard": [
        scene(1, ["Dekhiye ye basketball."], role="hook"),
        scene(2, ["Speed ko todte hain."], role="build",
              elements=[{"type": "svg_icon", "content": "basketball"}]),
        scene(3, ["Ab dono ko jodte hain."], role="recap",
              elements=[{"type": "svg_icon", "content": "basketball hoop"}]),
    ],
}
check("C2 an anchor carried by on-screen elements counts too",
      not any("running example" in p for p in SB.narrative_problems(visual_anchor)),
      str(SB.narrative_problems(visual_anchor)))

no_recap = {
    "topic": "Projectile Motion",
    "narrative": {"through_line": "q", "anchor": "basketball"},
    "visual_storyboard": [
        scene(1, ["Ye basketball dekhiye."], role="hook"),
        scene(2, ["Basketball ki speed todte hain."], role="build"),
        scene(3, ["Basketball ka path banta hai."], role="build"),
    ],
}
check("C3 a board that never closes the loop is flagged",
      any("recap" in p for p in SB.narrative_problems(no_recap)),
      str(SB.narrative_problems(no_recap)))

check("C4 a single-scene board is exempt (nothing to connect)",
      SB.narrative_problems({"topic": "X", "visual_storyboard": [scene(1, ["hi"])]}) == [])
check("C5 an empty board never raises",
      SB.narrative_problems({}) == [] and SB.narrative_problems({"visual_storyboard": []}) == [])

# The recap scene is allowed to restate the topic — that is what a summary does.
recap_restates = {
    "topic": "Projectile Motion",
    "narrative": {"through_line": "q", "anchor": "basketball"},
    "visual_storyboard": [
        scene(1, ["Ye basketball dekhiye."], role="hook"),
        scene(2, ["Basketball upar jaati hai."], role="build"),
        scene(3, ["To aaj humne Projectile Motion ke bare mein seekha — basketball ka path."],
              role="recap"),
    ],
}
check("C6 a recap may restate the topic without being called a cold open",
      not any("cold open" in p for p in SB.narrative_problems(recap_restates)),
      str(SB.narrative_problems(recap_restates)))

print("\nPart D — the contract around the metric")
check("D1 narrative_problems never raises on a malformed board",
      SB.narrative_problems({"visual_storyboard": [{"scene_index": 1}, {"narration_cues": None}]}) is not None)
check("D2 the metric reports, it does not reject (the shape gate stays separate)",
      SB.storyboard_shape_problems(CONNECTED) == []
      and "narrative" not in " ".join(SB.storyboard_shape_problems(DISCONNECTED)))
check("D3 the scene schema carries the role field",
      "role" in __import__("lessonforge.engine.schemas", fromlist=["x"]).StoryboardScene.model_fields)
check("D4 the response schema carries the narrative spine",
      "narrative" in __import__("lessonforge.engine.schemas", fromlist=["x"]).StoryboardResponse.model_fields)

failed = [n for n, ok in CHECKS if not ok]
print(f"\n{len(CHECKS) - len(failed)}/{len(CHECKS)} checks passed")
if failed:
    print("FAILED: " + "; ".join(failed))
sys.exit(1 if failed else 0)
