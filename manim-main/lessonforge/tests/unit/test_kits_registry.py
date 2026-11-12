"""The kit registry and the shared base: registration rules, the switch, and the generic settle loop.

Uses a toy kit ("toy": a figure with one number ``n``) so none of this depends on a real subject. The real kits are
held to the same rules by ``test_every_registered_kit_meets_the_protocol`` at the bottom.
"""
import json
import re
import subprocess
import sys

import pytest

from lessonforge import kits, knobs
from lessonforge.kits import registry
from lessonforge.kits.base import GAP, STRAY, STRAY_RE, KitBase, KitCases, KitError, arithmetic


class ToyModel:
    notes: tuple = ()

    def __init__(self, n):
        self.n = n

    def facts(self):
        return {"n": self.n}

    def shown(self):
        return frozenset({float(self.n)})


class ToyKit(KitBase):
    name = "toy"
    figure_kinds = ("toy",)
    builder = {"toy": "os.path:basename"}
    rules = "A toy figure: {\"kind\":\"toy\",\"n\":3}. Write a gap {n}."

    def solve(self, figure):
        n = figure.get("n")
        if not isinstance(n, (int, float)) or n < 0:
            raise KitError("toy n must be a number from 0 up")
        return ToyModel(n)

    def fill_gap(self, expr, model):
        try:
            value = arithmetic(re.sub(r"\bn\b", repr(float(model.n)), expr))
        except ValueError as exc:
            raise KitError(f"gap {{{expr}}} can only hold n, numbers and + - * / ({exc})") from exc
        return f"{value:g}", value

    def claims(self, text, model):
        if re.search(r"\bbig\b", text, re.I) and model.n < 5 and not re.search(r"\bnot\b", text, re.I):
            return [f"the words say it is big, but n is {model.n:g}"]
        return []

    def stray_numbers(self, text, model, used):
        allowed = set(model.shown()) | set(used)
        return [f"{m.group(1)} apples" for m in re.finditer(r"(\d+(?:\.\d+)?)\s*apples", text)
                if float(m.group(1)) not in allowed]

    def cases(self):
        good = _lesson([_beat("There are {n} apples.", {"kind": "toy", "n": 3})])
        return KitCases(good=(good,), refused=((_lesson([_beat("It is big.", {"kind": "toy", "n": 3})]), "big"),),
                        gaps=(("n + 1", {"kind": "toy", "n": 3}, "4"),))


def _beat(narration, figure=None, steps=None, quiz=None):
    beat = {"narration": narration, "steps": steps if steps is not None else []}
    if figure is not None:
        beat["figure"] = figure
    if quiz:
        beat["quiz"] = quiz
    return beat


def _lesson(beats):
    return {"title": "t", "chapters": [{"title": "ONE", "beats": beats}]}


@pytest.fixture()
def reg(monkeypatch):
    """An empty registry for the test, restored afterwards."""
    monkeypatch.setattr(registry, "_KITS", {})
    return registry


class Other(ToyKit):
    name = "other"
    figure_kinds = ("other",)
    builder = {"other": "os.path:basename"}


# ---------------------------------------------------------------- registration

def test_register_returns_the_kit_and_get_finds_it(reg):
    kit = ToyKit()
    assert reg.register(kit) is kit
    assert reg.get("toy") is kit and reg.for_kind("toy") is kit and reg.all_kits() == [kit]


def test_a_duplicate_name_and_a_taken_kind_raise(reg):
    reg.register(ToyKit())
    with pytest.raises(ValueError, match="already registered"):
        reg.register(ToyKit())

    class Twin(ToyKit):
        name = "twin"
    with pytest.raises(ValueError, match="already owned by kit 'toy'"):
        reg.register(Twin())


def test_a_builtin_kind_is_refused_unless_the_kit_is_a_legacy_adapter(reg):
    class Takes(ToyKit):
        name = "takes"
        figure_kinds = ("graph",)
    with pytest.raises(ValueError, match="built-in kind"):
        reg.register(Takes())

    class Adapter(Takes):
        name = "adapter"
        legacy = True
    assert reg.register(Adapter()).legacy


def test_a_kit_without_rules_or_kinds_or_methods_is_refused(reg):
    class NoRules(ToyKit):
        name, rules = "norules", "  "
    with pytest.raises(ValueError, match="needs rules"):
        reg.register(NoRules())

    class NoKinds(ToyKit):
        name, figure_kinds = "nokinds", ()
    with pytest.raises(ValueError, match="needs figure_kinds"):
        reg.register(NoKinds())

    class NoBuilder(ToyKit):
        name, builder = "nobuilder", {}
    with pytest.raises(ValueError, match="needs a builder"):
        reg.register(NoBuilder())

    class NoName(ToyKit):
        name = ""
    with pytest.raises(ValueError, match="needs a name"):
        reg.register(NoName())

    class Bare:
        name, figure_kinds, rules, legacy = "bare", ("bare",), "r", False
    with pytest.raises(TypeError, match="lacks"):
        reg.register(Bare())


def test_a_kit_that_cannot_name_its_model_cannot_be_made():
    class Half(KitBase):
        name, figure_kinds, rules = "half", ("half",), "r"

        def solve(self, figure):
            raise KitError("x")
    with pytest.raises(TypeError, match="abstract"):
        Half()


# ---------------------------------------------------------------- serving and the switch

def test_an_unknown_kind_is_served_by_nobody(reg):
    reg.register(ToyKit())
    assert reg.for_kind("nonsense") is None and reg.serving("nonsense") is None
    assert reg.serving(None) is None and reg.builder_for("nonsense") is None


def test_a_served_kit_answers_and_the_switch_turns_it_off(reg):
    kit = reg.register(ToyKit())
    lesson = _lesson([_beat("x", {"kind": "toy", "n": 1})])
    assert reg.serving("toy") is kit and reg.kinds() == ("toy",) and reg.active(lesson) == [kit]
    with knobs.applied({"LESSONFORGE_KITS": "0"}):
        assert not reg.enabled()
        assert reg.serving("toy") is None and reg.kinds() == () and reg.active(lesson) == []
        assert reg.builder_for("toy") is None and reg.rules_for(["toy"]) == "" and reg.lesson_faults(lesson) == []
    assert reg.enabled()


def test_the_switch_is_a_listed_control_that_defaults_on(monkeypatch):
    monkeypatch.delenv("LESSONFORGE_KITS", raising=False)
    control = next(c for c in knobs.CONTROLS if c.id == "LESSONFORGE_KITS")
    assert control.kind == "toggle" and control.default == "1"
    assert knobs.validate({"LESSONFORGE_KITS": "0"}) == {"LESSONFORGE_KITS": "0"}
    assert knobs.validate({"LESSONFORGE_KITS": "1"}) == {}           # the default is not recorded
    monkeypatch.setenv("LESSONFORGE_KITS", "0")
    assert not registry.enabled()


def test_a_legacy_kit_is_never_served(reg):
    class Legacy(ToyKit):
        name, figure_kinds, legacy = "old", ("old",), True
    kit = reg.register(Legacy())
    lesson = _lesson([_beat("x", {"kind": "old", "n": 1})])
    assert reg.for_kind("old") is kit and reg.serving("old") is None
    assert reg.kinds() == () and reg.active(lesson) == [] and reg.rules_for(["old"]) == ""


def test_builder_for_resolves_a_dotted_path_lazily(reg):
    class Drawn(ToyKit):
        name, figure_kinds = "drawn", ("drawn",)
        builder = {"drawn": "os.path:basename"}
    reg.register(Drawn())
    import os.path
    assert reg.builder_for("drawn") is os.path.basename


def test_rules_for_is_empty_without_a_kit_and_adds_the_rules_of_a_named_one(reg):
    reg.register(ToyKit())
    logged = []
    assert reg.rules_for(None) == "" and reg.rules_for([]) == "" and reg.rules_for("") == ""
    text = reg.rules_for(["toy", "toy"])
    assert text.startswith("\n\nSUBJECT KIT toy") and ToyKit.rules in text and text.count("SUBJECT KIT") == 1
    assert reg.rules_for("toy") == text
    assert reg.rules_for(["nope"], log=logged.append) == "" and "nope" in logged[0] and "not registered" in logged[0]


def test_guarded_returns_the_default_and_says_why():
    logged = []
    assert registry.guarded("x", lambda: 1 / 0, "d", logged.append) == "d"
    assert "[kits] x failed (ZeroDivisionError" in logged[0]
    assert registry.guarded("x", lambda: 7, "d", logged.append) == 7


# ---------------------------------------------------------------- lesson faults and the one-subject rule

def test_lesson_faults_runs_the_active_kit_and_drops_its_expected_faults(reg):
    reg.register(ToyKit())
    quiz = {"question": "How many?", "options": ["3 apples", "5 apples"], "answer_index": 0, "why": ["a", "b"]}
    lesson = _lesson([_beat("It is big.", {"kind": "toy", "n": 3}, quiz=quiz)])
    found = reg.lesson_faults(lesson)
    assert any("big" in f for f in found)
    assert not any("quiz option 2" in f for f in found), "a wrong option's number is the point of the option"
    assert reg.lesson_faults(_lesson([_beat("plain words")])) == []


def test_a_lesson_that_draws_from_two_kits_gets_one_fault_while_mixing_is_off(reg):
    reg.register(ToyKit())
    reg.register(Other())
    lesson = _lesson([_beat("a", {"kind": "toy", "n": 1}), _beat("b", {"kind": "other", "n": 1})])
    with knobs.applied({"LESSONFORGE_KITS_MIXED": "0"}):
        found = reg.lesson_faults(lesson)
        assert found == [registry.ONE_SUBJECT.format(names="toy, other")]
        assert "give each lesson one subject" in found[0]
        assert not reg.multi(lesson)
    assert reg.lesson_faults(lesson) == []            # the default: mixing is on, each beat is its own kit's


def test_a_legacy_kit_counts_towards_the_one_subject_rule_while_mixing_is_off(reg):
    class Legacy(ToyKit):
        name, figure_kinds, legacy = "old", ("old",), True
    reg.register(Legacy())
    reg.register(ToyKit())
    lesson = _lesson([_beat("a", {"kind": "toy", "n": 1}), _beat("b", {"kind": "old", "n": 1})])
    with knobs.applied({"LESSONFORGE_KITS_MIXED": "0"}):
        assert any("two subject kits (old, toy)" in f for f in reg.lesson_faults(lesson))
    assert not any("two subject kits" in f for f in reg.lesson_faults(lesson))
    # a lesson that is only the legacy subject is not the registry's business
    assert reg.lesson_faults(_lesson([_beat("b", {"kind": "old", "n": 1})])) == []


def test_a_kit_that_crashes_costs_nothing(reg):
    class Boom(ToyKit):
        def settle(self, lesson):
            raise RuntimeError("boom")
    reg.register(Boom())
    logged = []
    assert reg.lesson_faults(_lesson([_beat("a", {"kind": "toy", "n": 1})]), log=logged.append) == []
    assert "boom" in logged[0]


# ---------------------------------------------------------------- the shared settle loop (toy kit)

def test_settle_fills_gaps_in_every_text_and_reports_nothing_for_a_clean_beat():
    quiz = {"question": "How many, {n}?", "options": ["{n} apples", "{n + 1} apples"], "answer_index": 0,
            "why": ["{n} it is", "no"], "explain": "{n}"}
    lesson = _lesson([_beat("There are {n} apples.", {"kind": "toy", "n": 3},
                            steps=[{"say": "There are {n}", "show": "{n} apples"}], quiz=quiz)])
    out, issues = ToyKit().settle(lesson)
    beat = out["chapters"][0]["beats"][0]
    assert beat["narration"] == "There are 3 apples."
    assert beat["steps"][0] == {"say": "There are 3", "show": "3 apples"}
    assert beat["quiz"]["options"] == ["3 apples", "4 apples"] and beat["quiz"]["question"] == "How many, 3?"
    assert beat["quiz"]["why"] == ["3 it is", "no"]
    assert issues == []
    assert lesson["chapters"][0]["beats"][0]["narration"] == "There are {n} apples."      # the input is untouched


def test_settle_refuses_claims_stray_numbers_and_bad_gaps():
    kit = ToyKit()
    _, issues = kit.settle(_lesson([_beat("It is big.", {"kind": "toy", "n": 3})]))
    assert issues == ["beat 1 (chapter 1) narration: the words say it is big, but n is 3"]
    _, issues = kit.settle(_lesson([_beat("It is not big.", {"kind": "toy", "n": 3})]))
    assert issues == []
    _, issues = kit.settle(_lesson([_beat("There are 9 apples.", {"kind": "toy", "n": 3})]))
    assert issues == [STRAY.format(ref="beat 1 (chapter 1)", where=" narration", what="9 apples")]
    _, issues = kit.settle(_lesson([_beat("There are {m} apples.", {"kind": "toy", "n": 3})]))
    assert len(issues) == 1 and "can only hold n" in issues[0]
    _, issues = kit.settle(_lesson([_beat("There are {n} apples.", {"kind": "toy", "n": -1})]))
    assert issues == ["beat 1 (chapter 1): toy n must be a number from 0 up"]


def test_settle_flags_a_gap_on_a_beat_with_no_figure_of_the_kit_but_not_another_kits(reg):
    kit = reg.register(ToyKit())
    _, issues = kit.settle(_lesson([_beat("There are {n} apples.")]))
    assert issues == ["beat 1 (chapter 1) narration: gap {n} on a beat with no toy figure"]
    reg.register(Other())
    out, issues = kit.settle(_lesson([_beat("There are {n} apples.", {"kind": "other", "n": 2})]))
    assert issues == [] and "{n}" in out["chapters"][0]["beats"][0]["narration"]
    _, issues = kit.settle(_lesson([_beat("There are {n} apples.", {"kind": "unregistered"})]))
    assert len(issues) == 1


def test_settle_refuses_two_quiz_options_that_come_out_the_same():
    quiz = {"question": "q", "options": ["{n} apples", "3 apples"], "answer_index": 0, "why": ["a", "b"]}
    _, issues = ToyKit().settle(_lesson([_beat("Count.", {"kind": "toy", "n": 3}, quiz=quiz)]))
    assert len(issues) == 1 and "two options come out the same once filled" in issues[0]


def test_a_stray_number_message_is_what_expected_fault_recognises():
    kit = ToyKit()
    quiz = {"question": "q", "options": ["{n} apples", "9 apples"], "answer_index": 0, "why": ["a", "b"]}
    lesson = _lesson([_beat("Count.", {"kind": "toy", "n": 3}, quiz=quiz)])
    _, issues = kit.settle(lesson)
    assert len(issues) == 1 and STRAY_RE.match(issues[0])
    assert kit.expected_fault(issues[0], lesson) is True                    # option 2 is a wrong option
    lesson["chapters"][0]["beats"][0]["quiz"]["answer_index"] = 1
    assert kit.expected_fault(issues[0], lesson) is False                   # option 2 is the answer: a real fault
    assert kit.expected_fault("something else", lesson) is False


def test_unfilled_reads_words_and_not_a_figures_json():
    kit = ToyKit()
    assert kit.unfilled(_lesson([_beat("There are {n} apples.")]))
    assert not kit.unfilled(_lesson([_beat("fine", {"kind": "toy", "points": {"A": [1, 1]}})]))
    assert not kit.unfilled(kit.settle(_lesson([_beat("{n} apples", {"kind": "toy", "n": 2})]))[0])


def test_figure_level_defaults_follow_solve():
    kit = ToyKit()
    assert kit.figure_issues({"kind": "toy", "n": 2}) == [] and kit.figure_issues({"kind": "toy"}) == ["toy n must be a number from 0 up"]
    assert kit.normalise_figure({"kind": "toy", "n": 2}) == {"kind": "toy", "n": 2} and kit.normalise_figure({"kind": "toy"}) is None
    assert kit.numbers({"kind": "toy", "n": 2.5}) == {"2.5"} and kit.numbers({"kind": "toy"}) == set()
    assert kit.describe({"kind": "toy", "n": 2}) == "n 2" and "must be" in kit.describe({"kind": "toy"})


def test_uses_recognises_figures_and_declared_data():
    kit = ToyKit()
    assert kit.uses_figures(_lesson([_beat("a", {"kind": "toy", "n": 1})])) and kit.uses(_lesson([_beat("a", {"kind": "toy"})]))
    assert not kit.uses(_lesson([_beat("a")])) and not kit.uses({"title": "t"})

    class WithData(ToyKit):
        data_key = "things"
    with_data = WithData()
    plain = _lesson([_beat("a", {"kind": "x", "use": "thing"})])
    assert not with_data.uses(plain) and with_data.uses(plain, after_edit=True)
    assert with_data.uses({**_lesson([_beat("a")]), "things": {"a": {}}})
    assert not kit.uses(plain, after_edit=True)                          # no data_key: "use" means nothing


def test_repair_prompt_lists_faults_facts_and_the_whole_lesson():
    kit = ToyKit()
    lesson = _lesson([_beat("It is big.", {"kind": "toy", "n": 3})])
    text = kit.repair_prompt(lesson, ["a fault"])
    assert "- a fault" in text and "- n 3" in text and "Return the WHOLE lesson again as JSON" in text
    assert text.endswith(json.dumps(lesson, ensure_ascii=False))
    assert kit.merge_declared(lesson, {"things": {}}) is None and "things" not in lesson


def test_arithmetic_takes_numbers_and_four_operations_only():
    assert arithmetic("2 + 3 * (4 - 1) / 3") == 5.0 and arithmetic("-2 * 3") == -6.0
    for bad in ("__import__('os')", "2 ** 3", "x + 1", "2 +", "True"):
        with pytest.raises(ValueError):
            arithmetic(bad)


# ---------------------------------------------------------------- the boundaries

def test_importing_the_kits_package_pulls_in_no_manim_numpy_or_harness():
    code = (f"import sys; sys.path[:0] = {sys.path!r}; import lessonforge.kits; "
            "bad = [m for m in ('manim', 'numpy', 'lessonforge.harness', 'lessonforge.longform.figures') if m in sys.modules]; "
            "assert not bad, bad; print('ok')")
    done = subprocess.run([sys.executable, "-I", "-c", code], capture_output=True, text=True, timeout=120,
                          env={"PATH": "", "HOME": "/nonexistent"})
    assert done.returncode == 0 and done.stdout.strip().endswith("ok"), done.stderr[-800:]


def test_the_gap_and_stray_patterns_match_the_ones_in_shapes():
    from lessonforge.harness import shapes
    assert GAP.pattern == shapes._GAP.pattern
    sample = STRAY.format(ref="beat 2 (chapter 1)", where=" quiz option 3", what="10 m/s")
    assert STRAY_RE.match(sample)
    geometry_message = ("beat 2 (chapter 1) quiz option 3: says 100 degrees, which the picture does not show "
                        "(write a gap such as {angle D} instead of a number)")
    assert STRAY_RE.match(geometry_message), "the shared matcher also reads geometry's own message"


def test_builtin_kinds_cover_every_kind_the_engine_already_draws():
    from lessonforge.harness import writer
    assert set(registry.BUILTIN_KINDS) >= set(writer.FIGURE_KINDS) | set(writer.PREPARED_KINDS) | set(writer.IMPORTED_KINDS)
    pytest.importorskip("manim")
    from lessonforge.longform import figures
    assert set(registry.BUILTIN_KINDS) >= set(figures.KINDS)


def test_the_package_exports_the_registry_api():
    for name in ("register", "serving", "active", "rules_for", "lesson_faults", "guarded", "builder_for", "KitBase",
                 "KitError", "KitCases", "GAP"):
        assert hasattr(kits, name), name


# ---------------------------------------------------------------- conformance: every registered kit

def test_every_registered_kit_meets_the_protocol():
    """Rules non-empty, at least one good case, at least three refused cases, gaps exact; run through its own settle."""
    for kit in kits.all_kits():
        for method in ("uses_figures", "uses", "figure_issues", "settle", "unfilled", "expected_fault", "cases"):
            assert callable(getattr(kit, method)), (kit.name, method)
        assert kit.figure_kinds and all(isinstance(k, str) for k in kit.figure_kinds), kit.name
        assert str(kit.rules).strip(), f"{kit.name} has no rules"
        cases = kit.cases()
        assert len(cases.good) >= 1 and len(cases.refused) >= 3, kit.name
        for good in cases.good:
            _, issues = kit.settle(good)
            assert issues == [] and not kit.unfilled(kit.settle(good)[0]), (kit.name, issues)
        for bad, fragment in cases.refused:
            _, issues = kit.settle(bad)
            assert any(fragment in i for i in issues), (kit.name, fragment, issues)
        if hasattr(kit, "solve"):                        # a native kit fills its own gaps; an adapter is held by its parity test
            for expr, figure, expected in cases.gaps:
                assert kit.fill_gap(expr, kit.solve(figure))[0] == expected, (kit.name, expr)


def test_the_toy_kit_itself_meets_the_conformance_rules(reg):
    kit = reg.register(ToyKit())
    cases = kit.cases()
    for good in cases.good:
        assert kit.settle(good)[1] == []
    for bad, fragment in cases.refused:
        assert any(fragment in i for i in kit.settle(bad)[1])
    for expr, figure, expected in cases.gaps:
        assert kit.fill_gap(expr, kit.solve(figure))[0] == expected
