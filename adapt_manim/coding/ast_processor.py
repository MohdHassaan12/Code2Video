"""
AST Processor Module.
Parses, analyzes, sanitizes, and mutates Manim Python code using AST manipulation.
Provides block extraction, deprecated API auto-migration, and surgical code patching
for ScopeRefine++ (Code2Video Section 4.2).
"""

import ast
import re
from typing import List, Dict, Optional, Tuple


class AstProcessor:
    """Performs static analysis and surgical AST repairs on Manim code."""

    DEPRECATED_METHOD_MAP = {
        "resize": "scale",
        "ShowCreation": "Create",
        "FadeInAndShift": "FadeIn",
        "FadeOutAndShift": "FadeOut",
        "SetColor": "set_color",
    }

    @classmethod
    def check_syntax(cls, code: str) -> Optional[Tuple[str, int, str]]:
        """
        Validates syntax using Python ast.parse.
        Returns None if valid, or (error_msg, line_number, offending_line).
        """
        try:
            ast.parse(code)
            return None
        except SyntaxError as e:
            line_num = e.lineno or 1
            code_lines = code.split("\n")
            offending = code_lines[line_num - 1] if 0 <= line_num - 1 < len(code_lines) else ""
            return (e.msg, line_num, offending)

    @classmethod
    def auto_migrate_deprecated_apis(cls, code: str) -> Tuple[str, List[str]]:
        """
        0-token deterministic auto-fixer:
        Replaces deprecated or hallucinated Manim method names via regex / AST.
        """
        modifications = []
        modified_code = code

        for old_name, new_name in cls.DEPRECATED_METHOD_MAP.items():
            pattern = rf"\.{old_name}\("
            if re.search(pattern, modified_code):
                modified_code = re.sub(pattern, f".{new_name}(", modified_code)
                modifications.append(f"Auto-migrated .{old_name}() -> .{new_name}()")

            # Also check functions called as classes, e.g. ShowCreation(obj)
            pattern_cls = rf"\b{old_name}\("
            if re.search(pattern_cls, modified_code):
                modified_code = re.sub(pattern_cls, f"{new_name}(", modified_code)
                modifications.append(f"Auto-migrated {old_name}() -> {new_name}()")

        return modified_code, modifications

    @classmethod
    def extract_lecture_blocks(cls, code: str) -> Dict[int, Tuple[int, int, str]]:
        """
        Extracts line ranges and code content for each lecture animation block:
        # === Animation for Lecture Line k ===
        Returns mapping: line_index -> (start_lineno, end_lineno, block_code)
        """
        lines = code.split("\n")
        block_starts = []

        # Find markers
        pattern = re.compile(r"#\s*===\s*Animation for Lecture Line\s*(\d+)\s*===", re.IGNORECASE)
        for idx, line in enumerate(lines):
            match = pattern.search(line)
            if match:
                block_num = int(match.group(1))
                block_starts.append((block_num, idx))

        blocks: Dict[int, Tuple[int, int, str]] = {}
        for i in range(len(block_starts)):
            block_num, start_idx = block_starts[i]
            end_idx = block_starts[i + 1][1] if i + 1 < len(block_starts) else len(lines)
            block_content = "\n".join(lines[start_idx:end_idx])
            # 1-based line numbers for IDE/traceback consistency
            blocks[block_num] = (start_idx + 1, end_idx, block_content)

        return blocks

    @classmethod
    def replace_line(cls, code: str, line_number: int, replacement: str) -> str:
        """Surgically replaces a single line (1-based index)."""
        lines = code.split("\n")
        if 1 <= line_number <= len(lines):
            lines[line_number - 1] = replacement
            return "\n".join(lines)
        return code

    @classmethod
    def replace_block(cls, code: str, block_number: int, replacement_block: str) -> str:
        """Surgically replaces an entire lecture animation block."""
        blocks = cls.extract_lecture_blocks(code)
        if block_number in blocks:
            start_line, end_line, _ = blocks[block_number]
            lines = code.split("\n")
            # Replace lines from start_line-1 to end_line
            new_lines = lines[:start_line - 1] + [replacement_block] + lines[end_line:]
            return "\n".join(new_lines)
        return code

    @classmethod
    def find_grid_call_at_line(cls, code: str, line_number: int) -> Optional[Tuple[str, str, str]]:
        """
        Parses line to find place_at_grid(obj, 'B2') call.
        Returns (obj_name, current_anchor, full_match).
        """
        lines = code.split("\n")
        if 1 <= line_number <= len(lines):
            line = lines[line_number - 1]
            match = re.search(r"self\.place_at_grid\(\s*([a-zA-Z0-9_]+)\s*,\s*['\"]([A-F][1-6])['\"]", line)
            if match:
                return (match.group(1), match.group(2), match.group(0))
        return None
