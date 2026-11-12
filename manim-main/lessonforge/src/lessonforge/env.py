"""Two small facts about the process environment that more than one entry point needs.

``PAID_KEYS`` names every environment variable that lets lessonforge spend money or quota. ``workbench.film`` hides
all of them for a free film, and tests blank all of them, from this one tuple so a new provider is added once.

``dotenv_disabled()`` is the opt-out for the ``.env`` loading that the engine package and the CLI do at start-up. The
default is unchanged (the file is loaded); a process that must not see the owner's keys, such as an improver run or a
test that is told to use only what it is given, sets ``LESSONFORGE_NO_DOTENV=1``.
"""
from __future__ import annotations

import os

#: Every key that can cost money or quota when present. Never print a value from these.
PAID_KEYS: tuple[str, ...] = (
    "OPENROUTER_API_KEY", "ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GEMINI_API_KEY", "GROQ_API_KEY", "SARVAM_AI_KEY",
    "INDIC_TTS_KEY", "TTS_HTTP_KEY", "TAVILY_API_KEY", "SERPER_API_KEY", "BRAVE_API_KEY", "YOUTUBE_API_KEY",
    "DIAGRAM_API_KEY",
)

NO_DOTENV = "LESSONFORGE_NO_DOTENV"


def dotenv_disabled() -> bool:
    """True when ``LESSONFORGE_NO_DOTENV`` is 1, true, yes or on: the caller must then skip ``load_dotenv()``."""
    return os.environ.get(NO_DOTENV, "").strip().lower() in ("1", "true", "yes", "on")
