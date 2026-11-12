"""Free test of library components through the components kit: no model, no key, no cost.

For each component (all in scope, or the ids given): load it through the kit, turn each of its ready-made situations into
lesson beats (``situation_to_beats``: code only), settle the lesson with the kit (every figure accepted or refused by code),
and report any issue. Optionally write one lesson JSON per situation, ready for ``workbench.add`` / ``film``.

    LESSON_VISUALS_DIR=/path/to/lesson-visuals PYTHONPATH=src python scripts/components_suite.py [--ids a,b] [--subject maths]
        [--out DIR]          # write <id>__<situation>.json lessons (title = the situation's own title)
Exit 1 when a component is not loadable or a situation has an issue.

Filming one of the written lessons (free local voice, no paid key):
    from lessonforge.harness import workbench as W
    r = W.film(W.add(lesson, "name")["lesson_id"], quality="m", wait=True)   # LESSONFORGE_COMPONENT_TWEEN=1 and _TIGHT=1 as in the proofs
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

os.environ.setdefault("LESSONFORGE_NO_DOTENV", "1")   # never load .env (it holds paid keys)

from lessonforge.kits import components as C  # noqa: E402
from lessonforge.longform import component_lib as lib  # noqa: E402


def lesson_of(cid: str, situation: str) -> tuple[dict, list[dict]]:
    """(lesson dict, beats) for one situation of one component."""
    entry = lib.get(cid)
    title = lib.get_situation(entry, situation).get("title") or situation.replace("_", " ")
    beats = C.situation_to_beats(cid, situation)
    for i, b in enumerate(beats, 1):
        b["id"] = f"{i:02}"
    return {"title": title, "chapters": [{"id": 1, "title": entry["title"], "learning_goal": title, "role": "explain",
                                          "beats": beats}]}, beats


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--ids", default="", help="comma-separated component ids (default: every component in scope)")
    ap.add_argument("--subject", default="", help="only this subject folder, e.g. maths")
    ap.add_argument("--out", default="", help="write one lesson JSON per situation into this folder")
    a = ap.parse_args(argv)
    broken = lib.broken()
    if broken:
        print("not loadable:", json.dumps(broken, indent=1)[:1500])
    cat = {e["id"]: e for e in lib.catalogue()}
    ids = [i for i in a.ids.split(",") if i] or sorted(i for i, e in cat.items() if not a.subject or e["subject"] == a.subject)
    out = Path(a.out) if a.out else None
    if out:
        out.mkdir(parents=True, exist_ok=True)
    kit = C._kit()
    total = bad = 0
    for cid in ids:
        if cid not in cat:
            print(f"{cid}: not in the catalogue (in scope)")
            bad += 1
            continue
        raw = lib.get(cid).get("situations") or {}
        for sit in sorted(raw if isinstance(raw, dict) else (x["name"] if isinstance(x, dict) else x for x in raw)):
            total += 1
            try:
                lesson, beats = lesson_of(cid, sit)
                issues = kit.settle(json.loads(json.dumps(lesson)))[1]
            except Exception as exc:  # noqa: BLE001 - a situation the kit refuses is a finding, not a crash
                lesson, beats, issues = None, [], [f"{type(exc).__name__}: {exc}"]
            if issues:
                bad += 1
                print(f"FAIL {cid}/{sit}: {issues[:3]}")
            if out and lesson:
                (out / f"{cid}__{sit}.json").write_text(json.dumps(lesson, indent=1))
    print(f"{total} situations over {len(ids)} components; {bad} problem(s); {len(broken)} file(s) not loadable")
    return 1 if (bad or broken) else 0


if __name__ == "__main__":
    sys.exit(main())
