"""Regression test for the frame: preview every finished lesson as stills with the renderer AS IT STANDS in this tree and
compare what is found with what was found the last time the frame was accepted.

    .venv/bin/python scripts/layout_regress.py                 every finished lesson in the workspace (about a quarter of an hour)
    .venv/bin/python scripts/layout_regress.py --only 12       the 12 newest
    .venv/bin/python scripts/layout_regress.py --update        ... and keep this run as the baseline
    .venv/bin/python scripts/layout_regress.py --as LESSONFORGE_WORKING=column     with a look forced, to compare two looks
    PYTHONPATH=<abs path of a source copy> .venv/bin/python scripts/layout_regress.py      a scratch copy's renderer

Run it BEFORE a change to ``longform/runtime.py`` or ``figures.py`` goes into ``src`` (on the scratch copy), and after.
Nothing is asked of a model, nothing is spent and no lesson is written to: each lesson gets a light copy of its
``lesson.json`` and timeline under ``<workspace>/layout_regress/``. A lesson that says how it looks is previewed that
way; one that does not (made before 2026-10-10) is previewed in the look a lesson made now gets, because that is the
frame a change is about to touch.

A lesson REGRESSES when it has more of these than in the baseline: chapters that could not be previewed, notes from
the renderer, things outside the stage, collisions the layout probe counts. Exit status 1 when any lesson does.
The table printed at the end is the frame in numbers (how many lines of words are under 30, 38, 44 points; how beats
are laid out), so a change that is not a regression can still be seen for what it does.
"""
from __future__ import annotations

import argparse
import collections
import json
import shutil
import sys
import time
from pathlib import Path

from lessonforge import paths
from lessonforge.longform import look, preview


def row_of(result: dict, lesson: dict) -> dict:
    ends = [s for s in result["stills"] if s["what"] == "end"]
    return {"title": lesson.get("title"), "look": lesson.get("look"), "seconds": result["seconds"], "stills": len(result["stills"]),
            "failed": result["failed"], "notes": result["notes"], "bounds": len(result["bounds"]),
            "layout_counted": sum(1 for item in result["layout"] if item.get("counted")), "faults": preview.faults(result),
            "findings": result["findings"],
            "beats": {s["beat"]: {"layout": s.get("layout"), "picture": s.get("picture"),
                                  "lines": [line.get("points") for line in s.get("lines") or []]} for s in ends}}


def numbers(rows: dict) -> collections.Counter:
    out, points = collections.Counter(), []
    for row in rows.values():
        out["lessons"] += 1
        out["faults (not previewed, notes, outside the stage, counted collisions)"] += int(row.get("faults") or 0)
        for finding in row.get("findings") or []:
            out[f"measured: {finding['kind']}"] += 1
        for beat in (row.get("beats") or {}).values():
            layout = beat.get("layout") or {}
            out[f"beats laid out {layout.get('mode')}/{layout.get('words')}"] += 1
            points += [p for p in beat.get("lines") or [] if p]
    points.sort()
    out["lines of words"] = len(points)
    for limit in (30, 38, 44):
        out[f"lines of words under {limit} points"] = sum(1 for p in points if p < limit - .5)
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--only", type=int, default=0, help="the N newest lessons only")
    parser.add_argument("--update", action="store_true", help="keep this run as the baseline")
    parser.add_argument("--as", dest="forced", action="append", default=[], metavar="KEY=VALUE", help="force a look for this run")
    parser.add_argument("--baseline", default=str(paths.home() / "layout_baseline.json"))
    parser.add_argument("--jobs", type=int, default=8)
    args = parser.parse_args()
    env = dict(item.split("=", 1) for item in args.forced if "=" in item)
    folders = sorted(f for f in (paths.home() / "lessons").iterdir() if (f / "lesson.json").is_file() and (f / "timeline.json").is_file())
    folders = folders[-args.only:] if args.only else folders
    work, rows, began = paths.home() / "layout_regress", {}, time.time()
    for folder in folders:
        lesson = json.loads((folder / "lesson.json").read_text(encoding="utf-8"))
        if not isinstance(lesson.get("look"), dict):
            lesson["look"] = look.for_new(lesson, environ={})
        copy = work / folder.name
        shutil.rmtree(copy, ignore_errors=True)
        copy.mkdir(parents=True)
        shutil.copy2(folder / "timeline.json", copy / "timeline.json")
        for script in folder.glob("chapters_*.py"):
            shutil.copy2(script, copy / script.name)
        (copy / "lesson.json").write_text(json.dumps(lesson, ensure_ascii=False), encoding="utf-8")
        try:
            result = preview.stills(copy, env=env, jobs=args.jobs, log=lambda *a: None)
            rows[folder.name] = row_of(result, lesson)
        except Exception as exc:  # noqa: BLE001 - one lesson that cannot be previewed is a finding, not the end of the run
            rows[folder.name] = {"title": lesson.get("title"), "failed": ["all"], "notes": [f"{type(exc).__name__}: {str(exc)[:160]}"], "faults": 99}
        row = rows[folder.name]
        print(f"{folder.name}  {row.get('seconds', 0):4.0f} s  {row.get('stills', 0):3} stills  faults {row.get('faults')}  | {str(row.get('title'))[:44]}", flush=True)
        shutil.rmtree(copy / "media", ignore_errors=True)
    baseline_path = Path(args.baseline)
    before = json.loads(baseline_path.read_text(encoding="utf-8")) if baseline_path.is_file() else {}
    worse = [(name, before[name].get("faults", 0), row["faults"]) for name, row in rows.items() if name in before and row["faults"] > before[name].get("faults", 0)]
    now, was = numbers(rows), numbers({name: before[name] for name in rows if name in before})
    print(f"\n{'':70}{'baseline':>10}{'this run':>10}")
    for key in sorted(set(now) | set(was)):
        print(f"{key:70}{was.get(key, 0) if before else '-':>10}{now.get(key, 0):>10}")
    print(f"\n{len(rows)} lessons previewed in {time.time() - began:.0f} s; "
          + (f"{len(worse)} with MORE faults than in the baseline" if before else "no baseline to compare with (run with --update to keep one)"))
    for name, a, b in worse:
        row = rows[name]
        print(f"   {name}: {a} -> {b}  failed {row.get('failed')}  outside {row.get('bounds')}  counted {row.get('layout_counted')}  | {str(row.get('title'))[:40]}")
        for note in (row.get("notes") or [])[:3]:
            print(f"        {note[:170]}")
    if args.update:
        baseline_path.write_text(json.dumps({**before, **rows}, indent=1, ensure_ascii=False), encoding="utf-8")
        print(f"kept as the baseline: {baseline_path}")
    return 1 if worse else 0


if __name__ == "__main__":
    sys.exit(main())
