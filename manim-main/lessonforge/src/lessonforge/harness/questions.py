"""The questions a lesson asks its learner: written as questions, checked as questions.

The owner, 2026-10-09: "Try to improve the question, it [is] not giving good questions."
Until then a question was one clause in the writer's rules ("about once a minute, stop
and ask") and nothing looked at what came out. Their own lesson on why the sky is blue
asked, in three minutes:

* "Which light scatters more?" before anything had tied wavelength to scattering;
* "What reaches the observer sideways?" one chapter after the voice had said exactly
  that, with the reason printed inside the right option ("Blue, shorter wavelength") and
  the narration going on AFTER the question to give the reason once more;
* in the recap, "Which step chooses scattering?": a question about the lesson's own
  outline, which tests nothing a learner needs;

and whichever wrong option a learner tapped, the player said the same sentence.

The owner again, 2026-10-10: "The options in the question are like the next narration
now and the question is giving narration script itself." Both were also true of what the
first version of this pass had written for that lesson: "What does colourless air do to
blue laser light?" one sentence after the voice had said "molecules only change the
light's direction, not its colour", and options such as "Blue scatters toward eyes",
which is a line of narration with a tick box in front of it. Code could not see either.

And read on five real lessons the same day, the first version did damage of its own: it
gave a card to a lesson's OPENING question and had the next beat answer it (the question
the whole lesson exists to answer); it hung a new case on the end of a beat that sets a
paper task; it replaced fair questions with others and left the old question's setup
standing in front of them ("Question three: the wire broke in the middle. Which outer
material should a charger cable have?"). So what is done at each stop is now decided by
CODE, from what is wrong there, and the model does only that:

* a question with nothing wrong beyond its card (long options, a reason in an option, one
  line of feedback for all) KEEPS its words; only its options and their reasons are written;
* a beat that goes on after its question is cut to END on it;
* only a question that cannot stand (it asks about the lesson, its answer is on screen, a
  listener can answer it by repeating the voice) gets another question written, and then
  the old question and what set it up go with it;
* a pause that has no card is not touched at all: the lesson's opening question and its
  try-it task are pauses of that kind.

``faults(lesson)`` — what code can tell is wrong with a question card and its beat.

``listen(lesson, model)`` — what only a listener can tell: given the last sentences the
voice said before the stop and nothing else, do they already state how the question's
own case comes out? The model must COPY the words and say what they state; code keeps a
finding only when those words were heard and are not the question itself.

``improve(lesson, …)`` — the pass. Every change is tried on the lesson and kept only where
``faults`` then finds no more than before and none of the hard ones, and where the
listener has to think. What does not pass is asked for ONCE more with the reason; a stop
that still has no honest question is taken out. A pasted script keeps every word.

``confirm_answers(lesson, …)`` — after the cards are settled: does the voice SAY each
card's answer when the video goes on? Where a listener finds it does not (a reviewer's
rewrite of the next beat had dropped it in four of ten lessons), one sentence is put there.

``settle_pauses(lesson)`` — a pause with no card that follows a plain statement is taken
out: the video showed "YOUR TURN" over a statement and waited.

``RULES`` is the wording both this pass and the writer are given, so the two do not
drift. ``HARNESS_QUESTIONS=0`` switches the pass off.
"""
from __future__ import annotations

import copy
import json
import os
import re

from .. import knobs
from ..longform.contract import split_sentences
from . import critic, voice, writer
from .annotate import spoken_numbers

KINDS = ("predict", "apply", "spot", "recall")
#: An option is an answer (a name, a number with its unit, a value), never a sentence: at most this many words, counting
#: only words of two letters or more ("16 cm" is one, "x = 2 and y = 3" is one).
MAX_OPTION_WORDS = 3
#: Faults a card may not have after this pass has written it (the others are weighed: fewer is better).
HARD = ("not_last", "statement", "about_the_lesson", "reason_in_option", "long_option", "on_screen", "unsaid_number")
#: What is done at a stop, decided by code from what is wrong there (``plan``).
CARD, CUT, NEW = "card", "cut", "new"
#: A question with one of these cannot stand as it is: another question is written for the stop.
#: ("asks_other": the card asks for another thing than the voice does, found by ``solve``: the voice and its card are
#: written again together.)
NEEDS_ANOTHER = ("statement", "about_the_lesson", "on_screen", "told", "asks_other", "unsaid_number")
#: ... and when none could be, a stop with one of these is taken out: no question is better than one of these.
BAD = ("statement", "about_the_lesson", "not_last", "told", "asks_other", "unsaid_number")
#: How much of the beat before is part of "what the voice has just said" (sentences).
HEARD_BEFORE = 2
#: The candidate that changes no card and only ends the beat on its question.
ONLY_CUT: dict = {}

#: What a good question is: ONE text, held in ``writer.QUESTION_RULES`` (this module imports the writer, so the
#: writer cannot import it) and given to the writer in its own rules as well as to this pass, so the two cannot drift.
RULES = writer.QUESTION_RULES

SYSTEM = """You write the questions a short narrated lesson video asks its learner. The script is finished; you are
given all of it. At a question the video stops, shows a card, and the player takes the learner's answer.
""" + RULES + """
You are given every beat: its narration and what is on screen. Each beat that stops for a question card is marked with
ONE of three jobs for you. Do exactly the job named at that beat, and nothing else there:
- "KEEP THIS QUESTION": the voice's question and the card's question stay word for word. Give that very question three
  short answers and a reason for each, in the language its card is written in: return only "beat", "kind", "options",
  "answer_index", "why" and "confirm". No "ask", no "question", no "new_case": it is the same question.
- "KEEP THIS QUESTION, CUT WHAT FOLLOWS IT": the same; code ends the beat on its question.
- "WRITE ANOTHER QUESTION HERE", with the reason: the question there cannot stand. Write a new one in full: "ask" (the
  closing words of the beat), the card, its options, a reason for each, and "confirm". Your closing words take the place
  of the beat's present question and of anything said after it. Say with "replaces" how many of the sentences BEFORE
  that question go as well, because they only set the old question up and would hang in the air in front of yours (0, 1
  or 2; when in doubt 0). Everything else the beat says stays as written, and so does what is on screen. So read what
  the beat has ALREADY SAID before you choose what to ask: if its own words have given the idea (a recap does, a beat
  that corrects the usual mistake does, a worked example does), any question about that idea in the same case only
  repeats it. Ask an "apply" question there: a case that is new in its SITUATION and comes out DIFFERENTLY from the
  sentence just said, and give "new_case", the new situation in two or three words. It must be one the script never
  mentions, never "another scene" of the same thing, and its right answer is not an earlier question's. List the beat
  under "drop" instead (its stop goes) only when no honest question can be asked there at all, which is rare.
A beat that pauses WITHOUT a card is not yours to change, and you may not add a stop anywhere.
EACH QUESTION TESTS A DIFFERENT THING: no two share their new case, their right answer or their set of options, and no
two need the same step of reasoning (the sky on the Moon and the sky on an airless planet are one question asked twice).
Do not invent a named person; "ek student" or "someone" will do when a wrong statement needs a speaker.
Return ONLY JSON:
{"questions": [
   {"beat": "id of a KEEP beat", "kind": "predict" | "apply" | "spot" | "recall",
    "options": ["three short answers, one to three words each"], "answer_index": 0,
    "why": ["one sentence for each option, in the same order"],
    "confirm": "ONE short sentence in the narration's language that tells the learner the right answer, as the voice says it when the video goes on (code uses it only where the next beat does not already say the answer; leave it out for the lesson's last beat)"},
   {"beat": "id of a WRITE ANOTHER QUESTION beat", "kind": "predict" | "apply" | "spot" | "recall",
    "ask": "the closing words of the beat, in the narration's own language and voice, ENDING with the question: one or two sentences. They set the case up and ask; they give no hint and no reason",
    "replaces": 0,
    "question": "the card, in English: it names the case it asks about, so that it can be read without the voice",
    "options": ["three short answers, one to three words each"], "answer_index": 0,
    "why": ["one sentence for each option, in the same order, in English"],
    "new_case": "for apply only",
    "confirm": "ONE sentence in the narration's language with which the NEXT beat will open: it names the right answer and gives its reason in one breath (leave it out for the lesson's last beat)"}],
 "drop": ["beat ids"]}
In "ask" and "confirm" keep the narration's language exactly as the script uses it (in Hinglish: Hindi for the talk,
English for every number, unit and subject term), write numbers in words, and add no stage directions."""

KEEP_WORDS = """
THIS SCRIPT IS ITS AUTHOR'S OWN: not a word of narration may change, so every stop here is a KEEP. Return only "beat",
"kind", "options", "answer_index" and "why" for each, and no "drop"."""

RETRY = """
YOU HAVE DONE THIS ONCE AND SOME OF IT WAS NOT KEPT. Under WRITE AGAIN is each such beat, its job, what you wrote for it
and why that was not kept. Do those beats again and no others. Where the reason is that the voice has already said the
answer, other words for the same question will fail again: it needs another CASE. Change one thing in the situation
(take the cause away, change a number, swap the object, turn the order round) so that the right answer is NOT what the
quoted sentence says. Return the same JSON with those beats only, and no "drop"."""

LISTEN = """You check the questions a narrated lesson asks, as a strict and fair teacher would. At each question the
video stops and the learner picks one of the options. A question is worth its stop only if the learner has to THINK. It
is worth nothing when the voice has JUST SAID how the very case in the question comes out, so that repeating it is
enough.
For each question you are given HEARD (the last things the voice said before the stop, ending with the question), any
lines ON SCREEN at that moment, the options, and which option is right. Work through these steps and give them all:
 "case": what the question asks about, in a few words (the object and its condition).
 "quote": the words in HEARD or ON SCREEN that state how THAT case comes out, or why. Copy them exactly (one sentence
   or clause). Never the question's own sentence, and never a sentence that only describes the case or only names the
   choices. "" when there are none.
 "states": what those words state, in a few words of your own ("" when there is no quote).
 "told": true only if "states" IS the right option: the same outcome for the same case. false when it is the outcome of
   ANOTHER case (the one before, the opposite one), when it is a general fact the learner still has to use on something
   new, when two things said separately have to be connected, and whenever you are in doubt.
 "same": the beat id of an EARLIER question in the list that needs the very same step of reasoning to answer (the same
   change to the case and the same reason: what the sky looks like on the Moon, and on a planet with no air). "" when
   none does; two questions on one idea that need different reasoning are not the same.
Four examples, so that the line is clear:
 HEARD: "A magnet pulls iron but not plastic. Take an iron nail and a plastic spoon: which one does the magnet pull?"
   RIGHT: "The nail".  quote "A magnet pulls iron but not plastic", states "it pulls the iron thing", told true.
 HEARD: "Off: the path is broken. Question two: the switch is closed and every wire is joined. Is the bulb on or off?"
   RIGHT: "On".  quote "Off: the path is broken", states "the bulb is off when the path is broken", told false (that is
   the other case; the learner has to turn it round).
 HEARD: "The denominator says into how many equal parts the whole is cut. Which piece is bigger: one third or one fifth?"
   RIGHT: "One third".  quote "", told false (a general fact; nobody has said which piece is bigger).
 HEARD: "So a plant in sunlight makes its own food. A plant is kept in a dark cupboard for a week: what happens to it?"
   RIGHT: "It turns pale".  quote "", told false (a new case, and nobody has said how it comes out).
Return ONLY JSON, with one entry for EVERY question under CHECK, in the order given:
{"checks": [{"beat": "id", "case": "", "quote": "", "states": "", "told": false, "same": ""}]}"""

AFTER = """A narrated lesson video stops at a question, the learner picks an option, and then the voice goes on. For each
question below you are given the card, its options, which option is RIGHT, and NEXT: the first things the voice says
when the video goes on. Say whether NEXT tells the learner the right answer.
 "quote": the words in NEXT that state the right answer (copy them exactly: one sentence or clause). "" when none do.
 "answered": true only when a learner who picked a WRONG option would know from those words which answer was right.
   false when NEXT goes on to something else, only asks the learner to check their guess, or gives a general rule from
   which the answer would still have to be worked out, and whenever you are in doubt.
Return ONLY JSON, with one entry for EVERY question, in the order given:
{"checks": [{"beat": "id", "quote": "", "answered": false}]}"""

SOLVE = """You check the question cards of a narrated lesson video, as a careful teacher who answers every card herself
before her learners see it. You are given the whole script, beat by beat (what the voice says, and the lines on screen),
and under CHECK every card: the beat it stops at, the question the voice asks there, and the card's question and options.
Which option is meant to be right is NOT given: work it out. For each card give:
 "voice": what the voice's question asks for, in a few words.
 "card": what the card's question asks for, in a few words.
 "same": true when one answer answers both: the card may name the case more fully, be in English while the voice speaks
   Hindi, or ask the same thing in other words. false only when they ask for DIFFERENT things (a shape and an area; which
   way a box moves and which way a passenger leans).
 "work": one or two short lines that work the card's answer out from the script's own facts and numbers, for the case
   the card names.
 "pick": the number of the right option, counting from 1; 0 when no option is right.
Return ONLY JSON, with one entry for EVERY card under CHECK, in the order given:
{"checks": [{"beat": "id", "voice": "", "card": "", "same": true, "work": "", "pick": 1}]}"""


def solve(lesson: dict, model, log=print) -> dict | None:
    """Each card answered by a model that is not told which option is meant: ``{beat: {"pick", "same", "voice", "card", "work"}}``.

    ``pick`` is the option's index, or -1 when it found none right. One call for the whole lesson; None when nobody
    could answer. The card is the only place the learner is TOLD an answer: a card whose marked option is wrong teaches
    a wrong fact (a writer on the 6 × 4 triangle marked "20 cm²" right, 2026-10-15), and nothing else in the pass
    looks at whether the marked option is true.
    """
    order = _beats(lesson)
    cards, script = {}, []
    for at, beat in enumerate(order):
        beat_id = str(beat.get("id"))
        shown = [str(step.get("show", "")).strip() for step in beat.get("steps") or [] if str(step.get("show", "")).strip()]
        script.append(f"[beat {beat_id}] VOICE: {beat.get('narration', '')}" + (f"\n    ON SCREEN: {' | '.join(shown)}" if shown else ""))
        quiz = _card(beat)
        options, right = [str(o) for o in quiz.get("options") or []], quiz.get("answer_index")
        if quiz and isinstance(right, int) and 0 <= right < len(options) and len(options) > 1:
            close = closing(beat.get("narration", ""))[1]
            cards[beat_id] = (f"\nCARD at beat {beat_id}\n  THE VOICE ASKS: {close[0] if close else '(nothing)'}\n  THE CARD: {quiz.get('question', '')}\n"
                              + "".join(f"  {n}. {o}\n" for n, o in enumerate(options, 1)), len(options))
    if not cards:
        return {}
    if model is None:
        return None
    try:
        answer = model("THE SCRIPT:\n" + "\n".join(script) + "\n\nCHECK:" + "".join(text for text, _ in cards.values()), SOLVE)
    except Exception as exc:  # noqa: BLE001 - a check that cannot be made is reported, never fatal
        log(f"[questions] nobody answered the cards to check them ({type(exc).__name__}: {str(exc)[:100]})")
        return None
    checks = answer.get("checks") if isinstance(answer, dict) else answer
    if not isinstance(checks, list):
        log("[questions] the answers to the cards could not be read: nothing is known about whether their marked options are right")
        return None
    out = {}
    for check in checks:
        beat_id = critic.beat_id(check.get("beat"), cards) if isinstance(check, dict) else ""
        if beat_id not in cards or beat_id in out:
            continue
        try:
            pick = int(check.get("pick"))
        except (TypeError, ValueError):
            continue
        if not 0 <= pick <= cards[beat_id][1]:
            continue
        same = check.get("same")
        out[beat_id] = {"pick": pick - 1, "same": not (same is False or str(same).strip().lower() in ("false", "no")),
                        "voice": str(check.get("voice") or "")[:120], "card": str(check.get("card") or "")[:120],
                        "work": str(check.get("work") or "")[:240]}
    return out


#: The plain sentence that tells an answer when no better one could be used, by the lesson's language.
_THE_ANSWER = {"hinglish": "Sahi jawab hai {answer}.", "hi-in": "सही जवाब है {answer}.", "en-in": "And the answer is {answer}.",
               "en": "And the answer is {answer}."}       # no colon: it is said, not printed (voice.notes_in)

_ABOUT_THE_LESSON = re.compile(r"\b(which|what|first|second|third|next|last)\s+(step|point|part|stage)\b|\b(this|the)\s+(lesson|video|chapter)\b"
                               r"|\bwe\s+(saw|learn(ed|t)|discussed|covered)\b|\bstep\s+(one|two|three|\d)\b", re.I)
#: A reason inside an option: a comma, semicolon or colon that a word follows ("Blue, shorter wavelength"), or the
#: words that open a reason. Not a comma between numbers ("1,000"), a ratio ("2:3") or a pair of coordinates.
_REASON = re.compile(r"[,;:]\s*[A-Za-z]{2,}|\bbecause\b|\bsince\b|\bso that\b|\bas it\b", re.I)
_SMALL = {"the", "a", "an", "of", "to", "in", "is", "are", "and", "or", "it", "its", "by", "on", "at", "for", "with", "more", "less", "than"}
_ASKING = {"what", "which", "does", "will", "would", "when", "where", "that", "this", "have", "many", "much", "happens"}
#: Words that make a case sound new without naming one ("another scene", "a different example").
_NOT_A_CASE = {"another", "different", "other", "scene", "case", "example", "situation", "same", "similar", "setup", "version", "time"}


def enabled() -> bool:
    return (knobs.get("HARNESS_QUESTIONS") or "1").strip() != "0"


def _card(beat: dict) -> dict:
    return beat["quiz"] if isinstance(beat.get("quiz"), dict) and beat["quiz"].get("options") else {}


def _words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", str(text).lower())


def _flat(sentence: str) -> str:
    return " ".join(_words(sentence))


def _is_question(sentence: str) -> bool:
    return str(sentence).rstrip().rstrip('"”’\'').endswith("?")


def answer_words(option: str) -> int:
    """How long an option is as an ANSWER: its words of two letters or more ("16 cm" is one, "Stays the same" three)."""
    return len(re.findall(r"[A-Za-z]{2,}", str(option)))


def carries_reason(option: str) -> bool:
    """An option that explains itself ("Blue, shorter wavelength", "Red because it bends least")."""
    return bool(_REASON.search(re.sub(r"\([^()]*\)", " ", str(option))))


def closing(narration: str) -> tuple[list[str], list[str]]:
    """A beat's narration as (what is said before its last question, that question and anything said after it)."""
    said = split_sentences(narration or "")
    last = max((i for i, sentence in enumerate(said) if _is_question(sentence)), default=None)
    return (said, []) if last is None else (said[:last], said[last:])


def says_again(sentence: str, others: list[str]) -> bool:
    """A sentence that is one of ``others`` again, word for word or nearly (four fifths of its words that carry anything)."""
    mine = [w for w in _words(sentence) if len(w) >= 3 and w not in _SMALL]
    if _flat(sentence) in {_flat(o) for o in others}:
        return True
    return len(mine) >= 3 and any(sum(w in set(_words(o)) for w in mine) >= 0.8 * len(mine) for o in others)


def faults(lesson: dict, told: dict | None = None, solved: dict | None = None) -> list[dict]:
    """What is wrong with the lesson's question cards: ``[{"beat", "fault", "what"}]``, in the lesson's order.

    Only beats that carry a card: a pause without one is the writer's own device (the opening question, the try-it
    task) and none of this pass's business. Everything here is found by code, except ``told``: a beat's entry in the
    optional ``told`` (``listen``'s answer: the words that already say the right option) becomes a fault of that name,
    so one list is the whole measure. So is ``solved`` (``solve``'s answer): a card that asks another thing than the
    voice (``asks_other``) and a marked option a teacher who was not told it did not pick (``wrong_answer``).
    """
    found = []
    heard: set[str] = set()                                         # every number the voice has said so far
    for chapter in lesson.get("chapters") or []:
        for beat in chapter.get("beats") or []:
            heard |= spoken_numbers(beat.get("narration", ""))
            quiz = _card(beat)
            if not quiz:
                continue
            def note(fault, what, beat=beat):
                found.append({"beat": str(beat.get("id")), "fault": fault, "what": what})
            before, close = closing(beat.get("narration", ""))
            if not close:
                note("statement", "the card comes up and the voice has asked nothing")
            elif len(close) > 1:
                note("not_last", "the voice goes on after the question: " + " ".join(close[1:])[:90])
            if (told or {}).get(str(beat.get("id"))):
                note("told", "the voice has already said the answer: " + str(told[str(beat.get("id"))])[:110])
            worked = (solved or {}).get(str(beat.get("id")))
            if worked and close and not worked["same"]:
                note("asks_other", f"the card asks for {worked['card'] or 'another thing'}, the voice for {worked['voice'] or 'another'}")
            if worked and isinstance(quiz.get("answer_index"), int) and worked["pick"] != quiz["answer_index"]:
                note("wrong_answer", "the option marked right is not right" + (f": {worked['work']}" if worked["work"] else ""))
            question = str(quiz.get("question") or "").strip()
            # The card names its case; the voice must have set that case up. A card about "a ray 40 degrees from the
            # normal" under a voice that never says forty asks a question the learner never heard (8 of 400 cards on
            # 2026-10-15, 5 of them this; another question written by this pass had the voice say "cut it along the
            # diagonal" over the rectangle on screen while its card named a 10 by 3 one). Ordinals ("the 10th term",
            # said "tenth" or "dasvein") and 1 and 2 ("one way", "do S ends") are not a case's numbers.
            unsaid = sorted(n for n in case_numbers(question) if n not in heard)
            if unsaid:
                note("unsaid_number", f"the card names {', '.join(unsaid)}, which the voice never says")
            if not question.endswith("?"):
                note("statement", f"the card is not a question: {question[:60]}")
            if _ABOUT_THE_LESSON.search(question):
                note("about_the_lesson", f"the card asks about the lesson itself: {question[:60]}")
            options = [str(o) for o in quiz.get("options") or []]
            right = quiz.get("answer_index")
            if any(carries_reason(o) for o in options):
                note("reason_in_option", "an option carries its own reason: " + next(o for o in options if carries_reason(o))[:50])
            if any(answer_words(o) > MAX_OPTION_WORDS for o in options):
                note("long_option", "an option is a phrase, not an answer of one to three words: "
                     + next(o for o in options if answer_words(o) > MAX_OPTION_WORDS)[:50])
            if isinstance(right, int) and 0 <= right < len(options) and len(options) > 1:
                others = [len(o.split()) for k, o in enumerate(options) if k != right]
                if len(options[right].split()) >= max(others) + 2:
                    note("uneven_options", "the right option is the longest by two words or more")
                # The words that tell the right option from the wrong ones, all on screen in one line while it is asked
                # (and none of the words that mark a wrong one: "Blue and red rays" names the choices, not the answer).
                wrong = {w for k, o in enumerate(options) if k != right for w in _words(o)}
                apart = {w for w in _words(options[right]) if len(w) >= 4 and w not in _SMALL} - wrong
                others = {w for w in wrong if w not in _SMALL} - set(_words(options[right]))
                for step in beat.get("steps") or []:
                    shown = set(_words(step.get("show", "")))
                    if apart and apart <= shown and not others & shown and str(step.get("show", "")).strip() != question:
                        note("on_screen", f"the answer is on screen while it is asked: {str(step.get('show'))[:50]}")
                        break
            why = quiz.get("why") if isinstance(quiz.get("why"), list) else []
            said = [re.sub(r"\W+", " ", str(w)).strip().lower() for w in why]
            if len(why) != len(options) or len(set(said)) < len(said) or not all(said):
                note("same_feedback", "the options do not each have feedback of their own")
    return found


def case_numbers(question: str) -> set[str]:
    """The numbers a card's question names its case by: not an ordinal ("the 10th term" is said "tenth" or "dasvein"),
    and not 1 or 2 ("one way", "do S ends")."""
    return {n for n in spoken_numbers(re.sub(r"\b\d+(st|nd|rd|th)\b", " ", str(question), flags=re.I)) if float(n) > 2}


def _of(found: list[dict], beat_id: str) -> list[str]:
    return [f["fault"] for f in found if f["beat"] == str(beat_id)]


def _beats(lesson: dict) -> list[dict]:
    return [beat for chapter in lesson["chapters"] for beat in chapter["beats"]]


def plan(lesson: dict, told: dict | None = None, keep_words: bool = False, solved: dict | None = None) -> dict:
    """What is done at each stop: ``{beat: CARD | CUT | NEW}``. Code's decision, from what is wrong there.

    A question that only needs a better card keeps its words; a beat that talks on after its question is cut to end on
    it; only a question that cannot stand gets another one written. An author's own script is all ``CARD``.
    """
    found = faults(lesson, told, solved)
    out = {}
    for beat in _beats(lesson):
        if _card(beat):
            wrong = _of(found, beat["id"])
            out[str(beat["id"])] = (CARD if keep_words else NEW if any(f in NEEDS_ANOTHER for f in wrong)
                                    else CUT if "not_last" in wrong else CARD)
    return out


def heard_at(order: list[dict], at: int) -> tuple[list[str], list[str]]:
    """What a learner has taken in when the video stops at ``order[at]``: (the last sentences heard, the lines on screen).

    The beat that asks up to and including its question (what a beat says AFTER its question is code's to see, and to
    cut), and the end of the beat before.
    """
    beat = order[at]
    earlier = split_sentences(order[at - 1].get("narration", ""))[-HEARD_BEFORE:] if at else []
    before, close = closing(beat.get("narration", ""))
    card = _flat(_card(beat).get("question", ""))
    shown = [str(step.get("show", "")).strip() for step in beat.get("steps") or []]
    return earlier + before + close[:1], [line for line in shown if line and _flat(line) != card]


def _quoted(quote: str, heard: list[str]) -> str:
    """The sentence of ``heard`` a listener's quote is taken from, or '' when it was not said (a model's own words)."""
    words = _words(quote)
    if len(words) < 3:
        return ""
    flat = " ".join(words)
    for sentence in heard:
        if flat in _flat(sentence):
            return sentence
    if flat in _flat(" ".join(heard)):
        return re.sub(r"\s+", " ", str(quote)).strip()
    big = [w for w in words if len(w) >= 3]                       # a copy with a word or two changed is still that sentence
    for sentence in heard:
        said = set(_words(sentence))
        if len(big) >= 3 and sum(w in said for w in big) >= 0.75 * len(big):
            return sentence
    return ""


def _listened(lesson: dict, model, only=None, log=print) -> tuple[dict, dict] | None:
    """One call to a listener: ``(told {beat: the sentence that says it}, same {beat: the earlier beat it repeats})``."""
    order = _beats(lesson)
    asked, blocks, cards = {}, [], []
    for at, beat in enumerate(order):
        quiz, beat_id = _card(beat), str(beat.get("id"))
        options, right = [str(o) for o in quiz.get("options") or []], quiz.get("answer_index")
        if not quiz or not (isinstance(right, int) and 0 <= right < len(options)):
            continue
        cards.append(f"  {beat_id}: {quiz.get('question', '')}  (right: {options[right]})")
        if (only is not None and beat_id not in only) or not closing(beat.get("narration", ""))[1]:
            continue                                               # (nothing asked aloud: code says so already)
        heard, shown = heard_at(order, at)
        asked[beat_id] = (heard[:-1] + shown, at)                  # the question's own sentence gives nothing away by being asked
        blocks.append(f"\nQUESTION at beat {beat_id}\n  HEARD: {' '.join(heard)}"
                      + (f"\n  ON SCREEN: {' | '.join(shown)}" if shown else "")
                      + f"\n  THE CARD: {quiz.get('question', '')}\n  OPTIONS: " + " / ".join(options) + f"\n  RIGHT: {options[right]}")
    if not asked:
        return {}, {}
    if model is None:
        return None
    prompt = "ALL THE LESSON'S QUESTIONS, in order:\n" + "\n".join(cards) + "\n\nCHECK:" + "\n".join(blocks)
    try:
        answer = model(prompt, LISTEN)
    except Exception as exc:  # noqa: BLE001 - a check that cannot be made is reported, never fatal
        log(f"[questions] nobody listened to the questions ({type(exc).__name__}: {str(exc)[:100]})")
        return None
    checks = answer.get("checks") if isinstance(answer, dict) else answer
    if not isinstance(checks, list):
        log("[questions] the listener's answer could not be read: nothing is known about what the voice gives away")
        return None
    told, same = {}, {}
    place = {str(beat.get("id")): n for n, beat in enumerate(order)}
    for check in checks:
        if not isinstance(check, dict):
            continue
        beat_id = critic.beat_id(check.get("beat"), asked)
        if beat_id not in asked:
            continue
        # Believed only when it says so (not "true" for what it then cannot quote) and the words were really heard.
        said = _quoted(str(check.get("quote") or ""), asked[beat_id][0])
        if said and (check.get("told") is True or str(check.get("told")).strip().lower() in ("true", "yes")):
            told[beat_id] = said
        other = critic.beat_id(check.get("same"), place) if check.get("same") else ""
        if other in place and place[other] < asked[beat_id][1] and _card(order[place[other]]):
            same[beat_id] = other
    return told, same


def listen(lesson: dict, model, only=None, log=print) -> dict | None:
    """Which questions a learner could answer by repeating what the voice has just said: ``{beat: the words that say it}``.

    One call for all the lesson's question cards (or those in ``only``). A finding is kept only when the model says
    the words state the right option for the question's own case, and those words are in what was heard there (not
    in the question itself). None when the model gave no usable answer: nothing is known.
    """
    heard = _listened(lesson, model, only, log)
    return None if heard is None else heard[0]


def clean(raw: dict, old: dict | None = None) -> dict | None:
    """A model's card made safe: ``writer.clean_quiz``'s card with a reason for each option, or None."""
    if not isinstance(raw, dict):
        return None
    quiz = writer.clean_quiz({**raw, "question": raw.get("question") or (old or {}).get("question") or "", "explain": raw.get("explain") or ""})
    if not quiz or not 2 <= len(quiz["options"]) <= 4:
        return None
    why = [re.sub(r"\s+", " ", str(w)).strip()[:180] for w in raw.get("why") or []] if isinstance(raw.get("why"), list) else []
    if len(why) != len(quiz["options"]) or not all(why):
        return None
    quiz["why"] = why
    quiz["explain"] = why[quiz["answer_index"]][:160]            # what the screen says after the reveal: why it is right
    if raw.get("kind") in KINDS:
        quiz["kind"] = raw["kind"]
    return quiz


_JOB = {CARD: "KEEP THIS QUESTION", CUT: "KEEP THIS QUESTION, CUT WHAT FOLLOWS IT", NEW: "WRITE ANOTHER QUESTION HERE"}


def _script(lesson: dict, jobs: dict, found: list[dict] | None = None) -> str:
    """The lesson as the question-writer reads it, each stop with its job and what is wrong there now."""
    lines = []
    beats = [(chapter, beat) for chapter in lesson["chapters"] for beat in chapter["beats"]]
    for n, (chapter, beat) in enumerate(beats):
        lines.append(f"\nBEAT {beat['id']}  (part: {chapter.get('title', '')}; its job: {chapter.get('role', '') or 'teach'})"
                     + ("  [THE LAST BEAT]" if n == len(beats) - 1 else ""))
        lines.append(f"  narration: {beat.get('narration', '')}")
        shown = [f"{i}: {step.get('show', '')}" for i, step in enumerate(beat.get("steps") or [])]
        if shown:
            lines.append("  on screen, by index: " + " | ".join(shown))
        figure = beat.get("figure") or {}
        if figure:
            lines.append(f"  picture: {str(figure.get('describe') or figure.get('ask') or figure.get('kind'))[:140]}")
        quiz = _card(beat)
        if quiz:
            lines.append(f"  STOPS HERE and asks on its card: {json.dumps({k: quiz.get(k) for k in ('question', 'options', 'answer_index')}, ensure_ascii=False)}")
            wrong = [f["what"] for f in found or [] if f["beat"] == str(beat["id"])]
            job = jobs.get(str(beat["id"]))
            lines.append((f"  YOUR JOB: {_JOB[job]}" if job else "  NOT YOURS: leave this beat out") + (" (" + "; ".join(wrong) + ")" if wrong else ""))
        elif float(beat.get("thinking_pause_seconds") or 0) > 0:
            lines.append("  (pauses here without a card: not yours to change)")
    return "\n".join(lines)


def _answered(llm, prompt: str, system: str, log) -> dict | None:
    """The question-writer's answer when it is one: a dict with a list of questions."""
    try:
        answer = llm(prompt, system) or {}
    except Exception as exc:  # noqa: BLE001 - better questions are an improvement, never a requirement
        log(f"[questions] not written again ({type(exc).__name__}: {str(exc)[:100]})")
        return None
    return answer if isinstance(answer, dict) and isinstance(answer.get("questions"), list) else None


def _candidates(answer: dict, lesson: dict) -> dict:
    """``{beat id: the model's card for it}`` for beats that have one now (no new stops, and only beats this lesson has)."""
    order = _beats(lesson)
    index = {str(beat["id"]): n for n, beat in enumerate(order)}
    out = {}
    for raw in answer.get("questions") or []:
        beat_id = critic.beat_id(raw.get("beat"), index) if isinstance(raw, dict) else None
        if beat_id in index and _card(order[index[beat_id]]) and beat_id not in out:
            out[beat_id] = raw
    return out


def _replay(lesson: dict, pristine: dict, chosen: dict, lenient: bool) -> tuple[dict, dict]:
    """``lesson`` made again from ``pristine`` with, for each beat, the first of its candidates that code accepts.

    ``chosen`` is ``{beat: [(candidate, job), …]}``. Returns ``(applied {beat: candidate}, refused {beat: why its last
    candidate was not kept})``. From the script as written every time, in the lesson's order: a second try must not
    stand on what the first one left behind, and the sentence that confirms one answer must be in place before the
    next beat's own question is tried.
    """
    order = _beats(lesson)
    for beat, written in zip(order, _beats(pristine)):               # beat by beat, in place: whoever holds a beat still holds it
        beat.clear()
        beat.update(copy.deepcopy(written))
    applied, refused = {}, {}
    for at, beat in enumerate(order):
        beat_id = str(beat["id"])
        for raw, job in chosen.get(beat_id) or []:
            why = _try(lesson, order, at, raw, job, lenient)
            if not why:
                applied[beat_id] = raw
                break
            if raw is not ONLY_CUT:
                refused[beat_id] = why
        if beat_id in applied and applied[beat_id] is not ONLY_CUT:
            refused.pop(beat_id, None)
    return applied, refused


def confirm_answers(lesson: dict, written: dict | None, model, log=print) -> list[str]:
    """See that the voice SAYS the answer of every question card when the video goes on. Returns the beats it added it for.

    The beat after a card opens by telling its answer: the writer is told so, and another question written by this
    pass brings its own confirming sentence. But a reviewer's rewrite of that next beat can drop the sentence (four of
    the ten lessons read on 2026-10-10), and then the video stops, asks, and never says how it comes out: only the
    app's card tells. Code can be sure only when the option's own words are there (``critic.says_answer``); otherwise a
    listener is asked once about what the voice says next, and is believed about "answered" only for words that are
    really there. Where the answer is not said, ONE sentence goes in front of the next beat: the one written with the
    card (``written[beat]["confirm"]``) when it can be used, else the plain "the answer is ..." of the lesson's language.
    Nothing is known, and nothing is done, when nobody can listen.
    """
    order = _beats(lesson)
    unsure = {}                                                     # beat id -> (place, card, what the voice says next)
    for at, beat in enumerate(order[:-1]):
        quiz = _card(beat)
        options, right = quiz.get("options") or [], quiz.get("answer_index")
        if not quiz or not (isinstance(right, int) and 0 <= right < len(options)):
            continue
        after = split_sentences(order[at + 1].get("narration", ""))[:2]
        if not any(critic.says_answer(sentence, quiz) for sentence in after):
            unsure[str(beat["id"])] = (at, quiz, after)
    if not unsure or model is None:
        return []
    blocks = [f"QUESTION at beat {beat_id}\n  THE CARD: {quiz.get('question', '')}\n  OPTIONS: " + " / ".join(str(o) for o in quiz["options"])
              + f"\n  RIGHT: {quiz['options'][quiz['answer_index']]}\n  NEXT: {' '.join(after)}" for beat_id, (_, quiz, after) in unsure.items()]
    try:
        answer = model("\n\n".join(blocks), AFTER)
    except Exception as exc:  # noqa: BLE001 - a check that cannot be made is reported, never fatal
        log(f"[questions] nobody listened for the answers after the questions ({type(exc).__name__}: {str(exc)[:100]})")
        return []
    checks = answer.get("checks") if isinstance(answer, dict) else answer
    if not isinstance(checks, list):
        log("[questions] the listener's answer could not be read: nothing is known about whether the answers are said")
        return []
    said = set()
    for check in checks:
        beat_id = critic.beat_id(check.get("beat"), unsure) if isinstance(check, dict) else ""
        if beat_id in unsure and (check.get("answered") is True or str(check.get("answered")).strip().lower() in ("true", "yes")) \
                and _quoted(str(check.get("quote") or ""), unsure[beat_id][2]):
            said.add(beat_id)
    language = str((lesson.get("brief") or {}).get("language") or lesson.get("language") or "en-IN").lower()
    added = []
    for beat_id, (at, quiz, _) in unsure.items():
        if beat_id in said:
            continue
        following = order[at + 1]
        answer_text = str(quiz["options"][quiz["answer_index"]])
        own = split_sentences(re.sub(r"\s+", " ", str(((written or {}).get(beat_id) or {}).get("confirm") or "")).strip())
        plain = _THE_ANSWER.get(language, "").format(answer=answer_text)
        for sentence in ([own[0]] if len(own) == 1 and not _is_question(own[0]) and len(own[0].split()) <= 30 else []) + ([plain] if plain else []):
            report = {"edits": [{"beat": following["id"], "narration": f"{sentence} {following.get('narration', '')}", "adds_a_sentence": True}]}
            critic.apply_edits(lesson, report, log=lambda *_: None)
            if following["id"] in report.get("edits_applied", []):
                added.append(beat_id)
                log(f"[questions] the answer to beat {beat_id}'s question was not said when the video went on: beat {following['id']} now opens with \"{sentence}\"")
                break
        else:
            log(f"[questions] the answer to beat {beat_id}'s question is not said when the video goes on, and no sentence could be put there")
    return added


def settle_pauses(lesson: dict, log=print) -> list[str]:
    """Take away a pause that follows a plain statement on a beat with no card. Returns the beats whose pause went.

    A pause is time to think about something just asked. Where a beat with a pause ends on a statement the video shows
    "YOUR TURN" over that statement and waits: the first lesson made end to end on 2026-10-10 did it twice in three
    minutes ("YOUR TURN: roots hold the plant ... Think about your answer"). The reviewer notes it (``critic.pause_gate``)
    and nothing acted on the note. A pause after an ORDER stays: that is time to do the thing ("draw four leaves").
    Not a word changes.
    """
    gone = []
    for beat in _beats(lesson):
        if _card(beat) or not float(beat.get("thinking_pause_seconds") or 0):
            continue
        last = (split_sentences(beat.get("narration", "")) or [""])[-1]
        if _is_question(last) or voice.is_order(last):
            continue
        beat["thinking_pause_seconds"] = 0.0
        gone.append(str(beat["id"]))
    if gone:
        log(f"[questions] {len(gone)} pause(s) that followed a statement, with nothing asked, taken out (beat {', '.join(gone)})")
    return gone


def improve(lesson: dict, brief: dict, llm, card: dict | None = None, keep_words: bool = False, log=print, listener=None) -> dict:
    """Write the lesson's question cards again and keep each change that is better. Returns a summary; ``lesson`` is changed in place.

    ``{"asked", "kept": [beats], "rewritten": [beats given another question], "refused": {beat: why}, "dropped":
    [beats], "faults_before", "faults_after", "told_before", "told_after", "unheard": [beats]}``: ``told_*`` count the
    questions a listener could answer by repeating the voice's last sentences (``listener`` is the model that listens;
    the writer's own when none is given); ``unheard`` are new questions nobody could listen to. Never raises for a bad
    answer: a question that cannot be improved stays as it was, unless it was one of ``BAD``.
    """
    stops = [str(beat["id"]) for beat in _beats(lesson) if _card(beat)]
    before = faults(lesson)
    summary = {"asked": len(stops), "kept": [], "rewritten": [], "refused": {}, "dropped": [], "faults_before": len(before),
               "faults_after": len(before), "told_before": 0, "told_after": 0, "unheard": [], "confirmed": [], "disputed": []}
    if not enabled() or llm is None or not stops:
        return summary
    hears = None if keep_words else (listener or llm)              # an author's script keeps its questions where they are
    told = (listen(lesson, hears, log=log) or {}) if hears else {}
    summary["told_before"] = summary["told_after"] = len(told)
    if told:
        log(f"[questions] {len(told)} of {len(stops)} question(s) can be answered by repeating what the voice has just said (beat {', '.join(told)})")
    # Every card answered by someone not told which option is meant (``solve``): a card that asks another thing than the
    # voice gets another question, voice and card written together; a marked option nobody would pick gets its card
    # written again. Also in an author's script, whose cards are a model's.
    solver = listener or llm
    solved = solve(lesson, solver, log=log) or {}
    if solved:
        before = faults(lesson, solved=solved)
        summary["faults_before"] = len(before)
        found = [f for f in before if f["fault"] in ("asks_other", "wrong_answer")]
        if found:
            log("[questions] answered without the marked option: " + "; ".join(f"beat {f['beat']} {f['fault']}" for f in found)[:300])
    jobs = plan(lesson, told, keep_words, solved)
    # An author's words cannot be cut or changed, so a card alone cannot cure a beat that asks nothing, talks on after
    # its question or asks about the lesson: nobody is asked to try.
    cannot = {}
    for fault in before if keep_words else []:
        if fault["fault"] in ("statement", "about_the_lesson", "not_last", "on_screen", "asks_other", "unsaid_number"):
            cannot[fault["beat"]] = "; ".join(filter(None, [cannot.get(fault["beat"]), fault["what"]]))
    jobs.update({b: None for b in cannot})
    # A teaching card holds the mistakes learners really make and why each fails (``card["mistakes"]``), and the
    # question the lesson opens on with what learners actually guess: the wrong options and their reasons.
    mistakes = []
    for m in (card or {}).get("mistakes") or []:
        if isinstance(m, dict) and m.get("mistake"):
            mistakes.append(str(m["mistake"])[:160] + (f" (it fails because: {str(m['why_it_fails'])[:160]})" if m.get("why_it_fails") else ""))
        elif m:
            mistakes.append(str(m)[:200])
    opening = (card or {}).get("opening_question") if isinstance((card or {}).get("opening_question"), dict) else {}
    prompt = (f"FOR: {brief.get('audience') or 'school students'}; language of the narration: {brief.get('language') or 'en-IN'}; "
              f"what they should be able to do afterwards: {brief.get('goal') or brief.get('topic') or ''}\n"
              + ("WHERE LEARNERS GO WRONG (take wrong options and their reasons from these):\n" + "\n".join(f"- {m}" for m in mistakes[:6]) + "\n" if mistakes else "")
              + (f"THE QUESTION THE LESSON OPENS ON, and what learners guess: {json.dumps(opening, ensure_ascii=False)[:400]}\n" if opening else "")
              + ((f"THE USUAL MISTAKE, as the requester put it: {brief['misconception']}\n") if brief.get("misconception") else "")
              + "\nTHE SCRIPT:" + _script(lesson, jobs, faults(lesson, told, solved)))
    system = SYSTEM + (KEEP_WORDS if keep_words else "")
    answer = _answered(llm, prompt, system, log)
    if answer is None:
        return summary
    pristine = copy.deepcopy(lesson)
    first = _candidates(answer, lesson)
    cut = {b: [(ONLY_CUT, CUT)] for b in stops if jobs[b] == CUT}     # ending a beat on its question needs no model
    chosen = {b: ([(first[b], jobs[b])] if b in first else []) + cut.get(b, []) for b in stops if b not in cannot}
    tried = {b: [raw] for b, raw in first.items()}                  # every card a model offered, for the log
    applied, refused = _replay(lesson, pristine, chosen, keep_words)
    asked_out = [b for b in (critic.beat_id(v, set(stops)) for v in (answer.get("drop") if isinstance(answer.get("drop"), list) else []))
                 if jobs.get(b) == NEW]
    checked: set[int] = set()                                       # new questions a listener heard in place and had to think about

    def hear(applied: dict) -> tuple[dict, dict]:
        """Among the NEW questions nobody has listened to yet: (the words that already say an answer, the questions that are another one again)."""
        new = {b for b, raw in applied.items() if jobs[b] == NEW and raw is not ONLY_CUT and id(raw) not in checked}
        found = _listened(lesson, hears, only=new, log=log) if hears and new else ({}, {})
        if found is None:
            return {}, {}
        checked.update(id(applied[b]) for b in new if b not in found[0])
        return found

    again, alike = hear(applied)                                    # kept by code, but the voice has already said the answer
    said = dict(again)
    retry = {}
    for beat_id in (b for b in stops if b not in cannot):
        if beat_id in again:
            retry[beat_id] = (f"a listener given only the last sentences could answer it by repeating them: \"{again[beat_id]}\". "
                              "It needs another case, one whose right answer is not what that sentence says")
        elif beat_id in alike:
            retry[beat_id] = (f"it needs the same step of reasoning as the question at beat {alike[beat_id]}: ask about another part of the "
                              "idea, or a case that comes out differently for another reason")
        elif beat_id in refused:
            retry[beat_id] = refused[beat_id]
        elif (beat_id not in applied or applied[beat_id] is ONLY_CUT) and beat_id not in asked_out:
            retry[beat_id] = "you wrote nothing for this stop"
    if retry:
        wrote = []
        for beat_id, why in retry.items():
            raw = first.get(beat_id) or {}
            was = (f"you wrote [{' / '.join(str(o) for o in raw.get('options') or [])}]"
                   + (f" for \"{raw.get('question')}\", asked as \"{raw.get('ask')}\"" if raw.get("ask") else "") + ". ") if raw.get("options") else ""
            wrote.append(f"- beat {beat_id} ({_JOB[jobs[beat_id]]}): {was}Not kept: {why}.")
        log(f"[questions] {len(retry)} card(s) asked for once more ({'; '.join(f'{b}: {w}' for b, w in retry.items())[:240]})")
        # What already stands from the first answer: a second try that cannot see it asks it again in other clothes
        # (the owner's sky lesson: "almost no air" at one stop, "a planet with no air" at the next).
        stand = [f"- beat {b}: \"{raw.get('question')}\" (right: {(raw.get('options') or [''])[int(raw.get('answer_index') or 0)]})"
                 for b, raw in applied.items() if jobs[b] == NEW and b not in retry and raw is not ONLY_CUT and raw.get("question")]
        kept_note = ("\nALREADY KEPT from your first answer (no beat above may ask one of these again, in the same words or in "
                     "others, or need the same step of reasoning):\n" + "\n".join(stand)) if stand else ""
        answer = _answered(llm, prompt + "\n\nWRITE AGAIN:\n" + "\n".join(wrote) + kept_note, system + RETRY, log)
        second = {b: raw for b, raw in (_candidates(answer, lesson) if answer else {}).items() if b in retry}
        for beat_id, raw in second.items():
            tried.setdefault(beat_id, []).append(raw)
        for beat_id in retry:
            # the new one first; the first one stays in reserve unless a listener could answer it by repeating the voice
            chosen[beat_id] = ([(second[beat_id], jobs[beat_id])] if beat_id in second else []) \
                + ([(first[beat_id], jobs[beat_id])] if beat_id in first and beat_id not in again else []) + cut.get(beat_id, [])
        applied, refused = _replay(lesson, pristine, chosen, keep_words)
        heard, _ = hear(applied)
        if heard:                                                   # the same thing asked in other words: not a third time
            said.update(heard)
            for beat_id in heard:
                chosen[beat_id] = [(raw, job) for raw, job in chosen[beat_id] if raw is not applied[beat_id]]
            applied, refused = _replay(lesson, pristine, chosen, keep_words)
    for beat_id, quote in said.items():
        if beat_id not in applied:
            refused[beat_id] = f"the voice has already said its answer: \"{quote}\""
    refused.update(cannot)
    order = _beats(lesson)
    index = {str(beat["id"]): n for n, beat in enumerate(order)}
    as_it_stands = faults(lesson)
    for beat_id in stops:
        beat = order[index[beat_id]]
        if beat_id in refused:
            summary["refused"][beat_id] = refused[beat_id]
            for raw in tried.get(beat_id, []):
                if raw is not applied.get(beat_id) and raw.get("options"):
                    log(f"[questions] beat {beat_id}, tried and not kept: {raw.get('question') or beat.get('quiz', {}).get('question') or ''} "
                        f"[{' / '.join(str(o) for o in raw['options'])}]" + (f", asked as: {raw['ask']}" if raw.get("ask") else ""))
        if beat_id in applied:
            summary["kept"].append(beat_id)
            quiz = beat["quiz"]
            if jobs[beat_id] == NEW:
                summary["rewritten"].append(beat_id)
            log(f"[questions] beat {beat_id} " + ("asks another question now" if jobs[beat_id] == NEW
                                                 else "ends on its question now" if applied[beat_id] is ONLY_CUT
                                                 else "keeps its question, with a better card")
                + f" ({quiz.get('kind') or 'think'}): {quiz['question']} [{' / '.join(quiz['options'])}]")
            continue
        # No question is better than a bad one: a stop that asks about the lesson itself, asks nothing, or only repeats
        # the voice, and could not be given an honest question, is taken out. In an author's own script only a card
        # under which the voice asks nothing goes: taking a card away changes none of their words.
        wrong = _of(as_it_stands, beat_id) + (["told"] if beat_id in told else []) \
            + (["asks_other"] if not (solved.get(beat_id) or {}).get("same", True) else [])
        if beat_id in asked_out or (any(f in ("statement", "asks_other", "unsaid_number") for f in wrong) if keep_words
                                    else any(f in BAD for f in wrong)):
            beat.pop("quiz", None)
            beat["thinking_pause_seconds"] = 0.0                   # the lesson does not stop here; not a word changes
            summary["dropped"].append(beat_id)
    # The cards as they now stand, answered once more without their marked option: one whose marked option is still not
    # the one worked out, or that still asks another thing or another case than the voice, is taken out. A wrong card
    # TEACHES a wrong fact, and a card under another question is a second question the learner never heard; a stop
    # without a card only asks. (Another question written here had the voice say "cut it along the diagonal" over the
    # rectangle on screen while its card named one of other sides: right answer, wrong case.)
    again_solved: dict = {}
    if solved and any(_card(beat) for beat in order):
        again_solved = solve(lesson, solver, log=log) or {}
        for beat_id, worked in again_solved.items():
            beat = order[index[beat_id]]
            # "Another thing" is a judgement that wavers on a fair card (asked twice, one card was "the same" and then
            # not): a card nobody wrote again goes for it only when both looks say so. A wrong option goes on one look.
            asks = bool(closing(beat.get("narration", ""))[1])
            other = asks and not worked["same"] and (beat_id in summary["rewritten"] or not (solved.get(beat_id) or {}).get("same", True))
            if worked["pick"] != _card(beat).get("answer_index") or other:
                log(f"[questions] beat {beat_id}: " + (f"the option marked right on \"{beat['quiz'].get('question')}\" is still not the one "
                                                       f"worked out ({worked['work'][:160]})" if worked["pick"] != _card(beat).get("answer_index")
                                                       else f"the card asks for {worked['card']}, the voice for {worked['voice']}")
                    + ": the card is taken out")
                beat.pop("quiz", None)
                beat["thinking_pause_seconds"] = 0.0
                summary["dropped"].append(beat_id)
                summary["disputed"].append(beat_id)
                if beat_id in summary["kept"]:
                    summary["kept"].remove(beat_id)
                if beat_id in summary["rewritten"]:
                    summary["rewritten"].remove(beat_id)
    summary["unheard"] = [b for b in summary["rewritten"] if hears and id(applied[b]) not in checked]
    if hears:                                                       # (an author's own script: not a word is added)
        summary["confirmed"] = confirm_answers(lesson, {b: raw for b, raw in applied.items() if raw is not ONLY_CUT}, hears, log=log)
    summary["faults_after"] = len(faults(lesson, solved=again_solved))
    summary["told_after"] = sum(1 for b in stops if b in told and b not in summary["rewritten"] and b not in summary["dropped"])
    lesson["questions"] = {k: summary[k] for k in ("asked", "kept", "rewritten", "dropped", "faults_before", "faults_after", "told_before",
                                                   "told_after", "confirmed", "disputed")}
    log(f"[questions] {summary['asked']} question card(s): {len(summary['kept']) - len(summary['rewritten'])} kept with a better card, "
        f"{len(summary['rewritten'])} given another question"
        + (f", {len(summary['dropped'])} stop(s) taken out" if summary["dropped"] else "")
        + (f", {len(summary['refused'])} not kept ({'; '.join(f'{b}: {w}' for b, w in summary['refused'].items())[:200]})" if summary["refused"] else "")
        + f"; faults {summary['faults_before']} → {summary['faults_after']}"
        + (f"; answerable by repeating the voice {summary['told_before']} → {summary['told_after']}" if hears else "")
        + (f"; nobody could listen to {', '.join(summary['unheard'])}" if summary["unheard"] else "")
        + (f"; the answer is now said after beat {', '.join(summary['confirmed'])}" if summary["confirmed"] else ""))
    return summary


def _confirms(sentence: str, quiz: dict) -> bool:
    """Whether a beat's opening sentence is the one that confirms the answer of the card before it."""
    options, right = quiz.get("options") or [], quiz.get("answer_index")
    answer = options[right] if isinstance(right, int) and 0 <= right < len(options) else ""
    key = {w for w in _words(f"{answer} {quiz.get('question', '')}") if len(w) >= 4 and w not in _SMALL and w not in _ASKING}
    # two words of the card at least: one alone is the lesson's own subject ("blue"), which any sentence may hold
    return len(key & set(_words(sentence))) >= 2 or len(str(sentence).split()) <= 6


def _try(lesson: dict, order: list[dict], at: int, raw: dict, job: str, lenient: bool = False) -> str:
    """Do one job at one beat (and, for another question, the next beat's first sentence). '' when kept, else why not."""
    beat = order[at]
    old = _card(beat)
    first = {"beat": copy.deepcopy(beat), "next": copy.deepcopy(order[at + 1]) if at + 1 < len(order) else None}
    was = _of(faults(lesson), beat["id"])

    def undo(reason: str) -> str:
        beat.clear()
        beat.update(first["beat"])
        if first["next"] is not None:
            order[at + 1].clear()
            order[at + 1].update(first["next"])
        return reason

    said_before, old_close = closing(beat.get("narration", ""))
    if raw is ONLY_CUT:
        quiz = copy.deepcopy(old)
    else:
        quiz = clean(raw, old)
        if quiz is None:
            return "no usable card (two to four options, one of them right, and a reason for each)"
    gone: list[str] = []                                            # sentences of the beat that are no longer said
    narration, asked = "", []
    if job in (CARD, CUT):
        if raw is not ONLY_CUT:
            # The same question: a card written for another one (a new case, new closing words) would put that
            # question's answers under this one. (An author's script is told to send neither; what it sends is ignored.)
            closing_words = _flat(str(raw.get("ask") or ""))
            if not lenient and (str(raw.get("new_case") or "").strip() or (closing_words and closing_words != _flat(" ".join(old_close[:1])))):
                return "this question is kept as it is: give only its three short answers and a reason for each, no new closing words and no new case"
            quiz["question"] = old.get("question") or quiz["question"]
        beat["quiz"] = quiz
        if job == CUT and len(old_close) > 1:
            gone = old_close[1:]
            narration = " ".join(said_before + old_close[:1])
    else:
        answer = quiz["options"][quiz["answer_index"]]
        right, mine = _flat(answer), {w for w in _words(answer) if w not in ("the", "a", "an")}
        for earlier in order[:at]:
            other = _card(earlier)
            if not other or not (isinstance(other.get("answer_index"), int) and 0 <= other["answer_index"] < len(other["options"])):
                continue
            theirs = other["options"][other["answer_index"]]
            shared = {_flat(o) for o in other["options"]} & {_flat(o) for o in quiz["options"]}
            if _flat(theirs) == right and len(shared) >= 2:
                return f"it asks what beat {earlier.get('id')} already asks"
            # The idea used on a new case earns its pause when the case comes out DIFFERENTLY: a second question whose
            # answer is the first one's again ("Blue light", then "Blue") is answered from the lesson's refrain.
            # ("More than blue" is not "Blue" again: the small words are the answer there, so only articles are left out.)
            said = {w for w in _words(theirs) if w not in ("the", "a", "an")}
            if quiz.get("kind") == "apply" and mine and said and (mine <= said or said <= mine):
                return (f"its right answer ({answer}) is the one beat {earlier.get('id')} has already had the learner pick: "
                        "change one thing in the case so that the answer comes out different")
        beat["quiz"] = quiz
        ask = re.sub(r"\s+", " ", str(raw.get("ask") or "")).strip()
        if not _is_question(ask):
            return undo("its closing words do not end with the question")
        asked = split_sentences(ask)
        # What the new closing words take the place of: the present question, anything said after it, any question
        # asked just before it (two in a row are one asking), the sentences the model says only set the old one up,
        # and a sentence the new words say again. Never the whole beat.
        gone = list(old_close)
        while len(said_before) > 1 and _is_question(said_before[-1]):
            gone.insert(0, said_before.pop())
        try:
            extra = min(max(int(raw.get("replaces") or 0), 0), 2)
        except (TypeError, ValueError):
            extra = 0
        while extra and len(said_before) > 1:
            gone.insert(0, said_before.pop())
            extra -= 1
        while len(said_before) > 1 and says_again(said_before[-1], asked):
            gone.insert(0, said_before.pop())
        while len(asked) > 1 and says_again(asked[0], said_before[-3:]):
            asked = asked[1:]
        if quiz.get("kind") == "apply":
            # A case is new when the script has not spoken of it: one of its words at least is nowhere before the question.
            case = [w for w in _words(raw.get("new_case") or "") if len(w) >= 4 and w not in _SMALL and w not in _NOT_A_CASE]
            spoken = set(_words(" ".join(b.get("narration", "") for b in order[:at]) + " " + " ".join(said_before)))
            if not case or all(w in spoken for w in case):
                return undo("its 'new case' is one the script has already spoken of" if case else "an 'apply' question with no new case named")
        narration = " ".join(said_before + asked)
    if narration:
        # The screen follows the voice: a line that came up on words no longer said ("First decision", "Choose the
        # relation") would stand there under a question it has nothing to do with. Such lines go.
        lost, still = " ".join(gone).lower(), narration.lower() if job == CUT else " ".join(said_before).lower()
        steps = [step for step in beat.get("steps") or []
                 if not (str(step.get("say", "")).strip() and str(step["say"]).lower() in lost and str(step["say"]).lower() not in still)]
        if job == NEW:                                              # ... and the new question is the beat's last line, as a writer puts it
            steps = [step for step in steps if _flat(step.get("show", "")) != _flat(quiz["question"])][:writer.MAX_STEPS - 1]
            steps.append({"say": " ".join(asked[-1].split()[:4]), "show": quiz["question"], "kind": "key",
                          "highlight": not any(step.get("highlight") for step in steps)})
        beat["steps"] = steps
        report = {"edits": [{"beat": beat["id"], "narration": narration}]}
        confirm = re.sub(r"\s+", " ", str(raw.get("confirm") or "")).strip() if job == NEW else ""
        if confirm and first["next"] is not None:
            opening = split_sentences(order[at + 1].get("narration", ""))
            # The next beat opens by confirming the OLD answer: that sentence is replaced. Where its opening is about
            # something else (the writer did not confirm), the new confirmation goes in front and nothing is lost.
            rest = opening[1:] if len(opening) > 1 and _confirms(opening[0], old) else opening
            report["edits"].append({"beat": order[at + 1]["id"], "narration": " ".join([confirm] + rest), "adds_a_sentence": rest is opening})
        critic.apply_edits(lesson, report, log=lambda *_: None)
        if beat["id"] not in report.get("edits_applied", []):
            return undo("its closing words were refused (they change the language, or the beat's length by too much)" if job == NEW
                        else "the beat could not be cut to end on its question")
        if len(report["edits"]) > 1 and order[at + 1]["id"] not in report.get("edits_applied", []):
            return undo("the next beat could not take the sentence that confirms the answer")
        if job == NEW and float(beat.get("thinking_pause_seconds") or 0) < 4:
            beat["thinking_pause_seconds"] = 5.0                  # a question with a card is given time to answer
    if job == NEW and raw is not ONLY_CUT:
        # A question written here sets its own case up: the numbers its card names are said in THIS beat, not merely
        # somewhere in the lesson (a card about "a 6 by 8 cm rectangle" under a voice that only asked "what is the area
        # of one triangle?" passed the lesson-wide rule because six and eight had been said for other things).
        unsaid = sorted(case_numbers(quiz.get("question", "")) - spoken_numbers(beat.get("narration", "")))
        if unsaid:
            return undo(f"its card names {', '.join(unsaid)}, which its closing words never say: the voice sets the new case up, numbers and all")
    now = faults(lesson)
    hard = [f["what"] for f in now if f["beat"] == str(beat["id"]) and f["fault"] in HARD]
    if hard and raw is not ONLY_CUT:
        return undo("; ".join(hard))
    if len(_of(now, beat["id"])) > len(was):
        return undo("more is wrong with it than with the card it replaces")
    return ""
