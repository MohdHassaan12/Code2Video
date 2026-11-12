"""The components kit against the CURRENT lesson-visuals contract: number states, layer and ground, situations.

Hermetic like ``test_kits_components.py``: ``tests/unit/conftest.py`` points LESSON_VISUALS_DIR at the pinned snapshot in
``fixtures/lv_components`` (the owner's own files, README there). The last test is optional: it checks a whole real tree
when LESSON_VISUALS_DIR was set to one in the shell, and is skipped otherwise. No model, no network.
"""
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from lessonforge import kits
from lessonforge.kits import components as C
from lessonforge.kits.base import KitError
from lessonforge.longform import component_lib as lib

REASON = lib.unavailable_reason()
pytestmark = pytest.mark.skipif(bool(REASON), reason=f"components are not available here: {REASON}")

KIT = kits.get("components") or C.ComponentsKit()
SNAPSHOT = Path(__file__).parent / "fixtures" / "lv_components"
REAL_TREE = os.environ.get("LF_TEST_REAL_LV", "")


def lesson(*beats):
    return {"title": "t", "chapters": [{"title": "ONE", "learning_goal": "g", "role": "explain", "beats": list(beats)}]}


def beat(narration, figure=None, steps=None):
    out = {"narration": narration, "steps": steps if steps is not None else [{"say": narration[:20], "show": "x"}]}
    if figure is not None:
        out["figure"] = figure
    return out


def fig(cid, params=None, state=None):
    inner = {"id": cid}
    if params is not None:
        inner["params"] = params
    if state is not None:
        inner["state"] = state
    return {"kind": "component", "params": inner}


@pytest.fixture
def folder(tmp_path, monkeypatch):
    """A private copy of the snapshot, so a test may add or change a component."""
    root = tmp_path / "lv"
    shutil.copytree(SNAPSHOT, root / "components", ignore=shutil.ignore_patterns("README.md"))
    monkeypatch.setenv(lib.ENV_DIR, str(root))
    return root


# ---------------------------------------------------------------- the loader: number states, canvas fields, unknown fields

def test_the_snapshot_is_the_owners_current_contract():
    assert Path(os.environ["LESSON_VISUALS_DIR"]) == SNAPSHOT
    leaf = lib.get("leaf_section")
    assert leaf["states"]["stoma"] == ["open", "closed"]
    assert leaf["states"]["opening"] == {"type": "number", "min": 0, "max": 1, "default": 1,
                                         "say": "how wide the stoma is: 0 closed, 1 fully open"}
    assert lib.broken() == [] and len(lib.catalogue(classes=None)) == 6


def test_a_state_may_be_a_list_of_names_or_a_number_slider_and_canvas_fields_are_carried():
    leaf, tube, block = lib.get("leaf_section"), lib.get("test_tube"), lib.get("force_block")
    assert (leaf["layer"], leaf["ground"]) == ("actor", 192.0) and (tube["layer"], tube["ground"]) == ("prop", 232.0)
    assert lib.is_knob(tube["states"]["bubble_rate"]) and not lib.is_knob(tube["states"]["bubbles"])
    assert tube["states"]["bubbles"] == ["none", "some", "many"]
    assert block["states"] == {"motion": ["rest", "sliding_right", "sliding_left", "impending"]}      # the older shape is the same
    pend = lib.get("simple_pendulum")
    assert pend["layer"] is None and pend["ground"] is None and lib.is_knob(pend["states"]["time_s"])
    assert pend["warnings"] == [] and leaf["extra"] == {}


def test_situations_are_surfaced_as_ready_made_beat_plans():
    tube = lib.get("test_tube")
    assert [s["name"] for s in tube["situations"]] == ["zinc_and_acid", "lime_water", "reaction_speeds_up"]
    zinc = tube["situations"][0]
    assert set(zinc) == {"name", "title", "ncert", "params", "steps"}
    assert zinc["title"] == "Zinc and dilute acid give hydrogen" and zinc["ncert"].startswith("Class 10 Ch 1")
    assert zinc["params"] == {"liquid": "dilute acid", "solid": "granules", "level": 0.45}
    assert [set(s) for s in zinc["steps"]] == [{"state", "show", "say"}] * 5
    assert zinc["steps"][0]["say"] == "This is a test tube." and zinc["steps"][0]["show"] == ["glass"]
    assert zinc["steps"][4]["state"] == {"bubbles": "many"} and zinc["steps"][4]["show"][-1] == "bubbles"    # show is kept
    assert [s["name"] for s in lib.catalogue(subjects=["biology"])[0]["situations"]] == ["leaf_layers", "stoma_open_close", "gases_day_night"]
    sheet = lib.sheet(lib.get("leaf_section"))
    assert "state opening (number 0 to 1; default 1" in sheet and "gases_day_night" in sheet


def test_unknown_meta_fields_and_odd_canvas_values_are_carried_not_refused(folder):
    src = (folder / "components/physics/force_block.ts").read_text()
    new = src.replace('id: "force_block"', 'id: "odd_block"').replace("layer: \"actor\"", 'layer: "sideways", mood: "calm", extra_list: [1, 2]')
    assert new != src
    (folder / "components/physics/odd_block.ts").write_text(new)
    entry = lib.get("odd_block")
    assert entry["layer"] is None and entry["extra"] == {"mood": "calm", "extra_list": [1, 2]}
    assert any("meta.layer" in w for w in entry["warnings"]) and "odd_block" not in {b["id"] for b in lib.broken()}


def test_a_component_that_really_cannot_load_is_listed_by_broken_with_its_reason(folder):
    src = (folder / "components/physics/force_block.ts").read_text()
    def variant(cid, old, new):
        assert old in src
        (folder / "components/physics" / f"{cid}.ts").write_text(src.replace('id: "force_block"', f'id: "{cid}"').replace(old, new))
    variant("text_state", 'motion: ["rest"', 'motion: "rest", other: ["rest"')
    variant("flat_range", 'motion: ["rest"', 'motion: { type: "number", min: 1, max: 1, default: 1, say: "x" }, other: ["rest"')
    variant("late_default", 'motion: ["rest"', 'motion: { type: "number", min: 0, max: 1, default: 5, say: "x" }, other: ["rest"')
    variant("states_list", "states: {", "states: [] || {")
    bad = {b["id"]: b["error"] for b in lib.broken()}
    assert "must be a list of names or a number slider" in bad["text_state"]
    assert "needs numbers min < max" in bad["flat_range"] and "default between min and max" in bad["late_default"]
    assert set(bad) >= {"text_state", "flat_range", "late_default"} and "force_block" not in bad


# ---------------------------------------------------------------- checking a state

def test_number_state_in_range_out_of_range_and_unknown_key():
    ok = lambda st: lib.validate("leaf_section", {}, st)          # noqa: E731
    assert ok({"opening": 0.5}) == [] and ok({"opening": 0}) == [] and ok({"opening": 1}) == [] and ok({"light": 0.25}) == []
    assert ok({"opening": 0.5, "light": 0.4, "stoma": "closed", "time": "night"}) == []                # several keys at once
    low, high = " ".join(ok({"opening": -0.1})), " ".join(ok({"opening": 1.5}))
    assert "state opening must be from 0 to 1" in low and "-0.1" in low and "1.5" in high
    assert "must be a number from 0 to 1" in " ".join(ok({"opening": "wide"}))
    assert "must be a number" in " ".join(ok({"opening": True})) and "must be a number" in " ".join(ok({"opening": float("nan")}))
    assert "must be a number" in " ".join(ok({"opening": "open"}))                                      # a preset name is not a number
    assert "not a state of leaf_section (it has: stoma, time, opening, light)" in " ".join(ok({"brightness": 1}))
    assert "state stoma must be one of: open, closed" in " ".join(ok({"stoma": "ajar"}))
    assert "state stoma must be one of" in " ".join(ok({"stoma": 0.5}))                                   # a number is not a preset
    assert any("opening" in p for p in ok({"opening": 2, "stoma": "ajar"})) and len(ok({"opening": 2, "stoma": "ajar"})) == 2
    assert "state must be an object" in " ".join(lib.check_params(lib.get("leaf_section"), {}, ["opening"]))
    with pytest.raises(lib.ComponentError, match="state opening must be from 0 to 1"):
        lib.draw("leaf_section", {}, {"opening": 3})


def test_a_number_state_wins_over_a_named_preset_and_a_preset_still_works_alone():
    d = lambda st: lib.draw("leaf_section", {}, st)               # noqa: E731
    closed, wide, shut_by_number = d({"stoma": "closed"}), d({"stoma": "open"}), d({"opening": 0})
    assert closed["parts"] != wide["parts"]                                                           # the preset alone works
    assert closed["parts"] == shut_by_number["parts"]                                                  # and means what the slider means
    assert d({"stoma": "closed", "opening": 1})["parts"] == d({"opening": 1})["parts"] == wide["parts"]    # the number wins
    assert d({"stoma": "open", "opening": 0})["parts"] == shut_by_number["parts"] != wide["parts"]
    assert d({"time": "night"})["parts"] != d({"time": "day"})["parts"]
    assert d({"time": "day", "light": 0})["parts"] == d({"light": 0})["parts"]


def test_missing_number_states_get_their_defaults_but_a_preset_and_an_empty_state_are_left_alone():
    leaf = lib.get("leaf_section")
    assert lib.filled_state(leaf, {"opening": 0.5}) == {"opening": 0.5, "light": 1}
    assert lib.draw("leaf_section", {}, {"opening": 0.5})["state"] == {"opening": 0.5, "light": 1}
    assert lib.filled_state(leaf, {"stoma": "closed"}) == {"stoma": "closed"}                          # the preset decides the rest
    assert lib.filled_state(leaf, {"stoma": "closed", "opening": 0.3}) == {"stoma": "closed", "opening": 0.3}
    assert lib.filled_state(leaf, {}) == {} and lib.filled_state(leaf, None) == {}
    line = lib.get("number_line")                                  # its finished picture is the unset one, not hops_done = 0
    assert lib.draw("number_line", {})["parts"] != lib.draw("number_line", {}, {"hops_done": 0})["parts"]
    assert lib.draw("number_line", {})["state"] == {}


def test_draw_is_deterministic_at_every_value_in_between_and_the_two_ends_differ():
    values = [round(i / 6, 3) for i in range(7)]
    pics = [lib.draw("leaf_section", {}, {"opening": v}) for v in values]
    assert pics == [lib.draw("leaf_section", {}, {"opening": v}) for v in values]
    assert json.dumps(pics[3], sort_keys=True) == json.dumps(lib.draw("leaf_section", {}, {"opening": values[3]}), sort_keys=True)
    assert pics[0]["parts"] != pics[-1]["parts"] and pics[0]["parts"] != pics[3]["parts"] != pics[-1]["parts"]
    assert all(set(dict(p["parts"])) == set(lib.get("leaf_section")["parts"]) for p in pics)
    assert lib.draw("simple_pendulum", {}, {"time_s": 1.7}) == lib.draw("simple_pendulum", {}, {"time_s": 1.7})


def test_the_kit_takes_a_figure_with_a_number_state_and_keeps_it_canonical():
    f = fig("leaf_section", state={"opening": 0.4, "stoma": "closed"})
    done, issues = KIT.settle(lesson(beat("Look at the pore.", f)))
    assert issues == []
    canon = done["chapters"][0]["beats"][0]["figure"]
    assert canon["params"]["state"] == {"opening": 0.4, "stoma": "closed"} and canon["manifest"].startswith("leaf_section-")
    assert KIT.settle(done)[0] == done
    assert any("state opening must be from 0 to 1" in i for i in KIT.settle(lesson(beat("Look.", fig("leaf_section", state={"opening": 4}))))[1])
    assert any("is not a state" in i for i in KIT.settle(lesson(beat("Look.", fig("leaf_section", state={"width": 1}))))[1])
    assert "state opening" in KIT.rules_with("leaf_section") and "number 0 to 1" in KIT.rules_with("leaf_section")


# ---------------------------------------------------------------- situations as beat plans

ALL_SITUATIONS = [(e["id"], s["name"]) for e in lib.catalogue(classes=None) for s in e["situations"]] if not REASON else []


@pytest.mark.parametrize("cid,name", ALL_SITUATIONS)
def test_every_situation_becomes_beats_that_pass_settle_with_no_fault(cid, name):
    beats = C.situation_to_beats(cid, name)
    done, issues = KIT.settle(lesson(*beats))
    assert issues == [], issues
    sit = next(s for s in lib.get(cid)["situations"] if s["name"] == name)
    said = [b["narration"] for b in beats]
    assert " ".join(said) == " ".join(s["say"].strip() for s in sit["steps"])            # the library's words, in order, nothing else
    assert sum(len(b["steps"]) for b in beats) == len(sit["steps"]) and all(b["figure"]["kind"] == "component" for b in beats)
    assert C.situation_to_beats(cid, name) == beats                                       # deterministic


def test_a_situation_is_cut_into_beats_where_the_numbers_or_the_named_state_change():
    beats = C.situation_to_beats("test_tube", "zinc_and_acid", speaker="Asha")
    assert len(beats) == 3 and [len(b["steps"]) for b in beats] == [3, 1, 1]
    assert all(b["speaker"] == "Asha" and b["situation"]["name"] == "zinc_and_acid" for b in beats)
    first = beats[0]
    assert first["narration"] == "This is a test tube. We pour in some dilute sulphuric acid. Then we drop in a few zinc granules."
    assert [s.get("focus") for s in first["steps"]] == [None, "liquid", "solid"]
    assert [s["say"] for s in first["steps"]] == ["This is a test tube.", "We pour in some dilute", "Then we drop in a"]
    assert first["figure"]["params"]["hold"] == ["bubbles", "gas"] and "state" not in first["figure"]["params"]
    assert beats[1]["figure"]["params"]["state"] == {"bubbles": "some"} and beats[2]["figure"]["params"]["state"] == {"bubbles": "many"}
    assert beats[1]["steps"][0]["focus"] == "bubbles"                                      # the part this step brings in
    assert "params" not in first["figure"]["params"]                                       # the set-up's params are the defaults
    lime = C.situation_to_beats("test_tube", "lime_water")[0]["figure"]["params"]
    assert lime["params"] == {"liquid": "lime water", "level": 0.5, "solid": "none"}                 # the ones that differ are kept
    assert all(len(s["show"].split()) <= 12 for b in beats for s in b["steps"])
    assert "speaker" not in C.situation_to_beats("test_tube", "lime_water")[0]


def test_parts_shown_together_come_in_together_and_a_number_that_moves_makes_a_new_figure():
    beats = C.situation_to_beats("leaf_section", "leaf_layers")
    assert [len(b["steps"]) for b in beats] == [4, 1] and beats[1]["steps"][0]["focus"] == "lower_epidermis"    # at most 4 steps a beat
    assert beats[0]["figure"] == beats[1]["figure"]                                                            # ... on ONE figure
    fig0 = beats[0]["figure"]["params"]
    assert fig0["with"] == {"lower_epidermis": ["stoma"]} and fig0["hold"] == ["light", "gases"]
    settled = KIT.settle(lesson(*beats))[0]["chapters"][0]["beats"]
    assert settled[0]["figure"]["params"]["reveal"] == ["palisade", "spongy", "vein", "lower_epidermis"]
    assert settled[0]["figure"] == settled[1]["figure"]
    assert C._show_text("This is a thin slice across a leaf. On top is a single layer of cells.") == "This is a thin slice across a leaf."
    assert C._show_text("A 40 cm pendulum has a period of about 1.3 seconds.") == "A 40 cm pendulum has a period of about 1.3 seconds."
    assert C._show_text("A vein runs through the middle of the leaf, and its xylem brings water.") == "A vein runs through the middle of the leaf"
    assert C._show_text("One two three four five six seven eight nine ten eleven twelve thirteen.") == "One two three four five six seven eight nine…"
    slide = C.situation_to_beats("number_line", "hop_by_hop")
    states = [b["figure"]["params"].get("state") for b in slide]
    assert len(slide) == len(states) >= 4 and states == [{"hops_done": v} for v in (0, 0.5, 1, 3)]


def test_a_situation_or_component_that_does_not_exist_or_cannot_be_drawn_is_refused():
    with pytest.raises(KitError, match="has no situation 'nope'.*zinc_and_acid"):
        C.situation_to_beats("test_tube", "nope")
    with pytest.raises(KitError, match="there is no component"):
        C.situation_to_beats("no_such", "x")
    with pytest.raises(KitError, match="speaker"):
        C.situation_to_beats("test_tube", "lime_water", speaker="")


def test_a_situation_whose_numbers_are_outside_min_and_max_is_refused(folder):
    path = folder / "components/maths/number_line.ts"
    src = path.read_text()
    assert "hops_done: 3 }" in src
    path.write_text(src.replace("hops_done: 3 }", "hops_done: 9 }"))
    with pytest.raises(KitError, match="situation hop_by_hop step 4.*state hops_done must be from 0 to 6.*9"):
        C.situation_to_beats("number_line", "hop_by_hop")
    path.write_text(src)
    assert [b["figure"]["params"]["state"] for b in C.situation_to_beats("number_line", "hop_by_hop")][-1] == {"hops_done": 3}


def test_a_part_focus_that_is_not_in_meta_parts_is_refused_on_a_situation_beat():
    beats = C.situation_to_beats("test_tube", "zinc_and_acid")
    beats[0]["steps"][1]["focus"] = "wheel"
    issues = KIT.settle(lesson(*beats))[1]
    assert len(issues) == 1 and "'wheel' is not a part of component test_tube" in issues[0] and "glass, liquid, solid" in issues[0]
    beats = C.situation_to_beats("test_tube", "lime_water")
    beats[0]["figure"]["params"]["hold"] = ["wheel"]
    assert any("wheel" in i and "not parts" in i for i in KIT.settle(lesson(*beats))[1])
    beats = C.situation_to_beats("test_tube", "lime_water")
    beats[0]["figure"]["params"]["hold"] = ["glass"]
    assert any("outline" in i for i in KIT.settle(lesson(*beats))[1])


def test_the_numbers_in_the_librarys_own_lines_are_not_stray_but_a_writers_are():
    beats = C.situation_to_beats("simple_pendulum", "longer_string")
    assert any("1.3" in b["narration"] for b in beats) and KIT.settle(lesson(*beats))[1] == []
    plain = lesson(beat("The period is about 1.3 seconds.", fig("simple_pendulum")))
    assert any("1.3" in i and "does not show" in i for i in KIT.settle(plain)[1])                      # no situation, no trust
    beats[0]["narration"] += " It swings 99 times."
    assert any("99" in i for i in KIT.settle(lesson(*beats))[1])


# ---------------------------------------------------------------- number params and states change per beat, never inside one

def test_an_override_outside_min_and_max_is_refused_and_a_good_one_is_a_new_canonical_figure():
    base = fig("leaf_section", state={"opening": 1})
    moved = C.override_figure(base, state={"opening": 0.3})
    assert moved["params"]["state"] == {"opening": 0.3} and moved["manifest"] != KIT.normalise_figure(base)["manifest"]
    assert C.override_figure(fig("force_block"), params={"applied_force": 12})["params"]["params"] == {"applied_force": 12}
    for bad, match in ((dict(state={"opening": 1.2}), "state opening must be from 0 to 1"),
                       (dict(state={"opening": -3}), "from 0 to 1"), (dict(state={"nope": 1}), "not a state"),
                       (dict(params={"colour": "red"}), "not a parameter")):
        with pytest.raises(KitError, match=match):
            C.override_figure(base, **bad)
    with pytest.raises(KitError, match="applied_force must be from 0 to 50"):
        C.override_figure(fig("force_block"), params={"applied_force": 999})
    assert base == fig("leaf_section", state={"opening": 1})                                              # the original is untouched


def test_a_step_that_carries_params_or_state_is_a_fault_because_a_beat_has_one_drawing():
    f = fig("leaf_section", state={"opening": 1})
    step = lambda **kw: {"say": "Look at", "show": "pore", "focus": "stoma", **kw}                      # noqa: E731
    issues = KIT.settle(lesson(beat("Look at the pore.", f, steps=[step(state={"opening": 0.5})])))[1]
    assert len(issues) == 1 and "cannot change the picture's numbers" in issues[0] and "new beat" in issues[0]
    issues = KIT.settle(lesson(beat("Look at the pore.", f, steps=[step(state={"opening": 5})])))[1]
    assert len(issues) == 1 and "state opening must be from 0 to 1" in issues[0]
    issues = KIT.settle(lesson(beat("Look at the force.", fig("force_block"), steps=[{"say": "Look", "show": "f", "params": {"applied_force": 99}}])))[1]
    assert len(issues) == 1 and "applied_force must be from 0 to 50" in issues[0]
    assert KIT.settle(lesson(beat("Look at the pore.", f, steps=[step()])))[1] == []


# ---------------------------------------------------------------- the Manim side of hold and with

def test_held_parts_stay_out_and_parts_shown_together_come_in_together():
    pytest.importorskip("manim", reason="manim is not installed here")
    from lessonforge.longform import component_figure as CF
    beats = C.situation_to_beats("leaf_section", "leaf_layers")
    done = KIT.settle(lesson(*beats))[0]
    spec = done["chapters"][0]["beats"][0]["figure"]
    assert spec == done["chapters"][0]["beats"][1]["figure"]
    f = CF.component(spec)
    assert set(f.hidden) == {"palisade", "spongy", "vein", "lower_epidermis", "stoma", "light", "gases"}
    assert f.shown == {"upper_epidermis"}
    anims = f.focus_animations("lower_epidermis")
    assert len(anims) == 1 and f.shown == {"upper_epidermis", "lower_epidermis", "stoma"}            # the pair came in as one
    assert "light" not in f.shown and "gases" not in f.shown
    assert f.focus_animations("stoma")[0].__class__.__name__ == "_Pulse"                              # already there
    other = CF.component(spec)
    other.resume(["palisade", "lower_epidermis"])
    assert {"palisade", "lower_epidermis", "stoma"} <= other.shown and "spongy" not in other.shown


# ---------------------------------------------------------------- optional: a whole real tree

def _real_components_dir():
    root = Path(REAL_TREE).expanduser() if REAL_TREE else None
    if root is None or not root.is_dir():
        return None
    return root / "components" if (root / "components").is_dir() else root


@pytest.mark.skipif(not REAL_TREE or _real_components_dir() is None or not (_real_components_dir() / "tools" / "check.ts").is_file(),
                    reason="set LESSON_VISUALS_DIR to a real lesson-visuals tree (with components/tools/check.ts) to run this")
def test_every_component_the_owners_checker_accepts_also_loads_in_the_kit_real_tree(monkeypatch):
    cdir = _real_components_dir()
    node = lib.node_path()
    done = subprocess.run([node, "--experimental-strip-types", "--no-warnings", str(cdir / "tools" / "check.ts")], capture_output=True,
                          text=True, timeout=300, cwd=str(cdir), env={"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"})
    report = json.loads(done.stdout)
    accepted = {Path(path).stem for path, why in report.items() if not why}
    monkeypatch.setenv(lib.ENV_DIR, str(cdir))
    loaded = {e["id"] for e in lib.catalogue(classes=None)}
    broken = {b["id"]: b["error"] for b in lib.broken()}
    assert accepted <= loaded, {i: broken.get(i) for i in sorted(accepted - loaded)}
    assert set(broken) <= {Path(p).stem for p, why in report.items() if why}, broken          # broken() lists only what is really broken
    for cid in sorted(loaded):                                                                # and each draws its own example
        entry = lib.get(cid)
        assert [n for n, _ in lib.draw(cid, entry["example"])["parts"]] == entry["parts"]
