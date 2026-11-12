"""
lessonforge.engine — the storyboard → Manim → verified-video engine (FastAPI server).

Formerly the ``stem_animation_lab/app`` package of concept_explorer. Importing this
package builds the FastAPI ``app`` and re-exports the full public surface, so
``from lessonforge.engine import X`` and ``uvicorn lessonforge.engine:app`` both work.
Launch with ``lessonforge serve`` (or ``python -m lessonforge.engine``).

Module map (follows the video-pipeline stages):

    config        paths, render limits, env-override allowlist
    bootstrap     ffmpeg / LaTeX / SoX / sound-asset self-healing
    schemas       Pydantic Scene-DSL + request bodies
    llm           provider routing (Gemini -> OpenRouter -> Groq) + JSON helpers
    rag           ChromaDB error->repair + component retrieval
    codegen       Manim code sanitize / validate / repair / layout critic
    assets        non-Manim item detection + svg/molecule preflight probe
    storyboard    storyboard generation + shape/language gate + cache
    codegen_pipeline  storyboard -> Manim script (transpiler + LLM fallback)
    render        compile + dry-run probe + overlap repair (static validate + repair agent)
    jobs          async render-job registry + thread pool + sidecars
    api/*         FastAPI routers grouped by concern
    pipeline/*    typed stage protocol + Visual-Director / Vision-QA agent scaffold (stubs)

See ``engine/README.md`` for the stage protocol and the agent stages.
"""
import os
import logging

from dotenv import load_dotenv

# .env must load before anything reads provider keys (LESSONFORGE_NO_DOTENV=1 opts out; see lessonforge/env.py).
from ..env import dotenv_disabled  # noqa: E402

if not dotenv_disabled():
    load_dotenv()

# Importing config configures logging and resolves the anchored paths.
from . import config  # noqa: E402
from .config import GENERATED_DIR, STATIC_DIR, VIDEO_DIR, TTS_PREVIEW_DIR  # noqa: E402

logger = logging.getLogger(__name__)

# Environment self-healing + RAG init — same steps, same order, as the old
# import-time side effects in app.py.
from . import bootstrap  # noqa: E402
bootstrap.ensure_all()

from . import rag  # noqa: E402
rag._init_chroma()

# ── FastAPI app ───────────────────────────────────────────────────────────────
from fastapi import FastAPI  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402

# The workspace folders are created by config (lessonforge/paths.py).

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# The request gate (lessonforge/harness/gate.py): with LESSONFORGE_ACCESS_TOKEN set every
# request must carry it; LESSONFORGE_REVIEW_TOKEN is the weaker secret behind a student's
# review link; and each request tells the dashboard who came. Unset = localhost use.
from ..harness import gate as _gate  # noqa: E402
_gate.install(app, os.getenv("LESSONFORGE_ACCESS_TOKEN", ""), os.getenv("LESSONFORGE_REVIEW_TOKEN", ""),
              open_paths=("/health", "/healthz"))

# Rendered output lives in the workspace, the UI in the package. The two workspace
# mounts are registered FIRST: Starlette matches mounts in order, and /static would
# otherwise swallow /static/videos and look for the mp4 inside the installed package.
app.mount("/static/videos", StaticFiles(directory=VIDEO_DIR), name="videos")
app.mount("/static/tts_previews", StaticFiles(directory=TTS_PREVIEW_DIR), name="tts_previews")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# Bulk video generation (manifest-driven, resumable) — UI at /bulk.
from lessonforge.engine.bulk_runner import router as _bulk_router  # noqa: E402
app.include_router(_bulk_router)

# Feature routers, grouped by concern.
from .api import (pages, generation, render_routes, assets_routes, content, batch, voices,  # noqa: E402
                  tasks, models_routes)
for _mod in (pages, generation, render_routes, assets_routes, content, batch, voices, tasks,
             models_routes):
    app.include_router(_mod.router)

# Content harness: Socratic intake → framework → script → narrated, checked video.
# Its lessons are complete directories under the workspace, served read-only.
from ..harness.api import router as _harness_router  # noqa: E402
from .. import paths as _paths  # noqa: E402
app.include_router(_harness_router)
app.mount("/lessons", StaticFiles(directory=str(_paths.sub("lessons"))), name="lessons")
# The exported React Native Web client (clients/lessonforge-app → `npm run export:web`).
_WEB_APP = os.getenv("LESSONFORGE_WEB_APP", "")
if _WEB_APP and os.path.isdir(_WEB_APP):
    app.mount("/app", StaticFiles(directory=_WEB_APP, html=True), name="web_app")

# Merged finals gallery (served read-only for /timeline), if present.
if os.path.isdir(GENERATED_DIR):
    app.mount("/generated_videos", StaticFiles(directory=GENERATED_DIR), name="generated_videos")

# ── Public API re-exports (`from lessonforge.engine import X`) ───────────────
from .llm import *            # noqa: E402,F401,F403
from .codegen import *        # noqa: E402,F401,F403
from .storyboard import *     # noqa: E402,F401,F403
from .assets import *         # noqa: E402,F401,F403
from .render import *         # noqa: E402,F401,F403
from .jobs import *           # noqa: E402,F401,F403
from .codegen_pipeline import *  # noqa: E402,F401,F403
from .schemas import *        # noqa: E402,F401,F403
from .bootstrap import *      # noqa: E402,F401,F403

# Underscore-prefixed names that external callers / test harnesses rely on
# (import * does not re-export these).
from .render import (  # noqa: E402,F401
    _overlap_violations, _repair_overlaps, _render_scenes_parallel,
    _concat_scene_clips, _repair_scenes_parallel, _discard_video, _video_path,
    _inject_frame_assertion,
)
from .rag import _store_repair_pair, _retrieve_past_fixes  # noqa: E402,F401
from .jobs import _set_job, _get_job, _prune_jobs  # noqa: E402,F401
from .storyboard import (  # noqa: E402,F401
    _storyboard_cache_path, _storyboard_cache_read, _storyboard_cache_write,
)
