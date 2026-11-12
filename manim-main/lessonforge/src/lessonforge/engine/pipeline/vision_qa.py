"""Vision-QA stage (pipeline stage 9): the one reviewer that looks at PIXELS.

The geometry probe in ``app.render`` measures overlap / clipped / text-over-shape by
walking the mobject tree; it is blind to the defect classes a human reviewer catches —
crowding, dead space (a 90%-empty frame), weak contrast, unreadable tiny text, broken
visual hierarchy (roadmap §G and §3c: every §3c defect was invisible to the probe at
``violations_remaining: 0``).

Implementation (reference-architecture.md §18):

    1. extract N frames from the rendered mp4 (ffmpeg, evenly spaced, downscaled —
       frames are a metered-edge input, so we send small JPEGs)
    2. ONE vision-LLM call for all frames with a fixed critique rubric
    3. findings come back as JSON, are whitelist-gated (lenient parse + shape gate,
       principle P8; class names checked exactly, principle P10), and are formatted as
       ``LAYOUT_VIOLATION: vision-<class> t=<sec>s <detail>`` lines — the probe's line
       format with a ``vision-`` class prefix, so ``render._overlap_violations`` (which
       matches only the three geometric classes) never double-counts them
    4. non-fatal at every step: any failure returns no findings (improve or stand
       aside); the verified video is never lost.

Enable with ``VISION_QA=1``. Knobs: ``VISION_QA_FRAMES`` (default 6),
``VISION_QA_MODELS`` (see app.llm.VISION_QA_DEFAULT_MODELS).
The repair half lives in ``app.render._run_vision_qa`` (accept-if-better, geometric
non-regression guard) — this module only measures.
"""
from __future__ import annotations

import base64
import logging
import os
import subprocess
import tempfile
from typing import List

from ..llm import call_vision_llm, loads_json_lenient
from .stages import PipelineContext

logger = logging.getLogger(__name__)

# The exact defect vocabulary (P10: the parser accepts these forms and nothing else).
VISION_CLASSES = (
    "clipped-text",      # text cut off by the frame edge
    "colliding-text",    # text overlapping text/diagram in ways the probe missed
    "unreadable-text",   # too small / blurry to read at video resolution
    "crowding",          # too many objects packed in one region
    "dead-frame",        # frame is mostly empty while narration runs
    "low-contrast",      # foreground barely separates from background
    "broken-hierarchy",  # everything has equal visual weight / no focal point
)

_RUBRIC = (
    "You are reviewing frames from an educational STEM animation. For EACH frame, "
    "check ONLY these defect classes:\n"
    + "\n".join(f"- {c}" for c in VISION_CLASSES) +
    "\nReport a finding ONLY when the defect is clear and would bother a student. "
    "An intentionally minimal frame (a single centered title) is NOT dead-frame; a "
    "frame that is ~90% empty mid-explanation IS. Return ONLY a JSON object:\n"
    '{"findings": [{"t": <frame timestamp seconds>, "class": "<one class above>", '
    '"detail": "<one short sentence naming the on-screen text/object>"}]}\n'
    "Return {\"findings\": []} when the frames are clean. No markdown, no prose."
)


def _probe_duration(video_path: str) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", video_path],
        capture_output=True, text=True, timeout=30,
    )
    return float(out.stdout.strip())


def _extract_frames(video_path: str, n: int):
    """Return [(timestamp_seconds, jpeg_base64), ...] for n evenly spaced frames."""
    duration = _probe_duration(video_path)
    if duration <= 0:
        return []
    frames = []
    with tempfile.TemporaryDirectory(prefix="vision_qa_") as tmp:
        for i in range(n):
            t = round((i + 0.5) * duration / n, 2)
            out_path = os.path.join(tmp, f"f{i}.jpg")
            # Downscale to 640w: enough to judge legibility, cheap to send.
            r = subprocess.run(
                ["ffmpeg", "-ss", str(t), "-i", video_path, "-frames:v", "1",
                 "-vf", "scale=640:-2", "-q:v", "5", "-y", out_path],
                capture_output=True, timeout=60,
            )
            if r.returncode == 0 and os.path.exists(out_path):
                with open(out_path, "rb") as f:
                    frames.append((t, base64.b64encode(f.read()).decode("ascii")))
    return frames


def _parse_findings(text: str, timestamps) -> List[str]:
    """Lenient parse + shape gate (P8): keep only well-formed, whitelisted findings."""
    try:
        data = loads_json_lenient(text)
    except Exception:
        return []
    raw = data.get("findings") if isinstance(data, dict) else None
    if not isinstance(raw, list):
        return []
    lines = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        cls = item.get("class")
        detail = str(item.get("detail") or "").strip().replace("\n", " ")
        try:
            t = float(item.get("t"))
        except (TypeError, ValueError):
            continue
        if cls not in VISION_CLASSES or not detail:
            continue
        # Snap to the nearest frame we actually sent — the model can't have seen
        # any other moment, so an invented timestamp is normalized, not trusted.
        if timestamps:
            t = min(timestamps, key=lambda ts: abs(ts - t))
        lines.append(f"LAYOUT_VIOLATION: vision-{cls} t={t}s {detail}")
    return lines


class VisionQAStage:
    """Frame-level critique of a rendered video. Measurement only; never fatal."""

    name = "vision_qa"

    def enabled(self) -> bool:
        return os.getenv("VISION_QA", "0") == "1"

    def critique(self, video_path: str) -> List[str]:
        """Return ``LAYOUT_VIOLATION: vision-*`` lines for a rendered video file.

        Empty list on ANY failure (no key, ffmpeg error, model refusal, bad JSON):
        this stage improves or stands aside, it never blocks a shipped video.
        """
        if not self.enabled():
            return []
        try:
            if not video_path:
                return []
            if not os.path.exists(video_path):
                # Accept the /static/videos/<name>.mp4 URL form too.
                from ..config import VIDEO_DIR
                candidate = os.path.join(VIDEO_DIR, os.path.basename(video_path))
                if not os.path.exists(candidate):
                    return []
                video_path = candidate
            n = max(1, int(os.getenv("VISION_QA_FRAMES", "6")))
            frames = _extract_frames(video_path, n)
            if not frames:
                logger.warning("Vision QA: no frames extracted from %s.", video_path)
                return []
            timestamps = [t for t, _ in frames]
            prompt = ("Frame timestamps in order: "
                      + ", ".join(f"{t}s" for t in timestamps)
                      + ". Review each frame against the rubric.")
            text = call_vision_llm(prompt, [b for _, b in frames],
                                   system_instruction=_RUBRIC)
            if text is None:
                return []
            findings = _parse_findings(text, timestamps)
            if findings:
                logger.warning("Vision QA: %d finding(s) on %s.",
                               len(findings), os.path.basename(video_path))
            else:
                logger.info("Vision QA: clean (%d frames).", len(frames))
            return findings
        except Exception as e:
            logger.warning("Vision QA stood aside (%s).", e)
            return []

    def run(self, ctx: PipelineContext) -> PipelineContext:
        if ctx.video_url:
            ctx.violations.extend(self.critique(ctx.video_url))
        return ctx
