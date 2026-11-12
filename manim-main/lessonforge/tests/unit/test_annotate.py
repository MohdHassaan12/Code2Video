"""The annotation harness on top of a drawing's SVG: what a teacher's hand adds while talking (no render, no model).

The owner, 2026-10-12: "the visual is not matching audio … we can't able to see the 30 deg 40 deg"; "there should be an
annotation harness on top of the SVG which will ideate the annotations, not just stale text"; "intelligent enough to
update and change so it is not giving bad annotations or overlapping things … starting and ending time stamps for
synchrony … extendable for any topics". ``harness/annotate.py`` has the framework; tests/integration films it.
"""
import json

import pytest

from lessonforge.harness import annotate, sequence
from lessonforge.longform import figures, runtime

from test_drawn_with_words import lesson, proof


@pytest.fixture
def board():
    return annotate.Board({"width": 1280, "height": 960, "parts": proof()})


def test_the_numbers_a_voice_says_are_read_as_numbers():
    said = annotate.spoken_numbers("Fifty, sixty, or seventy degrees? Suppose it is thirty-five; a straight angle is one hundred eighty, and 2.5 cm.")
    assert said == {"50", "60", "70", "35", "180", "2.5"}                    # three options are three numbers, not one hundred and ten
    assert annotate.spoken_numbers("iska angle forty degrees hai, aur side six cm") == {"40", "6"}
    assert annotate.spoken_numbers("one thousand eight hundred, two thousand and five, aur twelve thousand") == {"1800", "2005", "12000"}
    assert annotate.spoken_numbers("one thousand seven hundred sixty-four ladoos") == {"1764"}


def test_writing_goes_to_the_clearest_place_and_further_off_on_a_leader_when_every_near_place_is_taken(board):
    letter = board.parts[4]["box"]                                           # the printed "2" at the angle at B
    prims, box, side = board.write("50°", letter, [])
    assert [p["shape"] for p in prims] == ["text"] and 0 <= box[0] < box[2] <= 1 and 0 <= box[1] < box[3] <= 1
    assert board.clutter(box, []) < 55                                       # not on the drawing's words, and inside the picture
    # every place round the letter is taken by marks that stand: it is written further off and tied to its letter
    w, h = box[2] - box[0], box[3] - box[1]
    cx, cy = (letter[0] + letter[2]) / 2, (letter[1] + letter[3]) / 2
    crowd = [[cx - 3 * w, cy - 4 * h, cx + 3 * w, cy + 4 * h]]
    prims, far, side = board.write("50°", letter, crowd)
    assert side == "away" and [p["shape"] for p in prims] == ["path", "text"] and prims[0]["thin"]
    assert annotate._overlap(far, crowd[0]) == 0


def ideas(board, answer, narrations=None, drawn_at=None, log=None):
    moments = {1: ("01", 0), 2: ("01", 1), 3: ("02", 0), 4: ("02", 1)}
    narrations = narrations or {"01": "A triangle has fifty degrees at B. What could angle A be: sixty or seventy?",
                                "02": "Draw a line through A, parallel to the base. The angle beside it is fifty degrees too."}
    return annotate.honest(answer, board, moments, narrations, {"01": set(), "02": set()}, drawn_at if drawn_at is not None else {2: 3, 4: 4},
                           log=log or (lambda *a: None)), moments


def test_an_idea_is_kept_only_when_code_can_stand_behind_it(board):
    # things of the test drawing: #1 the triangle, #2 the dashed line (drawn at S3), #3 the arc at B, #4 the arc beside the line (S4)
    said = []
    kept, _ = ideas(board, {
        "heard": [{"at": "S1", "says": "fifty degrees at B", "value": "50°", "measures": "#3"},
                  {"at": "S2", "says": "sixty or seventy", "value": "60°", "measures": "#3", "open": True},       # only asked: not written
                  {"at": "S1", "says": "fifty degrees", "value": "45°", "measures": "#3"},                         # a number nobody says
                  {"at": "S4", "says": "fifty degrees too", "value": "50°", "measures": "#4"},
                  {"at": "S2", "says": "angle A", "value": "?", "measures": "#9"},                                  # no such thing
                  {"at": "S1", "says": "a triangle", "value": "big", "measures": "#1"}],                           # a value with no number
        "add": [{"at": "S3", "do": "trace", "on": "#2", "says": "a line through A"},
                {"at": "S1", "do": "ring", "on": "#2", "says": "a triangle"},                                      # not on the board at S1
                {"at": "S3", "do": "ring", "on": "#1", "says": "the base"},                                        # a second gesture at one step
                {"at": "S2", "do": "arrow", "on": "#3", "text": "this is a very long note indeed", "says": "angle"},
                {"at": "S2", "do": "sparkle", "on": "#1"},
                {"at": "S4", "do": "equal", "on": ["#3", "#4"], "says": "is fifty degrees too"}]}, log=said.append)
    assert [(i["at"], i["kind"], i["text"], i["tags"]) for i in kept] == [
        (1, "value", "50°", [3]), (3, "trace", "", [2]), (4, "value", "50°", [4]), (4, "equal", "", [3, 4])]
    assert kept[0]["say"] == "fifty degrees at B" and kept[1]["say"] == "a line through A"       # the words it comes with are the voice's own
    assert [i["id"] for i in kept] == ["m1", "m2", "m3", "m4"] and "7 idea(s) not taken" in said[0]


def test_a_mark_that_claims_two_things_are_equal_needs_words_that_say_so(board):
    # "Angles in a Triangle", 2026-10-12: the stroke that means EQUAL was put on two parallel lines, for the words "the
    # two lines stay the same distance apart". A mark that makes a claim comes with a sentence that makes it (Kind.heard,
    # Kind.never); a fair "is fifty degrees too" still passes (the test above).
    said = []
    narrations = {"01": "A triangle has fifty degrees at B.",
                  "02": "Draw a line through A, parallel to the base: the two lines stay the same distance apart. The angle beside it equals the angle at B."}
    kept, _ = ideas(board, {"add": [{"at": "S3", "do": "equal", "on": ["#1", "#2"], "says": "lines stay the same distance apart"},
                                    {"at": "S4", "do": "equal", "on": ["#3", "#4"], "says": "equals the angle at B"},
                                    {"at": "S4", "do": "equal", "on": ["#3", "#4"], "says": "words nobody says"}]}, narrations=narrations, log=said.append)
    assert [(idea["kind"], idea["tags"], idea["say"]) for idea in kept] == [("equal", [3, 4], "equals the angle at B")]
    assert said and said[0].count("the voice does not say what this mark says") == 2
    assert annotate._sentence_of("stay the same", narrations["02"]).startswith("Draw a line") and annotate._sentence_of("nowhere", narrations["02"]) == ""
    assert "never on parallel lines" in annotate.ideate_system()                # ... and the hand is told so


def test_an_angle_given_as_two_lines_is_written_at_the_drawings_own_mark_when_it_has_one(board):
    # A small model gave every angle of a ray diagram as "the angle between these two lines", and the hand drew a second
    # arc beside the printed one, seven times (2026-10-12). Where exactly one mark of the drawing rests on both lines,
    # the value belongs at that mark.
    resting = [m for m, thing in enumerate(board.things, 1) if not thing["big"]
               and all(sequence._rests_on(thing, board.things[t - 1], board.aspect) for t in (1, 2))]
    kept, _ = ideas(board, {"heard": [{"at": "S4", "says": "fifty degrees too", "value": "50°", "measures": ["#1", "#2"]}]})
    if len(resting) == 1:                                                    # the test drawing's arc beside the line rests on both
        assert [(i["kind"], i["tags"]) for i in kept] == [("value", resting)]
    else:
        assert [(i["kind"], i["tags"]) for i in kept] == [("angle", [1, 2])]
    assert resting, "the test drawing is expected to have a mark between the triangle and the dashed line"


def test_a_value_said_before_its_mark_is_drawn_makes_the_hand_draw_the_mark_but_not_before_the_lines_it_stands_on(board):
    # the arc beside the line (#4) is planned for S4; the voice gives its value at S3, when the line itself is drawn
    kept, moments = ideas(board, {"heard": [{"at": "S3", "says": "a line through A", "value": "50°", "measures": "#4"}]},
                          narrations={"01": "A triangle.", "02": "Draw a line through A: fifty degrees beside it."})
    assert kept[0]["pull"] and kept[0]["at"] == 3
    # ... and when the voice gives it in the very first sentence, before the line: it waits for the line (S3), it does not hang in the air
    kept, moments = ideas(board, {"heard": [{"at": "S1", "says": "fifty degrees", "value": "50°", "measures": "#4"}]},
                          narrations={"01": "The angle beside the line will be fifty degrees.", "02": "Draw a line through A."})
    assert kept[0]["pull"] and kept[0]["at"] == 3
    marks, pulls = annotate.lay_out(board, kept, moments, {"01": 1, "02": 2})
    assert pulls == {("02", 0): [6, 7]} and marks[("02", 0)][0]["needs"] == [6]


def test_what_is_written_belongs_to_its_part_of_the_lesson_and_one_value_stands_at_a_thing(board):
    kept, moments = ideas(board, {"heard": [{"at": "S1", "says": "fifty degrees at B", "value": "50°", "measures": "#3"},
                                            {"at": "S2", "says": "sixty", "value": "60°", "measures": "#3"},
                                            {"at": "S4", "says": "fifty degrees too", "value": "50°", "measures": "#4"}],
                                  "add": [{"at": "S2", "do": "ring", "on": "#3", "says": "angle A"}]})
    marks, _ = annotate.lay_out(board, kept, moments, {"01": 1, "02": 2})
    first, second = marks[("01", 0)], marks[("01", 1)]
    assert first[0]["slot"] == second[0]["slot"] == "value:3" and first[0]["life"] == "stays"       # the new value takes the old one's place
    assert second[1]["kind"] == "ring" and second[1]["life"] == "beat" and second[1]["slot"] == ""
    # the next chapter begins: what stood is wiped at its first step (a mark with nothing to draw)
    wipe = marks[("02", 0)][0]
    assert wipe["slot"] == "value:3" and wipe["prims"] == []
    states = annotate.states(marks, moments)
    assert [len(standing) for _, standing, _ in states] == [1, 1, 0, 1]
    # A value of the old case never stands beside one of the new ("40°" beside the last part's "30°", then "35°" beside
    # the "40°" it had just replaced: Laws of Reflection on film). The wipe at a part's first step stays a wipe when a new
    # value comes at that place a moment later, and a "?" that replaces a standing value comes with the new case's value.
    thing, other = board.things[2], board.things[3]
    idea = lambda n, at, of, tag, words, say: {"id": n, "at": at, "kind": "value", "things": [of], "tags": [tag], "text": words, "pull": False, "say": say}     # noqa: E731
    marks, _ = annotate.lay_out(board, [idea("m1", 1, thing, 3, "30°", "thirty"), idea("m2", 1, other, 4, "30°", "thirty too"),
                                        idea("m3", 2, thing, 3, "35°", "thirty-five"), idea("m4", 2, other, 4, "?", "predict the other"),
                                        idea("m5", 3, thing, 3, "40°", "forty"), idea("m6", 3, other, 4, "?", "which label")],
                            {1: ("01", 0), 2: ("01", 1), 3: ("02", 0)}, {"01": 1, "02": 2}, log=lambda *a: None)
    assert [(m["text"], m["say"]) for m in marks[("01", 1)]] == [("35°", "thirty-five"), ("?", "thirty-five")]      # with the new case, not later
    opening = marks[("02", 0)]
    assert [(m["slot"], bool(m["prims"])) for m in opening[:2]] == [("value:3", False), ("value:4", False)]         # both wiped as the part begins
    assert [(m["text"], m["say"]) for m in opening[2:]] == [("40°", "forty"), ("?", "which label")]                 # nothing stale stands: its own words
    # every primitive is a path or a piece of text, in shares of the drawing
    for step in marks.values():
        for mark in step:
            for prim in mark["prims"]:
                assert prim["shape"] in ("path", "text")
                points = prim.get("points") or [prim["box"][:2], prim["box"][2:]]
                assert all(-0.05 <= x <= 1.05 and -0.05 <= y <= 1.05 for x, y in points)


def test_code_measures_what_is_wrong_and_a_look_that_makes_it_worse_stands_aside(board, tmp_path):
    from PIL import Image
    Image.new("RGBA", (400, 300), (0, 0, 0, 0)).save(tmp_path / "whole.png")
    kept, moments = ideas(board, {"heard": [{"at": "S1", "says": "fifty degrees at B", "value": "50°", "measures": "#3"}],
                                  "add": [{"at": "S3", "do": "trace", "on": "#2", "says": "a line through A"}]})
    chapters = {"01": 1, "02": 1}
    marks, pulls = annotate.lay_out(board, kept, moments, chapters)
    assert annotate.problems(board, marks, moments) == []
    # writing put on the drawing's own words is found
    bad = json.loads(json.dumps({f"{k[0]}|{k[1]}": v for k, v in marks.items()}))
    moved = {tuple([k.split("|")[0], int(k.split("|")[1])]): v for k, v in bad.items()}
    moved[("01", 0)][0]["prims"] = [annotate._text(list(board.words[0]), "50°")]
    assert [p["what"] for p in annotate.problems(board, moved, moments)] == ["on the drawing's own words"]
    # ... and what a viewer would see as wrong is not put on the drawing: the value's place is left empty, the rest stays
    said = []
    seen, still = annotate.seen_right(board, moved, moments, log=said.append)
    assert still == [] and seen[("01", 0)][0]["prims"] == [] and seen[("01", 0)][0]["life"] == "stays" and "1 mark(s) left out" in said[0]
    assert [m["kind"] for step in seen.values() for m in step if m["prims"]] == ["trace"]
    assert annotate.seen_right(board, marks, moments)[0] is marks                    # nothing wrong: nothing touched
    # the look: one mark called pointless is dropped; one moved to another thing is placed again
    asked = []

    def look(prompt, system, image):
        asked.append(prompt)
        return {"marks": {"m2": {"is": "pointless"}, "m1": {"is": "wrong_thing", "on": "#4"}, "m9": {"is": "pointless"}}}
    again, _ = annotate.improve(tmp_path, board, kept, marks, pulls, moments, chapters, ["BEAT 01 …"], look, log=lambda *a: None)
    assert "m1: at S1, with the words “fifty degrees at B”: value “50°” on #3" in asked[0]
    assert [m["kind"] for step in again.values() for m in step] == ["value"] and again[("01", 0)][0]["on"] == [4]
    assert [i["id"] for i in kept] == ["m1"]
    # nobody answers, or an answer that changes nothing: the marks stand as they are
    kept2, _ = ideas(board, {"heard": [{"at": "S1", "says": "fifty degrees at B", "value": "50°", "measures": "#3"}]})
    marks2, pulls2 = annotate.lay_out(board, kept2, moments, chapters)
    for answer in (None, {}, {"marks": {"m1": {"is": "ok"}}}):
        assert annotate.improve(tmp_path, board, kept2, marks2, pulls2, moments, chapters, [], lambda *a: answer, log=lambda *a: None)[0] is marks2


def the_drawing(tmp_path, monkeypatch):
    from PIL import Image
    folder = tmp_path / "a_triangle-0123456789"
    folder.mkdir()
    Image.new("RGBA", (400, 300), (0, 0, 0, 0)).save(folder / "whole.png")
    made = {"version": sequence.VERSION, "of": "x", "width": 1280, "height": 960, "parts": proof(), "faithful": True}
    monkeypatch.setattr(sequence, "sequence", lambda where, log=print: made)
    monkeypatch.setenv("HARNESS_ANNOTATE", "1")                              # off in every other test (tests/conftest.py)
    return folder


def test_a_lessons_steps_are_given_what_a_hand_adds(tmp_path, monkeypatch):
    folder = the_drawing(tmp_path, monkeypatch)
    made = lesson(folder)
    made["chapters"][1]["beats"][0]["narration"] = "Draw a line through A, parallel to the base. The angle beside it is fifty degrees too."
    made["chapters"][1]["beats"][0]["steps"][0]["draw"] = [2, 3]             # the plan: the line comes at "Line through A" …
    made["chapters"][1]["beats"][0]["steps"][1]["draw"] = [6, 7]             # … and the angle beside it one step later
    asked = []

    def look(prompt, system, image):
        asked.append((prompt, system))
        if "check a teacher's annotations" in system:
            return {"marks": {"m1": {"is": "ok"}}}
        return {"heard": [{"at": "S1", "says": "fifty degrees at B", "value": "50°", "of": "the angle at B", "measures": "#3", "open": False},
                          {"at": "S3", "says": "Draw a line through A", "value": "50°", "of": "the angle beside the line", "measures": "#4"}],
                "add": [{"at": "S3", "do": "trace", "on": "#2", "says": "a line through A"}]}
    summary = annotate.for_lesson(made, look=look, log=lambda *a: None)
    assert summary == {"drawings": 1, "annotated": 1, "marks": 3, "wrong": 0}
    steps = {(b["id"], i): s for c in made["chapters"] for b in c["beats"] for i, s in enumerate(b["steps"])}
    value = steps[("01", 0)]["annotate"][0]
    assert value["kind"] == "value" and value["say"] == "fifty degrees at B" and value["life"] == "stays" and value["needs"] == [4]
    # the chapter's wipe, the line gone over, the value beside the new angle: and that angle is drawn WITH its value now
    assert [(m["kind"], bool(m["prims"])) for m in steps[("02", 0)]["annotate"]] == [("value", False), ("value", True), ("trace", True)]
    assert steps[("02", 0)]["draw"] == [2, 3, 6, 7] and "draw" not in steps[("02", 1)]
    # the model is told the kinds from the registry, the things with when they are drawn, and the words with their moments
    prompt, system = asked[0]
    assert all(f'"{kind.name}"' in system for kind in annotate.GESTURES) and "(drawn at S3)" in prompt and "S3, when the voice says" in prompt
    assert len(asked) == 2                                                   # ideas, then one look at its own annotated drawing
    # asked once: a lesson whose steps already carry marks is left as it is; and it can be switched off
    assert annotate.for_lesson(made, look=look, log=lambda *a: None)["annotated"] == 0 and len(asked) == 2
    monkeypatch.setenv("HARNESS_ANNOTATE", "0")
    assert annotate.for_lesson(lesson(folder), look=look, log=lambda *a: None)["drawings"] == 0


def test_no_ideas_is_no_change_and_a_drawing_a_pen_cannot_follow_is_left_alone(tmp_path, monkeypatch):
    folder = the_drawing(tmp_path, monkeypatch)
    for answer in (None, {}, {"heard": [], "add": []}, {"heard": [{"at": "S1", "value": "99°", "measures": "#3"}]}):
        made = lesson(folder)
        was = json.dumps(made, sort_keys=True)
        assert annotate.for_lesson(made, look=lambda *a: answer, log=lambda *a: None)["annotated"] == 0
        assert json.dumps(made, sort_keys=True) == was

    def fails(*a):
        raise RuntimeError("no model")
    assert annotate.for_lesson(lesson(folder), look=fails, log=lambda *a: None)["annotated"] == 0
    monkeypatch.setattr(sequence, "sequence", lambda where, log=print: {"parts": proof(), "faithful": False, "width": 1280, "height": 960})
    assert annotate.for_lesson(lesson(folder), look=lambda *a: 1 / 0, log=lambda *a: None)["annotated"] == 0


def test_a_new_kind_of_mark_is_one_entry(board, monkeypatch):
    """The framework's promise: a kind brings its line for the model and its own placing; nothing else changes."""
    def place_star(board, things, text, taken, prefer=""):
        anchor, _ = board.anchor(things[0])
        return [annotate._path([(anchor[0], anchor[1]), (anchor[2], anchor[3])])]
    star = annotate.Kind("star", 1, "", "beat", "put a star on the thing the lesson is about", place_star)
    monkeypatch.setitem(annotate.KINDS, "star", star)
    monkeypatch.setattr(annotate, "GESTURES", annotate.GESTURES + [star])
    assert '"star": put a star on the thing the lesson is about' in annotate.ideate_system()
    kept, moments = ideas(board, {"add": [{"at": "S1", "do": "star", "on": "#1", "says": "A triangle"}]})
    marks, _ = annotate.lay_out(board, kept, moments, {"01": 1, "02": 1})
    assert marks[("01", 0)][0]["kind"] == "star" and marks[("01", 0)][0]["prims"][0]["shape"] == "path"


def test_every_kind_places_itself_inside_the_picture(board):
    from test_drawn_with_words import line as points_of, part
    triangle, line, arc_b, arc_a = board.things
    slanted = {"main": part(20, "stroke", points_of((.3, .7), (.6, .3))), "marks": [], "labels": [], "big": True, "numbers": [20]}    # crosses the dashed line
    for kind in annotate.KINDS.values():
        things = [line, slanted] if kind.name == "angle" else [arc_b, arc_a] if kind.things == 2 else [line if kind.name in ("span", "trace") else arc_b]
        text = "6 cm" if kind.name == "span" else "50°" if kind.says == "value" else "this one" if kind.says == "words" else ""
        prims = kind.place(board, things, text, [])
        assert prims, kind.name
        for prim in prims:
            points = prim.get("points") or [prim["box"][:2], prim["box"][2:]]
            assert all(-0.02 <= x <= 1.02 and -0.02 <= y <= 1.02 for x, y in points), kind.name


def test_a_mark_comes_with_its_own_words_never_before_what_it_stands_on_and_a_gesture_has_time_to_be_seen():
    scene = runtime.GuidedChapter.__new__(runtime.GuidedChapter)
    scene.beat_start, scene.current = 100.0, {"duration": 20.0}
    times = {"thirty degrees": (2.0, "aligned"), "the normal": (19.6, "aligned"), "fifty": (6.0, "aligned")}
    scene.locate = lambda phrase, after=0.0: times.get(phrase)
    mark = lambda kind, say, **more: {"id": say, "kind": kind, "say": say, "life": "stays" if kind == "value" else "beat",      # noqa: E731
                                      "slot": "value:6" if kind == "value" else "", "prims": [{"shape": "text"}], **more}
    steps = [{"annotate": [{"id": "", "slot": "value:9", "life": "stays", "prims": []}]},
             {"draw": [7], "annotate": [mark("value", "thirty degrees", needs=[7]), mark("ring", "the normal")]},
             {"annotate": [mark("value", "fifty"), mark("value", "nowhere said")]}]
    due = [101.0, 108.0, 112.0]
    got = [(round(at, 2), m["id"], how) for at, m, how in scene._marks_due(steps, due)]
    assert got[0] == (100.05, "", "step")                                    # the last part's value is wiped as the beat begins
    assert (108.6, "thirty degrees", "words") in got                         # said at 102, but its arc is drawn at 108: it waits for it
    assert (112.0, "nowhere said", "step") in got                            # no words of its own: with its step
    assert ("fifty" in [g[1] for g in got]) and [g for g in got if g[1] == "fifty"][0][0] > 108.6      # one slot keeps its order
    assert [g for g in got if g[1] == "the normal"][0][0] == 118.1           # 1.4 s before the beat's end, not 0.4

    # "Drawn" means the pen has finished. The figure says how long a step's parts take, and a drawing that arrives in
    # this beat is being drawn until ``settled``: a ring came a second and a half into "Why Water Pushes Up" and hung in
    # the empty place where the stone was drawn two seconds later.
    class Pen:
        pen_seconds = staticmethod(lambda numbers: 2.2)
    steps = [{"annotate": [mark("ring", "the stone", needs=[3])]},                      # part 3 is there when the drawing arrives
             {"draw": [7], "annotate": [mark("value", "thirty degrees", needs=[7])]}]
    times.update({"the stone": (1.5, "aligned")})
    got = {m["id"]: round(at, 2) for at, m, how in scene._marks_due(steps, [101.0, 108.0], Pen, settled=104.6)}
    assert got == {"the stone": 104.6, "thirty degrees": 110.2}              # after the arrival's pen-work; after the step's
    got = {m["id"]: round(at, 2) for at, m, how in scene._marks_due(steps, [101.0, 108.0], Pen)}
    assert got["the stone"] == round(101.5 - runtime.CUE_LEAD, 2)            # a drawing that stands already: with its words
    # A gesture has time to be seen before the hand goes elsewhere, and one that writes words time to be read: an arrow
    # with "motion: right" was up for 1.1 s before a ring took its place (Friction, 2026-10-12).
    times.update({"motion right": (2.0, "aligned"), "wooden floor": (2.4, "aligned"), "sand paper": (2.6, "aligned")})
    steps = [{"annotate": [mark("arrow", "motion right", text="motion: right"), mark("ring", "wooden floor"), mark("ring", "sand paper")]}]
    got = [round(at, 2) for at, m, how in scene._marks_due(steps, [101.0])]
    assert got[1] - got[0] == pytest.approx(runtime.GuidedChapter.WORDS_SECONDS) and got[2] - got[1] == pytest.approx(runtime.GuidedChapter.GESTURE_LEAST)


def test_a_gesture_is_not_drawn_through_what_is_written(board, monkeypatch):
    # "Why Water Pushes Up", 2026-10-12: a ring round the displaced water ran through the "2 units" written beside it at
    # that very step; in "Laws of Reflection" a ring round each angle ran through its "30°".
    import dataclasses
    assert annotate._through([{"shape": "path", "points": [[.1, .5], [.9, .5]]}], [[.4, .45, .6, .55]])
    assert not annotate._through([{"shape": "path", "points": [[.1, .5], [.9, .5]], "soft": True}], [[.4, .45, .6, .55]])      # a see-through pass may
    assert not annotate._through([{"shape": "path", "points": [[.1, .44], [.9, .44]]}], [[.4, .45, .6, .55]])                 # a line that only grazes it
    thing = board.things[2]                                                  # the arc at B
    moments, chapters, said = {1: ("01", 0), 2: ("01", 1)}, {"01": 1}, []
    value = {"id": "m1", "at": 1, "kind": "value", "things": [thing], "tags": [3], "text": "50°", "pull": False, "say": ""}
    ring = {"id": "m2", "at": 2, "kind": "ring", "things": [thing], "tags": [3], "text": "", "pull": False, "say": ""}
    marks, _ = annotate.lay_out(board, [value, ring], moments, chapters, log=said.append)
    assert [m["kind"] for m in marks[("01", 1)]] == ["ring"] and not said    # on this drawing the ring clears the value: it is made
    x0, y0, x1, y1 = next(prim["box"] for prim in marks[("01", 0)][0]["prims"] if prim["shape"] == "text")
    across = [{"shape": "path", "points": [[x0 - .05, (y0 + y1) / 2], [x1 + .05, (y0 + y1) / 2]]}]
    # a ring that would run through the value is left out, and the log says so
    monkeypatch.setitem(annotate.KINDS, "ring", dataclasses.replace(annotate.KINDS["ring"], place=lambda *a: across))
    marks, _ = annotate.lay_out(board, [value, ring], moments, chapters, log=said.append)
    assert ("01", 1) not in marks and "run through what is written" in said[0]
    # and where one stands all the same (a look by the model moved something), code counts it as wrong
    stands = {"id": "m9", "slot": "", "kind": "ring", "life": "beat", "say": "", "text": "", "on": [3], "needs": [], "prims": across}
    found = annotate.problems(board, {("01", 0): marks[("01", 0)], ("01", 1): [stands]}, moments)
    assert {"id": "m9", "what": "through what the hand has written", "step": 2} in found


def test_a_mark_that_leaves_is_not_drawn_back_in_by_its_own_unfinished_animation(monkeypatch):
    """An arrow's words ("motion: right") stood on the picture long after the hand had moved on (Friction, 2026-10-12):
    the next gesture came 1.1 s after it, while its own drawing-in (1.3 s) was still being stepped, and every later
    frame went on fading in the words the figure had just hidden. What is half drawn is finished BEFORE anything leaves."""
    from types import SimpleNamespace
    monkeypatch.setattr(runtime, "STILLS", False)
    scene = runtime.GuidedChapter.__new__(runtime.GuidedChapter)
    scene.renderer, scene._beat_layout, scene._mark_records = SimpleNamespace(time=100.0), {}, []
    scene.add = scene.remove = scene.bring_to_back = lambda *a, **k: None
    log = []

    class Drawing:                                       # an animation that takes 1.3 s and shows its mark while it runs
        run_time = 1.3

        def __init__(self, name):
            self.name, self.done = name, False

        def begin(self):
            log.append(f"{self.name} begins")

        def interpolate(self, alpha):
            if not self.done:
                seen.add(self.name)                      # drawing a mark in makes it seen

        def finish(self):
            self.done = True
            log.append(f"{self.name} finished")

    seen = set()

    class Figure:
        left = []

        def prepare_marks(self, marks):
            pass

        def annotate(self, marks, now=False):
            running = [a.name for a in made if not a.done]
            assert not running, f"{running} still being drawn in while a mark changes"
            self.left = [gesture[0]] if gesture else []
            for name in self.left:
                seen.discard(name)                       # the figure hides what leaves
            gesture[:] = [marks[0]["id"]]
            made.append(Drawing(marks[0]["id"]))
            return [made[-1]]

        def clear_gesture(self):
            assert all(a.done for a in made)
            self.left = list(gesture)
            for name in self.left:
                seen.discard(name)
            gesture.clear()

    gesture, made = [], []
    mark = lambda name: {"id": name, "kind": "arrow", "life": "beat", "slot": "", "text": name, "prims": [{"shape": "text"}]}      # noqa: E731
    driver, tick, finish = scene._start_marks(Figure(), [(100.5, mark("first"), "words"), (101.6, mark("second"), "words")])
    for frame in range(1, 151):                          # five seconds at 30 frames a second
        scene.renderer.time = 100.0 + frame / 30
        tick(None, 1 / 30)
    assert "first" not in seen and log.index("first finished") < log.index("second begins")
    assert [m["id"] for m in scene._beat_layout["annotations"]] == ["first", "second"] and scene._beat_layout["annotations"][0]["end"] is not None


def test_what_a_hand_wrote_earlier_stands_when_a_later_chapter_opens(tmp_path):
    made = lesson(tmp_path / "d")
    stays = lambda slot, text: {"id": text, "slot": slot, "life": "stays", "kind": "value", "prims": [{"shape": "text"}] if text else []}   # noqa: E731
    made["chapters"][0]["beats"][0]["steps"][0]["annotate"] = [stays("value:3", "50°"), {"id": "g", "slot": "", "life": "beat", "prims": [{}]}]
    made["chapters"][1]["beats"][0]["steps"][0]["annotate"] = [stays("value:4", "60°")]
    scene = runtime.GuidedChapter.__new__(runtime.GuidedChapter)
    scene.lesson = made
    second = made["chapters"][1]["beats"][0]
    assert [m["id"] for m in scene._annotated_before(second["figure"], second)] == ["50°"]          # the value, not the gesture
    assert scene._annotated_before({"kind": "picture", "file": "/another/whole.png"}, second) == []


def test_the_picture_draws_a_hands_marks_and_only_a_drawing_shown_whole_can_take_them(tmp_path):
    from PIL import Image
    file = tmp_path / "whole.png"
    Image.new("RGB", (400, 300), "white").save(file)
    fig = figures.PictureFigure(file)
    value = {"id": "m1", "slot": "value:3", "life": "stays", "prims": [{"shape": "text", "box": [.4, .4, .5, .46], "text": "30°"}]}
    ring = {"id": "m2", "slot": "", "life": "beat", "prims": [{"shape": "path", "points": [[.2, .2], [.3, .2], [.3, .3]], "closed": True}]}
    arrow = {"id": "m3", "slot": "", "life": "beat", "prims": [{"shape": "path", "points": [[.6, .6], [.7, .7]], "arrow": True}]}
    assert len(fig.annotate([value, ring])) == 2 and fig.left == []
    box = fig._notes["value:3"][1]
    assert abs(box.get_center()[0] - (fig.art.get_left()[0] + .45 * fig.art.width)) < .02          # where the harness put it, in the picture's own frame
    assert fig.annotate([arrow], now=True) == [] and fig.left == ["m2"]                           # the hand is in one place at a time
    newer = {**value, "id": "m4", "prims": [{"shape": "text", "box": [.4, .4, .5, .46], "text": "40°"}]}
    fig.annotate([newer], now=True)
    assert fig.left == ["m1"] and fig._notes["value:3"][0] == "m4"                                # one value stands at a thing
    fig.annotate([{**value, "id": "", "prims": []}], now=True)
    assert fig._notes == {} and fig.left == ["m4"]                                                # a wipe
    fig.clear_gesture()
    assert fig.left == ["m3"] and fig._gesture is None
    drawn = figures.build({"kind": "right_triangle", "a": 3, "b": 4, "unknown": "c"})
    assert not hasattr(drawn, "annotate") and not hasattr(drawn, "clear_gesture")                 # asked by name: no other figure has these


def test_steps_written_again_keep_what_a_hand_wrote(tmp_path):
    was = lesson(tmp_path / "d")
    was["chapters"][1]["beats"][0]["steps"][1]["annotate"] = [{"id": "m1", "slot": "value:4", "life": "stays", "prims": [{}]}]
    now = json.loads(json.dumps(was))
    now["chapters"][1]["beats"][0]["steps"] = [{"say": "Draw a line", "show": "One parallel line", "kind": "point"}]
    assert sequence.keep_draws(now, was) == 1
    assert now["chapters"][1]["beats"][0]["steps"][0]["annotate"][0]["id"] == "m1"


def test_every_filmed_mark_has_its_start_and_end_on_the_lessons_clock(tmp_path):
    # The owner, 2026-10-12: "the starting and ending time stamps for synchrony". The film's own record, per chapter,
    # brought to one clock; a mark that stays ends when its place is written again or wiped, else with the lesson.
    text = lambda words: [{"shape": "text", "box": [.1, .1, .2, .2], "text": words}]                             # noqa: E731
    figure = {"kind": "picture", "file": "/x/a_drawing-123/whole.png"}
    stays = lambda n, slot, words: {"id": n, "slot": slot, "kind": "value", "life": "stays", "say": "", "text": words, "on": [6], "prims": text(words) if words else []}      # noqa: E731
    ring = {"id": "m2", "slot": "", "kind": "ring", "life": "beat", "say": "", "text": "", "on": [3], "prims": [{"shape": "path", "points": [[.1, .1], [.2, .2]]}]}
    lesson_ = {"chapters": [
        {"id": 1, "beats": [{"id": "01", "figure": figure, "steps": [{"annotate": [stays("m1", "value:6", "30°"), ring]}, {"annotate": [stays("m3", "value:7", "30°")]}]}]},
        {"id": 2, "beats": [{"id": "02", "figure": figure, "steps": [{"annotate": [stays("", "value:6", ""), stays("m4", "value:7", "40°")]}]},
                            {"id": "03", "figure": figure, "steps": [{"annotate": [stays("m5", "value:6", "never filmed")]}]}]}]}
    (tmp_path / "output").mkdir()
    (tmp_path / "lesson.json").write_text(json.dumps(lesson_), encoding="utf-8")
    (tmp_path / "timeline.json").write_text(json.dumps([{"id": "01", "start": 0.0, "duration": 20.0}, {"id": "02", "start": 20.0, "duration": 10.0},
                                                        {"id": "03", "start": 30.0, "duration": 10.0}]), encoding="utf-8")
    record = lambda n, kind, words, start, end: {"id": n, "kind": kind, "text": words, "start": start, "end": end, "with": "words"}       # noqa: E731
    (tmp_path / "output" / "chapter_01_audit.json").write_text(json.dumps({"bounds": [{"beat": "01", "layout": {"annotations": [
        record("m1", "value", "30°", 2.0, None), record("m2", "ring", "", 2.5, 7.0), record("m3", "value", "30°", 9.0, None)]}}]}), encoding="utf-8")
    (tmp_path / "output" / "chapter_02_audit.json").write_text(json.dumps({"bounds": [
        {"beat": "02", "layout": {"annotations": [record("m4", "value", "40°", 3.0, None)]}}, {"beat": "03", "layout": {}}]}), encoding="utf-8")
    made = annotate.timed(tmp_path, log=lambda *a: None)
    got = {(m["beat"], m["id"]): (m["start"], m["end"]) for m in made["marks"]}
    assert got == {("01", "m1"): (2.0, 20.05),          # wiped as the next part begins (chapter 2's clock starts at 20 s)
                   ("01", "m2"): (2.5, 7.0),            # a gesture: the film's own end
                   ("01", "m3"): (9.0, 23.0),           # replaced by the 40° at the same place
                   ("02", "m4"): (23.0, 40.0)}          # stands to the lesson's end
    assert json.loads((tmp_path / "output" / "annotations.json").read_text())["marks"][0]["prims"] and made["marks"][0]["drawing"] == "a_drawing-123"
    (tmp_path / "output" / "chapter_01_audit.json").write_text(json.dumps({"bounds": []}), encoding="utf-8")
    (tmp_path / "output" / "chapter_02_audit.json").write_text(json.dumps({"bounds": []}), encoding="utf-8")
    assert annotate.timed(tmp_path, log=lambda *a: None) is None             # nothing on film: no file is claimed

