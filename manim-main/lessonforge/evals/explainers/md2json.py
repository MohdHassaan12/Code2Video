"""Turn a combined-transcripts .md export (one '# Video transcript:' section per video) into corpus records.
No timings in the export: a sentence's time is spread by its word position over the stated duration."""
import json, re, sys
from pathlib import Path
out = Path(sys.argv[1]); n = 0
SET = "khan-middle-school (user upload)"
for src in sys.argv[2:]:
    for sec in Path(src).read_text().split("# Video transcript: ")[1:]:
        title = sec.split("\n", 1)[0].strip()
        vid = re.search(r"watch\?v=([\w-]{11})", sec).group(1)
        dur = re.search(r"Duration: ([\d:]+)", sec).group(1); d = 0
        for p in dur.split(":"): d = d * 60 + int(p)
        body = sec.split("## Transcript", 1)[1].split("\n---", 1)[0]
        body = re.sub(r"^\s*-\s*\[[^\]]+\]\s*", "", body.strip())
        words = body.split(); total = len(words) or 1
        cues, pos = [], 0
        for para in [p for p in body.split("\n\n") if p.strip()]:
            w = para.split(); cues.append({"start": d * pos / total, "end": d * (pos + len(w)) / total, "text": " ".join(w)}); pos += len(w)
        topic = title.split("|")[0].strip().lower()
        set_ = "khan-high-school (user upload)" if "High school" in title else "khan-science-toolkit (user upload)" if "toolkit" in src.lower() else SET
        rec = {"id": vid, "title": title, "channel": "Khan Academy", "duration": d, "chapters": [], "caption_lang": "en",
               "cues": cues, "topic": topic, "set": set_, "timing": "spread"}
        (out / f"{vid}.json").write_text(json.dumps(rec, ensure_ascii=False)); n += 1
print(n, "records")
