"""Per-lesson settings: every switch the pipeline reads from the environment, as controls a requester can set.

The harness has grown about fifty ``HARNESS_*`` / ``LESSONFORGE_*`` switches (pictures on or off, how many review
rounds, which models, which voice fallbacks ...). They were read with ``os.getenv`` at the moment of use, so they
were one setting for the whole server. A lesson can now carry its own: ``service.start_job(..., settings=)`` stores
them on the job and ``_run`` applies them for the job's duration with :func:`applied`; every read goes through
:func:`get`, which answers the job's value first and the environment after.

Jobs run in threads, two at a time, and a job's stages fan out into pools of their own, so the overrides live in a
``contextvars`` variable and :func:`wrap` carries them into a pool's workers (a plain ``ThreadPoolExecutor`` does
not copy the context). A switch that is read in a manim SUBPROCESS (the question card's form) travels in that
process's environment instead: :func:`render_env`.

``CONTROLS`` is the catalogue the app renders (``GET /api/harness/controls``) and :func:`validate` is the gate a
request's settings pass: an unknown name or a value of the wrong shape is refused with its name, so a typo cannot
silently do nothing. Adding a switch: one ``Control`` here; read it with ``knobs.get``; nothing else.
"""
from __future__ import annotations

import contextvars
import os
import re
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Callable, Iterator

_OVERRIDES: contextvars.ContextVar[dict] = contextvars.ContextVar("lessonforge_knobs", default={})


def get(name: str, default: str | None = None) -> str | None:
    """The value of a switch for THIS lesson: its own setting, else the environment, else ``default``."""
    found = _OVERRIDES.get().get(name)
    if found is not None:
        return found
    return os.getenv(name, default)


def overrides() -> dict:
    """The settings in force for this lesson (a copy)."""
    return dict(_OVERRIDES.get())


def environ() -> dict:
    """The environment as this lesson sees it (for code that takes a mapping, such as ``look.for_new``)."""
    return {**os.environ, **_OVERRIDES.get()}


def render_jobs() -> int:
    """How many chapters are filmed at once (``LESSONFORGE_RENDER_JOBS``, default 8)."""
    try:
        return max(1, int(get("LESSONFORGE_RENDER_JOBS", "8") or 8))
    except (ValueError, TypeError):
        return 8


@contextmanager
def applied(settings: dict | None) -> Iterator[None]:
    """Apply a lesson's settings to everything run inside the block (this thread, and pools through ``wrap``)."""
    token = _OVERRIDES.set({**_OVERRIDES.get(), **{k: str(v) for k, v in (settings or {}).items()}})
    try:
        yield
    finally:
        _OVERRIDES.reset(token)


def wrap(fn: Callable) -> Callable:
    """``fn`` with the calling thread's settings: hand this to a pool so its workers see the lesson's settings.

    The lesson's spending tally (``spend.lesson_scope``) is carried the same way, so a pool's calls count
    against the lesson's own ceiling and carry its id in the ledger.

    The settings are copied here and set again in each call, never run through one ``contextvars.Context``: a
    context can be entered by one thread at a time, and a pool mapping it over several workers raised
    ``RuntimeError`` in every worker but the first (found by ``test_picture_off``: the look at the stills then
    found nothing and no picture was taken off).
    """
    from . import spend  # noqa: PLC0415 - the lesson's spending tally travels with its settings
    settings = dict(_OVERRIDES.get())
    lesson = spend._LESSON.get()

    def inside(*args, **kwargs):
        token = _OVERRIDES.set(settings)
        tally = spend._LESSON.set(lesson)
        try:
            return fn(*args, **kwargs)
        finally:
            spend._LESSON.reset(tally)
            _OVERRIDES.reset(token)

    return inside


# ── the catalogue ──

@dataclass(frozen=True)
class Control:
    id: str                       # the environment name the code reads
    group: str
    label: str
    kind: str                     # toggle | choice | number | text
    default: str                  # the code's own default, as the environment string
    hint: str = ""
    options: tuple = ()           # choice: (value, label) pairs
    low: int = 0                  # number
    high: int = 0
    render: bool = False          # read in the manim subprocess: travels in its environment (render_env)
    pattern: str = ""             # text: what a value must match

    def view(self) -> dict:
        row = {"id": self.id, "group": self.group, "label": self.label, "kind": self.kind,
               "default": self.default, "current": get(self.id, self.default), "hint": self.hint}
        if self.kind == "choice":
            row["options"] = [{"value": v, "label": l} for v, l in self.options]
        if self.kind == "number":
            row["low"], row["high"] = self.low, self.high
        return row


def _toggle(id, group, label, default, hint="", render=False):
    return Control(id, group, label, "toggle", default, hint, render=render)


def _choice(id, group, label, default, options, hint="", render=False):
    return Control(id, group, label, "choice", default, hint, options=tuple(options), render=render)


def _number(id, group, label, default, low, high, hint=""):
    return Control(id, group, label, "number", str(default), hint, low=low, high=high)


def _models(id, group, label, default, hint=""):
    return Control(id, group, label, "text", default, hint, pattern=r"^[\w.-]+/[\w.:-]+(,[\w.-]+/[\w.:-]+)*$")


WRITING, PICTURES, CHECKS, VOICE, LOOK, MODELS, SPEED = ("Writing", "Pictures", "Checks and repair", "Voice",
                                                         "Look of the video", "Models", "Speed")

CONTROLS: tuple[Control, ...] = (
    # writing
    _toggle("HARNESS_TOPIC_READ", WRITING, "Read the typed topic before searching", "1",
            "A small model reads what the topic is (subject, class) before sources are looked for."),
    _number("HARNESS_CRITIC_ROUNDS", WRITING, "Review rounds", 2, 0, 4,
            "How many times the reviewer reads the script and has it revised. 0 reviews once and changes nothing."),
    _toggle("HARNESS_COHERENCE", WRITING, "Check that the lesson flows", "0",
            "One small extra look in each review: does every chapter pick up from the last, is each term explained "
            "before it is used, is the opening question answered. What it finds is rewritten like other findings."),
    _toggle("HARNESS_STORY_GATE", WRITING, "Check the story does not jump", "0",
            "No model call: lines that say the lesson's plan aloud (\"Pause on that\", \"Now you, with help\") are rewritten "
            "like other findings. None of them occurs in 590,000 words of good YouTube explainers."),
    _toggle("HARNESS_STORY_FIRST", WRITING, "Write a story lesson's words in one go", "1",
            "One small model call: a lesson with the story framework gets its words from one plain story prompt, and the "
            "screen is then designed around them, keeping every word. Blind script scores 7-8 against 5-6 when the "
            "same story is written chapter by chapter. English only."),
    _toggle("HARNESS_TEACHING_RUBRIC", WRITING, "Score how the lesson teaches", "0",
            "One small extra look in each review: eight weighted teaching criteria (clarity, order, prediction, "
            "demonstration, correctness, examples, mistakes, takeaway), each scored with words quoted from the script. "
            "A low score with a quote is rewritten like other findings."),
    _toggle("HARNESS_EXPLANATIONS", WRITING, "Start from the checked explanation", "1",
            "Give the writer the textbook-framed explanation, the common mistake and the best lectures for this "
            "concept from the NCERT concept table, when the topic clearly matches a row. No model call."),
    _toggle("HARNESS_QUESTIONS", WRITING, "Improve the questions", "1",
            "One pass that rewrites each question card by kind (predict, apply, spot, recall)."),
    _choice("LESSONFORGE_VOICE_POLISH", WRITING, "Polish how the narration sounds", "",
            (("", "With a teaching card"), ("1", "Always"), ("0", "Never")),
            "A rewrite that removes orders, repeated openers, talk about the screen, notes and too many questions."),
    _toggle("HARNESS_LECTURER_VOICE", WRITING, "Learn the manner from YouTube lecturers", "1",
            "The writer reads two short passages of real lectures on the topic, chosen for how plainly they explain, "
            "and takes their manner, never their words. Free (captions only)."),
    _toggle("HARNESS_SCRIPT_READER", WRITING, "Reader model for a structured pasted script", "1",
            "A pasted document with scenes, tables or answer keys is labelled line by line before it is spoken."),
    _choice("HARNESS_CONCEPTS", WRITING, "Concept knowledge base", "1",
            (("1", "Use it, and keep what new topics teach"), ("use", "Use it only"), ("0", "Off")),
            "A topic the knowledge base knows is explained its one proven way, with its chosen picture; a new topic's "
            "card is kept once its lesson passes its checks."),
    _toggle("HARNESS_SCRIPT_REFERENCES", WRITING, "Reference lessons for a pasted script", "1",
            "Two lectures on the script's topic are read for what they show, never for words."),
    # pictures
    _toggle("HARNESS_TOPIC_PICTURES", PICTURES, "Drawings from the drawing service", "1",
            "The topic's own drawing, asked for before the script is written."),
    _toggle("HARNESS_SCRIPT_PICTURES", PICTURES, "Pictures for a pasted script", "1",
            "Each part of a pasted script asks the drawing service for its picture."),
    _number("HARNESS_SCRIPT_MAX_PICTURES", PICTURES, "Most drawings for one pasted script", 8, 1, 12),
    _toggle("HARNESS_JUDGE_PICTURES", PICTURES, "Look at each drawing before using it", "1",
            "A small vision model checks the drawing is of the thing asked for; a wrong one is asked for again."),
    _toggle("HARNESS_PICTURE_HOLDS", PICTURES, "Tell the writer what the drawing holds", "1",
            "The finished drawing is read once and the writer may only speak of what is in it."),
    _toggle("HARNESS_TYPESET_NAMES", PICTURES, "Read the printed labels of typeset drawings", "1"),
    _choice("HARNESS_DRAWING_LOOK", PICTURES, "Drawing look", "paper",
            (("paper", "Paint on paper"), ("0", "As drawn"))),
    _toggle("HARNESS_SEQUENCE", PICTURES, "Draw the picture stroke by stroke", "1",
            "The drawing is taken apart into its parts and drawn with a pen instead of appearing whole."),
    _toggle("HARNESS_DRAW_WITH_WORDS", PICTURES, "Draw each part when the words name it", "1"),
    _toggle("LESSONFORGE_KITS", PICTURES, "Subject kits (motion and later subjects)", "1",
            "Off: only the built-in figure kinds and geometry checks run, exactly as before. A stored lesson with a "
            "kit's figure then keeps the previous picture on screen where the kit's figure was."),
    _toggle("LESSONFORGE_KITS_MIXED", PICTURES, "Lessons that mix subjects (geometry and motion in one lesson)", "1",
            "On: each beat belongs to the subject kit of its figure and is checked by that kit only, so one lesson can "
            "draw from several subjects. Off: a lesson that draws from two subject kits gets one fault asking for one "
            "subject, exactly as before. Has no effect while the subject kits are off."),
    _toggle("LESSONFORGE_COMPONENT_FRAME", PICTURES, "One card size for a run of beats on one component", "1",
            "On: when a lesson is settled, the beats that show one library component in different states are given one "
            "frame (the union of their drawings), so the picture does not change size or place between them. Off: each "
            "state has its own card, as before 9 November. A lesson already settled keeps what it was given."),
    _toggle("LESSONFORGE_COMPONENT_TWEEN", PICTURES, "A library component's number moves between beats", "0",
            "On: when a library component changes only a number that moves it smoothly (a cell losing water, a bob "
            "swinging) between two beats of one run, the drawing moves from the old to the new in the lead-in instead of "
            "fading out and being drawn again. Off: the old fade, exactly as before. Read when the video is rendered.",
            render=True),
    _toggle("LESSONFORGE_COMPONENT_TIGHT", PICTURES, "Larger writing and less paper round a library component", "0",
            "On: the labels of a library component are set as large as the room between them allows (15 to 18 px instead "
            "of 14, one size for a run of beats on one card) and the paper margin is 0.10 instead of 0.18 scene units, "
            "so the drawing and its writing are larger on the screen. A size that would put one label on another is "
            "not used. Off: the sizes the library previews, exactly as before. Read when the video is rendered.",
            render=True),
    _number("HARNESS_PLAN_VOTES", PICTURES, "Votes for the drawing plan", 3, 1, 5,
            "The model is asked this many times when each part is drawn; the median wins."),
    _toggle("HARNESS_PRINTED_TELLS", PICTURES, "Hold back printed words that tell an answer", "1"),
    _toggle("HARNESS_ANNOTATE", PICTURES, "The hand's marks", "1",
            "Spoken values written on the drawing, rings and strokes with the words (about 4 cents a drawing)."),
    _toggle("HARNESS_COMPOSE", PICTURES, "Compose stage", "1",
            "The lesson is previewed as stills before any narration, to settle how pictures are shown."),
    _toggle("HARNESS_COMPOSE_LOOK", PICTURES, "Vision look at the preview", "1",
            "A model looks at the end still of each beat for words that point at things the picture lacks."),
    _choice("HARNESS_COMPOSE_MEND", PICTURES, "Act on what the look finds", "pictures",
            (("pictures", "Hide a wrong picture for that beat"), ("words", "Also rewrite the words"), ("0", "Report only")),
            "Rewriting words was tried and made lessons worse one time in three."),
    _toggle("HARNESS_COMPOSE_DRAW", PICTURES, "A drawing of its own for a beat about something else", "1",
            "At most three a lesson, from the drawing service."),
    _choice("HARNESS_SCENE_LOOK", PICTURES, "Look at each animated scene against its description", "0",
            (("0", "Off"), ("1", "Look and report"), ("redraw", "Look, and draw again what misses")),
            "A small vision model checks the scene's stills thing by thing (about half a cent a scene). Off: in the "
            "first trial its redraws cured nothing."),
    _toggle("HARNESS_COMPOSE_SCENES", PICTURES, "Draw a scene again when it lacks what its words name", "1",
            "At most four a lesson; kept only when a second look says a fault was cured. Tried on two lessons: two scenes better, one mixed, one worse."),
    _toggle("HARNESS_REPAINT", PICTURES, "Repaint drawings with the local image model", "0",
            "Needs a free GPU; loses small things now and then. Off unless you want to see it."),
    # checks
    _toggle("HARNESS_VISION_REVIEW", CHECKS, "Frame review of the finished video", "1",
            "One frame per beat is looked at for what the screen shows against what is said."),
    _toggle("HARNESS_SCREEN_REPAIR", CHECKS, "Repair what the frame review finds", "1",
            "Steps of a faulty beat are written again and the chapter rendered again; kept only when better."),
    _number("HARNESS_SCREEN_REPAIR_BEATS", CHECKS, "Most beats repaired this way", 6, 1, 12),
    _toggle("HARNESS_SYNC_REPAIR", CHECKS, "Re-time steps that are out of step with the voice", "1",
            "Before the render, a step whose words are never heard, or that comes too soon after the one before, "
            "waits for other words of the same narration. No model, no money; kept only when the beat is better."),
    _toggle("HARNESS_SYNC_THIN", CHECKS, "Fewer lines where they cannot be read in time", "1",
            "When re-timing cannot give a line time to be read, it is cut to its first clause or, if the voice "
            "says it anyway, taken off the screen. Never a question, working, or a line that points at the picture."),
    _toggle("HARNESS_QUIZ_LEAKS", CHECKS, "Keep a quiz's answer off the screen until it is asked", "1",
            "A speed-time graph leaves the point that shows the answer off until the beat after the question; any other "
            "place the answer is already said or shown is noted on the lesson. The words are not rewritten."),
    _toggle("HARNESS_STORYBOARD_MEND", CHECKS, "Fix screens before the voice is made", "1",
            "A beat whose voice says numbers or words its screen never shows gets its steps written again before any "
            "audio is made; kept only when the storyboard check then finds less."),
    _toggle("LESSONFORGE_ALIGN", CHECKS, "Word timing by the recogniser", "1",
            "Whisper hears each clip so every cue lands on its word (about 0.2 cents a minute)."),
    _toggle("HARNESS_STORE", CHECKS, "Reuse kept stages", "1",
            "A script or review made before for the same brief and code is used again instead of paid for."),
    # voice
    _toggle("HARNESS_PAID_VOICES", VOICE, "Paid voices as fallbacks", "0",
            "Sarvam and Gemini voices tried when our own cannot be used (charged per lesson)."),
    _toggle("HARNESS_EDGE_VOICES", VOICE, "Microsoft's online voices in the voice list", "1",
            "Free neural voices in Hindi, Indian English, Telugu and Tamil (edge-tts). Not an official service: it can "
            "stop working, so a lesson uses one only when it is chosen."),
    _toggle("HARNESS_LOCAL_VOICE", VOICE, "The voice on this machine (Kokoro)", "1",
            "English and Hindi; the fallback when the owner's service is down."),
    _choice("HARNESS_KOKORO_HINDI", VOICE, "Kokoro's Hindi voice", "hf_alpha",
            (("hf_alpha", "Alpha (female)"), ("hf_beta", "Beta (female)"), ("hm_omega", "Omega (male)"), ("hm_psi", "Psi (male)"))),
    _toggle("HARNESS_ALLOW_GTTS", VOICE, "The basic voice as the last fallback", "1",
            "gTTS, free and flat. Off means a lesson that gets no other voice is silent."),
    # look
    _choice("HARNESS_FRAME", LOOK, "Frame", "stage",
            (("stage", "Stage: one line at a time beside the picture"), ("columns", "Columns, as before 10 October"))),
    _choice("HARNESS_CAPTIONS", LOOK, "Captions", "outside",
            (("outside", "Under the video, by the player"), ("band", "Drawn into the video"))),
    _choice("HARNESS_PAGE", LOOK, "Page", "",
            (("", "Light for drawn lessons, dark otherwise"), ("paper", "Light paper"), ("night", "Dark"))),
    _choice("HARNESS_WORKING", LOOK, "Working lines", "pinned",
            (("pinned", "Kept while the words come one at a time"), ("column", "A column of small lines"))),
    _choice("HARNESS_DRAWINGS", LOOK, "Drawings", "painted",
            (("painted", "Drawn by a pen"), ("shown", "Shown whole"))),
    _choice("HARNESS_JOINS", LOOK, "Joins between parts", "carried",
            (("carried", "Smooth: a part opens on the screen the last one left"), ("cut", "A cut and a pause, as before 15 October"))),
    _choice("HARNESS_MATH", LOOK, "Formulas", "sans",
            (("sans", "In the same plain face as the words"), ("serif", "In the textbook serif face, as before 17 October"))),
    _choice("HARNESS_VALUES", LOOK, "Numbers beside an angle", "spoken",
            (("spoken", "Drawn when the voice says them"), ("named", "Drawn with the angle's arc, as before 9 November"))),
    _choice("HARNESS_STAGING", LOOK, "Graphs and tables", "steps",
            (("steps", "Each point, equation, count and verdict drawn at its own words"), ("whole", "Shown whole with the picture, as before 9 November"))),
    _choice("HARNESS_CRAFT", LOOK, "Title card, closing hold and pauses", "crafted",
            (("crafted", "A 2 s title card, a 3 s closing hold, pictures that cross-fade, a clean thinking pause"),
             ("plain", "As before 9 November"))),
    _choice("LESSONFORGE_QUIZ_IN_VIDEO", LOOK, "A question card shows", "question",
            (("question", "The question only; the player takes the answer"), ("options", "The options too")), render=True),
    # models
    _models("HARNESS_WRITER_MODELS", MODELS, "Writer", "anthropic/claude-haiku-5.5,qwen/qwen3.8-flash,openai/gpt-5.4-nano",
            "Comma-separated, tried in order. A dearer model costs several times more a script."),
    _models("HARNESS_CRITIC_MODELS", MODELS, "Reviewer", "anthropic/claude-haiku-5.5,openai/gpt-5.4-nano,deepseek/deepseek-v4-pro"),
    _models("HARNESS_CARD_MODELS", MODELS, "Teaching card", "anthropic/claude-haiku-5.5,openai/gpt-5.4-nano,google/gemini-3.8-flash"),
    _models("HARNESS_PLAN_MODEL", MODELS, "Drawing plan", "anthropic/claude-haiku-5.5"),
    _models("HARNESS_ANNOTATE_MODEL", MODELS, "The hand's marks", "anthropic/claude-haiku-5.5"),
    _models("HARNESS_VISUAL_MODELS", MODELS, "Small looks (pictures)", "google/gemini-3.5-flash-lite,google/gemini-2.5-flash,openai/gpt-5.4-nano"),
    _models("HARNESS_TOPIC_MODELS", MODELS, "Reading the topic", "google/gemini-3.5-flash-lite,google/gemini-2.5-flash,openai/gpt-5.4-nano"),
    _models("HARNESS_BLUEPRINT_MODELS", MODELS, "How each source teaches", "google/gemini-3.5-flash-lite,google/gemini-2.5-flash,openai/gpt-5.4-nano"),
    _models("HARNESS_READER_MODELS", MODELS, "Script reader", "google/gemini-3.5-flash-lite,google/gemini-2.5-flash,openai/gpt-5.4-nano"),
    _models("HARNESS_VOICE_SCRIPT_MODELS", MODELS, "Hinglish for the voice", "google/gemini-3.5-flash-lite,google/gemini-2.5-flash,openai/gpt-5.4-nano"),
    # speed
    _number("HARNESS_SCENE_WORKERS", SPEED, "Scenes written at once", 3, 1, 8),
    _choice("LESSONFORGE_RENDERER", SPEED, "Renderer", "manim",
            (("manim", "Manim (Python)"), ("ts", "Revideo (TypeScript)"))),
)

BY_ID: dict[str, Control] = {c.id: c for c in CONTROLS}
GROUPS: tuple[str, ...] = (WRITING, PICTURES, CHECKS, VOICE, LOOK, MODELS, SPEED)


def catalogue() -> dict:
    """What the app renders: every control with the server's current value."""
    return {"groups": list(GROUPS), "controls": [c.view() for c in CONTROLS]}


class BadSetting(ValueError):
    pass


def validate(settings: dict | None) -> dict[str, str]:
    """A request's settings as environment strings, or ``BadSetting`` naming the first that cannot be taken.

    A value equal to the control's default is dropped: the job then records only what was changed.
    """
    out: dict[str, str] = {}
    for name, raw in (settings or {}).items():
        control = BY_ID.get(str(name))
        if control is None:
            raise BadSetting(f"unknown control: {name}")
        if raw is None:
            continue
        if control.kind == "toggle":
            if isinstance(raw, bool):
                value = "1" if raw else "0"
            elif str(raw).strip().lower() in ("1", "true", "on", "yes"):
                value = "1"
            elif str(raw).strip().lower() in ("0", "false", "off", "no"):
                value = "0"
            else:
                raise BadSetting(f"{name}: expected on or off, got {raw!r}")
        elif control.kind == "choice":
            value = str(raw).strip()
            if value not in {v for v, _ in control.options}:
                raise BadSetting(f"{name}: not one of {[v for v, _ in control.options]}: {raw!r}")
        elif control.kind == "number":
            try:
                number = int(raw)
            except (TypeError, ValueError):
                raise BadSetting(f"{name}: expected a whole number, got {raw!r}")
            if not control.low <= number <= control.high:
                raise BadSetting(f"{name}: must be between {control.low} and {control.high}, got {number}")
            value = str(number)
        else:
            value = re.sub(r"\s+", "", str(raw))[:400]
            if control.pattern and not re.fullmatch(control.pattern, value):
                raise BadSetting(f"{name}: expected model ids separated by commas, got {raw!r}")
        if value != control.default:
            out[control.id] = value
    return out


def render_env() -> dict[str, str]:
    """The settings a manim subprocess must see (read there, not through ``get``): for ``extra_env``."""
    own = _OVERRIDES.get()
    return {c.id: own[c.id] for c in CONTROLS if c.render and c.id in own}
