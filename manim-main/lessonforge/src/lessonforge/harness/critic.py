"""Script critic: a correctness and pedagogy pass BEFORE any speech is bought.

The first long lesson shipped six critical errors that only a human reviewer caught
(a central angle given as α+β instead of 180−α−β, right angles at the wrong corners,
an answer revealed before its thinking pause — docs/longform/pythagoras_case_study).
The docs ask for a critic that works on the text alone, keeps the beat count fixed and
runs before TTS, and for "claim lints" that check numbers with code rather than
with another opinion (docs/research/RESEARCH_QUESTIONS.md RQ-01/05, pipeline-roadmap #4).

Three layers, cheapest first:

1. **Arithmetic lint ($0).** Spoken arithmetic ("nine plus sixteen gives twenty-five",
   "six squared is thirty-six") is parsed and evaluated. A wrong sum is a finding
   no model can talk its way out of.
2. **Model review (one call).** The reviewer scores the lesson on the project's
   rubric dimensions (conceptual accuracy, visual truthfulness of what is shown
   against what is said, explanatory clarity, pedagogy), lists findings with a
   severity, and — the part code can verify — states every mathematical claim as a
   Python expression. Those expressions are evaluated here under a whitelist
   (arithmetic, comparisons, ``math.*``), so "the model says it is right" becomes
   "the expression is true".
3. **Text-only edits.** For findings it can fix, the reviewer returns replacement
   narration and steps for existing beats only. Beat ids, count and order never
   change, so timing contracts downstream are untouched; edited steps go back
   through the writer's anchoring discipline.

The result is a ``verification`` report on the lesson: scores, findings (with
``resolved`` flags), claims checked/passed, and whether anything critical is left.
Nothing here is acceptance — it is the cheapest filter in front of a human review.
"""
from __future__ import annotations

import ast
import math
import operator
import re
from fractions import Fraction
from typing import Any, Callable

from .. import knobs
from ..longform.contract import split_sentences
from . import coherence, rubric, storyflow, voice, writer

LLM = Callable[[str, str], Any]
RUBRIC = ("conceptual_accuracy", "visual_truthfulness", "explanatory_clarity", "pedagogy")
SEVERITIES = ("critical", "major", "minor")
# A different model FAMILY from the writer (Gemini): same-model self-verification
# accepts its own errors ~14% of the time; cross-family checking does not
# (docs/research/approaches/01_consistency_and_correctness.md). Cheap first.
CRITIC_MODELS_DEFAULT = "anthropic/claude-haiku-5.5,openai/gpt-5.4-nano,deepseek/deepseek-v4-pro"
_UNIVERSAL = re.compile(r"\b(always|never|every|all|any|no matter|whenever|cannot ever|must always)\b", re.I)


def critic_models() -> list[str]:
    import os
    raw = knobs.get("HARNESS_CRITIC_MODELS", CRITIC_MODELS_DEFAULT)
    return [m.strip() for m in raw.split(",") if m.strip()]


def default_llm() -> LLM | None:
    """The reviewer model chain (another family than the writer), or None without a key."""
    return writer.default_llm(models=critic_models(), temperature=0.2)


def universal_claims(lesson: dict) -> list[dict]:
    """Sentences that claim 'always/never/all': each needs its condition stated or a theorem behind it."""
    out = []
    for chapter in lesson["chapters"]:
        for beat in chapter["beats"]:
            for sentence in re.split(r"(?<=[.!?])\s+", beat["narration"]):
                if _UNIVERSAL.search(sentence):
                    out.append({"beat": beat["id"], "text": sentence.strip()})
    return out


_VOWELS = re.compile(r"[aeiouy]+")
# Per class band: (max mean words per sentence, Flesch–Kincaid grade above which a
# beat FAILS). From docs/research/approaches/05_* §Q2: narration is heard once, mostly
# by second-language listeners, so the bands sit 1–2 grades below the Common Core
# reading bands (6–8: target FK 5–7, fail >8, ≤14 words/sentence; 9–10: 7–9, >10, ≤17;
# 11–12: 9–11, >12, ≤20). Glossary terms are the lesson's own and are not penalised.
READABILITY_BANDS = {(1, 8): (14.0, 8.0), (9, 10): (17.0, 10.0), (11, 12): (20.0, 12.0)}


def _syllables(word: str) -> int:
    w = re.sub(r"[^a-z]", "", word.lower())
    if not w:
        return 0
    n = len(_VOWELS.findall(w))
    if w.endswith("e") and not w.endswith(("le", "ee")) and n > 1:
        n -= 1
    return max(1, n)


def _target_class(lesson: dict) -> int | None:
    brief = lesson.get("brief", {})
    if brief.get("grade"):
        return int(brief["grade"])
    m = re.search(r"\b(?:class|grade|std)\s*(\d{1,2})\b", str(brief.get("audience", "")), re.I)
    return int(m.group(1)) if m else None


def readability(lesson: dict) -> dict:
    """Is the WORDING within reach of the class? Flesch–Kincaid grade and sentence length per beat (English only)."""
    language = str(lesson.get("language", "en")).lower()
    target = _target_class(lesson)
    if not language.startswith("en"):
        return {"applies": False, "reason": f"no readability formula for {language}", "target_class": target}
    band = next((v for (lo, hi), v in READABILITY_BANDS.items() if target and lo <= target <= hi), None)
    beats_over, words_all, sents_all, syll_all, long_all = [], 0, 0, 0, 0
    for chapter in lesson["chapters"]:
        for beat in chapter["beats"]:
            sentences = [s for s in re.split(r"(?<=[.!?])\s+", beat["narration"]) if s.strip()]
            words = [w for s in sentences for w in s.split()]
            if not words:
                continue
            syll = sum(_syllables(w) for w in words)
            mean_len = len(words) / max(1, len(sentences))
            fk = 0.39 * mean_len + 11.8 * (syll / len(words)) - 15.59
            words_all += len(words)
            sents_all += len(sentences)
            syll_all += syll
            long_all += sum(1 for w in words if _syllables(w) >= 3)
            if band and (mean_len > band[0] or fk > band[1]):
                beats_over.append({"beat": beat["id"], "mean_sentence_words": round(mean_len, 1), "fk_grade": round(fk, 1)})
    if not words_all:
        return {"applies": False, "reason": "no narration", "target_class": target}
    mean_len = words_all / max(1, sents_all)
    return {
        "applies": True, "target_class": target, "band": band,
        "fk_grade": round(0.39 * mean_len + 11.8 * (syll_all / words_all) - 15.59, 1),
        "mean_sentence_words": round(mean_len, 1),
        "long_word_share": round(long_all / words_all, 3),
        "beats_over": beats_over,
    }


# Hindi words for numbers, operations and maths terms, as they appear in Latin-script Hinglish.
# ("ek" and "do" are left out: "ek seedhi" is just "a ladder", and "do" is also English.)
_HINDI_MATH_LATIN = (
    "teen|chaar|char|paanch|panch|chhe|chhah|cheh|saat|aath|nau|das|gyarah|barah|terah|chaudah|pandrah|solah|"
    "satrah|atharah|unnis|bees|pachees|tees|chalees|pachaas|sattar|assi|nabbe|sau|hazaar|hazar|aadha|aadhi|adha|"
    "dedh|dhai|sava|paune|tihai|chauthai|bata|bate|batte|guna|gunaa|jod|jodo|jodna|jodkar|jodte|ghata|ghatao|"
    "ghatana|ghatakar|bhag|barabar|varg|vargmool|ghan|kon|kona|tribhuj|samkon|karn|lamb|aadhar|bhinn|ansh|"
    "kshetrafal|chetrafal|paridhi|trijya|vyas|samikaran|pratishat|byaj|mooldhan|rekha|bindu|anupat")
_HINDI_MATH_DEVANAGARI = (
    "दो|तीन|चार|पाँच|पांच|छह|छः|सात|आठ|नौ|दस|ग्यारह|बारह|बीस|तीस|चालीस|पचास|सौ|हज़ार|हजार|आधा|आधी|डेढ़|ढाई|"
    "बटा|बटे|गुणा|गुना|जोड़|घटा|भाग|बराबर|वर्ग|वर्गमूल|कोण|त्रिभुज|समकोण|कर्ण|लंब|आधार|भिन्न|अंश|"
    "क्षेत्रफल|परिधि|त्रिज्या|व्यास|समीकरण|प्रतिशत|ब्याज|मूलधन")
# ("हर" is left out: it is the denominator, but far more often it is just "every" — it flagged
# two beats of a lesson about magnets.)
_HINDI_LATIN_RE = re.compile(rf"\b(?:{_HINDI_MATH_LATIN})\b", re.I)
_HINDI_DEVA_RE = re.compile(rf"(?<![\u0900-\u097F])(?:{_HINDI_MATH_DEVANAGARI})(?![\u0900-\u097F])")
_DIGITS_RE = re.compile(r"\d")


# Words that make a Latin-script sentence Hindi. Left out because they are English words
# too: to, me, do, is, so, hi, the (थे), main, use, ham, hue, mat, tab, jab, fir, ho.
_HINDI_MARKERS = set(
    "hai hain tha thi hoga hogi honge hota hoti hote hua hui ka ki ke ko mein se par tak aur ya yah yeh ye "
    "woh wo kya kyun kyon kyunki kaise kaisa kitna kitne kitni kab kahan kaun toh ab abhi bhi nahi nahin hum "
    "aap tum mera meri mere hamara hamari hamare aapka aapki aapke iska iski iske uska uski uske unka inka isse "
    "usse isliye lekin magar agar phir jaise waise aise wala wali wale liye saath sath sirf bas bahut "
    "thoda zyada kam har koi kuch sab dono ek chahiye sakta sakti sakte raha rahi rahe kar karo karna karte karta "
    "karti karenge kiya kiye kijiye dekho dekhiye dekhte socho sochiye chalo chaliye chalte banta banti bante banega "
    "banenge milta milti milte lete leta rakhna rakhte yahan wahan upar neeche pehle baad andar bahar "
    "bilkul haan ji theek sahi galat matlab yaani kyonki unhe inhe ise apna apni apne".split())
_SENTENCE = re.compile(r"(?<=[.!?।])\s+")


def english_only_sentences(text: str) -> list[str]:
    """Sentences of six or more words with no Hindi in them (Latin-script Hinglish or Devanagari)."""
    out = []
    for sentence in _SENTENCE.split(text):
        words = re.findall(r"[A-Za-z']+", sentence.lower())
        if len(words) >= 6 and not re.search(r"[\u0900-\u097F]", sentence) and not _HINDI_MARKERS.intersection(words):
            out.append(sentence.strip())
    return out


def language_gate(lesson: dict) -> list[dict]:
    """Hindi/Hinglish lessons: the conversation is Hindi, everything technical is English.

    A tester's Hinglish lesson said "teen bate char" for three by four and "char
    metre" for four metres. Numbers, fractions, operations and subject terms must be
    the English ones an English-medium class uses; this finds the Hindi ones so the
    revision round can replace them. Digits in narration are reported too: a Hindi
    voice reads "3/4" in Hindi.
    """
    requested = str(lesson.get("brief", {}).get("language") or lesson.get("language") or "").lower()
    if requested not in ("hinglish", "hi-in"):
        return []
    out = []
    for chapter in lesson["chapters"]:
        for beat in chapter["beats"]:
            text = beat["narration"]
            hits = [m.group(0) for m in _HINDI_LATIN_RE.finditer(text)] + [m.group(0) for m in _HINDI_DEVA_RE.finditer(text)]
            if _DIGITS_RE.search(text):
                hits.append("digits")
            if hits:
                shown = ", ".join(dict.fromkeys(hits))[:90]
                out.append({"severity": "major", "beat": beat["id"], "resolved": False,
                            "what": f"language: technical words in Hindi ({shown}) — numbers, fractions, operations and "
                                    "maths terms must be said in English",
                            "fix": "keep the Hindi conversation; say every number and technical term in English words "
                                   "(three by four, four metres, equals, right angle)"})
            # The other half of the same rule. A tester's Hinglish lesson (2026-10-08) had six
            # of nineteen beats spoken entirely in English; the reviewer called it minor and
            # left it. The conversation is Hindi: only the numbers and terms are English.
            english = english_only_sentences(text)
            sentences = [x for x in _SENTENCE.split(text) if len(x.split()) >= 6]
            if len(english) >= 2 and len(english) * 2 >= len(sentences):
                out.append({"severity": "major", "beat": beat["id"], "resolved": False,
                            "what": f"language: {len(english)} of {len(sentences)} sentences are entirely in English "
                                    f"(e.g. “{english[0][:70]}”) — the conversation must be Hindi",
                            "fix": "say each sentence in Hindi (…hai, …karte hain, isliye…), keeping only the numbers "
                                   "and the technical terms in English"})
    return out


def repetition_gate(lesson: dict, limit: int = 8) -> list[dict]:
    """Things said twice: a phrase an earlier chapter already spoke, the example's scene set again, a long
    number read out in full once more.

    A tester on 2026-10-08: "same things are coming again and again". ``writer.continuity``
    had counted 18 phrases repeated across chapters in that lesson and said so in a
    warning nobody acted on. These are findings, so the revision round removes them.
    """
    chapters = lesson["chapters"]
    n, seen, by_beat = 5, {}, {}
    numbers = writer._NUMBER_WORDS
    for index, chapter in enumerate(chapters):
        here = {}
        for beat in chapter["beats"]:
            # Matched on normalised words, shown in the words as written (normalising drops
            # Devanagari vowel signs, which reads as nonsense in a finding).
            pairs = [(writer._norm(w), w.strip(".,;:!?।\"'“”()")) for w in beat["narration"].replace("-", " ").split()]
            pairs = [(norm, shown) for norm, shown in pairs if norm]
            toks, last_end = [norm for norm, _ in pairs], -1
            for i in range(len(toks) - n + 1):
                gram = toks[i:i + n]
                if all(t in numbers or t.isdigit() for t in gram):
                    continue                              # a number is the number gate's business
                key = " ".join(gram)
                if key in seen:
                    by_beat.setdefault(beat["id"], {"chapter": seen[key], "phrases": [], "last": index == len(chapters) - 1})
                    phrases = by_beat[beat["id"]]["phrases"]
                    if phrases and last_end == i + n - 2:
                        phrases[-1] += " " + pairs[i + n - 1][1]     # overlapping 5-grams → one readable phrase
                    else:
                        phrases.append(" ".join(shown for _, shown in pairs[i:i + n]))
                    last_end = i + n - 1
                here.setdefault(key, chapter["id"])
        for key, cid in here.items():
            seen.setdefault(key, cid)
    out = []
    ranked = sorted(by_beat.items(), key=lambda kv: -sum(len(p.split()) for p in kv[1]["phrases"]))
    for beat_id_, hit in ranked:
        # One short phrase said again is usually the idea's own name ("equal rows and equal columns"),
        # not a restatement: the first version of this gate had it cut out of the definition of a
        # square number. A retold scene is long (seven words or more) or comes as several phrases.
        if len(hit["phrases"]) < 2 and len(hit["phrases"][0].split()) < 7:
            continue
        shown = "”, “".join(p[:60] for p in hit["phrases"][:3])
        out.append({"severity": "major", "beat": beat_id_, "resolved": False,
                    "what": f"repetition: says again what chapter {hit['chapter']} already said (“{shown}”)",
                    "fix": "say it once: cut the RETELLING, or point back in at most six words; never set the example's "
                           "scene again. Keep any words the beat's own definition, rule or question needs to stay true "
                           "and complete"})
        if len(out) >= limit:
            break
    # A long number spoken in full: once per chapter, and not more than three times in all.
    chapter_of = {b["id"]: c["id"] for c in chapters for b in c["beats"]}
    flagged = {f["beat"] for f in out}
    for phrase, beats in writer.long_number_mentions(lesson).items():
        said_in, total = {}, 0
        for beat_id_ in beats:
            total += 1
            said_in.setdefault(chapter_of[beat_id_], 0)
            said_in[chapter_of[beat_id_]] += 1
            again = said_in[chapter_of[beat_id_]] > 2 or total > 4      # twice in a chapter is ordinary speech
            if again and beat_id_ not in flagged and len(out) < limit + 4:
                flagged.add(beat_id_)
                out.append({"severity": "major", "beat": beat_id_, "resolved": False,
                            "what": f"repetition: “{phrase}” is spoken in full {len(beats)} times in this lesson",
                            "fix": "here say “this number” (in Hindi “yeh number”) — it stays on screen in digits"})
    return out


def _budget(lesson: dict) -> int:
    """The words a lesson was asked to be said in; 0 for a pasted script (as long as its author made it) or no length."""
    brief = lesson.get("brief") or {}
    if brief.get("mode") == "script":
        return 0
    try:
        minutes = int(brief.get("duration_minutes") or 0)
    except (TypeError, ValueError):
        return 0
    return writer.word_budget(max(3, minutes)) if minutes else 0


LENGTH_SLACK = 1.03           # a script this much over its budget is still "on" it
GATE_ROUNDS = 2               # rewrites the code gates get for themselves after the last review


def length_gate(lesson: dict) -> list[dict]:
    """A script over its length: the beats that carry the excess are asked to be said in fewer words.

    Every lesson measured came out over its budget, and each rewrite made it longer (350 words as written, 391 after
    its review, for "at most 343": Friction, 2026-10-12; 401 and 382 on the two after it). The prompt said "at most";
    nothing held it. The longest beats give the most, down toward the lesson's mean beat, never more than four tenths
    of a beat. Each finding carries ``at_most``: the reviser is told that number and ``apply_edits`` holds it.
    """
    budget = _budget(lesson)
    beats = [b for c in lesson.get("chapters") or [] for b in c.get("beats") or []]
    total = sum(len(str(b.get("narration") or "").split()) for b in beats)
    over = total - round(budget * LENGTH_SLACK)
    if not budget or over <= 0:
        return []
    mean, out = max(22, budget // max(1, len(beats))), []
    for beat in sorted(beats, key=lambda b: -len(str(b.get("narration") or "").split())):
        words = len(str(beat.get("narration") or "").split())
        cut = min(over, max(0, words - mean), round(words * 0.4))
        if cut < 4:
            continue
        out.append({"severity": "major", "beat": beat["id"], "resolved": False, "at_most": words - cut,
                    "what": f"length: the script is {total} words for a lesson of at most {budget}; this beat is {words}",
                    "fix": f"say the same in at most {words - cut} words: cut restatement and filler; keep every number and term, "
                           "the question the beat ends on, and the sentence that answers the question before it"})
        over -= cut
        if over <= 0:
            break
    return out


#: Settings the owner's bar keeps out of an example ("simple examples, no cricket or festival stories", 2026-10-08;
#: the intake once suggested a cricket ground and a lesson on gradient descent got a cricket squad's fatigue sensors).
#: Whole words only; a new word goes in with a test on both sides ("cricket" the insect is a risk taken knowingly).
_SETTINGS = re.compile(r"\b(cricket|ipl|wicket|stadium|festival|diwali|deepavali|holi|mela|bollywood|wedding|shaadi|barat|baraat)\b", re.I)


def setting_gate(lesson: dict) -> list[dict]:
    """A story setting the owner's bar excludes, in the words or in a line on screen: the example is the thing itself or
    one plain object. (The atom lesson of 2026-10-12 opened "think of an atom as big as a cricket stadium".)"""
    out = []
    for chapter in lesson.get("chapters") or []:
        for beat in chapter.get("beats") or []:
            text = " ".join([str(beat.get("narration") or "")] + [str(step.get("show") or "") for step in beat.get("steps") or []])
            found = list(dict.fromkeys(m.group(0).lower() for m in _SETTINGS.finditer(text)))
            if found:
                out.append({"severity": "major", "beat": beat["id"], "resolved": False,
                            "what": f"example: a story setting ({', '.join(found)}) — examples are the thing itself or one plain object",
                            "fix": "say the same comparison with a plain object or a plain size (a room, a football field, a dot on "
                                   "a page), with no sport, festival or film in it"})
    return out


def figure_gate(lesson: dict) -> list[dict]:
    """A figure whose numbers and labels disagree: reported, and drawn from the labels (what is said)."""
    out = []
    for chapter in lesson["chapters"]:
        for beat in chapter["beats"]:
            for issue in beat.get("figure_issues") or []:
                fixable = "drawn from the labels" in issue or "but drawn" in issue
                out.append({"severity": "minor" if fixable else "major", "beat": beat["id"], "resolved": fixable,
                            "what": f"figure: {issue}",
                            "fix": "the drawing follows the labelled numbers" if fixable else
                                   "the labelled sides cannot all be right; correct the script"})
    return out


def pause_gate(lesson: dict) -> list[dict]:
    """A thinking pause must follow a question. Deterministic; the answer-before-pause check is the critic's."""
    out = []
    for chapter in lesson["chapters"]:
        for beat in chapter["beats"]:
            if beat.get("thinking_pause_seconds", 0) and not beat["narration"].rstrip().endswith(("?", "?\"", "?”")):
                out.append({"severity": "minor", "beat": beat["id"], "resolved": False,
                            "what": f"a {beat['thinking_pause_seconds']:g}s thinking pause follows a statement, not a question",
                            "fix": "end the beat with the question the learner should think about, or drop the pause"})
    return out

SYSTEM = """You are a meticulous subject reviewer for an animated maths/science lesson for school students.
You check what is SAID (narration), what is SHOWN (steps: "show" text or LaTeX that appears while the
"say" phrase is spoken) and whether the two agree. Return ONLY JSON.

Score each rubric dimension 0-4 (4 = nothing to fix):
  conceptual_accuracy   every statement true, with its conditions (no "always" where a condition is needed)
  visual_truthfulness   each "show" matches what is being said at that moment; no stale or misleading screen text
  explanatory_clarity   one idea at a time; terms introduced before use; the opening question is answered;
                        nothing is said twice (a later beat that re-explains or re-describes is a finding)
  pedagogy              the thinking pauses sit AFTER a real question and BEFORE its answer; the stated
                        misconception is actually confronted; the EXAMPLE is simpler than the idea it carries;
                        the METHOD the goal needs is actually carried out on screen

Three things to check on every lesson, each a "major" finding when it fails:
  THE EXAMPLE. List its parts to yourself and what each stands for in the idea. A part that stands for nothing
    (a festival, a shop, an owner, a sport, a reason for doing it) is clutter: name it and say to cut it. An
    example with more moving parts than the idea, or one that itself needs explaining, is the wrong example:
    say what simpler one would do (often the thing itself with small numbers).
  THE METHOD. Read the goal. Is every step the learner must be able to do afterwards carried out on screen at
    least once, in the order they will do it? An answer reached by a route the learner cannot take (guessed, or
    already known) does not count. When the goal is a test or a decision, is there a case that FAILS?
  THE NUMBERS. Does the lesson start from a case small enough to count on screen before the big numbers?

Findings: list every real problem with "severity" critical | major | minor, the "beat" id, "what" is wrong
and, if a text-only change fixes it, the "fix" as a short instruction. Do not invent problems to look thorough.

Claims: every arithmetic or mathematical claim the narration or screen makes, each as a Python boolean
expression using only numbers, + - * / ** ( ), comparisons and math.sqrt/math.sin/math.cos/math.pi etc.
Example: "nine plus sixteen gives twenty-five" -> "9 + 16 == 25"; "the ladder is five metres" (from 3, 4) ->
"math.isclose(math.sqrt(3**2 + 4**2), 5)". Write what the lesson CLAIMS, even if you think it is wrong.

Edits: for each beat you can repair with words alone, the full replacement "narration" (same length, same
voice, same language; it is SPOKEN, so every number is written as English words and there are no symbols: "one
thousand eight hundred equals two into nine hundred", never "1800 = 2 x 900") and, only if the screen must change,
the full replacement "steps" list in the writer's format (one line of working per "math" step, never a chain)
({"say","show","kind","highlight"}; "say" copied exactly from the new narration). Never add or remove beats."""

_NUM = {w: i for i, w in enumerate(("zero", "one", "two", "three", "four", "five", "six", "seven", "eight",
                                    "nine", "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen",
                                    "sixteen", "seventeen", "eighteen", "nineteen"))}
_NUM.update({"twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80,
             "ninety": 90})
_SCALE = {"hundred": 100, "thousand": 1000}


def _number(text: str) -> float | None:
    """'one hundred and forty-four' / '144' / 'twenty-five' → number, else None."""
    t = text.lower().replace("-", " ").replace(",", "")
    if re.fullmatch(r"\d+(\.\d+)?", t.strip()):
        return float(t)
    total, current, seen = 0, 0, False
    for w in t.split():
        if w in ("and", "a"):
            continue
        if w in _NUM:
            current += _NUM[w]
            seen = True
        elif w in _SCALE:
            current = max(current, 1) * _SCALE[w]
            total += current
            current = 0
            seen = True
        else:
            return None
    return float(total + current) if seen else None


_NUMBER_RE = r"((?:\d+(?:\.\d+)?)|(?:(?:zero|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety|hundred|thousand|and)(?:[ -](?:zero|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety|hundred|thousand|and))*))"
_EQUALS = r"(?:equals|equal to|is equal to|gives|gives us|makes|is|are|comes to|total|totals|which is|we get)"
_BINARY = re.compile(rf"\b{_NUMBER_RE}\s+(plus|minus|times|multiplied by|divided by|into)\s+{_NUMBER_RE}\s+{_EQUALS}\s+{_NUMBER_RE}\b", re.I)
_SQUARE = re.compile(rf"\b{_NUMBER_RE}\s+squared\s+{_EQUALS}\s+{_NUMBER_RE}\b", re.I)
_ROOT = re.compile(rf"\bsquare root of\s+{_NUMBER_RE}\s+{_EQUALS}\s+{_NUMBER_RE}\b", re.I)
_OPS = {"plus": lambda a, b: a + b, "minus": lambda a, b: a - b, "times": lambda a, b: a * b,
        "multiplied by": lambda a, b: a * b, "divided by": lambda a, b: a / b if b else float("nan"),
        "into": lambda a, b: a * b}


_OPERATOR_BEFORE = re.compile(r"(?:\b(?:over|by|times|plus|minus|into|of|and|upon|divided|multiplied|squared|root)|[-+*/×÷=])\s*$", re.I)


def _standalone(text: str, match) -> bool:
    """False when the match is the tail of a longer expression.

    "twenty-two over seven times fourteen gives forty-four" contains "seven times
    fourteen gives forty-four"; read alone that is a wrong product, read whole it is a
    correct sum. A lint that cries wolf gets ignored, so such tails are not judged.
    """
    return not _OPERATOR_BEFORE.search(text[max(0, match.start() - 24):match.start()])


def arithmetic_lint(lesson: dict) -> list[dict]:
    """Spoken arithmetic, evaluated. Each result: {beat, text, expected, said, ok}."""
    out = []
    for chapter in lesson["chapters"]:
        for beat in chapter["beats"]:
            text = beat["narration"]
            for m in _BINARY.finditer(text):
                if not _standalone(text, m):
                    continue
                a, op, b, c = _number(m.group(1)), m.group(2).lower(), _number(m.group(3)), _number(m.group(4))
                if None in (a, b, c):
                    continue
                expected = _OPS[op](a, b)
                out.append({"beat": beat["id"], "text": re.sub(r"^and\s+", "", m.group(0), flags=re.I), "expected": expected, "said": c,
                            "ok": math.isclose(expected, c, rel_tol=1e-6, abs_tol=1e-9)})
            for m in _SQUARE.finditer(text):
                if not _standalone(text, m):
                    continue
                a, c = _number(m.group(1)), _number(m.group(2))
                if None in (a, c):
                    continue
                out.append({"beat": beat["id"], "text": re.sub(r"^and\s+", "", m.group(0), flags=re.I), "expected": a * a, "said": c,
                            "ok": math.isclose(a * a, c, rel_tol=1e-6)})
            for m in _ROOT.finditer(text):
                a, c = _number(m.group(1)), _number(m.group(2))
                if None in (a, c):
                    continue
                out.append({"beat": beat["id"], "text": re.sub(r"^and\s+", "", m.group(0), flags=re.I), "expected": math.sqrt(a), "said": c,
                            "ok": math.isclose(math.sqrt(a), c, rel_tol=1e-3)})
    return out


_ALLOWED_NODES = (ast.Expression, ast.BinOp, ast.UnaryOp, ast.Compare, ast.BoolOp, ast.Constant, ast.Call,
                  ast.Attribute, ast.Name, ast.Load, ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow, ast.Mod,
                  ast.FloorDiv, ast.USub, ast.UAdd, ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE,
                  ast.And, ast.Or, ast.Not, ast.Tuple)


def check_claim(expression: str) -> bool | None:
    """Evaluate a model-written claim under a whitelist. None = could not be evaluated."""
    try:
        tree = ast.parse(expression.strip(), mode="eval")
    except SyntaxError:
        return None
    for node in ast.walk(tree):
        if not isinstance(node, _ALLOWED_NODES):
            return None
        if isinstance(node, ast.Name) and node.id not in ("math", "abs", "round", "min", "max", "True", "False"):
            return None
        if isinstance(node, ast.Attribute) and not (isinstance(node.value, ast.Name) and node.value.id == "math"):
            return None
        if isinstance(node, ast.Call):
            fn = node.func
            ok = (isinstance(fn, ast.Attribute) and isinstance(fn.value, ast.Name) and fn.value.id == "math") or \
                 (isinstance(fn, ast.Name) and fn.id in ("abs", "round", "min", "max"))
            if not ok:
                return None
    try:
        return bool(_exact(tree.body))
    except Exception:  # noqa: BLE001 - a claim that cannot be evaluated is reported, not raised
        return None


_BIN = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv,
        ast.FloorDiv: operator.floordiv, ast.Mod: operator.mod}
_CMP = {ast.Lt: operator.lt, ast.LtE: operator.le, ast.Gt: operator.gt, ast.GtE: operator.ge}


def _exact(node):
    """A claim's value with numbers as exact fractions, so "2/3 == 1 - 1/3" is true.

    It was evaluated in floats, where 2/3 is 0.6666666666666666 and 1 - 1/3 is 0.6666666666666667: four true claims of
    a Monty Hall lesson (2026-10-19) were reported as failed checks, and the reviser was asked to rewrite them. A value
    that only a float can hold (``math.sqrt(2)``, ``math.pi``) is compared within a rounding error.
    """
    if isinstance(node, ast.Constant):
        if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
            return node.value
        return Fraction(str(node.value)) if isinstance(node.value, float) else Fraction(node.value)
    if isinstance(node, ast.Name):
        return {"True": True, "False": False}[node.id]
    if isinstance(node, ast.Attribute):
        return getattr(math, node.attr)
    if isinstance(node, ast.Tuple):
        return tuple(_exact(e) for e in node.elts)
    if isinstance(node, ast.UnaryOp):
        value = _exact(node.operand)
        return {ast.USub: operator.neg, ast.UAdd: operator.pos, ast.Not: operator.not_}[type(node.op)](value)
    if isinstance(node, ast.BinOp):
        a, b = _exact(node.left), _exact(node.right)
        if isinstance(node.op, ast.Pow):
            if isinstance(b, Fraction) and b.denominator == 1 and abs(b) <= 64:
                return a ** int(b)
            return float(a) ** float(b)
        return _BIN[type(node.op)](a, b)
    if isinstance(node, ast.BoolOp):
        values = [_exact(v) for v in node.values]
        return all(values) if isinstance(node.op, ast.And) else any(values)
    if isinstance(node, ast.Call):
        fn = _exact(node.func) if isinstance(node.func, ast.Attribute) else {"abs": abs, "round": round,
                                                                           "min": min, "max": max}[node.func.id]
        args = [_exact(a) for a in node.args]
        if fn in (abs, min, max):
            return fn(*args)
        if fn is round:
            return Fraction(round(*args))
        return fn(*[float(a) if isinstance(a, Fraction) else a for a in args])
    if isinstance(node, ast.Compare):
        left = _exact(node.left)
        for op, right_node in zip(node.ops, node.comparators):
            right = _exact(right_node)
            if isinstance(op, (ast.Eq, ast.NotEq)):
                if isinstance(left, Fraction) and isinstance(right, Fraction):
                    same = left == right
                elif isinstance(left, (Fraction, float, int)) and isinstance(right, (Fraction, float, int)):
                    same = math.isclose(float(left), float(right), rel_tol=1e-9, abs_tol=1e-12)
                else:
                    same = left == right
                if same != isinstance(op, ast.Eq):
                    return False
            elif not _CMP[type(op)](left, right):
                return False
            left = right
        return True
    raise ValueError(f"not allowed: {type(node).__name__}")


def beat_id(value, known) -> str:
    """'beat-05', 'beat 5', 5, '05' → the lesson's id for that beat ('05'), or the text unchanged.

    A reviewer that wrote "beat-05" had every one of its edits silently dropped on the
    first browser-driven run; ids are normalised wherever a model names a beat.
    """
    text = str(value if value is not None else "").strip()
    if text in known:
        return text
    digits = re.search(r"\d+", text)
    if digits:
        for candidate in (digits.group().zfill(2), digits.group(), digits.group().lstrip("0") or "0"):
            if candidate in known:
                return candidate
    return text


def _language_line(lesson: dict) -> str:
    requested = str(lesson.get("brief", {}).get("language") or lesson.get("language") or "en-IN").lower()
    if requested == "hinglish":
        return ("Hinglish in Latin letters — every sentence is a HINDI sentence (…hai, …karte hain, isliye…) carrying "
                "English numbers and technical terms; never a plain English sentence")
    if requested == "hi-in":
        return "Hindi in Devanagari for the conversation; numbers and technical terms in English, in Latin letters"
    return {"en-in": "Indian English", "te-in": "Telugu, technical terms in English",
            "ta-in": "Tamil, technical terms in English"}.get(requested, requested)


def _lesson_text(lesson: dict) -> str:
    lines = [f"TITLE: {lesson['title']}", f"THESIS: {lesson.get('thesis', '')}", f"RUNNING EXAMPLE: {lesson.get('anchor', '')}",
             f"AUDIENCE: {lesson.get('brief', {}).get('audience', '')}",
             f"LANGUAGE OF THE NARRATION (any text you write for it must be in exactly this): {_language_line(lesson)}"]
    if lesson.get("framework") == "script":
        # Pasted by its author (harness/scripted.py): there is no brief to hold it to. The first real
        # run's reviewer reported "no stated GOAL and no METHOD" as a finding against the script.
        lines.append("THIS SCRIPT WAS WRITTEN BY ITS AUTHOR, who declared no goal, method or misconception. Judge what it "
                     "says and shows; do not report that a goal, a method or a misconception is missing.")
    else:
        lines += [f"GOAL — after watching, the learner can: {lesson.get('brief', {}).get('goal', '')}",
                  f"METHOD THE WRITER PROMISED TO SHOW: {lesson.get('method') or '(none listed)'}",
                  f"KNOWN MISCONCEPTION TO CONFRONT: {lesson.get('brief', {}).get('misconception', '') or '(none given)'}"]
    for c in lesson["chapters"]:
        lines.append(f"\n## Chapter {c['id']}: {c['title']} — {c.get('learning_goal', '')}")
        for b in c["beats"]:
            lines.append(f"[beat {b['id']}] pause={b.get('thinking_pause_seconds', 0)}s\n  SAY: {b['narration']}")
            for s in b.get("steps", []):
                lines.append(f"  SHOW ({s['kind']}{', highlight' if s.get('highlight') else ''}) at «{s['say']}»: {s['show']}")
    return "\n".join(lines)


def teaching_questions() -> list[str]:
    """The reviewer's yes/no questions about TEACHING, from the skill (``skills/teaching-script/checks.md``), in order.

    Each asks whether something that can be pointed at is there (a question before the rule, the
    why said with "because", the card's mistake met), which a reviewer answers reliably; none asks
    whether the lesson is "engaging", which it does not (docs/research/approaches/04, evaluation).
    """
    from . import skill
    out: list[str] = []
    numbered = False
    for line in skill.for_reviewer().splitlines():
        item = re.match(r"^(\d{1,2})\.\s+(.*)$", line)
        if item:
            out.append(item.group(2).strip())
            numbered = True
        elif numbered and line[:1] in (" ", "\t") and line.strip():
            out[-1] += " " + line.strip()          # a question that runs onto the next line
        else:
            numbered = False
    return out


def _card_block(lesson: dict, questions: list[str]) -> str:
    """The lesson's teaching card and the questions to answer about it, for the reviewer. '' without a card."""
    card = lesson.get("card") if isinstance(lesson.get("card"), dict) else None
    if not card or not questions:
        return ""

    def said(key: str, field: str = "text") -> str:
        value = card.get(key)
        return re.sub(r"\s+", " ", str((value.get(field) if isinstance(value, dict) else value) or "")).strip()

    opening = card.get("opening_question") if isinstance(card.get("opening_question"), dict) else {}
    task = card.get("try_it") if isinstance(card.get("try_it"), dict) else {}
    mistakes = [m for m in (card.get("mistakes") or []) if isinstance(m, dict) and m.get("mistake")]
    lines = ["", "", "THE TEACHING CARD this lesson was written from (what it must deliver):",
             f"  BIG IDEA: {said('big_idea')}", f"  THE WHY: {said('the_why')}", f"  THE ONE PICTURE: {said('picture')}",
             f"  OPENING QUESTION: {opening.get('question', '')} (answered later as: {opening.get('answer', '')})",
             "  WHERE LEARNERS GO WRONG: " + ("; ".join(f"{m['mistake']} (it fails because: {m.get('why_it_fails', '')})"
                                                         for m in mistakes[:5]) or "(none on the card)"),
             f"  TRY IT YOURSELF: {task.get('title', '')}. Guess first: {task.get('predict', '')} Question after: "
             f"{task.get('question', '')}",
             "",
             "TEACHING CHECKS: answer every one in \"teaching\". \"pass\": true means the lesson is fine on that point "
             "(where a question asks whether a FAULT is present, pass means the fault is absent). For a pass give the "
             "beat id that shows it and quote a few of its words as \"evidence\". For a fail give the beat where it "
             "should happen and a \"fix\" in words alone. You are shown the card, not the source passages: judge a "
             "question about the sources against the card."]
    return "\n".join(lines + [f"  {n}. {q}" for n, q in enumerate(questions, 1)])


CHECK_AGAIN_SYSTEM = """You turn ONE sentence from a school lesson into a check a computer can run.
Write one Python expression, using numbers, + - * / ** and comparisons only (fractions as a/b), that is True exactly
when the sentence is true. Work out first, in words, what quantity the sentence is about and what it says that
quantity is. Return ONLY JSON: {"reading": "what the sentence says, in at most twenty words", "python": "..."}"""
#: At most this many failed claims are checked a second time in one review.
CHECK_AGAIN = 6


def _computes(expression: str) -> bool:
    """Whether a check works something out (``2/2 == 1``) rather than stating a number equals itself (``360 == 360``,
    which a second check of the Moon lesson returned: a check that cannot be false proves nothing)."""
    try:
        tree = ast.parse(expression.strip(), mode="eval")
    except SyntaxError:
        return False
    return any(isinstance(node, (ast.BinOp, ast.UnaryOp, ast.Call)) for node in ast.walk(tree))


def _check_again(claims: list[dict], llm: LLM, log=print) -> None:
    """A claim the reviewer's own code calls false is checked once more, alone, by a fresh expression.

    The Moon lesson (2026-10-19): "A Moon that never turned would show every side over one orbit" (true) was checked
    as ``0 - 1 == 1`` and "with two spins per trip, every side comes round once" as ``2 - 1 == 2``; both were reported
    as failed claims and the lesson failed its QA on its correctness. The sentence was right, the reviewer's check was
    wrong. When the second expression says true, the two checks disagree and the claim is NOT counted as failed
    (``result`` None: unverifiable, with both expressions kept); when it says false too, it stays failed. A second
    answer that cannot be read leaves the first verdict as it was."""
    for claim in [c for c in claims if c["result"] is False][:CHECK_AGAIN]:
        try:
            answer = llm(f"THE SENTENCE: {claim['claim'][:400]}", CHECK_AGAIN_SYSTEM) or {}
        except Exception as exc:  # noqa: BLE001 - the first verdict stands
            log(f"[critic] claim in beat {claim['beat']} not checked again ({type(exc).__name__})")
            continue
        again = str(answer.get("python") or "") if isinstance(answer, dict) else ""
        verdict = check_claim(again) if again and _computes(again) else None
        if verdict is None:
            continue
        claim["python_again"] = again
        if verdict:
            claim["result"] = None
            log(f"[critic] claim in beat {claim['beat']} was checked as {claim['python'][:60]!r} (false) and again as "
                f"{again[:60]!r} (true): the checks disagree, so it is not counted as failed")


def review(lesson: dict, llm: LLM, log=print) -> dict:
    """One reviewer call + code checks. Returns the verification report (lesson untouched)."""
    lint = arithmetic_lint(lesson)
    for item in lint:
        if not item["ok"]:
            log(f"[critic] arithmetic: beat {item['beat']} says “{item['text']}” but it is {item['expected']:g}")
    universals = universal_claims(lesson)
    extra = ""
    if universals:
        extra = ("\n\nUNIVERSAL CLAIMS to check — each is only correct if its condition is stated nearby or it is a "
                 "named theorem:\n" + "\n".join(f"  [beat {u['beat']}] {u['text']}" for u in universals[:12]))
    # A lesson written from a teaching card is also asked the skill's teaching questions about it. A lesson
    # without a card gets the prompt it always got, to the byte.
    questions = teaching_questions() if lesson.get("card") else []
    card_block = _card_block(lesson, questions)
    teaching_shape = ('\"teaching\": [{\"check\": 1, \"pass\": true, \"beat\": \"id\", \"evidence\": str, \"fix\": str}], '
                      if card_block else "")
    prompt = (f"{_lesson_text(lesson)}{extra}{card_block}\n\nReturn JSON: {{\"scores\": {{\"conceptual_accuracy\": 0-4, "
              f"\"visual_truthfulness\": 0-4, \"explanatory_clarity\": 0-4, \"pedagogy\": 0-4}}, "
              f"\"findings\": [{{\"severity\": \"critical|major|minor\", \"beat\": \"id\", \"what\": str, \"fix\": str}}], "
              f"\"claims\": [{{\"beat\": \"id\", \"claim\": str, \"python\": str}}], "
              f"\"edits\": [{{\"beat\": \"id\", \"narration\": str, \"steps\": [...] or null}}], "
              f"{teaching_shape}\"summary\": str}}")
    raw = llm(prompt, SYSTEM) or {}
    known = {b["id"] for c in lesson["chapters"] for b in c["beats"]}
    scores = {k: _score((raw.get("scores") or {}).get(k)) for k in RUBRIC}
    findings = [{"severity": f.get("severity") if f.get("severity") in SEVERITIES else "minor",
                 "beat": beat_id(f.get("beat"), known), "what": str(f.get("what", "")), "fix": str(f.get("fix", "") or "")}
                for f in (raw.get("findings") or []) if isinstance(f, dict)]
    claims = []
    for c in raw.get("claims") or []:
        if not isinstance(c, dict):
            continue
        verdict = check_claim(str(c.get("python", "")))
        claims.append({"beat": beat_id(c.get("beat"), known), "claim": str(c.get("claim", "")),
                       "python": str(c.get("python", "")), "result": verdict})
    _check_again(claims, llm, log)
    for item in lint:
        claims.append({"beat": item["beat"], "claim": item["text"], "python": "(arithmetic lint)", "result": item["ok"]})
    edits = [{**e, "beat": beat_id(e.get("beat"), known)} for e in (raw.get("edits") or [])
             if isinstance(e, dict) and e.get("beat") and e.get("narration")]
    findings += pause_gate(lesson)
    findings += figure_gate(lesson)
    findings += language_gate(lesson)
    findings += repetition_gate(lesson)
    findings += setting_gate(lesson)
    findings += length_gate(lesson)
    # Whether it holds together as one explanation (coherence.py): chapters that restart or jump, terms used before
    # they are explained, an opening question never answered. Off unless HARNESS_COHERENCE=1: a review without it is
    # the review it always was.
    if coherence.enabled():
        findings += coherence.findings(lesson, llm, log=log)
    # How it TEACHES, by a weighted rubric scored with quotes (rubric.py). Off unless HARNESS_TEACHING_RUBRIC=1.
    teach = rubric.assess(lesson, llm, _lesson_text(lesson), log=log) if rubric.enabled() else None
    if teach:
        findings += teach["findings"]
    # How the script SOUNDS (voice.py), in the text that is being reviewed. All minor: the writer's own
    # polish pass is what acts on them; here they say what is still open after it.
    findings += voice.findings(lesson)
    # How the STORY holds together, by code (storyflow.py, measured on YouTube explainers): the plan said aloud,
    # sentences that jump. Major, so they are rewritten. Off unless HARNESS_STORY_GATE=1.
    if storyflow.enabled():
        findings += storyflow.story_gate(lesson)
    teaching = None
    if card_block:
        rows: dict[int, dict] = {}
        for item in raw.get("teaching") or []:
            try:
                number = int(item.get("check"))
            except (AttributeError, TypeError, ValueError):
                continue
            if 1 <= number <= len(questions) and number not in rows:
                rows[number] = {"check": number, "question": questions[number - 1], "pass": bool(item.get("pass")),
                                "beat": beat_id(item.get("beat"), known) if item.get("beat") else "",
                                "evidence": str(item.get("evidence") or "")[:200], "fix": str(item.get("fix") or "")[:240]}
        checks = [rows[n] for n in sorted(rows)]
        teaching = {"checks": checks, "passed": sum(c["pass"] for c in checks), "of": len(questions),
                    "unanswered": len(questions) - len(checks)}
        # REPORTED, not enforced: a failed check is a minor finding, so it starts no rewrite and does not make
        # the lesson "needs review". What these checks would break when obeyed has not been read on real
        # scripts yet (the repetition gate once cut a definition in half that way).
        findings += [{"severity": "minor", "beat": c["beat"], "resolved": False, "fix": c["fix"],
                      "what": f"teaching check {c['check']} not met: {c['question'][:110]}"} for c in checks if not c["pass"]]
        log(f"[critic] teaching checks: {teaching['passed']} of {teaching['of']} met"
            + (f" ({teaching['unanswered']} not answered)" if teaching["unanswered"] else ""))
    read = readability(lesson)
    for over in read.get("beats_over", [])[:6]:
        findings.append({"severity": "minor", "beat": over["beat"], "resolved": False,
                         "what": f"wording above class {read['target_class']}: {over['mean_sentence_words']} words per "
                                 f"sentence, Flesch–Kincaid grade {over['fk_grade']}",
                         "fix": "split only the longest sentence and keep each reason joined to its result; everyday words, keep the technical terms"})
    report = {
        "scores": scores,
        "findings": findings,
        "readability": read,
        "universal_claims": universals,
        "claims": claims,
        "claims_checked": sum(1 for c in claims if c["result"] is not None),
        "claims_failed": [c for c in claims if c["result"] is False],
        "claims_unverifiable": sum(1 for c in claims if c["result"] is None),
        "edits": edits,
        "summary": str(raw.get("summary", "")),
    }
    if teaching is not None:
        report["teaching"] = teaching
    if teach is not None:
        report["rubric"] = {k: v for k, v in teach.items() if k != "findings"}
    log(f"[critic] scores {scores}; {len(findings)} finding(s) "
        f"({sum(1 for f in findings if f['severity'] == 'critical')} critical); "
        f"{report['claims_checked']} claims checked, {len(report['claims_failed'])} failed; {len(edits)} edit(s) offered")
    return report


def _score(value) -> int | None:
    try:
        return max(0, min(4, int(round(float(value)))))
    except (TypeError, ValueError):
        return None


_SUBJECT_WORD = re.compile(r"[a-z]{3,}")
_SUBJECT_STOP = frozenset("""the and with while then that this from into onto each one two three four five six its their
both are for has have was all not when where which what how why your you will can does""".split())


def _subject_words(text: str) -> set[str]:
    words = (w[:-1] if w.endswith("s") and len(w) > 3 else w for w in _SUBJECT_WORD.findall(str(text).lower()))
    return set(words) - _SUBJECT_STOP


def leaves_its_picture(beat: dict, narration: str) -> bool:
    """True when a rewrite stops talking about what the beat SHOWS and ASKS.

    A beat's animation and its question card are made from the first script and a text
    rewrite cannot change them. Hindi or English, the things in a picture are named in
    English ("bus", "passenger", "friction"), so shared words are a fair test: the old
    words named at least three of them and the new words keep fewer than half.
    """
    figure, quiz = beat.get("figure") or {}, beat.get("quiz") or {}
    about = _subject_words(f"{figure.get('describe', '') if figure.get('kind') == 'scene' else ''} {quiz.get('question', '')}")
    before, after = len(about & _subject_words(beat.get("narration", ""))), len(about & _subject_words(narration))
    return before >= 3 and after < before / 2


def asked_before(lesson: dict, beat: str) -> dict | None:
    """The question card the beat BEFORE ``beat`` stops on, or None (no card there, or its right option is unknown)."""
    order = [b for c in lesson["chapters"] for b in c["beats"]]
    for n, here in enumerate(order):
        if here["id"] == beat and n:
            quiz = order[n - 1].get("quiz") or {}
            options, right = quiz.get("options") or [], quiz.get("answer_index")
            if quiz.get("question") and isinstance(right, int) and not isinstance(right, bool) and 0 <= right < len(options):
                return quiz
    return None


_ANSWER_SMALL = frozenset("the a an of to in is are and or it its by on at for with than".split())


def says_answer(sentence: str, quiz: dict) -> bool:
    """Whether ``sentence`` plainly says the card's right option: every word of the option is in it, and it does not ask.

    Strict on purpose. A spoken "sixteen" is not the card's "16" and "hote" is not "honge", so True means the
    sentence certainly says the answer and False means only that code cannot tell (a listener can: questions.AFTER).
    """
    options, right = quiz.get("options") or [], quiz.get("answer_index")
    if not (isinstance(right, int) and not isinstance(right, bool) and 0 <= right < len(options)):
        return False
    key = {w for w in re.findall(r"[a-z0-9]+", str(options[right]).lower()) if w not in _ANSWER_SMALL}
    return bool(key) and key <= set(re.findall(r"[a-z0-9]+", str(sentence).lower())) \
        and not str(sentence).rstrip().endswith(("?", "?\"", "?”"))


#: On-screen words that talk about the screen are a direction to whoever animates it, not words for the learner:
#: the writer's own list (``writer.SCREEN_TALK``, one definition for a writer's line, a repair's and a rewrite's).
#: And a rewrite's line that OPENS by telling the animator what to do ("Highlight the six-centimetre base on the
#: slanted triangle" stood on screen through a worked example, 2026-10-10). "Draw" and "Label" are not on the list:
#: a try-it task tells the LEARNER to draw.
_SCREEN_TALK = writer.SCREEN_TALK
_TO_THE_ANIMATOR = re.compile(r"^\s*(?:highlight|animate|display|reveal|zoom|fade)\b", re.I)


def anchors_in_order(steps: list[dict], narration: str) -> int:
    """Empty the anchor of a step whose words are spoken out of turn. Returns how many were emptied.

    Steps come up in the order they are written, each when its phrase (``say``) is spoken. After a rewrite a step is
    anchored again from its own words, and can land near the END of the beat: "Leaves A to D", the first step of a
    task, took "leaves B, C" from the beat's last sentence. The steps after it are looked for after that point, are
    not found there, and everything comes up in the beat's last seconds: a still screen for twenty-two seconds, then
    three lines at once (the lesson made again on 2026-10-10; its lateness check failed by 1.9 s and did not say
    why). The steps whose phrases stand in the order of the steps are kept (the longest such run); another's anchor
    is emptied, and the renderer places it by even spread between its neighbours, as for any step with no anchor.
    """
    flat = " ".join(str(narration).lower().split())
    at = [flat.find(" ".join(str(step.get("say") or "").lower().split())) if str(step.get("say") or "").strip() else -1 for step in steps]
    known = [i for i, place in enumerate(at) if place >= 0]
    run: dict[int, tuple[int, int | None]] = {}                    # step -> (length of the best run ending on it, the step before)
    for n, i in enumerate(known):
        run[i] = max(((run[j][0] + 1, j) for j in known[:n] if at[j] <= at[i]), default=(1, None), key=lambda r: r[0])
    if not run:
        return 0
    keep, last = set(), max(run, key=lambda i: (run[i][0], i))
    while last is not None:
        keep.add(last)
        last = run[last][1]
    emptied = [i for i in known if i not in keep]
    for i in emptied:
        steps[i]["say"] = ""
    return len(emptied)


def apply_edits(lesson: dict, report: dict, log=print) -> dict:
    """Text-only repair: swap narration/steps of EXISTING beats; ids, count and order are fixed."""
    by_id = {b["id"]: b for c in lesson["chapters"] for b in c["beats"]}
    applied = []
    for edit in report.get("edits", []):
        beat = by_id.get(beat_id(edit.get("beat"), by_id))
        if beat is None:
            continue
        narration = re.sub(r"\s+", " ", re.sub(r"\[[^\]]*\]|[*_#`]", " ", str(edit["narration"]))).strip()
        # A rewrite is spoken too: no digits or symbols reach the voice, whoever wrote them.
        narration = writer.speakable(narration, (lesson.get("brief") or {}).get("language", "en-IN"))
        if not narration:
            continue
        # A rewrite improves or stands aside. One reviewer answered a Hinglish beat's finding with
        # five English sentences; the next review flagged them and had no round left to fix them.
        requested = str((lesson.get("brief") or {}).get("language") or lesson.get("language") or "").lower()
        if requested in ("hinglish", "hi-in") and \
                len(english_only_sentences(narration)) > len(english_only_sentences(beat["narration"])):
            log(f"[critic] edit for beat {beat['id']} rejected: it turns Hindi sentences into English ones")
            continue
        old_words, new_words = len(beat["narration"].split()), len(narration.split())
        # Down to about a third: cutting a restated scene can remove most of a beat, and that is the point. An edit that
        # only puts ONE sentence in front of a beat (harness/questions.py: the sentence that confirms the answer of the
        # question before it) may double a short beat; it says so with "adds_a_sentence".
        if not 0.35 <= new_words / max(1, old_words) <= (2.6 if edit.get("adds_a_sentence") else 1.6):
            log(f"[critic] edit for beat {beat['id']} rejected: length {old_words}→{new_words} words")
            continue
        # The limit the reviser was given for this beat is held: "at most" in a prompt is advice, this is the contract.
        # (Three words of grace: a rewrite that lands a word or two over is still the cut that was asked for.)
        if edit.get("at_most") and not edit.get("adds_a_sentence") and new_words > int(edit["at_most"]) + 3 and new_words >= old_words:
            log(f"[critic] edit for beat {beat['id']} rejected: {new_words} words where at most {edit['at_most']} were asked ({old_words} before)")
            continue
        # A rewrite improves or stands aside, for the picture too. One reviewer found a bus-and-passenger
        # beat cluttered and rewrote it about a sliding box: the lesson then showed a bus and asked
        # which way the passenger leans while the voice talked about a box (2026-10-09).
        if leaves_its_picture(beat, narration):
            log(f"[critic] edit for beat {beat['id']} rejected: it no longer talks about the beat's picture or its question")
            continue
        # Said plainly, or not at all (the owner, 2026-10-20: "very complex and cryptic"). A reviser asked to shorten
        # a beat cut its sentences into notes ("Weight is mass times g, twice the pull."): the writer's plain beat
        # went to the voice as a telegram. A rewrite may not add notes or plan-talk, nor chop its sentences short.
        # A colon is printed, not said ("socho: light …" → "socho, light …"), in the sentences this rewrite wrote only.
        narration = voice.unnoted(narration, keep=beat["narration"])
        if (lesson.get("brief") or {}).get("mode") != "script":          # a pasted script is spoken as its author wrote it
            narration = voice.split_long(narration)                       # a run-on is cut at its own clause boundaries
        if voice.plan_talk_in(narration) > voice.plan_talk_in(beat["narration"]):
            log(f"[critic] edit for beat {beat['id']} rejected: it reads the lesson's plan aloud (“the claim is”, “test it”)")
            continue
        if voice.chopped(beat["narration"], narration):
            log(f"[critic] edit for beat {beat['id']} rejected: it cuts the beat's sentences short instead of dropping one")
            continue
        # Questions are placed by the lesson's stop plan (writer.stop_plan), about one a minute. Measured 2026-10-20 on
        # ten lessons: the reviser raised a lesson's questions from 4-7 to 5-8 against 4 allowed, answering findings
        # ("the transfer is never answered") with another question. A rewrite may keep or drop a question, not add one.
        if voice.asks_in(narration) > voice.asks_in(beat["narration"]):
            log(f"[critic] edit for beat {beat['id']} rejected: it asks more questions than the beat did")
            continue
        # The answer to the question before stays said. A beat that follows a question card opens by telling its
        # answer; a rewrite of that beat for some other finding dropped the sentence in four of the ten lessons read
        # on 2026-10-10, and the video then stops for a question and never says how it comes out.
        asked = asked_before(lesson, beat["id"])
        opening = split_sentences(beat["narration"])[:1] if asked else []
        if opening and says_answer(opening[0], asked) and not any(says_answer(s, asked) for s in split_sentences(narration)[:2]):
            narration = f"{opening[0]} {narration}"
            log(f"[critic] edit for beat {beat['id']}: the sentence that answers the question before it is kept in front")
        beat["narration"] = narration
        steps = edit.get("steps")
        if isinstance(steps, list) and steps:
            cleaned = []
            for s in steps[:writer.MAX_STEPS]:
                if not isinstance(s, dict) or not str(s.get("show", "")).strip():
                    continue
                if _SCREEN_TALK.search(str(s["show"])) or _TO_THE_ANIMATOR.search(str(s["show"])):
                    continue                # "Broad green leaf stays on screen": a rewrite's note to the animator, shown as a line
                kind = s.get("kind") if s.get("kind") in ("point", "key", "math") else "point"
                if kind != "math" and writer._MATH_MARKERS.search(str(s["show"])):
                    kind = "math"
                # A rewritten line is cleaned as the writer's own are (writer.discipline, repairs.clean_steps): a line of
                # working with a word in it, "180 - 50 = 130 degrees", was set as maths and read "130degrees" (2026-10-12).
                show = str(s["show"]).strip()
                if kind == "math":
                    show = writer.mathify(writer.one_line_math(show))
                show = writer.shown(show, kind)
                if not show:
                    continue
                if cleaned and " ".join(show.lower().split()) == " ".join(cleaned[-1]["show"].lower().split()):
                    continue                # the same line twice in a row is one line ("Two equal triangles", twice)
                cleaned.append({"say": writer._anchor_step(s, narration), "show": show, "kind": kind, "highlight": bool(s.get("highlight"))})
            if cleaned:
                beat["steps"] = cleaned
            else:                           # nothing usable came with the rewrite: the beat's own lines, on the new words
                for s in beat["steps"]:
                    s["say"] = writer._anchor_step(s, narration)
        else:  # the words changed under the old anchors: re-anchor them to the new narration
            for s in beat["steps"]:
                s["say"] = writer._anchor_step(s, narration)
        if anchors_in_order(beat["steps"], narration):
            log(f"[critic] edit for beat {beat['id']}: a step whose words are spoken out of turn is placed by spread, not by them")
        beat["board_text"] = next((s["show"] for s in beat["steps"] if s["kind"] != "math"), "")
        beat["equation"] = next((s["show"] for s in beat["steps"] if s["kind"] == "math"), "")
        applied.append(beat["id"])
    report["edits_applied"] = applied
    return lesson


REVISE_SYSTEM = """You repair the script of an animated lesson for school students. For each listed beat you get its
narration, its on-screen steps and what a subject reviewer found wrong with it. Rewrite the beat so the finding no
longer applies and nothing true is lost. The beat's PICTURE and its QUESTION card are already made and will not change:
the new narration must still be about that picture and still lead to that question, so never swap the beat's example
for another one. A beat marked OPENS BY ANSWERING comes right after the video has stopped for a question: its first
sentence tells the learner the right answer, and your rewrite must still open with a sentence that does. Keep the same teaching point, the same voice, the same language and about
the same length (within 20%) — except for a "repetition" finding: then CUT the repeated words instead of rephrasing
them, never describe the example's setting again, and let the beat be shorter — but keep every word the beat's own
definition, rule or question needs to stay true and complete ("a total that can be arranged in equal rows and equal
columns" must not lose its rows and columns). Narration is spoken aloud: no symbols a voice cannot read, no stage
directions. Keep it said plainly: to make a beat shorter, drop a sentence, never cut sentences into notes (no
colons, no "the answer is:", no clipped phrases like "twice the pull"; keep the small words that make it a sentence). A
thinking pause must come right after a question and before its answer, so a beat with a pause ENDS with the question.
In a Hindi or Hinglish lesson the conversation stays Hindi and EVERY number, fraction, unit, operation and maths
term is English ("three by four", "four metres", "equals", "right angle"), numbers written as English words.
Every step's "say" is 2 to 6 consecutive words copied exactly from the NEW narration. A step's "show" is what the
LEARNER reads on screen: a few words of content ("Height = 4 cm", "Two equal triangles"), each line different from the
others, never a note to whoever animates ("Highlight the base", "Draw the perpendicular, labelled four centimetres").
Each beat is headed with how many words it has now and the most it may have: do not go over. Return ONLY JSON:
{"edits": [{"beat": "05", "narration": "...", "steps": [{"say": "...", "show": "...", "kind": "point|key|math",
"highlight": false}]}]}"""


#: Added to the reviser's rules ONLY when it is told what the pictures hold (``harness/compose.mend`` with
#: ``HARNESS_COMPOSE_MEND=words``): the standing prompt of every other revision is what it was.
REVISE_HOLDS = """A beat may come with THE PICTURE HOLDS: a list read from the finished picture itself. Then the picture is right and the
words give way: never describe, point at or name as visible a thing that is not in that list ("the faint squares", "the
red arrow"); a number may be tied ONCE to a letter the picture prints ("the base, marked b, is six centimetres") and
used freely after that; and what the picture does not show may still be imagined, drawn or tried by the learner, said
as imagining, drawing or trying, never as seeing. A beat marked NO PICTURE is spoken over words alone: it must not
say "look at", "here" or "this" of anything. Change ONLY the words that speak of a thing the picture does not hold:
every other sentence stays word for word, nothing the beat teaches is added, dropped or said earlier than it was, and
the picture, the caption and the screen are never mentioned."""


def revise(lesson: dict, findings: list[dict], llm: LLM, log=print, holds: dict | None = None) -> list[dict]:
    """One call asking for replacement text for the beats with unresolved findings. Returns edits.

    ``holds``: ``{beat id: what the picture on screen during that beat holds}``, a paragraph read from the picture
    itself (``vision_review.holds_line``), for findings that the words speak of things the picture does not show.
    """
    by_id = {b["id"]: b for c in lesson["chapters"] for b in c["beats"]}
    wanted: dict[str, list[str]] = {}
    limits: dict[str, int] = {}
    for f in findings:
        if f["beat"] in by_id:
            wanted.setdefault(f["beat"], []).append(f"[{f['severity']}] {f['what']}" + (f" — suggested: {f['fix']}" if f.get("fix") else ""))
            if f.get("at_most"):
                limits[f["beat"]] = min(int(f["at_most"]), limits.get(f["beat"], 10 ** 6))
    if not wanted:
        return []
    # A rewrite used to be allowed a fifth more words than the beat had, and every lesson grew at each revision. A
    # script that is at its length already gets no more: the same words or fewer.
    budget = _budget(lesson)
    full = bool(budget) and sum(len(b["narration"].split()) for b in by_id.values()) >= budget
    blocks = [f"LESSON: {lesson['title']} — for {lesson.get('brief', {}).get('audience', 'school students')}; "
              f"running example: {lesson.get('anchor', '')}"]
    for bid, problems in wanted.items():
        beat = by_id[bid]
        figure, quiz = beat.get("figure") or {}, beat.get("quiz") or {}
        fixed = (f"  PICTURE (will not change): {figure.get('describe') or figure.get('ask') or figure.get('kind')}\n" if figure else "") \
            + (f"  THE PICTURE HOLDS: {holds[bid]}\n" if holds and holds.get(bid) else "") \
            + ("  NO PICTURE: this beat is spoken over words alone\n" if beat.get("picture") == "off" else "") \
            + (f"  QUESTION card (will not change): {quiz.get('question')}\n" if quiz.get("question") else "")
        answered = asked_before(lesson, bid)
        if answered:
            fixed += (f"  OPENS BY ANSWERING the question the beat before it stops on (\"{answered['question']}\", right answer: "
                      f"\"{answered['options'][answered['answer_index']]}\"): its first sentence must still tell the learner that answer\n")
        words = len(beat["narration"].split())
        limits.setdefault(bid, words + 2 if full else round(words * 1.2) + 2)
        blocks.append(f"\n[beat {bid}] pause={beat.get('thinking_pause_seconds', 0)}s; {words} words now, at most {limits[bid]}\n"
                      f"  SAY: {beat['narration']}\n" + fixed
                      + "\n".join(f"  SHOW ({s['kind']}) at «{s['say']}»: {s['show']}" for s in beat.get("steps", []))
                      + "\n  FOUND:\n" + "\n".join(f"    - {p}" for p in problems))
    raw = llm("\n".join(blocks), REVISE_SYSTEM if not holds else f"{REVISE_SYSTEM}\n{REVISE_HOLDS}") or {}
    edits = [{**e, "beat": beat_id(e.get("beat"), by_id)} for e in (raw.get("edits") or [])
             if isinstance(e, dict) and e.get("narration")]
    for edit in edits:                                   # the limit each beat was given travels with its rewrite (``apply_edits``)
        if edit["beat"] in limits:
            edit["at_most"] = limits[edit["beat"]]
    log(f"[critic] revision asked for {len(wanted)} beat(s), {len(edits)} rewrite(s) returned")
    return edits


def verify(lesson: dict, llm: LLM | None, log=print, apply: bool = True, rounds: int | None = None) -> dict:
    """Review, repair, re-check. Attaches ``lesson["verification"]`` and returns it.

    With a reviewer: review → apply its edits → if a critical or major finding is still
    open, ask for a rewrite of exactly those beats and review ONCE more (``rounds`` =
    number of reviews, default 2, env ``HARNESS_CRITIC_ROUNDS``). Speech is bought only
    after this, so a wrong sentence costs a model call here instead of a narrated video.
    """
    if llm is None:
        lint = arithmetic_lint(lesson)
        report = {"scores": {k: None for k in RUBRIC},
                  "findings": pause_gate(lesson) + figure_gate(lesson) + language_gate(lesson) + repetition_gate(lesson)
                  + setting_gate(lesson) + length_gate(lesson),
                  "edits": [],
                  "universal_claims": universal_claims(lesson), "readability": readability(lesson),
                  "claims": [{"beat": i["beat"], "claim": i["text"], "python": "(arithmetic lint)", "result": i["ok"]} for i in lint],
                  "claims_checked": len(lint), "claims_failed": [i for i in lint if not i["ok"]], "claims_unverifiable": 0,
                  "summary": "no reviewer model configured — arithmetic lint only", "edits_applied": []}
    else:
        import os
        rounds = rounds if rounds is not None else int(knobs.get("HARNESS_CRITIC_ROUNDS", "2"))
        history, all_applied = [], []
        report = review(lesson, llm, log=log)
        for round_number in range(1, max(1, rounds) + 1):
            if apply and report["edits"]:
                apply_edits(lesson, report, log=log)
            applied = set(report.get("edits_applied", []))
            all_applied += [b for b in report.get("edits_applied", []) if b not in all_applied]
            open_findings = [f for f in report["findings"] if f["severity"] in ("critical", "major")
                             and f["beat"] not in applied and not str(f.get("what", "")).startswith("figure:")]
            history.append({"round": round_number, "scores": report["scores"], "findings": len(report["findings"]),
                            "open_critical_or_major": len(open_findings), "edits_applied": sorted(applied)})
            if not apply or round_number >= rounds:
                break
            changed = bool(applied)
            try:
                if open_findings:               # the reviewer named a problem but wrote no fix for it
                    rewrite = {"edits": revise(lesson, open_findings, llm, log=log)}
                    apply_edits(lesson, rewrite, log=log)
                    all_applied += [b for b in rewrite.get("edits_applied", []) if b not in all_applied]
                    changed = changed or bool(rewrite.get("edits_applied"))
                if not changed:
                    break                       # same text: a second review would say the same
                # Whatever changed is checked, not trusted — and the scores reported with
                # the lesson are then the scores of the script that is actually narrated.
                report = review(lesson, llm, log=log)
            except Exception as exc:  # noqa: BLE001 - keep the review we have rather than lose it
                log(f"[critic] re-check failed ({type(exc).__name__}: {str(exc)[:100]}); keeping the previous review")
                break
        # The code gates (language, repetition, a story setting, the length) are cheap and exact, and the last review may
        # leave some of their findings standing with no round left. They get rewrites of their own (``GATE_ROUNDS``: a
        # second one only for what the first left open, since one round brought three real scripts from 114% of their
        # length to 106%, with a rewrite or two refused by another contract each time); then the gates — not the
        # reviewer — say what is still open.
        gates = lambda: (language_gate(lesson) + repetition_gate(lesson) + setting_gate(lesson) + length_gate(lesson)  # noqa: E731
                         + (storyflow.story_gate(lesson) if storyflow.enabled() else []))
        for round_ in range(GATE_ROUNDS):
            standing = [f for f in gates() if f["severity"] in ("critical", "major")]
            if not (apply and standing):
                break
            try:
                rewrite = {"edits": revise(lesson, standing, llm, log=log)}
                apply_edits(lesson, rewrite, log=log)
                all_applied += [b for b in rewrite.get("edits_applied", []) if b not in all_applied]
                # Found again AFTER the rewrite: these are open, whatever edits landed on their beats.
                report["findings"] = [f for f in report["findings"]
                                      if not str(f.get("what", "")).startswith(("language:", "repetition:", "example:", "length:", "story:"))] + \
                                     [{**f, "still_open": True} for f in gates()]
                report["edits_applied"] = list(dict.fromkeys(report.get("edits_applied", []) + rewrite.get("edits_applied", [])))
                open_after = sum(1 for f in gates() if f["severity"] in ("critical", "major"))
                history.append({"round": "gates" if round_ == 0 else f"gates {round_ + 1}", "open_before": len(standing),
                                "open_after": open_after, "edits_applied": sorted(rewrite.get("edits_applied", []))})
                if not rewrite.get("edits_applied") or open_after >= len(standing):
                    break                                # nothing landed, or nothing got better: another asking is the same asking
            except Exception as exc:  # noqa: BLE001
                log(f"[critic] gate rewrite failed ({type(exc).__name__}: {str(exc)[:100]}); findings stand")
                break
        report["rounds"] = history
        report["beats_rewritten"] = all_applied
        if all_applied:
            lesson["continuity"] = writer.continuity(lesson)
            after = arithmetic_lint(lesson)
            report["arithmetic_after_edits"] = {"checked": len(after), "failed": sum(1 for i in after if not i["ok"])}
    report.setdefault("edits_applied", [])        # a report-only review (apply=False) applied none
    fixed = set(report["edits_applied"])
    for f in report["findings"]:
        if "resolved" in f and str(f.get("what", "")).startswith("figure:"):
            continue                    # decided by the figure gate, not by whether a text edit landed
        if f.pop("still_open", False):
            f["resolved"] = False       # a code gate found it in the text that will be narrated
            continue
        f["resolved"] = f["beat"] in fixed and f["severity"] != "critical" or (f["beat"] in fixed and bool(f["fix"]))
    report["critical_unresolved"] = sum(1 for f in report["findings"] if f["severity"] == "critical" and not f["resolved"])
    report["major_unresolved"] = sum(1 for f in report["findings"] if f["severity"] == "major" and not f["resolved"])
    # Measured on the second real run: a reviewer flagged "the bottom number never
    # changes" (false as a rule) as MAJOR and offered no edit; that must not pass.
    report["status"] = ("needs_review" if report["critical_unresolved"] or report["major_unresolved"]
                        or report["claims_failed"] else "passed")
    lesson["verification"] = report
    return report
