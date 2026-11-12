"""A hand-made look for a drawing's scene WITHOUT a model: nothing is generated, so nothing can vanish or appear.

The owner, 2026-10-10: "make the skeleton using svg api then use diffusion based approaches to style it". Repainting a
scene with the image model was built with a gate (``harness/repaint.py``) and stays off: at the strength where the
look changes it loses small things (a water drop of three, a river's blue), with an edge hint it either changes
nothing or turns the sea green, and the gate passed two such losses (docs/research/approaches/11 §7). The owner's
go-ahead of 2026-10-12 is for this instead: a flat drawing is already the "abstraction" of a painting, so only the
EFFECTS of paint on paper are added to its scene, by arithmetic:

* every edge wobbles a little, as a line drawn by hand does (at most about two pixels, slowly varying: a thing stays
  where it is to within the width of its own outline);
* pigment pools along edges: a darker rim where two colours meet;
* washes are never even: slow blotches, and grain that shows more where the colour is deep;
* paper: a fine tooth and the faintest warmth.

Only for a drawing that has a SCENE layer of its own (the service's posters: the water cycle, a plant in the sun):
its arrows and labels are laid back on top unchanged, exactly as ``repaint`` does. A drawing in one piece (an anatomy
drawing, a typeset figure with its print inside it) is left as drawn: its fine print is the lesson.

The look is made once per drawing and kept beside it (``<drawing>/paper/``, a manifest of its own); a lesson's beats
are pointed at that copy (``apply``). The same scene always gets the same grain. No model, no GPU, no money, a few
seconds a drawing, once. ``HARNESS_DRAWING_LOOK=0`` leaves every drawing as drawn.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path

from .. import knobs
from . import repaint

#: Raised when the filter changes: a look made by another version is made again.
VERSION = "paper-2"


def enabled() -> bool:
    return (knobs.get("HARNESS_DRAWING_LOOK") or "paper").strip().lower() not in ("0", "off", "plain", "as-drawn")


def paper(scene, seed: int = 3):
    """``scene`` (a PIL image) with the look of paint on paper. Same size; every thing where it was."""
    import numpy as np  # noqa: PLC0415
    from PIL import Image  # noqa: PLC0415
    from scipy import ndimage  # noqa: PLC0415
    rng = np.random.default_rng(seed)
    a = np.asarray(repaint._on_white(scene)).astype(np.float32) / 255.0
    h, w = a.shape[:2]
    unit = max(w, h) / 1280.0                              # the strengths were chosen on drawings 1280 pixels wide

    def field(sigma, strength=1.0):
        noise = ndimage.gaussian_filter(rng.standard_normal((h, w)).astype(np.float32), sigma * unit)
        return strength * noise / (float(np.abs(noise).max()) + 1e-6)

    # 1. every edge wobbles a little
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    dx, dy = field(22, 2.4 * unit), field(22, 2.4 * unit)
    a = np.clip(np.stack([ndimage.map_coordinates(a[..., c], [yy + dy, xx + dx], order=3, mode="nearest") for c in range(3)], axis=-1), 0, 1)
    # 2. pigment pools along edges: on the DARKER side of an edge only (a thin light line on a dark ground, the roots in
    #    the soil, three small drops, would otherwise be darkened into its ground), and not along the picture's own border
    grey = a.mean(axis=2)
    edge = ndimage.gaussian_gradient_magnitude(grey, 1.2 * unit, mode="nearest")
    rim = np.clip(ndimage.gaussian_filter(edge, 1.6 * unit) * 9.0, 0, 1)
    rim *= 1 - np.clip((grey - ndimage.gaussian_filter(grey, 4 * unit)) * 14.0, 0, 1)
    margin = max(2, round(4 * unit))
    rim[:margin, :] = rim[-margin:, :] = 0
    rim[:, :margin] = rim[:, -margin:] = 0
    a *= (1 - 0.22 * rim)[..., None]
    # 3. washes are never even
    depth = 1 - a.min(axis=2)
    a *= (1 + 0.06 * field(46))[..., None]
    a *= (1 + 0.05 * field(1.3) * (0.35 + depth))[..., None]
    # 4. paper
    a *= (1 + 0.018 * field(0.6))[..., None]
    a = a * 0.965 + np.array([0.98, 0.955, 0.90], np.float32) * 0.035
    return Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8), "RGB")


def looked(manifest_path, log=print) -> str | None:
    """The manifest of a drawing's copy with the paper look (made now, or kept from before); None when it stays as drawn."""
    try:
        manifest_path = Path(str(manifest_path))
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        folder = Path(manifest.get("folder") or manifest_path.parent)
        if manifest.get("paper") or manifest.get("styled"):
            return None                                    # already a copy with a look of its own: used as it is
        if not manifest.get("base") or not (folder / str(manifest["base"])).is_file():
            return None                                    # a drawing in one piece: its print is inside it
        source = repaint._source_of(manifest, folder)
        kept = folder / "paper" / "manifest.json"
        try:
            done = json.loads(kept.read_text(encoding="utf-8"))
            if (done.get("paper") or {}).get("of") == source and (done.get("paper") or {}).get("version") == VERSION \
                    and (folder / "paper" / str(done["base"])).is_file():
                return str(kept)
        except (OSError, ValueError, KeyError, TypeError):
            pass
        from PIL import Image  # noqa: PLC0415
        began = time.time()
        seed = int(hashlib.sha256(source.encode("utf-8")).hexdigest()[:8], 16)
        scene = paper(Image.open(folder / str(manifest["base"])), seed)
        made = repaint._write(folder, manifest, scene, {"of": source, "version": VERSION, "seed": seed,
                                                        "when": time.strftime("%Y-%m-%d %H:%M")}, name="paper")
        log(f"[look] the drawing's scene was given the look of paint on paper in {time.time() - began:.1f} s; "
            f"its {len(manifest.get('parts') or [])} arrow layers and its labels are the drawing's own")
        return made
    except Exception as exc:  # noqa: BLE001 - a better look is an improvement, never a requirement
        log(f"[look] the drawing is left as drawn ({type(exc).__name__}: {str(exc)[:140]})")
        return None


def apply(lesson: dict, log=print) -> dict:
    """Point every beat that shows a poster at the poster's copy with the paper look. ``{"asked", "given"}``."""
    summary = {"asked": 0, "given": 0}
    if not enabled():
        return summary
    swap = {}
    for path in repaint.candidates(lesson):
        summary["asked"] += 1
        made = looked(path, log=log)
        if made:
            swap[path] = made
    for chapter in lesson.get("chapters") or []:
        for beat in chapter.get("beats") or []:
            figure = beat.get("figure") if isinstance(beat.get("figure"), dict) else None
            if figure and figure.get("kind") == "diagram" and str(figure.get("manifest")) in swap:
                figure["manifest"] = swap[str(figure["manifest"])]
    summary["given"] = len(swap)
    return summary
