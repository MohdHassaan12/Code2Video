"""Student reviews: the tasks, the question sheet, stored answers, and a summary to improve from.

Every measurement the pipeline makes about itself is a production measurement — the
checks say a cue landed on its word, not that a twelve-year-old understood the idea.
This module is the other half: a short review a student fills in after watching, kept
with the lesson it is about.

* ``form()`` is the whole sheet: five tasks ("watch once without skipping, press
  *this part is confusing* whenever you feel lost…") and twenty questions in plain
  words, thirteen of them required, about four minutes. Each question carries the
  ``area`` of the pipeline it informs (sync, layout, language, pacing…), so an answer
  is a pointer to the code that should change, not just a score.
* ``store()`` validates a submission against the sheet and writes it under
  ``<workspace>/lessons/<job>/feedback/`` (and appends it to ``feedback.jsonl`` for
  cross-lesson work). What the player observed rides along: which in-video questions
  were answered right, how much was watched, and the moments marked confusing.
* ``summarize()`` turns a lesson's reviews into means, counts, the comments, the
  confusing moments mapped to chapters and beats, and ``signals`` — the few plain
  statements worth acting on ("picture and voice out of step: 2.9 of 5 from 8 reviews").

Students get a review-only link (``LESSONFORGE_REVIEW_TOKEN``): it can load one
lesson and send one form, and nothing else on the server.
"""
from __future__ import annotations

import json
import os
import re
import time
import uuid
from pathlib import Path

from .. import paths

FORM_VERSION = "2026-10-08"
MAX_TEXT = 400

TASKS = [
    {"id": "watch", "text": "Watch the whole lesson once, from the start, without skipping."},
    {"id": "answer", "text": "Answer every question that appears in the video. Guessing is fine."},
    {"id": "mark", "text": "Whenever you feel lost, press “This part is confusing”."},
    {"id": "form", "text": "After the video, answer the questions below without watching again."},
    {"id": "honest", "text": "Be honest. We are testing the lesson, not you."},
]


def _rating(qid, section, area, prompt, low, high, required=True):
    return {"id": qid, "section": section, "area": area, "kind": "rating", "prompt": prompt, "required": required,
            "min": 1, "max": 5, "low_label": low, "high_label": high}


def _choice(qid, section, area, prompt, options, required=True):
    return {"id": qid, "section": section, "area": area, "kind": "choice", "prompt": prompt, "required": required,
            "options": [{"value": v, "label": label} for v, label in options]}


def _text(qid, section, area, prompt, placeholder=""):
    return {"id": qid, "section": section, "area": area, "kind": "text", "prompt": prompt, "required": False,
            "placeholder": placeholder, "max_length": MAX_TEXT}


QUESTIONS = [
    _choice("class_level", "About you", "audience", "Which class are you in?",
            [(str(n), f"Class {n}") for n in range(6, 13)] + [("other", "Other")]),
    _choice("knew_before", "About you", "audience", "How much of this topic did you know before watching?",
            [("none", "Nothing, it was new"), ("some", "A little"), ("most", "Most of it")]),

    _rating("understood", "Understanding", "script", "How well do you understand the topic now?",
            "Still confused", "I could teach a friend"),
    _text("main_idea", "Understanding", "script", "In one sentence, what was the main idea of this lesson?",
          "Say it in your own words"),
    _rating("can_do", "Understanding", "script", "Could you solve a similar problem on your own now?",
            "Not yet", "Yes, easily"),

    _choice("pace", "The explanation", "pacing", "How was the speed?",
            [("too_slow", "Too slow"), ("right", "Just right"), ("too_fast", "Too fast")]),
    _rating("language", "The explanation", "language", "How easy was the language to follow?",
            "Hard to follow", "Very easy"),
    _text("hard_words", "The explanation", "language", "Write any word or sentence you did not understand.",
          "Leave empty if everything was clear"),
    {"id": "confusing_chapters", "section": "The explanation", "area": "script", "kind": "chapters",
     "prompt": "Which parts were confusing? Tap all that apply.", "required": False, "multiple": True},
    {"id": "best_chapter", "section": "The explanation", "area": "script", "kind": "chapters",
     "prompt": "Which part helped you the most?", "required": False, "multiple": False},

    _rating("visuals", "Picture and sound", "motion", "Did the pictures and animation help you understand?",
            "Not at all", "A lot"),
    _rating("sync", "Picture and sound", "sync", "Did the picture match what the teacher was saying at that moment?",
            "Often did not match", "Always matched"),
    _rating("voice", "Picture and sound", "voice", "How was the teacher's voice?",
            "Hard to listen to", "Clear and pleasant"),
    _choice("screen_problem", "Picture and sound", "layout",
            "Did anything on the screen overlap, get cut off or look too small?",
            [("no", "No"), ("once", "Yes, once or twice"), ("often", "Yes, often")]),

    _rating("questions_useful", "Questions in the video", "interaction",
            "Did the questions inside the video help you think?", "Not useful", "Very useful"),
    _choice("questions_amount", "Questions in the video", "interaction", "How many questions were there?",
            [("too_few", "Too few"), ("right", "About right"), ("too_many", "Too many")], required=False),

    _choice("length", "Overall", "pacing", "How was the length?",
            [("too_short", "Too short"), ("right", "Just right"), ("too_long", "Too long")]),
    _text("mistake", "Overall", "correctness", "Did you notice a mistake: a wrong number, word or picture? Tell us where.",
          "Leave empty if you saw none"),
    _rating("overall", "Overall", "overall", "Overall, how good was this lesson?", "Poor", "Excellent"),
    _text("improve", "Overall", "overall", "What is one thing we should change?"),
]
BY_ID = {q["id"]: q for q in QUESTIONS}

# The tester sheet: for the people who MAKE a lesson (teachers, parents, colleagues), not the
# students who watch one. Ten questions, grouped so "was it easy to make" can be told apart
# from "was the video good" and "would you use it" — a friend liking it is not evidence it teaches.
TESTER_TASKS = [
    {"id": "maths", "text": "Is the maths right? Note the time of any wrong number, formula or explanation."},
    {"id": "match", "text": "Does the picture match the voice? Blank screens, misplaced labels, an answer shown too early."},
    {"id": "follow", "text": "Would a student follow it? Too fast, too slow, words they would not know."},
    {"id": "voice", "text": "Does the narration sound natural? Robotic pauses, mispronounced words, odd Hinglish."},
    {"id": "making", "text": "Was making it easy? Were the follow-up questions useful or annoying?"},
    {"id": "use", "text": "Would you actually use it: in class, for homework, for revision, or not at all?"},
]


def _multi(qid, section, area, prompt, options, required=True):
    return {"id": qid, "section": section, "area": area, "kind": "multi", "prompt": prompt, "required": required,
            "options": [{"value": v, "label": label} for v, label in options]}


TESTER_QUESTIONS = [
    _choice("role", "About you", "audience", "Which best describes you?",
            [("teacher", "Teacher"), ("student", "Student"), ("parent", "Parent"), ("edtech", "Edtech / engineer"),
             ("other", "Other")]),
    _text("topics", "About you", "audience", "What topic(s) did you make a video for?", "e.g. Area of a circle, class 7"),
    _choice("finished", "Making the video", "reliability", "Did a video finish generating?",
            [("yes", "Yes"), ("failed", "No, it failed"), ("gave_up", "Gave up waiting")]),
    _rating("ease", "Making the video", "intake", "How easy was it to make the video?", "Very hard", "Very easy"),
    _choice("followups", "Making the video", "intake", "Were the follow-up questions helpful?",
            [("helpful", "Helpful"), ("too_many", "Too many"), ("confusing", "Confusing"), ("unnoticed", "Didn't notice")]),
    _choice("maths_correct", "The video", "correctness", "Was the maths correct?",
            [("correct", "Fully correct"), ("small", "Small errors"), ("big", "Big errors"), ("unsure", "Not sure")]),
    _rating("sync", "The video", "sync", "Did the visuals match what the voice was saying?", "Never", "Always"),
    _choice("student_follow", "The video", "script", "Could a student of that class follow it on their own?",
            [("yes", "Yes"), ("with_help", "With a teacher's help"), ("no", "No")]),
    _multi("would_use", "Using it", "overall", "Would you use a video like this? Tap all that apply.",
           [("class", "In class"), ("homework", "Homework / revision"), ("share", "Share with students"),
            ("no", "Wouldn't use")]),
    _text("fix_first", "Using it", "overall",
          "The one thing we should fix or add first, and the times of any problems.", "e.g. 1:20 the label covers the triangle"),
]
SHEETS = {"student": {"title": "Help us make this lesson better", "minutes": 4, "tasks": TASKS, "questions": QUESTIONS},
          "tester": {"title": "Tell us how it went", "minutes": 4, "tasks": TESTER_TASKS, "questions": TESTER_QUESTIONS}}
#: Where an answer points in the pipeline, for whoever reads the summary.
AREAS = {
    "script": "writer and framework (harness/writer.py, frameworks.py)",
    "language": "language policy and readability (writer language notes, critic.language_gate)",
    "pacing": "words per minute, beat length, lesson length (writer budgets, depth cuts)",
    "motion": "figures and scenes (longform/figures.py, engine/sim_gen.py)",
    "sync": "alignment and cue timing (longform/align.py, runtime.cue)",
    "voice": "speech model, voice and narrator instruction (speech.py, service.tts_instructions)",
    "layout": "layout and readability on screen (runtime.GuidedChapter, layout_probe)",
    "interaction": "in-video questions (writer quiz rule, runtime._pause, player overlay)",
    "correctness": "critic and gates (harness/critic.py)",
    "audience": "who is watching (intake)", "overall": "everything",
    "intake": "the question-by-question intake (harness/intake.py, interviewer.py)",
    "reliability": "jobs finishing, speed, the server (harness/service.py)",
}


def form(kind: str = "student") -> dict:
    """A sheet as the app renders it: ``student`` (watching one lesson) or ``tester`` (making lessons)."""
    sheet = SHEETS.get(kind)
    if sheet is None:
        raise KeyError(kind)
    return {"kind": kind, "version": FORM_VERSION, **sheet, "areas": AREAS}


def review_token() -> str | None:
    return (os.getenv("LESSONFORGE_REVIEW_TOKEN") or "").strip() or None


def _lesson_root(job_id: str) -> Path:
    if not re.fullmatch(r"[A-Za-z0-9_-]{6,64}", job_id or ""):
        raise KeyError(job_id)
    root = paths.home() / "lessons" / job_id
    if not (root / "lesson.json").is_file():
        raise KeyError(job_id)
    return root


def _chapters(root: Path) -> list[dict]:
    lesson = json.loads((root / "lesson.json").read_text(encoding="utf-8"))
    return [{"id": c["id"], "title": c["title"]} for c in lesson["chapters"]]


def validate(answers: dict, auto: dict | None, chapter_ids: set, questions: list | None = None) -> tuple[dict, dict]:
    """A submission checked against a sheet. Raises ``ValueError`` naming what is missing or wrong."""
    questions = QUESTIONS if questions is None else questions
    by_id = {q["id"]: q for q in questions}
    if not isinstance(answers, dict):
        raise ValueError("answers must be an object")
    clean: dict = {}
    for q in questions:
        value = answers.get(q["id"])
        kind = q["kind"]
        if kind == "rating":
            try:
                number = int(value)
            except (TypeError, ValueError):
                number = None
            if number is not None and q["min"] <= number <= q["max"]:
                clean[q["id"]] = number
        elif kind == "choice":
            if str(value) in {o["value"] for o in q["options"]}:
                clean[q["id"]] = str(value)
        elif kind == "multi":
            allowed = [o["value"] for o in q["options"]]
            picked = [str(v) for v in (value if isinstance(value, list) else [value]) if str(v) in allowed]
            picked = [v for v in allowed if v in picked]            # sheet order, no repeats
            if picked:
                clean[q["id"]] = picked
        elif kind == "text":
            text = re.sub(r"\s+", " ", str(value or "")).strip()[:MAX_TEXT]
            if text:
                clean[q["id"]] = text
        elif kind == "chapters":
            picked = value if isinstance(value, list) else ([] if value in (None, "") else [value])
            ids = []
            for item in picked:
                try:
                    number = int(item)
                except (TypeError, ValueError):
                    continue
                if number in chapter_ids and number not in ids:
                    ids.append(number)
            if ids:
                clean[q["id"]] = ids if q.get("multiple") else ids[:1]
    missing = [q["id"] for q in questions if q["required"] and q["id"] not in clean]
    if missing:
        raise ValueError("please answer: " + ", ".join(by_id[m]["prompt"] for m in missing[:3])
                         + (f" (and {len(missing) - 3} more)" if len(missing) > 3 else ""))
    auto = auto if isinstance(auto, dict) else {}
    quiz = auto.get("quiz") if isinstance(auto.get("quiz"), dict) else {}

    def count(source, key, top=10_000):
        try:
            return max(0, min(top, int(source.get(key) or 0)))
        except (TypeError, ValueError):
            return 0

    moments = []
    for t in (auto.get("confused_at") or [])[:60] if isinstance(auto.get("confused_at"), list) else []:
        try:
            moments.append(round(max(0.0, float(t)), 1))
        except (TypeError, ValueError):
            continue
    clean_auto = {
        "watch_mode": str(auto.get("watch_mode") or "full")[:20],
        "seconds_watched": count(auto, "seconds_watched", 36_000), "completed": bool(auto.get("completed")),
        # retried_right: right on the second try after a nudge (not counted correct). sure_wrong_ids: wrong while
        # "sure", the strongest sign of a misconception rather than a slip. misconceptions: what those options named.
        "quiz": {k: count(quiz, k, 200) for k in ("asked", "answered", "correct", "skipped", "retried_right")}
                | {key: [str(x)[:size] for x in (quiz.get(key) or [])[:40]] if isinstance(quiz.get(key), list) else []
                   for key, size in (("wrong_ids", 12), ("sure_wrong_ids", 12), ("misconceptions", 160))},
        "confused_at": sorted(moments),
    }
    return clean, clean_auto


def review_of(job_id: str, body: dict, chapter_ids: set, lesson: dict) -> dict:
    """One student's review, checked against the sheet and dated, as it is kept. ``ValueError`` when it is not
    complete. ``lesson``: what the review is about (title, framework, language, level, grade, minutes).
    The server keeps it in the lesson's folder (:func:`store`); the viewer site in its database."""
    answers, auto = validate((body or {}).get("answers") or {}, (body or {}).get("auto"), chapter_ids)
    return {
        "id": time.strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:6], "at": time.time(), "job_id": job_id,
        "form_version": FORM_VERSION,
        "reviewer": re.sub(r"\s+", " ", str((body or {}).get("reviewer") or "")).strip()[:40],
        "answers": answers, "auto": auto, "lesson": lesson,
    }


def store(job_id: str, body: dict) -> dict:
    """Validate and keep one review. Returns ``{"stored", "id", "count"}``."""
    root = _lesson_root(job_id)
    chapters = _chapters(root)
    lesson = json.loads((root / "lesson.json").read_text(encoding="utf-8"))
    brief = lesson.get("brief") or {}
    record = review_of(job_id, body, {c["id"] for c in chapters},
                       {"title": lesson.get("title"), "framework": lesson.get("framework"),
                        "language": brief.get("language"), "level": brief.get("level"), "grade": brief.get("grade"),
                        "minutes": brief.get("duration_minutes")})
    review_id = record["id"]
    folder = root / "feedback"
    folder.mkdir(exist_ok=True)
    (folder / f"{review_id}.json").write_text(json.dumps(record, indent=1, ensure_ascii=False), encoding="utf-8")
    with (paths.home() / "feedback.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    return {"stored": True, "id": review_id, "count": len(list(folder.glob("*.json")))}


def _reviews(root: Path) -> list[dict]:
    out = []
    for path in sorted((root / "feedback").glob("*.json")) if (root / "feedback").is_dir() else []:
        try:
            out.append(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            continue
    return out


def _aggregate(reviews: list[dict], questions: list | None = None) -> dict:
    ratings, choices, chapters, texts = {}, {}, {}, {}
    for q in (QUESTIONS if questions is None else questions):
        values = [r["answers"][q["id"]] for r in reviews if q["id"] in r.get("answers", {})]
        if q["kind"] == "rating":
            histogram = [sum(1 for v in values if v == n) for n in range(1, 6)]
            ratings[q["id"]] = {"prompt": q["prompt"], "area": q["area"], "n": len(values), "histogram": histogram,
                                "mean": round(sum(values) / len(values), 2) if values else None}
        elif q["kind"] in ("choice", "multi"):
            choices[q["id"]] = {"prompt": q["prompt"], "area": q["area"], "multiple": q["kind"] == "multi",
                                "labels": {o["value"]: o["label"] for o in q["options"]},
                                "counts": {o["value"]: sum(1 for v in values if v == o["value"] or
                                                           (isinstance(v, list) and o["value"] in v))
                                           for o in q["options"]}}
        elif q["kind"] == "chapters":
            counts: dict = {}
            for picked in values:
                for cid in picked:
                    counts[str(cid)] = counts.get(str(cid), 0) + 1
            chapters[q["id"]] = {"prompt": q["prompt"], "counts": counts}
        else:
            items = [{"text": r["answers"][q["id"]], "reviewer": r.get("reviewer") or None, "at": r.get("at")}
                     for r in reviews if q["id"] in r.get("answers", {})]
            texts[q["id"]] = {"prompt": q["prompt"], "area": q["area"], "items": items[::-1][:50]}
    shares = [r["auto"]["quiz"]["correct"] / r["auto"]["quiz"]["asked"] for r in reviews
              if r.get("auto", {}).get("quiz", {}).get("asked")]
    return {"count": len(reviews), "ratings": ratings, "choices": choices, "chapters": chapters, "texts": texts,
            "quiz": {"responses": len(shares), "mean_correct_share": round(sum(shares) / len(shares), 2) if shares else None},
            "completed_share": round(sum(1 for r in reviews if r.get("auto", {}).get("completed")) / len(reviews), 2)
            if reviews else None}


def signals(summary: dict) -> list[dict]:
    """The few statements worth acting on, each pointing at an area of the pipeline."""
    out, n = [], summary["count"]
    if not n:
        return out
    for qid, r in summary["ratings"].items():
        if r["n"] and r["mean"] is not None and r["mean"] < 3.5:
            out.append({"area": r["area"], "where": AREAS.get(r["area"], ""),
                        "message": f"“{r['prompt']}” averaged {r['mean']} of 5 from {r['n']} review(s)."})
    share = lambda qid, *values: sum(summary["choices"][qid]["counts"].get(v, 0) for v in values) / n  # noqa: E731
    rules = [("pace", ("too_fast",), 0.4, "pacing", "found the lesson too fast"),
             ("pace", ("too_slow",), 0.4, "pacing", "found the lesson too slow"),
             ("length", ("too_long",), 0.4, "pacing", "found the lesson too long"),
             ("screen_problem", ("once", "often"), 0.3, "layout", "saw something overlap, cut off or too small"),
             ("questions_amount", ("too_many",), 0.4, "interaction", "found too many questions"),
             ("questions_amount", ("too_few",), 0.4, "interaction", "wanted more questions")]
    for qid, values, limit, area, words in rules:
        if share(qid, *values) >= limit:
            out.append({"area": area, "where": AREAS[area],
                        "message": f"{round(share(qid, *values) * 100)}% of {n} reviewer(s) {words}."})
    mistakes = summary["texts"].get("mistake", {}).get("items") or []
    if mistakes:
        out.append({"area": "correctness", "where": AREAS["correctness"],
                    "message": f"{len(mistakes)} reviewer(s) reported a mistake, e.g. “{mistakes[0]['text'][:120]}”."})
    quiz = summary.get("quiz") or {}
    if quiz.get("mean_correct_share") is not None and quiz["mean_correct_share"] < 0.5:
        out.append({"area": "script", "where": AREAS["script"],
                    "message": f"In-video questions were answered right only {round(quiz['mean_correct_share'] * 100)}% "
                               f"of the time ({quiz['responses']} viewing(s))."})
    return out


def summarize(job_id: str) -> dict:
    """Everything the reviews of one lesson say, with the confusing moments mapped to beats."""
    root = _lesson_root(job_id)
    timeline = []
    if (root / "timeline.json").is_file():
        timeline = json.loads((root / "timeline.json").read_text(encoding="utf-8"))
    return summary_from(job_id, _reviews(root), json.loads((root / "lesson.json").read_text(encoding="utf-8")), timeline)


def summary_from(job_id: str, reviews: list[dict], lesson: dict, timeline: list[dict]) -> dict:
    """:func:`summarize` from its parts: the reviews, the lesson (title, chapters and beats' narration) and its
    timeline (each beat's ``id``, ``chapter``, ``start`` and ``duration``). The viewer site has these from its
    database and the lesson's published files."""
    summary = _aggregate(reviews)
    buckets: dict = {}
    for review in reviews:
        for t in review.get("auto", {}).get("confused_at", []):
            beat = next((e for e in timeline if e["start"] <= t < e["start"] + e["duration"]), None)
            key = beat["id"] if beat else f"t{int(t // 10)}"
            slot = buckets.setdefault(key, {"t": round(beat["start"], 1) if beat else float(int(t // 10) * 10),
                                            "chapter": beat["chapter"] if beat else None,
                                            "beat": beat["id"] if beat else None, "count": 0})
            slot["count"] += 1
    narration = {b["id"]: b["narration"] for c in lesson["chapters"] for b in c["beats"]}
    moments = sorted(buckets.values(), key=lambda m: (-m["count"], m["t"]))[:12]
    for moment in moments:
        if moment["beat"]:
            moment["said"] = narration.get(moment["beat"], "")[:160]
    summary.update({"job_id": job_id, "title": lesson.get("title", ""), "confused_at": moments,
                    "chapters_list": [{"id": c["id"], "title": c["title"]} for c in lesson["chapters"]]})
    summary["signals"] = signals(summary)
    return summary


def summarize_all() -> dict:
    """Across every lesson: one row per reviewed lesson, and the same aggregate over all reviews."""
    lessons_dir = paths.home() / "lessons"
    groups = []
    for root in sorted(lessons_dir.iterdir(), reverse=True) if lessons_dir.is_dir() else []:
        reviews = _reviews(root) if root.is_dir() else []
        if reviews:
            groups.append((root.name, reviews))
    return all_from(groups)


def all_from(groups: list[tuple[str, list[dict]]]) -> dict:
    """:func:`summarize_all` from ``(job_id, that lesson's reviews)`` pairs, newest lesson first."""
    rows, everything = [], []
    for job_id, reviews in groups:
        if not reviews:
            continue
        everything += reviews
        agg = _aggregate(reviews)
        rows.append({"job_id": job_id, "title": reviews[-1].get("lesson", {}).get("title"), "count": agg["count"],
                     "language": reviews[-1].get("lesson", {}).get("language"),
                     "framework": reviews[-1].get("lesson", {}).get("framework"),
                     **{k: agg["ratings"][k]["mean"] for k in ("overall", "understood", "can_do", "language", "visuals",
                                                               "sync", "voice", "questions_useful")}})
    overall = _aggregate(everything)
    overall["signals"] = signals(overall)
    return {"reviews": len(everything), "lessons": rows, "all": overall}


# ── testers: people who make lessons ──────────────────────────────────────────

def tester_of(body: dict, title_of) -> dict:
    """One tester's form, checked and dated, as it is kept. ``title_of(job_id)`` gives the title of the lesson
    they had open and raises ``KeyError`` (or ``OSError``/``ValueError``) when there is no such lesson."""
    body = body or {}
    answers, _ = validate(body.get("answers") or {}, None, set(), TESTER_QUESTIONS)
    job_id, title = str(body.get("job_id") or ""), None
    try:
        title = title_of(job_id)
    except (KeyError, OSError, ValueError):
        job_id = ""
    return {"id": time.strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:6], "at": time.time(), "kind": "tester",
            "form_version": FORM_VERSION, "job_id": job_id or None, "lesson_title": title,
            "reviewer": re.sub(r"\s+", " ", str(body.get("reviewer") or "")).strip()[:40],
            "contact": re.sub(r"\s+", " ", str(body.get("contact") or "")).strip()[:80],
            "answers": answers}


def store_tester(body: dict) -> dict:
    """Keep one tester's form. ``job_id`` is optional: the lesson they had open, when there was one."""
    record = tester_of(body, lambda job_id: json.loads((_lesson_root(job_id) / "lesson.json").read_text(encoding="utf-8")).get("title"))
    review_id = record["id"]
    folder = paths.sub("feedback", "tester")
    (folder / f"{review_id}.json").write_text(json.dumps(record, indent=1, ensure_ascii=False), encoding="utf-8")
    with (paths.home() / "feedback_testers.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    return {"stored": True, "id": review_id, "count": len(list(folder.glob("*.json")))}


def summarize_testers() -> dict:
    """What the testers said, with the signals worth acting on. Contact details are not included."""
    folder = paths.home() / "feedback" / "tester"
    reviews = []
    for path in sorted(folder.glob("*.json")) if folder.is_dir() else []:
        try:
            reviews.append(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            continue
    return testers_from(reviews)


def testers_from(reviews: list[dict]) -> dict:
    """:func:`summarize_testers` from the forms themselves, oldest first."""
    summary = _aggregate(reviews, TESTER_QUESTIONS)
    n, out = summary["count"], []
    if n:
        share = lambda qid, *values: sum(summary["choices"][qid]["counts"].get(v, 0) for v in values) / n  # noqa: E731
        for qid, r in summary["ratings"].items():
            if r["n"] and r["mean"] < 3.5:
                out.append({"area": r["area"], "where": AREAS.get(r["area"], ""),
                            "message": f"“{r['prompt']}” averaged {r['mean']} of 5 from {r['n']} tester(s)."})
        for qid, values, limit, area, words in (
                ("finished", ("failed", "gave_up"), 0.2, "reliability", "did not get a finished video"),
                ("maths_correct", ("small", "big"), 0.2, "correctness", "saw errors in the maths"),
                ("followups", ("too_many", "confusing"), 0.3, "intake", "found the follow-up questions too many or confusing"),
                ("student_follow", ("no",), 0.3, "script", "said a student could not follow it alone"),
                ("would_use", ("no",), 0.3, "overall", "would not use a video like this")):
            if share(qid, *values) >= limit:
                out.append({"area": area, "where": AREAS[area],
                            "message": f"{round(share(qid, *values) * 100)}% of {n} tester(s) {words}."})
    summary.update({"kind": "tester", "signals": out,
                    "lessons": sorted({r["lesson_title"] for r in reviews if r.get("lesson_title")})})
    return summary
