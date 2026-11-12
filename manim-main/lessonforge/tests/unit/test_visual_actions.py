"""The visual-teaching vocabulary, plan and checks (longform/visual_actions.py), and the reaction's coefficient change."""
from lessonforge.longform import figure_math, visual_actions


def test_balance_finds_the_smallest_whole_numbers():
    p = figure_math.parse_equation
    assert figure_math.balance(p("? N2 + ? H2 -> ? NH3")) == {"left": [1, 3], "right": [2]}
    assert figure_math.balance(p("? Fe + ? O2 -> ? Fe2O3")) == {"left": [4, 3], "right": [2]}
    assert figure_math.balance(p("? CH4 + ? O2 -> ? CO2 + ? H2O"), fixed={"right": {0: 2}}) == \
        {"left": [2, 4], "right": [2, 4]}
    assert figure_math.balance(p("? N2 + ? H2 -> ? NH3"), fixed={"right": {0: 3}}) is None


def test_a_balancing_task_gets_a_question_made_by_code_with_a_worked_reason_per_option():
    lesson = {"chapters": [{"beats": [{"id": "09", "figure": {"kind": "reaction", "equation": "? N2 + ? H2 -> ? NH3"}},
                                      {"id": "10", "figure": {"kind": "reaction", "equation": "N2 + 3H2 -> 2NH3"}}]}]}
    assert visual_actions.reaction_questions(lesson, log=lambda *a: None) == 1
    quiz = lesson["chapters"][0]["beats"][0]["quiz"]
    assert quiz["options"][quiz["answer_index"]] == "2" and len(quiz["why"]) == len(quiz["options"])
    assert "N2 + 3H2 -> 2NH3" in quiz["why"][quiz["answer_index"]]
    assert "quiz" not in lesson["chapters"][0]["beats"][1]          # a solved equation asks nothing


def test_the_plan_types_every_action_and_its_checks_find_a_revealed_answer():
    lesson = {"chapters": [{"title": "T", "beats": [
        {"id": "01", "narration": "Count them.", "figure": {"kind": "reaction", "equation": "H2 + O2 -> H2O"},
         "steps": [{"show": "Count", "say": "Count them", "kind": "text"}]},
        {"id": "02", "narration": "Which number balances it?", "thinking_pause_seconds": 4,
         "figure": {"kind": "reaction", "equation": "2H2 + O2 -> 2H2O"},
         "quiz": {"question": "Which number balances it?", "options": ["1", "2"], "answer_index": 1},
         "steps": [{"show": "Which number?", "say": "Which number", "kind": "text"}]}]}]}
    plan = visual_actions.visual_plan(lesson)
    acts = [a["action"] for a in plan["scenes"][1]["actions"]]
    assert "change" in acts and all(a in visual_actions.ACTIONS for s in plan["scenes"] for a in
                                    [x["action"] for x in s["actions"]])
    assert plan["scenes"][0]["first_on_screen"]["verdict"] == "not balanced yet"
    assert any(f["check"] == "answer_before_question" for f in plan["validation"])


def test_a_coefficient_change_moves_only_what_changed():
    from lessonforge.longform import figures
    old = figures.build({"kind": "reaction", "equation": "H2 + O2 -> H2O"})
    new = figures.build({"kind": "reaction", "equation": "H2 + O2 -> 2H2O"})
    steps = new.change_from(old)
    assert len(steps) == 2                                          # molecules first, then the recount
    names = [type(a).__name__ for a in steps[0].animations]
    assert "GrowFromPoint" in names                                 # the new water grows out of the one there
    assert new.change_from(figures.build({"kind": "number_line", "range": [0, 5]})) == []
