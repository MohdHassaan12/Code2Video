"""Run the engine's script-style acceptance harnesses and summarise.

Each ``tests/engine/test_*.py`` is a standalone script (PASS/FAIL lines, exit code
0/1) — several do real manim renders with the LLM stubbed. They are run as
subprocesses against a throwaway workspace so no test writes into your real one.

    python tests/run_engine_checks.py            # everything
    python tests/run_engine_checks.py --fast     # skip the real-render harnesses
    python tests/run_engine_checks.py theme ir   # only scripts whose name matches
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
# Harnesses that launch manim (slow). Everything else is pure Python.
RENDERS = {"test_overlap_probe", "test_layout_safety", "test_sustained_motion",
           "test_simulation", "test_tts_resilience", "test_tts_shared_cache"}


def main(argv: list[str]) -> int:
    fast = "--fast" in argv
    filters = [a for a in argv if not a.startswith("--")]
    scripts = sorted((HERE / "engine").glob("test_*.py"))
    if fast:
        scripts = [p for p in scripts if p.stem not in RENDERS]
    if filters:
        scripts = [p for p in scripts if any(f in p.stem for f in filters)]

    env = dict(os.environ)
    workspace = tempfile.mkdtemp(prefix="lessonforge_tests_")
    env.setdefault("LESSONFORGE_HOME", workspace)
    # Never let a harness reach a metered provider by accident.
    for key in ("GEMINI_API_KEY", "OPENROUTER_API_KEY", "GROQ_API_KEY", "SARVAM_API_KEY"):
        env.pop(key, None)

    failed = []
    for script in scripts:
        t0 = time.time()
        proc = subprocess.run([sys.executable, str(script)], capture_output=True, text=True,
                              env=env, cwd=workspace, timeout=1800)
        out = (proc.stdout or "") + (proc.stderr or "")
        tally = re.findall(r"(\d+)\s*/\s*(\d+)\s+(?:checks\s+)?passed", out)
        note = f"{tally[-1][0]}/{tally[-1][1]}" if tally else ""
        status = "ok  " if proc.returncode == 0 else "FAIL"
        print(f"{status} {script.stem:28s} {note:>9s}  {time.time() - t0:6.1f}s", flush=True)
        if proc.returncode != 0:
            failed.append(script.stem)
            tail = "\n".join(out.strip().splitlines()[-25:])
            print("     " + tail.replace("\n", "\n     "))
    print(f"\n{len(scripts) - len(failed)}/{len(scripts)} harnesses passed"
          + (f" — failed: {', '.join(failed)}" if failed else ""))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
