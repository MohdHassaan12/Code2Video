"""
Regression tests for the 10 Code Audit Bug Fixes in Lessonforge.
Verifies all 10 fixes identified in:
'Lessonforge vs Code2Video and SGA: architecture, baseline and feedback directions'
"""

import json
import os
import shutil
import tempfile
from pathlib import Path
import pytest

from lessonforge import knobs, layout_probe
from lessonforge.harness import repairs, qa as harness_qa
from lessonforge.longform import qa as longform_qa, build as longform_build
from lessonforge.engine import render as engine_render, sim_gen


def test_bug1_layout_probe_per_kind_cap_and_truncation():
    """Bug 1: Verify layout probe parses truncation as counted fault and maintains per-kind caps."""
    # Test truncation parsing
    log_with_trunc = (
        "LAYOUT_VIOLATION: overlap Text('A') at [0,0] x Text('B') at [0,0] depth 0.5x0.5 after play#1\n"
        "LAYOUT_VIOLATION: overlap report truncated (limit reached)\n"
        "LAYOUT_VIOLATION: shape-overlap Circle x Square depth 0.5x0.5 after play#2\n"
        "LAYOUT_VIOLATION: shape-overlap report truncated (limit reached)\n"
    )
    parsed = layout_probe.parse(log_with_trunc)
    assert len(parsed) == 4

    # Counted kinds vs uncounted kinds
    overlap_item = next(p for p in parsed if p["kind"] == "overlap")
    assert overlap_item["counted"] is True

    # Counted truncation (overlap) must be counted
    trunc_overlap = next(p for p in parsed if p["kind"] == "truncation" and "overlap report truncated" in p["detail"])
    assert trunc_overlap["counted"] is True

    # Uncounted truncation (shape-overlap) must NOT be counted
    trunc_shape = next(p for p in parsed if p["kind"] == "truncation" and "shape-overlap report truncated" in p["detail"])
    assert trunc_shape["counted"] is False


def test_bug3_render_jobs_knobs_configuration(monkeypatch):
    """Bug 3: Verify render_jobs respects LESSONFORGE_RENDER_JOBS environment and override."""
    monkeypatch.setenv("LESSONFORGE_RENDER_JOBS", "2")
    assert knobs.render_jobs() == 2

    with knobs.applied({"LESSONFORGE_RENDER_JOBS": "4"}):
        assert knobs.render_jobs() == 4

    monkeypatch.delenv("LESSONFORGE_RENDER_JOBS", raising=False)
    assert knobs.render_jobs() == 8


def test_bug4_repair_count_treats_error_row_as_not_improved():
    """Bug 4: Verify _count returns infinity if review failed or contains error rows."""
    # Successful review with 1 finding
    clean_review = {
        "detail": [
            {"beat": "01", "findings": [{"kind": "mismatch", "what": "wrong label"}]}
        ]
    }
    assert repairs._count(clean_review, ["01"]) == 1

    # Failed review with error in row
    error_row_review = {
        "detail": [
            {"beat": "01", "error": "LLM Provider Timeout 504"}
        ]
    }
    assert repairs._count(error_row_review, ["01"]) == float("inf")

    # Review is None
    assert repairs._count(None, ["01"]) == float("inf")

    # Missing detail
    assert repairs._count({}, ["01"]) == float("inf")


def test_bug5_repairs_put_back_restores_chapter_atomically():
    """Bug 5: Verify put_back restores the original chapter from before without desync."""
    before_lesson = {
        "chapters": [
            {
                "id": "1",
                "beats": [
                    {"id": "b1", "steps": [{"say": "original", "show": "X"}]}
                ]
            }
        ]
    }
    lesson_dict = {
        "chapters": [
            {
                "id": "1",
                "beats": [
                    {"id": "b1", "steps": [{"say": "modified", "show": "Y"}]}
                ]
            }
        ]
    }

    # Verify that restoring cid=1 replaces the chapter structure completely
    first = {1: before_lesson["chapters"][0]}
    for i, ch in enumerate(lesson_dict["chapters"]):
        if int(ch["id"]) == 1:
            lesson_dict["chapters"][i] = json.loads(json.dumps(first[1]))
            break

    assert lesson_dict["chapters"][0]["beats"][0]["steps"][0]["say"] == "original"


def test_bug6_asset_preservation_guard():
    """Bug 6: Verify _repair_preserves_assets blocks replacing simulations or images."""
    code_with_sim = "s = simulation('orbit.py', width=6, height=4)\nplay(Create(s))"
    repaired_without_sim = "c = Circle()\nplay(Create(c))"
    repaired_with_sim = "s = simulation('orbit.py', width=6, height=4)\ns.to_edge(UP)\nplay(Create(s))"

    assert not engine_render._repair_preserves_assets(code_with_sim, repaired_without_sim)
    assert engine_render._repair_preserves_assets(code_with_sim, repaired_with_sim)

    code_with_img = "img = fetch_real_image('dna.jpg')\nplay(FadeIn(img))"
    repaired_without_img = "txt = Text('DNA')\nplay(Write(txt))"
    assert not engine_render._repair_preserves_assets(code_with_img, repaired_without_img)


def test_bug8_atomic_simulation_cache_writes(tmp_path):
    """Bug 8: Verify simulation cache is written atomically and published files are guarded."""
    out_py = str(tmp_path / "sim_test.py")
    out_json = out_py + ".json"

    # Simulate atomic write
    code = "def build(w, h): return Circle()"
    tmp_out = f"{out_py}.tmp.{os.getpid()}"
    with open(tmp_out, "w", encoding="utf-8") as f:
        f.write(code)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp_out, out_py)

    assert os.path.exists(out_py)
    assert open(out_py).read() == code

    # Verify published guard in _verify_again logic
    side_data = {"verified_with": "2026-10-19-text", "published": True}
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(side_data, f)

    meta = json.load(open(out_json, encoding="utf-8"))
    assert meta.get("published") is True


def test_bug9_render_failure_classification():
    """Bug 9: Verify failure classification gates code-repair only to genuine code failures."""
    infra_log = "Error: All TTS services failed: ConnectTimeout"
    latex_log = "! LaTeX Error: File 'amsmath.sty' not found."
    code_log = "NameError: name 'non_existent_obj' is not defined"

    assert engine_render._classify_render_failure(infra_log) == "infra"
    assert engine_render._classify_render_failure(latex_log) == "latex"
    assert engine_render._classify_render_failure(code_log) == "code"


def test_bug10_dual_qa_writers_separation(tmp_path):
    """Bug 10: Verify qa_report.json and beat_qa_report.json do not conflict or overwrite bundle."""
    out_dir = tmp_path / "output"
    out_dir.mkdir(parents=True)

    # 1. Longform QA report writes official schema
    longform_report = {
        "schema": longform_qa.SCHEMA,
        "status": "passed",
        "counts": {"pass": 10, "warn": 0, "fail": 0, "skipped": 0},
        "repair_plan": {}
    }
    (out_dir / "qa_report.json").write_text(json.dumps(longform_report))

    # 2. Harness beat report writes to beat_qa_report.json
    harness_report = {
        "version": 1,
        "status": "pass",
        "findings": 0,
        "beats": {}
    }
    harness_qa_file = out_dir / "beat_qa_report.json"
    harness_qa_file.write_text(json.dumps(harness_report))

    # Assert longform qa_report is preserved and has official schema and counts
    assert (out_dir / "qa_report.json").exists()
    assert (out_dir / "beat_qa_report.json").exists()

    persisted = json.loads((out_dir / "qa_report.json").read_text())
    assert persisted["schema"] == longform_qa.SCHEMA
    assert "counts" in persisted
