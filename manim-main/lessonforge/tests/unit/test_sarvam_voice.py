"""The Sarvam voice (``longform/speech.SarvamBackend``): one narrator for the whole lesson, or none. No network."""
import base64
import io
import wave

import httpx
import pytest

from lessonforge.harness import service
from lessonforge.longform import speech


def clip(seconds=1.0, rate=22050):
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"\x01\x00" * int(rate * seconds))
    return base64.b64encode(buffer.getvalue()).decode()


class Reply:
    def __init__(self, status=200, audio=None, text=""):
        self.status_code, self._audio, self.text = status, audio, text

    def json(self):
        return {"audios": [self._audio], "request_id": "r"}


@pytest.fixture
def ledger(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENROUTER_LEDGER", str(tmp_path / "spend.jsonl"))
    monkeypatch.setenv("SARVAM_AI_KEY", "sk-test")
    return tmp_path


def test_a_block_is_spoken_in_one_voice_and_long_text_is_cut_at_sentence_ends(ledger, monkeypatch):
    sent = []

    def post(url, headers=None, json=None, timeout=None):
        sent.append((url, headers, json))
        return Reply(audio=clip(1.0))
    monkeypatch.setattr(httpx, "post", post)
    backend = speech.get_backend("sarvam:shubh/hi-IN")
    assert isinstance(backend, speech.SarvamBackend) and backend.cache_key() == "sarvam|bulbul:v3|shubh|hi-IN|1"
    backend.synthesize("Ek roti lijiye. Ise do equal parts mein kaatiye.", ledger / "a.wav")
    url, headers, payload = sent[0]
    assert url == speech.SarvamBackend.URL and headers["api-subscription-key"] == "sk-test" and len(sent) == 1
    assert payload == {"text": "Ek roti lijiye. Ise do equal parts mein kaatiye.", "target_language_code": "hi-IN",
                       "speaker": "shubh", "model": "bulbul:v3", "pace": 1.0}
    with wave.open(str(ledger / "a.wav")) as w:
        assert w.getframerate() == 22050 and abs(w.getnframes() / 22050 - 1.0) < 0.01
    # longer than one request: cut between sentences, joined into one file, nothing dropped
    sent.clear()
    sentence = "Har part ko one fourth kehte hain aur yeh one half se chhota hota hai."
    long_text = " ".join([sentence] * 60)
    backend.synthesize(long_text, ledger / "b.wav")
    assert len(sent) == 4 and " ".join(p[2]["text"] for p in sent) == long_text          # about 4200 characters
    assert all(len(p[2]["text"]) <= speech.SarvamBackend.MAX_CHARS and p[2]["text"].endswith("hai.") for p in sent)
    with wave.open(str(ledger / "b.wav")) as w:
        assert abs(w.getnframes() / 22050 - 4.0) < 0.01
    # the usage is on the ledger at zero dollars: Sarvam bills it, not the OpenRouter budget
    from lessonforge import spend
    rows = spend.entries()
    assert len(rows) == 2 and all(r["model"] == "sarvam/bulbul:v3" and r["cost"] == 0 and "billed by Sarvam" in r["note"] for r in rows)
    assert speech.get_backend("sarvam:anushka/en-IN@0.9").pace == 0.9


def test_a_failed_call_raises_so_the_whole_lesson_moves_to_the_next_voice(ledger, monkeypatch):
    monkeypatch.setattr(httpx, "post", lambda *a, **k: Reply(status=403, text='{"error":"invalid key"}'))
    with pytest.raises(RuntimeError, match="Sarvam TTS HTTP 403"):
        speech.get_backend("sarvam:shubh/hi-IN").synthesize("Ek roti lijiye.", ledger / "x.wav")
    assert not (ledger / "x.wav").exists()
    monkeypatch.delenv("SARVAM_AI_KEY")
    with pytest.raises(RuntimeError, match="SARVAM_AI_KEY is not set"):
        speech.get_backend("sarvam:shubh/hi-IN").synthesize("Ek roti lijiye.", ledger / "x.wav")


def test_the_owners_own_voice_comes_first_and_a_paid_voice_only_when_it_is_asked_for(monkeypatch):
    """"Don't use audio credits like Gemini … or give an option to select these things" (the owner, 2026-10-09)."""
    for name in ("HARNESS_VOICE", "HARNESS_PAID_VOICES", "HARNESS_INDIC_SPEAKER", "KOKORO_MODEL"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("SARVAM_AI_KEY", "sk-test")
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or")
    monkeypatch.setenv("INDIC_TTS_URL", "https://voice.example")
    monkeypatch.setenv("INDIC_TTS_KEY", "k")
    order = service.voice_candidates("hinglish")
    assert order[0] == "indic:kavya/hinglish" and order[-2:] == ["gtts:hi", "silent"]
    assert not any(v.startswith(("sarvam:", "gemini:")) for v in order)          # nothing paid unless asked for
    assert speech.get_backend(order[0]).speaker == "kavya"
    # a voice chosen for one lesson: another of ours, or a paid one with ours behind it
    assert service.voice_candidates("hinglish", "indic:maitri")[0] == "indic:maitri/hinglish"
    asked = service.voice_candidates("hinglish", "gemini")
    assert asked[0].startswith("gemini:") and asked[1] == "indic:kavya/hinglish" and not any(v.startswith("sarvam:") for v in asked)
    assert service.voice_candidates("en-IN", "sarvam")[:2] == ["sarvam:shubh/en-IN@0.75", "indic:kavya/en-IN"]
    assert service.voice_candidates("hinglish", "somebody else") == order and service.voice_choice("INDIC:Vinaya") == "indic:vinaya"
    # the app is told what exists, ours first, the paid ones marked, and nothing of where the service lives
    listed = service.voices()
    # the owner's own voices first, the paid ones last; the free voices added on 2026-10-15 (Microsoft's, the
    # machine's, Google basic, the learner's device) sit between and are never marked paid
    ids = [v["id"] for v in listed["voices"]]
    assert ids[:4] == ["indic:kavya", "indic:agastya", "indic:maitri", "indic:vinaya"] and ids[-2:] == ["sarvam", "gemini"]
    assert [v["id"] for v in listed["voices"] if v["paid"]] == ["sarvam", "gemini"] and listed["default"] == "indic:kavya"
    assert listed["paid_by_default"] is False and "voice.example" not in str(listed)
    # switched on for every lesson: ours is still first
    monkeypatch.setenv("HARNESS_PAID_VOICES", "1")
    every = service.voice_candidates("hinglish")
    assert every[0] == "indic:kavya/hinglish" and every[1].startswith("sarvam:") and every[2].startswith("gemini:")
    monkeypatch.setenv("HARNESS_INDIC_SPEAKER", "agastya")
    assert service.voice_candidates("hi-IN")[0] == "indic:agastya/hi-IN" and service.voices()["default"] == "indic:agastya"


def test_sarvam_is_tried_first_when_its_key_is_set(monkeypatch):
    monkeypatch.setenv("SARVAM_AI_KEY", "sk-test")
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or")
    monkeypatch.delenv("HARNESS_VOICE", raising=False)
    for name in ("INDIC_TTS_URL", "INDIC_TTS_KEY", "HARNESS_PAID_VOICES"):       # a server without the owner's service
        monkeypatch.delenv(name, raising=False)
    order = service.voice_candidates("hinglish")
    assert order[0] == "sarvam:shubh/hi-IN@0.75" and order[1].startswith("gemini:") and order[-1] == "silent"
    assert service.voice_candidates("en-IN")[0] == "sarvam:shubh/en-IN@0.75"
    assert speech.get_backend(order[0]).pace == 0.75 and speech.get_backend(order[0]).language == "hi-IN"
    monkeypatch.setenv("HARNESS_SARVAM_PACE", "0.9")
    monkeypatch.setenv("HARNESS_SARVAM_SPEAKER", "anushka")
    assert service.voice_candidates("te-IN")[0] == "sarvam:anushka/te-IN@0.9"
    monkeypatch.delenv("SARVAM_AI_KEY")
    assert service.voice_candidates("hinglish")[0].startswith("gemini:")


def test_an_empty_hearing_is_asked_again_and_never_kept(tmp_path, monkeypatch):
    """Three Hindi hearings of one lesson came back with no words (HTTP 200) and were cached as that: two of its
    three blocks were then timed by estimate. The same clip was heard correctly a minute later."""
    from lessonforge.longform import align
    wav = tmp_path / "clip.wav"
    with wave.open(str(wav), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(24000)
        w.writeframes(b"\x01\x00" * 24000 * 3)
    text = "Ek roti lijiye. Ise do equal parts mein kaatiye."
    words = [{"word": word, "start": i * 0.3, "end": i * 0.3 + 0.25} for i, word in enumerate(text.replace(".", "").split())]
    answers = [[], words]
    calls = []
    asked = []
    monkeypatch.setattr(align, "transcribe_words", lambda wav, language=None, model=None: (
        calls.append(language), asked.append(model), answers.pop(0) if answers else [])[2])
    cache = tmp_path / "clip.words.hi.json"
    result = align.align_clip(text, wav, language="hi", cache=cache)
    assert calls == ["hi", "hi"] and result and result["trusted"] and cache.exists()
    # the second hearing is asked of the model whose providers all return word times: one provider of the first
    # never does, and asking the first again went to that provider twelve times in a row
    assert asked == [align.STT_MODEL, align.STT_SECOND] and align.STT_SECOND != align.STT_MODEL
    # a hearing that stays empty is not written down, so the next build asks again; an old empty file is not trusted
    cache.unlink()
    calls.clear()
    assert align.align_clip(text, wav, language="hi", cache=cache) is None and not cache.exists()
    assert calls == ["hi"] * len(align.STT_ORDER)
    cache.write_text("[]")
    answers.append(words)
    calls.clear()
    assert align.align_clip(text, wav, language="hi", cache=cache)["trusted"] and calls == ["hi"]


def test_the_same_words_in_the_same_voice_are_paid_for_once_across_lessons(tmp_path, monkeypatch):
    """One 2000-word script was narrated three times in an afternoon (a restart, then two re-runs): each lesson
    kept its clips in its own folder. Remaking or editing a script now buys only the blocks that changed."""
    from lessonforge.longform import audio
    from lessonforge.longform.contract import Lesson
    monkeypatch.setenv("LESSONFORGE_HOME", str(tmp_path / "workspace"))
    monkeypatch.setenv("LESSONFORGE_ALIGN", "0")
    spoken = []

    class Paid(speech.SilentBackend):
        name = "paid"

        def cache_key(self):
            return "paid|voice-a"

        def synthesize(self, text, dest):
            spoken.append(text)
            super().synthesize(text, dest)

    def lesson(*lines):
        return Lesson.model_validate({"title": "T", "chapters": [{"id": 1, "title": "One", "beats": [
            {"id": f"{i:02}", "narration": line} for i, line in enumerate(lines, 1)]}]})

    one, two = "Ek roti lijiye aur use do equal parts mein kaatiye.", "Har part ko one half kehte hain."
    first = audio.build_audio(lesson(one, two), tmp_path / "a", Paid(), log=lambda *_: None)
    assert spoken == [one, two] and first["clips_synthesized"] == 2 and first["clips_reused_from_other_lessons"] == 0
    # the same script in a NEW lesson folder: nothing is bought again
    log = []
    again = audio.build_audio(lesson(one, two), tmp_path / "b", Paid(), log=log.append)
    assert spoken == [one, two] and again["clips_synthesized"] == 0 and again["clips_reused_from_other_lessons"] == 2
    assert any("already paid for" in line for line in log) and again["final_duration"] == first["final_duration"]
    # one paragraph edited: only that one is bought
    edited = audio.build_audio(lesson(one, two + " Yaad rakhiye."), tmp_path / "c", Paid(), log=lambda *_: None)
    assert spoken[-1] == two + " Yaad rakhiye." and len(spoken) == 3 and edited["clips_reused_from_other_lessons"] == 1
    # another voice setting is another clip; a free voice is never kept; and it can be switched off
    class Other(Paid):
        def cache_key(self):
            return "paid|voice-b"
    audio.build_audio(lesson(one), tmp_path / "d", Other(), log=lambda *_: None)
    assert len(spoken) == 4
    audio.build_audio(lesson(one), tmp_path / "e", "silent", log=lambda *_: None)
    assert not any("silent" in p.name for p in (tmp_path / "workspace" / "cache" / "speech").glob("*"))
    monkeypatch.setenv("LESSONFORGE_SPEECH_CACHE", "0")
    audio.build_audio(lesson(one), tmp_path / "f", Paid(), log=lambda *_: None)
    assert len(spoken) == 5
