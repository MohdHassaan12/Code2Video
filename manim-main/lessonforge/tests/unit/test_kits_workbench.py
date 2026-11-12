"""A motion lesson through the workbench, the improver and the MCP note: check, edit, revert, and the one-subject rule."""
import pytest

from lessonforge import kits, knobs
from lessonforge.harness import improver
from lessonforge.harness import workbench as W

SPEEDING = {"kind": "motion", "start_speed": 0, "acceleration": 2, "duration": 6, "marks": [3, 6]}
BRAKING = {"kind": "motion", "start_speed": 10, "acceleration": -2, "duration": 4}


def _beat(bid, narration, figure=None, quiz=None):
    beat = {"id": bid, "narration": narration, "steps": [{"say": narration.split(".")[0], "show": "v = 2t", "kind": "point"}]}
    if figure is not None:
        beat["figure"] = figure
    if quiz:
        beat["quiz"] = quiz
    return beat


def _lesson(*beats):
    return {"title": "Speeding up", "chapters": [{"id": 1, "title": "ONE", "learning_goal": "g", "role": "explain",
                                                  "beats": list(beats)}]}


def _motion():
    return _lesson(
        _beat("01", "The car starts from rest and speeds up. At 3 s its speed is {speed at 3} m/s."
                    " After {duration} s it has gone {distance at duration} m. What is the speed at 3 s?", SPEEDING,
              quiz={"question": "What is the speed at 3 s?", "options": ["{speed at 3} m/s", "20 m/s"], "answer_index": 0,
                    "why": ["right", "a wrong one on purpose"]}),
        _beat("02", "Now the driver brakes. The car slows down.", BRAKING))


@pytest.fixture()
def bench(tmp_path, monkeypatch):
    monkeypatch.setenv("LESSONFORGE_HOME", str(tmp_path))
    return W.add(_motion(), "speeding")["lesson_id"]


def test_adding_a_motion_lesson_fills_its_gaps_and_reports_no_fault(bench):
    saved = W.load(bench)
    first = saved["chapters"][0]["beats"][0]
    assert first["narration"].startswith("The car starts from rest and speeds up. At 3 s its speed is 6 m/s.")
    assert "36 m" in first["narration"] and not kits.get("motion").unfilled(saved)
    assert first["quiz"]["options"] == ["6 m/s", "20 m/s"]
    found = W.check(bench)
    assert found["faults"] == [] and found["versions"] == 1               # the wrong option on purpose is not a fault


def test_a_claim_the_picture_denies_is_a_fault_on_check(tmp_path, monkeypatch):
    monkeypatch.setenv("LESSONFORGE_HOME", str(tmp_path))
    added = W.add(_lesson(_beat("01", "The car speeds up.", BRAKING)), "wrong")
    assert len(added["faults"]) == 1 and "speeds up" in added["faults"][0]


def test_an_edit_that_brings_in_a_wrong_value_is_refused_and_a_right_one_is_kept(bench):
    wrong = W.edit(bench, [{"op": "insert_beat", "after": "01", "beat": {
        "narration": "At 6 s the speed is 20 m/s.", "figure": SPEEDING,
        "steps": [{"say": "At 6 s", "show": "v = 12", "kind": "point"}]}}])
    assert wrong["kept"] is False and wrong["faults_before"] == 0
    assert any("20 m/s" in f and "which the picture does not show" in f for f in wrong["faults"])
    assert len(W.history(bench)) == 1                                       # nothing was saved
    right = W.edit(bench, [{"op": "insert_beat", "after": "01", "beat": {
        "narration": "At 6 s the speed is {speed at 6} m/s.", "figure": SPEEDING,
        "steps": [{"say": "At 6 s", "show": "v = {speed at 6}", "kind": "point"}]}}])
    assert right["kept"] is True and right["faults"] == [] and right["version"] == 2
    inserted = W.load(bench)["chapters"][0]["beats"][1]
    assert inserted["narration"] == "At 6 s the speed is 12 m/s." and inserted["steps"][0]["show"] == "v = 12"


def test_an_edit_that_changes_the_figure_so_a_claim_fails_is_refused(bench):
    refused = W.edit(bench, [{"op": "set_beat", "beat": "02", "fields": {"figure": SPEEDING}}])
    assert refused["kept"] is False and any("slows down" in f for f in refused["faults"])


def test_revert_goes_back_and_checks_again(bench):
    W.edit(bench, [{"op": "set_beat", "beat": "02", "fields": {"narration": "Now the driver brakes hard. The car slows down."}}])
    assert "brakes hard" in W.load(bench)["chapters"][0]["beats"][1]["narration"]
    back = W.revert(bench, 1)
    assert back["faults"] == [] and back["version"] == 3
    assert "brakes hard" not in W.load(bench)["chapters"][0]["beats"][1]["narration"]


def test_an_unknown_op_message_is_the_one_it_always_was(bench):
    with pytest.raises(W.WorkbenchError) as err:
        W.apply_edits(W.load(bench), [{"op": "nonsense"}])
    assert str(err.value) == "edit 1: unknown op 'nonsense' (set_beat, insert_beat, delete_beat, set_shape)"


def test_a_lesson_that_draws_two_subjects_reports_one_clear_fault_only_while_mixing_is_off(tmp_path, monkeypatch):
    monkeypatch.setenv("LESSONFORGE_HOME", str(tmp_path))
    mixed = _lesson(_beat("01", "A car on a road.", SPEEDING),
                    _beat("02", "A shape with a gap {angle A}.", {"kind": "shape", "points": {"A": [0, 0], "B": [4, 0], "C": [0, 3]},
                                                                  "polygon": "ABC"}))
    with knobs.applied({"LESSONFORGE_KITS_MIXED": "0"}):
        added = W.add(mixed, "mixed")
        assert added["faults"] == ["this lesson draws from two subject kits (geometry, motion); give each lesson one subject"]
    assert not any("two subject kits" in f for f in W.faults_of(mixed))      # the default: each kit checks its own beats
    with knobs.applied({"LESSONFORGE_KITS": "0"}):
        assert not any("two subject kits" in f for f in W.faults_of(mixed))


def test_a_geometry_lesson_is_untouched_by_the_motion_seams():
    from lessonforge.harness import shapes
    assert kits.active({"title": "t", "shapes": {"a": {"points": {"A": [0, 0]}}}, "chapters": []}) == []
    assert kits.settle_active({"title": "t", "chapters": []}) == {"title": "t", "chapters": []}
    assert shapes.SHAPE_RULES in improver._system()


def test_the_improver_is_given_the_kits_rules_in_the_user_text_not_the_system_prompt(bench):
    seen = []

    def ask(tier, system, text, image):
        seen.append((system, text))
        return {"edits": [], "why": "nothing"}, 0.001, {}
    # a fault keeps the loop from stopping before the first call
    W.edit(bench, [{"op": "set_beat", "beat": "02", "fields": {"narration": "The car speeds up."}}], keep_if_worse=True)
    improver.improve(bench, cap_usd=1.0, rounds=1, look=False, ask=ask, log=lambda *a: None)
    system, text = seen[0]
    assert system == improver._system() and "SUBJECT KIT motion" not in system
    assert text.startswith("THE SUBJECT KIT THIS LESSON DRAWS FROM") and "{speed at 3}" in text and "LESSON:\n{" in text
    assert "speeds up" in text                                              # the fault code found is in the same text


def test_slim_and_the_addendum_are_empty_for_a_lesson_that_uses_no_kit():
    plain = _lesson(_beat("01", "Look."))
    assert kits.slim(plain) == {} and kits.rules_for_lesson(plain) == "" and kits.edit_ops() == {}
    assert kits.rules_for_lesson(_motion()).startswith("\n\nSUBJECT KIT motion")
    with knobs.applied({"LESSONFORGE_KITS": "0"}):
        assert kits.rules_for_lesson(_motion()) == "" and kits.mcp_note() == ""


def test_the_mcp_instructions_carry_one_sentence_per_served_kit(monkeypatch):
    """The MCP package is not needed: a stand-in FastMCP records the instructions the server is built with."""
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
    server = importlib.import_module("lessonforge.mcp_server").server
    note = kits.mcp_note()
    served = [k for k in kits.all_kits() if not k.legacy and k.mcp_note]       # one sentence per served kit that has a note
    assert "{speed at 3}" in note and note.count(".") <= len(served) and server.instructions.endswith(" " + note)
    assert server.instructions.startswith("Lessonforge makes narrated lesson videos.")
    monkeypatch.delitem(sys.modules, "lessonforge.mcp_server", raising=False)
    with knobs.applied({"LESSONFORGE_KITS": "0"}):
        plain = importlib.import_module("lessonforge.mcp_server").server.instructions
    assert plain.endswith("repeat it.") and "motion" not in plain.lower()
    monkeypatch.delitem(sys.modules, "lessonforge.mcp_server", raising=False)


def test_a_registered_op_from_a_kit_is_applied_and_listed(monkeypatch, tmp_path):
    seen = []
    monkeypatch.setattr(kits, "edit_ops", lambda: {"nudge": lambda lesson, edit: seen.append(edit["by"])})
    out = W.apply_edits(_motion(), [{"op": "nudge", "by": 2}])
    assert seen == [2] and out["title"] == "Speeding up"
    with pytest.raises(W.WorkbenchError) as err:
        W.apply_edits(_motion(), [{"op": "nonsense"}])
    assert str(err.value).endswith("set_shape, nudge)")

    def refuse(lesson, edit):
        raise kits.KitError("no way")
    monkeypatch.setattr(kits, "edit_ops", lambda: {"nudge": refuse})
    with pytest.raises(W.WorkbenchError, match="edit 1: no way"):
        W.apply_edits(_motion(), [{"op": "nudge"}])


def test_a_kit_that_crashes_in_a_workbench_seam_costs_nothing(monkeypatch, tmp_path):
    monkeypatch.setenv("LESSONFORGE_HOME", str(tmp_path))
    motion = kits.get("motion")

    def boom(*_a, **_k):
        raise RuntimeError("boom")
    monkeypatch.setattr(motion, "settle", boom)
    monkeypatch.setattr(motion, "expected_fault", boom)
    lesson = _lesson(_beat("01", "Its speed is {speed at 3} m/s.", SPEEDING))
    assert kits.settle_active(lesson) == lesson and kits.lesson_faults(lesson) == []
    assert kits.is_expected_fault("beat 1 (chapter 1) quiz option 2: says 20 m/s, which the picture does not show", lesson) is False
    assert W.add(lesson, "crash")["lesson_id"]            # the lesson is still put on the bench
