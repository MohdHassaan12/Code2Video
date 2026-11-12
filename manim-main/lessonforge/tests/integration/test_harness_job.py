"""One job through the WHOLE service path — script → verify → speech → render → assemble → check → done.

This is the test that was missing on 2026-10-08, when a change to the last step of
``service._run`` shipped without one job being run through it and cost a tester a
15-minute generation. It renders a real (tiny, silent, 480p) video with a stub
writer model, so it needs manim and ffmpeg and takes about half a minute:

    pytest tests/integration -q
"""
import json
import shutil
import time

import pytest

pytest.importorskip("manim")
if not shutil.which("ffmpeg"):
    pytest.skip("ffmpeg is required", allow_module_level=True)

from lessonforge.harness import service  # noqa: E402

BRIEF = {"topic": "Pythagorean theorem", "audience": "Class 8", "grade": 8, "level": "standard",
         "goal": "find a missing side", "framework": "worked_examples", "style": "tutor", "language": "en-IN",
         "duration_minutes": 2, "context": "a ladder against a wall", "misconception": "adding the sides"}


# One line per chapter, none sharing a phrase with another: a script that says the same thing in
# every chapter is now a finding (critic.repetition_gate), as it should be.
LINES = ["A ladder leans on a wall with its foot four metres out. Nine plus sixteen gives twenty-five. How long is the ladder?",
         "Draw the wall as one leg of a triangle. Mark the ground as the second leg below it. Which side faces the corner?",
         "Square each leg separately first. Add those two squares together next. What does that sum tell us?",
         "Name the longest side the hypotenuse now. It always sits opposite the right angle. Where is it here?",
         "Take the square root at the very end. Five metres comes out as the answer. Does that length look sensible?",
         "Try a rope tied to a pole instead. Its base is six and its height eight. What is the rope length?",
         "Say the three moves back in order. Square, add, then root. Which move do learners forget most?"]
SCENES = {2: "Two squares slide together and merge into one larger square", 3: "A triangle turns so its longest side faces the viewer"}


def stub_model(prompt, system, scenes=False):
    """Stands in for both the writer and the critic."""
    if "Score each rubric dimension" in system:
        return {"scores": {"conceptual_accuracy": 4, "visual_truthfulness": 4, "explanatory_clarity": 4, "pedagogy": 4},
                "findings": [], "claims": [{"beat": "01", "claim": "nine plus sixteen", "python": "9 + 16 == 25"}],
                "edits": [], "summary": "fine"}
    chapters = []
    for i, line in enumerate(LINES):
        first = " ".join(line.split()[:3])
        chapters.append({"title": f"Stage {i + 1}", "learning_goal": "g", "beats": [{
            "narration": line, "visual": "a ladder", "check": "look at the squares",
            "thinking_pause_seconds": 3 if i == 0 else 0,
            "quiz": {"question": "How long is the ladder?", "options": ["Five metres", "Seven metres", "Twenty-five metres"],
                     "answer_index": 0, "explain": "The square root of twenty-five is five."} if i == 0 else None,
            "figure": {"kind": "right_triangle", "a": 4, "b": 3, "unknown": "c"} if i == 0 else
                      ({"kind": "scene", "describe": SCENES[i]} if scenes and i in SCENES else None),
            "steps": [{"say": first, "show": "9 + 16 = 25" if i == 0 else f"Move {i + 1}", "kind": "math" if i == 0 else "point",
                       "highlight": True},
                      {"say": " ".join(line.split()[-3:]), "show": "Find the ladder" if i == 0 else f"Question {i + 1}",
                       "kind": "key", "highlight": False}]}]})
    return {"title": "Pythagoras in two minutes", "thesis": "t", "anchor": "a ladder against a wall",
            "glossary": [{"term": "hypotenuse", "meaning": "the longest side"}], "chapters": chapters}


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    monkeypatch.setenv("LESSONFORGE_HOME", str(tmp_path))
    monkeypatch.setenv("LESSONFORGE_ALIGN", "0")
    monkeypatch.setenv("HARNESS_VISION_REVIEW", "0")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    service._JOBS.clear()
    return tmp_path


def wait(job_id, seconds=240):
    deadline = time.time() + seconds
    while time.time() < deadline:
        job = service.get_job(job_id)
        if job["status"] in ("done", "failed"):
            return job
        time.sleep(1)
    raise AssertionError("the job did not finish in time")


def frames_of(root):
    """The frame every beat of a rendered lesson was laid out in, as its chapters' own records say."""
    return {record["layout"]["frame"] for audit in sorted((root / "output").glob("chapter_*_audit.json"))
            for record in json.loads(audit.read_text())["bounds"]}


def test_a_job_runs_to_a_playable_video_and_survives_a_restart(workspace, monkeypatch):
    # A finished lesson publishes itself for the viewer site (harness/publish.py); a folder stands in for Cloudflare R2.
    monkeypatch.setenv("LESSONFORGE_PUBLISH", "1")
    monkeypatch.setenv("LESSONFORGE_CLOUD_DIR", str(workspace / "cloud"))
    # With settings of its own (lessonforge.knobs): the switches a requester can set from the app ride on the job.
    settings = {"HARNESS_CRITIC_ROUNDS": "1", "LESSONFORGE_QUIZ_IN_VIDEO": "options"}
    started = service.start_job(dict(BRIEF), quality="l", voice="silent", llm=stub_model, settings=settings)
    assert started["settings"] == settings
    job = wait(started["job_id"])
    assert job["status"] == "done", (job["error"], job["progress"][-8:])
    root = workspace / "lessons" / job["job_id"]
    from lessonforge import cloud
    deadline = time.time() + 60          # the upload runs after the record says "done"
    while time.time() < deadline and not any(line.startswith("[publish]") for line in service.get_job(job["job_id"])["progress"]):
        time.sleep(0.5)
    published = cloud.objects().get_json(cloud.job_key(job["job_id"]))
    assert published and published["video_url"] == job["video_url"], service.get_job(job["job_id"])["progress"][-4:]
    assert cloud.objects().get_bytes(cloud.lesson_key(job["job_id"], job["video_url"].split("/", 3)[3])) is not None
    assert [row["job_id"] for row in cloud.objects().get_json(cloud.JOBS_KEY)["jobs"]] == [job["job_id"]]
    assert json.loads((root / "job.json").read_text())["settings"] == settings, "the settings are kept with the job"
    video = workspace / job["video_url"].lstrip("/")
    assert video.is_file() and video.stat().st_size > 20_000
    assert job["checks"]["status"] == "technical_checks_passed", job["checks"]["failed"]
    assert job["checks"]["chapters"] == 7 and len(job["chapters"]) == 7 and job["chapters"][0]["start"] == 0.0
    assert job["verification"]["status"] == "passed" and job["verification"]["claims_checked"] >= 1
    assert job["continuity"]["chapters_using_running_example"] >= 1 and job["continuity"]["cross_chapter_repeats"] == 0
    assert not [f for f in job["verification"]["findings"] if f["what"].startswith("repetition")]
    assert job["voice"] == "silent" and job["generated_by"] == "model"
    # The lesson says how it looks (longform/look.py) and every chapter was laid out that way: the frame a lesson
    # made now gets, no band kept for captions, and the dark page because its triangle is drawn by code.
    made = json.loads((root / "lesson.json").read_text())["look"]
    assert {k: made[k] for k in ("frame", "captions", "page", "working")} == {"frame": "stage", "captions": "outside", "page": "night",
                                                                                "working": "pinned"}
    assert any("[look]" in line and "captions under the video" in line for line in job["progress"])
    assert frames_of(root) == {"stage"}
    # Before the narration was made the lesson was previewed as stills (harness/compose.py): its code-drawn triangle
    # was tried enlarged and kept that way only because the preview showed no fault the first did not have.
    composed = json.loads((root / "composition.json").read_text())
    assert composed["stills"] >= 14 and set(composed["faults"]) == {"kept", "fill"} and composed["looked_at"] == 0
    assert made["pictures"] == composed["pictures"] == ("fill" if composed["faults"]["fill"] <= composed["faults"]["kept"] else "kept")
    assert job["composition"]["stills"] == composed["stills"] and "compose" in job["stages"]
    assert list((root / "preview" / composed["pictures"] / "stills").glob("c01_b01_*_end.jpg"))
    # The stage files of the shared storyboard, the compiled timeline, the quality report and the bundle
    # (longform/storyboard.py, timeline_compiler.py, qa.py), each from the lesson as it was made.
    out = root / "output"
    board = json.loads((out / "storyboard.json").read_text())
    assert len(board["beats"]) == 7 and board["gate"]["errors"] == 0, board["gate"]
    assert all(json.loads((out / name).read_text())["schema"] for name in ("lesson_spec.json", "teaching_plan.json"))
    sync = json.loads((out / "sync_timeline.json").read_text())
    assert sync["summary"]["steps"] == 14 and not [i for i in sync["issues"] if i["severity"] == "error"], sync["issues"]
    qa = json.loads((out / "qa_report.json").read_text())
    assert qa["status"] != "failed" and job["qa"]["status"] == qa["status"], [c for c in qa["checks"] if c["status"] == "fail"]
    bundled = {f["path"] for f in json.loads((out / "bundle.json").read_text())["files"]}
    assert {"lesson.json", "timeline.json", "output/storyboard.json", "output/qa_report.json",
            job["video_url"].split("/", 3)[3]} <= bundled, bundled
    # every file the client links to exists
    for key in ("captions_url", "review_url", "lesson_url", "interactions_url"):
        assert (workspace / job[key].lstrip("/")).is_file(), key
    sidecar = json.loads((root / "output" / "interactions.json").read_text())
    # every stub chapter ends by asking, but the lesson stops only where its plan says (writer.stop_plan: about once a
    # minute); the first chapter's stop carries answer choices
    assert job["interactions"] == len(sidecar["interactions"]) == 3 and len(sidecar["chapters"]) == 7
    choices = [q for q in sidecar["interactions"] if q["type"] == "mcq"]
    assert len(choices) == 1 and choices[0]["prompt"]["text"] == "How long is the ladder?"
    # one video, several ways of watching: the cuts are ranges of this video, and any of them exports as a file
    cut_ids = [c["id"] for c in job["cuts"]]
    assert cut_ids[0] == "full" and "revision" in cut_ids, cut_ids
    revision = next(c for c in job["cuts"] if c["id"] == "revision")
    assert 5 < revision["seconds"] < job["checks"]["duration_seconds"] - 5
    exported = service.export_cut(job["job_id"], "revision")
    clip = workspace / exported["video_url"].lstrip("/")
    assert clip.is_file() and (workspace / exported["captions_url"].lstrip("/")).is_file()
    import subprocess
    seconds = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                                    str(clip)], capture_output=True, text=True).stdout)
    assert abs(seconds - revision["seconds"]) < 0.6
    assert service.export_cut(job["job_id"], "full")["video_url"] == job["video_url"]
    with pytest.raises(KeyError):
        service.export_cut(job["job_id"], "nope")
    # the record is on disk and a restart changes nothing the client sees
    saved = json.loads((root / "job.json").read_text())
    assert saved["status"] == "done" and saved["video_url"] == job["video_url"]
    service._JOBS.clear()
    again = service.get_job(job["job_id"])
    assert again["status"] == "done" and again["video_url"] == job["video_url"] and again["checks"] == job["checks"]
    assert service.list_jobs()[0]["job_id"] == job["job_id"]


def test_a_failure_after_the_video_is_built_still_hands_the_video_over(workspace, monkeypatch):
    def boom(*args, **kwargs):
        raise TypeError("'Chapter' object is not subscriptable")
    monkeypatch.setattr(service, "write_interactions", boom)      # the exact step that crashed in production
    monkeypatch.setattr(service, "write_review", boom)
    started = service.start_job(dict(BRIEF), quality="l", voice="silent", llm=stub_model)
    job = wait(started["job_id"])
    assert job["status"] == "done" and job["video_url"], (job["error"], job["progress"][-6:])
    assert any("interactions] skipped" in line for line in job["progress"])
    assert job["interactions_url"] is None and job["review_url"] is None


def test_a_lesson_whose_animations_all_fail_stops_before_anything_is_narrated(workspace, monkeypatch):
    """2026-10-08: a safety check refused every animation of a lesson, and it went on to be narrated and
    rendered as eight minutes of text on a dark screen. When ALL of them fail the cause is systematic."""
    def none_made(lesson_dict, log=print, generate=None, why=None):
        return {"asked": 2, "made": 0, "failed": list(SCENES.values()), "retried": 2, "simplified": 0,
                "reasons": {SCENES[2]: "refused before running: forbidden construct 'os.'"}}

    monkeypatch.setattr(service, "resolve_scenes", none_made)
    started = service.start_job(dict(BRIEF), quality="l", voice="silent",
                                llm=lambda prompt, system: stub_model(prompt, system, scenes=True))
    job = wait(started["job_id"])
    assert job["status"] == "failed" and job["stage"] == "visuals", (job["status"], job["stage"], job["error"])
    assert "None of the 2 animations" in job["error"] and "forbidden construct" in job["error"]
    assert "Nothing was narrated" in job["error"] and job["video_url"] is None
    root = workspace / "lessons" / job["job_id"]
    assert not (root / "timeline.json").exists() and not any((root / "audio").glob("*")) if (root / "audio").exists() else True
    assert job["scenes"] == {"asked": 2, "made": 0, "failed": list(SCENES.values()), "retried": 2, "simplified": 0,
                             "reasons": {SCENES[2]: "refused before running: forbidden construct 'os.'"}}


# ── a script the requester wrote ─────────────────────────────────────────────

SCRIPT = """# Finding the ladder

A ladder leans on a wall. [draw the wall, the ground and the ladder as a right triangle]
Its foot is 4 metres from the wall and it reaches 3 metres up. How long is the ladder?

## The working
Square each leg: 4 squared is 16 and 3 squared is 9. Add them and you get 25.
The square root of 25 is 5, so the ladder is 5 metres long.
"""


def script_model(prompt, system):
    """The director (plan, then the screen for each part) and the reviewer of a pasted script."""
    from lessonforge.harness import scripted
    if "Score each rubric dimension" in system:
        return {"scores": {"conceptual_accuracy": 4, "visual_truthfulness": 3, "explanatory_clarity": 3, "pedagogy": 3},
                "findings": [{"severity": "major", "beat": "02", "what": "the root is taken without saying why", "fix": "say why"}],
                "claims": [{"beat": "02", "claim": "sixteen plus nine", "python": "16 + 9 == 25"}],
                "edits": [{"beat": "02", "narration": "A reviewer's own sentence that the author never wrote at all."}],
                "summary": "sound"}
    if system is scripted.PLAN_SYSTEM:
        return {"title": "ignored: the script has its own", "thesis": "find the ladder", "anchor": "a ladder on a wall",
                "picture_plan": "One right triangle throughout.", "chapters": [],
                "try_it": {"title": "A ruler ladder", "kind": "hands", "materials": ["a ruler", "a book", "squared paper"],
                           "stands_for": "The ruler is the ladder, the book is the wall.",
                           "predict": "Will the ruler be longer or shorter than the two distances added?",
                           "steps": ["Stand the book up.", "Lean the ruler on it, 4 squares out and 3 squares up.",
                                     "Measure the ruler between the two points."],
                           "observe": "It measures 5 squares, less than 4 plus 3.",
                           "question": "Why is the ladder shorter than 4 plus 3?",
                           "expected": "It goes straight across; its square is 16 plus 9, so it is 5.",
                           "write": "Square, add, then take the root.", "in_class": "Pairs, one ruler each, five minutes."}}
    asked = prompt.split("these beats, every one of them:")[1].split("JSON shape")[0]
    out = []
    for line in asked.splitlines():
        if not line.startswith("["):
            continue
        words = line[5:].split()
        out.append({"id": line[1:3], "visual": "the triangle", "depth": "core",
                    "figure": {"kind": "right_triangle", "a": 4, "b": 3, "labels": {"a": "4 m", "b": "3 m", "c": "?"}, "unknown": "c"},
                    "quiz": {"question": "How long is the ladder?", "options": ["7 m", "5 m", "25 m"], "answer_index": 1,
                             "explain": "Square, add, then root."},
                    "steps": [{"say": " ".join(words[:3]), "show": "a^2 + b^2 = c^2", "kind": "math", "highlight": True, "focus": "c"},
                              {"say": " ".join(words[-3:]), "show": "Find the ladder", "kind": "key", "focus": "a"}]})
    return {"beats": out}


def test_a_pasted_script_becomes_a_video_with_its_words_untouched(workspace):
    from lessonforge.harness import scripted
    started = service.start_job({"mode": "script", "script": SCRIPT, "audience": "Class 8"}, quality="l",
                                voice="silent", llm=script_model)
    assert started["title"] == "Finding the ladder" and started["brief"]["language"] == "en-IN"
    job = wait(started["job_id"])
    assert job["status"] == "done", (job["error"], job["progress"][-8:])
    root = workspace / "lessons" / job["job_id"]
    assert (workspace / job["video_url"].lstrip("/")).stat().st_size > 20_000
    assert job["checks"]["status"] == "technical_checks_passed", job["checks"]["failed"]
    lesson = json.loads((root / "lesson.json").read_text())
    said = [b["narration"] for c in lesson["chapters"] for b in c["beats"]]
    assert said == [b["narration"] for s in scripted.parse_script(SCRIPT)["sections"] for b in s["beats"]]
    assert said[0].endswith("How long is the ladder?") and "four metres" in said[0] and "draw the wall" not in " ".join(said)
    assert [c["title"] for c in job["chapters"]] == ["OPENING", "THE WORKING"] and job["title"] == "Finding the ladder"
    assert job["generated_by"] == "script" and job["script"]["parts_from"] == "headings" and job["script"]["undesigned"] == []
    # the reviewer's finding is reported, its rewrite is not applied: the author did not ask for one
    check = job["verification"]
    assert check["status"] == "needs_review" and check["edits_applied"] == [] and check["claims_checked"] >= 1
    assert [f["what"] for f in check["findings"] if f["severity"] == "major"] == ["the root is taken without saying why"]
    assert any("your words were left as written" in line for line in job["progress"])
    # the script asks one question: the player gets it, with thinking time in the video
    sidecar = json.loads((root / "output" / "interactions.json").read_text())
    assert [q["type"] for q in sidecar["interactions"]] == ["mcq"] and sidecar["interactions"][0]["prompt"]["text"] == "How long is the ladder?"
    assert service.list_jobs()[0]["mode"] == "script"
    # "Try again" posts the stored brief back, and a restart loses nothing
    assert scripted.prepare(job["brief"]) == job["brief"] and job["brief"]["script_edit"] == "keep"
    service._JOBS.clear()
    assert service.get_job(job["job_id"])["script"] == job["script"]
    # the task to do by hand travels with the lesson, and an answer is kept beside it
    from lessonforge.harness import tryit
    assert job["try_it"]["title"] == "A ruler ladder" and len(job["try_it"]["steps"]) == 3 and job["try_it_answers"] == 0
    assert "card" not in job                                   # a pasted script has no teaching card
    kept = tryit.store(job["job_id"], {"prediction": "shorter", "observation": "five squares", "answer": "it cuts across"})
    assert kept["count"] == 1 and kept["expected"].startswith("It goes straight across")
    service._JOBS.clear()
    assert service.get_job(job["job_id"])["try_it_answers"] == 1
    # a lesson made by another process was read as interrupted while it ran; once its files are there it is done
    service._JOBS[job["job_id"]] = {**job, "status": "failed", "error": service.INTERRUPTED, "video_url": None}
    again = service.get_job(job["job_id"])
    assert again["status"] == "done" and again["video_url"] == job["video_url"] and again["error"] is None


def test_a_lesson_being_made_stops_at_its_next_stage_when_it_is_removed(workspace):
    """"Stop and remove this run" pressed while the script is being written: the run ends at the stage boundary,
    nothing is narrated or rendered, and its folder is moved aside rather than deleted."""
    def model(prompt, system):
        service.remove_job(next(iter(service._JOBS)))          # pressed during the script stage
        return stub_model(prompt, system)

    started = service.start_job(dict(BRIEF), quality="l", voice="silent", llm=model)
    moved = workspace / "removed" / started["job_id"]
    deadline = time.time() + 60
    while time.time() < deadline and not moved.is_dir():
        time.sleep(0.2)
    assert moved.is_dir() and not (workspace / "lessons" / started["job_id"]).exists()
    record = json.loads((moved / "job.json").read_text())
    assert record["status"] == "failed" and record["error"] == service.STOPPED and record["stage"] == "script"
    assert (moved / "lesson.draft.json").is_file()                   # what was written before the stop is kept
    assert not (moved / "audio").exists() and not (moved / "timeline.json").exists() and not (moved / "lesson.json").exists()
    assert started["job_id"] not in service._JOBS and service.list_jobs() == []
    with pytest.raises(KeyError):
        service.get_job(started["job_id"])


def test_a_finished_lesson_is_narrated_again_without_planning_drawing_or_reviewing_it_again(workspace, monkeypatch):
    """"Add the voice": a new lesson from a finished one's script and pictures, the old one left as it is."""
    first = wait(service.start_job({"mode": "script", "script": SCRIPT, "audience": "Class 8"}, quality="l",
                                   voice="silent", llm=script_model)["job_id"])
    assert first["status"] == "done", first["error"]

    def no_model(prompt, system):
        raise AssertionError("a voice job asked a model for something")

    # A lesson from before 2026-10-10 does not say how it looks. Narrated again it must come out in the frame it was
    # made and checked in, not in the one new lessons get: here the first lesson is made to be such a lesson.
    first_root = workspace / "lessons" / first["job_id"]
    assert frames_of(first_root) == {"stage"}
    as_made = json.loads((first_root / "lesson.json").read_text())
    assert as_made.pop("look")["frame"] == "stage"
    (first_root / "lesson.json").write_text(json.dumps(as_made), encoding="utf-8")

    started = service.narrate_again(first["job_id"], voice="silent", llm=no_model)
    assert started["job_id"] != first["job_id"] and started["brief"]["voice_for"] == first["job_id"]
    again = wait(started["job_id"])
    assert again["status"] == "done", (again["error"], again["progress"][-8:])
    old_root, new_root = workspace / "lessons" / first["job_id"], workspace / "lessons" / again["job_id"]
    assert json.loads((new_root / "lesson.json").read_text()) == json.loads((old_root / "lesson.json").read_text())
    assert frames_of(new_root) == {"columns"}                              # no look written: the frame as it was
    assert again["verification"] == first["verification"] and again["title"] == first["title"]
    assert again["checks"]["status"] == "technical_checks_passed" and again["try_it"] == first["try_it"]
    assert any("only the narration is made again" in line for line in again["progress"])
    assert (workspace / first["video_url"].lstrip("/")).is_file()            # the lesson it came from is untouched
    assert service.list_jobs()[0]["job_id"] == again["job_id"] and service.list_jobs()[0]["mode"] == "script"

    # With no voice that narrates, a voice job stops before the render and says why; a first run would go on, silent.
    monkeypatch.setattr(service, "voice_candidates", lambda language, prefer=None: ["silent"])
    refused = wait(service.narrate_again(first["job_id"], llm=no_model)["job_id"])
    assert refused["status"] == "failed" and "The narration could not be made" in refused["error"]
    assert "no narration voice is set up" in refused["error"] and refused["stage"] == "speech" and not refused["video_url"]

    with pytest.raises(KeyError):
        service.narrate_again("20990101-000000-nosuch")
    with pytest.raises(KeyError):
        service.narrate_again("../../etc")


def test_a_script_about_a_real_thing_is_rendered_around_the_prepared_picture(workspace, monkeypatch, tmp_path):
    """The plan asks the diagram service for a picture; the lesson is rendered with it, shown whole."""
    from PIL import Image
    from lessonforge.harness import scripted
    drawing = tmp_path / "whole.png"
    Image.new("RGB", (900, 610), "#bde3ff").save(drawing)
    asked = []

    def prepared(ask, brief, log=print):
        asked.append(ask)
        return {"ask": ask, "manifest": str(tmp_path / "manifest.json"), "parts": [], "names": {"x": "1. Evaporation"},
                "credit": "Art: the diagram service", "shown": "whole", "file": str(drawing)}
    monkeypatch.setattr(scripted, "prepared_picture", prepared)

    def model(prompt, system):
        answer = script_model(prompt, system)
        if system is scripted.PLAN_SYSTEM:
            return {**answer, "diagram_ask": "A ladder leaning on a wall"}
        if system is scripted.DIRECT_SYSTEM:
            assert "A PREPARED PICTURE is ready" in prompt
            for beat in answer["beats"]:
                beat["figure"] = {"kind": "diagram"}
        return answer

    started = service.start_job({"mode": "script", "script": SCRIPT, "audience": "Class 8"}, quality="l",
                                voice="silent", llm=model)
    job = wait(started["job_id"])
    assert job["status"] == "done", (job["error"], job["progress"][-8:])
    assert asked == ["A ladder leaning on a wall"]                       # one drawing for the script: asked for once
    assert job["script"]["pictures"] == [{"ask": asked[0], "shown": "whole", "parts": [1, 2]}]
    root = workspace / "lessons" / job["job_id"]
    lesson = json.loads((root / "lesson.json").read_text())
    figures = [b["figure"] for c in lesson["chapters"] for b in c["beats"]]
    assert figures and all(f == {"kind": "picture", "file": str(drawing), "ask": asked[0]} for f in figures)
    assert lesson["credits"] == ["Art: the diagram service"]
    # every picture is a prepared drawing, which is made for white paper: the lesson is on the light page
    assert lesson["look"] == {"frame": "stage", "captions": "outside", "page": "paper", "pictures": "kept", "working": "pinned",
                              "drawings": "painted", "joins": "carried", "math": "sans", "values": "spoken", "staging": "steps", "craft": "crafted"}
    assert job["checks"]["status"] == "technical_checks_passed", job["checks"]["failed"]
    # the picture really was built: a figure that cannot be is reported in the chapter's own log, nowhere else
    logs = "".join(p.read_text(errors="replace") for p in (root / "logs").glob("C*.log"))
    assert "could not be built" not in logs and "scene motion not started" not in logs


def test_the_same_script_again_pays_for_no_planning_and_no_review(workspace):
    """"Try again": the screen planned for a script and its review are kept (harness/store.py) and used again."""
    from lessonforge.harness import scripted
    calls = []

    def counted(prompt, system):
        calls.append("review" if "Score each rubric dimension" in system else "plan" if system is scripted.PLAN_SYSTEM
                     else "questions" if system.startswith(questions.SYSTEM) else "solve" if system is questions.SOLVE
                     else "mend" if system is repairs.FIX_SYSTEM else "screen")
        return script_model(prompt, system)

    from lessonforge.harness import questions, repairs
    brief = {"mode": "script", "script": SCRIPT, "audience": "Class 8"}
    first = wait(service.start_job(dict(brief), quality="l", voice="silent", llm=counted)["job_id"])
    assert first["status"] == "done", first["error"]
    assert calls.count("plan") == 1 and calls.count("screen") == 2 and calls.count("review") >= 1
    # the questions the script stops for are looked at once, with the author's words kept (harness/questions.py) ...
    assert calls.count("questions") == 1
    assert 1 <= calls.count("solve") <= 2                                 # its cards answered without their marked option
    before = len(calls)

    second = wait(service.start_job(dict(brief), quality="l", voice="silent", llm=counted)["job_id"])
    assert second["status"] == "done", second["error"]
    assert len(calls) == before                                          # not one model call: the questions pass is kept too
    assert sum("[store]" in line for line in second["progress"]) == 3    # the planned screen, its review, its mended storyboard
    root = workspace / "lessons"
    one, two = (json.loads((root / j["job_id"] / "lesson.json").read_text()) for j in (first, second))
    assert one == two and second["verification"] == first["verification"] and second["try_it"] == first["try_it"]

    # a script with one word changed is another script ...
    changed = wait(service.start_job({**brief, "script": SCRIPT.replace("5 metres long", "5 metres tall")}, quality="l",
                                     voice="silent", llm=counted)["job_id"])
    assert changed["status"] == "done" and len(calls) > before
    # ... and "fresh" asks for a new take on the same one
    before = len(calls)
    fresh = service.start_job({**brief, "fresh": True}, quality="l", voice="silent", llm=counted)
    assert fresh["brief"]["fresh"] is True
    assert wait(fresh["job_id"])["status"] == "done" and calls[before:].count("plan") == 1


def test_a_screen_planned_without_the_picture_it_asked_for_is_not_the_one_kept(workspace, monkeypatch):
    """The diagram service was down when the plan asked it for a picture: the next run plans again, with it."""
    from PIL import Image
    from lessonforge.harness import scripted
    plans = []

    def asks_for_a_picture(prompt, system):
        answer = script_model(prompt, system)
        if system is scripted.PLAN_SYSTEM:
            plans.append(1)
            return {**answer, "diagram_ask": "A ladder leaning on a wall, with the wall, the ground and the ladder labelled"}
        return answer

    brief = {"mode": "script", "script": SCRIPT, "audience": "Class 8"}
    monkeypatch.setattr(scripted, "prepared_picture", lambda ask, brief, log=print: None)          # the service is down
    down = wait(service.start_job(dict(brief), quality="l", voice="silent", llm=asks_for_a_picture)["job_id"])
    assert down["status"] == "done" and down["script"]["picture_missed"].startswith("A ladder leaning")

    drawing = workspace / "whole.png"
    Image.new("RGB", (900, 610), "#bde3ff").save(drawing)
    monkeypatch.setattr(scripted, "prepared_picture", lambda ask, brief, log=print: {
        "ask": ask, "manifest": str(workspace / "manifest.json"), "parts": [], "names": {}, "credit": "", "shown": "whole",
        "file": str(drawing)})
    up = wait(service.start_job(dict(brief), quality="l", voice="silent", llm=asks_for_a_picture)["job_id"])
    assert up["status"] == "done" and len(plans) == 2 and up["script"]["pictures"][0]["shown"] == "whole"
    assert not any("[store] the screen planned" in line for line in up["progress"])


def test_what_the_frame_review_finds_wrong_on_screen_is_repaired_and_kept_only_if_better(workspace, monkeypatch):
    """A finding causes a repair: the faulted beat's steps are written again, its chapter rendered again, and the
    change kept only when the second look finds less. Otherwise the first render and steps come back."""
    from lessonforge.harness import repairs
    monkeypatch.setenv("HARNESS_STORYBOARD_MEND", "0")        # the mend before speech asks the same stub; this is the repair after
    state = {"fixed": False, "looks": [], "cure": True}

    def model(prompt, system):
        if system is repairs.FIX_SYSTEM:
            state["fixed"] = True
            words = prompt.split("NARRATION OF THE BEAT (recorded, unchangeable):\n")[1].split("\n\n")[0].split()
            return {"steps": [{"say": " ".join(words[:3]), "show": "16 + 9 = 25", "kind": "math", "highlight": True},
                              {"say": " ".join(words[-4:]), "show": "The ladder is 5 m", "kind": "key"}]}
        return script_model(prompt, system)

    def judge(prompt, system, image):
        state["looks"].append(prompt[:40])
        still_wrong = not state["fixed"] or not state["cure"]
        second_beat = any(words in prompt for words in ("Square each", "Add them", "square root"))
        if second_beat and still_wrong:
            return {"findings": [{"kind": "mismatch", "what": "The narrator says the total is 25, but 25 is not on screen."}],
                    "shows_intended": False, "readable": True}
        return {"findings": [], "shows_intended": True, "readable": True}

    brief = {"mode": "script", "script": SCRIPT, "audience": "Class 8"}
    cured = wait(service.start_job(dict(brief), quality="l", voice="silent", llm=model, judge=judge)["job_id"])
    assert cured["status"] == "done", (cured["error"], cured["progress"][-8:])
    assert cured["screen_repair"]["tried"] == ["02"] and cured["screen_repair"]["kept"] == ["02"]
    assert cured["screen_repair"]["findings_before"] == 1 and cured["screen_repair"]["findings_after"] == 0
    root = workspace / "lessons" / cured["job_id"]
    steps = json.loads((root / "lesson.json").read_text())["chapters"][1]["beats"][0]["steps"]
    assert [s["show"] for s in steps][-1] == "The ladder is 5 m" and steps[0]["kind"] == "math"
    review = json.loads((root / "output" / "vision_review.json").read_text())
    assert review["findings"] == 0 and review["repaired_beats"] == ["02"] and cured["vision_review"]["findings"] == 0
    assert cured["checks"]["status"] == "technical_checks_passed" and (workspace / cured["video_url"].lstrip("/")).is_file()
    assert len(state["looks"]) == 3                                      # two beats looked at, then the repaired one again

    # The same repair that cures nothing is undone: the first steps and the first render stand.
    state.update(fixed=False, cure=False)
    kept = wait(service.start_job({**brief, "fresh": True}, quality="l", voice="silent", llm=model, judge=judge)["job_id"])
    assert kept["status"] == "done", kept["error"]
    assert kept["screen_repair"]["kept"] == [] and kept["screen_repair"]["undone"] == ["02"]
    again = json.loads((workspace / "lessons" / kept["job_id"] / "lesson.json").read_text())["chapters"][1]["beats"][0]["steps"]
    assert [s["show"] for s in again] == ["a^2 + b^2 = c^2", "Find the ladder"]          # the director's own, back in place
    assert kept["vision_review"]["findings"] == 1 and kept["checks"]["status"] == "technical_checks_passed"
    assert any("put back" in line for line in kept["progress"])


def test_a_script_waits_for_a_person_who_edits_it_and_the_edit_is_filmed(workspace):
    """The human in the loop (harness/edit.py): stop after the script, read it, change it, then film the change."""
    from lessonforge.harness import edit
    first = wait(service.start_job({"mode": "script", "script": SCRIPT, "audience": "Class 8", "stop_after": "verify"},
                                   quality="l", voice="silent", llm=script_model)["job_id"])
    assert first["status"] == "done" and first["script_only"] and first["awaiting_approval"] and not first["video_url"]
    view = service.script_for(first["job_id"])
    beats = [b for c in view["chapters"] for b in c["beats"]]
    assert view["script_only"] and len(beats) >= 2 and beats[1]["findings"]       # the review's note is beside its beat
    first_id, second_id = beats[0]["id"], beats[1]["id"]

    with pytest.raises(edit.EditError):
        service.edit_lesson(first["job_id"], {"77": {"remove": True}})
    with pytest.raises(KeyError):
        service.edit_lesson("../../etc", {})

    asked = []

    def director_and_reviewer(prompt, system):
        asked.append(system)
        return script_model(prompt, system) if "Score each rubric dimension" in system else {"beats": [{
            "id": second_id, "visual": "the three squares", "figure": {"kind": "right_triangle", "a": 4, "b": 3, "unknown": "c"},
            "steps": [{"say": "Square each leg", "show": "16 + 9 = 25", "kind": "math", "highlight": True}]}]}

    new_words = "A ladder leans on a wall, four metres out and three metres up. How long is the ladder?"
    started = service.edit_lesson(first["job_id"], {first_id: {"narration": new_words}, second_id: {"note": "show the squares"}},
                                  voice="silent", llm=director_and_reviewer)
    assert started["brief"]["edit_of"] == first["job_id"] and "stop_after" not in started["brief"]
    made = wait(started["job_id"])
    assert made["status"] == "done", (made["error"], made["progress"][-8:])
    assert made["video_url"] and made["edit"]["words"] == [first_id] and made["edit"]["screens"] == [second_id]
    lesson = json.loads((workspace / "lessons" / made["job_id"] / "lesson.json").read_text())
    said = [b["narration"] for c in lesson["chapters"] for b in c["beats"]]
    assert said[0] == new_words and said[1:] == [b["narration"] for b in beats[1:]]   # nobody rewrote the person's words
    assert any("your words were left as written" in line for line in made["progress"])
    assert (workspace / "lessons" / made["job_id"] / "lesson.reviewed.json").is_file()
    # the script it came from is as it was, and can be edited again
    assert service.script_for(first["job_id"])["chapters"][0]["beats"][0]["narration"] == beats[0]["narration"]
    assert service.script_for(made["job_id"])["edit_of"] == first["job_id"]
