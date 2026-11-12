#!/usr/bin/env python3
"""Download NCERT textbook PDFs straight from ncert.nic.in.

NCERT serves every chapter as  https://ncert.nic.in/textbook/pdf/<code><NN>.pdf
where <code> is the book code (e.g. `iesc1`, `jemh1`, `aejm1`) and <NN> is the
2-digit chapter number. The site's own class→subject→book dropdown JS
(`textbook.js`) is the authoritative catalog: every book appears as
`... .value="textbook.php?<code>=0-<N>"` (chapters 0..N) next to its title, inside
an `if(tclass.value==<class>) && (tsubject...=="<subject>")` guard.

Two ways to use it:

  # 1. Whole catalog from the site JS (save it first from view-source of
  #    https://ncert.nic.in/textbook.php, or the <script src=...textbook.js>):
  python3 scripts/ncert_download.py --from-js textbook.js --class 9 --subject Science

  # 2. Directly, no JS, when you already know the code + chapter count:
  python3 scripts/ncert_download.py --code iesc1 --chapters 15

Cache-first: an already-downloaded, non-empty PDF is never re-fetched. 404s are
skipped (some books have gaps). Writes `<out>/catalog.json` — the parsed catalog
plus what landed on disk.

The default --out is the lesson library (`<workspace>/library/ncert`), the folder
`lessonforge.harness.library` reads: a book downloaded here is searched for the
chapter that covers a lesson's topic, and its `catalog.json` rows extend the small
table of books that module knows by itself. NCERT textbooks are free to read and
all rights reserved, which is why they live in the workspace and never in the repo.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

BASE = "https://ncert.nic.in/textbook/pdf"
UA = "Mozilla/5.0 (CE-ncert-downloader; +local)"
DEFAULT_OUT = Path(os.getenv("LESSONFORGE_HOME", "lessonforge_workspace")) / "library" / "ncert"

# NCERT class-letter prefixes are not needed to download (the code is explicit),
# but the site groups books under numeric class + subject guards, which we parse.


def _strip_js_comments(js: str) -> str:
    js = re.sub(r"/\*.*?\*/", "", js, flags=re.S)          # /* block */
    js = re.sub(r"^\s*//.*$", "", js, flags=re.M)          # // line
    return js


_GUARD_RE = re.compile(
    r"tclass\.value==(\d+)\)\s*&&\s*\(document\.test\.tsubject\.options\[sind\]\.text==\"([^\"]+)\"")
_TEXT_RE = re.compile(r"tbook\.options\[(\d+)\]\.text=\"([^\"]+)\"")
_VALUE_RE = re.compile(r"tbook\.options\[(\d+)\]\.value=\"textbook\.php\?([A-Za-z0-9]+)=(\d+)-(\d+)\"")


def parse_textbook_js(js: str) -> list[dict]:
    """Return catalog rows: {klass, subject, book, code, first, last, chapters}.

    `chapters` = last (the site's `0-N` means chapters 1..N; 0 is front-matter)."""
    js = _strip_js_comments(js)
    guards = list(_GUARD_RE.finditer(js))
    rows: list[dict] = []
    for i, g in enumerate(guards):
        klass, subject = int(g.group(1)), g.group(2).strip()
        body = js[g.end(): guards[i + 1].start() if i + 1 < len(guards) else len(js)]
        texts = {int(m.group(1)): m.group(2).strip() for m in _TEXT_RE.finditer(body)}
        for m in _VALUE_RE.finditer(body):
            idx, code, first, last = int(m.group(1)), m.group(2), int(m.group(3)), int(m.group(4))
            title = texts.get(idx, code)
            if not title or title.startswith(".."):     # ".. Select Book Title .."
                title = code
            rows.append({"klass": klass, "subject": subject, "book": title,
                         "code": code, "first": first, "last": last, "chapters": last})
    # de-dupe identical (code) rows the JS repeats
    seen, uniq = set(), []
    for r in rows:
        key = (r["code"], r["klass"], r["subject"])
        if key in seen:
            continue
        seen.add(key)
        uniq.append(r)
    return uniq


def _fetch(url: str, dest: Path, *, timeout: int, retries: int = 3) -> tuple[str, int]:
    """Return ("ok"|"skip"|"404"|"err", bytes). Cache-first: existing non-empty file is kept."""
    if dest.exists() and dest.stat().st_size > 0:
        return "skip", dest.stat().st_size
    last_exc = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = resp.read()
            if not data:
                return "err", 0
            tmp = dest.with_suffix(dest.suffix + ".part")
            tmp.write_bytes(data)
            tmp.replace(dest)
            return "ok", len(data)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return "404", 0
            last_exc = e
        except Exception as e:  # noqa: BLE001 - network flakiness, retry
            last_exc = e
        time.sleep(1.5 * (attempt + 1))
    print(f"    ! failed {url}: {last_exc}", file=sys.stderr)
    return "err", 0


def download_book(code: str, chapters: int, out: Path, *, timeout: int,
                  delay: float, extras: bool = True) -> list[dict]:
    """Download <code>01..<chapters>.pdf (+ optional front-matter/answers) into out/<code>/."""
    book_dir = out / code
    book_dir.mkdir(parents=True, exist_ok=True)
    got: list[dict] = []
    names = [f"{code}{n:02d}" for n in range(1, chapters + 1)]
    if extras:
        names = [f"{code}ps"] + names + [f"{code}an"]     # prelims, answers (skipped if 404)
    for name in names:
        dest = book_dir / f"{name}.pdf"
        status, size = _fetch(f"{BASE}/{name}.pdf", dest, timeout=timeout)
        tag = {"ok": "✓", "skip": "·", "404": "–", "err": "✗"}[status]
        print(f"  {tag} {name}.pdf  ({size:,} B){'' if status!='skip' else '  cached'}")
        if status in ("ok", "skip"):
            got.append({"name": name, "path": str(dest), "bytes": size})
        if status == "ok":
            time.sleep(delay)
    return got


def main() -> int:
    ap = argparse.ArgumentParser(description="Download NCERT textbook PDFs.")
    ap.add_argument("--from-js", type=Path, help="path to the site's textbook.js")
    ap.add_argument("--code", help="direct book code, e.g. iesc1")
    ap.add_argument("--chapters", type=int, help="chapter count for --code")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--class", dest="klass", type=int, help="filter: class number")
    ap.add_argument("--subject", help="filter: subject (substring, case-insensitive)")
    ap.add_argument("--timeout", type=int, default=60)
    ap.add_argument("--delay", type=float, default=0.5, help="polite pause between downloads (s)")
    ap.add_argument("--no-extras", action="store_true", help="skip prelims/answers files")
    ap.add_argument("--list-only", action="store_true", help="print the parsed catalog and exit")
    args = ap.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)
    catalog: list[dict] = []

    if args.from_js:
        rows = parse_textbook_js(args.from_js.read_text(encoding="utf-8", errors="ignore"))
        if args.klass:
            rows = [r for r in rows if r["klass"] == args.klass]
        if args.subject:
            rows = [r for r in rows if args.subject.lower() in r["subject"].lower()]
        print(f"Catalog: {len(rows)} book(s)"
              + (f" (class {args.klass})" if args.klass else "")
              + (f" (subject~{args.subject})" if args.subject else ""))
        for r in rows:
            print(f"  [{r['klass']:>2}] {r['subject']:<16} {r['book']:<40} {r['code']}  ch 1..{r['chapters']}")
        if args.list_only:
            (args.out / "catalog.json").write_text(json.dumps(rows, indent=2, ensure_ascii=False))
            return 0
        for r in rows:
            print(f"\n▼ {r['book']}  (class {r['klass']} · {r['subject']} · {r['code']})")
            r["downloaded"] = download_book(r["code"], r["chapters"], args.out,
                                            timeout=args.timeout, delay=args.delay,
                                            extras=not args.no_extras)
            catalog.append(r)
    elif args.code and args.chapters:
        print(f"▼ {args.code}  ch 1..{args.chapters}")
        got = download_book(args.code, args.chapters, args.out, timeout=args.timeout,
                            delay=args.delay, extras=not args.no_extras)
        catalog.append({"klass": None, "subject": "", "book": args.code, "code": args.code,
                        "chapters": args.chapters, "downloaded": got})
    else:
        ap.error("give either --from-js, or --code with --chapters")

    cat_path = args.out / "catalog.json"
    prior = []
    if cat_path.exists():
        try:
            prior = json.loads(cat_path.read_text())
        except Exception:
            prior = []
    by_code = {c["code"]: c for c in prior if isinstance(c, dict) and c.get("code")}
    for c in catalog:
        by_code[c["code"]] = c
    cat_path.write_text(json.dumps(list(by_code.values()), indent=2, ensure_ascii=False))
    total = sum(len(c.get("downloaded", [])) for c in catalog)
    print(f"\nDone. {total} PDF(s) on disk. Catalog → {cat_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
