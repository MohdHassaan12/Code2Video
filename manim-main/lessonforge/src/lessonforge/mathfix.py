"""Cleaning of maths strings written by a model, shared by the video path (``transpiler``) and the lesson cards
(``harness.writer``, which re-exports these names). Pure: only ``re``, so the transpiler can import it without
pulling the harness in.
"""
import re

# A run of words starts at a word of three letters or more, or at a common two-letter word that
# another word follows: "1/2 is larger" was typeset "1/2islarger", because "is" stayed in maths
# italics (which eats spaces) and only "larger" became text. A lone "in" or "to" between symbols
# ("x in A", "0 to 10") is still left to the maths.
_SHORT_WORDS = (r"(?:(?i:is|of|to|in|on|by|or|an|as|if|so|we|it|be|no|at|do|up)(?=[ ]+[A-Za-z]{2,})"
                r"|(?<=\d[ ])(?i:by|of|to|or|is)(?=[ ]+\d))")      # … and between two numbers: "5 by 5" was "5by5"
_WORD_RUN = re.compile(r"(?<![\\A-Za-z{])([ ]*)((?:[A-Za-z]{3,}|" + _SHORT_WORDS + r")(?:[ ]+[A-Za-z]{2,})*)([ ]*)(?![A-Za-z}])")
_LONE_WORD = re.compile(r"(?<=[A-Za-z)}])[ ]+(by|is)[ ]+(?=(?:[A-Za-z0-9](?![A-Za-z])|[(\\]))", re.I)
_MATH_WORDS = {"sin", "cos", "tan", "cot", "sec", "csc", "log", "ln", "max", "min", "lim", "gcd"}
_GREEK_WORDS = {"theta", "alpha", "beta", "gamma", "delta", "phi", "lambda", "sigma", "omega", "pi", "eta", "rho",
                "tau", "epsilon"}


#: Units a number is written with. In maths mode "13 m" was set as the italic product "13m" (the trigonometry remake
#: of 2026-10-16: "c = 13 m" read as thirteen times a variable m).
_UNITS = ("mm", "cm", "km", "m", "kg", "g", "mg", "s", "ms", "min", "h", "N", "J", "kJ", "W", "kW", "V", "A", "Pa",
          "kPa", "L", "mL", "ml", "Hz", "K", "mol")
_UNIT = "(?:" + "|".join(sorted(_UNITS, key=len, reverse=True)) + ")"
_UNIT_AFTER_NUMBER = re.compile(r"(?<![\\A-Za-z])(\d+(?:\.\d+)?)(?:\s+(" + _UNIT + r"(?:/" + _UNIT + r")?)|\s*(" + _UNIT +
                                r"/" + _UNIT + r"))"
                                r"(?=\s*(?:\^|$|[,;)\]}=<>+\-]|\\[a-z]))")


def units_upright(show: str) -> str:
    """A unit written after a number is set upright with a thin space: "13 m" → "13\\,\\text{m}", "400 N/m^2" →
    "400\\,\\text{N/m}^2". Only a known unit, and only where the line goes on with a power, an operator or nothing."""
    return _UNIT_AFTER_NUMBER.sub(lambda m: m.group(1) + "\\,\\text{" + (m.group(2) or m.group(3)) + "}", str(show))


#: A run of plain words at the very start, ending in a colon ("Units:") or made only of words of 3+ letters.
_PLAIN_PREFIX = re.compile(r"^(\s*(?:[A-Za-z][A-Za-z0-9]*(?:[ \t]+[A-Za-z0-9]+)*[ \t]*:|(?:[A-Za-z]{3,}[ \t]+)+))(?=\s*\\)")


def mathify(show: str) -> str:
    """LaTeX for a step that mixes words and symbols: word runs become ``\\text{…}``.

    A model writes ``Right angle = 90^\\circ`` as an ordinary line; typeset as maths
    that came out as the italic run "Rightangle". Runs of three or more letters that are
    not already inside a command or braces are wrapped, so words stay words and single
    letters stay variables.

    Also handles the case where a model writes a plain-text prefix before a LaTeX command,
    e.g. ``Units: \\text{cm}^2`` — the ``Units:`` prefix is not in math mode and must be
    wrapped in ``\\text{}``, otherwise MathTex raises a LaTeX error on the colon.
    """
    if "\\text" in show or "\\mathrm" in show:
        # A plain-word prefix before the first command ("Units: \\text{cm}^2") is not in maths mode: the colon makes
        # LaTeX fail. Only a prefix that ends in a colon, or is made of words of three letters or more, is wrapped:
        # a variable before a command ("x \\text{cm}", "dx \\cdot") stays maths, and so do sin / cos / theta.
        prefix_match = _PLAIN_PREFIX.match(show)
        if prefix_match:
            words = re.findall(r"[A-Za-z]+", prefix_match.group(1))
            if not all(w.lower() in _MATH_WORDS or w.lower() in _GREEK_WORDS for w in words):
                show = "\\text{" + prefix_match.group(1).strip() + " }" + show[prefix_match.end(1):].lstrip()
        return units_upright(show)

    def wrap(match):
        before, run, after = match.group(1), match.group(2), match.group(3)
        # A word that follows a one-letter symbol ("I constant"): the space before it cannot be part of the match (a
        # run may not begin right after a letter), so it is looked for here. Without it "V by I constant" was set
        # "VbyIconstant" (a lesson of 2026-10-12).
        before = before or (" " if match.start() and match.string[match.start() - 1] == " " else "")
        # ... and the same on the other side, before a one-letter symbol: "Make i equal r" was set "Makeiequalr".
        after = after or (" " if match.end() < len(match.string) and match.string[match.end()] == " " else "")
        out, words = [], []

        def flush():
            if words:
                out.append("\\text{" + " ".join(words) + "}")
                words.clear()
        for word in run.split():
            if word.lower() in _MATH_WORDS or word.lower() in _GREEK_WORDS:
                flush()
                out.append("\\" + word.lower())      # sin → \sin, theta → \theta
            else:
                words.append(word)
        flush()
        # Maths mode eats spaces: "24 records, 1 update" came out as "24records, 1update".
        # A space next to a word is kept INSIDE the text group, where it survives.
        if out and before and out[0].startswith("\\text{"):
            out[0] = "\\text{ " + out[0][len("\\text{"):]
        if out and after and out[-1].startswith("\\text{"):
            out[-1] = out[-1][:-1] + " }"
        return " ".join(out) + ("" if out and out[-1].startswith("\\text{") else (" " if after else ""))
    # "by" and "is" standing alone between two symbols ("V by I", "x is 5") are words too: kept aside while the
    # runs of words are wrapped, then set as text with a space on each side.
    held = _LONE_WORD.sub(lambda m: f"\x00{m.group(1)}\x00", show)
    return units_upright(re.sub("\x00([A-Za-z]+)\x00", lambda m: "\\text{ " + m.group(1) + " }", _WORD_RUN.sub(wrap, held)))


#: Maths written with the keyboard's own symbols. LaTeX has no glyph for them, so a line holding
#: one was drawn as raw text with boxes: "1+3+■■■+(2n-1)=n^2" (2026-10-09, an ellipsis).
_UNICODE_MATH = {"…": r"\dots ", "⋯": r"\cdots ", "×": r"\times ", "÷": r"\div ", "−": "-", "–": "-", "·": r"\cdot ",
                 "²": "^2", "³": "^3", "√": r"\sqrt ", "≠": r"\neq ", "≤": r"\le ", "≥": r"\ge ", "≈": r"\approx ",
                 "→": r"\to ", "±": r"\pm ", "∞": r"\infty ", "π": r"\pi ", "θ": r"\theta ", "°": r"^\circ ",
                 "α": r"\alpha ", "β": r"\beta ", "Δ": r"\Delta ", "Σ": r"\Sigma ", "Ω": r"\Omega ", "∑": r"\sum ", "∫": r"\int ",
                 "∠": r"\angle ", "△": r"\triangle ", "⊥": r"\perp ", "∥": r"\parallel ", "∈": r"\in ",
                 "∪": r"\cup ", "∩": r"\cap ", "⇒": r"\Rightarrow ", "←": r"\leftarrow ", "↔": r"\leftrightarrow ",
                 "≡": r"\equiv ", "∝": r"\propto ", "∴": r"\therefore ", "γ": r"\gamma ", "δ": r"\delta ",
                 "λ": r"\lambda ", "μ": r"\mu ", "σ": r"\sigma ", "φ": r"\phi ", "ω": r"\omega ", "ρ": r"\rho ",
                 "ε": r"\epsilon ", "τ": r"\tau ", "½": r"\tfrac{1}{2}", "¼": r"\tfrac{1}{4}", "¾": r"\tfrac{3}{4}"}
_UNICODE_MATH_RE = re.compile("|".join(map(re.escape, _UNICODE_MATH)))


def latex_symbols(show: str) -> str:
    """Keyboard and Unicode maths symbols as the LaTeX a formula step needs."""
    return _UNICODE_MATH_RE.sub(lambda m: _UNICODE_MATH[m.group(0)], show)


def _balanced_text_calls(s: str) -> str:
    """``text(kg m)`` -> ``\\text{kg m}``, with the closing bracket found by counting, so ``text(f(x) in R)`` keeps
    its inner brackets (the one-line regex stopped at the first ``)``)."""
    out, i = [], 0
    while i < len(s):
        m = re.compile(r"\btext\(").search(s, i)
        if not m:
            out.append(s[i:])
            break
        out.append(s[i:m.start()])
        depth, j = 1, m.end()
        while j < len(s) and depth:
            depth += {"(": 1, ")": -1}.get(s[j], 0)
            j += 1
        if depth:                       # never closed: leave it as it was
            out.append(s[m.start():])
            break
        out.append("\\text{" + s[m.end():j - 1] + "}")
        i = j
    return "".join(out)


def sanitize_math(content) -> str:
    """The LaTeX a ``MathTex(r"...")`` line can compile, from what a model wrote for a ``math`` element.

    Until 2026-11-10 the video path put the model's string straight into ``MathTex`` while only the lesson cards
    cleaned theirs, so ``13 m``, ``Area = 4πr²``, ``$x^2$``, ``Units: cm`` and a stray ``"`` each ended a render in
    a LaTeX error. Steps, in order: strip ``$`` / ``\\(`` / ``\\[`` delimiters; ``text(..)`` to ``\\text{..}``;
    Unicode symbols to commands; word runs to ``\\text{..}`` and units upright (``mathify``); then make it safe
    inside a raw Python string: no newline, no ``"``, no trailing backslash. Running it twice changes nothing more.
    """
    s = str(content if content is not None else "")
    s = re.sub(r"\\[()\[\]]", " ", s).replace("$", " ")
    s = _balanced_text_calls(s)
    s = latex_symbols(s)
    s = mathify(s)
    s = s.replace("\r", " ").replace("\n", " ").replace('"', "''")
    s = re.sub(r"\s+", " ", s).strip()
    s = re.sub(r"[\\\s]+$", "", s)       # a trailing backslash would swallow the closing quote of r"..."
    return s or " "
