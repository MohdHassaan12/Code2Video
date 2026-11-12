"""How a script SOUNDS, measured: so "it does not feel natural" becomes lines someone can act on.

On 2026-10-09 the owner watched the first lessons written from a teaching card and said
they "feel a bit off, not natural". Read across five of them (timeline.json and the
narration), the same things were in every one, so they are the system's doing and not one
lesson's:

* an order in about half of all Hinglish sentences ("dekhiye", "sochiye", "kijiye":
  21 of 44, 22 of 45, 23 of 57);
* "Ab" opening seven or eight sentences, most of them the first sentence of a beat;
* the opening question asked again in other words, up to four times in five minutes;
* sentences about the screen ("Sabse chhote picture mein …", "side by side pictures"),
  nine in one lesson;
* beats that are a row of statements with no joining word ("Cell ek … hai. Bahut se
  cells … hain. Food aur oxygen … hain. Waste woh cheez hai …");
* English sentences with Hindi glue ("one thin outer edge aur one soft inside space
  hai", "controls what enters and leaves ko kis part se connect karenge?").

How a teacher talks instead is written for the model in
``skills/teaching-script/voice.md``. This module is the other half: code that finds
each fault and words it as a reviewer's finding, so the revision round rewrites the beat
("a measurement nobody acts on is not a check"). ``report`` gives the same things as
numbers for the log.

Nothing here judges whether a lesson is engaging. Every finding is something that can
be pointed at in a named beat, and each rule is deliberately loose: it fires on what
was plainly wrong in those lessons and keeps quiet when in doubt, because a rewrite
asked for without cause can remove something the lesson needed.

A lesson made from a pasted script is never measured: its words are the author's.
"""
from __future__ import annotations

import copy
import os
import re
from collections import Counter
from typing import Any, Callable

from .. import knobs
from . import skill

LLM = Callable[[str, str], Any]

_SENTENCE = re.compile(r"(?<=[.?!।])\s+")          # the danda ends a Hindi sentence
_WORD = re.compile(r"[A-Za-z][A-Za-z'\-]*")

# Hindi glue in Latin letters: enough to tell that a sentence is Hindi and where an English run ends.
HINDI = set(
    "hai hain tha thi hoga hogi honge hota hoti hote hua hui hue ho ka ki ke ko mein me se par tak aur ya yeh ye yah "
    "woh wo kya kyun kyon kyunki kyonki kaise kaisa kitna kitne kitni kab kahan kaun kis toh to ab abhi bhi nahi nahin na "
    "hum aap tum apna apni apne iska iski iske uska uski uske inhe unhe isse usse isliye lekin magar agar phir jaise waise "
    "aise wala wali wale liye saath sath sirf bas bahut thoda zyada kam har koi kuch sab dono ek do chahiye sakta sakti "
    "sakte raha rahi rahe kar karo karna karte karta karti karke kiya kiye karega karegi karenge gaya gayi gaye jata jati "
    "jate jaata jaati jaate liya diya dete deta deti lena dena aata aati aate hoon yahan wahan idhar udhar andar bahar upar "
    "neeche pehle baad jab tab matlab yaani yani isi usi inka unka kehte kehta bana banta banti bante dekhiye sochiye "
    "kijiye lijiye dekho socho is us in un jo jis".split())
#: Also English words: they end an English run, and never count towards calling a sentence Hindi.
_ALSO_ENGLISH = set("to do is us in me hum tab par na so".split())
JOINERS = set("toh isliye kyunki kyonki lekin magar matlab yaani yani phir tabhi jabki warna varna tab islie "
              "because so but then since therefore hence while although unless otherwise instead".split())
_JOIN_PHRASE = re.compile(r"\b(which means|that is why|that's why|this is why|as a result|and then|aur phir|is wajah se|"
                          r"iska matlab|is tarah)\b|,\s*par\b", re.I)

# An order. Hindi: the polite forms end in -iye/-ijiye; a few words only look like one.
_NOT_AN_ORDER = {"chahiye", "isliye", "kisliye", "liye", "kiye", "diye", "piye", "jiye", "siye", "gaye", "naye",
                 "chaliye", "aaiye"}          # "chaliye, … dekhte hain" is doing it together, which is what is wanted
_POLITE = re.compile(r"\b[a-z]{2,}(?:ijiye|iyega|iye)\b", re.I)
_PLAIN = re.compile(r"\b(dekho|socho|batao|likho|suno|bolo|banao|gino|samjho)\b", re.I)
_ENGLISH_ORDER = re.compile(r"^(?:now|next|then|so|first|and)?,?\s*(look|observe|notice|watch|see|consider|imagine|think|take|"
                            r"draw|write|count|note|remember|recall|pause|try|compare|check|find|say|start|make|lay|list|"
                            r"test|guess|picture|put|change|keep|trace|follow|ask)\b", re.I)

# The lesson's PLAN read aloud: the framework's stage names said as narration ("So the claim is: …", "Start small",
# "Change one thing", "Test it"). Read on the five hard-question lessons of 2026-10-19, which the owner called
# "very complex and cryptic"; fifteen lectures on the same topics on YouTube never talk like this.
_PLAN_TALK = re.compile(r"\b(here is the claim|the claim is|a claim worth|change one thing|test it|start small|make a guess|"
                        r"guess first|your turn|say it back|recall it|predict first|now predict|the key move|"
                        r"where intuition breaks|the argument is|the rule is this|the claim for|so the claim|"
                        r"here is the (?:key )?(?:question|problem|result|idea|catch)|the key question)\b", re.I)
#: Stock phrases a listener hears as a machine talking, never as a teacher (the owner's teaching notes, 2026-10-20:
#: "avoid AI phrases"). Whole phrases only: "journey" alone would catch a lesson about a car's journey.
_STOCK = re.compile(r"\b(let'?s dive (?:in|into)|dive deep|in this video|in today'?s (?:video|lesson)|fascinating|mind[- ]blowing|"
                    r"simply put|in conclusion|it'?s important to note|it is important to note|embark|delve|"
                    r"(?:our|this|a) (?:learning )?journey (?:of|into|through)|buckle up)\b", re.I)
#: How often lecturers ask, measured on the YouTube lectures found for those five topics (their own captions, about
#: 4,000 words): 0.1 to 1.0 questions in 100 words, against 1.7 to 2.7 in our lessons. A lesson asks about once a
#: minute, plus its opening question.
QUESTIONS_PER_MINUTE = 1

# Talking about the screen instead of the thing on it.
_SCREEN = re.compile(r"\b(pictures?|screen|diagram|images?|slide|animation|video|tasveer|chitra)\b|\bside[- ]by[- ]side\b|"
                     r"\bfigure\b(?! out)|\blabels? ke saath\b|\bon the (?:left|right) (?:side )?of the (?:screen|picture)\b", re.I)
#: A sentence that tells the learner to make their OWN picture is not about the screen.
_OWN_WORK = re.compile(r"\b(draw|paper|pencil|notebook|copy|sheet|banaiye|banao|page)\b", re.I)

#: Words that describe a thing: after "one" they show it was used as an article.
_DESCRIBING = set("thin thick round soft hard small big large tiny little long short tall wide narrow outer inner upper lower "
                  "single simple irregular regular new old empty full flat curved straight bright dark heavy light smooth "
                  "rough closed open blank coloured oval square".split())
_MATHS_WORDS = set("zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen "
                   "seventeen eighteen nineteen twenty thirty forty fifty sixty seventy eighty ninety hundred thousand by "
                   "plus minus into times equals squared cubed divided over point half third fourth and is".split())
#: English words that are never part of a subject's term: a run that holds one is a phrase, not a name.
_FUNCTION = set("what that which who whose the of are was were does has have when where its their this these those it they "
                "can will would should than there here".split())
_STOP = HINDI | set("the a an of to in on at for with from that this these those it its is are was were be been do does did "
                    "can could will would should what which who why how when where your you we our they them their there "
                    "have has had not and or but if then than so as about into out up down one two three four five".split())

ENGLISH_RUN = 4            # this many English words in a row, one of them a function word, is a phrase nobody translated
ORDERS_IN_A_BEAT = 2       # more than one order in a beat ...
ORDER_SHARE = 0.5          # ... and in at least this share of its sentences
WEAK_OPENERS = ("ab", "now", "toh", "so", "next", "then", "phir", "aur", "and")
SAME_QUESTION = 0.6        # share of the shorter question's own words found in the other
MIN_SHARED = 3
_NUMBER_WORDS = set("zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen "
                    "seventeen eighteen nineteen twenty thirty forty fifty sixty seventy eighty ninety hundred thousand".split())


def sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENTENCE.split(str(text or "").strip()) if s.strip()]


def _words(sentence: str) -> list[str]:
    return [w.lower() for w in _WORD.findall(sentence)]


def is_order(sentence: str) -> bool:
    polite = [m.group(0).lower() for m in _POLITE.finditer(sentence)]
    return any(w not in _NOT_AN_ORDER for w in polite) or bool(_PLAIN.search(sentence)) or bool(_ENGLISH_ORDER.match(sentence.strip()))


def talks_about_the_screen(sentence: str) -> str | None:
    """The words that point at the screen, or None."""
    if _OWN_WORK.search(sentence):
        return None
    found = _SCREEN.search(sentence)
    return found.group(0) if found else None


def is_hindi(sentence: str) -> bool:
    return sum(1 for w in _words(sentence) if w in HINDI and w not in _ALSO_ENGLISH) >= 2


def _looks_hindi(word: str) -> bool:
    return word in HINDI or bool(_POLITE.fullmatch(word)) or word.endswith(("enge", "egi", "ega", "kar", "oge"))


def english_phrase(sentence: str) -> str | None:
    """Words in a Hindi sentence that were plainly made in English first, or None.

    Two shapes, both read off real lessons. "one" used as an article before a describing
    word ("one thin outer edge", "one round control part"): the count is not part of any
    working, and the describing words are a short list because a word this module does not
    know may just as well be Hindi ("one factor akela reh gaya"). And a run of English words that holds a function word ("controls what enters
    and leaves ko …"): a subject's term never contains "what" or "that". A list of terms
    ("membrane, cytoplasm, nucleus"), a line of working ("three by four plus one by two")
    and any Hindi word this module does not know are all left alone: Hindi's vocabulary
    is open, so "not in the list" must never be read as "English".
    """
    if not is_hindi(sentence):
        return None
    words = _words(sentence)
    for at, word in enumerate(words[:-1]):
        if word == "one" and words[at + 1] in _DESCRIBING:
            return " ".join(words[at:at + 4])
    run: list[str] = []
    for word in words + [""]:
        if word and not _looks_hindi(word):
            run.append(word)
            continue
        if (len(run) >= ENGLISH_RUN and any(w in _FUNCTION for w in run)
                and sum(1 for w in run if w in _MATHS_WORDS) * 2 < len(run)):
            return " ".join(run)
        run = []
    return None


def _content(sentence: str) -> set[str]:
    """A question's own words: no glue, no numbers, plural and singular as one."""
    out = set()
    for word in _words(sentence):
        parts = word.split("-")
        if len(word) < 3 or word in _STOP or any(part in _NUMBER_WORDS for part in parts):
            continue
        out.add((word[:-1] if word.endswith("s") and len(word) > 4 else word)[:6])
    return out


def _numbers(sentence: str) -> set[str]:
    return {part for word in _words(sentence) for part in word.split("-") if part in _NUMBER_WORDS}


def same_question(first: str, second: str) -> bool:
    """Whether two questions ask the same thing in other words.

    The same form about different numbers ("Is eighteen a square number?", "Is two
    thousand eight hundred a square number?") is practice, not repetition.
    """
    if _numbers(first) != _numbers(second):
        return False
    a, b = _content(first), _content(second)
    shared = a & b
    return len(shared) >= MIN_SHARED and len(shared) >= SAME_QUESTION * min(len(a), len(b))


def _joined(sentence: str) -> bool:
    return any(w in JOINERS for w in _words(sentence)) or bool(_JOIN_PHRASE.search(sentence))


def _beats(lesson: dict):
    chapters = lesson.get("chapters") or []
    for at, chapter in enumerate(chapters):
        for beat in chapter.get("beats") or []:
            yield at, chapter, beat, sentences(beat.get("narration", ""))


def _is_script(lesson: dict) -> bool:
    return (lesson.get("brief") or {}).get("mode") == "script"


def _finding(beat: dict, what: str, fix: str, severity: str = "minor") -> dict:
    return {"severity": severity, "beat": beat.get("id"), "resolved": False, "what": f"voice: {what}", "fix": fix}


def findings(lesson: dict) -> list[dict]:
    """What a listener would notice, as reviewer's findings (one beat each). [] for a pasted script."""
    if _is_script(lesson):
        return []
    out: list[dict] = []
    hinglish = str((lesson.get("brief") or {}).get("language") or lesson.get("language") or "").lower() in ("hinglish", "hi-in")
    last_chapter = len(lesson.get("chapters") or []) - 1
    asked: list[tuple[str, str]] = []                      # (beat id, question) in the order they are asked
    previous_opener = ""
    for at, chapter, beat, said in _beats(lesson):
        if not said:
            continue
        task = any(_OWN_WORK.search(s) for s in said)       # the beat that sets the try-it task is a list of things to do
        orders = [s for s in said if is_order(s)]
        # The recap asks the learner to say and do things: that is its job, so orders are not counted there.
        if not task and at != last_chapter and len(orders) >= ORDERS_IN_A_BEAT and len(orders) >= ORDER_SHARE * len(said):
            out.append(_finding(beat, f"{len(orders)} of {len(said)} sentences are orders (“{orders[0][:60]}”, “{orders[1][:60]}”)",
                                "keep at most one order in the beat; say the others as what is happening or as something done "
                                "together (“ab hum …”, “yahan …”), with the same facts"))
        screen = next((hit for hit in (talks_about_the_screen(s) for s in said) if hit), None)
        if screen:
            out.append(_finding(beat, f"it talks about the screen (“{screen}”) instead of the thing on it",
                                "name the thing itself and point with yeh / yahan (this, here); never mention the picture, "
                                "the screen, a label or where things sit"))
        openers = Counter(_words(s)[0] for s in said if _words(s))
        again, times = openers.most_common(1)[0] if openers else ("", 0)
        opener = _words(said[0])[0] if _words(said[0]) else ""
        if times >= 3 or (times >= 2 and again in WEAK_OPENERS):
            out.append(_finding(beat, f"{times} of its sentences open with “{again.capitalize()}”",
                                "open each sentence differently: start from what the last one ended on, with a joining word"))
        elif opener and opener == previous_opener and opener in WEAK_OPENERS:
            out.append(_finding(beat, f"it opens with “{opener.capitalize()}”, as the beat before it does",
                                "open by picking up the last thought of the beat before, not with the same word"))
        previous_opener = opener
        plain = [s for s in said if not s.endswith("?")]
        if not task and len(said) >= 3 and len(plain) >= 3 and not any(_joined(s) for s in said):
            out.append(_finding(beat, "its sentences are a row of statements with no joining word between them",
                                "say it as one joined thought: link the sentences with toh, isliye, kyunki, lekin, matlab "
                                "(so, because, but, which means), keeping every fact"))
        plan = next((s for s in said if _PLAN_TALK.search(s)), None)
        if plan:
            out.append(_finding(beat, f"it reads the lesson's plan aloud (“{_PLAN_TALK.search(plan).group(0)}”)",
                                "say what happens and why, as a teacher explaining it; never name the step of the lesson "
                                "(the claim, the test, your turn)"))
        stock = next((s for s in said if _STOCK.search(s)), None)
        if stock:
            out.append(_finding(beat, f"it uses a stock phrase (“{_STOCK.search(stock).group(0)}”)",
                                "say the thought in plain words of your own, as a teacher talking to one learner"))
        shout = next((s for s in said if s.endswith("!")), None)
        if shout:
            out.append(_finding(beat, f"it exclaims (“{shout[:60]}”)",
                                "say why it matters in a plain sentence; let the idea carry the surprise, not the punctuation"))
        noted = next((s for s in said if ":" in s and not re.search(r"\d:\d", s)), None)
        if noted:
            out.append(_finding(beat, f"it is written like notes, with a colon (“{noted[:70]}”)",
                                "say it as full spoken sentences joined by so, because, which means; no colons"))
        asking = [s for s in said if s.endswith("?")]
        if len(asking) > 1:
            out.append(_finding(beat, f"it asks {len(asking)} questions (“{asking[0][:50]}”, “{asking[1][:50]}”)",
                                "keep at most one question in the beat; say the others as the explanation they lead to"))
        if hinglish:
            phrase = next((hit for hit in (english_phrase(s) for s in said) if hit), None)
            if phrase:
                out.append(_finding(beat, f"an English phrase inside a Hindi sentence (“{phrase}”)",
                                    "make the sentence in Hindi and keep only the subject's terms and the numbers of the "
                                    "working in English (“ek patli si boundary”, never “one thin outer edge”)"))
        for question in (s for s in said if s.endswith("?")):
            earlier = next((b for b, q in asked if b != beat.get("id") and same_question(q, question)), None)
            if earlier and at != last_chapter:               # the recap may ask the lesson's question again
                out.append(_finding(beat, f"it asks again what beat {earlier} already asked (“{question[:80]}”)",
                                    "do not ask it a second time: build towards its answer here, or ask the next question "
                                    "the lesson needs"))
            asked.append((beat.get("id"), question))
    out += _too_many_questions(lesson, last_chapter)
    return out


def questions_allowed(lesson: dict) -> int:
    """How many questions a lesson of this length may ask: about one a minute, the opening one included, at least two."""
    minutes = float((lesson.get("brief") or {}).get("duration_minutes") or 0) or len(
        " ".join(b.get("narration", "") for _, _, b, _ in _beats(lesson)).split()) / 150
    return max(2, round(QUESTIONS_PER_MINUTE * minutes) + 1)


def _too_many_questions(lesson: dict, last_chapter: int) -> list[dict]:
    """When a lesson asks more than it may, the questions it answers itself in passing are the first to go.

    A question that ENDS a beat is a stop (a pause, a card, the next beat confirming it): its
    place is decided with the lesson's plan, and a rewrite of one beat cannot move it. A
    question in the middle of a beat is the teacher thinking aloud, and saying the thought
    instead loses nothing.
    """
    beats = [(at, beat, said) for at, _, beat, said in _beats(lesson) if said]
    total = sum(1 for _, _, said in beats for s in said if s.endswith("?"))
    over = total - questions_allowed(lesson)
    out = []
    for at, beat, said in beats[1:]:                       # the opening beat keeps its question
        if over <= 0:
            break
        inside = [s for s in said[:-1] if s.endswith("?")]
        if inside and at != last_chapter:
            out.append(_finding(beat, f"the lesson asks {total} questions where about {total - over} fit its length, and this "
                                      f"beat asks one it answers itself (“{inside[0][:60]}”)",
                                "say that thought as a statement that explains, keeping every fact; leave the beat's last "
                                "sentence as it is"))
            over -= len(inside)
    return out


def report(lesson: dict) -> dict:
    """The same things as numbers, for the log and the audit. Empty for a pasted script."""
    if _is_script(lesson):
        return {}
    said = [s for _, _, _, each in _beats(lesson) for s in each]
    if not said:
        return {}
    openers = Counter(_words(s)[0] for s in said if _words(s))
    opener, times = openers.most_common(1)[0]
    stops = [float(beat.get("thinking_pause_seconds") or 0) for _, _, beat, _ in _beats(lesson)]
    found = findings(lesson)
    kinds = Counter("asked again" if "asks again" in f["what"] else "orders" if "are orders" in f["what"] else
                    "screen" if "the screen" in f["what"] else "unjoined" if "row of statements" in f["what"] else
                    "translated" if "English phrase" in f["what"] else "plan aloud" if "plan aloud" in f["what"] else
                    "notes" if "like notes" in f["what"] else "questions" if "questions" in f["what"] else
                    "copied" if "copies" in f["what"] else "stock" if "stock phrase" in f["what"] else
                    "exclaims" if "exclaims" in f["what"] else "same opener" for f in found)
    return {"sentences": len(said), "orders": sum(1 for s in said if is_order(s)),
            "about_the_screen": sum(1 for s in said if talks_about_the_screen(s)),
            "questions": sum(1 for s in said if s.endswith("?")), "questions_allowed": questions_allowed(lesson),
            "colons": sum(s.count(":") for s in said), "stock": sum(1 for s in said if _STOCK.search(s)), "plan_aloud": sum(1 for s in said if _PLAN_TALK.search(s)),
            "words_per_sentence": round(sum(len(_words(s)) for s in said) / len(said), 1), "top_opener": opener, "top_opener_times": times,
            "stops": sum(1 for s in stops if s), "stop_seconds": round(sum(stops), 1),
            "chapters": len(lesson.get("chapters") or []), "findings": len(found), "by_kind": dict(kinds)}


def line(lesson: dict) -> str:
    """One line for the job log."""
    r = report(lesson)
    if not r:
        return ""
    kinds = ", ".join(f"{n} {k}" for k, n in sorted(r["by_kind"].items(), key=lambda kv: -kv[1])) or "nothing to rewrite"
    return (f"{r['orders']} of {r['sentences']} sentences are orders; “{r['top_opener'].capitalize()}” opens {r['top_opener_times']}; "
            f"{r['about_the_screen']} talk about the screen; {r['questions']} questions, {r['stops']} stops ({r['stop_seconds']:.0f} s); "
            f"to rewrite: {kinds}")


# ── acting on it ─────────────────────────────────────────────────────────────

POLISH_SYSTEM = """You make the narration of an animated lesson sound like a teacher talking. For each listed beat you get
what is said, what is on screen while it is said, and what a listener would notice. Rewrite ONLY the narration of those
beats so the listed faults are gone.

What must not change:
- every fact, number, term and step of working, and their order. You change HOW it is said, never WHAT is taught;
- the language of the lesson. In a Hindi or Hinglish lesson the conversation is Hindi and every number of the working,
  unit, operation and subject term is English, written as words ("three by four", "equals", "cell membrane");
- the picture and the question card: they are already made. The beat still talks about that picture and still leads to
  that question;
- the words on screen: every SHOW line must still be said, in its own words, in the same order, so it can appear on time;
- a beat that ENDS with a question still ends with that question; a beat that does not, must not end with one;
- about the same length (within 15%). Narration is spoken: no symbols, no digits, no brackets, no stage directions.

Return ONLY JSON: {"edits": [{"beat": "03", "narration": "..."}]}

HOW A TEACHER TALKS:
"""


def enabled(card: dict | None) -> bool:
    """On for a lesson written from a teaching card; ``LESSONFORGE_VOICE_POLISH`` = 1 or 0 decides for every lesson.

    It is one more model call for a lesson that has something to rewrite, so it rides with
    the card (already a billing choice) unless the owner says otherwise.
    """
    asked = (knobs.get("LESSONFORGE_VOICE_POLISH") or "").strip()
    return asked == "1" if asked in ("0", "1") else bool(card)


def _ask(lesson: dict, found: list[dict]) -> str:
    by_id = {beat.get("id"): beat for _, _, beat, _ in _beats(lesson)}
    wanted: dict[str, list[str]] = {}
    for f in found:
        if f["beat"] in by_id:
            wanted.setdefault(f["beat"], []).append(f"{f['what'][7:]} — {f['fix']}")
    blocks = [f"LESSON: {lesson.get('title', '')} — language: {(lesson.get('brief') or {}).get('language') or lesson.get('language')}"]
    order = [beat.get("id") for _, _, beat, _ in _beats(lesson)]
    for bid, problems in wanted.items():
        beat = by_id[bid]
        figure, quiz = beat.get("figure") or {}, beat.get("quiz") or {}
        before = by_id.get(order[order.index(bid) - 1]) if order.index(bid) else None
        blocks.append(
            f"\n[beat {bid}]"
            + (f"\n  THE BEAT BEFORE IT ENDS: …{' '.join(sentences(before.get('narration', ''))[-1:])}" if before else "")
            + f"\n  SAY: {beat.get('narration', '')}"
            + (f"\n  PICTURE (will not change): {figure.get('describe') or figure.get('kind')}" if figure else "")
            + (f"\n  QUESTION card (will not change): {quiz.get('question')}" if quiz.get("question") else "")
            + "".join(f"\n  SHOW: {step.get('show', '')}" for step in beat.get("steps") or [])
            + "\n  A LISTENER NOTICES:" + "".join(f"\n    - {p}" for p in problems))
    return "\n".join(blocks)


def polish(lesson: dict, llm: LLM | None, log=print, examples: list[dict] | None = None) -> dict:
    """One rewrite of the beats that do not sound spoken. A rewrite improves or stands aside.

    Each returned beat is tried on a copy of the lesson and kept only if that beat then
    has FEWER voice faults, still ends the way it did (a thinking pause follows a
    question), and the reviewer's own guards (``critic.apply_edits``: language, length,
    still about its picture and its question) let it through without adding a language
    or repetition finding. Whatever is kept is still reviewed afterwards: this runs
    before the reviewer, so a changed sentence is checked like any other.
    """
    measure = lambda which: findings(which) + copied(which, examples or [])  # noqa: E731
    before = measure(lesson)
    out = {"before": len(before), "after": len(before), "rewritten": [], "refused": []}
    if not before or llm is None:
        return out
    from . import critic  # noqa: PLC0415 - critic imports the writer, which imports this module

    try:
        raw = llm(_ask(lesson, before), POLISH_SYSTEM + skill.part("voice.md")
                  + ("\n\n" + for_writer(examples) if examples else "")) or {}
    except Exception as exc:  # noqa: BLE001 - polish is an improvement, never a requirement
        log(f"[voice] not polished: {type(exc).__name__}: {str(exc)[:120]}")
        return out
    by_id = {beat.get("id"): beat for _, _, beat, _ in _beats(lesson)}
    faults = Counter(f["beat"] for f in before)
    kept = []
    for edit in raw.get("edits") if isinstance(raw.get("edits"), list) else []:
        if not isinstance(edit, dict) or not str(edit.get("narration") or "").strip():
            continue
        bid = critic.beat_id(edit.get("beat"), by_id)
        if bid not in faults:
            continue                                        # only the beats that were asked about
        edit = {"beat": bid, "narration": str(edit["narration"])}
        old = by_id[bid].get("narration", "")
        trial = copy.deepcopy(lesson)
        critic.apply_edits(trial, {"edits": [edit]}, log=lambda *_: None)
        new = next(b.get("narration", "") for _, _, b, _ in _beats(trial) if b.get("id") == bid)
        gates = lambda which: sum(1 for f in critic.language_gate(which) + critic.repetition_gate(which) if f["beat"] == bid)  # noqa: E731
        why = ("the reviewer's guards refused it" if new == old else
               "it changes whether the beat ends with a question" if old.rstrip().endswith("?") != new.rstrip().endswith("?") else
               "it does not sound better by the same measure" if sum(1 for f in measure(trial) if f["beat"] == bid) >= faults[bid] else
               "it adds a language or repetition fault" if gates(trial) > gates(lesson) else "")
        if why:
            out["refused"].append({"beat": bid, "why": why})
            continue
        kept.append(edit)
    if kept:
        report = {"edits": kept}
        critic.apply_edits(lesson, report, log=log)
        out["rewritten"] = list(report.get("edits_applied") or [])
    out["after"] = len(measure(lesson))
    log(f"[voice] {out['before']} thing(s) a listener would notice in {len(faults)} beat(s); {len(out['rewritten'])} beat(s) "
        f"rewritten, {len(out['refused'])} rewrite(s) refused; {out['after']} left")
    return out



# ── how lecturers on the topic talk ──────────────────────────────────────────
# The owner, 2026-10-20: "The narration is very complex and cryptic, can you use youtube to get good narrations".
# The card already carried a lecturer's MANNER as a description ("teacher_talk"); a description of plain talk did
# not make the writer talk plainly. So the writer now READS two short passages of real lectures on its topic, chosen
# by code for how plainly they explain, and is told to take their manner and none of their words. The passages are
# the speakers' own: they go to the writer's prompt only (as they already go to the card's), never into a lesson
# file, and a beat that copies nine words in a row from one is rewritten (``copied``).

EXAMPLE_WORDS = 110


def plainness(text: str) -> float:
    """How plainly a passage explains, by the same counts as ``report``: joined, spoken to someone, rarely asking."""
    said = sentences(text)
    words = max(1, len(text.split()))
    joins = len(re.findall(r"\b(because|so|which means|that means|this means|then|but|if|and that's)\b", text, re.I))
    spoken_to = len(re.findall(r"\b(we|let's|us|our|you|your|I)\b", text, re.I))
    asks = sum(1 for s in said if s.endswith("?"))
    long_ = sum(1 for s in said if len(s.split()) > 30)
    return (2 * joins + spoken_to - 4 * asks - 3 * text.count(":") - 2 * long_) / words * 100


def _windows(text: str, size: int):
    said = sentences(text)
    for start in range(len(said)):
        taken, count = [], 0
        for sentence in said[start:]:
            taken.append(sentence)
            count += len(sentence.split())
            if count >= size:
                break
        if count >= size * 0.7:
            yield " ".join(taken)


def lecturer_examples(pack: dict | None, language: str = "", count: int = 2, size: int = EXAMPLE_WORDS) -> list[dict]:
    """Up to ``count`` passages of the pack's lectures, one per lecture, the plainest of each; [] when it has none.

    A lecture with YouTube's automatic captions has no full stops, so it cannot be read
    as sentences and is skipped. For an English lesson only English lectures count.
    """
    if not pack:
        return []
    lectures = {s["id"]: s for s in pack.get("sources") or [] if s.get("kind") == "lecture"
                and (language in ("hinglish", "hi-IN") or "Hindi" not in str(s.get("note", "")))}
    best: dict[str, tuple[float, str]] = {}
    for chunk in pack.get("chunks") or []:
        source = chunk.get("source")
        text = str(chunk.get("text") or "")
        if source not in lectures or len(sentences(text)) < len(text.split()) / 40:
            continue
        for window in _windows(text, size):
            score = plainness(window)
            if score > best.get(source, (-1e9, ""))[0]:
                best[source] = (score, window)
    ranked = sorted(best.items(), key=lambda kv: -kv[1][0])[:count]
    return [{"source": lectures[sid]["title"], "text": text} for sid, (_, text) in ranked]


def for_writer(examples: list[dict]) -> str:
    """The block the writer reads; '' with no examples, so its prompt is then what it was."""
    if not examples:
        return ""
    lines = ["HOW GOOD LECTURERS EXPLAIN THIS TOPIC: short passages from lectures on it, chosen because they explain "
             "plainly. Take their MANNER: full sentences joined by so, because, which means; spoken to 'you' and 'we'; "
             "one thought leading to the next; a question only now and then, answered straight away. Take NONE of their "
             "words, sentences, jokes or examples: what this lesson teaches and its example come from the brief and the card."]
    lines += [f"[{e['source']}] “{e['text']}”" for e in examples]
    return "\n".join(lines)


def copied(lesson: dict, examples: list[dict]) -> list[dict]:
    """A finding for every beat that carries ``library.COPIED_RUN`` words in a row from a lecturer's passage."""
    if not examples:
        return []
    from . import library  # noqa: PLC0415 - library is heavy and only needed here

    source_words = library.tokens_all(" ".join(e["text"] for e in examples))
    return [_finding(beat, f"it copies {library.COPIED_RUN} or more words in a row from a lecture it was shown",
                     "say the same thing in your own words: the lecture's manner, never its sentences")
            for _, _, beat, said in _beats(lesson) if any(library._copied(s, source_words) for s in said)]


def examples_for(brief: dict, pack: dict | None, log=print) -> list[dict]:
    """The lecturer passages for a lesson: from its teaching pack, else from lectures found for its topic now.

    Off with ``HARNESS_LECTURER_VOICE=0`` (tests set it: finding lectures reads the network).
    """
    if knobs.get("HARNESS_LECTURER_VOICE", "1") == "0":
        return []
    language = str(brief.get("language") or "")
    found = lecturer_examples(pack, language)
    if not found:
        from . import library  # noqa: PLC0415

        topic = str((pack or {}).get("topic") or brief.get("topic") or "").strip()
        klass = (pack or {}).get("klass") or brief.get("grade")
        if topic:
            found = lecturer_examples(library.lectures_pack(topic, klass if isinstance(klass, int) else None, language or "en-IN", log=log), language)
    log(f"[voice] lecturer passages for the writer: {len(found)}" + "".join(f"; {e['source'][:60]}" for e in found))
    return found


def notes_in(text: str) -> int:
    """Colons and the lesson's plan said aloud, in one narration: what makes it read like notes."""
    return sum(1 for s in sentences(text) if ":" in s and not re.search(r"\d:\d", s)) + len(_PLAN_TALK.findall(text))


#: A spoken sentence of fewer words than this, on average, is notes (lecturers on YouTube: 16 to 22 words).
SHORTEST_PLAIN = 9


def chopped(before: str, after: str) -> bool:
    """True when a rewrite of a plainly spoken beat keeps as many sentences but cuts them short: average length under
    ``SHORTEST_PLAIN`` and under 0.7 of what it was. Dropping a sentence, or cutting a repeat, is not chopping."""
    def length(sentence: str) -> int:             # a number spoken in words is one thing said, however many words
        words = [w.lower().strip(",.?!") for w in sentence.split()]
        return sum(1 for i, w in enumerate(words) if not (w in _NUMBER_WORDS and i and words[i - 1] in _NUMBER_WORDS))

    def average(text: str) -> float:
        said = sentences(text)
        return sum(length(s) for s in said) / max(1, len(said))
    return (average(before) >= SHORTEST_PLAIN and len(sentences(after)) >= len(sentences(before))
            and average(after) < SHORTEST_PLAIN and average(after) < 0.7 * average(before))


#: A spoken sentence of more words than this is a run-on: it is also one caption cue of three lines, and a learner
#: loses its start before it ends. The writer is told "12 to 22 words"; this is that ceiling as a check.
LONG_SENTENCE_WORDS = 22
_MIN_SIDE = 5              # a piece of a split sentence has at least this many words
#: Words a spoken clause can start with: a sentence cut in front of one keeps its joining word.
_CLAUSE_STARTS = set("aur lekin magar par toh isliye kyunki kyonki phir jabki jisse jiska jiski and but so because then "
                     "while which whereas yaani matlab".split())


def _clause_cuts(words: list[str]) -> list[int]:
    """Indexes where a long sentence may be cut: after a semicolon or a colon between words, or after a comma that
    is followed by a joining word; never so that a piece is left with fewer than ``_MIN_SIDE`` words."""
    cuts = []
    for i in range(_MIN_SIDE, len(words) - _MIN_SIDE + 1):
        end, nxt = words[i - 1], re.sub(r"[^\w]", "", words[i]).lower()
        if (end.endswith((";", ":")) and not re.search(r"\d:$", end)) or (end.endswith(",") and nxt in _CLAUSE_STARTS):
            cuts.append(i)
    return cuts


def _cut(words: list[str], limit: int) -> list[str]:
    if len(words) <= limit:
        return [" ".join(words)]
    cuts = _clause_cuts(words)
    if not cuts:
        return [" ".join(words)]
    i = min(cuts, key=lambda c: abs(c - len(words) / 2))
    left = " ".join(words[:i]).rstrip(",;:") + "."
    right = words[i:]
    right = [right[0][:1].upper() + right[0][1:]] + right[1:]
    return _cut(left.split(), limit) + _cut(right, limit)


def split_long(text: str, limit: int = LONG_SENTENCE_WORDS) -> str:
    """Narration with every sentence over ``limit`` words cut at its own clause boundaries (a semicolon, a colon, or a
    comma before aur / lekin / kyunki / but / because …); the words, their order and their joining words are kept.
    A sentence with no such place is left as it is. Text with nothing long in it comes back exactly as it was."""
    said = sentences(text)
    if not any(len(s.split()) > limit for s in said):
        return text
    return " ".join(piece for s in said for piece in _cut(s.split(), limit))


def asks_in(text: str) -> int:
    """How many of these sentences are questions."""
    return sum(1 for s in sentences(text) if s.endswith("?"))


def plan_talk_in(text: str) -> int:
    return len(_PLAN_TALK.findall(text))


def unnoted(text: str, keep: str = "") -> str:
    """Narration with its colons said as a pause (a comma), never between digits; a sentence also in ``keep`` (the
    words as they were) is left exactly as it was."""
    kept = set(sentences(keep))
    return " ".join(s if s in kept else re.sub(r"(?<!\d)\s*:\s+(?!\d)", ", ", s) for s in sentences(text))
