"""Model routing table — which model chain each (provider, task) uses, plus the
runtime override surface behind ``/api/models``.

Split out of ``llm.py`` so it can be read and tested with NO heavy imports (no
genai, no fastapi, no app bootstrap) — ``test_model_routing.py`` loads this file
standalone. ``llm.py`` imports every name it used to define, so the chains have a
single source of truth.

Two layers, on purpose:

* **Defaults + env** (`.env` / process env) — the durable configuration. Chain
  order is priority; later entries are failover only.
* **Runtime overrides** (`apply_overrides`, driven by the UI panel) — process-global
  last-writer-wins, exactly like `config.ENV_OVERRIDE_ALLOWLIST`. A single-user
  affordance for "try another model without restarting the server"; don't build
  concurrent isolation on it. `reset_overrides()` restores the values captured at
  import time.

**Reasoning models are blocked here, in code, not by comment.** A model that spends
its completion budget on reasoning tokens returns ``finish_reason=length`` with no
content, gets discarded as truncated, and the chain walks model by model for minutes
— which reads as a flaky network error, not a config bug (measured 2026-08-01:
glm-5.2 burned 10727 reasoning tokens of 12000, kimi-k3 all 12000). The comment
warning about it lived in `.env` and did not stop anyone re-adding one, so the block
is now an invariant: blocked models are stripped from any chain, wherever it came
from, and rejected outright at the API.
"""
import contextlib
import os
import logging

logger = logging.getLogger(__name__)

# ── The chains ────────────────────────────────────────────────────────────────

PROVIDERS = ("gemini", "openrouter", "groq", "anthropic")

# "vision" is multimodal critique in pipeline/vision_qa.py.
TASKS = ("storyboard", "code", "general", "vision")

GEMINI_DEFAULT_MODELS = "gemini-2.5-flash,gemini-2.5-pro,gemini-2.0-flash"

# The defaults are the chains roadmap §5a chose and measured (2026-08-01). Until 2026-10-15 the code still held
# an older set: `deepseek/deepseek-v4-pro` first (it reasons on every call by default: twice all 16,000 tokens
# thinking on one scene and no code, and §5a keeps deepseek out of storyboards for its structured output) with two `:free`
# fallbacks that had gone from the catalogue, so each chain was one thinking model in practice.
# `scripts/check_models.py` checks every default chain against the live catalogue; run it before changing one.
OPENROUTER_DEFAULT_MODELS = (
    "google/gemini-2.5-flash,"                # general: transliteration, label translation
    "deepseek/deepseek-v4-flash,"             # thinking off (llm.THINKING_BY_MODEL); v3.2 kept thinking anyway
    "mistralai/mistral-small-3.2-24b-instruct"
)

OPENROUTER_STORYBOARD_MODELS = (
    "google/gemini-2.5-flash,"                # Gemini 2.5 Flash via OpenRouter — schema-native
    "openai/gpt-4.1,"                         # strong structured output, if Gemini quota is exhausted
    "qwen/qwen3-235b-a22b-2507"
)

# Measured with `scripts/eval_scenes.py` (8 frozen scene descriptions, each written, run and verified exactly as
# sim_gen does it; 2026-10-15). Verified scenes / first try / USD a scene / seconds a scene:
#   anthropic/claude-haiku-5.5, thinking off   8/8  8/8  0.0008  6     (thinking on: 8/8, 0.0022, 19)
#   deepseek/deepseek-v4-flash, thinking off   7/8  7/8  0.0003  22    (frames plainer: a dark grid, no jump arcs)
#   qwen/qwen3-coder-next                     12/16       0.0011  20-27
#   deepseek/deepseek-v4-pro (the old first)   5/8  4/8  0.0286  147   (two answers all thinking, no code)
#   google/gemini-2.5-flash 4/8, openai/gpt-5.4-nano 4/8, z-ai/glm-4.7-flash 4/8
# Thinking for this task is set in llm.THINKING_BY_TASK (Haiku thinks for the lesson writer, not here).
OPENROUTER_CODE_MODELS = (
    "anthropic/claude-haiku-5.5,"
    "deepseek/deepseek-v4-flash,"
    "qwen/qwen3-coder-next"
)

GROQ_DEFAULT_MODELS = "llama-3.3-70b-versatile,llama-3.1-8b-instant"

# Anthropic API model chains, routed by what a task costs to get wrong (current IDs, checked 2026-11-10; the API
# takes these exact strings, no date suffix). Prices are USD per million tokens, input / output:
# - General and small calls (transliteration, label translation, edits): Haiku 5.5, 0.10 / 0.50 - the cheap tier.
# - Vision QA: Haiku 5.5 reads the frames (the rubric is a bounded checklist); Sonnet 5.5 only if Haiku fails.
# - Code (scene scripts, repairs): Sonnet 5.5, 2 / 10, then Haiku 5.5 as failover.
# - Storyboard (the plan every later stage depends on): Opus 5.5, 4 / 20, then Sonnet 5.5 as failover.
# The 3.x ids that were here before (claude-3-5-sonnet-20241022, claude-3-haiku-20240307, ...) are retired.
ANTHROPIC_DEFAULT_MODELS = "claude-haiku-5-5,claude-sonnet-5-5"
ANTHROPIC_STORYBOARD_MODELS = "claude-opus-5-5,claude-sonnet-5-5"
ANTHROPIC_CODE_MODELS = "claude-sonnet-5-5,claude-haiku-5-5"
ANTHROPIC_VISION_MODELS = "claude-haiku-5-5,claude-sonnet-5-5"

# Vision QA model chain (multimodal). Cheap tier on purpose: the rubric is a
# bounded checklist, not open-ended reasoning (metered-edge routing, CLAUDE.md).
VISION_QA_DEFAULT_MODELS = "google/gemini-2.5-flash,google/gemini-2.5-flash-lite"

_GENERAL_DEFAULTS = {"gemini": GEMINI_DEFAULT_MODELS,
                     "openrouter": OPENROUTER_DEFAULT_MODELS,
                     "groq": GROQ_DEFAULT_MODELS,
                     "anthropic": ANTHROPIC_DEFAULT_MODELS}

_CODE_DEFAULTS = {"gemini": GEMINI_DEFAULT_MODELS,
                  "openrouter": OPENROUTER_CODE_MODELS,
                  "groq": GROQ_DEFAULT_MODELS,
                  "anthropic": ANTHROPIC_CODE_MODELS}

_STORYBOARD_DEFAULTS = {"gemini": GEMINI_DEFAULT_MODELS,
                        "openrouter": OPENROUTER_STORYBOARD_MODELS,
                        "groq": GROQ_DEFAULT_MODELS,
                        "anthropic": ANTHROPIC_STORYBOARD_MODELS}

_VISION_DEFAULTS = {"openrouter": VISION_QA_DEFAULT_MODELS,
                    "anthropic": ANTHROPIC_VISION_MODELS}

_TASK_DEFAULTS = {"general": _GENERAL_DEFAULTS, "code": _CODE_DEFAULTS,
                  "storyboard": _STORYBOARD_DEFAULTS, "vision": _VISION_DEFAULTS}

# (provider, task) -> the env var that overrides that chain. A pair missing from
# this table has no env lever and falls back to its provider's general chain.
MODEL_ENV = {
    ("gemini", "general"): "GEMINI_MODELS", ("gemini", "code"): "GEMINI_CODE_MODELS",
    ("gemini", "storyboard"): "GEMINI_STORYBOARD_MODELS",
    ("openrouter", "general"): "OPENROUTER_MODELS", ("openrouter", "code"): "OPENROUTER_CODE_MODELS",
    ("openrouter", "storyboard"): "OPENROUTER_STORYBOARD_MODELS",
    ("openrouter", "vision"): "VISION_QA_MODELS",
    ("groq", "general"): "GROQ_MODELS", ("groq", "code"): "GROQ_CODE_MODELS",
    ("groq", "storyboard"): "GROQ_STORYBOARD_MODELS",
    ("anthropic", "general"): "ANTHROPIC_MODELS", ("anthropic", "code"): "ANTHROPIC_CODE_MODELS",
    ("anthropic", "storyboard"): "ANTHROPIC_STORYBOARD_MODELS",
    ("anthropic", "vision"): "ANTHROPIC_VISION_MODELS",
}

PROVIDER_ORDER_ENV = "LLM_PROVIDER_ORDER"

# Gemini FIRST by default (2026-08-02): OpenRouter is pay-as-you-go and answers an
# uncapped storyboard request with HTTP 402 ("requires more credits ... you requested
# up to 65535 tokens") as soon as the balance dips below the estimated worst-case
# cost — every model in the chain, so the whole stage dies. The Gemini key is a
# free-tier key on a separate quota, so it keeps working when credits run out.
LLM_PROVIDER_ORDER_DEFAULT = "gemini,openrouter,groq,anthropic"


# ── Reasoning-model block (see module docstring) ──────────────────────────────

# Matched case-insensitively as substrings of the model id, so a vendor prefix or a
# ":free"/":nitro" suffix can't sneak one past. Add a model here the moment it is
# measured burning its completion budget on reasoning.
BLOCKED_MODEL_MARKERS = (
    "kimi-k3",          # moonshotai/kimi-k3 — 12000 of 12000 tokens on reasoning
    "glm-5.2",          # z-ai/glm-5.2 — 10727 of 12000
    "deepseek-r1",      # reasoning by construction
    "qwq",
    "thinking",         # any *-thinking / :thinking variant
    "-sol",             # openai/gpt-5.6-sol — reasoning default_enabled
)


def blocked_reason(model):
    """Return the marker that blocks `model`, or None if it is allowed."""
    low = (model or "").lower()
    for marker in BLOCKED_MODEL_MARKERS:
        if marker in low:
            return marker
    return None


def catalogue_problems(model, entry, switched_off=False):
    """What is wrong with `model` for a chain, judged from its OpenRouter catalogue `entry` (None = not listed).

    Returns ``(kind, why)`` pairs; ``kind`` is ``"dead"`` (the id no longer exists: a chain silently loses that
    fallback, as ``openai/gpt-oss-120b:free`` did twice) or ``"thinks"`` (it reasons on a call nobody told
    otherwise: the 2026-08-01 failure). ``switched_off`` says the caller does tell it (``llm.THINKING_BY_MODEL``);
    a model whose reasoning is mandatory thinks whatever it is told. The catalogue's ``default_enabled`` alone
    is not enough: ``deepseek/deepseek-v4-flash`` has none, lists only "xhigh" and "high", and spent 15,702 of
    16,000 tokens thinking on one scene (2026-10-15). ``scripts/check_models.py`` runs this over every default
    chain against the live catalogue; this function stays pure for the tests.
    """
    if entry is None:
        return [("dead", "not in the OpenRouter catalogue")]
    reasoning = entry.get("reasoning") or {}
    efforts = [str(e) for e in reasoning.get("supported_efforts") or ()]
    if reasoning.get("mandatory"):
        return [("thinks", f"reasoning is mandatory (default effort {reasoning.get('default_effort') or '?'})")]
    if switched_off or reasoning.get("default_enabled") is False:
        return []
    if reasoning.get("default_enabled") or efforts:
        return [("thinks", f"reasons by default (efforts: {', '.join(efforts) or 'not listed'})")]
    return []


def _strip_blocked(models, where):
    kept = []
    for m in models:
        marker = blocked_reason(m)
        if marker:
            logger.warning(
                "MODEL_BLOCKED: dropping %r from %s — matches %r (reasoning model: spends the "
                "completion budget thinking, returns finish_reason=length with no content).",
                m, where, marker)
            continue
        kept.append(m)
    return kept


# ── Resolution ────────────────────────────────────────────────────────────────

def parse_models(csv):
    return [m.strip() for m in (csv or "").split(",") if m.strip()]


def default_models(provider, task):
    """The built-in chain for (provider, task), ignoring env/overrides."""
    base = _TASK_DEFAULTS.get(task, _GENERAL_DEFAULTS)
    return parse_models(base.get(provider) or _GENERAL_DEFAULTS.get(provider, ""))


def resolve_models(provider, task):
    """Pick the model chain for a provider/task: env override, else per-task default.

    Blocked (reasoning) models are stripped wherever they came from. If stripping
    empties an env-supplied chain, the built-in default is used instead — a chain of
    zero models would make the provider silently unusable.
    """
    env_var = MODEL_ENV.get((provider, task))
    val = os.getenv(env_var) if env_var else None
    if val:
        models = _strip_blocked(parse_models(val), env_var)
        if models:
            return models
        logger.warning("%s named only blocked models; falling back to the built-in chain.", env_var)
    return _strip_blocked(default_models(provider, task), f"{provider}/{task} default")


# The code task (generated scenes, drawings, icons, repairs) asks OpenRouter first when nobody chose an order
# (2026-10-15). Gemini-first exists because OpenRouter answers an UNCAPPED storyboard request with 402 when the
# balance is low; a code call is capped (LLM_MAX_TOKENS), so that reason does not apply, and Gemini 2.5 Flash
# verified 4 of 8 scenes where the OpenRouter chain's first model verified 8 of 8 (scripts/eval_scenes.py).
# A provider with no key is skipped as before. `LLM_PROVIDER_ORDER_CODE` sets it; an `LLM_PROVIDER_ORDER` set in
# the environment or the Model routing panel still decides for every task when the code order is not set.
CODE_PROVIDER_ORDER_ENV = "LLM_PROVIDER_ORDER_CODE"
CODE_PROVIDER_ORDER_DEFAULT = "openrouter,gemini,groq,anthropic"


def _parse_order(raw):
    return [p.strip().lower() for p in (raw or "").split(",") if p.strip()]


def provider_order(task=None):
    if task == "code":
        raw = os.getenv(CODE_PROVIDER_ORDER_ENV) or os.getenv(PROVIDER_ORDER_ENV) or CODE_PROVIDER_ORDER_DEFAULT
    else:
        raw = os.getenv(PROVIDER_ORDER_ENV, LLM_PROVIDER_ORDER_DEFAULT)
    return _parse_order(raw) or list(PROVIDERS)


# ── Runtime overrides (the /api/models write path) ────────────────────────────

# Env values as they were when the process started, so a reset is exact (including
# "this var was not set at all").
_BASELINE = {}
for _var in list(MODEL_ENV.values()) + [PROVIDER_ORDER_ENV, CODE_PROVIDER_ORDER_ENV]:
    _BASELINE[_var] = os.environ.get(_var)

_OVERRIDDEN = set()


def _set_env(var, value):
    if value is None:
        os.environ.pop(var, None)
    else:
        os.environ[var] = value
    if value == _BASELINE.get(var):
        _OVERRIDDEN.discard(var)
    else:
        _OVERRIDDEN.add(var)


def apply_overrides(provider_order_list=None, chains=None):
    """Apply a UI/API model selection to the process environment.

    `provider_order_list`: list of provider names (subset of PROVIDERS, non-empty).
    `chains`: {task: {provider: [model, ...]}} — only pairs present in MODEL_ENV are
    settable; an empty list clears that override back to the built-in default.

    Raises ValueError with a user-facing message on anything invalid (unknown
    provider/task, blocked reasoning model, empty order). Validation happens for the
    WHOLE payload before any of it is applied, so a rejected request changes nothing.
    """
    to_set = {}

    if provider_order_list is not None:
        order = [str(p).strip().lower() for p in provider_order_list if str(p).strip()]
        if not order:
            raise ValueError("Provider order cannot be empty — pick at least one provider.")
        unknown = [p for p in order if p not in PROVIDERS]
        if unknown:
            raise ValueError(f"Unknown provider(s): {', '.join(unknown)}. "
                             f"Valid: {', '.join(PROVIDERS)}.")
        if len(set(order)) != len(order):
            raise ValueError("Provider order lists a provider twice.")
        to_set[PROVIDER_ORDER_ENV] = ",".join(order)

    for task, per_provider in (chains or {}).items():
        if task not in TASKS:
            raise ValueError(f"Unknown task {task!r}. Valid: {', '.join(TASKS)}.")
        for provider, models in (per_provider or {}).items():
            if provider not in PROVIDERS:
                raise ValueError(f"Unknown provider {provider!r}. Valid: {', '.join(PROVIDERS)}.")
            env_var = MODEL_ENV.get((provider, task))
            if not env_var:
                raise ValueError(f"{provider} has no separate chain for the {task} task "
                                 f"(it uses its general chain).")
            if isinstance(models, str):
                models = parse_models(models)
            models = [str(m).strip() for m in (models or []) if str(m).strip()]
            for m in models:
                marker = blocked_reason(m)
                if marker:
                    raise ValueError(
                        f"{m} is blocked: it is a reasoning model (matched {marker!r}). Reasoning "
                        f"models spend the whole completion budget thinking and return no content, "
                        f"so the chain stalls for minutes and fails intermittently.")
            to_set[env_var] = ",".join(models) if models else None

    for var, value in to_set.items():
        _set_env(var, value)
    return snapshot()


@contextlib.contextmanager
def scoped_routing(provider, model, task):
    """Route ONE job to `provider` (and `model` for `task`, if a model is named) and put everything back after.

    The Studio picker used to write into the process environment for good, so one run's choice leaked into every
    later run and the failure to apply it was only logged. Here an invalid choice (unknown provider, a blocked
    reasoning model) raises ``ValueError`` with a user-facing message, the choice holds for the ``with`` block
    only, and what was set before (env or the Model routing panel) comes back in ``finally``. "auto" or no
    provider changes nothing. The provider is moved to the front of both the general and the code order, so its
    cheap vision and small-call chains are used too; a named model replaces only the chain of `task`.
    Still process-global (see the module docstring): two jobs started together with different choices share it.
    """
    if not provider or provider == "auto":
        yield
        return
    provider = str(provider).strip().lower()
    if provider not in PROVIDERS:
        raise ValueError(f"Unknown provider {provider!r}. Valid: {', '.join(PROVIDERS)}.")
    watched = list(MODEL_ENV.values()) + [PROVIDER_ORDER_ENV, CODE_PROVIDER_ORDER_ENV]
    saved_env = {var: os.environ.get(var) for var in watched}
    saved_overridden = set(_OVERRIDDEN)
    try:
        chains = None
        if model and model != "auto":
            chains = {task: {provider: [model]}}
        general = [provider] + [p for p in provider_order() if p != provider]
        apply_overrides(provider_order_list=general, chains=chains)
        code = [provider] + [p for p in provider_order("code") if p != provider]
        _set_env(CODE_PROVIDER_ORDER_ENV, ",".join(code))
        yield
    finally:
        for var, value in saved_env.items():
            if value is None:
                os.environ.pop(var, None)
            else:
                os.environ[var] = value
        _OVERRIDDEN.clear()
        _OVERRIDDEN.update(saved_overridden)


def reset_overrides():
    """Restore every routing var to its start-of-process value."""
    for var, value in _BASELINE.items():
        if value is None:
            os.environ.pop(var, None)
        else:
            os.environ[var] = value
    _OVERRIDDEN.clear()
    return snapshot()


def snapshot(keys=None):
    """The full routing state, for GET /api/models and for logging.

    `keys` (an APIKeys-like object with .gemini/.openrouter/.groq) marks which
    providers are actually usable; without it the env is consulted.
    """
    def _available(provider):
        if keys is not None:
            return bool(getattr(keys, provider, None))
        return bool(os.getenv({"gemini": "GEMINI_API_KEY",
                               "openrouter": "OPENROUTER_API_KEY",
                               "groq": "GROQ_API_KEY",
                               "anthropic": "ANTHROPIC_API_KEY"}[provider]))

    chains = {}
    for task in TASKS:
        per_provider = {}
        for provider in PROVIDERS:
            env_var = MODEL_ENV.get((provider, task))
            if not env_var:
                continue
            per_provider[provider] = {
                "models": resolve_models(provider, task),
                "default": default_models(provider, task),
                "env_var": env_var,
                "overridden": env_var in _OVERRIDDEN,
                "source": ("runtime" if env_var in _OVERRIDDEN
                           else "env" if os.getenv(env_var) else "default"),
            }
        chains[task] = per_provider

    return {
        "provider_order": provider_order(),
        "provider_order_default": parse_models(LLM_PROVIDER_ORDER_DEFAULT),
        "provider_order_overridden": PROVIDER_ORDER_ENV in _OVERRIDDEN,
        "providers": {p: {"available": _available(p)} for p in PROVIDERS},
        "tasks": list(TASKS),
        "chains": chains,
        "catalogue": CATALOGUE,
        "blocked_markers": list(BLOCKED_MODEL_MARKERS),
        "max_tokens": {
            "global": os.getenv("LLM_MAX_TOKENS", "16000"),
            "storyboard": os.getenv("LLM_MAX_TOKENS_STORYBOARD", "") or "uncapped",
        },
    }


# ── Suggested models for the picker ───────────────────────────────────────────
# Not a hard allowlist — the UI lets you type any id — just what we have actually
# run here. Every entry is reasoning-OFF by default (checked against OpenRouter
# /api/v1/models: .reasoning.mandatory false, .reasoning.default_enabled absent).
CATALOGUE = {
    "gemini": [
        {"id": "gemini-2.5-flash", "note": "fast, schema-native — default"},
        {"id": "gemini-2.5-pro", "note": "strongest, slower"},
        {"id": "gemini-2.0-flash", "note": "cheap failover"},
        {"id": "gemini-2.5-flash-lite", "note": "cheapest"},
    ],
    "openrouter": [
        {"id": "google/gemini-2.5-flash", "note": "schema-native, good storyboards"},
        {"id": "openai/gpt-4.1", "note": "strong structured output"},
        {"id": "anthropic/claude-haiku-5.5", "note": "Claude Haiku 5.5 via OpenRouter"},
        {"id": "deepseek/deepseek-v3.2", "note": "cheap codegen"},
        {"id": "qwen/qwen3-coder", "note": "codegen"},
        {"id": "qwen/qwen3-235b-a22b-2507", "note": "general/storyboard failover"},
        {"id": "mistralai/mistral-small-3.2-24b-instruct", "note": "cheap general"},
        {"id": "google/gemini-2.5-flash-lite", "note": "cheapest, takes images"},
    ],
    "groq": [
        {"id": "llama-3.3-70b-versatile", "note": "fast failover"},
        {"id": "llama-3.1-8b-instant", "note": "fastest, weakest"},
    ],
    "anthropic": [
        {"id": "claude-opus-5-5", "note": "costliest, best plans: storyboard (4 / 20 per MTok)"},
        {"id": "claude-sonnet-5-5", "note": "scene code and repairs (2 / 10 per MTok)"},
        {"id": "claude-haiku-5-5", "note": "cheapest: small calls and vision checks (0.10 / 0.50 per MTok)"},
        {"id": "claude-fable-5-1", "note": "most capable, 10 / 50 per MTok - pick by hand only"},
    ],
}
