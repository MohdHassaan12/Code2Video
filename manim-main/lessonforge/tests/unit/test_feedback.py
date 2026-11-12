"""Student reviews: the sheet, validation, storage, the summary and its signals. No network, no render."""
import json

import pytest

from lessonforge.harness import feedback

GOOD = {"class_level": "8", "knew_before": "some", "understood": 4, "can_do": 3, "pace": "right", "language": 5,
        "visuals": 4, "sync": 2, "voice": 4, "screen_problem": "no", "questions_useful": 5, "length": "right", "overall": 4}


@pytest.fixture
def lesson(tmp_path, monkeypatch):
    monkeypatch.setenv("LESSONFORGE_HOME", str(tmp_path))
    root = tmp_path / "lessons" / "20261008-120000-abc123"
    root.mkdir(parents=True)
    (root / "lesson.json").write_text(json.dumps({
        "title": "Sine from two sides", "framework": "worked_examples", "brief": {"language": "hinglish", "grade": 10},
        "chapters": [{"id": 1, "title": "HOOK", "beats": [{"id": "01", "narration": "A ladder leans on a wall."}]},
                     {"id": 2, "title": "IDEA", "beats": [{"id": "02", "narration": "Sin theta equals three by four."}]}]}))
    (root / "timeline.json").write_text(json.dumps([
        {"id": "01", "chapter": 1, "start": 0.0, "duration": 30.0}, {"id": "02", "chapter": 2, "start": 30.0, "duration": 40.0}]))
    return root


def test_the_sheet_is_short_plain_and_every_question_points_at_an_area():
    form = feedback.form()
    assert len(form["tasks"]) == 5 and form["minutes"] <= 5
    questions = form["questions"]
    assert 15 <= len(questions) <= 22 and sum(q["required"] for q in questions) <= 14
    assert len({q["id"] for q in questions}) == len(questions)
    for q in questions:
        assert q["kind"] in ("rating", "choice", "text", "chapters") and q["area"] in feedback.AREAS, q["id"]
        assert len(q["prompt"]) <= 110                                # a student reads this on a phone
        if q["kind"] == "rating":
            assert (q["min"], q["max"]) == (1, 5) and q["low_label"] and q["high_label"]
        if q["kind"] == "text":
            assert q["required"] is False                             # typing is never forced
    # the user's four named problems each have a question
    assert {"sync", "layout", "motion", "script", "language", "interaction", "correctness"} <= {q["area"] for q in questions}


def test_validation_requires_the_required_and_cleans_the_rest():
    with pytest.raises(ValueError, match="please answer"):
        feedback.validate({"overall": 5}, None, {1, 2})
    # an out-of-range rating and an unknown choice are NOT accepted as answers to required questions
    with pytest.raises(ValueError):
        feedback.validate({**GOOD, "understood": 9}, None, {1, 2})
    with pytest.raises(ValueError):
        feedback.validate({**GOOD, "pace": "sideways"}, None, {1, 2})
    answers, auto = feedback.validate(
        {**GOOD, "overall": "5", "main_idea": "  sin is  opposite by hypotenuse ", "hard_words": "x" * 900,
         "confusing_chapters": [2, "2", 7, "junk"], "best_chapter": [1, 2], "unknown": "dropped"},
        {"watch_mode": "full", "seconds_watched": "412", "completed": 1, "confused_at": [73.26, "x", -4, 12],
         "quiz": {"asked": 6, "answered": 5, "correct": 4, "skipped": 1, "wrong_ids": ["q2"], "retried_right": 1,
                  "sure_wrong_ids": ["q2"], "misconceptions": ["Thinks a heavier ball falls faster"], "extra": 9}}, {1, 2})
    assert answers["overall"] == 5 and answers["main_idea"] == "sin is opposite by hypotenuse"
    assert len(answers["hard_words"]) == feedback.MAX_TEXT and "unknown" not in answers
    assert answers["confusing_chapters"] == [2] and answers["best_chapter"] == [1]      # unknown chapters dropped; single-select
    assert auto == {"watch_mode": "full", "seconds_watched": 412, "completed": True, "confused_at": [0.0, 12.0, 73.3],
                    "quiz": {"asked": 6, "answered": 5, "correct": 4, "skipped": 1, "retried_right": 1, "wrong_ids": ["q2"],
                             "sure_wrong_ids": ["q2"], "misconceptions": ["Thinks a heavier ball falls faster"]}}


def test_reviews_are_stored_with_the_lesson_and_summarised_with_signals(lesson):
    job = lesson.name
    first = feedback.store(job, {"reviewer": "  Asha ", "answers": {**GOOD, "mistake": "It said teen bata char once",
                                                                  "confusing_chapters": [2]},
                                 "auto": {"confused_at": [35, 41.5], "completed": True,
                                          "quiz": {"asked": 4, "answered": 4, "correct": 1}}})
    second = feedback.store(job, {"answers": {**GOOD, "sync": 3, "pace": "too_fast", "screen_problem": "often",
                                              "confusing_chapters": [2, 1]},
                                  "auto": {"confused_at": [38], "quiz": {"asked": 4, "answered": 2, "correct": 1}}})
    assert first["stored"] and (first["count"], second["count"]) == (1, 2)
    saved = json.loads((lesson / "feedback" / f"{first['id']}.json").read_text())
    assert saved["reviewer"] == "Asha" and saved["lesson"]["language"] == "hinglish" and saved["form_version"] == feedback.FORM_VERSION
    assert len((lesson.parent.parent / "feedback.jsonl").read_text().splitlines()) == 2

    s = feedback.summarize(job)
    assert s["count"] == 2 and s["title"] == "Sine from two sides"
    assert s["ratings"]["sync"] == {"prompt": feedback.BY_ID["sync"]["prompt"], "area": "sync", "n": 2,
                                    "histogram": [0, 1, 1, 0, 0], "mean": 2.5}
    assert s["choices"]["pace"]["counts"] == {"too_slow": 0, "right": 1, "too_fast": 1}
    assert s["chapters"]["confusing_chapters"]["counts"] == {"2": 2, "1": 1}
    assert s["texts"]["mistake"]["items"][0]["text"].startswith("It said teen bata char")
    # all three presses fell in beat 02 (30–70 s): one moment, counted three times, with what was being said
    assert s["confused_at"] == [{"t": 30.0, "chapter": 2, "beat": "02", "count": 3, "said": "Sin theta equals three by four."}]
    assert s["quiz"] == {"responses": 2, "mean_correct_share": 0.25} and s["completed_share"] == 0.5
    areas = {x["area"] for x in s["signals"]}
    assert {"sync", "pacing", "layout", "correctness", "script"} <= areas       # low sync, too fast, screen problem, a mistake, quiz < 50%
    assert any("2.5 of 5" in x["message"] for x in s["signals"])

    everything = feedback.summarize_all()
    assert everything["reviews"] == 2 and everything["lessons"][0]["job_id"] == job and everything["lessons"][0]["sync"] == 2.5
    with pytest.raises(KeyError):
        feedback.store("../../etc", {"answers": GOOD})
    with pytest.raises(KeyError):
        feedback.summarize("20990101-000000-nolesn")
    with pytest.raises(ValueError):
        feedback.store(job, {"answers": {"overall": 5}})          # incomplete: nothing stored
    assert feedback.summarize(job)["count"] == 2


def test_a_lesson_with_no_reviews_has_an_empty_summary_and_no_signals(lesson):
    s = feedback.summarize(lesson.name)
    assert s["count"] == 0 and s["signals"] == [] and s["ratings"]["overall"]["mean"] is None


def test_the_tester_sheet_is_the_ten_questions_from_the_walkthrough_and_is_stored_apart(lesson):
    sheet = feedback.form("tester")
    assert sheet["kind"] == "tester" and len(sheet["questions"]) == 10 and len(sheet["tasks"]) == 6
    assert [q["id"] for q in sheet["questions"]] == ["role", "topics", "finished", "ease", "followups", "maths_correct",
                                                    "sync", "student_follow", "would_use", "fix_first"]
    assert feedback.form("student")["kind"] == "student"
    with pytest.raises(KeyError):
        feedback.form("nonsense")
    good = {"role": "teacher", "finished": "yes", "ease": 4, "followups": "helpful", "maths_correct": "small",
            "sync": 3, "student_follow": "with_help", "would_use": ["homework", "class", "junk", "class"]}
    with pytest.raises(ValueError, match="please answer"):
        feedback.store_tester({"answers": {**good, "would_use": []}})          # checkboxes: at least one
    first = feedback.store_tester({"job_id": lesson.name, "reviewer": "Ravi", "contact": "98xxxxxx01",
                                   "answers": {**good, "topics": "Sine", "fix_first": "1:20 label covers the triangle"}})
    feedback.store_tester({"job_id": "no-such-lesson", "answers": {**good, "finished": "gave_up", "sync": 2,
                                                                   "would_use": ["no"]}})
    saved = json.loads((lesson.parent.parent / "feedback" / "tester" / f"{first['id']}.json").read_text())
    assert saved["answers"]["would_use"] == ["class", "homework"] and saved["lesson_title"] == "Sine from two sides"
    s = feedback.summarize_testers()
    assert s["count"] == 2 and s["choices"]["would_use"]["counts"] == {"class": 1, "homework": 1, "share": 0, "no": 1}
    assert s["choices"]["would_use"]["multiple"] is True and s["ratings"]["sync"]["mean"] == 2.5
    assert s["lessons"] == ["Sine from two sides"] and "contact" not in json.dumps(s)
    areas = {x["area"] for x in s["signals"]}
    assert {"reliability", "correctness", "sync", "overall"} <= areas
    # tester forms never mix into the student summary
    assert feedback.summarize_all()["reviews"] == 0
