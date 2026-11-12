"""Shared TTS cache acceptance test — no API keys, no manim render.

Pins the roadmap C-2 contract ("shared, content-addressed TTS cache"):
- a clip synthesized once is reused by every later render — a repair-round
  re-render bills ZERO TTS calls;
- the framework contract holds on a cache hit (audio lands in the per-render
  cache dir under the dict's original_audio name);
- different text or different voice config synthesizes fresh (no wrong hits);
- TTS_SHARED_CACHE_DISABLE=1 bypasses the layer;
- an unwritable shared dir is non-fatal (render proceeds, nothing raised).

Run: .venv/bin/python stem_animation_lab/test_tts_shared_cache.py
"""
import base64
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("SARVAM_AI_KEY", "test-key")
_tmp_root = tempfile.mkdtemp(prefix="tts_cache_test_")
os.environ["TTS_SHARED_CACHE"] = str(Path(_tmp_root) / "shared")
os.environ.pop("TTS_SHARED_CACHE_DISABLE", None)

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lessonforge.viz_helpers as vh  # noqa: E402

calls = {"n": 0}


class _FakeResp:
    def raise_for_status(self):
        pass

    def json(self):
        return {"audios": [base64.b64encode(b"RIFFfake-wav-bytes").decode()]}


def _fake_post(url, json=None, headers=None, timeout=None):
    calls["n"] += 1
    return _FakeResp()


vh.requests.post = _fake_post

checks = []


def check(name, cond):
    checks.append((name, bool(cond)))
    print(("PASS " if cond else "FAIL ") + name)


TEXT = "Namaste! [PAUSE] Aaj hum do bindu ke beech ki doori seekhenge."
svc_kwargs = dict(speaker="shubh", provider="sarvam", language="en-IN")

# render 1: fresh synthesis
render1 = Path(_tmp_root) / "media_render1" / "voiceovers"
render1.mkdir(parents=True)
svc1 = vh.UniversalTTSService(cache_dir=str(render1), **svc_kwargs)
r1 = svc1.generate_from_text(TEXT)
check("first render synthesizes exactly once", calls["n"] == 1)
check("result dict carries original_audio", bool(r1.get("original_audio")))
check("audio written into render-1 dir", (render1 / r1["original_audio"]).exists())

# render 2: a repair-round re-render — NEW per-render dir, NEW service instance
render2 = Path(_tmp_root) / "media_render2" / "voiceovers"
render2.mkdir(parents=True)
svc2 = vh.UniversalTTSService(cache_dir=str(render2), **svc_kwargs)
r2 = svc2.generate_from_text(TEXT)
check("repair re-render bills ZERO TTS calls", calls["n"] == 1)
check("cached audio copied into render-2 dir", (render2 / r2["original_audio"]).exists())
check("stable audio name across renders", r2["original_audio"] == r1["original_audio"])

# key discrimination: new text or new voice must NOT hit
svc2.generate_from_text("Bilkul naya vakya, alag audio chahiye.")
check("different text synthesizes fresh", calls["n"] == 2)
svc3 = vh.UniversalTTSService(cache_dir=str(render2), speaker="anushka",
                              provider="sarvam", language="en-IN")
svc3.generate_from_text(TEXT)
check("different speaker synthesizes fresh", calls["n"] == 3)

# disable knob
os.environ["TTS_SHARED_CACHE_DISABLE"] = "1"
render3 = Path(_tmp_root) / "media_render3" / "voiceovers"
render3.mkdir(parents=True)
svc4 = vh.UniversalTTSService(cache_dir=str(render3), **svc_kwargs)
svc4.generate_from_text(TEXT)
check("disable knob bypasses the shared cache", calls["n"] == 4)
del os.environ["TTS_SHARED_CACHE_DISABLE"]

# non-fatal: an unwritable shared dir must not fail the render
os.environ["TTS_SHARED_CACHE"] = "/proc/definitely-not-writable/tts"
svc5 = vh.UniversalTTSService(cache_dir=str(render3), **svc_kwargs)
r5 = svc5.generate_from_text("Ek aur naya vakya.")
check("unwritable shared cache is non-fatal", bool(r5.get("original_audio")))


# ── TTS_MUTE: visuals-only renders spend nothing ─────────────────────────────
# Layout/visual iteration re-renders the same board many times, and every tier of
# the voice chain is a metered edge. Muting must (a) bill nothing, (b) still hand
# manim_voiceover a realistic beat length, and — the one that bites — (c) leave the
# SHARED CACHE untouched in both directions. Its key is the request intent and does
# not record which tier answered, so storing silence under it would make the next
# REAL render silent: a money-saving flag turned into a poisoned cache.
os.environ["TTS_SHARED_CACHE"] = str(Path(_tmp_root) / "shared")
render4 = Path(_tmp_root) / "media_render4" / "voiceovers"
render4.mkdir(parents=True)
_before = calls["n"]

os.environ["TTS_MUTE"] = "1"
svc6 = vh.UniversalTTSService(cache_dir=str(render4), **svc_kwargs)
MUTE_TEXT = "Yeh ek bilkul naya muted vakya hai jise kabhi synthesize nahi karna chahiye."
r6 = svc6.generate_from_text(MUTE_TEXT)
check("muted render bills ZERO TTS calls", calls["n"] == _before)
check("muted render still returns playable audio", bool(r6.get("original_audio"))
      and (render4 / r6["original_audio"]).exists())

# Beat timing must survive: silence is sized from the word count, so a long cue
# yields a long beat and sustain/entrance pacing behave as they do in production.
short = svc6.generate_from_text("Do shabd.")
long_ = svc6.generate_from_text(" ".join(["shabd"] * 120))
_dur = lambda res: (render4 / res["original_audio"]).stat().st_size
check("silence is sized to the narration (long cue > short cue)", _dur(long_) > _dur(short) * 3)

# The poisoning check: a REAL service asking for the same text must synthesize,
# not inherit the muted silence.
os.environ.pop("TTS_MUTE", None)
render5 = Path(_tmp_root) / "media_render5" / "voiceovers"
render5.mkdir(parents=True)
_before_real = calls["n"]
svc7 = vh.UniversalTTSService(cache_dir=str(render5), **svc_kwargs)
svc7.generate_from_text(MUTE_TEXT)
check("a muted run never poisons the shared cache for real renders",
      calls["n"] == _before_real + 1)

# And muting is loud: the sidecar counts TTS_DEGRADED markers, so a silent video
# can never look clean (same reason TTS_SILENT_FALLBACK defaults off).
check("TTS_MUTE is off by default", vh._tts_muted() is False)
os.environ["TTS_MUTE"] = "1"
check("TTS_MUTE=1 is detected", vh._tts_muted() is True)
os.environ.pop("TTS_MUTE", None)

failed = [n for n, ok in checks if not ok]
print(f"\n{len(checks) - len(failed)}/{len(checks)} checks passed")
sys.exit(1 if failed else 0)
