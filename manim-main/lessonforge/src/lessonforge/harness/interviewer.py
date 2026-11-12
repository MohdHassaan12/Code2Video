"""Topic-specific Socratic questions: code decides WHAT to ask, a model decides HOW.

The deterministic intake (``intake.py``) asks the same wording for every topic —
"What do learners usually get wrong here?" — and leaves the requester to invent the
answer. Tested on a real request ("Trigonometric equations" for class 9, Hinglish) it
collected "You decide" twice and a goal of "they should do problems on trigonometry",
and the writer was handed those strings as the running example and the known mistake.

Here the split is the one the rest of the pipeline uses. ``intake.next_question``
still decides which FIELD is missing and in what order, so the brief stays a fixed
contract and the conversation always terminates. A fast model then writes that
question for THIS topic and THESE learners:

* the wording and the reason name the topic ("Do they already know the sin, cos, tan
  ratios, or is this their first meeting with them?");
* free-text fields come with three or four complete, concrete answers to tap — the
  usual mistakes for this topic, running examples these learners recognise, goals
  that can be checked — and the requester can still type their own;
* fixed choices keep their values and labels; only the hint is rewritten to say what
  that choice would mean for this topic;
* an answer too vague to build a lesson on is pushed back on once: a goal with no
  checkable action is re-asked with sharper options built from what the requester
  said; a topic that is a whole chapter gets a narrowing question once the audience
  is known;
* anything else the answer reveals (class, language, a mistake they mentioned) is
  recorded so it is not asked again.

Everything the model returns is validated against the base question; a slow, failed
or malformed call falls back to the deterministic wording, so the intake never
blocks on a provider.
"""
from __future__ import annotations

import json
import os
import re
from typing import Any, Callable

from .. import knobs
from . import intake

LLM = Callable[[str, str], Any]
INTAKE_MODELS_DEFAULT = "google/gemini-3.5-flash-lite,google/gemini-2.5-flash,openai/gpt-5.4-nano"
#: fields whose question a model writes; the rest (voice style, language) are generic by nature.
MODEL_FIELDS = ("focus", "audience", "level", "goal", "framework", "duration_minutes", "context", "misconception")
#: free-text fields whose answer may be pushed back on once when it is too vague.
SHARPEN_FIELDS = ("topic", "goal")
_ENUMS = {
    "level": [o["value"] for o in intake.LEVELS],
    "language": [o["value"] for o in intake.LANGUAGES],
    "style": [o["value"] for o in intake.STYLES],
}
_FIELD_MEANING = {
    "focus": "the ONE idea inside the topic this video should teach (the topic given is too broad for one video)",
    "audience": "who the video is for: class/age, and anything about them that changes how to explain",
    "level": "how much these learners already know about THIS topic (decides where the explanation starts)",
    "goal": "what the learner will be able to DO after watching — an action that can be checked",
    "framework": ("which kind of video to make — how it opens and unfolds for THIS topic. The requester is not a "
                  "teaching expert and is choosing by what they would SEE"),
    "duration_minutes": "how long the video should be",
    "context": ("ONE simple example that shows the idea directly: a single everyday object, or the thing itself, with "
                "small numbers. Not a story or a setting. Every part of it must stand for part of the idea"),
    "misconception": "the mistake learners usually make on this topic, to be confronted in the video",
}
_DELEGATE = re.compile(
    r"^\s*(?:(?:you|u|aap|tum)\s+(?:can\s+)?(?:decide|choose|pick|select)(?:\s+(?:it|yourself|for me))?|up to (?:you|u)|"
    r"your (?:choice|call)|anything(?: is fine| works)?|any|whatever|no idea|not sure|i ?do(?:n'?t| not) know|idk|"
    r"decide yourself|as you (?:like|wish|think)|you know best|surprise me)\s*[.!]*\s*$", re.I)

SYSTEM = """You are the intake interviewer of a tool that makes narrated, animated lesson videos for school
students in India. You interview the REQUESTER (a teacher or content maker), one question at a time, the way a
good instructional designer would: every question is about THIS topic and THESE learners, says what in the video
depends on the answer, and offers concrete choices so it can be answered with one tap. Never ask a generic form
question. Plain English, no flattery, no emojis.

Code has already decided which field must be asked next. Return ONLY JSON:
{
 "learned": {},     // other facts the requester's LAST ANSWER states in their own words (allowed keys are listed
                    // in the request; fixed-choice keys must use an allowed value). {} when there are none.
                    // Never infer something they did not say.
 "unclear": null,   // or one sentence, addressed to the requester, saying what is missing — ONLY when PUSH-BACK
                    // is allowed and the last answer cannot be built on: a "topic" that is a whole subject or
                    // chapter rather than one teachable idea, or a "goal" naming no checkable action ("understand
                    // X", "learn X", "do problems on X"). A short but specific answer is NOT unclear.
 "question": {
   "prompt": "the question, specific to the topic and learners, at most 28 words",
   "why": "one sentence: what in the video depends on the answer, for this topic",
   "options": [{"value": "...", "label": "...", "hint": "..."}]
 }
}
Rules for "question":
- It ALWAYS asks about NEXT FIELD, whatever "unclear" says. When the request carries a RE-ASK line, the last
  answer to this field was not usable: ask it again, narrower, with options built from what the requester said.
- FREE-TEXT field: give 3 or 4 options. Each "value" is a complete, concrete answer for this topic that could be
  stored as it is (a real mistake students make, a checkable goal...).
  "label" repeats the answer in at most 12 words; "hint" (at most 14 words) says when to pick it. Make the options
  genuinely different from each other. Put the one you would choose first. The requester may also type their own
  or skip an optional question, so never offer "skip", "none" or "other" as an option.
- FIXED-CHOICE field: you are given the allowed options. Return one entry per allowed value, same order, same
  "value", and write only a "hint" (at most 18 words) saying what that choice would mean for THIS topic and these
  learners. Do not add, drop or rename choices.
- The field "framework" is the one fixed choice where you ALSO write each "label": at most 12 words, starting with
  a verb, saying what that video would actually do with THIS topic ("Count a 3 by 3 square of dots, then find the
  rule" / "Solve 1764 step by step, then try 2025" / "Test the rule, break it, then prove it"). Its "hint" (at
  most 14 words) says which learners it suits. No teaching jargon: never "framework", "concrete", "worked
  example", "retrieval", "scaffold". The three labels must be clearly different videos.
- The field "context" asks for ONE simple example. Each option is a single everyday object, or the thing itself,
  with small numbers the learner can count ("a tray of 9 sweets in 3 rows of 3"). The FIRST option is always the
  plain one: the idea shown directly with small numbers and no everyday object. Never offer a story or a
  backdrop — no festival, shop, sport, match, journey or character — unless the topic itself is about it. An
  example with more parts than the idea has is a bad example.
- Use the learners' world: Indian school context and the NCERT class level when it is known. Technical terms in
  English."""


_GENERIC_GOAL_WORDS = set("""they students student learners learner children kids should will can could must be able to do
does doing solve solving practice practise practising understand understanding learn learning know knowing study studying
get grasp master problems problem questions question sums sum exercises exercise it this that these those the a an on of
about in from with for topic concept concepts chapter basics basic well properly better easily more all everything
things and their them some any video lesson after watching related based numericals numerical""".split())


def is_vague_goal(text: str, brief: dict) -> bool:
    """True for a goal that names no checkable action: "they should do problems on it", "understand trigonometry".

    Only generic verbs and nouns plus the topic's own words. The model usually pushes
    back on these, but not every time, and a lesson aimed at nothing is the most
    expensive mistake of the interview — so this one is decided in code.
    """
    tokens = re.findall(r"[a-z]+", str(text or "").lower())
    if not tokens or len(tokens) > 14:
        return False
    topic_words = set(re.findall(r"[a-z]{3,}", " ".join(str(brief.get(k, "")) for k in ("topic", "subject")).lower()))
    topic_words |= {w.rstrip("s") for w in topic_words} | {w + "s" for w in topic_words}
    return all(t in _GENERIC_GOAL_WORDS or t in topic_words for t in tokens)


_WANTS_ALL = re.compile(r"\b(all|everything|every one|full|whole|entire|complete|each of|both|sab|saare|sare|poora|pura)\b", re.I)


def wants_everything(text: str) -> bool:
    """An answer to "which one idea?" that declines to choose: "we need full coverage of all of them"."""
    words = str(text or "").split()
    return 0 < len(words) <= 14 and bool(_WANTS_ALL.search(text))


def is_delegation(text: str) -> bool:
    """'You decide', 'up to you', 'anything' — the requester hands the choice back."""
    return bool(_DELEGATE.match(text or ""))


def intake_models() -> list[str]:
    raw = knobs.get("HARNESS_INTAKE_MODELS", INTAKE_MODELS_DEFAULT)
    return [m.strip() for m in raw.split(",") if m.strip()]


def default_llm() -> LLM | None:
    """A fast, metered JSON-mode model for interactive questions, or None (no key / switched off)."""
    key = (os.getenv("OPENROUTER_API_KEY") or "").strip()
    if not key or knobs.get("HARNESS_INTAKE_LLM", "1") != "1":
        return None
    from ..engine import llm as engine_llm
    chain = intake_models()

    def call(prompt: str, system: str):
        # One model per attempt so a slow one cannot stack its timeout on the next; the
        # caller falls back to the deterministic wording when every attempt fails.
        last = None
        for model in chain:
            try:
                reasoning = {"enabled": False} if "2.5" in model or "gpt-" in model else None
                text = engine_llm.call_openrouter(key, prompt, system, temperature=0.4, models=[model],
                                                  max_tokens=1200, json_object=True, note="intake",
                                                  timeout=float(knobs.get("HARNESS_INTAKE_TIMEOUT", "14")),
                                                  reasoning=reasoning)
                return engine_llm.loads_json_lenient(text)
            except Exception as exc:  # noqa: BLE001 - next model, then the deterministic question
                last = exc
        raise last or RuntimeError("no intake model answered")
    return call


def wants_model(base: dict | None, last: dict | None) -> bool:
    """Is a model call worth making for this turn?"""
    if base is None:
        return False
    if base["id"] in MODEL_FIELDS:
        return True
    return bool(last and last.get("free_text") and len(str(last.get("answer", "")).split()) >= 4)


def _known(brief: dict) -> dict:
    keys = ("topic", "subject", "focus", "audience", "grade", "level", "goal", "framework", "style", "language",
            "duration_minutes", "context", "misconception")
    return {k: brief[k] for k in keys if brief.get(k) not in (None, "")}


def build_prompt(brief: dict, base: dict, last: dict | None, may_push_back: bool = False,
                 reask_reason: str = "") -> str:
    lines = [f"BRIEF SO FAR: {json.dumps(_known(brief), ensure_ascii=False)}"]
    if last:
        lines.append(f"LAST EXCHANGE — field \"{last['id']}\": Q: {last.get('prompt', '')!r}  →  "
                     f"A: {str(last.get('answer', ''))!r}")
    else:
        lines.append("LAST EXCHANGE: (none)")
    lines.append("PUSH-BACK: " + ("allowed once for the last answer, if it truly is unclear."
                                  if may_push_back else 'not allowed — "unclear" must be null.'))
    lines.append('ALLOWED KEYS FOR "learned": audience (text), grade (integer class 1-12), '
                 f"level ({' | '.join(_ENUMS['level'])}), goal (text, an action), "
                 f"language ({' | '.join(_ENUMS['language'])}), duration_minutes (integer 3-25), "
                 "context (text), misconception (text). Only keys not already in the brief.")
    field = base["id"]
    lines.append(f"NEXT FIELD: {field} — {_FIELD_MEANING.get(field, base['prompt'])}"
                 + (" (optional: the requester may skip it)" if base.get("optional") else ""))
    lines.append(f"GENERIC WORDING TO IMPROVE ON: {base['prompt']!r}")
    if reask_reason:
        lines.append(f"RE-ASK: the last answer to this field was not usable ({reask_reason}).")
    if base["kind"] == "choice":
        if field == "framework":
            # No label is handed over to echo: the model is told what each choice IS and must
            # say what it would look like for this topic.
            allowed = [{"value": o["value"], "what_it_is": o["label"].replace(" (suggested)", ""),
                        "who_it_suits": o.get("hint", "")} for o in base["options"]]
            lines.append("FIXED-CHOICE field. Keep each value and the order. For EVERY option return "
                         '{"value", "label", "hint"}: write a topic-specific label AND a hint for each. OPTIONS: '
                         + json.dumps(allowed, ensure_ascii=False))
        else:
            allowed = [{"value": o["value"], "label": o["label"], "hint": o.get("hint", "")} for o in base["options"]]
            lines.append("FIXED-CHOICE field. ALLOWED OPTIONS (keep value and order, rewrite only the hint): "
                         + json.dumps(allowed, ensure_ascii=False))
    else:
        lines.append("FREE-TEXT field: give 3 or 4 concrete options for this topic and these learners.")
    return "\n".join(lines)


def _clip(value, limit: int) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()[:limit]


def merge_question(base: dict, raw: Any) -> dict:
    """The base question with the model's wording and options, where they pass validation."""
    question = {**base, "source": "default"}
    if not isinstance(raw, dict):
        return question
    prompt, why = _clip(raw.get("prompt"), 240), _clip(raw.get("why"), 280)
    options = raw.get("options") if isinstance(raw.get("options"), list) else []
    if base["kind"] == "choice":
        hints = {str(o.get("value")): _clip(o.get("hint"), 170) for o in options if isinstance(o, dict)}
        if not prompt or len(hints) < len(base["options"]) - 1:
            return question          # the model changed the choice set: keep the safe wording
        # The kind of video is the one choice whose LABEL is written for the topic: its plain
        # names are still names of teaching shapes. Used only when all of them are present,
        # short and different; the suggested one keeps its mark.
        labels = {}
        if base["id"] == "framework":
            labels = {str(o.get("value")): _clip(str(o.get("label") or "").replace("(suggested)", ""), 150)
                      for o in options if isinstance(o, dict)}
            given = [labels.get(str(o["value"]), "") for o in base["options"]]
            jargon = re.compile(r"\b(framework|concrete|worked example|retrieval|scaffold|pedagog)", re.I)
            if not all(given) or len({g.lower() for g in given}) < len(given) or any(jargon.search(g) or len(g.split()) > 24 for g in given):
                labels = {}
        merged = []
        for option in base["options"]:
            hint = hints.get(str(option["value"])) or option.get("hint", "")
            entry = {**option, "hint": hint}
            if labels:
                entry["label"] = labels[str(option["value"])] + (" (suggested)" if "(suggested)" in option["label"] else "")
            merged.append(entry)
        question.update({"prompt": prompt, "why": why or base["why"], "options": merged, "source": "model"})
        return question
    suggestions, seen = [], set()
    for o in options:
        if not isinstance(o, dict):
            continue
        value = _clip(o.get("value") or o.get("label"), 200)
        label = _clip(o.get("label") or value, 110)
        if not value or value.lower() in seen:
            continue
        if re.match(r"^(skip|none|no (setting|example|mistake)|not applicable|n/?a)\b", label, re.I):
            continue                      # optional questions already have a Skip button
        seen.add(value.lower())
        suggestions.append({"value": value, "label": label, "hint": _clip(o.get("hint"), 130)})
        if len(suggestions) == 4:
            break
    if not prompt:
        return question
    question.update({"prompt": prompt, "why": why or base["why"], "options": suggestions, "source": "model"})
    if suggestions:
        question["placeholder"] = "or type your own" + (" — or skip" if base.get("optional") else "")
    return question


def clean_learned(raw: Any, brief: dict) -> dict:
    """Validated extras from the last answer; never overwrites what the brief already has."""
    if not isinstance(raw, dict):
        return {}
    out: dict = {}
    for key in ("audience", "goal", "context", "misconception"):
        value = _clip(raw.get(key), 220)
        if value and not brief.get(key) and key not in brief and not is_delegation(value):
            out[key] = value
    for key in ("level", "language"):
        value = str(raw.get(key) or "").strip()
        if value in _ENUMS[key] and not brief.get(key):
            out[key] = value
    for key, lo, hi in (("grade", 1, 12), ("duration_minutes", intake.MIN_MINUTES, 25)):
        try:
            number = int(raw.get(key))
        except (TypeError, ValueError):
            continue
        if lo <= number <= hi and not brief.get(key):
            out[key] = number
    return out


def turn(brief: dict, base: dict, last: dict | None, llm: LLM, may_push_back: bool = False,
         reask_reason: str = "") -> dict:
    """One model call: ``{"raw_question", "learned", "unclear"}``. Raises when the model cannot be used."""
    raw = llm(build_prompt(brief, base, last, may_push_back, reask_reason), SYSTEM)
    if not isinstance(raw, dict):
        raise ValueError("the intake model did not return an object")
    unclear = _clip(raw.get("unclear"), 240) if (raw.get("unclear") and may_push_back) else ""
    return {"raw_question": raw.get("question"), "learned": clean_learned(raw.get("learned"), brief),
            "unclear": unclear}
