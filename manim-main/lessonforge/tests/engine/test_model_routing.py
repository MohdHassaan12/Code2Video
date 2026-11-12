"""Acceptance harness for the model routing table + /api/models override surface.

No manim, no keys, no network, no app bootstrap: loads app/model_routing.py as a
standalone module (it deliberately has no heavy imports).

    .venv/bin/python stem_animation_lab/test_model_routing.py

What it pins:
  A. Resolution — env override beats default, per-task chains, the vision chain.
  B. The reasoning-model block: kimi-k3/glm-5.2 & friends are stripped from ANY
     chain (env or default) and rejected at the API, and stripping never leaves a
     provider with an empty chain.
  C. Overrides — validation happens before assignment (a rejected payload changes
     nothing), reset restores the start-of-process values exactly.
  D. Snapshot shape (what the UI panel renders) + provider-order handling.
"""
import os
import sys
import importlib.util

HERE = os.path.dirname(os.path.abspath(__import__("lessonforge").__file__))  # the installed package dir

CHECKS = []


def check(name, cond, detail=""):
    CHECKS.append((name, bool(cond), detail))
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"  — {detail}" if detail and not cond else ""))


def load_module(clean_env):
    """(Re)load model_routing with a controlled environment (it snapshots env at import)."""
    for var in ("LLM_PROVIDER_ORDER", "LLM_PROVIDER_ORDER_CODE", "GEMINI_MODELS", "GEMINI_CODE_MODELS",
                "GEMINI_STORYBOARD_MODELS", "OPENROUTER_MODELS", "OPENROUTER_CODE_MODELS",
                "OPENROUTER_STORYBOARD_MODELS", "VISION_QA_MODELS", "GROQ_MODELS",
                "GROQ_CODE_MODELS", "GROQ_STORYBOARD_MODELS", "GEMINI_API_KEY",
                "OPENROUTER_API_KEY", "GROQ_API_KEY", "LLM_MAX_TOKENS", "LLM_MAX_TOKENS_STORYBOARD"):
        os.environ.pop(var, None)
    os.environ.update(clean_env)
    spec = importlib.util.spec_from_file_location(
        "model_routing_under_test", os.path.join(HERE, "engine", "model_routing.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ── Part A: resolution ────────────────────────────────────────────────────────
print("\nPart A — chain resolution")
mr = load_module({})

check("A1 default provider order puts gemini first",
      mr.provider_order()[0] == "gemini", str(mr.provider_order()))
check("A2 gemini general default chain",
      mr.resolve_models("gemini", "general")[0] == "gemini-2.5-flash",
      str(mr.resolve_models("gemini", "general")))
check("A3 openrouter storyboard default differs from its general default",
      mr.resolve_models("openrouter", "storyboard") != mr.resolve_models("openrouter", "general"))
check("A4 vision chain resolves for openrouter only",
      mr.resolve_models("openrouter", "vision")[0] == "google/gemini-2.5-flash"
      and ("groq", "vision") not in mr.MODEL_ENV)
check("A5 a task with no per-provider default falls back to the general chain",
      mr.default_models("groq", "storyboard") == mr.default_models("groq", "general"))

mr = load_module({"OPENROUTER_CODE_MODELS": "a/one, b/two ,, c/three"})
check("A6 env override wins and is whitespace/empty tolerant",
      mr.resolve_models("openrouter", "code") == ["a/one", "b/two", "c/three"],
      str(mr.resolve_models("openrouter", "code")))
check("A7 env override does not leak into another task",
      mr.resolve_models("openrouter", "storyboard") != ["a/one", "b/two", "c/three"])

mr = load_module({"LLM_PROVIDER_ORDER": " Groq , GEMINI "})
check("A8 provider order is normalized (case, spaces)",
      mr.provider_order() == ["groq", "gemini"], str(mr.provider_order()))
mr = load_module({"LLM_PROVIDER_ORDER": "  "})
check("A9 a blank provider order falls back to all providers",
      mr.provider_order() == list(mr.PROVIDERS), str(mr.provider_order()))


# ── Part B: the reasoning-model block ─────────────────────────────────────────
print("\nPart B — reasoning models are blocked in code, not by comment")
mr = load_module({"OPENROUTER_CODE_MODELS": "moonshotai/kimi-k3,deepseek/deepseek-v3.2"})
check("B1 a blocked model is stripped from an env-supplied chain",
      mr.resolve_models("openrouter", "code") == ["deepseek/deepseek-v3.2"],
      str(mr.resolve_models("openrouter", "code")))

mr = load_module({"OPENROUTER_CODE_MODELS": "moonshotai/kimi-k3,z-ai/glm-5.2"})
resolved = mr.resolve_models("openrouter", "code")
check("B2 stripping never leaves an empty chain — falls back to the default",
      resolved == mr.default_models("openrouter", "code") and len(resolved) > 0, str(resolved))

check("B3 blocked_reason matches vendor prefixes and :free/:nitro suffixes",
      mr.blocked_reason("moonshotai/kimi-k3:free") == "kimi-k3"
      and mr.blocked_reason("Z-AI/GLM-5.2") == "glm-5.2"
      and mr.blocked_reason("qwen/qwen3-30b-a3b-thinking") == "thinking")
check("B4 an ordinary model is not blocked",
      mr.blocked_reason("deepseek/deepseek-v3.2") is None
      and mr.blocked_reason("google/gemini-2.5-flash") is None
      and mr.blocked_reason("qwen/qwen3-coder") is None)

try:
    mr.apply_overrides(None, {"code": {"openrouter": ["moonshotai/kimi-k3"]}})
    check("B5 the API rejects a blocked model outright", False, "no ValueError raised")
except ValueError as e:
    check("B5 the API rejects a blocked model outright",
          "kimi-k3" in str(e) and "reasoning" in str(e).lower(), str(e))

check("B6 the rejected payload changed nothing",
      os.environ.get("OPENROUTER_CODE_MODELS") == "moonshotai/kimi-k3,z-ai/glm-5.2",
      str(os.environ.get("OPENROUTER_CODE_MODELS")))


# ── Part C: overrides + reset ────────────────────────────────────────────────
print("\nPart C — runtime overrides and reset")
mr = load_module({"OPENROUTER_CODE_MODELS": "deepseek/deepseek-v3.2", "GEMINI_API_KEY": "x"})

state = mr.apply_overrides(["gemini", "groq"], {"code": {"openrouter": ["qwen/qwen3-coder"]}})
check("C1 apply sets the provider order",
      os.environ["LLM_PROVIDER_ORDER"] == "gemini,groq", os.environ["LLM_PROVIDER_ORDER"])
check("C2 apply sets the chain env var",
      os.environ["OPENROUTER_CODE_MODELS"] == "qwen/qwen3-coder")
check("C3 the snapshot reports the new chain and marks it runtime",
      state["chains"]["code"]["openrouter"]["models"] == ["qwen/qwen3-coder"]
      and state["chains"]["code"]["openrouter"]["source"] == "runtime")

mr.apply_overrides(None, {"code": {"openrouter": []}})
check("C4 an empty list clears the override back to the built-in default",
      "OPENROUTER_CODE_MODELS" not in os.environ
      and mr.resolve_models("openrouter", "code") == mr.default_models("openrouter", "code"))

mr.reset_overrides()
check("C5 reset restores the start-of-process env exactly",
      os.environ.get("OPENROUTER_CODE_MODELS") == "deepseek/deepseek-v3.2"
      and "LLM_PROVIDER_ORDER" not in os.environ,
      f"{os.environ.get('OPENROUTER_CODE_MODELS')} / {os.environ.get('LLM_PROVIDER_ORDER')}")
check("C6 after reset nothing is marked overridden",
      not mr.snapshot()["provider_order_overridden"]
      and not any(c["overridden"] for per in mr.snapshot()["chains"].values() for c in per.values()))

for bad, label in (
    ([], "C7 empty provider order rejected"),
    (["gemini", "gemini"], "C8 duplicate provider rejected"),
    (["openai"], "C9 unknown provider rejected"),
):
    try:
        mr.apply_overrides(bad, None)
        check(label, False, "no ValueError raised")
    except ValueError as e:
        check(label, True, str(e))

try:
    # Vision QA is OpenRouter-only — gemini/vision has no chain of its own.
    mr.apply_overrides(None, {"vision": {"gemini": ["gemini-2.5-flash"]}})
    check("C10 a provider/task pair with no chain of its own is rejected", False, "no ValueError")
except ValueError as e:
    check("C10 a provider/task pair with no chain of its own is rejected",
          "general chain" in str(e), str(e))

try:
    mr.apply_overrides(None, {"nonsense": {"gemini": ["gemini-2.5-flash"]}})
    check("C11 an unknown task is rejected", False, "no ValueError")
except ValueError as e:
    check("C11 an unknown task is rejected", "Unknown task" in str(e), str(e))

check("C12 a rejected payload left the env untouched",
      "LLM_PROVIDER_ORDER" not in os.environ and "GEMINI_MODELS" not in os.environ)


# ── Part D: snapshot shape (what the UI renders) ──────────────────────────────
print("\nPart D — snapshot shape")
mr = load_module({"GEMINI_API_KEY": "k", "OPENROUTER_STORYBOARD_MODELS": "google/gemini-2.5-flash"})
snap = mr.snapshot()
check("D1 every task is present with at least one provider chain",
      all(snap["chains"].get(t) for t in snap["tasks"]), str(list(snap["chains"])))
check("D2 availability is read from the provider keys",
      snap["providers"]["gemini"]["available"] and not snap["providers"]["groq"]["available"])
check("D3 an env-supplied chain is labelled 'env', an untouched one 'default'",
      snap["chains"]["storyboard"]["openrouter"]["source"] == "env"
      and snap["chains"]["general"]["gemini"]["source"] == "default")
check("D4 each chain carries its env var name and built-in default for the UI",
      snap["chains"]["code"]["openrouter"]["env_var"] == "OPENROUTER_CODE_MODELS"
      and len(snap["chains"]["code"]["openrouter"]["default"]) >= 1)
check("D5 the catalogue offers models for every provider",
      all(snap["catalogue"].get(p) for p in mr.PROVIDERS))
check("D6 no catalogue entry is a blocked model",
      not [m["id"] for ms in snap["catalogue"].values() for m in ms if mr.blocked_reason(m["id"])])
check("D7 the storyboard cap reads 'uncapped' by default",
      snap["max_tokens"]["storyboard"] == "uncapped" and snap["max_tokens"]["global"] == "16000")


class _Keys:
    gemini, openrouter, groq, anthropic = None, "or-key", None, None


check("D9 the storyboard task exposes a lever for every provider that can serve it",
      set(snap["chains"]["storyboard"]) == {"gemini", "openrouter", "groq", "anthropic"},
      str(sorted(snap["chains"]["storyboard"])))
check("D10 gemini's storyboard chain is settable separately from its general chain",
      mr.MODEL_ENV[("gemini", "storyboard")] != mr.MODEL_ENV[("gemini", "general")])

check("D8 an APIKeys object overrides env for availability",
      mr.snapshot(_Keys())["providers"]["openrouter"]["available"]
      and not mr.snapshot(_Keys())["providers"]["gemini"]["available"])


# ── Part E: the catalogue check behind scripts/check_models.py ───────────────
print("\nPart E — catalogue_problems (pure; the script feeds it the live catalogue)")
mr = load_module({})
cp = mr.catalogue_problems
check("E1 a model missing from the catalogue is dead",
      cp("openai/gpt-oss-120b:free", None) == [("dead", "not in the OpenRouter catalogue")])
check("E2 mandatory reasoning thinks, even when the caller switches it off",
      [k for k, _ in cp("g/flash-lite", {"reasoning": {"mandatory": True, "default_effort": "minimal"}}, True)] == ["thinks"])
check("E3 efforts listed with no default_enabled means it thinks (deepseek-v4-flash, 2026-10-15)",
      [k for k, _ in cp("d/v4", {"reasoning": {"mandatory": False, "supported_efforts": ["xhigh", "high"]}})] == ["thinks"])
check("E4 default_enabled false, or switched off by the caller, is fine",
      cp("o/nano", {"reasoning": {"mandatory": False, "default_enabled": False, "supported_efforts": ["none"]}}) == []
      and cp("q/flash", {"reasoning": {"mandatory": False, "default_enabled": True}}, True) == [])
check("E5 a model with no reasoning entry is fine",
      cp("m/small", {"id": "m/small"}) == [] and cp("g/flash", {"reasoning": {"mandatory": False}}) == [])
known_dead = {"openai/gpt-oss-120b:free", "meta-llama/llama-3.3-70b-instruct:free", "google/gemini-2.0-flash-001"}
check("E6 no default OpenRouter chain names a model known to have left the catalogue (2026-10-15)",
      not [m for t in mr.TASKS for m in mr.default_models("openrouter", t) if m in known_dead],
      str({t: mr.default_models("openrouter", t) for t in mr.TASKS}))
check("E7 no default OpenRouter chain names deepseek-v4-pro (all 16,000 tokens thinking, twice, on a scene)",
      not [m for t in mr.TASKS for m in mr.default_models("openrouter", t) if m.startswith("deepseek/deepseek-v4-pro")])
check("E8 the code task asks OpenRouter first when nobody chose an order; other tasks keep Gemini first",
      mr.provider_order("code")[0] == "openrouter" and mr.provider_order("storyboard")[0] == "gemini"
      and mr.provider_order()[0] == "gemini")
os.environ["LLM_PROVIDER_ORDER"] = "groq,gemini,openrouter"
check("E9 an order chosen for every task still decides the code task when no code order is set",
      mr.provider_order("code")[0] == "groq")
os.environ["LLM_PROVIDER_ORDER_CODE"] = "gemini,openrouter"
check("E10 LLM_PROVIDER_ORDER_CODE wins for the code task only",
      mr.provider_order("code") == ["gemini", "openrouter"] and mr.provider_order("general")[0] == "groq")
os.environ.pop("LLM_PROVIDER_ORDER", None)
os.environ.pop("LLM_PROVIDER_ORDER_CODE", None)


failed = [n for n, ok, _ in CHECKS if not ok]
print(f"\n{len(CHECKS) - len(failed)}/{len(CHECKS)} checks passed")
if failed:
    print("FAILED: " + "; ".join(failed))
sys.exit(1 if failed else 0)
