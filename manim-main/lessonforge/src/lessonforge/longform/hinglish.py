"""Latin-letter Hindi as a Hindi voice can read it: the words a first pass left in Latin letters, put into Devanagari.

A Hindi text-to-speech voice reads a Latin-letter word by ENGLISH spelling rules. Hinglish narration is Hindi in Latin
letters with English terms in it, so the English terms come out right and the Hindi does not: the local voice read
"karke" as "cock" and "karne se" as "can't see" (heard back by a recogniser, 2026-10-12). ``speech.voice_script`` has a
small model write the Hindi words in Devanagari, and on that block it turned three of twelve.

So what is still in Latin letters afterwards is looked at word by word, here, with no model:

* a word an English word list has is English and stays (``english``: the system's ``/usr/share/dict`` lists; without
  them nothing is touched, because then nothing can be told apart);
* any other word is Hindi and is written in Devanagari by its sounds (``to_devanagari``).

The spelling this writes is not always the dictionary's ("कर्के" for "करके"): it only has to SOUND right when a voice
reads it, and a consonant cluster written with a halant sounds as the word does. A few dozen of the commonest words,
whose casual Latin spelling hides a nasal or a long vowel ("hain", "nahi", "kyunki"), are written from a table.
"""
from __future__ import annotations

import functools
import re
from pathlib import Path

_LISTS = ("/usr/share/dict/american-english", "/usr/share/dict/british-english", "/usr/share/dict/words")

#: Written from memory of how the word is spelt, because its sounds cannot be read off its usual Latin spelling.
COMMON = {
    "hai": "है", "hain": "हैं", "hoon": "हूँ", "hun": "हूँ", "ho": "हो", "tha": "था", "thi": "थी", "hoga": "होगा", "hogi": "होगी",
    "main": "मैं", "mein": "में", "nahin": "नहीं", "nahi": "नहीं", "haan": "हाँ", "kahan": "कहाँ", "yahan": "यहाँ", "wahan": "वहाँ",
    "kyun": "क्यों", "kyon": "क्यों", "kyunki": "क्योंकि", "kyonki": "क्योंकि", "kya": "क्या", "kaun": "कौन", "kaise": "कैसे",
    "kaisa": "कैसा", "kitna": "कितना", "kitne": "कितने", "kitni": "कितनी", "kaunsa": "कौनसा", "kab": "कब",
    "yeh": "यह", "ye": "ये", "woh": "वह", "wo": "वो", "yahi": "यही", "wahi": "वही", "iska": "इसका", "iske": "इसके", "iski": "इसकी",
    "uska": "उसका", "uske": "उसके", "uski": "उसकी", "isse": "इससे", "usse": "उससे", "ise": "इसे", "use": "उसे", "inhe": "इन्हें",
    "aur": "और", "ek": "एक", "agar": "अगर", "lekin": "लेकिन", "phir": "फिर", "pehle": "पहले", "pehla": "पहला", "baad": "बाद",
    "liye": "लिए", "isliye": "इसलिए", "jaise": "जैसे", "sirf": "सिर्फ़", "bahut": "बहुत", "zyada": "ज़्यादा", "jyada": "ज़्यादा",
    "upar": "ऊपर", "neeche": "नीचे", "andar": "अंदर", "bahar": "बाहर", "saath": "साथ", "taraf": "तरफ़", "matlab": "मतलब",
    "chahiye": "चाहिए", "abhi": "अभी", "kabhi": "कभी", "sabhi": "सभी", "bhi": "भी", "toh": "तो", "apna": "अपना", "apne": "अपने",
    "apni": "अपनी", "hum": "हम", "aap": "आप", "tum": "तुम", "kuch": "कुछ", "koi": "कोई", "har": "हर", "dono": "दोनों",
    "paani": "पानी", "pani": "पानी", "hawa": "हवा", "zameen": "ज़मीन", "aasman": "आसमान", "suraj": "सूरज",
}

_CONSONANTS = (("ksh", "क्ष"), ("chh", "छ"), ("kh", "ख"), ("gh", "घ"), ("ch", "च"), ("jh", "झ"), ("th", "थ"), ("dh", "ध"),
               ("ph", "फ"), ("bh", "भ"), ("sh", "श"), ("k", "क"), ("g", "ग"), ("c", "क"), ("j", "ज"), ("t", "त"), ("d", "द"),
               ("n", "न"), ("p", "प"), ("b", "ब"), ("m", "म"), ("y", "य"), ("r", "र"), ("l", "ल"), ("v", "व"), ("w", "व"),
               ("s", "स"), ("h", "ह"), ("z", "ज़"), ("f", "फ़"), ("q", "क"), ("x", "क्स"))
#: (Latin, the sign after a consonant, the letter at the start of a word or after a vowel)
_VOWELS = (("aa", "ा", "आ"), ("ai", "ै", "ऐ"), ("au", "ौ", "औ"), ("ou", "ौ", "औ"), ("ee", "ी", "ई"), ("ii", "ी", "ई"),
           ("oo", "ू", "ऊ"), ("uu", "ू", "ऊ"), ("a", "", "अ"), ("i", "ि", "इ"), ("u", "ु", "उ"), ("e", "े", "ए"), ("o", "ो", "ओ"))
#: A vowel that ends a word is long: "karta" is "kartaa", "ki" is "kee".
_FINAL = {"a": ("ा", "आ"), "i": ("ी", "ई"), "u": ("ू", "ऊ")}
#: An n that ends a word after these is a nasal vowel, not a consonant: karen, logon, karun.
_NASAL_ENDINGS = ("ain", "ein", "en", "on", "un")
_DEVANAGARI = re.compile("[ऀ-ॿ]")
_WORD = re.compile(r"[A-Za-z]+")


@functools.lru_cache(maxsize=1)
def english() -> frozenset:
    """The words an English word list has; empty when this machine has no list.

    Only entries the list writes in small letters: its names and symbols ("Se" for selenium, "Karo") made "se" and
    "karo" English, and the voice read them as "see" and "kaarav".
    """
    words: set = set()
    for name in _LISTS:
        try:
            words.update(line.strip() for line in Path(name).read_text(encoding="utf-8", errors="ignore").splitlines()
                         if line.strip().isalpha() and line.strip().islower())
        except OSError:
            continue
    return frozenset(words)


def to_devanagari(word: str) -> str:
    """One Latin-letter Hindi word in Devanagari, by its sounds ("rahega" → "रहेगा", "karke" → "कर्के")."""
    low = word.lower()
    if low in COMMON:
        return COMMON[low]
    nasal = len(low) > 3 and any(low.endswith(ending) for ending in _NASAL_ENDINGS)
    if nasal:
        low = low[:-1]
    out, at, after_consonant = [], 0, False
    while at < len(low):
        vowel = next((v for v in _VOWELS if low.startswith(v[0], at)), None)
        if vowel is not None:
            latin, sign, letter = vowel
            last = at + len(latin) == len(low)
            if last and latin in _FINAL and not nasal:
                sign, letter = _FINAL[latin]
            out.append(sign if after_consonant else letter)
            at, after_consonant = at + len(latin), False
            continue
        consonant = next((c for c in _CONSONANTS if low.startswith(c[0], at)), None)
        if consonant is None:                               # a letter with no sound of its own here: left out
            at += 1
            continue
        if after_consonant:
            out.append("्")                                 # two consonants with no vowel between them
        out.append(consonant[1])
        at, after_consonant = at + len(consonant[0]), True
    if nasal:
        out.append("ं")
    return "".join(out) or word


def rest_in_devanagari(text: str) -> str:
    """``text`` with every Latin-letter word that is not English written in Devanagari; English words, words in capitals
    (CO, DNA) and single letters stay. Unchanged when this machine has no English word list."""
    known = english()
    if not known:
        return text

    def turn(match):
        word = match.group(0)
        low = word.lower()
        if len(word) == 1 or (word.isupper() and len(word) <= 5):
            return word
        if low in COMMON:
            return COMMON[low]
        if low in known or (low.endswith("s") and low[:-1] in known):
            return word
        return to_devanagari(word)
    return _WORD.sub(turn, text)


def latin_hindi_left(text: str) -> list[str]:
    """The Latin-letter words of ``text`` that are not English: what a Hindi voice would misread."""
    known = english()
    return [w for w in _WORD.findall(text) if known and len(w) > 1 and not (w.isupper() and len(w) <= 5)
            and w.lower() not in known and not (w.lower().endswith("s") and w.lower()[:-1] in known)]
