"""Scene runtime for audio-first chapters: measured narration timing + shared style.

A chapter scene never decides how long anything takes. It names WHAT happens and
which spoken phrase it belongs to; this runtime waits until that phrase is actually
being said (``timeline.json``, built from the real audio) and then plays it:

    from lessonforge.longform.runtime import *

    class C01(LessonScene):
        def construct(self):
            self.chapter(1)
            self.begin("01")
            self.cue("Picture a rectangular warehouse floor", Create(floor))
            self.cue("then three metres north", Create(leg), run_time=1.4)
            self.finish()
            self.done()

Every chapter writes ``output/chapter_NN_audit.json``: where each cue landed against
where it was meant to, and — per beat — anything left outside the stage area. With
the layout probe on (default) the same per-play measurements the engine uses for its
repair loop are printed as ``LAYOUT_VIOLATION:`` lines and attributed to beats by the
build (``build.render_chapters``).

The lesson directory is found from ``LESSONFORGE_LESSON_DIR`` (set by the build), else
from the folder of the file that defines the scene — so a chapter file still renders
with a bare ``manim chapters.py C01`` next to its ``lesson.json``.
"""
from manim import *  # noqa: F401,F403  (re-exported for chapter files)
from pathlib import Path
import inspect
import json
import os
import re
import textwrap

import numpy as np

from . import look as _look

# Teaching palette (docs/research/approaches/05_* §Q4): dark theme, every text colour
# ≥ 6:1 against the background, colour never the only signal.
BG = "#1C1F26"
INK = "#F2F3F5"
MUTED = "#A8B0BD"
TEAL = "#80B1E7"   # "given" blue (name kept for the scene files)
GOLD = "#FFE566"   # accent / highlight
PINK = "#E57A9E"   # "wrong"
GRID = "#2E3340"
FONT = os.getenv("LESSONFORGE_FONT", "Lato")
MINT = "#56FAAA"   # "result" green
#: How THIS lesson looks (``look.py``): its frame, where its captions are shown, its page. The service wrote it into
#: the lesson when it was made; it is read once, here, because the palette below is the default of ``txt`` and ``eq``
#: and so is fixed when this module is loaded. A lesson that says nothing is laid out as lessons were before
#: 2026-10-10. (A chapter file run by hand next to its lesson.json, with no LESSONFORGE_LESSON_DIR, is that too.)
LOOK = _look.of(_look.read(os.getenv("LESSONFORGE_LESSON_DIR")))
#: "paper": a light page. A prepared drawing is made for white paper; on the dark page it is a white card beside a
#: column of text, which is most of why a lesson read as a slide. Every text colour is 5.5:1 or more on it.
THEME = LOOK["page"]
if THEME == "paper":
    BG, INK, MUTED, GRID = "#F6F1E7", "#1F2933", "#4F5A69", "#DDD5C6"
    TEAL, GOLD, PINK, MINT = "#17578F", "#9A4507", "#A82B59", "#0B6B3D"
config.background_color = BG


def txt(s, size=28, color=INK):
    return Text(s, font=FONT, font_size=size, color=color)


#: Formulas in a sans-serif face when the lesson's look says so (``look.MATHS``); None keeps Manim's own template.
SANS_MATH = None
if LOOK.get("math") == "sans":
    SANS_MATH = TexTemplate()
    SANS_MATH.add_to_preamble(r"\renewcommand{\familydefault}{\sfdefault}\usepackage{sfmath}")


def eq(s, size=42, color=INK):
    if SANS_MATH is not None:
        # the sans face's figures are about a fifth smaller than the words' at one point size; set to look alike
        return MathTex(s, font_size=size * 1.2, color=color, tex_template=SANS_MATH)
    return MathTex(s, font_size=size, color=color)


def fit(m, width=6.5, height=4.7, center=(-2.8, -.1, 0)):
    """Shrink (never enlarge) a mobject into a box and centre it there."""
    factor = min(1, width / max(m.width, .001), height / max(m.height, .001))
    m.scale(factor).move_to(center)
    return m


def fill(m, width=7.4, height=4.8, center=(-2.95, -.125, 0), most=1.7):
    """Scale a mobject to FILL a box — enlarging it too, up to ``most`` times — and centre it there."""
    factor = min(most, width / max(m.width, .001), height / max(m.height, .001))
    m.scale(factor).move_to(center)
    return m


def screen_words(show, most=14):
    """A step's wording as it may stand on screen: at most ``most`` words, cut at a word, with an ellipsis.

    The script rules ask for nine words. A writer once put a whole instruction to the animator there
    ("Say the route, highlight the sea to cloud, cloud to ground and return legs with labels …", cut
    mid-word at 110 characters): five wrapped lines that shrank every other step in the column.
    """
    words = str(show).split()
    return " ".join(words) if len(words) <= most else " ".join(words[:most]).rstrip(",;:") + " …"


def swept_box(origin, animator, samples=13):
    """(x0, x1, y0, y1) of everything a scene shows from its first frame to its last, where it was verified."""
    work = origin.copy()

    def box(m):
        return [float(m.get_left()[0]), float(m.get_right()[0]), float(m.get_bottom()[1]), float(m.get_top()[1])]
    seen = [box(work)]
    try:
        animation = animator(work, 3.0)
        animation.begin()
        for i in range(samples):
            animation.interpolate(i / (samples - 1.0))
            seen.append(box(work))
        animation.finish()
        seen.append(box(work))
    except Exception:  # noqa: BLE001 - a scene that cannot be stepped is laid out by what it shows at rest
        pass
    return min(b[0] for b in seen), max(b[1] for b in seen), min(b[2] for b in seen), max(b[3] for b in seen)


def scale_strokes(mob, factor):
    """Make every line of a picture as much thicker as the picture was made larger (each part its own width: a group's
    ``scale(scale_stroke=True)`` gives all its parts ONE width). Enlarged three times with its lines left as they
    were, a drawing looks as if it had been traced with a harder pencil."""
    if abs(factor - 1.0) < 1e-6:
        return mob
    for member in mob.get_family():
        try:
            width = member.get_stroke_width() if len(member.points) else 0
            if width:
                member.set_stroke(width=float(width) * factor, family=False)
        except Exception:  # noqa: BLE001 - an image or a group has no stroke of its own
            continue
    return mob


def place_scene(figure, width, height, center, most=1.7, swept=None, strokes=False):
    """Size and place a model-written scene by ALL it will show, not by its first frame.

    ``fill`` measured the picture as it stood before anything moved. A scene that starts small and
    grows (squares built on a triangle's sides) was enlarged to fill the box and then grew out of
    it: one lesson's last chapter ended 0.05 above the stage and failed its bounds check. The
    scene is stepped once on a copy, and the box of everything it showed is what is fitted and
    centred. Absolute, so calling it again changes nothing.
    """
    origin, inner = figure.origin, figure.inner
    x0, x1, y0, y1 = swept or swept_box(origin, figure.animator)
    scale = min(most, width / max(x1 - x0, .001), height / max(y1 - y0, .001))
    by = scale * origin.width / max(inner.width, 1e-6)
    figure.scale(by)
    if strokes:
        scale_strokes(figure, by)
    swept_centre = np.array([(x0 + x1) / 2, (y0 + y1) / 2, 0.0])
    figure.move_to(np.array(center, dtype=float) + (origin.get_center() - swept_centre) * scale)
    return figure


def _is_words(m):
    return isinstance(m, (Text, MarkupText, MathTex, DecimalNumber))


def outline_of(part):
    """A gold outline of a part's SHAPES, or None when it has none.

    The part's words are left out. Copied with the rest they were drawn a second time, in outline,
    on top of the label they came from: "3^2 = 9" lay on "3^2 = 9" in a square's corner, which the
    layout check rightly counted as text on text and which looked like a smudge.
    """
    if _is_words(part):
        return None
    ring = part.copy()
    for parent in ring.get_family():
        parent.submobjects = [child for child in parent.submobjects if not _is_words(child)]
    if not any(len(m.points) for m in ring.get_family()):
        return None
    return ring.set_fill(opacity=0).set_stroke(GOLD, width=6, opacity=.9)


_FOUND = re.compile(r"=\s*([-+]?\d[\d,]*(?:\.\d+)?(?:\s?[A-Za-z°%²³]{1,8})?)\s*$")


def found_value(show):
    """The value a line of working ends on ("4 \\times 4 = 16" → "16"), or '' when it ends on anything else."""
    match = _FOUND.search(plain_math(show))
    return match.group(1).strip() if match else ""


def math_rows(s):
    """A LIST written on one line ("17^2 = 289, 18^2 = 324, 19^2 = 361, 20^2 = 400") as two lines of about
    equal length, cut after a comma that separates items; ``[]`` for anything else.

    A comma inside braces or brackets, a thin space (``\\,``) and a thousands comma ("1,000") are not
    separators, and a multi-line block is left alone.
    """
    s = str(s).strip()
    if "\\\\" in s or "\\begin" in s:
        return []
    cuts, stops, depth = [], [], 0
    for i, ch in enumerate(s):
        depth += (ch in "{([") - (ch in "})]")
        if ch in ",;" and depth == 0 and s[i - 1:i] != "\\" and s[i + 1:i + 2].isspace():
            (stops if ch == ";" else cuts).append(i + 1)
    # Two statements joined by a semicolon ("F = mg = 10 N; a = 10/1 = 10", 2026-10-19) are cut there first: cut at
    # an equals sign instead, the second line began with "=" and read as a fragment.
    cuts = stops or cuts
    if not cuts:
        return []
    cut = min(cuts, key=lambda c: abs(c - len(s) / 2))
    rows = [s[:cut].strip().rstrip(";").strip(), s[cut:].strip()]
    return rows if all(len(r) > 2 for r in rows) else []


_RELATION = re.compile(r"\\x(?:right|left)arrow(?:\[[^\]]*\])?\{|\\(?:long)?(?:right|left|leftright)arrow\b|\\(?:to|implies|iff|approx|neq|leq|geq)\b|=")


def screen_question(beat: dict) -> str:
    """What a pause with no card of its own puts on its card: the beat's last line of words for the SCREEN ('' when it
    has none). Never the narration: what is said and what is shown are two scripts, and the card belongs to the second."""
    lines = [str(step.get("show") or "").strip() for step in beat.get("steps") or [] if step.get("kind") != "math"]
    lines = [line for line in lines if line]
    asking = [line for line in lines if line.endswith("?")]
    return (asking or lines or [""])[-1]


def relation_rows(s):
    """One long line of working as two: cut before its first top-level arrow or relation; ``[]`` when it has none.

    A word equation ("carbon dioxide + water -> glucose + oxygen", every word in ``\\text``) is long by nature; fitted to
    a column on one line it came out a quarter of the size of the lines around it and could not be read (the first
    lesson made end to end in this frame, 2026-10-10).
    """
    s = str(s).strip()
    if "\\\\" in s or "\\begin" in s:
        return []
    depth = 0
    for i, ch in enumerate(s):
        depth += (ch in "{([") - (ch in "})]")
        if depth == 0 and i > 2:
            found = _RELATION.match(s, i)
            if found:
                rows = [s[:i].strip(), s[i:].strip()]
                return rows if all(len(r) > 2 for r in rows) else []
    return []


class Later:
    """Animations worked out only when they are about to be played: ``cue`` waits for the words first.

    A figure's ``focus_animations`` also DOES things when it is called: a drawing that is built up by its parts stops
    the beads on the last part's arrows and starts them on this one's. Called when the step was prepared, which is
    seconds before its words are spoken, the beads ran along an arrow that had not been drawn yet (every lesson on a
    built-up drawing; seen in the frames of the first one made end to end, 2026-10-10).
    """

    def __init__(self, make):
        self.make = make


def stage_marks(marks, start):
    """Step times as stage edges: in order, none before the scene is up, two steps on one word made one stage."""
    edges = sorted(max(float(m), start) for m in (marks or []))
    return [e for i, e in enumerate(edges) if i == 0 or e - edges[i - 1] > .05]


def stage_progress(now, start, total, edges, across=False):
    """How far (0..1) a scene's motion has got at scene-clock ``now``.

    With no ``edges`` it runs evenly from ``start`` over ``total`` seconds. With edges (the times the
    beat's steps are spoken) it is cut into ``len(edges)`` equal stages. Stage k begins at edge k, nothing
    moves before the first edge, and a stage is PLAYED SOON AND THEN WAITS: it takes ``stage_seconds`` of
    the time to the next edge (the last one: to the end of the speech), not all of it. Spread over the
    whole gap, a block that "appears" was still half faded when its sentence had ended.

    ``across`` (a figure key written by hand, ``"pace": "voice"``; ``shape_figure.build`` sets ``fig.voice_paced``): a corner that is dragged or an angle
    that turns is not a block that appears; it should go on the whole time the sentence is spoken. With ``across`` a stage
    takes ALL the time to the next edge, evenly, so the picture moves across the voice and not for its first 40%.
    """
    if not edges:
        return min(1.0, max(0.0, (now - start) / max(total, 1e-6)))
    if now <= edges[0]:
        return 0.0
    last = len(edges) - 1
    k = max(i for i, e in enumerate(edges) if now >= e)
    until = edges[k + 1] if k < last else max(start + total, edges[k] + 1.0)
    done = min(1.0, (now - edges[k]) / (max(until - edges[k], .4) if across else stage_seconds(until - edges[k])))
    # A stage that is over rests a hair BEFORE the boundary, not on it (the very end is reached when the
    # beat ends). Exactly on a boundary the next stage's shapes are at their zero point: an arrow of no
    # length, a line from a point to itself. One scene raised there on every frame of every wait.
    return (k + (done if k == last else min(done, .999))) / len(edges)


#: A step's window for the voice-timed tween is at least this long (seconds); a shorter sentence keeps the lead-in tween.
VOICE_TWEEN_MIN = 1.0
#: Seconds of title card at the start of a crafted lesson; ``audio.TITLE_CARD_SECONDS`` makes the room for them in the timeline.
TITLE_CARD_SECONDS = 2.0


def tween_progress(now, start, end):
    """How far (0..1) a number's move has got at scene-clock ``now`` when it is driven by the voice (``_start_tween``).

    The move runs EVENLY from ``start`` (the moment the step's words begin) to a little before ``end`` (the moment the next
    step's words begin, or the speech ends), so it is going on while the sentence is spoken: a number that moves across
    "the cell shrinks" and not in the 0.45 to 1.4 s before it. ``stage_progress`` is the same cut of the beat into stages, but
    it plays a stage "soon and then waits" (a fifth of a long sentence), which is right for a block that appears and wrong
    for a number that slides. It rests a hair before ``end`` (at most 0.4 s, a sixth of a long window) so the new state is
    the one on screen when the sentence is over.
    """
    run = max(float(end) - float(start) - min(.4, (float(end) - float(start)) / 6), .2)
    return min(1.0, max(0.0, (float(now) - float(start)) / run))


def stage_seconds(gap):
    """How long one stage of a scene plays inside the ``gap`` to the next: about the time its words take."""
    return max(.4, min(gap, max(1.2, .4 * gap)))


_LATEX_WORDS = {"\\rightleftharpoons": "⇌", "\\rightarrow": "→", "\\to ": "→ ", "\\leftarrow": "←", "\\times": "×",
                "\\cdot": "·", "\\div": "÷", "\\approx": "≈", "\\neq": "≠", "\\leq": "≤", "\\geq": "≥", "\\pm": "±",
                "\\theta": "θ", "\\pi": "π", "\\alpha": "α", "\\beta": "β", "\\eta": "η", "\\Delta": "Δ", "\\circ": "°",
                "\\sqrt": "√", "\\quad": " ", "\\,": " ", "\\;": " "}


_SILENT_GLYPHS = {"×": r" \times ", "÷": r" \div ", "·": r" \cdot ", "−": "-"}


def plain_math(s):
    """LaTeX that will not compile, as words a viewer can read — never the raw markup."""
    s = re.sub(r"\\(?:begin|end)\{[A-Za-z*]+\}", " ", str(s))
    s = re.sub(r"\\(?:text|mathrm|mathbf|operatorname)\s*\{([^{}]*)\}", r"\1", s)
    s = re.sub(r"\\frac\s*\{([^{}]*)\}\s*\{([^{}]*)\}", r"(\1)/(\2)", s)
    for command, symbol in _LATEX_WORDS.items():
        s = s.replace(command, symbol)
    s = re.sub(r"\\[A-Za-z]+", " ", s).replace("{", "").replace("}", "").replace("&", " ").replace("\\", " ")
    return re.sub(r"\s+", " ", s).strip()


def safe_eq(s, size=42, color=INK):
    """``eq`` that degrades to READABLE words when the LaTeX does not compile.

    The fallback used to print the raw markup as text; a three-line ``aligned`` block
    then appeared as a wall of backslashes shrunk too small to read (seen in a real
    chemistry lesson). Now the markup is translated to plain words and wrapped.
    """
    # LaTeX DROPS these characters without an error ("6 ÷ 2 = 3 cm" was set as "62 = 3cm"): their commands instead
    for char, command in _SILENT_GLYPHS.items():
        s = str(s).replace(char, command)
    try:
        return eq(s, size, color)
    except Exception:
        return wrapped(plain_math(s)[:140] or "?", 30, min(size, 28), color)


def wrapped(s, width=40, size=22, color=MUTED, line_gap=.18):
    """Left-aligned paragraph: Pango does not wrap, so lines are broken here."""
    # A word is never cut in two: "Parallelogra / m?" was on screen. A word longer than the line keeps its own line
    # and the caller shrinks what does not fit (``_lines``).
    lines = [txt(line, size, color) for line in textwrap.wrap(s, width, break_long_words=False)] or [txt(" ", size, color)]
    return VGroup(*lines).arrange(DOWN, aligned_edge=LEFT, buff=line_gap)


_norm = lambda s: re.sub(r"[^\w ]", "", s.lower())  # noqa: E731
# Where a phrase is spoken: ONE search for the renderer and the timeline compiler (longform/timeline_compiler.py).
from .timeline_compiler import CUE_LEAD, locate as _locate  # noqa: E402,F401  CUE_LEAD: the picture leads aligned words
# "question" (default): a thinking pause shows the question and a countdown. "options": it also
# draws the answer choices and lights up the right one — only for a file watched without the player.
QUIZ_IN_VIDEO = os.environ.get("LESSONFORGE_QUIZ_IN_VIDEO", "question").strip().lower()
#: A folder for STILLS (``longform/preview.py``). With it a chapter is not filmed: the preview runs manim with ``-s``,
#: which jumps every animation to its end, and a picture of the screen is saved after every step, at every pause and
#: at the end of every beat, with what was measured there. How a lesson will look is then known in seconds, before
#: its narration is bought and before it is rendered.
STILLS = os.getenv("LESSONFORGE_STILLS", "").strip()


def type_points(mob):
    """The size, in points AS IT STANDS, of every piece of type in a mobject: a line scaled to fit says its real size."""
    sizes = []
    for member in mob.get_family():
        if isinstance(member, (Text, MarkupText, MathTex)):
            try:
                sizes.append(round(float(member.font_size), 1))
            except Exception:  # noqa: BLE001 - an empty line has no height to measure
                pass
    return sizes


class LessonScene(Scene):
    def render(self, preview: bool = False):
        """A chapter that raises must END with its traceback. Left to Manim it never ends.

        Manim reports the error and returns; the interpreter then waits at shutdown for the thread that
        writes the movie, which is waiting for frames that will never come. On 2026-10-09 the last chapter
        of a lesson raised in its third animation and its process then slept for half an hour: the job
        stayed "rendering", and a job in progress blocks every restart. So: print, flush, and leave.
        """
        try:
            return super().render(preview)
        except Exception:  # noqa: BLE001
            import sys
            import traceback
            traceback.print_exc()
            print("LESSON_NOTE: the chapter stopped on the error above", flush=True)
            sys.stdout.flush()
            sys.stderr.flush()
            os._exit(1)

    #: Stage area between the header rule and the caption rule: x-min, x-max, y-min, y-max.
    #: Subtitles are drawn below the lower rule, so staying inside keeps them clear.
    STAGE = (-6.8, 6.8, -2.65, 2.4)
    #: Set on a subclass to pin the lesson directory instead of discovering it.
    lesson_dir = None
    #: Hand-written scenes fail loudly when animation outruns its beat (an authoring
    #: error). Generated scenes record the overrun in the audit and carry on — beats
    #: are timed absolutely, so the next one re-synchronises.
    STRICT_OVERRUN = True

    def _root(self):
        root = os.getenv("LESSONFORGE_LESSON_DIR") or self.lesson_dir
        return Path(root) if root else Path(inspect.getfile(type(self))).resolve().parent

    def chapter(self, n):
        self.root = self._root()
        self.chapter_number = n
        self.timeline = {t["id"]: t for t in json.loads((self.root / "timeline.json").read_text(encoding="utf-8"))}
        self.lesson = json.loads((self.root / "lesson.json").read_text(encoding="utf-8"))
        chapters = self.lesson["chapters"]
        ch = next(c for c in chapters if c["id"] == n)
        self.chapter_start = self.timeline[ch["beats"][0]["id"]]["start"]
        self.records, self.cue_records = [], []
        if os.getenv("LESSONFORGE_LAYOUT_PROBE", "1") != "0":
            from lessonforge import layout_probe
            layout_probe.install()
        title = txt(ch["title"], 34)
        if title.width > 11.7:
            title.scale_to_fit_width(11.7)
        title.move_to([-6.45, 2.94, 0], aligned_edge=LEFT)
        eyebrow = txt((self.lesson.get("eyebrow") or self.lesson["title"]).upper(), 16, TEAL)
        if eyebrow.width > 9.5:
            eyebrow.scale_to_fit_width(9.5)
        eyebrow.move_to([-6.45, 3.53, 0], aligned_edge=LEFT)
        number = txt(f"{n:02} / {len(chapters):02}", 18, MUTED).move_to([6.12, 3.5, 0])
        top_rule = Line([-6.45, 2.45, 0], [6.45, 2.45, 0], color=GRID)
        self.chrome = VGroup(title, eyebrow, number, top_rule,
                             Line([-6.45, -2.7, 0], [6.45, -2.7, 0], color=GRID))
        self.add(self.chrome)
        self.panel = VGroup()
        self._heading, self._heading_small, self._stage = (title, eyebrow, number, top_rule), False, None
        if getattr(self, "staged", False):
            # The stage layout: one small line of heading for the whole chapter and no rules; the frame is the picture's.
            self.small_heading()
            for rule in self.chrome[3:]:
                rule.set_stroke(opacity=0)
            plate = Rectangle(width=config.frame_width + .2, height=.82, stroke_width=0, fill_color=BG, fill_opacity=.72)
            plate.move_to([0, config.frame_height / 2 - .41, 0])
            self.chrome.add_to_back(plate)               # nothing on the dark page; a readable heading over a picture
            self._stage = self._stage_bounds()

    #: The stage once the chapter heading has become one line (``small_heading``): 0.8 units taller.
    TALL_STAGE = (-6.8, 6.8, -2.65, 3.2)

    def small_heading(self):
        """Turn the chapter heading into ONE small line and give its height to the stage.

        The heading used to stay at full size for the whole chapter, above a picture that was limited by
        height: a prepared drawing took about a quarter of the frame, and the owner said it was "not
        being used at the centre … a raw way of using" (2026-10-09). At a chapter's very start the
        heading is simply small; later it shrinks in a third of a second. Returns True when it changed.
        """
        if self._heading_small:
            return False
        title, eyebrow, number, rule = self._heading
        small = title.copy().scale(.5)
        small.next_to(eyebrow, RIGHT, buff=.32)
        room = number.get_left()[0] - .3 - small.get_left()[0]
        if small.width > room > .5:
            small.scale_to_fit_width(room).next_to(eyebrow, RIGHT, buff=.32)
        raised = Line([-6.45, 3.25, 0], [6.45, 3.25, 0], color=GRID)
        if self.renderer.time < .15:
            title.become(small)
            rule.become(raised)
        else:
            self.play(Transform(title, small), Transform(rule, raised), run_time=.35)
        self._heading_small, self._stage = True, self.TALL_STAGE
        return True

    def begin(self, beat_id):
        self.current = self.timeline[str(beat_id).zfill(2) if str(beat_id).isdigit() else str(beat_id)]
        self.beat_start = self.current["start"] - self.chapter_start
        self.until(self.beat_start)
        # Parsed by the build to attribute the probe's per-play findings to a beat.
        print(f"LESSON_BEAT: {self.current['id']} t={self.renderer.time:.3f}", flush=True)

    def until(self, t):
        delta = t - self.renderer.time
        if delta > 1 / config.frame_rate:
            self.wait(round(delta * config.frame_rate) / config.frame_rate)

    def locate(self, phrase, after=0.0):
        """Where ``phrase`` is spoken in the current beat: ``(offset, source)`` or ``None``.

        ``after`` (seconds into the beat) makes the search start there, so steps are
        matched in the order they are shown: "five metres" said in the first sentence
        and again in the last must not pull a LATER step back to the first one (which
        made that step 4.7 s "late" on a demo lesson). The sentence start comes from
        the timeline; the position INSIDE the sentence is the aligned word time when
        the timeline carries one, else a word-count estimate — the source says which.
        """
        return _locate(self.current["sentences"], phrase, after=after)

    def cue(self, phrase, *animations, run_time=1.2, fallback=None, after=0.0):
        """Wait until ``phrase`` is being spoken in the current beat, then play.

        A phrase that is not in the narration is an authoring error and raises —
        unless ``fallback`` (seconds into the beat) is given, which generated scenes
        use so one bad anchor degrades to an even spread instead of killing a chapter.
        ``after``: only match the phrase at or after this many seconds into the beat.
        """
        found = self.locate(phrase, after=after)
        if found is None:
            if fallback is None:
                raise ValueError(f'Cue not found in beat {self.current["id"]}: {phrase}')
            found = (max(fallback, after), "fallback-spread")
        offset, source = found
        # Picture slightly BEFORE the word: a saccade takes ~200 ms and viewers tolerate
        # picture-first far better than audio-first (BT.1359; approaches/03_*). 250 ms
        # lead on aligned anchors; estimates keep their own, larger, error.
        lead = CUE_LEAD if source == "aligned" else 0.0
        target = max(self.beat_start, self.beat_start + offset - lead)
        # ``anchor`` is when the word is SPOKEN; ``target`` is when the picture should start
        # (the anchor minus the lead). Lateness is judged against the anchor.
        self.cue_records.append({"beat": self.current["id"], "phrase": phrase, "target": target,
                                 "anchor": self.beat_start + offset,
                                 "actual_before_wait": self.renderer.time, "timing_source": source})
        self.until(target)
        ready = []
        for animation in animations:
            ready += list(animation.make() or []) if isinstance(animation, Later) else [animation]
        if ready:
            self.play(*ready, run_time=run_time)

    def panel_to(self, *items):
        new = VGroup(*items).arrange(DOWN, buff=.4, aligned_edge=LEFT)
        fit(new, 5.15, 4.3, (3.7, -.05, 0))
        old = self.panel
        self.panel = new
        # Remove old writing before revealing new writing; crossfading both creates
        # a brief but unreadable overlap even when endpoint layouts are correct.
        return Succession(FadeOut(old), FadeIn(new))

    def finish(self):
        target = self.beat_start + self.current["duration"]
        overrun = self.renderer.time - target
        if overrun > .05 and self.STRICT_OVERRUN:
            raise ValueError(f'Beat overrun {self.current["id"]}: {overrun}')
        self.until(target)
        self.still("end", **(self.__dict__.get("_measured") or {}))
        x0, x1, y0, y1 = getattr(self, "_stage", None) or self.STAGE
        violations = []
        for m in self.mobjects:
            if m is self.chrome or getattr(m, "bleeds", False):
                continue
            try:
                if m.width < .001 and m.height < .001:
                    continue
                box = [float(m.get_left()[0]), float(m.get_right()[0]), float(m.get_bottom()[1]), float(m.get_top()[1])]
            except Exception as exc:  # noqa: BLE001
                # A mobject that cannot be MEASURED (a model-written scene left one with a malformed point
                # array) is reported, not allowed to end the chapter: on 2026-10-09 this check itself raised
                # on such a shape and a whole lesson was lost at its last chapter.
                print(f"LESSON_NOTE: a {type(m).__name__} could not be measured at the end of beat "
                      f"{self.current['id']} ({type(exc).__name__}: {str(exc)[:80]})", flush=True)
                violations.append({"type": type(m).__name__, "bbox": None, "unmeasurable": True})
                continue
            if box[0] < x0 or box[1] > x1 or box[2] < y0 or box[3] > y1:
                violations.append({"type": type(m).__name__, "bbox": box})
        self.records.append({"beat": self.current["id"], "time": self.renderer.time,
                             "overrun": round(max(0.0, overrun), 3), "bounds_violations": violations,
                             **({"layout": self._beat_layout} if getattr(self, "_beat_layout", None) else {})})

    def still(self, what, **said):
        """Save the screen as it stands, when stills are asked for (``STILLS``); ``said`` goes into the still's record."""
        if not STILLS:
            return
        try:
            folder = Path(STILLS)
            folder.mkdir(parents=True, exist_ok=True)
            taken = self.__dict__.setdefault("_stills", [])
            name = f"c{self.chapter_number:02}_b{self.current['id']}_{len(taken):03}_{what}.jpg"
            self.renderer.static_image = None            # the whole screen, not only what moved in the last animation
            self.renderer.update_frame(self)
            self.renderer.camera.get_image().convert("RGB").save(folder / name, quality=88)
            taken.append({"file": name, "chapter": self.chapter_number, "beat": self.current["id"], "what": what,
                          "time": round(float(self.renderer.time), 3), **said})
        except Exception as exc:  # noqa: BLE001 - a preview that cannot be saved must not end the chapter
            print(f"LESSON_NOTE: a still could not be saved ({type(exc).__name__}: {str(exc)[:100]})", flush=True)

    def done(self):
        out = self.root / "output"
        out.mkdir(exist_ok=True)
        (out / f"chapter_{self.chapter_number:02}_audit.json").write_text(
            json.dumps({"bounds": self.records, "cues": self.cue_records}, indent=2), encoding="utf-8")
        if STILLS:
            (Path(STILLS) / f"stills_c{self.chapter_number:02}.json").write_text(
                json.dumps(self.__dict__.get("_stills", []), indent=1, ensure_ascii=False), encoding="utf-8")


class AutoChapter(LessonScene):
    """Animatic for a chapter that has no hand-written scene yet.

    Plays the real narration timing with the beat's board text and equation on the
    right and its ``visual`` direction as a placeholder card on the left. It exists so
    a script can be heard, read and reviewed end to end — captions, chapters and
    pacing included — BEFORE anyone writes or generates scene code for it.
    """
    chapter_id = None
    STRICT_OVERRUN = False

    def construct(self):
        self.chapter(self.chapter_id)
        ch = next(c for c in self.lesson["chapters"] if c["id"] == self.chapter_id)
        card = VGroup()
        for beat in ch["beats"]:
            self.begin(beat["id"])
            new_card = fit(wrapped(beat.get("visual") or beat.get("check") or ""), 6.2, 4.2, (-3.3, -.1, 0))
            items = []
            if beat.get("board_text"):
                items.append(wrapped(beat["board_text"], 26, 30, INK))
            if beat.get("equation"):
                items.append(safe_eq(beat["equation"]))
            animations = [Succession(FadeOut(card), FadeIn(new_card))]
            if items:
                animations.append(self.panel_to(*items))
            opening = " ".join(self.current["sentences"][0]["text"].split()[:3])
            self.cue(opening, *animations, run_time=1.0)
            card = new_card
            self.finish()
        self.done()


class GuidedChapter(LessonScene):
    """A whole chapter rendered from data: no scene code, synced, laid out and ANIMATED by construction.

    Each beat carries ``steps`` — what appears, and the spoken phrase it belongs to:

        {"say": "three metres north", "show": "North leg: 3 m", "kind": "point", "focus": "b"}
        {"say": "squaring", "show": "4^2 + 3^2 = c^2", "kind": "math", "highlight": true}

    Structural, not hoped for:

    * **Sync** — every step waits for its phrase in the measured narration; a phrase
      that cannot be found falls back to an even spread (and the audit says so).
    * **No collisions** — figure left, wording and mathematics right, each laid out
      ONCE with every step already in place; steps are revealed into slots they own.
    * **Attention follows the voice** — the step being spoken is at full strength,
      earlier steps recede, the key step is boxed.

    And, since the first user review ("the dynamics are very minimal"), motion that
    carries meaning rather than decoration:

    * a figure is DRAWN — outline, fills, labels — in the beat's lead-in, and morphs
      into the next figure of the same kind instead of blinking out and in;
    * a step with a ``focus`` makes that part of the figure pulse, and a formula step
      takes its number from the figure's label (the value travels into the formula);
    * each formula line grows out of the line before it;
    * a thinking pause is an on-screen question card with answer options and a
      countdown, and the right option lights up before the lesson goes on.

    Kinds: ``point`` (a line of wording), ``key`` (the idea to keep, written in),
    ``math`` (LaTeX). ``LESSONFORGE_COMPACT=1`` re-lays everything smaller.
    """
    chapter_id = None
    STRICT_OVERRUN = False
    # Non-focus steps dim to ~0.35 (cueing meta-analyses: one evoked cue, the rest
    # dimmed — docs/research/approaches/03_sync_and_highlighting.md).
    RECEDE = 0.35
    #: The picture's box and the steps' column (width, height, centre), both inside STAGE. Until 2026-10-09
    #: a picture was only ever SHRUNK into a 6.0 by 4.2 box: a scene whose content was smaller than its
    #: canvas sat in a corner at a quarter of the frame, under 26-point steps, and a tester on a phone
    #: called the composition bad. Now it is enlarged to fill its box and the type is a size up.
    PICTURE_BOX = (7.4, 4.6, (-2.95, -.125, 0))
    STEPS_BOX = (5.3, 4.6, (3.95, -.125, 0))
    #: A prepared drawing (``diagram``, ``picture``) on the TALL stage: it takes the stage's whole height at
    #: the left and its steps a narrow column beside it. Beside, not under: the frame is 16:9 and the band
    #: for subtitles is kept free, so a 3:2 drawing is limited by HEIGHT, and a caption row under it would
    #: cost exactly the height the small heading gave back. About 8.5 by 5.7 for a 3:2 drawing: 43% of the
    #: frame, where it had about a quarter.
    DRAWING_BOX = (8.85, 5.7, (-2.33, .275, 0))
    DRAWING_STEPS = (4.3, 5.3, (4.62, .275, 0))
    DRAWN_FOR_YOU = ("diagram", "picture")

    #: "stage" (2026-10-10, the owner: "one side image and another side text … is not giving good look"): the picture
    #: takes what the frame can give it and the words take what is left, ONE line at a time, beside the picture or
    #: above it, whichever leaves the picture larger. "columns": picture left and a column of steps right, as every
    #: lesson was laid out before. Which one is the LESSON's own (``look.py``), not this process's.
    LAYOUT = LOOK["frame"]
    #: The band at the foot of the frame that a browser draws captions over. Not kept when the player shows captions
    #: outside the picture (the app does, under the video): the picture then has nearly the frame's whole height.
    CAPTION_BAND = LOOK["captions"] == "band"
    #: The column for one line of words beside a picture, the wider one for working that grows line by line, the
    #: strip for one line above a wide picture, and the gap: ``look.py`` has them, because whoever prepares a
    #: picture must fit it to the same boxes (``look.picture_boxes``).
    WORDS, BOARD, LINE, GAP = _look.WORDS, _look.BOARD, _look.LINE, _look.GAP

    @property
    def staged(self):
        return self.LAYOUT == "stage"

    def _stage_bounds(self):
        """The stage the bounds check holds the chapter to: under the one-line heading, above the captions' band."""
        return _look.stage_bounds({"captions": "band" if self.CAPTION_BAND else "outside"})

    def _stage_box(self):
        """(x0, x1, y0, y1) the picture and its words are laid out in: the stage, less a margin."""
        return _look.stage_box({"captions": "band" if self.CAPTION_BAND else "outside"})

    def _natural(self, figure):
        """A picture's own width and height, before the frame has sized it (a scene: all it will show while it moves)."""
        if getattr(figure, "_natural", None) is None:
            if getattr(figure, "animator", None) is not None and getattr(figure, "origin", None) is not None:
                # Measured ONCE and kept: a model-written scene stepped a second time does not always show what it
                # showed the first time (one came back with no width at all and was placed 33,000 units off the frame).
                figure._swept = x0, x1, y0, y1 = swept_box(figure.origin, figure.animator)
                figure._natural = (max(x1 - x0, .01), max(y1 - y0, .01))
            else:
                body = figure.art if getattr(figure, "bleeds", False) else figure      # a full-frame picture: its art, not its marks
                figure._natural = (max(body.width, .01), max(body.height, .01))
        return figure._natural

    #: Whether a picture drawn by code is enlarged to the room the frame has for it (``look.py``: ``pictures``).
    FILL = LOOK["pictures"] == "fill"
    #: Whether working stays while the words beside it come one at a time (``look.py``: ``working``).
    PINNED = LOOK["working"] == "pinned"
    #: Whether a prepared drawing that is shown whole is DRAWN part by part when it arrives (``look.py``: ``drawings``).
    PAINTED = LOOK["drawings"] == "painted"
    #: Whether a chapter opens on the screen the chapter before left (``look.py``: ``joins``). Only the stage frame.
    JOINS = LOOK["joins"] == "carried"
    #: Whether the number beside an angle's arc waits for the word that says it (``look.py``: ``values``; video-quality plan S3).
    VALUES_SPOKEN = LOOK["values"] == "spoken"
    #: Whether a finished graph, table or verdict is drawn in at the step whose words bring it (``look.py``: ``staging``; S5).
    STAGED = LOOK["staging"] == "steps"
    #: Whether the lesson has a title card and a closing hold, pictures that cross-fade and a clean thinking pause
    #: (``look.py``: ``craft``; S11).
    CRAFTED = LOOK["craft"] == "crafted"

    def _most(self, figure, compact=False):
        """How far a picture may be enlarged: a drawing's print coarsens; what code draws does not, and with ``FILL``
        it is given the room there is (a scene drawn two units wide stood two and a half units wide in a stage of thirteen)."""
        if getattr(figure, "kind", "") in self.DRAWN_FOR_YOU:
            return 1.6
        if compact:
            return 1.0
        if self.FILL:
            return 3.2
        # a moving ``shape`` is drawn by code like a still one: it keeps the still one's size (the first test film
        # showed the tipping point at 0.6 of the size of the same quadrilateral a beat before)
        moving = getattr(figure, "animator", None) is not None and getattr(figure, "kind", "") != "shape"
        return 1.7 if moving else 2.2

    @staticmethod
    def _run_key(figure):
        """What makes two beats show 'the same picture' for the place it is given. Normally the figure itself; the figures of
        a run of beats on one library component that share a ``span`` (``kits/components.py``, video-quality plan S6) are
        one picture in different states, drawn on one card, so they are one run."""
        if not figure:
            return None
        inner = figure.get("params") if isinstance(figure.get("params"), dict) else figure
        if figure.get("kind") == "component" and inner.get("span"):
            return "span:" + json.dumps([inner.get("id") or inner.get("component"), inner["span"]], sort_keys=True)
        return json.dumps(figure, sort_keys=True)

    def _run_board(self, beat):
        """Whether any beat that shows the picture this beat shows works in formula lines.

        A picture stays up until another replaces it, through beats and through chapters; its place in the frame is
        chosen once for all of them, so it does not jump when one beat of the run brings a formula.
        """
        order = [b for c in self.lesson["chapters"] for b in c["beats"]]
        keys, last = [], None
        for b in order:
            last = self._run_key(b["figure"]) if b.get("figure") else last
            keys.append(last)
        at = next((i for i, b in enumerate(order) if b is beat or b.get("id") == beat.get("id")), 0)
        run = [b for b, k in zip(order, keys) if k == keys[at]] if keys[at] is not None else [order[at]]
        return any(s.get("kind") == "math" and str(s.get("show", "")).strip() for b in run for s in b.get("steps") or [])

    def _working(self, beat):
        """Whether THIS chapter works in formula lines on the picture this beat shows.

        The picture's place is one for the whole run (``_run_board``); how the words beside it are shown is the
        chapter's own. One formula in one chapter had made a seven-chapter lesson a column of small lines throughout.
        """
        chapter = next((c for c in self.lesson["chapters"] if any(b is beat or b.get("id") == beat.get("id") for b in c["beats"])), None)
        if chapter is None:
            return self._run_board(beat)
        key = lambda b: self._run_key(b["figure"]) if b.get("figure") else None      # noqa: E731
        mine = key(beat)
        return any(s.get("kind") == "math" and str(s.get("show", "")).strip()
                   for b in chapter["beats"] if key(b) == mine or mine is None for s in b.get("steps") or [])

    def _stage_plan(self, figure, board, compact=False):
        """Where the picture and the words go: ``{"mode": "side" | "top" | "words", "picture": box, "words": box}``.

        Worked out, not chosen by taste: the picture is scaled to the larger of the two sizes it can have, with a
        column of words beside it or a strip of words above it. A 3:2 drawing is limited by the frame's height and
        leaves room at its side; a before-and-after pair is limited by width and leaves room above. Working in
        formula lines needs a column, so it is always beside. Picture and words together sit in the middle of the frame.
        """
        x0, x1, y0, y1 = self._stage_box()
        W, H, cx, cy = x1 - x0, y1 - y0, (x0 + x1) / 2, (y0 + y1) / 2
        if figure is None:
            return {"mode": "words", "words": (min(W, 11.6), H - .2, (cx, cy, 0))}
        pw, ph = self._natural(figure)
        if getattr(figure, "bleeds", False) and not board:
            scale = max(config.frame_width / pw, config.frame_height / ph)       # cover the frame; what does not fit is cut
            return {"mode": "bleed", "picture": (pw * scale, ph * scale, (0, 0, 0)), "words": (W - 1.2, self.LINE, (cx, y0 + .2 + self.LINE / 2, 0))}
        most = self._most(figure, compact)
        ww = self.BOARD if board else self.WORDS
        side = min(most, (W - ww - self.GAP) / pw, H / ph)
        top = min(most, W / pw, (H - self.LINE - self.GAP) / ph)
        if getattr(figure, "animator", None) is not None and not self.FILL and getattr(figure, "kind", "") != "shape":
            was = min(self.PICTURE_BOX[0] / pw, self.PICTURE_BOX[1] / ph)
            side, top = min(side, was), min(top, was)
        beside = side > top * 1.02 or (side >= top * .98 and pw / ph < 2.0)     # equal sizes: a wide picture is captioned above
        if board or beside:
            w, h = pw * side, ph * side
            left = cx - (w + self.GAP + ww) / 2
            return {"mode": "side", "picture": (w, h, (left + w / 2, cy, 0)), "words": (ww, H, (left + w + self.GAP + ww / 2, cy, 0))}
        w, h = pw * top, ph * top
        base = cy - (h + self.GAP + self.LINE) / 2
        return {"mode": "top", "picture": (w, h, (cx, base + h / 2, 0)), "words": (W, self.LINE, (cx, base + h + self.GAP + self.LINE / 2, 0))}

    def _lines(self, show, width, size, colour):
        """A step's wording wrapped to a width in units (Lato sets about 0.006 units a character a point)."""
        chars = max(9, int(width / (size * .00597)))
        mob = wrapped(screen_words(show), chars, size, colour, line_gap=.2)
        while mob.width > width and chars > 9:
            chars -= 2
            mob = wrapped(screen_words(show), chars, size, colour, line_gap=.2)
        if mob.width > width:
            mob.scale_to_fit_width(width)
        return mob

    def _measure(self, steps, figure, plan=None):
        """What can be read off a beat's layout without looking at it: how much of the frame the picture has, how much
        of the room it was given it spans (``fill``: 1.0 when it reaches the room's width or height), and the real
        size of every line of words (a line that was shrunk to fit says the size it ended at)."""
        frame = config.frame_width * config.frame_height
        lines = []
        for step in steps:
            mob = step.get("_mob")
            if mob is None:
                continue
            sizes = type_points(mob)
            lines.append({"kind": step.get("kind", "point"), "show": str(step.get("show", ""))[:90],
                          "points": min(sizes) if sizes else None, "page": step.get("_page", 0),
                          "box": [round(float(v), 3) for v in (mob.get_left()[0], mob.get_right()[0], mob.get_bottom()[1], mob.get_top()[1])]})
        picture = None
        if figure is not None:
            kind = getattr(figure, "kind", "") or ("scene" if getattr(figure, "animator", None) is not None else "figure")
            body = getattr(figure, "art", None) if kind in self.DRAWN_FOR_YOU else None
            body = figure if body is None else body
            inner = type_points(figure)
            picture = {"kind": kind, "width": round(float(body.width), 3), "height": round(float(body.height), 3),
                       "share": round(float(body.width * body.height) / frame, 4), "type_points": min(inner) if inner else None}
            if plan and plan.get("mode") in ("side", "top"):
                x0, x1, y0, y1 = self._stage_box()
                ww = plan["words"][0]
                room = (x1 - x0 - ww - self.GAP, y1 - y0) if plan["mode"] == "side" else (x1 - x0, y1 - y0 - self.LINE - self.GAP)
                picture["fill"] = round(max(float(body.width) / room[0], float(body.height) / room[1]), 3)
        return {"lines": lines, "picture": picture}

    def _staged(self, steps, figure, beat):
        """Lay one beat out on the stage. Returns the plan (kept on the picture: it stays where it was first put)."""
        compact = os.getenv("LESSONFORGE_COMPACT", "0") == "1"
        board = self._run_board(beat)
        plan = getattr(figure, "_plan", None) if figure is not None else None
        if plan is None:
            plan = self._stage_plan(figure, board, compact)
            if figure is not None:
                w, h, centre = plan["picture"]
                if getattr(figure, "animator", None) is not None and getattr(figure, "origin", None) is not None:
                    place_scene(figure, w, h, centre, most=self._most(figure, compact), swept=getattr(figure, "_swept", None),
                                strokes=self.FILL)
                    figure._placed = True
                elif plan["mode"] == "bleed":
                    figure.scale(w / max(figure.art.width, 1e-6))
                    figure.shift(np.array(centre, dtype=float) - figure.art.get_center())
                    # a mark may not reach into the heading's line: the sun in a top corner is outlined below it
                    top = self._stage_bounds()[3] - .12
                    for mark in figure.marks.values():
                        over = mark.get_top()[1] - top
                        if over > 0 and mark.height - over > .3:
                            mark.stretch_to_fit_height(mark.height - over, about_edge=DOWN)
                else:
                    by = min(w / max(figure.width, 1e-6), h / max(figure.height, 1e-6))
                    figure.scale(by).move_to(centre)
                    if self.FILL and getattr(figure, "kind", "") not in self.DRAWN_FOR_YOU:
                        scale_strokes(figure, by)
                figure._plan = plan
        ww, wh, centre = plan["words"]
        # One line at a time while a picture is being looked at. Not for working that grows line by line, and not for a
        # recap beside its picture: what a recap lists is meant to stand together.
        chapter = next((c for c in self.lesson["chapters"] if any(b is beat or b.get("id") == beat.get("id") for b in c["beats"])), {})
        listed = plan["mode"] == "side" and chapter.get("role") == "recap"
        # A strip above a wide picture, or on one, has room for ONE line: working is shown there line by line too. (A beat
        # with no picture of its own, under a wide scene, in a chapter that works something out later, had its three
        # lines fitted into the strip as a column of 15-point type.)
        strip = plan["mode"] in ("top", "bleed")
        working = (self._working(beat) and not strip) if plan["mode"] != "words" else board
        caption = plan["mode"] != "words" and not working and not listed
        # Working beside a picture (``PINNED``): only the WORKING stays. A beat of such a chapter that works nothing out
        # itself shows its lines one at a time like any other; one that does keeps its formula lines and shows its
        # words one at a time above them. Before, every line of both piled up in one column of 30-point type.
        pinned = False
        if self.PINNED and working and not listed and plan["mode"] == "side":
            pinned = any(s.get("kind") == "math" for s in steps)
            caption = not pinned
        plan = {**plan, "caption": caption, "board": working and not caption, "pinned": pinned}
        # A line that stands alone is set for a phone held upright, where the frame is about 200 points high: type of
        # 6% of the frame's height or more (44 here is 6.9%), and a line across the frame of about 42 characters. A list
        # and a column of working keep the smaller sizes: they are several lines that have to fit together.
        wide = plan["mode"] in ("top", "bleed")
        text_size, key_size, math_size = ((32, 34, 34) if compact else (48, 48, 48) if wide else (44, 46, 44)) if caption else \
            ((30, 32, 34) if compact else (40, 42, 44)) if pinned else \
            ((22, 26, 34) if compact else (30, 34, 44)) if plan["mode"] != "words" else ((28, 30, 38) if compact else (38, 42, 50))
        mobs = []
        for step in steps:
            kind, show = step.get("kind", "point"), str(step.get("show", "")).strip()
            if plan["mode"] == "bleed" and kind != "math":
                # words that lie on a picture stand on a plate of the page's colour (the layout check knows such a label)
                mob = self._lines(show, ww * .92, key_size if kind == "key" else text_size, GOLD if kind == "key" else INK)
                mob.add_background_rectangle(color=BG, opacity=.82, buff=.24)
            elif kind == "math":
                mob = safe_eq(show, math_size)
                rows = (math_rows(show) or (relation_rows(show) if mob.width > ww * 1.45 else [])) if mob.width > ww * 1.2 else []
                if rows:
                    mob = VGroup(*[safe_eq(r, math_size) for r in rows]).arrange(DOWN, aligned_edge=LEFT, buff=.24)
                if mob.width > ww:
                    mob.scale_to_fit_width(ww)
            else:
                mob = self._lines(show, ww * (.94 if plan["mode"] == "top" else 1.0), key_size if kind == "key" else text_size,
                                  GOLD if kind == "key" else INK)
            step["_mob"] = mob
            mobs.append(mob)
        if caption:
            for mob in mobs:                                         # every line owns the same place: it is there alone
                if mob.height > wh - .1:
                    mob.scale_to_fit_height(wh - .1)
                if plan["mode"] in ("top", "bleed"):
                    mob.move_to(centre)
                else:
                    mob.move_to([centre[0] - ww / 2, centre[1] + .25, 0], aligned_edge=LEFT)
        elif pinned:
            self._pin(steps, ww, wh, centre)
        elif mobs:
            column = VGroup(*mobs).arrange(DOWN, aligned_edge=LEFT, buff=.5 if plan["mode"] != "words" else .55)
            fit(column, ww, wh - .2, centre)
            if plan["mode"] == "side":
                column.move_to([centre[0] - ww / 2, centre[1], 0], aligned_edge=LEFT)
        return plan

    def _pin(self, steps, width, height, centre, gap=.45):
        """Place a beat that works something out: ONE line of words at the head of the column, the working under it.

        Every line of words owns the same place and is there alone; every line of working owns a place under it and
        stays. Working that does not fit under the words at its full size is not shrunk: it goes on to another
        SCREEN (``_page``), and the screen before leaves when its first line comes. Only a single line taller than the
        whole room is made smaller. Marks each step ``_pinned`` (it stays) and with its ``_page``.
        """
        left = centre[0] - width / 2
        words = [s for s in steps if s.get("kind") != "math"]
        working = [s for s in steps if s.get("kind") == "math"]
        head = min(2.7, max((s["_mob"].height for s in words), default=0.0))
        for step in words:
            if step["_mob"].height > head:
                step["_mob"].scale_to_fit_height(head)
        under = (head + gap) if words else 0.0
        room = max(1.0, height - .2 - under)
        pages, page, used = [], [], 0.0
        for step in working:
            mob = step["_mob"]
            if mob.height > room:
                mob.scale_to_fit_height(room)
            need = mob.height + (gap if page else 0.0)
            if page and used + need > room:
                pages.append(page)
                page, used, need = [], 0.0, mob.height
            page.append(step)
            used += need
        if page:
            pages.append(page)
        tallest = max((sum(s["_mob"].height for s in p) + gap * (len(p) - 1) for p in pages), default=0.0)
        top = centre[1] + (under + tallest) / 2
        for step in words:                               # each stands on the working it is about: a short line is not left
            step["_mob"].move_to([left, top - head, 0], aligned_edge=DL)       # hanging a line's height above it
            step["_pinned"], step["_page"] = False, 0
        for number, page in enumerate(pages):
            y = top - under
            for step in page:
                step["_mob"].move_to([left, y, 0], aligned_edge=UL)
                y -= step["_mob"].height + gap
                step["_pinned"], step["_page"] = True, number

    def _columns(self, steps, figure=None):
        """Lay the beat out once. With a figure: figure left, words and maths stacked right."""
        compact = os.getenv("LESSONFORGE_COMPACT", "0") == "1"
        text_size, key_size, math_size, wrap, key_wrap = (22, 26, 34, 38, 38) if compact else (30, 34, 44, 27, 24)
        has_math = any(s.get("kind") == "math" for s in steps)
        beside = has_math or figure is not None          # the wording shares the frame with a picture or a formula
        # A labelled diagram, or a finished picture shown whole, carries its own words and needs the
        # room: it gets the wider box and the steps a narrower column.
        wide = getattr(figure, "kind", "") in self.DRAWN_FOR_YOU
        roomy = figure is not None and not wide and not compact
        room = self.STEPS_BOX[0] if roomy else (self.DRAWING_STEPS[0] if wide else 5.6) if figure is not None else 5.0
        left, right = [], []
        for step in steps:
            kind, show = step.get("kind", "point"), str(step.get("show", "")).strip()
            if kind == "math":
                mob = safe_eq(show, math_size)
                # A list too long for the column is written on two lines at full size before it is shrunk.
                rows = math_rows(show) if mob.width > room * 1.2 else []
                if rows:
                    mob = VGroup(*[safe_eq(r, math_size) for r in rows]).arrange(DOWN, aligned_edge=LEFT, buff=.24)
                (right if beside else left).append(mob)
            elif kind == "key":
                mob = wrapped(screen_words(show), key_wrap if beside else key_wrap + 22, key_size, GOLD)
                (right if figure is not None else left).append(mob)
            else:
                mob = wrapped(screen_words(show), wrap if beside else wrap + 22, text_size, INK)
                (right if figure is not None else left).append(mob)
            step["_mob"] = mob
        if figure is not None:
            if wide:
                fill(figure, *self.DRAWING_BOX, most=1.6)         # inside TALL_STAGE: construct made the heading small
            elif getattr(figure, "animator", None) is not None and getattr(figure, "origin", None) is not None:
                if not getattr(figure, "_placed", False):       # once: a later beat finds it where it was put
                    place_scene(figure, *((6.0, 4.2, (-3.3, -.1, 0)) if compact else self.PICTURE_BOX),
                                most=1.0 if compact else 1.7)
                    figure._placed = True
            elif compact:
                fit(figure, 6.0, 4.2, (-3.3, -.1, 0))
            else:
                fill(figure, *self.PICTURE_BOX)
        if left:
            column = VGroup(*left).arrange(DOWN, aligned_edge=LEFT, buff=.42)
            fit(column, 6.0 if has_math else 11.6, 4.2, (-3.3 if has_math else 0, -.1, 0))
        if right:
            for mob in right:
                # One long line is narrowed by itself. Fitting the whole column to it made every line small
                # ("17^2 = 289, 18^2 = 324, …" shrank the three lines above it too).
                if mob.width > room:
                    mob.scale_to_fit_width(room)
            column = VGroup(*right).arrange(DOWN, aligned_edge=LEFT, buff=.5)
            fit(column, room, self.STEPS_BOX[1] if roomy else (self.DRAWING_STEPS[1] if wide else 4.2),
                self.STEPS_BOX[2] if roomy else (self.DRAWING_STEPS[2] if wide else (3.75, -.1, 0)))

    def _entrance(self, step, mob, figure, previous_math):
        """How a step arrives. Returns ``(entrance, extra animations)``."""
        parts = getattr(figure, "parts", None) or {}
        focus = str(step.get("focus") or "")
        part, label = parts.get(focus), parts.get(focus + "_label")
        if hasattr(figure, "focus_animations"):
            # Picture layers are images: Indicate would repaint one flat. The figure says what a focus does.
            extra, label = ([Later(lambda: figure.focus_animations(focus))] if focus else []), None
        else:
            extra = [Indicate(part, color=GOLD, scale_factor=1.12)] if part is not None else []
        kind = step.get("kind", "point")
        # The unknown is FOUND: a line of working that ends "= 16" on a part still marked "?" puts 16 where the
        # "?" was, and a counted grid fills as it does. (The "?" used to stay on the picture through "four
        # into four equals sixteen" and to the end of the beat.)
        value = found_value(step.get("show", "")) if kind == "math" and label is not None else ""
        if value and str(getattr(label, "text", "")).strip() == "?":
            found = Text(value, font=FONT, font_size=40, color=GOLD)
            found.scale_to_fit_height(max(.34, label.height * (.8 if hasattr(label, "background_rectangle") else 1.0)))
            if found.width > (part.width * .8 if part is not None else 3.0):
                found.scale_to_fit_width(part.width * .8 if part is not None else 3.0)
            found.move_to(label.get_center())
            if hasattr(label, "background_rectangle"):
                found.add_background_rectangle(color=BG, opacity=.85, buff=.1)
            cells = getattr(figure, "cells", None) if focus == "area" else None
            if cells is not None and len(cells):
                extra.append(LaggedStart(*[c.animate.set_fill(GOLD, opacity=.3) for c in cells], lag_ratio=.12))
            extra.append(Transform(label, found))
            label.text, label = value, None        # it is no longer a "?", and nothing travels out of it
        try:
            # A COPY travels and is replaced by the line itself. ``TransformFromCopy(source, line)`` transforms the line,
            # and a Transform pads the mobject it changes with copies of its own parts until its family matches the
            # other's: a two-row formula came out holding three "Total distance" rows on top of each other, which the
            # layout probe counted as text on text and failed the lesson (speed and velocity, 2026-10-20).
            if kind == "math" and label is not None:
                return ReplacementTransform(label.copy(), mob), extra       # the value leaves the picture for the formula
            if kind == "math" and previous_math is not None:
                return ReplacementTransform(previous_math.copy(), mob), extra   # the next line grows out of the last
            if kind == "key":
                return Write(mob), extra
        except Exception:  # noqa: BLE001 - never lose a step to its entrance
            pass
        return FadeIn(mob, shift=UP * .15), extra

    def _title_card(self, seconds):
        """The lesson's title over the page for ``seconds`` (S11): in, held, out, in the lead of the lesson's first beat. It covers the
        chapter heading and the page; the picture is drawn after it, in the lead that is left."""
        title = txt(str(self.lesson.get("title") or "").strip() or "Lesson", 54, INK)
        if title.width > 11.5:
            title.scale_to_fit_width(11.5)
        parts = [title]
        thesis = str(self.lesson.get("thesis") or "").strip()
        if thesis and len(thesis) <= 140:
            parts.append(wrapped(thesis, 60, 28, MUTED))
        body = VGroup(*parts).arrange(DOWN, buff=.45).move_to([0, .15, 0])
        plate = Rectangle(width=config.frame_width + .2, height=config.frame_height + .2, stroke_width=0, fill_color=BG, fill_opacity=1)
        card = VGroup(plate, body)
        fade = min(.4, seconds / 5)
        self.play(FadeIn(card), run_time=fade)
        self.wait(max(0.0, round((seconds - 2 * fade) * config.frame_rate) / config.frame_rate))
        self.play(FadeOut(card), run_time=fade)

    def _quiz_card(self, quiz, with_figure, narrow=False):
        """The on-screen question for a thinking pause: the prompt and a countdown.

        The answers are NOT drawn into the video unless ``LESSONFORGE_QUIZ_IN_VIDEO=options``.
        Drawn as boxes they looked like buttons nobody could press, and the right one lit
        up by itself: a tester (2026-10-08) said the questions were "inside the video
        itself … we couldn't answer". Answering belongs to the player, which stops here
        and takes the tap; the video only asks, and gives time to think.
        """
        width, centre, wrap_at = (5.6, (3.75, -.1, 0), 30) if with_figure else (9.0, (0, -.1, 0), 50)
        if narrow:                                   # beside a prepared drawing, in its steps' column
            width, centre, wrap_at = self.DRAWING_STEPS[0], self.DRAWING_STEPS[2], 22
        plan = getattr(self, "_plan_now", None)
        if plan is not None:                         # the stage layout: the question takes the words' place
            ww, wh, centre = plan["words"]
            if plan["mode"] in ("top", "bleed"):     # a strip above a wide picture, or on one: the question and its countdown, no more
                question = self._lines(str(quiz.get("question") or "Your turn: think about your answer"), ww * .9, 36, INK)
                timer = Rectangle(width=min(ww * .5, 5.2), height=.07, stroke_width=0, fill_color=GOLD, fill_opacity=1)
                extra = []
                if self.CRAFTED:          # the choices as words, and what the bar is counting (S11)
                    choices = [f"{'ABCD'[k]}. {text}" for k, text in enumerate((quiz.get("options") or [])[:4])]
                    if choices:
                        extra.append(self._lines("    ".join(choices), ww * .9, 28, MUTED))
                    extra.append(txt("Time to think", 20, MUTED))
                card = VGroup(question, *extra, timer).arrange(DOWN, buff=.2)
                fit(card, ww * .94, wh, centre)
                if plan["mode"] == "bleed":
                    card.add_background_rectangle(color=BG, opacity=.82, buff=.24)
                return card, [], timer
            width, wrap_at = (ww, max(12, int(ww / (30 * .00597)))) if plan["mode"] == "side" else (9.6, 44)
        head = txt("YOUR TURN", 20, GOLD)
        asked = str(quiz.get("question") or "").strip()
        question = [wrapped(asked, wrap_at, 30, INK)] if asked else []
        options = []
        if QUIZ_IN_VIDEO == "options":
            for k, text in enumerate(quiz.get("options") or []):
                line = wrapped(f"{'ABCD'[k]}.  {text}", wrap_at - 4, 24, INK)
                options.append(VGroup(SurroundingRectangle(line, color=MUTED, buff=.14, corner_radius=.1, stroke_width=2), line))
        prompt = [] if options else [txt("Think about your answer", 20, MUTED)]
        if self.CRAFTED and not options and quiz.get("options"):
            # the choices as words (no boxes, nothing lights up: the answer comes in the next beat), so a question that asks
            # for one of them is not asking for something never shown (S11)
            question += [wrapped(f"{'ABCD'[k]}.  {text}", wrap_at - 4, 24, INK) for k, text in enumerate((quiz.get("options") or [])[:4])]
        timer = Rectangle(width=min(width, 5.2), height=.07, stroke_width=0, fill_color=GOLD, fill_opacity=1)
        card = VGroup(head, *question, *options, *prompt, timer).arrange(DOWN, aligned_edge=LEFT, buff=.3)
        fit(card, width, 4.2, centre)
        if plan is not None and plan["mode"] == "side":
            card.move_to([centre[0] - width / 2, centre[1] + .1, 0], aligned_edge=LEFT)
        return card, options, timer

    def _pause(self, beat, step_mobs, figure):
        """A thinking pause the viewer can SEE: the question and a countdown (the answer comes in the next beat)."""
        end = self.beat_start + self.current["duration"]
        self.until(self.beat_start + self.current["speech_end"] + .1)
        available = end - self.renderer.time - .05
        if available < 2.6:
            return False
        quiz = beat.get("quiz") or {}
        if not str(quiz.get("question") or "").strip():
            # A pause with no card of its own shows the beat's own LINE for the screen, never the sentence being
            # spoken: 70 of 211 pauses in 46 lessons put the narration's last sentence on the card, word for word
            # (the owner, 2026-10-12: "the question has the narration thing").
            quiz = {**quiz, "question": screen_question(beat)}
        card, options, timer = self._quiz_card(quiz, figure is not None,
                                               narrow=getattr(figure, "kind", "") in self.DRAWN_FOR_YOU)
        hidden = VGroup(*step_mobs)
        crafted = self.CRAFTED
        if crafted and len(hidden):
            # the steps leave first, then the card comes: the two together drew the question over the words it hid (S11)
            self.play(FadeOut(hidden), run_time=.3)
            available -= .3
            self.play(FadeIn(card, shift=UP * .15), run_time=.4)
        else:
            self.play(FadeIn(card, shift=UP * .15), *([FadeOut(hidden)] if len(hidden) else []), run_time=.4)
        self.still("pause")
        answer = quiz.get("answer_index")
        has_answer = isinstance(answer, int) and 0 <= answer < len(options)
        reveal = .9 if has_answer else 0.0
        self.play(timer.animate.stretch(.001, 0, about_edge=LEFT), rate_func=linear,
                  run_time=max(.6, available - .4 - reveal - .45))
        if has_answer:
            right = options[answer]
            self.play(right[0].animate.set_stroke(MINT, width=4), right[1].animate.set_color(MINT),
                      *[o.animate.set_opacity(.3) for i, o in enumerate(options) if i != answer], run_time=.5)
            self.wait(.4)
        # crafted: the steps of THIS beat do not come back (the next beat takes them away at once: they were up for a moment
        # of stale words, "Speeds up as before", over the answer's first picture)
        self.play(FadeOut(card), *([FadeIn(hidden)] if len(hidden) and not crafted else []), run_time=.45)
        return True

    def _start_motion(self, figure, marks=None):
        """Run a generated scene's own animation alongside the steps, IN STEP WITH THEM.

        ``marks`` are the scene-clock times at which the beat's steps are due (each the moment
        its words are spoken). The motion is cut into as many equal stages as there are
        marks: stage k begins when step k's words begin and runs until the next step's (the
        last one until the speech ends), and nothing moves before the first. Until
        2026-10-09 the motion ran evenly from the first frame to the last, so only the
        words on the right were in step with the voice: a tester saw the picture act out
        the end of a paragraph while its beginning was being read, and hold still while the
        voice counted. Without marks the old even run is kept.

        The animation is stepped by hand — begin / interpolate(alpha) / finish — exactly
        as ``engine.sim_gen.verify`` stepped it, and ON A COPY SITTING AT THE ORIGIN,
        where it was verified; each frame that copy is mirrored into the picture's place
        in the layout. (The first scene written by a weaker model animated with absolute
        coordinates: right at the origin, 3 units off once the picture sat in its column,
        molecules drifting out of their flask and over the text.) The driver is a
        separate invisible mobject because ``Animation.begin`` suspends updaters on the
        animated mobject itself. Every beat starts the motion from the beginning.
        """
        animator, inner, origin = (getattr(figure, name, None) for name in ("animator", "inner", "origin"))
        if animator is None or inner is None or origin is None:
            return None
        try:
            scale = inner.width / origin.width if origin.width > 1e-6 else 1.0
            offset = inner.get_center() - origin.get_center() * scale
            work = origin.copy()
            start = self.renderer.time
            # Before a chapter's first beat has begun (a picture carried over from the chapter before, put at its end at
            # once) there is no beat clock yet. That case raised here, so every carried-over scene stood at its START:
            # the ice block of a re-filmed lesson hung above the water through a whole recap (2026-11-02).
            current = getattr(self, "current", None)
            total = max(1.5, self.beat_start + current["speech_end"] - start) \
                if current and hasattr(self, "beat_start") else 1.5
            animation = animator(work, total)
            # Each stage's own clock: from its step's words to the next step's (never before the scene is up).
            edges = stage_marks(marks, start)
            across = bool(getattr(figure, "voice_paced", False))
            if edges:
                # Every Manim animation eases in and out over its WHOLE run by default (smooth). Left on, a
                # third of the way through the time is 15% of the way through the motion: the first of three
                # blocks was still invisible when the second was being named. The stages are timed here.
                animation.rate_func = linear
            animation.begin()
            clock = {"t": 0.0}

            def mirror():
                frame = work.copy()
                if abs(scale - 1.0) > 1e-6:
                    frame.scale(scale, about_point=ORIGIN)
                    if self.FILL:
                        scale_strokes(frame, scale)
                frame.shift(offset)
                for member in frame.get_family():
                    # A frame with a malformed shape in it is not shown: the last sound one stays.
                    if getattr(member.points, "ndim", 2) != 2 or (len(member.points) and member.points.shape[1] != 3):
                        raise ValueError(f"a {type(member).__name__} has a malformed point array {member.points.shape}")
                # The picture BECOMES a holder of this frame's copy. Not ``inner.become(frame)``: become
                # aligns the two first, and aligning a part that has points with its own state before
                # ``Create`` has drawn any of it raises IndexError inside Manim. One scene did exactly that
                # in the last chapter of an 8.5-minute lesson (a bracket drawn at its step's words).
                if len(inner.points):
                    inner.reset_points()
                gone = list(inner.submobjects)
                inner.submobjects = [frame]
                # A play draws the family it listed when it BEGAN: the frame replaced here is still in that list
                # and was drawn under the new one until the next play (a moving quadrilateral showed two "D"s and
                # two angle values through every wait, the lagging copy updated at each step's entrance). The copy
                # that leaves is made invisible, so the list's stale entry draws nothing.
                for old in gone:
                    if old is not frame:
                        try:
                            old.set_opacity(0)
                        except Exception:  # noqa: BLE001 - something with no opacity of its own
                            pass

            skipped = {"frames": 0}

            def tick(_, dt):
                # Never raises: this runs inside every frame of the beat, and a model-written scene must
                # not be able to end the chapter. A frame that cannot be made keeps the last one.
                clock["t"] += dt
                try:
                    animation.interpolate(stage_progress(start + clock["t"], start, total, edges, across))
                    mirror()
                except Exception as exc:  # noqa: BLE001
                    skipped["frames"] += 1
                    if skipped["frames"] == 1:
                        print(f"LESSON_NOTE: scene motion could not make a frame ({type(exc).__name__}: "
                              f"{str(exc)[:120]}); the picture holds its last state", flush=True)

            driver = Mobject()
            driver.add_updater(tick)
            # BEHIND everything, not on top. Manim paints once, as a still background, every mobject that
            # comes before the first one with an updater or an animation, and redraws only what follows.
            # Added last, the driver left the picture it was moving in that still background: the motion
            # showed only in the moments another animation happened to play (a step arriving) and stood
            # frozen through every wait, then jumped to its end. Measured on a lesson from before this was
            # found: one beat's picture changed in six short bursts with a six-second freeze in the middle.
            self.bring_to_back(driver)
            return driver, tick, animation, mirror
        except Exception as exc:  # noqa: BLE001 - a still picture is better than a dead chapter
            print(f"LESSON_NOTE: scene motion not started ({type(exc).__name__}: {exc})", flush=True)
            return None

    def _voice_window(self, steps, due, located):
        """``(start, end)`` of the sentence a number should move across, or None (the lead-in tween plays instead).

        The beat's first step flagged ``tween: "voice"`` (the kit writes it, ``kits/components.py``). None when its words were
        not found in the speech (``located``: an even spread is a guess, and a move paced by a guess starts in the wrong
        place), when an earlier step names a part of the picture (it would act on a picture that is under the old one), or
        when the sentence is shorter than ``VOICE_TWEEN_MIN``. It runs to the next step's words, else to the end of the speech.
        """
        flagged = next((i for i, step in enumerate(steps) if step.get("tween") == "voice"), None)
        if flagged is None or not located[flagged] or any(step.get("focus") for step in steps[:flagged]):
            return None
        start = due[flagged]
        later = [d for d in due[flagged + 1:] if d > start + .05]
        end = min(later) if later else self.beat_start + self.current["speech_end"]
        return (start, end) if end - start >= VOICE_TWEEN_MIN else None

    def _start_tween(self, ghost, animation, start, end, figure=None):
        """Move the old picture (``ghost``, still on screen) into the new one BY THE VOICE, from ``start`` to ``end`` (scene clock).

        ``animation`` is what ``ComponentFigure.change_from`` returned. The step cue caps every animation at 0.9 s
        (``run_time=min(.9, ...)``), and the lead-in tween 1.4 s; a number that moves for the whole sentence that says it needs
        a clock of its own. Modelled on ``_start_motion``: the animation is stepped by hand (begin / interpolate / the picture is
        left at its end) from a driver mobject BEHIND everything (see there for why behind), at ``tween_progress`` of the scene
        clock (Manim's own clock moves only between plays: it is that time plus the frames' dt). The new picture is under the ghost from the first frame, so the beat's steps do what they always do to it; when the
        sentence is over the ghost is made invisible (the frame it reaches its end it equals the picture below) and
        ``_stop_tween`` removes it. A focus pulse can therefore never fight the move: it acts on the picture below.
        Returns a handle, or None (nothing was changed) when the animation cannot be started; nothing here may raise.
        """
        try:
            animation.rate_func = linear                 # the sentence sets the pace, not an ease over the whole of it
            # A Succession (the stations of a knob that moves along a curve, S8, inside the group ``change_from`` returns) sets its
            # legs up from the scene it is played on; stepped by hand it has none, and ``begin`` raised AttributeError: the whole
            # move fell back to the lead-in (found filming the pendulum, plan S13). Every level gets the scene as a name.
            pending = [animation]
            while pending:
                one = pending.pop()
                if not hasattr(one, "scene"):
                    one.scene = self
                pending.extend(getattr(one, "animations", None) or [])
            animation.begin()
            # ``renderer.time`` moves only when a play or a wait is over, never inside one: the clock is that time at the last
            # boundary plus the frames' own dt since (a long wait with nothing else playing is one such stretch).
            state = {"last": None, "gone": False, "at": None, "since": 0.0}
            # The new picture sits under the old one from the first frame, and its words are on screen at full strength while the
            # old picture's words cross-fade into them: "time 1.8 s" faded out over "time 3.6 s" (found filming the pendulum, plan
            # S13). The new words are taken away until the move is over; the ghost carries its own copies of them coming in.
            hidden = []
            for text in getattr(figure, "labels", None) or []:
                for m in text.family_members_with_points():
                    hidden.append((m, float(m.get_stroke_opacity()), float(m.get_fill_opacity())))
                    m.set_stroke(opacity=0)
                    m.set_fill(opacity=0)

            def restore():
                while hidden:
                    m, stroke, fill = hidden.pop()
                    m.set_stroke(opacity=stroke)
                    m.set_fill(opacity=fill)

            def tick(_, dt):
                if state["gone"]:
                    return
                try:
                    if self.renderer.time != state["at"]:
                        state["at"], state["since"] = self.renderer.time, 0.0
                    else:
                        state["since"] += dt
                    p = tween_progress(state["at"] + state["since"], start, end)
                    if p != state["last"]:
                        state["last"] = p
                        animation.interpolate(p)
                    if p >= 1.0:
                        state["gone"] = True
                        ghost.set_opacity(0)
                        restore()
                except Exception as exc:  # noqa: BLE001 - never raises inside a frame; the picture holds its last state
                    state["gone"] = True
                    ghost.set_opacity(0)
                    restore()
                    print(f"LESSON_NOTE: a number's move could not be driven ({type(exc).__name__}: {str(exc)[:120]}); "
                          "the new picture is shown", flush=True)

            driver = Mobject()
            driver.add_updater(tick)
            driver.restore_words = restore
            self.add(driver)
            self.bring_to_back(driver)
            return driver, tick, ghost, end
        except Exception as exc:  # noqa: BLE001 - the lead-in tween is always there to fall back on
            (locals().get("restore") or (lambda: None))()
            print(f"LESSON_NOTE: a number's move was not driven by the voice ({type(exc).__name__}: {str(exc)[:120]})", flush=True)
            return None

    def _stop_tween(self, handle):
        if not handle:
            return
        driver, tick, ghost, _ = handle
        try:
            getattr(driver, "restore_words", lambda: None)()
            driver.remove_updater(tick)
            self.remove(driver, ghost)
        except Exception:  # noqa: BLE001
            pass

    def _start_paint(self, figure, room: float, numbers=None):
        """Have a prepared drawing DRAW itself, part by part, while the beat goes on (``figures.PictureFigure.paint``).
        With ``numbers``: only the parts a step brings (a drawing drawn WITH the words, ``_draw_with``).

        The pen-work takes a few seconds and the voice does not wait for it: like a scene's motion it is stepped by
        hand from a driver behind everything (see ``_start_motion`` for why behind). Never in a preview of stills,
        where every moment is the finished one. Returns a handle for ``_stop_paint``, or None when the figure has
        nothing to draw; nothing here may raise.
        """
        if not self.PAINTED or STILLS or not hasattr(figure, "paint"):
            return None
        try:
            made = figure.paint() if numbers is None else figure.paint(numbers)
            if not made:
                return None
            animation, seconds = made
            seconds = max(1.2, min(seconds, room)) if numbers is None else max(.4, min(seconds, room))
            if numbers is None and isinstance(getattr(self, "_beat_layout", None), dict):
                self._beat_layout["painted"] = round(seconds, 2)     # for whoever looks at this beat's frames afterwards
            animation.rate_func = linear                # the strokes ease by themselves; the whole runs evenly
            animation.begin()
            clock = {"t": 0.0, "done": False, "began": self.renderer.time}

            def finish():
                if not clock["done"]:
                    clock["done"] = True
                    animation.interpolate(1.0)
                    animation.finish()
                    figure.painted()

            def tick(_, dt):
                clock["t"] = self.renderer.time - clock["began"]      # the scene's clock (a sum of dt loses a frame a play)
                try:
                    if clock["t"] >= seconds:
                        finish()
                    elif not clock["done"]:
                        animation.interpolate(clock["t"] / seconds)
                except Exception as exc:  # noqa: BLE001 - a drawing that cannot be drawn by hand is shown as it is
                    if not clock.get("said"):
                        clock["said"] = True
                        print(f"LESSON_NOTE: the drawing could not be drawn part by part ({type(exc).__name__}: {str(exc)[:120]}); "
                              "it is shown finished", flush=True)
                    try:
                        clock["done"] = True
                        figure.painted()
                    except Exception:  # noqa: BLE001
                        pass

            driver = Mobject()
            driver.add_updater(tick)
            self.add(driver)
            self.bring_to_back(driver)
            return driver, tick, finish
        except Exception as exc:  # noqa: BLE001
            print(f"LESSON_NOTE: the drawing could not be drawn part by part ({type(exc).__name__}: {str(exc)[:120]}); it is shown finished",
                  flush=True)
            try:
                figure.painted()
            except Exception:  # noqa: BLE001
                pass
            return None

    def _stop_paint(self, handle):
        if not handle:
            return
        driver, tick, finish = handle
        try:
            driver.remove_updater(tick)
            self.remove(driver)
            finish()
        except Exception:  # noqa: BLE001
            pass

    def _stop_motion(self, handle):
        if not handle:
            return
        driver, tick, animation, mirror = handle
        try:
            driver.remove_updater(tick)
            self.remove(driver)
            animation.finish()
            mirror()
        except Exception:  # noqa: BLE001
            pass

    def _start_hints(self, figure):
        """Light what the voice is talking about on a reaction picture, word by word, beside the beat
        (``reaction_hints.plan`` says when, ``figure.hint_targets`` says what). Stateless in time: each frame is the
        picture as it was plus how strongly each thing is lit now, so it always settles exactly where it began.
        Returns a handle for ``_stop_hints``, or None; nothing here may raise."""
        if STILLS or not hasattr(figure, "hint_targets"):
            return self._start_staging(figure)
        try:
            from .reaction_hints import SPAN, plan     # noqa: PLC0415
            # A figure that reads the voice itself (a geometry ``shape``: "side AB", "angle C") plans its own lights.
            own = getattr(figure, "hint_plan", None)
            events = own(self.current["sentences"]) if own else plan(self.current["sentences"], getattr(figure, "species_info", []))
            if own:
                events = events + self._question_lights(own)
            now = self.renderer.time
            lights: dict = {}
            for event in events:
                start = self.beat_start + float(event["t"]) - CUE_LEAD
                for mob, delay in figure.hint_targets(event):
                    if start + delay >= now:
                        lights.setdefault(id(mob), [mob, []])[1].append(start + delay)
            if not lights:
                if getattr(figure, "_late", None) and getattr(figure, "staged_steps", False):
                    return self._start_staging(figure)
                self._show_late(figure, 0.0, everything=True)
                return None
            base = {}
            for key, (mob, _) in lights.items():
                # Colours are kept per GLYPH: a Text's own colour is not its letters' (read back from the container,
                # every count turned black after its first light).
                letters = [g for w in mob.get_family() if _is_words(w) for g in w.get_family() if len(g.points)]
                # A line, an arc or a tick of a geometry picture lights by its stroke (``lights_up``) and does not grow
                # (``hint_grow``): a side scaled about its middle would be a longer side.
                base[key] = {"scale": 1.0, "words": [(g, g.get_fill_color()) for g in letters],
                             "grow": getattr(mob, "hint_grow", None),
                             "rims": [(m, m.get_stroke_color(), m.get_stroke_width()) for m in mob.get_family()
                                      if (isinstance(m, Circle) or getattr(m, "lights_up", False)) and len(m.points)],
                             # a shaded region (a proof's triangle) brightens in place: grown, it spilled past its shape
                             "shades": [(m, m.get_fill_opacity()) for m in mob.get_family()
                                        if getattr(m, "lights_fill", False) and len(m.points)]}
            record = getattr(self, "_beat_layout", None)
            if isinstance(record, dict):
                record["hints"] = len(events)

            def strength(t, starts):
                best = 0.0
                for t0 in starts:
                    d = t - t0
                    if 0 <= d < SPAN:
                        best = max(best, min(1.0, d / .2, (SPAN - d) / .4))
                return best

            def apply(key, a):
                mob, b = lights[key][0], base[key]
                grow = b["grow"] if b.get("grow") is not None else (.12 if b["words"] else .28)
                want = 1 + grow * a     # words grow less: a count sits next to the steps
                if abs(want - b["scale"]) > 1e-4:
                    mob.scale(want / b["scale"])
                    b["scale"] = want
                for m, colour in b["words"]:
                    m.set_fill(interpolate_color(ManimColor(colour), ManimColor(GOLD), a))
                for m, colour, width in b["rims"]:
                    m.set_stroke(interpolate_color(ManimColor(colour), ManimColor(GOLD), a), width=width + 4 * a)
                for m, opacity in b["shades"]:
                    m.set_fill(opacity=min(1.0, opacity + .3 * a))

            def tick(_, dt):
                t = self.renderer.time
                for key, (_, starts) in lights.items():
                    try:
                        apply(key, strength(t, starts))
                    except Exception:  # noqa: BLE001 - a hint that cannot be shown is left out
                        pass
                self._show_late(figure, t)      # a part that waited for its words is drawn in as they come

            def settle():
                for key in lights:
                    try:
                        apply(key, 0.0)
                    except Exception:  # noqa: BLE001
                        pass
                self._show_late(figure, 0.0, everything=True)

            driver = Mobject()
            driver.add_updater(tick)
            self.add(driver)
            self.bring_to_back(driver)         # behind everything, or the picture is painted once as a still background
            return driver, tick, settle
        except Exception as exc:  # noqa: BLE001
            print(f"LESSON_NOTE: the picture's hints could not be planned ({type(exc).__name__}: {str(exc)[:120]})", flush=True)
            self._show_late(figure, 0.0, everything=True)
            return None

    def _question_lights(self, own) -> list:
        """While a thinking pause counts down, the parts its question is about light in turn, again and again (the
        2026-10-21 review: 6 to 8 s of a still picture at every question, only the thin bar moving). The lights are
        ordinary hint events placed after the speech, so the hint clock draws them and the beat ends settled."""
        try:
            pause = float(self.current.get("thinking_pause_seconds") or 0)
            if pause < 2.5:
                return []
            beat = getattr(self, "_beat_now", None) or {}
            quiz = (beat.get("quiz") if isinstance(beat, dict) else None) or {}
            if not str(quiz.get("question") or "").strip() and isinstance(beat, dict):
                quiz = {**quiz, "question": screen_question(beat)}
            text = " ".join([str(quiz.get("question") or "")] + [str(o) for o in quiz.get("options") or []])
            if not text.strip():
                return []
            seen, groups = set(), []
            for event in own([{"text": text, "start": 0.0, "duration": 1.0}]):
                key = tuple(event["parts"])
                if key not in seen:
                    seen.add(key)
                    groups.append(event)
            if not groups:
                return []
            start = float(self.current["speech_end"]) + .9          # after the card has come in
            stop = float(self.current["duration"]) - 1.6            # every light is out before the answer shows
            out, t, k = [], start, 0
            while t + 1.0 < stop and k < 40:
                g = groups[k % len(groups)]
                out.append({**g, "t": t + CUE_LEAD})
                t += 1.7
                k += 1
            return out
        except Exception:  # noqa: BLE001 - a pause without lights is the old pause
            return []

    #: seconds a held-back part takes to be drawn in once its words come
    DRAW_IN = .6

    def _hold_back_named(self, figure, carried, ready_at):
        """Parts of a new picture that the voice names later in the beat wait for their words, unseen
        (``figure.buildable``: never the outline or its corners). The 2026-10-21 review measured the picture still for
        36 to 62% of the spoken time: every beat's figure arrived whole in its lead-in, so "draw the diagonal AC" was
        said over a diagonal that had been there for ten seconds. ``_start_hints`` draws each part in at its words and
        lights it; the beat always ends with every part shown. Nothing here may raise; in stills nothing waits."""
        figure._late = {}
        if STILLS or not hasattr(figure, "buildable") or not hasattr(figure, "hint_plan"):
            return
        try:
            names = figure.buildable()
            had = set(getattr(carried, "parts", {}) or {}) if getattr(carried, "kind", None) == getattr(figure, "kind", "") else set()
            if had and getattr(figure, "values_spoken", False):
                # look ``values: spoken``: an angle's number or a sum line that the next shape WRITES DIFFERENTLY is new, not
                # the one already on screen (a second triangle's "75" took the first one's place at once, 6 s early)
                def written(mob) -> str:
                    return " ".join(str(m.text) for m in mob.get_family() if hasattr(m, "text")) if mob is not None else ""
                had = {n for n in had if not (n.endswith("_value") or n.endswith("band"))
                       or written(carried.parts.get(n)) == written(figure.parts.get(n))}
            by_id = {id(m): n for n, m in figure.parts.items() if n in names and n not in had}
            first: dict = {}
            for event in figure.hint_plan(self.current["sentences"]):
                start = self.beat_start + float(event["t"]) - CUE_LEAD
                for mob, delay in figure.hint_targets(event):
                    name = by_id.get(id(mob))
                    if name:
                        first[name] = min(first.get(name, 1e9), start + delay)
            # A part that hangs on a point the voice names later waits for that point too: a midpoint's ticks, the
            # segment PQ, the arrows on it (first try: the ticks and PQRS stood there before P, Q, R and S had come).
            points = {n for n in first if re.fullmatch(r"[A-Z]\d*", n)}
            for name in set(by_id.values()):
                hangs = [first[q] for q in re.findall(r"[A-Z]\d*", name.split("_")[-1]) if q in points and q != name]
                if hangs and name not in points:
                    first[name] = max(max(hangs), first.get(name, 0.0))
            for name, t in first.items():
                if t < ready_at + .6:
                    continue            # named as the picture arrives: it simply arrives with it
                mob = figure.parts[name]
                saved = []
                for m in mob.get_family():
                    if not len(m.points) and not m.submobjects:
                        continue
                    # an open stroke grows from its start; a Dot is a Circle is an Arc, and is faded in, fill and all
                    line = (isinstance(m, Line) or (isinstance(m, Arc) and not isinstance(m, Circle))) \
                        and not isinstance(m, DashedLine) and len(m.points)
                    saved.append((m, m.get_stroke_opacity(), m.get_fill_opacity(), m.copy() if line else None))
                for m, _, _, _ in saved:
                    m.set_stroke(opacity=0)
                    m.set_fill(opacity=0)
                figure._late[name] = {"mob": mob, "at": t, "saved": saved}
            if figure._late:
                record = getattr(self, "_beat_layout", None)
                if isinstance(record, dict):
                    record["drawn_with_words"] = sorted(figure._late)
                    record["held_until"] = {n: round(float(i["at"]) - self.beat_start, 2) for n, i in figure._late.items()}
        except Exception as exc:  # noqa: BLE001
            print(f"LESSON_NOTE: the picture is shown whole ({type(exc).__name__}: {str(exc)[:120]})", flush=True)
            self._show_late(figure, 1.0, everything=True)

    #: parts of a graph that are never held back for a step: its frame
    STAGE_KEEP = ("axes", "x_label", "y_label")

    def _hide(self, mob) -> list:
        """Hide ``mob`` and return what ``_show_late`` needs to draw it in again (a line or a curve is grown from its start)."""
        saved = []
        for m in mob.get_family():
            if not len(m.points) and not m.submobjects:
                continue
            line = (isinstance(m, Line) or (isinstance(m, Arc) and not isinstance(m, Circle)) or getattr(m, "grows_in", False)) \
                and not isinstance(m, DashedLine) and len(m.points)
            saved.append((m, m.get_stroke_opacity(), m.get_fill_opacity(), m.copy() if line else None))
        for m, _, _, _ in saved:
            m.set_stroke(opacity=0)
            m.set_fill(opacity=0)
        return saved

    def _graph_stage_times(self, figure, steps, due) -> dict:
        """name -> (scene time, step index): a graph's point, its label, its curve and the curve's equation come with the
        step whose ``focus`` names them. A part no step names stays with the picture."""
        out: dict = {}
        for i, step in enumerate(steps):
            focus = str(step.get("focus") or "")
            if not focus or focus in self.STAGE_KEEP or focus not in figure.parts or focus in out:
                continue
            out[focus] = (due[i], i)
            tag = re.fullmatch(r"(point|meet)(\d+)", focus)
            if tag and f"{focus}_label" in figure.parts and not any(str(s.get("focus") or "") == f"{focus}_label" for s in steps):
                out[f"{focus}_label"] = (due[i], i)
        for name in [n for n in out if re.fullmatch(r"(?:point|meet)\d+_label", n)]:
            # The dot comes with its step ("After 2 seconds"); the label that WRITES the value waits for the voice to say it
            # ("... its speed is 6 metres per second"), at most 15 s after the step and never before it.
            said = self._value_said(figure.parts[name], out[name][0])
            if said is not None:
                out[name] = (said, out[name][1])
        for name in list(out):                       # a curve's equation comes with the curve unless a step brings it itself
            tag = re.fullmatch(r"curve(\d+)", name)
            label = f"curve{tag.group(1)}_label" if tag else ""
            if label and label in figure.parts and not any(str(s.get("focus") or "") == label for s in steps):
                out.setdefault(label, out[name])
        return out

    def _value_said(self, label, after) -> float | None:
        """Scene time at which the voice says the last number a graph label writes ("2 s, 6 m/s" -> 6), looked for from the
        moment of its step (``after``) to 15 s later; None when the label has no two numbers or the voice does not say it."""
        try:
            from .shape_hints import tokens  # noqa: PLC0415 - the same word clock the geometry hints use
            text = str(getattr(label, "text", "") or getattr(label, "tex_string", "") or "")
            found = re.findall(r"-?\d+(?:\.\d+)?", text)
            if len(found) < 2:
                return None
            want = float(found[-1])
            start = after - self.beat_start
            for sentence in self.current["sentences"]:
                for tok, t in tokens(sentence):
                    if re.fullmatch(r"\d+", tok) and abs(float(tok) - want) < 1e-9 and start - .3 <= t <= start + 15:
                        return max(after, self.beat_start + t - CUE_LEAD)
        except Exception:  # noqa: BLE001 - then the label comes with its step
            pass
        return None

    def _reaction_stage_times(self, figure, ready_at) -> dict:
        """name -> (scene time, None): the count table at the word that counts, the verdict at the word that says it."""
        from .reaction_hints import stage_times  # noqa: PLC0415
        got = stage_times(self.current["sentences"], getattr(figure, "species_info", []))
        out: dict = {}
        for names, key in ((("count_heads", "left_count", "right_count"), "table"), (("verdict",), "verdict")):
            t = got.get(key)
            at = ready_at if t is None else max(ready_at, self.beat_start + float(t) - CUE_LEAD)
            for name in names:
                if name in figure.parts:
                    out[name] = (at, None)
        return out

    def _only_a_hold_differs(self, figure, carried, spec) -> bool:
        """Look ``staging: steps``: whether this motion figure is the one on screen but for its ``hold_marks``."""
        try:
            if not getattr(figure, "staged_steps", False) or getattr(figure, "kind", "") != "motion" \
                    or getattr(carried, "kind", None) != "motion" or not self._figure_key:
                return False
            drop = lambda d: {k: v for k, v in d.items() if k != "hold_marks"}  # noqa: E731
            return drop(json.loads(self._figure_key)) == drop(spec) and json.loads(self._figure_key) != spec
        except Exception:  # noqa: BLE001
            return False

    def _hold_back_steps(self, figure, steps, due, ready_at):
        """Look ``staging: steps`` (video-quality plan S5): a finished graph or table is drawn in as it is talked about.

        A graph's points, labels, curve and equation wait for the step that focuses them (a curve is drawn along, the rest
        fade in); a reaction's count table and verdict wait for the word that counts and the word that says the verdict.
        The same ``_late`` machinery as ``_hold_back_named`` draws them in (``_start_hints`` or ``_start_staging`` run the
        clock) and the beat always ends with every part shown. In stills only a graph waits, by step. Nothing raises."""
        if not getattr(figure, "staged_steps", False) or not hasattr(figure, "parts"):
            return
        try:
            kind = getattr(figure, "kind", "")
            if kind in ("graph", "motion"):
                when = self._graph_stage_times(figure, steps, due)
            elif kind == "reaction" and not STILLS:
                when = self._reaction_stage_times(figure, ready_at)
            else:
                return
            late = getattr(figure, "_late", None)
            if late is None:
                late = figure._late = {}
            for name, (t, k) in when.items():
                if name in late:
                    continue
                late[name] = {"mob": figure.parts[name], "at": t, "saved": self._hide(figure.parts[name]), "step": k}
            if late:
                record = getattr(self, "_beat_layout", None)
                if isinstance(record, dict):
                    record["staged"] = sorted(late)
                    record["held_until"] = {**(record.get("held_until") or {}),
                                            **{n: round(float(i["at"]) - self.beat_start, 2) for n, i in late.items()}}
        except Exception as exc:  # noqa: BLE001
            print(f"LESSON_NOTE: the picture is shown whole ({type(exc).__name__}: {str(exc)[:120]})", flush=True)
            self._show_late(figure, 1.0, everything=True)

    def _reveal_to_step(self, figure, i):
        """Stills: the parts that steps 0..i bring are there (a still has no clock; ``_show_late`` reads ``at``)."""
        late = getattr(figure, "_late", None)
        if not late:
            return
        for item in late.values():
            if item.get("step") is not None and item["step"] <= i:
                item["at"] = -1e9
        self._show_late(figure, -1e8)

    def _start_staging(self, figure):
        """A clock for parts held back by ``_hold_back_steps`` on a picture with no voice-led lights. A handle for
        ``_stop_hints`` (which draws whatever is left), or None."""
        if STILLS or not getattr(figure, "_late", None):
            return None

        def tick(_, dt):
            self._show_late(figure, self.renderer.time)

        def settle():
            self._show_late(figure, 0.0, everything=True)

        driver = Mobject()
        driver.add_updater(tick)
        self.add(driver)
        self.bring_to_back(driver)
        return driver, tick, settle

    def _show_late(self, figure, t, everything=False):
        """Draw in each held-back part as far as the scene clock ``t`` says (a line grows from its start, the rest
        fades in); ``everything`` shows them all, whole."""
        for item in (getattr(figure, "_late", None) or {}).values():
            a = 1.0 if everything else min(1.0, max(0.0, (t - item["at"]) / self.DRAW_IN))
            for m, stroke, fill, whole in item["saved"]:
                try:
                    if whole is not None:
                        m.pointwise_become_partial(whole, 0, max(a, 1e-3))
                        m.set_stroke(opacity=stroke if a > 0 else 0)
                        m.set_fill(opacity=fill if a > 0 else 0)
                    else:
                        m.set_stroke(opacity=stroke * a)
                        m.set_fill(opacity=fill * a)
                except Exception:  # noqa: BLE001 - a part that cannot be drawn in is shown
                    pass
        if everything and hasattr(figure, "_late"):
            figure._late = {}

    def _stop_hints(self, handle):
        if not handle:
            return
        driver, tick, settle = handle
        try:
            driver.remove_updater(tick)
            self.remove(driver)
        finally:
            settle()

    def _drawn_later(self, spec: dict, beat: dict) -> set:
        """The parts of this drawing (their numbers) that a step of THIS beat or a later one draws (``step["draw"]``,
        from ``harness.sequence.with_words``): what is not on the board yet when the beat begins.

        Worked out from the whole lesson, in order, like ``_pointed_at_before``: a chapter is a render of its own, and
        a drawing that is drawn with the words stands in each chapter as the chapters before left it. A part a step
        of an earlier beat has drawn is there. A lesson in which no step draws anything has nothing held back, and its
        drawings are as they always were.
        """
        file = str(spec.get("file") or "")
        if spec.get("kind") != "picture" or not file:
            return set()
        earlier, later, seen = set(), set(), False
        for chapter in self.lesson["chapters"]:
            for other in chapter["beats"]:
                seen = seen or other is beat or other.get("id") == beat.get("id")
                figure = other.get("figure") or {}
                if figure.get("kind") != "picture" or str(figure.get("file") or "") != file:
                    continue
                for step in other.get("steps") or []:
                    numbers = {int(n) for n in step.get("draw") or [] if isinstance(n, int) or str(n).isdigit()}
                    (later if seen else earlier).update(numbers)
        return later - earlier

    def _draw_with(self, figure, numbers, room: float) -> list:
        """A step's words have come: the parts they bring are drawn now, beside them (never before: ``Later``)."""
        try:
            if not getattr(figure, "_staged", False):
                return []
            if STILLS or not self.PAINTED:
                figure.reveal(numbers)
                return []
            self._stop_paint(getattr(self, "_step_paint", None))        # the pen is in one place at a time
            self._step_paint = self._start_paint(figure, max(.4, room), numbers) if getattr(figure, "_staged", False) else None
        except Exception as exc:  # noqa: BLE001 - a part that cannot be drawn in is simply there
            print(f"LESSON_NOTE: a step's part of the drawing could not be drawn in ({type(exc).__name__}: {str(exc)[:120]})", flush=True)
            try:
                figure.reveal(numbers)
            except Exception:  # noqa: BLE001
                pass
        return []

    def _annotated_before(self, spec: dict, beat: dict) -> list:
        """The marks that STAY which earlier beats of the lesson wrote on this same drawing, in order
        (``harness/annotate.py``): what a hand has written is on the board when a later chapter opens on it."""
        file = str(spec.get("file") or "")
        if spec.get("kind") != "picture" or not file:
            return []
        out = []
        for chapter in self.lesson["chapters"]:
            for other in chapter["beats"]:
                if other is beat or other.get("id") == beat.get("id"):
                    return out
                figure = other.get("figure") or {}
                if figure.get("kind") == "picture" and str(figure.get("file") or "") == file:
                    out += [mark for step in other.get("steps") or [] for mark in step.get("annotate") or [] if mark.get("life") == "stays"]
        return out

    def _marks_due(self, steps, due, figure=None, settled: float = 0.0) -> list:
        """When each mark of this beat is made: ``[(scene time, mark)]`` in order.

        A mark comes with ITS OWN words (``say``, looked for anywhere in the beat: a value is often said before the
        line that carries it comes up), else with its step. Never before the parts of the drawing it stands on are
        drawn; marks of one slot keep their order; the hand makes one gesture at a time.

        "Drawn" means the pen has finished: a part a step brings takes the pen up to 2.6 s (``figure.pen_seconds``),
        and a drawing that arrives in this beat is being drawn until ``settled``. A ring came a second and a half
        into a lesson and hung in the empty place where the stone was drawn two seconds later (Why Water Pushes Up).
        """
        out, last_in_slot, last_gesture, room = [], {}, 0.0, 0.0
        drawn = {}
        for i, step in enumerate(steps):
            numbers = step.get("draw") or []
            if numbers:
                lasts = .6
                try:
                    lasts = max(.6, float(figure.pen_seconds(numbers))) if hasattr(figure, "pen_seconds") else .6
                except Exception:  # noqa: BLE001 - then the old allowance
                    lasts = .6
                drawn.update({int(n): due[i] + lasts for n in numbers})
        end = self.beat_start + self.current["duration"] - .5
        for i, step in enumerate(steps):
            for mark in step.get("annotate") or []:
                if not mark.get("prims") and i == 0:     # the last part's values are wiped as this one begins
                    out.append((self.beat_start + .05, len(out), mark, "step"))
                    continue
                at = due[i]
                found = self.locate(str(mark.get("say") or ""), after=0.0) if mark.get("say") else None
                if found:
                    at = self.beat_start + max(0.0, found[0] - (CUE_LEAD if found[1] == "aligned" else 0.0))
                at = max([at, self.beat_start + .15] + [drawn.get(int(n), settled) for n in mark.get("needs") or []])
                if mark.get("life") == "stays":
                    at = max(at, last_in_slot.get(mark.get("slot"), 0.0) + .05)
                    last_in_slot[mark.get("slot")] = at
                else:
                    # A gesture has time to be seen before the hand goes elsewhere: a ring a second, and one that
                    # WRITES words long enough to read them ("motion: right" was up for 1.1 s, drawn for most of it).
                    at = max(min(at, end - 1.4), last_gesture + room, self.beat_start + .15)
                    last_gesture, room = at, (self.WORDS_SECONDS if str(mark.get("text") or "").strip() else self.GESTURE_LEAST)
                out.append((min(at, max(end, self.beat_start + .2)), len(out), mark, "words" if found else "step"))
        return [(at, mark, how) for at, _, mark, how in sorted(out, key=lambda e: e[:2])]

    def _note_mark(self, figure, mark, now, how="step") -> None:
        """The record of a mark's time on the board (the chapter's audit): its start, and the end of what it replaced."""
        for gone in getattr(figure, "left", None) or []:
            for entry in self._mark_records:
                if entry["id"] == gone and entry["end"] is None:
                    entry["end"] = round(now, 2)
        if mark is not None and mark.get("prims") and isinstance(getattr(self, "_beat_layout", None), dict):
            entry = {"id": mark.get("id"), "kind": mark.get("kind"), "text": mark.get("text", ""), "start": round(now, 2), "end": None, "with": how}
            self._beat_layout.setdefault("annotations", []).append(entry)
            self._mark_records.append(entry)

    #: How long a gesture of the hand (a ring, a line gone over, an arrow, a cross) stays when nothing replaces it sooner.
    #: A line gone over at a beat's fifth second lay highlighted for seventeen more.
    GESTURE_SECONDS = 4.5
    #: The least a gesture has before the next one takes the hand away: a ring or a line gone over, and an arrow with words.
    GESTURE_LEAST, WORDS_SECONDS = 1.0, 2.6

    def _start_marks(self, figure, events):
        """Have a hand add its marks to the drawing when their words come (``figures.PictureFigure.annotate``), beside
        whatever else the beat is doing: stepped by hand from a driver behind everything, like the pen that draws the
        picture. Returns a handle for ``_stop_marks``; nothing here may raise."""
        if not events or STILLS or not hasattr(figure, "annotate"):
            return None
        try:
            figure.prepare_marks([mark for _, mark, _ in events])       # on the picture, unseen, before the beat's first frame
        except Exception as exc:  # noqa: BLE001
            print(f"LESSON_NOTE: a beat's marks could not be made ready ({type(exc).__name__}: {str(exc)[:120]})", flush=True)
        pending, active, clock = list(events), [], {"now": self.renderer.time, "said": False, "gesture": None}

        def fire(mark, how, at_once=False):
            try:
                # What the hand is still drawing is finished first. A mark that LEAVES is hidden by the figure; while its
                # own drawing-in was still running, the next frames went on fading its words in, and "motion: right"
                # stood on the picture long after the hand had moved to another place (Friction, 2026-10-12).
                step(final=True)
                animations = figure.annotate([mark], now=at_once)
                self._note_mark(figure, mark, clock["now"], how)
                if mark.get("life") != "stays" and mark.get("prims"):
                    clock["gesture"] = clock["now"] + self.GESTURE_SECONDS      # a ring or a pass of the pen is a moment, not a fixture
                for animation in animations:
                    animation.begin()
                    active.append([animation, clock["now"], max(.2, float(getattr(animation, "run_time", .5) or .5))])
            except Exception as exc:  # noqa: BLE001 - a mark that cannot be made is left out
                if not clock["said"]:
                    clock["said"] = True
                    print(f"LESSON_NOTE: a mark could not be made on the drawing ({type(exc).__name__}: {str(exc)[:120]})", flush=True)

        def step(final=False):
            for item in list(active):
                animation, began, lasts = item
                alpha = 1.0 if final else (clock["now"] - began) / lasts
                try:
                    if alpha >= 1.0:
                        animation.interpolate(1.0)
                        animation.finish()
                        active.remove(item)
                    else:
                        animation.interpolate(alpha)
                except Exception:  # noqa: BLE001
                    active.remove(item)

        def tick(_, dt):
            # The scene's own clock, not a sum of ``dt``: every play begins with a frame whose dt is 0, so a sum loses a
            # frame a play and ran a second late ten seconds into a beat of many short plays (found by the filmed test:
            # a value recorded at 10.3 s was not on screen at 11.5 s).
            clock["now"] = self.renderer.time
            while pending and clock["now"] >= pending[0][0]:
                _, mark, how = pending.pop(0)
                fire(mark, how)
            if clock["gesture"] is not None and clock["now"] >= clock["gesture"]:
                clock["gesture"] = None
                try:
                    step(final=True)                     # as in ``fire``: nothing half-drawn outlives being hidden
                    figure.clear_gesture()
                    self._note_mark(figure, None, clock["now"])
                except Exception:  # noqa: BLE001
                    pass
            step()

        def finish():
            while pending:                               # the beat is over: what was still to come is there
                _, mark, how = pending.pop(0)
                fire(mark, how, at_once=True)
            step(final=True)

        driver = Mobject()
        driver.add_updater(tick)
        self.add(driver)
        self.bring_to_back(driver)
        return driver, tick, finish

    def _stop_marks(self, handle):
        if not handle:
            return
        driver, tick, finish = handle
        try:
            driver.remove_updater(tick)
            self.remove(driver)
            finish()
        except Exception:  # noqa: BLE001
            pass

    def _pointed_at_before(self, spec: dict, beat: dict) -> list[str]:
        """What every EARLIER beat of the lesson pointed at on this same drawing, in order (not only the last chapter's)."""
        names = []
        for chapter in self.lesson["chapters"]:
            for other in chapter["beats"]:
                if other is beat or other.get("id") == beat.get("id"):
                    return names
                figure = other.get("figure") or {}
                if figure.get("kind") == spec.get("kind") and figure.get("manifest") and figure.get("manifest") == spec.get("manifest"):
                    names += [str(step["focus"]) for step in other.get("steps") or [] if step.get("focus")]
        return names

    def _carry_over(self, ch, earlier, inherited):
        """Open this chapter on the screen the chapter before ended on: ``(words, figure, key)`` now on screen.

        Each chapter is a render of its own, joined to the next by a cut. Without this, the last frame of a chapter
        held a picture, a line of words and a heading, and the next chapter's first frame held a new heading on an
        empty stage: everything popped at once, then the new picture was drawn (the owner, 2026-10-15: "a somewhat
        choppy experience. It is not continuous"). Now the old heading cross-fades into the new one, the picture is
        put back exactly as the lesson left it (its parts so far, its marks, a scene at its end) and becomes this
        chapter's picture: kept when the first beat keeps it, morphed or faded out by the beat that replaces it, like
        any change of picture inside a chapter. The last beat's closing words stand until this chapter's first line
        replaces them. Nothing here may end a chapter: on any failure the chapter opens as it always did.
        """
        nothing = (VGroup(), None, None)
        if not (self.JOINS and self.staged) or STILLS or not earlier:
            return nothing
        from . import figures as _figures
        last = earlier[-1]
        chapters = self.lesson["chapters"]
        index = next(i for i, c in enumerate(chapters) if c["id"] == self.chapter_id)
        previous = chapters[index - 1]
        first = ch["beats"][0]
        figure, key = None, None
        try:
            if inherited is not None:
                spec = json.loads(inherited)
                figure = _figures.build(spec, crafted=self.CRAFTED)
                if figure is not None:
                    if hasattr(figure, "resume"):
                        figure.resume(self._pointed_at_before(spec, first))
                    if getattr(figure, "kind", "") in self.DRAWN_FOR_YOU:
                        self.small_heading()
                    self._staged([], figure, last)               # its place: the one the run of beats has
                    if hasattr(figure, "hold_back"):
                        figure.hold_back(self._drawn_later(spec, first), str(spec.get("planned") or ""))
                    if hasattr(figure, "annotate"):
                        figure.annotate(self._annotated_before(spec, first), now=True)
                    self.add(figure)
                    if getattr(figure, "bleeds", False):
                        self.bring_to_back(figure)
                    self._stop_motion(self._start_motion(figure))      # a scene stands at its end
                    key = inherited
        except Exception as exc:  # noqa: BLE001
            print(f"LESSON_NOTE: the last chapter's picture was not carried over ({type(exc).__name__}: {str(exc)[:120]})", flush=True)
            if figure is not None:
                self.remove(figure)
            figure, key = None, None
        words = VGroup()
        try:
            steps = [dict(s) for s in last.get("steps") or [] if str(s.get("show", "")).strip()]
            if not steps:
                steps = [{"say": "", "show": last[k], "kind": kind}
                         for k, kind in (("board_text", "key"), ("equation", "math")) if last.get(k)]
            if steps:
                plan = self._staged(steps, figure, last)            # no figure: the last beat was words alone
                if plan.get("caption"):
                    kept = [steps[-1]["_mob"]]
                elif plan.get("pinned"):
                    lines = [s["_mob"] for s in steps if not s.get("_pinned")]
                    pages = [s.get("_page", 0) for s in steps if s.get("_pinned")]
                    kept = lines[-1:] + [s["_mob"] for s in steps if s.get("_pinned") and s.get("_page", 0) == (pages[-1] if pages else 0)]
                else:
                    kept = [s["_mob"] for s in steps]
                words = VGroup(*kept)
                if len(words):
                    self.add(words)
        except Exception as exc:  # noqa: BLE001
            print(f"LESSON_NOTE: the last chapter's words were not carried over ({type(exc).__name__}: {str(exc)[:120]})", flush=True)
            words = VGroup()
        # the heading: the last chapter's line fades as this one's comes, over the screen that chapter left
        try:
            title, eyebrow, number, _rule = self._heading
            old = txt(previous["title"], 34)
            if old.width > 11.7:
                old.scale_to_fit_width(11.7)
            old.scale(.5).next_to(eyebrow, RIGHT, buff=.32)
            room = number.get_left()[0] - .3 - old.get_left()[0]
            if old.width > room > .5:
                old.scale_to_fit_width(room).next_to(eyebrow, RIGHT, buff=.32)
            old_number = txt(f"{index:02} / {len(chapters):02}", 18, MUTED).move_to(number)
            self.play(FadeOut(old), FadeOut(old_number), FadeIn(title), FadeIn(number), run_time=.35)
        except Exception as exc:  # noqa: BLE001
            print(f"LESSON_NOTE: the heading was not cross-faded ({type(exc).__name__}: {str(exc)[:120]})", flush=True)
        return words, figure, key

    def construct(self):
        from . import figures as _figures
        self.chapter(self.chapter_id)
        ch = next(c for c in self.lesson["chapters"] if c["id"] == self.chapter_id)
        shown = VGroup()
        self._figure, self._figure_key = None, None
        self._mark_records = []                          # every mark a hand makes in this chapter, with its start and end
        # The picture the chapter before ended on. A chapter is a render of its own, so its first picture was
        # always drawn afresh: in a lesson that keeps ONE diagram throughout, the viewer saw it wiped and
        # drawn again at every chapter heading. When this chapter opens on that same picture, it is there.
        # A chapter that opens with NO picture of its own keeps that one too, as a beat inside a chapter
        # always has: a script whose middle part got no picture was twenty seconds of one line of text.
        chapters = self.lesson["chapters"]
        index = next(i for i, c in enumerate(chapters) if c["id"] == self.chapter_id)
        earlier = [b for c in chapters[:index] for b in c["beats"]]
        before = [b["figure"] for b in earlier if b.get("figure")]
        # ... unless the chapter before ended on a beat that showed NO picture (``"picture": "off"``): then nothing was
        # on screen, and this chapter's picture is drawn in like any other.
        inherited = json.dumps(before[-1], sort_keys=True) if before and earlier[-1].get("picture") != "off" else None
        named = before[-1] if before else None           # the picture the lesson last named, on screen or not
        # A joined lesson opens on the screen the last chapter left (``_carry_over``); that picture is then this
        # chapter's own, and the beats below keep it, morph it or replace it as they would inside a chapter.
        shown, self._figure, self._figure_key = self._carry_over(ch, earlier, inherited)
        for beat in ch["beats"]:
            self.begin(beat["id"])
            if self.CRAFTED and not STILLS and beat is ch["beats"][0] and ch is chapters[0] \
                    and float(self.current.get("lead", .5)) >= TITLE_CARD_SECONDS + .3:
                # the lesson's first beat: the title, then the beat's own lead (a timeline made before this look has no such lead)
                try:
                    self._title_card(TITLE_CARD_SECONDS)
                except Exception as exc:  # noqa: BLE001 - a card that cannot be drawn is not worth a chapter
                    print(f"LESSON_NOTE: the title card was not drawn ({type(exc).__name__}: {str(exc)[:120]})", flush=True)
            if beat is ch["beats"][-1] and self.chapter_id == self.lesson["chapters"][-1]["id"] and self.lesson.get("credits"):
                # Borrowed art is credited once, in the lesson's last beat (most of it is CC BY).
                credit = Text(" · ".join(str(c) for c in self.lesson["credits"])[:150], font=FONT, font_size=13, color=MUTED)
                self.chrome.add(credit.to_edge(DOWN, buff=.1))     # frame furniture: below the stage on purpose
            lead = float(self.current.get("lead", .5))
            steps = [dict(s) for s in beat.get("steps") or [] if str(s.get("show", "")).strip()]
            if not steps:
                first = " ".join(self.current["sentences"][0]["text"].split()[:3])
                steps = [{"say": first, "show": beat[k], "kind": kind}
                         for k, kind in (("board_text", "key"), ("equation", "math")) if beat.get(k)]
            # A figure stays on screen until a DIFFERENT one replaces it: the next beats
            # usually keep talking about the same picture.
            # A beat marked ``"picture": "off"`` is spoken over words alone: the picture that was up has nothing to do
            # with it (a balloon to try at home, spoken over a foot and a ball: ``harness/compose.mend``). The picture
            # leaves for that beat and comes back, drawn in again, with the next beat that is about it.
            off = beat.get("picture") == "off"
            painting = None                              # a drawing being drawn part by part during this beat (_start_paint)
            settled = 0.0                                # ... and the moment its pen-work is done (a hand's marks wait for it)
            named = beat.get("figure") or named
            spec = None if off else beat.get("figure")
            if not spec and not off and named is not None and self._figure is None:
                spec = named
            key = json.dumps(spec, sort_keys=True) if spec else None
            carried = self._figure
            if off:
                figure, fresh = None, False
            elif key is None or (carried is not None and key == self._figure_key):
                figure, fresh = carried, False
            else:
                built = _figures.build(spec, crafted=self.CRAFTED)          # None for a kind outside the inventory
                if built is not None:
                    # what the look says about this picture's timing, read by its own hint plan and change (shape_hints, S3/S5)
                    built.values_spoken, built.staged_steps = self.VALUES_SPOKEN, self.STAGED
                figure, fresh = (built, True) if built is not None else (carried, False)
                if built is not None and hasattr(built, "resume"):
                    # A drawing that is built up by its parts stands as the lesson has left it so far: a chapter is
                    # a render of its own, and the arrows a learner watched being drawn in chapter 3 were gone when
                    # chapter 4 opened (``figures.DiagramFigure.resume``).
                    built.resume(self._pointed_at_before(spec, beat))
            # The picture this chapter takes over from the one before, exactly as that one left it.
            inherits = fresh and carried is None and key == inherited and beat is ch["beats"][0]
            if getattr(figure, "kind", "") in self.DRAWN_FOR_YOU:
                self.small_heading()                 # a prepared drawing gets the taller stage
            if self.staged:
                self._plan_now = self._staged(steps, figure, beat)
            else:
                self._plan_now = None
                self._columns(steps, figure)
            if fresh and spec and hasattr(figure, "hold_back"):
                # A drawing that is drawn WITH the words: the parts later steps bring are held back (it has its place
                # and size now, and is not on screen yet).
                try:
                    figure.hold_back(self._drawn_later(spec, beat), str(spec.get("planned") or ""))
                except Exception as exc:  # noqa: BLE001 - then it is shown as it always was
                    print(f"LESSON_NOTE: the drawing is shown whole ({type(exc).__name__}: {str(exc)[:120]})", flush=True)
            if fresh and spec and hasattr(figure, "annotate"):
                # ... and what a hand wrote on it in earlier beats stands on it (a chapter is a render of its own)
                try:
                    wiped = {mark.get("slot") for mark in (steps[0].get("annotate") if steps else None) or [] if not mark.get("prims")}
                    figure.annotate([mark for mark in self._annotated_before(spec, beat) if mark.get("slot") not in wiped], now=True)
                except Exception as exc:  # noqa: BLE001
                    print(f"LESSON_NOTE: the drawing's earlier marks could not be put back ({type(exc).__name__}: {str(exc)[:120]})", flush=True)
            self._step_paint = None
            caption = bool(self._plan_now and self._plan_now["caption"])
            pinned = bool(self._plan_now and self._plan_now.get("pinned"))
            self._measured = self._measure(steps, figure, self._plan_now) if STILLS else None
            # Written into the chapter's record, for whoever looks at its frames afterwards (harness/vision_review.py):
            # with one line of words at a time, a line that has gone is not a line that is missing.
            self._beat_layout = {"frame": "stage", "mode": self._plan_now["mode"],
                                 "words": "caption" if caption else "pinned" if pinned else "board" if self._plan_now["board"] else "list"} \
                if self._plan_now else {"frame": "columns", "mode": "side", "words": "list"}
            if getattr(figure, "_staged", False):
                self._beat_layout["built"] = True        # the drawing is being drawn with the words: parts are still to come
            speech = max(self.current["speech_end"] - lead, .5)
            # When each step is due (scene clock), so no animation runs into the next cue.
            due, afters, cursor, located = [], [], 0.0, []
            for i, step in enumerate(steps):
                afters.append(cursor)          # each step is looked for after the one before it
                found = self.locate(step.get("say", ""), after=cursor)
                located.append(bool(found))     # False: its moment is a guess (an even spread), not a place in the speech
                if found:
                    cursor = found[0]
                    offset = found[0] - (CUE_LEAD if found[1] == "aligned" else 0.0)
                else:
                    offset = cursor = max(cursor, lead + speech * i / max(1, len(steps)))
                due.append(self.beat_start + max(0.0, offset))
            revealed = []
            voice = None                                 # a number being moved by the voice in this beat (``_start_tween``)
            if off and carried is not None:
                self.play(FadeOut(Group(*shown, carried)), run_time=.3)
                shown = VGroup()
                self._figure, self._figure_key = None, None
            if fresh:
                first_due = min(due) if due else self.beat_start + self.current["duration"]
                room = first_due - self.renderer.time - .05
                if not inherits:
                    self._hold_back_named(figure, carried, first_due)
                    self._hold_back_steps(figure, steps, due, first_due)
                change = figure.change_from(carried) if carried is not None and hasattr(figure, "change_from") else []
                # A number that moves across the sentence that says it (S9): the step is flagged ``tween: "voice"`` by the kit,
                # its words were found in the speech, and a render of stills has no clock to move by.
                if change and not STILLS:
                    window = self._voice_window(steps, due, located)
                    if window is not None:
                        voice = self._start_tween(carried, change[0], *window, figure=figure)
                if voice is not None:
                    # The new picture is in place under the old one at once; the old one is morphed by the voice and goes when
                    # the sentence is over (``_start_tween``), so what the beat's steps do to the new picture is never fought.
                    if len(shown):
                        self.play(FadeOut(shown), run_time=.25)
                    self.add(figure)
                    self.bring_to_front(carried)
                elif change:
                    # The picture CHANGES part by part (a reaction: new molecules grow, then the counts roll over),
                    # in the lead-in; what the picture showed before is then replaced by the figure as one mobject.
                    if len(shown):
                        self.play(FadeOut(shown), run_time=.25)
                        room -= .25
                    # Slow enough to SEE a molecule grow and a count roll over (0.25 s each was a blink); the
                    # voice's own count of the new numbers is lit by the hints a moment later.
                    each = min(1.4, max(.45, (room + .3) / len(change)))   # at most 0.3 s into the words
                    for anim in change:
                        self.play(anim, run_time=each)
                    self.remove(carried, *[m for m in self.mobjects if m in figure.get_family()])
                    self.add(figure)
                elif carried is not None and self._only_a_hold_differs(figure, carried, spec):
                    # The same speed-time graph with a quiz's answer drawn or not (``hold_marks``): the picture is the same
                    # everywhere else, so it is swapped, not morphed (a morph smeared every label for a second).
                    if len(shown):
                        self.play(FadeOut(shown), run_time=min(.3, max(.12, room)))
                    self.remove(carried)
                    self.add(figure)
                elif carried is not None and getattr(carried, "kind", None) == getattr(figure, "kind", "") \
                        and not hasattr(figure, "focus_animations"):
                    # Same kind of picture: it CHANGES (a side gets its value, a bar is re-cut).
                    self.play(ReplacementTransform(carried, figure), *([FadeOut(shown)] if len(shown) else []),
                              run_time=min(.9, max(.4, room)))
                else:
                    leaving = Group(*shown, *([carried] if carried is not None else []))   # a figure may hold images
                    crossing = []
                    if len(leaving) and self.CRAFTED and not STILLS and not getattr(figure, "bleeds", False) and not inherits:
                        # crafted: the old picture fades while the new one is drawn over it (one play below), not first
                        # fading to nothing and then being drawn (a blank card for the 0.3 s and the whole lead-in)
                        crossing = [FadeOut(leaving, run_time=.4)]
                    elif len(leaving):
                        self.play(FadeOut(leaving), run_time=.3)
                        room -= .3
                    if getattr(figure, "bleeds", False):
                        self.add(figure)                 # under the heading and the words from its first frame
                        self.bring_to_back(figure)
                    if inherits:
                        self.add(figure)                 # on screen when the last chapter ended: not drawn again
                        self._stop_motion(self._start_motion(figure))        # ... and a scene stands at its end
                    else:
                        # A prepared drawing that can be drawn part by part: its card comes, and the pen-work runs
                        # beside the beat's first words (``_start_paint``). Otherwise the figure is drawn in the
                        # beat's lead-in, before the first word about it.
                        if self.PAINTED and not STILLS and hasattr(figure, "paint") and getattr(figure, "_sequence", None):
                            self.play(FadeIn(figure.card), *crossing, run_time=min(.3, max(.12, room)))
                            crossing = []
                            self.add(figure)
                            painting = self._start_paint(figure, max(1.5, self.beat_start + self.current["duration"] - self.renderer.time - .4))
                            if painting is not None:
                                settled = self.renderer.time + float((getattr(self, "_beat_layout", None) or {}).get("painted") or 0.0)
                        if painting is None:
                            self.play(_figures.construct_animation(figure, run_time=min(1.5, max(.45, room))), *crossing)
                            crossing = []
                        # Drawing it put its PARTS into the scene one by one, in the order they were drawn;
                        # anything animated later (a label, its plate, a lit layer) was then stacked in the
                        # order it happened to be animated, not in the figure's own. A label's white plate
                        # arrived after its words and covered them in the one chapter that drew the diagram,
                        # while the chapters that took it over whole were right. Now the figure is one mobject.
                        self.add(figure)
                    if getattr(figure, "bleeds", False):
                        self.bring_to_back(figure)
                shown = VGroup()
                self._figure, self._figure_key = figure, key
            if figure is not None:
                revealed.append(figure)
            # A scene is played ONCE, by the beat it was written for: its stages are that beat's steps. A later
            # beat that keeps the picture up finds it as it ended. (It used to start again in every beat, so
            # blocks that had been counted vanished and reappeared under words about something else.)
            motion = self._start_motion(figure, due) if fresh and not inherits else None
            # What a hand adds to the drawing in this beat, each mark when its own words are spoken (harness/annotate.py)
            marking = self._start_marks(figure, self._marks_due(steps, due, figure, settled)) if figure is not None and hasattr(figure, "annotate") else None
            self._beat_now = beat
            hinting = self._start_hints(figure) if figure is not None else None
            previous_math, halo = None, None
            standing = list(shown)                # the words on screen now (in caption mode: the one line before this)
            line_now, kept_now, page_now = None, [], 0   # ``pinned``: the one line of words up, and the working that stays
            for i, step in enumerate(steps):
                mob = step["_mob"]
                spread = lead + speech * i / max(1, len(steps))
                turns = pinned and step.get("_pinned") and step.get("_page", 0) != page_now
                if turns:
                    previous_math = None           # a new screen of working: nothing grows out of a line that is leaving
                enter, extra = self._entrance(step, mob, figure, previous_math)
                if caption:
                    if self._plan_now["mode"] == "bleed":
                        enter = FadeIn(mob, shift=UP * .12)
                    animations = [Succession(FadeOut(VGroup(*standing), shift=UP * .12), enter)] if standing else [enter]
                    standing = [mob]
                elif pinned:
                    leaving = list(shown) if i == 0 else []
                    if step.get("_pinned"):
                        if turns:
                            leaving, kept_now, page_now = leaving + kept_now, [], step.get("_page", 0)
                        animations = [m.animate.set_opacity(self.RECEDE) for m in kept_now]     # the working before it recedes
                        kept_now = kept_now + [mob]
                    else:
                        leaving, line_now, animations = leaving + ([line_now] if line_now is not None else []), mob, []
                    animations = [Succession(FadeOut(VGroup(*leaving), shift=UP * .12), enter) if leaving else enter] + animations
                else:
                    animations = [Succession(FadeOut(shown), enter)] if (i == 0 and len(shown)) else [enter]
                animations += extra
                # The part being talked about STAYS marked until the talk moves on. Indicate alone is a
                # half-second pulse: a viewer who looks up a moment late sees an unmarked picture.
                part = None
                if figure is not None and not hasattr(figure, "focus_animations") and step.get("focus"):
                    part = (getattr(figure, "parts", None) or {}).get(str(step["focus"]))
                ring = outline_of(part) if part is not None else None
                if ring is not None:
                    animations += [FadeIn(ring)] + ([FadeOut(halo)] if halo is not None else [])
                    halo = ring
                if not caption and not pinned:
                    animations += [m.animate.set_opacity(self.RECEDE) for m in revealed if m is not figure]
                later = [d for d in due[i + 1:] if d > due[i]]
                room = (min(later) - max(due[i], self.renderer.time)) if later else 99.0
                if step.get("draw") and getattr(figure, "_staged", False):
                    # until the next line's words, or the beat's end: the pen never runs into the next thing said
                    until = min(room, self.beat_start + self.current["duration"] - max(due[i], self.renderer.time)) - .15
                    animations.append(Later(lambda numbers=list(step["draw"]), until=until: self._draw_with(figure, numbers, until)))
                # Steps due at the SAME words (a heading and its first line, both on a beat's opening phrase) enter
                # quickly one after another: at 0.9 s each the second came 0.65 s after its words in 10 of 20 filmed
                # lessons, and every one of them failed the lateness check (2026-10-20).
                twins = sum(1 for d in due[i + 1:] if abs(d - due[i]) < .05)
                run = min(.9, max(.3, room - .05)) if not twins else .35
                self.cue(step.get("say", ""), *animations, run_time=run, fallback=spread, after=afters[i])
                if STILLS and step.get("annotate") and hasattr(figure, "annotate"):
                    try:                                 # a still has no clock: a step's marks are there with the step
                        for mark in step["annotate"]:
                            figure.annotate([mark], now=True)
                            self._note_mark(figure, mark, self.renderer.time)
                    except Exception as exc:  # noqa: BLE001
                        print(f"LESSON_NOTE: a mark could not be made on the drawing ({type(exc).__name__}: {str(exc)[:120]})", flush=True)
                if STILLS:
                    self._reveal_to_step(figure, i)
                self.still("step", step=i)
                left_in_beat = self.beat_start + self.current["duration"] - self.renderer.time
                until_next = (min(later) - self.renderer.time) if later else left_in_beat
                if step.get("highlight") and left_in_beat > 1.3 and until_next > 1.1:
                    # The box may not reach into a neighbouring step: in a tightly packed column
                    # its edge crossed the next line of text (one counted finding on a real lesson).
                    beside = [] if caption else (kept_now + ([line_now] if line_now is not None else [])) if pinned \
                        else [s["_mob"] for s in steps]
                    gaps = [abs(o.get_center()[1] - mob.get_center()[1]) - (o.height + mob.height) / 2
                            for o in beside if o is not mob and abs(o.get_center()[0] - mob.get_center()[0]) < 3]
                    buff = min(.14, max(.03, (min(gaps) if gaps else 1.0) / 2 - .02))
                    box = SurroundingRectangle(mob, color=GOLD, buff=buff, corner_radius=min(.08, buff), stroke_width=3)
                    self.play(Create(box), run_time=.5)
                    self.play(FadeOut(box), run_time=.5)
                if step.get("kind") == "math":
                    previous_math = mob
                revealed.append(mob)
            if not steps and len(shown):
                self.play(FadeOut(shown), run_time=.5)
            if halo is not None:
                self.remove(halo)                # the mark belongs to this beat's talk, not to the picture
            if STILLS and figure is not None and getattr(figure, "_late", None):
                self._show_late(figure, 0.0, everything=True)       # the beat's last screen has every part
            step_mobs = [m for m in revealed if m is not figure]
            if caption:
                step_mobs = [m for m in step_mobs if m in standing]      # only the last line is still there
            elif pinned:                                                  # the one line of words, and this screen's working
                step_mobs = [m for m in step_mobs if m is line_now or any(m is k for k in kept_now)]
            paused = False
            if float(self.current.get("thinking_pause_seconds") or 0) >= 2.5:
                paused = self._pause(beat, step_mobs, figure)
            if not paused and len(step_mobs) > 1:
                # Bring the whole beat back to full strength for the closing hold, so a
                # viewer who looks up late can still read everything that was said.
                remaining = self.beat_start + self.current["duration"] - self.renderer.time
                if remaining > .7:
                    self.play(*[m.animate.set_opacity(1) for m in step_mobs[:-1]], run_time=.5)
            if paused and self.CRAFTED:
                step_mobs = []                         # a crafted pause took the steps away for good
            shown = VGroup(*step_mobs)                 # the figure outlives the beat
            if marking is not None or hinting is not None or getattr(self, "_step_paint", None):
                # What a hand is still to write, and a part still being drawn, have the rest of the beat: the voice goes
                # on after the last line has come up. (Stopped here, a value said in a beat's last sentence was written
                # in a jump the moment the last line arrived, and a ring left six seconds before its beat ended.)
                self.until(self.beat_start + self.current["duration"] - .1)
            self._stop_marks(marking)
            self._stop_hints(hinting)
            if figure is not None and hasattr(figure, "clear_gesture"):
                try:
                    figure.clear_gesture()               # a ring or an arrow belongs to its beat; what was written stays
                    self._note_mark(figure, None, self.renderer.time)
                    figure.sweep()
                except Exception as exc:  # noqa: BLE001 - tidying up must not end a chapter
                    print(f"LESSON_NOTE: a beat's marks could not be cleared ({type(exc).__name__}: {str(exc)[:120]})", flush=True)
            self._stop_paint(getattr(self, "_step_paint", None))
            self._step_paint = None
            self._stop_paint(painting)
            self._stop_motion(motion)
            if voice is not None:
                self.until(voice[3])             # the move is the sentence's: it runs to the end of it, past the last step's entrance
            self._stop_tween(voice)
            self.finish()
        self.done()
