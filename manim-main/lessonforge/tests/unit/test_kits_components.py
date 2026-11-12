"""The components kit: lesson-visuals components (TypeScript, drawn through Node) as a subject kit.

Hermetic: ``tests/unit/conftest.py`` points LESSON_VISUALS_DIR at ``tests/unit/fixtures/lv_components``, a pinned snapshot
of six of the owner's own components in their current contract (named states, number states, situations, layer and
ground; see the README there), plus temporary copies in a temp folder. One optional test checks a whole real tree when
LESSON_VISUALS_DIR was set to one in the shell. Skipped, with the reason, when Node 22.6+ is missing. No model, no network.
"""
import json
import logging
import math
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from lessonforge import kits, knobs
from lessonforge.kits import components as C
from lessonforge.longform import component_lib as lib

REASON = lib.unavailable_reason()
pytestmark = pytest.mark.skipif(bool(REASON), reason=f"components are not available here: {REASON}")

REAL = lib.components_dir()
SIX = {"force_block", "test_tube", "child", "leaf_section", "number_line", "simple_pendulum"}
SNAPSHOT = Path(__file__).parent / "fixtures" / "lv_components"
REAL_TREE = os.environ.get("LF_TEST_REAL_LV", "")          # what LESSON_VISUALS_DIR was in the shell (conftest keeps it)
KIT = kits.get("components")


def lesson(*beats):
    return {"title": "t", "chapters": [{"title": "ONE", "learning_goal": "g", "role": "explain", "beats": list(beats)}]}


def beat(narration, figure=None, steps=None, quiz=None):
    out = {"narration": narration, "steps": steps if steps is not None else [{"say": narration[:20], "show": "x"}]}
    if figure is not None:
        out["figure"] = figure
    if quiz:
        out["quiz"] = quiz
    return out


def fig(cid="force_block", params=None, state=None, **extra):
    inner = {"id": cid}
    if params is not None:
        inner["params"] = params
    if state is not None:
        inner["state"] = state
    return {"kind": "component", "params": inner, **extra}


def step(focus, say="the block", show="x"):
    return {"say": say, "show": show, "focus": focus}


@pytest.fixture
def folder(tmp_path, monkeypatch):
    """A private lesson-visuals folder with physics/force_block.ts and chemistry/test_tube.ts copied in."""
    root = tmp_path / "lv"
    for sub, name in (("physics", "force_block"), ("chemistry", "test_tube")):
        (root / "components" / sub).mkdir(parents=True, exist_ok=True)
        shutil.copy(REAL / sub / f"{name}.ts", root / "components" / sub / f"{name}.ts")
    monkeypatch.setenv(lib.ENV_DIR, str(root))
    return root


# ---------------------------------------------------------------- the owner's real components

def test_the_catalogue_finds_the_real_components():
    cat = {e["id"]: e for e in lib.catalogue(classes=None)}
    assert SIX <= set(cat), sorted(SIX - set(cat))
    fb = cat["force_block"]
    assert fb["subject"] == "physics" and fb["classes"] == [8, 9] and fb["size"] == [360.0, 240.0]
    assert fb["parts"] == ["surface_ground", "block", "force_arrows", "net_force_arrow", "micro_zoom"]
    assert {c["title"] for c in fb["chapters"]} >= {"Force and Pressure", "Friction", "Force and Laws of Motion"}
    names = {p["name"]: p for p in fb["params"]}
    assert names["applied_force"]["type"] == "number" and (names["applied_force"]["min"], names["applied_force"]["max"]) == (0, 50)
    assert names["surface"]["options"] == ["smooth ice", "wood", "rough sandpaper", "rollers"] and names["applied_force"]["say"]
    assert fb["states"] == {"motion": ["rest", "sliding_right", "sliding_left", "impending"]} and "left_hook" in fb["anchors"]
    assert "friction" in fb["keywords"] and "block" in fb["keywords"]
    assert lib.broken() == [] or all("error" in b for b in lib.broken())
    json.dumps(lib.catalogue(classes=None))                                  # plain data


def test_classes_come_from_meta_ncert():
    assert lib.classes_of(["Class 8, Ch 11 Force and Pressure"]) == {8}
    assert lib.classes_of(["Class 9, Ch 9 Gravitation (Newton's falling apple, F = G M m / d^2)", "Class 8, Ch 11 Force"]) == {8, 9}
    assert lib.classes_of(["Any class 6-10 story, activity or classroom scene"]) == {6, 7, 8, 9, 10}
    assert lib.classes_of(["something free-form", ""]) == set() and lib.classes_of(None) == set()
    chapters = lib.chapters_of(["Class 9, Ch 9 Gravitation (Newton's falling apple, F = G M m / d^2)", "Any class 6-10 x"])
    assert chapters == [{"cls": 9, "ch": 9, "title": "Gravitation"}]
    scope = {e["id"] for e in lib.catalogue()}                                # classes 6-9 by default
    assert {"child", "test_tube", "leaf_section", "simple_pendulum"} <= scope           # generic and 'Class 10 plus a 6-9 string' stay
    assert {e["id"] for e in lib.catalogue(subjects=["physics"])} == {"force_block", "simple_pendulum"}
    # the looser strings the library writes now: "Class 8 Science: Light (reflection)", "Class 11, Chemistry lab: titration"
    assert lib.classes_of(["Class 8 Science: Light (reflection, laws of reflection)"]) == {8}
    assert lib.classes_of(["Class 11, Chemistry lab: titration", "Class 12, Chemistry lab: titration"]) == {11, 12}
    assert lib.classes_of(["Class 6-8 Science: x"]) == {6, 7, 8}
    assert {e["subject"] for e in lib.catalogue(subjects=["physics"])} == {"physics"}


def test_validate_refuses_what_the_component_cannot_draw():
    ok = lib.get("force_block")["example"]
    assert lib.validate("force_block", ok) == [] and lib.validate("force_block", {}) == []          # defaults are merged
    far = " ".join(lib.validate("force_block", {"applied_force": 999}))
    assert "applied_force must be from 0 to 50" in far and "999" in far
    assert "must be one of: smooth ice, wood" in " ".join(lib.validate("force_block", {"surface": "mud"}))
    assert "not a parameter of force_block" in " ".join(lib.validate("force_block", {"colour": "red"}))
    assert "must be a number" in " ".join(lib.validate("force_block", {"applied_force": True}))      # a boolean is not a number
    assert "must be a number" in " ".join(lib.validate("force_block", {"mass_kg": "5"}))
    assert "must be a number" in " ".join(lib.validate("force_block", {"mass_kg": float("nan")}))
    assert "true or false" in " ".join(lib.validate("force_block", {"show_micro": "yes"}))
    assert "no digits" in " ".join(lib.validate("force_block", {"label": "a 50 kg block"}))          # a number must be a parameter
    assert lib.validate("force_block", {"label": "heavy block"}) == []
    assert "not a state of force_block" in " ".join(lib.validate("force_block", {}, {"speed": "fast"}))
    assert "state motion must be one of" in " ".join(lib.validate("force_block", {}, {"motion": "flying"}))
    assert "must be an object" in " ".join(lib.validate("force_block", ["x"]))
    with pytest.raises(lib.ComponentError, match="there is no component 'nope'.*force_block"):
        lib.validate("nope", {})
    cross = lib.validate("test_tube", {"liquid": "none", "level": 0.5})                              # the component's own rule
    assert cross and "empty tube" in " ".join(cross)


def test_draw_is_deterministic_ordered_and_complete():
    a = lib.draw("force_block", {"applied_force": 30, "opposing_force": 15}, {"motion": "sliding_right"})
    b = lib.draw("force_block", {"applied_force": 30, "opposing_force": 15}, {"motion": "sliding_right"})
    assert a == b and json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)
    meta = lib.get("force_block")
    assert [n for n, _ in a["parts"]] == meta["parts"] and all(isinstance(svg, str) for _, svg in a["parts"])
    assert all(len(p) == 2 and all(math.isfinite(x) for x in p) for p in a["anchors"].values()) and set(a["anchors"]) == set(meta["anchors"])
    assert a["params"]["label"] == "wooden block" and a["params"]["mass_kg"] == 5                     # defaults were merged
    assert all("undefined" not in lab["text"] for lab in a["labels"]) and a["state"] == {"motion": "sliding_right"}
    assert "net force 15" in " ".join(a["facts"]) and {30.0, 15.0, 5.0} <= set(a["numbers"])          # the CODE worked it out
    assert lib.draw("force_block", {"applied_force": 10})["labels"] != a["labels"]
    t = lib.draw("test_tube", {}, {"bubbles": "none"})
    assert dict(t["parts"])["bubbles"] == "" and [n for n, _ in t["parts"]][3] == "bubbles"            # an empty part is kept
    assert lib.empty_parts(t) == ["bubbles"] and lib.empty_parts(lib.draw("test_tube", {}, {"bubbles": "many"})) == []
    with pytest.raises(lib.ComponentError, match="applied_force must be from 0 to 50"):
        lib.draw("force_block", {"applied_force": 51})


def test_every_real_component_draws_its_example_in_every_state():
    for e in lib.catalogue(classes=None):
        states = [{k: v} for k, vs in e["states"].items()
                  for v in (vs if isinstance(vs, list) else [vs["min"], (vs["min"] + vs["max"]) / 2, vs["max"]])] or [None]
        for st in states:
            d = lib.draw(e["id"], e["example"], st)
            assert [n for n, _ in d["parts"]] == e["parts"] and d["parts"][0][1].strip(), (e["id"], st)
            assert all(re.search(r"<(?:path|line|polyline|polygon|rect|circle|ellipse|g|text)\b", svg) or not svg.strip()
                       for _, svg in d["parts"])


# ---------------------------------------------------------------- the kit on real components

def test_the_kit_is_registered_served_and_describes_itself():
    assert KIT is not None and kits.serving("component") is KIT and "component" in kits.kinds()
    assert not KIT.legacy and KIT.builder == {"component": "lessonforge.longform.component_figure:component"}
    row = next(r for r in kits.describe() if r["name"] == "components")
    assert {"physics", "chemistry", "characters", "biology", "maths"} <= set(row["subjects"]) and {6, 7, 8, 9} <= set(row["classes"]) <= set(range(1, 13))   # the classes the files serve, inside scope
    assert "leaf" in row["keywords"] and row["served"] is True
    assert "component" not in kits.BUILTIN_KINDS
    with knobs.applied({"LESSONFORGE_KITS": "0"}):
        assert kits.serving("component") is None and kits.rules_for(["components"]) == ""


def test_a_good_component_lesson_has_no_faults_and_gaps_are_filled():
    good = lesson(beat("The push is {param applied_force} newtons and the friction is {param opposing_force} newtons.",
                       fig(params={"applied_force": 30, "opposing_force": 15}, state={"motion": "rest"}),
                       steps=[step("block"), step("force_arrows")]))
    done, issues = KIT.settle(good)
    assert issues == [] and not KIT.unfilled(done)
    assert done["chapters"][0]["beats"][0]["narration"] == "The push is 30 newtons and the friction is 15 newtons."
    assert KIT.fill_gap("param mass_kg", KIT.solve(fig()))[0] == "5"                                  # a default is filled too


def test_numbers_must_be_parameters_labels_or_gaps():
    f = fig(params={"applied_force": 30, "opposing_force": 15})
    def faults(text, figure=f):
        return KIT.settle(lesson(beat(text, figure)))[1]
    assert faults("A 30 N push and a 15 N friction leave a net force of 15 N.") == []             # 15 is on the label
    assert faults("The block weighs 5 kg.") == []                                                     # a default parameter
    bad = faults("The push is 40 newtons.")
    assert len(bad) == 1 and "40" in bad[0] and "does not show" in bad[0]
    assert faults("Newton's 3rd law, Class 8, step 2 of the 1/2 plan, m2.") == []                     # ordinals, class, fractions
    assert any("no parameter" in i for i in faults("It is {param speed}."))
    assert any("can only be {param NAME}" in i for i in faults("It is {applied_force + 1}."))
    assert any("is not a number" in i for i in faults("It is {param surface}."))
    assert any("no components figure" in i for i in KIT.settle(lesson(beat("It is {param mass_kg}.")))[1])
    quiz = {"question": "How big is the push?", "options": ["{param applied_force}", "45", "10"], "answer_index": 0,
            "why": ["right", "no", "no"]}
    done, issues = KIT.settle(lesson(beat("Look.", f, quiz=quiz)))
    assert done["chapters"][0]["beats"][0]["quiz"]["options"][0] == "30"
    assert all(KIT.expected_fault(i, done) for i in issues) and len(issues) == 2                     # wrong options are the point


def test_the_kit_refuses_an_unknown_component_param_state_or_part():
    unknown = KIT.settle(lesson(beat("Look.", fig("magic_lens"))))[1]
    assert len(unknown) == 1 and "there is no component 'magic_lens'" in unknown[0] and "force_block" in unknown[0]
    assert any("is not a parameter" in i for i in KIT.settle(lesson(beat("Look.", fig(params={"colour": 1}))))[1])
    assert any("applied_force must be from 0 to 50" in i for i in KIT.settle(lesson(beat("Look.", fig(params={"applied_force": 80}))))[1])
    assert any("is not a state" in i for i in KIT.settle(lesson(beat("Look.", fig(state={"colour": "red"}))))[1])
    assert any("needs \"id\"" in i for i in KIT.settle(lesson(beat("Look.", {"kind": "component", "params": {"params": {}}})))[1])
    assert any("takes id, params and state" in i for i in KIT.settle(lesson(beat("Look.", {"kind": "component", "id": "child", "values": {}})))[1])
    part = KIT.settle(lesson(beat("Look.", fig(), steps=[step("wheel")])))[1]
    assert len(part) == 1 and "'wheel' is not a part of component force_block" in part[0] and "surface_ground, block" in part[0]
    assert KIT.settle(lesson(beat("Look.", fig(), steps=[step("Block"), step("net-force-arrow")])))[1] == []     # as the writer spells focus
    assert any("draws nothing in this state" in i for i in
               KIT.settle(lesson(beat("Look.", fig("test_tube", state={"bubbles": "none"}), steps=[step("bubbles")])))[1])
    # a beat that keeps the previous picture is checked against that picture's parts
    carried = lesson(beat("Look.", fig()), beat("More.", None, steps=[step("wheel")]))
    assert any("beat 2" in i and "'wheel' is not a part" in i for i in KIT.settle(carried)[1])


def test_a_component_that_serves_only_other_classes_is_refused(folder):
    # classes 1 to 12 are in scope (2026-11-09), so the file is for a class past the last one
    src = (folder / "components/physics/force_block.ts").read_text()
    new = re.sub(r'ncert: \[[^\]]*\]', 'ncert: ["Class 12, Ch 12 Electricity"]', src, count=1).replace('id: "force_block"', 'id: "grade_twelve"')
    (folder / "components/physics/grade_twelve.ts").write_text(new)
    assert "grade_twelve" in {e["id"] for e in lib.catalogue()}                       # in scope now
    narrowed = lib.scope_classes("6-9")                                              # what LESSONFORGE_SCOPE_CLASSES=6-9 gives
    assert narrowed == (6, 7, 8, 9)
    assert lib.scope_classes("junk") == tuple(range(1, 13)) and lib.scope_classes("3,5-6") == (3, 5, 6)
    assert "grade_twelve" not in {e["id"] for e in lib.catalogue(classes=narrowed)}
    assert lib.get("grade_twelve")["classes"] == [12]


def test_the_figure_is_made_canonical_and_parts_are_revealed_in_order():
    flat = {"kind": "component", "id": "force_block", "params": {"applied_force": 30, "opposing_force": 20, "mass_kg": 5}}
    done, issues = KIT.settle(lesson(
        beat("One.", flat, steps=[step("micro_zoom"), step("force_arrows")]),
        beat("Two.", fig(params={"opposing_force": 20}), steps=[step("block")]),
        beat("Three.", fig(params={"opposing_force": 20}, state={"motion": "rest"}), steps=[step("net_force_arrow")])))
    assert issues == []
    beats = [b for ch in done["chapters"] for b in ch["beats"]]
    first, second, third = (b["figure"] for b in beats)
    # the three beats are one run of two drawings: each carries the same span (plan S6, test_kits_components_frame.py); the rest
    # of the figure is what it was
    span = first["params"].pop("span")
    assert span == second["params"].pop("span") == third["params"].pop("span") and len(span) == 2
    assert first == {"kind": "component", "params": {"id": "force_block", "params": {"opposing_force": 20}, "reveal":
                     ["block", "force_arrows", "micro_zoom"]}, "manifest": first["manifest"]}          # defaults dropped, voice order
    assert first == second and first["manifest"].startswith("force_block-")                          # same drawing, same figure
    assert third["manifest"] != first["manifest"] and third["params"]["reveal"] == ["net_force_arrow"]
    assert KIT.normalise_figure(KIT.normalise_figure(flat)) == KIT.normalise_figure(flat)             # idempotent
    assert KIT.normalise_figure(fig("nope")) is None
    for f in (first, second, third):
        f["params"]["span"] = span
    assert KIT.settle(done)[0] == done                                                                # settling again changes nothing


def test_describe_and_repair_prompt_carry_what_code_worked_out():
    text = KIT.describe(fig(params={"applied_force": 30, "opposing_force": 15}))
    assert "applied_force 30" in text and "net force 15" in text and "surface_ground, block" in text
    assert "there is no component" in KIT.describe(fig("nope"))
    bad = lesson(beat("The push is 40 newtons.", fig(params={"applied_force": 30})))
    prompt = kits.repair_prompt(bad, KIT.settle(bad)[1])
    assert "applied_force 30" in prompt and "40" in prompt


def test_rules_are_generated_from_the_catalogue():
    text = C.rules_text()
    for cid in SIX:
        assert f'  "{cid}" - ' in text or f"  {cid} (" in text, cid          # a sheet, or a line of the index
    assert "param applied_force (number 0 to 50; default 30)" in text
    one = kits.rules_for(["components:force_block"])
    assert one.startswith("\n\nSUBJECT KIT components") and '  "force_block" - ' in one and '  "test_tube" - ' not in one
    assert "net_force_arrow" in one and "no component 'zzz'" in kits.rules_for(["components:zzz,force_block"])
    plain = kits.rules_for(["components"])
    assert '  "test_tube" - ' in plain                                                                # all (few enough for full sheets)
    used = lesson(beat("Look.", fig("child", params={"who": "Meera"})))
    assert '  "child" - ' in kits.rules_for_lesson(used) and '  "force_block" - ' not in kits.rules_for_lesson(used)


def test_it_mixes_with_other_subjects_and_other_kits_keep_their_beats():
    mixed = lesson(
        beat("The push is {param applied_force} newtons.", fig(params={"applied_force": 30})),
        beat("The equation has {atoms of O left} oxygen atoms.", {"kind": "chem_reaction", "equation": "H2 + O2 -> H2O"}))
    comp, chem = kits.get("components"), kits.get("chemistry")
    assert comp.settle(mixed)[1] == [] and chem.settle(mixed)[1] == []
    assert kits.lesson_faults(mixed) == []
    done = kits.settle_active(mixed)
    assert [b["narration"] for b in done["chapters"][0]["beats"]] == ["The push is 30 newtons.",
                                                                       "The equation has 2 oxygen atoms."]


# ---------------------------------------------------------------- a folder of its own: new files, broken files, safety

def test_a_new_file_is_picked_up_without_any_code_change(folder):
    assert [e["id"] for e in lib.catalogue(classes=None)] == ["test_tube", "force_block"]
    assert KIT.settle(lesson(beat("Look.", fig("new_one"))))[1] != []
    src = (folder / "components/physics/force_block.ts").read_text()
    (folder / "components/physics/new_one.ts").write_text(src.replace('id: "force_block"', 'id: "new_one"').replace(
        '"Force and friction block on surface"', '"A brand new block"'))
    ids = [e["id"] for e in lib.catalogue(classes=None)]
    assert ids == ["test_tube", "force_block", "new_one"] or set(ids) == {"test_tube", "force_block", "new_one"}
    assert KIT.settle(lesson(beat("It is {param mass_kg} kg.", fig("new_one", params={"mass_kg": 7}))))[0]["chapters"][0]["beats"][0][
        "narration"] == "It is 7 kg."
    assert KIT.solve(fig("new_one")).entry["title"] == "A brand new block"
    assert '  "new_one" - ' in kits.rules_for(["components"]) and "A brand new block" in C.rules_text()
    # a whole new subject folder (biology) too
    (folder / "components/biology").mkdir()
    (folder / "components/biology/leaf.ts").write_text(src.replace('id: "force_block"', 'id: "leaf"').replace(
        'subject: "physics"', 'subject: "biology"'))
    assert [e["id"] for e in lib.catalogue(subjects=["biology"])] == ["leaf"] and "biology" in KIT.subjects
    (folder / "components/physics/new_one.ts").unlink()
    assert "new_one" not in {e["id"] for e in lib.catalogue(classes=None)}


def test_an_edited_component_is_not_served_from_an_old_drawing(folder):
    path = folder / "components/physics/force_block.ts"
    before = lib.draw("force_block", {})
    path.write_text(path.read_text().replace('text: "wood"', 'text: "planks"') if 'text: "wood"' in path.read_text()
                    else path.read_text().replace("wooden block", "oak block"))
    after = lib.draw("force_block", {})
    assert after["labels"] != before["labels"] or after["parts"] != before["parts"]


def test_a_file_that_fails_is_listed_as_broken_never_raised(folder):
    (folder / "components/physics/throws.ts").write_text('throw new Error("boom");\nexport const meta = {};\n')
    (folder / "components/physics/wrong_id.ts").write_text(
        (folder / "components/physics/force_block.ts").read_text().replace('id: "force_block"', 'id: "other"'))
    (folder / "components/physics/no_draw.ts").write_text('export const meta = { id: "no_draw", subject: "physics" };\n')
    (folder / "components/physics/not_ts.ts").write_text("export const meta = ;;; syntax error\n")
    cat = {e["id"] for e in lib.catalogue(classes=None)}
    assert cat == {"force_block", "test_tube"}
    bad = {b["id"]: b["error"] for b in lib.broken()}
    assert set(bad) == {"throws", "wrong_id", "no_draw", "not_ts"}
    assert "boom" in bad["throws"] and "must match the file name" in bad["wrong_id"] and "validate and draw" in bad["no_draw"]
    assert KIT.settle(lesson(beat("Look.", fig("throws"))))[1] and lib.draw("force_block", {})            # the rest still works


MINI = """export const meta = {
  id: "ID", title: "Mini", subject: "physics", ncert: ["Class 8, Ch 1 Mini"], size: [100, 100] as [number, number],
  params: { n: { type: "number", min: 0, max: 10, default: 3, say: "how many" } },
  parts: ["outline", "dots"], states: {}, anchors: ["mid"], example: { n: 3 },
};
export function validate(p: { n: number }): string[] { return p.n >= 0 && p.n <= 10 ? [] : ["n must be between 0 and 10"]; }
export function draw(p: { n: number }, state = {}) {
  BODY
  return {
    parts: { outline: `<rect x="10" y="10" width="80" height="80" fill="none" stroke="#1B2033"/>`, dots: `<circle cx="50" cy="50" r="${p.n}"/>` },
    anchors: { mid: [50, 50] },
    labels: [{ part: "outline", text: `n ${p.n}${TAIL}`, at: [50, 96], side: "below" }],
  };
}
"""


def mini(folder, cid, body="", tail='""'):
    (folder / "components/physics" / f"{cid}.ts").write_text(MINI.replace("ID", cid).replace("BODY", body).replace("TAIL", tail))


def test_a_component_runs_without_reach_beyond_its_folder(folder):
    mini(folder, "fine")
    mini(folder, "sneaky", body='process.getBuiltinModule("node:fs").readFileSync("/etc/hostname", "utf8");')
    mini(folder, "spawner", body='process.getBuiltinModule("node:child_process").execSync("echo hi");')
    assert lib.draw("fine", {})["numbers"] == [3.0]
    for cid in ("sneaky", "spawner"):
        with pytest.raises(lib.ComponentError, match="could not be drawn"):
            lib.draw(cid, {})
    assert lib.draw("force_block", {})                                                                # others are unaffected


def test_a_component_that_draws_different_pictures_for_the_same_input_is_refused(folder):
    mini(folder, "flicker", body="(globalThis as any).__c = ((globalThis as any).__c ?? 0) + 1;",
         tail='`, ${(globalThis as any).__c}`')
    with pytest.raises(lib.ComponentError, match="different picture each time"):
        lib.draw("flicker", {})
    issues = KIT.settle(lesson(beat("Look.", fig("flicker"))))[1]
    assert len(issues) == 1 and "different picture each time" in issues[0]


def test_a_component_with_a_bad_drawing_is_refused(folder):
    (folder / "components/physics/bad_tag.ts").write_text(MINI.replace("ID", "bad_tag").replace("BODY", "").replace("TAIL", '""').replace(
        '<circle cx="50" cy="50" r="${p.n}"/>', '<image href="x.png"/>'))
    (folder / "components/physics/nan_part.ts").write_text(MINI.replace("ID", "nan_part").replace("BODY", "").replace("TAIL", '""').replace(
        'r="${p.n}"', 'r="${Number.NaN}"'))
    with pytest.raises(lib.ComponentError, match="uses <image>, which is not allowed"):
        lib.draw("bad_tag", {})
    with pytest.raises(lib.ComponentError, match="NaN"):
        lib.draw("nan_part", {})


def test_the_folder_may_be_given_with_or_without_components(folder, monkeypatch):
    assert lib.components_dir() == folder / "components"
    monkeypatch.setenv(lib.ENV_DIR, str(folder / "components"))
    assert lib.components_dir() == folder / "components" and {e["id"] for e in lib.catalogue(classes=None)} == {"force_block", "test_tube"}


def test_a_draw_is_cached_by_content_not_run_twice(folder, monkeypatch):
    calls = []
    real = lib._run
    monkeypatch.setattr(lib, "_run", lambda jobs: (calls.append(len(jobs)), real(jobs))[1])
    lib.draw("force_block", {"applied_force": 12.5})
    n = len(calls)
    lib.draw("force_block", {"applied_force": 12.5}); lib.validate("force_block", {"applied_force": 12.5})
    assert len(calls) == n                                                                           # no second Node process
    lesson_figs = [("force_block", {"applied_force": v}, None) for v in (1, 2, 3)]
    lib.prefetch(lesson_figs)
    assert len(calls) == n + 1                                                                       # three drawings, ONE process


# ---------------------------------------------------------------- unavailable: the kit steps aside

def test_without_node_the_kit_is_skipped_with_one_log_line(monkeypatch, caplog):
    monkeypatch.setattr(lib, "node_path", lambda: None)
    assert not lib.available() and "node was not found" in lib.unavailable_reason()
    with caplog.at_level(logging.WARNING, logger="lessonforge.kits"):
        assert C._register() is None
    lines = [r for r in caplog.records if "components kit not registered" in r.getMessage()]
    assert len(lines) == 1 and "node was not found" in lines[0].getMessage()
    with pytest.raises(lib.ComponentError, match="node was not found"):
        lib.draw("force_block", {"mass_kg": 13.25})                                                   # not drawn before: needs Node
    assert [k.name for k in kits.all_kits() if k.name == "chemistry"]                                # the others are untouched


def test_without_the_folder_the_kit_is_skipped(monkeypatch, tmp_path, caplog):
    monkeypatch.setenv(lib.ENV_DIR, str(tmp_path / "nowhere"))
    assert not lib.available() and "does not exist" in lib.unavailable_reason()
    empty = tmp_path / "empty"
    (empty / "components").mkdir(parents=True)
    monkeypatch.setenv(lib.ENV_DIR, str(empty))
    assert "holds no" in lib.unavailable_reason()
    with caplog.at_level(logging.WARNING, logger="lessonforge.kits"):
        assert C._register() is None
    assert len(caplog.records) == 1


def test_importing_the_kits_with_no_node_is_silent_and_pure():
    import subprocess
    import sys
    code = (f"import sys; sys.path[:0] = {sys.path!r}; import lessonforge.kits as k; "
            "bad = [m for m in ('manim', 'numpy', 'lessonforge.harness', 'lessonforge.longform.figures') if m in sys.modules]; "
            "assert not bad, bad; assert k.get('components') is None and k.get('motion'); print('ok')")
    done = subprocess.run([sys.executable, "-I", "-c", code], capture_output=True, text=True, timeout=120,
                          env={"PATH": "", "HOME": "/nonexistent", "LESSON_VISUALS_DIR": "/nonexistent"})
    assert done.returncode == 0 and done.stdout.strip().endswith("ok"), done.stderr[-800:]
    assert done.stderr.count("components kit not registered") == 1


# ---------------------------------------------------------------- the Manim side (component_figure)

def _manim():
    pytest.importorskip("manim", reason="manim is not installed here")
    from lessonforge.longform import component_figure as CF, figures
    return CF, figures


def _box(mob):
    return (float(mob.get_left()[0]), float(mob.get_right()[0]), float(mob.get_bottom()[1]), float(mob.get_top()[1]))


def test_every_real_component_builds_part_by_part_in_meta_order():
    CF, _ = _manim()
    for e in lib.catalogue(classes=None):
        f = CF.component({"id": e["id"], "params": e["example"]})
        assert list(f.parts) == e["parts"] == list(f.art) and f.kind == "component", e["id"]
        assert set(f.anchors) == set(e["anchors"]) and f.hidden == [] and f.shown == set(e["parts"])
        assert len(f.parts[e["parts"][0]].family_members_with_points()) > 0, "the outline draws something"
        card = _box(f.card)
        assert all(card[0] <= _box(m)[0] + 1e-6 and _box(m)[1] <= card[1] + 1e-6 and card[2] <= _box(m)[2] + 1e-6
                   and _box(m)[3] <= card[3] + 1e-6 for m in f.parts.values()), "the paper card holds the whole drawing"
        assert f.card.get_fill_opacity() == 1 and f.build == [("fade", [f.card] + [f.parts[p] for p in e["parts"]])]


def test_svg_points_land_where_draw_put_them_after_the_y_flip(folder):
    CF, _ = _manim()
    # asymmetric content in every corner, so a part that is flipped about its own middle cannot pass by accident
    body = ('(globalThis as any).__x = 1;')
    (folder / "components/physics/corners.ts").write_text(
        MINI.replace("ID", "corners").replace("BODY", body).replace("TAIL", '""').replace(
            '<circle cx="50" cy="50" r="${p.n}"/>',
            '<rect x="20" y="15" width="10" height="20"/><rect x="70" y="60" width="20" height="5"/>').replace(
            "anchors: { mid: [50, 50] }", "anchors: { mid: [50, 50] }").replace(
            "[50, 50] }", "[50, 50], top_left: [20, 15] }").replace('anchors: ["mid"]', 'anchors: ["mid", "top_left"]'))
    drawn = lib.draw("corners", {})
    f = CF.component({"id": "corners"})
    w, h = drawn["size"]
    k = f.k
    at = lambda x, y: ((x - w / 2) * k, (h / 2 - y) * k)   # noqa: E731 - the documented formula
    left, right, bottom, top = _box(f.art["dots"])
    (x0, y0), (x1, y1) = at(20, 15), at(90, 65)
    assert (left, right, top, bottom) == pytest.approx((x0, x1, y0, y1), abs=1e-3)
    outline = _box(f.art["outline"])
    assert outline == pytest.approx((at(10, 90)[0], at(90, 10)[0], at(10, 90)[1], at(90, 10)[1]), abs=1e-3)
    assert top > bottom and f.anchor("top_left")[:2] == pytest.approx(at(20, 15), abs=1e-6)      # y grows upward on the stage
    label = f.labels[0]
    assert float(label.get_center()[0]) == pytest.approx(at(50, 96)[0], abs=1e-3)                  # side "below": centred on x
    assert float(label.get_center()[1]) == pytest.approx(at(50, 96)[1], abs=1e-3)


def test_a_person_stands_head_up_with_the_hair_above_the_face_above_the_feet():
    CF, _ = _manim()
    f = CF.component({"id": "child", "params": {"who": "Meera"}})
    hair, face, body = (_box(f.art[n]) for n in ("hair", "face", "body"))                           # (left, right, bottom, top)
    assert hair[3] > face[3] > face[2] > body[2] and abs(body[3] - hair[3]) < 0.2                      # hair over face over feet
    assert f.anchor("head")[1] > f.anchor("center")[1] > f.anchor("feet")[1]
    assert f.anchor("hand_left")[0] < f.anchor("hand_right")[0]
    ground = CF.component({"id": "force_block", "params": {}})
    assert _box(ground.art["block"])[2] > _box(ground.art["surface_ground"])[3] - 0.02              # the block stands on the ground


def test_text_inside_a_part_is_written_again_with_text_not_given_to_the_svg_parser(folder):
    CF, _ = _manim()
    from manim import Text
    svg, texts = CF.split_text('<rect x="1" y="2" width="3" height="4"/><text x="50" y="30" font-size="12" text-anchor="middle" '
                               'fill="#112233">M<tspan> &amp; m</tspan></text>')
    assert "<text" not in svg and "<rect" in svg
    assert texts == [{"text": "M & m", "x": 50.0, "y": 30.0, "px": 12.0, "anchor": "middle", "fill": "#112233"}]
    (folder / "components/physics/lettered.ts").write_text(
        MINI.replace("ID", "lettered").replace("BODY", "").replace("TAIL", '""').replace(
            '<circle cx="50" cy="50" r="${p.n}"/>', '<text x="50" y="40" font-size="14" text-anchor="middle">M</text><circle cx="20" cy="20" r="4"/>'))
    f = CF.component({"id": "lettered"})
    written = [m for m in f.art["dots"].submobjects if isinstance(m, Text)]
    assert len(written) == 1 and written[0].text == "M" and len(f.art["dots"].family_members_with_points()) > 1
    w, h = f.size
    assert float(written[0].get_center()[0]) == pytest.approx((50 - w / 2) * f.k, abs=1e-3)


def test_parts_named_by_steps_wait_for_their_words_and_the_rest_are_there_from_the_start():
    CF, figures = _manim()
    from manim import FadeIn
    spec = {"id": "force_block", "reveal": ["force_arrows", "micro_zoom"]}
    f = CF.component(spec)
    assert f.hidden == ["force_arrows", "micro_zoom"] and f.shown == {"surface_ground", "block", "net_force_arrow"}
    assert all(m.get_stroke_opacity() == 0 and m.get_fill_opacity() == 0 for m in f.parts["force_arrows"].family_members_with_points())
    assert f.build == [("fade", [f.card] + [f.parts[n] for n in ("surface_ground", "block", "net_force_arrow")])]    # voice order
    figures.construct_animation(f)                                                                      # accepted by the generic builder
    whole = CF.component({"id": "force_block"})
    want = [(float(m.get_stroke_opacity()), float(m.get_fill_opacity())) for m in whole.parts["force_arrows"].family_members_with_points()]
    first = f.focus_animations("force_arrows")
    assert len(first) == 1 and type(first[0]).__name__ == "_Reveal" and "force_arrows" in f.shown
    first[0].begin(); first[0].interpolate(1.0)
    got = [(float(m.get_stroke_opacity()), float(m.get_fill_opacity())) for m in f.parts["force_arrows"].family_members_with_points()]
    assert got == pytest.approx(want)                                                                   # what it was drawn with, not flat
    again = f.focus_animations("force_arrows")
    assert len(again) == 1 and type(again[0]).__name__ == "_Pulse"                                       # already there: a pulse
    assert f.focus_animations("Net-Force_Arrow") and f.focus_animations("wheel") == []                  # spelling; an unknown name
    f.resume(["micro_zoom"])
    assert "micro_zoom" in f.shown and f.focus_animations("micro_zoom")[0].__class__.__name__ == "_Pulse"
    for part in f.parts.values():
        assert all(m.get_stroke_opacity() >= 0 for m in part.family_members_with_points())


def test_figures_build_reaches_the_component_through_the_kit_and_a_bad_one_keeps_the_picture(capsys):
    CF, figures = _manim()
    ok = figures.build({"kind": "component", "params": {"id": "test_tube", "state": {"bubbles": "many"}}, "manifest": "x"})
    assert isinstance(ok, CF.ComponentFigure) and ok.component == "test_tube"
    flat = figures.build({"kind": "component", "id": "test_tube", "params": {"level": 0.5}})
    assert flat is None or isinstance(flat, CF.ComponentFigure)
    assert figures.build({"kind": "component", "params": {"id": "no_such_thing"}}) is None
    assert figures.build({"kind": "component", "params": {"id": "force_block", "params": {"applied_force": 99}}}) is None
    out = capsys.readouterr().out
    assert out.count("LESSON_NOTE: figure 'component' could not be built") >= 2 and "there is no component" in out
    assert "component" not in figures.BUILDERS and "component" not in figures.KINDS                      # built-ins untouched
    with knobs.applied({"LESSONFORGE_KITS": "0"}):
        assert figures.build({"kind": "component", "params": {"id": "test_tube"}}) is None


# ---------------------------------------------------------------- through the workbench, the writer's gate and a mixed lesson

def _wb_beat(bid, narration, figure=None, steps=None):
    beat = {"id": bid, "narration": narration,
            "steps": steps or [{"say": narration.split(".")[0][:24], "show": "the block", "kind": "point"}]}
    if figure is not None:
        beat["figure"] = figure
    return beat


def test_a_component_lesson_goes_through_the_workbench_and_a_wrong_edit_is_a_fault(tmp_path, monkeypatch):
    from lessonforge.harness import workbench as W
    monkeypatch.setenv("LESSONFORGE_HOME", str(tmp_path))
    steps = [{"say": "The push", "show": "push", "kind": "point", "focus": "force_arrows"}]
    first = _wb_beat("01", "The push is {param applied_force} newtons. Does the block move?",
                     fig(params={"applied_force": 30, "opposing_force": 20}), steps)
    motion = _wb_beat("02", "A car speeds up. At 3 s its speed is {speed at 3} m/s.",
                      {"kind": "motion", "start_speed": 0, "acceleration": 2, "duration": 6, "marks": [3, 6]})
    added = W.add({"title": "Push and speed", "chapters": [{"id": 1, "title": "ONE", "learning_goal": "g", "role": "explain",
                                                            "beats": [first, motion]}]}, "mixed")
    assert added["faults"] == [], added["faults"]
    saved = W.load(added["lesson_id"])
    one, two = saved["chapters"][0]["beats"]
    assert one["narration"].startswith("The push is 30 newtons.") and two["narration"].endswith("6 m/s.")
    assert one["figure"]["params"]["reveal"] == ["force_arrows"] and one["figure"]["manifest"].startswith("force_block-")
    wrong = W.edit(added["lesson_id"], [{"op": "insert_beat", "after": "01", "beat": {
        "narration": "The push is 45 newtons.", "figure": fig(params={"applied_force": 30}),
        "steps": [{"say": "The push", "show": "push", "kind": "point"}]}}])
    assert wrong["kept"] is False and any("45" in f and "does not show" in f for f in wrong["faults"])      # refused, as for motion
    right = W.edit(added["lesson_id"], [{"op": "insert_beat", "after": "01", "beat": {
        "narration": "Now the push is {param applied_force} newtons.", "figure": fig(params={"applied_force": 40}),
        "steps": [{"say": "Now the push", "show": "push", "kind": "point", "focus": "block"}]}}])
    assert right["kept"] is True and right["faults"] == []
    kept = W.load(added["lesson_id"])["chapters"][0]["beats"][1]
    assert kept["narration"] == "Now the push is 40 newtons." and kept["figure"]["params"]["params"] == {"applied_force": 40}


def test_a_part_with_only_a_label_is_not_empty():
    """proof2: number_line's `result` has no shapes, only the label "0 + 3 + 3 = 6"; a step could not focus on it ("draws
    nothing") and the sum was on screen from the first frame."""
    drawn = {"parts": [("line", "<g/>"), ("result", ""), ("gone", " ")], "labels": [{"part": "result", "text": "0 + 3 = 3"}]}
    assert lib.empty_parts(drawn) == ["gone"]
    assert lib.empty_parts({"parts": [("a", "")]}) == ["a"]                                          # no labels key at all
