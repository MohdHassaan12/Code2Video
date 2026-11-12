"""Long-form contract, audio-first timeline and bridge — no manim render, no network.

The silent backend makes the audio build deterministic and free, so the timeline
arithmetic (frame alignment, pauses, captions, pacing refusal) is tested for real;
only ffmpeg is required.
"""
import json
import shutil

import numpy as np
import pytest

from lessonforge import bridge, layout_probe
from lessonforge.longform import audio
from lessonforge.longform.contract import Lesson, split_sentences
from lessonforge.longform.speech import SAMPLE_RATE, SilentBackend, get_backend, read_wav, write_wav

needs_ffmpeg = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg not installed")


def make_lesson(**overrides):
    data = {
        "title": "Why like terms combine",
        "thesis": "Like terms count the same thing.",
        "chapters": [
            {"id": 1, "title": "TILES", "beats": [
                {"id": "01", "narration": "Take a square of side x. Its area is x squared.",
                 "board_text": "One tile", "equation": "A = x^2"},
                {"id": "02", "narration": "Here are two tiles and three more. Count them. What do you get?",
                 "board_text": "Two and three", "equation": "2x^2 + 3x^2", "thinking_pause_seconds": 2},
            ]},
            {"id": 2, "title": "RULE", "beats": [
                {"id": "03", "narration": "Add the coefficients and keep the variable part.", "equation": "(2+3)x^2"},
            ]},
        ],
    }
    data.update(overrides)
    return Lesson.model_validate(data)


# ── contract ──────────────────────────────────────────────────────────────────

def test_sentences_split_on_latin_and_devanagari_stops():
    assert split_sentences("One. Two? Three!") == ["One.", "Two?", "Three!"]
    assert split_sentences("यह एक वर्ग है। इसका क्षेत्रफल निकालो।") == ["यह एक वर्ग है।", "इसका क्षेत्रफल निकालो।"]


def test_duplicate_beat_ids_are_rejected_across_chapters():
    lesson = make_lesson().model_dump()
    lesson["chapters"][1]["beats"][0]["id"] = "01"
    with pytest.raises(ValueError, match="beat id '01'"):
        Lesson.model_validate(lesson)


def test_empty_narration_is_rejected():
    lesson = make_lesson().model_dump()
    lesson["chapters"][0]["beats"][0]["narration"] = "   "
    with pytest.raises(ValueError, match="no narration"):
        Lesson.model_validate(lesson)


def test_unknown_keys_survive_a_round_trip():
    lesson = make_lesson(reviewer="teacher-1")
    assert json.loads(lesson.model_dump_json())["reviewer"] == "teacher-1"


# ── speech ────────────────────────────────────────────────────────────────────

def test_voice_specs_parse():
    assert get_backend("silent").name == "silent"
    kokoro = get_backend("kokoro:af_sky@0.9")
    assert (kokoro.voice, kokoro.speed) == ("af_sky", 0.9)
    engine = get_backend("engine:gemini/hi-IN/Kore")
    assert (engine.provider, engine.language, engine.speaker) == ("gemini", "hi-IN", "Kore")
    with pytest.raises(ValueError):
        get_backend("festival")


def test_cache_key_changes_with_anything_that_changes_the_audio():
    assert get_backend("kokoro:af_heart@0.85").cache_key() != get_backend("kokoro:af_heart@0.9").cache_key()
    assert get_backend("engine:sarvam/hi-IN/shubh").cache_key() != get_backend("engine:sarvam/en-IN/shubh").cache_key()


def test_wav_round_trip(tmp_path):
    tone = (0.5 * np.sin(np.linspace(0, 440 * 2 * np.pi, SAMPLE_RATE))).astype(np.float32)
    write_wav(tmp_path / "t.wav", tone)
    back, rate = read_wav(tmp_path / "t.wav")
    assert rate == SAMPLE_RATE and len(back) == len(tone) and np.max(np.abs(back - tone)) < 1e-3


# ── sentence location inside a block ──────────────────────────────────────────

def _speech_with_pauses(durations, pause=0.3):
    rng = np.random.default_rng(0)
    parts = []
    for i, d in enumerate(durations):
        parts.append(0.3 * rng.standard_normal(round(d * SAMPLE_RATE)).astype(np.float32))
        if i < len(durations) - 1:
            parts.append(np.zeros(round(pause * SAMPLE_RATE), np.float32))
    return np.concatenate(parts)


def test_boundaries_snap_to_real_pauses():
    # Character counts predict the durations only roughly (as in real speech); the
    # boundaries must land on the pauses, not on the arithmetic.
    sentences = ["A first sentence of some length.", "Then a second one, a bit longer than it.", "And the last."]
    samples = _speech_with_pauses([2.4, 2.4, 1.2])
    spans = audio.locate_sentences(sentences, samples, SAMPLE_RATE)
    assert [s["timing_source"] for s in spans] == ["pause-snapped"] * 3
    assert abs(spans[1]["start"] - 2.55) < 0.1 and abs(spans[2]["start"] - 5.25) < 0.1


def test_a_pause_too_far_from_the_estimate_is_not_trusted():
    # Text and audio disagree badly: rather than snap to a pause that is probably a
    # comma, the boundary stays an estimate and SAYS so.
    sentences = ["Short one.", "A much much much longer second sentence here.", "End."]
    spans = audio.locate_sentences(sentences, _speech_with_pauses([2.0, 2.0, 2.0]), SAMPLE_RATE)
    assert spans[0]["timing_source"] == "estimated"


def test_without_pauses_boundaries_are_labelled_estimated():
    samples = 0.3 * np.ones(4 * SAMPLE_RATE, np.float32)
    spans = audio.locate_sentences(["One two three.", "Four five six."], samples, SAMPLE_RATE)
    assert {s["timing_source"] for s in spans} == {"estimated"}
    assert abs(spans[1]["start"] - 2.0) < 0.05


# ── the audio build ───────────────────────────────────────────────────────────

@needs_ffmpeg
@pytest.mark.parametrize("granularity", ["beat", "sentence"])
def test_timeline_is_frame_aligned_and_contiguous(tmp_path, granularity):
    lesson = make_lesson()
    report = audio.build_audio(lesson, tmp_path, SilentBackend(), audio.BuildOptions(granularity=granularity),
                               log=lambda *_: None)
    timeline = json.loads((tmp_path / "timeline.json").read_text())
    assert [t["id"] for t in timeline] == ["01", "02", "03"]
    cursor = 0.0
    for entry in timeline:
        assert abs(entry["start"] - cursor) < 1e-6
        assert abs(entry["duration"] * 30 - round(entry["duration"] * 30)) < 1e-6, "not a whole number of frames"
        # speech + closing hold + the requested thinking pause all fit inside the beat
        assert entry["duration"] >= entry["speech_end"] + 0.6 + entry["thinking_pause_seconds"] - 1e-6
        cursor += entry["duration"]
    narration, rate = read_wav(tmp_path / "audio" / "narration.wav")
    assert abs(len(narration) / rate - cursor) < 1e-3
    assert report["sentence_count"] == 6 and report["atempo"] == 1.0
    expected_source = "measured" if granularity == "sentence" else None
    if expected_source:
        assert report["sentence_timing"]["measured"] == 6


@needs_ffmpeg
def test_rebuild_reuses_cached_clips(tmp_path):
    lesson = make_lesson()
    first = audio.build_audio(lesson, tmp_path, "silent", log=lambda *_: None)
    second = audio.build_audio(lesson, tmp_path, "silent", log=lambda *_: None)
    assert first["clips_synthesized"] == 3 and second["clips_synthesized"] == 0


@needs_ffmpeg
def test_target_duration_is_refused_when_it_needs_audible_retiming(tmp_path):
    lesson = make_lesson()
    natural = audio.build_audio(lesson, tmp_path, "silent", log=lambda *_: None)["final_duration"]
    with pytest.raises(audio.PacingError, match="change the script or the target"):
        audio.build_audio(lesson, tmp_path, "silent", audio.BuildOptions(target_seconds=natural * 2),
                          log=lambda *_: None)


@needs_ffmpeg
def test_captions_cover_every_sentence_in_order(tmp_path):
    audio.build_audio(make_lesson(), tmp_path, "silent", log=lambda *_: None)
    vtt = (tmp_path / "output" / "captions.vtt").read_text()
    assert vtt.startswith("WEBVTT") and vtt.count("-->") == 6
    assert vtt.index("Take a square") < vtt.index("Count them.") < vtt.index("Add the coefficients")


# ── bridge ────────────────────────────────────────────────────────────────────

def test_lesson_becomes_a_valid_engine_storyboard():
    board = bridge.lesson_to_storyboard(make_lesson())
    scenes = board["visual_storyboard"]
    assert len(scenes) == 3 and [s["scene_index"] for s in scenes] == [1, 2, 3]
    # narration is carried over verbatim, one cue per sentence
    assert [c["cue"] for c in scenes[1]["narration_cues"]] == \
        ["Here are two tiles and three more.", "Count them.", "What do you get?"]
    # every shown element exists in its own scene (per-scene renders are isolated)
    for scene in scenes:
        ids = {e["id"] for e in scene["elements"]}
        shown = {ev["target"] for cue in scene["narration_cues"] for ev in (cue["animation_events"] or [])}
        assert shown == ids
    assert scenes[1]["wait_time"] == pytest.approx(2.6)  # closing hold + thinking pause


def test_storyboard_transpiles_to_valid_python():
    code = bridge.transpile(bridge.lesson_to_storyboard(make_lesson()))
    compile(code, "<transpiled>", "exec")
    assert "class STEMAnimation" in code and "from viz_helpers import *" in code


def test_storyboard_to_lesson_strips_pacing_tags_and_round_trips_the_words():
    lesson = make_lesson()
    board = bridge.lesson_to_storyboard(lesson)
    board["visual_storyboard"][0]["narration_cues"][0]["cue"] += " [pause]"
    back = bridge.storyboard_to_lesson(board)
    original = [b.narration for _, b in lesson.beats()]
    assert [b.narration for _, b in back.beats()] == original
    assert back.chapters[0].beats[0].equation == "A = x^2"


# ── shared layout probe ───────────────────────────────────────────────────────

def test_probe_lines_are_parsed_and_only_proven_classes_count():
    log = ("noise\nLAYOUT_VIOLATION: overlap Text('a') at [0.0,1.0] x Text('b') at [0.0,0.9] depth 1x1 after play#2\n"
           "LAYOUT_VIOLATION: shape-overlap Circle x Square depth 1.00x1.00 after play#3\n"
           "LAYOUT_VIOLATION: text-over-shape MathTex('16') at [0.0,0.0] is crossed by Line after play#4\n")
    found = layout_probe.parse(log)
    assert [f["kind"] for f in found] == ["overlap", "shape-overlap", "text-over-shape"]
    assert [f["counted"] for f in found] == [True, False, True]


def test_probe_snippet_is_valid_python():
    compile(layout_probe.PROBE_SNIPPET, "<probe>", "exec")


# ── renderer switch and ts integration ────────────────────────────────────────

def test_renderer_ts_dir_discovery():
    from lessonforge.longform import build as B
    ts_dir = B.find_renderer_ts_dir()
    assert ts_dir is not None
    assert ts_dir.name == "renderer-ts"
    assert (ts_dir / "package.json").exists()


def test_render_chapters_respects_renderer_switch(tmp_path, monkeypatch):
    from pathlib import Path
    from lessonforge import knobs
    from lessonforge.longform import build as B

    lesson = make_lesson()
    calls = []

    def mock_ts(lesson_dir, lesson=None, **kwargs):
        calls.append(("ts", lesson_dir, kwargs))
        return {1: Path(lesson_dir) / "media" / "C01" / "videos" / "ts" / "720p30" / "C01.mp4"}

    monkeypatch.setattr(B, "render_chapters_ts", mock_ts)

    # 1. Explicit argument renderer="ts"
    res1 = B.render_chapters(tmp_path, lesson, renderer="ts")
    assert calls[-1][0] == "ts"
    assert 1 in res1

    # 2. Via knob LESSONFORGE_RENDERER="ts"
    with knobs.applied({"LESSONFORGE_RENDERER": "ts"}):
        res2 = B.render_chapters(tmp_path, lesson)
        assert calls[-1][0] == "ts"
        assert 1 in res2

