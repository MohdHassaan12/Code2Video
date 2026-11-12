"""The owner's own speech service (``longform/speech.IndicBackend``): one narrator for the whole lesson, or none. No network."""
import io
import wave

import httpx
import pytest

from lessonforge.longform import speech


def wav(seconds=1.0, rate=24000):
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"\xd0\x07" * int(rate * seconds))      # loud enough to be a voice (the backend re-asks a silent clip)
    return buffer.getvalue()


class Reply:
    def __init__(self, status=200, content=b"", text=""):
        self.status_code, self.content, self.text = status, content, text


@pytest.fixture
def service(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENROUTER_LEDGER", str(tmp_path / "spend.jsonl"))
    monkeypatch.setenv("INDIC_TTS_URL", "https://speech.example/")
    monkeypatch.setenv("INDIC_TTS_KEY", "k-test")
    monkeypatch.setattr("time.sleep", lambda seconds: None)
    return tmp_path


def test_a_block_goes_out_whole_with_the_key_a_voice_and_a_seed(service, monkeypatch):
    sent = []

    def post(url, headers=None, json=None, timeout=None):
        sent.append((url, headers, json))
        return Reply(content=wav(4.0))

    monkeypatch.setattr(httpx, "post", post)
    backend = speech.get_backend("indic:maitri")
    assert isinstance(backend, speech.IndicBackend) and backend.cache_key() == "indic|maitri|0.4|7"
    backend.synthesize("यह हमारे गाल की एक cell है। बाहर एक पतली सी boundary है।", service / "a.wav")
    url, headers, body = sent[0]
    assert url == "https://speech.example/tts" and headers["X-API-Key"] == "k-test" and len(sent) == 1
    assert body == {"text": "यह हमारे गाल की एक cell है। बाहर एक पतली सी boundary है।", "speaker": "maitri", "temperature": 0.4, "seed": 7}
    samples, rate = speech.read_wav(service / "a.wav")
    assert rate == 24000 and abs(len(samples) / rate - 4.0) < 0.01
    row = (service / "spend.jsonl").read_text()
    assert '"cost": 0.0' in row and "indic/maitri" in row and "not in this budget" in row     # seen in the ledger, never charged to the cap
    assert speech.get_backend("indic:kavya@0.6").temperature == 0.6 and speech.get_backend("indic").speaker == "kavya"
    with pytest.raises(ValueError):
        speech.get_backend("indic:someone")


def test_a_long_block_is_cut_at_sentence_ends_and_joined(service, monkeypatch):
    sent = []

    def post(url, headers=None, json=None, timeout=None):
        sent.append(json["text"])
        return Reply(content=wav(2.0))

    monkeypatch.setattr(httpx, "post", post)
    monkeypatch.setattr(speech.IndicBackend, "MAX_CHARS", 60)
    speech.get_backend("indic:kavya").synthesize("Pehla sentence yahan khatam hota hai. Doosra sentence bhi yahan hai. Teesra bhi hai.", service / "b.wav")
    assert len(sent) >= 2 and all(len(piece) <= 60 and piece.endswith("hai.") for piece in sent)
    samples, rate = speech.read_wav(service / "b.wav")
    assert abs(len(samples) / rate - 2.0 * len(sent)) < 0.01


def test_a_failed_clip_raises_so_a_lesson_never_changes_narrator(service, monkeypatch):
    calls = []

    def flaky(url, headers=None, json=None, timeout=None):
        calls.append(1)
        return Reply(status=502, text="generation failed") if len(calls) < 3 else Reply(content=wav(0.8))

    monkeypatch.setattr(httpx, "post", flaky)
    speech.get_backend("indic:kavya").synthesize("Ek sentence.", service / "c.wav")     # a 502 is tried again, as its page says
    assert len(calls) == 3
    calls.clear()
    monkeypatch.setattr(httpx, "post", lambda url, **kw: calls.append(1) or Reply(status=401, text="bad key"))
    with pytest.raises(RuntimeError, match="401"):
        speech.get_backend("indic:kavya").synthesize("Ek sentence.", service / "d.wav")
    assert len(calls) == 1                                                             # a wrong key will not get better
    monkeypatch.setattr(httpx, "post", lambda url, **kw: Reply(status=200, content=b"<html>tunnel error</html>"))
    with pytest.raises(RuntimeError, match="no audio"):
        speech.get_backend("indic:kavya").synthesize("Ek sentence.", service / "e.wav")
    assert speech.get_backend("indic:kavya").plausible(b"not a wav", "Ek sentence.") > 0
    monkeypatch.delenv("INDIC_TTS_KEY")
    with pytest.raises(RuntimeError, match="INDIC_TTS_URL and INDIC_TTS_KEY"):
        speech.get_backend("indic:kavya").synthesize("Ek sentence.", service / "f.wav")


# ── the owner, 2026-10-09: use OUR audio API for every lesson, and ask it again when a clip is wrong ──────────

HINGLISH = "Yeh hamare gaal ki ek cell hai. Bahar ek patli si boundary hai, aur andar three parts hain."
DEVA = "यह हमारे गाल की एक cell है। बाहर एक पतली सी boundary है, और अंदर three parts हैं।"


def test_a_hinglish_block_is_put_into_devanagari_for_the_voice_and_the_english_words_stay(service, monkeypatch):
    monkeypatch.setenv("LESSONFORGE_HOME", str(service / "ws"))
    asked, sent = [], []

    def model(prompt, system):
        asked.append((prompt, system))
        return {"text": DEVA}

    assert speech.voice_script(HINGLISH, llm=model) == DEVA
    assert asked[0][0] == HINGLISH and "Leave every ENGLISH word exactly as it is" in asked[0][1]
    assert speech.voice_script(HINGLISH, llm=lambda p, s: 1 / 0) == DEVA and len(asked) == 1      # kept by the text: asked once
    monkeypatch.setattr(speech, "voice_script", lambda text, llm=None: DEVA)
    monkeypatch.setattr(httpx, "post", lambda url, headers=None, json=None, timeout=None:
                        sent.append(json["text"]) or Reply(content=wav(len(json["text"].split()) / 3.0)))   # read at three words a second
    backend = speech.get_backend("indic:kavya/hinglish")
    assert backend.language == "hinglish" and backend.cache_key().endswith("|deva1")
    backend.synthesize(HINGLISH, service / "h.wav")
    assert sent == [DEVA]                                             # the voice is handed Devanagari, the lesson keeps its own text
    sent.clear()
    speech.get_backend("indic:kavya/hi-IN").synthesize(DEVA, service / "d.wav")
    speech.get_backend("indic:kavya/en-IN").synthesize("This is an English lesson about cells.", service / "e.wav")
    speech.get_backend("indic:kavya").synthesize(HINGLISH, service / "plain.wav")
    assert sent == [DEVA, "This is an English lesson about cells.", HINGLISH]   # already Devanagari, English, or no language given: as written


def test_a_rewrite_that_changed_the_words_is_not_spoken(service, monkeypatch):
    monkeypatch.setenv("LESSONFORGE_HOME", str(service / "ws"))
    for bad in ("Yeh hamare gaal ki ek cell hai. Bahar ek boundary hai.",                 # no Devanagari at all
                "यह हमारे गाल की एक कोशिका है। बाहर एक पतली सी सीमा है, और अंदर तीन भाग हैं।",   # translated the English terms away
                "यह cell है।",                                                              # dropped most of the block
                DEVA + " यह 3 parts हैं।"):                                                  # another sentence, and a digit
        monkeypatch.setenv("LESSONFORGE_HOME", str(service / ("ws" + str(abs(hash(bad))))))
        assert speech.voice_script(HINGLISH, llm=lambda p, s, bad=bad: {"text": bad}) is None, bad
    assert speech.voice_script(HINGLISH, llm=lambda p, s: 1 / 0) is None and speech.voice_script("") is None


def test_a_clip_plainly_wrong_for_its_words_is_asked_for_again_with_another_seed(service, monkeypatch):
    seeds, answers = [], iter([wav(0.4), wav(60.0), wav(4.0)])       # ten words: cut off, far too long, about right

    def post(url, headers=None, json=None, timeout=None):
        seeds.append(json["seed"])
        return Reply(content=next(answers))

    monkeypatch.setattr(httpx, "post", post)
    text = "Is chhoti si cell ko oxygen andar leni hai aur waste."
    speech.get_backend("indic:kavya").synthesize(text, service / "r.wav")
    samples, rate = speech.read_wav(service / "r.wav")
    assert seeds == [7, 8, 9] and abs(len(samples) / rate - 4.0) < 0.01   # the third try is kept
    seeds.clear()
    monkeypatch.setattr(httpx, "post", lambda url, **kw: seeds.append(kw["json"]["seed"]) or Reply(content=wav(0.4)))
    speech.get_backend("indic:kavya").synthesize(text, service / "s.wav")  # never right: the best of three is used, nothing raises
    assert seeds == [7, 8, 9]

