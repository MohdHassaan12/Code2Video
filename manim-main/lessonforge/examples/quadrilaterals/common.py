"""Helpers for the hand-written quadrilateral lessons (the owner's 'Quadrilaterals adaptive framework' pack).

Every picture is a ``shape`` figure: points only, and ``longform.geometry`` works out angles, equal and parallel
marks, convex / concave / crossed. A builder never writes an angle value or a verdict by hand.
"""
from __future__ import annotations

import json
import re
from pathlib import Path


def S(say, show, kind="point", focus=None, highlight=None):
    step = {"say": say, "show": show, "kind": kind}
    if focus:
        step["focus"] = focus
    if highlight:
        step["highlight"] = highlight
    return step


def Q(question, options, answer, why, kind="apply", explain=""):
    return {"question": question, "options": options, "answer_index": answer, "why": why, "kind": kind,
            "explain": explain or why[answer]}


def B(bid, narration, figure=None, steps=(), quiz=None, pause=0, depth="core"):
    beat = {"id": bid, "narration": narration, "figure": figure, "steps": list(steps), "depth": depth}
    if quiz:
        beat["quiz"] = quiz
        beat["thinking_pause_seconds"] = pause or 6
    elif pause:
        beat["thinking_pause_seconds"] = pause
    return beat


def C(cid, title, goal, beats, role="explain"):
    return {"id": cid, "title": title, "learning_goal": goal, "role": role, "beats": beats}


def _norm(s):
    return re.sub(r"[^a-z0-9 ]", " ", s.lower()).split()


def check(lesson):
    """Every step's words are said in its beat, in order; a quiz beat ends with a question."""
    problems = []
    for ch in lesson["chapters"]:
        for b in ch["beats"]:
            words = " ".join(_norm(b["narration"]))
            at = 0
            for st in b["steps"]:
                say = " ".join(_norm(st["say"]))
                k = words.find(say, at)
                if k < 0:
                    problems.append(f"{b['id']}: '{st['say']}' not found in order")
                else:
                    at = k
            if b.get("quiz") and not b["narration"].rstrip().endswith("?"):
                problems.append(f"{b['id']}: quiz beat does not end with its question")
            q = b.get("quiz")
            if q and len(q["why"]) != len(q["options"]):
                problems.append(f"{b['id']}: one reason per option")
    return problems


def write(lesson, path):
    bad = check(lesson)
    if bad:
        raise SystemExit("\n".join(bad))
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(lesson, indent=1, ensure_ascii=False))
    words = sum(len(b["narration"].split()) for c in lesson["chapters"] for b in c["beats"])
    beats = sum(len(c["beats"]) for c in lesson["chapters"])
    print(f"{path}: {len(lesson['chapters'])} chapters, {beats} beats, {words} words")


def lesson(title, chapters):
    return {"title": title, "language": "en-US", "generated_by": "written by hand (quadrilaterals pack)",
            "continuity": {"warnings": []}, "chapters": chapters}


def _norm_any(s):
    return [w for w in re.sub(r"[^\w ]", " ", s.lower()).split() if w]


def in_hindi(english, table, title):
    """The same lesson with Hindi narration (maths words and point names kept in English, as a Hindi-medium class
    says them). ``table[beat_id] = (narration, [say for each step], quiz or None)`` where quiz is
    ``(question, options, why)``. Pictures and the steps' on-screen words are the English lesson's own."""
    import copy
    lesson_hi = copy.deepcopy(english)
    lesson_hi["title"], lesson_hi["language"] = title, "hi-IN"
    for ch in lesson_hi["chapters"]:
        for b in ch["beats"]:
            if b["id"] not in table:
                raise SystemExit(f"beat {b['id']} has no Hindi")
            narration, says, quiz = table[b["id"]]
            if len(says) != len(b["steps"]):
                raise SystemExit(f"beat {b['id']}: {len(says)} Hindi anchors for {len(b['steps'])} steps")
            b["narration"] = narration
            for step, say in zip(b["steps"], says):
                step["say"] = say
            if b.get("quiz"):
                if not quiz:
                    raise SystemExit(f"beat {b['id']}: the quiz needs Hindi")
                q, options, why = quiz
                if len(options) != len(b["quiz"]["options"]) or len(why) != len(options):
                    raise SystemExit(f"beat {b['id']}: options and reasons must match the English quiz")
                b["quiz"].update(question=q, options=options, why=why, explain=why[b["quiz"]["answer_index"]])
    problems = []
    for ch in lesson_hi["chapters"]:
        for b in ch["beats"]:
            words, at = " ".join(_norm_any(b["narration"])), 0
            for st in b["steps"]:
                k = words.find(" ".join(_norm_any(st["say"])), at)
                if k < 0:
                    problems.append(f"{b['id']}: '{st['say']}' not found in order")
                else:
                    at = k
            if b.get("quiz") and not b["narration"].rstrip().endswith("?"):
                problems.append(f"{b['id']}: quiz beat does not end with its question")
    if problems:
        raise SystemExit("\n".join(problems))
    return lesson_hi


def write_hi(lesson_hi, path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(lesson_hi, indent=1, ensure_ascii=False))
    words = sum(len(b["narration"].split()) for c in lesson_hi["chapters"] for b in c["beats"])
    print(f"{path}: {len(lesson_hi['chapters'])} chapters, {words} words (Hindi)")
