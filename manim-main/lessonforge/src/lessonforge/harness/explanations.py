"""The best explanation of each concept, from a table a person checked: handed to the writer with the brief.

LGLG, 2026-10-16: "get the best explanations database and approaches to improve the videos". The project
already holds one: ``ncert-8-10-maths-science-concepts.csv`` (573 NCERT Class 8-10 sections, each with its
``key_idea`` written in the textbook's own framing WITH the common misconception, its ``prerequisites`` and
the best English and Hindi lecture for it, every link checked by hand). This module finds the rows a lesson
is about and turns them into one block of the writer's brief, so the writer starts from the explanation
good teachers give instead of its own first idea.

- Code chooses the rows (word overlap with the topic, the class within one): no model call, nothing spent.
- A match must share at least two content words with the section's concept name (its chapter adds to the score);
  in doubt nothing is attached (a wrong expert explanation is worse than none).
- The rows are put INTO the brief (``brief["explanations"]``) when a job starts, so the stage store keys the
  script by what the writer was shown, and a lesson made again later sees the same rows.
- Mistakes students actually make: the Eedi Misconceptions Graph (CC BY 4.0, Eedi; maths only), 19,294
  misconception-to-skill edges with how often each misconception shows in that skill. The skills whose names
  share at least two words with the topic give their most common misconceptions (``mistakes``).
  ``eedi-misconception-map.csv`` in ``LESSONFORGE_MISCONCEPTIONS`` or ``<workspace>/library/misconceptions/``.
- Files: every ``*.csv`` in ``LESSONFORGE_EXPLANATIONS`` (a folder or a file) or in
  ``<workspace>/library/explanations/``. ``HARNESS_EXPLANATIONS=0`` turns it off (tests do).
"""
from __future__ import annotations

import csv
import os
import re
from functools import lru_cache
from pathlib import Path

from .. import knobs, paths

MAX_ROWS = 2
FIELDS = ("concept_id", "class", "subject", "chapter", "concept", "key_idea", "prerequisites",
          "lecture1_title", "lecture1_channel", "lecture2_title", "lecture2_channel")

_STOP = set("""a an and the of in on to for with by from as at is are be or its it this that these those
how what why which when into using use their his her our your we you they them than then so not no
class ncert chapter part lesson introduction basic basics concept concepts understanding learn
""".split())


def enabled() -> bool:
    return knobs.get("HARNESS_EXPLANATIONS", "1") != "0"


def _files() -> list[Path]:
    where = os.getenv("LESSONFORGE_EXPLANATIONS")
    root = Path(where) if where else paths.sub("library", "explanations", create=False)
    if root.is_file():
        return [root]
    return sorted(root.glob("*.csv")) if root.is_dir() else []


@lru_cache(maxsize=4)
def _load(key: tuple) -> list[dict]:
    rows = []
    for name in key:
        with open(name, newline="", encoding="utf-8") as f:
            rows += [{k: (r.get(k) or "").strip() for k in FIELDS} for r in csv.DictReader(f)]
    return [r for r in rows if r["concept"] and r["key_idea"]]


def rows() -> list[dict]:
    files = _files()
    return _load(tuple(str(f) for f in files)) if files else []


def words(text: str) -> set[str]:
    out = set()
    for w in re.findall(r"[a-z][a-z'-]+", (text or "").lower()):
        w = w.strip("'-")
        if len(w) > 2 and w not in _STOP:
            out.add(w[:6])                  # a prefix, so "ratios" meets "ratio" and "trigonometric" meets "trigonometry"
    return out


def _class_of(level: str) -> int | None:
    m = re.search(r"\b(\d{1,2})\b", str(level or ""))
    return int(m.group(1)) if m else None


def find(topic: str, level: str = "", limit: int = MAX_ROWS) -> list[dict]:
    """The rows this topic is about, best first; [] when none is clearly about it."""
    want = words(topic)
    if not want:
        return []
    grade = _class_of(level)
    scored = []
    for r in rows():
        if grade is not None and r["class"].isdigit() and abs(int(r["class"]) - grade) > 1:
            continue
        name = words(r["concept"])
        hits = want & (name | words(r["chapter"]))
        if len(want & name) < 2:            # the CONCEPT itself must be named: "air pressure and winds" is not
            continue                        # the row on pressure = force / area because its chapter says winds
        score = len(hits) + 0.5 * len(want & name) + 0.1 * len(want & words(r["key_idea"]))
        if grade is not None and r["class"] == str(grade):
            score += 0.5
        scored.append((score, r))
    scored.sort(key=lambda s: -s[0])
    return [r for _, r in scored[:limit]]


MAX_MISTAKES = 4
MIN_OVERLAP = 0.45      # read on 9 real topics: below this the skill was about something else
EEDI_CREDIT = "Eedi Misconceptions Graph, CC BY 4.0, eedi.com"


def _misconception_file() -> Path | None:
    where = os.getenv("LESSONFORGE_MISCONCEPTIONS")
    root = Path(where) if where else paths.sub("library", "misconceptions", create=False)
    found = [root] if root.is_file() else (sorted(root.glob("*misconception*.csv")) if root.is_dir() else [])
    return found[0] if found else None


@lru_cache(maxsize=2)
def _edges(name: str) -> list[tuple[set, str, float, str]]:
    with open(name, newline="", encoding="utf-8") as f:
        out = []
        for r in csv.DictReader(f):
            try:
                share = float(r.get("PercentageMisconceptionExistsInThisConstruct") or 0)
            except ValueError:
                share = 0.0
            skill = r.get("ConstructName") or ""
            out.append((words(skill + " " + (r.get("SubTopicName") or "")), (r.get("MisconceptionName") or "").strip(),
                        share, skill.strip()))
    return out


_SAME = {"like": "same", "unlike": "differ", "ascend": "order", "compare": "order", "compar": "order"}


def _norm_words(text: str) -> set[str]:
    return {_SAME.get(w, w) for w in words(text)}


@lru_cache(maxsize=2)
def _skills(name: str) -> tuple[dict, dict]:
    """skill name -> its words, and each word's rarity (inverse document frequency) over the skills."""
    import math
    skills = {}
    for w, _n, _s, skill in _edges(name):
        skills.setdefault(skill, _norm_words(skill))
    df: dict[str, int] = {}
    for ws in skills.values():
        for w in ws:
            df[w] = df.get(w, 0) + 1
    return skills, {w: math.log(len(skills) / c) for w, c in df.items()}


def mistakes(topic: str, limit: int = MAX_MISTAKES) -> list[dict]:
    """The misconceptions most often seen in the skills this topic names (maths only); [] when none match.
    Skills are ranked by their weighted overlap with the topic (rare words count more: "denominator" says
    more than "fractions"); a skill must overlap by ``MIN_OVERLAP`` and only the best three speak."""
    f = _misconception_file()
    want = _norm_words(topic)
    if not f or len(want) < 2:
        return []
    skills, idf = _skills(str(f))
    scored = []
    for skill, ws in skills.items():
        hit = want & ws
        if len(hit) < 2:
            continue
        got = sum(idf[w] for w in hit)
        union = sum(idf.get(w, max(idf.values())) for w in want | ws)
        scored.append((got / union, got, skill))   # weighted overlap: the skill IS the topic, not just near it
    scored.sort(reverse=True)
    best = [skill for share, got, skill in scored[:3] if share >= MIN_OVERLAP]
    if not best:
        return []
    rank = {skill: i for i, skill in enumerate(best)}
    tally: dict[str, tuple] = {}
    for _w, name, share, skill in _edges(str(f)):
        if name and skill in rank:          # the closest skill speaks first, then by how often it is seen there
            key = (rank[skill], -share)
            if name not in tally or key < tally[name][0]:
                tally[name] = (key, skill)
    ranked = sorted(tally.items(), key=lambda kv: kv[1][0])[:limit]
    return [{"mistake": name, "seen_in": skill} for name, (_, skill) in ranked]


def attach(brief: dict) -> dict:
    """The brief with its matching rows (``explanations``), unchanged when off, already done or nothing fits."""
    if not enabled() or "explanations" in brief or not brief.get("topic"):
        return brief
    found = find(str(brief.get("topic")), str(brief.get("level") or brief.get("audience") or ""))
    seen = mistakes(str(brief.get("topic")))
    if not found and not seen:
        return brief
    keep = ("concept_id", "concept", "key_idea", "prerequisites", "lecture1_title", "lecture1_channel",
            "lecture2_title", "lecture2_channel")
    out = [{k: r[k] for k in keep if r.get(k)} for r in found]
    if seen:
        out.append({"mistakes": seen, "credit": EEDI_CREDIT})
    return {**brief, "explanations": out}


def block(found: list[dict]) -> str:
    """What the writer is told. The explanation is to be FOLLOWED, its words are not to be copied."""
    if not found:
        return ""
    lines = ["HOW THE BEST TEACHERS EXPLAIN THIS (from a checked NCERT concept base): build the lesson on this "
             "explanation and meet this mistake; write your own words, never these."]
    for r in found:
        if r.get("mistakes"):
            lines.append("- Mistakes students actually make in this skill, most common first (" + r.get("credit", "") +
                         "): " + "; ".join(m["mistake"] for m in r["mistakes"]) +
                         ". Meet the one that fits the lesson best: say it as a learner would and let the example break it.")
            continue
        lines.append(f"- {r.get('concept')}: {r.get('key_idea')}")
        if r.get("prerequisites"):
            lines.append(f"  It stands on: {r['prerequisites']} (remind the learner of it in one sentence).")
    return "\n".join(lines)
