"""Run many briefs through the harness and tabulate what came out — the scale loop.

A framework is only worth keeping if it survives many topics, levels and languages,
so the unit of experiment here is a BATCH: a JSON list of briefs (the same fields the
intake fills), each run through script → verify → speech → render → check → review,
with the spend ledger metering every call. The output is one row per lesson —
status, length, continuity, critic scores, probe findings, vision findings, voice,
cost — written as ``results.json`` and ``results.md`` next to the lessons, so a run
can be compared with the next one instead of remembered.

Briefs run sequentially by default so the per-lesson cost is exact (the ledger is
global); ``parallel`` runs them on the service's thread pool and attributes cost by
time window, which is only approximate.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from .. import paths, spend
from . import service


def _row(job: dict, cost: float, seconds: float) -> dict:
    checks = job.get("checks") or {}
    cont = job.get("continuity") or {}
    ver = job.get("verification") or {}
    vis = job.get("vision_review") or {}
    brief = job.get("brief") or {}
    return {
        "job_id": job["job_id"], "status": job["status"], "error": job.get("error"),
        "title": job.get("title"), "framework": brief.get("framework"), "level": brief.get("level"),
        "language": brief.get("language"), "minutes_asked": brief.get("duration_minutes"),
        "seconds": round(seconds, 1), "cost_usd": round(cost, 4), "voice": job.get("voice"),
        "generated_by": job.get("generated_by"),
        "duration_s": checks.get("duration_seconds"), "words": cont.get("words"), "target_words": cont.get("target_words"),
        "chapters_with_example": f"{cont.get('chapters_using_running_example')}/{cont.get('chapters')}",
        "cold_opens": cont.get("cold_opens"), "steps_anchored": f"{cont.get('steps_anchored_to_speech')}/{cont.get('steps')}",
        "critic_scores": ver.get("scores"), "critic_status": ver.get("status"),
        "claims_checked": ver.get("claims_checked"), "claims_failed": len(ver.get("claims_failed") or []),
        "critical_unresolved": ver.get("critical_unresolved"),
        "checks_status": checks.get("status"), "layout_counted": checks.get("layout_counted"),
        "anchor_timing": checks.get("anchor_timing"), "sentence_timing": checks.get("sentence_timing"),
        "alignment": job.get("alignment"),
        "vision_findings": vis.get("findings"), "vision_by_kind": vis.get("by_kind"),
        "video_url": job.get("video_url"),
    }


def run_batch(briefs: list[dict], quality: str = "m", voice: str | None = None, parallel: bool = False,
              out_dir: str | Path | None = None, log=print) -> list[dict]:
    out = Path(out_dir) if out_dir else paths.sub("bulk_runs", time.strftime("%Y%m%d-%H%M%S"))
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    if parallel:
        started = {j["job_id"]: (time.time(), spend.spent()) for j in (service.start_job(b, quality=quality, voice=voice) for b in briefs)}
        pending = set(started)
        while pending:
            time.sleep(5)
            for job_id in list(pending):
                job = service.get_job(job_id)
                if job["status"] in ("done", "failed"):
                    t0, c0 = started[job_id]
                    rows.append(_row(job, spend.spent() - c0, time.time() - t0))
                    pending.discard(job_id)
                    log(f"[batch] {job_id} {job['status']} ({len(rows)}/{len(briefs)})")
    else:
        for i, brief in enumerate(briefs, 1):
            t0, c0, seen = time.time(), spend.spent(), 0
            job = service.start_job(brief, quality=quality, voice=voice)
            log(f"[batch] {i}/{len(briefs)} {brief.get('topic', '')!r} → {job['job_id']}")
            while True:
                job = service.get_job(job["job_id"])
                for line in job["progress"][seen:]:
                    log(f"    {line}")
                seen = len(job["progress"])
                if job["status"] in ("done", "failed"):
                    break
                time.sleep(3)
            rows.append(_row(job, spend.spent() - c0, time.time() - t0))
    (out / "results.json").write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")
    (out / "results.md").write_text(table(rows), encoding="utf-8")
    log(f"[batch] wrote {out / 'results.md'}")
    return rows


def table(rows: list[dict]) -> str:
    cols = [("title", "lesson"), ("framework", "framework"), ("language", "lang"), ("status", "status"),
            ("duration_s", "video s"), ("words", "words"), ("target_words", "target"),
            ("chapters_with_example", "example"), ("steps_anchored", "anchored"), ("critic_scores", "critic"),
            ("claims_failed", "claims✗"), ("layout_counted", "layout"), ("anchor_timing", "anchors"),
            ("vision_findings", "vision"), ("voice", "voice"), ("cost_usd", "USD"), ("seconds", "wall s")]
    head = "| " + " | ".join(h for _, h in cols) + " |\n|" + "|".join("---" for _ in cols) + "|\n"
    body = ""
    for r in rows:
        cells = []
        for key, _ in cols:
            v = r.get(key)
            if isinstance(v, dict):
                v = " ".join(f"{k[:4]}={x}" for k, x in v.items())
            cells.append(str(v if v is not None else "").replace("|", "/"))
        body += "| " + " | ".join(cells) + " |\n"
    return head + body
