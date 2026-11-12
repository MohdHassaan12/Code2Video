"""The Manim side of the components kit: a lesson-visuals component drawn part by part (kind ``component``).

``kits/components.py`` (pure) decides what is drawn: it validates the parameters with the component's own ``validate`` and
asks Node for ``draw``. This module only puts those SVG parts, anchors and labels on the stage:

* every part is its own ``SVGMobject`` in ``meta.parts`` order. The first part is the outline and is there from the first
  frame; a part the beat's steps name (``reveal``, set by the kit) waits, at zero opacity, until the step with that
  ``focus`` is said, and is drawn in then (the way ``figures.DiagramFigure`` waits for its layers). A part that no step
  names is there from the start, so the picture is always whole by the end of the beat;
* the SVG is in pixels with y pointing DOWN and a size of ``meta.size``: a part is loaded with
  ``should_center=False, height=None`` (otherwise Manim centres each file and rescales it to height 2, which destroys the
  shared frame). Manim still turns each FILE upside down about the middle of its own contents (measured: a child's body
  came out head down), so that is undone, and the points are placed as ``((x - w/2) k, (h/2 - y) k)``. Anchors and labels
  use the same formula;
* ``<text>`` inside a part is taken out of the SVG (Manim's SVG parser hangs on it) and written again with ``Text`` at the
  same place; labels are written with ``Text`` where ``draw`` put them (``side`` says which edge of the words is at
  ``at``: right = left edge at x + 6, left = right edge at x - 6, above and below = centred, as ``check.ts`` previews them);
* a figure made from a library situation also carries ``hold`` (parts kept out of the drawing even when no step names them:
  the set-up has not shown them yet) and ``with`` (``{part: [parts]}`` that come in together with the part when its step is
  said); both wait at zero opacity like ``reveal``;
* nothing is dimmed or ringed: a step that names a part already on screen makes it pulse once.

The component's colours are its own, made for paper (ink ``#1B2033`` on ``#F7F3EA``), and a lesson's stage can be dark
(first film, 2026-11-09: the outlines and labels vanished), so the figure stands on a paper card, as a prepared diagram does.
"""
from __future__ import annotations

import hashlib
import html
import json
import math
import os
import re

import numpy as np
from manim import (Animation, AnimationGroup, Dot, Group, RoundedRectangle, Succession, SVGMobject, Text, Transform, VGroup, linear,
                   smooth)

from .. import knobs, paths
from . import component_lib as lib
from . import figures

INK = "#1B2033"
PAPER = "#F7F3EA"                   # the paper a component is drawn for (README: ink #1B2033, paper #F7F3EA)
CARD_PAD = 0.18
LABEL_PX = 14.0                     # the size check.ts previews labels at
#: ``LESSONFORGE_COMPONENT_TIGHT`` (video-quality plan S12, default off): labels as large as these sizes allow where none of them
#: lands on another label (``tight_px``), and a thinner paper margin. Largest first.
TIGHT_SWITCH = "LESSONFORGE_COMPONENT_TIGHT"
TIGHT_PX = (18.0, 17.0, 16.0, 15.0)
TIGHT_PAD = 0.10
TIGHT_KEEP = 0.97                   # the picture may not lose more than 3% of its size to the larger writing
STROKE_PER_UNIT = 100.0             # Manim stroke_width 1 is 0.01 of a scene unit
TWEEN_SWITCH = "LESSONFORGE_COMPONENT_TWEEN"
FRAME_BOX = (7.4, 4.4)              # scene units the component is sized to (runtime.GuidedChapter.PICTURE_BOX is 7.4 x 4.6)
_TEXT = re.compile(r"<text\b([^>]*)>(.*?)</text\s*>", re.S | re.I)
_ATTR = re.compile(r"([a-zA-Z_:-]+)\s*=\s*\"([^\"]*)\"|([a-zA-Z_:-]+)\s*=\s*'([^']*)'")
_CAP = {}                           # font size -> height of a capital H in scene units, measured once


def _cap_height() -> float:
    if "h" not in _CAP:
        _CAP["h"] = float(Text("H", font=figures.FONT, font_size=48).height)
    return _CAP["h"]


def words(text: str, px: float, k: float, colour: str = INK) -> Text:
    """``text`` as Manim Text whose capital letters are 0.72 em tall for a font of ``px`` svg pixels (``k`` units per pixel)."""
    mob = Text(text, font=figures.FONT, font_size=48, color=colour)
    mob.scale(0.72 * px * k / _cap_height())
    return mob


def place_labels(drawn: dict, px: float, k: float) -> list[tuple[dict, Text]]:
    """Each label of ``drawn`` as Text of ``px`` svg pixels, put where ``draw`` said (``side``: right = left edge at x + 6, left =
    right edge at x - 6, above and below = centred), in the drawing's own units before the stage scales it."""
    w, h = drawn["size"]
    out = []
    for lab in drawn["labels"]:
        mob = words(lab["text"], px, k)
        x, y = lab["at"]
        gap = 6 * k
        centre = np.array([(x - w / 2) * k, (h / 2 - y) * k, 0.0])
        if lab["side"] == "right":
            mob.move_to(centre + np.array([gap + mob.width / 2, 0, 0]))
        elif lab["side"] == "left":
            mob.move_to(centre - np.array([gap + mob.width / 2, 0, 0]))
        else:
            mob.move_to(centre)
        out.append((lab, mob))
    return out


def label_collisions(drawn: dict, px: float, k: float | None = None, box: tuple[float, float] = FRAME_BOX) -> int:
    """How many pairs of labels sit on each other at ``px``: by ``check.ts``'s own boxes (8 px a letter, scaled with the size)
    and by the words as Manim sets them. ``check.ts`` previews at 14 px; this is the same check at another size."""
    w, h = drawn["size"]
    k = min(box[0] / w, box[1] / h) if k is None else k
    labels = place_labels(drawn, px, k)
    scale = px / LABEL_PX
    hits = 0
    for a in range(len(labels)):
        for b in range(a + 1, len(labels)):
            (la, ma), (lb, mb) = labels[a], labels[b]
            if _boxes_meet(_check_box(la, scale), _check_box(lb, scale)) or _boxes_meet(_text_box(ma), _text_box(mb)):
                hits += 1
    return hits


def _check_box(lab: dict, scale: float) -> tuple[float, float, float, float]:
    width = len(str(lab["text"])) * 8 * scale
    x, y = lab["at"]
    x0 = x + 6 if lab["side"] == "right" else x - 6 - width if lab["side"] == "left" else x - width / 2
    return (x0, y - 7 * scale, x0 + width, y + 8 * scale)


def _text_box(mob) -> tuple[float, float, float, float]:
    return (float(mob.get_left()[0]), float(mob.get_bottom()[1]), float(mob.get_right()[0]), float(mob.get_top()[1]))


def _boxes_meet(a, b) -> bool:
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def _fit(extent: tuple[float, float, float, float], pad: float) -> float:
    """How much a card round ``extent`` can be enlarged in the room the stage gives a picture (the larger of its two boxes)."""
    from . import look  # noqa: PLC0415 - no Manim in it
    width, height = extent[1] - extent[0] + 2 * pad, extent[3] - extent[2] + 2 * pad
    return max(min(bw / width, bh / height) for bw, bh in look.picture_boxes(look.for_new()))


def tight_px(drawings: list[dict], box: tuple[float, float] = FRAME_BOX) -> float:
    """The label size a run of drawings is set at under ``LESSONFORGE_COMPONENT_TIGHT``: the largest of ``TIGHT_PX`` at which NO
    drawing has more pairs of labels on each other than it has at ``LABEL_PX`` AND the drawing, put on the thinner card, is
    still at least ``TIGHT_KEEP`` of the size it was on the old card (larger writing that widens the card shrinks the picture:
    measured on the 28 library components, a few lose 8 to 9%); ``LABEL_PX`` when none qualifies. One size for the whole run,
    so a label does not change size between the states of one card."""
    base = [label_collisions(d, LABEL_PX, box=box) for d in drawings]
    was = [_fit(extent_of(d, box, LABEL_PX), CARD_PAD) for d in drawings]
    for px in TIGHT_PX:
        if not all(label_collisions(d, px, box=box) <= n for d, n in zip(drawings, base)):
            continue
        if all(_fit(extent_of(d, box, px), TIGHT_PAD) >= TIGHT_KEEP * w for d, w in zip(drawings, was)):
            return px
    return LABEL_PX


def _attrs(blob: str) -> dict[str, str]:
    return {(m.group(1) or m.group(3)): (m.group(2) if m.group(1) else m.group(4)) for m in _ATTR.finditer(blob)}


def split_text(svg: str) -> tuple[str, list[dict]]:
    """(``svg`` without its <text> elements, the texts as ``{text, x, y, px, anchor, fill}``)."""
    found = []
    for m in _TEXT.finditer(svg):
        a = _attrs(m.group(1))
        content = html.unescape(re.sub(r"<[^>]+>", " ", m.group(2)))
        content = re.sub(r"\s+", " ", content).strip()
        if not content:
            continue
        try:
            x, y = float(a.get("x", 0)), float(a.get("y", 0))
            px = float(re.sub(r"[^0-9.]", "", a.get("font-size", "")) or 12)
        except ValueError:
            continue
        found.append({"text": content, "x": x, "y": y, "px": px, "anchor": a.get("text-anchor", "start"),
                      "fill": a.get("fill") if re.fullmatch(r"#[0-9a-fA-F]{3,8}", a.get("fill") or "") else INK})
    return _TEXT.sub("", svg), found


def _svg_file(fragment: str, w: float, h: float):
    """A one-part SVG file under the workspace cache (``SVGMobject`` takes only a path)."""
    body = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w:g} {h:g}" width="{w:g}" height="{h:g}">{fragment}</svg>'
    folder = paths.cache("components", "svg")
    target = folder / (hashlib.sha256(body.encode()).hexdigest()[:20] + ".svg")
    if not target.exists():
        tmp = target.with_suffix(f".{os.getpid()}.tmp")
        tmp.write_text(body, encoding="utf-8")
        tmp.replace(target)
    return target


class _Reveal(Animation):
    """A part comes in by its opacities, each back to what it was drawn with (``set_opacity(1)`` would flatten fills)."""

    def __init__(self, group, saved, **kwargs):
        self._saved = saved
        super().__init__(group, **kwargs)

    def interpolate_mobject(self, alpha: float) -> None:
        for mob, stroke, fill in self._saved:
            mob.set_stroke(opacity=stroke * alpha)
            mob.set_fill(opacity=fill * alpha)

    def clean_up_from_scene(self, scene) -> None:
        self.interpolate_mobject(1.0)
        super().clean_up_from_scene(scene)


class _Pulse(Animation):
    """A part already on screen grows a little and settles back: the step is about it, and nothing is recoloured."""

    def __init__(self, group, **kwargs):
        super().__init__(group, run_time=kwargs.pop("run_time", 0.7), **kwargs)

    def interpolate_mobject(self, alpha: float) -> None:
        self.mobject.become(self.starting_mobject)
        self.mobject.scale(1 + 0.07 * math.sin(math.pi * alpha), about_point=self.starting_mobject.get_center())


#: Words that change while a picture is morphed go out in the first 30% of the run and the new ones come in in the last 30%
#: (plan S13): faded over the whole run, two different numbers stood printed over each other, half strength each, at its middle
#: ("time 1.8 s" over "time 3.6 s", "at the end: speed zero" over "swinging"). Only reached through ``change_from`` (the control).
WORDS_OUT, WORDS_IN = (0.0, 0.3), (0.7, 1.0)


class _Opacity(Animation):
    """Everything in ``group`` goes from nothing to what it was (``into``) or from what it is to nothing, by opacity alone:
    a word never morphs, it cross-fades (a '20' turned into a smear when it was tried as a glyph morph)."""

    def __init__(self, group, into: bool, window: tuple[float, float] = (0.0, 1.0), **kwargs):
        self._into = into
        self._window = window
        self._saved = [(m, float(m.get_stroke_opacity()), float(m.get_fill_opacity())) for m in group.family_members_with_points()]
        super().__init__(group, rate_func=linear, **kwargs)
        if into:
            self._set(0.0)

    def _set(self, factor: float) -> None:
        for mob, stroke, fill in self._saved:
            mob.set_stroke(opacity=stroke * factor)
            mob.set_fill(opacity=fill * factor)

    def begin(self) -> None:
        self._set(0.0 if self._into else 1.0)
        super().begin()

    def interpolate_mobject(self, alpha: float) -> None:
        a, b = self._window                  # the share of the run the fade takes (all of it unless a window is given)
        x = min(1.0, max(0.0, (alpha - a) / max(b - a, 1e-9)))
        self._set(x if self._into else 1.0 - x)


class ComponentFigure(figures.Figure):
    """A component drawn part by part. ``parts[name]`` is the part's drawing together with its labels.

    ``art[name]`` is the SVG alone (for measuring), ``anchors[name]`` an invisible dot at the anchor, ``labels`` the label
    Text mobjects and ``card`` (also ``frame``) the paper under everything, so the figure's box never changes when a part
    appears.
    """

    def __init__(self, drawn: dict, reveal: list[str] | None = None, box: tuple[float, float] = FRAME_BOX,
                 hold: list[str] | None = None, together: dict[str, list[str]] | None = None,
                 span_box: tuple[float, float, float, float] | None = None, label_px: float = LABEL_PX, pad: float = CARD_PAD):
        super().__init__("component")
        self.label_px, self.pad = label_px, pad
        w, h = drawn["size"]
        k = min(box[0] / w, box[1] / h)
        self.component, self.size, self.k = drawn["id"], (w, h), k
        self.manifest_id = drawn["id"]
        flip = lambda x, y: np.array([(x - w / 2) * k, (h / 2 - y) * k, 0.0])      # noqa: E731 - the one formula
        self.art: dict[str, VGroup] = {}
        self.svg: dict[str, SVGMobject | None] = {}      # the SVG alone of each part (None when it draws nothing)
        self.sig: dict[str, dict] = {}                   # what ``change_from`` compares: shapes, words and labels of each part
        self.labels: list[Text] = []
        self.anchors: dict[str, Dot] = {}
        self._saved: dict[str, list] = {}
        order = [name for name, _ in drawn["parts"]]
        for name, fragment in drawn["parts"]:
            svg, texts = split_text(fragment)
            art = VGroup()
            self.svg[name] = None
            self.sig[name] = {"svg": lib.svg_numbers(svg) if svg.strip() else ("", []),
                              "text": tuple((t["text"], t["x"], t["y"], t["px"], t["anchor"], t["fill"]) for t in texts),
                              "labels": tuple((lab["text"], tuple(lab["at"]), lab["side"]) for lab in drawn["labels"] if lab["part"] == name)}
            if svg.strip():
                mob = SVGMobject(str(_svg_file(svg, w, h)), should_center=False, height=None)
                # Manim turns each FILE upside down about the middle of its own contents, whatever should_center says (a part
                # that is symmetric keeps its numbers, which hides it). Undo that: y_svg = (ymin + ymax) - y_loaded.
                every = mob.get_all_points()
                flipped = float(every[:, 1].min() + every[:, 1].max())
                for sm in mob.family_members_with_points():
                    pts = np.array(sm.points)
                    pts[:, 0] = (pts[:, 0] - w / 2) * k
                    pts[:, 1] = (h / 2 - (flipped - pts[:, 1])) * k
                    sm.set_points(pts)
                    sm.set_stroke(width=float(sm.get_stroke_width()) * k * STROKE_PER_UNIT)
                art.add(mob)
                self.svg[name] = mob
            for t in texts:                                                  # words inside a part: Text, not the SVG parser
                mob = words(t["text"], t["px"], k, t["fill"])
                at = flip(t["x"], t["y"] - t["px"] * 0.3)
                if t["anchor"] == "middle":
                    mob.move_to(at)
                else:
                    mob.move_to(at + (1 if t["anchor"] != "end" else -1) * np.array([mob.width / 2, 0, 0]))
                art.add(mob)
            self.art[name] = art
        part_labels: dict[str, list[Text]] = {name: [] for name in order}
        for lab, mob in place_labels(drawn, label_px, k):
            part_labels[lab["part"]].append(mob)
            self.labels.append(mob)
        for name, at in drawn["anchors"].items():
            self.anchors[name] = Dot(flip(*at), radius=0.001, fill_opacity=0, stroke_width=0)
        self.parts = {}
        for name in order:
            self.parts[name] = VGroup(self.art[name], *part_labels[name])
        # The card: paper under the whole drawing and its labels, so a part that comes later never changes the figure's box.
        content = Group(*[g for g in self.art.values() if len(g.submobjects)], *self.labels)
        left, right, bottom, top = (float(content.get_left()[0]), float(content.get_right()[0]),
                                    float(content.get_bottom()[1]), float(content.get_top()[1]))
        # What this drawing takes up with its anchors, kept for the stable frame (``span_frame``): the anchors are invisible
        # but belong to the figure's box, so a card must hold them too when several states share one.
        spots = [d.get_center() for d in self.anchors.values()]
        self.extent = (min([left] + [float(q[0]) for q in spots]), max([right] + [float(q[0]) for q in spots]),
                       min([bottom] + [float(q[1]) for q in spots]), max([top] + [float(q[1]) for q in spots]))
        if span_box is not None:           # one frame for a run of states: every state's card is the same rectangle
            left, right, bottom, top = (min(span_box[0], self.extent[0]), max(span_box[1], self.extent[1]),
                                        min(span_box[2], self.extent[2]), max(span_box[3], self.extent[3]))
        self.span_box = span_box
        self.card = RoundedRectangle(width=right - left + 2 * pad, height=top - bottom + 2 * pad, corner_radius=0.12,
                                     stroke_width=0, fill_color=PAPER, fill_opacity=1).move_to([(left + right) / 2, (bottom + top) / 2, 0])
        self.frame = self.card
        # Where the drawing stood before the stage scaled and moved it, and how thick its first line was: ``change_from``
        # draws stations in between in the same frame and puts them where this figure now is (``_placed``).
        self.native = {"centre": np.array(self.card.get_center(), dtype=float), "width": float(self.card.width),
                       "stroke_of": next((m for g in self.art.values() for m in g.family_members_with_points()
                                          if float(m.get_stroke_width()) > 0), None)}
        self.native["stroke"] = float(self.native["stroke_of"].get_stroke_width()) if self.native["stroke_of"] is not None else 0.0
        self.add(self.card, *self.parts.values(), *self.anchors.values())
        # ``together``: parts that come in with another part's step; they wait, hidden, like ``reveal``. ``hold``: parts a
        # set-up has not shown yet, hidden whether or not a step names them.
        self.together = {k: [x for x in v if x in self.parts and x != order[0]] for k, v in (together or {}).items() if k in self.parts}
        waiting = list(reveal or []) + list(hold or []) + [x for v in self.together.values() for x in v]
        hidden = [name for name in dict.fromkeys(waiting) if name in self.parts and name != order[0]]
        for name in hidden:
            self._saved[name] = [(m, float(m.get_stroke_opacity()), float(m.get_fill_opacity()))
                                 for m in self.parts[name].family_members_with_points()]
            for m, _, _ in self._saved[name]:
                m.set_stroke(opacity=0)
                m.set_fill(opacity=0)
        self.hidden = list(hidden)
        self.shown: set[str] = set(order) - set(hidden)
        # What construct_animation draws in the lead-in: the parts that are there from the start, in the order of the voice.
        self.build = [("fade", [self.card] + [self.parts[n] for n in order if n in self.shown])]

    # ── the same component with a number that moved (video-quality plan S7) ──────────────────────────────────────────────

    def change_from(self, old) -> list:
        """The next beat's drawing grows out of this one: ``[animation]`` for ``GuidedChapter`` to play in the lead-in, or ``[]``
        and the old fade-out and redraw happen as before.

        Only when the control ``LESSONFORGE_COMPONENT_TWEEN`` is on, ``old`` is a ``ComponentFigure`` of the same component, both
        carry the same ``span`` (one card, one place on the stage: ``kits/components.py``) and the only change between them is a
        listed number knob (``component_lib.TWEEN_KNOBS``): a rotation, a periodic knob, a preset, an integer, a part that
        appears and anything else is not morphed. The library MEASURES the change (``component_lib.morph_plan``): where
        the straight morph of the art is within a pixel of the truth, that is the morph; where it is not (a bob swinging, a
        cell across zero), the art goes through the stations the plan lists, the component drawn at values in between
        (plan step S8). What moves: the SVG art of each part that has the same shapes at every station (``Transform`` of
        the art alone; the part group is never tweened, and each file's Manim flip was already undone per part, so the flip
        holds); parts whose shapes differ, words in a part and the labels cross-fade; a part the new drawing keeps back
        fades out; the invisible anchors are ignored.
        """
        if str(knobs.get(TWEEN_SWITCH, "0")).strip() != "1":
            return []
        try:
            return self._change(old)
        except Exception as exc:  # noqa: BLE001 - the old fade and redraw is always there to fall back on
            print(f"LESSON_NOTE: the component was not morphed ({type(exc).__name__}: {str(exc)[:120]})", flush=True)
            return []

    def _change(self, old) -> list:
        if not isinstance(old, ComponentFigure) or old is self or not (old.span and old.span == self.span):
            return []
        if old.drawing["id"] != self.drawing["id"] or not self.span:
            return []
        mine, theirs = np.array([self.card.width, self.card.height, *self.card.get_center()[:2]]), \
            np.array([old.card.width, old.card.height, *old.card.get_center()[:2]])
        if float(np.abs(mine - theirs).max()) > 1e-4:               # not placed alike: a morph would slide the whole card
            return []
        plan = lib.morph_plan(self.drawing["id"], {"params": old.drawing["params"], "state": old.drawing["state"]},
                              {"params": self.drawing["params"], "state": self.drawing["state"]})
        if plan is None:
            return []
        stations = []                          # a knob that moves along a curve: the drawings it passes through, placed like this one
        for st in plan["stations"]:
            station = ComponentFigure(lib.draw(self.drawing["id"], st["params"], st["state"]), label_px=self.label_px)
            stations.append((float(st["t"]), self._placed(station)))
        moves = self._moves(old, plan, stations)
        return [AnimationGroup(*moves, rate_func=smooth)] if moves else []

    def _placed(self, other):
        """``other`` (a figure built in the same frame, never placed) put where the stage put this one: scaled about the card's
        native centre by the factor the card was scaled by, moved to where the card now is, lines as much thicker as this
        figure's lines became (the stage scales strokes with the picture). The drawings share ``k`` and the flip formula, so the
        same point of the drawing lands in the same place whatever the knob."""
        by = float(self.card.width) / self.native["width"]
        here = np.array(self.card.get_center(), dtype=float)
        other.scale(by, about_point=self.native["centre"])
        other.shift(here - self.native["centre"])
        ref = self.native["stroke_of"]
        ratio = float(ref.get_stroke_width()) / self.native["stroke"] if ref is not None and self.native["stroke"] else 1.0
        if abs(ratio - 1.0) > 1e-6:
            for member in other.get_family():
                if len(member.points) and float(member.get_stroke_width()) > 0:
                    member.set_stroke(width=float(member.get_stroke_width()) * ratio, family=False)
        return other

    def _moves(self, old, plan: dict, stations: list | None = None) -> list:
        """The animations that turn ``old`` (on the stage) into this drawing, all on ``old``'s own mobjects, so nothing is
        added to or removed from the scene and the runtime then swaps the whole figure in as it does for any change."""
        out: list = []
        for name in self.parts:
            was_here, is_here = name in old.shown, name in self.shown
            before, after = old.parts[name], self.parts[name]
            if not is_here:                                           # kept back in the new drawing: it leaves
                if was_here and len(before.family_members_with_points()):
                    out.append(_Opacity(before, into=False))
                continue
            if not was_here:                                          # kept back before: the new part comes in
                if len(after.family_members_with_points()):
                    coming = after.copy()
                    old.parts[name].add(coming)
                    out.append(_Opacity(coming, into=True))
                continue
            a, b = old.sig[name], self.sig[name]
            mob_old, mob_new = old.svg.get(name), self.svg.get(name)
            passes = [st.svg.get(name) for _, st in stations or [] if st.sig[name]["svg"] != a["svg"]]
            if a["svg"] != b["svg"] or (passes and name in plan["stable"]):      # (a closed curve: the ends are the same, the way is not)
                if mob_old is not None and mob_new is not None and name in plan["stable"]:
                    out.append(self._along(mob_old, mob_new, stations, name))
                else:                                                  # a shape appears, goes or changes: cross-fade
                    if mob_old is not None:
                        out.append(_Opacity(mob_old, into=False))
                    if mob_new is not None:
                        out.append(self._brought(old.art[name], mob_new))
            if a["text"] != b["text"]:
                out += self._swap(old.art[name], [m for m in old.art[name].submobjects if isinstance(m, Text)],
                                  [m for m in self.art[name].submobjects if isinstance(m, Text)])
            if a["labels"] != b["labels"]:
                out += self._swap(old.parts[name], list(old.parts[name].submobjects[1:]), list(self.parts[name].submobjects[1:]))
        return out

    @staticmethod
    def _along(mob_old, mob_new, stations: list | None, name: str):
        """The part's art on the stage becomes the new art: straight when the library measured that to be right, else through
        the drawings the knob passes through, each leg as long (in the knob) as the knob's own step, at a steady pace."""
        if not stations:
            return Transform(mob_old, mob_new, rate_func=linear)
        way = [(t, st.svg[name]) for t, st in stations] + [(1.0, mob_new)]
        legs, last = [], 0.0
        for t, target in way:
            legs.append(Transform(mob_old, target, rate_func=linear, run_time=t - last))
            last = t
        return Succession(*legs, rate_func=linear)

    @staticmethod
    def _brought(into, mob):
        """A copy of ``mob`` (already placed) put into ``into`` at no opacity, with the animation that brings it in."""
        coming = mob.copy()
        into.add(coming)
        return _Opacity(coming, into=True, window=WORDS_IN if isinstance(mob, Text) else (0.0, 1.0))

    def _swap(self, into, going: list, coming: list) -> list:
        out = [_Opacity(m, into=False, window=WORDS_OUT if isinstance(m, Text) else (0.0, 1.0)) for m in going if len(m.family_members_with_points())]
        out += [self._brought(into, m) for m in coming if len(m.family_members_with_points())]
        return out

    def anchor(self, name: str):
        """Where an anchor is now on the stage (the figure is moved and scaled after it is built)."""
        return self.anchors[name].get_center()

    def _part(self, name) -> str | None:
        """The part a focus names, however it was spelt (the writer keeps ``a-z0-9_`` only, lower case)."""
        flat = lambda text: re.sub(r"[^a-z0-9]", "", str(text).lower())      # noqa: E731
        return next((p for p in self.parts if p == name or flat(p) == flat(name)), None)

    def _release(self, key: str) -> list[str]:
        """The hidden parts a focus on ``key`` brings in: the part itself and the parts that come in with it."""
        return [k for k in [key, *self.together.get(key, [])] if k in self._saved and k not in self.shown]

    def resume(self, names) -> None:
        """Stand as after these focuses, with nothing animated: the parts earlier beats and chapters drew in are there."""
        for name in names or []:
            key = self._part(name)
            for k in self._release(key) if key else []:
                for m, stroke, fill in self._saved[k]:
                    m.set_stroke(opacity=stroke)
                    m.set_fill(opacity=fill)
                self.shown.add(k)

    def focus_animations(self, name: str) -> list:
        """What happens on screen when a step is about ``name``: a waiting part (and the parts that come in with it) is drawn
        in, a visible one pulses."""
        key = self._part(name)
        if key is None:
            return []
        coming = self._release(key)
        if coming:
            self.shown.update(coming)
            return [_Reveal(VGroup(*[self.parts[k] for k in coming]), [row for k in coming for row in self._saved[k]], run_time=0.6)]
        return [_Pulse(self.parts[key])] if len(self.parts[key].family_members_with_points()) else []


_EXTENTS: dict[str, tuple[float, float, float, float]] = {}      # drawing digest -> (left, right, bottom, top) with anchors


def _digest(drawn: dict, box: tuple[float, float], px: float = LABEL_PX) -> str:
    blob = json.dumps([drawn["id"], drawn["size"], drawn["parts"], drawn["labels"], drawn["anchors"], list(box), px],
                      sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode()).hexdigest()


def extent_of(drawn: dict, box: tuple[float, float] = FRAME_BOX, px: float = LABEL_PX) -> tuple[float, float, float, float]:
    """The room one drawing takes in scene units before it is placed (content and anchors), measured once per process."""
    key = _digest(drawn, box, px)
    if key not in _EXTENTS:
        _EXTENTS[key] = ComponentFigure(drawn, box=box, label_px=px).extent
    return _EXTENTS[key]


def span_frame(cid: str, span: list[dict], own: tuple[dict | None, dict | None] = (None, None),
               px: float = LABEL_PX) -> tuple[float, float, float, float] | None:
    """The one rectangle that holds every drawing of a run of beats (video-quality plan S6): the union of the content and
    anchor boxes of each ``{params, state}`` in ``span``. All the drawings are asked for in ONE ``prefetch`` (one Node
    process). ``None`` when any of them cannot be drawn: the figure then has its own card, as it always had."""
    specs = [(cid, e.get("params"), e.get("state")) for e in span] + [(cid, *own)]
    lib.prefetch(specs)
    try:
        boxes = [extent_of(lib.draw(*spec), px=px) for spec in specs]
    except ValueError:                          # ComponentError and KitError are ValueErrors
        return None
    return (min(b[0] for b in boxes), max(b[1] for b in boxes), min(b[2] for b in boxes), max(b[3] for b in boxes))


def component(p: dict) -> ComponentFigure:
    """The builder ``figures.build`` reaches for a ``component`` figure (through ``kits.builder_for``).

    ``p`` is what ``build`` passes: the figure's ``params`` (``{id, params, state, reveal}``), or a whole flat figure.
    Raises ``ComponentError`` / ``KitError`` (both ``ValueError``) for a component that cannot be drawn, so ``build``
    says so and the previous picture stays.
    """
    from ..kits import components as kit  # noqa: PLC0415 - the pure kit module; the builder is reached only through it
    spec = p if "kind" in p else {"kind": "component", "params": p}
    cid, params, state, reveal = kit.parse_figure(spec)
    extras = kit.figure_extras(spec)
    entry = lib.get(cid, in_scope=True)
    span = extras.get("span")
    px, pad = LABEL_PX, CARD_PAD
    if str(knobs.get(TIGHT_SWITCH, "0")).strip() == "1":
        # video-quality plan S12: bigger labels where they do not land on each other, one size for the whole run, and less paper
        try:
            specs = [(entry["id"], e.get("params"), e.get("state")) for e in span or []] + [(entry["id"], params, state)]
            lib.prefetch(specs)
            px, pad = tight_px([lib.draw(*spec) for spec in specs]), TIGHT_PAD
        except ValueError:
            px, pad = LABEL_PX, CARD_PAD
    frame = span_frame(entry["id"], span, (params, state), px) if span else None
    fig = ComponentFigure(lib.draw(entry["id"], params, state), reveal, hold=extras.get("hold"), together=extras.get("with"),
                          span_box=frame, label_px=px, pad=pad)
    fig.span = span if frame is not None else None            # what the runtime and ``change_from`` compare
    fig.drawing = {"id": entry["id"], "params": lib.merged_params(entry, params), "state": lib.filled_state(entry, state or {})}
    return fig
