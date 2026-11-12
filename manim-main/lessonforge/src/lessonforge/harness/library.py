"""The source library — what a lesson is written FROM.

Until 2026-10-09 the script writer was handed a topic's name, a lesson shape and a
list of rules, and nothing about how that topic is taught. It wrote the average of
what a model has read: correct, tidy, dull (docs/research/approaches/06_*). This
module gives it sources. Three things, kept deliberately small:

* a **local cache of sources** by kind, under ``<workspace>/library/`` — the textbook
  chapter (NCERT), two or three lecture transcripts (YouTube), a teacher's lesson plan
  with its list of common mistakes (Mathematics Assessment Project), a misconception
  table (Eedi, when its file is present), and anything the requester handed in;
* **plain passage search** inside them (BM25 written out below: no vector store, no
  new dependency — the same choice as ``engine/manim_context.py``);
* a **topic graph** (``graph.json``): which sources, mistakes and earlier topics
  belong to a topic. It is an INDEX of the library, grown one topic at a time. It is
  not knowledge extracted from the text: a lesson needs three to six documents and
  they fit in one model call, so nothing is gained by mining them into triples.

House rules encoded here:

* **Every source degrades, none raises.** A dead site, a video without captions, a
  book that is not downloaded: a warning in the pack, and the pack is built from what
  remains. An empty pack is legal — it is what the writer had before.
* **Sources stay in the workspace.** Most may be read and not redistributed (NCERT is
  all rights reserved; a transcript is its speaker's; the Mathematics Assessment
  Project is non-commercial, as-is — the licence table is in
  ``06_plan_checks_and_additions.md``). ``LICENCE`` travels with every source so the
  card writer is told to paraphrase and cite, never to copy. Showing passages to app
  users is the owner's decision and nothing here does it.
* **Chunks are numbered and citable** (``S2#3``), like ``engine/sources.py``, so a line
  of the teaching card can be traced to what it stands on.
"""
from __future__ import annotations

import hashlib
import html
import json
import math
import os
import re
import subprocess
import time
from pathlib import Path

from .. import knobs
from .. import paths

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"
NCERT_PDF = "https://ncert.nic.in/textbook/pdf"
MAP_SITE = "https://www.map.mathshell.org"
PASSAGE_WORDS = 130
#: Words kept from one source. A whole chapter is ~8000 words, most of it other topics.
MAX_SOURCE_WORDS = int(os.getenv("LIBRARY_MAX_SOURCE_WORDS", "3200"))
HTTP_TIMEOUT = 45

LICENCE = {
    "textbook": "NCERT textbook: free to read, all rights reserved. Cite the chapter and say it in your own words.",
    "lecture": "A lecture transcript: the speaker's own work. Study the order of ideas, the example and the questions; reuse no sentence.",
    "lesson_plan": "Mathematics Assessment Project: non-commercial, as-is. Say its common issues in your own words and cite it.",
    "misconceptions": "A research list of learner mistakes. Cite it; say each mistake in your own words.",
    "given": "Handed in by the requester.",
    "web": "A web page: its owner's work. Cite it and say it in your own words.",
}

#: The books this module knows without a catalog. ``scripts/ncert_download.py --from-js``
#: writes ``library/ncert/catalog.json``, whose rows extend this table. Codes checked
#: against ncert.nic.in on 2026-10-09 (a class may have an older and a newer book).
NCERT_BOOKS = [
    {"klass": 6, "subject": "maths", "code": "fegp1", "book": "Ganita Prakash, Class 6", "chapters": 10},
    {"klass": 6, "subject": "science", "code": "fecu1", "book": "Curiosity, Class 6", "chapters": 12},
    {"klass": 7, "subject": "maths", "code": "gegp1", "book": "Ganita Prakash, Class 7", "chapters": 8},
    {"klass": 7, "subject": "science", "code": "gecu1", "book": "Curiosity, Class 7", "chapters": 12},
    {"klass": 8, "subject": "maths", "code": "hemh1", "book": "Mathematics, Class 8", "chapters": 13},
    {"klass": 8, "subject": "maths", "code": "hegp1", "book": "Ganita Prakash, Class 8", "chapters": 8},
    {"klass": 8, "subject": "science", "code": "hecu1", "book": "Curiosity, Class 8", "chapters": 13},
    {"klass": 9, "subject": "maths", "code": "iemh1", "book": "Mathematics, Class 9", "chapters": 12},
    {"klass": 9, "subject": "science", "code": "iesc1", "book": "Science, Class 9", "chapters": 14},
    {"klass": 10, "subject": "maths", "code": "jemh1", "book": "Mathematics, Class 10", "chapters": 14},
    {"klass": 10, "subject": "science", "code": "jesc1", "book": "Science, Class 10", "chapters": 13},
]

#: Channels that explain rather than recite, tried first. A search rank is a popularity
#: rank; a preferred channel is a guess about quality made once, by a person.
PREFERRED_CHANNELS = ("khan academy", "3blue1brown", "veritasium", "minutephysics", "numberphile", "mathologer",
                      "math antics", "don't memorise", "fuseschool", "amoeba sisters", "crashcourse",
                      "mit opencourseware", "nptel", "ncert official", "physics girl", "ted-ed")


def root(*parts: str) -> Path:
    return paths.sub("library", *parts)


# ── text ─────────────────────────────────────────────────────────────────────

_WORD = re.compile(r"[a-z0-9ऀ-ॿ]+")
_STOP = frozenset("""a an the of to in on for and or is are was were be been by with from as at it its this that these
those how what why which when where do does did we you your our can will not into than then so if but about class
chapter have has had they them their there here also each one two more most very such using use used i""".split())


def tokens(text: str) -> list[str]:
    """Search terms: lower-cased, British and American spellings met, plurals folded."""
    out = []
    for word in _WORD.findall(str(text).lower()):
        if word in _STOP or len(word) < 2:
            continue
        word = word.replace("isation", "ization").replace("ising", "izing")
        if word.endswith("ies") and len(word) > 4:
            word = word[:-3] + "y"
        elif word.endswith("s") and not word.endswith("ss") and len(word) > 3:
            word = word[:-1]
        out.append(word)
    return out


def bm25(query: str, texts: list[str], k1: float = 1.5, b: float = 0.75) -> list[float]:
    """One score per text for ``query``. Okapi BM25, written out because it is twenty lines."""
    docs = [tokens(t) for t in texts]
    if not docs:
        return []
    terms = list(dict.fromkeys(tokens(query)))
    average = sum(len(d) for d in docs) / len(docs) or 1.0
    scores = [0.0] * len(docs)
    for term in terms:
        counts = [d.count(term) for d in docs]
        containing = sum(1 for c in counts if c)
        if not containing:
            continue
        idf = math.log(1 + (len(docs) - containing + 0.5) / (containing + 0.5))
        for i, count in enumerate(counts):
            if count:
                scores[i] += idf * count * (k1 + 1) / (count + k1 * (1 - b + b * len(docs[i]) / average))
    return scores


def passages(text: str, words: int = PASSAGE_WORDS) -> list[str]:
    """Cut text into passages of about ``words`` words, at blank lines where there are any."""
    blocks = [re.sub(r"\s+", " ", b).strip() for b in re.split(r"\n\s*\n", str(text))]
    out, current, count = [], [], 0
    for block in (b for b in blocks if b):
        pieces = block.split()
        while len(pieces) > 2 * words:          # a transcript is one block: cut it by length
            out.append(" ".join(pieces[:words]))
            pieces = pieces[words:]
        current.append(" ".join(pieces))
        count += len(pieces)
        if count >= words:
            out.append(" ".join(current))
            current, count = [], 0
    if current:
        out.append(" ".join(current))
    return [p for p in out if len(p.split()) >= 8]


_PDF_NOISE = re.compile(r"^\s*(reprint \d{4}.*|\d{1,3}|not to be republished.*|© ?ncert.*)\s*$", re.I)

# ── cleaning a source's text ─────────────────────────────────────────────────
# Marks that extraction leaves in a text and that are not the lesson's words. The rule is the one a careful
# copy-editor of converted lessons works by: fix only what is certainly an artefact, change no word of the
# content, and when in doubt leave it, because a false fix is worse than none. So this is a table, not a model.
# What each line is for was counted on the library itself (56 NCERT chapters, 2026-10-09): 964 printer's
# marks ("Chapter 2.indd 15 …") and 385 lines holding only "z", the bullet of a symbol font read as a letter.
_PRINT_LINE = re.compile(r"^\s*(?:\S.{0,60}\.indd\s+\d+.*|rationalised \d{4}.*|reprint \d{4}.*|not to be republished.*|"
                         r"© ?ncert.*|page \d+ of \d+|\d{1,3})\s*$", re.I)
_BULLET_LINE = re.compile(r"^\s*[z\uf06c\uf0b7•■▪●◆]\s*$")
_BULLET_INLINE = re.compile(r"(?<=[.?!:;])\s+z\s+(?=[A-Z\u0900-\u097F])")
_LEAKED_TAG = re.compile(r"</?(?:div|span|br|p|font|table|tbody|tr|td|th|ul|ol|li|a|img|script|style|iframe)\b[^<>]{0,200}>", re.I)
_ENTITY = re.compile(r"&(?:[a-z]{2,8}|#\d{2,5});", re.I)
# UTF-8 read as Windows-1252 and saved again: "Â°" for "°", "Ã—" for "×", "â‰¥" for "≥", "Ï€" for "π".
_MOJIBAKE = re.compile("[\u00c2-\u00f4][\u0080-\u00bf\u0152\u0153\u0160\u0161\u0178\u017d\u017e\u0192\u02c6\u02dc"
                       "\u2013-\u203a\u20ac\u2122]{1,3}")


def _unscramble(match: re.Match) -> str:
    try:
        fixed = match.group(0).encode("cp1252").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return match.group(0)
    return fixed if len(fixed) == 1 else match.group(0)       # exactly one character came back, or nothing is touched


def clean(text: str) -> str:
    """A source's text without the marks extraction left in it. No word of the content is changed."""
    text = _MOJIBAKE.sub(_unscramble, str(text or "").replace("\r\n", "\n"))
    text = _LEAKED_TAG.sub(" ", text)
    text = _ENTITY.sub(lambda m: html.unescape(m.group(0)).replace("\u00a0", " "), text)
    lines, bullet = [], False
    for line in text.split("\n"):
        if _PRINT_LINE.match(line):
            continue
        if _BULLET_LINE.match(line):            # a bullet on a line of its own belongs to the line after it
            bullet = True
            continue
        line = line.rstrip()
        lines.append(("- " + line.lstrip()) if bullet and line.strip() else line)
        bullet = bullet and not line.strip()
    return re.sub(r"\n{3,}", "\n\n", _BULLET_INLINE.sub(" - ", "\n".join(lines))).strip()



def pdf_text(pdf: Path) -> str:
    """The text of a PDF (poppler's ``pdftotext``), cached beside it. '' when it cannot be read."""
    cached = pdf.with_suffix(".txt")
    try:
        if cached.is_file() and cached.stat().st_mtime >= pdf.stat().st_mtime:
            return cached.read_text(encoding="utf-8")
        done = subprocess.run(["pdftotext", "-enc", "UTF-8", str(pdf), "-"], capture_output=True, timeout=180)
        lines = [ln.rstrip() for ln in done.stdout.decode("utf-8", "ignore").replace("\f", "\n\n").splitlines()]
        text = re.sub(r"\n{3,}", "\n\n", "\n".join(ln for ln in lines if not _PDF_NOISE.match(ln))).strip()
        cached.write_text(text, encoding="utf-8")
        return text
    except (OSError, subprocess.SubprocessError):
        return ""


def fetch(url: str, dest: Path, retries: int = 3) -> str:
    """Download ``url`` to ``dest``, cache-first. Returns ok | cached | 404 | err. Never raises."""
    if dest.is_file() and dest.stat().st_size > 0:
        return "cached"
    import requests  # noqa: PLC0415
    for attempt in range(retries):
        try:
            response = requests.get(url, headers={"User-Agent": UA}, timeout=HTTP_TIMEOUT)
            if response.status_code == 404:
                return "404"
            if response.ok and response.content:
                part = dest.with_suffix(dest.suffix + ".part")
                part.write_bytes(response.content)
                part.replace(dest)
                return "ok"
        except Exception:  # noqa: BLE001 - a flaky site is the normal case here
            pass
        time.sleep(1.5 * (attempt + 1))
    return "err"


# ── the textbook ─────────────────────────────────────────────────────────────

def ncert_books(klass: int | None, subject: str | None = None) -> list[dict]:
    """Books for a class (and subject), from the built-in table and the downloader's catalog."""
    rows = [dict(b) for b in NCERT_BOOKS]
    catalog = root("ncert") / "catalog.json"
    if catalog.is_file():
        try:
            known = {b["code"] for b in rows}
            for row in json.loads(catalog.read_text(encoding="utf-8")):
                if isinstance(row, dict) and row.get("code") and row["code"] not in known and row.get("klass"):
                    name = str(row.get("subject", "")).lower()
                    rows.append({"klass": int(row["klass"]), "code": row["code"], "book": row.get("book") or row["code"],
                                 "chapters": int(row.get("chapters") or 0),
                                 "subject": "maths" if "math" in name else "science" if "scien" in name else name})
        except (ValueError, OSError):
            pass
    return [b for b in rows if (klass is None or b["klass"] == klass) and (not subject or b["subject"] == subject)]


def ncert_download(book: dict, log=print) -> int:
    """Fetch a book's chapters into the library (cache-first). Returns how many are on disk."""
    folder = root("ncert", book["code"])
    have, misses = 0, 0
    for n in range(1, (book.get("chapters") or 16) + 1):
        status = fetch(f"{NCERT_PDF}/{book['code']}{n:02d}.pdf", folder / f"{book['code']}{n:02d}.pdf")
        have += status in ("ok", "cached")
        misses = misses + 1 if status in ("404", "err") else 0
        if misses >= 3:                           # past the end of the book, or the site is down
            break
    log(f"[library] NCERT {book['code']} ({book['book']}): {have} chapter(s) on disk")
    return have


def _chapter_title(text: str, fallback: str) -> str:
    """A chapter's heading when the PDF's text has one; older books draw it as a picture."""
    lines = [ln.strip() for ln in text.splitlines()[:8] if ln.strip()]
    heading = []
    for line in lines:
        if re.fullmatch(r"[A-Z][A-Z ,'&:-]{2,40}", line) and not re.search(r"\d", line):
            heading.append(line)
        elif heading:
            break
    title = " ".join(heading).title().strip()
    return title if 1 <= len(title.split()) <= 9 else fallback


def find_chapter(query: str, klass: int | None, subject: str | None = None, log=print, download: bool = True) -> list[dict]:
    """The chapter(s) that cover ``query``: the best one, and a second book's if it is close.

    Every chapter of every candidate book is scored in ONE search, by its five best
    passages: a long chapter that mentions the words once must not beat a short one that
    is about them, and scores from separate searches cannot be compared with each other.
    """
    chapters, parts, owner = [], [], []
    for book in ncert_books(klass, subject):
        if download:
            ncert_download(book, log=log)
        for pdf in sorted(root("ncert", book["code"]).glob(f"{book['code']}[0-9][0-9].pdf")):
            text = pdf_text(pdf)
            own = passages(text)
            if not own:
                continue
            number = int(pdf.stem[-2:])
            chapters.append({"book": book, "chapter": number, "text": text, "path": str(pdf),
                             "title": _chapter_title(text, f"chapter {number}")})
            parts += own
            owner += [len(chapters) - 1] * len(own)
    if not chapters:
        return []
    scores = bm25(query, parts)
    by_chapter: dict[int, list[float]] = {}
    for score, index in zip(scores, owner):
        by_chapter.setdefault(index, []).append(score)
    for index, chapter in enumerate(chapters):
        chapter["score"] = round(sum(sorted(by_chapter.get(index, [0.0]), reverse=True)[:5]), 2)
    ranked = sorted((c for c in chapters if c["score"] > 0), key=lambda c: -c["score"])
    if not ranked:
        return []
    log("[library] textbook: " + "; ".join(f"{c['book']['book']} ch {c['chapter']} {c['title']} ({c['score']})" for c in ranked[:4]))
    best, second = ranked[0], None
    for other in ranked[1:]:                      # a second treatment only from a DIFFERENT book, and only if close
        if other["book"]["code"] != best["book"]["code"] and other["score"] >= 0.6 * best["score"]:
            second = other
            break
    return [best] + ([second] if second else [])


# ── lectures ─────────────────────────────────────────────────────────────────

_YT_ID = re.compile(r"(?:v=|youtu\.be/|/shorts/|/embed/)([A-Za-z0-9_-]{11})")


def _seconds(length: str) -> int:
    total = 0
    for part in str(length).split(":"):
        total = total * 60 + (int(part) if part.isdigit() else 0)
    return total


def youtube_search(query: str, limit: int = 8) -> list[dict]:
    """Videos for a query, read from the results page (no API key). [] on any failure."""
    try:
        import requests  # noqa: PLC0415
        page = requests.get("https://www.youtube.com/results", params={"search_query": query},
                            headers={"User-Agent": UA, "Accept-Language": "en-IN,en;q=0.9"}, timeout=HTTP_TIMEOUT)
        found = re.search(r"var ytInitialData = (\{.*?\});</script>", page.text, re.S)
        data = json.loads(found.group(1)) if found else {}
    except Exception:  # noqa: BLE001
        return []
    out: list[dict] = []

    def walk(node) -> None:
        if isinstance(node, dict):
            video = node.get("videoRenderer")
            if isinstance(video, dict) and video.get("videoId"):
                runs = lambda key: "".join(r.get("text", "") for r in (video.get(key) or {}).get("runs", []))  # noqa: E731
                out.append({"id": video["videoId"], "title": runs("title"), "channel": runs("ownerText"),
                            "seconds": _seconds((video.get("lengthText") or {}).get("simpleText", ""))})
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)
    walk(data)
    return out[:limit]


def transcript(video_id: str) -> dict:
    """{'text', 'language', 'generated'} for a video, cached; ``text`` is '' when it has no captions."""
    cached = root("youtube") / f"{video_id}.json"
    if cached.is_file():
        try:
            return json.loads(cached.read_text(encoding="utf-8"))
        except ValueError:
            pass
    result = {"text": "", "language": "", "generated": None, "why": ""}
    try:
        from youtube_transcript_api import YouTubeTranscriptApi  # noqa: PLC0415
        fetched = YouTubeTranscriptApi().fetch(video_id, languages=["en", "en-IN", "hi", "hi-IN"])
        text = " ".join(getattr(s, "text", "") or "" for s in getattr(fetched, "snippets", fetched))
        text = re.sub(r"\s+", " ", re.sub(r"\[[^\]]{1,20}\]", " ", text)).strip()
        result.update(text=text, language=getattr(fetched, "language_code", ""), generated=getattr(fetched, "is_generated", None))
    except Exception as exc:  # noqa: BLE001
        result["why"] = f"{type(exc).__name__}: {str(exc)[:120]}"
    if not result["text"]:
        # From a cloud machine YouTube refuses the transcript API ("IpBlocked") and yt-dlp's usual player ("Sign in
        # to confirm you're not a bot"), while the EMBEDDED player still lists the captions (2026-10-20).
        result.update({k: v for k, v in _captions_by_ytdlp(video_id).items() if v not in ("", None)})
    if result["text"]:
        cached.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
    return result


def _captions_by_ytdlp(video_id: str, wanted: tuple[str, ...] = ("en", "en-IN", "en-GB", "en-US", "hi")) -> dict:
    """{'text', 'language', 'generated', 'why'} from the captions the embedded player lists; text '' on any failure.

    ONE caption track is fetched: the author's own in the first wanted language, else
    YouTube's automatic one in the language spoken (``-orig``). Asking for several at once
    is answered "429 Too Many Requests" (every automatic track is a machine translation).
    """
    try:
        import yt_dlp  # noqa: PLC0415
    except ImportError:
        return {"text": "", "why": "yt-dlp is not installed"}
    options = {"skip_download": True, "ignore_no_formats_error": True, "quiet": True, "no_warnings": True,
               "noprogress": True, "extractor_args": {"youtube": {"player_client": ["web_embedded"]}},
               "socket_timeout": HTTP_TIMEOUT}
    try:
        with yt_dlp.YoutubeDL(options) as ydl:
            info = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=False) or {}
            own, auto = info.get("subtitles") or {}, info.get("automatic_captions") or {}
            choice = next(((lang, own[lang], False) for lang in wanted if own.get(lang)), None) or next(
                ((lang, auto[lang], True) for lang in auto if lang.endswith("-orig") and lang[:2] in {w[:2] for w in wanted}), None)
            if not choice:
                return {"text": "", "why": "no captions in " + "/".join(wanted)}
            lang, tracks, generated = choice
            url = next((t["url"] for t in tracks if t.get("ext") == "json3" and t.get("url")), "")
            if not url:
                return {"text": "", "why": "no json3 captions"}
            events = json.loads(ydl.urlopen(url).read().decode("utf-8")).get("events") or []
    except Exception as exc:  # noqa: BLE001
        return {"text": "", "why": f"yt-dlp: {type(exc).__name__}: {str(exc)[:100]}"}
    text = " ".join("".join(seg.get("utf8", "") for seg in e.get("segs") or []) for e in events)
    text = re.sub(r"\s+", " ", re.sub(r"\[[^\]]{1,20}\]", " ", text)).strip()
    return {"text": text, "language": lang.replace("-orig", ""), "generated": generated, "why": "" if text else "empty captions"}


def lectures_pack(topic: str, klass: int | None, language: str = "en-IN", count: int = 3, log=print) -> dict:
    """The lectures on a topic as a pack (``sources`` and whole-transcript ``chunks``), for ``voice.lecturer_examples``.

    Used when a lesson's teaching pack holds no lecture (a card from the concept knowledge
    base, or a pack built while YouTube refused transcripts). Free: search pages and
    caption files, cached. The text stays in the workspace.
    """
    sources, chunks = [], []
    for n, video in enumerate(find_lectures(topic, klass, language, count=count, log=log, query=topic), 1):
        spoken = "Hindi" if str(video.get("language", "")).startswith("hi") else "English"
        sources.append({"id": f"L{n}", "kind": "lecture", "title": f"{video['channel']}: {video['title']}"[:140],
                        "url": f"https://www.youtube.com/watch?v={video['id']}", "note": f"{spoken} lecture"})
        chunks.append({"id": f"L{n}#1", "source": f"L{n}", "text": clean(video["text"])})
    return {"topic": topic, "sources": sources, "chunks": chunks}


def find_lectures(topic: str, klass: int | None, language: str = "en-IN", count: int = 3, log=print, query: str = "") -> list[dict]:
    """Up to ``count`` lecture transcripts on the topic, chosen by what is SAID in them.

    A search rank is a popularity rank and a title is a promise: the first cut took two
    videos on prime factorisation in general for a lesson on square numbers, because a
    preferred channel came first. So the transcripts of the first candidates are read
    (free) and scored against the topic like textbook chapters, in one search; a
    preferred channel only breaks a near tie. For a Hindi or Hinglish lesson one place is
    kept for a lecture found by the Hindi search, so the writer hears how the topic is
    spoken in class.
    """
    level = f" class {klass}" if klass else ""
    searches = [(f"{topic}{level}", False), (f"{topic} explained", False)]
    if language in ("hinglish", "hi-IN"):
        searches.append((f"{topic}{level} in hindi", True))
    seen, candidates, dropped = set(), [], []
    for text, hindi in searches:
        for video in youtube_search(text)[:6]:
            if video["id"] in seen or not 150 <= video["seconds"] <= 1800:
                continue
            seen.add(video["id"])
            heard = transcript(video["id"])
            if len(heard["text"].split()) >= 250:
                # A Hindi lecture's captions are Devanagari and cannot be matched to the topic's words: its TITLE
                # must name the topic. An English one may also show it in what is said.
                if not about("" if hindi and str(heard.get("language", "")).startswith("hi") else heard["text"], topic, video["title"]):
                    dropped.append(f"{video['channel']}: {video['title'][:40]}")
                    continue
                candidates.append({**video, **heard, "hindi": hindi,
                                   "preferred": any(name in video["channel"].lower() for name in PREFERRED_CHANNELS)})
    if dropped:
        log(f"[library] {len(dropped)} video(s) found by the search were not about “{topic}” and are not used: "
            + "; ".join(dropped[:4]))
    if not candidates:
        log("[library] lectures: none with a usable transcript")
        return []
    parts, owner = [], []
    for index, video in enumerate(candidates):
        own = passages(video["text"])
        parts += own
        owner += [index] * len(own)
    scores = bm25(query or topic, parts)
    for index, video in enumerate(candidates):
        mine = sorted((s for s, o in zip(scores, owner) if o == index), reverse=True)[:5]
        video["score"] = round(sum(mine) * (1.15 if video["preferred"] else 1.0), 2)
    out, per_channel = [], {}
    hindi = sorted((v for v in candidates if v["hindi"]), key=lambda v: -v["score"])   # Devanagari captions score ~0: keep search order
    if hindi:
        out.append(hindi[0])
        per_channel[hindi[0]["channel"]] = 1
    for video in sorted((v for v in candidates if not v["hindi"]), key=lambda v: -v["score"]):
        if len(out) >= count:
            break
        if video["score"] <= 0 or per_channel.get(video["channel"], 0) >= 2:
            continue
        per_channel[video["channel"]] = per_channel.get(video["channel"], 0) + 1
        out.append(video)
    log("[library] lectures: " + "; ".join(f"{v['channel']}: {v['title'][:44]} ({len(v['text'].split())} words, {v['score']})" for v in out))
    return out


# ── a teacher's lesson plan with its common mistakes (maths) ─────────────────

def map_index(log=print) -> list[dict]:
    """The Mathematics Assessment Project's classroom lessons: unit, title, goals. Crawled once."""
    cached = root("map") / "index.json"
    if cached.is_file():
        try:
            return json.loads(cached.read_text(encoding="utf-8"))
        except ValueError:
            pass
    import requests  # noqa: PLC0415
    units: dict[str, dict] = {}
    try:
        for page in ("", "?gradeid=21", "?gradeid=22", "?gradeid=23", "?gradeid=24"):
            html = requests.get(f"{MAP_SITE}/lessons.php{page}", headers={"User-Agent": UA}, timeout=HTTP_TIMEOUT).text
            for unit, collection, title in re.findall(r'href="\?unit=(\d+)&(?:amp;)?collection=(\d+)">\s*([^<]+?)\s*</a>', html):
                units.setdefault(unit, {"unit": unit, "collection": collection, "title": re.sub(r"\s+", " ", title)})
        for entry in units.values():
            html = requests.get(f"{MAP_SITE}/lessons.php?unit={entry['unit']}&collection={entry['collection']}",
                                headers={"User-Agent": UA}, timeout=HTTP_TIMEOUT).text
            body = re.sub(r"<[^>]+>", " ", re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", html))
            goals = re.search(r"Mathematical goals(.{0,900})", re.sub(r"\s+", " ", body), re.I)
            entry["goals"] = (goals.group(1) if goals else "").strip()
            link = re.search(r'class="pdf"[^>]*href="(download\.php\?fileid=\d+)"', html)
            entry["pdf"] = f"{MAP_SITE}/{link.group(1)}" if link else ""
            entry["url"] = f"{MAP_SITE}/lessons.php?unit={entry['unit']}&collection={entry['collection']}"
    except Exception as exc:  # noqa: BLE001
        log(f"[library] lesson plans: index not built ({type(exc).__name__})")
        return []
    rows = list(units.values())
    if rows:
        cached.write_text(json.dumps(rows, indent=1, ensure_ascii=False), encoding="utf-8")
    log(f"[library] lesson plans: indexed {len(rows)} Mathematics Assessment Project lessons")
    return rows


_GENERIC = frozenset("number given whether find finding through method large small simple problem solve solving value term".split())


def find_lesson_plan(topic: str, log=print) -> dict | None:
    """The one lesson plan on the topic, with its text. None when nothing matches.

    Matched on the TOPIC's own words, and at least two of them that say something: with
    the lesson's goal in the query, "identify whether a given number…" once matched a
    lesson on describing triangles through the words "given" and "whether".
    """
    index = [e for e in map_index(log=log) if e.get("pdf")]
    if not index:
        return None
    scores = bm25(topic, [f"{e['title']} {e['title']} {e.get('goals', '')}" for e in index])
    best = max(range(len(index)), key=lambda i: scores[i])
    entry = index[best]
    shared = (set(tokens(topic)) - _GENERIC) & set(tokens(f"{entry['title']} {entry.get('goals', '')}"))
    if scores[best] <= 0 or len(shared) < 2:
        log("[library] lesson plans: none on this topic")
        return None
    pdf = root("map") / f"{entry['unit']}.pdf"
    if fetch(entry["pdf"], pdf) not in ("ok", "cached"):
        return None
    log(f"[library] lesson plan: {entry['title']} (shares {sorted(shared)[:4]})")
    return {**entry, "text": pdf_text(pdf)}


def eedi_misconceptions(query: str, limit: int = 12) -> list[str]:
    """Named misconceptions near the topic, from Eedi's table when its file is in the library.

    The file (``misconception_mapping.csv``, Kaggle: "Eedi - Mining Misconceptions in
    Mathematics") needs a Kaggle account and its rules accepted, so it is never fetched
    here: put it in ``<workspace>/library/eedi/`` and it is used.
    """
    table = root("eedi") / "misconception_mapping.csv"
    if not table.is_file():
        return []
    import csv  # noqa: PLC0415
    with table.open(encoding="utf-8", newline="") as handle:
        names = [row.get("MisconceptionName", "").strip() for row in csv.DictReader(handle)]
    names = [n for n in names if n]
    scores = bm25(query, names)
    ranked = sorted(range(len(names)), key=lambda i: -scores[i])
    return [names[i] for i in ranked[:limit] if scores[i] > 0]


# ── the pack ─────────────────────────────────────────────────────────────────

_CLASS = re.compile(r"\b(?:class|grade|std|standard)\s*[-:]?\s*(\d{1,2})\b", re.I)
_SCIENCE = frozenset("""force motion energy atom cell light sound heat pressure acid base metal electricity current magnet
gravity gravitation friction velocity acceleration plant animal reaction element compound mixture newton inertia density
photosynthesis respiration tissue wave work power matter solution temperature evaporation""".split())
_MATHS = frozenset("""probability chance fraction fractions decimal decimals number numbers integer integers equation
equations algebra triangle triangles angle angles area perimeter volume circle polygon ratio proportion percentage
percent prime factor factors multiple multiples square squares cube root roots theorem pythagoras pythagorean
geometry graph graphs linear quadratic polynomial polynomials sequence series arithmetic progression mean median
mode statistics trigonometry sine cosine tangent coordinate coordinates infinity infinite recurring repeating
divisible divisibility exponent exponents logarithm symmetry""".split())
#: Words a goal uses in their everyday sense ("work out", "the power of") that would otherwise name a subject.
_EVERYDAY = frozenset({"work", "power", "matter", "solution", "base", "element", "current"})
_IMPORTANT = re.compile(r"common issues|misconception|students (?:may|often|might)|mistake|error|activity|try this|think and", re.I)


def school_class(brief: dict) -> int | None:
    found = _CLASS.search(f"{brief.get('audience', '')} {brief.get('topic', '')} {brief.get('subject', '')}")
    value = int(found.group(1)) if found else None
    return value if value and 1 <= value <= 12 else None


def school_subject(brief: dict) -> str | None:
    """maths | science | None (search both). ``brief['school_subject']`` wins when given."""
    if brief.get("school_subject") in ("maths", "science"):
        return brief["school_subject"]
    named = set(tokens(f"{brief.get('topic', '')} {brief.get('subject', '')}"))
    goal = set(tokens(str(brief.get("goal", "")))) - _EVERYDAY
    science, maths = len((named | goal) & _SCIENCE), len((named | goal) & _MATHS)
    # A word of maths beats a word of science: "work out the probability of winning" (a Monty Hall lesson, 2026-10-19)
    # was sent to the Class 10 science book by "work", and its card could cite none of what it was given.
    if maths and maths >= science:
        return "maths"
    return "science" if science else None


def _trim(text: str, query: str, limit: int = MAX_SOURCE_WORDS) -> list[str]:
    """A source's passages, cut to ``limit`` words: the best for the query, kept in reading order."""
    parts = passages(text)
    if sum(len(p.split()) for p in parts) <= limit:
        return parts
    scores = bm25(query, parts)
    for i, part in enumerate(parts):            # a list of mistakes or an activity is why the source is here
        if _IMPORTANT.search(part):
            scores[i] = scores[i] * 1.5 + 0.5
    keep, words = set(), 0
    for i in sorted(range(len(parts)), key=lambda i: -scores[i]):
        size = len(parts[i].split())
        if words + size > limit:
            continue
        keep.add(i)
        words += size
    return [parts[i] for i in sorted(keep)]


# ── the topic as a textbook prints it ────────────────────────────────────────
# A requester typed "pythogeroustherom" for "a new learner for government school" (2026-10-09). The video search
# matched it loosely, the scoring query also held "understand … real life example … you think", and the pack's
# three sources were a Python tutorial, a film explainer and one lecture on Pythagoras' theorem; with no class
# number in the brief, no textbook was looked for at all. The card's own model read the topic correctly. So the
# topic is read once, the way that model read it, BEFORE anything is searched; and a source has to be about it.

TOPIC_MODELS_DEFAULT = "google/gemini-3.5-flash-lite,google/gemini-2.5-flash,openai/gpt-5.4-nano"
TOPIC_SYSTEM = """A person has typed the topic of a school lesson, perhaps misspelt, run together or in mixed Hindi and English.
Write it as an Indian school textbook's index would print it, in English: correct the spelling, separate the words, keep
what it is about and change nothing else. Then say in which class (1 to 12) NCERT textbooks first teach it properly.
Return ONLY JSON: {"topic": "…", "class": 8}   (class null when it is not a school topic)"""


def topic_llm():
    """A small, fast model through OpenRouter, metered as "topic". None without a key."""
    key = (os.getenv("OPENROUTER_API_KEY") or "").strip()
    if not key:
        return None
    from ..engine import llm as engine_llm  # noqa: PLC0415

    def call(prompt: str, system: str):
        models = [m.strip() for m in knobs.get("HARNESS_TOPIC_MODELS", TOPIC_MODELS_DEFAULT).split(",") if m.strip()]
        text = engine_llm.call_openrouter(key, prompt, system, temperature=0.0, models=models, max_tokens=None,
                                          json_object=True, note="topic", timeout=60.0)
        return engine_llm.loads_json_lenient(text)
    return call


def read_topic(brief: dict, llm=None, log=print) -> dict:
    """``{"topic", "klass", "asked"}``: the topic as a textbook prints it and the class it belongs to.

    Kept by the words that were typed (``library/topics_read.json``), so it is asked once.
    Without a model, or when the answer is unusable, the topic is the one that was typed
    and the class is whatever the brief says: exactly what happened before.
    """
    typed = re.sub(r"\s+", " ", str((brief or {}).get("topic") or "")).strip()
    said = school_class(brief)
    out = {"topic": typed, "klass": said, "asked": typed}
    if len(typed) < 3 or knobs.get("HARNESS_TOPIC_READ", "1") != "1":
        return out
    saved = root() / "topics_read.json"
    try:
        kept = json.loads(saved.read_text(encoding="utf-8")) if saved.is_file() else {}
    except ValueError:
        kept = {}
    key = typed.lower()
    if key not in kept:
        llm = llm or topic_llm()
        if llm is None:
            return out
        try:
            answer = llm(f"TOPIC AS TYPED: {typed}\nFOR: {brief.get('audience', '')}", TOPIC_SYSTEM)
        except Exception as exc:  # noqa: BLE001 - reading the topic is an improvement, never a requirement
            log(f"[library] the topic was not read ({type(exc).__name__}): searching for it as typed")
            return out
        better = re.sub(r"\s+", " ", str((answer or {}).get("topic") or "")).strip()[:120] if isinstance(answer, dict) else ""
        guess = answer.get("class") if isinstance(answer, dict) else None
        kept[key] = {"topic": better if 3 <= len(better) and len(better.split()) <= 14 else "",
                     "klass": int(guess) if isinstance(guess, (int, float)) and 1 <= int(guess) <= 12 else None}
        try:
            saved.write_text(json.dumps(kept, indent=1, ensure_ascii=False), encoding="utf-8")
        except OSError:
            pass
    read = kept[key]
    if read.get("topic"):
        out["topic"] = read["topic"]
    if said is None and read.get("klass"):
        out["klass"] = read["klass"]                    # only a hint for where to look: the brief's own class always wins
    if out["topic"].lower() != typed.lower() or out["klass"] != said:
        log(f"[library] the topic is read as “{out['topic']}”" + (f", class {out['klass']} (not said in the request)"
                                                                 if out["klass"] != said else ""))
    return out


def about(text: str, topic: str, title: str = "") -> bool:
    """Whether a source is ABOUT the topic: its title or its words carry the topic's own words.

    Two of them when the topic has two or more that say something; all of its one word
    otherwise. Scoring a transcript against the whole request let a Python tutorial in on
    "understand", "example" and "think".
    """
    wanted = set(tokens(topic)) - _GENERIC
    if not wanted:
        return True
    there = set(tokens(title)) | set(tokens(text))
    # "Pythagorean" is "Pythagoras" said another way: a long word is found when its first six letters are.
    stems = {word[:6] for word in there if len(word) >= 6}
    found = {word for word in wanted if word in there or (len(word) >= 7 and word[:6] in stems)}
    return len(found) >= min(2, len(wanted))


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(text).lower()).strip("-")[:60] or "topic"


def pack_folder(brief: dict) -> Path:
    """Where a topic's pack and its card are kept: one folder per topic and class, whatever the language."""
    return root("packs", slug(f"{str(brief.get('topic') or '').strip()}-class-{school_class(brief) or 'x'}"))


def build_pack(brief: dict, log=print, refresh: bool = False, lectures: int = 3) -> dict:
    """Gather the sources for a brief's topic into numbered, citable passages.

    Cached per topic and class under ``library/packs/`` — a second lesson on the same
    topic reads nothing from the network. Returns the pack even when it is empty.
    """
    subject = school_subject(brief)
    saved = pack_folder(brief) / "pack.json"
    if saved.is_file() and not refresh:
        try:
            pack = json.loads(saved.read_text(encoding="utf-8"))
            log(f"[library] pack from the library: {len(pack['sources'])} source(s), {len(pack['chunks'])} passages")
            return pack
        except (ValueError, KeyError):
            pass
    read = read_topic(brief, log=log)                       # spelling put right, and a class to look in when none was said
    topic, klass = read["topic"], read["klass"]
    query = " ".join([topic] + [str(brief.get(k) or "") for k in ("goal", "misconception")]).strip()
    docs, warnings = [], []

    def add(kind: str, title: str, url: str, text: str, note: str = "") -> None:
        text = clean(text)
        if text and len(text.split()) >= 40:
            docs.append({"kind": kind, "title": title, "url": url, "text": text, "note": note})

    for given in brief.get("sources") or []:      # what the requester handed in comes first
        given = str(given).strip()
        video = _YT_ID.search(given)
        if video:
            heard = transcript(video.group(1))
            add("lecture", f"YouTube {video.group(1)}", given, heard["text"], "given by the requester")
            if not heard["text"]:
                warnings.append(f"no captions for {given}")
        elif given.startswith(("http://", "https://")):
            try:
                import requests  # noqa: PLC0415
                html = requests.get(given, headers={"User-Agent": UA}, timeout=HTTP_TIMEOUT).text
                body = re.sub(r"<[^>]+>", " ", re.sub(r"(?is)<(script|style|nav|footer|header)[^>]*>.*?</\1>", " ", html))
                add("web", given, given, re.sub(r"\s+", " ", body), "given by the requester")
            except Exception as exc:  # noqa: BLE001
                warnings.append(f"could not read {given} ({type(exc).__name__})")
        elif given:
            add("given", "The requester's notes", "", given)

    if klass:
        chapters = find_chapter(f"{topic} {topic} {query}", klass, subject, log=log)
        for chapter in chapters:
            add("textbook", f"NCERT {chapter['book']['book']}, chapter {chapter['chapter']}: {chapter['title']}",
                f"{NCERT_PDF}/{chapter['book']['code']}{chapter['chapter']:02d}.pdf", chapter["text"])
        if not chapters:
            warnings.append(f"no NCERT chapter found for class {klass}")
    else:
        warnings.append("no school class in the brief, so no textbook was looked for")

    for video in find_lectures(topic, klass, brief.get("language", "en-IN"), count=lectures, log=log, query=f"{topic} {topic} {query}"):
        spoken = "Hindi" if str(video.get("language", "")).startswith("hi") else "English"
        add("lecture", f"{video['channel']}: {video['title']}", f"https://www.youtube.com/watch?v={video['id']}", video["text"],
            f"{spoken} lecture, {video['seconds'] // 60} min" + (", automatic captions" if video.get("generated") else ""))

    if subject != "science":
        plan = find_lesson_plan(topic, log=log)
        if plan:
            add("lesson_plan", f"Mathematics Assessment Project: {plan['title']}", plan["url"], plan["text"])
        named = eedi_misconceptions(query)
        if named:
            add("misconceptions", "Eedi: named misconceptions near this topic", "https://www.kaggle.com/competitions/eedi-mining-misconceptions-in-mathematics",
                "\n\n".join(f"Misconception: {n}." for n in named) + "\n\n" + " ".join(["(a list of named learner mistakes)"] * 10))

    sources, chunks = [], []
    for n, doc in enumerate(docs, 1):
        sid = f"S{n}"
        kept = _trim(doc["text"], query)
        sources.append({"id": sid, "kind": doc["kind"], "title": doc["title"], "url": doc["url"], "note": doc["note"],
                        "licence": LICENCE.get(doc["kind"], ""), "words": sum(len(p.split()) for p in kept),
                        "of_words": len(doc["text"].split())})
        chunks += [{"id": f"{sid}#{i}", "source": sid, "text": part} for i, part in enumerate(kept, 1)]
    digest = hashlib.sha256("\x00".join(c["text"] for c in chunks).encode("utf-8")).hexdigest()[:16]
    pack = {"topic": topic, "asked": read["asked"], "klass": klass, "subject": subject, "query": query,
            "built": time.strftime("%Y-%m-%d %H:%M"),
            "sources": sources, "chunks": chunks, "warnings": warnings, "digest": digest}
    saved.write_text(json.dumps(pack, indent=1, ensure_ascii=False), encoding="utf-8")
    log(f"[library] pack: {len(sources)} source(s), {len(chunks)} passages, {sum(s['words'] for s in sources)} words"
        + (f"; {len(warnings)} warning(s)" if warnings else ""))
    return pack


def pack_text(pack: dict) -> str:
    """The pack as the model reads it: a list of sources, then every passage under its id."""
    head = ["SOURCES:"] + [f"  {s['id']} [{s['kind']}] {s['title']}" + (f" ({s['note']})" if s.get("note") else "")
                           + f"\n      {s['licence']}" for s in pack["sources"]]
    return "\n".join(head) + "\n\nPASSAGES:\n" + "\n\n".join(f"[{c['id']}] {c['text']}" for c in pack["chunks"])


# ── how each source teaches it ───────────────────────────────────────────────
# The passages say WHAT a source says. They do not say how it is built: which phase comes first, what each
# phase is for, what the learner is made to do, how the teacher talks. A reader that reverse-engineers the
# lesson plan behind each source gives the card maker that, in one vocabulary for every source, so three
# sources can be laid side by side. The form is the owner's (a reverse-engineering prompt for lesson plans,
# 2026-10-09): measurable objectives with Bloom's levels, an essential question, the flow as phases with an
# instructional role, the type and purpose of the examples, the scaffolding, the misconceptions, and what the
# source leaves out. Roles are Gagné's events, Merrill's principles and the 5E phases folded into six.

ROLES = ("motivation", "activation", "demonstration", "application", "integration", "assessment")
BLOOM = ("remember", "understand", "apply", "analyze", "evaluate", "create")
BLUEPRINT_VERSION = 2            # 2: "pictures", what the source shows while it teaches
BLUEPRINT_MODELS_DEFAULT = "google/gemini-3.5-flash-lite,google/gemini-2.5-flash,openai/gpt-5.4-nano"
COPIED_RUN = 9                 # this many words in a row taken from the source is copying, not describing

BLUEPRINT_SYSTEM = """You reverse-engineer the lesson plan behind ONE teaching source: a textbook chapter, the
transcript of a lecture, or a lesson plan. You are NOT summarising it. You write the blueprint an instructional designer
would have handed its author BEFORE it was made: what it aims at, in what order it teaches, and why it is built that way.

You are given the source as numbered passages in the source's own order. A lecture's text is automatic captions: no
punctuation and some misheard words; read through that. Return ONLY JSON:
{"audience": "who it is for, inferred from its language and from what it assumes",
 "prior": ["what it assumes the learner already knows"],
 "objectives": [{"can": "what the learner can DO afterwards, starting with a verb", "level": "remember|understand|apply|analyze|evaluate|create"}],
 "essential_question": "the open question that drives it (never a closed 'what is X?'), or empty",
 "flow": [{"phase": "a short name", "role": "motivation|activation|demonstration|application|integration|assessment",
           "how": "one or two sentences: what this phase is for and how it goes about it", "at": ["S2#1"]}],
 "examples": "the TYPE and progression of its examples and what each is for, never their content",
 "pictures": ["what is SHOWN or drawn while it teaches, in the order it appears: each diagram, demonstration, object or
              worked figure, with what it is used to show. A lecture's captions say it: 'look at this', 'here we draw', 'take a'"],
 "scaffolding": "how difficulty is built up",
 "misconceptions": ["pitfalls it anticipates, said as a learner would hold them"],
 "leaves_out": ["what it visibly chooses not to do: states a result without proof, keeps to whole numbers, ..."],
 "manner": ["for a LECTURE only: how this teacher talks, described and never quoted: how they open, how they ask, how they
             move from one thing to the next, what they do after asking. Empty for every other kind of source"]}

Rules:
- The flow follows the source's order, three to eight phases, each citing the passages it covers.
- Roles. motivation: a hook, a real situation, a stated goal. activation: recalling what is already known.
  demonstration: the content itself (definitions, the idea, a derivation). application: worked examples and practice
  with feedback. integration: links to the real world or to other topics, and the limits of the idea. assessment:
  questions or exercises left to the learner. One role for a phase: its main one.
- Levels (Bloom, revised). remember: name, state, list. understand: explain, describe, compare. apply: calculate,
  solve, use, predict. analyze: distinguish, relate. evaluate: justify, judge. create: design, derive. Tag an objective
  by the highest thing the source actually makes the learner do.
- Be specific. Not "includes some examples" but "three worked examples of rising difficulty: a direct one, one that
  needs rearranging, one word problem where the learner must pick the formula".
- Write in English and in your own words. Copy no sentence of the source. Add nothing the source does not contain;
  do not judge it or improve it."""


def blueprint_models() -> list[str]:
    raw = knobs.get("HARNESS_BLUEPRINT_MODELS", BLUEPRINT_MODELS_DEFAULT)
    return [m.strip() for m in raw.split(",") if m.strip()]


def blueprint_llm():
    """A small, fast model through OpenRouter, metered as "blueprint". None without a key."""
    key = (os.getenv("OPENROUTER_API_KEY") or "").strip()
    if not key:
        return None
    from ..engine import llm as engine_llm  # noqa: PLC0415

    def call(prompt: str, system: str):
        text = engine_llm.call_openrouter(key, prompt, system, temperature=0.0, models=blueprint_models(),
                                          max_tokens=None, json_object=True, note="blueprint", timeout=120.0)
        return engine_llm.loads_json_lenient(text)
    return call


def _copied(line: str, source_words: list[str]) -> bool:
    words = tokens_all(line)
    if len(words) < COPIED_RUN:
        return False
    text = " " + " ".join(source_words) + " "
    return any(" " + " ".join(words[i:i + COPIED_RUN]) + " " in text for i in range(len(words) - COPIED_RUN + 1))


def tokens_all(text: str) -> list[str]:
    """Every word, in order, lower-cased (``tokens`` drops the common ones; copying is measured on all of them)."""
    return _WORD.findall(str(text).lower())


def shape_blueprint(raw, ids: list[str], text: str, kind: str = "") -> dict | None:
    """A reader's answer as a blueprint, or None when it has no usable flow.

    Code decides what a model may not: a role or a level outside the closed lists is
    dropped with its line, a cited passage that does not exist is removed, the phases
    are put back in the source's order, and any line that carries ``COPIED_RUN`` words in a
    row from the source is dropped (the sources may be read and described, never copied).
    """
    if not isinstance(raw, dict):
        return None
    source_words, known = tokens_all(text), {i: n for n, i in enumerate(ids)}

    def line(value, limit=260) -> str:
        value = re.sub(r"\s+", " ", str(value or "")).strip()
        if len(value) > limit:                      # cut at a word, and say that it was cut
            value = value[:limit].rsplit(" ", 1)[0].rstrip(",;:") + " …"
        return "" if _copied(value, source_words) else value

    def lines(value, limit=6, each=200) -> list[str]:
        return [x for x in (line(v, each) for v in (value if isinstance(value, list) else [])) if x][:limit]

    flow = []
    for step in raw.get("flow") if isinstance(raw.get("flow"), list) else []:
        if not isinstance(step, dict) or str(step.get("role") or "").strip().lower() not in ROLES:
            continue
        how, phase = line(step.get("how"), 320), line(step.get("phase"), 60)
        if not how:
            continue
        at = [str(i).strip() for i in (step.get("at") if isinstance(step.get("at"), list) else []) if str(i).strip() in known]
        flow.append({"phase": phase or step["role"], "role": str(step["role"]).strip().lower(), "how": how, "at": at[:6]})
    if len(flow) < 2:
        return None
    # the source's own order: a phase with no passage keeps its place after the one before it
    place, last = [], -1
    for step in flow:
        last = min((known[i] for i in step["at"]), default=last)
        place.append(last)
    flow = [step for _, _, step in sorted(zip(place, range(len(flow)), flow))][:8]
    objectives = [{"can": line(o.get("can"), 160), "level": str(o.get("level") or "").strip().lower()}
                  for o in (raw.get("objectives") if isinstance(raw.get("objectives"), list) else []) if isinstance(o, dict)]
    return {"audience": line(raw.get("audience"), 160), "prior": lines(raw.get("prior"), 5, 120),
            "objectives": [o for o in objectives if o["can"] and o["level"] in BLOOM][:5],
            "essential_question": line(raw.get("essential_question"), 200), "flow": flow,
            "examples": line(raw.get("examples"), 320), "pictures": lines(raw.get("pictures"), 8, 220),
            "scaffolding": line(raw.get("scaffolding"), 260),
            "misconceptions": lines(raw.get("misconceptions"), 5), "leaves_out": lines(raw.get("leaves_out"), 5),
            "manner": lines(raw.get("manner"), 6) if kind == "lecture" else []}


def blueprints(pack: dict, folder: Path, llm=None, log=print, refresh: bool = False) -> dict:
    """{source id: blueprint} for a pack's textbook, lecture and lesson-plan sources. Cached beside the pack.

    One small call per source, made once: the file is keyed by the pack's digest and
    ``BLUEPRINT_VERSION``. A source whose reading fails or is refused simply has no
    blueprint; the card is then made from the passages alone, as before.
    """
    Path(folder).mkdir(parents=True, exist_ok=True)
    saved = Path(folder) / "blueprints.json"
    if saved.is_file() and not refresh:
        try:
            kept = json.loads(saved.read_text(encoding="utf-8"))
            if kept.get("digest") == pack.get("digest") and kept.get("version") == BLUEPRINT_VERSION:
                return kept.get("plans") or {}
        except ValueError:
            pass
    llm = llm or blueprint_llm()
    if llm is None or not pack.get("chunks"):
        return {}
    plans = {}
    for source in pack.get("sources") or []:
        if source.get("kind") not in ("textbook", "lecture", "lesson_plan", "web", "given"):
            continue
        parts = [c for c in pack["chunks"] if c.get("source") == source["id"]]
        if sum(len(c["text"].split()) for c in parts) < 150:
            continue
        text = "\n\n".join(f"[{c['id']}] {c['text']}" for c in parts)
        try:
            raw = llm(f"SOURCE {source['id']} [{source['kind']}] {source['title']}"
                      + (f" ({source['note']})" if source.get("note") else "") + f"\n\nPASSAGES IN ORDER:\n{text}", BLUEPRINT_SYSTEM)
        except Exception as exc:  # noqa: BLE001 - a blueprint is an improvement, never a requirement
            log(f"[library] no blueprint for {source['id']}: {type(exc).__name__}: {str(exc)[:100]}")
            continue
        plan = shape_blueprint(raw, [c["id"] for c in parts], " ".join(c["text"] for c in parts), source.get("kind", ""))
        if plan:
            plans[source["id"]] = plan
        else:
            log(f"[library] the blueprint for {source['id']} had no usable flow: not used")
    if plans:
        log("[library] how each source teaches it: " + "; ".join(
            f"{sid} " + " → ".join(step["role"] for step in plan["flow"]) for sid, plan in plans.items()))
        try:
            saved.write_text(json.dumps({"digest": pack.get("digest"), "version": BLUEPRINT_VERSION, "plans": plans},
                                        indent=1, ensure_ascii=False), encoding="utf-8")
        except OSError:
            pass
    return plans


def blueprint_text(plans: dict, pack: dict) -> str:
    """The blueprints as the card maker reads them. '' when there are none."""
    if not plans:
        return ""
    titles = {s["id"]: s for s in pack.get("sources") or []}
    out = ["HOW EACH SOURCE TEACHES IT (its lesson plan, worked out from the source; the six roles are the same for all):"]
    for sid, plan in plans.items():
        source = titles.get(sid, {})
        out.append(f"\n{sid} [{source.get('kind', '')}] {source.get('title', '')}" + (f" — for {plan['audience']}" if plan["audience"] else ""))
        if plan["objectives"]:
            out.append("  aims: " + "; ".join(f"{o['can']} ({o['level']})" for o in plan["objectives"]))
        if plan["essential_question"]:
            out.append(f"  driving question: {plan['essential_question']}")
        out += [f"  {n}. [{step['role']}] {step['phase']}: {step['how']}" + (f" ({', '.join(step['at'])})" if step["at"] else "")
                for n, step in enumerate(plan["flow"], 1)]
        for label, key in (("examples", "examples"), ("builds up by", "scaffolding")):
            if plan[key]:
                out.append(f"  {label}: {plan[key]}")
        for label, key in (("shows", "pictures"), ("anticipates", "misconceptions"), ("leaves out", "leaves_out"),
                           ("how the teacher talks", "manner")):
            if plan.get(key):
                out.append(f"  {label}: " + "; ".join(plan[key]))
    return "\n".join(out)


def roles_missing(plans: dict) -> dict:
    """{role: how many of the sources have it}: what every source does is probably the topic's own."""
    return {role: sum(1 for plan in plans.values() if any(step["role"] == role for step in plan["flow"])) for role in ROLES}


# ── reference lessons for a pasted script ────────────────────────────────────
# The owner, 2026-10-09: "try to fetch reference videos for the script also. This is just for fine-tuning the given
# narration for visuals. We won't improve the audio voiceover but we'll improve the visuals with that." A pasted
# script's WORDS are its author's and stay as they are; what a model designs is the screen, and until now it
# designed it from the words alone. Two or three lectures on the same topic say what teachers SHOW for it.

SCRIPT_TOPIC_SYSTEM = """You are given the opening of the script of a narrated school lesson. Say what school topic it teaches,
as an Indian school textbook's index would print it, in English, and the class (1 to 12) in which NCERT textbooks teach
it. Return ONLY JSON: {"topic": "…", "class": 8}   (class null when it is not a school topic)"""


def reference_for_script(script: str, language: str = "hinglish", llm=None, reader=None, log=print, lectures: int = 2) -> dict:
    """What reference lessons SHOW for a pasted script's topic: ``{"topic", "klass", "sources", "notes"}``.

    ``notes`` is a short text for whoever designs the screen (never for rewriting the
    words): per lecture, what is drawn or demonstrated and in what order, how its examples
    progress and which mistakes it expects. One small call names the script's topic, the
    lectures are found and read as for a lesson made from a topic (free), and one small
    call per lecture works out its plan. Kept by the script's own text under
    ``library/scripts/``, so making the lesson again asks nobody. ``HARNESS_SCRIPT_REFERENCES=0``
    switches it off. An empty ``notes`` means: design the screen from the words, as before.
    """
    text = re.sub(r"\s+", " ", str(script or "")).strip()
    out = {"topic": "", "klass": None, "sources": [], "notes": ""}
    if len(text.split()) < 40 or knobs.get("HARNESS_SCRIPT_REFERENCES", "1") != "1":
        return out
    saved = root("scripts") / (hashlib.sha256(text.encode("utf-8")).hexdigest()[:20] + ".json")
    if saved.is_file():
        try:
            return json.loads(saved.read_text(encoding="utf-8"))
        except ValueError:
            pass
    llm = llm or topic_llm()
    if llm is None:
        return out
    try:
        answer = llm("THE SCRIPT OPENS:\n" + " ".join(text.split()[:260]), SCRIPT_TOPIC_SYSTEM)
    except Exception as exc:  # noqa: BLE001 - references are an improvement, never a requirement
        log(f"[library] the script's topic was not named ({type(exc).__name__}): no reference lessons")
        return out
    topic = re.sub(r"\s+", " ", str((answer or {}).get("topic") or "")).strip()[:120] if isinstance(answer, dict) else ""
    guess = answer.get("class") if isinstance(answer, dict) else None
    klass = int(guess) if isinstance(guess, (int, float)) and 1 <= int(guess) <= 12 else None
    if len(topic) < 3:
        return out
    out.update(topic=topic, klass=klass)
    found = find_lectures(topic, klass, language, count=lectures, log=log, query=topic)
    sources, chunks = [], []
    for n, video in enumerate(found, 1):
        sid = f"R{n}"
        spoken = "Hindi" if str(video.get("language", "")).startswith("hi") else "English"
        sources.append({"id": sid, "kind": "lecture", "title": f"{video['channel']}: {video['title']}"[:140],
                        "url": f"https://www.youtube.com/watch?v={video['id']}", "note": f"{spoken} lecture, {video['seconds'] // 60} min"})
        chunks += [{"id": f"{sid}#{i}", "source": sid, "text": part} for i, part in enumerate(_trim(clean(video["text"]), topic), 1)]
    if sources:
        pack = {"topic": topic, "klass": klass, "sources": sources, "chunks": chunks,
                "digest": hashlib.sha256("\x00".join(c["text"] for c in chunks).encode("utf-8")).hexdigest()[:16]}
        plans = blueprints(pack, saved.parent / (saved.stem + "_plans"), llm=reader, log=log) if chunks else {}
        lines = [f"HOW REFERENCE LESSONS SHOW THIS TOPIC ({topic}; from {len(sources)} lecture(s)). Use it to choose and design the "
                 "PICTURES only: the script's words are its author's and are not changed."]
        for source in sources:
            plan = plans.get(source["id"])
            if not plan:
                continue
            lines.append(f"- {source['title']} ({source['note']})")
            if plan.get("pictures"):
                lines.append("    shows, in order: " + "; ".join(plan["pictures"]))
            if plan.get("examples"):
                lines.append("    its examples: " + plan["examples"])
            if plan.get("misconceptions"):
                lines.append("    expects these mistakes: " + "; ".join(plan["misconceptions"]))
        out.update(sources=sources, notes="\n".join(lines)[:2400] if len(lines) > 1 else "")
    log(f"[library] reference lessons for the script (“{topic}”): " + ("; ".join(s_["title"][:50] for s_ in sources) or "none found")
        + ("" if out["notes"] else " (nothing usable about what they show)"))
    try:
        saved.write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass
    return out


# ── the topic graph ──────────────────────────────────────────────────────────

def graph_add(pack: dict, card: dict | None = None) -> dict:
    """Record a topic, its sources, its mistakes and what it needs first in ``graph.json``.

    Node-link JSON (networkx reads it with ``node_link_graph``). Nodes: ``topic:…``,
    ``source:…`` (by URL, so two topics that used the same chapter meet at it),
    ``mistake:…``. Edges: has_source, goes_wrong, needs_first. Grown one lesson at a time.
    """
    path = root() / "graph.json"
    try:
        graph = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
    except ValueError:
        graph = {}
    nodes = {n["id"]: n for n in graph.get("nodes", [])}
    links = {(e["source"], e["target"], e["kind"]) for e in graph.get("links", [])}
    topic = f"topic:{slug(pack['topic'])}"
    nodes[topic] = {"id": topic, "kind": "topic", "label": pack["topic"], "klass": pack.get("klass"), "subject": pack.get("subject")}
    for source in pack["sources"]:
        sid = "source:" + (source["url"] or slug(source["title"]))
        nodes[sid] = {"id": sid, "kind": source["kind"], "label": source["title"], "url": source["url"]}
        links.add((topic, sid, "has_source"))
    for item in ((card or {}).get("mistakes") or []):
        text = str(item.get("mistake") or "").strip()
        if text:
            mid = f"mistake:{slug(text)}"
            nodes[mid] = {"id": mid, "kind": "mistake", "label": text}
            links.add((topic, mid, "goes_wrong"))
    for item in ((card or {}).get("needs_first") or []):
        text = str(item.get("text") if isinstance(item, dict) else item or "").strip()
        if text:
            before = f"topic:{slug(text)}"
            nodes.setdefault(before, {"id": before, "kind": "topic", "label": text, "stub": True})
            links.add((topic, before, "needs_first"))
    graph = {"directed": True, "multigraph": False, "graph": {}, "nodes": list(nodes.values()),
             "links": [{"source": s, "target": t, "kind": k} for s, t, k in sorted(links)]}
    path.write_text(json.dumps(graph, indent=1, ensure_ascii=False), encoding="utf-8")
    return graph
