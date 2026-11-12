"""Acceptance harness for prose->shape resolution (no manim, no API keys).

Pins the failure class found on the 2026-08-01 "Prime Factorization" render, where
16 of 17 shape elements drew as the wrong object and the video lost its entire
teaching content. The storyboard was fine — `content` for a shape is prose by
schema ("For shape, a description"), and the transpiler was substring-matching
that prose:

  · "Large cyan chalk circle containing 84"        -> Circle(), the 84 DROPPED
  · "Two chalk branches from 84 to circles ..."    -> Circle() (matched the
                                                      contents, not the object)
  · "Chalk starburst surrounding ..."              -> Circle() (unknown -> fallback)
  · "... four chalk tiles ... with motion arrows"  -> Arrow() (matched decoration)

Run: .venv/bin/python stem_animation_lab/test_shape_resolution.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import lessonforge.transpiler as T  # noqa: E402

_passed = 0
_failed = 0


def check(label, cond):
    global _passed, _failed
    if cond:
        _passed += 1
        print(f"PASS {label}")
    else:
        _failed += 1
        print(f"FAIL {label}")


def obj_of(content):
    """The object expression the transpiler would emit for a shape description."""
    expr, _ = T._resolve_shape(content)
    if expr is None:
        return "svg:" + T._shape_asset_keyword(content)
    value = T._shape_value_label(content)
    if value and expr in T._CLOSED_SHAPES:
        return f"value_in({expr}, {value!r})"
    return expr


# ── A. Word-boundary matching (the "narrow" contains "arrow" trap) ────────────
print("\n-- A. word-boundary matching --")
check("'narrow band' is NOT an Arrow", "Arrow" not in obj_of("a narrow band"))
check("'arrows' still matches Arrow", obj_of("two arrows").startswith("Arrow"))
check("'outline of a leaf' is NOT a Line", "Line" not in obj_of("outline of a leaf"))
check("'dashed line' is a Line", obj_of("dashed line").startswith("Line"))
check("'anecdote card' is NOT a Dot", "Dot" not in obj_of("anecdote card"))

# ── B. Head-noun wins over contents/decoration ────────────────────────────────
print("\n-- B. the head noun names the shape --")
check("branches ... to circles -> Line (not Circle)",
      obj_of("Two diagonal chalk branches from 84 to circles containing 12 and 7").startswith("Line"))
check("frame with ... circles -> Rectangle (not Circle)",
      obj_of("Large coral chalk frame with a short factor branch ending at circles 2 and 6").startswith("Rectangle"))
check("tiles ... with motion arrows -> Rectangle (not Arrow)",
      obj_of("A second row of the same four chalk tiles reordered as 5, 2, 3, and 2 with curved motion arrows").startswith("Rectangle"))
check("'arrow pointing at X' still builds a Dot (documented precedence)",
      obj_of("arrow pointing at X").startswith("Dot"))

# ── C. Contained values are drawn (the content-loss bug) ──────────────────────
print("\n-- C. a shape 'containing 84' renders the 84 --")
check("circle containing 84 -> value_in(Circle(), '84')",
      obj_of("Large cyan chalk circle containing 84 as the root of a factor tree")
      == "value_in(Circle(), '84')")
check("block containing 60, drawn as ... -> keeps 60 (comma then prose)",
      obj_of("large chalk block containing 60, drawn as a single area")
      == "value_in(Rectangle(), '60')")
check("'containing 12 and 7' labels NOTHING (two nodes, one shape would lie)",
      obj_of("chalk circle containing 12 and 7") == "Circle()")
check("'containing 2, 2, 3 and 5' labels NOTHING (a list)",
      obj_of("four chalk tiles containing 2, 2, 3 and 5") == "Rectangle()")
check("'containing twelve evenly spaced slots' is prose, not a value",
      obj_of("rectangular tray containing twelve evenly spaced slots") == "Rectangle()")
check("a value only goes inside a CLOSED shape",
      "value_in" not in obj_of("chalk branch showing 7"))

# ── D. Unknown shapes reach the asset cascade, not a blank Circle ─────────────
print("\n-- D. unknown shape -> asset cascade (roadmap D5) --")
check("starburst -> asset, not Circle",
      obj_of("Chalk starburst surrounding the smallest equal groups").startswith("Star")
      or obj_of("Chalk starburst surrounding the smallest equal groups").startswith("svg:"))
check("check mark -> asset keyword, not Circle",
      obj_of("large green chalk check mark beside the three prime leaves").startswith("svg:"))
check("asset keyword drops colour/size adjectives",
      "chalk" not in T._shape_asset_keyword("large green chalk check mark beside x")
      and "green" not in T._shape_asset_keyword("large green chalk check mark beside x"))
check("cross -> Cross()", obj_of("large coral chalk cross over the composite leaf 6").startswith("Cross"))
check("'cross-section of a stem' is NOT a Cross",
      not obj_of("cross-section of a stem").startswith("Cross"))

# ── E. New diagram nouns map to sensible primitives ───────────────────────────
print("\n-- E. diagram vocabulary --")
for word, expect in [("node", "Circle"), ("panel", "Rectangle"), ("tray", "Rectangle"),
                     ("tile", "Rectangle"), ("block", "Rectangle"), ("oval", "Ellipse"),
                     ("branch", "Line"), ("connector", "Line"), ("star", "Star")]:
    check(f"'{word}' -> {expect}", obj_of(f"a {word}").startswith(expect))

# ── F. Entrance stays consistent with the object emitted ──────────────────────
print("\n-- F. object and entrance cannot drift --")
for content in ["Two chalk branches from 84 to circles containing 12 and 7",
                "four chalk tiles with motion arrows",
                "arrow pointing at X",
                "chalk starburst"]:
    expr, entrance = T._resolve_shape(content)
    call = T._build_entrance_call("shape", "", "v", content=content)
    if expr is None:
        ok = call.startswith("GrowFromCenter")  # falls back to the shape default
    else:
        ok = call.startswith(entrance[0])
    check(f"entrance matches object for {content[:38]!r}", ok)

print(f"\n{_passed}/{_passed + _failed} checks passed")
sys.exit(1 if _failed else 0)
