"""
Video Stitcher Module.
Renders all sections of an educational storyboard, stitches the individual
scene video clips into a continuous full-length lecture video, and combines
synchronized narration tracks using FFmpeg (Code2Video Section 4.2).
"""

import os
import subprocess
import shutil
from typing import List, Dict, Optional, Tuple
from adapt_manim.core.types import Storyboard
from adapt_manim.core.audio import NarrationEngine


class VideoStitcher:
    """Renders all sections and stitches them into a final master video."""

    def __init__(
        self,
        script_path: str,
        output_dir: str = "demo_outputs",
        manim_bin: str = ".venv/bin/manim",
        quality: str = "ql"  # ql (480p), qm (720p), qh (1080p)
    ):
        self.script_path = script_path
        self.output_dir = output_dir
        self.manim_bin = manim_bin
        self.quality = quality
        os.makedirs(self.output_dir, exist_ok=True)

    def render_section_video(self, section_id: str) -> Optional[str]:
        """Renders an individual section scene to MP4."""
        class_name = f"{section_id.title().replace('_', '')}Scene"
        media_dir = os.path.join(self.output_dir, "media")

        cmd = [
            self.manim_bin,
            f"-{self.quality}",
            self.script_path,
            class_name,
            "--media_dir", media_dir
        ]

        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            if res.returncode == 0:
                # Find rendered MP4
                res_dir_name = "480p15" if self.quality == "ql" else ("720p30" if self.quality == "qm" else "1080p60")
                base_script_name = os.path.splitext(os.path.basename(self.script_path))[0]
                expected_path = os.path.join(
                    media_dir, "videos", base_script_name, res_dir_name, f"{class_name}.mp4"
                )
                if os.path.exists(expected_path):
                    return expected_path
        except Exception:
            pass

        return None

    def render_and_stitch_all(
        self,
        storyboard: Storyboard,
        narrate: bool = False
    ) -> Tuple[Optional[str], List[str]]:
        """
        Renders all section scenes in order and stitches them into a continuous master MP4.
        Returns: (master_video_path, list_of_section_video_paths)
        """
        section_video_paths: List[str] = []

        for sec in storyboard.sections:
            video_path = self.render_section_video(sec.id)
            if video_path and os.path.exists(video_path):
                # If narrate enabled, synthesize audio and mux into section clip
                if narrate:
                    audio_dir = os.path.join(self.output_dir, "audio", sec.id)
                    cue_audios = NarrationEngine.synthesize_section_narration(sec, audio_dir)
                    if cue_audios:
                        # Concat cue audios
                        combined_wav = os.path.join(audio_dir, f"{sec.id}_narration.wav")
                        self._concat_audios(cue_audios, combined_wav)

                        narrated_video = video_path.replace(".mp4", "_narrated.mp4")
                        if NarrationEngine.mux_video_and_audio(video_path, combined_wav, narrated_video):
                            section_video_paths.append(narrated_video)
                            continue

                section_video_paths.append(video_path)

        if not section_video_paths:
            return None, []

        # Stitch all section videos into single continuous video
        master_output_path = os.path.join(self.output_dir, "complete_lecture.mp4")
        stitched_path = self._concat_videos(section_video_paths, master_output_path)

        return stitched_path, section_video_paths

    def _concat_videos(self, video_paths: List[str], output_path: str) -> Optional[str]:
        """Concatenates videos using FFmpeg concat demuxer."""
        if len(video_paths) == 1:
            shutil.copy(video_paths[0], output_path)
            return output_path

        list_file = os.path.join(self.output_dir, "concat_list.txt")
        with open(list_file, "w") as f:
            for p in video_paths:
                f.write(f"file '{os.path.abspath(p)}'\n")

        cmd = [
            "ffmpeg", "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", list_file,
            "-c", "copy",
            output_path
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if os.path.exists(list_file):
            os.remove(list_file)

        return output_path if res.returncode == 0 and os.path.exists(output_path) else None

    def _concat_audios(self, audio_paths: List[str], output_path: str) -> Optional[str]:
        """Concatenates audio files using FFmpeg concat demuxer."""
        list_file = output_path + ".txt"
        with open(list_file, "w") as f:
            for p in audio_paths:
                f.write(f"file '{os.path.abspath(p)}'\n")

        cmd = [
            "ffmpeg", "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", list_file,
            "-c", "copy",
            output_path
        ]
        res = subprocess.run(cmd, capture_output=True)
        if os.path.exists(list_file):
            os.remove(list_file)

        return output_path if res.returncode == 0 and os.path.exists(output_path) else None
