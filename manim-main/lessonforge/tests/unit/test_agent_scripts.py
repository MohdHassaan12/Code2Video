"""The improver's own tools (scripts/agent): a dossier from a lesson folder, and the before/after call; where its
lessons go (its own workspace, never the app's list), and that its runs get the live keys, library and ledger."""
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

LF = Path(__file__).resolve().parents[2]
AGENT = LF / "scripts" / "agent"


def _load(name):
    spec = importlib.util.spec_from_file_location(f"agent_{name}", AGENT / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _lesson(tmp_path: Path, name: str = "20261015-000000-abcdef") -> Path:
    root = tmp_path / name
    (root / "output").mkdir(parents=True)
    (root / "job.json").write_text(json.dumps({
        "job_id": root.name, "status": "done", "stage": "done", "title": "Friction", "created": 0,
        "brief": {"topic": "Friction", "language": "hinglish", "duration_minutes": 3},
        "progress": ["— script —", "[sequence] skipped: ValueError: bad plan", "done"],
        "verification": {"status": "needs_review", "critical_unresolved": 1,
                         "findings": [{"beat": "02", "severity": "major", "what": "length", "resolved": False},
                                      {"beat": "03", "severity": "minor", "what": "ok now", "resolved": True}]},
        "scenes": {"asked": 2, "made": 1},
        "continuity": {"words": 400, "target_words": 343, "warnings": []}}))
    (root / "lesson.json").write_text(json.dumps({"title": "Friction", "chapters": [
        {"beats": [{"id": "01", "narration": "a", "figure": {"kind": "scene"}}, {"id": "02", "narration": "b"}]}]}))
    (root / "output" / "final_checks.json").write_text(json.dumps({
        "status": "technical_checks_passed", "duration_seconds": 180.0, "bounds_violations": 0,
        "layout_findings": {"counted": 2, "reported_only": 1, "detail": []}, "checks": [{"name": "x", "passed": True}]}))
    return root


def test_a_dossier_reads_every_stage_and_lists_what_fell_back(tmp_path):
    s = _load("dossier").summarise(_lesson(tmp_path))
    assert s["status"] == "done" and s["script"]["beats"] == 2
    assert s["script"]["figures"] == {"scene": 1, "none": 1}
    assert s["verify"]["unresolved_findings"] == 1 and s["verify"]["critical_unresolved"] == 1
    assert s["check"]["layout_counted"] == 2 and s["check"]["failed_checks"] == []
    assert s["alarms"] == ["[sequence] skipped: ValueError: bad plan"]


def test_compare_keeps_only_what_is_better_and_never_judges_on_cost(tmp_path):
    compare = _load("compare")
    before = compare.metrics(_load("dossier").summarise(_lesson(tmp_path)), {"beats": [{"score": 1, "issues": [
        {"severity": "major"}]}, {"score": 2}]})
    better = {**before, "agent_mean_score": 2.5, "agent_major_issues": 0, "agent_bad_beats": 0, "cost_usd": 9}
    assert compare.compare(before, better)["verdict"] == "KEEP"
    assert compare.compare(before, {**better, "layout_counted": 5})["verdict"] == "REVERT"
    assert compare.compare(before, {**before, "cost_usd": 9})["verdict"] == "UNSURE"
    assert compare.compare(before, {**better, "done": 0})["verdict"] == "REVERT"


# --- the improver's own workspace -------------------------------------------------------------------------------

def _workspaces(tmp_path: Path):
    """A live workspace (the app's list) and the improver's own, linked to it the way `improve.sh setup` links it."""
    live, own = tmp_path / "live", tmp_path / "live" / "improver" / "home"
    for name in ("library", "cache", "lessons"):
        (live / name).mkdir(parents=True)
    (live / "spend.jsonl").write_text("")
    own.mkdir(parents=True)
    for name in ("library", "cache"):
        (own / name).symlink_to(live / name)
    return live, own


def test_a_job_id_is_looked_up_in_the_improvers_workspace_then_in_the_apps_list(tmp_path, monkeypatch):
    live, own = _workspaces(tmp_path)
    in_app = _lesson(live / "lessons")                                   # a tester's lesson, in the app's list
    mine = _lesson(own / "lessons", "20261015-120000-fedcba")            # one the improver made
    monkeypatch.setenv("LESSONFORGE_HOME", str(own))
    monkeypatch.setenv("IMPROVER_LIVE_HOME", str(live))
    monkeypatch.setenv("OPENROUTER_LEDGER", str(live / "spend.jsonl"))
    dossier = _load("dossier")
    assert dossier.find_lesson(in_app.name) == in_app.resolve()          # /inspect-lesson <job> still works on the app's lessons
    assert dossier.find_lesson(mine.name) == mine.resolve()
    twin = _lesson(own / "lessons")                                      # the same id in both: the improver's own wins
    assert dossier.find_lesson(twin.name) == twin.resolve()
    with pytest.raises(SystemExit, match="looked in .*home/lessons.* and .*live/lessons"):
        dossier.find_lesson("20261015-235959-000000")
    monkeypatch.delenv("IMPROVER_LIVE_HOME")                             # outside the improver: only <workspace>/lessons
    assert [where for where, _ in dossier.lesson_dirs()] == ["own"]


def test_the_survey_reads_both_workspaces_once_each_and_says_which_is_which(tmp_path, monkeypatch, capsys):
    live, own = _workspaces(tmp_path)
    _lesson(live / "lessons")
    _lesson(live / "lessons", "20261014-090000-111111")
    _lesson(own / "lessons", "20261015-120000-fedcba")
    _lesson(own / "lessons")                                             # also in the app's list: counted once, as the improver's
    monkeypatch.setenv("LESSONFORGE_HOME", str(own))
    monkeypatch.setenv("IMPROVER_LIVE_HOME", str(live))
    monkeypatch.setenv("OPENROUTER_LEDGER", str(live / "spend.jsonl"))
    assert _load("survey").main(["--json", "--grep", "bad plan"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert [(r["job"], r["where"]) for r in out["rows"]] == [
        ("20261015-120000-fedcba", "own"), ("20261015-000000-abcdef", "own"), ("20261014-090000-111111", "live")]
    assert len(out["hits"]) == 3


def _preflight(env: dict, *args) -> subprocess.CompletedProcess:
    """`preflight.sh` from this checkout with nothing of the caller's environment: no key, so nothing leaves the machine."""
    pybin = Path(env.pop("_bin"))
    pybin.mkdir(exist_ok=True)
    if not (pybin / "python").exists():
        (pybin / "python").symlink_to(sys.executable)
    full = {"PATH": f"{pybin}{os.pathsep}{os.environ.get('PATH', '/usr/bin:/bin')}", "HOME": os.environ.get("HOME", "/tmp"),
            "PYTHONPATH": str(LF / "src"), "IMPROVER_ALLOW_MAIN_CHECKOUT": "1", **env}
    return subprocess.run(["bash", str(AGENT / "preflight.sh"), *args], cwd=LF, env=full,
                          capture_output=True, text=True, timeout=120)


def test_preflight_refuses_the_live_workspace_an_unlinked_library_and_a_ledger_of_its_own(tmp_path):
    live, own = _workspaces(tmp_path)
    base = {"_bin": str(tmp_path / "bin"), "IMPROVER_LIVE_HOME": str(live)}

    out = _preflight({**base, "LESSONFORGE_HOME": str(live), "OPENROUTER_LEDGER": str(live / "spend.jsonl")}, "--check")
    assert out.returncode != 0 and "is the live workspace" in out.stdout and "app's list" in out.stdout

    alias = tmp_path / "alias"                                           # the live workspace by another name is still the live one
    alias.symlink_to(live)
    out = _preflight({**base, "LESSONFORGE_HOME": str(alias), "OPENROUTER_LEDGER": str(live / "spend.jsonl")}, "--check")
    assert out.returncode != 0 and "is the live workspace" in out.stdout

    out = _preflight({**base, "LESSONFORGE_HOME": str(own)}, "--check")  # no OPENROUTER_LEDGER: the ledger would be the home's own
    assert out.returncode != 0 and "inside the improver's workspace" in out.stdout
    out = _preflight({**base, "LESSONFORGE_HOME": str(own), "OPENROUTER_LEDGER": str(own / "spend.jsonl")}, "--check")
    assert out.returncode != 0 and "inside the improver's workspace" in out.stdout

    (own / "library").unlink()
    (own / "library").mkdir()                                            # a library of its own would pay for every card again
    out = _preflight({**base, "LESSONFORGE_HOME": str(own), "OPENROUTER_LEDGER": str(live / "spend.jsonl")}, "--check")
    assert out.returncode != 0 and "library is not a link" in out.stdout

    out = _preflight({"_bin": str(tmp_path / "bin"), "LESSONFORGE_HOME": str(own),
                      "OPENROUTER_LEDGER": str(live / "spend.jsonl")}, "--check")
    assert out.returncode != 0 and "IMPROVER_LIVE_HOME is not set" in out.stdout


def test_preflight_passes_its_own_workspace_on_the_live_ledger_and_puts_the_run_beside_the_live_one(tmp_path):
    if not shutil.which("ffmpeg"):
        pytest.skip("preflight needs ffmpeg")
    live, own = _workspaces(tmp_path)
    env = {"_bin": str(tmp_path / "bin"), "IMPROVER_LIVE_HOME": str(live), "LESSONFORGE_HOME": str(own),
           "OPENROUTER_LEDGER": str(live / "spend.jsonl")}
    out = _preflight(dict(env), "--check")
    assert out.returncode == 0, out.stdout + out.stderr
    assert f"ledger:    {live / 'spend.jsonl'}" in out.stdout and "library and cache linked" in out.stdout
    assert "OPENROUTER_API_KEY is not set" in out.stdout                 # a note, not a failure
    out = _preflight(dict(env))
    assert out.returncode == 0, out.stdout + out.stderr
    run = Path(next(line[4:] for line in out.stdout.splitlines() if line.startswith("RUN=")))
    assert run.parent == live / "improver" and (run / "spent_before.txt").is_file()
    assert not (own / "improver").exists()


_SHOW_ENV = """#!/usr/bin/env bash
echo "args: $*"
echo "LESSONFORGE_HOME=$LESSONFORGE_HOME"
echo "IMPROVER_LIVE_HOME=$IMPROVER_LIVE_HOME"
echo "OPENROUTER_LEDGER=$OPENROUTER_LEDGER"
echo "OPENROUTER_API_KEY=${OPENROUTER_API_KEY:+set}"
echo "ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY-unset}"
echo "cwd=$(pwd -P)"
"""


def test_setup_makes_its_own_workspace_and_a_run_gets_the_live_keys_without_a_key_file(tmp_path):
    """`improve.sh setup` then `shell`, on a made-up server: Claude Code and the preflight are stand-ins that print
    what they were given. Nothing outside tmp_path is read or written."""
    repo, live, wt, venv, bin_ = (tmp_path / n for n in ("repo", "live", "wt", "venv", "bin"))
    (repo / "lessonforge").mkdir(parents=True)
    keys = repo / "lessonforge" / ".env"
    keys.write_text("LESSONFORGE_HOME=/the/live/one\nOPENROUTER_API_KEY=not-a-real-key\nANTHROPIC_API_KEY=would-bill-the-api\n")
    (live / "library").mkdir(parents=True)
    (live / "spend.jsonl").write_text("")
    (wt / "lessonforge" / "scripts" / "agent").mkdir(parents=True)
    (wt / "lessonforge" / ".env").symlink_to(keys)                       # what an older setup left in the checkout
    (wt / "lessonforge" / "scripts" / "agent" / "preflight.sh").write_text(_SHOW_ENV)
    (venv / "bin").mkdir(parents=True)
    (venv / "bin" / "python").symlink_to(sys.executable)
    bin_.mkdir()
    (bin_ / "claude").write_text(_SHOW_ENV)
    (bin_ / "claude").chmod(0o755)
    conf = tmp_path / "improver.env"
    conf.write_text(f"LIVE_REPO={repo}\nWORKTREE={wt}\nVENV={venv}\nLIVE_HOME={live}\n")
    env = {"PATH": f"{bin_}{os.pathsep}{os.environ.get('PATH', '/usr/bin:/bin')}", "HOME": str(tmp_path),
           "IMPROVER_CONF": str(conf)}

    def improve(*args):
        out = subprocess.run(["bash", str(AGENT / "improve.sh"), *args], env=env, capture_output=True, text=True, timeout=60)
        assert out.returncode == 0, out.stdout + out.stderr
        return out.stdout

    said = improve("setup")
    own = live / "improver" / "home"
    for name in ("library", "cache"):                                    # shared, so nothing is paid twice
        assert (own / name).is_symlink() and (own / name).resolve() == (live / name).resolve()
    assert not (own / "models").exists()                                 # linked only when the live workspace has one
    assert not (wt / "lessonforge" / ".env").exists() and keys.is_file()  # the old link is gone, the live file untouched
    assert f"LESSONFORGE_HOME={own}" in said and f"IMPROVER_LIVE_HOME={live}" in said
    assert f"OPENROUTER_LEDGER={live / 'spend.jsonl'}" in said           # the owner's ledger and cap
    assert "OPENROUTER_API_KEY=set" in said and "ANTHROPIC_API_KEY=unset" in said   # Claude Code stays on the plan
    assert (live / "improver" / "logs").is_dir() and (live / "improver" / "inbox").is_dir()

    keys.write_text(keys.read_text() + f"OPENROUTER_LEDGER={tmp_path / 'ledger' / 'spend.jsonl'}\n")
    said = improve("shell")
    assert f"OPENROUTER_LEDGER={tmp_path / 'ledger' / 'spend.jsonl'}" in said   # a ledger the live .env names is kept
    assert f"--add-dir {live}" in said and f"cwd={(wt / 'lessonforge').resolve()}" in said
    assert f"LESSONFORGE_HOME={own}" in said and "ANTHROPIC_API_KEY=unset" in said

    (own / "cache").unlink()
    (own / "cache").mkdir()                                              # a real folder is never replaced
    assert "is a real folder" in improve("setup") and not (own / "cache").is_symlink()
