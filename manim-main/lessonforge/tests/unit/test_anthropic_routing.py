"""Tests for Anthropic API provider integration, task model routing, and manual model selection."""
import json
from unittest.mock import patch, MagicMock
import pytest

from lessonforge.engine import model_routing, llm
from lessonforge.engine.dependencies import APIKeys


def test_anthropic_provider_in_routing():
    assert "anthropic" in model_routing.PROVIDERS
    snapshot = model_routing.snapshot()
    assert "anthropic" in snapshot["providers"]
    assert "anthropic" in snapshot["catalogue"]


def test_anthropic_task_chains_cost_and_capability_tiering():
    # Storyboard / Important tasks: costliest / strongest models
    sb_models = model_routing.resolve_models("anthropic", "storyboard")
    assert sb_models[0] == "claude-opus-5-5"
    assert "claude-sonnet-5-5" in sb_models      # failover

    # Code: the mid tier first
    code_models = model_routing.resolve_models("anthropic", "code")
    assert code_models[0] == "claude-sonnet-5-5"

    # General / small calls: cheap and fast
    gen_models = model_routing.resolve_models("anthropic", "general")
    assert gen_models[0] == "claude-haiku-5-5"

    # Vision check: cheap multimodal
    vision_models = model_routing.resolve_models("anthropic", "vision")
    assert vision_models[0] == "claude-haiku-5-5"


def test_anthropic_manual_model_selection():
    try:
        model_routing.apply_overrides(
            provider_order_list=["anthropic", "openrouter", "gemini", "groq"],
            chains={"storyboard": {"anthropic": ["claude-fable-5-1"]}},
        )
        assert model_routing.provider_order()[0] == "anthropic"
        sb = model_routing.resolve_models("anthropic", "storyboard")
        assert sb == ["claude-fable-5-1"]
    finally:
        model_routing.reset_overrides()


def test_call_anthropic_success():
    fake_response = MagicMock()
    fake_response.status_code = 200
    fake_response.json.return_value = {
        "id": "msg_test123",
        "type": "message",
        "role": "assistant",
        "content": [{"type": "text", "text": '{"result": "success"}'}],
        "model": "claude-sonnet-5-5",
        "stop_reason": "end_turn",
        "usage": {"input_tokens": 50, "output_tokens": 25},
    }

    with patch("httpx.post", return_value=fake_response) as mock_post:
        resp = llm.call_anthropic(
            api_key="test-key",
            prompt="Hello Claude",
            system_instruction="Be concise",
            models=["claude-sonnet-5-5"],
            task="general",
        )
        assert resp == '{"result": "success"}'
        assert mock_post.called
        kwargs = mock_post.call_args[1]
        assert kwargs["headers"]["x-api-key"] == "test-key"
        assert kwargs["headers"]["anthropic-version"] == "2023-06-01"
        assert kwargs["json"]["model"] == "claude-sonnet-5-5"
        assert kwargs["json"]["system"] == "Be concise"
        assert kwargs["json"]["max_tokens"] > 0


def test_call_llm_with_fallback_routes_to_anthropic():
    fake_response = MagicMock()
    fake_response.status_code = 200
    fake_response.json.return_value = {
        "id": "msg_test456",
        "type": "message",
        "role": "assistant",
        "content": [{"type": "text", "text": "Storyboard generated"}],
        "model": "claude-sonnet-5-5",
        "stop_reason": "end_turn",
        "usage": {"input_tokens": 100, "output_tokens": 200},
    }

    keys = APIKeys(anthropic="test-anthropic-key")

    with patch("httpx.post", return_value=fake_response):
        with patch.object(llm, "_provider_order", return_value=["anthropic"]):
            res = llm.call_llm_with_fallback(
                gemini_client=None,
                prompt="Generate lesson",
                system_instruction="Tutor persona",
                task="storyboard",
                keys=keys,
            )
            assert res.text == "Storyboard generated"


def test_call_vision_llm_anthropic():
    fake_response = MagicMock()
    fake_response.status_code = 200
    fake_response.json.return_value = {
        "id": "msg_vis123",
        "type": "message",
        "role": "assistant",
        "content": [{"type": "text", "text": "Scene visual layout is clean"}],
        "model": "claude-haiku-5-5",
        "stop_reason": "end_turn",
        "usage": {"input_tokens": 200, "output_tokens": 30},
    }

    keys = APIKeys(anthropic="test-anthropic-key")

    with patch("httpx.post", return_value=fake_response) as mock_post:
        with patch.object(llm, "_provider_order", return_value=["anthropic"]):
            res = llm.call_vision_llm(
                prompt="Check frame layout",
                images_b64=["aW1hZ2VkYXRh"],
                keys=keys,
            )
            assert res == "Scene visual layout is clean"
            body = mock_post.call_args[1]["json"]
            assert body["model"] == "claude-haiku-5-5"
            assert body["messages"][0]["content"][1]["type"] == "image"


def _ok_response(text="ok", usage=None, stop_reason="end_turn"):
    r = MagicMock()
    r.status_code = 200
    r.json.return_value = {"id": "msg_x", "content": [{"type": "text", "text": text}],
                           "stop_reason": stop_reason, "usage": usage or {"input_tokens": 10, "output_tokens": 5}}
    return r


def test_anthropic_request_has_no_temperature_and_sets_effort_per_task():
    # Opus 5.5 / Sonnet 5.5 / Haiku 5.5 answer 400 to a non-default temperature.
    for task, effort in (("storyboard", "high"), ("code", "medium"), ("general", "low")):
        with patch("httpx.post", return_value=_ok_response()) as post:
            llm.call_anthropic("k", "hi", "sys", temperature=0.7, models=["claude-sonnet-5-5"], task=task)
        body = post.call_args[1]["json"]
        assert "temperature" not in body
        assert body["output_config"] == {"effort": effort}


def test_anthropic_legacy_ids_get_no_effort_field():
    with patch("httpx.post", return_value=_ok_response()) as post:
        llm.call_anthropic("k", "hi", "sys", models=["claude-3-5-haiku-20241022"], task="code")
    assert "output_config" not in post.call_args[1]["json"]


def test_anthropic_uncapped_storyboard_is_not_cut_to_8192():
    # 2026-11-10: max_tokens=None was clamped to 8192, truncating boards of about 7 scenes or more.
    with patch("httpx.post", return_value=_ok_response()) as post:
        llm.call_anthropic("k", "hi", "sys", models=["claude-opus-5-5"], max_tokens=None, task="storyboard")
    assert post.call_args[1]["json"]["max_tokens"] >= 32000


def test_openai_compatible_none_cap_is_large_not_8192():
    r = MagicMock()
    r.status_code = 200
    r.json.return_value = {"choices": [{"message": {"content": "{}"}, "finish_reason": "stop"}], "usage": {}}
    with patch("httpx.post", return_value=r) as post, patch("lessonforge.spend.check"):
        llm.call_openrouter("k", "hi", "sys", models=["google/gemini-2.5-flash"], max_tokens=None)
    sent = post.call_args[1]["json"].get("max_tokens")
    assert sent is not None and sent >= 32000


def test_anthropic_long_system_prompt_is_cache_marked():
    long_sys = "rule. " * 1000
    with patch("httpx.post", return_value=_ok_response()) as post:
        llm.call_anthropic("k", "hi", long_sys, models=["claude-haiku-5-5"], task="general")
    system = post.call_args[1]["json"]["system"]
    assert isinstance(system, list) and system[0]["cache_control"] == {"type": "ephemeral"}


def test_anthropic_cost_uses_the_model_price_and_cache_rates():
    opus = llm._estimate_anthropic_cost("claude-opus-5-5", 1_000_000, 1_000_000)
    haiku = llm._estimate_anthropic_cost("claude-haiku-5-5", 50_000, 1_000_000)
    assert opus == pytest.approx(4.0 + 20.0)
    assert haiku == pytest.approx(0.05 * 0.10 + 0.50)
    assert haiku < llm._estimate_anthropic_cost("claude-sonnet-5-5", 50_000, 1_000_000) < opus
    # Haiku 5.5 costs more per token once the prompt passes 100K tokens
    assert llm._estimate_anthropic_cost("claude-haiku-5-5", 200_000, 0) == pytest.approx(0.2 * 0.50)
    # cache reads cost far less than fresh input; writes cost 1.25x
    assert llm._estimate_anthropic_cost("claude-sonnet-5-5", 0, 0, cache_read=1_000_000) == pytest.approx(0.20)
    assert llm._estimate_anthropic_cost("claude-sonnet-5-5", 0, 0, cache_write=1_000_000) == pytest.approx(2.5)


def test_scoped_routing_applies_then_restores():
    before_order = model_routing.provider_order("code")
    before_chain = model_routing.resolve_models("anthropic", "code")
    with model_routing.scoped_routing("anthropic", "claude-opus-5-5", "code"):
        assert model_routing.provider_order("code")[0] == "anthropic"
        assert model_routing.provider_order()[0] == "anthropic"
        assert model_routing.resolve_models("anthropic", "code") == ["claude-opus-5-5"]
        # the cheap tiers are untouched by a manual pick for the code task
        assert model_routing.resolve_models("anthropic", "vision")[0] == "claude-haiku-5-5"
    assert model_routing.provider_order("code") == before_order
    assert model_routing.resolve_models("anthropic", "code") == before_chain


def test_scoped_routing_restores_after_an_error_and_rejects_bad_choices():
    before = model_routing.provider_order()
    with pytest.raises(RuntimeError):
        with model_routing.scoped_routing("anthropic", None, "storyboard"):
            raise RuntimeError("task failed")
    assert model_routing.provider_order() == before
    with pytest.raises(ValueError):
        with model_routing.scoped_routing("anthropic", "some-thinking-model", "code"):
            pass
    with pytest.raises(ValueError):
        with model_routing.scoped_routing("nonsense", None, "code"):
            pass
    assert model_routing.provider_order() == before


def test_scoped_routing_auto_changes_nothing():
    before = model_routing.provider_order()
    with model_routing.scoped_routing("auto", "whatever", "code"):
        assert model_routing.provider_order() == before
    with model_routing.scoped_routing(None, None, "code"):
        assert model_routing.provider_order() == before
