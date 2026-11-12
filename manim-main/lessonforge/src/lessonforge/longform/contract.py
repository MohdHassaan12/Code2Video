"""The lesson contract: what a long-form lesson IS, independent of how it is rendered.

A lesson is chapters of beats. A beat is one teaching move: the words spoken, what the
picture must do while they are spoken, and what the viewer should be able to do after.
The narration is the spine — every later stage (speech, timeline, scenes, captions)
is derived from it and none of them may reorder or rewrite it.

This is the ``lesson.json`` shape used by the reviewed Pythagoras lesson, formalised.
Unknown keys are preserved, so a lesson can carry review notes or provenance without
a schema change here.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Iterator, List, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

_SENTENCE_END = re.compile(r"(?<=[.!?।])\s+")


def split_sentences(text: str) -> List[str]:
    """Narration → sentences. ``।`` (danda) ends a sentence too, for Hindi narration."""
    return [s for s in _SENTENCE_END.split((text or "").strip()) if s]


class Beat(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str = Field(description="Lesson-wide unique id, e.g. '07'. Cue anchors and audits refer to it.")
    narration: str = Field(description="Exactly what is spoken. Never contains stage directions.")
    visual: str = Field("", description="What the picture does while the narration plays.")
    board_text: str = Field("", description="Short on-screen wording for this beat, if any.")
    equation: str = Field("", description="Reference LaTeX for this beat, if any (no surrounding $).")
    thinking_pause_seconds: float = Field(
        0.0, ge=0, description="Silence held AFTER the speech for the viewer to think. Never synthesized.")
    check: str = Field("", description="What the viewer should be able to see/say/do after this beat.")

    @property
    def sentences(self) -> List[str]:
        return split_sentences(self.narration)


class Chapter(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: int = Field(description="Chapter number, starting at 1. Scene classes are named C01, C02, …")
    title: str
    learning_goal: str = ""
    beats: List[Beat] = Field(min_length=1)

    @property
    def scene_name(self) -> str:
        return f"C{self.id:02}"


class Lesson(BaseModel):
    model_config = ConfigDict(extra="allow")

    title: str
    thesis: str = ""
    prerequisites: List[str] = Field(default_factory=list)
    language: str = Field("en-US", description="BCP-47 locale of the narration. One lesson file per language.")
    eyebrow: Optional[str] = Field(None, description="Small running header on every frame; defaults to the title.")
    chapters: List[Chapter] = Field(min_length=1)

    @model_validator(mode="after")
    def _ids_are_usable(self) -> "Lesson":
        chapter_ids = [c.id for c in self.chapters]
        if len(set(chapter_ids)) != len(chapter_ids):
            raise ValueError(f"duplicate chapter ids: {chapter_ids}")
        seen: dict[str, int] = {}
        for chapter in self.chapters:
            for beat in chapter.beats:
                if beat.id in seen:
                    raise ValueError(f"beat id {beat.id!r} is used in chapters {seen[beat.id]} and {chapter.id}")
                seen[beat.id] = chapter.id
                if not beat.narration.strip():
                    raise ValueError(f"beat {beat.id!r} has no narration")
        return self

    def beats(self) -> Iterator[tuple[Chapter, Beat]]:
        for chapter in self.chapters:
            for beat in chapter.beats:
                yield chapter, beat

    def chapter(self, chapter_id: int) -> Chapter:
        for chapter in self.chapters:
            if chapter.id == chapter_id:
                return chapter
        raise KeyError(f"no chapter {chapter_id}")

    @property
    def word_count(self) -> int:
        return sum(len(b.narration.split()) for _, b in self.beats())


def load_lesson(path: str | Path) -> Lesson:
    """Load and validate ``lesson.json`` (a directory is taken to contain one)."""
    p = Path(path)
    if p.is_dir():
        p = p / "lesson.json"
    return Lesson.model_validate(json.loads(p.read_text(encoding="utf-8")))
