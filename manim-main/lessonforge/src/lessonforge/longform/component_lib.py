"""Lesson-visuals components, read through Node: the catalogue, the parameter checks and the drawing (stdlib only).

A component is one TypeScript file, ``components/<subject>/<id>.ts``, in the lesson-visuals repo (contract:
``components/README.md`` there; checker: ``components/tools/check.ts``). It exports ``meta`` (id, title, subject, ncert,
size, params, parts, states, anchors, example), ``validate(params)`` and ``draw(params, state)``, with no imports.
This module is the Python side of that contract, and it is the only place that runs Node:

* ``catalogue()`` globs ``components/*/*.ts`` at call time, so a file the owner adds is found with no registration;
* a state is either a list of named presets or a number slider ``{type: "number", min, max, default, say}`` (the
  lesson-visuals contract of 2026-11); ``meta.layer``, ``meta.ground``, ``meta.situations`` and any field this module
  does not know are carried, never refused (``catalogue()`` shows them);
* ``validate()`` checks the keys, types, options, ranges and states from ``meta`` first (the component's own
  ``validate`` does not reject an unknown key or a wrong JS type), fills the defaults (``draw`` does not), then asks
  the component's own ``validate``;
* ``draw()`` returns the parts IN ``meta.parts`` ORDER, the anchors and the labels, and re-checks the shape of what
  came back. The same input is drawn once per process: results are cached by sha256 of (file content, merged params,
  state), so an edited component is never served from an old drawing.

Node runs in ONE short process per batch (about 0.06 s to start), with ``--permission`` and read access to the
components folder only: no writes, no child processes, no workers, and a clean environment (no keys). A file that
fails to load is listed by ``broken()``, never raised. Nothing here imports manim, numpy or ``lessonforge.harness``.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import threading
from pathlib import Path
from typing import Any, Iterable

ENV_DIR = "LESSON_VISUALS_DIR"
ENV_NODE = "LESSONFORGE_NODE"
DEFAULT_DIR = "/home/mani/lesson-visuals"
ENV_SCOPE = "LESSONFORGE_SCOPE_CLASSES"


def scope_classes(raw: str | None = None) -> tuple[int, ...]:
    """The NCERT classes the kits serve: 1 to 12 (the owner, 2026-11-09: maths for every class). ``LESSONFORGE_SCOPE_CLASSES``
    narrows it ("6-9" or "6,7,8,9" gives the earlier scope); a value that names no class from 1 to 12 is ignored."""
    text = os.environ.get(ENV_SCOPE, "") if raw is None else raw
    found: set[int] = set()
    for piece in re.split(r"[\s,]+", text.strip()):
        m = re.fullmatch(r"(\d{1,2})(?:\s*[-\u2013]\s*(\d{1,2}))?", piece)
        if m:
            lo, hi = int(m.group(1)), int(m.group(2) or m.group(1))
            found.update(c for c in range(lo, hi + 1) if 1 <= c <= 12)
    return tuple(sorted(found)) or tuple(range(1, 13))


SCOPE_CLASSES = scope_classes()


def scope_text() -> str:
    """"classes 6 to 9" / "classes 1 to 12", for messages."""
    return f"classes {SCOPE_CLASSES[0]} to {SCOPE_CLASSES[-1]}"
NODE_MIN = (22, 6)            # --experimental-strip-types arrived in 22.6
RUN_TIMEOUT = 20.0
MAX_OUTPUT = 12_000_000       # bytes of JSON a run may print
MAX_PART_SVG = 400_000        # characters in one part
SKIP_DIRS = {"tools"}
#: The tags check.ts allows in a drawing; a part with another tag is refused (manim's SVG parser is fragile).
SVG_TAGS = frozenset({"path", "line", "polyline", "polygon", "rect", "circle", "ellipse", "g", "text", "tspan"})
_BANNED = re.compile(r"\b(?:filter|mask|clipPath|linearGradient|radialGradient|image|foreignObject|script|style|use|animate\w*)\b")
_ID = re.compile(r"^[a-z][a-z0-9_]*$")
_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_CLASS = re.compile(r"^\s*Class\s+(\d+)\s*,\s*Ch(?:apter)?\s*(\d+)\s*(.*?)\s*$", re.I)
#: The looser form the library now also writes: "Class 8 Science: Light (reflection)" or "Class 11, Chemistry lab: titration".
_CLASS_LOOSE = re.compile(r"^\s*Class\s+(\d+)\b(?!\s*(?:-|–|to)\s*\d)\s*[,:]?\s*\S", re.I)
_RANGE = re.compile(r"^\s*(?:Any\s+class(?:es)?|Class(?:es)?)\s+(\d+)\s*(?:-|–|to)\s*(\d+)", re.I)
#: "Any class story, activity or scene" (no number): every class, 1 to 12.
_ANY = re.compile(r"^\s*Any\s+class(?:es)?\b(?!\s*\d)", re.I)
_SIDES = ("left", "right", "above", "below")
LAYERS = ("background", "actor", "prop", "overlay")        # the order the composer draws them in
#: Fields of ``meta`` this module reads; any other field is carried in ``entry["extra"]``.
_KNOWN_META = frozenset("id title subject ncert size params parts states anchors example layer ground situations".split())
_LABEL_NUMBER = re.compile(r"(?<![\w.^])\d+(?:\.\d+)?")
_STOP = frozenset("a an and are as at be by for from has have in is it its of on or that the their this to up was with "
                  "you your into how what when where which who whose than then them they who per each one two".split())


class ComponentError(ValueError):
    """Something about a component that code cannot work around. ``str(e)`` is plain words."""


# ── Node: where it is, whether it can be used ────────────────────────────────────────────────────────────────────

def visuals_dir() -> Path:
    """The lesson-visuals checkout (``LESSON_VISUALS_DIR``, default ``/home/mani/lesson-visuals``)."""
    return Path(os.environ.get(ENV_DIR, "").strip() or DEFAULT_DIR).expanduser()


def components_dir() -> Path:
    """``<visuals>/components``; a folder that holds the subject folders itself is taken as it is."""
    root = visuals_dir()
    return root / "components" if (root / "components").is_dir() else root


def node_path() -> str | None:
    """The Node binary: ``LESSONFORGE_NODE``, then ``node`` on PATH, then ``~/.local/bin/node``."""
    for cand in (os.environ.get(ENV_NODE, "").strip(), shutil.which("node") or "", str(Path.home() / ".local/bin/node")):
        if cand and Path(cand).is_file() and os.access(cand, os.X_OK):
            return cand
    return None


_NODE_OK: dict[str, str] = {}      # node path -> "" when usable, else the reason


def _node_reason(node: str) -> str:
    if node in _NODE_OK:
        return _NODE_OK[node]
    reason = ""
    try:
        done = subprocess.run([node, "--version"], capture_output=True, text=True, timeout=10,
                              env={"PATH": "/usr/bin:/bin"})
        found = re.match(r"v(\d+)\.(\d+)", done.stdout.strip())
        if not found:
            reason = f"node answered {done.stdout.strip()[:40]!r} to --version"
        elif (int(found.group(1)), int(found.group(2))) < NODE_MIN:
            reason = f"node {done.stdout.strip()} is too old: components need Node 22.6 or newer (--experimental-strip-types)"
    except (OSError, subprocess.SubprocessError) as exc:
        reason = f"node could not be run ({type(exc).__name__})"
    _NODE_OK[node] = reason
    return reason


def has_components(directory: Path | None = None) -> bool:
    """True when the folder holds at least one ``<subject>/<id>.ts`` (cheap: no Node)."""
    try:
        return bool(_files(directory or components_dir()))
    except OSError:
        return False


def unavailable_reason() -> str:
    """"" when components can be used now, else one plain sentence saying why not."""
    node = node_path()
    if node is None:
        return f"node was not found (set {ENV_NODE}, or put Node 22.6+ on PATH): components cannot be drawn"
    bad = _node_reason(node)
    if bad:
        return bad
    cdir = components_dir()
    if not cdir.is_dir():
        return f"the components folder {cdir} does not exist (set {ENV_DIR} to the lesson-visuals checkout)"
    if not has_components(cdir):
        return f"the components folder {cdir} holds no <subject>/<id>.ts file"
    return ""


def available() -> bool:
    return not unavailable_reason()


# ── the Node runner: one process per batch ───────────────────────────────────────────────────────────────────────

#: Jobs come on stdin as JSON ``[{"op": "meta"|"validate"|"draw", "file": ..., ...}]``; one result per job comes back on
#: stdout. A job that throws costs only itself. ``clone`` drops functions and turns NaN into null (Python then sees it).
_RUNNER = r"""
import { pathToFileURL } from "node:url";
const chunks = [];
for await (const c of process.stdin) chunks.push(c);
const jobs = JSON.parse(Buffer.concat(chunks).toString("utf8"));
const clone = (x) => JSON.parse(JSON.stringify(x === undefined ? null : x));
const mods = new Map();
const load = async (file) => {
  if (!mods.has(file)) mods.set(file, import(pathToFileURL(file).href));
  return mods.get(file);
};
const out = [];
for (const job of jobs) {
  try {
    const m = await load(job.file);
    if (job.op === "meta") {
      out.push({ ok: true, meta: clone(m.meta), validate: typeof m.validate, draw: typeof m.draw });
    } else if (job.op === "validate") {
      const r = m.validate(clone(job.params));
      out.push({ ok: true, problems: Array.isArray(r) ? clone(r) : ["validate did not return a list"] });
    } else if (job.op === "draw") {
      const a = clone(m.draw(clone(job.params), clone(job.state ?? {})));
      let same = true;
      if (job.twice) same = JSON.stringify(a) === JSON.stringify(clone(m.draw(clone(job.params), clone(job.state ?? {}))));
      out.push({ ok: true, draw: a, deterministic: same });
    } else {
      out.push({ ok: false, error: "unknown op" });
    }
  } catch (e) {
    out.push({ ok: false, error: String((e && e.message) || e).slice(0, 300) });
  }
}
process.stdout.write(JSON.stringify(out));
"""


def _run(jobs: list[dict]) -> list[dict]:
    """The results of ``jobs`` from ONE Node process. Raises ``ComponentError`` when Node itself fails."""
    why = unavailable_reason()
    if why:
        raise ComponentError(why)
    cdir = components_dir().resolve()
    cmd = [node_path(), "--permission", f"--allow-fs-read={cdir}", "--no-warnings", "--experimental-strip-types",
           "--input-type=module", "-e", _RUNNER]
    try:
        done = subprocess.run(cmd, input=json.dumps(jobs), capture_output=True, text=True, timeout=RUN_TIMEOUT,
                              cwd=str(cdir), env={"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"})
    except subprocess.TimeoutExpired:
        raise ComponentError(f"a component did not finish in {RUN_TIMEOUT:g} s (an endless loop?)") from None
    except OSError as exc:
        raise ComponentError(f"node could not be run ({type(exc).__name__}: {exc})") from exc
    if done.returncode != 0 or not done.stdout.strip():
        raise ComponentError("node failed while reading the components: " + (done.stderr.strip().splitlines() or ["no message"])[-1][:200])
    if len(done.stdout) > MAX_OUTPUT:
        raise ComponentError("a component printed far too much")
    try:
        out = json.loads(done.stdout)
    except ValueError as exc:
        raise ComponentError("node answered with something that is not JSON") from exc
    if not isinstance(out, list) or len(out) != len(jobs):
        raise ComponentError("node answered with the wrong number of results")
    return out


# ── the catalogue ────────────────────────────────────────────────────────────────────────────────────────────────

def classes_of(ncert: Iterable[str] | str | None) -> set[int]:
    """Classes named by ``meta.ncert`` strings: "Class 8, Ch 11 ..." -> {8}; "Class 6-10" or "Class 1 to 12" -> that range;
    "Any class 6-10 ..." -> {6..10}; "Any class ..." (no number) -> every class, 1 to 12."""
    out: set[int] = set()
    for line in [ncert] if isinstance(ncert, str) else list(ncert or []):
        text = str(line)
        if (m := _CLASS.match(text)):
            out.add(int(m.group(1)))
        elif (m := _RANGE.match(text)):
            lo, hi = sorted((int(m.group(1)), int(m.group(2))))
            out |= set(range(max(lo, 1), min(hi, 12) + 1))
        elif _ANY.match(text):
            out |= set(range(1, 13))
        elif (m := _CLASS_LOOSE.match(text)):
            out.add(int(m.group(1)))
    return out


def chapters_of(ncert: Iterable[str] | None) -> list[dict]:
    """``[{cls, ch, title}]`` for each "Class N, Ch M Title (notes)" string; the title stops at the first "("."""
    out = []
    for line in ncert or []:
        m = _CLASS.match(str(line))
        if m:
            out.append({"cls": int(m.group(1)), "ch": int(m.group(2)), "title": m.group(3).split("(")[0].strip()})
    return out


def _files(cdir: Path) -> list[Path]:
    """Every ``<subject>/<id>.ts`` under ``cdir`` (not ``tools``, drafts starting with . or _, or a link out of it)."""
    if not cdir.is_dir():
        return []
    root = cdir.resolve()
    out = []
    for sub in sorted(cdir.iterdir()):
        if not sub.is_dir() or sub.name in SKIP_DIRS or sub.name.startswith((".", "_")):
            continue
        for f in sorted(sub.glob("*.ts")):
            if f.name.startswith(("_", ".")) or f.name.endswith(".d.ts"):
                continue
            try:
                if f.is_file() and f.resolve().is_relative_to(root):
                    out.append(f)
            except OSError:
                continue
    return out


def _keywords(entry: dict) -> list[str]:
    """Lower-case words that suggest the component: title, id, parts, and what each parameter says."""
    texts = [entry["title"], entry["id"].replace("_", " "), entry["subject"]]
    texts += [p["name"].replace("_", " ") + " " + p.get("say", "") for p in entry["params"]]
    texts += [c["title"] for c in entry["chapters"]]
    out: list[str] = []
    for text in texts:
        for word in re.findall(r"[a-z][a-z\-]{2,}", text.lower()):
            if word not in _STOP and word not in out:
                out.append(word)
    return out[:60]


def _num(x: Any) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def is_knob(spec: Any) -> bool:
    """True for a number state (a slider): ``{type: "number", min, max, default, say}``; a named state is a list."""
    return isinstance(spec, dict) and spec.get("type") == "number"


def _states(raw: Any) -> tuple[dict, str]:
    """(``{name: [values] | {type, min, max, default, say}}``, "") or ({}, why the component cannot be loaded)."""
    if raw is None:
        return {}, ""
    if not isinstance(raw, dict):
        return {}, "meta.states must be an object mapping each state to a list of names or a number slider"
    out: dict[str, Any] = {}
    for name, spec in raw.items():
        if not _NAME.match(str(name)):
            return {}, f"meta.states has a name that is not a plain word: {str(name)[:30]!r}"
        if isinstance(spec, list):
            out[str(name)] = list(spec)
        elif is_knob(spec):
            lo, hi, dflt = spec.get("min"), spec.get("max"), spec.get("default")
            if not (_num(lo) and _num(hi) and lo < hi):
                return {}, f"number state {name} needs numbers min < max"
            if not (_num(dflt) and lo <= dflt <= hi):
                return {}, f"number state {name} needs a default between min and max"
            out[str(name)] = {"type": "number", "min": lo, "max": hi, "default": dflt, "say": str(spec.get("say") or "")}
        else:
            return {}, (f"meta.states.{name} must be a list of names or a number slider "
                        "{type: 'number', min, max, default, say}")
    return out, ""


def _canvas(meta: dict, size: list, warnings: list[str]) -> tuple[str | None, float | None]:
    """(layer, ground) as carried: a value outside the contract is dropped with a warning, never a refusal."""
    layer, ground = meta.get("layer"), meta.get("ground")
    if "layer" in meta and layer not in LAYERS:
        warnings.append(f"meta.layer {str(layer)[:20]!r} is not one of {', '.join(LAYERS)}; ignored")
        layer = None
    if "ground" in meta and not (_num(ground) and 0 <= ground <= size[1]):
        warnings.append("meta.ground is not a y inside the size; ignored")
        ground = None
    return (layer if isinstance(layer, str) else None), (float(ground) if ground is not None else None)


def _situations(raw: Any, entry: dict, warnings: list[str]) -> list[dict]:
    """``[{name, title, ncert, params, steps: [{state, show, say}]}]`` from ``meta.situations`` (an object keyed by name).

    A step's ``state`` is what the step sets (as written); ``show`` is the parts on screen at that step (a step that lists
    none keeps the step before it, the first shows every part); ``params`` appears only on a step that moves a number
    param. A situation that cannot be read is left out with a warning, never a refusal; whether its numbers are legal
    is checked when it is used (``situation_plan``).
    """
    if raw is None:
        return []
    if not isinstance(raw, dict):
        warnings.append("meta.situations is not an object {name: {title, params, steps}}; ignored")
        return []
    out = []
    for name, spec in raw.items():
        steps_in = spec.get("steps") if isinstance(spec, dict) else None
        if not (_NAME.match(str(name)) and isinstance(steps_in, list) and steps_in
                and all(isinstance(s, dict) for s in steps_in)):
            warnings.append(f"situation {str(name)[:30]!r} has no steps or a bad name; left out")
            continue
        shown, steps = list(entry["parts"]), []
        for st in steps_in:
            if isinstance(st.get("show"), list) and all(isinstance(p, str) for p in st["show"]):
                shown = list(st["show"])
            step = {"state": dict(st["state"]) if isinstance(st.get("state"), dict) else {}, "show": list(shown),
                    "say": str(st.get("say") or "")}
            if isinstance(st.get("params"), dict):
                step["params"] = dict(st["params"])
            steps.append(step)
        ncert = spec.get("ncert")
        out.append({"name": str(name), "title": str(spec.get("title") or name),
                    "ncert": "; ".join(map(str, ncert)) if isinstance(ncert, list) else str(ncert or ""),
                    "params": dict(spec["params"]) if isinstance(spec.get("params"), dict) else {}, "steps": steps})
    return out


def _entry(file: Path, meta: Any, cdir: Path) -> tuple[dict | None, str]:
    """(catalogue entry, "") for a loadable component, or (None, why not)."""
    if not isinstance(meta, dict):
        return None, "it exports no meta object"
    cid, subject = meta.get("id"), meta.get("subject")
    if cid != file.stem or not isinstance(cid, str) or not _ID.match(cid):
        return None, f'meta.id {cid!r} must match the file name "{file.stem}" (lower case, digits, _)'
    if subject != file.parent.name:
        return None, f'meta.subject {subject!r} must match the folder "{file.parent.name}"'
    size = meta.get("size")
    if not (isinstance(size, list) and len(size) == 2 and all(isinstance(x, (int, float)) and not isinstance(x, bool) and x > 0 for x in size)):
        return None, "meta.size must be [width, height]"
    parts = meta.get("parts")
    if not (isinstance(parts, list) and parts and all(isinstance(p, str) and p for p in parts) and len(set(parts)) == len(parts)):
        return None, "meta.parts must be a list of distinct names"
    params_in = meta.get("params")
    if not isinstance(params_in, dict):
        return None, "meta.params must be an object"
    params = []
    for name, spec in params_in.items():
        if not _NAME.match(str(name)) or not isinstance(spec, dict) or "default" not in spec:
            return None, f"meta.params.{name} needs a type and a default"
        item = {"name": name, "type": str(spec.get("type") or ""), "default": spec["default"], "say": str(spec.get("say") or "")}
        for key in ("min", "max"):
            if isinstance(spec.get(key), (int, float)) and not isinstance(spec.get(key), bool):
                item[key] = spec[key]
        if isinstance(spec.get("options"), list):
            item["options"] = list(spec["options"])
        params.append(item)
    states, why = _states(meta.get("states"))
    if why:
        return None, why
    anchors = meta.get("anchors") if isinstance(meta.get("anchors"), list) else []
    ncert = [str(x) for x in meta.get("ncert") or []] if isinstance(meta.get("ncert"), list) else []
    classes = sorted(classes_of(ncert))
    warnings: list[str] = []
    for key, knob in states.items():
        if isinstance(knob, dict) and not knob["say"]:
            warnings.append(f"number state {key} has no 'say' line, so a planner is not told what the number means")
    if not classes:
        warnings.append("meta.ncert has no 'Class N ...' or 'Any class a-b' string, so its class is unknown")
    if any(not re.fullmatch(r"[a-z][a-z0-9_]{0,23}", p) for p in parts):
        warnings.append("a part name is not lower case snake_case within 24 characters, so a step's focus cannot name it")
    entry = {"id": cid, "title": str(meta.get("title") or cid), "subject": subject, "size": [float(size[0]), float(size[1])],
             "classes": classes, "chapters": chapters_of(ncert), "ncert": ncert, "params": params, "parts": list(parts),
             "states": states, "anchors": [str(a) for a in anchors],
             "example": meta.get("example") if isinstance(meta.get("example"), dict) else {},
             "path": str(file.relative_to(cdir)), "warnings": warnings}
    entry["layer"], entry["ground"] = _canvas(meta, entry["size"], warnings)
    entry["situations"] = _situations(meta.get("situations"), entry, warnings)
    entry["extra"] = {str(k): v for k, v in meta.items() if k not in _KNOWN_META}
    entry["keywords"] = _keywords(entry)
    return entry, ""


_SCAN_LOCK = threading.Lock()
_SCANS: dict[str, tuple[str, dict]] = {}          # components dir -> (content key, scan)


def _scan() -> dict:
    """``{"entries": [...], "broken": [...]}`` for the components folder now. Cached by the CONTENT of the files."""
    cdir = components_dir()
    files = _files(cdir)
    blobs = {f: f.read_bytes() for f in files}
    key = hashlib.sha256(("v3\n" + "\n".join(f"{f.relative_to(cdir)}:{hashlib.sha256(b).hexdigest()}"
                                              for f, b in blobs.items())).encode()).hexdigest()
    with _SCAN_LOCK:
        held = _SCANS.get(str(cdir))
        if held and held[0] == key:
            return held[1]
        scan = _disk_get(key)
        if scan is None:
            scan = _load_all(cdir, files, blobs)
            _disk_put(key, scan)
        _SCANS[str(cdir)] = (key, scan)
        return scan


def _disk_dir() -> Path | None:
    try:
        from .. import paths  # noqa: PLC0415 - tiny module, only needed here
        return paths.cache("components")
    except Exception:  # noqa: BLE001 - a cache that cannot be had is no reason to fail
        return None


def _disk_get(key: str) -> dict | None:
    folder = _disk_dir()
    if folder is None:
        return None
    try:
        data = json.loads((folder / f"catalogue-{key[:24]}.json").read_text(encoding="utf-8"))
        return data if isinstance(data, dict) and "entries" in data and "broken" in data else None
    except (OSError, ValueError):
        return None


def _disk_put(key: str, scan: dict) -> None:
    folder = _disk_dir()
    if folder is None:
        return
    try:
        target = folder / f"catalogue-{key[:24]}.json"
        tmp = target.with_suffix(f".{os.getpid()}.tmp")
        tmp.write_text(json.dumps(scan), encoding="utf-8")
        tmp.replace(target)
    except OSError:
        pass


def _load_all(cdir: Path, files: list[Path], blobs: dict[Path, bytes]) -> dict:
    entries: list[dict] = []
    broken: list[dict] = []
    if not files:
        return {"entries": entries, "broken": broken}
    try:
        got = _run([{"op": "meta", "file": str(f.resolve())} for f in files])
    except ComponentError as exc:
        return {"entries": [], "broken": [{"id": f.stem, "path": str(f.relative_to(cdir)), "error": str(exc)} for f in files]}
    seen: set[str] = set()
    for f, res in zip(files, got):
        rel = str(f.relative_to(cdir))
        if not res.get("ok"):
            broken.append({"id": f.stem, "path": rel, "error": f"it does not load: {res.get('error')}"})
            continue
        if res.get("validate") != "function" or res.get("draw") != "function":
            broken.append({"id": f.stem, "path": rel, "error": "it must export validate and draw"})
            continue
        entry, why = _entry(f, res.get("meta"), cdir)
        if entry is None:
            broken.append({"id": f.stem, "path": rel, "error": why})
        elif entry["id"] in seen:
            broken.append({"id": f.stem, "path": rel, "error": f"id {entry['id']} is used by another component"})
        else:
            seen.add(entry["id"])
            entry["sha"] = hashlib.sha256(blobs[f]).hexdigest()
            entries.append(entry)
    entries.sort(key=lambda e: (e["subject"], e["id"]))
    return {"entries": entries, "broken": broken}


def catalogue(*, subjects: Iterable[str] | None = None, classes: Iterable[int] | None = SCOPE_CLASSES) -> list[dict]:
    """Every loadable component: id, title, subject, size, classes, chapters, params, parts, states, anchors, example.

    ``classes`` keeps the components that serve one of those classes (``None``: no filter; a component whose class is
    unknown is then listed, otherwise it is not); ``subjects`` keeps those subjects. A file that fails to load is not
    here: see :func:`broken`. Returns copies, safe to change.
    """
    wanted_subjects = {str(s).lower() for s in subjects} if subjects is not None else None
    wanted_classes = {int(c) for c in classes} if classes is not None else None
    out = []
    for entry in _scan()["entries"]:
        if wanted_subjects is not None and entry["subject"] not in wanted_subjects:
            continue
        if wanted_classes is not None and not (set(entry["classes"]) & wanted_classes):
            continue
        out.append(json.loads(json.dumps(entry)))
    return out


def broken() -> list[dict]:
    """Files that did not load or break the contract: ``[{id, path, error}]``."""
    return json.loads(json.dumps(_scan()["broken"]))


def ids(*, classes: Iterable[int] | None = SCOPE_CLASSES) -> list[str]:
    return [e["id"] for e in catalogue(classes=classes)]


def get(component_id: Any, *, in_scope: bool = False) -> dict:
    """The catalogue entry for an id; ``ComponentError`` (listing the known ids) when there is none."""
    cid = str(component_id or "")
    for entry in _scan()["entries"]:
        if entry["id"] == cid:
            if in_scope and entry["classes"] and not set(entry["classes"]) & set(SCOPE_CLASSES):
                raise ComponentError(f"component {cid} is for Class {', '.join(map(str, entry['classes']))} only; lessons here "
                                     f"are for Classes {SCOPE_CLASSES[0]} to {SCOPE_CLASSES[-1]}")
            return json.loads(json.dumps(entry))
    known = [e["id"] for e in _scan()["entries"]]
    shown = ", ".join(known[:25]) + (f" (and {len(known) - 25} more)" if len(known) > 25 else "")
    raise ComponentError(f"there is no component {cid!r}" + (f"; the components are: {shown}" if known else ": none are available"))


# ── checking parameters ──────────────────────────────────────────────────────────────────────────────────────────

def _is_number(x: Any) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def _g(x: Any) -> str:
    return f"{x:g}" if _is_number(x) else json.dumps(x)


def merged_params(entry: dict, params: dict | None) -> dict:
    """The defaults of the component with ``params`` laid over them (``draw`` does not do this itself)."""
    out = {p["name"]: p["default"] for p in entry["params"]}
    out.update(params or {})
    return out


def check_params(entry: dict, params: Any, state: Any = None) -> list[str]:
    """Problems in plain words with ``params`` and ``state`` against the component's ``meta``. [] when none.

    Covers what the component's own ``validate`` leaves open: an unknown key, a boolean where a number belongs, a
    number that is not finite, an option not listed, a value outside min/max, a state key or value the component does
    not have, and a number typed into a text parameter.
    """
    problems: list[str] = []
    if params is None:
        params = {}
    if not isinstance(params, dict):
        return [f"params must be an object of {entry['id']}'s parameters, not {type(params).__name__}"]
    by_name = {p["name"]: p for p in entry["params"]}
    for key, value in params.items():
        spec = by_name.get(key)
        if spec is None:
            problems.append(f"{key} is not a parameter of {entry['id']} (it has: {', '.join(by_name) or 'none'})")
            continue
        kind = spec["type"]
        if kind in ("number", "integer", "int"):
            if not _is_number(value):
                problems.append(f"{key} must be a number (you gave {json.dumps(value)[:40]})")
                continue
            if kind != "number" and float(value) != int(value):
                problems.append(f"{key} must be a whole number (you gave {_g(value)})")
            lo, hi = spec.get("min"), spec.get("max")
            if (lo is not None and value < lo) or (hi is not None and value > hi):
                span = (f"from {_g(lo)} to {_g(hi)}" if lo is not None and hi is not None
                        else f"at least {_g(lo)}" if lo is not None else f"at most {_g(hi)}")
                problems.append(f"{key} must be {span} (you gave {_g(value)})")
        elif kind == "enum":
            options = spec.get("options") or []
            if value not in options or isinstance(value, bool):
                problems.append(f"{key} must be one of: {', '.join(str(o) for o in options)} (you gave {json.dumps(value)[:40]})")
        elif kind == "boolean":
            if not isinstance(value, bool):
                problems.append(f"{key} must be true or false (you gave {json.dumps(value)[:40]})")
        elif kind == "string":
            if not isinstance(value, str):
                problems.append(f"{key} must be words (you gave {json.dumps(value)[:40]})")
            elif len(value) > 80 or any(c in value for c in "<>&\n\r"):
                problems.append(f"{key} must be short plain words (at most 80 characters, no < > &)")
            elif re.search(r"\d", value) and value != spec["default"]:
                problems.append(f"{key} must be words with no digits: a number on the picture has to come from a number "
                                "parameter, not from words you type")
        elif not isinstance(value, (str, int, float, bool)) or (isinstance(value, float) and not math.isfinite(value)):
            problems.append(f"{key} must be a plain value")
    if state is not None:
        problems += check_state(entry, state)
    return problems


def check_state(entry: dict, state: Any) -> list[str]:
    """Problems with a state, in plain words. A named state takes one of its listed names; a number state takes a finite
    number from its min to its max (a name or a boolean is refused); a key the component does not have is refused.
    Several keys may be given at once; where a number state and a named preset both speak, the number wins (README)."""
    if not isinstance(state, dict):
        first = next(iter(entry["states"]), "name")
        return [f"state must be an object such as {{'{first}': {'0.5' if is_knob(entry['states'].get(first)) else repr('value')}}}"]
    problems: list[str] = []
    for key, value in state.items():
        spec = entry["states"].get(key)
        if spec is None:
            have = ", ".join(entry["states"]) or "none"
            problems.append(f"{key} is not a state of {entry['id']} (it has: {have})")
        elif is_knob(spec):
            if not _is_number(value):
                problems.append(f"state {key} must be a number from {_g(spec['min'])} to {_g(spec['max'])} "
                                f"(you gave {json.dumps(value)[:40]})")
            elif value < spec["min"] or value > spec["max"]:
                problems.append(f"state {key} must be from {_g(spec['min'])} to {_g(spec['max'])} (you gave {_g(value)})")
        elif value not in spec or (isinstance(value, bool) and not any(isinstance(v, bool) for v in spec)):
            problems.append(f"state {key} must be one of: {', '.join(str(v) for v in spec)} (you gave {json.dumps(value)[:40]})")
    return problems


def filled_state(entry: dict, state: dict | None) -> dict:
    """The state ``draw`` is given: ``state`` with the default of every number state it does not set.

    Two exceptions, both so that the component's own behaviour is not overruled by a default nobody asked for:

    * an empty state stays empty: the component draws its own default picture (measured on the 2026-11 library, filling
      every default changed the picture of four components, such as ``number_line``, whose unset picture is the finished
      hops while its ``hops_done`` default is 0);
    * when the state names a preset (a list state), the number states it does not set are left out and the component
      works them out from the preset. A number the caller sets always wins over a preset (README).
    """
    st = dict(state or {})
    if not st or any(isinstance(entry["states"].get(k), list) for k in st):
        return st
    for key, spec in entry["states"].items():
        if is_knob(spec) and key not in st:
            st[key] = spec["default"]
    return st


# ── drawing ──────────────────────────────────────────────────────────────────────────────────────────────────────

_DRAWN: dict[str, dict] = {}                 # key -> result, or {"problems": [...]}
_TRUSTED: set[str] = set()                   # component sha values already drawn twice with the same answer
_DRAW_LOCK = threading.Lock()


def _key(entry: dict, merged: dict, state: dict) -> str:
    blob = json.dumps([entry["sha"], merged, state], sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(blob.encode()).hexdigest()


def _plan(component_id: str, params: Any, state: Any) -> tuple[dict, dict, dict, str, list[str]]:
    """(entry, merged params, state, cache key, problems found before Node is asked)."""
    entry = get(component_id)
    problems = check_params(entry, params, state)
    merged = merged_params(entry, params if isinstance(params, dict) else {})
    st = filled_state(entry, state if isinstance(state, dict) else {}) if not problems else (dict(state) if isinstance(state, dict) else {})
    return entry, merged, st, _key(entry, merged, st), problems


def prefetch(specs: Iterable[tuple[str, dict | None, dict | None]], *, quiet: bool = True) -> None:
    """Validate and draw every ``(id, params, state)`` not seen yet in ONE Node process. Never raises unless ``quiet`` is
    False and Node itself cannot be run."""
    jobs: list[dict] = []
    order: list[tuple[str, dict, str, bool]] = []
    cdir = components_dir()
    seen: set[str] = set()
    try:
        for cid, params, state in specs:
            try:
                entry, merged, st, key, problems = _plan(cid, params, state)
            except ComponentError:
                continue
            if problems or key in _DRAWN or key in seen:
                continue
            seen.add(key)
            file = str((cdir / entry["path"]).resolve())
            twice = entry["sha"] not in _TRUSTED
            jobs += [{"op": "validate", "file": file, "params": merged},
                     {"op": "draw", "file": file, "params": merged, "state": st, "twice": twice}]
            order.append((key, entry, merged, twice))
        if not jobs:
            return
        got = _run(jobs)
    except ComponentError:
        if quiet:
            return
        raise
    with _DRAW_LOCK:
        for i, (key, entry, merged, twice) in enumerate(order):
            v, d = got[2 * i], got[2 * i + 1]
            _DRAWN[key] = _result(entry, merged, v, d, twice)


def _result(entry: dict, merged: dict, v: dict, d: dict, twice: bool) -> dict:
    """The cached outcome of one validate+draw pair: ``{"problems": [...]}`` or the drawing."""
    cid = entry["id"]
    if not v.get("ok"):
        return {"problems": [f"{cid}'s own validate failed: {v.get('error')}"]}
    if v.get("problems"):
        return {"problems": [str(p) for p in v["problems"]]}
    if not d.get("ok"):
        return {"problems": [f"{cid} could not be drawn: {d.get('error')}"]}
    if twice and not d.get("deterministic"):
        return {"problems": [f"{cid} draws a different picture each time for the same input (the contract needs the "
                             "same output): it cannot be used"]}
    if twice:
        _TRUSTED.add(entry["sha"])
    shaped = _shape(entry, d.get("draw"))
    if isinstance(shaped, str):
        return {"problems": [shaped]}
    shaped["params"] = merged
    return shaped


def _shape(entry: dict, raw: Any) -> dict | str:
    """The drawing in a fixed shape, or one sentence on what is wrong with it."""
    if not isinstance(raw, dict) or not isinstance(raw.get("parts"), dict):
        return "draw did not return {parts, anchors, labels}"
    parts = []
    for name in entry["parts"]:
        svg = raw["parts"].get(name)
        if not isinstance(svg, str):
            return f"draw has no part {name!r}"
        if len(svg) > MAX_PART_SVG:
            return f"part {name!r} is far too large"
        if re.search(r"\bNaN\b|undefined|Infinity", svg):
            return f"part {name!r} has NaN or undefined in it"
        for tag in re.findall(r"<\s*([a-zA-Z][\w:-]*)", svg):
            if tag not in SVG_TAGS:
                return f"part {name!r} uses <{tag}>, which is not allowed"
        if _BANNED.search(re.sub(r"stroke-linecap|stroke-linejoin|font-family|text-anchor", "", svg)):
            return f"part {name!r} uses filters, gradients, masks, images, styles or scripts"
        parts.append((name, svg))
    if not parts[0][1].strip():
        return f"the first part {parts[0][0]!r} draws nothing: it must be the outline"
    anchors = {}
    raw_anchors = raw.get("anchors") if isinstance(raw.get("anchors"), dict) else {}
    for name in entry["anchors"]:
        at = raw_anchors.get(name)
        if not (isinstance(at, list) and len(at) == 2 and all(_is_number(x) for x in at)):
            return f"anchor {name!r} is missing or not [x, y]"
        anchors[name] = [float(at[0]), float(at[1])]
    labels = []
    for lab in raw.get("labels") or []:
        if not (isinstance(lab, dict) and lab.get("part") in entry["parts"] and isinstance(lab.get("text"), str)
                and lab.get("side") in _SIDES and isinstance(lab.get("at"), list) and len(lab["at"]) == 2
                and all(_is_number(x) for x in lab["at"])):
            return f"a label is malformed: {json.dumps(lab)[:80]}"
        if re.search(r"undefined|NaN", lab["text"]):
            return f"a label says {lab['text']!r}"
        labels.append({"part": lab["part"], "text": lab["text"], "at": [float(lab["at"][0]), float(lab["at"][1])],
                       "side": lab["side"]})
    return {"id": entry["id"], "size": list(entry["size"]), "parts": parts, "anchors": anchors, "labels": labels}


def validate(component_id: str, params: dict | None = None, state: dict | None = None) -> list[str]:
    """Problems with these parameters and this state, in plain words; [] means the component can be drawn.

    Python's checks (keys, types, options, ranges, states) come first, then the defaults are filled in and the
    component's own ``validate`` runs. Raises ``ComponentError`` only for an unknown component or no Node.
    """
    entry, merged, st, key, problems = _plan(component_id, params, state)
    if problems:
        return problems
    return _outcome(entry, merged, st, key).get("problems", [])


def _outcome(entry: dict, merged: dict, state: dict, key: str) -> dict:
    with _DRAW_LOCK:
        held = _DRAWN.get(key)
    if held is not None:
        return held
    prefetch([(entry["id"], merged, state)], quiet=False)
    with _DRAW_LOCK:
        held = _DRAWN.get(key)
    if held is None:
        raise ComponentError(f"component {entry['id']} could not be run")
    return held


def draw(component_id: str, params: dict | None = None, state: dict | None = None) -> dict:
    """The component drawn: ``{id, size, params (merged), state, parts [(name, svg)] in meta.parts order, anchors,
    labels, numbers, facts}``. ``ComponentError`` with the problem list when the parameters are not drawable.

    ``numbers`` are the values the picture shows (numeric parameters, numbers in the labels); ``facts`` are the
    strings code allows on screen (label texts and parameter values).
    """
    entry, merged, st, key, problems = _plan(component_id, params, state)
    if problems:
        raise ComponentError(f"component {entry['id']}: " + "; ".join(problems))
    result = _outcome(entry, merged, st, key)
    if result.get("problems"):
        raise ComponentError(f"component {entry['id']}: " + "; ".join(result["problems"]))
    out = dict(result)
    out["state"] = dict(st)
    nums = {float(v) for v in merged.values() if _is_number(v)}
    for lab in out["labels"]:
        nums |= {float(m) for m in _LABEL_NUMBER.findall(lab["text"])}
    out["numbers"] = sorted(nums)
    out["facts"] = [lab["text"] for lab in out["labels"]] + [f"{k} {_g(v) if _is_number(v) else v}" for k, v in merged.items()]
    return out


def empty_parts(drawn: dict) -> list[str]:
    """Names of the parts that draw nothing in this state (a part may be '' in some states). A part with no shapes but
    a label (number_line's ``result`` is only its sum "0 + 3 + 3 = 6") draws something: the label is part of it."""
    labelled = {lab.get("part") for lab in drawn.get("labels") or []}
    return [name for name, svg in drawn["parts"] if not svg.strip() and name not in labelled]


# ── between two drawings: which numbers may be moved smoothly, and whether a straight morph is the truth ────────────────

#: Number knobs (a ``params`` name or a ``state`` slider) that may be moved smoothly from one value to another between two
#: beats (``component_figure.ComponentFigure.change_from``). Component id -> knob names. This is the safety belt: a knob that
#: is not listed is never morphed (a rotation, a periodic knob, a preset, an integer or structural parameter). Being listed
#: is not enough: ``morph_plan`` then MEASURES the change, because a listed knob can still be piecewise (the cell's
#: ``water_balance`` is linear on each side of 0 and kinks at 0) or curved (a pendulum's ``time_s``).
#: ``sound_wave.time_ms`` (the plan's list) is NOT here: the wave is a polyline that translates, and the straight morph of
#: two shifted waves is 45 svg pixels off the wave drawn half way between (``docs/engine/kits.md``).
TWEEN_KNOBS: dict[str, tuple[str, ...]] = {
    "cell": ("water_balance",), "nephron": ("extra_water",), "clamp_stand": ("jaw_open",), "leaf_section": ("opening",),
    "burette": ("added_ml",), "food_chain": ("energy_kept",), "simple_pendulum": ("time_s",),
    "solid_nets": ("unfold",),
}
#: The probe grid is ``2 ** KEY_DEPTH`` steps wide, every point drawn in one batch (at most ``2 ** KEY_DEPTH + 1`` draws).
KEY_DEPTH = 3
KEY_TOL_PX = 1.0                # svg pixels: the straight morph may be this far from the real drawing (about 0.015 scene units)

_HEX = re.compile(r"#[0-9A-Fa-f]{3,8}\b")
_SVG_NUMBER = re.compile(r"-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?")


def svg_numbers(svg: str) -> tuple[str, list[float]]:
    """(the markup with every number replaced by ``#``, the numbers in order): two drawings whose first parts are equal
    have the same shapes and differ only in where they are, so one can be morphed into the other. Colours are not numbers."""
    flat = _HEX.sub("#c", svg)
    return _SVG_NUMBER.sub("#", flat), [float(x) for x in _SVG_NUMBER.findall(flat)]


def knob_changes(entry: dict, a: dict, b: dict) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    """``(moving, other)``: the keys that differ between two ``{params, state}`` of one component, split into number knobs
    that could be moved smoothly (a number ``params`` entry, a number-slider state, a number on both sides) and every
    other change (a name, a boolean, a text, a number that is set on one side only). Defaults are filled first."""
    pa, sa = merged_params(entry, a.get("params")), filled_state(entry, a.get("state") or {})
    pb, sb = merged_params(entry, b.get("params")), filled_state(entry, b.get("state") or {})
    kinds = {p["name"]: p["type"] for p in entry["params"]}
    moving: list[tuple[str, str]] = []
    other: list[tuple[str, str]] = []
    for name in sorted(set(pa) | set(pb)):
        if pa.get(name) != pb.get(name):
            both = _num(pa.get(name)) and _num(pb.get(name))
            (moving if kinds.get(name) == "number" and both else other).append(("params", name))
    for name in sorted(set(sa) | set(sb)):
        if sa.get(name) != sb.get(name):
            both = _num(sa.get(name)) and _num(sb.get(name))
            (moving if is_knob(entry["states"].get(name)) and both else other).append(("state", name))
    return moving, other


def tweenable(entry: dict, a: dict, b: dict) -> list[tuple[str, str]]:
    """The knobs that move between two ``{params, state}``, when the change is ONLY listed number knobs (``TWEEN_KNOBS``);
    ``[]`` otherwise: a preset, an integer or structural parameter, a number set on one side only, a rotation, a periodic
    knob, anything not listed, or no change at all."""
    moving, other = knob_changes(entry, a, b)
    allowed = set(TWEEN_KNOBS.get(entry["id"], ()))
    return moving if moving and not other and {name for _, name in moving} <= allowed else []


def _station(entry: dict, a: dict, b: dict, moving: list[tuple[str, str]], t: float) -> dict:
    """The ``{params, state}`` a fraction ``t`` of the way from ``a`` to ``b``: only the moving knobs are interpolated."""
    params, state = merged_params(entry, a.get("params")), filled_state(entry, a.get("state") or {})
    pb, sb = merged_params(entry, b.get("params")), filled_state(entry, b.get("state") or {})
    for kind, name in moving:
        here, there = (params, pb) if kind == "params" else (state, sb)
        lo, hi = here[name], there[name]
        value = round(lo + (hi - lo) * t, 6)
        here[name] = int(value) if value == int(value) and isinstance(lo, int) and isinstance(hi, int) else value
    return {"params": params, "state": state}


def deviation_px(a: dict, b: dict, mid: dict, t: float, parts: set[str]) -> float:
    """How far (svg pixels, the largest single number) the drawing ``mid`` is from the straight morph of ``a`` into ``b`` at
    ``t``, over the parts named in ``parts``: every number of the part's markup is compared with the same number interpolated
    between ``a`` and ``b``. ``inf`` when a named part has a different shape in the three drawings."""
    worst = 0.0
    for (name, sa), (_, sb), (_, sm) in zip(a["parts"], b["parts"], mid["parts"]):
        if name not in parts:
            continue
        ka, xa = svg_numbers(sa)
        kb, xb = svg_numbers(sb)
        km, xm = svg_numbers(sm)
        if not (ka == kb == km):
            return math.inf
        worst = max([worst] + [abs(m - ((1 - t) * p + t * q)) for p, q, m in zip(xa, xb, xm)])
    return worst


def morph_plan(component_id: str, a: dict, b: dict, *, tol_px: float = KEY_TOL_PX, max_depth: int = KEY_DEPTH) -> dict | None:
    """Whether and how drawing ``a`` can be morphed into drawing ``b`` (each ``{params, state}`` of one component), measured.

    ``None``: do not morph (not only listed number knobs, a draw failed, nothing moves). Otherwise
    ``{"stations": [{t, params, state}, ...], "stable": [part names]}``: ``stations`` are drawings strictly between
    0 and 1 that the morph must pass through, ``[]`` when the straight morph is within ``tol_px`` of the truth everywhere
    it was probed; ``stable`` are the parts whose markup has the same shape at every probe (a speed arrow that is empty
    at rest is not: the figure cross-fades such a part, it never morphs it).

    The drawing at ``t = j / 2**max_depth`` is made for every grid point in ONE batch (at most ``2**max_depth + 1`` draws,
    far inside the Node timeout). The grid is cut where the straight morph between two kept stations is farther than
    ``tol_px`` from the drawing at ANY grid point between them: several probes, never the midpoint alone (a symmetric
    curve, such as a sine over a symmetric interval, passes a midpoint-only test).
    """
    try:
        entry = get(component_id)
    except ComponentError:
        return None
    moving = tweenable(entry, a, b)
    if not moving or max_depth < 1:
        return None
    steps = 2 ** max_depth
    grid = [_station(entry, a, b, moving, j / steps) for j in range(steps + 1)]
    specs = [(entry["id"], g["params"], g["state"]) for g in grid]
    prefetch(specs)
    try:
        drawn = [draw(*spec) for spec in specs]
    except ComponentError:
        return None
    shapes = [[svg_numbers(svg)[0] for _, svg in d["parts"]] for d in drawn]
    stable = {name for k, (name, _) in enumerate(drawn[0]["parts"])
              if all(row[k] == shapes[0][k] for row in shapes) and drawn[0]["parts"][k][1].strip()}

    def cut(i: int, j: int) -> list[int]:
        if j - i < 2:
            return []
        worst = max(deviation_px(drawn[i], drawn[j], drawn[p], (p - i) / (j - i), stable) for p in range(i + 1, j))
        if worst <= tol_px:
            return []
        mid = (i + j) // 2
        return cut(i, mid) + [mid] + cut(mid, j)

    return {"stations": [{"t": j / steps, **grid[j]} for j in cut(0, steps)], "stable": sorted(stable)}


def keyframes(component_id: str, a: dict, b: dict, *, tol_px: float = KEY_TOL_PX, max_depth: int = KEY_DEPTH) -> list[dict]:
    """The stations a knob needs between two drawings: ``[{t, params, state}]`` strictly between 0 and 1, in order, each the
    component drawn at that value; ``[]`` when the straight morph is right (a linear knob: no extra draw is kept) or when the
    change is not one that may be morphed at all (``morph_plan`` is ``None``: a preset, an integer or structural parameter,
    an unlisted knob; nothing is drawn for it). See ``morph_plan`` for how they are found."""
    plan = morph_plan(component_id, a, b, tol_px=tol_px, max_depth=max_depth)
    return list(plan["stations"]) if plan else []


# ── situations: ready-made beat plans ────────────────────────────────────────────────────────────────────────────

def get_situation(entry: dict, name: Any) -> dict:
    """The situation ``name`` of a catalogue entry, or ``ComponentError`` listing the ones it has."""
    for sit in entry.get("situations") or []:
        if sit["name"] == str(name):
            return sit
    have = ", ".join(s["name"] for s in entry.get("situations") or []) or "none"
    raise ComponentError(f"component {entry['id']} has no situation {str(name)[:40]!r} (it has: {have})")


def situation_plan(component_id: str, situation_name: str) -> list[dict]:
    """The steps of a situation with everything worked out and checked: ``[{params, state, show, say, empty}]``.

    ``params`` are the component's example params with the situation's (and any earlier step's) laid over them, as the
    library's own checker draws it; ``state`` is every state set so far (a step keeps what earlier steps set); ``show`` the
    parts on screen; ``say`` the authors' own line; ``empty`` the parts that draw nothing at this step. Every step is
    checked here (a param or state outside its min/max, an unknown key or part, a missing ``say`` line, then the
    component's own ``validate`` and a drawing); ``ComponentError`` says which step and why. Nothing here is written by a model.
    """
    entry = get(component_id, in_scope=True)
    sit = get_situation(entry, situation_name)
    params = {**entry["example"], **sit["params"]}
    state: dict = {}
    frames: list[dict] = []
    for k, step in enumerate(sit["steps"], start=1):
        params = {**params, **(step.get("params") or {})}
        state = {**state, **step["state"]}
        problems = check_params(entry, params, state)
        problems += [f"shows {p!r}, which is not a part (parts: {', '.join(entry['parts'])})" for p in step["show"]
                     if p not in entry["parts"]]
        if not step["say"].strip():
            problems.append("has no say line")
        if problems:
            raise ComponentError(f"component {entry['id']} situation {sit['name']} step {k}: " + "; ".join(problems))
        frames.append({"params": dict(params), "state": dict(state), "show": list(step["show"]), "say": step["say"].strip()})
    prefetch([(entry["id"], f["params"], f["state"]) for f in frames])
    for k, frame in enumerate(frames, start=1):
        try:
            frame["empty"] = empty_parts(draw(entry["id"], frame["params"], frame["state"]))
        except ComponentError as exc:
            raise ComponentError(f"situation {sit['name']} step {k}: {exc}") from exc
    return frames


# ── words for the writer ─────────────────────────────────────────────────────────────────────────────────────────

def _param_line(p: dict) -> str:
    kind = p["type"]
    if kind in ("number", "integer", "int"):
        span = f"{_g(p['min'])} to {_g(p['max'])}" if "min" in p and "max" in p else f"min {_g(p['min'])}" if "min" in p \
            else f"max {_g(p['max'])}" if "max" in p else "any number"
        what = f"number {span}"
    elif kind == "enum":
        what = "one of " + " | ".join(json.dumps(o) for o in p.get("options") or [])
    elif kind == "boolean":
        what = "true | false"
    else:
        what = "words only, no digits" if kind == "string" else kind or "value"
    return f"{p['name']} ({what}; default {json.dumps(p['default'])}): {p['say']}".rstrip(": ")


def sheet(entry: dict) -> str:
    """A component for the writer: id, what it is for, every parameter, the parts in the order to name them, states."""
    cls = ", ".join(map(str, entry["classes"])) or "unknown"
    lines = [f'  "{entry["id"]}" - {entry["title"]} ({entry["subject"]}, Class {cls})']
    chapters = "; ".join(f"Class {c['cls']} Ch {c['ch']} {c['title']}" for c in entry["chapters"] if c["cls"] in SCOPE_CLASSES) \
        or "; ".join(n[:90] for n in entry["ncert"] if classes_of(n) & set(SCOPE_CLASSES))[:200]
    if chapters:
        lines.append(f"    for: {chapters}")
    lines += [f"    param {_param_line(p)}" for p in entry["params"]]
    lines.append("    parts, in the order to name them (each step's focus): " + ", ".join(entry["parts"])
                 + " (the first is the outline and is there from the start)")
    for key, values in entry["states"].items():
        if is_knob(values):
            lines.append(f"    state {key} (number {_g(values['min'])} to {_g(values['max'])}; default {_g(values['default'])}; "
                         f"when you give it, it wins over any named state): {values['say']}".rstrip(": "))
        else:
            lines.append(f"    state {key}: " + " | ".join(json.dumps(v) for v in values))
    if entry.get("situations"):
        lines.append("    ready-made set-ups (checked by the library's authors; code can start a lesson from one): "
                     + "; ".join(f"{sit['name']} - {sit['title']}" for sit in entry["situations"]))
    return "\n".join(lines)


def index_line(entry: dict) -> str:
    return f'  {entry["id"]} ({entry["subject"]}, Class {",".join(map(str, entry["classes"])) or "?"}): {entry["title"]}'
