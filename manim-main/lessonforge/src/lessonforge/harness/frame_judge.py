"""Every spoken sentence of a film judged against its frame by a vision model, in bulk and inside a cap.

The owner, 2026-11-03 and 2026-11-07: videos that passed every code check still showed text that did not match
the voice, held one picture for many sentences, or drew something the voice contradicted; and "don't check it
yourself, make a system which will use a VLM with images in bulk". ``vision_review`` looks at one frame per beat;
this looks at one frame per SENTENCE, the unit a viewer notices.

How it stays cheap:

* frames are cut at 80% of each sentence (its words have landed) from the lesson's own ``timeline.json``;
* a frame identical to the one before it is found by code (free) and reported as ``held`` without asking anyone;
* frames go to the model six at a time on one numbered contact sheet, with the six sentences: one call per six
  sentences, a few hundred tokens of text;
* the model is the cheapest that reads images well (Haiku 5.5 by default, about 0.05 US cents a call), every call
  is written to the spend ledger, and the run stops before it would pass ``cap_usd``.

``judge(lesson_id)`` returns one verdict per sentence and the share that pass; ``improver`` hands the failures to
Claude as faults, so a film's own frames drive the next edit.
"""
from __future__ import annotations

import base64
import io
import json
import subprocess
import tempfile
from pathlib import Path

from . import workbench as W

PER_SHEET = 6
TILE_W = 480
KINDS = ("ok", "mismatch", "text_mismatch", "empty", "overlap", "unreadable", "wrong_fact", "held")
SYSTEM = """You check frames of a narrated lesson video for school students. You get a numbered contact sheet of
frames, and for each number the sentence the narrator is saying at that frame. Frames are in order.
For EACH number decide what a learner sees while hearing that sentence:
  ok            the picture or the on-screen words go with the sentence
  mismatch      the picture shows something else than the sentence talks about
  text_mismatch the on-screen words say something different from, or contradict, the sentence
  empty         the voice explains something visual and the screen shows (almost) nothing for it
  overlap       labels or words collide or are cut off so they cannot be read
  unreadable    words too small or faint to read
  wrong_fact    a number, label or verdict on screen is wrong for the sentence (e.g. says convex, shape is concave)
Judge only what you can see; do not ask for style changes. Return ONLY JSON:
{"frames":[{"n":1,"verdict":"ok|mismatch|text_mismatch|empty|overlap|unreadable|wrong_fact","what":"<=15 words"}]}"""


def _job_of(lesson_id: str) -> str:
    jobs = [h["job_id"] for h in W.history(lesson_id) if h.get("job_id")]
    if not jobs:
        raise W.WorkbenchError("the lesson has not been filmed yet")
    return jobs[-1]


def sentence_times(timeline: list[dict], at: float = 0.8) -> list[dict]:
    """One point per spoken sentence: beat id, the sentence, and the time to look (timeline starts are per beat)."""
    out = []
    for beat in timeline:
        for s in beat.get("sentences") or []:
            out.append({"beat": beat["id"], "text": s["text"],
                        "t": round(float(beat["start"]) + float(s["start"]) + at * float(s["duration"]), 2)})
    return out


def _grab(video: str, t: float, file: Path) -> None:
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.2f}", "-i", video, "-frames:v", "1",
                    "-vf", f"scale={TILE_W}:-1", "-q:v", "4", str(file)], check=True)


def _same(a: Path, b: Path) -> bool:
    import numpy as np
    from PIL import Image
    x = np.asarray(Image.open(a).convert("L"), dtype=np.int16)
    y = np.asarray(Image.open(b).convert("L"), dtype=np.int16)
    return x.shape == y.shape and float((np.abs(x - y) > 12).mean()) < W.CHANGED_SHARE


def _sheet(files: list[Path], first: int) -> str:
    from PIL import Image, ImageDraw
    tiles = [Image.open(f).convert("RGB") for f in files]
    w, h = tiles[0].size
    cols = 3
    rows = (len(tiles) + cols - 1) // cols
    sheet = Image.new("RGB", (w * cols, h * rows), "white")
    d = ImageDraw.Draw(sheet)
    for i, t in enumerate(tiles):
        x, y = (i % cols) * w, (i // cols) * h
        sheet.paste(t, (x, y))
        d.rectangle([x, y, x + 34, y + 26], fill="yellow")
        d.text((x + 6, y + 6), str(first + i), fill="black")
    buf = io.BytesIO()
    sheet.save(buf, "JPEG", quality=72)
    return base64.b64encode(buf.getvalue()).decode()


def judge(lesson_id: str, cap_usd: float = 0.03, tier: str = "haiku", ask=None, log=print) -> dict:
    """Every sentence of the newest film judged. ``ask(tier, system, text, image_b64)`` -> (answer, cost, tokens)."""
    from . import improver
    folder = W.root() / lesson_id
    films = sorted(folder.glob("v[0-9][0-9][0-9].mp4"))
    if not films:
        raise W.WorkbenchError("the lesson has not been filmed yet")
    video = str(films[-1])
    timeline = json.loads((W.paths.sub("lessons", _job_of(lesson_id), create=False) / "timeline.json").read_text(encoding="utf-8"))
    points = sentence_times(timeline)
    if ask is None:
        kind = improver.provider()
        if kind is None:
            raise RuntimeError("no key for the vision model: set ANTHROPIC_API_KEY or OPENROUTER_API_KEY")
        ask = lambda t, s, text, image: improver._ask(kind, t, s, text, image, note="frame judge")   # noqa: E731
    spent, last = 0.0, None
    with tempfile.TemporaryDirectory() as tmp:
        files = []
        for i, p in enumerate(points):
            f = Path(tmp) / f"s{i:03}.jpg"
            _grab(video, p["t"], f)
            files.append(f)
            # Held: the screen did not change although a new sentence began (free, no model).
            p["held"] = bool(i and points[i - 1]["beat"] == p["beat"] and _same(files[i - 1], f))
        for start in range(0, len(points), PER_SHEET):
            chunk = points[start:start + PER_SHEET]
            guess = (last or 0.001) * 1.3
            if spent + guess > cap_usd:
                log(f"[frames] cap ${cap_usd:.3f} reached after ${spent:.4f}: {len(points) - start} sentence(s) not judged")
                break
            text = "\n".join(f"{start + k + 1}. \"{p['text']}\"" for k, p in enumerate(chunk))
            answer, cost, _ = ask(tier, SYSTEM, text, _sheet(files[start:start + PER_SHEET], start + 1))
            spent, last = spent + cost, cost
            for item in answer.get("frames") or []:
                try:
                    k = int(item.get("n")) - 1
                except (TypeError, ValueError):
                    continue
                if start <= k < start + len(chunk) and str(item.get("verdict")) in KINDS:
                    points[k]["verdict"], points[k]["what"] = item["verdict"], str(item.get("what") or "")[:160]
    judged = [p for p in points if "verdict" in p]
    bad = [p for p in judged if p["verdict"] != "ok"]
    held = [p for p in points if p["held"]]
    counts = {k: sum(1 for p in judged if p["verdict"] == k) for k in KINDS if k != "held"}
    counts["held"] = len(held)
    report = {"lesson_id": lesson_id, "video": video, "sentences": len(points), "judged": len(judged),
              "pass_share": round(1 - len(bad) / len(judged), 3) if judged else None,
              "held_share": round(len(held) / len(points), 3) if points else None,
              "counts": counts, "spent_usd": round(spent, 4),
              "problems": [{k: p[k] for k in ("beat", "t", "text", "verdict", "what") if k in p} for p in bad],
              "held": [{"beat": p["beat"], "t": p["t"], "text": p["text"]} for p in held]}
    (folder / f"{films[-1].stem}_frames.json").write_text(json.dumps(report, indent=1, ensure_ascii=False), encoding="utf-8")
    log(f"[frames] {lesson_id}: {report['judged']}/{report['sentences']} judged, pass {report['pass_share']}, "
        f"held {report['held_share']}, ${spent:.4f}")
    return report


def as_faults(report: dict, limit: int = 12) -> list[str]:
    """The film's problems in the words the improver gives Claude."""
    out = [f"beat {p['beat']} at {p['t']:.0f}s, while saying \"{p['text'][:90]}\": {p['verdict']} ({p.get('what', '')})"
           for p in report.get("problems") or []]
    out += [f"beat {p['beat']}: the screen does not change for \"{p['text'][:90]}\"" for p in report.get("held") or []]
    return out[:limit]
