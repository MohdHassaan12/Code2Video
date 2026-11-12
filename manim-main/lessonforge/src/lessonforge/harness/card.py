"""The teaching card — one page on how THIS topic is taught, filled from sources.

The step between "here are the sources" (``library.build_pack``) and "write the script"
(``writer.write_lesson``). A model reads the numbered passages and fills ten lines
adapted from the CoRe form (Loughran, Mulhall & Berry 2004): the big idea, why it
matters, the reason it is true, the one picture that carries it, what is needed first,
where learners go wrong, the opening question, the route, the questions, and a task to
try by hand. The script that was rejected as dull on 2026-10-08 had none of the lines
"the why" and "the picture": the rule was announced and two pictures were never joined.

Same split as everywhere in the harness — the model writes the content, code owns the
shape and checks what code can check:

* every cited id must be a passage of the pack (a made-up id is dropped and reported);
* the lines a lesson cannot do without must be there (big idea, the why, the picture,
  the opening question, the task);
* the task is at most five steps, uses things from the allowed list, and has every part
  the evidence asks for (what each object stands for, a prediction, what is seen, a
  question that asks why, an answer that carries the reason).

One repair round is given the list of problems; what is still open after it is kept in
``card["problems"]`` and shown, never hidden. A card costs one or two model calls and is
judged by a person in a minute, which is the point: a dull card means a dull video, and
it is far cheaper to find that out here.
"""
from __future__ import annotations

import json
import os
import re
from typing import Any, Callable

from .. import knobs
from . import diagrams, library, skill

LLM = Callable[[str, str], Any]
# 2026-10-12, the owner: "use cheap models and improve the harness". The card cost 0.10 USD a topic on the large model.
# The small one's first card for Friction cited 24 of 25 lines and passed every check, and spread into another idea of
# the chapter; with one small question per item about that (``scope``) and the repair round, its card stays on the
# lesson's idea for 1.4 cents. ``HARNESS_CARD_MODELS`` puts another order.
CARD_MODELS_DEFAULT = "anthropic/claude-haiku-5.5,openai/gpt-5.4-nano,google/gemini-3.8-flash"
REQUIRED = ("big_idea", "the_why", "picture", "opening_question", "try_it")
TRY_KINDS = ("hands", "paper", "simulation")
TRY_KEYS = ("title", "kind", "materials", "stands_for", "predict", "steps", "observe", "question", "expected", "write",
            "in_class", "cites")
MAX_STEPS = 5
CARD_COST_ESTIMATE = 0.20        # USD: about 20k tokens read and 5k written, twice when a repair round runs
#: What a task may ask a learner to pick up (practicum.md). Matched on word starts.
ALLOWED_MATERIALS = ("paper", "pencil", "pen", "ruler", "scale", "scissors", "thread", "string", "coin", "bean", "seed",
                     "button", "rubber band", "glass", "water", "bottle", "ball", "book", "notebook", "torch", "phone",
                     "mirror", "salt", "sugar", "straw", "balloon", "eraser", "marble", "stone", "pebble", "cup", "spoon",
                     "plate", "card", "tape", "chalk", "toothpick", "rice", "dal", "lentil", "clip", "table",
                     "bowl", "cloth", "towel", "tumbler", "lid", "cap", "dice", "die", "counter", "grid", "sheet", "stick",
                     "bangle", "sharpener", "box", "tray", "calculator", "clock", "watch", "timer", "wall", "floor", "hand",
                     "finger", "tile", "dot", "block", "cube", "wire", "magnet", "pin", "nail", "sand", "soil", "leaf",
                     "ice", "oil", "soap", "flour", "lemon", "paper clip", "sticky note", "crayon", "colour", "color")
FORBIDDEN_MATERIALS = ("candle", "match box", "matchbox", "lighter", "flame", "fire", "burner", "stove", "knife", "blade",
                       "razor", "acid", "bleach", "socket", "mains", "plug point", "kerosene", "petrol", "spirit")

SHAPE = """{
 "big_idea": {"text": "one sentence the learner should be able to say afterwards", "cites": ["S1#4"]},
 "objectives": [{"can": "what the learner can DO afterwards, starting with a verb (name, explain, predict, work out)", "level": "remember|understand|apply|analyze|evaluate|create", "checked_by": "opening | q1 | q2 | q3 | try_it: where in this card the learner does exactly this"}],
 "why_it_matters": {"text": "one sentence, to this learner", "cites": []},
 "the_why": {"text": "the REASON it is true, one or two sentences a picture can show", "cites": []},
 "picture": {"text": "the ONE picture: what it looks like at the start and how it changes", "standard": "the standard way this topic is drawn in class, by name, or empty", "cites": []},
 "diagram_ask": "a request to the drawing service for the picture this topic is KNOWN BY (rule 3): the real thing as a labelled diagram, the classic demonstration as one still picture with before and after side by side, or the standard diagram of the method. A picture, never the topic's name, and with no formula, result or rule written in it (the lesson reaches that itself). Empty only when the topic has no such picture",
 "needs_first": [{"text": "something the learner must already have", "cites": []}],
 "mistakes": [{"mistake": "as a learner would make it", "why_it_fails": "one sentence", "cites": []}],
 "opening_question": {"question": "about the big idea, guessable", "guesses": ["what a learner might say"], "answer": "the answer, given later in the lesson", "cites": []},
 "route": [{"move": "question|guess|see|why|name|example|contrast|your_turn|try_it|say_back", "what": "what is shown and what is asked", "cites": []}],
 "questions": [{"question": "makes the learner predict or decide", "options": ["three choices; the wrong ones are the card's mistakes"], "answer_index": 0, "explain": "one sentence with the reason", "cites": []}],
 "try_it": {"title": "a short name", "kind": "hands|paper|simulation", "materials": ["things at home"], "stands_for": "what each object stands for, one line",
            "predict": "the guess to make first", "steps": ["at most five, one action each"], "observe": "what they should see, stated plainly",
            "question": "asks WHY", "expected": "the answer WITH its reason", "write": "the two lines the learner writes or says",
            "in_class": "the same task for 40 students and five minutes: pairs, what goes on the board, the question to ask", "cites": []},
 "leave_out": ["true and nearby, but not for this lesson"],
 "from_lectures": [{"source": "S3", "took": "what you took from this lecture", "left": "what you left, and why"}],
 "uncited": ["each line that came from your own knowledge and not from a passage"]
}"""


def card_models() -> list[str]:
    raw = knobs.get("HARNESS_CARD_MODELS", CARD_MODELS_DEFAULT)
    return [m.strip() for m in raw.split(",") if m.strip()]


def default_llm(temperature: float = 0.4) -> LLM | None:
    """The card model through OpenRouter, metered under its own note. None without a key."""
    key = (os.getenv("OPENROUTER_API_KEY") or "").strip()
    if not key:
        return None
    from ..engine import llm as engine_llm  # noqa: PLC0415

    def call(prompt: str, system: str):
        text = engine_llm.call_openrouter(key, prompt, system, temperature=temperature, models=card_models(),
                                          max_tokens=None, json_object=True, note="card", timeout=240.0)
        return engine_llm.loads_json_lenient(text)
    return call


def enabled(brief: dict) -> bool:
    """A card is made when the brief asks for one, or for every lesson when the flag is set.

    Default OFF: a card is one or two more model calls and reads the network, so turning
    it on is a billing change and a change to what gets written.
    """
    if brief.get("card") is False:
        return False
    return bool(brief.get("card")) or knobs.get("LESSONFORGE_TEACHING_CARD", "").strip() == "1"


def _line(value) -> dict:
    if isinstance(value, dict):
        cites = value.get("cites") if isinstance(value.get("cites"), list) else []
        return {"text": str(value.get("text") or "").strip(), "cites": [str(c).strip() for c in cites if str(c).strip()]}
    return {"text": str(value or "").strip(), "cites": []}


def _cites(value) -> list[str]:
    return [str(c).strip() for c in value if str(c).strip()] if isinstance(value, list) else []


def _strings(value, limit: int = 12) -> list[str]:
    return [str(v).strip() for v in value if str(v).strip()][:limit] if isinstance(value, list) else []


def shape(raw: dict) -> dict:
    """The model's answer in the card's shape: every key present, nothing of an unexpected type."""
    raw = raw if isinstance(raw, dict) else {}
    task = raw.get("try_it") if isinstance(raw.get("try_it"), dict) else {}
    opening = raw.get("opening_question") if isinstance(raw.get("opening_question"), dict) else {}
    card = {
        "big_idea": _line(raw.get("big_idea")), "why_it_matters": _line(raw.get("why_it_matters")),
        "the_why": _line(raw.get("the_why")),
        "objectives": [{"can": str(o.get("can") or "").strip()[:200], "level": str(o.get("level") or "").strip().lower(),
                        "checked_by": re.sub(r"[^a-z0-9_]", "", str(o.get("checked_by") or "").strip().lower().replace(" ", "_"))}
                       for o in (raw.get("objectives") or []) if isinstance(o, dict) and str(o.get("can") or "").strip()][:4],
        "picture": {**_line(raw.get("picture")), "standard": str((raw.get("picture") or {}).get("standard") or "").strip()[:80]
                    if isinstance(raw.get("picture"), dict) else ""},
        "diagram_ask": re.sub(r"\s+", " ", str(raw.get("diagram_ask") or "")).strip()[:300],
        "needs_first": [_line(v) for v in (raw.get("needs_first") or []) if _line(v)["text"]][:5],
        "mistakes": [{"mistake": str(m.get("mistake") or "").strip(), "why_it_fails": str(m.get("why_it_fails") or "").strip(),
                      "cites": _cites(m.get("cites"))}
                     for m in (raw.get("mistakes") or []) if isinstance(m, dict) and str(m.get("mistake") or "").strip()][:4],
        "opening_question": {"question": str(opening.get("question") or "").strip(), "guesses": _strings(opening.get("guesses"), 4),
                             "answer": str(opening.get("answer") or "").strip(), "cites": _cites(opening.get("cites"))},
        "route": [{"move": str(r.get("move") or "").strip(), "what": str(r.get("what") or "").strip(), "cites": _cites(r.get("cites"))}
                  for r in (raw.get("route") or []) if isinstance(r, dict) and str(r.get("what") or "").strip()][:10],
        "questions": [],
        "try_it": {"title": str(task.get("title") or "").strip(),
                   "kind": task.get("kind") if task.get("kind") in TRY_KINDS else "paper",
                   "materials": _strings(task.get("materials"), 8), "stands_for": str(task.get("stands_for") or "").strip(),
                   "predict": str(task.get("predict") or "").strip(), "steps": _strings(task.get("steps"), 8),
                   "observe": str(task.get("observe") or "").strip(), "question": str(task.get("question") or "").strip(),
                   "expected": str(task.get("expected") or "").strip(), "write": str(task.get("write") or "").strip(),
                   "in_class": str(task.get("in_class") or "").strip(), "cites": _cites(task.get("cites"))},
        "leave_out": _strings(raw.get("leave_out"), 6),
        "from_lectures": [{"source": str(f.get("source") or "").strip(), "took": str(f.get("took") or "").strip(),
                           "left": str(f.get("left") or "").strip()}
                          for f in (raw.get("from_lectures") or []) if isinstance(f, dict)][:5],
        "uncited": _strings(raw.get("uncited"), 12),
    }
    for q in (raw.get("questions") or []):
        if not isinstance(q, dict) or not str(q.get("question") or "").strip():
            continue
        options, answer = _strings(q.get("options"), 4), q.get("answer_index")
        if len(options) >= 2 and isinstance(answer, int) and 0 <= answer < len(options):
            card["questions"].append({"question": str(q["question"]).strip(), "options": options, "answer_index": answer,
                                      "explain": str(q.get("explain") or "").strip(), "cites": _cites(q.get("cites"))})
    card["questions"] = card["questions"][:3]
    return card


def _every_cite(card: dict):
    """(holder, list) for every cites list in the card, so one loop can check or clean them all."""
    for key in ("big_idea", "why_it_matters", "the_why", "picture", "opening_question", "try_it"):
        yield key, card[key]["cites"]
    for key in ("needs_first", "mistakes", "route", "questions"):
        for i, item in enumerate(card[key]):
            yield f"{key}[{i}]", item["cites"]


def check(card: dict, pack: dict) -> list[str]:
    """What is wrong with a card that code can see. Removes cited ids that are not in the pack."""
    problems = []
    known = {c["id"] for c in pack.get("chunks", [])}
    invented = []
    for where, cites in _every_cite(card):
        bad = [c for c in cites if c not in known]
        if bad:
            invented.append(f"{where}: {', '.join(bad[:3])}")
            cites[:] = [c for c in cites if c in known]
    if invented:
        problems.append("cited passages that do not exist (removed): " + "; ".join(invented[:4]))
    for key in REQUIRED:
        value = card[key]
        if not (value.get("text") or value.get("question") or value.get("steps")):
            problems.append(f"'{key}' is empty")
    if known and card["the_why"]["text"] and not card["the_why"]["cites"] and "the_why" not in " ".join(card["uncited"]).lower():
        problems.append("'the_why' cites no passage: cite the passage that gives the reason, or list it under 'uncited'")
    why, idea = set(library.tokens(card["the_why"]["text"])), set(library.tokens(card["big_idea"]["text"]))
    if why and idea and len(why & idea) / len(why | idea) > 0.8:
        problems.append("'the_why' restates the big idea: it must give the reason the idea is true")
    task = card["try_it"]
    if len(task["steps"]) > MAX_STEPS:
        problems.append(f"the task has {len(task['steps'])} steps: at most {MAX_STEPS}")
    for key, what in (("stands_for", "what each object stands for"), ("predict", "a prediction to make first"),
                      ("observe", "what the learner should see"), ("question", "a question that asks why"),
                      ("expected", "the answer with its reason"), ("in_class", "the version for a full class")):
        if task["steps"] and not task[key]:
            problems.append(f"the task is missing {what} ('{key}')")
    if task["expected"] and not re.search(r"\b(because|since|so that|kyunki|isliye|as each|as every|which means|therefore)\b",
                                           task["expected"], re.I):
        problems.append("the task's 'expected' gives an answer without its reason")
    for item in task["materials"]:
        low = item.lower()
        if any(re.search(rf"\b{re.escape(bad)}", low) for bad in FORBIDDEN_MATERIALS):
            problems.append(f"the task uses '{item}': nothing that burns, cuts or uses mains electricity")
        elif not any(re.search(rf"\b{re.escape(ok)}", low) for ok in ALLOWED_MATERIALS):
            problems.append(f"the task uses '{item}', which is not on the list of things found at home or in a school bag")
    if not card["mistakes"]:
        problems.append("no learner mistakes: give the two to four that matter most")
    problems += _objective_problems(card)
    if len(card["route"]) < 5:
        problems.append("the route has fewer than five moves")
    return problems


SCOPE_SYSTEM = """You check ONE thing about a teaching card: whether each of its mistakes and questions is about the card's OWN
idea. You are given the lesson's goal, the card's big idea and its reason, what the card says it leaves out, and the
mistakes and questions, numbered (m1, m2, …, q1, q2, …).

For EVERY numbered item answer:
- "about": "this idea" when a learner holding the mistake, or answering the question, is thinking about the big idea or
  its reason as stated; "another idea" when it is about something else that is true and nearby (another law of the same
  chapter, a finer distinction the big idea does not make, something the card says it leaves out).
- "which": for "another idea", that idea in a few words; else "".
In doubt, "this idea". Answer in JSON only: {"items": {"m1": {"about": "this idea", "which": ""}, "q2": {"about": "another idea", "which": "..."}}}"""


def scope(card: dict, brief: dict, llm: LLM, log=print) -> list[str]:
    """Mistakes and questions that are about ANOTHER idea than the card's own, as problems for the card's repair round.

    A small model's card for "why a moving object slows down, and what makes friction larger or smaller" listed
    "coefficients of static and kinetic friction" under what it leaves out and then gave, as two of its four mistakes and
    one of its three questions, static against sliding friction (2026-10-12): true, in the chapter, and another lesson.
    Words cannot tell this (a check on the words of 'leave_out' called 14 of the library's 18 good cards wrong: a lesson
    on convection leaves out "convection currents in sea breezes"), so one small question is asked per item, and code
    acts only on an answer that names the other idea. Nothing here raises: no answer is no problem found.
    """
    items = {f"m{i}": f"mistake: {m.get('mistake', '')} (why it fails: {m.get('why_it_fails', '')})" for i, m in enumerate(card["mistakes"], 1)}
    items.update({f"q{i}": f"question: {q.get('question', '')} options: {q.get('options', '')}" for i, q in enumerate(card["questions"], 1)})
    if not items:
        return []
    prompt = "\n".join([f"GOAL OF THE LESSON: {brief.get('goal') or brief.get('topic') or ''}", f"BIG IDEA: {card['big_idea']['text']}",
                        f"ITS REASON: {card['the_why']['text']}",
                        f"LEFT OUT: {'; '.join(str(x) for x in card.get('leave_out') or []) or '(nothing listed)'}", ""]
                       + [f"{tag}. {text}" for tag, text in items.items()])
    try:
        answer = llm(prompt, SCOPE_SYSTEM)
        said = answer.get("items") if isinstance(answer, dict) else None
    except Exception as exc:  # noqa: BLE001
        log(f"[card] nobody to check its scope ({type(exc).__name__})")
        return []
    problems = []
    for tag, text in items.items():
        verdict = (said or {}).get(tag) if isinstance(said, dict) else None
        which = str((verdict or {}).get("which") or "").strip() if isinstance(verdict, dict) else ""
        if isinstance(verdict, dict) and str(verdict.get("about") or "").strip().lower().startswith("another") and which:
            name = f"mistake {tag[1:]}" if tag[0] == "m" else f"question {tag[1:]}"
            problems.append(f"{name} is about another idea ({which[:80]}), not this lesson's: replace it with one about the big idea")
    return problems


def _objective_problems(card: dict) -> list[str]:
    """Objectives a learner can be SEEN to meet: a level from the closed list, and a place in the card where it is done.

    The alignment is the point (what is aimed at, what is done, what is asked are the
    same thing): an objective that nothing in the lesson makes the learner do is a wish.
    """
    problems, objectives = [], card.get("objectives") or []
    places = (["opening"] if card["opening_question"]["question"] else []) + [f"q{i}" for i in range(1, len(card["questions"]) + 1)] \
        + (["try_it"] if card["try_it"]["steps"] else [])
    if not 2 <= len(objectives) <= 4:
        problems.append("give two to four 'objectives': what the learner can DO afterwards, each starting with a verb")
    for n, o in enumerate(objectives, 1):
        if o["level"] not in library.BLOOM:
            problems.append(f"objective {n} has no level: one of {', '.join(library.BLOOM)}")
        if o["checked_by"] not in places:
            problems.append(f"objective {n} is checked by nothing in the card: name where the learner does it ({', '.join(places)})")
    if objectives and all(o["level"] == "remember" for o in objectives if o["level"] in library.BLOOM):
        problems.append("every objective is recall: at least one must be understand (explain why) or apply (carry it out)")
    return problems


def _brief_lines(brief: dict, pack: dict | None = None) -> str:
    read = str((pack or {}).get("topic") or "")
    typed = str(brief.get("topic", ""))
    lines = [f"TOPIC: {read} (typed by the requester as “{typed}”)" if read and read.lower() != typed.lower() else f"TOPIC: {typed}", f"FOR: {brief.get('audience', '')} (starting point: {brief.get('level', 'standard')})",
             f"AFTER THE LESSON THEY CAN: {brief.get('goal', '')}",
             f"LESSON LENGTH: about {brief.get('duration_minutes') or 6} minutes of narrated animation"]
    if brief.get("misconception"):
        lines.append(f"THE REQUESTER SAYS LEARNERS OFTEN: {brief['misconception']}")
    if brief.get("context"):
        lines.append(f"THE REQUESTER SUGGESTED AN EXAMPLE: {brief['context']} (use only what is simpler than the idea; no story)")
    return "\n".join(lines)


def make_card(brief: dict, pack: dict, llm: LLM, log=print, plans: dict | None = None) -> dict:
    """Fill the card for a brief from its pack. Always returns a card in the full shape.

    ``plans`` are the sources' lesson plans (``library.blueprints``): how each one orders and
    builds the topic. The passages say what the sources say; the plans say how they teach.
    """
    system = ("You prepare a lesson the way an experienced teacher does before writing a word of it: by writing down, on "
              "one page, how THIS topic is best taught. You are given the teaching skill you work by, the brief, and "
              "numbered passages from the sources. Return ONLY JSON.\n\n" + skill.for_card())
    sources = library.pack_text(pack) if pack.get("chunks") else ("SOURCES: none could be gathered. Fill the card from your own "
                                                                 "knowledge and list every line under 'uncited'.")
    planned = library.blueprint_text(plans or {}, pack)
    if planned:
        sources = planned + "\n\n" + sources
    prompt = (f"{_brief_lines(brief, pack)}\n\n{sources}\n\nFill the teaching card. Cite passage ids exactly as written above "
              f"(for example \"S1#4\"). Say everything in your own words.\n\nJSON shape:\n{SHAPE}")
    card = shape(llm(prompt, system))
    problems = check(card, pack) + scope(card, brief, llm, log=log)
    if problems:
        log(f"[card] {len(problems)} thing(s) to fix: " + "; ".join(problems)[:300])
        fixed = shape(llm(f"{prompt}\n\nYOUR FIRST CARD:\n{json.dumps(card, ensure_ascii=False)}\n\nFIX THESE and return the whole "
                          "card again, changing nothing that was not asked for:\n- " + "\n- ".join(problems), system))
        still = check(fixed, pack) + scope(fixed, brief, llm, log=log)
        if len(still) <= len(problems):           # a repair improves or stands aside
            card, problems = fixed, still
    # How the lecturers talk is the readers' description, carried as it is: a manner for the writer to take up.
    card["teacher_talk"] = [line for sid, plan in (plans or {}).items() for line in plan.get("manner") or []][:6]
    card["source_flows"] = {sid: [step["role"] for step in plan["flow"]] for sid, plan in (plans or {}).items()}
    # A card's sources are the ones it STANDS ON: those at least one line cites. A lesson on Pythagoras' theorem
    # listed a Python tutorial and a film explainer under "From sources" because they had been fetched.
    used = {cite.split("#")[0] for _, cites in _every_cite(card) for cite in cites}
    unused = [s for s in pack.get("sources", []) if s["id"] not in used]
    if unused and used:
        log(f"[card] {len(unused)} fetched source(s) that no line cites are not listed: " + "; ".join(s["title"][:50] for s in unused))
    card.update(topic=str(pack.get("topic") or brief.get("topic") or ""), asked=str(brief.get("topic") or ""), klass=pack.get("klass"),
                sources=[{k: s.get(k, "") for k in ("id", "kind", "title", "url", "note")}
                         for s in pack.get("sources", []) if s["id"] in used or not used],
                problems=problems, skill_version=skill.card_version(), pack_digest=pack.get("digest", ""))
    cited = sum(1 for _, cites in _every_cite(card) if cites)
    total = sum(1 for _ in _every_cite(card))
    log(f"[card] {cited} of {total} lines cite a passage; {len(card['mistakes'])} mistake(s); task: {card['try_it']['kind']}, "
        f"{len(card['try_it']['steps'])} step(s)" + (f"; still open: {len(problems)}" if problems else ""))
    return card


def picture_holds() -> bool:
    """Whether the writer is told what a finished drawing HOLDS (``HARNESS_PICTURE_HOLDS``, on unless "0")."""
    return (knobs.get("HARNESS_PICTURE_HOLDS") or "1").strip() != "0"


def add_holds(ready: dict | None, log=print) -> bool:
    """Read what a prepared drawing holds from the drawing itself and keep it on ``ready`` (``"holds"``). True when it has one.

    The writer was told what a drawing was ASKED for and never what came back, so it wrote "faint squares", "a six
    centimetre base" and "the grey arrow is blocked" over drawings that have none of them: every one of the three
    lessons read on 2026-10-10. Rewriting such words afterwards was tried and made four beats of thirteen worse
    (``compose.mending``); telling the writer costs one look per drawing, kept beside it (``vision_review.holds``).
    """
    if not ready or not picture_holds():
        return False
    if isinstance(ready.get("holds"), dict):
        return True
    from . import vision_review  # noqa: PLC0415 - a judge over the network; only when a drawing is there to read
    figure = ({"kind": "picture", "file": ready["file"]} if ready.get("shown") == "whole" and ready.get("file")
              else {"kind": "diagram", "manifest": ready.get("manifest")})
    try:
        held = vision_review.holds(figure, log=log)
    except Exception as exc:  # noqa: BLE001 - a reading is a help: the card and its drawing stand without it
        log(f"[card] the drawing was not read ({type(exc).__name__}: {str(exc)[:100]})")
        return False
    if not held:
        return False
    ready["holds"] = held
    log(f"[card] the drawing was read: {len(held.get('things') or [])} thing(s) and {len(held.get('print') or [])} printed word(s) "
        "the script may speak of as being in it")
    return True


def holds_block(ready: dict) -> str:
    """What the writer is told about what the finished drawing holds; '' when it was not read."""
    held = ready.get("holds") if isinstance(ready.get("holds"), dict) else None
    if not held:
        return ""
    return (" WHAT IS IN IT, read from the finished drawing itself: " + "; ".join(held.get("things") or ["(nothing listed)"])
            + (". PRINTED IN IT: " + "; ".join(f"“{p}”" for p in held["print"]) if held.get("print") else ". Nothing is printed in it")
            + ". The drawing will not change, so the words fit it. Speak of a thing as being in the picture ONLY if it is in "
            "this list: no grid, colour, arrow, label or number that the list does not have. A number the lesson needs is "
            "tied ONCE to a letter the drawing prints (“the base, marked b, is six centimetres”) and used freely after "
            "that. Whatever else the lesson needs (another case, an experiment, a thing to try at home) is said as "
            "something to imagine, draw or try, never as something to look at.")


def diagram_block(ready: dict) -> str:
    """What the writer is told about a drawing that is ready, whoever asked for it (a card, or the topic itself)."""
    # The second lesson made with a diagram (2026-10-09) drew the cell twice: a model-written scene of
    # polygons for the first two minutes ("a thin edge, a round centre" before the parts were named) and
    # the real drawing after it. "On every beat that talks about its parts" had been read as "once the
    # parts have names".
    return ("A LABELLED DIAGRAM IS READY — an exact drawing with its parts cut out, so each can be shown alone: "
            f"{ready.get('ask', '')}. It is the lesson's ONE picture of this thing, from the first beat that shows "
            "the thing to the last: on every such beat give \"figure\": {\"kind\": \"diagram\"} (the same each "
            "time, so the picture stays). NEVER draw the same thing again as a scene, in any style and at any "
            "stage: a learner shown two different drawings of it cannot tell which one it is. Before a part has "
            "its name, point at it all the same (the narration may call it “yeh patli si boundary”; the step "
            "still carries its focus). EVERY step that is about a part carries \"focus\" with one of these exact "
            "words: " + ", ".join(ready["parts"])
            + ". When that step is said, the part stays lit, the rest fades and its label is written. Name at most "
            "eight parts in the whole lesson, each in the sentence that explains what it does. A scene is allowed "
            "only for a DIFFERENT object that the drawing does not contain (another kind of cell beside it, an "
            "experiment), never for the thing itself or a simpler version of it."
            + (f" WHAT IT SHOWS: {ready['shows']} Build the lesson's example on this picture: do not invent another."
               if ready.get("shows") else "")
            + holds_block(ready))


def picture_block(ready: dict) -> str:
    """What the writer is told about a drawing that is shown whole (nothing in it can be lit)."""
    return ("A DRAWING IS READY — the picture this topic is known by, drawn the way a textbook prints it: "
            f"{ready.get('ask', '')}. It is the lesson's picture of this. On EVERY beat that talks about it give "
            "\"figure\": {\"kind\": \"diagram\"} (the same each time, so it stays up) and NEVER write a scene of the same "
            "thing. It is shown whole, with its own small words on it, so give no \"focus\": each sentence says where to "
            "look in plain words (“the coin on the card”, “the second glass”), and the step's on-screen text carries "
            "every word the learner must read. A scene is allowed only for a DIFFERENT object the drawing does not show."
            + (f" It has {len(ready['panels'])} panels (before, then after). Only the FIRST is on screen at the start: the "
               "step that tells what happened gives \"focus\": \"panel2\" and the next panel appears with those words. "
               "Never describe a later panel before the step that brings it in: the learner has not seen it yet."
               if len(ready.get("panels") or []) >= 2 else "")
            + (f" WHAT IT SHOWS: {ready['shows']} Build the lesson's example on this picture: do not invent another."
               if ready.get("shows") else "")
            + holds_block(ready))


def block_for(ready: dict | None) -> str:
    """The writer's block for a prepared drawing in whichever way it is shown; '' for none."""
    if not ready:
        return ""
    return picture_block(ready) if ready.get("shown") == "whole" else diagram_block(ready) if ready.get("parts") else ""


def for_writer(card: dict) -> str:
    """The card as the script writer reads it: every line the script must use, no passage text."""
    opening, task = card["opening_question"], card["try_it"]
    lines = ["TEACHING CARD FOR THIS TOPIC (built from the textbook, lectures and research on learners' mistakes; "
             "it outranks your own first idea of how to teach this):",
             f"BIG IDEA: {card['big_idea']['text']}",
             f"THE WHY — the lesson must leave the learner able to say this: {card['the_why']['text']}",
             f"THE PICTURE — the lesson's one example and figure; change it as the idea grows, do not replace it: {card['picture']['text']}"
             + (f" It is built on the standard way this is drawn in class ({card['picture']['standard']}): draw it the way the "
                "learner's textbook and notebook do, then let it move." if card["picture"].get("standard") else ""),
             f"OPENING QUESTION — the first two sentences of the lesson; ask for a guess; do not answer yet: {opening['question']}"
             + (f" (they may guess: {'; '.join(opening['guesses'])})" if opening["guesses"] else "")
             + (f" ANSWER, given by name when the example is worked: {opening['answer']}" if opening["answer"] else "")]
    if card.get("objectives"):
        where = {"opening": "the opening question", "try_it": "the try-it task"}
        lines.append("AFTER THE LESSON THE LEARNER CAN (each is DONE by the learner somewhere in the lesson, not only told):\n"
                     + "\n".join(f"  {n}. {o['can']} [{o['level']}; done in {where.get(o['checked_by'], 'question ' + o['checked_by'][1:])}]"
                                 for n, o in enumerate(card["objectives"], 1)))
    if card.get("teacher_talk"):
        lines.append("HOW TEACHERS OF THIS TOPIC TALK (described from the lectures; a manner to take up, never words to copy): "
                     + "; ".join(card["teacher_talk"]))
    hint = card.get("figure_hint")
    if isinstance(hint, dict) and hint.get("kind"):
        # A knowledge-base concept whose proven picture is a figure code draws exactly: the writer uses that kind
        # on every beat about it, so the picture changes as the idea grows instead of being replaced.
        lines.append(f"THE FIGURE — draw this lesson's picture with the \"{hint['kind']}\" figure on every beat about it "
                     f"(the same kind each time, so it CHANGES instead of being replaced). A good start: "
                     f"{json.dumps(hint, ensure_ascii=False)}. Do not write a scene of the same thing.")
    ready = card.get("diagram") or {}
    if ready.get("shown") == "whole":
        lines.append(picture_block(ready))
    elif ready.get("parts"):
        lines.append(diagram_block(ready))
    if card["needs_first"]:
        lines.append("THEY NEED FIRST: " + "; ".join(n["text"] for n in card["needs_first"]))
    if card["mistakes"]:
        lines.append("WHERE LEARNERS GO WRONG (the wrong choices in your questions; state and break the first one once):\n"
                     + "\n".join(f"  - {m['mistake']} — fails because {m['why_it_fails']}" for m in card["mistakes"]))
    if card["route"]:
        lines.append("ROUTE (the order of moves for this topic):\n"
                     + "\n".join(f"  {i}. [{r['move']}] {r['what']}" for i, r in enumerate(card["route"], 1)))
    if card["questions"]:
        lines.append("QUESTIONS WORTH ASKING:\n" + "\n".join(
            f"  - {q['question']} → {' | '.join(q['options'])} (right: {q['options'][q['answer_index']]})" for q in card["questions"]))
    if task["steps"]:
        lines.append("TRY IT YOURSELF — set this in two or three spoken sentences where practice ends (what to take, what to "
                     f"predict, the question); never give its answer: take {', '.join(task['materials']) or 'paper and pencil'}; "
                     f"{' '.join(task['steps'])} What they guess before trying it: {task['predict']} What they find out: {task['question']}")
    if card["leave_out"]:
        lines.append("LEAVE OUT: " + "; ".join(card["leave_out"]))
    return "\n".join(lines)


def markdown(card: dict) -> str:
    """The card as a person reads it."""
    def cited(cites):
        return f" `{', '.join(cites)}`" if cites else ""
    opening, task = card["opening_question"], card["try_it"]
    out = [f"# Teaching card: {card.get('topic', '')}", "",
           f"**Big idea.** {card['big_idea']['text']}{cited(card['big_idea']['cites'])}", "",
           f"**Why it matters.** {card['why_it_matters']['text']}{cited(card['why_it_matters']['cites'])}", "",
           f"**The why.** {card['the_why']['text']}{cited(card['the_why']['cites'])}", "",
           "**After the lesson the learner can.**"] + [f"  - {o['can']} *({o['level']}; checked by {o['checked_by']})*"
                                                         for o in card.get("objectives") or []] + ["",
           f"**The picture.** {card['picture']['text']}{cited(card['picture']['cites'])}"
           + (f" *Standard form in class:* {card['picture']['standard']}." if card["picture"].get("standard") else ""), "",
           f"**Opening question.** {opening['question']}{cited(opening['cites'])}",
           f"  - guesses: {'; '.join(opening['guesses'])}", f"  - answer: {opening['answer']}", "",
           "**Needs first.**"] + [f"  - {n['text']}{cited(n['cites'])}" for n in card["needs_first"]] + ["", "**Where learners go wrong.**"]
    out += [f"  - {m['mistake']} *Fails because* {m['why_it_fails']}{cited(m['cites'])}" for m in card["mistakes"]]
    out += ["", "**Route.**"] + [f"  {i}. *{r['move']}*: {r['what']}{cited(r['cites'])}" for i, r in enumerate(card["route"], 1)]
    out += ["", "**Questions.**"] + [f"  - {q['question']} [{' | '.join(q['options'])}] right: {q['options'][q['answer_index']].rstrip('.')}. {q['explain']}"
                                     for q in card["questions"]]
    out += ["", f"**Try it yourself: {task['title']}** ({task['kind']})", f"  - you need: {', '.join(task['materials'])}",
            f"  - what stands for what: {task['stands_for']}", f"  - predict first: {task['predict']}"]
    out += [f"  - step {i}: {s}" for i, s in enumerate(task["steps"], 1)]
    out += [f"  - you should see: {task['observe']}", f"  - question: {task['question']}", f"  - answer: {task['expected']}",
            f"  - write or say: {task['write']}", f"  - in class: {task['in_class']}{cited(task['cites'])}", "",
            "**Leave out.** " + "; ".join(card["leave_out"]), "", "**From the lectures.**"]
    out += [f"  - {f['source']}: took {f['took']}; left {f['left']}" for f in card["from_lectures"]]
    if card["uncited"]:
        out += ["", "**From the model's own knowledge (no passage).**"] + [f"  - {u}" for u in card["uncited"]]
    if card.get("problems"):
        out += ["", "**Still open after the checks.**"] + [f"  - {p}" for p in card["problems"]]
    out += ["", "**Sources.**"] + [f"  - {s['id']} [{s['kind']}] {s['title']}" + (f" — {s['url']}" if s.get("url") else "")
                                   for s in card.get("sources", [])]
    return "\n".join(out)


def add_diagram(card: dict, brief: dict, log=print) -> bool:
    """Fetch and take apart the diagram a card asks for. True when the card gained one.

    Done here, before the script is written, because the writer has to be told which parts
    it can point at. Skipped silently when the card already has one whose files are still
    there, or no diagram service is configured.

    Whether a lesson gets a drawing is NOT left to the card's model. The first lesson made
    by the pipeline alone after the owner asked for "designing what images are needed and
    calling the image generation API" (the water cycle, 2026-10-09) asked the service for
    nothing: its card described a landscape for a model to animate and left ``diagram_ask``
    empty, a lesson with a card never looked the topic's picture up, and all five pictures
    were scenes written by a model, one of which stopped the render. So: the card's own
    request first; when it has none, or that drawing cannot be used, the picture the topic
    is known by (``diagrams.for_brief``), told what the card's one picture is.
    """
    ask = card.get("diagram_ask") or ""
    have = card.get("diagram") or {}
    if card.get("no_drawing"):
        return False          # a knowledge-base card whose picture is an exact built-in figure (``figure_hint``)
    if (have.get("manifest") and os.path.isfile(have["manifest"])) or not diagrams.available():
        return False
    language = "hi" if str(brief.get("language", "")).lower() in ("hi-in", "hi") else "en"
    klass = library.school_class(brief) or card.get("klass")
    ready = None
    if card.get("concept") and card.get("picture_asks"):
        from . import concepts  # noqa: PLC0415
        ready = concepts.best_picture(card, brief, log=log)          # every candidate drawn once, the best one kept
    if not ready and ask:
        ready = diagrams.prepare_checked(ask, klass, language, log=log)      # drawn, taken apart, looked at
    if not ready and diagrams.topic_pictures():
        asked = {**brief, "topic": card.get("topic") or brief.get("topic") or "",
                 "picture_plan": " ".join(str((card.get("picture") or {}).get(k) or "") for k in ("standard", "text")).strip()}
        if library.school_class(asked) is None and klass:
            asked["subject"] = f"{asked.get('subject') or ''} class {klass}".strip()      # where school_class reads it
        ready = diagrams.for_brief(asked, log=log)
    if not ready:
        card.pop("diagram", None)
        return False
    card["diagram"] = ready          # "shown": "parts" (a step lights what it names) or "whole" (the drawing as it is)
    return True


def prepare(brief: dict, llm: LLM | None = None, log=print, refresh: bool = False) -> tuple[dict | None, dict]:
    """Sources → pack → card for one brief, and the topic graph updated. (None, pack) without a model.

    A topic the concept knowledge base knows (``harness/concepts.py``) takes its card from there: no sources are
    read and no model is asked, so every lesson on it explains the idea the same way.
    """
    from . import concepts  # noqa: PLC0415 - concepts imports this module
    entry = None if refresh else concepts.find(brief, log=log)
    if entry:
        made = concepts.as_card(entry, brief)
        log(f"[card] the knowledge base's card for “{entry['id']}” ({entry.get('status', '')}, {entry.get('source', '')}): "
            "no sources read, no model asked")
        add_diagram(made, brief, log)
        return made, {"topic": made["topic"], "chunks": [], "sources": [], "digest": f"concept:{entry['id']}",
                      "warnings": [], "concept": entry["id"]}
    pack = library.build_pack(brief, log=log, refresh=refresh)
    # A card says how the TOPIC is taught, in English, for a class: the Hinglish and the English
    # lesson on it stand on the same one. Kept beside the pack; made again when the sources or
    # the skill have changed.
    saved = library.pack_folder(brief) / "card.json"
    if saved.is_file() and not refresh:
        try:
            kept = json.loads(saved.read_text(encoding="utf-8"))
            if kept.get("pack_digest") == pack.get("digest") and kept.get("skill_version") == skill.card_version():
                log("[card] the library's card for this topic (same sources, same skill)")
                if add_diagram(kept, brief, log):
                    saved.write_text(json.dumps(kept, indent=1, ensure_ascii=False), encoding="utf-8")
                return kept, pack
        except ValueError:
            pass
    if llm is None:
        llm = default_llm()
        if llm is not None:
            from .. import spend  # noqa: PLC0415
            spend.ensure_credit(CARD_COST_ESTIMATE, "a teaching card")   # refuse here, not half-way through a lesson
    if llm is None:
        log("[card] no model configured: sources gathered, no card made")
        return None, pack
    plans = library.blueprints(pack, library.pack_folder(brief), log=log)      # cheap, cached beside the pack
    made = make_card(brief, pack, llm, log=log, plans=plans)
    add_diagram(made, brief, log)
    try:
        saved.write_text(json.dumps(made, indent=1, ensure_ascii=False), encoding="utf-8")
        library.graph_add(pack, made)
    except OSError:
        pass
    return made, pack
