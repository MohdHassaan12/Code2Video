"""Geometry lessons shared by the Phase 0 safety net and the kit parity tests (a plain module, not a test file).

Each fixture is a lesson as a model writes it: named shapes, ``{use: ...}`` figures, gaps. ``fixtures()`` returns
``name -> lesson``; the safety net pins what ``harness.shapes`` makes of every one, and ``test_kits_geometry_parity``
holds the geometry kit to exactly those answers.
"""
from __future__ import annotations

import copy
import importlib.util
import pathlib
import sys

ARROW = {"points": {"A": [0, 0], "B": [4.4, 1.6], "C": [0, 3.2], "D": [1.4, 1.6]}, "polygon": "ABCD", "is": ["concave"]}
BOX = {"points": {"A": [0, 0], "B": [4, 0.3], "C": [4.6, 3.2], "D": [0.4, 2.8]}, "polygon": "ABCD", "is": ["convex"]}
PARA = {"points": {"A": [0, 0], "B": [4, 0], "C": [5, 3], "D": [1, 2.9]}, "polygon": "ABCD", "is": ["parallelogram"]}

QUADRILATERALS = pathlib.Path(__file__).resolve().parents[2] / "examples" / "quadrilaterals"
HAND_MADE_UNITS = (1, 2, 4, 6, 7, 8)


def lesson(beats, table=None):
    return {"title": "t", "shapes": table if table is not None else {"arrow": copy.deepcopy(ARROW), "box": copy.deepcopy(BOX)},
            "chapters": [{"title": "ONE", "learning_goal": "g", "role": "explain", "beats": beats}]}


def beat(narration, figure, steps=None, quiz=None):
    out = {"narration": narration, "figure": figure,
           "steps": steps if steps is not None else [{"say": narration.split(".")[0][:30], "show": "x"}]}
    if quiz:
        out["quiz"] = quiz
    return out


def _hand_made(unit: int) -> dict:
    here = str(QUADRILATERALS)
    sys.path.insert(0, here)
    try:
        spec = importlib.util.spec_from_file_location(f"kit_fixture_unit{unit}", QUADRILATERALS / f"unit{unit}.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return copy.deepcopy(mod.L)
    finally:
        sys.path.remove(here)


def fixtures() -> dict[str, dict]:
    arrow = {"kind": "shape", "use": "arrow"}
    out: dict[str, dict] = {
        "gaps_fill_and_add_up": lesson([beat(
            "The angle at D is {angle D} degrees. A, B and C add to {angle A + angle B + angle C}.",
            {"kind": "shape", "use": "arrow", "angles": ["D"]},
            steps=[{"say": "The angle at D", "show": "∠D = {angle D}°"}])]),
        "typed_angle": lesson([beat("The angle at D is 230 degrees.", {**arrow, "angles": ["D"]})]),
        "typed_angle_in_words": lesson([beat("The angle at D is two hundred and thirty degrees.", {**arrow, "angles": ["D"]})]),
        "claim_denied": lesson([beat("So ABCD is convex.", arrow)]),
        "claim_true": lesson([beat("So ABCD is concave.", arrow)]),
        "claim_negated": lesson([beat("It is not convex.", arrow)]),
        "shape_not_what_is_needed": lesson([], {"para": {**PARA, "points": {"A": [0, 0], "B": [4, 0], "C": [5, 3], "D": [1, 2.9]},
                                                         "is": ["rectangle"]}}),
        "moving_corner_on_segment": lesson([beat(
            "Before the line it is convex. On the line it has collapsed. Past it, concave.",
            {"kind": "shape", "use": "box", "move": {"D": [[1.5, 2.2], "on AC", [3.0, 1.4]]}, "verdict": True})]),
        "moving_corner_misses": lesson([beat(
            "On the line it has collapsed.",
            {"kind": "shape", "use": "box", "move": {"D": [[1.5, 2.2], [2.4, 1.6], [3.0, 1.4]]}})]),
        "options_equal_after_filling": lesson([beat("What is angle D?", arrow, quiz={
            "question": "What is angle D?", "options": ["{angle D}°", "{360 - angle A - angle B - angle C}°"],
            "answer_index": 0, "why": ["a", "b"]})]),
        "deliberate_wrong_option": lesson([beat("What is angle D?", arrow, quiz={
            "question": "What is angle D?", "options": ["{angle D}°", "100°", "{angle A}°"],
            "answer_index": 0, "why": ["right", "wrong", "wrong"]})]),
        "wrong_answer_option": lesson([beat("What is angle D?", arrow, quiz={
            "question": "What is angle D?", "options": ["100°", "{angle D}°"],
            "answer_index": 0, "why": ["x", "y"]})]),
        "gap_on_beat_without_shape": lesson([beat("The angle is {angle D} degrees.", None)]),
        "gap_cannot_be_filled": lesson([beat("The weight is {mass of D}.", arrow)]),
        "unknown_shape_name": lesson([beat("Look at it.", {"kind": "shape", "use": "nonsense"})]),
        "use_without_kind": lesson([beat("Look at it.", {"use": "arrow"})]),
        "two_panels": lesson([beat("Two shapes. The angle at D is {arrow: angle D} degrees.", {
            "kind": "shape", "panels": [{"use": "box", "caption": "convex"}, {"use": "arrow", "caption": "concave", "angles": ["D"]}]})]),
        "no_shape_at_all": {"title": "t", "chapters": [{"title": "ONE", "learning_goal": "g", "role": "explain", "beats": [
            beat("Nothing is drawn here. Twelve degrees is a number.", None)]}]},
    }
    for unit in HAND_MADE_UNITS:
        out[f"hand_made_unit{unit}"] = _hand_made(unit)
    return out
