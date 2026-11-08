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

    @classmethod
    def align_animation_durations_to_audio(
        cls,
        code: str,
        cue_durations: List[float],
        section_id: Optional[str] = None
    ) -> str:
        """
        Dynamically paces Manim animation blocks to synchronize with speech audio durations
        following Mayer's Temporal Contiguity Principle.
        
        For each lecture block (# === Animation for Lecture Line k ===):
          - Computes T_existing = sum(run_time) + sum(self.wait).
          - If T_existing < T_audio: adjusts or appends self.wait(round(T_audio - T_existing, 2)).
          - If T_existing >= T_audio: ensures a minimum 0.5s pause or scales run_time.
        """
        if not cue_durations:
            return code

        lines = code.split("\n")

        # If section_id is provided, find the class boundary for that section
        class_start_idx = 0
        class_end_idx = len(lines)
        if section_id:
            cls_pattern = re.compile(rf"class\s+{re.escape(section_id.title().replace('_', ''))}Scene\b", re.IGNORECASE)
            for idx, line in enumerate(lines):
                if cls_pattern.search(line):
                    class_start_idx = idx
                    for end_i in range(idx + 1, len(lines)):
                        if re.match(r"^class\s+", lines[end_i]):
                            class_end_idx = end_i
                            break
                    break

        # Extract lecture blocks within the target range
        pattern = re.compile(r"#\s*===\s*Animation for Lecture Line\s*(\d+)\s*===", re.IGNORECASE)
        block_starts = []
        for idx in range(class_start_idx, class_end_idx):
            m = pattern.search(lines[idx])
            if m:
                block_starts.append((int(m.group(1)), idx))

        if not block_starts:
            return code

        new_lines = list(lines)

        # Process blocks in reverse order so inserted lines don't invalidate earlier line indices
        for i in reversed(range(len(block_starts))):
            b_num, start_idx = block_starts[i]
            end_idx = block_starts[i + 1][1] if i + 1 < len(block_starts) else class_end_idx
            if b_num - 1 >= len(cue_durations):
                continue

            t_audio = float(cue_durations[b_num - 1])
            block_lines = new_lines[start_idx:end_idx]
            block_text = "\n".join(block_lines)

            # Detect indentation
            indent = "        "
            for bl in block_lines[1:]:
                if bl.strip():
                    indent = bl[:len(bl) - len(bl.lstrip())]
                    break

            # Calculate existing durations
            runs = [float(x) for x in re.findall(r"run_time\s*=\s*([0-9.]+)", block_text)]
            waits = [float(x) for x in re.findall(r"self\.wait\(\s*([0-9.]+)\s*\)", block_text)]
            t_existing = sum(runs) + sum(waits)
            delta = t_audio - t_existing

            wait_matches = list(re.finditer(r"self\.wait\(\s*([0-9.]+)\s*\)", block_text))
            if wait_matches:
                last_m = wait_matches[-1]
                old_w = float(last_m.group(1))
                if delta > 0:
                    new_w = round(old_w + delta, 2)
                else:
                    new_w = max(0.5, round(old_w, 2))
                span_s, span_e = last_m.span()
                new_block_text = block_text[:span_s] + f"self.wait({new_w})" + block_text[span_e:]
                new_lines[start_idx:end_idx] = new_block_text.split("\n")
            else:
                wait_val = max(0.5, round(delta, 2)) if delta > 0 else 0.5
                new_lines.insert(end_idx, f"{indent}self.wait({wait_val})")

        return "\n".join(new_lines)

