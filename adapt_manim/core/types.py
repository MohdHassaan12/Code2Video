"""
Pydantic data models and type definitions for AdaptManim.
Defines schemas for outlines, storyboards, symbol ledgers, occupancy tables,
multi-tier verification reports, adaptive repair traces, and evaluation metrics.
"""

from enum import Enum
from typing import Dict, List, Optional, Any, Union
from pydantic import BaseModel, Field


class AudienceLevel(str, Enum):
    MIDDLE_SCHOOL = "middle_school"
    HIGH_SCHOOL = "high_school"
    UNDERGRADUATE = "undergraduate"
    RESEARCHER = "researcher"


class OutlineSection(BaseModel):
    """A high-level pedagogical section in the video outline."""
    id: str
    title: str
    content: str
    example: Optional[str] = None
    prerequisites: List[str] = Field(default_factory=list)
    estimated_duration_sec: int = 90


class Outline(BaseModel):
    """Complete decomposed outline for a topic."""
    topic: str
    audience: AudienceLevel = AudienceLevel.UNDERGRADUATE
    target_duration_minutes: float = 3.0
    key_takeaway: str = ""
    sections: List[OutlineSection] = Field(default_factory=list)


class LectureCue(BaseModel):
    """Speech/narration cue aligned with visual events (Mayer's contiguity principle)."""
    cue_id: str
    text: str
    target_event_id: Optional[str] = None
    color_hex: str = "#58C4DD"  # Highlight color when spoken


class AnimationStep(BaseModel):
    """A concrete visual animation instruction paired with a lecture cue."""
    step_id: str
    paired_cue_id: str
    description: str
    anchor_target: str = "C3"  # Point e.g. "B2" or area e.g. "A1-D4"
    scale_factor: float = 1.0
    action_type: str = "FadeIn"  # FadeIn, Create, Transform, Indicate, etc.
    assets_required: List[str] = Field(default_factory=list)


class StoryboardSection(BaseModel):
    """Detailed storyboard for one video section."""
    id: str
    title: str
    lecture_lines: List[str] = Field(default_factory=list)
    animations: List[str] = Field(default_factory=list)
    cues: List[LectureCue] = Field(default_factory=list)
    animation_steps: List[AnimationStep] = Field(default_factory=list)


class Storyboard(BaseModel):
    """Complete storyboard mapping lecture lines to visual steps."""
    topic: str
    sections: List[StoryboardSection] = Field(default_factory=list)


class SymbolEntry(BaseModel):
    """A tracked mathematical symbol or constant across scenes."""
    symbol_latex: str
    name: str
    domain: str
    units: Optional[str] = None
    color_hex: str = "#FFFF00"
    description: str = ""
    first_section_id: str = "section_1"


class SymbolLedger(BaseModel):
    """
    Cross-scene symbol memory ledger to prevent notation and unit drift
    (addressing LLM2Manim & Mayer's signaling/dual coding principles).
    """
    topic: str
    symbols: Dict[str, SymbolEntry] = Field(default_factory=dict)
    active_coordinate_system: str = "2d_cartesian"
    theme_colors: Dict[str, str] = Field(default_factory=lambda: {
        "primary": "#58C4DD",     # Manim Blue
        "secondary": "#83C167",   # Manim Green
        "accent": "#FC6255",      # Manim Red
        "highlight": "#FFFF00",   # Yellow
        "text": "#FFFFFF",
        "background": "#000000"
    })

    def register(self, symbol: SymbolEntry):
        self.symbols[symbol.symbol_latex] = symbol

    def lookup(self, latex: str) -> Optional[SymbolEntry]:
        return self.symbols.get(latex)


class AnchorPosition(BaseModel):
    """Specification of 6x6 anchor placement."""
    mode: str = "point"  # "point" or "area"
    point: Optional[str] = "C3"  # e.g. "B2"
    top_left: Optional[str] = None  # e.g. "A1"
    bottom_right: Optional[str] = None  # e.g. "D4"
    scale_factor: float = 1.0


class OccupancyRecord(BaseModel):
    """Record of an object occupying cells on the 6x6 canvas."""
    object_name: str
    anchor: str  # e.g. "B2" or "A1:D4"
    points_covered: List[str] = Field(default_factory=list)
    scale_factor: float = 1.0
    code_line: int = -1
    color: Optional[str] = None


class OccupancyTable(BaseModel):
    """Discrete 6x6 occupancy tracker for deterministic collision prevention."""
    records: List[OccupancyRecord] = Field(default_factory=list)
    collisions: List[Dict[str, Any]] = Field(default_factory=list)
    vacant_points: List[str] = Field(default_factory=list)


class VerificationTier(str, Enum):
    TIER1_AST = "Tier 1: AST & Syntax Check"
    TIER2_SYMBOLIC = "Tier 2: Symbol & Pedagogical Consistency"
    TIER3_EXECUTION = "Tier 3: Sandboxed Execution & Traceback"
    TIER4_SPATIAL = "Tier 4: Discrete Spatial Layout & Occupancy"
    TIER5_SEMANTIC = "Tier 5: Pedagogical Soundness & VLM-as-Judge"


class IssueSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class VerificationIssue(BaseModel):
    """An issue identified by one of the verification tiers."""
    tier: VerificationTier
    severity: IssueSeverity
    message: str
    line_number: Optional[int] = None
    offending_code: Optional[str] = None
    suggested_scope: str = "line"  # "autogrid", "line", "block", "ledger", "section"
    suggested_fix: Optional[str] = None


class VerificationReport(BaseModel):
    """Comprehensive multi-tier verification diagnostic output."""
    section_id: str
    passed: bool = True
    highest_failing_tier: Optional[VerificationTier] = None
    issues: List[VerificationIssue] = Field(default_factory=list)
    execution_time_sec: float = 0.0
    traceback_str: Optional[str] = None
    occupancy_table: Optional[OccupancyTable] = None


class RepairScope(str, Enum):
    ZERO_TOKEN_AUTOGRID = "zero_token_autogrid"
    LINE_SCOPE = "line_scope"
    BLOCK_SCOPE = "block_scope"
    LEDGER_PATCH = "ledger_patch"
    SECTION_SCOPE = "section_scope"


class RepairAttempt(BaseModel):
    """Record of a single repair step in ScopeRefine++."""
    attempt_id: int
    scope: RepairScope
    tier_trigger: VerificationTier
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_sec: float = 0.0
    resolved: bool = False
    patch_summary: str = ""


class RepairHistory(BaseModel):
    """Complete repair trajectory for a section."""
    section_id: str
    total_attempts: int = 0
    total_tokens: int = 0
    total_latency_sec: float = 0.0
    final_success: bool = False
    attempts: List[RepairAttempt] = Field(default_factory=list)


class QualityMetrics(BaseModel):
    """Aesthetic (AES), TeachQuiz, and Pedagogy evaluation metrics."""
    element_layout: float = 0.0     # EL (0-20)
    attractiveness: float = 0.0     # AT (0-20)
    logic_flow: float = 0.0         # LF (0-20)
    visual_consistency: float = 0.0 # VC (0-20)
    accuracy_depth: float = 0.0     # AD (0-20)
    overall_aes: float = 0.0        # (0-100 sum)
    teach_quiz_relative: float = 0.0 # eS = S(V) - S(V|unlearn) (0-100)
    pedagogical_alignment: float = 0.0 # Mayer's principles compliance (0-100)
    verdict: str = "PENDING"


class ComputeMetrics(BaseModel):
    """Resource consumption and efficiency metrics."""
    planning_tokens: int = 0
    coding_tokens: int = 0
    verification_tokens: int = 0
    repair_tokens: int = 0
    total_tokens: int = 0
    wall_clock_time_sec: float = 0.0
    repair_iterations: int = 0
    pass_at_1: bool = False
    pass_at_repair: bool = False
    estimated_cost_usd: float = 0.0


class SectionResult(BaseModel):
    """Result of processing a single section through the pipeline."""
    section_id: str
    title: str
    code: str
    verification_report: VerificationReport
    repair_history: RepairHistory
    is_executable: bool = False
    rendered_video_path: Optional[str] = None
    rendered_preview_frame: Optional[str] = None


class PipelineResult(BaseModel):
    """Final aggregated result of the AdaptManim pipeline."""
    topic: str
    outline: Outline
    storyboard: Storyboard
    symbol_ledger: SymbolLedger
    section_results: List[SectionResult] = Field(default_factory=list)
    combined_code: str = ""
    final_video_path: Optional[str] = None
    quality_metrics: QualityMetrics = Field(default_factory=QualityMetrics)
    compute_metrics: ComputeMetrics = Field(default_factory=ComputeMetrics)
    success: bool = False
