"""
FastAPI dependency for API key resolution.

Replaces all Flask-specific patterns in app.py:
  - has_request_context()
  - request.headers.get(...)
  - get_genai_client()       →  make_genai_client(keys)
  - _header_or_env()         →  deleted
  - _openrouter_key()        →  keys.openrouter
  - _groq_key()              →  keys.groq
  - call_llm_with_fallback() →  accepts keys: APIKeys

Two entry points:
  - resolve_api_keys  — FastAPI Depends() for route handlers (reads headers + env)
  - env_api_keys()    — plain function for background threads (reads env only)
"""
from __future__ import annotations

import logging
import os

from fastapi import Header
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class APIKeys(BaseModel):
    """Resolved API keys for all LLM providers.

    Frozen so a keys instance can be passed around safely across threads without
    accidental mutation. Background threads use env_api_keys(); routes use
    Depends(resolve_api_keys) which also reads request headers.
    """
    gemini: str | None = None
    openrouter: str | None = None
    groq: str | None = None
    anthropic: str | None = None

    model_config = {"frozen": True}

    def any_available(self) -> bool:
        return bool(self.gemini or self.openrouter or self.groq or self.anthropic)


# ---------------------------------------------------------------------------
# FastAPI dependency — inject into route handlers with Depends(resolve_api_keys)
# ---------------------------------------------------------------------------

def resolve_api_keys(
    x_gemini_api_key: str | None = Header(default=None),
    authorization: str | None = Header(default=None),
    x_openrouter_api_key: str | None = Header(default=None),
    x_groq_api_key: str | None = Header(default=None),
    x_anthropic_api_key: str | None = Header(default=None),
) -> APIKeys:
    """Read API keys from request headers first, then fall back to env vars.

    Header priority lets the debug sandbox UI pass a user-supplied key without
    needing it in the server's environment — same behaviour as the old Flask
    has_request_context() pattern.

    Header names (case-insensitive in HTTP, FastAPI normalises them):
      X-Gemini-API-Key      or  Authorization: Bearer <key>
      X-OpenRouter-API-Key
      X-Groq-API-Key
      X-Anthropic-API-Key
    """
    # --- Gemini ---
    gemini = x_gemini_api_key
    if not gemini and authorization:
        # Accept "Bearer sk-xxx" or bare key
        bearer = authorization.strip()
        if bearer.startswith("Bearer "):
            bearer = bearer[len("Bearer "):]
        gemini = bearer.strip() or None
    gemini = (gemini or os.getenv("GEMINI_API_KEY") or "").strip() or None

    # --- OpenRouter ---
    openrouter = (
        x_openrouter_api_key or os.getenv("OPENROUTER_API_KEY") or ""
    ).strip() or None

    # --- Groq ---
    groq = (x_groq_api_key or os.getenv("GROQ_API_KEY") or "").strip() or None

    # --- Anthropic ---
    anthropic = (x_anthropic_api_key or os.getenv("ANTHROPIC_API_KEY") or "").strip() or None

    keys = APIKeys(gemini=gemini, openrouter=openrouter, groq=groq, anthropic=anthropic)
    logger.debug(
        "resolve_api_keys: gemini=%s openrouter=%s groq=%s anthropic=%s",
        "set" if keys.gemini else "none",
        "set" if keys.openrouter else "none",
        "set" if keys.groq else "none",
        "set" if keys.anthropic else "none",
    )
    return keys


# ---------------------------------------------------------------------------
# Env-only resolver — for background threads (no request context)
# ---------------------------------------------------------------------------

def env_api_keys() -> APIKeys:
    """Resolve keys from environment only.

    Call this inside ThreadPoolExecutor workers or any code that runs outside
    a FastAPI request handler (e.g. _run_render_job, repair_code_with_gemini
    called from the render thread).
    """
    return APIKeys(
        gemini=(os.getenv("GEMINI_API_KEY") or "").strip() or None,
        openrouter=(os.getenv("OPENROUTER_API_KEY") or "").strip() or None,
        groq=(os.getenv("GROQ_API_KEY") or "").strip() or None,
        anthropic=(os.getenv("ANTHROPIC_API_KEY") or "").strip() or None,
    )


# ---------------------------------------------------------------------------
# Gemini client factory — replaces get_genai_client()
# ---------------------------------------------------------------------------

def make_genai_client(keys: APIKeys):
    """Build a google.genai.Client from resolved keys.

    Returns None (not a crash) when no Gemini key is available — the LLM
    fallback chain in call_llm_with_fallback will skip Gemini and try
    OpenRouter/Groq instead.
    """
    if not keys.gemini:
        return None
    try:
        from google import genai
        return genai.Client(api_key=keys.gemini)
    except Exception as e:
        logger.warning("Failed to build Gemini client: %s", e)
        return None
