"""Publishing finished lessons from the GPU machine to the viewer site (R2; ``docs/DEPLOY_RENDER_VIEWER.md``).

Lessons are made here, on the studio server; the site on Render shows the finished ones and makes
nothing (``lessonforge/viewer.py``). What it shows is exactly what this module puts in the bucket
(``lessonforge/cloud.py``):

* ``api/jobs/<job_id>.json`` — the lesson's record, as ``GET /api/harness/jobs/{id}`` returns it here
  (``service.get_job``), so the app reads the same thing from either server;
* ``api/jobs.json`` — the list, as ``GET /api/harness/jobs`` returns its rows (``service.list_jobs``),
  newest first, finished lessons only;
* ``lessons/<job_id>/<path>`` — the files that record points at (video, captions, the player's
  questions, the outline of the cuts, the lesson, the review page and what that page links to), at the
  same paths as under ``/lessons/<job_id>/`` here.

Never a file ``harness/gate.py`` keeps private (``PRIVATE_IN_LESSON``: the sources' text, reviews,
try-it answers), never a render cache, the audio blocks or the logs: only files a record names are
sent, and those are checked against both lists.

Run by ``lessonforge publish`` and, when a lesson finishes, by ``service._run`` (advisory, only when R2
or ``LESSONFORGE_CLOUD_DIR`` is set and ``LESSONFORGE_PUBLISH`` is not ``0``). Sending again is free:
a file the bucket already has byte for byte is not sent, an unchanged record is not written.
"""
from __future__ import annotations

import os
import posixpath
import re
import threading
from pathlib import Path
from urllib.parse import unquote

from .. import cloud, paths
from . import gate

#: The job statuses a published lesson may have.
PUBLISHABLE = ("done", "needs_review")
#: Fields of a record that point at files under ``/lessons/<job_id>/``.
SERVED = ("video_url", "captions_url", "interactions_url", "outline_url", "lesson_url", "review_url")
#: Inside a lesson folder, never sent whatever names it (besides ``gate.PRIVATE_IN_LESSON``).
NEVER = re.compile(r"^(?:media|audio|logs|feedback|tryit|chapters)(?:/|$)|(?:^|/)(?:teaching_pack\.json|job\.json)$"
                   r"|(?:^|/)\.|\.part(?:\.|$)", re.I)
_LINK = re.compile(r"""(?:src|href)\s*=\s*["']([^"'#?]+)""", re.I)
_LIST_LOCK = threading.Lock()       # two lessons finishing together must not each write the list without the other


#: Critic scores (1-5) a lesson must reach to be published by itself. Pedagogy is left out: its rubric is off by
#: default, so its score says little yet.
GATED_SCORES = ("conceptual_accuracy", "visual_truthfulness", "explanatory_clarity")


def held_back(job: dict) -> list[str]:
    """Why a finished lesson should wait for a person instead of going to the site by itself ([] = it may go).

    Before 2026-11-07 every lesson that rendered was published, whatever its own checks said: the speed lesson
    went out with visual truthfulness 2/5, clarity 2/5, six plain picture/voice mismatches and failed timing
    checks. The lesson stays "done" and can still be sent by hand (``lessonforge publish``); this only stops
    the automatic send. ``LESSONFORGE_PUBLISH_GATE=0`` turns it off, ``LESSONFORGE_PUBLISH_MIN_SCORE`` (default 3)
    and ``LESSONFORGE_PUBLISH_MAX_MISMATCH`` (default 2) set the bar.
    """
    if (os.getenv("LESSONFORGE_PUBLISH_GATE") or "1").strip() == "0":
        return []
    try:
        least = float(os.getenv("LESSONFORGE_PUBLISH_MIN_SCORE") or 3)
        most_mismatch = int(os.getenv("LESSONFORGE_PUBLISH_MAX_MISMATCH") or 2)
    except ValueError:
        least, most_mismatch = 3.0, 2
    why = []
    scores = ((job.get("verification") or {}).get("scores")) or {}
    for name in GATED_SCORES:
        v = scores.get(name)
        if isinstance(v, (int, float)) and not isinstance(v, bool) and v < least:
            why.append(f"critic scored {name} {v:g}/5 (needs {least:g})")
    if ((job.get("checks") or {}).get("status")) == "technical_checks_failed":
        failed = (job.get("checks") or {}).get("failed") or []
        why.append("technical checks failed" + (f": {', '.join(map(str, failed[:3]))}" if failed else ""))
    findings = ((job.get("vision_review") or {}).get("findings")) or []
    plain = [f for f in findings if isinstance(f, dict) and f.get("kind") == "mismatch" and f.get("severity") == "high"]
    if len(plain) > most_mismatch:
        why.append(f"{len(plain)} plain picture/voice mismatches in the final video (at most {most_mismatch})")
    return why


def wanted() -> bool:
    """Whether a lesson that finishes here is published by itself."""
    return (os.getenv("LESSONFORGE_PUBLISH") or "1").strip() != "0" and cloud.configured()


def _sendable(job_id: str, rel: str) -> bool:
    if not rel or rel in (".", "..") or rel.startswith(("/", "../")) or "\\" in rel:
        return False
    return not gate.PRIVATE_IN_LESSON.match(f"/lessons/{job_id}/{rel}") and not NEVER.search(rel)


def _linked(page: Path) -> list[str]:
    """The relative links of a lesson's review page (its video, captions and the notes it links to)."""
    try:
        text = page.read_text(encoding="utf-8")
    except OSError:
        return []
    return [link for link in _LINK.findall(text) if "//" not in link and ":" not in link]


def files_of(record: dict, root: Path) -> list[str]:
    """The files of a lesson folder the record points at, as paths relative to the folder."""
    job_id = record["job_id"]
    base = f"/lessons/{job_id}/"
    wanted_ = []
    for field in SERVED:
        url = record.get(field)
        if isinstance(url, str) and url.startswith(base):
            wanted_.append(unquote(url[len(base):].split("?")[0]))
    if "review.html" in wanted_:
        wanted_ += [unquote(link) for link in _linked(root / "review.html")]
    found, inside = [], root.resolve()
    for rel in wanted_:
        rel = posixpath.normpath(rel)
        if rel in found or not _sendable(job_id, rel):
            continue
        path = root / rel
        try:
            if path.is_file() and path.resolve().is_relative_to(inside):
                found.append(rel)
        except OSError:
            continue
    return found


def publish(job_ids=(), *, everything: bool = False, dry_run: bool = False, store=None, log=print) -> dict:
    """Send finished lessons to the bucket and bring its list up to date.

    ``everything``: every finished lesson here; lessons the bucket lists that are no longer here (taken out of
    the history) are taken off the site. ``dry_run``: say what would be sent, send nothing.
    Returns a report: ``published``, ``skipped`` (id: why), ``sent`` / ``unchanged`` (files and records),
    ``bytes`` sent, ``removed``.
    """
    from . import service

    store = store if store is not None else (None if dry_run and not cloud.configured() else cloud.objects())
    rows = service.list_jobs(limit=100_000)
    by_id = {row["job_id"]: row for row in rows}
    if everything:
        chosen = [row["job_id"] for row in rows if row.get("status") in PUBLISHABLE and row.get("video_url")]
    else:
        chosen = list(dict.fromkeys(str(j) for j in job_ids))
    report = {"published": [], "skipped": {}, "sent": 0, "unchanged": 0, "bytes": 0, "removed": [], "dry_run": dry_run}
    listed: dict[str, dict] = {}
    for job_id in chosen:
        if not cloud.safe_job_id(job_id):
            report["skipped"][job_id] = "not a lesson id"
            continue
        try:
            record = service.get_job(job_id)
        except KeyError:
            report["skipped"][job_id] = "no such lesson here"
            continue
        if record.get("status") not in PUBLISHABLE or not record.get("video_url"):
            report["skipped"][job_id] = f"not a finished lesson (status {record.get('status')})"
            continue
        root = paths.home() / "lessons" / job_id
        files = files_of(record, root)
        video = unquote(str(record["video_url"]))[len(f"/lessons/{job_id}/"):]
        if video not in files:
            report["skipped"][job_id] = "its video file is missing"
            continue
        sent = size = 0
        for rel in files:
            path = root / rel
            if dry_run:
                size += path.stat().st_size
                continue
            if store.upload_file(path, cloud.lesson_key(job_id, rel), cloud.content_type(rel)):
                sent += 1
                size += path.stat().st_size
            else:
                report["unchanged"] += 1
        if not dry_run:
            if store.put_json(cloud.job_key(job_id), record):
                sent += 1
            else:
                report["unchanged"] += 1
        report["sent"] += sent
        report["bytes"] += size
        listed[job_id] = by_id.get(job_id) or _row(record)
        report["published"].append(job_id)
        log(f"[publish] {job_id}: {len(files)} file(s)" + (f", {size / 1e6:.1f} MB would be sent" if dry_run else
            f" and its record; {sent} sent ({size / 1e6:.1f} MB), the rest already there"))
    if store is None:
        return report
    with _LIST_LOCK:
        current = store.get_json(cloud.JOBS_KEY) or {}
        rows_there = [r for r in (current.get("jobs") or []) if isinstance(r, dict) and r.get("job_id")]
        if everything:
            # Taken out of the history here (its folder moved to removed/): taken off the site too.
            gone = [r["job_id"] for r in rows_there
                    if r["job_id"] not in by_id and not (paths.home() / "lessons" / r["job_id"]).is_dir()]
            report["removed"] = gone
        if dry_run:
            for job_id in report["removed"]:
                log(f"[publish] {job_id}: no longer here, would be taken off the site")
            return report
        rows_now = [r for r in rows_there if r["job_id"] not in listed and r["job_id"] not in report["removed"]]
        rows_now += list(listed.values())
        rows_now.sort(key=lambda r: r.get("created") or 0, reverse=True)
        if store.put_json(cloud.JOBS_KEY, {"jobs": rows_now}):
            report["sent"] += 1
        elif listed or report["removed"]:
            report["unchanged"] += 1
    for job_id in report["removed"]:
        _take_off(store, job_id)
        log(f"[publish] {job_id}: no longer here, taken off the site")
    return report


def _row(record: dict) -> dict:
    """A list row made from a record, the way ``service.list_jobs`` makes it (when the list did not have it)."""
    return {"job_id": record["job_id"], "status": record.get("status"), "stage": record.get("stage"),
            "title": record.get("title"), "video_url": record.get("video_url"), "created": record.get("created"),
            "duration_seconds": (record.get("checks") or {}).get("duration_seconds"),
            "language": (record.get("brief") or {}).get("language"),
            "mode": (record.get("brief") or {}).get("mode") or "intent", "error": record.get("error"),
            "elsewhere": bool(record.get("elsewhere"))}


def _take_off(store, job_id: str) -> int:
    """The record, then the files (the list no longer names it by now)."""
    store.delete(cloud.job_key(job_id))
    return store.delete_prefix(cloud.lesson_prefix(job_id))


def unpublish(job_id: str, *, store=None, log=print) -> bool:
    """Take one lesson off the site: out of the list first, then its record and its files. True if it was listed."""
    if not cloud.safe_job_id(job_id):
        return False
    store = store if store is not None else cloud.objects()
    with _LIST_LOCK:
        current = store.get_json(cloud.JOBS_KEY) or {}
        rows = [r for r in (current.get("jobs") or []) if isinstance(r, dict)]
        kept = [r for r in rows if r.get("job_id") != job_id]
        if len(kept) != len(rows):
            store.put_json(cloud.JOBS_KEY, {"jobs": kept})
    files = _take_off(store, job_id)
    log(f"[publish] {job_id}: taken off the site ({files} file(s))")
    return len(kept) != len(rows)


def after_lesson(job_id: str, log=print) -> dict | None:
    """Called by ``service._run`` when a lesson has finished (inside its ``advisory``: an error is logged there)."""
    if not wanted():
        return None
    return publish([job_id], log=log)


def after_removal(job_id: str, log=print) -> None:
    """Called by ``service.remove_job`` once the folder is moved out. Never raises: the removal has happened."""
    if not wanted():
        return
    try:
        unpublish(job_id, log=log)
    except Exception as exc:  # noqa: BLE001 - the site is a copy; `lessonforge publish --all` puts it right later
        log(f"[publish] {job_id}: could not take it off the site: {type(exc).__name__}: {str(exc)[:160]}")
