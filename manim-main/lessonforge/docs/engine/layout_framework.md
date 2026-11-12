# Layout Framework for Generated Manim Scenes

How we get the AI to lay out content like a human animator instead of piling
mobjects on top of each other. This documents the **progression** (v1 → v5),
the **patterns we borrowed from 3Blue1Brown's source**, and the **Layout Grammar**
the agents should follow.

---

## Why this exists

Manim does *no* automatic layout. `coords_to_point` doesn't clip, `next_to` anchors to
bounding-box corners, and nothing stops text from leaving the frame or overlapping.
([Manim #503](https://github.com/3b1b/manim/issues/503),
[CoordinateSystem docs](https://docs.manim.community/en/stable/reference/manim.mobject.graphing.coordinate_systems.CoordinateSystem.html))
So every spatial decision has to be made explicitly — either by the model or by us.

---

## Version history

### v1 — raw single-shot generation (original "IIT Mandi")
One Gemini call: storyboard → Manim code. No spatial reasoning.
**Observed failures (real renders):**
- Points plotted outside the axes range → drawn off-screen (e.g. `B(4,6)` on a `y_range=[-4,4]` axis).
- Equation/derivation stacks built with repeated `next_to(prev, DOWN)` from a `to_edge(DOWN)`
  anchor → walked off the bottom of the frame.
- Line labels placed with `next_to(line, UP+LEFT)` → landed at a bbox corner, far from the line.

### v2 — layout rules + Layout QA Critic (current, shipped)
- **5 frame-safety rules** injected into the generator prompt (frame bounds, group-before-position,
  verify-axis-bounds, midpoint label anchoring, screen-splitting).
- A dedicated **Layout QA Critic** second pass (`review_layout_with_gemini` / `ensure_layout` in
  `app/codegen.py`, toggle `LAYOUT_REVIEW`) that rewrites only spatial bugs and re-validates.
- Verified: on the v1 distance-formula failure the Critic widened the axis range, grouped+fitted the
  equation stack, midpoint-anchored the label, **and auto-applied a left-graph/right-text split** — then
  rendered to a valid MP4.

**Residual issues (the chemistry images that prompted v3):**
- **Equation token spacing** — coefficients rendered inside a single `Text` string overlap
  (`"2 H₂ + O₂ 2→ H₂O"`): there's no room reserved for the inserted `2`.
- **Text clutter** — too many simultaneous blocks (title + two misconception headers + two captions +
  two diagrams) collide because everything is shown at once on one screen.

### v3 — the Layout Grammar (this document; partially shipped)
Standardize *how content is constructed and revealed*, not just where it lands:
regions, equation-as-tokens, a screen budget, a sizing scale, and make-space-by-animation.

### v4 — content richness & accuracy (shipped)
Observed regression: for non-geometry topics (e.g. *Balancing Chemical Equations*) the storyboard
collapsed to ~2 elements/scene (a title + one text line) and was sometimes factually wrong (called a
balanced equation unbalanced). Fixes:
- **Storyboard prompt** gained a *Visual Richness — Show, Don't Tell* section (4–7 elements/scene,
  ≥2–3 non-text visuals, domain-specific diagram guidance) and a *Scientific Accuracy* section.
  Verified: chemistry storyboard went from 2 → 11–13 elements/scene with 3–5 shape elements.
- **Code prompt** gained rule 12 (*Visual fidelity*) + a few-shot diagram example (atoms as Circles
  grouped into molecules) so non-text elements render as real mobjects, not Text.
- **Text-density rule (7)** clarified to limit *text* only, so it no longer suppresses rich visuals.

Open: on the free `gemini-2.5-flash` model the *code* still under-draws diagram primitives (low
Circle/shape density, variable per run). The durable fix is a reusable drawing-helper module the agent
imports (e.g. `molecule()`, `vector()`), so rich diagrams don't depend on model strength — see roadmap.

### v5 — measured per-beat enforcement + overlap repair (shipped)
Everything through v4 acted at *authoring* time (prompts, critic, width-clamping) — nothing ever
**measured** what actually ends up on screen. Three gaps let overlapping content ship:
1. The dry-run assertion only checked *out-of-frame* on the **final** frame; text piled on
   un-faded text from a previous beat was invisible to the pipeline.
2. The dry-run ran `auto_fit_scene()` *before* measuring — but post-construct shifts never render
   (nothing plays after them), so the dry-run reported "clean" for videos that overlap on screen.
3. On a successful render, spatial warnings were informational only; nothing repaired them.

Fixes (all in the `app/` package):
- **Per-beat probe** (`_OVERLAP_PROBE_SNIPPET`, injected into the dry-run copy only): patches
  `Scene.play` and, after every beat, checks all text-like mobjects (Text/MarkupText/Paragraph/
  MathTex/Tex/DecimalNumber/BulletedList…) for
  (a) **text-on-text overlap** — both axes penetrated >0.05u AND intersection ≥15% of the smaller
  bbox (so glyph-grazes and intentional label-in-box don't fire), and
  (b) **clipped text** — between 5% and 85% visible at the frame edge (fully off-screen text is
  skipped: it's usually parked for a slide-in, invisible rather than broken), and
  (c) **text-over-shape** — a diagram's stroke path (axis line, circle outline, arrow tip)
  passing *through* the text's shrunk bbox, detected by sampling the shape's point polyline.
  The crossing test is what makes this false-positive-safe: text fully *inside* a box and text
  *beside* a curve never trip it; text struck through by a line does. Exemptions: shapes grouped
  under the same top-level root as the text (intentional label+box pairs), NumberPlane /
  ComplexPlane grids (backdrops), and z_index ≤ -50 (backgrounds). Visibility uses a
  family-aware opacity check (`MathTex.get_fill_opacity()` is 0.0 at the top level — only glyph
  descendants carry fill).
  Violations print as parseable lines with text excerpts, centers, and the beat number:
  `LAYOUT_VIOLATION: overlap Text('…') at [0.0,0.9] x Text('…') at [0.0,1.0] depth 8.11x0.40 after play#2`.
  Reports are deduped per pair and capped at 12. The probe fails open everywhere.
- **Measure-before-autofit**: the end-of-construct bounds report now runs *before*
  `auto_fit_scene`, so it reflects what the real render will show.
- **Overlap-repair post-pass** (`_repair_overlaps`, wired into both the single-clip
  `_run_render_job` and the master batch flow): when a render **succeeds** but violations were
  measured, the repair agent gets only the violation lines plus targeted guidance (FadeOut /
  `clear_canvas` between beats, `VGroup(...).arrange(...)`, TITLE_Y/BODY_Y bands, safe region)
  and the scene re-renders. A repaired version is accepted **only if it renders and reduces the
  violation count** — the original video is always kept as fallback, so the pass can improve a
  video but never lose one. Accepted fixes are stored in the repair RAG.
  Env knobs: `OVERLAP_REPAIR` (default `1`), `OVERLAP_REPAIR_ROUNDS` (default `2`);
  `LAYOUT_STRICT=1` additionally promotes dry-run violations to hard render failures.

Verified live (real Gemini): a deliberate two-beat overlap scene and a clipped-text scene each
resolved to zero violations in one repair round. Acceptance harness:
`python test_overlap_probe.py` (15 checks — detection true/false-positives through the production
`compile_manim_code` path, plus every accept/reject/fallback branch of the repair loop with the
LLM stubbed; no API keys needed). `test_layout_safety.py` still covers the deterministic
viz_helpers layer.

---

## What we took from 3Blue1Brown's source

Grant Sanderson's videos are 53K+ lines of analyzed Manim ([ManimBench/ManiBench],
[3b1b/videos](https://github.com/3b1b/videos), [3b1b/manim example_scenes](https://github.com/3b1b/manim/blob/master/example_scenes.py)).
Recurring patterns:

| Pattern | Idiom | Why it matters for us |
|---|---|---|
| **One concept per scene** | 4–16 short scenes, 30–90s each | Don't cram; clear the screen between ideas (fixes clutter) |
| **Title at top** | `title.to_edge(UP)` | Stable region for the heading |
| **Group then arrange** | `VGroup(a,b,c).arrange(DOWN, buff=LARGE_BUFF)` | Spacing is automatic; never hand-stack |
| **Corners for asides** | `note.to_corner(UR)` | Secondary info gets its own region |
| **Evolve equations in place** | `TransformMatchingTex` / `TransformMatchingStrings(a, b, matched_keys=[...])` | Inserting a coefficient *slides existing parts to make room* — the user's "animate to create space" idea, done natively |
| **Isolate equation parts** | `MathTex(r"{{2}} {{H_2}} + {{O_2}}")` | Parts become addressable for transforms/color |
| **Sizing scale** | `font_size=72` headline, `24–30` secondary, `set_width(FRAME_WIDTH-1)` | A consistent type hierarchy that fits the frame |
| **Color by key** | `t2c={"H_2": BLUE}` / `set_color_by_tex` | Highlight without extra mobjects |
| **`Group` not `VGroup` for `self.mobjects`** | `FadeOut(Group(*self.mobjects))` | `self.mobjects` may hold non-VMobjects (we already follow this) |

> Note: 3b1b runs **ManimGL** (his own fork) with `TransformMatchingStrings` and `MovingCamera`
> as defaults. We're on **Manim Community**; the equivalents are `TransformMatchingTex`
> (needs LaTeX, now installed) and `MovingCameraScene`.

---

## The Layout Grammar (v3 framework)

### 1. Screen regions
Every scene assigns content to named regions; regions never overlap.

```
┌───────────────────────────────────────────┐
│ TITLE            to_edge(UP, buff=0.5)       │  scale ~0.85
├───────────────────────────────────────────┤
│                                             │
│ STAGE  (main visual / diagram / axes)        │  centered; ≤ 12w × 5h
│        split into STAGE-L / STAGE-R when     │
│        a graph and text must coexist         │
│                                             │
├───────────────────────────────────────────┤
│ CAPTION          to_edge(DOWN, buff=0.5)     │  scale ~0.6, ≤ 2 lines
└───────────────────────────────────────────┘
```
- Title → `to_edge(UP)`. Caption → `to_edge(DOWN)`. Main content → center STAGE.
- If a graph **and** a derivation are both needed: STAGE-L = `axes.to_edge(LEFT)`,
  STAGE-R = `text_group.to_edge(RIGHT)`, each fitted to its half.

### 2. Equation construction standard (fixes coefficient overlap)
**Never** render an equation as one `Text` with inline coefficients and manual spaces — `Text`
won't reserve room for a prepended coefficient, so it overlaps.

- **Text-only path (current philosophy):** build the equation as a VGroup of token mobjects:
  ```python
  eq = VGroup(Text("2"), Text("H₂"), Text("+"), Text("O₂"), Text("→"),
              Text("2"), Text("H₂O")).arrange(RIGHT, buff=0.18)
  ```
  Spacing is automatic. To *add* a coefficient, build the balanced VGroup (which already reserves
  the space) and `ReplacementTransform(unbalanced_eq, balanced_eq)`, or `FadeIn` the new token while
  the arranged group holds the gap.
- **MathTex path (now available — LaTeX is installed):** use isolated parts and transform:
  ```python
  eq = MathTex(r"{{H_2}} + {{O_2}} \rightarrow {{H_2O}}")
  eq2 = MathTex(r"{{2}} {{H_2}} + {{O_2}} \rightarrow {{2}} {{H_2O}}")
  self.play(TransformMatchingTex(eq, eq2))   # parts slide to make room for the 2's
  ```
  This is exactly the "animate to create space" behavior, for free. **Open decision below.**

### 3. Screen budget & decluttering (fixes the chemistry clutter)
- Show at most **~6 elements / ~5 short text lines** at once.
- One idea per *beat*. When introducing the next idea, `FadeOut` the previous group first
  (or `Transform` it). Don't let title + multiple headers + multiple captions + multiple diagrams
  coexist.
- For "compare A vs B" scenes, give each its own half and a single shared caption — not four
  stacked text blocks.

### 4. Sizing scale & fit-to-region
- Title `scale 0.8–0.9`; body `0.6–0.7`; caption `0.55–0.6`.
- After placing a group, if it exceeds its region: `grp.set(width=region_w)` or
  `grp.set(height=region_h)`. Helper idiom: `grp.set(height=min(grp.height, 6.5))`.

### 5. Transitions = make space by animation
- Evolve an equation rather than redrawing: `TransformMatchingTex` / `ReplacementTransform`.
- Reveal sequentially (`LaggedStart`, successive `Write`s) instead of dumping everything.
- Between sub-topics: `FadeOut(Group(*things))` → next beat (a "new screen").

---

## Concrete agent rules (what lives in the prompt + Critic)

These are encoded in `LAYOUT_RULES` in `app/codegen.py` (generator prompt + Layout QA Critic checklist):
1. Frame bounds: keep content in x∈[-6.8,6.8], y∈[-3.7,3.7]; axes ≤ 12×6.
2. Group before positioning (VGroup + arrange + position once + fit).
3. Verify axis ranges contain every plotted point (≥1 unit margin).
4. Midpoint anchoring for line labels.
5. Screen-split graph vs. long text.
6. **Equations as arranged token VGroups (or MathTex), never one manual-spaced Text.**
7. **Screen budget: ≤ ~6 elements; one idea per beat; FadeOut before the next beat.**
8. **Sizing scale + fit-to-region.**

---

## Decision (made): `MathTex` enabled for equations

v1/v2 forbade `MathTex`/`Tex` to dodge LaTeX errors. **LaTeX is now installed and the render path is
green**, so as of v3 we **allow `MathTex` for equations/formulas only** — prose, titles, and labels
stay `Text` (Pango/Unicode). This unlocks the 3b1b idioms: `TransformMatchingTex`, native math spacing,
`{{ }}` part isolation, and `set_color_by_tex`.

Wired into the `app/` package:
- Both generator prompts now say: `Text` for prose, `MathTex` (with `{{ }}` parts) for equations, and
  evolve equations with `TransformMatchingTex` (parts slide to make room for inserted coefficients).
- The Layout QA Critic additionally checks for unbalanced `MathTex` braces / invalid LaTeX and any
  leftover `MarkupText` XML.

Residual risk: a malformed `MathTex` can still fail a render at LaTeX-compile time (the Python
auto-repair loop only catches *syntax* errors, not LaTeX errors). Captured in the render logs; a future
enhancement could detect LaTeX compile errors and run a targeted repair pass.

---

## Roadmap

- [x] v2 frame-safety rules + Layout QA Critic
- [x] v3 rules 6–8 (token equations, screen budget, sizing) in `LAYOUT_RULES`
- [x] MathTex enabled for equations + `TransformMatchingTex` idioms in both generator prompts + Critic checks
- [x] v4 storyboard visual-richness + accuracy; code visual-fidelity rule + few-shot diagram example
- [x] **Drawing-helper module** (`viz_helpers.py`: `atom`, `molecule`, `count_row`, `vector`, `labeled`),
      imported into every scene (staged next to the script + on PYTHONPATH). Verified: helpers render to
      MP4, and a generated chemistry scene used `atom()` 37× / `molecule()` 14× — rich diagrams without
      depending on model strength. Add more builders (cell, circuit, number line) as topics demand.
- [x] Programmatic bbox check — covered twice over: v5's per-beat overlap + clipped-text probe
      in the dry-run feeding a measured repair loop (`test_overlap_probe.py` is the harness), plus
      the transpiler's `[BBOX_CHECK]` block (below)
- [x] Text-over-diagram collisions — shipped in v5: stroke-crossing test with same-root /
      grid-backdrop exemptions as the intentional-label heuristic
- [x] **Transpiler animation-quality pipeline** (`transpiler.py` + `viz_helpers.py` + `app/`):
      Complete rewrite of `parse_schema_to_base_scene` as the sole code-generation path (no LLM per-block
      decoration). Items shipped:
  - [x] Elastic rate functions — `FadeIn(scale=0.1, rate_func=ease_out_elastic)` on text/svg/molecule; `GrowFromCenter` on shapes; `Write` on math
  - [x] Scene-start canvas clear — `FadeOut(*[m for m in self.mobjects if m is not _bg_image(self)])` before every scene after the first
  - [x] Voiceover-synced timing — `run_time=tracker.duration * 0.6` on all entrance plays
  - [x] Staggered group reveals — `AnimationGroup(..., lag_ratio=0.15)` when a cue introduces multiple elements simultaneously
  - [x] Same-zone collision detection — `_safe_zone_suffix()` tracks claimed zones per scene, redirects to best available fallback zone, shifts down as last resort; `_ZONE_FALLBACKS` dict encodes spatial priority
  - [x] Topological sort of elements — `_topo_sort_elements()` ensures `relative_positioning` targets are defined before the elements that reference them
  - [x] `math_evolution` element type — `FROM_LATEX → TO_LATEX` in `content` drives `Write(from)` entrance followed by `TransformMatchingTex(from, to)` for step-by-step equation transforms
  - [x] SVG sanitization — `_sanitize_svg_for_manim` strips gradients, filters, clipPath, mask, pattern; replaces `url(#...)` fill/stroke with white
  - [x] SVG keyword normalization — `_SVG_KEYWORD_NORM` (70+ STEM terms) + `_normalize_svg_keyword()` maps vocabulary like "velocity", "electron" to Iconify-compatible search terms
  - [x] Storyboard result caching — 48 h file-based cache keyed by `sha256(topic+persona+language+style+grade+subject+node_type)`; skips full LLM storyboard call on cache hit
  - [x] Scene count + cue density guidance — storyboard prompt enforces "4–6 scenes", "≤2 new elements per cue", "2–4 cues per scene"
  - [x] Parallel asset probing — `ThreadPoolExecutor(max_workers=min(N,10))` already present in `generate_code_impl`; confirmed no change needed
- [x] **LaTeX compile-error recovery** (`app/render.py`): `_LATEX_ERROR_MARKERS` in `_run_render_job` detects
      LaTeX errors in render logs and retries with `_strip_mathtex_to_text()` — deterministic
      MathTex→Text substitution, no LLM round-trip. Module-level function also used by `compile_manim_code`
      when `latex` is absent from PATH (replaces the former inline closure).
- [x] **Layout templates** (`transpiler.py` + `app/`): opt-in `layout_template` field on `StoryboardScene`
      (`"TitleStageCaption"` / `"SplitScreen"` / `"FullCanvas"`); `_apply_template_zones()` overrides
      `safe_zone_alignment` on elements that have no existing positioning. Templates described in the
      storyboard system prompt so the LLM picks the right one per scene.
- [x] **Post-render bbox check** (`transpiler.py` + `app/`): transpiler injects a `[BBOX_CHECK]` block
      at the end of every `construct`; any mobject whose bounding box extends outside `±frame_width/2` or
      `±frame_height/2` emits a `[BBOX_WARNING]` line to stderr. `_run_render_job` extracts these lines
      and stores them as `bbox_warnings` in the job dict — visible via `/api/render_status`.
