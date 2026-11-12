"""Three explanation frameworks — the same idea taught three ways, by learner level.

A framework is a SHAPE for the explanation, not content: an ordered list of stages,
each with a job. The script writer fills one chapter per stage, so the framework is
what makes two lessons on different topics feel like the same teacher, and what
keeps a twenty-minute lesson from turning into unrelated mini-lessons — every stage
knows what came before it and what it must hand to the next.

Revised 2026-10-08 against the evidence collected in
docs/research/approaches/04_frameworks_evaluation_selfhosting.md:

* every level opens by ACTIVATING what the learner already has (prior-knowledge
  review plus pre-training of the few terms the lesson needs — Rosenshine; Mayer's
  pretraining principle) and closes with RETRIEVAL, not a summary read aloud;
* "explore" is guided prediction → pause → reveal, at most two cycles, never open
  exploration (the worked-example effect: novices learn more from studying than
  from searching);
* practice is FADED — the learner supplies one step, then more (fading has the
  strongest effect in the worked-example meta-analyses, g≈0.48);
* the known misconception is confronted by REFUTATION — state it, let it fail on
  the running example (Muller's refutation videos, d≈0.8) — in exactly one stage;
* the advanced track is problem-first (attempt before instruction; productive
  failure, g≈0.36) with a proof segmented by "why is this step allowed?" pauses.

Nothing here has yet been validated with learners; these are the structures the
literature supports, encoded so that the writer, the critic and the batch runner
can all refer to the same stage roles.
"""
from __future__ import annotations

FRAMEWORKS = [
    {
        "id": "concrete_first",
        "name": "See it, then name it",
        # What a requester is shown. They are choosing a video, not a pedagogy: say what
        # they will SEE and who it is for (a tester, 2026-10-08: the three versions were
        # "generic and not understandable for the person who is using the app").
        "plain": "Start from a picture",
        "plain_hint": "For learners new to it: a small case they can see, a guess, then the rule.",
        "level": "foundation",
        "for": "New to the idea, or shaky on the prerequisites. Classes 6–8, or anyone meeting it for the first time.",
        "promise": "Starts from something you can picture, lets you predict before being told, and only brings in symbols once the picture is obvious.",
        "voice": "Warm and unhurried. Short sentences. One new word at a time, always tied to the picture. Speaks to 'you'.",
        "stages": [
            {"role": "activate", "title": "What you already know",
             "job": "Recall the one or two things the learner already knows that this lesson builds on, and pre-teach the two or three words the lesson will need, each with a tiny case of its own. No new idea yet, and the lesson's example is not used yet."},
            {"role": "concrete", "title": "A situation you can picture",
             "job": "Describe the example — the only chapter that does — starting from its smallest case, one the learner can count on screen, and pose the question the learner wants answered. No formula, no jargon beyond the pre-taught words."},
            {"role": "explore", "title": "Predict, then look",
             "job": "Guided prediction on the small case, then on the next size up: ask the learner to predict ONE specific thing, pause, then reveal and name what actually happens. At most two predict-pause-reveal cycles. Let the pattern show itself; do not solve the lesson's big case here."},
            {"role": "name", "title": "Give it a name",
             "job": "Name the idea and state it as one rule; move from the picture to the symbols, each symbol tied to a part of the picture (concrete → representational → abstract). No worked example here: that is the next chapter's job."},
            {"role": "model", "title": "Watch one, step by step",
             "job": "One complete worked example with the lesson's real numbers: carry out every step of the method the learner must later do alone, in order, each step spoken with its reason. The learner only watches. Do not re-derive the rule. End by answering, in one sentence, the question the example posed."},
            {"role": "practice", "title": "Now you, with help",
             "job": "A fresh case that comes out differently from the worked one where the goal allows it (when the goal is a test: a case that fails). The learner supplies the first step (thinking pause), then it is revealed; then the next step. Aim for a problem the learner will mostly get right."},
            {"role": "recap", "title": "Say it back",
             "job": "Retrieval, not summary: ask two short questions that make the learner recall the idea and the method, pause, answer each in one sentence. Then name the most common mistake in one sentence and why it fails. Re-explain nothing."},
        ],
    },
    {
        "id": "worked_examples",
        "name": "Watch one, do one",
        "plain": "Start from a solved example",
        "plain_hint": "For learners who know the basics: one problem solved step by step, then one they try.",
        "level": "standard",
        "for": "Knows the prerequisites and needs to become fluent. Classes 8–10, exam preparation.",
        "promise": "States the idea early, then builds skill through worked examples that hand over more of the work each time, and breaks the usual mistake in the open.",
        "voice": "Clear and brisk, like a good tutor. Says WHY each step is taken, not only what it is. Speaks to 'you'.",
        "stages": [
            {"role": "hook", "title": "The problem we will crack",
             "job": "Present the running example as a problem worth solving, with its numbers, and state what the learner will be able to do by the end."},
            {"role": "activate", "title": "What we are building on",
             "job": "Recall the one or two prerequisite facts this lesson uses and fix the terms and notation the lesson will use, each said one way. Brief."},
            {"role": "idea", "title": "The idea in one picture",
             "job": "State the rule and justify it with ONE picture or argument on the running example, in at most two chunks. Define each symbol once."},
            {"role": "example", "title": "Worked example",
             "job": "Solve the running example completely. Name the decision at every step: what do we know, what do we want, which relation links them."},
            {"role": "faded", "title": "Your turn, with help",
             "job": "A second problem where the learner supplies the next step at two marked points (thinking pauses) before it is revealed, and once is asked to explain WHY a step is taken before hearing it."},
            {"role": "refutation", "title": "Where it goes wrong",
             "job": "State the known mistake as someone would actually make it, apply it to the running example, and show concretely why the result cannot be right. Give a quick self-check the learner can always run."},
            {"role": "recap", "title": "The method in three lines",
             "job": "Retrieval: ask the learner to recall the three steps, pause, then give them in one line each. Close the opening problem in one sentence and point to one new situation where the same method applies. Re-explain nothing."},
        ],
    },
    {
        "id": "why_it_works",
        "name": "Why must it be true?",
        "plain": "Start from why it is true",
        "plain_hint": "For learners who already use it: they try first, see where it breaks, then the proof.",
        "level": "advanced",
        "for": "Already uses the result and wants to understand it. Strong Class 9–12 students, olympiad or teacher audiences.",
        "promise": "Treats the result as a claim to be tested: try first, find where intuition breaks, then prove it and push on its limits.",
        "voice": "Curious and exact, and plain: explains in full joined sentences, the way a good lecturer reasons out loud. Asks a few real questions and waits for those. Never says 'obviously'. Speaks to 'you'.",
        "stages": [
            {"role": "problem", "title": "Try it before you are told",
             "job": "Pose the running example as a problem and ask the learner to attempt it with what they have, with a thinking pause. Do not give the method yet."},
            {"role": "claim", "title": "A claim worth doubting",
             "job": "Say the result plainly, in full sentences, on the running example, and say what makes it surprising or hard to believe. Do not announce it as a claim."},
            {"role": "conflict", "title": "Where intuition breaks",
             "job": "Show the tempting wrong idea (the known mistake, if given) and a case that seems to contradict the result. Make the tension explicit on the running example's numbers."},
            {"role": "proof", "title": "The argument",
             "job": "A complete argument in small steps using the running example's objects, explained the way a lecturer reasons out loud: each step joined to the last with so, because, which means, and the reason each step is allowed said with it. Say which step does the real work."},
            {"role": "limits", "title": "When does it fail?",
             "job": "Show what happens when one condition is different, and how the result then breaks. Say plainly what the result needs."},
            {"role": "transfer", "title": "The same idea elsewhere",
             "job": "Apply the idea in a different setting, with one question for the learner and thinking time."},
            {"role": "recap", "title": "What we now know, and why",
             "job": "Retrieval: ask the learner to state the result with its conditions and the one-line reason it is true, pause, then say it. Ask what they would check first next time. Re-explain nothing."},
        ],
    },
    {
        "id": "story",
        "name": "A puzzle, then the answer",
        # Built from the script benchmark of 2026-11-03 (evals/explainers, script-bench): scripts written to this shape
        # scored 6.8/10 blind against 3.5 for the three stage plans above on the same models; Haiku went from 3.5 to 7.5.
        # It follows how explainer channels (Khan Academy, 3Blue1Brown) tell one idea: a thing you have seen, the
        # guess most people make, a "but", the reason through the same example, one check, the answer.
        "plain": "Start from a puzzle",
        "plain_hint": "For any learner: an everyday puzzle, why the obvious guess fails, then the idea that explains it.",
        "level": "foundation",
        "for": "Anyone meeting the idea, Classes 6-10. One idea told as one story.",
        "promise": "Opens on something you have seen and a question about it, shows why the obvious guess is not quite right, then explains the idea through that same example and answers the question.",
        "voice": ("Talk to 'you' and 'we' in full joined sentences of mostly 12 to 25 words, like a teacher thinking aloud. "
                  "Every sentence follows from the one before: it picks up a word or result of the sentence before, or "
                  "says why it comes next (so, because, which means, but). Never read the lesson plan aloud: no chapter "
                  "titles, no 'pause on that', 'your turn', 'say it back', 'predict before you look', no lists."),
        "stops": ["hook", "check"],
        # Not offered in the intake's "kind of video" question yet: chosen by giving "framework": "story" in a brief.
        "offered": False,
        "stages": [
            {"role": "hook", "title": "The puzzle",
             "job": "Open on one concrete thing the learner has seen or can picture (the lesson's one example, with its numbers), and a question about it they want answered. Say what most people would expect or guess, and why that guess feels right."},
            {"role": "turn", "title": "Why the guess is not quite right",
             "job": "Turn it with a 'but': show on the same example why the expectation fails, so the idea is needed to explain the surprise. If a known mistake is given, it is this guess."},
            {"role": "explain", "title": "What is really going on",
             "job": "Explain the idea through that same example, step by step, each step with its reason. Give the reason before the name: show why it must be so, then name it or write the formula, each symbol tied to a part of the example."},
            {"role": "check", "title": "One more case",
             "job": "Check understanding once: one real question about a slightly different case, a moment to think, then the answer with its reason."},
            {"role": "payoff", "title": "The answer",
             "job": "Answer the opening question in one or two plain sentences, and say the key idea in one sentence so it can be remembered. Re-explain nothing."},
        ],
    },
]

BY_ID = {f["id"]: f for f in FRAMEWORKS}
#: The frameworks a requester is asked to choose between (one per level).
OFFERED = [f for f in FRAMEWORKS if f.get("offered", True)]
_LEVEL_DEFAULT = {"foundation": "concrete_first", "standard": "worked_examples", "advanced": "why_it_works"}
#: The stage role that owns the known misconception in each framework.
MISCONCEPTION_ROLE = {"concrete_first": "recap", "worked_examples": "refutation", "why_it_works": "conflict",
                      "story": "turn"}


def get(framework_id: str) -> dict:
    return BY_ID.get(framework_id) or BY_ID["worked_examples"]


def recommend(level: str | None) -> str:
    return _LEVEL_DEFAULT.get((level or "").lower(), "worked_examples")


def misconception_stage(framework: dict) -> dict:
    role = MISCONCEPTION_ROLE.get(framework["id"], "recap")
    return next((s for s in framework["stages"] if s["role"] == role), framework["stages"][-1])
