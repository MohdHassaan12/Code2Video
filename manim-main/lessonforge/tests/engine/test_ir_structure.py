"""Acceptance harness for the structural IR (no manim import, no API keys).

The 2026-08-01 Prime-Factorization render exposed the root defect behind sparse,
arbitrary frames: the Storyboard IR was a **flat bag of positioned elements**. An
element could not say what it contained or connected to, so models wrote whole
sub-diagrams into one element's prose ("two branches from 84 to circles containing
12 and 7") and every object but one silently failed to exist.

Two fields close it — `connects: [a, b]` (edges) and
`relative_positioning.relation: "inside"` (containment) — with ALL geometry owned by
code: `viz_helpers.connector()` computes endpoints from the two shapes, and
`place_inside()` distributes siblings across the container.

Run: .venv/bin/python stem_animation_lab/test_ir_structure.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import lessonforge.transpiler as T  # noqa: E402

_passed = 0
_failed = 0


def check(label, cond):
    global _passed, _failed
    if cond:
        _passed += 1
        print(f"PASS {label}")
    else:
        _failed += 1
        print(f"FAIL {label}")


def el(eid, etype="shape", **kw):
    base = {"id": eid, "type": etype, "content": kw.pop("content", eid),
            "entrance_animation": "", "exit_animation": ""}
    base.update(kw)
    return base


def board(elements, cues=None):
    ids = [e["id"] for e in elements]
    return {
        "topic": "t", "style_profile": "3blue1brown/minimalist/neon",
        "aspect_ratio": "widescreen",
        "visual_storyboard": [{
            "scene_index": 1, "description": "d", "wait_time": 1,
            "layout_template": "FullCanvas", "elements": elements,
            "narration_cues": cues or [{
                "cue": "c",
                "animation_events": [{"action": "show", "target": i} for i in ids],
            }],
        }],
    }


TREE = [
    el("n84", content="circle containing 84", absolute_position=[0, 2]),
    el("n12", content="circle containing 12", absolute_position=[-2, 0]),
    el("n7", content="circle containing 7", absolute_position=[2, 0]),
    el("b1", content="chalk branch", connects=["n84", "n12"]),
    el("b2", content="arrow", connects=["n84", "n7"]),
]
TRAY = [
    el("tray", content="wide tray", scale=1.4, absolute_position=[0, -2]),
    el("c1", "svg_icon", content="candy",
       relative_positioning={"relative_to": "tray", "direction": "RIGHT", "buffer": 0.2, "relation": "inside"}),
    el("c2", "svg_icon", content="candy",
       relative_positioning={"relative_to": "tray", "direction": "RIGHT", "buffer": 0.2, "relation": "inside"}),
    el("c3", "svg_icon", content="candy",
       relative_positioning={"relative_to": "tray", "direction": "RIGHT", "buffer": 0.2, "relation": "inside"}),
]

code_tree = T.parse_schema_to_base_scene(board(TREE))
code_tray = T.parse_schema_to_base_scene(board(TRAY))

# ── A. Edges ─────────────────────────────────────────────────────────────────
print("\n-- A. connects -> a real edge between two shapes --")
check("edge emits connector() over the two endpoint vars",
      "connector(mobj_scene1_n84, mobj_scene1_n12" in code_tree)
check("second edge resolves its own endpoints",
      "connector(mobj_scene1_n84, mobj_scene1_n7" in code_tree)
check("content mentioning 'arrow' sets arrow=True",
      "mobj_scene1_n7, color=" in code_tree and "arrow=True" in code_tree)
check("plain branch is not an arrow", "arrow=False" in code_tree)
check("an edge gets NO position of its own (would tear it off its nodes)",
      "connector(" in code_tree
      and not any(ln.strip().startswith("mobj_scene1_b1 =") and (".move_to(" in ln or ".to_edge(" in ln)
                  for ln in code_tree.splitlines()))
check("nodes still render their contained value",
      "value_in(Circle(), '84')" in code_tree)

print("\n-- B. edges are ordered after both endpoints --")
pos = {v: code_tree.index(f"mobj_scene1_{v} =") for v in ("n84", "n12", "n7", "b1", "b2")}
check("b1 emitted after n84 and n12", pos["b1"] > pos["n84"] and pos["b1"] > pos["n12"])
check("b2 emitted after n84 and n7", pos["b2"] > pos["n84"] and pos["b2"] > pos["n7"])

print("\n-- C. malformed / foreign edges degrade, never crash --")
for bad, why in [(["n84"], "one id"), (["n84", "n84"], "self-loop"),
                 (["n84", "ghost"], "id not in this scene"), ("n84", "not a list")]:
    c = T.parse_schema_to_base_scene(board(TREE[:3] + [el("bx", content="branch", connects=bad)]))
    check(f"{why} -> no connector emitted, still valid Python",
          "connector(" not in c and compile(c, "<s>", "exec") is not None)

# ── D. Containment ───────────────────────────────────────────────────────────
print("\n-- D. relation:'inside' -> distributed inside the container --")
check("children emit place_inside() against the container var",
      "place_inside(" in code_tray and "mobj_scene1_tray, index=" in code_tray)
check("siblings get DISTINCT slot indices (not stacked on the centre)",
      "index=0, total=3" in code_tray and "index=1, total=3" in code_tray
      and "index=2, total=3" in code_tray)
check("a contained child is not also pinned to a frame edge",
      not any(ln.strip().startswith("mobj_scene1_c1 =") and ".to_edge(" in ln
              for ln in code_tray.splitlines()))
check("container itself keeps its own placement", ".move_to(RIGHT * 0 + UP * -2)" in code_tray)

single = T.parse_schema_to_base_scene(board([
    el("box", content="box", absolute_position=[0, 0]),
    el("dot1", content="dot",
       relative_positioning={"relative_to": "box", "direction": "UP", "buffer": 0.2, "relation": "inside"}),
]))
check("a lone child is index=0 total=1", "index=0, total=1" in single)

nextto = T.parse_schema_to_base_scene(board([
    el("box", content="box", absolute_position=[0, 0]),
    el("lab", "text", content="label",
       relative_positioning={"relative_to": "box", "direction": "UP", "buffer": 0.2}),
]))
check("relation defaults to next_to (unchanged behaviour)",
      ".next_to(mobj_scene1_box, UP" in nextto and "place_inside(" not in nextto)

orphan = T.parse_schema_to_base_scene(board([
    el("kid", content="dot",
       relative_positioning={"relative_to": "missing", "direction": "UP", "buffer": 0.2, "relation": "inside"}),
]))
check("'inside' a container that isn't in the scene does not emit place_inside",
      "place_inside(" not in orphan)

# ── E. Both codegen paths agree ──────────────────────────────────────────────
# parse_schema_to_scene_scripts returns [] for a single-scene board (nothing to
# parallelise), so the two-path comparison needs a board with two scenes.
print("\n-- E. per-scene scripts match the master path --")


def two_scene_board(a, b):
    bd = board(a)
    second = board(b)["visual_storyboard"][0]
    second["scene_index"] = 2
    bd["visual_storyboard"].append(second)
    return bd


scripts = T.parse_schema_to_scene_scripts(two_scene_board(TREE, TRAY))
check("per-scene path produced one script per scene", len(scripts) == 2)
joined = "\n".join(scripts)
check("per-scene path emits connector() for the tree scene", "connector(" in joined)
check("per-scene path emits place_inside() for the tray scene", "place_inside(" in joined)
check("per-scene slot indices are distributed too",
      "index=0, total=3" in joined and "index=2, total=3" in joined)
check("every per-scene script is valid Python",
      bool(scripts) and all(compile(s, "<s>", "exec") is not None for s in scripts))

check("master script is valid Python", compile(code_tree, "<s>", "exec") is not None)
check("tray script is valid Python", compile(code_tray, "<s>", "exec") is not None)

# ── F. Helpers are exported (a star-import miss = NameError at render) ───────
print("\n-- F. helpers reachable through the star import --")
import re  # noqa: E402
vh = open(os.path.join(os.path.dirname(os.path.abspath(__import__("lessonforge").__file__)), "viz_helpers.py")).read()
allblock = re.search(r"__all__\s*=\s*\[(.*?)\]", vh, re.S)
for fn in ("connector", "place_inside", "value_in"):
    check(f"{fn} is in viz_helpers.__all__", bool(allblock) and f'"{fn}"' in allblock.group(1))

# ── G. The LLM critic may adjust layout, never delete objects ────────────────
# Measured 2026-08-01: asked to tidy a tray of six sweets, the Layout QA Critic
# collapsed all six into ONE mobject and replaced place_inside() with its own
# arrange_in_grid — deleting five elements from the video. Acceptance checked only
# "does it parse and keep the class name".
print("\n-- G. critic acceptance preserves elements and structure --")
import lessonforge.engine.codegen as CG  # noqa: E402

GOOD = (
    "class STEMAnimation(VoiceoverScene):\n"
    "    def construct(self):\n"
    "        mobj_scene1_a = value_in(Circle(), '84')\n"
    "        mobj_scene1_b = Circle()\n"
    "        mobj_scene1_e = connector(mobj_scene1_a, mobj_scene1_b)\n"
    "        mobj_scene2_k = place_inside(Square(), mobj_scene1_a, index=0, total=1)\n"
)
check("element vars are detected",
      CG._element_vars(GOOD) == {"mobj_scene1_a", "mobj_scene1_b", "mobj_scene1_e", "mobj_scene2_k"})
dropped = GOOD.replace("        mobj_scene1_b = Circle()\n", "")
check("a rewrite that deletes an element is rejected",
      bool(CG._element_vars(GOOD) - CG._element_vars(dropped)))
check("an equal-element rewrite is not rejected on that ground",
      not (CG._element_vars(GOOD) - CG._element_vars(GOOD.replace("Circle()", "Square()"))))
dissolved = GOOD.replace("place_inside(Square(), mobj_scene1_a, index=0, total=1)", "Square().move_to(ORIGIN)")
check("dissolving place_inside is reported as structure loss",
      any("place_inside" in s for s in CG._structure_losses(GOOD, dissolved)))
check("dissolving connector is reported as structure loss",
      any("connector" in s for s in
          CG._structure_losses(GOOD, GOOD.replace("connector(mobj_scene1_a, mobj_scene1_b)", "Line(LEFT, RIGHT)"))))
check("an untouched rewrite reports no structure loss", CG._structure_losses(GOOD, GOOD) == [])
check("ADDING structure is never a loss",
      CG._structure_losses(GOOD, GOOD + "        mobj_scene1_z = connector(mobj_scene1_a, mobj_scene1_b)\n") == [])

# Zone anchors are code-owned too. Measured 2026-08-01: the critic turned a
# BOTTOM_CENTER caption's .to_edge(DOWN) into .move_to([0, BODY_Y, 0]) — BODY_Y is
# the frame's MIDDLE — dropping the caption through a factor tree. Nothing was
# deleted, so the element and structure guards both passed it.
ANCHORED = GOOD + "        mobj_scene1_cap = Text('x').to_edge(DOWN, buff=0.3)\n"
unanchored = ANCHORED.replace(".to_edge(DOWN, buff=0.3)", ".move_to([0, BODY_Y, 0])")
check("converting a zone anchor to raw coordinates is caught",
      CG._anchor_losses(ANCHORED, unanchored) is not None)
check("keeping the anchor is not a loss", CG._anchor_losses(ANCHORED, ANCHORED) is None)
check("adding an anchor is not a loss",
      CG._anchor_losses(ANCHORED, ANCHORED + "        m = Text('y').to_corner(UL)\n") is None)

# ── H. Graph layout: structure decides geometry ──────────────────────────────
# The governing rule is that the LLM never emits geometry. A storyboard's
# hand-written coordinates for tree nodes are exactly the guess that produced
# off-balance, overlapping diagrams, so for nodes in a declared graph the layout
# wins. Input below is deliberately terrible: every node piled on one point.
print("\n-- H. connects-declared graphs are laid out by code --")
PILE = [
    el("n84", content="circle containing 84", absolute_position=[-5, 3.5]),
    el("n12", content="circle containing 12", absolute_position=[-5, 3.4]),
    el("n7", content="circle containing 7", absolute_position=[-4.9, 3.5]),
    el("n3", content="circle containing 3", absolute_position=[-5, 3.45]),
    el("n4", content="circle containing 4", absolute_position=[-4.95, 3.5]),
    el("b1", content="branch", connects=["n84", "n12"]),
    el("b2", content="branch", connects=["n84", "n7"]),
    el("b3", content="branch", connects=["n12", "n3"]),
    el("b4", content="branch", connects=["n12", "n4"]),
]
laid = T._apply_graph_layout([dict(e) for e in PILE])
pos = {e["id"]: e.get("absolute_position") for e in laid if e.get("_graph_laid_out")}
check("every node in the graph was placed", set(pos) == {"n84", "n12", "n7", "n3", "n4"})
check("the model's piled-up coordinates were overridden",
      all(p != [-5, 3.5] for p in pos.values()))
check("root sits above its children", pos["n84"][1] > pos["n12"][1] > pos["n3"][1])
check("siblings share a row", pos["n12"][1] == pos["n7"][1] and pos["n3"][1] == pos["n4"][1])
check("siblings are separated horizontally", abs(pos["n12"][0] - pos["n7"][0]) > 1.0)
check("all nodes stay inside the safe band",
      all(-2.6 <= p[1] <= 2.4 and -6.0 <= p[0] <= 6.0 for p in pos.values()))
check("no two nodes share a position", len({tuple(p) for p in pos.values()}) == len(pos))
check("edges themselves are not repositioned",
      all(not e.get("_graph_laid_out") for e in laid if e.get("connects")))

small = T._apply_graph_layout([dict(e) for e in [
    el("a", content="circle"), el("b", content="circle"),
    el("x", content="branch", connects=["a", "b"])]])
check("a 2-node link is left alone (not a diagram)",
      not any(e.get("_graph_laid_out") for e in small))

inside_kid = T._apply_graph_layout([dict(e) for e in [
    el("n1", content="circle containing 1"), el("n2", content="circle containing 2"),
    el("n3b", content="circle containing 3"),
    el("lbl", "text", content="tag",
       relative_positioning={"relative_to": "n1", "direction": "UP", "buffer": 0.2, "relation": "inside"}),
    el("e1", content="branch", connects=["n1", "n2"]),
    el("e2", content="branch", connects=["n1", "n3b"]),
]])
check("a contained child is not yanked out by graph layout",
      not any(e.get("_graph_laid_out") for e in inside_kid if e["id"] == "lbl"))

two_comp = T._apply_graph_layout([dict(e) for e in [
    el("p1", content="circle"), el("p2", content="circle"), el("p3", content="circle"),
    el("q1", content="circle"), el("q2", content="circle"), el("q3", content="circle"),
    el("pe1", content="branch", connects=["p1", "p2"]), el("pe2", content="branch", connects=["p1", "p3"]),
    el("qe1", content="branch", connects=["q1", "q2"]), el("qe2", content="branch", connects=["q1", "q3"]),
]])
check("two independent graphs are both laid out",
      len([e for e in two_comp if e.get("_graph_laid_out")]) == 6)

check("graph layout runs inside the real codegen path",
      "_graph_laid_out" not in T.parse_schema_to_base_scene(board([dict(e) for e in PILE]))
      and "connector(" in T.parse_schema_to_base_scene(board([dict(e) for e in PILE])))


# ── Part E: forward references in the master script (2026-08-15) ──────────────
#
# The master path shares ONE construct() namespace, so an event reaching BACK to
# an earlier scene's mobject is legitimate. Reaching FORWARD is not — Python
# executes top-to-bottom, so the name is unbound and the whole script dies with a
# NameError. The id→var map used to be global and last-writer-wins, so when two
# scenes reused an element id, scene 2's `ball` event resolved to
# `mobj_scene3_ball`. Measured on a live board: 5 ids repeated across scenes (they
# are only made unique WITHIN a scene, since each screen is written by its own
# LLM call) and 2 scenes carried a forward reference.
import re as _re  # noqa: E402


def _use_before_def(code):
    defined, bad = set(), []
    for ln in code.split("\n"):
        m = _re.match(r"\s*(mobj_\w+)\s*=", ln)
        for u in _re.findall(r"\bmobj_\w+", ln):
            if u not in defined and not (m and u == m.group(1)):
                bad.append(u)
        if m:
            defined.add(m.group(1))
    return bad


def _scene(idx, elements, events):
    return {"scene_index": idx, "description": f"s{idx}", "wait_time": 1,
            "layout_template": "FullCanvas", "elements": elements,
            "narration_cues": [{"cue": "c", "animation_events": events}]}


# `ball` exists in BOTH scenes; scene 1 highlights it, scene 2 hides it.
_dup = {"topic": "t", "style_profile": "3blue1brown", "aspect_ratio": "widescreen",
        "visual_storyboard": [
            _scene(1, [el("ball", content="circle", position=[0, 0]),
                       el("tag", etype="text", content="Ball", position=[0, 2])],
                   [{"action": "show", "target": "ball"},
                    {"action": "show", "target": "tag"},
                    {"action": "highlight", "target": "ball"}]),
            _scene(2, [el("ball", content="circle", position=[1, 0])],
                   [{"action": "show", "target": "ball"},
                    {"action": "hide", "target": "ball"}]),
        ]}
_master = T.parse_schema_to_base_scene(_dup)
check("duplicate ids across scenes emit no forward reference",
      not _use_before_def(_master))
check("scene 1's event binds to scene 1's own variable, not scene 2's",
      "emphasize(mobj_scene1_ball" in _master and "emphasize(mobj_scene2_ball" not in _master)
check("scene 2's event binds to its own redeclaration",
      "FadeOut(mobj_scene2_ball)" in _master)

# A backward reference stays legal — clearing an earlier scene's prop is the
# documented reason the master path shares one namespace.
_back = {"topic": "t", "style_profile": "3blue1brown", "aspect_ratio": "widescreen",
         "visual_storyboard": [
             _scene(1, [el("prop", content="circle", position=[0, 0])],
                    [{"action": "show", "target": "prop"}]),
             _scene(2, [el("other", content="square", position=[1, 0])],
                    [{"action": "show", "target": "other"},
                     {"action": "hide", "target": "prop"}]),
         ]}
_bcode = T.parse_schema_to_base_scene(_back)
check("a backward cross-scene reference is still emitted",
      "FadeOut(mobj_scene1_prop)" in _bcode and not _use_before_def(_bcode))

# A target that only ever exists LATER must be dropped, not emitted raw — the
# `.get(id, id)` fallback would print the bare id and NameError just the same.
_fwd = {"topic": "t", "style_profile": "3blue1brown", "aspect_ratio": "widescreen",
        "visual_storyboard": [
            _scene(1, [el("here", content="circle", position=[0, 0])],
                   [{"action": "show", "target": "here"},
                    {"action": "highlight", "target": "later_only"}]),
            _scene(2, [el("later_only", content="square", position=[1, 0])],
                   [{"action": "show", "target": "later_only"}]),
        ]}
_fcode = T.parse_schema_to_base_scene(_fwd)
check("a forward-only target is dropped, not emitted as a bare id",
      "Indicate(later_only" not in _fcode and not _use_before_def(_fcode))
check("dropping a forward event leaves the script valid Python",
      compile(_fcode, "<master>", "exec") is not None)

print(f"\n{_passed}/{_passed + _failed} checks passed")
sys.exit(1 if _failed else 0)
