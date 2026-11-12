"""The agentic pipeline that calls the subject kits: route, brief, write, settle, repair, add, look, film.

A lesson brief goes in; a checked lesson on the workbench comes out, with a trace of every step. The order is the
repo's cost rule, code first and free, the model last and capped:

1. ``route``      each beat (or paragraph) of the brief is given to a kit BY CODE: its words are scored against what each
                  kit declares (``kits.describe()``: subjects, classes, keywords; for the components kit, each component of
                  the catalogue on its own). A beat nothing fits gets ``kit=None`` (the existing scene or diagram figure
                  kinds, never a failure). An optional model router, a callable you inject, decides only the beats the
                  code scored low, and its answer is validated against the registry and the component catalogue.
2. ``plan_to_brief`` fills ``brief["kits"]`` (so only those kits' rules reach the writer; several kits get the mixed-lesson
                  addendum) and ``brief["kit_hints"]``, one line per part of the brief for the writer to read.
3. ``run``        route, brief, write (``writer.write_lesson`` with the injected model, or a ready ``lesson=``), settle and
                  check every kit's beats, a bounded repair loop, ``workbench.add``, optionally the stills and the film.
                  It returns a :class:`Report`: plan, lesson id, faults, craft numbers, spend and the steps taken.

The rule that holds: code, not a model, decides every fact on screen. The router only picks WHICH kit draws a part; the
kit's model works out every number, the gaps are filled by code, and a claim or typed value the picture denies is a fault
that no round of repair may leave behind unnoticed (the report lists what is left).

Money. ``llm`` is a callable ``(prompt, system) -> parsed JSON`` (the writer's own shape). ``llm=None`` means free only:
nothing here calls a model. A model is wrapped in :class:`Meter`, which refuses a call BEFORE making it when the call,
by the last one's cost, would pass ``cap_usd``. A callable that does not say what it costs (no ``spent_usd``) is assumed to
cost ``DEFAULT_CALL_USD`` a call, so ``cap_usd=0`` stops it at once; a stub or a metered model says so with ``spent_usd``
(a number, cumulative) and ``call_estimate_usd``. :func:`ledger_llm` meters a real model from the spend ledger.

The tools (``TOOLS``: list_kits, describe_kit, route, check_lesson) are plain functions of plain JSON, so a Claude session
or an agent loop can call them one by one; ``lessonforge kits ...`` and the MCP server are thin wrappers over them.
"""
from __future__ import annotations

import copy
import json
import math
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from .. import kits
from ..kits.base import beats_of
from ..longform import component_lib as lib
from ..longform.component_lib import SCOPE_CLASSES, scope_text   # classes 1 to 12; LESSONFORGE_SCOPE_CLASSES narrows it
#: A beat whose best kit scores below this goes to no kit (``kit=None``).
MIN_SCORE = 0.5
#: Below this a beat is "unsure": the optional model router may decide it. At or above it, code decides alone.
SURE_SCORE = 1.5
#: A part shorter than this (in words) is never sent to the model router: "Class 8." is not worth a call.
MODEL_MIN_WORDS = 4
#: Two scores this close are a tie, and ``PRIORITY`` breaks it.
TIE = 0.05
#: Higher wins a tie. A kit that is not listed has 2; the components kit is the general fallback, so lowest.
PRIORITY = {"chemistry": 3, "motion": 3, "geometry": 2, "components": 1}
#: What one model call is assumed to cost when the callable does not say (dollars). A writer call is a few cents and a
#: long lesson's can be more, so this errs high: a library caller who passes a raw paid callable without ``spent_usd``
#: (and without ``ledger_llm``) is over-counted rather than under-metered, and the cap stops it early, not late. Declare
#: ``spent_usd`` / ``call_estimate_usd`` (a stub) or use :func:`ledger_llm` (a real model) to be charged what is true.
DEFAULT_CALL_USD = 0.05
#: The first-call guess for a model metered from the spend ledger: after that call the ledger says what it really cost, so
#: this is only the opening bet (a Haiku-class call measured 0.2-0.5 cents), unlike the unmetered default above.
LEDGER_FIRST_CALL_USD = 0.005
SUBJECT_ALIASES = {"math": "maths", "mathematics": "maths", "geometry": "maths", "algebra": "maths", "bio": "biology",
                   "chem": "chemistry", "phys": "physics", "geography": "earth", "science": "physics chemistry biology earth"}

#: Words that make a single-word keyword useless on its own (they come from component descriptions, not from subjects).
NOISE = frozenset("""
    a an the and or of to in on at by for with from is are was were be been it its this that these those as but not no
    own way thing things usually whether off show name type under mode between near down up out into over about word
    learner label height pixels open clean base full level length carry test points size scale side sides
    one two three four five six seven eight nine ten has have had her his their there then than so if when what which who
    how can will may let us our we you your they them make made makes each every some any also very just more most
    """.split())

#: How much a component keyword is worth by where it came from. The id and title say what the picture IS; a situation title
#: says what it is used to show; an NCERT chapter says where it is taught; a parameter's own ``say`` line (and its parts)
#: only describe a knob, so they are the weakest evidence.
TIER_NAME, TIER_SITUATION, TIER_CHAPTER, TIER_PARAM = 1.0, 0.6, 0.5, 0.25
#: Matches from the parameter tier alone add up to at most this, which is under ``SURE_SCORE``: they can never decide alone.
WEAK_CAP = 1.0
#: Single words that appear in many components' own text but say nothing about which one a part is about. They are never a
#: component keyword by themselves (a phrase that contains them, like "number line", still is).
GENERIC = frozenset("""
    negative positive number value amount angle line time change left right point small large long short high low
    increase decrease different same another using use used shows shown draw drawn picture figure diagram through
    """.split())

#: Router-only extras: words and phrases that point to a kit but that the kit does not declare. They are data for the
#: router, not kit metadata, so no kit changes. Chemistry gets the elements and substances a Class 7-9 lesson names.
EXTRAS: dict[str, tuple[str, ...]] = {
    "chemistry": ("hydrogen", "oxygen", "nitrogen", "carbon dioxide", "water", "ammonia", "methane", "magnesium", "sodium",
                  "chlorine", "iron", "copper", "sulphur", "calcium", "burns in", "reacts with", "react", "oxide", "chloride",
                  "hydroxide", "to make water", "to form", "chemical", "rusting", "baking soda", "vinegar"),
    "motion": ("car", "train", "bus", "cyclist", "runner", "from rest", "at rest", "metres per second", "km/h", "m/s", "slow down",
               "speeding up", "brake", "braking", "travels", "moving", "velocity", "acceleration", "starts moving", "stops"),
    "geometry": ("sum of angles", "angle sum", "exterior angle", "interior angle", "vertices", "isosceles", "equilateral",
                 "scalene", "quadrilateral", "square", "sides", "bisect", "right angle", "triangle abc"),
}
#: Patterns on the raw text: (kit, regex, weight, why). A balanced-looking equation is chemistry whatever the words are.
PATTERNS: tuple[tuple[str, re.Pattern, float, str], ...] = (
    ("chemistry", re.compile(r"[A-Z][a-z]?\d*.*(?:->|\u2192|=>)"), 1.5, "an equation"),
    ("chemistry", re.compile(r"\b[A-Z][a-z]?\d+(?:[A-Z][a-z]?\d*)*\b"), 1.0, "a chemical formula"),
    ("geometry", re.compile(r"\b(?:triangle|quadrilateral|parallelogram|rhombus|trapezium|kite)\s+[A-Z]{3,4}\b", re.I), 1.0,
     "a named polygon"),
    ("motion", re.compile(r"\b\d+(?:\.\d+)?\s*(?:m/s|km/h|m/s\^?2|metres? per second)", re.I), 1.5, "a speed in units"),
)

_CLASS = re.compile(r"\b(?:class(?:es)?|grade|std)\.?\s*(\d{1,2})(?:\s*(?:-|\u2013|to|and|&)\s*(\d{1,2}))?", re.I)
_WORD = re.compile(r"[a-z0-9]+(?:/[a-z0-9]+)?")


class PipelineError(ValueError):
    """A request the pipeline cannot take, in plain words."""


class CapReached(RuntimeError):
    """A model call that would pass the spending cap was refused before it was made."""


# ---------------------------------------------------------------- reading the brief

def _stem_once(w: str) -> str:
    if w.endswith("ies") and len(w) > 5:
        return w[:-3] + "y"
    for suf in ("ing", "ed", "s"):
        if w.endswith(suf) and not w.endswith("ss") and len(w) - len(suf) >= 3:
            return w[: -len(suf)]
    if w.endswith("e") and len(w) > 4:
        return w[:-1]
    return w


def stem(word: str) -> str:
    """A crude, consistent stem (both sides of a match go through it): speeds, speed -> speed; burning, burns -> burn."""
    word = word.lower()
    for _ in range(3):
        nxt = _stem_once(word)
        if nxt == word:
            break
        word = nxt
    return word


def tokens(text: str) -> list[str]:
    return [stem(w) for w in _WORD.findall(str(text).lower())]


def classes_in(text: str) -> list[int]:
    """The NCERT classes (in scope: 1 to 12) a text names: "Class 8", "classes 7 to 9". Other numbers are ignored."""
    found: set[int] = set()
    for m in _CLASS.finditer(str(text)):
        lo = int(m.group(1))
        hi = int(m.group(2)) if m.group(2) else lo
        if lo <= hi <= 12:
            found.update(c for c in range(lo, hi + 1) if c in SCOPE_CLASSES)
    return sorted(found)


def band(classes: list[int]) -> str:
    """[7, 8, 9] -> "7-9", [6, 8] -> "6,8", [] -> ""."""
    cs = sorted(set(classes))
    if not cs:
        return ""
    if cs == list(range(cs[0], cs[-1] + 1)):
        return str(cs[0]) if len(cs) == 1 else f"{cs[0]}-{cs[-1]}"
    return ",".join(str(c) for c in cs)


_BULLET = re.compile(r"^\s*(?:[-*•]|\d{1,2}[.)])\s+")
_SENTENCE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"“])")


def split_brief(text: str) -> list[str]:
    """The parts of a brief to route: paragraphs, or the lines of a list, or (for one paragraph) its sentences.

    A heading line (``# ...``) is not a part: it is put in front of the part that follows it, as context.
    """
    parts: list[str] = []
    heading = ""
    for para in re.split(r"\n\s*\n", str(text or "").strip()):
        lines = [ln for ln in para.splitlines() if ln.strip()]
        units: list[str] = []
        if lines and all(_BULLET.match(ln) for ln in lines) and len(lines) > 1:
            units = [_BULLET.sub("", ln).strip() for ln in lines]
        else:
            units = [" ".join(ln.strip() for ln in lines)]
        for unit in units:
            if unit.startswith("#"):
                heading = unit.lstrip("# ").strip()
                continue
            parts.append((heading + ". " if heading else "") + unit)
            heading = ""
    if len(parts) == 1:
        sentences = [s.strip() for s in _SENTENCE.split(parts[0]) if s.strip()]
        if len(sentences) > 1:
            parts = sentences
    return parts


# ---------------------------------------------------------------- what can be routed to

@dataclass
class Doc:
    """One thing a beat can be routed to: a kit, or (components) one component of the catalogue."""
    kit: str
    kind: str
    subjects: tuple[str, ...]
    classes: tuple[int, ...]
    words: dict[str, str] = field(default_factory=dict)             # stem -> the keyword as written (single words)
    phrases: dict[tuple[str, ...], str] = field(default_factory=dict)
    tier: dict[Any, float] = field(default_factory=dict)            # keyword or phrase -> its tier (default 1.0, a kit's own)
    component: str = ""
    title: str = ""


def _add(doc: Doc, term: str, tier: float = 1.0, *, generic: bool = False) -> None:
    """Add a keyword (one word) or phrase (several) to ``doc``; the best tier it was ever added at is kept.

    ``generic=True`` (components) drops a single word listed in ``GENERIC`` (a phrase containing one is kept).
    """
    term = str(term).strip().lower()
    if not term:
        return
    toks = tuple(tokens(term))
    if len(toks) > 1:
        doc.phrases[toks] = term
        doc.tier[toks] = max(tier, doc.tier.get(toks, 0.0))
    elif len(toks) == 1:
        word = toks[0]
        if (term in NOISE or word in NOISE or len(term) < 3) and not any(ch.isdigit() or ch == "/" for ch in term):
            return
        if generic and (term in GENERIC or word in GENERIC):
            return
        doc.words[word] = term
        doc.tier[word] = max(tier, doc.tier.get(word, 0.0))


def _add_text(doc: Doc, text: str, tier: float) -> None:
    """The words of a sentence-like text as keywords at ``tier``, and each pair of neighbouring content words as a phrase."""
    raw = [w for w in _WORD.findall(str(text).lower()) if len(w) > 1 and not w.isdigit()]     # no "s" from "ohm's", no "3"
    for w in raw:
        _add(doc, w, tier, generic=True)
    for a, b in zip(raw, raw[1:]):
        if not ({a, stem(a)} & NOISE or {b, stem(b)} & NOISE) and a not in GENERIC | NOISE:
            _add(doc, f"{a} {b}", tier)


def _ncert_text(line: str) -> str:
    """"Class 7, Ch 1 Nutrition in Plants (stomata)" -> "Nutrition in Plants stomata": the topic words of an NCERT string."""
    text = re.sub(r"^\s*(?:Any\s+class(?:es)?|Class(?:es)?)\b(?:\s|\d|,|-|\u2013|\bto\b)*(?:Ch(?:apter)?\s*\d+)?", " ", str(line), flags=re.I)
    return re.sub(r"\b(?:Fig|Figure|Table|Activity|Ch|Chapter)\.?\s*[\d.]+", " ", text).replace("(", " ").replace(")", " ")


def _component_doc(entry: dict) -> Doc:
    """One routing target from one catalogue entry. Everything comes from the entry (id, title, situation titles, NCERT
    strings, parameters, parts, named states), so a new ``components/<subject>/<id>.ts`` is routable with no code change."""
    subject = str(entry["subject"]).lower()
    title = str(entry.get("title") or entry["id"])
    doc = Doc("components", "component", (subject,), tuple(c for c in entry["classes"] if c in SCOPE_CLASSES),
              component=entry["id"], title=title)
    _add(doc, entry["id"].replace("_", " "), TIER_NAME, generic=True)       # one word id ("clock") or the whole id as a phrase
    for w in entry["id"].split("_"):
        _add(doc, w, TIER_NAME, generic=True)
    _add_text(doc, title, TIER_NAME)
    for sit in entry.get("situations") or []:
        _add_text(doc, str(sit.get("title") or ""), TIER_SITUATION)
        if sit.get("ncert") and not isinstance(sit.get("ncert"), (int, float)):
            _add_text(doc, _ncert_text(str(sit["ncert"])), TIER_CHAPTER)
    for line in entry.get("ncert") or []:
        _add_text(doc, _ncert_text(line), TIER_CHAPTER)
    for p in entry.get("params") or []:
        _add_text(doc, str(p.get("name", "")).replace("_", " ") + " " + str(p.get("say", "")), TIER_PARAM)
    for part in entry.get("parts") or []:
        _add_text(doc, str(part).replace("_", " "), TIER_PARAM)
    for name in entry.get("states") or {}:
        _add_text(doc, str(name).replace("_", " "), TIER_PARAM)
    doc.words.pop(stem(subject), None)       # the subject word alone ("physics") is the subject filter's job, not evidence
    return doc


def _components(log: Callable[[str], Any] = lambda *_: None) -> list[dict]:
    """The component catalogue (the classes in scope), or [] when the kit or Node is not there."""
    comp = kits.get("components")
    if comp is None or not kits.enabled():
        return []
    try:
        from ..kits import components as C
        return list(C.catalogue())
    except Exception as exc:  # noqa: BLE001 - a catalogue that cannot be read is "no component", not a failure
        log(f"[kit-pipeline] component catalogue not read ({type(exc).__name__}: {str(exc)[:100]})")
        return []


def docs(log: Callable[[str], Any] = lambda *_: None) -> list[Doc]:
    """Every routing target: each registered kit from ``kits.describe()``, the components kit as one doc per component."""
    out: list[Doc] = []
    for row in kits.describe():
        name = row["name"]
        if name == "components":
            for entry in _components(log):
                doc = _component_doc(entry)
                if doc.classes:
                    out.append(doc)
            continue
        if not row["figure_kinds"]:
            continue
        doc = Doc(name, row["figure_kinds"][0], tuple(s.lower() for s in row["subjects"]),
                  tuple(c for c in row["classes"] if c in SCOPE_CLASSES) or SCOPE_CLASSES)
        for kw in list(row["keywords"]) + list(EXTRAS.get(name, ())):
            _add(doc, kw)
        out.append(doc)
    return out


def _subjects_wanted(subjects) -> set[str] | None:
    if not subjects:
        return None
    wanted: set[str] = set()
    raw = [subjects] if isinstance(subjects, str) else list(subjects)
    for s in raw:
        for piece in re.split(r"[\s,]+", str(s).lower()):
            if piece:
                wanted.update(SUBJECT_ALIASES.get(piece, piece).split())
    return wanted


def _classes_wanted(classes) -> list[int]:
    if classes is None or classes == "" or classes == []:
        return list(SCOPE_CLASSES)
    raw = [classes] if isinstance(classes, (int, str)) else list(classes)
    out: list[int] = []
    for c in raw:
        for piece in re.split(r"[\s,]+", str(c)):
            if not piece:
                continue
            try:
                n = int(piece)
            except ValueError as exc:
                raise PipelineError(f"classes must be numbers like 7,8 (got {piece!r})") from exc
            if n not in SCOPE_CLASSES:
                raise PipelineError(f"class {n} is outside {scope_text()} (NCERT), the scope of the kits")
            out.append(n)
    return sorted(set(out))


def _weights(pool: list[Doc]) -> dict[Any, float]:
    """A keyword shared by many targets says little: weight 1/sqrt(how many targets list it)."""
    count: dict[Any, int] = {}
    for d in pool:
        for key in list(d.words) + list(d.phrases):
            count[key] = count.get(key, 0) + 1
    return {key: 1.0 / math.sqrt(n) for key, n in count.items()}


def _score(doc: Doc, toks: list[str], raw: str, weight: dict[Any, float]) -> tuple[float, list[str]]:
    """How well ``doc`` fits ``toks``: each matched keyword is worth ``weight`` (rarer is more) x its tier. What only the
    weakest tier matched (a parameter's own ``say`` words) counts at most ``WEAK_CAP``, so it never decides alone."""
    score, weak, why = 0.0, 0.0, []
    have = set(toks)
    for key, shown in doc.phrases.items():
        n = len(key)
        if any(tuple(toks[i:i + n]) == key for i in range(len(toks) - n + 1)):
            tier = doc.tier.get(key, 1.0)
            part = 0.8 * n * weight.get(key, 1.0) * tier
            if tier <= TIER_PARAM:
                weak += part
            else:
                score += part
            why.append(shown if tier >= TIER_NAME else f"{shown} ({_TIER_NAMES.get(tier, 'weak')})")
    for key, shown in doc.words.items():
        if key in have:
            tier = doc.tier.get(key, 1.0)
            part = weight.get(key, 1.0) * tier
            if tier <= TIER_PARAM:
                weak += part
            else:
                score += part
            why.append(shown if tier >= TIER_NAME else f"{shown} ({_TIER_NAMES.get(tier, 'weak')})")
    for kit, rx, w, label in PATTERNS:
        if kit == doc.kit and rx.search(raw):
            score += w
            why.append(label)
    return score + min(weak, WEAK_CAP), why


_TIER_NAMES = {TIER_SITUATION: "situation", TIER_CHAPTER: "chapter", TIER_PARAM: "parameter"}


# ---------------------------------------------------------------- the plan

@dataclass
class Plan:
    beats: list[dict]
    classes: list[int]
    subjects: list[str] | None = None
    notes: list[str] = field(default_factory=list)

    def kit_names(self) -> list[str]:
        return list(dict.fromkeys(b["kit"] for b in self.beats if b.get("kit")))

    def component_ids(self) -> list[str]:
        return list(dict.fromkeys(b["component"] for b in self.beats if b.get("component")))

    @property
    def mixed(self) -> bool:
        return len(self.kit_names()) > 1

    def to_dict(self) -> dict:
        return {"beats": self.beats, "kits": self.kit_names(), "components": self.component_ids(), "mixed": self.mixed,
                "classes": self.classes, "subjects": self.subjects, "notes": self.notes}


def _excerpt(text: str, n: int = 110) -> str:
    text = " ".join(str(text).split())
    return text if len(text) <= n else text[: n - 1].rstrip() + "…"


def _item(i: int, text: str, doc: Doc | None, score: float, why: list[str], others: list[tuple[float, Doc]],
          classes: list[int], by: str) -> dict:
    return {"beat": i, "text": _excerpt(text), "kit": doc.kit if doc else None, "kind": doc.kind if doc else None,
            "component": (doc.component or None) if doc else None,
            "subject": (doc.subjects[0] if doc and doc.subjects else None),
            "class_band": band([c for c in doc.classes if c in classes]) if doc else "",
            "score": round(score, 3), "why": why[:8], "by": by if doc else "none",
            "alternatives": [{"kit": d.kit, "component": d.component or None, "score": round(s, 3)} for s, d in others[:2]]}


def route(brief_text: str, classes=None, subjects=None, beats: list[str] | None = None, *, llm=None,
          log: Callable[[str], Any] = lambda *_: None) -> Plan:
    """Give each part of a brief to a kit, by code. See the module docstring.

    ``classes`` (e.g. ``[7, 8]``) keeps only the kits and components that serve one of those classes; given none, the
    classes the brief names ("Class 8") are used, else every class in scope. ``subjects`` likewise. ``beats`` are the parts to route
    (default: the brief split by :func:`split_brief`). ``llm`` (a callable, ideally a :class:`Meter`) is asked only about
    the parts code scored below ``SURE_SCORE``, and what it answers is checked before it is believed.
    """
    notes: list[str] = []
    wanted = _classes_wanted(classes)
    if classes in (None, "", []):
        named = classes_in(brief_text)
        if named:
            wanted = named
            notes.append(f"classes {band(named)} read from the brief")
    subs = _subjects_wanted(subjects)
    parts = [str(b) for b in beats] if beats else split_brief(brief_text)
    if not kits.enabled():
        notes.append("the kits are switched off (LESSONFORGE_KITS=0): every beat is routed to none")
    pool = [d for d in docs(log) if set(d.classes) & set(wanted) and (subs is None or set(d.subjects) & subs)] \
        if kits.enabled() else []
    weight = _weights(pool)
    items: list[dict] = []
    for i, text in enumerate(parts, start=1):
        toks = tokens(text)
        scored = sorted(((s, d, w) for d in pool for s, w in [_score(d, toks, text, weight)] if s > 0),
                        key=lambda t: (-t[0], -PRIORITY.get(t[1].kit, 2), t[1].kit, t[1].component))
        if scored:      # a tie within TIE goes to the higher priority
            top = scored[0][0]
            close = [t for t in scored if top - t[0] <= TIE]
            close.sort(key=lambda t: (-PRIORITY.get(t[1].kit, 2), -t[0], t[1].kit, t[1].component))
            scored = close + [t for t in scored if t not in close]
        best = scored[0] if scored and scored[0][0] >= MIN_SCORE else None
        others = [(s, d) for s, d, _ in scored[1:] if best is None or (d.kit, d.component) != (best[1].kit, best[1].component)]
        items.append(_item(i, text, best[1] if best else None, best[0] if best else (scored[0][0] if scored else 0.0),
                           best[2] if best else [], others, wanted, "code"))
    plan = Plan(items, wanted, sorted(subs) if subs else None, notes)
    if llm is not None and kits.enabled():
        _ask_model(plan, parts, pool, llm, log)
    return plan


# ---------------------------------------------------------------- the optional model router

ROUTER_SYSTEM = ("You route the parts of a school lesson brief to drawing kits. Choose only from the kits and components "
                 "listed; answer null when none fits. You never invent a kit or a component, and you never decide a number: "
                 "the kit's code does. Maintain visual and apparatus continuity: parts explaining the same demonstration or "
                 "activity belong to the same kit/component. Answer JSON only.")


def _router_prompt(unsure: list[dict], pool: list[Doc], topic: str = "", context_kits: list[str] | None = None) -> str:
    kits_seen: dict[str, str] = {}
    for d in pool:
        if d.component:
            kits_seen["components"] = "components (ids: " + ", ".join(sorted({x.component + " = " + x.title for x in pool if x.component})) + ")"
        else:
            kits_seen[d.kit] = f"{d.kit}: draws {d.kind}; subjects {', '.join(d.subjects)}; classes {band(list(d.classes))}"
    listing = "\n".join(f"- {v}" for v in kits_seen.values())
    asked = "\n".join(f"{b['beat']}. {b['text']}" for b in unsure)
    context = f"LESSON TOPIC: {topic}\n\n" if topic else ""
    if context_kits:
        context += f"ESTABLISHED KITS FOR THIS LESSON: {', '.join(context_kits)} (prefer continuing with the established kit for parts of the same demonstration).\n\n"
    return (f"{context}KITS YOU MAY CHOOSE FROM:\n{listing}\n\nPARTS TO ROUTE (code was not sure about them):\n{asked}\n\n"
            'Answer {"routes": [{"beat": number, "kit": "a kit name or null", "component": "a component id when the kit is '
            'components, else null", "why": "five words"}]}')


def _ask_model(plan: Plan, parts: list[str], pool: list[Doc], llm, log) -> None:
    """Let the model decide the unsure beats. Its answer is validated; anything invalid leaves the code's choice."""
    unsure = [b for b in plan.beats if b["score"] < SURE_SCORE and len(tokens(parts[b["beat"] - 1])) >= MODEL_MIN_WORDS]
    if not unsure or not pool:
        return
    try:
        topic = parts[0] if parts else ""
        established = list(dict.fromkeys((b.get("component") or b.get("kit")) for b in plan.beats if b.get("kit") and b["score"] >= SURE_SCORE))
        answer = llm(_router_prompt(unsure, pool, topic=topic, context_kits=established), ROUTER_SYSTEM)
    except CapReached as exc:
        plan.notes.append(f"model router not asked: {exc}")
        return
    except Exception as exc:  # noqa: BLE001 - the code router's plan stands
        plan.notes.append(f"model router failed ({type(exc).__name__}): the code router's choices stand")
        log(f"[kit-pipeline] model router failed ({type(exc).__name__})")
        return
    rows = answer.get("routes") if isinstance(answer, dict) else None
    if not isinstance(rows, list):
        plan.notes.append("model router answered in no usable shape: the code router's choices stand")
        return
    by_beat = {b["beat"]: b for b in unsure}
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("beat"), int) or row["beat"] not in by_beat:
            continue
        name, comp = row.get("kit"), row.get("component")
        if not name or name == "null":
            continue
        choice = None
        if name == "components":
            choice = next((d for d in pool if d.component and d.component == str(comp)), None)
            if choice is None:
                plan.notes.append(f"model router named a component that does not exist ({str(comp)[:40]!r}): ignored")
        else:
            choice = next((d for d in pool if d.kit == name and not d.component), None)
            if choice is None:
                plan.notes.append(f"model router named a kit that is not registered or not in scope ({str(name)[:40]!r}): ignored")
        if choice is None:
            continue
        b = by_beat[row["beat"]]
        b.update({"kit": choice.kit, "kind": choice.kind, "component": choice.component or None,
                  "subject": choice.subjects[0] if choice.subjects else None,
                  "class_band": band([c for c in choice.classes if c in plan.classes]), "by": "model",
                  "why": ["model: " + _excerpt(str(row.get("why") or "chosen"), 50)]})


# ---------------------------------------------------------------- the plan as a brief

def _hint(b: dict) -> str:
    text = _excerpt(b["text"], 80)
    if not b.get("kit"):
        return f"part {b['beat']} \"{text}\": no kit figure fits (a plain figure, or none; never an invented number)"
    what = f"figure kind {b['kind']} (kit {b['kit']}" + (f", component id {b['component']}" if b.get("component") else "") + ")"
    if b.get("component"):
        try:
            entry = lib.get(b["component"])
            b_text = str(b.get("text", "")).lower()
            for sit in entry.get("situations", []):
                sname = sit.get("name", "").lower()
                stitle = sit.get("title", "").lower()
                if sname in b_text or any(w in b_text for w in stitle.split() if len(w) > 4):
                    sparams = sit.get("params", {})
                    states = [s.get("state") for s in sit.get("steps", []) if s.get("state")]
                    state_note = ""
                    if states and any("unfold" in st for st in states if isinstance(st, dict)):
                        state_note = "; advance state unfold from 0 to 0.5 to 1 across beats"
                    what += f" [set-up {sit['name']}: params {json.dumps(sparams)}{state_note}]"
                    break
        except Exception:
            pass
    return f"part {b['beat']} \"{text}\": {what}"


def plan_to_brief(plan: Plan, brief: dict | None = None) -> dict:
    """``brief`` with ``kits`` (the kits the plan uses, plus any it already named) and ``kit_hints`` (one line per part).

    ``brief["kits"]`` is what ``writer.write_lesson`` turns into the per-lesson rules addendum, so a kit that no part
    needs adds nothing to the prompt; several kits get the mixed-lesson opening. Components are named with their ids
    (``components:force_block``) so the writer gets the full sheet of those components. The input is not changed.
    """
    out = dict(brief or {})
    named = out.get("kits") or []
    named = [named] if isinstance(named, str) else list(named)
    ids = plan.component_ids()
    names = list(dict.fromkeys(n.partition(":")[0] for n in named))
    for n in plan.kit_names():
        if n not in names:
            names.append(n)
    out["kits"] = [("components:" + ",".join(ids)) if n == "components" and ids else n for n in names]
    out["kit_hints"] = [_hint(b) for b in plan.beats]
    if not names:
        out.pop("kits")
    return out


def brief_from_text(text: str, plan: Plan | None = None, **over) -> dict:
    """A writer brief from free text: the first line is the topic, the classes and subjects come from the plan."""
    lines = [ln.strip("# ").strip() for ln in str(text or "").strip().splitlines() if ln.strip()]
    topic = _excerpt(lines[0] if lines else "a lesson", 90)
    classes = plan.classes if plan else list(SCOPE_CLASSES)
    subjects = sorted({b["subject"] for b in (plan.beats if plan else []) if b.get("subject")})
    brief = {"topic": topic, "audience": f"Class {band(classes)} students", "level": "standard",
             "goal": f"understand {topic}", "style": "tutor", "language": "en-IN", "framework": "worked_examples",
             "duration_minutes": 6, "context": "", "notes": {"brief": _excerpt(" ".join(lines), 1200)}}
    for ln in lines:
        lower = ln.lower()
        if lower.startswith(("duration:", "duration_minutes:")):
            m = re.search(r"\d+", ln)
            if m:
                brief["duration_minutes"] = int(m.group(0))
        elif lower.startswith("framework:"):
            brief["framework"] = ln.split(":", 1)[1].strip()
        elif lower.startswith("goal:"):
            brief["goal"] = ln.split(":", 1)[1].strip()
    if subjects:
        brief["subject"] = " and ".join(subjects)
    brief.update(over)
    return brief


# ---------------------------------------------------------------- the money

class Meter:
    """A model callable with a hard dollar cap, checked BEFORE every call.

    What a call costs is read from the callable when it says (``spent_usd``, cumulative dollars; ``call_estimate_usd``, the
    first call's guess) and otherwise assumed to be ``DEFAULT_CALL_USD``. The next call is refused (:class:`CapReached`)
    when the dollars spent plus the last call's cost (by 1.3, the improver's margin), or the estimate before any call,
    would pass ``cap_usd``. So ``cap_usd=0`` refuses any model that is not declared free.
    """

    def __init__(self, llm: Callable, cap_usd: float, log: Callable[[str], Any] = lambda *_: None):
        self.llm, self.cap, self.log = llm, float(cap_usd or 0.0), log
        self.metered = hasattr(llm, "spent_usd")
        self._base = float(getattr(llm, "spent_usd", 0.0) or 0.0)
        self.estimate = float(getattr(llm, "call_estimate_usd", DEFAULT_CALL_USD))
        self.spent, self.calls, self.refusals = 0.0, 0, 0
        self.last: float | None = None

    def guess(self) -> float:
        return self.last * 1.3 if self.last is not None else self.estimate

    def can_call(self) -> bool:
        return self.spent + self.guess() <= self.cap + 1e-9

    def __call__(self, prompt: str, system: str):
        if not self.can_call():
            self.refusals += 1
            raise CapReached(f"the next call (about ${self.guess():.3f}) would pass the cap (${self.cap:.2f}, spent ${self.spent:.3f})")
        before = self.spent
        try:
            return self.llm(prompt, system)
        finally:
            self.calls += 1
            if self.metered:
                self.spent = max(self.spent, float(getattr(self.llm, "spent_usd", 0.0) or 0.0) - self._base)
            else:
                self.spent += self.estimate
            self.last = self.spent - before


def ledger_llm(llm: Callable) -> Callable:
    """``llm`` metered from the spend ledger (``spend.spent()``): what it costs is what the ledger grew by."""
    from .. import spend

    class Ledgered:
        call_estimate_usd = LEDGER_FIRST_CALL_USD

        def __init__(self):
            self._start = float(spend.spent() or 0.0)

        @property
        def spent_usd(self) -> float:
            return float(spend.spent() or 0.0) - self._start

        def __call__(self, prompt, system):
            return llm(prompt, system)

    return Ledgered()


# ---------------------------------------------------------------- the report and its trace

@dataclass
class Report:
    plan: dict
    lesson_id: str | None = None
    faults: list[str] = field(default_factory=list)
    craft: dict = field(default_factory=dict)
    spend: dict = field(default_factory=dict)
    steps: list[dict] = field(default_factory=list)
    brief: dict = field(default_factory=dict)
    preview: dict | None = None
    film: dict | None = None

    def to_dict(self) -> dict:
        return {"plan": self.plan, "lesson_id": self.lesson_id, "faults": self.faults, "craft": self.craft,
                "spend": self.spend, "steps": self.steps, "brief": self.brief, "preview": self.preview, "film": self.film}


class _Trace:
    def __init__(self, log):
        self.steps: list[dict] = []
        self.log, self._t0 = log, time.time()

    def add(self, name: str, ok: bool, what: str, **extra) -> dict:
        row = {"n": len(self.steps) + 1, "step": name, "ok": ok, "what": what, "seconds": round(time.time() - self._t0, 2), **extra}
        self.steps.append(row)
        self.log(f"[kit-pipeline] {name}: {'ok' if ok else 'NOT ok'} - {what}")
        return row


def _load_lesson(lesson) -> dict:
    if isinstance(lesson, dict):
        return copy.deepcopy(lesson)
    text = str(lesson)
    if text.lstrip().startswith("{"):
        return json.loads(text)
    return json.loads(Path(text).read_text(encoding="utf-8"))


QUIZ_LEAK = "quiz leak: "


def quiz_leak_faults(settled: dict) -> list[str]:
    """A quiz whose answer is said or written before the question is a fault HERE (video-quality plan S4): the pipeline
    refuses to film it. Elsewhere (``writer.quiz_leaks``) it is a note on the lesson. A motion graph's own mark is not one:
    the writer pass holds it back when the lesson is made. ``HARNESS_QUIZ_LEAKS=0`` turns the check off."""
    from .. import knobs
    from . import quiz_leaks
    if str(knobs.get("HARNESS_QUIZ_LEAKS", "1")).strip() == "0":
        return []
    try:
        return [QUIZ_LEAK + quiz_leaks.describe(f) for f in quiz_leaks.find(settled) if f["kind"] != "figure"]
    except Exception:  # noqa: BLE001 - a lint that cannot read a lesson says nothing
        return []


def settled_faults(lesson: dict) -> tuple[dict, list[str]]:
    """``lesson`` settled as the workbench settles it (every kit's gaps filled), and every fault code finds in it."""
    from . import workbench as W
    try:
        settled = W._settled(W._normalise(copy.deepcopy(lesson)))
        return settled, W.faults_of(settled) + quiz_leak_faults(settled)
    except Exception as exc:  # noqa: BLE001 - a lesson too broken to settle is one fault, in words
        return lesson, [f"lesson contract: {type(exc).__name__}: {str(exc)[:300]}"]


def _repair_prompt(lesson: dict, faults: list[str], log) -> str:
    text = kits.repair_prompt(lesson, faults, log=log)
    if text:
        return text
    if lesson.get("shapes") or any(isinstance((b.get("figure") or {}), dict) and (b.get("figure") or {}).get("kind") == "shape"
                                   for c in lesson.get("chapters") or [] for b in c.get("beats") or [] if isinstance(b, dict)):
        from . import shapes
        return shapes.repair_prompt(lesson, faults)
    return ("Code checked your lesson and found these faults:\n" + "\n".join(f"- {f}" for f in faults[:40])
            + "\n\nReturn the WHOLE lesson again as JSON in the same shape, with every fault fixed. Change only what a fault "
              "needs. Keep every other word as it is.\n\nYOUR LESSON:\n" + json.dumps(lesson, ensure_ascii=False))


def run(brief_text: str, llm=None, cap_usd: float = 0.0, film: bool = False, rounds: int = 2, *, lesson=None, classes=None,
        subjects=None, preview: bool = False, brief: dict | None = None, name: str | None = None, model_router: bool = True,
        voice: str | None = None, log: Callable[[str], Any] = lambda *_: None) -> Report:
    """route -> brief -> write -> settle and check every kit -> repair (bounded) -> workbench -> look -> film.

    ``llm=None`` is free only: nothing calls a model, a ready ``lesson=`` (dict, JSON text or file path) is checked
    and put on the workbench, and without one the report says no lesson was written. With ``llm`` every call goes through
    a :class:`Meter` that stops at ``cap_usd`` (a lesson written under the cap or not at all; a repair that would pass it
    is not asked for). ``rounds`` bounds the repair loop, which stops at the first round that does not lower the fault
    count. ``preview`` makes the stills (free, a minute of CPU); ``film`` films with the free local voice, only when no
    fault is left. Never raises for a request that cannot go on: the report's steps say what stopped it.
    """
    from . import workbench as W
    trace = _Trace(log)
    meter = Meter(llm, cap_usd, log) if llm is not None else None
    try:
        plan = route(brief_text, classes, subjects, llm=meter if (meter and model_router) else None, log=log)
    except PipelineError as exc:
        trace.add("route", False, str(exc))
        return Report({"beats": [], "kits": [], "notes": [str(exc)]}, steps=trace.steps, spend=_spend(meter, cap_usd))
    used = ", ".join(plan.kit_names()) or "none"
    trace.add("route", True, f"{len(plan.beats)} part(s): kits {used}" + (" (mixed)" if plan.mixed else "")
              + (f"; {sum(1 for b in plan.beats if b['by'] == 'model')} decided by the model" if meter else ""),
              kits=plan.kit_names(), unrouted=[b["beat"] for b in plan.beats if not b["kit"]])
    wbrief = plan_to_brief(plan, brief_from_text(brief_text, plan, **(brief or {})))
    trace.add("brief", True, "brief['kits'] = " + json.dumps(wbrief.get("kits", [])) + f", {len(wbrief['kit_hints'])} hint(s)")
    report = Report(plan.to_dict(), brief=wbrief, steps=trace.steps)
    system = ""
    if meter is not None or lesson is None:
        from . import writer
        system = writer.SYSTEM + kits.rules_for(wbrief.get("kits"), log=log)

    # -- the lesson: given, or written by the model under the cap
    if lesson is not None:
        try:
            work = _load_lesson(lesson)
            trace.add("lesson", True, "a ready lesson was given: " + str(work.get("title") or "untitled")[:60])
        except Exception as exc:  # noqa: BLE001
            trace.add("lesson", False, f"the given lesson could not be read ({type(exc).__name__}: {str(exc)[:120]})")
            report.spend = _spend(meter, cap_usd)
            return report
    elif meter is None:
        trace.add("write", False, "skipped: no model was given (free only) and no ready lesson; give lesson= or a model with a cap")
        report.spend = _spend(meter, cap_usd)
        return report
    elif not meter.can_call():
        meter.refusals += 1                 # refused here, before any call was made: still a refusal in spend.refused
        trace.add("write", False, f"refused before calling the model: its first call (about ${meter.guess():.3f}) would pass the "
                                  f"cap (${meter.cap:.2f})", usd=0.0)
        report.spend = _spend(meter, cap_usd)
        return report
    else:
        from . import writer
        try:
            work = writer.write_lesson(wbrief, meter, log=log)
            trace.add("write", True, f"{meter.calls} model call(s), ${meter.spent:.4f}", usd=round(meter.spent, 4))
        except CapReached as exc:
            trace.add("write", False, f"stopped by the cap: {exc}", usd=round(meter.spent, 4))
            report.spend = _spend(meter, cap_usd)
            return report
        except Exception as exc:  # noqa: BLE001 - a model that failed is a report, not a crash
            trace.add("write", False, f"the writer failed ({type(exc).__name__}: {str(exc)[:160]})", usd=round(meter.spent, 4))
            report.spend = _spend(meter, cap_usd)
            return report

    # -- settle every kit's beats, check, repair
    served = kits.subject_kits(work)
    settled, faults = settled_faults(work)
    trace.add("check", not faults, f"kits {', '.join(k.name for k in served) or 'none'}: {len(faults)} fault(s) after settling the gaps",
              faults=len(faults), kits=[k.name for k in served])
    for r in range(1, max(0, int(rounds)) + 1):
        if not faults:
            break
        if meter is None:
            trace.add("repair", False, f"round {r} skipped: no model was given (free only); {len(faults)} fault(s) remain")
            break
        if not meter.can_call():
            meter.refusals += 1
            trace.add("repair", False, f"round {r} refused before calling the model: about ${meter.guess():.3f} would pass the "
                                       f"cap (${meter.cap:.2f}, spent ${meter.spent:.3f})", usd=round(meter.spent, 4))
            break
        try:
            again = meter(_repair_prompt(work, faults, log), system)
        except Exception as exc:  # noqa: BLE001
            trace.add("repair", False, f"round {r}: the model call failed ({type(exc).__name__}: {str(exc)[:120]})")
            break
        if not isinstance(again, dict) or not again.get("chapters"):
            trace.add("repair", False, f"round {r}: the model answered with no lesson; the draft stands")
            break
        s2, f2 = settled_faults(again)
        if len(f2) < len(faults):
            trace.add("repair", True, f"round {r}: {len(faults)} -> {len(f2)} fault(s)", faults=len(f2), usd=round(meter.spent, 4))
            work, settled, faults = {**work, **again, "chapters": again["chapters"]}, s2, f2
        else:
            trace.add("repair", False, f"round {r}: no gain ({len(faults)} -> {len(f2)}); stopped, the draft stands")
            break

    # -- the workbench
    try:
        added = W.add(work, name or wbrief["topic"], source="kit pipeline")
        report.lesson_id, report.faults, report.craft = added["lesson_id"], added["faults"], added["craft"]
        report.faults = list(report.faults) + [f for f in faults if f.startswith(QUIZ_LEAK) and f not in report.faults]
        trace.add("workbench", True, f"lesson {added['lesson_id']}: {len(added['faults'])} fault(s) left", lesson_id=added["lesson_id"])
    except Exception as exc:  # noqa: BLE001
        report.faults = faults
        trace.add("workbench", False, f"not put on the workbench ({type(exc).__name__}: {str(exc)[:160]})")
        report.spend = _spend(meter, cap_usd)
        return report
    if preview:
        try:
            report.preview = W.preview(report.lesson_id, log=log)
            trace.add("preview", True, f"{report.preview['stills']} still(s), {len(report.preview['findings'])} finding(s)",
                      sheet=report.preview.get("sheet"))
        except Exception as exc:  # noqa: BLE001
            trace.add("preview", False, f"no stills ({type(exc).__name__}: {str(exc)[:120]})")
    if film:
        if report.faults:
            trace.add("film", False, f"refused: {len(report.faults)} fault(s) left; a lesson is filmed once check finds none")
        else:
            try:
                report.film = W.film(report.lesson_id, **({"voice": voice} if voice else {}), log=log)
                trace.add("film", report.film.get("status") == "done" or bool(report.film.get("video")),
                          f"status {report.film.get('status')}", video=report.film.get("video"))
            except Exception as exc:  # noqa: BLE001
                trace.add("film", False, f"not filmed ({type(exc).__name__}: {str(exc)[:160]})")
    report.spend = _spend(meter, cap_usd)
    return report


def _spend(meter: Meter | None, cap_usd: float) -> dict:
    if meter is None:
        return {"usd": 0.0, "cap_usd": float(cap_usd or 0.0), "calls": 0, "refused": 0, "model": False}
    return {"usd": round(meter.spent, 5), "cap_usd": meter.cap, "calls": meter.calls, "refused": meter.refusals,
            "model": True, "metered": meter.metered}


# ---------------------------------------------------------------- the tools (plain functions of plain JSON)

def list_kits() -> dict:
    """Every kit: what it draws, who it is for, whether it is served, and the components the library offers."""
    out: dict[str, Any] = {"enabled": kits.enabled(), "mixed_lessons": kits.mixed_enabled(), "kits": kits.describe(),
                           "components": [], "components_unavailable": None}
    try:
        from ..kits import components as C
        out["components_unavailable"] = None if kits.get("components") else (C.unavailable_reason() or "not registered")
        out["components"] = [{"id": e["id"], "title": e["title"], "subject": e["subject"], "classes": e["classes"]}
                             for e in _components()]
    except Exception as exc:  # noqa: BLE001
        out["components_unavailable"] = f"{type(exc).__name__}: {str(exc)[:100]}"
    return out


def describe_kit(name: str) -> dict:
    """One kit in full: its row, the rules the writer is given for it, and example figures from the cases it ships."""
    kit = kits.get(str(name))
    if kit is None:
        raise PipelineError(f"no kit {name!r}; the kits are: {', '.join(k.name for k in kits.all_kits())}")
    row = next(r for r in kits.describe() if r["name"] == kit.name)
    examples: list[dict] = []
    try:
        for lesson in kit.cases().good:
            for _, beat in beats_of(lesson):
                fig = beat.get("figure")
                if isinstance(fig, dict) and fig.get("kind") in kit.figure_kinds and fig not in examples:
                    examples.append(fig)
    except Exception:  # noqa: BLE001 - examples are a courtesy
        pass
    out = {**row, "rules": "" if row["legacy"] else str(kit.rules), "mcp_note": str(getattr(kit, "mcp_note", "") or ""),
           "example_figures": examples[:3]}
    if kit.name == "components":
        out["catalogue"] = [{k: e[k] for k in ("id", "title", "subject", "classes", "parts", "states") if k in e}
                            for e in _components()]
    if row["legacy"]:
        out["note"] = "legacy: the pre-kit geometry code draws and checks it; its rules are already in the writer's prompt"
    return out


def route_text(text: str, classes=None, subjects=None) -> dict:
    """Route a brief by code (free). The plan as JSON."""
    return route(text, classes, subjects).to_dict()


def check_lesson(lesson) -> dict:
    """Free. Faults and craft numbers for a lesson (JSON, a file path, or a workbench lesson id). Nothing is saved."""
    from . import workbench as W
    if isinstance(lesson, str) and not lesson.lstrip().startswith("{") and not Path(lesson).is_file():
        return W.check(lesson)
    work = _load_lesson(lesson)
    settled, faults = settled_faults(work)
    try:
        craft = W.craft(settled)
    except Exception:  # noqa: BLE001
        craft = {}
    return {"faults": faults, "craft": craft, "kits": [k.name for k in kits.subject_kits(settled)]}


TOOLS: dict[str, Callable] = {"list_kits": list_kits, "describe_kit": describe_kit, "route": route_text,
                              "check_lesson": check_lesson}
