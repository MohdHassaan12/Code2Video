"""LESSONFORGE_NO_DOTENV keeps ``.env`` out of a process, and a free film hides every paid key, from one tuple."""
import os
import subprocess
import sys

import pytest

from lessonforge import env
from lessonforge.harness import workbench as W


@pytest.mark.parametrize("value,off", [("1", True), ("true", True), ("YES", True), (" on ", True), ("0", False),
                                       ("", False), ("no", False), ("false", False)])
def test_the_switch_reads_one_true_and_nothing_else(monkeypatch, value, off):
    monkeypatch.setenv("LESSONFORGE_NO_DOTENV", value)
    assert env.dotenv_disabled() is off


def test_by_default_dotenv_still_loads(monkeypatch):
    monkeypatch.delenv("LESSONFORGE_NO_DOTENV", raising=False)
    assert env.dotenv_disabled() is False


def _cli_loads_dotenv(monkeypatch, flag):
    import dotenv

    from lessonforge import cli
    calls = []
    monkeypatch.setattr(dotenv, "load_dotenv", lambda *a, **k: calls.append(1) or False)
    if flag is None:
        monkeypatch.delenv("LESSONFORGE_NO_DOTENV", raising=False)
    else:
        monkeypatch.setenv("LESSONFORGE_NO_DOTENV", flag)
    with pytest.raises(SystemExit):
        cli.main(["--help"])
    return len(calls)


def test_the_cli_loads_dotenv_unless_told_not_to(monkeypatch):
    assert _cli_loads_dotenv(monkeypatch, None) == 1
    assert _cli_loads_dotenv(monkeypatch, "1") == 0


def _engine_dotenv_calls(flag):
    code = (f"import sys; sys.path[:0] = {sys.path!r}; import dotenv; calls = []; "
            "dotenv.load_dotenv = lambda *a, **k: calls.append(1) or False; import lessonforge.engine; print(len(calls))")
    child = {k: v for k, v in os.environ.items() if k != "LESSONFORGE_NO_DOTENV"}
    if flag:
        child["LESSONFORGE_NO_DOTENV"] = flag
    done = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=300, env=child)
    assert done.returncode == 0, done.stderr[-600:]
    return int(done.stdout.strip().splitlines()[-1])


def test_importing_the_engine_loads_dotenv_unless_told_not_to():
    assert _engine_dotenv_calls(None) == 1
    assert _engine_dotenv_calls("1") == 0


def test_the_paid_keys_are_one_tuple_that_names_the_usual_providers():
    for name in ("OPENROUTER_API_KEY", "ANTHROPIC_API_KEY", "SARVAM_AI_KEY", "GEMINI_API_KEY", "GROQ_API_KEY",
                 "TAVILY_API_KEY", "DIAGRAM_API_KEY", "INDIC_TTS_KEY", "OPENAI_API_KEY"):
        assert name in env.PAID_KEYS
    assert len(set(env.PAID_KEYS)) == len(env.PAID_KEYS)


def test_a_free_film_hides_every_paid_key_and_puts_them_back(monkeypatch, tmp_path):
    monkeypatch.setenv("LESSONFORGE_HOME", str(tmp_path))
    for name in env.PAID_KEYS:
        monkeypatch.setenv(name, "present-" + name)
    seen = {}

    def spy(lesson_id):
        seen["during"] = {k for k in env.PAID_KEYS if os.environ.get(k)}
        raise W.WorkbenchError("stop here: no lesson")
    monkeypatch.setattr(W, "_folder", spy)
    with pytest.raises(W.WorkbenchError, match="stop here"):
        W.film("nothing")
    assert seen["during"] == set(), "no paid key may be visible while a free film runs"
    assert all(os.environ.get(k) == "present-" + k for k in env.PAID_KEYS), "the keys are back afterwards"


def test_a_paid_film_leaves_the_keys_alone(monkeypatch, tmp_path):
    monkeypatch.setenv("LESSONFORGE_HOME", str(tmp_path))
    monkeypatch.setenv("OPENROUTER_API_KEY", "present")
    seen = {}

    def spy(lesson_id):
        seen["during"] = os.environ.get("OPENROUTER_API_KEY")
        raise W.WorkbenchError("stop here")
    monkeypatch.setattr(W, "_folder", spy)
    with pytest.raises(W.WorkbenchError):
        W.film("nothing", paid_checks=True)
    assert seen["during"] == "present"


def test_a_film_with_no_keys_set_runs_straight_through(monkeypatch, tmp_path):
    monkeypatch.setenv("LESSONFORGE_HOME", str(tmp_path))
    for name in env.PAID_KEYS:
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(W.WorkbenchError, match="no lesson"):
        W.film("nothing")
