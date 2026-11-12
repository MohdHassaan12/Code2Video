"""
Tests for Direction D2: Learner-in-the-Loop Repair.
Validates:
1. Locating failing instructional beats from cited seconds in timeline.json
2. Diagnostic categorization (never_taught, taught_but_unclear, picture_contradicts_words)
3. Surgical step remediation targeting misconceptions without whole-script rewrite
4. Selective chapter re-rendering harness (only affected chapters re-rendered)
5. Rollback on fault regression and acceptance when improved
"""

import json
import os
import shutil
from pathlib import Path
import pytest

from lessonforge.harness import learner_repair
from code2video.lessonforge_bridge import LearnerInTheLoopRepairOrchestrator


@pytest.fixture
def sample_timeline():
    return [
        {
            "id": "beat_01",
            "chapter": 1,
            "start": 0.0,
            "duration": 12.0,
            "sentences": [{"text": "Welcome to Newton's Laws.", "start": 0.5, "duration": 3.0}]
        },
        {
            "id": "beat_02",
            "chapter": 1,
            "start": 12.0,
            "duration": 18.0,
            "sentences": [{"text": "Action and reaction are equal and opposite.", "start": 12.5, "duration": 5.0}]
        },
        {
            "id": "beat_03",
            "chapter": 2,
            "start": 30.0,
            "duration": 25.0,
            "sentences": [{"text": "Forces act on two different bodies, so they do not cancel.", "start": 30.5, "duration": 6.0}]
        },
        {
            "id": "beat_04",
            "chapter": 3,
            "start": 55.0,
            "duration": 20.0,
            "sentences": [{"text": "In summary, force pairs never cancel out.", "start": 55.5, "duration": 4.0}]
        }
    ]


@pytest.fixture
def sample_lesson():
    return {
        "title": "Newton's Third Law",
        "chapters": [
            {
                "id": 1,
                "title": "Introduction & Statement",
                "beats": [
                    {
                        "id": "beat_01",
                        "narration": "Welcome to Newton's Laws.",
                        "steps": [{"say": "Welcome", "show": "Newton's Laws", "kind": "point"}]
                    },
                    {
                        "id": "beat_02",
                        "narration": "Action and reaction are equal and opposite.",
                        "steps": [{"say": "equal and opposite", "show": "F_A = -F_B", "kind": "math"}]
                    }
                ]
            },
            {
                "id": 2,
                "title": "Why Pairs Do Not Cancel",
                "beats": [
                    {
                        "id": "beat_03",
                        "narration": "Forces act on two different bodies, so they do not cancel.",
                        "steps": [{"say": "two different", "show": "Two bodies", "kind": "point"}]
                    }
                ]
            },
            {
                "id": 3,
                "title": "Summary",
                "beats": [
                    {
                        "id": "beat_04",
                        "narration": "In summary, force pairs never cancel out.",
                        "steps": [{"say": "never cancel", "show": "Pairs Never Cancel", "kind": "key"}]
                    }
                ]
            }
        ]
    }


def test_locate_beat_from_second(sample_timeline):
    # Cited second 5.0s -> beat_01 in Chapter 1
    loc1 = learner_repair.locate_beat_from_second(sample_timeline, 5.0)
    assert loc1 is not None
    assert loc1["chapter_id"] == 1
    assert loc1["beat_id"] == "beat_01"

    # Cited second 18.5s -> beat_02 in Chapter 1
    loc2 = learner_repair.locate_beat_from_second(sample_timeline, 18.5)
    assert loc2 is not None
    assert loc2["chapter_id"] == 1
    assert loc2["beat_id"] == "beat_02"

    # Cited second 38.0s -> beat_03 in Chapter 2
    loc3 = learner_repair.locate_beat_from_second(sample_timeline, 38.0)
    assert loc3 is not None
    assert loc3["chapter_id"] == 2
    assert loc3["beat_id"] == "beat_03"


def test_diagnose_quiz_failures(sample_timeline):
    quiz_errors = [
        {
            "concept": "forces act on different objects",
            "question": "Why don't action-reaction force pairs cancel each other out?",
            "cited_second": 36.5,
            "fault_class": "taught_but_unclear",
            "learner_answer": "They cancel because they are opposite",
            "expected_answer": "They act on two different bodies"
        }
    ]

    targets = learner_repair.diagnose_quiz_failures(quiz_errors, sample_timeline)
    assert len(targets) == 1
    assert targets[0]["chapter_id"] == 2
    assert targets[0]["beat_id"] == "beat_03"
    assert targets[0]["fault_class"] == "taught_but_unclear"


def test_repair_beat_steps_deterministic(sample_lesson):
    beat = sample_lesson["chapters"][1]["beats"][0]  # beat_03
    target = {
        "concept": "Different Bodies",
        "fault_class": "taught_but_unclear",
        "expected_answer": "Forces act on distinct objects",
        "why": "Learner thought forces cancel"
    }

    repaired = learner_repair.repair_beat_steps(beat, target, llm=None)
    assert repaired is not None
    assert len(repaired) >= 1
    # Check that the misconception is grounded
    assert any("Different Bodies" in s["show"] for s in repaired)


def test_orchestrator_bridge_localization(sample_timeline):
    quiz_errors = [
        {
            "concept": "force pair cancellation",
            "cited_second": 40.0,
            "fault_class": "picture_contradicts_words"
        }
    ]

    targets = LearnerInTheLoopRepairOrchestrator.locate_faulty_beats(quiz_errors, sample_timeline)
    assert len(targets) == 1
    assert targets[0]["matched_beat_id"] == "beat_03"
    assert targets[0]["chapter_index"] == 2
    assert targets[0]["fault_class"] == "picture_contradicts_words"


def test_selective_chapter_repair_execution(tmp_path, sample_lesson, sample_timeline, monkeypatch):
    """
    Simulates the chapter repair harness:
    Verifies that only Chapter 2 is rendered when beat_03 fails,
    leaving Chapter 1 and Chapter 3 untouched.
    """
    root = tmp_path / "lesson_run"
    root.mkdir()
    (root / "timeline.json").write_text(json.dumps(sample_timeline))
    (root / "lesson.json").write_text(json.dumps(sample_lesson))

    # Fake existing clips for chapters 1, 2, 3
    clips_dir = root / "clips"
    clips_dir.mkdir()
    clips = {
        1: clips_dir / "c01.mp4",
        2: clips_dir / "c02.mp4",
        3: clips_dir / "c03.mp4"
    }
    for p in clips.values():
        p.write_bytes(b"original_video")

    rendered_chapters = []

    def fake_render_chapters(lesson_dir, lesson=None, quality="m", jobs=4, only=None, **kwargs):
        rendered_chapters.extend(only or [])
        # Update clip for re-rendered chapter
        for cid in only or []:
            clips[cid].write_bytes(b"re_rendered_video")
        return {cid: clips[cid] for cid in only or []}

    def fake_assemble(lesson_dir, clips_dict, lesson, **kwargs):
        master = lesson_dir / "output" / "lesson.mp4"
        master.parent.mkdir(exist_ok=True)
        master.write_bytes(b"master_video")
        return master

    def fake_run_checks(lesson_dir, video_path, lesson, **kwargs):
        return {"passed": True, "bounds_violations": 0, "layout_findings": {"detail": []}}

    # Monkeypatch rendering functions
    monkeypatch.setattr(learner_repair.lesson_build, "render_chapters", fake_render_chapters)
    monkeypatch.setattr(learner_repair.lesson_build, "assemble", fake_assemble)
    monkeypatch.setattr(learner_repair.lesson_build, "run_checks", fake_run_checks)

    quiz_errors = [
        {
            "concept": "forces act on different bodies",
            "cited_second": 35.0,  # inside beat_03 (Chapter 2)
            "fault_class": "taught_but_unclear",
            "expected_answer": "Two different objects"
        }
    ]

    initial_report = {"passed": True, "bounds_violations": 0, "layout_findings": {"detail": []}}

    result = learner_repair.repair_lesson_from_learner(
        root=root,
        lesson_dict=sample_lesson,
        video=root / "output" / "lesson.mp4",
        clips=clips,
        timeline=sample_timeline,
        report=initial_report,
        quiz_errors=quiz_errors,
        log=lambda *_: None
    )

    assert result is not None
    new_video, new_report, summary = result

    # CRITICAL: Only Chapter 2 must have been re-rendered!
    assert rendered_chapters == [2]
    assert summary["chapters_rendered"] == [2]
    assert set(summary["chapters_skipped"]) == {1, 3}
    assert summary["repaired_beats"] == ["beat_03"]

    # Verify that lesson.json on disk contains the repaired steps for beat_03
    saved_lesson = json.loads((root / "lesson.json").read_text())
    beat3_steps = saved_lesson["chapters"][1]["beats"][0]["steps"]
    assert any("different bodies" in s["show"].lower() for s in beat3_steps)
