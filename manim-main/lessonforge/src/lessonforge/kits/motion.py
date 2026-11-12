"""The motion kit: straight-line motion at constant acceleration, drawn as a speed-time graph. The proof kit.

The whole chain a kit must supply, in one file:

* MODEL    ``longform/motion_math.py`` (pure): three of start speed, end speed, acceleration, duration give the
           fourth, ``v(t) = u + a t``, displacement, distance, stop time and what the speed does.
* FIGURE   ``{"kind": "motion", "start_speed": 0, "acceleration": 2, "duration": 6, "marks": [3, 6]}`` is drawn by the
           existing graph builder, fed only from the model (``longform/kit_figures.py``, the Manim side).
* GAPS     ``{speed at 3}``, ``{distance at duration}``, ``{speed at 3 + 2}`` are filled by code.
* CLAIMS   "speeds up", "slows down", "constant speed", "comes to rest", "starts from rest", "turns back" are checked
           against the model; a speed, acceleration, time or distance with a unit that the picture does not show is
           a fault.
* RULES    ``MOTION_RULES`` is the writer's section for the figure, shipped only through ``brief["kits"]`` or the
           workbench addendum, never inside the built-in prompts.

Nothing here imports manim or numpy.
"""
from __future__ import annotations

import re
from typing import Mapping

from ..longform import motion_math as M
from .base import GAP, KitBase, KitCases, KitError, Lesson, Whole, arithmetic
from .registry import register

MOTION_RULES = """    {"kind":"motion","start_speed":0,"acceleration":2,"duration":6,"marks":[3,6]}
      Straight-line motion at constant acceleration, drawn as a speed-time graph (SI units: m/s, m/s^2, s). Give
      any THREE of start_speed, end_speed, acceleration, duration; code works out the fourth. "marks" are the times
      (seconds, at most four) you will talk about; code labels the speed at each. A negative acceleration slows a
      body that moves forward. Never give all four unless they agree.
      Never type a speed, acceleration, distance or time that you worked out: write a gap and code fills it from
      the model: {speed at 3}, {distance at 6}, {distance at duration}, {acceleration}, {start speed}, {end speed},
      {duration}, {stop time}; arithmetic works on them: {speed at 3 + 2}. The time in a gap must be a mark (or 0, or
      duration). A number with a unit that is not a mark, an input or a gap is a fault; a time you speak is a mark.
      Say only what the numbers allow. "speeds up" needs the speed to rise; "slows down" or "brakes" needs it to
      fall; "constant speed" needs acceleration 0; "comes to rest" or "stops" needs the speed to reach 0 within the
      run; "starts from rest" needs start_speed 0; "turns back" needs the speed to change sign.
      Give a NEW motion figure when the numbers change. Use the SAME figure on every beat that keeps discussing it.
      A lesson may mix subjects: use a motion figure only on the beats about this motion; a beat of another subject
      keeps the figure of its own kit, and its numbers are that kit's business, not these.
      A gap fills a number, never its unit: write the unit yourself and match it to the gap: {acceleration} is in m/s^2
      (m/s squared), speeds in m/s, {duration} and times in s, {distance at 6} in m.
"""

#: Parts of the graph a step's "focus" may name (the graph builder's own parts).
_PARTS = ("axes", "x_label", "y_label", "curve0", "curve0_label") + tuple(
    p for i in range(4) for p in (f"point{i}", f"point{i}_label"))

_NEGATION = re.compile(r"\b(?:not|never|no longer|isn't|isnt|doesn't|doesnt|don't|dont|didn't|won't|cannot|can't|without|"
                       r"nor|neither|unless|if|would|could|might|may|whether|or)\b", re.I)
_CLAIMS: tuple[tuple[str, "re.Pattern[str]", str], ...] = (
    ("speeds up", re.compile(r"\b(?:speeds?\s+up|speeding\s+up|sped\s+up|accelerat(?:es|ing|ed)|gains?\s+speed)\b", re.I), "speeding up"),
    ("slows down", re.compile(r"\b(?:slows?\s+down|slowing\s+down|slowed\s+down|decelerat(?:es|ing|ed)|brak(?:es|ing)|retards?)\b", re.I), "slowing down"),
    ("constant speed", re.compile(r"\b(?:constant|steady|uniform)\s+(?:speed|velocity)\b", re.I), "steady"),
    ("comes to rest", re.compile(r"\b(?:com(?:es|ing)|came)\s+to\s+(?:a\s+)?(?:rest|stop|halt)\b|\bstop(?:s|ped)?\b(?!\s+(?:time|watch|sign|distance))|\bhalts?\b", re.I), "rest"),
    ("starts from rest", re.compile(r"\b(?:start(?:s|ed)?|begin(?:s)?|set(?:s)?\s+off|released|leaves?)\s+(?:from|at)\s+rest\b", re.I), "from rest"),
    ("turns back", re.compile(r"\b(?:turn(?:s|ed)?\s+(?:back|around)|revers(?:es|ed|ing)|changes?\s+direction|com(?:es|ing)\s+back|moves?\s+back)\b", re.I), "reverses"),
)
# A number, then its unit. Acceleration is tried before speed, speed before distance (m/s^2, m/s, m).
_QUANTITY = re.compile(
    r"(?<![\w.])(?P<n>\d+(?:\.\d+)?)\s*(?:"
    r"(?P<acc>m\s*/\s*s\s*(?:\^\s*2|2|²|squared\b)|m\s*s\s*\^\s*-\s*2|met(?:re|er)s?\s+per\s+second\s+squared)"
    r"|(?P<speed>m\s*/\s*s\b|met(?:re|er)s?\s+per\s+second\b)"
    r"|(?P<time>seconds?\b|secs?\b|s\b(?![/^²\w]))"
    r"|(?P<dist>met(?:re|er)s?\b|m\b(?!\s*/))"
    r")", re.I)
_TOL = 0.005 + 1e-9
#: What a gap's number is, by the words in the gap, and the unit it is written with (for the "wrong unit" finding).
_GAP_KIND = (("acc", re.compile(r"\bacceleration\b", re.I)), ("speed", re.compile(r"\b(?:speed|velocity)\b", re.I)),
             ("time", re.compile(r"\b(?:duration|stop\s+time)\b", re.I)), ("dist", re.compile(r"\bdistance\b", re.I)))
_GAP_NAME = {"acc": "{acceleration}", "speed": "a speed gap ({speed at T}, {start speed}, {end speed})",
             "time": "a time gap ({duration}, {stop time})", "dist": "{distance at T}"}
_UNIT_WORDS = {"acc": "m/s squared (or metres per second squared)", "speed": "m/s (or metres per second)",
               "time": "s (or seconds)", "dist": "m (or metres)"}


def _gap_kind(expr: str) -> str | None:
    """"acceleration" -> "acc"; "speed at 3 + 2" -> "speed"; a gap mixing quantities or an unknown one -> None."""
    found = {kind for kind, rx in _GAP_KIND if rx.search(re.sub(r"\bat\s+duration\b", "at T", expr or ""))}
    return found.pop() if len(found) == 1 else None
_TERM = re.compile(r"\b(?P<fn>speed|distance)\s+at\s+(?P<t>duration|\d+(?:\.\d+)?)\b"
                   r"|\b(?P<one>acceleration|start\s+speed|end\s+speed|duration|stop\s+time)\b", re.I)
_CAN_ONLY = ("can only hold speed at T, distance at T, acceleration, start speed, end speed, duration, stop time, "
             "numbers and + - * / (T is a number of seconds or duration)")


def _nice(value: float) -> str:
    """The text a gap prints: at most two decimals, no trailing zeros, never ``-0``."""
    v = round(value, 2) + 0.0
    return f"{v:g}"


def _sentences(text: str) -> list[str]:
    return [s for s in re.split(r"(?<=[.!?])\s+", text or "") if s]


def _close(x: float, pool) -> bool:
    return any(abs(x - y) <= _TOL for y in pool)


class MotionKit(KitBase):
    name = "motion"
    figure_kinds = ("motion",)
    subjects = ("physics",)
    classes = (7, 8, 9)
    keywords = ("speed", "velocity", "acceleration", "distance", "displacement", "uniform", "graph", "motion",
                "slows down", "speeds up", "brakes", "constant speed")
    rules = MOTION_RULES
    builder: Mapping[str, str] = {"motion": "lessonforge.longform.kit_figures:motion"}
    focus_parts: Mapping[str, tuple[str, ...]] = {"motion": _PARTS}
    mcp_note = ("Motion figures are drawn from start_speed, acceleration and duration (any three of those and end_speed): "
                "write a gap such as {speed at 3} and code fills it, on a beat whose figure is a motion figure.")

    # -- the model --

    def solve(self, figure):
        try:
            return M.solve(figure)
        except M.MotionError as exc:
            raise KitError(str(exc)) from exc

    def normalise_figure(self, figure):
        if not isinstance(figure, dict):
            return None
        try:
            model = self.solve(figure)
        except KitError:
            return None
        out = {"kind": "motion", **{k: figure[k] for k in M.INPUT_KEYS if figure.get(k) is not None}}
        if model.marks:
            out["marks"] = list(model.marks)
        return out

    def describe(self, figure):
        try:
            m = self.solve(figure)
        except KitError as exc:
            return str(exc)
        bits = [f"starts at {m.u:g} m/s, ends at {m.end_speed:g} m/s after {m.T:g} s (acceleration {m.a:g} m/s^2)",
                f"displacement {_nice(m.s(m.T))} m, distance {_nice(m.distance(m.T))} m"]
        stop = m.stop_time()
        bits.append(f"comes to rest at {_nice(stop)} s" if stop is not None else "does not come to rest")
        if m.marks:
            bits.append("marked: " + ", ".join(f"{t:g} s -> {_nice(m.v(t))} m/s" for t in m.marks))
        return "; ".join(bits)

    # -- gaps --

    def fill_gap(self, expr, model):
        def at(raw: str) -> float:
            t = model.T if raw.lower() == "duration" else float(raw)
            if not -M.EPS <= t <= model.T + M.EPS:
                raise KitError(f"gap {{{expr}}}: {t:g} s is outside the run, which lasts 0 to {model.T:g} s")
            if not _close(t, {0.0, model.T, *model.marks}):
                # a value the graph does not label would read as a typed number the next time the lesson is checked
                raise KitError(f"gap {{{expr}}}: {t:g} s is not a time the figure marks; add {t:g} to the figure's "
                               f"\"marks\" (at most {M.MAX_MARKS}) so the graph shows it, or use duration")
            return min(max(t, 0.0), model.T)

        def term(match) -> str:
            if match.group("fn"):
                t = at(match.group("t"))
                value = model.v(t) if match.group("fn").lower() == "speed" else model.distance(t)
            else:
                one = re.sub(r"\s+", " ", match.group("one").lower())
                if one == "stop time":
                    value = model.stop_time()
                    if value is None:
                        raise KitError(f"gap {{{expr}}}: this motion does not come to rest during its {model.T:g} s")
                else:
                    value = {"acceleration": model.a, "start speed": model.u, "end speed": model.end_speed,
                             "duration": model.T}[one]
            return f"({value:.9f})"
        body = _TERM.sub(term, expr)
        if re.search(r"[A-Za-z]", body):
            raise KitError(f"gap {{{expr}}} {_CAN_ONLY}")
        try:
            value = arithmetic(body)
        except ZeroDivisionError:
            raise KitError(f"gap {{{expr}}} divides by zero") from None
        except ValueError as exc:
            raise KitError(f"gap {{{expr}}} is not arithmetic code can work out ({exc})") from exc
        value = round(value, 2) + 0.0
        return _nice(value), value

    # -- claims --

    def claims(self, text, model):
        issues: list[str] = []
        trends, stop = model.trends(), model.stop_time()
        for sentence in _sentences(GAP.sub(" ", text or "")):          # a gap that failed to fill is not a claim
            if sentence.rstrip().endswith("?"):
                continue                                  # a question asks; it claims nothing
            for label, pattern, needs in _CLAIMS:
                for m in pattern.finditer(sentence):
                    before = sentence[:m.start()]
                    if _NEGATION.search(before[max(0, len(before) - 40):]):
                        continue
                    if needs == "steady":
                        ok = abs(model.a) < M.EPS
                    elif needs == "rest":
                        ok = stop is not None
                    elif needs == "from rest":
                        ok = abs(model.u) < M.EPS
                    else:
                        ok = needs in trends
                    if not ok:
                        issues.append(f"the words say “{m.group(0)}”, but the picture is: {self.summary(model)}")
        return list(dict.fromkeys(issues))

    @staticmethod
    def summary(model) -> str:
        stop = model.stop_time()
        return (f"{model.phase()}, from {model.u:g} m/s to {model.end_speed:g} m/s in {model.T:g} s "
                f"(acceleration {model.a:g} m/s^2" + (f", at rest at {_nice(stop)} s)" if stop is not None else ", never at rest)"))

    # -- typed numbers --

    def stray_numbers(self, text, model, used):
        marks = model.marks
        stop = model.stop_time()
        allowed = {
            "speed": {model.u, model.end_speed, *(model.v(t) for t in marks)},
            "acc": {model.a},
            "time": {model.T, 0.0, *marks, *([stop] if stop is not None else [])},
            "dist": {model.s(model.T), model.distance(model.T), *(model.s(t) for t in marks),
                     *(model.distance(t) for t in marks)},
        }
        for kind, pool in allowed.items():            # a change between two shown values is shown as well (v at 6 - v at 3)
            pool |= {abs(x - y) for x in pool for y in pool}
        filled = {abs(v) for v in used}
        out: list[str] = []
        for m in _QUANTITY.finditer(GAP.sub(" ", text or "")):
            n = float(m.group("n"))
            kind = next(k for k in ("acc", "speed", "time", "dist") if m.group(k))
            if n == 0 or _close(n, {abs(x) for x in allowed[kind]}):
                continue
            if _close(n, filled):
                # a gap made this number. Fine when the unit fits what the gap was; else the UNIT is the fault, not the number
                kinds = {_gap_kind(getattr(v, "expr", "")) for v in used if abs(abs(v) - n) <= _TOL}
                if not kinds or None in kinds or kind in kinds:
                    continue
                gap_kind = sorted(kinds)[0]
                said = m.group(0)[len(m.group("n")):].strip().replace("{", "{{").replace("}", "}}")
                what = Whole("{ref}{where}: the unit after " + _GAP_NAME[gap_kind].replace("{", "{{").replace("}", "}}")
                             + " should be " + _UNIT_WORDS[gap_kind] + f", not “{said}”")
            else:
                unit = {"acc": "m/s^2", "speed": "m/s", "time": "s", "dist": "m"}[kind]
                what = f"{n:g} {unit}"
            if what not in out:
                out.append(what)
        return out

    # -- conformance --

    def cases(self) -> KitCases:
        speeding = {"kind": "motion", "start_speed": 0, "acceleration": 2, "duration": 6, "marks": [3, 6]}
        braking = {"kind": "motion", "start_speed": 10, "acceleration": -2, "duration": 4}
        steady = {"kind": "motion", "start_speed": 5, "acceleration": 0, "duration": 6}
        reversing = {"kind": "motion", "start_speed": 10, "acceleration": -2, "duration": 8}
        good = _lesson(
            _beat("The car starts from rest and speeds up. At 3 s its speed is {speed at 3} m/s, and after "
                  "{duration} s it has gone {distance at duration} m.", speeding,
                  quiz={"question": "What is the speed at 3 s?", "options": ["{speed at 3} m/s", "{speed at 3 + 2} m/s", "{speed at 3 - 2} m/s"],
                        "answer_index": 0, "why": ["right", "too fast", "too slow"]}),
            _beat("Now the driver brakes. The car slows down and its acceleration is {acceleration} m/s^2.", braking),
            _beat("It slows down, comes to rest after {stop time} s and then turns back.", reversing))
        return KitCases(
            good=(good,),
            refused=((_lesson(_beat("The car speeds up.", braking)), "speeds up"),
                     (_lesson(_beat("The car slows down.", speeding)), "slows down"),
                     (_lesson(_beat("It moves at a constant speed.", speeding)), "constant speed"),
                     (_lesson(_beat("The car comes to rest.", braking)), "comes to rest"),
                     (_lesson(_beat("The car starts from rest.", braking)), "starts from rest"),
                     (_lesson(_beat("The car turns back.", braking)), "turns back"),
                     (_lesson(_beat("At 3 s the speed is 20 m/s.", speeding)), "20 m/s"),
                     (_lesson(_beat("It speeds up.", {**speeding, "end_speed": 15})), "you gave"),
                     (_lesson(_beat("Its speed is {speed at 3} m/s.", None)), "no motion figure"),
                     (_lesson(_beat("It stops after {stop time} s.", speeding)), "does not come to rest")),
            gaps=(("speed at 3", speeding, "6"), ("distance at duration", speeding, "36"),
                  ("speed at 3 + 2", speeding, "8"), ("acceleration", braking, "-2"), ("start speed", braking, "10"),
                  ("end speed", braking, "2"), ("duration", steady, "6"), ("stop time", reversing, "5"),
                  ("distance at 8", reversing, "34"), ("speed at duration * 2", speeding, "24")))


def _beat(narration: str, figure: dict | None = None, quiz: dict | None = None) -> dict:
    beat = {"narration": narration, "steps": [{"say": narration.split(".")[0][:30], "show": "x"}]}
    if figure is not None:
        beat["figure"] = figure
    if quiz:
        beat["quiz"] = quiz
    return beat


def _lesson(*beats: dict) -> Lesson:
    return {"title": "cases", "chapters": [{"title": "ONE", "learning_goal": "g", "role": "explain", "beats": list(beats)}]}


MOTION = register(MotionKit())
