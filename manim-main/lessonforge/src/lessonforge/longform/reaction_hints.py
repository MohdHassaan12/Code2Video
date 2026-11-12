"""When a reaction picture should point at what the voice is talking about (no Manim here, so it can be tested).

The owner of the balancing-equations lesson (2026-10-20): "There are no dynamic hints in the video, the video is
stale." Measured: the picture changed in 10% of half-seconds (a Khan Academy lecture: 81 to 92%). The voice says
"count the oxygen atoms", "four hydrogen atoms on the right", "two water molecules", and the balls sat still.

``plan(sentences, species)`` reads the beat's heard words (each with its time) and returns events, each a moment and
what it is about. The figure (``figures.reaction``) turns an event into the balls and counts it lights, and
``runtime`` plays them beside the voice, stateless in time, so the picture always settles exactly as it was.
"""
from __future__ import annotations

import re

NAMES = {"hydrogen": "H", "oxygen": "O", "nitrogen": "N", "carbon": "C", "magnesium": "Mg", "chlorine": "Cl",
         "sodium": "Na", "calcium": "Ca", "sulphur": "S", "sulfur": "S", "iron": "Fe", "copper": "Cu", "zinc": "Zn",
         "aluminium": "Al", "aluminum": "Al", "potassium": "K", "phosphorus": "P", "silver": "Ag"}
COMMON = {"water": "H2O", "peroxide": "H2O2", "ammonia": "NH3", "methane": "CH4", "rust": "Fe2O3"}
NUMBER_WORDS = {"two": "2", "three": "3", "four": "4", "five": "5", "six": "6", "seven": "7", "eight": "8"}
#: Single letters that are also everyday words are never read as a symbol on their own.
NOT_SYMBOLS = {"a", "i"}
LEFT = {"left", "start", "starting", "before", "reactants"}
RIGHT = {"right", "end", "ending", "after", "products"}
COUNT = {"count", "counting", "counted", "recount"}
BOTH = {"both", "balanced", "balance", "matches", "match", "same", "equal"}
FRONT = {"front", "coefficient", "coefficients"}
SPAN = 1.6         # how long one light stays on (seconds)


def _words(sentence: dict) -> list[tuple[str, float]]:
    """(word, time) for every word of a sentence; positions are spread when the sentence has no heard words."""
    heard = sentence.get("words") or []
    if heard:
        return [(re.sub(r"[^a-z0-9]", "", str(w.get("word", "")).lower()), float(w.get("start", 0.0))) for w in heard]
    text = re.findall(r"[A-Za-z0-9']+", str(sentence.get("text", "")))
    start, length = float(sentence.get("start", 0.0)), float(sentence.get("duration", 0.0) or 2.0)
    return [(t.lower().replace("'", ""), start + length * i / max(1, len(text))) for i, t in enumerate(text)]


def spoken_forms(formula: str) -> list[list[str]]:
    """'H2O' → [['h', 'two', 'o'], ['h', '2', 'o']]: how a formula is read aloud letter by letter."""
    parts = re.findall(r"[A-Z][a-z]?|\d+", formula)
    words, digits = [], []
    for p in parts:
        if p.isdigit():
            words.append({v: k for k, v in NUMBER_WORDS.items()}.get(p, p))
            digits.append(p)
        else:
            letters = [ch.lower() for ch in p]
            words += letters
            digits += letters
    return [words, digits]


def plan(sentences: list[dict], species: list[dict]) -> list[dict]:
    """Events {t, kind, element?, side?, species?} in time order.

    ``species``: the figure's species in drawing order, each {"formula", "side", "atoms": [(el, k)]}.
    kinds: ``atoms`` (an element's balls, on one side or both), ``tally`` (a side's count of an element),
    ``species`` (one species' molecules and formula), ``count`` (every atom in turn, then the counts),
    ``front`` (the coefficients), ``both`` (both sides' counts together).
    """
    elements = {el for sp in species for el, _ in sp["atoms"]}
    forms = sorted(((form, i) for i, sp in enumerate(species) for form in spoken_forms(sp["formula"])),
                   key=lambda f: -len(f[0]))
    events: list[dict] = []
    for sentence in sentences or []:
        words = _words(sentence)
        last_element = None
        i = 0
        while i < len(words):
            word, t = words[i]
            matched = False
            for form, k in forms:                         # a formula read out: "h two o"
                if len(form) >= 2 and [w for w, _ in words[i:i + len(form)]] == form:
                    events.append({"t": t, "kind": "species", "species": k})
                    i += len(form)
                    matched = True
                    break
            if matched:
                continue
            nxt = words[i + 1][0] if i + 1 < len(words) else ""
            if word in COMMON:
                found = [k for k, sp in enumerate(species) if sp["formula"] == COMMON[word]]
                if found:
                    events.append({"t": t, "kind": "species", "species": found[0]})
                    i += 1
                    continue
            el = NAMES.get(word)
            if el in elements and nxt in COMMON:          # "hydrogen peroxide" is a substance, not hydrogen
                i += 1
                continue
            if el in elements:
                if nxt.startswith("molecule") or nxt == "gas":
                    found = [k for k, sp in enumerate(species) if sp["atoms"] == [(el, 2)]]
                    if found:
                        events.append({"t": t, "kind": "species", "species": found[0]})
                        i += 1
                        continue
                events.append({"t": t, "kind": "atoms", "element": el, "side": None})
                last_element = el
            elif word in COUNT:
                events.append({"t": t, "kind": "count"})
            elif word in FRONT:
                events.append({"t": t, "kind": "front"})
            elif word in BOTH:
                events.append({"t": t, "kind": "both", "element": last_element})
            elif last_element and (word in LEFT or word in RIGHT):
                side = "left" if word in LEFT else "right"
                events.append({"t": t, "kind": "tally", "element": last_element, "side": side})
            i += 1
    events.sort(key=lambda e: e["t"])
    # A "count" holds the picture for a while: lights inside it would only flicker over it.
    out, busy_until = [], -1.0
    for e in events:
        if e["t"] < busy_until and e["kind"] != "count":
            continue
        out.append(e)
        if e["kind"] == "count":
            busy_until = e["t"] + 2.2
    return out


#: Words that say the verdict of an equation (video-quality plan S5: "balance" alone is a verb in "to balance it").
VERDICT_SAID = {"balanced", "unbalanced"}


def stage_times(sentences: list[dict], species: list[dict]) -> dict:
    """When the count table and the verdict of a reaction picture may be drawn: ``{"table": t | None, "verdict": t | None}``.

    ``staging="steps"``: the table of atom counts appears at the first word that counts ("count", or an element's side:
    "oxygen on the left"), the verdict ("balanced", "not balanced yet") at the word that says it. ``None``: the voice never
    gets there in this beat, and the caller leaves that part with the picture (nothing is hidden for good)."""
    events = plan(sentences, species)
    table = min((e["t"] for e in events if e["kind"] in ("count", "tally")), default=None)
    verdict = None
    for sentence in sentences or []:
        for word, t in _words(sentence):
            if word in VERDICT_SAID:
                verdict = t if verdict is None else min(verdict, t)
    if verdict is not None and table is not None:
        verdict = max(verdict, table)             # the verdict is a conclusion drawn from the table
    return {"table": table, "verdict": verdict}
