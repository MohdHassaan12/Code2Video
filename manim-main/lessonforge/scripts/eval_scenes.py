"""Which model writes a lesson's animated scenes: the Model Choice Protocol run on ``engine/sim_gen.py``.

    set -a; . ./.env; set +a
    .venv/bin/python scripts/eval_scenes.py --run base                      # every candidate on every case
    .venv/bin/python scripts/eval_scenes.py --run quick --models deepseek/deepseek-v4-flash,qwen/qwen3.8-flash:none

Why this job: model-written scenes were about two thirds of a lesson's cost when a lesson had them (CLAUDE.md,
2026-10-09: 0.51 of 0.77 USD), and they go through the engine's ``code`` chain, whose OpenRouter default had never
been measured against anything cheaper.

Unit: ONE SCENE, the writer's job end to end exactly as ``sim_gen.generate_simulation`` does it: the prompt with the
installed-Manim context, the security gate, ``verify`` (a real manim subprocess: it draws, it moves, it stays in its
box, its labels do not collide, something is on screen at the start) and ``REPAIR_ROUNDS`` repair rounds carrying the
real error. Each call is a single model, so a failure is that model's, not the chain's next entry.

Test set: ``evals/scenes/cases.json``, frozen: scene descriptions of the kinds lessons ask for (motion, growth,
stages "first … then …", a count, a labelled measurement), passed through ``service.scene_brief`` as a lesson does.

A model is named ``provider/model`` (thinking as the provider sets it), ``provider/model:none`` / ``:low`` (an effort),
or ``provider/model:off`` (``reasoning: {"enabled": false}``: OpenRouter's documented switch, which reaches models such
as ``deepseek/deepseek-v4-flash`` whose effort list is only "xhigh" and "high").

No judge: ``verify`` is the gate a lesson applies, and it is free and exact. It cannot tell a correct picture from
a tidy wrong one, so ``--stills`` saves the first and last frame of every verified scene under the run folder to be
LOOKED at before a model is promoted (the 2026-08-15 lesson: a metric that stops at the code will lie about the video).

Writes ``lessonforge_workspace/evals/scenes/<run>/``: every scene's code, ``rows.json``, ``scorecard.csv``,
``failures.md``. Nothing here touches a lesson or the scene cache.
"""
from __future__ import annotations

import argparse
import concurrent.futures as futures
import csv
import json
import os
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
from lessonforge import paths, spend  # noqa: E402
from lessonforge.engine import llm as engine_llm  # noqa: E402
from lessonforge.engine import manim_context, sim_gen  # noqa: E402
from lessonforge.harness import service  # noqa: E402

# The default code chain's first model, then cheaper ones. Thinking off (":none") only where the model allows it.
CANDIDATES = ["deepseek/deepseek-v4-pro", "deepseek/deepseek-v4-flash", "deepseek/deepseek-v3.2:none",
              "qwen/qwen3.8-flash:none", "qwen/qwen3-coder-next", "google/gemini-2.5-flash",
              "anthropic/claude-haiku-5.5", "openai/gpt-5.4-nano:none", "z-ai/glm-4.7-flash:none"]

_STILL = """
from manim import *
import numpy as np
{code}

class Still(Scene):
    def construct(self):
        g = build({w}, {h})
        frame = Rectangle(width={w}, height={h}, stroke_color=GREY_D, stroke_width=1)
        self.add(frame, g)
        anim = animate(g, 2.0)
        anim.begin()
        anim.interpolate({alpha})
"""


def model_and_thinking(spec: str) -> tuple[str, dict | None]:
    model, _, effort = spec.partition(":")
    if effort == "off":  # OpenRouter's unified switch, for models whose effort list has no "none" (deepseek-v4-*)
        return model, {"enabled": False}
    return model, ({"effort": effort} if effort else None)


def save_stills(code: str, out: Path) -> None:
    """The scene at its start and its end, as a lesson would show them: for a person to look at."""
    for name, alpha in (("start", 0.0), ("end", 0.999)):
        with tempfile.TemporaryDirectory() as work:
            src = Path(work) / "still.py"
            src.write_text(_STILL.format(code=code, w=sim_gen.BOX_W, h=sim_gen.BOX_H, alpha=alpha), encoding="utf-8")
            subprocess.run([sys.executable, "-m", "manim", "-s", "-ql", "--disable_caching", "-o", "still",
                            "--media_dir", work, str(src), "Still"], cwd=work, capture_output=True, timeout=120)
            found = list(Path(work).rglob("still*.png"))
            if found:
                (out.parent / f"{out.stem}_{name}.png").write_bytes(found[0].read_bytes())


def one(spec: str, case: dict, run: str, out: Path, key: str, stills: bool) -> dict:
    model, reasoning = model_and_thinking(spec)
    brief = service.scene_brief(case["describe"])
    prompt = sim_gen._PROMPT.format(description=brief, context=manim_context.context_for(brief))
    row = {"model": spec, "case": case["name"], "attempts": 0, "first_try": False, "passed": False, "failed": "",
           "errors": []}
    started = time.time()
    code, error = "", ""
    for attempt in range(1 + max(0, sim_gen.REPAIR_ROUNDS)):
        row["attempts"] = attempt + 1
        text, problem = None, ""
        for wait in (0, 15, 45):  # an upstream rate limit is the provider's, not the model's: wait and ask again
            time.sleep(wait)
            try:
                text = engine_llm.call_openrouter(
                    key, prompt if attempt == 0 else sim_gen._REPAIR.format(error=error, code=code),
                    sim_gen._SYSTEM, temperature=0.2, models=[model], max_tokens=16000,
                    note=f"eval-scene|{run}|{spec}|{case['name']}", reasoning=reasoning, timeout=240.0)
                break
            except Exception as exc:  # noqa: BLE001
                problem = f"{type(exc).__name__}: {str(exc)[:160]}"
                if "429" not in problem:
                    break
        if text is None:
            row["failed"] = problem
            break
        code = engine_llm.strip_code_fences(text or "")
        if not code.strip():
            row["failed"] = "no code returned"
            break
        unsafe = sim_gen._unsafe_code(code)
        if unsafe:  # never retried in production either
            row["failed"] = f"refused: {unsafe}"
            break
        error = sim_gen.verify(code)
        if error is None:
            row["passed"] = True
            row["first_try"] = attempt == 0
            break
        row["errors"].append(error[:300])
    row["seconds"] = round(time.time() - started, 1)
    target = out / spec.replace("/", "__").replace(":", "_") / f"{case['name']}.py"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(code or "", encoding="utf-8")
    if stills and row["passed"]:
        save_stills(code, target)
    return row


def costs(run: str) -> dict:
    """USD per (model, case) from the ledger (billed figures, discarded answers included)."""
    spend.reconcile()
    table: dict = {}
    for entry in spend.entries():
        note = str(entry.get("note") or "")
        if note.startswith("eval-scene|"):
            _, r, spec, case = (note.split(" (discarded")[0].split("|") + ["", "", "", ""])[:4]
            if r == run:
                table[(spec, case)] = table.get((spec, case), 0.0) + float(entry.get("cost") or 0)
    return table


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--models", default=",".join(CANDIDATES))
    ap.add_argument("--cases", default="")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--stills", action="store_true", help="save the first and last frame of every verified scene")
    args = ap.parse_args()
    key = os.environ["OPENROUTER_API_KEY"]
    cases = json.loads((ROOT / "evals" / "scenes" / "cases.json").read_text(encoding="utf-8"))
    if args.cases:
        cases = [c for c in cases if c["name"] in args.cases.split(",")]
    specs = [s.strip() for s in args.models.split(",") if s.strip()]
    out = paths.home() / "evals" / "scenes" / args.run
    out.mkdir(parents=True, exist_ok=True)
    print(f"{len(specs)} model(s) x {len(cases)} case(s); out {out}", flush=True)
    rows = []
    with futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        jobs = [pool.submit(one, spec, case, args.run, out, key, args.stills) for spec in specs for case in cases]
        for job in futures.as_completed(jobs):
            row = job.result()
            rows.append(row)
            print(f"  {row['model']:34} {row['case']:16} "
                  + (f"FAILED {row['failed']}" if row["failed"] else
                     f"{'pass' if row['passed'] else 'FAIL'} in {row['attempts']} {row['seconds']}s"), flush=True)
    billed = costs(args.run)
    for row in rows:
        row["cost"] = round(billed.get((row["model"], row["case"]), 0.0), 5)
    (out / "rows.json").write_text(json.dumps(rows, indent=1, ensure_ascii=False), encoding="utf-8")
    card_rows = []
    for spec in specs:
        mine = [r for r in rows if r["model"] == spec]
        passed = sum(r["passed"] for r in mine)
        total = sum(r["cost"] for r in mine)
        card_rows.append({"model": spec, "passed": f"{passed}/{len(mine)}",
                          "first_try": f"{sum(r['first_try'] for r in mine)}/{len(mine)}",
                          "failed_calls": sum(1 for r in mine if r["failed"]),
                          "cost_per_scene_usd": round(total / len(mine), 5) if mine else None,
                          "cost_per_passed_scene_usd": round(total / passed, 5) if passed else None,
                          "seconds_per_scene": round(statistics.mean(r["seconds"] for r in mine), 1) if mine else None})
    with (out / "scorecard.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(card_rows[0]))
        w.writeheader()
        w.writerows(card_rows)
    with (out / "failures.md").open("w", encoding="utf-8") as fh:
        for spec in specs:
            fh.write(f"\n## {spec}\n")
            for r in sorted((r for r in rows if r["model"] == spec), key=lambda r: r["case"]):
                if r["failed"] or not r["passed"]:
                    fh.write(f"- **{r['case']}** {r['failed'] or 'not verified'}: " + " | ".join(r["errors"])[:600] + "\n")
    print("\nmodel, passed, first try, failed calls, $/scene, $/passed scene, s/scene")
    for r in sorted(card_rows, key=lambda r: (-int(r["passed"].split("/")[0]), r["cost_per_scene_usd"] or 0)):
        print(f"  {r['model']:34} {r['passed']:6} {r['first_try']:6} {r['failed_calls']} "
              f"{r['cost_per_scene_usd']} {r['cost_per_passed_scene_usd']} {r['seconds_per_scene']}")
    print(f"scene calls {sum(r['cost'] for r in rows):.3f} USD")
    return 0


if __name__ == "__main__":
    sys.exit(main())
