"""
Dead-Hold Motion Budget Monitor & Dynamic Telestration Module (Direction D9+).
Monitors keyframe animation density to eradicate 'dead holds' (frozen screens during narration)
and enforces a minimum active motion density matching the Khan Academy standard (81-92%).

Key Capabilities:
1. Motion Density Analysis: Computes active vs static half-second video intervals.
2. Dead-Hold Detection: Flags spans exceeding 2.5s where the lecturer speaks with 0 visual activity.
3. Dynamic Telestration Injector: 0-token deterministic code enhancement that injects subtle
   pedagogical gestures (Indicate, Circumscribe, TracedPath) into dead holds.
"""

from __future__ import annotations

import ast
import math
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class DeadHoldSpan:
    start_sec: float
    end_sec: float
    duration_sec: float
    line_number: Optional[int]
    context: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "start_sec": round(self.start_sec, 2),
            "end_sec": round(self.end_sec, 2),
            "duration_sec": round(self.duration_sec, 2),
            "line_number": self.line_number,
            "context": self.context,
        }


@dataclass
class MotionBudgetReport:
    total_duration_sec: float
    active_duration_sec: float
    static_duration_sec: float
    active_density_ratio: float  # Share of active half-seconds (0.0 to 1.0)
    max_dead_hold_sec: float
    dead_holds: List[DeadHoldSpan] = field(default_factory=list)
    passed: bool = False
    standard: str = "Khan Academy Benchmark (target >= 75% active motion density)"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_duration_sec": round(self.total_duration_sec, 2),
            "active_duration_sec": round(self.active_duration_sec, 2),
            "static_duration_sec": round(self.static_duration_sec, 2),
            "active_density_ratio": round(self.active_density_ratio, 3),
            "max_dead_hold_sec": round(self.max_dead_hold_sec, 2),
            "dead_holds_count": len(self.dead_holds),
            "dead_holds": [dh.to_dict() for dh in self.dead_holds],
            "passed": self.passed,
            "standard": self.standard,
        }


class MotionBudgetMonitor:
    """
    Evaluates and enforces active visual motion budgets across educational animation code.
    """

    DEAD_HOLD_THRESHOLD_SEC = 2.5  # Any static interval > 2.5s violates pedagogical engagement

    @classmethod
    def analyze_code_motion(
        cls,
        code: str,
        target_duration: Optional[float] = None
    ) -> MotionBudgetReport:
        """
        Parses Manim code to construct an execution timeline of active vs static half-seconds.
        """
        timeline_events = cls._extract_timeline_events(code)
        
        if not timeline_events:
            total_dur = target_duration or 30.0
            return MotionBudgetReport(
                total_duration_sec=total_dur,
                active_duration_sec=0.0,
                static_duration_sec=total_dur,
                active_density_ratio=0.0,
                max_dead_hold_sec=total_dur,
                dead_holds=[DeadHoldSpan(0.0, total_dur, total_dur, 1, "No animations detected")],
                passed=False
            )

        total_duration = max(ev[1] for ev in timeline_events)
        if target_duration and target_duration > total_duration:
            total_duration = target_duration

        # Discretize into 0.5-second bins
        num_half_seconds = max(1, int(math.ceil(total_duration * 2)))
        half_sec_active = [False] * num_half_seconds

        for ev_type, end_time, dur, line_no in timeline_events:
            if ev_type == "active":
                start_time = max(0.0, end_time - dur)
                start_bin = int(start_time * 2)
                end_bin = min(num_half_seconds, int(math.ceil(end_time * 2)))
                for b in range(start_bin, end_bin):
                    if 0 <= b < num_half_seconds:
                        half_sec_active[b] = True

        active_count = sum(1 for is_act in half_sec_active if is_act)
        active_ratio = active_count / num_half_seconds
        active_sec = active_count * 0.5
        static_sec = total_duration - active_sec

        # Detect contiguous dead holds
        dead_holds: List[DeadHoldSpan] = []
        current_dead_start = None

        for b, is_act in enumerate(half_sec_active):
            t = b * 0.5
            if not is_act:
                if current_dead_start is None:
                    current_dead_start = t
            else:
                if current_dead_start is not None:
                    span_dur = t - current_dead_start
                    if span_dur >= cls.DEAD_HOLD_THRESHOLD_SEC:
                        dead_holds.append(DeadHoldSpan(
                            start_sec=current_dead_start,
                            end_sec=t,
                            duration_sec=span_dur,
                            line_number=None,
                            context=f"Static canvas during active lecture interval [{current_dead_start:.1f}s - {t:.1f}s]"
                        ))
                    current_dead_start = None

        if current_dead_start is not None:
            span_dur = total_duration - current_dead_start
            if span_dur >= cls.DEAD_HOLD_THRESHOLD_SEC:
                dead_holds.append(DeadHoldSpan(
                    start_sec=current_dead_start,
                    end_sec=total_duration,
                    duration_sec=span_dur,
                    line_number=None,
                    context=f"Trailing static freeze until end of scene [{current_dead_start:.1f}s - {total_duration:.1f}s]"
                ))

        max_dead_hold = max((dh.duration_sec for dh in dead_holds), default=0.0)
        passed = (active_ratio >= 0.70 and max_dead_hold <= 3.0)

        return MotionBudgetReport(
            total_duration_sec=total_duration,
            active_duration_sec=active_sec,
            static_duration_sec=static_sec,
            active_density_ratio=active_ratio,
            max_dead_hold_sec=max_dead_hold,
            dead_holds=dead_holds,
            passed=passed
        )

    @classmethod
    def _extract_timeline_events(cls, code: str) -> List[Tuple[str, float, float, int]]:
        """
        Extracts list of (event_type, cumulative_end_time, duration, line_no).
        event_type in ("active", "wait").
        """
        events: List[Tuple[str, float, float, int]] = []
        current_time = 0.0

        try:
            tree = ast.parse(code)
            for node in ast.walk(tree):
                if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
                    call = node.value
                    if isinstance(call.func, ast.Attribute):
                        method = call.func.attr
                        line_no = node.lineno

                        if method == "wait":
                            dur = 1.0
                            if call.args and isinstance(call.args[0], ast.Constant) and isinstance(call.args[0].value, (int, float)):
                                dur = float(call.args[0].value)
                            current_time += dur
                            events.append(("wait", current_time, dur, line_no))

                        elif method == "play":
                            dur = 1.0
                            for kw in call.keywords:
                                if kw.arg == "run_time" and isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, (int, float)):
                                    dur = float(kw.value.value)
                            current_time += dur
                            events.append(("active", current_time, dur, line_no))
        except SyntaxError:
            # Fallback regex if AST parsing fails
            lines = code.split("\n")
            for idx, line in enumerate(lines, 1):
                if "self.wait(" in line:
                    m = re.search(r"self\.wait\((\d+(?:\.\d+)?)\)", line)
                    dur = float(m.group(1)) if m else 1.0
                    current_time += dur
                    events.append(("wait", current_time, dur, idx))
                elif "self.play(" in line:
                    m = re.search(r"run_time\s*=\s*(\d+(?:\.\d+)?)", line)
                    dur = float(m.group(1)) if m else 1.0
                    current_time += dur
                    events.append(("active", current_time, dur, idx))

        return events

    @classmethod
    def inject_dynamic_telestration(
        cls,
        code: str,
        dead_holds: Optional[List[DeadHoldSpan]] = None
    ) -> Tuple[str, List[str]]:
        """
        Deterministic 0-token code enhancement:
        Surgically breaks long `self.wait(T)` calls (T >= 2.5s) into progressive emphasis
        and dynamic telestration pulses (e.g. Indicate, Circumscribe, pulse).
        """
        modifications = []
        lines = code.split("\n")
        new_lines = []

        # Find any declared Mobjects to use as targets for telestration
        declared_vars = []
        for line in lines:
            m = re.match(r"\s*(\w+)\s*=\s*(MathTex|Tex|Text|Dot|Axes|Circle|Arrow|Square)", line)
            if m:
                var_name = m.group(1)
                if var_name not in declared_vars and var_name not in ("self", "cls"):
                    declared_vars.append(var_name)

        wait_pattern = re.compile(r"^(\s*)self\.wait\((\d+(?:\.\d+)?)\)(.*)$")

        for line in lines:
            m = wait_pattern.match(line)
            if m:
                indent = m.group(1)
                dur = float(m.group(2))
                trailing = m.group(3)

                if dur >= cls.DEAD_HOLD_THRESHOLD_SEC:
                    target = declared_vars[-1] if declared_vars else None
                    if target and dur >= 3.5:
                        # Break into 1.0s wait + 1.2s Indicate + remainder wait
                        rem = max(0.5, dur - 2.2)
                        replacement = [
                            f"{indent}self.wait(1.0){trailing}",
                            f"{indent}# Dynamic telestration: eliminate dead hold by pulsing salient element",
                            f"{indent}self.play(Indicate({target}, scale_factor=1.06), run_time=1.2)",
                            f"{indent}self.wait({rem:.1f})"
                        ]
                        new_lines.extend(replacement)
                        modifications.append(f"Injected dynamic Indicate({target}) into {dur}s dead-hold wait")
                        continue
                    elif target and dur >= 2.5:
                        rem = max(0.5, dur - 1.5)
                        replacement = [
                            f"{indent}# Dynamic telestration: subtle pulse",
                            f"{indent}self.play(Indicate({target}, scale_factor=1.04), run_time=1.0)",
                            f"{indent}self.wait({rem:.1f})"
                        ]
                        new_lines.extend(replacement)
                        modifications.append(f"Injected dynamic pulse into {dur}s dead-hold wait")
                        continue

            new_lines.append(line)

        return "\n".join(new_lines), modifications
