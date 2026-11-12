"""Audio-first long-form lessons: contract → speech → measured timeline → chapters → checks.

Submodules import lazily on purpose: ``contract`` is pure Pydantic, ``audio`` needs
only numpy + ffmpeg, and ``runtime`` imports manim (it runs inside the render).
"""
from .contract import Beat, Chapter, Lesson, load_lesson, split_sentences  # noqa: F401
