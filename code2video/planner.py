"""
Code2Video Planner Module.
Implements Query-to-Storyboard decomposition and visual asset retrieval (Section 4.1).
"""

import json
from typing import List, Dict, Optional, Any
from code2video.prompts import PROMPT_OUTLINE, PROMPT_STORYBOARD, PROMPT_ASSET
from adapt_manim.core.types import Outline, OutlineSection, Storyboard, StoryboardSection, AudienceLevel
from adapt_manim.planning.outline_planner import OutlinePlanner
from adapt_manim.planning.storyboard_builder import StoryboardBuilder
from adapt_manim.core.ledger import SymbolLedgerManager


class Code2VideoPlanner:
    """
    Official Planner of Code2Video:
    (i) Outline Generation: Q -> O = {o_1, ..., o_n}
    (ii) Storyboard Construction: s_i <- P_storyboard(o_i)
    (iii) External Database Asset Retrieval: a_i <- P_asset(s_i)
    """

    def __init__(self, llm_client: Optional[Any] = None):
        self.llm_client = llm_client
        self.asset_cache: Dict[str, Any] = {}

    def generate_outline(
        self,
        topic: str,
        audience: str = "undergraduate",
        duration: float = 3.0
    ) -> Outline:
        """Step 1: Outline Generation considering intended audience."""
        aud_enum = AudienceLevel(audience) if audience in AudienceLevel._value2member_map_ else AudienceLevel.UNDERGRADUATE

        if self.llm_client:
            try:
                prompt = PROMPT_OUTLINE.format(topic=topic, audience=audience, duration=duration)
                resp = self.llm_client.generate(prompt)
                clean_json = resp[resp.find("{"):resp.rfind("}") + 1]
                data = json.loads(clean_json)
                return Outline(**data)
            except Exception:
                pass

        # Fallback to calibrated pedagogical outline generator
        return OutlinePlanner.generate_outline(topic, aud_enum, duration_minutes=duration)

    def generate_storyboards(
        self,
        outline: Outline,
        ledger_mgr: Optional[SymbolLedgerManager] = None
    ) -> Storyboard:
        """Step 2: Convert outline into detailed stepwise storyboards."""
        lm = ledger_mgr or SymbolLedgerManager(outline.topic)
        return StoryboardBuilder.build_storyboard(outline, lm, self.llm_client)

    def identify_visual_assets(self, storyboard: Storyboard) -> List[Dict[str, str]]:
        """Step 3: Asset Identification P_asset for external database retrieval."""
        assets = []
        sb_dict = storyboard.model_dump()

        if self.llm_client:
            try:
                prompt = PROMPT_ASSET.format(storyboard_data=json.dumps(sb_dict, indent=2))
                resp = self.llm_client.generate(prompt)
                clean_json = resp[resp.find("{"):resp.rfind("}") + 1]
                data = json.loads(clean_json)
                return data.get("assets", [])
            except Exception:
                pass

        # Built-in visual asset registry
        t_lower = storyboard.topic.lower()
        if "vector" in t_lower or "svm" in t_lower:
            assets.append({"name": "class_points", "search_query": "red blue cluster icons", "intended_section": "section_1"})
        elif "wave" in t_lower or "fourier" in t_lower:
            assets.append({"name": "signal_phasor", "search_query": "sine wave vector phasor", "intended_section": "section_2"})

        return assets
