"""The source library, the teaching card and the writer's use of it. No network, no model."""
import json

from lessonforge.harness import card as teaching_card
from lessonforge.harness import library, skill, voice, writer

PACK = {"topic": "Square numbers", "klass": 8, "digest": "d1",
        "sources": [{"id": "S1", "kind": "textbook", "title": "NCERT ch 5", "url": "u", "note": "", "licence": "x", "words": 9}],
        "chunks": [{"id": "S1#1", "source": "S1", "text": "each prime factor occurs twice in the square"},
                   {"id": "S1#2", "source": "S1", "text": "try 36 and 18"}]}


def good_card() -> dict:
    return {"big_idea": {"text": "A number is a square exactly when every prime factor has a partner.", "cites": ["S1#1"]},
            "why_it_matters": {"text": "You can test a large number.", "cites": []},
            "the_why": {"text": "In n times n each prime of n arrives once from each copy, so it comes twice.", "cites": ["S1#1"]},
            "objectives": [{"can": "Decide whether a number is a square from its prime factors", "level": "apply", "checked_by": "q1"},
                           {"can": "Explain why every prime needs a partner", "level": "Understand", "checked_by": "try it"}],
            "picture": {"text": "Factor tiles dealt into two equal trays.", "cites": ["S1#1"]},
            "needs_first": [{"text": "prime numbers", "cites": []}],
            "mistakes": [{"mistake": "Pairing a 2 with a 3.", "why_it_fails": "a pair is two of the same prime", "cites": ["S1#2"]}],
            "opening_question": {"question": "Can 1156 tiles make a perfect square?", "guesses": ["yes"], "answer": "Yes, 34 by 34.", "cites": []},
            "route": [{"move": m, "what": f"do {m}", "cites": []} for m in ("question", "guess", "see", "why", "name", "example")],
            "questions": [{"question": "Is 18 a square?", "options": ["yes", "no"], "answer_index": 1, "explain": "the 2 is alone", "cites": []}],
            "try_it": {"title": "Pair check", "kind": "paper", "materials": ["paper", "pencil"], "stands_for": "each number is a tile",
                       "predict": "Which of 36 and 18 is a square?", "steps": ["Factorise 36.", "Factorise 18."],
                       "observe": "36 pairs up, 18 leaves a 2.", "question": "Why is 18 not a square?",
                       "expected": "Because the 2 has no partner.", "write": "18 is not a square because …",
                       "in_class": "Pairs, five minutes.", "cites": ["S1#2"]},
            "leave_out": ["cubes"], "from_lectures": [], "uncited": []}


def test_search_meets_spellings_and_plurals():
    assert library.tokens("Prime factorisation of squares") == library.tokens("prime factorization of square")
    texts = ["the cat sat on the mat", "prime factors of a square number come in pairs", "area of a circle"]
    scores = library.bm25("square numbers prime factorisation", texts)
    assert scores.index(max(scores)) == 1 and scores[0] == 0


def test_passages_keep_every_word_and_cut_long_blocks():
    text = "\n\n".join(" ".join(f"w{i}_{j}" for j in range(60)) for i in range(5)) + "\n\n" + " ".join("x" for _ in range(700))
    parts = library.passages(text, words=130)
    assert sum(len(p.split()) for p in parts) == 5 * 60 + 700
    assert max(len(p.split()) for p in parts) <= 2 * 130 + 60


def test_a_lesson_plan_is_not_matched_on_filler_words(monkeypatch):
    index = [{"unit": "1", "title": "Describing and Defining Triangles", "goals": "decide whether a given shape is a triangle", "pdf": "p", "url": "u"}]
    monkeypatch.setattr(library, "map_index", lambda log=print: index)
    assert library.find_lesson_plan("Identify whether a given number is a square", log=lambda *_: None) is None


def test_school_class_and_subject_come_from_the_brief():
    brief = {"topic": "Newton's first law of motion", "audience": "Class 9 students"}
    assert library.school_class(brief) == 9 and library.school_subject(brief) == "science"
    assert library.school_class({"audience": "Working professionals"}) is None
    assert library.school_subject({"topic": "Adding fractions", "school_subject": "maths"}) == "maths"


def test_a_good_card_passes_and_made_up_citations_are_removed():
    card = teaching_card.shape(good_card())
    assert teaching_card.check(card, PACK) == []
    card["the_why"]["cites"] = ["S1#1", "S9#9"]
    problems = teaching_card.check(card, PACK)
    assert any("do not exist" in p for p in problems) and card["the_why"]["cites"] == ["S1#1"]


def test_the_task_is_checked_for_what_the_evidence_asks():
    raw = good_card()
    raw["try_it"].update(steps=[f"step {i}" for i in range(7)], materials=["a candle", "a spaceship"], expected="18 is not a square.", stands_for="")
    problems = " | ".join(teaching_card.check(teaching_card.shape(raw), PACK))
    for part in ("7 steps", "candle", "spaceship", "without its reason", "stands_for"):
        assert part in problems, part


def test_a_why_that_restates_the_idea_is_refused():
    raw = good_card()
    raw["the_why"] = {"text": raw["big_idea"]["text"], "cites": ["S1#1"]}
    assert any("restates" in p for p in teaching_card.check(teaching_card.shape(raw), PACK))


def test_one_repair_round_and_the_card_records_what_it_stands_on():
    first = good_card()
    first["try_it"]["expected"] = "18 is not a square."
    answers, prompts, scoped = [first, good_card()], [], []

    def llm(prompt, system):
        if system == teaching_card.SCOPE_SYSTEM:          # the small question about each mistake and question (``scope``)
            scoped.append(prompt)
            return {"items": {}}
        prompts.append((prompt, system))
        return answers[len(prompts) - 1]
    card = teaching_card.make_card({"topic": "Square numbers", "audience": "Class 8"}, PACK, llm, log=lambda *_: None)
    assert len(prompts) == 2 and "FIX THESE" in prompts[1][0] and card["problems"] == []
    assert len(scoped) == 2 and "BIG IDEA:" in scoped[0] and "m1. mistake:" in scoped[0]      # the first card and the repaired one
    assert "[S1#1] each prime factor occurs twice" in prompts[0][0]          # the model reads the numbered passages
    assert "Seven principles" in prompts[0][1] and "try-it-yourself task" in prompts[0][1]   # … and the skill
    assert card["sources"] == [{"id": "S1", "kind": "textbook", "title": "NCERT ch 5", "url": "u", "note": ""}]
    assert "each prime factor occurs twice" not in json.dumps(card)      # no passage text travels with the card
    assert card["skill_version"] == skill.card_version() and card["pack_digest"] == "d1"
    assert skill.card_version() != skill.version()          # the card does not depend on how a beat is written


def test_a_mistake_about_another_idea_of_the_chapter_is_sent_back_once():
    """A small model's card for "why a moving object slows down" left out static against sliding friction and then gave
    it as two of its mistakes and a question (2026-10-12). One small question per item; code acts only on an answer that
    NAMES the other idea, and the card's repair round is told. (A check on the words of 'leave_out' called 14 of the
    library's 18 good cards wrong.)"""
    scoped, card_calls, said = [], [], []

    def llm(prompt, system):
        if system == teaching_card.SCOPE_SYSTEM:
            scoped.append(prompt)
            if len(scoped) == 1:
                return {"items": {"m1": {"about": "another idea", "which": "square roots by long division"},
                                  "q1": {"about": "another idea", "which": ""},              # names nothing: not acted on
                                  "q9": {"about": "another idea", "which": "no such item"}}}
            return {"items": {"m1": {"about": "this idea", "which": ""}}}
        card_calls.append(prompt)
        return good_card()
    card = teaching_card.make_card({"topic": "Square numbers", "audience": "Class 8", "goal": "tell a square number"}, PACK, llm, log=said.append)
    assert len(card_calls) == 2 and len(scoped) == 2 and card["problems"] == []
    assert "mistake 1 is about another idea (square roots by long division)" in card_calls[1] and "question 1 is about" not in card_calls[1]
    assert "GOAL OF THE LESSON: tell a square number" in scoped[0] and any("1 thing(s) to fix" in line for line in said)

    def nobody(prompt, system):
        raise RuntimeError("no model")
    assert teaching_card.scope(teaching_card.shape(good_card()), {"topic": "x"}, nobody, log=lambda *_: None) == []      # no answer, no problem


def test_a_card_is_made_only_when_asked_for(monkeypatch):
    monkeypatch.delenv("LESSONFORGE_TEACHING_CARD", raising=False)
    assert not teaching_card.enabled({"topic": "x"}) and teaching_card.enabled({"card": True})
    monkeypatch.setenv("LESSONFORGE_TEACHING_CARD", "1")
    assert teaching_card.enabled({"topic": "x"}) and not teaching_card.enabled({"card": False})


def _chapter(i):
    return {"title": f"Part {i}", "learning_goal": "g", "beats": [
        {"narration": "Can eleven fifty-six tiles make a perfect square? Take a guess before we look at anything else on the screen today.",
         "visual": "v", "check": "c", "steps": [{"say": "perfect square", "show": "1156 = ?", "kind": "point"}]}]}


def _stub(seen):
    def llm(prompt, system):
        seen.append((prompt, system))
        if "Plan a" in prompt:
            return {"title": "Squares", "thesis": "t", "anchor": "tiles", "anchor_name": "the tiles", "small_case": "36",
                    "method": ["factorise"], "glossary": [], "moves": ["question", "guess"],
                    "chapters": [{"title": f"c{i}", "learning_goal": "g", "enters_with": "a", "leaves_with": f"b{i}"} for i in range(7)]}
        return {**_chapter(len(seen)), "uses_from_before": [], "running_example_step": "not used", "hands_forward": "next",
                "ledger_update": {"established_add": [], "glossary_add": []}}
    return llm


BRIEF = {"topic": "Square numbers", "audience": "Class 8 students", "level": "foundation", "goal": "test a number",
         "style": "tutor", "language": "en-IN", "framework": "concrete_first", "duration_minutes": 6}


def test_without_a_card_the_writer_is_given_exactly_what_it_was_before():
    seen = []
    lesson = writer.write_lesson(BRIEF, _stub(seen), log=lambda *_: None)
    assert all(system == writer.SYSTEM for _, system in seen)
    assert not any("TEACHING CARD" in prompt or "THE CARD ASKS" in prompt for prompt, _ in seen)
    assert "do not use or mention it here" in seen[1][0] and "card" not in lesson


def test_with_a_card_each_chapter_is_told_which_line_it_carries():
    seen, card = [], teaching_card.shape(good_card())
    lesson = writer.write_lesson(BRIEF, _stub(seen), log=lambda *_: None, card=card)
    # The last call is the voice rewrite (the stub says the same question in every chapter, which is a fault to repair).
    polish = [call for call in seen if call[1].startswith(voice.POLISH_SYSTEM)]
    seen = [call for call in seen if call not in polish]
    assert len(polish) == 1 and "asks again what beat" in polish[0][0] and lesson["voice"]["before"] > 0
    plan, chapters = seen[0], seen[1:]
    assert all("HOW TO TEACH" in system and system.startswith(writer.SYSTEM) for _, system in seen)
    assert "How the teacher talks" in seen[0][1]
    assert "THE WHY — the lesson must leave the learner able to say this" in plan[0] and '"moves"' in plan[0]
    assert "OPEN THE LESSON with the card's opening question" in chapters[0][0]
    assert sum("OPEN THE LESSON" in p for p, _ in chapters) == 1
    asked_once = ["ASK ONCE: the lesson's opening question was asked in chapter 1" in p for p, _ in chapters]
    assert not asked_once[0] and not asked_once[-1] and all(asked_once[1:-1])        # not the opening, not the recap
    roles = [s["role"] for s in writer.frameworks.get("concrete_first")["stages"]]
    assert "THIS CHAPTER OWNS THE WHY" in chapters[roles.index("name")][0]
    assert "OPENING QUESTION by name" in chapters[roles.index("model")][0]
    assert "sets the try-it task and does nothing else" in chapters[roles.index("practice")][0]
    assert "Pairing a 2 with a 3" in chapters[3][0]                       # the mistake comes from the card
    recap, practice = chapters[roles.index("recap")][0], chapters[roles.index("practice")][0]
    assert "MEET THE MISTAKE HERE" in recap and sum("MEET THE MISTAKE HERE" in p for p, _ in chapters) == 1
    assert "NEVER says the task's result" in practice and "Why is 18 not a square?" in practice
    assert "uses a DIFFERENT case from the task's" in practice
    assert "THE PICTURE ON SCREEN WHEN THIS CHAPTER STARTS" not in chapters[0][0]      # nothing is drawn before the first
    assert lesson["card"]["try_it"]["title"] == "Pair check" and lesson["moves"] == ["question", "guess"]


def test_every_framework_has_a_stage_for_each_line_of_the_card():
    for framework in writer.frameworks.FRAMEWORKS:
        roles = [s["role"] for s in framework["stages"]]
        for group in (writer.WHY_ROLES, writer.ANSWER_ROLES, writer.TASK_ROLES):
            assert set(roles) & set(group), (framework["id"], group)


def test_the_standard_way_of_drawing_reaches_the_writer():
    raw = good_card()
    raw["picture"]["standard"] = "division ladder"
    card = teaching_card.shape(raw)
    assert card["picture"]["standard"] == "division ladder" and "division ladder" in teaching_card.for_writer(card)
    assert teaching_card.shape(good_card())["picture"]["standard"] == ""


def test_a_second_language_reuses_the_topic_card(tmp_path, monkeypatch):
    monkeypatch.setenv("LESSONFORGE_HOME", str(tmp_path))
    monkeypatch.setattr(library, "build_pack", lambda brief, log=print, refresh=False: dict(PACK))
    calls = []

    def llm(prompt, system):
        if system == teaching_card.SCOPE_SYSTEM:
            return {"items": {}}
        calls.append(1)
        return good_card()
    hinglish = {"topic": "Square numbers", "audience": "Class 8 students", "language": "hinglish"}
    first, _ = teaching_card.prepare(hinglish, llm=llm, log=lambda *_: None)
    second, _ = teaching_card.prepare({**hinglish, "language": "en-IN"}, llm=llm, log=lambda *_: None)
    assert len(calls) == 1 and second == first
    monkeypatch.setattr(skill, "card_version", lambda: "changed")   # new card rules mean a new card
    teaching_card.prepare(hinglish, llm=llm, log=lambda *_: None)
    assert len(calls) == 2


def test_a_script_that_is_not_the_whole_lesson_is_asked_for_again_and_then_written_chapter_by_chapter():
    """A small model returned three of seven chapters (111 words of 343) and stopped; the lesson went to its review as if
    it were whole (2026-10-12, the first lesson on the cheap routing). The owner: "work on the harness, not by taking
    costly models": a script is the whole lesson or it is asked for again, and then written one small job at a time."""
    brief = {**BRIEF, "duration_minutes": 3}
    whole = {"title": "Squares", "thesis": "t", "chapters": [_chapter(i) for i in range(7)]}
    part = {"title": "Squares", "thesis": "t", "chapters": [_chapter(i) for i in range(3)]}
    budget = writer.word_budget(3)
    assert writer.too_little(whole, 7, 30) == "" and writer.too_little(None, 7, budget).startswith("with 0 of 7 chapters")
    assert writer.too_little(part, 7, budget).startswith("with 3 of 7 chapters")
    assert "spoken words where about" in writer.too_little(whole, 7, 100000)            # every chapter there, and far too few words

    answers, asked, said = [part, whole], [], []
    monkey_budget = lambda minutes: 30                                                   # noqa: E731 - the stub's chapters are short
    real, writer.word_budget = writer.word_budget, monkey_budget
    try:
        def llm(prompt, system):
            asked.append(prompt)
            return answers[len(asked) - 1]
        lesson = writer.write_lesson(brief, llm, log=said.append)
        assert len(asked) == 2 and "YOUR FIRST ANSWER came back with 3 of 7 chapters" in asked[1] and len(lesson["chapters"]) == 7
        assert any("asked once more" in line for line in said)
        # still short the second time: chapter by chapter, where every call has one small job
        seen, said = [], []
        short_then_stub = _stub(seen)

        def stubborn(prompt, system):
            if "write exactly" in prompt:
                seen.append((prompt, system))
                return part
            return short_then_stub(prompt, system)
        lesson = writer.write_lesson(brief, stubborn, log=said.append)
        assert len(lesson["chapters"]) == 7 and any("written chapter by chapter instead" in line for line in said)
        assert sum(1 for prompt, _ in seen if "write exactly" in prompt) == 2 and sum(1 for prompt, _ in seen if "Write ONLY chapter" in prompt) == 7
        # ... and when THAT fails too, the short script is the lesson: a fallback improves or stands aside
        said = []

        def only_short(prompt, system):
            if "write exactly" in prompt:
                return part
            raise RuntimeError("no model for the chapters")
        lesson = writer.write_lesson(brief, only_short, log=said.append)
        assert len(lesson["chapters"]) == 3 and any("THE SHORT SCRIPT IS KEPT" in line for line in said)
    finally:
        writer.word_budget = real


def test_a_draft_is_rendered_only_from_inside_the_workspace(tmp_path, monkeypatch):
    monkeypatch.setenv("LESSONFORGE_HOME", str(tmp_path / "ws"))
    seen = []
    lesson = writer.write_lesson(BRIEF, _stub(seen), log=lambda *_: None)
    inside = tmp_path / "ws" / "pilot" / "draft.json"
    inside.parent.mkdir(parents=True)
    inside.write_text(json.dumps(lesson), encoding="utf-8")
    outside = tmp_path / "draft.json"
    outside.write_text(json.dumps(lesson), encoding="utf-8")
    assert writer.load_draft(inside, log=lambda *_: None)["title"] == lesson["title"]
    assert writer.load_draft(outside, log=lambda *_: None) is None
    assert writer.load_draft(tmp_path / "ws" / "missing.json", log=lambda *_: None) is None


def test_a_chapter_is_told_what_the_last_one_left_on_screen():
    seen, card = [], teaching_card.shape(good_card())

    def llm(prompt, system):
        seen.append(prompt)
        if "Plan a" in prompt:
            return _stub([])(prompt, system)
        chapter = _stub([])(prompt, system)
        chapter["beats"][0]["figure"] = {"kind": "scene", "describe": f"Factor tiles in two trays, step {len(seen)}"}
        return chapter
    writer.write_lesson(BRIEF, llm, log=lambda *_: None, card=card)
    assert "It is: Factor tiles in two trays, step 2" in seen[2]          # chapter 2 continues chapter 1's picture
    assert "It is: Factor tiles in two trays, step 3" in seen[3]


# ── from the owner's two prompts (2026-10-09): what a learner can DO, how each source teaches, clean sources ──────

def test_an_objective_needs_a_level_and_a_place_in_the_card_where_the_learner_does_it():
    card = teaching_card.shape(good_card())
    assert [(o["level"], o["checked_by"]) for o in card["objectives"]] == [("apply", "q1"), ("understand", "try_it")]
    assert teaching_card.check(card, PACK) == []
    card["objectives"][0].update(level="deep", checked_by="q4")              # no such level, and the card has one question
    card["objectives"][1]["level"] = "remember"
    problems = " | ".join(teaching_card.check(card, PACK))
    assert "objective 1 has no level" in problems and "objective 1 is checked by nothing in the card" in problems
    assert "(opening, q1, try_it)" in problems
    card["objectives"] = card["objectives"][1:]
    problems = " | ".join(teaching_card.check(card, PACK))
    assert "give two to four 'objectives'" in problems and "every objective is recall" in problems
    told = teaching_card.for_writer(teaching_card.shape(good_card()))
    assert "AFTER THE LESSON THE LEARNER CAN" in told and "[apply; done in question 1]" in told and "done in the try-it task" in told
    assert "After the lesson the learner can" in teaching_card.markdown({**teaching_card.shape(good_card()), "topic": "t", "sources": []})


def test_the_recap_is_told_to_have_the_learner_do_each_objective():
    seen = []
    writer.write_lesson(BRIEF, _stub(seen), log=lambda *_: None, card=teaching_card.shape(good_card()))
    chapters = [prompt for prompt, system in seen[1:] if not system.startswith(voice.POLISH_SYSTEM)]
    assert "THE RECAP has the learner DO each of these" in chapters[-1] and "Explain why every prime needs a partner" in chapters[-1]
    assert not any("THE RECAP has the learner DO" in prompt for prompt in chapters[:-1])


def test_a_sources_text_loses_what_extraction_left_in_it_and_not_one_word_of_its_own():
    dirty = ("Chapter 2.indd   15\t27-06-2025 10:11:12\nActivity 2.2: Let us study a cell\nz\nTake an onion bulb.\n\n\n\n"
             "A right angle is 90Â°. z Cut it. 3 Ã— 4 â‰¥ 12 &amp; x&nbsp;= 2<br>Ï€ r\n17\nReprint 2025-26\n"
             "x, y and z are numbers. café déjà")
    assert library.clean(dirty) == ("Activity 2.2: Let us study a cell\n- Take an onion bulb.\n\nA right angle is 90°. - Cut it. "
                                    "3 × 4 ≥ 12 & x = 2 π r\nx, y and z are numbers. café déjà")
    for untouched in ("Solve for z when x + y + z = 10.", "आज हम cell के बारे में बात करेंगे।", "5 < 7 and 9 > 2", "Tom & Jerry",
                      "The naïve façade"):
        assert library.clean(untouched) == untouched


PLAN = {"audience": "class 8", "prior": ["living things"],
        "objectives": [{"can": "name the parts of a cell", "level": "remember"}, {"can": "judge it", "level": "deep"}],
        "essential_question": "How does one small cell do so many jobs?",
        "flow": [{"phase": "Parts and jobs", "role": "demonstration", "how": "Names each part beside what it does.", "at": ["S1#2", "S9#9"]},
                 {"phase": "Hook", "role": "motivation", "how": "Opens with a journey into the body.", "at": ["S1#1"]},
                 {"phase": "Fun", "role": "entertainment", "how": "A song."},
                 {"phase": "Copied", "role": "assessment", "how": "each prime factor occurs twice in the square try 36 and 18 now", "at": ["S1#2"]}],
        "examples": "comparisons with everyday things", "scaffolding": "body, organ, tissue, cell", "misconceptions": ["a cell is a dot"],
        "leaves_out": ["cell division"], "manner": ["asks the viewer to imagine, then confirms the guess"]}


def test_a_sources_lesson_plan_keeps_its_order_its_closed_lists_and_nothing_copied():
    text = "each prime factor occurs twice in the square try 36 and 18 now and again"
    plan = library.shape_blueprint(PLAN, ["S1#1", "S1#2"], text, kind="lecture")
    assert [(step["role"], step["at"]) for step in plan["flow"]] == [("motivation", ["S1#1"]), ("demonstration", ["S1#2"])]
    assert plan["objectives"] == [{"can": "name the parts of a cell", "level": "remember"}]      # "deep" is not a level
    assert plan["manner"] and library.shape_blueprint(PLAN, ["S1#1", "S1#2"], text, kind="textbook")["manner"] == []
    assert library.shape_blueprint({"flow": [PLAN["flow"][0]]}, ["S1#1"], text) is None           # one phase is not a plan
    assert library.shape_blueprint("no", [], text) is None


def test_plans_are_read_once_per_pack_and_reach_the_card_maker(tmp_path):
    pack = {**PACK, "chunks": [{"id": "S1#1", "source": "S1", "text": " ".join(f"alpha{i}" for i in range(90))},
                               {"id": "S1#2", "source": "S1", "text": " ".join(f"beta{i}" for i in range(90))}]}
    pack["sources"] = [{**PACK["sources"][0], "kind": "lecture", "note": "Hindi lecture"}]
    asked = []

    def reader(prompt, system):
        asked.append((prompt, system))
        return PLAN

    plans = library.blueprints(pack, tmp_path, llm=reader, log=lambda *_: None)
    assert list(plans) == ["S1"] and "PASSAGES IN ORDER" in asked[0][0] and "[S1#2] beta0" in asked[0][0]
    assert asked[0][1] == library.BLUEPRINT_SYSTEM and "You are NOT summarising it" in asked[0][1]
    assert library.blueprints(pack, tmp_path, llm=reader, log=lambda *_: None) == plans and len(asked) == 1     # kept beside the pack
    assert library.blueprints({**pack, "digest": "other"}, tmp_path, llm=lambda p, s: 1 / 0, log=lambda *_: None) == {}   # a failed reading is no plan
    said = library.blueprint_text(plans, pack)
    assert "HOW EACH SOURCE TEACHES IT" in said and "1. [motivation] Hook" in said and "how the teacher talks:" in said
    assert library.roles_missing(plans)["activation"] == 0 and library.roles_missing(plans)["motivation"] == 1
    prompts = []

    def card_model(prompt, system):
        prompts.append((prompt, system))
        return good_card()

    card = teaching_card.make_card(BRIEF, pack, card_model, log=lambda *_: None, plans=plans)
    assert "HOW EACH SOURCE TEACHES IT" in prompts[0][0] and prompts[0][0].index("HOW EACH SOURCE") < prompts[0][0].index("PASSAGES:")
    assert "Lay the\n  flows side by side" in prompts[0][1] or "flows side by side" in prompts[0][1]
    assert card["teacher_talk"] == ["asks the viewer to imagine, then confirms the guess"]
    assert card["source_flows"] == {"S1": ["motivation", "demonstration", "assessment"]}      # nothing of THIS pack was copied
    assert "HOW TEACHERS OF THIS TOPIC TALK" in teaching_card.for_writer(card)
    bare = teaching_card.make_card(BRIEF, pack, card_model, log=lambda *_: None)
    assert "HOW EACH SOURCE TEACHES IT" not in prompts[-1][0] and bare["teacher_talk"] == []


# ── a topic typed wrongly (the owner's own lesson, 2026-10-09: "pythogeroustherom") ───────────────────────────

TYPED = {"topic": "pythogeroustherom", "audience": "for a new lerner for governmet shchool", "goal": "understand the therom with intutuion and real life example",
         "misconception": "you think", "language": "hinglish"}


def test_the_topic_is_read_before_anything_is_searched_and_a_class_is_only_a_hint(tmp_path, monkeypatch):
    monkeypatch.setenv("HARNESS_TOPIC_READ", "1")
    monkeypatch.setattr(library, "root", lambda *parts: tmp_path.joinpath(*parts))
    asked = []

    def model(prompt, system):
        asked.append((prompt, system))
        return {"topic": "Pythagoras theorem", "class": 8}

    said = []
    read = library.read_topic(TYPED, llm=model, log=said.append)
    assert read == {"topic": "Pythagoras theorem", "klass": 8, "asked": "pythogeroustherom"}
    assert "TOPIC AS TYPED: pythogeroustherom" in asked[0][0] and "index would print it" in asked[0][1]
    assert "read as “Pythagoras theorem”, class 8 (not said in the request)" in said[-1]
    assert library.read_topic(TYPED, llm=lambda p, s: 1 / 0, log=said.append)["topic"] == "Pythagoras theorem" and len(asked) == 1
    with_class = library.read_topic({**TYPED, "audience": "Class 10 students"}, llm=model, log=said.append)
    assert with_class["klass"] == 10                                    # what the requester said always wins
    for unusable in ({"topic": "", "class": 99}, "nonsense", {"topic": "x " * 30}):
        other = library.read_topic({"topic": f"squre numbrs {len(str(unusable))}"}, llm=lambda p, s, a=unusable: a, log=said.append)
        assert other["topic"].startswith("squre numbrs") and other["klass"] is None
    assert library.read_topic({"topic": "inertia"}, llm=lambda p, s: 1 / 0, log=said.append)["topic"] == "inertia"   # no answer: as typed
    monkeypatch.setenv("HARNESS_TOPIC_READ", "0")
    assert library.read_topic({"topic": "anythng"}, llm=model)["topic"] == "anythng" and len(asked) == 1      # switched off: nobody is asked


def test_a_source_must_be_about_the_topic_whatever_the_search_returned(monkeypatch):
    assert library.about("in a right angled triangle the theorem of pythagoras says", "Pythagoras theorem")
    assert not library.about("python is a programming language you think of a real life example to understand", "Pythagoras theorem")
    assert library.about("", "Pythagoras theorem", title="Pythagoras Theorem in Hindi | Class 8") and library.about("anything", "")
    assert library.about("the pythagorean theorem relates the sides", "Pythagoras theorem")          # the same word, said another way
    videos = [{"id": "py", "title": "Python in Hindi - Python Kya Hai?", "channel": "TutorialInHindi", "seconds": 600},
              {"id": "mv", "title": "Secret Wars Explained", "channel": "Thragg", "seconds": 700},
              {"id": "ok", "title": "What Is Pythagoras Theorem?", "channel": "Peekaboo Kidz", "seconds": 400}]
    words = {"py": "python is a programming language " * 80, "mv": "doom fears the beyonders in secret wars " * 60,
             "ok": "the pythagoras theorem says that in a right triangle the square on the hypotenuse " * 30}
    monkeypatch.setattr(library, "youtube_search", lambda text, limit=8: videos)
    monkeypatch.setattr(library, "transcript", lambda vid: {"text": words[vid], "language": "en", "generated": True})
    said = []
    chosen = library.find_lectures("Pythagoras theorem", 8, "hinglish", log=said.append, query="Pythagoras theorem understand real life example you think")
    assert [v["id"] for v in chosen] == ["ok"]
    assert any("2 video(s) found by the search were not about “Pythagoras theorem”" in line for line in said)


def test_a_card_lists_the_sources_it_stands_on_and_not_everything_that_was_fetched():
    pack = {**PACK, "topic": "Pythagoras theorem",
            "sources": PACK["sources"] + [{"id": "S2", "kind": "lecture", "title": "Python in Hindi", "url": "u2", "note": "", "licence": "x", "words": 9}]}
    said = []
    card = teaching_card.make_card({**BRIEF, "topic": "pythogeroustherom"}, pack, lambda prompt, system: good_card(), log=said.append)
    assert [s["id"] for s in card["sources"]] == ["S1"] and card["topic"] == "Pythagoras theorem" and card["asked"] == "pythogeroustherom"
    assert any("1 fetched source(s) that no line cites are not listed: Python in Hindi" in line for line in said)
    prompts = []
    teaching_card.make_card({**BRIEF, "topic": "pythogeroustherom"}, pack, lambda prompt, system: prompts.append(prompt) or good_card(), log=lambda *_: None)
    assert "TOPIC: Pythagoras theorem (typed by the requester as “pythogeroustherom”)" in prompts[0]


# ── reference lessons for a pasted script: for its PICTURES, never its words (the owner, 2026-10-09) ──────────

def test_a_pasted_script_gets_what_reference_lessons_show_and_is_asked_about_once(tmp_path, monkeypatch):
    monkeypatch.setenv("HARNESS_SCRIPT_REFERENCES", "1")
    monkeypatch.setattr(library, "root", lambda *parts: (tmp_path.joinpath(*parts).mkdir(parents=True, exist_ok=True) or tmp_path.joinpath(*parts)))
    script = "Bijli ek jagah se doosri jagah kaise jaati hai? " * 30
    searched = []

    def lectures(topic, klass, language="en-IN", count=3, log=print, query=""):
        searched.append((topic, klass, language, count))
        return [{"id": "abc123def45", "title": "Electric current and circuits", "channel": "A Teacher", "seconds": 600, "language": "en",
                 "text": " ".join(f"word{i}" for i in range(400))}]

    monkeypatch.setattr(library, "find_lectures", lectures)
    topic_calls, plan_calls = [], []

    def namer(prompt, system):
        topic_calls.append((prompt, system))
        return {"topic": "Electric current and circuits", "class": 7}

    def reader(prompt, system):
        plan_calls.append(prompt)
        return {**PLAN, "pictures": ["a cell, a switch and a bulb joined in a loop", "the loop opened at the switch: the bulb goes dark"]}

    said = []
    got = library.reference_for_script(script, "hinglish", llm=namer, reader=reader, log=said.append)
    assert got["topic"] == "Electric current and circuits" and got["klass"] == 7 and searched == [("Electric current and circuits", 7, "hinglish", 2)]
    assert "THE SCRIPT OPENS:" in topic_calls[0][0] and "what school topic it teaches" in topic_calls[0][1]
    assert [s["id"] for s in got["sources"]] == ["R1"] and "youtube.com/watch?v=abc123def45" in got["sources"][0]["url"]
    notes = got["notes"]
    assert "Use it to choose and design the PICTURES only" in notes and "shows, in order: a cell, a switch and a bulb joined in a loop" in notes
    assert "word1 word2" not in notes                                   # what the lecturer SAID does not travel, only what is shown
    again = library.reference_for_script(script, "hinglish", llm=lambda p, s: 1 / 0, reader=lambda p, s: 1 / 0, log=said.append)
    assert again == got and len(topic_calls) == 1 and len(plan_calls) == 1          # kept by the script's own text
    assert library.reference_for_script("too short", llm=namer)["notes"] == ""
    monkeypatch.setenv("HARNESS_SCRIPT_REFERENCES", "0")
    assert library.reference_for_script(script + " naya", llm=namer)["notes"] == "" and len(topic_calls) == 1
    monkeypatch.setenv("HARNESS_SCRIPT_REFERENCES", "1")
    unnamed = library.reference_for_script(script + " alag", llm=lambda p, s: {"topic": ""}, log=said.append)
    assert unnamed["notes"] == "" and unnamed["sources"] == []          # no topic named: the screen is designed from the words, as before


def test_a_sources_plan_says_what_it_shows():
    plan = library.shape_blueprint({**PLAN, "pictures": ["a right triangle with squares on its sides", "the two small squares cut and moved"]},
                                   ["S1#1", "S1#2"], "nothing in common here", kind="lecture")
    assert plan["pictures"] == ["a right triangle with squares on its sides", "the two small squares cut and moved"]
    said = library.blueprint_text({"S1": plan}, {"sources": [{"id": "S1", "kind": "lecture", "title": "T"}]})
    assert "shows: a right triangle with squares on its sides; the two small squares cut and moved" in said



def test_a_pause_is_asked_for_at_the_end_of_a_beat_never_after_a_statement():
    # The first end-to-end trial lesson (2026-10-10) paused twice after a STATEMENT: the opening question was "the
    # first two sentences" of a three-sentence beat, and the why was asked and told in one beat.
    import inspect
    notes = inspect.getsource(writer.card_notes)
    assert "the question as that beat's LAST sentence" in notes and "first two sentences" not in notes
    assert "a pause never follows a statement" in notes and "then say it in the next beat" in notes
    # a beat a note adds must not add words: nine beats of 48 words made 428 for "at most 343" (two drafts with seven were on budget)
    assert "taken out of this chapter's share of words" in notes and "a chapter with two beats has the same" in notes
