"""storyflow: the story checks measured on YouTube explainers (evals/explainers)."""
from lessonforge.harness import critic, storyflow


def _lesson(*beats, mode=None):
    lesson = {"chapters": [{"id": "c1", "beats": [{"id": f"b{i}", "narration": n} for i, n in enumerate(beats, 1)]}]}
    if mode:
        lesson["brief"] = {"mode": mode}
    return lesson


GOOD = ("Light slows down when it goes from air into water. Because it slows, the edge of the beam that reaches the "
        "water first falls behind the rest of the beam. So the beam turns towards the normal as it enters the water.")


def test_plan_said_aloud_is_a_major_story_finding():
    found = storyflow.story_gate(_lesson(GOOD, "So does the beam bend when it goes straight down into water? Pause on that."))
    plan = [f for f in found if "plan aloud" in f["what"]]
    assert [f["beat"] for f in plan] == ["b2"] and plan == found
    assert plan[0]["severity"] == "major" and plan[0]["what"].startswith("story:")


def test_jumps_are_reported_not_rewritten():
    jumpy = _lesson(GOOD + " Bananas contain potassium, an essential mineral for muscles.")
    assert storyflow.story_gate(jumpy) == []               # too unreliable to send a rewrite after (scramble test)
    rep = storyflow.report(storyflow.lesson_sentences(jumpy))
    assert rep["jumps"] == ["Bananas contain potassium, an essential mineral for muscles."]
    assert storyflow.report(storyflow.lesson_sentences(_lesson(GOOD)))["jumps"] == []


def test_a_pasted_script_is_spoken_as_written():
    assert storyflow.story_gate(_lesson("Pause on that.", mode="script")) == []


def test_measures_and_report():
    sents = storyflow.lesson_sentences(_lesson(GOOD, GOOD.replace("water", "glass")))
    m = storyflow.measure(sents)
    assert m["sentences"] == 6 and 0 <= m["jump_rate"] <= 1 and m["cause_per_100w"] > 0
    assert set(storyflow.report(sents)) == {"measures", "plan_aloud", "jumps"}


def test_the_gate_is_off_unless_switched_on(monkeypatch):
    monkeypatch.delenv("HARNESS_STORY_GATE", raising=False)
    assert not storyflow.enabled()
    monkeypatch.setenv("HARNESS_STORY_GATE", "1")
    assert storyflow.enabled()
    assert critic.storyflow is storyflow
