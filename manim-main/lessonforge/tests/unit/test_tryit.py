"""Try it yourself (``harness/tryit.py``): which tasks may be shown, what is kept of an answer,
and what a link may and may not fetch from a lesson folder. No model, no render."""
import json

import pytest
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.testclient import TestClient

from lessonforge.harness import api, gate, scripted, service, tryit

TASK = {"title": "Beans in a square", "kind": "hands", "materials": ["36 beans, or dots on squared paper"],
        "stands_for": "One bean is one unit; a full row is one factor.",
        "predict": "Which of 12, 16, 18 and 36 will close into a square?",
        "steps": ["1. Lay out 12 beans in equal rows.", "- Do the same with 16, 18 and 36.", "Write each number as primes."],
        "observe": "16 and 36 close into a square; 12 and 18 only make rectangles.",
        "question": "18 has a pair of 3s. Why is it not a square?",
        "expected": "Its 2 has no partner, so the two sides cannot be equal.",
        "write": "A number is a square when every prime factor has a partner.",
        "in_class": "Pairs of students, squared paper, five minutes."}


def test_a_task_is_shown_only_when_it_can_be_checked_and_is_safe():
    task, why = tryit.clean(TASK)
    assert why == "" and task["steps"][0] == "Lay out 12 beans in equal rows." and task["steps"][1].startswith("Do the same")
    assert set(task) == {"title", "kind", "materials", "stands_for", "predict", "steps", "observe", "question",
                         "expected", "write", "in_class"}
    for missing, reason in (("steps", "no steps"), ("predict", "nothing to guess"), ("question", "no question"),
                            ("expected", "no expected answer")):
        assert reason in tryit.clean({k: v for k, v in TASK.items() if k != missing})[1]
    assert "more than 5 steps" in tryit.clean({**TASK, "steps": list("abcdef")})[1]
    assert tryit.clean("do something")[0] is None
    # nothing that burns or cuts: by whole words, so ordinary words that contain one are fine
    for unsafe in ("Hold the paper over a candle flame.", "Cut the card with a knife.", "Add a few drops of acid.",
                   "Taste the water after the salt dissolves."):
        assert "unsafe" in tryit.clean({**TASK, "steps": [unsafe]})[1], unsafe
    for fine in ("Find the matching pair of beans.", "Gasp: the two piles are equal.", "Burnish nothing; fold the paper.",
                 "Put the socks in pairs.", "Cut the paper circle with scissors.", "Heat nothing: just fold it."):
        assert tryit.clean({**TASK, "steps": [fine]})[0] is not None, fine
    assert tryit.clean({**TASK, "kind": "explosion", "predict": {"question": "What will happen?", "options": ["a", "b"]}})[0] | {} \
        == {**task, "predict": "What will happen?"}


def test_the_task_is_found_in_the_lesson_or_in_its_card():
    assert tryit.task_of({"try_it": TASK})["title"] == "Beans in a square"
    assert tryit.task_of({"card": {"try_it": TASK}})["question"].startswith("18 has a pair")
    assert tryit.task_of({"card": {"try_it": {"steps": []}}}) is None and tryit.task_of({}) is None and tryit.task_of(None) is None


def test_the_card_is_shown_without_passages():
    card = {"big_idea": {"text": "A square has every prime factor twice.", "cites": ["S1#4"]},
            "the_why": {"text": "In n times n every prime of n arrives twice.", "cites": ["S1#5"]},
            "picture": {"text": "Factor tiles dealt into two equal hands.", "cites": [], "standard": "factor tree"},
            "opening_question": {"question": "Can 1764 ladoos sit in a square tray?", "guesses": ["yes"], "answer": "Yes, 42 by 42."},
            "mistakes": [{"mistake": "Pairing a 2 with a 3", "why_it_fails": "A pair is two of the same prime.", "cites": ["S2#1"]}, "junk"],
            "needs_first": [{"text": "Prime numbers", "cites": []}],
            "sources": [{"id": "S1", "kind": "textbook", "title": "NCERT Class 8, chapter 5", "url": "https://ncert.nic.in/x.pdf", "note": ""},
                        {"id": "S2", "kind": "given", "title": "The requester's notes", "url": "file:///etc/passwd"}],
            "problems": ["one"], "try_it": TASK}
    view = tryit.card_view({"card": card})
    assert view["big_idea"] == "A square has every prime factor twice." and view["picture"].startswith("Factor tiles")
    assert view["mistakes"] == [{"mistake": "Pairing a 2 with a 3", "why_it_fails": "A pair is two of the same prime."}]
    assert view["sources"][0]["url"].startswith("https://") and view["sources"][1]["url"] == ""      # only web links are links
    assert view["needs_first"] == ["Prime numbers"] and view["problems"] == 1
    assert view["picture_standard"] == "factor tree" and tryit.card_view({"card": {"big_idea": "x", "picture": "p"}})["picture_standard"] == ""
    assert "cites" not in json.dumps(view) and "S1#4" not in json.dumps(view)
    assert tryit.card_view({"card": {}}) is None and tryit.card_view({}) is None


@pytest.fixture
def lesson(tmp_path, monkeypatch):
    monkeypatch.setenv("LESSONFORGE_HOME", str(tmp_path))
    root = tmp_path / "lessons" / "20261009-000000-abc123"
    (root / "feedback").mkdir(parents=True)
    (root / "lesson.json").write_text(json.dumps({"title": "Squares", "chapters": [], "try_it": TASK}))
    (root / "teaching_pack.json").write_text(json.dumps({"chunks": [{"id": "S1#1", "text": "a passage of someone's book"}]}))
    (root / "feedback" / "r1.json").write_text("{}")
    return root


def test_an_answer_is_kept_with_the_lesson_and_the_reveal_comes_back(lesson):
    job = lesson.name
    with pytest.raises(ValueError, match="what you saw"):
        tryit.store(job, {"prediction": "all of them"})
    first = tryit.store(job, {"prediction": "all of them", "observation": " 16 and 36  closed ", "answer": "x" * 900,
                              "reviewer": "Asha", "done_in_class": 1})
    assert first["stored"] and first["count"] == 1 and first["expected"] == TASK["expected"] and first["observe"] == TASK["observe"]
    kept = json.loads(next((lesson / "tryit").glob("*.json")).read_text())
    assert kept["observation"] == "16 and 36 closed" and len(kept["answer"]) == tryit.MAX_ANSWER and kept["done_in_class"] is True
    tryit.store(job, {"answer": "the two has no partner"})
    summary = tryit.summarize(job)
    assert summary["count"] == 2 and summary["answers"][0]["answer"] == "the two has no partner" and summary["task"]["title"]
    for bad in ("nope", "../etc", ".hidden"):
        with pytest.raises(KeyError):
            tryit.store(bad, {"answer": "x"})
    (lesson / "lesson.json").write_text(json.dumps({"title": "No task", "chapters": []}))
    with pytest.raises(KeyError):
        tryit.store(job, {"answer": "x"})


def test_a_student_link_may_answer_the_task_and_nobody_fetches_the_private_files(lesson):
    app = FastAPI()
    app.include_router(api.router)
    app.mount("/lessons", StaticFiles(directory=str(lesson.parent)), name="lessons")
    gate.install(app, access_token="owner-key", review_token="review-key")
    client = TestClient(app)
    job = lesson.name
    owner, student = {"X-Access-Token": "owner-key"}, {"X-Access-Token": "review-key"}
    sent = client.post(f"/api/harness/jobs/{job}/tryit", json={"observation": "16 closed", "answer": "no partner"}, headers=student)
    assert sent.status_code == 200 and sent.json()["expected"] == TASK["expected"]
    assert client.post(f"/api/harness/jobs/{job}/tryit", json={"prediction": "hm"}, headers=student).status_code == 400
    assert client.post("/api/harness/jobs/nope/tryit", json={"answer": "x"}, headers=student).status_code == 404
    # reading what others wrote is the owner's
    assert client.get(f"/api/harness/jobs/{job}/tryit", headers=student).status_code == 403
    assert client.get(f"/api/harness/jobs/{job}/tryit", headers=owner).json()["count"] == 1
    # the lesson itself is served; the sources' text, the reviews and the answers are not, to anyone
    assert client.get(f"/lessons/{job}/lesson.json", headers=student).status_code == 200
    stored = next((lesson / "tryit").glob("*.json")).name
    for private in ("teaching_pack.json", "feedback/r1.json", f"tryit/{stored}", "./teaching_pack.json", "TEACHING_PACK.JSON"):
        for who in (owner, student):
            assert client.get(f"/lessons/{job}/{private}", headers=who).status_code == 404, private
    assert client.get(f"/lessons/{job}/lesson.json").status_code == 401


def test_a_pasted_script_gets_a_task_from_its_director_and_an_unsafe_one_is_left_out():
    script = ("A fraction names a part of a whole. Cut a roti into four equal pieces and take one. You now hold one fourth "
              "of the roti, and three fourths are still on the plate in front of you.")

    def director(task):
        def model(prompt, system):
            if system is scripted.PLAN_SYSTEM:
                assert '"try_it"' in system and "Nothing that burns, cuts" in system
                return {"title": "One fourth", "chapters": [], "try_it": task}
            return {"beats": [{"id": "01", "steps": [{"say": "A fraction names", "show": "1/4", "kind": "math"}]}]}
        return model

    log = []
    made = scripted.script_lesson(scripted.prepare({"mode": "script", "script": script}), director(TASK), log=log.append)
    assert made["try_it"]["title"] == "Beans in a square" and any("try-it-yourself task goes with" in line for line in log)
    assert [b["narration"] for c in made["chapters"] for b in c["beats"]][0].startswith("A fraction names")   # not a word added
    log.clear()
    unsafe = scripted.script_lesson(scripted.prepare({"mode": "script", "script": script}),
                                    director({**TASK, "steps": ["Cut the roti with a knife."]}), log=log.append)
    assert "try_it" not in unsafe and any("left out" in line and "knife" in line for line in log)
    assert "try_it" not in scripted.script_lesson(scripted.prepare({"mode": "script", "script": script}), director(None), log=log.append)
    assert service.results_from_disk.__doc__                      # (the job record carries it: see tests/integration)


def test_a_lesson_the_account_cannot_pay_for_is_refused_before_anything_is_spent(tmp_path, monkeypatch):
    """2026-10-09: 0.57 USD of account credit left under a 20 USD cap; a 16-minute lesson paid for its script and
    animations and was then narrated by the fallback voice."""
    from lessonforge import spend
    monkeypatch.setenv("LESSONFORGE_HOME", str(tmp_path))
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")
    monkeypatch.setattr(spend, "account_credit", lambda max_age=60.0: 0.57)
    script = " ".join(["Riya counts the tiles on her grandfather's floor and writes the number down."] * 160)   # ~16 minutes
    with pytest.raises(spend.BudgetExceeded, match="0.57 USD of credit left"):
        service.start_job({"mode": "script", "script": script})
    with pytest.raises(spend.BudgetExceeded, match="Nothing was started"):
        service.start_job({"topic": "Fractions", "duration_minutes": 6})
    assert not list((tmp_path / "lessons").glob("*")) if (tmp_path / "lessons").exists() else True
    app = FastAPI()
    app.include_router(api.router)
    seen = {}
    monkeypatch.setattr(service, "start_job", lambda brief, **kw: seen.update(brief) or {"job_id": "x"})
    TestClient(app).post("/api/harness/generate", json={"brief": {"topic": "Fractions", "draft_file": "/etc/passwd"}})
    assert seen == {"topic": "Fractions"}                     # a path on the server never arrives over HTTP
    monkeypatch.undo()
    monkeypatch.setenv("LESSONFORGE_HOME", str(tmp_path))
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")
    monkeypatch.setattr(spend, "account_credit", lambda max_age=60.0: 0.57)
    refused = TestClient(app).post("/api/harness/generate", json={"brief": {"topic": "Fractions"}})
    assert refused.status_code == 402 and "openrouter.ai/settings/credits" in refused.json()["detail"]
    # unknown credit is not zero credit, and a short lesson fits what is left
    assert spend.lesson_estimate(1) < 0.57 < spend.lesson_estimate(6)
    monkeypatch.setattr(spend, "account_credit", lambda max_age=60.0: None)
    spend.ensure_credit(5.0)
    summary_line = spend.format_summary({"ledger": "x", "calls": 1, "spent": 14.36, "budget": 20.0, "remaining": 5.64,
                                         "key_usage_since_baseline": 17.18, "account_credit": 0.57, "by_kind": {}, "by_model": {}})
    assert "account credit left (OpenRouter): $0.57" in summary_line and "run out before the budget" in summary_line


# ── runs: made elsewhere, stopped, removed (service.remove_job) ──────────────

def _folder(tmp_path, job_id, record=None, lesson=True):
    root = tmp_path / "lessons" / job_id
    root.mkdir(parents=True)
    if lesson:
        (root / "lesson.draft.json").write_text(json.dumps({"title": "Squares", "chapters": []}))
    if record is not None:
        (root / "job.json").write_text(json.dumps({"job_id": job_id, "title": "Squares", "brief": {"topic": "Squares"},
                                                   "created": 1.0, "progress": [], **record}))
    return root


def test_a_lesson_another_process_is_making_is_running_not_failed(tmp_path, monkeypatch):
    """Four lessons a command-line batch was making were listed as "failed … Start it again" (2026-10-09);
    "Try again" was pressed on each: four duplicates at full price."""
    monkeypatch.setenv("LESSONFORGE_HOME", str(tmp_path))
    service._JOBS.clear()
    _folder(tmp_path, "20261009-120614-aaaaaa", {"status": "running", "stage": "verify", "pid": 4242})
    _folder(tmp_path, "20261009-120615-bbbbbb", {"status": "running", "stage": "speech", "pid": 4343})
    _folder(tmp_path, "20261009-120616-cccccc", {"status": "running", "stage": "speech"})          # an older record: no pid
    monkeypatch.setattr(service, "_alive", lambda pid: pid == 4242)
    live, dead, old = (service.get_job(i) for i in ("20261009-120614-aaaaaa", "20261009-120615-bbbbbb", "20261009-120616-cccccc"))
    assert (live["status"], live["stage"], live["error"]) == ("running", "verify", None) and live["note"] == service.ELSEWHERE
    assert dead["status"] == "failed" and dead["error"] == service.INTERRUPTED
    assert old["status"] == "failed" and old["error"] == service.INTERRUPTED
    assert {r["job_id"][-6:]: r["status"] for r in service.list_jobs()} == {"aaaaaa": "running", "bbbbbb": "failed", "cccccc": "failed"}
    assert {r["job_id"][-6:]: r["elsewhere"] for r in service.list_jobs()} == {"aaaaaa": True, "bbbbbb": False, "cccccc": False}
    # when that process dies the reading changes; it is taken from the files every time, never remembered
    monkeypatch.setattr(service, "_alive", lambda pid: False)
    assert service.get_job("20261009-120614-aaaaaa")["status"] == "failed"
    # and it cannot be pulled out from under the process that is writing it
    monkeypatch.setattr(service, "_alive", lambda pid: pid == 4242)
    with pytest.raises(ValueError, match="still making this lesson"):
        service.remove_job("20261009-120614-aaaaaa")
    assert (tmp_path / "lessons" / "20261009-120614-aaaaaa").is_dir()


def test_a_run_is_stopped_at_its_next_stage_and_moved_aside_not_deleted(tmp_path, monkeypatch):
    monkeypatch.setenv("LESSONFORGE_HOME", str(tmp_path))
    service._JOBS.clear()
    # a failed run nobody owns: moved at once, with everything in it
    root = _folder(tmp_path, "20261009-110000-dddddd", {"status": "failed", "error": "boom"})
    (root / "feedback").mkdir()
    assert service.remove_job("20261009-110000-dddddd") == {"removed": True, "stopping": False}
    assert not root.exists() and (tmp_path / "removed" / "20261009-110000-dddddd" / "feedback").is_dir()
    with pytest.raises(KeyError):
        service.remove_job("20261009-110000-dddddd")
    for bad in ("../lessons", ".hidden", "nope"):
        with pytest.raises(KeyError):
            service.remove_job(bad)
    # a run of this process that is still waiting for a worker: asked to stop, gone from the list at once …
    waiting = {"job_id": "20261009-110100-eeeeee", "status": "queued", "stage": "queued", "stages": service.STAGES, "progress": [],
               "title": "Squares", "brief": {"topic": "Squares"}, "created": 2.0, "pid": 1, "_owned": True,
               "_quality": "l", "_voice": "silent", "_llm": lambda prompt, system: pytest.fail("a stopped run called the model")}
    _folder(tmp_path, waiting["job_id"], {"status": "queued"}, lesson=False)
    service._JOBS[waiting["job_id"]] = waiting
    assert service.remove_job(waiting["job_id"]) == {"removed": False, "stopping": True}
    assert waiting["job_id"] not in [r["job_id"] for r in service.list_jobs()]
    # … and when its worker reaches it, nothing is written, narrated or paid for, and the folder is moved aside
    service._run(waiting)
    assert waiting["status"] == "failed" and waiting["error"] == service.STOPPED and waiting["_owned"] is False
    moved = tmp_path / "removed" / waiting["job_id"]
    assert moved.is_dir() and not (tmp_path / "lessons" / waiting["job_id"]).exists()
    assert json.loads((moved / "job.json").read_text())["error"] == service.STOPPED
    assert waiting["job_id"] not in service._JOBS
    # over HTTP: the owner may remove, a review link may not
    app = FastAPI()
    app.include_router(api.router)
    gate.install(app, access_token="owner-key", review_token="review-key")
    client = TestClient(app)
    _folder(tmp_path, "20261009-110200-ffffff", {"status": "failed", "error": "boom"})
    assert client.post("/api/harness/jobs/20261009-110200-ffffff/remove", json={}, headers={"X-Access-Token": "review-key"}).status_code == 403
    assert client.post("/api/harness/jobs/20261009-110200-ffffff/remove", json={}, headers={"X-Access-Token": "owner-key"}).json() == {"removed": True, "stopping": False}
    assert client.post("/api/harness/jobs/20261009-110200-ffffff/remove", json={}, headers={"X-Access-Token": "owner-key"}).status_code == 404


# ── the reviewer's teaching checks (plan step 4): reported, not enforced ─────

def test_a_lesson_written_from_a_card_is_asked_the_skills_teaching_questions_and_nothing_is_rewritten_for_them():
    from lessonforge.harness import critic, frameworks, writer
    brief = {"topic": "Square numbers", "audience": "Class 8", "grade": 8, "level": "foundation", "goal": "tell a square by its factors",
             "framework": "concrete_first", "style": "tutor", "language": "en-IN", "duration_minutes": 2}
    raw = {"title": "Squares", "anchor": "36 dots", "chapters": [{"beats": [
        {"narration": "Can thirty-six dots sit in a square? Guess before we lay them out on the page.",
         "steps": [{"say": "thirty-six dots", "show": "36 dots", "kind": "point"}]},
        {"narration": "They can, because every prime factor of thirty-six has a partner in the other row.",
         "steps": [{"say": "every prime factor", "show": "Every factor paired", "kind": "key"}]}]}]}
    lesson = writer.discipline(raw, brief, frameworks.get("concrete_first"))
    questions = critic.teaching_questions()
    assert len(questions) >= 10 and all(q.endswith(("?", ")")) for q in questions) and "WHY" in " ".join(questions)
    seen = {}

    def reviewer(prompt, system):
        seen["prompt"] = prompt
        return {"scores": {k: 4 for k in critic.RUBRIC}, "findings": [], "claims": [], "edits": [], "summary": "fine",
                "teaching": [{"check": 1, "pass": True, "beat": "beat-01", "evidence": "Can thirty-six dots"},
                             {"check": 3, "pass": True, "beat": "02", "evidence": "because every prime factor"},
                             {"check": 8, "pass": False, "beat": "02", "fix": "state the pairing of a 2 with a 3 and show it fail"},
                             {"check": 99, "pass": False}, {"check": "x"}, "junk", {"check": 3, "pass": False}]}

    # without a card the reviewer is asked what it was always asked
    plain = critic.review(lesson, reviewer, log=lambda *_: None)
    assert "TEACHING" not in seen["prompt"] and '"teaching"' not in seen["prompt"] and "teaching" not in plain
    lesson["card"] = {"big_idea": {"text": "A square has every prime factor twice.", "cites": ["S1#2"]},
                      "the_why": {"text": "In n times n every prime of n arrives twice."}, "picture": {"text": "Tiles in two equal hands."},
                      "opening_question": {"question": "Can 36 dots sit in a square?", "answer": "Yes, 6 by 6."},
                      "mistakes": [{"mistake": "Pairing a 2 with a 3", "why_it_fails": "A pair is two of the same prime."}],
                      "try_it": {"title": "Beans in a square", "predict": "Which numbers close?", "question": "Why not 18?"}}
    report = critic.verify(lesson, reviewer, log=lambda *_: None)
    prompt = seen["prompt"]
    assert "THE TEACHING CARD" in prompt and "In n times n every prime of n arrives twice." in prompt and "Pairing a 2 with a 3" in prompt
    assert all(f"  {n}. {q}" in prompt for n, q in enumerate(questions, 1)) and "S1#2" not in prompt and '"teaching": [' in prompt
    teaching = report["teaching"]
    assert (teaching["passed"], teaching["of"], teaching["unanswered"]) == (2, len(questions), len(questions) - 3)
    assert [c["check"] for c in teaching["checks"]] == [1, 3, 8] and teaching["checks"][0]["beat"] == "01"
    assert teaching["checks"][1]["pass"] is True                                  # the first answer for a check stands
    # a check that is not met is said, as a minor finding: no rewrite is asked for and the lesson still passes
    noted = [f for f in report["findings"] if f["what"].startswith("teaching check")]
    assert len(noted) == 1 and noted[0]["severity"] == "minor" and noted[0]["beat"] == "02" and "show it fail" in noted[0]["fix"]
    assert report["status"] == "passed" and report["beats_rewritten"] == [] and report["major_unresolved"] == 0


def test_a_lesson_the_cap_cannot_cover_is_refused_before_it_starts(monkeypatch):
    """The cap is checked for the whole lesson up front, by whichever count is further along."""
    from lessonforge import spend
    monkeypatch.setattr(spend, "budget", lambda: 30.0)
    monkeypatch.setattr(spend, "spent", lambda: 25.0)                 # the ledger runs behind ...
    monkeypatch.setattr(spend, "baseline", lambda: 1.5)
    monkeypatch.setattr(spend, "remote_usage", lambda max_age=30.0: 30.4)   # ... OpenRouter's own count: 28.90 used
    assert abs(spend.room() - 1.10) < 1e-9
    spend.ensure_room(0.34, "the narration of about 9 minute(s)")     # adding a voice fits
    with pytest.raises(spend.BudgetExceeded, match="leaves 1.10 and a lesson of about 9 minute"):
        spend.ensure_room(spend.lesson_estimate(8.6), "a lesson of about 9 minute(s)")
    assert spend.lesson_estimate(8.6) > 1.2 and spend.narration_estimate(8.6) < 0.4
    monkeypatch.setattr(spend, "remote_usage", lambda max_age=30.0: None)   # OpenRouter not reachable: the ledger alone
    assert spend.room() == 5.0
    monkeypatch.setattr(spend, "budget", lambda: None)                # no cap set: nothing is refused
    assert spend.room() is None
    spend.ensure_room(1000.0)


def test_a_chapter_with_something_outside_the_stage_is_laid_out_again_like_one_with_an_overlap():
    report = {"layout_findings": {"counted": 1, "detail": [{"chapter": 3, "counted": True}, {"chapter": 5, "counted": False}]},
              "bounds_violations": 2, "bounds_detail": [{"chapter": 7, "beat": "07"}, {"chapter": 3, "beat": "03"}]}
    assert service.chapters_to_relay(report) == [3, 7] and service.layout_faults(report) == 3
    # a re-lay is kept only when the TOTAL drops: curing the overlap by pushing something off the stage is no cure
    traded = {"layout_findings": {"counted": 0, "detail": []}, "bounds_violations": 3, "bounds_detail": []}
    better = {"layout_findings": {"counted": 0, "detail": []}, "bounds_violations": 1, "bounds_detail": [{"chapter": 7}]}
    assert not service.layout_faults(traded) < service.layout_faults(report) and service.layout_faults(better) < service.layout_faults(report)
    older = {"layout_findings": {"counted": 0, "detail": []}}             # a report written before bounds_detail existed
    assert service.chapters_to_relay(older) == [] and service.layout_faults(older) == 0


def test_reconciling_the_ledger_keeps_what_another_process_wrote_meanwhile(tmp_path, monkeypatch):
    """`lessonforge spend` corrects estimated rows; a row the server appends while it asks OpenRouter must survive."""
    import json as _json
    from lessonforge import spend
    ledger = tmp_path / "spend.jsonl"
    monkeypatch.setattr(spend, "ledger_path", lambda: ledger)
    spend.record("tts", "google/gemini-3.8-flash-tts", 0.01, generation_id="gen-1", estimated=True, note="20 words")
    spend.record("chat", "openai/gpt-5.6-terra", 0.05, generation_id="gen-2", note="code")

    def billed_later(generation_id, tries=4, wait=1.0):
        # while this "HTTP call" is in flight, the server writes another row
        with ledger.open("a", encoding="utf-8") as fh:
            fh.write(_json.dumps({"at": 1.0, "kind": "chat", "model": "m", "cost": 0.07, "prompt_tokens": 0, "completion_tokens": 0,
                                  "reasoning_tokens": 0, "seconds": None, "note": "written meanwhile",
                                  "generation_id": "gen-3", "estimated": False}) + "\n")
        return {"cost": 0.0123, "prompt_tokens": 5, "completion_tokens": 50, "model": "m"}

    monkeypatch.setattr(spend, "generation_cost", billed_later)
    assert spend.reconcile() == 1
    rows = spend.entries()
    assert [r["generation_id"] for r in rows] == ["gen-1", "gen-2", "gen-3"]          # nothing lost
    assert rows[0]["cost"] == 0.0123 and rows[0]["estimated"] is False and rows[2]["note"] == "written meanwhile"
    assert abs(spend.spent() - (0.0123 + 0.05 + 0.07)) < 1e-9
