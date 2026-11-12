"""Story-flow measures for a spoken explanation: does each sentence follow from the last? Pure Python, no model.

Used two ways: to score a lesson's narration against the range good YouTube explainers fall in, and (in lessonforge) to
point at the exact sentences that jump. Optional sentence embeddings add a second, meaning-based view of each seam.
"""
from __future__ import annotations
import re, statistics as st
from collections import Counter

STOP = set("""a about above after again against all also am an and any are aren't as at be because been before being below
between both but by can can't cannot could couldn't did didn't do does doesn't doing don't down during each few for from further
get gets got had hadn't has hasn't have haven't having he he'd he'll he's her here here's hers herself him himself his how how's i
i'd i'll i'm i've if in into is isn't it it's its itself just let's like me more most mustn't my myself no nor not now of off on once
only or other ought our ours ourselves out over own really right same say says said see she she'd she'll she's should shouldn't so
some such than that that's the their theirs them themselves then there there's these they they'd they'll they're they've this those
through to too under until up us very was wasn't we we'd we'll we're we've were weren't what what's when when's where where's which
while who who's whom why why's will with won't would wouldn't you you'd you'll you're you've your yours yourself yourselves
going go goes went gonna want wants one two three thing things way ways lot kind just actually okay yeah oh well also even still
make makes made take takes look looks looking think know need mean means bit little much many every something anything
here's thats dont doesnt isnt youre weve lets""".split())
LINK = ("so", "but", "and", "now", "then", "this", "that", "these", "those", "it", "its", "it's", "they", "which", "because",
        "here", "same", "notice", "remember", "again", "instead", "also", "next", "finally", "if", "when", "in", "or", "that's",
        "thus", "therefore", "hence", "yet", "otherwise", "similarly", "likewise", "both", "each", "another", "other", "such",
        "there", "still", "even", "after", "before", "once", "since", "only", "what", "why", "how", "where", "who", "look",
        "let's", "okay", "well", "right", "first", "second", "third", "last", "for", "as", "with", "our", "we", "you", "he", "she",
        "his", "her", "their", "him", "them", "imagine", "suppose", "say", "take")
# the words a listener hears as "this follows from that"; a sentence that has none and shares no word with the last two is a jump
BACKREF = {"this", "that", "these", "those", "it", "its", "it's", "they", "them", "their", "which", "such", "same", "there",
           "here", "both", "each", "another", "other", "again", "instead", "also", "then", "so", "but", "because", "therefore",
           "thus", "hence", "yet", "similarly", "likewise", "that's", "remember", "notice", "otherwise", "still", "now", "next"}
CONNECT = {"cause": r"\b(because|so that|so|therefore|that's why|which means|this means|that means|since|hence|thus|as a result)\b",
           "contrast": r"\b(but|however|yet|instead|although|though|whereas|on the other hand)\b",
           "sequence": r"\b(first|then|next|now|finally|after that|second|third)\b",
           "example": r"\b(for example|for instance|imagine|suppose|let's say|say you|picture|think of|like this)\b",
           "recap": r"\b(remember|so far|in other words|that is|recall|we saw|we found|we've seen)\b"}
WORD = re.compile(r"[a-z][a-z'\-]*")

def stem(w: str) -> str:
    w = w.strip("'-")
    for suf in ("ations", "ation", "ingly", "ings", "ing", "edly", "ies", "ied", "ers", "er", "est", "ed", "ly", "es", "s"):
        if w.endswith(suf) and len(w) - len(suf) >= 3:
            w = w[: -len(suf)] + ("y" if suf in ("ies", "ied") else "")
            break
    return w

def content(sentence: str) -> set[str]:
    return {stem(w) for w in WORD.findall(sentence.lower()) if w not in STOP and len(w) >= 3 and stem(w) not in STOP}

def sentences_from_cues(cues: list[dict]) -> list[dict]:
    """Join timed caption cues and split into sentences, each with its start time."""
    text, starts = "", []
    for c in cues:
        t = re.sub(r"\s+", " ", re.sub(r"\[[^\]]{1,30}\]|\([^)]{1,30}\)|♪", " ", c["text"])).strip()
        t = re.sub(r"^[-–>]+\s*|^[A-Z ]{2,20}:\s*", "", t)   # speaker marks
        if not t:
            continue
        starts.append((len(text), c["start"]))
        text += t + " "
    out, pos = [], 0
    for m in re.finditer(r".+?(?:[.!?…]+[\"')\]]*(?=\s+[\"'(\[]?[A-Z0-9])|$)", text.strip(), re.S):
        s = m.group(0).strip()
        if not s:
            continue
        at = next((t for off, t in reversed(starts) if off <= m.start()), 0.0)
        out.append({"text": s, "start": at})
    return out

def measure(sents: list[dict], duration: float | None = None, embed=None) -> dict:
    texts = [s["text"] for s in sents]
    words = [WORD.findall(t.lower()) for t in texts]
    nwords = sum(len(w) for w in words) or 1
    cont = [content(t) for t in texts]
    jumps, ties, seen, new_counts = [], [], set(), []
    for i, t in enumerate(texts):
        new_counts.append(len(cont[i] - seen)); seen |= cont[i]
        if i == 0:
            continue
        prev = cont[i - 1] | (cont[i - 2] if i >= 2 else set())
        shared = cont[i] & prev
        opener = words[i][:4]
        linked = bool(shared) or any(w in BACKREF for w in opener)
        ties.append(1.0 if shared else 0.0)
        if not linked and len(words[i]) >= 4:
            jumps.append(i)
    n = len(texts) or 1
    low = " ".join(texts).lower()
    freq = Counter(w for c in cont for w in c)
    spine = [w for w, k in freq.most_common(8) if k >= 3][:5]
    deciles = [set() for _ in range(10)]
    for i, c in enumerate(cont):
        deciles[min(9, i * 10 // n)] |= c
    spine_cover = (sum(1 for d in deciles if d & set(spine)) / 10) if spine else 0.0
    window_new = [sum(new_counts[i:i + 3]) for i in range(max(1, n - 2))]
    lens = [len(w) for w in words if w]
    out = {
        "sentences": n, "words": nwords,
        "wpm": round(nwords / (duration / 60), 1) if duration else None,
        "jump_rate": round(len(jumps) / max(1, n - 1), 3),
        "tie_rate": round(st.mean(ties), 3) if ties else 0.0,
        "new_terms_per_100w": round(100 * len(seen) / nwords, 1),
        "max_new_terms_3_sentences": max(window_new) if window_new else 0,
        "spine_cover": round(spine_cover, 2),
        "questions_per_100w": round(100 * sum(t.rstrip().endswith("?") for t in texts) / nwords, 2),
        "mean_sentence_words": round(st.mean(lens), 1) if lens else 0,
        "short_sentence_share": round(sum(1 for L in lens if L <= 3) / n, 3),
        **{f"{k}_per_100w": round(100 * len(re.findall(p, low)) / nwords, 2) for k, p in CONNECT.items()},
        "numbers_per_100w": round(100 * len(re.findall(r"\b\d+(?:\.\d+)?\b|\b(?:two|three|four|five|six|seven|eight|nine|ten|hundred|thousand|half)\b", low)) / nwords, 2),
        "you_we_per_100w": round(100 * len(re.findall(r"\b(you|your|we|our|us|let's)\b", low)) / nwords, 2),
        "spine": spine, "jumps": [{"i": i, "at": round(sents[i]["start"], 1), "text": texts[i][:160], "before": texts[i - 1][:120]} for i in jumps],
    }
    if embed is not None and n >= 3:
        import numpy as np
        v = embed(texts); v = v / (np.linalg.norm(v, axis=1, keepdims=True) + 1e-9)
        sims = [float(v[i] @ v[i - 1]) for i in range(1, n)]
        sims2 = [max(float(v[i] @ v[i - 1]), float(v[i] @ v[i - 2])) for i in range(2, n)]
        out["adjacent_similarity"] = round(st.mean(sims), 3)
        out["weak_seam_rate"] = round(sum(s < 0.15 for s in sims2) / len(sims2), 3)
        # how much nearer is a sentence to its neighbour than to a random sentence of the same talk (scale-free)
        allm = v @ v.T; base = (allm.sum() - n) / (n * (n - 1))
        out["neighbour_gain"] = round(st.mean(sims) - float(base), 3)
    return out


def seam_features(sents: list[dict], embed=None) -> list[list[float]]:
    """Per sentence (from the second on): what ties it to what came just before. Used by the jump finder."""
    texts = [s["text"] for s in sents]
    cont = [content(t) for t in texts]
    words = [WORD.findall(t.lower()) for t in texts]
    v = None
    if embed is not None:
        import numpy as np
        v = embed(texts); v = v / (np.linalg.norm(v, axis=1, keepdims=True) + 1e-9)
    feats = []
    for i in range(1, len(texts)):
        prev1 = cont[i - 1]; prev2 = prev1 | (cont[i - 2] if i >= 2 else set())
        f = [len(cont[i] & prev1), len(cont[i] & prev2), 1.0 if any(w in BACKREF for w in words[i][:4]) else 0.0,
             1.0 if texts[i].rstrip().endswith("?") else 0.0, min(len(words[i]), 40) / 40]
        if v is not None:
            c1 = float(v[i] @ v[i - 1]); c2 = float(v[i] @ v[i - 2]) if i >= 2 else c1
            nxt = float(v[i] @ v[i + 1]) if i + 1 < len(texts) else c1
            f += [c1, max(c1, c2), nxt]
        feats.append(f)
    return feats


def rule_jumps(sents: list[dict]) -> list[int]:
    """Words-only jump rule: a sentence of 6+ words that shares no word with the two before it, opens with no link
    word, and brings at least two words the talk has not used yet. (The scramble test measures how often it is right.)"""
    texts = [s["text"] for s in sents]; cont = [content(t) for t in texts]
    words = [WORD.findall(t.lower()) for t in texts]
    seen, out = set(), []
    for i, c in enumerate(cont):
        if i >= 1:
            prev = cont[i - 1] | (cont[i - 2] if i >= 2 else set())
            if len(words[i]) >= 6 and not (c & prev) and not any(w in BACKREF for w in words[i][:4]) and len(c - seen) >= 2:
                out.append(i)
        seen |= c
    return out


# ── lessons ──────────────────────────────────────────────────────────────────────────────────────────────────────────
# What follows reads a lessonforge lesson (chapters → beats → narration). The numbers it is held to come from the
# concept-explainer benchmark (evals/explainers/README.md): 230+ YouTube explainers from channels known for clear
# teaching, measured with the functions above; ``storyflow_band.json`` holds where the practice channels fall.

#: Lines that say the lesson's PLAN aloud instead of explaining. Each was heard in our 2026-11-03 videos; in 590,000
#: words of explainers from the benchmark none occurs even once ("take a moment": 12 times, always with a task).
STAGE_TALK = re.compile(
    r"\b(pause on (?:that|this|it)(?: too)?|predict before you (?:look|see)|now,? you,? with help|you,? with help|"
    r"say it back|start with what you know|start with the smallest(?: case)?|now (?:the|a) (?:picture|example|rule)\b\.?$|"
    r"(?:two|three|four) (?:words|quantities|things|ideas) first|your turn|take a moment\.?$)", re.I)


def _band() -> dict:
    import json
    from pathlib import Path
    try:
        return json.loads((Path(__file__).with_name("storyflow_band.json")).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def lesson_sentences(lesson: dict) -> list[dict]:
    """Every spoken sentence in order, with its beat id (``start`` is its position, for the shared measures)."""
    out = []
    for chapter in lesson.get("chapters") or []:
        for beat in chapter.get("beats") or []:
            for s in re.split(r"(?<=[.!?…])\s+(?=[\"'(\[]?[A-Z0-9])", str(beat.get("narration") or "").strip()):
                if s.strip():
                    out.append({"text": s.strip(), "start": float(len(out)), "beat": beat.get("id"), "chapter": chapter.get("id")})
    return out


def enabled() -> bool:
    from .. import knobs
    return knobs.get("HARNESS_STORY_GATE", "0") == "1"


def story_gate(lesson: dict) -> list[dict]:
    """Code-only story findings, ``major`` so the reviser rewrites them: lines that say the lesson's plan aloud.

    Sentences that jump are NOT findings here, on purpose. The benchmark's scramble test (evals/explainers) plants
    breaks in 162 held-out explainers: the word-overlap rule finds only 11-23% of them and also flags 8% of the
    sentences of real, good explainers, so it would send rewrites after faults that are not there. Jumps are reported
    by ``report`` (and ``lessonforge storyflow``) for a person to read, and need a judge that passes that test."""
    if (lesson.get("brief") or {}).get("mode") == "script":
        return []                                # a pasted script is spoken as written
    out, seen_beats = [], set()
    for s in lesson_sentences(lesson):
        hit = STAGE_TALK.search(s["text"])
        if hit and s["beat"] not in seen_beats:
            seen_beats.add(s["beat"])
            out.append({"severity": "major", "beat": s["beat"], "resolved": False,
                        "what": f"story: it says the lesson's plan aloud (“{s['text'][:80]}”) — good explainers never do",
                        "fix": "drop that line and carry its job in the explanation itself: ask the real question and say "
                               "why it matters (“So which way does it bend, and why?”), or go straight on with the reason"})
    return out


def report(sents: list[dict], duration: float | None = None, embed=None) -> dict:
    """The measures, each beside where good explainers fall (p10–p90 of the practice channels)."""
    m = measure(sents, duration, embed)
    band = (_band().get("practice_channels") or {})
    rows = {}
    for key, value in m.items():
        if key in band and isinstance(value, (int, float)):
            b = band[key]
            where = "low" if b["p10"] is not None and value < b["p10"] else "high" if b["p90"] is not None and value > b["p90"] else "in range"
            rows[key] = {"value": value, "p10": b["p10"], "p50": b["p50"], "p90": b["p90"], "where": where}
    stage = [s["text"] for s in sents if STAGE_TALK.search(s["text"])]
    return {"measures": rows, "plan_aloud": stage, "jumps": [sents[i]["text"] for i in rule_jumps(sents)]}
