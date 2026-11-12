"""When a geometry picture should point at what the voice is naming (no Manim here, so it can be tested).

The voice says "side AB", "angle C", "the diagonals", "ABCD", "the dent"; the matching part of the ``shape`` figure
lights up as it is said and settles back (``runtime._start_hints`` plays the light; ``shape_figure`` says which
mobjects a name stands for). Same contract as ``reaction_hints``: ``plan`` returns events, each a moment and the
names of the parts it lights, in order.

``values="spoken"`` (look key ``values``, video-quality plan S3) splits an angle's NAME from its VALUE: "angle DAB" lights the
arc and its letters, the number written beside the arc waits for the word that says it ("50"), and a sum line under the
picture waits for the word that says the total ("makes", "equals", "check"). A number or an equation the voice never says
in the beat falls back to the name, so nothing is left unseen. The default (``named``) is the old plan, event for event.

Letters are read from the sentence's own text, where their case survives: the heard words are lower case, and "a"
the article must never light vertex A. A capital letter is a point's name only where the picture has that point;
a lone "A" opening a sentence is the article.
"""
from __future__ import annotations

import re

SPAN = 1.6           # how long one light stays on (seconds)
WALK = 0.32          # seconds between sides when the boundary is walked
ANGLE_WORDS = {"angle", "angles", "corner", "corners"}
SIDE_WORDS = {"boundary", "perimeter", "around", "trace", "traced", "tracing", "walk"}
DIAGONAL_WORDS = {"diagonal", "diagonals"}
VERDICT_WORDS = {"convex", "concave", "nonconvex", "crosses", "crossing", "cross", "crossed", "collapsed", "collapses",
                 "degenerate", "selfintersecting", "dent", "reflex", "360", "sum", "total", "valid", "invalid",
                 "parallelogram", "kite", "trapezium", "rhombus", "rectangle", "square", "verdict"}
PARALLEL_WORDS = {"parallel"}
EQUAL_WORDS = {"equal", "same", "congruent"}
MID_WORDS = {"midpoint", "midpoints", "middle"}
#: Words that follow a point's name and never the article ("A moves", "A is"): as in ``speech.letter_names``.
#: Words that begin an equation or a total (``values="spoken"``: the sum line under the picture appears at the first of them).
EQ_WORDS = {"makes", "make", "equals", "equal", "gives", "totals", "total", "altogether", "check", "adds"}
#: How far past an angle's name its number is looked for: the rest of that sentence and the next one, at most this many words.
VALUE_REACH = 25
NAME_VERBS = {"and", "or", "is", "to", "has", "lies", "moves", "sits", "was", "becomes", "goes", "slides", "stays",
              "joins", "meets"}


def tokens(sentence: dict) -> list[tuple[str, float]]:
    """(token with its case, time) for every word of a sentence, timed by its heard words when they line up."""
    text = str(sentence.get("text", ""))
    raw = re.sub(r"[^\w ]", " ", text.replace("'", "")).split()
    heard = sentence.get("words") or []
    if heard and len(heard) == len(raw):
        return [(tok, float(w.get("start", 0.0))) for tok, w in zip(raw, heard)]
    start, length = float(sentence.get("start", 0.0)), float(sentence.get("duration", 0.0) or 2.0)
    if heard:
        # different splits (a number read as two words): spread the tokens between the first and last heard word
        first, last = float(heard[0].get("start", start)), float(heard[-1].get("start", start + length))
        return [(tok, first + (last - first) * i / max(1, len(raw) - 1)) for i, tok in enumerate(raw)]
    return [(tok, start + length * i / max(1, len(raw))) for i, tok in enumerate(raw)]


def _same_cycle(a: str, b: str) -> bool:
    if len(a) != len(b) or not a:
        return False
    return a in b + b or a[::-1] in b + b


def _letters(tok: str) -> list[str] | None:
    """'ABCD' → ['A','B','C','D'], a token that is only capital letters (and digits after a letter), else None."""
    if not re.fullmatch(r"(?:[A-Z]\d*)+", tok):
        return None
    return re.findall(r"[A-Z]\d*", tok)


def _value_time(rows: list[list[tuple[str, float]]], s: int, i: int, deg) -> float | None:
    """When the voice says ``deg`` (whole degrees) after word ``i`` of sentence ``s``: in that sentence or the next one."""
    if deg is None:
        return None
    seen = 0
    for k in (s, s + 1):
        if k >= len(rows):
            break
        for j, (tok, t) in enumerate(rows[k]):
            if k == s and j <= i:
                continue
            seen += 1
            if seen > VALUE_REACH:
                return None
            if tok.isdigit() and int(tok) == int(round(float(deg))):
                return t
    return None


def plan_one(sentences: list[dict], info: dict, spoken: bool = False) -> list[dict]:
    """Events {t, kind, parts: [names], gap} for one shape (``info`` from ``shape_figure.draw``).

    ``spoken``: an angle's number and a sum line wait for the word that says them (see the module note)."""
    segs, angles, points = info.get("segments", {}), info.get("angles", {}), info.get("points", set())
    words = info.get("words", {})
    degrees = info.get("angle_deg", {})
    rows = [tokens(sentence) for sentence in sentences or []]
    band = words.get("band")
    wait_band = bool(spoken and band and info.get("band_eq") and not info.get("band_verdict"))
    eq_times: list[float] = []
    total_times: list[float] = []
    band_fallback: list[float] = []
    polygon = info.get("polygon", "")
    sides = [segs[s] for s in info.get("sides", []) if s in segs]
    events: list[dict] = []

    def seg_part(a: str, b: str):
        return segs.get(a + b) or segs.get(b + a)

    def add(t, kind, parts, gap=0.0):
        parts = [p for p in parts if p]
        if parts:
            events.append({"t": t, "kind": kind, "parts": parts, "gap": gap})

    def angle_event(t, key, s, i):
        arc, value = angles.get(key), words.get(f"angle_{key}_value")
        if not spoken or not value:
            add(t, "angle", [arc, value])
            return
        said = _value_time(rows, s, i, degrees.get(key))
        add(t, "angle", [arc])                  # the name lights the arc and its letters ...
        add(t if said is None else said, "value", [value])        # ... the number, where the voice says it

    for s, sentence in enumerate(sentences or []):
        toks = rows[s]
        for i, (tok, t) in enumerate(toks):
            low = tok.lower()
            if wait_band:
                if low in EQ_WORDS:
                    eq_times.append(t)
                elif info.get("band_total") is not None and tok.isdigit() and int(tok) == int(round(info["band_total"])):
                    total_times.append(t)
            prev = toks[i - 1][0].lower() if i else ""
            prev2 = toks[i - 2][0].lower() if i > 1 else ""
            letters = _letters(tok)
            if letters and all(p in points for p in letters):
                if len(letters) == 1:
                    p = letters[0]
                    nxt = toks[i + 1][0] if i + 1 < len(toks) else ""
                    if p == "A" and i == 0 and nxt[:1].islower() and nxt not in NAME_VERBS:
                        continue                     # "A diagonal joins …": the article
                    if (prev in ANGLE_WORDS or (prev == "at" and prev2 in ANGLE_WORDS)) and p in angles:
                        angle_event(t, p, s, i)
                    else:
                        add(t, "point", [words.get(p), info.get("prefix", "") + "dot_" + p])
                        before = _letters(toks[i - 2][0]) if i > 1 and prev == "to" else None
                        if before and len(before) == 1 and before[0] in points:
                            # "join them in order, P to Q to R to S": each "to" draws the segment it names
                            add(t, "segment", [seg_part(before[0], p)])
                elif len(letters) == 2:
                    add(t, "segment", [seg_part(*letters), words.get(letters[0]), words.get(letters[1])])
                elif polygon and _same_cycle("".join(letters), polygon):
                    add(t, "walk", sides, WALK)
                elif len(letters) == 3:
                    named = "".join(letters)
                    if prev in ANGLE_WORDS and named in angles:
                        angle_event(t, named, s, i)
                    else:
                        trio = [seg_part(letters[0], letters[1]), seg_part(letters[1], letters[2]),
                                seg_part(letters[2], letters[0]), segs.get("fill_" + named)]
                        add(t, "triangle", trio, 0.12)
                continue
            if low in DIAGONAL_WORDS:
                nxt = toks[i + 1][0] if i + 1 < len(toks) else ""
                if not _letters(nxt):
                    add(t, "diagonals", [segs[d] for d in info.get("diagonals", []) if d in segs], 0.25)
            elif low in SIDE_WORDS or (low == "sides" and prev in ("four", "the", "its", "all")):
                add(t, "walk", sides, WALK)
            elif low in ("angles", "corners") and prev in ("four", "the", "its", "all", "interior"):
                add(t, "angles", list(angles.values()), 0.25)
            elif low in PARALLEL_WORDS:
                add(t, "parallel", [v for k, v in segs.items() if k.startswith("arrows_")])
            elif low in EQUAL_WORDS:
                add(t, "equal", [v for k, v in segs.items() if k.startswith("ticks_")])
            elif low in MID_WORDS:
                mids = info.get("midpoints") or []
                add(t, "midpoints", [info.get("prefix", "") + "dot_" + m for m in mids] + [words.get(m) for m in mids])
            elif low in VERDICT_WORDS or low.startswith("convex") or low.startswith("concav"):
                if wait_band:
                    band_fallback.append(t)         # "sum" names the total, it does not say it: used only if nothing else comes
                else:
                    add(t, "verdict", [words.get("band")])
                if low in ("dent", "reflex") or low.startswith("concav"):
                    st = info.get("status") or {}
                    for v in st.get("reflex") or []:
                        add(t + 0.15, "angle", [angles.get(v), words.get(f"angle_{v}_value"), words.get(v)])
            elif low in ("crosses", "crossing", "cross", "crossed", "selfintersecting"):
                add(t, "verdict", [segs.get("crossing"), words.get("band")])
    if wait_band:
        # the sum line is drawn where the equation is said; a lesson that never says one keeps the old word
        for t in ([min(eq_times)] if eq_times else [min(total_times)] if total_times else band_fallback):
            add(t, "verdict", [band])
    return events


def plan_panels(sentences: list[dict], panels: list[dict]) -> list[dict]:
    """Panels side by side: a word that names a panel (its ``key``) lights that panel's outline and caption, and the
    names inside it as ``plan_one`` reads them."""
    events: list[dict] = []
    keys = []
    for info in panels:
        words = re.findall(r"[a-z]+", str(info.get("key", "")).lower())
        keys.append(set(w for w in words if len(w) > 2 and w not in {"the", "and", "with", "not", "one"}))
    for sentence in sentences or []:
        for tok, t in tokens(sentence):
            low = tok.lower().replace("-", "")
            for k, info in enumerate(panels):
                if low in keys[k]:
                    sides = [info["segments"][s] for s in info.get("sides", []) if s in info["segments"]]
                    parts = sides + [info.get("words", {}).get("band")]
                    events.append({"t": t, "kind": "panel", "parts": [p for p in parts if p], "gap": 0.0})
    return events


def plan(sentences: list[dict], info: dict | None, panels: list[dict] | None = None, spoken: bool = False) -> list[dict]:
    events = plan_panels(sentences, panels) if panels else plan_one(sentences, info or {}, spoken)
    events.sort(key=lambda e: e["t"])
    out, last = [], {}
    for e in events:
        key = tuple(e["parts"])
        if key in last and e["t"] - last[key] < 0.8:
            continue                     # the same thing named twice in a breath lights once
        last[key] = e["t"]
        out.append(e)
    return out
