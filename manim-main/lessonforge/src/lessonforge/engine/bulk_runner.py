"""Bulk video generation for the STEM Animation Lab.

Modeled on the NotebookLM bulk_orchestrator pattern: a JSON manifest is the
single source of truth (one row per topic, written atomically under a lock),
every stage artifact is cached on disk so a dead run resumes from its last
completed stage with zero re-billed LLM calls, and topics run through a small
thread pool while the lab server's RENDER_EXECUTOR provides the natural render
throttle.

Three ways in:
  • CLI:        python3 bulk_runner.py plan.json [--parallel 2] [--dry-run] [--resume RUN_ID]
  • Web UI:     http://localhost:5000/bulk  (served by app.py)
  • API:        POST /api/bulk/start, GET /api/bulk/runs, GET /api/bulk/status/{run_id}

Plan file schema (topics may be bare strings or dicts with per-topic overrides):
  {
    "settings": {"language": "en-IN", "persona": "en", "speaker": "shubh",
                 "tech_terms": "english",   # english | bilingual | native
                 "style": "3blue1brown/minimalist/neon", "quality": "l",
                 "aspect_ratio": "widescreen", "grade": "9", "subject": "Science",
                 "parallel": 2},
    "topics": ["Photosynthesis", {"topic": "Ohm's Law", "grade": "10"}]
  }

Run state lives in bulk_runs/<run_id>/ (git-ignored):
  manifest.json                     — run status, one row per topic
  <key>/storyboard.json, code.json  — stage caches (code.json holds code + scene_scripts)
Videos render into the lab's static/videos/ as usual (with .mp4.json sidecars),
so finished rows appear on /timeline too.
"""

import argparse
import concurrent.futures
import json
import logging
import os
import re
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

import requests

logger = logging.getLogger("bulk_runner")

LAB_URL = os.getenv("BULK_LAB_URL", "http://localhost:5000")
from lessonforge import paths as _paths
BULK_DIR = _paths.sub("bulk_runs")

DEFAULT_SETTINGS = {
    "language": "hi-IN",
    "persona": "hybrid",
    "tech_terms": "english",  # english | bilingual | native (how STEM terms are narrated)
    "speaker": "shubh",
    "style": "3blue1brown/minimalist/neon",
    "quality": "l",
    "aspect_ratio": "widescreen",
    "grade": "9",
    "subject": "Science",
    "parallel": 2,
    "env_overrides": {},
}

_MANIFEST_LOCK = threading.Lock()
# run_id -> True while an engine thread is working that run.
_ACTIVE_RUNS = {}


def _now():
    return datetime.now().isoformat(timespec="seconds")


def _slug(text, fallback="topic"):
    s = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")[:40]
    return s or fallback


def _run_dir(run_id):
    return BULK_DIR / run_id


def _manifest_path(run_id):
    return _run_dir(run_id) / "manifest.json"


def _read_manifest(run_id):
    try:
        with open(_manifest_path(run_id), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


def _write_manifest(manifest):
    """Atomic write (tmp + replace) under a lock — the manifest is read
    concurrently by the status endpoint and the gallery page."""
    with _MANIFEST_LOCK:
        manifest["updated_at"] = _now()
        path = _manifest_path(manifest["run_id"])
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=1)
        os.replace(tmp, path)


def _normalize_topics(topics, settings):
    rows = []
    for i, t in enumerate(topics):
        if isinstance(t, str):
            t = {"topic": t}
        topic = (t.get("topic") or "").strip()
        if not topic:
            continue
        rows.append({
            "key": f"t{i:02d}-{_slug(topic)}",
            "topic": topic,
            "grade": str(t.get("grade") or settings["grade"]),
            "subject": t.get("subject") or settings["subject"],
            "context_text": t.get("context") or None,
            "status": "pending",       # pending | storyboard | codegen | render | done | failed
            "error": None,
            "video_url": None,
            "storyboard_cached": False,
            "code_cached": False,
            "seconds": None,
            "created_at": _now(),
            "updated_at": _now(),
        })
    return rows


def create_run(topics, settings=None, persist=True):
    settings = {**DEFAULT_SETTINGS, **(settings or {})}
    rows = _normalize_topics(topics, settings)
    if not rows:
        raise ValueError("No non-empty topics given")
    run_id = f"bulk_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:4]}"
    manifest = {
        "run_id": run_id,
        "created_at": _now(),
        "updated_at": _now(),
        "settings": settings,
        "rows": rows,
    }
    if persist:  # dry runs stay in memory — they must create and spend nothing
        _write_manifest(manifest)
    return manifest


def plan_summary(manifest):
    """Dry-run view: what would run, what is already cached."""
    rows = manifest["rows"]
    return {
        "run_id": manifest["run_id"],
        "settings": manifest["settings"],
        "topics_total": len(rows),
        "already_done": sum(1 for r in rows if r["status"] == "done"),
        "to_run": [
            {"key": r["key"], "topic": r["topic"], "status": r["status"],
             "storyboard_cached": r["storyboard_cached"], "code_cached": r["code_cached"]}
            for r in rows if r["status"] != "done"
        ],
    }


# ── Per-topic pipeline (storyboard → code → render), cache-first ─────────────

def _stage_file(run_id, key, name):
    d = _run_dir(run_id) / key
    d.mkdir(parents=True, exist_ok=True)
    return d / name


def _update_row(manifest, row, **fields):
    row.update(fields, updated_at=_now())
    _write_manifest(manifest)


def _run_topic(manifest, row, force=False):
    run_id = manifest["run_id"]
    s = manifest["settings"]
    t_start = time.time()
    label = f"[{run_id}] {row['key']}"

    try:
        # 1. Storyboard (cache-first)
        sb_path = _stage_file(run_id, row["key"], "storyboard.json")
        storyboard = None
        if sb_path.exists() and not force:
            try:
                storyboard = json.loads(sb_path.read_text(encoding="utf-8"))
                _update_row(manifest, row, storyboard_cached=True)
                logger.info("%s storyboard ✓ (cached)", label)
            except (OSError, json.JSONDecodeError):
                storyboard = None
        if storyboard is None:
            _update_row(manifest, row, status="storyboard")
            context = {
                "grade": row["grade"],
                "grade_level": f"Grade {row['grade']}",
                "subject": row["subject"],
                "node_type": "concept",
            }
            if row.get("context_text"):
                context["ncert_content"] = {"heading": row["topic"], "full_content": row["context_text"]}
            r = requests.post(f"{LAB_URL}/api/generate_storyboard", json={
                "topic": row["topic"], "style": s["style"], "persona": s["persona"],
                "language": s["language"], "speaker": s["speaker"], "context": context,
                "tech_terms": s.get("tech_terms", "english"),
            }, timeout=300)
            r.raise_for_status()
            storyboard = r.json()
            sb_path.write_text(json.dumps(storyboard, ensure_ascii=False), encoding="utf-8")
            logger.info("%s storyboard ✓", label)

        # 2. Codegen (cache-first)
        code_path = _stage_file(run_id, row["key"], "code.json")
        codegen = None
        if code_path.exists() and not force:
            try:
                codegen = json.loads(code_path.read_text(encoding="utf-8"))
                _update_row(manifest, row, code_cached=True)
                logger.info("%s codegen ✓ (cached)", label)
            except (OSError, json.JSONDecodeError):
                codegen = None
        if codegen is None:
            _update_row(manifest, row, status="codegen")
            r = requests.post(f"{LAB_URL}/api/generate_code", json={
                "storyboard": storyboard, "style": s["style"], "persona": s["persona"],
                "language": s["language"], "speaker": s["speaker"],
                "tts_provider": os.getenv("TTS_PROVIDER", "sarvam"),
                "gemini_tts_model": os.getenv("GEMINI_TTS_MODEL", "gemini-3.1-flash-tts-preview"),
            }, timeout=600)
            r.raise_for_status()
            data = r.json()
            codegen = {
                "code": data["code"],
                "scene_class": data["scene_class"],
                "scene_scripts": data.get("scene_scripts") or None,
            }
            code_path.write_text(json.dumps(codegen, ensure_ascii=False), encoding="utf-8")
            logger.info("%s codegen ✓", label)

        # 3. Render via the real pipeline (parallel scenes + overlap repair +
        # sidecar). The server owns discarding repair losers — no new
        # compile_manim_code caller here.
        _update_row(manifest, row, status="render")
        payload = {
            "code": codegen["code"], "scene_class": codegen["scene_class"],
            "quality": s["quality"], "aspect_ratio": s["aspect_ratio"],
            "persona": s["persona"],
        }
        if codegen.get("scene_scripts"):
            payload["scene_scripts"] = codegen["scene_scripts"]
        if s.get("env_overrides"):
            payload["env_overrides"] = s["env_overrides"]
        r = requests.post(f"{LAB_URL}/api/compile_video", json=payload, timeout=60)
        if r.status_code != 202:
            raise RuntimeError(f"compile_video returned {r.status_code}: {r.text[:500]}")
        job_id = r.json()["job_id"]

        while True:
            time.sleep(3)
            st = requests.get(f"{LAB_URL}/api/render_status/{job_id}", timeout=30)
            st.raise_for_status()
            status = st.json()
            if status.get("state") in ("done", "error"):
                break

        if status.get("state") != "done" or not status.get("success"):
            raise RuntimeError((status.get("logs") or "Render failed")[-1500:])

        _update_row(manifest, row, status="done", video_url=status["video_url"],
                    error=None, seconds=round(time.time() - t_start, 1))
        logger.info("%s render ✓ → %s (%.0fs)", label, status["video_url"], time.time() - t_start)

    except Exception as e:
        _update_row(manifest, row, status="failed", error=str(e)[:2000],
                    seconds=round(time.time() - t_start, 1))
        logger.error("%s FAILED: %s", label, e)


def run_bulk(manifest, force=False):
    """Run all not-done rows through the pipeline. Blocking; call in a thread
    for the API path. Already-done rows with a surviving video are skipped."""
    run_id = manifest["run_id"]
    _ACTIVE_RUNS[run_id] = True
    try:
        todo = [r for r in manifest["rows"] if force or r["status"] != "done"]
        if force:
            for r in todo:
                _update_row(manifest, r, status="pending", error=None, video_url=None,
                            storyboard_cached=False, code_cached=False)
        logger.info("[%s] starting: %d/%d topics to run, parallel=%s",
                    run_id, len(todo), len(manifest["rows"]), manifest["settings"]["parallel"])
        workers = max(1, int(manifest["settings"].get("parallel", 2)))
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
            futures = [pool.submit(_run_topic, manifest, row, force) for row in todo]
            for f in futures:
                f.result()
        done = sum(1 for r in manifest["rows"] if r["status"] == "done")
        logger.info("[%s] finished: %d/%d done", run_id, done, len(manifest["rows"]))
    finally:
        _ACTIVE_RUNS.pop(run_id, None)
    return manifest


def list_runs():
    runs = []
    if BULK_DIR.is_dir():
        for d in sorted(BULK_DIR.iterdir(), reverse=True):
            m = _read_manifest(d.name)
            if not m:
                continue
            rows = m["rows"]
            runs.append({
                "run_id": m["run_id"],
                "created_at": m["created_at"],
                "updated_at": m.get("updated_at"),
                "active": bool(_ACTIVE_RUNS.get(m["run_id"])),
                "settings": m["settings"],
                "topics_total": len(rows),
                "done": sum(1 for r in rows if r["status"] == "done"),
                "failed": sum(1 for r in rows if r["status"] == "failed"),
            })
    return runs


# ── FastAPI surface (mounted by app.py) ──────────────────────────────────────

try:
    from fastapi import APIRouter, HTTPException
    from pydantic import BaseModel

    router = APIRouter()

    class BulkStartRequest(BaseModel):
        topics: list
        settings: dict = {}
        dry_run: bool = False

    @router.post("/api/bulk/start")
    def bulk_start(body: BulkStartRequest):
        try:
            manifest = create_run(body.topics, body.settings, persist=not body.dry_run)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        if body.dry_run:
            summary = plan_summary(manifest)
            summary["dry_run"] = True
            return summary
        threading.Thread(target=run_bulk, args=(manifest,), daemon=True,
                         name=f"bulk-{manifest['run_id']}").start()
        return {"run_id": manifest["run_id"], "state": "started",
                "topics_total": len(manifest["rows"])}

    @router.get("/api/bulk/runs")
    def bulk_runs():
        return {"runs": list_runs()}

    @router.get("/api/bulk/status/{run_id}")
    def bulk_status(run_id: str):
        manifest = _read_manifest(run_id)
        if not manifest:
            raise HTTPException(status_code=404, detail="Unknown bulk run id")
        manifest["active"] = bool(_ACTIVE_RUNS.get(run_id))
        return manifest

    @router.post("/api/bulk/retry/{run_id}")
    def bulk_retry(run_id: str):
        manifest = _read_manifest(run_id)
        if not manifest:
            raise HTTPException(status_code=404, detail="Unknown bulk run id")
        if _ACTIVE_RUNS.get(run_id):
            raise HTTPException(status_code=409, detail="Run is already active")
        # Re-queue failed/interrupted rows; done rows are never re-billed.
        for row in manifest["rows"]:
            if row["status"] in ("failed", "storyboard", "codegen", "render"):
                row["status"] = "pending"
                row["error"] = None
        _write_manifest(manifest)
        threading.Thread(target=run_bulk, args=(manifest,), daemon=True,
                         name=f"bulk-{run_id}").start()
        return {"run_id": run_id, "state": "restarted"}

except ImportError:  # CLI use without fastapi installed
    router = None


# ── CLI ──────────────────────────────────────────────────────────────────────

def _load_plan(path):
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    if p.suffix == ".txt":
        return {"settings": {}, "topics": [ln.strip() for ln in text.splitlines() if ln.strip()]}
    data = json.loads(text)
    if isinstance(data, list):
        return {"settings": {}, "topics": data}
    return data


def main():
    ap = argparse.ArgumentParser(description="Bulk-generate STEM animation videos via the lab server.")
    ap.add_argument("plan", nargs="?", help="Plan file: JSON ({settings, topics}) or .txt (one topic per line)")
    ap.add_argument("--parallel", type=int, help="Concurrent topics (overrides plan settings)")
    ap.add_argument("--dry-run", action="store_true", help="Print the plan, spend nothing")
    ap.add_argument("--resume", metavar="RUN_ID", help="Resume an existing run (skips done rows, reuses stage caches)")
    ap.add_argument("--force", action="store_true", help="Ignore caches and regenerate everything")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    if args.resume:
        manifest = _read_manifest(args.resume)
        if not manifest:
            ap.error(f"No manifest for run {args.resume} under {BULK_DIR}")
    else:
        if not args.plan:
            ap.error("A plan file is required unless --resume is given")
        plan = _load_plan(args.plan)
        settings = plan.get("settings") or {}
        if args.parallel:
            settings["parallel"] = args.parallel
        manifest = create_run(plan.get("topics") or [], settings, persist=not args.dry_run)

    if args.parallel:
        manifest["settings"]["parallel"] = args.parallel

    if args.dry_run:
        print(json.dumps(plan_summary(manifest), indent=2, ensure_ascii=False))
        return

    try:
        requests.get(f"{LAB_URL}/api/video_history", timeout=5)
    except requests.RequestException:
        raise SystemExit(f"Lab server is not reachable at {LAB_URL} — start it first "
                         f"(lessonforge serve).")

    run_bulk(manifest, force=args.force)
    failed = [r for r in manifest["rows"] if r["status"] == "failed"]
    print(f"\nRun {manifest['run_id']}: "
          f"{sum(1 for r in manifest['rows'] if r['status'] == 'done')}/{len(manifest['rows'])} done.")
    if failed:
        print(f"{len(failed)} failed — retry with: python3 bulk_runner.py --resume {manifest['run_id']}")
        for r in failed:
            print(f"  ✗ {r['topic']}: {(r['error'] or '')[:160]}")


if __name__ == "__main__":
    main()
