"""The writer is told what a finished drawing HOLDS, read from the drawing itself (card.add_holds, 2026-10-11).

It had been told what the drawing was ASKED for and wrote "faint squares" and "a six centimetre base" over a drawing
that prints b and h. Written again with the list, the same lesson pointed at nothing the drawing lacks (four such
places before, none after: vision_review.findings_of). Without a reading the writer's blocks are what they were.
"""
from lessonforge.harness import card, vision_review

PARTS = {"ask": "a labelled diagram of a green plant", "manifest": "/library/plant/manifest.json", "shown": "parts", "parts": ["sunlight", "water"]}
WHOLE = {"ask": "a triangle and the same triangle joined to its copy", "manifest": "/library/tri/manifest.json", "shown": "whole",
         "file": "/library/tri/whole.png", "panels": ["p1.png", "p2.png"]}
HELD = {"things": ["blue triangle on the left", "dashed line inside left triangle"], "print": ["b", "h"]}


def test_without_a_reading_the_writers_blocks_are_what_they_were():
    for ready, block in ((PARTS, card.diagram_block), (WHOLE, card.picture_block)):
        assert card.holds_block(ready) == ""
        assert "WHAT IS IN IT" not in block(ready)
        assert block(ready) == block({**ready, "holds": None}) == block({**ready, "holds": {}})


def test_with_a_reading_the_writer_gets_the_list_and_the_rule_that_goes_with_it():
    for ready, block in ((PARTS, card.diagram_block), (WHOLE, card.picture_block)):
        told = block({**ready, "holds": HELD})
        assert told.startswith(block(ready))                 # the reading is added at the end; nothing before it changes
        added = told[len(block(ready)):]
        assert "blue triangle on the left; dashed line inside left triangle" in added and "“b”; “h”" in added
        assert "ONLY if it is in this list" in added and "imagine, draw or try" in added
    assert "Nothing is printed in it" in card.holds_block({"holds": {"things": ["a sun"], "print": []}})


def test_the_drawing_is_read_once_as_the_lesson_will_show_it(monkeypatch):
    read = []

    def holds(figure, llm_call=None, log=print):
        read.append(figure)
        return dict(HELD)
    monkeypatch.setattr(vision_review, "holds", holds)
    monkeypatch.setenv("HARNESS_PICTURE_HOLDS", "1")
    whole, parts = dict(WHOLE), dict(PARTS)
    assert card.add_holds(whole, log=lambda *a: None) and card.add_holds(parts, log=lambda *a: None)
    assert read == [{"kind": "picture", "file": "/library/tri/whole.png"}, {"kind": "diagram", "manifest": "/library/plant/manifest.json"}]
    assert whole["holds"] == parts["holds"] == HELD
    assert card.add_holds(whole, log=lambda *a: None) and len(read) == 2          # it has its reading: nobody looks again
    # no drawing, a drawing nobody could read, and the switch
    monkeypatch.setattr(vision_review, "holds", lambda *a, **k: None)
    unread = dict(PARTS)
    assert not card.add_holds(None) and not card.add_holds(unread, log=lambda *a: None) and "holds" not in unread
    def falls_over(*a, **k):
        raise RuntimeError("no judge")
    monkeypatch.setattr(vision_review, "holds", falls_over)                      # a reading can never cost the card
    assert not card.add_holds(dict(PARTS), log=lambda *a: None)
    monkeypatch.setattr(vision_review, "holds", holds)
    monkeypatch.setenv("HARNESS_PICTURE_HOLDS", "0")
    assert not card.add_holds(dict(PARTS), log=lambda *a: None) and len(read) == 2
