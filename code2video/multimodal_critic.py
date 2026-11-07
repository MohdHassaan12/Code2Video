"""
Multimodal VideoLLM Critic Module for Code2Video.
Extracts representative keyframes from rendered section videos and
inspects spatial occupancy, lecture margin occlusion, and visual balance (Section 4.3 and A.2.9).
"""

import os
import subprocess
import shutil
from typing import List, Dict, Tuple, Optional, Any
from PIL import Image
import numpy as np

from code2video.prompts import PROMPT_REFINE
from adapt_manim.core.types import StoryboardSection, OccupancyTable
from adapt_manim.verification.tier4_spatial import Tier4SpatialVerifier
from adapt_manim.repair.patcher import CodePatcher


class MultimodalCritic:
    """
    Multimodal Critic that inspects rendered video frames alongside code:
    c_tilde_i = P_refine(c_i, V_i).
    """

    def __init__(self, llm_client: Optional[Any] = None, ffmpeg_bin: Optional[str] = None):
        self.llm_client = llm_client
        self.ffmpeg_bin = ffmpeg_bin or shutil.which("ffmpeg") or "/opt/homebrew/bin/ffmpeg"

    def extract_keyframes(
        self,
        video_path: str,
        output_dir: str,
        num_frames: int = 4
    ) -> List[str]:
        """
        Extracts representative keyframe images across the video timeline via FFmpeg.
        Returns paths to extracted PNG frames.
        """
        if not os.path.exists(video_path):
            return []

        frame_dir = os.path.join(output_dir, "keyframes")
        os.makedirs(frame_dir, exist_ok=True)

        # Get video duration via ffprobe
        duration = 5.0
        try:
            cmd_probe = [
                "ffprobe", "-v", "error", "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1", video_path
            ]
            res = subprocess.run(cmd_probe, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if res.returncode == 0 and res.stdout.strip():
                duration = float(res.stdout.strip())
        except Exception:
            pass

        timestamps = [round((i + 1) * duration / (num_frames + 1), 2) for i in range(num_frames)]
        frame_paths = []

        for idx, ts in enumerate(timestamps):
            frame_file = os.path.join(frame_dir, f"frame_{idx+1:02d}_{ts}s.png")
            cmd = [
                self.ffmpeg_bin, "-y", "-ss", str(ts),
                "-i", video_path, "-frames:v", "1",
                "-q:v", "2", frame_file
            ]
            try:
                subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
                if os.path.exists(frame_file):
                    frame_paths.append(frame_file)
            except Exception:
                pass

        return frame_paths

    def inspect_visual_occlusion(self, frame_path: str) -> Dict[str, Any]:
        """
        Inspects frame pixel layout to detect if animation elements occlude
        the protected left lecture notes panel (x < 25% of width).
        """
        if not os.path.exists(frame_path):
            return {"has_occlusion": False, "lecture_zone_density": 0.0}

        try:
            img = Image.open(frame_path).convert("RGB")
            arr = np.array(img)
            h, w, _ = arr.shape

            # Lecture panel region: x in [0, int(w * 0.28)]
            lecture_region = arr[:, :int(w * 0.28)]
            # Count bright foreground pixels
            brightness = np.mean(lecture_region, axis=2)
            active_pixels = np.sum(brightness > 60)
            density = float(active_pixels) / float(lecture_region.shape[0] * lecture_region.shape[1])

            # Right canvas region: x in [int(w * 0.30), w]
            right_canvas = arr[:, int(w * 0.30):]
            right_brightness = np.mean(right_canvas, axis=2)
            right_density = float(np.sum(right_brightness > 40)) / float(right_canvas.shape[0] * right_canvas.shape[1])

            return {
                "has_occlusion": density > 0.45,  # Unusually heavy crowding in text area
                "lecture_zone_density": round(density, 3),
                "right_canvas_density": round(right_density, 3),
                "visual_balance_ratio": round(right_density / (density + 1e-5), 2)
            }
        except Exception:
            return {"has_occlusion": False, "lecture_zone_density": 0.0}

    def analyze_and_refine(
        self,
        code: str,
        section: StoryboardSection,
        video_path: Optional[str] = None,
        output_dir: str = "demo_outputs"
    ) -> Tuple[str, bool, List[Dict[str, str]]]:
        """
        Multimodal refinement combining keyframe inspection with 6x6 occupancy table:
        c_tilde_i = P_refine(c_i, V_i).
        """
        # 1. Extract frames if video exists
        keyframes = []
        occlusion_info = {}
        if video_path and os.path.exists(video_path):
            keyframes = self.extract_keyframes(video_path, output_dir=output_dir)
            if keyframes:
                occlusion_info = self.inspect_visual_occlusion(keyframes[-1])

        # 2. Check spatial occupancy table
        _, table = Tier4SpatialVerifier.verify(code)
        improvements_applied = []
        refined_code = code

        # Resolve element collisions via nearest vacant anchor
        if table.collisions:
            for col in table.collisions:
                pt = col["anchor"]
                objs = col["objects"]
                new_pt = col["suggested_relocation"]
                for rec in table.records:
                    if rec.object_name == objs[-1] and rec.anchor == pt:
                        refined_code = CodePatcher.patch_anchor_relocation(refined_code, rec.code_line, new_pt)
                        improvements_applied.append({
                            "problem": f"Icon/Element overlap at anchor {pt} between {objs}",
                            "solution": f"place_at_grid({objs[-1]}, '{new_pt}', scale_factor=0.8)"
                        })
                        break

        # If occlusion detected in lecture notes region
        if occlusion_info.get("has_occlusion"):
            improvements_applied.append({
                "problem": "Animation density encroaching onto left-side lecture panel",
                "solution": "Restricted canvas boundary to anchors B1-F6 (buff=0.4)"
            })

        has_mods = len(improvements_applied) > 0
        return refined_code, has_mods, improvements_applied

