"""A person in the loop (harness/edit.py): a script read back, changed by hand, and only what was changed made again."""
import pytest

from lessonforge.harness import edit, scripted

SCRIPT = """# Finding the ladder

A ladder leans on a wall. Its foot is 4 metres from the wall and it reaches 3 metres up. How long is the ladder?

## The working
Square each leg: 4 squared is 16 and 3 squared is 9. Add them and you get 25.

The square root of 25 is 5, so the ladder is 5 metres long.
"""


def lesson():
    brief = scripted.prepare({"mode": "script", "script": SCRIPT, "audience": "Class 8"})
    made = scripted.plain_lesson(brief, log=lambda *_: None)
    return made, brief


def ids(made):
    return [b["id"] for c in made["chapters"] for b in c["beats"]]


def test_the_script_reads_back_with_its_words_screens_and_review_notes():
    made, _ = lesson()
    first = ids(made)[0]
    view = edit.editable(made, {"findings": [{"severity": "major", "beat": first, "what": "the root is not explained"}]})
    assert view["beats"] == len(ids(made)) and view["words"] == sum(len(b["narration"].split())
                                                                   for c in made["chapters"] for b in c["beats"])
    beat = view["chapters"][0]["beats"][0]
    assert beat["id"] == first and beat["narration"].startswith("A ladder leans") and beat["findings"] == ["[major] the root is not explained"]


def test_edits_are_checked_before_anything_is_started():
    made, _ = lesson()
    first, *rest = ids(made)
    assert edit.clean(made, None) == {}
    # the same words again are not an edit; a beat named "beat-1" is beat 01
    same = made["chapters"][0]["beats"][0]["narration"]
    assert edit.clean(made, {first: {"narration": same}}) == {}
    assert edit.clean(made, {f"beat-{int(first)}": {"note": "  show   the ladder  "}}) == {first: {"note": "show the ladder"}}
    for bad, why in (({"99": {"remove": True}}, "no beat"), ({first: {"narration": "  "}}, "nothing to say"),
                     ({first: {"narration": "word " * 500}}, "at most"),
                     ({b: {"remove": True} for b in ids(made)}, "at least one must stay")):
        with pytest.raises(edit.EditError, match=why):
            edit.clean(made, bad)


def test_new_words_are_spoken_exactly_and_the_rest_of_the_lesson_is_untouched():
    made, brief = lesson()
    first, second, *rest = ids(made)
    edits = edit.clean(made, {first: {"narration": "A ladder rests against a wall, four metres out and three metres up. "
                                                   "What is its length?"}, second: {"remove": True}})
    out, summary = edit.apply(made, edits, brief, llm=None, log=lambda *_: None)
    assert summary["words"] == [first] and summary["removed"] == [second]
    assert ids(out) == [first, *rest]
    beat = out["chapters"][0]["beats"][0]
    assert beat["narration"].startswith("A ladder rests against a wall") and beat["steps"]
    assert all(s["say"] == "" or s["say"].lower() in beat["narration"].lower() for s in beat["steps"])
    untouched = {b["id"]: b for c in made["chapters"] for b in c["beats"]}
    assert all(b == untouched[b["id"]] for c in out["chapters"] for b in c["beats"] if b["id"] != first)
    assert out["edited"] and made["chapters"][0]["beats"][0]["narration"].startswith("A ladder leans")   # source kept


def test_a_note_has_the_screen_designed_again_without_touching_a_word():
    made, brief = lesson()
    first = ids(made)[0]
    asked = []

    def director(prompt, system):
        asked.append(prompt)
        assert system is scripted.DIRECT_SYSTEM and "DIRECTION: use a right triangle" in prompt
        return {"beats": [{"id": first, "visual": "a right triangle", "narration": "a model may not say this",
                           "figure": {"kind": "right_triangle", "a": 4, "b": 3, "unknown": "c"},
                           "steps": [{"say": "A ladder leans", "show": "Find the ladder", "kind": "key"}]}]}

    out, summary = edit.apply(made, edit.clean(made, {first: {"note": "use a right triangle"}}), brief,
                              llm=director, log=lambda *_: None)
    beat = out["chapters"][0]["beats"][0]
    assert len(asked) == 1 and summary["screens"] == [first]
    assert beat["figure"]["kind"] == "right_triangle" and beat["visual"] == "a right triangle"
    assert beat["narration"] == made["chapters"][0]["beats"][0]["narration"]


def test_a_director_that_fails_leaves_the_old_screen():
    made, brief = lesson()
    first = ids(made)[0]

    def broken(prompt, system):
        raise RuntimeError("no answer")

    out, summary = edit.apply(made, {first: {"note": "anything"}}, brief, llm=broken, log=lambda *_: None)
    assert summary["screens_kept"] == [first] and out["chapters"][0]["beats"][0]["steps"] == made["chapters"][0]["beats"][0]["steps"]
