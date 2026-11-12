"""What a lesson's paid steps produced, kept so the same work is never bought twice.

A lesson is made in stages, and until 2026-10-09 only two of them kept what they made
where another run could find it: an animation (by its description) and, since that
morning, a block of narration (by voice and words). The two steps that cost the most
did not: the script, or for a pasted script the screen planned for it, and its review.
So "Try again" on a lesson that had failed at its LAST step planned the screen, reviewed
it and drew what was not cached all over again. The owner pressed it on an 8.5-minute
lesson whose render had stuck and paid about 2.7 USD for a second copy of work that was
sitting in the failed lesson's folder; their words: "when gen got failed it is starting
from scratch" and "store content so we dont need to regen again things in the pipeline".

Here a stage's result is kept under a key made from EVERYTHING it was made from (the
brief, the prompts in force, the models asked, the card), so:

* the same request again finds it, whichever job asks and however the first one ended;
* a changed script, a changed prompt or another model is another key, and is made anew;
* nothing here can serve a result for an input it was not made from.

It is kept after the stage has finished and passed its own checks, never per model
call: a reply that code rejected and asked for again must not come back from a store.

``HARNESS_STORE=0`` switches reading and writing off. A brief with ``fresh: true`` is
made anew and replaces what was kept (for "I want a different take on the same script").
Entries live in ``<workspace>/cache/stages/<stage>/``; nothing prunes them (a script's
plan is a few kilobytes).
"""
from __future__ import annotations

import hashlib
import json
import os
import time

from .. import knobs
from .. import paths

#: Part of every key. Raise it when what a stage RETURNS changes shape, so older entries are not read.
VERSION = 1
#: Brief keys that say how to run, not what to make: they never change what a stage produces.
_NOT_CONTENT = ("fresh", "voice_for", "voice_choice", "draft_file", "needs_focus", "stop_after")


def enabled() -> bool:
    return knobs.get("HARNESS_STORE", "1") == "1"


def content(brief: dict) -> dict:
    """The brief as far as it decides WHAT is made."""
    return {k: v for k, v in sorted(brief.items()) if k not in _NOT_CONTENT}


def key(*made_from) -> str:
    """One key from everything a result was made from (anything JSON can write; order matters)."""
    text = json.dumps([VERSION, *made_from], sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:40]


def _file(stage: str, key_: str):
    return paths.cache("stages") / stage / f"{key_}.json"


def get(stage: str, key_: str, fresh: bool = False):
    """What was kept for this stage and key, or None (also when the store is off or a fresh take is asked for)."""
    if fresh or not enabled():
        return None
    try:
        return json.loads(_file(stage, key_).read_text(encoding="utf-8"))["value"]
    except (OSError, ValueError, KeyError):
        return None


def put(stage: str, key_: str, value) -> None:
    """Keep a stage's finished result. Never raises: a full disk must not cost a lesson."""
    if not enabled():
        return
    try:
        file = _file(stage, key_)
        file.parent.mkdir(parents=True, exist_ok=True)
        part = file.with_suffix(".part")
        part.write_text(json.dumps({"stage": stage, "kept": time.strftime("%Y-%m-%d %H:%M:%S"), "value": value},
                                   ensure_ascii=False), encoding="utf-8")
        part.replace(file)                       # whole or not at all: a reader never sees half an entry
    except (OSError, TypeError, ValueError):
        pass
