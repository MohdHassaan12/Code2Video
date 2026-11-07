"""
Parallel Runner Module.
Executes parallel section code synthesis and stitches section scenes into
a coherent complete educational lecture video (Code2Video Section 4.2).
"""

import os
import subprocess
from concurrent.futures import ThreadPoolExecutor
from typing import List, Dict, Optional, Any
from adapt_manim.core.types import Storyboard, StoryboardSection, SectionResult
from adapt_manim.core.ledger import SymbolLedgerManager
from adapt_manim.coding.coder import ManimCoder


class ParallelRunner:
    """Orchestrates independent section synthesis and final compilation."""

    def __init__(self, output_dir: str = "demo_outputs"):
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)

    def generate_all_sections_parallel(
        self,
        storyboard: Storyboard,
        ledger_manager: SymbolLedgerManager,
        llm_client: Optional[Any] = None,
        max_workers: int = 4
    ) -> Dict[str, str]:
        """Synthesizes code for all sections in parallel."""
        results: Dict[str, str] = {}

        def _synthesize_task(sec: StoryboardSection):
            code = ManimCoder.generate_section_code(sec, ledger_manager, llm_client)
            return sec.id, code

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(_synthesize_task, sec) for sec in storyboard.sections]
            for f in futures:
                sec_id, code = f.result()
                results[sec_id] = code

        return results

    def combine_section_codes(self, section_codes: Dict[str, str], topic: str) -> str:
        """Combines section codes into a single multi-scene Manim script."""
        from adapt_manim.core.base_scene import TEACHING_SCENE_CODE

        combined_lines = [
            f"# Auto-generated Complete Lecture Script: {topic}",
            "from manim import *",
            "import numpy as np",
            "",
            TEACHING_SCENE_CODE,
            ""
        ]

        # Append each scene class, omitting redundant imports and base class definitions
        for sec_id, code in section_codes.items():
            lines = code.split("\n")
            in_class = False
            class_lines = []
            for line in lines:
                if line.startswith("class ") and "Scene(TeachingScene):" in line:
                    in_class = True
                if in_class:
                    class_lines.append(line)
            combined_lines.extend(class_lines)
            combined_lines.append("\n")

        return "\n".join(combined_lines)
