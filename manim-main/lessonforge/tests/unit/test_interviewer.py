"""Model-written intake questions: validation, fallbacks, push-back, delegation, persistence. No network."""
import json

import pytest

from lessonforge.harness import intake, interviewer, service


@pytest.fixture(autouse=True)
def workspace(tmp_path, monkeypatch):
    monkeypatch.setenv("LESSONFORGE_HOME", str(tmp_path))
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    service._SESSIONS.clear()
    service._JOBS.clear()
    yield tmp_path
    service.INTAKE_LLM = None
    service._SESSIONS.clear()
    service._JOBS.clear()


def scripted(replies):
    """A stub interviewer model: pops one reply per call and records the prompts."""
    calls = []

    def llm(prompt, system):
        calls.append(prompt)
        reply = replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply
    llm.calls = calls
    return llm


def q(prompt, options, **extra):
    return {"learned": {}, "unclear": None, "question": {"prompt": prompt, "why": "because", "options": options}, **extra}


def test_text_question_gets_topic_specific_suggestions_and_keeps_free_text():
    base = intake.next_question({"topic": "Pythagorean theorem", "audience": "Class 8", "level": "standard"})
    assert base["id"] == "goal" and base["kind"] == "text"
    merged = interviewer.merge_question(base, {"prompt": "What should Class 8 be able to do with a right triangle?",
                                               "why": "It decides the worked example.",
                                               "options": [{"value": "Find the missing side of a right triangle", "label": "Find a missing side", "hint": "exam skill"},
                                                           {"value": "Find the missing side of a right triangle", "label": "dup"},
                                                           {"label": "Explain why the squares add up"}, "junk", {"value": ""}]})
    assert merged["source"] == "model" and merged["kind"] == "text" and merged["id"] == "goal"
    assert [o["value"] for o in merged["options"]] == ["Find the missing side of a right triangle",
                                                       "Explain why the squares add up"]
    assert "type your own" in merged["placeholder"]


def test_choice_question_keeps_values_and_labels_and_only_takes_hints():
    base = intake.next_question({"topic": "Trig", "audience": "Class 10"})
    assert base["id"] == "level"
    good = interviewer.merge_question(base, {"prompt": "Do they know sin, cos and tan yet?", "why": "w", "options": [
        {"value": "foundation", "label": "RENAMED", "hint": "Has not met the ratios"},
        {"value": "standard", "hint": "Knows the ratios and the table"},
        {"value": "advanced", "hint": "Solves basic equations"}]})
    assert [o["value"] for o in good["options"]] == ["foundation", "standard", "advanced"]
    assert good["options"][0]["label"] == base["options"][0]["label"]          # label is code's
    assert good["options"][0]["hint"] == "Has not met the ratios" and good["source"] == "model"
    # a model that changes the choice set is ignored entirely
    bad = interviewer.merge_question(base, {"prompt": "x", "options": [{"value": "expert", "hint": "h"}]})
    assert bad["source"] == "default" and bad["prompt"] == base["prompt"]
    assert interviewer.merge_question(base, "not a dict")["source"] == "default"


def test_learned_is_validated_and_never_overwrites():
    brief = {"topic": "T", "language": "hi-IN"}
    learned = interviewer.clean_learned({"grade": "9", "level": "expert", "language": "en-IN", "duration_minutes": 99,
                                         "misconception": "They add the angles", "context": "you decide",
                                         "audience": "  Class 9, village school  ", "secret": "x"}, brief)
    assert learned == {"grade": 9, "misconception": "They add the angles", "audience": "Class 9, village school"}


def test_delegation_phrases():
    for phrase in ("You decide", "you decide.", "up to you", "anything", "u choose", "not sure", "idk", "you can decide"):
        assert interviewer.is_delegation(phrase), phrase
    for phrase in ("a ladder", "You decide the angle of a ladder", "any triangle with a right angle"):
        assert not interviewer.is_delegation(phrase), phrase


def test_session_uses_the_model_pushes_back_once_and_resolves_you_decide(workspace):
    llm = scripted([
        # 1. opening "Trigonometric equations" → broad chapter flagged; question is for the audience
        {"learned": {}, "unclear": "That is a whole chapter.", "question": {
            "prompt": "Which class is this trigonometry video for?", "why": "w",
            "options": [{"value": "Class 10 students (NCERT chapter 8)", "label": "Class 10", "hint": "first meeting"}]}},
        # 2. after audience → the narrowing (focus) question, written for class 9
        q("Which one idea inside trigonometric equations should Class 9 take away?",
          [{"value": "Finding an angle when sin theta is known", "label": "Angle from a sine", "hint": "table lookup"},
           {"value": "Solving sin x = cos x", "label": "sin x = cos x"}]),
        # 3. level, 4. goal
        q("Do they already know sin, cos and tan?", [{"value": "foundation", "hint": "no"}, {"value": "standard", "hint": "yes"},
                                                     {"value": "advanced", "hint": "fluent"}]),
        q("What should they be able to do?", [{"value": "Find an unknown angle from a given sine using the table",
                                               "label": "Find an unknown angle", "hint": "checkable"}]),
        # 5. the vague goal is sent back …
        {"learned": {}, "unclear": "“Do problems” names no skill to check.", "question": {"prompt": "ignored", "options": []}},
        # 6. … and re-asked narrower
        q("Which problems exactly?", [{"value": "Find theta when sin theta = 1/2", "label": "Find theta from a sine"}]),
        # 7. framework
        q("How should it unfold?", [{"value": v, "hint": "for trig"} for v in ("worked_examples", "concrete_first", "why_it_works")]),
        # 8. duration
        q("How long?", [{"value": 2, "hint": "one equation"}, {"value": 6, "hint": "two"}, {"value": 15, "hint": "lesson"}]),
        # 9. context, 10. misconception
        q("Which setting?", [{"value": "The shadow of a flagpole on the school ground", "label": "Flagpole shadow"}]),
        q("Which mistake?", [{"value": "They read the angle off the wrong row of the table", "label": "Wrong table row"}]),
    ])
    service.INTAKE_LLM = llm
    view = service.start_session("Trigonometric equations")
    assert view["question"]["id"] == "audience" and view["question"]["source"] == "model"
    assert "PUSH-BACK: allowed" in llm.calls[0]
    sid = view["session_id"]
    view = service.answer_session(sid, "audience", view["question"]["options"][0]["value"])
    assert view["question"]["id"] == "focus" and view["brief"]["grade"] == 10
    view = service.answer_session(sid, "focus", "Finding an angle when sin theta is known")   # tapped a suggestion
    assert view["brief"]["topic"] == "Finding an angle when sin theta is known"
    assert view["brief"]["subject"] == "Trigonometric equations" and view["question"]["id"] == "level"
    view = service.answer_session(sid, "level", "standard")
    assert view["question"]["id"] == "goal" and len(view["question"]["options"]) == 1
    view = service.answer_session(sid, "goal", "They should do problems on trigonometry")
    # pushed back ONCE: same field, sharper, with a note saying why; the raw words are kept for the writer
    assert view["question"]["id"] == "goal" and view["question"]["prompt"] == "Which problems exactly?"
    assert "names no skill" in view["note"] and "goal" not in view["brief"]
    assert view["brief"]["notes"]["goal"] == "They should do problems on trigonometry"
    assert "RE-ASK" in llm.calls[5]
    view = service.answer_session(sid, "goal", "still vague")
    assert view["question"]["id"] == "framework" and view["brief"]["goal"] == "still vague"   # no second push-back
    assert "PUSH-BACK: not allowed" in llm.calls[6]
    view = service.answer_session(sid, "framework", "worked_examples")
    assert view["question"]["id"] == "style" and view["question"]["source"] == "default"       # generic by nature: no call
    view = service.answer_session(sid, "style", "tutor")
    view = service.answer_session(sid, "language", "hinglish")
    assert view["question"]["id"] == "duration_minutes"
    view = service.answer_session(sid, "duration_minutes", 6)
    assert view["question"]["id"] == "context"
    view = service.answer_session(sid, "context", "You decide")
    assert view["brief"]["context"] == "The shadow of a flagpole on the school ground"
    assert "Flagpole shadow" in view["note"]
    view = service.answer_session(sid, "misconception", "you decide")
    assert view["question"] is None and view["progress"]["complete"]
    assert view["brief"]["misconception"].startswith("They read the angle")
    assert "needs_focus" not in service.session_brief(sid)
    assert not llm.calls[len(llm.calls):] and len(llm.calls) == 10


def test_model_failure_falls_back_to_the_plain_question(workspace):
    service.INTAKE_LLM = scripted([RuntimeError("timeout"), {"nonsense": True}])
    view = service.start_session("Fractions for class 6")
    assert view["question"]["id"] == "level" and view["question"]["source"] == "default"
    view = service.answer_session(view["session_id"], "level", "foundation")
    assert view["question"]["id"] == "goal" and view["question"]["source"] == "default"
    assert service._session(view["session_id"])["model_errors"] == 1


def test_no_model_configured_is_the_deterministic_intake_and_sessions_survive_a_restart(workspace):
    service.INTAKE_LLM = False
    view = service.start_session("Pythagorean theorem for class 8")
    sid = view["session_id"]
    assert view["question"]["id"] == "level" and view["question"]["source"] == "default"
    service.answer_session(sid, "level", "standard")
    service._SESSIONS.clear()                                   # the server restarts
    view = service.get_session(sid)
    assert view["question"]["id"] == "goal" and view["brief"]["level"] == "standard"
    view = service.answer_session(sid, "goal", "you decide")    # required field, no options offered
    assert view["brief"]["goal"].startswith("Solve typical problems on Pythagorean theorem")
    with pytest.raises(KeyError):
        service.get_session("doesnotexist")


def test_job_records_survive_a_restart_and_a_built_video_outlives_a_late_failure(workspace):
    root = workspace / "lessons" / "20261008-065634-86fa90"
    (root / "output").mkdir(parents=True)
    lesson = {"title": "Trig", "brief": {"topic": "Trig", "grade": 9, "language": "hinglish"}, "generated_by": "model",
              "continuity": {"warnings": []}, "verification": {"status": "passed", "scores": {}, "findings": []},
              "chapters": [{"id": 1, "title": "A", "role": "hook", "beats": [
                  {"id": "01", "narration": "What is the angle?", "thinking_pause_seconds": 4, "check": "look at the table"},
                  {"id": "02", "narration": "It is thirty degrees. Then we go on.", "thinking_pause_seconds": 0}]}]}
    (root / "lesson.json").write_text(json.dumps(lesson))
    (root / "timeline.json").write_text(json.dumps([
        {"id": "01", "chapter": 1, "start": 0.0, "duration": 9.0, "speech_end": 4.5, "sentences": [{"text": "What is the angle?", "start": 0.5, "duration": 4}]},
        {"id": "02", "chapter": 1, "start": 9.0, "duration": 6.0, "speech_end": 5.0, "sentences": []}]))
    (root / "output" / "final_checks.json").write_text(json.dumps({
        "status": "technical_checks_passed", "video": "trig.mp4", "duration_seconds": 15.0, "chapters": 1, "beats": 2,
        "captions": 1, "animation_anchors": 0, "anchor_timing": {}, "sentence_timing": {}, "bounds_violations": 0,
        "review_limits": [], "layout_findings": {"counted": 0}, "checks": [{"check": "x", "passed": True}]}))
    (root / "audio_report.json").write_text(json.dumps({"backend": "gemini", "alignment": {"clips": 2, "trusted": 2}}))
    # no video yet → nothing to recover
    assert service.results_from_disk(root) is None
    (root / "output" / "trig.mp4").write_bytes(b"\x00")
    # the record the crashed run left behind (or none at all): the video on disk wins
    (root / "job.json").write_text(json.dumps({"job_id": root.name, "status": "failed", "stage": "review",
                                               "error": "TypeError: 'Chapter' object is not subscriptable",
                                               "brief": lesson["brief"], "created": 1.0, "title": "Trig"}))
    job = service.get_job(root.name)
    assert job["status"] == "done" and job["error"] is None and job["recovered"] is True
    assert job["video_url"] == f"/lessons/{root.name}/output/trig.mp4" and "had failed" in job["note"]
    assert job["chapters"] == [{"id": 1, "title": "A", "start": 0.0, "depths": ["core"]}] and job["alignment"]["trusted"] == 2
    # the interaction file the crash never wrote is produced on recovery
    sidecar = json.loads((root / "output" / "interactions.json").read_text())
    assert sidecar["schema"] == "lessonforge.interactions/0.1" and sidecar["band"] == "9-10" and sidecar["lang"] == "hinglish"
    assert sidecar["chapters"] == [{"t": 0.0, "title": "A"}]
    (card,) = sidecar["interactions"]
    assert card["prompt"]["text"] == "What is the angle?" and card["t"] == 4.5 and card["answer"]["text"] == "It is thirty degrees."
    assert job["interactions"] == 1
    # listed newest-first, with what the history screen needs; an interrupted run says so
    cut = workspace / "lessons" / "20261009-010101-aaaaaa"
    cut.mkdir()
    (cut / "job.json").write_text(json.dumps({"job_id": cut.name, "status": "running", "stage": "speech", "created": 2.0,
                                              "title": "Cut short", "brief": {}}))
    service._JOBS.clear()
    rows = service.list_jobs()
    assert [r["job_id"] for r in rows] == [cut.name, root.name]
    assert rows[0]["status"] == "failed" and "restarted" in rows[0]["error"]
    assert rows[1]["status"] == "done" and rows[1]["duration_seconds"] == 15.0 and rows[1]["language"] == "hinglish"
    with pytest.raises(KeyError):
        service.get_job("../etc")


def test_a_goal_with_no_checkable_action_is_sent_back_even_when_the_model_lets_it_through(workspace):
    brief = {"topic": "Adding fractions with unlike denominators", "subject": "Fractions"}
    for vague in ("they should do problems on it", "They should to problems on fractions", "understand the topic well",
                  "learn adding fractions"):
        assert interviewer.is_vague_goal(vague, brief), vague
    for specific in ("add two fractions like 1/2 + 1/3", "explain why a common denominator is needed",
                     "find the missing side of a right triangle"):
        assert not interviewer.is_vague_goal(specific, brief), specific
    llm = scripted([
        q("Do they know equal-denominator addition?", [{"value": v, "hint": "h"} for v in ("foundation", "standard", "advanced")]),
        q("What should they be able to do?", [{"value": "Add 1/2 and 1/3", "label": "Add 1/2 and 1/3"}]),
        q("How should it unfold?", [{"value": v, "hint": "h"} for v in ("concrete_first", "worked_examples", "why_it_works")]),  # model: no push-back
        q("Which skill exactly?", [{"value": "Add two fractions with different denominators", "label": "Add unlike fractions"}]),
    ])
    service.INTAKE_LLM = llm
    view = service.start_session("Adding fractions with unlike denominators, class 6")
    view = service.answer_session(view["session_id"], "level", "foundation")
    view = service.answer_session(view["session_id"], "goal", "they should do problems on it")
    assert view["question"]["id"] == "goal" and view["question"]["prompt"] == "Which skill exactly?"
    assert "does not yet say" in view["note"] and "goal" not in view["brief"]


def test_one_video_several_ways_of_watching(workspace):
    root = workspace / "lessons" / "20261008-120000-abcdef"
    (root / "output").mkdir(parents=True)
    beats = [("01", 1, "activate", "basics", 0, 20), ("02", 2, "idea", "core", 20, 30), ("03", 3, "example", "core", 50, 40),
             ("04", 4, "faded", "practice", 90, 30), ("05", 5, "refutation", "extra", 120, 20), ("06", 6, "recap", "core", 140, 15)]
    lesson = {"title": "T", "chapters": [{"id": c, "title": f"C{c}", "role": role,
                                         "beats": [{"id": bid, "narration": "x", "depth": depth}]}
                                        for bid, c, role, depth, _, _ in beats]}
    (root / "timeline.json").write_text(json.dumps([{"id": bid, "chapter": c, "start": float(st), "duration": float(d),
                                                     "sentences": []} for bid, c, _, _, st, d in beats]))
    outline = service.write_outline(root, lesson)
    cuts = {c["id"]: c for c in outline["cuts"]}
    assert list(cuts) == ["full", "standard", "revision", "summary"]
    assert cuts["full"]["seconds"] == 155 and cuts["full"]["ranges"] == [[0.0, 155.0]]
    assert cuts["standard"]["ranges"] == [[20.0, 155.0]]                       # the basics chapter is skipped
    assert cuts["revision"]["beats"] == ["02", "03", "06"] and cuts["revision"]["seconds"] == 85
    assert cuts["revision"]["ranges"] == [[20.0, 90.0], [140.0, 155.0]]        # adjacent segments are merged
    assert cuts["summary"]["beats"] == ["02", "06"] and cuts["summary"]["seconds"] == 45
    assert outline["chapters"][0] == {"id": 1, "title": "C1", "role": "activate", "depths": ["basics"], "start": 0.0, "end": 20.0}
    # a lesson whose beats are all core offers no pointless choices
    flat = {"title": "T", "chapters": [{"id": c, "title": "C", "role": "idea", "beats": [{"id": bid, "narration": "x"}]}
                                       for bid, c, *_ in beats]}
    assert [c["id"] for c in service.write_outline(root, flat)["cuts"]] == ["full"]


def test_writer_tags_every_beat_with_a_depth():
    from lessonforge.harness import frameworks, writer
    raw = {"chapters": [{"beats": [{"narration": "Recall what a fraction is.", "steps": []}]},
                        {"beats": [{"narration": "Here is the idea.", "depth": "CORE", "steps": []},
                                   {"narration": "An aside.", "depth": "nonsense", "steps": []}]}]}
    lesson = writer.discipline(raw, {"topic": "t"}, frameworks.get("worked_examples"))   # stages: hook, activate, …
    depths = [b["depth"] for c in lesson["chapters"] for b in c["beats"]]
    # chapter 1 is the hook (core by default); chapter 2 is "activate": its "CORE" beat is capped to basics,
    # and an unknown tag falls back to the stage's depth
    assert depths == ["core", "basics", "basics"]
    # the chapter's job caps what may be core: a warm-up beat the model called "core" stays basics, a recap beat stays core
    assert writer.beat_depth({"depth": "core"}, "activate") == "basics" and writer.beat_depth({"depth": "core"}, "faded") == "practice"
    assert writer.beat_depth({"depth": "core"}, "recap") == "core" and writer.beat_depth({"depth": "extra"}, "idea") == "extra"
    assert writer.beat_depth({}, "refutation") == "extra"


def test_scenes_are_resolved_once_per_description_and_an_unverified_one_is_dropped():
    from lessonforge.harness import frameworks, writer
    good, bad = "A closed flask where brown molecules keep pairing up and splitting again", "A machine that cannot be drawn at all, ever"
    raw = {"chapters": [{"beats": [
        {"narration": "Look at the flask.", "steps": [], "figure": {"kind": "scene", "describe": good, "junk": 1}},
        {"narration": "It keeps going.", "steps": [], "figure": {"kind": "scene", "describe": good}},
        {"narration": "And this one.", "steps": [], "figure": {"kind": "scene", "describe": bad}},
        {"narration": "Too vague.", "steps": [], "figure": {"kind": "scene", "describe": "a thing"}}]}]}
    lesson = writer.discipline(raw, {"topic": "t"}, frameworks.get("worked_examples"))
    beats = lesson["chapters"][0]["beats"]
    assert beats[0]["figure"] == {"kind": "scene", "describe": good} and "figure" not in beats[3]   # too vague to draw
    calls = []

    def generate(description):
        calls.append(description)
        return "/cache/sim_flask.py" if description == good + service.SCENE_PAIRS else None

    report = service.resolve_scenes(lesson, log=lambda *_: None, generate=generate)
    # one call per DISTINCT description, and one more, simpler, for the one that failed
    pairs = service.SCENE_PAIRS
    assert sorted(calls) == sorted([good + pairs, bad + pairs, bad + pairs + service.SCENE_LIMITS])
    assert (report["asked"], report["made"], report["failed"], report["retried"]) == (2, 1, [bad], 1)
    assert beats[0]["figure"]["module"] == beats[1]["figure"]["module"] == "/cache/sim_flask.py"
    assert "figure" not in beats[2]                                   # no picture rather than a placeholder
    assert service.resolve_scenes(lesson, log=lambda *_: None, generate=generate)["asked"] == 0   # already resolved


def test_declining_to_narrow_keeps_the_topic(workspace):
    service.INTAKE_LLM = False
    view = service.start_session("Maths")                       # a whole subject → audience, then "which one idea?"
    sid = view["session_id"]
    view = service.answer_session(sid, "audience", "Working professionals moving into data analytics")
    assert view["question"]["id"] == "focus"
    view = service.answer_session(sid, "focus", "we need full coverage of all of them")
    assert view["brief"]["topic"] == "Maths"                    # the sentence is NOT the topic
    assert view["brief"]["notes"]["scope"] == "we need full coverage of all of them"
    assert view["question"]["id"] == "level" and "one video covering the main ideas of Maths" in view["note"]
    assert interviewer.wants_everything("cover everything") and interviewer.wants_everything("sab kuch chahiye")
    assert not interviewer.wants_everything("why the sign flips when multiplying by a negative")
