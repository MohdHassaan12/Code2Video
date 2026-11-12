"""Acceptance harness for Vision QA (pipeline stage 9). No manim, no API keys.

Real ffmpeg (a 2s synthetic clip) exercises frame extraction; the vision LLM and the
render/repair seams are stubbed. Pins (reference-architecture.md §18 / §19):
  * findings are whitelist- and shape-gated (P8/P10) and formatted as
    ``LAYOUT_VIOLATION: vision-<class>`` lines that the geometric matcher
    (``render._overlap_violations``) must NEVER count;
  * critique stands aside (empty list) on every failure mode;
  * ``_run_vision_qa``'s repair round is accept-if-better with a geometric
    non-regression guard, and the incumbent video is never lost.

Run: .venv/bin/python stem_animation_lab/test_vision_qa.py
"""
import json
import os
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

os.environ["VISION_QA"] = "1"

from lessonforge.engine.pipeline import vision_qa as VQ  # noqa: E402
import lessonforge.engine.render as R                    # noqa: E402

PASS, FAIL = [], []


def check(name, cond):
    (PASS if cond else FAIL).append(name)
    print(f"{'PASS' if cond else 'FAIL'} {name}")


# ── A. parsing: whitelist + shape gate + line format ────────────────────────
ts = [1.0, 3.0, 5.0]
lines = VQ._parse_findings(json.dumps({"findings": [
    {"t": 3.1, "class": "dead-frame", "detail": "frame mostly empty"},
    {"t": 1.0, "class": "explosions", "detail": "not a real class"},
    {"t": 1.0, "class": "low-contrast", "detail": ""},
    {"t": "soon", "class": "crowding", "detail": "bad timestamp"},
    "not even a dict",
]}), ts)
check("A1 only whitelisted, well-formed findings survive", len(lines) == 1)
check("A2 line format is the probe's with a vision- class prefix",
      lines[0].startswith("LAYOUT_VIOLATION: vision-dead-frame t="))
check("A3 timestamps snap to a frame the model actually saw", "t=3.0s" in lines[0])
check("A4 the geometric matcher never counts vision lines",
      R._overlap_violations("\n".join(lines) + "\nLAYOUT_VIOLATION: overlap play#2 x y") ==
      ["LAYOUT_VIOLATION: overlap play#2 x y"])
check("A5 non-JSON and non-dict responses yield no findings",
      VQ._parse_findings("garbage {{{", ts) == [] and VQ._parse_findings("[1,2]", ts) == [])

# ── B. frame extraction on a real (synthetic) clip ──────────────────────────
tmp = tempfile.mkdtemp(prefix="vqa_harness_")
clip = os.path.join(tmp, "clip.mp4")
subprocess.run(["ffmpeg", "-f", "lavfi", "-i", "color=c=navy:s=320x240:d=2",
                "-y", clip], capture_output=True, check=True)
frames = VQ._extract_frames(clip, 4)
check("B1 four evenly spaced frames extracted from a 2s clip",
      len(frames) == 4 and [t for t, _ in frames] == sorted(t for t, _ in frames)
      and all(0 < t < 2 for t, _ in frames))
check("B2 frames are non-empty base64 JPEG payloads",
      all(isinstance(b, str) and len(b) > 100 for _, b in frames))

# ── C. critique(): stubbed vision LLM ───────────────────────────────────────
stage = VQ.VisionQAStage()
_real_vllm = VQ.call_vision_llm

VQ.call_vision_llm = lambda *a, **kw: json.dumps({"findings": [
    {"t": 0.9, "class": "low-contrast", "detail": "dim formula bottom left"}]})
out = stage.critique(clip)
check("C1 critique formats stubbed findings as vision lines",
      len(out) == 1 and out[0].startswith("LAYOUT_VIOLATION: vision-low-contrast"))

VQ.call_vision_llm = lambda *a, **kw: None
check("C2 no vision provider (None) stands aside", stage.critique(clip) == [])

VQ.call_vision_llm = lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("api down"))
check("C3 a crashing vision call stands aside", stage.critique(clip) == [])

VQ.call_vision_llm = _real_vllm
check("C4 a missing video path stands aside",
      stage.critique(os.path.join(tmp, "nope.mp4")) == [])

os.environ["VISION_QA"] = "0"
check("C5 flag off: critique is inert", VQ.VisionQAStage().critique(clip) == [])
os.environ["VISION_QA"] = "1"

# ── D. _run_vision_qa: accept-if-better with geometric guard ────────────────
CODE0, URL0, LOGS0 = "code v0", "/static/videos/old.mp4", "clean run\n"
discards, critiques = [], []


def _setup(critique_queue, compile_result, repaired="code v1"):
    """Patch every seam _run_vision_qa touches; return recorders."""
    del discards[:], critiques[:]
    queue = list(critique_queue)

    def fake_critique(self, path):
        critiques.append(path)
        return list(queue.pop(0)) if queue else []

    VQ.VisionQAStage.critique = fake_critique
    R.llm_available = lambda *a, **kw: True
    R.repair_code_with_gemini = lambda *a, **kw: repaired
    R.sanitize_generated_code = lambda code, persona=None: code
    R.compile_manim_code = lambda *a, **kw: compile_result
    R._discard_video = lambda url, keep=(): discards.append((url, tuple(keep)))
    R._store_repair_pair = lambda *a, **kw: None


_orig_critique = VQ.VisionQAStage.critique
F3 = ["LAYOUT_VIOLATION: vision-crowding t=1.0s a",
      "LAYOUT_VIOLATION: vision-dead-frame t=3.0s b",
      "LAYOUT_VIOLATION: vision-low-contrast t=5.0s c"]

# D1 accept: candidate renders clean and reduces findings 3 -> 1.
_setup([F3, F3[:1]], (True, "/static/videos/new.mp4", "clean candidate\n"))
code, url, logs, findings, rounds = R._run_vision_qa(
    CODE0, URL0, LOGS0, "STEMAnimation", "l", "widescreen", "hybrid", allow_repair=True)
check("D1 accepted candidate replaces the incumbent and discards it",
      url == "/static/videos/new.mp4" and code == "code v1" and rounds == 1
      and len(findings) == 1 and (URL0, ("/static/videos/new.mp4",)) in discards)

# D2 reject: candidate renders but does not reduce findings.
_setup([F3, F3], (True, "/static/videos/new.mp4", "clean candidate\n"))
code, url, logs, findings, rounds = R._run_vision_qa(
    CODE0, URL0, LOGS0, "STEMAnimation", "l", "widescreen", "hybrid", allow_repair=True)
check("D2 non-improving candidate is rejected; incumbent survives",
      url == URL0 and code == CODE0 and len(findings) == 3
      and ("/static/videos/new.mp4", (URL0,)) in discards)

# D3 geometric guard: candidate reduces vision findings but ADDS a probe violation.
_setup([F3, []], (True, "/static/videos/new.mp4",
                  "LAYOUT_VIOLATION: overlap play#1 t v\n"))
code, url, logs, findings, rounds = R._run_vision_qa(
    CODE0, URL0, LOGS0, "STEMAnimation", "l", "widescreen", "hybrid", allow_repair=True)
check("D3 a geometric regression is rejected before re-critique",
      url == URL0 and len(critiques) == 1
      and ("/static/videos/new.mp4", (URL0,)) in discards)

# D4 candidate fails to render.
_setup([F3], (False, "/static/videos/half.mp4", "boom"))
code, url, logs, findings, rounds = R._run_vision_qa(
    CODE0, URL0, LOGS0, "STEMAnimation", "l", "widescreen", "hybrid", allow_repair=True)
check("D4 a render failure keeps the incumbent and discards the half-artifact",
      url == URL0 and ("/static/videos/half.mp4", (URL0,)) in discards)

# D5 repair disabled: measurement only.
os.environ["VISION_QA_REPAIR"] = "0"
_setup([F3], (True, "x", "y"))
code, url, logs, findings, rounds = R._run_vision_qa(
    CODE0, URL0, LOGS0, "STEMAnimation", "l", "widescreen", "hybrid", allow_repair=True)
check("D5 VISION_QA_REPAIR=0 reports findings without touching the video",
      url == URL0 and len(findings) == 3 and rounds == 0 and discards == [])
del os.environ["VISION_QA_REPAIR"]

# D6 allow_repair=False (the parallel path): measurement only.
_setup([F3], (True, "x", "y"))
code, url, logs, findings, rounds = R._run_vision_qa(
    CODE0, URL0, LOGS0, "STEMAnimation", "l", "widescreen", "hybrid", allow_repair=False)
check("D6 report-only mode measures without repairing",
      url == URL0 and len(findings) == 3 and rounds == 0 and discards == [])

# D7 stage disabled: full pass-through, zero critiques.
os.environ["VISION_QA"] = "0"
_setup([F3], (True, "x", "y"))
code, url, logs, findings, rounds = R._run_vision_qa(
    CODE0, URL0, LOGS0, "STEMAnimation", "l", "widescreen", "hybrid", allow_repair=True)
check("D7 flag off: no critique, no findings, nothing changes",
      url == URL0 and findings == [] and critiques == [])
os.environ["VISION_QA"] = "1"

VQ.VisionQAStage.critique = _orig_critique

# ── E. render-failure classification (infra must never reach the repair agent) ──
check("E1 a TTS/provider outage classifies as infra",
      R._classify_render_failure("RuntimeError: All TTS services failed. Primary: ...")
      == "infra")
check("E2 a transport error classifies as infra",
      R._classify_render_failure("httpx.ConnectTimeout: timed out") == "infra")
check("E3 a LaTeX failure still classifies as latex (its own deterministic heal)",
      R._classify_render_failure("! LaTeX Error: File `foo.sty' not found") == "latex")
check("E4 an ordinary code error classifies as code (repairable)",
      R._classify_render_failure("NameError: name 'axes' is not defined") == "code")
check("E5 infra wins over a co-occurring LaTeX line (outages cascade)",
      R._classify_render_failure("! LaTeX Error: x\nAll TTS services failed") == "infra")

# ── F. voice-degradation markers surface from subprocess logs ──────────────
_deg = R._tts_degraded_lines(
    "rendering...\nTTS_DEGRADED: gtts-keyless keyed providers failed: 500\n"
    "more logs\nTTS_DEGRADED: silence ALL voice providers failed\n")
check("F1 TTS_DEGRADED markers are extracted from render logs", len(_deg) == 2)
check("F2 clean logs report no degradation", R._tts_degraded_lines("all good") == [])

# ── G. vision finding → scene attribution (scene-scoped repair input) ──────
_durations = {"/static/videos/a.mp4": 10.0, "/static/videos/b.mp4": 20.0,
              "/static/videos/c.mp4": 5.0}
VQ._probe_duration = lambda path: _durations[
    "/static/videos/" + os.path.basename(path)]
_real_exists, _real_vpath = os.path.exists, R._video_path
R._video_path = lambda url: url
os.path.exists = lambda p: p in _durations or _real_exists(p)

clips = list(_durations)
attributed = R._attribute_vision_findings([
    "LAYOUT_VIOLATION: vision-dead-frame t=5.0s early",     # clip a  (0-10)
    "LAYOUT_VIOLATION: vision-crowding t=12.0s middle",     # clip b  (10-30)
    "LAYOUT_VIOLATION: vision-low-contrast t=31.0s late",   # clip c  (30-35)
], clips)
check("G1 findings attribute to the clip whose time window contains them",
      sorted(attributed) == [0, 1, 2])
check("G2 timestamps are rebased to scene-local time for the repair brief",
      "t=2.0s" in attributed[1][0] and "t=1.0s" in attributed[2][0])
check("G3 a finding inside the first clip keeps its own timestamp",
      "t=5.0s" in attributed[0][0])

os.path.exists = lambda p: False
check("G4 missing clips ⇒ no attribution (never guess a scene to rewrite)",
      R._attribute_vision_findings(["LAYOUT_VIOLATION: vision-crowding t=1.0s x"],
                                   clips) is None)
os.path.exists = _real_exists

# ── H. scene-scoped vision repair: accept-if-better at the concat level ────
CLIPS = ["/static/videos/s1.mp4", "/static/videos/s2.mp4"]
SCRIPTS, SLOGS = ["s1 code", "s2 code"], ["", ""]
CONCAT = "/static/videos/concat_old.mp4"
V2 = ["LAYOUT_VIOLATION: vision-crowding t=1.0s a",
      "LAYOUT_VIOLATION: vision-dead-frame t=2.0s b"]


def _setup_scene_repair(critique_after, compile_ok=True, concat="/static/videos/concat_new.mp4",
                        cand_logs=""):
    del discards[:]
    R._attribute_vision_findings = lambda f, c: {0: [f[0]]}
    R.llm_available = lambda *a, **kw: True
    R.repair_code_with_gemini = lambda *a, **kw: "s1 repaired"
    R.sanitize_generated_code = lambda code, persona=None: code
    R.compile_manim_code = lambda *a, **kw: (compile_ok, "/static/videos/s1_new.mp4", cand_logs)
    R._concat_scene_clips = lambda clips: (concat, None) if concat else (None, "concat boom")
    R._discard_video = lambda url, keep=(): discards.append((url, tuple(keep)))
    R._store_repair_pair = lambda *a, **kw: None
    VQ.VisionQAStage.critique = lambda self, path: list(critique_after)


_real_attr = R._attribute_vision_findings
# H1 accept: findings drop 2 -> 1.
_setup_scene_repair(critique_after=V2[:1])
scripts, clips_out, logs_out, concat_out, findings, n = R._repair_scenes_vision(
    None, None, SCRIPTS, CLIPS, SLOGS, CONCAT, V2, "STEMAnimation", "l",
    "widescreen", "hybrid")
check("H1 improved concat is accepted; only the flagged scene was re-rendered",
      concat_out == "/static/videos/concat_new.mp4" and n == 1
      and scripts[0] == "s1 repaired" and scripts[1] == "s2 code"
      and len(findings) == 1)
check("H2 the superseded concat and replaced clip are discarded",
      (CONCAT, ("/static/videos/concat_new.mp4",)) in discards
      and any(u == "/static/videos/s1.mp4" for u, _ in discards))

# H3 reject: findings do not drop.
_setup_scene_repair(critique_after=V2)
scripts, clips_out, logs_out, concat_out, findings, n = R._repair_scenes_vision(
    None, None, SCRIPTS, CLIPS, SLOGS, CONCAT, V2, "STEMAnimation", "l",
    "widescreen", "hybrid")
check("H3 a non-improving re-concat is rejected; original video and clips survive",
      concat_out == CONCAT and n == 0 and scripts == SCRIPTS and clips_out == CLIPS
      and any(u == "/static/videos/concat_new.mp4" for u, _ in discards))

# H4 geometric regression in the candidate scene.
_setup_scene_repair(critique_after=V2[:1],
                    cand_logs="LAYOUT_VIOLATION: overlap play#1 a b\n")
scripts, clips_out, logs_out, concat_out, findings, n = R._repair_scenes_vision(
    None, None, SCRIPTS, CLIPS, SLOGS, CONCAT, V2, "STEMAnimation", "l",
    "widescreen", "hybrid")
check("H4 a scene candidate that adds geometric violations is rejected",
      concat_out == CONCAT and n == 0)

# H5 unattributable findings ⇒ report-only, nothing re-rendered.
_setup_scene_repair(critique_after=V2[:1])
R._attribute_vision_findings = lambda f, c: None
scripts, clips_out, logs_out, concat_out, findings, n = R._repair_scenes_vision(
    None, None, SCRIPTS, CLIPS, SLOGS, CONCAT, V2, "STEMAnimation", "l",
    "widescreen", "hybrid")
check("H5 unattributable findings stay report-only", concat_out == CONCAT and n == 0
      and discards == [])

R._attribute_vision_findings = _real_attr
R._video_path = _real_vpath
VQ.VisionQAStage.critique = _orig_critique

import shutil  # noqa: E402
shutil.rmtree(tmp, ignore_errors=True)

print(f"\n{len(PASS)}/{len(PASS) + len(FAIL)} checks passed")
sys.exit(1 if FAIL else 0)
