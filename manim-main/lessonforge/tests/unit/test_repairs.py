"""The frame review's findings cause a repair of the beat's steps (harness/repairs.py)."""
from lessonforge.harness import repairs, scripted, vision_review, writer

NARRATION = ("Ab three unit side ke bahar three rows banti hain, aur har row mein three tiles hain. "
             "Apna guess boliye: nine, six, ya three?")
REVIEW = {"detail": [
    {"beat": "01", "findings": []},
    {"beat": "02", "findings": [{"kind": "overlap", "what": "two labels touch"}]},                # layout: not this repair's
    {"beat": "03", "findings": [{"kind": "mismatch", "what": "The narrator asks to guess between nine, six or three, "
                                                             "but these numbers are not on screen."}]},
    {"beat": "04", "findings": [{"kind": "empty", "what": "nothing"}, {"kind": "stale", "what": "old picture"}]}]}


def test_only_findings_about_what_is_on_screen_are_this_repairs_and_the_worst_come_first(monkeypatch):
    assert list(repairs.targets(REVIEW)) == ["04", "03"] and repairs.targets(None) == {} and repairs.targets({"detail": []}) == {}
    monkeypatch.setattr(repairs, "MAX_BEATS", 1)
    assert list(repairs.targets(REVIEW)) == ["04"]


def test_new_steps_are_cleaned_exactly_as_a_writers_are():
    raw = [{"say": "three rows banti hain", "show": "3 rows of 3", "kind": "point", "focus": "Square_A!"},
           {"say": "words the narrator never says", "show": r"3 \\times 3 = 9", "kind": "point", "highlight": True},
           {"say": "nine, six, ya three", "show": "9, 6 or 3?", "kind": "key", "highlight": True},
           {"say": "", "show": "   "}, "not a step",
           {"say": "x", "show": "a"}, {"say": "x", "show": "b"}, {"say": "x", "show": "c"}]
    mine = repairs.clean_steps(raw, NARRATION)
    lesson = writer.discipline({"title": "t", "chapters": [{"title": "c", "beats": [
        {"narration": NARRATION, "steps": [s for s in raw if isinstance(s, dict)]}]}]}, {"language": "hinglish"}, scripted.FRAMEWORK)
    assert mine == lesson["chapters"][0]["beats"][0]["steps"]
    assert mine[0]["focus"] == "square_a" and mine[1]["kind"] == "math" and len(mine) <= writer.MAX_STEPS
    assert all(writer._norm(s["say"]) in writer._norm(NARRATION) or s["say"] == "" for s in mine)   # an anchor is never invented


def test_a_beat_is_asked_for_again_with_its_finding_and_nothing_is_invented():
    beat = {"id": "03", "narration": NARRATION, "figure": {"kind": "right_triangle", "a": 4, "b": 3},
            "steps": [{"say": "three rows banti hain", "show": "3 rows of 3", "kind": "point", "highlight": False, "focus": "square_a"},
                      {"say": "Apna guess boliye", "show": "Predict the total", "kind": "key", "highlight": True}]}
    seen = {}

    def model(prompt, system):
        seen.update(prompt=prompt, system=system)
        return {"steps": [beat["steps"][0],
                          {"say": "nine, six, ya three", "show": "9, 6 or 3?", "kind": "key", "highlight": True, "focus": "hypotenuse_square"}]}

    steps = repairs.fix_steps(beat, REVIEW["detail"][2]["findings"], model)
    assert seen["system"] is repairs.FIX_SYSTEM and "not on screen" in seen["prompt"] and NARRATION in seen["prompt"]
    assert writer.STEP_RULES in repairs.FIX_SYSTEM                       # the writer's own step rules, not a second set
    assert [s["show"] for s in steps] == ["3 rows of 3", "9, 6 or 3?"] and steps[0]["focus"] == "square_a"
    assert "focus" not in steps[1]                                       # the picture has no such part: not invented
    assert repairs.fix_steps(beat, [], lambda p, s: {"steps": beat["steps"]}) is None      # the same steps back: nothing to try
    assert repairs.fix_steps(beat, [], lambda p, s: {"steps": []}) is None and repairs.fix_steps(beat, [], lambda p, s: "no") is None


def test_a_second_look_replaces_only_the_beats_it_looked_at():
    second = {"detail": [{"beat": "03", "findings": [], "shows_intended": True, "readable": True}]}
    merged = vision_review.merge({**REVIEW, "by_kind": {}, "findings": 4}, second, ["03"])
    assert [len(r["findings"]) for r in merged["detail"]] == [0, 1, 0, 2] and merged["findings"] == 3
    assert merged["by_kind"]["mismatch"] == 0 and merged["by_kind"]["overlap"] == 1 and merged["repaired_beats"] == ["03"]
    assert vision_review.merge(REVIEW, second, ["04"])["detail"][3] == REVIEW["detail"][3]     # not looked at again: unchanged


def test_the_repair_is_told_a_prepared_drawings_parts_and_keeps_only_a_focus_the_drawing_has(monkeypatch):
    """The first lesson repaired on the owner's drawing: the steps handed in had already lost their focus, the model was
    told nothing of the drawing's parts, and the "cured" beats showed the drawing bare."""
    monkeypatch.setattr(repairs.diagrams, "ready_from", lambda manifest, ask="": {
        "parts": ["evaporation", "condensation"], "names": {"evaporation": "Evaporation", "condensation": "Condensation"}})
    beat = {"id": "03", "narration": "Sooraj ki garmi se paani bhaap bankar upar uthta hai. Ise evaporation kehte hain.",
            "figure": {"kind": "diagram", "manifest": "/lib/water/manifest.json", "ask": "The water cycle"},
            "steps": [{"say": "Sooraj ki garmi", "show": "Sun heats the sea", "kind": "point", "highlight": False}]}
    seen = {}

    def model(prompt, system):
        seen["prompt"] = prompt
        return {"steps": [{"say": "bhaap bankar", "show": "Water becomes vapour", "kind": "point", "focus": "evaporation"},
                          {"say": "evaporation kehte", "show": "Evaporation", "kind": "key", "highlight": True, "focus": "the_sun"}]}

    steps = repairs.fix_steps(beat, [{"kind": "mismatch", "what": "the vapour is not shown"}], model)
    assert '"evaporation" (Evaporation)' in seen["prompt"] and '"condensation" (Condensation)' in seen["prompt"]
    assert steps[0]["focus"] == "evaporation" and "focus" not in steps[1]          # "the_sun" is no part of this drawing


def test_steps_the_screen_repair_writes_again_are_timed_on_the_voice_before_they_are_filmed(tmp_path, monkeypatch):
    """The Monty Hall lesson (2026-10-19): rewritten steps came after the pipeline's sync repair and four beats showed
    lines too close together to be read. They are re-anchored on the measured narration before the render."""
    import json
    from lessonforge.longform import timeline_compiler as tc
    narration = ("Drop a heavy ball and a light ball together. Both start from rest at the same height. "
                 "Watch the two balls land at the same moment. Gravity gives each the same speed every second.")
    timeline = [{"id": "01", "start": 0.0, "duration": 14.0, "speech_end": 13.5, "lead": 0.5, "sentences": [
        {"text": t, "start": s, "duration": d, "timing_source": "measured"}
        for t, s, d in [("Drop a heavy ball and a light ball together.", 0.5, 3.0),
                        ("Both start from rest at the same height.", 3.5, 3.0),
                        ("Watch the two balls land at the same moment.", 6.5, 3.0),
                        ("Gravity gives each the same speed every second.", 9.5, 4.0)]]}]
    lesson = {"title": "Falling", "look": {"frame": "stage"}, "chapters": [
        {"id": 1, "title": "FALL", "role": "idea", "learning_goal": "g",
         "beats": [{"id": "01", "narration": narration, "visual": "two balls falling",
                    "steps": [{"say": "drop a heavy", "show": "Two balls", "kind": "point", "highlight": False}]}]}]}
    (tmp_path / "timeline.json").write_text(json.dumps(timeline), encoding="utf-8")
    (tmp_path / "output").mkdir()
    (tmp_path / "output" / "chapter_01_audit.json").write_text("{}", encoding="utf-8")
    clip = tmp_path / "c1.mp4"
    clip.write_bytes(b"clip")
    filmed = {}

    def render(root, made, **_):
        filmed["lesson"] = json.loads((root / "lesson.json").read_text(encoding="utf-8"))
        return {}

    monkeypatch.setattr(repairs.lesson_build, "render_chapters", render)
    monkeypatch.setattr(repairs.lesson_build, "assemble", lambda root, clips, made, log=print: tmp_path / "v.mp4")
    monkeypatch.setattr(repairs.lesson_build, "run_checks",
                        lambda *a, **k: {"layout_findings": {"counted": 0}, "bounds_violations": 0})
    monkeypatch.setattr(repairs.vision_review, "review_video",
                        lambda *a, **k: {"detail": [{"beat": "01", "findings": []}]})
    crowded = [{"say": "heavy ball", "show": "Heavy ball", "kind": "point"},
               {"say": "ball and", "show": "Light ball beside it falls the same way", "kind": "point"},
               {"say": "same moment", "show": "Both land together", "kind": "key"}]
    review = {"detail": [{"beat": "01", "findings": [{"kind": "mismatch", "what": "the light ball is not shown"}]}]}
    report = {"layout_findings": {"counted": 0}, "bounds_violations": 0}
    repairs.repair_screen(tmp_path, lesson, tmp_path / "v.mp4", {1: clip}, report, review,
                          llm=lambda p, s: {"steps": crowded}, judge=lambda *a: None, quality="l", log=lambda *_: None)
    issues = tc.compile_timeline(filmed["lesson"], timeline)["issues"]
    assert not any(i["check"] == "events crowded" for i in issues)
    assert [s["show"] for s in filmed["lesson"]["chapters"][0]["beats"][0]["steps"]] == \
        ["Heavy ball", "Light ball beside it falls the same way", "Both land together"]
