"""Content harness: intake conversation, script discipline, continuity measurement.

No model, no render: the model is a stub, and what is tested is the code that
stands between a model's answer and a lesson that is safe to render unattended.
"""
import pytest

from lessonforge.harness import frameworks, intake, writer
from lessonforge.longform.contract import Lesson


def run_intake(answers: dict, opening: str | None = None) -> tuple[dict, list[str]]:
    brief, asked = {}, []
    if opening:
        intake.answer(brief, "topic", opening)
    for _ in range(20):
        question = intake.next_question(brief)
        if question is None:
            break
        asked.append(question["id"])
        intake.answer(brief, question["id"], answers.get(question["id"], "skip" if question["optional"] else "x"))
    return brief, asked


def test_one_sentence_answers_several_questions_at_once():
    brief, asked = run_intake(
        {"level": "standard", "goal": "find a missing side", "framework": "worked_examples", "style": "tutor"},
        opening="Why the Pythagorean theorem works for class 8 in Hindi, about 5 minutes")
    assert brief["topic"] == "Why the Pythagorean theorem works"
    assert (brief["grade"], brief["language"], brief["duration_minutes"]) == (8, "hi-IN", 5)
    # nothing it already knew is asked again
    assert not {"topic", "audience", "language", "duration_minutes"} & set(asked)
    # ...but the class number is not what they KNOW: the level is always asked
    assert "level" in asked and brief["level"] == "standard"
    assert intake.next_question(brief) is None


def test_a_whole_subject_is_pushed_back_on():
    brief = {}
    intake.answer(brief, "topic", "Maths")
    # who it is for comes first: which idea to pick inside a subject depends on the learners
    assert intake.next_question(brief)["id"] == "audience"
    intake.answer(brief, "audience", "Class 7 students")
    question = intake.next_question(brief)
    assert question["id"] == "focus" and "whole subject" in question["prompt"]
    intake.answer(brief, "focus", "why a negative times a negative is positive")
    assert brief["topic"] == "why a negative times a negative is positive"
    assert brief["subject"] == "Maths" and intake.next_question(brief)["id"] == "level"


def test_a_chapter_flagged_by_the_interviewer_is_narrowed_and_you_decide_is_never_stored():
    brief = {"topic": "Trigonometric equations", "audience": "Class 9", "needs_focus": True}
    assert intake.next_question(brief)["id"] == "focus"
    intake.answer(brief, "focus", "Finding an angle when sin theta is known")
    assert "needs_focus" not in brief and brief["subject"] == "Trigonometric equations"
    for phrase in ("You decide", "up to you", "anything", "not sure"):
        b2 = {}
        intake.answer(b2, "context", phrase)
        assert b2["context"] == ""


def test_framework_question_recommends_for_the_level():
    brief = {"topic": "Fractions", "audience": "Class 6", "level": "foundation", "goal": "compare two fractions"}
    question = intake.next_question(brief)
    assert question["id"] == "framework"
    assert question["options"][0]["value"] == "concrete_first" and question["options"][0]["label"] == "Start from a picture (suggested)"
    # a requester is choosing a video, not a pedagogy: no option is named after a teaching shape
    assert question["prompt"] == "What kind of video should this be?"
    assert [o["label"] for o in question["options"][1:]] == ["Start from a solved example", "Start from why it is true"]
    assert all("learners" in o["hint"] for o in question["options"])


def test_every_question_says_why_it_is_asked():
    brief, seen = {}, 0
    while (question := intake.next_question(brief)) is not None:
        assert question["why"].strip(), question["id"]
        intake.answer(brief, question["id"], question["options"][0]["value"] if question["options"] else "something")
        seen += 1
    assert seen >= 8


def test_three_frameworks_cover_three_levels():
    assert {f["level"] for f in frameworks.OFFERED} == {"foundation", "standard", "advanced"}
    for framework in frameworks.OFFERED:
        roles = [s["role"] for s in framework["stages"]]
        # Evidence-based shape (docs/research/approaches/04_*): activate prior knowledge
        # early, close with retrieval, and exactly one stage owns the misconception.
        assert "activate" in roles[:2] or roles[0] == "problem"
        assert roles[-1] == "recap" and len(roles) >= 6
        assert frameworks.misconception_stage(framework)["role"] == frameworks.MISCONCEPTION_ROLE[framework["id"]]
        assert "pause" in " ".join(s["job"].lower() for s in framework["stages"])  # prediction/retrieval pauses


BRIEF = {"topic": "Pythagorean theorem", "audience": "Class 8", "level": "standard", "goal": "find a missing side",
         "framework": "worked_examples", "style": "tutor", "language": "en-IN", "duration_minutes": 4,
         "context": "a ladder against a wall"}


def fake_chapter(i: int, opening: str = "") -> dict:
    return {"title": f"Stage {i}", "beats": [{
        "narration": f"{opening} The ladder leans on the wall. Its foot is five metres out. "
                     f"So the ladder forms a right triangle number {i}.",
        "steps": [
            {"say": "Its foot is five", "show": "Foot: 5 m", "kind": "point"},
            {"say": "a phrase the model made up", "show": "right triangle", "kind": "key", "highlight": True},
            {"say": "nowhere at all", "show": "c^2 = a^2 + b^2", "kind": "math", "highlight": True},
            {"say": "", "show": "", "kind": "point"},
        ]}]}


def test_invented_anchors_are_rederived_or_dropped_never_trusted():
    lesson = writer.discipline({"chapters": [fake_chapter(1)], "anchor": "a ladder against a wall"},
                               BRIEF, frameworks.get("worked_examples"))
    steps = lesson["chapters"][0]["beats"][0]["steps"]
    narration = lesson["chapters"][0]["beats"][0]["narration"]
    assert len(steps) == 3                                     # the empty step is gone
    assert steps[0]["say"] == "Its foot is five"               # a real phrase is kept
    assert steps[1]["say"] and writer._norm(steps[1]["say"]) in writer._norm(narration)  # re-derived from 'show'
    assert steps[2]["say"] == ""                               # nothing to anchor to → even spread
    Lesson.model_validate(lesson)


def test_stage_directions_are_stripped_from_what_is_spoken():
    chapter = fake_chapter(1)
    chapter["beats"][0]["narration"] = "[pause] The **ladder** leans on the wall."
    lesson = writer.discipline({"chapters": [chapter]}, BRIEF, frameworks.get("worked_examples"))
    assert lesson["chapters"][0]["beats"][0]["narration"] == "The ladder leans on the wall."


def test_short_lesson_is_one_call_and_long_lesson_carries_a_ledger(monkeypatch):
    calls = []
    # the fake chapters are a sentence each: a budget they fill, so that the script counts as the whole lesson
    # (``writer.too_little``; a real one-call script far short of its budget is asked for again)
    monkeypatch.setattr(writer, "word_budget", lambda minutes: 60)

    def llm(prompt, system):
        calls.append(prompt)
        if "Plan a" in prompt:
            return {"title": "T", "thesis": "t", "anchor": "a ladder against a wall",
                    "chapters": [{"learning_goal": "g", "leaves_with": f"fact {i}"} for i in range(7)]}
        if "Write ONLY chapter" in prompt:
            return fake_chapter(len(calls))
        return {"title": "T", "anchor": "a ladder against a wall", "chapters": [fake_chapter(i) for i in range(7)]}

    # A 3-minute short is one call; anything longer is planned then written per chapter
    # (measured 2026-10-08: one-call scripts came back 35-55% short of the target).
    writer.write_lesson({**BRIEF, "duration_minutes": writer.SINGLE_CALL_MINUTES}, llm, log=lambda *_: None)
    assert len(calls) == 1
    calls.clear()
    lesson = writer.write_lesson({**BRIEF, "duration_minutes": 15}, llm, log=lambda *_: None)
    assert len(calls) == 1 + 7 and len(lesson["chapters"]) == 7
    # chapter 3 is told what chapters 1–2 established and how chapter 2 ended
    assert "fact 0" in calls[3] and "fact 1" in calls[3] and "right triangle number" in calls[3]


def test_continuity_is_measured():
    good = writer.discipline({"anchor": "a ladder against a wall",
                              "chapters": [fake_chapter(i) for i in range(1, 4)]}, BRIEF,
                             frameworks.get("worked_examples"))
    report = writer.continuity(good)
    # The fake chapters are far shorter than a 6-minute target (LENGTH warning) and
    # are near-copies of each other (REPEATED warning); both are expected here. There
    # must be no cold open and no missing running example.
    assert [w for w in report["warnings"] if not (w.startswith("Length") or "repeated" in w)] == []
    assert report["words"] < report["target_words"]
    assert report["cross_chapter_repeats"] >= 1 and report["repeated_phrases"]
    bad = {"anchor": "a ladder against a wall", "chapters": [
        fake_chapter(1), fake_chapter(2, opening="Welcome back! In this video we learn the Pythagorean theorem.")]}
    bad["chapters"][1]["beats"][0]["narration"] = "Welcome back! In this video we look at triangles in general."
    report = writer.continuity(writer.discipline(bad, BRIEF, frameworks.get("worked_examples")))
    assert report["cold_opens"] == [2] and report["chapters_using_running_example"] == 1


def test_outline_without_a_model_is_valid_and_says_what_it_is():
    lesson = writer.outline_lesson(BRIEF)
    assert "placeholder" in lesson["generated_by"]
    assert len(lesson["chapters"]) == len(frameworks.get("worked_examples")["stages"])
    assert all(s["say"] for c in lesson["chapters"] for b in c["beats"] for s in b["steps"])


def test_words_inside_a_formula_are_typeset_as_words():
    assert writer.mathify("Right angle = 90^\\circ") == "\\text{Right angle }= 90^\\circ"
    # a space beside a word is kept inside the text group ("24records, 1update" was on screen in a real lesson)
    assert writer.mathify("24 records, 1 update") == "24\\text{ records}, 1\\text{ update}"
    assert writer.mathify("6 records make 1 update") == "6\\text{ records make }1\\text{ update}"
    assert writer.mathify("h^2 = 10^2 - 6^2") == "h^2 = 10^2 - 6^2"                       # variables untouched
    assert writer.mathify("\\text{Height } h = ?") == "\\text{Height } h = ?"             # already marked up
    assert writer.mathify("sin theta = 3/4") == "\\sin \\theta = 3/4"
    lesson = writer.discipline({"chapters": [{"beats": [{"narration": "A right angle is ninety degrees.", "steps": [
        {"say": "right angle", "show": "Right angle = 90^\\circ", "kind": "point"}]}]}]}, BRIEF,
        frameworks.get("worked_examples"))
    step = lesson["chapters"][0]["beats"][0]["steps"][0]
    assert step["kind"] == "math" and step["show"] == "\\text{Right angle }= 90^\\circ"


def test_a_chapter_is_planned_into_ordered_single_idea_lessons_with_ready_briefs():
    from lessonforge.harness import planner

    def model(prompt, system):
        assert "Trigonometry" in prompt and "ONE idea" in system
        return {"chapter": "Introduction to Trigonometry", "for": "Class 10 students", "lessons": [
            {"title": "Naming the sides of a right triangle", "idea": "Opposite and adjacent depend on the angle.",
             "prerequisites": [], "goal": "Label the three sides for a given angle", "minutes": 4, "level": "foundation",
             "running_example": "a ladder on a wall", "misconception": "opposite is always the vertical side"},
            {"title": "The sine ratio", "idea": "sin theta is opposite by hypotenuse.", "prerequisites": [1, 2, 9, "x"],
             "goal": "Find sin theta from two sides", "minutes": 40, "level": "expert"},
            {"title": "", "idea": "no title: dropped"}, "junk"]}

    plan = planner.plan_chapter("Trigonometry", "Class 10", model, language="hinglish")
    assert [lesson["order"] for lesson in plan["lessons"]] == [1, 2]
    second = plan["lessons"][1]
    assert second["prerequisites"] == [1]                 # only earlier lessons count
    assert second["minutes"] == 8 and second["level"] == "foundation"      # clamped, unknown level replaced
    briefs = planner.to_briefs(plan)
    assert briefs[0]["topic"] == "Naming the sides of a right triangle" and briefs[0]["grade"] == 10
    assert briefs[1]["language"] == "hinglish" and briefs[1]["series"] == {"chapter": "Introduction to Trigonometry", "order": 2, "of": 2}
    assert "Naming the sides" in briefs[1]["notes"]["builds on"] and intake.next_question(dict(briefs[0])) is None
    with pytest.raises(ValueError):
        planner.plan_chapter("X", "", lambda p, s: {"lessons": [{"title": "only one", "idea": "i"}]})


def test_a_formula_step_is_one_line():
    block = "\\begin{aligned}\\mathrm{N_2O_4} &\\rightleftharpoons 2\\,\\mathrm{NO_2}\\\\ \\text{forward rate} &= \\text{reverse rate}\\end{aligned}"
    assert writer.one_line_math(block) == "\\mathrm{N_2O_4} \\rightleftharpoons 2\\,\\mathrm{NO_2}"
    assert writer.one_line_math("a^2 + b^2 = c^2") == "a^2 + b^2 = c^2"


# ── the shortest lesson is three minutes (the owner, 2026-10-09: seven stages do not fit in two) ──────────────

def test_the_shortest_lesson_offered_and_written_is_three_minutes():
    from lessonforge.harness import intake
    assert intake.MIN_MINUTES == 3 and min(d["value"] for d in intake.DURATIONS) == 3
    assert intake.absorb({}, "a 2 min video on fractions")["duration_minutes"] == 3
    assert intake.absorb({}, "an 8 min video on fractions")["duration_minutes"] == 8
    assert intake.answer({"topic": "t"}, "duration_minutes", "2")["duration_minutes"] == 3


def test_a_question_keeps_a_reason_for_each_option_and_nothing_else_unknown():
    quiz = {"question": "Which light scatters more?", "options": ["Blue", "Red", "Both the same"], "answer_index": 0, "explain": "Shorter waves scatter more.",
            "why": ["Yes: blue has the shorter wavelength.", "Red has the longer wavelength, so it scatters less.", "They differ: wavelength decides."],
            "something_else": 1}
    cleaned = writer.clean_quiz(quiz)
    assert cleaned["why"] == quiz["why"] and "something_else" not in cleaned and cleaned["options"] == quiz["options"]
    assert writer.clean_quiz(cleaned) == cleaned                                       # cleaning it again loses nothing
    assert "why" not in writer.clean_quiz({**quiz, "why": quiz["why"][:2]})            # one short: none is kept
    assert "why" not in writer.clean_quiz({**quiz, "why": ["a", "", "c"]})             # one empty: none is kept
    assert "why" not in writer.clean_quiz({k: v for k, v in quiz.items() if k != "why"})



def test_the_writer_is_given_the_same_question_rules_as_the_pass_that_rewrites_questions():
    from lessonforge.harness import questions
    assert writer.QUESTION_RULES == questions.RULES                                   # one text; the two modules cannot import each other both ways
    assert writer._indented(writer.QUESTION_RULES) in writer.SYSTEM
    assert '"why": ["one short sentence for EACH option' in writer.SYSTEM
    assert "the beat that asks has NOT yet said the answer or its reason" in writer.SYSTEM


def test_the_story_framework_stops_only_at_its_question_and_its_check():
    story = frameworks.get("story")
    roles = [s["role"] for s in story["stages"]]
    assert roles == ["hook", "turn", "explain", "check", "payoff"] and story not in frameworks.OFFERED
    assert frameworks.misconception_stage(story)["role"] == "turn"
    from lessonforge.harness import writer
    assert writer.stop_plan(story, 6) == {0, 3} and len(writer.stop_plan(frameworks.get("concrete_first"), 6)) > 2
    assert "Never read the lesson plan aloud" in story["voice"]


def test_a_story_lesson_gets_its_words_in_one_go_and_keeps_them():
    from lessonforge.harness import story_first, scripted
    brief = {"topic": "Newton's first law", "audience": "Class 8 students", "goal": "explain why things stop",
             "framework": "story", "language": "en-IN", "duration_minutes": 3, "style": "tutor"}
    assert story_first.applies(brief) and not story_first.applies({**brief, "language": "hi-IN"})
    assert not story_first.applies({**brief, "framework": "concrete_first"})
    asked = []

    def llm(prompt, system):
        asked.append(prompt)
        return {"title": "Why things stop", "script": " ".join(["Push a book across the table and it stops."] * 12)
                + "\n\nBut friction is what stops it, so with no friction it would keep going."}
    written = story_first.words(brief, llm)
    assert "Never read the lesson plan aloud" in asked[0] and "Newton's first law" in asked[0]
    out = story_first.script_brief(brief, written)
    assert scripted.is_script(out) and scripted.keeps_words(out) and out["story_first"] and out["framework"] == "story"
    assert out["script"] == written["script"] and out["audience"] == "Class 8 students"
    with pytest.raises(ValueError):
        story_first.words(brief, lambda p, s: {"script": "too short"})
