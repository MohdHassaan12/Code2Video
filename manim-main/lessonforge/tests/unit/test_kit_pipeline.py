"""The kit pipeline: routing by code, the brief it fills, the capped model, the run and its trace, the tools and the CLI.

No test makes a paid call: models are stubs. The components kit is registered only when Node and the lesson-visuals
components are there, so the tests that need a component skip without them.
"""
import json
import os
from pathlib import Path

import pytest

from lessonforge import kits
from lessonforge.harness import kit_pipeline as P

HAS_COMPONENTS = kits.get("components") is not None
SNAPSHOT_DIR = Path(__file__).parent / "fixtures" / "lv_components"
needs_components = pytest.mark.skipif(not HAS_COMPONENTS, reason="the components kit needs Node 22.6+ and lesson-visuals")


def one(text, **kw):
    return P.route(text, beats=[text], **kw).beats[0]


# ---------------------------------------------------------------- the router

def test_a_triangle_angle_sentence_goes_to_geometry():
    b = one("In triangle ABC, angle A is 60 degrees and angle B is 50 degrees, so find angle C.")
    assert (b["kit"], b["kind"]) == ("geometry", "shape") and "triangle" in b["why"] and b["by"] == "code"
    assert b["subject"] == "maths" and b["class_band"] == "1-12"


def test_a_car_speeding_up_goes_to_motion():
    b = one("A car speeds up from rest and reaches a speed of 6 metres per second.")
    assert (b["kit"], b["kind"]) == ("motion", "motion") and b["subject"] == "physics" and b["class_band"] == "7-9"


def test_hydrogen_burning_in_oxygen_goes_to_the_reaction_kit():
    b = one("Hydrogen burns in oxygen to make water.")
    assert (b["kit"], b["kind"]) == ("chemistry", "chem_reaction")
    assert one("2H2 + O2 -> 2H2O")["kit"] == "chemistry"


@needs_components
def test_a_block_with_friction_goes_to_the_force_block_component():
    b = one("A block on a rough surface with friction.")
    assert (b["kit"], b["component"], b["kind"]) == ("components", "force_block", "component")
    assert one("A test tube is half full of liquid with bubbles.")["component"] == "test_tube"


@needs_components
def test_a_weak_word_in_a_parameters_say_line_cannot_send_a_part_to_a_component():
    # 2026-11 review: "negative" is in a splinter parameter's say line, and "angle" in an inclined plane's.
    for text in ("Negative integers on a number line.", "The angle is 40 degrees."):
        item = P.route(text).beats[0]
        assert item["component"] not in ("splinter", "inclined_plane", "free_body_incline"), item
    assert P.route("Negative integers on a number line.").beats[0]["component"] in (None, "number_line")


def test_parameter_words_alone_never_pass_the_sure_threshold_and_the_why_names_the_tier():
    comp = {"id": "gizmo", "title": "Gizmo", "subject": "physics", "classes": [8], "ncert": ["Class 8, Ch 3 Pressure (the piston)"],
            "params": [{"name": f"p{i}", "say": w} for i, w in enumerate("alpha beta gamma delta epsilon zeta".split())],
            "parts": ["body"], "states": {}, "situations": [{"title": "Squeezing the bulb", "name": "s"}]}
    doc = P._component_doc(comp)
    assert doc.tier["alpha"] == P.TIER_PARAM and doc.tier["gizmo"] == P.TIER_NAME and doc.tier["piston"] == P.TIER_CHAPTER
    assert doc.tier["bulb"] == P.TIER_SITUATION
    score, why = P._score(doc, P.tokens("alpha beta gamma delta epsilon zeta"), "", {})
    assert score <= P.WEAK_CAP < P.SURE_SCORE and all("(parameter)" in w for w in why)
    score, why = P._score(doc, P.tokens("the piston"), "", {})
    assert why == ["piston (chapter)"] and score == pytest.approx(P.TIER_CHAPTER)


def test_generic_words_are_never_a_component_keyword_alone_but_a_phrase_with_them_is():
    doc = P._component_doc({"id": "number_line", "title": "Number line", "subject": "maths", "classes": [6], "ncert": [],
                            "params": [{"name": "x", "say": "a negative value"}], "parts": [], "states": {}, "situations": []})
    assert not {"negative", "number", "value", "line"} & set(doc.words)
    assert ("number", "line") in doc.phrases


def test_a_preposition_in_a_title_is_not_a_component_keyword_alone():
    # "Gas bubbled through lime water" used to take "Light bends when it passes through a glass slab" (a Class 10 topic,
    # so no component serves it) because "through" alone scored 0.83
    doc = P._component_doc({"id": "limewater_test", "title": "Gas bubbled through lime water", "subject": "chemistry",
                            "classes": [8], "ncert": [], "params": [], "parts": [], "states": {}, "situations": []})
    assert "through" not in doc.words and ("bubbl", "through") in doc.phrases
    assert P._score(doc, P.tokens("Light bends when it passes through a glass slab."), "", {})[0] < P.MIN_SCORE


@needs_components
def test_a_new_component_is_routable_from_its_own_metadata_with_no_code_change(tmp_path, monkeypatch):
    import shutil
    from lessonforge.longform import component_lib as lib
    tree = tmp_path / "components"
    shutil.copytree(SNAPSHOT_DIR, tree)
    src = (tree / "physics" / "simple_pendulum.ts").read_text()
    new = src.replace("simple_pendulum", "tuning_fork").replace("Simple pendulum", "Tuning fork")
    (tree / "physics" / "tuning_fork.ts").write_text(new)
    monkeypatch.setenv(lib.ENV_DIR, str(tmp_path))
    assert "tuning_fork" in lib.ids()
    assert P.route("A tuning fork is struck and hums.", classes=[7, 8, 9]).beats[0]["component"] == "tuning_fork"


@needs_components
def test_a_biology_sentence_about_the_leaf_goes_to_the_biology_component():
    item = P.route("The stomata on the leaf open and close.", classes=[7]).beats[0]
    assert (item["kit"], item["component"], item["subject"]) == ("components", "leaf_section", "biology")
    assert any("stomata" in w or "leaf" in w for w in item["why"])


@pytest.mark.skipif(not os.environ.get("LF_TEST_REAL_LV"), reason="set LESSON_VISUALS_DIR to a real lesson-visuals tree")
def test_a_biology_sentence_routes_in_the_real_library_too(monkeypatch):
    from lessonforge.longform import component_lib as lib
    monkeypatch.setenv(lib.ENV_DIR, os.environ["LF_TEST_REAL_LV"])
    item = P.route("The stomata on the leaf open and close.", classes=[7]).beats[0]
    assert item["component"] == "leaf_section"
    assert P.route("Negative integers on a number line.").beats[0]["component"] in (None, "number_line")
    assert P.route("The angle is 40 degrees.").beats[0]["component"] not in ("inclined_plane", "splinter")


@needs_components
def test_an_equation_to_solve_goes_to_maths_or_to_none_and_does_not_crash():
    for text in ("Solve x + 3 = 7.", "solve x + 3 = 7", "x = 4, because 4 + 3 = 7"):
        item = P.route(text).beats[0]
        assert item["kit"] in (None, "geometry") and item["component"] in (None, "number_line"), item
        assert item["subject"] in (None, "maths", "math")


def test_classes_are_understood_in_all_the_ways_a_library_and_a_brief_write_them():
    from lessonforge.longform.component_lib import classes_of
    assert classes_of("Class 6-10 story") == set(range(6, 11))
    assert classes_of("Class 1 to 12 anything") == set(range(1, 13))
    assert classes_of(["Any class 6-10 scene"]) == set(range(6, 11))
    assert classes_of(["Any class story or activity"]) == set(range(1, 13))
    assert classes_of(["Class 8, Ch 3 Coal", "Class 9 Science: Sound"]) == {8, 9}
    assert P.classes_in("Classes 7 to 9") == [7, 8, 9] and P.classes_in("Class 6\u201310") == [6, 7, 8, 9, 10]
    assert P.classes_in("Class 1 to 12") == list(range(1, 13)) and P.classes_in("Any class") == []


def test_a_sentence_about_nothing_goes_to_no_kit_and_is_not_a_failure():
    for text in ("The weather was pleasant today and everybody smiled.", "Let us begin our lesson now.", ""):
        b = one(text)
        assert b["kit"] is None and b["kind"] is None and b["by"] == "none" and b["score"] < P.MIN_SCORE


def test_the_class_filter_removes_the_kits_that_do_not_serve_it():
    text = "A car speeds up from rest and reaches a speed of 6 metres per second."
    assert one(text, classes=[7])["kit"] == "motion" and one(text, classes=[8, 9])["kit"] == "motion"
    assert one(text, classes=[6])["kit"] != "motion"                  # motion's classes start at 7 (a Class 6 component may still match a word)
    assert one("Find angle C in triangle ABC.", classes=[6])["kit"] == "geometry"
    with pytest.raises(P.PipelineError):
        P.route("x", classes=[13])      # classes 1 to 12 are in scope


def test_the_class_the_brief_names_is_the_default_filter():
    plan = P.route("Class 6 lesson. A car speeds up from rest.", beats=["A car speeds up from rest."])
    assert plan.classes == [6] and plan.beats[0]["kit"] is None and any("read from the brief" in n for n in plan.notes)
    assert P.route("Class 8. A car speeds up from rest.", beats=["A car speeds up from rest."]).beats[0]["kit"] == "motion"


def test_the_subject_filter():
    text = "In triangle ABC, find angle C. A car speeds up from rest."
    assert one(text, subjects="physics")["kit"] == "motion"
    assert one(text, subjects=["maths"])["kit"] == "geometry"
    assert one("Hydrogen burns in oxygen to make water.", subjects="maths")["kit"] is None


def test_a_brief_is_split_into_parts_and_a_mixed_brief_names_several_kits():
    brief = ("# Three ideas\n\nIn triangle ABC, angle A is 60 degrees and angle B is 50 degrees.\n\n"
             "A car speeds up from rest at 2 metres per second every second.\n\n"
             "Hydrogen burns in oxygen to make water.\n\nThe weather was pleasant.")
    plan = P.route(brief)
    assert [b["kit"] for b in plan.beats] == ["geometry", "motion", "chemistry", None]
    assert plan.mixed and plan.kit_names() == ["geometry", "motion", "chemistry"]
    assert plan.beats[0]["text"].startswith("Three ideas. In triangle")           # the heading is context for the next part
    assert [len(P.split_brief(t)) for t in ("One. Two. Three.", "- a\n- b\n- c", "x\n\ny")] == [3, 3, 2]


def test_every_item_is_plain_json_and_ties_go_by_priority():
    plan = P.route("A car speeds up from rest.\n\nFind angle C in triangle ABC.")
    json.dumps(plan.to_dict())
    assert set(plan.beats[0]) >= {"beat", "kit", "subject", "class_band", "score", "why", "kind", "component", "by"}
    assert P.PRIORITY["chemistry"] > P.PRIORITY["geometry"] > P.PRIORITY["components"]


def test_switching_the_kits_off_routes_everything_to_none():
    from lessonforge import knobs
    with knobs.applied({"LESSONFORGE_KITS": "0"}):
        plan = P.route("A car speeds up from rest.")
    assert plan.beats[0]["kit"] is None and any("switched off" in n for n in plan.notes)


class Stub:
    """A model stand-in that costs nothing and says so."""
    spent_usd = 0.0
    call_estimate_usd = 0.0

    def __init__(self, answers):
        self.answers, self.calls = list(answers), []

    def __call__(self, prompt, system):
        self.calls.append((prompt, system))
        a = self.answers.pop(0) if self.answers else {}
        if callable(a):
            return a(prompt, system)
        return a


def test_the_model_router_decides_only_unsure_beats_and_its_answer_is_checked():
    sure = "Hydrogen burns in oxygen to make water."
    unsure = "The weather was pleasant today."
    llm = Stub([{"routes": [{"beat": 1, "kit": "motion", "why": "x"},                  # a sure beat: not asked, ignored
                            {"beat": 2, "kit": "geometry", "why": "a shape in the sky"},
                            {"beat": 3, "kit": "nonsense"}, {"beat": 2, "kit": "components", "component": "nope"}]}])
    plan = P.route("x", beats=[sure, unsure], llm=llm)
    assert len(llm.calls) == 1 and sure not in llm.calls[0][0].split("PARTS TO ROUTE")[1]
    assert plan.beats[0]["kit"] == "chemistry" and plan.beats[0]["by"] == "code"
    assert (plan.beats[1]["kit"], plan.beats[1]["by"]) == ("geometry", "model") and plan.beats[1]["why"][0].startswith("model:")
    assert any("not registered" in n for n in plan.notes) or any("does not exist" in n for n in plan.notes)


def test_the_model_router_cannot_name_a_kit_outside_the_class_filter_or_a_missing_component():
    llm = Stub([{"routes": [{"beat": 1, "kit": "motion"}]}])
    assert P.route("x", beats=["Some words about nothing."], llm=llm, classes=[6]).beats[0]["kit"] is None          # motion is 7-9
    llm = Stub([{"routes": [{"beat": 1, "kit": "components", "component": "no_such_component"}]}])
    plan = P.route("x", beats=["Some words about nothing."], llm=llm)
    assert plan.beats[0]["kit"] is None and any("does not exist" in n for n in plan.notes)
    plan = P.route("x", beats=["Some words about nothing."], llm=Stub(["not json at all"]))
    assert plan.beats[0]["kit"] is None and any("no usable shape" in n for n in plan.notes)


@needs_components
def test_the_model_router_may_choose_a_real_component():
    plan = P.route("x", beats=["Some words about nothing."], llm=Stub([{"routes": [{"beat": 1, "kit": "components", "component": "force_block"}]}]))
    assert (plan.beats[0]["kit"], plan.beats[0]["component"]) == ("components", "force_block")


def test_a_failing_model_router_costs_nothing():
    def broken(prompt, system):
        raise RuntimeError("boom")
    plan = P.route("x", beats=["Some words about nothing."], llm=broken)
    assert plan.beats[0]["kit"] is None and any("model router failed" in n for n in plan.notes)


# ---------------------------------------------------------------- the plan as a brief

MIXED = ("In triangle ABC, angle A is 60 degrees and angle B is 50 degrees.\n\n"
         "A car speeds up from rest at 2 metres per second every second.\n\n"
         "Hydrogen burns in oxygen to make water.")


def test_the_plan_fills_the_kits_and_a_hint_for_every_part_without_changing_the_brief_it_was_given():
    original = {"topic": "Three ideas", "kits": ["motion"]}
    brief = P.plan_to_brief(P.route(MIXED), original)
    assert original == {"topic": "Three ideas", "kits": ["motion"]}
    assert brief["kits"] == ["motion", "geometry", "chemistry"]
    assert len(brief["kit_hints"]) == 3 and "figure kind shape (kit geometry)" in brief["kit_hints"][0]
    rules = kits.rules_for(brief["kits"])
    assert "THIS LESSON MIXES SUBJECTS" in rules and "SUBJECT KIT motion" in rules and "SUBJECT KIT chemistry" in rules


def test_one_kit_gets_the_single_kit_header_and_no_kit_adds_nothing():
    one_kit = P.plan_to_brief(P.route("A car speeds up from rest.\n\nIt keeps speeding up."))
    assert one_kit["kits"] == ["motion"] and "MIXES" not in kits.rules_for(one_kit["kits"])
    none = P.plan_to_brief(P.route("The weather was pleasant."))
    assert "kits" not in none and "no kit figure fits" in none["kit_hints"][0] and kits.rules_for(none.get("kits")) == ""


@needs_components
def test_a_component_is_named_by_id_so_the_writer_gets_its_sheet():
    brief = P.plan_to_brief(P.route("A block on a rough surface with friction.\n\nA car speeds up from rest."))
    assert brief["kits"] == ["components:force_block", "motion"] and "component id force_block" in brief["kit_hints"][0]
    rules = kits.rules_for(brief["kits"])
    assert "force_block" in rules and "applied_force" in rules


def test_the_writer_shows_the_hints_and_a_brief_without_them_reads_as_it_always_did():
    from lessonforge.harness import frameworks, writer
    framework = frameworks.get("worked_examples")
    base = {"topic": "Speed", "audience": "Class 8", "goal": "g"}
    plain = writer._brief_block(base, framework)
    assert "PICTURES CHOSEN BY CODE" not in plain
    hinted = writer._brief_block({**base, "kit_hints": ["part 1 \"A car\": figure kind motion (kit motion)"]}, framework)
    assert hinted.startswith(plain) and "figure kind motion (kit motion)" in hinted


def test_brief_from_text_takes_the_topic_the_classes_and_the_subjects_from_the_plan():
    plan = P.route("Class 7 and 8: speed\n\nA car speeds up from rest.")
    brief = P.brief_from_text("Class 7 and 8: speed\n\nA car speeds up from rest.", plan, duration_minutes=4)
    assert brief["topic"] == "Class 7 and 8: speed" and brief["audience"] == "Class 7-8 students"
    assert "physics" in brief["subject"] and brief["duration_minutes"] == 4          # the title line may also reach a component


# ---------------------------------------------------------------- the money

def test_a_model_not_declared_free_is_refused_before_a_call_at_cap_zero():
    called = []
    meter = P.Meter(lambda p, s: called.append(p) or {}, 0.0)
    with pytest.raises(P.CapReached):
        meter("x", "y")
    assert called == [] and meter.calls == 0 and meter.refusals == 1 and not meter.can_call()


def test_a_declared_free_stub_runs_at_cap_zero_and_a_priced_one_stops_at_the_cap():
    free = P.Meter(Stub([{"a": 1}]), 0.0)
    assert free({}, "") if False else free("x", "y") == {"a": 1} and free.spent == 0.0 and free.calls == 1

    class Priced:
        spent_usd = 0.0
        call_estimate_usd = 0.02

        def __call__(self, prompt, system):
            self.spent_usd += 0.03
            return {}
    priced = P.Meter(Priced(), 0.05)
    priced("a", "s")                                            # estimate 0.02 fits; it cost 0.03
    assert priced.spent == pytest.approx(0.03) and priced.guess() == pytest.approx(0.039)
    with pytest.raises(P.CapReached):                           # 0.03 + 0.039 > 0.05
        priced("b", "s")
    assert priced.calls == 1 and priced.spent == pytest.approx(0.03)


def test_the_default_charge_for_an_unmetered_callable_is_conservative_not_a_best_case():
    # A library caller passing a raw paid callable (no spent_usd, no ledger_llm) must not be under-metered: a writer call
    # is several cents, so the stand-in is 5 cents.
    assert P.DEFAULT_CALL_USD == pytest.approx(0.05)
    called = []
    small = P.Meter(lambda p, s: called.append(p) or {}, 0.04)
    with pytest.raises(P.CapReached):
        small("x", "y")
    assert called == [] and small.refusals == 1
    wide = P.Meter(lambda p, s: {}, 0.12)
    wide("a", "s")
    wide("b", "s")
    assert wide.spent == pytest.approx(0.10) and not wide.can_call() and wide.metered is False


def test_an_unmetered_callable_is_charged_the_default_for_every_call():
    meter = P.Meter(lambda p, s: {}, 2.5 * P.DEFAULT_CALL_USD)
    meter("a", "s")
    meter("b", "s")
    assert meter.spent == pytest.approx(2 * P.DEFAULT_CALL_USD) and meter.calls == 2
    with pytest.raises(P.CapReached):
        meter("c", "s")


# ---------------------------------------------------------------- run

SPEEDING = {"kind": "motion", "start_speed": 0, "acceleration": 2, "duration": 6, "marks": [3, 6]}


def _beat(bid, narration, figure=None):
    beat = {"id": bid, "narration": narration, "steps": [{"say": narration.split(".")[0], "show": "v = 2t", "kind": "point"}]}
    if figure is not None:
        beat["figure"] = figure
    return beat


def _lesson(*beats):
    return {"title": "Speeding up", "chapters": [{"id": 1, "title": "ONE", "learning_goal": "g", "role": "explain",
                                                  "beats": list(beats)}]}


WRONG = _lesson(_beat("01", "The car starts from rest and speeds up. At 3 s its speed is 20 m/s.", SPEEDING))
RIGHT = _lesson(_beat("01", "The car starts from rest and speeds up. At 3 s its speed is {speed at 3} m/s.", SPEEDING))
BRIEF = "Class 8: a car speeds up from rest at 2 metres per second every second."


@pytest.fixture()
def bench(tmp_path, monkeypatch):
    monkeypatch.setenv("LESSONFORGE_HOME", str(tmp_path))
    return tmp_path


def steps_of(report, name):
    return [s for s in report.steps if s["step"] == name]


def test_a_wrong_typed_value_is_repaired_in_a_round_and_the_stub_costs_nothing(bench):
    llm = Stub([RIGHT])
    report = P.run(BRIEF, llm=llm, cap_usd=0.0, lesson=WRONG, rounds=2)
    assert [s["step"] for s in report.steps] == ["route", "brief", "lesson", "check", "repair", "workbench"]
    assert steps_of(report, "check")[0]["faults"] == 1 and steps_of(report, "repair")[0]["ok"] is True
    assert "round 1: 1 -> 0" in steps_of(report, "repair")[0]["what"]
    assert report.faults == [] and report.lesson_id and len(llm.calls) == 1
    assert report.spend == {"usd": 0.0, "cap_usd": 0.0, "calls": 1, "refused": 0, "model": True, "metered": True}
    assert "20 m/s" in llm.calls[0][0] and llm.calls[0][1].startswith("You write")      # the writer's system + the kit's rules
    assert "SUBJECT KIT motion" in llm.calls[0][1]
    from lessonforge.harness import workbench as W
    assert "6 m/s" in W.load(report.lesson_id)["chapters"][0]["beats"][0]["narration"]
    assert report.craft and report.plan["kits"] == ["motion"]


def test_free_only_checks_and_files_the_lesson_and_says_the_faults_remain(bench):
    report = P.run(BRIEF, lesson=WRONG)
    assert report.lesson_id and len(report.faults) == 1 and report.spend["model"] is False and report.spend["usd"] == 0.0
    assert steps_of(report, "repair")[0]["ok"] is False and "no model was given" in steps_of(report, "repair")[0]["what"]
    json.dumps(report.to_dict())


def test_a_round_that_gains_nothing_stops_the_loop(bench):
    llm = Stub([WRONG, WRONG, WRONG])
    report = P.run(BRIEF, llm=llm, cap_usd=0.0, lesson=WRONG, rounds=3)
    assert len(llm.calls) == 1 and "no gain" in steps_of(report, "repair")[0]["what"] and len(report.faults) == 1


def test_cap_zero_with_a_model_not_declared_free_refuses_before_calling_it(bench):
    def never(prompt, system):
        raise AssertionError("the model must not be called")
    written = P.run(BRIEF, llm=never, cap_usd=0.0)
    assert written.lesson_id is None and "refused before calling the model" in steps_of(written, "write")[0]["what"]
    assert written.spend["calls"] == 0 and written.spend["usd"] == 0.0
    assert written.spend["refused"] == 1                       # refused before the first call, and still counted
    repaired = P.run(BRIEF, llm=never, cap_usd=0.0, lesson=WRONG, model_router=False)
    assert "refused before calling the model" in steps_of(repaired, "repair")[0]["what"] and repaired.lesson_id
    assert repaired.spend["refused"] == 1 and repaired.spend["calls"] == 0


def test_no_model_and_no_lesson_is_a_report_not_a_failure(bench):
    report = P.run(BRIEF)
    assert report.lesson_id is None and "skipped" in steps_of(report, "write")[0]["what"] and report.plan["kits"] == ["motion"]
    bad = P.run(BRIEF, classes=[13], lesson=WRONG)
    assert bad.steps[0]["step"] == "route" and bad.steps[0]["ok"] is False and bad.lesson_id is None
    unreadable = P.run(BRIEF, lesson="/no/such/lesson.json")
    assert steps_of(unreadable, "lesson")[0]["ok"] is False


def _writer_stub(wrong):
    """A stub writer: plans, writes chapters with a typed wrong speed, and fixes it when code sends the faults back."""
    def llm(prompt, system):
        llm.calls += 1
        if "Plan a" in prompt:
            return {"title": "Motion", "thesis": "t", "anchor": "a car", "anchor_name": "the car", "small_case": "2 m/s^2",
                    "method": ["read"], "glossary": [], "moves": ["question", "guess"],
                    "chapters": [{"title": f"c{i}", "learning_goal": "g", "enters_with": "a", "leaves_with": f"b{i}"} for i in range(7)]}
        if "found these faults" in prompt:             # code sent the faults back: answer with the whole lesson, the number now a gap
            llm.repaired = True
            return json.loads(prompt.split("YOUR LESSON:\n", 1)[1].replace("20 m/s", "{speed at 3} m/s"))
        said = "At 3 s the speed is 20 m/s." if wrong and not llm.repaired else "At 3 s the speed is {speed at 3} m/s."
        return {"title": "Part", "learning_goal": "g", "beats": [
            {"narration": "The car starts from rest and speeds up. " + said + " Look at how the line climbs on the graph as the seconds go by.",
             "visual": "v", "check": "c", "figure": SPEEDING, "steps": [{"say": "speeds up", "show": "v = 2t", "kind": "point"}]}],
            "uses_from_before": [], "running_example_step": "not used", "hands_forward": "next",
            "ledger_update": {"established_add": [], "glossary_add": []}}
    llm.calls, llm.repaired = 0, False
    llm.spent_usd, llm.call_estimate_usd = 0.0, 0.0
    return llm


def test_the_model_path_writes_through_the_writer_with_the_kits_rules_and_ends_with_no_fault(bench):
    llm = _writer_stub(wrong=True)
    report = P.run(BRIEF, llm=llm, cap_usd=0.0)
    assert steps_of(report, "write")[0]["ok"] and report.lesson_id and report.faults == []
    assert report.spend["usd"] == 0.0 and report.spend["calls"] == llm.calls > 1 and llm.repaired
    assert report.brief["kits"] == ["motion"] and report.brief["audience"] == "Class 8 students"
    from lessonforge.harness import workbench as W
    assert "20 m/s" not in json.dumps(W.load(report.lesson_id))


def test_film_is_only_asked_for_when_no_fault_is_left(bench, monkeypatch):
    from lessonforge.harness import workbench as W
    monkeypatch.setattr(W, "film", lambda *a, **k: (_ for _ in ()).throw(AssertionError("must not film")))
    refused = P.run(BRIEF, lesson=WRONG, film=True)
    assert "refused" in steps_of(refused, "film")[0]["what"] and refused.film is None
    seen = []
    monkeypatch.setattr(W, "film", lambda lid, **k: seen.append(lid) or {"status": "done", "video": "/x.mp4", "job_id": "j"})
    done = P.run(BRIEF, lesson=RIGHT, film=True)
    assert done.faults == [] and seen == [done.lesson_id] and done.film["video"] == "/x.mp4" and steps_of(done, "film")[0]["ok"]


def test_a_mixed_lesson_is_checked_beat_by_beat_by_its_own_kit(bench):
    mixed = _lesson(_beat("01", "The car starts from rest and speeds up. At 3 s its speed is 20 m/s.", SPEEDING),
                    _beat("02", "Hydrogen burns in oxygen to make water.", {"kind": "chem_reaction", "equation": "2H2 + O2 -> 2H2O"}))
    report = P.run(MIXED, lesson=mixed)
    assert report.plan["mixed"] and report.plan["kits"] == ["geometry", "motion", "chemistry"]
    assert len(report.faults) == 1 and "20" in report.faults[0] and steps_of(report, "check")[0]["kits"] == ["motion", "chemistry"]


# ---------------------------------------------------------------- the tools

def test_the_tools_are_plain_functions_of_plain_json(bench):
    assert set(P.TOOLS) == {"list_kits", "describe_kit", "route", "check_lesson"}
    listed = P.TOOLS["list_kits"]()
    names = [k["name"] for k in listed["kits"]]
    assert {"geometry", "motion", "chemistry"} <= set(names) and listed["enabled"] is True and listed["mixed_lessons"] is True
    one_kit = P.TOOLS["describe_kit"]("motion")
    assert one_kit["served"] and "speed" in one_kit["keywords"] and one_kit["rules"] and one_kit["example_figures"]
    assert P.TOOLS["describe_kit"]("geometry")["note"].startswith("legacy")
    with pytest.raises(P.PipelineError) as err:
        P.TOOLS["describe_kit"]("nonsense")
    assert "motion" in str(err.value)
    assert P.TOOLS["route"](BRIEF)["kits"] == ["motion"]
    checked = P.TOOLS["check_lesson"](WRONG)
    assert len(checked["faults"]) == 1 and checked["kits"] == ["motion"] and "craft" in checked
    assert P.TOOLS["check_lesson"](json.dumps(RIGHT))["faults"] == []
    for value in (listed, one_kit, checked):
        json.dumps(value)
    from lessonforge.harness import workbench as W
    assert W.lessons() == []                                       # check_lesson saves nothing
    added = P.run(BRIEF, lesson=RIGHT).lesson_id
    assert P.TOOLS["check_lesson"](added)["faults"] == []           # a workbench id works too


@needs_components
def test_describe_kit_lists_the_component_catalogue():
    out = P.TOOLS["describe_kit"]("components")
    assert "force_block" in [c["id"] for c in out["catalogue"]] and "force_block" in out["rules"]
    assert any(c["id"] == "test_tube" for c in P.TOOLS["list_kits"]()["components"])


# ---------------------------------------------------------------- the command line

def cli(monkeypatch, capsys, *argv):
    from lessonforge import cli as C
    monkeypatch.setenv("LESSONFORGE_NO_DOTENV", "1")
    code = C.main(list(argv))
    out = capsys.readouterr()
    return code, out.out, out.err


def test_cli_list_and_describe(monkeypatch, capsys):
    code, out, _ = cli(monkeypatch, capsys, "kits", "list")
    assert code == 0 and "motion" in out and "chem_reaction" in out and "geometry" in out and "legacy" in out
    code, out, _ = cli(monkeypatch, capsys, "kits", "describe", "motion")
    assert code == 0 and '"name": "motion"' in out and "RULES THE WRITER IS GIVEN" in out and "example_figures" in out
    code, out, err = cli(monkeypatch, capsys, "kits", "describe", "nonsense")
    assert code == 2 and "no kit 'nonsense'" in err and out == ""


def test_cli_route_prints_the_choice_per_part_and_honours_the_class_filter(monkeypatch, capsys):
    text = "A car speeds up from rest.\n\nIn triangle ABC find angle C."
    code, out, _ = cli(monkeypatch, capsys, "kits", "route", text, "--classes", "7,8")
    assert code == 0 and "motion" in out and "geometry" in out and "(mixed)" in out
    code, out, _ = cli(monkeypatch, capsys, "kits", "route", text, "--classes", "6", "--json")
    plan = json.loads(out)
    assert [b["kit"] for b in plan["beats"]] == [None, "geometry"] and plan["classes"] == [6]
    code, _, err = cli(monkeypatch, capsys, "kits", "route", text, "--classes", "13")
    assert code == 2 and "outside classes 1 to 12" in err
    code, _, err = cli(monkeypatch, capsys, "kits", "route")
    assert code == 2 and "needs the text" in err


def test_cli_route_reads_a_brief_file(monkeypatch, capsys, tmp_path):
    f = tmp_path / "brief.md"
    f.write_text("Hydrogen burns in oxygen to make water.", encoding="utf-8")
    code, out, _ = cli(monkeypatch, capsys, "kits", "route", str(f), "--json")
    assert code == 0 and json.loads(out)["kits"] == ["chemistry"]


def test_cli_run_needs_a_cap_whenever_a_model_would_write_and_never_reaches_for_one_without_it(monkeypatch, capsys, bench):
    from lessonforge.harness import writer
    monkeypatch.setattr(writer, "default_llm", lambda *a, **k: (_ for _ in ()).throw(AssertionError("no model without --cap")))
    code, out, err = cli(monkeypatch, capsys, "kits", "run", BRIEF)
    assert code == 2 and "--cap" in err and out == ""
    code, out, err = cli(monkeypatch, capsys, "kits", "run", BRIEF, "--cap", "0")
    assert code == 2 and "--cap" in err
    monkeypatch.setattr(writer, "default_llm", lambda *a, **k: None)
    code, out, err = cli(monkeypatch, capsys, "kits", "run", BRIEF, "--cap", "0.05")
    assert code == 2 and "no model is configured" in err


def test_cli_run_checks_a_given_lesson_for_free_and_exits_by_its_faults(monkeypatch, capsys, bench, tmp_path):
    from lessonforge.harness import writer
    monkeypatch.setattr(writer, "default_llm", lambda *a, **k: (_ for _ in ()).throw(AssertionError("free only")))
    good, bad = tmp_path / "good.json", tmp_path / "bad.json"
    good.write_text(json.dumps(RIGHT), encoding="utf-8")
    bad.write_text(json.dumps(WRONG), encoding="utf-8")
    code, out, err = cli(monkeypatch, capsys, "kits", "run", BRIEF, "--lesson", str(good))
    report = json.loads(out)
    assert code == 0 and report["faults"] == [] and report["lesson_id"] and report["spend"]["model"] is False
    assert "[kit-pipeline] route" in err                                    # the trace goes to stderr as it happens
    code, out, _ = cli(monkeypatch, capsys, "kits", "run", BRIEF, "--lesson", str(bad))
    assert code == 1 and len(json.loads(out)["faults"]) == 1


def test_cli_run_with_a_cap_repairs_through_the_metered_model(monkeypatch, capsys, bench, tmp_path):
    from lessonforge.harness import writer
    seen = []
    monkeypatch.setattr(writer, "default_llm", lambda *a, **k: (lambda prompt, system: seen.append(prompt) or RIGHT))
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps(WRONG), encoding="utf-8")
    code, out, _ = cli(monkeypatch, capsys, "kits", "run", BRIEF, "--lesson", str(bad), "--cap", "0.05")
    report = json.loads(out)
    assert code == 0 and report["faults"] == [] and report["spend"]["calls"] == 1 and report["spend"]["cap_usd"] == 0.05
    assert report["spend"]["usd"] == 0.0 and len(seen) == 1            # the ledger did not grow: the stand-in spent nothing


# ---------------------------------------------------------------- the MCP tools (a stand-in FastMCP: the package is not needed)

def test_the_mcp_tools_are_the_pipeline_tools_and_check_only(monkeypatch, bench):
    import importlib
    import sys
    import types

    class FastMCP:
        def __init__(self, name, instructions=""):
            self.instructions = instructions

        def tool(self, *a, **k):
            return lambda fn: fn

    fake = types.ModuleType("mcp.server.fastmcp")
    fake.FastMCP, fake.Image = FastMCP, object
    for name, mod in (("mcp", types.ModuleType("mcp")), ("mcp.server", types.ModuleType("mcp.server")), ("mcp.server.fastmcp", fake)):
        monkeypatch.setitem(sys.modules, name, mod)
    monkeypatch.delitem(sys.modules, "lessonforge.mcp_server", raising=False)
    server = importlib.import_module("lessonforge.mcp_server")
    try:
        assert {"motion", "chemistry"} <= {k["name"] for k in server.list_kits()["kits"]}
        assert server.describe_kit("motion")["rules"]
        assert server.route_kits(BRIEF, classes="8")["kits"] == ["motion"]
        assert "motion" not in server.route_kits(BRIEF, classes="6")["kits"]
        none = server.run_kit_pipeline(BRIEF)
        assert none["lesson_id"] is None and "skipped" in none["steps"][-1]["what"]
        report = server.run_kit_pipeline(BRIEF, lesson_json=json.dumps(WRONG))
        assert report["lesson_id"] and len(report["faults"]) == 1 and report["spend"]["model"] is False
        assert [s["step"] for s in report["steps"]][-2:] == ["repair", "workbench"] and "film" not in [s["step"] for s in report["steps"]]
    finally:
        monkeypatch.delitem(sys.modules, "lessonforge.mcp_server", raising=False)
