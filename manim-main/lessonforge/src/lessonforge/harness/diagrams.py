"""A labelled diagram, taken apart so a lesson can point at its parts.

Model-drawn pictures of real things (a cell, a heart, a flower) were the weakest frames
of the first pilots, and a good drawing of each already exists. This module fetches one
as SVG and turns it into what the renderer needs: exact picture layers and the names of
the parts. Evidence and the measurements behind each rule:
``docs/research/approaches/07_composition_and_pictures.md`` (5b).

Three decisions, each taken from a test on a real diagram:

* **A browser draws, Manim animates.** Manim's ``SVGMobject`` loaded an animal cell of
  5,510 shapes without an error and drew it with heavy black outlines, holes and no
  labels; a shaded football came out as a black disc. So the SVG is split by code into
  its top-level groups and a headless browser draws the whole art and each group alone
  on a transparent ground, all from the same view box, so the layers register exactly.
* **The parts name themselves.** A diagram's own labels say what its parts are called,
  and each label's pointer line ends on, or just short of, its part. Walking a few
  pixels on from the pointer's end and taking the smallest layer found there gave nine
  of thirteen labels of that cell a layer of their own. A label that lands only on the
  largest layer (the cell body) has no layer to lift out: its part is ``None`` and the
  renderer rings the pointer's end.
* **The diagram's words are dropped, its names kept.** Manim cannot draw SVG text, and we
  want labels in the lesson's language at a size a phone can read, appearing when they
  are spoken. So the text is removed from the art and comes back as data.

Two kinds of drawing come back from the service, and both end as the same manifest:

* an **office export** (the animal cell): groups of shapes, each label a text with a
  pointer line. The pointer names the part, as above;
* a **flat poster** (the water cycle): shapes straight under ``<svg>``, and for each
  process a rounded box of words with the arrows it is about drawn just before it in
  the file, often in the box's own colour. There the box becomes the label (its heading
  only: the rest is said by the voice, and words at 17 px of 1180 cannot be read in a
  video), the box is taken out of the art, and its arrows are the part that lights up.

A flat drawing may also label a thing with **words beside it and no box** (a ray
diagram: "Object" in the arrow's own green, "F" beside its dot). Such a label takes the
marks of its own colour: all of them when it is the only label of that colour, else the
one nearest to it and whatever of that colour touches it; nothing when the nearest is
far away (a caption in a corner names no part).

Nothing here raises to its caller: no service address, no browser, an SVG that is refused
or a diagram with no usable labels all return None with a line in the log, and the lesson
is made with the pictures it would have had anyway.

**Using the pieces, not only lighting them** (the owner, 2026-10-09: "current svg is not
being intelligently used by splitting and using at the center … this is a raw way of
using"). Dim-and-light in the left half of the frame was all the first demo did with a
drawing it had gone to the trouble of taking apart. The manifest now carries what each
kind of drawing can really do:

* a poster is BUILT UP: ``base`` is the scene with no process in it, each label's marks
  are drawn in when it is named and stay, and ``flows`` are the paths of its arrows in
  pixels, read from the SVG's own geometry, so that a dot can travel along them (vapour
  rising, rain falling);
* an anatomy drawing is ZOOMED: ``detail`` is a close-up of each named place, drawn
  again by the browser with the SVG's view box on that region, so it is sharp at any
  size (it is a vector drawing; an enlarged screenshot is not);
* a wide two-panel picture has its ``panels`` as files, so "after" can wait until the
  lesson has asked what will happen;
* a drawing that names its own parts (``data-part="Evaporation"`` on an element or a
  group) is believed before any of the guessing above.

**What a drawing costs.** The owner's drawing service does not use OpenRouter (the owner, 2026-10-09:
"our API is not using OpenRouter so why is it costing us?"). Earlier that day about twenty
requests were followed by a rise in OpenRouter's count that the app's ledger did not show,
and I took the drawings to be the cause and charged each at 0.25 USD against the cap. That
was an inference from timing and it was wrong: two of the owner's lessons were being narrated
by a paid voice in the same minutes. A request is therefore free unless ``DIAGRAM_COST_ESTIMATE``
is set above 0 (for a service that is one day metered); it is still written to the ledger at
that cost, as kind "diagram", so the number of drawings asked for can be seen.

The licence travels with the manifest (``credit``): art from a library is usually CC BY
and must be credited once in the video.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import shutil
import subprocess
import time
import xml.etree.ElementTree as ET
from pathlib import Path

from .. import knobs
from .. import paths, spend
from ..longform import look as lesson_look            # which frame a new lesson gets, and the boxes it gives a picture

SVG_NS = "http://www.w3.org/2000/svg"
WIDTH = int(os.getenv("DIAGRAM_WIDTH", "1280"))          # pixels the art is drawn at
MAX_SVG_BYTES = 8_000_000
MAX_PARTS = 120
BIG = 0.30                                                # a layer covering more than this is "the body"
REACH = 70 * WIDTH // 1600                                # how far past a pointer's end to look, in pixels
MANIFEST_VERSION = 10         # 2: the art is cropped to what is drawn (art_box), so it fills its card
#                               3: the browser's window is taller than the drawing (the bottom 87 px used to be lost),
#                                  boxes of words become labels with their arrows as the part, and whole.png is kept
#                               4: a layer three or more labels share is the drawing in one piece, not a part
#                               5: a pointer written BEFORE its words is that label's (the heart's names were one place off)
#                               6: a wide two-panel picture is also kept re-laid, one panel under the other
#                               7: what a lesson needs to USE the pieces: a poster's scene without its processes and the
#                                  paths its arrows follow; a close-up of each named place; a picture's panels; data-part
#                               8: where each panel sits in the re-laid drawing (panel_boxes)
#                               9: close-ups share one window shape, at least 1.5 wide for 1 high (frame)
#                              10: an arrow's filled head goes with its arrow (it stood in a poster's scene before the
#                                  arrow was drawn); what another module keeps in a manifest ("typeset") is carried over
KEPT_ACROSS = ("typeset",)    # manifest keys other modules own: carried over when a drawing is taken apart again
WINDOW_MARGIN = 160           # a headless window's page is shorter than --window-size by its own frame
_UNSAFE = re.compile(rb"<\s*script|<\s*foreignObject|<!ENTITY|\son[a-z]+\s*=|javascript:|href\s*=\s*[\"']\s*(?:https?:)?//", re.I)
_CREDIT = re.compile(r"\b(CC[ -]?BY|CC0|public domain|©|\bArt:|licen[cs]e)", re.I)
_LINE_CLASS = ("LineShape", "ConnectorShape")
ET.register_namespace("", SVG_NS)             # so a layer is written back as <svg>, not <ns0:svg>


def slug(name: str) -> str:
    """A part's name as a step's ``focus`` carries it (the same cut ``writer.discipline`` makes)."""
    return re.sub(r"[^a-z0-9_]", "", re.sub(r"[\s\-/]+", "_", str(name).strip().lower()))[:24]


def root(*parts: str) -> Path:
    return paths.sub("library", "diagrams", *parts)


def service_url() -> str:
    return (os.getenv("DIAGRAM_API_URL") or "").strip().rstrip("/")


def browser() -> str | None:
    """The headless browser that draws the layers, or None."""
    named = (os.getenv("LESSONFORGE_CHROME") or "").strip()
    for candidate in ([named] if named else []) + ["google-chrome", "chromium", "chromium-browser"]:
        found = shutil.which(candidate)
        if found:
            return found
    return None


def available() -> bool:
    return bool(service_url()) and browser() is not None


def safe(svg: bytes) -> str | None:
    """Why an SVG is refused, or None. A drawing has no business carrying scripts or outside links."""
    if len(svg) > MAX_SVG_BYTES:
        return f"it is {len(svg) // 1_000_000} MB"
    if b"<svg" not in svg[:4000].lower():
        return "it is not an SVG"
    found = _UNSAFE.search(svg)
    return f"it contains {found.group(0)[:24].decode('latin-1').strip()!r}" if found else None


# ── asking the service ───────────────────────────────────────────────────────

#: The service's own verdict on a drawing, worst first. It returns a drawing even when its checks fail.
QUALITY = ("failed_checks", "review_needed", "student_ready")
POLL_SECONDS = 150.0          # how long a drawing that outlived the waiting request is still asked for


def cost_estimate() -> float:
    """What one drawing is taken to cost in USD (``DIAGRAM_COST_ESTIMATE``, default 0: the owner's own service)."""
    try:
        return max(0.0, float(os.getenv("DIAGRAM_COST_ESTIMATE", "0")))
    except ValueError:
        return 0.0


def service_key() -> str:
    return (os.getenv("DIAGRAM_API_KEY") or "").strip()


def min_quality() -> str:
    """The worst verdict a lesson will still use (``DIAGRAM_MIN_QUALITY``, default review_needed)."""
    asked = (os.getenv("DIAGRAM_MIN_QUALITY") or "review_needed").strip().lower()
    return asked if asked in QUALITY else "review_needed"


SERVICE_TRIES = 2             # asks of the service for ONE request when it fails its own drawing (a new drawing each time)


def fetch(ask: str, klass: int | None = None, language: str = "en", log=print, wait: float = 90.0,
          labels: bool = True, subject: str = "") -> Path | None:
    """The SVG for a request from the owner's diagram service, kept in the library. None on any failure.

    One request that waits (``POST /v1/diagrams?wait=90`` with ``X-API-Key``); a drawing
    that takes longer comes back as an id and is asked for until ``POLL_SECONDS`` have
    passed. ``labels=False`` asks for the drawing alone, for a picture nobody points into.

    The service keeps a result for six hours and its address is a quick tunnel that
    changes, so the copy saved here is the only durable one. A request already answered is
    never sent again. The service returns a drawing even when its own checks failed
    (``quality: failed_checks``): that one is kept beside the others as ``refused.svg`` for
    a person to look at and is never put in a lesson.
    """
    ask = re.sub(r"\s+", " ", str(ask)).strip()[:300]
    if len(ask) < 3:
        return None
    subject = re.sub(r"\s+", " ", str(subject or "")).strip()[:40]
    # The first three parts are the key every diagram already in the library was saved under.
    variant = f"{ask.lower()}|{klass}|{language}" + ("" if labels else "|plain") + (f"|{subject.lower()}" if subject else "")
    key = hashlib.sha256(variant.encode()).hexdigest()[:10]
    folder = root(f"{slug(ask)[:40] or 'diagram'}-{key}")
    saved = folder / "source.svg"
    if saved.is_file() and saved.stat().st_size > 0:
        return saved
    base = service_url()
    if not base:
        log("[diagram] no DIAGRAM_API_URL is set: no diagram was asked for")
        return None
    if cost_estimate() > 0:                      # only a metered service is held to the budget
        try:
            spend.check(cost_estimate(), "a drawing from the diagram service")
        except spend.BudgetExceeded as exc:
            log(f"[diagram] “{ask[:60]}” was not asked for: {str(exc)[:140]}")
            return None
    try:
        import requests  # noqa: PLC0415
        headers = {"X-API-Key": service_key()} if service_key() else {}
        body = {"prompt": ask, "labels": bool(labels), "language": "hi" if str(language).startswith("hi") else "en",
                "min_quality": min_quality()}      # asked for, the service redraws until its own checks pass
        if klass:
            body["class_level"] = int(klass)
        if subject:
            body["subject"] = subject
        out: dict = {}
        for attempt in range(max(1, SERVICE_TRIES)):
            reply = requests.post(f"{base}/v1/diagrams", params={"wait": int(wait)}, json=body, headers=headers, timeout=wait + 30)
            if reply.status_code in (401, 403):
                log("[diagram] the service wants a key: put DIAGRAM_API_KEY in .env" if not headers else "[diagram] the service refused the key in DIAGRAM_API_KEY")
                return None
            if not reply.ok:
                log(f"[diagram] the service refused the request ({reply.status_code})")
                return None
            out, began = reply.json(), time.time()
            # Asked and answered: the service has drawn (and perhaps redrawn), whatever we then make of the drawing.
            spend.record("diagram", "diagram-service", cost_estimate(),
                         note="the owner's own drawing service (not in this budget)" if cost_estimate() == 0 else "diagram",
                         estimated=cost_estimate() > 0)
            job = out.get("id")
            while not out.get("svg") and job and out.get("status") != "failed" and time.time() - began < POLL_SECONDS:
                time.sleep(3)
                out = requests.get(f"{base}/v1/diagrams/{job}", headers=headers, timeout=60).json()
            if out.get("svg") or out.get("status") != "failed" or attempt + 1 >= SERVICE_TRIES:
                break
            # The service draws afresh each time and fails its own drawing now and then: the same words came back
            # "failed checks" and, a minute later, "student ready". One more ask; it costs nothing.
            log(f"[diagram] “{ask[:60]}”: the service failed its own drawing ({str(out.get('detail') or '')[:80]}); asking once more")
        if not out.get("svg"):
            log(f"[diagram] “{ask}”: {out.get('status') or 'no drawing'} {str(out.get('detail') or '')[:100]}")
            return None
        svg = out["svg"].encode("utf-8")
        why = safe(svg)
        if why:
            log(f"[diagram] the SVG was refused: {why}")
            return None
        quality = str(out.get("quality") or "").strip().lower()
        record = {"ask": ask, "class": klass, "language": language, "labels": bool(labels), "subject": subject, "service": base,
                  "fetched": time.strftime("%Y-%m-%d %H:%M"), "sha256": hashlib.sha256(svg).hexdigest(),
                  "visual_type": out.get("visual_type"), "quality": quality, "seconds": out.get("seconds")}
        if quality in QUALITY and QUALITY.index(quality) < QUALITY.index(min_quality()):
            (folder / "refused.svg").write_bytes(svg)
            (folder / "refused.json").write_text(json.dumps(record, indent=1), encoding="utf-8")
            log(f"[diagram] “{ask}”: the service's own checks say {quality.replace('_', ' ')}; kept as refused.svg, not used")
            return None
        saved.write_bytes(svg)
        if out.get("png_base64"):                    # the service's own rendering: what the browser's drawing is compared with
            try:
                import base64  # noqa: PLC0415
                (folder / "source.png").write_bytes(base64.b64decode(out["png_base64"]))
            except (ValueError, OSError):
                pass
        (folder / "source.json").write_text(json.dumps(record, indent=1), encoding="utf-8")
        log(f"[diagram] “{ask}”: drawn by the service in {out.get('seconds')} s "
            f"({out.get('visual_type') or 'diagram'}{', ' + quality.replace('_', ' ') if quality else ''})")
        return saved
    except Exception as exc:  # noqa: BLE001 - a picture is an improvement, never a requirement
        log(f"[diagram] not fetched: {type(exc).__name__}: {str(exc)[:120]}")
        return None


# ── reading the SVG ──────────────────────────────────────────────────────────

def _tag(element) -> str:
    return element.tag.split("}")[-1]


_NOT_DRAWN = ("defs", "title", "desc", "metadata", "style")


def _container(svg_root):
    """The element whose children are the diagram's parts: the group with the most wordless children.

    A drawing exported from an office program arrives wrapped several groups deep, and a
    service may add a group of its own beside it (a credit line). Going down "while there
    is one group to go into" stopped at the wrapper, where the whole drawing is one child.
    The shallowest group wins a tie, so a part made of many shapes is not mistaken for
    the drawing.
    """
    if svg_root.get("data-sorted"):              # it sorted itself (sorted_groups): its own children are the parts
        return svg_root
    best, best_count, queue = svg_root, -1, [(svg_root, 0)]
    while queue:
        node, depth = queue.pop(0)
        kids = [c for c in node if _tag(c) not in _NOT_DRAWN]
        wordless = sum(1 for c in kids if not any(_tag(t) == "text" for t in c.iter()))
        if wordless > best_count and (wordless >= 2 or best_count < 0):
            best, best_count = node, wordless
        if depth < 6:
            queue += [(c, depth + 1) for c in kids if _tag(c) == "g" and any(_tag(t) == "text" for t in c.iter())]
    return best


def _words(element) -> str:
    spans = [s.text.strip() for s in element.iter() if _tag(s) == "tspan" and s.text and s.text.strip()]
    text = " ".join(spans) if spans else " ".join("".join(t.itertext()).strip() for t in element.iter() if _tag(t) == "text")
    return re.sub(r"\s+", " ", text).strip()


def _numbers(text: str) -> list[float]:
    return [float(n) for n in re.findall(r"-?\d+(?:\.\d+)?(?:e-?\d+)?", text or "")]


def _ends(element) -> tuple | None:
    """Both ends of a line-like element in SVG units, or None."""
    for node in element.iter():
        kind = _tag(node)
        if kind == "line":
            try:
                return (float(node.get("x1")), float(node.get("y1"))), (float(node.get("x2")), float(node.get("y2")))
            except (TypeError, ValueError):
                continue
        if kind == "path" and node.get("stroke") not in (None, "none"):
            nums = _numbers(node.get("d"))
            if len(nums) >= 4:
                return (nums[0], nums[1]), (nums[-2], nums[-1])
    return None


def _text_at(element) -> tuple | None:
    for node in element.iter():
        if _tag(node) in ("tspan", "text") and node.get("x") and node.get("y"):
            try:
                return float(_numbers(node.get("x"))[0]), float(_numbers(node.get("y"))[0])
            except (IndexError, ValueError):
                continue
    return None


def _rect(element) -> tuple | None:
    """(x0, y0, x1, y1) of a ``<rect>``, or None."""
    if _tag(element) != "rect":
        return None
    try:
        x, y = float(element.get("x") or 0), float(element.get("y") or 0)
        return x, y, x + float(element.get("width")), y + float(element.get("height"))
    except (TypeError, ValueError):
        return None


def _colour(element, key: str) -> str:
    value = str(element.get(key) or "").strip().lower()
    return "" if value in ("", "none", "transparent") or value.startswith("url(") else value


def _arrow_like(element) -> bool:
    """A stroke with no body (a line, an open path) or an arrowhead (a polygon of three or four corners)."""
    kind = _tag(element)
    if kind in ("line", "polyline"):
        return True
    if kind == "path":
        return not _colour(element, "fill") and bool(_colour(element, "stroke"))
    return kind == "polygon" and len(_numbers(element.get("points"))) <= 8


def _bbox(element) -> tuple | None:
    """(x0, y0, x1, y1) of what an element draws, from its own numbers (absolute coordinates), or None."""
    kind, get = _tag(element), lambda key: float(element.get(key) or 0)  # noqa: E731
    try:
        if kind == "line":
            xs, ys = (get("x1"), get("x2")), (get("y1"), get("y2"))
        elif kind == "circle":
            xs, ys = (get("cx") - get("r"), get("cx") + get("r")), (get("cy") - get("r"), get("cy") + get("r"))
        elif kind == "ellipse":
            xs, ys = (get("cx") - get("rx"), get("cx") + get("rx")), (get("cy") - get("ry"), get("cy") + get("ry"))
        elif kind == "rect":
            xs, ys = (get("x"), get("x") + get("width")), (get("y"), get("y") + get("height"))
        elif kind in ("polygon", "polyline", "path"):
            nums = _numbers(element.get("points") if kind != "path" else element.get("d"))
            xs, ys = nums[0::2], nums[1::2][:len(nums[0::2])]
            if not xs or not ys:
                return None
        elif kind == "g":
            boxes = [b for b in (_bbox(child) for child in element) if b]
            if not boxes:
                return None
            return min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes)
        else:
            return None
    except (TypeError, ValueError):
        return None
    return min(xs), min(ys), max(xs), max(ys)


def _polyline(element, steps: int = 14) -> list[tuple] | None:
    """The centre line of a stroke as points in SVG units, in the direction it is drawn, or None.

    A line, a polyline, or a path of absolute M, L, Q and C commands (what the service
    writes for an arrow). Anything else (arcs, relative commands) gives None: no path is
    better than a wrong one for a dot to run along.
    """
    kind = _tag(element)
    try:
        if kind == "line":
            return [(float(element.get("x1")), float(element.get("y1"))), (float(element.get("x2")), float(element.get("y2")))]
        if kind == "polyline":
            nums = _numbers(element.get("points"))
            return list(zip(nums[0::2], nums[1::2])) if len(nums) >= 4 else None
        if kind != "path":
            return None
        tokens_ = re.findall(r"[A-Za-z]|-?\d+(?:\.\d+)?(?:e-?\d+)?", element.get("d") or "")
    except (TypeError, ValueError):
        return None
    points, i, command = [], 0, ""
    take = {"M": 2, "L": 2, "Q": 4, "C": 6}
    while i < len(tokens_):
        if tokens_[i].isalpha():
            command, i = tokens_[i], i + 1
            if command not in take:
                return None
            continue
        need = take.get(command)
        if not need or i + need > len(tokens_):
            return None
        nums = [float(t) for t in tokens_[i:i + need]]
        i += need
        if command in ("M", "L"):
            points.append((nums[0], nums[1]))
            command = "L"
        elif not points:
            return None
        else:
            x0, y0 = points[-1]
            for k in range(1, steps + 1):
                t = k / steps
                if command == "Q":
                    cx, cy, x1, y1 = nums
                    points.append(((1 - t) ** 2 * x0 + 2 * (1 - t) * t * cx + t * t * x1, (1 - t) ** 2 * y0 + 2 * (1 - t) * t * cy + t * t * y1))
                else:
                    ax, ay, bx, by, x1, y1 = nums
                    points.append(((1 - t) ** 3 * x0 + 3 * (1 - t) ** 2 * t * ax + 3 * (1 - t) * t * t * bx + t ** 3 * x1,
                                   (1 - t) ** 3 * y0 + 3 * (1 - t) ** 2 * t * ay + 3 * (1 - t) * t * t * by + t ** 3 * y1))
    return points if len(points) >= 2 else None


def _gap(a: tuple, b: tuple) -> float:
    """How far apart two boxes are (0 when they touch or overlap)."""
    dx = max(a[0] - b[2], b[0] - a[2], 0.0)
    dy = max(a[1] - b[3], b[1] - a[3], 0.0)
    return (dx * dx + dy * dy) ** 0.5


NEAR = 0.06            # of the drawing's width: a label's own mark is no farther from its words than this
LINK = 0.02            # ... and marks of one colour this close to each other are one thing (an arrow and its head)


def free_marks(children: list, labels: list[dict], width: float, taken: set[int]) -> None:
    """Give each label that is only words beside a thing the marks of its own colour (fills ``marks`` and ``box``).

    ``labels`` here carry ``index`` (their child) and ``at``. A colour only one label has
    owns every mark of that colour; a colour several labels share (the dark grey of "F"
    and "2F") gives each label the mark nearest to its words, with whatever of that
    colour touches it. A label whose nearest mark is farther than ``NEAR`` gets none.
    """
    colour_of = {id(label): _colour(children[label["index"]], "fill") for label in labels}
    shared: dict[str, int] = {}
    for colour in colour_of.values():
        shared[colour] = shared.get(colour, 0) + 1
    drawn = [(k, _bbox(child)) for k, child in enumerate(children)
             if k not in taken and _tag(child) != "text" and not _words(child)]
    for label in labels:
        colour, at = colour_of[id(label)], label.get("at")
        if not colour or not at:
            continue
        mine = [(k, box) for k, box in drawn if box and colour in (_colour(children[k], "stroke"), _colour(children[k], "fill"))
                and ((box[2] - box[0]) < 0.9 * width or _tag(children[k]) == "line")]   # never the ground it stands on
        if not mine:
            continue
        here = (at[0], at[1], at[0], at[1])
        nearest = min(mine, key=lambda item: _gap(here, item[1]))
        if shared[colour] == 1 and _gap(here, nearest[1]) <= 4 * NEAR * width:
            chosen = [k for k, _ in mine]
        elif _gap(here, nearest[1]) <= NEAR * width:
            chosen, grew = [nearest[0]], True
            boxes = dict(mine)
            while grew:                                                    # what touches it, in the same colour
                grew = False
                for k, box in mine:
                    if k not in chosen and any(_gap(box, boxes[c]) <= LINK * width for c in chosen):
                        chosen.append(k)
                        grew = True
        else:
            continue
        label["marks"], label["box"], label["beside"] = sorted(chosen), here, True


_NUMBERING = re.compile(r"^\s*(?:step\s*)?(?:\(?[0-9]{1,2}\)?|\(?[a-h]\))\s*[.:)\-]\s*", re.I)


def _heading(lines: list) -> str:
    """What a box of words is called: its bold line, else a word it gives in brackets, else its first words."""
    bold = next((_words(t) for t in lines if str(t.get("font-weight") or "").lower() in ("bold", "600", "700", "800")), "")
    first = _words(lines[0])
    named = re.search(r"\(([A-Za-z][A-Za-z \-]{2,30})\)", " ".join(_words(t) for t in lines))
    name = bold or (named.group(1) if named else " ".join(first.split()[:3]))
    return _NUMBERING.sub("", name).strip(" .:;,")[:60]


def callouts(children: list, title: str = "") -> list[dict]:
    """Boxes of words in a flat drawing: ``{"rect", "texts", "box", "name", "marks", "title"}`` by child index.

    A box is a ``<rect>`` with the text lines after it that are printed inside it. Its
    marks are what it is ABOUT: the arrows drawn just before it in the file (walking back
    while they are arrow-like and of one colour), and any other stroke anywhere in the
    drawing that has the box's own outline colour (the rain under "Precipitation"). The
    box whose words are the drawing's title is marked so and names nothing.
    """
    lines = [(i, c) for i, c in enumerate(children) if _tag(c) == "text" and _words(c)]
    found, taken = [], set()
    for i, child in enumerate(children):
        box = _rect(child)
        if box is None or (box[2] - box[0]) * (box[3] - box[1]) <= 0:
            continue
        inside = []
        for j, text in lines:
            at = _text_at(text)
            if j > i and j not in taken and at and box[0] <= at[0] <= box[2] and box[1] <= at[1] <= box[3]:
                inside.append(j)
        # the words of a box follow it directly; a rect that merely has text over it somewhere (the sky) is not one
        if not inside or inside[0] != i + 1 or inside != list(range(i + 1, i + 1 + len(inside))):
            continue
        taken.update(inside)
        words = " ".join(_words(children[j]) for j in inside)
        found.append({"rect": i, "texts": inside, "box": box, "name": _heading([children[j] for j in inside]),
                      "stroke": _colour(child, "stroke"), "marks": [],
                      "title": bool(title) and re.sub(r"\W+", " ", words).strip().lower() == re.sub(r"\W+", " ", title).strip().lower()})
    members = {k for c in found for k in [c["rect"], *c["texts"]]}
    claimed: set[int] = set()
    for c in found:
        colour, j = None, c["rect"] - 1
        while j >= 0 and j not in members and j not in claimed and _arrow_like(children[j]):
            mine = _colour(children[j], "stroke") or _colour(children[j], "fill")
            if colour is None:
                colour = mine
            elif mine != colour:
                break
            c["marks"].append(j)
            j -= 1
        claimed.update(c["marks"])
    for c in found:                                   # the box's own colour, anywhere else in the drawing
        if not c["stroke"] or c["title"]:
            continue
        for k, child in enumerate(children):
            if k in members or k in claimed or not _arrow_like(child):
                continue
            # A stroke in the box's colour, or an arrowhead FILLED with it: the head of the water arrow is a
            # triangle with a fill and no stroke, and it stood alone in the scene until its arrow was drawn in
            # (the first lesson on the photosynthesis poster, 2026-10-10).
            stroke = _tag(child) in ("line", "polyline", "path") and _colour(child, "stroke") == c["stroke"]
            head = _tag(child) == "polygon" and not _colour(child, "stroke") and _colour(child, "fill") == c["stroke"]
            if stroke or head:
                c["marks"].append(k)
                claimed.add(k)
        c["marks"].sort()
    return found


GROUPS = ("scene", "arrows", "labels")     # the three groups a drawing may sort itself into (see ``sorted_groups``)


def sorted_groups(svg_root) -> bool:
    """Lay a drawing that has sorted ITSELF into scene / arrows / labels out the way the reader reads. True if it had.

    The owner agreed (2026-10-10) that their drawing service should return a poster as three
    groups instead of leaving this module to guess which stroke belongs to which box of
    words (the guessing put two arrowheads in the scene and once paired every name with its
    neighbour's arrow). What the service is asked to write::

        <g id="scene">   everything that is scenery                                   </g>
        <g id="arrows">  <g data-part="Evaporation"> the arrow, its head, what moves with it </g> ... </g>
        <g id="labels">  <g data-part="Evaporation"> <rect .../> <text>Evaporation</text> <text>...</text> </g> ... </g>

    ``data-part`` is the label's name, the same on a label and on its arrows; a label may
    have no arrows; a group named "title" in ``labels`` is the drawing's title and names
    nothing. Words are ``<text>``. The groups stand directly under ``<svg>`` in that order.

    The reader works on one flat list of children, so the three are opened in place: the
    scene stays one child, each arrow group becomes a child marked ``data-arrow``, and each
    label's box and lines follow it with the box marked ``data-label``. A group's own
    attributes (a transform, a fill) stay on a wrapper so nothing moves or changes colour.
    """
    named = {str(child.get("id") or "").strip().lower(): child for child in svg_root if _tag(child) == "g"}
    if "labels" not in named or "scene" not in named:
        return False
    for key in ("arrows", "labels"):
        group = named.get(key)
        if group is None:
            continue
        carried = {k: v for k, v in group.attrib.items() if k not in ("id", "data-part")}
        at, lifted = list(svg_root).index(group), []
        for child in list(group):
            name = re.sub(r"\s+", " ", str(child.get("data-part") or "")).strip()
            if key == "arrows":
                if carried:                              # keep the group's transform and paint on what leaves it
                    wrapper = ET.Element(f"{{{SVG_NS}}}g", carried)
                    wrapper.append(child)
                    child = wrapper
                child.attrib.pop("data-part", None)
                if name:
                    child.set("data-arrow", name)
                lifted.append(child)
                continue
            pieces = list(child) if _tag(child) == "g" else [child]
            box = next((piece for piece in pieces if _tag(piece) == "rect"), None)
            if box is not None and name:
                box.set("data-label", name)
            for piece in pieces:
                for k, v in {**carried, **{k: v for k, v in child.attrib.items() if k not in ("id", "data-part")}}.items():
                    if _tag(child) == "g" and k not in piece.attrib and k != "transform":
                        piece.set(k, v)                  # paint and font the label group said once for all its lines
                lifted.append(piece)
        svg_root.remove(group)
        for offset, child in enumerate(lifted):
            svg_root.insert(at + offset, child)
    svg_root.set("data-sorted", "1")                 # every later reading of this tree takes its children as they now stand
    return True


def read(svg_path: Path) -> dict | None:
    """The diagram's children sorted into parts, labels (with their pointers) and a credit."""
    try:
        tree = ET.parse(svg_path)
    except (ET.ParseError, OSError):
        return None
    svg_root = tree.getroot()
    box = _numbers(svg_root.get("viewBox"))
    if len(box) != 4 or box[2] <= 0 or box[3] <= 0:
        return None
    sorted_itself = sorted_groups(svg_root)          # scene / arrows / labels, when the drawing says so itself
    container = svg_root if sorted_itself else _container(svg_root)
    children = [c for c in container if _tag(c) not in _NOT_DRAWN]
    parts, labels, used = [], [], set()
    named = next((re.sub(r"\s+", " ", "".join(t.itertext())).strip() for t in svg_root if _tag(t) == "title"), "")
    boxes = callouts(children, named)
    if sorted_itself:
        # What the drawing says wins over every guess: a label's name is the one it gave, and its arrows are the
        # groups that carry that name and nothing else.
        said_arrows: dict[str, list[int]] = {}
        for i, child in enumerate(children):
            if child.get("data-arrow"):
                said_arrows.setdefault(str(child.get("data-arrow")).lower(), []).append(i)
        for words_box in boxes:
            name = re.sub(r"\s+", " ", str(children[words_box["rect"]].get("data-label") or "")).strip()
            if name:
                words_box.update(name=name[:60], marks=sorted(said_arrows.get(name.lower(), [])), title=name.lower() == "title")
            else:
                words_box["marks"] = []
    boxed = {k: c for c in boxes for k in [c["rect"], *c["texts"]]}
    credit = next((w for w in (re.sub(r"\s+", " ", "".join(t.itertext())).strip() for t in svg_root.iter() if _tag(t) == "text")
                   if _CREDIT.search(w)), "")[:200]
    def line_like(k: int) -> bool:
        if not 0 <= k < len(children) or k in used or k in boxed or _words(children[k]):
            return False
        return str(children[k].get("class") or "").endswith(_LINE_CLASS) or _tag(children[k]) in ("line", "polyline")

    def pointer_of(i: int, at) -> int | None:
        """The child that is label ``i``'s pointer line: after its words, or before them.

        An office export writes the words and then the line. The service's own anatomy
        drawings write line, dot, words, so the line AFTER a label belongs to the next
        one: read that way, every name in a heart pointed at its neighbour's place
        (2026-10-09, seen in the first demo's frames). With a line on both sides the one
        that starts level with the words is the label's own.
        """
        near = [k for k in (i + 1, i - 1, i - 2) if line_like(k) and _ends(children[k])]
        if len(near) <= 1 or not at:
            return near[0] if near else None

        def level(k: int) -> float:
            a, b = _ends(children[k])
            end = a if (a[0] - at[0]) ** 2 + (a[1] - at[1]) ** 2 <= (b[0] - at[0]) ** 2 + (b[1] - at[1]) ** 2 else b
            return abs(end[1] - at[1])
        return min(near, key=level)

    art_said = {i for i, child in enumerate(children)
                if sorted_itself and (str(child.get("id") or "").lower() == "scene" or child.get("data-arrow"))}
    for i, child in enumerate(children):
        if i in art_said:                            # the drawing says so: scenery or an arrow, never a label
            continue
        if i in boxed:                               # a box of words: one label, drawn by us; the box leaves the art
            words_box = boxed[i]
            if i == words_box["rect"] and not words_box["title"] and words_box["name"]:
                x0, y0, x1, y1 = words_box["box"]
                labels.append({"name": words_box["name"], "at": ((x0 + x1) / 2, (y0 + y1) / 2), "pointer": None,
                               "marks": words_box["marks"], "box": words_box["box"]})
            continue
        words = _words(child)
        if not words or _CREDIT.search(words):
            continue
        at = _text_at(child)
        k = pointer_of(i, at)
        pointer = _ends(children[k]) if k is not None else None
        if k is not None:
            used.add(k)
            for j in (k - 1, k + 1, i - 1, i + 1):   # the dot drawn at a pointer's end is the pointer's, not the art's
                box_ = _bbox(children[j]) if 0 <= j < len(children) and _tag(children[j]) == "circle" and not _words(children[j]) else None
                if box_ and any(_gap(box_, (e[0], e[1], e[0], e[1])) <= 2.0 for e in pointer) and (box_[2] - box_[0]) <= 0.03 * box[2]:
                    used.add(j)
        labels.append({"name": words[:60], "at": at, "pointer": pointer, "index": i})
    parts = [i for i, child in enumerate(children) if i in art_said or (i not in used and i not in boxed and not _words(child))]
    # What the drawing says about itself comes first: data-part="Evaporation" on an element or a group makes it
    # (with every other child that carries the same name) that part, whatever the guessing below would say.
    said: dict[str, list[int]] = {}
    for i, child in enumerate(children):
        name = re.sub(r"\s+", " ", str(child.get("data-part") or "")).strip()
        if name and not _words(child):
            said.setdefault(name, []).append(i)
    for name, mine in said.items():
        spans = [b for b in (_bbox(children[i]) for i in mine) if b]
        if not spans or any(label["name"].lower() == name.lower() and label.get("marks") for label in labels):
            continue
        box_ = (min(b[0] for b in spans), min(b[1] for b in spans), max(b[2] for b in spans), max(b[3] for b in spans))
        centre = ((box_[0] + box_[2]) / 2, (box_[1] + box_[3]) / 2)
        same = next((label for label in labels if label["name"].lower() == name.lower()), None)
        if same is None:
            same = {"name": name[:60], "at": centre, "pointer": None}
            labels.append(same)
        same.update(marks=sorted(mine), box=same.get("box") or (centre[0], centre[1], centre[0], centre[1]), beside=True, named="data-part")
    claimed = {k for words_box in boxes for k in words_box["marks"]} | set(boxed) | {i for mine in said.values() for i in mine}
    free_marks(children, [label for label in labels if label.get("index") is not None and not label["pointer"]
                          and not label.get("marks")], box[2], claimed)
    if len(parts) > MAX_PARTS:
        # Too many to draw one by one: keep the ones made of the most shapes. Cutting by position
        # kept sixty stray dots that came first in the file and dropped every organelle.
        size = {i: sum(1 for _ in children[i].iter()) for i in parts}
        parts = sorted(sorted(parts, key=lambda i: -size[i])[:MAX_PARTS])
    return {"tree": tree, "container": container, "children": children, "box": box, "parts": parts,
            "labels": labels, "credit": credit}


# ── drawing the layers ───────────────────────────────────────────────────────

def _shot(tree, keep: set[int] | None, width: int, height: int, folder: Path, name: str, chrome: str, words: bool = False,
          view: tuple | None = None):
    """A browser's drawing of the SVG with only some children kept, on a transparent ground (RGBA array).

    ``keep=None`` keeps every child; ``words=True`` leaves the drawing's own text in;
    ``view`` (x, y, width, height in the SVG's own units) draws only that region, filling the picture.
    The window is asked for taller than the drawing and the picture is cut back to size:
    a headless window's page is shorter than ``--window-size`` (87 px here), and until
    2026-10-09 the bottom of every diagram was silently missing.

    Safe to call from several threads and processes at once (a script's pictures are asked
    for three at a time): every call has file names of its own, so two lessons taking the
    same drawing apart do not read each other's page, and a browser profile of its own, so
    nothing depends on the default profile of whoever runs the server. Measured 2026-10-09:
    five drawings taken apart together gave byte-for-byte the pictures of one at a time. (On
    this machine browsers sharing the default profile also all drew, 18 of 18; the profile
    of its own is a precaution, not the cure of a fault that was seen.)
    """
    import tempfile  # noqa: PLC0415
    import uuid  # noqa: PLC0415

    import numpy as np  # noqa: PLC0415
    from PIL import Image  # noqa: PLC0415
    name = f"{name}_{uuid.uuid4().hex[:8]}"             # two lessons may be taking the same drawing apart
    one = copy.deepcopy(tree)
    container = _container(one.getroot())
    for index, child in enumerate([c for c in container if _tag(c) not in _NOT_DRAWN]):
        if keep is not None and index not in keep:
            container.remove(child)
    for parent in list(one.getroot().iter()) if not words else []:   # words anywhere (a credit line) are not part of the art
        for child in [c for c in parent if _tag(c) == "text"]:
            parent.remove(child)
    if view:                                            # a close-up: the same drawing, seen through a smaller window
        one.getroot().set("viewBox", " ".join(f"{v:.3f}" for v in view))
        one.getroot().set("preserveAspectRatio", "xMidYMid slice")
    one.getroot().set("width", str(width))
    one.getroot().set("height", str(height))
    svg, html, png = folder / f"{name}.svg", folder / f"{name}.html", folder / f"{name}.png"
    one.write(svg, encoding="utf-8", xml_declaration=True)
    html.write_text(f'<html><body style="margin:0;background:transparent"><img src="{svg.name}" width="{width}" height="{height}"></body></html>')
    with tempfile.TemporaryDirectory(prefix="lessonforge_chrome_") as profile:
        subprocess.run([chrome, "--headless=new", "--no-sandbox", "--disable-gpu", "--hide-scrollbars",
                        "--default-background-color=00000000", f"--window-size={width},{height + WINDOW_MARGIN}",
                        f"--user-data-dir={profile}", f"--screenshot={png}", html.resolve().as_uri()],
                       capture_output=True, timeout=120, check=False)
    svg.unlink(missing_ok=True)
    html.unlink(missing_ok=True)
    if not png.is_file():
        return None
    image = np.asarray(Image.open(png).convert("RGBA")).copy()
    png.unlink(missing_ok=True)
    if image.shape[0] < height or image.shape[1] < width:
        return None                                   # the page was still shorter than the drawing: no half picture
    image = image[:height, :width]
    return image


WIDE = 2.2                    # a picture wider than this for its height is a strip in the lesson's picture box


ZOOM = 0.45                   # a close-up shows this share of the drawing's height (more when the part is bigger)
FRAME = 1.5                   # ... in a window at least this wide for its height
DETAIL_WIDTH = 1100           # pixels a close-up is drawn at


def panels(image) -> list:
    """The two halves of a wide two-panel picture, each cut to what is drawn in it; [] when it is not one."""
    import numpy as np  # noqa: PLC0415
    cut = _gutter(image)
    if cut is None:
        return []
    alpha = image[:, :, 3]
    out = []
    for a, b in ((0, cut), (cut, image.shape[1])):
        ys, xs = np.where(alpha[:, a:b] > 16)
        if not len(xs):
            return []
        out.append(image[ys.min():ys.max() + 1, a + xs.min():a + xs.max() + 1])
    return out


def _gutter(image) -> int | None:
    """The column at which a wide picture on a clear ground splits into two panels, or None."""
    import numpy as np  # noqa: PLC0415
    alpha = image[:, :, 3]
    ys, xs = np.where(alpha > 16)
    if not len(xs):
        return None
    x0, x1, y0, y1 = int(xs.min()), int(xs.max()) + 1, int(ys.min()), int(ys.max()) + 1
    if (x1 - x0) < WIDE * (y1 - y0):
        return None
    empty = alpha[y0:y1, x0:x1].max(axis=0) <= 16
    best, start = (0, 0), None
    for k in range(int(0.3 * (x1 - x0)), int(0.7 * (x1 - x0)) + 1):
        if empty[k] and start is None:
            start = k
        if (not empty[k] or k == int(0.7 * (x1 - x0))) and start is not None:
            if k - start > best[1] - best[0]:
                best = (start, k)
            start = None
    if best[1] - best[0] < 0.015 * (x1 - x0):
        return None
    return x0 + (best[0] + best[1]) // 2


def stacked(image, with_boxes: bool = False):
    """A very wide picture made of two panels side by side, re-laid with the second under the first, or None.

    A before-and-after drawing (which ``VISUAL_RULE`` asks for) comes back three times as
    wide as it is tall; fitted into the picture's half of the frame it was a strip 107
    pixels high with print nobody could read (the first demo, 2026-10-09). Only a picture
    on a clear ground with an empty gutter between its halves is re-laid; anything else is
    left as it is.
    """
    import numpy as np  # noqa: PLC0415
    alpha = image[:, :, 3]
    ys, xs = np.where(alpha > 16)
    if not len(xs):
        return None
    x0, x1, y0, y1 = int(xs.min()), int(xs.max()) + 1, int(ys.min()), int(ys.max()) + 1
    if (x1 - x0) < WIDE * (y1 - y0):
        return None
    empty = alpha[y0:y1, x0:x1].max(axis=0) <= 16                       # columns with nothing drawn in them
    best, start = (0, 0), None
    for k in range(int(0.3 * (x1 - x0)), int(0.7 * (x1 - x0)) + 1):     # a gutter near the middle
        if empty[k] and start is None:
            start = k
        if (not empty[k] or k == int(0.7 * (x1 - x0))) and start is not None:
            if k - start > best[1] - best[0]:
                best = (start, k)
            start = None
    if best[1] - best[0] < 0.015 * (x1 - x0):
        return None
    cut = x0 + (best[0] + best[1]) // 2
    halves, came_from = [], []
    for a, b in ((x0, cut), (cut, x1)):
        cols = np.where(alpha[y0:y1, a:b].max(axis=0) > 16)[0]
        rows = np.where(alpha[y0:y1, a:b].max(axis=1) > 16)[0]
        if not len(cols) or not len(rows):
            return None
        halves.append(image[y0 + rows.min():y0 + rows.max() + 1, a + cols.min():a + cols.max() + 1])
        came_from.append([int(a + cols.min()), int(y0 + rows.min()), int(a + cols.max() + 1), int(y0 + rows.max() + 1)])
    gap = max(8, int(0.03 * (x1 - x0)))
    width = max(h.shape[1] for h in halves)
    out = np.zeros((sum(h.shape[0] for h in halves) + gap, width, 4), dtype=image.dtype)
    top, boxes = 0, []
    for h in halves:
        left = (width - h.shape[1]) // 2
        out[top:top + h.shape[0], left:left + h.shape[1]] = h
        boxes.append([left, top, left + h.shape[1], top + h.shape[0]])
        top += h.shape[0] + gap
    if with_boxes == "both":                 # also where each panel was cut FROM, for moving a place in the drawing with it
        return out, boxes, came_from
    return (out, boxes) if with_boxes else out


def name_parts(labels: list[dict], layers: list[dict], width: int, height: int) -> None:
    """Give each label the layer its pointer ends on. Fills ``part`` (a layer id or None) and ``found``.

    ``layers``: ``{"id", "alpha" (2-D array), "area"}``. A pointer often stops just short of
    what it points at, so the search walks on a little in the pointer's direction and takes
    the smallest layer it meets that is not the body.
    """
    import numpy as np  # noqa: PLC0415
    big = BIG * width * height

    def under(x: float, y: float, small_only: bool) -> list[dict]:
        xi, yi = int(round(x)), int(round(y))
        if not (0 <= xi < width and 0 <= yi < height):
            return []
        return [layer for layer in layers
                if layer["alpha"][max(0, yi - 3):yi + 4, max(0, xi - 3):xi + 4].max() > 40 and (layer["area"] < big or not small_only)]

    for label in labels:
        label["part"], label["found"] = None, "nothing under the pointer"
        if not label.get("tip"):
            label["found"] = "no pointer"
            continue
        tip, start = np.array(label["tip"], dtype=float), np.array(label["from"], dtype=float)
        length = float(np.linalg.norm(tip - start))
        along = (tip - start) / length if length > 1e-6 else np.zeros(2)
        for reach in range(0, REACH + 1, 4):
            hit = under(*(tip + along * reach), small_only=True)
            if hit:
                label["part"] = min(hit, key=lambda layer: layer["area"])["id"]
                label["found"] = "at the pointer's end" if reach == 0 else f"{reach} px past the pointer's end"
                break
        else:
            if under(*tip, small_only=False):
                label["found"] = "only the body is there"


def take_apart(svg_path: Path, log=print, width: int = WIDTH) -> dict | None:
    """Layers and names for a diagram SVG, saved beside it as ``manifest.json``. None when it cannot be used."""
    svg_path = Path(svg_path).resolve()        # the browser is handed a file address: it must be absolute
    folder = svg_path.parent
    saved = folder / "manifest.json"
    if saved.is_file():
        try:
            manifest = json.loads(saved.read_text(encoding="utf-8"))
            if manifest.get("version") == MANIFEST_VERSION and (folder / manifest["art"]).is_file():
                return manifest
        except (ValueError, KeyError):
            pass
    chrome = browser()
    if chrome is None:
        log("[diagram] no headless browser found: the diagram cannot be drawn in layers")
        return None
    try:
        why = safe(svg_path.read_bytes())
    except OSError:
        return None
    if why:
        log(f"[diagram] the SVG was refused: {why}")
        return None
    found = read(svg_path)
    if not found:                # (no parts beside the labels is fine: the art may live outside their group, as the heart's does)
        log("[diagram] nothing to draw was found in the SVG")
        return None
    import numpy as np  # noqa: PLC0415
    from PIL import Image  # noqa: PLC0415
    vx, vy, vw, vh = found["box"]
    height = round(width * vh / vw)
    to_px = lambda point: [round((point[0] - vx) / vw * width, 1), round((point[1] - vy) / vh * height, 1)]  # noqa: E731
    began = time.time()
    art = _shot(found["tree"], set(found["parts"]), width, height, folder, "art", chrome)
    if art is None or art[:, :, 3].max() == 0:
        log("[diagram] the browser drew nothing")
        return None
    children = found["children"]
    def grounds(element) -> bool:
        """Does it paint a ground over the whole canvas: a rectangle that size, itself or inside it (a scene's sky)."""
        for inner in element.iter():
            span = _rect(inner)
            if span and span[2] - span[0] >= 0.98 * vw and span[3] - span[1] >= 0.98 * vh:
                return True
        return False

    covers = any(grounds(children[i]) for i in found["parts"])
    if not covers and (art[:, :, 3] > 250).mean() > 0.995:
        # "It made a picture" proves nothing. With a relative file address the browser drew its
        # own "This site can't be reached" page, opaque from corner to corner, 92 times, and
        # every label was then found to point at "the body". Art on a transparent ground never
        # covers the whole canvas, unless the drawing itself paints a ground over all of it (a sky), which the
        # SVG says and is read above.
        log("[diagram] the browser's picture is opaque from edge to edge: it did not draw the SVG")
        return None
    whole = _shot(found["tree"], None, width, height, folder, "whole", chrome, words=True)
    relaid, panel_boxes = None, []
    if whole is not None:                               # the drawing as its maker meant it, words and all
        Image.fromarray(whole).save(folder / "whole.png")
        laid = stacked(whole, with_boxes=True)
        if laid is not None:                            # two panels side by side, the second put under the first
            relaid, panel_boxes = laid
            Image.fromarray(relaid).save(folder / "whole_stacked.png")
    # Keep only what is drawn. The canvas of a labelled diagram is mostly margin left for its
    # own labels; shown whole, the cell took less than half of its card.
    ys, xs = np.where(art[:, :, 3] > 40)
    art_box = [int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1]
    Image.fromarray(art[art_box[1]:art_box[3], art_box[0]:art_box[2]]).save(folder / "art.png")
    layers = []
    # One layer for each child is only needed where a pointer has to be followed to its part.
    searching = any(label["pointer"] for label in found["labels"])
    for n, index in enumerate(found["parts"] if searching else []):
        image = _shot(found["tree"], {index}, width, height, folder, f"layer{n}", chrome)
        if image is None:
            continue
        alpha = image[:, :, 3]
        ys, xs = np.where(alpha > 40)
        if not len(xs):
            continue
        box = [int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1]
        layers.append({"id": f"part_{n:02d}", "alpha": alpha, "area": int(len(xs)), "box": box, "image": image})
    labels, marked = [], []
    for label in found["labels"]:
        entry = {"name": label["name"], "slug": slug(label["name"]), "tip": None, "from": None, "flows": [], "colour": ""}
        for index in label.get("marks") or []:            # the paths a dot can run along, and the colour they are drawn in
            strokes = [children[index]] if _tag(children[index]) != "g" else [e for e in children[index].iter() if _tag(e) != "g"]
            for stroke in strokes:                        # (an arrow the drawing declared is a group: the strokes in it)
                line = _polyline(stroke)
                if line:
                    entry["flows"].append([to_px(point) for point in line])
                entry["colour"] = entry["colour"] or _colour(stroke, "stroke") or _colour(stroke, "fill")
        if label.get("marks"):
            # A box of words and its arrows: the arrows are the part, the label stands where the box stood, on the
            # box's side nearer the arrows, and points at the nearest of them.
            image = _shot(found["tree"], set(label["marks"]), width, height, folder, f"marks{len(marked)}", chrome)
            ys, xs = np.where(image[:, :, 3] > 40) if image is not None else ((), ())
            if len(xs):
                (x0, y0), (x1, y1) = to_px(label["box"][:2]), to_px(label["box"][2:])
                centre = ((x0 + x1) / 2, (y0 + y1) / 2)
                left = float(xs.mean()) < centre[0]
                start = [x0 if left else x1, round(centre[1], 1)]
                nearest = int(np.argmin((xs - start[0]) ** 2 + (ys - start[1]) ** 2))
                entry["from"], entry["tip"] = start, [float(xs[nearest]), float(ys[nearest])]
                layer = {"id": f"marks_{len(marked):02d}", "alpha": image[:, :, 3], "area": int(len(xs)), "image": image,
                         "box": [int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1]}
                marked.append((entry, layer, "the marks of its own colour beside its words" if label.get("beside")
                               else "the arrows drawn for its box of words"))
        if label["pointer"]:
            a, b = to_px(label["pointer"][0]), to_px(label["pointer"][1])
            at = to_px(label["at"]) if label["at"] else a
            # the end nearer the words is where the label sits; the other end is the tip
            near_a = (a[0] - at[0]) ** 2 + (a[1] - at[1]) ** 2 <= (b[0] - at[0]) ** 2 + (b[1] - at[1]) ** 2
            entry["from"], entry["tip"] = (a, b) if near_a else (b, a)
        elif label["at"] and entry["from"] is None:
            entry["from"] = to_px(label["at"])
        if entry["slug"] and entry["from"]:
            labels.append(entry)
    name_parts([label for label in labels if not any(label is entry for entry, _, _ in marked)], layers, width, height)
    for entry, layer, how in marked:
        entry["part"], entry["found"] = layer["id"], how
        layers.append(layer)
    # One layer that three or more labels all "name" is not a part: it is the drawing itself, in one piece (the
    # heart came as a single group, and every label then lit the whole heart). Those labels keep their pointer
    # and get a ring at its end instead.
    named_by: dict[str, int] = {}
    for label in labels:
        if label["part"]:
            named_by[label["part"]] = named_by.get(label["part"], 0) + 1
    for label in labels:
        if label["part"] and named_by[label["part"]] >= 3:
            label["part"], label["found"] = None, "the drawing is in one piece there"
    wanted = {label["part"] for label in labels if label["part"]}
    parts = []
    for layer in layers:
        if layer["id"] in wanted:                       # only a part a label names is ever lifted out
            x0, y0, x1, y1 = layer["box"]
            Image.fromarray(layer["image"][y0:y1, x0:x1]).save(folder / f"{layer['id']}.png")
            parts.append({"id": layer["id"], "png": f"{layer['id']}.png", "box": layer["box"], "area": layer["area"]})
    base = ""
    if marked:
        # The scene with none of its processes in it: what a lesson starts from when it builds the poster up.
        every = {index for label in found["labels"] for index in label.get("marks") or []}
        bare = _shot(found["tree"], set(found["parts"]) - every, width, height, folder, "base", chrome)
        if bare is not None:
            Image.fromarray(bare[art_box[1]:art_box[3], art_box[0]:art_box[2]]).save(folder / "base.png")
            base = "base.png"
    else:
        # A close-up of each named place. The browser draws the SVG again with its view box there, so the
        # close-up is as sharp as the whole (an enlarged screenshot of a 1280 px drawing is not).
        aw, ah = art_box[2] - art_box[0], art_box[3] - art_box[1]
        # Every close-up has ONE shape, never narrower than FRAME to 1: an upright drawing (the heart) would
        # otherwise be shown in an upright card a quarter of the frame wide, close-ups and all.
        frame = max(aw / ah, FRAME)
        for label in labels:
            if not label["tip"] or not label["slug"]:
                continue
            part = next((layer for layer in layers if layer["id"] == label["part"]), None)
            cx, cy = ((part["box"][0] + part["box"][2]) / 2, (part["box"][1] + part["box"][3]) / 2) if part else label["tip"]
            tall = (part["box"][3] - part["box"][1]) if part else 0
            rh = min(ah, max(ZOOM * ah, 2.4 * tall))
            rw = rh * frame
            if rw > width:
                rw, rh = float(width), width / frame
            x0 = min(max(cx - rw / 2, 0), width - rw)             # the margin beside the drawing may be in view; it is blank
            y0 = min(max(cy - rh / 2, art_box[1]), art_box[3] - rh)
            view = (vx + x0 / width * vw, vy + y0 / height * vh, rw / width * vw, rh / height * vh)
            close = _shot(found["tree"], set(found["parts"]), DETAIL_WIDTH, max(2, round(DETAIL_WIDTH * rh / rw)), folder,
                          f"detail_{label['slug']}", chrome, view=view)
            if close is not None and close[:, :, 3].max() > 0:
                Image.fromarray(close).save(folder / f"detail_{label['slug']}.png")
                label["detail"] = {"png": f"detail_{label['slug']}.png", "box": [round(x0, 1), round(y0, 1), round(x0 + rw, 1), round(y0 + rh, 1)]}
    panel_files = []
    for n, panel in enumerate(panels(whole) if whole is not None else [], 1):
        Image.fromarray(panel).save(folder / f"panel_{n}.png")
        panel_files.append(f"panel_{n}.png")
    manifest = {"version": MANIFEST_VERSION, "width": width, "height": height, "art": "art.png", "art_box": art_box, "parts": parts,
                "base": base, "panels": panel_files if relaid is not None else [], "panel_boxes": panel_boxes,
                "frame": round(max((art_box[2] - art_box[0]) / (art_box[3] - art_box[1]), FRAME), 4) if not marked else 0,
                "whole": "whole.png" if whole is not None else "", "style": "boxes" if marked else "pointers",
                "whole_stacked": "whole_stacked.png" if relaid is not None else "",
                "labels": [{k: label.get(k) for k in ("name", "slug", "part", "tip", "from", "found", "flows", "colour", "detail")}
                           for label in labels],
                "credit": found["credit"], "folder": str(folder), "layers_drawn": len(layers),
                "seconds": round(time.time() - began, 1)}
    try:                                                # what another module keeps here is not ours to throw away:
        before = json.loads(saved.read_text(encoding="utf-8")) if saved.is_file() else {}
    except ValueError:                                  # harness.typeset pays one look per drawing for its names
        before = {}
    manifest.update({key: before[key] for key in KEPT_ACROSS if key in before})
    saved.write_text(json.dumps(manifest, indent=1, ensure_ascii=False), encoding="utf-8")
    own = sum(1 for label in manifest["labels"] if label["part"])
    log(f"[diagram] {len(layers)} layers drawn in {manifest['seconds']} s; {len(manifest['labels'])} labels, "
        f"{own} with a part of their own" + (f"; credit: {manifest['credit'][:60]}" if manifest["credit"] else ""))
    return manifest


def pointable(manifest: dict) -> list[dict]:
    """The labels a lesson can point at: one with a part to light, or a pointer whose end can be ringed.

    A poster's title, its caption in a corner and a box of words with no arrows are words
    on the drawing and nothing to point at; offered to the writer as names they used up
    its nine labels on things that then did nothing on screen.
    """
    return [label for label in manifest.get("labels") or [] if label.get("part") or label.get("tip")]


def ready_from(manifest_path, ask: str = "") -> dict | None:
    """What ``prepare`` returns, read back from a drawing already in the library (its manifest's path); None if gone."""
    try:
        manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return None
    labels = pointable(manifest)
    return {"ask": ask, "manifest": str(manifest_path), "parts": [label["slug"] for label in labels],
            "names": {label["slug"]: label["name"] for label in labels}, "credit": manifest.get("credit", ""),
            "style": manifest.get("style", "")}


def prepare(ask: str, klass: int | None = None, language: str = "en", log=print, subject: str = "") -> dict | None:
    """A request → what a lesson needs to use the diagram: its manifest path, the names it can point at, the credit.

    ``parts`` holds only what can be pointed at (``pointable``) and may be empty: the
    drawing is then still in the library with its ``whole.png``, for a figure that shows
    it whole.
    """
    svg = fetch(ask, klass, language, log=log, subject=subject)
    manifest = take_apart(svg, log=log) if svg else None
    if not manifest:
        return None
    labels = pointable(manifest)
    return {"ask": ask, "manifest": str(Path(manifest["folder"]) / "manifest.json"),
            "parts": [label["slug"] for label in labels], "names": {label["slug"]: label["name"] for label in labels},
            "credit": manifest.get("credit", ""), "style": manifest.get("style", "pointers")}


# ── a drawing is looked at before a lesson stands on it ──────────────────────
# The owner, 2026-10-09: "This critic is giving some things but we are not able to improve by using those critic
# things. Now because we have an API, you can iterate for images and audio again and again." The service's own
# verdict lets through a drawing that is fine as a drawing and not what was asked for, and until now nothing on
# our side looked at one. A small vision model does, once per drawing (the answer is kept beside it), and a
# drawing it finds wrong is asked for again WITH what was wrong: that is the finding acted on.

JUDGE_TRIES = 3               # drawings asked for, at most, for ONE request (each later one says what was wrong before)
# The first judge checked a drawing "against the request" and was read on a real run for what IT broke the same day:
# the service's water cycle (Sun, sea, clouds, six labelled processes, a textbook's picture) was thrown away three times
# because the request had said "blue arrows" and they were orange, the return flow was labelled "Collection" and not
# "runoff", and condensation "was not requested"; the lesson was then left with no picture and the topic marked as
# having none. A request says what a picture is OF. It is not a specification, and the judge is told so.
JUDGE_SYSTEM = """You look at ONE drawing made for a school lesson and say whether a teacher could put it in front of a class for
the request it was drawn from. Look only at the picture. The request says what the picture is OF; it is not a
specification. The artist may choose colours, style, layout and wording, may use another correct word for the same thing
("collection" for "runoff"), and may add things a textbook's picture of this would also have.
Return ONLY JSON: {"shows": true, "readable": true, "problems": ["each fault, a few words each"]}
"shows" is false ONLY when: it is a picture of a different thing; or a main thing the request names is not in it at all;
or something in it is plainly untrue (a label on the wrong thing, an arrow going the wrong way for what its label says).
"readable" is false ONLY when: words cannot be read or are cut off; labels lie on each other or on the drawing so that
they cannot be read; or stray bars, boxes or lines lie across the picture.
NEVER a fault: a colour, a style, the shape or number of arrows, where something is placed, a different but correct
word, a plain or simple drawing, something extra that is correct. "problems" lists only faults of the kinds above and
is empty when both answers are true."""
JUDGE_VERSION = hashlib.sha256(JUDGE_SYSTEM.encode("utf-8")).hexdigest()[:10]    # a verdict belongs to the judge that gave it


def judging() -> bool:
    return (knobs.get("HARNESS_JUDGE_PICTURES") or "1").strip() != "0"


def judge(ready: dict | None, look=None, log=print) -> dict | None:
    """What a small vision model makes of a prepared drawing: ``{"ok", "shows", "readable", "problems"}``.

    None when nobody looked (switched off, no model, no picture file, a failed call):
    the drawing is then used as before. Kept as ``judged.json`` beside the drawing.
    """
    if not ready or not judging():
        return None
    try:
        folder = Path(ready["manifest"]).parent
        kept = folder / "judged.json"
        if kept.is_file():
            before = json.loads(kept.read_text(encoding="utf-8"))
            if before.get("judge") == JUDGE_VERSION:          # another judge's verdict is not this one's: look again
                return before
        picture = next((folder / n for n in ("whole.png", "source.png") if (folder / n).is_file()), None)
        if picture is None:
            return None
        if look is None:
            from . import vision_review  # noqa: PLC0415
            look = vision_review.default_judge()
        if look is None:
            return None
        import base64  # noqa: PLC0415
        import io  # noqa: PLC0415
        from PIL import Image  # noqa: PLC0415
        image = Image.open(picture).convert("RGBA")
        ground = Image.new("RGBA", image.size, "white")
        ground.alpha_composite(image)
        ground = ground.convert("RGB")
        ground.thumbnail((1100, 1100))
        buffer = io.BytesIO()
        ground.save(buffer, format="JPEG", quality=85)
        raw = look(f"THE REQUEST: {ready.get('ask', '')}", JUDGE_SYSTEM, base64.b64encode(buffer.getvalue()).decode())
    except Exception as exc:  # noqa: BLE001 - a second look is an improvement, never a requirement
        log(f"[diagram] the drawing was not looked at ({type(exc).__name__}: {str(exc)[:100]})")
        return None
    if not isinstance(raw, dict):
        return None
    problems = [re.sub(r"\s+", " ", str(x)).strip()[:120] for x in (raw.get("problems") if isinstance(raw.get("problems"), list) else [])
                if str(x).strip()][:5]
    shows, readable = raw.get("shows") is not False, raw.get("readable") is not False
    verdict = {"ok": bool(shows and readable), "shows": bool(shows), "readable": bool(readable), "problems": problems,
               "judge": JUDGE_VERSION}
    try:
        kept.write_text(json.dumps(verdict, indent=1, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass
    return verdict


def prepare_checked(ask: str, klass: int | None = None, language: str = "en", log=print, look=None) -> dict | None:
    """A request → a drawing a lesson can show (``showable``) that has also been LOOKED AT, or None.

    A drawing found wrong is asked for again with what was wrong added to the request
    (``JUDGE_TRIES`` drawings at most). When every one was found wrong, none is used: a
    wrong picture on screen for a whole lesson is worse than none.
    """
    request, last = ask, None
    for attempt in range(max(1, JUDGE_TRIES)):
        ready = showable(prepare(request, klass, language, log=log))
        if not ready:
            return None if last is None else None
        verdict = judge(ready, look=look, log=log)
        if verdict is None or verdict["ok"]:
            return {**_named(ready, log), "ask": ask, "judged": verdict}
        last = verdict
        wrong = "; ".join(verdict["problems"]) or ("it does not show what was asked for" if not verdict["shows"] else "its labels cannot be read")
        log(f"[diagram] “{ask[:60]}”: looked at and found wrong ({wrong[:140]})"
            + ("; asking for it again" if attempt + 1 < JUDGE_TRIES else "; not used"))
        request = f"{ask} Draw it again and avoid what was wrong with the last drawing: {wrong[:240]}."
    return None


# ── the picture a topic is known by ──────────────────────────────────────────
# The owner, 2026-10-09: "you need to ask [for a] visual thing, like in NLM inertia what it knows [as a] visual, so we
# need a visual, not just some arbitrary thing." Sent the topic's NAME ("Newton's first law of motion: inertia") the
# service drew something its own checks failed; a topic is not a picture. So a small model is first asked what a
# teacher DRAWS for the topic, and each answer is a request the service can draw.

MIN_POINTABLE = 3             # fewer names than this and the drawing gives a lesson nothing to walk through
MAX_VISUALS = 3
MAX_TRIES = 3                 # pictures tried, at most, before a topic goes without one
VISUAL_MODELS_DEFAULT = "google/gemini-3.5-flash-lite,google/gemini-2.5-flash,openai/gpt-5.4-nano"

#: How a request to the drawing service is worded, whoever writes it (this module's own step, the teaching card's
#: ``diagram_ask``, the script path's planning call). One text, so the three do not drift apart.
VISUAL_RULE = """Ask for a PICTURE, never for a topic. A topic's name ("inertia", "photosynthesis", "fractions") cannot be drawn;
the picture the topic is KNOWN BY can. It is one of three things:
- the real thing as a labelled diagram (an animal cell, the human heart, a flower cut open, the eye);
- the classic demonstration or everyday situation that makes the idea visible, drawn as one still picture, before and
  after side by side when something changes (inertia: "A coin resting on a card on top of a glass, and beside it the same
  glass after the card is flicked away sideways with the coin fallen straight down into the glass"; pressure: "a nail
  resting on its point and a nail resting on its head on soft clay");
- the standard diagram of the method (a ray diagram of a convex lens with the object between F and 2F, a simple circuit
  with a cell, a switch and a bulb, the water cycle, a food chain, the division ladder for the prime factors of 36).
Write ONE sentence that names the objects, how they are arranged, what is labelled (three to seven things) and any arrows.
Begin with what it is ("A standard diagram of …", "A labelled diagram of …") and go on with "showing …" and each thing in
it: asked for that way, a drawing comes back with pieces a lesson can point at one by one.
Ask for the THINGS, not for what the lesson concludes: no formula, result, rule or summary written in the picture (a
drawing that prints "Area = 1/2 x b x h" has given the lesson away before its first sentence).
Keep it SHORT and plain: at most 35 words and six things. A request that asks for many details at once (a torch on the
left, a beam that looks bluish from the side, a red ray going on, a person watching) fails the service's own checks.
Use only nouns that can be drawn. Never make an abstract word the subject ("inertia", "a law", "the concept of").
No faces, no story, no brand, nothing that only makes sense while it moves."""

VISUAL_SYSTEM = """You choose the picture for a school lesson. A drawing service will draw exactly what you describe.

""" + VISUAL_RULE + """

Return ONLY JSON: {"visuals": [{"ask": "the request, one sentence", "shows": "the idea of the topic this picture makes
visible, one sentence", "kind": "labelled diagram | demonstration | standard diagram"}]}
Each visual stands alone and is complete in one request: never split one demonstration over two visuals, and draw
a before and an after side by side in the SAME picture.
Two or three visuals. Put first the one an Indian school textbook (NCERT) for this class prints or describes for
this topic: its own activity, its own figure. A learner should recognise it from their book."""


SHOWN_IN = (8.85, 5.7)        # the "columns" frame's one box for a prepared drawing (GuidedChapter.DRAWING_BOX)


def picture_scale(width: float, height: float, boxes: list | None = None) -> float:
    """Scene units per pixel a ``width`` by ``height`` picture is shown at: the largest it gets in any box of the frame.

    The boxes are the frame's, not this module's (``longform.look.picture_boxes``: the look a
    lesson made now gets). The "stage" frame has two, beside a column of words and under a
    strip of them, and a picture is shown in the one it fills most.
    """
    boxes = boxes or lesson_look.picture_boxes()
    return max(min(box_w / max(width, 1), box_h / max(height, 1)) for box_w, box_h in boxes)


def _laid_out(manifest: dict, folder: Path, boxes: list | None = None) -> tuple[Path | None, list, list]:
    """Which file shows a whole drawing LARGEST on screen: ``(file, its panels' files, each panel's box in that file)``.

    A wide two-panel drawing exists twice: as drawn (panels side by side) and re-laid (the
    second under the first). Until 2026-10-09 the re-laid one was always taken. A picture is
    scaled into its box by the smaller of width and height; in the old frame's 8.85 by 5.7 a
    1280 by 577 circuit came out 24% of the frame's width re-laid (680 by 1137) where side by
    side it fills 62%, while a 1280 by 389 tumbler is 10% larger re-laid. So the two scales
    are compared in the boxes of the frame in force (``picture_scale``), and the
    panels (shown one after the other) are offered for either: for the side-by-side file each
    panel's box is where it stands in the drawing as drawn.
    """
    side = next((folder / str(n) for n in (manifest.get("whole") or "whole.png", "source.png") if n and (folder / str(n)).is_file()), None)
    stack = folder / str(manifest.get("whole_stacked")) if manifest.get("whole_stacked") else None
    if stack is None or not stack.is_file():
        return side, [], []
    files = [folder / str(n) for n in manifest.get("panels") or []]
    files = files if len(files) >= 2 and all(f.is_file() for f in files) else []
    relaid = (stack, files, (manifest.get("panel_boxes") or []) if files else [])
    if side is None or side.name == "source.png":
        return relaid
    try:
        import numpy as np  # noqa: PLC0415
        from PIL import Image  # noqa: PLC0415

        def scale(path: Path) -> float:
            with Image.open(path) as image:
                return picture_scale(image.width, image.height, boxes)

        if scale(side) <= scale(stack):
            return relaid
        laid = stacked(np.asarray(Image.open(side).convert("RGBA")), with_boxes="both")
    except (OSError, ValueError):
        return relaid
    if laid is None:
        return side, [], []
    return side, files, ([list(box) for box in laid[2]] if files else [])


def showable(ready: dict | None, boxes: list | None = None) -> dict | None:
    """How a prepared drawing can be shown in a lesson: ``shown`` is "parts" or "whole" (then ``file``); None for neither.

    With at least ``MIN_POINTABLE`` things to name, a step lights the part it is about
    (the ``diagram`` figure). Otherwise the drawing is shown whole, words and all (the
    ``picture`` figure): a demonstration or a division ladder from the service has its
    words set as outlines, so nothing in it can be named, and it is still the picture
    the topic is known by.
    """
    if not ready:
        return None
    if len(ready.get("parts") or []) >= MIN_POINTABLE:
        return {**ready, "shown": "parts"}
    try:
        manifest = json.loads(Path(ready["manifest"]).read_text(encoding="utf-8"))
    except (OSError, ValueError, KeyError):
        return None
    folder = Path(manifest.get("folder") or Path(ready["manifest"]).parent)
    whole, files, places = _laid_out(manifest, folder, boxes)   # as drawn or re-laid: whichever is larger on screen
    if not whole:
        return None
    out = {**ready, "shown": "whole", "file": str(whole)}
    pointed = points_of(manifest, folder, whole)       # its printed labels, when harness.typeset has read them
    if pointed:
        out["points"] = pointed
    if files and places:
        # Its panels, each on its own, and where each sits in the file shown: the figure shows the first
        # and brings the next in on a step's focus ("panel2"), so "after" waits until the lesson has asked.
        out.update(panels=[str(f) for f in files], panel_boxes=places)
    return out


def focus_key(text) -> str:
    """A name as a step's ``focus`` is cleaned everywhere: lower case, letters digits and "_", 24 characters."""
    return re.sub(r"[^a-z0-9_]", "", str(text).strip().lower().replace(" ", "_"))[:24]


def points_of(manifest: dict, folder: Path, shown: Path) -> dict:
    """The printed labels of a whole drawing that a step may point at: ``{focus: {"name", "box"}}`` in the FILE shown.

    ``harness.typeset`` finds the labels of a drawing whose words are outlines and keeps them
    in the manifest with boxes as shares of the source drawing. Shown as ``whole.png`` those
    are the file's own shares. A wide two-panel drawing is shown re-laid (``whole_stacked.png``,
    the second panel under the first): each box moves with the panel it lies in, and one that
    lies in neither is left out. {} when the drawing has no such names or the move cannot be made.
    """
    kept = manifest.get("typeset")
    names = kept.get("names") if isinstance(kept, dict) and isinstance(kept.get("names"), dict) else {}
    if not names:
        return {}

    def box_of(entry):
        box = entry.get("box") if isinstance(entry, dict) else None
        try:
            box = [float(v) for v in box] if isinstance(box, (list, tuple)) and len(box) == 4 else None
        except (TypeError, ValueError):
            return None
        return box if box and 0 <= box[0] < box[2] <= 1 and 0 <= box[1] < box[3] <= 1 else None

    move = None
    if manifest.get("whole_stacked") and shown.name == str(manifest["whole_stacked"]):
        try:
            import numpy as np  # noqa: PLC0415
            from PIL import Image  # noqa: PLC0415
            source = np.asarray(Image.open(folder / str(manifest.get("whole") or "whole.png")).convert("RGBA"))
            laid = stacked(source, with_boxes="both")
        except (OSError, ValueError):
            laid = None
        if laid is None:
            return {}
        out_image, places, came_from = laid
        (high, wide), (src_high, src_wide) = out_image.shape[:2], source.shape[:2]

        def move(box):
            x0, y0, x1, y1 = box[0] * src_wide, box[1] * src_high, box[2] * src_wide, box[3] * src_high
            cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
            for (sx0, sy0, sx1, sy1), (px0, py0, _px1, _py1) in zip(came_from, places):
                if sx0 <= cx < sx1 and sy0 <= cy < sy1:
                    dx, dy = px0 - sx0, py0 - sy0
                    return [max(0.0, (x0 + dx) / wide), max(0.0, (y0 + dy) / high), min(1.0, (x1 + dx) / wide), min(1.0, (y1 + dy) / high)]
            return None

    out = {}
    for slug_, entry in names.items():
        key, box = focus_key(slug_), box_of(entry)
        if box is not None and move is not None:
            box = move(box)
        if key and key not in out and box is not None and not re.fullmatch(r"panel_?\d+", key):
            out[key] = {"name": str(entry.get("name") or slug_)[:48], "box": [round(v, 4) for v in box]}
    # One or two labels are not a picture to point into. The triangle-area drawing had ONE readable label, its
    # formula, and every step that wanted a mark got that one: the answer lit up under "24 or 12?".
    return out if len(out) >= MIN_POINTABLE else {}


def _named(ready: dict, log=print) -> dict:
    """A whole drawing with its printed labels read (once, kept in its manifest by ``harness.typeset``), or as it was."""
    if not ready or ready.get("shown") != "whole" or ready.get("points"):
        return ready
    try:
        from . import typeset  # noqa: PLC0415
        if typeset.names(ready["manifest"], log=log):
            again = showable({k: v for k, v in ready.items() if k not in ("shown", "file", "panels", "panel_boxes", "points")})
            if again and again.get("points"):
                return {**ready, **again}
    except Exception as exc:  # noqa: BLE001 - names to point at are an improvement, never a requirement
        log(f"[diagram] the drawing's printed labels were not read ({type(exc).__name__}: {str(exc)[:100]})")
    return ready


def whole_of(ready: dict | None) -> dict | None:
    """A prepared drawing as ONE picture, words and all (``shown`` "whole", ``file``), whatever else it could be; no panels."""
    if not ready:
        return None
    try:
        manifest = json.loads(Path(ready["manifest"]).read_text(encoding="utf-8"))
    except (OSError, ValueError, KeyError):
        return None
    folder = Path(manifest.get("folder") or Path(ready["manifest"]).parent)
    whole = _laid_out(manifest, folder)[0]
    if not whole:
        return None
    out = {**{k: v for k, v in ready.items() if k not in ("panels", "panel_boxes", "points")}, "shown": "whole", "file": str(whole)}
    pointed = points_of(manifest, folder, whole)
    if pointed:
        out["points"] = pointed
    return out


def topic_pictures() -> bool:
    """Whether a lesson with no prepared picture asks for its topic's (``HARNESS_TOPIC_PICTURES``, on when it can)."""
    return (knobs.get("HARNESS_TOPIC_PICTURES") or "1").strip() != "0" and available()


def visual_llm():
    """A small, fast model through OpenRouter, metered as "visual". None without a key."""
    key = (os.getenv("OPENROUTER_API_KEY") or "").strip()
    if not key:
        return None
    from ..engine import llm as engine_llm  # noqa: PLC0415
    models = [m.strip() for m in knobs.get("HARNESS_VISUAL_MODELS", VISUAL_MODELS_DEFAULT).split(",") if m.strip()]

    def call(prompt: str, system: str):
        text = engine_llm.call_openrouter(key, prompt, system, temperature=0.2, models=models, max_tokens=None,
                                          json_object=True, note="visual", timeout=90.0)
        return engine_llm.loads_json_lenient(text)
    return call


def visuals_for(brief: dict, llm, log=print) -> list[dict]:
    """What a teacher draws for a brief's topic: up to ``MAX_VISUALS`` requests the service can draw, best first.

    Code keeps a request only if it describes something: at least six words, and more
    than the topic's own words said again (the fault this step exists to prevent).
    """
    from . import library  # noqa: PLC0415
    topic = re.sub(r"\s+", " ", str((brief or {}).get("topic") or "")).strip()
    if len(topic) < 3 or llm is None:
        return []
    lines = [f"TOPIC: {topic}", f"CLASS: {library.school_class(brief) or 'not given'} ({brief.get('audience', '')})",
             f"AFTER THE LESSON THE LEARNER CAN: {brief.get('goal', '')}"]
    if brief.get("more_pictures"):
        lines.append("GIVE THREE DIFFERENT PICTURES this time (a first answer had fewer than two that could be used): the textbook's "
                     "own figure, the classic demonstration, and the real thing as a labelled diagram.")
    if brief.get("picture_plan"):          # a lesson made from a teaching card: its drawing should be the card's one picture
        lines.append("THE LESSON'S PLAN FOR ITS ONE PICTURE (the lesson will talk about this: make it the FIRST visual, as one "
                     "still, labelled picture with everything in it at once, not as steps; the other visuals are other pictures "
                     f"this topic is known by): {str(brief['picture_plan'])[:500]}")
    try:
        raw = llm("\n".join(lines), VISUAL_SYSTEM) or {}
    except Exception as exc:  # noqa: BLE001 - a picture is an improvement, never a requirement
        log(f"[diagram] no picture was thought of ({type(exc).__name__}: {str(exc)[:100]})")
        return []
    named, out = set(library.tokens(topic)), []
    for item in raw.get("visuals") if isinstance(raw, dict) and isinstance(raw.get("visuals"), list) else []:
        if not isinstance(item, dict):
            continue
        ask = re.sub(r"\s+", " ", str(item.get("ask") or "")).strip()[:300]
        words = set(library.tokens(ask))
        if len(ask.split()) < 6 or len(words - named) < 3 or any(ask.lower() == o["ask"].lower() for o in out):
            continue                                   # the topic said again is not a picture
        shows = re.sub(r"\s+", " ", str(item.get("shows") or "")).strip()[:200]
        if not set(library.tokens(shows)) - named:      # the topic's name again says nothing about the picture
            shows = ""
        out.append({"ask": ask, "shows": shows,
                    "kind": re.sub(r"\s+", " ", str(item.get("kind") or "")).strip()[:30]})
    return out[:MAX_VISUALS]


NOTHING_FOUND_HOURS = 24      # a topic the service could draw nothing usable for is asked about again after this
ASKING_VERSION = 2            # how a topic's picture is looked for (2: a failed request asked twice, more than one candidate):
#                               a "nothing usable" note made by an older way of asking does not stand


def _recent(when) -> bool:
    """Whether a "nothing usable" note is young enough to stand: the service is free, changes, and can be down."""
    try:
        return time.time() - time.mktime(time.strptime(str(when), "%Y-%m-%d %H:%M")) < NOTHING_FOUND_HOURS * 3600
    except (ValueError, OverflowError):
        return False


# ── as many pictures as the service can draw ─────────────────────────────────
# The owner, 2026-10-09, asked where a topic lesson's pictures should come from: "as many as from the drawings". A
# lesson's other pictures were scenes a model writes from one sentence (two thirds of a lesson's cost, a tree in four
# shapes in seven chapters, one of them stopping a render). Each such scene is offered to the drawing service first,
# as a still; the model-written scene stays only where the service has nothing a lesson can show.

MAX_LESSON_PICTURES = 6       # drawings asked for, at most, in place of ONE lesson's scenes
STILLS_AT_ONCE = 3            # requests in flight (the service draws one at a time; more only queue there)
STILLS_SYSTEM = """A school lesson has been written. Some of its pictures are animated SCENES, each described in a sentence. A
drawing service can draw still pictures. For each numbered scene, write the request for ONE still drawing that can stand
in its place while the scene's words are spoken.

""" + VISUAL_RULE + """

Return ONLY JSON: {"pictures": [{"scene": 1, "ask": "the request, one sentence"}, {"scene": 2, "same_as": 1}]}
- A still picture cannot move. Draw the END of the scene's motion with what moved shown by arrows, or before and after
  side by side in the same picture.
- "same_as": when a scene shows the same things as an EARLIER scene (a later moment of it, a part of it), give that
  scene's number instead of a new request, so one drawing stays on screen for both. The request of a drawing several
  scenes share must hold EVERYTHING those scenes talk about.
- Few drawings: a lesson on one thing usually needs one or two.
- "ask": "" only for a scene with nothing in it that can be drawn."""


def _listed(raw, key: str) -> list:
    """A model's list, whether it came as ``{key: [...]}`` (as asked) or as the bare list.

    Asked for one entry per step, the small model answered with a correct bare list and all
    of it was thrown away as "not the shape"; the lesson's drawing then stood unlit.
    """
    if isinstance(raw, dict) and isinstance(raw.get(key), list):
        return raw[key]
    return raw if isinstance(raw, list) else []


def stills_for(scenes: list[dict], brief: dict, llm=None, log=print) -> list[dict | None]:
    """For each scene (``{"describe", "said"}``), the service's drawing that can stand in its place, or None.

    One small call turns the scenes into requests for stills (scenes showing the same
    things share one); each DISTINCT request is drawn, taken apart and looked at
    (``prepare_checked``), ``STILLS_AT_ONCE`` at a time, ``MAX_LESSON_PICTURES`` at most.
    Nothing here raises: a scene with no drawing keeps what it had.
    """
    from concurrent.futures import ThreadPoolExecutor  # noqa: PLC0415

    from . import library  # noqa: PLC0415
    nothing: list[dict | None] = [None] * len(scenes)
    llm = llm or visual_llm()
    if not scenes or llm is None:
        return nothing
    klass = library.school_class(brief)
    lines = [f"TOPIC: {str((brief or {}).get('topic') or '')[:120]}", f"CLASS: {klass or 'not given'} ({(brief or {}).get('audience', '')})"]
    for n, scene in enumerate(scenes, 1):
        lines += [f"SCENE {n}: {re.sub(r'\s+', ' ', str(scene.get('describe') or ''))[:400]}",
                  f"   ITS WORDS: {re.sub(r'\s+', ' ', str(scene.get('said') or ''))[:400]}"]
    try:
        raw = llm("\n".join(lines), STILLS_SYSTEM) or {}
    except Exception as exc:  # noqa: BLE001 - a drawing is an improvement, never a requirement
        log(f"[pictures] no drawings were thought of for the scenes ({type(exc).__name__}: {str(exc)[:100]})")
        return nothing
    asked: dict[int, str] = {}
    shared: dict[int, int] = {}
    for item in _listed(raw, "pictures"):
        if not isinstance(item, dict) or not isinstance(item.get("scene"), int) or not 1 <= item["scene"] <= len(scenes):
            continue
        ask = re.sub(r"\s+", " ", str(item.get("ask") or "")).strip()[:300]
        if len(ask.split()) >= 6:
            asked[item["scene"]] = ask
        elif isinstance(item.get("same_as"), int) and 1 <= item["same_as"] < item["scene"]:
            shared[item["scene"]] = item["same_as"]            # only ever an EARLIER scene: no circles
    for n, other in sorted(shared.items()):
        if other in asked and n not in asked:
            asked[n] = asked[other]
    wanted = list(dict.fromkeys(asked[n] for n in sorted(asked)))[:MAX_LESSON_PICTURES]
    if not wanted:
        return nothing

    def draw(ask: str):
        try:
            return prepare_checked(ask, klass, "en", log=log)
        except Exception as exc:  # noqa: BLE001
            log(f"[pictures] “{ask[:60]}” could not be had ({type(exc).__name__}: {str(exc)[:100]})")
            return None

    with ThreadPoolExecutor(max_workers=max(1, STILLS_AT_ONCE)) as pool:
        drawn = dict(zip(wanted, pool.map(knobs.wrap(draw), wanted)))
    return [drawn.get(asked.get(n, "")) for n in range(1, len(scenes) + 1)]


POINT_SYSTEM = """A labelled drawing is on screen during some beats of a school lesson. Its parts are listed by name. Each beat has
steps: a line that appears on screen at a moment, with the words spoken in that beat. For EVERY step, say which ONE part
of the drawing it is about, so that part can be lit at that moment.
Return ONLY JSON, one entry for every step of every beat:
{"points": [{"beat": "04", "step": 1, "part": "evaporation"}, {"beat": "04", "step": 2, "part": "none"}]}
- "part" is one of the listed names, exactly as listed, or "none". "step" counts from 1 within its beat.
- Most steps shown beside a drawing are about one of its parts: name it whenever the step's line, or what is being said
  when it appears, is about that part, in whatever words ("sea to vapour", "a puddle dries up", "the Sun heats the sea"
  and "warm vapour rises" are evaporation; "water soaks into soil" is groundwater; "cooler air makes droplets" and "why
  clouds form" are condensation; "rain, snow or hail" is precipitation).
- "none" only for a step about the whole picture, a question that names no part, or something the list does not have."""


def point_steps(ready: dict, beats: list[dict], llm=None, log=print) -> dict:
    """Which part of a prepared drawing each step is about: ``{(beat id, step index from 0): part}``.

    For a drawing the writer did not know when it wrote the steps (``writer.drawings_for_scenes``).
    The steps' own words name a part only now and then ("Precipitation" yes, "Sea to
    vapour" no: 3 of 26 steps in the first lesson tried), and a drawing built up by its
    parts then stands bare through most of the lesson. A small model reads the steps
    against the drawing's own names; code keeps only names the drawing has. {} on any failure.
    """
    printed = ready.get("points") or {}                 # a whole drawing's printed labels (harness.typeset)
    parts = [str(p) for p in ready.get("parts") or []] or [str(p) for p in printed]
    llm = llm or visual_llm()
    if not parts or not beats or llm is None:
        return {}
    names = ready.get("names") or {key: entry.get("name") for key, entry in printed.items() if isinstance(entry, dict)}
    lines = ["THE DRAWING: " + str(ready.get("ask") or "")[:300],
             "ITS PARTS: " + "; ".join(f"{p} ({names[p]})" if names.get(p) and str(names[p]).lower() != p else p for p in parts)]
    for beat in beats:
        lines.append(f"BEAT {beat.get('id', '')} — spoken: {re.sub(r'\s+', ' ', str(beat.get('narration') or ''))[:500]}")
        lines += [f"   step {n}: {str(step.get('show') or '')[:110]}" + (f"   (appears at the words “{step['say']}”)" if step.get("say") else "")
                  for n, step in enumerate(beat.get("steps") or [], 1)]
    try:
        raw = llm("\n".join(lines), POINT_SYSTEM) or {}
    except Exception as exc:  # noqa: BLE001 - pointing is an improvement, never a requirement
        log(f"[pictures] the steps were not matched to the drawing's parts ({type(exc).__name__}: {str(exc)[:100]})")
        return {}
    known = {p.replace("_", "").lower(): p for p in parts}
    sizes = {str(beat.get("id", "")): len(beat.get("steps") or []) for beat in beats}
    out = {}
    for item in _listed(raw, "points"):
        if not isinstance(item, dict) or not isinstance(item.get("step"), int):
            continue
        beat, part = str(item.get("beat") or "").strip(), known.get(re.sub(r"[^a-z0-9]", "", str(item.get("part") or "").lower()))
        if part and beat in sizes and 1 <= item["step"] <= sizes[beat]:
            out[(beat, item["step"] - 1)] = part
    return out


def _judged_by() -> str:
    """Who looked at the drawings a topic's choice was made from: the judge's version, or "off"."""
    return JUDGE_VERSION if judging() else "off"


def for_brief(brief: dict, llm=None, log=print) -> dict | None:
    """The picture a brief's topic is known by, drawn by the service and ready to point into, or None.

    A small model says what a teacher draws for the topic (``visuals_for``); the service
    draws them one at a time in that order, ``MAX_TRIES`` at most, and the first that can
    be shown (``showable``: with parts to point at, or whole) is the lesson's picture. The
    choice is kept per topic and class
    (``topics.json``), so the next lesson on the topic asks no model and no service.
    """
    from . import library  # noqa: PLC0415
    topic = re.sub(r"\s+", " ", str((brief or {}).get("topic") or "")).strip()
    if len(topic) < 3 or not topic_pictures():
        return None
    klass = library.school_class(brief)
    key, saved = f"{library.slug(topic)}|{klass}", root() / "topics.json"
    try:
        kept = json.loads(saved.read_text(encoding="utf-8")) if saved.is_file() else {}
    except ValueError:
        kept = {}
    if key in kept:
        chosen = kept[key]
        if (not chosen.get("ask") and chosen.get("judge") == _judged_by() and chosen.get("asking") == ASKING_VERSION
                and _recent(chosen.get("when"))):
            return None                                 # looked for today, nothing usable: not asked again by this judge
        ready = showable(prepare(chosen.get("drawn") or chosen["ask"], klass, "en", log=log)) if chosen.get("ask") else None
        if ready:
            return {**ready, "ask": chosen["ask"], "shows": chosen.get("shows", ""), "visual_kind": chosen.get("kind", "")}
    log(f"[diagram] asking what a teacher draws for “{topic}”, then having it drawn (up to two minutes)")
    model = llm or visual_llm()
    visuals = visuals_for(brief, model, log=log)
    if len(visuals) < 2 and not brief.get("picture_plan"):
        # One candidate is no pipeline: "Why sky is blue" (the owner's lesson, 2026-10-09) was given one picture
        # to try, the service failed it, and the lesson fell to model-written scenes. Asked again, for more.
        asked = {v["ask"].lower() for v in visuals}
        visuals += [v for v in visuals_for({**brief, "more_pictures": True}, model, log=log) if v["ask"].lower() not in asked]
        visuals = visuals[:MAX_VISUALS]
    if len(visuals) < MAX_VISUALS and brief.get("picture_plan"):
        # Told a card's plan, the model answers with that ONE picture, and when the service could not draw it the
        # lesson had none (the water cycle: a custom landscape failed the service's checks, while the textbook's
        # diagram, never asked for, comes back student ready). The topic's own pictures stand behind the plan's.
        asked = {v["ask"].lower() for v in visuals}
        visuals += [v for v in visuals_for({k: v for k, v in brief.items() if k != "picture_plan"}, model, log=log)
                    if v["ask"].lower() not in asked]
        visuals = visuals[:MAX_VISUALS]
    if not visuals:
        return None
    # One drawing at a time, in the teacher's order, stopping at the first that can be shown.
    drawn: list = []
    for visual in visuals[:MAX_TRIES]:
        drawn.append(prepare_checked(visual["ask"], klass, "en", log=log))
        if drawn[-1]:
            break
    visuals = visuals[:len(drawn)]
    choice = next(((v, r) for v, r in zip(visuals, drawn) if r), None)       # the model's order is the teacher's order
    tried = "; ".join(f"“{v['ask'][:60]}…” → " + ("no usable drawing" if not r else f"{len(r['parts'])} part(s) to point at"
                                                    if r["shown"] == "parts" else "shown whole")
                      for v, r in zip(visuals, drawn))
    kept[key] = {"topic": topic, "class": klass, **(choice[0] if choice else {"ask": ""}), "tried": tried,
                 # the words the drawing that was kept was actually asked for with (a second try names what was wrong)
                 "drawn": json.loads((Path(choice[1]["manifest"]).parent / "source.json").read_text(encoding="utf-8")).get("ask", "")
                 if choice and (Path(choice[1]["manifest"]).parent / "source.json").is_file() else "",
                 "judge": _judged_by(), "asking": ASKING_VERSION, "when": time.strftime("%Y-%m-%d %H:%M")}
    try:
        saved.write_text(json.dumps(kept, indent=1, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass
    if not choice:
        log(f"[diagram] no picture for “{topic}” that a lesson can point into ({tried})")
        return None
    visual, ready = choice
    log(f"[diagram] the lesson's picture: “{visual['ask'][:90]}” ("
        + (f"{len(ready['parts'])} part(s) to point at: {', '.join(ready['parts'][:8])}" if ready["shown"] == "parts"
           else "shown whole, with its own words") + ")")
    return {**ready, "shows": visual["shows"], "visual_kind": visual["kind"]}
