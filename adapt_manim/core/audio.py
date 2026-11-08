"""
Audio Narration and Speech-Visual Synchronization Module.
Synthesizes spoken narration tracks corresponding to Storyboard LectureCues
and muxes them synchronously into rendered Manim video clips (LLM2Manim Section II.B).
"""

import os
import subprocess
import shutil
import wave
from typing import List, Dict, Optional, Tuple, Any
from adapt_manim.core.types import LectureCue, StoryboardSection


def get_audio_duration(file_path: str) -> float:
    """Returns exact audio duration in seconds via wave or ffprobe."""
    if not os.path.exists(file_path):
        return 0.0

    # Try standard library wave module first (for standard WAV files)
    if file_path.lower().endswith(".wav"):
        try:
            with wave.open(file_path, "r") as wf:
                frames = wf.getnframes()
                rate = wf.getframerate()
                if rate > 0:
                    return round(frames / float(rate), 3)
        except Exception:
            pass

    # Fallback to ffprobe
    try:
        cmd = [
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", file_path
        ]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if res.returncode == 0 and res.stdout.strip():
            return round(float(res.stdout.strip()), 3)
    except Exception:
        pass

    return 0.0


class NarrationEngine:
    """Generates audio speech tracks and muxes them with video animations."""

    get_audio_duration = staticmethod(get_audio_duration)

    @classmethod
    def synthesize_cue_audio(
        cls,
        text: str,
        output_wav_path: str,
        voice: Optional[str] = None
    ) -> Tuple[bool, float]:
        """
        Synthesizes text into audio using edge-tts (cross-platform neural voice),
        macOS native 'say' command fallback, or silent audio buffer fallback.
        Returns: Tuple[bool, float] -> (success, duration_sec)
        """
        os.makedirs(os.path.dirname(output_wav_path), exist_ok=True)

        # 1. Edge-TTS neural speech (cross-platform modern natural voice)
        try:
            import edge_tts
            import asyncio
            voice_name = voice or "en-US-ChristopherNeural"
            temp_mp3 = output_wav_path.replace(".wav", "_edge_temp.mp3")

            async def _edge_speak():
                comm = edge_tts.Communicate(text, voice_name)
                await comm.save(temp_mp3)

            asyncio.run(_edge_speak())
            if os.path.exists(temp_mp3) and os.path.getsize(temp_mp3) > 0:
                cmd_conv = [
                    "ffmpeg", "-y", "-i", temp_mp3,
                    "-acodec", "pcm_s16le", "-ar", "44100", "-ac", "1", output_wav_path
                ]
                subprocess.run(cmd_conv, capture_output=True, check=True)
                if os.path.exists(temp_mp3):
                    os.remove(temp_mp3)
                duration = get_audio_duration(output_wav_path)
                return True, duration
        except Exception:
            pass

        # 2. macOS native 'say' fallback
        if shutil.which("say"):
            aiff_temp = output_wav_path.replace(".wav", "_say_temp.aiff")
            cmd_say = ["say"]
            say_voice = voice if (voice and "Neural" not in voice) else "Samantha"
            cmd_say.extend(["-v", say_voice, "-o", aiff_temp, text])

            try:
                res_say = subprocess.run(cmd_say, capture_output=True, text=True, timeout=15)
                if res_say.returncode == 0 and os.path.exists(aiff_temp):
                    cmd_conv = [
                        "ffmpeg", "-y", "-i", aiff_temp,
                        "-acodec", "pcm_s16le", "-ar", "44100", "-ac", "1", output_wav_path
                    ]
                    res_conv = subprocess.run(cmd_conv, capture_output=True, text=True, timeout=10)
                    if os.path.exists(aiff_temp):
                        os.remove(aiff_temp)
                    if res_conv.returncode == 0 and os.path.exists(output_wav_path):
                        duration = get_audio_duration(output_wav_path)
                        return True, duration
            except Exception:
                pass

        # 3. Fallback: generate silent audio spacer via ffmpeg
        ok = cls._create_silent_wav(output_wav_path, duration_sec=2.0)
        return ok, 2.0

    @classmethod
    def _create_silent_wav(cls, output_path: str, duration_sec: float = 2.0) -> bool:
        """Generates silent audio spacer via ffmpeg."""
        cmd = [
            "ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono",
            "-t", str(duration_sec), "-q:a", "9", "-acodec", "pcm_s16le", output_path
        ]
        res = subprocess.run(cmd, capture_output=True)
        return res.returncode == 0 and os.path.exists(output_path)

    @classmethod
    def synthesize_section_narration(
        cls,
        section: StoryboardSection,
        output_dir: str = "demo_outputs/audio"
    ) -> List[Dict[str, Any]]:
        """
        Synthesizes audio for all lecture cues in a section.
        Returns: List[Dict[str, Any]] containing:
          - cue_id: str
          - wav_path: str
          - duration_sec: float
        """
        os.makedirs(output_dir, exist_ok=True)
        cue_metadata = []

        for idx, cue in enumerate(section.cues):
            clean_text = cue.text.lstrip("- •").strip()
            wav_path = os.path.join(output_dir, f"{cue.cue_id}.wav")
            success, duration = cls.synthesize_cue_audio(clean_text, wav_path)
            if os.path.exists(wav_path):
                cue_metadata.append({
                    "cue_id": cue.cue_id,
                    "wav_path": wav_path,
                    "duration_sec": duration
                })

        return cue_metadata

    @classmethod
    def mux_video_and_audio(
        cls,
        video_path: str,
        audio_path: str,
        output_muxed_path: str
    ) -> bool:
        """
        Muxes video and audio track using ffmpeg with AAC audio encoding.
        Uses -c:v copy and -c:a aac with clean shortest termination.
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
