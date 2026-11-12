"""The components kit: lesson-visuals figure components (physics, chemistry, biology, earth, characters, anything the
owner adds) as a subject kit.

A component is one TypeScript file in the lesson-visuals repo, ``components/<subject>/<id>.ts``: ``meta``,
``validate(params)`` and ``draw(params, state)`` (contract: ``components/README.md`` there). The chain a kit supplies:

* MODEL    ``longform/component_lib.py`` (pure, stdlib) runs the component through Node (one short, read-only process per
           batch, results cached by the file's content): the catalogue, the parameters checked against ``meta`` and the
           component's own ``validate``, and the drawing. A new file is found at the next call, with no registration.
* FIGURE   ``{"kind": "component", "params": {"id": "force_block", "params": {"applied_force": 30},
           "state": {"motion": "sliding_right"}}}`` is drawn by ``longform/component_figure.py`` (Manim side): the
           component's SVG parts, revealed one by one in ``meta.parts`` order under the voice.
* GAPS     ``{param applied_force}`` is the value of a validated number parameter, filled by code.
* CLAIMS   none. The component cannot back a claim about what its picture does, and the kit does not invent one. The
           only checks on words are the part names a step's ``focus`` may use (they must be parts of the component, and
           must draw something in this state) and the numbers.
* NUMBERS  a typed number on a component beat must be a number parameter, a number the component's own labels show
           (``net force 15 N``) or a filled gap; any other is stray. Text parameters take no digits.
* RULES    generated from the catalogue (``rules`` lists the components in scope; ``rules_with("a,b")`` gives the full
           sheet of the components a brief names), shipped only through ``brief["kits"]``, never in a built-in prompt.

Code, not a model, decides every fact on screen: the writer picks an id, parameters from the component's closed lists and
ranges, a state and the order of the parts. Every number and word on the picture comes from the component's ``draw``.

The kit is registered only when Node (22.6+) and the components folder are there; otherwise the registry skips it with ONE
log line and nothing else changes. The folder is ``LESSON_VISUALS_DIR`` (default ``/home/mani/lesson-visuals``).
Scope is NCERT classes 1 to 12 (LESSONFORGE_SCOPE_CLASSES narrows it): a component that serves only other classes is refused.

Nothing here imports manim, numpy or ``lessonforge.harness``.
"""
from __future__ import annotations

import copy
import hashlib
import json
import logging
import re
from typing import Any, Mapping

from .. import knobs
from ..longform import component_lib as lib
from ..longform.component_lib import (SCOPE_CLASSES, ComponentError, available, broken, catalogue, chapters_of, classes_of,
                                      components_dir, draw, get, ids, unavailable_reason, validate, visuals_dir)
from .base import GAP, KitBase, KitCases, KitError, Lesson, beats_of
from .registry import register

log = logging.getLogger("lessonforge.kits")

__all__ = ["ComponentsKit", "COMPONENT_RULES", "COMPONENTS", "ComponentError", "available", "broken", "catalogue",
           "chapters_of", "classes_of", "components_dir", "draw", "get", "ids", "rules_text", "unavailable_reason",
           "validate", "visuals_dir", "figure_extras", "override_figure", "situation_to_beats"]

#: Up to this many components the default ``rules`` give every component's full sheet; above it, a one-line index.
FULL_SHEET_LIMIT = 12
KEYS = ("id", "params", "state", "reveal")
#: Keys only code writes (``situation_to_beats``, ``normalise_figure``); the writer's rules never mention them.
#: ``hold``: parts that stay out of this drawing until a step names them (or all beat); ``with``: ``{part: [parts]}``
#: that come in together with the part when its step is said; ``situation``: the library's own set-up the beat was made
#: from, whose lines are the library's words (numbers in them are not stray). ``span`` (video-quality plan S6): the
#: distinct ``{params, state}`` of every figure in a run of consecutive beats on one component, so the card is the same
#: size in all of them (the camera does not jump between states); written by ``_focus``, never carried by
#: ``normalise_figure`` (it is recomputed on every settle), never part of ``manifest_of``.
EXTRA_KEYS = ("hold", "with", "situation", "span")
CARRIED_KEYS = ("hold", "with", "situation")
#: Most distinct drawings one span holds (one Node batch, one set of measured boxes); a longer run starts a new span.
SPAN_LIMIT = 12
FRAME_SWITCH = "LESSONFORGE_COMPONENT_FRAME"
#: The control that moves a number between beats (``component_figure``). Read here when a lesson is SETTLED too: with it on, the
#: first step of a beat whose drawing differs from the last beat's only by a listed number knob is flagged ``tween: "voice"``
#: (video-quality plan S9), so the render moves the number across that step's sentence instead of in the lead-in.
TWEEN_SWITCH = "LESSONFORGE_COMPONENT_TWEEN"

COMPONENT_RULES = """    {"kind":"component","params":{"id":"force_block","params":{"applied_force":30},"state":{"motion":"sliding_right"}}}
      A ready-made drawing from the component library (an apparatus, a force diagram, a person, a part of nature). You
      pick ONLY: "id" (a component named below, nothing else), "params" (its parameters, each from the list or range
      given for it; leave out the ones you do not need and they take their default) and "state" (optional: for each
      state it lists, either one of its named values, such as the motion or how many bubbles, or, for a state given as a
      number range, a number inside that range; several states may be given at once, and a number wins over a name).
      Do not invent an id, a parameter, an option or a state. A picture shows ONE set of numbers: to show a number
      changing, use a new figure (other numbers) on a new beat.
      Every word and number ON the picture comes from the component. Never type a value that you worked out: write
      {param applied_force} (the name of a number parameter) and code fills it. A number that is not a parameter, a
      gap, or a number the component itself writes on its picture is a fault. A text parameter takes words only, no
      digits. If no component fits, use no component figure: a picture that is not there is better than a wrong one.
      Name the parts of the drawing in the order they are listed: give a step a "focus" that is one of the component's
      PARTS, and the part is drawn in when the step is said. The first part is the outline and is there from the start.
      Use the SAME figure on every beat that keeps discussing it, and a NEW figure (other parameters or state) when the
      picture must change. Classes in scope only.
      CANVAS CONTINUITY AND STAGE LAYOUT:
      - The canvas card sits on the LEFT of the stage; the step-by-step mathematical reasoning and deductions unfold on
        the RIGHT of the stage. Keep them in visual harmony.
      - Keep the SAME component across consecutive beats of a concept or activity. When the physical state progresses
        (e.g., winding a string on a sphere, then unwinding it to 4 flat circles), keep the SAME parameters and advance
        only "state" (e.g. "unfold": 0 -> 0.5 -> 1). Never drop the figure or switch to unrelated figures mid-topic.
      - Reveal steps progressively: each step has a single concise line (LaTeX for kind "math", e.g. "A = 4 \\pi r^2")
        locked to the exact phrase in "say". Assign "focus" to the part being explained so the viewer's eye is led
        seamlessly from the visual on the left to the equation on the right.
"""

_ACTUALLY = "(none are available now)"


def _nice(value: float) -> str:
    value = round(float(value), 4) + 0.0
    return str(int(value)) if value == int(value) and abs(value) < 1e15 else f"{value:.4f}".rstrip("0").rstrip(".")


def sanitize_focus(name: Any) -> str:
    """A step's ``focus`` as ``writer`` stores it (lower case, ``a-z0-9_``, 24 characters)."""
    return re.sub(r"[^a-z0-9_]", "", str(name or "").lower())[:24]


def match_part(focus: Any, parts: list[str]) -> str | None:
    """The part a step's ``focus`` names, however the writer spelt it ("Net-Force Arrow", "netforcearrow"), else None.

    ``writer`` strips a focus to ``a-z0-9_`` and cuts it at 24 characters; a cut name still finds its part when only one
    part starts with it.
    """
    flat = lambda text: re.sub(r"[^a-z0-9]", "", str(text).lower())      # noqa: E731
    want = flat(focus)
    if not want:
        return None
    for part in parts:
        if flat(part) == want:
            return part
    if len(sanitize_focus(focus)) >= 24:
        near = [p for p in parts if flat(p).startswith(want)]
        return near[0] if len(near) == 1 else None
    return None


# ── the figure spec ──────────────────────────────────────────────────────────────────────────────────────────────

def parse_figure(figure: Any) -> tuple[str, dict, dict | None, list[str]]:
    """(id, params, state, reveal) from a component figure, written nested (``params: {id, params, state}``) or flat
    (``id``, ``params``, ``state`` beside ``kind``). Raises ``KitError`` in plain words."""
    if not isinstance(figure, dict):
        raise KitError("a component figure must be an object")
    inner = figure.get("params")
    nested = isinstance(inner, dict) and ("id" in inner or "component" in inner) and "id" not in figure
    body = inner if nested else figure
    extra = sorted(set(body) - set(KEYS) - set(EXTRA_KEYS) - ({"component"} if nested else {"kind", "manifest", "component"}))
    if extra:
        raise KitError(f"a component figure takes id, params and state, not {', '.join(extra)}: write "
                       '{"kind":"component","params":{"id":"...","params":{...},"state":{...}}}')
    cid = body.get("id", body.get("component"))
    if not isinstance(cid, str) or not cid.strip():
        raise KitError('a component figure needs "id": the name of a component')
    params = body.get("params") if nested else (inner if isinstance(inner, dict) else None)
    if params is not None and not isinstance(params, dict):
        raise KitError(f"component {cid}: params must be an object of its parameters")
    state = body.get("state")
    if state is not None and not isinstance(state, dict):
        raise KitError(f"component {cid}: state must be an object such as {{\"motion\": \"rest\"}}")
    reveal = body.get("reveal")
    if reveal is not None and not (isinstance(reveal, list) and all(isinstance(x, str) for x in reveal)):
        raise KitError(f"component {cid}: reveal must be a list of part names")
    return cid.strip(), dict(params or {}), (dict(state) if state is not None else None), list(reveal or [])


def figure_extras(figure: Any) -> dict:
    """``{hold, with, situation, span}`` of a component figure (only the ones it has); ``KitError`` when one is malformed.

    Written by code (``situation_to_beats``), read here and by the Manim side; the same nested or flat spelling as
    :func:`parse_figure`."""
    if not isinstance(figure, dict):
        return {}
    inner = figure.get("params")
    body = inner if isinstance(inner, dict) and ("id" in inner or "component" in inner) and "id" not in figure else figure
    out: dict[str, Any] = {}
    hold, together, situation, span = body.get("hold"), body.get("with"), body.get("situation"), body.get("span")
    if hold is not None:
        if not (isinstance(hold, list) and all(isinstance(x, str) for x in hold)):
            raise KitError("a component figure's hold must be a list of part names")
        out["hold"] = list(dict.fromkeys(hold))
    if together is not None:
        if not (isinstance(together, dict) and all(isinstance(k, str) and isinstance(v, list) and all(isinstance(x, str) for x in v)
                                                    for k, v in together.items())):
            raise KitError("a component figure's with must be {part: [parts that come in with it]}")
        out["with"] = {k: list(dict.fromkeys(v)) for k, v in together.items() if v}
    if situation is not None:
        if not isinstance(situation, str):
            raise KitError("a component figure's situation must be the name of one of the component's situations")
        out["situation"] = situation
    if span is not None:
        out["span"] = _check_span(span)
    return out


def _check_span(span: Any) -> list[dict]:
    """A figure's ``span`` as a list of ``{params?, state?}`` objects (at most ``SPAN_LIMIT``); ``KitError`` otherwise."""
    if not (isinstance(span, list) and 1 <= len(span) <= SPAN_LIMIT
            and all(isinstance(e, dict) and set(e) <= {"params", "state"}
                    and all(isinstance(e[k], dict) for k in e) for e in span)):
        raise KitError(f"a component figure's span must be a list of 1 to {SPAN_LIMIT} objects, each with params and/or state "
                       "(the drawings of a run of beats on one component)")
    return [{k: dict(v) for k, v in e.items()} for e in span]


def manifest_of(entry: dict, params: dict, state: dict | None, extras: dict | None = None) -> str:
    """A name for one drawing (id + the parameters and state that differ from the defaults). The runtime asks the figure
    what earlier beats pointed at ``manifest``-wise (``runtime._pointed_at_before``), so a part revealed in an earlier
    chapter is there when the figure is carried into the next."""
    held = {k: v for k, v in (extras or {}).items() if k in ("hold", "with") and v}      # absent: the name is what it was
    blob = json.dumps([entry["id"], params, state or {}] + ([held] if held else []), sort_keys=True, separators=(",", ":"))
    return f"{entry['id']}-{hashlib.sha256(blob.encode()).hexdigest()[:8]}"


class ComponentModel:
    """One component drawn with these parameters and state: what ``solve`` returns."""

    def __init__(self, entry: dict, supplied: dict, state: dict | None, drawn: dict, reveal: list[str],
                 extras: dict | None = None):
        self.entry, self.supplied, self.state, self.drawn, self.reveal = entry, supplied, state, drawn, reveal
        self.extras = dict(extras or {})
        self.id = entry["id"]
        self.params = drawn["params"]
        self.notes: tuple[str, ...] = ()
        self.trusted: frozenset[float] = frozenset()
        sit = next((x for x in entry.get("situations") or [] if x["name"] == self.extras.get("situation")), None)
        if sit is not None:                  # the library's own lines for this set-up: its authors' words, not a writer's
            self.trusted = frozenset(float(n) for step in sit["steps"] for n in lib._LABEL_NUMBER.findall(step["say"]))

    @property
    def parts(self) -> list[str]:
        return [name for name, _ in self.drawn["parts"]]

    def empty_parts(self) -> list[str]:
        return lib.empty_parts(self.drawn)

    def number_params(self) -> dict[str, float]:
        kinds = {p["name"]: p["type"] for p in self.entry["params"]}
        return {k: float(v) for k, v in self.params.items()
                if kinds.get(k) in ("number", "integer", "int") and isinstance(v, (int, float)) and not isinstance(v, bool)}

    def facts(self) -> Mapping[str, Any]:
        out: dict[str, Any] = {"component": self.id}
        out.update({k: v for k, v in self.params.items() if isinstance(v, (int, float, str)) and not isinstance(v, bool)})
        return out

    def shown(self) -> frozenset[float]:
        return frozenset(float(x) for x in self.drawn["numbers"]) | self.trusted


# ── words in a beat ──────────────────────────────────────────────────────────────────────────────────────────────

#: A number on its own. Not part of a word or an exponent ("m2", "x^2"), not half of a fraction ("1/2"), not an ordinal
#: ("3rd"), not the number of a class, chapter, step or figure ("Class 8").
_NUMBER = re.compile(r"(?<![\w.^/])(\d+(?:\.\d+)?)(?![\d]|/\d|\.\d)")
_ORDINAL = re.compile(r"(?:st|nd|rd|th)\b", re.I)
_LABELLED = re.compile(r"\b(?:class|classes|chapter|ch|step|steps|part|figure|fig|question|q|grade|std|no|number)\.?\s*$", re.I)
_GAP_TERM = re.compile(r"\s*param\s+([A-Za-z_]\w*)\s*")


class ComponentsKit(KitBase):
    name = "components"
    figure_kinds = ("component",)
    builder: Mapping[str, str] = {"component": "lessonforge.longform.component_figure:component"}
    mcp_note = ("Component figures are {\"kind\":\"component\",\"params\":{\"id\":\"force_block\"}} from the component "
                "library: use only the ids and parameters in the kit's rules, write {param NAME} for a number and code "
                "fills it, and let each step's focus name a part of the drawing.")

    # -- routing metadata: from the components themselves, so a new subject appears with its first file --

    @property
    def rules(self) -> str:                                    # type: ignore[override]
        return rules_text()

    @property
    def subjects(self) -> tuple[str, ...]:                     # type: ignore[override]
        try:
            return tuple(dict.fromkeys(e["subject"] for e in catalogue()))
        except Exception:  # noqa: BLE001 - metadata must never cost a lesson
            return ()

    @property
    def classes(self) -> tuple[int, ...]:                      # type: ignore[override]
        try:
            return tuple(sorted({c for e in catalogue() for c in e["classes"]} & set(SCOPE_CLASSES))) or SCOPE_CLASSES
        except Exception:  # noqa: BLE001
            return SCOPE_CLASSES

    @property
    def keywords(self) -> tuple[str, ...]:                     # type: ignore[override]
        try:
            return tuple(dict.fromkeys(w for e in catalogue() for w in e["keywords"]))[:120]
        except Exception:  # noqa: BLE001
            return ()

    @property
    def focus_parts(self) -> Mapping[str, tuple[str, ...]]:   # type: ignore[override]
        try:
            return {"component": tuple(dict.fromkeys(p for e in catalogue() for p in e["parts"]))}
        except Exception:  # noqa: BLE001
            return {}

    # -- the model --

    def solve(self, figure):
        cid, params, state, reveal = parse_figure(figure)
        try:
            entry = get(cid, in_scope=True)
            problems = lib.check_params(entry, params, state)
            if problems:
                raise KitError(f"component {cid}: " + "; ".join(problems))
            drawn = draw(cid, params, state)
        except ComponentError as exc:
            raise KitError(str(exc)) from exc
        extras = figure_extras(figure)
        model = ComponentModel(entry, params, state, drawn, reveal, extras)
        named = list(reveal) + list(extras.get("hold", [])) + [x for k, v in extras.get("with", {}).items() for x in [k, *v]]
        unknown = [r for r in dict.fromkeys(named) if r not in model.parts]
        if unknown:
            raise KitError(f"component {cid}: reveal names {', '.join(unknown)}, which are not parts (parts: "
                           f"{', '.join(model.parts)})")
        if model.parts[0] in extras.get("hold", []):
            raise KitError(f"component {cid}: the first part ({model.parts[0]}) is the outline and cannot be held back")
        if "situation" in extras and not any(x["name"] == extras["situation"] for x in entry.get("situations") or []):
            raise KitError(f"component {cid} has no situation {extras['situation']!r}")
        return model

    def normalise_figure(self, figure):
        """The canonical nested spec with only what differs from the defaults, or None when it cannot be drawn."""
        try:
            model = self.solve(figure)
        except KitError:
            return None
        defaults = {p["name"]: p["default"] for p in model.entry["params"]}
        params = {k: (int(v) if isinstance(v, float) and v == int(v) else v) for k, v in model.supplied.items()
                  if v != defaults.get(k)}
        inner: dict[str, Any] = {"id": model.id}
        if params:
            inner["params"] = params
        if model.state:
            inner["state"] = dict(model.state)
        if model.reveal:
            inner["reveal"] = list(model.reveal)
        for key in CARRIED_KEYS:                       # not ``span``: it is a property of the run, recomputed by ``_focus``
            if model.extras.get(key):
                inner[key] = model.extras[key]
        return {"kind": "component", "params": inner, "manifest": manifest_of(model.entry, params, model.state, model.extras)}

    def describe(self, figure):
        try:
            m = self.solve(figure)
        except KitError as exc:
            return str(exc)
        labels = "; ".join(f"{lab['text']!r} on {lab['part']}" for lab in m.drawn["labels"])
        numeric = ", ".join(f"{k} {_nice(v)}" for k, v in m.number_params().items())
        return (f"component {m.id}: {numeric or 'no number parameters'}; parts in order: {', '.join(m.parts)}"
                + (f"; empty in this state: {', '.join(m.empty_parts())}" if m.empty_parts() else "")
                + (f"; the picture writes: {labels}" if labels else ""))

    # -- gaps --

    def fill_gap(self, expr, model):
        found = _GAP_TERM.fullmatch(expr or "")
        numeric = model.number_params()
        have = ", ".join(f"{k} = {_nice(v)}" for k, v in numeric.items()) or "none"
        if not found:
            raise KitError(f"gap {{{expr}}} can only be {{param NAME}}, a number parameter of {model.id} (they are: {have})")
        name = found.group(1)
        if name not in numeric:
            kind = "is not a number" if name in model.params else f"has no parameter {name}"
            raise KitError(f"gap {{{expr}}}: {model.id} {kind}; its number parameters are: {have}")
        return _nice(numeric[name]), numeric[name]

    # -- claims: none (the component cannot back a claim about its picture) --

    def claims(self, text, model):
        return []

    # -- typed numbers --

    def stray_numbers(self, text, model, used):
        allowed = list(model.shown()) + [abs(v) for v in used]
        out: list[str] = []
        plain = GAP.sub(" ", text or "")
        for m in _NUMBER.finditer(plain):
            if _ORDINAL.match(plain, m.end()) or _LABELLED.search(plain[:m.start()]):
                continue
            value = float(m.group(1))
            if any(abs(value - a) <= 1e-9 * max(1.0, abs(a)) for a in allowed):
                continue
            if m.group(1) not in out:
                out.append(m.group(1))
        return out

    # -- the lesson: focus names, the reveal order, canonical figures --

    def settle(self, lesson: Lesson) -> tuple[Lesson, list[str]]:
        beats = beats_of(lesson)
        specs = []
        for _, beat in beats:
            fig = beat.get("figure")
            if isinstance(fig, dict) and fig.get("kind") in self.figure_kinds:
                try:
                    cid, params, state, _ = parse_figure(fig)
                    specs.append((cid, params, state))
                except KitError:
                    pass
        if specs:
            lib.prefetch(specs)                                   # every drawing of the lesson in ONE Node process
        lesson, issues = super().settle(lesson)
        return lesson, issues + self._focus(lesson)

    def _focus(self, lesson: Lesson) -> list[str]:
        """Faults for a step's focus; sets each component figure's ``reveal`` and ``manifest``. Mutates ``lesson``."""
        issues: list[str] = []
        current: dict | None = None                               # the component figure on screen, carried across beats
        groups: dict[str, set[str]] = {}                          # manifest -> parts named by steps while it is on screen
        seen: list[tuple[dict, str]] = []                         # (figure dict, manifest) per beat that owns a figure
        runs: list[dict] = []                                     # runs of consecutive beats on one component (the stable frame)
        run: dict | None = None
        voice = str(knobs.get(TWEEN_SWITCH, "0")).strip() == "1"   # flag the step that carries a number change (S9)
        last: dict | None = None                                  # {params, state} of the run's last drawing
        moved = False                                             # this beat's drawing is the last one with a listed knob moved
        for number, (ci, beat) in enumerate(beats_of(lesson), start=1):
            fig = beat.get("figure") if isinstance(beat.get("figure"), dict) else None
            ref = f"beat {number} (chapter {ci})"
            if fig is not None:
                if fig.get("kind") in self.figure_kinds:
                    canon = self.normalise_figure(fig)
                    if canon is None:
                        current, run, last = None, None, None     # unsolvable: reported by settle already
                        continue
                    fig.clear()
                    fig.update(canon)
                    current = fig
                    seen.append((fig, canon["manifest"]))
                    before = run
                    run = self._join_run(runs, run, fig)
                    inner = fig["params"]
                    entry = {k: inner[k] for k in ("params", "state") if inner.get(k)}
                    moved = bool(voice and before is run and last is not None and last != entry and self._moves_a_number(inner["id"], last, entry))
                    last = entry
                else:
                    current, run, last = None, None, None         # another kit's or a built-in picture replaces it
                    for step in beat.get("steps") or []:
                        if isinstance(step, dict):
                            step.pop("tween", None)               # a flag is this kit's, for its own drawings only
                    continue
            elif beat.get("picture") == "off" or current is None:
                continue
            else:
                moved = False                                     # a beat that keeps the picture up changes nothing
            try:
                model = self.solve(current)
            except KitError:
                continue
            empty = set(model.empty_parts())
            steps = [x for x in beat.get("steps") or [] if isinstance(x, dict)]
            chosen = next((x for x in steps if x.get("tween") == "voice" and str(x.get("show", "")).strip()), None)
            for step in steps:
                step.pop("tween", None)                           # rewritten below: a flag on a beat that moves no number goes
            if moved:                                             # the step a hand flagged, else the beat's first
                first = chosen or next((x for x in steps if str(x.get("show", "")).strip()), None)
                if first is not None:
                    first["tween"] = "voice"
            for k, step in enumerate(beat.get("steps") or [], start=1):
                if isinstance(step, dict) and ("params" in step or "state" in step):
                    issues.append(f"{ref} step {k}: {self._override_fault(current, step)}")
                focus = step.get("focus") if isinstance(step, dict) else None
                if not focus:
                    continue
                part = match_part(focus, model.parts)
                if part is None:
                    issues.append(f"{ref} step {k} focus: {focus!r} is not a part of component {model.id} "
                                  f"(its parts, in order: {', '.join(model.parts)})")
                elif part in empty:
                    issues.append(f"{ref} step {k} focus: part {part} of {model.id} draws nothing in this state "
                                  "(choose another state, or another part)")
                else:
                    if part != model.parts[0]:
                        groups.setdefault(current["manifest"], set()).add(part)
                    step["focus"] = part
        for fig, manifest in seen:                                # one reveal list per drawing, for every beat it is on
            order = [p for p in self.solve(fig).parts if p in groups.get(manifest, set())]
            if order:
                fig["params"]["reveal"] = order
            else:
                fig["params"].pop("reveal", None)
        if str(knobs.get(FRAME_SWITCH, "1")).strip() != "0":      # off: no figure gets a span, every card is its own size
            for one in runs:
                if len(one["entries"]) >= 2:
                    span = [one["entries"][k] for k in sorted(one["entries"])]
                    for fig in one["figs"]:
                        fig["params"]["span"] = copy.deepcopy(span)
        return issues

    @staticmethod
    def _moves_a_number(cid: str, before: dict, after: dict) -> bool:
        """Whether the change from one drawing of a component to the next is only listed number knobs
        (``component_lib.TWEEN_KNOBS``); the render still measures it (``morph_plan``) and may refuse."""
        try:
            return bool(lib.tweenable(get(cid, in_scope=True), before, after))
        except (ComponentError, KeyError, TypeError, ValueError):
            return False

    @staticmethod
    def _join_run(runs: list[dict], run: dict | None, fig: dict) -> dict:
        """The run of consecutive beats on one component that ``fig`` (canonical, no span) belongs to: the current run when it
        is the same component and the drawing is one it already holds or fits (``SPAN_LIMIT``), else a new run."""
        inner = fig["params"]
        entry = {k: inner[k] for k in ("params", "state") if inner.get(k)}
        key = json.dumps(entry, sort_keys=True, separators=(",", ":"))
        if run is None or run["id"] != inner["id"] or (key not in run["entries"] and len(run["entries"]) >= SPAN_LIMIT):
            run = {"id": inner["id"], "entries": {}, "figs": []}
            runs.append(run)
        run["entries"].setdefault(key, entry)
        run["figs"].append(fig)
        return run

    def _override_fault(self, figure: dict, step: dict) -> str:
        """Why a step that carries ``params`` or ``state`` is a fault. A beat has ONE drawing, so a step cannot move a
        number on it (the renderer would ignore the override and the words would describe a picture that is not there)."""
        try:
            override_figure(figure, step.get("params"), step.get("state"))
        except KitError as exc:
            return f"{exc}"
        return ("a step cannot change the picture's numbers (a beat has one drawing): give the new numbers to a NEW figure "
                "on a new beat, as situation_to_beats does")

    # -- conformance --

    def cases(self) -> KitCases:
        pool = catalogue()
        entry = next((e for e in pool if any(p["type"] == "number" and "min" in p and "max" in p for p in e["params"])), None) \
            or (pool[0] if pool else None)
        refused: list[tuple[Lesson, str]] = [
            (_lesson(_beat("Look at it.", {"kind": "component", "params": {"id": "no_such_component_x"}})),
             "there is no component"),
            (_lesson(_beat("Look at it.", {"kind": "component", "params": {"params": {}}})), 'needs "id"'),
            (_lesson(_beat("The value is {param width}.", None)), "no components figure"),
        ]
        gaps: list[tuple[str, dict, str]] = []
        if entry is None:
            return KitCases(good=(_lesson(_beat("A plain beat with no picture."),),), refused=tuple(refused), gaps=())
        number = next((p for p in entry["params"] if p["type"] == "number"), None)
        fig = {"kind": "component", "params": {"id": entry["id"], "params": dict(entry["example"])}}
        draw_now = draw(entry["id"], entry["example"])
        later = next((n for n, svg in draw_now["parts"][1:] if svg.strip()), entry["parts"][0])
        narration = f"This is the {entry['title'].lower()}."
        if number is not None:
            narration += f" Its {number['name'].replace('_', ' ')} is {{param {number['name']}}}."
            gaps.append((f"param {number['name']}", fig, _nice(draw_now["params"][number["name"]])))
        good = _lesson(_beat(narration, fig, steps=[{"say": "This is the", "show": "x", "focus": later}]))
        refused += [
            (_lesson(_beat("Look at the second part.", fig, steps=[{"say": "Look at", "show": "x", "focus": "nonesuch_part"}])),
             "is not a part of component"),
            (_lesson(_beat("It is 987654 units.", fig)), "987654"),
            (_lesson(_beat("Look at it.", {"kind": "component", "params": {"id": entry["id"], "params": {"no_such_param": 1}}})),
             "is not a parameter"),
            (_lesson(_beat("Look at it.", {"kind": "component", "params": {"id": entry["id"], "state": {"no_such_state": "x"}}})),
             "is not a state"),
            (_lesson(_beat("It is {param no_such_param}.", fig)), "no parameter"),
        ]
        if number is not None and "max" in number:
            far = {**entry["example"], number["name"]: number["max"] + 1000}
            refused.append((_lesson(_beat("Look at it.", {"kind": "component", "params": {"id": entry["id"], "params": far}})),
                            "must be from"))
        return KitCases(good=(good,), refused=tuple(refused), gaps=tuple(gaps))

    # -- the rules the writer is given, for the components a lesson or brief names --

    def rules_with(self, argument: str) -> str:
        """The rules with the full sheet of the components named in ``argument`` ("force_block,test_tube")."""
        return rules_text([a.strip() for a in str(argument or "").split(",") if a.strip()])

    def rules_name(self, lesson: Lesson) -> str:
        """``components:<ids the lesson uses>`` for ``registry.rules_for_lesson``, so the improver sees their sheets."""
        used: list[str] = []
        for _, beat in beats_of(lesson):
            fig = beat.get("figure")
            if isinstance(fig, dict) and fig.get("kind") in self.figure_kinds:
                try:
                    cid = parse_figure(fig)[0]
                except KitError:
                    continue
                if cid not in used:
                    used.append(cid)
        return "components:" + ",".join(used) if used else self.name


def override_figure(figure: dict, params: Mapping[str, Any] | None = None, state: Mapping[str, Any] | None = None) -> dict:
    """A copy of a component figure with ``params`` and ``state`` laid over its own, or ``KitError``.

    The contract lets a number param change in any step and a number state move; the lesson contract draws ONE figure per
    beat, so a change of numbers is a new figure on a new beat, and this builds that figure. Refused in plain words: an
    unknown parameter or state, a number outside its min/max, a name that is not listed. A number state set here wins
    over a named preset of the old figure (the component's README), so a preset the override does not mention is dropped
    only when the override sets a number state. The result is canonical (``normalise_figure``)."""
    cid, old_params, old_state, _ = parse_figure(figure)
    extras = figure_extras(figure)
    if params is not None and not isinstance(params, Mapping):
        raise KitError(f"component {cid}: params must be an object")
    if state is not None and not isinstance(state, Mapping):
        raise KitError(f"component {cid}: state must be an object")
    new_params = {**old_params, **(params or {})}
    new_state = {**(old_state or {}), **(state or {})}
    nested = {"id": cid, **({"params": new_params} if new_params else {}), **({"state": new_state} if new_state else {}),
              **{k: v for k, v in extras.items() if k in CARRIED_KEYS}}
    canon = _kit().normalise_figure({"kind": "component", "params": nested})
    if canon is None:                               # say why, with the library's own words
        try:
            entry = get(cid, in_scope=True)
        except ComponentError as exc:
            raise KitError(str(exc)) from exc
        why = lib.check_params(entry, new_params, new_state or None)
        raise KitError(f"component {cid}: " + "; ".join(why or ["these numbers cannot be drawn"]))
    return canon


def _kit() -> ComponentsKit:
    """The registered kit, else a private one (its methods need nothing the registry holds)."""
    return COMPONENTS or ComponentsKit()


def _show_text(say: str, limit: int = 12) -> str:
    """The on-screen words for a step from the library's own ``say`` line: its first sentence when that is short (at most
    ``limit`` words), else the first clause of it that is, else its first 9 words. Only words the library wrote."""
    first = re.split(r"(?<=[.!?])\s+", " ".join(say.split()))[0]
    words = first.split()
    if len(words) <= limit:
        return first
    for cut in range(limit, 2, -1):
        if words[cut - 1].endswith((",", ";", ":", "—", "–")):
            return " ".join(words[:cut]).rstrip(",;:—– ")
    return " ".join(words[:9]).rstrip(",;:—– ") + "…"


#: A beat holds at most this many steps (the writer's rule is 2 to 4): more are set in a column too small to read.
MAX_STEPS = 4


def situation_to_beats(component_id: str, situation_name: str, speaker: str | None = None) -> list[dict]:
    """Lesson beats made from one of the component's own ready-made situations: a textbook set-up its authors checked.

    ``[{narration, steps, figure, visual, situation[, speaker]}]`` with no id (the caller numbers beats). Everything on the
    screen and in the voice is the library's: the narration is the situation's ``say`` lines in order, each step is one of
    them (``say``: its first words, found in the narration; ``show``: its first sentence, or the first clause of a long one), the figure is
    the component with the situation's params and the states set so far, and a step's ``focus`` is the part it brings in.
    No model touches a word.

    A beat has one drawing, so a step that changes a state or a param (a number sliding, a preset changing) starts a NEW
    beat with a new figure; a step that only shows more parts stays in its beat and its ``focus`` draws the part in.
    Parts the set-up has not shown yet are held back (``hold``); parts a step shows together come in together (``with``).
    A part the set-up shows and later stops showing stays on screen (a beat cannot take a part away). A run of more than
    ``MAX_STEPS`` steps with the same numbers is cut into beats of that many steps, each with the same figure (the picture
    stays up and its parts stay drawn).

    ``speaker`` (optional) is carried on every beat as ``speaker``. ``KitError`` for an unknown component or situation, a
    param or state outside its min/max, or anything the component's own ``validate`` refuses.
    """
    if speaker is not None and not (isinstance(speaker, str) and speaker.strip() and len(speaker) <= 60 and "\n" not in speaker):
        raise KitError("speaker must be a short name")
    try:
        entry = get(component_id, in_scope=True)
        sit = lib.get_situation(entry, situation_name)
        frames = lib.situation_plan(component_id, situation_name)
    except ComponentError as exc:
        raise KitError(str(exc)) from exc
    kit = _kit()
    parts = entry["parts"]
    groups: list[list[dict]] = []
    for frame in frames:                                 # a new beat when the numbers or the named state change
        if groups and groups[-1][0]["params"] == frame["params"] and groups[-1][0]["state"] == frame["state"]:
            groups[-1].append(frame)
        else:
            groups.append([frame])
    beats: list[dict] = []
    total = sum(-(-len(g) // MAX_STEPS) for g in groups)
    seen = {parts[0]}                                    # on screen before the beat: the outline, then what earlier beats showed
    for group in groups:
        visible, together, steps = set(seen), {}, []
        for frame in group:
            new = [p for p in parts if p in frame["show"] and p not in visible and p not in frame["empty"]]
            step = {"say": " ".join(frame["say"].split()[:5]), "show": _show_text(frame["say"]), "kind": "point", "highlight": False}
            if new:
                step["focus"] = new[0]
                if len(new) > 1:
                    together[new[0]] = new[1:]
            visible |= set(frame["show"])
            steps.append(step)
        hold = [p for p in parts[1:] if p not in visible]
        spec: dict[str, Any] = {"id": entry["id"]}
        defaults = {p["name"]: p["default"] for p in entry["params"]}
        shown_params = {k: v for k, v in group[0]["params"].items() if v != defaults.get(k)}
        if shown_params:
            spec["params"] = shown_params
        if group[0]["state"]:
            spec["state"] = dict(group[0]["state"])
        if hold:
            spec["hold"] = hold
        if together:
            spec["with"] = together
        spec["situation"] = sit["name"]
        figure = kit.normalise_figure({"kind": "component", "params": spec})
        if figure is None:
            kit.solve({"kind": "component", "params": spec})          # raises KitError saying why
            raise KitError(f"component {entry['id']} situation {sit['name']} cannot be drawn")
        for start in range(0, len(group), MAX_STEPS):          # a long run keeps ONE figure (the same spec) over several beats
            chunk = slice(start, start + MAX_STEPS)
            beat = {"narration": " ".join(f["say"] for f in group[chunk]), "steps": steps[chunk], "figure": copy.deepcopy(figure),
                    "visual": f"{entry['title']}: {sit['title']}" + (f" ({len(beats) + 1} of {total})" if total > 1 else ""),
                    "situation": {"component": entry["id"], "name": sit["name"], "title": sit["title"], "ncert": sit["ncert"]}}
            if speaker:
                beat["speaker"] = speaker.strip()
            beats.append(beat)
        seen = visible | seen
    return beats


def rules_text(component_ids: list[str] | None = None, *, subjects: list[str] | None = None) -> str:
    """The writer's section for this kit, GENERATED from the catalogue so a new component appears at once.

    With ``component_ids`` (the components a brief names): the full sheet of each, and an id that does not exist is said
    to be missing. Without: every component in scope (the classes in scope, optionally one of ``subjects``): the full sheets
    when there are at most ``FULL_SHEET_LIMIT``, else one line each.
    """
    head = COMPONENT_RULES
    try:
        if component_ids:
            lines, missing = [], []
            for cid in component_ids:
                try:
                    lines.append(lib.sheet(get(cid, in_scope=True)))
                except ComponentError as exc:
                    missing.append(str(exc))
            body = "    THE COMPONENTS FOR THIS LESSON (use these ids and parameters only):\n" + "\n".join(lines) if lines else ""
            return head + (body + "\n" if body else "") + "".join(f"    ({m})\n" for m in missing)
        pool = catalogue(subjects=subjects)
    except ComponentError as exc:
        return head + f"    (components are not available: {exc})\n"
    if not pool:
        return head + "    No component is available for the classes in scope yet: use no component figure.\n"
    if len(pool) <= FULL_SHEET_LIMIT:
        return head + "    THE COMPONENTS (use these ids and parameters only):\n" + "\n".join(lib.sheet(e) for e in pool) + "\n"
    return (head + "    THE COMPONENTS (use these ids only; a brief that names components gets each one's parameters):\n"
            + "\n".join(lib.index_line(e) + "; parts: " + ", ".join(e["parts"]) for e in pool) + "\n")


def _beat(narration: str, figure: dict | None = None, steps: list | None = None) -> dict:
    beat = {"narration": narration, "steps": steps if steps is not None else [{"say": narration.split(".")[0][:30], "show": "x"}]}
    if figure is not None:
        beat["figure"] = figure
    return beat


def _lesson(*beats: dict) -> Lesson:
    return {"title": "cases", "chapters": [{"title": "ONE", "learning_goal": "g", "role": "explain", "beats": list(beats)}]}


def _register() -> ComponentsKit | None:
    """Register the kit when Node and the components are there; otherwise ONE log line and no kit (never an exception)."""
    try:
        why = unavailable_reason()
        if why:
            log.warning("components kit not registered: %s", why)
            return None
        return register(ComponentsKit())
    except Exception as exc:  # noqa: BLE001 - a kit that cannot start costs nothing else
        log.warning("components kit not registered (%s: %s)", type(exc).__name__, str(exc)[:160])
        return None


COMPONENTS = _register()
