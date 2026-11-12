"""Acceptance harness for TTS resilience. No API keys, no network (httpx stubbed).

Pins the fixes for the 2026-07-21 outage, where OpenRouter's audio endpoint returned
HTTP 500 (and "200 OK with an empty body") for a few seconds, one cue's synthesis
failed, a scene died, and the whole parallel render fell back to sequential:

  A. Transient failures RETRY before the provider is declared dead; permanent ones
     (401/400) fail immediately — retrying a bad key is just latency.
  B. The fallback chain is primary → Gemini (keyed) → gTTS (KEYLESS) → silence
     (opt-in), so a keyed-provider outage can no longer kill a render, and every
     degraded tier prints a TTS_DEGRADED marker the server folds into the sidecar.

Run: .venv/bin/python stem_animation_lab/test_tts_resilience.py
"""
import io
import os
import sys
from contextlib import redirect_stdout

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import lessonforge.viz_helpers as VH  # noqa: E402  (pulls in manim; slow but keyless)

PASS, FAIL = [], []


def check(name, cond):
    (PASS if cond else FAIL).append(name)
    print(f"{'PASS' if cond else 'FAIL'} {name}")


class _Resp:
    def __init__(self, status_code, content=b"audio", text=""):
        self.status_code = status_code
        self.content = content
        self.text = text


# No real sleeping in a test harness.
VH.time.sleep = lambda *_a, **_k: None
os.environ["TTS_RETRY_ATTEMPTS"] = "3"


def _stub_post(responses):
    """Replace httpx.post with a scripted sequence; returns the call counter."""
    import httpx
    calls = {"n": 0}
    seq = list(responses)

    def fake_post(*_a, **_k):
        calls["n"] += 1
        item = seq.pop(0) if seq else seq_last[0]
        seq_last[0] = item
        if isinstance(item, Exception):
            raise item
        return item

    seq_last = [responses[-1] if responses else _Resp(200)]
    httpx.post = fake_post
    return calls


import httpx  # noqa: E402
_real_post = httpx.post

# ── A. retry semantics ──────────────────────────────────────────────────────
calls = _stub_post([_Resp(500, b"", "server error"), _Resp(200, b"realaudio")])
resp = VH._tts_post_with_retry("http://x", {}, {}, label="T")
check("A1 a 5xx blip retries and then succeeds",
      resp.content == b"realaudio" and calls["n"] == 2)

calls = _stub_post([_Resp(200, b""), _Resp(200, b"realaudio")])
resp = VH._tts_post_with_retry("http://x", {}, {}, label="T")
check("A2 '200 OK with empty body' is treated as transient and retried",
      resp.content == b"realaudio" and calls["n"] == 2)

calls = _stub_post([httpx.ConnectTimeout("timeout"), _Resp(200, b"realaudio")])
resp = VH._tts_post_with_retry("http://x", {}, {}, label="T")
check("A3 a transport timeout retries", resp.content == b"realaudio" and calls["n"] == 2)

calls = _stub_post([_Resp(500, b"", "down")])
try:
    VH._tts_post_with_retry("http://x", {}, {}, label="T")
    _gave_up = False
except Exception:
    _gave_up = True
check("A4 a persistent outage gives up after TTS_RETRY_ATTEMPTS",
      _gave_up and calls["n"] == 3)

calls = _stub_post([_Resp(401, b"", "bad key")])
try:
    VH._tts_post_with_retry("http://x", {}, {}, label="T")
    _failed_fast = False
except Exception:
    _failed_fast = True
check("A5 a permanent error (401) fails immediately, without retrying",
      _failed_fast and calls["n"] == 1)

calls = _stub_post([_Resp(429, b"", "slow down"), _Resp(200, b"realaudio")])
resp = VH._tts_post_with_retry("http://x", {}, {}, label="T")
check("A6 rate limiting (429) is retried", calls["n"] == 2)

httpx.post = _real_post

# ── B. fallback chain + degradation markers ─────────────────────────────────
def _svc(delegate=None):
    """A UniversalTTSService without SpeechService.__init__ side effects."""
    s = VH.UniversalTTSService.__new__(VH.UniversalTTSService)
    s.delegate = delegate
    s.speaker, s.language, s.model, s.api_key = "shubh", "hi-IN", "bulbul:v3", None
    return s


class _DeadDelegate:
    model, voice_name = "google/x", "Puck"

    def generate_from_text(self, *_a, **_k):
        raise RuntimeError("No audio content returned in model response")


SENTINEL = {"original_audio": "keyless.mp3"}

s = _svc()
s._generate_sarvam_direct = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("sarvam down"))
_real_gemini = VH.GeminiTTSService
VH.GeminiTTSService = lambda **kw: (_ for _ in ()).throw(RuntimeError("openrouter 500"))
s._generate_gtts_keyless = lambda *a, **k: SENTINEL
buf = io.StringIO()
with redirect_stdout(buf):
    out = s._synthesize("hello", "/tmp")
check("B1 keyed providers all failing falls through to the KEYLESS tier",
      out is SENTINEL)
check("B2 the keyless tier prints a TTS_DEGRADED marker for the sidecar",
      "TTS_DEGRADED: gtts-keyless" in buf.getvalue())

# A provider that was never configured is not a provider that failed: this box has no
# SARVAM key by design, and marking that as degradation would make voice_degraded
# nonzero on every render (observed live 2026-07-22 — a metric always red is ignored).
s = _svc()
s._generate_sarvam_direct = lambda *a, **k: (_ for _ in ()).throw(
    ValueError("SARVAM_AI_KEY is required for UniversalTTSService."))
VH.GeminiTTSService = lambda **kw: type("G", (), {
    "generate_from_text": lambda self, *a, **k: {"original_audio": "gemini.wav"}})()
buf = io.StringIO()
with redirect_stdout(buf):
    out = s._synthesize("hello", "/tmp")
check("B2a an UNCONFIGURED primary is not reported as degradation",
      out["original_audio"] == "gemini.wav" and "TTS_DEGRADED" not in buf.getvalue())

s = _svc()
s._generate_sarvam_direct = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("sarvam 503"))
buf = io.StringIO()
with redirect_stdout(buf):
    out = s._synthesize("hello", "/tmp")
check("B2b a primary that FAILED at runtime is reported as degradation",
      "TTS_DEGRADED: gemini-fallback" in buf.getvalue())

s = _svc(delegate=_DeadDelegate())
s._generate_gtts_keyless = lambda *a, **k: SENTINEL
_gemini_ctor_calls = {"n": 0}


def _count_ctor(**kw):
    _gemini_ctor_calls["n"] += 1
    raise RuntimeError("openrouter 500")


VH.GeminiTTSService = _count_ctor
with redirect_stdout(io.StringIO()):
    out = s._synthesize("hello", "/tmp")
check("B3 when Gemini WAS the primary, the dead endpoint is not re-tried as its own fallback",
      out is SENTINEL and _gemini_ctor_calls["n"] == 0)

s = _svc()
s._generate_sarvam_direct = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("sarvam down"))
VH.GeminiTTSService = lambda **kw: (_ for _ in ()).throw(RuntimeError("openrouter 500"))
s._generate_gtts_keyless = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("gtts down"))
try:
    with redirect_stdout(io.StringIO()):
        s._synthesize("hello", "/tmp")
    _raised = False
except RuntimeError:
    _raised = True
check("B4 with silence OFF (default), a total outage still fails LOUDLY", _raised)

os.environ["TTS_SILENT_FALLBACK"] = "1"
s._generate_silence = lambda *a, **k: {"original_audio": "silence.wav"}
buf = io.StringIO()
with redirect_stdout(buf):
    out = s._synthesize("hello", "/tmp")
check("B5 opt-in silence keeps the render alive as a last resort",
      out["original_audio"] == "silence.wav")
check("B6 silence is marked as the loudest degradation (no narration shipped)",
      "TTS_DEGRADED: silence" in buf.getvalue())
del os.environ["TTS_SILENT_FALLBACK"]

os.environ["TTS_KEYLESS_FALLBACK"] = "0"
s2 = _svc()
s2._generate_sarvam_direct = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("sarvam down"))
s2._generate_gtts_keyless = lambda *a, **k: SENTINEL
try:
    with redirect_stdout(io.StringIO()):
        s2._synthesize("hello", "/tmp")
    _off = False
except RuntimeError:
    _off = True
check("B7 TTS_KEYLESS_FALLBACK=0 disables the keyless tier", _off)
del os.environ["TTS_KEYLESS_FALLBACK"]

VH.GeminiTTSService = _real_gemini

# ── C. pacing tags never reach the fallback voices ─────────────────────────
s3 = _svc()
check("C1 pacing/bookmark tags are stripped before keyless synthesis",
      s3._clean_for_speech("[SPEED: SPRINT]Hello there[PAUSE: 300]") == "Hello there")

print(f"\n{len(PASS)}/{len(PASS) + len(FAIL)} checks passed")
sys.exit(1 if FAIL else 0)
