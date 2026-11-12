"""One short moving picture for another app's video (Image Teacher's "motion" scenes).

Image Teacher keeps the story, the voice and the board. When a scene needs something to MOVE (a bottle rising, a
ray bending, a square splitting into pieces), it asks for one clip here:

    {"brief": "a closed bottle pushed under water, then let go; it rises and floats",
     "parts": ["bottle", "water", "weight arrow", "upthrust arrow"],
     "cues": [{"at": 0.0, "do": "the bottle sits under the water line"},
              {"at": 4.2, "do": "a downward weight arrow appears on the bottle"},
              {"at": 9.8, "do": "the bottle rises until part of it is above the water"}],
     "seconds": 18, "width": 1056, "height": 500}

and gets back an MP4 of exactly ``seconds``, where cue k's change plays when its sentence starts and then rests
(``longform.runtime.stage_progress``, the same rule lessons use), so each movement lands on the words that say it.

Manim only draws and moves here: no narration, no titles, no text beyond short labels. The drawing is written by
``engine.sim_gen`` (one ``build``/``animate`` pair, stepped and checked with no renderer: inside its box, something
moves, labels don't sit on each other, every part is seen) and cached by its description, so asking twice costs
nothing. When no checked drawing can be made, ``make_clip`` says why and the caller falls back to a still picture.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

SCHEMA = "motion-clip/1"
MAX_SECONDS = 60.0
MAX_CUES = 8


class ClipError(ValueError):
    """The request cannot be made into a clip (bad input, or no checked drawing)."""


def _clean(text, n: int = 300) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()[:n]


def check_request(req: dict) -> dict:
    """The request with defaults filled in, or ClipError saying what is wrong."""
    if not isinstance(req, dict):
        raise ClipError("send a JSON object")
    brief = _clean(req.get("brief"), 600)
    if len(brief) < 8:
        raise ClipError("brief: say what moves, in a sentence")
    cues = []
    for c in (req.get("cues") or [])[:MAX_CUES]:
        if not isinstance(c, dict):
            continue
        do = _clean(c.get("do") or c.get("say"), 200)
        try:
            at = float(c.get("at", 0))
        except (TypeError, ValueError):
            raise ClipError("cues: every 'at' is a number of seconds")
        if do:
            cues.append({"at": max(0.0, at), "do": do})
    cues.sort(key=lambda c: c["at"])
    try:
        seconds = float(req.get("seconds") or (cues[-1]["at"] + 4 if cues else 8))
    except (TypeError, ValueError):
        raise ClipError("seconds: a number")
    if not 2 <= seconds <= MAX_SECONDS:
        raise ClipError(f"seconds: between 2 and {MAX_SECONDS:.0f}")
    if cues and cues[-1]["at"] >= seconds:
        raise ClipError("cues: the last cue must start before the clip ends")
    width, height = int(req.get("width") or 1056), int(req.get("height") or 500)
    if not (320 <= width <= 1920 and 240 <= height <= 1080):
        raise ClipError("width and height: 320-1920 by 240-1080 pixels")
    parts = [_clean(p, 60) for p in (req.get("parts") or []) if _clean(p, 60)][:8]
    return {"brief": brief, "parts": parts, "cues": cues, "seconds": seconds,
            "width": width - width % 2, "height": height - height % 2,
            "fps": max(10, min(30, int(req.get("fps") or 15)))}


def description(req: dict) -> str:
    """What sim_gen is asked to draw: the brief, its parts, and one stage per cue in order."""
    text = req["brief"].rstrip(".") + "."
    if req["parts"]:
        text += " Parts: " + ", ".join(req["parts"]) + "."
    if len(req["cues"]) > 1:
        text += (f" It happens in {len(req['cues'])} stages, one after another (equal shares of the animation): "
                 + " ".join(f"({i}) {c['do'].rstrip('.')}." for i, c in enumerate(req["cues"], 1)))
    elif req["cues"]:
        text += " What happens: " + req["cues"][0]["do"].rstrip(".") + "."
    # how the clip sits in a lesson: in the colours the brief names, with each label kept on its part
    text += (" Draw each part in the colour the description gives it, if any."
             " A label stays right next to the part it names for the whole animation: when that part moves, the"
             " label moves with it (put the part and its label in one VGroup and move the VGroup)."
             " It is shown on white paper: draw no background rectangle or dark backdrop (show space, night or"
             " water depth with a few marks or a light tint, never a black fill), and keep every part clearly"
             " visible against white. A label for something that only exists after a change (the rectangle a cut"
             " piece makes) appears when that change happens, never before.")
    return text


_SCENE = r'''
import json, sys
from manim import *
import numpy as np
sys.path.insert(0, {src!r})
from lessonforge.longform.runtime import stage_progress

config.pixel_width, config.pixel_height = {w}, {h}
config.frame_height = {fh!r}
config.frame_width = {fh!r} * {w} / {h}
config.frame_rate = {fps}
config.background_color = "#ffffff"

# The drawing is written for a dark screen; the clip sits on Image Teacher's white board, so colours are moved onto
# paper here: light strokes and fills get darker (same hue), greys and white become the board's ink, and the old
# dark background colour becomes paper. The map is idempotent, so it runs again after every frame's step.
import colorsys
INK, PAPER, OLD_BG = (0x14 / 255, 0x21 / 255, 0x3d / 255), (1.0, 1.0, 1.0), (0x1b / 255, 0x1f / 255, 0x27 / 255)


def _paper(rgb):
    r, g, b = (float(v) for v in rgb[:3])
    if max(abs(r - OLD_BG[0]), abs(g - OLD_BG[1]), abs(b - OLD_BG[2])) < 0.05:
        return PAPER
    lum = 0.2126 * r + 0.7152 * g + 0.0722 * b
    if lum <= 0.6:
        return None
    if max(r, g, b) - min(r, g, b) < 0.15:
        return INK
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    while l > 0.05:
        l -= 0.03
        r, g, b = colorsys.hls_to_rgb(h, l, s)
        if 0.2126 * r + 0.7152 * g + 0.0722 * b <= 0.45:
            break
    return (r, g, b)


def on_paper(group):
    for m in group.family_members_with_points():
        try:
            new = _paper(m.get_fill_color().to_rgb())
            if new is not None:
                m.set_fill(ManimColor(new), family=False)
            new = _paper(m.get_stroke_color().to_rgb())
            if new is not None:
                m.set_stroke(ManimColor(new), family=False)
        except Exception:
            pass

{code}

EDGES, TOTAL = {edges!r}, {total!r}


def fit_camera(camera):
    """Point the camera at where the drawing really goes. The box is only its limit: a drawing that uses a third of
    the box was shown a third of the size (the parallelogram clip, 2026-11-03). A copy is stepped through its whole
    animation and the camera framed on everything visible at any time, with a margin, keeping the clip's shape."""
    try:
        probe = build({bw}, {bh})
        run = animate(probe, 1.0)
        run.begin()
        lo, hi = np.array([np.inf, np.inf]), np.array([-np.inf, -np.inf])
        for a in np.linspace(0.0, 1.0, 25):
            run.interpolate(a)
            for m in probe.family_members_with_points():
                pts = m.get_points()
                if len(pts) and (m.get_fill_opacity() > 0.02 or (m.get_stroke_opacity() > 0.02 and m.get_stroke_width() > 0)):
                    lo = np.minimum(lo, pts[:, :2].min(axis=0))
                    hi = np.maximum(hi, pts[:, :2].max(axis=0))
        if not np.all(np.isfinite(lo)):
            return
        aspect = {w} / {h}
        width, height = max(hi[0] - lo[0], 0.5) * 1.14, max(hi[1] - lo[1], 0.5) * 1.18
        fw = min(max(width, height * aspect, 2.5), {fh!r} * aspect)
        camera.frame_width, camera.frame_height = fw, fw / aspect
        camera.frame_center = np.array([(lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2, 0.0])
    except Exception:
        pass   # the box framing stays


class Clip(Scene):
    def construct(self):
        fit_camera(self.camera)
        group = build({bw}, {bh})
        on_paper(group)
        anim = animate(group, 1.0)
        try:
            anim.rate_func = linear
        except Exception:
            pass
        self.add(group)
        anim.begin()
        clock = ValueTracker(0.0)

        def step(_m):
            alpha = stage_progress(clock.get_value(), 0.0, TOTAL, EDGES) if EDGES else min(1.0, clock.get_value() / TOTAL)
            anim.interpolate(min(alpha, 1.0))
            on_paper(group)
        # the drawing itself is one of the played mobjects, so the scene redraws it every frame (a mobject only
        # stepped from an updater elsewhere is baked into the still background and never seen to move)
        self.play(clock.animate.set_value(TOTAL), UpdateFromFunc(group, step), run_time=TOTAL, rate_func=linear)
'''


def render(code: str, req: dict, out: Path, timeout: int = 600) -> Path:
    """Render a checked build/animate pair as the clip the request asks for."""
    from ..engine import sim_gen
    src = str(Path(__file__).resolve().parents[2])
    edges = [c["at"] for c in req["cues"]] if len(req["cues"]) > 1 else ([req["cues"][0]["at"]] if req["cues"] else [])
    # the camera is fitted to the drawing's box (the checks keep the drawing inside it), so nothing is rescaled
    fh = max(sim_gen.BOX_H / 0.9, (sim_gen.BOX_W / 0.92) * req["height"] / req["width"])
    work = Path(tempfile.mkdtemp(prefix="clip_"))
    scene = work / "clip_scene.py"
    scene.write_text(_SCENE.format(src=src, w=req["width"], h=req["height"], fps=req["fps"], code=code, fh=fh,
                                   edges=edges, total=float(req["seconds"]), bw=sim_gen.BOX_W, bh=sim_gen.BOX_H),
                     encoding="utf-8")
    proc = subprocess.run([sys.executable, "-m", "manim", "render", "-q", "l", "--disable_caching",
                           "--media_dir", str(work / "media"), "-o", "clip", str(scene), "Clip"],
                          cwd=work, capture_output=True, text=True, timeout=timeout)
    made = list((work / "media").rglob("clip.mp4"))
    if proc.returncode != 0 or not made:
        raise ClipError("render failed: " + (proc.stderr or proc.stdout)[-600:])
    out.parent.mkdir(parents=True, exist_ok=True)
    # -q l renders at 854x480; scale to the asked size (the frame's shape is already right)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(made[0]), "-vf", f"scale={req['width']}:{req['height']}",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "23", "-an", str(out)], check=True)
    return out


def make_clip(req: dict, out: Path, keys=None) -> dict:
    """Check the request, get a checked drawing for it (cached by description) and render the clip.

    Returns {"schema", "mp4", "seconds", "cues", "description", "cached"}; raises ClipError with the reason when
    the request is bad or no drawing passed its checks (the caller shows a still picture instead)."""
    from ..engine import sim_gen
    req = check_request(req)
    desc = description(req)
    cached = os.path.exists(sim_gen.cached_path(desc))
    # a clip has no other picture to fall back on inside the video, so its drawing gets more repair rounds than a
    # lesson scene (2 rounds refused the parallelogram cut-and-slide twice; 4 made it, at about $0.001 a round)
    # ... and the camera is framed on the drawing (fit_camera), so it need not sit centred in its box
    rounds, centred = sim_gen.REPAIR_ROUNDS, sim_gen.CENTRED
    sim_gen.REPAIR_ROUNDS = max(rounds, int(os.environ.get("CLIP_REPAIR_ROUNDS", "4")))
    sim_gen.CENTRED = False
    try:
        path = sim_gen.generate_simulation(desc, keys=keys)
    finally:
        sim_gen.REPAIR_ROUNDS, sim_gen.CENTRED = rounds, centred
    if not path:
        raise ClipError("no drawing passed its checks: " + (sim_gen.why_failed(desc) or "unknown reason"))
    code = Path(path).read_text(encoding="utf-8")
    render(code, req, out)
    return {"schema": SCHEMA, "mp4": str(out), "seconds": req["seconds"], "cues": req["cues"],
            "description": desc, "cached": cached}


if __name__ == "__main__":       # python -m lessonforge.harness.clip request.json out.mp4
    print(json.dumps(make_clip(json.load(open(sys.argv[1])), Path(sys.argv[2])), indent=1))
