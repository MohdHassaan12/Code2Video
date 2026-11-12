"""Which model writes the lesson script: the Model Choice Protocol (owner's note of 2026-10-12) run on the writer.

    set -a; . ./.env; set +a
    .venv/bin/python scripts/eval_writer.py --run base                      # every candidate on every case
    .venv/bin/python scripts/eval_writer.py --run tuned --models deepseek/deepseek-v3.2:none,qwen/qwen3.8-flash:none

Unit: ONE LESSON SCRIPT, the writer's job end to end (the script, its voice pass, any second asking), every call of a
run on the same model. Cost is reported per script, retries and repairs included.

Test set: ``evals/writer/cases/*.json``, frozen: real briefs with the teaching card and the prepared drawing their
lessons were made from (no source passages: a card carries passage ids only).

A model is named ``provider/model`` (thinking as the provider sets it) or ``provider/model:none`` / ``:low`` (thinking
off / low: the protocol's default is off, and cheap thinking models have spent whole budgets thinking).

Checks in code, free and exact: the script came back whole (``writer.too_little``), the code gates (language, story
setting, pauses, figures, repetition), the length against the budget, the question faults, the voice findings; and how
often the harness had to ask again. Then a JUDGE, a stronger model that never runs in production (its cost kept
apart), scores each script 1 to 5 on five criteria and lists problems with quotes.

Writes ``lessonforge_workspace/evals/writer/<run>/``: every script, every judgement, ``scorecard.csv`` and
``problems.md`` (the judge's problems grouped by model, to read). Nothing here touches a lesson.
"""
from __future__ import annotations

import argparse
import concurrent.futures as futures
import csv
import json
import os
import statistics
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
from lessonforge import paths, spend  # noqa: E402
from lessonforge.engine import llm as engine_llm  # noqa: E402
from lessonforge.harness import card as teaching_card  # noqa: E402
from lessonforge.harness import critic, questions, voice, writer  # noqa: E402

CANDIDATES = ["anthropic/claude-haiku-5.5", "anthropic/claude-haiku-5.5:none", "deepseek/deepseek-v3.2:none", "qwen/qwen3.8-flash:none",
              "google/gemini-3.1-flash-lite:none", "openai/gpt-5.4-nano:none", "z-ai/glm-4.7-flash:none"]
JUDGE = "openai/gpt-5.4-mini:low"
CRITERIA = ("correctness", "teaching", "language", "picture", "economy")

JUDGE_SYSTEM = """You review the SCRIPT of a short narrated school lesson video, as a strict senior teacher would. You get the brief
(topic, class, language, goal, length), the lesson's teaching card (its big idea, the reason, the learners' mistakes),
what the ONE drawing on screen holds, and the script beat by beat: what the voice says, the short lines that come up on
screen, and the question cards.

Score each criterion 1 to 5 (5 = nothing to fix, 4 = small things, 3 = one real fault, 2 = several, 1 = unusable):
- correctness: every fact, number, unit and step of reasoning is right for this class; nothing is stated that is false
  or misleading.
- teaching: one idea, built in a sensible order; it asks before it tells; a question makes the learner predict or decide
  and is not answered in the same breath; a mistake learners make is confronted; the learner can check themselves at
  the end.
- language: the requested language is kept. Hinglish means the conversation is Hindi written in Latin letters, with
  every number and subject term in English; English means plain English for this class. Natural speech, not stiff or
  translated, no English-only stretches in a Hinglish lesson.
- picture: the words speak of what the drawing holds and use it; nothing is said to be on screen that is not there.
- economy: no restating, no filler, close to the asked length; screen lines are short labels, not sentences.

Then list the concrete problems, each with the exact words it is about.

These are NOT problems: numbers written as words (the text is read aloud); screen lines that are short fragments; a
pause after a question; Hinglish in Latin letters; question options of one to three words; "the drawing" or "the
picture" being referred to (one prepared drawing is on screen). SCREEN LINES AND QUESTION CARDS ARE IN ENGLISH ON
PURPOSE, in every lesson, Hinglish ones included: only the VOICE is Hinglish, so judge "language" on the voice alone.
A screen line may name something the voice asks the learner to imagine or to try at home; it is a fault only when the
line or the voice says it is IN the drawing.

Answer in JSON only: {"scores": {"correctness": n, "teaching": n, "language": n, "picture": n, "economy": n},
"problems": [{"criterion": "...", "quote": "...", "what": "..."}]}"""

_LOCK = threading.Lock()


def model_and_thinking(spec: str) -> tuple[str, dict | None]:
    model, _, effort = spec.partition(":")
    return model, ({"effort": effort} if effort else None)


def caller(spec: str, note: str, temperature: float, key: str):
    model, reasoning = model_and_thinking(spec)

    def call(prompt: str, system: str):
        text = engine_llm.call_openrouter(key, prompt, system, temperature=temperature, models=[model], max_tokens=None,
                                          json_object=True, note=note, reasoning=reasoning, timeout=300.0)
        return engine_llm.loads_json_lenient(text)
    return call


def structure(lesson: dict, brief: dict) -> dict:
    """What code can say about one script, free and exact."""
    budget = writer.word_budget(max(3, int(brief.get("duration_minutes") or 3)))
    beats = [b for c in lesson.get("chapters") or [] for b in c.get("beats") or []]
    words = sum(len(str(b.get("narration") or "").split()) for b in beats)
    out = {"chapters": len(lesson.get("chapters") or []), "beats": len(beats), "words": words, "budget": budget,
           "length_ratio": round(words / max(1, budget), 2),
           "whole": not writer.too_little(lesson, 7, budget),
           "language": len(critic.language_gate(lesson)), "setting": len(critic.setting_gate(lesson)),
           "pauses": len(critic.pause_gate(lesson)), "figures": len(critic.figure_gate(lesson)),
           "repetition": len(critic.repetition_gate(lesson)),
           "question_faults": len(questions.faults(lesson)), "voice": len(voice.findings(lesson)),
           "quizzes": sum(1 for b in beats if b.get("quiz"))}
    out["passed"] = bool(out["whole"] and not out["language"] and not out["setting"] and not out["pauses"] and not out["figures"]
                         and out["length_ratio"] <= 1.15)
    return out


def script_text(lesson: dict) -> str:
    lines = []
    for chapter in lesson.get("chapters") or []:
        lines.append(f"\nCHAPTER {chapter.get('id', '')}: {chapter.get('title', '')}")
        for beat in chapter.get("beats") or []:
            lines.append(f"  [beat {beat.get('id')}] VOICE: {beat.get('narration', '')}")
            for step in beat.get("steps") or []:
                lines.append(f"      screen line: {step.get('show', '')}")
            quiz = beat.get("quiz") or {}
            if quiz.get("question"):
                options = quiz.get("options") or []
                right = options[quiz["answer_index"]] if isinstance(quiz.get("answer_index"), int) and 0 <= quiz["answer_index"] < len(options) else "?"
                lines.append(f"      QUESTION CARD: {quiz['question']} options {options} (right: {right})")
    return "\n".join(lines)


def judge_prompt(case: dict, lesson: dict) -> str:
    brief, card = case["brief"], case["card"]
    text = lambda v: str((v or {}).get("text") if isinstance(v, dict) else v or "")       # noqa: E731
    mistakes = "; ".join(str(m.get("mistake") if isinstance(m, dict) else m) for m in card.get("mistakes") or [])
    holds = teaching_card.holds_block(card["diagram"]) if card.get("diagram") else "(no prepared drawing)"
    return (f"BRIEF: topic “{brief.get('topic')}”, for {brief.get('audience') or brief.get('grade')}, language {brief.get('language')}, "
            f"goal: {brief.get('goal')}; about {brief.get('duration_minutes')} minutes, at most {writer.word_budget(int(brief.get('duration_minutes') or 3))} spoken words.\n"
            f"CARD: big idea: {text(card.get('big_idea'))}\nthe reason: {text(card.get('the_why'))}\nlearners' mistakes: {mistakes}\n\n"
            f"THE DRAWING ON SCREEN:\n{holds}\n\nTHE SCRIPT:{script_text(lesson)}")


def rejudge(spec: str, case: dict, run: str, out: Path, key: str, judge: str) -> dict:
    """A script already written in this run, judged again (after the judge was corrected): no writer call is made."""
    name = case["name"]
    row = json.loads((out / "judged" / spec.replace("/", "_").replace(":", "-") / f"{name}.json").read_text(encoding="utf-8")) \
        if (out / "judged" / spec.replace("/", "_").replace(":", "-") / f"{name}.json").is_file() else {"model": spec, "case": name, "failed": "no script"}
    script = out / "scripts" / spec.replace("/", "_").replace(":", "-") / f"{name}.json"
    if row.get("failed") or not script.is_file():
        return row
    lesson = json.loads(script.read_text(encoding="utf-8"))
    try:
        verdict = caller(judge, f"eval-rejudge|{run}|{spec}|{name}", 0.0, key)(judge_prompt(case, lesson), JUDGE_SYSTEM)
        scores = {c: float((verdict.get("scores") or {}).get(c) or 0) for c in CRITERIA}
        row.update({f"j_{c}": scores[c] for c in CRITERIA})
        row["judge"] = round(20 * statistics.mean(scores.values()), 1)
        row["problems"] = [p for p in verdict.get("problems") or [] if isinstance(p, dict)]
        row.pop("judge_failed", None)
    except Exception as exc:  # noqa: BLE001
        row["judge_failed"] = f"{type(exc).__name__}: {str(exc)[:120]}"
    return row


def one(spec: str, case: dict, run: str, out: Path, key: str, judge: str, stage: str = "writer", reviewer: str = "") -> dict:
    name = case["name"]
    note = f"eval-writer|{run}|{spec}|{name}"
    row = {"model": spec, "case": name, "failed": "", "seconds": 0.0, "asked_again": 0}
    said: list[str] = []
    began = time.time()
    try:
        card = json.loads(json.dumps(case["card"]))
        if card.get("diagram"):
            teaching_card.add_holds(card["diagram"], log=lambda *a: None)
        lesson = writer.write_lesson(dict(case["brief"]), caller(spec, note, 0.6, key), log=said.append, card=card)
        if stage == "review":
            # The script as it leaves the text chain of the pipeline: the reviewer reads it and has it revised, and
            # the code gates (language, story setting, length, repetition) get their own rewrites. Same model.
            # ``reviewer``: the pipeline's own pairing (another model reviews), billed under this unit's note.
            verification = critic.verify(lesson, caller(reviewer or spec, note, 0.2, key), log=said.append)
            row["review"] = verification.get("status")
            row["rewritten"] = len(verification.get("beats_rewritten") or [])
    except Exception as exc:  # noqa: BLE001 - a failed call is a result
        row["failed"] = f"{type(exc).__name__}: {str(exc)[:160]}"
        row["seconds"] = round(time.time() - began, 1)
        return row
    row["seconds"] = round(time.time() - began, 1)
    row["asked_again"] = sum(1 for line in said if "asked once more" in line or "chapter by chapter instead" in line)
    row.update(structure(lesson, case["brief"]))
    folder = out / "scripts" / spec.replace("/", "_").replace(":", "-")
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{name}.json").write_text(json.dumps(lesson, indent=1, ensure_ascii=False), encoding="utf-8")
    try:
        verdict = caller(judge, f"eval-judge|{run}|{spec}|{name}", 0.0, key)(judge_prompt(case, lesson), JUDGE_SYSTEM)
        scores = {c: float((verdict.get("scores") or {}).get(c) or 0) for c in CRITERIA}
        row.update({f"j_{c}": scores[c] for c in CRITERIA})
        row["judge"] = round(20 * statistics.mean(scores.values()), 1)
        row["problems"] = [p for p in verdict.get("problems") or [] if isinstance(p, dict)]
    except Exception as exc:  # noqa: BLE001
        row["judge_failed"] = f"{type(exc).__name__}: {str(exc)[:120]}"
    jfolder = out / "judged" / spec.replace("/", "_").replace(":", "-")
    jfolder.mkdir(parents=True, exist_ok=True)
    (jfolder / f"{name}.json").write_text(json.dumps(row, indent=1, ensure_ascii=False), encoding="utf-8")
    return row


def costs(run: str) -> tuple[dict, dict]:
    """USD per (model, case) for the writer's calls and for the judge's, from the ledger (billed figures)."""
    spend.reconcile()
    writes, judged = {}, {}
    for entry in spend.entries():
        note = str(entry.get("note") or "")
        for prefix, table in (("eval-writer|", writes), ("eval-judge|", judged), ("eval-rejudge|", judged)):
            if note.startswith(prefix):
                _, r, spec, case = (note.split(" (discarded")[0].split("|") + ["", "", "", ""])[:4]
                if r == run:
                    table[(spec, case)] = table.get((spec, case), 0.0) + float(entry.get("cost") or 0)
    return writes, judged


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--models", default=",".join(CANDIDATES))
    ap.add_argument("--cases", default="")
    ap.add_argument("--judge", default=JUDGE)
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--rejudge", action="store_true", help="judge this run's scripts again; no writer call")
    ap.add_argument("--stage", choices=("writer", "review"), default="writer",
                    help="the unit: the writer's script, or the script after the review and the code gates (same model)")
    ap.add_argument("--reviewer", default="", help="with --stage review: the model that reviews (default: the writer's own)")
    args = ap.parse_args()
    key = os.environ["OPENROUTER_API_KEY"]
    cases = [json.loads(p.read_text(encoding="utf-8")) for p in sorted((ROOT / "evals" / "writer" / "cases").glob("*.json"))]
    if args.cases:
        cases = [c for c in cases if c["name"] in args.cases.split(",")]
    specs = [s.strip() for s in args.models.split(",") if s.strip()]
    out = paths.home() / "evals" / "writer" / args.run
    out.mkdir(parents=True, exist_ok=True)
    print(f"{len(specs)} model(s) x {len(cases)} case(s); judge {args.judge}; out {out}", flush=True)
    rows = []
    with futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        jobs = {(pool.submit(rejudge, spec, case, args.run, out, key, args.judge) if args.rejudge else
                 pool.submit(one, spec, case, args.run, out, key, args.judge, args.stage, args.reviewer)): (spec, case["name"]) for spec in specs for case in cases}
        for job in futures.as_completed(jobs):
            row = job.result()
            rows.append(row)
            print(f"  {row['model']:36} {row['case']:11} " + (f"FAILED {row['failed']}" if row["failed"] else
                  f"{row.get('words')} words ({row.get('length_ratio')}x) passed={row.get('passed')} judge={row.get('judge')} "
                  f"corr={row.get('j_correctness')} {row['seconds']}s"), flush=True)
    writes, judged = costs(args.run)
    for row in rows:
        row["cost"] = round(writes.get((row["model"], row["case"]), 0.0), 5)
        row["judge_cost"] = round(judged.get((row["model"], row["case"]), 0.0), 5)
    (out / ("rows_rejudged.json" if args.rejudge else "rows.json")).write_text(json.dumps(rows, indent=1, ensure_ascii=False), encoding="utf-8")
    # one row per model, as the protocol's scorecard
    card_rows = []
    for spec in specs:
        mine = [r for r in rows if r["model"] == spec]
        ok = [r for r in mine if not r["failed"] and "judge" in r]
        mean = lambda key: round(statistics.mean(r[key] for r in ok), 2) if ok else None          # noqa: E731
        card_rows.append({"model": spec, "judge_score": mean("judge"), "correctness": mean("j_correctness"),
                          **{c: mean(f"j_{c}") for c in CRITERIA if c != "correctness"},
                          "structural_pass": f"{sum(1 for r in mine if r.get('passed'))}/{len(mine)}",
                          "failed_calls": sum(1 for r in mine if r["failed"]), "asked_again": sum(r.get("asked_again", 0) for r in mine),
                          "length_ratio": mean("length_ratio"), "cost_per_unit_usd": round(statistics.mean(r["cost"] for r in mine), 5) if mine else None,
                          "seconds_per_unit": mean("seconds"), "judge_cost_usd": round(sum(r["judge_cost"] for r in mine), 4)})
    with (out / ("scorecard_rejudged.csv" if args.rejudge else "scorecard.csv")).open("w", newline="", encoding="utf-8") as fh:
        writer_ = csv.DictWriter(fh, fieldnames=list(card_rows[0]))
        writer_.writeheader()
        writer_.writerows(card_rows)
    with (out / ("problems_rejudged.md" if args.rejudge else "problems.md")).open("w", encoding="utf-8") as fh:
        for spec in specs:
            fh.write(f"\n## {spec}\n")
            for r in sorted((r for r in rows if r["model"] == spec), key=lambda r: r["case"]):
                if r["failed"]:
                    fh.write(f"- **{r['case']}** FAILED: {r['failed']}\n")
                for p in r.get("problems") or []:
                    fh.write(f"- **{r['case']}** [{p.get('criterion')}] “{str(p.get('quote'))[:120]}” — {str(p.get('what'))[:200]}\n")
    print("\nmodel, judge, correctness, structural, failed, asked again, length, $/script, s/script")
    for r in sorted(card_rows, key=lambda r: -(r["judge_score"] or 0)):
        print(f"  {r['model']:36} {r['judge_score']} {r['correctness']} {r['structural_pass']} {r['failed_calls']} {r['asked_again']} "
              f"{r['length_ratio']} {r['cost_per_unit_usd']} {r['seconds_per_unit']}")
    print(f"writer calls {sum(r['cost'] for r in rows):.3f} USD, judge {sum(r['judge_cost'] for r in rows):.3f} USD")
    return 0


if __name__ == "__main__":
    sys.exit(main())
