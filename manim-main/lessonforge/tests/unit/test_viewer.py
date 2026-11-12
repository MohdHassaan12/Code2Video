"""The viewer site on Render and what the studio publishes for it (``lessonforge/cloud.py``, ``harness/publish.py``,
``lessonforge/viewer.py``).

No Cloudflare: ``LESSONFORGE_CLOUD_DIR`` stands in for R2 (a folder) and D1 (an SQLite file running the same
SQL). A real finished-lesson folder is published from a studio workspace and read back through the viewer.
"""
import json
import shutil
import sqlite3
from collections import OrderedDict

import pytest
from fastapi.testclient import TestClient

from lessonforge import cloud, viewer
from lessonforge.harness import analytics, gate, publish, service

JOB = "20261015-101500-a1b2c3"
TASK = {"title": "Beans in a square", "kind": "hands", "materials": ["36 beans"],
        "predict": "Which of 12, 16 and 36 will close into a square?",
        "steps": ["Lay out 12 beans in equal rows.", "Do the same with 16 and 36."],
        "observe": "16 and 36 close into a square; 12 makes only rectangles.",
        "question": "Why is 12 not a square?", "expected": "Its 3 has no partner, so the sides cannot be equal."}
CLOUD_SETTINGS = cloud.R2_SETTINGS + cloud.D1_SETTINGS + (cloud.TOKEN, cloud.EMAIL, cloud.GLOBAL_KEY)


def finished_lesson(home, job_id=JOB, title="Squares"):
    """A lesson folder as a finished run leaves it, with the private and the bulky things a run also leaves."""
    root = home / "lessons" / job_id
    for sub in ("output", "feedback", "tryit", "audio", "logs", "media/C01/videos"):
        (root / sub).mkdir(parents=True, exist_ok=True)
    brief = {"topic": "Square numbers", "language": "en-IN", "duration_minutes": 3, "grade": 8,
             "framework": "concrete_first", "card": True}
    lesson = {"title": title, "brief": brief, "framework": "concrete_first", "try_it": TASK, "chapters": [
        {"id": 1, "title": "Dots", "role": "hook", "beats": [
            {"id": "01", "narration": "Can thirty-six dots sit in a square?", "thinking_pause_seconds": 3},
            {"id": "02", "narration": "They can. Six rows of six."}]},
        {"id": 2, "title": "Why", "role": "recap", "beats": [{"id": "03", "narration": "Every factor has a partner."}]}]}
    (root / "lesson.json").write_text(json.dumps(lesson))
    (root / "timeline.json").write_text(json.dumps([
        {"id": "01", "chapter": 1, "start": 0.0, "duration": 6.0, "speech_end": 3.5,
         "sentences": [{"text": "Can thirty-six dots sit in a square?", "start": 0.5, "duration": 3.0}]},
        {"id": "02", "chapter": 1, "start": 6.0, "duration": 4.0, "sentences": []},
        {"id": "03", "chapter": 2, "start": 10.0, "duration": 4.0, "sentences": []}]))
    (root / "output" / "final_checks.json").write_text(json.dumps({
        "status": "technical_checks_passed", "video": "squares.mp4", "duration_seconds": 14.0, "chapters": 2, "beats": 3,
        "captions": 1, "checks": [{"check": "x", "passed": True}]}))
    (root / "output" / "squares.mp4").write_bytes(bytes(range(256)) * 64)
    (root / "output" / "captions.vtt").write_text("WEBVTT\n\n00:00.500 --> 00:03.500\nCan thirty-six dots sit in a square?\n")
    (root / "review.html").write_text(
        '<video><source src="output/squares.mp4"><track src="output/captions.vtt"></video>'
        '<a href="narrative.md">n</a><a href="storyboard.md">s</a><a href="output/final_checks.json">c</a>'
        '<a href="teaching_pack.json">sources</a><a href="../other/lesson.json">x</a><a href="https://example.com/a">e</a>'
        '<a href="logs/C01.log">log</a>')
    (root / "narrative.md").write_text("# Squares\n")
    (root / "storyboard.md").write_text("# Board\n")
    (root / "teaching_pack.json").write_text(json.dumps({"chunks": [{"id": "S1#1", "text": "someone's book"}]}))
    (root / "teaching_card.json").write_text("{}")
    (root / "feedback" / "r1.json").write_text("{}")
    (root / "tryit" / "a1.json").write_text("{}")
    (root / "audio" / "beat_01.wav").write_bytes(b"RIFF")
    (root / "logs" / "C01.log").write_text("render log")
    (root / "media" / "C01" / "videos" / "partial.mp4").write_bytes(b"\x00")
    (root / "job.json").write_text(json.dumps({"job_id": job_id, "status": "done", "stage": "done", "title": title,
                                               "created": 1791441000.0, "brief": brief, "progress": ["done"],
                                               "voice": "kokoro"}))
    return root


@pytest.fixture
def studio(tmp_path, monkeypatch):
    for name in CLOUD_SETTINGS + ("LESSONFORGE_ACCESS_TOKEN", "LESSONFORGE_REVIEW_TOKEN", "LESSONFORGE_WEB_APP"):
        monkeypatch.delenv(name, raising=False)
    home = tmp_path / "studio"
    monkeypatch.setenv("LESSONFORGE_HOME", str(home))
    monkeypatch.setenv("LESSONFORGE_CLOUD_DIR", str(tmp_path / "cloud"))
    monkeypatch.setattr(service, "_JOBS", OrderedDict())
    monkeypatch.setattr(analytics, "_RATE", {})
    analytics._CTX.set(None)
    finished_lesson(home)
    return home


def database_rows(tmp_path, sql):
    conn = sqlite3.connect(tmp_path / "cloud" / "d1.sqlite3")
    try:
        return conn.execute(sql).fetchall()
    finally:
        conn.close()


# ── publishing ───────────────────────────────────────────────────────────────

def test_publishing_sends_the_record_the_list_and_only_the_files_the_app_reads_and_again_sends_nothing(studio):
    said = []
    report = publish.publish([JOB], log=said.append)
    assert report["published"] == [JOB] and report["skipped"] == {} and said and JOB in said[0]
    store = cloud.objects()
    files = {key[len(f"lessons/{JOB}/"):] for key in store.list(f"lessons/{JOB}/")}
    # what the record points at, and what its review page links to; nothing private, no render cache, no logs
    assert files == {"output/squares.mp4", "output/captions.vtt", "output/interactions.json", "output/outline.json",
                     "lesson.json", "review.html", "narrative.md", "storyboard.md", "output/final_checks.json"}
    for rel in files:
        assert not gate.PRIVATE_IN_LESSON.match(f"/lessons/{JOB}/{rel}")
    assert store.get_bytes(f"lessons/{JOB}/output/squares.mp4") == (studio / "lessons" / JOB / "output" / "squares.mp4").read_bytes()
    # the cloud holds exactly what the studio's routes answer
    assert store.get_json(cloud.job_key(JOB)) == json.loads(json.dumps(service.get_job(JOB)))
    assert store.get_json(cloud.JOBS_KEY) == {"jobs": json.loads(json.dumps(service.list_jobs()))}
    assert set(store.list("")) == {cloud.JOBS_KEY, cloud.job_key(JOB)} | {f"lessons/{JOB}/{rel}" for rel in files}

    again = publish.publish([JOB], log=said.append)
    assert again["sent"] == 0 and again["unchanged"] == len(files) + 2 and again["bytes"] == 0

    # a lesson that is not finished is not published, and says why
    other = finished_lesson(studio, "20261015-111111-ffffff", title="Cut short")
    (other / "output" / "squares.mp4").unlink()
    (other / "job.json").write_text(json.dumps({"job_id": other.name, "status": "running", "stage": "speech",
                                                "created": 1791442000.0, "title": "Cut short", "brief": {}, "pid": 1}))
    service._JOBS.clear()
    skipped = publish.publish([other.name, "../etc", "nope-nope"], log=said.append)
    assert skipped["published"] == [] and set(skipped["skipped"]) == {other.name, "../etc", "nope-nope"}
    assert [row["job_id"] for row in store.get_json(cloud.JOBS_KEY)["jobs"]] == [JOB]


def test_publishing_everything_lists_newest_first_and_takes_off_what_left_the_studio(studio):
    finished_lesson(studio, "20261016-090000-bbbbbb", title="Cubes")
    json_path = studio / "lessons" / "20261016-090000-bbbbbb" / "job.json"
    record = json.loads(json_path.read_text())
    json_path.write_text(json.dumps({**record, "created": 1791530000.0}))
    report = publish.publish(everything=True, log=lambda *_: None)
    store = cloud.objects()
    assert sorted(report["published"]) == [JOB, "20261016-090000-bbbbbb"]
    assert [row["job_id"] for row in store.get_json(cloud.JOBS_KEY)["jobs"]] == ["20261016-090000-bbbbbb", JOB]
    # taken out of the history on the studio (moved to removed/), while publishing was off: --all takes it off
    shutil.move(str(studio / "lessons" / JOB), str(studio / "removed"))
    service._JOBS.clear()
    dry = publish.publish(everything=True, dry_run=True, log=lambda *_: None)
    assert dry["removed"] == [JOB] and store.get_json(cloud.job_key(JOB))            # a dry run changes nothing
    report = publish.publish(everything=True, log=lambda *_: None)
    assert report["removed"] == [JOB] and store.get_json(cloud.job_key(JOB)) is None
    assert store.list(f"lessons/{JOB}/") == [] and [r["job_id"] for r in store.get_json(cloud.JOBS_KEY)["jobs"]] == ["20261016-090000-bbbbbb"]


def test_a_lesson_removed_on_the_studio_leaves_the_site_and_a_finished_one_publishes_itself(studio, monkeypatch):
    assert publish.wanted() is False                                    # tests switch it off (conftest)
    monkeypatch.setenv("LESSONFORGE_PUBLISH", "1")
    assert publish.wanted() is True
    assert publish.after_lesson(JOB, log=lambda *_: None)["published"] == [JOB]
    store = cloud.objects()
    assert store.get_json(cloud.job_key(JOB))["status"] == "done"
    assert service.remove_job(JOB) == {"removed": True, "stopping": False}
    assert store.get_json(cloud.job_key(JOB)) is None and store.list(f"lessons/{JOB}/") == []
    assert store.get_json(cloud.JOBS_KEY) == {"jobs": []}
    # not set up: nothing is attempted, and a removal never fails for the site's sake
    monkeypatch.delenv("LESSONFORGE_CLOUD_DIR")
    assert publish.wanted() is False and publish.after_removal("20261015-000000-zzzzzz") is None


def test_the_service_settings_say_what_is_missing(monkeypatch):
    for name in CLOUD_SETTINGS + ("LESSONFORGE_ACCESS_TOKEN",):
        monkeypatch.delenv(name, raising=False)               # the owner's .env may hold real ones
    with pytest.raises(cloud.NotConfigured) as missing:
        cloud.objects()
    assert "CLOUDFLARE_R2_BUCKET" in str(missing.value) and "LESSONFORGE_CLOUD_DIR" in str(missing.value)
    with pytest.raises(cloud.NotConfigured) as missing:
        cloud.database()
    assert "CLOUDFLARE_D1_DATABASE_ID" in str(missing.value) and "CLOUDFLARE_API_TOKEN" in str(missing.value)
    client = TestClient(viewer.create_app())
    assert client.get("/healthz").json()["objects"] is None
    refused = client.get("/api/harness/jobs")
    assert refused.status_code == 503 and "CLOUDFLARE_R2_ACCESS_KEY_ID" in refused.json()["detail"]


def test_d1_is_asked_in_its_rest_shape_and_its_rows_read_back(monkeypatch):
    import httpx
    sent = {}

    def post(url, json=None, headers=None, timeout=None):
        sent.update(url=url, body=json, headers=headers)
        return httpx.Response(200, json={"success": True, "errors": [], "messages": [],
                                         "result": [{"success": True, "meta": {}, "results": [{"n": 2}]}]})

    monkeypatch.setattr(httpx, "post", post)
    db = cloud.D1("acct", "db-1", token="tok")
    assert db.query("SELECT COUNT(*) AS n FROM tryit WHERE job_id = ? AND done_in_class = ?", ["j", True]) == [{"n": 2}]
    assert sent["url"] == "https://api.cloudflare.com/client/v4/accounts/acct/d1/database/db-1/query"
    assert sent["body"] == {"sql": "SELECT COUNT(*) AS n FROM tryit WHERE job_id = ? AND done_in_class = ?", "params": ["j", 1]}
    assert sent["headers"] == {"Authorization": "Bearer tok"}
    assert cloud.D1("acct", "db-1", email="me@example.com", key="k").headers == {"X-Auth-Email": "me@example.com", "X-Auth-Key": "k"}
    monkeypatch.setattr(httpx, "post", lambda *a, **k: httpx.Response(400, json={"success": False, "errors": [{"message": "no such table"}]}))
    with pytest.raises(cloud.CloudError, match="no such table"):
        db.query("SELECT 1")


def test_r2_skips_an_object_it_already_has_and_signs_links_without_asking(tmp_path):
    pytest.importorskip("boto3")
    from botocore.stub import Stubber
    r2 = cloud.R2("acct", "lessons-bucket", "key-id", "secret")
    video = tmp_path / "v.mp4"
    video.write_bytes(b"0123456789")
    md5 = cloud._md5_file(video)
    with Stubber(r2.s3) as stub:
        stub.add_response("head_object", {"ContentLength": 10, "ETag": '"abc-2"', "Metadata": {"md5": md5}},
                          {"Bucket": "lessons-bucket", "Key": "lessons/j/v.mp4"})
        assert r2.upload_file(video, "lessons/j/v.mp4") is False                     # same size and content: not sent
        stub.assert_no_pending_responses()
    link = r2.presign("lessons/j/output/squares.mp4")
    assert link.startswith("https://acct.r2.cloudflarestorage.com/lessons-bucket/lessons/j/output/squares.mp4?")
    assert "X-Amz-Signature=" in link and "X-Amz-Expires=" in link


# ── the viewer ───────────────────────────────────────────────────────────────

MAKING = [("POST", "/api/harness/generate"), ("POST", "/api/harness/sessions"), ("GET", "/api/harness/sessions/abc"),
          ("POST", "/api/harness/sessions/abc/answer"), ("POST", "/api/harness/sessions/abc/generate"),
          ("POST", "/api/harness/script/preview"), ("POST", "/api/harness/plan"), ("POST", f"/api/harness/jobs/{JOB}/remove"),
          ("POST", f"/api/harness/jobs/{JOB}/voice"), ("POST", f"/api/harness/jobs/{JOB}/cuts/standard"),
          ("POST", "/api/harness/anything/new")]


def test_the_viewer_shows_what_was_published_and_makes_nothing(studio):
    publish.publish([JOB], log=lambda *_: None)
    client = TestClient(viewer.create_app())
    assert client.get("/healthz").json() == {"ok": True, "mode": "viewer", "objects": "local", "database": "local", "missing": []}
    assert client.get("/api/harness/mode").json() == {"mode": "viewer"}
    assert client.get("/api/harness/jobs").json() == {"jobs": json.loads(json.dumps(service.list_jobs()))}
    record = client.get(f"/api/harness/jobs/{JOB}").json()
    assert record == json.loads(json.dumps(service.get_job(JOB))) and record["try_it"]["title"] == TASK["title"]
    assert client.get("/api/harness/jobs/20261015-000000-nothere").status_code == 404
    # the video is a redirect to a signed link, which serves ranges; small files come through
    moved = client.get(record["video_url"], follow_redirects=False)
    assert moved.status_code == 307 and moved.headers["location"].startswith(f"/_cloud/object/lessons/{JOB}/output/squares.mp4?")
    video = (studio / "lessons" / JOB / "output" / "squares.mp4").read_bytes()
    assert client.get(record["video_url"]).content == video
    part = client.get(moved.headers["location"], headers={"Range": "bytes=256-511"})
    assert part.status_code == 206 and part.content == video[256:512]
    assert client.get(moved.headers["location"].replace("s=", "s=0")).status_code == 403          # a forged link
    captions = client.get(record["captions_url"])
    assert captions.status_code == 200 and captions.headers["content-type"].startswith("text/vtt") and "thirty-six" in captions.text
    assert client.get(record["interactions_url"]).json()["schema"] == "lessonforge.interactions/0.1"
    for private in ("teaching_pack.json", "feedback/r1.json", "tryit/a1.json", "./teaching_pack.json", "logs/C01.log",
                    "media/C01/videos/partial.mp4", "output/../teaching_pack.json", "job.json"):
        assert client.get(f"/lessons/{JOB}/{private}", follow_redirects=False).status_code == 404, private
    assert client.get("/lessons/20261015-000000-nothere/output/squares.mp4", follow_redirects=False).status_code == 404
    # nothing is made or changed here
    for method, path in MAKING:
        refused = client.request(method, path, json={} if method == "POST" else None)
        assert refused.status_code == 403 and refused.json() == {"detail": viewer.MAKING}, path
    assert client.get("/api/harness/voices").json() == {"voices": [], "default": None}
    assert client.get("/api/harness/controls").json() == {"groups": [], "controls": []}


def test_what_viewers_write_lands_in_the_database_with_the_studios_checks(studio, tmp_path):
    publish.publish([JOB], log=lambda *_: None)
    app = viewer.create_app()
    client = TestClient(app, headers={"user-agent": "Mozilla/5.0 (Linux; Android 14) Chrome/140.0 Mobile Safari/537.36"})
    form = client.get("/api/harness/feedback/form").json()
    required = {q["id"]: q for q in form["questions"] if q["required"]}
    answers = {qid: (3 if q["kind"] == "rating" else q["options"][0]["value"]) for qid, q in required.items()}
    assert client.post(f"/api/harness/jobs/{JOB}/feedback", json={"answers": {}}).status_code == 400
    sent = client.post(f"/api/harness/jobs/{JOB}/feedback",
                       json={"reviewer": "Asha", "answers": {**answers, "confusing_chapters": [2, 9]},
                             "auto": {"confused_at": [1.5], "completed": True, "quiz": {"asked": 1, "correct": 1}}})
    assert sent.status_code == 200 and sent.json()["stored"] is True and sent.json()["count"] == 1
    (row,) = database_rows(tmp_path, "SELECT kind, job_id, reviewer, answers FROM reviews")
    assert row[:3] == ("student", JOB, "Asha") and json.loads(row[3])["confusing_chapters"] == [2]
    summary = client.get(f"/api/harness/jobs/{JOB}/feedback").json()
    assert summary["count"] == 1 and summary["confused_at"][0]["beat"] == "01" and "thirty-six" in summary["confused_at"][0]["said"]
    assert summary["chapters_list"] == [{"id": 1, "title": "Dots"}, {"id": 2, "title": "Why"}]
    assert client.get("/api/harness/feedback/summary").json()["lessons"][0]["job_id"] == JOB
    assert client.post(f"/api/harness/jobs/{JOB}/feedback", json={"answers": answers}).status_code == 200
    assert client.post("/api/harness/jobs/20261015-000000-nothere/feedback", json={"answers": answers}).status_code == 404
    # the try-it answer: the expected result comes back only in reply to a stored answer
    assert client.post(f"/api/harness/jobs/{JOB}/tryit", json={"prediction": "16"}).status_code == 400
    told = client.post(f"/api/harness/jobs/{JOB}/tryit", json={"prediction": "16", "answer": "no partner"}).json()
    assert told["stored"] and told["count"] == 1 and told["expected"] == TASK["expected"] and told["observe"] == TASK["observe"]
    assert database_rows(tmp_path, "SELECT job_id, prediction, answer FROM tryit") == [(JOB, "16", "no partner")]
    assert client.get(f"/api/harness/jobs/{JOB}/tryit").json()["answers"][0]["answer"] == "no partner"
    assert client.post("/api/harness/jobs/20261015-000000-nothere/tryit", json={"answer": "x"}).status_code == 404
    # what the player saw, and the dashboard over this site's own visitors
    assert client.post("/api/harness/events", json={"event": "play", "job_id": JOB, "value": "full"}).json() == {"stored": True}
    assert client.post("/api/harness/events", json={"event": "progress", "job_id": JOB, "value": 50}).json() == {"stored": True}
    assert client.post("/api/harness/events", json={"event": "play"}).status_code == 400
    app.state.site.events.flush()
    stored = database_rows(tmp_path, "SELECT event, job_id, value FROM events ORDER BY at")
    assert [(e, j, json.loads(v)) for e, j, v in stored if e in ("play", "progress")] == [("play", JOB, "full"), ("progress", JOB, 50)]
    stats = client.get("/api/harness/stats?days=0&tz=330").json()
    assert stats["totals"]["plays"] == 1 and stats["totals"]["student_reviews"] == 2 and stats["totals"]["lessons"] == 1
    assert stats["lessons"][0]["job_id"] == JOB and stats["lessons"][0]["reviews"] == 2 and stats["spend"]["budget"] is None
    assert stats["funnel"][4]["visitors"] == 1                      # watched at least half
    # a tester's form, which names the lesson it was about only when that lesson is on this site
    tester = {q["id"]: (3 if q["kind"] == "rating" else [q["options"][0]["value"]] if q["kind"] == "multi" else q["options"][0]["value"])
              for q in client.get("/api/harness/feedback/form?kind=tester").json()["questions"] if q["required"]}
    assert client.post("/api/harness/feedback", json={"job_id": JOB, "answers": tester, "contact": "a@b"}).json()["count"] == 1
    assert database_rows(tmp_path, "SELECT kind, job_id, contact FROM reviews WHERE kind = 'tester'") == [("tester", JOB, "a@b")]
    assert client.get("/api/harness/feedback/summary?kind=tester").json()["count"] == 1


def test_the_token_rule_is_the_studios(studio, tmp_path, monkeypatch):
    publish.publish([JOB], log=lambda *_: None)
    web = tmp_path / "dist"
    web.mkdir()
    (web / "index.html").write_text("<!doctype html><title>app</title>")
    monkeypatch.setenv("LESSONFORGE_WEB_APP", str(web))
    monkeypatch.setenv("LESSONFORGE_ACCESS_TOKEN", "owner-key")
    monkeypatch.setenv("LESSONFORGE_REVIEW_TOKEN", "review-key")
    client = TestClient(viewer.create_app())
    owner, student = {"X-Access-Token": "owner-key"}, {"X-Access-Token": "review-key"}
    assert client.get("/healthz").status_code == 200                              # Render's check carries no token
    assert client.get("/api/harness/jobs").status_code == 401
    assert client.get("/api/harness/jobs", headers={"X-Access-Token": "wrong"}).status_code == 401
    assert client.get("/api/harness/jobs", headers=owner).status_code == 200
    assert client.get(f"/lessons/{JOB}/output/captions.vtt").status_code == 401
    # a review link opens its lesson, says which kind of site this is, sends a review and an answer; nothing else
    assert client.get("/api/harness/mode", headers=student).json() == {"mode": "viewer"}
    assert client.get(f"/api/harness/jobs/{JOB}", headers=student).status_code == 200
    assert client.post(f"/api/harness/jobs/{JOB}/tryit", json={"answer": "x"}, headers=student).status_code == 200
    for method, path in (("GET", "/api/harness/jobs"), ("GET", "/api/harness/stats"), ("GET", f"/api/harness/jobs/{JOB}/tryit"),
                         ("GET", "/api/harness/feedback/summary"), ("POST", "/api/harness/generate")):
        assert client.request(method, path, headers=student, json={} if method == "POST" else None).status_code == 403, path
    for who in (owner, student):
        assert client.get(f"/lessons/{JOB}/teaching_pack.json", headers=who).status_code == 404
    # the web app: ?token= once, then the cookie carries it (videos and captions load without a header)
    browser = TestClient(viewer.create_app())
    assert browser.get("/app/").status_code == 401
    assert browser.get("/app/?token=owner-key").status_code == 200 and browser.cookies.get(gate.TOKEN_COOKIE) == "owner-key"
    assert browser.get(f"/lessons/{JOB}/output/captions.vtt").status_code == 200
    assert browser.get("/", follow_redirects=False).headers["location"] == "/app/"
