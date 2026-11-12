"""A reviewer's rewrite may change a beat's words, not what the beat shows and asks."""
from lessonforge.harness import critic, writer

BUS = ("Ab moving bus mein khade passenger ko sochiye. Bus suddenly stop hoti hai, aur passenger ke feet floor par hain. "
       "Upper body forward jayega ya backward? Passenger kis taraf jhukega?")


def lesson():
    beat = {"id": "11", "narration": BUS, "thinking_pause_seconds": 4,
            "figure": {"kind": "scene", "describe": "A bus moving right with one standing passenger; the bus stops while the "
                                                    "passenger's feet move backward with the bus and the upper body continues forward"},
            "quiz": {"question": "Stopping bus mein passenger kis taraf jhukega?", "options": ["forward", "backward"], "answer_index": 0},
            "steps": [{"say": "moving bus", "show": "Bus stops", "kind": "point", "highlight": False}]}
    return {"title": "Inertia", "brief": {"language": "hinglish", "audience": "Class 9"}, "chapters": [{"beats": [beat]}]}


def test_a_rewrite_that_swaps_the_example_is_refused():
    made, logs = lesson(), []
    box = ("Ab ek box rough floor par sliding kar raha hai, aur sirf ek horizontal force, friction, us par lag raha hai. "
           "Box ki motion dekhiye. Pehle apna answer choose kijiye: box chalti rahegi ya ruk jayegi?")
    report = {"edits": [{"beat": "11", "narration": box}]}
    critic.apply_edits(made, report, log=logs.append)
    assert made["chapters"][0]["beats"][0]["narration"] == BUS and report["edits_applied"] == []
    assert any("picture" in line for line in logs)


def test_a_rewrite_about_the_same_picture_is_applied():
    made = lesson()
    better = ("Ab bus mein khade passenger ko dekhiye. Bus achanak stop hoti hai, lekin passenger ke feet floor ke saath hain. "
              "Upper body forward jayega ya backward? Passenger kis taraf jhukega?")
    report = {"edits": [{"beat": "11", "narration": better}]}
    critic.apply_edits(made, report, log=lambda *_: None)
    assert report["edits_applied"] == ["11"] and "achanak" in made["chapters"][0]["beats"][0]["narration"]


def test_a_beat_without_a_scene_or_question_is_free_to_change():
    beat = {"id": "02", "narration": "Square numbers ko dekhiye aur unke factors likhiye, phir pairs banaiye aur check kijiye.",
            "steps": [{"say": "Square numbers", "show": "Pairs", "kind": "point"}]}
    assert not critic.leaves_its_picture(beat, "Yeh bilkul alag sentence hai jo kisi aur cheez ke baare mein hai.")


def test_the_reviser_is_shown_the_picture_and_the_question():
    seen = []

    def llm(prompt, system):
        seen.append((prompt, system))
        return {"edits": []}
    critic.revise(lesson(), [{"beat": "11", "severity": "major", "what": "cluttered"}], llm, log=lambda *_: None)
    prompt, system = seen[0]
    assert "PICTURE (will not change): A bus moving right" in prompt and "QUESTION card (will not change)" in prompt
    assert "never swap the beat's example" in system


def test_short_words_stay_words_in_a_maths_step():
    assert writer.mathify("1/2 is larger") == "1/2\\text{ is larger}"
    assert writer.mathify("x in A") == "x in A"                       # a lone "in" between symbols is left to the maths
    assert writer.mathify("Right angle = 90^\\circ") == "\\text{Right angle }= 90^\\circ"
    # a lesson made on 2026-10-12 showed "VbyIconstant": a lone "by" or "is" between two symbols lost its spaces in maths
    assert writer.mathify("V by I constant") == "V\\text{ by }I \\text{ constant}"
    assert writer.mathify("x is 5") == "x\\text{ is }5"
    # ... and a word before a one-letter symbol kept no space after it: "2. Make i equal r" was set "Makeiequalr"
    assert writer.mathify("2. Make i equal r") == "2.\\text{ Make } i \\text{ equal } r"
    assert writer.mathify("i and r") == "i \\text{ and } r"


def test_a_rewritten_line_of_working_is_cleaned_as_the_writers_own_lines_are():
    """A lesson made on 2026-10-12 showed "180 − 50 = 130degrees": the reviewer's rewrite of the beat brought its own
    steps, and they went on screen without the cleaning ``writer.discipline`` gives a writer's (words in a line of
    working set as words; a note about the screen dropped)."""
    made = {"title": "Angles", "brief": {"language": "en-IN"}, "chapters": [{"beats": [{
        "id": "07", "narration": "Start with one hundred eighty degrees. Take away fifty, then seventy. Angle A is sixty degrees.",
        "steps": [{"say": "Start with", "show": "Find angle A", "kind": "point", "highlight": False}]}]}]}
    report = {"edits": [{"beat": "07", "narration": "Start with one hundred eighty degrees. Take away fifty, and then take away seventy. "
                                                    "So angle A is sixty degrees.",
                         "steps": [{"say": "Start with", "show": "Start with 180 degrees", "kind": "point"},
                                   {"say": "Take away fifty", "show": "180 - 50 = 130 degrees", "kind": "math"},
                                   {"say": "take away seventy", "show": "The answer stays on screen", "kind": "point"},
                                   {"say": "angle A is", "show": "\\angle A=60^\\circ", "kind": "point"}]}]}
    critic.apply_edits(made, report, log=lambda *a: None)
    steps = made["chapters"][0]["beats"][0]["steps"]
    assert [(s["kind"], s["show"]) for s in steps] == [("point", "Start with 180 degrees"), ("math", "180 - 50 = 130\\text{ degrees}"),
                                                       ("math", "\\angle A=60^\\circ")]
    same = writer.mathify(writer.one_line_math("180 - 50 = 130 degrees"))
    assert steps[1]["show"] == same
