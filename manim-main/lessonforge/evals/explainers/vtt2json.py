import json, re, sys
from pathlib import Path
def ts(x):
    h, m, s = x.split(":") if x.count(":") == 2 else ("0", *x.split(":")); return int(h) * 3600 + int(m) * 60 + float(s)
src, dest, name = sys.argv[1], sys.argv[2], sys.argv[3]
cues = []
for block in Path(src).read_text().split("\n\n"):
    m = re.search(r"([\d:.]+) --> ([\d:.]+)\n(.+)", block, re.S)
    if m: cues.append({"start": ts(m.group(1)), "end": ts(m.group(2)), "text": " ".join(m.group(3).split())})
Path(dest).write_text(json.dumps({"id": name, "title": name, "channel": "lessonforge", "duration": cues[-1]["end"] if cues else None, "chapters": [], "cues": cues}))
