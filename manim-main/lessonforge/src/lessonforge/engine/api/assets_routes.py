"""Routes: /api/preflight_assets, /api/probe_asset, /api/asset_issues."""
from fastapi import APIRouter, HTTPException
from concurrent.futures import ThreadPoolExecutor

from ..assets import _collect_asset_elements, probe_asset, extract_non_manim_items
from ..schemas import PreflightRequest, ProbeAssetRequest

router = APIRouter()

@router.post("/api/preflight_assets")
def preflight_assets(body: PreflightRequest):
    """Probe all svg_icon and chemical_molecule elements in a storyboard in parallel.
    Returns per-item resolution status so the creator can fix fallbacks before codegen."""
    storyboard = body.storyboard
    raw_items = _collect_asset_elements(storyboard)

    if not raw_items:
        return {"total": 0, "resolved": 0, "fallback_count": 0, "items": []}

    def probe_one(item):
        result = probe_asset(item["type"], item["keyword"])
        return {**item, **result}

    with ThreadPoolExecutor(max_workers=min(len(raw_items), 10)) as pool:
        results = list(pool.map(probe_one, raw_items))

    fallback_count = sum(1 for r in results if r["status"] == "fallback")
    return {
        "total": len(results),
        "resolved": len(results) - fallback_count,
        "fallback_count": fallback_count,
        "items": results,
    }


@router.post("/api/probe_asset")
def probe_asset_route(body: ProbeAssetRequest):
    """Single-asset re-test endpoint – used by the UI when a creator edits a keyword inline."""
    keyword = body.keyword.strip()
    if not keyword:
        raise HTTPException(status_code=400, detail="keyword is required")
    return probe_asset(body.type, keyword)


@router.post("/api/asset_issues")
def asset_issues(body: PreflightRequest):
    """Unified asset-issues endpoint — runs both the keyword scan and the live probe pass,
    then returns a single structured list of everything a creator needs to fix before rendering.

    Tiers:
      'missing'  — real photos / data tables Manim cannot produce at all
      'fallback' — svg_icon / chemical_molecule that failed all API probes (will degrade to native shape)

    Request body: { "storyboard": <storyboard dict> }
    Response:
    {
      "counts": { "missing": N, "fallback": N, "total": N },
      "issues": [
        {
          "scene": <int|str>,
          "tier": "missing" | "fallback",
          "element_type": "real_image" | "data_table" | "complex_svg" | "svg_icon" | "chemical_molecule",
          "element_id": <str|null>,
          "description": <str>,
          "provider_tried": <str|null>,   // only for fallback tier
          "action": <str>
        }, ...
      ]
    }
    """
    storyboard = body.storyboard

    issues = []

    def _fallback_action(probe):
        """What will ACTUALLY happen to this asset — not generic advice.

        Until 2026-08-14 this panel told the user to "edit the keyword to a simpler
        single-word term", because a miss meant a generic native shape. It now
        under-reports what the pipeline does: an unresolvable icon is DRAWN
        (app/asset_gen.py). Telling someone to simplify "person throwing ball" to
        "person" would actively make their video worse, so the panel must describe
        the real cascade — advice that contradicts the code is worse than none.
        """
        try:
            from ..asset_gen import should_generate, enabled
        except Exception:
            return ("Will render as a generic native shape — simplify the keyword "
                    "or supply a custom SVG.")
        if enabled() and should_generate(probe):
            return ("No icon found, so it will be DRAWN at codegen time (generated "
                    "vector asset, cached per keyword). Keep the descriptive keyword — "
                    "a specific one draws better. Set ASSET_GEN=0 to disable.")
        return ("Will render as a generic native shape (icon generation is off for "
                "this type/mode) — simplify the keyword or supply a custom SVG.")

    # â"€â"€ Tier 1: keyword scan (missing / Manim-impossible items) â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€
    _ACTION_MAP = {
        "real_image":   "Source externally (stock library, Wikimedia Commons, or textbook scan)",
        "data_table":   "Create as a static image or hardcode data into a Manim Table() mobject",
        "complex_svg":  "Will be DRAWN at codegen time (generated vector asset) — keep the descriptive keyword",
    }
    for item in extract_non_manim_items(storyboard):
        issues.append({
            "scene":        item["scene"],
            "tier":         "missing",
            "element_type": item["type"],
            "element_id":   item.get("element_id"),
            "description":  item["description"],
            "provider_tried": None,
            "action":       _ACTION_MAP.get(item["type"], item.get("suggestion", "")),
        })

    # â"€â"€ Tier 2: live probe (fallback — will degrade to native shape) â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€
    raw_items = _collect_asset_elements(storyboard)

    def probe_one(item):
        result = probe_asset(item["type"], item["keyword"])
        return {**item, **result}

    if raw_items:
        with ThreadPoolExecutor(max_workers=min(len(raw_items), 10)) as pool:
            probed = list(pool.map(probe_one, raw_items))
        for p in probed:
            if p["status"] == "fallback":
                issues.append({
                    "scene":        p["scene"],
                    "tier":         "fallback",
                    "element_type": p["type"],
                    "element_id":   p.get("element_id"),
                    "description":  p["keyword"],
                    "provider_tried": p.get("provider"),
                    "action":       _fallback_action(p),
                })

    missing_count  = sum(1 for i in issues if i["tier"] == "missing")
    fallback_count = sum(1 for i in issues if i["tier"] == "fallback")
    return {
        "counts": {
            "missing":  missing_count,
            "fallback": fallback_count,
            "total":    len(issues),
        },
        "issues": issues,
    }


@router.get("/api/theme")
def get_theme(style: str = "", background: str = "default"):
    """The RESOLVED theme for a style/background pair — canvas, accent, palette.

    Exists so the Studio blueprint can draw on the same canvas and palette the
    transpiler will use. Until 2026-08-14 the blueprint hard-coded its own dark
    background and its own colours, so the preview could not match the render even
    in principle, and mirroring the theme table in JavaScript would have been a
    drift-by-construction copy (the same mistake as the hardcoded voice lists).
    One table, served.
    """
    from lessonforge.theme import resolve_theme, MIN_CONTRAST

    t = resolve_theme(style, background)
    return {
        "key": t.key,
        "background": t.background,
        "is_light": t.is_light,
        "text": t.text,
        "accent": t.accent,
        "accent2": t.accent2,
        "palette": list(t.palette),
        "min_contrast": MIN_CONTRAST,
        # The canvas the CONTENT lands on, which is what a preview must paint:
        # a light theme is only ever reached through white_canvas.
        "canvas": "#FFFFFF" if t.is_light else t.background,
    }
