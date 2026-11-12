"""A script the requester wrote → a lesson (``harness/scripted.py``).

What is pinned here: the author's words reach the voice as written, structure comes from
their headings and paragraphs, and a model's answer can only add to the SCREEN. No
network, no render: the model is a stub.
"""
import re

import pytest

from lessonforge.harness import critic, scripted, service, writer
from lessonforge.longform.contract import Lesson

SCRIPT = """# Why the sky is blue

Have you ever looked up and wondered why the sky is blue? [show a blue sky with the sun]
Sunlight looks white, but it is really a mix of all the colours.

## Scattering
Visual: sunlight entering the air, blue rays bouncing more
In 1871 Lord Rayleigh explained it. Blue light has a shorter wavelength, about 450 nanometres, so it is scattered about 5.5 times more than red light. That scattered blue light reaches your eyes from every direction.

So what colour is the sky at sunset?

## Sunset
At sunset the light travels through much more air. Most of the blue is scattered away before it reaches you, e.g. over the sea. What is left is red and orange.
"""
PLAIN = ("A fraction names a part of a whole. Cut a roti into four equal pieces and take one. You now hold one fourth "
         "of the roti.\n\nThe bottom number says how many equal pieces the whole was cut into. The top number says how "
         "many of them you have.\n\nWhich is bigger, one half or one fourth?\n\nOne half is bigger, because the "
         "pieces are bigger when there are fewer of them.")
BRIEF = {"mode": "script", "script": SCRIPT, "audience": "Class 8 students"}


def director(prompt, system):
    """Stands in for the model that plans and designs the screen."""
    if system is scripted.PLAN_SYSTEM:
        return {"title": "A model's title", "thesis": "Why the sky is blue", "anchor": "sunlight in air",
                "glossary": [{"term": "scattering", "meaning": "light bounced in all directions", "say_it_as": "skat-er-ing"}],
                "picture_plan": "One sky that changes colour.", "chapters": [{"first_beat": "beat-03", "title": "Which is bigger"}]}
    assert system is scripted.DIRECT_SYSTEM and "narration" not in scripted._BEAT_SHAPE
    asked = prompt.split("these beats, every one of them:")[1].split("JSON shape")[0]
    ids = [line[1:3] for line in asked.splitlines() if line.startswith("[")]
    return {"beats": [{"id": f"beat-{i}", "narration": "REWRITTEN BY THE MODEL", "visual": "a sky", "depth": "core",
                       "figure": {"kind": "scene", "describe": "Sunlight enters the air and blue rays scatter more than red ones"},
                       "quiz": {"question": "What colour at sunset?", "options": ["Blue", "Red", "Green"], "answer_index": 1,
                                "explain": "Blue is scattered away."},
                       "steps": [{"say": "made up words", "show": "Blue scatters most", "kind": "key", "highlight": True}]}
                      for i in ids]}


def test_headings_become_parts_and_what_is_not_narration_is_never_spoken():
    parsed = scripted.parse_script(SCRIPT)
    assert parsed["title"] == "Why the sky is blue" and parsed["language"] == "en-IN"
    assert [s["title"] for s in parsed["sections"]] == [None, "Scattering", "Sunset"]
    said = " ".join(b["narration"] for s in parsed["sections"] for b in s["beats"])
    for never in ("show a blue sky", "sunlight entering the air", "Visual", "#", "[", "Scattering"):
        assert never not in said, never
    first, second = parsed["sections"][0]["beats"][0], parsed["sections"][1]["beats"][0]
    assert first["direction"] == "show a blue sky with the sun" and second["direction"].startswith("sunlight entering")
    # numbers are read out as words, a year as a year
    assert "In eighteen seventy-one Lord Rayleigh" in said and "four hundred fifty nanometres" in said
    assert "five point five times" in said and not any(ch.isdigit() for ch in said)
    # the closing question joined the paragraph before it, so the beat ENDS by asking
    assert second["narration"].endswith("So what colour is the sky at sunset?") and len(parsed["sections"][1]["beats"]) == 1
    assert "e.g. over the sea. What is left" in parsed["sections"][2]["beats"][0]["narration"]


def test_a_long_paragraph_is_cut_at_sentence_ends_and_nothing_is_lost():
    sentence = "The ladder leans on the wall and its foot is four metres from the wall on level ground."
    text = " ".join([sentence] * 12)
    beats = [b["narration"] for s in scripted.parse_script(text)["sections"] for b in s["beats"]]
    assert len(beats) == 3 and " ".join(beats) == text
    assert all(len(b.split()) <= scripted.MAX_BEAT_WORDS and b.endswith(".") for b in beats)
    assert len({len(b.split()) for b in beats}) == 1          # about equal, not 75 + 75 + a remainder


def test_what_only_looks_like_a_heading_is_still_spoken():
    text = "Introduction\n\n" + PLAIN + "\n\nThank You"
    parsed = scripted.parse_script(text)
    # "Introduction" names the document, not the lesson: neither spoken, nor a title, nor a part
    assert parsed["title"] == "" and [s["title"] for s in parsed["sections"]] == [None]
    assert "Introduction" not in parsed["sections"][0]["beats"][0]["narration"]
    assert parsed["sections"][0]["beats"][-1]["narration"].endswith("Thank You")
    alone = scripted.parse_script("Fractions\n\n" + PLAIN)       # one heading at the top is the title
    assert alone["title"] == "Fractions" and alone["sections"][0]["title"] is None
    worded = scripted.parse_script("Part 1: The idea\n" + PLAIN + "\n\nPart 2 is where we compare them.\n" + PLAIN)
    # "Part 2 is where…" is a sentence, so "Part 1: The idea" is the only heading: the title
    assert worded["title"] == "The idea" and "Part two is where we compare them." in " ".join(
        b["narration"] for b in worded["sections"][0]["beats"])
    two = scripted.parse_script("Part 1: The idea\n" + PLAIN + "\n\nPart 2 - Comparing\n" + PLAIN)
    assert [s["title"] for s in two["sections"]] == ["The idea", "Comparing"] and two["title"] == ""


def test_language_is_read_from_the_script():
    assert scripted.detect_language(PLAIN) == "en-IN"
    assert scripted.detect_language("Dekhiye, ab hum ek triangle banate hain aur uski sides ko naam dete hain.") == "hinglish"
    assert scripted.detect_language("भिन्न किसी पूरे का एक हिस्सा होता है। रोटी को four बराबर टुकड़ों में काटिए।") == "hi-IN"
    assert scripted.parse_script(PLAIN, "hinglish")["language"] == "hinglish"          # the requester's choice wins
    assert scripted.parse_script(PLAIN, "klingon")["language"] == "en-IN"


def test_too_little_or_too_much_is_refused_before_anything_is_spent():
    with pytest.raises(ValueError, match="too short"):
        scripted.preview("Just a title")
    with pytest.raises(ValueError, match="split it into parts"):
        scripted.preview("word " * (scripted.MAX_WORDS + 1))
    with pytest.raises(ValueError):
        service.start_job({"mode": "script", "script": "[only a direction]"})


def test_the_preview_reads_the_script_back():
    view = scripted.preview(SCRIPT)
    assert view["title"] == "Why the sky is blue" and view["parts_from"] == "headings"
    assert [c["title"] for c in view["chapters"]] == ["Opening", "Scattering", "Sunset"]
    assert view["words"] == sum(c["words"] for c in view["chapters"]) and view["beats"] == 3
    assert any("not spoken" in n for n in view["notes"]) and any("read out as words" in n for n in view["notes"])
    assert [row["label"] for row in view["summary"]] == ["Title", "Length", "Parts", "Language"]
    free = scripted.preview(PLAIN)
    assert free["parts_from"] == "planned" and free["chapters"] == [] and any("No headings" in n for n in free["notes"])
    assert free["title"].startswith("A fraction names a part of a whole")


def test_the_brief_a_job_keeps():
    brief = scripted.prepare({**BRIEF, "framework": "worked_examples", "duration_minutes": 9, "script_edit": "bogus"})
    assert brief == {"mode": "script", "script": SCRIPT.strip(), "language": "en-IN", "topic": "Why the sky is blue",
                     "script_edit": "keep", "audience": "Class 8 students", "grade": 8}
    assert scripted.prepare(brief) == brief                                   # "Try again" posts it back
    assert scripted.keeps_words(brief) and not scripted.keeps_words({**brief, "script_edit": "fix"})
    assert not scripted.is_script({"topic": "Fractions"}) and not scripted.keeps_words({"topic": "Fractions"})


def test_the_model_designs_the_screen_and_cannot_touch_a_word():
    log = []
    lesson = scripted.script_lesson(scripted.prepare(BRIEF), director, log=log.append)
    Lesson.model_validate(lesson)
    parsed = scripted.parse_script(SCRIPT)
    beats = [b for c in lesson["chapters"] for b in c["beats"]]
    assert [b["narration"] for b in beats] == [b["narration"] for s in parsed["sections"] for b in s["beats"]]
    assert not any("WARNING" in line for line in log)
    # the author's headings stand (the model's chapters are not asked), and so does the author's title
    assert [c["title"] for c in lesson["chapters"]] == ["OPENING", "SCATTERING", "SUNSET"]
    assert lesson["title"] == "Why the sky is blue" and lesson["generated_by"] == "script" and lesson["framework"] == "script"
    assert lesson["script"]["parts_from"] == "headings" and lesson["script"]["undesigned"] == []
    for beat in beats:
        assert beat["figure"]["kind"] == "scene" and beat["depth"] == "core"
        step = beat["steps"][0]
        # an anchor the model invented is re-derived from the narration or spread, never trusted
        assert step["say"] == "" or writer._norm(step["say"]) in writer._norm(beat["narration"])
    # a question card only where the SCRIPT asks; a statement gets neither a card nor silence
    asking = [b for b in beats if b["narration"].endswith("?")]
    assert [b["id"] for b in asking] == ["02"] and asking[0]["quiz"]["answer_index"] == 1
    assert asking[0]["thinking_pause_seconds"] == 5.0
    assert all("quiz" not in b and b["thinking_pause_seconds"] == 0 for b in beats if b not in asking)
    assert "No running example was named." not in lesson["continuity"]["warnings"]
    # the reviewer is not told to hold a pasted script to a goal or a method nobody declared
    read = critic._lesson_text(lesson)
    assert "WRITTEN BY ITS AUTHOR" in read and "GOAL —" not in read and "METHOD THE WRITER" not in read


def test_a_script_without_headings_takes_its_parts_from_the_plan_or_from_its_length():
    lesson = scripted.script_lesson(scripted.prepare({"mode": "script", "script": PLAIN}), director, log=lambda *_: None)
    assert [c["title"] for c in lesson["chapters"]] == ["OPENING", "WHICH IS BIGGER"]        # "beat-03" understood
    assert [len(c["beats"]) for c in lesson["chapters"]] == [2, 1] and lesson["script"]["parts_from"] == "model"
    assert lesson["title"] == "A model's title"
    long = "\n\n".join(f"Fact number {writer.number_words(i)} is that a square with side {writer.number_words(i)} "
                       f"has an area you can count on a grid of little unit squares drawn inside it." for i in range(1, 24))
    chapters, source = scripted.chapterise(scripted.parse_script(long), [{"first_beat": str(i)} for i in range(1, 24)])
    assert source == "even" and all(len(c["beats"]) <= scripted.EVEN_CHAPTER_BEATS for c in chapters)   # 23 one-beat parts: not a plan
    one, _ = scripted.chapterise({**scripted.parse_script(long), "sections": [
        {"title": "Everything", "beats": [b for s in scripted.parse_script(long)["sections"] for b in s["beats"]]}]})
    assert [c["title"] for c in one] == ["Everything", "Everything (2)", "Everything (3)"]
    assert all(len(c["beats"]) <= scripted.MAX_CHAPTER_BEATS for c in one)


def test_a_part_the_model_fails_on_falls_back_and_total_failure_stops():
    def flaky(prompt, system):
        if system is scripted.DIRECT_SYSTEM and "“Scattering”" in prompt:
            raise TimeoutError("the model did not answer")
        return director(prompt, system)

    log = []
    lesson = scripted.script_lesson(scripted.prepare(BRIEF), flaky, log=log.append)
    assert lesson["script"]["undesigned"] == ["02"] and any("trying once more" in line for line in log)
    middle = lesson["chapters"][1]["beats"][0]
    assert "figure" not in middle and middle["steps"][0]["show"].startswith("In eighteen seventy-one")

    def dead(prompt, system):
        raise TimeoutError("the model did not answer")
    with pytest.raises(RuntimeError, match="Nothing was narrated"):
        scripted.script_lesson(scripted.prepare(BRIEF), dead, log=lambda *_: None)


def test_a_beat_the_director_left_bare_is_asked_for_once_more():
    calls = []

    def forgetful(prompt, system):
        answer = director(prompt, system)
        if system is scripted.DIRECT_SYSTEM and "“Scattering”" in prompt:
            calls.append(prompt)
            if len(calls) == 1:                     # named the beat and gave it nothing to show
                answer = {"beats": [{"id": b["id"], "visual": "", "steps": [], "figure": None} for b in answer["beats"]]}
        return answer

    log = []
    lesson = scripted.script_lesson(scripted.prepare(BRIEF), forgetful, log=log.append)
    assert len(calls) == 2 and "no steps and no figure" in calls[1] and "no steps and no figure" not in calls[0]
    assert lesson["script"]["undesigned"] == [] and any("no screen for beat(s) 02" in line for line in log)
    assert lesson["chapters"][1]["beats"][0]["figure"]["kind"] == "scene"

    # ... and a bare second answer does not undo a first answer that designed the beat
    def worse_second(prompt, system):
        answer = director(prompt, system)
        if system is scripted.DIRECT_SYSTEM and "no steps and no figure" in prompt:
            answer = {"beats": []}
        return answer
    assert scripted.script_lesson(scripted.prepare(BRIEF), worse_second, log=lambda *_: None)["script"]["undesigned"] == []


def _with_a_picture(marks_focus=None):
    """A director whose plan asks the diagram service for a picture and whose beats carry it."""
    prompts = []

    def model(prompt, system):
        answer = director(prompt, system)
        if system is scripted.PLAN_SYSTEM:
            return {**answer, "diagram_ask": "Why the sky is blue,   as a labelled picture"}
        prompts.append(prompt)
        for beat in answer["beats"]:
            beat["figure"] = {"kind": "diagram", "file": "/etc/passwd"}          # a model never names a file
            if marks_focus:
                beat["steps"][0]["focus"] = marks_focus
        return answer
    return model, prompts


def test_a_prepared_picture_with_no_parts_to_point_at_is_shown_whole():
    asked = []

    def prepare(ask, brief, log):
        asked.append(ask)
        return {"ask": "Why the sky is blue, as a labelled picture", "manifest": "/lib/sky/manifest.json", "parts": ["a_line"],
                "names": {"a_line": "Blue light scatters"}, "credit": "Art: someone, CC BY", "shown": "whole",
                "file": "/lib/sky/source.png"}

    model, prompts = _with_a_picture(marks_focus="a_line")
    log = []
    lesson = scripted.script_lesson(scripted.prepare(BRIEF), model, log=log.append, prepare=prepare)
    assert len(asked) == 1 and all("A PREPARED PICTURE is ready" in p and "shown whole" in p for p in prompts)
    beats = [b for c in lesson["chapters"] for b in c["beats"]]
    assert all(b["figure"] == {"kind": "picture", "file": "/lib/sky/source.png",
                               "ask": "Why the sky is blue, as a labelled picture"} for b in beats)
    assert not any("focus" in step for b in beats for step in b["steps"])
    assert lesson["credits"] == ["Art: someone, CC BY"]
    # one drawing for the whole script ("diagram_ask"): every part takes it, and it is asked for once
    assert lesson["script"]["pictures"] == [{"ask": "Why the sky is blue, as a labelled picture", "shown": "whole", "parts": [1, 2, 3]}]
    assert sum("shown whole on 1 beat(s)" in line for line in log) == 3
    Lesson.model_validate(lesson)


def test_a_drawing_in_panels_shows_the_first_and_reveals_the_next_where_a_step_says_so():
    def prepare(ask, brief, log):
        return {"ask": "A coin on a card on a glass, before and after the flick", "manifest": "/lib/coin/manifest.json",
                "parts": [], "names": {}, "credit": "", "shown": "whole", "file": "/lib/coin/whole_stacked.png",
                "panels": ["/lib/coin/panel_1.png", "/lib/coin/panel_2.png"], "panel_boxes": [[0, 0, 640, 389], [0, 400, 640, 789]]}

    model, prompts = _with_a_picture(marks_focus="Panel_2")
    lesson = scripted.script_lesson(scripted.prepare(BRIEF), model, log=lambda *_: None, prepare=prepare)
    assert all("It has 2 panels" in p and '"panel2"' in p and "shown whole" not in p for p in prompts)
    beats = [b for c in lesson["chapters"] for b in c["beats"]]
    assert beats[0]["figure"]["panels"] == ["/lib/coin/panel_1.png", "/lib/coin/panel_2.png"]
    assert beats[0]["figure"]["panel_boxes"] == [[0, 0, 640, 389], [0, 400, 640, 789]] and beats[0]["figure"]["kind"] == "picture"
    # the model marked every beat's first step: the panel is revealed ONCE, by the first, and nothing else has a focus
    focuses = [step.get("focus") for beat in beats for step in beat["steps"]]
    assert focuses.count("panel2") == 1 and beats[0]["steps"][0]["focus"] == "panel2" and set(focuses) <= {"panel2", None}
    # the parts after the reveal show the drawing whole: a part is a render of its own and would start at panel 1 again
    assert all(b["figure"] == {"kind": "picture", "file": "/lib/coin/whole_stacked.png",
                               "ask": "A coin on a card on a glass, before and after the flick"} for b in beats[1:])


def test_each_part_of_a_script_gets_its_own_drawing_and_a_part_without_one_keeps_the_last():
    """The plan asks the drawing service for one picture per part; model-written scenes are what is left over."""
    asked = []

    def prepare(ask, brief, log):
        asked.append(ask)
        if "prism" in ask:
            return None                                                  # the service had nothing usable for this one
        return {"ask": ask, "manifest": f"/lib/{len(asked)}/manifest.json", "parts": [], "names": {}, "credit": "",
                "shown": "whole", "file": f"/lib/{ask.split()[0].lower()}.png"}

    prompts = {}

    def model(prompt, system):
        answer = director(prompt, system)
        if system is scripted.PLAN_SYSTEM:
            return {**answer, "chapters": [{"first_beat": "01", "title": "x", "picture": "Sunlight entering the air above a city"},
                                           {"first_beat": "02", "title": "y", "picture": ""},
                                           {"first_beat": "03", "title": "z", "picture": "A prism splitting white light"}]}
        part = prompt.split("Design the screen for part ")[1][0]
        prompts[part] = prompt
        for beat in answer["beats"]:
            beat["figure"] = {"kind": "diagram"}
        return answer

    log = []
    lesson = scripted.script_lesson(scripted.prepare(BRIEF), model, log=log.append, prepare=prepare)
    # each asked for ONCE here: the second ask of a drawing the service fails is diagrams.fetch's (SERVICE_TRIES), for every path
    assert sorted(asked) == ["A prism splitting white light", "Sunlight entering the air above a city"]
    one, two, three = (c["beats"][0] for c in lesson["chapters"])
    assert one["figure"]["file"] == "/lib/sunlight.png" and two["figure"] == one["figure"]       # the part with none keeps it
    assert "figure" not in three                                         # asked for, not to be had: no mark is left standing
    assert "Sunlight entering the air" in prompts["1"] and "Sunlight entering the air" in prompts["2"]
    assert "PREPARED PICTURE" not in prompts["3"]                        # the director is told only of a picture that exists
    assert lesson["script"]["pictures"] == [{"ask": "Sunlight entering the air above a city", "shown": "whole", "parts": [1, 2]}]
    assert lesson["script"]["picture_missed"] == "A prism splitting white light"                 # so this plan is not kept
    assert scripted.part_pictures([{"beats": [{"id": "01"}]}, {"beats": [{"id": "02"}]}], {"diagram_ask": "The water cycle"},
                                  {"01": 0, "02": 1}) == ["The water cycle", "The water cycle"]


def test_a_prepared_picture_whose_parts_have_names_goes_through_the_writers_diagram():
    def prepare(ask, brief, log):
        return {"ask": "Sunlight in air", "manifest": "/lib/air/manifest.json", "parts": ["blue_light", "red_light"],
                "names": {"blue_light": "Blue light", "red_light": "Red light"}, "credit": "", "shown": "parts"}

    model, prompts = _with_a_picture(marks_focus="blue_light")
    lesson = scripted.script_lesson(scripted.prepare(BRIEF), model, log=lambda *_: None, prepare=prepare)
    assert all('"blue_light" (Blue light)' in p and "shown whole" not in p for p in prompts)
    for beat in (b for c in lesson["chapters"] for b in c["beats"]):
        assert beat["figure"] == {"kind": "diagram", "manifest": "/lib/air/manifest.json", "labels": ["blue_light"],
                                  "ask": "Sunlight in air"}
        assert beat["steps"][0]["focus"] == "blue_light"


def test_no_picture_prepared_means_the_director_is_not_told_and_a_stray_mark_is_removed():
    model, prompts = _with_a_picture()
    lesson = scripted.script_lesson(scripted.prepare(BRIEF), model, log=lambda *_: None, prepare=lambda *a: None)
    assert not any("PREPARED PICTURE" in p for p in prompts)
    assert not any("figure" in b for c in lesson["chapters"] for b in c["beats"]) and "pictures" not in lesson["script"]
    # ... and the lesson says its plan asked for a picture that could not be had, so this screen is not kept for the script
    assert lesson["script"]["picture_missed"].startswith("Why the sky is blue")
    assert "picture_missed" not in scripted.script_lesson(scripted.prepare(BRIEF), director, log=lambda *_: None)["script"]
    # a plan that asks for nothing never reaches the service
    def never(*_):
        raise AssertionError("asked for a picture nobody planned")
    scripted.script_lesson(scripted.prepare(BRIEF), director, log=lambda *_: None, prepare=never)


def test_how_a_fetched_drawing_is_shown_is_the_diagram_tools_one_rule(tmp_path, monkeypatch):
    import json as _json
    from lessonforge.harness import diagrams
    folder = tmp_path / "water"
    folder.mkdir()
    (folder / "manifest.json").write_text(_json.dumps({"folder": str(folder), "labels": [], "parts": []}))
    (folder / "source.png").write_bytes(b"png")
    calls, pointable = [], []

    def fetched(ask, klass, language, log=print):
        calls.append((ask, klass, language))
        return {"ask": ask, "manifest": str(folder / "manifest.json"), "parts": list(pointable),
                "names": {p: p.title() for p in pointable}, "credit": ""}

    monkeypatch.setattr(diagrams, "available", lambda: True)
    monkeypatch.setattr(diagrams, "prepare", fetched)
    assert scripted.prepared_picture("Water cycle", {"audience": "Class 7"}, log=lambda *_: None) is None   # off in tests
    monkeypatch.setenv("HARNESS_SCRIPT_PICTURES", "1")
    # nothing in it can be named: shown whole, from the drawing the service sent along
    ready = scripted.prepared_picture("  Water   cycle ", {"audience": "Class 7 students"}, log=lambda *_: None)
    assert ready["shown"] == "whole" and ready["file"] == str(folder / "source.png") and calls == [("Water cycle", 7, "en")]
    # the tool's own drawings are preferred: its 1280-wide one, and before that a wide strip re-laid in two rows
    (folder / "whole.png").write_bytes(b"png")
    (folder / "manifest.json").write_text(_json.dumps({"folder": str(folder), "whole": "whole.png", "labels": []}))
    assert scripted.prepared_picture("Water cycle", {}, log=lambda *_: None)["file"] == str(folder / "whole.png")
    (folder / "stacked.png").write_bytes(b"png")
    (folder / "manifest.json").write_text(_json.dumps({"folder": str(folder), "whole": "whole.png", "whole_stacked": "stacked.png"}))
    assert scripted.prepared_picture("Coin and card", {}, log=lambda *_: None)["file"] == str(folder / "stacked.png")
    # enough of it can be named: its parts are pointed at, and no file is needed
    pointable[:] = ["evaporation", "condensation", "precipitation"]
    named = scripted.prepared_picture("Water cycle", {}, log=lambda *_: None)
    assert named["shown"] == "parts" and named["parts"] == pointable and "file" not in named
    # neither way: not used, and never a failure
    pointable[:] = []
    for name in ("whole.png", "stacked.png", "source.png"):
        (folder / name).unlink()
    assert scripted.prepared_picture("Water cycle", {}, log=lambda *_: None) is None
    monkeypatch.setattr(diagrams, "prepare", lambda *a, **k: (_ for _ in ()).throw(TimeoutError("service down")))
    assert scripted.prepared_picture("Water cycle", {}, log=lambda *_: None) is None
    monkeypatch.setattr(diagrams, "available", lambda: False)
    assert scripted.prepared_picture("Water cycle", {}, log=lambda *_: None) is None


def test_reference_lessons_reach_the_screens_designer_and_never_the_words():
    prompts = []

    def model(prompt, system):
        prompts.append((system, prompt))
        return director(prompt, system)

    reference = {"topic": "Why the sky is blue", "klass": 8, "notes": "HOW REFERENCE LESSONS SHOW THIS TOPIC\nS1 shows a prism first, then a beam in milky water.",
                 "sources": [{"id": "S1", "kind": "lecture", "title": "Why is the sky blue? (a lecture)", "url": "https://example.org/v", "note": "x"}]}
    lesson = scripted.script_lesson(scripted.prepare(BRIEF), model, log=lambda *_: None, reference=reference)
    assert all("a beam in milky water" in p and "The narration is final" in p for _, p in prompts)      # the plan and every part
    parsed = scripted.parse_script(SCRIPT)
    assert [b["narration"] for c in lesson["chapters"] for b in c["beats"]] == [b["narration"] for s in parsed["sections"] for b in s["beats"]]
    assert lesson["script"]["references"] == [{"title": "Why is the sky blue? (a lecture)", "url": "https://example.org/v"}]
    # nothing found: nothing said, nothing listed
    prompts.clear()
    plain = scripted.script_lesson(scripted.prepare(BRIEF), model, log=lambda *_: None, reference={"notes": "", "sources": [{"title": "x"}]})
    assert not any("REFERENCE LESSONS" in p for _, p in prompts) and "references" not in plain["script"]


DIALOGUE = """Narrator: Shaam ka time hai. Achanak light chali gayi aur room dark ho gaya.

Asha: Kya electricity koi liquid hai jo wire ke andar bhara hota hai?

Teacher: Bahut achha sawaal! Aaj hum khud dekhenge aur samjhenge.

[Pause]

Kabir (surprised): Yani battery mein electricity thi?

Teacher: Achha guess hai, lekin battery electricity store karke nahi rakhti.

Asha: Toh bulb kab jalta hai?

Kabir: Jab circuit ka path complete hota hai.

Note: yeh line bhi boli jaati hai, kyunki Note ek hi baar aaya hai.
"""


def test_a_dialogue_scripts_character_names_and_lone_directions_are_not_spoken_or_made_headings():
    parsed = scripted._parse(DIALOGUE, "hinglish")
    said = " ".join(b["narration"] for s in parsed["sections"] for b in s["beats"])
    assert "Asha" not in said and "Kabir" not in said and "Teacher" not in said and "Narrator" not in said
    assert "Kya electricity koi liquid hai" in said and "Yani battery mein electricity thi?" in said     # their words are
    assert "Pause" not in said and all("Pause" not in str(s["title"]) for s in parsed["sections"])         # a direction only
    assert "Note: yeh line" in said                                      # one "Word:" opener is a sentence, not a speaker


def test_a_part_whose_heading_is_only_a_label_is_named_and_cut_by_the_plan():
    long_paragraph = " ".join(["Yeh ek lamba paragraph hai jisme circuit ke baare mein ek poori baat kahi gayi hai."] * 6)
    many = scripted.MAX_CHAPTER_BEATS * 2 + 2
    text = "## Scene 1\n\n" + "\n\n".join(f"Paragraph {k}. {long_paragraph}" for k in range(1, many + 1)) \
        + "\n\n## What we learned\n\nAaj humne dekha ki circuit ka path complete hona zaroori hai. " + long_paragraph
    parsed = scripted._parse(text, "hinglish")
    assert [s["title"] for s in parsed["sections"]] == ["Scene 1", "What we learned"]
    scene = parsed["sections"][0]["beats"]
    assert len(scene) > scripted.MAX_CHAPTER_BEATS                      # too long for one chapter
    third = len(scene) // 3
    plan = [{"first_beat": scene[0]["id"], "title": "The lights go out"}, {"first_beat": scene[third]["id"], "title": "A complete path"},
            {"first_beat": scene[2 * third]["id"], "title": "Charges in the wire"}]
    chapters, source = scripted.chapterise(parsed, plan)
    assert source == "headings" and not any("Scene" in c["title"] for c in chapters)
    names = list(dict.fromkeys(re.sub(r" \(\d+\)$", "", c["title"]) for c in chapters))      # "(2)": a piece still too long
    assert names == ["The lights go out", "A complete path", "Charges in the wire", "What we learned"]
    opens = {c["beats"][0]["id"]: c["title"] for c in chapters}
    assert opens[scene[0]["id"]] == "The lights go out" and opens[scene[third]["id"]] == "A complete path"
    assert opens[scene[2 * third]["id"]] == "Charges in the wire"       # cut where the plan said, named as the plan said
    assert all(len(c["beats"]) <= scripted.MAX_CHAPTER_BEATS for c in chapters)
    assert sum(len(c["beats"]) for c in chapters) == len(scene) + len(parsed["sections"][1]["beats"])     # nothing lost
    # with no plan the label is all there is, and a real heading is never renamed or cut where it need not be
    bare, _ = scripted.chapterise(parsed, None)
    assert bare[0]["title"] == "Scene 1" and bare[-1]["title"] == "What we learned"
    kept, _ = scripted.chapterise(scripted._parse(SCRIPT), [{"first_beat": "02", "title": "A model's own name"}])
    assert [c["title"] for c in kept] == ["Opening", "Scattering", "Sunset"]


def test_without_a_model_the_script_is_still_narrated_and_says_what_it_is():
    lesson = scripted.plain_lesson(scripted.prepare(BRIEF))
    assert "no model configured" in lesson["generated_by"] and len(lesson["chapters"]) == 3
    assert all(b["steps"] and not b.get("figure") for c in lesson["chapters"] for b in c["beats"])
    hindi = scripted.plain_lesson(scripted.prepare({"mode": "script", "script": "भिन्न किसी पूरे का एक हिस्सा होता है। " * 6}))
    assert all(b["steps"] == [] for c in hindi["chapters"] for b in c["beats"])     # no narration on an English screen
    assert scripted.plain_steps("Don’t add the sides — square them first, then add.")[0]["show"].startswith("Don’t add")


def test_the_reviewer_reports_on_a_kept_script_and_changes_nothing():
    wrong = PLAIN.replace("One half is bigger", "Nine plus sixteen gives twenty-four. One half is bigger")
    lesson = scripted.plain_lesson(scripted.prepare({"mode": "script", "script": wrong}))
    before = [b["narration"] for c in lesson["chapters"] for b in c["beats"]]

    def reviewer(prompt, system):
        return {"scores": {k: 3 for k in critic.RUBRIC}, "findings": [{"severity": "major", "beat": "03", "what": "wrong sum", "fix": "say 25"}],
                "claims": [], "summary": "one slip",
                "edits": [{"beat": b, "narration": "Rewritten by the reviewer so that it is different now."} for b in ("01", "02", "03")]}
    report = critic.verify(lesson, reviewer, log=lambda *_: None, apply=False)
    assert [b["narration"] for c in lesson["chapters"] for b in c["beats"]] == before
    assert report["status"] == "needs_review" and len(report["claims_failed"]) == 1 and report["beats_rewritten"] == []
    assert not any(f["resolved"] for f in report["findings"])


def test_the_screen_rules_are_the_writers_own():
    """A figure kind or a step field is described once, and both prompts carry it."""
    for shared in (writer.STEP_RULES, writer.SCREEN_TEXT_RULE, writer.FIGURE_RULES):
        assert shared in writer.SYSTEM and shared in scripted.DIRECT_SYSTEM
    for kind in writer.FIGURE_KINDS:
        assert f'"kind":"{kind}"' in scripted.DIRECT_SYSTEM
    assert "SAY A THING ONCE" not in scripted.DIRECT_SYSTEM            # rules for WRITING words do not apply here


# ── a production table pasted as text (the first real script a user pasted, 2026-10-09) ──

TABLE = """Meera, a Class 6 girl, helps her uncle sell fruit. Every idea comes from the stall.
Characters (flat 2D, consistent across scenes): Meera – eleven, blue frock. Uncle – white cap, a weighing scale.
Look and feel for this story: bright cartoon, warm colours.
Scene
Time
On-screen visual
Voiceover (Hinglish)
1
0:00–0:30
A cart of mangoes rolls into the market; Meera waves.
Narrator: Aaj Meera apne uncle ke stall par hai. Uncle ne poocha, "Ek mango ko 2 equal parts mein kaato, to har part kya hai?"
2
0:30–1:30
A mango splits into two halves; one half glows.
Meera boli, "One half!" Narrator: Agar 9 × 9 tiles hon to 9² likhte hain, aur n × n ko n² kehte hain.
3
1:30–2:00
The same mango is cut into four; the pieces shrink.
Ab usi mango ko 4 equal parts mein kaato. Har part chhota ho gaya, kyunki parts zyada hain.
Scene 3 on-screen questions (show only the questions; answers are for the teacher):
1. Level 1 – Easy (green): Which is bigger, 1/2 or 1/4? Answer: 1/2
2. Level 2 – Medium (yellow): Cut a roti into 8 parts. What is one part called? Answer: one eighth
"""


def _spoken_and_directions(parsed):
    beats = [b for s in parsed["sections"] for b in s["beats"]]
    return " ".join(b["narration"] for b in beats), [b["direction"] for b in beats]


def test_only_the_voiceover_column_of_a_pasted_script_table_is_spoken():
    parsed = scripted.parse_script(TABLE)
    said, directions = _spoken_and_directions(parsed)
    assert parsed["table"] == {"columns": ["scene", "time", "visual", "spoken"], "rows": 3} and parsed["language"] == "hinglish"
    for never in ("Characters", "Look and feel", "sell fruit", "cart of mangoes", "splits into two", "0:30", "Scene", "Voiceover",
                  "On-screen", "Narrator", "Answer", "Level 1", "one eighth", "teacher"):
        assert never not in said, never
    assert said.startswith("Aaj Meera apne uncle ke stall par hai.") and said.endswith("kyunki parts zyada hain.")
    # each row's visual cell directs the picture for that row's words
    assert [d[:22] for d in directions] == ["A cart of mangoes roll", "A mango splits into tw", "The same mango is cut "]
    # what a voice cannot read is put into words: 9 × 9, 9², n × n, n²; a label in the middle of a cell goes
    assert 'Meera boli, "One half!" Agar nine into nine tiles hon to nine squared likhte hain, aur n into n ko n squared kehte hain.' in said
    # the author's lines outside the table are notes for the director, not narration
    assert "Characters (flat 2D" in parsed["notes"] and "Answer: one eighth" in parsed["notes"] and "bright cartoon" in parsed["notes"]
    view = scripted.preview(TABLE)
    assert "script table with 3 rows" in view["notes"][0] and "not spoken" in view["notes"][0]
    assert view["words"] == len(said.split()) and view["parts_from"] == "planned"
    seen = []

    def model(prompt, system):
        seen.append(prompt)
        if system is scripted.PLAN_SYSTEM:
            return {"title": "Half and fourth at the stall", "chapters": []}
        return {"beats": [{"id": i, "steps": [{"say": "x", "show": "1/2", "kind": "math"}]} for i in ("01", "02", "03")]}
    lesson = scripted.script_lesson(scripted.prepare({"mode": "script", "script": TABLE}), model, log=lambda *_: None)
    assert "THE AUTHOR'S OWN NOTES" in seen[0] and "Characters (flat 2D" in seen[0] and "DIRECTION: A cart of mangoes" in seen[1]
    assert " ".join(b["narration"] for c in lesson["chapters"] for b in c["beats"]) == said


def test_a_table_given_one_row_per_line_and_a_labelled_script_read_the_same_way():
    rows = [("1", "0:00", "A mango on a plate.", "Narrator: Yeh ek mango hai, aur hum ise do equal parts mein kaatenge abhi."),
            ("2", "0:20", "The mango splits in two.", "Har part ko one half kehte hain, kyunki do equal parts hain yahan.")]
    tabbed = "Scene\tTime\tVisual\tVoiceover\n" + "\n".join("\t".join(r) for r in rows)
    piped = "| Scene | Time | Visual | Narration |\n|---|---|---|---|\n" + "\n".join("| " + " | ".join(r) + " |" for r in rows)
    labelled = ("**Scene 1 (0:00–0:20)**\n**Visual:** A mango on a plate.\n**Voiceover:** Yeh ek mango hai, aur hum ise do equal parts "
                "mein kaatenge abhi.\n\n**Scene 2 (0:20–0:40)**\n**Visual:** The mango splits in two.\n**Voiceover:** Har part ko one "
                "half kehte hain, kyunki do equal parts hain yahan.\n")
    expected = ("Yeh ek mango hai, aur hum ise do equal parts mein kaatenge abhi. "
                "Har part ko one half kehte hain, kyunki do equal parts hain yahan.")
    for text in (tabbed, piped):
        parsed = scripted.parse_script(text)
        said, directions = _spoken_and_directions(parsed)
        assert parsed["table"]["rows"] == 2 and said == expected, text[:20]
        assert "A mango on a plate." in " ".join(directions) and "The mango splits in two." in " ".join(directions)
    parsed = scripted.parse_script(labelled)
    said, directions = _spoken_and_directions(parsed)
    assert parsed["table"] is None and said == expected and "Scene" not in said and "Visual" not in said
    assert [s["title"] for s in parsed["sections"]] == ["Scene 1", "Scene 2"] and directions[0] == "A mango on a plate."
    # an ordinary script that merely mentions these words is not a table
    assert scripted.parse_script(PLAIN)["table"] is None and scripted.parse_script(SCRIPT)["table"] is None
    # labels that are also ordinary sentence openers count only with the colon straight after them
    kept = scripted.parse_script("Time to begin: take one roti and cut it into two equal parts with your hands today.\n"
                                 "Answer: one half\nShow me which part is bigger when the same roti is cut into four equal parts now.")
    said, _ = _spoken_and_directions(kept)
    assert said.startswith("Time to begin: take one roti") and "Answer" not in said and "Show me which part" in said


# ── any other structured document: a reader model labels lines, code cuts the words ──

SCREENPLAY = """FRACTIONS AT THE FRUIT STALL
INT. MARKET - DAY
A cart of mangoes rolls in. Meera waves at her uncle.
VO: Aaj Meera apne uncle ke stall par hai, aur aaj woh fractions seekhegi.
The mango splits into two halves on the board.
VO: Ek mango ko do equal parts mein kaato, to har part one half hai.
TEACHER NOTE: pause here and ask the class.
VO: Ab usi mango ko four equal parts mein kaato, to har part one fourth hai.
"""


def test_a_structured_document_is_read_by_the_reader_model_and_its_reading_is_used_only_when_it_gains(tmp_path, monkeypatch):
    from lessonforge.harness import script_reader
    monkeypatch.setenv("LESSONFORGE_HOME", str(tmp_path))
    monkeypatch.setenv("HARNESS_SCRIPT_READER", "1")
    calls = []
    read = {"script": ("[A cart of mangoes rolls in. Meera waves at her uncle.]\nAaj Meera apne uncle ke stall par hai, aur aaj woh "
                       "fractions seekhegi.\n\n[The mango splits into two halves on the board.]\nEk mango ko do equal parts mein kaato, "
                       "to har part one half hai.\n\nAb usi mango ko four equal parts mein kaato, to har part one fourth hai.\n"),
            "title": "Fractions at the fruit stall", "notes": "INT. MARKET - DAY", "teacher": "pause here and ask the class.",
            "questions": [], "report": {"words": 74, "spoken_words": 40}}
    monkeypatch.setattr(script_reader, "default_llm", lambda: (lambda prompt, system: {}))
    monkeypatch.setattr(script_reader, "read", lambda text, llm, log=print: (calls.append(text), read)[1])
    parsed = scripted.parse_script(SCREENPLAY)
    said, directions = _spoken_and_directions(parsed)
    assert parsed["reading"] == {"words": 74, "spoken_words": 40} and parsed["table"] is None and parsed["title"] == "Fractions at the fruit stall"
    assert said.startswith("Aaj Meera apne uncle ke stall par hai") and "cart of mangoes" not in said and "TEACHER" not in said and "INT." not in said
    assert "A cart of mangoes rolls in." in directions[0] and parsed["language"] == "hinglish" and "INT. MARKET" in parsed["notes"]
    untitled = {**read, "title": "", "script": "# Scene 1\n" + read["script"]}
    monkeypatch.setattr(script_reader, "read", lambda text, llm, log=print: untitled)
    assert scripted.parse_script(SCREENPLAY.replace("Meera", "Tara"))["title"] == ""          # "Scene 1" is not a title
    monkeypatch.setattr(script_reader, "read", lambda text, llm, log=print: (calls.append(text), read)[1])
    # the read-back says how it was read, and the same document is not paid for twice
    view = scripted.preview(SCREENPLAY)
    assert any("reader model picked out the spoken lines" in n for n in view["notes"]) and view["words"] == len(said.split())
    assert scripted.prepare({"mode": "script", "script": SCREENPLAY})["topic"] == "Fractions at the fruit stall" and len(calls) == 1
    # a script this module already reads (headings, [directions], "Visual:" lines) gains nothing: it stays as it was
    monkeypatch.setattr(script_reader, "read", lambda text, llm, log=print: {"script": text, "report": {"words": 1}})
    assert scripted.parse_script(SCRIPT)["reading"] is None
    # a table is read by its columns and the model is never asked; plain narration is never shown to it either
    monkeypatch.setattr(script_reader, "read", lambda text, llm, log=print: pytest.fail("the reader was asked"))
    assert scripted.parse_script(TABLE)["table"]["rows"] == 3 and scripted.parse_script(PLAIN)["reading"] is None
    # a reader that fails, or one that is switched off, leaves the plain reading
    monkeypatch.setattr(script_reader, "read", lambda text, llm, log=print: (_ for _ in ()).throw(TimeoutError("no answer")))
    other = SCREENPLAY.replace("Meera", "Asha")
    assert scripted.parse_script(other)["reading"] is None and "cart of mangoes" in _spoken_and_directions(scripted.parse_script(other))[0]
    monkeypatch.setenv("HARNESS_SCRIPT_READER", "0")
    assert scripted.parse_script(SCREENPLAY.replace("Meera", "Rani"))["reading"] is None


def test_a_whole_drawings_printed_labels_can_be_a_steps_focus_and_nothing_else_can():
    """A typeset drawing (a circuit, a ladder) has no parts to light, but its printed labels are found and read
    (harness/typeset.py): the director is told their names, a step that names one keeps it, and the figure gets them."""
    ready = {"ask": "A simple circuit", "shown": "whole", "file": "/lib/circuit/whole.png", "parts": [], "names": {},
             "points": {"bulb": {"name": "Bulb", "box": [0.45, 0.05, 0.55, 0.15]},
                        "Direction of current, clockwise": {"name": "Direction of current", "box": [0.0, 0.4, 0.3, 0.5]},
                        "panel2": {"name": "not a label", "box": [0, 0, 1, 1]}, "bad": {"name": "x"}}}
    note = scripted._picture_note(ready)
    assert '"bulb" (Bulb)' in note and '"direction_of_current_clo" (Direction of current)' in note and "not a label" not in note
    lesson = {"chapters": [{"beats": [{"id": "01", "figure": {"kind": "diagram"}, "steps": [
        {"say": "a", "show": "The bulb", "focus": "bulb"}, {"say": "b", "show": "Which way", "focus": "Direction_of_current_clockwise"},
        {"say": "c", "show": "The switch", "focus": "switch"}, {"say": "d", "show": "Plain"}]}]}]}
    scripted.place_picture(lesson, ready, log=lambda *_: None)
    beat = lesson["chapters"][0]["beats"][0]
    assert beat["figure"]["kind"] == "picture" and set(beat["figure"]["points"]) == {"bulb", "direction_of_current_clo"}
    assert beat["figure"]["points"]["bulb"]["box"] == [0.45, 0.05, 0.55, 0.15]
    assert [s.get("focus") for s in beat["steps"]] == ["bulb", "direction_of_current_clo", None, None]   # "switch" is not on the drawing
    # without printed labels nothing changes: no focus survives on a whole picture
    plain = {"chapters": [{"beats": [{"id": "01", "figure": {"kind": "diagram"}, "steps": [{"say": "a", "show": "x", "focus": "bulb"}]}]}]}
    scripted.place_picture(plain, {k: v for k, v in ready.items() if k != "points"}, log=lambda *_: None)
    assert "points" not in plain["chapters"][0]["beats"][0]["figure"] and "focus" not in plain["chapters"][0]["beats"][0]["steps"][0]
    assert "Give no \"focus\"" in scripted._picture_note({k: v for k, v in ready.items() if k != "points"})


def test_a_panel_brought_in_during_one_chapter_is_still_there_in_the_next():
    """The triangle lesson, rendered again with its second panel put back (2026-10-10): the parallelogram came in chapter 4
    and was gone when chapter 5 opened, because each chapter is a render of its own and opens on the first panel."""
    def picture():
        return {"kind": "picture", "file": "/library/triangle/whole.png", "panels": ["p1.png", "p2.png"], "panel_boxes": [[0, 0, 5, 5], [6, 0, 9, 5]],
                "points": {}}

    def beat(beat_id, focus=None, figure=True):
        return {"id": beat_id, "figure": picture() if figure else None, "steps": [{"show": "x", "kind": "point", "say": "x", "focus": focus}]}
    lesson = {"chapters": [{"id": 1, "beats": [beat("01")]},
                           {"id": 2, "beats": [beat("02"), beat("03", "panel2"), beat("04")]},
                           {"id": 3, "beats": [beat("05"), beat("06", figure=False)]},
                           {"id": 4, "beats": [beat("07", "panel2")]}]}
    said = []
    assert scripted.whole_once_brought_in(lesson, log=said.append) == ["/library/triangle/whole.png"]
    has = {b["id"]: "panels" in (b["figure"] or {}) for c in lesson["chapters"] for b in c["beats"]}
    # up to the end of the chapter that brings it in, nothing changes; from the next chapter on the drawing is whole
    assert has == {"01": True, "02": True, "03": True, "04": True, "05": False, "06": False, "07": False}
    assert "shown whole in the chapters after" in said[0]
    never = {"chapters": [{"id": 1, "beats": [beat("01")]}, {"id": 2, "beats": [beat("02")]}]}
    assert scripted.whole_once_brought_in(never, log=said.append) == [] and len(said) == 1      # nobody asked: writer.settle_panels' case


GEOMETRY = """# Opposite sides

## Meet it
This is a parallelogram, ABCD. Its opposite sides are parallel.

## The diagonal
Draw the diagonal AC. Now we have two triangles, ABC and CDA.
"""


def test_a_shape_figure_keeps_its_shape_from_the_brief_or_from_the_director():
    """2026-10-26: the director's answer had nowhere to declare shapes, so every "shape" figure named a shape that
    did not exist and a parallelogram lesson rendered as words only."""
    points = {"ABCD": {"points": {"A": [2, 5], "B": [9, 5], "C": [8, 1], "D": [1, 1]}, "polygon": "ABCD", "is": ["parallelogram"]}}
    prompts = []

    def model(prompt, system, declare=False):
        if system is scripted.PLAN_SYSTEM:
            return {"title": "Opposite sides", "chapters": []}
        prompts.append(prompt)
        asked = prompt.split("these beats, every one of them:")[1].split("JSON shape")[0]
        ids = [line[1:3] for line in asked.splitlines() if line.startswith("[")]
        return {**({"shapes": points} if declare else {}),
                "beats": [{"id": i, "visual": "the parallelogram", "figure": {"kind": "shape", "use": "ABCD", "segments": ["AC"]},
                           "steps": [{"say": "parallelogram", "show": "ABCD", "kind": "key"}]} for i in ids]}

    given = scripted.script_lesson(scripted.prepare({"mode": "script", "script": GEOMETRY, "shapes": points}), model,
                                   log=lambda *_: None)
    assert given["chapters"][0]["beats"][0]["figure"]["points"]["B"] == [9, 5]
    assert "SHAPES ALREADY DECLARED" in prompts[0] and '"ABCD"' in prompts[0]
    drawn = scripted.script_lesson(scripted.prepare({"mode": "script", "script": GEOMETRY}),
                                   lambda p, s: model(p, s, declare=True), log=lambda *_: None)
    assert drawn["chapters"][1]["beats"][0]["figure"]["points"]["B"] == [9, 5]


def test_a_figures_points_are_not_mistaken_for_an_unfilled_gap():
    from lessonforge.harness import shapes
    fig = {"kind": "shape", "points": {"A": [1, 1], "B": [4, 1]}, "caption": "AB"}
    assert not shapes.unfilled({"chapters": [{"beats": [{"narration": "Side AB.", "figure": fig}]}]})
    assert shapes.unfilled({"chapters": [{"beats": [{"narration": "Angle D is {angle D} degrees.", "figure": fig}]}]})


def test_latex_braces_are_not_mistaken_for_an_unfilled_gap():
    from lessonforge.harness import shapes
    fig = {"kind": "shape", "points": {"A": [0, 0], "B": [4, 0], "C": [4, 3]}, "draw": [["A", "B", "C"]]}
    latex = r"$\angle \text{ BAC } = \frac{1}{2} \cdot 60^{\circ}$"
    assert not shapes.unfilled({"chapters": [{"beats": [{"narration": "Look.", "steps": [{"show": latex}],
                                                           "figure": fig}]}]})
    filled, issues, _ = shapes.fill_text(r"$\text{ BAC } = {angle BAC}^{\circ}$", fig)
    assert issues == [] and r"\text{ BAC }" in filled and "{angle BAC}" not in filled
