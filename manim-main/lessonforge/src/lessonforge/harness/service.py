"""Sessions and generation jobs for the content harness.

A session is an intake conversation filling a brief. A job turns a finished brief
into a video:  script → verify → speech → render → assemble → check → (repair) →
review → done.

A brief comes in one of two kinds. The usual one states an INTENT (topic, audience,
goal …) and a model writes the words. A brief with ``mode: "script"`` carries the words
themselves (``harness/scripted.py``): they are spoken as written, a model designs only
the screen, and the reviewer reports on them without changing them unless asked to.

Jobs run on a small thread pool and are polled — a generation takes minutes, and a
long stage must never sit on an open HTTP connection.

**Nothing a user waited for is kept only in memory.** Every job writes ``job.json``
into its lesson directory at each stage, and a finished lesson directory
(``lesson.json``, ``timeline.json``, ``output/…``) is enough on its own to rebuild
the job record, so a server restart loses no result. Sessions are saved the same way.

**A built video is never lost to a later step.** The first real test run rendered a
15-minute lesson, then died writing a sidecar file and reported the whole job as
failed. Everything after the checks (vision review, review page, interaction file)
is now advisory: it logs and moves on, and the result fields are computed from disk
by the same function that recovers old jobs.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import shutil
import threading
import time
import uuid
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .. import knobs
from .. import paths, spend
from ..longform import build as lesson_build
from ..longform.audio import BuildOptions, build_audio
from ..longform import look as lesson_look
from ..longform import visual_actions
from ..longform import qa as lesson_qa
from ..longform import storyboard as lesson_storyboard
from ..longform import sync_repair, timeline_compiler
from ..longform.contract import Lesson
from ..longform.review import write_review
from . import card as teaching_card
from . import forge, pack, story_first
from .shapes import unfilled as _shapes_unfilled
from . import concepts, contract, explanations
from . import qa
from . import edit as lesson_edit

from . import (annotate, coherence, compose, critic, rubric, diagrams, frameworks, intake, interviewer, library, paperlook, questions, repaint, repairs, scripted, sequence, skill,
               store, tryit, typeset, vision_review, voice, writer)

MAX_TRACKED = 200
STAGES = ["script", "verify", "visuals", "compose", "speech", "render", "assemble", "check", "review", "done"]
INTERRUPTED = "The server restarted while this lesson was being generated. Start it again."
STOPPED = "Stopped before it was finished."
ELSEWHERE = "This lesson is being made by another process on the server. It shows here when it is done."


class _Stopped(Exception):
    """The run was asked to stop (``remove_job``); raised at a stage boundary."""
_EXECUTOR = ThreadPoolExecutor(max_workers=int(os.getenv("HARNESS_WORKERS", "2")))   # the process's, not a lesson's
_LOCK = threading.Lock()
_SESSIONS: "OrderedDict[str, dict]" = OrderedDict()
_JOBS: "OrderedDict[str, dict]" = OrderedDict()
#: Tests (and callers embedding the harness) can set this to a ``(prompt, system) -> dict``
#: callable to replace the interviewer model, or to ``False`` to force the plain questions.
INTAKE_LLM = None


def _remember(store: OrderedDict, key: str, value: dict) -> dict:
    with _LOCK:
        store[key] = value
        while len(store) > MAX_TRACKED:
            store.popitem(last=False)
    return value


def _write_json(path: Path, data) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=1, ensure_ascii=False, default=str), encoding="utf-8")
    os.replace(tmp, path)


def _read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


# ── intake sessions ───────────────────────────────────────────────────────────

def _session_path(session_id: str) -> Path:
    return paths.sub("sessions") / f"{session_id}.json"


def _save_session(session: dict) -> None:
    try:
        _write_json(_session_path(session["id"]), session)
    except OSError:
        pass


def _session(session_id: str) -> dict:
    session = _SESSIONS.get(session_id)
    if session is None and session_id.isalnum():
        session = _read_json(_session_path(session_id))
        if session:
            _remember(_SESSIONS, session_id, session)
    if session is None:
        raise KeyError(session_id)
    return session


def _view(session: dict) -> dict:
    brief = session["brief"]
    progress = intake.progress(brief)
    progress["complete"] = session.get("question") is None and bool(brief.get("topic"))
    return {"session_id": session["id"], "question": session.get("question"), "brief": brief,
            "summary": intake.summary(brief), "progress": progress, "note": session.get("note")}


def _intake_llm():
    if INTAKE_LLM is False:
        return None
    return INTAKE_LLM or interviewer.default_llm()


def _apply_answer(session: dict, question_id: str, value) -> dict:
    """Record one answer; returns the exchange (what was asked, what was said) for the next turn."""
    brief = session["brief"]
    asked = session.get("question") or {}
    if asked.get("id") != question_id:
        asked = {}
    text = "" if value is None else str(value).strip()
    options = asked.get("options") or []
    picked = next((o for o in options if str(o["value"]) == text), None)
    free_text = asked.get("kind", "text") == "text" and picked is None
    if interviewer.is_delegation(text):
        # "You decide": take the first option we offered (the one we would choose), or
        # leave an optional field empty so the writer chooses. Never store the phrase.
        free_text = False
        if options:
            value = options[0]["value"]
            session["pending_note"] = f"You left that to me, so I will go with: {options[0]['label']}."
        elif question_id == "goal":
            value = f"Solve typical problems on {brief.get('topic', 'this topic')} and explain each step"
            session["pending_note"] = f"You left that to me, so the goal is: {value}."
        elif question_id == "audience":
            value = "School students"
        elif question_id in ("topic", "focus"):
            value = ""          # a video needs a topic: the question is asked again
        else:
            value = ""
    session.setdefault("history", []).append({"id": question_id, "prompt": asked.get("prompt", ""), "answer": text})
    if question_id == "focus" and brief.get("topic") and (interviewer.wants_everything(text) or value == ""):
        # "Which one idea?" answered with "all of them" (or left to us): the topic stays what
        # it was. A tester's "we need full coverage of all of them" was once stored AS the
        # topic. The wish is kept for the writer, and the question is not asked again.
        brief["focus"] = brief["topic"]
        brief.pop("needs_focus", None)
        if text and not interviewer.is_delegation(text):
            brief.setdefault("notes", {})["scope"] = text
        session["pending_note"] = (f"Understood — one video covering the main ideas of {brief['topic']}. "
                                   "For depth on each idea, a series of short lessons works better; "
                                   "the chapter planner can lay one out.")
        return {"id": question_id, "prompt": asked.get("prompt") or question_id, "answer": text, "free_text": False}
    intake.answer(brief, question_id, value)
    return {"id": question_id, "prompt": asked.get("prompt") or question_id, "answer": text, "free_text": free_text}


def _learned_note(learned: dict) -> str:
    labels = {"audience": "for", "grade": "class", "level": "starting point", "goal": "goal", "language": "language",
              "duration_minutes": "minutes", "context": "running example", "misconception": "known mistake"}
    return "Noted from your answer — " + "; ".join(f"{labels.get(k, k)}: {v}" for k, v in learned.items()) + "."


def _ask(session: dict, last: dict | None) -> None:
    """Decide the next question (code) and, when a model is available, how to ask it for this topic."""
    brief = session["brief"]
    note = session.pop("pending_note", None)
    base = intake.next_question(brief)
    question = None if base is None else {**base, "source": "default"}
    llm = _intake_llm() if base is not None else None
    if llm and interviewer.wants_model(base, last):
        reasks = session.setdefault("reasks", {})
        field = last["id"] if last else None
        may_push_back = bool(last and last.get("free_text") and field in interviewer.SHARPEN_FIELDS
                             and not reasks.get(field))
        try:
            result = interviewer.turn(brief, base, last, llm, may_push_back=may_push_back)
            reask = ""
            if (may_push_back and field == "goal" and not result["unclear"]
                    and interviewer.is_vague_goal(last["answer"], brief)):
                result["unclear"] = (f"“{last['answer']}” does not yet say what they will be able to do. "
                                     "Which skill exactly?")
            if result["unclear"] and may_push_back:
                reasks[field] = 1
                brief.setdefault("notes", {})[field] = last["answer"]
                if field == "topic":
                    # A whole chapter: narrowed in its own question, once we know who it is for.
                    brief["needs_focus"] = True
                else:
                    brief.pop(field, None)
                    note = reask = result["unclear"]
            elif result["learned"]:
                brief.update(result["learned"])
                if "grade" in result["learned"] and not brief.get("audience"):
                    brief["audience"] = f"Class {brief['grade']} students"
                note = (note + " " if note else "") + _learned_note(result["learned"])
            new_base = intake.next_question(brief)
            if new_base is None:
                question = None
            elif new_base["id"] == base["id"] and not reask:
                question = interviewer.merge_question(new_base, result["raw_question"])
            else:
                # The field to ask changed (an answer was sent back, or what we learned
                # already covered it): have the question written for the right field.
                question = {**new_base, "source": "default"}
                if reask or interviewer.wants_model(new_base, None):
                    second = interviewer.turn(brief, new_base, last if reask else None, llm, reask_reason=reask)
                    question = interviewer.merge_question(new_base, second["raw_question"])
        except Exception as exc:  # noqa: BLE001 - the plain question always works
            session["model_errors"] = session.get("model_errors", 0) + 1
            session["last_model_error"] = f"{type(exc).__name__}: {str(exc)[:160]}"
            fallback = intake.next_question(brief)
            question = None if fallback is None else {**fallback, "source": "default"}
    session["question"], session["note"] = question, note
    _save_session(session)


def start_session(opening: str | None = None) -> dict:
    session_id = uuid.uuid4().hex[:12]
    session = _remember(_SESSIONS, session_id, {"id": session_id, "brief": {}, "created": time.time(),
                                                "history": [], "question": None, "note": None, "reasks": {}})
    last = None
    if opening and opening.strip():
        last = _apply_answer(session, "topic", opening)
        last["prompt"] = "What should this video teach?"
    _ask(session, last)
    return _view(session)


def get_session(session_id: str) -> dict:
    return _view(_session(session_id))


def answer_session(session_id: str, question_id: str, value) -> dict:
    session = _session(session_id)
    last = _apply_answer(session, question_id, value)
    _ask(session, last)
    return _view(session)


def session_brief(session_id: str) -> dict:
    """The brief to generate from (bookkeeping keys removed)."""
    brief = dict(_session(session_id)["brief"])
    brief.pop("needs_focus", None)
    return brief


# ── generation jobs ───────────────────────────────────────────────────────────

def tts_instructions(language: str) -> str:
    """The delivery note for the narrator (part of the audio cache key)."""
    custom = os.getenv("LESSONFORGE_TTS_INSTRUCTIONS", "").strip()
    if custom:
        return custom.replace("|", " ")
    if language in ("hinglish", "hi-IN"):
        return ("A warm, lively Indian school teacher talking to her class. The conversation is in Hindi; say every "
                "number, formula and technical term in English exactly as written, the way an English-medium "
                "teacher does. Unhurried and clear, with real expression, and a short pause after each question.")
    return ("A warm, lively Indian school teacher talking to her class. Unhurried and clear, with real expression, "
            "and a short pause after each question.")


#: The owner's own text-to-speech service (``speech.IndicBackend``): its voices, the first is the default.
OWN_VOICES = ("kavya", "agastya", "maitri", "vinaya")


def _own_voice_ready() -> bool:
    return bool(os.getenv("INDIC_TTS_URL", "").strip() and os.getenv("INDIC_TTS_KEY", "").strip())


def _paid_voices(language: str) -> dict[str, str]:
    """The narration voices that cost money per lesson, by the name a lesson may choose them by."""
    locale = {"hinglish": "hi-IN"}.get(language, language or "en-IN")
    paid = {}
    if os.getenv("SARVAM_AI_KEY"):
        # Sarvam's own backend, not the engine's chain: there a failed clip is answered in another
        # provider's voice, and a long lesson changes narrator mid-way (speech.SarvamBackend).
        # Slowed on purpose (HARNESS_SARVAM_PACE): at its own pace of 1.0 the voice speaks about 196 words a
        # minute, against about 140 for the Gemini voice that the lesson lengths were measured with; a
        # six-minute request came out at 3 min 47 s, fast for a school learner. 0.75 measured about 157.
        paid["sarvam"] = (f"sarvam:{knobs.get('HARNESS_SARVAM_SPEAKER', 'shubh')}/{locale}"
                          f"@{knobs.get('HARNESS_SARVAM_PACE', '0.75')}")
    if os.getenv("OPENROUTER_API_KEY"):
        # Gemini TTS straight from the long-form speech stack: block synthesis with a
        # delivery note, measured and cached per beat (speech.OpenRouterTTSBackend).
        tier = knobs.get("HARNESS_TTS_TIER", "flash")
        voice = knobs.get("HARNESS_TTS_VOICE", "Kore")
        paid["gemini"] = f"gemini:{tier}/{voice}|{tts_instructions(language)}"
    return paid


#: Microsoft's neural voices offered for a lesson (``speech.EdgeBackend``), a woman's and a man's per language.
EDGE_VOICES = (("hi-IN-SwaraNeural", "Swara", "hi"), ("hi-IN-MadhurNeural", "Madhur", "hi"),
               ("en-IN-NeerjaNeural", "Neerja", "en"), ("en-IN-PrabhatNeural", "Prabhat", "en"),
               ("te-IN-ShrutiNeural", "Shruti", "te"), ("te-IN-MohanNeural", "Mohan", "te"),
               ("ta-IN-PallaviNeural", "Pallavi", "ta"), ("ta-IN-ValluvarNeural", "Valluvar", "ta"))
#: Kokoro's voices offered for a lesson (``speech.KokoroBackend``; a name beginning with h is a Hindi voice).
KOKORO_CHOICES = (("af_heart", "Heart", "en"), ("am_michael", "Michael", "en"), ("hf_alpha", "Alpha", "hi"), ("hm_omega", "Omega", "hi"))
#: Which lesson languages a voice of each tongue can narrate.
_SPEAKS = {"en": ["en-IN"], "hi": ["hi-IN", "hinglish"], "te": ["te-IN"], "ta": ["ta-IN"]}
_EVERY = ["en-IN", "hinglish", "hi-IN", "te-IN", "ta-IN"]
#: What each kind of voice costs, as the voice picker shows it. USD a minute of narration where it is known and is
#: this app's: Gemini measured on 155 minutes of lessons (2026-10-15); Sarvam bills in rupees on its own account.
VOICE_COSTS = {
    "indic": ("Free to this app: your own speech service", 0.0),
    "edge": ("Free: Microsoft's online voices (not an official service: it can stop working)", 0.0),
    "kokoro": ("Free: runs on this machine", 0.0),
    "http": ("Your own speech server: whatever it costs you", None),
    "gtts": ("Free: Google's basic voice", 0.0),
    "browser": ("Free: the learner's device reads the captions aloud (web player; sound depends on the device)", 0.0),
    "sarvam": ("Paid: Sarvam bills it per character, on its own account", None),
    "gemini": ("Paid: about 1.4 cents a minute of narration, on the model account", 0.0136),
}
#: Timing every word of a narration (a speech recogniser): measured about 0.15 cents a minute; not for the device voice.
TIMING_USD_PER_MINUTE = 0.0015


def _voice_rows(own: bool, paid: dict) -> list[dict]:
    """Every voice this server can narrate with, in the order the picker shows them."""
    import importlib.util

    def row(vid, label, kind, group, languages, paid_=False):
        text, usd = VOICE_COSTS[kind]
        return {"id": vid, "label": label, "kind": kind, "group": group, "languages": languages, "paid": paid_,
                "ours": kind == "indic", "cost": text, "usd_per_minute": usd}
    rows = [row(f"indic:{name}", name.capitalize(), "indic", "Your voice service", ["en-IN", "hinglish", "hi-IN"])
            for name in OWN_VOICES] if own else []
    if importlib.util.find_spec("edge_tts") is not None and knobs.get("HARNESS_EDGE_VOICES", "1") == "1":
        rows += [row(f"edge:{voice}", label, "edge", "Microsoft voices (online)", _SPEAKS[tongue]) for voice, label, tongue in EDGE_VOICES]
    model = os.getenv("KOKORO_MODEL") or str(paths.home() / "models" / "kokoro-v1.0.onnx")
    if os.path.exists(model) and knobs.get("HARNESS_LOCAL_VOICE", "1") == "1":
        rows += [row(f"kokoro:{voice}", label, "kokoro", "On this machine", _SPEAKS[tongue]) for voice, label, tongue in KOKORO_CHOICES]
    if os.getenv("TTS_HTTP_URL", "").strip():
        names = [n.strip() for n in os.getenv("TTS_HTTP_VOICES", "").split(",") if n.strip()]
        rows += [row(f"http:{name}" if name else "http", name.capitalize() if name else "Your server", "http", "Your speech server", _EVERY)
                 for name in (names or [""])]
    if knobs.get("HARNESS_ALLOW_GTTS", "1") == "1":
        rows.append(row("gtts", "Google basic", "gtts", "Basic", _EVERY))
    rows.append(row("browser", "Learner's device", "browser", "Learner's device", _EVERY))
    rows += [row(name, {"sarvam": "Sarvam", "gemini": "Gemini"}[name], name, "Paid", _EVERY, paid_=True) for name in paid]
    return rows


def voices(language: str | None = None) -> dict:
    """What a lesson can be narrated with on this server, for the app's voice choice, with what each costs. No
    address or key in it. ``language`` keeps only the voices that can narrate a lesson in it."""
    own, paid = _own_voice_ready(), _paid_voices("en-IN")
    default = knobs.get("HARNESS_INDIC_SPEAKER", OWN_VOICES[0]).strip().lower()
    rows = _voice_rows(own, paid)
    if language:
        rows = [r for r in rows if language in r["languages"]]
    return {"voices": rows,
            "default": f"indic:{default if default in OWN_VOICES else OWN_VOICES[0]}" if own else next(iter(paid), None),
            "paid_by_default": not own or knobs.get("HARNESS_PAID_VOICES", "0") == "1",
            "timing": {"usd_per_minute": TIMING_USD_PER_MINUTE,
                       "text": "Every narrated lesson also has its words timed: about 0.15 cents a minute (not for the device voice)."}}


def voice_choice(value) -> str | None:
    """A lesson's chosen voice as this server knows it (``indic:maitri``, ``edge:hi-IN-SwaraNeural``,
    ``kokoro:hf_alpha``, ``gtts``, ``browser``, ``sarvam``, ``gemini`` …), or None. Case is kept: Microsoft's voice
    names have capitals."""
    value = str(value or "").strip()
    known = {row["id"]: row["id"] for row in voices()["voices"]}
    return known.get(value) or {k.lower(): k for k in known}.get(value.lower())


def voice_candidates(language: str, prefer: str | None = None) -> list[str]:
    """Voices to try, best first; the last one always works (silence sized to the words).

    The owner's own voice service comes first whenever it is set up (``INDIC_TTS_URL`` and
    ``INDIC_TTS_KEY``): it is theirs and costs nothing per lesson. The owner's words on
    2026-10-09: "Don't use audio credits like Gemini … or give an option to select these
    things." So the paid voices (Sarvam, Gemini through OpenRouter) are tried only when they
    are asked for: chosen for this lesson (``prefer``, from the brief's ``voice_choice``), or
    switched on for every lesson with ``HARNESS_PAID_VOICES=1``. On a server without the
    owner's service they are tried as before. A chosen voice that fails falls back down the
    same list, so a lesson is not lost to it.
    """
    forced = knobs.get("HARNESS_VOICE", "").strip()
    if forced:
        return [forced, "silent"]
    locale = {"hinglish": "hi-IN"}.get(language, language or "en-IN")
    own, paid = _own_voice_ready(), _paid_voices(language)
    speaker = knobs.get("HARNESS_INDIC_SPEAKER", OWN_VOICES[0]).strip().lower()
    candidates = []
    prefer = voice_choice(prefer)
    chosen = next((r for r in voices()["voices"] if r["id"] == prefer), None)
    if chosen and (language or "en-IN") not in chosen["languages"]:
        prefer = None                       # a voice that cannot speak this lesson's language: the usual voices instead
    kind, _, name = (prefer or "").partition(":")
    if kind == "browser":
        # The learner's device reads the captions; the video carries silence timed to the words. Nothing to fall back
        # to and nothing to fail. A Latin-letter Hinglish caption is read better by an Indian English voice than by a
        # Hindi one, which expects Devanagari.
        return [f"browser:{'en-IN' if language == 'hinglish' else locale}"]
    if kind == "indic":
        speaker = name
    elif prefer in paid:
        candidates.append(paid[prefer])
    elif kind == "edge":
        candidates.append(f"edge:{name}/{language or 'en-IN'}")
    elif kind == "kokoro":
        candidates.append(f"kokoro:{name}@0.85")
    elif kind == "http":
        candidates.append(f"http:{name}/{language or 'en-IN'}")
    elif kind == "gtts":
        candidates.append(f"gtts:{locale.split('-')[0]}")
    if own:
        # The lesson's language rides in the spec: for Hinglish the backend gives the voice the same words
        # with the Hindi in Devanagari (the service's own form); captions and timing keep the lesson's text.
        candidates.append(f"indic:{speaker if speaker in OWN_VOICES else OWN_VOICES[0]}/{language or 'en-IN'}")
    if not own or knobs.get("HARNESS_PAID_VOICES", "0") == "1":
        candidates += [spec for spec in paid.values() if spec not in candidates]
    # The voice on this machine, before the basic one: Kokoro, in English and (since 2026-10-12, the owner's word:
    # "deploy some TTS as a fallback if we aren't able to get that Indic TTS URL") in Hindi for Hindi and Hinglish.
    model = os.getenv("KOKORO_MODEL") or str(paths.home() / "models" / "kokoro-v1.0.onnx")
    if os.path.exists(model) and knobs.get("HARNESS_LOCAL_VOICE", "1") == "1":
        if locale.startswith("en"):
            candidates.append("kokoro")
        elif locale.startswith("hi"):
            candidates.append(f"kokoro:{knobs.get('HARNESS_KOKORO_HINDI', 'hf_alpha').strip() or 'hf_alpha'}@0.85")
    if knobs.get("HARNESS_ALLOW_GTTS", "1") == "1":
        candidates.append(f"gtts:{locale.split('-')[0]}")
    return list(dict.fromkeys(candidates + ["silent"]))     # a chosen voice is not tried twice


def _public(job: dict) -> dict:
    return {k: v for k, v in job.items() if not k.startswith("_")}


def _lesson_root(job_id: str) -> Path:
    return paths.home() / "lessons" / job_id


def _save_job(job: dict) -> None:
    try:
        root = _lesson_root(job["job_id"])
        if root.is_dir():
            _write_json(root / "job.json", _public(job))
    except OSError:
        pass


def _concept_of(brief: dict) -> tuple[dict | None, list[str]]:
    """The checked concept a lesson was written on (``brief["explanations"]``) and the mistakes it was told of."""
    rows = brief.get("explanations") or []
    found = next((r for r in rows if r.get("concept_id")), None)
    concept = {"id": found["concept_id"], "name": found.get("concept") or ""} if found else None
    mistakes = [m["mistake"] for r in rows for m in (r.get("mistakes") or []) if m.get("mistake")]
    return concept, mistakes


_MISTAKE_STOP = frozenset("the a an of to is are and or in on for that this it be by with as when not from their they "
                          "believes thinks students student does do".split())


def _misconception_of(text: str, mistakes: list[str]) -> str | None:
    """The one listed mistake a wrong option's words plainly name (three shared words or more), else None.
    A guess is worse than no tag: a tag feeds what the learner is told to practise."""
    words = {w for w in re.findall(r"[a-z]+", text.lower()) if len(w) > 2 and w not in _MISTAKE_STOP}
    scored = sorted(((len(words & {w for w in re.findall(r"[a-z]+", m.lower()) if len(w) > 2 and w not in _MISTAKE_STOP}), m)
                     for m in mistakes), reverse=True)
    if not scored or scored[0][0] < 3 or (len(scored) > 1 and scored[1][0] == scored[0][0]):
        return None
    return scored[0][1]


def write_interactions(root: Path, job_id: str, brief: dict, lesson_dict: dict, duration: float) -> int:
    """Interaction points for a player that can pause (``lessonforge.interactions/0.1``).

    Every thinking pause becomes a question card — the sentence spoken just before the
    pause — with the answer that follows it. Schema: docs/research/approaches/05_* §Q3.
    """
    timeline = json.loads((root / "timeline.json").read_text(encoding="utf-8"))
    chapters = lesson_dict["chapters"]
    beats = [b for c in chapters for b in c["beats"]]
    grade = int(brief.get("grade") or 0)
    band = "6-8" if not grade or grade <= 8 else "9-10" if grade <= 10 else "11-12"
    language = str(brief.get("language") or "en-IN")
    interactions = []
    concept, mistakes = _concept_of(brief)
    chapter_start: dict = {}
    for i, (entry, beat) in enumerate(zip(timeline, beats)):
        chapter_start.setdefault(entry["chapter"], (i, entry["start"]))
        if not beat.get("thinking_pause_seconds") and not (beat.get("quiz") or {}).get("made_by"):
            continue                   # a card made by code needs no pause in the video: the player stops for it
        sentences = entry.get("sentences") or []
        question = sentences[-1]["text"] if sentences else beat["narration"]
        answer = beats[i + 1]["narration"].split(". ")[0].rstrip(".") + "." if i + 1 < len(beats) else ""
        role = next((c.get("role", "") for c in chapters if c["id"] == entry["chapter"]), "")
        quiz = beat.get("quiz") or {}
        if quiz.get("made_by"):
            answer = quiz.get("explain") or answer     # the next beat does not answer a card the voice never asked
        # Each option answers for itself (``quiz["why"]``, harness/questions.py): why the right one is right, what
        # makes a wrong one tempting and why it fails. An older lesson has one line for all of them.
        why = quiz.get("why") if isinstance(quiz.get("why"), list) and len(quiz["why"]) == len(quiz.get("options") or []) else None
        options = [{"id": "abcd"[k], "text": text, "correct": k == quiz.get("answer_index"),
                    "feedback": str(why[k]) if why else ((quiz.get("explain") or "Yes.") if k == quiz.get("answer_index")
                                                         else "Not quite. " + (quiz.get("explain") or ""))}
                   for k, text in enumerate(quiz.get("options") or [])]
        for o in options:
            if not o["correct"] and (m := _misconception_of(o["text"] + " " + o["feedback"], mistakes)):
                o["misconception"] = m
        kind = quiz.get("kind") or ""
        first, start = chapter_start[entry["chapter"]]
        # Where to watch again after a wrong answer: the start of this part, or of the part before when the
        # question opens its part. A prediction is asked BEFORE the idea is shown, so there is nothing to go back to.
        if first == i and i > 0:
            start = next((timeline[j]["start"] for j in range(i - 1, -1, -1)
                          if chapter_start[timeline[j]["chapter"]][0] == j), 0.0)
        on_wrong = ({"seek_to": round(start, 2), "allow_skip": True}
                    if options and kind != "predict" and start < entry["start"] else None)
        interactions.append({
            "id": f"q{len(interactions) + 1}",
            "type": "mcq" if options else ("recall" if role == "recap" else "predict"),
            "t": round(entry["start"] + entry.get("speech_end", entry["duration"]), 2), "pause": True,
            "resume_at": round(entry["start"] + entry["duration"], 2),
            "max_wait_s": max(15, int(beat["thinking_pause_seconds"]) * 5), "scored": bool(options),
            "prompt": {"text": quiz.get("question") or question}, "options": options,
            "answer": {"text": answer} if answer else None,
            "hints": [beat["check"]] if beat.get("check") else [], "on_wrong": on_wrong,
            "confidence": bool(options), "kind": kind or None, "concept": concept,
            "segment_id": f"beat-{beat['id']}", "chapter": entry["chapter"],
        })
    starts = {}
    for entry in timeline:
        starts.setdefault(entry["chapter"], entry["start"])
    _write_json(root / "output" / "interactions.json", {
        "schema": "lessonforge.interactions/0.1", "video_id": job_id,
        "lang": "hinglish" if language == "hinglish" else language.split("-")[0], "band": band,
        "duration_s": duration,
        "chapters": [{"t": starts.get(c["id"], 0.0), "title": c["title"]} for c in chapters],
        "interactions": interactions})
    return len(interactions)


#: One video, several viewers: which depths each way of watching keeps.
CUTS = (("full", "Full lesson", "Everything, from the basics", ("basics", "core", "practice", "extra")),
        ("standard", "Skip the basics", "For learners who know the prerequisites", ("core", "practice", "extra")),
        ("revision", "Quick revision", "Only the idea, the method and the recap", ("core",)),
        ("summary", "Summary", "The idea and the recap", ()))
_SUMMARY_ROLES = ("idea", "name", "claim", "recap")


def write_outline(root: Path, lesson_dict: dict) -> dict:
    """``output/outline.json``: the lesson as timed segments with a depth, and the cuts built from them.

    A cut is a list of time ranges of the ONE rendered video, so a player can offer
    "full / skip the basics / quick revision / summary" by skipping, and ``export_cut``
    can write any of them as its own file. Nothing is re-generated.
    """
    timeline = json.loads((root / "timeline.json").read_text(encoding="utf-8"))
    by_id = {t["id"]: t for t in timeline}
    segments = []
    for chapter in lesson_dict["chapters"]:
        for beat in chapter["beats"]:
            entry = by_id.get(beat["id"])
            if entry is None:
                continue
            segments.append({"beat": beat["id"], "chapter": chapter["id"], "chapter_title": chapter["title"],
                             "role": chapter.get("role", ""), "depth": writer.beat_depth(beat, chapter.get("role", "")),
                             "start": round(entry["start"], 3), "end": round(entry["start"] + entry["duration"], 3)})
    cuts = []
    for cut_id, label, hint, depths in CUTS:
        if cut_id == "summary":
            keep = [s for s in segments if s["depth"] == "core" and s["role"] in _SUMMARY_ROLES]
            keep = keep or [s for s in segments if s["chapter"] == segments[-1]["chapter"]] if segments else []
        else:
            keep = [s for s in segments if s["depth"] in depths]
        ranges = []
        for seg in keep:
            if ranges and abs(ranges[-1][1] - seg["start"]) < 0.05:
                ranges[-1][1] = seg["end"]
            else:
                ranges.append([seg["start"], seg["end"]])
        cuts.append({"id": cut_id, "label": label, "hint": hint, "beats": [s["beat"] for s in keep],
                     "ranges": ranges, "seconds": round(sum(b - a for a, b in ranges), 2)})
    # A cut that keeps everything, or nothing, is not a choice worth offering.
    full = cuts[0]["seconds"] if cuts else 0.0
    cuts = [c for c in cuts if c["id"] == "full" or (c["seconds"] > 5 and c["seconds"] < full - 5)]
    seen, unique = set(), []
    for c in cuts:
        key = tuple(c["beats"])
        if key not in seen:
            seen.add(key)
            unique.append(c)
    outline = {"schema": "lessonforge.outline/0.1", "title": lesson_dict.get("title", ""), "duration_s": full,
               "chapters": [{"id": c["id"], "title": c["title"], "role": c.get("role", ""),
                             "depths": sorted({s["depth"] for s in segments if s["chapter"] == c["id"]}),
                             "start": next((s["start"] for s in segments if s["chapter"] == c["id"]), 0.0),
                             "end": next((s["end"] for s in reversed(segments) if s["chapter"] == c["id"]), 0.0)}
                            for c in lesson_dict["chapters"]],
               "segments": segments, "cuts": unique}
    _write_json(root / "output" / "outline.json", outline)
    return outline


def export_cut(job_id: str, cut_id: str) -> dict:
    """Write one cut of a finished lesson as its own mp4 (+ captions); cached after the first call."""
    import subprocess
    root = _lesson_root(job_id)
    outline = _read_json(root / "output" / "outline.json")
    report = _read_json(root / "output" / "final_checks.json")
    if "/" in job_id or not outline or not report:
        raise KeyError(job_id)
    cut = next((c for c in outline["cuts"] if c["id"] == cut_id), None)
    if cut is None:
        raise KeyError(cut_id)
    source = root / "output" / str(report["video"])
    base = f"/lessons/{job_id}/output"
    if cut_id == "full":
        return {"cut": "full", "video_url": f"{base}/{source.name}", "captions_url": f"{base}/captions.vtt",
                "seconds": cut["seconds"]}
    target = root / "output" / f"{source.stem}__{cut_id}.mp4"
    captions = root / "output" / f"captions__{cut_id}.vtt"
    if not target.exists() or target.stat().st_mtime < source.stat().st_mtime:
        chain, labels = [], ""
        for i, (start, end) in enumerate(cut["ranges"]):
            chain.append(f"[0:v]trim=start={start}:end={end},setpts=PTS-STARTPTS[v{i}];"
                         f"[0:a]atrim=start={start}:end={end},asetpts=PTS-STARTPTS[a{i}]")
            labels += f"[v{i}][a{i}]"
        graph = ";".join(chain) + f";{labels}concat=n={len(cut['ranges'])}:v=1:a=1[v][a]"
        tmp = target.with_suffix(".part.mp4")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(source), "-filter_complex", graph, "-map", "[v]",
                        "-map", "[a]", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-c:a", "aac",
                        "-movflags", "+faststart", str(tmp)], check=True)
        os.replace(tmp, target)
        # Captions for the cut: the same sentences, moved onto the cut's clock.
        from ..longform.audio import stamp
        timeline = {t["id"]: t for t in json.loads((root / "timeline.json").read_text(encoding="utf-8"))}
        lines, clock = ["WEBVTT", ""], 0.0
        for beat_id in cut["beats"]:
            entry = timeline[beat_id]
            for sentence in entry.get("sentences", []):
                a = clock + sentence["start"]
                lines += [f"{stamp(a)} --> {stamp(a + sentence['duration'])}", sentence["text"], ""]
            clock += entry["duration"]
        captions.write_text("\n".join(lines), encoding="utf-8")
    return {"cut": cut_id, "video_url": f"{base}/{target.name}", "captions_url": f"{base}/{captions.name}",
            "seconds": cut["seconds"]}


# Added to a scene's description when it asks for more than can be drawn, and on the second
# try of any scene that failed. The description stays the writer's; this is the limit.
SCENE_LIMITS = (" Draw it simply: at most 40 separate objects in all. Where the description gives a count too "
                "large to draw one by one, draw a small version with the same structure (for example 6 rows of 6 "
                "in place of 42 rows of 42) and write the real count beside it as one short label. One clear "
                "motion, slow enough to follow.")
SCENE_MAX_OBJECTS = 60
# Added to every scene. "the labels 400 and 200 N/m2 sit under them" (a 20 N block named first, a 40 N block second)
# came back with 200 under the 20 N block and 400 under the 40 N one: the wrong physics, filmed (2026-10-18). No check
# can see which number belongs to which object, so the writer of the scene is told the reading.
SCENE_PAIRS = (" Every number or label goes beside the object it belongs to: when values are listed for several objects "
               "(\"under them\", \"respectively\"), the first value is the first object named, the second the second.")
# Added to a description written as stages ("first …, then …, then …"). The lesson's renderer moves the picture
# to stage k when the k-th step's words are spoken (runtime.GuidedChapter._start_motion): that only shows the
# right thing if the animation gives every stage the same share of its run time, in the order written.
SCENE_STAGES = (" Animate the stages strictly one after another, in the order written, each taking an EQUAL share of "
                "the run time (three stages: thirds), and nothing of a later stage may show before its turn.")
_STAGED = re.compile(r"\bfirst\b.{3,200}\bthen\b|\bthen\b.{3,200}\bthen\b", re.I | re.S)
# A large number followed by one of these is a measurement, not a crowd of objects.
_SCENE_UNITS = re.compile(r"\s*(?:%|°|percent|degrees?|radians?|minutes?|seconds?|hours?|days?|years?|ms|hz|hertz|"
                          r"metres?|meters?|m|cm|mm|km|kg|g|grams?|litres?|ml|volts?|v|watts?|w|ohms?|amps?|"
                          r"kelvin|k|celsius|newtons?|n|joules?|j|pascals?|pa|rupees?|rs|nm|mol|moles?)\b", re.I)


def scene_brief(description: str) -> str:
    """The description as the scene writer gets it: unchanged, or with the limits when it names a crowd.

    A lesson on square numbers asked for "1764 ladoos gliding one at a time into a
    square box" eight ways (2026-10-08). Nothing can draw that legibly in a 6 by 4 box,
    and the one such scene that reached verification failed it twice.
    """
    brief = description + (SCENE_STAGES if _STAGED.search(description) else "") + SCENE_PAIRS
    for match in re.finditer(critic._NUMBER_RE, description, flags=re.I):
        value = critic._number(match.group(1))
        if value is not None and value > SCENE_MAX_OBJECTS and not _SCENE_UNITS.match(description, match.end()):
            return brief + SCENE_LIMITS
    return brief


def look_at_scenes(wanted: dict, made: dict, briefs: dict, log=print, check=None) -> dict:
    """Each made scene's stills looked at against its description (``harness.scene_look``), when switched on.

    ``HARNESS_SCENE_LOOK``: ``0`` (default) does nothing; ``1`` looks and reports; ``redraw`` also has a scene with
    confirmed faults drawn once more, kept only when nothing it showed is lost. Off by default because the redraw
    kept none of nine tries on three lessons (2026-10-19): the look finds real faults, the cheap scene writer did not
    cure them. Advisory: nothing here can cost a lesson its scene.
    """
    mode = knobs.get("HARNESS_SCENE_LOOK", "0")
    if mode not in ("1", "redraw"):
        return {}
    from . import scene_look  # noqa: PLC0415
    if check is None:
        from ..engine import sim_gen
        from ..engine.dependencies import env_api_keys
        keys = env_api_keys()

        def check(description, path, stages):
            revise = (lambda code, brief: sim_gen.revise_simulation(briefs[description], code, brief, keys=keys)) \
                if mode == "redraw" else None
            return scene_look.check(briefs[description], path, stages, revise=revise, log=log)
    out = {}

    def one(description):
        beats = wanted[description]
        stages = max(1, len([s for s in beats[0].get("steps") or [] if str(s.get("show", "")).strip()]))
        try:
            return description, check(description, made[description], stages)
        except Exception as exc:  # noqa: BLE001
            return description, {"looked": False, "why": f"{type(exc).__name__}: {str(exc)[:100]}"}

    with ThreadPoolExecutor(max_workers=int(knobs.get("HARNESS_SCENE_WORKERS", "3"))) as pool:
        for description, result in pool.map(knobs.wrap(one), [d for d in wanted if made.get(d)]):
            out[description[:80]] = result
            if result.get("faults"):
                missing = [t["thing"] for t in result.get("things") or [] if t.get("seen") != "shown"]
                log(f"[scene look] «{description[:60]}…» does not show: {'; '.join(missing)[:160]}"
                    + (f" (redrawn: {'kept' if result.get('kept') else 'not kept, ' + result.get('why', '')})"
                       if result.get("redrawn") else ""))
    if out:
        log(f"[scene look] {len(out)} scene(s) looked at; {sum(1 for r in out.values() if r.get('faults'))} miss "
            f"something they were asked to show; {sum(1 for r in out.values() if r.get('kept'))} drawn again and kept")
    return out


def resolve_scenes(lesson_dict: dict, log=print, generate=None, why=None) -> dict:
    """Have a strong model write, animate and VERIFY the picture behind every ``scene`` figure.

    One call per distinct description (cached by the engine for ever), a few in
    parallel. A scene that fails gets ONE more try with the limits spelled out; one
    that still cannot be verified is dropped from its beats — no picture is better than
    a placeholder pretending to be one — and the count and the reasons are reported.
    """
    wanted: dict[str, list[dict]] = {}
    for chapter in lesson_dict["chapters"]:
        for beat in chapter["beats"]:
            figure = beat.get("figure") or {}
            if figure.get("kind") == "scene" and not figure.get("module"):
                wanted.setdefault(figure.get("describe", ""), []).append(beat)
    if not wanted:
        return {"asked": 0, "made": 0, "failed": []}
    if generate is None:
        from ..engine import sim_gen
        from ..engine.dependencies import env_api_keys
        keys = env_api_keys()
        generate = lambda description: sim_gen.generate_simulation(description, keys=keys)  # noqa: E731
        why = sim_gen.why_failed
    why = why or (lambda description: "")

    def make(pair):
        description, brief = pair
        try:
            return description, generate(brief)
        except Exception as exc:  # noqa: BLE001
            log(f"[visuals] {type(exc).__name__}: {str(exc)[:120]}")
            return description, None

    workers = int(knobs.get("HARNESS_SCENE_WORKERS", "3"))
    briefs = {description: scene_brief(description) for description in wanted}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        made = dict(pool.map(knobs.wrap(make), briefs.items()))
    reasons = {d: why(briefs[d]) for d in wanted if not made.get(d)}
    again = {d: (briefs[d] if briefs[d].endswith(SCENE_LIMITS) else briefs[d] + SCENE_LIMITS) for d in reasons}
    if again:
        log(f"[visuals] {len(again)} of {len(wanted)} scene(s) failed (e.g. {next(iter(reasons.values())) or 'no reason given'}); "
            "trying each once more, simpler")
        with ThreadPoolExecutor(max_workers=workers) as pool:
            second = dict(pool.map(knobs.wrap(make), again.items()))
        for description, path in second.items():
            if path:
                made[description] = path
                reasons.pop(description, None)
            else:
                reasons[description] = why(again[description]) or reasons.get(description, "")
    looked = look_at_scenes(wanted, made, briefs, log)
    failed = []
    for description, beats in wanted.items():
        path = made.get(description)
        if not path:
            failed.append(description)
        for beat in beats:
            if path:
                beat["figure"]["module"] = str(path)
            else:
                beat.pop("figure", None)
                writer.open_with_something(beat)       # its picture is gone: do not leave the screen empty
    log(f"[visuals] {len(wanted) - len(failed)} of {len(wanted)} animated scene(s) written and verified"
        + (f"; dropped: {failed[0][:70]}… ({reasons.get(failed[0]) or 'no reason given'})" if failed else ""))
    return {"asked": len(wanted), "made": len(wanted) - len(failed), "failed": failed, "retried": len(again),
            "looked": looked,
            "simplified": sum(1 for d in wanted if briefs[d].endswith(SCENE_LIMITS)),
              "reasons": {d[:80]: r for d, r in reasons.items() if r}}


def results_from_disk(root: Path) -> dict | None:
    """Everything a client needs to show a finished lesson, read from its directory alone.

    Used at the end of a run AND to recover a job after a restart or a late failure, so
    the two can never disagree. Returns None when there is no finished video.
    """
    lesson_dict = _read_json(root / "lesson.json")
    report = _read_json(root / "output" / "final_checks.json")
    timeline = _read_json(root / "timeline.json")
    if not (lesson_dict and report and timeline):
        return None
    video = root / "output" / str(report.get("video", ""))
    if not video.is_file():
        return None
    job_id, base = root.name, f"/lessons/{root.name}"
    brief = lesson_dict.get("brief") or {}
    interactions = _read_json(root / "output" / "interactions.json")
    if interactions is None:
        try:
            write_interactions(root, job_id, brief, lesson_dict, report.get("duration_seconds") or 0.0)
            interactions = _read_json(root / "output" / "interactions.json")
        except Exception:  # noqa: BLE001 - a sidecar must never cost the lesson
            interactions = None
    starts = {}
    for entry in timeline:
        starts.setdefault(entry["chapter"], entry["start"])
    try:
        outline = write_outline(root, lesson_dict)
    except Exception:  # noqa: BLE001 - a sidecar must never cost the lesson
        outline = None
    verification = lesson_dict.get("verification") or None
    vision = _read_json(root / "output" / "vision_review.json")
    audio = _read_json(root / "audio_report.json") or {}
    out = {
        "title": lesson_dict.get("title", ""), "generated_by": lesson_dict.get("generated_by"),
        "continuity": lesson_dict.get("continuity"),
        "video_url": f"{base}/output/{video.name}", "captions_url": f"{base}/output/captions.vtt",
        "review_url": f"{base}/review.html" if (root / "review.html").exists() else None,
        "lesson_url": f"{base}/lesson.json",
        "interactions_url": f"{base}/output/interactions.json" if interactions else None,
        "interactions": len((interactions or {}).get("interactions", [])),
        "outline_url": f"{base}/output/outline.json" if outline else None,
        "cuts": [{k: c[k] for k in ("id", "label", "hint", "seconds", "ranges")} for c in (outline or {}).get("cuts", [])],
        "checks": {k: report.get(k) for k in ("status", "duration_seconds", "chapters", "beats", "captions",
                                              "animation_anchors", "anchor_timing", "sentence_timing",
                                              "bounds_violations", "review_limits")}
                  | {"layout_counted": (report.get("layout_findings") or {}).get("counted"),
                     "failed": [c["check"] for c in report.get("checks", []) if not c.get("passed")]},
        "chapters": [{"id": c["id"], "title": c["title"], "start": starts.get(c["id"], 0.0),
                      "depths": sorted({writer.beat_depth(b, c.get("role", "")) for b in c["beats"]})}
                     for c in lesson_dict["chapters"]],
        "alignment": audio.get("alignment"),
    }
    if lesson_dict.get("script"):
        out["script"] = lesson_dict["script"]
    # What the app shows under the video: the task to do by hand (with how many answered it) and what
    # the lesson stands on. Both are read from the lesson, so an older lesson simply has neither.
    task = tryit.task_of(lesson_dict)
    if task:
        out["try_it"], out["try_it_answers"] = task, tryit.count(root)
    card = tryit.card_view(lesson_dict)
    if card:
        out["card"] = card
    if verification:
        out["verification"] = {k: verification.get(k) for k in ("status", "scores", "claims_checked",
                                                                "critical_unresolved", "edits_applied", "summary",
                                                                "readability", "rounds", "beats_rewritten",
                                                                "teaching", "rubric", "questions")} | {
            "findings": verification.get("findings") or [], "claims_failed": verification.get("claims_failed") or []}
    if vision:
        out["vision_review"] = {k: vision.get(k) for k in ("frames", "findings", "by_kind", "frames_showing_intended",
                                                           "frames_unreadable")}
    qa = _read_json(root / "output" / "qa_report.json")
    if qa:
        out["qa"] = {"status": qa.get("status"), "counts": qa.get("counts"), "url": f"{base}/output/qa_report.json",
                     "beats_to_repair": list((qa.get("repair_plan") or {}))[:40]}
    return out


def _created_from_id(job_id: str, root: Path) -> float:
    try:
        return time.mktime(time.strptime(job_id[:15], "%Y%m%d-%H%M%S"))
    except ValueError:
        return root.stat().st_mtime


def _alive(pid: int) -> bool:
    """Whether ``pid`` is a running lessonforge process on this machine."""
    try:
        return b"lessonforge" in Path(f"/proc/{pid}/cmdline").read_bytes()
    except OSError:
        if Path("/proc").is_dir():
            return False                 # Linux, and the process is gone
    try:                                 # no /proc: the process exists, which is all that can be known
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _made_elsewhere(job: dict, root: Path) -> bool:
    """Whether ANOTHER live process is making this lesson (``lessonforge script`` / ``harness`` in a shell).

    Until 2026-10-09 such a lesson was listed as "failed: the server restarted … Start it again"
    for as long as it was being made, and "Try again" was pressed on four of them: four duplicate
    lessons at full price. A run records the process that owns it (``pid``). A record without one
    is an older run and reads as interrupted, as it always did: guessing from how recently its
    folder was written would call a lesson killed a minute ago "running".
    """
    pid = job.get("pid")
    return isinstance(pid, int) and pid != os.getpid() and _alive(pid)


def _load_job(job_id: str) -> dict | None:
    """A job that is not in memory: from ``job.json``, or rebuilt from the lesson directory."""
    root = _lesson_root(job_id)
    if not root.is_dir() or "/" in job_id or job_id.startswith("."):
        return None
    job = _read_json(root / "job.json")
    results = results_from_disk(root)
    if job is None:
        lesson_dict = _read_json(root / "lesson.json") or _read_json(root / "lesson.draft.json")
        if lesson_dict is None:
            return None
        audio = _read_json(root / "audio_report.json") or {}
        job = {"job_id": job_id, "stages": STAGES, "progress": [], "title": lesson_dict.get("title", ""),
               "brief": lesson_dict.get("brief") or {}, "created": _created_from_id(job_id, root),
               "voice": audio.get("backend"), "error": None, "recovered": True}
    if job.get("status") in ("queued", "running", None) or job.get("status") == "failed" and results:
        # Not in memory, so no worker owns it. A finished video on disk IS the result,
        # whatever the record says; otherwise the run was cut short.
        if results:
            job.update(results)
            job.update({"status": "done", "stage": "done", "recovered": True,
                        "note": "Recovered from the lesson files on the server." +
                                (f" A later step had failed: {job['error']}" if job.get("error") else "")})
            job["error"] = None
        elif job.get("status") in ("queued", "running") and _made_elsewhere(job, root):
            # Still being made, just not by this process: say so, and offer no "Try again" on it.
            job.update({"status": "running", "stage": job.get("stage") or "queued", "elsewhere": True, "note": ELSEWHERE})
        else:
            job.update({"status": "failed", "error": job.get("error") or INTERRUPTED,
                        "stage": job.get("stage") or "script"})
    if job.get("status") == "failed" and job.get("error") != STOPPED:
        job["can_finish"] = (root / "lesson.json").is_file()
    if results and job.get("status") == "done":
        job.update(results)          # computed from the files, so older lessons gain what was added since
    for key in ("video_url", "review_url", "captions_url", "checks", "continuity", "verification", "vision_review",
                "alignment", "voice", "voice_note", "error"):
        job.setdefault(key, None)
    job.setdefault("stages", STAGES)
    job.setdefault("progress", [])
    return job


def get_job(job_id: str) -> dict:
    job = _JOBS.get(job_id)
    # A lesson another process is making (``lessonforge script`` / ``harness`` from the command line) looks
    # interrupted from here while it runs. That reading is not kept: it is taken again from the files each
    # time, so the lesson shows as done once that process has finished it (it used to stay "failed" in the
    # app until the server was restarted).
    if job is None or job.get("error") == INTERRUPTED or job.get("elsewhere"):
        fresh = _load_job(job_id)
        if fresh is None and job is None:
            raise KeyError(job_id)
        if fresh is not None:
            job = _remember(_JOBS, job_id, fresh)
    return _public(job)


def list_jobs(limit: int = 500) -> list[dict]:
    """Recent jobs, newest first — the ones running now and every lesson directory on disk.

    Every lesson, not the newest 30: the cap of 30 hid 20 of 50 finished lessons from the app (the owner,
    2026-10-15: "show all videos gen")."""
    ids = set(_JOBS)
    lessons = paths.home() / "lessons"
    if lessons.is_dir():
        ids |= {p.name for p in lessons.iterdir() if p.is_dir() and not p.name.startswith(".")}
    rows = []
    for job_id in sorted(ids, reverse=True)[:limit * 2]:
        if (_JOBS.get(job_id) or {}).get("_remove"):
            continue                     # asked to be removed: it leaves the list now, its worker stops at the next stage
        try:
            job = get_job(job_id)
        except KeyError:
            continue
        rows.append({"job_id": job["job_id"], "status": job.get("status"), "stage": job.get("stage"),
                     "title": job.get("title"), "video_url": job.get("video_url"), "created": job.get("created"),
                     "duration_seconds": (job.get("checks") or {}).get("duration_seconds"),
                     "language": (job.get("brief") or {}).get("language"),
                     "mode": (job.get("brief") or {}).get("mode") or "intent", "error": job.get("error"),
                     # Being made by another process (a command-line run): a server restart does not touch it.
                     "elsewhere": bool(job.get("elsewhere"))})
    rows.sort(key=lambda r: r.get("created") or 0, reverse=True)
    return rows[:limit]


def start_job(brief: dict, quality: str = "m", voice: str | None = None, llm=None, judge=None,
              settings: dict | None = None) -> dict:
    """``settings``: this lesson's own values for the pipeline's switches (``knobs.CONTROLS``), already validated
    (``knobs.validate``); kept on the job and in force for every stage of it."""
    again = brief.get(VOICE_FOR)             # narrate a finished lesson again (narrate_again): set by code only
    if scripted.is_script(brief):
        fresh, chosen = brief.get("fresh"), brief.get("voice_choice")
        kept = {k: brief[k] for k in ("stop_after", lesson_edit.EDIT_OF, lesson_edit.EDITS) if k in brief}
        brief = scripted.prepare(brief)      # ValueError when there is too little or too much to narrate
        brief.update(kept)                   # read the script first, or an edit of a lesson: not part of the script
        if again:
            brief[VOICE_FOR] = again
        if chosen:
            brief["voice_choice"] = chosen
        if fresh:
            brief["fresh"] = True            # a new take on the same script: what was kept for it is not used
    if contract.is_scope(brief):           # lesson-board's scope/1: objectives, ideas, what to leave out
        brief = contract.brief_from_scope(brief)
    if not brief.get("topic"):
        raise ValueError("the brief needs at least a topic")
    brief = {k: v for k, v in brief.items() if k != "needs_focus"}
    if not again and not scripted.is_script(brief) and not forge.is_forge(brief) and not pack.is_pack(brief):
        brief = explanations.attach(brief)   # the checked explanation of this concept, kept in the brief (store key)
    if "voice_choice" in brief:              # only a voice this server has; anything else means "the usual one"
        brief["voice_choice"] = voice_choice(brief["voice_choice"])
        if not brief["voice_choice"]:
            del brief["voice_choice"]
    needed = None
    if llm is None and spend.api_key():
        # Refuse here what the account cannot pay for (spend.BudgetExceeded): a lesson that runs out of credit
        # half-way has paid for its script and its animations and is then narrated by the fallback voice.
        # The same for the spending cap: a lesson the cap could not cover was planned, drawn, and left silent.
        words = len(str(brief.get("script") or "").split()) or (forge.spoken_words(brief) if forge.is_forge(brief) else 0)
        minutes = words / writer.WORDS_PER_MINUTE if words else float(brief.get("duration_minutes") or 6)
        needed, what = ((spend.narration_estimate(minutes), f"the narration of about {max(1, round(minutes))} minute(s)") if again
                        else (spend.lesson_estimate(minutes), f"a lesson of about {max(1, round(minutes))} minute(s)"))
        if not again and diagrams.available():
            # A drawing from the diagram service is paid for from the same key (found out the expensive way on
            # 2026-10-09: about twenty of them, 4.7 USD, none of it in the ledger). Room for one is asked for.
            needed = round(needed + diagrams.cost_estimate(), 2)
        spend.ensure_credit(needed, what)
        spend.ensure_room(needed, what)
    job_id = time.strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:6]
    job = _remember(_JOBS, job_id, {
        "job_id": job_id, "status": "queued", "stage": "queued", "stages": STAGES, "progress": [],
        "title": brief.get("topic", ""), "brief": dict(brief), "created": time.time(), "quality": quality,
        "video_url": None, "review_url": None, "captions_url": None, "checks": None, "continuity": None,
        "verification": None, "vision_review": None, "alignment": None,
        "voice": None, "error": None, "settings": dict(settings or {}),
        # What this lesson has spent on metered calls so far, and the most it may (spend.lesson_scope).
        "cost_usd": 0.0, "cost_cap_usd": spend.lesson_cap(needed),
        "_quality": quality, "_voice": voice, "_llm": llm, "_judge": judge,
        # Which process is making it (so another process can tell "running elsewhere" from "interrupted"),
        # and that a worker of THIS process will run it (so it can be asked to stop).
        "pid": os.getpid(), "_owned": True,
    })
    paths.sub("lessons", job_id)
    _save_job(job)
    _EXECUTOR.submit(_run, job)
    return _public(job)


def _made_with(custom, models: list[str], *modules) -> list:
    """What a stage's result depends on besides its input: who was asked, and the code and prompts that asked.

    The code is taken whole (the bytes of the modules that make the stage): a changed prompt, rule or check
    is then another key by itself, and nobody has to remember to raise a version when they edit one.
    """
    who = f"{getattr(custom, '__module__', '')}.{getattr(custom, '__qualname__', 'custom')}" if custom else list(models)
    digest = hashlib.sha256()
    for module in modules:
        digest.update(_code_of(module).encode())
    return [who, digest.hexdigest()[:20]]


_CODE: dict[str, str] = {}


def _code_of(module) -> str:
    """The digest of a module's source AS THIS PROCESS LOADED IT, taken once.

    Read from disk at every use it described the file as it is NOW: a module edited while the server was
    running (two sessions work on this tree) made the old code in memory store its result under the new
    code's key, and after a restart the new code would have taken that result for its own.
    """
    name = module.__name__
    if name not in _CODE:
        try:
            _CODE[name] = hashlib.sha256(Path(module.__file__).read_bytes()).hexdigest()
        except OSError:
            _CODE[name] = repr(module)
    return _CODE[name]


for _module in (scripted, writer, diagrams, teaching_card, skill, voice, critic):
    _code_of(_module)          # now, at load: see _code_of


#: Brief key of a lesson made from a finished one's script and pictures, with only the narration made again.
VOICE_FOR = "voice_for"
def render_jobs() -> int:
    """How many chapters are filmed at once (``LESSONFORGE_RENDER_JOBS``, default 8).

    Each chapter is its own Manim process with LaTeX and its frames in memory. On Render's 2 GB plan the first
    lesson (seven chapters, 2026-11-02) was killed for memory as all seven started together, after its script, pictures
    and voice had been paid for; ``render.yaml`` sets 2 there.
    """
    return knobs.render_jobs()


def narrated(voice: str | None) -> bool:
    """Is this a real narration? Silence and the basic free voice (gTTS) are what a lesson is left with when
    its voices could not be used; every other backend is a narrator, including one added later."""
    return bool(voice) and voice != "silent" and not str(voice).startswith("gtts")


def narrate_again(job_id: str, quality: str | None = None, voice: str | None = None, llm=None,
                  choice: str | None = None) -> dict:
    """A NEW lesson from a finished one's script, pictures and review, with the narration made again.

    For a lesson that came out silent or in the basic voice because the voice could not be paid for when it
    was made (2026-10-09: the cap was reached as an 8.5-minute lesson reached its speech). Nothing is planned,
    drawn or reviewed again, so it costs the narration only; the lesson it is made from is left as it is.
    ``KeyError``: no such finished lesson. ``ValueError``: it is still being made.
    """
    if not re.fullmatch(r"[\w.-]{1,80}", str(job_id)) or str(job_id).startswith("."):
        raise KeyError(job_id)
    source = get_job(job_id)
    if source is None or not (_lesson_root(job_id) / "lesson.json").is_file():
        raise KeyError(job_id)
    if source.get("status") in ("queued", "running"):
        raise ValueError("That lesson is still being made. Its voice can be added once it has finished.")
    brief = {**(source.get("brief") or {}), VOICE_FOR: str(job_id)}
    brief.setdefault("topic", source.get("title") or "lesson")
    if choice:
        brief["voice_choice"] = choice       # the voice asked for this time (the app's choice), not the first run's
    return start_job(brief, quality or source.get("quality") or "m", voice=voice, llm=llm,
                     settings=source.get("settings") or None)


def _kept_lesson(job_id: str, root: Path, job: dict, log) -> dict:
    """The finished lesson a voice job stands on: its script and pictures, and what was found about them."""
    source_root = _lesson_root(job_id)
    lesson_dict = _read_json(source_root / "lesson.json")
    if not lesson_dict:
        raise RuntimeError(f"lesson {job_id} has no script to narrate (was it removed?)")
    for name in ("teaching_card.json",):                   # what the app shows beside the video
        if (source_root / name).is_file():
            shutil.copy2(source_root / name, root / name)
    before = _read_json(source_root / "job.json") or {}
    for key in ("verification", "scenes"):
        if before.get(key) is not None:
            job[key] = before[key]
    log(f"[voice] the script, the pictures and the review are lesson {job_id}'s own; only the narration is made again")
    return lesson_dict


def layout_faults(report: dict) -> int:
    """What the layout repair tries to bring down: counted overlaps plus things outside the stage."""
    return int(report["layout_findings"]["counted"]) + int(report.get("bounds_violations") or 0)


def chapters_to_relay(report: dict) -> list[int]:
    """The chapters a finished render's checks say need laying out again.

    A chapter where something ended OUTSIDE the stage is repaired the same way as one with an overlap.
    Until 2026-10-09 that was only counted: a lesson failed "nothing outside the stage" with nothing tried,
    and the owner said of the checks "we are not able to improve by using those".
    """
    return sorted({f["chapter"] for f in report["layout_findings"]["detail"] if f["counted"]}
                  | {b["chapter"] for b in report.get("bounds_detail") or []})


def _move_out(job_id: str) -> None:
    """Take a lesson out of the history: its folder goes to ``<workspace>/removed/``. Nothing is deleted."""
    root = _lesson_root(job_id)
    with _LOCK:
        _JOBS.pop(job_id, None)
    if root.is_dir():
        target = paths.sub("removed") / job_id
        if target.exists():
            target = target.with_name(f"{job_id}-{uuid.uuid4().hex[:4]}")
        shutil.move(str(root), str(target))


def remove_job(job_id: str) -> dict:
    """Stop a run if it is waiting or being made, and take it out of the history.

    A run this process owns is stopped at its next stage boundary (a stage is not cut in the
    middle: a render or a narration in progress finishes first) and its folder is moved out
    when its worker lets go: ``{"removed": False, "stopping": True}``. Anything else is moved
    at once. ``KeyError``: no such lesson. ``ValueError``: another process is still making it.
    """
    if not re.fullmatch(r"[\w.-]{1,80}", str(job_id)) or str(job_id).startswith("."):
        raise KeyError(job_id)
    root, job = _lesson_root(job_id), _JOBS.get(job_id)
    if job is None and not root.is_dir():
        raise KeyError(job_id)
    if job is not None and job.get("_owned"):
        job["_cancel"] = job["_remove"] = True
        return {"removed": False, "stopping": True}
    on_disk = _read_json(root / "job.json") or {}
    if on_disk.get("status") in ("queued", "running") and _made_elsewhere(on_disk, root):
        raise ValueError("Another process on the server is still making this lesson. It can be removed once that has finished.")
    _move_out(job_id)
    # The viewer site (harness/publish.py, 2026-10-15): a lesson taken out of the history here is taken off the
    # site too. Never raises, and does nothing when R2 is not set up or LESSONFORGE_PUBLISH=0.
    from . import publish
    publish.after_removal(job_id)
    return {"removed": True, "stopping": False}


def script_for(job_id: str) -> dict:
    """A lesson's script as a person reads and edits it (harness/edit.py). ``KeyError``: no such lesson or no script."""
    if not re.fullmatch(r"[\w.-]{1,80}", str(job_id)) or str(job_id).startswith("."):
        raise KeyError(job_id)
    job = get_job(job_id)
    found = lesson_edit.source_file(_lesson_root(job_id)) if job is not None else None
    if found is None:
        raise KeyError(job_id)
    view = lesson_edit.editable(_read_json(found) or {}, job.get("verification"))
    view.update({"job_id": job_id, "status": job.get("status"), "script_only": bool(job.get("script_only")),
                 "edit_of": (job.get("brief") or {}).get(lesson_edit.EDIT_OF)})
    return view


def edit_lesson(job_id: str, edits=None, film: bool = True, quality: str | None = None, voice: str | None = None,
                llm=None, choice: str | None = None) -> dict:
    """A NEW lesson from a lesson's script with a person's edits (harness/edit.py); the source is left as it is.

    ``film`` False stops the new one after its script again (to read it once more before anything is paid for
    beyond the script). ``KeyError``: no such lesson. ``ValueError`` (``edit.EditError``): the edit cannot be made,
    or the lesson is still being made.
    """
    if not re.fullmatch(r"[\w.-]{1,80}", str(job_id)) or str(job_id).startswith("."):
        raise KeyError(job_id)
    source = get_job(job_id)
    found = lesson_edit.source_file(_lesson_root(job_id)) if source is not None else None
    if found is None:
        raise KeyError(job_id)
    if source.get("status") in ("queued", "running"):
        raise ValueError("That lesson is still being made. It can be edited once it has finished.")
    cleaned = lesson_edit.clean(_read_json(found) or {}, edits)       # refused here, before anything is started
    brief = {k: v for k, v in (source.get("brief") or {}).items() if k not in ("stop_after", "fresh", VOICE_FOR)}
    brief.update({lesson_edit.EDIT_OF: str(job_id), lesson_edit.EDITS: cleaned})
    brief.setdefault("topic", source.get("title") or "lesson")
    if not film:
        brief["stop_after"] = "verify"
    if choice:
        brief["voice_choice"] = choice       # the voice asked for this time, not the first run's
    return start_job(brief, quality or source.get("quality") or "m", voice=voice, llm=llm,
                     settings=source.get("settings") or None)


def _edited_lesson(job_id: str, root: Path, job: dict, brief: dict, llm, log) -> tuple[dict, dict]:
    """The script an edit job stands on: its source's, with the person's edits made (harness/edit.py)."""
    source_root = _lesson_root(job_id)
    found = lesson_edit.source_file(source_root)
    if found is None:
        raise RuntimeError(f"lesson {job_id} has no script to edit (was it removed?)")
    if found.name == "lesson.json" and not (source_root / "job.json").is_file():
        log("[edit] that lesson was made before edits were kept apart; its finished script is used")
    for name in ("teaching_card.json",):
        if (source_root / name).is_file():
            shutil.copy2(source_root / name, root / name)
    before = _read_json(source_root / "job.json") or {}
    for key in ("verification", "scenes"):
        if before.get(key) is not None:
            job[key] = before[key]
    lesson_dict, summary = lesson_edit.apply(_read_json(found), brief.get(lesson_edit.EDITS) or {}, brief,
                                             llm=job["_llm"] or llm, log=log)
    job["edit"] = {"of": job_id, **{k: v for k, v in summary.items() if v}}
    return lesson_dict, summary


def _review_edit(job: dict, lesson_dict: dict, edited: dict | None, llm, log, advisory) -> None:
    """Words a person wrote are kept and only reported on; an edit that changed no words is not reviewed again."""
    if not (edited or {}).get("words"):
        log("[critic] no words were changed: the review of the lesson this was edited from stands")
        return
    reviewer = job["_llm"] or critic.default_llm() or llm
    if reviewer is None:
        log("[critic] no reviewer is set up: the changed words are not reviewed")
        return
    verification = advisory("review", lambda: critic.verify(lesson_dict, reviewer, log=log, apply=False))
    if verification:
        job["verification"] = {k: verification.get(k) for k in ("status", "scores", "claims_checked", "critical_unresolved",
                                                                 "summary", "readability", "rounds")} | {
            "findings": verification["findings"], "claims_failed": verification["claims_failed"]}
        changed = set(edited["words"])
        mine = [f for f in verification["findings"] if str(f.get("beat")) in changed]
        log(f"[critic] the changed words were read: {len(mine)} thing(s) noted on them; your words were left as written")


def _run(job: dict) -> None:
    """One lesson, start to end, under its own settings (``job["settings"]``: see ``lessonforge.knobs``)."""
    with knobs.applied(job.get("settings") or {}), \
            spend.lesson_scope(job["job_id"], job.get("cost_cap_usd")) as tally:
        job["_tally"] = tally
        _run_job(job)


def _note_cost(job: dict) -> None:
    """Copy the lesson's running spend into its record (shown with the job; saved with every stage)."""
    tally = job.get("_tally")
    if tally is not None:
        job["cost_usd"] = round(tally.spent, 4)


def _run_job(job: dict) -> None:
    root = paths.sub("lessons", job["job_id"])
    video = None

    def log(message: str) -> None:
        job["progress"] = (job["progress"] + [str(message)])[-60:]

    def stage(name: str) -> None:
        if job.get("_cancel"):
            raise _Stopped()             # asked to stop: nothing of the next stage is started or paid for
        job["stage"], job["status"] = name, "running"
        log(f"— {name} —")
        _note_cost(job)
        _save_job(job)

    def advisory(label: str, fn):
        """Run a step whose failure must not cost the video."""
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001
            log(f"[{label}] skipped: {type(exc).__name__}: {str(exc)[:160]}")
            return None

    try:
        if job.get("_cancel"):
            raise _Stopped()             # removed while it was still waiting for a worker
        brief = job["brief"]
        from_script = scripted.is_script(brief)
        from_forge = forge.is_forge(brief)      # planned and built by Lesson Forge (harness/forge.py): its words are reviewed here
        again = brief.get(VOICE_FOR)          # a finished lesson narrated again: nothing is written, drawn or reviewed
        edit_of = brief.get(lesson_edit.EDIT_OF)   # a lesson's script as a person changed it (harness/edit.py)
        edited = None                         # what the person's edits changed, once made
        if not from_script:
            brief.setdefault("framework", frameworks.recommend(brief.get("level")))
        if (not from_script and not from_forge and not again and not edit_of and not pack.is_pack(brief)
                and not brief.get("draft_file") and story_first.applies(brief)):
            # A story lesson's words are written in one go and kept; the screen is designed for them (story_first.py).
            try:
                written = story_first.words(brief, job["_llm"] or writer.default_llm())
                _write_json(root / "story_words.json", written)
                brief = job["brief"] = story_first.script_brief(brief, written)
                from_script = True
                log(f"[story] the words were written in one go ({len(written['script'].split())} words); "
                    f"the screen is designed for them")
            except Exception as exc:  # noqa: BLE001 -- the writer still makes the lesson
                log(f"[story] writing the words in one go failed ({type(exc).__name__}: {str(exc)[:120]}); "
                    f"the writer writes them chapter by chapter")
        # Sources before words: with a card asked for, the topic's textbook chapter, lectures and
        # known mistakes are gathered and written down as one page on how THIS topic is taught
        # (harness/card.py). Advisory: no sources, no model or a failure here means the lesson
        # is written as before, and the log says so.
        card, gathered = None, {}
        draft = writer.load_draft(brief["draft_file"], log=log) if brief.get("draft_file") and not from_script else None
        # A topic the concept knowledge base knows gets its card from there whether or not a card was asked for:
        # it costs nothing, and it is what makes two lessons on one topic explain it the same way.
        if not again and not edit_of and not from_script and not from_forge and not pack.is_pack(brief) and not draft and (teaching_card.enabled(brief) or concepts.find(brief, log=log)):
            job["stages"] = ["research"] + [s for s in job["stages"] if s != "research"]
            stage("research")

            def research():
                made, pack = teaching_card.prepare(brief, llm=job["_llm"], log=log)
                gathered["pack"] = pack
                _write_json(root / "teaching_pack.json", pack)        # passages: local only, never served
                if made:
                    # The writer is told what the finished drawing HOLDS, read from the drawing itself, and not only
                    # what was asked for: it had written "faint squares" over a drawing that has none (card.add_holds).
                    teaching_card.add_holds(made.get("diagram"), log=log)
                    _write_json(root / "teaching_card.json", made)
                return made
            card = advisory("research", research)
            if not card:
                log("[research] no teaching card: the script is written from the brief alone")
        stage("script")
        llm = job["_llm"] or writer.default_llm()
        fresh = bool(brief.get("fresh"))
        if again:
            lesson_dict = _kept_lesson(again, root, job, log)
        elif edit_of:
            lesson_dict, edited = _edited_lesson(edit_of, root, job, brief, llm, log)
        elif from_script:
            # The words are the author's: a model designs the screen for them, nothing else. What it designed
            # for THIS script is kept (harness/store.py): making the lesson again, after a failure or because
            # "Try again" was pressed, does not plan the same screen a second time.
            # How lectures on this topic SHOW it, for the screen's designer only (library.reference_for_script:
            # kept by the script's own text, empty on any failure). Looked up here because it is part of what
            # the planned screen is made from, and so of its key.
            reference = advisory("references", lambda: library.reference_for_script(
                brief.get("script", ""), brief.get("language") or "hinglish", log=log)) if llm else None
            kept_as = store.key("script", store.content(brief), diagrams.available() and knobs.get("HARNESS_SCRIPT_PICTURES", "1"),
                                (reference or {}).get("notes") or "",
                                _made_with(job["_llm"], writer.writer_models(), scripted, writer, diagrams, typeset))
            lesson_dict = store.get("script", kept_as, fresh) if llm else None
            if lesson_dict:
                log("[store] the screen planned for this script on an earlier run is used again: nothing is paid for it")
            else:
                lesson_dict = (scripted.script_lesson(brief, llm, log=log, reference=reference) if llm
                               else scripted.plain_lesson(brief, log=log))
                # Kept only when it is the screen this script should have: every beat designed, and the
                # picture its plan asked the diagram service for actually there (a plan made while the
                # service was down must not be the one used again once it is up).
                made = lesson_dict.get("script") or {}
                if (llm and lesson_dict.get("generated_by") == scripted.GENERATED_BY and not made.get("undesigned")
                        and not made.get("picture_missed")):
                    store.put("script", kept_as, lesson_dict)
        elif from_forge:
            lesson_dict = forge.lesson_for(brief, log=log)
        elif pack.is_pack(brief) and not draft:
            # A unit of a teaching pack: the model writes points and gaps, code fills and checks them (harness/pack.py).
            # Kept like a written script, under everything it is made from, only when no fault is left.
            kept_as = store.key("pack", store.content(brief), _made_with(job["_llm"], writer.writer_models(), pack, writer))
            lesson_dict = store.get("pack", kept_as, fresh)
            if lesson_dict:
                log("[store] this unit was written on an earlier run and is used again: nothing is paid for it")
            else:
                lesson_dict = pack.lesson_for(brief, llm, log=log)
                if not lesson_dict["geometry_check"]["faults_left"]:
                    store.put("pack", kept_as, lesson_dict)
            if _shapes_unfilled(lesson_dict):  # recomputed: a stored lesson may carry an older verdict
                raise RuntimeError("the pack lesson still has a value code could not work out from its pictures: "
                                   + "; ".join(lesson_dict["geometry_check"]["faults_left"][:3]))
        elif draft:
            lesson_dict = draft
        elif llm:
            # Everything the written script depends on is in its key, or a stale one comes back: the skill's
            # TEXT (the .md files the writer is given, not only skill.py), whether the voice pass runs, and
            # the picture the topic is drawn with when there is no card. The picture is looked up HERE and
            # handed to the writer (False: looked, there is none), so a script written while the diagram
            # service was down is not used again once the picture exists.
            picture = (diagrams.for_brief(brief, log=log) or False) if (not card and diagrams.topic_pictures()) else False
            if picture:                       # ... and what that picture holds, before the key is made: the writer reads it
                advisory("picture", lambda: teaching_card.add_holds(picture, log=log))
            # How lecturers on the topic talk, read from their own captions (voice.examples_for): the writer takes their
            # manner. Part of what the script is made from, so part of its key.
            lecturers = advisory("lecturers", lambda: voice.examples_for(brief, gathered.get("pack"), log=log)) or []
            kept_as = store.key("lesson", store.content(brief), card, picture, skill.version(), voice.enabled(card),
                                *([[e["text"] for e in lecturers]] if lecturers else []),
                                _made_with(job["_llm"], writer.writer_models(), writer, teaching_card, skill, voice, diagrams, typeset))
            lesson_dict = store.get("lesson", kept_as, fresh)
            if lesson_dict:
                log("[store] the script written for this request on an earlier run is used again: nothing is paid for it")
            else:
                lesson_dict = writer.write_lesson(brief, llm, log=log, card=card, picture=picture, lecturers=lecturers)
                if lesson_dict.get("generated_by") == "model":
                    store.put("lesson", kept_as, lesson_dict)
        else:
            lesson_dict = writer.outline_lesson(brief)
        job["continuity"], job["generated_by"] = lesson_dict["continuity"], lesson_dict["generated_by"]
        job["title"] = lesson_dict["title"]
        for warning in lesson_dict["continuity"]["warnings"]:
            log(f"[continuity] {warning}")
        _write_json(root / "lesson.draft.json", lesson_dict)

        # Correctness before cost: the critic reads the text, checks every arithmetic
        # claim with code, and may replace words in existing beats. Speech is bought
        # only after this. A critical finding it cannot fix is reported, not hidden.
        stage("verify")
        if again:
            log("[critic] these words were reviewed when the lesson was first made: not paid for again")
        elif edit_of:
            _review_edit(job, lesson_dict, edited, llm, log, advisory)
        else:
            reviewed = lesson_dict["generated_by"] in ("model", scripted.GENERATED_BY, forge.GENERATED_BY)
            reviewer = (job["_llm"] or critic.default_llm() or llm) if reviewed else None
            # An author's own words are reported on, not rewritten, unless they asked for mistakes to be fixed.
            keep = scripted.keeps_words(brief)
            # A review belongs to the exact words and pictures it read (the script as it stands BEFORE the
            # review, which may rewrite beats): the same script again is not reviewed, or paid for, twice.
            # The flow look joins the key only when it is on, so turning it off finds the reviews kept without it.
            flow = ["flow", coherence.VERSION] if coherence.enabled() else []
            teach = ["rubric", rubric.VERSION] if rubric.enabled() else []
            kept_as = store.key("verify", lesson_dict, keep, skill.version(), *flow, *teach,   # checks.md is the skill's text
                                _made_with(job["_llm"], critic.critic_models(), critic, voice, writer, questions,
                                           *((coherence,) if flow else ()), *((rubric,) if teach else ())))
            kept = store.get("verify", kept_as, fresh) if reviewer else None
            if kept:
                lesson_dict, verification = kept["lesson"], kept["verification"]
                log("[store] this script was reviewed on an earlier run: its review is used again, nothing is paid for it")
            else:
                as_written = None if keep else copy.deepcopy(lesson_dict)
                verification = critic.verify(lesson_dict, reviewer, log=log, apply=not keep)
                if as_written is not None:
                    # A revision writes steps again and gives them no focus; on a prepared drawing that is the
                    # part appearing as the voice names it. Put back from the script as written (writer.point_again:
                    # the first lesson made on the owner's drawing lost it on four of six beats this way).
                    advisory("pointing", lambda: writer.point_again(lesson_dict, log=log, was=as_written))
                # The questions the lesson stops for are written again as questions (harness/questions.py): each by
                # its kind, with options from real mistakes and a reason per option, kept only where code then
                # finds no more wrong with it than before. Here, after the reviewer and before the review is kept,
                # so a repeated lesson does not pay for it twice. An author's own script keeps every word.
                if reviewer and lesson_dict["generated_by"] != "outline":
                    # A pasted script's questions are its author's, whether or not they let the reviewer fix mistakes:
                    # it gets better cards and never another question.
                    # Who listens is the reviewer's family at temperature 0: asked twice about one borderline question
                    # at 0.2, it answered once each way.
                    listener = job["_llm"] or writer.default_llm(models=critic.critic_models(), temperature=0.0) or reviewer
                    asked = advisory("questions", lambda: questions.improve(
                        lesson_dict, brief, llm or reviewer, card=card, keep_words=keep or scripted.is_script(brief), log=log,
                        listener=listener))
                    if asked:
                        verification["questions"] = {k: asked.get(k) for k in ("asked", "kept", "rewritten", "dropped", "faults_before",
                                                                               "faults_after", "told_before", "told_after", "unheard",
                                                                               "confirmed", "disputed")}
                    # A pause with nothing asked before it is taken out (the reviewer notes it; nothing acted on the
                    # note, and the video showed "YOUR TURN" over a statement). Never in an author's own script, whose
                    # pauses are placed by scripted._finish.
                    if not scripted.is_script(brief):
                        settled = advisory("pauses", lambda: questions.settle_pauses(lesson_dict, log=log)) or []
                        for finding in verification["findings"]:
                            if finding.get("beat") in settled and "thinking pause follows a statement" in str(finding.get("what")):
                                finding["resolved"] = True
                        if settled:
                            verification.setdefault("questions", {})["pauses_taken_out"] = settled
                if reviewer:
                    store.put("verify", kept_as, {"lesson": lesson_dict, "verification": verification})
            if keep and verification["findings"]:
                log(f"[critic] {len(verification['findings'])} thing(s) noted about your script; your words were left as written")
            job["verification"] = {k: verification.get(k) for k in ("status", "scores", "claims_checked", "critical_unresolved",
                                                                     "edits_applied", "summary", "readability", "rounds",
                                                                     "beats_rewritten", "teaching", "rubric", "questions")} | {
                "findings": verification["findings"], "claims_failed": verification["claims_failed"]}
        job["continuity"] = lesson_dict["continuity"]
        # The script as it stands after its review, before the screen passes below work on it: what an edit starts
        # from (harness/edit.py), so those passes run once on the edited lesson instead of twice.
        _write_json(root / "lesson.reviewed.json", lesson_dict)
        if brief.get("stop_after") == "verify":
            # The script read before anything is narrated or filmed (lessonforge forge --check): the reviewed lesson is
            # kept as lesson.json and the review is in the store, so making it afterwards pays for neither again.
            _write_json(root / "lesson.json", lesson_dict)
            job.update({"stage": "verify", "status": "done", "script_only": True, "awaiting_approval": True})
            log("stopped after the script review, as asked: nothing was narrated or rendered")
            return
        if not again and any((b.get("figure") or {}).get("kind") == "scene" for c in lesson_dict["chapters"] for b in c["beats"]):
            stage("visuals")
            job["scenes"] = resolve_scenes(lesson_dict, log=log)
            # Stop here rather than narrate and render a lesson with no picture in it: when
            # EVERY animation fails the cause is systematic (2026-10-08: a safety check
            # refused all of them), and the result is 8 minutes of text on a dark screen.
            if job["scenes"]["asked"] >= 2 and job["scenes"]["made"] == 0:
                reason = next(iter(job["scenes"].get("reasons", {}).values()), "") or "see the server log"
                raise RuntimeError(f"None of the {job['scenes']['asked']} animations for this lesson could be drawn "
                                   f"({reason}). Nothing was narrated or rendered, so nothing more was spent.")
        # A drawing in panels whose second panel no step asks for would stand as half a drawing for the whole lesson
        # (writer.settle_panels, which the writer's own passes call after a rewrite). Once more here, when the steps
        # are final (the questions pass may have taken a step away) and before anything is rendered.
        advisory("panels", lambda: writer.settle_panels(lesson_dict, log=log))
        # ... and a panel brought in during one chapter is still there when the next chapter opens.
        advisory("panels", lambda: scripted.whole_once_brought_in(lesson_dict, log=log))
        # A code-drawn figure agrees with the voice: it changes on the beat that speaks the new numbers, its "?" becomes
        # the side once the voice states it, and a scaled copy shows what it was scaled from (writer.figures_and_words).
        advisory("figures", lambda: writer.figures_and_words(lesson_dict, log=log))
        # An equation handed to the learner to balance gets a question made by code, its answer and every reason
        # worked out from the atom counts (longform/visual_actions.py).
        advisory("figures", lambda: visual_actions.reaction_questions(lesson_dict, log=log))
        # The storyboard gate: what code can tell is wrong with the words and screens before any audio is made, beat by
        # beat (harness/qa.py); each finding names the pass that owns its repair.
        if not again:
            # ... and a beat whose screen never shows what its voice says gets its steps written again now, while that
            # costs one small call and no audio, render or look at a frame (qa.mend_storyboard; kept only if better).
            # Kept in the stage store under the lesson it was given, so the same lesson again pays for it once.
            mend_as = store.key("mend", lesson_dict, _made_with(job["_llm"], writer.writer_models(), qa, repairs, writer))
            kept_mend = store.get("mend", mend_as, fresh)
            if kept_mend:
                lesson_dict, mended_board = kept_mend["lesson"], kept_mend["result"]
                log("[store] this storyboard was mended on an earlier run: its new screens are used again")
            else:
                mended_board = advisory("storyboard mend", lambda: qa.mend_storyboard(lesson_dict, llm, log=log))
                if mended_board is not None:
                    store.put("mend", mend_as, {"lesson": lesson_dict, "result": mended_board})
            if mended_board and mended_board.get("tried"):
                job["storyboard_mend"] = mended_board
        gate = advisory("storyboard gate", lambda: qa.storyboard_findings(lesson_dict))
        if gate is not None:
            job["storyboard_gate"] = len(gate)
            log(f"[qa] storyboard: {len(gate)} finding(s) before speech"
                + "".join(f"\n  beat {f['beat']}: {f['kind']}: {f['what']}" for f in gate[:12]))
        if not again and repaint.enabled() and repaint.candidates(lesson_dict):
            # A poster's scene repainted by the image model on this machine, its arrows and labels left the drawing's
            # own (harness/repaint.py; off unless HARNESS_REPAINT=1). A drawing it does not repaint stays as drawn.
            painted = advisory("repaint", lambda: repaint.restyle_lesson(lesson_dict, log=log))
            if painted and painted.get("asked"):
                job["repaint"] = painted
        if not again:
            # A drawing shown whole is taken apart into the sequence of its parts, so the renderer can DRAW it part by
            # part instead of fading it in (harness/sequence.py; the owner, 2026-10-12: "the visuals are static").
            advisory("sequence", lambda: sequence.for_lesson(lesson_dict, log=log))
        if not again and paperlook.enabled():
            # The look of paint on paper for a poster's scene, by arithmetic: no model, so nothing in it can go missing
            # (harness/paperlook.py; the owner's go-ahead of 2026-10-12). Made once per drawing and kept beside it.
            given = advisory("look", lambda: paperlook.apply(lesson_dict, log=log))
            if given and given.get("given"):
                job["drawing_look"] = given
        if not again:
            # How the lesson looks is decided once, here, when its pictures are final, and written into the lesson:
            # every render of it reads it back (longform/look.py), so a later repair or a new voice does not change
            # the frame it was checked in. After the review, so a review kept for these words is still found.
            # A lesson that is only being narrated again keeps the look it has (none: the frame as it was).
            lesson_dict["look"] = lesson_look.for_new(lesson_dict, environ=knobs.environ())
            log("[look] " + ("picture left and a column of steps, as before" if lesson_dict["look"]["frame"] == "columns" else
                             "the picture as large as the frame allows, one line of words at a time; "
                             + ("captions under the video" if lesson_dict["look"]["captions"] == "outside" else "a band kept for captions")
                             + ("; the light page (every picture is a prepared drawing)" if lesson_dict["look"]["page"] == "paper"
                                else "; the dark page")))
            if compose.enabled() and lesson_dict["look"]["frame"] == "stage":
                # The lesson is PREVIEWED as stills before its narration is bought and before it is filmed (seconds, no
                # voice): what can be chosen by trying is tried on it, and what the stills show is measured and looked at
                # (harness/compose.py). It cannot cost the lesson. One thing found is acted on: a beat spoken over a
                # drawing of something else is given a drawing of its own from the drawing service, or, when none can
                # be had and it never had a picture, is shown without one (compose.mend). Words are rewritten only
                # with HARNESS_COMPOSE_MEND=words, and never an author's own.
                stage("compose")
                composed = advisory("compose", lambda: compose.settle(lesson_dict, root, log=log, jobs=render_jobs(), keep_words=scripted.is_script(brief) or bool(edit_of)))
                if composed:
                    job["composition"] = {k: composed.get(k) for k in ("pictures", "stills", "faults", "measured", "seen", "looked_at",
                                                                       "seconds", "mended") if k in composed}
                    if (composed.get("mended") or {}).get("drawn"):                       # a drawing a beat was just given
                        advisory("sequence", lambda: sequence.for_lesson(lesson_dict, log=log))
                        if paperlook.enabled():
                            advisory("look", lambda: paperlook.apply(lesson_dict, log=log))
            if lesson_dict["look"].get("drawings") == "painted":
                # A drawing that is drawn part by part is drawn WITH the words: one look at it beside the script says at
                # which step a teacher would draw each thing in it, and the steps carry that (harness/sequence.with_words;
                # a reference lecture's board holds nothing before it is spoken of, ours held the whole proof from second
                # five). After the preview, so its looks judged the whole drawing and a beat's own new drawing is planned too.
                planned = advisory("sequence", lambda: sequence.with_words(lesson_dict, log=log))
                if planned and planned.get("planned"):
                    job["drawn_with_words"] = planned
                # ... and a hand ANNOTATES it while the voice speaks: every value the voice says is written where it belongs,
                # and what is spoken of is ringed, gone over, pointed at (harness/annotate.py; the owner: "the image is not
                # being annotated … an annotation harness on top of the SVG"). Ideas by a model, places and checks by code.
                marked = advisory("annotate", lambda: annotate.for_lesson(lesson_dict, log=log))
                if marked and marked.get("annotated"):
                    job["annotated"] = marked
        # The shared storyboard, checked before any narration is bought (longform/storyboard.py): stages 1 to 3 are
        # written as files, and what code can fix without changing what is taught (an anchor a rewrite left
        # unspoken, markup in the narration) is fixed in the beats that have it. Never for a lesson narrated again.
        gate = advisory("storyboard", lambda: lesson_storyboard.prepare(
            root, lesson_dict, fix=not again, keep_words=scripted.keeps_words(brief) or from_script or bool(edit_of), log=log))
        if gate:
            job["storyboard"] = {k: gate[k] for k in ("errors", "warnings", "repaired")}
        _write_json(root / "lesson.json", lesson_dict)
        lesson = Lesson.model_validate(lesson_dict)

        stage("speech")
        refused = []                          # (voice, why) for every voice that could not be used
        for candidate in ([job["_voice"]] if job["_voice"] else
                          voice_candidates(brief.get("language", "en-IN"), brief.get("voice_choice"))):
            try:
                audio_report = build_audio(lesson, root, candidate, BuildOptions(granularity="beat"), log=log)
                job["voice"] = candidate
                job["alignment"] = audio_report.get("alignment")
                break
            except Exception as exc:  # a voice tier being down must not cost the video
                refused.append((candidate.split("|")[0], f"{type(exc).__name__}: {str(exc)[:160]}"))
                log(f"[speech] {candidate} unavailable ({type(exc).__name__}: {str(exc)[:120]}) — trying the next voice")
        if job["voice"] is None:
            raise RuntimeError("no speech backend produced audio" + (
                " (" + "; ".join(f"{name}: {why}" for name, why in refused)[:400] + ")" if refused else ""))
        if not narrated(job["voice"]) and not job["_voice"]:
            # Why the lesson has no real narration, in words its maker can act on. The old line said "NO VOICE
            # is configured" on a server with two voices set up, one out of credit and one refused by the cap.
            paid = [(name, why) for name, why in refused if narrated(name)]
            over = any("budget" in why.lower() or "credit" in why.lower() or "402" in why for _, why in paid)
            job["voice_note"] = ("budget" if over else "unavailable") if paid else "none"
            reason = ("the spending cap or the voice account's credit ran out before the narration" if over else
                      "; ".join(f"{name}: {why}" for name, why in paid)[:300] if paid else
                      "no narration voice is set up on this server (a provider key, or KOKORO_MODEL)")
            if again:
                raise RuntimeError(f"The narration could not be made ({reason}). Nothing was rendered, and the lesson you "
                                   "have is unchanged.")
            log(f"[speech] this video is {'silent, with captions' if job['voice'] == 'silent' else 'in the basic voice'}: "
                f"{reason}. Its script and pictures are kept: the voice can be added to it afterwards.")

        # Every visual event placed on the measured narration before anything is filmed (longform/timeline_compiler.py).
        advisory("timeline", lambda: timeline_compiler.compile_lesson(root, lesson_dict, log=log))
        # ... and the beats it finds out of step are re-anchored on the words actually heard, before the render, kept
        # only where a beat's schedule is measurably better (longform/sync_repair.py). The voice is never touched.
        if knobs.get("HARNESS_SYNC_REPAIR", "1") == "1":
            def resync():
                timeline = _read_json(root / "timeline.json") or []
                mended = sync_repair.repair(lesson_dict, timeline, log=log)
                if mended["kept"]:
                    _write_json(root / "lesson.json", lesson_dict)
                    timeline_compiler.compile_lesson(root, lesson_dict, log=log)
                return mended
            mended = advisory("sync repair", resync)
            if mended and mended["kept"]:
                job["sync_repair"] = mended
                lesson = Lesson.model_validate(lesson_dict)

        quality = job["_quality"]
        stage("render")
        clips = lesson_build.render_chapters(root, lesson, quality=quality, jobs=render_jobs(), log=log, extra_env=knobs.render_env())
        stage("assemble")
        video = lesson_build.assemble(root, clips, lesson, log=log)
        stage("check")
        report = lesson_build.run_checks(root, video, lesson, quality=quality, log=log)

        # Feedback loop: a collision the probe can see gets ONE deterministic repair —
        # re-lay the flagged chapters smaller — and the result is kept only if it is
        # measurably better. The first render is never lost.
        faults, flagged = layout_faults, chapters_to_relay(report)
        if flagged:
            stage("repair")
            log(f"[repair] {report['layout_findings']['counted']} layout finding(s) and "
                f"{int(report.get('bounds_violations') or 0)} thing(s) outside the stage in chapter(s) {flagged}; re-laying compact")
            backups = {cid: shutil.copy2(clips[cid], str(clips[cid]) + ".keep") for cid in flagged}
            audits = {cid: (root / "output" / f"chapter_{cid:02}_audit.json").read_text() for cid in flagged}
            try:
                lesson_build.render_chapters(root, lesson, quality=quality, jobs=render_jobs(), only=flagged, log=log,
                                             extra_env={**knobs.render_env(), "LESSONFORGE_COMPACT": "1"})
                video = lesson_build.assemble(root, clips, lesson, log=log)
                retry = lesson_build.run_checks(root, video, lesson, quality=quality, log=log)
                if faults(retry) < faults(report):
                    log("[repair] accepted: fewer findings")
                    report = retry
                else:
                    log("[repair] rejected: not better — restoring the first render")
                    for cid, backup in backups.items():
                        shutil.move(backup, clips[cid])
                        (root / "output" / f"chapter_{cid:02}_audit.json").write_text(audits[cid])
                    video = lesson_build.assemble(root, clips, lesson, log=log)
                    report = lesson_build.run_checks(root, video, lesson, quality=quality, log=log)
            except Exception as _re_exc:
                log(f"[repair] compact re-render failed ({_re_exc}); restoring first verified render")
                for cid, backup in backups.items():
                    if Path(backup).exists():
                        shutil.move(backup, clips[cid])
                    if cid in audits:
                        (root / "output" / f"chapter_{cid:02}_audit.json").write_text(audits[cid])
                video = lesson_build.assemble(root, clips, lesson, log=log)
                report = lesson_build.run_checks(root, video, lesson, quality=quality, log=log)
            finally:
                for backup in backups.values():
                    Path(backup).unlink(missing_ok=True)

        # ── The video exists from here on. Everything below is advisory. ──
        judge = job.get("_judge") or (vision_review.default_judge() if knobs.get("HARNESS_VISION_REVIEW", "1") == "1" else None)
        looked = None
        if judge:
            stage("review")
            looked = advisory("vision", lambda: vision_review.review_video(root, video, llm_call=judge, log=log))
            # What the frame review finds wrong with the SCREEN is repaired, not only reported: the faulted
            # beats' steps are written again, their chapters rendered again, and the change kept only when
            # the same review then finds less (harness/repairs.py). Never for a lesson that is only being
            # narrated again: nothing of that one is to be planned again.
            if looked and repairs.enabled() and llm and not again and repairs.targets(looked):
                def repair():
                    return repairs.repair_screen(root, lesson_dict, video, clips, report, looked, llm, judge, quality, log=log)
                mended = advisory("screen repair", repair)
                if mended:
                    video, report, _, job["screen_repair"] = mended

        # Direction D2: Learner-in-the-loop repair: re-synthesizes only failing beats located
        # via cited seconds from probe quiz errors, and re-renders only those affected chapters.
        from . import learner_repair
        if learner_repair.enabled() and not again and job.get("quiz_errors"):
            def run_learner():
                timeline = _read_json(root / "timeline.json") or []
                return learner_repair.repair_lesson_from_learner(
                    root, lesson_dict, video, clips, timeline, report,
                    job["quiz_errors"], llm=llm, quality=quality, log=log
                )
            learned = advisory("learner repair", run_learner)
            if learned:
                video, report, job["learner_repair"] = learned
        # What this lesson shows about its explanation: noted against its knowledge-base entry, or, for a new
        # topic whose card-made lesson passed its checks, the card kept as the explanation from now on.
        if card and not again:
            advisory("concepts", lambda: concepts.record(card, brief, job["job_id"], report, looked, log=log))
        advisory("review page", lambda: write_review(root, lesson, video, log=log))
        advisory("interactions", lambda: write_interactions(root, job["job_id"], brief, lesson_dict,
                                                            report["duration_seconds"]))
        advisory("annotations", lambda: annotate.timed(root, log=log))     # every mark a hand made, with its start and end
        # The visual plan: every visual action per scene, typed, with its target and the heard words it waits for,
        # and code checks on it (output/visual_plan.json; longform/visual_actions.py).
        advisory("visual plan", lambda: visual_actions.write(root, _read_json(root / "lesson.json") or lesson_dict))
        # One quality report for the lesson as it now stands (a screen repair may have written steps again), and the
        # record of every stage file it was made from (longform/qa.py).
        def quality_report():
            final = _read_json(root / "lesson.json") or lesson_dict
            lesson_storyboard.prepare(root, final, fix=False, log=log)
            timeline_compiler.compile_lesson(root, final, log=log)
            made = lesson_qa.write_qa(root, verification=job.get("verification"), log=log)
            lesson_qa.write_bundle(root, video, log=log)
            return made
        advisory("qa", quality_report)
        # One quality report for the lesson, beat by beat, from every check above (output/beat_qa_report.json).
        qa_result = advisory("qa report", lambda: qa.report(root, job=job, dest="output/beat_qa_report.json"))
        if qa_result:
            log(qa.line(qa_result))
        results = results_from_disk(root)
        if results is None:
            raise RuntimeError("the build finished but its result files could not be read back")
        job.update(results)
        job.update({"stage": "done", "status": "done"})
        from . import publish as _publish
        job["held_back"] = _publish.held_back(job)
        if job["held_back"]:
            log("[gate] not published by itself: " + "; ".join(job["held_back"]))
        log("done")
    except _Stopped:
        job.update({"status": "failed", "error": STOPPED})
        log("stopped")
    except Exception as exc:
        job.update({"status": "failed", "error": f"{type(exc).__name__}: {exc}"})
        log(f"FAILED: {exc}")
        # Its script and pictures were finished and kept: it can be completed from them (narrate_again)
        # without paying for either again.
        job["can_finish"] = (root / "lesson.json").is_file() and not job["brief"].get(VOICE_FOR)
        if video is not None:   # built before the failure: still hand it over
            results = advisory("recover", lambda: results_from_disk(root))
            if results:
                job.update(results)
    finally:
        job["_owned"] = False
        _note_cost(job)
        _save_job(job)
        if job.get("_remove"):
            try:
                _move_out(job["job_id"])
            except OSError:
                pass
        elif job.get("status") == "done":
            # The viewer site (harness/publish.py, 2026-10-15): a finished lesson's files and record go to R2 (or
            # LESSONFORGE_CLOUD_DIR) when that is set up and LESSONFORGE_PUBLISH is not 0. After the record is saved
            # and advisory: a failed upload leaves the lesson as it is, and `lessonforge publish` sends it later.
            from . import publish
            if job.get("held_back"):
                log("[publish] held back for a person (lessonforge publish sends it): " + "; ".join(job["held_back"]))
            elif publish.wanted():
                advisory("publish", lambda: publish.after_lesson(job["job_id"], log=log))
                _save_job(job)
