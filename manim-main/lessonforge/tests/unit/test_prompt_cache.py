"""Prompt caching: a long system prompt is marked for the model family that caches only what is marked, and the ledger
keeps how much of a call's input was read from the cache (so the saving is a number, not a hope).

The owner, 2026-10-12: "try to use prompt caching. We are not using caching and because of that it is leading to so much
cost." Measured the same evening on the writer's standing rules (4,592 tokens) sent twice to the small model: the first
call wrote 4,573 tokens to the cache, the second read them and cost a third of the first.
"""
import pytest

from lessonforge import spend
from lessonforge.engine import llm

LONG = "The standing rules of a writer, the same in every call of a lesson. " * 80


@pytest.fixture
def ledger(tmp_path, monkeypatch):
    path = tmp_path / "spend.jsonl"
    monkeypatch.setenv("OPENROUTER_LEDGER", str(path))
    monkeypatch.setenv("OPENROUTER_BUDGET_USD", "1.00")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)  # no remote check
    return path


class Answer:
    status_code, text = 200, ""

    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


def test_a_long_system_prompt_is_marked_only_for_the_family_that_needs_the_mark(monkeypatch):
    marked = llm.system_message("anthropic/claude-haiku-5.5", LONG)
    assert marked["role"] == "system" and marked["content"] == [{"type": "text", "text": LONG, "cache_control": {"type": "ephemeral"}}]
    # a short one is below what a provider caches: sent plain
    assert llm.system_message("anthropic/claude-haiku-5.5", "Short rules.") == {"role": "system", "content": "Short rules."}
    # these cache a repeated prefix by themselves; a mark they do not know must not reach them
    for model in ("openai/gpt-5.4-nano", "google/gemini-2.5-flash", "deepseek/deepseek-v4-pro"):
        assert llm.system_message(model, LONG) == {"role": "system", "content": LONG}
    monkeypatch.setenv("LLM_PROMPT_CACHE", "0")                             # the switch
    assert llm.system_message("anthropic/claude-haiku-5.5", LONG) == {"role": "system", "content": LONG}


def test_each_model_of_a_chain_gets_its_own_form_and_the_ledger_keeps_what_was_read_from_the_cache(ledger, monkeypatch):
    sent = []

    def post(url, headers=None, json=None, timeout=None):
        sent.append(json)
        if json["model"].startswith("anthropic/"):                         # billed, and discarded: the chain moves on
            return Answer({"id": "gen-1", "choices": [{"message": {"content": ""}, "finish_reason": "error"}],
                           "usage": {"cost": 0.001, "prompt_tokens": 4000, "prompt_tokens_details": {"cached_tokens": 0}}})
        return Answer({"id": "gen-2", "choices": [{"message": {"content": '{"ok": true}'}, "finish_reason": "stop"}],
                       "usage": {"cost": 0.0002, "prompt_tokens": 4000, "completion_tokens": 5,
                                 "prompt_tokens_details": {"cached_tokens": 3800}}})
    monkeypatch.setattr("httpx.post", post)
    text = llm.call_openrouter("key", "the brief", LONG, models=["anthropic/claude-haiku-5.5", "openai/gpt-5.4-nano"], note="writer")
    assert text == '{"ok": true}'
    assert isinstance(sent[0]["messages"][0]["content"], list) and sent[1]["messages"][0]["content"] == LONG
    assert sent[0]["messages"][1] == sent[1]["messages"][1] == {"role": "user", "content": "the brief"}
    rows = spend.entries()
    assert [row.get("cached_tokens") for row in rows] == [None, 3800]      # written only when something was read from the cache
    assert rows[0]["note"].startswith("writer (discarded") and rows[1]["note"] == "writer"
    assert llm.cached_of(None) == 0 and llm.cached_of({"prompt_tokens_details": {"cached_tokens": "many"}}) == 0


def test_a_look_at_a_picture_marks_its_rules_and_records_the_cache_too(ledger, monkeypatch):
    from lessonforge.harness import vision_review
    monkeypatch.setenv("OPENROUTER_API_KEY", "key")
    monkeypatch.setattr(spend, "check", lambda *a, **k: None)              # the budget guard is another test's subject
    sent = []

    def post(url, json=None, timeout=None, headers=None):
        sent.append(json)
        return Answer({"id": "gen-3", "choices": [{"message": {"content": '{"findings": []}'}}],
                       "usage": {"cost": 0.0004, "prompt_tokens": 2600, "completion_tokens": 12, "prompt_tokens_details": {"cached_tokens": 2100}}})
    monkeypatch.setattr("httpx.post", post)
    judge = vision_review.default_judge(models=("anthropic/claude-haiku-5.5",))
    assert judge("what is on this frame?", LONG, "aGVsbG8=") == {"findings": []}
    assert sent[0]["messages"][0]["content"][0]["cache_control"] == {"type": "ephemeral"}
    assert sent[0]["messages"][1]["content"][1]["type"] == "image_url"     # the picture changes every call: after the cached rules
    assert spend.entries()[-1]["cached_tokens"] == 2100 and spend.entries()[-1]["kind"] == "vision"


def test_a_model_measured_better_without_thinking_is_asked_that_way_unless_the_caller_says_otherwise(ledger, monkeypatch):
    """The owner's Model Choice Protocol (2026-10-14): thinking off by default, the choice remembered per model.

    Measured on the writer: Qwen 3.8 Flash with thinking off scored with Haiku 5.5 at a seventh of the cost, and Haiku
    with thinking off wrote worse lessons, so it is not in the table.
    """
    sent = []

    def post(url, headers=None, json=None, timeout=None):
        sent.append(json)
        return Answer({"id": "gen-4", "choices": [{"message": {"content": '{"ok": true}'}, "finish_reason": "stop"}],
                       "usage": {"cost": 0.0001, "prompt_tokens": 10, "completion_tokens": 3}})
    monkeypatch.setattr("httpx.post", post)
    monkeypatch.delenv("OPENROUTER_REASONING_EFFORT", raising=False)
    llm.call_openrouter("key", "brief", "rules", models=["qwen/qwen3.8-flash"], note="writer")
    llm.call_openrouter("key", "brief", "rules", models=["anthropic/claude-haiku-5.5"], note="writer")
    llm.call_openrouter("key", "brief", "rules", models=["qwen/qwen3.8-flash"], note="writer", reasoning={"effort": "low"})
    monkeypatch.setenv("OPENROUTER_REASONING_EFFORT", "medium")
    llm.call_openrouter("key", "brief", "rules", models=["qwen/qwen3.8-flash"], note="writer")
    assert sent[0]["reasoning"] == {"effort": "none"}
    assert "reasoning" not in sent[1]                                       # Haiku thinks as the provider has it
    assert sent[2]["reasoning"] == {"effort": "low"}                        # the caller wins
    assert sent[3]["reasoning"] == {"effort": "medium"}                     # so does the environment
    assert llm.thinking_for(" qwen/qwen3.8-flash ") == {"effort": "none"} and llm.thinking_for("") is None
    llm.thinking_for("qwen/qwen3.8-flash")["effort"] = "high"               # a copy: the table cannot be changed by a caller
    assert llm.THINKING_BY_MODEL["qwen/qwen3.8-flash"] == {"effort": "none"}


def test_a_look_at_a_picture_asks_a_model_from_the_table_without_thinking(ledger, monkeypatch):
    from lessonforge.harness import vision_review
    monkeypatch.setenv("OPENROUTER_API_KEY", "key")
    monkeypatch.setattr(spend, "check", lambda *a, **k: None)
    sent = []

    def post(url, json=None, timeout=None, headers=None):
        sent.append(json)
        return Answer({"id": "gen-5", "choices": [{"message": {"content": '{"findings": []}'}}],
                       "usage": {"cost": 0.0001, "prompt_tokens": 50, "completion_tokens": 5}})
    monkeypatch.setattr("httpx.post", post)
    vision_review.default_judge(models=("google/gemini-3.1-flash-lite",))("look", "rules", "aGVsbG8=")
    vision_review.default_judge(models=("google/gemini-3.8-flash",))("look", "rules", "aGVsbG8=")
    assert sent[0]["reasoning"] == {"effort": "none"} and "reasoning" not in sent[1]


def test_a_task_can_switch_a_models_thinking_off_without_changing_it_for_other_tasks(ledger, monkeypatch):
    """Scene eval (2026-10-15): Haiku 5.5 writes Manim scenes as well without thinking (8 of 8 both ways) at a third
    of the cost, while it writes worse lesson scripts without it. So the code task switches it off; the writer does not.
    DeepSeek V4 Flash offers no "none" effort: it is switched off with OpenRouter's ``enabled: false``.
    """
    sent = []

    def post(url, headers=None, json=None, timeout=None):
        sent.append(json)
        return Answer({"id": "gen-5", "choices": [{"message": {"content": "code"}, "finish_reason": "stop"}],
                       "usage": {"cost": 0.0001, "prompt_tokens": 10, "completion_tokens": 3}})
    monkeypatch.setattr("httpx.post", post)
    monkeypatch.delenv("OPENROUTER_REASONING_EFFORT", raising=False)
    monkeypatch.setenv("LLM_PROVIDER_ORDER_CODE", "openrouter")
    monkeypatch.setenv("OPENROUTER_CODE_MODELS", "anthropic/claude-haiku-5.5")
    keys = type("Keys", (), {"gemini": None, "openrouter": "key", "groq": None})()
    llm.call_llm_with_fallback(None, "a scene", "rules", task="code", keys=keys)
    llm.call_openrouter("key", "brief", "rules", models=["anthropic/claude-haiku-5.5"], note="writer")
    llm.call_openrouter("key", "brief", "rules", models=["deepseek/deepseek-v4-flash"], note="general")
    assert sent[0]["model"] == "anthropic/claude-haiku-5.5" and sent[0]["reasoning"] == {"enabled": False}
    assert "reasoning" not in sent[1]                                       # the writer's Haiku still thinks
    assert sent[2]["reasoning"] == {"enabled": False}
    assert llm.thinking_for("anthropic/claude-haiku-5.5", "code") == {"enabled": False}
    assert llm.thinking_for("anthropic/claude-haiku-5.5") is None
