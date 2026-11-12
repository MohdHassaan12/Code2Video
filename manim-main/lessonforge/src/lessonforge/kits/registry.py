"""The kit registry: the one place a seam asks "is there a kit for this?".

Seams (the figure builder, the writer's discipline gate, the workbench) call :func:`serving` and fall through to
today's code when it answers ``None``. It answers ``None`` for an unknown figure kind, for a ``legacy`` kit (geometry
is still served by the pre-kit code) and for every kind while the ``LESSONFORGE_KITS`` switch is off. So nothing a
kit adds can break an old lesson, and a broken kit never costs a lesson (:func:`guarded`).

Registration is eager and cheap: kit modules hold light metadata, and adapters import heavy modules inside methods.
"""
from __future__ import annotations

import importlib
from typing import Any, Callable, Iterable

from .. import knobs
from .base import GAP, EditOp, Kit, KIT_METHODS, Lesson, Issues, beats_of, quiz_texts

#: Figure kinds the engine already draws, without importing manim (``figures.KINDS`` plus the writer's prepared
#: ``diagram``). ``test_kits_registry`` pins this against ``figures.KINDS`` and ``writer.FIGURE_KINDS``. A new kit may
#: not claim one of these unless it is ``legacy`` (an adapter over the code that already serves the kind).
BUILTIN_KINDS = ("right_triangle", "number_line", "bars", "circle", "rectangle", "graph", "reaction", "scene",
                 "diagram", "picture", "shape", "float")

_KITS: dict[str, Kit] = {}

ONE_SUBJECT = "this lesson draws from two subject kits ({names}); give each lesson one subject"
#: A gap on a beat that belongs to no kit, in a lesson that draws from several: no kit may guess whose value it is.
WHICH_SUBJECT = ("{ref} {where}: gap {{{expr}}} is on a beat with no subject figure, so which subject is this value "
                 "from? Give the beat the figure of its subject ({kinds}) or take the gap out")
MIXED_SWITCH = "LESSONFORGE_KITS_MIXED"


def register(kit: Kit) -> Kit:
    """Add ``kit``. Raises at import time on a name or figure kind that is already taken, or an incomplete kit."""
    name = getattr(kit, "name", None)
    if not isinstance(name, str) or not name.strip():
        raise ValueError("a kit needs a name")
    if name in _KITS:
        raise ValueError(f"kit {name!r} is already registered")
    kinds = tuple(getattr(kit, "figure_kinds", ()) or ())
    if not kinds or not all(isinstance(k, str) and k for k in kinds):
        raise ValueError(f"kit {name!r} needs figure_kinds (a tuple of kind names)")
    missing = [m for m in KIT_METHODS if not callable(getattr(type(kit), m, None))]
    if missing:
        raise TypeError(f"kit {name!r} lacks {', '.join(missing)}")
    legacy = bool(getattr(kit, "legacy", False))
    for kind in kinds:
        owner = for_kind(kind)
        if owner is not None:
            raise ValueError(f"figure kind {kind!r} is already owned by kit {owner.name!r}")
        if kind in BUILTIN_KINDS and not legacy:
            raise ValueError(f"figure kind {kind!r} is a built-in kind: only a legacy adapter kit may own it")
    if not legacy and not str(getattr(kit, "rules", "") or "").strip():
        raise ValueError(f"kit {name!r} needs rules: the words the writer is given for its figure")
    if not legacy:                  # the figure link of the chain: a kind nothing can draw is a silent "previous picture stays"
        built = getattr(kit, "builder", None) or {}
        lacking = [k for k in kinds if ":" not in str(built.get(k) or "")]
        if lacking:
            raise ValueError(f"kit {name!r} needs a builder (\"pkg.mod:func\") for {', '.join(lacking)}: nothing could draw it")
    _KITS[name] = kit
    return kit


def describe() -> list[dict[str, Any]]:
    """Every registered kit as plain JSON, for a router or a page: name, what it draws and who it is for.

    ``subjects``, ``classes`` and ``keywords`` are the routing metadata a kit declares (empty when it declares none);
    ``served`` is False for a legacy kit (the pre-kit code still draws it). Pure data, safe to ``json.dumps``.
    """
    return [{"name": k.name, "figure_kinds": list(k.figure_kinds),
             "subjects": [str(x) for x in getattr(k, "subjects", ()) or ()],
             "classes": [int(x) for x in getattr(k, "classes", ()) or ()],
             "keywords": [str(x) for x in getattr(k, "keywords", ()) or ()],
             "legacy": bool(getattr(k, "legacy", False)),
             "served": not getattr(k, "legacy", False)} for k in _KITS.values()]


def get(name: str) -> Kit | None:
    return _KITS.get(name)


def all_kits() -> list[Kit]:
    return list(_KITS.values())


def for_kind(kind: Any) -> Kit | None:
    """The kit that owns a figure kind, served or not."""
    for kit in _KITS.values():
        if kind in kit.figure_kinds:
            return kit
    return None


def enabled() -> bool:
    """``LESSONFORGE_KITS`` (default on). Off: only the built-in figure kinds and geometry checks run."""
    return str(knobs.get("LESSONFORGE_KITS", "1")).strip() != "0"


def mixed_enabled() -> bool:
    """``LESSONFORGE_KITS_MIXED`` (default on, and only while the kits are on): a lesson may draw from several kits.

    Off, a lesson that draws from two kits gets the one-subject fault and nothing below changes behaviour.
    """
    return enabled() and str(knobs.get(MIXED_SWITCH, "1")).strip() != "0"


def owner_of_beat(beat: Any) -> Kit | None:
    """The kit a beat belongs to: the one that owns its figure's kind (geometry owns ``shape``), else ``None``.

    A beat with no figure, or a figure of a built-in kind no kit owns, belongs to none. Ownership is by kind only, so it
    does not depend on any switch; the callers check :func:`mixed_enabled`.
    """
    fig = beat.get("figure") if isinstance(beat, dict) else None
    return for_kind(fig.get("kind")) if isinstance(fig, dict) and fig.get("kind") else None


def subject_kits(lesson: Lesson, after_edit: bool = False) -> list[Kit]:
    """Every kit (geometry included) whose subject ``lesson`` uses; ``[]`` while the kits are off."""
    if not enabled() or not isinstance(lesson, dict):
        return []
    return [k for k in _KITS.values() if k.uses(lesson, after_edit=after_edit)]


def multi(lesson: Lesson) -> bool:
    """True when mixing is on and ``lesson`` draws from more than one kit: each kit then checks only its own beats."""
    if not mixed_enabled():
        return False
    try:
        return len(subject_kits(lesson)) > 1
    except Exception:  # noqa: BLE001 - a kit that cannot say is not a reason to change how a lesson is checked
        return False


def serving(kind: Any) -> Kit | None:
    """The kit seams should use for ``kind``: None when the switch is off, the kind is unknown, or the kit is legacy."""
    if not enabled():
        return None
    kit = for_kind(kind)
    return None if kit is None or getattr(kit, "legacy", False) else kit


def kinds() -> tuple[str, ...]:
    """Figure kinds of the kits that are served now."""
    if not enabled():
        return ()
    return tuple(k for kit in _KITS.values() if not getattr(kit, "legacy", False) for k in kit.figure_kinds)


def active(lesson: Lesson, after_edit: bool = False) -> list[Kit]:
    """The served kits whose subject this lesson uses."""
    if not enabled() or not isinstance(lesson, dict):
        return []
    return [k for k in _KITS.values() if not getattr(k, "legacy", False) and k.uses(lesson, after_edit=after_edit)]


def builder_for(kind: Any) -> Callable | None:
    """The Manim-side builder for a kit's figure kind, imported now. Called only from ``figures.build``."""
    kit = serving(kind)
    target = (kit.builder or {}).get(kind) if kit is not None else None
    if not target:
        return None
    module, _, func = str(target).partition(":")
    return getattr(importlib.import_module(module), func)


def rules_for(names: Iterable[str] | str | None, log: Callable[[str], Any] = print) -> str:
    """The writer's per-lesson addendum for the kits a brief names: "" when none, so the system prompt is unchanged.

    A name nobody registered is logged and skipped; a legacy kit (geometry) adds no rules because they are already in
    the writer's prompt. One kit named: its rules under one header, as always. Several named (and mixing on): an
    opening line about mixed lessons, then each kit's rules under its own one-line header.
    """
    if not enabled() or not names:
        return ""
    wanted = [names] if isinstance(names, str) else list(names)
    found: list[Kit] = []
    args: dict[str, str] = {}
    for raw in wanted:
        # "kit:argument" asks a kit for rules specific to something it knows ("components:force_block,test_tube")
        name, _, argument = str(raw).partition(":")
        if any(k.name == name for k in found):
            continue
        kit = get(name)
        if kit is None:
            log(f"[writer] kit {name!r} is not registered")
            continue
        found.append(kit)
        if argument.strip() and callable(getattr(kit, "rules_with", None)):
            args[name] = argument.strip()
    many = len(found) > 1 and mixed_enabled()
    parts = []
    for kit in found:
        if getattr(kit, "legacy", False):
            if many:
                parts.append(f"SUBJECT KIT {kit.name} (beats whose figure is {', '.join(kit.figure_kinds)}; its rules are "
                             "the ones already given above)")
            continue
        header = (f"SUBJECT KIT {kit.name} (beats whose figure is {', '.join(kit.figure_kinds)} come from it):" if many
                  else f"SUBJECT KIT {kit.name} (this lesson's figures come from it):")
        text = guarded(f"{kit.name} rules_with", lambda kit=kit: kit.rules_with(args[kit.name]), kit.rules, log) \
            if kit.name in args else kit.rules
        parts.append(f"{header}\n{text}".rstrip())
    if not any(not getattr(k, "legacy", False) for k in found):
        return ""
    if many:
        parts.insert(0, "THIS LESSON MIXES SUBJECTS. Each beat belongs to the kit of its figure, and code checks that beat "
                        "with that kit alone: a gap or a number on a beat is about THAT beat's figure. Every beat that "
                        "has a gap needs a figure of the subject the value is from.")
    return ("\n\n" + "\n\n".join(parts) + "\n") if parts else ""


def mixed(lesson: Lesson) -> str | None:
    """The one-subject-per-lesson fault, only while ``LESSONFORGE_KITS_MIXED`` is off.

    Off: a served kit and another kit (geometry included) both drawing in ``lesson`` is a fault, as it always was.
    On: a mixed lesson is allowed, so there is no such fault (:func:`orphan_gaps` is its check instead).
    """
    if mixed_enabled() or not active(lesson):
        return None
    subjects = [k.name for k in _KITS.values() if k.uses(lesson)]
    return ONE_SUBJECT.format(names=", ".join(subjects)) if len(subjects) > 1 else None


def _beat_texts(beat: dict) -> list[tuple[str, str]]:
    """(where, text) for the words of a beat, labelled as ``KitBase.settle`` labels them."""
    out = [("narration", str(beat.get("narration") or ""))]
    for k, step in enumerate(beat.get("steps") or []):
        if isinstance(step, dict):
            out += [(f"step {k + 1} {f}", str(step.get(f) or "")) for f in ("say", "show")]
    quiz = beat.get("quiz") if isinstance(beat.get("quiz"), dict) else None
    out += [(f"quiz {k}", v) for k, v in (quiz_texts(quiz) if quiz else [])]
    return out


def orphan_gaps(lesson: Lesson) -> Issues:
    """In a lesson that draws from several kits: one fault per gap on a beat no kit owns ("which subject is this from?").

    With one kit (or mixing off) this is empty, because the single kit reports such a gap itself ("no <subject>
    figure"). In a mixed lesson every kit stays silent on such a beat and this reports it once.
    """
    if not multi(lesson):
        return []
    kinds_ = ", ".join(k for kit in subject_kits(lesson) for k in kit.figure_kinds)
    issues: Issues = []
    for number, (ci, beat) in enumerate(beats_of(lesson), start=1):
        if owner_of_beat(beat) is not None:
            continue
        for where, text in _beat_texts(beat):
            issues += [WHICH_SUBJECT.format(ref=f"beat {number} (chapter {ci})", where=where, expr=m.group(1), kinds=kinds_)
                       for m in GAP.finditer(text)]
    return issues


def lesson_faults(lesson: Lesson, log: Callable[[str], Any] = print) -> Issues:
    """Faults the served kits find in a lesson, expected faults dropped, plus the mixed-lesson check.

    Each active kit runs over its own beats (``KitBase.settle`` leaves another kit's beats alone). Mixing on: gaps on
    beats no kit owns are one "which subject" fault each. Mixing off: the one-subject fault, as before.
    """
    kits = active(lesson)
    if not kits:
        return []
    issues: Issues = []
    for kit in kits:
        found = guarded(f"{kit.name} settle", lambda kit=kit: kit.settle(lesson)[1], [], log)
        issues += [i for i in found if not kit.expected_fault(i, lesson)]
    one = mixed(lesson)
    if one:
        issues.append(one)
    issues += guarded("orphan gaps", lambda: orphan_gaps(lesson), [], log)
    return issues


def checkers(lesson: Lesson) -> list[Kit]:
    """The kits that each check their own beats of ``lesson`` in a pass: the served kits it uses, and in a mixed lesson
    geometry too (a repair of one subject can break another's beats). Without mixing, exactly ``active(lesson)``."""
    return subject_kits(lesson) if multi(lesson) else active(lesson)


def repair_prompt(lesson: Lesson, issues: Issues, log: Callable[[str], Any] = print) -> str:
    """The repair request for a lesson's faults: the first served kit's prompt, as before.

    A mixed lesson also gets what the OTHER kits' figures make (worked out by code), so the writer fixes a value
    against the right subject's numbers.
    """
    served = active(lesson)
    if not served:
        return ""
    base = served[0].repair_prompt(lesson, issues)
    if not multi(lesson):
        return base
    facts: list[str] = []
    for kit in subject_kits(lesson):
        if kit is served[0]:
            continue
        for _, beat in beats_of(lesson):
            fig = beat.get("figure")
            if isinstance(fig, dict) and fig.get("kind") in kit.figure_kinds:
                text = guarded(f"{kit.name} describe", lambda kit=kit, fig=fig: kit.describe(fig), "", log)
                if text and text not in facts:
                    facts.append(text)
    if not facts:
        return base
    extra = "\n\nWhat the other subject's figures make, worked out by code:\n" + "\n".join(f"- {f}" for f in facts)
    marker = "\n\nReturn the WHOLE lesson again"
    return base.replace(marker, extra + marker, 1) if marker in base else base + extra


def is_expected_fault(issue: str, lesson: Lesson) -> bool:
    """True when a served kit that this lesson uses says ``issue`` is deliberate (a wrong quiz option)."""
    return any(guarded(f"{k.name} expected_fault", lambda k=k: bool(k.expected_fault(issue, lesson)), False)
               for k in active(lesson))


def settle_active(lesson: Lesson, after_edit: bool = False, log: Callable[[str], Any] = print) -> Lesson:
    """``lesson`` with the gaps of every served kit it uses filled. Faults are not raised here (``lesson_faults``)."""
    for kit in active(lesson, after_edit=after_edit):
        lesson = guarded(f"{kit.name} settle", lambda kit=kit, lesson=lesson: kit.settle(lesson)[0], lesson, log)
    return lesson


def edit_ops() -> dict[str, EditOp]:
    """Extra workbench ops the served kits bring (none today: geometry's ``set_shape`` is built into the workbench)."""
    if not enabled():
        return {}
    return {op: fn for kit in _KITS.values() if not getattr(kit, "legacy", False) for op, fn in (kit.edit_ops or {}).items()}


def slim(lesson: Lesson) -> dict[str, Any]:
    """The lesson-level declarations of the served kits this lesson uses (``data_key``), for the improver's slim view."""
    return {k.data_key: lesson.get(k.data_key) or {} for k in active(lesson) if getattr(k, "data_key", None)}


def rules_for_lesson(lesson: Lesson) -> str:
    """The rules of the served kits a lesson uses, for the improver's user text: "" when it uses none."""
    kits = subject_kits(lesson) if mixed_enabled() else active(lesson)      # mixed: geometry is named too, so the header says so
    return rules_for([guarded(f"{k.name} rules_name", lambda k=k: k.rules_name(lesson), k.name) if callable(getattr(k, "rules_name", None))
                      else k.name for k in kits])


def mcp_note() -> str:
    """One sentence per served, non-legacy kit that has one, to append to the MCP server's instructions."""
    if not enabled():
        return ""
    notes = [str(getattr(k, "mcp_note", "") or "").strip() for k in _KITS.values() if not getattr(k, "legacy", False)]
    return " ".join(n for n in notes if n)


def guarded(label: str, fn: Callable[[], Any], default: Any, log: Callable[[str], Any] = print) -> Any:
    """``fn()``, or ``default`` (and a log line) when it raises: a kit never costs a lesson."""
    try:
        return fn()
    except Exception as exc:  # noqa: BLE001 - the seam's own behaviour stands
        log(f"[kits] {label} failed ({type(exc).__name__}: {str(exc)[:160]})")
        return default
