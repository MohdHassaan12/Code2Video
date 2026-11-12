"""The sync repair (longform/sync_repair.py): steps re-anchored on the words heard, kept only when the beat's
schedule is better. No manim render, no model, no network."""
import copy

from lessonforge.longform import sync_repair, timeline_compiler as tc


def sentence(text, start, duration):
    return {"text": text, "start": start, "duration": duration, "timing_source": "measured"}


NARRATION = ("Drop a heavy ball and a light ball together. Both start from rest at the same height. "
             "Watch the two balls land at the same moment. Gravity gives each the same speed every second.")
ENTRY = {"id": "01", "start": 0.0, "duration": 14.0, "speech_end": 13.5, "lead": 0.5,
         "sentences": [sentence("Drop a heavy ball and a light ball together.", 0.5, 3.0),
                       sentence("Both start from rest at the same height.", 3.5, 3.0),
                       sentence("Watch the two balls land at the same moment.", 6.5, 3.0),
                       sentence("Gravity gives each the same speed every second.", 9.5, 4.0)]}


def lesson(steps, frame="stage"):
    beat = {"id": "01", "narration": NARRATION, "visual": "two balls falling", "steps": steps}
    return {"title": "Falling", "look": {"frame": frame},
            "chapters": [{"id": 1, "title": "FALL", "role": "idea", "learning_goal": "g", "beats": [beat]}]}


def issues(made):
    return tc.compile_timeline(made, [ENTRY])["issues"]


def test_a_step_whose_words_are_never_heard_waits_for_its_own_sentence():
    made = lesson([{"say": "drop a heavy", "show": "Heavy and light ball dropped", "kind": "point"},
                   {"say": "never said at all", "show": "Same speed every second", "kind": "key"}])
    assert any(i["check"] == "anchor spoken" for i in issues(made))
    result = sync_repair.repair(made, [ENTRY], log=lambda *_: None)
    assert result["kept"] == ["01"] and result["after"] < result["before"]
    step = made["chapters"][0]["beats"][0]["steps"][1]
    assert tc.locate(ENTRY["sentences"], step["say"]) is not None
    assert step["say"].lower() in "gravity gives each the same speed every second."   # the sentence holding its words
    assert not any(i["check"] == "anchor spoken" for i in issues(made))


def test_two_steps_on_the_same_words_are_pulled_apart_so_each_can_be_read():
    made = lesson([{"say": "heavy ball", "show": "Heavy ball", "kind": "point"},
                   {"say": "ball and", "show": "Light ball beside it falls the same way", "kind": "point"},
                   {"say": "same moment", "show": "Both land together", "kind": "key"}])
    before = {i["check"] for i in issues(made)}
    assert "events crowded" in before
    sync_repair.repair(made, [ENTRY], log=lambda *_: None)
    after = issues(made)
    assert "events crowded" not in {i["check"] for i in after}
    times = [e["time"] for b in tc.compile_timeline(made, [ENTRY])["beats"] for e in b["events"] if e["kind"] == "step"]
    assert times == sorted(times)                      # still in the order they are shown


def test_a_beat_that_cannot_be_made_better_is_left_exactly_as_it_was():
    clean = lesson([{"say": "drop a heavy", "show": "Two balls", "kind": "point"},
                    {"say": "same moment", "show": "Land together", "kind": "key"}])
    kept = copy.deepcopy(clean)
    result = sync_repair.repair(clean, [ENTRY], log=lambda *_: None)
    assert result["tried"] == [] and clean == kept
    # a beat with nothing spoken that could be better: no candidate gives room, so nothing changes
    tight = {**ENTRY, "sentences": [sentence("Drop them.", 0.5, 0.6)], "duration": 1.4, "speech_end": 1.1}
    crowded = lesson([{"say": "drop them", "show": "A", "kind": "point"}, {"say": "drop them", "show": "B", "kind": "point"}])
    before = copy.deepcopy(crowded)
    sync_repair.repair(crowded, [tight], log=lambda *_: None, thin_lines=False)
    assert crowded == before
    # ... and with thinning one of the two lines goes: there is time for one line, not two
    sync_repair.repair(crowded, [tight], log=lambda *_: None)
    assert [s["show"] for s in crowded["chapters"][0]["beats"][0]["steps"]] in (["A"], ["B"])


def test_the_narration_and_what_a_step_shows_are_never_changed():
    made = lesson([{"say": "heavy ball", "show": "Heavy ball", "kind": "point"},
                   {"say": "nowhere", "show": "Same speed every second", "kind": "key", "focus": "ball"}])
    was = copy.deepcopy(made)
    sync_repair.repair(made, [ENTRY], log=lambda *_: None)
    beat, old = made["chapters"][0]["beats"][0], was["chapters"][0]["beats"][0]
    assert beat["narration"] == old["narration"]
    assert [(s["show"], s["kind"], s.get("focus")) for s in beat["steps"]] == \
        [(s["show"], s["kind"], s.get("focus")) for s in old["steps"]]



# ── Thinning: a beat with more lines than its words give time to read ─────────────────────────────────────────
TIGHT = {"id": "01", "start": 0.0, "duration": 6.6, "speech_end": 6.1, "lead": 0.5,
         "sentences": [sentence("Drop a heavy ball and a light ball together.", 0.5, 2.6),
                       sentence("They land at the same moment.", 3.2, 2.9)]}


def tight_issues(made):
    return [i for i in tc.compile_timeline(made, [TIGHT])["issues"] if i["check"] in ("reading time", "events crowded")]


def test_a_last_line_too_long_for_its_time_is_cut_to_its_first_clause_and_the_voice_is_untouched():
    made = lesson([{"say": "drop a heavy", "show": "Heavy and light", "kind": "point"},
                   {"say": "the same moment", "show": "They land together, at exactly one moment", "kind": "key"}])
    words = made["chapters"][0]["beats"][0]["narration"]
    assert tight_issues(made)
    result = sync_repair.repair(made, [TIGHT], log=lambda *_: None)
    beat = made["chapters"][0]["beats"][0]
    assert [s["show"] for s in beat["steps"]] == ["Heavy and light", "They land together"]
    assert beat["narration"] == words and result["thinned"]["01"]
    assert not tight_issues(made)


def test_a_line_that_repeats_another_is_taken_off_before_any_line_is_shortened():
    made = lesson([{"say": "drop a heavy", "show": "Heavy ball, light ball", "kind": "point"},
                   {"say": "a light ball", "show": "Light ball and heavy ball", "kind": "point"},
                   {"say": "the same moment", "show": "Same moment", "kind": "key"}])
    assert tight_issues(made)
    sync_repair.repair(made, [TIGHT], log=lambda *_: None)
    shows = [s["show"] for s in made["chapters"][0]["beats"][0]["steps"]]
    assert len(shows) == 2 and "Same moment" in shows and not tight_issues(made)


def test_lines_that_point_ask_work_or_are_the_only_key_are_never_taken_off():
    steps = [{"say": "drop a heavy", "show": "Heavy ball", "kind": "point", "focus": "ball"},
             {"say": "a light ball", "show": "Light ball too?", "kind": "point"},
             {"say": "light ball together", "show": "m g = m a", "kind": "math"},
             {"say": "the same moment", "show": "Same moment always and everywhere", "kind": "key"}]
    for index in range(len(steps)):
        assert not sync_repair._may_drop(steps, index)
    with_draw = [{"show": "A", "kind": "point", "draw": [3]}, {"show": "B", "kind": "key"}]
    assert not sync_repair._may_drop(with_draw, 0)


def test_a_mark_on_a_line_taken_off_goes_to_its_neighbour():
    beat = {"id": "01", "steps": [{"say": "drop a heavy", "show": "Heavy ball", "kind": "point"},
                                  {"say": "a light ball", "show": "Light ball", "kind": "point",
                                   "annotate": [{"kind": "ring", "say": "light ball"}]},
                                  {"say": "same moment", "show": "Same moment", "kind": "key"}]}
    dropped = [made for _, what, made in sync_repair._edits(beat) if "Light ball" in what and "off" in what][0]
    assert [s["show"] for s in dropped["steps"]] == ["Heavy ball", "Same moment"]
    assert dropped["steps"][0]["annotate"] == [{"kind": "ring", "say": "light ball"}]


def test_thinning_can_be_switched_off():
    made = lesson([{"say": "drop a heavy", "show": "Heavy and light", "kind": "point"},
                   {"say": "the same moment", "show": "They land together, at exactly one moment", "kind": "key"}])
    was = copy.deepcopy(made)
    result = sync_repair.repair(made, [TIGHT], log=lambda *_: None, thin_lines=False)
    assert [s["show"] for s in made["chapters"][0]["beats"][0]["steps"]] == \
        [s["show"] for s in was["chapters"][0]["beats"][0]["steps"]] and not result["thinned"]
