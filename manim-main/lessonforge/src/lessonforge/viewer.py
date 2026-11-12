"""The viewer site: the finished lessons, at a fixed address on Render (``docs/DEPLOY_RENDER_VIEWER.md``).

Lessons are MADE on the GPU machine (the studio server, ``lessonforge serve``) and published to
Cloudflare R2 (``harness/publish.py``). This app shows them and makes nothing:

* the same web app at ``/app/`` (``LESSONFORGE_WEB_APP``), which asks ``/api/harness/mode``, hears
  ``viewer`` and hides every way to make or change a lesson;
* ``/api/harness/jobs`` and ``/jobs/{id}`` read from R2 (cached for a minute), exactly the records the
  studio published;
* ``/lessons/{job_id}/{path}``: a video is a redirect to a signed R2 link (the browser streams it from
  R2 with range requests, nothing large passes through Render); the small files (captions, the
  player's questions, the outline) are passed through, so the app needs no cross-origin set-up;
* what viewers write (reviews, try-it answers, the dashboard's events) goes to Cloudflare D1, with the
  studio's own checks (``feedback``, ``tryit``, ``analytics``: their pure parts, reused);
* every route that makes or changes a lesson answers 403 with :data:`MAKING`.

Access: the studio's own gate (``harness/gate.py``) with ``LESSONFORGE_ACCESS_TOKEN`` and
``LESSONFORGE_REVIEW_TOKEN``, so the rule is the same on both sites; ``/healthz`` is open.

This module must never import the engine, the renderer or ``harness.service``: the Docker image has
no Manim, LaTeX or browser (``deploy/Dockerfile``). Run: ``uvicorn lessonforge.viewer:app``.
"""
from __future__ import annotations

import contextlib
import hashlib
import json
import os
import posixpath
import queue
import secrets
import threading
import time
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import cloud
from .harness import analytics, feedback, frameworks, gate, intake, tryit

MAKING = "Lessons are made on the studio server; this site shows the finished ones."
CACHE_SECONDS = 60.0
#: Files sent as a redirect to a signed R2 link; anything else in a lesson folder is small and passed through.
REDIRECTED = (".mp4", ".webm", ".m4v", ".mov", ".mp3", ".m4a", ".wav", ".ogg")
KEEP_IN_MEMORY = 2 * 1024 * 1024        # a passed-through file larger than this is read again each time
MAX_EVENTS_READ = 50_000                # the dashboard reads at most the newest this many events
EVENT_COLUMNS = ("at", "event", "visitor", "role", "device", "browser", "os", "country", "test", "job_id", "value", "extra")
_EVENT_FIELDS = set(EVENT_COLUMNS) - {"extra", "value", "test"}

#: The studio's routes that make or change a lesson (``harness/api.py``). Any other POST is refused as well.
MAKING_ROUTES = (
    ("POST", "/api/harness/sessions"), ("GET", "/api/harness/sessions/{session_id}"),
    ("POST", "/api/harness/sessions/{session_id}/answer"), ("POST", "/api/harness/sessions/{session_id}/generate"),
    ("POST", "/api/harness/generate"), ("POST", "/api/harness/script/preview"), ("POST", "/api/harness/plan"),
    ("POST", "/api/harness/jobs/{job_id}/remove"), ("POST", "/api/harness/jobs/{job_id}/voice"),
    ("POST", "/api/harness/jobs/{job_id}/cuts/{cut_id}"),
)


class Review(BaseModel):
    reviewer: Optional[str] = None
    answers: dict = {}
    auto: Optional[dict] = None


class TesterForm(BaseModel):
    kind: str = "tester"
    job_id: Optional[str] = None
    reviewer: Optional[str] = None
    contact: Optional[str] = None
    answers: dict = {}


class TryIt(BaseModel):
    prediction: Optional[str] = None
    observation: Optional[str] = None
    answer: Optional[str] = None
    reviewer: Optional[str] = None
    done_in_class: bool = False


class Event(BaseModel):
    event: str
    job_id: Optional[str] = None
    value: Any = None


def visitor_salt() -> str:
    """Stable for a deployment and secret: derived from a secret the site already has (no workspace here)."""
    explicit = (os.getenv("LESSONFORGE_VISITOR_SALT") or "").strip()
    if explicit:
        return explicit
    folder = cloud.local_dir()
    seed = (os.getenv("CLOUDFLARE_R2_SECRET_ACCESS_KEY") or os.getenv("LESSONFORGE_ACCESS_TOKEN")
            or (str(folder) if folder else "") or secrets.token_hex(16))
    return hashlib.sha256(f"lessonforge-viewer-visitors|{seed}".encode()).hexdigest()[:32]


def _event_columns(row: dict) -> tuple:
    extra = {k: v for k, v in row.items() if k not in _EVENT_FIELDS and k not in ("value", "test")}
    return (row["at"], row["event"], row["visitor"], row.get("role"), row.get("device"), row.get("browser"),
            row.get("os"), row.get("country"), 1 if row.get("test") else 0, row.get("job_id"),
            json.dumps(row["value"], ensure_ascii=False) if "value" in row else None,
            json.dumps(extra, ensure_ascii=False) if extra else None)


def _event_of(stored: dict) -> dict | None:
    """A database row back into the row ``analytics`` keeps in its file."""
    try:
        row = {k: stored.get(k) for k in ("at", "event", "visitor", "role", "device", "browser", "os", "country")}
        if stored.get("test"):
            row["test"] = True
        if stored.get("job_id"):
            row["job_id"] = stored["job_id"]
        if stored.get("value") is not None:
            row["value"] = json.loads(stored["value"])
        if stored.get("extra"):
            row.update(json.loads(stored["extra"]))
        return row if isinstance(row["at"], (int, float)) and row["visitor"] else None
    except (TypeError, ValueError):
        return None


class EventSink:
    """Events reach the database from a thread of their own: the gate notes them inside a request, which must
    not wait for Cloudflare. ``flush()`` writes everything waiting and returns once it is written."""

    def __init__(self, site: "Site"):
        self.site = site
        self.queue: queue.Queue = queue.Queue(maxsize=10_000)
        self._thread: threading.Thread | None = None
        self._start_lock = threading.Lock()

    def add(self, row: dict) -> bool:
        try:
            self.queue.put_nowait(row)
        except queue.Full:
            return False
        with self._start_lock:
            if self._thread is None or not self._thread.is_alive():
                self._thread = threading.Thread(target=self._run, name="viewer-events", daemon=True)
                self._thread.start()
        return True

    def _take(self, first=None) -> list[dict]:
        batch = [] if first is None else [first]
        while len(batch) < 400:
            try:
                batch.append(self.queue.get_nowait())
            except queue.Empty:
                break
        return batch

    def _write(self, batch: list[dict]) -> None:
        try:
            if batch:
                cloud.insert_many(self.site.db(), "events", EVENT_COLUMNS, [_event_columns(r) for r in batch])
        except Exception:  # noqa: BLE001 - counting visitors must never break the site; the batch is dropped
            pass
        finally:
            for _ in batch:
                self.queue.task_done()

    def _run(self) -> None:
        while True:
            first = self.queue.get()
            time.sleep(0.5)                       # gather what arrives with it: one statement, not one per event
            self._write(self._take(first))

    def flush(self) -> None:
        self._write(self._take())
        self.queue.join()


class Site:
    """The viewer's view of the cloud, with a minute's memory of what it read."""

    def __init__(self):
        self._cache: dict = {}
        self._cache_lock = threading.Lock()
        self._schema = False
        self.events = EventSink(self)

    # ── services ──
    def store(self):
        try:
            return cloud.objects()
        except cloud.NotConfigured as exc:
            raise HTTPException(status_code=503, detail=str(exc))

    def db(self):
        try:
            db = cloud.database()
        except cloud.NotConfigured as exc:
            raise HTTPException(status_code=503, detail=str(exc))
        if not self._schema:
            cloud.schema(db)
            self._schema = True
        return db

    def query(self, sql: str, params=()) -> list[dict]:
        db = self.db()
        try:
            return db.query(sql, params)
        except cloud.CloudError as exc:
            raise HTTPException(status_code=502, detail=str(exc))

    def cached(self, key, make, seconds: float = CACHE_SECONDS):
        now = time.monotonic()
        with self._cache_lock:
            hit = self._cache.get(key)
            if hit and hit[0] > now:
                return hit[1]
        try:
            value = make()
        except HTTPException:
            raise
        except Exception as exc:  # noqa: BLE001 - R2 down or refusing: say so, keep serving what is cached elsewhere
            raise HTTPException(status_code=502, detail=f"the lesson store did not answer: {type(exc).__name__}")
        with self._cache_lock:
            if len(self._cache) > 2000:
                self._cache = {k: v for k, v in self._cache.items() if v[0] > now}
            self._cache[key] = (now + seconds, value)
        return value

    # ── what was published ──
    def jobs(self) -> list[dict]:
        listed = self.cached("jobs", lambda: self.store().get_json(cloud.JOBS_KEY) or {})
        return [row for row in (listed.get("jobs") or []) if isinstance(row, dict) and row.get("job_id")]

    def record(self, job_id: str) -> dict:
        if not cloud.safe_job_id(job_id):
            raise HTTPException(status_code=404, detail="not found")
        found = self.cached(("job", job_id), lambda: self.store().get_json(cloud.job_key(job_id)))
        if not isinstance(found, dict):
            raise HTTPException(status_code=404, detail="not found")
        return found

    def lesson_json(self, record: dict, field: str):
        """A small published file a record points at (``lesson_url``, ``outline_url``), parsed; None if absent."""
        url, base = record.get(field), f"/lessons/{record['job_id']}/"
        if not isinstance(url, str) or not url.startswith(base):
            return None
        key = cloud.lesson_key(record["job_id"], url[len(base):])
        raw = self.cached(("file", key), lambda: self.store().get_bytes(key), seconds=300)
        try:
            return json.loads(raw) if raw else None
        except ValueError:
            return None

    # ── what viewers wrote ──
    def reviews(self, kind: str, job_id: str | None = None) -> list[dict]:
        sql = "SELECT * FROM reviews WHERE kind = ?" + (" AND job_id = ?" if job_id else "") + " ORDER BY at, id"
        rows = self.query(sql, [kind] + ([job_id] if job_id else []))
        out = []
        for row in rows:
            try:
                record = {"id": row["id"], "at": row["at"], "job_id": row["job_id"], "form_version": row["form_version"],
                          "reviewer": row["reviewer"] or "", "answers": json.loads(row["answers"] or "{}")}
                lesson = json.loads(row["lesson"] or "{}")
                if kind == "tester":
                    record.update({"kind": "tester", "lesson_title": lesson.get("title"), "contact": row["contact"] or ""})
                else:
                    record.update({"auto": json.loads(row["auto"] or "{}"), "lesson": lesson})
                out.append(record)
            except (TypeError, ValueError, KeyError):
                continue
        return out

    def answers(self, job_id: str) -> list[dict]:
        rows = self.query("SELECT * FROM tryit WHERE job_id = ? ORDER BY at, id", [job_id])
        return [{**row, "done_in_class": bool(row.get("done_in_class"))} for row in rows]

    def all_events(self, include_tests: bool) -> list[dict]:
        rows = self.query("SELECT * FROM events" + ("" if include_tests else " WHERE test = 0")
                          + " ORDER BY at DESC LIMIT ?", [MAX_EVENTS_READ])
        events = [e for e in (_event_of(r) for r in rows) if e]
        events.reverse()
        return events


def create_app() -> FastAPI:
    """The app, reading its settings now (``app`` below is made at import; tests make their own)."""
    site = Site()

    @contextlib.asynccontextmanager
    async def lifespan(_app):
        yield
        site.events.flush()                           # what is still waiting is written before the process ends

    app = FastAPI(title="lessonforge viewer", docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)
    app.state.site = site
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"],
                       allow_headers=["*"])
    salt = visitor_salt()

    def begin(headers, cookies, path, role, client_host=""):
        return analytics.begin(headers, cookies, path, role, client_host, salt=salt)

    def note(event: str, ctx: dict | None = None, **fields) -> bool:
        """``analytics.note``'s rules (the same row, the same hourly allowances); kept in the database."""
        try:
            row = analytics.event_row(event, ctx, **fields)
            return bool(row) and analytics.admit(row) and site.events.add(row)
        except Exception:  # noqa: BLE001 - never breaks a request
            return False

    gate.install(app, os.getenv("LESSONFORGE_ACCESS_TOKEN", ""), os.getenv("LESSONFORGE_REVIEW_TOKEN", ""),
                 begin=begin, note=note, open_paths=("/healthz", cloud.LocalObjects.ROUTE))

    @app.get("/healthz")
    def healthz():
        """For Render's health check: answers without a token and asks nothing of Cloudflare."""
        return {"ok": True, "mode": "viewer", **cloud.describe()}

    @app.get("/")
    def root(request: Request):
        query = request.url.query
        return RedirectResponse("/app/" + (f"?{query}" if query else ""), status_code=307)

    # ── the lessons ──
    @app.get("/api/harness/mode")
    def mode():
        return {"mode": "viewer"}

    @app.get("/api/harness/jobs")
    def jobs():
        return {"jobs": site.jobs()}

    @app.get("/api/harness/jobs/{job_id}")
    def job(job_id: str):
        return site.record(job_id)

    @app.get("/api/harness/voices")
    def voices():
        return {"voices": [], "default": None}

    @app.get("/api/harness/controls")
    def controls():
        return {"groups": [], "controls": []}

    @app.get("/api/harness/frameworks")
    def list_frameworks():
        return {"frameworks": frameworks.FRAMEWORKS, "levels": intake.LEVELS, "styles": intake.STYLES,
                "languages": intake.LANGUAGES, "durations": intake.DURATIONS}

    @app.get("/lessons/{job_id}/{rel:path}")
    def lesson_file(job_id: str, rel: str):
        rel = posixpath.normpath(rel)
        if rel in (".", "") or rel.startswith(("/", "../")) or gate.PRIVATE_IN_LESSON.match(f"/lessons/{job_id}/{rel}"):
            raise HTTPException(status_code=404, detail="not found")
        site.record(job_id)                           # only a published lesson's files, never a taken-off one's
        key = cloud.lesson_key(job_id, rel)
        if rel.lower().endswith(REDIRECTED):
            if not site.cached(("exists", key), lambda: site.store().exists(key), seconds=300):
                raise HTTPException(status_code=404, detail="not found")
            link = site.cached(("link", key), lambda: site.store().presign(key), seconds=cloud.PRESIGN_SECONDS / 2)
            return RedirectResponse(link, status_code=307, headers={"Cache-Control": "private, max-age=600"})
        data = site.cached(("file", key), lambda: site.store().get_bytes(key), seconds=300)
        if data is None:
            raise HTTPException(status_code=404, detail="not found")
        if len(data) > KEEP_IN_MEMORY:
            with site._cache_lock:
                site._cache.pop(("file", key), None)
        return Response(data, media_type=cloud.content_type(rel), headers={"Cache-Control": "private, max-age=300"})

    @app.get(cloud.LocalObjects.ROUTE + "{key:path}")
    def local_object(key: str, e: str = "", s: str = ""):
        """A trial without Cloudflare: the signed links of the local store (a real one points at R2)."""
        store = site.store()
        if not isinstance(store, cloud.LocalObjects) or not store.signed(key, e, s):
            raise HTTPException(status_code=403, detail="not a valid link")
        try:
            path = store.path(key)
        except ValueError:
            raise HTTPException(status_code=404, detail="not found")
        if not path.is_file():
            raise HTTPException(status_code=404, detail="not found")
        return FileResponse(path, media_type=cloud.content_type(key))

    # ── reviews ──
    @app.get("/api/harness/feedback/form")
    def feedback_form(kind: str = "student"):
        try:
            return feedback.form(kind)
        except KeyError:
            raise HTTPException(status_code=404, detail="not found")

    @app.post("/api/harness/jobs/{job_id}/feedback")
    def send_feedback(job_id: str, body: Review):
        record = site.record(job_id)
        brief = record.get("brief") or {}
        lesson = {"title": record.get("title"), "framework": brief.get("framework"), "language": brief.get("language"),
                  "level": brief.get("level"), "grade": brief.get("grade"), "minutes": brief.get("duration_minutes")}
        try:
            review = feedback.review_of(job_id, body.model_dump(), {c.get("id") for c in record.get("chapters") or []
                                                                    if isinstance(c, dict)}, lesson)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        site.query("INSERT INTO reviews (id, at, kind, job_id, form_version, reviewer, contact, lesson, answers, auto) "
                   "VALUES (?, ?, 'student', ?, ?, ?, NULL, ?, ?, ?)",
                   [review["id"], review["at"], job_id, review["form_version"], review["reviewer"],
                    json.dumps(lesson, ensure_ascii=False), json.dumps(review["answers"], ensure_ascii=False),
                    json.dumps(review["auto"], ensure_ascii=False)])
        note("review_sent", job_id=job_id)
        count = site.query("SELECT COUNT(*) AS n FROM reviews WHERE kind = 'student' AND job_id = ?", [job_id])
        return {"stored": True, "id": review["id"], "count": int(count[0]["n"]) if count else 1}

    @app.get("/api/harness/jobs/{job_id}/feedback")
    def read_feedback(job_id: str):
        record = site.record(job_id)
        lesson = site.lesson_json(record, "lesson_url")
        if not isinstance(lesson, dict) or not isinstance(lesson.get("chapters"), list):
            lesson = {"title": record.get("title", ""), "chapters": [{"id": c.get("id"), "title": c.get("title"), "beats": []}
                                                                   for c in record.get("chapters") or [] if isinstance(c, dict)]}
        outline = site.lesson_json(record, "outline_url") or {}
        timeline = [{"id": s["beat"], "chapter": s["chapter"], "start": s["start"], "duration": s["end"] - s["start"]}
                    for s in outline.get("segments") or [] if isinstance(s, dict) and {"beat", "chapter", "start", "end"} <= set(s)]
        return feedback.summary_from(job_id, site.reviews("student", job_id), lesson, timeline)

    @app.get("/api/harness/feedback/summary")
    def feedback_summary(kind: str = "student"):
        if kind == "tester":
            return feedback.testers_from(site.reviews("tester"))
        by_job: dict[str, list] = {}
        for review in site.reviews("student"):
            by_job.setdefault(review["job_id"], []).append(review)
        return feedback.all_from(sorted(by_job.items(), reverse=True))

    @app.post("/api/harness/feedback")
    def send_tester_feedback(body: TesterForm):
        def title_of(job_id: str):
            if not job_id:
                raise KeyError(job_id)
            try:
                return site.record(job_id).get("title")
            except HTTPException:
                raise KeyError(job_id)
        try:
            form = feedback.tester_of(body.model_dump(), title_of)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        site.query("INSERT INTO reviews (id, at, kind, job_id, form_version, reviewer, contact, lesson, answers, auto) "
                   "VALUES (?, ?, 'tester', ?, ?, ?, ?, ?, ?, NULL)",
                   [form["id"], form["at"], form["job_id"], form["form_version"], form["reviewer"], form["contact"],
                    json.dumps({"title": form["lesson_title"]}, ensure_ascii=False),
                    json.dumps(form["answers"], ensure_ascii=False)])
        note("tester_feedback", job_id=body.job_id)
        count = site.query("SELECT COUNT(*) AS n FROM reviews WHERE kind = 'tester'")
        return {"stored": True, "id": form["id"], "count": int(count[0]["n"]) if count else 1}

    @app.get("/api/harness/jobs/{job_id}/review_link")
    def review_link(job_id: str):
        site.record(job_id)
        token = feedback.review_token()
        if not token:
            raise HTTPException(status_code=503, detail="set LESSONFORGE_REVIEW_TOKEN on the server to share review links")
        return {"path": f"/app/?token={token}#review={job_id}"}

    # ── the task done by hand ──
    def task_of(job_id: str) -> dict:
        try:
            record = site.record(job_id)
        except HTTPException:
            raise KeyError(job_id)
        task, _ = tryit.clean(record.get("try_it"))
        if task is None:
            raise KeyError(job_id)
        return task

    @app.post("/api/harness/jobs/{job_id}/tryit")
    def send_tryit(job_id: str, body: TryIt):
        """The expected result is handed out only here, in reply to a STORED answer (``tryit.reveal``)."""
        try:
            task = task_of(job_id)
            answer = tryit.answer_of(job_id, body.model_dump())
        except KeyError:
            raise HTTPException(status_code=404, detail="this lesson has no try-it-yourself task")
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        site.query("INSERT INTO tryit (id, at, job_id, reviewer, done_in_class, prediction, observation, answer) "
                   "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                   [answer["id"], answer["at"], job_id, answer["reviewer"], 1 if answer["done_in_class"] else 0,
                    answer["prediction"], answer["observation"], answer["answer"]])
        note("tryit_sent", job_id=job_id)
        count = site.query("SELECT COUNT(*) AS n FROM tryit WHERE job_id = ?", [job_id])
        return tryit.reveal(task, answer["id"], int(count[0]["n"]) if count else 1)

    @app.get("/api/harness/jobs/{job_id}/tryit")
    def read_tryit(job_id: str):
        try:
            task = task_of(job_id)
        except KeyError:
            raise HTTPException(status_code=404, detail="not found")
        return tryit.summary_from(job_id, task, site.answers(job_id))

    # ── the dashboard ──
    @app.post("/api/harness/events")
    def event(body: Event):
        try:
            name, fields = analytics.client_fields(body.model_dump())
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        return {"stored": note(name, **fields)}

    @app.get("/api/harness/stats")
    def stats(days: int = 7, tz: int = 0, tests: int = 0, me: int = 1):
        """The studio's dashboard over this site's own visitors, plays and reviews (nothing is made or spent here)."""
        mine = (analytics.current() or {}).get("visitor", "")
        site.events.flush()
        jobs_ = site.jobs()
        students = site.reviews("student")

        def reviews():
            by_job: dict[str, list] = {}
            for review in students:
                by_job.setdefault(review["job_id"], []).append(review)
            return {row["job_id"]: row for row in feedback.all_from(sorted(by_job.items(), reverse=True))["lessons"]}

        return analytics.summarize(site.all_events(bool(tests)), jobs_, days=days, tz_minutes=tz,
                                   exclude="" if me else mine, reviews=reviews,
                                   tester_forms=lambda: len(site.reviews("tester")))

    # ── nothing is made here ──
    def refuse():
        raise HTTPException(status_code=403, detail=MAKING)

    for method, path in MAKING_ROUTES:
        app.add_api_route(path, refuse, methods=[method], include_in_schema=False)

    @app.api_route("/api/harness/{rest:path}", methods=["POST", "PUT", "PATCH", "DELETE"], include_in_schema=False)
    def refuse_any(rest: str):
        raise HTTPException(status_code=403, detail=MAKING)

    web = (os.getenv("LESSONFORGE_WEB_APP") or "").strip()
    if web and os.path.isdir(web):
        app.mount("/app", StaticFiles(directory=web, html=True), name="web_app")

    return app


app = create_app()
