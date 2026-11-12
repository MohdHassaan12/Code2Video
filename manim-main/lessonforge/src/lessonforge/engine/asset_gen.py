"""Generated vector assets — the LAST tier of the icon cascade.

When every retrieval provider misses (Iconify → registries → Wikimedia → Openverse →
PubChem/RDKit), the asset preflight reports ``status: "fallback", provider:
"native_shape"`` and the render draws a generic circle. A "grandfather clock" becomes
a ring. This module fills that gap: an LLM writes matplotlib **drawing code**, we
execute it in a sandboxed subprocess, and the resulting SVG enters the cascade as a
normal local asset.

Design follows the house rules:

* **Code owns structure, models own content.** The model writes ONE function —
  ``def draw(ax):`` — and nothing else. The figure, the aspect, the axis-off, the
  transparent background and the ``savefig`` are ours, in a harness the model never
  sees the inside of. That kills a whole class of "the model saved a PNG / drew axes
  / painted a white background rectangle" failures without prompt-tuning.
* **Server-side at codegen time**, exactly like the Wikimedia image pass: the
  element's ``content`` is rewritten to an absolute local path, so the render
  subprocess needs no network and no key. ``get_smart_asset`` loads a path directly.
* **Metered edge, cached hard.** One LLM call per *keyword*, then never again — the
  cache is keyed on the normalized keyword and survives across videos, so a repeated
  icon costs zero. Cache dir: ``assets/generated_cache/`` (git-ignored), with a
  sidecar recording model, prompt and the code that produced each SVG.
* **Never lose a verified artifact / degrade, never crash.** Every failure path
  (LLM down, unsafe code, subprocess error, empty SVG) returns None and leaves the
  existing native-shape fallback exactly as it was. A generated asset is accepted
  only if it renders to an SVG with real drawing primitives in it.

**Executing model-written code is a real boundary**, so it is treated as one:
``_unsafe_code`` rejects imports and IO the drawing job has no use for, and the
subprocess runs with ``-I`` (isolated: no PYTHONPATH, no user site-packages), a
scrubbed environment, a scratch cwd and a hard timeout. Knobs: ``ASSET_GEN`` (1),
``ASSET_GEN_TIMEOUT`` (45s), ``ASSET_GEN_REPAIR_ROUNDS`` (1).
"""
import os
import re
import sys
import json
import shutil
import logging
import subprocess
import tempfile
import xml.etree.ElementTree as ET

from .llm import call_llm_with_fallback, strip_code_fences, get_genai_client
from .code_safety import forbidden_reason

logger = logging.getLogger(__name__)

from .. import paths as _paths
CACHE_DIR = str(_paths.cache("assets", "generated", create=False))

TIMEOUT = int(os.getenv("ASSET_GEN_TIMEOUT", "45"))


def enabled():
    return os.getenv("ASSET_GEN", "1") != "0"


def slug(keyword):
    """Cache key: the keyword, normalized the way a filename can hold it."""
    s = re.sub(r"[^a-z0-9]+", "_", (keyword or "").strip().lower()).strip("_")
    return (s or "asset")[:48]


def cached_path(keyword):
    """Path this keyword's generated SVG lives at (existing or not)."""
    return os.path.join(CACHE_DIR, f"gen_{slug(keyword)}.svg")


# ── The prompt ────────────────────────────────────────────────────────────────

_SYSTEM = (
    "You write matplotlib drawing code for educational vector icons. You reply with "
    "Python source ONLY — no markdown fences, no prose, no explanation."
)

_PROMPT = """Draw a clean, recognisable **flat line-art icon** of: {keyword}

{context}Write exactly one Python function and nothing else:

    def draw(ax):
        ...

Rules — the harness around you owns everything except the drawing:
- `ax` is a matplotlib Axes that is already square, axis-off and transparent. Do NOT
  create a figure, do NOT call savefig, show, subplots, axis, set_aspect or tight_layout.
- `np` (numpy) and `math` are already imported. Import nothing at all.
- Draw with ax.plot / ax.add_patch (matplotlib.patches is available as `patches`) /
  ax.fill. Use `lw=6` strokes, `color='black'`, and `fill=False` on patches — the
  renderer recolours the whole icon later, so shape is all that matters.
- Stay inside x in [0, 100] and y in [0, 100]; call ax.set_xlim(0, 100) and
  ax.set_ylim(0, 100) as your first two lines so the icon is centred and sized.
- NO text, NO labels, NO axes, NO legend, NO title, NO gridlines — a text glyph in an
  icon renders as unreadable outlines.
- Aim for 4-12 strokes/shapes: the silhouette that makes the object recognisable at
  thumbnail size, not a detailed illustration.
"""

_REPAIR = """The code you wrote failed to run. Fix it and return the corrected
`def draw(ax):` function only — same rules as before.

Error:
{error}

Your code:
{code}
"""


# ── Safety gate on model-written code ─────────────────────────────────────────

# Substrings that have no business in a drawing function. Checked before the code is
# ever written to disk: this is model-authored code about to be EXECUTED, so the
# gate is a contract, not advice (same reasoning as the reasoning-model block).
# The shared list (code_safety.py) matches tokens, not letters; these two are this
# harness's own: it owns the figure, so the model may neither save nor show one.
_FORBIDDEN_HERE = ("savefig", "plt.show")

# The only imports tolerated (the harness already provides them; a model that adds
# them anyway is being redundant, not hostile).
_IMPORT_OK = re.compile(r"^\s*(import\s+(numpy|math|matplotlib)[\w. ]*|"
                        r"from\s+(numpy|math|matplotlib)[\w.]*\s+import\s+[\w, ]+)\s*$")


def _unsafe_code(code):
    """Return the reason this code must not be executed, or None if it is fine."""
    if "def draw(" not in code:
        return "no draw(ax) function"
    reason = forbidden_reason(code, extra=_FORBIDDEN_HERE)
    if reason:
        return reason
    for line in code.splitlines():
        stripped = line.strip()
        if (stripped.startswith("import ") or stripped.startswith("from ")) \
                and not _IMPORT_OK.match(line):
            return f"disallowed import: {stripped[:60]!r}"
    return None


# ── The harness the model's function runs inside ──────────────────────────────

_HARNESS = '''\
import matplotlib
matplotlib.use("Agg")
import math
import numpy as np
import matplotlib.pyplot as plt
from matplotlib import patches

{code}

fig, ax = plt.subplots(figsize=(4, 4))
ax.set_aspect("equal")
ax.set_axis_off()
ax.set_xlim(0, 100)
ax.set_ylim(0, 100)
draw(ax)
fig.patch.set_alpha(0.0)
fig.savefig({out!r}, format="svg", transparent=True,
            bbox_inches="tight", pad_inches=0.04)
'''


def _run_drawing_code(code, out_path):
    """Execute the harness in an isolated subprocess. Returns (ok, error_text)."""
    work = tempfile.mkdtemp(prefix="assetgen_")
    script = os.path.join(work, "draw_asset.py")
    try:
        with open(script, "w", encoding="utf-8") as f:
            f.write(_HARNESS.format(code=code, out=out_path))
        env = {
            "PATH": os.environ.get("PATH", ""),
            "HOME": work,
            "MPLBACKEND": "Agg",
            "MPLCONFIGDIR": work,
        }
        # -I = isolated mode: no PYTHONPATH, no user site-packages, no cwd on sys.path.
        proc = subprocess.run([sys.executable, "-I", script], cwd=work, env=env,
                              capture_output=True, text=True, timeout=TIMEOUT)
        if proc.returncode != 0:
            return False, (proc.stderr or proc.stdout or "unknown error")[-1200:]
        return True, ""
    except subprocess.TimeoutExpired:
        return False, f"drawing code exceeded the {TIMEOUT}s time limit"
    except Exception as e:
        return False, str(e)
    finally:
        shutil.rmtree(work, ignore_errors=True)


# ── Accepting the result ──────────────────────────────────────────────────────

_DRAWABLE = ("path", "polygon", "polyline", "circle", "ellipse", "line", "rect")


def _paint(node):
    """Style + presentation attributes of an SVG node, lowercased."""
    out = {}
    for part in (node.get("style") or "").split(";"):
        if ":" in part:
            k, v = part.split(":", 1)
            out[k.strip().lower()] = v.strip().lower()
    for attr in ("fill", "stroke", "opacity", "fill-opacity", "stroke-opacity", "visibility"):
        val = node.get(attr)
        if val is not None:
            out.setdefault(attr, str(val).strip().lower())
    return out


def _is_visible(node):
    """True if this primitive actually puts ink on the canvas.

    Matplotlib always emits a full-canvas figure-background path — with
    `style="fill: none; opacity: 0"`, i.e. invisible. Counting it made an EMPTY
    drawing look like a successful one (measured: a `draw()` that only set the axis
    limits was accepted and shipped a blank icon). Invisible marks don't count.
    """
    p = _paint(node)
    if p.get("visibility") == "hidden":
        return False
    if p.get("opacity") in ("0", "0.0", "0%"):
        return False
    stroked = (p.get("stroke", "none") != "none"
               and p.get("stroke-opacity") not in ("0", "0.0"))
    filled = (p.get("fill", "none") != "none"
              and p.get("fill-opacity") not in ("0", "0.0"))
    if "fill" not in p and "stroke" not in p:
        return True  # SVG's default fill is black
    return stroked or filled


def _svg_problems(path):
    """Why this SVG is not usable as an icon, or None if it is.

    An empty axes still saves a perfectly valid SVG file — "the subprocess exited 0"
    proves nothing, exactly like "the JSON parsed" at the storyboard gate. So the
    file is opened and its VISIBLE drawing primitives are counted.
    """
    try:
        size = os.path.getsize(path)
    except OSError:
        return "no file was written"
    if size < 200:
        return f"file is only {size} bytes"
    if size > 4_000_000:
        return f"file is {size // 1024}KB — too complex to be an icon"
    try:
        root = ET.parse(path).getroot()
    except Exception as e:
        return f"not parseable as SVG ({e})"
    marks = 0
    for node in root.iter():
        tag = node.tag.rsplit("}", 1)[-1].lower()
        if tag not in _DRAWABLE:
            continue
        if tag == "path" and len(node.get("d") or "") < 12:
            continue  # a degenerate stub, e.g. matplotlib's clip artefacts
        if not _is_visible(node):
            continue
        marks += 1
    if marks < 1:
        return "the SVG contains no visible drawing primitives (empty canvas)"
    return None


def _write_sidecar(svg_path, **meta):
    try:
        with open(svg_path + ".json", "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=1)
    except Exception as e:
        logger.warning("Could not write generated-asset sidecar: %s", e)


# ── Public API ────────────────────────────────────────────────────────────────

def generate_vector_asset(keyword, context="", keys=None, client=None):
    """Draw `keyword` with LLM-written matplotlib code. Returns a path, or None.

    Cached by keyword: the second call for the same icon costs nothing. Every
    failure returns None so the caller keeps whatever fallback it already had.
    """
    if not enabled():
        return None
    kw = (keyword or "").strip()
    if not kw:
        return None

    out = cached_path(kw)
    if os.path.exists(out) and not _svg_problems(out):
        logger.info("Generated-asset cache HIT for %r.", kw)
        return out

    os.makedirs(CACHE_DIR, exist_ok=True)
    if client is None:
        client = get_genai_client(keys)

    prompt = _PROMPT.format(
        keyword=kw,
        context=(f"Context — it appears in this scene: {context}\n\n" if context else ""),
    )
    rounds = int(os.getenv("ASSET_GEN_REPAIR_ROUNDS", "1"))
    code, last_error = None, ""

    for attempt in range(rounds + 1):
        try:
            resp = call_llm_with_fallback(
                client,
                prompt if attempt == 0 else _REPAIR.format(error=last_error, code=code),
                _SYSTEM, temperature=0.3, task="code", keys=keys,
            )
            code = strip_code_fences((resp.text or "").strip())
        except Exception as e:
            logger.warning("Asset generation for %r: no LLM available (%s).", kw, e)
            return None

        reason = _unsafe_code(code)
        if reason:
            # Not a retry case: a model that reached for `open(` will reach again.
            logger.warning("Asset generation for %r REJECTED before execution: %s.", kw, reason)
            return None

        tmp_out = out + ".part"
        ok, err = _run_drawing_code(code, tmp_out)
        problem = None if ok else err
        if ok:
            problem = _svg_problems(tmp_out)
        if not problem:
            os.replace(tmp_out, out)
            _write_sidecar(out, keyword=kw, context=context, code=code,
                           attempts=attempt + 1, generator="matplotlib")
            logger.info("Generated a vector asset for %r (attempt %d) -> %s",
                        kw, attempt + 1, os.path.basename(out))
            return out

        try:
            os.remove(tmp_out)
        except OSError:
            pass
        last_error = problem
        logger.warning("Asset generation for %r failed (attempt %d/%d): %s",
                       kw, attempt + 1, rounds + 1, str(problem)[:200])

    return None


def _mode():
    """Which icons to draw: `fallback` (misses only) | `weak` (default) | `always`.

    `weak` also draws icons the retrieval cascade "resolved" with a generic ancestor
    — Iconify answers "grandfather clock" with a plain clock face and reports
    success, so a resolved-but-wrong icon never reached any fallback. See
    assets.icon_match_strength.
    """
    m = (os.getenv("ASSET_GEN_MODE") or "weak").strip().lower()
    return m if m in ("fallback", "weak", "always") else "weak"


def should_generate(probe):
    """True if this probed asset should be DRAWN rather than trusted to retrieval."""
    if probe.get("type") != "svg_icon":
        return False          # molecules stay with RDKit/PubChem — see below
    if probe.get("status") == "fallback":
        return True           # nothing found at all
    mode = _mode()
    if mode == "fallback":
        return False
    if mode == "always":
        return True
    return probe.get("match", "strong") != "strong"


def resolve_generated_assets(storyboard, asset_warnings, probes=None, keys=None, client=None):
    """Fill unresolvable — and *badly* resolved — `svg_icon` elements with drawings.

    `asset_warnings` is the preflight's fallback list (nothing resolved the keyword);
    `probes` is the full probe result list, which also carries the icons that
    resolved to a generic ancestor (`match` != "strong"). Both are candidates: for
    each, the element's `content` is rewritten to an absolute path to a generated
    SVG — the same contract as the Wikimedia image pass, and `get_smart_asset` loads
    a path directly. Returns the warnings that are still unresolved, so the caller
    keeps degrading exactly as before for those.

    chemical_molecule is deliberately NEVER generated: a wrong structural formula is
    worse than a generic shape, and RDKit/PubChem are authoritative.
    """
    candidates = list(asset_warnings or [])
    for p in (probes or []):
        if p not in candidates and should_generate(p):
            candidates.append(p)
    if not enabled() or not candidates:
        return list(asset_warnings or [])

    targets = {}
    for w in candidates:
        if w.get("type") == "svg_icon" and (w.get("keyword") or "").strip():
            targets.setdefault(w["keyword"].strip(), []).append(w)
    if not targets:
        return list(asset_warnings)

    if client is None:
        client = get_genai_client(keys)

    logger.info("Asset generation (mode=%s): drawing %d icon keyword(s) — %s",
                _mode(), len(targets), ", ".join(sorted(targets))[:200])
    resolved = {}
    for kw in targets:
        # Give the model the scene description as context when we can find it.
        path = generate_vector_asset(kw, context=_scene_context(storyboard, kw),
                                     keys=keys, client=client)
        if path:
            resolved[kw] = path

    if resolved:
        for scene in storyboard.get("visual_storyboard", []) or []:
            for el in scene.get("elements", []) or []:
                if el.get("type") != "svg_icon":
                    continue
                path = resolved.get(str(el.get("content") or "").strip())
                if path:
                    el["content"] = path

    still = [w for w in asset_warnings
             if not (w.get("type") == "svg_icon"
                     and (w.get("keyword") or "").strip() in resolved)]
    for w in asset_warnings:
        if w not in still:
            logger.info("Icon %r for element %s is now a generated drawing.",
                        w.get("keyword"), w.get("element_id"))
    return still


def _scene_context(storyboard, keyword):
    """The description of the first scene using this keyword — helps the drawing."""
    for scene in storyboard.get("visual_storyboard", []) or []:
        for el in scene.get("elements", []) or []:
            if str(el.get("content") or "").strip() == keyword:
                return str(scene.get("description") or "")[:200]
    return ""
