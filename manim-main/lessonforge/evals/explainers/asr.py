"""Transcribe our lesson videos to timed sentences (faster-whisper, CPU) so they can be scored like the YouTube captions."""
import json, sys
from pathlib import Path
from faster_whisper import WhisperModel
import subprocess, numpy as np
def load(p):
    raw=subprocess.run(['ffmpeg','-nostdin','-i',str(p),'-f','s16le','-ac','1','-ar','16000','-'],capture_output=True).stdout
    return np.frombuffer(raw,np.int16).astype(np.float32)/32768
m = WhisperModel("small.en", device="cpu", compute_type="int8", cpu_threads=4)
out = Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
for f in sys.argv[2:]:
    p = Path(f); name = p.parent.name + "__" + p.stem
    dest = out / f"{name}.json"
    if dest.exists(): continue
    segs, info = m.transcribe(load(p), language="en", vad_filter=False)
    cues = [{"start": s.start, "end": s.end, "text": s.text.strip()} for s in segs]
    dest.write_text(json.dumps({"id": name, "title": p.stem, "channel": "lessonforge", "source": str(p), "duration": info.duration, "chapters": [], "cues": cues}))
    print(name, len(cues), flush=True)
