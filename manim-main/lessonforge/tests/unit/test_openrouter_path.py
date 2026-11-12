"""Spend ledger, Gemini TTS spec parsing, word alignment and the script critic — all offline."""
import json

import pytest

from lessonforge import spend
from lessonforge.harness import critic, frameworks, writer
from lessonforge.longform import align
from lessonforge.longform.speech import OpenRouterTTSBackend, get_backend


@pytest.fixture
def ledger(tmp_path, monkeypatch):
    path = tmp_path / "spend.jsonl"
    monkeypatch.setenv("OPENROUTER_LEDGER", str(path))
    monkeypatch.setenv("OPENROUTER_BUDGET_USD", "1.00")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)  # no remote check
    return path


def test_ledger_records_sums_and_enforces_the_budget(ledger):
    spend.record("chat", "google/gemini-3.8-flash", 0.40, prompt_tokens=10, completion_tokens=20, reasoning_tokens=5)
    spend.record("tts", "google/gemini-3.8-flash-lite-tts", 0.55, seconds=60, generation_id="gen-x", estimated=True)
    assert spend.spent() == pytest.approx(0.95)
    assert spend.last()["kind"] == "tts"
    spend.check(estimate=0.04)  # still inside
    with pytest.raises(spend.BudgetExceeded):
        spend.check(estimate=0.06, what="one more clip")
    s = spend.summary()
    assert s["calls"] == 2 and s["remaining"] == pytest.approx(0.05)
    assert s["by_kind"]["tts"]["seconds"] == 60 and s["by_model"]["google/gemini-3.8-flash"]["reasoning_tokens"] == 5
    assert "google/gemini-3.8-flash-lite-tts" in spend.format_summary()
    # A corrupt line never takes the ledger down
    ledger.write_text(ledger.read_text() + "{not json\n")
    assert spend.summary()["calls"] == 2


def test_a_budget_raised_while_the_server_runs_applies_to_the_next_call(ledger, monkeypatch, tmp_path, capsys):
    """Raising the budget must not need a restart: a restart kills the lesson being generated."""
    from lessonforge import cli
    spend.record("chat", "google/gemini-3.8-flash", 0.98)
    with pytest.raises(spend.BudgetExceeded):
        spend.check(estimate=0.05)
    # The environment of this "server" still says 1.00; the file next to the ledger wins.
    assert spend.set_budget(2.0) == 2.0 and spend.budget() == 2.0 and spend.budget_file().parent == ledger.parent
    spend.check(estimate=0.05)
    assert spend.summary()["remaining"] == pytest.approx(1.02)
    # A damaged or nonsensical file falls back to the environment instead of removing the guard.
    for junk in ("{not json", '{"budget_usd": "lots"}', '{"budget_usd": -5}', "[]", '{"budget_usd": true}'):
        spend.budget_file().write_text(junk)
        assert spend.budget() == 1.0, junk
    with pytest.raises(ValueError):
        spend.set_budget(-1)
    # The command: "+10" adds to the cap, a bare number sets it, and .env is kept in step.
    spend.budget_file().unlink()
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text("OPENROUTER_API_KEY=k\nOPENROUTER_BUDGET_USD=1\nOTHER=x\n")
    monkeypatch.setattr("dotenv.load_dotenv", lambda *a, **k: False)       # the test's environment stays as set above
    assert cli.main(["budget", "+10"]) == 0 and spend.budget() == 11.0
    assert (tmp_path / ".env").read_text() == "OPENROUTER_API_KEY=k\nOPENROUTER_BUDGET_USD=11\nOTHER=x\n"
    assert "$1.00 -> $11.00" in capsys.readouterr().out
    assert cli.main(["budget", "20"]) == 0 and spend.budget() == 20.0
    assert cli.main(["budget", "plenty"]) == 2 and spend.budget() == 20.0
    assert cli.main(["budget"]) == 0 and "of $20.00" in capsys.readouterr().out


def test_no_budget_means_no_guard(ledger, monkeypatch):
    monkeypatch.delenv("OPENROUTER_BUDGET_USD")
    spend.record("chat", "m", 99.0)
    spend.check(estimate=1000)  # nothing raised


def test_gemini_tts_spec_parsing():
    b = get_backend("gemini:lite/Puck|warm teacher, pause after questions")
    assert isinstance(b, OpenRouterTTSBackend)
    assert b.model == "google/gemini-3.8-flash-lite-tts" and b.voice == "Puck"
    assert b.instructions == "warm teacher, pause after questions"
    assert b.cache_key() != get_backend("gemini:lite/Puck").cache_key()  # instructions change the audio
    assert get_backend("gemini:flash").model == "google/gemini-3.8-flash-tts"
    with pytest.raises(ValueError):
        get_backend("gemini:pro/Kore")


def test_align_words_matches_interpolates_and_reports_coverage():
    script = "Look at this ladder. It is five metres long, and its foot is three metres from the wall.".split()
    # The recogniser wrote the numbers as digits and dropped one word.
    heard_text = "Look at this ladder. It is 5 meters long, and its foot is 3 meters from the wall."
    heard = [{"word": w, "start": 0.3 * i, "end": 0.3 * i + 0.25} for i, w in enumerate(heard_text.split())]
    del heard[4]  # "is" is missing
    timings, coverage = align.align_words(script, heard)
    assert len(timings) == len(script)
    assert coverage > 0.8
    assert timings[0]["matched"] and timings[0]["start"] == 0.0
    assert not timings[4]["matched"]                     # the dropped word is interpolated...
    assert timings[3]["end"] <= timings[4]["start"] <= timings[5]["start"]   # ...between its neighbours
    assert all(timings[i]["start"] <= timings[i + 1]["start"] for i in range(len(timings) - 1))


def test_align_clip_uses_cache_and_builds_sentence_spans(tmp_path):
    text = "First sentence here. Second one follows."
    words = ["first", "sentence", "here", "second", "one", "follows"]
    cache = tmp_path / "clip.words.json"
    cache.write_text(json.dumps([{"word": w, "start": 0.5 * i, "end": 0.5 * i + 0.4} for i, w in enumerate(words)]))
    result = align.align_clip(text, tmp_path / "missing.wav", cache=cache)  # no STT call: cache hit
    assert result["trusted"] and result["coverage"] == 1.0
    s1, s2 = result["sentences"]
    assert s1["timing_source"] == "aligned" and s1["start"] == 0.0
    assert s2["start"] == pytest.approx(1.5) and s1["duration"] == pytest.approx(1.5)
    assert [w["word"] for w in s2["words"]] == ["second", "one", "follows"]
    shifted = align.shift(result["sentences"], 0.5, scale=2.0)
    assert shifted[1]["start"] == pytest.approx(3.5) and shifted[1]["words"][0]["start"] == pytest.approx(3.5)


def test_untrusted_alignment_is_labelled_not_used(tmp_path):
    cache = tmp_path / "c.json"
    cache.write_text(json.dumps([{"word": "completely", "start": 0, "end": 1}, {"word": "different", "start": 1, "end": 2}]))
    result = align.align_clip("Nothing here matches at all.", tmp_path / "x.wav", cache=cache)
    assert result["trusted"] is False and result["sentences"] == []


def _lesson(narrations):
    raw = {"anchor": "a ladder against a wall", "chapters": [
        {"title": "C", "beats": [{"narration": n, "steps": [{"say": n.split()[0], "show": "x", "kind": "point"}]}
                                 for n in narrations]}]}
    brief = {"topic": "Pythagoras", "goal": "g", "duration_minutes": 2, "misconception": "adding sides"}
    return writer.discipline(raw, brief, frameworks.get("worked_examples"))


def test_arithmetic_lint_catches_a_wrong_sum_in_words_and_digits():
    lesson = _lesson(["Nine plus sixteen gives twenty-five. Three squared is nine.",
                      "Six squared is thirty-four, so 6 times 8 equals 48 and the square root of one hundred is ten."])
    results = critic.arithmetic_lint(lesson)
    said = {r["text"].lower(): r["ok"] for r in results}
    assert said["nine plus sixteen gives twenty-five"] is True
    assert said["three squared is nine"] is True
    assert said["six squared is thirty-four"] is False
    # digits never reach the voice: the script clean-up writes them out, and the lint reads the words
    assert next(ok for text, ok in said.items() if text.startswith("six times eight equals forty-eight")) is True
    assert not any(ch.isdigit() for r in results for ch in r["text"])
    assert said["square root of one hundred is ten"] is True


def test_claim_checker_is_whitelisted():
    assert critic.check_claim("9 + 16 == 25") is True
    assert critic.check_claim("math.isclose(math.sqrt(3**2 + 4**2), 5)") is True
    assert critic.check_claim("3 + 4 == 5") is False
    assert critic.check_claim("__import__('os').system('true')") is None
    assert critic.check_claim("open('/etc/passwd')") is None
    assert critic.check_claim("not valid python ((") is None


def test_critic_applies_text_only_edits_and_keeps_beat_count():
    lesson = _lesson(["Three plus four equals eight, so the ladder is eight metres.",
                      "Next we square both legs."])

    reviews = []

    def reviewer(prompt, system):
        assert "[beat 01]" in prompt and "SHOW (" in prompt
        reviews.append(prompt)
        if len(reviews) == 2:        # the edited text is reviewed again; this time it is clean
            assert "equals seven" in prompt
            return {"scores": {"conceptual_accuracy": 4, "visual_truthfulness": 4, "explanatory_clarity": 3, "pedagogy": 3},
                    "findings": [], "claims": [{"beat": "01", "claim": "three plus four equals seven", "python": "3 + 4 == 7"}],
                    "edits": [], "summary": "fixed"}
        return {"scores": {"conceptual_accuracy": 1, "visual_truthfulness": 4, "explanatory_clarity": 3, "pedagogy": 3},
                "findings": [{"severity": "critical", "beat": "01", "what": "3+4 is not 8", "fix": "say seven"}],
                "claims": [{"beat": "01", "claim": "three plus four equals eight", "python": "3 + 4 == 8"}],
                "edits": [{"beat": "01", "narration": "Three plus four equals seven, so the path is seven metres.",
                           "steps": [{"say": "seven metres", "show": "3 + 4 = 7", "kind": "math", "highlight": True}]}],
                "summary": "one arithmetic slip"}

    report = critic.verify(lesson, reviewer, log=lambda *_: None)
    beats = [b for c in lesson["chapters"] for b in c["beats"]]
    assert len(beats) == 2 and beats[0]["narration"].startswith("Three plus four equals seven")
    assert beats[0]["steps"][0]["say"] == "seven metres" and beats[0]["equation"] == "3 + 4 = 7"
    assert report["beats_rewritten"] == ["01"] and len(reviews) == 2
    # the scores and claims reported are those of the EDITED script, checked a second time
    assert report["scores"]["conceptual_accuracy"] == 4 and report["claims_failed"] == [] and report["status"] == "passed"
    assert report["rounds"][0]["scores"]["conceptual_accuracy"] == 1 and report["rounds"][0]["edits_applied"] == ["01"]
    assert report["arithmetic_after_edits"] == {"checked": 1, "failed": 0}
    assert lesson["verification"] is report


def test_critic_without_a_model_still_lints():
    lesson = _lesson(["Two plus two equals five."])
    report = critic.verify(lesson, None, log=lambda *_: None)
    assert report["status"] == "needs_review" and len(report["claims_failed"]) == 1


def test_reviewer_beat_ids_are_normalised_and_an_open_critical_finding_gets_one_rewrite_round():
    lesson = _lesson(["At sixty-four slices the edges become flat, straight lines. It is a true rectangle.",
                      "Next we measure the long side."])
    calls = []

    def reviewer(prompt, system):
        calls.append(system[:40])
        if system == critic.REVISE_SYSTEM:
            assert "[beat 01]" in prompt and "FOUND:" in prompt and "true rectangle" in prompt
            return {"edits": [{"beat": "beat-01", "narration": "At sixty-four slices the edges look almost straight. "
                                                            "The shape is very close to a rectangle.",
                               "steps": [{"say": "look almost straight", "show": "Nearly a rectangle", "kind": "key"}]}]}
        if len(calls) == 1:      # first review: a critical finding, written the way a model writes ids, and no edit
            return {"scores": {"conceptual_accuracy": 2, "visual_truthfulness": 3, "explanatory_clarity": 3, "pedagogy": 3},
                    "findings": [{"severity": "critical", "beat": "beat-01", "what": "a finite cut is not a true rectangle",
                                  "fix": "say it approaches a rectangle"}], "claims": [], "edits": [], "summary": "one overclaim"}
        assert "very close to a rectangle" in prompt          # the second review reads the rewritten text
        return {"scores": {"conceptual_accuracy": 4, "visual_truthfulness": 4, "explanatory_clarity": 3, "pedagogy": 3},
                "findings": [], "claims": [], "edits": [], "summary": "fine now"}

    report = critic.verify(lesson, reviewer, log=lambda *_: None)
    assert len(calls) == 3 and report["status"] == "passed" and report["critical_unresolved"] == 0
    assert report["beats_rewritten"] == ["01"] and [r["open_critical_or_major"] for r in report["rounds"]] == [1, 0]
    beat = lesson["chapters"][0]["beats"][0]
    assert "very close to a rectangle" in beat["narration"] and beat["steps"][0]["say"] == "look almost straight"
    assert critic.beat_id("beat 2", {"01", "02"}) == "02" and critic.beat_id(1, {"01"}) == "01"
    assert critic.beat_id("chapter recap", {"01"}) == "chapter recap"


def test_a_rewrite_that_changes_nothing_stops_the_loop_and_the_finding_stays_open():
    lesson = _lesson(["The bottom number never changes when we add fractions."])
    calls = []

    def reviewer(prompt, system):
        calls.append(1)
        if system == critic.REVISE_SYSTEM:
            return {"edits": []}
        return {"scores": {}, "findings": [{"severity": "major", "beat": "01", "what": "false as a rule", "fix": ""}],
                "claims": [], "edits": [], "summary": ""}

    report = critic.verify(lesson, reviewer, log=lambda *_: None)
    assert len(calls) == 2 and report["status"] == "needs_review" and report["major_unresolved"] == 1


def test_arithmetic_lint_does_not_judge_the_tail_of_a_longer_expression():
    lesson = _lesson(["Twenty-two over seven times fourteen gives forty-four.",          # correct as a whole
                      "So seven times fourteen gives ninety-eight, and two plus two is five."])
    results = {r["text"].lower(): r["ok"] for r in critic.arithmetic_lint(lesson)}
    assert "seven times fourteen gives forty-four" not in results                         # not read out of context
    assert results == {"seven times fourteen gives ninety-eight": True, "two plus two is five": False}


def test_a_claim_is_checked_with_exact_fractions_not_floats():
    # seen 2026-10-19: four true claims of a Monty Hall lesson ("2/3 == 1 - 1/3") failed in floats
    from lessonforge.harness.critic import check_claim
    assert check_claim("2/3 == 1 - 1/3") is True and check_claim("1/3 + 1/3 + 1/3 == 1") is True
    assert check_claim("0.1 + 0.2 == 0.3") is True and check_claim("math.sqrt(2) ** 2 == 2") is True
    assert check_claim("2/3 == 0.67") is False and check_claim("20 / 2 == 15") is False
    assert check_claim("__import__('os')") is None and check_claim("open('x')") is None


def test_a_claim_the_reviewers_own_check_calls_false_is_checked_again_alone():
    """The Moon lesson (2026-10-19): true sentences checked as '0 - 1 == 1' failed the lesson's correctness."""
    from lessonforge.harness import critic
    claims = [{"beat": "05", "claim": "A Moon that never turned would show every side over one orbit.", "python": "0 - 1 == 1", "result": False},
              {"beat": "06", "claim": "Two thirds plus one third is one.", "python": "2/3 + 1/3 == 2", "result": False},
              {"beat": "07", "claim": "Half of ten is five.", "python": "10/2 == 5", "result": True}]
    asked = []

    def model(prompt, system):
        asked.append(prompt)
        return {"python": "abs(0 - 1) == 1"} if "never turned" in prompt else {"python": "2/3 + 1/3 == 2"}
    critic._check_again(claims, model, log=lambda *_: None)
    assert claims[0]["result"] is None and claims[0]["python_again"] == "abs(0 - 1) == 1"     # the checks disagree
    assert claims[1]["result"] is False                                                     # false twice: still failed
    assert claims[2]["result"] is True and len(asked) == 2                                  # a true claim is not asked about
    sure = [{"beat": "05", "claim": "x", "python": "1 == 2", "result": False}]
    critic._check_again(sure, lambda p, s: {"python": "360 == 360"}, log=lambda *_: None)    # a check that cannot fail
    assert sure[0]["result"] is False
    stubborn = [{"beat": "05", "claim": "x", "python": "1 == 2", "result": False}]
    critic._check_again(stubborn, lambda p, s: {"claims": []}, log=lambda *_: None)          # an answer it cannot read
    assert stubborn[0]["result"] is False


def test_one_lesson_is_held_to_its_own_ceiling_and_its_rows_carry_its_id(ledger, monkeypatch):
    """A lesson stuck repeating a failing step stops at its own ceiling, long before the key's cap (2026-10-22)."""
    from concurrent.futures import ThreadPoolExecutor
    from lessonforge import knobs
    monkeypatch.setenv("OPENROUTER_BUDGET_USD", "100")
    monkeypatch.delenv("LESSONFORGE_LESSON_MAX_USD", raising=False)
    assert spend.lesson_cap(0.66) == 1.65 and spend.lesson_cap(0.1) == spend.LESSON_CAP_FLOOR
    assert spend.lesson_cap(None) is None
    spend.record("chat", "m", 0.30, note="before the lesson")             # not the lesson's
    with spend.lesson_scope("job-1", cap=0.50) as tally:
        spend.record("chat", "m", 0.20)
        # a stage's pool counts against the same lesson (knobs.wrap carries the tally)
        with ThreadPoolExecutor(max_workers=2) as pool:
            list(pool.map(knobs.wrap(lambda _: spend.record("vision", "v", 0.10)), range(2)))
        assert tally.calls == 3 and tally.spent == pytest.approx(0.40)
        spend.check(estimate=0.05)
        with pytest.raises(spend.BudgetExceeded, match="this lesson has spent 0.40 USD in 3 calls"):
            spend.check(estimate=0.20, what="one more review")
    spend.check(estimate=0.20)                                            # outside the lesson: only the cap applies
    rows = spend.entries()
    assert [r.get("job") for r in rows] == [None, "job-1", "job-1", "job-1"]
    s = spend.summary()
    assert s["in_lessons"] == pytest.approx(0.40) and s["outside_lessons"] == pytest.approx(0.30)
    assert "of which in lessons: $0.4000" in spend.format_summary(s)


def test_the_lesson_ceiling_can_be_set_or_switched_off_for_the_server(monkeypatch):
    monkeypatch.setenv("LESSONFORGE_LESSON_MAX_USD", "3")
    assert spend.lesson_cap(0.66) == 3.0 and spend.lesson_cap(None) == 3.0
    monkeypatch.setenv("LESSONFORGE_LESSON_MAX_USD", "0")
    assert spend.lesson_cap(0.66) is None
    monkeypatch.setenv("LESSONFORGE_LESSON_MAX_USD", "lots")                 # nonsense keeps the default
    assert spend.lesson_cap(0.66) == 1.65


def test_a_daily_cap_on_the_key_refuses_once_today_is_spent(ledger, monkeypatch):
    monkeypatch.setattr(spend, "remote_daily", lambda max_age=30.0: 4.90)
    spend.check(estimate=1.0)                                             # no daily cap set
    monkeypatch.setenv("OPENROUTER_DAILY_USD", "5")
    spend.check(estimate=0.05)
    with pytest.raises(spend.BudgetExceeded, match="spent 4.90 USD today"):
        spend.check(estimate=0.20)
    monkeypatch.setattr(spend, "remote_daily", lambda max_age=30.0: None)  # unknown: the other guards decide
    spend.check(estimate=0.20)
