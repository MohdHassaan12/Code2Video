"""Who opened the app and what they did there — the numbers behind the Dashboard tab.

Two sources, joined in :func:`stats`:

* **events** — one line per thing that happened, appended to
  ``<workspace>/analytics/events.jsonl``. The server's request gate opens a visitor
  context (:func:`begin`) and records page loads and refusals; the harness routes add
  what was asked for (:func:`note`); the client reports what only it can see — which
  screen is up, a video starting, how far it was watched (:func:`client_event`).
* **the workspace** — lessons, intake conversations, reviews and the spend ledger are
  already on disk with their times, so those counts reach back before tracking began.

A visitor is a random cookie (``lf_vid``), or a salted hash of address + user agent for
a client that keeps no cookies. No name, address or full user agent is stored. Automated
browsers (the end-to-end tests) are marked ``test`` and left out unless asked for.

Nothing here may break a request: every write is best-effort.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import threading
import time
from collections import Counter, defaultdict
from contextvars import ContextVar
from pathlib import Path

from .. import paths

COOKIE = "lf_vid"
COOKIE_MAX_AGE = 365 * 24 * 3600
VISIT_GAP = 30 * 60            # events closer than this belong to one visit
MAX_BYTES = 64 * 1024 * 1024   # stop recording rather than fill the disk
MAX_PER_HOUR = 900             # per visitor: a runaway client is dropped, not stored
MAX_BLOCKED_PER_HOUR = 600     # in all: refusals cost a caller nothing, so they share one allowance
ONLINE_WINDOW = 5 * 60

# What a client may report, and the values each accepts.
# "lessons": the viewer site's start screen, the list of finished lessons (lessonforge/viewer.py).
SCREENS = ("ask", "script", "confirm", "making", "watch", "failed", "feedback", "dashboard", "review", "lessons")
CLIENT_EVENTS = {
    "screen": lambda v: v if v in SCREENS else None,
    "play": lambda v: (str(v)[:24] if re.fullmatch(r"[a-z_]{1,24}", str(v or "full")) else "full"),
    "progress": lambda v: int(v) if str(v) in ("25", "50", "75", "100") else None,
}
# The order of the funnel: each step names the events that count as reaching it.
FUNNEL = (
    ("opened", "Opened the app", None),      # everyone active in the period: their page may have loaded before it
    ("asked", "Started describing a lesson", ("intake_start", "script_check")),    # by questions, or by pasting a script
    ("generated", "Asked for a video", ("generate",)),
    ("played", "Played a video", ("play",)),
    ("watched", "Watched at least half", ("progress>=50",)),
    ("feedback", "Sent a review or feedback", ("review_sent", "tester_feedback")),
)
JOB_ID = re.compile(r"^[\w.-]{1,80}$")
_TEST_AGENTS = ("headlesschrome", "puppeteer", "playwright", "curl/", "python-requests", "python-httpx", "wget/")

_CTX: ContextVar[dict | None] = ContextVar("lessonforge_visitor", default=None)
_LOCK = threading.Lock()
_RATE: dict[str, list[float]] = {}
_SALT: dict[str, str] = {}


def folder() -> Path:
    return paths.sub("analytics")


def events_path() -> Path:
    return folder() / "events.jsonl"


def _salt() -> str:
    """Per workspace, so a visitor hash cannot be matched against another server's."""
    path = folder() / "salt"
    cached = _SALT.get(str(path))
    if cached:
        return cached
    try:
        salt = path.read_text(encoding="utf-8").strip()
    except OSError:
        salt = ""
    if not salt:
        salt = secrets.token_hex(16)
        try:
            path.write_text(salt, encoding="utf-8")
        except OSError:
            pass
    _SALT[str(path)] = salt
    return salt


def describe_agent(agent: str) -> dict:
    """A user agent reduced to what a dashboard needs: device class, browser, system."""
    ua = (agent or "").lower()
    test = any(mark in ua for mark in _TEST_AGENTS)
    if not ua:
        return {"device": "unknown", "browser": "", "os": "", "test": False}
    if "ipad" in ua or "tablet" in ua or ("android" in ua and "mobile" not in ua):
        device = "tablet"
    elif "mobi" in ua or "iphone" in ua or "android" in ua:
        device = "phone"
    elif "okhttp" in ua or "expo" in ua or "cfnetwork" in ua or "dalvik" in ua:
        device = "app"
    else:
        device = "desktop"
    system = next((name for mark, name in (("android", "Android"), ("iphone", "iOS"), ("ipad", "iOS"),
                                           ("windows", "Windows"), ("mac os", "macOS"), ("cros", "ChromeOS"),
                                           ("linux", "Linux")) if mark in ua), "")
    browser = next((name for mark, name in (("edg/", "Edge"), ("opr/", "Opera"), ("samsungbrowser", "Samsung"),
                                            ("firefox", "Firefox"), ("fxios", "Firefox"), ("crios", "Chrome"),
                                            ("chrome", "Chrome"), ("safari", "Safari")) if mark in ua), "")
    return {"device": device, "browser": browser, "os": system, "test": test}


def begin(headers, cookies, path: str, role: str, client_host: str = "", salt: str | None = None) -> tuple[dict, str | None]:
    """Open the visitor context for one request.

    Returns the context and, when this browser has no visitor cookie yet, the value to
    set. Only an admitted page load may start a cookie: an API client that keeps none —
    or a caller without a key — would otherwise become a new visitor on every call, so
    those are recognised by a salted hash. ``salt``: the viewer site's own (it keeps no
    workspace); the server's is read from its workspace.
    """
    agent = headers.get("user-agent", "")
    known = cookies.get(COOKIE, "")
    fresh = None
    if re.fullmatch(r"v_[0-9a-f]{12}", known or ""):
        visitor = known
    elif path.startswith("/app") and role != "none":
        visitor = fresh = "v_" + secrets.token_hex(6)
    else:
        address = (headers.get("cf-connecting-ip") or headers.get("x-forwarded-for", "").split(",")[0].strip()
                   or client_host)
        visitor = "h_" + hashlib.sha256(f"{salt or _salt()}|{address}|{agent}".encode()).hexdigest()[:12]
    country = (headers.get("cf-ipcountry") or "").upper()
    ctx = {"visitor": visitor, "role": role, **describe_agent(agent),
           "country": country if re.fullmatch(r"[A-Z]{2}", country) and country not in ("XX", "T1") else ""}
    _CTX.set(ctx)
    return ctx, fresh


def current() -> dict | None:
    return _CTX.get()


def _allowed(visitor: str, now: float, limit: int | None = None) -> bool:
    recent = [t for t in _RATE.get(visitor, ()) if now - t < 3600]
    if len(recent) >= (MAX_PER_HOUR if limit is None else limit):
        _RATE[visitor] = recent
        return False
    recent.append(now)
    _RATE[visitor] = recent
    if len(_RATE) > 5000:
        for key in [k for k, v in _RATE.items() if not v or now - v[-1] > 3600]:
            _RATE.pop(key, None)
    return True


def event_row(event: str, ctx: dict | None = None, **fields) -> dict | None:
    """One event as it is kept, for the visitor of the current request; None outside a request.

    The server appends it to ``events.jsonl`` (:func:`note`); the viewer site (``lessonforge/viewer.py``)
    keeps the same row in its database.
    """
    ctx = ctx or _CTX.get()
    if not ctx:
        return None
    row = {"at": round(time.time(), 3), "event": event, "visitor": ctx["visitor"], "role": ctx["role"],
           "device": ctx["device"], "browser": ctx["browser"], "os": ctx["os"], "country": ctx["country"]}
    if ctx.get("test"):
        row["test"] = True
    row.update({k: v for k, v in fields.items() if v not in (None, "")})
    return row


def admit(row: dict) -> bool:
    """Whether the hourly allowances let this event be kept (and counts it against them)."""
    with _LOCK:
        if row["event"] == "blocked" and not _allowed("(blocked)", row["at"], MAX_BLOCKED_PER_HOUR):
            return False
        return _allowed(row["visitor"], row["at"])


def note(event: str, ctx: dict | None = None, **fields) -> bool:
    """Record one event for the visitor of the current request. Never raises."""
    try:
        row = event_row(event, ctx, **fields)
        if row is None or not admit(row):
            return False
        line = json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n"
        with _LOCK:
            path = events_path()
            if path.exists() and path.stat().st_size > MAX_BYTES:
                return False
            with path.open("a", encoding="utf-8") as fh:
                fh.write(line)
        return True
    except Exception:
        return False


def page_event(method: str, path: str, status: int) -> str | None:
    """What a request means to the dashboard, judged by the gate (routes add the rest)."""
    if status in (401, 403):
        return "blocked"
    if method == "GET" and status < 400 and path in ("/app", "/app/", "/app/index.html"):
        return "visit"
    return None


def client_event(body: dict) -> bool:
    """One event reported by the client: a screen shown, a video started, a share of it watched."""
    event, fields = client_fields(body)
    return note(event, **fields)


def client_fields(body: dict) -> tuple[str, dict]:
    """A client's report, checked: ``(event, fields)``. ``ValueError`` names what is wrong with it."""
    body = body if isinstance(body, dict) else {}
    event = str(body.get("event") or "")
    clean = CLIENT_EVENTS.get(event)
    if clean is None:
        raise ValueError(f"unknown event; expected one of {sorted(CLIENT_EVENTS)}")
    value = clean(body.get("value"))
    if value is None:
        raise ValueError(f"not a value this event takes: {body.get('value')!r}")
    job_id = str(body.get("job_id") or "")
    if job_id and not JOB_ID.match(job_id):
        raise ValueError("job_id is not a lesson id")
    if event != "screen" and not job_id:
        raise ValueError("this event needs the lesson's job_id")
    return event, {"value": value, "job_id": job_id}


def read(include_tests: bool = False) -> list[dict]:
    rows = []
    try:
        with events_path().open(encoding="utf-8") as fh:
            for line in fh:
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                if isinstance(row, dict) and isinstance(row.get("at"), (int, float)) and row.get("visitor") \
                        and (include_tests or not row.get("test")):
                    rows.append(row)
    except OSError:
        pass
    rows.sort(key=lambda r: r["at"])
    return rows


def forget(visitors) -> int:
    """Drop every event of the given visitors (after a browser test). Returns how many were removed."""
    visitors = set(visitors)
    with _LOCK:
        path = events_path()
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            return 0
        kept, dropped = [], 0
        for line in lines:
            try:
                gone = json.loads(line).get("visitor") in visitors
            except ValueError:
                gone = False
            dropped += gone
            if not gone:
                kept.append(line)
        tmp = path.with_suffix(".tmp")
        tmp.write_text("".join(k + "\n" for k in kept), encoding="utf-8")
        os.replace(tmp, path)
    return dropped


# ── aggregation ──────────────────────────────────────────────────────────────

def _day(at: float, tz_minutes: int) -> str:
    """The viewer's calendar day. ``tz_minutes`` is minutes EAST of UTC (India: 330)."""
    return time.strftime("%Y-%m-%d", time.gmtime(at + tz_minutes * 60))


def _visits(times: list[float]) -> int:
    count, last = 0, None
    for at in times:
        if last is None or at - last > VISIT_GAP:
            count += 1
        last = at
    return count


def _reached(step_events, events: list[dict]) -> bool:
    if step_events is None:
        return True
    for wanted in step_events:
        if wanted.startswith("progress>="):
            floor = int(wanted.split(">=")[1])
            if any(e["event"] == "progress" and isinstance(e.get("value"), int) and e["value"] >= floor for e in events):
                return True
        elif any(e["event"] == wanted for e in events):
            return True
    return False


def _sessions(since: float) -> list[dict]:
    """Intake conversations on disk: when each began and whether it reached a full brief."""
    rows = []
    folder_ = paths.home() / "sessions"
    for path in folder_.glob("*.json") if folder_.is_dir() else []:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            at = float(data.get("created") or path.stat().st_mtime)
        except (OSError, ValueError, TypeError):
            continue
        if at >= since:
            rows.append({"at": at, "complete": not data.get("question") and bool((data.get("brief") or {}).get("topic")),
                         "topic": str((data.get("brief") or {}).get("topic") or "")[:120]})
    return sorted(rows, key=lambda r: r["at"])


def _spend(since: float, tz_minutes: int) -> dict:
    from .. import spend as ledger
    by_day: dict[str, float] = defaultdict(float)
    total = period = 0.0
    try:
        rows = ledger.entries()
    except Exception:
        rows = []
    for row in rows:
        cost, at = float(row.get("cost") or 0.0), float(row.get("at") or 0.0)
        total += cost
        if at >= since:
            period += cost
            by_day[_day(at, tz_minutes)] += cost
    try:
        cap = ledger.budget()
    except Exception:
        cap = None
    return {"spent": round(total, 4), "period": round(period, 4), "budget": cap,
            "remaining": round(cap - total, 4) if cap is not None else None,
            "by_day": {day: round(cost, 4) for day, cost in by_day.items()}}


def _being_written(job_id: str, within: float = 600.0) -> bool:
    """Whether anything in the lesson's folder changed in the last few minutes."""
    root, newest = paths.home() / "lessons" / job_id, 0.0
    try:
        for folder_, _dirs, files in os.walk(root):
            if folder_[len(str(root)):].count(os.sep) > 3:
                continue
            for name in files:
                try:
                    newest = max(newest, os.stat(os.path.join(folder_, name)).st_mtime)
                except OSError:
                    continue
    except OSError:
        return False
    return time.time() - newest < within


def stats(days: int = 7, tz_minutes: int = 0, include_tests: bool = False, exclude: str = "",
          now: float | None = None, outside_server: bool = False) -> dict:
    """Everything the Dashboard tab shows, for the last ``days`` calendar days (0: everything).

    ``outside_server``: asked from the command line while a server may be generating. This
    process then sees an unfinished record, which ``service`` reads as interrupted; a
    folder still being written is reported as in progress instead.
    """
    from . import feedback, service

    all_jobs = service.list_jobs(limit=500)
    if outside_server:
        for job in all_jobs:
            if job.get("error") == service.INTERRUPTED and _being_written(job["job_id"]):
                job.update({"status": "running", "error": None})
    return summarize(read(include_tests), all_jobs, days=days, tz_minutes=tz_minutes, exclude=exclude, now=now,
                     sessions=_sessions, spend=_spend,
                     reviews=lambda: {row["job_id"]: row for row in feedback.summarize_all().get("lessons", [])},
                     tester_forms=lambda: feedback.summarize_testers().get("count", 0))


def summarize(everything: list[dict], all_jobs: list[dict], *, days: int = 7, tz_minutes: int = 0, exclude: str = "",
              now: float | None = None, sessions=lambda since: [], spend=None, reviews=lambda: {},
              tester_forms=lambda: 0) -> dict:
    """The dashboard's numbers from its sources, whoever keeps them.

    ``everything``: the events, oldest first (``read``); ``all_jobs``: rows as ``GET /jobs`` lists them;
    ``sessions(since)``: intake conversations; ``spend(since, tz_minutes)``: the ledger's figures;
    ``reviews()``: per lesson, as ``feedback.summarize_all()["lessons"]`` has them; ``tester_forms()``: a count.
    The server reads all of them from its workspace (:func:`stats`); the viewer site has no intakes and no
    ledger, and reads the rest from its own database.
    """
    now = time.time() if now is None else now
    tz_minutes = max(-14 * 60, min(14 * 60, int(tz_minutes)))
    days = max(0, min(366, int(days)))
    spend = spend or (lambda since, tz: {"spent": 0.0, "period": 0.0, "budget": None, "remaining": None, "by_day": {}})
    tracking_since = everything[0]["at"] if everything else None
    if days:
        # Midnight, in the viewer's zone, of the first day shown.
        local_midnight = (now + tz_minutes * 60) // 86400 * 86400 - tz_minutes * 60
        since = local_midnight - (days - 1) * 86400
    else:
        since = 0.0
    events = [e for e in everything if e["at"] >= since and e["visitor"] != exclude]

    by_visitor: dict[str, list[dict]] = defaultdict(list)
    for e in events:
        by_visitor[e["visitor"]].append(e)
    # "People" are those who loaded something; a refused request alone is not a visitor.
    people = {v: rows for v, rows in by_visitor.items() if any(r["event"] != "blocked" for r in rows)}
    first_seen = {}
    for e in everything:
        first_seen.setdefault(e["visitor"], e["at"])

    def active(rows):
        return [r["at"] for r in rows if r["event"] != "blocked"]

    visits = sum(_visits(active(rows)) for rows in people.values())
    plays = [e for e in events if e["event"] == "play"]

    # ── by day ──
    jobs = [j for j in all_jobs if (j.get("created") or 0) >= since]
    sessions = sessions(since)
    spend = spend(since, tz_minutes)
    series: dict[str, dict] = {}

    def slot(day):
        return series.setdefault(day, {"day": day, "visits": 0, "visitors": 0, "intakes": 0, "lessons": 0,
                                       "finished": 0, "plays": 0, "spend": 0.0})
    if days:
        for k in range(days):
            slot(_day(since + k * 86400 + 43200, tz_minutes))
    per_day_people: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    for visitor, rows in people.items():
        for at in active(rows):
            per_day_people[_day(at, tz_minutes)][visitor].append(at)
    for day, group in per_day_people.items():
        slot(day)["visitors"] = len(group)
        slot(day)["visits"] = sum(_visits(times) for times in group.values())
    for e in plays:
        slot(_day(e["at"], tz_minutes))["plays"] += 1
    for s in sessions:
        slot(_day(s["at"], tz_minutes))["intakes"] += 1
    for j in jobs:
        row = slot(_day(j["created"], tz_minutes))
        row["lessons"] += 1
        row["finished"] += j.get("status") == "done"
    for day, cost in spend["by_day"].items():
        slot(day)["spend"] = cost

    # ── funnel: visitors reaching each step, since tracking began ──
    funnel = [{"id": step, "label": label, "visitors": sum(_reached(wanted, rows) for rows in people.values())}
              for step, label, wanted in FUNNEL]

    # ── lessons ──
    reviews = reviews()
    by_job: dict[str, dict] = defaultdict(lambda: {"plays": 0, "viewers": set(), "half": set(), "end": set()})
    for e in events:
        job_id = e.get("job_id")
        if not job_id:
            continue
        slot_ = by_job[job_id]
        if e["event"] == "play":
            slot_["plays"] += 1
            slot_["viewers"].add(e["visitor"])
        elif e["event"] == "progress" and isinstance(e.get("value"), int):
            if e["value"] >= 50:
                slot_["half"].add(e["visitor"])
            if e["value"] >= 100:
                slot_["end"].add(e["visitor"])
    made_by = {e["job_id"]: e["visitor"] for e in everything if e["event"] == "generate" and e.get("job_id")}
    lessons = []
    for j in jobs:
        seen = by_job.get(j["job_id"], {"plays": 0, "viewers": set(), "half": set(), "end": set()})
        review = reviews.get(j["job_id"], {})
        lessons.append({"job_id": j["job_id"], "title": j.get("title") or "Untitled lesson", "status": j.get("status"),
                        "stage": j.get("stage"), "created": j.get("created"), "language": j.get("language"),
                        "duration_seconds": j.get("duration_seconds"), "plays": seen["plays"],
                        "viewers": len(seen["viewers"]), "watched_half": len(seen["half"]),
                        "watched_end": len(seen["end"]), "reviews": review.get("count", 0),
                        "rating": review.get("overall"), "made_by": made_by.get(j["job_id"])})
    status = Counter(j.get("status") for j in jobs)

    # ── visitors ──
    def split(key):
        counts = Counter((rows[-1].get(key) or "unknown") for rows in people.values())
        return [{"name": name, "visitors": n} for name, n in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))]

    visitors = []
    for visitor, rows in people.items():
        times = active(rows)
        last = rows[-1]
        screens = [r.get("value") for r in rows if r["event"] == "screen"]
        visitors.append({"visitor": visitor, "first_seen": first_seen.get(visitor, times[0]), "last_seen": times[-1],
                         "new": first_seen.get(visitor, 0) >= since, "visits": _visits(times),
                         "device": last.get("device") or "unknown", "browser": last.get("browser") or "",
                         "os": last.get("os") or "", "country": last.get("country") or "", "role": last.get("role"),
                         "intakes": sum(r["event"] == "intake_start" for r in rows),
                         "lessons": sum(r["event"] == "generate" for r in rows),
                         "plays": sum(r["event"] == "play" for r in rows),
                         "feedback": sum(r["event"] in ("review_sent", "tester_feedback") for r in rows),
                         "last_screen": screens[-1] if screens else None})
    visitors.sort(key=lambda v: -v["last_seen"])

    titles = {j["job_id"]: j.get("title") for j in all_jobs}
    recent = [{"at": e["at"], "event": e["event"], "visitor": e["visitor"], "device": e.get("device"),
               "country": e.get("country") or "", "value": e.get("value"), "job_id": e.get("job_id"),
               "title": titles.get(e.get("job_id")) if e.get("job_id") else None}
              for e in reversed(events) if e["event"] not in ("screen", "blocked")][:40]

    tester_count = tester_forms()
    finished = status.get("done", 0)
    return {
        "generated_at": now, "days": days, "since": since or None, "tracking_since": tracking_since,
        "me": (current() or {}).get("visitor"),
        "totals": {
            "visitors": len(people), "new_visitors": sum(first_seen.get(v, 0) >= since for v in people),
            "visits": visits, "online": sum(1 for rows in people.values() if now - active(rows)[-1] <= ONLINE_WINDOW),
            "intakes": len(sessions), "intakes_completed": sum(s["complete"] for s in sessions),
            "lessons": len(jobs), "finished": finished, "failed": status.get("failed", 0),
            "in_progress": status.get("running", 0) + status.get("queued", 0),
            "plays": len(plays), "viewers": len({e["visitor"] for e in plays}),
            "minutes_made": round(sum((j.get("duration_seconds") or 0) for j in jobs if j.get("status") == "done") / 60, 1),
            "student_reviews": sum(lesson["reviews"] for lesson in lessons),
            "tester_forms": tester_count,
            "blocked": sum(e["event"] == "blocked" for e in events),
        },
        "series": [series[day] for day in sorted(series)],
        "funnel": funnel,
        "lessons": lessons[:60],
        "devices": split("device"), "countries": [c for c in split("country") if c["name"] != "unknown"],
        "roles": split("role"),
        "visitors": visitors[:60],
        "recent": recent,
        "spend": {**{k: spend[k] for k in ("spent", "period", "budget", "remaining")},
                  "per_finished_lesson": round(spend["period"] / finished, 3) if finished else None},
    }


def format_stats(s: dict) -> str:
    t = s["totals"]
    period = f"last {s['days']} day(s)" if s["days"] else "all time"
    lines = [f"lessonforge — {period}",
             f"visitors {t['visitors']} ({t['new_visitors']} new)   visits {t['visits']}   on the app now {t['online']}",
             f"conversations {t['intakes']}   lessons {t['lessons']} ({t['finished']} finished, {t['failed']} failed, "
             f"{t['in_progress']} in progress)   plays {t['plays']}",
             f"student reviews {t['student_reviews']}   tester forms {t['tester_forms']}"]
    sp = s["spend"]
    if sp["budget"] is not None:
        lines.append(f"spend ${sp['period']:.2f} in this period   ${sp['spent']:.2f} of ${sp['budget']:.2f} in all, "
                     f"${sp['remaining']:.2f} left")
    if s["tracking_since"]:
        lines.append("visits counted since " + time.strftime("%Y-%m-%d %H:%M", time.localtime(s["tracking_since"])))
    else:
        lines.append("no visits recorded yet (counting starts when the server is restarted on this version)")
    lines.append("-- funnel (visitors) --")
    lines += [f"  {step['visitors']:4d}  {step['label']}" for step in s["funnel"]]
    lines.append("-- most played --")
    for lesson in sorted(s["lessons"], key=lambda r: -r["plays"])[:8]:
        lines.append(f"  {lesson['plays']:3d} plays  {lesson['viewers']:3d} viewers  {str(lesson['title'])[:60]}")
    return "\n".join(lines)
