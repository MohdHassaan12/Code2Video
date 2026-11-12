"""Asset stage: detect non-Manim items, live-probe svg_icon/chemical_molecule
resolution, choose a realistic background."""
import re
import urllib.parse
import logging
import requests as _requests

logger = logging.getLogger(__name__)

def determine_background(style, interest=""):
    """
    Determines realistic background filename based on style and interest keywords.
    Returns 'chalkboard.jpg', 'space.jpg', 'notebook_paper.jpg', 'blueprint.jpg', or 'default'.
    """
    style_lower = style.lower()
    interest_lower = interest.lower()
    
    # 1. Match specific interest keywords
    if any(x in interest_lower for x in ["space", "universe", "astronomy", "physics", "galaxy", "star"]):
        return "space.jpg"
    if any(x in interest_lower for x in ["school", "classroom", "chalk", "teacher", "chalkboard"]):
        return "chalkboard.jpg"
    if any(x in interest_lower for x in ["notebook", "paper", "write", "drawing", "art", "baking", "cooking"]):
        return "notebook_paper.jpg"
    if any(x in interest_lower for x in ["minecraft", "game", "gaming", "building", "engineer", "blueprint", "grid", "coding", "computer"]):
        return "blueprint.jpg"
    
    # 2. Match style keywords
    if "chalkboard" in style_lower:
        return "chalkboard.jpg"
    if "space" in style_lower or "cyberpunk" in style_lower:
        return "space.jpg"
    if "powerpoint" in style_lower:
        return "white_canvas"
    
    return "default"


_REAL_IMAGE_RE = re.compile(
    r'\b(photograph|photo(?:graph)?|real[- ]image|actual[- ]image|real[- ]photo|'
    r'microscope[- ]image|satellite[- ]image|x[- ]ray|mri scan|ct scan|'
    r'picture of|image of|real[- ]world (photo|image)|textbook (diagram|figure)|'
    r'diagram from|anatomical diagram|histology|electron microscope)\b',
    re.IGNORECASE
)


_TABLE_RE = re.compile(
    r'\b(data[- ]table|table of (values|data|results)|comparison[- ]table|'
    r'tabulated|refractive[- ]index[- ]table|periodic[- ]table|'
    r'truth[- ]table|lookup[- ]table)\b',
    re.IGNORECASE
)


_TYPE_LABELS = {
    "real_image":       "Real image / photograph",
    "data_table":       "Data table",
    "complex_svg":      "Complex SVG (Iconify may not find)",
}


_SUGGESTIONS = {
    "real_image":   "Source from a stock image library, textbook scan, or Wikimedia Commons",
    "data_table":   "Create as a static image or use Manim's Table() mobject with hardcoded data",
    # No longer "simplify the keyword": since 2026-08-14 an unresolvable icon is DRAWN
    # (app/asset_gen.py writes matplotlib code and renders it), so a specific multi-word
    # keyword is now an ASSET, not a liability — dumbing it down makes the result worse.
    "complex_svg":  "Left to the icon generator — it will be drawn from the keyword at codegen time",
}


def extract_non_manim_items(storyboard_data: dict) -> list:
    """Scan a storyboard dict and return a list of items Manim cannot produce natively."""
    items = []
    seen = set()  # deduplicate identical (scene, type, description) tuples

    def _add(scene_idx, item_type, elem_id, description):
        key = (scene_idx, item_type, description[:80])
        if key in seen:
            return
        seen.add(key)
        entry = {
            "scene": scene_idx,
            "type": item_type,
            "label": _TYPE_LABELS.get(item_type, item_type),
            "description": description,
            "suggestion": _SUGGESTIONS.get(item_type, ""),
        }
        if elem_id:
            entry["element_id"] = elem_id
        items.append(entry)

    for scene in storyboard_data.get("visual_storyboard", []):
        s = scene.get("scene_index", "?")
        desc = scene.get("description", "")

        if _REAL_IMAGE_RE.search(desc):
            _add(s, "real_image", None, desc[:200])
        if _TABLE_RE.search(desc):
            _add(s, "data_table", None, desc[:200])

        for cue_obj in scene.get("narration_cues", []):
            cue = cue_obj.get("cue", "")
            if _REAL_IMAGE_RE.search(cue):
                _add(s, "real_image", None, cue[:200])
            if _TABLE_RE.search(cue):
                _add(s, "data_table", None, cue[:200])

        for elem in scene.get("elements", []):
            etype = elem.get("type", "")
            content = elem.get("content", "")
            elem_id = elem.get("id", "")

            if etype == "svg_icon" and len(content.split()) > 2:
                _add(s, "complex_svg", elem_id, content[:200])

            if _REAL_IMAGE_RE.search(content):
                _add(s, "real_image", elem_id, content[:200])
            if _TABLE_RE.search(content):
                _add(s, "data_table", elem_id, content[:200])

    return items


def probe_asset(element_type: str, keyword: str) -> dict:
    """Lightweight HTTP probe — checks whether an svg_icon or chemical_molecule will resolve
    at render time WITHOUT writing files or invoking Manim.
    Returns {"status": "resolved"|"fallback", "provider": str, ...extras}
    """
    kw = keyword.strip()

    if element_type == "chemical_molecule":
        # RDKit is local (no network) — fastest check
        try:
            from rdkit import Chem
            mol = Chem.MolFromSmiles(kw)
            if mol is not None:
                return {"status": "resolved", "provider": "RDKit"}
        except Exception:
            pass
        # PubChem fallback (network)
        try:
            is_smiles = len(kw) > 2 and all(c in "CcnNoOsSpPFFClBrIBH1234567890()=#-/\\[]@+ " for c in kw)
            id_type = "smiles" if is_smiles else "name"
            url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/{id_type}/{urllib.parse.quote(kw)}/record/SVG"
            r = _requests.get(url, timeout=6)
            if r.status_code == 200 and "</svg>" in r.text:
                return {"status": "resolved", "provider": "PubChem"}
        except Exception:
            pass
        return {"status": "fallback", "provider": "native_shape"}

    else:  # svg_icon
        # Iconify: returns a ranked icon list for the keyword
        try:
            kw_slug = kw.lower().replace(" ", "-")
            res = _requests.get(
                f"https://api.iconify.design/search?query={urllib.parse.quote(kw_slug)}&limit=1",
                timeout=5
            ).json()
            if res.get("icons"):
                icon_id = res["icons"][0]
                return {"status": "resolved", "provider": "Iconify", "icon_id": icon_id,
                        "match": icon_match_strength(kw, icon_id)}
        except Exception:
            pass
        # Bootstrap Icons: exact name match (no API key needed)
        try:
            kw_slug = kw.lower().replace(" ", "-")
            r = _requests.get(
                f"https://cdn.jsdelivr.net/npm/bootstrap-icons@1.10.0/icons/{urllib.parse.quote(kw_slug)}.svg",
                timeout=3
            )
            if r.status_code == 200 and "</svg>" in r.text:
                # An exact filename match — the icon IS the keyword.
                return {"status": "resolved", "provider": "Bootstrap Icons",
                        "icon_id": kw_slug, "match": "strong"}
        except Exception:
            pass
        return {"status": "fallback", "provider": "native_shape", "match": "none"}


# Words that carry no icon meaning — ignored when scoring a match.
_ICON_STOPWORDS = {"the", "a", "an", "of", "for", "and", "with", "icon", "symbol",
                   "simple", "small", "large", "old", "new"}


def icon_match_strength(keyword: str, icon_id: str) -> str:
    """How well a retrieved icon actually covers the keyword: strong | partial | weak.

    Iconify always answers with its CLOSEST icon, never "no". Ask it for a
    "grandfather clock" and it hands back a plain clock face — a *generic ancestor*
    of what the storyboard asked for. That resolves the probe (status: resolved) so
    nothing downstream ever knew the icon was wrong, and the video showed a generic
    time icon (reported by the user, 2026-08-14). A retrieved-but-wrong asset is a
    worse failure than a miss, because a miss at least triggers a fallback.

    Scoring is deterministic: every significant keyword word must appear in the icon
    id (5-char prefix, so plurals/inflections still count). Anything less means the
    icon dropped part of the request, and the caller may prefer to DRAW it instead
    (app/asset_gen.py).
    """
    words = [w for w in re.split(r"[^a-z0-9]+", (keyword or "").lower())
             if len(w) > 2 and w not in _ICON_STOPWORDS]
    name = (icon_id or "").split(":")[-1].lower()
    if not words:
        return "weak"
    covered = sum(1 for w in words if w[:5] in name or (len(name) > 2 and name in w))
    if covered == len(words):
        return "strong"
    return "partial" if covered else "weak"


def _collect_asset_elements(storyboard: dict) -> list:
    """Extract every svg_icon and chemical_molecule element from a storyboard dict.

    An element whose content is already an absolute path is SKIPPED: the server drew it
    in Manim (sim_gen.resolve_drawn_elements) and there is nothing left to fetch.
    Probing it would spend a network round-trip on a filename, fail, and — because a
    failed probe becomes an asset warning, and a warned element degrades to a Text
    placeholder — actively delete the drawing it was reporting on.
    """
    items = []
    for scene in storyboard.get("visual_storyboard", []):
        scene_idx = scene.get("scene_index", "?")
        for elem in scene.get("elements", []):
            etype = elem.get("type", "")
            content = str(elem.get("content", ""))
            if content.endswith(".py") and _os.path.isabs(content):
                continue
            if etype in ("svg_icon", "chemical_molecule"):
                items.append({
                    "scene": scene_idx,
                    "element_id": elem.get("id", ""),
                    "type": etype,
                    "keyword": elem.get("content", ""),
                })
    return items


# ---------------------------------------------------------------------------
# Wikimedia Commons raster images (type: "image" elements)
#
# Resolution happens SERVER-SIDE at codegen time: the search query in the
# element's `content` is replaced with an absolute local file path, so the
# render subprocess never depends on the network and the layout knows real
# pixel dimensions. `fetch_real_image` in viz_helpers is the render-time
# fallback for a query that was never resolved (and the loader for the path).
# Attribution (license/artist/source URL) is kept in a JSON sidecar next to
# each cached image — required for CC-licensed files.
# ---------------------------------------------------------------------------

import os as _os
import json as _json
import hashlib as _hashlib

# Wikimedia's User-Agent policy requires a CONTACT (URL or email) in the string, not
# just a product name. Measured 2026-08-15 on a live "Projectile motion" run: the
# search API answered fine and returned the right files, then every download from
# upload.wikimedia.org came back `429 — Your request does not comply with our robot
# policy`. So 0/2 images resolved and both degraded to Text placeholders of the raw
# search query, one of which rendered clipped off the frame edge. Nothing in the logs
# said "images are off" — the pipeline degrades quietly by design, which is right for
# one bad query and misleading for a blanket block.
# Override with WIKIMEDIA_USER_AGENT to put your own contact in (recommended if you
# generate at volume — the policy is enforced per UA).
_WM_UA = _os.environ.get(
    "WIKIMEDIA_USER_AGENT",
    "GyanSetu-ConceptExplorer/1.0 "
    "(https://github.com/ManideepDonkena/concept_explorer; educational video pipeline)",
)
_WM_HEADERS = {"User-Agent": _WM_UA, "Accept": "image/*,*/*;q=0.8"}
_WM_API = "https://commons.wikimedia.org/w/api.php"


def _image_cache_dir() -> str:
    from lessonforge import paths as _paths
    d = _os.environ.get("WIKIMEDIA_IMAGE_CACHE") or str(_paths.cache("assets", "wikimedia"))
    _os.makedirs(d, exist_ok=True)
    return d


def resolve_wikimedia_image(query: str, thumb_width: int = 1024) -> dict | None:
    """Search Commons for a bitmap matching `query`, download a sized thumbnail,
    and return {path, width, height, title, source_url, license, artist}.
    Cached on disk by query hash; returns None on any failure (caller degrades)."""
    query = (query or "").strip()
    if not query:
        return None
    cache_dir = _image_cache_dir()
    key = _hashlib.sha1(f"{query}|{thumb_width}".encode("utf-8")).hexdigest()[:12]
    meta_path = _os.path.join(cache_dir, f"wm_{key}.json")
    if _os.path.exists(meta_path):
        try:
            meta = _json.load(open(meta_path, encoding="utf-8"))
            if _os.path.exists(meta.get("path", "")):
                return meta
        except Exception:
            pass
    try:
        params = {
            "action": "query", "format": "json",
            "generator": "search",
            "gsrsearch": f"filetype:bitmap {query}",
            "gsrnamespace": 6, "gsrlimit": 5,
            "prop": "imageinfo",
            "iiprop": "url|size|mime|extmetadata",
            "iiurlwidth": thumb_width,
            "iiextmetadatafilter": "LicenseShortName|Artist",
        }
        res = _requests.get(_WM_API, params=params, headers=_WM_HEADERS, timeout=10)
        res.raise_for_status()
        pages = res.json().get("query", {}).get("pages", {})
    except Exception as e:
        logger.warning("Wikimedia search failed for %r: %s", query, e)
        return None

    # Pages come keyed by pageid; restore search ranking via 'index'.
    candidates = sorted(pages.values(), key=lambda p: p.get("index", 999))
    for page in candidates:
        infos = page.get("imageinfo") or []
        if not infos:
            continue
        info = infos[0]
        mime = info.get("mime", "")
        w, h = info.get("width", 0), info.get("height", 0)
        if mime not in ("image/jpeg", "image/png") or w < 400 or h < 300:
            continue
        # Extreme aspect ratios (panoramas, strips) layout badly in a 16:9 frame.
        if h and not (0.4 <= w / h <= 2.6):
            continue
        thumb_url = info.get("thumburl") or info.get("url")
        if not thumb_url:
            continue
        ext = ".png" if mime == "image/png" else ".jpg"
        img_path = _os.path.join(cache_dir, f"wm_{key}{ext}")
        try:
            dl = _requests.get(thumb_url, headers=_WM_HEADERS, timeout=15)
            if dl.status_code == 429:
                # Commons rate-limits parallel thumb downloads; one polite retry.
                import time as _time
                _time.sleep(3)
                dl = _requests.get(thumb_url, headers=_WM_HEADERS, timeout=15)
            dl.raise_for_status()
            with open(img_path, "wb") as f:
                f.write(dl.content)
        except Exception as e:
            logger.warning("Wikimedia download failed for %r (%s): %s", query, thumb_url, e)
            continue
        extmeta = info.get("extmetadata") or {}
        meta = {
            "path": img_path,
            "width": info.get("thumbwidth", w),
            "height": info.get("thumbheight", h),
            "title": page.get("title", ""),
            "source_url": info.get("descriptionurl", ""),
            "license": (extmeta.get("LicenseShortName") or {}).get("value", ""),
            "artist": re.sub(r"<[^>]+>", "", (extmeta.get("Artist") or {}).get("value", "")).strip(),
            "query": query,
        }
        try:
            with open(meta_path, "w", encoding="utf-8") as f:
                _json.dump(meta, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
        logger.info("Wikimedia image resolved: %r -> %s (%sx%s, %s)",
                    query, meta["title"], meta["width"], meta["height"], meta["license"])
        return meta
    logger.warning("Wikimedia: no suitable bitmap for %r", query)
    return None


def resolve_image_elements(storyboard: dict) -> list:
    """Pre-render pass: resolve every `image` element's search query to a local
    cached file (content is rewritten to the absolute path). Returns asset-warning
    dicts (same shape as probe_asset fallbacks) for elements that could not be
    resolved, so codegen degrades them instead of failing at render time."""
    from concurrent.futures import ThreadPoolExecutor

    todo = []
    for scene in storyboard.get("visual_storyboard", []):
        for elem in scene.get("elements", []):
            if elem.get("type") == "image" and not _os.path.isabs(elem.get("content", "")):
                todo.append((scene.get("scene_index", "?"), elem))
    if not todo:
        return []
    warnings = []
    # 3 workers, not more: Commons 429s aggressive parallel thumbnail pulls.
    with ThreadPoolExecutor(max_workers=min(len(todo), 3)) as pool:
        metas = list(pool.map(lambda t: resolve_wikimedia_image(t[1].get("content", "")), todo))
    for (scene_idx, elem), meta in zip(todo, metas):
        if meta:
            elem["content"] = meta["path"]
        else:
            warnings.append({
                "scene": scene_idx,
                "element_id": elem.get("id", ""),
                "type": "image",
                "keyword": elem.get("content", ""),
                "status": "fallback",
                "provider": "wikimedia",
            })
    return warnings
