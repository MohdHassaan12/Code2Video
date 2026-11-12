"""Add explainers straight from channels known for clear explanations (their own captions), up to N per channel."""
import json, sys, time, random
from pathlib import Path
import yt_dlp
sys.path.insert(0, str(Path(__file__).parent)); from collect import fetch
OUT = Path(sys.argv[1]); N = int(sys.argv[2])
CH = ["@3blue1brown", "@khanacademy", "@veritasium", "@minutephysics", "@TEDEd", "@kurzgesagt", "@crashcourse",
      "@ProfessorDaveExplains", "@SteveMould", "@numberphile", "@Mathologer", "@upandatom", "@EddieWooTeacher", "@TylerDeWitt",
      "@MinuteEarth", "@scishow", "@amoebasisters", "@FuseSchool", "@WelchLabsVideo", "@Reducible", "@PracticalEngineeringChannel",
      "@TheEfficientEngineer", "@AlphaPhoenixChannel", "@standupmaths", "@PrimerBlobs", "@DrTrefor"]
idx = OUT / "index.jsonl"; seen = {json.loads(l)["id"] for l in open(idx)} if idx.exists() else set()
for ch in CH:
    try:
        with yt_dlp.YoutubeDL({"extract_flat": True, "quiet": True, "playlistend": 60}) as y:
            ents = (y.extract_info(f"https://www.youtube.com/{ch}/videos", download=False) or {}).get("entries") or []
    except Exception as e:
        print(ch, "list failed", e); continue
    kept = 0
    for e in ents:
        if kept >= N: break
        if e["id"] in seen or not (180 <= (e.get("duration") or 0) <= 1500): continue
        seen.add(e["id"])
        try: rec = fetch(e["id"])
        except Exception as ex: rec = {"skip": f"{type(ex).__name__}"}
        if not rec.get("skip"):
            rec["topic"] = ""; (OUT / "videos" / f"{e['id']}.json").write_text(json.dumps(rec, ensure_ascii=False)); kept += 1
        with open(idx, "a") as f: f.write(json.dumps({"id": e["id"], "topic": "", "title": e.get("title"), "channel": ch, "skip": rec.get("skip", "")}) + "\n")
        time.sleep(1 + random.random())
    print(ch, kept, flush=True)
