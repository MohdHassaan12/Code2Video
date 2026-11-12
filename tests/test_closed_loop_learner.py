"""
Tests for Closed-Loop Learner-in-the-Loop Diagnostic Repair (Direction D2).
Verifies:
1. DiagnosticProbeGenerator extracts misconception questions matching topic taxonomy.
2. ClosedLoopLearnerRepair diagnoses ungrounded or stalled instructional concepts.
3. Surgical remediation applies block-level patches to failing sections without whole-script rewrite.
4. Non-regression invariant: post-repair score exceeds initial baseline.
5. End-to-end integration into Code2VideoPipeline with learner_in_the_loop=True.
"""

import pytest
from adapt_manim.core.types import Storyboard, StoryboardSection
from code2video.learner_loop import (
    DiagnosticProbe, DiagnosticProbeGenerator, LearnerFaultDiagnosis,
    LearnerLoopReport, ClosedLoopLearnerRepair
)
from code2video.grounding_matrix import GroundingMatrixReport
from code2video.motion_budget import MotionBudgetReport, DeadHoldSpan
from code2video.pipeline import Code2VideoPipeline


@pytest.fixture
def sample_storyboard():
    return Storyboard(
        topic="Calculus: The Derivative",
        sections=[
            StoryboardSection(
                id="sec_1",
                title="Introduction to Slopes",
                lecture_lines=["We observe the curve and consider secant lines.", "As the interval shrinks, slope changes."],
                animations=["Show curve", "Draw secant line"]
            ),
            StoryboardSection(
                id="sec_2",
                title="The Instantaneous Limit",
                lecture_lines=["Taking limit of df over dx as h approaches zero.", "This gives instantaneous derivative."],
                animations=["Shrink h towards zero", "Transform secant to tangent"]
            ),
            StoryboardSection(
                id="sec_3",
                title="Summary & Power Rule",
                lecture_lines=["The slope function is continuous.", "For x squared the derivative is 2x."],
                animations=["Plot derivative function"]
            )
        ]
    )


def test_probe_generator_extracts_canonical_misconceptions(sample_storyboard):
    probes = DiagnosticProbeGenerator.generate_probes("Calculus: The Derivative", sample_storyboard)
    assert len(probes) >= 3

    concepts = [p.concept.lower() for p in probes]
    assert any("derivative" in c or "limit" in c for c in concepts)

    # Check structure of probe
    first_probe = probes[0]
    assert len(first_probe.options) == 4
    assert 0 <= first_probe.correct_index < 4
    assert first_probe.misconception_distractor != ""
    assert isinstance(first_probe.to_dict(), dict)


def test_diagnose_draft_detects_grounding_defects(sample_storyboard):
    probes = [
        DiagnosticProbe(
            probe_id="p1",
            concept="derivative",
            question="What happens to df/dx?",
            options=["Undefined", "Finite limit", "Infinity", "Zero"],
            correct_index=1,
            misconception_distractor="Undefined 0/0",
            target_second=15.0,
            target_section_id="sec_2"
        )
    ]

    # Grounding report where 'derivative' was ungrounded
    mock_grounding = GroundingMatrixReport(
        topic="Calculus: The Derivative",
        total_spoken_entities=2,
        grounded_count=0,
        ungrounded_count=2,
        grounding_ratio=0.0,
        grounding_score=0.0,
        mayer_contiguity_score=50.0,
        passed=False,
        ungrounded_entities=[{"term": "derivative", "category": "concept"}]
    )

    score, faults = ClosedLoopLearnerRepair.diagnose_draft(
        topic="Calculus: The Derivative",
        storyboard=sample_storyboard,
        code="class Demo(Scene): pass",
        grounding_report=mock_grounding,
        probes=probes
    )

    assert score == 0.0
    assert len(faults) == 1
    assert faults[0].concept == "derivative"
    assert faults[0].matched_section_id == "sec_2"
    assert faults[0].fault_class in ("never_taught", "taught_but_unclear")


def test_surgical_remediation_on_section_code():
    orig_code = """class SectionScene(Scene):
    def construct(self):
        title = Title("Section 2")
        self.play(Write(title))
        self.wait(2.0)
"""
    sec = StoryboardSection(id="sec_2", title="The Instantaneous Limit")
    diag = LearnerFaultDiagnosis(
        probe_id="p1",
        concept="derivative",
        cited_second=15.0,
        fault_class="never_taught",
        matched_section_id="sec_2",
        matched_beat_id="beat_sec_2",
        learner_answer="0/0",
        expected_answer="Finite limit",
        diagnostic_rationale="Not grounded",
        recommended_action="Inject MathTex"
    )

    remed_code, mods = ClosedLoopLearnerRepair.remediate_section_code(orig_code, sec, diag)
    assert len(mods) >= 1
    assert "MathTex" in remed_code
    assert "derivative" in remed_code or "remed_" in remed_code


def test_execute_closed_loop_repair_cycle(sample_storyboard):
    section_codes = {
        "sec_1": "class Sec1(Scene):\n    def construct(self):\n        self.wait(1.0)",
        "sec_2": "class Sec2(Scene):\n    def construct(self):\n        self.wait(2.0)",
        "sec_3": "class Sec3(Scene):\n    def construct(self):\n        self.wait(1.0)",
    }

    # Simulate fault on sec_2
    mock_grounding = GroundingMatrixReport(
        topic="Calculus: The Derivative",
        total_spoken_entities=3,
        grounded_count=1,
        ungrounded_count=2,
        grounding_ratio=0.33,
        grounding_score=33.3,
        mayer_contiguity_score=50.0,
        passed=False,
        ungrounded_entities=[{"term": "derivative", "category": "concept"}]
    )

    repaired_codes, report = ClosedLoopLearnerRepair.execute_closed_loop_repair(
        topic="Calculus: The Derivative",
        storyboard=sample_storyboard,
        section_codes=section_codes,
        grounding_report=mock_grounding
    )

    assert report.post_repair_score > report.initial_score
    assert report.status == "improved"
    # Preserved sections should include sec_1 or sec_3 (compute saved > 0)
    assert len(report.preserved_sections) >= 1
    assert report.compute_saved_percent > 0.0
    assert "sec_2" in report.repaired_sections or len(report.repaired_sections) >= 1


def test_pipeline_integration_with_learner_loop(tmp_path):
    out_dir = str(tmp_path / "test_pipeline_learner")
    pipeline = Code2VideoPipeline(output_dir=out_dir)

    res = pipeline.run(
        topic="Calculus: The Derivative",
        render=False,
        learner_in_the_loop=True
    )

    assert "learner_loop" in res
    assert res["learner_loop"] is not None
    lr = res["learner_loop"]
    assert "initial_score" in lr
    assert "post_repair_score" in lr
    assert lr["post_repair_score"] >= lr["initial_score"]
    assert "compute_saved_percent" in lr
