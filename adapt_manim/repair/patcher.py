"""
Surgical Code Patcher Module.
Applies surgical line replacements, block substitutions, and anchor mutations
without regenerating the entire file.
"""

from typing import Tuple, Optional
from adapt_manim.coding.ast_processor import AstProcessor
import re


class CodePatcher:
    """Applies surgical edits to Manim code."""

    @classmethod
    def patch_line(cls, code: str, line_number: int, replacement: str) -> str:
        """Replaces a specific line in code."""
        return AstProcessor.replace_line(code, line_number, replacement)

    @classmethod
    def patch_block(cls, code: str, block_number: int, replacement_block: str) -> str:
        """Replaces an entire lecture animation block."""
        return AstProcessor.replace_block(code, block_number, replacement_block)

    @classmethod
    def patch_anchor_relocation(cls, code: str, line_number: int, new_anchor: str) -> str:
        """
        Deterministically updates self.place_at_grid(obj, 'OLD') to 'NEW' at line_number.
        """
        lines = code.split("\n")
        if 1 <= line_number <= len(lines):
            line = lines[line_number - 1]
            updated_line = re.sub(
                r"(self\.place_at_grid\(\s*[a-zA-Z0-9_]+\s*,\s*['\"])[A-F][1-6](['\"])",
                rf"\g<1>{new_anchor}\g<2>",
                line
            )
            lines[line_number - 1] = updated_line
            return "\n".join(lines)
        return code

    @classmethod
    def patch_signaling(cls, code: str, block_number: int, line_index: int) -> str:
        """Inserts self.highlight_lecture(line_index) into block if missing."""
        blocks = AstProcessor.extract_lecture_blocks(code)
        if block_number in blocks:
            start_l, end_l, block_content = blocks[block_number]
            b_lines = block_content.split("\n")
            # Insert after the header comment
            insert_idx = 1 if len(b_lines) > 1 else 0
            indent = "        "
            b_lines.insert(insert_idx, f"{indent}self.highlight_lecture({line_index})")
            new_block = "\n".join(b_lines)
            return cls.patch_block(code, block_number, new_block)
        return code

