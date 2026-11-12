"""How a lesson looks: the frame its chapters are laid out in, where its captions are shown, the page it is drawn on.

No drawing happens here. Three places have to agree on a lesson's look and only one of them is a renderer:

* the service decides it when a lesson is MADE and writes it into ``lesson.json`` (``for_new``);
* the chapter runtime reads it back in every render of that lesson, the first and any later one (``of``): a lesson
  rendered again next month, for a new voice or a repair, comes out in the frame it was made and checked in;
* whoever prepares a picture has to know the box it will be shown in (``picture_boxes``).

A ``lesson.json`` that says nothing is a lesson made before 2026-10-10 and renders as every lesson did until then
(``BEFORE``): picture left, a column of steps right, a band kept free for captions, the dark page.

The owner, 2026-10-10, of that frame: "one side image and another side text … is not giving good look", and on the
five decisions that followed (the new frame for new lessons; captions under the video in the app; the light page):
"Yes for all". So a lesson made now is ``stage``, with no band, and on the light page when every picture in it is a
prepared drawing. ``HARNESS_FRAME=columns`` in ``.env`` makes new lessons as they were: the old frame is one setting away.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

#: ``stage``: the picture takes what the frame can give it and the words what is left, one line at a time.
#: ``columns``: picture left and a column of steps right.
FRAMES = ("stage", "columns")
#: ``outside``: the player shows captions under the video, so the frame keeps no band for them. ``band``: the foot of
#: the frame is left empty for the browser's own captions.
CAPTIONS = ("outside", "band")
#: ``paper``: a light page (a prepared drawing is made for white paper). ``night``: the dark page.
PAGES = ("paper", "night")
#: ``fill``: a picture drawn by code (a figure, a model-written scene) is enlarged to the room the frame has for it,
#: its strokes with it. ``kept``: it stays the size it was first given (a scene drawn small stands small in a large
#: stage). A lesson gets ``fill`` only when a preview of it shows no fault that ``kept`` does not have
#: (``harness/compose.py``): enlarging is tried, never assumed.
PICTURES = ("fill", "kept")
#: How a beat that works something out beside a picture shows its lines. ``pinned``: the WORKING (formula lines) stays
#: and grows, the words come one at a time above it, large, and working that no longer fits makes room by leaving
#: (a new screen) instead of everything being shrunk. ``column``: every line of the beat, words and working alike,
#: piles up in one column of small type (how the stage frame began on 2026-10-10: 290 of 605 beats in 43 lessons
#: were such a column of 30-point lines, which is under ten points on a phone).
WORKING = ("pinned", "column")
#: How a prepared drawing that is shown whole arrives. ``painted``: it is DRAWN, part by part, from the sequence of its
#: SVG's parts (``harness/sequence.py``, ``figures.PictureFigure.paint``), while the voice begins. ``shown``: it
#: fades in whole, as every drawing did until 2026-10-12 (the owner: "the visuals are static").
DRAWINGS = ("painted", "shown")
#: What happens where one chapter ends and the next begins, and between beats. ``carried``: the next chapter opens on
#: the screen the last one left (its picture, the last words, the heading cross-fading), the picture changes from
#: there, and the silences between beats are shorter. ``cut``: each chapter starts on an empty stage after a hard cut,
#: with about two seconds of silence at the join (doc 12: ten points of a lesson's 40% silent time were those joins;
#: the owner, 2026-10-15: "a somewhat choppy experience. It is not continuous").
JOINS = ("carried", "cut")
#: How formulas are set. ``sans``: in a sans-serif face beside the sans-serif words (``sfmath``), so a line of working
#: and a line of words read as one hand. ``serif``: Computer Modern, as every lesson until 2026-10-17 (LGLG, of the
#: three remakes of 2026-10-16: "the visuals are not good"; one fault named was "4/3 original, and 8/6 = 4/3 doubled"
#: set in a small serif face beside large sans words).
MATHS = ("sans", "serif")
#: When a number written beside an angle's arc in a geometry picture appears. ``named``: with the arc, at the first word that
#: names the angle ("angle DAB" shows the arc AND its 50), as every lesson did until 2026-11-09. ``spoken``: the arc and its
#: letters at the name, the number at the word that says it, and a sum line under the picture at the word that says the total
#: (video-quality plan S3: 50 degrees stood on the screen 16 s before the voice said it).
VALUES = ("named", "spoken")
#: How a finished graph, a table or a verdict arrives on a beat. ``whole``: with the picture, as it was until 2026-11-09 (a
#: motion graph arrived with every point and its value, a reaction with its atom table and its verdict, 13 to 24 s before the
#: voice got there). ``steps``: each such part is drawn in at the step whose words bring it (video-quality plan S5), and a
#: reaction's old table and verdict leave before its molecules move.
STAGING = ("whole", "steps")
#: Craft at a lesson's edges and its pauses (video-quality plan S11). ``plain``: as every lesson was until 2026-11-09 (the first
#: beat opens on its picture, the last holds 0.6 s, one beat gives way to the next by fading out and then drawing, a thinking
#: pause's card fades in over the steps it hides and gives them back, stale, before the next beat takes them away).
#: ``crafted``: a 2 s title card opens the lesson, the last beat holds 3 s, a new picture is drawn while the old one fades,
#: a thinking pause takes the steps away first and does not give them back, shows the options as words and labels its
#: countdown, and a speed-time graph whose speeds are never negative starts at 0.
CRAFT = ("plain", "crafted")
#: Every lesson made before 2026-10-10, and what a ``lesson.json`` that does not say is taken to be.
BEFORE = {"frame": "columns", "captions": "band", "page": "night", "pictures": "kept", "working": "column", "drawings": "shown",
          "joins": "cut", "math": "serif", "values": "named", "staging": "whole", "craft": "plain"}
#: Pictures that are a finished drawing made for white paper (``figures.DiagramFigure``, ``figures.PictureFigure``).
#: Everything else is drawn by code in colours chosen for the dark page.
DRAWN_FOR_YOU = ("diagram", "picture")

# The stage of the ``stage`` frame in scene units (the frame is 14.22 wide and 8 high): under the one line of heading,
# and down to the captions' band or, with captions outside, nearly to the frame's foot.
STAGE_SIDES = (-6.8, 6.8)
STAGE_TOP = 3.2
STAGE_FOOT = {"band": -2.65, "outside": -3.8}
WORDS = 3.9          # the column for one line of words at a time, beside a picture
BOARD = 4.9          # ... and for working that grows line by line (formula steps)
LINE = 1.25          # the strip for one line of words above a wide picture
GAP = .4
#: The old frame's box for a prepared drawing (``GuidedChapter.DRAWING_BOX``).
COLUMNS_DRAWING = (8.85, 5.7)


def _one_of(value, allowed: tuple, default: str) -> str:
    value = str(value or "").strip().lower()
    return value if value in allowed else default


def read(lesson_dir) -> dict | None:
    """The lesson in a folder, or None: a look is read at a renderer's start, where nothing may raise."""
    try:
        lesson = json.loads((Path(str(lesson_dir)) / "lesson.json").read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return None
    return lesson if isinstance(lesson, dict) else None


def of(lesson: dict | None, environ=None) -> dict:
    """The look ONE lesson is rendered with: what its ``lesson.json`` says, and ``BEFORE`` for whatever it does not.

    A trial may override it for one render without touching the lesson: ``LESSONFORGE_FRAME`` (stage, columns),
    ``LESSONFORGE_CAPTION_BAND`` (0: no band), ``LESSONFORGE_THEME`` (paper, night), ``LESSONFORGE_PICTURES`` (fill,
    kept), ``LESSONFORGE_WORKING`` (pinned, column), ``LESSONFORGE_DRAWINGS`` (painted, shown), ``LESSONFORGE_JOINS``
    (carried, cut), ``LESSONFORGE_VALUES`` (named, spoken) and ``LESSONFORGE_STAGING`` (whole, steps) and ``LESSONFORGE_CRAFT`` (plain, crafted). The old frame has its band built into its boxes and knows none of the last four, so ``columns`` is
    always ``band``, ``kept``, ``column``, ``shown``, ``cut``.
    """
    environ = os.environ if environ is None else environ
    said = lesson.get("look") if isinstance(lesson, dict) and isinstance(lesson.get("look"), dict) else {}
    look = {"frame": _one_of(said.get("frame"), FRAMES, BEFORE["frame"]),
            "captions": _one_of(said.get("captions"), CAPTIONS, BEFORE["captions"]),
            "page": _one_of(said.get("page"), PAGES, BEFORE["page"]),
            "pictures": _one_of(said.get("pictures"), PICTURES, BEFORE["pictures"]),
            "working": _one_of(said.get("working"), WORKING, BEFORE["working"]),
            "drawings": _one_of(said.get("drawings"), DRAWINGS, BEFORE["drawings"]),
            "joins": _one_of(said.get("joins"), JOINS, BEFORE["joins"]),
            "math": _one_of(said.get("math"), MATHS, BEFORE["math"]),
            "values": _one_of(said.get("values"), VALUES, BEFORE["values"]),
            "staging": _one_of(said.get("staging"), STAGING, BEFORE["staging"]),
            "craft": _one_of(said.get("craft"), CRAFT, BEFORE["craft"])}
    look["frame"] = _one_of(environ.get("LESSONFORGE_FRAME"), FRAMES, look["frame"])
    look["drawings"] = _one_of(environ.get("LESSONFORGE_DRAWINGS"), DRAWINGS, look["drawings"])
    look["pictures"] = _one_of(environ.get("LESSONFORGE_PICTURES"), PICTURES, look["pictures"])
    look["working"] = _one_of(environ.get("LESSONFORGE_WORKING"), WORKING, look["working"])
    look["joins"] = _one_of(environ.get("LESSONFORGE_JOINS"), JOINS, look["joins"])
    look["math"] = _one_of(environ.get("LESSONFORGE_MATH"), MATHS, look["math"])
    look["values"] = _one_of(environ.get("LESSONFORGE_VALUES"), VALUES, look["values"])
    look["staging"] = _one_of(environ.get("LESSONFORGE_STAGING"), STAGING, look["staging"])
    look["craft"] = _one_of(environ.get("LESSONFORGE_CRAFT"), CRAFT, look["craft"])
    if str(environ.get("LESSONFORGE_CAPTION_BAND") or "").strip():
        look["captions"] = "outside" if str(environ["LESSONFORGE_CAPTION_BAND"]).strip() == "0" else "band"
    look["page"] = _one_of(environ.get("LESSONFORGE_THEME"), PAGES, look["page"])
    if look["frame"] == "columns":
        look["captions"], look["pictures"], look["working"], look["drawings"], look["joins"] = "band", "kept", "column", "shown", "cut"
        look["math"], look["craft"] = "serif", "plain"
    return look


def drawn_only(lesson: dict | None) -> bool:
    """Whether a lesson has pictures and every one of them is a prepared drawing (so it can stand on the light page)."""
    kinds = {str((beat.get("figure") or {}).get("kind") or "") for chapter in (lesson or {}).get("chapters") or []
             for beat in chapter.get("beats") or [] if isinstance(beat.get("figure"), dict)}
    kinds.discard("")
    return bool(kinds) and kinds <= set(DRAWN_FOR_YOU)


def for_new(lesson: dict | None = None, environ=None) -> dict:
    """The look a lesson made NOW is given (the service writes it into the lesson; ``of`` reads it back).

    ``HARNESS_FRAME`` (stage; ``columns`` makes new lessons exactly as before), ``HARNESS_CAPTIONS`` (outside; ``band``
    when the player draws captions over the picture) and ``HARNESS_PAGE`` (auto: the light page for a lesson whose
    pictures are all prepared drawings, the dark page for any lesson with a code-drawn figure or a model-written
    scene, whose colours were chosen for the dark page; or paper / night for every lesson). Without a lesson the
    page is the dark one: nothing that asks before the lesson exists depends on it. ``HARNESS_WORKING`` (pinned;
    ``column`` for the column of small lines), ``HARNESS_JOINS`` (carried; ``cut`` for a hard cut and two seconds of
    silence at every chapter's start, as before 2026-10-15), ``HARNESS_MATH`` (sans; ``serif`` for Computer Modern),
    ``HARNESS_VALUES`` (spoken; ``named`` shows an angle's number with its arc) and ``HARNESS_STAGING`` (steps; ``whole`` shows a
    finished graph or table with its picture) and ``HARNESS_CRAFT`` (crafted; ``plain`` for no title card or closing hold). ``pictures`` starts as ``kept``: whether a lesson's code-drawn
    pictures are enlarged is settled by previewing THAT lesson (``harness/compose.settle``), not here.
    """
    environ = os.environ if environ is None else environ
    if _one_of(environ.get("HARNESS_FRAME"), FRAMES, "stage") == "columns":
        return dict(BEFORE)
    page = _one_of(environ.get("HARNESS_PAGE"), PAGES, "")
    return {"frame": "stage", "captions": _one_of(environ.get("HARNESS_CAPTIONS"), CAPTIONS, "outside"),
            "page": page or ("paper" if drawn_only(lesson) else "night"), "pictures": "kept",
            "working": _one_of(environ.get("HARNESS_WORKING"), WORKING, "pinned"),
            "drawings": _one_of(environ.get("HARNESS_DRAWINGS"), DRAWINGS, "painted"),
            "joins": _one_of(environ.get("HARNESS_JOINS"), JOINS, "carried"),
            "math": _one_of(environ.get("HARNESS_MATH"), MATHS, "sans"),
            "values": _one_of(environ.get("HARNESS_VALUES"), VALUES, "spoken"),
            "staging": _one_of(environ.get("HARNESS_STAGING"), STAGING, "steps"),
            "craft": _one_of(environ.get("HARNESS_CRAFT"), CRAFT, "crafted")}


def stage_bounds(look: dict) -> tuple[float, float, float, float]:
    """(x0, x1, y0, y1) the ``stage`` frame holds a chapter to: what the end-of-beat bounds check measures against."""
    return STAGE_SIDES[0], STAGE_SIDES[1], STAGE_FOOT[_one_of(look.get("captions"), CAPTIONS, "band")], STAGE_TOP


def stage_box(look: dict) -> tuple[float, float, float, float]:
    """(x0, x1, y0, y1) the picture and its words are laid out in: the stage, less a margin."""
    x0, x1, y0, y1 = stage_bounds(look)
    return x0 + .15, x1 - .15, y0 + .08, y1 - .12


def picture_boxes(look: dict | None = None) -> list[tuple[float, float]]:
    """The boxes (width, height in scene units) a prepared drawing can be given; it is shown in the one it fills most.

    For the ``stage`` frame: beside a column of words, or under a strip of them (``GuidedChapter._stage_plan``, which
    lays out by these same numbers). For ``columns`` the one box that frame has. With no look named: the look a
    lesson made now gets, which is what a picture being prepared for a new lesson will be shown in.
    """
    look = for_new() if look is None else look
    if _one_of(look.get("frame"), FRAMES, BEFORE["frame"]) != "stage":
        return [COLUMNS_DRAWING]
    x0, x1, y0, y1 = stage_box(look)
    width, height = x1 - x0, y1 - y0
    return [(round(width - WORDS - GAP, 3), round(height, 3)), (round(width, 3), round(height - LINE - GAP, 3))]
