"""The chemistry kit: a chemical equation drawn as molecules with an atom-count table (classes 7 to 9).

The chain a kit supplies, in one file, over code that already exists (nothing is parsed or counted twice):

* MODEL    ``longform/reaction_math.py`` (pure, stdlib) reads the equation ONCE through ``figure_math``
           (``parse_equation``, ``atom_counts``, ``balance``): atoms of each element on each side, the coefficients as
           written, the smallest balancing coefficients, balanced yes/no, real element symbols.
* FIGURE   ``{"kind": "chem_reaction", "equation": "2H2 + O2 -> 2H2O"}`` is drawn by the existing ``figures.reaction``
           builder (``longform/kit_figures.py:chem_reaction``), so the picture, the voice-led hints and the
           coefficient-change animation are the ones the ``reaction`` figure has.
* GAPS     ``{atoms of O left}``, ``{atoms of oxygen after}``, ``{total atoms right}``, ``{coefficient of H2}``,
           ``{balanced coefficient of H2O}`` are filled by code.
* CLAIMS   "balanced", "not balanced", "the same number of atoms on both sides", "conserved here" and "more X atoms
           on the left" are checked against the counts; a typed atom count the picture does not show is a fault.
* RULES    ``REACTION_RULES``, shipped only through ``brief["kits"]`` or the workbench addendum.

WHY THE KIND IS ``chem_reaction`` AND NOT ``reaction`` (the one design decision here): ``reaction`` is a built-in
figure kind, written by the writer's own prompt (``writer.FIGURE_KINDS``, pinned by ``test_prompts_pinned``) and
drawn by ``figures.BUILDERS``. ``registry.register`` lets only a ``legacy`` adapter own a built-in kind, and a legacy
kit is never served: its gaps and claims would not be checked at all. Owning ``reaction`` as a served kit would make
every OLD lesson with a reaction figure ``active`` and subject it to new faults and repair calls. So the served kit
owns a NEW kind that reaches the same builder, and every old ``reaction`` lesson stays as it was, byte for byte.

Nothing here imports manim or numpy.
"""
from __future__ import annotations

import re
from typing import Mapping

from ..longform import reaction_math as R
from ..longform.reaction_hints import NAMES
from .base import GAP, KitBase, KitCases, KitError, Lesson, arithmetic
from .registry import register

REACTION_RULES = """    {"kind":"chem_reaction","equation":"2H2 + O2 -> 2H2O"}
      A chemical equation drawn as molecules, with a table of the atoms of each element before and after, and a
      verdict (balanced, not balanced yet, find the numbers). Give ONLY the equation, as formulas and an arrow
      ("->"), a coefficient in front of a formula (1 to 6). Write an unknown coefficient as "?": "? N2 + ? H2 -> ? NH3".
      Every symbol must be a real element. Not drawn: state symbols (s)(l)(g), ions and charges, reversible arrows,
      word equations. Optional: "counts":false hides the table; "role":"wrong" with "wrong":["H2O2"] marks a formula
      that was changed, which is not allowed.
      Never type an atom count or a coefficient you worked out: write a gap and code fills it from the equation:
      {atoms of O left}, {atoms of hydrogen right} (sides: left, right, before, after), {total atoms left},
      {coefficient of H2} (as written; a "?" has none), {balanced coefficient of H2O} (the smallest whole numbers that
      balance it; add left or right when a formula is on both sides); arithmetic works on them: {atoms of H left + 2}.
      A number of atoms that is not a gap, a coefficient or a subscript the picture shows is a fault.
      Say only what the counts allow. "balanced" or "the same number of atoms on both sides" needs every count equal
      and no "?"; "not balanced" needs a count that differs (or a "?"); "more oxygen atoms on the left" needs it so.
      Give a NEW chem_reaction figure when the equation changes, and the solved equation on the beat after the "?".
"""

#: Parts a step's "focus" may name (the reaction builder's own parts).
_PARTS = ("left", "right", "arrow", "left_count", "right_count", "verdict") + tuple(
    p for i in range(6) for p in (f"mol{i}", f"formula{i}"))

_SIDE = r"left|right|before|after|reactants?|products?"
_HEDGE = re.compile(r"\b(?:never|no longer|doesn't|doesnt|don't|dont|didn't|won't|cannot|can't|without|nor|neither|"
                    r"unless|if|would|could|might|may|whether|or|make|makes|making|made|until|need|needs|needed|want|"
                    r"wants|try|tries|trying|get|gets|getting|should|must|once|when|how|let's|lets|so that|before it|"
                    r"to be|will)\b", re.I)
_NOT_BALANCED = re.compile(
    r"\b(?:not\s+(?:yet\s+)?balanced|(?:isn|aren|wasn|weren)['’]?t\s+(?:yet\s+)?balanced|unbalanced|"
    r"(?:does|do)\s*(?:not|n['’]?t)\s+(?:yet\s+)?balance)\b", re.I)
_BALANCED = re.compile(r"(?<!un)\bbalanced\b|\bbalances\b", re.I)
_GENERAL = re.compile(r"\b(?:a|an|every|any|each|what\s+is\s+a)\s+(?:\w+\s+)?$", re.I)     # "a balanced equation has ..."
_SAME = re.compile(
    r"\b(?:same|equal)\s+(?:number|count|amount|numbers|counts)\s+of\s+(?:\w+\s+){0,2}?atoms?\b"
    r"|\b(?:atoms?|counts?|numbers?)\b[^.]{0,30}?\b(?:are|is|stay|stays|remain|remains|match|matches)\s+(?:the\s+)?"
    r"(?:same|equal)\b"
    r"|\bboth\s+sides\s+(?:have|has|hold)\s+(?:the\s+)?same\b", re.I)
_CONSERVED = re.compile(r"\bconserved\b|\bconserves\b|\bnothing\s+(?:is\s+)?(?:lost|created)\b", re.I)
#: A "conserved" that talks about THIS picture; "mass is conserved in every reaction" is a law, not a claim about it.
_HERE = re.compile(r"\b(?:here|now|both\s+sides|each\s+side|either\s+side|this\s+equation|as\s+written|so\s+far|"
                   r"on\s+(?:the\s+)?screen|in\s+(?:this|the)\s+picture)\b", re.I)
_MORE = re.compile(rf"\b(?P<cmp>more|fewer|less)\s+(?:(?P<el>[A-Za-z]+)\s+)?atoms?\s+(?:on|in)\s+the\s+(?P<side>left|right)\b", re.I)
_NUMBER = r"\d+|one|two|three|four|five|six|seven|eight|nine|ten"
_WORDS = {w: str(i) for i, w in enumerate(_NUMBER.split("|")[1:], start=1)}
_ATOMS_A = re.compile(rf"(?<![\w.])(?P<n>{_NUMBER})\s+(?:(?P<el>[A-Za-z]+)\s+)?atoms?\b", re.I)
_ATOMS_B = re.compile(rf"(?<![\w.])(?P<n>{_NUMBER})\s+atoms?\s+of\s+(?P<el>[A-Za-z]+)\b", re.I)
_TERM = re.compile(
    rf"\batoms?\s+of\s+(?P<el>[A-Za-z]+)\s+(?P<s1>{_SIDE})\b"
    rf"|\btotal\s+atoms\s+(?P<s2>{_SIDE})\b"
    rf"|\b(?P<bal>balanced\s+)?coefficient\s+of\s+(?P<f>[A-Za-z0-9()]+)(?:\s+(?P<s3>{_SIDE})\b)?", re.I)
_CAN_ONLY = ("can only hold atoms of E left|right, total atoms left|right, coefficient of FORMULA, balanced coefficient "
             "of FORMULA, numbers and + - * / (E is an element symbol or name)")


def _sentences(text: str) -> list[str]:
    return [s for s in re.split(r"(?<=[.!?])\s+", text or "") if s]


def _nice(value: float) -> str:
    return f"{round(value, 2) + 0.0:g}"


def _side(word: str | None) -> str | None:
    return R.SIDES.get(word.lower()) if word else None


def _sides_named(sentence: str) -> set[str]:
    words = {w.lower() for w in re.findall(r"[A-Za-z]+", sentence)}
    return {side for w, side in R.SIDES.items() if w in words}


class ReactionKit(KitBase):
    name = "chemistry"
    figure_kinds = ("chem_reaction",)
    subjects = ("chemistry",)
    classes = (7, 8, 9)
    keywords = ("reaction", "equation", "balance", "balanced", "balancing", "atom", "atoms", "molecule", "formula",
                "chemical change", "chemical reaction", "conserved", "conservation of mass", "reactant", "product",
                "coefficient", "element", "compound", "rust", "combustion", "burning")
    rules = REACTION_RULES
    builder: Mapping[str, str] = {"chem_reaction": "lessonforge.longform.kit_figures:chem_reaction"}
    focus_parts: Mapping[str, tuple[str, ...]] = {"chem_reaction": _PARTS}
    mcp_note = ("Chemistry figures are chem_reaction equations such as \"2H2 + O2 -> 2H2O\": write a gap such as "
                "{atoms of O left} or {coefficient of H2} and code fills it, on a beat whose figure is a chem_reaction.")

    # -- the model --

    def solve(self, figure):
        try:
            return R.solve(figure)
        except R.ReactionError as exc:
            raise KitError(str(exc)) from exc

    def normalise_figure(self, figure):
        if not isinstance(figure, dict):
            return None
        try:
            m = self.solve(figure)
        except KitError:
            return None
        out: dict = {"kind": "chem_reaction", "equation": m.equation}
        if not m.counts_shown:
            out["counts"] = False
        if m.wrong:
            out["role"] = "wrong"
            if m.wrong_names:
                out["wrong"] = list(m.wrong_names)
        return out

    def describe(self, figure):
        try:
            m = self.solve(figure)
        except KitError as exc:
            return str(exc)
        bits = [f"{m.equation} is {m.verdict}"]
        bits.append("atoms before: " + ", ".join(f"{el} {m.count(el, 'left')}" for el in m.elements)
                    + "; after: " + ", ".join(f"{el} {m.count(el, 'right')}" for el in m.elements))
        solved = m.solved() if not m.balanced or m.unknown else None
        if solved:
            names = [f"{n} {f}" for n, (f, _, _) in zip([*solved["left"], *solved["right"]], m.formulas())]
            bits.append("smallest balancing coefficients: " + ", ".join(names))
        return "; ".join(bits)

    # -- gaps --

    def fill_gap(self, expr, model):
        def pick(formula: str, side: str | None) -> tuple[str, int]:
            plain = R.figure_math._plain_formula(formula)        # noqa: SLF001 - the one reading of a formula
            found = [(f, s, i) for f, s, i in model.formulas() if f == plain and (side is None or s == side)]
            if not found:
                have = ", ".join(dict.fromkeys(f for f, _, _ in model.formulas()))
                raise KitError(f"gap {{{expr}}}: {formula} is not in the equation (it has {have})")
            if len(found) > 1:
                raise KitError(f"gap {{{expr}}}: {plain} is on both sides: say left or right")
            return found[0][1], found[0][2]

        def term(match) -> str:
            if match.group("f"):
                side, index = pick(match.group("f"), _side(match.group("s3")))
                if match.group("bal"):
                    solved = model.solved()
                    if solved is None:
                        raise KitError(f"gap {{{expr}}}: no whole coefficients up to {R.figure_math.MAX_COEFFICIENT} "
                                       "balance this equation: check the formulas")
                    value = solved[side][index]
                else:
                    sp = model.species(side)[index]
                    if sp["unknown"]:
                        raise KitError(f"gap {{{expr}}}: the figure still asks for this coefficient (?), so it has "
                                       "none yet: use {balanced coefficient of " + sp["formula"] + "} or show the "
                                       "solved equation on a beat and use {coefficient of ...} there")
                    value = sp["n"]
            else:
                if not model.counts_shown:
                    raise KitError(f"gap {{{expr}}}: this figure hides its atom counts (counts:false), so they are "
                                   "not on the screen: take counts:false out or do not give a count")
                side = _side(match.group("s1") or match.group("s2"))
                if match.group("el"):
                    element = R.element_of(match.group("el"))
                    if element is None or element not in model.elements:
                        have = ", ".join(model.elements)
                        raise KitError(f"gap {{{expr}}}: there is no {match.group('el')} in the equation "
                                       f"(it has {have})")
                    value = model.count(element, side)
                else:
                    value = model.total(side)
            return f"({value})"
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

    @staticmethod
    def summary(model) -> str:
        sides = "; ".join(f"{el}: {model.count(el, 'left')} before, {model.count(el, 'right')} after"
                          for el in model.elements)
        return f"{model.equation} ({sides}; {model.verdict})"

    def claims(self, text, model):
        issues: list[str] = []
        for sentence in _sentences(GAP.sub(" ", text or "")):          # a gap that failed to fill is not a claim
            if sentence.rstrip().endswith("?"):
                continue                                              # a question asks; it claims nothing
            say = f"the words say “%s”, but the picture is: {self.summary(model)}"
            for m in _NOT_BALANCED.finditer(sentence):
                if self._hedged(sentence, m.start()):
                    continue
                if model.balanced:
                    issues.append(say % m.group(0))
            rest = _NOT_BALANCED.sub(lambda m: " " * len(m.group(0)), sentence)
            for m in _BALANCED.finditer(rest):
                before = rest[:m.start()]
                if self._hedged(rest, m.start()) or _GENERAL.search(before[-24:]):
                    continue
                if not model.balanced:
                    issues.append(say % m.group(0))
            for m in _SAME.finditer(rest):
                if not self._hedged(rest, m.start()) and not self._same_ok(sentence, model):
                    issues.append(say % m.group(0))
            for m in _CONSERVED.finditer(rest):
                if _HERE.search(sentence) and not self._hedged(rest, m.start()) and not self._same_ok(sentence, model):
                    issues.append(say % m.group(0))
            for m in _MORE.finditer(sentence):
                if self._hedged(sentence, m.start()):
                    continue
                side = m.group("side").lower()
                other = "right" if side == "left" else "left"
                element = R.element_of(m.group("el")) if m.group("el") else None
                if element is not None:
                    mine, theirs = model.count(element, side), model.count(element, other)
                elif m.group("el") and m.group("el").lower() not in ("more", "extra", "many", "some", "fewer", "less"):
                    continue                                          # a word we cannot read: no claim we can check
                else:
                    mine, theirs = model.total(side), model.total(other)
                ok = mine > theirs if m.group("cmp").lower() == "more" else mine < theirs
                if not ok:
                    issues.append(say % m.group(0))
        return list(dict.fromkeys(issues))

    @staticmethod
    def _hedged(sentence: str, start: int) -> bool:
        before = sentence[:start]
        return bool(_HEDGE.search(before[max(0, len(before) - 40):]))

    @staticmethod
    def _same_ok(sentence: str, model) -> bool:
        """'The same number of atoms': true when every element NAMED in the sentence agrees (all of them if none is)."""
        named = {el for w in re.findall(r"[A-Za-z]+", sentence)
                 if w.lower() in NAMES and (el := NAMES[w.lower()])}
        named |= {m.group(1) for m in re.finditer(r"\b([A-Z][a-z]?)\s+atoms?\b", sentence) if m.group(1) in R.ELEMENTS}
        if named:
            return all(model.count(el, "left") == model.count(el, "right") for el in named)
        return model.balanced

    # -- typed numbers --

    def stray_numbers(self, text, model, used):
        filled = {abs(v) for v in used}
        out: list[str] = []
        for sentence in _sentences(GAP.sub(" ", text or "")):
            sides = _sides_named(sentence)
            sides = {s for s in sides} if len(sides) == 1 else {"left", "right"}
            for pattern in (_ATOMS_A, _ATOMS_B):
                for m in pattern.finditer(sentence):
                    n = float(_WORDS.get(m.group("n").lower(), m.group("n")))
                    word = m.group("el")
                    element = R.element_of(word) if word else None
                    if word and element is None and pattern is _ATOMS_B:
                        continue                                       # "atoms of a molecule": not an element
                    if n in filled or n in self._pool(model, element, sides):
                        continue
                    what = f"{n:g} {element} atoms" if element else f"{n:g} atoms"
                    if what not in out:
                        out.append(what)
        return out

    @staticmethod
    def _pool(model, element: str | None, sides: set[str]) -> set[float]:
        species = [sp for name in sides for sp in model.parsed[name]]       # a sentence about one side reads that side
        pool: set[float] = {float(sp["n"]) for sp in species}
        for sp in species:
            for el, k in sp["atoms"]:
                if element is None or el == element:
                    pool |= {float(k), float(k * sp["n"])}
            if element is None:
                whole = sum(k for _, k in sp["atoms"])                 # atoms in one molecule, and in all its copies
                pool |= {float(whole), float(whole * sp["n"])}
        if model.counts_shown:
            for side in sides:
                if element is None:
                    pool |= {float(model.count(el, side)) for el in model.elements} | {float(model.total(side))}
                else:
                    pool.add(float(model.count(element, side)))
        return pool

    # -- conformance --

    def cases(self) -> KitCases:
        bal = {"kind": "chem_reaction", "equation": "2H2 + O2 -> 2H2O"}
        unbal = {"kind": "chem_reaction", "equation": "H2 + O2 -> H2O"}
        unknown = {"kind": "chem_reaction", "equation": "? H2 + ? O2 -> ? H2O"}
        wrong = {"kind": "chem_reaction", "equation": "2H2 + O2 -> 2H2O2", "role": "wrong", "wrong": ["H2O2"]}
        good = _lesson(
            _beat("Count the oxygen atoms. The left has {atoms of O left} and the right has {atoms of O right}, so "
                  "the equation is not balanced.", unbal,
                  quiz={"question": "How many oxygen atoms are on the right?",
                        "options": ["{atoms of O right}", "{atoms of O left}", "{atoms of O left + atoms of O right}"],
                        "answer_index": 0, "why": ["right", "that is the left", "that is both added"]}),
            _beat("Now find the numbers that make each element match. Count each atom again.", unknown),
            _beat("With {coefficient of H2} hydrogen molecules and {coefficient of H2O} water molecules the equation "
                  "is balanced. Each side has {atoms of H right} hydrogen atoms, and the atoms are conserved here.", bal),
            _beat("Changing the formula to H2O2 is not allowed: it makes a different substance.", wrong))
        return KitCases(
            good=(good,),
            refused=((_lesson(_beat("The equation is balanced.", unbal)), "balanced"),
                     (_lesson(_beat("The equation is not balanced yet.", bal)), "not balanced"),
                     (_lesson(_beat("There are 5 oxygen atoms on the right.", unbal)), "5 O atoms"),
                     (_lesson(_beat("The atoms are conserved here.", unbal)), "conserved"),
                     (_lesson(_beat("There are more oxygen atoms on the right.", unbal)), "more oxygen atoms"),
                     (_lesson(_beat("It has {atoms of Na left} sodium atoms.", unbal)), "no Na in the equation"),
                     (_lesson(_beat("We need {coefficient of H2}.", unknown)), "still asks for this coefficient"),
                     (_lesson(_beat("Look at it.", {"kind": "chem_reaction", "equation": "CaCO3(s) -> CaO + CO2"})),
                      "cannot read the equation"),
                     (_lesson(_beat("Look at it.", {"kind": "chem_reaction", "equation": "Zz2 + O2 -> ZzO"})),
                      "not an element symbol"),
                     (_lesson(_beat("Oxygen on the left is {atoms of O left} atoms.", None)), "no chemistry figure")),
            gaps=(("atoms of O left", unbal, "2"), ("atoms of O right", unbal, "1"), ("atoms of oxygen after", bal, "2"),
                  ("coefficient of H2", bal, "2"), ("balanced coefficient of H2O", unknown, "2"),
                  ("balanced coefficient of H2", unbal, "2"), ("atoms of H left + atoms of O left", bal, "6"),
                  ("total atoms right", bal, "6"), ("atoms of H left - 1", bal, "3"),
                  ("coefficient of H2O right", bal, "2")))


def _beat(narration: str, figure: dict | None = None, quiz: dict | None = None) -> dict:
    beat = {"narration": narration, "steps": [{"say": narration.split(".")[0][:30], "show": "x"}]}
    if figure is not None:
        beat["figure"] = figure
    if quiz:
        beat["quiz"] = quiz
    return beat


def _lesson(*beats: dict) -> Lesson:
    return {"title": "cases", "chapters": [{"title": "ONE", "learning_goal": "g", "role": "explain", "beats": list(beats)}]}


REACTION = register(ReactionKit())
