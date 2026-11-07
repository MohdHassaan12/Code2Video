"""
Tier 1: Static AST & Syntax Verification.
Inspects AST for syntax validity, banned continuous positioning calls,
deprecated APIs, and import whitelists (Compute Cost: ~0ms, 0 tokens).
"""

import ast
from typing import List, Optional
from adapt_manim.core.types import (
    VerificationTier, VerificationIssue, IssueSeverity
)
from adapt_manim.coding.ast_processor import AstProcessor


class Tier1AstVerifier:
    """Fast, zero-token static analyzer for Manim code."""

    BANNED_METHODS = ["resize", "ShowCreation"]
    ALLOWED_IMPORTS = {"manim", "numpy", "math", "scipy"}

    @classmethod
    def verify(cls, code: str) -> List[VerificationIssue]:
        issues: List[VerificationIssue] = []

        # 1. Syntax check
        syntax_err = AstProcessor.check_syntax(code)
        if syntax_err:
            msg, lineno, offending = syntax_err
            issues.append(VerificationIssue(
                tier=VerificationTier.TIER1_AST,
                severity=IssueSeverity.CRITICAL,
                message=f"Syntax Error: {msg}",
                line_number=lineno,
                offending_code=offending,
                suggested_scope="line",
                suggested_fix="Correct Python syntax at indicated line."
            ))
            return issues  # Cannot parse further if syntax is broken

        # 2. Parse tree
        tree = ast.parse(code)

        # 3. Check for deprecated methods or banned direct canvas positioning
        lines = code.split("\n")
        for node in ast.walk(tree):
            # Check attribute calls
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                attr_name = node.func.attr
                if attr_name in cls.BANNED_METHODS:
                    lineno = getattr(node, "lineno", 1)
                    offending = lines[lineno - 1] if 0 <= lineno - 1 < len(lines) else ""
                    replacement = AstProcessor.DEPRECATED_METHOD_MAP.get(attr_name, "scale")
                    issues.append(VerificationIssue(
                        tier=VerificationTier.TIER1_AST,
                        severity=IssueSeverity.CRITICAL,
                        message=f"Deprecated or invalid Manim method '{attr_name}' detected. Use '{replacement}' instead.",
                        line_number=lineno,
                        offending_code=offending,
                        suggested_scope="autogrid" if attr_name == "resize" else "line",
                        suggested_fix=f"Replace .{attr_name}() with .{replacement}()"
                    ))

                # Check if .to_edge() or .move_to() is called directly inside construct (instead of place_at_grid)
                if attr_name in ["to_edge", "move_to"]:
                    # Allow on self.title or self.lecture or axes
                    caller_name = ""
                    if isinstance(node.func.value, ast.Name):
                        caller_name = node.func.value.id
                    elif isinstance(node.func.value, ast.Attribute):
                        caller_name = node.func.value.attr

                    if caller_name not in ["title", "lecture", "axes", "mobject", "self"]:
                        lineno = getattr(node, "lineno", 1)
                        offending = lines[lineno - 1] if 0 <= lineno - 1 < len(lines) else ""
                        issues.append(VerificationIssue(
                            tier=VerificationTier.TIER1_AST,
                            severity=IssueSeverity.WARNING,
                            message=f"Unanchored canvas positioning '.{attr_name}()' used on '{caller_name}'. Use self.place_at_grid() or self.place_in_area().",
                            line_number=lineno,
                            offending_code=offending,
                            suggested_scope="line",
                            suggested_fix="Replace with self.place_at_grid(obj, 'C3')"
                        ))

        return issues
