"""
Unit tests for Novel Features Beyond the Original Paper:
1. VisionAccessibilityAuditor (WCAG AAA Contrast, Visual Clutter, Split Attention)
2. MultiLingualEngine (Multi-Lingual Neural Speech, Formula Phonetics, WebVTT subtitles)
3. InteractivePlayerGenerator (Active-Recall Interactive Web Companion)
4. MathPlaygroundGenerator (Explorable Explanations Parameter Sandbox)
"""

import os
import pytest
from PIL import Image, ImageDraw
import numpy as np

from code2video.vision_auditor import VisionAccessibilityAuditor
from code2video.multilingual import MultiLingualEngine
from code2video.interactive_player import InteractivePlayerGenerator
from code2video.math_playground import MathPlaygroundGenerator
from adapt_manim.core.types import Storyboard, StoryboardSection, LectureCue, AnimationStep


def test_wcag_contrast_ratio():
    """Verifies standard WCAG contrast ratio calculations."""
    black = (0, 0, 0)
    white = (255, 255, 255)
    ratio = VisionAccessibilityAuditor.calculate_contrast_ratio(white, black)
    assert ratio >= 20.0  # ~21:1 for black and white

    # Low contrast gray on black
    dark_gray = (40, 40, 40)
    ratio_low = VisionAccessibilityAuditor.calculate_contrast_ratio(dark_gray, black)
    assert ratio_low < 4.5  # fails WCAG AA


def test_vision_auditor_on_generated_image(tmp_path):
    """Verifies full keyframe audit on a generated test frame."""
    img_path = str(tmp_path / "test_frame.png")
    # Create black canvas with bright white text/geometry
    img = Image.new("RGB", (400, 300), color=(15, 17, 23))
    draw = ImageDraw.Draw(img)
    draw.rectangle([50, 50, 150, 150], fill=(88, 196, 221))  # cyan rectangle
    draw.ellipse([250, 100, 320, 170], fill=(131, 193, 103))  # green circle
    img.save(img_path)

    report = VisionAccessibilityAuditor.audit_keyframe(img_path)
    assert "composite_accessibility_score" in report
    assert report["composite_accessibility_score"] > 0
    assert "wcag_contrast" in report
    assert "visual_clutter" in report
    assert "spatial_contiguity" in report
    assert report["wcag_contrast"]["passed_wcag_aa"] is True


def test_multilingual_engine_supported_languages():
    """Verifies that all 7 languages and neural voices are registered."""
    langs = MultiLingualEngine.get_supported_languages()
    assert len(langs) == 7
    codes = [l["code"] for l in langs]
    assert "en" in codes
    assert "es" in codes
    assert "de" in codes
    assert "fr" in codes
    assert "hi" in codes
    assert "zh" in codes
    assert "ja" in codes


def test_multilingual_formula_phoneticization():
    """Verifies that LaTeX formulas are translated to natural spoken text."""
    math_text = r"Notice that e^{i\pi} + 1 = 0 connects five fundamental constants."
    spoken_es = MultiLingualEngine.phoneticize_formulas(math_text, "es")
    assert "e elevado a la i pi" in spoken_es

    spoken_de = MultiLingualEngine.phoneticize_formulas(math_text, "de")
    assert "e hoch i pi" in spoken_de


def test_multilingual_webvtt_subtitle_generation(tmp_path):
    """Verifies WebVTT subtitle track generation."""
    vtt_path = str(tmp_path / "subtitles.vtt")
    cues = [
        {"cue_id": "c1", "duration_sec": 3.5, "localized_text": "Bienvenidos a la clase."},
        {"cue_id": "c2", "duration_sec": 4.0, "localized_text": "Esta es la fórmula de Euler."}
    ]
    out = MultiLingualEngine.generate_webvtt_subtitles(cues, vtt_path)
    assert os.path.exists(out)
    with open(out, "r", encoding="utf-8") as f:
        content = f.read()
    assert "WEBVTT" in content
    assert "00:00:00.000 --> 00:00:03.500" in content
    assert "Bienvenidos a la clase." in content


def test_interactive_player_html_generation(tmp_path):
    """Verifies generation of standalone interactive active-recall companion player."""
    player_path = str(tmp_path / "interactive_lecture.html")
    storyboard = Storyboard(
        topic="Euler's Formula",
        sections=[
            StoryboardSection(
                id="sec1",
                title="Introduction to Phasors",
                cues=[LectureCue(cue_id="c1", text="Euler formula connects exponential and trigonometry.")],
                animation_steps=[AnimationStep(step_id="s1", paired_cue_id="c1", description="Draw phasor", anchor_target="B2")]
            )
        ]
    )
    quizzes = [
        {
            "question": "What is e^(i pi)?",
            "options": ["A) 1", "B) -1", "C) 0", "D) i"],
            "answer_index": 1,
            "explanation": "e^(i pi) = cos(pi) + i sin(pi) = -1."
        }
    ]
    out = InteractivePlayerGenerator.generate_player_html(
        topic="Euler's Formula",
        video_filename="euler.mp4",
        storyboard=storyboard,
        quiz_items=quizzes,
        output_path=player_path,
        section_durations=[12.0]
    )
    assert os.path.exists(out)
    with open(out, "r", encoding="utf-8") as f:
        html = f.read()
    assert "Euler's Formula" in html
    assert "euler.mp4" in html
    assert "Active-Recall Checkpoint" in html
    assert "What is e^(i pi)?" in html
    assert "ontimeupdate" in html


def test_mathematical_parameter_playgrounds(tmp_path):
    """Verifies HTML5 Canvas interactive parameter sandbox exports."""
    euler_path = str(tmp_path / "euler.html")
    svm_path = str(tmp_path / "svm.html")

    p1 = MathPlaygroundGenerator.generate_euler_playground(euler_path)
    p2 = MathPlaygroundGenerator.generate_svm_playground(svm_path)

    assert os.path.exists(p1)
    assert os.path.exists(p2)

    with open(p1, "r", encoding="utf-8") as f:
        h1 = f.read()
    assert "<canvas" in h1
    assert "Euler's Formula" in h1

    with open(p2, "r", encoding="utf-8") as f:
        h2 = f.read()
    assert "<canvas" in h2
    assert "Support Vector Machine" in h2
