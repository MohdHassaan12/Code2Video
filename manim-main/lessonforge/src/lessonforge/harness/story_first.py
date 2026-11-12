"""Story first: the words of a "story" lesson are written as one spoken script, then the screen is designed for them.

The script benchmark of 2026-11-03 (evals/explainers/README.md) scored the same story told two ways, blind:
written by one plain prompt (this one) it scored 7.25 to 8.25 out of 10; written chapter by chapter inside
``writer.write_lesson`` with the story framework it scored 4.75 to 6.0, on the same model. The writer's beat
and screen rules (steps, figures, depth, quiz cards) are needed for the screen, not for the words. So for the
story framework the words come from here, and ``scripted.script_lesson`` designs the screen around them while
keeping every word: the same route a script pasted by a person takes.

Only English lessons go this way for now; any other language keeps the writer.
"""
from __future__ import annotations

from .. import knobs
from . import intake, writer

PROMPT = """Write the spoken script of a short video that explains {topic} to {audience}. After watching, they should be able to {goal}.

How great explainers tell it (measured on 290 explainer videos from channels like Khan Academy and 3Blue1Brown):
1. Open on one concrete thing the viewer has seen or can picture, and a question about it that they want answered.
   Say what most people would expect or guess.
2. Turn it: "But..." show why that expectation is not quite right. The idea is needed to explain the surprise.
3. Explain the idea through that same example, step by step. Every sentence follows from the one before it: it picks
   up a word or the result of the sentence before, or says why it comes next (so, because, which means, but).
   Give the reason before the name: show why it must be so, then name it or write the formula.
4. Check understanding once: ask one real question about a slightly different case, give a moment, then answer it
   with its reason.
5. Close by answering the opening question in one or two plain sentences, and say the key idea so it can be
   remembered.

Voice: talk to "you" and "we", in full joined sentences of mostly 12 to 25 words, like a teacher thinking aloud.
Never read the lesson plan aloud (no "Pause on that", "Your turn", "Say it back", "Predict before you look", no
headings, no lists). Numbers only where they help; every number with its unit. Be correct: say what you assume, and
do not overstate a rule.{mistake}

About {words} words. Return JSON: {{"title": "3-7 word title", "script": "the spoken words only, as paragraphs separated by a blank line"}}."""

SYSTEM = "You write the spoken script of a short school explainer video. Return only the JSON asked for."


def applies(brief: dict) -> bool:
    """A story lesson in English, with the switch on (HARNESS_STORY_FIRST, on by default)."""
    return (brief.get("framework") == "story" and str(brief.get("language") or "en-IN").startswith("en")
            and knobs.get("HARNESS_STORY_FIRST", "1") != "0")


def prompt(brief: dict) -> str:
    minutes = max(intake.MIN_MINUTES, int(brief.get("duration_minutes") or 6))
    mistake = brief.get("misconception")
    return PROMPT.format(topic=brief.get("topic", ""), audience=brief.get("audience") or "school students",
                         goal=brief.get("goal") or f"explain {brief.get('topic', '')} in their own words",
                         words=writer.word_budget(minutes),
                         mistake=f"\nThe guess in step 1 is this common mistake: {mistake}" if mistake else "")


def words(brief: dict, llm) -> dict:
    """{"title", "script"} for the brief. ``llm(prompt, system)`` returns a dict (writer.default_llm). Raises ValueError."""
    got = llm(prompt(brief), SYSTEM) or {}
    script = str(got.get("script") or "").strip()
    if len(script.split()) < 60:
        raise ValueError("the story script came back empty or too short")
    return {"title": str(got.get("title") or brief.get("topic") or "").strip()[:80], "script": script}


def script_brief(brief: dict, written: dict) -> dict:
    """The brief as a script brief (scripted.prepare's shape), keeping what the rest of the job reads."""
    from . import scripted
    out = scripted.prepare({"script": written["script"], "topic": brief.get("topic") or written["title"],
                            "audience": brief.get("audience"), "language": brief.get("language") or "en-IN"})
    keep = {k: v for k, v in brief.items() if k not in out and k not in ("framework",)}
    return {**keep, **out, "story_first": True, "framework": "story"}
