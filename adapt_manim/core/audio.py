"""
Audio Narration and Speech-Visual Synchronization Module.
Synthesizes spoken narration tracks corresponding to Storyboard LectureCues
and muxes them synchronously into rendered Manim video clips (LLM2Manim Section II.B).
"""

import os
import subprocess
import shutil
from typing import List, Dict, Optional, Tuple
from adapt_manim.core.types import LectureCue, StoryboardSection


class NarrationEngine:
    """Generates audio speech tracks and muxes them with video animations."""

    @classmethod
    def synthesize_cue_audio(
        cls,
        text: str,
        output_wav_path: str,
        voice: Optional[str] = "Samantha"
    ) -> bool:
        """
        Synthesizes text into audio using macOS 'say' command or fallback synthesizer.
        """
        os.makedirs(os.path.dirname(output_wav_path), exist_ok=True)

        if shutil.which("say"):
            aiff_temp = output_wav_path.replace(".wav", ".aiff")
            cmd_say = ["say"]
            if voice:
                cmd_say.extend(["-v", voice])
            cmd_say.extend(["-o", aiff_temp, text])

            try:
                res_say = subprocess.run(cmd_say, capture_output=True, text=True, timeout=15)
                if res_say.returncode == 0 and os.path.exists(aiff_temp):
                    # Convert AIFF to WAV via ffmpeg
                    cmd_conv = ["ffmpeg", "-y", "-i", aiff_temp, output_wav_path]
                    res_conv = subprocess.run(cmd_conv, capture_output=True, text=True, timeout=10)
                    if os.path.exists(aiff_temp):
                        os.remove(aiff_temp)
                    return res_conv.returncode == 0
            except Exception:
                pass

        # Fallback: create silent audio buffer if TTS fails or on non-macOS
        return cls._create_silent_wav(output_wav_path, duration_sec=2.0)

    @classmethod
    def _create_silent_wav(cls, output_path: str, duration_sec: float = 2.0) -> bool:
        """Generates silent audio spacer via ffmpeg."""
        cmd = [
            "ffmpeg", "-y", "-f", "lavfi", "-i", f"anullsrc=r=44100:cl=mono",
            "-t", str(duration_sec), "-q:a", "9", "-acodec", "pcm_s16le", output_path
        ]
        res = subprocess.run(cmd, capture_output=True)
        return res.returncode == 0

    @classmethod
    def synthesize_section_narration(
        cls,
        section: StoryboardSection,
        output_dir: str = "demo_outputs/audio"
    ) -> List[str]:
        """Synthesizes audio for all lecture cues in a section."""
        os.makedirs(output_dir, exist_ok=True)
        audio_files = []

        for idx, cue in enumerate(section.cues):
            clean_text = cue.text.lstrip("- •").strip()
            wav_path = os.path.join(output_dir, f"{cue.cue_id}.wav")
            cls.synthesize_cue_audio(clean_text, wav_path)
            if os.path.exists(wav_path):
                audio_files.append(wav_path)

        return audio_files

    @classmethod
    def mux_video_and_audio(
        cls,
        video_path: str,
        audio_path: str,
        output_muxed_path: str
    ) -> bool:
        """
        Muxes video and audio track using ffmpeg with AAC audio encoding.
        """
        if not os.path.exists(video_path) or not os.path.exists(audio_path):
            return False

        os.makedirs(os.path.dirname(output_muxed_path), exist_ok=True)
        cmd = [
            "ffmpeg", "-y",
            "-i", video_path,
            "-i", audio_path,
            "-c:v", "copy",
            "-c:a", "aac",
            "-shortest",
            output_muxed_path
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        return res.returncode == 0 and os.path.exists(output_muxed_path)

