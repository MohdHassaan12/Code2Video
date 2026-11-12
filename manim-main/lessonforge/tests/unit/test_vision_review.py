"""Vision review sampling is deterministic and lands AFTER the key step's cue, not at the beat start."""
from lessonforge.harness import vision_review


def test_sample_points_land_after_the_key_cue_and_carry_the_spoken_sentence():
    lesson = {"chapters": [{"id": 1, "beats": [
        {"id": "01", "steps": [{"say": "three metres", "show": "3 m", "kind": "math", "highlight": False},
                               {"say": "ladder cuts across", "show": "c", "kind": "key", "highlight": True}]},
        {"id": "02", "steps": []},
    ]}]}
    timeline = [
        {"id": "01", "chapter": 1, "start": 10.0, "duration": 12.0, "speech_end": 11.0,
         "sentences": [{"text": "The wall is three metres high.", "start": 0.5, "duration": 3.0},
                       {"text": "The ladder cuts across the gap.", "start": 3.5, "duration": 4.0}]},
        {"id": "02", "chapter": 1, "start": 22.0, "duration": 10.0, "speech_end": 9.0,
         "sentences": [{"text": "Now a new wall.", "start": 0.5, "duration": 8.0}]},
    ]
    pts = vision_review.sample_points(timeline, lesson)
    assert [p["beat"] for p in pts] == ["01", "02"]
    # key step is in sentence 2 (starts at 13.5 s): sample just after its cue, inside the beat
    assert 13.5 < pts[0]["at"] < 22.0
    assert pts[0]["spoken"].startswith("The ladder cuts")
    assert pts[0]["intended"] == ["math: 3 m", "key: c"]
    # no key step: 60% into the speech, never at the start
    assert pts[1]["at"] > 22.0 + 2.0 and pts[1]["spoken"] == "Now a new wall."
    assert all(p["at"] < t["start"] + t["duration"] for p, t in zip(pts, timeline))


def test_the_review_looks_when_the_render_showed_the_step_not_when_it_should_have(tmp_path):
    """One lesson's review looked 0.2 and 0.4 s after two steps had begun to be written and reported "Predic" and
    "Attractio" as text clipped by the frame: its own working-out of a cue differed from the renderer's."""
    import json
    lesson = {"chapters": [{"id": 1, "beats": [{"id": "01", "steps": []}]}, {"id": 2, "beats": [
        {"id": "02", "steps": [{"say": "pehle experiment", "show": "Experiment", "kind": "point", "highlight": False},
                               {"say": "kya bulb jalega", "show": "Predict: on or off?", "kind": "key", "highlight": True}]},
        {"id": "03", "steps": [{"say": "ek wire", "show": "One wire", "kind": "point", "highlight": False}]},
        {"id": "04", "steps": [{"say": "bulb bujh", "show": "Bulb goes out", "kind": "key", "highlight": True}]}]}]}
    timeline = [
        {"id": "01", "chapter": 1, "start": 0.0, "duration": 30.0, "sentences": []},
        {"id": "02", "chapter": 2, "start": 30.0, "duration": 18.0, "speech_end": 13.0,
         "sentences": [{"text": "Pehle experiment.", "start": 1.5, "duration": 2.0},
                       {"text": "Predict karo, kya bulb jalega agar ek wire ho?", "start": 8.5, "duration": 4.5}]},
        {"id": "03", "chapter": 2, "start": 48.0, "duration": 10.0, "speech_end": 9.0,
         "sentences": [{"text": "Ab ek wire hata dete hain.", "start": 0.5, "duration": 8.5}]},
        {"id": "04", "chapter": 2, "start": 58.0, "duration": 6.0, "speech_end": 5.8,
         "sentences": [{"text": "Toh path toot jaata hai aur bulb bujh jaata hai.", "start": 0.5, "duration": 5.3}]},
    ]
    out = tmp_path / "output"
    out.mkdir()
    # chapter 2's own clock starts at its first beat (30 s into the video); the key step was put up 9.7 s into it,
    # 1.2 s after the sentence that holds its phrase began; beat 03's step came 5.2 s into that beat
    (out / "chapter_02_audit.json").write_text(json.dumps({"cues": [
        {"beat": "02", "phrase": "pehle experiment", "target": 1.25, "actual_before_wait": 0.9},
        {"beat": "02", "phrase": "kya bulb jalega", "target": 9.7, "actual_before_wait": 5.0},
        {"beat": "03", "phrase": "ek wire", "target": 23.0, "actual_before_wait": 23.2},
        {"beat": "04", "phrase": "bulb bujh", "target": 33.3, "actual_before_wait": 30.0}]}))
    shown = vision_review.shown_at(tmp_path, timeline)
    assert shown["02"][1] == ("kya bulb jalega", 39.7) and shown["03"] == [("ek wire", 53.2)]      # late: when it was reached
    by_guess = {p["beat"]: p for p in vision_review.sample_points(timeline, lesson)}
    by_record = {p["beat"]: p for p in vision_review.sample_points(timeline, lesson, shown)}
    # guessed from the sentence start, the look fell 0.4 s into the writing; from the record it waits until the step is whole
    assert by_guess["02"]["at"] == round(30.0 + 8.5 + vision_review.KEY_STEP_SETTLE, 3)
    assert 0 < by_guess["02"]["at"] - 39.7 < vision_review.ARRIVING
    assert by_record["02"]["at"] == round(39.7 + vision_review.KEY_STEP_SETTLE, 3) and "key: Predict: on or off?" in by_record["02"]["intended"]
    # a beat with no key step is looked at 60% into its speech (53.4 s): 0.2 s into this step's writing, so later
    assert by_record["03"]["at"] == round(53.2 + vision_review.KEY_STEP_SETTLE, 3) and by_record["03"]["intended"] == ["point: One wire"]
    # a step that begins 0.7 s before its beat ends can never be seen whole there: look just before it, and say it is not due
    assert by_record["04"]["at"] < 30.0 + 33.3 and by_record["04"]["later"] == ["key: Bulb goes out"]
    # a chapter with no record keeps the estimates, and nothing raises
    assert vision_review.shown_at(tmp_path / "nowhere", timeline) == {}


def test_the_judge_is_told_what_a_prepared_drawing_holds_by_each_beat():
    """The first lesson whose chapters opened with what earlier chapters had drawn in was reported for exactly that:
    "the labels Precipitation and Collection are visible but not intended yet"."""
    water = {"kind": "diagram", "manifest": "/lib/water/manifest.json", "ask": "The water cycle"}
    lesson = {"chapters": [
        {"id": 1, "beats": [{"id": "01", "figure": water, "steps": [{"say": "a", "show": "Rain falls", "kind": "point", "focus": "precipitation"}]}]},
        {"id": 2, "beats": [{"id": "02", "figure": water, "steps": [{"say": "b", "show": "Vapour rises", "kind": "point", "focus": "evaporation"}]},
                            {"id": "03", "figure": {"kind": "picture", "file": "/lib/circuit/whole.png", "ask": "A simple circuit"},
                             "steps": [{"say": "c", "show": "The bulb", "kind": "point", "focus": "panel2"}]},
                            {"id": "04", "steps": []}]}]}
    timeline = [{"id": i, "chapter": c, "start": 10.0 * n, "duration": 10.0, "speech_end": 9.0, "sentences": []}
                for n, (i, c) in enumerate((("01", 1), ("02", 2), ("03", 2), ("04", 2)))]
    by = {p["beat"]: p["drawing"] for p in vision_review.sample_points(timeline, lesson)}
    assert by["01"] == {"of": "The water cycle", "kept": [], "whole": False}
    assert by["02"]["kept"] == ["precipitation"] and by["03"] == {"of": "A simple circuit", "kept": [], "whole": True} and by["04"] is None
    note = vision_review._drawing_note(by["02"])
    assert "precipitation" in note and "STAY" in note and "The water cycle" in note
    assert "shown whole" in vision_review._drawing_note(by["03"]) and vision_review._drawing_note(None) == ""


def test_judge_is_none_without_a_key(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    assert vision_review.default_judge() is None


def test_the_reviewer_is_told_when_a_beat_shows_one_line_of_words_at_a_time(tmp_path):
    """A line that has gone is not a line that is missing: the render says how it laid each beat out."""
    import json
    timeline = [{"id": "01", "chapter": 1, "start": 0.0, "duration": 20.0, "speech_end": 16.0,
                 "sentences": [{"text": "sea water rises and then it rains", "start": 0.5, "duration": 14.0}]},
                {"id": "02", "chapter": 2, "start": 20.0, "duration": 20.0, "speech_end": 16.0,
                 "sentences": [{"text": "water keeps moving", "start": 0.5, "duration": 14.0}]}]
    lesson = {"chapters": [{"id": 1, "beats": [{"id": "01", "steps": [{"say": "sea water", "show": "Sea water", "kind": "point"},
                                                                        {"say": "it rains", "show": "Rain falls", "kind": "point"}]}]},
                           {"id": 2, "beats": [{"id": "02", "steps": [{"say": "water keeps", "show": "Water keeps moving", "kind": "key"}]}]}]}
    (tmp_path / "output").mkdir()
    (tmp_path / "output" / "chapter_01_audit.json").write_text(json.dumps({"cues": [], "bounds": [
        {"beat": "01", "bounds_violations": [], "layout": {"frame": "stage", "mode": "top", "words": "caption"}}]}))
    (tmp_path / "output" / "chapter_02_audit.json").write_text(json.dumps({"cues": [], "bounds": [{"beat": "02", "bounds_violations": []}]}))
    layouts = vision_review.laid_out(tmp_path, timeline)
    assert layouts == {"01": {"frame": "stage", "mode": "top", "words": "caption"}}        # a chapter rendered the old way says nothing
    points = {p["beat"]: p for p in vision_review.sample_points(timeline, lesson, layouts=layouts)}
    one = vision_review._intended_note(points["01"])
    assert "ONE line of words at a time, above the picture" in one and "only the LAST of them" in one and "do not report it as missing" in one
    assert "earlier ones are dimmed" in vision_review._intended_note(points["02"]) and points["02"]["words"] is None
    assert vision_review.laid_out(tmp_path / "nowhere", timeline) == {}
