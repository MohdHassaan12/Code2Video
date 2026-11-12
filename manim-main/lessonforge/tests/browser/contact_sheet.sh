#!/bin/bash
# contact_sheet.sh LESSON_DIR VIDEO OUT_PREFIX : one frame per beat at the vision-review sample points, tiled 3x2
set -e
ROOT=$1; VIDEO=$2; OUT=$3
cd "$(dirname "$0")"
python - "$ROOT" "$VIDEO" "$OUT" <<'EOF'
import json, subprocess, sys
from pathlib import Path
from lessonforge.harness.vision_review import sample_points, _frame
root, video, out = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
lesson = json.loads((root / "lesson.json").read_text()); timeline = json.loads((root / "timeline.json").read_text())
pts = sample_points(timeline, lesson)
frames = []
for p in pts:
    f = Path(f"{out}_beat{p['beat']}.jpg"); _frame(video, p["at"], f, width=640); frames.append(f)
    print(p["beat"], p["at"], p["spoken"][:80])
for i in range(0, len(frames), 6):
    chunk = frames[i:i+6]
    inputs = sum([["-i", str(f)] for f in chunk], [])
    n = len(chunk)
    layout = "|".join(f"{(k%3)*640}_{(k//3)*360}" for k in range(n))
    subprocess.run(["ffmpeg", "-v", "error", "-y", *inputs, "-filter_complex", f"xstack=inputs={n}:layout={layout}:fill=black", f"{out}_sheet{i//6+1}.jpg"], check=True)
    print("sheet", f"{out}_sheet{i//6+1}.jpg", [f.name for f in chunk])
EOF
