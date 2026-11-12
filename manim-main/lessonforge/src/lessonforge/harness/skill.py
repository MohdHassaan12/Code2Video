"""The teaching-script skill — the craft of the script, kept as files a teacher can read.

``writer.SYSTEM`` holds the FORMAT of a script (what code checks after the model
answers). How to TEACH lives in ``skills/teaching-script/``: the principles, the moves
of a beat, the try-it task, the card and the reviewer's questions. The folder follows
the open SKILL.md layout (name = folder name, lowercase with a hyphen), so it can also
be loaded by hand into an assistant that reads skills.

Code decides which parts a caller reads: the card maker gets the principles, the card
rules and the task rules; the writer gets the principles, the moves and how a teacher
talks (``voice.md``, which ``voice.py`` measures and repairs). ``VERSION`` is a
hash of every file — a change to the skill is a change to what gets written, so it
belongs in whatever a caller caches by (the lesson's card records it).
"""
from __future__ import annotations

import hashlib
import re
from functools import lru_cache
from pathlib import Path

FOLDER = Path(__file__).parent / "skills" / "teaching-script"
PARTS = ("SKILL.md", "moves.md", "voice.md", "explainers.md", "practicum.md", "card.md", "checks.md")


@lru_cache(maxsize=None)
def part(name: str) -> str:
    """One file of the skill, without its front matter. '' when it is missing."""
    try:
        text = (FOLDER / name).read_text(encoding="utf-8")
    except OSError:
        return ""
    return re.sub(r"\A---\n.*?\n---\n", "", text, flags=re.S).strip()


def text(*names: str) -> str:
    return "\n\n".join(p for p in (part(n) for n in names) if p)


def for_writer() -> str:
    return text("SKILL.md", "moves.md", "voice.md", "explainers.md")


def for_card() -> str:
    return text(*CARD_PARTS)


def for_reviewer() -> str:
    return text("checks.md")


CARD_PARTS = ("SKILL.md", "card.md", "practicum.md")


@lru_cache(maxsize=None)
def version(*names: str) -> str:
    """A hash of the skill's files, or of the ones named."""
    return hashlib.sha256("\x00".join(part(n) for n in (names or PARTS)).encode("utf-8")).hexdigest()[:10]


def card_version() -> str:
    """The version of what the CARD is made from. A topic's card is kept until this changes:
    rewording how a beat is written (moves.md) must not throw away, and bill again for,
    every card in the library."""
    return version(*CARD_PARTS)
