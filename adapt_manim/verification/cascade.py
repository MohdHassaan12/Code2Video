"""
Verification Cascade Controller.
Implements the multi-tier early-exit verification pipeline to minimize compute
while guaranteeing syntax, symbolic consistency, executability, and visual layout.
"""

from typing import Optional, Any
from adapt_manim.core.types import (
    VerificationReport, VerificationTier, IssueSeverity,
    StoryboardSection, QualityMetrics
)
from adapt_manim.core.ledger import SymbolLedgerManager
from adapt_manim.verification.tier1_ast import Tier1AstVerifier
from adapt_manim.verification.tier2_symbolic import Tier2SymbolicVerifier
from adapt_manim.verification.tier3_execution import Tier3ExecutionVerifier
from adapt_manim.verification.tier4_spatial import Tier4SpatialVerifier
from adapt_manim.verification.tier5_semantic import Tier5SemanticVerifier


class VerificationCascade:
    """Orchestrates tiered verification with early-exit budget optimization."""

    @classmethod
    def verify_section(
        cls,
        code: str,
        section: StoryboardSection,
        ledger_manager: SymbolLedgerManager,
        output_dir: str = "demo_outputs",
        llm_client: Optional[Any] = None,
        skip_execution: bool = False
    ) -> VerificationReport:
        """
        Executes cascade from Tier 1 to Tier 5.
        Early exits upon encountering critical failures to conserve compute.
        """
        report = VerificationReport(section_id=section.id)

        # ---------------- Tier 1: AST & Syntax ----------------
        t1_issues = Tier1AstVerifier.verify(code)
        report.issues.extend(t1_issues)
        has_critical = any(i.severity == IssueSeverity.CRITICAL for i in t1_issues)
        if has_critical:
            report.passed = False
            report.highest_failing_tier = VerificationTier.TIER1_AST
            return report  # Early exit

        # ---------------- Tier 2: Symbolic & Invariants ----------------
        t2_issues = Tier2SymbolicVerifier.verify(code, section, ledger_manager)
        report.issues.extend(t2_issues)
        has_critical = any(i.severity == IssueSeverity.CRITICAL for i in t2_issues)
        if has_critical:
            report.passed = False
            report.highest_failing_tier = VerificationTier.TIER2_SYMBOLIC
            return report  # Early exit

        # ---------------- Tier 3: Execution Sandbox ----------------
        rendered_frame_path = None
        if not skip_execution:
            t3_issues, exec_time, tb_str, frame_path = Tier3ExecutionVerifier.verify(
                code=code,
                section=section,
                output_dir=output_dir
            )
            report.issues.extend(t3_issues)
            report.execution_time_sec = exec_time
            report.traceback_str = tb_str
            rendered_frame_path = frame_path

            has_critical = any(i.severity == IssueSeverity.CRITICAL for i in t3_issues)
            if has_critical:
                report.passed = False
                report.highest_failing_tier = VerificationTier.TIER3_EXECUTION
                return report  # Early exit

        # ---------------- Tier 4: Spatial & Occupancy ----------------
        t4_issues, occ_table = Tier4SpatialVerifier.verify(code)
        report.issues.extend(t4_issues)
        report.occupancy_table = occ_table

        # ---------------- Tier 5: Semantic & VLM Critic ----------------
        t5_issues, _ = Tier5SemanticVerifier.verify(
            code=code,
            section=section,
            llm_client=llm_client,
            rendered_frame_path=rendered_frame_path
        )
        report.issues.extend(t5_issues)

        # Final pass determination
        critical_remaining = any(i.severity == IssueSeverity.CRITICAL for i in report.issues)
        report.passed = not critical_remaining
        if not report.passed:
            for issue in report.issues:
                if issue.severity == IssueSeverity.CRITICAL:
                    report.highest_failing_tier = issue.tier
                    break

        return report
