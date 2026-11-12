"""Routes: /api/compile_video, /api/render_status, /api/video_history, ws status."""
import os
import json
import time
import uuid
import asyncio
import logging
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse

from ..codegen import sanitize_generated_code, validate_python
from ..config import _apply_env_overrides, VIDEO_DIR, GENERATED_DIR
from ..jobs import (_set_job, _get_job, _prune_jobs, RENDER_EXECUTOR,
                    RENDER_JOBS, RENDER_JOBS_LOCK)
from ..render import _run_render_job
from ..schemas import CompileRequest

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/api/compile_video")
def compile_video(body: CompileRequest):
    try:
        code = sanitize_generated_code(body.code.strip(), body.persona)
        scene_class = body.scene_class.strip()
        quality = body.quality.strip()
        aspect_ratio = body.aspect_ratio.strip()

        if not code:
            raise HTTPException(status_code=400, detail="Python code is required")

        # Fail fast (and cheaply) on a syntax error rather than spinning up Manim.
        ok, err = validate_python(code)
        if not ok:
            logger.error(f"Syntax error before render: {err}")
            raise HTTPException(status_code=400, detail=f"Syntax error before render: {err}")

        # Enqueue the render and return immediately; the client polls /render_status.
        _apply_env_overrides(body.env_overrides)
        job_id = str(uuid.uuid4())[:8]
        _set_job(job_id, state="queued", success=None, video_url=None, logs="", created=time.time())
        _prune_jobs()
        RENDER_EXECUTOR.submit(_run_render_job, job_id, code, scene_class, quality, aspect_ratio, body.persona, body.scene_scripts)
        logger.info(f"Queued render job {job_id} (scene '{scene_class}', quality '{quality}', parallel_scenes={len(body.scene_scripts) if body.scene_scripts else 0}).")
        return JSONResponse({"job_id": job_id, "state": "queued"}, status_code=202)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to queue video compilation")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/render_status/{job_id}")
def render_status(job_id: str):
    job = _get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Unknown render job id")
    return {"job_id": job_id, **job}


@router.get("/api/video_history")
def video_history():
    """All rendered videos (lab renders + merged ce/ finals) sorted newest-first,
    plus any in-flight render jobs — powers the /timeline progression viewer."""
    videos = []
    for base, url_prefix, source in [
        (VIDEO_DIR, "/static/videos", "lab_render"),
        (GENERATED_DIR, "/generated_videos", "merged_final"),
    ]:
        if not os.path.isdir(base):
            continue
        for name in os.listdir(base):
            if not name.endswith(".mp4"):
                continue
            path = os.path.join(base, name)
            try:
                st = os.stat(path)
            except OSError:
                continue
            entry = {
                "name": name,
                "url": f"{url_prefix}/{name}",
                "source": source,
                "mtime": st.st_mtime,
                "modified": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(st.st_mtime)),
                "size_mb": round(st.st_size / 1e6, 2),
            }
            # Sidecar written by the render job: verification status per video.
            # Videos without one (test-suite/raw compiles) show as "raw".
            try:
                with open(os.path.join(base, name + ".json"), encoding="utf-8") as f:
                    entry["render_meta"] = json.load(f)
            except Exception:
                pass
            videos.append(entry)
    videos.sort(key=lambda v: v["mtime"], reverse=True)
    with RENDER_JOBS_LOCK:
        jobs = [
            {"job_id": jid, "state": j.get("state"), "progress": j.get("progress"),
             "video_url": j.get("video_url"), "repair_rounds": j.get("repair_rounds")}
            for jid, j in RENDER_JOBS.items() if j.get("state") in ("queued", "running")
        ]
    return {"videos": videos, "active_jobs": jobs}


@router.websocket("/ws/render_status/{job_id}")
async def render_status_ws(websocket: WebSocket, job_id: str):
    """WebSocket push — sends job state every 1 s; closes when state is done/error.
    Replaces the 2-second HTTP polling loop used by CE clients."""
    await websocket.accept()
    try:
        while True:
            job = _get_job(job_id)
            if not job:
                await websocket.send_json({"error": "Unknown job"})
                break
            await websocket.send_json({"job_id": job_id, **job})
            if job.get("state") in ("done", "error"):
                break
            await asyncio.sleep(1.0)
    except WebSocketDisconnect:
        pass
