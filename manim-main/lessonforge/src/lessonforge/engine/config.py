"""Engine configuration: paths, render limits, env-override allowlist.

Bundled data (static UI, schemas, backgrounds, viz_helpers.py) is read from the
installed package; everything written at runtime goes under the workspace
(``LESSONFORGE_HOME``, default ``./lessonforge_workspace``) — see ``lessonforge/paths.py``.
All paths here are absolute, so the server no longer depends on its working directory."""
import os
import logging

from .. import paths

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

HOME_DIR = str(paths.home())
STATIC_DIR = str(paths.STATIC_DIR)

_ENV_OVERRIDE_ALLOWLIST = {
    "OVERLAP_REPAIR",
    "OVERLAP_REPAIR_ROUNDS",
    "LAYOUT_STRICT",
    "PARALLEL_RENDER",
    "PARALLEL_RENDER_WORKERS",
    "LAYOUT_REVIEW",
    # Agent stages (reference-architecture §7.3 / §18), default-off:
    "VISUAL_DIRECTOR",
    "VISION_QA",
    "VISION_QA_REPAIR",
    "VISION_QA_REPAIR_ROUNDS",
    "VISION_QA_FRAMES",
    # Visuals-only iteration: skip ALL speech synthesis (viz_helpers._tts_muted).
    # Cheap to flip per job because every TTS tier is a metered edge and layout
    # work re-renders the same board many times.
    "TTS_MUTE",
}


def _apply_env_overrides(overrides):
    if not overrides:
        return
    for key, value in overrides.items():
        if key not in _ENV_OVERRIDE_ALLOWLIST:
            logger.warning(f"Ignoring non-allowlisted env override: {key}")
            continue
        os.environ[key] = str(value)
        logger.info(f"Env override applied: {key}={value}")


RENDER_DIR = str(paths.sub("temp_renders"))


VIDEO_DIR = str(paths.sub("videos"))


TTS_PREVIEW_DIR = str(paths.sub("tts_previews"))


VIZ_HELPERS_SRC = str(paths.VIZ_HELPERS_SRC)


RENDER_TIMEOUT_SECONDS = int(os.getenv("RENDER_TIMEOUT_SECONDS", "600"))


GENERATED_DIR = str(paths.sub("generated_videos"))
