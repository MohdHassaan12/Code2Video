"""Old vs new framework through lessonforge's real writer (write_lesson): one lesson per topic per framework.

    PYTHONPATH=src python evals/explainers/writer_ab.py newtons_first_law,kinetic_energy concrete_first,story [out_dir]

Writes <topic>__<framework>.json with the spoken words (narration, then each revealed answer). About $0.01 a lesson on Haiku.
"""
import json, sys, time, os
from pathlib import Path
from lessonforge.harness import writer, storyflow
OUT = Path(sys.argv[3] if len(sys.argv) > 3 else "writer_ab_out"); OUT.mkdir(exist_ok=True)
T = {t["id"]: t for t in json.load(open(Path(__file__).with_name("script_topics.json")))}
def spoken(lesson):
    """The words a viewer hears: each beat's narration, and after a question its revealed answer (the player shows it)."""
    def beat(b):
        q = b.get("quiz") or {}
        return (b.get("narration", "") + (" " + q["explain"] if q.get("explain") else "")).strip()
    return "\n\n".join(" ".join(beat(b) for b in ch.get("beats") or []) for ch in lesson.get("chapters") or [])
def run(tid, fw, minutes=3):
    dest = OUT / f"{tid}__{fw}.json"
    if dest.exists(): return
    t = T[tid]
    brief = {"topic": t["topic"], "audience": t["audience"], "goal": t["goal"], "level": "foundation",
             "framework": fw, "duration_minutes": minutes, "language": "en-IN", "style": "tutor"}
    t0 = time.time()
    lesson = writer.write_lesson(brief, writer.default_llm(), log=lambda *a: None, picture=False)
    text = spoken(lesson)
    dest.write_text(json.dumps({"topic": tid, "framework": fw, "text": text, "seconds": round(time.time() - t0),
                                "story_findings": [f if isinstance(f, str) else f.get("message", str(f)) for f in storyflow.story_gate(lesson)],
                                "lesson": lesson}, default=str))
    print(tid, fw, len(text.split()), "words", round(time.time() - t0), "s", flush=True)
if __name__ == "__main__":
    for tid in sys.argv[1].split(","):
        for fw in sys.argv[2].split(","):
            try: run(tid, fw)
            except Exception as e: print("FAILED", tid, fw, str(e)[:300], flush=True)
