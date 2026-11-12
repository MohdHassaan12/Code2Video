"""The voices a lesson can be narrated in (2026-10-15, the owner: "add possible audios for generation video and also
controls to select audio possibilities ... give cost"): Microsoft's online voices, your own speech server over HTTP,
the learner's device reading the captions, and what each costs. No network: the services are stubbed."""
import io
import json
import shutil
import sys
import types
import wave

import pytest

from lessonforge import spend
from lessonforge.harness import service
from lessonforge.longform import audio, speech
from lessonforge.longform.contract import Lesson


@pytest.fixture
def ledger(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENROUTER_LEDGER", str(tmp_path / "spend.jsonl"))
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    return tmp_path / "spend.jsonl"


def a_wav(seconds: float = 0.5) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(24000)
        w.writeframes(b"\x10\x00" * int(24000 * seconds))
    return buf.getvalue()


def test_each_new_voice_is_a_spec_and_a_bad_one_is_refused():
    edge = speech.get_backend("edge:hi-IN-SwaraNeural/hinglish@-5%")
    assert (edge.name, edge.voice, edge.language, edge.rate) == ("edge", "hi-IN-SwaraNeural", "hinglish", "-5%")
    assert edge.devanagari and edge.cache_key() == "edge|hi-IN-SwaraNeural|-5%|deva1"
    assert not speech.get_backend("edge:en-IN-NeerjaNeural/en-IN").devanagari          # an English voice reads as written
    http = speech.get_backend("http:anika/hi-IN")
    assert (http.name, http.voice, http.language) == ("http", "anika", "hi-IN")
    browser = speech.get_backend("browser:hi-IN")
    assert browser.name == "browser" and browser.language == "hi-IN" and isinstance(browser, speech.SilentBackend)
    for bad in ("edge:not a voice", "edge:hi-IN-SwaraNeural@fast"):
        with pytest.raises(ValueError):
            speech.get_backend(bad)


def test_microsofts_voice_writes_its_clip_and_a_failure_is_the_lessons_next_voice(tmp_path, ledger, monkeypatch):
    said = []

    class Communicate:
        def __init__(self, text, voice, rate="+0%"):
            said.append((text, voice, rate))

        async def save(self, path):
            with open(path, "wb") as fh:
                fh.write(b"ID3" + b"\0" * 2048)
    monkeypatch.setitem(sys.modules, "edge_tts", types.SimpleNamespace(Communicate=Communicate))
    monkeypatch.setattr("time.sleep", lambda *_: None)
    dest = tmp_path / "clip.mp3"
    speech.get_backend("edge:en-IN-NeerjaNeural/en-IN").synthesize("Now we see how energy changes.", dest)
    assert dest.stat().st_size > 512 and said == [("Now we see how energy changes.", "en-IN-NeerjaNeural", "+0%")]
    assert spend.entries()[-1]["model"] == "edge/en-IN-NeerjaNeural" and spend.entries()[-1]["cost"] == 0.0

    class Refused(Communicate):
        async def save(self, path):
            raise ConnectionError("blocked")
    monkeypatch.setitem(sys.modules, "edge_tts", types.SimpleNamespace(Communicate=Refused))
    with pytest.raises(RuntimeError, match="Microsoft's voice service failed"):
        speech.get_backend("edge:en-IN-NeerjaNeural").synthesize("Again.", tmp_path / "again.mp3")


def test_a_hindi_voice_is_given_hinglish_with_its_hindi_in_devanagari(tmp_path, ledger, monkeypatch):
    said = []

    class Communicate:
        def __init__(self, text, voice, rate="+0%"):
            said.append(text)

        async def save(self, path):
            with open(path, "wb") as fh:
                fh.write(b"ID3" + b"\0" * 2048)
    monkeypatch.setitem(sys.modules, "edge_tts", types.SimpleNamespace(Communicate=Communicate))
    monkeypatch.setattr(speech, "voice_script", lambda text, llm=None: "अब देखते हैं kinetic energy.")
    speech.get_backend("edge:hi-IN-SwaraNeural/hinglish").synthesize("Ab dekhte hain kinetic energy.", tmp_path / "c.mp3")
    assert said[0].startswith("अब देखते हैं") and "kinetic energy" in said[0]


def test_your_own_speech_server_gets_text_voice_and_language_and_must_answer_with_audio(tmp_path, ledger, monkeypatch):
    sent = []

    class Answer:
        def __init__(self, code, content):
            self.status_code, self.content, self.text = code, content, ""
    answers = iter([Answer(200, a_wav())])
    monkeypatch.setattr("httpx.post", lambda url, headers=None, json=None, timeout=None: sent.append((url, headers, json)) or next(answers))
    monkeypatch.setenv("TTS_HTTP_URL", "http://voices.local/tts")
    monkeypatch.setenv("TTS_HTTP_KEY", "k")
    dest = tmp_path / "clip.audio"
    speech.get_backend("http:anika/hi-IN").synthesize("Namaste.", dest)
    assert dest.read_bytes()[:4] == b"RIFF"
    assert sent == [("http://voices.local/tts", {"Content-Type": "application/json", "X-API-Key": "k"},
                     {"text": "Namaste.", "voice": "anika", "language": "hi-IN"})]
    # a wrong key will not get better: no second try, and the lesson moves to its next voice
    answers = iter([Answer(401, b"no"), Answer(200, a_wav())])
    with pytest.raises(RuntimeError, match="your speech server failed"):
        speech.get_backend("http:anika").synthesize("Again.", tmp_path / "again.audio")
    assert next(answers).status_code == 200
    monkeypatch.delenv("TTS_HTTP_URL")
    with pytest.raises(RuntimeError, match="TTS_HTTP_URL"):
        speech.get_backend("http:anika").synthesize("No server.", tmp_path / "none.audio")


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg not installed")
def test_the_device_voice_is_silence_timed_to_the_words_and_nobody_is_paid_to_listen_to_it(tmp_path, monkeypatch):
    lesson = Lesson.model_validate({"title": "T", "thesis": "T.", "chapters": [{"id": 1, "title": "A", "beats": [
        {"id": "01", "narration": "Take a square of side x. Its area is x squared."}]}]})
    import lessonforge.longform as longform
    deaf = types.SimpleNamespace(align_best=lambda *a, **k: pytest.fail("a recogniser was asked to hear silence"))
    monkeypatch.setattr(audio, "_align_enabled", lambda opts: True)
    monkeypatch.setitem(sys.modules, "lessonforge.longform.align", deaf)
    monkeypatch.setattr(longform, "align", deaf, raising=False)
    report = audio.build_audio(lesson, tmp_path, "browser:en-IN", log=lambda *_: None)
    assert report["final_duration"] > 2.0
    timeline = json.loads((tmp_path / "timeline.json").read_text())
    assert timeline[0]["id"] == "01"


@pytest.fixture
def server_voices(monkeypatch, tmp_path):
    """A server with Microsoft's voices installed, no owner's service, no Kokoro, no paid key."""
    import importlib.util
    real = importlib.util.find_spec
    monkeypatch.setattr(importlib.util, "find_spec", lambda name, *a: object() if name == "edge_tts" else real(name, *a))
    for key in ("INDIC_TTS_URL", "INDIC_TTS_KEY", "SARVAM_AI_KEY", "OPENROUTER_API_KEY", "TTS_HTTP_URL", "TTS_HTTP_VOICES"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("KOKORO_MODEL", str(tmp_path / "absent.onnx"))


def test_the_voice_list_says_what_each_voice_costs_and_which_languages_it_speaks(server_voices, monkeypatch):
    listed = service.voices()
    rows = {r["id"]: r for r in listed["voices"]}
    assert {"edge:hi-IN-SwaraNeural", "edge:en-IN-NeerjaNeural", "edge:te-IN-ShrutiNeural", "edge:ta-IN-PallaviNeural",
            "gtts", "browser"} <= set(rows)
    assert all(r["cost"] and "usd_per_minute" in r and r["languages"] for r in rows.values())
    assert rows["edge:hi-IN-SwaraNeural"]["usd_per_minute"] == 0.0 and not rows["edge:hi-IN-SwaraNeural"]["paid"]
    assert listed["timing"]["usd_per_minute"] > 0
    assert "edge:en-IN-NeerjaNeural" not in {r["id"] for r in service.voices("hinglish")["voices"]}
    assert "edge:hi-IN-SwaraNeural" in {r["id"] for r in service.voices("hinglish")["voices"]}
    # a paid voice says so, with its measured price
    monkeypatch.setenv("OPENROUTER_API_KEY", "k")
    gemini = {r["id"]: r for r in service.voices()["voices"]}["gemini"]
    assert gemini["paid"] and gemini["usd_per_minute"] == pytest.approx(0.0136)
    # your own server, by the voice names you give it
    monkeypatch.setenv("TTS_HTTP_URL", "http://voices.local/tts")
    monkeypatch.setenv("TTS_HTTP_VOICES", "anika, ravi")
    assert {"http:anika", "http:ravi"} <= {r["id"] for r in service.voices()["voices"]}
    # switched off from the controls: Microsoft's voices leave the list
    monkeypatch.setenv("HARNESS_EDGE_VOICES", "0")
    assert not any(r["kind"] == "edge" for r in service.voices()["voices"])


def test_a_chosen_voice_is_tried_first_falls_back_like_any_other_and_must_speak_the_lessons_language(server_voices):
    assert service.voice_choice("EDGE:HI-IN-SWARANEURAL") == "edge:hi-IN-SwaraNeural"     # Microsoft's names keep their case
    assert service.voice_choice("edge:xx-YY-NobodyNeural") is None
    assert service.voice_candidates("hinglish", "edge:hi-IN-SwaraNeural")[0] == "edge:hi-IN-SwaraNeural/hinglish"
    assert service.voice_candidates("te-IN", "edge:te-IN-ShrutiNeural")[0] == "edge:te-IN-ShrutiNeural/te-IN"
    assert service.voice_candidates("hinglish", "edge:hi-IN-SwaraNeural")[-1] == "silent"
    # a Hindi voice is not used for an English lesson: the usual voices instead
    assert not any(c.startswith("edge:") for c in service.voice_candidates("en-IN", "edge:hi-IN-SwaraNeural"))
    # the device voice is the whole list: nothing to fail, nothing to fall back to; Hinglish captions in Indian English
    assert service.voice_candidates("hinglish", "browser") == ["browser:en-IN"]
    assert service.voice_candidates("hi-IN", "browser") == ["browser:hi-IN"]
    assert len(set(service.voice_candidates("hi-IN", "gtts"))) == len(service.voice_candidates("hi-IN", "gtts"))
    assert service.narrated("browser:en-IN") and service.narrated("edge:hi-IN-SwaraNeural/hinglish")
