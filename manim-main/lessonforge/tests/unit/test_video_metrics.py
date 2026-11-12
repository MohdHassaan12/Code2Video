"""scripts/video_metrics.py: the one yardstick every video-quality step is measured with.

Free: tiny synthetic clips written with ffmpeg's lossless codec from numpy arrays (no voice, no GPU, no model). Skipped
when ffmpeg is not installed. Real baselines are in docs/engine/kits.md ("Video metrics").
"""
from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
import wave
from pathlib import Path

import numpy as np
import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "video_metrics.py"
spec = importlib.util.spec_from_file_location("video_metrics", SCRIPT)
vm = importlib.util.module_from_spec(spec)
sys.modules["video_metrics"] = vm
spec.loader.exec_module(vm)

needs_ffmpeg = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg not installed")
W, H = 640, 360
BG = (0x1C, 0x1F, 0x26)
GOLD = (0xFF, 0xE5, 0x66)


def blank():
    f = np.zeros((H, W, 3), np.uint8)
    f[:] = BG
    return f


def write_clip(path: Path, frames: list[np.ndarray], audio: np.ndarray | None = None, fps: int = 10) -> Path:
    """A lossless clip of ``frames`` (so no codec noise), with an optional mono 16 kHz audio track."""
    cmd = ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(fps), "-i", "-"]
    if audio is not None:
        wav = path.with_suffix(".wav")
        with wave.open(str(wav), "wb") as w:
            w.setnchannels(1), w.setsampwidth(2), w.setframerate(16000)
            w.writeframes((np.clip(audio, -1, 1) * 32767).astype(np.int16).tobytes())
        cmd += ["-i", str(wav), "-c:a", "pcm_s16le"]
    cmd += ["-c:v", "ffv1", str(path)]
    subprocess.run(cmd, input=b"".join(f.tobytes() for f in frames), check=True)
    return path


def box(frame, x, y, w, h, colour):
    frame[y:y + h, x:x + w] = colour
    return frame


# ---------------------------------------------------------------- moving and still

@needs_ffmpeg
def test_a_still_clip_is_all_still(tmp_path):
    clip = write_clip(tmp_path / "still.mkv", [box(blank(), 100, 100, 200, 100, (200, 200, 220))] * 50)
    m = vm.measure(clip)["motion"]
    for level in m["levels"].values():
        assert level["moving_share"] == 0.0
        assert level["longest_still_s"] == pytest.approx(4.9, abs=0.2)          # 50 frames = 49 steps
        assert level["still_3s_share"] == pytest.approx(1.0, abs=0.03)
    assert m["quiz_spans"] == []


@needs_ffmpeg
def test_a_fade_moves_only_while_it_fades(tmp_path):
    frames = [box(blank(), 200, 100, 200, 160, (0x1C + 4, 0x1F + 4, 0x26 + 4))] * 30
    for i in range(1, 11):                                                      # one second: 20 grey levels a step
        c = 30 + 20 * i
        frames.append(box(blank(), 200, 100, 200, 160, (c, c, c)))
    frames += [frames[-1]] * 30
    m = vm.measure(write_clip(tmp_path / "fade.mkv", frames))["motion"]
    med = m["levels"]["medium"]
    assert 9 <= round(med["moving_share"] * m["steps"]) <= 11
    assert med["longest_still_s"] == pytest.approx(2.9, abs=0.3)
    assert med["still_3s_s"] == 0.0 or med["still_3s_s"] < 6.2                  # two stills of about 3 s


@needs_ffmpeg
def test_a_sliding_box_is_moving_the_whole_time(tmp_path):
    frames = [box(blank(), 20 + 8 * i, 120, 100, 100, (240, 240, 240)) for i in range(60)]
    m = vm.measure(write_clip(tmp_path / "slide.mkv", frames))["motion"]
    for level in m["levels"].values():
        assert level["moving_share"] > 0.95
        assert level["longest_still_s"] <= 0.2


@needs_ffmpeg
def test_the_quiz_countdown_bar_is_masked_and_marks_a_quiz_span(tmp_path):
    base = box(blank(), 100, 100, 300, 100, (200, 200, 220))
    frames = [base] * 20
    for i in range(1, 31):                                                      # 3 s: a 600 px bar eats 20 px a step
        f = base.copy()
        box(f, 20, 300, 600 - 20 * i, 6, GOLD)
        frames.append(f)
    frames += [frames[-1]] * 20
    change = vm.step_changes(write_clip(tmp_path / "bar.mkv", frames))
    assert max(change["raw_counts"]) > 0 and any(change["bars"])               # the bar did move ...
    m = vm.motion_report(change)
    assert len(m["quiz_spans"]) == 1 and m["quiz_spans"][0][0] == pytest.approx(2.0, abs=0.3)
    assert m["quiz_s"] == pytest.approx(3.0, abs=0.4)
    assert m["levels"]["loose"]["moving_share"] == 0.0                          # ... and it is not counted as motion
    assert m["levels"]["loose"]["longest_still_s"] == pytest.approx(6.9, abs=0.3)
    assert m["levels"]["loose"]["longest_still_outside_quiz_s"] == pytest.approx(2.0, abs=0.3)   # the pause is cut out


def test_a_short_gold_flicker_is_not_a_quiz_and_is_not_masked():
    area = vm.SIZE[0] * vm.SIZE[1]
    counts = [0] * 10 + [200] + [0] * 10
    bars = [False] * 10 + [True] + [False] * 10
    m = vm.motion_report({"counts": counts, "raw_counts": [0] * 10 + [900] + [0] * 10, "bars": bars, "area": area})
    assert m["quiz_spans"] == [] and m["levels"]["medium"]["moving_share"] == pytest.approx(1 / 21, abs=1e-3)


def test_still_runs_and_quiz_subtraction():
    assert vm.still_runs([True, False, False, True, False]) == [(0.1, 0.3), (0.4, 0.5)]
    assert vm.quiz_spans([False, True, False, True, True, False, False, False, False, False, False, True]) == [(0.1, 0.5), (1.1, 1.2)]
    assert vm._minus((0.0, 10.0), [(2.0, 4.0), (9.0, 12.0)]) == [(0.0, 2.0), (4.0, 9.0)]


def test_pauses_from_the_timeline_count_as_still_whatever_the_bar_does():
    timeline = [{"start": 0.0, "duration": 10.0, "thinking_pause_seconds": 0.0},
                {"start": 10.0, "duration": 20.0, "thinking_pause_seconds": 5.0}]
    assert vm.pause_spans(timeline) == [(25.0, 30.0)] and vm.pause_spans([]) == []
    change = {"counts": [500] * 300, "raw_counts": [500] * 300, "bars": [False] * 300, "area": 320 * 180}
    plain = vm.motion_report(change)
    assert plain["moving_share"] == 1.0 and plain["quiz_spans"] == []
    held = vm.motion_report(change, pauses=vm.pause_spans(timeline))
    assert held["moving_share"] == pytest.approx(250 / 300, abs=1e-3)
    assert held["quiz_spans"] == [[25.0, 30.0]] and held["quiz_s"] == pytest.approx(5.0)
    assert held["levels"]["medium"]["longest_still_s"] == pytest.approx(5.0, abs=0.11)
    assert held["levels"]["medium"]["longest_still_outside_quiz_s"] == 0.0           # the pause is cut out of every still run


# ---------------------------------------------------------------- picture share

def test_card_ink_and_content_boxes():
    f = blank()
    box(f, 100, 60, 400, 250, vm.PAPER[0])                                      # a paper card, 100000 px of 230400
    box(f, 200, 120, 100, 100, (30, 30, 80))                                    # ink inside it
    look = vm.look_at(f)
    assert look["card"] == pytest.approx(100000 / 230400, abs=0.003)
    assert look["ink"] == pytest.approx(10000 / 230400, abs=0.003)
    assert look["content"] is None
    g = blank()
    box(g, 50, 100, 300, 200, (120, 170, 240))                                  # a dark-stage figure: no card
    box(g, 50, 5, 500, 20, (250, 250, 250))                                     # the header band is not counted
    look = vm.look_at(g)
    assert look["card"] is None and look["content"] == pytest.approx(300 * 200 / 230400, abs=0.003)


@needs_ffmpeg
def test_picture_report_over_a_clip(tmp_path):
    f = box(blank(), 100, 60, 400, 250, vm.PAPER[0])
    p = vm.picture_report(write_clip(tmp_path / "card.mkv", [f] * 45))
    assert p["looked_at"] >= 2 and p["card"]["median"] == pytest.approx(0.434, abs=0.01) and p["content"] is None


# ---------------------------------------------------------------- audio

def tone(seconds):
    t = np.arange(int(16000 * seconds)) / 16000
    return 0.3 * np.sin(2 * np.pi * 220 * t)


def test_silence_counts_only_long_quiet_runs():
    samples = np.concatenate([tone(2), np.zeros(16000), tone(2), np.zeros(int(16000 * 0.1)), tone(1)])
    s = vm.silence_of(samples, 16000)
    assert s["silent_s"] == pytest.approx(1.0, abs=0.1)                         # the 0.1 s breath is not silence
    assert s["silence_share"] == pytest.approx(1.0 / 6.1, abs=0.02)


@needs_ffmpeg
def test_silence_is_read_from_the_clip_audio(tmp_path):
    audio = np.concatenate([tone(2), np.zeros(16000), tone(2)])
    clip = write_clip(tmp_path / "talk.mkv", [blank()] * 50, audio=audio)
    assert vm.silence_report(clip)["silence_share"] == pytest.approx(0.2, abs=0.03)


# ---------------------------------------------------------------- premature reveals

VTT = """WEBVTT

00:00:01.000 --> 00:00:05.000
We push it with 30 newtons.

00:00:05.000 --> 00:00:09.000
Then it speeds up to 12 metres a second.
"""


def test_reveal_check_flags_a_number_printed_before_it_is_said(tmp_path):
    vtt = tmp_path / "c.vtt"
    vtt.write_text(VTT)
    cues = vm.read_vtt(vtt)
    assert [c["start"] for c in cues] == [1.0, 5.0] and cues[1]["text"].endswith("a second.")
    r = vm.reveal_check([{"value": "12", "seen": 5.0, "window": 4.0}, {"value": "30", "seen": 2.9, "window": 0.0},
                         {"value": "99", "seen": 1.0, "window": 0.0}, {"value": "12", "seen": 9.0, "window": 4.0}], cues)
    rows = {(x["value"], x["seen"]): x for x in r["rows"]}
    assert rows[("12", 5.0)]["flag"] == "premature" and rows[("12", 5.0)]["lead_s"] > 1.0     # printed at the sentence start
    assert rows[("30", 2.9)]["flag"] == ""                                                    # said about when it is shown
    assert rows[("99", 1.0)]["flag"] == "never spoken"
    assert rows[("12", 9.0)]["flag"] == "late"
    assert (r["premature"], r["late"], r["never_spoken"]) == (1, 1, 1)


def test_step_appearances_read_the_numbers_of_the_shown_text():
    sync = {"beats": [{"id": "03", "events": [{"kind": "figure", "time": 0.0, "action": "component 5"},
                                              {"kind": "step", "time": 4.0, "anchor_time": 4.2, "action": "Push 30 N, friction 12.5 N"},
                                              {"kind": "step", "time": 8.0, "action": "No number here"}]}]}
    got = vm.step_appearances(sync)
    assert [(g["value"], g["seen"], g["beat"]) for g in got] == [("30", 4.0, "03"), ("12.5", 4.0, "03")]
    assert vm.numbers_in("Triangle ABC, 3x2 and A1; 40 degrees, -5 and 2,5 and 1,200.5") == ["40", "-5", "2", "5", "1200.5"]


def test_preview_rows_read_sizes_per_beat():
    pv = {"stills": [{"what": "step", "beat": "01"},
                     {"what": "end", "chapter": 1, "beat": "01", "layout": {"mode": "top"},
                      "lines": [{"points": 48.0}, {"points": 44.0}], "picture": {"share": 0.4255, "type_points": 24.6}}]}
    assert vm.preview_rows(pv) == [{"chapter": 1, "beat": "01", "words_min_pt": 44.0, "words_max_pt": 48.0, "label_pt": 24.6,
                                    "card_share": 0.4255, "mode": "top"}]


# ---------------------------------------------------------------- the command

@needs_ffmpeg
def test_command_line_json_and_text(tmp_path, capsys):
    clip = write_clip(tmp_path / "still.mkv", [box(blank(), 100, 100, 200, 100, (200, 200, 220))] * 30,
                      audio=np.concatenate([tone(1.5), np.zeros(16000 * 1)] ))
    assert vm.main([str(clip), "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert {"video", "seconds", "motion", "picture", "silence"} <= set(data) and "reveals" not in data
    assert data["motion"]["moving_share"] == 0.0 and data["seconds"] == pytest.approx(3.0, abs=0.2)
    assert vm.main([str(clip)]) == 0
    assert "MOVING SHARE" in capsys.readouterr().out
    run = subprocess.run([sys.executable, str(SCRIPT), str(clip), "--json"], capture_output=True, text=True)
    assert run.returncode == 0 and json.loads(run.stdout)["primary"] == "medium"
