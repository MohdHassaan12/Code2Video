"""The words printed on a typeset drawing: where each one is, and what it says.

About half of what the owner's drawing service returns is TYPESET (a circuit, a division
ladder, fraction strips, a demonstration before and after): drawn by a typesetting
program, with every letter an outline. ``harness/diagrams.py`` finds no ``<text>`` in such
a drawing, so "nothing in it can be named" and a lesson showed it whole and still while
the voice walked through it. The owner, 2026-10-09: "the visuals are bad"; of an earlier
use of their drawings, "a raw way of using".

The letters are not lost, only unnamed. Every one is a ``<use>`` of a glyph, so:

1. a headless browser is handed the drawing with a few lines of script and writes down
   every glyph's rectangle (``measure``): exact, no model, no network;
2. glyphs that share a line and stand no farther apart than a word space are one label
   (``labels_of``). Tried on six drawings of the library the day it was written: every
   printed label boxed, none split, none joined to its neighbour;
3. what a box SAYS takes one look by a small vision model at the drawing with its boxes
   numbered (``read``). Looking, not drawing: the owner's rule is that no picture is made
   by anything but their service. Code keeps a reading only when it is short, and a
   reading two boxes share names neither (nobody could tell which "3" was meant).

``names`` does all three once per drawing and keeps the answer IN the drawing's manifest
(``manifest["typeset"] = {slug: {"name", "box"}}``; a box is x0, y0, x1, y1 as shares of
the source drawing, so it survives whatever file and size the drawing is shown at).
``HARNESS_TYPESET_NAMES=0`` switches the look off (as in tests); the measuring needs only
a browser.
"""
from __future__ import annotations

import html
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path

from .. import knobs
from . import diagrams

VERSION = 3                 # of what ``names`` keeps: raise it when the kept shape or the rules below change
#                             2: a heading's words are one label (the space is judged by the label's own letters),
#                                upright text is one label, a hyphenated label is joined with its second line, the
#                                reader is shown small print enlarged, and "(a)" is not a name
MAX_LABELS = 40             # boxes shown to the reader at most (a drawing with more is a page of text, not a picture)
MAX_WORDS = 4               # a label longer than this is a sentence printed on the drawing, not a thing to point at
# Of a tall letter's height: glyphs this close on one line are the same label. 0.75 until 2026-10-12: a ray diagram's
# "Reflected ray" was two labels (its word space is 0.82 of a tall letter, "Incident ray"'s 0.7), and a lesson marked
# "ray" alone, on the reflected ray's label, under words about the incident one. Measured on the library's 31 typeset
# drawings before it was raised: 0.9 joins eleven pairs, all of them one label ("Leaf C" + "(No CO2)"); 1.15 joins a
# heading with a line under it.
WORD_SPACE = 0.9
_WIDTH = 1280               # pixels the drawing is measured at (any width gives the same shares)

_SCRIPT = """
const svg = document.querySelector('svg');
const vb = svg.viewBox.baseVal, W = %d;
const H = vb && vb.width ? W * vb.height / vb.width : W * svg.getBoundingClientRect().height / svg.getBoundingClientRect().width;
svg.setAttribute('width', W); svg.setAttribute('height', H);
const out = {width: W, height: H, glyphs: [], texts: svg.querySelectorAll('text').length};
for (const el of svg.querySelectorAll('use')) {
  if (el.closest('defs')) continue;
  const href = el.getAttribute('xlink:href') || el.getAttribute('href') || '';
  if (!href.includes('glyph')) continue;
  const r = el.getBoundingClientRect();
  if (r.width || r.height) out.glyphs.push([r.left, r.top, r.right, r.bottom].map(v => Math.round(v * 10) / 10));
}
document.getElementById('out').textContent = JSON.stringify(out);
""" % _WIDTH

READ_SYSTEM = """You read the printed text in a drawing made for a school lesson. Some pieces of text have a red box around
them and a red number beside the box. For EACH numbered box, write exactly the text printed inside it: the same
words, the same spelling, the same digits and signs (a fraction as "1/2", a multiplication sign as "×"). Read only
what is inside the box; never describe the drawing, never guess a word you cannot see.
Return ONLY JSON: {"1": "…", "2": "…"} with one entry per box; give "" for a box whose text you cannot read."""


def reading() -> bool:
    return (knobs.get("HARNESS_TYPESET_NAMES") or "1").strip() != "0"


def measure(svg_path: Path, chrome: str | None = None) -> dict | None:
    """Every glyph's rectangle in the drawing, as a browser lays it out: ``{"width", "height", "glyphs", "texts"}``.

    None when there is no browser, the drawing is not one this module may hand to a browser
    (``diagrams.safe``), or nothing came back. The page holds the drawing and this module's own
    script, nothing of the drawing's is run (a drawing with a script in it is refused first).
    """
    chrome = chrome or diagrams.browser()
    try:
        raw = Path(svg_path).read_bytes()
    except OSError:
        return None
    if not chrome or diagrams.safe(raw) or b"<svg" not in raw:
        return None
    text = raw.decode("utf-8", "replace")
    text = text[text.index("<svg"):]
    try:
        with tempfile.TemporaryDirectory() as tmp:
            page = Path(tmp) / "page.html"
            page.write_text("<!doctype html><html><body style='margin:0'>" + text
                            + f"<pre id='out'></pre><script>{_SCRIPT}</script></body></html>", encoding="utf-8")
            dom = subprocess.run([chrome, "--headless=new", "--disable-gpu", "--no-sandbox", f"--user-data-dir={tmp}/profile",
                                  "--virtual-time-budget=3000", "--dump-dom", page.as_uri()],
                                 capture_output=True, text=True, timeout=60).stdout
        found = re.search(r'<pre id="out">(.*?)</pre>', dom, re.S)
        measured = json.loads(html.unescape(found.group(1))) if found and found.group(1).strip() else None
    except (OSError, ValueError, subprocess.SubprocessError):
        return None
    if not isinstance(measured, dict) or not measured.get("width") or not measured.get("height"):
        return None
    return measured


def labels_of(glyphs: list) -> list[list[float]]:
    """Glyph rectangles joined into labels, in reading order.

    Letters on one line with no gap wider than a word space are one label; the space is judged by the
    taller of the usual letter and the two pieces being joined, so a heading set larger than the rest
    ("Square Number", "Figure (a)") is not cut at its wider spaces. Letters standing one right above the
    other with almost nothing between them are text set upright (a label written along an arrow) and are
    joined too; two LINES of text are wider than a letter and stay two labels.
    """
    boxes = [[float(v) for v in g[:4]] for g in glyphs if len(g) >= 4]
    if not boxes:
        return []
    heights = sorted(b[3] - b[1] for b in boxes)
    tall = max(heights[len(heights) * 3 // 4], 1.0)          # a tall letter: dots, dashes and commas do not set the scale

    def on_a_line(a, b) -> bool:
        scale = max(tall, min(a[3] - a[1], b[3] - b[1]))
        return (min(a[3], b[3]) - max(a[1], b[1]) >= -0.15 * tall           # on one line (a dash sits between the lines)
                and max(a[0], b[0]) - min(a[2], b[2]) <= WORD_SPACE * scale)

    def upright(a, b) -> bool:
        # Pieces no wider than a letter, one right above the other: text set upright. Two one-letter labels in a
        # column ("4" over "4" in a table) are more than half a letter apart and stay two.
        across = min(a[2], b[2]) - max(a[0], b[0])
        return (max(a[2] - a[0], b[2] - b[0]) <= 1.3 * tall and across >= 0.6 * min(a[2] - a[0], b[2] - b[0])
                and 0 <= max(a[1], b[1]) - min(a[3], b[3]) <= 0.45 * tall)

    for near in (on_a_line, upright):
        joined = True
        while joined:
            joined = False
            for i in range(len(boxes)):
                for j in range(i + 1, len(boxes)):
                    if near(boxes[i], boxes[j]):
                        a, b = boxes[i], boxes.pop(j)
                        boxes[i] = [min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3])]
                        joined = True
                        break
                if joined:
                    break
    return sorted(boxes, key=lambda b: (round(b[1] / tall), b[0]))


def numbered(picture: Path, boxes: list, width: float):
    """The drawing on white with each label boxed and numbered in red: what the reader is shown."""
    from PIL import Image, ImageDraw, ImageFont  # noqa: PLC0415
    image = Image.open(picture).convert("RGBA")
    ground = Image.new("RGBA", image.size, "white")
    ground.alpha_composite(image)
    ground = ground.convert("RGB")
    # Small print is read wrongly ("Identica" for "Identical"): the reader is shown the drawing enlarged until a
    # usual label is about 26 pixels tall, twice at most.
    usual = sorted(b[3] - b[1] for b in boxes)[len(boxes) // 2] * ground.width / float(width) if boxes else 26.0
    grow = min(2.0, max(1.0, 26.0 / max(usual, 1.0)))
    if grow > 1.05:
        ground = ground.resize((round(ground.width * grow), round(ground.height * grow)), Image.LANCZOS)
    k = ground.width / float(width)
    pad = 26                                        # room for a number left of a label at the drawing's edge
    sheet = Image.new("RGB", (ground.width + 2 * pad, ground.height + 2 * pad), "white")
    sheet.paste(ground, (pad, pad))
    draw = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.truetype("DejaVuSans-Bold.ttf", 15)
    except OSError:
        font = ImageFont.load_default()
    for n, box in enumerate(boxes, 1):
        x0, y0, x1, y1 = (box[0] * k + pad - 3, box[1] * k + pad - 3, box[2] * k + pad + 3, box[3] * k + pad + 3)
        draw.rectangle([x0, y0, x1, y1], outline=(215, 25, 25), width=2)
        tag = str(n)
        w = draw.textlength(tag, font=font)
        draw.rectangle([x0 - w - 5, y0 - 1, x0 - 1, y0 + 17], fill="white")
        draw.text((x0 - w - 3, y0), tag, fill=(215, 25, 25), font=font)
    return sheet


def pointable(text: str) -> str:
    """A reading as a NAME, or "" when it is not a thing to point at (a sentence, a lone sign, nothing)."""
    name = re.sub(r"\s+", " ", str(text or "")).strip().strip("\"'“”").rstrip(":").strip()[:48]
    if not (re.search(r"[A-Za-z]{2}", name) or re.search(r"\d", name)):
        return ""                                   # "(a)", "+", "×": a mark, not a name
    words = name.split()
    formula = not re.search(r"[A-Za-z]{2,}", name) and len(name) <= 28      # "36 = 2 × 2 × 3 × 3" is one thing
    return name if len(words) <= MAX_WORDS or formula else ""


def read(picture: Path, boxes: list, width: float, look, log=print) -> dict[int, str]:
    """What each box says, by one look: ``{box index: text}`` for the boxes that could be read."""
    import base64  # noqa: PLC0415
    import io  # noqa: PLC0415
    sheet = numbered(picture, boxes, width)
    sheet.thumbnail((2600, 2600))
    buffer = io.BytesIO()
    sheet.save(buffer, format="JPEG", quality=88)
    answer = look(f"There are {len(boxes)} numbered boxes, 1 to {len(boxes)}.", READ_SYSTEM,
                  base64.b64encode(buffer.getvalue()).decode())
    if not isinstance(answer, dict):
        return {}
    out = {}
    for key, value in answer.items():
        digits = re.sub(r"\D", "", str(key))
        if digits and 1 <= int(digits) <= len(boxes) and isinstance(value, (str, int, float)) and str(value).strip():
            out[int(digits) - 1] = str(value)
    return out


def named(boxes: list, readings: dict[int, str], width: float, height: float) -> dict[str, dict]:
    """Boxes and their readings as the kept shape: ``{slug: {"name", "box"}}``, boxes as shares of the drawing.

    A reading that is not a name is left out, and so is every box of a reading that two boxes
    share: a ring on the wrong one of two "3"s is worse than no ring.
    """
    readings, boxes = dict(readings), [list(b) for b in boxes]
    heights = sorted(b[3] - b[1] for b in boxes)
    tall = heights[len(heights) * 3 // 4] if heights else 1.0
    for index, text in sorted(readings.items()):
        # "Prime Fac-" over "tors (Divisors)": one label set on two lines. The second line is the nearest box under
        # the first that it overlaps; a first half with no second half is no name at all.
        if not str(text).rstrip().endswith("-") or not 0 <= index < len(boxes):
            continue
        top = boxes[index]
        under = [(boxes[j][1] - top[3], j) for j in readings if j != index and 0 <= j < len(boxes)
                 and 0 <= boxes[j][1] - top[3] <= 1.2 * tall and min(top[2], boxes[j][2]) - max(top[0], boxes[j][0]) > 0]
        if under:
            j = min(under)[1]
            low = boxes[j]
            readings[index] = str(text).rstrip()[:-1] + str(readings.pop(j)).lstrip()
            boxes[index] = [min(top[0], low[0]), top[1], max(top[2], low[2]), low[3]]
        else:
            readings.pop(index)
    found: dict[str, list] = {}
    for index, text in sorted(readings.items()):
        name = pointable(text)
        key = diagrams.slug(name) if name else ""
        if key and 0 <= index < len(boxes):
            box = boxes[index]
            upright = box[3] - box[1] > 1.5 * (box[2] - box[0])
            if upright and re.search(r"[A-Za-z]{2}", name):
                continue          # letters in a sliver taller than wide: a piece of text set upright along an arrow
            stacked = re.fullmatch(r"(\d{1,3})\s+(\d{1,3})", name)
            if upright and stacked:
                name = f"{stacked.group(1)}/{stacked.group(2)}"       # one number over another: a fraction, read "1 2"
                key = diagrams.slug(name)
            found.setdefault(key, []).append((name, boxes[index]))
    out = {}
    for key, entries in found.items():
        if len(entries) == 1:
            name, box = entries[0]
            out[key] = {"name": name, "box": [round(max(0.0, box[0] / width), 4), round(max(0.0, box[1] / height), 4),
                                              round(min(1.0, box[2] / width), 4), round(min(1.0, box[3] / height), 4)]}
    return out


def names(manifest_path, look=None, log=print) -> dict[str, dict]:
    """The names a typeset drawing can be pointed at: ``{slug: {"name", "box"}}``; {} for any other drawing.

    Made once and kept in the drawing's manifest under ``"typeset"`` (with ``VERSION``); a drawing
    that could not be read is asked about again next time, one that has no outlined words is noted
    as having none. Never raises.
    """
    path = Path(manifest_path)
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return {}
    kept = manifest.get("typeset")
    if isinstance(kept, dict) and kept.get("version") == VERSION and isinstance(kept.get("names"), dict):
        return kept["names"]
    folder = path.parent
    try:
        measured = measure(folder / "source.svg")
        if not measured:
            return {}
        boxes = labels_of(measured.get("glyphs") or [])
        result: dict[str, dict] = {}
        if boxes and not measured.get("texts") and len(boxes) <= MAX_LABELS:
            if not reading():
                return {}
            picture = next((folder / n for n in (manifest.get("whole") or "whole.png", "source.png") if n and (folder / n).is_file()), None)
            if picture is None:
                return {}
            if look is None:
                from . import vision_review  # noqa: PLC0415
                look = vision_review.default_judge()
            if look is None:
                return {}
            readings = read(picture, boxes, measured["width"], look, log=log)
            if not readings:
                log("[typeset] the drawing's words could not be read: it stays unpointed for now")
                return {}                               # not kept: a failed look is asked for again
            result = named(boxes, readings, measured["width"], measured["height"])
            log(f"[typeset] {len(boxes)} printed label(s) found, {len(result)} can be pointed at: "
                + ", ".join(entry["name"] for entry in result.values())[:160])
        # Kept in the manifest as it is NOW: whoever takes a drawing apart rewrites this file.
        manifest = json.loads(path.read_text(encoding="utf-8"))
        manifest["typeset"] = {"version": VERSION, "names": result}
        part = path.with_suffix(".part")
        part.write_text(json.dumps(manifest, indent=1, ensure_ascii=False), encoding="utf-8")
        part.replace(path)
        return result
    except Exception as exc:  # noqa: BLE001 - pointing is an improvement, never a requirement
        log(f"[typeset] the drawing's words were not found ({type(exc).__name__}: {str(exc)[:100]})")
        return {}
