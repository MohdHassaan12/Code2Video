"""A drawing as a SEQUENCE of its parts: what a hand would draw, in the order it would draw it, as JSON.

The owner, 2026-10-12: "the visuals are static … take the SVG and divide the SVG components into JSON. Different
parts of the visual should be coming in a sequence as JSON, which contains the text and parts of the SVG. Then you
take the pattern and style it." A drawing from the drawing service was shown as one finished picture: it faded in
whole and stood still. Its SVG knows more than that. Every line, shape and label in it is an element of its own, with
its own geometry, so the drawing can be DRAWN: part by part, the way it is put on a blackboard.

``sequence(folder)`` walks the SVG in a headless browser (the same way ``typeset`` measures its glyphs: the page holds
the drawing and this module's own script, nothing of the drawing's is run) and writes ``sequence.json`` beside it::

    {"version": …, "of": <digest of the SVG>, "width": 1280, "height": 859,
     "parts": [{"n": 1, "kind": "stroke" | "fill" | "text",
                "svg": "<path … />",                      the part of the SVG this is, as the browser holds it
                "text": "",                               what a label says (kind "text"; "" when it was not read)
                "box": [x0, y0, x1, y1],                  where it is, as shares of the drawing (0 to 1)
                "points": [[x, y], …],                    its outline in drawing order, as shares of the drawing
                "closed": false, "stroke": "#000099", "fill": "", "width": 0.0033, "dashed": false, "dash": 0.0,
                "length": 0.71},                          how much pen it takes (in drawing widths)
               …]}

Order: the drawing's own (an SVG paints its elements first to last, which is ground before detail), except that a
tiny piece (an arrowhead, a tick) follows the stroke it belongs to and a label follows the last shape drawn near it,
so a line and its name arrive together. Coordinates are shares of the drawing, so the picture a lesson shows can be
any size. Nothing here asks a model; one browser run a drawing, kept beside it.
"""
from __future__ import annotations

import hashlib
import html
import json
import re
import subprocess
import tempfile
from pathlib import Path

from .. import knobs
from . import diagrams

VERSION = "sequence-4"            # 3: labels joined by typeset's wider word space; 4: clip paths, a fill's own opacity, "faithful"
MAX_PARTS = 160               # more than this and the drawing is not one to draw by hand: it is shown as before
_WIDTH = 1280

_SCRIPT = r"""
const svg = document.querySelector('svg');
const vb = svg.viewBox.baseVal, W = %d;
const H = vb && vb.width ? W * vb.height / vb.width : W * svg.getBoundingClientRect().height / svg.getBoundingClientRect().width;
svg.setAttribute('width', W); svg.setAttribute('height', H);
const hex = c => { const m = /rgba?\(([^)]+)\)/.exec(c || ''); if (!m) return ''; const p = m[1].split(',').map(s => parseFloat(s));
  if (p.length > 3 && p[3] === 0) return ''; return '#' + p.slice(0, 3).map(v => Math.round(v).toString(16).padStart(2, '0')).join(''); };
const out = {width: W, height: H, shapes: [], texts: [], unseen: 0};
// What this script cannot give a pen: a raster picture inside the drawing, a gradient or a pattern as paint, a mask, a filter.
out.unseen += svg.querySelectorAll('image').length;
const clipOf = node => {            // the outline of a clip path, in the frame of the element that is clipped by it
  const found = /url\(["']?#([^"')]+)/.exec(getComputedStyle(node).clipPath || '');
  const clip = found && document.getElementById(found[1]);
  if (!clip) return null;
  const nm = node.getScreenCTM(), polys = [];
  for (const child of clip.querySelectorAll('path, rect, circle, ellipse, polygon')) {
    if (typeof child.getTotalLength !== 'function') continue;
    const total = child.getTotalLength();
    if (!(total > 0)) continue;
    const n = Math.max(4, Math.min(160, Math.ceil(total / 3))), pts = [];
    for (let i = 0; i < n; i++) { const q = child.getPointAtLength(total * i / n);
      pts.push([r4((nm.a * q.x + nm.c * q.y + nm.e) / W), r4((nm.b * q.x + nm.d * q.y + nm.f) / H)]); }
    polys.push(pts);
  }
  return polys.length === 1 ? polys[0] : (polys.length ? 'many' : null);
};
const r4 = v => Math.round(v * 10000) / 10000;
let order = 0;
const walker = svg.querySelectorAll('path, line, polyline, polygon, rect, circle, ellipse, text, use');
for (const el of walker) {
  if (el.closest('defs') || el.closest('clipPath') || el.closest('mask') || el.closest('symbol') || el.closest('marker') || el.closest('pattern')) continue;
  order += 1;
  const cs = getComputedStyle(el);
  if (cs.display === 'none' || cs.visibility === 'hidden' || parseFloat(cs.opacity) === 0) continue;
  const r = el.getBoundingClientRect();
  if (!(r.width || r.height)) continue;
  const box = [r4(r.left / W), r4(r.top / H), r4(r.right / W), r4(r.bottom / H)];
  if (el.tagName === 'text') { out.texts.push({order, box, text: el.textContent.replace(/\s+/g, ' ').trim(), svg: el.outerHTML.slice(0, 600)}); continue; }
  if (el.tagName === 'use') { const href = el.getAttribute('xlink:href') || el.getAttribute('href') || '';
    if (href.includes('glyph')) out.texts.push({order, box, text: '', glyph: true}); continue; }
  if (typeof el.getTotalLength !== 'function') continue;
  const stroke = cs.stroke === 'none' ? '' : hex(cs.stroke), fill = cs.fill === 'none' ? '' : hex(cs.fill);
  if (/^url/.test(cs.fill) || /^url/.test(cs.stroke) || (cs.mask && cs.mask !== 'none' && !/^none/.test(cs.mask)) || (cs.filter && cs.filter !== 'none')) out.unseen += 1;
  if (!stroke && !fill) continue;
  // clip paths this element is drawn through (its own and its ancestors'), kept only when they cut something off it
  const clips = [];
  for (let node = el; node && node !== svg; node = node.parentElement) {
    const poly = clipOf(node);
    if (!poly) continue;
    if (poly === 'many') { clips.push('many'); continue; }
    const xs = poly.map(q => q[0]), ys = poly.map(q => q[1]);
    const inside = box[0] >= Math.min(...xs) - 0.001 && box[2] <= Math.max(...xs) + 0.001 && box[1] >= Math.min(...ys) - 0.001 && box[3] <= Math.max(...ys) + 0.001;
    const rect = poly.every(q => (Math.abs(q[0] - Math.min(...xs)) < 0.0015 || Math.abs(q[0] - Math.max(...xs)) < 0.0015 || Math.abs(q[1] - Math.min(...ys)) < 0.0015 || Math.abs(q[1] - Math.max(...ys)) < 0.0015));
    if (!(inside && rect)) clips.push(poly);
  }
  const m = el.getScreenCTM();
  const scale = Math.sqrt(Math.abs(m.a * m.d - m.b * m.c));
  // each subpath of a path is a stroke of its own: the pen is lifted between them
  let pieces = [el];
  const temp = [];
  if (el.tagName === 'path') {
    const chunks = (el.getAttribute('d') || '').split(/(?=[Mm])/).map(s => s.trim()).filter(s => s.length > 1);
    if (chunks.length > 1 && !/[m]/.test(el.getAttribute('d'))) {
      pieces = [];
      for (const d of chunks) { const c = el.cloneNode(false); c.setAttribute('d', d); el.parentNode.insertBefore(c, el); temp.push(c);
        if (c.getTotalLength() > 0.01) pieces.push(c); }
    }
  }
  for (const piece of pieces) {
    const total = piece.getTotalLength();
    if (!(total > 0)) continue;
    const pm = piece.getScreenCTM();
    const n = Math.max(2, Math.min(220, Math.ceil(total * scale / 4)));
    const pts = [];
    for (let i = 0; i <= n; i++) { const p = piece.getPointAtLength(total * i / n);
      pts.push([r4((pm.a * p.x + pm.c * p.y + pm.e) / W), r4((pm.b * p.x + pm.d * p.y + pm.f) / H)]); }
    const first = pts[0], last = pts[pts.length - 1];
    const closed = /[Zz]\s*$/.test(piece.getAttribute('d') || '') || ['rect', 'circle', 'ellipse', 'polygon'].includes(piece.tagName)
      || (Math.hypot((first[0] - last[0]) * W, (first[1] - last[1]) * H) < 1.5 && pts.length > 3);
    const pr = piece.getBoundingClientRect();
    out.shapes.push({order, tag: el.tagName, box: [r4(pr.left / W), r4(pr.top / H), r4(pr.right / W), r4(pr.bottom / H)], points: pts, closed,
      stroke, fill, width: r4(parseFloat(cs.strokeWidth || '1') * scale / W), dashed: cs.strokeDasharray !== 'none',
      dash: cs.strokeDasharray !== 'none' ? r4(cs.strokeDasharray.split(/[ ,]+/).slice(0, 2).reduce((a, v) => a + (parseFloat(v) || 0), 0) * scale / W) : 0,
      opacity: r4(parseFloat(cs.opacity) * (stroke ? parseFloat(cs.strokeOpacity || '1') : parseFloat(cs.fillOpacity || '1'))),
      fill_opacity: fill ? r4(parseFloat(cs.opacity) * parseFloat(cs.fillOpacity || '1')) : 0, clips,
      length: r4(total * scale / W), svg: piece.outerHTML.slice(0, 900)});
  }
  for (const c of temp) c.remove();
}
document.getElementById('out').textContent = JSON.stringify(out);
""" % _WIDTH


def measure(svg_path: Path, chrome: str | None = None) -> dict | None:
    """Every drawable element of the SVG as a browser lays it out: ``{"width", "height", "shapes", "texts"}``; None
    with no browser, for a drawing this module may not hand to one (``diagrams.safe``), or when nothing came back."""
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
                                  "--virtual-time-budget=4000", "--dump-dom", page.as_uri()],
                                 capture_output=True, text=True, timeout=90).stdout
        found = re.search(r'<pre id="out">(.*?)</pre>', dom, re.S)
        measured = json.loads(html.unescape(found.group(1))) if found and found.group(1).strip() else None
    except (OSError, ValueError, subprocess.SubprocessError):
        return None
    if not isinstance(measured, dict) or not measured.get("width") or not measured.get("height"):
        return None
    return measured


def _labels(texts: list[dict], width: float, height: float) -> list[dict]:
    """Glyphs joined into labels (``typeset.labels_of``), and SVG text elements as they are: ``{"order", "box", "text"}``."""
    from . import typeset  # noqa: PLC0415
    out = [{"order": t["order"], "box": t["box"], "text": t.get("text", ""), "svg": t.get("svg", "")} for t in texts if not t.get("glyph")]
    glyphs = [t for t in texts if t.get("glyph")]
    if glyphs:
        pixels = [[g["box"][0] * width, g["box"][1] * height, g["box"][2] * width, g["box"][3] * height] for g in glyphs]
        for x0, y0, x1, y1 in typeset.labels_of(pixels):
            inside = [g["order"] for g, p in zip(glyphs, pixels) if p[0] >= x0 - 1 and p[2] <= x1 + 1 and p[1] >= y0 - 1 and p[3] <= y1 + 1]
            out.append({"order": min(inside) if inside else 10 ** 6, "box": [round(x0 / width, 4), round(y0 / height, 4), round(x1 / width, 4), round(y1 / height, 4)],
                        "text": "", "svg": ""})
    return out


def _corners(poly: list, slack: float = 0.0008) -> list:
    """An outline without the points that lie on a straight run between their neighbours (a browser gives a point
    every few pixels, rounded: along a straight edge they wobble to either side by a hair)."""
    out = [list(p) for p in poly]
    changed = True
    while changed and len(out) > 3:
        changed = False
        for i in range(len(out)):
            (ax, ay), (bx, by), (cx, cy) = out[i - 1], out[i], out[(i + 1) % len(out)]
            span = ((cx - ax) ** 2 + (cy - ay) ** 2) ** 0.5
            off = abs((cx - ax) * (by - ay) - (cy - ay) * (bx - ax)) / span if span > 1e-9 else 0.0
            if off < slack:
                del out[i]
                changed = True
                break
    return out


def _convex(poly: list) -> bool:
    sign = 0
    for i in range(len(poly)):
        (ax, ay), (bx, by), (cx, cy) = poly[i], poly[(i + 1) % len(poly)], poly[(i + 2) % len(poly)]
        cross = (bx - ax) * (cy - by) - (by - ay) * (cx - bx)
        if abs(cross) > 1e-7:
            if sign and (cross > 0) != (sign > 0):
                return False
            sign = 1 if cross > 0 else -1
    return bool(sign)


def _cut(points: list, clip: list) -> list:
    """A closed outline cut to a convex clip outline (Sutherland and Hodgman): what of the shape a viewer sees."""
    area = sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(clip, clip[1:] + clip[:1]))
    clip = clip if area > 0 else clip[::-1]
    out = [list(p) for p in points]
    for (ax, ay), (bx, by) in zip(clip, clip[1:] + clip[:1]):
        inside = lambda p: (bx - ax) * (p[1] - ay) - (by - ay) * (p[0] - ax) >= -1e-9           # noqa: E731
        kept, source = [], out
        if not source:
            break
        for i, cur in enumerate(source):
            prev = source[i - 1]
            if inside(cur) != inside(prev):
                dx, dy = cur[0] - prev[0], cur[1] - prev[1]
                denom = (bx - ax) * dy - (by - ay) * dx
                t = ((by - ay) * (prev[0] - ax) - (bx - ax) * (prev[1] - ay)) / denom if abs(denom) > 1e-12 else 0.0
                kept.append([round(prev[0] + t * dx, 4), round(prev[1] + t * dy, 4)])
            if inside(cur):
                kept.append(cur)
        out = kept
    return out


def clipped(shapes: list[dict], aspect: float = 1.0) -> tuple[list[dict], int]:
    """Every shape as a viewer sees it: cut to the clip paths it is drawn through. ``(shapes, cannot)``: how many shapes
    are clipped in a way this cannot follow (a clip outline that is not convex, several outlines, an open line).

    A typesetter draws a shaded sector as a whole disc clipped by the triangle it sits in: drawn by its own outline, three
    corners of a triangle were three discs lying over it (a lesson of 2026-10-12, seen once the pen-work stood for a
    whole beat instead of five seconds)."""
    out, cannot = [], 0
    for shape in shapes:
        clips = shape.get("clips") or []
        if not clips:
            out.append(shape)
            continue
        points = [list(p) for p in shape["points"]]
        for clip in clips:
            clip = _corners(clip) if clip != "many" else clip
            if clip == "many" or not shape.get("closed") or len(clip) < 3 or not _convex(clip):
                cannot += 1
                continue
            points = _cut(points, clip)
        if len(points) < 3:
            continue                                     # nothing of it is seen
        points = points + [points[0]]
        xs, ys = [p[0] for p in points], [p[1] for p in points]
        length = sum(((a[0] - b[0]) ** 2 + ((a[1] - b[1]) * aspect) ** 2) ** 0.5 for a, b in zip(points, points[1:]))
        out.append({**shape, "points": points, "box": [min(xs), min(ys), max(xs), max(ys)], "length": round(length, 4), "closed": True})
    return out, cannot


def _near(a: list, b: list) -> float:
    """The gap between two boxes (0 when they touch or overlap), in drawing widths."""
    dx = max(0.0, max(a[0], b[0]) - min(a[2], b[2]))
    dy = max(0.0, max(a[1], b[1]) - min(a[3], b[3]))
    return (dx * dx + dy * dy) ** 0.5


def order_parts(shapes: list[dict], labels: list[dict], names: dict | None = None) -> list[dict]:
    """The parts in the order a hand would draw them (see the module's note). ``names``: ``{slug: {"name", "box"}}`` from
    ``typeset`` for labels whose words were read."""
    strokes = []
    for shape in sorted(shapes, key=lambda s: s["order"]):
        kind = "fill" if shape.get("fill") and (shape.get("closed") or not shape.get("stroke")) else "stroke"
        last = strokes[-1] if strokes else None
        # The same outline twice, once filled and once stroked (how a typesetter writes a filled shape with an edge):
        # one part, outlined in the edge's colour and then filled.
        if last and last["kind"] == "fill" and not last.get("stroke") and kind == "stroke" and not shape.get("fill") \
                and max(abs(a - b) for a, b in zip(last["box"], shape["box"])) < 0.004 and abs(last["length"] - shape["length"]) < 0.01:
            last.update(stroke=shape["stroke"], width=shape["width"], svg=(last.get("svg", "") + shape.get("svg", ""))[:1400])
            continue
        strokes.append({**shape, "kind": kind, "text": ""})
    # a tiny piece (an arrowhead, a tick mark) is drawn right after the larger stroke it touches
    big = [s for s in strokes if s["length"] >= 0.03]
    small = [s for s in strokes if s["length"] < 0.03]
    after: dict[int, list] = {}
    loose = []
    for piece in small:
        host = min(big, key=lambda s: (_near(piece["box"], s["box"]), -s["order"]), default=None)
        if host is not None and _near(piece["box"], host["box"]) < 0.02:
            after.setdefault(id(host), []).append(piece)
        else:
            loose.append(piece)
    ordered, ends = [], []                                # ``ends[i]``: where the stroke that part i belongs to ends, pieces and all
    for stroke in big:
        group = [stroke] + after.get(id(stroke), [])
        ends += [len(ordered) + len(group) - 1] * len(group)
        ordered += group
    for piece in (loose if big else sorted(loose, key=lambda s: s["order"])):
        ends.append(len(ordered))
        ordered.append(piece)
    # a label follows the last of the shapes drawn nearest to it
    read = [(entry.get("box"), str(entry.get("name") or "")) for entry in (names or {}).values() if isinstance(entry, dict) and entry.get("box")]
    slots: dict[int, list] = {}
    for label in sorted(labels, key=lambda t: (round(t["box"][1], 2), t["box"][0])):
        said = label.get("text") or next((name for box, name in read if _near(label["box"], box) < 0.004
                                           and abs((box[0] + box[2]) - (label["box"][0] + label["box"][2])) < 0.03), "")
        part = {"kind": "text", "text": said, "box": label["box"], "points": [], "closed": False, "stroke": "", "fill": "",
                "width": 0.0, "dashed": False, "length": round(label["box"][2] - label["box"][0], 4), "svg": label.get("svg", ""),
                "order": label["order"], "opacity": 1.0}
        if ordered:
            gap = min(_near(label["box"], s["box"]) for s in ordered)
            host = ends[max((i for i, s in enumerate(ordered) if _near(label["box"], s["box"]) <= gap + 0.01), default=len(ordered) - 1)]
        else:
            host = -1
        slots.setdefault(host, []).append(part)
    parts = list(slots.get(-1, []))
    for i, stroke in enumerate(ordered):
        parts.append(stroke)
        parts += slots.get(i, [])
    return [{"n": n, **{k: part[k] for k in ("kind", "text", "box", "points", "closed", "stroke", "fill", "width", "dashed", "length", "svg")},
             "opacity": part.get("opacity", 1.0), "fill_opacity": part.get("fill_opacity", part.get("opacity", 1.0)),
             "dash": part.get("dash", 0.0)} for n, part in enumerate(parts, 1)]


def sequence(folder, log=print) -> dict | None:
    """The drawing in ``folder`` (a drawing of the library: ``source.svg``, ``manifest.json``) as its sequence of parts.

    Made once and kept as ``sequence.json``; None when the drawing has no SVG, no browser is there, or it has too few
    or too many parts to be drawn by hand (``MAX_PARTS``).
    """
    folder = Path(folder)
    source = folder / "source.svg"
    try:
        digest = hashlib.sha256(source.read_bytes()).hexdigest()[:16]
    except OSError:
        return None
    kept = folder / "sequence.json"
    try:
        names = (json.loads((folder / "manifest.json").read_text(encoding="utf-8")).get("typeset") or {}).get("names") or {}
    except (OSError, ValueError):
        names = {}
    # what its labels SAY comes from the drawing's own reading (``typeset.names``), which may be made, or made again,
    # after this: a sequence kept under other names is made again
    named = hashlib.sha256(json.dumps(names, sort_keys=True).encode()).hexdigest()[:12]
    try:
        made = json.loads(kept.read_text(encoding="utf-8"))
        if made.get("version") == VERSION and made.get("of") == digest and made.get("named") == named:
            return made if made.get("parts") else None
    except (OSError, ValueError):
        pass
    measured = measure(source)
    if not measured:
        return None
    shapes, cannot = clipped(measured["shapes"], float(measured["height"]) / max(float(measured["width"]), 1.0))
    parts = order_parts(shapes, _labels(measured["texts"], measured["width"], measured["height"]), names)
    drawable = sum(1 for part in parts if part["kind"] != "text")
    # ``faithful``: the parts, drawn by a pen, look like the drawing. Not when it holds what this cannot follow (a
    # raster picture, a gradient, a mask, a clip that is not a simple outline): such a drawing may be drawn in for a
    # few seconds before the finished picture comes, but its pen-work is not left standing (``with_words``).
    made = {"version": VERSION, "of": digest, "named": named, "faithful": not cannot and not int(measured.get("unseen") or 0),
            "width": measured["width"], "height": round(measured["height"], 1),
            "parts": parts if 2 <= drawable and len(parts) <= MAX_PARTS else []}
    try:
        kept.write_text(json.dumps(made, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass
    log(f"[sequence] the drawing as {len(parts)} part(s) in drawing order ({drawable} drawn, {len(parts) - drawable} label(s))"
        + ("" if made["parts"] else ": not one to draw by hand, shown as before"))
    return made if made["parts"] else None


def identity(made: dict | None) -> str:
    """Which taking-apart of a drawing this is. A plan of drawing it with the words names parts by their numbers, and
    the numbers are this sequence's: the lesson's figure carries the identity (``planned``), and the renderer holds
    nothing back when the sequence on disk is another one (``figures.PictureFigure.hold_back``)."""
    return ":".join(str((made or {}).get(k) or "") for k in ("version", "of", "named"))


def enabled() -> bool:
    """Whether drawings are taken apart into a sequence at all (``HARNESS_SEQUENCE``, on unless "0")."""
    import os  # noqa: PLC0415
    return (knobs.get("HARNESS_SEQUENCE") or "1").strip() != "0"


def for_lesson(lesson: dict, log=print) -> dict:
    """The sequence for every prepared drawing a lesson shows WHOLE (``figure["kind"] == "picture"``), made beside the
    drawing where the renderer looks for it. ``{"drawings", "made"}``. Nothing here raises."""
    summary = {"drawings": 0, "made": 0}
    if not enabled():
        return summary
    seen = set()
    for chapter in lesson.get("chapters") or []:
        for beat in chapter.get("beats") or []:
            figure = beat.get("figure") if isinstance(beat.get("figure"), dict) else {}
            file = Path(str(figure.get("file") or ""))
            if figure.get("kind") != "picture" or file.name != "whole.png" or str(file.parent) in seen:
                continue
            seen.add(str(file.parent))
            summary["drawings"] += 1
            try:
                summary["made"] += bool(sequence(file.parent, log=log))
            except Exception as exc:  # noqa: BLE001 - a drawing that cannot be taken apart is shown as before
                log(f"[sequence] the drawing is shown as before ({type(exc).__name__}: {str(exc)[:120]})")
    return summary


# ── drawn WITH the words ─────────────────────────────────────────────────────────────────────────────────────────────
#
# A drawing that draws itself when it arrives is finished five seconds into the lesson: it then holds everything the
# lesson is going to reach (the parallel line of a proof, the answer to the opening question) before a word of it.
# Beside a reference lecture on the same proof (docs/research/approaches/12): the lecturer's board has only the triangle
# for 53 seconds, and each line comes when it is spoken of. ``with_words`` says, for every thing in a drawing, at which
# of the lesson's steps a teacher would draw it; the steps then carry ``"draw": [part numbers]`` and the renderer holds
# a part back until its step's words (``figures.PictureFigure.hold_back``, ``runtime.GuidedChapter._draw_with``).
#
# Code decides what the THINGS are (a line with its arrowhead and its name; an angle's arc with its number) and keeps
# the plan consistent with the drawing; a model that sees the drawing and reads the words decides only WHEN each comes.

PLAN_VERSION = "with-words-1"
MAX_THINGS = 30               # things to decide about in one drawing; more, and it is drawn at once as before
MIN_WAITING = 2               # fewer things than this held back, and the drawing is drawn at once as before
NAME_REACH = 0.08             # how near (as a share of the drawing's width) a printed name stands to the thing it names
#: Who is asked. The small model that judges frames was tried first on one drawing, five times: it took our red numbers
#: for the drawing's own printed "1" to "5", put the proof's line on the board at the start in two of three later
#: answers, and held an angle's arc back for twenty steps as "showing the answer". This one gave a plan a teacher
#: would make, three times of three. About 1.7 cents a drawing against 0.3 (2026-10-12).
#: The owner the same evening: "use cheap models and improve the harness; work on the harness, not by taking costly
#: models". So the small model of that family is asked, SEVERAL times (``PLAN_VOTES``), and code puts the answers
#: together: each thing comes at the MEDIAN of the steps it was given, so one answer that holds a ray back to the end
#: or brings it at the start is outvoted. Read thing by thing on the reflection drawing, its single answers each had one
#: or two such things; three looks cost about half a cent against three for the large model's one.
#: ``HARNESS_PLAN_MODEL`` names another model, ``HARNESS_PLAN_VOTES`` another number of looks.
PLAN_MODEL = "anthropic/claude-haiku-5.5"
PLAN_VOTES = 3
BIG = 0.12                    # a stroke with at least this much pen is a thing of its own; shorter, it is a mark on one

PLAN_SYSTEM = """A teacher is going to draw this picture on a board WHILE saying the words of a lesson, the way a good teacher
does: nothing is on the board before the words reach it. You decide WHEN each thing is drawn.

You get the picture with its things tagged in red: #1, #2, … (the tag sits on the thing or beside its label). A red
tag with a hash sign is OUR tag; a number or letter printed in the picture without one is the picture's own label and
is not a tag. You also get the same things as a list, and the lesson's words beat by beat. The moments a new line comes up on the screen are numbered S1, S2, … in
order: those are the moments something can be drawn.

FIRST list every question the words ask the learner and leave open (a guess, a prediction, "which …?", "what will
…?"): the step it is asked at, the things in the picture that would by themselves TELL its answer to someone who sees
them (the path something takes, a result standing there, a printed value), and the step at which the words themselves
give the answer. Be strict: a mark or a label that only shows WHERE the question is about (the arc at the angle that
is asked for, the name of the unknown) tells nothing and is not listed; most questions have no such thing, and then
"shown_by" is [].

THEN, for EVERY tagged thing say what it is in the picture, in two to five words of your own (look at it: "the angle at
B", "the line through A", "the reflected ray"), and the step at which it is drawn:
- the step whose words first speak of that thing, or of what it measures. A measure or a number the words give for a
  place ("fifty degrees at B") IS the words speaking of the mark at that place;
- the thing the lesson starts from (what the first words describe) is drawn at S1;
- a step that marks a printed label (it is said beside the step) is usually the moment for the thing with that label;
- something that is ADDED to the picture in the telling (a line drawn through a point, a second object, an arrow, a
  result) waits for the step that adds it, however early it could be drawn;
- a thing that shows the answer to one of the questions you listed waits for the step where the words give that answer;
  it is never on the board while its question is open;
- a thing the words never speak of is drawn with the thing nearest to it; a frame or a ground line at S1.
Follow the words: do not put everything at S1 unless they really begin with all of it, and do not hold back what the
first words already describe.

Answer in JSON only, the questions first, then an entry for every thing:
{"questions": [{"asked_at": "S2", "asks": "which way it will move", "shown_by": ["#4"], "answered_at": "S9"}],
 "things": {"#1": ["what it is", "S1"], "#2": ["what it is", "S4"]}}"""


def _colour(value: str) -> str:
    value = str(value or "").lstrip("#")
    if len(value) != 6:
        return ""
    try:
        r, g, b = (int(value[i:i + 2], 16) / 255 for i in (0, 2, 4))
    except ValueError:
        return ""
    high, low = max(r, g, b), min(r, g, b)
    if high - low < 0.12:
        return "black" if high < 0.3 else "white" if high > 0.9 else "grey"
    if r >= g and r >= b:
        return "brown" if g > 0.25 and high < 0.75 and g > b else "orange" if g > 0.45 else "red" if b < 0.5 else "pink"
    if g >= r and g >= b:
        return "green"
    return "purple" if r > 0.45 else "blue"


def _where(box: list) -> str:
    x, y = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
    across = "left" if x < 0.36 else "right" if x > 0.64 else "middle"
    down = "top" if y < 0.36 else "bottom" if y > 0.64 else "middle"
    return "in the middle" if across == down == "middle" else f"{down} {across}" if down != "middle" else f"{across} side"


def _outline(part: dict) -> list:
    if part["kind"] == "text" or not part.get("points"):
        x0, y0, x1, y1 = part["box"]
        return [[(x0 + x1) / 2, (y0 + y1) / 2]]
    got = part["points"]
    return got if len(got) <= 48 else got[::max(1, len(got) // 48)] + [got[-1]]


def _to_outline(p, outline: list, aspect: float = 1.0):
    """``(distance, nearest point)`` from a point to an outline (its segments, not only its corners), in widths."""
    if len(outline) == 1:
        q = outline[0]
        return ((p[0] - q[0]) ** 2 + ((p[1] - q[1]) * aspect) ** 2) ** 0.5, q
    best, at = 9.0, outline[0]
    px, py = p[0], p[1] * aspect
    for a, b in zip(outline, outline[1:]):
        ax, ay, bx, by = a[0], a[1] * aspect, b[0], b[1] * aspect
        dx, dy = bx - ax, by - ay
        t = 0.0 if dx == dy == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
        d = ((px - ax - t * dx) ** 2 + (py - ay - t * dy) ** 2) ** 0.5
        if d < best:
            best, at = d, (ax + t * dx, (ay + t * dy) / aspect)
    return best, at


def _reach(a: list[dict], b: list[dict], aspect: float = 1.0) -> float:
    """How near two sets of parts come: the least distance between the outlines of one and of the other (a label: the
    middle of its box), in widths of the drawing."""
    return min(min(_to_outline(point, _outline(q), aspect)[0] for p in a for point in _outline(p) for q in b),
               min(_to_outline(point, _outline(p), aspect)[0] for q in b for point in _outline(q) for p in a))


def things_of(parts: list[dict], aspect: float = 1.0) -> list[dict]:
    """The THINGS in a drawing a teacher draws in one go, in drawing order, each ``{"numbers", "main", "marks", "labels",
    "big"}``: a line with the arrowheads on it and the words at it; an angle's arc with its number; a word standing alone.

    * a stroke with at least ``BIG`` of pen is a thing; a shorter one is a MARK;
    * a tiny piece follows the stroke before it (how the sequence is ordered); a filled mark that touches exactly one
      big thing (an arrowhead) belongs to it;
    * a label belongs to the thing drawn nearest to it; a white plate goes with the label on it.
    """
    plates = [p for p in parts if p["kind"] == "fill" and str(p.get("fill") or "").lower() in ("#ffffff", "#fff") and not p.get("stroke")]
    drawn = [p for p in parts if p["kind"] != "text" and p not in plates]
    things, last = [], None
    for part in drawn:
        if float(part.get("length") or 0) < 0.03 and last is not None and _near(part["box"], last["main"]["box"]) < 0.02:
            last["marks"].append(part)
            continue
        last = {"main": part, "marks": [], "labels": [], "big": float(part.get("length") or 0) >= BIG}
        things.append(last)
    big = [t for t in things if t["big"]]
    touched = {id(t): [b for b in big if _reach([t["main"]] + t["marks"], [b["main"]] + b["marks"], aspect) < 0.012]
               for t in things if not t["big"]}
    # a row of like marks on one thing (the hatching under a mirror, the ticks of a scale) is that thing's own
    rows: dict[tuple, list] = {}
    for thing in things:
        if not thing["big"] and thing["main"]["kind"] == "stroke" and len(touched[id(thing)]) == 1:
            rows.setdefault((id(touched[id(thing)][0]), thing["main"].get("stroke")), []).append(thing)
    for row in rows.values():
        lengths = sorted(float(t["main"]["length"]) for t in row)
        if len(row) >= 5 and lengths[-1] <= 1.6 * max(lengths[0], 1e-6):
            for thing in row:
                touched[id(thing)][0]["marks"] += [thing["main"]] + thing["marks"]
                things.remove(thing)
    for thing in [t for t in things if not t["big"] and t["main"]["kind"] == "fill"]:
        touching = touched[id(thing)]
        colours = {b["main"].get("stroke") or b["main"].get("fill") for b in touching}
        if len(touching) == 1:                       # an arrowhead at the end of a line
            touching[0]["marks"] += [thing["main"]] + thing["marks"]
            things.remove(thing)
        elif len(touching) == 2 and len(colours) == 1 and all(b in things for b in touching):
            # an arrowhead in the MIDDLE of a line: the line was written as two pieces, and is one thing
            first, second = touching
            first["marks"] += [thing["main"]] + thing["marks"] + [second["main"]] + second["marks"]
            things.remove(thing)
            things.remove(second)
            big.remove(second)
    for label in [p for p in parts if p["kind"] == "text"]:
        under = [p for p in plates if _near(label["box"], p["box"]) < 0.004]
        near = min(things, key=lambda t: (round(_reach([label], [t["main"]] + t["marks"], aspect), 3), parts.index(t["main"])), default=None)
        if near is not None and _reach([label], [near["main"]] + near["marks"], aspect) < 0.075:
            near["labels"].append(label)
            near["marks"] += under
        else:
            things.append({"main": label, "marks": under, "labels": [], "big": False})
    for thing in things:
        thing["numbers"] = [int(p["n"]) for p in [thing["main"]] + thing["marks"] + thing["labels"]]
    return things


def _described(thing: dict) -> str:
    part = thing["main"]
    said = [str(l.get("text") or "").strip() for l in thing["labels"]]
    named = [f"“{t}”" for t in said if t]
    if part["kind"] == "text":
        text = str(part.get("text") or "").strip()
        return (f"the printed label “{text}”" if text else "a printed letter or word") + f", {_where(part['box'])}"
    colour = _colour(part.get("stroke") or part.get("fill"))
    width, height = part["box"][2] - part["box"][0], part["box"][3] - part["box"][1]
    if part["kind"] == "fill":
        shape = "filled shape"
    elif part.get("dashed"):
        shape = "dashed line"
    elif part.get("closed"):
        shape = "closed outline"
    else:
        shape = "short curve or mark" if not thing["big"] else "line or curve"
    size = "small" if max(width, height) < 0.12 else "large" if max(width, height) > 0.5 else ""
    name = " ".join(w for w in (size, colour, shape) if w)
    extra = []
    if any(p["kind"] != "text" and p not in thing["labels"] for p in thing["marks"] if str(p.get("fill") or "").lower() not in ("#ffffff", "#fff")):
        extra.append("a small piece on it (an arrowhead or a tick)")
    if named:
        extra.append("the printed label" + ("s " if len(named) > 1 else " ") + ", ".join(named))
    elif said:
        extra.append("a printed letter or word at it" if len(said) == 1 else f"{len(said)} printed letters or words at it")
    return f"{'an' if name[0] in 'aeiou' else 'a'} {name}" + (" with " + " and ".join(extra) if extra else "") + f", {_where(part['box'])}"


def numbered(picture: Path, things: list[dict]):
    """The drawing with a red number on every thing to decide about: what the planner is shown."""
    from PIL import Image, ImageDraw, ImageFont  # noqa: PLC0415
    image = Image.open(picture).convert("RGBA")
    ground = Image.new("RGBA", image.size, "white")
    ground.alpha_composite(image)
    ground = ground.convert("RGB")
    if ground.width < 1500:
        ground = ground.resize((1500, round(ground.height * 1500 / ground.width)), Image.LANCZOS)
    pad = 30
    sheet = Image.new("RGB", (ground.width + 2 * pad, ground.height + 2 * pad), "white")
    sheet.paste(ground, (pad, pad))
    draw = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.truetype("DejaVuSans-Bold.ttf", 17)
    except OSError:
        font = ImageFont.load_default()
    taken = []
    for n, thing in enumerate(things, 1):
        part = thing["labels"][0] if thing["labels"] and not thing["big"] else thing["main"]
        if part["kind"] == "text" or not part.get("points"):
            x, y, beside = part["box"][0] - 0.004, (part["box"][1] + part["box"][3]) / 2, True
        else:
            points = part["points"]
            (x, y), beside = points[len(points) // 3 if part.get("closed") else len(points) // 2], False
        tag = f"#{n}"                               # never a bare number: a drawing prints numbers of its own ("angle 2")
        w = draw.textlength(tag, font=font)
        px = x * ground.width + pad - (w + 4 if beside else w / 2)
        py = y * ground.height + pad - 10
        for _ in range(12):                         # a number never sits on another number
            if not any(abs(px - ox) < 34 and abs(py - oy) < 19 for ox, oy in taken):
                break
            py += 20
        taken.append((px, py))
        draw.rectangle([px - 3, py - 1, px + w + 3, py + 19], fill="white", outline=(215, 25, 25))
        draw.text((px, py), tag, fill=(215, 25, 25), font=font)
    return sheet


def _rests_on(thing: dict, other: dict, aspect: float = 1.0) -> bool:
    """Whether ``thing`` is drawn ON ``other``: an end of its line (any point of a closed mark) lies on the other's
    outline, away from that outline's own ends. An arc between two arms rests on both arms; a dot on a line rests on
    it; three lines that meet in one point rest on none of each other (each would wait for the last)."""
    part, base = thing["main"], other["main"]
    points = part.get("points") or []
    outline = base.get("points") or []
    if len(points) < 2 or len(outline) < 2 or base["kind"] == "text" or part["kind"] == "text":
        return False
    tests = points if part.get("closed") or part["kind"] == "fill" else [points[0], points[-1]]
    tests = tests if len(tests) <= 24 else tests[::max(1, len(tests) // 24)]
    span = lambda a, b: ((a[0] - b[0]) ** 2 + ((a[1] - b[1]) * aspect) ** 2) ** 0.5                 # noqa: E731
    for p in tests:
        best, at = _to_outline(p, outline, aspect)
        if best < 0.012 and (base.get("closed") or (span(at, outline[0]) >= 0.03 and span(at, outline[-1]) >= 0.03)):
            return True
    return False


def settle(things: list[dict], when: dict[int, int], aspect: float = 1.0, answers: dict[int, int] | None = None) -> dict[int, int]:
    """A plan made consistent with the drawing itself (the plan is advice; this is what code can tell):

    * a thing the plan left out goes with the thing nearest to it;
    * the first big thing the SVG draws is the thing the lesson starts from, and is there when the drawing arrives
      (one plan held the triangle back until the fifth step and showed its labels around nothing);
    * a mark (an arc, a dot, a tick) is not drawn before a line it is drawn ON (``_rests_on``): an angle needs both
      its arms. Only marks: big things touch each other everywhere (a beaker stands in a tray, a stone hangs on a
      string), and made to wait for what they touch a whole second panel waited for its last drop of water;
    * what shows a question's answer is not there before the words give the answer (``answers``: thing -> step);
    * a printed name that stands alone is not there before the thing it stands beside (``NAME_REACH``);
    * a card is never empty: when nothing is planned for the first step, what comes first is there at the start.
    """
    parts = lambda t: [t["main"]] + t["marks"]                                    # noqa: E731
    out = dict(when)
    for n, thing in enumerate(things, 1):
        if n not in out:
            known = [m for m in out if m != n]
            out[n] = out[min(known, key=lambda m: _reach(parts(thing), parts(things[m - 1]), aspect))] if known else 1
    big = [n for n, thing in enumerate(things, 1) if thing["big"]]
    if big:
        out[big[0]] = 1
    for n, step in (answers or {}).items():
        if n in out and n != (big[0] if big else None):
            out[n] = max(out[n], step)
    for n, thing in enumerate(things, 1):
        if not thing["big"]:
            under = [m for m in big if things[m - 1]["main"]["kind"] == "stroke" and _rests_on(thing, things[m - 1], aspect)]
            if under:
                out[n] = max(out[n], max(out[m] for m in under))
    for n, thing in enumerate(things, 1):
        if thing["main"]["kind"] == "text":
            # A printed name that stands alone is not there before the thing it stands beside: one plan brought the
            # words "Reflected ray" eight steps before the ray (2026-10-12).
            others = [m for m, other in enumerate(things, 1) if m != n and other["main"]["kind"] != "text"]
            if others:
                beside = min(others, key=lambda m: _reach(parts(thing), parts(things[m - 1]), aspect))
                if _reach(parts(thing), parts(things[beside - 1]), aspect) <= NAME_REACH:
                    out[n] = max(out[n], out[beside])
    first = min(out.values(), default=1)
    if first > 1:
        out = {n: (1 if step == first else step) for n, step in out.items()}
    return out


def _beats_on(lesson: dict, file: str) -> list[dict]:
    return [beat for chapter in lesson.get("chapters") or [] for beat in chapter.get("beats") or []
            if isinstance(beat.get("figure"), dict) and beat["figure"].get("kind") == "picture"
            and str(beat["figure"].get("file") or "") == file and beat.get("picture") != "off"]


TELLS_SYSTEM = """A lesson shows a drawing and stops to ask the learner questions. You decide ONE thing about each piece of text
PRINTED in the drawing: if a learner can see it while a question is being asked, does it help them to the right answer?

You get the questions (q1, q2, …; with the right answer where it is known) and the printed words, each with a tag
(#3, #7, …). For EVERY question and EVERY tag answer one word:
- "tells": the words rank, compare or judge what the question asks about ("Lower", "Higher", "More", "Maximum",
  "Equal", "Wrong"), or state the answer, a value that is the answer, or the formula that gives it.
- "names": the words only name a thing or a place, as the question itself does. Naming the right option is not telling:
  the learner still has to choose it.
Answer in JSON only: {"q1": {"#4": "tells", "#9": "names"}, "q2": {"#4": "names", "#9": "names"}}"""


def asked_over(beats: list[dict], at: dict) -> list[dict]:
    """The questions a lesson stops on while this drawing is up, as code can tell them: a beat that ENDS with a question
    and stops for it (a card, or a pause). ``[{"asks", "answer", "answered_at", "heard"}]``: the right option where a
    card has one, the step at which the lesson goes on (the first line of the next beat that shows the drawing), and
    every word the voice has spoken over the drawing up to and including the question."""
    first = {}
    for number, (beat_id, _) in sorted(at.items()):
        first.setdefault(beat_id, number)
    order = [str(beat.get("id")) for beat in beats if str(beat.get("id")) in first]
    out = []
    heard: set[str] = set()                              # every word the voice has spoken over this drawing so far
    for i, beat in enumerate(beat for beat in beats if str(beat.get("id")) in first):
        text = " ".join(str(beat.get("narration") or "").split())
        heard |= set(re.findall(r"[a-zA-Z]{3,}", text.lower()))
        quiz = beat.get("quiz") if isinstance(beat.get("quiz"), dict) else {}
        if not text.endswith("?") or not (quiz or float(beat.get("thinking_pause_seconds") or 0) > 0) or i + 1 >= len(order):
            continue
        options, index = quiz.get("options") or [], quiz.get("answer_index")
        answer = str(options[index]) if isinstance(index, int) and 0 <= index < len(options) else ""
        asks = str(quiz.get("question") or re.split(r"(?<=[.!?])\s+", text)[-1])
        out.append({"asks": asks[:200], "answer": answer[:80], "answered_at": first[order[i + 1]], "heard": set(heard)})
    return out


def printed_tells(things: list[dict], questions: list[dict], tells=None, log=print) -> dict[int, int]:
    """``{thing: step}``: things whose PRINTED WORDS would tell a question's answer, and the step each must wait for.

    "F₁ (Lower)" stood beside the first of two cases while the lesson asked on which of them the reading is lower, and
    a strip of terms printed its formula under the question it answers (2026-10-12). The model that plans the drawing
    is asked about things that SHOW an answer and missed the words both times; this is one small question about the
    printed words alone, with the questions and their right answers found by code. No answer, nothing is held."""
    printed = {}
    for n, thing in enumerate(things, 1):
        words = [str(part.get("text") or "").strip() for part in ([thing["main"]] if thing["main"]["kind"] == "text" else []) + list(thing["labels"])]
        words = [w for w in words if w]
        if words:
            printed[n] = " / ".join(words)[:80]
    if not questions or not printed or tells is None:
        return {}
    prompt = "\n".join(["QUESTIONS:"] + [f"q{i}. “{q['asks']}”" + (f" (right answer: “{q['answer']}”)" if q["answer"] else "") for i, q in enumerate(questions, 1)]
                        + ["", "WORDS PRINTED IN THE DRAWING:"] + [f"#{n}: “{words}”" for n, words in printed.items()])
    try:
        answer = tells(prompt, TELLS_SYSTEM)
    except Exception as exc:  # noqa: BLE001
        log(f"[sequence] nobody to say which printed words tell an answer ({type(exc).__name__})")
        return {}
    held = {}
    for i, question in enumerate(questions, 1):
        listed = answer.get(f"q{i}") if isinstance(answer, dict) else None
        if isinstance(listed, list):                     # the other shape a model may answer in: only the tags that tell
            listed = {tag: "tells" for tag in listed}
        for tag, verdict in (listed.items() if isinstance(listed, dict) else []):
            digits = re.sub(r"\D", "", str(tag))
            if not digits or int(digits) not in printed or not str(verdict).strip().lower().startswith("tell"):
                continue
            # Words the voice has already SPOKEN before the question were taught, not given away: a recall question at
            # a lesson's end named "Proton (+)" and "nucleus" as telling, and they would have been hidden for the whole
            # lesson that is about them.
            own = {w for w in re.findall(r"[a-zA-Z]{3,}", printed[int(digits)].lower())}
            if own & question["heard"]:
                continue
            held[int(digits)] = max(held.get(int(digits), 1), int(question["answered_at"]))
    if held:
        log("[sequence] printed words that would tell an answer wait for it: "
            + "; ".join(f"“{printed[n]}” until S{step}" for n, step in sorted(held.items()))[:300])
    return held


def plan(folder, beats: list[dict], look=None, log=print, tells=None) -> dict | None:
    """``{(beat id, step index): [part numbers]}`` for one drawing and the beats that show it: which parts each step
    brings. The parts of the first step are simply there when the drawing arrives and are not listed. None when the
    drawing has no sequence, there are too many things in it, no model answers, or (almost) nothing would wait."""
    made = sequence(folder, log=lambda *a: None)
    steps = [(beat, i) for beat in beats for i, step in enumerate(beat.get("steps") or []) if str(step.get("show") or "").strip()]
    if not made or len(steps) < 2:
        return None
    if made.get("faithful") is False:
        log("[sequence] the drawing holds what a pen cannot follow (a gradient, a picture, a clip): it is drawn at once, as before")
        return None
    aspect = float(made.get("height") or 1) / max(float(made.get("width") or 1), 1.0)
    things = things_of(made["parts"], aspect)
    if not 3 <= len(things) <= MAX_THINGS:
        log(f"[sequence] {len(things)} thing(s) in the drawing: it is drawn at once, as before")
        return None
    looks = [look]
    if look is None:
        import os  # noqa: PLC0415
        from . import critic, vision_review  # noqa: PLC0415
        if tells is None and (knobs.get("HARNESS_PRINTED_TELLS") or "1").strip() != "0":
            tells = critic.default_llm()                 # the small text model: one question about the printed words
        model = (knobs.get("HARNESS_PLAN_MODEL") or PLAN_MODEL).strip()
        try:
            votes = max(1, min(5, int(knobs.get("HARNESS_PLAN_VOTES") or PLAN_VOTES)))
        except ValueError:
            votes = PLAN_VOTES
        # the first look as a judge looks (temperature 0); the others a little freer, so that they are not one answer three times
        looks = [vision_review.default_judge(models=(model,), temperature=0.0 if n == 0 else 0.3, max_tokens=3000) for n in range(votes)]   # 27 things took 1900
    if looks[0] is None:
        return None
    import base64  # noqa: PLC0415
    import io  # noqa: PLC0415
    import statistics  # noqa: PLC0415
    sheet = numbered(Path(folder) / "whole.png", things)
    sheet.thumbnail((2200, 2200))
    buffer = io.BytesIO()
    sheet.save(buffer, format="JPEG", quality=88)
    lines, at, number = ["THE THINGS IN THE PICTURE:"] + [f"  #{n}: {_described(thing)}" for n, thing in enumerate(things, 1)] + ["", "THE WORDS:"], {}, 0
    names = {re.sub(r"[^a-z0-9_]", "", re.sub(r"\s+", "_", str(part.get("text") or "").strip().lower())): str(part["text"]).strip()
             for part in made["parts"] if part["kind"] == "text" and str(part.get("text") or "").strip()}
    for beat in beats:
        lines.append(f"BEAT {beat.get('id')}. The voice: “{' '.join(str(beat.get('narration') or '').split())}”")
        for i, step in enumerate(beat.get("steps") or []):
            if not str(step.get("show") or "").strip():
                continue
            number += 1
            at[number] = (str(beat.get("id")), i)
            marked = names.get(re.sub(r"[^a-z0-9_]", "", str(step.get("focus") or "").lower()))
            lines.append(f"  S{number}, when the voice says “{str(step.get('say') or '').strip()}”: the line “{str(step.get('show')).strip()[:80]}” comes up"
                         + (f" (it marks the printed label “{marked}”)" if marked else ""))
    picture = base64.b64encode(buffer.getvalue()).decode()

    def ask(one) -> tuple | None:
        """One look's answer as ``(when, names, answers, questions)``; None when it names too few things."""
        answer = one("\n".join(lines), PLAN_SYSTEM, picture)
        listed = answer.get("things") if isinstance(answer, dict) and isinstance(answer.get("things"), dict) else answer if isinstance(answer, dict) else {}
        when, what = {}, {}
        for key, value in listed.items():
            digits = re.sub(r"\D", "", str(key))
            if not digits or not 1 <= int(digits) <= len(things):
                continue
            value = value if isinstance(value, (list, tuple)) else [value]
            step = next((re.sub(r"\D", "", str(v)) for v in reversed(value) if re.fullmatch(r"\s*S?\d+\s*", str(v))), "")
            if step and 1 <= int(step) <= number:
                when[int(digits)] = int(step)
                what[int(digits)] = str(value[0])[:40] if len(value) > 1 else ""
        if len(when) < 0.8 * len(things):
            return None
        answers, open_questions = {}, []
        for question in (answer.get("questions") if isinstance(answer, dict) and isinstance(answer.get("questions"), list) else []):
            if not isinstance(question, dict):
                continue
            asked_at, said_at = (re.sub(r"\D", "", str(question.get(k) or "")) for k in ("asked_at", "answered_at"))
            shown = [int(d) for d in (re.sub(r"\D", "", str(v)) for v in question.get("shown_by") or []) if d and 1 <= int(d) <= len(things)]
            if asked_at and said_at and shown and int(asked_at) < int(said_at) <= number:
                for n in shown:
                    answers[n] = max(answers.get(n, 1), int(said_at))
                open_questions.append(f"S{asked_at} “{str(question.get('asks') or '')[:40]}” answered at S{said_at}")
        return when, what, answers, open_questions

    given = []
    for one in looks:
        try:
            got = ask(one)
        except Exception as exc:  # noqa: BLE001 - one look less
            log(f"[sequence] a look at the drawing gave no plan ({type(exc).__name__}: {str(exc)[:100]})")
            continue
        if got:
            given.append(got)
    if not given:
        log(f"[sequence] no plan names enough of the {len(things)} thing(s): the drawing is drawn at once, as before")
        return None
    if len(given) == 1:
        when, what, answers, open_questions = given[0]
    else:
        # Several answers, one plan: a thing comes at the MEDIAN of the steps it was given; it is held back as showing
        # an answer only when most of the answers say so, until the median of the steps they name.
        when = {n: int(statistics.median_low([g[0][n] for g in given if n in g[0]])) for n in range(1, len(things) + 1)
                if any(n in g[0] for g in given)}
        what = {n: next((g[1][n] for g in given if g[1].get(n)), "") for n in when}
        answers = {n: int(statistics.median_low([g[2][n] for g in given if n in g[2]])) for n in range(1, len(things) + 1)
                   if 2 * sum(1 for g in given if n in g[2]) > len(given)}
        open_questions = max((g[3] for g in given), key=len)
        apart = sum(1 for n in when if len({g[0].get(n) for g in given}) > 1)
        log(f"[sequence] {len(given)} looks at the drawing: they agree on {len(when) - apart} of {len(when)} thing(s); the rest come at the middle answer")
    for n, step in printed_tells(things, asked_over(beats, at), tells=tells, log=log).items():
        answers[n] = max(answers.get(n, 1), step)
    asked = dict(when)
    when = settle(things, when, aspect, answers)
    if open_questions:
        log("[sequence] questions whose answer the drawing would show: " + "; ".join(open_questions)[:300])
    out, waiting = {}, 0
    for n, thing in enumerate(things, 1):
        if when[n] > 1:
            waiting += 1
            out.setdefault(at[when[n]], []).extend(thing["numbers"])
    if waiting < MIN_WAITING:
        log("[sequence] the words begin with all of the drawing: it is drawn at once, as before")
        return None
    moved = sum(1 for n in when if asked.get(n) != when[n])
    log(f"[sequence] drawn with the words: {len(things) - waiting} thing(s) when it arrives, {waiting} at {len(out)} later step(s)"
        + (f" ({moved} moved by the drawing's own rules)" if moved else "") + ": "
        + "; ".join(f"S{when[n]} {what.get(n) or '?'}" for n in sorted(when, key=lambda n: (when[n], n)) if when[n] > 1)[:520])
    return out


def with_words(lesson: dict, look=None, log=print, tells=None) -> dict:
    """Give the steps of every drawing a lesson shows whole the parts they bring (``step["draw"]``). ``{"drawings",
    "planned", "steps"}``. A lesson that already has such steps is left as it is; nothing here raises."""
    import os  # noqa: PLC0415
    summary = {"drawings": 0, "planned": 0, "steps": 0}
    if not enabled() or (knobs.get("HARNESS_DRAW_WITH_WORDS") or "1").strip() == "0":
        return summary
    if any(step.get("draw") for chapter in lesson.get("chapters") or [] for beat in chapter.get("beats") or [] for step in beat.get("steps") or []):
        return summary
    seen = set()
    for chapter in lesson.get("chapters") or []:
        for beat in chapter.get("beats") or []:
            figure = beat.get("figure") if isinstance(beat.get("figure"), dict) else {}
            file = Path(str(figure.get("file") or ""))
            if figure.get("kind") != "picture" or file.name != "whole.png" or figure.get("panels") or str(file) in seen:
                continue
            seen.add(str(file))
            summary["drawings"] += 1
            try:
                beats = _beats_on(lesson, str(file))
                made = plan(file.parent, beats, look=look, log=log, tells=tells)
            except Exception as exc:  # noqa: BLE001 - a drawing that cannot be planned is drawn at once, as before
                log(f"[sequence] the drawing is drawn at once ({type(exc).__name__}: {str(exc)[:120]})")
                continue
            if not made:
                continue
            summary["planned"] += 1
            by_id = {str(b.get("id")): b for b in beats}
            for (beat_id, index), numbers in made.items():
                by_id[beat_id]["steps"][index]["draw"] = sorted(set(numbers))
                summary["steps"] += 1
            stamp = identity(sequence(file.parent, log=lambda *a: None))
            for other in lesson.get("chapters") or []:      # every beat that shows it, so their figures stay one figure
                for shown in other.get("beats") or []:
                    if isinstance(shown.get("figure"), dict) and str(shown["figure"].get("file") or "") == str(file):
                        shown["figure"]["planned"] = stamp
    return summary


def keep_draws(lesson: dict, was: dict) -> int:
    """After something has written a beat's steps again: the parts its steps brought are brought by its steps still.

    A part that no step brings is on the board from the start, so a rewrite that dropped ``draw`` would put a part of a
    proof back in front of the words that lead to it, and only in the chapters filmed again. Each old step's parts go
    to the new step in its place (the last one when there are fewer). Returns how many steps were given parts back."""
    old = {str(beat.get("id")): beat for chapter in was.get("chapters") or [] for beat in chapter.get("beats") or []}
    given = 0
    for chapter in lesson.get("chapters") or []:
        for beat in chapter.get("beats") or []:
            before = old.get(str(beat.get("id")))
            steps = beat.get("steps") or []
            if not before or not steps or any(step.get("draw") or step.get("annotate") for step in steps):
                continue
            same = isinstance(beat.get("figure"), dict) and isinstance(before.get("figure"), dict) \
                and beat["figure"].get("file") == before["figure"].get("file")
            if not same:
                continue
            for index, step in enumerate(before.get("steps") or []):
                target = steps[min(index, len(steps) - 1)]
                if step.get("draw"):
                    target["draw"] = sorted(set(target.get("draw") or []) | set(step["draw"]))
                    given += 1
                if step.get("annotate"):                 # ... and what a hand wrote on the drawing at that step (harness/annotate.py)
                    target["annotate"] = list(target.get("annotate") or []) + list(step["annotate"])
                    given += 1
    return given
