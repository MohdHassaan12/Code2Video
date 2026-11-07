"""
Unit tests for Audio Narration Engine and Video Stitcher.
"""

import os
import pytest
from adapt_manim.core.audio import NarrationEngine
from adapt_manim.coding.video_stitcher import VideoStitcher


def test_narration_audio_synthesis(tmp_path):
    out_wav = str(tmp_path / "test_cue.wav")
    success = NarrationEngine.synthesize_cue_audio("Hello, world!", out_wav)
    assert success
    assert os.path.exists(out_wav)
    assert os.path.getsize(out_wav) > 0


def test_silent_wav_generation(tmp_path):
    out_wav = str(tmp_path / "silent.wav")
    success = NarrationEngine._create_silent_wav(out_wav, duration_sec=1.0)
    assert success
    assert os.path.exists(out_wav)
    assert os.path.getsize(out_wav) > 0


def test_audio_concatenation(tmp_path):
    wav1 = str(tmp_path / "cue1.wav")
    wav2 = str(tmp_path / "cue2.wav")
    NarrationEngine.synthesize_cue_audio("Section one.", wav1)
    NarrationEngine.synthesize_cue_audio("Section two.", wav2)

    combined_wav = str(tmp_path / "combined.wav")
    stitcher = VideoStitcher(script_path="", output_dir=str(tmp_path))
    res = stitcher._concat_audios([wav1, wav2], combined_wav)

    assert res is not None
    assert os.path.exists(combined_wav)
    assert os.path.getsize(combined_wav) > os.path.getsize(wav1)

