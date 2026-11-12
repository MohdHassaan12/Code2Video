"""What model-written code may never contain before it is executed — one list, two generators.

``sim_gen`` (Manim scenes) and ``asset_gen`` (matplotlib icons) both run code a model
wrote, and both refuse it first if it reaches for IO, the interpreter or another module.

The first version matched plain substrings, so ``"os."`` also matched ``ladoos.``,
``pos.``, ``photos.`` and ``videos.``. On 2026-10-08 a lesson about packing ladoos lost
seven of its eight animations to that: each was "unsafe", an unsafe reply is never
retried, and the video shipped as text on a dark screen. The lesson is the one
``_SHAPE_KINDS`` already taught for prose ("narrow" is not an arrow): **match the token,
not the letters.** Every pattern here is anchored on an identifier boundary.

What actually keeps the code contained is the import gate in each generator (only
numpy / math / manim or matplotlib may be imported) plus the subprocess it runs in;
this list is the second line, so a miss here is not an escape. A false hit, however,
silently costs a visual — keep it exact.
"""
from __future__ import annotations

import re

# Builtins that execute, read or reach around the sandbox: refused as CALLS.
_CALLS = ("eval", "exec", "compile", "open", "input", "globals", "locals", "getattr", "setattr", "delattr",
          "breakpoint", "exit", "quit")
# Modules the drawing job has no use for: refused when USED (``os.getcwd()``), not when
# the same letters end a variable name (``ladoos.add(dot)``).
_MODULES = ("os", "sys", "subprocess", "socket", "shutil", "pathlib", "requests", "urllib", "pickle", "marshal", "io",
            "codecs", "tempfile", "glob", "ctypes")
_NAMES = ("__import__", "importlib", "builtins")

_PATTERNS = (
    # A METHOD of the same name is not the builtin: a Monty Hall scene's ``door.open(...)`` was refused as
    # ``open(`` (2026-10-19). Every object with a dangerous ``.open`` needs an import, and imports are refused.
    [(re.compile(rf"(?<![\w.]){re.escape(name)}\s*\("), f"{name}(") for name in _CALLS]
    + [(re.compile(rf"(?<![\w.]){re.escape(name)}\s*\."), f"{name}.") for name in _MODULES]
    + [(re.compile(rf"(?<![A-Za-z0-9]){re.escape(name)}(?![A-Za-z0-9])"), name) for name in _NAMES]
)


def forbidden_reason(code: str, extra: tuple[str, ...] = ()) -> str | None:
    """Why this code must not be executed, or None. ``extra``: further whole names to refuse."""
    for pattern, shown in _PATTERNS:
        if pattern.search(code):
            return f"forbidden construct {shown!r}"
    for name in extra:
        if re.search(rf"(?<![\w]){re.escape(name)}(?![\w])", code):
            return f"forbidden construct {name!r}"
    return None
