"""A chemical equation worked out by code (stdlib only: no manim, no numpy). The model behind the ``chemistry`` kit.

This is a thin layer over ``figure_math`` (``parse_equation``, ``atom_counts``, ``balance``), which already read an
equation once for the ``reaction`` figure: nothing is parsed or counted twice here. What this adds is what a LESSON
may say about the figure: atoms of each element on each side, the coefficients as written, the smallest balancing
coefficients, whether the equation is balanced, and the checks that an element is a real one and that a formula
named in ``wrong`` is in the equation.

``ReactionError`` is a ``ValueError`` with a plain-words message; the kit turns it into a ``KitError``.
"""
from __future__ import annotations

import functools
import re
from typing import Any, Mapping

from . import figure_math

#: The 118 element symbols (a made-up symbol such as ``Zz`` parses as a formula, so the kit checks it here).
ELEMENTS = frozenset(
    "H He Li Be B C N O F Ne Na Mg Al Si P S Cl Ar K Ca Sc Ti V Cr Mn Fe Co Ni Cu Zn Ga Ge As Se Br Kr Rb Sr Y Zr Nb Mo "
    "Tc Ru Rh Pd Ag Cd In Sn Sb Te I Xe Cs Ba La Ce Pr Nd Pm Sm Eu Gd Tb Dy Ho Er Tm Yb Lu Hf Ta W Re Os Ir Pt Au Hg Tl "
    "Pb Bi Po At Rn Fr Ra Ac Th Pa U Np Pu Am Cm Bk Cf Es Fm Md No Lr Rf Db Sg Bh Hs Mt Ds Rg Cn Nh Fl Mc Lv Ts Og".split())
SIDES = {"left": "left", "before": "left", "reactants": "left", "reactant": "left",
         "right": "right", "after": "right", "products": "right", "product": "right"}
MAX_SPECIES_TO_BALANCE = 5          # ``balance`` tries every coefficient: 6 ** n tries per total
_FORMAT = ("write the equation as formulas with an arrow, like \"2H2 + O2 -> 2H2O\" (an unknown coefficient as \"?\"; "
           "no state symbols, ions or reversible arrows; coefficients 1 to " + str(figure_math.MAX_COEFFICIENT) + ")")


class ReactionError(ValueError):
    """An equation code cannot read or a figure that is not coherent; the message says what to change."""


def clean_equation(equation: Any) -> str:
    return re.sub(r"\s+", " ", str(equation or "")).strip()[:160]


class Reaction:
    """One reading of a ``chem_reaction`` figure. Build it with :func:`solve`."""

    notes: tuple[str, ...] = ()

    def __init__(self, equation: str, parsed: dict, counts_shown: bool, wrong: bool, wrong_names: tuple[str, ...]):
        self.equation = equation
        self.parsed = parsed
        self.counts_shown = counts_shown
        self.wrong = wrong
        self.wrong_names = wrong_names
        self.before = figure_math.atom_counts(parsed["left"])
        self.after = figure_math.atom_counts(parsed["right"])
        self.unknown = any(sp["unknown"] for side in parsed.values() for sp in side)
        self.balanced = figure_math.is_balanced(parsed)
        self.elements = tuple(dict.fromkeys([*self.before, *self.after]))

    # -- what the picture says --

    @property
    def verdict(self) -> str:
        """The words under the table, as ``figures.reaction`` and ``visual_actions.reaction_state`` choose them."""
        return ("formula changed" if self.wrong else "find the numbers" if self.unknown
                else "balanced" if self.balanced else "not balanced yet")

    def species(self, side: str) -> list[dict]:
        return self.parsed[side]

    def count(self, element: str, side: str) -> int:
        return (self.before if side == "left" else self.after).get(element, 0)

    def total(self, side: str) -> int:
        return sum((self.before if side == "left" else self.after).values())

    def formulas(self) -> list[tuple[str, str, int]]:
        """(formula, side, index within the side) of every species, in drawing order."""
        return [(sp["formula"], side, i) for side in ("left", "right") for i, sp in enumerate(self.parsed[side])]

    # -- what code works out beyond the picture --

    def solved(self) -> dict | None:
        """The smallest whole coefficients that balance the formulas as written, or None when none up to 6 do."""
        return _balance(self.equation)

    # -- the KitModel protocol --

    def facts(self) -> Mapping[str, Any]:
        out: dict[str, Any] = {"equation": self.equation, "verdict": self.verdict}
        if self.counts_shown:
            for el in self.elements:
                out[f"{el} atoms left"] = self.count(el, "left")
                out[f"{el} atoms right"] = self.count(el, "right")
        return out

    def shown(self) -> frozenset[float]:
        """Numbers the drawing carries: each coefficient above 1 (a known one) and, when counts are on, every count."""
        out = {float(sp["n"]) for side in self.parsed.values() for sp in side if not sp["unknown"] and sp["n"] > 1}
        if self.counts_shown:
            out |= {float(n) for n in (*self.before.values(), *self.after.values())}
        return frozenset(out)


@functools.lru_cache(maxsize=256)
def _balance(equation: str) -> dict | None:
    parsed = figure_math.parse_equation(equation)
    if len(parsed["left"]) + len(parsed["right"]) > MAX_SPECIES_TO_BALANCE:
        return None
    return figure_math.balance(parsed)


def solve(spec: Any) -> Reaction:
    """The :class:`Reaction` of a ``chem_reaction`` figure, or ``ReactionError`` in plain words."""
    if not isinstance(spec, dict):
        raise ReactionError("a reaction figure needs an \"equation\"")
    equation = clean_equation(spec.get("equation"))
    if not equation:
        raise ReactionError(f"a reaction figure needs an \"equation\": {_FORMAT}")
    try:
        parsed = figure_math.parse_equation(equation)
    except ValueError as exc:
        raise ReactionError(f"code cannot read the equation {equation!r} ({exc}): {_FORMAT}") from exc
    for side in parsed.values():
        for sp in side:
            for el, _ in sp["atoms"]:
                if el not in ELEMENTS:
                    raise ReactionError(f"{el} in {sp['formula']} is not an element symbol: check the formula")
    wrong = str(spec.get("role") or "") == "wrong"
    named = spec.get("wrong")
    names: list[str] = []
    if wrong and isinstance(named, list):
        names = [figure_math._plain_formula(w) for w in named if isinstance(w, str)]       # noqa: SLF001 - one reading
        present = {sp["formula"] for side in parsed.values() for sp in side}
        missing = [w for w in names if w not in present]
        if missing:
            raise ReactionError(f"\"wrong\" names {', '.join(missing)}, which is not in the equation {equation!r} "
                                f"(it has {', '.join(sorted(present))})")
    return Reaction(equation, parsed, spec.get("counts") is not False, wrong, tuple(names))


def element_of(token: str) -> str | None:
    """'O', 'o', 'oxygen' -> 'O'; None for a word that is no element."""
    from . import reaction_hints                         # NAMES: the element names a voice hint already knows
    word = token.strip()
    if not word:
        return None
    low = word.lower()
    if low in reaction_hints.NAMES:
        return reaction_hints.NAMES[low]
    symbol = word[0].upper() + word[1:].lower()
    return symbol if symbol in ELEMENTS else None
