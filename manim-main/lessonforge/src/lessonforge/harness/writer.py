"""Brief + framework → a lesson contract.

The model writes words; code owns everything structural. That split is the same one
the engine uses for storyboards, and it is what makes a generated script safe to
render unattended:

* ids, chapter order and the framework's stage sequence come from code;
* every on-screen step must be anchored to a phrase that is ACTUALLY in the
  narration — an anchor the model invented is re-derived or dropped to an even
  spread, never trusted;
* step counts, lengths and highlight budgets are clamped;
* continuity is MEASURED on the result (does the running example come back in
  every chapter? does a chapter open by re-introducing the topic?) and reported
  with the lesson. A weak story still renders — rejecting would spend a whole
  regeneration on a soft metric — but it is a number, not a feeling.

Long lessons are written one chapter at a time against a shared ledger (running
example, glossary, what has already been established, the previous chapter's last
lines), so chapter 5 cannot contradict or re-introduce what chapter 2 said. Short
lessons are a single call.

With no model configured, ``outline_lesson`` returns a deterministic outline whose
narration describes each stage's job. It is a placeholder that exercises the whole
pipeline and says so — it is not a lesson.
"""
from __future__ import annotations

import json
import os
import re
from typing import Any, Callable

from .. import kits, knobs
from ..longform import figure_math
from ..longform.contract import Lesson
from . import card as teaching_card
from . import diagrams, frameworks, intake, skill, voice

# Measured on eight narrated lessons (2026-10-08): 112 to 135 words a minute once the gaps
# between sentences and the lead-ins are counted, mean 125. At the assumed 135, with the
# thinking pauses uncounted and a floor of 120 words a chapter, EVERY lesson overran what
# was asked for: six-minute requests ran 7.3 to 9.2 minutes, two-minute ones 3.6 to 4.
WORDS_PER_MINUTE = 125
PAUSE_SECONDS_PER_MINUTE = 5      # "about once a minute, stop and ask" — time that is not speech


def word_budget(minutes: int) -> int:
    """Spoken words that fit the requested length, after the thinking pauses."""
    return int(minutes * (60 - PAUSE_SECONDS_PER_MINUTE) / 60 * WORDS_PER_MINUTE)

MAX_STEPS = 5
MAX_HIGHLIGHTS = 2
# Measured 2026-10-08 on the first real run: asked for ~810 words in one call, Gemini
# 3.8 Flash wrote 507, 2.5 Flash 727, 3.5 Flash-Lite 438. Per-chapter calls carry an
# explicit word budget each, so anything longer than a 3-minute short is written
# chapter by chapter against the ledger.
SINGLE_CALL_MINUTES = 3
_MATH_MARKERS = re.compile(r"\\[A-Za-z]+|\^|_\{|\\\(|\$")
MAX_SHOW_WORDS = 9            # what STEP_RULES asks for; three more are let through before code shortens a step
#: On-screen words that talk ABOUT the screen are a direction to whoever animates it. "Broad green leaf stays on
#: screen" stood on screen for a whole beat of the first end-to-end trial lesson (2026-10-10). Only wordings no
#: lesson line has: "the coin stays there" is the inertia lesson's own sentence and must pass.
SCREEN_TALK = re.compile(r"\bon[- ](?:the )?screen\b|\b(?:stays?|remains?|keeps?) (?:visible|in view)\b|"
                         r"\b(?:zooms?|fades?) (?:in|out)\b", re.I)


def shown(show: str, kind: str = "point") -> str:
    """A step's on-screen text, as it may be drawn: ONE function for the writer's steps and for a repair's.

    "" for a line that talks about the screen (``SCREEN_TALK``): the caller drops that step.
    A line of working (kind "math") is cut only by length, as before. A line of wording
    is at most ``MAX_SHOW_WORDS`` words (twelve are let through): a longer one is not a
    label, it is a sentence or a direction to whoever animates. The lesson that taught it
    (2026-10-09) showed "Say the route, highlight the sea to cloud, cloud to ground and
    return legs with labels evaporation, condensati", cut in the middle of a word, and
    the column shrank every other step to fit it. Its first clause is kept when that is
    short enough, else its first nine words; never part of a word.
    """
    show = str(show or "").strip()
    if kind == "math":
        return show[:110]
    if SCREEN_TALK.search(show):
        return ""                              # a direction, not a line: the step is not shown at all
    words = show.split()
    if len(words) > MAX_SHOW_WORDS + 3:
        first = re.split(r"[,;:]\s|\s[—–-]\s", show, maxsplit=1)[0].strip()
        show = first if 2 <= len(first.split()) <= MAX_SHOW_WORDS else " ".join(words[:MAX_SHOW_WORDS])
        show = show.rstrip(" ,;:—–-")
    while len(show) > 110 and " " in show:
        show = show.rsplit(" ", 1)[0].rstrip(" ,;:—–-")
    return show[:110]
FIGURE_KINDS = ("shape", "right_triangle", "number_line", "bars", "circle", "rectangle", "graph", "reaction", "float", "scene")   # mirrors longform.figures.KINDS (no manim import here)
#: Kinds that exist only when something was prepared for THIS lesson, so no standing prompt
#: describes them: the teaching card's own block does (``card.for_writer``), and
#: ``use_diagram`` removes one that was asked for with nothing prepared.
PREPARED_KINDS = ("diagram",)
#: Kinds a lesson can bring from outside that no prompt offers the writer. Empty since 2026-10-20: the writer drew a
#: taxi-fare graph as a model-written scene with its dots off the line, because nobody had told it ``graph`` existed.
IMPORTED_KINDS: tuple = ()
MAX_DIAGRAM_LABELS = 9     # more names than this on one drawing and none of them can be read on a phone   # mirrors longform.figures.KINDS (no manim import here)
_STYLE_NOTES = {
    "storyteller": "Warm, unhurried storyteller. Vivid and concrete. One idea per sentence.",
    "tutor": "Crisp tutor. Says why each step is taken. No filler.",
    "questioner": "Curious questioner. Asks real questions, lets the learner predict before revealing.",
}
_LANGUAGE_NOTES = {
    "en-IN": "Narration in clear Indian English.",
    "hi-IN": "Narration in natural spoken Hindi (Devanagari) for the CONVERSATION only. Everything technical is in "
             "English, written in Latin script, exactly as in an English-medium classroom: every number, fraction, "
             "unit, operation and subject term. Write 'three by four', 'five squared', 'ninety degrees', 'plus', "
             "'equals', 'right angle', 'hypotenuse' — never तीन बटा चार, पाँच का वर्ग, बराबर, कोण, त्रिभुज. "
             "A fraction p/q is read 'p by q'. Numbers are written as English words.",
    "hinglish": "Narration in natural spoken Hinglish in Latin script, the way a good teacher talks in an "
                "English-medium Indian classroom: Hindi for the CONVERSATION (dekhiye, ab hum, toh, kyunki, isliye, "
                "sochiye, samajhte hain), English for EVERYTHING technical — every number, fraction, unit, operation, "
                "symbol name and subject term. Write 'three by four', 'sin theta equals three by four', 'five "
                "squared', 'ninety degrees', 'four metres', 'plus', 'minus', 'into', 'equals', 'right angle', "
                "'hypotenuse', 'opposite side' — NEVER 'teen bata char', 'paanch ka varg', 'char metre', 'barabar', "
                "'jod', 'guna', 'kon', 'tribhuj'. A fraction p/q is read 'p by q'. Numbers are written as English "
                "words. Keep sentences short and warm; do not translate a term and then repeat it in the other language. "
                "EVERY sentence is a Hindi sentence that carries English terms — 'Seven prime number hai, lekin six aur "
                "nine nahi hain', never 'Seven is prime, but six and nine are not'. A sentence that would read as plain "
                "English with the terms removed is wrong.",
    "te-IN": "Narration in natural spoken Telugu. Keep exam-relevant technical terms in English.",
    "ta-IN": "Narration in natural spoken Tamil. Keep exam-relevant technical terms in English.",
}
LLM = Callable[[str, str], Any]  # (prompt, system) -> parsed JSON

_SYSTEM_OPENING = """You write the script for a narrated, animated lesson. You are an expert teacher: you explain one idea
so that it actually lands, the way the best classroom teachers do — a concrete running example, honest questions,
and every symbol earned before it is used.

Return ONLY JSON. Rules that are checked by code after you answer:
- "narration" is EXACTLY what is spoken. No stage directions, no markdown, no bracketed tags, no symbols a voice
  cannot read (write "x squared", not "x^2"; "three metres", not "3 m").
"""
# The screen rules are shared with ``scripted.py`` (a script the user wrote, where a model designs only
# the screen), so a figure kind or a step field is described in ONE place.
STEP_RULES = """- Each beat has "steps": what appears on screen WHILE it is spoken. Every step has
  "say"  — 2 to 6 consecutive words copied EXACTLY from this beat's narration, marking when the step appears;
  "show" — the on-screen text (at most 9 words) or, for kind "math", ONE line of LaTeX without dollar signs
           (no \\begin{...} environments, no line breaks: one step per line of working);
  "kind" — "point" (a line of wording), "key" (the one idea to remember) or "math";
  "highlight" — true only for the single most important step of the beat.
  "focus" — the part of this beat's figure the step is about, so the picture REACTS when it is said (the part
            pulses and its value travels to the formula). right_triangle: "a" | "b" | "c" | "angle" | "right_angle" |
            "square_a" | "square_b" | "square_c"; bars: "bar0", "bar1", ...; number_line: "point0", "point1", ...,
            "arrow"; circle: "radius" | "diameter" | "circumference" | "centre" | "sectors"; rectangle: "length" |
            "width" | "area". Give a focus on every step that talks about a part of the picture.
  2 to 4 steps per beat. Steps appear in the order their "say" phrases occur.
- The lesson is WATCHED, not read: prefer a figure with focused steps over lines of wording, and let the formula
  grow one line at a time (each "math" step is the previous line taken one move further).
"""
# What makes a question worth its pause. Written by the other session for harness/questions.py (the pass that writes a
# lesson's questions again), after the owner said "it not giving good questions" (2026-10-09); that module imports this
# one, so the text lives here and a test holds the two equal. The writer gets it too: the pass can change how a beat
# ENDS, never where its question sits, and a question put after the beat has said the answer can only repeat it.
QUESTION_RULES = """A QUESTION EARNS ITS PAUSE ONLY IF THE LEARNER HAS TO THINK AT THAT MOMENT. A learner who only repeats
the last thing the voice said must not get it right: the answer is never in the sentences just before the question, and
an option is never a sentence of the script. Four kinds of question do this, each in its place:
- "predict": BEFORE the idea is told. The learner commits to a guess from what is on screen and what they already know.
  Nothing said or shown so far gives the answer; the lesson then shows who was right.
- "apply": AFTER the idea. A NEW small case that needs the idea to answer, and whose answer comes out DIFFERENT from
  what the lesson has been saying: change one thing (take the cause away, change a number, swap the object, turn the
  order round). After "a square of side 4 has area 16": the side is doubled to 8, what is the area now? After "a
  closed circuit lights the bulb": one wire is taken out, what does the bulb do? After "plants make food in sunlight":
  a plant spends a week in a dark cupboard, what happens to its leaves? Never the case the lesson has just worked,
  and never a fact the voice has just said, in the same words or in others.
- "spot": at the usual mistake, BEFORE the lesson corrects it. The voice gives the wrong idea as somebody's claim and
  stops there; the card asks about the thing itself, so that a learner who holds the wrong idea picks a wrong option.
- "recall": at the START of a recap, before the idea is said again: its name, its value or its rule, asked for cold.
Never ask about the lesson ("which step", "what did we see first", "what was the second point"): that tests memory of
a video, not understanding of anything.
THE BEAT ENDS WITH THE QUESTION. Nothing is said after it: no hint, no reason, no "think about …". Before it the beat
sets the case up and stops short of how the case comes out: neither the answer nor its reason is said in that beat
before the question, and neither is on screen while it is asked.
THE CARD: one sentence of at most 14 words that ends with a question mark, asking exactly what the voice asks. Ask
what, which, how many or what happens; a "why" on a card needs a sentence for an answer, and a sentence is not an option.
THE OPTIONS: three SHORT ANSWERS of one kind: a name, a number with its unit, a colour, a direction, an outcome
("Black", "64 square cm", "Evaporation", "It goes out"). One to three words each. Never a statement and never an
explanation ("Blue light scatters toward our eyes" is narration with a tick box, not an option): the question carries
the situation and the option carries only the answer. No reason inside an option ("Blue, because …" is two things).
Built alike, so the right one cannot be told by its length or its detail. Exactly one is right. Each wrong one is what
a learner with a real mistake would pick, not a joke and not "none of these".
THE FEEDBACK: one short sentence for EACH option. For the right one, why it is right. For a wrong one, what makes it
tempting and why it fails. Never the same sentence twice, never "Not quite"."""


def _indented(text: str, by: str = "  ") -> str:
    return "\n".join(by + line if line else line for line in text.split("\n"))


_SYSTEM_VIEWERS = """- ONE VIDEO, SEVERAL VIEWERS. Every beat carries "depth": "basics" (what a beginner needs first: prerequisites and
  the slow build-up), "core" (the idea itself, its formula, the ONE worked example, the answer to the opening
  question, the recap), "practice" (your-turn questions and further examples) or "extra" (enrichment, edge cases,
  the misconception in detail). A learner who is REVISING watches only the core beats, in order — so every core
  beat must make sense with the non-core beats before it skipped: it names what it talks about ("in our ladder
  triangle, the wall is the opposite side") instead of pointing back ("as we just saw"). About a third to a half
  of the lesson is core; the recap is core.
- INTERACTION: about once a minute, stop and ask. Such a beat has "thinking_pause_seconds" (4 to 6), ENDS with the
  question, and carries "quiz": {"question": "at most 14 words", "options": ["three short answers, one to three words each"],
  "answer_index": 0, "why": ["one short sentence for EACH option, in the options' order"], "explain": "one short
  sentence said by the screen after the reveal"}. Vary where the right option sits. The NEXT beat opens by confirming
  the answer: so the beat that asks has NOT yet said the answer or its reason. A recap asks first and tells after the
  pause; a beat about the usual mistake gives the wrong idea as a claim and asks BEFORE it corrects. A chapter whose job is to
  predict, practise or recall stops when it is told it STOPS; a chapter told it DOES NOT STOP asks nothing it waits
  for. What makes a question worth its pause:
""" + _indented(QUESTION_RULES) + """
"""
SCREEN_TEXT_RULE = """- On-screen text is in English unless told otherwise. Never put a sentence of narration on screen.
"""
def _shape_rules() -> str:
    from . import shapes  # noqa: PLC0415 - shapes imports nothing from here at import time
    return shapes.SHAPE_RULES


FIGURE_RULES = """- A beat may carry ONE "figure" drawn by code (give numbers, not descriptions). Use one whenever the
  narration talks about a picture; repeat the SAME figure object on later beats that keep discussing it. Kinds:
    {"kind":"right_triangle","a":4,"b":3,"labels":{"a":"4 m","b":"3 m","c":"?"},"unknown":"c","angle":"a",
     "angle_label":"θ","squares":false}
      a = horizontal leg, b = vertical leg, c = hypotenuse. Give any two lengths ("b":3,"c":4 is fine); code
      computes the third and draws to scale. Labels are short plain text ("3 m", "ground", "ladder 4 m") and any
      number in a label MUST be that side's length. "angle":"a" marks the angle between leg a and the hypotenuse
      (at the foot of the hypotenuse), "angle":"b" the one at the top; never put θ in a side label.
      "squares":true draws the three squares on the sides; "result":"c" once a side is found.
    {"kind":"number_line","min":-5,"max":5,"points":[{"x":-3,"label":"-3","role":"given"}],
      "arrow":{"from":-3,"to":3,"label":"×(-1)","role":"unknown"}}
    {"kind":"bars","parts":[{"label":"1/2","n":1,"d":2,"role":"given"},{"label":"1/3","n":1,"d":3,"role":"given"}]}
    {"kind":"circle","r":7,"labels":{"radius":"7 cm","diameter":"","circumference":""},"sectors":0,"unknown":"area"}
      "sectors":8 (or 16, 32) cuts the disc into that many equal sectors; "rearranged":true lays them out side by
      side, alternately up and down (the cut-and-rearrange picture for the area of a circle).
    {"kind":"rectangle","w":6,"h":4,"labels":{"w":"6 m","h":"4 m","area":""},"grid":true,"unknown":"area"}
      "grid":true draws the unit squares (use it when counting area).
    {"kind":"graph","functions":["40 + 12*x"],"x_range":[0,10],"x_label":"km","y_label":"fare (rupees)",
     "labels":{"curve0":"fare = 40 + 12 × km"},"points":[{"x":5,"label":"(5, 100)","role":"result"}]}
      any relation y = f(x) on axes (a straight line, a parabola, a rate, a cost): give the FUNCTION, never
      drawn coordinates. Up to three functions, written with x, numbers, + - * / ^ and sqrt/sin/cos/log; code draws
      each from its formula and computes where two lines meet, holes and asymptotes. A point gives only "x": code
      puts it ON the first curve, so it can never sit off the line. Use the same graph object on every beat that
      keeps discussing it.
    {"kind":"reaction","equation":"2H2 + O2 -> 2H2O","counts":true}
      a chemical equation drawn as ball molecules: code draws every molecule, the formula under it and the atom
      count of each side FROM THE EQUATION, so give only the equation (formulas with their numbers, an unknown
      coefficient as "?": "? N2 + ? H2 -> ? NH3"). Write a new equation on the beat where the voice changes it
      (a coefficient added); the picture changes into it. "role":"wrong" shows the formulas as a mistake (a
      formula changed the forbidden way, "H2 + O2 -> H2O2"). Use it for every chemical equation, never a scene.
    {"kind":"float","liquid":{"name":"water","density":1.0},"objects":[{"name":"ice","mass":92,"volume":100}]}
      objects in a tank of liquid (floating, sinking, density, how much is under the surface): give each object two
      of mass (g), volume (cm³), density (g/cm³). Code works out its density and where it rests, and ANIMATES it
      being let go: a floater dips, bobs and settles with the right share under the surface, a sinker goes to the
      floor, the liquid rises. Up to three objects side by side to compare. Use it for every floating or sinking
      object, never a scene; give a NEW float figure (new numbers) when the lesson moves to another object.
""" + _shape_rules() + """    {"kind":"scene","describe":"ONE sentence saying what is drawn and what MOVES, with its numbers"}
      for anything the kinds above cannot draw: a process, an experiment, particles, a flow,
      a machine, a cell, a circuit. A strong model writes AND ANIMATES it, so describe the mechanism, not the
      styling — e.g. "A closed flask holding 12 brown NO2 molecules and 6 colourless N2O4 molecules; pairs of NO2
      keep joining into N2O4 while N2O4 molecules keep splitting, at the same rate, so the counts stay constant".
      No words in it (the steps carry the words). Use the SAME sentence on every beat that keeps the picture and
      write a new one only when the picture must change. Steps beside a scene take no "focus".
      A scene is drawn in a small box, so it holds at most about 40 objects. NEVER ask for a large count one by
      one ("1764 ladoos"): describe a small version with the same structure ("a square tray, 6 rows of 6
      ladoos, filling row by row") and let a step show the real number. One mechanism, one motion.
      Prefer a kind above when one fits: rows and columns of things are a "rectangle" with "grid":true; molecules
      of a reaction are a "reaction"; points, sides, angles and polygons are a "shape".
  roles: given | unknown | result | wrong. Omit "figure" when no picture is being discussed.
  A figure STAYS ON SCREEN until another replaces it. So when the lesson moves to a new case (another object, other
  numbers, a practice question), that beat gives a new figure with THAT case's numbers; never leave the last case's
  picture up while the voice talks about different numbers.
"""
_SYSTEM_WRITING = """- One beat is 35 to 75 spoken words. Use "thinking_pause_seconds" (3 to 6) only right after a question you
  genuinely want the learner to answer.
- SAY IT PLAINLY, the way a good lecturer explains to one learner: full sentences joined by so, because, which
  means; "you" and "we"; each sentence starting from where the last one ended. Never notes: no colons, no labels
  ("Claim:", "Step one:"), no lesson plan said aloud ("here is the claim", "test it", "change one thing", "your
  turn", "start small"), never a row of orders. A question is asked only where the chapter stops; anywhere else the
  thought is said, not asked.
- SOUND LIKE A TEACHER WHO ENJOYS THE IDEA, thinking aloud with the learner ("let's see what happens if", "notice
  that", "so what does this tell us"). Most sentences are 12 to 22 words and carry a reason with its result; a very
  short sentence is kept for the one moment that matters ("And it is exactly one."). At the turning point say once,
  in your own words, that it is surprising or that it is the fact everything rests on ("This surprises almost
  everyone."), with no exclamation mark and never "here is the". Be honest: say what you assume ("when the air hardly
  slows it") and where the idea stops working. Give every number its unit and keep one name for one thing. The idea
  comes before its name or formula: show why it must be so, then name it. Near the end say the key idea again in
  new, shorter words, and end on one sentence a learner can carry away. Never stock phrases ("let's dive in", "in
  this video", "fascinating", "journey", "simply put", "in conclusion"), and never a real lecturer's catchphrases
  or stories.
- THE EXAMPLE SERVES THE IDEA, never the other way round. ONE example, with the SAME numbers every time.
  · It is one everyday object the learner has handled (a tray of sweets, a ladder, a pizza) — no story around
    it: no festival, shop, owner, match, journey or reason for doing it. Every part of the example must stand
    for a part of the idea; a part that stands for nothing is left out. An example that needs explaining is the
    wrong example.
  · If the idea is already something that can be drawn or counted (numbers, shapes, a graph, a table of values),
    use the thing itself with small numbers and no everyday object at all.
  · Start from the SMALLEST case that shows the idea (3 rows of 3 before 42 rows of 42) — one the learner can
    count on screen — and only then move to the lesson's numbers.
  · Describe the example ONCE, in one or two sentences, in the chapter told to introduce it. After that call it
    by its short name and never describe it or its setting again. Use it only where it helps that chapter's
    job; working, practice and recap are done in plain maths.
- A chapter after the first opens by continuing from the previous one — never by re-introducing the topic, the
  example or the viewer.
- TEACH THE METHOD THE GOAL NEEDS. Every step the learner must be able to do afterwards is carried out on
  screen at least once, slowly, in the order they will do it. When the goal is a test or a decision, show one
  case that passes AND one that fails. Never reach an answer by a route the learner cannot take (guessing it,
  or already knowing it).
- A long number (four digits or more) is spoken in full at most once per chapter; after that say "this number"
  (in Hindi "yeh number") — it stays on screen in digits.
- Use each technical term one way throughout, in its ordinary spelling. NEVER write phonetic respellings
  ("hypotenuse", not "high-pot-en-yoos"): the narration is also the captions, and the voice knows the words.
- SAY A THING ONCE. No sentence, question, explanation or result is said again in a later beat; a later beat
  may point back in at most six words. Each beat must add something the learner did not have. The recap asks —
  it does not re-explain. The known mistake is met only in the chapter whose job is to confront it.
- CANVAS AND STAGE CONTINUITY:
  When an apparatus, solid, or visual setup is used for a demonstration or derivation, KEEP IT ON SCREEN across the whole chapter and consecutive chapters (do not omit "figure" or set it to null during working, formulas, or practice beats of that example). The picture stands stably on the left of the stage while the steps and mathematics unfold on the right. Dropping the figure causes visual flashes and canvas discontinuity."""
# Since 2026-10-09 the renderer cuts a scene's animation into one stage per step and starts
# stage k at step k's words (``runtime._start_motion``). Before that a scene was one motion
# stretched evenly over the beat: it began before the words that describe it and stood still
# while the words moved on. The rule below is what lets the writer use that; the script
# path's director carries the same sentence in its own prompt.
SCENE_STAGES_RULE = """- A SCENE MOVES WITH THE WORDS. Write a "scene"'s motion as STAGES, one for each step of its beat, in the
  order the steps are spoken: "<what is drawn>; first <what happens at step 1's words>, then <at step 2's words>, then
  <at step 3's words>". The picture reaches each stage when that step's words are said and waits there, so every
  stage shows what those very words say: when the voice counts a row, that row lights up; when it says the answer,
  the answer appears in the picture. Nothing in the picture happens before the words that describe it. Three
  steps, three stages. Keep the whole description under 400 characters.
"""
SYSTEM = _SYSTEM_OPENING + STEP_RULES + _SYSTEM_VIEWERS + SCREEN_TEXT_RULE + FIGURE_RULES + SCENE_STAGES_RULE + _SYSTEM_WRITING


def _brief_block(brief: dict, framework: dict) -> str:
    lines = [
        f"TOPIC: {brief.get('topic', '')}",
        f"AUDIENCE: {brief.get('audience', '')} (starting point: {brief.get('level', 'standard')})",
        f"AFTER WATCHING THEY CAN: {brief.get('goal', '')}",
        f"TEACHER VOICE: {_STYLE_NOTES.get(brief.get('style', ''), _STYLE_NOTES['tutor'])} {framework['voice']}",
        f"LANGUAGE: {_LANGUAGE_NOTES.get(brief.get('language', 'en-IN'), _LANGUAGE_NOTES['en-IN'])}",
    ]
    if brief.get("subject") and brief["subject"].lower() != str(brief.get("topic", "")).lower():
        lines.insert(1, f"WITHIN THE WIDER SUBJECT: {brief['subject']} (teach only the topic above)")
    for field, said in (brief.get("notes") or {}).items():
        lines.append(f"THE REQUESTER'S OWN WORDS ABOUT THE {field.upper()}: {said}")
    if brief.get("context"):
        # The requester's words are a suggestion, not an order: the old intake offered settings
        # like this one itself, and a gradient-descent lesson kept its cricket squad even after
        # the rules changed, because the brief still said so.
        lines.append(f"THE REQUESTER SUGGESTED THIS EXAMPLE: {brief['context']} — use it ONLY if it is simpler than the "
                     f"idea. Keep at most its one object and its numbers; drop people, sport, devices, places and "
                     f"occasions. If it still has more parts than the idea, replace it with the thing itself in small "
                     f"numbers (a short table of values, a few points on a graph).")
    if brief.get("misconception"):
        lines.append(f"KNOWN MISTAKE TO MEET HEAD-ON: {brief['misconception']}")
    if brief.get("explanations"):
        from . import explanations
        lines.append(explanations.block(brief["explanations"]))
    if brief.get("kit_hints"):        # from harness/kit_pipeline.plan_to_brief: absent from every older brief, so no older prompt changes
        lines.append("PICTURES CHOSEN BY CODE FOR THE PARTS OF THIS LESSON (give the beat that teaches a part the figure named "
                     "for it; where no kit figure fits, use none and type no number you worked out):\n"
                     + "\n".join(f"  - {h}" for h in brief["kit_hints"] if isinstance(h, str)))
    return "\n".join(lines)


def _stage_block(framework: dict, stops: set[int] | None = None) -> str:
    return "\n".join(f"  {i}. [{s['role']}] {s['title']} — {s['job']}"
                     + ("" if stops is None else " " + (STOPS if i - 1 in stops else NO_STOP))
                     for i, s in enumerate(framework["stages"], 1))


# Where a lesson stops for the learner is decided here, for the whole lesson, not by each chapter. Every stage of a
# framework used to have a reason to ask ("invite a prediction", "ask why this step is allowed", "a chapter whose job is
# to predict must have one"), so a three-minute lesson stopped six to nine times, once every twenty seconds, and every
# beat ended on a question (the five lessons of 2026-10-19; the owner: "very complex and cryptic"). Lecturers on the same
# topics ask 0.1 to 1 times in 100 words. A lesson now stops about once a minute: its opening question, then the recap,
# the chapter that owns the usual mistake, then practice.
STOP_ROLES = ("recap", "refutation", "conflict", "faded", "practice", "transfer", "explore", "concrete", "proof")
STOPS = ("STOPS ONCE: one beat of this chapter ends on a question for the learner, with thinking_pause_seconds and a quiz.")
NO_STOP = ("DOES NOT STOP: no beat of this chapter ends on a question, has thinking_pause_seconds or a quiz. Where the "
           "job says ask, predict or pause, ask it in passing and answer it in the next sentence, as a lecturer thinks "
           "aloud; say everything else as plain explanation.")


def keep_planned_stops(lesson: dict, stops: set[int], log=print) -> dict:
    """The lesson stops where its plan says, once a chapter; any other stop is taken out, its words unchanged.

    Told which chapters stop, the writer still stopped six times in a three-minute Moon lesson (twice in its first
    chapter, once in a chapter told not to, twice in the recap). A stop taken out keeps its question, which the next
    beat answers, as a lecturer asks and answers aloud; only the pause and the card go (as ``questions.improve`` does
    for a stop it cannot cure). A chapter's stop that is kept is the one with a card, else its last.
    """
    dropped = []
    for at, chapter in enumerate(lesson.get("chapters") or []):
        stopping = [b for b in chapter.get("beats") or [] if b.get("thinking_pause_seconds")]
        keep = None
        if at in stops and stopping:
            keep = next((b for b in reversed(stopping) if b.get("quiz")), stopping[-1])
        for beat in stopping:
            if beat is not keep:
                beat.pop("quiz", None)
                beat["thinking_pause_seconds"] = 0.0
                dropped.append(beat["id"])
    lesson["stops"] = {"planned": sorted(stops), "taken_out": dropped}
    if dropped:
        log(f"[writer] stops taken out where the lesson's plan has none (the words are kept): {', '.join(dropped)}")
    return lesson


def stops_allowed(minutes: float) -> int:
    return max(2, round(minutes))


def stop_plan(framework: dict, minutes: float) -> set[int]:
    """The chapters (by index) that stop for the learner: the first, then by ``STOP_ROLES``, about one a minute."""
    stages = framework["stages"]
    if framework.get("stops"):  # a framework that names its own stops (the story: its opening question and one check)
        return {i for i, s in enumerate(stages) if s["role"] in framework["stops"]}
    owner = stages.index(frameworks.misconception_stage(framework))
    order = [0, len(stages) - 1, owner] + [i for role in STOP_ROLES for i, s in enumerate(stages) if s["role"] == role]
    chosen: list[int] = []
    for i in order:
        if i not in chosen and len(chosen) < min(stops_allowed(minutes), len(stages)):
            chosen.append(i)
    return set(chosen)


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^\w ]", "", (text or "").lower())).strip()


def _anchor_step(step: dict, narration: str) -> str:
    """A ``say`` phrase guaranteed to be in the narration, or '' (→ even spread)."""
    hay = _norm(narration)
    say = _norm(step.get("say", ""))
    if say and say in hay:
        return step["say"]
    words = narration.split()
    plain = [_norm(w) for w in words]
    # The model's phrase is not there: look for the step's own content words instead.
    for token in _norm(step.get("show", "")).split():
        if len(token) >= 4 and token in plain:
            i = plain.index(token)
            return " ".join(words[i:i + 3])
    return ""


# The maths-string helpers live in lessonforge.mathfix (the transpiler needs them without importing this module);
# the names stay available here for the callers and tests that use writer.mathify and friends.
from ..mathfix import (_GREEK_WORDS, _MATH_WORDS, _SHORT_WORDS, _UNICODE_MATH, _UNIT, _UNITS, _WORD_RUN,  # noqa: E402,F401
                       latex_symbols, mathify, sanitize_math, units_upright)


def one_line_math(show: str) -> str:
    """A formula step is ONE line. Environments and line breaks are cut down to the first line.

    A model wrote a three-line ``\\begin{aligned}`` block into one step; it did not
    compile, fell back to raw markup as text and was shrunk until nobody could read it.
    """
    text = re.sub(r"\\(?:begin|end)\{[A-Za-z*]+\}", " ", show).replace("&", " ")
    text = latex_symbols(text)
    first = re.split(r"\\\\", text)[0]
    # "12 = 2 x 2 x 3": the letter x between numbers is a multiplication sign, not a variable.
    first = re.sub(r"(?<=\d)\s*[x×]\s*(?=[\d(])", r" \\times ", first)
    first = re.sub(r"\s+", " ", first).strip() or show
    return chemistry_upright(first)


_ELEMENTS = set("""H He Li Be B C N O F Ne Na Mg Al Si P S Cl Ar K Ca Sc Ti V Cr Mn Fe Co Ni Cu Zn Ga Ge As Se Br
Kr Rb Sr Y Zr Nb Mo Tc Ru Rh Pd Ag Cd In Sn Sb Te I Xe Cs Ba La Ce Pr Nd Pm Sm Eu Gd Tb Dy Ho Er Tm Yb Lu Hf Ta W Re
Os Ir Pt Au Hg Tl Pb Bi Po At Rn Fr Ra Ac Th Pa U Np Pu Am""".split())


def chemistry_upright(show: str) -> str:
    """A chemical equation in a formula step is set upright: "2H_2 + O_2 \\rightarrow 2H_2O" drew H and O in maths
    italics, as if they were unknowns (balancing-equations video, 2026-10-20). Only a line with a reaction arrow that
    code reads as an equation (``figure_math.parse_equation``) is rewritten, from that reading; anything else
    (x + y = z, V = IR) is returned unchanged. An atom count ("4 H + 2 O = 4 H + 2 O") is read the same way."""
    arrow = bool(re.search(r"->|→|\\(?:long)?rightarrow\b|\\to\b", show))
    if not arrow and not ("=" in show and "+" in show):    # V = IR is physics, not a count
        return show
    from ..longform import figure_math
    try:
        parsed = figure_math.parse_equation(show)
    except (ValueError, KeyError, TypeError):
        return show
    if any(el not in _ELEMENTS for part in ("left", "right") for sp in parsed[part] for el, _ in sp["atoms"]):
        return show                                    # "R" is a resistance, not an element
    side = lambda part: " + ".join(figure_math.formula_latex(sp) for sp in parsed[part])  # noqa: E731
    return side("left") + (r" \rightarrow " if arrow else " = ") + side("right")


_ONES = ("zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen "
         "seventeen eighteen nineteen").split()
_TENS = "zero ten twenty thirty forty fifty sixty seventy eighty ninety".split()


def number_words(n: int) -> str:
    """An integer as it is said in an Indian English-medium class: 1764 → one thousand seven hundred sixty-four."""
    if n < 0:
        return "minus " + number_words(-n)
    if n < 20:
        return _ONES[n]
    if n < 100:
        return _TENS[n // 10] + ("-" + _ONES[n % 10] if n % 10 else "")
    if n < 1000:
        return _ONES[n // 100] + " hundred" + (" " + number_words(n % 100) if n % 100 else "")
    for size, name in ((10 ** 7, "crore"), (10 ** 5, "lakh"), (1000, "thousand")):
        if n >= size:
            return number_words(n // size) + " " + name + (" " + number_words(n % size) if n % size else "")
    return str(n)


_UNITS = {"cm": "centimetres", "mm": "millimetres", "km": "kilometres", "kg": "kilograms", "ml": "millilitres",
          "m": "metres", "g": "grams", "l": "litres"}
_ORDINALS = {1: "first", 2: "second", 3: "third", 5: "fifth", 8: "eighth", 9: "ninth", 12: "twelfth"}


def _ordinal(n: int) -> str:
    """5 → fifth, 21 → twenty-first, 40 → fortieth."""
    if n in _ORDINALS:
        return _ORDINALS[n]
    if n > 20 and n % 10 and n < 100:
        return number_words(n - n % 10) + "-" + _ordinal(n % 10)
    words = number_words(n)
    return words[:-1] + "ieth" if words.endswith("y") else words + "th"


def speakable(text: str, language: str = "en-IN") -> str:
    """Narration a voice can read: digits and maths symbols become the words for them.

    The rule is in every prompt, and a reviewer's rewrite still produced "1800 = 2 x 900,
    phir 900 = 2 x 450" for a Hinglish lesson (2026-10-08). The voice reads that however it
    likes — in Hindi, or skipping the symbols. This is the backstop: whatever reaches the
    voice has no digits and no symbols in it.
    """
    if not re.search(r"[\d=+×÷%^°₹$]", text):
        return _spoken_units(text)
    hindi = str(language).lower() in ("hinglish", "hi-in")
    times = " into " if hindi else " times "
    # A compound unit first, before "/" between letters is read as "by" ("m/s" was "metres/s").
    t = re.sub(r"(?<=\d)\s*(m/s²|m/s\^2|m/s2|m/s|km/h|kmph)(?![A-Za-z0-9])", lambda m: " " + _UNIT_WORDS[m.group(1)], text)
    t = re.sub(r"(?<=\d)\s*[x×*]\s*(?=\d)", times, t)
    t = re.sub(r"(?<=\d)\s*÷\s*(?=\d)|(?<=\d)\s*/\s*(?=\d)", " by ", t)
    # Algebra (2026-10-16, the first Lesson Forge lessons): "3x + 5 = 14" was spoken "threex + five equals fourteen",
    # since a coefficient ran into its letter and only a + or - between two DIGITS was put into words.
    t = re.sub(r"₹\s*(\d[\d,]*(?:\.\d+)?)", r"\1 rupees", t)
    t = re.sub(r"\$\s*(\d[\d,]*(?:\.\d+)?)", r"\1 dollars", t)
    t = re.sub(r"(?<=\d)\s*°\s*C\b", " degrees Celsius", t)
    t = re.sub(r"\s*°", " degrees", t)
    t = re.sub(r"\b(\d+)(st|nd|rd|th)\b", lambda m: _ordinal(int(m.group(1))), t)
    t = re.sub(r"(?<=\d)\s*(cm|mm|km|kg|ml|m|g|l)\b(?![²³^])", lambda m: " " + _UNITS[m.group(1)], t)
    t = re.sub(r"(?<![A-Za-z\d])(\d+(?:\.\d+)?)([a-z])(?![A-Za-z])", r"\1 \2", t)   # 3x → 3 x
    t = re.sub(r"(?<=\d)\s*\(", times.rstrip() + " (", t)                         # 2(x - 3) → 2 times (x - 3)
    t = re.sub(r"\)\s*\(", ")" + times + "(", t)
    t = re.sub(r"\)(?=[a-z\d])", ") ", t)
    t = re.sub(r"\s*=\s*", " equals ", t)
    operand = r"[\dA-Za-z)²³]"
    t = re.sub(rf"(?<={operand})\s*\+\s*(?=[\dA-Za-z(])", " plus ", t)
    t = re.sub(rf"(?<={operand})\s+[-−]\s+(?=[\dA-Za-z(])", " minus ", t)
    t = re.sub(r"(?:(?<=^)|(?<=[\s(]))[-−](?=\d|[a-z](?![a-z])|\()", "minus ", t)       # a negative: -3, -x
    t = re.sub(r"(?<=\b[a-z])\s*/\s*(?=[a-z\d]\b)", " by ", t)                     # a/b → a by b
    t = re.sub(r"(?<=\d)\s*%", " percent", t)
    t = re.sub(r"\^\s*2\b", " squared", t)      # after the operators, which look for a digit beside them
    t = re.sub(r"\^\s*3\b", " cubed", t)

    def spoken(match):
        whole, _, fraction = match.group(0).replace(",", "").partition(".")
        words = number_words(int(whole)) if len(whole) <= 9 else " ".join(_ONES[int(d)] for d in whole)
        return words + (" point " + " ".join(_ONES[int(d)] for d in fraction) if fraction else "")

    t = re.sub(r"\d{1,3}(?:,\d{2,3})+(?:\.\d+)?|\d+(?:\.\d+)?", spoken, t)
    return _spoken_units(re.sub(r"\s+", " ", t).strip())


#: Unit symbols a voice reads as letters ("twenty N" was heard "twenty en", 2026-10-19), said after a number. Only
#: case-sensitive symbols that are not words: "m", "g", "s" alone are left to the digit rule above, where a digit
#: before them makes them certain.
_UNIT_WORDS = {"N": "newtons", "J": "joules", "W": "watts", "Pa": "pascals", "Hz": "hertz", "kg": "kilograms",
               "cm": "centimetres", "mm": "millimetres", "km": "kilometres", "ml": "millilitres",
               "m/s²": "metres per second squared", "m/s^2": "metres per second squared", "m/s2": "metres per second squared",
               "m/s": "metres per second", "km/h": "kilometres per hour", "kmph": "kilometres per hour"}
_NUMBER_WORD = (r"(?:zero|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|\w+teen|\w+ty"
                r"|hundred|thousand|lakh|crore|\w+-(?:one|two|three|four|five|six|seven|eight|nine))")
_UNIT_AFTER_WORDS = re.compile(rf"\b({_NUMBER_WORD})\s+("
                               + "|".join(re.escape(u) for u in sorted(_UNIT_WORDS, key=len, reverse=True))
                               + r")(?![A-Za-z0-9²^])")


def _spoken_units(text: str) -> str:
    """A unit symbol after a number in words becomes its name; after exactly "one", its singular ("one kilogram")."""
    def name(match):
        number, unit = match.group(1), _UNIT_WORDS[match.group(2)]
        if number.lower() == "one" and not text[:match.start()].rstrip().endswith("point"):
            unit = unit.replace("metres per", "metre per").replace("kilometres per", "kilometre per") \
                if " per " in unit else (unit[:-1] if unit.endswith("s") and unit != "hertz" else unit)
        return f"{number} {unit}"
    text = _UNIT_AFTER_WORDS.sub(name, text)
    # "one kilograms": a unit already spelled out, after exactly one
    return re.sub(r"(?<![\w-])(?<!point )\b(one) (kilogram|gram|metre|centimetre|millimetre|kilometre|litre|millilitre|"
                  r"newton|joule|watt|second|minute|hour|degree)s\b(?! per)|(?<![\w-])(?<!point )\b(one) (metre|kilometre)s per\b",
                  lambda m: f"{m.group(1)} {m.group(2)}" if m.group(1) else f"{m.group(3)} {m.group(4)} per", text)


def _respellings(raw: dict) -> list[tuple[str, str]]:
    """(phonetic respelling, term) pairs from a glossary that carried ``say_it_as`` hints."""
    pairs = []
    for entry in raw.get("glossary") or []:
        if isinstance(entry, dict) and entry.get("say_it_as") and entry.get("term"):
            hint, term = str(entry["say_it_as"]).strip(), str(entry["term"]).strip()
            if hint.lower() != term.lower():
                pairs.append((hint, term))
    return pairs


def _plain(text: str, respellings: list[tuple[str, str]]) -> str:
    """Put the real word back wherever a respelling leaked into text meant for captions or the screen."""
    for hint, term in respellings:
        text = re.sub(re.escape(hint), term, text, flags=re.I)
    return text


DEPTHS = ("basics", "core", "practice", "extra")
#: What a beat is for when the model did not say: by the job of its chapter.
ROLE_DEPTH = {"activate": "basics", "concrete": "basics", "explore": "basics", "hook": "core", "claim": "core",
              "idea": "core", "name": "core", "example": "core", "model": "core", "proof": "core", "recap": "core",
              "problem": "practice", "faded": "practice", "practice": "practice", "transfer": "practice",
              "refutation": "extra", "conflict": "extra", "pitfall": "extra", "limits": "extra"}


def beat_depth(beat: dict, role: str) -> str:
    """Who a beat is for. The model proposes; the chapter's job decides what may count as core.

    On the first real run the writer marked 12 of 18 beats "core", so a "quick revision"
    would have been two thirds of the lesson. Only chapters whose job IS the core (the
    hook, the idea, the worked example, the proof, the recap) may hold core beats; a
    beat in a warm-up, practice or enrichment chapter keeps that chapter's depth.
    """
    proposed = str(beat.get("depth") or "").lower()
    by_role = ROLE_DEPTH.get(role, "core")
    if proposed not in DEPTHS:
        return by_role
    if proposed == "core" and by_role != "core":
        return by_role
    return proposed


def clean_quiz(raw, respellings=()) -> dict | None:
    """A multiple-choice question for a thinking pause: 2–4 short options, exactly one right."""
    if not isinstance(raw, dict):
        return None
    question = re.sub(r"\s+", " ", _plain(str(raw.get("question") or ""), list(respellings))).strip()[:140]
    given = raw.get("options") or []
    kept = [n for n, o in enumerate(given) if str(o).strip()][:4]
    options = [re.sub(r"\s+", " ", _plain(str(given[n]), list(respellings))).strip()[:60] for n in kept]
    try:
        answer = int(raw.get("answer_index"))
    except (TypeError, ValueError):
        return None
    if not question or len(options) < 2 or not 0 <= answer < len(options) or len(set(options)) < len(options):
        return None
    out = {"question": question, "options": options, "answer_index": answer,
           "explain": re.sub(r"\s+", " ", str(raw.get("explain") or "")).strip()[:160]}
    # "why": what a learner who picks each option is told (harness/questions.py writes it; one line per option, in the
    # options' order). Kept only when every option has its own: half a list would put a reason under the wrong choice.
    reasons = raw.get("why")
    if isinstance(reasons, list) and len(reasons) == len(given):
        why = [re.sub(r"\s+", " ", _plain(str(reasons[n] or ""), list(respellings))).strip()[:160] for n in kept]
        if all(why):
            out["why"] = why
    return out


def open_with_something(beat: dict) -> bool:
    """No beat opens on an empty screen. Returns True when the first step was brought forward.

    A step appears when its ``say`` words are spoken. When every step of a beat is anchored
    late and the beat has no figure, the screen shows only the title until then: frame
    reviews of seven lessons found it "empty … while the narrator is asking", once for
    most of a 32-second beat whose three steps were all tied to its last sentence. The
    first step then comes in with the beat's opening words instead.
    """
    steps = beat.get("steps") or []
    if beat.get("figure") or not steps or not steps[0].get("say"):
        return False                      # a picture is up, or the step is already spread from the start
    words = beat["narration"].split()
    at = _norm(beat["narration"]).find(_norm(steps[0]["say"]))
    before = len(_norm(beat["narration"])[:max(0, at)].split())
    if at < 0 or before <= max(6, len(words) // 4):
        return False
    steps[0]["say"] = " ".join(words[:3])
    return True


def discipline(raw: dict, brief: dict, framework: dict, split_long: bool = False) -> dict:
    """Model output → a structurally safe lesson dict (ids, anchors, clamps). Never raises on content.

    ``split_long``: a sentence of a model's script over ``voice.LONG_SENTENCE_WORDS`` words is cut at its clause
    boundaries (``voice.split_long``). Never for a person's own words (a pasted script, an edit by hand)."""
    chapters = []
    beat_number = 0
    respellings = _respellings(raw)
    for index, chapter in enumerate(raw.get("chapters") or [], start=1):
        stage = framework["stages"][min(index, len(framework["stages"])) - 1]
        beats = []
        for beat in chapter.get("beats") or []:
            narration = re.sub(r"\s+", " ", re.sub(r"\[[^\]]*\]|[*_#`]", " ", str(beat.get("narration", "")))).strip()
            narration = speakable(_plain(narration, respellings), brief.get("language", "en-IN"))
            if split_long:
                narration = voice.split_long(narration)
            if not narration:
                continue
            beat_number += 1
            steps, highlights = [], 0
            for step in (beat.get("steps") or [])[:MAX_STEPS]:
                show = _plain(str(step.get("show", "")).strip(), respellings)
                if not show:
                    continue
                kind = step.get("kind") if step.get("kind") in ("point", "key", "math") else "point"
                # Models write LaTeX into "point" steps (measured: \text{Wall height} = 4\text{ m});
                # a Pango text object would show the backslashes, so route it to MathTex.
                if kind != "math" and _MATH_MARKERS.search(show):
                    kind = "math"
                if kind == "math":
                    show = mathify(one_line_math(show))
                show = shown(show, kind)
                if not show:
                    continue                    # it was a note about the screen (shown): nothing to put on it
                highlight = bool(step.get("highlight")) and highlights < MAX_HIGHLIGHTS
                highlights += highlight
                entry_step = {"say": _anchor_step(step, narration), "show": show, "kind": kind,
                              "highlight": highlight}
                focus = re.sub(r"[^a-z0-9_]", "", str(step.get("focus") or "").lower())[:24]
                if focus:
                    entry_step["focus"] = focus
                steps.append(entry_step)
            pause = beat.get("thinking_pause_seconds") or 0
            try:
                pause = max(0.0, min(8.0, float(pause)))
            except (TypeError, ValueError):
                pause = 0.0
            entry = {
                "id": f"{beat_number:02}", "narration": narration, "visual": str(beat.get("visual", "")),
                "board_text": next((s["show"] for s in steps if s["kind"] != "math"), ""),
                "equation": next((s["show"] for s in steps if s["kind"] == "math"), ""),
                "thinking_pause_seconds": pause, "check": str(beat.get("check", "")), "steps": steps,
            }
            entry["depth"] = beat_depth(beat, stage["role"])
            quiz = clean_quiz(beat.get("quiz"), respellings)
            if quiz:
                entry["quiz"] = quiz
                if not entry["thinking_pause_seconds"]:
                    entry["thinking_pause_seconds"] = 5.0     # a question nobody is given time for is not one
            elif not entry["thinking_pause_seconds"] and narration.rstrip().endswith(("?", "?\"", "?”")):
                # A beat that ENDS by asking, answered at once by the next: three such beats in one
                # lesson were each a major finding. The learner gets a moment to answer it.
                entry["thinking_pause_seconds"] = 3.0
            figure = beat.get("figure")
            if isinstance(figure, dict) and figure.get("kind") == "scene":
                described = re.sub(r"\s+", " ", str(figure.get("describe") or "")).strip()[:400]
                figure = {"kind": "scene", "describe": described} if len(described) >= 16 else None
            if isinstance(figure, dict) and figure.get("kind") == "graph":
                figure = figure_math.settle_graph(figure)[0]      # a point is put back ON its line
            if isinstance(figure, dict) and figure.get("kind") == "reaction":
                figure = reaction_figure(figure)                  # an equation code cannot read is no picture
            kit = kits.serving(figure.get("kind")) if isinstance(figure, dict) else None
            if kit is not None:                                   # a subject kit's figure it cannot solve is no picture
                figure = kits.guarded(f"{kit.name} normalise_figure", lambda: kit.normalise_figure(figure), figure)
            if isinstance(figure, dict) and figure.get("kind") in FIGURE_KINDS + PREPARED_KINDS + IMPORTED_KINDS + kits.kinds():
                entry["figure"] = figure
                issues = figure_math.figure_issues(figure)
                if issues:                      # the drawing follows the labels; the critic reports this
                    entry["figure_issues"] = issues
            open_with_something(entry)
            beats.append(entry)
        if beats:
            entry = {"id": len(chapters) + 1, "title": str(chapter.get("title") or stage["title"]).upper()[:60],
                     "learning_goal": str(chapter.get("learning_goal") or stage["job"]), "role": stage["role"],
                     "beats": beats}
            if chapter.get("_continuity"):
                entry["continuity"] = chapter["_continuity"]
            chapters.append(entry)
    if not chapters:
        raise ValueError("the model returned no usable chapters")
    return {
        "title": str(raw.get("title") or brief.get("topic") or "Lesson")[:90],
        "thesis": str(raw.get("thesis") or brief.get("goal") or ""),
        "language": {"hinglish": "hi-IN"}.get(brief.get("language", "en-IN"), brief.get("language", "en-IN")),
        "anchor": str(raw.get("anchor") or brief.get("context") or ""),
        "anchor_name": str(raw.get("anchor_name") or "").strip()[:40],
        "small_case": str(raw.get("small_case") or "").strip()[:160],
        "method": [str(m).strip()[:160] for m in (raw.get("method") or []) if str(m).strip()][:8],
        "glossary": raw.get("glossary") or [],
        "framework": framework["id"],
        "brief": brief,
        "chapters": chapters,
    }


_NUMBER_WORD = (r"(?:zero|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|"
                r"sixteen|seventeen|eighteen|nineteen|twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety|hundred|"
                r"thousand|lakh|million|and)")
_LONG_NUMBER = re.compile(rf"\b{_NUMBER_WORD}(?:[ -]{_NUMBER_WORD}){{3,}}\b|\b\d{{4,}}\b", re.I)


def long_number_mentions(lesson: dict) -> dict[str, list[str]]:
    """Every long number spoken in full (four words or four digits and up) → the beats that say it.

    "One thousand seven hundred sixty-four" takes three seconds to say; one lesson said
    it sixteen times, about fifty seconds of an eight-minute video.
    """
    found: dict[str, list[str]] = {}
    for chapter in lesson["chapters"]:
        for beat in chapter["beats"]:
            for match in _LONG_NUMBER.finditer(beat["narration"]):
                phrase = re.sub(r"\s+and$", "", re.sub(r"[ -]+", " ", match.group(0).lower()).strip())
                found.setdefault(phrase, []).append(beat["id"])
    return found


_NUMBER_WORDS = set(_NUMBER_WORD[3:-1].split("|"))
_PLAIN_WORDS = {"with", "into", "from", "them", "that", "this", "these", "those", "wants", "have", "each", "equal", "same",
                "number", "numbers", "when", "then", "uses", "needs", "make", "made", "more", "less", "than", "there",
                "which", "what", "their", "they", "will", "must", "only", "every", "other"}


def _words(text: str) -> list[str]:
    return _norm(str(text).replace("-", " ")).split()


def _example_words(lesson: dict) -> set[str]:
    """The example's own words: content words of the anchor that are not numbers or glossary terms."""
    terms = {w for g in lesson.get("glossary") or [] if isinstance(g, dict) for w in _words(g.get("term", ""))}
    return {w for w in _words(lesson.get("anchor", ""))
            if len(w) >= 4 and not w.isdigit() and w not in _NUMBER_WORDS and w not in terms and w not in _PLAIN_WORDS}


def describes_example(lesson: dict, chapter: dict) -> bool:
    """Whether the chapter sets the example's scene: one sentence carrying a good part of its own words."""
    words = _example_words(lesson)
    need = max(3, -(-len(words) * 2 // 5))          # three words, or two fifths of a long example
    if len(words) < 3:
        return False
    for beat in chapter["beats"]:
        for sentence in re.split(r"(?<=[.!?।])\s+", beat["narration"]):
            if len(words & set(_words(sentence))) >= need:
                return True
    return False


def continuity(lesson: dict) -> dict:
    """How well the lesson holds together — measured here; the critic's gates act on it."""
    chapters = lesson["chapters"]
    spoken = [" ".join(b["narration"] for b in c["beats"]) for c in chapters]
    anchor_words = [w for w in _norm(lesson.get("anchor", "")).split() if len(w) >= 4]
    with_anchor = sum(1 for text in spoken if any(w in _norm(text) for w in anchor_words)) if anchor_words else 0
    topic_words = [w for w in _norm(lesson.get("brief", {}).get("topic", "")).split() if len(w) >= 4]
    cold = []
    for chapter, text in list(zip(chapters, spoken))[1:]:
        opening = _norm(" ".join(text.split()[:14]))
        if re.search(r"\b(welcome|hello|namaste|in this (video|lesson)|today we)\b", opening) or \
                (topic_words and all(w in opening for w in topic_words)):
            cold.append(chapter["id"])
    anchors = [s for c in chapters for b in c["beats"] for s in b["steps"]]
    warnings = []
    # Cross-chapter repetition: a 5-word phrase said in two different chapters is a
    # restatement (measured on the first real run: "many students simply add three"
    # opened the known mistake in chapters 1 and 3 before chapter 5, whose job it was).
    # Paraphrases escape this; the critic's clarity score is the softer net.
    n = 5
    grams: dict[str, set] = {}
    for c, text in zip(chapters, spoken):
        toks = _norm(text).split()
        for i in range(len(toks) - n + 1):
            grams.setdefault(" ".join(toks[i:i + n]), set()).add(c["id"])
    repeated = sorted({g for g, ids in grams.items() if len(ids) > 1})
    repeated_phrases = []
    for g in repeated:  # collapse overlapping n-grams into readable phrases
        if repeated_phrases and g.split()[:-1] == repeated_phrases[-1].split()[-(n - 1):]:
            repeated_phrases[-1] += " " + g.split()[-1]
        else:
            repeated_phrases.append(g)
    words = sum(len(b["narration"].split()) for c in chapters for b in c["beats"])
    minutes = int(lesson.get("brief", {}).get("duration_minutes") or 0)
    target = word_budget(minutes) if minutes else 0
    if target and not 0.7 <= words / target <= 1.15:
        pauses = sum(float(b.get("thinking_pause_seconds") or 0) for c in chapters for b in c["beats"])
        warnings.append(f"Length: {words} spoken words against a budget of {target} ({words / target:.0%}); "
                        f"the video will run about {(words / WORDS_PER_MINUTE * 60 + pauses) / 60:.1f} min, "
                        f"not {minutes}.")
    # How often the example is DESCRIBED (not merely used): chapters holding a sentence
    # with most of the example's own words. More than one is the same scene set again.
    described = [c["id"] for c in chapters if describes_example(lesson, c)]
    if len(described) > 1:
        warnings.append(f"The example is described again in chapter(s) {described[1:]} after chapter {described[0]}.")
    spoken_numbers = long_number_mentions(lesson)
    worst = max(spoken_numbers.items(), key=lambda kv: len(kv[1]), default=None)
    if worst and len(worst[1]) > 3:
        warnings.append(f"“{worst[0]}” is spoken in full {len(worst[1])} times.")
    if not anchor_words and lesson.get("framework") != "script":      # a pasted script owes nobody an example
        warnings.append("No running example was named.")
    if cold:
        warnings.append(f"Chapter(s) {cold} open by re-introducing the topic instead of continuing.")
    if len(repeated_phrases) > 2:
        warnings.append(f"{len(repeated_phrases)} phrase(s) are repeated across chapters, e.g. “{repeated_phrases[0]}”.")
    declared = [c.get("continuity") for c in chapters if c.get("continuity")]
    unexplained = [u for c in declared for u in c.get("unexplained_references", [])]
    if unexplained:
        warnings.append(f"{len(unexplained)} reference(s) to things no earlier chapter established, e.g. “{unexplained[0][:60]}”.")
    return {
        "chapters": len(chapters),
        "words": words,
        "target_words": target,
        "cross_chapter_repeats": len(repeated_phrases),
        "repeated_phrases": repeated_phrases[:8],
        "chapters_declaring_example_step": sum(1 for c in declared if c.get("running_example_step")),
        "unexplained_references": unexplained[:8],
        "chapters_using_running_example": with_anchor,
        "chapters_describing_example": described,
        "long_number_mentions": {phrase: len(beats) for phrase, beats in spoken_numbers.items() if len(beats) > 1},
        "cold_opens": cold,
        "steps": len(anchors),
        "steps_anchored_to_speech": sum(1 for s in anchors if s["say"]),
        "highlights": sum(1 for s in anchors if s["highlight"]),
        "warnings": warnings,
    }


#: The first stage of these roles is where the example is described; every other chapter only names it.
EXAMPLE_ROLES = ("concrete", "hook", "problem")


def example_stage(framework: dict) -> int:
    """Index of the stage that introduces the example."""
    return next((i for i, s in enumerate(framework["stages"]) if s["role"] in EXAMPLE_ROLES), 0)


#: Which stage of each framework carries a line of the teaching card (``card.py``). No
#: chapter is added for the card: its WHY becomes a required beat of the stage that
#: states the idea, its opening question is answered where the example is worked, and
#: its try-it task is set where practice ends.
WHY_ROLES = ("name", "idea", "proof", "explain")
ANSWER_ROLES = ("model", "example", "proof", "explain")
TASK_ROLES = ("practice", "faded", "transfer", "check")


def card_notes(card: dict, index: int, stage: dict, owns_mistake: bool = False, picture: str = "") -> str:
    """What the teaching card asks of ONE chapter, on top of its stage's job.

    ``picture`` is what the previous chapter left on screen. The first four pilot lessons
    each swapped to a new object mid-way (trays, then a ladder; two strips redrawn): every
    chapter was handed the words said so far and never the picture, so it could not
    continue one. The task and mistake notes say more than they first did for the same
    reason: read on four real lessons, the task's answer was given away in two and the
    mistake was shown failing in one (06_plan_checks_and_additions.md).
    """
    notes = []
    task = card["try_it"]
    if index == 0:
        notes.append("OPEN THE LESSON with the card's opening question in a SHORT beat of its own (about 20 spoken words: "
                     "shorter than a usual beat, and taken out of this chapter's share of words, so the chapter does not "
                     "grow): one or two sentences that set the scene, then the question as that beat's LAST sentence. "
                     "Nothing is said after the question in that beat. It asks the learner to commit to a guess and it is NOT answered in this chapter. Give that beat "
                     "thinking_pause_seconds 4 and no quiz (nothing is revealed yet). This chapter's own job starts in the "
                     "NEXT beat. Never open with a definition or with what the lesson will cover.")
    if stage["role"] in WHY_ROLES and card["the_why"]["text"]:
        notes.append("THIS CHAPTER OWNS THE WHY. Put it to the learner as a question that is the LAST sentence of a beat "
                     "(the pause belongs to that beat, and a pause never follows a statement), then say it in the next beat "
                     f"in one or two sentences with a joining word (because, so), while the picture shows it happening: {card['the_why']['text']}")
    if stage["role"] in ANSWER_ROLES and card["opening_question"]["question"]:
        notes.append("Once the working is done, answer the lesson's OPENING QUESTION by name, in one sentence.")
    if stage["role"] in TASK_ROLES and task["steps"]:
        notes.append("The LAST beat of this chapter sets the try-it task and does nothing else, in two or three spoken "
                     "sentences (about 25 words, taken out of this chapter's share: a chapter with two beats has the same "
                     "words in all as a chapter with one), said as a picture the learner imagines, never as a list of "
                     f"orders: picture yourself doing it with {', '.join(task['materials']) or 'paper and pencil'}; ask "
                     f"what they think will happen ({task['predict']}) as the beat's ONLY question; and say what to notice "
                     f"once they try it ({task['question']}) as a plain statement, never a second question. "
                     "The lesson NEVER says the task's result, sum or reason, here or later, and never works the task's own "
                     "numbers on screen: this chapter's practice uses a DIFFERENT case from the task's. Do not mention an "
                     "app or a card.")
    if owns_mistake and card["mistakes"]:
        first = card["mistakes"][0]
        notes.append(f"MEET THE MISTAKE HERE: say it the way a learner would say it (“{first['mistake']}”), carry it out on "
                     f"one case on screen, and let the result fail in front of them ({first['why_it_fails']}). A warning "
                     "about the mistake is not enough: it must be seen to go wrong. If this chapter stops to ask, it asks "
                     "BEFORE it corrects (a short question about the thing itself, which a learner holding the mistake gets wrong) and corrects in the "
                     "beat after the pause.")
    if stage["role"] == "recap" and card.get("objectives"):
        notes.append("THE RECAP has the learner DO each of these, one short question or prompt each, without explaining "
                     "anything again: " + "; ".join(o["can"] for o in card["objectives"])
                     + ". The beat that stops ends on its question and has not said the answer; the answer is the next "
                     "beat's first sentence, or the lesson's last one.")
    if picture:
        notes.append("THE PICTURE ON SCREEN WHEN THIS CHAPTER STARTS — continue it: the same objects in the same places, "
                     "changed only as far as this chapter's idea changes them. Bring in a different object only if the card's "
                     f"route asks for one. It is: {picture}")
    notes.append("Any quiz in this chapter takes its wrong options from the card's WHERE LEARNERS GO WRONG: each wrong option "
                 "is the short answer that mistake leads to (one to three words, never the mistake written out).")
    if index and stage["role"] != "recap" and card["opening_question"]["question"]:
        # Read on the first diagram lesson: the opening question was asked at 0:00, again at 0:37 as that
        # chapter's question card, and twice more in other words. Each chapter was told to stop and ask
        # and was never told the lesson already had its question.
        notes.append("ASK ONCE: the lesson's opening question was asked in chapter 1. Do not ask it again here in any "
                     "wording and do not make it this chapter's question card. A question in this chapter is about what "
                     "THIS chapter shows.")
    # Read on the first script written with the voice rules: 8 stops in 14 beats, two of them in the practice
    # chapter and two in the recap. The rule "about once a minute" was meant per chapter at most.
    notes.append("ONE STOP AT MOST: at most one beat of this chapter has thinking_pause_seconds. Any other question in "
                 "the chapter is answered in the same beat, so it is never a beat's last sentence.")
    notes.append("TITLE: two to five plain words naming what this chapter shows (“One cell, many jobs”, “The boundary”, "
                 "“Pairs make a square”), never the stage's name, and not built like the title before it.")
    return "\n".join(f"THE CARD ASKS OF THIS CHAPTER — {n}" for n in notes)


def use_diagram(lesson: dict, card: dict | None, log=print) -> dict:
    """Make every ``diagram`` figure the one the card prepared, and keep only focuses it can show.

    The model writes ``{"kind": "diagram"}`` and names parts in ``focus``; code supplies the
    manifest, checks each name against the diagram's own (a name it does not have is
    dropped, not guessed at) and lists the names the lesson uses, so only those labels are
    drawn. With no prepared diagram the figure is removed: a beat with no picture is
    better than a kind the renderer cannot build.
    """
    ready = (card or {}).get("diagram") or {}
    known = {str(p).replace("_", ""): p for p in ready.get("parts") or []}
    # A step that NAMES a part is pointing at it, whether or not the model wrote a focus. In the
    # first real lesson with a diagram the steps "Mitochondria: usable energy" and "Membrane:
    # exchange" carried none, and the picture sat unchanged through the second half. A word
    # counts when it belongs to one part's name only ("reticulum" is in two, so it needs
    # "rough" or "smooth" beside it, as the full name).
    names = {slug_: str(name).lower() for slug_, name in (ready.get("names") or {}).items() if slug_ in (ready.get("parts") or [])}
    owners: dict[str, set] = {}
    for slug_, name in names.items():
        for word in re.findall(r"[a-z]{6,}", name):
            owners.setdefault(word, set()).add(slug_)

    def named_in(step: dict) -> str | None:
        text = f"{step.get('show', '')} {step.get('say', '')}".lower()
        whole = [s for s, name in names.items() if name in text]
        if len(whole) == 1:
            return whole[0]
        single = {next(iter(who)) for word, who in owners.items() if len(who) == 1 and re.search(rf"\b{word}\b", text)}
        return single.pop() if len(single) == 1 else None

    used, beats = [], []
    for chapter in lesson["chapters"]:
        for beat in chapter["beats"]:
            if (beat.get("figure") or {}).get("kind") != "diagram":
                continue
            if not known:
                beat.pop("figure", None)
                continue
            beats.append(beat)
            for step in beat.get("steps") or []:
                name = known.get(str(step.get("focus") or "").replace("_", "")) or named_in(step)
                if name and (name in used or len(used) < MAX_DIAGRAM_LABELS):
                    step["focus"] = name
                    if name not in used:
                        used.append(name)
                else:
                    step.pop("focus", None)
    if beats:
        spec = {"kind": "diagram", "manifest": ready["manifest"], "labels": used, "ask": ready.get("ask", "")}
        for beat in beats:
            beat["figure"] = dict(spec)
        if ready.get("credit"):
            lesson["credits"] = [ready["credit"]]
        log(f"[writer] the diagram is used on {len(beats)} beat(s); parts named: {', '.join(used) or 'none'}")
    return lesson


def _panel(focus) -> str:
    """``panel2`` for a focus that asks for a panel (``panel_2``, ``Panel 2``), else ''."""
    found = re.fullmatch(r"panel[_ ]?(\d+)", str(focus or "").strip().lower())
    return f"panel{int(found.group(1))}" if found else ""


def settle_panels(lesson: dict, was: dict | None = None, log=print) -> dict:
    """A drawing shown one panel at a time brings EVERY panel in, or is shown whole from the start.

    A two-panel drawing shows its first panel and brings the second in when a step asks
    (``focus: "panel2"``). In the trial lesson on the area of a triangle (2026-10-10) the
    writer asked at the right step ("Matching copy rotates"); the reviewer's revision wrote
    that beat's steps again without it, and the second panel, the parallelogram that IS the
    proof, never appeared: three and a half minutes beside half a drawing, with ten findings
    from the frame review and no repair that could cure them. So after any rewrite the ask
    is put back on the step that had it in ``was`` (the same anchor words, the same line, or
    the step in the same place); and where no step has ever asked for a panel, the drawing
    is shown whole: half a picture for a whole lesson is worse than a picture seen early.
    """
    earlier = {str(beat.get("id", "")): beat.get("steps") or [] for chapter in (was or {}).get("chapters") or []
               for beat in chapter.get("beats") or []}
    shown: dict[str, list] = {}
    for chapter in lesson.get("chapters") or []:
        for beat in chapter.get("beats") or []:
            figure = beat.get("figure") or {}
            if figure.get("kind") == "picture" and len(figure.get("panels") or []) >= 2 and figure.get("file"):
                shown.setdefault(figure["file"], []).append(beat)
    for beats in shown.values():
        count = max(len(beat["figure"]["panels"]) for beat in beats)
        asked = {_panel(step.get("focus")) for beat in beats for step in beat.get("steps") or []} - {""}
        back, never = [], []
        for name in (f"panel{n}" for n in range(2, count + 1)):
            if name in asked:
                continue
            for beat in beats:
                old, steps = earlier.get(str(beat.get("id", "")), []), beat.get("steps") or []
                k = next((i for i, o in enumerate(old) if _panel(o.get("focus")) == name), None)
                if k is None or not steps:
                    continue
                target = (next((s for s in steps if s.get("say") and s.get("say") == old[k].get("say")), None)
                          or next((s for s in steps if str(s.get("show", "")).lower() == str(old[k].get("show", "")).lower()), None)
                          or steps[min(k, len(steps) - 1)])
                target["focus"] = name                  # bringing the panel in matters more than a mark on a label
                back.append(f"{name} at beat {beat.get('id', '')}")
                break
            else:
                never.append(name)
        if never:
            for beat in beats:
                beat["figure"].pop("panels", None)
                beat["figure"].pop("panel_boxes", None)
                for step in beat.get("steps") or []:
                    if _panel(step.get("focus")):
                        step.pop("focus", None)
            log(f"[writer] no step brings in {', '.join(never)} of the drawing on beat(s) {', '.join(str(b.get('id', '')) for b in beats)}: "
                "it is shown whole from the start")
        elif back:
            log(f"[writer] a rewrite had dropped the step that brings a panel in; put back: {', '.join(back)}")
    return lesson


def _beats(lesson: dict) -> list[dict]:
    return [beat for chapter in lesson.get("chapters") or [] for beat in chapter.get("beats") or []]


def _num_text(x) -> str:
    return f"{x:g}"


def reaction_figure(figure: dict) -> dict | None:
    """A ``reaction`` figure as code will draw it, or None when its equation is not one code can read."""
    equation = re.sub(r"\s+", " ", str(figure.get("equation") or "")).strip()[:160]
    try:
        figure_math.parse_equation(equation)
    except ValueError:
        return None
    out = {"kind": "reaction", "equation": equation}
    if figure.get("counts") is False:
        out["counts"] = False
    if str(figure.get("role") or "") == "wrong":
        out["role"] = "wrong"
    return out


def figure_numbers(figure: dict | None) -> set[str]:
    """The numbers a code-drawn figure SHOWS, as the digits ``annotate.spoken_numbers`` hears them.

    A right triangle shows its two legs and its hypotenuse (worked out when it is a whole number); fraction bars
    show each part's top and bottom number. Other kinds answer an empty set: nothing here may move them.
    """
    figure = figure or {}
    kind, out = figure.get("kind"), set()
    if kind == "right_triangle":
        sides = figure_math.resolve_right_triangle(figure)
        for key in ("a", "b", "c"):
            value = sides.get(key)
            if value and abs(value - round(value)) < 1e-6:
                out.add(_num_text(round(value)))
    elif kind == "reaction":
        try:
            parsed = figure_math.parse_equation(figure.get("equation", ""))
        except ValueError:
            return out
        for side in parsed.values():
            out.update(_num_text(sp["n"]) for sp in side if not sp["unknown"] and sp["n"] > 1)
            if figure.get("counts") is not False:
                out.update(_num_text(n) for n in figure_math.atom_counts(side).values())
    elif kind == "float":
        case = figure_math.float_case(figure)
        out.add(_num_text(case["liquid"]["density"]))
        for obj in case["objects"]:
            for key in ("mass", "volume", "density", "under", "above"):
                if obj.get(key) is not None:
                    out.add(_num_text(obj[key]))
    elif kind == "scene":
        from . import annotate              # annotate imports this module
        out.update(annotate.spoken_numbers(str(figure.get("describe") or "")))
    elif kind == "bars":
        for part in figure.get("parts") or []:
            for key in ("n", "d"):
                value = part.get(key) if isinstance(part, dict) else None
                if isinstance(value, (int, float)):
                    out.add(_num_text(value))
    else:                                                     # a subject kit's figure shows what its model shows
        kit = kits.serving(kind)
        if kit is not None:
            out.update(kits.guarded(f"{kit.name} numbers", lambda: kit.numbers(figure), set()))
    return out


def figures_follow_words(lesson: dict, log=print) -> dict:
    """A beat that SPEAKS the numbers of the next beat's figure shows that figure, not the one before.

    The writer gives each beat a figure, and it gave the change one beat late: in the trigonometry lesson of
    2026-10-16 the voice said "double every side: base six, perpendicular eight" over the 3-4 triangle and the
    6-8 one came a beat later; the frame showed one thing while the voice said another. A beat takes the next
    beat's figure when that figure is the same kind, holds at least two numbers the beat says that its own figure
    lacks, and holds more of what the beat says than its own figure does. A beat that only ASKS about the next
    case (fractions: "two fifths or two ninths?") keeps its figure: the next one would show the answer.
    """
    from . import annotate              # annotate imports this module

    beats, moved = _beats(lesson), []
    for here, after in zip(beats, beats[1:]):
        own, nxt = here.get("figure") or {}, after.get("figure") or {}
        if not own or own.get("kind") != nxt.get("kind") or own == nxt or not figure_numbers(nxt):
            continue
        said = annotate.spoken_numbers(here.get("narration", ""))
        mine, theirs = figure_numbers(own) & said, figure_numbers(nxt) & said
        missing = (said - figure_numbers(own)) & figure_numbers(nxt)
        if len(missing) >= 2 and len(theirs) > len(mine):
            here["figure"] = json.loads(json.dumps(nxt))
            moved.append(f"{here.get('id', '')} ({', '.join(sorted(missing, key=float))})")
    if moved:
        log(f"[writer] the figure follows the words: beat(s) {'; '.join(moved)} take the next beat's figure")
    return lesson


def _canon_numbers(numbers) -> set[str]:
    out = set()
    for n in numbers:
        try:
            out.add(f"{float(n):g}")
        except ValueError:
            pass
    return out - {"1", "2"}          # "one" and "two" are too often plain words


def stale_pictures(lesson: dict) -> list[tuple[dict, dict]]:
    """Beats spoken over a picture made for ANOTHER case: (beat, the figure on screen).

    A figure stays up until another replaces it (``runtime.GuidedChapter``), and the writer often gives a figure only
    to the first beat of a case. In the ice baseline (2026-11-02) the ice cube's "92 cm³ under water" bars stayed up
    for the wooden block (0.60), the dense cube (1.84) and the cork; in the refraction pilot the 60° ray into water
    stayed up while the voice worked a 30° ray into glass. A beat counts when it has no figure of its own, the figure
    on screen shows numbers, and the voice says at least two numbers that picture does not show and more of those than
    of the picture's own (for a scene, which names only some of its numbers: none of them). Beats marked ``"picture": "off"`` show nothing, so they are never stale.
    """
    from . import annotate              # annotate imports this module

    out, on_screen = [], None
    for beat in _beats(lesson):
        if beat.get("figure"):
            on_screen = beat["figure"]
            continue
        if beat.get("picture") == "off" or not on_screen:
            continue
        shows = _canon_numbers(figure_numbers(on_screen))
        said = _canon_numbers(annotate.spoken_numbers(str(beat.get("narration") or "")))
        if not shows or not said:
            continue
        other, same = said - shows, said & shows
        # A scene's sentence names only some of its numbers: a beat working new values ON the same case (the sines of
        # the 60° ray it shows) says one of them, and is not stale. A code-drawn figure shows all of its numbers.
        if len(other) >= 2 and len(other) > len(same) and not (on_screen.get("kind") == "scene" and same):
            out.append((beat, on_screen))
    return out


OWN_PICTURE_CALLS = 4
_OWN_PICTURE_SYSTEM = """You fix ONE beat of an animated lesson. The picture on screen during this beat was drawn for an
earlier case and shows other numbers than the voice says. Write the figure this beat should show instead: the SAME
kind as the picture on screen when it fits, with THIS beat's numbers. Return ONLY JSON: {"figure": {...}}, or
{"figure": null} when no figure kind below fits.
""" + FIGURE_RULES


def own_pictures(lesson: dict, llm=None, log=print) -> dict:
    """Every beat spoken over another case's picture gets a picture of its own, or none (``stale_pictures``).

    One small call per stale run (at most ``OWN_PICTURE_CALLS``) asks for this beat's figure; code keeps it only when
    it is a known kind and shows more of the beat's numbers than the old picture did. A beat still stale after that is
    shown without a picture (``"picture": "off"``): words alone are better than a picture that contradicts them.
    """
    from . import annotate              # annotate imports this module

    stale = stale_pictures(lesson)
    if not stale:
        return lesson
    fixed, dropped, calls = [], [], 0
    while stale and llm is not None and calls < OWN_PICTURE_CALLS:
        beat, old = stale[0]
        calls += 1
        said = _canon_numbers(annotate.spoken_numbers(str(beat.get("narration") or "")))
        try:
            reply = llm(f"PICTURE ON SCREEN NOW: {json.dumps(old, ensure_ascii=False)[:700]}\n\nTHIS BEAT'S NARRATION: "
                        f"{beat.get('narration', '')}\n\nWrite this beat's figure.", _OWN_PICTURE_SYSTEM)
        except Exception as exc:  # noqa: BLE001 - then the beat is shown without the picture, below
            log(f"[writer] own picture for {beat.get('id', '')}: the call failed ({type(exc).__name__})")
            reply = None
        new = reply.get("figure") if isinstance(reply, dict) else None
        good = isinstance(new, dict) and new.get("kind") in FIGURE_KINDS \
            and len(_canon_numbers(figure_numbers(new)) & said) > len(_canon_numbers(figure_numbers(old)) & said)
        if good:
            beat["figure"] = new
            fixed.append(str(beat.get("id", "")))
        else:
            beat["picture"] = "off"
            dropped.append(str(beat.get("id", "")))
        stale = stale_pictures(lesson)
    for beat, _ in stale:                    # no calls left: words alone
        beat["picture"] = "off"
        dropped.append(str(beat.get("id", "")))
    log(f"[writer] pictures from another case: new figure for {', '.join(fixed) or 'none'}; "
        f"shown without a picture: {', '.join(dropped) or 'none'}")
    lesson["own_pictures"] = {"fixed": fixed, "off": dropped, "calls": calls}
    return lesson


_HYPOTENUSE_WORDS = re.compile(r"\b(hypotenuse|longest|third side|slant)\b", re.I)


def found_unknowns(lesson: dict, log=print) -> dict:
    """When the voice states a right triangle's unknown side, the "?" on the drawing becomes that value.

    The renderer replaces a "?" only when a line of working ends on the value AND its step points at the side
    (``runtime.found_value``). The writer wrote "3^2+4^2=25" with no focus and said "the longest side is five":
    the "?" stayed on the hypotenuse for five more beats of a lesson that used the 5 throughout. So: in the beat
    whose words state the worked-out side (a whole number, said in a clause about the hypotenuse), a line of
    working that ends on that value gets the focus, or a short line "c = 5 m" is added at those words; and every
    later beat on the same triangle shows the value instead of "?".
    """
    from . import annotate

    found: dict[tuple, str] = {}
    changes = []
    for beat in _beats(lesson):
        figure = beat.get("figure") or {}
        if figure.get("kind") != "right_triangle":
            continue
        labels = figure.setdefault("labels", {})
        if not isinstance(labels, dict):
            continue
        sides = figure_math.resolve_right_triangle(figure)
        key = (round(sides.get("a", 0), 6), round(sides.get("b", 0), 6))
        if str(labels.get("c", "?")).strip() != "?":
            continue
        if key in found:
            labels["c"] = found[key]
            changes.append(f"{beat.get('id', '')}: shows {found[key]}")
            continue
        c = sides.get("c") or 0
        if not c or abs(c - round(c)) > 1e-6:
            continue
        value = _num_text(round(c))
        narration = str(beat.get("narration", ""))
        clause = next((part.strip() for part in re.split(r"[,.;:?!]", narration)
                       if value in annotate.spoken_numbers(part) and _HYPOTENUSE_WORDS.search(part)), "")
        if not clause:
            continue
        unit = ""
        for other in ("a", "b"):
            match = re.fullmatch(r"\s*[\d.]+\s*([A-Za-z]{1,4})\s*", str(labels.get(other, "")))
            if match:
                unit = match.group(1)
                break
        shown_value = f"{value} {unit}".strip()
        steps = beat.setdefault("steps", [])
        ends_on = re.compile(rf"=\s*{value}(?:\s*(?:\\text\s*)?\{{?\s*[A-Za-z]{{1,4}}\s*\}}?)?\s*$")
        hit = next((step for step in steps if step.get("kind") == "math" and not step.get("focus")
                    and ends_on.search(str(step.get("show", "")).strip())), None)
        if hit is not None:
            hit["focus"] = "c"
        else:
            words = clause.split()
            say = " ".join(words[-6:])
            at = narration.find(say)
            new = {"say": say, "show": units_upright(f"c = {shown_value}"), "kind": "math", "highlight": False,
                   "focus": "c"}
            index = len(steps)
            for k, step in enumerate(steps):
                there = narration.find(str(step.get("say", "")))
                if there > at >= 0:
                    index = k
                    break
            steps.insert(index, new)
        found[key] = shown_value
        changes.append(f"{beat.get('id', '')}: finds {shown_value}")
    if changes:
        log(f"[writer] the unknown side is found where the voice says it: {'; '.join(changes)}")
    return lesson


def scaled_copies(lesson: dict, log=print) -> dict:
    """A right triangle that is a scaled copy of the one before it shows that one inside it, dashed.

    Every triangle is drawn to fill its box, so "double every side" relabelled a drawing of the same size: the
    scaling the voice was explaining could not be seen. The copy's figure now carries ``ghost`` (the earlier
    sides), and the figure draws the earlier triangle at its true relative size in the same corner.
    """
    beats, marked, before = _beats(lesson), [], None
    for beat in beats:
        figure = beat.get("figure") or {}
        if figure.get("kind") != "right_triangle":
            before = None if figure else before
            continue
        sides = figure_math.resolve_right_triangle(figure)
        a, b = sides.get("a") or 0, sides.get("b") or 0
        if before and a and b and before != (a, b):
            ratio = a / before[0]
            if abs(b / before[1] - ratio) < 1e-6 and ratio > 1.05:
                figure["ghost"] = {"a": before[0], "b": before[1]}
                marked.append(f"{beat.get('id', '')} (x{ratio:g})")
                continue                # the earlier triangle stays the one to compare with
        before = (a, b) if a and b else None
    if marked:
        log(f"[writer] a scaled copy shows the triangle it was scaled from: beat(s) {', '.join(marked)}")
    return lesson


def figures_and_words(lesson: dict, log=print) -> dict:
    """The lesson-level passes that make a code-drawn figure agree with what the voice says."""
    for step in (figures_follow_words, found_unknowns, scaled_copies, graph_reveals, quiz_leaks, stage_graphs):
        try:
            step(lesson, log=log)
        except Exception as error:  # noqa: BLE001 - a picture pass never costs a lesson
            log(f"[writer] {step.__name__} stood aside: {error}")
    return lesson


def graph_reveals(lesson: dict, log=print) -> dict:
    """A graph's computed meeting point is shown only once the voice has said it (``"meet": false`` before then).

    ``figures.graph`` marks where two lines cross, with its coordinates, from the first beat that shows the lines. In a
    lesson whose question IS that point ("Reading the Crossing Point of Two Lines", 2026-10-20) the answer stood on
    the screen while the voice asked for it. A point the writer marks itself at the same place carries it instead (the
    frame review saw "(3, 2)" twice)."""
    from .annotate import spoken_numbers  # noqa: PLC0415 - annotate imports this module

    def same(value: float) -> str:
        return format(float(figure_math._nice(value)), "g")

    said: set[str] = set()
    hidden = 0
    for chapter in lesson.get("chapters") or []:
        for beat in chapter.get("beats") or []:
            said |= {format(float(n), "g") for n in spoken_numbers(beat.get("narration", ""))}
            figure = beat.get("figure")
            if not (isinstance(figure, dict) and figure.get("kind") == "graph") or figure.get("meet") is False:
                continue
            facts = figure_math.graph_facts(figure.get("functions") or [], figure.get("x_range") or (-5, 5), figure.get("y_range"))
            meets = facts["meeting_points"]
            if not meets:
                continue
            marked = {same(float(q["x"])) for q in figure.get("points") or [] if isinstance(q, dict) and q.get("x") is not None}
            if all(same(m["x"]) in said and same(m["y"]) in said and same(m["x"]) not in marked for m in meets):
                continue
            beat["figure"] = {**figure, "meet": False}
            hidden += 1
    if hidden:
        log(f"[writer] a graph's meeting point waits for the voice on {hidden} beat(s)")
    return lesson


def quiz_leaks(lesson: dict, log=print) -> dict:
    """A quiz's answer is not on the screen, or said, before it is asked (video-quality plan S4; ``harness/quiz_leaks.py``).

    On a beat that asks a question about a ``motion`` figure the marks that show the answer go into the figure's
    ``hold_marks`` (the graph leaves those points off until the next beat). Anything else that gives the answer away, in
    an earlier beat's words or screen or in the question beat's own, is logged and kept in ``lesson["quiz_leaks"]`` as a
    note for whoever reads the lesson; the words are not rewritten. ``HARNESS_QUIZ_LEAKS=0`` turns the pass off."""
    from .. import knobs  # noqa: PLC0415
    from . import quiz_leaks as leaks  # noqa: PLC0415
    if str(knobs.get("HARNESS_QUIZ_LEAKS", "1")).strip() == "0":
        return lesson
    leaks.hold(lesson, log=log)
    found = [f for f in leaks.find(lesson) if f["kind"] != "figure"]
    if found:
        for f in found:
            log(f"[writer] quiz answer in view: {leaks.describe(f)}")
        lesson["quiz_leaks"] = [leaks.describe(f) for f in found]
    elif "quiz_leaks" in lesson:
        del lesson["quiz_leaks"]
    return lesson


_STEP_TIME = re.compile(r"\b(\d+(?:\.\d+)?)\s*(?:seconds?|secs?|s)\b", re.I)
_STEP_LINE = re.compile(r"\b(?:line|curve|graph|slope|climbs?|steadily)\b", re.I)
_STEP_START = re.compile(r"\b(?:start(?:s|ed|ing)?|begin(?:s|ning)?|leaves?|leaving|set\s+off)\s+(?:at|from|with)\b", re.I)


def stage_graphs(lesson: dict, log=print) -> dict:
    """A motion graph's steps name the part they talk about, so the part is drawn when it is said (video-quality plan S5).

    ``look.staging: steps`` draws a graph's point, label, curve and equation at the step whose ``focus`` names them
    (``runtime._hold_back_steps``). A step the writer left without a focus gets one here when its words clearly name a part:
    "After 3 seconds" is the point at 3 s, "starts at" the point at 0 s, "the line climbs steadily" the curve. A step that
    has a focus keeps it; a point a quiz holds back (``hold_marks``) is named by the FIRST unfocused step of the beat that
    answers it (the next beat with the same graph), which is the answer's cue. Any other figure kind is left alone.
    ``HARNESS_STAGING=whole`` turns the pass off."""
    from .. import knobs  # noqa: PLC0415
    from ..longform import motion_math  # noqa: PLC0415
    if str(knobs.get("HARNESS_STAGING", "steps")).strip() == "whole":
        return lesson
    named, carry = 0, None
    for beat in _beats(lesson):
        figure = beat.get("figure")
        if not (isinstance(figure, dict) and figure.get("kind") == "motion") or not beat.get("steps"):
            carry = None
            continue
        try:
            marks = list(motion_math.solve(figure).marks)
        except Exception:  # noqa: BLE001 - a figure the kit refuses is its own fault
            carry = None
            continue
        held = [float(t) for t in figure.get("hold_marks") or []]
        used = {str(s.get("focus")) for s in beat["steps"] if isinstance(s, dict) and s.get("focus")}
        sig = json.dumps({k: v for k, v in figure.items() if k != "hold_marks"}, sort_keys=True)
        answers = [t for t in (carry[1] if carry and carry[0] == sig and not held else [])]
        for step in beat["steps"]:
            if not isinstance(step, dict) or step.get("focus"):
                continue
            say = str(step.get("say", ""))
            found = _STEP_TIME.search(say)
            name = None
            if answers:                                  # the answer's cue: the mark the question beat held back
                at = next((k for k, m in enumerate(marks) if abs(m - answers[0]) < 1e-6), None)
                answers.pop(0)
                name = f"point{at}" if at is not None else None
            elif found:
                t = float(found.group(1))
                at = next((k for k, m in enumerate(marks) if abs(m - t) < 1e-6), None)
                if at is not None and not any(abs(h - t) < 1e-6 for h in held):
                    name = f"point{at}"
            elif _STEP_START.search(say) and not any(abs(h) < 1e-6 for h in held):
                at = next((k for k, m in enumerate(marks) if abs(m) < 1e-6), None)
                name = f"point{at}" if at is not None else None
            elif _STEP_LINE.search(say):
                name = "curve0"
            if name and name not in used:
                step["focus"] = name
                used.add(name)
                named += 1
        carry = (sig, held) if held else None
    if named:
        log(f"[writer] {named} step(s) on a speed-time graph now name the part they talk about, so it is drawn when said")
    return lesson


def point_again(lesson: dict, log=print, pointer=None, was: dict | None = None) -> dict:
    """After steps were written again: every step on a prepared drawing points at its part once more.

    Call it after ANYTHING that rewrites steps (the reviewer's revision, the screen repair). The first lesson
    written on the owner's drawing by the pipeline alone (2026-10-09) had a focus on every step as written;
    the reviewer's revision and the screen repair then wrote the steps of four of its six beats again without
    one, the repair was counted as better (two findings fewer), and in the video the drawing stood bare, no
    arrows and no names, through the chapters that explain evaporation, condensation and rain. A reviewer of
    frames cannot see a missing focus; so code puts it back, in this order: a focus the drawing has is kept;
    a step takes the focus of the step it replaces in ``was`` (the lesson before the rewrite: the same anchor
    words, the same wording, or the same place when the beat has as many steps as before), because the
    writer, who was told the drawing's names, pointed better than anyone can afterwards; a step whose words
    name a part gets it (``use_diagram``); and the steps still without one are read against the drawing's own
    names by a small model (``diagrams.point_steps``; pass ``pointer=False`` for none). The drawing's
    ``labels`` end up the same on every beat that shows it, so the picture stays.
    """
    earlier = {str(beat.get("id", "")): beat.get("steps") or [] for chapter in (was or {}).get("chapters") or []
               for beat in chapter.get("beats") or []}
    shown: dict[str, list] = {}
    for chapter in lesson.get("chapters") or []:
        for beat in chapter.get("beats") or []:
            figure = beat.get("figure") or {}
            if figure.get("kind") == "diagram" and figure.get("manifest"):
                shown.setdefault(figure["manifest"], []).append(beat)
    for manifest, beats in shown.items():
        ready = diagrams.ready_from(manifest, ask=(beats[0]["figure"].get("ask") or ""))
        if not ready or not ready["parts"]:
            continue
        has = {str(name).replace("_", "") for name in ready["parts"]}
        before = sum(1 for beat in beats for step in beat.get("steps") or [] if str(step.get("focus") or "").replace("_", "") in has)
        part = {"chapters": [{"beats": beats}]}

        def again():
            for beat in beats:
                beat["figure"] = {"kind": "diagram"}
            use_diagram(part, {"diagram": ready}, log=lambda *_: None)        # keeps what the drawing has, adds what a step NAMES

        def words(step) -> set:
            return set(re.findall(r"[a-z]{4,}", str(step.get("show", "")).lower()))

        for beat in beats:                                                    # 1. the very step it replaces: same anchor or same line
            for step in beat.get("steps") or []:
                if str(step.get("focus") or "").replace("_", "") not in has:
                    same = next((o for o in earlier.get(str(beat.get("id", "")), []) if o.get("focus") and (
                        o.get("say") and o.get("say") == step.get("say")
                        or str(o.get("show", "")).lower() == str(step.get("show", "")).lower())), None)
                    if same is not None:
                        step["focus"] = same["focus"]
        again()                                                               # 2. a part the step names
        for beat in beats:                                                    # 3. the same place, when the line still shares a word:
            steps, old = beat.get("steps") or [], earlier.get(str(beat.get("id", "")), [])
            if len(old) == len(steps):                                        #    a line written again to say something else is not it
                for step, was_step in zip(steps, old):
                    if not step.get("focus") and was_step.get("focus") and words(step) & words(was_step):
                        step["focus"] = was_step["focus"]
        bare = [beat for beat in beats if any(not step.get("focus") for step in beat.get("steps") or [])]
        if bare and pointer is not False:                                     # 4. read against the drawing's names
            for (beat_id, index), name in ((pointer or diagrams.point_steps)(ready, bare, log=log) or {}).items():
                for beat in bare:
                    steps = beat.get("steps") or []
                    if str(beat.get("id", "")) == beat_id and index < len(steps) and not steps[index].get("focus"):
                        steps[index]["focus"] = name
        again()                                                               # the same labels on every beat
        after = sum(1 for beat in beats for step in beat.get("steps") or [] if step.get("focus"))
        if after != before:
            log(f"[writer] the drawing's steps point at its parts again: {before} → {after} of "
                f"{sum(len(beat.get('steps') or []) for beat in beats)} step(s) on {len(beats)} beat(s)")
    settle_panels(lesson, was=was, log=log)             # a panel a rewrite stopped asking for is asked for again
    # A whole picture with printed labels a step can mark (figure["points"]): the same order of putting a focus back.
    printed: dict[str, list] = {}
    for chapter in lesson.get("chapters") or []:
        for beat in chapter.get("beats") or []:
            figure = beat.get("figure") or {}
            if figure.get("kind") == "picture" and figure.get("points") and figure.get("file"):
                printed.setdefault(figure["file"], []).append(beat)
    for beats in printed.values():
        points = beats[0]["figure"]["points"]

        def kept(step) -> bool:
            focus = str(step.get("focus") or "")
            return focus in points or bool(re.fullmatch(r"panel\d+", focus))

        def line(step) -> set:
            return set(re.findall(r"[a-z]{4,}", str(step.get("show", "")).lower()))

        before = sum(1 for beat in beats for step in beat.get("steps") or [] if kept(step))
        for beat in beats:
            steps, old = beat.get("steps") or [], earlier.get(str(beat.get("id", "")), [])
            for index, step in enumerate(steps):
                if kept(step):
                    continue
                step.pop("focus", None)
                text = f"{step.get('show', '')} {step.get('say', '')}".lower()
                same = next((o for o in old if o.get("focus") in points and (o.get("say") and o.get("say") == step.get("say")
                                                                             or str(o.get("show", "")).lower() == str(step.get("show", "")).lower())), None)
                said = [key for key, entry in points.items() if len(str(entry.get("name", ""))) >= 3 and str(entry.get("name", "")).lower() in text]
                if same is not None:
                    step["focus"] = same["focus"]
                elif len(said) == 1:
                    step["focus"] = said[0]
                elif len(old) == len(steps) and old[index].get("focus") in points and line(step) & line(old[index]):
                    step["focus"] = old[index]["focus"]
        bare = [beat for beat in beats if any(not step.get("focus") for step in beat.get("steps") or [])]
        if bare and pointer is not False:
            ready = {"ask": beats[0]["figure"].get("ask", ""), "points": points}
            for (beat_id, index), name in ((pointer or diagrams.point_steps)(ready, bare, log=log) or {}).items():
                for beat in bare:
                    steps = beat.get("steps") or []
                    if str(beat.get("id", "")) == beat_id and index < len(steps) and not steps[index].get("focus") and name in points:
                        steps[index]["focus"] = name
        after = sum(1 for beat in beats for step in beat.get("steps") or [] if kept(step))
        if after != before:
            log(f"[writer] the picture's steps mark its printed labels again: {before} → {after} of "
                f"{sum(len(beat.get('steps') or []) for beat in beats)} step(s) on {len(beats)} beat(s)")
    return lesson


MIN_NAMED_STEPS = 2           # steps that must name a drawing's parts before it is shown by its parts and not whole


def drawings_for_scenes(lesson: dict, brief: dict, log=print, stills=None, pointer=None) -> dict:
    """As many of a lesson's pictures as the owner's drawing service can draw (their words: "as many as from the drawings").

    Every beat whose picture is a scene a model would have to write is offered to the
    service first (``diagrams.stills_for``; scenes that show the same things share one
    drawing). A drawing with parts is shown by them when at least ``MIN_NAMED_STEPS`` of
    its beats' steps are about a part (the writer did not know this drawing when it wrote
    them: ``diagrams.point_steps`` reads the steps against the drawing's own names, and
    ``use_diagram`` keeps only names the drawing has); otherwise it is shown whole, with
    its own labels. A scene the service has no drawing for stays a scene: the model
    writes it, as before. Off with ``HARNESS_TOPIC_PICTURES=0`` or no service.
    """
    if not diagrams.topic_pictures():
        return lesson
    order, groups = [], {}
    for chapter in lesson["chapters"]:
        for beat in chapter["beats"]:
            figure = beat.get("figure") or {}
            key = re.sub(r"\s+", " ", str(figure.get("describe") or "")).strip().lower()
            if figure.get("kind") == "scene" and key and not figure.get("module"):
                if key not in groups:
                    order.append(key)
                groups.setdefault(key, []).append(beat)
    if not order:
        return lesson
    scenes = [{"describe": groups[key][0]["figure"]["describe"], "said": " ".join(b.get("narration", "") for b in groups[key])}
              for key in order]
    drawn = (stills or diagrams.stills_for)(scenes, brief, log=log)
    pointer = pointer or (diagrams.point_steps if stills is None else (lambda *a, **k: {}))
    by_drawing: dict[str, tuple[dict, list]] = {}
    for key, ready in zip(order, drawn):
        if ready and ready.get("manifest"):
            by_drawing.setdefault(ready["manifest"], (ready, []))[1].extend(groups[key])
    from . import scripted  # noqa: PLC0415 - it imports this module; one rule for placing a whole picture
    quiet, placed, credits = (lambda *_: None), [], list(lesson.get("credits") or [])
    for ready, beats in by_drawing.values():
        before = [(beat, beat.get("figure"), [s.get("focus") for s in beat.get("steps") or []]) for beat in beats]
        part = {"chapters": [{"beats": beats}]}
        for beat in beats:
            beat["figure"] = {"kind": "diagram"}
        shown, named = "parts", 0
        if ready.get("shown") == "parts":
            for (beat_id, index), name in (pointer(ready, beats, log=log) or {}).items():
                for beat in beats:
                    if str(beat.get("id", "")) == beat_id and index < len(beat.get("steps") or []):
                        beat["steps"][index]["focus"] = name
            use_diagram(part, {"diagram": ready}, log=quiet)
            named = sum(1 for beat in beats for step in beat.get("steps") or [] if step.get("focus"))
        if ready.get("shown") != "parts" or named < MIN_NAMED_STEPS:
            whole, shown = diagrams.whole_of(ready), "whole"
            if not whole:                                   # nothing to show after all: the scene stands
                for beat, figure, focuses in before:
                    beat["figure"] = figure
                    for step, focus in zip(beat.get("steps") or [], focuses):
                        step.pop("focus", None) if focus is None else step.__setitem__("focus", focus)
                continue
            for beat in beats:
                beat["figure"] = {"kind": "diagram"}
            if whole.get("points"):                         # its printed labels: a step about one marks it (place_picture keeps those)
                for (beat_id, index), name in (pointer(whole, beats, log=log) or {}).items():
                    for beat in beats:
                        if str(beat.get("id", "")) == beat_id and index < len(beat.get("steps") or []):
                            beat["steps"][index]["focus"] = name
            scripted.place_picture(part, whole, log=quiet)
        credits += [c for c in part.get("credits") or [] if c not in credits]
        placed.append({"ask": ready.get("ask", ""), "shown": shown, "beats": [beat.get("id", "") for beat in beats]})
    left = sum(1 for chapter in lesson["chapters"] for beat in chapter["beats"] if (beat.get("figure") or {}).get("kind") == "scene")
    if credits:
        lesson["credits"] = credits
    if placed:
        lesson["pictures"] = placed
    log(f"[pictures] {sum(len(p['beats']) for p in placed)} beat(s) show {len(placed)} drawing(s) from the service in place of "
        f"model-written scenes; {left} scene(s) are left for a model to write"
        + ("" if not placed else ": " + "; ".join(f"“{p['ask'][:50]}…” ({p['shown']}, beats {', '.join(p['beats'])})" for p in placed)))
    return lesson


def _spoken(raw) -> int:
    listed = raw.get("chapters") if isinstance(raw, dict) else None
    return sum(len(str(beat.get("narration") or "").split()) for c in (listed if isinstance(listed, list) else []) if isinstance(c, dict)
               for beat in (c.get("beats") or []) if isinstance(beat, dict))


def too_little(raw, chapters: int, words: int) -> str:
    """What is missing from a script that is plainly not the whole lesson ("" when it is whole enough): fewer chapters
    than the framework has stages (one may be merged), or under six tenths of the words asked for."""
    listed = raw.get("chapters") if isinstance(raw, dict) else None
    listed = [c for c in listed if isinstance(c, dict)] if isinstance(listed, list) else []
    spoken = sum(len(str(beat.get("narration") or "").split()) for c in listed for beat in (c.get("beats") or []) if isinstance(beat, dict))
    if len(listed) < chapters - 1:
        return f"with {len(listed)} of {chapters} chapters ({spoken} spoken words)"
    if spoken < 0.6 * words:
        return f"with {spoken} spoken words where about {words} were asked for"
    return ""


def write_lesson(brief: dict, llm: LLM, log=print, card: dict | None = None, picture: dict | bool | None = None,
                 by_chapter: bool = False, lecturers: list[dict] | None = None) -> dict:
    """The model path. Returns a disciplined lesson dict with a ``continuity`` report.

    With a teaching ``card`` (``card.py``: how THIS topic is taught, built from sources)
    the model is also given the teaching skill and the card, and each chapter is told
    which line of the card it carries. Without one, nothing here changes: the prompts are
    the ones every earlier lesson was written with.

    ``picture`` is the drawing the topic is known by (``diagrams.for_brief``), for a lesson
    with no card. A caller that keeps written scripts must look for it BEFORE it decides
    whether a kept script fits, and hand it in (a dict, or False for "looked, there is
    none"): which picture a script was written on is part of what the script is. Left as
    None, the writer looks for it itself.
    """
    framework = frameworks.get(brief.get("framework", ""))
    minutes = int(brief.get("duration_minutes") or 6)
    if minutes < intake.MIN_MINUTES:          # a brief that did not come through the intake (the API, an older client)
        log(f"[writer] the shortest lesson is {intake.MIN_MINUTES} minutes: written to that, not to {minutes}")
        minutes = intake.MIN_MINUTES
        brief = {**brief, "duration_minutes": minutes}
    stages = framework["stages"]
    words = word_budget(minutes)
    stops = stop_plan(framework, minutes)
    system, brief_text, mistake = SYSTEM, _brief_block(brief, framework), brief.get("misconception")
    if lecturers:
        brief_text += "\n\n" + voice.for_writer(lecturers)
        log(f"[writer] {len(lecturers)} lecturer passage(s) to take the manner from: "
            + "; ".join(e["source"][:50] for e in lecturers))
    if card:
        system = SYSTEM + "\n\nHOW TO TEACH — the teaching skill you work by:\n" + skill.for_writer()
        brief_text += "\n\n" + teaching_card.for_writer(card)
        mistake = mistake or (card["mistakes"][0]["mistake"] if card["mistakes"] else None)
        log(f"[writer] writing from the teaching card (skill {skill.version()})")
    system += kits.rules_for(brief.get("kits"), log=log)    # "" unless the brief names a kit: prompts stay as they were
    # A lesson with no card still gets the picture its topic is known by (diagrams.for_brief): the owner's
    # instruction of 2026-10-09. With neither a card nor a picture the prompts are the ones they always were.
    if picture is None and not card and diagrams.topic_pictures():
        picture = diagrams.for_brief(brief, log=log)
    picture = picture if isinstance(picture, dict) and not card else None
    if picture:
        brief_text += "\n\n" + teaching_card.block_for(picture)
    shape = ('{"title": str, "thesis": str, "anchor": "the ONE example: an everyday object (or the thing itself) and '
             'its numbers, at most 16 words, no story", "anchor_name": "two or three words to call it by afterwards", '
             '"small_case": "the smallest numbers that show the idea", '
             '"shapes": {"<name>": {"points": {...}, "polygon": str, "is": [str]}} or {}, '
             '"method": ["each step the learner must be able to do afterwards, in order"], '
             '"glossary": [{"term": str, "meaning": str}], "chapters": [{"title": str, "learning_goal": str, '
             '"beats": [{"narration": str, "visual": str, "check": str, "thinking_pause_seconds": number, '
             '"figure": {...} or null, "quiz": {...} or null, "depth": "basics|core|practice|extra", '
             '"steps": [{"say": str, "show": str, "kind": "point|key|math", "highlight": bool, "focus": str}]}]}]}')
    whole = minutes <= SINGLE_CALL_MINUTES and not by_chapter
    if whole:
        log(f"[writer] one call: {len(stages)} chapters, at most {words} words")
        per_chapter = max(35, words // len(stages))
        prompt = (f"{brief_text}\n\nTEACHING FRAMEWORK “{framework['name']}” — write exactly "
                  f"{len(stages)} chapters, one per stage, in this order:\n{_stage_block(framework, stops)}\n\n"
                  f"LENGTH: at most {words} spoken words in total, about {per_chapter} per chapter, in "
                  f"{max(1, per_chapter // 60)} to {max(1, per_chapter // 40)} beat(s) each. The video must run "
                  f"{minutes} minute(s): going over is the usual failure, so cut restatement before anything else.\n\n"
                  f"JSON shape:\n{shape}")
        if card:
            owner = frameworks.misconception_stage(framework)
            prompt += "\n\n" + "\n".join(f"Chapter {i + 1}: " + card_notes(card, i, s, owns_mistake=s is owner).replace("\n", " ")
                                          for i, s in enumerate(stages))
        raw = llm(prompt, system)
        # A script is the WHOLE lesson or it is not a script. A small model returned three of seven chapters (111 words of
        # 343) and stopped, and the lesson went on to its review as if it were whole (2026-10-12). Asked once more with
        # what was missing; still short, it is written chapter by chapter, where every call has one small job.
        short = too_little(raw, len(stages), words)
        if short:
            log(f"[writer] the script came back {short}: asked once more")
            try:
                again = llm(f"{prompt}\n\nYOUR FIRST ANSWER came back {short}. Write the WHOLE lesson: all {len(stages)} chapters, "
                            f"one per stage in the order given, about {per_chapter} spoken words each.", system)
            except Exception as exc:  # noqa: BLE001 - then the first answer is judged alone
                again = None
                log(f"[writer] the second asking failed ({type(exc).__name__})")
            if again is not None and not too_little(again, len(stages), words):
                raw, short = again, ""
            elif again is not None and _spoken(again) > _spoken(raw):
                raw = again                              # still short, but the fuller of the two
        if short:
            # One small job a call. And a fallback improves or stands aside: when that fails too, the short script is
            # the lesson (a third of a lesson is more than none, and the log says what it is).
            log(f"[writer] still {short}: written chapter by chapter instead")
            try:
                return write_lesson(brief, llm, log=log, card=card, picture=picture, by_chapter=True, lecturers=lecturers)
            except Exception as exc:  # noqa: BLE001
                log(f"[writer] chapter by chapter failed too ({type(exc).__name__}: {str(exc)[:100]}): THE SHORT SCRIPT IS KEPT, {short}")
    if not whole:
        # Plan once, then write chapter by chapter against a ledger of what is already true.
        per_chapter = max(60, words // len(stages))
        plan = llm(
            f"{brief_text}\n\nPlan a {minutes}-minute lesson in the framework "
            f"“{framework['name']}”, one chapter per stage:\n{_stage_block(framework, stops)}\n\nReturn JSON: "
            '{"title": str, "thesis": str, "anchor": "the ONE example: an everyday object (or the thing itself) and '
            'its actual numbers, at most 16 words, no story", "anchor_name": "two or three words to call it by '
            'afterwards", "small_case": "the smallest numbers that show the idea, countable on screen", '
            '"method": ["each step the learner must be able to do afterwards, in order"], '
            '"glossary": [{"term": str, "meaning": "one line, as this lesson uses it"}], "chapters": [{"title": str, '
            '"learning_goal": str, "enters_with": "what the learner already has", "leaves_with": "what is newly '
            'established — different from every other chapter"}]}'
            + (' Also give "moves": the lesson as a chain of moves in order, one short line each, before any wording '
               '(question, guess, what is seen, why, name, worked case, your turn, try it, say it back). The anchor is the '
               "card's picture." if card else ""),
            system)
        raw = {**plan, "chapters": []}
        glossary = [g for g in (plan.get("glossary") or []) if isinstance(g, dict) and g.get("term")]
        method = [str(m).strip() for m in (plan.get("method") or []) if str(m).strip()][:8]
        name = str(plan.get("anchor_name") or "the example").strip()
        introduces = example_stage(framework)
        established, last_lines, handed, said, asked = [], "", "", [], ""
        on_screen = ""          # what the previous chapter left drawn; only a card lesson is told (see card_notes)
        for i, stage in enumerate(stages):
            outline = (plan.get("chapters") or [{}] * len(stages))[min(i, len(plan.get("chapters") or [{}]) - 1)]
            log(f"[writer] chapter {i + 1}/{len(stages)}: {stage['title']}")
            # The ledger is state the MODEL updates explicitly after each chapter
            # (docs/research/approaches/01_*: a code-validated ledger diff keeps
            # contradiction density down where a prose reminder does not).
            # The example is DESCRIBED in one chapter only. Until 2026-10-08 every chapter
            # was handed the full sentence with "use it", and none saw the others' words:
            # six of seven chapters of one lesson opened by setting the same scene again.
            if i < introduces:
                example = ("THE EXAMPLE comes in a later chapter — do not describe it here; the opening question may "
                           "use its plain numbers." if card else
                           "THE EXAMPLE comes in a later chapter — do not use or mention it here.")
            elif i == introduces:
                example = (f"THE EXAMPLE — describe it HERE, this once, in one or two sentences, smallest case first: "
                           f"{plan.get('anchor', '')} (smallest case: {plan.get('small_case', '') or 'your choice'}). "
                           f"From now on it is called “{name}”.")
            else:
                example = (f"THE EXAMPLE was described in chapter {introduces + 1}. Do NOT describe it or its setting "
                           f"again: call it “{name}” and use it only if this chapter's job needs it. ({plan.get('anchor', '')})")
            ledger = (f"{example}\n"
                      f"GLOSSARY (use exactly these terms, ordinary spelling): {json.dumps(glossary, ensure_ascii=False)}\n"
                      f"ALREADY ESTABLISHED (do not re-teach, do not contradict, do not repeat): {established or 'nothing yet'}\n"
                      f"THE PREVIOUS CHAPTER HANDS YOU: {handed or '(nothing yet)'}")
            if asked:
                # The rule "the next beat confirms the answer" used to stop at a chapter's edge:
                # a question asked in the last beat of one chapter was simply left hanging.
                ledger += (f"\nTHE PREVIOUS CHAPTER ENDED BY ASKING THE LEARNER: {asked} — open this chapter by "
                           "confirming the answer in one short sentence, then move on.")
            if method:
                ledger += ("\nTHE METHOD the learner must be able to do afterwards — each step carried out on screen "
                           f"somewhere in the lesson, not just named: {method}")
            if said:
                ledger += ("\nTHE SCRIPT SO FAR — every word already spoken. Repeat NONE of its sentences, questions, "
                           "explanations or results; build on them:\n" + "\n".join(said))
            if mistake:
                owner = frameworks.misconception_stage(framework)
                ledger += (f"\nTHE KNOWN MISTAKE is confronted in the stage “{owner['title']}”"
                           + (" — this chapter." if stage is owner else "; here, do not confront it (at most one brief mention)."))
            if raw.get("shapes"):
                ledger += ("\nSHAPES ALREADY DECLARED (use them by name; declare a new one in this chapter's \"shapes\"): "
                           + json.dumps(raw["shapes"], ensure_ascii=False)[:1500])
            chapter = llm(
                f"{brief_text}\n\nLESSON: {plan.get('title', '')} — {plan.get('thesis', '')}\n{ledger}\n\n"
                f"Write ONLY chapter {i + 1} of {len(stages)}: [{stage['role']}] {stage['title']} — {stage['job']}\n"
                f"{STOPS if i in stops else NO_STOP}\n"
                + (card_notes(card, i, stage, owns_mistake=stage is frameworks.misconception_stage(framework),
                              picture=on_screen) + "\n" if card else "") +
                f"Its goal: {outline.get('learning_goal', '')}. It must leave the learner with: {outline.get('leaves_with', '')}.\n"
                f"LENGTH: at most {per_chapter} spoken words, in {max(1, per_chapter // 60)} to {max(2, per_chapter // 40)} "
                f"beats of 35 to 70 words. Stop when the chapter's job is done: the whole video must run {minutes} "
                f"minutes, and restating is the usual way it runs over.\n\nJSON shape: "
                '{"title": str, "learning_goal": str, "shapes": {} or {"<name>": {"points": {...}, "polygon": str, "is": [str]}}, '
                '"beats": [{"narration": str, "visual": str, "check": str, '
                '"thinking_pause_seconds": number, "figure": {...} or null, "quiz": {...} or null, '
                '"depth": "basics|core|practice|extra", "steps": [{"say": str, "show": str, "kind": "point|key|math", "highlight": bool, "focus": str}]}], '
                '"uses_from_before": ["each earlier fact or term this chapter relies on, quoted from ALREADY ESTABLISHED or GLOSSARY"], '
                '"running_example_step": "what this chapter does with the example, with its numbers — or \"not used\"", '
                '"hands_forward": "the one thing the next chapter must pick up", '
                '"ledger_update": {"established_add": ["new facts now established, one line each"], '
                '"glossary_add": [{"term": str, "meaning": str}]}}', system)
            raw["chapters"].append(chapter)
            if isinstance(chapter.get("shapes"), dict):
                raw["shapes"] = {**(raw.get("shapes") or {}), **chapter["shapes"]}
            # Validate the chapter's continuity fields in code before trusting them.
            known = " ".join(established + [f"{g.get('term', '')} {g.get('meaning', '')}" for g in glossary]).lower()
            uses = [str(u) for u in (chapter.get("uses_from_before") or []) if str(u).strip()]
            unexplained = [u for u in uses if not any(len(w) >= 4 and w in known for w in _norm(u).split())]
            chapter["_continuity"] = {"uses_from_before": uses, "unexplained_references": unexplained,
                                      "running_example_step": str(chapter.get("running_example_step") or "").strip(),
                                      "hands_forward": str(chapter.get("hands_forward") or "").strip()}
            if unexplained:
                log(f"[writer] chapter {i + 1}: relies on {len(unexplained)} thing(s) never established: {unexplained[:2]}")
            update = chapter.get("ledger_update") or {}
            for fact in (update.get("established_add") or []) if isinstance(update, dict) else []:
                if str(fact).strip() and str(fact).strip() not in established:
                    established.append(str(fact).strip())
            for entry in (update.get("glossary_add") or []) if isinstance(update, dict) else []:
                if isinstance(entry, dict) and entry.get("term") and entry["term"] not in {g["term"] for g in glossary}:
                    glossary.append({"term": str(entry["term"]), "meaning": str(entry.get("meaning", ""))})
            if outline.get("leaves_with") and outline["leaves_with"] not in established:
                established.append(outline["leaves_with"])
            handed = chapter["_continuity"]["hands_forward"]
            written = [b for b in (chapter.get("beats") or []) if isinstance(b, dict)]
            spoken = " ".join(str(b.get("narration", "")).strip() for b in written)
            if spoken:
                said.append(f"[chapter {i + 1}] {spoken}")
            last = written[-1] if written else {}
            drawn = next((b["figure"] for b in reversed(written) if isinstance(b.get("figure"), dict) and b["figure"].get("kind")), None)
            if drawn:
                on_screen = str(drawn.get("describe") or json.dumps(drawn, ensure_ascii=False))[:400]
            quiz = last.get("quiz") if isinstance(last.get("quiz"), dict) else {}
            asked = ""
            if quiz.get("question") or float(last.get("thinking_pause_seconds") or 0) > 0:
                options, k = quiz.get("options") or [], quiz.get("answer_index")
                right = options[k] if isinstance(k, int) and 0 <= k < len(options) else ""
                asked = f"“{quiz.get('question') or str(last.get('narration', '')).split('. ')[-1]}”" + (f" (answer: {right})" if right else "")
        raw["glossary"] = glossary
    raw = geometry_pass(raw, llm, system, log=log)
    raw = kit_pass(raw, llm, system, log=log)
    ready = (card or {}).get("diagram") or picture
    lesson = keep_planned_stops(discipline(raw, brief, framework, split_long=True), stops, log=log)
    lesson = own_pictures(lesson, llm, log=log)
    if ready and ready.get("shown") == "whole":
        from . import scripted  # noqa: PLC0415 - it imports this module; one rule for placing a whole picture
        lesson = settle_panels(scripted.place_picture(lesson, ready, log=log), log=log)
    else:
        lesson = use_diagram(lesson, card or ({"diagram": picture} if picture else None), log=log)
    if picture:
        lesson["picture"] = {k: picture.get(k, "") for k in ("ask", "shows", "visual_kind", "shown", "credit")}
    lesson = drawings_for_scenes(lesson, brief, log=log)      # the scenes that are left are offered to the service first
    lesson["generated_by"] = "model"
    if raw.get("_geometry_faults") is not None:
        lesson["geometry_check"] = {"faults_left": raw["_geometry_faults"]}
    if raw.get("_kit_faults") is not None:
        lesson["kit_check"] = {"kits": raw["_kit_names"], "faults_left": raw["_kit_faults"]}
    lesson["continuity"] = continuity(lesson)
    # How it SOUNDS (voice.py). The beats a listener would call unnatural get one rewrite, kept only where it
    # helps; it runs before the reviewer, so whatever it changed is reviewed like any other sentence.
    if voice.enabled(card):
        lesson["voice"] = voice.polish(lesson, llm, log=log, examples=lecturers)
        if lesson["voice"]["rewritten"]:
            lesson["continuity"] = continuity(lesson)
    heard = voice.line(lesson)
    if heard:
        log(f"[writer] voice: {heard}")
    if card:
        lesson["card"] = card          # what the lesson stands on, and its try-it task; no passage text is in it
        if isinstance(raw.get("moves"), list):
            lesson["moves"] = [str(m).strip()[:160] for m in raw["moves"] if str(m).strip()][:14]
    Lesson.model_validate(lesson)
    return lesson


GEOMETRY_REPAIRS = 2


def geometry_pass(raw: dict, llm: LLM, system: str, log=print) -> dict:
    """Shape figures expanded from the lesson's named shapes and every gap filled from their points (``shapes``).

    Only when the script draws a ``shape``. The faults code finds (a claim the points do not make true, a number of
    degrees the picture does not show, a gap it cannot fill) go back to the model, at most ``GEOMETRY_REPAIRS``
    times; the draft with the fewest faults is kept, and what is left is recorded as ``figure_issues``.
    """
    from . import shapes  # noqa: PLC0415
    drawn = any(isinstance(b.get("figure"), dict) and b["figure"].get("kind") == "shape"
                for c in raw.get("chapters") or [] for b in c.get("beats") or [] if isinstance(b, dict))
    if not drawn:
        return raw
    filled, issues = shapes.settle(raw)
    log(f"[writer] geometry: {len(issues)} fault(s) found against the pictures' points")
    for _ in range(GEOMETRY_REPAIRS):
        if not issues:
            break
        try:
            again = llm(shapes.repair_prompt(raw, issues), system)
        except Exception as exc:  # noqa: BLE001 - the draft so far stands
            log(f"[writer] geometry repair failed ({type(exc).__name__})")
            break
        filled2, issues2 = shapes.settle(again)
        log(f"[writer] geometry repair: {len(issues2)} fault(s) left")
        if len(issues2) <= len(issues):
            raw, filled, issues = {**raw, **again, "chapters": again.get("chapters") or raw["chapters"]}, filled2, issues2
    filled["_geometry_faults"] = issues
    return filled


KIT_REPAIRS = 2


def kit_pass(raw: dict, llm: LLM, system: str, log=print) -> dict:
    """The subject kits' twin of ``geometry_pass``: gaps filled from the model and claims checked by code.

    Only for a lesson that uses a served kit (``kits.active``; geometry is not one, its own pass has run). The faults
    code finds go back to the model at most ``KIT_REPAIRS`` times and the draft with the fewest is kept; what is left is
    recorded in ``_kit_faults`` (and, on the lesson, ``kit_check``). A deliberate wrong quiz option is no fault. A kit
    that raises costs nothing: the draft stands.
    """
    served = kits.active(raw)
    if not served:
        return raw

    def check(draft: dict) -> tuple[dict, list[str]]:
        filled, faults = draft, []
        for kit in kits.checkers(draft):       # each kit over its own beats; geometry too when the lesson mixes subjects
            filled, found = kit.settle(filled)
            faults += [f for f in found if not kit.expected_fault(f, draft)]
        one = kits.mixed(draft)                 # the one-subject fault, only while LESSONFORGE_KITS_MIXED is off
        if one:
            faults.append(one)
        faults += kits.orphan_gaps(draft)       # mixed: a gap on a beat no kit owns, once ("which subject is this from?")
        return filled, faults
    names = [k.name for k in served]
    try:
        filled, issues = check(raw)
    except Exception as exc:  # noqa: BLE001 - the draft as written stands
        log(f"[writer] kits {', '.join(names)} failed ({type(exc).__name__}: {str(exc)[:120]})")
        return raw
    log(f"[writer] kits {', '.join(names)}: {len(issues)} fault(s) found against the pictures' models")
    for _ in range(KIT_REPAIRS):
        if not issues:
            break
        try:
            again = llm(kits.repair_prompt(raw, issues), system)
            filled2, issues2 = check(again)
        except Exception as exc:  # noqa: BLE001 - the draft so far stands
            log(f"[writer] kit repair failed ({type(exc).__name__})")
            break
        log(f"[writer] kit repair: {len(issues2)} fault(s) left")
        if len(issues2) <= len(issues):
            raw, filled, issues = {**raw, **again, "chapters": again.get("chapters") or raw["chapters"]}, filled2, issues2
    filled["_kit_faults"], filled["_kit_names"] = issues, names
    return filled


HAND_WRITTEN = "written by hand"      # how ``generated_by`` starts for a lesson a person wrote out in full


def load_draft(path, log=print) -> dict | None:
    """A lesson this writer already wrote, read back from the workspace so it can be rendered as it is.

    For a script someone has read and approved: writing it again would give different
    words. Only a file inside the workspace is accepted (a brief can arrive over the API),
    and only one that still passes the lesson contract.
    """
    from .. import paths  # noqa: PLC0415
    from pathlib import Path  # noqa: PLC0415
    try:
        file = Path(str(path)).expanduser().resolve()
        if not file.is_relative_to(paths.home()) or not file.is_file():
            log(f"[writer] draft not used: {file.name} is not a file in the workspace")
            return None
        lesson = json.loads(file.read_text(encoding="utf-8"))
        Lesson.model_validate(lesson)
        by = str(lesson.get("generated_by") or "")
        # A lesson a person wrote out in full (words, steps and pictures) says so itself, and is rendered as it is
        # too: that is how a demonstration is made without a single model call. It keeps its own label.
        # A teaching pack's geometry lesson (``pack``) was checked against its pictures by code before it was kept.
        if not (by in ("model", "geometry pack") or by.startswith(HAND_WRITTEN)) or not isinstance(lesson.get("continuity"), dict):
            log("[writer] draft not used: it was not written by the script writer or marked as written by hand")
            return None
        log(f"[writer] using the script already written ({file.name}): nothing is written again")
        return lesson
    except (OSError, ValueError) as exc:
        log(f"[writer] draft not used: {type(exc).__name__}: {str(exc)[:120]}")
        return None


def outline_lesson(brief: dict) -> dict:
    """No model configured: a deterministic outline that says what each stage WOULD do."""
    framework = frameworks.get(brief.get("framework", ""))
    topic, goal = brief.get("topic", "this idea"), brief.get("goal", "")
    example = brief.get("context") or "one concrete example"
    chapters = []
    for i, stage in enumerate(framework["stages"], start=1):
        opening = (f"This is an outline for a lesson on {topic}, built with the framework called {framework['name']}."
                   if i == 1 else f"Stage {i} continues from there.")
        narration = (f"{opening} This stage is called {stage['title']}. {stage['job']} "
                     f"The running example is {example}.")
        steps = [
            {"say": "This stage is called", "show": f"{i}. {stage['title']}", "kind": "key", "highlight": True},
            {"say": "The running example", "show": f"Running example: {example}"[:100], "kind": "point",
             "highlight": False},
        ]
        chapters.append({"title": stage["title"], "learning_goal": stage["job"],
                         "beats": [{"narration": narration, "visual": stage["job"], "check": "", "steps": steps}]})
    raw = {"title": topic, "thesis": goal, "anchor": example, "chapters": chapters}
    lesson = discipline(raw, brief, framework)
    lesson["generated_by"] = "outline (no model configured — placeholder narration, not a lesson)"
    lesson["continuity"] = continuity(lesson)
    Lesson.model_validate(lesson)
    return lesson


# Measured 2026-10-08 on one Hinglish brief (docs/research/experiments/…/REPORT.md §7): GPT-5.6 Terra and
# Claude Sonnet 5.5 wrote the richest scripts (a figure focus on every step, three quizzes); Terra in half the
# time. Gemini 3.8 Flash is the fallback: a fifth of the price and still on policy.
# 2026-10-12, the owner: "this narration or story board model is not good, try better model". The same brief and
# teaching card written again by two others, an English lesson and a Hinglish one: Sonnet 5.5 kept to the word budget
# both times (367 and 342 words for "at most 343"; Terra 484 and 400), said "I" and "we" three times as often, put the
# numbers it speaks into its lines ("30°, 60°, or anywhere?") and pointed at the picture ("Left mein bar magnet …").
# Opus 5.5 was no better for twice the price. Sonnet thinks before it writes: about 0.32 USD a script against about
# 0.19 for Terra. ``HARNESS_WRITER_MODELS`` in ``.env`` puts the order back.
#
# The same evening the owner: "Current models are taking a very heavy cost … use cheap models and improve the harness; you
# need to work on the harness, not by taking costly models." A lesson had cost 0.69 USD, 0.41 of it this chain (the model
# thinks before it writes: 23,000 of its 32,000 output tokens). The small model of the same family, on four briefs
# (Friction twice, Reflection in English, Heat): 352, 388, 353 and 338 words for "at most 343"; by the harness's own
# measures (language, repetition, pauses, question faults, voice) level with the large one's draft; 2 cents a script
# against 26. So it writes, and what it does less well is the harness's to catch (the gates, the reviewer, the voice and
# question passes all run on it too). ``HARNESS_WRITER_MODELS`` puts another order.
#
# 2026-10-14, the owner's Model Choice Protocol run on the writer (``scripts/eval_writer.py``, scorecard
# ``evals/writer/scorecard.csv``; the unit is the script after the review and the code gates, one model end to end):
# Qwen 3.8 Flash with thinking off scored with Haiku 5.5 (84.7 against 81.3, correctness 4.5 against 4.0 on six lessons)
# at a seventh of the cost, and comes second here until the same six-plus-six lessons confirm it; Gemini 3.8 Flash
# (thinking that cannot be switched off) is no longer in the chain. Thinking per model: ``engine.llm.THINKING_BY_MODEL``.
WRITER_MODELS_DEFAULT = "anthropic/claude-haiku-5.5,qwen/qwen3.8-flash,openai/gpt-5.4-nano"


def writer_models() -> list[str]:
    """The OpenRouter chain for script writing (``HARNESS_WRITER_MODELS``, comma-separated)."""
    raw = knobs.get("HARNESS_WRITER_MODELS", WRITER_MODELS_DEFAULT)
    return [m.strip() for m in raw.split(",") if m.strip()]


# The writer's thinking is left to the model. Tried 2026-10-12 on real briefs: a cap in tokens (``reasoning.max_tokens``
# 6000) was not kept (20,000 and 44,000 tokens of thinking) and one first answer came back with one chapter of seven;
# ``effort: low`` halved the thinking (16,000) and saved about a cent and a minute a script, and that script talked
# about the screen three times where the others did once at most. A cent is not worth a worse script.
def default_llm(models: list[str] | None = None, temperature: float = 0.6) -> LLM | None:
    """A script-writing model, or None when no key is set.

    With an OpenRouter key the writer goes straight to its own chain (Gemini 3.8 Flash
    first — the writer is the one call per lesson where quality matters most and its
    cost is cents) in JSON mode, metered through the spend ledger. Otherwise it falls
    back to the engine's general provider chain (Gemini → OpenRouter → Groq).
    """
    from ..engine import llm as engine_llm
    from ..engine.dependencies import env_api_keys
    keys = env_api_keys()
    openrouter_key = (os.getenv("OPENROUTER_API_KEY") or "").strip()
    if openrouter_key:
        chain = models or writer_models()

        def call(prompt: str, system: str):
            # An answer that is not a JSON object is a failed answer, not a crash: glm-4.7-flash answered the JSON-mode
            # call with a JSON STRING (the object serialised once more) and write_lesson died on ``'str'.get``
            # (2026-10-14, the writer evaluation). The next model in the chain is asked instead.
            rest = list(chain)
            while True:
                text = engine_llm.call_openrouter(openrouter_key, prompt, system, temperature=temperature,
                                                  models=rest, max_tokens=None, json_object=True, note="writer")
                try:
                    return answer_object(text)
                except ValueError:
                    if len(rest) <= 1:
                        raise
                    rest = rest[1:]
        return call
    client = engine_llm.get_genai_client(keys)
    if not engine_llm.llm_available(client, keys):
        return None

    def call_chain(prompt: str, system: str):
        response = engine_llm.call_llm_with_fallback(client, prompt, system, temperature=temperature,
                                                     task="storyboard", keys=keys)
        return answer_object(response.text)
    return call_chain


def answer_object(text: str) -> dict:
    """The JSON object in a model's answer, or ``ValueError``.

    A model in JSON mode sometimes returns the object serialised once more (a JSON string holding JSON): that is
    parsed a second time. Anything that is still not an object (a string, a list, a number) is refused, so the
    caller treats it as a failed answer instead of raising ``AttributeError`` deep inside ``write_lesson``.
    """
    from ..engine import llm as engine_llm
    parsed = engine_llm.loads_json_lenient(text)
    if isinstance(parsed, str):
        try:
            parsed = engine_llm.loads_json_lenient(parsed)
        except Exception as exc:  # noqa: BLE001
            raise ValueError(f"the model answered with a string, not a JSON object: {parsed[:80]!r}") from exc
    if not isinstance(parsed, dict):
        raise ValueError(f"the model answered with a {type(parsed).__name__}, not a JSON object")
    return parsed
