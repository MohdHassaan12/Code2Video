"""
Configuration module for AdaptManim pipeline.
Defines parameters for planning, anchor grids, verification cascade,
adaptive repair budgets, and evaluation metrics.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
import os


@dataclass
class GridConfig:
    """Configuration for the discrete visual anchor system (6x6 grid on right half)."""
    rows: List[str] = field(default_factory=lambda: ["A", "B", "C", "D", "E", "F"])
    cols: List[str] = field(default_factory=lambda: ["1", "2", "3", "4", "5", "6"])
    x_start: float = 0.5
    x_step: float = 1.0
    y_start: float = 2.2
    y_step: float = 1.0
    lecture_sidebar_width: float = 3.5
    canvas_width: float = 14.2
    canvas_height: float = 8.0


@dataclass
class PedagogyConfig:
    """Mayer's Cognitive Theory of Multimedia Learning constraints."""
    target_scene_duration_sec: int = 90  # 60-120 seconds per scene
    max_lecture_lines_per_scene: int = 5
    min_lecture_lines_per_scene: int = 2
    enforce_symbol_ledger: bool = True
    enforce_signaling: bool = True  # Highlight current lecture line synchronously
    enforce_dual_coding: bool = True  # Every lecture concept must have visual counterpart


@dataclass
class RepairConfig:
    """Adaptive Test-Time Compute & Repair Budget settings."""
    max_line_scope_attempts: int = 3   # K1
    max_block_scope_attempts: int = 2  # K2
    max_section_scope_attempts: int = 1 # K3
    enable_deterministic_autogrid: bool = True  # 0-token collision fixer
    enable_ast_auto_migration: bool = True     # 0-token deprecated API auto-fixer
    max_token_budget_per_section: int = 15000
    timeout_execution_seconds: int = 25


@dataclass
class AdaptManimConfig:
    """Top-level pipeline configuration."""
    model_name: str = "gemini-2.5-pro"
    fallback_model: str = "gemini-2.5-flash"
    api_key: Optional[str] = field(
        default_factory=lambda: os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    )
    grid: GridConfig = field(default_factory=GridConfig)
    pedagogy: PedagogyConfig = field(default_factory=PedagogyConfig)
    repair: RepairConfig = field(default_factory=RepairConfig)
    output_dir: str = "demo_outputs"
    enable_sandbox_rendering: bool = True
    manim_quality: str = "ql"  # ql: low quality (480p 15fps), qm: medium, qh: high
    use_mock_llm_if_no_key: bool = True
