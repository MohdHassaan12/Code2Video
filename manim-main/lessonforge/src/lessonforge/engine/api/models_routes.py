"""Model routing API — read and change which LLM each pipeline stage uses.

GET  /api/models         current provider order + per-task chains + catalogue
POST /api/models         apply a selection (validated; blocked reasoning models rejected)
POST /api/models/reset   back to the start-of-process (.env) configuration

Runtime selection is process-global (it writes the same env vars `.env` sets), the
same single-user affordance as the debug sandbox's `env_overrides`. Changes take
effect on the NEXT LLM call — nothing in flight is disturbed — and are lost on
restart; `.env` remains the durable configuration.
"""
import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from lessonforge.engine.dependencies import APIKeys, resolve_api_keys
from .. import model_routing

logger = logging.getLogger(__name__)
router = APIRouter()


class ModelSelection(BaseModel):
    # ["gemini", "openrouter", "groq"] — order is priority, later entries are failover.
    provider_order: list[str] | None = None
    # {task: {provider: [model, ...]}}; [] clears that chain back to its built-in default.
    chains: dict[str, dict[str, list[str]]] | None = None


@router.get("/api/models")
def get_models(keys: APIKeys = Depends(resolve_api_keys)):
    return model_routing.snapshot(keys)


@router.post("/api/models")
def set_models(selection: ModelSelection, keys: APIKeys = Depends(resolve_api_keys)):
    try:
        model_routing.apply_overrides(selection.provider_order, selection.chains)
    except ValueError as e:
        # A rejected payload changes nothing (validation runs before any assignment).
        raise HTTPException(status_code=400, detail=str(e))
    state = model_routing.snapshot(keys)
    logger.info("Model routing updated: order=%s, chains=%s",
                state["provider_order"],
                {t: {p: c["models"] for p, c in per.items() if c["overridden"]}
                 for t, per in state["chains"].items()})
    return state


@router.post("/api/models/reset")
def reset_models(keys: APIKeys = Depends(resolve_api_keys)):
    model_routing.reset_overrides()
    logger.info("Model routing reset to the .env configuration.")
    return model_routing.snapshot(keys)
