"""The questions a lesson asks: what code can tell is wrong with one, what a listener can, and a pass that does at each
stop only the job code chose for it, and keeps a change only when it is better."""
import copy
import json

from lessonforge.harness import questions, service

BRIEF = {"topic": "Why the sky is blue", "audience": "Class 6 students", "language": "hinglish", "goal": "Explain why the sky is blue"}


def sky() -> dict:
    """The owner's own lesson of 2026-10-09, as it asked its questions (narration shortened, questions word for word)."""
    return {"title": "Why the Sky Looks Blue", "brief": dict(BRIEF), "language": "hinglish", "chapters": [
        {"id": 1, "title": "THE MAIN IDEA", "role": "idea", "beats": [
            {"id": "03", "narration": "Ab goal wale sky ko samajhte hain. Sunlight air molecules se takrati hai. "
                                      "Ab socho, blue ya red, kaunsi light zyada scatter hogi?",
             "steps": [{"say": "Ab goal wale", "show": "Sky question", "kind": "point", "highlight": False},
                       {"say": "Ab socho", "show": "Which colour scatters more?", "kind": "key", "highlight": True}],
             "thinking_pause_seconds": 5.0,
             "quiz": {"question": "Which light scatters more?", "options": ["Red light", "Blue light", "Both equally"],
                      "answer_index": 1, "explain": "Blue light has a shorter wavelength."}}]},
        {"id": 2, "title": "YOUR TURN WITH HELP", "role": "practice", "beats": [
            {"id": "04", "narration": "Blue rays zyada sideways bheji jaati hain. Yeh sideways blue light hi observer ki aankhon tak pahunchti hai.",
             "steps": [{"say": "Blue rays", "show": "Blue goes sideways", "kind": "point", "highlight": False}], "thinking_pause_seconds": 0.0},
            {"id": "05", "narration": "Observer ab side mein khada hai. Pehla decision kijiye: sideways ray kaunsi hogi? "
                                      "Dusra, iska reason batayiye: chhoti wavelength zyada scatter hoti hai.",
             "steps": [{"say": "Observer ab", "show": "New observer direction", "kind": "point", "highlight": False},
                       {"say": "iska reason batayiye", "show": "Choose the relation", "kind": "key", "highlight": True}],
             "thinking_pause_seconds": 5.0,
             "quiz": {"question": "What reaches the observer sideways?",
                      "options": ["Red, longer wavelength", "Blue, shorter wavelength", "Both, same scattering"],
                      "answer_index": 1, "explain": "Blue scatters more because its wavelength is shorter."}}]},
        {"id": 3, "title": "A TEMPTING WRONG IDEA", "role": "misconception", "beats": [
            {"id": "06", "narration": "Kuch log sochte hain ki hawa khud blue hoti hai. Clear air colourless hoti hai. "
                                      "Self-check kijiye: kya molecules light ka rang badalte hain?",
             "steps": [{"say": "Clear air", "show": "Air is colourless", "kind": "key", "highlight": True}], "thinking_pause_seconds": 3.0}]},
        {"id": 4, "title": "THREE STEPS TO REMEMBER", "role": "recap", "beats": [
            {"id": "07", "narration": "Isliye sky blue dikhta hai. White sunlight mein saare colours hote hain aur blue sabse zyada bikharti hai. "
                                      "Dusra step kaunsa hai jo scattering ko blue se jodta hai?",
             "steps": [{"say": "Isliye sky", "show": "Sky appears blue", "kind": "key", "highlight": True}],
             "thinking_pause_seconds": 5.0,
             "quiz": {"question": "Which step chooses scattering?",
                      "options": ["Identify colours", "Link wavelength and scattering", "Follow light to observer"],
                      "answer_index": 1, "explain": "The second step selects the scattering relation."}}]}]}


def beats_of(lesson: dict) -> dict:
    return {b["id"]: b for c in lesson["chapters"] for b in c["beats"]}


KEEP_03 = {"beat": "03", "kind": "predict", "options": ["Red light", "Blue light", "Both equally"], "answer_index": 1,
           "why": ["Red has the longer wavelength, so it mostly goes straight on.", "Blue has the shorter wavelength, and shorter scatters more.",
                   "The two colours have different wavelengths, so they do not scatter alike."]}
KEEP_05 = {"beat": "05", "kind": "predict", "options": ["Red ray", "Blue ray", "Both alike"], "answer_index": 1,
           "why": ["Red is scattered least, so it keeps going straight.", "Blue is scattered most, so it is what turns sideways.",
                   "The two are scattered by different amounts."]}
SUNSET = {"beat": "07", "kind": "apply", "new_case": "sunset sky", "replaces": 0,
          "ask": "Ab sunset ke time socho, jab light bahut zyada air se guzarti hai. Tab seedhi aane wali light ka colour kaisa bachega?",
          "question": "At sunset, which colour is left in the direct light?", "options": ["Mostly blue", "Mostly red", "Pure white"],
          "answer_index": 1,
          "why": ["Blue is what gets scattered away on the long path, so little of it arrives.",
                  "Red scatters least, so it is what still comes straight through.",
                  "Some colours are removed along the way, so the light cannot stay white."]}


def cards(prompt, system):
    """What a good question-writer returns for the sky lesson: each stop's own job, and nothing else."""
    return {"questions": [KEEP_03, KEEP_05, SUNSET]}


def hears(told=None, same=None):
    """A listener: ``told`` and ``same`` map a beat to what it finds there (or are called with the beat and the prompt)."""
    def model(prompt, system):
        asked = [line.split()[-1] for line in prompt.splitlines() if line.startswith("QUESTION at beat")]
        if system is questions.AFTER:          # what the voice says when the video goes on: here, it always tells the answer
            nexts = [line.split("NEXT:", 1)[1].strip() for line in prompt.splitlines() if line.strip().startswith("NEXT:")]
            return {"checks": [{"beat": beat, "quote": said, "answered": True} for beat, said in zip(asked, nexts)]}
        assert system is questions.LISTEN
        out = []
        for beat in asked:
            quote = (told(beat, prompt) if callable(told) else (told or {}).get(beat, "")) or ""
            out.append({"beat": beat, "case": "x", "quote": quote, "states": "x" if quote else "", "told": bool(quote),
                        "same": (same or {}).get(beat, "")})
        return {"checks": out}
    return model


def nobody(prompt, system):
    """A listener that finds nothing given away."""
    return hears()(prompt, system)


def test_code_finds_what_was_wrong_with_the_questions_of_a_real_lesson_and_chooses_what_is_done_about_each():
    found = questions.faults(sky())
    by = {}
    for f in found:
        by.setdefault(f["beat"], []).append(f["fault"])
    assert by["03"] == ["same_feedback"]                               # a fair question; one line of feedback for all three
    assert {"not_last", "reason_in_option", "same_feedback"} <= set(by["05"])     # the voice goes on to give the reason
    assert {"about_the_lesson", "long_option", "same_feedback"} <= set(by["07"])  # "Which step …": a question about the video
    # a pause without a card is the writer's own device (the opening question, the try-it task): nobody's business here
    assert "06" not in by and "04" not in by
    # what is done at each stop is code's decision: a fair question keeps its words, a beat that talks on is cut to end
    # on its question, and only a question that cannot stand gets another one
    assert questions.plan(sky()) == {"03": questions.CARD, "05": questions.CUT, "07": questions.NEW}
    assert questions.plan(sky(), told={"05": "Yeh sideways blue light hi observer ki aankhon tak pahunchti hai."})["05"] == questions.NEW
    assert set(questions.plan(sky(), told={"03": "x"}, keep_words=True).values()) == {questions.CARD}     # an author's script


def test_the_right_answer_on_screen_and_an_option_told_by_its_length_are_faults():
    lesson = {"chapters": [{"id": 1, "beats": [{"id": "01", "narration": "Guess. Which one is larger?", "thinking_pause_seconds": 5,
              "steps": [{"show": "One half is larger"}],
              "quiz": {"question": "Which fraction is larger?", "options": ["One third", "One half of the whole roti", "One fourth"],
                       "answer_index": 1, "why": ["Thirds are smaller pieces.", "Two pieces are bigger than three.", "Fourths are smaller still."]}}]}]}
    assert {f["fault"] for f in questions.faults(lesson)} == {"uneven_options", "long_option"}
    lesson["chapters"][0]["beats"][0]["quiz"]["options"][1] = "One half"
    assert {f["fault"] for f in questions.faults(lesson)} == {"on_screen"}       # "One half is larger" stands beside the question
    assert questions.plan(lesson) == {"01": questions.NEW}                       # the screen stays, so the question cannot
    lesson["chapters"][0]["beats"][0]["steps"] = [{"show": "One half or one third?"}]     # the choices, not the answer
    assert questions.faults(lesson) == []


def test_an_option_is_an_answer_of_one_to_three_words_and_numbers_do_not_count():
    assert [questions.answer_words(o) for o in ("Black", "16 cm", "Stays the same", "x = 2 and y = 3", "9.8 m/s", "Blue scatters toward eyes")] == [1, 1, 3, 1, 0, 4]
    # a reason inside an option, and what only looks like one
    assert all(questions.carries_reason(o) for o in ("Blue, shorter wavelength", "Red because it bends least", "Step two: add"))
    assert not any(questions.carries_reason(o) for o in ("1,000 km", "2:3", "(2, 3)", "Half past two", "Sodium chloride"))
    lesson = sky()
    card = lesson["chapters"][0]["beats"][0]["quiz"]
    card.update(options=["Red light", "Blue light scatters much more", "Both equally"], why=["a", "b", "c"])
    assert {"long_option", "uneven_options"} <= {f["fault"] for f in questions.faults(lesson) if f["beat"] == "03"}


def test_each_stop_gets_the_job_code_chose_for_it_and_nothing_else_is_touched():
    lesson = sky()
    first = beats_of(copy.deepcopy(lesson))
    held = beats_of(lesson)                                         # whoever holds a beat still holds it afterwards
    summary = questions.improve(lesson, BRIEF, cards, listener=nobody, log=lambda *_: None)
    beats = beats_of(lesson)
    assert all(beats[k] is held[k] for k in beats)
    assert summary["kept"] == ["03", "05", "07"] and summary["rewritten"] == ["07"] and summary["dropped"] == []
    assert summary["faults_after"] == 0 < summary["faults_before"] and lesson["questions"]["rewritten"] == ["07"]
    # a fair question keeps every word, the voice's and the card's; it gains short answers and a reason for each
    assert beats["03"]["narration"] == first["03"]["narration"] and beats["03"]["steps"] == first["03"]["steps"]
    assert beats["03"]["quiz"]["question"] == "Which light scatters more?" and len(beats["03"]["quiz"]["why"]) == 3
    assert beats["04"] == first["04"]                               # ... and the beat after it still opens as it did
    # a beat that talked on after its question ENDS with it now; nothing before the question changed, the card asks
    # what it asked, and the line that came up on the words that were cut is gone from the screen
    assert beats["05"]["narration"] == "Observer ab side mein khada hai. Pehla decision kijiye: sideways ray kaunsi hogi?"
    assert beats["05"]["quiz"]["question"] == "What reaches the observer sideways?" and beats["05"]["quiz"]["options"] == ["Red ray", "Blue ray", "Both alike"]
    assert [step["show"] for step in beats["05"]["steps"]] == ["New observer direction"]
    # a pause without a card is not touched at all
    assert beats["06"] == first["06"]
    # the question about the lesson itself is another question now: the beat says what it said and ends on the new one
    assert beats["07"]["narration"].startswith("Isliye sky blue dikhta hai. White sunlight mein saare colours hote hain aur blue sabse zyada bikharti hai. Ab sunset")
    assert beats["07"]["narration"].endswith("colour kaisa bachega?") and "Dusra step" not in beats["07"]["narration"]
    assert beats["07"]["quiz"]["kind"] == "apply" and beats["07"]["quiz"]["explain"].startswith("Red scatters least")
    assert [step["show"] for step in beats["07"]["steps"]] == ["Sky appears blue", "At sunset, which colour is left in the direct light?"]
    assert beats["07"]["steps"][-1]["kind"] == "key" and beats["07"]["steps"][-1]["say"] in beats["07"]["narration"]


def test_a_card_written_for_another_question_is_never_put_under_a_question_that_is_kept():
    lesson = sky()
    prompts = []
    moon = {"beat": "03", "kind": "apply", "new_case": "Moon's sky", "ask": "Ab Moon par socho: wahan din mein sky kis colour ka dikhega?",
            "question": "What colour is the sky on the Moon?", "options": ["Black", "Blue", "Red"], "answer_index": 0,
            "why": ["No air, so nothing scatters light.", "Blue needs air to scatter it.", "Red needs a long path through air."]}

    def model(prompt, system):
        prompts.append((prompt, system))
        return {"questions": [KEEP_03 if questions.RETRY in system else moon, KEEP_05, SUNSET], "drop": ["03", "05"]}

    summary = questions.improve(lesson, BRIEF, model, listener=nobody, log=lambda *_: None)
    beats = beats_of(lesson)
    # "Black / Blue / Red" under "Which light scatters more?" would have been a wrong card: it was refused, asked for
    # once more with the reason, and the second answer is the one that stands
    assert summary["kept"] == ["03", "05", "07"] and beats["03"]["quiz"]["options"] == ["Red light", "Blue light", "Both equally"]
    assert "Moon" not in beats["03"]["narration"] and beats["03"]["quiz"]["question"] == "Which light scatters more?"
    again, stands = prompts[1][0].split("WRITE AGAIN")[1].split("ALREADY KEPT")
    assert len(prompts) == 2 and "beat 03 (KEEP THIS QUESTION)" in again and "kept as it is" in again
    assert "beat 05" not in again and "beat 07" not in again        # only what was not kept is asked for again
    # ... and the second try is shown the new question that already stands, so that it does not ask it again
    assert 'beat 07: "At sunset, which colour is left in the direct light?" (right: Mostly red)' in stands and "beat 05" not in stands
    assert summary["dropped"] == []                                 # a model may ask for a stop to go only where it must write another question


def test_a_rewrite_that_is_no_better_stands_aside_and_a_question_that_cannot_stand_goes():
    lesson = sky()
    first = beats_of(copy.deepcopy(lesson))

    def poor(prompt, system):
        return {"questions": [
            {**KEEP_03, "options": ["Red light", "Blue light scatters much more", "Both equally"]},     # a sentence for an option
            {**KEEP_05, "options": ["Red ray", "Blue ray, it scatters most", "Both alike"]},            # a reason inside an option
            {**SUNSET, "question": "Which step did we see second?"},                                    # about the lesson
            {"beat": "06", "question": "Is air blue?", "options": ["Yes", "No"], "answer_index": 1, "why": ["x", "y"]},   # no card there
            {"beat": "99", "question": "?"}, "not a question at all"]}

    summary = questions.improve(lesson, BRIEF, poor, listener=nobody, log=lambda *_: None)
    now = beats_of(lesson)
    assert set(summary["refused"]) == {"03", "05", "07"} and summary["rewritten"] == []
    assert now["03"] == first["03"] and now["04"] == first["04"] and now["06"] == first["06"]      # a fair question stays as written
    # ending a beat on its question needs no model: it is done although the card offered for it was refused
    assert summary["kept"] == ["05"] and now["05"]["narration"].endswith("sideways ray kaunsi hogi?")
    assert now["05"]["quiz"] == first["05"]["quiz"] and "reason" in summary["refused"]["05"]
    # no question is better than a bad one: the stop that asks about the lesson itself got no honest question and goes;
    # not a word of its beat changes
    assert summary["dropped"] == ["07"] and "quiz" not in now["07"] and now["07"]["thinking_pause_seconds"] == 0.0
    assert now["07"]["narration"] == first["07"]["narration"] and now["07"]["steps"] == first["07"]["steps"]
    # a model that fails, or answers something else, changes nothing at all
    again = sky()
    for broken in (lambda p, s: None, lambda p, s: {"lesson": "…"}, lambda p, s: (_ for _ in ()).throw(RuntimeError("down"))):
        assert questions.improve(again, BRIEF, broken, log=lambda *_: None)["kept"] == []
    assert beats_of(again) == first


def test_an_authors_own_script_keeps_every_word_and_gets_only_better_cards():
    lesson = sky()
    words = [b["narration"] for c in lesson["chapters"] for b in c["beats"]]
    seen = []

    def model(prompt, system):
        seen.append((prompt, system))
        return {"questions": [{**KEEP_03, "ask": "Ab socho, kaunsi light zyada scatter hogi?", "question": "Which light do air molecules scatter more?"},
                              KEEP_05, SUNSET], "drop": ["07"]}

    def never(prompt, system):
        raise AssertionError("an author's script is not listened to: its questions stay where they are")

    summary = questions.improve(lesson, BRIEF, model, keep_words=True, listener=never, log=lambda *_: None)
    beats = beats_of(lesson)
    assert len(seen) == 1 and "not a word of narration may change" in seen[0][1]
    assert [b["narration"] for c in lesson["chapters"] for b in c["beats"]] == words
    assert summary["kept"] == ["03"] and summary["dropped"] == [] and summary["rewritten"] == []
    assert len(beats["03"]["quiz"]["why"]) == 3 and beats["03"]["quiz"]["question"] == "Which light scatters more?"    # what is asked is the author's
    # a beat that talks on after its question, and a question about the lesson, cannot be cured without their words:
    # nobody is asked to try, and they stay as their author wrote them
    assert "goes on after the question" in summary["refused"]["05"] and "about the lesson itself" in summary["refused"]["07"]
    assert "NOT YOURS: leave this beat out" in seen[0][0] and "WRITE ANOTHER QUESTION" not in seen[0][0]
    assert beats["07"]["quiz"]["question"] == "Which step chooses scattering?" and "why" not in beats["07"]["quiz"]
    assert beats["05"]["quiz"]["options"][0] == "Red, longer wavelength"
    # ... but a card under which the voice asks nothing goes, in a script too: taking a card away changes no word
    silent = sky()
    beats_of(silent)["05"]["narration"] = "Observer ab side mein khada hai. Sideways blue light aati hai."
    summary = questions.improve(silent, BRIEF, model, keep_words=True, log=lambda *_: None)
    assert summary["dropped"] == ["05"] and "quiz" not in beats_of(silent)["05"]
    assert beats_of(silent)["05"]["narration"] == "Observer ab side mein khada hai. Sideways blue light aati hai."


def test_the_pass_can_be_switched_off_and_asks_nobody_when_the_lesson_has_no_card(monkeypatch):
    calls = []
    model = lambda p, s: calls.append(1) or cards(p, s)            # noqa: E731
    still = {"chapters": [{"id": 1, "beats": [{"id": "01", "narration": "Paani upar kyun uthta hai?", "steps": [], "thinking_pause_seconds": 4.0}]}]}
    assert questions.improve(still, BRIEF, model, log=lambda *_: None)["asked"] == 0 and not calls      # a pause is not a card
    monkeypatch.setenv("HARNESS_QUESTIONS", "0")
    assert questions.improve(sky(), BRIEF, model, log=lambda *_: None)["kept"] == [] and not calls


def test_the_question_writer_is_given_each_stops_job_the_cards_real_mistakes_and_the_rules():
    seen = {}

    def model(prompt, system):
        seen.update(prompt=prompt, system=system)
        return {}

    card = {"mistakes": [{"mistake": "The air itself is blue", "why_it_fails": "clear air has no colour"}],
            "opening_question": {"question": "Why is the sky not violet?", "guesses": ["Violet is weak"], "answer": "Our eyes and the Sun's light"}}
    questions.improve(sky(), {**BRIEF, "misconception": "Air molecules are painted blue"}, model, card=card, listener=nobody, log=lambda *_: None)
    assert "The air itself is blue (it fails because: clear air has no colour)" in seen["prompt"]
    assert "Why is the sky not violet?" in seen["prompt"] and "Air molecules are painted blue" in seen["prompt"]
    jobs = {beat: seen["prompt"].split(f"BEAT {beat} ")[1].split("\nBEAT ")[0] for beat in ("03", "04", "05", "06", "07")}
    assert "YOUR JOB: KEEP THIS QUESTION (" in jobs["03"] and "feedback of their own" in jobs["03"]
    assert "YOUR JOB: KEEP THIS QUESTION, CUT WHAT FOLLOWS IT (the voice goes on after the question" in jobs["05"]
    assert "YOUR JOB: WRITE ANOTHER QUESTION HERE (" in jobs["07"] and "asks about the lesson itself" in jobs["07"]
    assert "(pauses here without a card: not yours to change)" in jobs["06"] and "YOUR JOB" not in jobs["06"] + jobs["04"]
    assert questions.RULES in seen["system"] and "THE BEAT ENDS WITH THE QUESTION" in questions.RULES
    assert "on screen" in questions.RULES and "hide" not in questions.SYSTEM


def test_the_player_tells_each_option_why(tmp_path):
    lesson = sky()
    questions.improve(lesson, BRIEF, cards, listener=nobody, log=lambda *_: None)
    beats = [b for c in lesson["chapters"] for b in c["beats"]]
    chapter_of = {b["id"]: c["id"] for c in lesson["chapters"] for b in c["beats"]}
    timeline = [{"id": b["id"], "chapter": chapter_of[b["id"]], "start": 20.0 * n, "duration": 20.0, "speech_end": 14.0,
                 "sentences": [{"text": b["narration"], "start": 0.5, "duration": 13.0}]} for n, b in enumerate(beats)]
    (tmp_path / "output").mkdir()
    (tmp_path / "timeline.json").write_text(json.dumps(timeline))
    assert service.write_interactions(tmp_path, "job", BRIEF, lesson, 100.0) == 4      # three cards, and the pause that has none
    made = json.loads((tmp_path / "output" / "interactions.json").read_text())["interactions"]
    sunset = made[-1]
    assert sunset["prompt"]["text"] == "At sunset, which colour is left in the direct light?"
    assert [o["feedback"] for o in sunset["options"]] == beats_of(lesson)["07"]["quiz"]["why"]
    assert len({o["feedback"] for o in sunset["options"]}) == 3 and not any(o["feedback"].startswith("Not quite") for o in sunset["options"])


def test_each_question_carries_its_concept_where_to_watch_again_and_the_mistake_a_wrong_option_names(tmp_path):
    lesson = sky()
    questions.improve(lesson, BRIEF, cards, listener=nobody, log=lambda *_: None)
    beats = [b for c in lesson["chapters"] for b in c["beats"]]
    chapter_of = {b["id"]: c["id"] for c in lesson["chapters"] for b in c["beats"]}
    timeline = [{"id": b["id"], "chapter": chapter_of[b["id"]], "start": 20.0 * n, "duration": 20.0, "speech_end": 14.0,
                 "sentences": [{"text": b["narration"], "start": 0.5, "duration": 13.0}]} for n, b in enumerate(beats)]
    (tmp_path / "output").mkdir()
    (tmp_path / "timeline.json").write_text(json.dumps(timeline))
    wrong = next(b["quiz"]["why"][k] for b in beats if (b.get("quiz") or {}).get("why")
                 for k in range(len(b["quiz"]["options"])) if k != b["quiz"]["answer_index"])
    brief = {**BRIEF, "explanations": [
        {"concept_id": "SCI-9-01", "concept": "Scattering of light", "key_idea": "x"},
        {"mistakes": [{"mistake": "Thinks " + wrong, "seen_in": "light"},
                      {"mistake": "Confuses reflection with refraction", "seen_in": "light"}]}]}
    service.write_interactions(tmp_path, "job", brief, lesson, 200.0)
    made = json.loads((tmp_path / "output" / "interactions.json").read_text())["interactions"]
    scored = [q for q in made if q["scored"]]
    assert scored and all(q["concept"] == {"id": "SCI-9-01", "name": "Scattering of light"} for q in made)
    assert all(q["confidence"] for q in scored) and not any(q["confidence"] for q in made if not q["scored"])
    for q in made:
        if q["on_wrong"]:                     # always BACK to where the idea was shown, and never for a prediction
            assert q["on_wrong"]["seek_to"] < q["t"] and q["on_wrong"]["allow_skip"] and q["kind"] != "predict"
            assert any(e["start"] == q["on_wrong"]["seek_to"] for e in timeline)
    assert not any(q["on_wrong"] for q in made if not q["scored"])
    tagged = [o for q in made for o in q["options"] if o.get("misconception")]
    assert tagged and all(not o["correct"] for o in tagged)
    assert {o["misconception"] for o in tagged} <= {m["mistake"] for m in brief["explanations"][1]["mistakes"]}
    # a lesson written without the concept base carries no guesses
    service.write_interactions(tmp_path, "job", BRIEF, lesson, 200.0)
    plain = json.loads((tmp_path / "output" / "interactions.json").read_text())["interactions"]
    assert all(q["concept"] is None for q in plain) and not any(o.get("misconception") for q in plain for o in q["options"])


def test_a_mistake_is_named_only_when_the_words_plainly_say_it():
    listed = ["Believes the larger denominator makes the larger fraction", "Adds the numerators and the denominators"]
    assert service._misconception_of("Two fifths, because the larger denominator makes it larger fraction", listed) == listed[0]
    assert service._misconception_of("Five, the bigger number", listed) is None
    # words that fit two listed mistakes equally well name neither
    assert service._misconception_of("adds numerators and denominators: larger denominator makes", listed) is None
    assert service._misconception_of("anything", []) is None


def test_a_listener_is_given_only_the_last_sentences_and_is_believed_only_for_words_that_were_heard():
    lesson = sky()
    seen = {}

    def model(prompt, system):
        seen.update(prompt=prompt, system=system)
        return {"checks": [
            {"beat": "03", "quote": "", "told": False},
            {"beat": "beat-05", "quote": "Yeh sideways blue light hi observer ki aankhon tak pahunchti", "states": "blue goes sideways", "told": True},
            {"beat": "07", "quote": "The second step ties scattering to blue", "states": "step two", "told": True}]}      # the model's own words

    told = questions.listen(lesson, model, log=lambda *_: None)
    # a finding counts only when its words are in what was heard; the whole sentence they come from is kept
    assert told == {"05": "Yeh sideways blue light hi observer ki aankhon tak pahunchti hai."}
    # the listener is shown the end of the beat before and the beat that asks UP TO its question (what is said after
    # the question is code's to see, and to cut), the card and the right option; and every card, to tell a repeat
    check = seen["prompt"].split("CHECK:")[1]
    assert "Yeh sideways blue light hi observer ki aankhon tak pahunchti hai. Observer ab side mein khada hai." in check
    assert "RIGHT: Blue, shorter wavelength" in check and "chhoti wavelength zyada scatter hoti hai" not in check
    assert "QUESTION at beat 06" not in check                               # a pause without a card is nobody's business
    assert "Sunlight air molecules se takrati hai" not in check.split("QUESTION at beat 05")[1]
    assert "03: Which light scatters more?  (right: Blue light)" in seen["prompt"].split("CHECK:")[0]
    # what the question itself says is never what gives it away, and "told" without a quote that was heard is nothing
    for answer in ([{"beat": "05", "quote": "Pehla decision kijiye: sideways ray kaunsi hogi?", "told": True}],
                   [{"beat": "05", "quote": "Yeh sideways blue light hi observer ki aankhon tak pahunchti hai", "told": False}],
                   [{"beat": "05", "quote": "", "told": True}]):
        assert questions.listen(lesson, lambda p, s, answer=answer: {"checks": answer}, log=lambda *_: None) == {}
    # an answer that cannot be read is "nothing known", not "nothing wrong"; a lesson without a card needs nobody
    assert questions.listen(lesson, lambda p, s: {"lesson": "x"}, log=lambda *_: None) is None
    assert questions.listen(lesson, lambda p, s: [{"beat": "05", "quote": "sideways blue light hi observer ki aankhon tak", "told": "true"}],
                            log=lambda *_: None) == told                   # a bare list, part of the sentence, "true" as a word
    assert questions.listen({"chapters": [{"beats": [{"id": "01", "narration": "Paani upar uthta hai."}]}]}, None) == {}
    assert {f["fault"] for f in questions.faults(lesson, told) if f["beat"] == "05"} >= {"told", "not_last"}


def test_a_question_the_voice_has_already_answered_gets_another_and_a_second_try_stands_on_the_script_as_written():
    lesson = sky()
    first = beats_of(copy.deepcopy(lesson))
    laser = {"beat": "05", "kind": "apply", "new_case": "laser beam", "replaces": 0,
             "ask": "Ab ek laser beam lo: air molecule uski light ke saath kya karta hai?",
             "question": "What does an air molecule do to laser light?", "options": ["Changes direction", "Adds colour", "Blocks it"],
             "answer_index": 0, "why": ["Scattering only redirects light.", "Clear air has no colour to add.", "Most light passes; some is redirected."],
             "confirm": "Laser ki light ka direction badalta hai, rang nahi."}
    moon = {"beat": "05", "kind": "apply", "new_case": "Moon's sky", "replaces": 0,
            "ask": "Moon par hawa nahi hai. Wahan din mein sky ka colour kaisa dikhega?",
            "question": "With no air, what colour is the Moon's daytime sky?", "options": ["Blue", "Black", "White"], "answer_index": 1,
            "why": ["Blue needs air to scatter the light.", "With nothing to scatter light, the sky stays dark.", "White would need every colour scattered."],
            "confirm": "Moon par sky black dikhta hai, kyunki light ko scatter karne ke liye air hi nahi hai."}
    prompts = []

    def writer_model(prompt, system):
        prompts.append((prompt, system))
        return {"questions": [moon], "drop": ["03"]} if questions.RETRY in system else {"questions": [KEEP_03, laser, SUNSET]}

    # as written, the sentence before beat 05's question says what reaches the observer; and the laser question written
    # for it is that same sentence again ("sideways" is what "changes direction" says)
    gives_away = "Yeh sideways blue light hi observer ki aankhon tak pahunchti hai"
    listener = hears(lambda beat, prompt: gives_away if beat == "05" and "Moon" not in prompt.split("CHECK:")[1] else "")
    summary = questions.improve(lesson, BRIEF, writer_model, listener=listener, log=lambda *_: None)
    beats = beats_of(lesson)
    assert summary["told_before"] == 1 and summary["told_after"] == 0 and lesson["questions"]["told_before"] == 1
    assert "YOUR JOB: WRITE ANOTHER QUESTION HERE" in prompts[0][0].split("BEAT 05 ")[1].split("\nBEAT ")[0]
    assert f"the voice has already said the answer: {gives_away}" in prompts[0][0]
    assert summary["kept"] == ["03", "05", "07"] and summary["rewritten"] == ["05", "07"] and summary["unheard"] == []
    assert beats["05"]["quiz"]["question"] == "With no air, what colour is the Moon's daytime sky?"
    # the second try stands on the script as written, not on what the first one left behind
    assert beats["05"]["narration"] == "Observer ab side mein khada hai. Moon par hawa nahi hai. Wahan din mein sky ka colour kaisa dikhega?"
    assert "Laser" not in beats["06"]["narration"]
    # beat 06 opened on its own business, not by confirming beat 05: the sentence that confirms goes in FRONT of it
    assert beats["06"]["narration"] == "Moon par sky black dikhta hai, kyunki light ko scatter karne ke liye air hi nahi hai. " + first["06"]["narration"]
    again, stands = prompts[1][0].split("WRITE AGAIN")[1].split("ALREADY KEPT")
    assert len(prompts) == 2 and "beat 05 (WRITE ANOTHER QUESTION HERE)" in again and gives_away in again
    assert "What does an air molecule do to laser light?" in again and "beat 03" not in again and "beat 07" not in again
    assert "beat 07" in stands and "Mostly red" in stands
    assert beats["03"]["quiz"]["question"] == "Which light scatters more?"       # a "drop" in a second answer is ignored


def test_a_question_that_only_repeats_the_voice_and_cannot_be_cured_is_taken_out():
    lesson = sky()
    first = beats_of(copy.deepcopy(lesson))
    listener = hears(lambda beat, prompt: "Sunlight air molecules se takrati hai" if beat == "03" else "")     # whatever is written for it
    still = {"beat": "03", "kind": "apply", "new_case": "dusty room", "replaces": 0, "ask": "Ab ek dusty room socho: torch ki light kis se takrati hai?",
             "question": "What does torch light hit in a dusty room?", "options": ["Dust", "Nothing", "Glass"], "answer_index": 0,
             "why": ["Dust is in the way.", "The room is not empty.", "There is no glass."]}
    summary = questions.improve(lesson, BRIEF, lambda p, s: {"questions": [still, KEEP_05, SUNSET]}, listener=listener, log=lambda *_: None)
    now = beats_of(lesson)
    assert "03" in summary["dropped"] and "already said its answer" in summary["refused"]["03"]
    assert "quiz" not in now["03"] and now["03"]["thinking_pause_seconds"] == 0.0 and now["03"]["narration"] == first["03"]["narration"]
    assert now["04"] == first["04"] and summary["kept"] == ["05", "07"]


def test_another_question_takes_the_old_ones_place_with_what_set_it_up_and_is_new_in_its_case_and_its_answer():
    lesson = sky()
    beat = beats_of(lesson)["07"]
    beat["narration"] = ("Isliye sky blue dikhta hai. Ab three steps ko yaad kijiye. Pehla step kaunsa tha? "
                         "Dusra step kaunsa hai jo scattering ko blue se jodta hai?")
    beat["steps"].append({"say": "Ab three steps", "show": "Three steps", "kind": "point", "highlight": False})

    def model(candidate):
        return lambda p, s: {"questions": [KEEP_03, KEEP_05, candidate]}

    # the old question, the question asked just before it, and the one sentence said only to set them up all go; the
    # beat is not left with "remember the three steps" hanging in front of a sunset
    summary = questions.improve(lesson, BRIEF, model({**SUNSET, "replaces": 1}), listener=nobody, log=lambda *_: None)
    assert summary["rewritten"] == ["07"]
    assert beat["narration"] == "Isliye sky blue dikhta hai. " + SUNSET["ask"]
    assert [step["show"] for step in beat["steps"]] == ["Sky appears blue", SUNSET["question"]]     # the line for "three steps" went with its sentence
    # closing words that say the beat's last sentence again say it once
    again = sky()
    said = {**SUNSET, "ask": "Isliye sky blue dikhta hai. " + SUNSET["ask"]}
    questions.improve(again, BRIEF, model(said), listener=nobody, log=lambda *_: None)
    assert beats_of(again)["07"]["narration"].count("Isliye sky blue dikhta hai.") == 1
    # a case is new when the script has not spoken of it, and it comes out differently from an earlier answer
    for candidate, why in (({**SUNSET, "new_case": "another observer"}, "already spoken of"),
                           ({**SUNSET, "new_case": ""}, "no new case named"),
                           ({**SUNSET, "options": ["Red", "Blue", "No colour"], "answer_index": 1}, "already had the learner pick"),
                           ({**SUNSET, "options": ["Red light", "The blue light", "No light"], "answer_index": 1}, "already had the learner pick"),
                           ({**SUNSET, "options": ["Red light", "Blue light", "Both equally"], "answer_index": 1, "kind": "recall"}, "already asks"),
                           ({**SUNSET, "ask": "Sunset par light red dikhti hai."}, "do not end with the question")):
        lesson = sky()
        summary = questions.improve(lesson, BRIEF, model(candidate), listener=nobody, log=lambda *_: None)
        assert why in summary["refused"]["07"] and summary["dropped"] == ["07"], (why, summary)
    # ... but "More than blue" is not "Blue light" again: there the small words are the answer
    lesson = sky()
    violet = {**SUNSET, "new_case": "violet light", "ask": "Violet ki wavelength blue se bhi chhoti hai. Toh violet blue se kam scatter hogi ya zyada?",
              "question": "Violet has a shorter wavelength than blue. How is it scattered?", "options": ["Less than blue", "More than blue", "Same as blue"]}
    assert questions.improve(lesson, BRIEF, model(violet), listener=nobody, log=lambda *_: None)["rewritten"] == ["07"]


def test_a_question_that_needs_an_earlier_ones_reasoning_is_asked_for_once_more_and_kept_if_nothing_better_comes():
    planet = {**SUNSET, "new_case": "airless planet", "ask": "Ab ek airless planet socho: wahan din mein sky kaisa dikhega?",
              "question": "What colour is the sky on an airless planet?", "options": ["Black", "Blue", "White"], "answer_index": 0}
    prompts = []

    def model(prompt, system, better=True):
        prompts.append(prompt)
        return {"questions": [SUNSET] if better else []} if questions.RETRY in system else {"questions": [KEEP_03, KEEP_05, planet]}

    lesson = sky()
    summary = questions.improve(lesson, BRIEF, model, listener=hears(same={"07": "05"}), log=lambda *_: None)
    assert "the same step of reasoning as the question at beat 05" in prompts[1].split("WRITE AGAIN")[1]
    assert summary["rewritten"] == ["07"] and beats_of(lesson)["07"]["quiz"]["question"] == SUNSET["question"]
    # being alike is a reason to ask once more, never to lose the question: with nothing better, the first one stands
    lesson = sky()
    summary = questions.improve(lesson, BRIEF, lambda p, s: model(p, s, better=False), listener=hears(same={"07": "05"}), log=lambda *_: None)
    assert summary["rewritten"] == ["07"] and summary["dropped"] == []
    assert beats_of(lesson)["07"]["quiz"]["question"] == "What colour is the sky on an airless planet?"


LEAF = {"title": "How a Green Leaf Makes Food", "brief": {"topic": "Photosynthesis", "language": "hinglish"}, "language": "hinglish", "chapters": [
    {"id": 1, "title": "PLANT PARTS YOU KNOW", "role": "activate", "beats": [
        {"id": "01", "narration": "Ek green leaf ke paas sunlight aur water hain, lekin carbon dioxide nahi aa rahi. Kya woh phir bhi apna food "
                                  "bana sakti hai? Roots plant ko pakadte hain, aur stem leaf tak cheezon ko le jaata hai.",
         "steps": [{"say": "green leaf ke paas", "show": "Green leaf", "kind": "point", "highlight": False}], "thinking_pause_seconds": 4.0}]},
    {"id": 2, "title": "THE MISSING GAS", "role": "explore", "beats": [
        {"id": "03", "narration": "Ek green leaf ka half carbon dioxide nahi paata. Doosre half ko woh gas milti hai. Test ke baad kis half mein "
                                  "starch food dikhega?",
         "steps": [{"say": "green leaf ka half", "show": "Two leaf halves", "kind": "point", "highlight": False}], "thinking_pause_seconds": 5.0,
         "quiz": {"question": "Which half makes starch food?", "options": ["Carbon dioxide half", "No carbon dioxide", "Both halves"],
                  "answer_index": 0, "explain": "Sirf carbon-dioxide-wala half starch food banata hai."}}]},
    {"id": 3, "title": "ALL INPUTS ARRIVE", "role": "name", "beats": [
        {"id": "04", "narration": "Carbon-dioxide-wale half mein starch food banta hai. Leaf glucose tabhi bana sakta hai jab sab inputs aa jaayen. "
                                  "Isi food-making process ko photosynthesis kehte hain.",
         "steps": [{"say": "starch food banta hai", "show": "Starch food appears", "kind": "point", "highlight": False}],
         "thinking_pause_seconds": 4.0}]},
    {"id": 4, "title": "YOUR LEAF CHALLENGE", "role": "practice", "beats": [
        {"id": "06", "narration": "Ab aap khud kijiye. Paper aur pencil lijiye, aur four leaves banaiye.",
         "steps": [{"say": "Paper aur pencil", "show": "Leaves A to D", "kind": "point", "highlight": False}], "thinking_pause_seconds": 3.0}]}]}
REWRITE_04 = ("Leaf glucose tabhi bana sakta hai jab sab inputs aa jaayen, kyunki glucose banane ke liye pani, carbon dioxide aur sunlight, "
              "teeno ka saath hona zaroori hai. Isi food-making process ko photosynthesis kehte hain.")


def test_a_reviewers_rewrite_keeps_the_sentence_that_answers_the_question_before_it():
    """The first lesson made end to end (2026-10-10): beat 04 opened by telling which half makes starch; the reviewer rewrote
    the beat for another finding, the sentence went, and the video asked a question it never answered."""
    from lessonforge.harness import critic
    lesson, said = copy.deepcopy(LEAF), []
    report = {"edits": [{"beat": "04", "narration": REWRITE_04,
                         "steps": [{"say": "Leaf glucose tabhi", "show": "Broad green leaf stays on screen", "kind": "point"},
                                   {"say": "jab sab inputs", "show": "All inputs needed", "kind": "key"}]}]}
    critic.apply_edits(lesson, report, log=said.append)
    beat = beats_of(lesson)["04"]
    assert report["edits_applied"] == ["04"]
    assert beat["narration"].startswith("Carbon-dioxide-wale half mein starch food banta hai. Leaf glucose tabhi")
    assert any("answers the question before it" in line for line in said)
    # ... and a rewrite's note to the animator is not shown to the learner as a line
    assert [step["show"] for step in beat["steps"]] == ["All inputs needed"]
    # a rewrite that still tells the answer is taken as it is, and a beat that follows no question is never touched
    lesson = copy.deepcopy(LEAF)
    kept = "Starch food carbon dioxide wale half mein banta hai, kyunki wahan teeno inputs hain. Isi process ko photosynthesis kehte hain."
    critic.apply_edits(lesson, {"edits": [{"beat": "04", "narration": kept}]}, log=lambda *_: None)
    assert beats_of(lesson)["04"]["narration"] == kept
    lesson = copy.deepcopy(LEAF)
    critic.apply_edits(lesson, {"edits": [{"beat": "06", "narration": "Ab aap khud kijiye. Paper aur pencil lijiye, aur four small leaves banaiye."}]},
                       log=lambda *_: None)
    assert beats_of(lesson)["06"]["narration"].startswith("Ab aap khud kijiye.")


def test_the_reviser_is_told_which_beat_opens_by_answering_a_question():
    from lessonforge.harness import critic
    seen = {}

    def reviser(prompt, system):
        seen["prompt"], seen["system"] = prompt, system
        return {"edits": []}
    critic.revise(copy.deepcopy(LEAF), [{"beat": "04", "severity": "minor", "what": "the reason comes without because"},
                                        {"beat": "06", "severity": "minor", "what": "too long"}], reviser, log=lambda *_: None)
    block_04, block_06 = seen["prompt"].split("[beat 04]")[1].split("[beat 06]")
    assert 'OPENS BY ANSWERING the question the beat before it stops on ("Which half makes starch food?", right answer: "Carbon dioxide half")' in block_04
    assert "OPENS BY ANSWERING" not in block_06
    assert "OPENS BY ANSWERING" in seen["system"]


def test_an_answer_the_voice_never_says_is_said_when_the_video_goes_on():
    lesson = copy.deepcopy(LEAF)
    beats_of(lesson)["04"]["narration"] = REWRITE_04                # as the reviewer left it: the answer is gone
    card = {"beat": "03", "kind": "predict", "options": ["Carbon dioxide half", "No carbon dioxide", "Both halves"], "answer_index": 0,
            "why": ["Only this half has all three inputs.", "This half lacks carbon dioxide.", "The halves do not get the same inputs."],
            "confirm": "Starch sirf us half mein banta hai jise carbon dioxide mili."}
    asked = []

    def listener(prompt, system):
        if system is questions.AFTER:
            asked.append(prompt)
            return {"checks": [{"beat": "03", "quote": "", "answered": False}]}
        return nobody(prompt, system)
    said = []
    summary = questions.improve(lesson, lesson["brief"], lambda p, s: {"questions": [card]}, log=said.append, listener=listener)
    assert summary["confirmed"] == ["03"] and lesson["questions"]["confirmed"] == ["03"]
    assert beats_of(lesson)["04"]["narration"].startswith("Starch sirf us half mein banta hai jise carbon dioxide mili. Leaf glucose tabhi")
    assert "NEXT: Leaf glucose tabhi bana sakta hai" in asked[0] and "RIGHT: Carbon dioxide half" in asked[0]
    assert any("was not said when the video went on" in line for line in said)
    assert beats_of(lesson)["03"]["quiz"]["question"] == "Which half makes starch food?"       # the question itself is untouched
    # with no sentence of the writer's own, the plain one of the lesson's language is used
    lesson = copy.deepcopy(LEAF)
    beats_of(lesson)["04"]["narration"] = REWRITE_04
    questions.improve(lesson, lesson["brief"], lambda p, s: {"questions": [{k: v for k, v in card.items() if k != "confirm"}]},
                      log=lambda *_: None, listener=listener)
    assert beats_of(lesson)["04"]["narration"].startswith("Sahi jawab hai Carbon dioxide half. Leaf glucose tabhi")


def test_nothing_is_added_where_the_voice_already_tells_the_answer_or_nobody_can_say():
    card = {"beat": "03", "kind": "predict", "options": ["Carbon dioxide half", "No carbon dioxide", "Both halves"], "answer_index": 0,
            "why": ["Only this half has all three inputs.", "This half lacks carbon dioxide.", "The halves do not get the same inputs."],
            "confirm": "Starch sirf us half mein banta hai jise carbon dioxide mili."}

    def never(prompt, system):
        assert system is not questions.AFTER, "the option's own words are in the next sentence: nobody needs to be asked"
        return nobody(prompt, system)
    lesson = copy.deepcopy(LEAF)                                    # beat 04 opens "Carbon-dioxide-wale half mein starch food banta hai."
    summary = questions.improve(lesson, lesson["brief"], lambda p, s: {"questions": [card]}, log=lambda *_: None, listener=never)
    assert summary["confirmed"] == [] and beats_of(lesson)["04"]["narration"] == beats_of(LEAF)["04"]["narration"]

    def quotes_what_was_not_said(prompt, system):                   # "answered", with words that are not in NEXT: not believed
        if system is questions.AFTER:
            return {"checks": [{"beat": "03", "quote": "the half with carbon dioxide makes the starch", "answered": True}]}
        return nobody(prompt, system)
    lesson = copy.deepcopy(LEAF)
    beats_of(lesson)["04"]["narration"] = REWRITE_04
    assert questions.improve(lesson, lesson["brief"], lambda p, s: {"questions": [card]}, log=lambda *_: None,
                             listener=quotes_what_was_not_said)["confirmed"] == ["03"]

    def broken(prompt, system):
        if system is questions.AFTER:
            raise RuntimeError("no listener")
        return nobody(prompt, system)
    lesson = copy.deepcopy(LEAF)
    beats_of(lesson)["04"]["narration"] = REWRITE_04
    assert questions.improve(lesson, lesson["brief"], lambda p, s: {"questions": [card]}, log=lambda *_: None, listener=broken)["confirmed"] == []
    assert beats_of(lesson)["04"]["narration"] == REWRITE_04


def test_a_pause_after_a_plain_statement_goes_and_one_after_a_question_a_card_or_an_order_stays():
    lesson, said = copy.deepcopy(LEAF), []
    assert questions.settle_pauses(lesson, log=said.append) == ["01", "04"]
    now = {beat_id: beat["thinking_pause_seconds"] for beat_id, beat in beats_of(lesson).items()}
    assert now == {"01": 0.0, "03": 5.0, "04": 0.0, "06": 3.0}       # 03 has a card; 06 ends on an order: time to do it
    assert {b: beat["narration"] for b, beat in beats_of(lesson).items()} == {b: beat["narration"] for b, beat in beats_of(LEAF).items()}
    assert "2 pause(s)" in said[0]
    assert questions.settle_pauses(lesson, log=said.append) == [] and len(said) == 1


def test_a_step_anchored_out_of_turn_after_a_rewrite_is_placed_by_spread():
    """The lesson made again on 2026-10-10: the first step of a task was anchored on words of the beat's LAST sentence, so
    all three steps came up in its last four seconds."""
    from lessonforge.harness import critic
    narration = ("Paper aur pencil lijiye, four chhote leaf pieces banakar unhe A, B, C, D likhiye: A mein all four inputs, B mein no sunlight, "
                 "C mein no carbon dioxide, D mein no chlorophyll. Pehle predict kijiye. Phir likhiye, leaves B, C aur D food kyon nahi banate?")
    steps = [{"say": "leaves B, C", "show": "Leaves A to D"}, {"say": "C mein no carbon", "show": "C: carbon dioxide missing"},
             {"say": "D mein no chlorophyll", "show": "D: chlorophyll missing"}]
    assert critic.anchors_in_order(steps, narration) == 1
    assert [step["say"] for step in steps] == ["", "C mein no carbon", "D mein no chlorophyll"]
    assert critic.anchors_in_order(steps, narration) == 0            # in order now: nothing more is touched
    # steps already in order, a step with no anchor, and a phrase that is not in the words at all are left alone
    fine = [{"say": "Paper aur pencil", "show": "x"}, {"say": "", "show": "y"}, {"say": "not in it", "show": "z"}, {"say": "Phir likhiye", "show": "w"}]
    assert critic.anchors_in_order(fine, narration) == 0 and [s["say"] for s in fine] == ["Paper aur pencil", "", "not in it", "Phir likhiye"]
    # through a rewrite: the beat's own steps are anchored again on the new words, and the one out of turn is emptied
    lesson = copy.deepcopy(LEAF)
    beat = beats_of(lesson)["06"]
    beat["steps"] = [{"say": "nowhere", "show": "Leaves A to D", "kind": "point", "highlight": False},
                     {"say": "nowhere", "show": "carbon dioxide missing", "kind": "point", "highlight": False}]
    said = []
    report = {"edits": [{"beat": "06", "narration": "C mein carbon dioxide nahi hai. Phir likhiye ki leaves B aur C food kyon nahi banate."}]}
    critic.apply_edits(lesson, report, log=said.append)
    assert report["edits_applied"] == ["06"]
    assert [step["say"] for step in beat["steps"]] == ["", "carbon dioxide nahi"]     # "leaves" is only in the last sentence: out of turn
    assert any("out of turn" in line for line in said)


def test_each_card_is_answered_by_a_model_that_is_not_told_the_marked_option():
    """The card is where a learner is TOLD an answer. A writer marked "20 cm²" right for a 6 by 4 triangle (2026-10-15)."""
    lesson = sky()
    seen = {}

    def teacher(prompt, system):
        seen["prompt"], seen["system"] = prompt, system
        return {"checks": [{"beat": "03", "voice": "which scatters more", "card": "which light scatters more", "same": True, "pick": 2},
                           {"beat": "5", "voice": "the sideways ray", "card": "what reaches the observer", "same": "false", "pick": 1},
                           {"beat": "03", "pick": 3},                                   # a second answer for one card: the first stands
                           {"beat": "99", "pick": 1},                                   # no such card
                           {"beat": "07", "pick": 7}]}                                  # no such option
    got = questions.solve(lesson, teacher, log=lambda *a: None)
    assert got["03"]["pick"] == 1 and got["03"]["same"] is True                         # agrees with the marked option
    assert got["05"]["pick"] == 0 and got["05"]["same"] is False                        # disputes it, and says the card asks another thing
    assert set(got) == {"03", "05"}
    assert "RIGHT" not in seen["prompt"] and "answer_index" not in seen["prompt"]       # the marked option is never shown
    assert "1. Red, longer wavelength" in seen["prompt"] and "THE VOICE ASKS:" in seen["prompt"]
    assert questions.solve(lesson, None) is None                                        # nobody to ask: nothing is known

    def broken(prompt, system):
        raise RuntimeError("down")
    said = []
    assert questions.solve(lesson, broken, log=said.append) is None and "nobody answered" in said[0]
    assert questions.solve({"chapters": [{"beats": [{"id": "1", "narration": "No card."}]}]}, broken) == {}


FOG = {"beat": "05", "kind": "apply", "new_case": "red traffic light", "replaces": 0,
       "ask": "Ab fog mein ek door ki traffic light socho. Kaunsa colour door tak pahunchega?",
       "question": "In fog, which colour of light reaches farther?", "options": ["Red light", "Blue light", "Both alike"], "answer_index": 0,
       "why": ["Red scatters least, so more of it comes straight through the fog.", "Blue scatters most, so it is spread out on the way.",
               "The two colours scatter by different amounts."]}


def test_a_card_that_asks_another_thing_is_asked_again_and_one_still_marked_wrong_is_taken_out():
    """Two faults no rule in code can see, found by a teacher who answers each card without being told the marked option
    (on 284 real cards: a 36 and 72 degree triangle marked "108 degrees", a voice asking whether a box stops under a card
    about a bus passenger)."""
    lesson = sky()
    asked = {"solve": 0}
    prompts = []

    def writer_(prompt, system):
        prompts.append(prompt)
        return {"questions": [dict(KEEP_03, answer_index=1), FOG, SUNSET]}

    def listener(prompt, system):
        if system is questions.SOLVE:
            asked["solve"] += 1
            cards = [line.split()[-1] for line in prompt.splitlines() if line.startswith("CARD at beat")]
            out = []
            for beat in cards:
                if beat == "03":                                  # this teacher picks the first option, both times
                    out.append({"beat": "03", "voice": "which scatters more", "card": "which scatters more", "same": True,
                                "work": "worked out", "pick": 1})
                elif beat == "05" and asked["solve"] == 1:        # the card asks another thing than the voice
                    out.append({"beat": "05", "voice": "which ray goes sideways", "card": "what reaches the observer", "same": False, "pick": 2})
                elif beat == "07" and asked["solve"] == 2:        # the new question's voice and card are about other cases
                    out.append({"beat": "07", "voice": "the colour at noon", "card": "the colour at sunset", "same": False, "pick": 2})
                else:                                             # agrees with what is marked
                    quiz = beats_of(lesson)[beat]["quiz"]
                    out.append({"beat": beat, "voice": "x", "card": "x", "same": True, "pick": quiz["answer_index"] + 1})
            return {"checks": out}
        return nobody(prompt, system)

    said = []
    summary = questions.improve(lesson, BRIEF, writer_, listener=listener, log=said.append)
    beats = beats_of(lesson)
    assert asked["solve"] == 2                                    # before the cards are written, and once they stand
    job_05 = next(line for line in prompts[0].splitlines() if "YOUR JOB" in line and "the voice goes on after the question" in line)
    assert "WRITE ANOTHER QUESTION HERE" in job_05 and "the card asks for what reaches the observer, the voice for which ray goes sideways" in job_05
    assert "the option marked right is not right: worked out" in prompts[0]
    assert "05" in summary["rewritten"] and beats["05"]["quiz"]["question"] == "In fog, which colour of light reaches farther?"
    assert summary["disputed"] == ["03", "07"] and "03" in summary["dropped"] and "03" not in summary["kept"]
    assert "quiz" not in beats["07"] and "07" not in summary["rewritten"]
    assert any("the card asks for the colour at sunset, the voice for the colour at noon: the card is taken out" in line for line in said)
    assert "quiz" not in beats["03"] and beats["03"]["thinking_pause_seconds"] == 0.0
    assert beats["03"]["narration"].endswith("kaunsi light zyada scatter hogi?")       # not a word of the voice changes
    assert lesson["questions"]["disputed"] == ["03", "07"] and any("is still not the one worked out" in line for line in said)


def test_a_card_may_name_only_numbers_the_voice_has_said():
    """On 400 cards, 8 named a number the voice never said; 5 were a case the learner never heard ("a ray 40 degrees from
    the normal" under "will they match again?")."""
    def lesson(card, before="We measure each angle from the normal.", ask="Will they match again?"):
        return {"chapters": [{"id": 1, "beats": [
            {"id": "01", "narration": before, "steps": []},
            {"id": "02", "narration": f"Tilt the ray. {ask}", "steps": [], "thinking_pause_seconds": 5.0,
             "quiz": {"question": card, "options": ["Same", "Larger", "Smaller"], "answer_index": 0,
                      "why": ["They are equal.", "Not larger.", "Not smaller."]}}]}]}
    found = questions.faults(lesson("A ray meets the mirror 40 degrees from the normal. What is the reflected angle?"))
    assert [f["fault"] for f in found] == ["unsaid_number"] and "40" in found[0]["what"]
    # said in this beat or earlier, in words or digits, is said; ordinals and one or two are not a case's numbers
    assert not questions.faults(lesson("At 40 degrees, what is the reflected angle?", before="Now the ray is at forty degrees."))
    assert not questions.faults(lesson("At 1800, which prime comes first?", ask="Ab one thousand eight hundred ko test karo: kaunsa prime pehle?"))
    assert not questions.faults(lesson("What is the 10th term?")) and not questions.faults(lesson("Two S ends meet: pull or push?"))
    # it is a fault no card may have after the pass, so the stop is asked for again in full
    assert "unsaid_number" in questions.HARD and "unsaid_number" in questions.NEEDS_ANOTHER
    assert questions.plan(lesson("A ray 40 degrees from the normal: the reflected angle?")) == {"02": questions.NEW}


def test_a_question_written_here_says_its_own_numbers():
    lesson = sky()
    unsaid = dict(SUNSET, question="At sunset the light crosses 40 km of air. Which colour is left in the direct light?")
    said = dict(SUNSET, ask="Ab sunset ke time socho, jab light forty km air se guzarti hai. Seedhi aane wali light ka colour kaisa bachega?",
                question="At sunset the light crosses 40 km of air. Which colour is left in the direct light?")
    answers = iter([{"questions": [KEEP_03, KEEP_05, unsaid]}, {"questions": [said]}])
    summary = questions.improve(lesson, BRIEF, lambda prompt, system: next(answers), listener=nobody, log=lambda *_: None)
    assert "07" in summary["rewritten"] and "forty kilometres" in beats_of(lesson)["07"]["narration"]       # the second try says it (its "km" said as a word)
    again = sky()
    answers = iter([{"questions": [KEEP_03, KEEP_05, unsaid]}, {"questions": [unsaid]}])
    summary = questions.improve(again, BRIEF, lambda prompt, system: next(answers), listener=nobody, log=lambda *_: None)
    assert "07" not in summary["rewritten"] and "never say" in summary["refused"]["07"]


def test_a_card_nobody_wrote_again_goes_for_asking_another_thing_only_when_both_looks_say_so():
    lesson = sky()
    looks = {"n": 0}

    def listener(prompt, system):
        if system is questions.SOLVE:
            looks["n"] += 1
            cards = [line.split()[-1] for line in prompt.splitlines() if line.startswith("CARD at beat")]
            out = []
            for beat in cards:
                quiz = beats_of(lesson)[beat]["quiz"]
                wavers = beat == "03" and looks["n"] == 2              # the same fair card, judged "another thing" once
                out.append({"beat": beat, "voice": "x", "card": "y", "same": not wavers, "pick": quiz["answer_index"] + 1})
            return {"checks": out}
        return nobody(prompt, system)
    summary = questions.improve(lesson, BRIEF, cards, listener=listener, log=lambda *_: None)
    assert looks["n"] == 2 and summary["disputed"] == [] and "quiz" in beats_of(lesson)["03"]
