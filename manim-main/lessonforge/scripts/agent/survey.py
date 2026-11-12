"""The same numbers for many lessons at once: is a fault this lesson's, or the system's?

    python scripts/agent/survey.py [--last 20] [--grep WORD] [--json]

One row per finished or failed lesson (newest first), from the same reading as ``dossier.py`` (no frames,
no model, nothing spent). Lessons are read from ``<workspace>/lessons`` (``where`` = ``own``: for the
improver, its own workspace, never in the app's list) and from ``$IMPROVER_LIVE_HOME/lessons`` (``where`` =
``live``: the app's list), each job once. ``--grep`` counts the lessons whose log, critic findings or frame
findings mention a word, so a symptom seen in one dossier can be checked across all of them before anything
is changed (CLAUDE.md: "read all the lessons' records together before blaming one lesson").
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import dossier  # noqa: E402


def lessons(last: int) -> list[tuple[str, Path]]:
    """(where, folder) for the newest ``last`` lessons of both workspaces; a job id found in both is read once (own)."""
    seen, found = set(), []
    for where, folder in dossier.lesson_dirs():
        for p in sorted(folder.glob("*")) if folder.is_dir() else ():
            if (p / "job.json").is_file() and p.name not in seen:
                seen.add(p.name)
                found.append((where, p))
    return sorted(found, key=lambda wp: wp[1].name, reverse=True)[:last]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--last", type=int, default=20)
    ap.add_argument("--grep", default=None, help="count lessons whose records mention this (case-insensitive)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    rows, hits = [], []
    for where, root in lessons(args.last):
        s = dossier.summarise(root)
        if args.grep:
            blob = json.dumps([s["alarms"], s["_unresolved"], s["_vision_detail"], s["_progress_tail"],
                               s["script"]["warnings"]], ensure_ascii=False).lower()
            if args.grep.lower() in blob:
                hits.append(s["job_id"])
        sc, v, c, r = s["script"], s["verify"], s["check"], s["review"]
        rows.append({"job": s["job_id"], "where": where, "title": (s["title"] or "")[:40], "status": s["status"],
                     "lang": (s["brief"] or {}).get("language"), "words": f"{sc['words']}/{sc['target_words']}",
                     "critical": v["critical_unresolved"], "open_findings": v["unresolved_findings"],
                     "scenes": f"{(s['visuals'] or {}).get('made', '-')}/{(s['visuals'] or {}).get('asked', '-')}",
                     "layout": c["layout_counted"], "frame_findings": r["findings"], "alarms": len(s["alarms"]),
                     "usd": (s["spend"] or {}).get("total_usd")})
    if args.json:
        print(json.dumps({"rows": rows, "grep": args.grep, "hits": hits}, indent=1, ensure_ascii=False))
        return 0
    if rows:
        keys = list(rows[0])
        print("| " + " | ".join(keys) + " |\n|" + "---|" * len(keys))
        for row in rows:
            print("| " + " | ".join(str(row[k]) for k in keys) + " |")
        print("\nwhere: own = this workspace (the improver's own, never in the app's list); live = the app's list")
    if args.grep:
        print(f"\n{len(hits)} of {len(rows)} lessons mention {args.grep!r}: {', '.join(hits) or 'none'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
