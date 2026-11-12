"""The weighted teaching rubric (harness/rubric.py) and the teacher's delivery rules: the judge quotes, code decides.

No network: the judge is a stub that answers as a model would, honestly and not.
"""
from lessonforge import knobs
from lessonforge.harness import critic, frameworks, rubric, voice, writer

BRIEF = {"topic": "Why heavy and light balls fall together", "audience": "Class 9", "goal": "explain equal fall",
         "framework": "why_it_works", "style": "tutor", "language": "en-IN", "duration_minutes": 3}


def beat(narration):
    return {"narration": narration, "steps": [{"say": " ".join(narration.split()[:3]), "show": "x", "kind": "point"}]}


def lesson():
    raw = {"anchor": "a steel ball and a rubber ball",
           "chapters": [
               {"beats": [beat("Drop a steel ball and a rubber ball from the same height at the same moment. "
                               "Which one do you think lands first?")]},
               {"beats": [beat("Both land together, because the heavier ball is pulled harder but is also harder to "
                               "get moving, so the two effects cancel exactly.")]},
               {"beats": [beat("So weight does not decide how fast a thing falls when the air hardly slows it.")]},
           ]}
    return writer.discipline(raw, BRIEF, frameworks.get("why_it_works"))


def judge(answer):
    def call(prompt, system):
        call.seen.append((prompt, system))
        return answer
    call.seen = []
    return call


def row(key, score, evidence=(), defect=None, repair=""):
    return {"key": key, "score": score, "evidence": list(evidence), "defect": defect, "repair": repair}


def test_off_by_default_listed_and_weights_add_to_a_hundred():
    assert not rubric.enabled() and "HARNESS_TEACHING_RUBRIC" in {c.id for c in knobs.CONTROLS}
    assert sum(rubric.WEIGHTS.values()) == 100 and rubric.WEIGHTS["conceptual_clarity"] == 20
    for key in rubric.WEIGHTS:
        assert key in rubric.system()


def test_a_high_score_counts_only_with_a_quote_that_is_really_said():
    les = lesson()
    ids = [b["id"] for c in les["chapters"] for b in c["beats"]]
    call = judge({"criteria": [
        row("conceptual_clarity", 4, [{"beat": ids[1], "quote": "the heavier ball is pulled harder but is also harder"}]),
        row("sequencing", 4, [{"beat": ids[0], "quote": "Chapter 1: Hook, then Predict, then Discover"}]),   # a heading
        row("focus_and_takeaway", 3),                                                                      # no quote
    ]})
    out = rubric.assess(les, call, critic._lesson_text(les), log=lambda *_: None)
    assert out["criteria"]["conceptual_clarity"]["score"] == 4
    assert out["criteria"]["sequencing"]["score"] == 2 and out["criteria"]["sequencing"]["given"] == 4
    assert out["criteria"]["focus_and_takeaway"]["score"] == 2
    assert set(out["capped"]) == {"sequencing", "focus_and_takeaway"}
    assert out["criteria"]["correctness"]["score"] is None                                   # not answered, not counted
    assert out["total"] == round(100 * (20 * 4 / 4 + 15 * 2 / 4 + 5 * 2 / 4) / 40, 1)
    assert out["findings"] == []                                                             # nothing low with a defect


def test_a_low_score_with_a_real_defect_becomes_a_finding_and_an_invented_one_does_not():
    les = lesson()
    ids = [b["id"] for c in les["chapters"] for b in c["beats"]]
    call = judge({"criteria": [
        row("misconceptions", 1, defect={"beat": ids[2], "quote": "weight does not decide how fast a thing falls",
                                          "what": "the wrong idea is never said and shown to fail"},
            repair="say 'heavier things fall faster' as a learner would and show the two balls landing together"),
        row("worked_examples_and_transfer", 2, defect={"beat": ids[1], "quote": "both land together because",
                                                        "what": "no second case"}, repair="add a feather in a vacuum"),
        row("demonstrations_and_visuals", 0, defect={"beat": ids[1], "quote": "a video of a feather and a hammer on the Moon",
                                                      "what": "nothing shown"}, repair="show it"),   # not in the words
    ]})
    out = rubric.assess(les, call, critic._lesson_text(les), log=lambda *_: None)
    found = {f["what"].split(" scored")[0]: f for f in out["findings"]}
    assert found["teach: misconceptions"]["severity"] == "major" and found["teach: misconceptions"]["beat"] == ids[2]
    assert found["teach: worked examples and transfer"]["severity"] == "minor"
    assert "teach: demonstrations and visuals" not in found
    assert out["criteria"]["demonstrations_and_visuals"]["defect"] is None


def test_a_failed_or_junk_look_leaves_the_review_as_it_was():
    les = lesson()

    def broken(prompt, system):
        raise RuntimeError("down")
    assert rubric.assess(les, broken, "x", log=lambda *_: None)["findings"] == []
    assert rubric.assess(les, judge(["not", "json"]), "x", log=lambda *_: None)["total"] is None


def test_the_review_carries_the_rubric_only_when_switched_on(monkeypatch):
    les = lesson()
    ids = [b["id"] for c in les["chapters"] for b in c["beats"]]
    answer = {"scores": {}, "findings": [], "claims": [], "edits": [], "summary": "",
              "criteria": [row("misconceptions", 0, defect={"beat": ids[2], "quote": "weight does not decide how fast",
                                                            "what": "never met"}, repair="meet it")]}
    assert "rubric" not in critic.review(les, judge(answer), log=lambda *_: None)
    monkeypatch.setenv("HARNESS_TEACHING_RUBRIC", "1")
    report = critic.review(les, judge(answer), log=lambda *_: None)
    assert "rubric" in report and "findings" not in report["rubric"]
    assert any(f["what"].startswith("teach: misconceptions") for f in report["findings"])


def test_stock_phrases_and_exclamations_are_findings_but_a_journey_is_not():
    raw = {"chapters": [{"beats": [beat("Let's dive in and see why the steel ball and the rubber ball land together.")]},
                        {"beats": [beat("The heavier ball is pulled harder, so it should win! But it is also harder to move.")]},
                        {"beats": [beat("A car's journey of ten kilometres takes twenty minutes, so its speed is thirty "
                                        "kilometres an hour.")]}]}
    les = writer.discipline(raw, BRIEF, frameworks.get("why_it_works"))
    what = [f["what"] for f in voice.findings(les)]
    assert any("stock phrase" in w and "dive in" in w.lower() for w in what)
    assert any("exclaims" in w for w in what)
    third = les["chapters"][2]["beats"][0]["id"]
    assert not any(f["beat"] == third and "stock phrase" in f["what"] for f in voice.findings(les))


def test_the_writer_is_told_to_sound_like_a_teacher_and_the_task_is_a_prediction():
    assert "SOUND LIKE A TEACHER" in writer._SYSTEM_WRITING and "never \"here is the\"" in writer._SYSTEM_WRITING
    assert "12 to 22 words" in writer._SYSTEM_WRITING
    assert not voice._PLAN_TALK.search("This surprises almost everyone.")


def test_a_rewrite_may_not_add_a_question():
    les = lesson()
    target = les["chapters"][1]["beats"][0]
    was = target["narration"]
    report = {"edits": [{"beat": target["id"], "narration": was + " So what would happen with a feather in a vacuum?",
                         "steps": None}]}
    critic.apply_edits(les, report, log=lambda *_: None)
    assert target["narration"] == was
    assert voice.asks_in("One? Two. Three?") == 2
