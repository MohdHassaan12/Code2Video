"""
Adaptive Repair Router Module.
Routes verification failures through the optimal cost-effective repair scope
(Zero-token AutoGrid -> Line Scope -> Block Scope -> Section Scope),
dynamically optimizing the Quality-Compute Pareto frontier.
"""

import time
from typing import Optional, Any, Tuple
from adapt_manim.core.types import (
    VerificationReport, VerificationTier, RepairScope,
    RepairAttempt, RepairHistory, StoryboardSection
)
from adapt_manim.core.ledger import SymbolLedgerManager
from adapt_manim.repair.scope_refine import ScopeRefineRepairer
from adapt_manim.coding.coder import ManimCoder


class AdaptiveRepairRouter:
    """Manages hierarchical test-time repair loops and compute tracking."""

    @classmethod
    def execute_adaptive_repair(
        cls,
        code: str,
        initial_report: VerificationReport,
        section: StoryboardSection,
        ledger_manager: SymbolLedgerManager,
        verifier_func: Any,
        llm_client: Optional[Any] = None,
        max_k1: int = 3,
        max_k2: int = 2
    ) -> Tuple[str, VerificationReport, RepairHistory]:
        """
        Executes progressive ScopeRefine++ repair loop.
        Returns: (final_code, final_report, repair_history)
        """
        current_code = code
        current_report = initial_report
        history = RepairHistory(section_id=section.id)

        attempt_counter = 0

        # Loop until verified or budget exhausted
        while not current_report.passed and attempt_counter < 6:
            attempt_counter += 1
            primary_issue = current_report.issues[0] if current_report.issues else None
            if not primary_issue:
                break

            scope = primary_issue.suggested_scope
            start_t = time.time()
            repaired_code = current_code
            p_tokens = 0
            c_tokens = 0
            repair_scope_enum = RepairScope.LINE_SCOPE

            # Step 1: Zero-Token Auto-Grid / Auto-AST
            if scope == "autogrid" or primary_issue.tier == VerificationTier.TIER4_SPATIAL:
                repair_scope_enum = RepairScope.ZERO_TOKEN_AUTOGRID
                repaired_code, success = ScopeRefineRepairer.repair_zero_token_autogrid(current_code, primary_issue)
                p_tokens, c_tokens = 0, 0

            # Step 2: Line Scope
            elif scope == "line" or attempt_counter <= max_k1:
                repair_scope_enum = RepairScope.LINE_SCOPE
                repaired_code, p_tokens, c_tokens = ScopeRefineRepairer.repair_line_scope(
                    current_code, primary_issue, llm_client
                )

            # Step 3: Block Scope
            elif scope == "block" or attempt_counter <= (max_k1 + max_k2):
                repair_scope_enum = RepairScope.BLOCK_SCOPE
                repaired_code, p_tokens, c_tokens = ScopeRefineRepairer.repair_block_scope(
                    current_code, primary_issue, section, llm_client
                )

            # Step 4: Section Scope (Regeneration)
            else:
                repair_scope_enum = RepairScope.SECTION_SCOPE
                repaired_code = ManimCoder.generate_section_code(section, ledger_manager, llm_client)
                p_tokens, c_tokens = 1200, 450

            elapsed = time.time() - start_t

            # Re-verify candidate code with verification cascade
            new_report = verifier_func(repaired_code)
            resolved = new_report.passed or len(new_report.issues) < len(current_report.issues)

            attempt = RepairAttempt(
                attempt_id=attempt_counter,
                scope=repair_scope_enum,
                tier_trigger=primary_issue.tier,
                prompt_tokens=p_tokens,
                completion_tokens=c_tokens,
                latency_sec=round(elapsed, 3),
                resolved=resolved,
                patch_summary=f"Repaired via {repair_scope_enum.value} for issue: {primary_issue.message[:50]}"
            )
            history.attempts.append(attempt)
            history.total_tokens += (p_tokens + c_tokens)
            history.total_latency_sec += elapsed

            current_code = repaired_code
            current_report = new_report

            if current_report.passed:
                history.final_success = True
                break

        history.total_attempts = len(history.attempts)
        history.final_success = current_report.passed

        return (current_code, current_report, history)

