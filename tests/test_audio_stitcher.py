"""
Unit tests for Audio Narration Engine, Dynamic Audio-Visual Pacing, and Video Stitcher.
Validates Mayer's Temporal Contiguity Principle and Cross-Platform TTS.
"""

import os
import pytest
from adapt_manim.core.audio import NarrationEngine, get_audio_duration
from adapt_manim.core.types import StoryboardSection, LectureCue
from adapt_manim.coding.ast_processor import AstProcessor
from adapt_manim.coding.video_stitcher import VideoStitcher


def test_get_audio_duration(tmp_path):
    """Verifies that get_audio_duration accurately probes WAV audio lengths."""
    wav_path = str(tmp_path / "duration_test.wav")
    ok = NarrationEngine._create_silent_wav(wav_path, duration_sec=1.5)
    assert ok
    assert os.path.exists(wav_path)

    dur = get_audio_duration(wav_path)
    assert dur == pytest.approx(1.5, rel=0.1)


def test_narration_audio_synthesis(tmp_path):
    """Verifies cue synthesis returns (success, duration) tuple with positive length."""
    out_wav = str(tmp_path / "test_cue.wav")
    success, duration = NarrationEngine.synthesize_cue_audio("Hello, world! Welcome to calculus.", out_wav)
    assert success is True
    assert duration > 0.0
    assert os.path.exists(out_wav)
    assert os.path.getsize(out_wav) > 0


def test_synthesize_section_narration_metadata(tmp_path):
    """Verifies section-level narration synthesis outputs structured metadata with durations."""
    section = StoryboardSection(
        id="intro",
        title="Introduction",
        cues=[
            LectureCue(cue_id="intro_c1", text="Welcome to today's lecture on vectors."),
            LectureCue(cue_id="intro_c2", text="Vectors have both magnitude and direction.")
        ]
    )
    meta = NarrationEngine.synthesize_section_narration(section, str(tmp_path / "audio_sec"))
    assert len(meta) == 2
    for item in meta:
        assert "cue_id" in item
        assert "wav_path" in item
        assert "duration_sec" in item
        assert item["duration_sec"] > 0.0
        assert os.path.exists(item["wav_path"])


def test_align_animation_durations_to_audio_expansion():
    """
    Tests dynamic pacing expansion:
    When visual run_time is shorter than audio duration, expands wait to match audio.
    """
    sample_code = '''
from manim import *

class IntroScene(Scene):
    def construct(self):
        # === Animation for Lecture Line 1 ===
        title = Text("Intro")
        self.play(Write(title), run_time=1.5)
        self.wait(0.5)

        # === Animation for Lecture Line 2 ===
        dot = Dot()
        self.play(FadeIn(dot), run_time=1.0)
        self.wait(1.0)
'''
    # Cue 1 needs 4.0s (currently 1.5 + 0.5 = 2.0s -> wait should expand by 2.0s to 2.5s)
    # Cue 2 needs 3.5s (currently 1.0 + 1.0 = 2.0s -> wait should expand by 1.5s to 2.5s)
    cue_durations = [4.0, 3.5]
    paced = AstProcessor.align_animation_durations_to_audio(sample_code, cue_durations, section_id="intro")

    assert "self.wait(2.5)" in paced
    assert "# === Animation for Lecture Line 1 ===" in paced
    assert "# === Animation for Lecture Line 2 ===" in paced


def test_align_animation_durations_to_audio_insertion_if_missing():
    """
    Tests dynamic pacing when self.wait() is missing in the lecture block:
    Should append self.wait(delta) cleanly.
    """
    sample_code = '''
from manim import *

class SceneOneScene(Scene):
    def construct(self):
        # === Animation for Lecture Line 1 ===
        title = Text("No Wait Line")
        self.play(Write(title), run_time=2.0)
'''
    cue_durations = [5.0]
    paced = AstProcessor.align_animation_durations_to_audio(sample_code, cue_durations, section_id="scene_one")

    assert "self.wait(3.0)" in paced


def test_align_animation_durations_to_audio_min_pause():
    """
    Tests dynamic pacing when visual run_time is already longer than audio:
    Preserves at least a minimum 0.5s pause.
    """
    sample_code = '''
from manim import *

class IntroScene(Scene):
    def construct(self):
        # === Animation for Lecture Line 1 ===
        title = Text("Long Animation")
        self.play(Write(title), run_time=5.0)
        self.wait(1.0)
'''
    # Audio is only 2.0s, existing is 6.0s
    cue_durations = [2.0]
    paced = AstProcessor.align_animation_durations_to_audio(sample_code, cue_durations, section_id="intro")

    # Should retain a valid pause
    assert "self.wait(1.0)" in paced or "self.wait(0.5)" in paced


def test_audio_concatenation(tmp_path):
    """Verifies FFmpeg concat demuxer cleanly concatenates audio tracks."""
    wav1 = str(tmp_path / "cue1.wav")
    wav2 = str(tmp_path / "cue2.wav")
    s1, _ = NarrationEngine.synthesize_cue_audio("Section one explanation.", wav1)
    s2, _ = NarrationEngine.synthesize_cue_audio("Section two summary.", wav2)
    assert s1 and s2

    combined_wav = str(tmp_path / "combined.wav")
    stitcher = VideoStitcher(script_path="", output_dir=str(tmp_path))
    res = stitcher._concat_audios([wav1, wav2], combined_wav)

    assert res is not None
    assert os.path.exists(combined_wav)
    assert os.path.getsize(combined_wav) > os.path.getsize(wav1)
