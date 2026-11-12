"""Narration said plainly, the way lecturers on YouTube explain (the owner, 2026-10-20: "the narration is very complex
and cryptic"): notes, the lesson's plan said aloud and a question in every beat are findings; a lesson stops about
once a minute, decided by code; lecturer passages are chosen for how plainly they explain and a beat that copies one
is caught; captions come from the embedded player when the transcript API is refused. No model, no network."""
import sys
import types

from lessonforge.harness import frameworks, library, voice, writer


def lesson(*beats, minutes=3):
    return {"title": "t", "brief": {"duration_minutes": minutes, "language": "en-IN"},
            "chapters": [{"title": f"c{i}", "beats": [{"id": f"{i:02d}", "narration": text, "steps": []}]} for i, text in enumerate(beats, 1)]}


def kinds(found):
    return [f["what"] for f in found]


def test_notes_the_plan_said_aloud_and_two_questions_are_found():
    found = kinds(voice.findings(lesson(
        "The car is behind one of three doors, and you pick one. Does switching change your chance?",
        "So the claim is: switching wins two times in three. Test it by listing every place the car could be.",
        "Is it fifty-fifty now? Many people think so. What chance does door two have?")))
    assert any("plan aloud" in f and "claim" in f for f in found)
    assert any("like notes" in f for f in found)
    assert any("asks 2 questions" in f for f in found)


def test_plain_explanation_is_left_alone():
    found = voice.findings(lesson(
        "The car is behind one of three doors, and you pick one. Does switching change your chance?",
        "Your first pick hides the car one time in three, because every door is just as likely. So the other two "
        "doors hide it two times in three, and that does not change when the host opens one of them."))
    assert found == []


def test_a_lesson_that_asks_too_often_loses_the_questions_it_answers_itself():
    asks = "Why does it fall? Because gravity pulls it, and that pull is the same for every kilogram of it."
    many = lesson(*([asks] * 7))
    assert voice.questions_allowed(many) == 4
    found = [f for f in voice.findings(many) if "fit its length" in f["what"]]
    assert found and all(f["beat"] != "01" for f in found)          # the opening keeps its question
    assert not [f for f in voice.findings(lesson(asks, asks)) if "fit its length" in f["what"]]


def test_a_lesson_stops_about_once_a_minute_where_code_says():
    why = frameworks.get("why_it_works")
    plan = writer.stop_plan(why, 3)
    assert [why["stages"][i]["role"] for i in sorted(plan)] == ["problem", "conflict", "recap"]
    assert len(writer.stop_plan(why, 6)) == 5 and len(writer.stop_plan(why, 1)) == 2
    block = writer._stage_block(why, plan)
    assert block.count(writer.STOPS) == 3 and block.count(writer.NO_STOP) == 4
    assert writer.STOPS not in writer._stage_block(why)              # without a plan the block is what it was


PLAIN = ("So let's think about it. If you pick a door, you have a one in three chance, because the car could be "
         "behind any of them. And that means the other two doors together hold a two in three chance. When the host "
         "opens one of those two, he never shows the car, so all of that chance moves onto the last door. That's why "
         "switching works. It sounds strange, but we can check it by counting every case. ") * 2
CRYPTIC = ("Claim: switch wins. Test it? Change one thing: three doors. Why? Predict first: what then? Your turn: count. "
           "Doors: three. Cars: one. Odds? Half? No. Why not? ") * 4


def test_lecturer_passages_are_the_plainest_of_each_lecture_and_skip_automatic_captions():
    pack = {"sources": [{"id": "R1", "kind": "lecture", "title": "Numberphile: Monty Hall", "note": "English lecture"},
                        {"id": "R2", "kind": "lecture", "title": "Auto captions", "note": "English lecture"},
                        {"id": "S1", "kind": "textbook", "title": "NCERT"}],
            "chunks": [{"source": "R1", "text": CRYPTIC + PLAIN},
                       {"source": "R2", "text": "so you pick a door and then the host " * 40},
                       {"source": "S1", "text": PLAIN}]}
    found = voice.lecturer_examples(pack, "en-IN")
    assert [e["source"] for e in found] == ["Numberphile: Monty Hall"]
    assert "?" not in found[0]["text"] and "Claim" not in found[0]["text"]
    assert voice.plainness(PLAIN) > voice.plainness(CRYPTIC)
    block = voice.for_writer(found)
    assert "MANNER" in block and "NONE of their" in block and voice.for_writer([]) == ""


def test_a_beat_that_copies_a_lecture_is_found():
    examples = [{"source": "x", "text": PLAIN}]
    copying = lesson("If you pick a door, you have a one in three chance, because the car could be behind any.")
    own = lesson("Your door hides the car one time in three, since each door is just as likely.")
    assert voice.copied(copying, examples) and not voice.copied(own, examples)


def test_lecturer_passages_are_off_in_tests(monkeypatch):
    monkeypatch.setattr(library, "lectures_pack", lambda *a, **k: (_ for _ in ()).throw(AssertionError("network")))
    assert voice.examples_for({"topic": "Monty Hall"}, None, log=lambda *_: None) == []


def test_captions_come_from_the_embedded_player_one_track_only(monkeypatch):
    asked = []

    class Ydl:
        def __init__(self, options):
            asked.append(options["extractor_args"]["youtube"]["player_client"])

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def extract_info(self, url, download):
            assert not download
            return {"subtitles": {"en": [{"ext": "vtt", "url": "v"}, {"ext": "json3", "url": "own"}]},
                    "automatic_captions": {"en-orig": [{"ext": "json3", "url": "auto"}]}}

        def urlopen(self, url):
            asked.append(url)
            return types.SimpleNamespace(read=lambda: b'{"events": [{"segs": [{"utf8": "Hello there."}]}, '
                                                      b'{"segs": [{"utf8": "[Music] We pick a door."}]}]}')

    monkeypatch.setitem(sys.modules, "yt_dlp", types.SimpleNamespace(YoutubeDL=Ydl))
    got = library._captions_by_ytdlp("abc")
    assert got == {"text": "Hello there. We pick a door.", "language": "en", "generated": False, "why": ""}
    assert asked == [["web_embedded"], "own"]                  # the author's own track, and only that one


def test_a_rewrite_is_said_plainly_or_refused():
    from lessonforge.harness import critic
    plain = ("Weight is mass times g, so the heavy ball has twice the weight, which means twice the pull. But acceleration "
             "is force divided by mass, so the extra mass cancels the extra pull, and the rate stays g.")
    chopped = "Weight is mass times g, twice the pull. Force over mass, so the rate stays g."
    assert voice.chopped(plain, chopped) and not voice.chopped(plain, plain.split(". ")[0] + ".")   # dropping one is fine
    assert voice.unnoted("Socho: light kahan jaati hai? At 3:00 it rings.") == "Socho, light kahan jaati hai? At 3:00 it rings."
    assert voice.unnoted("Old: kept. New: changed.", keep="Old: kept.") == "Old: kept. New, changed."

    def edited(text):
        made = lesson(plain)
        critic.apply_edits(made, {"edits": [{"beat": "01", "narration": text}]}, log=lambda *_: None)
        return made["chapters"][0]["beats"][0]["narration"]

    assert edited(chopped) == plain
    assert edited("So the claim is that the extra mass cancels the extra pull, and the rate stays g for both balls.") == plain
    assert edited("Here is why, mass times g is the weight, so twice the mass means twice the pull, and the rate stays g.") != plain


def test_stops_the_plan_has_no_room_for_are_taken_out_and_their_words_kept():
    def stop(i, quiz=False):
        beat = {"id": i, "narration": f"Question {i}?", "thinking_pause_seconds": 5.0}
        return {**beat, "quiz": {"question": "q?"}} if quiz else beat
    made = {"chapters": [{"beats": [stop("01"), stop("02", quiz=True)]}, {"beats": [stop("03", quiz=True)]},
                         {"beats": [stop("04")]}]}
    writer.keep_planned_stops(made, {0, 2}, log=lambda *_: None)
    beats = {b["id"]: b for c in made["chapters"] for b in c["beats"]}
    assert [k for k, b in beats.items() if b["thinking_pause_seconds"]] == ["02", "04"]
    assert "quiz" not in beats["03"] and beats["03"]["narration"] == "Question 03?"
    assert made["stops"] == {"planned": [0, 2], "taken_out": ["01", "03"]}
