"""Speech first: synthesize the narration, MEASURE it, and derive the timeline.

Animation timing is never guessed. Every beat's length comes from the audio that will
actually play: a short lead-in, the measured speech, a closing hold and any requested
thinking pause, rounded UP to a whole video frame so chapters concatenate without
drift. The result is ``timeline.json`` — the single source of timing for the scenes
(``runtime.LessonScene``), the captions and the chapter markers.

Three decisions here come straight from the review of the first 20-minute lesson
(docs/longform/HANDOFF_REPORT.md, "What passed and what remains unacceptable"):

* **Blocks, not sentences, by default.** Synthesizing 274 sentences one at a time
  gave the model no preceding context and the delivery came out disconnected.
  ``granularity="beat"`` sends a whole teaching block per request. Sentence spans
  inside a block are then *located* (pauses in the audio) rather than measured, and
  are labelled with how they were obtained so nothing downstream mistakes an
  estimate for an alignment. ``granularity="sentence"`` reproduces the old build.
* **Speech sets the duration.** The old build stretched everything with ``atempo`` to
  land on exactly 1200 s. Here the default tempo is 1.0 and the lesson is as long as
  the approved narration takes. ``target_seconds`` is still available, but only
  inside a narrow tolerance — outside it the fix is editorial, and the build says so.
* **Thinking time is silence the build owns**, never synthesized and never trimmed.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import shutil
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .. import knobs
from .contract import Lesson, split_sentences
from .speech import SAMPLE_RATE, SpeechBackend, get_backend, read_wav, to_canonical_wav, write_wav

LEAD_SECONDS = 0.5      # picture settles before the voice starts
TAIL_SECONDS = 0.6      # visual hold after the last word
FIGURE_LEAD_SECONDS = 1.0   # extra lead-in for a beat that introduces a new figure (time to draw it)
#: With ``joins: carried`` (``look.py``) a lesson's chapters open on the screen the last one left and its picture is
#: followed ACROSS chapters, so a chapter whose first beat keeps that picture needs no time to draw it. The silences
#: between beats inside a chapter are shorter too; a chapter's first lead and last tail stay as they were, so a part
#: still ends and begins with a breath. Before, every chapter seam was about 2.1 s of silence and every beat seam 1.1 s
#: (doc 12: 40% of a lesson silent against 23 to 30% in the reference lectures).
JOINED_LEAD_SECONDS = 0.3
JOINED_TAIL_SECONDS = 0.35
#: With ``craft: crafted`` (``look.py``; video-quality plan S11) the lesson opens on a title card and ends on a held picture:
#: the first beat's lead grows by the card's seconds, the last beat's tail is the closing hold. Silence the build owns, like
#: every lead and tail; ``runtime.GuidedChapter`` draws the card in the lead only when the timeline carries those seconds.
TITLE_CARD_SECONDS = 2.0
CLOSING_HOLD_SECONDS = 3.0
PACING_TOLERANCE = 0.10  # widest tempo change target_seconds may impose (was .70–1.25)


class PacingError(ValueError):
    """The narration cannot reach the requested duration without audible retiming."""


@dataclass
class BuildOptions:
    granularity: str = "beat"           # "beat" (block synthesis) | "sentence"
    fps: int = 30
    tempo: float = 1.0                  # applied to every clip; ignored when target_seconds is set
    target_seconds: float | None = None
    lead: float = LEAD_SECONDS
    tail: float = TAIL_SECONDS
    #: word-level alignment through speech-to-text (longform.align): "auto" aligns when an
    #: OpenRouter key is present and LESSONFORGE_ALIGN is not "0"; "on" | "off" force it.
    align: str = "auto"


def _align_enabled(opts: "BuildOptions") -> bool:
    import os
    if opts.align == "off":
        return False
    if opts.align == "on":
        return True
    from .. import spend
    return bool(spend.api_key()) and knobs.get("LESSONFORGE_ALIGN", "1") != "0"


def stamp(seconds: float) -> str:
    """Seconds → WebVTT ``HH:MM:SS.mmm``."""
    ms = round(seconds * 1000)
    s, ms = divmod(ms, 1000)
    m, s = divmod(s, 60)
    h, m = divmod(m, 60)
    return f"{h:02}:{m:02}:{s:02}.{ms:03}"


def _clip_hash(backend: SpeechBackend, text: str) -> str:
    return hashlib.sha256(f"{backend.cache_key()}|{text}".encode("utf-8")).hexdigest()[:16]


def _shared_cache(backend: SpeechBackend) -> Path | None:
    """Where paid narration is kept for EVERY lesson, or None when it is not shared.

    A lesson's clips used to live only in its own folder, so "Try again" or "Edit the script and
    make it again" bought every block of narration once more, and heard it once more for
    alignment: on 2026-10-09 one 2000-word script was narrated three times in an afternoon.
    Clips are named by (voice settings, exact text), so the same words in the same voice are the
    same file whichever lesson asks. Free voices are not kept (nothing to save).
    """
    if os.getenv("LESSONFORGE_SPEECH_CACHE", "1") != "1" or backend.name in ("silent", "browser", "gtts"):
        return None
    from .. import paths
    return paths.cache("speech")


def _link(source: Path, dest: Path) -> None:
    """``dest`` becomes ``source``: a hard link where the disk allows it (no second copy), else a copy."""
    if dest.exists():
        return
    try:
        os.link(source, dest)
    except OSError:
        shutil.copy2(source, dest)


def _fetch_shared(shared: Path | None, raw: Path) -> bool:
    """Bring a clip, and whatever was already heard of it, from the shared cache into the lesson."""
    if shared is None or not (shared / raw.name).is_file():
        return False
    for kept in shared.glob(raw.stem + "*"):
        _link(kept, raw.with_name(kept.name))
    return raw.exists()


def _store_shared(shared: Path | None, raw: Path) -> None:
    """Keep a lesson's clip and its hearings for the next lesson. Best-effort: a full disk costs nothing but the saving."""
    if shared is None:
        return
    try:
        for made in raw.parent.glob(raw.stem + "*"):
            if made.suffix in (".wav", ".json") and made.stat().st_size > 2:      # never an empty hearing ("[]")
                _link(made, shared / made.name)
    except OSError:
        pass


def _silence_gaps(samples: np.ndarray, rate: int, min_gap: float = 0.12) -> list[float]:
    """Midpoints (seconds) of the pauses in a clip — where a sentence can end."""
    hop = max(1, rate // 100)  # 10 ms
    n = len(samples) // hop
    if n < 4:
        return []
    energy = np.sqrt(np.mean(samples[: n * hop].reshape(n, hop) ** 2, axis=1))
    floor = max(float(energy.max()) * 0.03, 1e-4)
    quiet = energy < floor
    gaps, start = [], None
    for i, q in enumerate(quiet):
        if q and start is None:
            start = i
        elif not q and start is not None:
            if (i - start) * hop / rate >= min_gap and start > 0:
                gaps.append((start + i) / 2 * hop / rate)
            start = None
    return gaps


def locate_sentences(sentences: list[str], samples: np.ndarray, rate: int) -> list[dict]:
    """Place sentence boundaries inside ONE synthesized block.

    A boundary is first estimated from the sentence's share of the remaining
    characters, then snapped to the nearest real pause in the audio when one lies
    within a second.
    ``timing_source`` records which happened: ``pause-snapped`` is a measurement of a
    silence the listener can hear; ``estimated`` is arithmetic and should be treated
    as needing review before a cue is trusted to it.
    """
    total = len(samples) / rate
    if len(sentences) <= 1:
        return [{"text": s, "start": 0.0, "duration": total, "timing_source": "measured"} for s in sentences]
    weights = [max(1, len(s)) for s in sentences]
    gaps = _silence_gaps(samples, rate)
    bounds, sources, last = [], [], 0.0
    for i in range(len(sentences) - 1):
        # Re-estimate from the last placed boundary, not from zero: once a boundary
        # is pinned to a real pause, its error must not carry into the next one.
        est = last + (total - last) * weights[i] / sum(weights[i:])
        near = [g for g in gaps if g > last + 0.2 and abs(g - est) <= 1.0]
        if near:
            point = min(near, key=lambda g: abs(g - est))
            sources.append("pause-snapped")
        else:
            point = max(est, last + 0.2)
            sources.append("estimated")
        bounds.append(min(point, total))
        last = bounds[-1]
    edges = [0.0, *bounds, total]
    located = []
    for i, text in enumerate(sentences):
        # A sentence is only as trustworthy as its weaker edge.
        edge_sources = ([sources[i - 1]] if i else []) + ([sources[i]] if i < len(sources) else [])
        located.append({"text": text, "start": edges[i], "duration": max(0.05, edges[i + 1] - edges[i]),
                        "timing_source": "estimated" if "estimated" in edge_sources else "pause-snapped"})
    return located


def _joined(lesson) -> bool:
    """Whether a lesson's chapters are joined (``look.py``: ``joins``); the renderer reads the same key."""
    from . import look as _look
    said = getattr(lesson, "look", None)
    return _look.of({"look": said} if isinstance(said, dict) else None)["joins"] == "carried"


def _crafted(lesson) -> bool:
    """Whether a lesson has a title card and a closing hold (``look.py``: ``craft``); the renderer reads the same key."""
    from . import look as _look
    said = getattr(lesson, "look", None)
    return _look.of({"look": said} if isinstance(said, dict) else None)["craft"] == "crafted"


def _joined_leads(beats: list, opts: "BuildOptions") -> None:
    """Lead and tail of every beat of a joined lesson.

    The picture on screen is worked out as ``runtime.GuidedChapter.construct`` works it out: a beat's own figure, else
    the one already up, else (after a beat spoken without a picture) the last one named, drawn in again. Only a
    picture that is DRAWN in a beat gets the figure's extra lead. A beat inside a chapter starts after a short breath;
    a chapter's first beat and last beat keep the full lead and tail.
    """
    up, named = None, None
    for i, b in enumerate(beats):
        beat = b["beat"]
        first = i == 0 or beats[i - 1]["chapter"].id != b["chapter"].id
        last = i == len(beats) - 1 or beats[i + 1]["chapter"].id != b["chapter"].id
        own = getattr(beat, "figure", None)
        named = own or named
        drawn = False
        if getattr(beat, "picture", None) == "off":
            up = None
        else:
            spec = own if own else (named if up is None else None)
            key = json.dumps(spec, sort_keys=True, default=str) if spec else None
            if key and key != up:
                drawn, up = True, key
        b["lead"] = (opts.lead if first else min(opts.lead, JOINED_LEAD_SECONDS)) + (FIGURE_LEAD_SECONDS if drawn else 0.0)
        b["tail"] = opts.tail if last else min(opts.tail, JOINED_TAIL_SECONDS)


def build_audio(lesson: Lesson, lesson_dir: str | Path, voice: str | SpeechBackend = "silent",
                options: BuildOptions | None = None, log=print) -> dict:
    """Synthesize, measure and write ``timeline.json``, ``audio/``, captions and a report.

    Clips are cached by (backend settings, text): editing one beat re-synthesizes one
    beat. Returns the audio report (also written to ``audio_report.json``).
    """
    opts = options or BuildOptions()
    if opts.granularity not in ("beat", "sentence"):
        raise ValueError("granularity must be 'beat' or 'sentence'")
    backend = get_backend(voice)
    root = Path(lesson_dir)
    audio_dir, out_dir = root / "audio", root / "output"
    audio_dir.mkdir(parents=True, exist_ok=True)
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1. Synthesize (or reuse) one raw clip per unit and measure it.
    shared = _shared_cache(backend)
    beats, raw_speech, synthesized, reused = [], 0.0, 0, 0
    for chapter, beat in lesson.beats():
        units = beat.sentences if opts.granularity == "sentence" else [beat.narration.strip()]
        clips = []
        for text in units:
            raw = audio_dir / f"raw_{_clip_hash(backend, text)}.wav"
            if not raw.exists() and _fetch_shared(shared, raw):
                reused += 1                       # the same words in the same voice were bought for another lesson
            if not raw.exists():
                produced = raw.with_suffix(".tmp" + backend.suffix)
                backend.synthesize(text, produced)
                to_canonical_wav(produced, raw)
                produced.unlink(missing_ok=True)
                synthesized += 1
                _store_shared(shared, raw)
            samples, rate = read_wav(raw)
            clips.append({"text": text, "raw": raw, "raw_duration": len(samples) / rate})
            raw_speech += len(samples) / rate
        beats.append({"chapter": chapter, "beat": beat, "clips": clips})
        log(f"[audio] beat {beat.id}: {sum(c['raw_duration'] for c in clips):.2f}s"
            f" ({len(clips)} clip{'s' if len(clips) != 1 else ''})")

    # A beat that brings a NEW figure gets a longer lead-in: the picture is drawn before
    # the voice starts talking about it (picture first, then words).
    if _joined(lesson):
        _joined_leads(beats, opts)
    else:
        current = {"chapter": None, "figure": None}
        for b in beats:
            figure = getattr(b["beat"], "figure", None)
            key = json.dumps(figure, sort_keys=True, default=str) if figure else None
            if b["chapter"].id != current["chapter"]:
                current = {"chapter": b["chapter"].id, "figure": None}
            b["lead"] = opts.lead + (FIGURE_LEAD_SECONDS if key and key != current["figure"] else 0.0)
            b["tail"] = opts.tail
            if key:
                current["figure"] = key

    if beats and _crafted(lesson):
        beats[0]["lead"] += TITLE_CARD_SECONDS
        beats[-1]["tail"] = max(beats[-1]["tail"], CLOSING_HOLD_SECONDS)

    # 2. Decide the tempo. A target may only nudge it.
    fixed = sum(b["lead"] + b["tail"] + b["beat"].thinking_pause_seconds for b in beats)
    tempo = opts.tempo
    if opts.target_seconds:
        tempo = raw_speech / max(opts.target_seconds - fixed, 1e-6)
        if abs(tempo - 1.0) > PACING_TOLERANCE:
            raise PacingError(
                f"Reaching {opts.target_seconds:.0f}s needs atempo={tempo:.3f}; more than "
                f"±{PACING_TOLERANCE:.0%} is audible. The narration runs {raw_speech + fixed:.0f}s "
                "at natural pace — change the script or the target, not the speech.")

    # 3. Pace, locate (or align) sentences, frame-align every beat.
    # Nothing to hear in silence (or when the learner's device reads the captions): no recogniser is paid to listen.
    aligning = _align_enabled(opts) and backend.name not in ("silent", "browser")
    align_stats = {"clips": 0, "trusted": 0, "words": 0, "matched_words": 0}
    timeline, tracks = [], []
    for b in beats:
        beat, parts, local, sentences = b["beat"], [np.zeros(round(b["lead"] * SAMPLE_RATE), np.float32)], b["lead"], []
        for clip in b["clips"]:
            if abs(tempo - 1.0) > 1e-6:
                paced = audio_dir / f"paced_{tempo:.4f}_{clip['raw'].name}"
                if not paced.exists():
                    to_canonical_wav(clip["raw"], paced, tempo=tempo)
                samples, _ = read_wav(paced)
            else:
                samples, _ = read_wav(clip["raw"])
            spans = None
            if aligning:
                from . import align
                try:
                    # Heard in the spoken language and, for Hinglish, in the script's too: the better match wins.
                    result = align.align_best(clip["text"], clip["raw"], lesson.language,
                                              cache_stem=clip["raw"].with_suffix(""))
                except Exception as exc:  # noqa: BLE001 - alignment is an upgrade, never a blocker
                    log(f"[align] beat {beat.id}: {type(exc).__name__}: {str(exc)[:100]} — using pause estimate")
                    result = None
                _store_shared(shared, clip["raw"])       # what was heard of the clip is kept with it
                if result:
                    align_stats["clips"] += 1
                    if result["trusted"]:
                        align_stats["trusted"] += 1
                        align_stats["words"] += result["words"]
                        align_stats["matched_words"] += result["matched_words"]
                        # Alignment ran on the raw clip; a tempo change scales its clock.
                        spans = align.shift(result["sentences"], 0.0, scale=1.0 / tempo)
                    else:
                        log(f"[align] beat {beat.id}: only {result['coverage']:.0%} of words recognised — using pause estimate")
            if spans is None and opts.granularity == "sentence":
                spans = [{"text": clip["text"], "start": 0.0, "duration": len(samples) / SAMPLE_RATE,
                          "timing_source": "measured"}]
            elif spans is None:
                spans = locate_sentences(split_sentences(clip["text"]), samples, SAMPLE_RATE)
            for span in spans:
                moved = {**span, "start": local + span["start"]}
                if span.get("words"):
                    moved["words"] = [{**w, "start": local + w["start"], "end": local + w["end"]} for w in span["words"]]
                sentences.append(moved)
            parts.append(samples)
            local += len(samples) / SAMPLE_RATE
        speech_end = local
        frames = math.ceil((local + b["tail"] + beat.thinking_pause_seconds) * opts.fps - 1e-9)
        timeline.append({"id": beat.id, "chapter": b["chapter"].id, "chapter_title": b["chapter"].title,
                         "start": 0.0, "duration": frames / opts.fps, "speech_end": speech_end, "lead": b["lead"],
                         "sentences": sentences, "thinking_pause_seconds": beat.thinking_pause_seconds})
        tracks.append(np.concatenate(parts))

    # 4. With a target, hand leftover whole frames out as visual holds — never trim.
    if opts.target_seconds:
        spare = round((opts.target_seconds - sum(t["duration"] for t in timeline)) * opts.fps)
        for i in range(max(0, spare)):
            timeline[i % len(timeline)]["duration"] += 1 / opts.fps

    # 5. Lay the beats end to end; write per-beat audio, the full track and captions.
    cursor, mixed, vtt = 0.0, [], ["WEBVTT", ""]
    for entry, track in zip(timeline, tracks):
        entry["start"] = cursor
        length = round(entry["duration"] * SAMPLE_RATE)
        assert length >= len(track), f"beat {entry['id']} shorter than its own speech"
        padded = np.pad(track, (0, length - len(track)))
        write_wav(audio_dir / f"beat_{entry['id']}.wav", padded)
        mixed.append(padded)
        for s in entry["sentences"]:
            vtt += [f"{stamp(cursor + s['start'])} --> {stamp(cursor + s['start'] + s['duration'])}", s["text"], ""]
        cursor += entry["duration"]
    narration = np.concatenate(mixed)
    write_wav(audio_dir / "narration.wav", narration)
    (root / "timeline.json").write_text(json.dumps(timeline, indent=2, ensure_ascii=False), encoding="utf-8")
    (out_dir / "captions.vtt").write_text("\n".join(vtt), encoding="utf-8")

    all_sentences = [s for t in timeline for s in t["sentences"]]
    report = {
        **backend.describe(),
        "granularity": opts.granularity,
        "atempo": tempo,
        "raw_speech_seconds": raw_speech,
        "final_duration": len(narration) / SAMPLE_RATE,
        "fps": opts.fps,
        "beat_count": len(timeline),
        "sentence_count": len(all_sentences),
        "word_count": lesson.word_count,
        "clips_synthesized": synthesized,
        "clips_reused_from_other_lessons": reused,
        "sentence_timing": {k: sum(1 for s in all_sentences if s["timing_source"] == k)
                            for k in ("aligned", "measured", "pause-snapped", "estimated")},
        "alignment": {**align_stats, "enabled": aligning,
                      "word_match_rate": (align_stats["matched_words"] / align_stats["words"]) if align_stats["words"] else None},
        "peak": float(np.max(np.abs(narration))) if len(narration) else 0.0,
        "rms": float(np.sqrt(np.mean(narration ** 2))) if len(narration) else 0.0,
        "sync": "Sentence starts as labelled per sentence in timeline.json; inside an 'aligned' sentence every "
                "word carries its recognised time, elsewhere positions are word-position estimates "
                "(see runtime.LessonScene.cue).",
    }
    (root / "audio_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    log(f"[audio] {report['final_duration']:.1f}s narration, {len(timeline)} beats, "
        f"{synthesized} clip(s) synthesized, tempo {tempo:.3f}"
        + (f"; {reused} clip(s) taken from the narration already paid for" if reused else ""))
    return report
