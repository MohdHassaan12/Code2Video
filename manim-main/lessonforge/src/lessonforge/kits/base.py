"""The shape of a subject kit: a model, the words that teach it, and the code that checks both.

A lesson video was good when four things held: a pure function worked out every number (the MODEL), the figure was
drawn only from that model, gaps in the narration were filled and claims checked by code, and the writer was told the
rules. A kit is that chain as an object, so adding a subject means writing one class instead of editing an
if-chain in five files. ``KitBase`` cannot be instantiated unless a subclass can name its model (``solve``), fill its
gaps (``fill_gap``), check its claims (``claims``), catch a typed number the picture does not show
(``stray_numbers``) and ship its own conformance cases (``cases``).

Import rule: nothing here imports manim, numpy or ``harness.writer`` at import time. An adapter over a heavy module
imports it inside a method.
"""
from __future__ import annotations

import abc
import ast
import copy
import json
import operator
import re
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Protocol, runtime_checkable

Lesson = dict[str, Any]
Figure = dict[str, Any]
Issues = list[str]
LLM = Callable[[str, str], Any]            # (prompt, system) -> parsed JSON; same as writer.LLM
EditOp = Callable[[Lesson, dict], None]    # mutates the working copy of a lesson

#: Same pattern as harness/shapes.py ``_GAP``; ``test_kits_registry`` pins the two equal. A gap stands on its own
#: ("is {speed at 3} m/s"); braces after a letter, ``}``, ``^``, ``_`` or a backslash belong to LaTeX.
GAP = re.compile(r"(?<![A-Za-z}^_\\])\{([^{}]{1,80})\}")
#: ONE message shape for "a number the picture does not show". The writer of the message (``KitBase.settle``) and the
#: matcher (``KitBase.expected_fault``) both use it, so they cannot drift apart the way shapes.py and
#: workbench._expected_fault did. ``where`` carries its own leading space (" quiz option 2").
STRAY = "{ref}{where}: says {what}, which the picture does not show (write a gap instead of a typed value)"
STRAY_RE = re.compile(r"beat (\d+) \(chapter \d+\) quiz option (\d+): says .* which the picture does not show")


class Filled(float):
    """A number a gap was filled with (``expr`` is the gap's text). It is a plain float to any code that adds or compares
    it; a kit's ``stray_numbers`` can read ``expr`` to tell WHICH quantity the number was (an acceleration, a speed)."""
    expr: str = ""

    def __new__(cls, value: float, expr: str = ""):
        self = super().__new__(cls, value)
        self.expr = expr
        return self


class Whole(str):
    """A stray-number finding that is a complete message, not "says {what}". It is a template with ``{ref}`` and
    ``{where}`` (``where`` carries its own leading space), filled by ``KitBase.settle``. Use it when the number is
    shown by the picture but is written with the wrong unit."""


class KitError(ValueError):
    """Inputs that are not a coherent situation. ``str(e)`` is plain words, shown to the writer model as a fault."""


@runtime_checkable
class KitModel(Protocol):
    """What ``solve`` returns: a pure value object, no manim."""

    notes: tuple[str, ...]                 # things code corrected or refused while solving

    def facts(self) -> Mapping[str, Any]: ...        # every number the screen may say, by name
    def shown(self) -> frozenset[float]: ...         # numbers the drawn figure itself carries


@dataclass(frozen=True)
class KitCases:
    """Shipped BY the kit; the conformance test runs them through the kit's own ``settle``."""

    good: tuple[Lesson, ...]                                   # settle() must return no issues
    refused: tuple[tuple[Lesson, str], ...]                    # (lesson, fragment an issue must contain); >= 3
    gaps: tuple[tuple[str, Figure, str], ...]                  # (gap text, figure, exact filled text)


@runtime_checkable
class Kit(Protocol):
    # identity and persisted names
    name: str
    figure_kinds: tuple[str, ...]
    #: Routing metadata (optional: ``registry.describe`` reads it with empty defaults, so a kit that sets none works).
    subjects: tuple[str, ...]                  # school subjects it serves ("maths", "physics", "chemistry", ...)
    classes: tuple[int, ...]                   # NCERT classes it serves (1-12 for maths)
    keywords: tuple[str, ...]                  # words in a brief or beat that suggest this kit (lower case)
    legacy: bool                               # True: seams skip it, the pre-kit code still serves it
    data_key: str | None                       # lesson-level declarations ("shapes"); None = figures carry their inputs
    generated_by: str | None
    check_key: str | None
    builder: Mapping[str, str]                 # kind -> "pkg.mod:func", resolved lazily on the MANIM side only
    # words the model is given
    rules: str
    answer_schema: str | None
    focus_parts: Mapping[str, tuple[str, ...]]
    edit_ops: Mapping[str, EditOp]

    def uses_figures(self, lesson: Lesson) -> bool: ...
    def uses(self, lesson: Lesson, *, after_edit: bool = False) -> bool: ...
    def figure_issues(self, figure: Figure) -> Issues: ...
    def normalise_figure(self, figure: Figure) -> Figure | None: ...
    def numbers(self, figure: Figure) -> set[str]: ...
    def describe(self, figure: Figure) -> str: ...
    def settle(self, lesson: Lesson) -> tuple[Lesson, Issues]: ...
    def unfilled(self, lesson: Lesson) -> bool: ...
    def repair_prompt(self, lesson: Lesson, issues: Issues) -> str: ...
    def expected_fault(self, issue: str, lesson: Lesson) -> bool: ...
    def merge_declared(self, lesson: Lesson, answer: dict) -> None: ...
    def cases(self) -> KitCases: ...


#: The methods ``registry.register`` requires of any kit, abstract or adapter.
KIT_METHODS = ("uses_figures", "uses", "figure_issues", "normalise_figure", "numbers", "describe", "settle",
               "unfilled", "repair_prompt", "expected_fault", "merge_declared", "cases")


# ── small helpers a kit shares ──────────────────────────────────────────────────────────────────────────────────

_OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv}


def arithmetic(expr: str) -> float:
    """A number from ``expr`` made of numbers, + - * / and brackets, nothing else. Raises ``ValueError``.

    A copy of the idea in ``harness/shapes._evaluate`` (which stays private and untouched), so a kit can evaluate the
    arithmetic around its gap terms without importing the geometry module.
    """
    def ev(node):
        if isinstance(node, ast.Expression):
            return ev(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
            return float(node.value)
        if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
            return _OPS[type(node.op)](ev(node.left), ev(node.right))
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
            return -ev(node.operand)
        raise ValueError("only numbers, + - * / and brackets")
    try:
        return ev(ast.parse(expr, mode="eval"))
    except SyntaxError as exc:
        raise ValueError(f"not arithmetic ({exc.msg})") from exc


def beats_of(lesson: Lesson) -> list[tuple[int, dict]]:
    """(chapter number from 1, beat) for every beat, in order."""
    return [(ci, b) for ci, ch in enumerate(lesson.get("chapters") or [], start=1)
            for b in (ch.get("beats") or []) if isinstance(b, dict)]


def figure_kind(beat: dict) -> str:
    fig = beat.get("figure")
    return str(fig.get("kind") or "") if isinstance(fig, dict) else ""


def _words(x):
    """Every string inside ``x`` (a beat list): the WORDS of a lesson, as ``shapes.unfilled`` reads them."""
    if isinstance(x, str):
        yield x
    elif isinstance(x, dict):
        for v in x.values():
            yield from _words(v)
    elif isinstance(x, list):
        for v in x:
            yield from _words(v)


def quiz_texts(quiz: dict) -> list[tuple[str, str]]:
    out = [("question", quiz.get("question")), ("explain", quiz.get("explain"))]
    out += [(f"option {i + 1}", o) for i, o in enumerate(quiz.get("options") or [])]
    out += [(f"reason {i + 1}", o) for i, o in enumerate(quiz.get("why") or [])]
    return [(k, v) for k, v in out if isinstance(v, str)]


# ── the base class ──────────────────────────────────────────────────────────────────────────────────────────────

class KitBase(abc.ABC):
    """The five abstract methods ARE the rule: a subclass without them cannot be instantiated, so cannot register."""

    name: str
    figure_kinds: tuple[str, ...]
    rules: str
    subjects: tuple[str, ...] = ()
    classes: tuple[int, ...] = ()
    keywords: tuple[str, ...] = ()
    legacy = False
    data_key: str | None = None
    generated_by: str | None = None
    check_key: str | None = None
    builder: Mapping[str, str] = {}
    answer_schema: str | None = None
    focus_parts: Mapping[str, tuple[str, ...]] = {}
    edit_ops: Mapping[str, EditOp] = {}
    mcp_note: str = ""                     # one sentence for the MCP server's instructions; "" says nothing

    # -- what a subclass supplies --

    @abc.abstractmethod
    def solve(self, figure: Figure) -> KitModel:
        """PURE. The model of this figure's situation, or ``KitError`` in plain words."""

    @abc.abstractmethod
    def fill_gap(self, expr: str, model: KitModel) -> tuple[str, float]:
        """(text to print, value) for the inside of one ``{gap}``, or ``KitError``."""

    @abc.abstractmethod
    def claims(self, text: str, model: KitModel) -> Issues:
        """Qualitative claims in ``text`` that the model denies ("speeds up", "balanced")."""

    @abc.abstractmethod
    def stray_numbers(self, text: str, model: KitModel, used: list[float]) -> list[str]:
        """What typed values in ``text`` are neither shown by the picture nor filled from a gap, as "10 m/s". ``used`` holds
        the numbers gaps were filled with (:class:`Filled`). A finding may be a :class:`Whole` message instead."""

    @abc.abstractmethod
    def cases(self) -> KitCases:
        """Good lessons, refused lessons and exact gap fills, run by the conformance test."""

    # -- recognising this kit's lesson --

    def uses_figures(self, lesson: Lesson) -> bool:
        return any(figure_kind(b) in self.figure_kinds for _, b in beats_of(lesson))

    def uses(self, lesson: Lesson, *, after_edit: bool = False) -> bool:
        if self.data_key and lesson.get(self.data_key):
            return True
        if self.uses_figures(lesson):
            return True
        return bool(after_edit and self.data_key
                    and any(isinstance(b.get("figure"), dict) and b["figure"].get("use") for _, b in beats_of(lesson)))

    # -- figure level --

    def figure_issues(self, figure: Figure) -> Issues:
        try:
            model = self.solve(figure)
        except KitError as exc:
            return [str(exc)]
        return list(model.notes)

    def normalise_figure(self, figure: Figure) -> Figure | None:
        try:
            self.solve(figure)
        except KitError:
            return None
        return dict(figure)

    def numbers(self, figure: Figure) -> set[str]:
        try:
            model = self.solve(figure)
        except KitError:
            return set()
        return {f"{x:g}" for x in model.shown()}

    def describe(self, figure: Figure) -> str:
        try:
            facts = self.solve(figure).facts()
        except KitError as exc:
            return str(exc)
        return "; ".join(f"{k} {v:g}" if isinstance(v, (int, float)) else f"{k} {v}" for k, v in facts.items()
                         if v is not None)

    # -- lesson level (the generic form of shapes.settle's per-beat loop) --

    def settle(self, lesson: Lesson) -> tuple[Lesson, Issues]:
        """The lesson with every gap of a beat that shows our figure filled, and every fault found on the way.

        Per beat whose figure kind is ours: solve (a ``KitError`` is a fault), fill gaps in the narration, steps
        (say and show) and quiz, check claims and typed numbers, and refuse two quiz options that come out the same.
        A gap on a beat with no figure of ours is a fault. Beats of other kinds are untouched.
        """
        quiet = self._mixed(lesson)
        lesson = copy.deepcopy(lesson)
        issues: Issues = []
        for number, (ci, beat) in enumerate(beats_of(lesson), start=1):
            ref = f"beat {number} (chapter {ci})"
            fig = beat.get("figure") if isinstance(beat.get("figure"), dict) else None
            ours = bool(fig and fig.get("kind") in self.figure_kinds)
            model = None
            if ours:
                try:
                    model = self.solve(fig)
                except KitError as exc:
                    issues.append(f"{ref}: {exc}")
                else:
                    issues += [f"{ref}: {n}" for n in model.notes]
            used: list[float] = []

            def fill(text: str, where: str) -> str:
                if not isinstance(text, str) or "{" not in text:
                    return text

                def put(match):
                    expr = match.group(1)
                    if not ours:
                        if self._foreign(fig) or quiet:
                            # another kit's gap: its own settle reports it. In a mixed lesson a gap on a beat no kit
                            # owns is reported once by ``registry.orphan_gaps`` ("which subject is this value from?").
                            return match.group(0)
                        issues.append(f"{ref} {where}: gap {{{expr}}} on a beat with no {self.name} figure")
                        return match.group(0)
                    if model is None:
                        return match.group(0)                # the figure is unsolvable: reported above
                    try:
                        shown, value = self.fill_gap(expr, model)
                    except KitError as exc:
                        issues.append(f"{ref} {where}: {exc}")
                        return match.group(0)
                    used.append(Filled(value, expr))
                    return shown
                return GAP.sub(put, text)

            beat["narration"] = fill(str(beat.get("narration") or ""), "narration")
            for k, step in enumerate(beat.get("steps") or []):
                if isinstance(step, dict):
                    for field in ("say", "show"):
                        step[field] = fill(str(step.get(field) or ""), f"step {k + 1} {field}")
            quiz = beat.get("quiz") if isinstance(beat.get("quiz"), dict) else None
            if quiz:
                for field in ("question", "explain"):
                    quiz[field] = fill(str(quiz.get(field) or ""), f"quiz {field}")
                for field, label in (("options", "option"), ("why", "reason")):
                    quiz[field] = [fill(str(item), f"quiz {label} {i + 1}") for i, item in enumerate(quiz.get(field) or [])]
                if ours:
                    opts = [re.sub(r"\s+", " ", o.strip().lower()) for o in quiz.get("options") or []]
                    if len(set(opts)) < len(opts):
                        issues.append(f"{ref} quiz: two options come out the same once filled ({quiz.get('options')}): "
                                      "each wrong option must be a different number or answer")
            if model is None:
                continue
            claimed = [("narration", beat["narration"])]
            claimed += [(f"step {k + 1}", s.get("show") or "") for k, s in enumerate(beat.get("steps") or [])
                        if isinstance(s, dict)]
            claimed += [(f"quiz {k}", v) for k, v in (quiz_texts(quiz) if quiz else []) if k in ("question", "explain")]
            for where, text in claimed:
                issues += [f"{ref} {where}: {c}" for c in self.claims(text, model)]
            typed = [("narration", beat["narration"])] + [(f"step {k + 1}", s.get("show") or "")
                                                          for k, s in enumerate(beat.get("steps") or [])
                                                          if isinstance(s, dict)]
            typed += [(f"quiz {k}", v) for k, v in (quiz_texts(quiz) if quiz else [])]
            for where, text in typed:
                issues += [what.format(ref=ref, where=f" {where}") if isinstance(what, Whole)
                           else STRAY.format(ref=ref, where=f" {where}", what=what)
                           for what in self.stray_numbers(text, model, used)]
        return lesson, issues

    @staticmethod
    def _mixed(lesson: Lesson) -> bool:
        """True when this lesson draws from several kits and mixing is on (``LESSONFORGE_KITS_MIXED``)."""
        from . import registry  # noqa: PLC0415 - registry imports this module
        return registry.multi(lesson)

    @staticmethod
    def _foreign(fig: Figure | None) -> bool:
        """True when ``fig`` is a figure of another registered kit (its gaps are that kit's business)."""
        kind = str((fig or {}).get("kind") or "")
        if not kind:
            return False
        from . import registry  # noqa: PLC0415 - registry imports this module
        return registry.for_kind(kind) is not None

    def unfilled(self, lesson: Lesson) -> bool:
        """True while a gap is left in the WORDS of a beat (not in a figure's JSON, which can look like one)."""
        return any(GAP.search(w) for c in lesson.get("chapters") or [] for w in _words(c.get("beats")))

    def expected_fault(self, issue: str, lesson: Lesson) -> bool:
        """A wrong quiz option that names a number the picture does not show is the point of the option."""
        m = STRAY_RE.match(issue)
        if not m:
            return False
        beats = [b for _, b in beats_of(lesson)]
        k = int(m.group(1)) - 1
        quiz = beats[k].get("quiz") if 0 <= k < len(beats) else None
        return isinstance(quiz, dict) and int(m.group(2)) - 1 != int(quiz.get("answer_index", -1))

    def repair_prompt(self, lesson: Lesson, issues: Issues) -> str:
        facts = []
        for _, beat in beats_of(lesson):
            fig = beat.get("figure")
            if isinstance(fig, dict) and fig.get("kind") in self.figure_kinds:
                text = self.describe(fig)
                if text and text not in facts:
                    facts.append(text)
        return ("Code checked your lesson against its own pictures and found these faults:\n"
                + "\n".join(f"- {i}" for i in issues[:40])
                + ("\n\nWhat your figures make, worked out by code:\n" + "\n".join(f"- {f}" for f in facts) if facts else "")
                + "\n\nReturn the WHOLE lesson again as JSON in the same shape, with every fault fixed. Change only what a "
                  "fault needs: fix a number, a gap, a word. Keep every other word as it is.\n\nYOUR LESSON:\n"
                + json.dumps(lesson, ensure_ascii=False))

    def merge_declared(self, lesson: Lesson, answer: dict) -> None:
        """Merge lesson-level declarations from a director's answer. A no-op: a kit with no ``data_key`` has none."""
        return None
