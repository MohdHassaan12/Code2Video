"""One quality report per lesson, and the record of what it was made from.

    storyboard.json (gate) · sync_timeline.json · audio_report.json · final_checks.json ·
    chapter audits · vision_review.json · the reviewer's verification          ─▶ output/qa_report.json
    every stage file, with its hash and size, and the code that made it          ─▶ output/bundle.json

Each stage already writes its own checks. ``qa_report`` puts them in one list under the six questions a lesson
must answer (is it correct, does the narration hold, does the picture work, is it in step, does it teach, is the
file sound) and, for everything that is not a pass, names the beats it is in and the stage that would fix it.
That last part is the repair plan: a fault is sent to the component that made it (the script, the storyboard,
the audio, the visuals, the render), so one beat is repaired instead of the lesson being made again. The
repairs that exist today run before this report is written (the storyboard gate's anchor repair, the reviewer's
rewrites, the layout re-lay, the screen repair); the report says what is still open after them.

Nothing here changes a lesson or calls a model.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

SCHEMA = "lessonforge.qa_report/1"
BUNDLE_SCHEMA = "lessonforge.bundle/1"
AREAS = ("correctness", "narration", "visual", "sync", "pedagogy", "technical")

#: The stage files of a lesson folder, in pipeline order, with the stage each belongs to.
STAGE_FILES = [
    ("output/lesson_spec.json", "1 lesson specification"),
    ("output/teaching_plan.json", "2 teaching plan"),
    ("output/storyboard.json", "3 shared storyboard"),
    ("lesson.json", "3 shared storyboard (renderer's copy)"),
    ("timeline.json", "4A audio timing"),
    ("audio_report.json", "4A audio timing"),
    ("audio/narration.wav", "4A audio"),
    ("output/captions.vtt", "4A audio"),
    ("output/sync_timeline.json", "5 timeline"),
    ("output/final_checks.json", "6 render checks"),
    ("output/vision_review.json", "6 render checks"),
    ("output/annotations.json", "6 render"),
    ("output/interactions.json", "6 render"),
    ("output/qa_report.json", "7 quality gate"),
]


def _read(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _check(cid: str, area: str, status: str, detail: str = "", beats=(), component: str = "") -> dict:
    return {"id": cid, "area": area, "status": status, "detail": detail,
            "beats": sorted({str(b) for b in beats if b is not None}), "component": component}


_ISSUE_AREA = {"narration": "narration", "visual intent": "visual", "anchor": "sync", "anchor order": "sync",
               "anchor spoken": "sync", "events crowded": "visual", "reading time": "visual",
               "after the voice": "sync", "beats end to end": "technical", "narrated": "narration",
               "question pause": "pedagogy"}


def _from_issues(prefix: str, issues: list[dict]) -> list[dict]:
    """Gate and compiler issues, grouped by what they check: one row per kind of issue."""
    grouped: dict[tuple, list[dict]] = {}
    for issue in issues:
        grouped.setdefault((issue["check"], issue["component"]), []).append(issue)
    rows = []
    for (check, component), found in grouped.items():
        worst = "fail" if any(i["severity"] == "error" for i in found) else "warn"
        rows.append(_check(f"{prefix}: {check}", _ISSUE_AREA.get(check, "sync"), worst,
                           f"{len(found)} beat(s): {found[0]['what']}", [i["beat"] for i in found], component))
    return rows


def qa_report(root: str | Path, verification: dict | None = None) -> dict:
    """Read a built lesson folder's reports and return the single quality report (not written)."""
    root = Path(root)
    out = root / "output"
    checks: list[dict] = []
    if verification is None:
        # A report written again from the command line (``lessonforge lesson mend``) reads the reviewer's verdict
        # from the job record, so the same lesson is not judged on fewer checks the second time.
        verification = (_read(root / "job.json") or {}).get("verification") or None

    board = _read(out / "storyboard.json")
    if board is None:
        checks.append(_check("storyboard gate", "narration", "skipped", "no storyboard.json"))
    else:
        gate = board.get("gate") or {}
        checks += _from_issues("storyboard", gate.get("issues") or [])
        checks.append(_check("storyboard gate", "narration", "fail" if gate.get("errors") else "pass",
                             f"{gate.get('errors', 0)} error(s), {gate.get('warnings', 0)} warning(s); "
                             f"repaired before speech: {', '.join(gate.get('repaired') or []) or 'nothing'}",
                             component="storyboard"))

    sync = _read(out / "sync_timeline.json")
    if sync is None:
        checks.append(_check("timeline compiled", "sync", "skipped", "no sync_timeline.json"))
    else:
        checks += _from_issues("timeline", sync.get("issues") or [])
        s = sync.get("summary") or {}
        heard = s.get("steps_on_heard_words", 0)
        checks.append(_check("steps placed on heard words", "sync",
                             "pass" if not s.get("steps") or heard == s.get("steps") else "warn",
                             f"{heard} of {s.get('steps', 0)} steps timed from the words as heard; the rest are "
                             "estimates inside a measured sentence or spread evenly", component="audio"))

    audio = _read(root / "audio_report.json")
    if audio:
        rate = (audio.get("alignment") or {}).get("word_match_rate")
        if rate is not None:
            checks.append(_check("narration heard as written", "narration", "pass" if rate >= 0.85 else "warn",
                                 f"{rate:.0%} of words recognised in the synthesized speech", component="audio"))

    final = _read(out / "final_checks.json")
    if final is None:
        checks.append(_check("render checks", "technical", "skipped", "no final_checks.json"))
    else:
        for c in final.get("checks") or []:
            name = c["check"]
            area = ("sync" if "cue" in name else "visual" if any(w in name for w in ("overlap", "stage", "bounds"))
                    else "technical")
            beats = []
            if "stage" in name:
                beats = [d.get("beat") for d in final.get("bounds_detail") or []]
            elif "overlap" in name:
                beats = [d.get("beat") for d in (final.get("layout_findings") or {}).get("detail") or [] if d.get("counted")]
            checks.append(_check(name, area, "pass" if c["passed"] else "fail", c.get("detail", ""), beats,
                                 "visuals" if area == "visual" else "render"))

    vision = _read(out / "vision_review.json")
    if vision is not None:
        rows = [r for r in vision.get("detail") or [] if r.get("findings")]
        checks.append(_check("frames show what the words say", "visual", "warn" if rows else "pass",
                             f"{vision.get('findings', 0)} finding(s) on {vision.get('frames', 0)} frame(s)",
                             [r.get("beat") for r in rows], "visuals"))

    if verification:
        open_findings = [f for f in verification.get("findings") or [] if not f.get("resolved")]
        flow = [f for f in open_findings if str(f.get("what", "")).startswith("flow:")]
        wrong = [f for f in open_findings if f.get("severity") == "critical"] + list(verification.get("claims_failed") or [])
        checks.append(_check("claims and facts", "correctness", "fail" if wrong else "pass",
                             f"{len(verification.get('claims_failed') or [])} claim(s) failed when checked with code; "
                             f"{sum(f.get('severity') == 'critical' for f in open_findings)} critical finding(s) open",
                             [f.get("beat") for f in wrong if isinstance(f, dict)], "script"))
        checks.append(_check("narration continuity", "narration", "warn" if flow else "pass",
                             f"{len(flow)} open finding(s) about how the lesson flows", [f.get("beat") for f in flow],
                             "script"))
        majors = [f for f in open_findings if f.get("severity") == "major" and f not in flow]
        checks.append(_check("reviewer's open findings", "pedagogy", "warn" if majors else "pass",
                             f"{len(majors)} major finding(s) left after the rewrites; review status "
                             f"{verification.get('status', '?')}", [f.get("beat") for f in majors], "script"))
    else:
        checks.append(_check("claims and facts", "correctness", "skipped", "no review of this lesson's words"))

    plan: dict[str, dict] = {}
    for c in checks:
        if c["status"] in ("fail", "warn"):
            for beat in c["beats"]:
                entry = plan.setdefault(beat, {"components": [], "because": []})
                if c["component"] and c["component"] not in entry["components"]:
                    entry["components"].append(c["component"])
                entry["because"].append(f"{c['id']} ({c['status']})")
    counts = {k: sum(c["status"] == k for c in checks) for k in ("pass", "warn", "fail", "skipped")}
    return {
        "schema": SCHEMA,
        "status": "failed" if counts["fail"] else "passed_with_warnings" if counts["warn"] else "passed",
        "counts": counts,
        "by_area": {a: {k: sum(c["status"] == k for c in checks if c["area"] == a) for k in ("pass", "warn", "fail")}
                    for a in AREAS},
        "checks": checks,
        "repair_plan": dict(sorted(plan.items())),
        "limits": ["Every check here is a measurement or a model's look; none is a teacher's or a learner's review.",
                   "A 'warn' is worth a look and does not stop a lesson; a 'fail' names the component to repair."],
    }


def write_qa(root: str | Path, verification: dict | None = None, log=print) -> dict:
    report = qa_report(root, verification)
    out = Path(root) / "output"
    out.mkdir(parents=True, exist_ok=True)
    (out / "qa_report.json").write_text(json.dumps(report, indent=1, ensure_ascii=False), encoding="utf-8")
    c = report["counts"]
    log(f"[qa] {report['status']}: {c['pass']} passed, {c['warn']} to look at, {c['fail']} failed"
        + (f"; beats to repair: {', '.join(list(report['repair_plan'])[:12])}" if report["repair_plan"] else ""))
    return report


# ── The bundle ─────────────────────────────────────────────────────────────────────────────────────────────────


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _code_version() -> dict:
    here = Path(__file__).resolve().parent
    found: dict = {}
    try:
        from importlib.metadata import version
        found["lessonforge"] = version("lessonforge")
    except Exception:  # noqa: BLE001 - an uninstalled checkout has no version
        pass
    try:
        commit = subprocess.run(["git", "-C", str(here), "rev-parse", "HEAD"], capture_output=True, text=True, timeout=5)
        if commit.returncode == 0:
            found["commit"] = commit.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        pass
    return found


def write_bundle(root: str | Path, video: str | Path | None = None, log=print) -> dict:
    """``output/bundle.json``: every stage file of the lesson with its hash, so a release can be checked and rebuilt.

    The lesson is editable at its storyboard (``lesson.json``) and rebuilt from it with
    ``lessonforge lesson build <folder>``; narration already paid for is reused from its cache.
    """
    root = Path(root)
    rows = []
    paths = list(STAGE_FILES) + [(p.relative_to(root).as_posix(), "4B scene code") for p in sorted(root.glob("chapters_*.py"))]
    if video:
        paths.append((Path(video).resolve().relative_to(root.resolve()).as_posix(), "8 final video"))
    for rel, stage in paths:
        path = root / rel
        if path.is_file():
            rows.append({"path": rel, "stage": stage, "bytes": path.stat().st_size, "sha256": _sha256(path)})
    bundle = {"schema": BUNDLE_SCHEMA, "made_with": _code_version(), "files": rows,
              "rebuild": "lessonforge lesson build <this folder>  (from lesson.json; narration is reused from its cache)"}
    out = root / "output"
    out.mkdir(parents=True, exist_ok=True)
    (out / "bundle.json").write_text(json.dumps(bundle, indent=1), encoding="utf-8")
    log(f"[bundle] {len(rows)} stage file(s) recorded with their hashes")
    return bundle
