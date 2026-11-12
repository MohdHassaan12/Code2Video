"""The concept knowledge base — one proven way to explain each concept, and the picture it is shown with.

The owner, 2026-10-15: "We need to come up with a way to find the best pictures for each of the concepts and
make knowledge-base-like things so that we can stick to some explanation." Until now every lesson was written
from the brief alone (the teaching card is off by default), so two lessons on the same topic explained it two
different ways, and the picture was whichever drawing came back first.

An entry is a teaching card (``card.SHAPE``) that has stopped changing, plus the picture that goes with it:

* **curated entries** ship in ``harness/concepts/<id>.json`` (status ``proven`` or ``locked``): written by hand from
  how the topic is taught in class, checked by ``card.check`` like any card;
* **learned entries** are written to ``<workspace>/library/concepts/<id>.json`` the first time a lesson on a new
  topic is made with a model-written card AND passes its technical checks. The next lesson on that topic is
  written from the same card, so it explains the idea the same way. A learned entry becomes ``proven`` after
  ``PROVEN_AFTER`` passing lessons and stops being used when its lessons fail more often than they pass.

Code owns the shape, the matching and the promotion; models only ever wrote the content, once.

**The picture is chosen, not taken.** ``diagrams.for_brief`` keeps the FIRST drawing that can be shown. For a
concept the choice is made once and kept, so it is worth drawing every candidate (``picture.asks``) and keeping
the best (``best_picture``): looked at by the judge, and ranked by what a lesson can do with it (parts it can
point at beat a picture shown whole). Where a built-in figure draws the idea exactly (a right triangle, fraction
bars), ``picture.prefer`` is ``figure`` and no drawing is asked for: an exact figure that moves is the better
picture for mathematics.

Nothing here raises to its caller: an unreadable file is skipped with a log line, and a lesson with no matching
entry is made exactly as before.
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path

from .. import knobs
from . import library

FOLDER = Path(__file__).parent / "concepts"
STATUS_RANK = {"locked": 3, "proven": 2, "learned": 1}
PROVEN_AFTER = 2          # passing lessons before a learned entry counts as proven
MIN_COVER = 0.6           # share of the topic's own words a name must account for (so "air pressure" is not "pressure")
MAX_EVIDENCE = 20
#: Words that say who the lesson is for or how it is asked, never what it is about.
_NOT_TOPIC = {"class", "grade", "std", "standard", "chapter", "lesson", "ncert", "cbse", "explain", "explained",
              "understand", "understanding", "learn", "learning", "introduction", "intro", "basic", "basics", "what",
              "why", "how", "concept", "topic", "video", "kid", "student", "maths", "math", "science", "physics",
              "chemistry", "biology"}


def mode() -> str:
    """``1``: use entries and keep what new lessons teach; ``use``: use entries only; ``0``: off."""
    value = (knobs.get("HARNESS_CONCEPTS") or "1").strip()
    return value if value in ("1", "use", "0") else "1"


def enabled() -> bool:
    return mode() != "0"


def learning() -> bool:
    return mode() == "1"


def learned_folder() -> Path:
    return library.root("concepts")


def _state_path(cid: str) -> Path:
    return learned_folder() / "state" / f"{_slug(cid)}.json"


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(text).lower()).strip("-")[:60] or "concept"


def _read(path: Path, log=print) -> dict | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        log(f"[concepts] {path.name} could not be read ({type(exc).__name__})")
        return None
    if not isinstance(data, dict) or not data.get("id") or not isinstance(data.get("card"), dict):
        log(f"[concepts] {path.name} is not an entry (it needs an id and a card)")
        return None
    data.setdefault("names", [])
    data.setdefault("picture", {})
    data["source"] = "curated" if path.parent == FOLDER else "learned"
    return data


def entries(log=print) -> list[dict]:
    """Every entry: the curated ones shipped with the code, then the ones this workspace learned."""
    out: dict[str, dict] = {}
    for folder in (FOLDER, learned_folder()):
        if not folder.is_dir():
            continue
        for path in sorted(folder.glob("*.json")):
            entry = _read(path, log=log)
            if entry is None:
                continue
            kept = out.get(entry["id"])
            if kept is None or STATUS_RANK.get(entry.get("status"), 0) > STATUS_RANK.get(kept.get("status"), 0):
                out[entry["id"]] = entry
    return list(out.values())


def state(cid: str) -> dict:
    """What lessons have shown about an entry (``lessons``) and the picture chosen for it (``picture``)."""
    try:
        data = json.loads(_state_path(cid).read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _save_state(cid: str, data: dict) -> None:
    path = _state_path(cid)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")


def _topic_words(brief: dict) -> set[str]:
    return {w for w in library.tokens(str((brief or {}).get("topic") or "")) if w not in _NOT_TOPIC and not w.isdigit()}


def match_score(entry: dict, words: set[str]) -> float:
    """How well an entry's names cover a topic's words: 0 for no match, higher for a closer one.

    A name matches when every one of its words is in the topic and together they are most of the topic
    (``MIN_COVER``). The longest such name wins, so "adding fractions with unlike denominators" prefers
    that entry to one named just "fractions".
    """
    if not words:
        return 0.0
    best = 0.0
    for name in entry.get("names") or []:
        own = {w for w in library.tokens(str(name)) if w not in _NOT_TOPIC}
        if not own or not own <= words:
            continue
        cover = len(own) / len(words)
        if cover >= MIN_COVER:
            best = max(best, cover + len(own) * 0.01)
    return best


def retired(entry: dict) -> bool:
    """A learned entry whose lessons fail more often than they pass is no longer used."""
    if entry.get("source") != "learned":
        return False
    lessons = state(entry["id"]).get("lessons") or []
    failed = sum(1 for x in lessons if not x.get("passed"))
    return failed >= 2 and failed > len(lessons) - failed


def find(brief: dict, log=print) -> dict | None:
    """The entry for a brief's topic, or None. A class outside the entry's range by more than two is no match."""
    if not enabled():
        return None
    words = _topic_words(brief)
    klass = library.school_class(brief)
    ranked = []
    for entry in entries(log=log):
        score = match_score(entry, words)
        if not score or retired(entry):
            continue
        low, high = (list(entry.get("classes") or []) + [None, None])[:2]
        if klass and low and high and not (low - 2 <= klass <= high + 2):
            continue
        ranked.append((score, STATUS_RANK.get(entry.get("status"), 0), entry))
    if not ranked:
        return None
    ranked.sort(key=lambda r: (r[0], r[1]), reverse=True)
    return ranked[0][2]


def as_card(entry: dict, brief: dict) -> dict:
    """The entry as a teaching card the writer reads (``card.for_writer``), marked with where it came from."""
    from . import card as teaching_card  # noqa: PLC0415 - card imports this module
    made = teaching_card.shape(entry["card"])
    picture = entry.get("picture") or {}
    chosen = (state(entry["id"]).get("picture") or {}).get("ask") or ""
    asks = [a for a in picture.get("asks") or [] if isinstance(a, str) and a.strip()]
    prefer_figure = picture.get("prefer") == "figure" and isinstance(picture.get("figure"), dict)
    made.update(
        topic=str(brief.get("topic") or entry["id"]), asked=str(brief.get("topic") or ""),
        klass=library.school_class(brief), sources=[], problems=[],
        concept=entry["id"], concept_status=entry.get("status", ""), concept_source=entry.get("source", ""),
        diagram_ask="" if prefer_figure else (chosen or (asks[0] if asks else made.get("diagram_ask", ""))),
        picture_asks=[] if prefer_figure else asks,
    )
    if prefer_figure:
        made["figure_hint"] = picture["figure"]
        made["no_drawing"] = True          # an exact figure is the picture: do not ask the drawing service for another
    return made


# ── the best picture for a concept ───────────────────────────────────────────

def picture_score(ready: dict | None) -> float:
    """What a lesson can do with a prepared drawing. 0 for none or one the judge found wrong."""
    if not ready:
        return 0.0
    verdict = ready.get("judged")
    if verdict is not None and not verdict.get("ok", True):
        return 0.0
    score = 1.0
    if ready.get("shown") == "parts":
        score = 2.0 + min(len(ready.get("parts") or []), 8) / 8       # parts to point at, up to what a phone can read
    elif len(ready.get("panels") or []) >= 2:
        score = 1.5                                                    # a before-and-after the lesson can bring in
    if verdict is None:
        score -= 0.25                                                  # nobody looked at it
    return score


def best_picture(entry_or_card: dict, brief: dict, log=print, prepare=None) -> dict | None:
    """Draw every candidate request for a concept, keep the best, remember the choice. None when none can be shown.

    Done once per concept: the choice is kept in the entry's state and ``as_card`` asks for that one drawing
    from then on (the drawing service caches by request, so a kept choice costs nothing to draw again).
    """
    from . import diagrams  # noqa: PLC0415
    cid = entry_or_card.get("concept") or entry_or_card.get("id")
    asks = list(dict.fromkeys(entry_or_card.get("picture_asks") or (entry_or_card.get("picture") or {}).get("asks") or []))
    if not cid or not asks or not diagrams.available():
        return None
    kept = state(cid)
    chosen = kept.get("picture") or {}
    prepare = prepare or (lambda ask: diagrams.prepare_checked(ask, library.school_class(brief), "en", log=log))
    if chosen.get("ask") and chosen.get("asks") == asks:
        ready = prepare(chosen["ask"])
        if ready:
            return ready
    tried, best, best_ask = [], None, ""
    for ask in asks[:3]:
        ready = prepare(ask)
        score = picture_score(ready)
        tried.append({"ask": ask, "score": round(score, 3),
                      "parts": len((ready or {}).get("parts") or []), "shown": (ready or {}).get("shown", "")})
        if score > picture_score(best):
            best, best_ask = ready, ask
    log(f"[concepts] pictures tried for {cid}: " + "; ".join(f"“{t['ask'][:50]}…” {t['score']}" for t in tried))
    if best is None:
        return None
    kept["picture"] = {"ask": best_ask, "asks": asks, "tried": tried, "when": time.strftime("%Y-%m-%d %H:%M")}
    try:
        _save_state(cid, kept)
    except OSError:
        pass
    return best


# ── what a finished lesson teaches the knowledge base ────────────────────────

def record(card: dict | None, brief: dict, job_id: str, report: dict | None, looked: dict | None = None, log=print) -> str:
    """After a lesson: note how it went against its entry, and keep a new topic's card as a learned entry.

    Returns what was done: "recorded", "learned", "promoted" or "" (nothing).
    """
    if not card or not enabled():
        return ""
    passed = bool(report and report.get("status") == "technical_checks_passed")
    row = {"job": job_id, "when": time.strftime("%Y-%m-%d %H:%M"), "passed": passed,
           "frame_findings": (looked or {}).get("findings")}
    cid = card.get("concept")
    done = ""
    if not cid:
        # A card a model wrote for a topic the knowledge base did not have. Kept only from a lesson that passed:
        # a card behind a failed lesson is not an explanation worth repeating.
        if not (learning() and passed and card.get("big_idea", {}).get("text")):
            return ""
        cid = _slug(card.get("asked") or card.get("topic") or brief.get("topic") or "")
        if (learned_folder() / f"{cid}.json").is_file() or (FOLDER / f"{cid}.json").is_file():
            return ""
        keep = {k: v for k, v in card.items() if k not in ("diagram", "problems", "sources", "pack_digest", "source_flows")}
        names = list(dict.fromkeys(n for n in (str(card.get("asked") or ""), str(card.get("topic") or ""),
                                               str(brief.get("topic") or "")) if n.strip()))
        entry = {"id": cid, "names": [n.lower() for n in names], "subject": library.school_subject(brief) or "",
                 "classes": [card["klass"], card["klass"]] if card.get("klass") else [], "status": "learned",
                 "picture": {"prefer": "drawing", "figure": None,
                             "asks": [a for a in [card.get("diagram_ask") or (card.get("diagram") or {}).get("ask") or ""] if a]},
                 "card": keep, "learned_from": job_id}
        path = learned_folder() / f"{cid}.json"
        path.write_text(json.dumps(entry, indent=1, ensure_ascii=False), encoding="utf-8")
        log(f"[concepts] kept this lesson's card as the explanation for “{names[0] if names else cid}”")
        done = "learned"
    kept = state(cid)
    kept["lessons"] = ((kept.get("lessons") or []) + [row])[-MAX_EVIDENCE:]
    try:
        _save_state(cid, kept)
    except OSError:
        return done
    path = learned_folder() / f"{cid}.json"
    if path.is_file():
        try:
            entry = json.loads(path.read_text(encoding="utf-8"))
        except ValueError:
            return done or "recorded"
        wins = sum(1 for x in kept["lessons"] if x.get("passed"))
        if entry.get("status") == "learned" and wins >= PROVEN_AFTER and wins > len(kept["lessons"]) - wins:
            entry["status"] = "proven"
            path.write_text(json.dumps(entry, indent=1, ensure_ascii=False), encoding="utf-8")
            log(f"[concepts] “{cid}” is now proven ({wins} lessons passed)")
            return "promoted"
    return done or "recorded"
