"""A quiz's answer must not be on the screen, or said, before the learner has been asked (video-quality plan S4).

Two filmed lessons asked a question with its answer already in view: a speed-time graph labelled every mark with its value
(``2 s, 8 m/s``) on the beat that asked "what is the speed after 2 seconds?" (19.4 s on screen), and a geometry quiz asked
for an angle the voice had said 15 s before. Two jobs, both pure (no Manim, no model, no network):

* :func:`hold` (a writer pass, ``writer.quiz_leaks``): on a beat that asks a question about a ``motion`` figure, the marks
  whose label shows the answer are listed in the figure's ``hold_marks``; ``longform.kit_figures.motion`` leaves those
  points and their labels off the graph, so the next beat (the figure without ``hold_marks``) is where they appear. The
  model is untouched (the kit still checks every number against all the marks); only the drawing waits. Idempotent.
* :func:`find` (a lint): the answer's number in the narration, a step's words or a figure label of an EARLIER beat, or in
  the question beat's own words (apart from the question and its options) is a finding. Advisory in a lesson's log;
  a hard fault only in ``kit_pipeline.run``. A quiz that sets ``"allow_seen": true`` says the earlier mention was deliberate.

The number-and-unit rules are deliberately small: an answer with a unit ("8 m/s", "120 degrees") is looked for with the same
unit family; a bare small whole number ("2") is not looked for at all (it is in every lesson).
"""
from __future__ import annotations

import re

_NUMBER = re.compile(r"(?<![\w.])-?\d+(?:\.\d+)?")
#: unit family -> the words and symbols it is written with (lower case, after the number)
UNITS = {
    "speed": ("m/s", "metres per second", "meters per second", "metre per second", "meter per second", "mps"),
    "accel": ("m/s²", "m/s^2", "m/s2", "metres per second squared", "meters per second squared", "m/s squared"),
    "time": ("s", "sec", "secs", "second", "seconds"),
    "force": ("n", "newton", "newtons"),
    "angle": ("°", "degree", "degrees", "deg"),
    "length": ("m", "metre", "metres", "meter", "meters", "cm", "km"),
    "mass": ("kg", "kilogram", "kilograms", "g", "gram", "grams"),
}
_UNIT_AFTER = re.compile(r"^\s*(?P<u>m\s*/\s*s\s*(?:\^\s*2|2|²|squared)|m\s*/\s*s|metres?\s+per\s+second(?:\s+squared)?|"
                         r"meters?\s+per\s+second(?:\s+squared)?|°|degrees?|deg|newtons?|n|kilograms?|kg|grams?|g|seconds?|secs?|s|"
                         r"metres?|meters?|cm|km|m)\b", re.I)


def _family(unit: str) -> str | None:
    unit = re.sub(r"\s+", " ", unit.lower().replace(" /", "/").replace("/ ", "/")).strip()
    for family in ("accel", "speed", "angle", "force", "time", "mass", "length"):
        if unit in UNITS[family]:
            return family
    return None


def numbers_with_units(text: str) -> list[tuple[float, str | None]]:
    """[(value, unit family or None)] for every number in ``text`` written as digits."""
    out = []
    text = str(text or "")
    for m in _NUMBER.finditer(text):
        after = _UNIT_AFTER.match(text[m.end():])
        out.append((float(m.group(0)), _family(after.group("u")) if after else None))
    return out


def _beats(lesson: dict) -> list[dict]:
    return [b for c in lesson.get("chapters") or [] for b in c.get("beats") or [] if isinstance(b, dict)]


def answer_of(beat: dict) -> tuple[str, list[tuple[float, str | None]]]:
    """The text of the correct option of a beat's quiz and the numbers (with unit families) in it; ``("", [])`` when the
    beat asks nothing, the answer is not a numbered one, or a gap in it is not filled yet."""
    quiz = beat.get("quiz")
    if not isinstance(quiz, dict):
        return "", []
    options, index = quiz.get("options"), quiz.get("answer_index")
    if not isinstance(options, list) or not isinstance(index, int) or not 0 <= index < len(options):
        return "", []
    text = str(options[index])
    if "{" in text:
        return text, []                    # a gap not filled yet: nothing to compare
    return text, numbers_with_units(text)


def _given(beat: dict) -> set[float]:
    """Numbers the question itself gives ("after 2 seconds"): they are not the answer."""
    return {v for v, _ in numbers_with_units((beat.get("quiz") or {}).get("question", ""))}


def _worth_looking_for(value: float, unit: str | None) -> bool:
    """A bare 0, 1 or 2 (no unit) is in every lesson; everything else with a unit, and any bigger or fractional number, is not."""
    if unit is not None:
        return True
    return abs(value) >= 10 or abs(value - round(value)) > 1e-9


def _same(a: float, b: float) -> bool:
    return abs(a - b) <= 0.005 + 1e-9


def _mentions(text: str, wanted: list[tuple[float, str | None]]) -> list[float]:
    """The wanted values that ``text`` says: as digits (with the answer's unit family when the text gives one) or in words."""
    from .annotate import spoken_numbers   # noqa: PLC0415 - annotate imports the writer
    typed = numbers_with_units(text)
    in_words = {float(n) for n in spoken_numbers(text)} - {v for v, _ in typed}
    hits = []
    for value, unit in wanted:
        by_digits = any(_same(v, value) and (unit is None or u is None or u == unit) for v, u in typed)
        if by_digits or any(_same(w, value) for w in in_words):
            hits.append(value)
    return hits


def _motion_marks(figure: dict):
    """(model, [(t, v)]) of a motion figure's marks, or (None, [])."""
    from ..longform import motion_math  # noqa: PLC0415 - pure module
    try:
        model = motion_math.solve(figure)
    except Exception:  # noqa: BLE001 - a figure the kit refuses is its own fault, reported elsewhere
        return None, []
    return model, [(t, model.v(t)) for t in model.marks]


def leaking_marks(beat: dict) -> list[float]:
    """The times of a motion figure's marks whose label ("t s, v m/s") shows the answer of the beat's quiz."""
    figure = beat.get("figure")
    if not (isinstance(figure, dict) and figure.get("kind") == "motion"):
        return []
    given = _given(beat)
    answers = [(v, u) for v, u in answer_of(beat)[1] if _worth_looking_for(v, u) and not any(_same(v, g) for g in given)]
    model, marks = _motion_marks(figure) if answers else (None, [])
    if model is None:
        return []
    out = []
    for t, v in marks:
        for value, unit in answers:
            if (unit in (None, "speed") and _same(v, value)) or (unit == "time" and _same(t, value)):
                out.append(t)
                break
    return sorted(set(out))


def leaking_angles(beat: dict) -> list[int]:
    """Indexes of the ``angles`` of a ``shape`` figure whose arc would write the quiz's answer (whole degrees, as the figure
    rounds them) and that do not already say ``"value": false``. The figure must carry its own points."""
    figure = beat.get("figure")
    if not (isinstance(figure, dict) and figure.get("kind") == "shape" and isinstance(figure.get("points"), dict)
            and figure.get("angle_values", True) and isinstance(figure.get("angles"), list)):
        return []
    given = _given(beat)
    answers = [v for v, u in answer_of(beat)[1] if u in (None, "angle") and _worth_looking_for(v, u)
               and not any(_same(v, g) for g in given)]
    if not answers:
        return []
    from ..longform import geometry as G  # noqa: PLC0415 - pure module
    try:
        model = G.Model(figure)
        inner = model.interior()
        rounded = G.round_to_total(inner, 180.0 * (len(inner) - 2)) if inner else {}
        out = []
        for k, item in enumerate(figure["angles"]):
            a = model.angle(item)
            if not a or (isinstance(item, dict) and item.get("value") is False):
                continue
            if isinstance(item, dict) and isinstance(item.get("value"), str):
                continue                           # the author wrote this label
            key = a["at"] if not (isinstance(item, dict) and item.get("from")) else f"{a['from']}{a['at']}{a['to']}"
            deg = rounded.get(a["at"], round(a["value"])) if key == a["at"] else round(a["value"])
            if any(_same(deg, v) for v in answers):
                out.append(k)
        return out
    except Exception:  # noqa: BLE001 - a shape the geometry model refuses is its own fault
        return []


def hold(lesson: dict, log=print) -> dict:
    """Keep a quiz's answer off the picture of the beat that asks it (in place).

    A ``motion`` figure lists the marks that show it in ``hold_marks``; a ``shape`` figure writes ``"value": false`` on the
    angle whose arc would show it (the arc stays, its number does not). Idempotent: a second run finds nothing new. A beat
    with no quiz, any other figure kind, a figure that already carries ``hold_marks`` and an author's own ``value`` are
    untouched."""
    held = []
    for beat in _beats(lesson):
        arcs = leaking_angles(beat)
        if arcs:
            figure = beat["figure"]
            angles = list(figure["angles"])
            for k in arcs:
                item = angles[k]
                angles[k] = {**(item if isinstance(item, dict) else {"at": item}), "value": False}
            beat["figure"] = {**figure, "angles": angles}
            named = [angles[k]["from"] + angles[k]["at"] + angles[k]["to"] if angles[k].get("from") else angles[k]["at"] for k in arcs]
            held.append(f"beat {beat.get('id', '?')} (angle {', '.join(named)})")
            continue
        marks = leaking_marks(beat)
        if not marks:
            continue
        figure = beat["figure"]
        if figure.get("hold_marks") == marks:
            continue
        if figure.get("hold_marks"):
            continue                            # an author's own list is kept
        beat["figure"] = {**figure, "hold_marks": marks}
        held.append(f"beat {beat.get('id', '?')} (marks {', '.join(f'{t:g} s' for t in marks)})")
    if held:
        log(f"[writer] a quiz's answer waits off the picture until the next beat: {'; '.join(held)}")
    return lesson


def _figure_labels(beat: dict) -> str:
    """The words a motion figure writes on its graph, as one string: what a viewer reads there."""
    figure = beat.get("figure")
    if not (isinstance(figure, dict) and figure.get("kind") == "motion"):
        return ""
    model, marks = _motion_marks(figure)
    if model is None:
        return ""
    held = {float(t) for t in figure.get("hold_marks") or []}
    return " ".join(f"{t:g} s, {v:g} m/s" for t, v in marks if not any(_same(t, h) for h in held))


def _screen(beat: dict) -> str:
    return " ".join(str(s.get("show", "")) for s in beat.get("steps") or [] if isinstance(s, dict))


def find(lesson: dict, assume_hold: bool = True) -> list[dict]:
    """Findings ``{"beat", "number", "where", "kind", "fix"}`` for every quiz whose answer is in view before it is asked.

    ``assume_hold`` counts a motion mark on the question's own beat as handled (``hold`` does it when the lesson is made);
    False reports it too. ``kind`` is ``narration``, ``screen`` (a step's words), ``figure`` (a label in a picture) or
    ``own``: the question beat's own narration or screen."""
    beats = _beats(lesson)
    out = []
    for at, beat in enumerate(beats):
        text, answers = answer_of(beat)
        quiz = beat.get("quiz")
        if not answers or not isinstance(quiz, dict) or quiz.get("allow_seen"):
            continue
        given = _given(beat)
        wanted = [(v, u) for v, u in answers if _worth_looking_for(v, u) and not any(_same(v, g) for g in given)]
        if not wanted:
            continue
        seen: set[tuple] = set()

        def report(where: str, kind: str, hits: list[float], fix: str):
            for value in hits:
                key = (value, where)
                if key not in seen:
                    seen.add(key)
                    out.append({"beat": str(beat.get("id", at + 1)), "number": f"{value:g}", "where": where, "kind": kind, "fix": fix})

        for earlier in beats[:at]:
            name = f"beat {earlier.get('id', '?')}"
            report(f"the narration of {name}", "narration", _mentions(earlier.get("narration", ""), wanted),
                   "say something else there, or ask about a number that has not been said")
            report(f"the words on screen in {name}", "screen", _mentions(_screen(earlier), wanted),
                   "take it off the screen before the question")
            report(f"a label in the picture of {name}", "figure", _mentions(_figure_labels(earlier), wanted),
                   "hold the mark back until the answer")
        own = f"beat {beat.get('id', '?')}"
        asked = " ".join(x for x in re.split(r"(?<=[.!?])\s+", str(beat.get("narration", "")).strip()) if "?" not in x)
        report(f"the narration of {own}, before its question", "own", _mentions(asked, wanted), "ask first, then say it")
        report(f"the words on screen in {own}", "own", _mentions(_screen(beat), wanted), "take it off the screen before the question")
        if not assume_hold:
            report(f"a label in the picture of {own}", "figure", _mentions(_figure_labels(beat), wanted), "hold the mark back until the answer")
    return out


def describe(finding: dict) -> str:
    return (f"beat {finding['beat']}: the answer {finding['number']} is already in view in {finding['where']}"
            f" ({finding['fix']})")
