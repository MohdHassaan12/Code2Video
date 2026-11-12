"""The shared storyboard, its gate, the timeline compiler and the quality report (longform/storyboard.py,
timeline_compiler.py, qa.py). No manim render, no model, no network."""
import copy
import json

from lessonforge.longform import qa, storyboard, timeline_compiler as tc


def lesson(**beat_extra):
    beats = [
        {"id": "01", "narration": "The horse pushes the ground backward. The ground pushes the horse forward.",
         "visual": "a hoof on the ground", "check": "name the force pair",
         "steps": [{"say": "pushes the ground", "show": "Hoof pushes ground back", "kind": "point"},
                   {"say": "the horse forward", "show": "Ground pushes horse forward", "kind": "key"}]},
        {"id": "02", "narration": "Which way does friction act on the hoof?", "thinking_pause_seconds": 3,
         "quiz": {"question": "Which way?", "options": ["Back", "Forward", "Up"], "answer_index": 1},
         "steps": [{"say": "friction act", "show": "Friction on the hoof?", "kind": "point"}]},
    ]
    beats[0].update(beat_extra)
    return {"title": "Third law", "language": "en-IN", "brief": {"topic": "Newton's third law", "goal": "find force pairs",
                                                                "misconception": "pairs cancel"},
            "chapters": [{"id": 1, "title": "PAIRS", "role": "idea", "learning_goal": "g", "beats": beats}]}


def test_a_clean_storyboard_passes_and_carries_narration_visual_events_and_rules():
    made = storyboard.from_lesson(lesson())
    assert made["schema"] == storyboard.SCHEMA and [b["id"] for b in made["beats"]] == ["01", "02"]
    first = made["beats"][0]
    assert first["visual_intent"] == "a hoof on the ground" and first["reasoning"] == "name the force pair"
    assert [e["anchor"] for e in first["events"]] == ["pushes the ground", "the horse forward"]
    assert made["beats"][1]["events"][-1]["kind"] == "question"
    assert any("anchor" in rule for rule in first["validation"])
    assert storyboard.validate(lesson()) == []


def test_the_gate_finds_what_the_renderer_would_get_wrong():
    broken = lesson()
    beat = broken["chapters"][0]["beats"][0]
    beat["narration"] = "The horse [pause] pushes the ground backward. The ground pushes the horse forward."
    beat["steps"][1]["say"] = "never said here"
    found = {(i["check"], i["severity"]) for i in storyboard.validate(broken)}
    assert ("narration", "error") in found and ("anchor", "error") in found
    # an anchor that runs across a sentence end is never found by the renderer
    across = lesson()
    across["chapters"][0]["beats"][0]["steps"][0]["say"] = "backward The ground"
    assert any(i["check"] == "anchor" for i in storyboard.validate(across))
    # steps whose words come in the wrong order: the later one is spread, not waited for
    order = lesson()
    order["chapters"][0]["beats"][0]["steps"].reverse()
    assert any(i["check"] == "anchor order" and i["severity"] == "warning" for i in storyboard.validate(order))
    bare = lesson(visual="", steps=[])
    assert any(i["check"] == "visual intent" for i in storyboard.validate(bare))


def test_repair_touches_only_the_failing_beat_and_keeps_an_authors_words():
    broken = lesson()
    broken["chapters"][0]["beats"][0]["narration"] = "The *horse* pushes the ground backward. The ground pushes the horse forward."
    broken["chapters"][0]["beats"][0]["steps"][1]["say"] = "never said here"
    other = copy.deepcopy(broken["chapters"][0]["beats"][1])
    kept = copy.deepcopy(broken)
    assert storyboard.repair(kept, keep_words=True, log=lambda *_: None) == ["01"]
    assert "*horse*" in kept["chapters"][0]["beats"][0]["narration"]
    changed = storyboard.repair(broken, log=lambda *_: None)
    assert changed == ["01"] and broken["chapters"][0]["beats"][1] == other
    fixed = broken["chapters"][0]["beats"][0]
    assert "*" not in fixed["narration"]
    assert fixed["steps"][1]["say"] == "ground pushes the"   # the sentence that holds the step's own words
    assert storyboard.validate(broken) == []


def test_prepare_writes_stages_one_to_three(tmp_path):
    made = lesson()
    gate = storyboard.prepare(tmp_path, made, log=lambda *_: None)
    assert gate["errors"] == 0
    spec = json.loads((tmp_path / "output" / "lesson_spec.json").read_text())
    plan = json.loads((tmp_path / "output" / "teaching_plan.json").read_text())
    assert spec["learning_objectives"] == ["find force pairs"] and plan["misconceptions"] == ["pairs cancel"]
    assert plan["sequence"][0]["questions"] == ["02"]
    assert json.loads((tmp_path / "output" / "storyboard.json").read_text())["gate"] == gate


def test_the_renderer_and_the_compiler_search_with_one_function():
    from lessonforge.longform import runtime
    assert runtime._locate is tc.locate and runtime.CUE_LEAD == tc.CUE_LEAD


def timeline(aligned=True, gap=0.0):
    s1 = {"text": "The horse pushes the ground backward.", "start": 0.5, "duration": 2.0, "timing_source": "measured"}
    s2 = {"text": "The ground pushes the horse forward.", "start": 2.6, "duration": 2.0, "timing_source": "measured"}
    if aligned:
        s1 = {**s1, "timing_source": "aligned",
              "words": [{"word": w, "start": 0.5 + 0.3 * i, "end": 0.8 + 0.3 * i} for i, w in enumerate(s1["text"].split())]}
        s2 = {**s2, "timing_source": "aligned",
              "words": [{"word": w, "start": 2.6 + 0.3 * i, "end": 2.9 + 0.3 * i} for i, w in enumerate(s2["text"].split())]}
    return [{"id": "01", "chapter": 1, "start": 0.0, "duration": 5.2, "speech_end": 4.6, "lead": 0.5, "sentences": [s1, s2]},
            {"id": "02", "chapter": 1, "start": 5.2 + gap, "duration": 5.0, "speech_end": 1.9, "lead": 0.5,
             "sentences": [{"text": "Which way does friction act on the hoof?", "start": 0.5, "duration": 1.4,
                            "timing_source": "measured"}]}]


def test_events_land_on_the_heard_word_and_say_how_their_time_was_found():
    compiled = tc.compile_timeline(lesson(), timeline())
    first = compiled["beats"][0]["events"]
    # "pushes the ground" is word 2 of sentence 1: heard at 0.5 + 0.6; the picture leads by CUE_LEAD
    assert first[0]["source"] == "aligned" and abs(first[0]["time"] - (1.1 - tc.CUE_LEAD)) < 1e-6
    assert first[0]["anchor_time"] == 1.1
    second = compiled["beats"][1]["events"]
    assert second[0]["source"].startswith("word-position") and second[-1]["kind"] == "question"
    assert compiled["summary"]["steps"] == 3 and compiled["summary"]["steps_on_heard_words"] == 2
    assert [i for i in compiled["issues"] if i["severity"] == "error"] == []


def test_the_compiler_finds_an_unspoken_anchor_a_gap_and_a_line_too_short_to_read():
    made = lesson()
    made["look"] = {"frame": "stage"}
    made["chapters"][0]["beats"][0]["steps"][0]["say"] = "not in the speech"
    made["chapters"][0]["beats"][0]["steps"][1]["show"] = "a long line of words that nobody could read in one second flat"
    compiled = tc.compile_timeline(made, timeline(gap=0.5))
    checks = {(i["check"], i["severity"]) for i in compiled["issues"]}
    assert ("anchor spoken", "warning") in checks and ("beats end to end", "error") in checks
    assert any(e["source"] == "fallback-spread" for e in compiled["beats"][0]["events"])


def test_the_quality_report_names_beats_and_the_component_to_repair(tmp_path):
    made = lesson()
    made["chapters"][0]["beats"][0]["steps"][1]["say"] = "never said here"
    storyboard.prepare(tmp_path, made, fix=False, log=lambda *_: None)
    (tmp_path / "timeline.json").write_text(json.dumps(timeline()))
    tc.compile_lesson(tmp_path, made, log=lambda *_: None)
    (tmp_path / "output" / "final_checks.json").write_text(json.dumps({
        "checks": [{"check": "nothing outside the stage at any beat end", "passed": False, "detail": "1 violation(s)"},
                   {"check": "audio stream present", "passed": True}],
        "bounds_detail": [{"chapter": 1, "beat": "02"}]}))
    report = qa.write_qa(tmp_path, verification={"status": "passed", "findings": [], "claims_failed": []},
                         log=lambda *_: None)
    assert report["status"] == "failed"
    assert set(report["repair_plan"]) == {"01", "02"}
    assert "storyboard" in report["repair_plan"]["01"]["components"]
    assert report["repair_plan"]["02"]["components"] == ["visuals"]
    assert report["by_area"]["correctness"]["pass"] == 1
    video = tmp_path / "output" / "lesson.mp4"
    video.write_bytes(b"x")
    bundle = qa.write_bundle(tmp_path, video, log=lambda *_: None)
    rows = {f["path"]: f for f in bundle["files"]}
    assert {"output/storyboard.json", "timeline.json", "output/qa_report.json", "output/lesson.mp4"} <= set(rows)
    assert len(rows["output/lesson.mp4"]["sha256"]) == 64
