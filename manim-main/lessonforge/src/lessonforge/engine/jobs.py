"""Async render job registry (in-memory, bounded) + the render thread pool +
per-video sidecar writer.

State is held in a dict keyed by job id, so a crashing worker can't silently lose the
job the way a fire-and-forget thread would. Renders run on a small thread pool so a
request no longer blocks for the whole (potentially minutes-long) render.

``JobStore`` encapsulates the dict + lock; the module-level ``RENDER_JOBS`` /
``RENDER_JOBS_LOCK`` / ``_set_job`` / ``_get_job`` / ``_prune_jobs`` names are kept as
thin aliases so the render core, the routes, and ``/api/video_history`` keep their
existing call shape.
"""
import os
import json
import threading
import logging
from concurrent.futures import ThreadPoolExecutor

from .config import VIDEO_DIR

logger = logging.getLogger(__name__)

RENDER_EXECUTOR = ThreadPoolExecutor(max_workers=int(os.getenv("RENDER_WORKERS", "2")))
MAX_TRACKED_JOBS = 50


class JobStore:
    """Thread-safe, bounded registry of render jobs keyed by job id."""

    def __init__(self, max_tracked=MAX_TRACKED_JOBS):
        self.jobs = {}
        self.lock = threading.Lock()
        self.max_tracked = max_tracked

    def set(self, job_id, **fields):
        with self.lock:
            self.jobs.setdefault(job_id, {}).update(fields)

    def get(self, job_id):
        with self.lock:
            job = self.jobs.get(job_id)
            return dict(job) if job else None

    def prune(self):
        """Keep the job table bounded by dropping the oldest finished jobs."""
        with self.lock:
            if len(self.jobs) <= self.max_tracked:
                return
            finished = sorted(
                (jid for jid, j in self.jobs.items() if j.get("state") in ("done", "error")),
                key=lambda jid: self.jobs[jid].get("created", 0),
            )
            for jid in finished[: len(self.jobs) - self.max_tracked]:
                self.jobs.pop(jid, None)


# Process-wide singleton + back-compat aliases (same dict / lock objects, so callers
# that iterate RENDER_JOBS under RENDER_JOBS_LOCK keep working unchanged).
_JOBS = JobStore(MAX_TRACKED_JOBS)
RENDER_JOBS = _JOBS.jobs
RENDER_JOBS_LOCK = _JOBS.lock
_set_job = _JOBS.set
_get_job = _JOBS.get
_prune_jobs = _JOBS.prune


def _probe_duration_s(mp4_path):
    """Real duration of the rendered mp4 via ffprobe, or None. Non-fatal by design —
    the duration contract is measured, and a missing measurement must never cost a
    video that already rendered."""
    try:
        import subprocess
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", mp4_path],
            capture_output=True, text=True, timeout=15,
        )
        return round(float(out.stdout.strip()), 1)
    except Exception:
        return None


def _write_video_sidecar(video_url, **meta):
    """Persist per-video render metadata next to the mp4 so /api/video_history can
    show verification status (clean / repaired / violations remaining) per video."""
    try:
        if not video_url:
            return
        base = os.path.basename(video_url)
        # The duration-contract loop closer: the storyboard logs its word-count
        # ESTIMATE ([DURATION] in app/storyboard.py); this is what actually rendered.
        _dur = _probe_duration_s(os.path.join(VIDEO_DIR, base))
        if _dur is not None:
            meta.setdefault("rendered_duration_s", _dur)
        path = os.path.join(VIDEO_DIR, base + ".json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(meta, f)
    except Exception as e:
        logger.warning(f"Could not write video sidecar: {e}")
