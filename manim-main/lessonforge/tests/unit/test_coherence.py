"""Whether a lesson holds together (harness/coherence.py): the judge quotes, code decides, and doubt reports nothing.

No network: the judge is a stub that answers as a model would, right and wrong.
"""
from lessonforge import knobs
from lessonforge.harness import coherence, critic, frameworks, writer

BRIEF = {"topic": "Area of a rectangle", "audience": "Class 6", "goal": "work out the area of a rectangle",
         "framework": "concrete_first", "style": "tutor", "language": "en-IN", "duration_minutes": 3}


def beat(narration):
    return {"narration": narration, "steps": [{"say": " ".join(narration.split()[:3]), "show": "x", "kind": "point"}]}


def lesson():
    raw = {"anchor": "a tile floor, 6 by 4", "glossary": [{"term": "unit square", "meaning": "a square of side one"},
                                                           {"term": "area", "meaning": "how many unit squares cover it"},
                                                           {"term": "perimeter", "meaning": "never spoken here"}],
           "chapters": [
               {"beats": [beat("How many tiles cover this floor? Look at the floor six tiles long and four tiles wide.")]},
               {"beats": [beat("Today we will learn about area. Count one unit square at a time along the first row."),
                           beat("A unit square is a square whose side is one centimetre, so each tile is one unit square.")]},
               {"beats": [beat("Six tiles in a row and four rows give twenty four tiles, so the area is twenty four.")]},
           ]}
    return writer.discipline(raw, BRIEF, frameworks.get("concrete_first"))


def judge(answer):
    seen = []

    def call(prompt, system):
        seen.append((prompt, system))
        return answer
    call.seen = seen
    return call


def test_off_by_default_and_the_review_is_what_it_was():
    assert knobs.get("HARNESS_COHERENCE", "0") == "0" and not coherence.enabled()
    assert "HARNESS_COHERENCE" in {c.id for c in knobs.CONTROLS}


def test_a_confirmed_restart_a_term_used_too_early_and_an_unanswered_question_are_findings():
    les = lesson()
    b = {x["id"]: x for c in les["chapters"] for x in c["beats"]}
    ids = list(b)
    call = judge({
        "seams": [{"chapter": 2, "opening": "Today we will learn about area", "picks_up": "", "verdict": "restarts"},
                  {"chapter": 3, "opening": "Six tiles in a row", "picks_up": "each tile is one unit square", "verdict": "continues"}],
        "terms": [{"term": "unit square", "explained_in": f"beat {ids[2]}", "quote": "A unit square is a square whose side is one"},
                  {"term": "area", "explained_in": "known", "quote": ""}],
        "opening": {"answered_in": "none", "quote": "", "belongs_in": ids[3]}})
    found = coherence.findings(les, call, log=lambda *_: None)
    what = [f["what"] for f in found]
    assert all(f["severity"] == "major" and f["what"].startswith("flow:") for f in found)
    assert any("chapter 2 starts the lesson again" in w for w in what)                     # the restart, on its first beat
    assert next(f for f in found if "starts the lesson again" in f["what"])["beat"] == ids[1]
    assert any("“unit square” is used here before" in w for w in what)                     # first used in beat 2, explained in 3
    assert next(f for f in found if "unit square" in f["what"])["beat"] == ids[1]
    assert any("never answers the question it opened with" in w for w in what)
    assert len(found) == 3                                                                 # chapter 3 continues: nothing
    prompt = call.seen[0][0]
    assert "TERMS: unit square; area" in prompt and "perimeter" not in prompt.split("TERMS:")[1]   # only terms it speaks
    assert "OPENING QUESTION: How many tiles cover this floor?" in prompt


def test_a_claim_code_cannot_confirm_reports_nothing():
    les = lesson()
    ids = [x["id"] for c in les["chapters"] for x in c["beats"]]
    call = judge({
        "seams": [{"chapter": 2, "opening": "words that are not there at all", "verdict": "jumps"},   # misquoted
                  {"chapter": 1, "opening": "How many tiles cover", "verdict": "restarts"},          # the first chapter
                  {"chapter": 9, "opening": "Six tiles in a row", "verdict": "jumps"}],              # no such chapter
        "terms": [{"term": "unit square", "explained_in": ids[2], "quote": "a quote the beat never says"},
                  {"term": "not a lesson term", "explained_in": "none"}],
        "opening": {"answered_in": ids[3], "quote": "so the area is twenty four"}})
    assert coherence.findings(les, call, log=lambda *_: None) == []


def test_a_judge_that_fails_or_a_one_chapter_lesson_costs_nothing_and_finds_nothing():
    les = lesson()

    def broken(prompt, system):
        raise RuntimeError("provider down")
    assert coherence.findings(les, broken, log=lambda *_: None) == []
    single = {**les, "chapters": les["chapters"][:1]}
    call = judge({})
    assert coherence.findings(single, call, log=lambda *_: None) == [] and call.seen == []


def test_the_review_carries_flow_findings_only_when_switched_on(monkeypatch):
    les = lesson()
    ids = [x["id"] for c in les["chapters"] for x in c["beats"]]
    answers = {"seams": [{"chapter": 2, "opening": "Today we will learn about area", "verdict": "restarts"}]}

    def model(prompt, system):
        if system == coherence.SYSTEM:
            return answers
        return {"scores": {}, "findings": [], "claims": [], "edits": []}
    off = critic.review(les, model, log=lambda *_: None)
    assert not any(f["what"].startswith("flow:") for f in off["findings"])
    monkeypatch.setenv("HARNESS_COHERENCE", "1")
    on = critic.review(les, model, log=lambda *_: None)
    flow = [f for f in on["findings"] if f["what"].startswith("flow:")]
    assert len(flow) == 1 and flow[0]["beat"] == ids[1]
