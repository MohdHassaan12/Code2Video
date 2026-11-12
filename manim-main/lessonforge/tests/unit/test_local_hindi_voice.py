"""The voice on this machine for a Hindi or Hinglish lesson, when the owner's speech service cannot be reached
(their word, 2026-10-12: "deploy some TTS as a fallback … but don't use the TTS of OpenRouter").

What a recogniser heard when it listened to the first tries is what is pinned: the language-switch markers were spoken
("in right atrium hi se"), and Hindi left in Latin letters was read by English rules ("karke" as "cock").
"""
import numpy as np
import pytest

from lessonforge.harness import service
from lessonforge.longform import hinglish, speech


def test_hindi_words_are_written_by_their_sounds_and_english_words_stay(monkeypatch):
    assert [hinglish.to_devanagari(w) for w in ("karke", "rahega", "rakho", "logon", "karen", "hain", "kyunki", "Ek")] == \
        ["कर्के", "रहेगा", "रखो", "लोगों", "करें", "हैं", "क्योंकि", "एक"]
    monkeypatch.setattr(hinglish, "english", lambda: frozenset({"balloon", "inflate", "neck", "pinch", "shut", "release", "predict", "air"}))
    said = "Ek balloon lo, inflate karke neck pinch shut rakho. Release karne se पहले predict karo: CO2 air nikle?"
    assert hinglish.rest_in_devanagari(said) == "एक balloon लो, inflate कर्के neck pinch shut रखो. Release कर्ने से पहले predict करो: CO2 air निक्ले?"
    assert hinglish.latin_hindi_left(said) == ["Ek", "lo", "karke", "rakho", "karne", "se", "karo", "nikle"]
    # a machine with no English word list cannot tell the two apart: nothing is touched
    monkeypatch.setattr(hinglish, "english", lambda: frozenset())
    assert hinglish.rest_in_devanagari(said) == said and hinglish.latin_hindi_left(said) == []


def test_only_small_letter_entries_of_the_word_list_are_english(tmp_path, monkeypatch):
    words = tmp_path / "words"
    words.write_text("Se\nKaro\npinch\nshut\nNASA\nwell's\n", encoding="utf-8")
    monkeypatch.setattr(hinglish, "_LISTS", (str(words),))
    hinglish.english.cache_clear()
    try:
        assert hinglish.english() == frozenset({"pinch", "shut"})       # "Se" (selenium) made "se" English: read as "see"
    finally:
        hinglish.english.cache_clear()


class Engine:
    """Stands in for the Kokoro model: remembers what it was asked to speak."""

    def __init__(self):
        self.asked = []
        self.tokenizer = type("T", (), {"vocab": set("abcdefghijklmnopqrstuvwxyz ,.?ˈˌːɛɔʌɪʊəɹɾʃŋ̃")})()

    def create(self, text, voice=None, speed=1.0, lang=None, is_phonemes=False):
        self.asked.append({"text": text, "voice": voice, "lang": lang, "is_phonemes": is_phonemes})
        return np.zeros(2400, dtype=np.float32), 24000


def test_a_hindi_voice_is_given_sounds_with_no_language_marker_and_devanagari_for_its_hindi(tmp_path, monkeypatch):
    pytest.importorskip("phonemizer")
    pytest.importorskip("kokoro_onnx")
    hindi, english = speech.get_backend("kokoro:hf_alpha@0.85"), speech.get_backend("kokoro")
    assert (hindi.lang, hindi.hindi, english.lang, english.hindi) == ("hi", True, "en-us", False)
    assert hindi.cache_key() != speech.KokoroBackend(voice="hf_alpha", speed=0.85, lang="en-us").cache_key()
    turned = []
    monkeypatch.setattr(speech, "voice_script", lambda text, llm=None: turned.append(text) or "दिल के चार chambers hote हैं।")
    monkeypatch.setattr(hinglish, "english", lambda: frozenset({"chambers"}))
    hindi._engine = Engine()
    try:
        hindi.synthesize("Dil ke chaar chambers hote hain.", tmp_path / "a.wav")
    except RuntimeError as exc:                              # no espeak library on this machine
        pytest.skip(str(exc)[:80])
    asked = hindi._engine.asked[0]
    assert turned == ["Dil ke chaar chambers hote hain."] and asked["is_phonemes"] and asked["voice"] == "hf_alpha"
    assert "(" not in asked["text"] and ")" not in asked["text"]                 # "(en)" and "(hi)" were spoken as letters
    assert "tʃˈeɪmbəz" in asked["text"] or "chambers" not in asked["text"]       # the English word by English rules
    assert (tmp_path / "a.wav").is_file()
    # a block already in Devanagari is not sent anywhere to be turned
    hindi.synthesize("दिल के चार chambers होते हैं।", tmp_path / "b.wav")
    assert len(turned) == 1
    # an English voice is asked as before: the words themselves, by the model's own rules
    english._engine = Engine()
    english.synthesize("The heart has four chambers.", tmp_path / "c.wav")
    assert english._engine.asked[0] == {"text": "The heart has four chambers.", "voice": "af_heart", "lang": "en-us", "is_phonemes": False}


def test_the_voice_on_this_machine_comes_before_the_basic_voice(tmp_path, monkeypatch):
    model = tmp_path / "kokoro-v1.0.onnx"
    model.write_bytes(b"x")
    monkeypatch.setenv("KOKORO_MODEL", str(model))
    for name in ("INDIC_TTS_URL", "INDIC_TTS_KEY", "HARNESS_VOICE", "SARVAM_AI_KEY", "OPENROUTER_API_KEY", "HARNESS_LOCAL_VOICE", "HARNESS_KOKORO_HINDI"):
        monkeypatch.delenv(name, raising=False)
    assert service.voice_candidates("hinglish") == ["kokoro:hf_alpha@0.85", "gtts:hi", "silent"]
    assert service.voice_candidates("hi-IN") == ["kokoro:hf_alpha@0.85", "gtts:hi", "silent"]
    assert service.voice_candidates("en-IN") == ["kokoro", "gtts:en", "silent"]
    monkeypatch.setenv("HARNESS_KOKORO_HINDI", "hm_omega")
    assert service.voice_candidates("hinglish")[0] == "kokoro:hm_omega@0.85"
    monkeypatch.setenv("HARNESS_LOCAL_VOICE", "0")
    assert service.voice_candidates("hinglish") == ["gtts:hi", "silent"] and service.voice_candidates("en-IN") == ["gtts:en", "silent"]
    assert service.narrated("kokoro:hf_alpha@0.85") and not service.narrated("gtts:hi")
