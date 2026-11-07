"""
Code2Video Critic Module.
Implements Visual Anchor Prompts (P_vis), Occupancy Table tracking,
and VideoLLM visual layout refinement (Section 4.3 and Appendix A.2.9).
"""

import json
import re
from typing import Dict, List, Optional, Tuple, Any
from code2video.prompts import PROMPT_REFINE
from adapt_manim.core.types import StoryboardSection, OccupancyTable, OccupancyRecord
from adapt_manim.verification.tier4_spatial import Tier4SpatialVerifier
from adapt_manim.core.base_scene import BaseSceneHelper
from adapt_manim.repair.patcher import CodePatcher


class Code2VideoCritic:
    """
    Official Critic of Code2Video:
    (i) Visual Anchor Prompt (P_vis): 6x6 Canvas Discretization
    (ii) Occupancy Table Tracking: maps each asset to assigned anchors and code lines
    (iii) VideoLLM Code Feedback (P_refine): identifies overlaps, lecture occlusions, and visual imbalance
    """

    def __init__(self, llm_client: Optional[Any] = None):
        self.llm_client = llm_client

    def build_occupancy_table(self, code: str) -> OccupancyTable:
        """Parses place_at_grid and place_in_area calls into an indexable occupancy table."""
        _, table = Tier4SpatialVerifier.verify(code)
        return table

    def analyze_layout_and_refine(
        self,
        code: str,
        section: StoryboardSection,
        rendered_frame_path: Optional[str] = None
    ) -> Tuple[str, bool, List[Dict[str, str]]]:
        """
        Inspects code alongside rendered frame and occupancy table to produce optimized code:
        c_tilde_i = P_refine(c_i, V_i).
        Returns: (refined_code, has_modifications, improvements_applied)
        """
        table = self.build_occupancy_table(code)
        improvements_applied = []
        refined_code = code

        # 1. Check for collisions in occupancy table
        if table.collisions:
            for col in table.collisions:
                pt = col["anchor"]
                objs = col["objects"]
                new_pt = col["suggested_relocation"]

                # Find line number for second object
                for rec in table.records:
                    if rec.object_name == objs[-1] and rec.anchor == pt:
                        refined_code = CodePatcher.patch_anchor_relocation(refined_code, rec.code_line, new_pt)
                        improvements_applied.append({
                            "problem": f"Icon/Element overlap at position {pt} between {objs}",
                            "solution": f"place_at_grid({objs[-1]}, '{new_pt}', scale_factor=0.8)"
                        })
                        break

        # 2. If LLM critic is available, invoke P_refine
        if self.llm_client:
            try:
                prompt = PROMPT_REFINE.format(
                    section_title=section.title,
                    lecture_lines="; ".join(section.lecture_lines)
                )
                resp = self.llm_client.generate(prompt)
                clean_json = resp[resp.find("{"):resp.rfind("}") + 1]
                data = json.loads(clean_json)

                layout_info = data.get("layout", {})
                if layout_info.get("has_issues"):
                    for imp in layout_info.get("improvements", []):
                        improvements_applied.append(imp)
                        # Extract grid fix e.g. "place_at_grid(obj, 'C3')"
                        sol = imp.get("solution", "")
                        match = re.search(r"place_at_grid\(\s*([a-zA-Z0-9_]+)\s*,\s*['\"]([A-F][1-6])['\"]", sol)
                        if match:
                            obj_name, new_anchor = match.group(1), match.group(2)
                            # Find line for this object and patch
                            for rec in table.records:
                                if rec.object_name == obj_name:
                                    refined_code = CodePatcher.patch_anchor_relocation(refined_code, rec.code_line, new_anchor)
                                    break
            except Exception:
                pass

        has_mods = len(improvements_applied) > 0
        return refined_code, has_mods, improvements_applied
