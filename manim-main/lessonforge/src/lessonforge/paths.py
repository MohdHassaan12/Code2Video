"""Filesystem layout: bundled (read-only) package data vs. the runtime workspace.

Everything lessonforge WRITES lives under one workspace directory, so an installed
package never writes into site-packages and two checkouts never share scratch state:

    $LESSONFORGE_HOME                 (default: ./lessonforge_workspace)
      temp_renders/                   scene scripts, per-job media dirs, staged viz_helpers.py
      videos/                         rendered mp4s + .mp4.json sidecars  (served at /static/videos)
      tts_previews/                   Studio voice auditions              (served at /static/tts_previews)
      generated_videos/               merged finals
      lessons/                        long-form lesson builds (audio, timeline, chapters, output)
      bulk_runs/                      bulk-generation run state
      chroma_db/                      optional RAG store (CHROMADB_ENABLED=1)
      logs/
      cache/storyboard/               content-addressed storyboards
      cache/tts/  cache/voiceover/    speech caches (a cache-key change is a billing change)
      cache/assets/{generated,simulation,drawing,wikimedia}/
      cache/manim_api_index.json

The render dir keeps the literal name ``temp_renders``: the staged ``viz_helpers.py``
copy recognises where it is running by that basename.

The resolved home is exported back into ``os.environ`` so the manim subprocesses (which
import the staged ``viz_helpers.py``, not this package) agree with the parent process
no matter what their working directory is.
"""
from __future__ import annotations

import os
from pathlib import Path

PKG_DIR = Path(__file__).resolve().parent
STATIC_DIR = PKG_DIR / "web" / "static"
SCHEMA_DIR = PKG_DIR / "schemas"
BACKGROUNDS_DIR = PKG_DIR / "assets" / "backgrounds"
VIZ_HELPERS_SRC = PKG_DIR / "viz_helpers.py"

ENV_HOME = "LESSONFORGE_HOME"
ENV_PKG = "LESSONFORGE_PKG_DIR"
DEFAULT_HOME_NAME = "lessonforge_workspace"


def home() -> Path:
    """The workspace root (absolute). Resolved once per process, then pinned in the env."""
    raw = os.environ.get(ENV_HOME, "").strip()
    root = Path(raw).expanduser() if raw else Path.cwd() / DEFAULT_HOME_NAME
    root = root.resolve()
    os.environ[ENV_HOME] = str(root)
    os.environ[ENV_PKG] = str(PKG_DIR)
    return root


def sub(*parts: str, create: bool = True) -> Path:
    """A directory under the workspace, created on first use."""
    p = home().joinpath(*parts)
    if create:
        p.mkdir(parents=True, exist_ok=True)
    return p


def cache(*parts: str, create: bool = True) -> Path:
    return sub("cache", *parts, create=create)
