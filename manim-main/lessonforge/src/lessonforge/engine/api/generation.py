"""Routes: /api/generate_storyboard, /api/generate_code, /api/research."""
import logging
from fastapi import APIRouter, Depends, HTTPException

from lessonforge.engine.dependencies import APIKeys, resolve_api_keys
from ..llm import get_genai_client, describe_gemini_error
from ..storyboard import generate_storyboard_impl
from ..codegen_pipeline import generate_code_impl
from ..schemas import StoryboardRequest, CodegenRequest, ResearchRequest

logger = logging.getLogger(__name__)
router = APIRouter()


def merge_sources(context, sources):
    """Fold a request's top-level `sources` into the context dict the stages read.

    One channel, two spellings: `sources` is the discoverable request field, and
    `context["sources"]` is what `ce/` and the bulk runner already pass through their
    free-form context. Making them the same list here means the deep path never has
    to know which door the caller came in by."""
    if not sources:
        return context
    merged = dict(context or {})
    existing = list(merged.get("sources") or [])
    merged["sources"] = existing + list(sources)
    return merged


@router.post("/api/generate_storyboard")
def generate_storyboard(body: StoryboardRequest, keys: APIKeys = Depends(resolve_api_keys)):
    try:
        client = get_genai_client(keys)
        if not body.topic:
            raise HTTPException(status_code=400, detail="Topic is required")
        result = generate_storyboard_impl(
            client=client,
            topic=body.topic,
            persona=body.persona,
            language=body.language,
            style=body.style,
            context=merge_sources(body.context, body.sources),
            speaker=body.speaker,
            tts_provider=body.tts_provider,
            gemini_tts_model=body.gemini_tts_model,
            keys=keys,
            tech_terms=body.tech_terms,
            target_duration_s=body.target_duration_s,
        )
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to generate storyboard")
        msg, status = describe_gemini_error(e)
        raise HTTPException(status_code=status, detail=msg)


@router.post("/api/generate_code")
def generate_code(body: CodegenRequest, keys: APIKeys = Depends(resolve_api_keys)):
    try:
        client = get_genai_client(keys)
        if not body.storyboard:
            raise HTTPException(status_code=400, detail="Storyboard JSON is required")
        result = generate_code_impl(
            client=client,
            storyboard=body.storyboard,
            style=body.style,
            background=body.background,
            persona=body.persona,
            language=body.language,
            speaker=body.speaker,
            tts_provider=body.tts_provider,
            gemini_tts_model=body.gemini_tts_model,
            skip_layout_review=body.skip_layout_review,
            keys=keys,
        )
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to generate Manim code")
        msg, status = describe_gemini_error(e)
        raise HTTPException(status_code=status, detail=msg)


@router.post("/api/research")
def research(body: ResearchRequest):
    """Fetch and chunk source material WITHOUT generating anything.

    The point is that grounding is inspectable before it is paid for: the caller sees
    exactly which sources resolved, how much text each contributed, and what failed —
    a transcript that turned out to be disabled is worth knowing about before spending
    a storyboard, not after watching the video. Costs no LLM call."""
    from ..sources import ingest
    pack = ingest(body.sources, topic=body.topic, grade=body.grade, subject=body.subject,
                  auto_search=body.auto_search)
    manifest = pack.manifest()
    manifest["preview"] = pack.as_prompt(char_budget=2000)[:2000]
    return manifest
