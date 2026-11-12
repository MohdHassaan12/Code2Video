"""Reviewable exports: the narrative, the timed storyboard and a local chapter player.

A lesson is accepted by a person, not by a check. These three files are what that
person needs: the words in order (``narrative.md``), each beat's purpose, speech,
picture and where its animation anchors landed (``storyboard.md``), and a page that
jumps the finished video to any chapter with captions on (``review.html``).

The player loads captions from a file, which some browsers refuse on ``file://`` —
serve the lesson directory (``python -m http.server``) if they do not appear. The
mp4 also carries its own subtitle track and chapter markers.
"""
from __future__ import annotations

import html
import json
from pathlib import Path

from .contract import Lesson

_PAGE = """<!doctype html><html lang="{lang}"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{title}</title><style>body{{margin:0;background:#0b1220;color:#f3f5f7;font:17px system-ui}}main{{max-width:1300px;margin:auto;padding:28px}}h1{{font-size:34px;margin:8px 0}}p{{color:#a9b6ca;line-height:1.5}}.layout{{display:grid;grid-template-columns:minmax(0,1fr) 290px;gap:20px}}video{{width:100%;background:#000;border-radius:12px}}button{{display:block;width:100%;text-align:left;padding:13px;border:1px solid #29394f;background:#111e31;color:#f3f5f7;border-radius:7px;margin-bottom:7px;cursor:pointer}}button:hover{{border-color:#57d6bf}}button span{{color:#57d6bf;font-variant-numeric:tabular-nums;margin-right:8px}}a{{color:#57d6bf}}video::cue{{font:24px sans-serif;background:#0b1220e8}}small{{color:#a9b6ca}}.warn{{color:#ffd17c}}@media(max-width:850px){{.layout{{grid-template-columns:1fr}}}}</style><main><small>{kicker}</small><h1>{title}</h1><p>{thesis}</p><div class="layout"><section><video id="lesson" controls preload="metadata"><source src="output/{video}" type="video/mp4"><track default kind="captions" src="output/captions.vtt" srclang="{lang}" label="Captions"></video><p><a href="output/{video}" download>Download video</a> · <a href="narrative.md">Narrative</a> · <a href="storyboard.md">Storyboard</a> · <a href="output/final_checks.json">Checks</a></p><small class="{status_class}">{status}</small></section><nav>{buttons}</nav></div></main><script>const video=document.getElementById('lesson');document.querySelectorAll('button[data-time]').forEach(b=>b.onclick=()=>{{video.currentTime=Number(b.dataset.time);video.play()}});</script></html>"""


def _clock(t: float) -> str:
    return f"{int(t) // 60:02}:{int(t) % 60:02}"


def write_review(lesson_dir: str | Path, lesson: Lesson, video: Path, log=print) -> Path:
    root = Path(lesson_dir)
    timeline = {t["id"]: t for t in json.loads((root / "timeline.json").read_text(encoding="utf-8"))}
    narrative = [f"# {lesson.title}", ""]
    board = ["# Narrative storyboard and visualization script", "",
             "Beat times are measured from the synthesized audio. Each anchor lists how its "
             "position was obtained; word-position anchors are estimates.", ""]
    buttons = []
    for chapter in lesson.chapters:
        start = timeline[chapter.beats[0].id]["start"]
        narrative += [f"## {_clock(start)} — {chapter.title}", ""]
        buttons.append(f'<button data-time="{start}"><span>{_clock(start)}</span> {html.escape(chapter.title)}</button>')
        audit_path = root / "output" / f"chapter_{chapter.id:02}_audit.json"
        audit = json.loads(audit_path.read_text(encoding="utf-8")) if audit_path.exists() else {}
        for beat in chapter.beats:
            t = timeline[beat.id]
            narrative += [beat.narration, ""]
            if beat.thinking_pause_seconds:
                narrative += [f"[Thinking pause: {beat.thinking_pause_seconds:g} seconds]", ""]
            board += [f"## Beat {beat.id} · {_clock(t['start'])}–{_clock(t['start'] + t['duration'])}", "",
                      f"**Teaching purpose:** {beat.check}", "", f"**Narration:** {beat.narration}", "",
                      f"**Visualization:** {beat.visual}", "", f"**Reference equation:** `{beat.equation}`", "",
                      f"**Thinking pause:** {beat.thinking_pause_seconds:g} seconds.", ""]
            cues = [c for c in audit.get("cues", []) if c["beat"] == beat.id]
            if cues:
                board += ["**Animation anchors in the narration:**", ""]
                board += [f"- {_clock(start + max(c['target'], c['actual_before_wait']))}: {c['phrase']}"
                          f" ({c.get('timing_source', 'word-position')})" for c in cues]
                board += [""]
            findings = [f for f in audit.get("layout", []) if f.get("beat") == beat.id]
            if findings:
                board += ["**Layout findings:**", ""] + [f"- {f['kind']}: {f['detail']}" for f in findings] + [""]
    (root / "narrative.md").write_text("\n".join(narrative), encoding="utf-8")
    (root / "storyboard.md").write_text("\n".join(board), encoding="utf-8")

    checks_path = root / "output" / "final_checks.json"
    checks = json.loads(checks_path.read_text(encoding="utf-8")) if checks_path.exists() else {}
    passed = checks.get("status") == "technical_checks_passed"
    status = ("Technical checks passed. " if passed else "Technical checks FAILED — see Checks. ") + \
        "Synthetic narration. Teacher and learner evaluation are separate and not implied."
    total = sum(t["duration"] for t in timeline.values())
    page = _PAGE.format(lang=html.escape((lesson.language or "en").split("-")[0]), title=html.escape(lesson.title),
                        thesis=html.escape(lesson.thesis), video=html.escape(video.name),
                        kicker=f"LESSON · {_clock(total)} · {len(lesson.chapters)} CHAPTERS",
                        status=html.escape(status), status_class="" if passed else "warn",
                        buttons="".join(buttons))
    out = root / "review.html"
    out.write_text(page, encoding="utf-8")
    log(f"[review] {out.name}, narrative.md, storyboard.md")
    return out
