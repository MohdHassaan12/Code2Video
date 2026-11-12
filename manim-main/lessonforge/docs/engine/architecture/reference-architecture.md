# A Reference Architecture for AI-Native Educational Animation Systems

**The GyanSetu Video Engine specification — v1.0, 2026-07-21**

> **Status legend used throughout:** ● implemented and tested in this repo ·
> ◐ implemented, partially verified · ○ scaffolded stub (wired, disabled) ·
> ◇ specified here, not yet built.
>
> This document is a *specification grounded in a running system*, not a proposal.
> Every ● claim is anchored to a file in this repository and, where the design was
> earned rather than guessed, to the incident that taught it (the incident log lives
> in [docs/pipeline-roadmap.md](../pipeline-roadmap.md) §3–§3c). Aspirational layers
> are marked ○/◇ and specified precisely enough to implement without re-deriving the
> constraints.

---

## Table of contents

1. [Motivation](#1-motivation)
2. [System goals](#2-system-goals)
3. [Design principles](#3-design-principles)
4. [Information hierarchy — the IR ladder](#4-information-hierarchy--the-ir-ladder)
5. [Layered architecture](#5-layered-architecture)
6. [Internal data representations](#6-internal-data-representations)
7. [Agent ecosystem — formal specifications](#7-agent-ecosystem--formal-specifications)
8. [Compiler pipeline](#8-compiler-pipeline)
9. [Verification pipeline](#9-verification-pipeline)
10. [Memory architecture](#10-memory-architecture)
11. [Knowledge layer](#11-knowledge-layer)
12. [Component library](#12-component-library)
13. [Scene graph](#13-scene-graph)
14. [Timeline graph](#14-timeline-graph)
15. [Layout engine](#15-layout-engine)
16. [Animation engine](#16-animation-engine)
17. [Rendering layer](#17-rendering-layer)
18. [Vision QA](#18-vision-qa)
19. [Repair loop](#19-repair-loop)
20. [Scalability](#20-scalability)
21. [Extensibility — the Renderer Backend Contract](#21-extensibility--the-renderer-backend-contract)
22. [Comparison with existing system classes](#22-comparison-with-existing-system-classes)
23. [Formal system properties](#23-formal-system-properties)

Appendices:
[A. Formal IR schemas](#appendix-a--formal-ir-schemas) ·
[B. Agent prompts & protocols](#appendix-b--agent-prompts--communication-protocols) ·
[C. Scene DSL serialization rules](#appendix-c--scene-dsl-serialization-rules) ·
[D. Compiler passes](#appendix-d--compiler-passes) ·
[E. QA metrics & scoring](#appendix-e--qa-metrics--scoring) ·
[F. Benchmark suite](#appendix-f--benchmark-suite) ·
[G. End-to-end case study](#appendix-g--end-to-end-case-study-daltons-law)

---

## 1. Motivation

Educational video is the highest-bandwidth medium a tutoring system can emit, and the
hardest to generate correctly. A single 90-second explainer must simultaneously satisfy
constraints from five unrelated disciplines:

- **Pedagogy** — the right concepts, in the right order, at the right pace for the grade.
- **Narration** — spoken language matching the learner's linguistic register (here:
  Hinglish narration with English on-screen text, a *bilingual contract* most systems
  don't even model).
- **Graphic design** — legible layout, visual hierarchy, no collisions or clipping.
- **Animation** — motion that directs attention rather than decorating.
- **Programming** — an executable artifact (a Manim program) that actually compiles
  and renders.

The naive architecture — *prompt an LLM to emit Manim code* — collapses all five
disciplines into one token stream and fails on all five at once. This repository's
history is a controlled record of that failure and its resolution: every trap in
[CLAUDE.md](../../CLAUDE.md) and every graded gap in
[pipeline-roadmap.md](../pipeline-roadmap.md) is a place where an undifferentiated
generation step produced a defect that a *layer boundary* now prevents by construction.

The thesis of this architecture:

> **An AI educational video system is a compiler.** Pedagogical intent is the source
> language; the rendered, verified video is the target artifact; between them sits a
> ladder of intermediate representations, each owned by the component best suited to
> reason at that level — LLMs where judgment is required, deterministic code where
> structure is required, and measurement everywhere a contract must hold.

MVC separated presentation from state; the Transformer separated attention from
recurrence; LLVM separated language frontends from machine backends. The separation
this architecture contributes: **models own content, code owns structure, probes own
truth** — at every layer, enforced by gates.

---

## 2. System goals

**G1 — Correct mathematics on screen.** A point labeled (−3, 2) renders *at* (−3, 2)
in data space, not near it. (Violated by the pre-`c2p` transpiler — audit §3,
2026-07-19 — and now guaranteed by construction; see §15.)

**G2 — Legible composition, verified, not assumed.** No text-on-text overlap, no
clipped text, no text crossing a diagram's stroke. These are *measured* per beat by an
instrumented dry run (§9), not asserted by prompt engineering.

**G3 — The bilingual contract.** Narration in the persona's language (default:
romanized Hinglish); on-screen text in English. Enforced at the storyboard gate with a
metered self-heal and a deterministic backstop (§9, invariant P9).

**G4 — Never ship worse than what you have.** Every enhancement pass (repair, healing,
critique) may only improve or stand aside. A verified artifact is never lost (P1).

**G5 — Cost-bounded generation.** Every LLM/TTS call is a metered edge: routed by task
tier, cached content-addressed, and a cache miss is a *billing event*, not merely a
latency event (P4). Target: a repair re-render bills **zero** TTS calls (achieved —
`test_tts_shared_cache.py`).

**G6 — Debuggable at every boundary.** Each IR is serializable and inspectable
(storyboard JSON, generated scripts in `temp_renders/`, violation lines, `.mp4.json`
sidecars, `/timeline` badges). A failure names its stage (§9 routing).

**G7 — Renderer independence above the layout boundary.** Everything upstream of the
Layout Engine must survive replacing Manim with Blender, Three.js, SVG, or Unity
unchanged (§21).

**Non-goals (v1):** real-time generation; learner-adaptive branching mid-video;
photorealistic rendering; multi-speaker dialogue.

---

## 3. Design principles

Each principle below is a *law of the system* — later chapters cite them as P1…P10.
None of them is speculative: each was installed after a concrete regression, recorded
with the incident that taught it. This is deliberate methodology: **a principle earns
its place in the architecture by having been paid for.**

### P1 — Never lose a verified artifact
A candidate replaces the incumbent only if it (a) renders and (b) strictly reduces
measured violations. The incumbent survives every failed enhancement attempt.
*Embodied in:* the repair loop's accept-if-better gate (`app/render.py`,
`_repair_scenes_parallel` / `_repair_overlaps`); the storyboard heal that keeps the
original board when the heal fails (`normalize_onscreen_language`).
*Paid for by:* early repair rounds that shipped a worse video than the original.

### P2 — Code owns structure, models own content
The LLM never emits geometry, coordinates, animation timing, or program scaffolding.
It emits *meaning* (concepts, labels, narration, element intents); the deterministic
transpiler emits *form* (positions via zones and `c2p`, entrances via type maps,
timing via the `_TIMING` table).
*Paid for by:* the scene-vs-data coordinate bug — points visibly off-grid because the
LLM guessed scene coordinates for data-space objects (roadmap §D gap 1, fixed by
`c2p` emission by construction).

### P3 — A gate improves or stands aside
Every QC stage is non-fatal: on any internal failure it returns its input unchanged.
The pipeline's throughput is never hostage to its own quality machinery.
*Embodied in:* `PipelineStage` protocol contract (`app/pipeline/stages.py:50-67`);
the Layout QA critic; the storyboard heal.
*Exception, by design:* **pre-cache admission gates** (truncation, shape, language)
*do* block — because caching a bad artifact poisons every future request for 48 h.
Blocking at an admission boundary protects P1's economy; blocking mid-pipeline
violates it. Know which kind of gate you are writing.

### P4 — Every metered edge is routed, tiered, and cached
LLM and TTS calls are the only expensive edges. Each has a provider chain
(Gemini → OpenRouter → Groq, `app/llm.py`), a task tier (premium models only where
output quality depends on it), and a content-addressed cache where re-billing is
possible (storyboard cache, shared TTS cache). **A cache-key change is a billing
change** and reviews as one.

### P5 — Encode each quantity once
When two stages both encode the same quantity, the upstream one silently wins.
*Paid for by:* the Dalton length bug — the pedagogy planner sized a lesson at 1 scene
from source-text length while the storyboard prompt asked for 4–6; the upstream number
won and a 23.7 s video that never stated the law shipped (roadmap §B). *Rule:* before
tuning a stage, grep for the twin.

### P6 — Fallbacks must be loud
A working fallback is how a broken fast path hides. The parallel render path was dead
code in production for weeks because the sequential fallback silently produced fine
videos (roadmap §F4). Every fallback logs its own firing; every dropped event prints
`[TRANSPILER] dropped …`; a counter beats a log line.

### P7 — Losers are deleted
Every rejected candidate, superseded original, and orphaned clip is discarded
(`_discard_video`) by *the caller that created it*. Artifact hygiene is a per-caller
obligation, not a sweeper's job. *Paid for by:* `static/videos/` filling with
sidecar-less "Raw" mp4s that polluted the review timeline.

### P8 — Lenient parsing requires a completeness gate
`json_repair` closes a *truncated* model response into *structurally valid* JSON — a
failure-hiding device unless something independently checks completeness. Every
lenient parse is paired with a shape gate (`storyboard_shape_problems`) and a
`finish_reason == "length"` rejection at the provider layer.
*Paid for by:* a cut-off storyboard cached for 48 h that rendered as a 2.9 s video
with no error in any log (roadmap §B).

### P8a — A health metric must read zero on a healthy run
Corollary of P6 (loud fallbacks) learned 2026-07-22: the first `voice_degraded` counter
marked the Sarvam→Gemini hop as degradation, but this deployment has *no Sarvam key by
design*, so the counter would have been nonzero on 100% of videos. A signal that is
always firing is indistinguishable from no signal. Before trusting a new health metric,
check what it reports on a known-good run and separate *not configured* from *failed*.

### P9 — Enforce contracts upstream; keep a deterministic backstop downstream
The language contract is enforced at the storyboard admission gate (reject or heal),
*and* a deterministic Indic-strip backstop survives in codegen sanitize. The upstream
gate is a metered LLM call that can fail; the backstop is free and cannot. Neither
replaces the other.

### P10 — Guards must test the exact form they guarantee
`"from viz_helpers import" not in code` was satisfied by a *selective* import, silently
skipping both the star-import and the font injection keyed off it. Twice (the second:
an Indic-strip regex blind to `repr()`'s quote choice). A guard that checks a prefix
of the property it protects will be satisfied by a counterexample eventually.

---

## 4. Information hierarchy — the IR ladder

The system is organized as a lowering pipeline over typed intermediate representations,
exactly as LLVM lowers C through IR to machine code. Each IR is optimized for one class
of reasoning, and each lowering step is owned by the component best suited to it:

```
Educational Intent            (topic, grade, persona, grounding context)
      │  ce/video_planner + planner_agent        [LLM judgment: is a video needed? what shape?]
      ▼
Pedagogy IR                   (PARTS plan: scenes, objectives, pacing, wpm)
      │  app/storyboard.generate_storyboard_impl  [LLM judgment: what to show and say]
      ▼
Storyboard IR  ── THE canonical, renderer-independent DSL (app/schemas.py)
      │  admission gates: truncation, shape, language (+ heal)   [measurement]
      │  ○ Visual Director annotations (hierarchy, lifetime, camera, highlight)
      ▼
Layout IR                     (zone claims, label slots, split-screen decisions)
      │  transpiler.py — deterministic            [code owns structure]
      ▼
Animation IR                  (entrance classes, timing fractions, event stream)
      │  transpiler.py — deterministic
      ▼
Render IR                     (Manim programs: one master + N per-scene scripts)
      │  compile + instrumented dry-run probe     [measurement]
      ▼
Verification IR               (LAYOUT_VIOLATION lines; .mp4.json sidecar)
      │  repair loop (accept-if-better)           [LLM judgment, code-gated]
      ▼
Verified video artifact       (mp4 + sidecar + /timeline badge)
```

Three structural facts about this ladder do the architectural work:

1. **Judgment and structure alternate.** Every LLM step is followed by a deterministic
   or measured step that bounds its damage. No LLM output reaches an expensive
   operation (render, TTS, cache write) unexamined.
2. **The Storyboard IR is the waist of the hourglass** — the narrowest, most stable
   interface, exactly like LLVM IR. Everything above it is renderer-agnostic pedagogy;
   everything below it is backend. Extensibility (§21) is defined as: *new backends
   attach at the waist.*
3. **Information is only added, never re-derived.** Each layer adds one class of
   information (pedagogical shape → visual meaning → geometry → motion → executable
   form → measured truth). A layer that re-derives an upstream quantity creates a P5
   violation; the architecture forbids it.

Layer-by-layer treatment of *what information is created* is in §6; *why each layer
cannot be merged into its neighbors* is argued per layer in §5–§19.

---

## 5. Layered architecture

### 5.1 The stack

The running system realizes the ladder as ten stages
(`stem_animation_lab/app/pipeline/stages.py:10-21` — the authoritative sequence):

| # | Stage | Owner | Kind | Status |
|---|-------|-------|------|--------|
| 1 | Pedagogy Planner | `ce/planner_agent.py` (PARTS) | LLM | ● |
| 2 | Storyboard Generator + admission gates | `app/storyboard.py` | LLM + code gate | ● |
| 3 | Visual Director | `app/pipeline/director.py` | LLM annotator | ◐ |
| 4 | Layout Engine | `transpiler.py` (zones, `c2p`, slots) | deterministic | ● |
| 5 | Animation Planner | `transpiler.py` (`_ENTRANCE_CONFIG`, `_TIMING`) | deterministic | ● |
| 6 | Component Retrieval | `app/rag.py` + `viz_helpers.py` | code + cache | ● |
| 7 | Codegen / Compiler | `app/codegen_pipeline.py` → `app/render.py` | deterministic + LLM critic | ● |
| 8 | Static Validator (probe) | `app/render.py` dry-run | measurement | ● |
| 9 | Vision QA | `app/pipeline/vision_qa.py` | vision LLM | ◐ |
| 10 | Repair Agent | `app/render.py` repair loops | LLM, code-gated | ● |

Two deployment units: the **`ce/` client** (lesson orchestration, stages 0–1, HTTP
client) and the **lab server** (`stem_animation_lab/`, stages 2–10, FastAPI on :5000).
The HTTP boundary between them is itself an architectural statement: the lesson system
and the video engine share *no* code, only the Storyboard-IR-shaped API
(`/api/generate_storyboard` → `/api/generate_code` → `/api/compile_video`), which is
what makes the engine reusable by any client (bulk runner, debugger, future systems).

### 5.2 Why the layer boundaries sit where they do

Each boundary exists because the reasoning on its two sides has a different *owner
type* (judgment vs. structure vs. measurement), a different *failure mode*, or a
different *cost profile*. Merging across any boundary re-creates a recorded failure:

- **1 | 2 (pedagogy vs. storyboard):** both are LLM judgment, but at different grains
  (lesson-level pacing vs. scene-level visuals) and different billing scopes. Merging
  them re-creates the P5 incident where two stages encoded lesson length.
- **2 | 4 (storyboard vs. layout):** the load-bearing boundary of the whole system —
  meaning vs. geometry. Every recorded geometry bug (off-grid points, labels through
  tick numbers, y-axis through title text, particles outside their container) traces
  to the LLM leaking across this boundary. The transpiler exists to make the leak
  structurally impossible.
- **4 | 5 (layout vs. animation):** both deterministic, kept as separate passes over
  the same IR because layout is *spatial* constraint satisfaction and animation is
  *temporal* — they compose (an entrance animates *into* a zone-assigned position)
  but never inform each other's decisions, so they must not share state.
- **7 | 8 (codegen vs. validation):** the generator must never grade its own output.
  The probe is an independent auditor with its own measurement code path
  (patched `Scene.play`), which is why it catches classes the generator believes
  it prevented.
- **8 | 10 (measurement vs. repair):** measurement is free and deterministic; repair
  is metered and stochastic. Fusing them (a "self-healing renderer") loses the
  accept-if-better gate that P1 requires.

### 5.3 Control flow vs. data flow

Control flow is a straight pipeline with two loops: the **repair loop** (10 → 7 → 8,
bounded by `OVERLAP_REPAIR_ROUNDS`, default 2) and the **provider-fallback loop**
inside every LLM call. Data flow is strictly forward along the IR ladder; the only
backward-flowing information is *Verification IR* (violation lines) entering the
repair prompt, and *error fingerprints* entering the RAG memory (§10). Nothing else
flows upstream at runtime — upstream improvement happens offline, through the
roadmap's attribute-upstream-first discipline (§9.4).

---

## 6. Internal data representations

Every IR below states: what it is, the mathematical object it encodes, the invariants
that must hold on exit, where it is serialized, and how it is validated. Formal JSON
Schemas for the machine-checked IRs are committed under
[`stem_animation_lab/schemas/`](../../stem_animation_lab/schemas/) and drift-gated by
`test_ir_contracts.py` (Appendix A).

### 6.1 Educational Intent

**Definition.** The tuple the system accepts from the outside world:

```
Intent = (topic, subject, grade, node_type, persona, language, speaker, style,
          grounding_context?)
```

Persona/language resolution is a strict precedence chain — per-node `videoSpec` →
`VIDEO_LANGUAGE`/`VIDEO_PERSONA`/`VIDEO_SPEAKER`/`VIDEO_STYLE` env → hardcoded
`hi-IN`/`hybrid` (`ce/stem_animation.py`) — the tail of which is why the system
defaults to Hinglish narration.

**Invariant on exit:** intent is *complete* — every downstream stage reads these
fields and none may invent a missing one (P5).

**Validation:** structural only; intent is trusted input.

### 6.2 Pedagogy IR

**Definition.** The PARTS lesson plan (`ce/planner_agent.py`): scene count, per-scene
objectives, narration pace.

**Mathematical model.** A sequence of scene intents `⟨p₁…pₙ⟩` with a pacing function
`wpm: grade → words/minute` and the floor `n ≥ MIN_LESSON_SCENES = 4`.

**Invariants on exit:**
- **PI-1:** `n ≥ 4` regardless of source-text length — a concept always gets hook →
  statement → example → recap. (The floor *is* the fix for the Dalton 1-scene bug;
  it aligns the planner with the storyboard stage's own stated target rather than
  encoding a second, competing length rule — P5.)
- **PI-2:** `wpm` is resolved by grade *number* match, in exactly one implementation
  (`planner_agent.narration_wpm()`, called by `ce/stem_animation.py` — the substring
  bug where `"grade 1" in "grade 11"` narrated teenagers at 90 wpm is why the single
  implementation rule exists).

**Why a separate layer:** lesson-level pacing decisions are made once per video and
bill once; scene-level visual decisions bill per scene. Merging them couples billing
scopes and re-creates the dual-encoding incident.

### 6.3 Storyboard IR — the canonical Scene DSL

The system's waist. Typed by Pydantic models in
[`app/schemas.py`](../../stem_animation_lab/app/schemas.py) (`StoryboardResponse`);
formal JSON Schema exported to `schemas/storyboard-ir.schema.json`.

**Definition.**

```
Storyboard  := (topic, key_theorems[], key_terms[], style_profile, aspect_ratio,
                scenes: Scene[])
Scene       := (scene_index, description, elements: Element[],
                narration_cues: Cue[], wait_time, layout_template?)
Element     := (id, type, content, color?, entrance_animation, exit_animation,
                scale?, position: Position)
Position    := AbsolutePosition([x,y])            -- shapes / coordinate systems only
             | RelativePosition(relative_to: id, direction, buffer)  -- anchored labels
             | SafeZone(TOP_CENTER | BOTTOM_CENTER | TOP_LEFT | TOP_RIGHT
                        | LEFT_CENTER | RIGHT_CENTER)                -- standalone text
Cue         := (cue: narration text, animation_events: Event[]?, event: legacy free-text)
Event       := (action: show|hide|transform|highlight|move_to,
                target: id, to?: id, color?, direction?)
```

Element `type` ∈ {`text`, `math`, `shape`, `svg_icon`, `chemical_molecule`,
`coordinate_system`, `graph`, `math_evolution`}.

**Mathematical model.** A storyboard is an ordered forest of **scene graphs** (§13)
paired with a **timeline graph** (§14): per scene, elements are nodes; typed edges are
*anchoring* (from `relative_positioning.relative_to`) and *morphing* (from
`transform`/`math_evolution`); cues impose the temporal order.

**Invariants on exit (the admission gates, `app/storyboard.py`):**
- **SB-1 (completeness, P8):** ≥1 scene; every scene has ≥1 cue; no cue ends inside a
  pacing tag. Enforced by `storyboard_shape_problems()` *before* the cache write.
- **SB-2 (language contract, G3):** under hybrid/en persona, no Devanagari in
  `text`/`math` element content (healed by `normalize_onscreen_language` — a heal is
  accepted only if it actually removed the Indic script, P1), and narration is not
  entirely plain English (≥1 cue carries Devanagari or a romanized-Hindi function
  word).
- **SB-3 (positioning discipline):** every element carries exactly one positioning
  strategy; standalone text uses safe zones, anchored labels use relative
  positioning, only shapes and coordinate systems may use absolute coordinates.
  (Pydantic-typed; the transpiler additionally treats any absolute position on
  axes-hosted content as data-space input for `c2p` — P2.)
- **SB-4 (referential integrity, scoped):** event targets should name elements of the
  same scene. Cross-scene references are *legal in the IR* (the master render shares
  one namespace) but are dropped at per-scene lowering (§6.7) — the rule that fixed
  the 3-of-4-scenes NameError cascade.

**Serialization:** JSON, cached content-addressed (§10.1).

**Known impurity (flagged for v1.1):** `entrance_animation`/`exit_animation` are
documented in Manim vocabulary ("FadeIn", "Write"). The transpiler already treats
them as *hints* that its own type-keyed entrance map may override (§16), so the field
is semantically renderer-neutral (an intent vocabulary), but the schema description
leaks backend names. The Renderer Backend Contract (§21) requires each backend to
supply the vocabulary mapping; renaming to abstract intents (`appear`, `draw`,
`grow`) is scheduled with the next schema version bump.

### 6.4 Directed Storyboard IR ◐

The Visual Director (§7, stage 3) annotates — never restructures — the storyboard.
**Implementation note (2026-07-21): the annotations are realized as *ordinary
Storyboard-IR constructs*** — scale-field adjustments for hierarchy, appended standard
`hide`/`highlight` events for lifetime and semantic highlighting — so the transpiler
consumes them with zero new vocabulary and strip-invariance holds by construction.
The abstract directive forms below remain the design target for the camera directives
(not yet expressible as plain IR):

```
Directive := hierarchy(id → primary|secondary|tertiary)     -- font/z tiers
           | lifetime(id → birth_cue, death_cue)             -- nothing lingers
           | camera(cue → zoom|pan|dim_unrelated|spotlight)
           | highlight(cue → id)                             -- glow what narration names
```

**Invariant:** a directed storyboard with all directives stripped is byte-identical
to its input — annotations are a *refinement*, so the stage can stand aside (P3) and
the transpiler treats every directive as optional. The embryonic implemented pieces
are `layout_template` and the split-screen manager (`_maybe_minimize_diagram`); the
director centralizes them.

### 6.5 Layout IR

The transpiler's internal spatial model — never serialized as a user artifact, but a
real representation with real invariants (fully specified in §15):

```
Frame   := [-7.1, 7.1] × [-4.0, 4.0] scene units (widescreen)
Zones   := the six named safe zones, each with a claim state and a fallback chain
Claims  := zone → element | AXES_FOOTPRINT | free
Slots   := label → direction flip decisions (away from tick strips)
Split   := per-cue screen-management decision (diagram → left half, text → right column)
```

**Invariants on exit:** LI-1 no two claimed zones overlap; LI-2 no text zone
intersects the axes' estimated bbox (`_seed_axes_zones` pre-claims every zone the
axes footprint touches); LI-3 zone stacking shifts *toward frame center* (a BOTTOM
stack once walked off-screen); LI-4 a label anchored to axes-hosted geometry never
sits over a tick strip (`_fix_label_slots`).

**Validation:** `test_axes_zones.py` (14 checks) + the probe as independent auditor.

### 6.6 Animation IR

The temporal plan, also internal to the transpiler (§16):

```
Entrance := element → animation class        (_ENTRANCE_CONFIG by type,
                                              _SHAPE_ENTRANCES by content keyword)
Timing   := element → seconds                (_TIMING: per-type fraction + floor,
                                              capped at the narration beat)
Events   := cue → ordered animation calls    (batched FadeOuts, sequenced others)
```

**Invariants:** AI-1 the entrance class always matches the object actually emitted —
keyword precedence deliberately mirrors `_build_obj_expr` ("arrow pointing at X"
builds a Dot and must not `GrowArrow`); AI-2 no entrance exceeds its narration beat;
AI-3 schema-specified animations win over the type map (author intent is a refinement).
**Validation:** `test_entrance_map.py` (14 checks, both codegen paths must agree).

### 6.7 Render IR

**Definition.** Executable Manim programs: one **master script** (all scenes in a
single `construct()` namespace) plus **N per-scene scripts** for the parallel path.
Serialized to `temp_renders/` — the IR *is* inspectable Python, deliberately.

**The isolation rule (the hard-won one):** a per-scene script is a *closed world* —
it contains only its own scene's `id→var` map, and both emitters fall back to the raw
storyboard id on a miss. Therefore lowering to per-scene form must drop cross-scene
events (`_drop_cross_scene_events` for structured events,
`_drop_foreign_id_calls` for legacy free-text) — loudly, to stderr — while the master
script *keeps* them (legal in a shared namespace). Both behaviours are contractual;
`test_event_sanitize.py` pins both directions.

**Invariants on exit:**
- **RI-1 (executability):** the program parses (AST-validated); every free-text event
  fragment is either a whitelisted animation call / `.animate` chain or was dropped
  (`_sanitize_anim_calls` — model prose never reaches `self.play`).
- **RI-2 (import exactness, P10):** the `viz_helpers` star import is present in
  normalized form; `config.font` injection keyed off it has fired.
- **RI-3 (cue body):** a cue emptied by event-dropping still gets a body (a wait) —
  beat structure survives sanitization.

**Validation:** `test_event_sanitize.py` (20), `test_minimize_split.py` (20),
syntax validation in `app/codegen.py`.

### 6.8 Verification IR

The measured truth about an artifact — two forms:

**(a) Violation stream** — parseable lines emitted by the probe
(`_OVERLAP_PROBE_SNIPPET`, §9.2):

```
LAYOUT_VIOLATION: <class> beat=<n> <details>
   class ∈ { text-on-text overlap, clipped text at frame edge, text-over-shape }
```

**(b) Sidecar** — `<video>.mp4.json` written next to every rendered artifact
(`app/jobs.py:_write_video_sidecar`): required `job_id`, `repair_rounds`,
`violations_remaining`; plus `animation_beats`, (parallel path) `scenes_repaired`,
`vision_findings` (§18 — counted separately from geometric violations), and
`voice_degraded` (§7.5a — cues that shipped on a fallback voice).
Ephemeral run state (`state`, `success`, `logs`, `render_duration_seconds`,
`bbox_warnings`) lives in the job store, *not* the sidecar — the sidecar is the
durable half (§10.3). Schema: `schemas/render-verification-ir.schema.json`.

**Invariants:** VI-1 every shipped video has a sidecar (a sidecar-less mp4 *is* the
detection signal for an artifact-hygiene bug — the /timeline "Raw" badge); VI-2
`violations_remaining` describes the *shipped* file, post-repair (the `[Scene N]`
log prefix is rebuilt from post-repair logs for exactly this reason); VI-3 the
sidecar travels with the artifact — `_discard_video` deletes both or neither.

**Why an IR and not just logging:** the repair loop *parses* violation lines to build
its brief (`_overlap_error_report`), the timeline UI *renders* sidecars as badges,
and the roadmap's grading audits *cite* them as evidence. Three consumers ⇒ a
contract, not a log format.

---

## 7. Agent ecosystem — formal specifications

Every agent is specified on the same template: Purpose · Inputs · Outputs · State ·
Knowledge required · Reasoning strategy · Failure modes · Recovery · Metrics ·
Complexity · Status · Planned evolution. "Agent" here means *any stage with an owner*,
LLM-backed or deterministic — the deterministic ones are agents whose policy happens
to be frozen into code, which is exactly the point of P2.

### 7.1 Pedagogy Planner ●

- **Purpose:** decide whether a lesson node needs a video and shape it (type,
  objective, duration, scene count, pace).
- **Inputs:** Educational Intent + node contents.
- **Outputs:** Pedagogy IR (`{needed, type, objective, duration}` + scene plan).
- **State:** stateless per call.
- **Knowledge:** PARTS pedagogy framework; grade→wpm table (single implementation,
  PI-2).
- **Reasoning strategy:** one premium-tier LLM call with key-normalization on the
  response (`needsAnimation`/`animationNeeded` → `needed`); offline stub maps node
  types (`hook`/`reveal`/`concept`/`simulation`/`recap`) to default 45 s specs.
- **Failure modes:** (F1) sizing the lesson off source-text *length* — the recorded
  Dalton failure, now floored by `MIN_LESSON_SCENES=4`; (F2) provider outage.
- **Recovery:** F2 → offline stub (loud, P6).
- **Metrics:** scene count distribution; % nodes gated to "no video".
- **Complexity:** O(1) LLM calls per node.
- **Planned:** a deck-brief + running-summary thread (roadmap §B) so scene k knows
  what scenes 1…k−1 established.

### 7.2 Storyboard Generator ●

- **Purpose:** lower pedagogy into the Storyboard IR — what the learner sees and
  hears, scene by scene, cue by cue.
- **Inputs:** Pedagogy IR, grounding context (3-tier: explicit URL → transcript
  search → NCERT node text), persona/style.
- **Outputs:** Storyboard IR (post-gate, post-heal).
- **State:** content-addressed cache (§10.1) — the *only* stage output cached across
  runs with a TTL.
- **Knowledge:** layout-framework prompt rules (visual richness, accuracy, scene-count
  and cue-density guidance); the bilingual contract.
- **Reasoning strategy:** single structured-output LLM call → lenient parse →
  **admission gates** (SB-1..SB-2) → heal → cache write. Truncation is rejected at
  the provider layer first (`finish_reason=="length"` falls through the chain, P8).
- **Failure modes:** (F1) truncation closed into valid JSON by `json_repair` —
  gated; (F2) language inversion (English cues + Devanagari screen — the exact
  Dalton §3c shape) — gated + healed; (F3) fallback model emits a clean-but-empty
  board (deepseek, observed live) — gated, but the gate currently runs *outside*
  the provider-fallback loop, so this 500s instead of retrying the next model
  (open weakness, roadmap §3b); (F4) prose in `event` fields — tolerated here,
  sanitized at lowering (RI-1), logged as upstream signal; (F5) **a non-`stop`
  finish reason** — a live call returned `finish=error, completion_tokens=0` and was
  *accepted* because the provider check tested only `length`; the partial board
  reached the shape gate two stages later. Now `error`/`content_filter` are rejected
  at the provider too, so the chain's next model gets a turn. The generalization is
  P8's real statement: **any terminal reason that isn't `stop` means the model did
  not finish, however well-formed its JSON parses.**
- **Recovery:** heal for on-screen language (accept only if Indic removed, P1);
  loud 500 for narration inversion (no code-owned romanizer exists — inventing
  Hinglish is a content decision, not a normalization).
- **Metrics:** gate rejection rate by class; heal success rate; cache hit rate;
  completion-token distribution vs. `LLM_MAX_TOKENS` (16000 — raised from 8000
  after a live boundary flake).
- **Complexity:** O(1) LLM calls per video (+1 heal call when triggered).
- **Planned:** move the shape gate inside the provider-fallback loop; `SCOPE_VERSION`
  cache-key field so a prompt fix can invalidate selectively (P4).

### 7.3 Visual Director ◐ (`VISUAL_DIRECTOR=1`, implemented 2026-07-21)

- **Purpose:** the composition decisions the storyboard doesn't make — visual
  hierarchy, object lifetime, camera language, semantic highlighting — emitted as
  Directed-Storyboard annotations (§6.4) that the *transpiler* acts on. The LLM
  decides *importance*; code decides *pixels* (P2).
- **Inputs:** Storyboard IR. **Outputs:** Directed Storyboard IR.
- **State:** stateless. **Knowledge:** attention/hierarchy design rules.
- **Failure modes:** over-direction (annotating everything primary), contradictory
  lifetimes (death before birth). Both are *validatable in code* before acceptance —
  the stage's output is annotations, so a validator can reject bad direction and
  stand aside (P3) without losing the board.
- **Recovery:** strip annotations → pipeline proceeds undirected.
- **Metrics:** stale-object count per scene (the recurring overlap source lifetime
  direction should eliminate); % elements ranked non-primary; per-scene applied/
  rejected counts (the `[DIRECTOR] applied:` log line).
- **Status (2026-07-21/22):** implemented — hierarchy (scale tiers, axes/graphs
  exempt), lifetime (safety-gated appended `hide` events), semantic highlighting
  (capped `highlight` events), and **camera language** as one `focus` spotlight per
  scene (§16.1). Called from `codegen_pipeline.generate_code_impl` before any codegen
  path reads the board. Pinned by `test_director.py` (33 checks).
- **Two halves, two failure semantics (the design worth copying):** the stage runs a
  **deterministic** pass first (`_enlarge_sparse_scenes` — the dead-frame fix: a
  scene with ≤4 elements and no axes gets every scale ×1.3, clamped at 1.4) and then
  a **best-effort LLM** pass. Pure code cannot fail, so the deterministic half applies
  even when the model is unreachable; "stand aside" scopes to the *judgment*, not to
  the whole stage. A stage that mixes free and metered work should split them this way.
- **Live evidence:** refraction board (6 scenes) — 40 rescaled, 14 highlights, 3 unsafe
  proposals rejected, 0 hides proposed; optical-fibre board (5 scenes) — enlarge-to-fill
  scaled 3 elements in sparse scenes, then 30 rescaled, 2 hides, 12 highlights, 0 focus,
  15 proposals rejected. Watch items: the model proposes `focus` rarely (0 on both
  boards — the prompt tells it to omit rather than force one), and the rejection count
  is high enough to be worth sampling if it grows.

### 7.4 Layout Engine ● (deterministic — full treatment §15)

Purpose: assign every element a collision-free position. Inputs: (Directed)
Storyboard IR. Outputs: Layout IR. Failure modes and recovery are *by construction* —
the engine cannot emit an unclaimed-zone conflict; residual risk is delegated to the
probe. Metrics: probe violations per video attributable to layout (A/B evidence:
4 → 0 on the raised-axes fixture). Complexity: O(elements × zone-chain length).

### 7.5 Animation Planner ● (deterministic — full treatment §16)

Purpose: give every element idiomatic, narration-synchronized motion. Inputs: Layout
IR + cues. Outputs: Animation IR. Metric: distinct entrance classes per mixed-type
scene (≥4 pinned; note a text-heavy storyboard *should* look FadeIn-dominated — the
content mix, not the map). Complexity: O(elements + events).

### 7.5a Narration Synthesis (TTS) ● — resilience contract

Not a stage in its own right (it runs inside the render), but it owns the system's
most expensive metered edge and its own failure semantics, added 2026-07-21 after a
live provider outage killed a render:

- **Retry before failover.** `_tts_post_with_retry` treats 5xx / 429 / transport
  timeouts **and `200 OK` with an empty body** as transient (that last shape is what
  the outage actually produced) and retries with linear backoff; 401/400 fail
  immediately, since retrying a bad key only adds latency.
- **The chain ends keyless.** primary → Gemini (keyed) → **gTTS (no key)** → silence.
  The keyless tier is a different vendor on a different network path, so a
  keyed-provider outage cannot take it down too.
- **Degradation is never silent** (the P1 corollary for *quality*, not just
  existence): each fallback tier prints `TTS_DEGRADED: <tier>` from the manim
  subprocess, counted into the sidecar as `voice_degraded`. Silence is opt-in and
  **off by default** — a render that fails gets retried; a silent video gets
  published, so failing loudly is the safer default.
- **Cost invariant preserved:** the shared TTS cache (§10.2) is keyed on request
  *intent*, so a fallback-synthesized clip still satisfies identical future requests
  and a repair re-render still bills zero.

### 7.6 Component Retriever ●

- **Purpose:** resolve non-primitive visuals — SVG icons (Iconify + sanitize:
  gradients/filters stripped), chemical molecules (RDKit from SMILES), backgrounds.
- **Inputs:** element type + content keyword. **Outputs:** render-ready assets +
  preflight substitution notes.
- **State:** keyword-named asset cache (upgrade planned: content-addressed +
  per-asset provenance in the sidecar).
- **Knowledge:** 106-entry STEM keyword normalization map
  (`viz_helpers._normalize_svg_keyword`).
- **Failure modes:** unresolvable keyword → preflight `failed_assets` guard →
  degrade to primitive shape rather than a broken render.
- **Metrics:** preflight failure rate; substitution-note frequency.

### 7.7 Codegen / Compiler ● (full treatment §8)

The deterministic transpiler plus its LLM adjuncts (Layout-QA critic rewrite pass,
syntax/logic validate-and-repair, LaTeX→Text self-heal). The transpiler is the sole
full-scene codegen path; the critic may *rewrite*, never *originate* structure.

### 7.8 Static Validator (probe) ● (full treatment §9.2)

Measurement, not judgment: an instrumented, TTS-stubbed dry run that patches
`Scene.play` and measures after every beat. Free, deterministic,
false-positive-safe by design (family-aware visibility; container point/submobject
duality; backdrop exemptions for `NumberPlane`/`ComplexPlane`).

### 7.9 Vision QA ◐ (`VISION_QA=1`, implemented 2026-07-21 — full treatment §18)

The pixel reviewer for defect classes geometry cannot see (contrast, sparse frames,
broken hierarchy, unreadability). Contract: emit `LAYOUT_VIOLATION: vision-<class>`
lines in the probe's line format (a distinct class namespace, so the geometric
matcher never double-counts them). Implemented: ffmpeg frame sampling → one
multimodal call → whitelist/shape-gated findings; sequential-path repair is
accept-if-better with a geometric non-regression guard; parallel path reports into
the sidecar (`vision_findings`) — scene-scoped vision repair is the v1.1 follow-up.
Pinned by `test_vision_qa.py` (19 checks).

### 7.10 Repair Agent ● (full treatment §19)

- **Purpose:** fix measured violations in Render IR without ever shipping a
  regression.
- **Inputs:** offending script + `_overlap_error_report(violations)` brief.
- **Outputs:** candidate script → candidate artifact → accept/reject.
- **State:** error→repair pair memory (ChromaDB, §10.4) — write-side wired.
- **Reasoning strategy:** premium-tier LLM rewrite scoped to the violation brief;
  **two implementations, one contract** — `_repair_scenes_parallel` (per-scene:
  only flagged scenes re-render) and `_repair_overlaps` (whole-video, sequential/
  batch path).
- **Failure modes:** candidate doesn't render; candidate renders but doesn't reduce
  violations; repair LLM unavailable.
- **Recovery:** all three → keep incumbent (P1), delete loser (P7), record honestly
  in the sidecar (`violations_remaining > 0, repair_rounds > 0`).
- **Metrics:** acceptance rate per round; violations before/after; sidecar
  truthfulness (VI-2).
- **Complexity:** ≤ `OVERLAP_REPAIR_ROUNDS` × (LLM call + re-render of *flagged
  scenes only*).

### 7.11 Inter-agent protocol

Agents communicate **only through IRs** — there is no shared blackboard, no agent
messaging, no conversational state. `PipelineContext`
(`app/pipeline/stages.py:29-47`) is the typed envelope a future orchestrator threads
through the stages; today production calls stage functions directly and the context
documents the shape. This is deliberate: IR-mediated communication is what makes
stages independently testable (every harness stubs its neighbors at an IR boundary)
and independently replaceable (§21).

---

## 8. Compiler pipeline

The transpiler (`stem_animation_lab/transpiler.py`) is a real multi-pass compiler
over the Storyboard IR. Passes in order (Appendix D tabulates them):

1. **Normalization** — SVG keyword normalization; content parsing (axis ranges from
   `'x:MIN-MAX, y:MIN-MAX'`; `math_evolution`'s `FROM → TO` split).
2. **Scene-graph construction & topo-sort** (§13) — elements ordered so every
   anchor target exists before its dependents.
3. **Zone seeding** — `_seed_axes_zones` pre-claims every safe zone the axes'
   estimated footprint touches (LI-2).
4. **Placement lowering** — safe-zone → concrete coordinates with fallback chains
   and center-shifting stacks; relative positions → `next_to` with slot-flipped
   directions (`_fix_label_slots`); axes-hosted content → `c2p(x, y)` (P2's
   flagship: **the data-space contract**).
5. **Screen management** — `_maybe_minimize_diagram`: when a cue piles free-standing
   text onto an on-screen diagram (any `math`, or ≥2 text-ish elements; never cue 0;
   never diagram-anchored labels), shrink the diagram to the left half and stack the
   text in a right column.
6. **Animation lowering** — entrance/timing maps (§16); event stream compilation
   with FadeOut batching.
7. **Event sanitization** — AST-parse every legacy free-text fragment; keep only
   whitelisted animation calls and `.animate` chains (RI-1); drop loudly.
8. **Per-scene splitting** — closed-world scripts with cross-scene event dropping
   (§6.7); the master script keeps the shared namespace.
9. **Code sanitize** (in `app/codegen.py`) — star-import normalization + font
   injection (RI-2/P10); Indic-strip backstop (P9); LaTeX fallback markers.

**Correctness argument (why "layout-by-construction" is the right altitude):** every
class the probe historically caught most often is now *unrepresentable* in the
transpiler's output — off-grid geometry (pass 4), axis-through-text (pass 3), label
on tick strip (pass 4), text pile-up (pass 5), prose in `play()` (pass 7), cross-scene
NameError (pass 8). The probe remains as independent auditor precisely because
"unrepresentable" is a claim about the emitter, and P10 says claims get verified by
something that isn't the claimant.

**LLM adjuncts, bounded:** the Layout-QA critic (rule-driven rewrite pass) and
validate-and-repair may transform the emitted program but are gated by the same
verification pipeline as everything else; `skip_layout_review` exists because the
critic is P3-optional.

---

## 9. Verification pipeline

Defense in depth: five gate families, each catching what the previous cannot see,
each placed at the *earliest* boundary where its defect class is decidable.

| Gate | Boundary | Decides | Class caught | Fatal? |
|---|---|---|---|---|
| Provider gate | inside every LLM call | `finish_reason != "length"` | truncation before lenient parsing can hide it | falls to next model |
| Admission gates | storyboard → cache | SB-1 shape, SB-2 language (+heal) | degenerate/contract-violating boards poisoning a 48 h cache | **yes — pre-cache only** (P3 exception) |
| Static program gates | codegen → render | AST validity, RI-1..RI-3 | prose-in-play, missing imports, cross-scene refs | sanitize in place |
| Dry-run probe | compile → accept | per-beat geometry (3 classes) | overlap / clipping / text-over-shape | no — feeds repair |
| Vision QA ○ | rendered frames | pixel-level legibility | contrast, sparse frames, hierarchy | no — feeds repair |

### 9.1 The economics of gate placement

Each gate is placed where (defect cost downstream) × (detection cost here) is
minimized. Truncation is decidable for free at the provider (a flag) but costs a 48 h
poisoned cache two stages later. Geometry is undecidable before code exists, but the
probe makes it decidable *without paying for TTS or full rendering* — the dry run
stubs TTS and renders cheap. Pixel legibility is undecidable before pixels exist —
hence Vision QA sits last and is the only gate that pays render cost to run.

### 9.2 The probe (Static Validator) — measurement mechanics

`_OVERLAP_PROBE_SNIPPET` (`app/render.py`) is injected into a dry-run copy of the
program; it patches `Scene.play` and, after every beat, measures: text-bbox pairwise
overlap; text clipped at the frame edge; a diagram's stroke path crossing a text bbox.
Violations print as parseable `LAYOUT_VIOLATION:` lines (Verification IR).
False-positive safety is part of the contract, learned trap by trap:
`MathTex.get_fill_opacity()` is 0.0 at top level (use the family-aware
`_ovl_visible`); containers like `NumberLine`/`Arrow` carry their own points *and*
submobjects (check both); `NumberPlane`/`ComplexPlane` are backdrops, never
violations.

### 9.3 Verification results are artifacts

Every measurement lands in the sidecar (VI-1..VI-3), surfaces as a /timeline badge
(Clean / Repaired ×N / ⚠ overlaps / Raw), and is citable evidence for the roadmap's
stage grades. **Grades are earned from measurement, never guessed** — the roadmap's
L0–L3 rubric requires a run, a test, or a benchmark to change a grade.

### 9.4 Failure propagation and attribution

**Classify before repairing.** A failed render is triaged by
`_classify_render_failure(logs)` into `infra` | `latex` | `code`, and **only `code`
reaches the LLM repair agent**. This exists because the untriaged path was measured
doing real harm: an audio-provider outage produced a TTS traceback, the self-heal fed
it to the code rewriter, and the agent "repaired" a script that was never broken —
burning a metered call and re-rendering into the same outage. `infra` fails loudly
naming the failing system; `latex` has its own deterministic heal; `infra` wins over a
co-occurring `latex` marker because outages cascade. Generalized: **a repair loop must
first establish that the thing it can rewrite is the thing that failed.**

Failures propagate *forward as defects* and are attributed *backward by discipline*:
symptom → inspect-first stage → first move, codified in the roadmap §4 routing table.
The standing rule is **attribute upstream-first** along storyboard → code → render →
repair, using sidecars as the evidence trail — the Dalton cascade (Appendix G) is the
canonical trace: six runs, each fix revealing the next fault *upstream of where the
symptom appeared*. Architecturally: because stages communicate only through
serialized IRs, every defect is reproducible from its stage's input artifact, which
is what makes attribution tractable at all.

---

## 10. Memory architecture

Four memory systems, all content-addressed or bounded, none load-bearing for
correctness (every memory is a cache over a recomputable function — P1 is never
delegated to memory):

### 10.1 Storyboard cache ●
`.storyboard_cache/`, keyed on topic+persona+language+style+grade+subject+node_type
(48 h TTL), or on the grounding-chunk sha256 with *no* TTL when chunks are present
(grounded content doesn't go stale with time, only with source change). Admission
gates run **before** the write — the cache stores only verified boards (P8). Missing:
a `SCOPE_VERSION` key field for selective invalidation after prompt fixes.

### 10.2 Shared TTS cache ●
`.tts_cache/` at repo root — content-addressed on request intent (text+voice+provider
shape), gated inside `UniversalTTSService.generate_from_text` so it covers Sarvam,
the Gemini delegate *and* the fallback: a clip synthesized by the fallback still
satisfies identical future requests. Atomic writes; safe under parallel per-scene
renders; failures non-fatal. **The design target it exists for: a repair re-render
bills zero TTS calls** (pinned by `test_tts_shared_cache.py`). TTS is the dominant
metered cost, so this cache is the single largest cost lever in the system.

### 10.3 Job store ●
`JobStore` (`app/jobs.py`) — bounded in-memory registry (dies with the process; the
durable `jobs.json` upgrade is roadmap §H). Sidecars are the durable half of job
state: the artifact record survives even though the job record doesn't.

### 10.4 Error→repair memory ◐
ChromaDB pairs (`app/rag.py`, `CHROMADB_ENABLED=1`): every accepted repair stores
(error fingerprint → fix). The read side — *pre-patching* a known failure before its
first render — was dropped in a merge except for the LaTeX path and is the roadmap's
last substantive stage-F gap. Specified target: fingerprint match ⇒ apply known fix
⇒ render once, instead of render-fail-repair-render.

### 10.5 Bulk-run stage caches ●
`bulk_runs/<run_id>/` — atomic manifest (one row per topic, status
`pending/storyboard/codegen/render/done/failed`) + per-topic storyboard.json /
code.json, so `--resume` re-bills **zero** LLM calls and retry-failed reuses stages.

---

## 11. Knowledge layer

What the system *knows* beyond its weights, in three tiers:

1. **Grounding context** (`storyboard_context.py`) — explicit YouTube URL transcript
   → topic-search transcript → NCERT node text. Reused for both pedagogy and
   storyboard so both stages cite the same source (P5 applied to knowledge).
   Open gap: no per-claim citation, nothing prevents invented numbers — the planned
   Rule 0 ("numbers/names must come from the source") plus fidelity spot-checks.
2. **Curriculum framing** — PARTS pedagogy, grade→wpm, persona/language contracts:
   compiled into prompts and code tables, versioned with the repo.
3. **Domain component knowledge** — the 106-entry keyword map, molecule construction,
   axis-range parsing conventions: deterministic lookup, never model recall (P2 —
   a molecule's structure is not something to hallucinate).

**Invariant:** knowledge flows *into* generation stages; generation never writes back
into the knowledge layer (memory §10 is where learned pairs go — the knowledge layer
stays human-curated).

---

## 12. Component library

`viz_helpers.py` — the runtime library every Render-IR program links against (the
"libc" of the system): `UniversalTTSService` (provider failover + shared cache),
`auto_fit_scene` / `clear_canvas` (canvas discipline), `get_smart_asset` /
`fetch_smart_svg` / `fetch_molecule_svg` (asset cascade with sanitize + preflight),
backgrounds, font/config injection.

**Contract with codegen (P10's home ground):** the program must carry the *star*
import in normalized form — a selective import satisfies a substring guard while
leaving library symbols undefined at render time and silently disabling the
font-injection that keys off the import line. Both incidents that taught this are
pinned in `test_minimize_split.py`.

**Planned:** route unknown shape keywords through `fetch_smart_svg` before the
`Circle()` fallback (roadmap D5) — the library, not the model, decides what "angle
diagram" looks like.

---

## 13. Scene graph

**Definition.** Per scene `s`: `G_s = (E_s, A_s ∪ M_s)` — elements as nodes;
**anchor edges** `A_s` (from `relative_positioning.relative_to`, typed by direction
+ buffer); **morph edges** `M_s` (from `transform` events and `math_evolution`
elements).

**Constraints.**
- **SG-1:** `(E_s, A_s)` is a DAG — the transpiler topo-sorts so every anchor target
  is constructed before its dependents; a cycle is a storyboard defect.
- **SG-2:** anchor edges never cross scenes (an anchored label rides *with* its
  diagram through screen-management shrinks — the reason diagram-anchored labels are
  exempt from the split trigger).
- **SG-3:** morph edges may cross scenes **only** in the master namespace (§6.7).
- **SG-4:** element ids are unique per scene; the `id→var` map is the scene's symbol
  table.

**Algorithms:** topo-sort (construction order); footprint estimation over node
bboxes (zone seeding, LI-2); reachability from cue events (lifetime analysis — the
Visual Director's input, §6.4).

**Compiler mapping:** node → constructor expression (`_build_obj_expr`); anchor edge
→ `next_to` with slot-checked direction; morph edge → `TransformMatchingTex` /
`ReplacementTransform`.

---

## 14. Timeline graph

**Definition.** The temporal spine: scenes in sequence; within scene `s`, cues
`c₁…cₙ`; within cue `i`, an ordered event list; `wait_time` terminates the scene.

**Beat model.** Beat `bᵢ` = duration of TTS(cᵢ) — *audio is the clock*; visuals fit
into narration, never the reverse. Entrance time for element `e` of type `t` in beat
`bᵢ`: `min(bᵢ, max(floor_t, frac_t × bᵢ))` (`_TIMING` — axes ≥1.5 s, math ≥1.0 s).
Known limitation: entrances play against *whole-cue* audio; the rest of each beat is
dead air until per-element beats land (roadmap C, "sync by construction" — split each
cue's narration per element so element k draws over beat k's real seconds).

**Constraints.** TL-1 events reference the current scene's symbols (per-scene worlds,
SG-3); TL-2 FadeOuts within a cue are batched into one `play()`, other actions fire
in sequence (deterministic event semantics); TL-3 a cue emptied by sanitization
still occupies its beat (RI-3) — narration timing survives visual dropouts.

**Cross-cutting invariant with §10.2:** the beat model is *why* the TTS cache is
correctness-relevant, not just cost-relevant — a repair re-render must reuse the
same audio or every beat length shifts and the repaired video desynchronizes.

---

## 15. Layout engine

The spatial half of the transpiler — full design in
[`stem_animation_lab/docs/layout_framework.md`](../../stem_animation_lab/docs/layout_framework.md);
this section states the model and its guarantees.

**Model.** The frame is partitioned into six named safe zones plus a center stage.
Standalone text *must* declare a zone (SB-3); the engine resolves collisions with a
per-zone **fallback chain** (claimed zone → next zone in chain → stacked placement
shifting toward frame center).

**The axes problem and its solution.** A coordinate system is not a zone citizen —
it's a variable-extent occupant whose real bbox depends on its ranges. The engine
estimates that bbox and **pre-claims every zone the footprint overlaps**
(`_seed_axes_zones`), so the ordinary fallback chains route text *around* the axes
with no new mechanism. Labels anchored to axes-hosted geometry get **slot analysis**
(`_fix_label_slots`): a label whose reference sits near a tick strip flips its
`next_to` direction away from the strip. Data-space placement (`c2p`) makes the
mathematics true; zone seeding makes it *legible*.

**Screen management.** When narration piles derivation text onto a live diagram, the
split-screen manager shrinks the diagram to the left half and stacks text in a right
column (§8 pass 5). The trigger was widened from math-only after a live job split on
zero of its scenes — real storyboards write derivation steps as `text`, so a
math-only trigger was nearly dead code. Evidence-driven trigger design is the
pattern to copy.

**Guarantees:** LI-1..LI-4 (§6.5) by construction; measured A/B on the raised-axes
fixture: 4 violations → 0. **Verification:** `test_axes_zones.py` +
render-verified via the probe — layout changes are verified by rendering, not only
by unit tests (house testing rule).

**Open gap (D7):** containment is not yet a placement primitive — "particles inside
a box" still trusts storyboard coordinates. Specified fix: a
`relative_positioning.relation: "inside"` form the engine resolves by clamping into
the container's bbox minus margin. Deterministic, no LLM (P2).

## 16. Animation engine

The temporal half. Entrances are keyed by element type (`_ENTRANCE_CONFIG`:
text→elastic FadeIn, math→Write, shape→GrowFromCenter, axes→Create), refined by
content keyword for shapes (`_SHAPE_ENTRANCES`: arrow→GrowArrow, line→Create,
point/dot→GrowFromCenter, closed shapes→DrawBorderThenFill) with keyword precedence
**deliberately mirroring the object builder** so the animation always matches the
object actually emitted (AI-1). Schema-specified animations win (AI-3). Rate-func
variety is by construction: elastic only on FadeIn targets, Write/Create smooth.
Event semantics per cue: batched FadeOuts, sequenced show/transform/highlight/move_to
(TL-2). Timing: the beat-capped `_TIMING` model (§14).

**Design position:** animation is a *vocabulary lookup*, not a creative act, at this
layer. Creative motion (camera language, semantic highlighting) belongs to the Visual
Director as *annotations* — keeping the engine deterministic and the judgment
strippable (P3).

### 16.1 Camera language, and why it stops where it does

The IR carries exactly one camera directive: **`focus`** — a semantic spotlight that
dims every other on-screen mobject, holds, and restores (`viz_helpers.spotlight_on` /
`spotlight_off`, emitted identically by both transpiler paths). Restoration replays
each mobject's *own* saved fill/stroke opacity, so a deliberately semi-transparent
shape comes back semi-transparent rather than being flattened to 1.0.

**Zoom and pan are deliberately absent, and this is an architectural constraint, not
a backlog item.** They require `MovingCameraScene`, and the Static Validator's
clipped-text check (§9.2) measures every text bbox against a *fixed*
`config.frame_width/height`. Under a moving camera that test becomes doubly wrong: it
would report legitimately off-frame content as clipped, and would miss text genuinely
clipped by the *current* viewport. Camera motion silently invalidates the system's
only independent geometric auditor — the exact failure mode P10 warns about, one
layer up. Opacity changes no geometry, so `focus` leaves every probe invariant
intact.

**The rule this generalizes to:** a rendering feature that invalidates a verifier must
ship *with* the verifier upgrade, never before it. Zoom/pan become available the day
the probe measures against the live camera frame instead of the config default.

## 17. Rendering layer

Backend-specific execution (Manim reference backend):

- **Parallel per-scene rendering** (`_render_scenes_parallel` → `_concat_scene_clips`,
  ffmpeg lossless concat; `PARALLEL_RENDER=0` disables) with a sequential
  single-script fallback. Measured payoff on the Dalton board: 406 s → 84 s, and
  4 violations → 0 *by construction* — per-scene renders start from a blank canvas,
  so the stale-text-from-a-previous-scene overlap class cannot occur.
- **Fallback discipline (P6):** partial parallel failure discards the orphan clips
  (P7) and falls back loudly; the weeks-long invisible failure of exactly this path
  is the system's canonical P6 incident.
- **TTS integration:** manim-voiceover with `UniversalTTSService`; the shared cache
  makes re-renders audio-free (§10.2); dry runs stub TTS entirely.
- **Quality ladder:** production renders low-quality (`quality: "l"`) for speed; the
  ladder is a knob, not an architecture property.
- **Ops:** render timeout; startup artifact sweeps (`SWEEP_MAX_AGE_HOURS`);
  allowlisted `env_overrides` per job (process-global last-writer-wins — a
  single-user debug affordance, explicitly *not* a concurrency mechanism).

## 18. Vision QA ◐ (implemented 2026-07-21)

The only gate that looks at pixels:

- **Measurement:** `VisionQAStage.critique(video_path)` (`app/pipeline/vision_qa.py`)
  extracts `VISION_QA_FRAMES` (6) evenly-spaced downscaled frames (ffmpeg) and makes
  ONE multimodal call (`call_vision_llm`, chain `VISION_QA_MODELS`, cheap tier — the
  rubric is a bounded checklist, P4) against the seven-class whitelist: clipped-text /
  colliding-text / unreadable-text / crowding / dead-frame / low-contrast /
  broken-hierarchy. Findings are lenient-parsed then shape- and whitelist-gated
  (P8/P10), timestamps snapped to frames actually sent, and emitted as
  `LAYOUT_VIOLATION: vision-<class> t=<sec>s <detail>` lines.
- **Repair:** `render._run_vision_qa` — sequential path runs an accept-if-better
  round (`VISION_QA_REPAIR`, rounds default 1 since each acceptance test is a metered
  re-critique): candidate must render, must NOT increase geometric violations
  (never trade a probe regression for a vision improvement), and must strictly
  reduce vision findings.
- **Scene-scoped repair on the parallel path** (`_repair_scenes_vision`, shipped
  2026-07-21): `_attribute_vision_findings` maps each finding's concat timestamp to
  the clip whose window contains it (ffprobe durations; timestamps rebased to
  scene-local time so the brief matches the script being edited), and only those
  scenes are rewritten and re-rendered. **The acceptance altitude differs from the
  geometric loop on purpose:** probe measurement is free, so overlap repair can
  accept per scene; a vision critique is metered, so vision repair accepts at the
  *artifact* level — re-concat once, re-critique once, accept only if total findings
  strictly drop (each scene candidate must also not raise its own geometric count).
  Unattributable findings stay report-only rather than guessing a scene to rewrite.
  *Ordering constraint (learned in review):* the per-scene clips must outlive the
  vision stage — discarding them first silently reduces this to report-only, the
  P6 shape.
- **Placement rationale (§9.1):** it pays render cost to run, so it sits after
  rendering and remains non-fatal (P3): improve or stand aside — pinned failure
  modes: no key, ffmpeg failure, model refusal, malformed JSON all yield zero
  findings, never an error.
- **Defect classes it owns** (all observed in the §3c manual review, invisible to
  the geometry probe): dim formula on dark ground; one tiny box top-left with 90%
  dead frame; near-equal visual weight everywhere.
- **Metrics rubric:** Appendix E. **Harness:** `test_vision_qa.py` (19 checks).
- **First live evidence (2026-07-21, refraction board, parallel path):** 6/6 sampled
  frames flagged `vision-dead-frame`; a manual pull of the t=46 s frame confirmed the
  critique exactly (one small diagram in ~85% empty frame). Sidecar:
  `{repair_rounds: 4, violations_remaining: 3, scenes_repaired: 1, vision_findings: 6}`
  — geometric and vision counts held separate, as specified (VI-2). The findings
  route upstream to composition (§7.3 hierarchy/§7.2 richness), demonstrating §9.4's
  attribution discipline end-to-end.

## 19. Repair loop

The system's signature mechanism — enhancement under a monotonicity guarantee.

**State machine (per artifact):**

```
        ┌────────────────────────────────────────────────┐
        ▼                                                │
   INCUMBENT (verified artifact, violations V > 0)       │
        │  round r ≤ OVERLAP_REPAIR_ROUNDS               │
        ▼                                                │
   brief = _overlap_error_report(violations)             │
   candidate = LLM_rewrite(script, brief)                │
   render candidate → V'                                 │
        │                                                │
        ├─ fails to render      → discard candidate ─────┤   (P1 + P7)
        ├─ V' ≥ V               → discard candidate ─────┤
        └─ V' < V               → candidate becomes INCUMBENT;
                                  discard superseded file; loop or exit
```

**Invariants:** R-1 *artifact monotonicity* — the shipped video's violation count is
the minimum ever observed; R-2 *no-leak* — a rejected round leaves **zero** net new
mp4s on disk (the harness asserts exactly this; the original "exactly one new mp4"
spec was corrected when the fix landed — the candidate renders and must then be
deleted); R-3 *honest accounting* — sidecar reflects the shipped file (VI-2); R-4
*scene scoping* — on the parallel path only flagged scenes re-render and re-concat
happens only if a scene actually improved.

**Why LLM-in-the-loop is safe here and nowhere else upstream:** repair is the one
place where a stochastic rewrite is *fully sandwiched* — measured input (violation
brief), measured output (re-probe), monotone gate, bounded rounds. The architecture
permits model creativity exactly where verification is total.

**Sidecar semantics for operators:** `violations_remaining > 0, repair_rounds > 0`
means "repair ran and could not do better" (LLM unavailable or every candidate
rejected) — check job logs for which. Since the parallel path repairs (2026-07-20),
`repair_rounds: 0` with violations means the repair agent never ran.

---

## 20. Scalability

Scaling dimensions and their mechanisms:

- **Within a video:** per-scene parallel rendering (thread pool via
  `RENDER_EXECUTOR`); scene-scoped repair (only flagged scenes re-render).
- **Across videos:** the bulk runner — topic-level thread pool (default 2) over an
  atomic manifest; the server's executor throttles renders; per-topic stage caches
  make resume O(remaining work) with zero re-billing.
- **Across time:** content-addressed caches (§10) convert repeat topics into cache
  hits; the storyboard's grounding-chunk key makes grounded reruns free until the
  source changes.
- **Cost scaling:** the metered-edge discipline (P4) means marginal cost per video is
  dominated by first-run TTS + 2–3 LLM calls; repair rounds add LLM but zero TTS.
- **Repair cost is serial, and that now dominates.** Both scene-scoped loops
  (geometric and vision) rewrite and re-render flagged scenes one at a time; a board
  with 4 flagged scenes pays 4 LLM calls plus 4 full scene renders back to back. The
  fix serves both loops: batch the (independent) LLM rewrites, then re-render the
  candidates through `_render_scenes_parallel`. Worth doing before Vision QA is
  enabled by default.
- **Known ceilings (roadmap §H, honest):** in-memory job registry (a crash loses
  "what was running"); no cost ledger (cannot answer "what did this video cost");
  artifacts scatter across three directories pending per-run folders; **no wall-clock
  deadline on the LLM edge** — the OpenAI-compatible path sets `timeout=120`, but the
  google-genai client sets none, and with no stale-job detection a wedged provider
  would leave a job `running` forever. These are operational-maturity gaps, not
  architectural blockers — the specified fixes (durable `jobs.json`, cost ledger with
  *cached-is-not-free* and *unknown ≠ $0* accounting, `runs/<topic-hash>/` folders,
  per-phase deadlines) slot into existing seams.

---

## 21. Extensibility — the Renderer Backend Contract

**Claim (G7):** everything above the Layout Engine is renderer-independent. The
Storyboard IR speaks in instructional abstractions — elements, meanings, anchoring
relations, narration beats — none of which name a graphics API (§6.3's noted
vocabulary impurity aside). Therefore a new renderer is a *backend*, attached at the
IR waist, implementing this contract:

```
interface RendererBackend:
    transpile(sb: StoryboardIR, opts) -> Program, PerScenePrograms
        # deterministic; owns ALL geometry (P2); implements the zone model,
        # anchoring, data-space placement, and the entrance-vocabulary mapping
    compile(program, quality) -> Artifact | CompileError
    probe(program) -> [Violation]
        # cheap, audio-stubbed, false-positive-safe; emits the shared
        # Verification-IR line format
    discard(artifact)                       # P7 — every backend owns its losers
    sidecar(artifact, meta)                 # VI-1..VI-3
```

The repair loop, admission gates, caches, bulk runner, timeline UI, and both agent
stubs consume only IRs and this interface — they port for free.

**Per-backend analysis:**

| Backend | Program form | Probe strategy | Backend-specific work |
|---|---|---|---|
| **Manim** (reference) | Python scripts | patched `Scene.play` dry run | — (this repo) |
| **SVG/web (SMIL/CSS)** | animated SVG document | DOM geometry queries (`getBBox`) per beat — the cheapest probe of all | element→SVG primitive map; TTS sync via `<audio>` + time offsets |
| **Three.js** | scene-graph JSON + driver | headless browser, project bboxes to screen space per beat | camera model (the Visual Director's camera annotations become first-class); font rendering to sprites/SDF |
| **Blender** | `bpy` script | scene-graph bbox queries in camera space (no GPU render needed) | 2D→3D staging conventions; render farm economics change the repair loop's cost calculus (fewer, better-briefed rounds) |
| **Unity** | C# scene builder | editor-mode bounds queries | asset pipeline; interactive extensions (the one backend where "video" can become "explorable") |

**What each backend must re-derive vs. reuse:** the zone model, beat model, entrance
*semantics* (appear/draw/grow intents), and all invariants LI-*/AI-*/RI-* are
backend-neutral and reusable as specification; only their *implementations* are
per-backend. The probe's three violation classes are defined on text bboxes and
stroke paths — meaningful in every backend listed.

**Falsifiable test of G7:** the SVG backend is the cheapest experiment — if building
it forces a Storyboard-IR schema change beyond the §6.3 vocabulary rename, G7 was
violated and the leak becomes a v2 finding.

---

## 22. Comparison with existing system classes

Positioning against the four architecture classes observable in the wild (compared
as *classes*, not products — the claim is architectural):

**(a) One-shot LLM codegen** ("prompt → Manim code"). No IR, no gates, no repair.
Every failure class this repo's incident log records — geometry guessing, language
inversion, truncation-as-valid-JSON, prose in `play()` — is unguarded by
construction. Works impressively on demo topics; unshippable at curriculum scale
because there is no place to *install* a lesson learned. The incident log **is** the
argument: each entry became a gate or a pass here; in class (a) it becomes a prompt
tweak that decays.

**(b) Template/slide systems** (parameterized scene templates, PowerPoint-style
generators). Deterministic and reliable, but the ceiling is the template library —
no novel visual explanation ever emerges. This architecture keeps class (b)'s
determinism *below* the waist (transpiler, component library) while letting models
own meaning *above* it.

**(c) Avatar/talking-head video generators.** Narration-first, visuals decorative;
no notion of a scene graph or data-space correctness — orthogonal to G1/G2.

**(d) Agentic pipelines with verification** (the sibling Video_Notebook_LM project is
the studied exemplar — roadmap §0 imports its lessons: bulk orchestration, script
critic, cost ledger, *a QC gate improves or stands aside*). This system's
distinguishing contributions within class (d): the **deterministic transpiler as the
sole full-scene codegen path** (peers typically LLM-decorate per block), the
**measured accept-if-better repair loop** with artifact monotonicity and no-leak
guarantees, and the **multi-IR ladder with admission-gated caching**.

**What "reference architecture" means as a research claim:** the reusable artifact is
not the code — it's the layer boundaries + IR contracts + invariants + the
verification placement economics (§9.1), each earned against a recorded failure.
Section 21's contract is the test: an implementation in a different renderer that
keeps the invariants is an instance of the architecture.

---

## 23. Formal system properties

Per-layer property matrix. **D** = deterministic (same input → same artifact),
**C** = correctness guarantee on exit, **Cp** = completeness requirement on exit,
**Cm** = composability (output consumed as-is downstream), **X** = replaceable
without upstream change, **R** = recoverable without restarting the pipeline.

| Layer | D | C (guarantee) | Cp (must exist on exit) | Cm | X | R |
|---|---|---|---|---|---|---|
| Pedagogy Planner | ✗ (LLM) | scene floor PI-1; single wpm source PI-2 | needed/type/objective/duration | ✓ Pedagogy IR | ✓ any planner emitting the IR | retry per node |
| Storyboard Gen + gates | ✗ gen / ✓ gates | SB-1..SB-4 on every cached board | scenes, cues, elements, positions | ✓ Storyboard IR | ✓ (IR waist) | provider chain; heal; cache |
| Visual Director ◐ | ✗ (LLM) | strip-invariance (§6.4); per-proposal safety gates | nothing — pure refinement | ✓ annotations | ✓ removable | stand aside (P3) |
| Layout Engine | **✓** | LI-1..LI-4 by construction | every element positioned | ✓ Layout IR | per-backend impl of shared model | n/a (deterministic) |
| Animation Planner | **✓** | AI-1..AI-3 | every element timed + animated | ✓ Animation IR | vocabulary map per backend | n/a |
| Component Retrieval | ✓ given cache | sanitized assets; preflight degrade | all assets resolved or substituted | ✓ | per-backend asset form | primitive fallback |
| Codegen/Compiler | ✓ (critic optional) | RI-1..RI-3 | master + per-scene programs | ✓ Render IR | **the** backend seam (§21) | sanitize in place |
| Static Validator | **✓** | false-positive-safe measurement | violation stream (possibly empty) | ✓ Verification IR | per-backend probe, shared format | n/a |
| Vision QA ◐ | ✗ (vision LLM) | whitelist-gated findings; geometric non-regression on repair | nothing — non-fatal | ✓ same consumer | ✓ | stand aside |
| Repair Agent | ✗ gated by ✓ | R-1..R-4 (monotonicity, no-leak) | sidecar (VI-1..VI-3) | ✓ final artifact | backend-neutral loop | **the** recovery layer |

Reading the matrix: determinism alternates with judgment down the whole stack
(§4 fact 1); every ✗-D layer is bracketed by ✓-D gates; and the two ◐ agent layers
are exactly the ones whose absence degrades quality but never correctness — which is
why they could ship first as stubs and then as flag-gated implementations
(2026-07-21) without violating any invariant.

---

## Appendix A — Formal IR schemas

Machine-checked, committed, drift-gated:

- [`stem_animation_lab/schemas/storyboard-ir.schema.json`](../../stem_animation_lab/schemas/storyboard-ir.schema.json)
  — JSON Schema for the Storyboard IR, **exported from** the live Pydantic models
  (`app/schemas.py:StoryboardResponse.model_json_schema()`). The Pydantic models are
  the source of truth; the committed file is the published contract.
- [`stem_animation_lab/schemas/render-verification-ir.schema.json`](../../stem_animation_lab/schemas/render-verification-ir.schema.json)
  — the sidecar contract (authored; the writer is `**meta`-typed).
- **Drift gate:** `stem_animation_lab/test_ir_contracts.py` fails if the committed
  storyboard schema no longer matches the live export (a schema change must be a
  *decision*, committed with a regenerated file), validates golden/degenerate
  fixtures through the models, and checks sidecar shapes against the contract.
  Regenerate after an intentional model change:
  `.venv/bin/python stem_animation_lab/test_ir_contracts.py --regen`.

## Appendix B — Agent prompts & communication protocols

Prompts live with their agents, versioned with the repo: storyboard + heal prompts
(`app/storyboard.py`), critic rules `LAYOUT_RULES` (`app/codegen.py`), repair brief
builder (`app/render.py:_overlap_error_report`), pedagogy prompts
(`ce/planner_agent.py`). Protocol rules: agents exchange only IRs (§7.11);
structured outputs are Pydantic-validated; every lenient parse pairs with a gate
(P8); provider chains and `LLM_MAX_TOKENS=16000` in `app/llm.py`. A prompt that
encodes a quantity owned elsewhere is a P5 violation — prompts state *intent*,
tables state *numbers*.

## Appendix C — Scene DSL serialization rules

JSON; UTF-8; math as LaTeX without surrounding `$`; `math_evolution` as
`FROM → TO` with a literal `→`; axis ranges as `'x:MIN-MAX, y:MIN-MAX'` parsed by
the transpiler; colors as hex or Manim names; ids `snake_case`, unique per scene;
pacing tags `[SPEED: …]`/`[PAUSE: …]` inline in cues (stripped for TTS, must never
be cut mid-tag — SB-1). Lenient parsing on ingest (`loads_json_lenient`) is *always*
followed by shape gating (P8).

## Appendix D — Compiler passes

The nine passes of §8, with their homes: normalization (`transpiler.py` keyword/
content parsers) · scene-graph topo-sort · `_seed_axes_zones` · placement lowering
(zones, `next_to`, `_fix_label_slots`, `c2p`) · `_maybe_minimize_diagram` ·
animation lowering (`_ENTRANCE_CONFIG`/`_SHAPE_ENTRANCES`/`_TIMING`) ·
`_sanitize_anim_calls` · per-scene splitting (`_drop_cross_scene_events`/
`_drop_foreign_id_calls`) · `sanitize_generated_code` (star-import, font, Indic
backstop, LaTeX markers). Optimization posture: passes prevent violation classes
(zero-cost at runtime) rather than optimizing render speed; the one performance
pass is per-scene splitting (406 s → 84 s measured).

## Appendix E — QA metrics & scoring

Per-video scorecard (sidecar-resident today, extended by Vision QA):
`violations_remaining` by class · `repair_rounds` / `scenes_repaired` ·
`animation_beats` · render duration · dropped-event count (specified: thread
`[TRANSPILER] dropped` through the codegen response into the sidecar so /timeline
can badge "storyboard wrote prose ×N"). Vision rubric (§18): clipped/colliding/
unreadable text, crowding, dead-frame ratio, contrast violations, hierarchy.
Fidelity (planned): N facts per video traced to a grounding chunk, pilot bar ≥95%.
Grading discipline: L0–L3 per stage, changed only with cited evidence
(roadmap §5).

## Appendix F — Benchmark suite

The deterministic harness battery is the regression benchmark (all LLM-stubbed, no
keys; 186+ checks green as of 2026-07-21): `test_overlap_probe.py` (32, real
renders) · `test_axes_zones.py` (14) · `test_tts_shared_cache.py` (10) ·
`test_event_sanitize.py` (20) · `test_minimize_split.py` (20) ·
`test_entrance_map.py` (14) · `test_storyboard_gate.py` (26) ·
`test_layout_safety.py` · `test_ir_contracts.py` (19, this spec's Appendix A gate +
the provider completeness rule) · `test_director.py` (33, §7.3's application safety
rules, enlarge-to-fill, and §16.1 focus gating) · `test_vision_qa.py` (35, §18's
gates, §19's accept-if-better rounds, §9.4 failure classification, scene-scoped
attribution) · `test_tts_resilience.py` (14, §7.5a's retry + keyless chain).
End-to-end benchmark topics (run live, graded by audit): distance between two
points (geometry/axes) · Dalton's law (multi-scene, language contract) · refraction
through a glass slab (heal path) — chosen because each historically broke a
different layer. House rule worth restating as method: **rendering one real video
is worth more than another round of code reading** — harnesses verify layers;
only end-to-end runs verify composition.

## Appendix G — End-to-end case study: Dalton's law

The recorded 2026-07-20/21 trace (roadmap §3b–§3c) — one instruction, six runs,
each fix revealing the next fault upstream; reproduced here as the architecture's
own failure-propagation evidence:

| Run | Result | Fault → principle installed/vindicated |
|---|---|---|
| 1 | HTTP 500 | missing `json_repair` dep → env gotcha recorded |
| 2 | 2.9 s video, cue cut mid-tag | truncation closed into valid JSON → **P8** (finish_reason gate + shape gate) |
| 3 | 23.7 s, never states the law | two stages encoded lesson length; upstream won → **P5** (scene floor) |
| 4 | 94.2 s ✓ but sequential, 4 violations unrepaired | client discarded `scene_scripts`; fast path dead in production → **P6** |
| 5 | 3 of 4 scenes NameError | cross-scene refs in closed-world scripts → **SG-3 / §6.7 dropping** |
| 6 | **92.7 s, 4 scenes, 0 violations, 84 s total** | shipped — parallel, clean by construction |
| review | audio/composition defects at `violations_remaining: 0` | probe measures geometry, not language or pixels → **SB-2 gates + §18 Vision QA spec** |

The sequence is the architecture's thesis in miniature: every fault was a *missing
gate at a layer boundary*, every fix was a gate or a pass — never a prompt tweak —
and the final state ships clean *by construction* with the probe as auditor.

---

*Maintenance: this spec is a living doc (see CLAUDE.md → Operating discipline). A
change to a layer's contract lands here, in its schema file, and in its harness in
the same pass. Status markers (●◐○◇) are updated when evidence changes them —
grades are earned, never guessed.*
