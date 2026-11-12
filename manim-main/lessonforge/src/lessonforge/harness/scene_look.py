"""Looking at a model-written scene before a lesson stands on it: does it show what it was asked to show?

    a scene's module ─▶ stills where the lesson will WAIT (its start, the end of every stage) ─▶ one sheet
                     ─▶ a vision model lists what the description asks to be seen and says, thing by thing,
                        shown | missing | wrong ─▶ (faults) the scene writer is told exactly what is missing
                     ─▶ the new scene is verified, its stills drawn, and the SAME numbered list asked again
                     ─▶ the new scene is kept only when it has fewer faults and nothing it showed before is lost

``engine.sim_gen.verify`` proves a scene draws, moves, stays in its box and keeps its labels apart; it never
compares the scene with its description. In the ice lesson of 2026-10-19 four of its scenes passed every check
and showed something else: one block and a white square for "two blocks side by side, both labelled equal
mass"; two blocks of the same size where the ice was to grow; the ice block drawn SMALLER where the description
asked for it larger; no molecules where they were to spread out. The frame review found none of it (it judges a
frame against the words, and most frames of a scene are fine to look at), and the redraw tried the same day
(``compose._redraw_scenes``) kept one scene that was worse, because its second look asked only whether each
fault was cured. Here both versions answer the same numbered list, so a thing the redraw loses is seen.

Rules the look keeps (each from the trials of ``vision_review``): the judge quotes nothing it was not shown;
it answers one decision per thing; in doubt a thing is "shown" (a false fault costs a redraw, never the scene);
it runs at temperature 0. A scene nobody could look at is used as it is. Advisory end to end: no failure here
ever costs a lesson its scene. The verdict is kept in the scene's sidecar (``looked``) so a scene is looked at
once, whatever lesson uses it next.
"""
from __future__ import annotations

import base64
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

SEEN = ("shown", "missing", "wrong")

LOOK = """You look at stills of ONE short animation made for a school lesson, and check it against what it was asked to show.
The sheet has numbered panels, left to right: panel 1 is the screen when the animation starts; each later panel is the
screen at the end of one stage of it, in order. You are told the description it was made from.

List every THING the description says the viewer must SEE: each object, each label it names, a size or count it
states ("larger", "two", "most of it below the line"), and each change it describes between stages (what appears,
grows, moves, melts). One short line each, in the description's own words; at most eight. For each, look at the
panel where it should be seen and answer ONE word:
- "shown": it is there and plainly reads as what the description says;
- "missing": it is not drawn at all;
- "wrong": something is drawn for it, but it says something else (the wrong size or count, the wrong order, a
  different object), and say in a few words what is drawn instead.
When in doubt answer "shown". Judge only what is visible: never style, colour or neatness.
Then list any WORDS written in the panels that the description does not ask for (a title, a sentence, a label
naming something else); single letters and numbers on an axis are not words.
Return ONLY JSON: {"things": [{"thing": "...", "panel": 1, "seen": "shown|missing|wrong", "instead": "..."}],
 "extra_words": ["..."]}"""

RECHECK = """You look at stills of ONE short animation made for a school lesson, and check it against a numbered list of
things it must show. The sheet has numbered panels, left to right: panel 1 is the screen when the animation starts;
each later panel is the screen at the end of one stage of it, in order. You are told the description it was made from.

For EVERY numbered thing, look at the panels and answer ONE word: "shown" (it is there and plainly reads as the
description says), "missing" (not drawn at all) or "wrong" (something is drawn for it but it says something else:
say in a few words what is drawn instead). When in doubt answer "shown". Judge only what is visible.
Then list any WORDS written in the panels that the description does not ask for (a title, a sentence, a label
naming something else); single letters and numbers on an axis are not words.
Return ONLY JSON: {"answers": [{"n": 1, "seen": "shown|missing|wrong", "instead": "..."}], "extra_words": ["..."]}"""

VERSION = hashlib.sha256((LOOK + RECHECK).encode("utf-8")).hexdigest()[:10]

_STILLS = '''
from manim import *
import numpy as np
{code}

def _at(scene, alpha, staged):
    g = build({w}, {h})
    scene.add(Rectangle(width={w}, height={h}, stroke_color=GREY_D, stroke_width=1), g)
    anim = animate(g, 3.0)
    if staged:
        anim.rate_func = linear
    anim.begin()
    anim.interpolate(alpha)
{classes}
'''
_CLASS = '''
class At{i}(Scene):
    def construct(self):
        _at(self, {alpha}, {staged})
'''


def rests(stages: int) -> list[float]:
    """Where a scene stands still in a lesson: its start, and the end of each of its ``stages`` (just before a boundary)."""
    stages = max(1, int(stages))
    return [0.0] + [round(min(.999, (k + .999) / stages) if k < stages - 1 else .999, 4) for k in range(stages)]


def stills(code: str, alphas: list[float], staged: bool, box: tuple[float, float] = (6.0, 4.0),
           timeout: int = 180) -> list[bytes]:
    """The scene at each of ``alphas``, drawn by Manim in ONE process: PNG bytes in order (missing ones left out)."""
    classes = "".join(_CLASS.format(i=i, alpha=a, staged=staged) for i, a in enumerate(alphas))
    with tempfile.TemporaryDirectory(prefix="scenelook_") as work:
        src = Path(work) / "stills.py"
        src.write_text(_STILLS.format(code=code, w=box[0], h=box[1], classes=classes), encoding="utf-8")
        subprocess.run([sys.executable, "-m", "manim", "-s", "-ql", "-a", "--disable_caching", "--media_dir", work,
                        str(src)], cwd=work, capture_output=True, timeout=timeout,
                       env={**os.environ, "PYTHONPATH": ""})
        out = []
        for i in range(len(alphas)):
            found = sorted(Path(work).rglob(f"At{i}*.png"))
            if found:
                out.append(found[0].read_bytes())
        return out


def sheet(pngs: list[bytes], box: tuple[float, float] = (6.0, 4.0)) -> bytes:
    """The stills side by side with their panel numbers, as one JPEG; each cut to the scene's own box."""
    from PIL import Image, ImageDraw, ImageFont  # noqa: PLC0415
    images = []
    for p in pngs:
        im = Image.open(io.BytesIO(p)).convert("RGB")
        # Manim's frame is 14.22 by 8 units; the scene lives in its box at the centre (a tenth more for its edge).
        w, h = im.width * min(1.0, box[0] * 1.1 / 14.222), im.height * min(1.0, box[1] * 1.1 / 8.0)
        images.append(im.crop((int((im.width - w) / 2), int((im.height - h) / 2),
                               int((im.width + w) / 2), int((im.height + h) / 2))))
    width = 520
    images = [im.resize((width, int(im.height * width / im.width))) for im in images]
    height = max(im.height for im in images)
    board = Image.new("RGB", (width * len(images) + 8 * (len(images) - 1), height + 34), "white")
    draw = ImageDraw.Draw(board)
    try:
        font = ImageFont.truetype("DejaVuSans-Bold.ttf", 22)
    except OSError:
        font = ImageFont.load_default()
    for i, im in enumerate(images):
        x = i * (width + 8)
        board.paste(im, (x, 34))
        draw.text((x + 8, 4), f"panel {i + 1}" + (" (start)" if i == 0 else f" (end of stage {i})"), fill="black", font=font)
    out = io.BytesIO()
    board.save(out, format="JPEG", quality=88)
    return out.getvalue()


def _faults(things: list[dict]) -> int:
    return sum(1 for t in things if t.get("seen") in ("missing", "wrong"))


def _clean_things(answer: dict | None) -> list[dict] | None:
    if not isinstance(answer, dict) or not isinstance(answer.get("things"), list):
        return None
    out = []
    for t in answer["things"][:8]:
        if not isinstance(t, dict) or not str(t.get("thing", "")).strip():
            continue
        seen = str(t.get("seen", "shown")).strip().lower()
        out.append({"thing": str(t["thing"]).strip()[:120], "seen": seen if seen in SEEN else "shown",
                    "instead": str(t.get("instead") or "").strip()[:120] if seen in ("missing", "wrong") else ""})
    return out


def _words(answer: dict | None) -> list[str]:
    words = (answer or {}).get("extra_words") or []
    # "panel" is the sheet's own heading, not the scene's (the look named it once as a word nobody asked for).
    return [str(w).strip()[:60] for w in words if isinstance(w, str) and len(re.sub(r"[^A-Za-z]", "", w)) >= 3
            and not re.fullmatch(r"(?i)\W*panel\b.*", str(w).strip())][:6]


def look(description: str, code: str, stages: int, judge, log=print) -> dict | None:
    """``{"things": [...], "extra_words": [...], "faults": n}`` for a scene, or None when nobody could look."""
    try:
        pngs = stills(code, rests(stages), staged=stages > 1)
        if len(pngs) < 2:
            return None
        answer = judge(f"THE DESCRIPTION: «{description[:900]}»", LOOK, base64.b64encode(sheet(pngs)).decode("ascii"))
    except Exception as exc:  # noqa: BLE001 - a scene nobody could look at is used as it is
        log(f"[scene look] not looked at ({type(exc).__name__}: {str(exc)[:100]})")
        return None
    things = _clean_things(answer)
    if not things:
        return None
    return {"things": things, "extra_words": _words(answer), "faults": _faults(things)}


def recheck(description: str, code: str, stages: int, things: list[dict], judge, log=print) -> dict | None:
    """The same numbered ``things`` asked of another version of the scene; None when nobody could look."""
    try:
        pngs = stills(code, rests(stages), staged=stages > 1)
        if len(pngs) < 2:
            return None
        listed = "\n".join(f"{n}. {t['thing']}" for n, t in enumerate(things, 1))
        answer = judge(f"THE DESCRIPTION: «{description[:900]}»\nTHE THINGS IT MUST SHOW:\n{listed}", RECHECK,
                       base64.b64encode(sheet(pngs)).decode("ascii"))
    except Exception as exc:  # noqa: BLE001
        log(f"[scene look] the new scene was not looked at ({type(exc).__name__}: {str(exc)[:100]})")
        return None
    if not isinstance(answer, dict) or not isinstance(answer.get("answers"), list):
        return None
    by_n = {}
    for a in answer["answers"]:
        if isinstance(a, dict) and isinstance(a.get("n"), int):
            seen = str(a.get("seen", "")).strip().lower()
            by_n[a["n"]] = (seen if seen in SEEN else "shown", str(a.get("instead") or "").strip()[:120])
    if len(by_n) < len(things):
        return None                    # an answer that skips a thing cannot say what was lost
    out = [{"thing": t["thing"], "seen": by_n[n][0], "instead": by_n[n][1] if by_n[n][0] != "shown" else ""}
           for n, t in enumerate(things, 1)]
    return {"things": out, "extra_words": _words(answer), "faults": _faults(out)}


def better(before: dict, after: dict) -> tuple[bool, str]:
    """Whether a redrawn scene may replace the first: fewer faults, nothing shown before now lost, no more stray words."""
    lost = [b["thing"] for b, a in zip(before["things"], after["things"]) if b["seen"] == "shown" and a["seen"] != "shown"]
    if lost:
        return False, f"it lost {lost[0]!r}"
    if after["faults"] >= before["faults"]:
        return False, f"faults {before['faults']} → {after['faults']}"
    if len(after["extra_words"]) > len(before["extra_words"]):
        return False, f"it wrote words nobody asked for ({after['extra_words'][0]!r})"
    return True, f"faults {before['faults']} → {after['faults']}"


def brief(things: list[dict], extra_words: list[str]) -> str:
    """What the scene writer is told about a scene that runs but does not show its description."""
    lines = []
    for t in things:
        if t["seen"] == "missing":
            lines.append(f"- {t['thing']}: NOT DRAWN.")
        elif t["seen"] == "wrong":
            lines.append(f"- {t['thing']}: drawn wrong" + (f" (it shows {t['instead']})." if t["instead"] else "."))
    kept = [t["thing"] for t in things if t["seen"] == "shown"]
    text = ("The code runs and moves, but looking at it, it does not show what the description asks:\n" + "\n".join(lines))
    if kept:
        text += "\nKeep what is already right: " + "; ".join(kept) + "."
    if extra_words:
        text += "\nRemove the words nobody asked for: " + ", ".join(repr(w) for w in extra_words) + "."
    return text + ("\nShow each thing by its shape, size and position. A label or mark the description names (\"labelled "
                   "...\", a question mark) IS asked for: draw it, readable (at least 0.2 units tall). Any other label only "
                   "where two things could be taken for each other; no title, no sentence.")


def check(description: str, module: str | Path, stages: int, judge=None, revise=None, log=print) -> dict:
    """Look at a cached scene and, when it misses what it was asked for, have it drawn once more; keep the better.

    ``revise(code, brief) -> code | None`` writes and verifies a new version (``sim_gen.revise_simulation``).
    Returns ``{"looked", "faults", "redrawn", "kept", "why"}``. The module file is replaced only by a version that
    is ``better``; the first is kept beside it as ``.first.py``. The verdict goes into the module's sidecar.
    """
    module = Path(module)
    sidecar = Path(str(module) + ".json")
    meta = json.loads(sidecar.read_text(encoding="utf-8")) if sidecar.exists() else {}
    done = meta.get("looked") or {}
    if done.get("version") == VERSION and done.get("stages") == stages:
        return {"looked": True, "faults": done.get("faults_after", done.get("faults")), "redrawn": False,
                "kept": False, "why": "looked at before", "cached": True}
    if judge is None:
        from .vision_review import default_judge  # noqa: PLC0415
        judge = default_judge(temperature=0.0, max_tokens=900)
    if judge is None:
        return {"looked": False, "faults": None, "redrawn": False, "kept": False, "why": "no judge"}
    code = module.read_text(encoding="utf-8")
    first = look(description, code, stages, judge, log)
    if first is None:
        return {"looked": False, "faults": None, "redrawn": False, "kept": False, "why": "nobody could look"}
    result = {"looked": True, "faults": first["faults"], "redrawn": False, "kept": False, "why": "",
              "things": first["things"]}
    record = {"version": VERSION, "stages": stages, "faults": first["faults"], "things": first["things"],
              "extra_words": first["extra_words"]}
    if first["faults"] and revise is not None:
        # The first look is asked once more, by number, before a redraw is paid for: one look alone is noisy.
        again = recheck(description, code, stages, first["things"], judge, log)
        confirmed = [t for t, a in zip(first["things"], (again or {}).get("things") or [])
                     if t["seen"] != "shown" and a["seen"] != "shown"]
        if not confirmed:
            result["why"] = "the second look did not confirm the faults"
        else:
            # Only what both looks call a fault is a fault: the rest is taken as shown, for the brief and the keep rule.
            sure = {id(t) for t in confirmed}
            first = {**first, "things": [t if id(t) in sure else {**t, "seen": "shown", "instead": ""}
                                         for t in first["things"]]}
            first["faults"] = _faults(first["things"])
            result["faults"] = record["faults"] = first["faults"]
            result["redrawn"] = True
            new = None
            try:
                new = revise(code, brief(first["things"], first["extra_words"]))
            except Exception as exc:  # noqa: BLE001
                log(f"[scene look] the redraw failed ({type(exc).__name__}: {str(exc)[:100]})")
            if new:
                module.with_suffix(".tried.py").write_text(new, encoding="utf-8")   # kept for a person to read
            after = recheck(description, new, stages, first["things"], judge, log) if new else None
            if after is None:
                result["why"] = "no verified redraw" if not new else "the redraw could not be looked at"
            else:
                ok, why = better(first, after)
                result["why"], result["after"] = why, after["things"]
                record["faults_after"] = after["faults"] if ok else first["faults"]
                if ok:
                    first_copy = module.with_suffix(".first.py")
                    if not first_copy.exists():
                        first_copy.write_text(code, encoding="utf-8")
                    header = "".join(line + "\n" for line in code.splitlines() if line.startswith("#"))[:400]
                    module.write_text(header + new, encoding="utf-8")
                    result["kept"], result["faults"] = True, after["faults"]
                    record["redrawn_things"] = after["things"]
            record["redraw"] = {"kept": result["kept"], "why": result["why"]}
    meta["looked"] = record
    try:
        sidecar.write_text(json.dumps(meta, indent=1, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass
    return result
