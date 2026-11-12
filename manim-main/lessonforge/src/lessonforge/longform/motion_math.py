"""Straight-line motion at constant acceleration, worked out by code (stdlib only: no manim, no numpy).

The model behind the ``motion`` subject kit (``lessonforge.kits.motion``). A figure gives THREE of start speed ``u``,
end speed ``v``, acceleration ``a`` and duration ``T`` (SI units: m/s, m/s^2, s); code works out the fourth and every
number a lesson may say: ``v(t) = u + a t``, displacement ``s(t) = u t + a t^2 / 2``, the distance travelled (which
differs from the displacement after a reversal), the moment the body stops, and what the speed does over a run.

Everything here is a pure function of the figure's numbers. ``MotionError`` is a ``ValueError`` whose message is plain
words a writer model can act on; the kit turns it into a ``KitError``.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Mapping

INPUT_KEYS = ("start_speed", "end_speed", "acceleration", "duration")
MAX_DURATION = 600.0          # seconds
MAX_VALUE = 1e4               # any speed, acceleration or time
MAX_MARKS = 4                 # the graph labels at most four points
EPS = 1e-9

SPEEDING_UP, SLOWING_DOWN, STEADY, REVERSES = "speeding up", "slowing down", "steady", "reverses"
_GIVE_THREE = "give THREE of start_speed, end_speed, acceleration, duration (SI units: m/s, m/s^2, s)"


class MotionError(ValueError):
    """Numbers that are not a coherent straight-line motion; the message says what to change."""


def _num(value: Any, name: str) -> float:
    if isinstance(value, bool) or value is None:
        raise MotionError(f"{name} must be a number")
    if isinstance(value, str):
        try:
            value = float(value.strip())
        except ValueError:
            raise MotionError(f"{name} must be a plain number, not {value!r}") from None
    if not isinstance(value, (int, float)):
        raise MotionError(f"{name} must be a number")
    value = float(value)
    if not math.isfinite(value):
        raise MotionError(f"{name} must be a finite number")
    if abs(value) > MAX_VALUE:
        raise MotionError(f"{name} {value:g} is out of range (at most {MAX_VALUE:g} either way)")
    return value


def _clean(x: float) -> float:
    """-0.0 and float dust (1e-15) read as 0."""
    return 0.0 if abs(x) < 1e-12 else x


@dataclass(frozen=True)
class Motion:
    """One run: start speed ``u``, acceleration ``a``, duration ``T``, and the times a figure labels (``marks``)."""

    u: float
    a: float
    T: float
    marks: tuple[float, ...] = ()
    notes: tuple[str, ...] = ()

    # -- the physics --

    @property
    def end_speed(self) -> float:
        return self.v(self.T)

    def v(self, t: float) -> float:
        """Velocity at time ``t`` (negative once the body moves back)."""
        return _clean(self.u + self.a * t)

    def s(self, t: float) -> float:
        """Displacement from the start at time ``t``."""
        return _clean(self.u * t + 0.5 * self.a * t * t)

    def stop_time(self) -> float | None:
        """When the body comes to rest, only if it was slowing (``u * a < 0``) and that moment is within the run."""
        if self.u * self.a >= 0:
            return None
        t = -self.u / self.a
        return min(t, self.T) if t <= self.T + EPS else None

    def distance(self, t: float) -> float:
        """Path length by time ``t``: equals ``|s|`` unless the body turned back first."""
        stop = self.stop_time()
        if stop is not None and EPS < stop < t - EPS:
            return abs(self.s(stop)) + abs(self.s(t) - self.s(stop))
        return abs(self.s(t))

    def phase(self, t0: float | None = None, t1: float | None = None) -> str:
        """What the speed does from ``t0`` to ``t1`` (default the whole run): speeding up, slowing down, steady, reverses."""
        t0, t1 = (0.0 if t0 is None else t0), (self.T if t1 is None else t1)
        if abs(self.a) < EPS:
            return STEADY
        stop = self.stop_time()
        if stop is not None and t0 + EPS < stop < t1 - EPS:
            return REVERSES
        before, after = abs(self.v(t0)), abs(self.v(t1))
        if after > before + EPS:
            return SPEEDING_UP
        if after < before - EPS:
            return SLOWING_DOWN
        return STEADY

    def trends(self) -> frozenset[str]:
        """Everything the speed does somewhere in the run. A reversing run both slows down (to rest) and speeds up."""
        phase = self.phase()
        if phase == REVERSES:
            return frozenset({SLOWING_DOWN, SPEEDING_UP, REVERSES})
        return frozenset({phase})

    # -- what a figure may say --

    def facts(self) -> Mapping[str, Any]:
        """Every number the screen may say, by name."""
        out: dict[str, Any] = {"start speed": self.u, "end speed": self.end_speed, "acceleration": self.a,
                               "duration": self.T, "displacement": self.s(self.T), "distance": self.distance(self.T),
                               "stop time": self.stop_time()}
        for t in self.marks:
            out[f"speed at {t:g}"] = self.v(t)
        return out

    def shown(self) -> frozenset[float]:
        """The numbers the drawn graph carries: start and end speed, acceleration, duration, and each mark's time and speed."""
        out = {self.u, self.end_speed, self.a, self.T}
        for t in self.marks:
            out |= {t, self.v(t)}
        return frozenset(round(_clean(x), 9) for x in out)


def solve(spec: Mapping[str, Any]) -> Motion:
    """The motion a figure describes: three of the four inputs given, the fourth worked out, everything checked."""
    if not isinstance(spec, Mapping):
        raise MotionError(f"a motion figure needs numbers: {_GIVE_THREE}")
    given = {k: _num(spec[k], k) for k in INPUT_KEYS if spec.get(k) is not None}
    if len(given) < 3:
        have = ", ".join(given) or "none"
        raise MotionError(f"a motion figure needs three numbers, but only {len(given)} given ({have}): {_GIVE_THREE}")
    u, v, a, T = (given.get(k) for k in INPUT_KEYS)
    if T is not None and not 0 < T <= MAX_DURATION:
        raise MotionError(f"duration must be more than 0 and at most {MAX_DURATION:g} s, not {T:g}")
    if len(given) == 4:
        if abs(u + a * T - v) > 1e-6 * max(1.0, abs(v)):
            raise MotionError(f"the four numbers disagree: {u:g} + {a:g} x {T:g} = {u + a * T:g}, not the {v:g} you gave "
                              "(give only three; code works out the fourth)")
    elif u is None:
        u = v - a * T
    elif a is None:
        a = (v - u) / T
    elif T is None:
        if abs(a) < EPS:
            raise MotionError("the duration cannot be worked out when the acceleration is 0: give the duration")
        T = (v - u) / a
        if not 0 < T <= MAX_DURATION:
            raise MotionError(f"going from {u:g} to {v:g} m/s at {a:g} m/s^2 would take {T:g} s, which is not a time "
                              f"from 0 to {MAX_DURATION:g} s: change a speed or the sign of the acceleration")
    for name, value in (("start speed", u), ("acceleration", a), ("duration", T), ("end speed", u + a * T)):
        if not math.isfinite(value) or abs(value) > MAX_VALUE:
            raise MotionError(f"the {name} comes out as {value:g}, which is out of range")
    raw = spec.get("marks")
    marks: list[float] = []
    if raw is not None:
        if not isinstance(raw, (list, tuple)):
            raise MotionError("marks must be a list of times in seconds, such as [3, 6]")
        for item in raw:
            t = _num(item, "a mark")
            if not -EPS <= t <= T + EPS:
                raise MotionError(f"mark {t:g} s is outside the run, which lasts 0 to {T:g} s")
            marks.append(min(max(t, 0.0), T))
    marks = sorted(set(marks))
    if len(marks) > MAX_MARKS:
        raise MotionError(f"at most {MAX_MARKS} marks can be labelled, not {len(marks)}")
    return Motion(u=_clean(u), a=_clean(a), T=T, marks=tuple(marks))


# ── module-level forms of the same questions ─────────────────────────────────────────────────────────────────────

def speed_at(m: Motion, t: float) -> float:
    return m.v(t)


def displacement_at(m: Motion, t: float) -> float:
    return m.s(t)


def distance_at(m: Motion, t: float) -> float:
    return m.distance(t)


def stop_time(m: Motion) -> float | None:
    return m.stop_time()


def phase(m: Motion, t0: float | None = None, t1: float | None = None) -> str:
    return m.phase(t0, t1)


def _plain(x: float) -> str:
    """6 decimals, no exponent, no trailing zeros: a number a graph function can be written with."""
    text = f"{x:.6f}".rstrip("0").rstrip(".")
    return "0" if text in ("", "-0") else text


def graph_params(m: Motion, marks=None, zero_floor: bool = False) -> dict:
    """The parameters ``longform.figures.graph`` draws this run from: v(t) as a line over 0..T, labelled points.

    Every number on the graph comes from ``m``: the line, the y range and each labelled point's time and speed.
    ``zero_floor`` (look ``craft``, S11): when no speed is negative the y axis starts at 0, not 2 units below it (the padding
    below zero made an empty band under every speed-time graph, and a graph's picture is as tall as its axis).
    """
    marks = m.marks if marks is None else tuple(marks)
    speeds = [m.u, m.end_speed] + [m.v(t) for t in marks]
    lo, hi = min(0.0, *speeds), max(0.0, *speeds)
    pad = max((hi - lo) * 0.12, 1.0)
    unit_word = "velocity" if lo < 0 else "speed"
    if abs(m.a) < EPS:
        name = f"v = {_plain(m.u)}"
    elif abs(m.u) < EPS:
        name = f"v = {_plain(m.a)}t"
    else:
        name = f"v = {_plain(m.u)} {'+' if m.a > 0 else '-'} {_plain(abs(m.a))}t"
    floor = 0 if zero_floor and lo >= 0 else math.floor(lo - pad)
    return {"functions": [f"{_plain(m.u)} + ({_plain(m.a)})*x"], "x_range": [0, m.T],
            "y_range": [floor, math.ceil(hi + pad)],
            "x_label": "time (s)", "y_label": f"{unit_word} (m/s)", "labels": {"curve0": name}, "meet": False,
            "points": [{"x": t, "y": m.v(t), "label": f"{t:g} s, {m.v(t):g} m/s", "role": "given"} for t in marks]}
