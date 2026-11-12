"""Before and after: two dossiers (and the agent's frame reviews, when present) side by side.

    python scripts/agent/compare.py <before dossier dir> <after dossier dir> [--json]

Prints one table, a verdict per metric (better / worse / same) and an overall call:
  KEEP     nothing measured got worse and at least one thing got better
  REVERT   something got worse that the change was not meant to trade (or the lesson failed)
  UNSURE   no metric moved: the change did not show on this lesson

A metric is only compared when both sides have it. The agent's own frame review
(``agent_review.json`` in the dossier folder, written by the frame-reviewer subagent) counts the most:
it is the only measure here that looks at whether the picture matches the words.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _load(folder: str) -> tuple[dict, dict | None]:
    root = Path(folder)
    d = json.loads((root / "dossier.json").read_text(encoding="utf-8"))
    review = root / "agent_review.json"
    return d, (json.loads(review.read_text(encoding="utf-8")) if review.is_file() else None)


def _agent(review: dict | None) -> dict:
    if not review:
        return {}
    beats = review.get("beats") or []
    scores = [b.get("score") for b in beats if isinstance(b.get("score"), (int, float))]
    issues = [i for b in beats for i in b.get("issues") or []]
    return {"agent_mean_score": round(sum(scores) / len(scores), 2) if scores else None,
            "agent_bad_beats": sum(1 for s in scores if s <= 1),
            "agent_issues": len(issues),
            "agent_major_issues": sum(1 for i in issues if i.get("severity") == "major")}


def metrics(d: dict, review: dict | None) -> dict:
    script, ver, chk, rev = d.get("script") or {}, d.get("verify") or {}, d.get("check") or {}, d.get("review") or {}
    words, target = script.get("words"), script.get("target_words")
    vis = d.get("visuals") or {}
    align = (d.get("speech") or {}).get("alignment") or {}
    m = {
        "done": 1 if d.get("status") == "done" else 0,
        "length_off_budget_pct": round(abs(words / target - 1) * 100, 1) if words and target else None,
        "critical_unresolved": ver.get("critical_unresolved"),
        "unresolved_findings": ver.get("unresolved_findings"),
        "claims_failed": ver.get("claims_failed"),
        "scenes_failed": (vis.get("asked", 0) - vis.get("made", 0)) if vis else None,
        "layout_counted": chk.get("layout_counted"),
        "bounds_violations": chk.get("bounds_violations"),
        "failed_checks": len(chk.get("failed_checks") or []) if chk.get("status") else None,
        "pipeline_frame_findings": rev.get("findings"),
        "alarms_in_log": len(d.get("alarms") or []),
        "word_match_rate": align.get("word_match_rate") if isinstance(align, dict) else None,
        "cost_usd": (d.get("spend") or {}).get("total_usd"),
    }
    m.update(_agent(review))
    return m


HIGHER_IS_BETTER = {"done", "word_match_rate", "agent_mean_score"}
NOT_JUDGED = {"cost_usd"}          # reported, never a reason to keep or revert on its own
WEIGHT = {"agent_mean_score": 3, "agent_major_issues": 3, "done": 5, "critical_unresolved": 2}


def compare(a: dict, b: dict) -> dict:
    rows, better, worse = [], 0, 0
    for k in a:
        x, y = a.get(k), b.get(k)
        if x is None or y is None:
            rows.append((k, x, y, "n/a"))
            continue
        if x == y or k in NOT_JUDGED:
            rows.append((k, x, y, "same" if x == y else "info"))
            continue
        up = y > x
        good = up if k in HIGHER_IS_BETTER else not up
        rows.append((k, x, y, "better" if good else "WORSE"))
        if good:
            better += WEIGHT.get(k, 1)
        else:
            worse += WEIGHT.get(k, 1)
    verdict = "REVERT" if worse or not b.get("done") else ("KEEP" if better else "UNSURE")
    return {"rows": rows, "better": better, "worse": worse, "verdict": verdict}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("before")
    ap.add_argument("after")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    (da, ra), (db, rb) = _load(args.before), _load(args.after)
    result = compare(metrics(da, ra), metrics(db, rb))
    if args.json:
        print(json.dumps(result, indent=1))
        return 0
    print(f"before: {da.get('job_id')}  ({da.get('code_from')})")
    print(f"after:  {db.get('job_id')}  ({db.get('code_from')})\n")
    print(f"| metric | before | after | |\n|---|---|---|---|")
    for k, x, y, v in result["rows"]:
        print(f"| {k} | {x} | {y} | {v} |")
    print(f"\nverdict: {result['verdict']}  (better weight {result['better']}, worse weight {result['worse']})")
    if not (ra and rb):
        print("note: an agent frame review is missing on one side; the picture-vs-words score was not compared")
    return 0


if __name__ == "__main__":
    sys.exit(main())
