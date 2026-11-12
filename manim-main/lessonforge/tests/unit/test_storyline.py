"""What one bad lesson taught (2026-10-08, "Square Numbers through Prime Factorization").

A tester's report: the same things again and again, no animation, questions inside the
video, an example too complicated to follow. Each test pins one cause found in that
lesson's files. No network, no render.
"""
import importlib.util
from pathlib import Path

import pytest

from lessonforge.harness import critic, frameworks, service, writer

SRC = Path(__file__).resolve().parents[2] / "src" / "lessonforge"
BRIEF = {"topic": "Square numbers", "audience": "Class 8", "grade": 8, "level": "foundation",
         "goal": "decide whether a four-digit number is a square number using prime factorization",
         "framework": "concrete_first", "style": "tutor", "language": "hinglish", "duration_minutes": 6}
BIG = "one thousand seven hundred sixty-four"


def beat(narration, **more):
    return {"narration": narration, "steps": [{"say": " ".join(narration.split()[:3]), "show": "x", "kind": "point"}], **more}


def lesson_of(*chapters, anchor="a square tray of ladoos, 6 rows of 6", language="hinglish"):
    raw = {"anchor": anchor, "chapters": [{"beats": [b if isinstance(b, dict) else beat(b) for b in beats]} for beats in chapters]}
    return writer.discipline(raw, {**BRIEF, "language": language}, frameworks.get("concrete_first"))


# ── no animation ─────────────────────────────────────────────────────────────

def test_the_safety_check_reads_tokens_not_letters():
    """Seven of eight animations were refused because their code said ``ladoos.`` — which contains "os."."""
    spec = importlib.util.spec_from_file_location("code_safety", SRC / "engine" / "code_safety.py")
    safety = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(safety)                                    # by path: importing the engine boots a server
    for fine in ("ladoos.add(dot)", "pos.copy()", "photos.arrange(RIGHT)", "videos.shift(UP)", "kilos.scale(2)",
                 "reopen(box)", "an_input(3)", "evaluate(3)", "socket = Circle()", "# requests per second",
                 "door.open(run_time=1)", "self.doors[0].open()", "ratio.set_value(2)"):
        assert safety.forbidden_reason(fine) is None, fine
    for unsafe in ("os.system('x')", "y = os .getcwd()", "sys.exit()", "open('/etc/passwd')", "f = io.open(p)",
                   "eval('1')", "exec(code)", "__import__('os')", "importlib.import_module('os')", "builtins.open",
                   "getattr(x, 'y')", "subprocess.run(['ls'])", "socket.socket()", "globals()['x']", "__builtins__['open']"):
        assert safety.forbidden_reason(unsafe) is not None, unsafe
    assert safety.forbidden_reason("fig.savefig('a.png')", ("savefig",)) and not safety.forbidden_reason("resavefigs = 1", ("savefig",))


def test_a_crowd_is_asked_for_small_and_a_measurement_is_left_alone():
    crowd = "One thousand seven hundred sixty-four ladoos move from a loose pile into a square box."
    assert service.scene_brief(crowd) == crowd + service.SCENE_PAIRS + service.SCENE_LIMITS
    assert service.scene_brief("A box fills as 42 rows of 42 ladoos appear, ending with 1764 ladoos.").endswith(service.SCENE_LIMITS)
    for fine in ("A flask holding 12 brown molecules and 6 colourless ones.", "A ball rolls down a 30 degree ramp.",
                 "Three sensors poll every 3, 5 and 7 minutes and meet at 105 minutes.", "A wire at 100 degrees Celsius cools."):
        assert service.scene_brief(fine) == fine + service.SCENE_PAIRS, fine


def test_a_failed_scene_gets_one_simpler_try_and_the_reason_is_kept():
    crowd, plain, hopeless = "A tray fills with 1764 ladoos.", "A ball rolls down a ramp.", "Something impossible moves."
    lesson = lesson_of([beat("Dekhiye yeh tray.", figure={"kind": "scene", "describe": crowd}),
                        beat("Ab ball ko dekhiye.", figure={"kind": "scene", "describe": plain}),
                        beat("Aur yeh bhi dekhiye.", figure={"kind": "scene", "describe": hopeless})])
    calls = []
    P, L = service.SCENE_PAIRS, service.SCENE_LIMITS

    def generate(brief):
        calls.append(brief)
        # the plain scene fails as written and works once the limits are spelled out
        return "/cache/ok.py" if brief in (crowd + P + L, plain + P + L) else None

    report = service.resolve_scenes(lesson, log=lambda *_: None, generate=generate,
                                    why=lambda brief: "nothing moved" if "impossible" in brief else "left its box")
    assert crowd + P not in calls and calls.count(crowd + P + L) == 1                  # asked for small from the start
    assert calls.count(plain + P) == 1 and calls.count(plain + P + L) == 1              # second try, simpler
    assert calls.count(hopeless + P) == 1 and calls.count(hopeless + P + L) == 1 and len(calls) == 5
    assert (report["asked"], report["made"], report["retried"], report["simplified"]) == (3, 2, 2, 1)
    assert report["failed"] == [hopeless] and report["reasons"] == {hopeless: "nothing moved"}
    beats = lesson["chapters"][0]["beats"]
    assert beats[0]["figure"]["module"] and beats[1]["figure"]["module"] and "figure" not in beats[2]


# ── the same things again and again ──────────────────────────────────────────

def test_the_example_is_described_in_one_chapter_and_every_chapter_reads_the_script_so_far():
    prompts = []

    def llm(prompt, system):
        prompts.append(prompt)
        if "Plan a" in prompt:
            return {"title": "T", "thesis": "t", "anchor": "a square tray of ladoos, 6 rows of 6", "anchor_name": "the tray",
                    "small_case": "9 ladoos in 3 rows of 3", "method": ["divide by the smallest prime", "pair equal factors"],
                    "chapters": [{"learning_goal": "g", "leaves_with": f"fact {i}"} for i in range(7)]}
        n = len(prompts) - 1
        return {"beats": [beat(f"Chapter {n} ki apni baat number {n} yahan kahi ja rahi hai aur kuch nahin.")],
                "hands_forward": f"handed {n}"}

    lesson = writer.write_lesson(BRIEF, llm, log=lambda *_: None)
    chapters = prompts[1:]
    assert len(chapters) == 7 and writer.example_stage(frameworks.get("concrete_first")) == 1
    assert "comes in a later chapter" in chapters[0] and "the tray" not in chapters[0]
    assert "describe it HERE, this once" in chapters[1] and "9 ladoos in 3 rows of 3" in chapters[1]
    for later in chapters[2:]:
        assert "Do NOT describe it or its setting" in later and "“the tray”" in later
    # no chapter writes blind: it is handed every word already spoken, and told to repeat none of it
    assert "THE SCRIPT SO FAR" not in chapters[0]
    assert "[chapter 1] Chapter 1 ki apni baat" in chapters[1] and "[chapter 5] Chapter 5 ki apni baat" in chapters[6]
    assert all("pair equal factors" in c and "at most" in c and "restating is the usual way" in c for c in chapters)
    assert "use it, with the same numbers" not in "".join(prompts)          # the line that made every chapter retell it
    assert (lesson["anchor_name"], lesson["small_case"], lesson["method"][1]) == ("the tray", "9 ladoos in 3 rows of 3", "pair equal factors")
    # the standing rules say the same thing the ledger enforces
    for rule in ("THE EXAMPLE SERVES THE IDEA", "no festival, shop, owner, match", "SMALLEST case", "SAY A THING ONCE",
                 "TEACH THE METHOD THE GOAL NEEDS", "one\n  case that passes AND one that fails", "at most about 40 objects"):
        assert rule in writer.SYSTEM, rule
    # every framework names exactly one stage that introduces the example
    assert [writer.example_stage(f) for f in frameworks.FRAMEWORKS] == [1, 0, 0, 0]


def test_the_length_asked_for_is_the_length_budgeted():
    # 125 words a minute as measured, minus five seconds a minute of thinking time
    assert (writer.word_budget(6), writer.word_budget(2), writer.word_budget(15)) == (687, 229, 1718)
    long = lesson_of(*[[" ".join(["shabd"] * 70) + f" {i}"] * 2 for i in range(7)])
    report = writer.continuity(long)
    assert report["target_words"] == 687 and report["words"] > 687 * 1.15
    assert any(w.startswith("Length") and "not 6" in w for w in report["warnings"])
    # the pressure that made every chapter retell the story is gone
    assert not any("running example appears" in w for w in report["warnings"])


def test_repetition_is_a_finding_that_gets_rewritten_not_a_warning_nobody_reads():
    scene = f"Diwali mela ke stall par {BIG} ladoos rakhe hain aur owner unhe box mein rakhna chahta hai."
    lesson = lesson_of(
        [scene + " Hum unhe ginte hain."],
        ["Ab hum factors nikalte hain dhyaan se. Yeh pehla step hai is kaam ka."],
        [scene + " Ab dekhte hain kya hota hai aage."],                               # the scene, set again
        [f"Yahan {BIG} ko todte hain. Phir se {BIG} ko dekhiye. Aur {BIG} hi answer hai."],
        ["Bilkul alag baat yahan kahi ja rahi hai jo pehle kabhi nahin aayi thi."],
        ["Ek aur nayi cheez jo kisi chapter mein pehle nahin thi bilkul bhi."],
        ["Hum unhe ginte hain kya aapko yaad hai woh pehla tareeka sahi se."],        # recap: one echo is allowed
        anchor="At a Diwali mela a stall packs ladoos into a box")
    found = critic.repetition_gate(lesson)
    by_beat = {f["beat"]: f for f in found}
    assert set(by_beat) == {"03", "04"} and all(f["severity"] == "major" for f in found)
    assert "chapter 1 already said" in by_beat["03"]["what"] and "Diwali mela ke stall par" in by_beat["03"]["what"]
    assert "spoken in full 5 times" in by_beat["04"]["what"] and "yeh number" in by_beat["04"]["fix"]
    report = writer.continuity(lesson)
    assert report["long_number_mentions"] == {"one thousand seven hundred sixty four": 5}
    assert report["chapters_describing_example"] == [1, 3]
    assert any("described again in chapter(s) [3]" in w for w in report["warnings"])

    # …and the revision round is asked to cut it, and does
    asked = []

    def reviewer(prompt, system):
        if system is critic.REVISE_SYSTEM:
            asked.append(prompt)
            return {"edits": [{"beat": "01", "narration": f"Ek tray par {BIG} ladoos rakhe hain aur unhe ek box mein rakhna hai. Hum unhe ginte hain."},
                              {"beat": "03", "narration": "Tray par wapas aate hain aur dekhte hain kya hota hai aage."},
                              {"beat": "04", "narration": "Yahan is number ko todte hain. Phir se yeh number dekhiye. Aur yeh number hi answer hai."}]}
        return {"scores": {k: 3 for k in critic.RUBRIC}, "findings": [], "claims": [], "edits": [], "summary": "ok"}

    # the same lesson is set at a Diwali mela, which the owner's bar keeps out of an example: that is a finding too
    assert [f["beat"] for f in critic.setting_gate(lesson)] == ["01", "03"] and "diwali, mela" in critic.setting_gate(lesson)[0]["what"]
    assert critic.setting_gate(lesson_of(["A cricket in the grass chirps at night."], ["The wicketkeeper is not here; a stadiums list neither."])) != [] \
        and critic.setting_gate(lesson_of(["Take a plain room and a dot on a page."], ["A ticket, a melody, a holiday."])) == []
    verification = critic.verify(lesson, reviewer, log=lambda *_: None)
    assert len(asked) == 1 and "repetition:" in asked[0] and "example: a story setting" in asked[0] and "CUT the repeated words" in critic.REVISE_SYSTEM
    assert sorted(verification["beats_rewritten"]) == ["01", "03", "04"] and critic.repetition_gate(lesson) == [] and critic.setting_gate(lesson) == []
    assert verification["status"] == "passed"


def test_a_script_over_its_length_is_cut_back_and_a_rewrite_may_not_lengthen_it():
    """Every lesson measured ran over its budget and each rewrite made it longer (350 words as written, 391 after its
    review, for "at most 343"; 31 of 45 lessons over by more than 3%, the worst at 164%). "At most" in a prompt is advice."""
    long = "Yeh ek lamba vaakya hai jo baar baar wahi baat kehta hai aur lesson ko bahut lamba bana deta hai bina kisi wajah ke yahan. " * 3
    short = "Yeh chhota vaakya hai jo ek hi baat kehta hai."
    lesson = lesson_of([long], [short], [long], [short], [short], [short], [short])
    lesson["brief"] = {**(lesson.get("brief") or {}), "duration_minutes": 3, "language": "hinglish"}
    budget = critic._budget(lesson)
    padding = max(0, budget - sum(len(b["narration"].split()) for c in lesson["chapters"] for b in c["beats"]) + 60)
    lesson["chapters"][1]["beats"][0]["narration"] = short + " " + " ".join(["aur"] * padding)       # now 60 words over
    total = sum(len(b["narration"].split()) for c in lesson["chapters"] for b in c["beats"])
    found = critic.length_gate(lesson)
    assert total > budget * 1.03 and found and all(f["what"].startswith("length:") and f["at_most"] >= 22 for f in found)
    assert sum(len(next(b for c in lesson["chapters"] for b in c["beats"] if b["id"] == f["beat"])["narration"].split()) - f["at_most"] for f in found) >= total - round(budget * 1.03)
    assert critic.length_gate({**lesson, "brief": {"mode": "script", "duration_minutes": 3}}) == []        # a pasted script is as long as it is
    # the reviser is told each beat's limit, and a rewrite that comes back no shorter is refused
    asked = []

    def reviser(prompt, system):
        asked.append(prompt)
        return {"edits": [{"beat": found[0]["beat"], "narration": lesson_text(found[0]["beat"]) + " aur ek baat aur."}]}
    lesson_text = lambda bid: next(b for c in lesson["chapters"] for b in c["beats"] if b["id"] == bid)["narration"]      # noqa: E731
    before, said = lesson_text(found[0]["beat"]), []
    edits = critic.revise(lesson, found, reviser, log=lambda *_: None)
    assert f"at most {found[0]['at_most']}" in asked[0] and edits[0]["at_most"] == found[0]["at_most"]
    critic.apply_edits(lesson, {"edits": edits}, log=said.append)
    assert lesson_text(found[0]["beat"]) == before and any("were asked" in line for line in said)
    # ... and a script already at its length gives a rewrite no room to grow, whatever the finding
    other = [{"severity": "major", "beat": "02", "resolved": False, "what": "clarity: say it plainly"}]
    critic.revise(lesson, other, reviser, log=lambda *_: None)
    words = len(lesson_text("02").split())
    assert f"{words} words now, at most {words + 2}" in asked[-1]


def test_a_number_alone_or_a_single_echo_in_the_recap_is_not_a_repetition():
    lesson = lesson_of(["Pehle hum one two three four five six ginte hain aaram se."],
                       ["Phir se one two three four five six bolte hain hum sab."],
                       anchor="counting")
    assert critic.repetition_gate(lesson) == []


# ── Hindi conversation, English terms ────────────────────────────────────────

def test_a_beat_spoken_entirely_in_english_is_a_major_finding_in_a_hinglish_lesson():
    english = ("That forty-two by forty-two packing pattern gives our number a name. In the gift box drawing, there are "
               "forty-two ladoos in each row. So the same whole number multiplies by itself.")
    hinglish = "Ab hum forty-two ko prime factors mein todte hain. Dekhiye, two into three into seven aata hai."
    assert len(critic.english_only_sentences(english)) == 3 and critic.english_only_sentences(hinglish) == []
    assert critic.english_only_sentences("यह number forty-two के barabar है और कुछ नहीं है।") == []      # Devanagari is Hindi
    lesson = lesson_of([english, hinglish])
    found = [f for f in critic.language_gate(lesson) if "entirely in English" in f["what"]]
    assert [f["beat"] for f in found] == ["01"] and found[0]["severity"] == "major" and "3 of 3" in found[0]["what"]
    assert critic.language_gate(lesson_of([english], language="en-IN")) == []                       # an English lesson may be English
    # "हर" is far more often "every" than "denominator": it flagged a lesson about magnets
    assert critic.language_gate(lesson_of(["हर bar को thread से freely लटकाइए और देखिए क्या होता है।"], language="hi-IN")) == []


def test_the_reviewer_is_told_to_judge_the_example_the_method_and_the_numbers():
    lesson = lesson_of(["Ek baat."])
    lesson["method"] = ["divide by the smallest prime"]
    text = critic._lesson_text(lesson)
    assert "GOAL — after watching, the learner can: decide whether a four-digit number" in text
    assert "METHOD THE WRITER PROMISED TO SHOW: ['divide by the smallest prime']" in text
    for line in ("THE EXAMPLE.", "A part that stands for nothing", "THE METHOD.", "is there a case that FAILS", "THE NUMBERS."):
        assert line in critic.SYSTEM, line


# ── the questions asked before a video is made ───────────────────────────────

def test_the_kind_of_video_is_offered_in_words_about_this_topic_not_names_of_teaching_shapes():
    from lessonforge.harness import intake, interviewer
    base = intake.next_question({"topic": "Square numbers", "audience": "Class 8", "level": "foundation", "goal": "decide"})
    assert base["id"] == "framework" and base["prompt"] == "What kind of video should this be?"
    assert [o["label"] for o in base["options"]] == ["Start from a picture (suggested)", "Start from a solved example",
                                                     "Start from why it is true"]
    wrote = {"prompt": "Which video fits Class 8 for square numbers?", "why": "It decides how the video opens.",
             "options": [{"value": "concrete_first", "label": "Count a 3 by 3 square of dots, then find the rule", "hint": "New to squares"},
                         {"value": "worked_examples", "label": "Solve 1764 step by step, then try 2025", "hint": "Knows factors"},
                         {"value": "why_it_works", "label": "Test the pairing rule, break it, then prove it", "hint": "Wants the proof"}]}
    merged = interviewer.merge_question(base, wrote)
    assert merged["source"] == "model" and [o["value"] for o in merged["options"]] == ["concrete_first", "worked_examples", "why_it_works"]
    assert merged["options"][0]["label"] == "Count a 3 by 3 square of dots, then find the rule (suggested)"
    assert merged["options"][1]["label"] == "Solve 1764 step by step, then try 2025" and merged["options"][2]["hint"] == "Wants the proof"
    # jargon, a missing label or two labels the same: the plain names stay
    for spoil in ({"label": "Concrete first framework"}, {"label": ""}, {"label": wrote["options"][1]["label"]}):
        bad = {**wrote, "options": [{**wrote["options"][0], **spoil}] + wrote["options"][1:]}
        assert [o["label"] for o in interviewer.merge_question(base, bad)["options"]] == [o["label"] for o in base["options"]], spoil
    # every other fixed choice keeps its own labels whatever the model sends
    level = intake.next_question({"topic": "Square numbers", "audience": "Class 8"})
    relabelled = {"prompt": "How much do they know?", "options": [{"value": o["value"], "label": "X", "hint": "h"} for o in level["options"]]}
    assert [o["label"] for o in interviewer.merge_question(level, relabelled)["options"]] == [o["label"] for o in level["options"]]
    prompt = interviewer.build_prompt({"topic": "Square numbers"}, base, None)
    assert "write a topic-specific label AND a hint" in prompt and "choosing by what they would SEE" in prompt
    assert '"what_it_is": "Start from a picture"' in prompt and '"label": "Start' not in prompt     # nothing to echo back


def test_the_example_question_asks_for_one_simple_thing_never_a_setting():
    from lessonforge.harness import intake, interviewer
    brief = {"topic": "t", "audience": "a", "level": "foundation", "goal": "g", "framework": "concrete_first", "style": "tutor",
             "language": "en-IN", "duration_minutes": 6}
    question = intake.next_question(brief)
    text = (question["prompt"] + question["why"] + question["placeholder"]).lower()
    assert question["id"] == "context" and question["optional"] and "simple example" in text
    assert "cricket" not in text and "setting" not in text and "every chapter" not in text
    assert "Not a story or a setting" in interviewer._FIELD_MEANING["context"]
    for rule in ("The FIRST option is always the\n  plain one", "no festival, shop, sport, match, journey or character",
                 "more parts than the idea has is a bad example"):
        assert rule in interviewer.SYSTEM, rule
    assert "running example with a setting" not in interviewer.SYSTEM and "everyday settings" not in interviewer.SYSTEM
    assert {"label": "Kind of video", "value": "Start from a picture"} in intake.summary(brief)


# ── what the first regenerated lesson exposed ────────────────────────────────

def test_whatever_reaches_the_voice_has_no_digits_or_symbols_in_it():
    """A reviewer's rewrite put "1800 = 2 x 900, phir 900 = 2 x 450" into a Hinglish narration."""
    said = writer.speakable("Ab 1800 = 2 x 900, phir 900 = 2 x 450 hai.", "hinglish")
    assert said == ("Ab one thousand eight hundred equals two into nine hundred, phir nine hundred equals two into "
                    "four hundred fifty hai.")
    assert writer.speakable("5^2 + 4 is 29, and 12% of 3.5 is 0.42", "en-IN") == \
        "five squared plus four is twenty-nine, and twelve percent of three point five is zero point four two"
    assert writer.speakable("3 x 4 = 12", "en-IN") == "three times four equals twelve"
    assert writer.speakable("Ab hum forty-two ko todte hain.", "hinglish") == "Ab hum forty-two ko todte hain."   # untouched
    assert (writer.number_words(1764), writer.number_words(250000), writer.number_words(105), writer.number_words(40)) == \
        ("one thousand seven hundred sixty-four", "two lakh fifty thousand", "one hundred five", "forty")
    # at both doors: what the writer returns, and what a reviewer rewrites
    lesson = lesson_of(["Yahan 1800 = 2 x 900 likhte hain."])
    assert lesson["chapters"][0]["beats"][0]["narration"] == "Yahan one thousand eight hundred equals two into nine hundred likhte hain."
    critic.apply_edits(lesson, {"edits": [{"beat": "01", "narration": "Ab 900 = 2 x 450 dekhiye aur samjhiye."}]}, log=lambda *_: None)
    assert lesson["chapters"][0]["beats"][0]["narration"] == "Ab nine hundred equals two into four hundred fifty dekhiye aur samjhiye."
    # on screen, the letter x between numbers is a multiplication sign
    assert writer.one_line_math("12 = 2 x 2 x 3") == "12 = 2 \\times 2 \\times 3" and writer.one_line_math("x^2 + 2x") == "x^2 + 2x"
    assert "every number is written as English words" in critic.SYSTEM


def test_one_short_phrase_said_again_is_the_ideas_own_name_not_a_restatement():
    """The first version of the gate had "equal rows aur equal columns" cut out of the definition of a square number."""
    lesson = lesson_of(["Is tray mein equal rows aur equal columns hain, dekhiye dhyaan se."],
                       ["Jis total ko equal rows aur equal columns mein sajaya ja sake, use square number kehte hain."],
                       ["Ab ek bilkul nayi baat karte hain jo pehle nahin aayi thi."], anchor="a tray")
    assert critic.repetition_gate(lesson) == []
    assert "must not lose its rows and columns" in critic.REVISE_SYSTEM
    # a number said twice in one chapter is ordinary speech; the third time is not
    twice = lesson_of([f"Pehle {BIG} ko dekhiye. Isliye {BIG} square number hai."], anchor="a tray")
    thrice = lesson_of([f"Pehle {BIG} ko dekhiye. Phir {BIG} ko todiye. Isliye {BIG} square hai."], anchor="a tray")
    assert critic.repetition_gate(twice) == [] and len(critic.repetition_gate(thrice)) == 1


def test_a_question_asked_at_the_end_of_a_chapter_is_confirmed_by_the_next():
    prompts = []

    def llm(prompt, system):
        prompts.append(prompt)
        if "Plan a" in prompt:
            return {"title": "T", "thesis": "t", "anchor": "a tray", "chapters": [{"learning_goal": "g"} for _ in range(7)]}
        n = len(prompts) - 1
        ends_asking = n == 1
        return {"beats": [beat(f"Chapter {n} mein yeh alag baat number {n} hai. Kaunsa pair dikhta hai?" if ends_asking
                               else f"Chapter {n} mein yeh alag baat number {n} hai.",
                               **({"thinking_pause_seconds": 5, "quiz": {"question": "Which pair is in twelve?",
                                   "options": ["Two and three", "Two and two"], "answer_index": 1}} if ends_asking else {}))]}

    writer.write_lesson(BRIEF, llm, log=lambda *_: None)
    assert "ENDED BY ASKING THE LEARNER: “Which pair is in twelve?” (answer: Two and two)" in prompts[2]
    assert "confirming the answer in one short sentence" in prompts[2]
    assert all("ENDED BY ASKING" not in p for p in prompts[3:]) and "ENDED BY ASKING" not in prompts[1]
    assert "End by answering, in one sentence, the question the example posed" in frameworks.get("concrete_first")["stages"][4]["job"]


# ── what the other lessons' records showed ───────────────────────────────────

def test_the_recogniser_is_told_the_alphabet_the_script_is_written_in():
    """Nine Hinglish lessons: 123 of 155 narration blocks aligned. Told "hi", the recogniser wrote Devanagari."""
    from lessonforge.longform import align
    # Hinglish (Latin letters, Hindi speech) is heard both ways; everything else once
    assert align.stt_languages("Ab Diwali mela ke stall par chalte hain.", "hi-IN") == ["hi", "en"]
    assert align.stt_languages("अब दिवाली मेला के स्टॉल पर चलते हैं।", "hi-IN") == ["hi"]
    assert align.stt_languages("A ladder leans on a wall.", "en-IN") == ["en"] and align.stt_languages("", "te-IN") == ["te"]
    # heard in Devanagari, written in Latin: matched by sound
    for latin, devanagari in (("chalte", "चलते"), ("factor", "फैक्टर"), ("stall", "स्टॉल"), ("ladoos", "लड्डूस"), ("number", "नंबर"),
                              ("identical", "आइडेंटिकल"), ("hain", "हैं"), ("wahan", "वहां"), ("columns", "कॉलम्स"), ("cell", "सेल")):
        assert align.sound_key(latin) == align.sound_key(devanagari), latin
    spoken = [{"word": w, "start": i * 0.4, "end": i * 0.4 + 0.3} for i, w in enumerate("अब दिवाली मेला के स्टॉल पर चलते हैं".split())]
    words = [align.norm(w) for w in "Ab Diwali mela ke stall par chalte hain".split()]
    timings, coverage = align.align_words(words, spoken)
    assert coverage == 1.0 and timings[4]["start"] == pytest.approx(1.6)                       # "stall" is where स्टॉल was heard
    assert align.align_words(["a", "ladder", "leans"], [{"word": "a", "start": 0, "end": .1}, {"word": "letter", "start": .2, "end": .4},
                                                         {"word": "lens", "start": .5, "end": .7}])[1] == 1.0   # English stays exact + positional

    # the better of the two hearings is kept, and a good first one is not second-guessed
    calls = []

    def fake(text, wav, language=None, cache=None):
        calls.append(language)
        return {"coverage": {"hi": 0.58, "en": 0.97}[language], "trusted": True, "sentences": []}

    real, align.align_clip = align.align_clip, fake
    try:
        assert align.align_best("Ab stall par chalte hain", None, "hi-IN")["heard_as"] == "en" and calls == ["hi", "en"]
        calls.clear(); fake_cov = {"hi": 0.95}
        align.align_clip = lambda text, wav, language=None, cache=None: (calls.append(language), {"coverage": fake_cov[language], "trusted": True})[1]
        assert align.align_best("Ab stall par chalte hain", None, "hi-IN")["heard_as"] == "hi" and calls == ["hi"]
    finally:
        align.align_clip = real
    script = "Wahan one thousand seven hundred sixty-four ladoos taiyar hain aur forty-two rows banti hain".split()
    heard = [{"word": w, "start": i * 0.5, "end": i * 0.5 + 0.4} for i, w in enumerate(
        "Wahan 1764 laddoos tayyar hain aur 42 rows banti hain".split())]
    _, before = align.align_words([align.norm(w) for w in script], heard)
    timings, after = align.align_words([align.norm(w) for w in script], align.tidy_heard(heard))
    assert after > before and after >= 0.8
    # "sixty-four" is cued where the recogniser heard the END of "1764", not the start
    said = dict(zip(script, timings))
    assert 0.5 <= said["one"]["start"] < said["sixty-four"]["start"] < 1.0 and said["forty-two"]["matched"]
    assert align._digit_tokens(1764) == ["1", "1000", "7", "100", "64"] and align._token("forty-two") == "42"


def test_no_word_is_stamped_after_the_audio_ends():
    """An 18.2 s clip came back with its last word ending at 29.8 s; that block's last caption ran into the next block."""
    from lessonforge.longform import align
    heard = [{"word": "ek", "start": 0.2, "end": 0.6}, {"word": "bar", "start": 17.9, "end": 29.8}, {"word": "ghost", "start": 30.0, "end": 31.0}]
    tidy = align.tidy_heard(heard, 18.24)
    assert [h["word"] for h in tidy] == ["ek", "bar"] and tidy[-1]["end"] == 18.24
    assert align.tidy_heard(heard)[-1]["end"] == 31.0                                         # length unknown: left alone


def test_no_beat_opens_on_an_empty_screen():
    """Seven lessons had frames "empty … while the narrator is asking": every step tied to the beat's last sentence."""
    late = {"narration": "Diwali ke din hum ek sawaal poochte hain jo bahut seedha hai aur phir sochte hain. Kya forty-two rows banengi?",
            "steps": [{"say": "forty-two rows banengi", "show": "42 rows?"}, {"say": "Kya forty-two", "show": "x"}]}
    assert writer.open_with_something(late) and late["steps"][0]["say"] == "Diwali ke din" and late["steps"][1]["say"] == "Kya forty-two"
    early = {"narration": "Kya forty-two rows banengi? Hum ab dekhte hain aaram se.", "steps": [{"say": "forty-two rows", "show": "x"}]}
    with_picture = {**late, "figure": {"kind": "scene"}, "steps": [{"say": "forty-two rows banengi", "show": "x"}]}
    spread = {**late, "steps": [{"say": "", "show": "x"}]}
    assert not writer.open_with_something(early) and not writer.open_with_something(with_picture) and not writer.open_with_something(spread)
    # a beat whose animation could not be drawn loses its picture, and must not be left blank either
    lesson = lesson_of([beat("Pehle hum is cheez ko dhyaan se dekhte hain aur samajhte hain ki kya ho raha hai. Phir tray bharti hai.",
                             figure={"kind": "scene", "describe": "A tray fills with thirty six ladoos row by row"})])
    lesson["chapters"][0]["beats"][0]["steps"] = [{"say": "tray bharti hai", "show": "Tray fills", "kind": "point", "highlight": False}]
    service.resolve_scenes(lesson, log=lambda *_: None, generate=lambda brief: None)
    only = lesson["chapters"][0]["beats"][0]
    assert "figure" not in only and only["steps"][0]["say"] == "Pehle hum is"


def test_a_review_frame_is_taken_after_the_key_step_has_arrived():
    from lessonforge.harness import vision_review
    lesson = {"chapters": [{"beats": [{"id": "01", "steps": [{"say": "the key", "show": "Key", "kind": "key", "highlight": True}]}]}]}
    timeline = [{"id": "01", "chapter": 1, "start": 10.0, "duration": 12.0, "speech_end": 11.0,
                 "sentences": [{"text": "Here is the key idea.", "start": 1.0, "duration": 3.0}]}]
    assert vision_review.KEY_STEP_SETTLE >= 1.5 and vision_review.sample_points(timeline, lesson)[0]["at"] == 10.0 + 1.0 + vision_review.KEY_STEP_SETTLE


def test_a_rewrite_that_turns_hindi_into_english_is_refused_and_the_gates_get_the_last_word():
    """A reviewer answered a Hinglish beat's finding with five English sentences; no round was left to undo it."""
    hinglish = "Seven prime number hai, lekin six aur nine nahi hain. Ab prime factor ko dhyaan se dekhiye."
    english = ("Seven is prime, but six and nine are not. In twelve equals two into two into three, each factor is prime. "
               "Prime factorization means writing twelve as multiplication of prime factors.")
    lesson = lesson_of([hinglish])
    critic.apply_edits(lesson, {"edits": [{"beat": "01", "narration": english}]}, log=lambda *_: None)
    assert lesson["chapters"][0]["beats"][0]["narration"] == hinglish                       # stood aside
    assert "any text you write for it must be in exactly this" in critic._lesson_text(lesson) and "HINDI sentence" in critic._lesson_text(lesson)
    assert "never 'Seven is prime, but six and nine are not'" in writer._LANGUAGE_NOTES["hinglish"]

    # the writer's own English beat: the reviewer offers nothing, both reviews pass by, the gates still get it rewritten
    lesson = lesson_of([english], ["Ab hum is cheez ko aage badhate hain aur dekhte hain kya hota hai."])
    calls = []

    def reviewer(prompt, system):
        calls.append("revise" if system is critic.REVISE_SYSTEM else "review")
        if system is critic.REVISE_SYSTEM:
            # the first rewrite does not help; the gates' own pass does
            fixed = hinglish if calls.count("revise") == 2 else english + " Indeed it is so."
            return {"edits": [{"beat": "01", "narration": fixed}]}
        return {"scores": {k: 3 for k in critic.RUBRIC}, "findings": [], "claims": [], "edits": [], "summary": "ok"}

    verification = critic.verify(lesson, reviewer, log=lambda *_: None)
    assert calls == ["review", "revise", "review", "revise"]        # the last call is the gates' own rewrite, with no review after it
    assert lesson["chapters"][0]["beats"][0]["narration"] == hinglish and verification["status"] == "passed"
    assert verification["rounds"][-1] == {"round": "gates", "open_before": 1, "open_after": 0, "edits_applied": ["01"]}
    # and when even that does not help, the finding is reported as open — never as fixed because an edit landed
    stubborn = lesson_of([english], ["Ab hum is cheez ko aage badhate hain aur dekhte hain kya hota hai."])
    stays = lambda prompt, system: ({"edits": [{"beat": "01", "narration": english + " Indeed it is so."}]} if system is critic.REVISE_SYSTEM
                                    else {"scores": {k: 3 for k in critic.RUBRIC}, "findings": [], "claims": [], "edits": []})
    verdict = critic.verify(stubborn, stays, log=lambda *_: None)
    assert verdict["status"] == "needs_review" and verdict["major_unresolved"] == 1


def test_a_beat_that_ends_by_asking_gives_time_to_answer_and_a_suggested_example_is_only_a_suggestion():
    lesson = lesson_of(["Ab sochiye, kya update arrows bilkul smooth rahenge?", "Nahin, woh thode hilte hain."])
    asks, tells = lesson["chapters"][0]["beats"]
    assert asks["thinking_pause_seconds"] == 3.0 and tells["thinking_pause_seconds"] == 0.0
    block = writer._brief_block({**BRIEF, "context": "Adjusting cricket player training workloads based on fatigue sensors"},
                                frameworks.get("concrete_first"))
    assert "use it ONLY if it is simpler than the idea" in block and "drop people, sport, devices" in block
    assert "replace it with the thing itself in small" in block


def test_unit_symbols_are_said_as_their_names_and_one_takes_the_singular():
    # seen 2026-10-19 in a lesson on falling: "twenty N over one kilograms", read "twenty en"
    from lessonforge.harness.writer import speakable
    assert speakable("20 N over 1 kg gives 20") == "twenty newtons over one kilogram gives twenty"
    assert speakable("twenty N over one kilograms") == "twenty newtons over one kilogram"
    assert speakable("a = 9.8 m/s²") == "a equals nine point eight metres per second squared"
    assert speakable("It moves at 1 m/s, then 36 km/h") == "It moves at one metre per second, then thirty-six kilometres per hour"
    assert speakable("one point one kilograms and twenty-one kilograms") == "one point one kilograms and twenty-one kilograms"
    assert speakable("The N stands for newton") == "The N stands for newton"         # a letter with no number is left
    assert speakable("a/b = 2") == "a by b equals two"
