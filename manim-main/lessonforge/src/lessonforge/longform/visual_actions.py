"""The visual-teaching vocabulary: every visual action a lesson can take, as typed data, and the checks on them.

The owner's module "Visual Teaching Intelligence" (2026-10-20, docs/engine/visual-teaching-engine.md) asks for a
typed vocabulary of visual actions with, for each, its purpose, targets, parameters, duration, prerequisites,
accessibility and validation, and for one structured plan per scene that the voice and the picture share.

Most actions already existed, each in its own place (a step's entrance, a figure's ``focus``, the hand's marks,
the voice-led hints on a reaction, a question card). This module names them ONE way and derives, from a finished
lesson and its timeline, the plan a renderer follows: ``visual_plan(lesson, timeline)`` writes, per beat, what is on
screen first, every action with its target and the spoken words it waits for (``t``: seconds into the scene), where the learner is asked, and what
a wrong answer leads to. ``validate(plan, lesson)`` is code, not a model: a target that does not exist, an action
the vocabulary does not have, too many changes at one moment, an answer revealed before its question, a reaction
whose counts disagree with its equation.

Nothing here imports manim or calls a model, so the same plan can drive the video renderer, a web player or a
mobile one; ``ACTIONS[...]["by"]`` says which code carries each action out in the video today.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from . import figure_math

SCHEMA = "lessonforge.visual_plan/1"

#: The vocabulary. ``by`` names what performs the action in the video renderer today ("" = not built).
ACTIONS: dict[str, dict] = {
    "highlight": {"purpose": "draw the eye to one element the words are about", "targets": "a figure part, a ball, a count",
                  "params": ["target"], "seconds": (0.2, 1.0), "needs": "target on screen",
                  "access": "never colour alone: the lit thing also grows", "by": "runtime._start_hints / step focus"},
    "dim": {"purpose": "hide what does not matter while one thing is explained", "targets": "everything but the target",
            "params": ["keep"], "seconds": (0.3, 0.6), "needs": "target on screen",
            "access": "dimmed things stay at least 30% visible", "by": "viz_helpers.spotlight_on (engine path only)"},
    "focus": {"purpose": "point at a part and keep it outlined until the next focus", "targets": "a named figure part",
              "params": ["target"], "seconds": (0.4, 0.9), "needs": "target is a part of the beat's figure",
              "access": "outline, not colour only", "by": "runtime._entrance (step focus)"},
    "label": {"purpose": "write a name or a value on the picture", "targets": "a drawing's thing",
              "params": ["text", "target"], "seconds": (0.6, 1.4), "needs": "target drawn",
              "access": "text at least 22 px on a phone", "by": "harness.annotate (step annotate)"},
    "connect": {"purpose": "arrows, braces, paths between things", "targets": "two things",
                "params": ["from", "to"], "seconds": (0.6, 1.4), "needs": "both drawn",
                "access": "", "by": "harness.annotate (arrow/trace kinds)"},
    "reveal": {"purpose": "bring one line or part in when it is spoken of", "targets": "a step, a drawing's part",
               "params": ["target", "anchor"], "seconds": (0.35, 0.9), "needs": "anchor words in the narration",
               "access": "one new thing at a time", "by": "runtime.GuidedChapter steps / sequence.with_words"},
    "construct": {"purpose": "build an equation or diagram step by step", "targets": "a formula line",
                  "params": ["from", "to"], "seconds": (0.5, 1.0), "needs": "the line before it on screen",
                  "access": "", "by": "runtime._entrance (a line grows from a copy of the last)"},
    "compare": {"purpose": "two representations side by side", "targets": "two figures or panels",
                "params": ["left", "right"], "seconds": (0.5, 1.0), "needs": "",
                "access": "each side labelled in words", "by": "figures (panels, ghost)"},
    "change": {"purpose": "a quantity, position or state changes, and only what changed moves", "targets": "a figure",
               "params": ["from", "to"], "seconds": (0.7, 2.8), "needs": "the figure before it on screen",
               "access": "", "by": "figures.reaction_change; same-kind morph otherwise"},
    "transform": {"purpose": "one representation becomes another", "targets": "a figure or a line",
                  "params": ["from", "to"], "seconds": (0.4, 0.9), "needs": "", "access": "",
                  "by": "runtime same-kind ReplacementTransform"},
    "contrast": {"purpose": "a correct and an incorrect example", "targets": "a figure with role wrong",
                 "params": ["wrong"], "seconds": (0.5, 1.0), "needs": "",
                 "access": "the wrong one also says so in words", "by": "figures.reaction role:wrong (verdict line)"},
    "counter": {"purpose": "counts, measures, live state shown and updated", "targets": "a count table cell",
                "params": ["side", "element"], "seconds": (0.3, 0.8), "needs": "counts shown",
                "access": "numbers, not only balls", "by": "figures.reaction count table + hints"},
    "pause": {"purpose": "stop for a prediction or a reflection; the picture holds still", "targets": "the beat",
              "params": ["seconds", "question"], "seconds": (2.0, 6.0), "needs": "the beat ends on its question",
              "access": "the question also on screen", "by": "runtime pause card + player interactions.json"},
    "hint": {"purpose": "a reason or a hint, given after a wrong answer, never before", "targets": "a question",
             "params": ["option", "why"], "seconds": (0, 0), "needs": "a question card",
             "access": "", "by": "player ladder (Questions.tsx, interactions.json on_wrong)"},
    "revisit": {"purpose": "go back to an earlier picture to compare", "targets": "an earlier beat",
                "params": ["seek_to"], "seconds": (0, 0), "needs": "", "access": "",
                "by": "player 'Watch that part again' (interactions.json on_wrong.seek_to)"},
    "remove": {"purpose": "take the picture away when the words are about something else", "targets": "a figure",
               "params": [], "seconds": (0.3, 0.3), "needs": "", "access": "", "by": "beat picture: off"},
}

#: How many actions may START within one second before a viewer cannot follow them (the hints' own count walk
#: lights balls 0.09 s apart, which is one action: "count").
AT_ONCE = 4

#: Hint kinds of ``reaction_hints.plan`` as vocabulary actions.
_HINT_ACTION = {"atoms": "highlight", "species": "highlight", "front": "highlight", "tally": "counter",
                "count": "counter", "both": "counter"}


def _words_in(beat: dict) -> list[dict]:
    return [w for s in beat.get("sentences") or [] for w in s.get("words") or []]


def _at(beat: dict, phrase: str, after: float = 0.0):
    """The time (on the lesson's clock) the beat's voice says ``phrase``, else None (the renderer's own search)."""
    from .timeline_compiler import locate
    try:
        found = locate(beat.get("sentences") or [], phrase, after=after)
    except TypeError:
        found = None
    return found[0] if found else None


def _figure_actions(spec: dict | None, before: dict | None) -> list[dict]:
    if not spec:
        return [{"action": "remove", "target": "picture"}] if before else []
    if before and before.get("kind") == spec.get("kind") and before != spec:
        what = "change" if spec.get("kind") == "reaction" else "transform"
        return [{"action": what, "target": "figure", "from": before.get("equation") or before.get("kind"),
                 "to": spec.get("equation") or spec.get("kind")}]
    if before == spec:
        return []
    act = [{"action": "reveal", "target": "figure", "what": spec.get("kind")}]
    if spec.get("kind") == "reaction" and str(spec.get("role", "")) == "wrong":
        act.append({"action": "contrast", "target": "figure", "wrong": spec.get("wrong") or "products"})
    return act


def reaction_state(spec: dict) -> dict | None:
    """What a reaction figure shows: species, counts per side, verdict (the figure's own reading, ``figures.reaction``)."""
    try:
        parsed = figure_math.parse_equation(spec.get("equation", ""))
    except (ValueError, KeyError, TypeError):
        return None
    left, right = figure_math.atom_counts(parsed["left"]), figure_math.atom_counts(parsed["right"])
    unknown = any(sp["unknown"] for side in parsed.values() for sp in side)
    verdict = "formula changed" if str(spec.get("role", "")) == "wrong" else "find the numbers" if unknown \
        else "balanced" if left == right else "not balanced yet"
    return {"equation": spec.get("equation"), "before": left, "after": right, "verdict": verdict,
            "species": [{"formula": sp["formula"], "n": sp["n"], "side": side, "unknown": sp["unknown"]}
                        for side in ("left", "right") for sp in parsed[side]]}


def visual_plan(lesson: dict, timeline: list[dict] | None = None, interactions: dict | None = None) -> dict:
    """The plan, per beat: objective, narration, what is on screen first, actions with targets and times, the
    learner's turn and what follows a wrong answer. ``timeline`` (timeline.json) gives the heard words; without it
    every anchor time is None and the plan is still complete in order."""
    by_id = {str(b.get("id")): b for b in timeline or []}
    asks = {}
    for item in (interactions or {}).get("interactions") or []:
        asks[str(item.get("beat") or item.get("beat_id") or "")] = item
    scenes, before = [], None
    for ch in lesson.get("chapters") or []:
        for beat in ch.get("beats") or []:
            bid = str(beat.get("id"))
            heard = by_id.get(bid, {})
            spec = beat.get("figure") if isinstance(beat.get("figure"), dict) else None
            if beat.get("picture") == "off":
                spec = None
            shown_spec = spec or (before if not beat.get("figure") and beat.get("picture") != "off" else None)
            actions = [{**a, "t": 0.0} for a in _figure_actions(shown_spec, before)]   # in the beat's lead-in
            cursor = 0.0
            for i, step in enumerate(beat.get("steps") or []):
                t = _at(heard, step.get("say", ""), cursor) if heard else None
                if t is not None:
                    cursor = t
                kind = "construct" if step.get("kind") == "math" and i and \
                    (beat.get("steps") or [])[i - 1].get("kind") == "math" else "reveal"
                actions.append({"action": kind, "target": f"step{i + 1}", "text": step.get("show", ""),
                                "anchor": step.get("say", ""), "t": t})
                if step.get("focus"):
                    actions.append({"action": "focus", "target": step["focus"], "anchor": step.get("say", ""), "t": t})
                for mark in step.get("annotate") or []:
                    actions.append({"action": "label" if mark.get("kind") in (None, "value", "name") else "connect",
                                    "target": mark.get("thing") or mark.get("target"), "anchor": mark.get("say", ""), "t": t})
            if shown_spec and shown_spec.get("kind") == "reaction" and heard.get("sentences"):
                from . import reaction_hints
                state = reaction_state(shown_spec) or {}
                species = [{"formula": sp["formula"], "side": sp["side"],
                            "atoms": figure_math.formula_atoms(sp["formula"])} for sp in state.get("species", [])]
                for ev in reaction_hints.plan(heard["sentences"], species):
                    actions.append({"action": _HINT_ACTION.get(ev["kind"], "highlight"), "target": ev["kind"],
                                    "element": ev.get("element"), "side": ev.get("side"),
                                    "species": ev.get("species"), "t": ev["t"]})
            turn = None
            if beat.get("quiz") or beat.get("pause"):
                ask = asks.get(bid) or {}
                turn = {"action": "pause", "seconds": beat.get("pause"), "question": (beat.get("quiz") or {}).get("question")
                        or (beat.get("steps") or [{}])[-1].get("show"),
                        "options": (beat.get("quiz") or {}).get("options"), "answer": (beat.get("quiz") or {}).get("answer"),
                        "on_wrong": ask.get("on_wrong") or {"action": "hint", "then": "revisit"}}
            scenes.append({
                "scene": bid, "chapter": ch.get("title"), "objective": beat.get("check") or ch.get("goal") or "",
                "narration": [s.get("text") for s in heard.get("sentences") or []] or [beat.get("narration", "")],
                "start": heard.get("start"), "end": (heard.get("start") or 0) + (heard.get("duration") or 0) if heard else None,
                "first_on_screen": shown_spec and (reaction_state(shown_spec) if shown_spec.get("kind") == "reaction"
                                                   else {"kind": shown_spec.get("kind")}),
                "actions": sorted(actions, key=lambda a: (a.get("t") is None, a.get("t") or 0.0)),
                "learner_turn": turn,
                "describe": _describe(shown_spec, beat),
            })
            before = shown_spec
    plan = {"schema": SCHEMA, "title": lesson.get("title"), "scenes": scenes}
    plan["validation"] = validate(plan, lesson)
    return plan


def _describe(spec, beat) -> str:
    """A screen-reader line for the scene's picture."""
    if not spec:
        return "Words only: " + "; ".join(s.get("show", "") for s in beat.get("steps") or [])
    if spec.get("kind") == "reaction":
        st = reaction_state(spec) or {}
        counts = ", ".join(f"{el} {st['before'][el]} before and {st['after'].get(el, 0)} after" for el in st.get("before", {}))
        return f"Molecules for {st.get('equation')}: {counts}. {st.get('verdict', '')}."
    return f"A {spec.get('kind')} picture."


def validate(plan: dict, lesson: dict | None = None) -> list[dict]:
    """Code checks on a plan. Each finding: {scene, check, what}."""
    found = []
    known = set(ACTIONS)
    for scene in plan.get("scenes") or []:
        sid = scene["scene"]
        for a in scene["actions"]:
            if a["action"] not in known:
                found.append({"scene": sid, "check": "unknown_action", "what": a["action"]})
        times = sorted(a["t"] for a in scene["actions"] if a.get("t") is not None and a["action"] not in ("counter",))
        for i, t in enumerate(times):
            if sum(1 for u in times[i:] if u - t < 1.0) > AT_ONCE:
                found.append({"scene": sid, "check": "too_many_at_once", "what": f"{AT_ONCE}+ changes within 1 s at {t:.1f}s"})
                break
        state = scene.get("first_on_screen") or {}
        if "verdict" in state:
            # the counts are read from the same equation as the balls, so they cannot disagree; what CAN go wrong is
            # an equation code could not read, which the writer drops (writer.reaction_figure)
            if not state.get("equation"):
                found.append({"scene": sid, "check": "reaction_unreadable", "what": "no equation"})
            turn = scene.get("learner_turn")
            if turn and state.get("verdict") == "balanced" and re.search(r"\b(balance|which number|coefficient|how many)\b",
                                                                        str(turn.get("question") or ""), re.I):
                found.append({"scene": sid, "check": "answer_before_question",
                              "what": f"the picture shows the balanced equation while asking: {turn.get('question')}"})
        for a in scene["actions"]:
            if a["action"] in ("reveal", "construct", "focus") and a.get("anchor") and a.get("t") is None \
                    and scene.get("start") is not None:
                found.append({"scene": sid, "check": "anchor_not_heard", "what": a["anchor"]})
    return found


def write(root: Path, lesson: dict | None = None) -> dict:
    """``output/visual_plan.json`` for a finished (narrated) lesson folder; returns the plan."""
    root = Path(root)
    lesson = lesson or json.loads((root / "lesson.json").read_text())
    read = lambda p: json.loads(p.read_text()) if p.exists() else None  # noqa: E731
    plan = visual_plan(lesson, read(root / "timeline.json"), read(root / "output" / "interactions.json"))
    out = root / "output" / "visual_plan.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(plan, ensure_ascii=False, indent=1))
    return plan


def reaction_questions(lesson: dict, log=print) -> int:
    """A beat that hands the learner an equation to balance (its reaction figure has "?" coefficients) and asks no
    card of its own gets one made by CODE: "What number goes in front of NH3?", the right option from
    ``figure_math.balance``, the wrong ones its neighbours, and for each a reason worked out from the atom counts
    ("with 1 NH3 the right side has 1 nitrogen atom, the left has 2"). The module's step 10, a transfer question on
    a different equation, and its "what visual evidence reveals a misunderstanding". Returns how many were added."""
    added = 0
    for ch in lesson.get("chapters") or []:
        for beat in ch.get("beats") or []:
            spec = beat.get("figure") if isinstance(beat.get("figure"), dict) else None
            if beat.get("quiz") or not spec or spec.get("kind") != "reaction":
                continue
            try:
                parsed = figure_math.parse_equation(spec.get("equation", ""))
            except (ValueError, KeyError, TypeError):
                continue
            if not any(sp["unknown"] for side in parsed.values() for sp in side):
                continue
            solved = figure_math.balance(parsed)
            if not solved:
                continue
            # ask about the product: what the learner works out last, after counting the start
            k = 0
            target = parsed["right"][k]
            right_n = solved["right"][k]
            scale = right_n
            choices = sorted({max(1, right_n - 1), right_n, right_n + 1} | ({right_n + 2} if right_n == 1 else set()))[:3]
            why = []
            for n in choices:
                if n == right_n:
                    full = " + ".join(f"{c if c > 1 else ''}{sp['formula']}" for c, sp in zip(solved["left"], parsed["left"]))
                    full += " -> " + " + ".join(f"{c if c > 1 else ''}{sp['formula']}"
                                                for c, sp in zip(solved["right"], parsed["right"]))
                    why.append(f"Yes: {full} has the same atoms on both sides.")
                    continue
                # what goes wrong with n, worked out: no whole numbers fit it, or they do but are not the smallest
                fits = figure_math.balance(parsed, fixed={"right": {k: n}})
                counts = ", ".join(f"{a * n} {el}" for el, a in target["atoms"])
                if fits is None:
                    why.append(f"With {n} {target['formula']} the right side has {counts}; no whole numbers in front "
                               f"of the starting substances give exactly that.")
                else:
                    why.append(f"{n} {target['formula']} can be balanced too, but every number then shares a factor; "
                               f"a balanced equation uses the smallest whole numbers.")
            beat["quiz"] = {"question": f"What number goes in front of {target['formula']}?",
                            "options": [str(n) for n in choices], "answer_index": choices.index(scale),
                            "why": why, "kind": "apply", "made_by": "code (figure_math.balance)",
                            "explain": why[choices.index(scale)]}
            added += 1
            log(f"[visual] beat {beat.get('id')}: a balancing question made by code ({target['formula']}: {right_n})")
    return added
