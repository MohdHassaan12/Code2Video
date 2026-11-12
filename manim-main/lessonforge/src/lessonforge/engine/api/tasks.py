"""Async LLM tasks — storyboard + codegen as polled jobs instead of held-open HTTP.

Why this exists: ``/api/generate_storyboard`` and ``/api/generate_code`` do minutes
of LLM work inside the request. When a model chain falls through (a reasoning model
burning the whole token ceiling and returning ``finish_reason=length`` is the observed
shape, 2026-08-01), the browser gives up on the open connection and the user sees a
bare "network error" — while the server is still working and eventually succeeds.

Same contract as the render jobs: POST returns a task id immediately, the client
polls. The sync routes in ``generation.py`` stay exactly as they are (the classic UI
and ``ce/`` still use them); this is additive.

Progress: LLM/codegen log records emitted **on the worker thread** are captured and
attached to the task, so "attempting model X" / "model X truncated, falling back" is
visible to the user instead of silence. Long runs must show progress — silence reads
as a hang.
"""
import logging
import threading
import time
import uuid

from fastapi import APIRouter, Depends, HTTPException

from lessonforge.engine.dependencies import APIKeys, resolve_api_keys
from ..llm import get_genai_client, describe_gemini_error
from ..storyboard import generate_storyboard_impl
from ..codegen_pipeline import generate_code_impl
from .generation import merge_sources
from ..schemas import StoryboardRequest, CodegenRequest
from ..jobs import JobStore

logger = logging.getLogger(__name__)
router = APIRouter()

# Separate pool from RENDER_EXECUTOR: a codegen task must never occupy a render
# worker (that pool is sized for renders, default 2).
from concurrent.futures import ThreadPoolExecutor
import os

TASK_EXECUTOR = ThreadPoolExecutor(max_workers=int(os.getenv("LLM_TASK_WORKERS", "4")))
_TASKS = JobStore(max_tracked=60)

# thread id -> task id, so the log handler can attribute a record to its task.
_THREAD_TASK = {}
_THREAD_TASK_LOCK = threading.Lock()

MAX_PROGRESS_LINES = 40


class _TaskProgressHandler(logging.Handler):
    """Attach pipeline log lines to whichever task is running on this thread."""

    def emit(self, record):
        try:
            with _THREAD_TASK_LOCK:
                task_id = _THREAD_TASK.get(threading.get_ident())
            if not task_id:
                return
            msg = record.getMessage()
            if len(msg) > 300:
                msg = msg[:300] + "…"
            task = _TASKS.get(task_id)
            if not task:
                return
            lines = list(task.get("progress_lines") or [])
            lines.append({"level": record.levelname, "text": msg, "at": time.time()})
            _TASKS.set(task_id, progress_lines=lines[-MAX_PROGRESS_LINES:], progress=msg)
        except Exception:
            pass  # progress reporting must never break the task


_HANDLER = _TaskProgressHandler()
_HANDLER.setLevel(logging.INFO)
for _name in ("lessonforge.engine.llm", "lessonforge.engine.codegen", "lessonforge.engine.codegen_pipeline",
              "lessonforge.engine.storyboard", "lessonforge.transpiler"):
    logging.getLogger(_name).addHandler(_HANDLER)


def _run_task(task_id, fn):
    tid = threading.get_ident()
    with _THREAD_TASK_LOCK:
        _THREAD_TASK[tid] = task_id
    _TASKS.set(task_id, state="running", started=time.time())
    try:
        result = fn()
        _TASKS.set(task_id, state="done", result=result, finished=time.time())
    except HTTPException as e:
        _TASKS.set(task_id, state="error", error=str(e.detail), status=e.status_code, finished=time.time())
    except Exception as e:
        logger.exception("Async task %s failed", task_id)
        msg, status = describe_gemini_error(e)
        _TASKS.set(task_id, state="error", error=msg, status=status, finished=time.time())
    finally:
        with _THREAD_TASK_LOCK:
            _THREAD_TASK.pop(tid, None)
        _TASKS.prune()


def _enqueue(fn):
    task_id = str(uuid.uuid4())[:8]
    _TASKS.set(task_id, state="queued", created=time.time(), progress="queued", progress_lines=[])
    TASK_EXECUTOR.submit(_run_task, task_id, fn)
    return {"task_id": task_id, "state": "queued"}


def _routing(provider: str | None, model: str | None, task: str):
    """The Studio's provider / model choice for ONE job: applied for the job, undone after it, and an invalid
    choice raises (the task shows the reason) instead of being logged and ignored."""
    from .. import model_routing
    return model_routing.scoped_routing(provider, model, task)


@router.post("/api/tasks/storyboard", status_code=202)
def task_storyboard(body: StoryboardRequest, keys: APIKeys = Depends(resolve_api_keys)):
    if not body.topic:
        raise HTTPException(status_code=400, detail="Topic is required")
    client = get_genai_client(keys)

    def work():
        with _routing(body.llm_provider, body.llm_model, "storyboard"):
            return generate_storyboard_impl(
                client=client, topic=body.topic, persona=body.persona, language=body.language,
                style=body.style, context=merge_sources(body.context, body.sources),
                speaker=body.speaker,
                tts_provider=body.tts_provider, gemini_tts_model=body.gemini_tts_model,
                keys=keys, tech_terms=body.tech_terms,
                target_duration_s=body.target_duration_s,
            )

    return _enqueue(work)


@router.post("/api/tasks/codegen", status_code=202)
def task_codegen(body: CodegenRequest, keys: APIKeys = Depends(resolve_api_keys)):
    if not body.storyboard:
        raise HTTPException(status_code=400, detail="Storyboard JSON is required")
    client = get_genai_client(keys)

    def work():
        with _routing(body.llm_provider, body.llm_model, "code"):
            return generate_code_impl(
                client=client, storyboard=body.storyboard, style=body.style,
                background=body.background, persona=body.persona, language=body.language,
                speaker=body.speaker, tts_provider=body.tts_provider,
                gemini_tts_model=body.gemini_tts_model,
                skip_layout_review=body.skip_layout_review, keys=keys,
            )

    return _enqueue(work)


@router.get("/api/tasks/{task_id}")
def task_status(task_id: str):
    task = _TASKS.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Unknown task id (the server may have restarted).")
    out = {"task_id": task_id, "state": task.get("state"), "progress": task.get("progress"),
           "progress_lines": task.get("progress_lines") or []}
    if task.get("state") == "done":
        out["result"] = task.get("result")
    if task.get("state") == "error":
        out["error"] = task.get("error")
    started = task.get("started")
    if started:
        out["elapsed"] = round((task.get("finished") or time.time()) - started, 1)
    return out
