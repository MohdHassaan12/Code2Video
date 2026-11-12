"""Point names reach the Sarvam voice letter by letter (``longform.speech.spell_point_names``)."""
from lessonforge.longform import speech


def test_point_names_are_spelled_and_words_said_as_one_are_not():
    assert speech.spell_point_names("Draw AC in ABCD.") == "Draw A, C in A, B, C, D."
    assert speech.spell_point_names("By ASA, from NCERT. A is a point.") == "By ASA, from NCERT. A is a point."
    assert speech.spell_point_names("side AB", sep=" ") == "side A B"


def test_only_english_sarvam_spells_and_its_cache_key_says_so(monkeypatch):
    monkeypatch.delenv("SARVAM_SPELL_POINTS", raising=False)
    en, hi = speech.SarvamBackend(language="en-IN"), speech.SarvamBackend(language="hi-IN")
    assert en._spells() and not hi._spells()
    assert en.cache_key().endswith("|letters") and not hi.cache_key().endswith("|letters")
    monkeypatch.setenv("SARVAM_SPELL_POINTS", "0")
    assert not en._spells()
