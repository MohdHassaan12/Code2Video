"""Geometry as kit #1: a legacy adapter over ``harness/shapes.py``, with no behaviour of its own.

Geometry predates the registry and keeps being served by the code that already serves it (``legacy = True``: seams
skip it). This class exists so the registry knows the subject, so a lesson that mixes geometry with a served kit gets
the one-subject fault, and so the day geometry is routed through the registry (a later, separate decision) the call
sites already have a kit to ask. Every method delegates to ``harness.shapes`` or repeats, word for word, the rule
that lives in ``workbench`` / ``edit`` today; ``test_kits_geometry_parity`` holds them equal.

``harness.shapes`` is imported inside methods only, so ``import lessonforge.kits`` stays free of the harness.
"""
from __future__ import annotations

from typing import Mapping

from .base import STRAY_RE, EditOp, Figure, Issues, KitCases, KitError, Lesson, beats_of, figure_kind
from .registry import register
from ..longform.component_lib import SCOPE_CLASSES


def _unexpand(part: dict, name: str, old: dict) -> None:
    """Turn a figure (or panel) that ``shapes.expand`` filled in from shape ``name`` back into ``{"use": name, ...}``.

    Everything the old shape contributed is removed (points, polygon, frame and so on, when the figure still holds the
    old value); what the beat itself said (angles, segments, a moved corner, a point it overrides) stays.
    """
    base = {k: v for k, v in old.items() if k != "is"}
    for key, value in base.items():
        if key == "points":
            mine = {k: v for k, v in (part.get("points") or {}).items() if value.get(k) != v}
            if mine:
                part["points"] = mine
            else:
                part.pop("points", None)
        elif part.get(key) == value:
            part.pop(key, None)
    part["use"] = name
    part.pop("_name", None)


def reexpand_users(lesson: Lesson, name: str, old: dict | None) -> int:
    """Give every beat that shows shape ``name`` its reference back, so the next ``settle`` expands it from the NEW shape.

    ``settle`` copies a shape's points into each figure, so changing only ``lesson["shapes"][name]`` left every beat
    drawn from the old points (found by the 2026-11-07 video run). Returns how many figures were reset.
    """
    if not isinstance(old, dict):
        return 0
    count = 0
    for _, beat in beats_of(lesson):
        fig = beat.get("figure")
        if not isinstance(fig, dict) or fig.get("kind") != "shape":
            continue
        parts = fig["panels"] if isinstance(fig.get("panels"), list) else [fig]
        for part in parts:
            if isinstance(part, dict) and not part.get("use") and part.get("_name") == name:
                _unexpand(part, name, old)
                count += 1
    return count


def declare_shape(lesson: Lesson, name: str, shape: dict) -> None:
    """Declare (or replace) shape ``name`` and re-point the beats that show it at the new shape."""
    shapes = lesson.setdefault("shapes", {})
    old = shapes.get(name)
    if isinstance(old, dict) and old.get("frame") and shape.get("frame") == old.get("frame") \
            and shape.get("points") != old.get("points"):
        shape = {k: v for k, v in shape.items() if k != "frame"}     # the old frame was worked out from the old points
    reexpand_users(lesson, name, old)
    shapes[name] = shape


def _set_shape(lesson: Lesson, edit: dict) -> None:
    """The workbench's ``set_shape`` edit: declare (or replace) a named shape a figure can then ``"use"``."""
    name, shape = str(edit.get("name") or ""), edit.get("shape")
    if not name or not isinstance(shape, dict):
        raise KitError("set_shape needs a name and a shape")
    declare_shape(lesson, name, shape)


_ARROW = {"points": {"A": [0, 0], "B": [4.4, 1.6], "C": [0, 3.2], "D": [1.4, 1.6]}, "polygon": "ABCD", "is": ["concave"]}


def _lesson(*beats: dict) -> Lesson:
    return {"title": "cases", "shapes": {"arrow": _ARROW},
            "chapters": [{"title": "ONE", "learning_goal": "g", "role": "explain", "beats": list(beats)}]}


def _beat(narration: str, figure: dict | None = None) -> dict:
    beat = {"narration": narration, "steps": [{"say": narration.split(".")[0][:30], "show": "x"}]}
    if figure is not None:
        beat["figure"] = figure
    return beat


class GeometryKit:
    name = "geometry"
    figure_kinds = ("shape",)
    subjects = ("maths",)
    classes = SCOPE_CLASSES      # plane geometry is checked the same for every class: 1 to 12 (LESSONFORGE_SCOPE_CLASSES narrows it)
    keywords = ("triangle", "angle", "quadrilateral", "polygon", "parallel", "diagonal", "midpoint", "proof",
                "parallelogram", "rectangle", "rhombus", "trapezium", "kite", "congruent", "side", "vertex")
    legacy = True
    data_key = "shapes"
    generated_by = "geometry pack"
    check_key = "geometry_check"
    builder: Mapping[str, str] = {}              # figures.BUILDERS draws "shape"
    answer_schema = None
    focus_parts: Mapping[str, tuple[str, ...]] = {}     # steps beside a shape take no "focus"
    edit_ops: Mapping[str, EditOp] = {"set_shape": _set_shape}

    @property
    def rules(self) -> str:
        from ..harness import shapes  # noqa: PLC0415 - lazy: shapes imports the geometry maths
        return shapes.SHAPE_RULES

    # -- recognising a geometry lesson (the divergent tests in workbench / writer / scripted, kept verbatim) --

    def uses_figures(self, lesson: Lesson) -> bool:
        """writer.geometry_pass and scripted._finish: some beat draws a ``shape``."""
        return any(figure_kind(b) == "shape" for _, b in beats_of(lesson))

    def uses(self, lesson: Lesson, *, after_edit: bool = False) -> bool:
        if after_edit:                           # workbench.apply_edits: declared shapes, or a figure that says "use"
            return bool(lesson.get("shapes") or any(isinstance(b.get("figure"), dict) and b["figure"].get("use")
                                                    for _, b in beats_of(lesson)))
        return bool(lesson.get("shapes") or self.uses_figures(lesson))      # workbench.faults_of

    # -- figure level --

    def figure_issues(self, figure: Figure) -> Issues:
        """Faults in a figure that already carries its points (an expanded one); the words are not read here."""
        from ..harness import shapes  # noqa: PLC0415
        if not isinstance(figure, dict) or not (figure.get("points") or figure.get("panels")):
            return []
        return shapes.check_figure(figure, "", "the figure")

    def normalise_figure(self, figure: Figure) -> Figure | None:
        return dict(figure) if isinstance(figure, dict) else None

    def numbers(self, figure: Figure) -> set[str]:
        return set()                             # writer.figure_numbers has no branch for "shape"

    def describe(self, figure: Figure) -> str:
        from ..harness import shapes  # noqa: PLC0415
        if not isinstance(figure, dict) or not (figure.get("points") or figure.get("panels")):
            return "a shape"
        return "; ".join(shapes.describe(name or "the shape", model) for name, model, _ in shapes.models(figure))

    # -- lesson level: all of it is harness/shapes.py --

    def settle(self, lesson: Lesson) -> tuple[Lesson, Issues]:
        from ..harness import shapes  # noqa: PLC0415
        return shapes.settle(lesson)

    def unfilled(self, lesson: Lesson) -> bool:
        from ..harness import shapes  # noqa: PLC0415
        return shapes.unfilled(lesson)

    def repair_prompt(self, lesson: Lesson, issues: Issues) -> str:
        from ..harness import shapes  # noqa: PLC0415
        return shapes.repair_prompt(lesson, issues)

    def expected_fault(self, issue: str, lesson: Lesson) -> bool:
        """workbench._expected_fault, verbatim: a wrong quiz option's number is the point of the option."""
        m = STRAY_RE.match(issue)
        if not m:
            return False
        beats = [b for _, b in beats_of(lesson)]
        k = int(m.group(1)) - 1
        quiz = beats[k].get("quiz") if 0 <= k < len(beats) else None
        return isinstance(quiz, dict) and int(m.group(2)) - 1 != int(quiz.get("answer_index", -1))

    def merge_declared(self, lesson: Lesson, answer: dict) -> None:
        """edit._redesign / scripted: shapes a director declared are added; a name the lesson has is never replaced."""
        if isinstance(answer, dict) and isinstance(answer.get("shapes"), dict):
            shapes = lesson.setdefault("shapes", {})
            for name, shape in answer["shapes"].items():
                if isinstance(shape, dict) and str(name) not in shapes:
                    shapes[str(name)] = shape

    def cases(self) -> KitCases:
        arrow = {"kind": "shape", "use": "arrow"}
        expanded = {"kind": "shape", "points": _ARROW["points"], "polygon": "ABCD", "_name": "arrow"}
        good = _lesson(_beat("So ABCD is concave. The angle at D is {angle D} degrees.", {**arrow, "angles": ["D"]}))
        return KitCases(
            good=(good,),
            refused=((_lesson(_beat("The angle at D is 230 degrees.", {**arrow, "angles": ["D"]})), "230 degrees"),
                     (_lesson(_beat("So ABCD is convex.", arrow)), "ABCD is convex"),
                     (_lesson(_beat("Look at it.", {"kind": "shape", "use": "nonsense"})), "no such shape"),
                     (_lesson(_beat("The angle is {angle D} degrees.")), "no shape figure")),
            gaps=(("angle D", expanded, "262"), ("side AD", expanded, "2.1"), ("angle A + angle C", expanded, "58")))


GEOMETRY = register(GeometryKit())
