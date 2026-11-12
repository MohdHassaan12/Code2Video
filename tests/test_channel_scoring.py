"""
Unit tests for Direction D13: Multimodal Channel Attribution (Voice vs. Pictures).
Verifies that evaluating learning gains across voice-only, pictures-only, and multimodal
channels accurately identifies visual uplift and catches redundant "talking head" animations.
"""

from code2video.channel_scoring import MultimodalChannelScorer, ChannelScoreResult


def test_channel_scoring_strong_multimodal():
    topic = "Fourier Epicycles"
    quiz = [{"q": f"q_{i}"} for i in range(10)]

    def mock_student(evidence: str, channel: str):
        if channel == "voice_only":
            # Answers 5 questions correctly
            return [True] * 5 + [False] * 5
        elif channel == "pictures_only":
            # Answers 6 questions correctly
            return [True] * 6 + [False] * 4
        else:
            # Multimodal answers 9 questions correctly
            return [True] * 9 + [False] * 1

    res = MultimodalChannelScorer.evaluate_channels(
        topic=topic,
        quiz_items=quiz,
        student_fn=mock_student,
        voice_script="Audio narration about complex winding numbers.",
        visual_description="Animations showing rotating circle vectors and center of mass.",
    )

    assert res.s_voice_only == 50.0
    assert res.s_pictures_only == 60.0
    assert res.s_multimodal == 90.0
    assert res.visual_uplift == 40.0
    assert res.audio_uplift == 30.0
    assert res.synergy == 30.0
    assert res.verdict == "strong_multimodal"


def test_channel_scoring_visual_redundant():
    topic = "History of Mathematics"
    quiz = [{"q": f"q_{i}"} for i in range(10)]

    def mock_student(evidence: str, channel: str):
        if channel == "voice_only":
            return [True] * 7 + [False] * 3
        elif channel == "pictures_only":
            # Pictures are just decorative shapes that don't teach anything
            return [True] * 2 + [False] * 8
        else:
            # Multimodal is identical to voice only
            return [True] * 7 + [False] * 3

    res = MultimodalChannelScorer.evaluate_channels(
        topic=topic,
        quiz_items=quiz,
        student_fn=mock_student,
        voice_script="Narration explaining biographical dates and facts.",
        visual_description="Abstract geometric cubes spinning passively in the background.",
    )

    assert res.s_voice_only == 70.0
    assert res.s_pictures_only == 20.0
    assert res.s_multimodal == 70.0
    assert res.visual_uplift == 0.0
    assert res.verdict == "visual_redundant"


def test_channel_scoring_calibrated():
    res = MultimodalChannelScorer.simulate_calibrated_scoring("Support Vector Machine", is_visual_heavy=True)
    assert isinstance(res, ChannelScoreResult)
    assert res.s_multimodal > res.s_voice_only
    assert res.visual_uplift > 0.0

