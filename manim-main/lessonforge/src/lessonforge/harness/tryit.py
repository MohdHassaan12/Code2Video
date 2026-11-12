"""Try it yourself — the task a learner does by hand after the video, and what they answered.

Goal 3 of the script plan (docs/research/approaches/06_teaching_script_plan.html): the
learner DOES something. "One task: things found at home, five steps or fewer, a
prediction first, a question after, the expected result", and a second version for a
teacher with a full class. The companion file (06_plan_checks_and_additions.md) adds what
the studies say such a task needs, and each is a field here:

* a guess BEFORE doing it (a demonstration watched without one taught almost nothing:
  Crouch et al. 2004) — ``predict``;
* "what did you see?", with the true outcome shown afterwards (18% of observations in one
  study did not match what happened: Miller et al. 2013) — ``observe``;
* a question that asks WHY, answered in words (handling objects alone is the weakest
  active level; the gain is where the learner produces something: Chi & Wylie 2014) —
  ``question`` / ``expected``;
* one line saying what each object stands for (objects need mapping to the idea:
  Fiorella & Mayer 2016) — ``stands_for``.

Whoever WRITES a task (the director of a pasted script in ``scripted.py``, the teaching
card for a generated lesson) hands it to :func:`clean`, the one place code decides whether
a task may be shown: its shape, its limits, and nothing that burns or cuts. The task
lives in the lesson (``lesson["try_it"]``, or inside its card); answers are kept with the
lesson, one file each, like reviews.
"""
from __future__ import annotations

import json
import re
import time
import uuid
from pathlib import Path

from .. import paths

MAX_STEPS = 5
MAX_MATERIALS = 8
MAX_ANSWER = 400
KINDS = ("hands", "paper", "simulation")
#: Where a lesson may carry its task (the first that holds a usable one wins).
_TASK_KEYS = ("try_it", "try_it_yourself", "practicum")
# Things a task for school children may not ask for. Whole words only: "matching" is not a
# match, "gasp" is not gas (the same lesson as engine/code_safety.py: tokens, never letters).
_UNSAFE = re.compile(
    r"\b(?:fire|flames?|burn(?:s|ing|er)?|matchsticks?|matchbox(?:es)?|lighters?|candles?|stoves?|boiling|"
    r"kni(?:fe|ves)|blades?|razors?|acids?|bleach|kerosene|petrol|firecrackers?|mains|sockets?|syringes?|needles?|"
    r"swallow(?:s|ed|ing)?|tast(?:e|es|ed|ing))\b",          # nothing is swallowed (skills/teaching-script/practicum.md)
    re.I)


def _line(value, limit: int) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()[:limit]


def _lines(value, count: int, limit: int) -> list[str]:
    items = value if isinstance(value, list) else ([value] if value else [])
    out = [_line(re.sub(r"^\s*(?:\d{1,2}[.)]|[-–•*])\s+", "", str(item)), limit) for item in items]
    return [item for item in out if item][:count]


def unsafe_words(task: dict) -> list[str]:
    """Words in a task that rule it out for a school lesson (fire, blades, acids …)."""
    text = " ".join([" ".join(task.get("materials") or []), " ".join(task.get("steps") or []),
                     str(task.get("title") or ""), str(task.get("in_class") or "")])
    return sorted({m.group(0).lower() for m in _UNSAFE.finditer(text)})


def clean(raw) -> tuple[dict | None, str]:
    """A model's (or a card's) task → ``(task, "")`` fit to show, or ``(None, why not)``.

    Kept: at most five steps and eight materials, every text clamped. Refused: a task with
    no steps, with nothing to guess, with no question or no expected answer (a task nobody
    can check is an activity, not a lesson), or one that needs anything that burns or cuts.
    """
    if not isinstance(raw, dict):
        return None, "no task was written"
    steps = raw.get("steps") if isinstance(raw.get("steps"), list) else []
    if len([s for s in steps if str(s).strip()]) > MAX_STEPS:
        return None, f"more than {MAX_STEPS} steps"
    predict = raw.get("predict")
    if isinstance(predict, dict):                      # a card may hold {"question": …, "options": […]}
        predict = predict.get("question") or predict.get("text")
    task = {
        "title": _line(raw.get("title"), 80),
        "kind": raw.get("kind") if raw.get("kind") in KINDS else "hands",
        "materials": _lines(raw.get("materials") or raw.get("you_need"), MAX_MATERIALS, 80),
        "stands_for": _line(raw.get("stands_for"), 240),
        "predict": _line(predict, 240),
        "steps": _lines(steps, MAX_STEPS, 220),
        "observe": _line(raw.get("observe") or raw.get("you_should_see"), 300),
        "question": _line(raw.get("question"), 240),
        "expected": _line(raw.get("expected") or raw.get("answer"), 400),
        "write": _line(raw.get("write"), 240),          # the two lines the learner writes or says at the end
        "in_class": _line(raw.get("in_class") or raw.get("class_version"), 400),
    }
    for needed, why in (("steps", "no steps"), ("predict", "nothing to guess first"),
                        ("question", "no question to answer afterwards"), ("expected", "no expected answer")):
        if not task[needed]:
            return None, why
    bad = unsafe_words(task)
    if bad:
        return None, "it needs something unsafe for a school task: " + ", ".join(bad)
    return task, ""


def task_of(lesson: dict | None) -> dict | None:
    """The lesson's task as a client shows it, or None when it has none."""
    lesson = lesson if isinstance(lesson, dict) else {}
    card = lesson.get("card") if isinstance(lesson.get("card"), dict) else {}
    for holder in (lesson, card):
        for key in _TASK_KEYS:
            task, _ = clean(holder.get(key))
            if task:
                return task
    return None


def card_view(lesson: dict | None) -> dict | None:
    """The teaching card as the app shows it under a video: what the lesson stands on, without passage ids.

    The card itself is ``lesson["card"]`` (``harness/card.py``). Only titles and links of its
    sources are passed on: the passages stay in ``teaching_pack.json``, which is never served
    (most of those sources may be read and not redistributed).
    """
    card = (lesson or {}).get("card") if isinstance(lesson, dict) else None
    if not isinstance(card, dict):
        return None

    def said(key: str, field: str = "text") -> str:
        value = card.get(key)
        return _line(value.get(field) if isinstance(value, dict) else value, 500)

    opening = card.get("opening_question") if isinstance(card.get("opening_question"), dict) else {}
    view = {
        "big_idea": said("big_idea"), "why_it_matters": said("why_it_matters"), "the_why": said("the_why"),
        "picture": said("picture"),
        # The standard way the topic is drawn in class (division ladder, number line …), when the sources use one.
        "picture_standard": said("picture", "standard")[:80] if isinstance(card.get("picture"), dict) else "",
        "opening_question": {"question": _line(opening.get("question"), 240), "answer": _line(opening.get("answer"), 300)},
        "mistakes": [{"mistake": _line(m.get("mistake"), 240), "why_it_fails": _line(m.get("why_it_fails"), 300)}
                     for m in (card.get("mistakes") or []) if isinstance(m, dict) and _line(m.get("mistake"), 240)][:6],
        "needs_first": [_line(n.get("text") if isinstance(n, dict) else n, 160) for n in (card.get("needs_first") or [])][:6],
        "sources": [{"id": _line(s.get("id"), 8), "kind": _line(s.get("kind"), 20), "title": _line(s.get("title"), 160),
                     "url": _line(s.get("url"), 400) if str(s.get("url") or "").startswith(("http://", "https://")) else ""}
                    for s in (card.get("sources") or []) if isinstance(s, dict) and _line(s.get("title"), 160)][:12],
        "problems": len(card.get("problems") or []),
    }
    view["needs_first"] = [n for n in view["needs_first"] if n]
    return view if any(view[k] for k in ("big_idea", "the_why", "picture", "mistakes", "sources")) else None


# ── answers, kept with the lesson ─────────────────────────────────────────────

def _lesson_root(job_id: str) -> Path:
    root = paths.home() / "lessons" / str(job_id)
    if not re.fullmatch(r"[\w.-]{1,80}", str(job_id)) or str(job_id).startswith(".") or not (root / "lesson.json").is_file():
        raise KeyError(job_id)
    return root


def _task(root: Path) -> dict:
    try:
        task = task_of(json.loads((root / "lesson.json").read_text(encoding="utf-8")))
    except (OSError, ValueError):
        task = None
    if task is None:
        raise KeyError(root.name)
    return task


def _answers(root: Path) -> list[dict]:
    out = []
    for path in sorted((root / "tryit").glob("*.json")) if (root / "tryit").is_dir() else []:
        try:
            out.append(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            continue
    # By the time each was sent: two answers in one second share a file-name prefix.
    return sorted(out, key=lambda a: a.get("at") or 0)


def count(root: Path) -> int:
    return len(list((root / "tryit").glob("*.json"))) if (root / "tryit").is_dir() else 0


def store(job_id: str, body: dict) -> dict:
    """Keep one learner's guess, what they saw and their answer. Returns what to reveal now.

    ``KeyError`` when the lesson has no task; ``ValueError`` when nothing was answered.
    """
    root = _lesson_root(job_id)
    task = _task(root)
    record = answer_of(job_id, body)
    answer_id = record["id"]
    folder = root / "tryit"
    folder.mkdir(exist_ok=True)
    (folder / f"{answer_id}.json").write_text(json.dumps(record, indent=1, ensure_ascii=False), encoding="utf-8")
    return reveal(task, answer_id, count(root))


def answer_of(job_id: str, body: dict) -> dict:
    """One learner's answer, clamped and dated, as it is kept. ``ValueError`` when nothing was answered.
    The server keeps it in the lesson's folder (:func:`store`); the viewer site in its database."""
    body = body if isinstance(body, dict) else {}
    record = {key: _line(body.get(key), MAX_ANSWER) for key in ("prediction", "observation", "answer")}
    if not record["answer"] and not record["observation"]:
        raise ValueError("say what you saw, or answer the question, before checking")
    return {"id": time.strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:6], "at": time.time(), "job_id": job_id,
            "reviewer": _line(body.get("reviewer"), 40), "done_in_class": bool(body.get("done_in_class")), **record}


def reveal(task: dict, answer_id: str, answers: int) -> dict:
    """The reply to a STORED answer, and the only place the expected result is handed out."""
    return {"stored": True, "id": answer_id, "count": answers, "observe": task["observe"], "expected": task["expected"]}


def summarize(job_id: str) -> dict:
    """For the lesson's owner: the task and what learners wrote, newest first."""
    root = _lesson_root(job_id)
    return summary_from(job_id, _task(root), _answers(root))


def summary_from(job_id: str, task: dict, answers: list[dict]) -> dict:
    """:func:`summarize` from the task and the answers, oldest first."""
    return {"job_id": job_id, "task": task, "count": len(answers),
            "answers": [{k: a.get(k) for k in ("id", "at", "reviewer", "prediction", "observation", "answer", "done_in_class")}
                        for a in reversed(answers)][:100]}
