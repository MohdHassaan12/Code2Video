"""FastAPI routes for the content harness (mounted by ``lessonforge.engine``).

    GET  /api/harness/mode                       {"mode": "studio"} (the viewer site answers "viewer")
    GET  /api/harness/frameworks                 the explanation frameworks
    POST /api/harness/sessions                   start an intake  {opening?}
    GET  /api/harness/sessions/{id}              current question + brief
    POST /api/harness/sessions/{id}/answer       {question_id, value} → next question
    POST /api/harness/sessions/{id}/generate     {quality?, voice?} → job
    POST /api/harness/generate                   {brief, quality?, voice?} → job (no session)
    POST /api/harness/script/preview             {script, language?} → what a pasted script will become (no model call)
    GET  /api/harness/jobs                       recent jobs, newest first (survive restarts)
    GET  /api/harness/jobs/{id}                  status, stage, progress, video_url, checks
    GET  /api/harness/jobs/{id}/script           the lesson's script to read and edit: parts, beats, words, screens, review notes
    POST /api/harness/jobs/{id}/edit             {edits: {beat: {narration?, note?, remove?}}, film?} → a NEW lesson with the edits
    POST /api/harness/jobs/{id}/remove           stop a run that is waiting or being made, and take it out of the history
    POST /api/harness/jobs/{id}/tryit            {prediction?, observation?, answer?} a learner's try-it-yourself answer
    GET  /api/harness/jobs/{id}/tryit            the task and what learners wrote (owner only)
    POST /api/harness/events                     {event, job_id?, value?} what the player saw
    GET  /api/harness/stats                      visitors, lessons, plays, reviews, spend (the Dashboard tab)
    POST /api/harness/clips                      {brief, parts, cues: [{at, do}], seconds, width, height} → one short
                                                 moving picture timed to the cues, for another app's video (clip.py)
    GET  /api/harness/clips/{id}.mp4             that clip

With an OpenRouter key the questions are written for the topic by a fast model
(``harness/interviewer.py``): each carries ``source: "model" | "default"``, text
questions may carry tappable ``options`` (suggested answers), and the session view
has a ``note`` the client shows before the question.

A brief with ``mode: "script"`` and the words in ``script`` (plus ``language``, ``audience`` and
``script_edit: "keep" | "fix"``) makes the video FROM THOSE WORDS: see ``harness/scripted.py``.

Finished lessons are served under ``/lessons/<job_id>/…`` (video, captions, review page).
"""
from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .. import knobs, spend
from . import analytics, clip, contract, feedback, frameworks, intake, planner, scripted, service, tryit

router = APIRouter(prefix="/api/harness", tags=["harness"])


class StartSession(BaseModel):
    opening: Optional[str] = None


class Answer(BaseModel):
    question_id: str
    value: Any = None


class Generate(BaseModel):
    quality: str = "m"
    voice: Optional[str] = None
    brief: Optional[dict] = None
    # This lesson's own values for the pipeline's switches, by control id (GET /controls lists them).
    settings: Optional[dict] = None


def _or_404(fn, *args):
    try:
        return fn(*args)
    except KeyError:
        raise HTTPException(status_code=404, detail="not found")


#: Brief keys that name something on the server's own disk. They are for the command line; a brief that
#: arrives over HTTP never carries them (the server is reachable through a public link).
SERVER_ONLY_KEYS = ("draft_file", service.VOICE_FOR, "edit_of", "edits")      # a voice job is started by its own route, never by a brief


def _start(brief: dict, body: "Generate") -> dict:
    brief = {k: v for k, v in brief.items() if k not in SERVER_ONLY_KEYS}
    try:
        settings = knobs.validate(body.settings)
    except knobs.BadSetting as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    try:
        return service.start_job(brief, quality=body.quality, voice=body.voice, **({"settings": settings} if settings else {}))
    except spend.BudgetExceeded as exc:     # the account (or the budget) cannot pay for it: nothing was started
        raise HTTPException(status_code=402, detail=str(exc))
    except ValueError as exc:               # a script too short or too long to narrate
        raise HTTPException(status_code=400, detail=str(exc))


def _started(job: dict, quality: str) -> dict:
    analytics.note("generate", job_id=job.get("job_id"), value=quality)
    return job


@router.get("/mode")
def mode():
    """Which kind of server this is. This one MAKES lessons; the viewer site (``lessonforge/viewer.py``) answers
    ``viewer`` and only shows the finished ones, and the app hides every way to make or change a lesson there."""
    return {"mode": "studio"}


@router.get("/controls")
def list_controls():
    """Every switch a lesson can carry (``lessonforge.knobs``), grouped, with the server's current value."""
    return knobs.catalogue()


@router.get("/frameworks")
def list_frameworks():
    return {"frameworks": frameworks.FRAMEWORKS, "levels": intake.LEVELS, "styles": intake.STYLES,
            "languages": intake.LANGUAGES, "durations": intake.DURATIONS}


@router.post("/sessions")
def start_session(body: StartSession):
    view = service.start_session(body.opening)
    analytics.note("intake_start", session_id=view.get("session_id"))
    return view


@router.get("/sessions/{session_id}")
def get_session(session_id: str):
    return _or_404(service.get_session, session_id)


@router.post("/sessions/{session_id}/answer")
def answer(session_id: str, body: Answer):
    return _or_404(service.answer_session, session_id, body.question_id, body.value)


@router.post("/sessions/{session_id}/generate")
def generate_from_session(session_id: str, body: Generate):
    brief = _or_404(service.session_brief, session_id)
    if not brief.get("topic"):
        raise HTTPException(status_code=400, detail="answer the topic question first")
    return _started(_start(brief, body), body.quality)


@router.post("/generate")
def generate(body: Generate):
    brief = body.brief or {}
    if not scripted.is_script(brief) and not brief.get("topic"):
        raise HTTPException(status_code=400, detail="brief.topic is required")
    return _started(_start(brief, body), body.quality)


class Script(BaseModel):
    script: str
    language: Optional[str] = None


@router.post("/script/preview")
def script_preview(body: Script):
    """A pasted script read back before anything is spent: length, parts, language, what will not be spoken."""
    try:
        view = scripted.preview(body.script, body.language)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    analytics.note("script_check", value=view["words"])
    return view


@router.get("/jobs")
def jobs(limit: int = 500):
    return {"jobs": service.list_jobs(max(1, min(limit, 2000)))}


@router.get("/jobs/{job_id}")
def job(job_id: str):
    return _or_404(service.get_job, job_id)


@router.post("/jobs/{job_id}/remove")
def remove(job_id: str):
    """Stop a run (at its next stage) and take it out of the history. Its files are moved aside, not deleted."""
    try:
        out = service.remove_job(job_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="not found")
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    analytics.note("job_removed", job_id=job_id, value="stopping" if out.get("stopping") else "removed")
    return out


class Voice(BaseModel):
    voice: Optional[str] = None           # one of GET /voices' ids; nothing means the server's usual voice


@router.get("/voices")
def list_voices(language: Optional[str] = None):
    """The voices a lesson can be narrated with here, each with what it costs: the owner's own first, the paid ones
    marked. ``?language=hinglish`` keeps the voices that can narrate a lesson in that language."""
    return service.voices(language)


@router.post("/jobs/{job_id}/voice")
def add_voice(job_id: str, body: Optional[Voice] = None):
    """Narrate a finished lesson again: a new lesson from its script and pictures, paying for the voice only.

    For a lesson that came out silent or in the basic voice. 402 when the cap or the account cannot pay for
    the narration (nothing is started), 409 while the lesson is still being made.
    """
    try:
        job = service.narrate_again(job_id, choice=service.voice_choice(body.voice) if body else None)
    except KeyError:
        raise HTTPException(status_code=404, detail="not found")
    except spend.BudgetExceeded as exc:
        raise HTTPException(status_code=402, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    analytics.note("voice_added", job_id=job.get("job_id"), value=job_id)
    return job


class Edit(BaseModel):
    # beat id → {"narration": new words, "note": what the screen should show instead, "remove": true}
    edits: dict[str, dict] = {}
    # False: stop the new lesson after its script again, to read it once more before it is narrated and filmed
    film: bool = True
    voice: Optional[str] = None


@router.get("/jobs/{job_id}/script")
def script_of(job_id: str):
    """A lesson's script as a person reads and edits it (harness/edit.py)."""
    return _or_404(service.script_for, job_id)


@router.post("/jobs/{job_id}/edit")
def edit_job(job_id: str, body: Edit):
    """A person's changes to a lesson's script, made into a NEW lesson (the one edited is left as it is).

    The human in the loop: a lesson started with ``stop_after: "verify"`` waits here with its script written and
    reviewed and nothing narrated; this approves it (with or without changes). It works on a finished video too.
    400 when an edit cannot be made, 402 when the cap cannot pay for it, 409 while the lesson is still being made.
    """
    from . import edit as lesson_edit
    try:
        job = service.edit_lesson(job_id, body.edits, film=body.film,
                                  choice=service.voice_choice(body.voice) if body.voice else None)
    except KeyError:
        raise HTTPException(status_code=404, detail="not found")
    except spend.BudgetExceeded as exc:
        raise HTTPException(status_code=402, detail=str(exc))
    except lesson_edit.EditError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    analytics.note("lesson_edited", job_id=job.get("job_id"), value=job_id)
    return job


@router.post("/jobs/{job_id}/cuts/{cut_id}")
def cut(job_id: str, cut_id: str):
    """One way of watching a finished lesson (full / standard / revision / summary) as its own file."""
    saved = _or_404(service.export_cut, job_id, cut_id)
    analytics.note("cut_export", job_id=job_id, value=cut_id)
    return saved


class Plan(BaseModel):
    subject: str
    audience: Optional[str] = None
    language: str = "en-IN"


@router.post("/plan")
def plan(body: Plan):
    """A chapter → an ordered series of single-idea lessons, each with a ready generation brief."""
    llm = planner.default_llm()
    if llm is None:
        raise HTTPException(status_code=503, detail="planning a chapter needs a model key on the server")
    try:
        result = planner.plan_chapter(body.subject, body.audience or "", llm, language=body.language)
    except ValueError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    result["briefs"] = planner.to_briefs(result)
    analytics.note("plan")
    return result


class Review(BaseModel):
    reviewer: Optional[str] = None
    answers: dict = {}
    auto: Optional[dict] = None


class TesterForm(BaseModel):
    kind: str = "tester"
    job_id: Optional[str] = None
    reviewer: Optional[str] = None
    contact: Optional[str] = None
    answers: dict = {}


@router.get("/feedback/form")
def feedback_form(kind: str = "student"):
    """A review sheet — ``student`` (watching one lesson) or ``tester`` (making lessons): tasks and questions."""
    return _or_404(feedback.form, kind)


@router.get("/feedback/summary")
def feedback_summary(kind: str = "student"):
    """What the reviews say, with the signals worth acting on (``kind=tester`` for the people making lessons)."""
    return feedback.summarize_testers() if kind == "tester" else feedback.summarize_all()


@router.post("/feedback")
def send_tester_feedback(body: TesterForm):
    """Store one tester's form (the people who make lessons)."""
    try:
        stored = feedback.store_tester(body.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    analytics.note("tester_feedback", job_id=body.job_id)
    return stored


@router.post("/jobs/{job_id}/feedback")
def send_feedback(job_id: str, body: Review):
    """Store one student's review of a lesson."""
    try:
        stored = feedback.store(job_id, body.model_dump())
    except KeyError:
        raise HTTPException(status_code=404, detail="not found")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    analytics.note("review_sent", job_id=job_id)
    return stored


@router.get("/jobs/{job_id}/feedback")
def read_feedback(job_id: str):
    """What the reviews of one lesson say."""
    return _or_404(feedback.summarize, job_id)


class TryIt(BaseModel):
    prediction: Optional[str] = None
    observation: Optional[str] = None
    answer: Optional[str] = None
    reviewer: Optional[str] = None
    done_in_class: bool = False


@router.post("/jobs/{job_id}/tryit")
def send_tryit(job_id: str, body: TryIt):
    """Keep one learner's guess, what they saw and their answer to the lesson's task; returns what to reveal."""
    try:
        stored = tryit.store(job_id, body.model_dump())
    except KeyError:
        raise HTTPException(status_code=404, detail="this lesson has no try-it-yourself task")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    analytics.note("tryit_sent", job_id=job_id)
    return stored


@router.get("/jobs/{job_id}/timeline")
def timeline(job_id: str, format: str = "contract"):
    """The finished lesson as the shared contract's video-timeline/1 (one segment per spoken sentence)."""
    _or_404(service.get_job, job_id)
    root = service._lesson_root(job_id)
    if not (root / "timeline.json").is_file() or not (root / "lesson.json").is_file():
        raise HTTPException(status_code=409, detail="this lesson has no timeline yet")
    return contract.video_timeline(root, job_id)


@router.get("/jobs/{job_id}/tryit")
def read_tryit(job_id: str):
    """The lesson's task and what learners wrote, newest first (not open to a review link)."""
    return _or_404(tryit.summarize, job_id)


@router.get("/jobs/{job_id}/review_link")
def review_link(job_id: str):
    """A link students can open: it can load this lesson and send one review, nothing else."""
    _or_404(service.get_job, job_id)
    token = feedback.review_token()
    if not token:
        raise HTTPException(status_code=503, detail="set LESSONFORGE_REVIEW_TOKEN on the server to share review links")
    return {"path": f"/app/?token={token}#review={job_id}"}


class Event(BaseModel):
    event: str
    job_id: Optional[str] = None
    value: Any = None


@router.post("/events")
def event(body: Event):
    """What only the client can see: which screen is up, a video starting, how much of it was watched."""
    try:
        return {"stored": analytics.client_event(body.model_dump())}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/stats")
def stats(days: int = 7, tz: int = 0, tests: int = 0, me: int = 1):
    """Visitors, lessons, plays, reviews and spend. ``tz``: the viewer's minutes east of UTC;
    ``me=0`` leaves out the browser asking; ``tests=1`` counts automated browsers too."""
    mine = (analytics.current() or {}).get("visitor", "")
    return analytics.stats(days=days, tz_minutes=tz, include_tests=bool(tests), exclude="" if me else mine)


@router.post("/clips")
def make_clip(req: dict):
    """One short moving picture for another app's video (Image Teacher's "motion" scenes): see ``harness/clip.py``.
    Answers when the clip is made (about 20-90 s; the same request again is served from the cache)."""
    import hashlib
    import json as _json
    from .. import paths
    try:
        checked = clip.check_request(req)
    except clip.ClipError as e:
        raise HTTPException(status_code=400, detail=str(e))
    try:
        spend.ensure_credit(0.05, "a clip")
    except spend.BudgetExceeded as e:
        raise HTTPException(status_code=402, detail=str(e))
    clip_id = hashlib.sha1(_json.dumps(checked, sort_keys=True).encode()).hexdigest()[:16]
    out = paths.sub("clips") / f"{clip_id}.mp4"
    if out.is_file():
        return {"schema": clip.SCHEMA, "id": clip_id, "url": f"/api/harness/clips/{clip_id}.mp4",
                "seconds": checked["seconds"], "cached": True}
    try:
        made = clip.make_clip(checked, out)
    except clip.ClipError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return {"schema": clip.SCHEMA, "id": clip_id, "url": f"/api/harness/clips/{clip_id}.mp4",
            "seconds": made["seconds"], "cues": made["cues"], "cached": made["cached"]}


@router.get("/clips/{clip_id}.mp4")
def clip_file(clip_id: str):
    import re as _re
    from fastapi.responses import FileResponse
    from .. import paths
    if not _re.fullmatch(r"[0-9a-f]{16}", clip_id):
        raise HTTPException(status_code=404, detail="no such clip")
    f = paths.sub("clips", create=False) / f"{clip_id}.mp4"
    if not f.is_file():
        raise HTTPException(status_code=404, detail="no such clip")
    return FileResponse(f, media_type="video/mp4")
