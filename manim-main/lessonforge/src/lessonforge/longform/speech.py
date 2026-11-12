"""Speech backends for the audio-first build.

A backend turns one block of narration into one audio file. That is the whole
interface, and it is small on purpose: the build (``audio.py``) owns caching,
measurement, pacing and the timeline, so swapping the voice never changes timing
logic, and every backend gets the same content-addressed cache.

    silent   word-count-sized silence. Free and deterministic — use it while iterating
             on visuals, the way ``TTS_MUTE=1`` is used on the engine path.
    kokoro   Kokoro-82M via kokoro-onnx, local, no per-request charge (the voice of the
             reviewed Pythagoras lesson).              pip install lessonforge[kokoro]
    gtts     Google Translate TTS, keyless, needs network. A listening placeholder.
    gemini   Gemini 3.8 Flash TTS / Flash-Lite TTS through OpenRouter, with delivery
             instructions. Metered (about a cent a minute) and recorded in the spend ledger.
    sarvam   Sarvam AI's Indian-language voices (bulbul), called directly. Billed by Sarvam, in
             rupees, on its own key; counted in the spend ledger at zero dollars.
    indic    the owner's own text-to-speech service (Hindi, English and mixed text, four voices), called
             directly over HTTPS. Not on OpenRouter: counted in the spend ledger at zero dollars.
    engine   the engine's ``UniversalTTSService`` chain (Sarvam / Gemini TTS / gTTS),
             so long-form lessons get the same Indian-language voices as short videos.
             Metered: a cache-key change is a billing change.

Spec strings (CLI ``--voice``):  ``silent``  ``kokoro``  ``kokoro:af_heart@0.85``
``gtts:hi``  ``gemini:lite/Kore``  ``gemini:flash/Puck|warm, unhurried teacher``
``sarvam:shubh/hi-IN``  ``sarvam:anushka/en-IN@0.95``  ``indic:kavya``  ``indic:maitri/hinglish@0.4``
``engine:sarvam/hi-IN/shubh``  ``engine:gemini/en-IN/Kore``
"""
from __future__ import annotations

import os
import re
import subprocess
import wave
from pathlib import Path

import numpy as np
from .. import knobs

SAMPLE_RATE = 24000


def write_wav(path: Path, samples: np.ndarray, rate: int = SAMPLE_RATE) -> None:
    """Mono float32 [-1, 1] → 16-bit PCM wav."""
    pcm = (np.clip(np.asarray(samples, dtype=np.float32), -1.0, 1.0) * 32767.0).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm.tobytes())


def read_wav(path: Path) -> tuple[np.ndarray, int]:
    """16-bit PCM wav → mono float32 [-1, 1] and its sample rate."""
    with wave.open(str(path), "rb") as w:
        rate, channels, width = w.getframerate(), w.getnchannels(), w.getsampwidth()
        raw = w.readframes(w.getnframes())
    if width != 2:
        raise ValueError(f"{path}: expected 16-bit PCM, got {8 * width}-bit")
    data = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
    if channels > 1:
        data = data.reshape(-1, channels).mean(axis=1)
    return data, rate


def to_canonical_wav(src: Path, dest: Path, tempo: float = 1.0) -> None:
    """Any audio file → mono 24 kHz 16-bit wav, optionally re-paced with ffmpeg atempo."""
    cmd = ["ffmpeg", "-v", "error", "-y", "-i", str(src)]
    if abs(tempo - 1.0) > 1e-6:
        cmd += ["-af", f"atempo={tempo:.9f}"]
    cmd += ["-ac", "1", "-ar", str(SAMPLE_RATE), "-c:a", "pcm_s16le", str(dest)]
    subprocess.run(cmd, check=True)


class SpeechBackend:
    """One block of text in, one audio file out. Subclasses set ``name``."""

    name = "base"
    #: file suffix the backend writes; the build converts it to the canonical wav.
    suffix = ".wav"

    def cache_key(self) -> str:
        """Everything that changes the audio for the same text. Part of the clip's hash."""
        return self.name

    def synthesize(self, text: str, dest: Path) -> None:  # pragma: no cover - interface
        raise NotImplementedError

    def describe(self) -> dict:
        return {"backend": self.name, "cache_key": self.cache_key()}


class SilentBackend(SpeechBackend):
    """Silence as long as the words would take to say. Deterministic, free, offline."""

    name = "silent"

    def __init__(self, wpm: float = 150.0):
        self.wpm = float(wpm)

    def cache_key(self) -> str:
        return f"silent|{self.wpm:g}"

    def synthesize(self, text: str, dest: Path) -> None:
        seconds = max(0.6, len(text.split()) / self.wpm * 60.0)
        write_wav(dest, np.zeros(round(seconds * SAMPLE_RATE), dtype=np.float32))


class KokoroModelError(RuntimeError):
    """The Kokoro files are there but cannot be used (a git-lfs pointer in place of the model), in plain words."""


#: A real model is hundreds of MB and the voice pack tens of MB; a git-lfs pointer is a ~130 byte text file.
_LFS_POINTER_MAX = 1024
_LFS_MAGIC = b"version https://git-lfs"
#: Where the real files usually are on the owner's machines.
KOKORO_USUAL_DIR = "/workspace/models/ComfyUI/models_local/tts/kokoro/"


def check_not_lfs_pointer(label: str, path: str) -> None:
    """Raise :class:`KokoroModelError` when ``path`` is a git-lfs pointer (under 1 KB, or starting "version https://git-lfs").

    A clone made without ``git lfs pull`` leaves such a pointer where the model should be; the engine then fails deep
    inside onnxruntime or says only "no speech backend produced audio". Say what it is and where the real file is.
    """
    try:
        size = os.path.getsize(path)
        with open(path, "rb") as fh:
            head = fh.read(len(_LFS_MAGIC))
    except OSError:
        return                                  # unreadable or missing: the caller's own message says so
    if size < _LFS_POINTER_MAX or head == _LFS_MAGIC:
        raise KokoroModelError(
            f"{label} points at {path}, which is a git-lfs pointer ({size} bytes), not the Kokoro file. The real "
            f"{os.path.basename(path)} is hundreds of MB (the voice pack tens of MB): run `git lfs pull` where it was cloned, or "
            f"point {label} at the real file, usually in {KOKORO_USUAL_DIR}")


class KokoroBackend(SpeechBackend):
    """Kokoro-82M (Apache-2.0) through kokoro-onnx (MIT). Runs locally on CPU, in English and in Hindi.

    The model and voice pack are not shipped. Point ``KOKORO_MODEL`` / ``KOKORO_VOICES``
    at ``kokoro-v1.0.onnx`` / ``voices-v1.0.bin``, or drop both in ``<workspace>/models/``.

    A voice whose name begins with ``h`` (``hf_alpha``, ``hf_beta``, ``hm_omega``, ``hm_psi``) is a HINDI voice: the
    fallback for a Hindi or Hinglish lesson when the owner's own speech service cannot be reached (their word,
    2026-10-12: "deploy some TTS as a fallback … but don't use the TTS of OpenRouter"). Two things it needs, each
    found by having a recogniser listen to it:

    * the block is turned into sounds HERE, with the language-switch markers taken out. Left to kokoro-onnx, every
      English word in a Hindi sentence was spoken with the marker's letters around it ("in right atrium hi se …");
    * Latin-letter Hinglish is given to it with its Hindi in Devanagari (``voice_script``), as the owner's voice gets
      it: read by English spelling rules "karta hai" came out as "kaata-hai". A block that cannot be turned is spoken
      as it is written.
    """

    name = "kokoro"

    def __init__(self, voice: str = "af_heart", speed: float = 0.85, lang: str | None = None,
                 model: str | None = None, voices: str | None = None):
        self.voice, self.speed = voice, float(speed)
        self.lang = lang or {"h": "hi", "b": "en-gb"}.get(voice[:1], "en-us")
        self._model, self._voices, self._engine = model, voices, None

    @property
    def hindi(self) -> bool:
        return self.lang.startswith("hi")

    def cache_key(self) -> str:
        return f"kokoro|{self.voice}|{self.speed:g}|{self.lang}" + ("|sounds-3" if self.hindi else "")

    def _paths(self) -> tuple[str, str]:
        from .. import paths
        model = self._model or os.getenv("KOKORO_MODEL")
        if not model or not os.path.exists(model):
            home_m = str(paths.home() / "models" / "kokoro-v1.0.onnx")
            usual_m = os.path.join(KOKORO_USUAL_DIR, "kokoro-v1.0.onnx")
            model = usual_m if os.path.exists(usual_m) else (model or home_m)
        voices = self._voices or os.getenv("KOKORO_VOICES")
        if not voices or not os.path.exists(voices):
            home_v = str(paths.home() / "models" / "voices-v1.0.bin")
            usual_v = os.path.join(KOKORO_USUAL_DIR, "voices-v1.0.bin")
            voices = usual_v if os.path.exists(usual_v) else (voices or home_v)
        for label, p in (("KOKORO_MODEL", model), ("KOKORO_VOICES", voices)):
            if not os.path.exists(p):
                raise FileNotFoundError(
                    f"Kokoro file not found: {p}. Set {label} or download it from "
                    "https://github.com/thewh1teagle/kokoro-onnx/releases")
            check_not_lfs_pointer(label, p)
        return model, voices

    def sounds(self, text: str) -> str:
        """A Hindi block as the sounds the model is given: Hindi and English words each by their own rules, and no
        language-switch marker left in ("(en)", "(hi)": their letters were spoken)."""
        import phonemizer  # noqa: PLC0415 - comes with kokoro-onnx
        from kokoro_onnx import tokenizer as kokoro_tokenizer  # noqa: PLC0415
        text = str(text).replace("।", ". ")                # a danda is a full stop: without it two sentences ran together
        with kokoro_tokenizer._espeak_lock:
            made = phonemizer.phonemize(text, self.lang, preserve_punctuation=True, with_stress=True, language_switch="remove-flags")
        known = self._engine.tokenizer.vocab
        return "".join(sound for sound in made if sound in known).strip()

    def synthesize(self, text: str, dest: Path) -> None:
        if self._engine is None:
            paths = self._paths()                      # first: a missing file or an lfs pointer is said in words
            from kokoro_onnx import Kokoro  # optional dependency: lessonforge[kokoro]
            self._engine = Kokoro(*paths)
        if self.hindi:
            from . import hinglish  # noqa: PLC0415
            spoken = text if _DEVANAGARI.search(text) else (voice_script(text) or text)
            # What is still in Latin letters and is not English would be read by English rules ("karke" as "cock"):
            # those words are written in Devanagari by their sounds, with no model (longform/hinglish.py).
            spoken = hinglish.rest_in_devanagari(spoken)
            samples, rate = self._engine.create(self.sounds(spoken), voice=self.voice, speed=self.speed, is_phonemes=True)
        else:
            samples, rate = self._engine.create(letter_names(text), voice=self.voice, speed=self.speed, lang=self.lang)
        write_wav(dest, samples, rate)

    def describe(self) -> dict:
        return {**super().describe(), "voice": self.voice, "synthesis_speed": self.speed, "lang": self.lang}


_RUN = re.compile(r"\b(?:[A-Z](?:\d|')*){3,6}\b")
_LONE_A = re.compile(r"(?<![.!?:]\s)(?<!^)(?<![-\w])A(?![-\w'’])")


_OPENING_A = re.compile(r"(?:(?<=^)|(?<=[.!?:]\s))A(?=[,.?!]|\s(?:and|or|is|to|has|lies|moves|sits|was|becomes|goes|"
                        r"slides|stays|joins|meets)\b)")


def letter_names(text: str) -> str:
    """Point names as a geometry teacher says them, for an English voice that reads by espeak's rules.

    espeak reads "ABCD" as one word ("abkd") and a lone capital A as the article ("uh"): "angle A" and "from A to D"
    came out wrong in the quadrilaterals lessons (2026-10-20). A run of three to six capitals is spelt with hyphens
    ("C-D-Eigh", read letter by letter; A inside such a run is "uh" too) and a capital A inside a sentence becomes "Eigh"
    (read "ay"). An A that opens a
    sentence stays the article. Captions and anchors keep the lesson's own text: only what the voice is given changes.
    """
    known = {"NCERT", "DNA", "LED", "USD", "UTC"}
    def spelt(m):
        if m.group(0) in known:
            return m.group(0)
        return "-".join("Eigh" if c == "A" else c for c in re.findall(r"[A-Z](?:\d|')*", m.group(0)))
    out = _LONE_A.sub("Eigh", _RUN.sub(spelt, str(text)))
    # an A opening a sentence is the article, unless what follows can only follow a name ("A, B and C", "A is …")
    return _OPENING_A.sub("Eigh", out)


class GTTSBackend(SpeechBackend):
    name = "gtts"
    suffix = ".mp3"

    def __init__(self, lang: str = "en"):
        self.lang = lang

    def cache_key(self) -> str:
        return f"gtts|{self.lang}"

    def synthesize(self, text: str, dest: Path) -> None:
        from gtts import gTTS
        gTTS(text=text, lang=self.lang).save(str(dest))


def _hindi_spoken(text: str) -> str:
    """Latin-letter Hinglish as a Hindi voice reads it best: the Hindi in Devanagari, every English word as written
    (``voice_script``, then ``hinglish.rest_in_devanagari`` for what is left). Devanagari text is left alone."""
    from . import hinglish  # noqa: PLC0415
    spoken = text if _DEVANAGARI.search(text) else (voice_script(text) or text)
    return hinglish.rest_in_devanagari(spoken)


class EdgeBackend(SpeechBackend):
    """Microsoft's neural voices, through the free read-aloud service the Edge browser uses (``edge-tts``, LGPLv3).

    Free and good, in English and in nine Indian languages (``hi-IN-SwaraNeural``, ``en-IN-NeerjaNeural``,
    ``te-IN-ShrutiNeural``, ``ta-IN-PallaviNeural`` …), and it needs the network. It is not an API Microsoft
    offers for this: there is no agreement and no service level, and it can be limited or stopped at any time,
    so it is a voice a lesson CHOOSES, never one the pipeline falls back to by itself. Like the owner's own
    service, a failed clip raises: a lesson never changes narrator half way.

    A Hindi voice is given a Hinglish block with its Hindi in Devanagari (as Kokoro's and the owner's voice are):
    read by English spelling rules, Latin-letter Hindi comes out wrong. Measured 2026-10-15: one mixed sentence of
    12 words, 5.3 s of speech in 2.1 s (about 137 words a minute, near the 125 lessons are budgeted on).
    """

    name = "edge"
    suffix = ".mp3"
    HINDI = ("hinglish", "hi-in", "hi")
    TRIES = 3

    def __init__(self, voice: str = "en-IN-NeerjaNeural", language: str = "", rate: str = "+0%"):
        self.voice = (voice or "en-IN-NeerjaNeural").strip()
        self.language = (language or "").strip().lower()
        self.rate = (rate or "+0%").strip()
        if not re.fullmatch(r"[a-z]{2,3}-[A-Z]{2}-[A-Za-z]+Neural", self.voice):
            raise ValueError(f"not a Microsoft neural voice name: {voice!r} (e.g. hi-IN-SwaraNeural)")
        if not re.fullmatch(r"[+-]\d{1,2}%", self.rate):
            raise ValueError(f"a rate is like +0% or -10%, not {rate!r}")

    @property
    def devanagari(self) -> bool:
        return self.voice.startswith("hi-") and self.language in self.HINDI

    def cache_key(self) -> str:
        return f"edge|{self.voice}|{self.rate}" + ("|deva1" if self.devanagari else "")

    def synthesize(self, text: str, dest: Path) -> None:
        import asyncio
        import time

        import edge_tts  # optional dependency: pip install edge-tts

        from .. import spend
        spoken = _hindi_spoken(text) if self.devanagari else text

        async def say() -> None:
            await edge_tts.Communicate(spoken, self.voice, rate=self.rate).save(str(dest))

        last: Exception | None = None
        for attempt in range(self.TRIES):
            try:
                asyncio.run(say())
                if dest.exists() and dest.stat().st_size > 512:
                    break
                last = RuntimeError("Microsoft's voice service returned no audio")
            except Exception as exc:  # noqa: BLE001 - network, refusal: tried again, then the lesson's next voice
                last = exc
            time.sleep(1.5 * (attempt + 1))
        else:
            raise RuntimeError(f"Microsoft's voice service failed: {type(last).__name__}: {str(last)[:160]}")
        spend.record("tts", f"edge/{self.voice}", 0.0, note=f"{len(text)} chars, Microsoft's free read-aloud voices (not billed)")

    def describe(self) -> dict:
        return {**super().describe(), "voice": self.voice, "rate": self.rate, "language": self.language}


class HttpBackend(SpeechBackend):
    """Any text-to-speech server of your own, over HTTP (``TTS_HTTP_URL``, optional ``TTS_HTTP_KEY``).

    The contract: ``POST <TTS_HTTP_URL>`` with JSON ``{"text", "voice", "language"}`` (and the header
    ``X-API-Key: <TTS_HTTP_KEY>`` when a key is set) answers 200 with the audio file itself, WAV or MP3. A block is
    sent whole; a failed clip raises after two more tries, so a lesson never changes narrator half way.
    """

    name = "http"
    suffix = ".audio"            # WAV or MP3: the build's conversion reads what it is, not its name

    def __init__(self, voice: str = "", language: str = ""):
        self.voice, self.language = (voice or "").strip(), (language or "").strip()

    def cache_key(self) -> str:
        url = os.getenv("TTS_HTTP_URL", "").strip().rstrip("/")
        return f"http|{url}|{self.voice}|{self.language}"

    def synthesize(self, text: str, dest: Path) -> None:
        import time

        import httpx

        from .. import spend
        url, key = os.getenv("TTS_HTTP_URL", "").strip(), os.getenv("TTS_HTTP_KEY", "").strip()
        if not url:
            raise RuntimeError("TTS_HTTP_URL is not set; the http speech backend needs it")
        headers = {"Content-Type": "application/json", **({"X-API-Key": key} if key else {})}
        last: Exception | None = None
        for attempt in range(3):
            try:
                r = httpx.post(url, headers=headers, json={"text": text, "voice": self.voice, "language": self.language},
                               timeout=120.0)
                audio = r.content
                if r.status_code == 200 and (audio[:4] == b"RIFF" or audio[:3] == b"ID3" or audio[:2] in (b"\xff\xfb", b"\xff\xf3", b"\xff\xf2")):
                    dest.write_bytes(audio)
                    spend.record("tts", f"http/{self.voice or 'default'}", 0.0, note=f"{len(text)} chars, your own speech server")
                    return
                last = RuntimeError(f"the speech server answered HTTP {r.status_code} without WAV or MP3 audio: {r.text[:120]}")
                if r.status_code in (400, 401, 403, 404, 422):
                    break                                   # a wrong address, key or request will not get better
            except httpx.HTTPError as exc:
                last = exc
            time.sleep(1.5 * (attempt + 1))
        raise RuntimeError(f"your speech server failed: {type(last).__name__}: {str(last)[:160]}")

    def describe(self) -> dict:
        return {**super().describe(), "voice": self.voice, "language": self.language}


class BrowserBackend(SilentBackend):
    """No narration in the video: the learner's own device reads the captions aloud (the browser's
    ``speechSynthesis``), in the lesson's language. The audio track is silence sized to the words, so the picture,
    the captions and the question stops are timed as for any voice; the web player speaks each caption as it comes.
    Free and offline for this server; how it sounds depends on the learner's device. Words are not timed by a
    recogniser (there is nothing to hear), so steps come up on estimated times.
    """

    name = "browser"

    def __init__(self, language: str = "en-IN", wpm: float = 140.0):
        super().__init__(wpm)
        self.language = (language or "en-IN").strip()

    def cache_key(self) -> str:
        return f"browser|{self.wpm:g}"


class OpenRouterTTSBackend(SpeechBackend):
    """Gemini TTS through OpenRouter's ``/audio/speech`` (metered; recorded in the spend ledger).

    Two tiers measured on 2026-10-08: ``flash`` (google/gemini-3.8-flash-tts, $9 per
    million audio tokens) and ``lite`` (google/gemini-3.8-flash-lite-tts, $6). Both
    emit 25 audio tokens per second, i.e. about 1.4 and 0.9 US cents per minute of
    narration. ``instructions`` is a free-text delivery note ("warm teacher, pause
    after each question") that the model honours — it is part of the cache key
    because it changes the audio. The language is detected from the text, so one
    backend serves English, Hindi and Hinglish; the voice names are Google's
    (Kore, Puck, Charon, Zephyr, Leda, Orus, Aoede, ...).
    """

    name = "gemini"
    suffix = ".wav"
    MODELS = {"flash": "google/gemini-3.8-flash-tts", "lite": "google/gemini-3.8-flash-lite-tts"}
    TOKENS_PER_SECOND = 25.0
    PRICE_PER_TOKEN = {"flash": 9e-6, "lite": 6e-6}

    def __init__(self, tier: str = "flash", voice: str = "Kore", instructions: str = ""):
        if tier not in self.MODELS:
            raise ValueError(f"unknown Gemini TTS tier {tier!r} (use flash or lite)")
        self.tier, self.voice = tier, voice or "Kore"
        self.instructions = (instructions or os.getenv("LESSONFORGE_TTS_INSTRUCTIONS", "")).strip()

    @property
    def model(self) -> str:
        return self.MODELS[self.tier]

    def cache_key(self) -> str:
        return f"gemini|{self.model}|{self.voice}|{self.instructions}"

    def synthesize(self, text: str, dest: Path) -> None:
        import httpx
        from .. import spend

        key = spend.api_key()
        if not key:
            raise RuntimeError("OPENROUTER_API_KEY is not set; the gemini speech backend needs it")
        # ~2.4 words per second spoken; the estimate only has to be the right order.
        words = len(text.split())
        spend.check(estimate=words / 2.4 * self.TOKENS_PER_SECOND * self.PRICE_PER_TOKEN[self.tier],
                    what=f"Gemini TTS ({self.tier}) for {words} words")
        payload = {"model": self.model, "input": text, "voice": self.voice, "response_format": "pcm"}
        if self.instructions:
            payload["instructions"] = self.instructions
        headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json", "X-Title": "lessonforge"}
        last_error = None
        for attempt in range(3):
            try:
                r = httpx.post("https://openrouter.ai/api/v1/audio/speech", headers=headers, json=payload, timeout=120.0)
                if r.status_code == 200 and r.content:
                    break
                last_error = RuntimeError(f"Gemini TTS HTTP {r.status_code}: {r.text[:200]}")
                if r.status_code not in (408, 409, 425, 429, 500, 502, 503, 504):
                    raise last_error
            except httpx.HTTPError as exc:
                last_error = exc
            if attempt < 2:
                import time
                time.sleep(1.5 * (attempt + 1))
        else:
            raise last_error or RuntimeError("Gemini TTS failed")
        audio = r.content
        if audio[:3] == b"ID3" or audio[:2] == b"\xff\xfb":  # a provider answered mp3 despite pcm
            tmp = dest.with_suffix(".mp3")
            tmp.write_bytes(audio)
            to_canonical_wav(tmp, dest)
            tmp.unlink(missing_ok=True)
        else:
            with wave.open(str(dest), "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(SAMPLE_RATE)
                w.writeframes(audio)
        seconds = len(audio) / 2 / SAMPLE_RATE
        gen_id = r.headers.get("X-Generation-Id")
        billed = spend.generation_cost(gen_id) if gen_id else None
        if billed:
            spend.record("tts", self.model, billed["cost"], prompt_tokens=billed["prompt_tokens"],
                         completion_tokens=billed["completion_tokens"], seconds=seconds, generation_id=gen_id,
                         note=f"{words} words")
        else:
            tokens = seconds * self.TOKENS_PER_SECOND
            spend.record("tts", self.model, tokens * self.PRICE_PER_TOKEN[self.tier] + words * 1.3 * 5e-7,
                         completion_tokens=int(tokens), seconds=seconds, generation_id=gen_id,
                         note=f"{words} words", estimated=True)

    def describe(self) -> dict:
        return {**super().describe(), "model": self.model, "voice": self.voice, "instructions": self.instructions}


#: Capital-letter runs that are words or names said as one, never spelled out letter by letter.
_SAID_AS_ONE = {"NCERT", "OK", "ASA", "SAS", "SSS", "RHS", "AAS", "CPCT", "CPCTC", "TV", "USA", "UK", "AI", "DNA"}
_POINT_NAMES = re.compile(r"\b[A-Z]{2,5}\b")


def spell_point_names(text: str, sep: str = ", ") -> str:
    """Point names (AB, ABCD) with a break between the letters, so a voice says each letter.

    Measured 2026-10-26 by transcribing every take with faster-whisper: Sarvam English heard 100% of the letters
    right with commas ("A, B, C, D") against 90% as written ("AB" ran together as one sound); the owner's Kavya
    voice 97.5%. Edge voices did best with spaces (``sep=" "``). Only the voice's text changes; the screen keeps
    "ABCD".
    """
    return _POINT_NAMES.sub(lambda m: m.group(0) if m.group(0) in _SAID_AS_ONE else sep.join(m.group(0)), text)


class SarvamBackend(SpeechBackend):
    """Sarvam AI text-to-speech (``bulbul``), one voice for the whole lesson or none.

    The engine's ``UniversalTTSService`` reaches Sarvam too, but it answers a failed call
    with ANOTHER provider's voice for that one clip. In a lesson of thirty blocks that is a
    narrator who changes mid-way, which testers had already reported as "voice mixing".
    Here a failure raises, so the harness moves the whole lesson to its next voice.

    Measured 2026-10-09 with ``bulbul:v3`` / ``shubh`` / ``hi-IN``: Hinglish written in Latin
    letters is read as Hinglish; 386 characters came back as 22.5 s of 22.05 kHz mono wav
    in about nine seconds; 1548 characters were accepted in one request. Longer text is
    cut at sentence ends and the pieces are joined.

    ``pace`` matters: on one 64-word Hinglish block the voice spoke 196 words a minute at
    1.0, about 168 at 0.9 and 0.8, 157 at 0.75, 134 at 0.7 (English at 0.7: 135). It is not
    a linear dial and varies by ten or so between calls. The harness asks for 0.75.
    """

    name = "sarvam"
    suffix = ".wav"
    URL = "https://api.sarvam.ai/text-to-speech"
    MAX_CHARS = 1400

    def __init__(self, speaker: str = "shubh", language: str = "hi-IN", pace: float = 1.0, model: str | None = None):
        self.speaker, self.language, self.pace = speaker or "shubh", language or "hi-IN", float(pace)
        self.model = model or os.getenv("SARVAM_TTS_MODEL", "bulbul:v3")

    def cache_key(self) -> str:
        return f"sarvam|{self.model}|{self.speaker}|{self.language}|{self.pace:g}" + ("|letters" if self._spells() else "")

    def _spells(self) -> bool:
        """English takes point names letter by letter (``SARVAM_SPELL_POINTS=0`` turns it off)."""
        return self.language.lower().startswith("en") and os.getenv("SARVAM_SPELL_POINTS", "1") != "0"

    def pieces(self, text: str) -> list[str]:
        """The text as requests of at most ``MAX_CHARS``, cut at sentence ends."""
        from .contract import split_sentences
        out, current = [], ""
        for sentence in split_sentences(text) or [text]:
            if current and len(current) + 1 + len(sentence) > self.MAX_CHARS:
                out.append(current)
                current = ""
            current = f"{current} {sentence}".strip()
        return out + ([current] if current else [])

    def _request(self, text: str, key: str) -> bytes:
        import base64
        import time

        import httpx
        payload = {"text": text, "target_language_code": self.language, "speaker": self.speaker, "model": self.model,
                   "pace": self.pace}
        last_error: Exception | None = None
        for attempt in range(3):
            try:
                r = httpx.post(self.URL, headers={"api-subscription-key": key, "Content-Type": "application/json"},
                               json=payload, timeout=120.0)
                if r.status_code == 200:
                    return base64.b64decode(r.json()["audios"][0])
                last_error = RuntimeError(f"Sarvam TTS HTTP {r.status_code}: {r.text[:200]}")
                if r.status_code not in (408, 409, 425, 429, 500, 502, 503, 504):
                    raise last_error
            except httpx.HTTPError as exc:
                last_error = exc
            if attempt < 2:
                time.sleep(1.5 * (attempt + 1))
        raise last_error or RuntimeError("Sarvam TTS failed")

    def synthesize(self, text: str, dest: Path) -> None:
        import io

        from .. import spend
        key = os.getenv("SARVAM_AI_KEY", "").strip()
        if not key:
            raise RuntimeError("SARVAM_AI_KEY is not set; the sarvam speech backend needs it")
        frames, params = [], None
        if self._spells():
            text = spell_point_names(text)
        for piece in self.pieces(text):
            with wave.open(io.BytesIO(self._request(piece, key)), "rb") as clip:
                if params is None:
                    params = (clip.getnchannels(), clip.getsampwidth(), clip.getframerate())
                elif params != (clip.getnchannels(), clip.getsampwidth(), clip.getframerate()):
                    raise RuntimeError("Sarvam TTS answered two pieces of one block in different audio formats")
                frames.append(clip.readframes(clip.getnframes()))
        if params is None or not any(frames):
            raise RuntimeError("Sarvam TTS returned no audio")
        with wave.open(str(dest), "wb") as out:
            out.setnchannels(params[0])
            out.setsampwidth(params[1])
            out.setframerate(params[2])
            out.writeframes(b"".join(frames))
        seconds = sum(len(f) for f in frames) / (params[0] * params[1] * params[2])
        # Not an OpenRouter call and not in dollars: recorded so the usage is visible, at zero cost to the budget.
        spend.record("tts", f"sarvam/{self.model}", 0.0, seconds=seconds,
                     note=f"{len(text)} chars, billed by Sarvam (not in this budget)")

    def describe(self) -> dict:
        return {**super().describe(), "model": self.model, "speaker": self.speaker, "language": self.language}


class IndicBackend(SpeechBackend):
    """The owner's own text-to-speech service: Hindi, English and mixed text at 24 kHz, one voice or none.

    ``POST <INDIC_TTS_URL>/tts`` with ``X-API-Key`` (``INDIC_TTS_KEY``) and ``{"text", "speaker"}``
    returns a finished WAV. Voices: kavya, agastya, maitri, vinaya. The address is a quick
    tunnel and changes when the service restarts, so it lives in ``.env`` and nowhere else.

    What the service's own page says, and what follows from it here:

    * it wants Hindi in Devanagari with English words in Latin letters inside the sentence
      ("इस lecture में हम loss function देखेंगे।"). A lesson for this voice is written that way
      (language ``hi-IN``), not as Hinglish in Latin letters;
    * it splits text at sentence ends and cuts a single unbroken sentence at about 25 s of
      speech, so a block is sent whole (it is sentences) and only cut here above ``MAX_CHARS``;
    * the same text sounds a little different on each call unless a ``seed`` is sent. One is
      always sent, so a block that is asked for again is the same clip;
    * a call is cut off by the tunnel after about 100 s.

    Measured 2026-10-09: 17 words of mixed text came back as 7.25 s of audio in 3.9 s, about
    141 words a minute, the pace the lesson lengths are budgeted on. Like ``SarvamBackend`` a
    failed clip raises, so a lesson never changes narrator mid-way.

    Two things the owner asked for the same day ("calling the audio API which we have created
    rather than generating it itself", "you can iterate for images and audio again and again"):

    * **A Hinglish lesson is written in Latin letters and this voice reads Devanagari.** With a
      language of ``hinglish`` or ``hi-IN`` in the spec (``indic:kavya/hinglish``), a block
      that is mostly Latin letters is first put into the form the service asks for: Hindi
      words in Devanagari, every English word left exactly as it is. A small model does it
      (``voice_script``), code checks that it changed the script and not the words, the
      answer is kept by the text, and anything doubtful means the block is sent as written.
      Captions and word timing keep the lesson's own text.
    * **A clip that is plainly wrong is asked for again.** Its audio costs nothing, so a clip
      far too short or too long for its words, or nearly silent, is requested with another
      seed (``RETRIES`` more at most) and the most plausible one is kept.
    """

    name = "indic"
    suffix = ".wav"
    MAX_CHARS = 1800
    SPEAKERS = ("kavya", "agastya", "maitri", "vinaya")
    RETRIES = 2                      # more requests for one piece when its clip is plainly wrong
    PACE = (1.2, 5.2)                # words a second a real reading falls between (it measured about 3)
    HINDI = ("hinglish", "hi-in", "hi")

    def __init__(self, speaker: str = "kavya", temperature: float = 0.4, seed: int = 7, language: str = ""):
        self.speaker, self.temperature, self.seed = (speaker or "kavya").strip().lower(), float(temperature), int(seed)
        self.language = (language or "").strip().lower()
        if self.speaker not in self.SPEAKERS:
            raise ValueError(f"unknown voice {speaker!r} (use one of {', '.join(self.SPEAKERS)})")

    def cache_key(self) -> str:
        # "deva1": the block is spoken from its Devanagari form (and from which wording of that step)
        return f"indic|{self.speaker}|{self.temperature:g}|{self.seed}" + ("|deva1" if self.language in self.HINDI else "")

    def spoken_form(self, text: str) -> str:
        """The block as this voice should be handed it. Unchanged unless it is Latin-letter Hindi."""
        if self.language not in self.HINDI:
            return text
        letters = [c for c in text if c.isalpha()]
        if not letters or sum(1 for c in letters if "\u0900" <= c <= "\u097f") > 0.3 * len(letters):
            return text                                  # already Devanagari (a hi-IN lesson), or nothing to read
        return voice_script(text) or text

    pieces = SarvamBackend.pieces          # the same cut at sentence ends, to this class's MAX_CHARS

    def plausible(self, clip: bytes, text: str) -> float:
        """How far a clip is from a real reading of ``text``: 0 is fine, more is worse (None-safe, never raises)."""
        import io
        try:
            with wave.open(io.BytesIO(clip), "rb") as w:
                seconds = w.getnframes() / float(w.getframerate() or 1)
                samples = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16) if w.getsampwidth() == 2 else None
        except (wave.Error, EOFError, ValueError):
            return 9.0
        words = max(1, len(text.split()))
        if seconds < 0.3 or (samples is not None and len(samples) and float(np.abs(samples).mean()) < 40):
            return 8.0                                   # nothing, or nearly silent
        rate = words / seconds
        low, high = self.PACE
        return 0.0 if low <= rate <= high else min(7.0, abs(rate - 3.0))

    def _checked(self, text: str, url: str, key: str) -> bytes:
        """One piece of text as audio, asked for again with another seed when the clip is plainly wrong."""
        best, best_score = None, None
        for attempt in range(1 + self.RETRIES):
            clip = self._request(text, url, key, seed=self.seed + attempt)
            score = self.plausible(clip, text)
            if best is None or score < best_score:
                best, best_score = clip, score
            if score == 0.0:
                break
        return best

    def _request(self, text: str, url: str, key: str, seed: int | None = None) -> bytes:
        import time

        import httpx
        payload = {"text": text, "speaker": self.speaker, "temperature": self.temperature,
                   "seed": self.seed if seed is None else seed}
        last_error: Exception | None = None
        for attempt in range(3):
            try:
                r = httpx.post(f"{url}/tts", headers={"X-API-Key": key, "Content-Type": "application/json"},
                               json=payload, timeout=110.0)
                if r.status_code == 200 and r.content[:4] == b"RIFF":
                    return r.content
                last_error = RuntimeError(f"the speech service answered HTTP {r.status_code}: {r.text[:160]}"
                                          if r.status_code != 200 else "the speech service answered 200 with no audio")
                if r.status_code in (400, 401, 403, 422):       # a wrong key or a bad request will not get better
                    raise last_error
            except httpx.HTTPError as exc:
                last_error = exc
            if attempt < 2:
                time.sleep(1.5 * (attempt + 1))
        raise last_error or RuntimeError("the speech service failed")

    def synthesize(self, text: str, dest: Path) -> None:
        import io

        from .. import spend
        url, key = os.getenv("INDIC_TTS_URL", "").strip().rstrip("/"), os.getenv("INDIC_TTS_KEY", "").strip()
        if not url or not key:
            raise RuntimeError("INDIC_TTS_URL and INDIC_TTS_KEY are not both set; the indic speech backend needs them")
        frames, params = [], None
        for piece in self.pieces(self.spoken_form(text)):
            with wave.open(io.BytesIO(self._checked(piece, url, key)), "rb") as clip:
                shape = (clip.getnchannels(), clip.getsampwidth(), clip.getframerate())
                if params is not None and params != shape:
                    raise RuntimeError("the speech service answered two pieces of one block in different audio formats")
                params = shape
                frames.append(clip.readframes(clip.getnframes()))
        if params is None or not any(frames):
            raise RuntimeError("the speech service returned no audio")
        with wave.open(str(dest), "wb") as out:
            out.setnchannels(params[0])
            out.setsampwidth(params[1])
            out.setframerate(params[2])
            out.writeframes(b"".join(frames))
        seconds = sum(len(f) for f in frames) / (params[0] * params[1] * params[2])
        spend.record("tts", f"indic/{self.speaker}", 0.0, seconds=seconds,
                     note=f"{len(text)} chars, the owner's own speech service (not in this budget)")

    def describe(self) -> dict:
        return {**super().describe(), "speaker": self.speaker, "temperature": self.temperature, "seed": self.seed,
                "language": self.language}


VOICE_SCRIPT_MODELS = "google/gemini-3.5-flash-lite,google/gemini-2.5-flash,openai/gpt-5.4-nano"
VOICE_SCRIPT_SYSTEM = """You prepare narration for a Hindi text-to-speech voice. The narration is Hinglish: Hindi written in Latin
letters, with English words in it. Write every HINDI word in Devanagari. Leave every ENGLISH word exactly as it is, in Latin
letters: numbers written as words (three, thirty-six), units, operations (plus, into, equals, by), subject terms (cell membrane,
prime factor, right angle) and any other English word or name. Change no word, add none, drop none, keep the order and the
punctuation; a Hindi sentence that ends with a full stop ends with the danda (।). Return ONLY JSON: {"text": "..."}"""
_DEVANAGARI = __import__("re").compile("[\u0900-\u097f]")
#: Words that are English whatever surrounds them: after the rewrite each must still be there, in Latin letters.
_SURELY_ENGLISH = frozenset("""zero one two three four five six seven eight nine ten eleven twelve twenty thirty forty fifty
sixty seventy eighty ninety hundred thousand plus minus into equals squared cubed divided fraction number numbers square
triangle angle circle radius area cell membrane nucleus energy oxygen water force motion speed light heat prime factor
factors pair pairs example question answer""".split())


def voice_script(text: str, llm=None) -> str | None:
    """Latin-letter Hinglish as a Hindi voice wants it: Hindi in Devanagari, English as it is. None when not sure.

    Kept by the text under ``<workspace>/cache/voice_script/``, so a block is rewritten
    once. Code decides whether the answer may be used: it must hold Devanagari, be of
    about the same number of words and sentences, bring in no digit, and keep in Latin
    letters every word of the block that is certainly English. A rewrite that fails any of
    these is not spoken: the block goes to the voice as it was written.
    """
    import hashlib
    import json
    import re

    from .. import paths
    text = re.sub(r"\s+", " ", str(text or "")).strip()
    if not text:
        return None
    kept = paths.cache("voice_script") / (hashlib.sha256(text.encode("utf-8")).hexdigest()[:24] + ".json")
    if kept.is_file():
        try:
            return json.loads(kept.read_text(encoding="utf-8")).get("text") or None
        except ValueError:
            pass
    if llm is None:
        key = (os.getenv("OPENROUTER_API_KEY") or "").strip()
        if not key:
            return None
        from ..engine import llm as engine_llm

        def llm(prompt: str, system: str):
            models = [m.strip() for m in knobs.get("HARNESS_VOICE_SCRIPT_MODELS", VOICE_SCRIPT_MODELS).split(",") if m.strip()]
            return engine_llm.loads_json_lenient(engine_llm.call_openrouter(
                key, prompt, system, temperature=0.0, models=models, max_tokens=None, json_object=True,
                note="voice-script", timeout=90.0))
    try:
        answer = llm(text, VOICE_SCRIPT_SYSTEM)
    except Exception:  # noqa: BLE001 - a better reading is an improvement, never a requirement
        return None
    out = re.sub(r"\s+", " ", str((answer or {}).get("text") or "")).strip() if isinstance(answer, dict) else ""
    words_in, words_out = text.split(), out.split()
    sentences = lambda t: len([x for x in re.split(r"[.?!।]+", t) if x.strip()])  # noqa: E731
    english = {w for w in re.findall(r"[a-z]+", text.lower()) if w in _SURELY_ENGLISH}
    still = set(re.findall(r"[a-z]+", out.lower()))
    good = (bool(_DEVANAGARI.search(out)) and words_in and 0.8 <= len(words_out) / len(words_in) <= 1.25
            and sentences(out) == sentences(text) and not (re.search(r"\d", out) and not re.search(r"\d", text))
            and english <= still)
    try:
        kept.write_text(json.dumps({"text": out if good else "", "from": text}, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass
    return out if good else None


class EngineBackend(SpeechBackend):
    """The engine's speech chain, reused for long-form narration.

    ``UniversalTTSService`` already carries the provider retries, the failover order
    and the shared cache that the short-video path depends on; routing long-form
    blocks through it means one speech stack to maintain instead of two.
    """

    name = "engine"
    suffix = ".mp3"

    def __init__(self, provider: str = "sarvam", language: str = "en-IN", speaker: str = "shubh",
                 tts_model: str | None = None):
        self.provider, self.language, self.speaker, self.tts_model = provider, language, speaker, tts_model
        self._service = None

    def cache_key(self) -> str:
        return f"engine|{self.provider}|{self.language}|{self.speaker}|{self.tts_model or ''}"

    def synthesize(self, text: str, dest: Path) -> None:
        if self._service is None:
            from ..viz_helpers import UniversalTTSService  # imports manim; deferred on purpose
            self._service = UniversalTTSService(
                language=self.language, speaker=self.speaker, provider=self.provider,
                tts_model=self.tts_model, cache_dir=str(dest.parent / "_engine_tts"))
        result = self._service.generate_from_text(text)
        produced = Path(self._service.cache_dir) / result["original_audio"]
        # The chain may answer with mp3 (providers) or wav (the silence tier): let
        # ffmpeg sniff the container instead of trusting the suffix.
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(produced), str(dest)], check=True)

    def describe(self) -> dict:
        return {**super().describe(), "provider": self.provider, "language": self.language,
                "speaker": self.speaker}


def get_backend(spec: str | SpeechBackend | None) -> SpeechBackend:
    """Parse a ``--voice`` spec (see the module docstring) into a backend."""
    if isinstance(spec, SpeechBackend):
        return spec
    kind, _, arg = (spec or "silent").partition(":")
    kind = kind.strip().lower()
    if kind == "silent":
        return SilentBackend(float(arg)) if arg else SilentBackend()
    if kind == "kokoro":
        voice, _, speed = arg.partition("@")
        return KokoroBackend(voice=voice or "af_heart", speed=float(speed) if speed else 0.85)
    if kind == "gtts":
        return GTTSBackend(arg or "en")
    if kind == "gemini":
        # gemini:lite/Kore|warm unhurried teacher   (tier, voice, optional instructions)
        spec_part, _, instructions = arg.partition("|")
        tier, _, voice = spec_part.partition("/")
        return OpenRouterTTSBackend(tier=tier.strip() or "flash", voice=voice.strip() or "Kore",
                                    instructions=instructions.strip())
    if kind == "sarvam":
        # sarvam:shubh/hi-IN@0.95   (speaker, language, optional pace)
        spec_part, _, pace = arg.partition("@")
        speaker, _, language = spec_part.partition("/")
        return SarvamBackend(speaker=speaker.strip() or "shubh", language=language.strip() or "hi-IN",
                             pace=float(pace) if pace else 1.0)
    if kind == "indic":
        # indic:kavya   indic:maitri/hinglish@0.4   (voice, the lesson's language, optional temperature)
        spec_part, _, temperature = arg.partition("@")
        speaker, _, language = spec_part.partition("/")
        return IndicBackend(speaker=speaker.strip() or "kavya", temperature=float(temperature) if temperature else 0.4,
                            language=language.strip())
    if kind == "edge":
        # edge:hi-IN-SwaraNeural/hinglish@-5%   (Microsoft voice, the lesson's language, optional rate)
        spec_part, _, rate = arg.partition("@")
        voice, _, language = spec_part.partition("/")
        return EdgeBackend(voice=voice.strip() or "en-IN-NeerjaNeural", language=language.strip(), rate=rate.strip() or "+0%")
    if kind == "http":
        # http:anika/hi-IN   (your server's voice name, the lesson's language)
        voice, _, language = arg.partition("/")
        return HttpBackend(voice=voice.strip(), language=language.strip())
    if kind == "browser":
        # browser:hi-IN   (the language the learner's device reads the captions in)
        return BrowserBackend(language=arg.strip() or "en-IN")
    if kind == "engine":
        parts = [p for p in arg.split("/") if p]
        defaults = ["sarvam", "en-IN", "shubh"]
        provider, language, speaker = (parts + defaults[len(parts):])[:3]
        return EngineBackend(provider=provider, language=language, speaker=speaker)
    raise ValueError(f"unknown speech backend {spec!r} (use silent, kokoro, gtts, gemini, sarvam, indic, edge, http, "
                     "browser or engine)")
