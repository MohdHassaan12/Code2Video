"""
Tier 3: Sandboxed Execution & Traceback Extraction.
Executes Manim in a sandboxed headless subprocess to verify executability,
capturing exact exception tracebacks, line numbers, and failure blocks (Code2Video Section 4.2).
Compute Cost: ~0.5s CPU, 0 tokens.
"""

import os
import re
import subprocess
import time
from typing import List, Tuple, Optional
from adapt_manim.core.types import (
    VerificationTier, VerificationIssue, IssueSeverity, StoryboardSection
)
from adapt_manim.coding.ast_processor import AstProcessor


class Tier3ExecutionVerifier:
    """Headless compilation and runtime error localization."""

    @classmethod
    def verify(
        cls,
        code: str,
        section: StoryboardSection,
        output_dir: str = "demo_outputs",
        python_bin: str = ".venv/bin/python",
        manim_bin: str = ".venv/bin/manim"
    ) -> Tuple[List[VerificationIssue], float, Optional[str], Optional[str]]:
        """
        Executes Manim dry-run render.
        Returns: (issues, execution_time_sec, traceback_str, rendered_frame_path)
        """
        os.makedirs(output_dir, exist_ok=True)
        sec_id = section.id
        script_path = os.path.join(output_dir, f"{sec_id}_sandbox.py")
        media_dir = os.path.join(output_dir, "media")

        with open(script_path, "w") as f:
            f.write(code)

        class_name = f"{sec_id.title().replace('_', '')}Scene"
        frame_name = f"{sec_id}_preview.png"

        cmd = [
            manim_bin,
            "-ql",            # 480p low quality for fast test verification
            "-s",             # Save only the last frame for rapid inspection
            script_path,
            class_name,
            "-o", frame_name,
            "--media_dir", media_dir
        ]

        start_t = time.time()
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            elapsed = time.time() - start_t
        except subprocess.TimeoutExpired:
            return (
                [VerificationIssue(
                    tier=VerificationTier.TIER3_EXECUTION,
                    severity=IssueSeverity.CRITICAL,
                    message="Execution timed out after 30 seconds (infinite loop or complex geometry).",
                    suggested_scope="section",
                    suggested_fix="Simplify animation geometry and remove blocking loops."
                )],
                30.0,
                "TimeoutExpired",
                None
            )

        if res.returncode == 0:
            # Successfully rendered
            # Find rendered frame path
            expected_frame = os.path.join(media_dir, "images", f"{sec_id}_sandbox", frame_name)
            frame_path = expected_frame if os.path.exists(expected_frame) else None
            return ([], elapsed, None, frame_path)

        # Execution Failed - Parse Traceback
        error_output = res.stderr or res.stdout
        issues = cls._parse_traceback(error_output, code, script_path)
        return (issues, elapsed, error_output, None)

    @classmethod
    def _parse_traceback(cls, tb_str: str, code: str, script_path: str) -> List[VerificationIssue]:
        issues = []
        code_lines = code.split("\n")

        # Extract file line numbers from traceback
        matches = re.findall(rf'File "{re.escape(script_path)}", line (\d+)', tb_str)
        failing_line = int(matches[-1]) if matches else None

        # Extract Exception Type and Message
        exc_match = re.search(r"([A-Za-z]+Error:[^\n]+)", tb_str)
        exc_msg = exc_match.group(1) if exc_match else "Runtime Execution Error"

        offending_code = None
        if failing_line and 0 <= failing_line - 1 < len(code_lines):
            offending_code = code_lines[failing_line - 1].strip()

        # Determine Scope based on error location
        scope = "line"
        if failing_line:
            # Check if line falls within a lecture animation block
            blocks = AstProcessor.extract_lecture_blocks(code)
            for block_num, (s_l, e_l, _) in blocks.items():
                if s_l <= failing_line <= e_l:
                    scope = "line"  # Start with line scope, expand to block scope if unresolved
                    break

        issues.append(VerificationIssue(
            tier=VerificationTier.TIER3_EXECUTION,
            severity=IssueSeverity.CRITICAL,
            message=exc_msg,
            line_number=failing_line,
            offending_code=offending_code,
            suggested_scope=scope,
            suggested_fix=f"Fix runtime crash '{exc_msg}' at line {failing_line}."
        ))

        return issues
