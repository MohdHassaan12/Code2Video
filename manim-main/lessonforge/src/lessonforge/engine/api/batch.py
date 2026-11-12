"""Route: /api/batch_render_and_merge."""
import uuid
import time
import logging
import os
import threading
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from ..config import _apply_env_overrides
from ..jobs import _set_job, _prune_jobs, RENDER_EXECUTOR
from ..render import _run_batch_render_job
from ..assets import determine_background
from ..schemas import BatchRenderRequest

logger = logging.getLogger(__name__)
router = APIRouter()
_ENV_OVERRIDE_LOCK = threading.Lock()


def _run_batch_render_with_env(
    job_id,
    nodes,
    style,
    persona,
    language,
    speaker,
    background,
    quality,
    aspect_ratio,
    skip_layout_review,
    tts_provider,
    gemini_tts_model,
    tech_terms,
    env_overrides,
):
    """Run one render with its overrides, then restore the process environment."""
    env_overrides = env_overrides or {}
    with _ENV_OVERRIDE_LOCK:
        previous = {key: os.environ.get(key) for key in env_overrides}
        try:
            _apply_env_overrides(env_overrides)
            _run_batch_render_job(
                job_id,
                nodes,
                style,
                persona,
                language,
                speaker,
                background,
                quality,
                aspect_ratio,
                skip_layout_review,
                tts_provider,
                gemini_tts_model,
                tech_terms,
            )
        finally:
            for key, value in previous.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

@router.post("/api/batch_render_and_merge")
def batch_render_and_merge(body: BatchRenderRequest):
    try:
        nodes = body.nodes
        style = body.style.strip()
        background = body.background.strip()
        persona = body.persona.strip().lower()
        language = body.language.strip()
        speaker = body.speaker.strip()
        tts_provider = body.tts_provider.strip()
        gemini_tts_model = body.gemini_tts_model.strip()
        quality = body.quality.strip()
        aspect_ratio = body.aspect_ratio.strip()
        skip_layout_review = body.skip_layout_review
        tech_terms = body.tech_terms.strip().lower()

        if not nodes:
            raise HTTPException(status_code=400, detail="A list of nodes is required")

        # If background is default, try to infer one dynamically from the first node
        if background == "default" and nodes:
            first_topic = nodes[0].get("content", {}).get("heading") or nodes[0].get("id") or ""
            background = determine_background(style, first_topic)

        env_overrides = dict(body.env_overrides or {})
        job_id = str(uuid.uuid4())[:8]
        _set_job(job_id, state="queued", success=None, video_url=None, logs="", current_step=0, total_steps=len(nodes), progress="Queued batch render job...", created=time.time(), env_overrides=env_overrides)
        _prune_jobs()

        RENDER_EXECUTOR.submit(
            _run_batch_render_with_env,
            job_id,
            nodes,
            style,
            persona,
            language,
            speaker,
            background,
            quality,
            aspect_ratio,
            skip_layout_review,
            tts_provider,
            gemini_tts_model,
            tech_terms,
            env_overrides,
        )

        logger.info(f"Queued batch render job {job_id} for {len(nodes)} nodes.")
        return JSONResponse({"job_id": job_id, "state": "queued"}, status_code=202)

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to queue batch render job")
        raise HTTPException(status_code=500, detail=str(e))
