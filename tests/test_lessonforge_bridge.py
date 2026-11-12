"""
Tests for Lessonforge <-> Code2Video Synchronization Bridge.
Validates SGA Scene Graph, MVQS calculations, Trusted TeachQuiz with Control Arms,
Learner-in-the-Loop beat localization, and Sync Manager.
"""

import pytest
from code2video.lessonforge_bridge import (
    SGASceneGraph,
    SGASceneObject,
    TrustedTeachQuizEvaluator,
    LearnerInTheLoopRepairOrchestrator,
    LessonforgeSyncManager,
)


def test_sync_manager_status():
    manager = LessonforgeSyncManager()
    status = manager.check_sync_status()
    assert status["code2video_available"] is True
    assert status["adapt_manim_available"] is True
    assert status["lessonforge_available"] is True
    assert status["lessonforge_dir_exists"] is True
    assert len(status["errors"]) == 0


def test_sga_scene_graph_mvqs_clean_layout():
    graph = SGASceneGraph()
    # Add non-overlapping objects
    graph.add_object(
        SGASceneObject(
            obj_id="title",
            class_name="Text",
            source_line=12,
            bounding_box=(-4.0, 2.5, 4.0, 3.5),
            center=(0.0, 3.0),
            text_content="Support Vector Machine",
        )
    )
    graph.add_object(
        SGASceneObject(
            obj_id="equation",
            class_name="MathTex",
            source_line=18,
            bounding_box=(-3.0, -1.0, 3.0, 0.5),
            center=(0.0, -0.25),
            text_content="w^T x + b = 0",
        )
    )

    mvqs = graph.compute_mvqs()
    assert mvqs["mvqs"] >= 85.0
    assert mvqs["overlap_count"] == 0
    assert mvqs["off_frame_count"] == 0


def test_sga_scene_graph_mvqs_overlap_detection():
    graph = SGASceneGraph()
    # Add overlapping objects
    graph.add_object(
        SGASceneObject(
            obj_id="obj_a",
            class_name="Text",
            source_line=25,
            bounding_box=(-1.0, -1.0, 1.0, 1.0),
            center=(0.0, 0.0),
            text_content="Margin A",
        )
    )
    graph.add_object(
        SGASceneObject(
            obj_id="obj_b",
            class_name="Text",
            source_line=27,
            bounding_box=(-0.5, -0.5, 1.5, 1.5),
            center=(0.5, 0.5),
            text_content="Margin B",
        )
    )

    mvqs = graph.compute_mvqs()
    assert mvqs["overlap_count"] == 1
    assert mvqs["spatial_score"] < 100.0


def test_trusted_teachquiz_with_controls():
    eval_result = TrustedTeachQuizEvaluator.evaluate_lesson_with_controls(
        topic="support vector machine", pedagogical_score=88.0, runs=3
    )

    assert eval_result["teach_quiz_gain"] > 0
    assert eval_result["passed_learner_gate"] is True

    conds = eval_result["conditions"]
    # Control arms must meet paper thresholds
    assert conds["no_video_forgetting"] <= 10.0
    assert conds["first_12s_only"] <= 15.0
    assert conds["another_lesson_video"] <= 10.0
    assert conds["no_forgetting_ceiling"] >= 80.0
    assert conds["full_video"] > conds["voice_only"]


def test_learner_in_the_loop_beat_localization():
    timeline = [
        {"id": "beat_01", "chapter_index": 0, "start_sec": 0.0, "end_sec": 15.0},
        {"id": "beat_02", "chapter_index": 0, "start_sec": 15.0, "end_sec": 35.0},
        {"id": "beat_03", "chapter_index": 1, "start_sec": 35.0, "end_sec": 60.0},
    ]

    quiz_errors = [
        {
            "concept": "margin maximization",
            "cited_second": 22.5,
            "fault_class": "taught_but_unclear",
        },
        {
            "concept": "dual formulation",
            "cited_second": 48.0,
            "fault_class": "picture_contradicts_words",
        },
    ]

    targets = LearnerInTheLoopRepairOrchestrator.locate_faulty_beats(
        quiz_errors, timeline
    )
    assert len(targets) == 2
    assert targets[0]["matched_beat_id"] == "beat_02"
    assert targets[0]["chapter_index"] == 0
    assert targets[1]["matched_beat_id"] == "beat_03"
    assert targets[1]["chapter_index"] == 1

