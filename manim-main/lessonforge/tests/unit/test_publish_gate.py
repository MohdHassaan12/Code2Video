"""A finished lesson that failed its own checks waits for a person instead of going to the site by itself."""
from lessonforge.harness import publish

SPEED = {  # the speed lesson as it shipped on 2026-10-16 (job 20261016-153953-da0299)
    "verification": {"scores": {"conceptual_accuracy": 3, "visual_truthfulness": 2, "explanatory_clarity": 2,
                                "pedagogy": 2}},
    "checks": {"status": "technical_checks_failed", "failed": ["no cue fired more than 0.5s after its spoken anchor"]},
    "vision_review": {"findings": [{"kind": "mismatch", "severity": "high", "what": "car, words about a bus"}] * 6},
}
GOOD = {"verification": {"scores": {"conceptual_accuracy": 4, "visual_truthfulness": 4, "explanatory_clarity": 3,
                                    "pedagogy": 2}},
        "checks": {"status": "technical_checks_passed", "failed": []},
        "vision_review": {"findings": [{"kind": "mismatch", "severity": "high", "what": "x"},
                                       {"kind": "stale", "severity": "high", "what": "y"}]}}


def test_the_speed_lesson_is_held_back_with_every_reason(monkeypatch):
    monkeypatch.delenv("LESSONFORGE_PUBLISH_GATE", raising=False)
    why = publish.held_back(SPEED)
    assert any("visual_truthfulness 2/5" in w for w in why)
    assert any("explanatory_clarity 2/5" in w for w in why)
    assert any("technical checks failed: no cue fired" in w for w in why)
    assert any("6 plain picture/voice mismatches" in w for w in why)
    assert not any("pedagogy" in w for w in why)          # its rubric is off by default


def test_a_lesson_that_passed_goes_out_and_old_records_without_scores_too(monkeypatch):
    monkeypatch.delenv("LESSONFORGE_PUBLISH_GATE", raising=False)
    assert publish.held_back(GOOD) == []
    assert publish.held_back({}) == []


def test_the_gate_can_be_turned_off_or_set(monkeypatch):
    monkeypatch.setenv("LESSONFORGE_PUBLISH_GATE", "0")
    assert publish.held_back(SPEED) == []
    monkeypatch.setenv("LESSONFORGE_PUBLISH_GATE", "1")
    monkeypatch.setenv("LESSONFORGE_PUBLISH_MIN_SCORE", "4.5")
    assert any("conceptual_accuracy 4/5" in w for w in publish.held_back(GOOD))
