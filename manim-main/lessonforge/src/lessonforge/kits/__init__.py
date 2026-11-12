"""Subject kits: add a subject by registering one :class:`KitBase` instead of editing if-chains.

``import lessonforge.kits`` is cheap and pure (no manim, numpy or harness import): kit modules hold light metadata,
adapters import heavy modules inside their methods, and a kit's Manim-side builder is a dotted path that only
``longform.figures.build`` resolves. The design, the protocol and the rules a new kit must meet are in
``docs/engine/kits.md``.
"""
from __future__ import annotations

import importlib

from .base import (GAP, STRAY, STRAY_RE, EditOp, Figure, Issues, Kit, KitBase, KitCases, KitError, KitModel, Lesson,
                   arithmetic)
from .registry import (BUILTIN_KINDS, ONE_SUBJECT, active, all_kits, builder_for, describe, edit_ops, enabled, for_kind, get,
                       guarded, is_expected_fault, kinds, lesson_faults, mcp_note, mixed, mixed_enabled, multi,
                       orphan_gaps, owner_of_beat, register, repair_prompt, rules_for, rules_for_lesson,
                       serving, settle_active, slim, subject_kits, checkers)

#: A new subject is one module here plus its name in this tuple. Each module registers its kit on import.
_BUILTIN: tuple[str, ...] = ("geometry", "motion", "reaction", "components")

for _name in _BUILTIN:
    importlib.import_module(f"{__name__}.{_name}")

__all__ = ["GAP", "STRAY", "STRAY_RE", "EditOp", "Figure", "Issues", "Kit", "KitBase", "KitCases", "KitError",
           "KitModel", "Lesson", "arithmetic", "BUILTIN_KINDS", "ONE_SUBJECT", "active", "all_kits", "builder_for", "describe",
           "edit_ops", "enabled", "for_kind", "get", "guarded", "is_expected_fault", "kinds", "lesson_faults",
           "mcp_note", "mixed", "mixed_enabled", "multi", "orphan_gaps", "owner_of_beat", "register", "repair_prompt", "checkers", "rules_for",
           "rules_for_lesson", "serving", "settle_active", "slim", "subject_kits"]
