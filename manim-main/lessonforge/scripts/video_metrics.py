"""One free, deterministic yardstick for a finished lesson video, so every later change is measured the same way.

    python scripts/video_metrics.py VIDEO [--json]
    python scripts/video_metrics.py VIDEO --lesson-dir <lessons/ID> [--preview preview.json] [--seen seen.json]

Needs only ``ffmpeg`` on PATH and ``numpy``. No model, no network, no GPU, nothing is written. Same file in, same numbers out.

What it reports (definitions are fixed here, so the 35% / 27% / 24% "moving" disagreement cannot come back):

* MOVING. The video is read at 10 frames a second, 320x180, and each step between two frames is "moving" when more than a
  fixed share of the frame's pixels changed by more than ``PIXEL_STEP`` grey levels. Three shares are always reported:
  ``loose`` > 0.03%, ``medium`` > 0.15% and ``strict`` > 0.5% of the frame. ``medium`` is THE number (``moving_share``).
* THE QUIZ BAR IS NOT MOTION. A thinking pause shows a thin gold countdown bar that shrinks for several seconds
  (``runtime.py`` ``_quiz_card``). A change that is only a thin gold line (<= 3 rows high at 180 rows) is masked out and the
  step is marked as a bar step; the stretch of bar steps (gaps up to 0.5 s joined) is the QUIZ SPAN. A quiz pause is therefore
  counted as still, and ``longest_still_outside_quiz_s`` subtracts the quiz spans from every still run.
* STILL RUNS. ``longest_still_s``, ``longest_still_outside_quiz_s`` and ``still_3s_s`` / ``still_3s_share`` (time inside
  still runs of 3 s or more) for each of the three thresholds.
* PICTURE SHARE. Every 2 s one 640x360 frame is looked at. ``card``: the paper (#F7F3EA or white) bounding box as a share of
  the frame (rows and columns holding at least a quarter of the busiest row or column); ``ink``: the bounding box of
  everything inside that card that is not paper; ``content``: for a frame with no card (a dark-stage figure), the bounding
  box of everything that is not the stage colour below the top 12% (header band). That includes the lesson's words, so it
  over-states a figure: say "content", not "figure". Median / min / max over the frames that have the thing.
* SILENCE. The audio is read at 16 kHz mono; 50 ms windows under ``SILENT_DB`` dBFS are silent; only silent runs of at least
  ``SILENT_RUN`` seconds count (a breath between words is not silence). ``silence_share`` is their time over the video.
* PREMATURE REVEALS (when ``--lesson-dir`` or ``--sync`` and ``--captions`` are given). The lesson writes when each step's
  text appears (``output/sync_timeline.json``) and when each sentence is spoken (``output/captions.vtt``). For every number in
  a step's ``show`` text, the spoken time is estimated inside its caption (proportional to the characters; the voice's own word
  times are not stored) and compared with the appearance. ``lead_s`` > 0 means it was printed before it was said. Flagged when
  more than ``REVEAL_TOL`` seconds early; a number first said more than ``REVEAL_AHEAD_S`` (15 s) after it is shown is "never spoken" (not the same mention). A number said in words ("one hundred eighty") is not matched to its digits, so it reads "never spoken". There is no OCR here (none is installed), so numbers drawn INSIDE a figure
  are not found by themselves: pass ``--seen seen.json`` (``[{"value": "12", "seen": 31.4}]``, read off the video by eye or
  by a vision pass) and they are compared the same way.
* PER-BEAT SIZES (``--preview preview.json``): the smallest line of words, the figure's label size and the card share of every
  beat, read from the file ``longform.preview`` wrote.

Everything is a pure function of the pixels and files, with no randomness.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import statistics
import subprocess
import sys
from pathlib import Path

import numpy as np

FPS = 10                                  # motion is measured at ten steps a second
SIZE = (320, 180)                         # ... on a 320x180 grey-ish copy
PIXEL_STEP = 10                           # grey levels a pixel must change by to count as changed
THRESHOLDS = {"loose": 0.0003, "medium": 0.0015, "strict": 0.005}     # share of the frame's pixels
PRIMARY = "medium"
BAR_ROWS = 3                              # a countdown bar is at most this many rows high (of 180)
BAR_JOIN_S = 0.5                          # bar steps closer than this make one quiz span
QUIZ_MIN_S = 1.0                          # a stretch of bar steps shorter than this is not a countdown (it is a small gold change)
STILL_LONG_S = 3.0
LOOK_EVERY_S = 2.0                        # a 640x360 frame is looked at this often for picture share
LOOK_SIZE = (640, 360)
PAPER = [(0xF7, 0xF3, 0xEA), (255, 255, 255)]
STAGE = (0x1C, 0x1F, 0x26)                # runtime.BG
HEADER_BAND = 0.12
SILENT_DB = -45.0
SILENT_RUN = 0.3
REVEAL_TOL = 0.5
REVEAL_AHEAD_S = 15.0                     # a number said more than this long after it is shown is not "the same mention"


# ---------------------------------------------------------------- reading the video

def ffmpeg() -> str:
    path = shutil.which("ffmpeg")
    if not path:
        raise SystemExit("video_metrics needs ffmpeg on PATH")
    return path


def probe_seconds(path: str | Path) -> float:
    """Duration of the video stream in seconds, from ffmpeg's own header read."""
    out = subprocess.run([ffmpeg(), "-hide_banner", "-i", str(path)], capture_output=True, text=True).stderr
    m = re.search(r"Duration: (\d+):(\d+):(\d+(?:\.\d+)?)", out)
    return (int(m[1]) * 3600 + int(m[2]) * 60 + float(m[3])) if m else 0.0


def frames(path: str | Path, fps: float, size: tuple[int, int]):
    """Yield RGB frames (h, w, 3 uint8) of the video at ``fps``, scaled (area average) to ``size``."""
    w, h = size
    cmd = [ffmpeg(), "-v", "error", "-i", str(path), "-an", "-vf", f"fps={fps},scale={w}:{h}:flags=area",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    n = w * h * 3
    try:
        while True:
            buf = proc.stdout.read(n)
            if len(buf) < n:
                break
            yield np.frombuffer(buf, np.uint8).reshape(h, w, 3)
    finally:
        proc.stdout.close()
        proc.wait()


def gold(rgb: np.ndarray) -> np.ndarray:
    """Pixels that lean yellow (the countdown bar and its blends with the stage); paper, blue and grey do not."""
    r, g, b = (rgb[..., i].astype(np.int16) for i in range(3))
    return (r - b > 20) & (g - b > 15) & (r > 60)


def step_changes(path: str | Path) -> dict:
    """For every step between two frames: the changed pixel count with the countdown bar masked, and whether a bar moved."""
    counts, raw_counts, bars = [], [], []
    prev = None
    for rgb in frames(path, FPS, SIZE):
        grey = rgb.astype(np.int16).sum(axis=2) // 3
        if prev is not None:
            changed = np.abs(grey - prev[0]) > PIXEL_STEP
            raw_counts.append(int(changed.sum()))
            g = changed & (gold(rgb) | gold(prev[1]))
            bar = False
            if g.any():
                rows, cols = np.where(g.any(axis=1))[0], np.where(g.any(axis=0))[0]
                if rows[-1] - rows[0] + 1 <= BAR_ROWS and cols[-1] - cols[0] + 1 >= 2:
                    changed = changed & ~g
                    bar = True
            counts.append(int(changed.sum()))
            bars.append(bar)
        prev = (grey, rgb)
    return {"counts": counts, "raw_counts": raw_counts, "bars": bars, "area": SIZE[0] * SIZE[1]}


# ---------------------------------------------------------------- moving, stills, quiz

def quiz_spans(bars: list[bool], fps: float = FPS) -> list[tuple[float, float]]:
    """Time spans (seconds) of the countdown bar moving; bar steps closer than BAR_JOIN_S make one span."""
    spans, start, last = [], None, None
    for i, bar in enumerate(bars):
        if not bar:
            continue
        if start is None:
            start, last = i, i
        elif (i - last) / fps <= BAR_JOIN_S:
            last = i
        else:
            spans.append((start / fps, (last + 1) / fps))
            start, last = i, i
    if start is not None:
        spans.append((start / fps, (last + 1) / fps))
    return spans


def still_runs(moving: list[bool], fps: float = FPS) -> list[tuple[float, float]]:
    """(start, end) seconds of every run of steps that did not move."""
    runs, start = [], None
    for i, m in enumerate(moving + [True]):
        if not m and start is None:
            start = i
        elif m and start is not None:
            runs.append((start / fps, i / fps))
            start = None
    return runs


def _minus(run: tuple[float, float], spans: list[tuple[float, float]]) -> list[tuple[float, float]]:
    pieces = [run]
    for a, b in spans:
        nxt = []
        for s, e in pieces:
            if b <= s or a >= e:
                nxt.append((s, e))
                continue
            if a > s:
                nxt.append((s, a))
            if b < e:
                nxt.append((b, e))
        pieces = nxt
    return pieces


def pause_spans(timeline: list[dict]) -> list[tuple[float, float]]:
    """The thinking pauses a lesson's ``timeline.json`` wrote, as (start, end) seconds: each beat ends with its pause, so a beat with
    ``thinking_pause_seconds`` p that starts at s and lasts d has its pause from s + d - p to s + d."""
    out = []
    for b in timeline or []:
        pause = float(b.get("thinking_pause_seconds") or 0.0)
        if pause > 0:
            end = float(b["start"]) + float(b["duration"])
            out.append((end - pause, end))
    return out


def motion_report(change: dict, fps: float = FPS, pauses: list[tuple[float, float]] | None = None) -> dict:
    area = change["area"]
    spans = [(a, b) for a, b in quiz_spans(change["bars"], fps) if b - a >= QUIZ_MIN_S - 1e-9]
    if pauses:
        # ``--pauses``: the pauses the timeline says (the countdown bar is only part of what a crafted pause changes: the card
        # fading in and out and the bar's own jumps could pass the threshold now and then and a pause counted as moving)
        spans = sorted(spans + [(a, b) for a, b in pauses])
        merged: list[tuple[float, float]] = []
        for a, b in spans:
            if merged and a <= merged[-1][1]:
                merged[-1] = (merged[-1][0], max(merged[-1][1], b))
            else:
                merged.append((a, b))
        spans = merged
    # the bar is masked only inside a confirmed quiz span; elsewhere a small gold change is a real change
    counts = [c if (bar and any(a <= i / fps < b for a, b in spans)) else raw
              for i, (c, raw, bar) in enumerate(zip(change["counts"], change["raw_counts"], change["bars"]))]
    if pauses:
        counts = [0 if any(a <= i / fps < b for a, b in pauses) else c for i, c in enumerate(counts)]
    seconds = len(counts) / fps
    out = {"steps": len(counts), "quiz_spans": [[round(a, 2), round(b, 2)] for a, b in spans],
           "quiz_s": round(sum(b - a for a, b in spans), 2), "levels": {}}
    for name, share in THRESHOLDS.items():
        moving = [c > share * area for c in counts]
        runs = still_runs(moving, fps)
        outside = [p for r in runs for p in _minus(r, spans)]
        long_ = [r for r in runs if r[1] - r[0] >= STILL_LONG_S - 1e-9]
        longest = max(runs, key=lambda r: r[1] - r[0], default=(0.0, 0.0))
        out["levels"][name] = {
            "threshold_share": share,
            "moving_share": round(sum(moving) / len(moving), 4) if moving else 0.0,
            "longest_still_s": round(longest[1] - longest[0], 2), "longest_still_at_s": round(longest[0], 2),
            "longest_still_outside_quiz_s": round(max((e - s for s, e in outside), default=0.0), 2),
            "still_3s_s": round(sum(e - s for s, e in long_), 2),
            "still_3s_share": round(sum(e - s for s, e in long_) / seconds, 4) if seconds else 0.0,
        }
    out["moving_share"] = out["levels"][PRIMARY]["moving_share"]
    # the same count with the bar NOT masked, to show what the masking removes
    if change["raw_counts"]:
        thr = THRESHOLDS[PRIMARY] * area
        out["moving_share_bar_unmasked"] = round(sum(c > thr for c in change["raw_counts"]) / len(change["raw_counts"]), 4)
    return out


# ---------------------------------------------------------------- picture share

def _near(rgb: np.ndarray, colour: tuple[int, int, int], tol: int) -> np.ndarray:
    return (np.abs(rgb.astype(np.int16) - np.array(colour, np.int16)).max(axis=2) <= tol)


def _bbox(mask: np.ndarray, keep: float = 0.0):
    """Bounding box (x0, y0, x1, y1) of the rows and columns holding at least ``keep`` of the busiest row / column."""
    if not mask.any():
        return None
    rows, cols = mask.sum(axis=1), mask.sum(axis=0)
    ry, cx = np.where(rows >= max(1, keep * rows.max()))[0], np.where(cols >= max(1, keep * cols.max()))[0]
    return int(cx[0]), int(ry[0]), int(cx[-1]) + 1, int(ry[-1]) + 1


def look_at(rgb: np.ndarray) -> dict:
    """Card, ink and content boxes of one frame, as shares of the frame."""
    h, w, _ = rgb.shape
    area = float(h * w)
    paper = np.zeros((h, w), bool)
    for colour in PAPER:
        paper |= _near(rgb, colour, 10)
    paper[: int(h * HEADER_BAND)] = False                 # the header's white words are not a card
    out = {"card": None, "ink": None, "content": None}
    if paper.sum() > 0.03 * area:
        box = _bbox(paper, keep=0.25)
        x0, y0, x1, y1 = box
        out["card"] = round((x1 - x0) * (y1 - y0) / area, 4)
        inside = ~paper[y0:y1, x0:x1] & (np.abs(rgb[y0:y1, x0:x1].astype(np.int16) - 245).max(axis=2) > 40)
        ink = _bbox(inside)
        if ink:
            out["ink"] = round((ink[2] - ink[0]) * (ink[3] - ink[1]) / area, 4)
    else:
        body = ~_near(rgb, STAGE, 40)
        body[: int(h * HEADER_BAND)] = False
        box = _bbox(body)
        if box:
            out["content"] = round((box[2] - box[0]) * (box[3] - box[1]) / area, 4)
    return out


def _summary(values: list[float]) -> dict | None:
    return ({"frames": len(values), "median": round(statistics.median(values), 4), "min": round(min(values), 4),
             "max": round(max(values), 4)} if values else None)


def picture_report(path: str | Path) -> dict:
    looks = [look_at(rgb) for rgb in frames(path, 1.0 / LOOK_EVERY_S, LOOK_SIZE)]
    return {"looked_at": len(looks),
            **{k: _summary([x[k] for x in looks if x[k] is not None]) for k in ("card", "ink", "content")}}


# ---------------------------------------------------------------- audio

def silence_report(path: str | Path) -> dict:
    cmd = [ffmpeg(), "-v", "error", "-i", str(path), "-vn", "-ac", "1", "-ar", "16000", "-f", "s16le", "-"]
    raw = subprocess.run(cmd, capture_output=True).stdout
    return silence_of(np.frombuffer(raw, np.int16).astype(np.float64) / 32768.0, 16000)


def silence_of(samples: np.ndarray, rate: int) -> dict:
    win = int(rate * 0.05)
    n = len(samples) // win
    if n == 0:
        return {"seconds": 0.0, "silence_share": 0.0, "silent_s": 0.0}
    rms = np.sqrt((samples[: n * win].reshape(n, win) ** 2).mean(axis=1))
    silent = (20 * np.log10(np.maximum(rms, 1e-9)) < SILENT_DB).tolist()
    need = int(round(SILENT_RUN / 0.05))
    total, run = 0, 0
    for s in silent + [False]:
        if s:
            run += 1
        else:
            if run >= need:
                total += run
            run = 0
    return {"seconds": round(n * 0.05, 2), "silent_s": round(total * 0.05, 2), "silence_share": round(total / n, 4)}


# ---------------------------------------------------------------- premature reveals

NUMBER = re.compile(r"(?<![\w.])-?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?(?![\w])")


def numbers_in(text: str) -> list[str]:
    return [m.group(0).replace(",", "") for m in NUMBER.finditer(text or "")]


def read_vtt(path: str | Path) -> list[dict]:
    """[{start, end, text}] of a WebVTT file (the lesson's captions: one cue per spoken sentence)."""
    cues, lines = [], Path(path).read_text(encoding="utf-8").splitlines()
    for i, line in enumerate(lines):
        m = re.match(r"(\d+):(\d+):(\d+\.\d+) --> (\d+):(\d+):(\d+\.\d+)", line)
        if m:
            a = int(m[1]) * 3600 + int(m[2]) * 60 + float(m[3])
            b = int(m[4]) * 3600 + int(m[5]) * 60 + float(m[6])
            j = i + 1
            text = []
            while j < len(lines) and lines[j].strip():
                text.append(lines[j].strip())
                j += 1
            cues.append({"start": a, "end": b, "text": " ".join(text)})
    return cues


def spoken_time(value: str, cues: list[dict], after: float = 0.0, before: float = 1e9) -> float | None:
    """When ``value`` is spoken: its position by characters inside the first caption between ``after`` and ``before`` that says it."""
    for cue in cues:
        if cue["end"] < after:
            continue
        if cue["start"] > before:
            break
        for m in NUMBER.finditer(cue["text"]):
            if m.group(0).replace(",", "") == value:
                span = max(len(cue["text"]), 1)
                return cue["start"] + (cue["end"] - cue["start"]) * (m.start() / span)
    return None


def reveal_check(appearances: list[dict], cues: list[dict], tol: float = REVEAL_TOL) -> dict:
    """``appearances``: [{value, seen, ...}]. Lead = spoken - seen, so a positive lead is a number printed before it is said."""
    rows = []
    for a in appearances:
        said = spoken_time(a["value"], cues, after=a["seen"] - 30.0 if "window" not in a else a["window"],
                           before=a["seen"] + REVEAL_AHEAD_S)
        if said is None:
            rows.append({**a, "spoken": None, "lead_s": None, "flag": "never spoken"})                  # ... within REVEAL_AHEAD_S of being shown
            continue
        lead = round(said - a["seen"], 2)
        rows.append({**a, "spoken": round(said, 2), "lead_s": lead,
                     "flag": "premature" if lead > tol else ("late" if lead < -tol else "")})
    leads = [r["lead_s"] for r in rows if r["lead_s"] is not None]
    return {"numbers": len(rows), "premature": sum(r["flag"] == "premature" for r in rows),
            "late": sum(r["flag"] == "late" for r in rows), "never_spoken": sum(r["flag"] == "never spoken" for r in rows),
            "max_lead_s": max(leads, default=0.0), "tolerance_s": tol, "rows": rows}


def step_appearances(sync: dict) -> list[dict]:
    """The numbers in every step's shown text, with the time the lesson prints that step (output/sync_timeline.json)."""
    out = []
    for beat in sync.get("beats", []):
        for ev in beat.get("events", []):
            if ev.get("kind") == "step":
                for value in numbers_in(ev.get("action") or ""):
                    out.append({"value": value, "seen": float(ev["time"]), "beat": beat.get("id"), "where": "step",
                                "window": float(ev.get("anchor_time", ev["time"])) - 1.0})
    return out


# ---------------------------------------------------------------- preview.json

def preview_rows(preview: dict) -> list[dict]:
    """Per beat: the smallest and the largest line of words, the figure's label size, the card share and the layout."""
    rows = []
    for s in preview.get("stills", []):
        if s.get("what") != "end":
            continue
        pts = [line["points"] for line in s.get("lines") or [] if line.get("points")]
        pic = s.get("picture") or {}
        rows.append({"chapter": s.get("chapter"), "beat": s.get("beat"), "words_min_pt": min(pts, default=None),
                     "words_max_pt": max(pts, default=None), "label_pt": pic.get("type_points"),
                     "card_share": pic.get("share"), "mode": (s.get("layout") or {}).get("mode")})
    return rows


# ---------------------------------------------------------------- the whole report

def measure(video: str | Path, lesson_dir: str | Path | None = None, sync: str | Path | None = None,
            captions: str | Path | None = None, preview: str | Path | None = None, seen: str | Path | None = None,
            pauses: bool = False) -> dict:
    video = Path(video)
    if not video.is_file():
        raise SystemExit(f"no such video: {video}")
    report = {"video": str(video), "seconds": round(probe_seconds(video), 2), "fps": FPS, "size": list(SIZE),
              "pixel_step": PIXEL_STEP, "primary": PRIMARY}
    held = None
    if pauses:
        timeline = Path(lesson_dir or ".") / "timeline.json"
        if not lesson_dir or not timeline.is_file():
            raise SystemExit("--pauses needs --lesson-dir with a timeline.json")
        held = pause_spans(json.loads(timeline.read_text(encoding="utf-8")))
    report["motion"] = motion_report(step_changes(video), pauses=held)
    if held is not None:
        report["motion"]["pauses_from_timeline"] = [[round(a, 2), round(b, 2)] for a, b in held]
    report["picture"] = picture_report(video)
    report["silence"] = silence_report(video)
    if lesson_dir:
        out = Path(lesson_dir) / "output"
        sync = sync or out / "sync_timeline.json"
        captions = captions or out / "captions.vtt"
        preview = preview or next(iter(sorted(Path(lesson_dir).glob("preview/*/preview.json"))), None)
    if sync and captions and Path(sync).is_file() and Path(captions).is_file():
        cues = read_vtt(captions)
        found = step_appearances(json.loads(Path(sync).read_text(encoding="utf-8")))
        if seen:
            found += [{**x, "where": "figure (read off the video)"} for x in json.loads(Path(seen).read_text(encoding="utf-8"))]
        report["reveals"] = reveal_check(found, cues)
    if preview and Path(preview).is_file():
        report["beats"] = preview_rows(json.loads(Path(preview).read_text(encoding="utf-8")))
    return report


def pct(x) -> str:
    return "-" if x is None else f"{100 * x:.1f}%"


def render(r: dict) -> str:
    m, lines = r["motion"], []
    lines.append(f"{r['video']}\n  {r['seconds']} s, read at {r['fps']} fps {r['size'][0]}x{r['size'][1]}, a pixel counts when it moves > {r['pixel_step']} grey levels")
    lines.append(f"  MOVING SHARE (medium, countdown bar masked): {pct(m['moving_share'])}   (bar left in: {pct(m.get('moving_share_bar_unmasked'))})")
    lines.append("  threshold  moving   longest still (at)   outside quiz   in stills >= 3 s")
    for name, lv in m["levels"].items():
        lines.append(f"  {name:<7} {lv['threshold_share'] * 100:>5.2f}%  {pct(lv['moving_share']):>6}   {lv['longest_still_s']:>5.1f} s ({lv['longest_still_at_s']:>5.1f})"
                     f"   {lv['longest_still_outside_quiz_s']:>6.1f} s      {lv['still_3s_s']:>6.1f} s ({pct(lv['still_3s_share'])})")
    lines.append(f"  quiz spans: {m['quiz_s']} s in {len(m['quiz_spans'])} span(s) {m['quiz_spans']}"
                 + (f"   (pauses from the timeline: {m['pauses_from_timeline']})" if m.get("pauses_from_timeline") else ""))
    p = r["picture"]
    for key, label in (("card", "card (paper bbox)"), ("ink", "ink inside the card"), ("content", "content, no card (stage frames)")):
        v = p.get(key)
        lines.append(f"  {label:<34} " + (f"median {pct(v['median'])}  min {pct(v['min'])}  max {pct(v['max'])}  ({v['frames']} of {p['looked_at']} frames)" if v else "none"))
    s = r["silence"]
    lines.append(f"  silence (runs >= {SILENT_RUN} s under {SILENT_DB:.0f} dBFS): {s['silent_s']} s = {pct(s['silence_share'])}")
    if "reveals" in r:
        v = r["reveals"]
        lines.append(f"  numbers shown: {v['numbers']}, printed > {v['tolerance_s']} s before spoken: {v['premature']}, late: {v['late']}, never spoken: {v['never_spoken']}, max lead {v['max_lead_s']} s")
        for row in v["rows"]:
            if row["flag"]:
                lines.append(f"    {row['flag']:<10} {row['value']:>6} seen {row['seen']:.1f}s spoken {row['spoken']} lead {row['lead_s']} ({row.get('where')}, beat {row.get('beat')})")
    else:
        lines.append("  premature reveals: not checked (give --lesson-dir, or --sync and --captions)")
    if r.get("beats"):
        lines.append("  beat  mode  words min/max pt  label pt  card share")
        for b in r["beats"]:
            lines.append(f"  {b['chapter']}/{b['beat']}  {b['mode'] or '-':<5} {b['words_min_pt']}/{b['words_max_pt']}  {b['label_pt']}  {b['card_share']}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("video")
    ap.add_argument("--json", action="store_true", help="print the numbers as JSON")
    ap.add_argument("--lesson-dir", help="a lesson folder (finds output/sync_timeline.json, output/captions.vtt, preview/*/preview.json)")
    ap.add_argument("--sync"), ap.add_argument("--captions"), ap.add_argument("--preview"), ap.add_argument("--seen")
    ap.add_argument("--pauses", action="store_true",
                    help="count the thinking pauses of <lesson-dir>/timeline.json as still (a quiz span by the clock, not only by the bar)")
    a = ap.parse_args(argv)
    report = measure(a.video, a.lesson_dir, a.sync, a.captions, a.preview, a.seen, a.pauses)
    print(json.dumps(report, indent=2) if a.json else render(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())
