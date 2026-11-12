"""The whole loop, unattended and capped: film, judge every sentence's frame, let Claude edit, film again.

    lessonforge loop <lesson-id | lesson.json | PACK.md --unit N ...> --cap 0.05 --batch-cap 1.00

Per lesson: film the newest version (free, local voice) -> ``frame_judge`` (about 0.65 US cents) -> ``improver``
with what the frames showed (Haiku, a few tenths of a cent a round) -> film -> judge again. The version whose film
passes more sentences is kept as the newest. Every paid call counts against the lesson's cap and the batch's cap;
the batch stops before a lesson would start without room for its own cap.
"""
from __future__ import annotations

from . import frame_judge, improver
from . import workbench as W


def _films(lesson_id: str) -> int:
    return len(list((W.root() / lesson_id).glob("v[0-9][0-9][0-9].mp4")))


def one(lesson_id: str, cap_usd: float = 0.05, rounds: int = 2, passes: int = 1, voice: str = W.DEFAULT_VOICE,
        log=print) -> dict:
    spent = 0.0
    newest = W.check(lesson_id)["versions"]
    if not (W.root() / lesson_id / f"v{newest:03}.mp4").is_file():
        W.film(lesson_id, voice=voice, log=lambda *a: None)
    first = frame_judge.judge(lesson_id, cap_usd=min(0.02, cap_usd / 2), log=log)
    spent += first["spent_usd"]
    best = {"version": W.check(lesson_id)["versions"], "pass": first["pass_share"] or 0.0,
            "held": first["held_share"] or 0.0, "report": first}
    history = [{"version": best["version"], "pass": best["pass"], "held": best["held"], "spent": first["spent_usd"]}]
    for _ in range(passes):
        room = cap_usd - spent - 0.01           # what the next judge needs is kept back
        if room <= 0.002:
            log(f"[loop] {lesson_id}: no room left in the cap (${spent:.4f} of ${cap_usd:.2f})")
            break
        done = improver.improve(lesson_id, cap_usd=room, rounds=rounds, escalate=None, log=log,
                                film_faults=frame_judge.as_faults(best["report"]))
        spent += done["spent_usd"]
        version = W.check(lesson_id)["versions"]
        if version == best["version"]:
            log(f"[loop] {lesson_id}: no edit was kept; stopping")
            break
        W.film(lesson_id, voice=voice, log=lambda *a: None)
        again = frame_judge.judge(lesson_id, cap_usd=min(0.02, max(0.0, cap_usd - spent)), log=log)
        spent += again["spent_usd"]
        score = again["pass_share"] or 0.0
        history.append({"version": version, "pass": score, "held": again["held_share"], "spent": done["spent_usd"] + again["spent_usd"]})
        if score + 0.005 >= best["pass"]:
            best = {"version": version, "pass": score, "held": again["held_share"] or 0.0, "report": again}
        else:
            log(f"[loop] {lesson_id}: the edited film passes fewer sentences ({score} < {best['pass']}); keeping version {best['version']}")
            W.revert(lesson_id, best["version"], by="loop (best film)")
            break
    return {"lesson_id": lesson_id, "spent_usd": round(spent, 4), "best_version": best["version"],
            "pass_share": best["pass"], "held_share": best["held"], "history": history}


def batch(lesson_ids: list[str], cap_usd: float = 0.05, batch_cap_usd: float = 1.0, log=print, **kw) -> list[dict]:
    out, spent = [], 0.0
    for lesson_id in lesson_ids:
        if spent + cap_usd > batch_cap_usd:
            log(f"[loop] batch cap ${batch_cap_usd:.2f} would be passed (spent ${spent:.4f}): {lesson_id} and later not run")
            break
        result = one(lesson_id, cap_usd=cap_usd, log=log, **kw)
        spent += result["spent_usd"]
        out.append(result)
        log(f"[loop] {lesson_id}: pass {result['history'][0]['pass']} -> {result['pass_share']}, ${result['spent_usd']:.4f} "
            f"(batch ${spent:.4f} of ${batch_cap_usd:.2f})")
    return out
