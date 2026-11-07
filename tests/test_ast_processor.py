"""
Unit tests for AstProcessor.
"""

import pytest
from adapt_manim.coding.ast_processor import AstProcessor


def test_syntax_checker_valid():
    code = "x = 10\ny = x + 5\n"
    assert AstProcessor.check_syntax(code) is None


def test_syntax_checker_invalid():
    code = "def broken(\n  x = 10"
    res = AstProcessor.check_syntax(code)
    assert res is not None
    msg, lineno, offending = res
    assert lineno >= 1


def test_auto_migrate_deprecated_apis():
    bad_code = """
bio_helix = VGroup()
bio_helix.resize(0.75)
self.play(ShowCreation(bio_helix))
"""
    migrated, mods = AstProcessor.auto_migrate_deprecated_apis(bad_code)
    assert ".scale(" in migrated
    assert "Create(" in migrated
    assert ".resize(" not in migrated
    assert "ShowCreation(" not in migrated
    assert len(mods) == 2


def test_extract_lecture_blocks():
    sample_code = """
class MyScene(Scene):
    def construct(self):
        # === Animation for Lecture Line 1 ===
        self.play(FadeIn(dot))
        self.wait(1.0)

        # === Animation for Lecture Line 2 ===
        self.play(Create(line))
        self.wait(1.0)
"""
    blocks = AstProcessor.extract_lecture_blocks(sample_code)
    assert 1 in blocks
    assert 2 in blocks
    assert "FadeIn(dot)" in blocks[1][2]
    assert "Create(line)" in blocks[2][2]

