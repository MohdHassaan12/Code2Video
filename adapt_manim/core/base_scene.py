"""
Base TeachingScene module.
Provides the 6x6 discrete visual anchor grid, lecture sidebar layout,
and standardized placement primitives based on Code2Video (Section 4.3 and Appendix A.2.7).
"""

from typing import Dict, List, Tuple, Optional
import numpy as np


TEACHING_SCENE_CODE = '''from manim import *
import numpy as np
import shutil

# Graceful fallback for environments without system LaTeX installed
if not shutil.which("latex"):
    class SafeMathTex(Text):
        """Pango-based Unicode fallback for MathTex when LaTeX binary is absent."""
        def __init__(self, *tex_strings, **kwargs):
            full_str = " ".join(str(s) for s in tex_strings)
            clean = (full_str
                     .replace(r"\\\\text{", "").replace(r"\\text{", "")
                     .replace(r"\\\\mathbf{", "").replace(r"\\mathbf{", "")
                     .replace(r"\\\\hat{", "").replace(r"\\hat{", "")
                     .replace(r"\\\\omega", "ω").replace(r"\\omega", "ω")
                     .replace(r"\\\\theta", "θ").replace(r"\\theta", "θ")
                     .replace(r"\\\\frac{", "").replace(r"\\frac{", "")
                     .replace(r"}{", "/")
                     .replace(r"}", "")
                     .replace(r"\\\\|", "‖").replace(r"\\|", "‖")
                     .replace(r"\\\\min", "min").replace(r"\\min", "min")
                     .replace(r"\\\\int", "∫").replace(r"\\int", "∫")
                     .replace(r"\\\\infty", "∞").replace(r"\\infty", "∞")
                     .replace(r"\\\\partial", "∂").replace(r"\\partial", "∂")
                     .replace(r"\\\\mathcal{L}", "L").replace(r"\\mathcal{L}", "L")
                     .replace("^2", "²").replace("^T", "ᵀ"))
            super().__init__(clean, **kwargs)
    MathTex = SafeMathTex
    Tex = SafeMathTex

class TeachingScene(Scene):
    """
    Standardized pedagogical scene template.
    Features:
      - Left-side lecture panel for conceptual bullet points (Mayer's Dual Coding & Signaling)
      - Right-side 6x6 visual anchor grid (A1 to F6) for discrete layout stabilization
      - Standardized placement methods (place_at_grid, place_in_area)
    """

    def setup_layout(self, title_text, lecture_lines):
        # Base canvas styling
        self.camera.background_color = "#000000"
        
        # Section title at top
        self.title = Text(title_text, font_size=28, color=WHITE).to_edge(UP, buff=0.4)
        self.add(self.title)

        # Left-side lecture lines
        lecture_texts = []
        for line in lecture_lines:
            # Normalize bullet prefix
            clean_line = line if line.startswith(("-", "•")) else f"- {line}"
            lecture_texts.append(Text(clean_line, font_size=20, color=WHITE))
            
        self.lecture = VGroup(*lecture_texts).arrange(DOWN, aligned_edge=LEFT, buff=0.35).scale(0.85)
        self.lecture.to_edge(LEFT, buff=0.4)
        self.add(self.lecture)

        # Discretized 6x6 Visual Anchor Grid (Right side canvas)
        self.grid = {}
        rows = ["A", "B", "C", "D", "E", "F"] # Top to bottom
        cols = ["1", "2", "3", "4", "5", "6"] # Left to right

        for i, row in enumerate(rows):
            for j, col in enumerate(cols):
                x = 0.5 + j * 1.0   # Span from x=0.5 to x=5.5
                y = 2.2 - i * 1.0   # Span from y=2.2 to y=-2.8
                self.grid[f"{row}{col}"] = np.array([x, y, 0.0])

        self.occupied_anchors = {}

    def place_at_grid(self, mobject, grid_pos, scale_factor=1.0):
        """Place an element centered at a specific grid anchor (e.g. 'B2')."""
        if grid_pos not in self.grid:
            raise KeyError(f"Grid coordinate '{grid_pos}' invalid. Must be in A1-F6.")
        mobject.scale(scale_factor)
        mobject.move_to(self.grid[grid_pos])
        self.occupied_anchors[grid_pos] = mobject
        return mobject

    def place_in_area(self, mobject, top_left, bottom_right, scale_factor=1.0):
        """Place an element centered within a bounding box formed by two anchors."""
        if top_left not in self.grid or bottom_right not in self.grid:
            raise KeyError(f"Area coordinates '{top_left}'-'{bottom_right}' invalid.")
        tl_pos = self.grid[top_left]
        br_pos = self.grid[bottom_right]

        center_x = (tl_pos[0] + br_pos[0]) / 2.0
        center_y = (tl_pos[1] + br_pos[1]) / 2.0
        center = np.array([center_x, center_y, 0.0])

        mobject.scale(scale_factor)
        mobject.move_to(center)
        self.occupied_anchors[f"{top_left}:{bottom_right}"] = mobject
        return mobject

    def highlight_lecture(self, line_index, highlight_color="#58C4DD", run_time=0.4):
        """
        Signaling mechanism (Mayer's signaling principle):
        Highlight the active lecture bullet while playing corresponding animation.
        """
        if 0 <= line_index < len(self.lecture):
            self.play(
                self.lecture[line_index].animate.set_color(highlight_color),
                run_time=run_time
            )

    def reset_lecture_colors(self):
        """Reset all lecture bullets to neutral white."""
        for line in self.lecture:
            line.set_color(WHITE)
'''


class BaseSceneHelper:
    """Python-side utilities for the 6x6 visual anchor system and occupancy analysis."""

    ROWS = ["A", "B", "C", "D", "E", "F"]
    COLS = ["1", "2", "3", "4", "5", "6"]

    @classmethod
    def get_all_anchor_names(cls) -> List[str]:
        return [f"{r}{c}" for r in cls.ROWS for c in cls.COLS]

    @classmethod
    def get_anchor_coordinates(cls, anchor: str) -> np.ndarray:
        if len(anchor) != 2 or anchor[0] not in cls.ROWS or anchor[1] not in cls.COLS:
            raise ValueError(f"Invalid anchor coordinate: {anchor}")
        i = cls.ROWS.index(anchor[0])
        j = cls.COLS.index(anchor[1])
        x = 0.5 + j * 1.0
        y = 2.2 - i * 1.0
        return np.array([x, y, 0.0])

    @classmethod
    def get_area_points(cls, top_left: str, bottom_right: str) -> List[str]:
        """Returns all anchor points covered by an area bounding box."""
        r_start = cls.ROWS.index(top_left[0])
        r_end = cls.ROWS.index(bottom_right[0])
        c_start = cls.COLS.index(top_left[1])
        c_end = cls.COLS.index(bottom_right[1])

        covered = []
        for r in range(min(r_start, r_end), max(r_start, r_end) + 1):
            for c in range(min(c_start, c_end), max(c_start, c_end) + 1):
                covered.append(f"{cls.ROWS[r]}{cls.COLS[c]}")
        return covered

    @classmethod
    def find_nearest_vacant_anchor(cls, target_anchor: str, occupied_anchors: List[str]) -> Optional[str]:
        """Finds the nearest unoccupied anchor to resolve collisions deterministically."""
        if target_anchor not in occupied_anchors:
            return target_anchor

        target_coord = cls.get_anchor_coordinates(target_anchor)
        all_anchors = cls.get_all_anchor_names()
        vacant = [a for a in all_anchors if a not in occupied_anchors]

        if not vacant:
            return None

        # Sort vacant anchors by Euclidean distance
        vacant.sort(key=lambda a: float(np.linalg.norm(cls.get_anchor_coordinates(a) - target_coord)))
        return vacant[0]
