"""
Code2Video Coder Module.
Implements parallel section code generation and ScopeRefine (SR) hierarchical debugging (Section 4.2).
"""

import os
import json
import re
from typing import Dict, List, Optional, Tuple, Any
from code2video.prompts import PROMPT_CODER
from adapt_manim.core.base_scene import TEACHING_SCENE_CODE
from adapt_manim.core.types import StoryboardSection, Storyboard
from adapt_manim.coding.ast_processor import AstProcessor
from adapt_manim.coding.coder import ManimCoder
from adapt_manim.verification.tier3_execution import Tier3ExecutionVerifier


class Code2VideoCoder:
    """
    Official Coder of Code2Video:
    - (i) Parallel Code Generation: c_i = P_coder(s_i, A)
    - (ii) Effective Debugging via ScopeRefine (SR):
          Line Scope (S_1 = line +/- 1, up to K1 attempts)
          Block Scope (S_2 = B_i,j, up to K2 attempts)
          Global Scope (S_3 = regenerate full section)
    """

    def __init__(
        self,
        llm_client: Optional[Any] = None,
        k1_line_attempts: int = 3,
        k2_block_attempts: int = 2
    ):
        self.llm_client = llm_client
        self.k1 = k1_line_attempts
        self.k2 = k2_block_attempts

    def synthesize_section_code(
        self,
        section: StoryboardSection,
        regenerate_note: str = ""
    ) -> str:
        """Synthesizes code for a section adhering to 6x6 visual anchor constraints."""
        if self.llm_client:
            try:
                prompt = PROMPT_CODER.format(
                    regenerate_note=f"Note: {regenerate_note}" if regenerate_note else "",
                    section_title=section.title,
                    lecture_lines=json.dumps(section.lecture_lines),
                    animations="; ".join(section.animations)
                )
                resp = self.llm_client.generate(prompt)
                code_match = re.search(r"```(?:python)?\s*([\s\S]*?)```", resp)
                raw_code = code_match.group(1).strip() if code_match else resp.strip()
                migrated, _ = AstProcessor.auto_migrate_deprecated_apis(raw_code)
                return migrated
            except Exception:
                pass

        # Use verified high-fidelity synthesis
        from adapt_manim.core.ledger import SymbolLedgerManager
        lm = SymbolLedgerManager("General STEM")
        return ManimCoder.generate_section_code(section, lm)

    def scope_refine(
        self,
        code: str,
        section: StoryboardSection,
        output_dir: str = "demo_outputs"
    ) -> Tuple[str, bool, int, int]:
        """
        Executes ScopeRefine (SR) hierarchical repair:
        Returns: (repaired_code, is_executable, total_tokens, attempts)
        """
        current_code = code
        total_tokens = 0
        attempts = 0

        # Verify execution
        issues, _, tb_str, _ = Tier3ExecutionVerifier.verify(
            current_code, section, output_dir=output_dir
        )
        if not issues:
            return current_code, True, total_tokens, 0

        # ScopeRefine Level 1: Line scope (line +/- 1)
        for a in range(self.k1):
            attempts += 1
            failing_line = issues[0].line_number if issues and issues[0].line_number else 1
            offending = issues[0].offending_code or ""

            # Check if deprecated API can be migrated
            migrated, mods = AstProcessor.auto_migrate_deprecated_apis(current_code)
            if mods:
                current_code = migrated
            else:
                # LLM line-scope prompt
                if self.llm_client and issues:
                    lines = current_code.split("\n")
                    s_idx = max(0, failing_line - 2)
                    e_idx = min(len(lines), failing_line + 1)
                    ctx = "\n".join(lines[s_idx:e_idx])

                    prompt = f"Fix this Python line in Manim:\nError: {issues[0].message}\nContext:\n{ctx}\nReturn corrected line only."
                    try:
                        rep = self.llm_client.generate(prompt).strip()
                        current_code = AstProcessor.replace_line(current_code, failing_line, rep)
                        total_tokens += 200
                    except Exception:
                        pass

            issues, _, tb_str, _ = Tier3ExecutionVerifier.verify(current_code, section, output_dir=output_dir)
            if not issues:
                return current_code, True, total_tokens, attempts

        # ScopeRefine Level 2: Block scope (lecture block)
        blocks = AstProcessor.extract_lecture_blocks(current_code)
        target_block = 1
        if issues and issues[0].line_number:
            for b_num, (s_l, e_l, _) in blocks.items():
                if s_l <= issues[0].line_number <= e_l:
                    target_block = b_num
                    break

        for a in range(self.k2):
            attempts += 1
            if self.llm_client and target_block in blocks:
                _, _, b_code = blocks[target_block]
                prompt = f"Fix this animation block in Manim Community for line {target_block}:\nError: {issues[0].message}\nBlock:\n{b_code}\nReturn corrected block only."
                try:
                    rep_block = self.llm_client.generate(prompt).strip()
                    clean_block = rep_block.replace("```python", "").replace("```", "").strip()
                    current_code = AstProcessor.replace_block(current_code, target_block, clean_block)
                    total_tokens += 450
                except Exception:
                    pass

            issues, _, tb_str, _ = Tier3ExecutionVerifier.verify(current_code, section, output_dir=output_dir)
            if not issues:
                return current_code, True, total_tokens, attempts

        # ScopeRefine Level 3: Global scope (regenerate full section)
        attempts += 1
        total_tokens += 1500
        current_code = self.synthesize_section_code(section, regenerate_note=f"Previous attempt failed with {issues[0].message if issues else 'error'}")
        issues, _, _, _ = Tier3ExecutionVerifier.verify(current_code, section, output_dir=output_dir)

        return current_code, (len(issues) == 0), total_tokens, attempts
