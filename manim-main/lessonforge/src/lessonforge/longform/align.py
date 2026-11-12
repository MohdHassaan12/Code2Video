"""Word-level alignment of synthesized narration, so cues land on the spoken word.

The audio-first build knows where each BEAT starts because it measured the clip.
Where a particular phrase falls inside the clip was, until now, arithmetic: a
sentence boundary snapped to a pause, then a word-count fraction. The review of the
first long lesson flagged every one of its 173 anchors as such an estimate
(docs/research/RESEARCH_QUESTIONS.md, RQ-12) and asked for forced alignment.

This module transcribes each synthesized clip with a speech-to-text model that
returns word timestamps (``openai/whisper-large-v3`` through OpenRouter, about a
fifth of a US cent per minute), matches the heard words back onto the script words,
and writes the result into the timeline: every sentence gets a measured ``start`` and
a ``words`` list, and ``timing_source`` becomes ``aligned``. The scene runtime
(``runtime.LessonScene.locate``) already prefers those word times when present.

What it does NOT do: it never changes the audio, never trusts a low-confidence
match, and never hides a fallback. A clip whose words match below ``MIN_COVERAGE``
keeps the pause-based estimate and says so; words the recognizer missed (numbers
spoken as words, Hinglish spelt differently) are interpolated between their matched
neighbours and marked ``matched: false``.
"""
from __future__ import annotations

import difflib
import json
import re
import subprocess
import tempfile
from pathlib import Path

from .contract import split_sentences

STT_MODEL = "openai/whisper-large-v3"
MIN_COVERAGE = 0.6   # below this share of matched words the alignment is not trusted
_NUMBER_WORDS = {
    "zero": "0", "one": "1", "two": "2", "three": "3", "four": "4", "five": "5", "six": "6", "seven": "7",
    "eight": "8", "nine": "9", "ten": "10", "eleven": "11", "twelve": "12", "thirteen": "13", "fourteen": "14",
    "fifteen": "15", "sixteen": "16", "seventeen": "17", "eighteen": "18", "nineteen": "19", "twenty": "20",
    "thirty": "30", "forty": "40", "fifty": "50", "sixty": "60", "seventy": "70", "eighty": "80", "ninety": "90",
    "hundred": "100", "thousand": "1000",
}


def norm(text: str) -> str:
    """The runtime's normalisation (``runtime._norm``): lower-case, keep word characters and spaces."""
    return re.sub(r"[^\w ]", "", (text or "").lower())


# "forty-two" loses its hyphen in ``norm`` and arrives as one word, "fortytwo"; the recogniser
# writes "42". Both become "42" so they match.
_TENS = ("twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety")
_ONES = ("one", "two", "three", "four", "five", "six", "seven", "eight", "nine")
_NUMBER_WORDS.update({t + o: str((i + 2) * 10 + k + 1) for i, t in enumerate(_TENS) for k, o in enumerate(_ONES)})


def _token(word: str) -> str:
    w = norm(word).strip()
    return _NUMBER_WORDS.get(w, w)


# Devanagari → rough Latin, for comparing what was HEARD in Devanagari with a script written in
# Latin letters. Only consonants matter (see ``sound_key``), so vowel signs map to nothing.
_DEVANAGARI = {
    "क": "k", "ख": "k", "ग": "g", "घ": "g", "ङ": "n", "च": "C", "छ": "C", "ज": "j", "झ": "j", "ञ": "n",
    "ट": "t", "ठ": "t", "ड": "d", "ढ": "d", "ण": "n", "त": "t", "थ": "t", "द": "d", "ध": "d", "न": "n",
    "प": "p", "फ": "f", "ब": "b", "भ": "b", "म": "n", "य": "", "र": "r", "ल": "l", "व": "v", "श": "s",
    "ष": "s", "स": "s", "ह": "h", "ं": "n", "ँ": "n", "ॉ": "", "ज़": "j", "फ़": "f", "ड़": "r", "ढ़": "r",
}


def sound_key(word: str) -> str:
    """A word reduced to its consonant sounds, the same for "chalte" and "चलते", "factor" and "फैक्टर".

    Vowels go (they are where transliterations disagree), aspirates fold into their plain
    consonant, and the letters that stand for one sound are made one letter. Coarse on
    purpose: it only has to line two tellings of the same sentence up in order.
    """
    w = word.lower()
    if any("\u0900" <= ch <= "\u097f" for ch in w):
        w = "".join(_DEVANAGARI.get(ch, "") for ch in w)
    else:
        w = re.sub(r"[^a-z]", "", w)
        for old, new in (("chh", "C"), ("ch", "C"), ("sh", "s"), ("ph", "f"), ("th", "t"), ("dh", "d"), ("kh", "k"),
                         ("gh", "g"), ("bh", "b"), ("ck", "k"), ("q", "k"), ("x", "ks"), ("z", "j"), ("w", "v"), ("m", "n")):
            w = w.replace(old, new)
        w = re.sub(r"c(?=[eiy])", "s", w).replace("c", "k")  # "cell" is soft, "factor" and "column" are hard
        w = re.sub(r"[aeiouy]", "", w)
    return re.sub(r"(.)\1+", r"\1", w)                     # doubled letters are one sound


def stt_languages(text: str, lesson_language: str | None) -> list[str | None]:
    """The languages to tell the recogniser, best first — more than one when the script and the speech differ.

    A Hinglish lesson is Hindi speech written in Latin letters. Told "hi" the recogniser
    writes Devanagari, and until ``sound_key`` nothing matched the script (9 Hinglish
    lessons: 123 of 155 blocks aligned, against every block of every English one). Told
    "en" it writes Latin letters but sometimes TRANSLATES the Hindi instead of spelling
    it. Measured on the 19 blocks of one lesson: "hi" matched by sound 18 trusted, "en"
    15, the better of the two 19 with at least 96% of words matched. So: the spoken
    language first, and the script's language as a second opinion.
    """
    code = (lesson_language or "").split("-")[0].lower() or None
    letters = [ch for ch in text if ch.isalpha()]
    latin = sum(1 for ch in letters if ch.isascii()) / len(letters) if letters else 0.0
    if code in (None, "en") or latin < 0.7:
        return [code]
    return [code, "en"]


def _digit_tokens(n: int) -> list[str]:
    """1764 as the tokens its spoken form normalises to: one thousand seven hundred sixty-four → 1 1000 7 100 64."""
    out = []
    if n >= 1000:
        out += _digit_tokens(n // 1000) + ["1000"]
        n %= 1000
    if n >= 100:
        out += [str(n // 100), "100"]
        n %= 100
    if n or not out:
        out.append(str(n))
    return out


def tidy_heard(heard: list[dict], clip_seconds: float | None = None) -> list[dict]:
    """What the recogniser returned, made comparable with the script.

    * A number written in digits ("1764") is split into the words it stands for, sharing
      its time span, so "one thousand seven hundred sixty-four" in the script has
      something to match. Steps are very often cued on exactly these words.
    * No word may end after the audio does. The recogniser sometimes stamps the last
      word far past the end of the clip (29.8 s on an 18.2 s clip); the last caption of
      that block then ran six seconds into the next one and the captions check failed.
    """
    out = []
    for h in heard:
        start, end = float(h["start"]), float(h["end"])
        if clip_seconds is not None:
            if start >= clip_seconds:
                continue
            end = min(end, clip_seconds)
        word = str(h.get("word", "")).strip()
        digits = re.sub(r"[,\s]", "", word.strip(".,;:!?()\"'"))
        if digits.isdigit() and 2 <= len(digits) <= 9 and int(digits) >= 21:
            parts = _digit_tokens(int(digits))
            for k, part in enumerate(parts):
                out.append({"word": part, "start": start + (end - start) * k / len(parts),
                            "end": start + (end - start) * (k + 1) / len(parts)})
        else:
            out.append({"word": word, "start": start, "end": max(start, end)})
    return out


def transcribe_words(wav: Path, language: str | None = None, model: str = STT_MODEL) -> list[dict]:
    """``[{"word", "start", "end"}, ...]`` for one clip, via OpenRouter STT (metered, ledger kind ``stt``)."""
    import httpx
    from .. import spend

    key = spend.api_key()
    if not key:
        raise RuntimeError("OPENROUTER_API_KEY is not set; alignment needs it")
    spend.check(estimate=0.01, what="speech-to-text alignment")
    with tempfile.TemporaryDirectory() as tmp:
        mp3 = Path(tmp) / "clip.mp3"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(wav), "-b:a", "48k", str(mp3)], check=True)
        data = {"model": model, "response_format": "verbose_json", "timestamp_granularities[]": "word"}
        if language:
            data["language"] = language
        with mp3.open("rb") as fh:
            r = httpx.post("https://openrouter.ai/api/v1/audio/transcriptions",
                           headers={"Authorization": f"Bearer {key}", "X-Title": "lessonforge"},
                           data=data, files={"file": ("clip.mp3", fh, "audio/mpeg")}, timeout=120.0)
    if r.status_code != 200:
        raise RuntimeError(f"STT HTTP {r.status_code}: {r.text[:200]}")
    payload = r.json()
    usage = payload.get("usage") or {}
    spend.record("stt", model, usage.get("cost"), seconds=usage.get("seconds"),
                 generation_id=r.headers.get("X-Generation-Id"), estimated=usage.get("cost") is None,
                 note=f"{len(payload.get('words') or [])} words" + (
                     "" if payload.get("words") or not payload.get("text") else " (text came back without word times)"))
    return [{"word": w.get("word", ""), "start": float(w["start"]), "end": float(w["end"])}
            for w in (payload.get("words") or []) if "start" in w and "end" in w]


def align_words(script_words: list[str], heard: list[dict]) -> tuple[list[dict], float]:
    """Match script words to heard words; interpolate the rest. Returns (per-word timings, coverage)."""
    a = [_token(w) for w in script_words]
    b = [_token(h["word"]) for h in heard]
    # A script in Latin letters heard in Devanagari (Hinglish told "hi"): compare by sound.
    if any("\u0900" <= ch <= "\u097f" for h in heard for ch in h["word"]) and \
            sum(w.isascii() for w in script_words) >= 0.7 * len(script_words):
        a = [t if t.isdigit() else sound_key(t) or t for t in a]
        b = [t if t.isdigit() else sound_key(t) or t for t in b]
    timings: list[dict | None] = [None] * len(a)
    matcher = difflib.SequenceMatcher(a=a, b=b, autojunk=False)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            for k in range(i2 - i1):
                timings[i1 + k] = {"start": heard[j1 + k]["start"], "end": heard[j1 + k]["end"], "matched": True}
        elif tag == "replace" and (i2 - i1) == (j2 - j1):
            # Same count on both sides (e.g. "metres" vs "meters"): accept positionally.
            for k in range(i2 - i1):
                timings[i1 + k] = {"start": heard[j1 + k]["start"], "end": heard[j1 + k]["end"], "matched": True}
    matched = sum(1 for t in timings if t)
    if not matched:
        return [], 0.0
    # Interpolate gaps between matched neighbours; clamp the ends to the clip.
    first = next(i for i, t in enumerate(timings) if t)
    last = max(i for i, t in enumerate(timings) if t)
    clip_end = heard[-1]["end"] if heard else timings[last]["end"]
    i = 0
    while i < len(timings):
        if timings[i]:
            i += 1
            continue
        j = i
        while j < len(timings) and not timings[j]:
            j += 1
        lo = timings[i - 1]["end"] if i > 0 else max(0.0, timings[first]["start"] - 0.3 * (first - i))
        hi = timings[j]["start"] if j < len(timings) else clip_end
        n = j - i
        for k in range(n):
            s = lo + (hi - lo) * k / n
            timings[i + k] = {"start": s, "end": lo + (hi - lo) * (k + 1) / n, "matched": False}
        i = j
    return timings, matched / len(a)


def _seconds(wav: Path) -> float | None:
    """Length of the clip, or None when it cannot be read (then nothing is clamped)."""
    try:
        import wave
        with wave.open(str(wav)) as fh:
            return fh.getnframes() / float(fh.getframerate())
    except Exception:  # noqa: BLE001
        return None


GOOD_ENOUGH = 0.9      # with this share of words matched a second opinion is not asked for
# Who is asked to hear one clip in one language, in order, until a hearing has word times. Why there is a
# second model: the "empty hearings" were never chance. OpenRouter sends ``STT_MODEL`` to one of three
# providers as it pleases, and one of them (Together) answers with the text and NO word times, every time.
# Measured 2026-10-09 on about 60 hearings of five clips: Groq and DeepInfra always gave word times, Together
# never; about half the requests went to Together, twelve in a row at one point (asking again is no cure),
# and the request's ``provider`` field can name a data policy but not a provider. A lesson in the owner's
# voice had 2 of its 5 blocks timed from heard words that way: the other three fell to the "en" hearing,
# which had TRANSLATED the Hindi, and so to estimates. ``STT_SECOND`` is served only by the two providers
# that do give word times; on the same five clips it matched 81 to 100% of the words (``STT_MODEL``, where
# it answered with times: 97 to 100%), so it is the second opinion and not the first.
STT_SECOND = "openai/whisper-large-v3-turbo"
STT_ORDER = (STT_MODEL, STT_SECOND, STT_MODEL)


def align_best(text: str, wav: Path, lesson_language: str | None, cache_stem: Path | None = None) -> dict | None:
    """``align_clip`` with each language ``stt_languages`` proposes; the result with the most words matched."""
    best = None
    for language in stt_languages(text, lesson_language):
        cache = Path(f"{cache_stem}.words.{language or 'auto'}.json") if cache_stem else None
        result = align_clip(text, wav, language=language, cache=cache)
        if result and (best is None or result["coverage"] > best["coverage"]):
            best = {**result, "heard_as": language}
        if best and best["coverage"] >= GOOD_ENOUGH:
            break
    return best


def align_clip(text: str, wav: Path, language: str | None = None, cache: Path | None = None) -> dict | None:
    """Sentence spans with word times for one synthesized clip, or None when not trustworthy.

    ``cache`` (a .json path) stores the raw transcript so re-builds cost nothing.
    """
    heard = json.loads(cache.read_text(encoding="utf-8")) if cache and cache.exists() else []
    if not heard:
        # The recogniser sometimes answers 200 with no words at all: on 2026-10-09 all three Hindi hearings
        # of one lesson came back empty, and the same clip was heard word for word a minute later. An empty
        # hearing of a narrated clip is a failed call, not silence: ask the next in ``STT_ORDER`` (see there
        # for what an "empty" hearing turned out to be), and never keep it, or the clip stays unaligned on
        # every later build.
        for model in STT_ORDER:
            heard = transcribe_words(wav, language=language, model=model)
            if heard:
                break
        if cache and heard:
            cache.write_text(json.dumps(heard, ensure_ascii=False), encoding="utf-8")
    heard = tidy_heard(heard, _seconds(wav))
    sentences = split_sentences(text)
    per_sentence = [norm(s).split() for s in sentences]
    flat = [w for ws in per_sentence for w in ws]
    if not flat or not heard:
        return None
    timings, coverage = align_words(flat, heard)
    if coverage < MIN_COVERAGE:
        return {"sentences": [], "coverage": coverage, "trusted": False}
    spans, cursor = [], 0
    for sentence, words in zip(sentences, per_sentence):
        chunk = timings[cursor:cursor + len(words)]
        cursor += len(words)
        if not chunk:
            continue
        spans.append({"text": sentence, "start": chunk[0]["start"], "end": chunk[-1]["end"],
                      "words": [{"word": w, **t} for w, t in zip(words, chunk)]})
    # A sentence lasts until the next one starts (the pause belongs to the sentence before it).
    for k, span in enumerate(spans):
        nxt = spans[k + 1]["start"] if k + 1 < len(spans) else max(span["end"], heard[-1]["end"])
        span["duration"] = max(0.05, nxt - span["start"])
        span["timing_source"] = "aligned"
        del span["end"]
    return {"sentences": spans, "coverage": coverage, "trusted": True,
            "matched_words": sum(1 for t in timings if t["matched"]), "words": len(flat)}


def shift(spans: list[dict], offset: float, scale: float = 1.0) -> list[dict]:
    """Move aligned spans to the beat's clock (lead-in, earlier clips) and apply a tempo scale."""
    out = []
    for s in spans:
        out.append({**s, "start": offset + s["start"] * scale, "duration": s["duration"] * scale,
                    "words": [{**w, "start": offset + w["start"] * scale, "end": offset + w["end"] * scale}
                              for w in s.get("words", [])]})
    return out
