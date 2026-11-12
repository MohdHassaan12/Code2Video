"""How good is the owner's drawing service? A free, repeatable test run against its real API.

    set -a; . ./.env; set +a                      # DIAGRAM_API_URL and DIAGRAM_API_KEY
    python scripts/eval_diagrams.py --run base                    # every case once
    python scripts/eval_diagrams.py --run twice --repeat 2        # every case twice: is the answer the same?
    python scripts/eval_diagrams.py --run some --cases mirror_35,series_circuit

Why: lessons take their prepared pictures from this service (``harness/diagrams.py``), and its own verdict
(``quality``) is what ``DIAGRAM_MIN_QUALITY`` trusts. On 2026-10-20 that verdict passed a mirror drawn at 55° under a
"35°" label, a lens drawn for the wrong case and a free-body diagram with no values, and failed two correct
attention diagrams. So the verdict is recorded here beside what code can check, and the run is LOOKED at.

Unit: ONE REQUEST as ``diagrams.fetch`` sends it (``POST /v1/diagrams?wait=90``, then poll), with ``labels`` on and
the case's class and subject. No model is asked anything by this script, and nothing touches a lesson or the
drawing library.

What code checks, per answer:
  * the service's status, verdict, reason and time (and our own wall time, with queueing);
  * the SVG is XML with an ``<svg>`` root and a ``viewBox``, passes ``diagrams.safe`` (scripts, outside links,
    size: a 15 MB ice lattice is refused there) and is under ``MAX_SVG_BYTES``;
  * the case's ``must_say`` words and ``numbers`` are in the drawing's text. A typeset drawing writes its words as
    glyph outlines (``<use>``), which code cannot read: those are reported "typeset" and left for the look;
  * a STORED answer: under 2 seconds, or byte for byte the same SVG on a repeat. Such an answer was made for an
    earlier request and can ignore what this one asks (the lens case came back for the wrong object distance).

What code cannot check (``look_for`` in each case says what to look at): whether an angle is drawn at its label,
which way arrows turn, whether labels overlap. ``sheet.jpg`` puts every drawing on one page for that look; record
what you saw in ``evals/diagrams/looked-<date>.csv``.

Writes ``lessonforge_workspace/evals/diagrams/<run>/``: each answer's ``.svg``, ``.png`` and ``.json``,
``rows.json``, ``scorecard.csv`` and ``sheet.jpg``.
"""
from __future__ import annotations

import argparse
import base64
import concurrent.futures as futures
import csv
import hashlib
import json
import os
import re
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from lessonforge import paths  # noqa: E402
from lessonforge.harness import diagrams  # noqa: E402

CASES = ROOT / "evals" / "diagrams" / "cases.json"
STORED_SECONDS = 2.0          # the service does not draw anything new this fast


def _ask(base: str, key: str, body: dict, poll_for: float = 150.0) -> tuple[dict, float]:
    import requests  # noqa: PLC0415
    began = time.time()
    headers = {"X-API-Key": key} if key else {}
    reply = requests.post(f"{base}/v1/diagrams", params={"wait": 90}, json=body, headers=headers, timeout=130)
    if reply.status_code != 200 and reply.status_code != 202:
        return {"status": "http_error", "detail": f"HTTP {reply.status_code}: {reply.text[:160]}"}, time.time() - began
    out = reply.json()
    while out.get("status") in ("queued", "running") and time.time() - began < poll_for:
        time.sleep(4)
        out = requests.get(f"{base}/v1/diagrams/{out['id']}", headers=headers, timeout=60).json()
    return out, time.time() - began


def _words(root: ET.Element) -> str:
    """Every word the SVG writes as text (``<text>`` and its ``<tspan>``s), lower case."""
    found = []
    for el in root.iter():
        if el.tag.split("}")[-1] == "text":
            found.append(" ".join(t for t in el.itertext()))
    return re.sub(r"\s+", " ", " ".join(found)).lower()


def _numbers(text: str) -> set[str]:
    return {n.lstrip("+") for n in re.findall(r"[-+]?\d+(?:\.\d+)?", text.replace("−", "-"))}


def check(svg: bytes, case: dict) -> dict:
    """What code can say about one SVG answer."""
    out: dict = {"kb": len(svg) // 1024, "sha": hashlib.sha1(svg).hexdigest()[:10],
                 "refused": diagrams.safe(svg) or "", "too_big": len(svg) > diagrams.MAX_SVG_BYTES}
    try:
        root = ET.fromstring(svg)
    except ET.ParseError as exc:
        return {**out, "valid": False, "error": str(exc)[:80]}
    tags = [el.tag.split("}")[-1] for el in root.iter()]
    words = _words(root)
    typeset = tags.count("use") > 0 and not words.strip()
    out.update(valid=tags[0] == "svg", viewBox=bool(root.get("viewBox")), elements=len(tags),
               text_words=len(words.split()), typeset=typeset)
    if typeset:
        out.update(missing_words="typeset", missing_numbers="typeset")
    else:
        flat = words.replace("₂", "2").replace("₄", "4")
        out["missing_words"] = ", ".join(w for w in case.get("must_say", []) if w.lower() not in flat)
        have = _numbers(flat)
        out["missing_numbers"] = ", ".join(n for n in case.get("numbers", []) if n.lstrip("+") not in have)
    return out


def run_one(case: dict, take: int, base: str, key: str, folder: Path) -> dict:
    body = {"prompt": case["prompt"], "labels": True, "language": "en", "min_quality": "any",
            "class_level": int(case["class"]), "subject": case["subject"]}
    name = f"{case['id']}-{take}"
    try:
        answer, wall = _ask(base, key, body)
    except Exception as exc:  # noqa: BLE001 - a run records every failure and goes on
        answer, wall = {"status": "error", "detail": str(exc)[:160]}, 0.0
    row = {"case": case["id"], "take": take, "status": answer.get("status"), "quality": answer.get("quality"),
           "reason": answer.get("reason") or answer.get("error") or answer.get("detail") or "", "visual_type": answer.get("visual_type"),
           "service_seconds": answer.get("seconds"), "wall_seconds": round(wall, 1), "look_for": case.get("look_for", "")}
    svg = (answer.get("svg") or "").encode()
    if svg:
        (folder / f"{name}.svg").write_bytes(svg)
        row.update(check(svg, case))
    if answer.get("png_base64"):
        (folder / f"{name}.png").write_bytes(base64.b64decode(answer["png_base64"]))
    row["stored"] = bool(svg) and (answer.get("seconds") or 99) < STORED_SECONDS
    (folder / f"{name}.json").write_text(json.dumps({k: v for k, v in answer.items() if k not in ("svg", "png_base64")}, indent=1))
    print(f"{name}: {row['status']} {row['quality']} {row.get('service_seconds')} s"
          f"{'  missing: ' + row['missing_words'] if row.get('missing_words') else ''}", flush=True)
    return row


def sheet(rows: list[dict], folder: Path) -> None:
    try:
        from PIL import Image, ImageDraw  # noqa: PLC0415
    except ImportError:
        return
    tiles = []
    for row in rows:
        png = folder / f"{row['case']}-{row['take']}.png"
        if not png.is_file():
            continue
        im = Image.open(png).convert("RGB")
        im.thumbnail((600, 400))
        tile = Image.new("RGB", (620, 450), "white")
        ImageDraw.Draw(tile).text((8, 6), f"{row['case']}-{row['take']}  {row['quality']}  {row.get('service_seconds')} s", fill="black")
        ImageDraw.Draw(tile).text((8, 22), f"look for: {row['look_for'][:90]}", fill="#555")
        tile.paste(im, (10, 42))
        tiles.append(tile)
    if not tiles:
        return
    cols = 3
    page = Image.new("RGB", (620 * cols, 450 * ((len(tiles) + cols - 1) // cols)), (230, 230, 230))
    for i, tile in enumerate(tiles):
        page.paste(tile, ((i % cols) * 620, (i // cols) * 450))
    page.save(folder / "sheet.jpg", quality=85)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--run", required=True)
    ap.add_argument("--cases", default="", help="comma-separated case ids (default: all)")
    ap.add_argument("--repeat", type=int, default=1)
    ap.add_argument("--workers", type=int, default=3, help="requests at once (the service queues beyond this)")
    args = ap.parse_args()
    base, key = diagrams.service_url(), diagrams.service_key()
    if not base:
        sys.exit("Set DIAGRAM_API_URL (and DIAGRAM_API_KEY) first.")
    cases = json.loads(CASES.read_text())
    if args.cases:
        wanted = set(args.cases.split(","))
        cases = [c for c in cases if c["id"] in wanted]
    folder = paths.sub("evals", "diagrams", args.run)
    folder.mkdir(parents=True, exist_ok=True)
    jobs = [(c, t) for t in range(1, args.repeat + 1) for c in cases]
    with futures.ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        rows = list(pool.map(lambda job: run_one(job[0], job[1], base, key, folder), jobs))
    by_case: dict[str, set] = {}
    for row in rows:
        if row.get("sha"):
            by_case.setdefault(row["case"], set()).add(row["sha"])
    for row in rows:
        if args.repeat > 1 and len(by_case.get(row["case"], ())) == 1:
            row["stored"] = True                      # the same bytes every time: not drawn for this request
    (folder / "rows.json").write_text(json.dumps(rows, indent=1))
    fields = ["case", "take", "status", "quality", "reason", "visual_type", "service_seconds", "wall_seconds", "stored",
              "valid", "viewBox", "refused", "too_big", "kb", "typeset", "text_words", "missing_words", "missing_numbers",
              "look_for"]
    with open(folder / "scorecard.csv", "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    sheet(rows, folder)
    done = [r for r in rows if r.get("sha")]
    ready = [r for r in done if r.get("quality") == "student_ready"]
    times = sorted(r["service_seconds"] for r in done if r.get("service_seconds") is not None)
    print(f"\n{len(done)}/{len(rows)} answered with a drawing; {len(ready)} rated student_ready by the service; "
          f"{sum(1 for r in done if r.get('stored'))} stored answers; "
          f"{sum(1 for r in done if r.get('refused') or r.get('too_big'))} refused by diagrams.safe; "
          f"median {times[len(times) // 2] if times else '-'} s. Now LOOK at {folder / 'sheet.jpg'}.")


if __name__ == "__main__":
    main()
