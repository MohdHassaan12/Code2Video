"""Collect good concept-explainer videos from YouTube: metadata, chapters, timed human captions. No API key, no model."""
import json, re, sys, time, random
from pathlib import Path
import requests, yt_dlp

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
OUT = Path(sys.argv[2] if len(sys.argv) > 2 else "corpus")
GOOD = {  # channels known for clear concept explanations (lower-case substring match)
 "3blue1brown","khan academy","veritasium","minutephysics","numberphile","mathologer","steve mould","ted-ed",
 "crashcourse","kurzgesagt","eddie woo","physics girl","scishow","professor dave explains","up and atom",
 "stand-up maths","tyler dewitt","looking glass universe","zach star","primer","real engineering","sabine hossenfelder",
 "the action lab","be smart","fermilab","domain of science","vsauce","cuemath","the organic chemistry tutor",
 "minute earth","minuteearth","smarter every day","simple science","fuseschool","amoeba sisters","bozeman science",
 "nancypi","blackpenredpen","physics videos by eugene khutoryansky","wrath of math","polar pi","the science asylum",
 "ted","dr. trefor bazett","welch labs","art of the problem","reducible","stated clearly","osmosis from elsevier",
 "practical engineering","andrew dotson","flammable maths","sciencephile the ai","lesics","the efficient engineer",
 "electroboom","for the allure of physics","acapellascience","scientific american","nova pbs","pbs space time",
 "physics with elliot","jeff hanson","mit opencourseware","sixty symbols","periodic videos","cheddar",
}
def search(q, limit=15):
    try:
        p = requests.get("https://www.youtube.com/results", params={"search_query": q}, headers={"User-Agent": UA, "Accept-Language": "en;q=0.9"}, timeout=30)
        m = re.search(r"var ytInitialData = (\{.*?\});</script>", p.text, re.S); data = json.loads(m.group(1)) if m else {}
    except Exception as e:
        print("search fail", e); return []
    out = []
    def walk(n):
        if isinstance(n, dict):
            v = n.get("videoRenderer")
            if isinstance(v, dict) and v.get("videoId"):
                runs = lambda k: "".join(r.get("text", "") for r in (v.get(k) or {}).get("runs", []))
                L = (v.get("lengthText") or {}).get("simpleText", "0"); s = 0
                for part in L.split(":"): s = s * 60 + (int(part) if part.isdigit() else 0)
                out.append({"id": v["videoId"], "title": runs("title"), "channel": runs("ownerText"), "seconds": s})
            for x in n.values(): walk(x)
        elif isinstance(n, list):
            for x in n: walk(x)
    walk(data); return out[:limit]

OPTS = {"skip_download": True, "ignore_no_formats_error": True, "quiet": True, "no_warnings": True, "noprogress": True,
        "extractor_args": {"youtube": {"player_client": ["web_embedded"]}}, "socket_timeout": 30}
def fetch(vid):
    """Video record with human-written English captions (punctuated); None when it has none."""
    with yt_dlp.YoutubeDL(OPTS) as y:
        i = y.extract_info("https://www.youtube.com/watch?v=" + vid, download=False) or {}
        subs = i.get("subtitles") or {}
        lang = next((l for l in ("en", "en-US", "en-GB", "en-IN", "en-CA", "en-AU") if subs.get(l)), None)
        if not lang:
            return {"id": vid, "skip": "no human English captions"}
        url = next((t["url"] for t in subs[lang] if t.get("ext") == "json3"), None)
        if not url:
            return {"id": vid, "skip": "no json3"}
        ev = json.loads(y.urlopen(url).read().decode("utf-8")).get("events") or []
    cues = []
    for e in ev:
        t = "".join(s.get("utf8", "") for s in e.get("segs") or []).replace("\n", " ").strip()
        if t:
            cues.append({"start": e.get("tStartMs", 0) / 1000, "end": (e.get("tStartMs", 0) + e.get("dDurationMs", 0)) / 1000, "text": t})
    return {"id": vid, "title": i.get("title"), "channel": i.get("channel"), "duration": i.get("duration"),
            "views": i.get("view_count"), "likes": i.get("like_count"), "upload_date": i.get("upload_date"),
            "chapters": [{"start": c["start_time"], "title": c["title"]} for c in i.get("chapters") or []],
            "caption_lang": lang, "cues": cues}

if __name__ == "__main__":
    topics = [l.strip() for l in open(sys.argv[1]) if l.strip() and not l.startswith("#")]
    (OUT / "videos").mkdir(parents=True, exist_ok=True)
    index_f = OUT / "index.jsonl"; seen = {json.loads(l)["id"] for l in open(index_f)} if index_f.exists() else set()
    for topic in topics:
        cands = {}
        for q in (topic, topic + " explained"):
            for v in search(q):
                if v["id"] not in cands and 150 <= v["seconds"] <= 1500 and any(g in v["channel"].lower() for g in GOOD):
                    cands[v["id"]] = v
            time.sleep(1)
        kept = 0
        for v in list(cands.values())[:8]:
            if v["id"] in seen: continue
            seen.add(v["id"])
            try:
                rec = fetch(v["id"])
            except Exception as e:
                rec = {"id": v["id"], "skip": f"{type(e).__name__}: {str(e)[:80]}"}
            row = {"id": v["id"], "topic": topic, "title": v["title"], "channel": v["channel"], "seconds": v["seconds"], "skip": rec.get("skip", "")}
            if not rec.get("skip"):
                rec["topic"] = topic
                (OUT / "videos" / f"{v['id']}.json").write_text(json.dumps(rec, ensure_ascii=False))
                kept += 1
            with open(index_f, "a") as f: f.write(json.dumps(row) + "\n")
            time.sleep(1.5 + random.random())
        print(f"{topic}: {len(cands)} candidates, {kept} kept", flush=True)
