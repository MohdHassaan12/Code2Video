"""Every default model chain checked against OpenRouter's live catalogue: does each model still exist, does it
think on calls nobody told otherwise, and what does it cost.

    .venv/bin/python scripts/check_models.py            # the defaults as the code has them
    .venv/bin/python scripts/check_models.py --env      # what this process's environment resolves to

CLAUDE.md asks for this by hand before a model is added ("check /api/v1/models … re-check that every model still
EXISTS"); it was not done for the fallbacks, and three of them had gone from the catalogue by 2026-10-15
(``openai/gpt-oss-120b:free``, ``meta-llama/llama-3.3-70b-instruct:free``, ``google/gemini-2.0-flash-001``):
a chain whose fallbacks are dead is a one-model chain that looks like three. Reading the catalogue is free and
needs no key. Exit status 1 when an engine chain has a dead or thinking model, or any chain has a dead one.
"""
from __future__ import annotations

import argparse
import importlib
import json
import sys
import urllib.request

from lessonforge import knobs
from lessonforge.engine import model_routing as mr

CATALOGUE_URLS = ("https://openrouter.ai/api/v1/models?output_modalities=all",)

# Single models the lesson path calls by constant rather than through a knob: (module, attribute).
CONSTANTS = (("lessonforge.harness.vision_review", "JUDGE_MODELS"),
             ("lessonforge.longform.align", "STT_ORDER"),
             ("lessonforge.engine.api.voices", "DEFAULT_GEMINI_TTS_MODEL"))


def catalogue() -> dict:
    found = {}
    for url in CATALOGUE_URLS:
        with urllib.request.urlopen(url, timeout=30) as response:
            for entry in json.load(response).get("data", []):
                found[entry["id"]] = entry
    return found


def chains(from_env: bool) -> list[tuple[str, list[str], str]]:
    """(name, models, engine task or ""): the engine's OpenRouter chains, then every model knob, then constants."""
    out = []
    for task in mr.TASKS:
        models = mr.resolve_models("openrouter", task) if from_env else mr.default_models("openrouter", task)
        out.append((f"engine openrouter/{task}", models, task))
    for control in knobs.CONTROLS:
        if control.group == knobs.MODELS:
            value = knobs.get(control.id, control.default) if from_env else control.default
            out.append((f"harness {control.id}", mr.parse_models(value), ""))
    for module, attribute in CONSTANTS:
        try:
            value = getattr(importlib.import_module(module), attribute)
        except Exception as exc:  # noqa: BLE001
            print(f"  (could not read {module}.{attribute}: {type(exc).__name__})")
            continue
        models = [value] if isinstance(value, str) else list(dict.fromkeys(value))
        out.append((f"constant {module.rsplit('.', 1)[1]}.{attribute}", models, ""))
    return out


def price(entry: dict | None) -> str:
    if not entry:
        return ""
    pricing = entry.get("pricing") or {}
    try:
        return f"${float(pricing.get('prompt', 0)) * 1e6:.2f}/${float(pricing.get('completion', 0)) * 1e6:.2f} per M"
    except (TypeError, ValueError):
        return ""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--env", action="store_true", help="check the chains as this environment resolves them")
    args = ap.parse_args()
    try:
        from lessonforge.engine.llm import thinking_for
    except Exception:  # noqa: BLE001
        thinking_for = lambda model, task="": None  # noqa: E731
    listed = catalogue()
    print(f"{len(listed)} models in the catalogue\n")
    bad = 0
    for name, models, engine in chains(args.env):
        print(name)
        for model in models:
            entry = listed.get(model)
            problems = mr.catalogue_problems(model, entry, switched_off=bool(thinking_for(model, engine)))
            blocking = [k for k, _ in problems if k == "dead" or engine]
            bad += bool(blocking)
            words = "; ".join(why for _, why in problems) or "ok"
            print(f"  {'FAIL' if blocking else 'warn' if problems else 'ok  '}  {model:44} {price(entry):24} {words}")
    print(f"\n{bad} problem(s) that must be fixed" if bad else "\nno dead model, no thinking model in an engine chain")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
