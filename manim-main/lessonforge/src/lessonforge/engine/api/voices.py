"""Voice catalogue + TTS audition preview.

Single source of truth for the language/provider/speaker tables that the
front-ends previously hardcoded (static/app.js mirrored the sandbox's list by
hand — drift by construction). /api/tts/preview lets the Studio audition a cue
before spending a render; previews are cached on disk and served from the
static mount, so replaying a sample is free.
"""
import base64
import hashlib
import logging
import os
import re

import requests
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter()

from ..config import TTS_PREVIEW_DIR as PREVIEW_DIR  # noqa: E402

LANGUAGES = [
    {"code": "hi-IN", "label": "Hindi (hi-IN)"},
    {"code": "en-IN", "label": "English (en-IN)"},
    {"code": "bn-IN", "label": "Bengali (bn-IN)"},
    {"code": "ta-IN", "label": "Tamil (ta-IN)"},
    {"code": "te-IN", "label": "Telugu (te-IN)"},
    {"code": "kn-IN", "label": "Kannada (kn-IN)"},
    {"code": "ml-IN", "label": "Malayalam (ml-IN)"},
    {"code": "mr-IN", "label": "Marathi (mr-IN)"},
    {"code": "gu-IN", "label": "Gujarati (gu-IN)"},
    {"code": "pa-IN", "label": "Punjabi (pa-IN)"},
    {"code": "od-IN", "label": "Odia (od-IN)"},
]

SARVAM_SPEAKERS_BY_LANG = {
    "hi-IN": ["shubh", "ashutosh", "priya", "suhani"],
    "en-IN": ["ratan", "ishita"],
    "bn-IN": ["rehan", "roopa", "suhani"],
    "ta-IN": ["ratan", "rohan", "ishita", "ritu"],
    "te-IN": ["shubh", "ratan", "neha", "priya"],
    "kn-IN": ["shubh", "ratan", "neha", "ishita"],
    "ml-IN": ["shubh", "pooja"],
    "mr-IN": ["ratan", "priya", "ritu"],
    "gu-IN": ["ratan", "priya", "ritu"],
    "pa-IN": ["mani", "roopa", "suhani"],
    "od-IN": ["shubh", "ritu", "pooja"],
}

GEMINI_VOICES = [
    "Puck", "Charon", "Kore", "Fenrir", "Aoede",
    "Zephyr", "Lyra", "Orion", "Callisto", "Nova",
]

EDGE_VOICES_BY_LANG = {
    "hi-IN": ["hi-IN-SwaraNeural", "hi-IN-MadhurNeural"],
    "en-IN": ["en-IN-NeerjaNeural", "en-IN-PrabhatNeural", "en-IN-NeerjaExpressiveNeural"],
    "bn-IN": ["bn-IN-TanishaaNeural", "bn-IN-BashkarNeural"],
    "ta-IN": ["ta-IN-PallaviNeural", "ta-IN-ValluvarNeural"],
    "te-IN": ["te-IN-ShrutiNeural", "te-IN-MohanNeural"],
    "kn-IN": ["kn-IN-SapnaNeural", "kn-IN-GaganNeural"],
    "ml-IN": ["ml-IN-SobhanaNeural", "ml-IN-MidhunNeural"],
    "mr-IN": ["mr-IN-AarohiNeural", "mr-IN-ManoharNeural"],
    "gu-IN": ["gu-IN-DhwaniNeural", "gu-IN-NiranjanNeural"],
    "ur-IN": ["ur-IN-GulNeural", "ur-IN-SalmanNeural"],
}

LOCAL_VOICES_BY_LANG = {
    "hi-IN": ["hf_alpha", "hm_omega", "hf_beta", "hm_psi"],
    "en-IN": ["af_heart", "am_michael", "bf_emma", "bm_george"],
}

DEFAULT_GEMINI_TTS_MODEL = "google/gemini-3.1-flash-tts-preview"

# Narration pacing tags are never spoken (the render path strips them before
# synthesis) — the preview must strip them too or the voice reads them aloud.
_PACING_TAG_RE = re.compile(r"\[(?:SPEED|PAUSE)[^\]]*\]", re.IGNORECASE)


@router.get("/api/voices")
def voices():
    import importlib.util
    from ...longform.speech import KOKORO_USUAL_DIR

    has_edge = importlib.util.find_spec("edge_tts") is not None
    kokoro_m = os.getenv("KOKORO_MODEL") or os.path.join(KOKORO_USUAL_DIR, "kokoro-v1.0.onnx")
    kokoro_v = os.getenv("KOKORO_VOICES") or os.path.join(KOKORO_USUAL_DIR, "voices-v1.0.bin")
    has_local = os.path.exists(kokoro_m) and os.path.exists(kokoro_v)

    return {
        "languages": LANGUAGES,
        "sarvam_speakers_by_lang": SARVAM_SPEAKERS_BY_LANG,
        "gemini_voices": GEMINI_VOICES,
        "edge_voices_by_lang": EDGE_VOICES_BY_LANG,
        "local_voices_by_lang": LOCAL_VOICES_BY_LANG,
        "defaults": {"language": "hi-IN", "tts_provider": "sarvam", "speaker": "shubh"},
        # "Never configured" is expected routing, not degradation — surface it
        # so UIs can say "will fall back to Gemini" up front instead of
        # pretending Sarvam will speak.
        "providers_configured": {
            "sarvam": bool(os.environ.get("SARVAM_AI_KEY")),
            "gemini": bool(os.environ.get("OPENROUTER_API_KEY")),
            "edge": has_edge,
            "local": has_local,
        },
    }


class TTSPreviewRequest(BaseModel):
    text: str
    language: str = "hi-IN"
    tts_provider: str = "sarvam"
    speaker: str = "shubh"
    gemini_tts_model: str = DEFAULT_GEMINI_TTS_MODEL


@router.post("/api/tts/preview")
def tts_preview(req: TTSPreviewRequest):
    text = _PACING_TAG_RE.sub(" ", (req.text or "")).strip()
    text = re.sub(r"\s+", " ", text)[:400]
    if not text:
        raise HTTPException(status_code=400, detail="text is required")

    sarvam_key = os.environ.get("SARVAM_AI_KEY")
    openrouter_key = os.environ.get("OPENROUTER_API_KEY")

    provider = req.tts_provider
    note = None
    if provider == "sarvam" and not sarvam_key:
        provider = "gemini"
        note = "Sarvam is not configured on this server — previewed with Gemini TTS."
    if provider == "gemini" and not openrouter_key:
        raise HTTPException(
            status_code=503,
            detail="No TTS provider configured (need SARVAM_AI_KEY or OPENROUTER_API_KEY in the server env).",
        )
    if provider == "edge":
        import importlib.util
        if importlib.util.find_spec("edge_tts") is None:
            raise HTTPException(status_code=503, detail="edge-tts package is not installed.")
    if provider in ("local", "kokoro"):
        provider = "local"
        from ...longform.speech import KOKORO_USUAL_DIR
        kokoro_m = os.getenv("KOKORO_MODEL") or os.path.join(KOKORO_USUAL_DIR, "kokoro-v1.0.onnx")
        kokoro_v = os.getenv("KOKORO_VOICES") or os.path.join(KOKORO_USUAL_DIR, "voices-v1.0.bin")
        if not (os.path.exists(kokoro_m) and os.path.exists(kokoro_v)):
            raise HTTPException(status_code=503, detail="Kokoro model/voices not found on server.")

    voice = req.speaker
    if provider == "gemini" and voice not in GEMINI_VOICES:
        # Mirror viz_helpers: a non-Gemini name on the Gemini path becomes Puck.
        voice = "Puck"
    elif provider == "edge":
        if not voice or not re.fullmatch(r"[a-z]{2,3}-[A-Z]{2}-[A-Za-z]+Neural", voice):
            candidates = EDGE_VOICES_BY_LANG.get(req.language) or EDGE_VOICES_BY_LANG.get("hi-IN") or ["hi-IN-SwaraNeural"]
            voice = candidates[0]
    elif provider == "local":
        valid_local = [v for lst in LOCAL_VOICES_BY_LANG.values() for v in lst]
        if not voice or voice not in valid_local:
            candidates = LOCAL_VOICES_BY_LANG.get(req.language) or (
                LOCAL_VOICES_BY_LANG["en-IN"] if req.language.startswith("en") else LOCAL_VOICES_BY_LANG["hi-IN"]
            )
            voice = candidates[0]

    ext = ".mp3" if provider == "edge" else ".wav"
    key_material = f"{provider}|{req.language}|{voice}|{req.gemini_tts_model}|{text}"
    fname = hashlib.sha1(key_material.encode("utf-8")).hexdigest()[:24] + ext
    os.makedirs(PREVIEW_DIR, exist_ok=True)
    fpath = os.path.join(PREVIEW_DIR, fname)
    url = f"/static/tts_previews/{fname}"

    if os.path.exists(fpath) and os.path.getsize(fpath) > 0:
        return {"url": url, "cached": True, "provider_used": provider, "note": note}

    try:
        if provider == "sarvam":
            res = requests.post(
                "https://api.sarvam.ai/text-to-speech",
                json={
                    "text": text,
                    "target_language_code": req.language,
                    "speaker": voice,
                    "model": "bulbul:v3",
                },
                headers={"api-subscription-key": sarvam_key, "Content-Type": "application/json"},
                timeout=30,
            )
            if res.status_code != 200:
                raise HTTPException(status_code=502, detail=f"Sarvam TTS error {res.status_code}: {res.text[:200]}")
            audio_bytes = base64.b64decode(res.json()["audios"][0])
            if not audio_bytes:
                raise HTTPException(status_code=502, detail=f"{provider} TTS returned empty audio (provider outage?)")
            with open(fpath, "wb") as f:
                f.write(audio_bytes)
        elif provider == "gemini":
            # Metered like every other OpenRouter call (lessonforge.spend): refused past the cap, and written
            # to the ledger. Until 2026-10-22 this preview was the one OpenRouter call that never was.
            from lessonforge import spend
            try:
                spend.check(estimate=0.002, what="a voice preview")
            except spend.BudgetExceeded as exc:
                raise HTTPException(status_code=402, detail=str(exc))
            res = requests.post(
                "https://openrouter.ai/api/v1/audio/speech",
                json={"model": req.gemini_tts_model, "input": text, "voice": voice},
                headers={
                    "Authorization": f"Bearer {openrouter_key}",
                    "HTTP-Referer": "http://localhost",
                    "X-Title": "STEM Animation Lab",
                    "Content-Type": "application/json",
                },
                timeout=30,
            )
            if res.status_code != 200:
                raise HTTPException(status_code=502, detail=f"Gemini TTS error {res.status_code}: {res.text[:200]}")
            audio_bytes = res.content
            if not audio_bytes:
                raise HTTPException(status_code=502, detail=f"{provider} TTS returned empty audio (provider outage?)")
            gen_id = res.headers.get("X-Generation-Id")
            billed = spend.generation_cost(gen_id, tries=1) if gen_id else None
            words = len(text.split())
            # ~25 audio tokens a second at about 9 USD a million (longform.speech.GeminiBackend's figures).
            spend.record("tts", req.gemini_tts_model, billed["cost"] if billed else words / 2.4 * 25 * 9e-6,
                         generation_id=gen_id, note=f"voice preview, {words} words", estimated=not billed)
            with open(fpath, "wb") as f:
                f.write(audio_bytes)
        elif provider == "edge":
            from pathlib import Path
            from ...longform.speech import EdgeBackend
            backend = EdgeBackend(voice=voice, language=req.language)
            backend.synthesize(text, Path(fpath))
        elif provider == "local":
            from pathlib import Path
            from ...longform.speech import KokoroBackend
            backend = KokoroBackend(voice=voice)
            backend.synthesize(text, Path(fpath))
    except HTTPException:
        raise
    except Exception as e:  # network/JSON shape errors → clean 502, never a traceback
        logger.warning("TTS preview failed (%s): %s", provider, e)
        raise HTTPException(status_code=502, detail=f"TTS preview failed ({provider}): {e}")

    return {"url": url, "cached": False, "provider_used": provider, "note": note}
