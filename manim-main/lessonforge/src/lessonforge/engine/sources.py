"""Source intake — the NotebookLM-shaped front door of the video pipeline.

Until now the video engine could only be *given* grounding text: `ce/` resolved a
YouTube transcript or NCERT chunk and passed it in `context["grounding_chunks"]`, and
anything that called the lab directly (Studio, /bulk, curl) generated a storyboard
from the topic string alone. A model asked to explain a topic it was never shown
writes the average of everything it has read about it — which is exactly the
"thin, generic video" symptom.

This module lets the engine gather its own sources, from whatever the user actually
has: a YouTube link, a web page, pasted notes, or a search query. What comes back is
a `ResearchPack` — chunked, **numbered, and citable** — so every later stage can be
asked to ground a claim in `[S2#1]` rather than invent one.

House rules encoded here:

* **Every tier degrades, none raises.** A dead link, a missing key, a video with
  transcripts disabled: the source is dropped with a warning and the pack is built
  from what remains. An empty pack is legal — it is the current behaviour.
* **The pack is content-addressed** (`ResearchPack.digest`). It joins the storyboard
  cache key upstream, so re-running with the same sources costs nothing and editing a
  source regenerates automatically — the same freshness signal `grounding_chunks`
  already uses.
* **No new hard dependency.** `requests` is already required; `youtube_transcript_api`
  and a search key are optional and each tier checks for its own imports.
"""
from __future__ import annotations

import hashlib
import logging
import os
import re
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Per-source cap. A 20-minute transcript is ~3000 words; several of those would
# crowd out the actual instructions in the prompt, and the tail of a transcript is
# rarely where the definition lives.
MAX_CHARS_PER_SOURCE = int(os.getenv("SOURCE_MAX_CHARS", "12000"))
MAX_SOURCES = int(os.getenv("SOURCE_MAX_COUNT", "6"))
CHUNK_CHARS = int(os.getenv("SOURCE_CHUNK_CHARS", "1100"))
HTTP_TIMEOUT = float(os.getenv("SOURCE_HTTP_TIMEOUT", "20"))

_YT_ID = re.compile(
    r"(?:youtube\.com/(?:watch\?(?:.*&)?v=|embed/|shorts/|live/)|youtu\.be/)([A-Za-z0-9_-]{11})"
)


@dataclass
class Source:
    """One ingested document, chunked for citation."""

    id: str                       # "S1" — the citation handle
    kind: str                     # youtube | web | text | search
    title: str = ""
    url: str = ""
    text: str = ""
    chunks: list = field(default_factory=list)   # list[str]
    error: str = ""               # set when the tier degraded; kept for the UI

    def cite(self, i):
        return f"[{self.id}#{i + 1}]"


@dataclass
class ResearchPack:
    """Everything the planning stages read, plus the provenance to cite it."""

    sources: list = field(default_factory=list)   # list[Source]
    warnings: list = field(default_factory=list)  # human-readable degradations

    @property
    def ok(self):
        return any(s.chunks for s in self.sources)

    @property
    def digest(self):
        """Content hash — the cache-freshness signal for everything downstream."""
        if not self.ok:
            return ""
        h = hashlib.sha256()
        for s in self.sources:
            h.update(s.id.encode())
            h.update((s.url or s.title).encode())
            for c in s.chunks:
                h.update(c.encode("utf-8", "ignore"))
        return h.hexdigest()[:16]

    def as_prompt(self, char_budget=None):
        """Render the pack as numbered, citable prompt text.

        Sources are interleaved round-robin rather than concatenated, so a budget cut
        truncates the *tail of every source* instead of deleting the last source
        outright — with one long transcript and three short notes, plain concatenation
        silently drops the notes.
        """
        budget = int(char_budget or os.getenv("RESEARCH_PACK_CHARS", "20000"))
        live = [s for s in self.sources if s.chunks]
        if not live:
            return ""
        header_lines = [
            "## SOURCE MATERIAL (the only place facts may come from)",
            "Each block is tagged [Sn#k]. Cite the tag you took a fact from.",
            "",
        ]
        head = "\n".join(header_lines)
        blocks, spent, idx = [], len(head), 0
        while spent < budget:
            progressed = False
            for order, s in enumerate(live):
                if idx >= len(s.chunks):
                    continue
                progressed = True
                block = f"{s.cite(idx)} ({s.kind}: {s.title or s.url or 'note'})\n{s.chunks[idx]}"
                if spent + len(block) > budget:
                    continue
                blocks.append((order, idx, block))
                spent += len(block) + 2
            if not progressed:
                break
            idx += 1
        blocks.sort()                       # restore reading order within each source
        return head + "\n\n".join(b[2] for b in blocks)

    def manifest(self):
        """Compact provenance for the API response / sidecar."""
        return {
            "digest": self.digest,
            "warnings": list(self.warnings),
            "sources": [
                {"id": s.id, "kind": s.kind, "title": s.title, "url": s.url,
                 "chunks": len(s.chunks), "chars": len(s.text), "error": s.error}
                for s in self.sources
            ],
        }


# ── chunking ──────────────────────────────────────────────────────────────────

def _chunk(text, size=None):
    """Split on paragraph/sentence boundaries, never mid-word."""
    size = size or CHUNK_CHARS
    text = re.sub(r"[ \t]+", " ", (text or "")).strip()
    if not text:
        return []
    parts, buf = [], ""
    for para in re.split(r"\n{2,}|(?<=[.!?])\s+(?=[A-Z0-9])", text):
        para = para.strip()
        if not para:
            continue
        if len(buf) + len(para) + 1 > size and buf:
            parts.append(buf.strip())
            buf = ""
        if len(para) > size:                       # one runaway paragraph
            for i in range(0, len(para), size):
                parts.append(para[i:i + size].strip())
            continue
        buf += (" " if buf else "") + para
    if buf.strip():
        parts.append(buf.strip())
    return [p for p in parts if p]


# ── tier: YouTube ─────────────────────────────────────────────────────────────

def youtube_id(ref):
    """Extract a video id from any YouTube URL form, or None."""
    if not ref:
        return None
    ref = ref.strip()
    m = _YT_ID.search(ref)
    if m:
        return m.group(1)
    if re.fullmatch(r"[A-Za-z0-9_-]{11}", ref):
        return ref
    return None


def fetch_youtube_transcript(video_id, languages=("en", "hi", "en-IN", "hi-IN")):
    """Transcript text for a video id, or ('', reason). Never raises."""
    try:
        from youtube_transcript_api import YouTubeTranscriptApi  # noqa: PLC0415
    except ImportError:
        return "", "youtube_transcript_api not installed"
    try:
        api = YouTubeTranscriptApi()
        # The 1.x API is instance-based (`fetch`); 0.6.x was a classmethod (`get_transcript`).
        # Supporting both keeps this working across the versions found in the wild.
        if hasattr(api, "fetch"):
            fetched = api.fetch(video_id, languages=list(languages))
            snippets = getattr(fetched, "snippets", fetched)
            text = " ".join(getattr(sn, "text", "") or "" for sn in snippets)
        else:  # pragma: no cover - legacy client
            rows = YouTubeTranscriptApi.get_transcript(video_id, languages=list(languages))
            text = " ".join(r.get("text", "") for r in rows)
        text = re.sub(r"\[[^\]]{1,20}\]", " ", text)      # [Music], [Applause]
        return re.sub(r"\s+", " ", text).strip(), ""
    except Exception as e:
        return "", f"{type(e).__name__}: {e}"[:200]


# ── tier: web page ────────────────────────────────────────────────────────────

_TAG_STRIP = re.compile(r"<(script|style|nav|footer|header|form|aside)[^>]*>.*?</\1>",
                        re.I | re.S)
_TAGS = re.compile(r"<[^>]+>")


def html_to_text(html):
    """Readable text from HTML, dependency-free.

    bs4 is used when present (better at malformed markup); the regex path is the
    fallback so a missing optional dep degrades quality, never availability.
    """
    try:
        from bs4 import BeautifulSoup  # noqa: PLC0415
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header", "form", "aside"]):
            tag.decompose()
        text = soup.get_text("\n")
    except Exception:
        text = _TAGS.sub(" ", _TAG_STRIP.sub(" ", html or ""))
    text = re.sub(r"&nbsp;?", " ", text)
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text)
    return re.sub(r"[ \t]{2,}", " ", text).strip()


def fetch_web_page(url):
    """(text, title, error) for a URL. Never raises."""
    try:
        import requests  # noqa: PLC0415
        resp = requests.get(
            url, timeout=HTTP_TIMEOUT,
            headers={"User-Agent": "Mozilla/5.0 (compatible; GyanSetuBot/1.0)"},
        )
        resp.raise_for_status()
        ctype = resp.headers.get("content-type", "")
        if "html" not in ctype and "text" not in ctype:
            return "", "", f"unsupported content-type {ctype!r}"
        html = resp.text
        title = ""
        m = re.search(r"<title[^>]*>(.*?)</title>", html, re.I | re.S)
        if m:
            title = re.sub(r"\s+", " ", _TAGS.sub("", m.group(1))).strip()[:120]
        return html_to_text(html), title, ""
    except Exception as e:
        return "", "", f"{type(e).__name__}: {e}"[:200]


# ── tier: web search ──────────────────────────────────────────────────────────

def search_web(query, max_results=3):
    """Search results as [{title, url, snippet}], or [] when no provider is configured.

    Deliberately provider-pluggable and deliberately optional: this repo meters every
    external edge, and a search key is not something the box is guaranteed to have.
    Supported by env key, in order: Tavily, Serper (Google), Brave.
    """
    try:
        import requests  # noqa: PLC0415
    except ImportError:                                  # pragma: no cover
        return []
    tavily = os.getenv("TAVILY_API_KEY", "").strip()
    serper = os.getenv("SERPER_API_KEY", "").strip()
    brave = os.getenv("BRAVE_API_KEY", "").strip()
    try:
        if tavily:
            r = requests.post("https://api.tavily.com/search", timeout=HTTP_TIMEOUT, json={
                "api_key": tavily, "query": query, "max_results": max_results,
                "include_answer": False,
            })
            r.raise_for_status()
            return [{"title": d.get("title", ""), "url": d.get("url", ""),
                     "snippet": d.get("content", "")}
                    for d in (r.json().get("results") or [])][:max_results]
        if serper:
            r = requests.post("https://google.serper.dev/search", timeout=HTTP_TIMEOUT,
                              headers={"X-API-KEY": serper}, json={"q": query})
            r.raise_for_status()
            return [{"title": d.get("title", ""), "url": d.get("link", ""),
                     "snippet": d.get("snippet", "")}
                    for d in (r.json().get("organic") or [])][:max_results]
        if brave:
            r = requests.get("https://api.search.brave.com/res/v1/web/search",
                             timeout=HTTP_TIMEOUT,
                             headers={"X-Subscription-Token": brave, "Accept": "application/json"},
                             params={"q": query, "count": max_results})
            r.raise_for_status()
            web = (r.json().get("web") or {}).get("results") or []
            return [{"title": d.get("title", ""), "url": d.get("url", ""),
                     "snippet": d.get("description", "")} for d in web][:max_results]
    except Exception as e:
        logger.warning("[SOURCES] web search failed: %s", e)
    return []


def search_youtube(query, max_results=2):
    """Top YouTube video ids for a query via the Data API, or [] without a key."""
    key = os.getenv("YOUTUBE_API_KEY", "").strip()
    if not key:
        return []
    try:
        import requests  # noqa: PLC0415
        r = requests.get("https://www.googleapis.com/youtube/v3/search",
                         timeout=HTTP_TIMEOUT,
                         params={"key": key, "q": query, "part": "id,snippet",
                                 "type": "video", "videoDuration": "medium",
                                 "maxResults": max_results})
        r.raise_for_status()
        return [{"id": it["id"]["videoId"], "title": it["snippet"].get("title", "")}
                for it in (r.json().get("items") or []) if it.get("id", {}).get("videoId")]
    except Exception as e:
        logger.warning("[SOURCES] youtube search failed: %s", e)
        return []


# ── the front door ────────────────────────────────────────────────────────────

def _normalize_refs(refs):
    """Accept the shapes a caller might plausibly send and yield dicts."""
    out = []
    for ref in (refs or []):
        if isinstance(ref, dict):
            out.append(dict(ref))
        elif isinstance(ref, str) and ref.strip():
            s = ref.strip()
            if youtube_id(s):
                out.append({"kind": "youtube", "url": s})
            elif s.startswith(("http://", "https://")):
                out.append({"kind": "web", "url": s})
            else:
                out.append({"kind": "text", "text": s})
    return out


def ingest(refs=None, topic="", auto_search=None, grade="", subject=""):
    """Build a `ResearchPack` from explicit references and (optionally) a search.

    `refs` items may be plain strings (auto-classified) or dicts:
        {"kind": "youtube"|"web"|"text", "url": ..., "text": ..., "title": ...}

    `auto_search` (default: env `SOURCE_AUTO_SEARCH`, off) adds a web + YouTube
    search for `topic` when the caller supplied no usable sources of its own.
    """
    if auto_search is None:
        auto_search = os.getenv("SOURCE_AUTO_SEARCH", "0").strip() == "1"

    pack = ResearchPack()
    items = _normalize_refs(refs)[:MAX_SOURCES]

    for i, ref in enumerate(items):
        sid = f"S{len(pack.sources) + 1}"
        kind = (ref.get("kind") or "").lower()
        url = (ref.get("url") or "").strip()
        if not kind:
            kind = "youtube" if youtube_id(url) else ("web" if url else "text")

        if kind == "youtube":
            vid = youtube_id(url) or youtube_id(ref.get("id", ""))
            if not vid:
                pack.warnings.append(f"{url or ref!r}: not a YouTube URL")
                continue
            text, err = fetch_youtube_transcript(vid)
            title = ref.get("title") or f"YouTube {vid}"
            if not text:
                pack.warnings.append(f"{title}: transcript unavailable ({err})")
                pack.sources.append(Source(id=sid, kind="youtube", title=title,
                                           url=url or f"https://youtu.be/{vid}", error=err))
                continue
            pack.sources.append(_mk(sid, "youtube", title, url or f"https://youtu.be/{vid}", text))
        elif kind == "web":
            text, title, err = fetch_web_page(url)
            title = ref.get("title") or title or url
            if not text:
                pack.warnings.append(f"{url}: not readable ({err})")
                pack.sources.append(Source(id=sid, kind="web", title=title, url=url, error=err))
                continue
            pack.sources.append(_mk(sid, "web", title, url, text))
        else:
            text = (ref.get("text") or "").strip()
            if not text:
                continue
            pack.sources.append(_mk(sid, "text", ref.get("title") or "Pasted notes", "", text))

    if auto_search and not pack.ok and topic:
        query = " ".join(x for x in [topic, subject, f"class {grade}" if grade else ""] if x)
        for hit in search_web(f"{query} explained"):
            if not hit.get("url"):
                continue
            sid = f"S{len(pack.sources) + 1}"
            text, title, err = fetch_web_page(hit["url"])
            if not text:
                # The snippet alone is still a (small) grounded source.
                text = hit.get("snippet", "")
            if text:
                pack.sources.append(_mk(sid, "search", hit.get("title") or title, hit["url"], text))
            if len(pack.sources) >= MAX_SOURCES:
                break
        for vid in search_youtube(f"{query} explained"):
            if len(pack.sources) >= MAX_SOURCES:
                break
            text, err = fetch_youtube_transcript(vid["id"])
            if text:
                pack.sources.append(_mk(f"S{len(pack.sources) + 1}", "youtube", vid["title"],
                                        f"https://youtu.be/{vid['id']}", text))

    live = sum(1 for s in pack.sources if s.chunks)
    logger.info("[SOURCES] %d/%d source(s) usable, %d chunk(s), digest=%s",
                live, len(pack.sources), sum(len(s.chunks) for s in pack.sources),
                pack.digest or "-")
    for w in pack.warnings:
        logger.warning("[SOURCES] %s", w)
    return pack


def _mk(sid, kind, title, url, text):
    text = (text or "")[:MAX_CHARS_PER_SOURCE]
    return Source(id=sid, kind=kind, title=(title or "")[:120], url=url,
                  text=text, chunks=_chunk(text))


def pack_from_chunks(chunks, source_label="content_store"):
    """Wrap pre-resolved `grounding_chunks` as a pack, so callers that already did
    their own resolution (``ce/``) flow through the same citable machinery."""
    pack = ResearchPack()
    for i, chunk in enumerate(chunks or []):
        if not (chunk or "").strip():
            continue
        pack.sources.append(_mk(f"S{i + 1}", "text", source_label, "", chunk))
    return pack
