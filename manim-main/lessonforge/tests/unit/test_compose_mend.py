"""Acting on what the look at a lesson's preview stills finds (harness/compose.mend), and the look itself.

Tried on real lessons on 2026-10-11 with every change read. What came of it is pinned here: the look QUOTES and code
checks the quote; a beat with no picture of its own, spoken over a drawing of something else, is shown without it;
rewriting words is behind its own switch and keeps a beat only when a second look, fault by fault, says it cured
something. No model, no render: the preview and the judge are stand-ins.
"""
import copy

import pytest

from lessonforge.harness import compose, vision_review


# ── the look: findings are built by code from what the judge quotes ───────────────────────────────────────────────

BEAT = {"id": "02", "narration": "That square corner helps us spot the height. This slanted triangle sits on faint squares, "
                                 "with a six centimetre base along the bottom.",
        "steps": [{"kind": "key", "show": "Right angle marks the height"}, {"kind": "point", "show": "Highlight the base in gold"}]}
HELD = {"things": ["blue triangle on the left", "right angle mark in left triangle"], "print": ["b", "h"]}


def test_a_thing_the_words_point_at_is_missing_only_when_the_quote_is_real_and_names_it():
    answer = {"subject": "same", "pointed_at": [
        {"quote": "This slanted triangle sits on faint squares, with a six centimetre base along the bottom",
         "says_is_there": ["slanted triangle", "faint squares", "six centimetre base"], "not_there": ["faint squares", "six centimetre base"]},
        # words nobody wrote: the judge made the sentence up
        {"quote": "look at the red arrow on the left side", "says_is_there": ["red arrow"], "not_there": ["red arrow"]},
        # a thing the quoted words do not name at all
        {"quote": "That square corner helps us spot the height", "says_is_there": ["square corner"], "not_there": ["a ruler"]}]}
    found = vision_review.findings_of(answer, BEAT, HELD)
    assert [(f["kind"], f["thing"]) for f in found] == [("missing", "faint squares"), ("missing", "six centimetre base")]
    assert all("sits on faint squares" in f["quote"] for f in found)


def test_what_the_reading_of_the_drawing_lists_is_never_missing():
    answer = {"pointed_at": [{"quote": "That square corner helps us spot the height",
                              "says_is_there": ["right angle mark"], "not_there": ["right angle mark in the triangle that helps spot height"]}]}
    beat = {**BEAT, "narration": "That right angle mark in the triangle helps us spot the height."}
    answer["pointed_at"][0]["quote"] = "That right angle mark in the triangle helps us spot the height"
    assert vision_review.findings_of(answer, beat, HELD) == []
    assert [f["kind"] for f in vision_review.findings_of(answer, beat, None)] == ["missing"]      # with no reading, the look is believed


def test_a_drawing_of_another_thing_a_note_to_the_animator_and_what_is_only_seen():
    answer = {"subject": "different", "shows": "a foot and a ball", "words_about": "a balloon to blow up",
              "notes": ["highlight the base in gold", "Draw it bigger"],                       # the second is not one of the beat's lines
              "findings": [{"kind": "lonely", "severity": "low", "what": "The drawing is small in an empty frame."},
                           {"kind": "half", "severity": "medium", "what": "The second triangle described in the drawing request has not arrived."},
                           {"kind": "missing", "severity": "high", "what": "The numbers are not in the drawing."}]}
    found = vision_review.findings_of(answer, BEAT, HELD)
    assert [(f["kind"], f["severity"]) for f in found] == [("mismatch", "high"), ("note", "medium"), ("lonely", "low")]
    assert "a foot and a ball" in found[0]["what"] and "a balloon" in found[0]["what"]
    assert found[1]["quote"] == "Highlight the base in gold"


def stills(tmp_path, *beats, without=()):
    """A stand-in preview: one end still per beat (a real file: the look reads it), with or without a picture."""
    folder = tmp_path / "stills"
    folder.mkdir(exist_ok=True)
    made = []
    for chapter, beat in beats:
        name = f"c{chapter:02}_b{beat}_end.jpg"
        (folder / name).write_bytes(b"jpg")
        made.append({"file": name, "chapter": chapter, "beat": beat, "what": "end",
                     "picture": None if beat in without else {"kind": "bars", "share": .3, "fill": 1.0}})
    return {"folder": str(folder), "stills": made, "failed": [], "notes": [], "bounds": [], "layout": [], "findings": []}


def test_the_second_look_answers_fault_by_fault_and_a_fault_it_does_not_answer_is_still_there(tmp_path):
    lesson = {"chapters": [{"id": 1, "beats": [dict(BEAT)]}]}
    before = {"02": [{"kind": "missing", "what": "faint squares"}, {"kind": "missing", "what": "six centimetre base"},
                     {"kind": "missing", "what": "four centimetres"}]}
    asked = []

    def judge(prompt, system, picture):
        asked.append(prompt)
        return {"faults": [{"n": 1, "now": "cured", "because": "no squares are spoken of"}, {"n": 2, "now": "still"}, {"n": "x", "now": "cured"}],
                "new": ["the words now point at a grid", 7]}
    seen = vision_review.recheck(stills(tmp_path, (1, "02")), lesson, before, llm_call=judge, log=lambda *a: None)["02"]
    assert [f["what"] for f in seen["cured"]] == ["faint squares"]
    assert [f["what"] for f in seen["still"]] == ["six centimetre base", "four centimetres"] and seen["new"] == ["the words now point at a grid"]
    assert "1. [missing] faint squares" in asked[0] and "THE NARRATOR SAYS" in asked[0]

    def broken(prompt, system, picture):
        raise RuntimeError("no answer")
    seen = vision_review.recheck(stills(tmp_path, (1, "02")), lesson, before, llm_call=broken, log=lambda *a: None)["02"]
    assert seen["cured"] == [] and len(seen["still"]) == 3      # a change nobody could look at is not kept


def test_the_frame_reviewer_is_told_of_a_beat_shown_without_its_picture():
    lesson = {"chapters": [{"id": 1, "beats": [
        {"id": "01", "figure": {"kind": "picture", "file": "/x/whole.png", "ask": "a foot kicking a ball"}, "steps": []},
        {"id": "02", "picture": "off", "steps": []}]}]}
    timeline = [{"id": "01", "chapter": 1, "start": 0.0, "duration": 4.0, "sentences": []},
                {"id": "02", "chapter": 1, "start": 4.0, "duration": 4.0, "sentences": []}]
    first, second = vision_review.sample_points(timeline, lesson)
    assert first["drawing"] and not first["no_picture"]
    assert second["drawing"] is None and second["no_picture"]


# ── mending ───────────────────────────────────────────────────────────────────────────────────────────────────────

def lesson():
    step = lambda say, show: {"say": say, "show": show, "kind": "point", "highlight": False}          # noqa: E731
    return {"title": "Force pairs", "brief": {"language": "en-IN"}, "chapters": [
        {"id": 1, "role": "concrete", "beats": [
            {"id": "01", "narration": "A foot kicks a ball. The ball pushes back on the foot with an equal force.",
             "figure": {"kind": "bars", "values": [1, 1]}, "steps": [step("A foot kicks", "Foot pushes ball")]},
            {"id": "02", "narration": "Now take a balloon and blow it up. Let it go. Which way does it fly?",
             "thinking_pause_seconds": 4, "steps": [step("take a balloon", "Blow up a balloon")]}]},
        {"id": 2, "role": "practice", "beats": [
            {"id": "03", "narration": "This slanted bar sits on faint squares, and the dashed line marks its height.",
             "figure": {"kind": "bars", "values": [2, 3]}, "steps": [step("This slanted bar", "Bar on squares")]}]}]}


def looked(*rows):
    return {"detail": [{"beat": beat, "shows": "a foot and a ball", "words_about": "a balloon", "findings": list(found)} for beat, found in rows],
            "holds": {}}


OTHER = {"kind": "mismatch", "severity": "high", "what": "the drawing shows a foot and a ball; the words are about a balloon"}
SQUARES = {"kind": "missing", "severity": "medium", "what": "the words point at faint squares, which is not in the drawing"}


def test_how_far_the_look_is_acted_on_is_one_setting(monkeypatch):
    for value, mode in (("0", ""), ("1", "pictures"), ("pictures", "pictures"), ("words", "words"), ("anything else", "")):
        monkeypatch.setenv("HARNESS_COMPOSE_MEND", value)
        assert compose.mending() == mode
    monkeypatch.delenv("HARNESS_COMPOSE_MEND")
    assert compose.mending() == "pictures"                  # rewriting words is never the default (see compose.mending)


def test_a_beat_spoken_over_a_drawing_of_something_else_is_shown_without_it(tmp_path, monkeypatch):
    monkeypatch.setenv("HARNESS_COMPOSE_MEND", "pictures")
    made = lesson()
    previewed = []

    def again(root, work=None, lesson=None, only=None, **_):
        previewed.append(only)
        return stills(tmp_path, (1, "01"), (1, "02"), without=("02",))
    monkeypatch.setattr(compose.preview, "stills", again)
    first = stills(tmp_path, (1, "01"), (1, "02"), (2, "03"))
    said = []
    summary = compose.mend(made, tmp_path, first, looked(("02", [OTHER]), ("03", [OTHER, SQUARES])), judge=lambda *a: {}, log=said.append)
    beats = {b["id"]: b for c in made["chapters"] for b in c["beats"]}
    assert beats["02"]["picture"] == "off" and summary["picture_off"] == summary["kept"] == ["02"] and summary["undone"] == []
    assert previewed == [[1]]                                # only the chapter that changed is previewed again
    # a beat that carries its OWN picture is never left without it, and no word of any beat was touched
    assert "picture" not in beats["03"] and summary["tried"] == ["02"]
    assert [b["narration"] for b in beats.values()] == [b["narration"] for c in lesson()["chapters"] for b in c["beats"]]
    assert summary["changes"]["02"]["what"] == "picture off" and summary["changes"]["02"]["shows"] == "a foot and a ball"
    assert any("shown without the picture" in line for line in said)


def test_a_beat_over_the_lessons_shared_drawing_of_something_else_is_shown_without_it(tmp_path, monkeypatch):
    # The speed lesson: one prepared drawing (a car between start and finish lines) copied onto every beat that uses
    # it, spoken over a scooter and a bus. Each beat "had a picture", so the look's finding was left on screen.
    monkeypatch.setenv("HARNESS_COMPOSE_MEND", "pictures")
    monkeypatch.setenv("HARNESS_COMPOSE_DRAW", "0")
    car = {"kind": "diagram", "file": "library/diagrams/car_on_road/whole.png", "manifest": "m.json"}
    made = lesson()
    for beat_id, parts in (("01", None), ("02", ["car"])):
        beat = made["chapters"][0]["beats"][int(beat_id) - 1]
        beat["figure"] = dict(car, **({"parts": parts} if parts else {}))   # same file, other parts named: same drawing
    monkeypatch.setattr(compose.preview, "stills", lambda *a, **k: stills(tmp_path, (1, "01"), (1, "02"), without=("02",)))
    first = stills(tmp_path, (1, "01"), (1, "02"), (2, "03"))
    summary = compose.mend(made, tmp_path, first, looked(("02", [OTHER]), ("03", [OTHER])), judge=lambda *a: {},
                           log=lambda *a: None)
    beats = {b["id"]: b for c in made["chapters"] for b in c["beats"]}
    assert summary["picture_off"] == ["02"] and beats["02"]["picture"] == "off"
    assert "picture" not in beats["01"]                      # the beat about the car keeps it
    assert "picture" not in beats["03"]                      # a drawing NO other beat carries is still never taken off
    assert compose._shared(lesson()["chapters"]) == set()


def test_a_picture_that_the_preview_still_shows_is_not_called_gone(tmp_path, monkeypatch):
    monkeypatch.setenv("HARNESS_COMPOSE_MEND", "pictures")
    made, as_it_came = lesson(), lesson()
    monkeypatch.setattr(compose.preview, "stills", lambda *a, **k: stills(tmp_path, (1, "01"), (1, "02")))
    summary = compose.mend(made, tmp_path, stills(tmp_path, (1, "01"), (1, "02")), looked(("02", [OTHER])), judge=lambda *a: {}, log=lambda *a: None)
    assert summary["undone"] == ["02"] and summary["kept"] == [] and made == as_it_came
    assert summary["changes"]["02"]["why_not"] == "the drawing is still there"


def test_a_layout_made_worse_or_a_failure_leaves_the_lesson_as_it_came(tmp_path, monkeypatch):
    monkeypatch.setenv("HARNESS_COMPOSE_MEND", "pictures")
    made, as_it_came = lesson(), lesson()
    worse = stills(tmp_path, (1, "01"), (1, "02"), without=("02",))
    worse["bounds"] = [{"chapter": 1, "beat": "02", "type": "Text"}]
    monkeypatch.setattr(compose.preview, "stills", lambda *a, **k: worse)
    summary = compose.mend(made, tmp_path, stills(tmp_path, (1, "01"), (1, "02")), looked(("02", [OTHER])), judge=lambda *a: {}, log=lambda *a: None)
    assert summary["undone"] == ["02"] and summary["changes"]["02"]["why_not"] == "its chapter's layout got worse" and made == as_it_came

    def fails(*a, **k):
        raise RuntimeError("manim fell over")
    monkeypatch.setattr(compose.preview, "stills", fails)
    with pytest.raises(RuntimeError):
        compose.mend(made, tmp_path, stills(tmp_path, (1, "01"), (1, "02")), looked(("02", [OTHER])), judge=lambda *a: {}, log=lambda *a: None)
    assert made == as_it_came


def rewriter(narration, steps=None):
    """A stand-in reviser: one rewrite, of beat 03."""
    return lambda prompt, system: {"edits": [{"beat": "03", "narration": narration, **({"steps": steps} if steps else {})}]}


def test_words_are_rewritten_only_when_asked_for_and_kept_only_when_the_second_look_says_cured(tmp_path, monkeypatch):
    first = stills(tmp_path, (1, "01"), (1, "02"), (2, "03"))
    monkeypatch.setattr(compose.preview, "stills", lambda *a, **k: stills(tmp_path, (1, "01"), (1, "02"), (2, "03")))
    new = "This slanted bar has a dashed line, and the dashed line marks its height."
    cured = lambda prompt, system, picture: {"faults": [{"n": 1, "now": "cured"}], "new": []}             # noqa: E731

    monkeypatch.setenv("HARNESS_COMPOSE_MEND", "pictures")
    made = lesson()
    summary = compose.mend(made, tmp_path, first, looked(("03", [SQUARES])), llm=rewriter(new), judge=cured, log=lambda *a: None)
    assert summary["tried"] == [] and made == lesson()        # pictures only: nobody is asked for words

    monkeypatch.setenv("HARNESS_COMPOSE_MEND", "words")
    made = lesson()
    summary = compose.mend(made, tmp_path, first, looked(("03", [SQUARES])), llm=rewriter(new), judge=cured, log=lambda *a: None)
    beat = made["chapters"][1]["beats"][0]
    assert summary["kept"] == ["03"] and beat["narration"] == new and summary["changes"]["03"]["was"].startswith("This slanted bar sits on faint")
    assert beat["steps"][0]["say"] in new                    # its line is anchored in the new words

    # an author's own script keeps every word, whatever the setting
    made = lesson()
    summary = compose.mend(made, tmp_path, first, looked(("03", [SQUARES])), llm=rewriter(new), judge=cured, keep_words=True, log=lambda *a: None)
    assert summary["tried"] == [] and made == lesson()

    for answer, why in (({"faults": [{"n": 1, "now": "still"}], "new": []}, "nothing it had was cured"),
                        ({"faults": [{"n": 1, "now": "cured"}], "new": ["the words now point at a ruler"]},
                         "its new words speak of something else the drawing lacks")):
        made = lesson()
        summary = compose.mend(made, tmp_path, first, looked(("03", [SQUARES])), llm=rewriter(new), judge=lambda *a, answer=answer: answer,
                               log=lambda *a: None)
        assert summary["undone"] == ["03"] and summary["changes"]["03"]["why_not"] == why and made == lesson()
        assert summary["changes"]["03"]["now"] == new        # what was tried is on record, kept or not


def test_a_rewrite_that_no_longer_ends_on_the_beats_question_is_put_back(tmp_path, monkeypatch):
    monkeypatch.setenv("HARNESS_COMPOSE_MEND", "words")
    made = lesson()
    asking = made["chapters"][1]["beats"][0]
    asking["narration"] = "This slanted bar sits on faint squares. Which line marks its height?"
    asking["thinking_pause_seconds"] = 4
    as_it_came = copy.deepcopy(made)
    monkeypatch.setattr(compose.preview, "stills", lambda *a, **k: stills(tmp_path, (1, "01"), (1, "02"), (2, "03")))
    summary = compose.mend(made, tmp_path, stills(tmp_path, (1, "01"), (1, "02"), (2, "03")), looked(("03", [SQUARES])),
                           llm=rewriter("This slanted bar has a dashed line. That dashed line marks its height."),
                           judge=lambda *a: {"faults": [{"n": 1, "now": "cured"}], "new": []}, log=lambda *a: None)
    assert summary["undone"] == ["03"] and summary["changes"]["03"]["why_not"] == "it no longer ends on its question"
    assert made == as_it_came


# ── a drawing of its own for a beat about another situation (2026-10-12) ──────────────────────────────────────────

def the_service_draws(monkeypatch, *beats, tells=(), fits=True):
    """Stand-ins: the drawing service gives each of ``beats`` a picture; the looks at a new drawing answer as told.
    ``tells``: for each drawing made, in order, whether it tells the answer to the beat's own question."""
    made, answers = [], list(tells)

    def own(lesson, asked, shows, was, stills=None, log=print, avoid=None):
        got = {}
        for chapter in lesson["chapters"]:
            for beat in chapter["beats"]:
                if beat["id"] in asked and beat["id"] in beats:
                    beat.pop("picture", None)
                    beat["figure"] = {"kind": "picture", "file": f"/library/drawn/{beat['id']}_{len(made)}.png", "ask": "a balloon held by its neck"}
                    got[beat["id"]] = "a balloon held by its neck" + (" (again)" if (avoid or {}).get(beat["id"]) else "")
                    made.append((beat["id"], (avoid or {}).get(beat["id"])))
        return got
    monkeypatch.setattr(compose, "drawing", lambda: True)
    monkeypatch.setattr(compose, "_own_drawings", own)
    monkeypatch.setattr(vision_review, "fits", lambda figure, beat, llm_call=None, log=print: {
        "fits": fits, "against": [] if fits else ["a leaf under black paper"], "drawing_shows": "a balloon", "words_describe": "a balloon"})
    monkeypatch.setattr(vision_review, "tells", lambda figure, question, llm_call=None, log=print: {
        "tells": answers.pop(0) if answers else False, "could_tell": ["an arrow labelled predicted direction"]})
    return made


def with_a_beat_after(made):
    """… and a third beat in the first chapter with no picture of its own: until now it showed the foot and the ball."""
    made["chapters"][0]["beats"].append({"id": "02b", "narration": "The foot feels the push too.", "steps": []})
    return made


def test_a_beat_about_another_thing_gets_a_drawing_of_its_own_and_the_next_beat_keeps_what_it_showed(tmp_path, monkeypatch):
    monkeypatch.setenv("HARNESS_COMPOSE_MEND", "pictures")
    drawn = the_service_draws(monkeypatch, "02", tells=[False])
    made = with_a_beat_after(lesson())
    monkeypatch.setattr(compose.preview, "stills", lambda *a, **k: stills(tmp_path, (1, "01"), (1, "02"), (1, "02b")))
    said = []
    summary = compose.mend(made, tmp_path, stills(tmp_path, (1, "01"), (1, "02"), (1, "02b"), (2, "03")), looked(("02", [OTHER])),
                           judge=lambda *a: {}, log=said.append)
    beats = {b["id"]: b for c in made["chapters"] for b in c["beats"]}
    assert summary["drawn"] == summary["kept"] == ["02"] and summary["picture_off"] == [] and drawn == [("02", None)]
    assert beats["02"]["figure"]["kind"] == "picture" and "picture" not in beats["02"]
    # the beat after it had no picture of its own and would now show the balloon: it is given the foot and ball by name
    assert beats["02b"]["figure"] == beats["01"]["figure"] and beats["02b"]["figure"] is not beats["01"]["figure"]
    assert summary["changes"]["02"]["what"] == "own drawing" and summary["changes"]["02"]["ask"] == "a balloon held by its neck"
    assert any("given a drawing of its own" in line for line in said)


def test_a_drawing_that_tells_the_answer_is_asked_for_once_more_and_then_the_picture_is_taken_off(tmp_path, monkeypatch):
    monkeypatch.setenv("HARNESS_COMPOSE_MEND", "pictures")
    first = stills(tmp_path, (1, "01"), (1, "02"), (2, "03"))
    # the second drawing is the set-up only: kept
    drawn = the_service_draws(monkeypatch, "02", tells=[True, False])
    made = lesson()
    monkeypatch.setattr(compose.preview, "stills", lambda *a, **k: stills(tmp_path, (1, "01"), (1, "02")))
    summary = compose.mend(made, tmp_path, first, looked(("02", [OTHER])), judge=lambda *a: {}, log=lambda *a: None)
    assert summary["drawn"] == ["02"] and [avoid for _, avoid in drawn] == [None, "an arrow labelled predicted direction"]
    assert summary["changes"]["02"]["ask"].endswith("(again)")
    # the second tells it too: no drawing of its own; the beat never had a picture, so it is shown without one
    drawn = the_service_draws(monkeypatch, "02", tells=[True, True])
    made = lesson()

    def as_the_lesson_stands(root, work=None, lesson=None, **_):       # a preview shows no picture on a beat marked "off"
        off = [b["id"] for c in lesson["chapters"] for b in c["beats"] if b.get("picture") == "off"]
        return stills(tmp_path, (1, "01"), (1, "02"), without=off)
    monkeypatch.setattr(compose.preview, "stills", as_the_lesson_stands)
    summary = compose.mend(made, tmp_path, first, looked(("02", [OTHER])), judge=lambda *a: {}, log=lambda *a: None)
    beat = made["chapters"][0]["beats"][1]
    assert len(drawn) == 2 and summary["drawn"] == [] and summary["picture_off"] == ["02"] and beat.get("picture") == "off" and "figure" not in beat
    assert summary["changes"]["02"]["what"] == "picture off" and summary["changes"]["02"]["tried_first"]["what"] == "own drawing"
    assert "tells the answer" in summary["changes"]["02"]["tried_first"]["why_not"]


def test_a_drawing_of_the_wrong_thing_is_not_kept_and_a_beat_with_its_own_picture_is_then_left_alone(tmp_path, monkeypatch):
    monkeypatch.setenv("HARNESS_COMPOSE_MEND", "pictures")
    the_service_draws(monkeypatch, "03", fits=False)
    made, as_it_came = lesson(), lesson()
    monkeypatch.setattr(compose.preview, "stills", lambda *a, **k: stills(tmp_path, (2, "03")))
    summary = compose.mend(made, tmp_path, stills(tmp_path, (1, "01"), (1, "02"), (2, "03")), looked(("03", [OTHER])), judge=lambda *a: {},
                           log=lambda *a: None)
    assert summary["drawn"] == [] and summary["undone"] == ["03"] and made == as_it_came
    assert "does not show what the words describe (a leaf under black paper)" in summary["changes"]["03"]["why_not"]


def test_what_a_beat_asks_and_what_every_beat_goes_on_showing():
    assert compose._question({"narration": "Blow it up. Let it go. Which way does it fly? Why?"}) == "Which way does it fly? Why?"
    assert compose._question({"narration": "It flies forward.", "quiz": {"question": "Which way?"}}) == "Which way?"
    assert compose._question({"narration": "It flies forward."}) == ""
    made = with_a_beat_after(lesson())
    before = vision_review._showing(made)
    beats = {b["id"]: b for c in made["chapters"] for b in c["beats"]}
    pinned = set()
    compose._keep_showing(made, before, pinned)
    assert pinned == set() and "figure" not in beats["02"]         # nothing was changed: nothing is given by name
    beats["02"]["figure"] = {"kind": "picture", "file": "/library/drawn/balloon.png"}
    compose._keep_showing(made, before, pinned)
    assert pinned == {"02b"} and beats["02b"]["figure"] == beats["01"]["figure"]
    del beats["02"]["figure"]                                      # the drawing was not kept after all
    compose._keep_showing(made, before, pinned)
    assert pinned == set() and "figure" not in beats["02b"]


def test_the_request_for_a_beats_own_drawing_and_a_beat_the_service_has_nothing_for(monkeypatch):
    from lessonforge.harness import scripted, writer
    made = with_a_beat_after(lesson())
    made["pictures"] = [{"ask": "a foot kicking a ball", "shown": "whole", "beats": ["01"]}]
    was = {b["id"]: copy.deepcopy(b) for c in made["chapters"] for b in c["beats"]}
    seen = {}

    def service(lesson, brief, log=print, stills=None, pointer=None):
        for chapter in lesson["chapters"]:
            for beat in chapter["beats"]:
                figure = beat.get("figure") or {}
                if figure.get("kind") == "scene":
                    seen[beat["id"]] = figure["describe"]
                    if beat["id"] == "02":                  # a drawing for the balloon; nothing for the other beat
                        beat["figure"] = {"kind": "picture", "file": "/library/drawn/balloon.png", "ask": "a balloon held by its neck"}
        lesson["pictures"] = [{"ask": "a balloon held by its neck", "shown": "whole", "beats": ["02"]}]
        return lesson
    monkeypatch.setattr(writer, "drawings_for_scenes", service)
    monkeypatch.setattr(writer, "settle_panels", lambda lesson, **k: lesson)
    monkeypatch.setattr(scripted, "whole_once_brought_in", lambda lesson, **k: [])
    shows = {"02": {"words_about": "a balloon let go"}, "02b": {"words_about": "a foot feeling a push"}}
    got = compose._own_drawings(made, ["02", "02b"], shows, was, log=lambda *a: None, avoid={"02": "an arrow of the motion"})
    beats = {b["id"]: b for c in made["chapters"] for b in c["beats"]}
    assert got == {"02": "a balloon held by its neck"} and beats["02"]["figure"]["kind"] == "picture"
    assert beats["02b"] == was["02b"]                                         # the service had nothing: exactly as it was
    # a beat that ASKS is drawn as its set-up only, and told what the refused drawing gave away; one that states is not
    assert "a balloon let go" in seen["02"] and "never the outcome" in seen["02"] and "an arrow of the motion" in seen["02"]
    assert "a foot feeling a push" in seen["02b"] and "never the outcome" not in seen["02b"]
    # the lesson's record of its pictures keeps the ones it had
    assert [p["beats"] for p in made["pictures"]] == [["01"], ["02"]]


# ── a model-written scene that lacks what its own words point at (the ice lesson, 2026-10-19) ─────────────────────

def ice_lesson():
    return {"title": "Ice", "brief": {"language": "en-IN"}, "chapters": [{"id": 1, "role": "concrete", "beats": [
        {"id": "02", "narration": "Here are two blocks of exactly equal mass, one water and one ice. The ice block looks bigger.",
         "figure": {"kind": "scene", "describe": "Two blocks side by side, both labelled equal mass.", "module": "/old.py"},
         "steps": [{"say": "two blocks of", "show": "Equal mass, two blocks", "kind": "point", "highlight": False}]}]}]}


ICE = {"kind": "missing", "severity": "medium", "quote": "The ice block looks bigger.", "thing": "The ice block",
       "what": "the words point at The ice block, which is not in the drawing"}


def test_a_scene_that_lacks_what_its_words_name_is_written_again_and_kept_only_when_a_second_look_says_cured(tmp_path, monkeypatch):
    from lessonforge.harness import service
    monkeypatch.setenv("HARNESS_COMPOSE_MEND", "pictures")
    monkeypatch.setenv("HARNESS_COMPOSE_SCENES", "1")                  # off by default: see compose.redrawing
    monkeypatch.setattr(compose.preview, "stills", lambda *a, **k: stills(tmp_path, (1, "02")))
    asked = []

    def resolve(trial, log=print, **_):
        for beat in trial["chapters"][0]["beats"]:
            asked.append(beat["figure"]["describe"])
            beat["figure"]["module"] = "/new.py"
    monkeypatch.setattr(service, "resolve_scenes", resolve)
    cured = lambda prompt, system, picture: {"faults": [{"n": 1, "now": "cured"}], "new": []}             # noqa: E731
    made = ice_lesson()
    summary = compose.mend(made, tmp_path, stills(tmp_path, (1, "02")), looked(("02", [ICE])), judge=cured, log=lambda *a: None)
    figure = made["chapters"][0]["beats"][0]["figure"]
    assert summary["kept"] == ["02"] and figure["module"] == "/new.py" and "The ice block" in figure["describe"]
    assert asked and asked[0].startswith("Two blocks side by side, both labelled equal mass") and "looks bigger" in asked[0]
    assert made["chapters"][0]["beats"][0]["narration"] == ice_lesson()["chapters"][0]["beats"][0]["narration"]   # no word changes

    still = lambda prompt, system, picture: {"faults": [{"n": 1, "now": "still"}], "new": []}             # noqa: E731
    made = ice_lesson()
    summary = compose.mend(made, tmp_path, stills(tmp_path, (1, "02")), looked(("02", [ICE])), judge=still, log=lambda *a: None)
    assert summary["undone"] == ["02"] and made == ice_lesson()                                   # not better: as it came

    monkeypatch.setattr(service, "resolve_scenes", lambda trial, log=print, **_: None)          # could not be written
    made = ice_lesson()
    summary = compose.mend(made, tmp_path, stills(tmp_path, (1, "02")), looked(("02", [ICE])), judge=cured, log=lambda *a: None)
    assert made == ice_lesson() and summary["changes"]["02"]["why_not"] == "the scene could not be written again"

    def same(trial, log=print, **_):
        trial["chapters"][0]["beats"][0]["figure"]["module"] = "/old.py"
    monkeypatch.setattr(service, "resolve_scenes", same)                                      # the old scene back
    made = ice_lesson()
    summary = compose.mend(made, tmp_path, stills(tmp_path, (1, "02")), looked(("02", [ICE])), judge=cured, log=lambda *a: None)
    assert made == ice_lesson() and summary["changes"]["02"]["why_not"] == "the same scene came back"

    monkeypatch.setenv("HARNESS_COMPOSE_SCENES", "0")                 # switched off: not drawn again
    made = ice_lesson()
    assert compose.mend(made, tmp_path, stills(tmp_path, (1, "02")), looked(("02", [ICE])), judge=cured,
                        log=lambda *a: None)["tried"] == [] and made == ice_lesson()

    monkeypatch.delenv("HARNESS_COMPOSE_SCENES")                      # the default: drawn again
    monkeypatch.setattr(service, "resolve_scenes", resolve)
    made = ice_lesson()
    assert compose.mend(made, tmp_path, stills(tmp_path, (1, "02")), looked(("02", [ICE])), judge=cured,
                        log=lambda *a: None)["tried"] == ["02"]
