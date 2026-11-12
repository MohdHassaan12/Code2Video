"""LLM edge: provider routing (Gemini -> OpenRouter -> Groq), per-task model chains,
and the JSON helpers. These functions are the metered edges and the debug_sandbox call
seams; kept as module functions, not classes."""
import os
import re
import json
import time
import logging

from google import genai
from google.genai import types
from lessonforge.engine.dependencies import make_genai_client as _make_genai_client

logger = logging.getLogger(__name__)

def get_genai_client(keys=None):
    if keys is not None:
        return _make_genai_client(keys)
    # Fallback: environment variable (for callers that don't pass keys)
    api_key = os.getenv("GEMINI_API_KEY")
    if api_key:
        try:
            return genai.Client(api_key=api_key)
        except Exception as e:
            logger.warning(f"Failed to configure Gemini client with provided API key: {e}")
            return None
    return None


def call_gemini_with_fallback(client, prompt, system_instruction, response_schema=None, temperature=0.2, models=None):
    # Caller may pass an explicit model chain (e.g. a code-tuned one); otherwise use the
    # GEMINI_MODELS default. The retired 1.5 series 404s, so it's excluded.
    if models is None:
        models = _resolve_models("gemini", "general")
    last_error = None
    
    for model in models:
        max_retries = 3
        for attempt in range(max_retries):
            try:
                logger.info(f"Attempting Gemini call with model: {model} (Attempt {attempt+1}/{max_retries})")
                config_args = {"temperature": temperature}
                if system_instruction:
                    config_args["system_instruction"] = system_instruction
                if response_schema:
                    config_args["response_mime_type"] = "application/json"
                    config_args["response_schema"] = response_schema
                    
                response = client.models.generate_content(
                    model=model,
                    contents=prompt,
                    config=types.GenerateContentConfig(**config_args)
                )
                logger.info(f"Gemini call succeeded with model: {model}")
                return response
            except Exception as e:
                err_str = str(e)
                # 503/UNAVAILABLE = temporary overload, worth a quick retry. 429/RESOURCE_EXHAUSTED
                # = quota exhaustion; a same-model retry seconds later won't help (the API asks for
                # 15-30s waits), so fail over to the next model immediately instead of burning time.
                is_transient = "503" in err_str or "UNAVAILABLE" in err_str
                
                if is_transient and attempt < max_retries - 1:
                    sleep_time = (attempt + 1) * 2
                    logger.warning(f"Model {model} failed with transient error: {e}. Retrying in {sleep_time}s...")
                    time.sleep(sleep_time)
                    continue
                else:
                    logger.warning(f"Model {model} failed: {e}")
                    last_error = e
                    break # Go to next model in list
            
    raise last_error if last_error else Exception("All Gemini models failed to generate content.")


def describe_gemini_error(e):
    """Map a Gemini/genai exception to a (user_message, http_status) pair.

    Turns the provider's wall-of-JSON into a short, actionable message and a sensible
    HTTP status instead of an opaque 500.
    """
    s = str(e)
    if "RESOURCE_EXHAUSTED" in s or "429" in s:
        return (
            "All configured LLM providers are quota/rate-limited (429). Gemini's free tier resets "
            "~midnight Pacific; OpenRouter/Groq free models are rate-limited upstream. Wait a moment "
            "and retry, enable billing, or add another key (GEMINI / OPENROUTER / GROQ).",
            429,
        )
    if "503" in s or "UNAVAILABLE" in s or "overloaded" in s.lower():
        return ("Gemini models are temporarily overloaded (503). Please try again in a minute.", 503)
    if "PERMISSION_DENIED" in s or "API key not valid" in s or "401" in s or "403" in s:
        return ("Gemini rejected the API key. Check GEMINI_API_KEY (or the key in the UI panel).", 401)
    return (s, 500)


OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

# The chains themselves live in model_routing (no heavy imports, so the routing table
# is readable by the API layer and testable standalone). Re-exported here because
# every caller in the tree — and the debug sandbox — reaches for them via app.llm.
from .model_routing import (  # noqa: E402
    GEMINI_DEFAULT_MODELS,
    OPENROUTER_DEFAULT_MODELS,
    OPENROUTER_STORYBOARD_MODELS,
    GROQ_DEFAULT_MODELS,
    VISION_QA_DEFAULT_MODELS,
    LLM_PROVIDER_ORDER_DEFAULT,
    MODEL_ENV as _MODEL_ENV,
    parse_models as _parse_models,
    resolve_models as _resolve_models,
    provider_order as _provider_order,
)


def _header_or_env(header_name, env_name):
    """Read a credential from the environment (legacy fallback when no keys object is passed)."""
    env_val = os.getenv(env_name)
    return env_val.strip() if env_val else None


def _openrouter_key(keys=None):
    if keys is not None:
        return keys.openrouter
    key = _header_or_env("X-OpenRouter-API-Key", "OPENROUTER_API_KEY")
    logger.info("_openrouter_key retrieved: %s", "set" if key else "missing")  # never log the secret
    return key


def _groq_key(keys=None):
    if keys is not None:
        return keys.groq
    return _header_or_env("X-Groq-API-Key", "GROQ_API_KEY")


def _anthropic_key(keys=None):
    if keys is not None:
        return keys.anthropic
    return _header_or_env("X-Anthropic-API-Key", "ANTHROPIC_API_KEY")


def llm_available(gemini_client, keys=None):
    """True if at least one provider (Gemini client, OpenRouter, Groq, or Anthropic key) is usable."""
    return (gemini_client is not None or _openrouter_key(keys) is not None or
            _groq_key(keys) is not None or _anthropic_key(keys) is not None)


class LLMResponse:
    """Minimal stand-in exposing `.text`, matching how callers use the genai response."""
    __slots__ = ("text",)

    def __init__(self, text):
        self.text = text


# Sentinel: "resolve the cap from LLM_MAX_TOKENS at call time" — distinct from None,
# which means UNCAPPED (omit max_tokens; the provider allows up to the model's own
# output window).
_ENV_CAP = object()


def _max_tokens_for_task(task):
    """Output-token cap for `task`, or None for uncapped.

    Storyboard is UNCAPPED by default (2026-07-31, user decision): a request-level
    token ceiling on the storyboard is also a ceiling on VIDEO LENGTH (~1.1k tokens
    per scene, so 12-16k caps a board at ~10-13 scenes), while the finish_reason
    gate below still rejects anything the MODEL itself truncates — so the cap bought
    no extra safety, only a shorter maximum video. The global LLM_MAX_TOKENS
    therefore deliberately does NOT apply to the storyboard task; restore a
    storyboard cap explicitly with LLM_MAX_TOKENS_STORYBOARD=<n> (0 = uncapped).
    Every other task keeps LLM_MAX_TOKENS (default 16000) — codegen/repair output
    is code whose healthy size is known, so a runaway there is a bug, not content.
    """
    per_task = os.getenv(f"LLM_MAX_TOKENS_{task.upper()}", "").strip()
    if per_task:
        try:
            n = int(per_task)
            return n if n > 0 else None
        except ValueError:
            logger.warning(f"Ignoring non-integer LLM_MAX_TOKENS_{task.upper()}={per_task!r}")
    if task == "storyboard":
        return None
    return int(os.getenv("LLM_MAX_TOKENS", "16000"))


#: A system prompt at least this long (characters) is worth marking for a provider's prompt cache. Anthropic's models
#: cache only what is MARKED, and only a prefix of about a thousand tokens or more (two thousand for the small model);
#: a shorter one is sent plain. OpenAI's, Google's and DeepSeek's cache a repeated prefix by themselves.
CACHE_FROM_CHARS = 3500


def system_message(model: str, text: str) -> dict:
    """The system message of a call. For a model that caches only a marked prefix, a long system prompt is marked: the
    same rules sent again within a few minutes (a lesson's chapters, its reviews, its rewrites) are then read from the
    cache at about a tenth of the price. The owner, 2026-10-12: "try to use prompt caching"."""
    if str(model).startswith("anthropic/") and len(text) >= CACHE_FROM_CHARS and os.getenv("LLM_PROMPT_CACHE", "1") != "0":
        return {"role": "system", "content": [{"type": "text", "text": text, "cache_control": {"type": "ephemeral"}}]}
    return {"role": "system", "content": text}


def cached_of(usage: dict | None) -> int:
    """How many prompt tokens of an answered call were read from the provider's cache (0 when it does not say)."""
    details = (usage or {}).get("prompt_tokens_details") or {}
    try:
        return int(details.get("cached_tokens") or 0)
    except (TypeError, ValueError):
        return 0


#: How each model THINKS when the caller does not say. The owner's Model Choice Protocol (2026-10-12): "Thinking off by
#: default … Remember the choice per model" (cheap thinking models had spent whole budgets thinking and answered nothing).
#: Measured on the lesson writer (``scripts/eval_writer.py``, scorecard in ``evals/writer/``, 2026-10-14): every model
#: here answered whole and well with thinking off. Haiku 5.5 is NOT here on purpose: with thinking off it wrote worse
#: lessons (judge 74 against 81 after review), so it thinks as the provider has it. An explicit ``reasoning`` argument
#: wins over this table, and ``OPENROUTER_REASONING_EFFORT`` wins over it too.
THINKING_BY_MODEL = {
    "qwen/qwen3.8-flash": {"effort": "none"},
    "deepseek/deepseek-v3.2": {"effort": "none"},
    "google/gemini-3.1-flash-lite": {"effort": "none"},
    "openai/gpt-5.4-nano": {"effort": "none"},
    "z-ai/glm-4.7-flash": {"effort": "none"},
    # Its effort list is only "xhigh" and "high", so "none" is not on offer; OpenRouter's documented switch is
    # ``enabled: false``. Measured on the scene writer (``scripts/eval_scenes.py``, 2026-10-15): with it, 0
    # reasoning tokens in 11 calls and 7 of 8 scenes verified at 0.0003 USD a scene; without it, 6,650 reasoning
    # tokens a call on average and 80 s a scene. NOTE: ``deepseek/deepseek-v3.2`` above still reasoned on 2 of 3
    # first calls with either switch (7,912 and 9,462 tokens), depending on which provider served it.
    "deepseek/deepseek-v4-flash": {"enabled": False},
}

#: Thinking per TASK of the engine's chains, read before ``THINKING_BY_MODEL``: one model may be right with
#: thinking for one job and without it for another. Haiku 5.5 writes better lesson scripts thinking (see above),
#: and writes Manim scenes as well without it, three times cheaper and three times faster (scene eval,
#: 2026-10-15: 8 of 8 verified on the first try both ways; 0.0008 against 0.0022 USD and 6 s against 19 s a scene).
THINKING_BY_TASK = {
    "code": {"anthropic/claude-haiku-5.5": {"enabled": False}},
}


def thinking_for(model: str, task: str = "") -> dict | None:
    """The thinking setting a model is called with when nobody asks for another (``THINKING_BY_TASK``, then
    ``THINKING_BY_MODEL``)."""
    model = str(model or "").strip()
    found = THINKING_BY_TASK.get(task or "", {}).get(model) or THINKING_BY_MODEL.get(model)
    return dict(found) if found else None


def _call_openai_compatible(provider, url, api_key, models, prompt, system_instruction,
                            response_schema, temperature, extra_headers=None,
                            max_tokens=_ENV_CAP, json_object=False, note="", timeout=180.0,
                            reasoning=None, task=""):
    """POST to any OpenAI-compatible /chat/completions endpoint, trying each model in turn.

    ``json_object=True`` asks for JSON mode without a schema (the writer's shape is in
    the prompt). OpenRouter calls are metered through ``lessonforge.spend``: the budget
    is checked before the first request and the reported ``usage.cost`` is recorded
    after each successful one.
    """
    import httpx
    from lessonforge import spend

    sys_inst = system_instruction or ""
    if response_schema is not None:
        # These APIs take no Pydantic schema; embed the JSON schema and request a JSON object.
        try:
            schema_json = json.dumps(response_schema.model_json_schema())
            sys_inst += ("\n\nReturn ONLY a single JSON object conforming to this JSON Schema "
                         "(no markdown, no prose):\n" + schema_json)
        except Exception:
            sys_inst += "\n\nReturn ONLY a single valid JSON object (no markdown, no prose)."

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    if extra_headers:
        headers.update(extra_headers)

    if max_tokens is _ENV_CAP:
        max_tokens = int(os.getenv("LLM_MAX_TOKENS", "16000"))
    elif max_tokens is None:
        # "Uncapped" (the storyboard, see _max_tokens_for_task) cannot mean no field here: OpenRouter answers 402
        # when the balance is below the worst case it prices from the model's own maximum (65535). A large bounded
        # ceiling keeps that worst case small. 2026-11-10: this branch used to fall into LLM_MAX_TOKENS (8192),
        # which cut every storyboard of about 7 scenes or more off with finish_reason=length.
        max_tokens = int(os.getenv("LLM_MAX_TOKENS_UNCAPPED", "32000"))

    metered = provider == "OpenRouter"
    if metered:
        spend.check(what=f"{provider} {note or 'chat'} call")
    reasoning_effort = os.getenv("OPENROUTER_REASONING_EFFORT", "").strip()

    last_error = None
    for model in models:
        try:
            logger.info(f"Attempting {provider} call with model: {model}")
            # max_tokens is a cap, not a target: models still stop when done, so a high
            # (or absent) cap never costs idle tokens. History: an 8000 ceiling truncated
            # a live storyboard (finish_reason=length, measured 2026-07-21) and the weak
            # deepseek fallback then shipped a degenerate board; since 2026-07-31 the
            # storyboard task is uncapped entirely (see _max_tokens_for_task) — the
            # finish_reason gate below is the completeness guard either way.
            messages = ([system_message(model, sys_inst)] if sys_inst else []) + [{"role": "user", "content": prompt}]
            body = {"model": model, "messages": messages, "temperature": temperature}
            if max_tokens:
                body["max_tokens"] = max_tokens
            if response_schema is not None or json_object:
                body["response_format"] = {"type": "json_object"}
            if metered:
                body["usage"] = {"include": True}
                # Gemini 3.x on OpenRouter reasons by default and bills the reasoning as
                # completion tokens; the effort is the only lever (disabling is refused).
                # An explicit ``reasoning`` argument (e.g. {"enabled": False} for an
                # interactive call that must answer in a second or two) wins over the env.
                if reasoning is not None:
                    body["reasoning"] = reasoning
                elif reasoning_effort:
                    body["reasoning"] = {"effort": reasoning_effort}
                elif thinking_for(model, task):
                    body["reasoning"] = thinking_for(model, task)
            started = time.time()
            r = httpx.post(url, headers=headers, json=body, timeout=timeout)
            if r.status_code != 200:
                raise RuntimeError(f"{provider} HTTP {r.status_code}: {r.text[:300]}")
            payload = r.json()
            choice = (payload.get("choices") or [{}])[0]
            text = choice.get("message", {}).get("content")
            # A truncated completion is a FAILED completion. Without this check the
            # partial JSON flows into loads_json_lenient, json_repair closes it into
            # something structurally valid, and a gutted storyboard renders as a
            # 3-second video with no error anywhere (measured 2026-07-20).
            finish = choice.get("finish_reason") or choice.get("native_finish_reason")
            usage = payload.get("usage") or {}
            if metered and (finish in ("length", "error", "content_filter") or not text):
                # About to be discarded below, and BILLED all the same: it goes into the ledger first. Until
                # 2026-10-09 the record came only after these checks, so a truncated answer (often the most
                # expensive kind: a full window of reasoning) cost money that no report ever showed.
                spend.record("chat", model, usage.get("cost"),
                             prompt_tokens=usage.get("prompt_tokens", 0),
                             completion_tokens=usage.get("completion_tokens", 0),
                             reasoning_tokens=(usage.get("completion_tokens_details") or {}).get("reasoning_tokens", 0),
                             seconds=round(time.time() - started, 2), note=f"{note or 'chat'} (discarded: {finish or 'empty'})",
                             generation_id=payload.get("id"), estimated=usage.get("cost") is None, cached_tokens=cached_of(usage))
            if finish == "length":
                cap_desc = (f"max_tokens={body['max_tokens']}" if "max_tokens" in body
                            else "no request cap — the MODEL's own output window")
                remedy = ("Raise LLM_MAX_TOKENS (or the per-task LLM_MAX_TOKENS_<TASK>) "
                          "or use a model that spends less budget on reasoning."
                          if "max_tokens" in body else
                          "The model's output window is the binding limit: use a model "
                          "with a larger window, or split the request (chapterize).")
                raise RuntimeError(
                    f"{provider} model {model} hit the token ceiling: finish_reason=length, "
                    f"completion_tokens={usage.get('completion_tokens')} of {cap_desc} "
                    f"(reasoning_tokens={(usage.get('completion_tokens_details') or {}).get('reasoning_tokens')}) "
                    f"— response truncated, discarding. {remedy}"
                )
            # Same class as `length`: any non-`stop` terminal reason means the model did
            # NOT finish, so the content is partial no matter how well-formed it parses.
            # Measured 2026-07-21: a storyboard came back `finish=error,
            # completion_tokens=0`, was accepted here, and only the downstream shape gate
            # caught it ("scene 3 has no narration cues"). Reject at the provider so the
            # NEXT model in the chain gets a turn instead of burning the whole request.
            if finish in ("error", "content_filter"):
                raise RuntimeError(
                    f"{provider} model {model} did not complete: finish_reason={finish}, "
                    f"completion_tokens={usage.get('completion_tokens')} — partial content, "
                    f"discarding and falling through to the next model."
                )
            if not text:
                raise RuntimeError(f"{provider} model {model} returned empty content "
                                   f"(finish_reason={finish}).")
            logger.info(f"{provider} call succeeded with model: {model} "
                        f"(finish={finish}, completion_tokens={usage.get('completion_tokens')})")
            if metered:
                spend.record("chat", model, usage.get("cost"),
                             prompt_tokens=usage.get("prompt_tokens", 0),
                             completion_tokens=usage.get("completion_tokens", 0),
                             reasoning_tokens=(usage.get("completion_tokens_details") or {}).get("reasoning_tokens", 0),
                             seconds=round(time.time() - started, 2), note=note,
                             generation_id=payload.get("id"), estimated=usage.get("cost") is None, cached_tokens=cached_of(usage))
            return text
        except Exception as e:
            logger.warning(f"{provider} model {model} failed: {e}")
            last_error = e
            continue
    raise last_error if last_error else RuntimeError(f"All {provider} models failed.")


def call_openrouter(api_key, prompt, system_instruction, response_schema=None, temperature=0.2,
                    models=None, max_tokens=_ENV_CAP, json_object=False, note="", timeout=180.0,
                    reasoning=None, task=""):
    if models is None:
        models = _resolve_models("openrouter", "general")
    return _call_openai_compatible("OpenRouter", OPENROUTER_URL, api_key, models, prompt,
                                   system_instruction, response_schema, temperature,
                                   extra_headers={"X-Title": "lessonforge"},
                                   max_tokens=max_tokens, json_object=json_object, note=note,
                                   timeout=timeout, reasoning=reasoning, task=task)


ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"


#: USD per million tokens, (input, output, cache read), first match on the model id wins. A cache write (5 minutes)
#: costs 1.25x the input price. Haiku 5.5 doubles to 0.50 / 2.50 for a prompt over 100K tokens (see _estimate).
#: Prices checked against the Claude API docs on 2026-11-10; an id that matches nothing is priced like Sonnet 4.x,
#: so an unknown model reads as a middling cost, not as free.
_ANTHROPIC_PRICES = (
    ("haiku-5", (0.10, 0.50, 0.01)),
    ("sonnet-5", (2.00, 10.00, 0.20)),
    ("opus-5-5", (4.00, 20.00, 0.20)),
    ("fable", (10.00, 50.00, 0.25)),
    ("mythos", (10.00, 50.00, 0.25)),
    ("opus-5", (5.00, 25.00, 0.50)),
    ("opus-4", (5.00, 25.00, 0.50)),
    ("haiku-4", (1.00, 5.00, 0.10)),
    ("sonnet-4", (3.00, 15.00, 0.30)),
    ("haiku", (0.80, 4.00, 0.08)),     # 3.x
    ("opus", (15.00, 75.00, 1.50)),    # 3.x
)


def _estimate_anthropic_cost(model: str, input_tokens: int, output_tokens: int,
                             cache_read: int = 0, cache_write: int = 0) -> float:
    """Estimated USD of one Anthropic call. `input_tokens` is the uncached part (the API reports cached tokens
    separately), so the three input kinds add up without overlap."""
    m = model.lower()
    price_in, price_out, price_read = (3.00, 15.00, 0.30)
    for marker, price in _ANTHROPIC_PRICES:
        if marker in m:
            price_in, price_out, price_read = price
            break
    if "haiku-5" in m and (input_tokens + cache_read + cache_write) > 100_000:
        price_in, price_out = 0.50, 2.50
    return (input_tokens * price_in + output_tokens * price_out
            + cache_read * price_read + cache_write * price_in * 1.25) / 1_000_000


#: Models that take `output_config.effort` and think by default (thinking cannot be switched off on Opus 5.5 and
#: Sonnet 5.5). Older ids (3.x, 4.x) 400 on `effort`, so they are sent without it.
_ANTHROPIC_EFFORT_MODEL = re.compile(r"^claude-(opus|sonnet|haiku|fable|mythos)-5")

#: How hard each task makes a 5.x model think. It is the cost lever: thinking tokens are billed as output.
#: Storyboard is the plan every later stage depends on; vision is a bounded checklist. `ANTHROPIC_EFFORT_<TASK>`
#: overrides one (low | medium | high | xhigh | max).
_ANTHROPIC_EFFORT_BY_TASK = {"storyboard": "high", "code": "medium", "general": "low", "vision": "low"}

#: Thinking tokens count against max_tokens, so a 5.x model gets this much extra room on top of what the caller
#: asked for, or a long script could be cut off mid-way by its own reasoning.
_ANTHROPIC_THINKING_HEADROOM = 4096


def _anthropic_effort(model: str, task: str):
    if not _ANTHROPIC_EFFORT_MODEL.match(model or ""):
        return None
    return (os.getenv(f"ANTHROPIC_EFFORT_{(task or 'general').upper()}", "").strip().lower()
            or _ANTHROPIC_EFFORT_BY_TASK.get(task or "general", "medium"))


def _anthropic_system(text: str):
    """The `system` field: a long prompt becomes one cache-marked block (read back at a fraction of the price when
    the same rules are sent again within minutes); a short one stays a plain string."""
    if text and len(text) >= CACHE_FROM_CHARS and os.getenv("LLM_PROMPT_CACHE", "1") != "0":
        return [{"type": "text", "text": text, "cache_control": {"type": "ephemeral"}}]
    return text


def call_anthropic(api_key, prompt, system_instruction, response_schema=None, temperature=0.2,
                   models=None, max_tokens=None, note="", timeout=180.0, task=""):
    """Call Anthropic API directly with model failover over models chain.

    `temperature` is accepted for the shared call signature but NOT sent: Opus 5.5, Sonnet 5.5 and Haiku 5.5
    answer 400 to a non-default sampling value, and the API is removing it for every model.
    """
    import httpx
    from lessonforge import spend

    if models is None:
        models = _resolve_models("anthropic", task or "general")

    sys_inst = system_instruction or ""
    if response_schema is not None:
        try:
            schema_json = json.dumps(response_schema.model_json_schema())
            sys_inst += ("\n\nReturn ONLY a single JSON object conforming to this JSON Schema "
                         "(no markdown, no prose):\n" + schema_json)
        except Exception:
            sys_inst += "\n\nReturn ONLY a single valid JSON object (no markdown, no prose)."

    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json",
    }

    # None / the env cap mean "no explicit ceiling" (storyboard): use the large bounded one, as OpenRouter's path does.
    if max_tokens is None or max_tokens is _ENV_CAP:
        max_tokens = int(os.getenv("LLM_MAX_TOKENS_UNCAPPED", "32000"))

    last_error = None
    for model in models:
        try:
            logger.info(f"Attempting Anthropic call with model: {model}")
            effort = _anthropic_effort(model, task)
            body = {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": max_tokens + (_ANTHROPIC_THINKING_HEADROOM if effort else 0),
            }
            if effort:
                body["output_config"] = {"effort": effort}
            if sys_inst:
                body["system"] = _anthropic_system(sys_inst)

            started = time.time()
            r = httpx.post(ANTHROPIC_URL, headers=headers, json=body,
                           timeout=max(timeout, 300.0) if body["max_tokens"] > 16000 else timeout)
            if r.status_code != 200:
                raise RuntimeError(f"Anthropic HTTP {r.status_code}: {r.text[:300]}")
            payload = r.json()
            stop_reason = payload.get("stop_reason")
            usage = payload.get("usage") or {}
            in_tokens = usage.get("input_tokens", 0)
            out_tokens = usage.get("output_tokens", 0)
            cache_read = usage.get("cache_read_input_tokens", 0) or 0
            cache_write = usage.get("cache_creation_input_tokens", 0) or 0

            text_blocks = [b.get("text", "") for b in payload.get("content", []) if b.get("type") == "text"]
            text = "".join(text_blocks).strip()

            cost = _estimate_anthropic_cost(model, in_tokens, out_tokens, cache_read, cache_write)
            spend.record("chat", model, cost, prompt_tokens=in_tokens + cache_read + cache_write,
                         completion_tokens=out_tokens, seconds=round(time.time() - started, 2),
                         note=note or "anthropic chat", generation_id=payload.get("id"), estimated=True)

            if stop_reason == "refusal":
                raise RuntimeError(f"Anthropic model {model} declined the request (stop_reason=refusal).")
            if stop_reason == "max_tokens":
                raise RuntimeError(
                    f"Anthropic model {model} hit token ceiling: stop_reason=max_tokens, "
                    f"output_tokens={out_tokens} — response truncated, discarding."
                )
            if not text:
                raise RuntimeError(f"Anthropic model {model} returned empty content (stop_reason={stop_reason})")

            logger.info(f"Anthropic call succeeded with model: {model} (stop_reason={stop_reason}, "
                        f"out_tokens={out_tokens}, cache_read={cache_read}, cost~${cost:.4f})")
            return text
        except Exception as e:
            logger.warning(f"Anthropic model {model} failed: {e}")
            last_error = e
            continue
    raise last_error if last_error else RuntimeError("All Anthropic models failed.")


def call_groq(api_key, prompt, system_instruction, response_schema=None, temperature=0.2,
              models=None, max_tokens=_ENV_CAP):
    if models is None:
        models = _resolve_models("groq", "general")
    return _call_openai_compatible("Groq", GROQ_URL, api_key, models, prompt,
                                   system_instruction, response_schema, temperature,
                                   max_tokens=max_tokens)


def call_vision_llm(prompt, images_b64, system_instruction=None, keys=None, temperature=0.1):
    """Multimodal critique call: text prompt + JPEG frames (base64) -> response text.

    Supports Anthropic (vision models like claude-haiku-5-5 / claude-sonnet-5-5)
    and OpenRouter (Gemini multimodal).
    """
    import httpx

    # Check Anthropic first if it's configured and in provider order (or has key)
    anthropic_key = _anthropic_key(keys)
    anthropic_models = _resolve_models("anthropic", "vision")
    order = _provider_order("vision")
    if anthropic_key and anthropic_models and "anthropic" in order:
        content = [{"type": "text", "text": prompt}]
        for b64 in images_b64:
            content.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/jpeg",
                    "data": b64,
                }
            })
        headers = {
            "x-api-key": anthropic_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }
        for model in anthropic_models:
            try:
                logger.info(f"Anthropic Vision QA call: model {model}, {len(images_b64)} frame(s).")
                # No `temperature`: the 5.x models reject a non-default value (see call_anthropic).
                effort = _anthropic_effort(model, "vision")
                body = {
                    "model": model,
                    "messages": [{"role": "user", "content": content}],
                    "max_tokens": 4096 + (_ANTHROPIC_THINKING_HEADROOM if effort else 0),
                }
                if effort:
                    body["output_config"] = {"effort": effort}
                if system_instruction:
                    body["system"] = _anthropic_system(system_instruction)
                started = time.time()
                r = httpx.post(ANTHROPIC_URL, headers=headers, json=body, timeout=120.0)
                if r.status_code != 200:
                    raise RuntimeError(f"Anthropic HTTP {r.status_code}: {r.text[:300]}")
                payload = r.json()
                usage = payload.get("usage") or {}
                cache_read = usage.get("cache_read_input_tokens", 0) or 0
                cache_write = usage.get("cache_creation_input_tokens", 0) or 0
                cost = _estimate_anthropic_cost(model, usage.get("input_tokens", 0), usage.get("output_tokens", 0),
                                                cache_read, cache_write)
                try:
                    from lessonforge import spend
                    spend.record("chat", model, cost,
                                 prompt_tokens=usage.get("input_tokens", 0) + cache_read + cache_write,
                                 completion_tokens=usage.get("output_tokens", 0),
                                 seconds=round(time.time() - started, 2), note="anthropic vision",
                                 generation_id=payload.get("id"), estimated=True)
                except Exception:
                    logger.debug("Vision spend not recorded", exc_info=True)
                text_blocks = [b.get("text", "") for b in payload.get("content", []) if b.get("type") == "text"]
                text = "".join(text_blocks).strip()
                if text:
                    return text
            except Exception as e:
                logger.warning(f"Anthropic Vision QA model {model} failed: {e}")

    # OpenRouter provider
    api_key = _openrouter_key(keys)
    if not api_key or not images_b64:
        return None
    content = [{"type": "text", "text": prompt}]
    for b64 in images_b64:
        content.append({"type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{b64}"}})
    messages = []
    if system_instruction:
        messages.append({"role": "system", "content": system_instruction})
    messages.append({"role": "user", "content": content})
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json",
               "X-Title": "STEM Animation Lab"}
    models = _resolve_models("openrouter", "vision")
    for model in models:
        try:
            logger.info(f"Vision QA call: model {model}, {len(images_b64)} frame(s).")
            body = {"model": model, "messages": messages, "temperature": temperature,
                    "max_tokens": int(os.getenv("LLM_MAX_TOKENS", "16000"))}
            r = httpx.post(OPENROUTER_URL, headers=headers, json=body, timeout=120.0)
            if r.status_code != 200:
                raise RuntimeError(f"OpenRouter HTTP {r.status_code}: {r.text[:300]}")
            choice = (r.json().get("choices") or [{}])[0]
            text = choice.get("message", {}).get("content")
            finish = choice.get("finish_reason") or choice.get("native_finish_reason")
            if finish == "length":
                raise RuntimeError(f"model {model} truncated (finish_reason=length)")
            if not text:
                raise RuntimeError(f"model {model} returned empty content")
            return text
        except Exception as e:
            logger.warning(f"Vision QA model {model} failed: {e}")
    return None


def call_llm_with_fallback(gemini_client, prompt, system_instruction, response_schema=None,
                           temperature=0.2, task="general", keys=None):
    """Provider-agnostic generation over a configurable provider order (default Gemini ->
    OpenRouter -> Groq -> Anthropic). `task` ("general"|"code"|"storyboard") selects the per-provider
    model chain AND the output-token cap (storyboard is uncapped — _max_tokens_for_task)."""
    max_tokens = _max_tokens_for_task(task)
    errors = []
    for provider in _provider_order(task):
        try:
            if provider == "gemini":
                if gemini_client is None:
                    continue
                # The genai path sets no max_output_tokens — it is already uncapped up to
                # the model's own output window for every task.
                resp = call_gemini_with_fallback(gemini_client, prompt, system_instruction,
                                                 response_schema, temperature, models=_resolve_models("gemini", task))
                return LLMResponse(resp.text)
            if provider == "openrouter":
                key = _openrouter_key(keys)
                if not key:
                    continue
                return LLMResponse(call_openrouter(key, prompt, system_instruction, response_schema,
                                                   temperature, models=_resolve_models("openrouter", task),
                                                   max_tokens=max_tokens, note=task, task=task))
            if provider == "groq":
                key = _groq_key(keys)
                if not key:
                    continue
                return LLMResponse(call_groq(key, prompt, system_instruction, response_schema,
                                             temperature, models=_resolve_models("groq", task),
                                             max_tokens=max_tokens))
            if provider == "anthropic":
                key = _anthropic_key(keys)
                if not key:
                    continue
                return LLMResponse(call_anthropic(key, prompt, system_instruction, response_schema,
                                                   temperature, models=_resolve_models("anthropic", task),
                                                   max_tokens=max_tokens, note=task, task=task))
            logger.warning(f"Unknown provider in LLM_PROVIDER_ORDER: {provider}")
        except Exception as e:
            errors.append(e)
            logger.warning(f"{provider} provider failed: {e}")

    if errors:
        raise errors[-1]
    raise ValueError("No LLM provider configured. Set GEMINI_API_KEY (or paste a key in the UI), "
                     "OPENROUTER_API_KEY, GROQ_API_KEY, or ANTHROPIC_API_KEY.")


def loads_json_lenient(text):
    """json.loads after stripping any markdown code fences, using json_repair for robustness.

    NOTE: json_repair makes malformed JSON parse — it does NOT make it complete. Anything
    downstream that cares about completeness must check the shape itself (see
    storyboard_shape_problems).
    """
    cleaned = strip_code_fences(text)
    try:
        import json_repair
        return json_repair.loads(cleaned)
    except ImportError:
        import json
        return json.loads(cleaned)


def strip_code_fences(code):
    """Remove accidental markdown ``` fences the model sometimes emits."""
    code = (code or "").strip()
    if code.startswith("```"):
        # Drop the opening fence line (``` or ```python)
        code = code.split("\n", 1)[1] if "\n" in code else ""
    if code.endswith("```"):
        code = code[: code.rfind("```")]
    return code.strip()
