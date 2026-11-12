"""How a script sounds: the faults a listener notices are found in named beats, and a rewrite is kept only if it helps.

The first two beats are real: chapter 1 and 2 of the first lesson written from a card with
a diagram (2026-10-09), which the owner called "a bit off, not natural".
"""
import copy

from lessonforge.harness import voice, writer

GLOSSARY = ("Cell ek tiny living building block hai. Bahut se cells milkar animal body banate hain. Food aur oxygen "
            "materials hain, jo living things use karti hain. Waste woh cheez hai jo cell ke work ke baad bahar nikalni hoti hai.")
AS_WRITTEN = ("Ab blank cheek cell ko dhyaan se dekhiye. Sabse chhote picture mein one thin outer edge aur one soft inside "
              "space hai. Isi cheek cell mein one round control part aur two bean-shaped energy parts bhi honge. Toh sochiye, "
              "kya different jobs ke liye different parts chahiye honge, ya ek hi part sab kuch sambhal lega?")
AS_SAID = ("Yeh hamare gaal ki ek cell hai. Bahar ek patli si boundary, aur andar yeh naram, jelly jaisa hissa. Abhi bas itna "
           "hi dikh raha hai. Lekin isi chhoti si cell ko oxygen andar leni hai, waste bahar nikalna hai, aur apne kaam ke "
           "liye energy bhi chahiye. Toh itna sab kaam yeh patli boundary akeli kaise karegi?")
OPENING = ("Sochiye, ek tiny cheek cell ko oxygen andar lena hai aur apne parts ko batana hai kya karna hai. Aapka guess kya "
           "hai: kya ek part yeh sab jobs karega, ya different parts chahiye honge?")


def _lesson(*narrations, language="hinglish", mode=None):
    beats = [{"id": f"{i + 1:02d}", "narration": text, "thinking_pause_seconds": 5.0 if text.endswith("?") else 0.0,
              "steps": [{"say": " ".join(text.split()[:3]), "show": "cheek cell", "kind": "point", "highlight": False}]}
             for i, text in enumerate(narrations)]
    brief = {"language": language, **({"mode": mode} if mode else {})}
    # one beat a chapter, and a last chapter that is the recap
    return {"title": "Animal cell", "brief": brief, "language": "hi-IN",
            "chapters": [{"id": i + 1, "title": f"c{i}", "role": "recap" if i == len(beats) - 1 else "concrete", "beats": [b]}
                         for i, b in enumerate(beats)]}


def _kinds(lesson):
    return {(f["beat"], f["what"].split("(")[0].strip()[7:40]) for f in voice.findings(lesson)}


def test_the_real_beats_are_found_for_what_a_listener_would_notice():
    found = voice.findings(_lesson(OPENING, GLOSSARY, AS_WRITTEN, "Yahi reason hai."))
    said = {f["beat"]: [x["what"] for x in found if x["beat"] == f["beat"]] for f in found}
    assert any("row of statements" in w for w in said["02"])                         # four definitions, nothing joining them
    third = " | ".join(said["03"])
    assert "2 of 4 sentences are orders" in third and "talks about the screen (“picture”)" in third
    assert "English phrase inside a Hindi sentence (“one thin outer edge”)" in third
    assert "asks again what beat 01 already asked" in third
    assert all(f["severity"] == "minor" and f["resolved"] is False and f["fix"] for f in found)   # a heuristic never marks a lesson "needs review"


def test_the_same_beat_said_the_way_a_teacher_says_it_has_nothing_to_find():
    assert voice.findings(_lesson("Chaliye, ek cell ko paas se dekhte hain.", AS_SAID, "Yahi reason hai.")) == []
    line = voice.line(_lesson(OPENING, AS_WRITTEN, "Yahi reason hai."))
    assert "sentences are orders" in line and "1 asked again" in line and "1 screen" in line


def test_an_order_is_told_from_the_words_that_only_look_like_one():
    for order in ("Ab is edge ko dekhiye.", "Four parts label kijiye.", "Zara socho, yeh kyun hua.", "Now look at the top number.",
                  "Observe the two strips."):
        assert voice.is_order(order), order
    for not_one in ("Cell ko energy chahiye.", "Isliye yeh square number hai.", "Chaliye, isi ko eighteen par aazmate hain.",
                    "Iske liye do parts hain.", "The top number tells how many parts are chosen.", "We look at the denominators first."):
        assert not voice.is_order(not_one), not_one


def test_the_learners_own_drawing_and_a_figure_of_speech_are_not_the_screen():
    assert voice.talks_about_the_screen("Ab side by side pictures mein membrane dono mein hai.") == "side by side"
    assert voice.talks_about_the_screen("Is diagram mein nucleus beech mein hai.") == "diagram"
    assert voice.talks_about_the_screen("One oval draw karke apni picture mein four parts label kijiye.") is None
    assert voice.talks_about_the_screen("Let us figure out which part does this.") is None
    assert voice.talks_about_the_screen("Yeh gol sa part nucleus hai.") is None


def test_terms_working_and_unknown_hindi_words_are_never_called_english():
    assert voice.english_phrase("Controls what enters and leaves ko kis part se connect karenge?") == "controls what enters and leaves"
    assert voice.english_phrase("One irregular oval shape banta hai aur yeh cell hai.") == "one irregular oval shape"
    for fine in ("Bahut se cells milkar animal body banate hain.",                    # milkar, banate: Hindi this module does not list
                 "Membrane exchange, cytoplasm activities, nucleus control aur mitochondria energy sambhalte hain.",
                 "Toh three by four plus one by two equals five by four hota hai.",
                 "Yeh selectively permeable cell membrane hai.", "Ek pair bana aur one factor akela reh gaya hai.",
                 "The membrane controls what enters and leaves the cell."):              # an English lesson is not measured for this
        assert voice.english_phrase(fine) is None, fine


def test_the_same_form_about_another_number_is_practice_and_the_recap_may_ask_again():
    assert voice.same_question("Kya ek part yeh sab jobs karega, ya different parts chahiye honge?",
                               "Toh kya different jobs ke liye different parts chahiye honge, ya ek hi part sab sambhal lega?")
    assert not voice.same_question("Kya eighteen ek square number hai, aur uske factors pair bante hain?",
                                   "Kya two thousand eight hundred ek square number hai, aur uske factors pair bante hain?")
    asked_in_the_recap = _lesson(OPENING, "Yahi reason hai, isliye alag parts hain.",
                                 "Toh ab bataiye: kya ek part sab jobs karega, ya different parts chahiye honge?")
    assert not any("asks again" in f["what"] for f in voice.findings(asked_in_the_recap))


def test_a_pasted_script_is_never_measured_or_rewritten():
    script = _lesson(OPENING, AS_WRITTEN, GLOSSARY, mode="script")
    assert voice.findings(script) == [] and voice.report(script) == {} and voice.line(script) == ""
    assert voice.polish(script, lambda prompt, system: 1 / 0)["rewritten"] == []


def test_a_rewrite_is_kept_only_where_the_beat_then_sounds_better():
    lesson = _lesson(OPENING, GLOSSARY, AS_WRITTEN, "Ab isko dekhiye. Phir usko dekhiye. Yahi reason hai.", "Bas, itna hi.")
    before, asked = copy.deepcopy(lesson), []
    joined = ("Hamari body bahut si cells se bani hai, aur har cell ek living building block hai. Isliye use food aur oxygen "
              "jaise materials chahiye, aur kaam ke baad jo waste bachta hai use bahar bhi nikalna hota hai.")

    def llm(prompt, system):
        asked.append((prompt, system))
        return {"edits": [{"beat": "beat-02", "narration": joined},                                  # better: kept
                          {"beat": "03", "narration": AS_SAID.replace("akeli kaise karegi?", "akeli nahi kar sakti.")},  # loses its question
                          {"beat": "04", "narration": "Ab isko dekhiye. Phir usko pehchaniye. Yahi reason hai."},   # no better
                          {"beat": "05", "narration": "This beat was never asked about."}]}

    out = voice.polish(lesson, llm, log=lambda *_: None)
    prompt, system = asked[0]
    assert len(asked) == 1 and system.startswith(voice.POLISH_SYSTEM) and "Point at the thing, never at the screen" in system
    assert "[beat 02]" in prompt and "SHOW: cheek cell" in prompt and "A LISTENER NOTICES" in prompt and "[beat 05]" not in prompt
    assert out["rewritten"] == ["02"] and {r["beat"]: r["why"] for r in out["refused"]} == {
        "03": "it changes whether the beat ends with a question", "04": "it does not sound better by the same measure"}
    beats = {b["id"]: b for c in lesson["chapters"] for b in c["beats"]}
    old = {b["id"]: b for c in before["chapters"] for b in c["beats"]}
    assert beats["02"]["narration"] == joined and beats["02"]["steps"][0]["say"] in joined           # its step is anchored again
    assert all(beats[i] == old[i] for i in ("01", "03", "04", "05"))
    assert out["before"] > out["after"] > 0


def test_a_model_that_fails_or_answers_nonsense_changes_nothing():
    lesson = _lesson(OPENING, AS_WRITTEN, "Yahi reason hai.")
    kept = copy.deepcopy(lesson)
    assert voice.polish(lesson, lambda prompt, system: 1 / 0, log=lambda *_: None)["rewritten"] == [] and lesson == kept
    assert voice.polish(lesson, lambda prompt, system: {"edits": "none"}, log=lambda *_: None)["rewritten"] == [] and lesson == kept
    assert voice.polish(lesson, None)["rewritten"] == []


def test_the_rewrite_rides_with_the_card_unless_the_owner_says_otherwise(monkeypatch):
    monkeypatch.delenv("LESSONFORGE_VOICE_POLISH", raising=False)
    assert voice.enabled({"big_idea": "x"}) and not voice.enabled(None)
    monkeypatch.setenv("LESSONFORGE_VOICE_POLISH", "0")
    assert not voice.enabled({"big_idea": "x"})
    monkeypatch.setenv("LESSONFORGE_VOICE_POLISH", "1")
    assert voice.enabled(None)


def test_the_writer_reads_how_a_teacher_talks_and_the_card_is_not_rebuilt_for_it():
    from lessonforge.harness import skill
    assert "Point at the thing, never at the screen" in skill.for_writer() and "Ask once, and mean it" in skill.for_writer()
    assert "voice.md" not in skill.CARD_PARTS and "How the teacher talks" not in skill.for_card()
    assert "voice" in writer.__dict__                                                   # the writer measures every lesson it writes


# ── a run-on sentence is cut at its clause boundaries (captions of 4 lessons, 2026-10) ────────────────────────

RUN_ON = ("Yaani pull hata do toh brick sand paper par jaldi rukegi, kyunki zyada bumps atakte hain, aur zor se "
          "ragadne par woh aur bhi jaldi ruk jaati hai, lekin smooth glass par woh der tak phisalti rehti hai.")


def test_a_sentence_over_the_limit_is_cut_where_a_clause_starts_and_nothing_else_changes():
    assert len(RUN_ON.split()) > voice.LONG_SENTENCE_WORDS
    out = voice.split_long(RUN_ON)
    pieces = voice.sentences(out)
    assert len(pieces) >= 2 and all(len(p.split()) <= voice.LONG_SENTENCE_WORDS for p in pieces)
    assert all(len(p.split()) >= 5 for p in pieces)
    strip = lambda t: [w.strip(".,;:").lower() for w in t.split()]           # noqa: E731
    assert strip(out) == strip(RUN_ON)                                        # same words, same order
    assert pieces[0].endswith(".") and pieces[1][0].isupper() and pieces[-1].endswith(".")


def test_a_short_sentence_a_list_and_a_sentence_with_no_clause_place_are_left_alone():
    short = "Lekin isi chhoti si cell ko oxygen andar leni hai, waste bahar nikalna hai, aur apne kaam ke liye energy bhi chahiye."
    assert voice.split_long(short) == short
    no_place = " ".join(["word"] * 30) + "."
    assert voice.split_long(no_place) == no_place
    listing = "one, two, three, four, five, six, seven, eight, nine, ten, eleven, twelve, thirteen, fourteen, fifteen, sixteen, seventeen, eighteen, nineteen, twenty, twenty one, twenty two, twenty three."
    assert voice.split_long(listing) == listing                               # a list of commas is not clauses


def test_the_writer_cuts_a_models_run_on_but_not_a_persons_own_words():
    from lessonforge.harness import frameworks
    brief = {"topic": "Friction", "language": "hinglish", "duration_minutes": 3, "framework": "worked_examples"}
    raw = lambda: {"title": "T", "chapters": [{"title": "C", "beats": [{"narration": RUN_ON,    # noqa: E731
                                                                         "steps": [{"say": "Yaani pull hata", "show": "Pull", "kind": "point"},
                                                                                   {"say": "kyunki zyada bumps", "show": "Bumps", "kind": "point"}]}]}]}
    framework = frameworks.get("worked_examples")
    kept = writer.discipline(raw(), brief, framework)["chapters"][0]["beats"][0]
    assert kept["narration"] == RUN_ON                                        # a pasted script is spoken as written
    cut = writer.discipline(raw(), brief, framework, split_long=True)["chapters"][0]["beats"][0]
    assert len(voice.sentences(cut["narration"])) >= 2
    assert cut["steps"][1]["say"] == "kyunki zyada bumps"                      # the anchor is still in the narration


def test_a_reviewers_rewrite_is_cut_too_unless_the_script_is_a_persons_own():
    from lessonforge.harness import critic
    for mode, cut in ((None, True), ("script", False)):
        lesson = _lesson("Yaani pull hata do toh brick jaldi rukegi. Zyada bumps atakte hain. Zor se ragadne par woh aur jaldi ruk "
                         "jaati hai. Smooth glass par woh der tak phisalti rehti hai.", mode=mode)
        critic.apply_edits(lesson, {"edits": [{"beat": "01", "narration": RUN_ON}]}, log=lambda *_: None)
        said = lesson["chapters"][0]["beats"][0]["narration"]
        assert (len(voice.sentences(said)) >= 2) is cut, mode


# ── what a step shows is a label, not a sentence and not a direction to the animator (2026-10-09) ─────────────

def test_a_steps_words_are_kept_short_and_never_cut_inside_a_word():
    from lessonforge.harness import writer
    leaked = ("Say the route, highlight the sea to cloud, cloud to ground and return legs with labels evaporation, "
              "condensation, precipitation")
    assert writer.shown(leaked) == "Say the route"                                   # its first clause, when that is a label
    assert writer.shown("Rain path flows over land, then back to the blue sea") == "Rain path flows over land, then back to the blue sea"
    assert writer.shown("one two three four five six seven eight nine ten eleven twelve thirteen") == "one two three four five six seven eight nine"
    long_words = writer.shown("Supercalifragilisticexpialidocious " * 4)
    assert len(long_words) <= 110 and long_words.split()[-1] == "Supercalifragilisticexpialidocious"   # whole words only
    working = "\\frac{1}{2} + \\frac{1}{3} = \\frac{3}{6} + \\frac{2}{6} = \\frac{5}{6}"
    assert writer.shown(working, "math") == working                                   # a line of working is left as it is
    lesson = {"title": "T", "chapters": [{"title": "C", "beats": [{"narration": "Paani upar jaata hai aur phir neeche aata hai.",
              "steps": [{"say": "Paani upar", "show": leaked, "kind": "point"}]}]}]}
    from lessonforge.harness import frameworks
    brief = {"topic": "Water cycle", "language": "hinglish", "duration_minutes": 2, "framework": "worked_examples"}
    made = writer.discipline(lesson, brief, frameworks.get("worked_examples"))
    assert made["chapters"][0]["beats"][0]["steps"][0]["show"] == "Say the route"


def test_a_line_about_the_screen_is_not_shown_and_a_lessons_own_line_is():
    from lessonforge.harness import frameworks, repairs, writer
    for note in ("Broad green leaf stays on screen", "The arrow fades in", "Leaf remains visible", "Zoom in on the stomata", "Keep the cell on-screen"):
        assert writer.shown(note) == "", note
    for line in ("The coin stays there", "Water stays in the leaf", "Fades with distance", "Keep the denominator"):
        assert writer.shown(line) == line, line
    assert writer.shown("\\text{stays on screen} = 2", "math") != ""              # a line of working is never judged as wording
    steps = [{"say": "Paani upar", "show": "Water rises", "kind": "point"}, {"say": "aur phir", "show": "Leaf stays on screen", "kind": "point"}]
    narration = "Paani upar jaata hai aur phir neeche aata hai."
    lesson = {"title": "T", "chapters": [{"title": "C", "beats": [{"narration": narration, "steps": steps}]}]}
    made = writer.discipline(lesson, {"topic": "Water cycle", "language": "hinglish", "duration_minutes": 3}, frameworks.get("worked_examples"))
    assert [s["show"] for s in made["chapters"][0]["beats"][0]["steps"]] == ["Water rises"]
    assert [s["show"] for s in repairs.clean_steps(steps, narration)] == ["Water rises"]              # a repair's steps are cleaned the same way
