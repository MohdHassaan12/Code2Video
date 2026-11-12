"""The concept knowledge base (``harness/concepts.py``): one explanation per concept, and the picture it is shown with."""
import json

import pytest

from lessonforge.harness import card as teaching_card
from lessonforge.harness import concepts, diagrams


@pytest.fixture
def on(monkeypatch, tmp_path):
    monkeypatch.setenv("HARNESS_CONCEPTS", "1")
    monkeypatch.setenv("LESSONFORGE_HOME", str(tmp_path / "ws"))
    return tmp_path


def test_every_shipped_entry_is_a_card_the_checks_accept(on):
    entries = [e for e in concepts.entries(log=lambda *a: None) if e.get("source") == "curated"]
    assert len(entries) >= 12
    for entry in entries:
        assert entry["id"] and entry["names"] and entry["status"] in concepts.STATUS_RANK
        shaped = teaching_card.shape(entry["card"])
        assert teaching_card.check(shaped, {"chunks": []}) == [], entry["id"]
        picture = entry["picture"]
        assert picture["prefer"] in ("figure", "drawing")
        assert picture["asks"] or isinstance(picture.get("figure"), dict), entry["id"]


def test_a_topic_finds_its_concept_and_only_its_own(on):
    found = lambda topic, **more: (concepts.find({"topic": topic, **more}, log=lambda *a: None) or {}).get("id")  # noqa: E731
    assert found("Pythagoras theorem") == "pythagoras-theorem"
    assert found("photosynthesis") == "photosynthesis"
    assert found("the water cycle", audience="class 6") == "water-cycle"
    # a name must cover most of what was asked: "air pressure" is another lesson than "pressure"
    assert found("air pressure") is None
    # ... and a class far outside the entry's range is no match
    assert found("Pythagoras theorem", audience="class 2") is None
    # off means off
    import os
    os.environ["HARNESS_CONCEPTS"] = "0"
    try:
        assert found("Pythagoras theorem") is None
    finally:
        os.environ["HARNESS_CONCEPTS"] = "1"


def test_an_entry_becomes_the_lessons_card_with_its_picture(on):
    entry = concepts.find({"topic": "Pythagoras theorem"}, log=lambda *a: None)
    made = concepts.as_card(entry, {"topic": "Pythagoras theorem", "audience": "class 8"})
    assert made["concept"] == "pythagoras-theorem" and made["klass"] == 8
    # an exact figure is the picture: the drawing service is not asked, and the writer is told the figure
    assert made["no_drawing"] and made["figure_hint"]["kind"] == "right_triangle" and made["diagram_ask"] == ""
    assert teaching_card.add_diagram(made, {"topic": "Pythagoras theorem"}, log=lambda *a: None) is False
    assert 'THE FIGURE' in teaching_card.for_writer(made)
    water = concepts.as_card(concepts.find({"topic": "water cycle"}, log=lambda *a: None), {"topic": "water cycle"})
    assert water["picture_asks"] and water["diagram_ask"] == water["picture_asks"][0] and "figure_hint" not in water


def test_the_best_picture_is_kept_and_asked_for_again(on, monkeypatch):
    monkeypatch.setattr(diagrams, "available", lambda: True)
    entry = {"id": "toy", "picture": {"asks": ["A labelled diagram of a toy", "A labelled diagram of a toy, side view", "A third"]}}
    drawn = {
        "A labelled diagram of a toy": {"shown": "whole", "judged": {"ok": True}},
        "A labelled diagram of a toy, side view": {"shown": "parts", "parts": [{}] * 5, "judged": {"ok": True}},
        "A third": {"shown": "parts", "parts": [{}] * 8, "judged": {"ok": False}},      # the judge found it wrong
    }
    asked = []

    def prepare(ask):
        asked.append(ask)
        return drawn[ask]
    best = concepts.best_picture(entry, {"topic": "toy"}, log=lambda *a: None, prepare=prepare)
    assert best is drawn["A labelled diagram of a toy, side view"] and len(asked) == 3
    assert concepts.state("toy")["picture"]["ask"] == "A labelled diagram of a toy, side view"
    asked.clear()
    assert concepts.best_picture(entry, {"topic": "toy"}, log=lambda *a: None, prepare=prepare) is best
    assert asked == ["A labelled diagram of a toy, side view"]                # chosen once, then asked for alone
    assert concepts.picture_score(None) == 0 and concepts.picture_score({"shown": "whole"}) == .75


def test_a_passing_lesson_on_a_new_topic_is_kept_and_proven_by_the_next_ones(on):
    card = {"topic": "Magnets attract iron", "asked": "magnets attract iron", "klass": 6,
            "big_idea": {"text": "A magnet pulls iron things towards it."}, "diagram_ask": "A labelled diagram of a bar magnet"}
    passed, failed = {"status": "technical_checks_passed"}, {"status": "failed"}
    quiet = lambda *a: None                                                     # noqa: E731
    assert concepts.record(card, {"topic": "magnets attract iron"}, "j1", failed, log=quiet) == ""     # a failed lesson teaches nothing
    assert concepts.record(card, {"topic": "magnets attract iron"}, "j2", passed, log=quiet) == "learned"
    entry = concepts.find({"topic": "magnets attract iron"}, log=quiet)
    assert entry and entry["status"] == "learned" and entry["source"] == "learned"
    made = concepts.as_card(entry, {"topic": "magnets attract iron"})
    assert made["concept"] == entry["id"]
    assert concepts.record(made, {"topic": "magnets attract iron"}, "j3", passed, log=quiet) == "promoted"
    assert json.loads((concepts.learned_folder() / f"{entry['id']}.json").read_text())["status"] == "proven"
    # learning off: entries are used, nothing new is kept
    import os
    os.environ["HARNESS_CONCEPTS"] = "use"
    try:
        other = {**card, "topic": "Static electricity", "asked": "static electricity"}
        assert concepts.record(other, {"topic": "static electricity"}, "j4", passed, log=quiet) == ""
    finally:
        os.environ["HARNESS_CONCEPTS"] = "1"


def test_the_card_stage_takes_the_entry_and_spends_nothing(on, monkeypatch):
    def no_model(*a, **k):
        raise AssertionError("a concept with an entry must not ask a model for a card")
    monkeypatch.setattr(teaching_card, "make", no_model, raising=False)
    said = []
    made, pack = teaching_card.prepare({"topic": "Pythagoras theorem", "audience": "class 8"}, log=said.append)
    assert made["concept"] == "pythagoras-theorem" and pack["digest"] == "concept:pythagoras-theorem"
    assert any("knowledge base" in line for line in said)
