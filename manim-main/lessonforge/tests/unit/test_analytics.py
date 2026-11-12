"""The dashboard's numbers: who is a visitor, what is recorded, how it adds up, and what the gate lets through.

No network, no render. Events are written with chosen times so the sums can be checked by hand.
"""
import json
from collections import OrderedDict

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from lessonforge.harness import analytics, gate, service
from lessonforge.harness.api import router

PHONE = "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0 Mobile Safari/537.36"
LAPTOP = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0 Safari/537.36"
HEADLESS = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) HeadlessChrome/140.0 Safari/537.36"
# 2026-10-08 12:00 India time (06:30 UTC); India is 330 minutes east of UTC.
NOON, IST = 1791441000.0, 330
JOB = "20261008-120000-abc123"


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    monkeypatch.setenv("LESSONFORGE_HOME", str(tmp_path))
    monkeypatch.setenv("OPENROUTER_LEDGER", str(tmp_path / "spend.jsonl"))
    monkeypatch.setenv("OPENROUTER_BUDGET_USD", "10")
    monkeypatch.setattr(service, "_JOBS", OrderedDict())
    monkeypatch.setattr(analytics, "_RATE", {})
    analytics._CTX.set(None)
    return tmp_path


def write_events(rows):
    with analytics.events_path().open("a", encoding="utf-8") as fh:
        for at, visitor, event, extra in rows:
            fh.write(json.dumps({"at": at, "event": event, "visitor": visitor, "role": "owner", "device": "phone",
                                 "browser": "Chrome", "os": "Android", "country": "IN", **extra}) + "\n")


def add_job(root, job_id, created, status="done", seconds=120.0, title="Which bar is the magnet?"):
    folder = root / "lessons" / job_id
    folder.mkdir(parents=True)
    (folder / "job.json").write_text(json.dumps({
        "job_id": job_id, "status": status, "stage": "done" if status == "done" else "speech", "title": title,
        "created": created, "brief": {"language": "hi-IN"}, "checks": {"duration_seconds": seconds} if seconds else None}))


def test_a_user_agent_is_reduced_to_a_device_class_and_tests_are_marked():
    assert analytics.describe_agent(PHONE) == {"device": "phone", "browser": "Chrome", "os": "Android", "test": False}
    assert analytics.describe_agent(LAPTOP)["device"] == "desktop" and analytics.describe_agent(LAPTOP)["os"] == "Windows"
    assert analytics.describe_agent("Mozilla/5.0 (iPad; CPU OS 18_0 like Mac OS X) Safari/605")["device"] == "tablet"
    assert analytics.describe_agent(HEADLESS)["test"] is True and analytics.describe_agent("curl/8.5.0")["test"] is True
    assert analytics.describe_agent("")["device"] == "unknown"


def test_a_page_load_starts_a_cookie_and_an_api_client_without_one_is_one_stable_visitor(workspace):
    ctx, fresh = analytics.begin({"user-agent": PHONE, "cf-ipcountry": "in"}, {}, "/app/", "owner")
    assert fresh == ctx["visitor"] and fresh.startswith("v_") and ctx["country"] == "IN" and ctx["device"] == "phone"
    again, fresh2 = analytics.begin({"user-agent": PHONE}, {analytics.COOKIE: fresh}, "/api/harness/jobs", "owner")
    assert again["visitor"] == fresh and fresh2 is None
    # No cookie on an API call (a native app): recognised by a salted hash, never given a cookie.
    headers = {"user-agent": "okhttp/4.12", "cf-connecting-ip": "203.0.113.9"}
    one, f1 = analytics.begin(headers, {}, "/api/harness/jobs", "owner")
    two, f2 = analytics.begin(headers, {}, "/api/harness/sessions", "owner")
    other, _ = analytics.begin({**headers, "cf-connecting-ip": "203.0.113.10"}, {}, "/api/harness/jobs", "owner")
    assert one["visitor"] == two["visitor"] != other["visitor"] and one["visitor"].startswith("h_") and f1 is f2 is None
    assert "203.0.113" not in json.dumps(one)                         # the address itself is never kept
    # A caller without a key is never given an id of its own to multiply: refusals share the hash.
    refused, f4 = analytics.begin({"user-agent": PHONE, "cf-connecting-ip": "203.0.113.9"}, {}, "/app/", "none")
    refused2, _ = analytics.begin({"user-agent": PHONE, "cf-connecting-ip": "203.0.113.9"}, {}, "/app/", "none")
    assert refused["visitor"] == refused2["visitor"] and refused["visitor"].startswith("h_") and f4 is None
    # A forged or odd cookie is not trusted as an id; Cloudflare's "unknown" country is not a country.
    forged, fresh3 = analytics.begin({"user-agent": PHONE, "cf-ipcountry": "XX"}, {analytics.COOKIE: "../../x"}, "/app/", "owner")
    assert forged["visitor"] == fresh3 and forged["country"] == ""


def test_events_are_stored_one_per_line_and_a_runaway_client_is_dropped(workspace, monkeypatch):
    assert analytics.note("visit") is False                            # outside a request there is no one to count
    ctx, _ = analytics.begin({"user-agent": PHONE}, {}, "/app/", "owner")
    assert analytics.note("visit") and analytics.note("play", job_id=JOB, value="full", empty="")
    rows = analytics.read()
    assert [r["event"] for r in rows] == ["visit", "play"] and rows[1]["job_id"] == JOB and "empty" not in rows[1]
    assert "test" not in rows[0]
    analytics.begin({"user-agent": HEADLESS}, {}, "/app/", "owner")
    analytics.note("visit")
    assert len(analytics.read()) == 2 and len(analytics.read(include_tests=True)) == 3
    monkeypatch.setattr(analytics, "MAX_PER_HOUR", 5)
    analytics.begin({"user-agent": LAPTOP}, {}, "/app/", "owner")
    assert [analytics.note("visit") for _ in range(7)] == [True] * 5 + [False] * 2
    monkeypatch.setattr(analytics, "MAX_BLOCKED_PER_HOUR", 2)                 # refusals share one allowance, whoever sends them
    refusals = []
    for k in range(4):
        analytics.begin({"user-agent": f"probe/{k}"}, {}, "/api/harness/jobs", "none")
        refusals.append(analytics.note("blocked"))
    assert refusals == [True, True, False, False]
    monkeypatch.setattr(analytics, "MAX_BYTES", 10)
    analytics.begin({"user-agent": PHONE}, {}, "/app/", "owner")
    assert analytics.note("visit") is False                            # the file is full: nothing more is written
    assert analytics.forget([ctx["visitor"]]) == 2 and all(r["visitor"] != ctx["visitor"] for r in analytics.read(True))


def test_the_client_may_report_only_what_the_dashboard_uses(workspace):
    analytics.begin({"user-agent": PHONE}, {}, "/app/", "review")
    assert analytics.client_event({"event": "screen", "value": "watch"})
    assert analytics.client_event({"event": "play", "job_id": JOB, "value": "revision"})
    assert analytics.client_event({"event": "progress", "job_id": JOB, "value": 50})
    for bad in ({"event": "purchase"}, {"event": "screen", "value": "<script>"}, {"event": "progress", "job_id": JOB, "value": 33},
                {"event": "play", "value": "full"}, {"event": "play", "job_id": "../etc/passwd"}, None):
        with pytest.raises(ValueError):
            analytics.client_event(bad)
    assert [(r["event"], r["value"]) for r in analytics.read()] == [("screen", "watch"), ("play", "revision"), ("progress", 50)]


def test_the_numbers_add_up(workspace):
    yesterday = NOON - 86400
    add_job(workspace, JOB, NOON - 3000)
    add_job(workspace, "20261008-110000-ffffff", NOON - 3600, status="failed", seconds=None, title="Fractions")
    add_job(workspace, "20261001-090000-000001", NOON - 7 * 86400)                 # outside a 7-day window
    for name, created in (("a", NOON - 3100), ("b", yesterday)):
        (workspace / "sessions").mkdir(exist_ok=True)
        (workspace / "sessions" / f"{name}.json").write_text(json.dumps(
            {"id": name, "created": created, "question": None if name == "a" else {"id": "goal"}, "brief": {"topic": "magnets"}}))
    (workspace / "spend.jsonl").write_text("".join(json.dumps({"at": at, "cost": cost}) + "\n" for at, cost in (
        (NOON - 3000, 0.75), (NOON - 2000, 0.25), (yesterday, 0.5), (NOON - 30 * 86400, 2.0))))
    write_events([
        # A: two visits today (more than 30 minutes apart), made the lesson, watched it to the end.
        (NOON - 7200, "v_a", "visit", {}), (NOON - 7100, "v_a", "intake_start", {}),
        (NOON - 2000, "v_a", "visit", {}), (NOON - 2000, "v_a", "generate", {"job_id": JOB}),
        (NOON - 600, "v_a", "play", {"job_id": JOB, "value": "full"}),
        (NOON - 500, "v_a", "progress", {"job_id": JOB, "value": 50}),
        (NOON - 200, "v_a", "progress", {"job_id": JOB, "value": 100}),
        (NOON - 100, "v_a", "screen", {"value": "watch"}),
        # B: came yesterday too, played twice today, stopped early, sent feedback. On a laptop.
        (yesterday, "v_b", "visit", {}),
        (NOON - 1000, "v_b", "visit", {"device": "desktop"}), (NOON - 900, "v_b", "play", {"job_id": JOB, "device": "desktop"}),
        (NOON - 800, "v_b", "play", {"job_id": JOB, "device": "desktop"}),
        (NOON - 700, "v_b", "progress", {"job_id": JOB, "value": 25, "device": "desktop"}),
        (NOON - 650, "v_b", "tester_feedback", {"device": "desktop"}),
        # C: only ever refused; D: an automated browser. Neither is a visitor.
        (NOON - 400, "h_c", "blocked", {"role": "none", "path": "/api/harness/jobs"}),
        (NOON - 300, "v_d", "visit", {"test": True}),
    ])
    s = analytics.stats(days=7, tz_minutes=IST, now=NOON)
    t = s["totals"]
    assert (t["visitors"], t["new_visitors"], t["visits"], t["blocked"]) == (2, 2, 4, 1)
    assert (t["plays"], t["viewers"], t["online"]) == (3, 1 + 1, 1)                # only A was active in the last 5 minutes
    assert (t["intakes"], t["intakes_completed"]) == (2, 1)
    assert (t["lessons"], t["finished"], t["failed"], t["in_progress"], t["minutes_made"]) == (2, 1, 1, 0, 2.0)
    assert s["tracking_since"] == yesterday and len(s["series"]) == 7
    today, before = s["series"][-1], s["series"][-2]
    assert today == {"day": "2026-10-08", "visits": 3, "visitors": 2, "intakes": 1, "lessons": 2, "finished": 1,
                     "plays": 3, "spend": 1.0}
    assert (before["day"], before["visits"], before["intakes"], before["spend"]) == ("2026-10-07", 1, 1, 0.5)
    assert [step["visitors"] for step in s["funnel"]] == [2, 1, 1, 2, 1, 1]
    lesson = next(row for row in s["lessons"] if row["job_id"] == JOB)
    assert (lesson["plays"], lesson["viewers"], lesson["watched_half"], lesson["watched_end"]) == (3, 2, 1, 1)
    assert lesson["made_by"] == "v_a" and lesson["duration_seconds"] == 120.0
    assert s["devices"] == [{"name": "desktop", "visitors": 1}, {"name": "phone", "visitors": 1}]
    assert s["countries"] == [{"name": "IN", "visitors": 2}]
    a = next(v for v in s["visitors"] if v["visitor"] == "v_a")
    assert (a["visits"], a["intakes"], a["lessons"], a["plays"], a["last_screen"]) == (2, 1, 1, 1, "watch")
    assert s["spend"] == {"spent": 3.5, "period": 1.5, "budget": 10.0, "remaining": 6.5, "per_finished_lesson": 1.5}
    assert s["recent"][0]["event"] == "progress" and s["recent"][0]["title"] == "Which bar is the magnet?"
    assert all(row["event"] not in ("screen", "blocked") for row in s["recent"])

    # Today only: B's first visit was yesterday, so B is not new; yesterday's numbers are gone.
    day = analytics.stats(days=1, tz_minutes=IST, now=NOON)
    assert (day["totals"]["visitors"], day["totals"]["new_visitors"], day["totals"]["visits"]) == (2, 1, 3)
    assert day["spend"]["period"] == 1.0 and len(day["series"]) == 1
    # The same instant is another calendar day elsewhere: buckets follow the viewer's clock.
    utc = analytics.stats(days=7, tz_minutes=-600, now=NOON)
    assert utc["series"][-1]["day"] == "2026-10-07"
    # Everything, without me, with the test browser.
    everything = analytics.stats(days=0, tz_minutes=IST, now=NOON, exclude="v_a", include_tests=True)
    assert everything["totals"]["visitors"] == 2 and everything["totals"]["lessons"] == 3
    assert {v["visitor"] for v in everything["visitors"]} == {"v_b", "v_d"}
    assert "visitors 2 (2 new)" in analytics.format_stats(s) and "Opened the app" in analytics.format_stats(s)


def test_an_empty_workspace_is_all_zeros_not_an_error(workspace):
    s = analytics.stats(days=7, tz_minutes=IST, now=NOON)
    assert s["tracking_since"] is None and s["totals"]["visitors"] == 0 and s["lessons"] == [] and s["recent"] == []
    assert s["spend"]["per_finished_lesson"] is None and "no visits recorded yet" in analytics.format_stats(s)


# ── through the gate ─────────────────────────────────────────────────────────

@pytest.fixture
def client(workspace):
    app = FastAPI()
    gate.install(app, "owner-secret", "review-secret")
    app.include_router(router)

    @app.get("/app/")
    def page():
        return {"page": "app"}

    add_job(workspace, JOB, NOON)
    return TestClient(app, headers={"user-agent": PHONE})


def test_the_gate_counts_a_visit_once_and_the_routes_know_who_is_asking(client, monkeypatch):
    assert client.get("/app/").status_code == 401                                   # no token: refused, and counted as that
    opened = client.get("/app/?token=owner-secret")
    assert opened.status_code == 200
    visitor = client.cookies.get(analytics.COOKIE)
    assert visitor and visitor.startswith("v_") and client.cookies.get(gate.TOKEN_COOKIE) == "owner-secret"
    assert client.get("/app/").status_code == 200 and client.cookies.get(analytics.COOKIE) == visitor   # the cookie carries both

    monkeypatch.setattr(service, "start_job", lambda brief, quality="m", voice=None: {"job_id": JOB, "status": "queued"})
    assert client.post("/api/harness/generate", json={"brief": {"topic": "magnets"}, "quality": "l"}).status_code == 200
    assert client.post("/api/harness/events", json={"event": "play", "job_id": JOB, "value": "full"}).json() == {"stored": True}
    assert client.post("/api/harness/events", json={"event": "play"}).status_code == 400

    rows = analytics.read()
    assert [(r["event"], r["role"]) for r in rows] == [("blocked", "none"), ("visit", "owner"), ("visit", "owner"),
                                                       ("generate", "owner"), ("play", "owner")]
    assert {r["visitor"] for r in rows[1:]} == {visitor} and rows[3]["job_id"] == JOB and rows[3]["value"] == "l"
    s = client.get("/api/harness/stats?days=0&tz=330").json()
    assert s["me"] == visitor and s["totals"]["visitors"] == 1 and s["totals"]["blocked"] == 1
    assert [step["visitors"] for step in s["funnel"]][:4] == [1, 0, 1, 1]
    assert client.get("/api/harness/stats?days=0&me=0").json()["totals"]["visitors"] == 0


def test_a_review_link_may_report_what_it_watched_but_never_read_the_dashboard(client):
    student = {"x-access-token": "review-secret"}
    assert client.post("/api/harness/events", json={"event": "progress", "job_id": JOB, "value": 100}, headers=student).status_code == 200
    assert client.get(f"/api/harness/jobs/{JOB}", headers=student).status_code == 200
    for method, path in (("GET", "/api/harness/stats"), ("GET", "/api/harness/jobs"), ("POST", "/api/harness/generate"),
                         ("GET", "/api/harness/feedback/summary")):
        assert client.request(method, path, headers=student, json={} if method == "POST" else None).status_code == 403, path
    assert client.get("/api/harness/stats", headers={"x-access-token": "wrong"}).status_code == 401
    assert client.get("/api/harness/stats", params={"token": "ключ"}).status_code == 401              # not a crash
    events = [(r["event"], r["role"]) for r in analytics.read()]
    assert events.count(("blocked", "review")) == 4 and ("progress", "review") in events


def test_unauthenticated_browser_sees_designed_page_while_api_sees_json(client):
    # Browser navigation receives designed HTML 401
    html_resp = client.get("/app/", headers={"accept": "text/html,application/xhtml+xml"})
    assert html_resp.status_code == 401
    assert "text/html" in html_resp.headers["content-type"]
    assert "Adhyay Video Studio" in html_resp.text
    assert "By Invitation" in html_resp.text
    assert 'name="token"' in html_resp.text
    assert "https://adhyay.app/#contact" in html_resp.text

    # With an invalid query token, the page shows the error notice
    invalid_resp = client.get("/app/?token=bad-token", headers={"accept": "text/html"})
    assert invalid_resp.status_code == 401
    assert "The token entered was not recognized" in invalid_resp.text

    # API endpoints receive machine-readable JSON 401
    api_resp = client.get("/api/harness/jobs")
    assert api_resp.status_code == 401
    assert "application/json" in api_resp.headers["content-type"]
    assert api_resp.json() == {"detail": "access token required (X-Access-Token header or ?token=)"}

